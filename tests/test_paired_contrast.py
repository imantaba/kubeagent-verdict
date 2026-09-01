"""The paired shared-origin decider: does the answer CHANGE with the evidence?

`shared_origin_probe` and `shared_origin_decoy_probe` are one exam question
asked twice. The two rows draw the same names from the same salt, so the pair
is a minimal contrast: identical inventory, identical candidate menus,
identical evidence labels in identical order, and a menu whose tags are
byte-identical across the pair. Only what the reads SAY differs -- and the
correct answer flips with it, shared on the probe and separate on the decoy.

Read one at a time, the two slices are each gameable by an answering habit,
and `docs/runbooks/train.md` decider 5 reads them one at a time:
`separate_reasons_rate` on the probe, `false_shared_rate` on the decoy. A
model that answers "separate reasons" everywhere aces the decoy and fails the
probe; one that answers "shared origin" everywhere does the reverse. Decider 5
catches both -- but only by reading two numbers together and knowing that a
good score on either alone is worthless.

This is the same judgement as one number. A pair scores 1.0 only when the
probe half says shared AND its decoy twin says separate, so every habit that
answers a pair the same way twice scores 0.0 on that pair no matter which
answer it picks. There is no third answer to try: the menu offers the same
three tags in the same order on both halves.

Why it earns a place beside the two rates rather than replacing them. The
0901 model scored `separate_reasons_rate` 0.5 and `false_shared_rate` 0.4 --
two middling numbers that read as partial skill, and that cleared decider 5's
pre-registered bar in its letter. Paired, the same answers score 0.1: nine of
its ten pairs answered both worlds identically, so the verdict was a function
of which scenario it was looking at rather than of what the reads said. The
marginals could not see that, because a per-scenario constant landing right
half the time is indistinguishable from half-skill until the halves are
joined.

The two habits below are not caricatures. Each fake answer is the TWIN row's
own assistant message, verbatim -- the same salt means the same workload
names, so it is exactly what a model that had learned the wrong rule would
emit. `test_the_0830_answering_habit_scores_zero` is the specific one: that
model answered independence on all ten probe rows, which scores 1.0 on
`separate_reasons_rate` and a clean 0.0 on `false_shared_rate`, the second of
which reads as the best number on the board.
"""

import json

import pytest

from kubeagent_verdict.dataset import cases, generate
from kubeagent_verdict.evals import score

PROBE = "shared_origin_probe"
DECOY = "shared_origin_decoy_probe"


@pytest.fixture(scope="module")
def exam():
    return generate.test_set()


@pytest.fixture(scope="module")
def probes(exam):
    rows = [e for e in exam if e.case == PROBE]
    assert rows, f"{PROBE} is not in the exam"
    return rows


@pytest.fixture(scope="module")
def decoys(exam):
    rows = [e for e in exam if e.case == DECOY]
    assert rows, f"{DECOY} is not in the exam"
    return rows


def _score(examples, answer):
    """Run `evaluate` over `examples`, answering each prompt with `answer`."""
    results = score.evaluate([generate.to_row(e) for e in examples],
                             lambda m: answer[m[1]["content"]])
    return score.paired_contrast(results)


# --------------------------------------------------- the constant is pinned

def test_the_shared_claim_phrases_match_the_generator():
    """score.py may not import dataset, so the list is duplicated.

    `INDEPENDENCE_PHRASES` lives in score.py because it is a fixed property of
    the correct answer rather than of a row. The shared side is the same kind
    of thing -- one tuple in `cases.py`, emitted verbatim into every row that
    carries it -- but it reached the scorer through row meta, which the paired
    decider cannot use: the probe half carries no `shared_claim_phrases` key,
    only the decoy half does. Duplicating it is what lets both halves be read
    by the same three-way gate. This test is the cost of the duplication: it
    fails the suite the moment the two drift.
    """
    assert score.SHARED_CLAIM_PHRASES == cases.SHARED_CLAIM_PHRASES


# ------------------------------------------------- no habit passes the pair

