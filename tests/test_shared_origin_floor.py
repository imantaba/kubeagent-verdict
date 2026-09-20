"""Every trainable scenario keeps enough shared-origin pairs in TRAIN.

The 0906 retrain built the data at the runbook's recipe (seed 17, size 5500)
with `shared_origin` at 4% of the mix. That gave each trainable scenario
about 9 pairs before the split. The validation split takes groups by hash,
not by count, so some scenarios lost 4 of their 9 pairs to validation and
reached the optimizer with 5. The model that came out of it learned "shared
by default" on the scenarios it saw least.

This test pins a floor at the build recipe itself, after the split and after
`drop_held_out`, because that is the pile the model reads. The floor is 12
rows of each half per scenario. A share that looks generous as emitted is
not the number that matters; the surviving count is.

On 2026-09-08 the recipe moved to size 8000, both halves to 12 percent, and
the pool to forty-eight scenarios. That is 960 rows per half, 20 pairs per
scenario before the split. The smallest scenario keeps 13 pairs in train
and the largest 20. The floor stays at 12: the extra room is the point,
because the split still takes groups by hash, not by count.

Re-measured 2026-09-19 (Task 9: pool merge to fifty-four scenarios and both
halves to 15 percent, spec section 6). That is 1200 rows per half before
the split, 20 pairs per plain scenario and 40 per ruled scenario -- the
selection loop gives ruled stories roughly twice the plain per-story rate
by design (spec section 7 ruling A), not evenly across all fifty-four. The
smallest scenario keeps 15 pairs in train (a plain story) and the largest
39 (a ruled story). The floor stays at 12: it was set once, against the
smallest surviving count, and every scenario -- plain or ruled -- still
clears it with room to spare.
"""
from collections import Counter

import pytest

from kubeagent_verdict.dataset import generate
from kubeagent_verdict.dataset import propagation as prop

SEED, SIZE = 17, 8000  # the runbook's build recipe
FLOOR = 12

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"


@pytest.fixture(scope="module")
def train():
    rows = generate.generate(seed=SEED, size=SIZE)
    train, _val = generate.split(rows, seed=SEED)
    return generate.drop_held_out(train, generate.test_set())


def _per_origin(rows, case):
    return Counter(e.meta["origin"] for e in rows if e.case == case)


def test_every_trainable_scenario_keeps_the_floor_in_train(train):
    keys = [p.key for p in prop.trainable_scenarios()]
    shared = _per_origin(train, SHARED)
    decoy = _per_origin(train, DECOY)
    short = {k: (shared[k], decoy[k]) for k in keys
             if shared[k] < FLOOR or decoy[k] < FLOOR}
    assert short == {}, (
        f"scenarios below {FLOOR} probe/decoy rows in train "
        f"(shared, decoy): {short}")


def test_the_two_halves_survive_the_split_together(train):
    """The pair shares a group key, so the split can never take one half."""
    assert _per_origin(train, SHARED) == _per_origin(train, DECOY)


def test_three_verdict_decoys_are_common_and_span_the_node_scenarios(train):
    """The 0907 model wrote broken JSON on decoy halves with three verdicts.
    It had seen few: 80 of 397 kept decoy rows carried three or more, and
    every node-scoped one came from a single scenario. Two floors now: at
    least 40 of every 100 decoy rows carry three or more verdicts, and the
    node-scoped ones with three or more come from at least 5 scenarios.

    The generator cycles a pair's width over 2..len(victims), so a scenario
    with two victims can never render three. These floors hold only when
    nearly every scenario has a third victim."""
    radius = {p.key: p.blast_radius for p in prop.trainable_scenarios()}
    decoys = [e for e in train if e.case == DECOY]
    wide = [e for e in decoys if len(e.meta["expected"]) >= 3]
    share = len(wide) / len(decoys)
    node_keys = {e.meta["origin"] for e in wide
                 if radius[e.meta["origin"]] == "node"}
    assert share >= 0.40, (
        f"{len(wide)} of {len(decoys)} decoy rows carry three or more "
        f"verdicts, share {share:.3f}")
    assert len(node_keys) >= 5, (
        f"node-scoped three-verdict decoys come from {len(node_keys)} "
        f"scenario(s): {sorted(node_keys)}")
