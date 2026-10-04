"""The curriculum's minimal contrast: the same story told both ways.

Every `shared_origin` row has a twin, `shared_origin_decoy`, drawn from the
same salt. The twin names the same victims and prints the same story. Only the
world differs. In the broken world the origin is broken. In the healthy world
it is not. The right answer flips with the world.

This is what the 0901 model got wrong. It answered the exam's ten twin pairs
the same way in both worlds on nine of them. Its verdict was a function of
which story it was looking at, not of what the reads said. The fix is to teach
every trainable story under BOTH answers, so nothing about the story predicts
the label. The read does, and only the read.

What this does not claim. It cannot make the model read. It removes a shortcut
that made not reading enough. Whether that shortcut was the cause is a question
for the paired score on the next run, not for this file.
"""

import json
import re

import pytest

from kubeagent_verdict.dataset import cases, generate, stories
from kubeagent_verdict.evals.score import INDEPENDENCE_PHRASES

SIZE = 800
SEED = 17

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")
_SEPARATE_HEAD = re.compile(r"^\d+ workloads are failing for separate reasons\.")


@pytest.fixture(scope="module")
def rows():
    return generate.generate(seed=SEED, size=SIZE)


@pytest.fixture(scope="module")
def kept(rows):
    train, val = generate.split(rows, seed=SEED)
    test = generate.test_set()
    return generate.drop_held_out(train, test) + generate.drop_held_out(val, test)


def _by_case(rows, case):
    return [e for e in rows if e.case == case]


def _victim_keys(example) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in example.group.split("+")}


def _summary(example) -> str:
    return json.loads(example.assistant)["summary"]


def _pairs(rows):
    """Twin rows, matched by emission order and checked by group.

    The emitter writes each pair as two consecutive rows from one salt, so the
    n-th `shared_origin` row and the n-th `shared_origin_decoy` row are twins.
    The group check is what makes that sound: twins carry one group string, and
    it names the story and its victims. The workload sets are not compared. The
    broken world can add an origin row that the healthy world lacks.
    """
    shared = _by_case(rows, SHARED)
    decoy = _by_case(rows, DECOY)
    assert shared, "no shared_origin rows"
    assert len(shared) == len(decoy), "a row has no twin"
    for a, b in zip(shared, decoy):
        assert a.group == b.group, "rows out of step: not twins"
        assert a.meta["origin"] == b.meta["origin"], "twins name different stories"
    return list(zip(shared, decoy))


# ------------------------------------------------------- the mix pairs it up

def test_the_case_mix_names_the_decoy_and_still_sums_to_one_hundred():
    mix = dict(generate.CASE_MIX)
    assert DECOY in mix
    assert sum(pct for _case, pct in generate.CASE_MIX) == 100


def test_the_two_halves_get_the_same_share():
    """A partial pairing reintroduces exactly what the pairing removes.

    If one half is rarer, its scenarios are the ones that appear under a
    single answer, and scenario identity predicts the label again for them.
    """
    mix = dict(generate.CASE_MIX)
    assert mix[DECOY] == mix[SHARED]


def test_the_decoy_is_not_a_held_out_case():
    """`held_out_case_set` mints eval rows from TRAINING scenarios.

    Listing this one would put a trainable origin into the exam — the leak the
    split exists to prevent, arriving by the other door.
    """
    assert DECOY not in generate.HELD_OUT_CASES


# --------------------------------------------------------- every row is a pair

def test_the_generator_emits_the_halves_in_equal_number(rows):
    assert _by_case(rows, SHARED), "no shared_origin rows"
    assert len(_by_case(rows, DECOY)) == len(_by_case(rows, SHARED))


def test_the_optimizer_never_reads_a_one_sided_pair(kept):
    """`drop_held_out` must take a pair whole or leave it whole.

    Both halves carry the same group, so the filter cannot split one. If that
    ever changes, the surviving halves are a one-sided curriculum again.
    """
    assert _by_case(kept, SHARED), "the filter took every shared_origin row"
    assert len(_by_case(kept, DECOY)) == len(_by_case(kept, SHARED))


def test_every_trainable_story_is_taught_under_both_answers(rows):
    """The claim the whole change rests on: the story does not predict the label."""
    shared = {e.meta["origin"] for e in _by_case(rows, SHARED)}
    decoy = {e.meta["origin"] for e in _by_case(rows, DECOY)}
    assert shared == decoy
    assert shared == {st.key for st in stories.trainable()}


# ------------------------------------------- only the world differs, and it does

def test_a_pair_shows_the_same_victims(rows):
    for shared, decoy in _pairs(rows):
        victims = _victim_keys(shared)
        assert victims == _victim_keys(decoy)
        assert victims <= set(shared.meta["expected"]), shared.group
        assert victims <= set(decoy.meta["expected"]), shared.group


