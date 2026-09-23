from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

from kubeagent_verdict.evals import client, score, smoke

# The slices a short run exists to look at. Everything else can only pass.
# `shared_origin_probe` sits beside the other multi-workload slice: both put
# several flagged workloads in one prompt, and it is the only slice that can
# fail on the summary alone, so a short run that dropped it could not see the
# axis it was added to measure.
PROBES_FIRST = ("contradiction_probe", "positional_probe", "misattribution_probe",
                "multi_misattribution_probe", "shared_origin_probe",
                "wrong_attribution")


def _case(row: dict) -> str:
    return row.get("meta", {}).get("case", "unknown")


def _int(value) -> int | None:
    """An integer, or nothing. `True` is an `int` in Python; a flag is not a count."""
    return value if type(value) is int else None


def dataset_provenance(test: Path) -> dict | None:
    """Which dataset the `--test` file came from, read from its manifest.

    The one impure function here besides `main`: it reads `manifest.json` from
    the directory holding the test file. `provenance` below stays a pure
    function of its arguments, so this is called at the one call site in
    `main` and handed in.

    A retrain overwrites `out/dataset/test.jsonl` in place, and every other
    field of the run block is a property of the serving side, a basename, or a
    row count two same-sized test sets share — so without this, two scoreboards
    scored against two different datasets carry an identical claim about what
    they scored.

    TWO digests, because either alone leaves a gap. `manifest_sha256` covers
    the manifest's bytes, so a manifest that grows a key still changes the
    hash with no audit of the new key against the leak denylist — a stronger
    answer than a summary of the three named fields. But `kv-dataset` writes
    `test.jsonl` and `manifest.json` as two separate writes and nothing
    afterwards ties them, and the file the eval actually read is the test
    file: a hand-edited `test.jsonl` beside an untouched manifest would
    otherwise produce an identical, complete-looking block. `test_sha256`
    covers the test file's bytes — not proof they are the scored bytes, since
    `main` reads the file, runs the whole eval, and only then calls this, so a
    file replaced mid-run hashes as its replacement. It catches the case that
    motivates it: an edit made before the run rather than during it. Together
    the two say which dataset was generated AND which rows the file held;
    neither says it alone.

    Both are digests of files this process only reads, so what they can prove
    is limited to matching or not matching another run's. The three named
    values are integers or absent — a string is dropped rather than copied —
    so this block cannot carry a filesystem path however the manifest is
    written. The corpus file list is never copied at all.

    A `--test` file with no manifest beside it is a hand-made test set, not an
    error: the answer is `None`, and so is an unreadable or unparseable
    manifest. An unreadable test file leaves `test_sha256` as `None` inside an
    otherwise complete block. That is not merely defensive: `main` reads the
    test file, then runs the whole eval over the network, and only then calls
    this — so the file has had the length of a scoring run to be moved,
    replaced or made unreadable. Provenance must not be the thing that raises.
    """
    try:
        raw = (test.parent / "manifest.json").read_bytes()
    except OSError:
        return None
    try:
        m = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(m, dict):
        return None
    try:
        test_sha = hashlib.sha256(test.read_bytes()).hexdigest()
    except OSError:
        test_sha = None
    return {
        "seed": _int(m.get("seed")),
        "size": _int(m.get("size")),
        "test_rows": _int(m.get("test")),
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "test_sha256": test_sha,
    }


def provenance(model: str, endpoint: str, test: Path,
               scored: int, available: int,
               dataset: dict | None = None) -> dict:
    """What this scoreboard scored — so two of them can never be confused.

    A release is argued from two scoreboards read side by side, tuned against
    untuned, and nothing else in the output directory says which model
    produced which. `--endpoint` defaults to Ollama's port, so a llama-server
    run that forgets the flag scores whatever Ollama is serving and writes a
    scoreboard indistinguishable from the intended one.

    Both fields are stripped of anything that could carry an operator's
    filesystem or a credential: the model keeps only its basename, because
    `--model /home/<user>/...gguf` is accepted and `/home/` is one of the five
    leak shapes the provenance denylist exists to catch, and the endpoint
    drops any `user:password@` userinfo. Neither reduction loses identity —
    a GGUF basename and a scheme/host/port/path are what distinguish two runs.

    `dataset` is `dataset_provenance`'s answer, or `None` when the test file
    has no manifest beside it. Passing it in rather than reading it here keeps
    this function pure.
    """
    parts = urlsplit(endpoint)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return {
        "model": PurePosixPath(model).name or model,
        "endpoint": urlunsplit((parts.scheme, host, parts.path, "", "")),
        "test_file": test.name,
        "rows_scored": scored,
        "rows_available": available,
        "limited": scored != available,
        "dataset": dataset,
    }


