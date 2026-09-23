"""`_stratified` decides what a short eval run actually looks at, and
`--replay` decides whether `kv-eval` calls a model at all.
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from kubeagent_verdict.evals import score
from kubeagent_verdict.evals.cli import _format_smoke_line, _stratified, main

CASES = ["attributed", "empty_candidates", "injection", "misattribution_probe",
         "none_of_these", "own_cause", "positional_probe", "shared_origin_probe",
         "truncated", "wrong_attribution"]


def _rows():
    return [{"meta": {"case": case}, "i": i}
            for case in CASES for i in range(19)]


def _cases_in(rows):
    return {r["meta"]["case"] for r in rows}


# Round-robin in plain alphabetical order put `positional_probe` ninth of nine,
# so `--limit 6` dropped it entirely — the same "keeps whichever bucket comes
# first" defect this function was written to close, rekeyed from file order to
# case name. The adversarial slices are the rows that can fail; a short run
# exists to look at them.
def test_a_short_limit_keeps_the_adversarial_slices():
    for limit in (3, 5, 6):
        cases = _cases_in(_stratified(_rows(), limit))
        assert "positional_probe" in cases, f"dropped at limit={limit}"
        assert "misattribution_probe" in cases, f"dropped at limit={limit}"


# `shared_origin_probe` is the only slice that can fail on the SUMMARY alone —
# every verdict right and the summary still calling the workloads independent.
# A short run that drops it reports "n/a" on Job 3's `shared` row, which reads
# as "nothing to see" rather than "not looked at".
def test_a_short_limit_keeps_the_shared_origin_slice():
    for limit in (5, 6):
        assert "shared_origin_probe" in _cases_in(_stratified(_rows(), limit)), limit


def test_stratified_returns_exactly_the_limit():
    assert len(_stratified(_rows(), 7)) == 7
    assert len(_stratified(_rows(), 40)) == 40


def test_every_case_survives_once_the_limit_allows_one_each():
    assert _cases_in(_stratified(_rows(), len(CASES))) == set(CASES)


def test_a_limit_above_the_row_count_returns_everything():
    rows = _rows()
    assert len(_stratified(rows, 10_000)) == len(rows)


# A limit below the case count MUST drop cases — there is no way around that.
# What it must not do is drop them quietly: a scoreboard covering three of nine
# cases looks exactly like one covering all nine.
def test_dropped_cases_are_named_rather_than_dropped_in_silence():
    from kubeagent_verdict.evals.cli import PROBES_FIRST, _dropped_cases
    rows = _rows()
    # The limit is derived, not typed: it is exactly the probe cases this
    # fixture carries, so the assertion states the invariant rather than a
    # coincidence of how many probe slices happened to exist when it was
    # written. A hardcoded 3 silently stopped meaning "keep the probes" the
    # moment a fifth probe slice was added.
    probes = set(CASES) & set(PROBES_FIRST)
    dropped = _dropped_cases(rows, _stratified(rows, len(probes)))
    assert set(dropped) == set(CASES) - probes
    assert _dropped_cases(rows, _stratified(rows, len(CASES))) == []


# The smoke block scores real kubeagent rule rows, not exam workloads, and its
# print text said so once before drifting to "decided workloads" -- the exam's
# own job-1 population name -- when job 1's population was renamed elsewhere.
# This pins the smoke line's wording so that drift fails a test instead of
# only a design-doc grep.
def test_smoke_line_names_rule_rows_not_decided_workloads():
    line = _format_smoke_line("02", 1, 4)
    assert line == "  02: job 1 scored 1 of 4 rule rows"
    assert "decided workloads" not in line


# --------------------------------------------------------------- --replay


def _run_cli(argv: list[str]) -> None:
    """Run `cli.main()` with `sys.argv` set to `argv`, restored afterward --
    the same "patch argv, call main()" pattern test_probe_wide.py and
    test_train_checkpoint.py use, minus the `monkeypatch` fixture: this
    helper is called from inside a test body rather than taking a fixture
    parameter itself.
    """
    with mock.patch.object(sys, "argv", ["kv-eval", *argv]):
        main()


def _replay_rows() -> list[dict]:
    """Two job-2 rows shaped like tests/test_score.py's ROW fixture: distinct
    cases and a non-empty `own_cause_keywords`, so `score.evaluate`'s
    job-2 pre-pass gate (Task 3's `UngradableWorkload` check) passes and the
    rows can be scored for real rather than stubbed.
    """
    def row(case: str, workload: str, keyword: str) -> dict:
        cause = f"{keyword} pressure too high"
        return {
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": f"user {workload}"},
                {"role": "assistant", "content": json.dumps({
                    "verdicts": [{"workload": workload, "cause": cause,
                                  "confidence": "high", "rationale": "r"}],
                    "summary": "s"})},
            ],
            "meta": {"case": case, "label": "none",
                     "workloads": {workload: {
                         "job": 2, "decided": False, "decided_cause": "",
                         "decided_outcome": "", "decided_evidence": "",
                         "expected_cause": cause,
                         "own_cause_keywords": [keyword]}}},
        }
    return [row("attributed", "shop/api", "memory"),
            row("own_cause", "shop/worker", "disk")]


def _write_test_file(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "test.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _prior_run(tmp_path: Path, rows: list[dict], *, name: str = "eval-0920-fixture",
               write_results: bool = True, write_scoreboard: bool = True,
               drop_result: bool = False, corrupt_case_at: int | None = None) -> Path:
    """A prior run directory holding real `results.jsonl` + `scoreboard.json`,
    scored by replaying each row's own gold reply as its own chat_fn -- the
    same oracle trick tests/test_oracle.py's `_gold_results` uses. That makes
    the fixture behave like a real prior run rather than a hand-typed stub,
    while still letting a test corrupt one row (`corrupt_case_at`) or shorten
    the file (`drop_result`) to exercise a refusal.
    """
    gold = iter(r["messages"][2]["content"] for r in rows)
    results = score.evaluate(rows, lambda _messages: next(gold))
    if corrupt_case_at is not None:
        results[corrupt_case_at] = {**results[corrupt_case_at],
                                    "case": "not-a-real-case"}
    if drop_result:
        results = results[:-1]

    run_dir = tmp_path / name
    run_dir.mkdir()
    if write_results:
        with open(run_dir / "results.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in results)
    if write_scoreboard:
        board = score.scoreboard(results)
        board["run"] = {"model": "kubeagent-verdict-0.6b-q8_0.gguf",
                        "endpoint": "http://127.0.0.1:8080/v1"}
        (run_dir / "scoreboard.json").write_text(json.dumps(board), encoding="utf-8")
    return run_dir


def test_replay_refuses_a_model(tmp_path, capsys):
    """A replay calls nothing. Accepting --model would write a scoreboard
    naming a model that produced none of its replies.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior),
                  "--out", str(out), "--model", "some.gguf"])


