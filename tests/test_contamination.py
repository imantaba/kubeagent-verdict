"""The contamination lock.

The shipped v0.1.0 weights were trained at 8bd9d28, where 33 of 253 test
rows shared a workload identity with training data -- concentrated in
multi_misattribution_probe (19/19) and contradiction_probe (14/19), which
is what forced both slices to be withdrawn in docs/model-card.md.

Commit baf173e fixed the cause: drop_held_out splits compound group keys
on "+" on BOTH sides. Nothing recomputed the intersection afterwards, so a
regression would have shipped green -- which is how the original leak
shipped. This is that recomputation.

The split-on-both-sides rule is not incidental. Reading either side unsplit
re-derives the blind spot baf173e fixed; the comment in
tests/test_generate.py above `held = {part for ex in test ...}` records that
mistake letting a test assert the buggy rule against itself and pass while
103 train rows leaked.
"""

import collections

from kubeagent_verdict.dataset import generate

# The release configuration, from docs/runbooks/train.md. Contamination is a
# function of seed and size, so a number measured at any other configuration
# says nothing about what ships.
SEED, SIZE = 17, 5500


def _parts(examples: list) -> set[str]:
    """Every group key, split on "+" -- drop_held_out's own unit."""
    return {part for ex in examples for part in ex.group.split("+")}


def _build() -> tuple[list, list, list]:
    exs = generate.generate(seed=SEED, size=SIZE)
    train, val = generate.split(exs, seed=SEED)
    return train, val, generate.test_set()


def test_no_test_row_shares_an_identity_with_training_data():
    """Per slice, not a single total -- a total hides which slice regressed."""
    train, val, test = _build()
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    trained = _parts(kept)
    tainted = collections.Counter(
        ex.case for ex in test
        if any(part in trained for part in ex.group.split("+")))
    assert dict(tainted) == {}


def test_the_filter_is_actually_doing_work():
    """Non-vacuity.

    Without this the lock above passes the moment generate() stops producing
    collisions for an unrelated reason, and a vacuous green is the exact
    failure mode this slice exists to prevent.

    Asserted as `> 0`, never as the measured 913: that figure is a function
    of seed and size, and pinning it would fail the test on an innocent
    curriculum change while proving nothing extra.
    """
    train, val, test = _build()
    held = _parts(test)
    before = sum(1 for ex in train + val
                 if any(part in held for part in ex.group.split("+")))
    assert before > 0, (
        "no train/val row collides with a test identity before filtering, so "
        "the contamination lock above cannot fail and proves nothing")