def test_a_pair_does_not_read_the_same_things(rows):
    for shared, decoy in _pairs(rows):
        assert set(shared.user.splitlines()) != set(decoy.user.splitlines()), shared.group


def test_the_answer_flips_with_the_read(rows):
    """The decoy is always `none` and never claims sharing. The broken half
    claims sharing exactly when its label is `shared`, and then its answer
    differs from the decoy's on at least one workload both halves flag."""
    flipped = 0
    for shared, decoy in _pairs(rows):
        decoy_head = _summary(decoy).split("\n")[0]
        assert decoy.meta["label"] == "none", decoy.group
        assert not _SHARED_HEAD.match(decoy_head), decoy.group
        shared_head = _summary(shared).split("\n")[0]
        claims = bool(_SHARED_HEAD.match(shared_head))
        assert claims == (shared.meta["label"] == "shared"), shared.group
        if shared.meta["label"] != "shared":
            continue
        common = set(shared.meta["expected"]) & set(decoy.meta["expected"])
        assert any(shared.meta["expected"][w] != decoy.meta["expected"][w]
                   for w in common), shared.group
        assert _summary(shared) != _summary(decoy), shared.group
        flipped += 1
    assert flipped > 0


def test_no_none_labelled_training_cause_speaks_the_language_of_a_shared_claim(kept):
    """A `none` row's verdicts may not use the words that assert sharing.

    The decoy half teaches "these have SEPARATE causes" by naming each
    workload's own. If one of those causes is worded with a shared-claim
    phrase, the row teaches the grader's positive signal as part of a negative
    answer. job3 reads the summary, which carries the per-workload lines, so it
    would score a correct answer as a shared claim.

    This reads the rendered verdict causes of every kept family row whose
    label is `none`. A `shared` row is exempt, because its summary makes the
    claim on purpose. The per-story version of this check (all 47 stories, both
    worlds, origin rows included) is in tests/test_shared_origin_decided.py.
    """
    checked = 0
    offenders = []
    for e in kept:
        if e.case not in (SHARED, DECOY) or e.meta["label"] != "none":
            continue
        for v in json.loads(e.assistant)["verdicts"]:
            checked += 1
            low = v["cause"].lower()
            offenders += [(e.meta["origin"], e.case, p, v["cause"])
                          for p in cases.SHARED_CLAIM_PHRASES if p in low]
    assert checked > 0
    assert offenders == [], (
        "a none-labelled training cause carries shared-claim language: "
        + "; ".join(f"{o} ({c}) says {p!r} in {t!r}" for o, c, p, t in offenders[:5]))


def _denying_rows(kept):
    """Training rows whose rendered answer denies a shared origin."""
    out = []
    for e in kept:
        summary = str(json.loads(e.assistant).get("summary", "")).lower()
        if any(p in summary for p in INDEPENDENCE_PHRASES):
            out.append((e, summary))
    return out


# 2026-10-04 (Spec 4b-1): the shared-origin rows were rebuilt on real lines; was every
# decoy row, because the old decoy summary always said "separate reasons".
DENYING_ROWS = 67


def test_no_trainable_answer_both_denies_sharing_and_speaks_its_language(kept):
    """A summary that both claims sharing and denies it scores 0 on every label.

    The old guard said every decoy row denies. That is no longer true. A
    healthy world says "failing for separate reasons" only when every row has
    its own, different cause. Otherwise it says the rules did not confirm one
    cause, and that header is not a denial. So the guard is now an equality:
    the family rows that deny are exactly the family rows whose header says
    "separate reasons". An equality cannot be lowered to make a red test
    green. It can only be deleted.
    """
    denying = _denying_rows(kept)
    family_denying = {id(e) for e, _ in denying if e.case in (SHARED, DECOY)}
    earned = {id(e) for e in kept
              if e.case in (SHARED, DECOY) and _SEPARATE_HEAD.match(_summary(e))}
    # A denominator, asserted rather than assumed. An empty set would make the
    # equality pass while measuring nothing.
    assert earned, "no kept family row earned the 'separate reasons' header"
    assert family_denying == earned, (
        f"{len(family_denying)} family rows deny, {len(earned)} earn the header")
    assert len(earned) == DENYING_ROWS

    offenders = [
        (e.case, e.group, [p for p in cases.SHARED_CLAIM_PHRASES if p in summary], summary)
        for e, summary in denying
        if any(p in summary for p in cases.SHARED_CLAIM_PHRASES)
    ]
    assert offenders == [], (
        f"{len(offenders)} of {len(denying)} denying answers also speak "
        "shared-claim language, so the grader reads them as ambiguous: "
        + "; ".join(f"{c} ({g}) says {p}" for c, g, p, _ in offenders[:5]))
