"""`_stratified` decides what a short eval run actually looks at."""

from kubeagent_verdict.evals.cli import _stratified

CASES = ["attributed", "empty_candidates", "injection", "misattribution_probe",
         "none_of_these", "own_cause", "positional_probe", "truncated",
         "wrong_attribution"]


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
    dropped = _dropped_cases(rows, _stratified(rows, 3))
    assert set(dropped) == set(CASES) - set(PROBES_FIRST)
    assert _dropped_cases(rows, _stratified(rows, len(CASES))) == []