def test_a_reader_scores_every_pair(probes, decoys):
    """Non-vacuity: the assertions below are about the ANSWER, not the shape."""
    own = {e.user: e.assistant for e in list(probes) + list(decoys)}
    board = _score(list(probes) + list(decoys), own)
    assert board["both_correct"] == {"rate": 1.0, "n": len(probes)}
    assert board["disagreement"] == {"rate": 1.0, "n": len(probes)}
    assert board["ambiguous"] == 0


def test_the_0830_answering_habit_scores_zero(probes, decoys):
    """Answer independence everywhere -- the model this decider was built for.

    On the two rates it reads 1.0 `separate_reasons_rate` and 0.0
    `false_shared_rate`. Paired, it scores nothing: it gave both halves of
    every pair the same answer.
    """
    always_separate = {p.user: d.assistant for p, d in zip(probes, decoys)}
    always_separate.update({d.user: d.assistant for d in decoys})
    board = _score(list(probes) + list(decoys), always_separate)
    assert board["both_correct"] == {"rate": 0.0, "n": len(probes)}
    assert board["disagreement"] == {"rate": 0.0, "n": len(probes)}


def test_the_opposite_answering_habit_also_scores_zero(probes, decoys):
    """Answer a shared origin everywhere -- the failure a correction invites."""
    always_shared = {p.user: p.assistant for p in probes}
    always_shared.update({d.user: p.assistant for d, p in zip(decoys, probes)})
    board = _score(list(probes) + list(decoys), always_shared)
    assert board["both_correct"] == {"rate": 0.0, "n": len(probes)}
    assert board["disagreement"] == {"rate": 0.0, "n": len(probes)}


def test_answering_both_halves_backwards_disagrees_but_scores_zero(probes, decoys):
    """Disagreement is not credit; it is the diagnostic beside the score.

    This model flips its answer with the evidence -- and gets the direction
    exactly wrong on every pair. `disagreement` reads 1.0 and `both_correct`
    reads 0.0, which is why the two are reported together: disagreement alone
    would call this model a reader.
    """
    inverted = {p.user: d.assistant for p, d in zip(probes, decoys)}
    inverted.update({d.user: p.assistant for d, p in zip(decoys, probes)})
    board = _score(list(probes) + list(decoys), inverted)
    assert board["both_correct"] == {"rate": 0.0, "n": len(probes)}
    assert board["disagreement"] == {"rate": 1.0, "n": len(probes)}


# ------------------------------------- what is not measured is not a number

def test_a_probe_only_run_reads_na_rather_than_a_number(probes):
    """The frozen 253-row exam carries the probe half and no decoy half.

    Scoring it must not produce a paired number from ten half-pairs. A rate
    always travels with its denominator, and nothing was measured here.
    """
    own = {e.user: e.assistant for e in probes}
    board = _score(list(probes), own)
    assert board["both_correct"] == {"rate": None, "n": 0}
    assert board["disagreement"] == {"rate": None, "n": 0}
    assert board["unpaired"] == len(probes)


def test_a_summary_that_says_neither_is_excluded_not_counted_right(probes, decoys):
    """A pair the gate cannot read is n/a, never a pass.

    A one-sided substring test would score this model 1.0 on the probe half:
    it never says "separate reasons" there. The three-way gate refuses to call
    an answer that claims nothing a claim.
    """
    def mute(example):
        doc = json.loads(example.assistant)
        doc["summary"] = "The cluster has several unhealthy workloads."
        return json.dumps(doc)

    answer = {e.user: mute(e) for e in list(probes) + list(decoys)}
    board = _score(list(probes) + list(decoys), answer)
    assert board["both_correct"] == {"rate": None, "n": 0}
    assert board["ambiguous"] == len(probes)


# ----------------------------------------------------- wired into the board

def test_the_scoreboard_carries_the_paired_block(probes, decoys):
    own = {e.user: e.assistant for e in list(probes) + list(decoys)}
    results = score.evaluate(
        [generate.to_row(e) for e in list(probes) + list(decoys)],
        lambda m: own[m[1]["content"]])
    board = score.scoreboard(results)
    assert board["paired_shared_origin"]["both_correct"]["rate"] == 1.0
    assert "paired shared-origin" in score.render_markdown(board).lower()
