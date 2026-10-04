"""The counter-example half of the shared-origin exam.

A shared-origin pair is one story told in two worlds. In `shared_origin_probe`
the origin is broken. In `shared_origin_decoy_probe` the same story is told
with the origin healthy. The two rows draw the same names from the same seed,
so they are a minimal contrast: the same victims, the same story. What the
reads say about the origin is what differs.

The right answer flips with the read. In the broken world the rules may
confirm one cause on two or more workloads, and the summary says so. In the
healthy world the rules confirm nothing, so each workload answers with its own
cause, or with `none_of_these` when its own lines do not show why.

These tests check three things.

* The pair is a real contrast: one group, the same victims, different lines.
* The decoy's right answer makes no shared claim.
* The scorer has teeth. A model that copies the twin's answer fails job 3 on
  every pair whose probe is labelled `shared`. A model that reads the
  evidence passes everything.

What this slice does not do. A model that always answers "separate reasons"
would pass these rows. The pair catches it, because the probe half expects a
shared claim. This file is the second half of a pair, not a fix on its own.
"""

import json
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, generate, stories
from kubeagent_verdict.evals import score

CASE = "shared_origin_decoy_probe"

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")


@pytest.fixture(scope="module")
def exam():
    return generate.test_set()


@pytest.fixture(scope="module")
def decoys(exam):
    rows = [e for e in exam if e.case == CASE]
    # Without this, every loop below passes over an empty list and the slice
    # could be unwired from `probe_sets` with a green suite.
    assert rows, f"{CASE} is not in the exam"
    return rows


@pytest.fixture(scope="module")
def probes(exam):
    return [e for e in exam if e.case == "shared_origin_probe"]


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def _template_pattern(template: str):
    """A regex for a story's cause template, each `{name}` slot matching any text."""
    return re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(template)))


def _twin_reply(decoy, probe) -> str:
    """The probe's own answer, cut down to the decoy's workloads.

    The broken world can flag an origin row that the healthy world does not
    (Ruling 36). A model that copied the probe's answer would also name that
    row, which the decoy does not ask about. Cutting the reply to the
    decoy's workloads keeps the contract check about the answer's content.
    """
    flagged = set(decoy.meta["expected"])
    doc = json.loads(probe.assistant)
    return json.dumps({"verdicts": [v for v in doc["verdicts"] if v["workload"] in flagged],
                       "summary": doc["summary"]}, ensure_ascii=False)


# --------------------------------------------------------------- the slice

def test_the_slice_mirrors_the_probe_row_for_row(decoys, probes):
    """Same stories, same widths, same order: one counter-example each."""
    want = ([st.key for st in stories.exam()]
            + [st.key for st in stories.exam() if len(st.victims) >= 3])
    assert len(decoys) == len(probes) == len(want) == 10
    assert [e.meta["origin"] for e in decoys] == want
    assert [e.meta["origin"] for e in probes] == want


def test_the_pair_shows_the_same_victims_and_the_lines_differ(decoys, probes):
    """The claim that makes the pair a contrast rather than two questions.

    The twins share a group, so they name the same victims. Their printed
    lines must differ, or the pair asks nothing and a model cannot tell the
    two worlds apart by reading.
    """
    for d, p in zip(decoys, probes):
        assert d.group == p.group, d.meta["origin"]
        victims = _victim_keys(d)
        assert victims <= set(d.meta["expected"]), d.meta["origin"]
        assert victims <= set(p.meta["expected"]), d.meta["origin"]
        assert set(d.user.splitlines()) != set(p.user.splitlines()), d.meta["origin"]


def test_the_correct_answer_is_each_workload_s_own_cause(decoys):
    """No named cause repeats inside a row, and none is the story's shared cause.

    `none_of_these` may repeat: it is an answer, not a cause. At least one
    decoy must name two or more causes, or the test above proves nothing about
    distinctness.
    """
    patterns = {st.key: _template_pattern(st.shown_cause) for st in stories.exam()}
    multi = 0
    for e in decoys:
        named = [c for c in e.meta["expected"].values() if c != contract.NONE_OF_THESE]
        assert len(named) == len(set(named)), e.group
        for cause in named:
            assert not patterns[e.meta["origin"]].fullmatch(cause), (e.group, cause)
        if len(named) >= 2:
            multi += 1
    assert multi > 0


