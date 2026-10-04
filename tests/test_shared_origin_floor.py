"""Every trainable story keeps enough shared-origin pairs in TRAIN, and the
pile the model reads is balanced.

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

2026-10-03 (Spec 4b-1): the family is built from `stories.trainable()`, 41
stories (35 plain, then 6 ruled), and each workload's answer is a named
cause, a rules-decided cause or `none_of_these`. At size 8000 that is 1200
pairs before the split: 27 or 28 per plain story and 40 per ruled story.
The floor stays 12. Four checks join it, all on the same pile (Ruling 29):

- balance: the `none_of_these` share of verdicts in the broken half and in
  the healthy half differ by at most 10 points, so the world, not the
  case, tells the model when to answer `none_of_these`;
- ceiling: `none_of_these` is at most 30% of every verdict in train, so a
  model cannot score by saying it everywhere;
- the label cue: at least 5 plain stories end "shared" and at least 5 end
  "none" by majority of their broken rows, so the story does not give the
  label away;
- twins differ: no kept pair prints the same set of lines in both worlds.

If one of these misses, the fix is in the stories, never in the bar.
"""
import json
from collections import Counter

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import generate, stories

SEED, SIZE = 17, 8000  # the runbook's build recipe
FLOOR = 12
BALANCE = 0.10  # most the two worlds' none_of_these shares may differ
CEILING = 0.30  # most of all train verdicts that may be none_of_these
LABEL_CUE = 5  # fewest plain stories that must end each way

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"


@pytest.fixture(scope="module")
def train():
    rows = generate.generate(seed=SEED, size=SIZE)
    train, _val = generate.split(rows, seed=SEED)
    return generate.drop_held_out(train, generate.test_set())


def _per_origin(rows, case):
    return Counter(e.meta["origin"] for e in rows if e.case == case)


def _none_share(rows) -> tuple[int, int]:
    """(`none_of_these` verdicts, all verdicts) over `rows`."""
    verdicts = [v for e in rows for v in json.loads(e.assistant)["verdicts"]]
    return sum(v["cause"] == contract.NONE_OF_THESE for v in verdicts), len(verdicts)


def _majority(labels) -> str | None:
    """The label most rows carry. A tie counts for neither side."""
    top = Counter(labels).most_common()
    if not top or (len(top) > 1 and top[0][1] == top[1][1]):
        return None
    return top[0][0]


def _pairs(rows):
    """The kept twins, in order. The training loop appends each broken half
    and its healthy twin back to back, and `split` and `drop_held_out` move
    a whole group at once, so adjacent family rows are twins."""
    fam = [e for e in rows if e.case in (SHARED, DECOY)]
    assert len(fam) % 2 == 0, len(fam)
    out = list(zip(fam[::2], fam[1::2]))
    for a, b in out:
        assert (a.case, b.case) == (SHARED, DECOY), (a.case, b.case)
        assert a.group == b.group, (a.group, b.group)
    return out


def test_every_trainable_story_keeps_the_floor_in_train(train):
    keys = [st.key for st in stories.trainable()]
    shared = _per_origin(train, SHARED)
    decoy = _per_origin(train, DECOY)
    short = {k: (shared[k], decoy[k]) for k in keys
             if shared[k] < FLOOR or decoy[k] < FLOOR}
    assert short == {}, (
        f"stories below {FLOOR} probe/decoy rows in train "
        f"(shared, decoy): {short}")


def test_the_two_halves_survive_the_split_together(train):
    """The pair shares a group key, so the split can never take one half."""
    assert _per_origin(train, SHARED) == _per_origin(train, DECOY)


def test_three_verdict_decoys_are_common_and_span_the_node_stories(train):
    """The 0907 model wrote broken JSON on decoy halves with three verdicts.
    It had seen few: 80 of 397 kept decoy rows carried three or more, and
    every node-scoped one came from a single scenario. Two floors now: at
    least 40 of every 100 decoy rows carry three or more verdicts, and the
    node-scoped ones with three or more come from at least 5 stories.

    The generator cycles a pair's width over 2..len(victims), so a story
    with two victims can never render three. These floors hold only when
    nearly every story has a third victim. 2026-10-03: the radius comes
    from `Story.blast_radius`."""
    radius = {st.key: st.blast_radius for st in stories.trainable()}
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
        f"story(s): {sorted(node_keys)}")


def test_none_of_these_is_balanced_across_the_worlds(train):
    """If the healthy half said `none_of_these` far more often than the
    broken half, the case name would be the cue, not the workload's lines."""
    b_none, b_all = _none_share([e for e in train if e.case == SHARED])
    h_none, h_all = _none_share([e for e in train if e.case == DECOY])
    gap = abs(b_none / b_all - h_none / h_all)
    assert gap <= BALANCE, (
        f"broken {b_none}/{b_all}, healthy {h_none}/{h_all}, gap {gap:.3f}")


def test_none_of_these_stays_under_the_ceiling(train):
    """Every verdict of every case in train, not only the family's."""
    n, total = _none_share(train)
    assert n / total <= CEILING, (
        f"{n} of {total} train verdicts are none_of_these ({n / total:.3f})")


def test_the_story_does_not_give_the_label_away(train):
    """A plain story's label depends on what its victims print, so some
    stories must end "shared" and some "none" by majority."""
    plain = [st.key for st in stories.trainable() if st.cls == "P"]
    ends = Counter(
        _majority([e.meta["label"] for e in train
                   if e.case == SHARED and e.meta["origin"] == k])
        for k in plain)
    assert ends["shared"] >= LABEL_CUE and ends["none"] >= LABEL_CUE, dict(ends)


def test_kept_twins_print_different_lines(train):
    """Spec section 4, "Worlds differ": the two prompts differ in at least
    one printed line (Ruling 35)."""
    same = [a.group for a, b in _pairs(train)
            if set(a.user.splitlines()) == set(b.user.splitlines())]
    assert same == [], f"{len(same)} kept pairs print the same lines: {same[:10]}"