def _stratified(rows: list[dict], limit: int) -> list[dict]:
    """Take `limit` rows round-robin across cases, not off the front.

    The test file is written case-block by case-block, so a positional slice
    keeps whichever case happens to be first and silently drops the rest —
    including both adversarial probe slices, which sit at the end. A short
    run must sample the shape of the test set, not its prefix.

    Round-robin alone did not deliver that. Walking the cases in plain
    alphabetical order puts `positional_probe` ninth of nine, so the trailing
    `[:limit]` dropped it for every limit below 7 and dropped
    `misattribution_probe` below 4 — reintroducing the very defect this
    function replaced, rekeyed from file order to case name. The probe slices
    therefore lead the walk: they are the rows that can actually fail, so a
    short run that cannot afford every case must spend what it has on them.
    """
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(_case(row), []).append(row)
    lead = [c for c in PROBES_FIRST if c in buckets]
    order = lead + sorted(c for c in buckets if c not in lead)
    out: list[dict] = []
    for i in range(max(len(b) for b in buckets.values())):
        for case in order:
            if i < len(buckets[case]):
                out.append(buckets[case][i])
    return out[:limit]


def _dropped_cases(rows: list[dict], kept: list[dict]) -> list[str]:
    """Cases the limit removed entirely. A silent cap reads as full coverage."""
    return sorted({_case(r) for r in rows} - {_case(r) for r in kept})


def _format_smoke_line(pair: str, job1_scored: int, total: int) -> str:
    """One smoke-block print line, isolated so its wording is unit-tested.

    The smoke set scores real kubeagent rule rows (`contract/smoke/README.md`,
    the design spec's `:800-804`), never the exam's job-1 "decided workloads"
    population -- that name belongs to `job1` alone. This function is the one
    place the line is built, so a rename that drifts the two apart fails a
    test instead of only a doc grep.
    """
    return f"  {pair}: job 1 scored {job1_scored} of {total} rule rows"