def test_the_summary_makes_no_shared_claim(decoys):
    for e in decoys:
        summary = json.loads(e.assistant)["summary"]
        assert e.meta["label"] == "none", e.group
        assert not _SHARED_HEAD.match(summary), e.group
        assert score.job3("none", summary) == 1.0, e.group
        low = summary.lower()
        for ph in cases.SHARED_CLAIM_PHRASES:
            assert ph not in low, (e.group, ph)


def test_the_slice_sets_no_row_level_decoy(decoys):
    """Ruling 8: `decoy_causes` is `[]`. A story has no scripted wrong cause
    any more. What the scorer watches is `decoy_by_workload`, the causes the
    rules ruled out or refuted for that workload."""
    for e in decoys:
        assert e.meta["decoy_causes"] == [], e.group
        assert set(e.meta["decoy_by_workload"]) <= set(e.meta["expected"]), e.group


def test_the_slice_carries_shared_claim_phrases_and_no_wrong_summary_phrase(decoys):
    for e in decoys:
        assert e.meta["shared_claim_phrases"] == list(cases.SHARED_CLAIM_PHRASES), e.group
        for gone in ("wrong_summary_phrase", "origin_read_label",
                     "distractor_cause", "expected_confidence"):
            assert gone not in e.meta, (e.group, gone)


# ------------------------------------------------------------ the teeth

def test_a_model_that_copies_the_twin_s_answer_fails_this_slice(decoys, probes):
    """The failure mode a shared-origin correction can plausibly introduce.

    The fake answer is the TWIN row's own assistant message, cut down to the
    decoy's workloads. Same salt means same victim names, so the twin's answer
    is exactly what a model that had learned "a story with an origin means one
    shared cause" would emit here.

    job3 grades the summary against THIS row's own `none` label. So it tracks
    what the twin's summary claims, not which story it is. A `shared`-labelled
    twin writes "N workloads share one upstream cause", which is false here, so
    job3 reads 0.0. A `none`-labelled twin already writes the honest "rules did
    not confirm one cause" header, so job3 reads 1.0. Both kinds must occur, or
    the test would only prove one of them.
    """
    reply = {d.user: _twin_reply(d, t) for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: reply[m[1]["content"]])
    seen = set()
    for d, t, r in zip(decoys, probes, results):
        assert r["contract_ok"], (d.group, r["contract_reasons"])
        want = 0.0 if t.meta["label"] == "shared" else 1.0
        assert r["job3"] == want, d.group
        seen.add(t.meta["label"])
    assert seen == {"shared", "none"}


def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape.

    The fake answer is each decoy row's own gold. It must pass the contract and
    score full marks on cause, confidence and job 3, and it must never name a
    decoy cause. (`named_decoy` is None where no job-2 workload has a listed
    decoy, and False where one does and the reply avoids it.)
    """
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]], grade_job2=True)
    for e, r in zip(decoys, results):
        assert r["contract_ok"], (e.group, r["contract_reasons"])
        assert r["cause_acc"] == 1.0, e.group
        assert r["conf_acc"] == 1.0, e.group
        assert r["job3"] == 1.0, e.group
        assert r["named_decoy"] in (False, None), e.group


# ------------------------------------------- the training set must not move

def test_the_slice_drops_no_training_row():
    """Groups are `propagation:<eval key>:...`, which no training row can hold.

    The whole point of appending rather than editing: `drop_held_out` removes
    a train/val row whose group collides with an exam group, so an exam slice
    built from training-reachable groups would silently shrink the curriculum
    and make this change incomparable with the run it is measured against.
    """
    examples = generate.generate(seed=17, size=800)
    train, val = generate.split(examples, seed=17)
    full = generate.test_set()
    without = [e for e in full if e.case != CASE]
    for pile in (train, val):
        assert [generate.to_row(e) for e in generate.drop_held_out(pile, full)] == \
               [generate.to_row(e) for e in generate.drop_held_out(pile, without)]
