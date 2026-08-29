from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

from kubeagent_verdict.evals import client, score

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
    field of the run block is a property of the serving side or a basename —
    so without this, two scoreboards scored against two different datasets
    carry an identical claim about what they scored.

    The digest is over the manifest's bytes, which is what makes this a
    complete answer rather than a summary of four fields: a manifest that
    grows a key still changes the hash, with no audit of the new key against
    the leak denylist. The three named values are integers or absent — a
    string is dropped rather than copied — so this block cannot carry a
    filesystem path however the manifest is written. The corpus file list is
    never copied at all.

    A `--test` file with no manifest beside it is a hand-made test set, not an
    error: the answer is `None`, and so is an unreadable or unparseable
    manifest. This block records provenance; it must not be able to fail a run.
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
    return {
        "seed": _int(m.get("seed")),
        "size": _int(m.get("size")),
        "test_rows": _int(m.get("test")),
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
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


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-eval")
    p.add_argument("--test", type=Path, required=True)
    p.add_argument("--endpoint", default=client.DEFAULT_ENDPOINT)
    p.add_argument("--model", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--limit", type=int)
    args = p.parse_args()

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

    results = score.evaluate(
        rows, lambda messages: client.chat(args.endpoint, args.model, messages))
    board = score.scoreboard(results)
    board["run"] = provenance(args.model, args.endpoint, args.test,
                              len(rows), available,
                              dataset=dataset_provenance(args.test))
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "results.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in results)
    (args.out / "scoreboard.json").write_text(
        json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = score.render_markdown(board)
    (args.out / "scoreboard.md").write_text(md, encoding="utf-8")
    print(md)