def replay_chat_fn(run_dir: Path, rows: list[dict]):
    """Stored replies from a prior run, as a `chat_fn`.

    `evaluate` calls `chat_fn` once per row, in order, so the stored `output`
    strings line up by position with no row identity lookup -- the same
    alignment `tests/test_oracle.py`'s `_gold_results` relies on. Two guards
    catch exactly two shapes of drift: a different number of stored replies
    than rows, and a stored reply whose `case` differs from its row's
    `meta.case` at the same position. Neither is, or claims to be, a check that
    the two runs share the same rows. `case` is a coarse label ("attributed",
    "own_cause", ...) shared by many rows, not a row identity, and
    `results.jsonl` stores nothing finer -- no prompt digest, no row id. The
    exam's rows come from `generate.test_set()`, which takes no seed or size,
    so its row count and case order do not depend on `--seed` or `--size` at
    all. Two exams whose prompts or expected causes differ but whose case order
    does not -- as any generator change that keeps the case order produces --
    pass both guards silently: same count, same case at every index. These
    guards cannot tell that pair apart. Confirming the prompts themselves match
    -- `messages` equal, row by row -- is the caller's job before trusting a
    replay; the 0920 re-score did this, diffing all 263 rows' `messages`
    between the original and regenerated datasets before running `--replay`.

    Returns `(chat_fn, prior_board)`. The board is the replayed run's own
    `scoreboard.json` -- its `run.model` and `run.endpoint` are carried into
    the new board, because that is who produced these replies.

    Raises `ValueError`, which `main` converts to `SystemExit` via
    `p.error`, naming the file when `results.jsonl` or `scoreboard.json` is
    missing, when the counts differ, or when a `case` mismatches at index
    *i*. A replay with no scoreboard beside it has no provenance, and
    inventing one is worse than refusing.
    """
    results_path = run_dir / "results.jsonl"
    board_path = run_dir / "scoreboard.json"
    try:
        lines = [line for line in
                 results_path.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        raise ValueError(f"--replay {run_dir}: no {results_path} to replay") from None
    try:
        board_raw = board_path.read_text(encoding="utf-8")
    except OSError:
        raise ValueError(
            f"--replay {run_dir}: no {board_path} to carry provenance from") from None

    stored = [json.loads(line) for line in lines]
    if len(stored) != len(rows):
        raise ValueError(
            f"--replay {run_dir}: {len(stored)} stored replies but "
            f"{len(rows)} test rows -- a replay lines up by position and "
            f"cannot re-score a different row count")
    for i, (result, row) in enumerate(zip(stored, rows)):
        stored_case, row_case = result.get("case"), _case(row)
        if stored_case != row_case:
            raise ValueError(
                f"--replay {run_dir}: row {i} case mismatch -- stored reply "
                f"is {stored_case!r}, test row is {row_case!r}")

    prior_board = json.loads(board_raw)
    run_block = prior_board.get("run")
    if run_block is None:
        raise ValueError(
            f"--replay {run_dir}: {board_path} has no run block to carry "
            "provenance from")
    for key in ("model", "endpoint"):
        if key not in run_block:
            raise ValueError(
                f"--replay {run_dir}: {board_path}'s run block has no "
                f"{key!r} to carry provenance from")
    outputs = iter(r["output"] for r in stored)

    def chat_fn(_messages: list[dict]) -> str:
        return next(outputs)

    return chat_fn, prior_board


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-eval")
    p.add_argument("--test", type=Path, required=True)
    p.add_argument("--endpoint", default=None,
                   help=f"defaults to {client.DEFAULT_ENDPOINT!r}; refused "
                        "with --replay, which calls no endpoint")
    p.add_argument("--model")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--replay", type=Path,
                   help="a prior run's output directory. Re-score the replies "
                        "it stored instead of calling a model.")
    p.add_argument("--no-job2", action="store_true",
                   help="skip job-2 grading, for probe sets built from "
                        "training scenarios, which carry no job-2 answer "
                        "keys; job 2 reads n/a")
    args = p.parse_args()

    if args.replay:
        if args.model:
            p.error("--replay re-scores stored replies and calls no model; "
                    "--model would name a model that produced none of them")
        if args.endpoint:
            p.error("--replay re-scores stored replies and calls no endpoint; "
                    "--endpoint would name a server that served none of them")
        if args.limit:
            p.error("--replay lines its stored replies up with the test rows "
                    "by position; --limit drops rows and breaks that")
        if args.out.resolve() == args.replay.resolve():
            p.error("--out must differ from --replay; a re-score must not "
                    "overwrite the run it re-scores")
    elif not args.model:
        p.error("--model is required")

    rows = [json.loads(line) for line in
            args.test.read_text(encoding="utf-8").splitlines() if line]
    available = len(rows)
    if args.limit:
        kept = _stratified(rows, args.limit)
        dropped = _dropped_cases(rows, kept)
        if dropped:
            print(f"note: --limit {args.limit} scores {len(kept)} of "
                  f"{len(rows)} rows and drops these cases entirely: "
                  f"{', '.join(dropped)}")
        rows = kept

    if args.replay:
        try:
            chat_fn, prior = replay_chat_fn(args.replay, rows)
        except ValueError as exc:
            p.error(str(exc))
        model, endpoint = prior["run"]["model"], prior["run"]["endpoint"]
    else:
        endpoint = args.endpoint or client.DEFAULT_ENDPOINT
        chat_fn = lambda messages: client.chat(endpoint, args.model, messages)
        model = args.model

    try:
        results = score.evaluate(rows, chat_fn, grade_job2=not args.no_job2)
    except score.UngradableWorkload as exc:
        p.error(f"{exc} Regenerate the rows with kv-dataset, or pass "
                "--no-job2 for a probe set built from training scenarios.")
    board = score.scoreboard(results)
    board["run"] = provenance(model, endpoint, args.test,
                              len(rows), available,
                              dataset=dataset_provenance(args.test))
    if args.replay:
        board["run"]["rescored_from"] = Path(args.replay).resolve().name
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "results.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in results)
    (args.out / "scoreboard.json").write_text(
        json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = score.render_markdown(board)
    if args.replay:
        md = (f"Re-scored from the stored replies of "
              f"`{board['run']['rescored_from']}`; no model was called.\n\n"
              f"{md}")
    (args.out / "scoreboard.md").write_text(md, encoding="utf-8")
    print(md)

    smoke_dir = Path(__file__).resolve().parents[3] / "contract" / "smoke"
    print("\nsmoke (not gated)")
    for pair in ("02", "03", "04"):
        smoke_request = json.loads(
            (smoke_dir / f"{pair}-request.json").read_text(encoding="utf-8"))
        smoke_response = json.loads(
            (smoke_dir / f"{pair}-response.json").read_text(encoding="utf-8"))
        pair_scores = smoke.score_smoke_pair(smoke_request, smoke_response)
        job1_scored = sum(1 for value in pair_scores if value == 1.0)
        print(_format_smoke_line(pair, job1_scored, len(pair_scores)))
