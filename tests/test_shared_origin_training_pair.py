"""The curriculum's minimal contrast: the same scenario told both ways.

`tests/test_shared_origin_training.py` closed the first shortcut. `multi` rows
carry a cluster-scoped origin read showing the component healthy, so "an origin
read is present" stopped separating the two classes in the curriculum, and its
own docstring named the residual it could not close.

This is the residual, and the measurement that found it. The 0901 model was
trained on that curriculum and answered the exam's ten minimal-contrast pairs
*identically in both worlds on nine of them* -- including one where the decoy
prompt states the node Ready and it still answered "2 workloads share one
upstream cause: node worker-2 is NotReady". Its verdict was a function of which
scenario it was looking at, not of what the reads said. It scored 0.1 paired
against a 0.7 bar.

The reason is visible in the curriculum rather than in the model. A
`shared_origin` row renders the scenario's OWN victims, whose local symptoms
cohere with the origin. Its counter-example, a `multi` row with a healthy
origin read, renders `rng.sample(entries)` -- arbitrary catalog entries whose
symptoms have nothing to do with the read. So the two classes differed in the
victims as well as in the read, and "do these symptoms look like they share a
cause" separates them without reading the origin at all. It is a better
shortcut than the label was, and the healthy-read counter-example does not
touch it.

`shared_origin_decoy` closes it the way the exam's pair did. It is
`shared_origin` rendered from the same salt with the origin reading healthy:
identical workloads, identical candidate menus with identical tags in identical
order, identical read labels in identical order. Only the read contents differ,
and the correct answer flips with them. Every trainable scenario is now
presented under BOTH answers, so nothing about the scenario -- its origin key,
its victims, their symptoms, the menu, the labels -- predicts the label. The
read does, and only the read.

What this does not claim. It cannot make the model read; it removes a shortcut
that made not reading sufficient. Whether the shortcut was the cause is a
question for the paired score on the next run, not for this file.
"""

import json

import pytest

from kubeagent_verdict.dataset import generate, propagation

SIZE = 800
SEED = 17

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"


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


def _workloads(example):
    return tuple(sorted(example.meta["expected"]))


def _pairs(rows):
    """Twin rows, matched on the workload set they share.

    Sound for the same reason the scorer's pairing is: the halves are rendered
    from one salt so they name the same workloads, and separate pairs draw
    separate salts so no two pairs collide. Asserted below rather than assumed.
    """
    shared = {_workloads(e): e for e in _by_case(rows, SHARED)}
    decoy = {_workloads(e): e for e in _by_case(rows, DECOY)}
    assert len(shared) == len(_by_case(rows, SHARED)), "workload sets collide"
    assert len(decoy) == len(_by_case(rows, DECOY)), "workload sets collide"
    assert set(shared) == set(decoy), "a row has no twin"
    return [(shared[k], decoy[k]) for k in shared]


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


def test_every_trainable_scenario_is_taught_under_both_answers(rows):
    """The claim the whole change rests on: origin does not predict the label."""
    shared = {e.meta["origin"] for e in _by_case(rows, SHARED)}
    decoy = {e.meta["origin"] for e in _by_case(rows, DECOY)}
    assert shared == decoy
    assert shared == {p.key for p in propagation.trainable_scenarios()}


# ------------------------------------------- only the reads differ, and do

def test_a_pair_shows_the_same_workloads_with_the_same_menus(rows):
    for shared, decoy in _pairs(rows):
        assert _workloads(shared) == _workloads(decoy)
        assert _menu(shared.user) == _menu(decoy.user)


def test_a_pair_reads_the_same_things_in_the_same_order(rows):
    for shared, decoy in _pairs(rows):
        assert _read_labels(shared.user) == _read_labels(decoy.user)


def test_a_pair_does_not_read_the_same_things(rows):
    """Non-vacuity: identical labels over identical menus must still differ."""
    for shared, decoy in _pairs(rows):
        assert shared.user != decoy.user


def test_the_answer_flips_with_the_read(rows):
    for shared, decoy in _pairs(rows):
        one = json.loads(shared.assistant)
        sep = json.loads(decoy.assistant)
        assert propagation.SEPARATE_REASONS not in one["summary"]
        assert propagation.SEPARATE_REASONS in sep["summary"]
        # One cause for every workload on the shared half; each workload's own
        # local cause on the decoy half. Same workloads, different answers.
        causes = {v["cause"] for v in one["verdicts"]}
        assert len(causes) == 1
        assert shared.meta["expected"] != decoy.meta["expected"]


def test_the_decoy_half_shows_the_component_healthy(rows):
    """The read that carries the whole label, on the half that denies it."""
    for _shared, decoy in _pairs(rows):
        assert "BROKEN" not in decoy.user


# The menu and the read labels are what a shortcut would key on, so the pair is
# only a minimal contrast if these are identical across it.
def _menu(user: str) -> list[str]:
    return [ln.strip() for ln in user.splitlines()
            if ln.strip().startswith(("- attributed", "- ruled_out", "- outranked"))]


def _read_labels(user: str) -> list[str]:
    return [ln.strip() for ln in user.splitlines()
            if ln.strip().startswith("== ") and ln.strip().endswith(" ==")
            and not ln.strip().startswith(("== BEGIN", "== END"))]


def test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim():
    """A victim's own cause may not use the words that assert sharing.

    The decoy half teaches "these have SEPARATE causes" by naming each
    workload's own. If one of those causes is worded with a shared-claim
    phrase, the row teaches the grader's positive signal as part of a
    negative answer -- and `evals.score._shared_verdict` reads the summary,
    which carries the per-workload lines, so it would score a correct answer
    as a shared claim.

    This is not the grader being crude. `kube-proxy-degraded`'s shared cause
    IS that pods on the node reach no Service, so a victim whose "separate"
    cause said the upstream refuses connections was restating the shared
    story rather than contrasting with it -- the row's own teaching point,
    lost. That scenario has exactly two victims, so `p.victims[:count]`
    always drew it: every one of its decoy rows carried the collision.

    Scoped to the TRAINING scenarios on purpose. The exam's six origins are
    frozen and this test must never be the reason their bytes move; the
    eval-side collision that remains -- a distractor a model can only reach
    by being wrong -- is recorded in the runbook, not fixed here.
    """
    from kubeagent_verdict.dataset.cases import SHARED_CLAIM_PHRASES

    offenders = [
        (s.key, i, p, v.local_cause)
        for s in propagation._TRAINING_SCENARIOS
        for i, v in enumerate(s.victims)
        for p in SHARED_CLAIM_PHRASES
        if p in v.local_cause.lower()
    ]
    assert offenders == [], (
        "a trainable victim's local cause carries shared-claim language: "
        + "; ".join(f"{k} victim[{i}] says {p!r} in {c!r}" for k, i, p, c in offenders))
