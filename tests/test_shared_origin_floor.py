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
"""
from collections import Counter

import pytest

from kubeagent_verdict.dataset import generate
from kubeagent_verdict.dataset import propagation as prop

SEED, SIZE = 17, 5500  # the runbook's build recipe
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