def test_replay_refuses_a_limit(tmp_path):
    """`evaluate` calls chat_fn once per row in order, so a replay lines up
    by position. --limit drops rows and breaks that alignment silently.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior),
                  "--out", str(out), "--limit", "10"])


def test_model_is_still_required_without_replay(tmp_path):
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--out", str(out)])


def test_replay_refuses_a_prior_run_of_a_different_length(tmp_path):
    """Positional alignment is the whole contract. A length mismatch means
    the stored replies answered a different set of rows.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows, drop_result=True)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior), "--out", str(out)])


def test_replay_refuses_a_case_mismatch(tmp_path):
    """A stored reply's `case` must match its row's -- catching the mistake
    that actually motivates this guard, replaying one run's replies over a
    different run's rows, even when the two happen to share a row count.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows, corrupt_case_at=0)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior), "--out", str(out)])


def test_replay_refuses_a_missing_results_file(tmp_path):
    """A replay with no stored replies beside it has nothing to re-score."""
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows, write_results=False)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior), "--out", str(out)])


def test_replay_refuses_a_missing_scoreboard(tmp_path):
    """A replay with no scoreboard beside it has no provenance to carry
    forward, and inventing one is worse than refusing.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows, write_scoreboard=False)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior), "--out", str(out)])


def test_replay_records_where_the_replies_came_from(tmp_path):
    """`rescored_from` names the run, reduced the same way `provenance`
    reduces `model`: a basename, because --replay /home/<user>/... is
    accepted and /home/ is one of the five leak shapes the provenance
    denylist exists to catch. The model and endpoint are carried forward
    from the replayed run's own scoreboard -- that is who produced these
    replies, and inventing anything else would be a false provenance.
    """
    rows = _replay_rows()
    test_file = _write_test_file(tmp_path, rows)
    prior = _prior_run(tmp_path, rows)
    out = tmp_path / "out"
    _run_cli(["--test", str(test_file), "--replay", str(prior), "--out", str(out)])
    board = json.loads((out / "scoreboard.json").read_text())
    assert board["run"]["rescored_from"] == "eval-0920-fixture"
    assert board["run"]["model"] == "kubeagent-verdict-0.6b-q8_0.gguf"
    assert board["run"]["endpoint"] == "http://127.0.0.1:8080/v1"
