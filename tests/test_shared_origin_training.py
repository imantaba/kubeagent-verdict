"""Teaching shared-origin reasoning without teaching the test.

This file guards the rows the model trains on. It asks two questions. Does
training leak the exam? And does the training pile hand the model a cue, so
it can score without reading the evidence?

How it began (kept as history)
------------------------------

`propagation.py` shipped its six scenarios as EVAL-ONLY and said why: the
measurement had to exist and had to fail before any attempt was made to teach
the correction. It has now failed — on all ten `shared_origin_probe` rows the
0830 model answered "N workloads are failing for separate reasons" and picked
a different local decoy for every workload. The same docstring named the
condition a correction has to meet:

    once these scenarios are ever trained on, a pass stops meaning that, and
    the slice needs held-out origins the way `contradiction_probe` needed
    held-out entries.

So training gets its OWN origins and the six eval scenarios stay eval-only —
the catalog's 19-trainable / 9-held-out split, applied to propagation. The
eval set does not move, which is what keeps the 0830 scoreboard comparable.

Until 2026-10-05 (Spec 4b-3) the next three paragraphs described live
code. They are history now: `multi` has no healthy-origin read and no
counterweight case.

That closes the obvious shortcut. This module was written mostly for the
second, which is not obvious: `multi` builds its reads per constituent
(`_reads(e, n)[:2]`), so a cluster-scoped read at the head of the list used to
appear in shared-origin rows and NOWHERE else. Train the positive case alone
and "an origin read is present" separates the two classes perfectly — the
model would pass the probe on the prompt's shape without reading a word of the
evidence, and every rate on the slice would improve for a reason that is not
the skill. The counterweight was a negative case: `multi` rows carrying the
SAME origin read label with content showing the component HEALTHY, where
"separate reasons" is still the right answer. Same shape, both answers, so
only the evidence separates them.

Two residuals were asserted rather than claimed away. The counterweight was
lighter than the generator made it look: `drop_held_out` removes about a
third of the `multi` counter-examples and none of the `shared_origin` rows,
so the emitted ~48/52 reached the optimizer as ~62/38 (the band is now held
by `test_the_trained_pile_is_not_one_sided_among_origin_read_rows`). And the
exam could not detect this shortcut even then — seven of the ten
`shared_origin_probe` rows carried a read label that appeared in none of the
other 243, so label-matching alone cleared job 3 and the decoy rate. The
second residual is gone: the family has no read label now (see below).

What changed on 2026-10-04 (Spec 4b-1)
--------------------------------------

The shared-origin family is rebuilt from `stories.py`: real lines, run
through kubeagent's own pipeline. Three things follow for this file.

1. The family's training pool is the 41 stories in `stories.trainable()`.
   The 54 made-up scenarios in `propagation.py` are no longer its pool.
2. The made-up candidate menu, the 12 X stories and the invented origin read
   are gone from the family. So are the tests that checked them: the origin
   variants, their states, their exam layouts, the read-layout floors and
   cousins, and `origin_read_label` on this family.
3. A family row's meta no longer carries `origin_read_label`,
   `distractor_cause`, `wrong_summary_phrase` or `expected_confidence`.
   `test_no_family_row_meta_carries_a_dropped_key` checks that on the train
   pile, the exam, the wide probes and the cousin probes.

2026-10-05 (Spec 4b-3): `multi` no longer shows a healthy-origin read.
kubeagent's gather never makes that read, so no case carries
`origin_read_label` now. The family's side of the shortcut is checked in
`tests/test_shared_origin_floor.py` and `tests/test_shared_origin_pool.py`.
"""

import dataclasses
import hashlib
import json
import re
from collections import Counter

import pytest

from kubeagent_verdict import contract, vocab
from kubeagent_verdict.dataset import generate, gold, propagation, stories

SIZE = 800
SEED = 17


@pytest.fixture(scope="module")
def rows():
    return generate.generate(seed=SEED, size=SIZE)


@pytest.fixture(scope="module")
def kept(rows):
    """What the model actually reads: train+val AFTER `drop_held_out` runs.

    `rows` is the generator's raw output, and every DISTRIBUTIONAL claim in
    this module has to be made about this pile instead, because the filter
    does not remove rows evenly. A `multi` row is a `+`-join of two to four
    catalog-entry groups and dies if ANY one of them collides with an exam
    group; a `shared_origin` row is built from a train-only story the exam
    never touches (before 2026-10-04 (Spec 4b-1) it was built from the
    train-only propagation pool). So `multi` loses about a third of its
    origin-read rows here and `shared_origin` loses none.

    Per-row invariants stay on `rows`: it is a superset of this pile, so
    checking it is the stronger check, not the weaker one.
    """
    train, val = generate.split(rows, seed=SEED)
    test = generate.test_set()
    return generate.drop_held_out(train, test) + generate.drop_held_out(val, test)


def _by_case(rows, case):
    return [e for e in rows if e.case == case]


FAMILY_CASES = ("shared_origin", "shared_origin_decoy",
                "shared_origin_probe", "shared_origin_decoy_probe")

# 2026-10-04 (Spec 4b-1): the four meta keys the made-up menu and the invented
# origin read needed. The family does not carry them.
_DROPPED_META_KEYS = ("origin_read_label", "distractor_cause",
                      "wrong_summary_phrase", "expected_confidence")

_BANNED = (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"https?://"),
           re.compile(r"kubeconfig", re.IGNORECASE), re.compile(r"/home/"),
           re.compile(r"@"))


def _origin_answers(story):
    """Every answer that names the origin: each world's origin row answer, and
    each victim answer that links to the origin."""
    out = []
    for world in (story.broken, story.healthy):
        row = world.origin_row
        if row is not None and row.answer is not None:
            out.append(row.answer)
    for v in story.victims:
        out += [a for a in (v.broken, v.healthy) if a is not None and a.link]
    return out


def _authored_origin_text(story):
    """The strings a story authors for the origin, which the exam grades.

    Only a plain (P) story writes them: its `shown_cause`, and the cause of
    each answer that names the origin. A ruled (R) story's cause is the
    rules' wording, decided by code and not chosen by the model, and the
    ruled stories may repeat it on purpose: the trainable node stories read
    like the exam story `node-not-ready`. So a ruled story authors nothing
    here.
    """
    if story.cls == "R":
        return set()
    text = {a.cause for a in _origin_answers(story)}
    text.add(story.shown_cause)
    return text


def _strings(obj):
    """Every string inside a story, however deep it sits."""
    if isinstance(obj, str):
        yield obj
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _strings(getattr(obj, f.name))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, (tuple, list, set, frozenset)):
        for item in obj:
            yield from _strings(item)


def _banned_shapes(story):
    blob = "\n".join(_strings(story))
    return [pat.pattern for pat in _BANNED if pat.search(blob)]


def _dropped_keys(node, path="meta"):
    """Where a dropped key sits in a meta value, however deep."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key in _DROPPED_META_KEYS:
                found.append(here)
            found += _dropped_keys(value, here)
    elif isinstance(node, (list, tuple)):
        for i, value in enumerate(node):
            found += _dropped_keys(value, f"{path}[{i}]")
    return found


def _rows_carrying_dropped_keys(piles):
    return [(name, e.case, e.group, path)
            for name, pile in piles.items() for e in pile
            for path in _dropped_keys(e.meta)]


@pytest.fixture(scope="module")
def family_piles(rows):
    """The four piles a family row can sit in."""
    exam = generate.test_set()
    return {"train": [e for e in rows if e.case in FAMILY_CASES],
            "exam": [e for e in exam if e.case in FAMILY_CASES],
            "wide": generate.shared_origin_wide_probes(),
            "cousin": generate.shared_origin_cousin_probes()}


# ------------------------------------------------- the held-out origin split

def test_both_trainable_pools_exist():
    """`stories` feeds the shared-origin family. The `propagation` pool is kept and still checked."""
    assert stories.trainable()
    assert propagation.trainable_scenarios()


def test_no_trainable_origin_is_an_eval_origin():
    """The whole point. A shared key would make the probe a memory test.

    2026-10-04 (Spec 4b-1): the family's two pools are `stories.exam()` and
    `stories.trainable()`; the trainable `propagation` pool is kept.
    All three must stay clear of the six held-out keys, and the six must still be the same six in both modules.
    """
    held = {st.key for st in stories.exam()}
    assert held == {p.key for p in propagation.all_scenarios()}
    assert {st.key for st in stories.trainable()} & held == set()
    assert {p.key for p in propagation.trainable_scenarios()} & held == set()


def test_no_trainable_story_reuses_an_eval_answer_string():
    """Disjoint keys are not enough — the probe grades the cause STRING.

    Two stories could carry different keys and the same cause string, and
    then the model has seen the graded answer verbatim while `drop_held_out`
    reports a clean split, because it keys on group identity and never looks
    at the text.

    2026-10-04 (Spec 4b-1): the strings compared are the ones a story writes
    for its origin (`_authored_origin_text`). A victim's answer to its OWN
    cause is left out on purpose: it is read off that victim's own lines, and
    two stories may fail a pod the same way. A ruled story's cause is the
    rules' wording, which the stories share on purpose.
    """
    held = set()
    for st in stories.exam():
        held |= _authored_origin_text(st)
    assert held, "the exam stories author no origin text, so this check is empty"
    for st in stories.trainable():
        assert not (_authored_origin_text(st) & held), st.key


def test_every_trainable_scenario_carries_a_healthy_origin_read():
    """The negative case's raw material: the same read, component healthy."""
    for p in propagation.trainable_scenarios():
        assert p.healthy_origin_content.strip(), p.key


# 2026-10-04 (Spec 4b-1): one story is wider than the two-to-four rule. It
# gained the Init:ErrImagePull and Init:ImagePullBackOff victims, which makes
# five. Its count is pinned exactly instead of the rule being loosened.
_VICTIM_COUNTS = {"image-pull-secret-expired": range(5, 6)}


def test_trainable_stories_obey_every_rule_the_eval_table_obeys():
    """The shape rules, on the 41 stories.

    2026-10-04 (Spec 4b-1): the old checks on `shared_verdict`, `confidence`,
    `pass_confidence` and a duplicate `local_cause` have no analog. A story
    has no verdict to forbid, a confidence is a closed pair checked when an
    `Answer` is built, and a victim's own cause is read off its own lines, not
    chosen from a menu.
    """
    for st in stories.trainable():
        assert st.cls in stories.CLASSES, st.key
        assert st.blast_radius in propagation.BLAST_RADII, st.key
        assert st.scope_field in stories.SCOPES, st.key
        assert st.origin_kind in stories.ORIGIN_KINDS, st.key
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", st.key), st.key
        assert len(st.victims) in _VICTIM_COUNTS.get(st.key, range(2, 5)), st.key
        for v in st.victims:
            assert v.issue in vocab.ISSUE_KINDS, f"{st.key}: {v.issue}"


_SCOPE_FOR_RADIUS = {"cluster": "", "node": "node", "namespace": "ns"}


def test_blast_radius_and_scope_field_agree():
    """A node-scoped origin is only coherent if every victim is on that node.
    `shared_origin.draw` pins the field named by `scope_field`, so a radius
    that disagrees with it asserts a blast radius its own inventory
    contradicts.

    2026-10-04 (Spec 4b-1): a story names "no scope" with the empty string,
    not `None`, so the cluster entry above changed from `None` to `""`.
    """
    for st in stories.trainable():
        assert st.scope_field == _SCOPE_FOR_RADIUS[st.blast_radius], st.key


def test_no_two_trainable_stories_share_an_origin_answer_string():
    """A cause string reused across stories is a lookup key spanning both."""
    owner = {}
    for st in stories.trainable():
        for value in sorted(_authored_origin_text(st)):
            assert owner.setdefault(value, st.key) == st.key, (
                f"{st.key} repeats an origin answer string of {owner[value]}: {value!r}")


def test_every_trainable_story_has_at_least_three_victims():
    """The 0907 model failed decider 5 on three-victim decoy halves it had
    never seen: 15 of 24 trainable scenarios held two victims, so the
    generator could only ever render two. Three is the floor now."""
    thin = {st.key: len(st.victims) for st in stories.trainable()
            if len(st.victims) < 3}
    assert thin == {}, f"stories with fewer than three victims: {thin}"


def test_no_trainable_story_text_carries_a_banned_identifier_shape():
    """Every string in a story, however deep, is checked. `_strings` walks the
    dataclasses, so a new field is covered the day it is added."""
    for st in stories.trainable():
        assert _banned_shapes(st) == [], st.key


def test_the_banned_shape_check_sees_a_planted_address():
    """Not vacuous: the same check reports a pattern planted in a victim line
    and one planted in a world."""
    st = stories.trainable()[0]
    victim = dataclasses.replace(st.victims[0], evidence="dial tcp 10.1.2.3:443 refused")
    planted_ip = dataclasses.replace(st, victims=(victim,) + st.victims[1:])
    assert _banned_shapes(planted_ip) == [_BANNED[0].pattern]
    world = dataclasses.replace(st.broken, pull_literal="GET https://registry.example.com/v2/")
    planted_url = dataclasses.replace(st, broken=world)
    assert _banned_shapes(planted_url) == [_BANNED[1].pattern]


# ---------------------------------------------------------- the curriculum mix

def test_the_case_mix_names_shared_origin_and_still_sums_to_one_hundred():
    mix = dict(generate.CASE_MIX)
    assert "shared_origin" in mix
    assert sum(pct for _case, pct in generate.CASE_MIX) == 100


def test_shared_origin_is_not_a_held_out_case():
    """`held_out_case_set` builds eval rows per case from TRAINING scenarios.

    Listing `shared_origin` there would mint test rows out of the trainable
    pool — the leak this whole split exists to prevent, arriving by the other
    door.
    """
    assert "shared_origin" not in generate.HELD_OUT_CASES


def test_generate_emits_shared_origin_rows(rows):
    assert _by_case(rows, "shared_origin")


def test_every_generated_shared_origin_row_names_a_trainable_origin(rows):
    train = {st.key for st in stories.trainable()}
    for case in ("shared_origin", "shared_origin_decoy"):
        pile = _by_case(rows, case)
        assert pile, case
        for e in pile:
            assert e.meta["origin"] in train, e.meta["origin"]


def test_no_family_row_meta_carries_a_dropped_key(family_piles):
    """2026-10-04 (Spec 4b-1): the family's meta lost `origin_read_label`,
    `distractor_cause`, `wrong_summary_phrase` and `expected_confidence`.
    Each had a reader in the old scorer or the old tests; a key that comes
    back would be read by nothing, or by the wrong thing. The check covers
    all four piles a family row can sit in, and looks inside the nested
    per-workload meta as well.
    """
    cases = set()
    for name, pile in family_piles.items():
        assert pile, f"the {name} pile is empty"
        cases |= {e.case for e in pile}
    assert cases == set(FAMILY_CASES), sorted(cases ^ set(FAMILY_CASES))
    assert _rows_carrying_dropped_keys(family_piles) == []


def test_the_dropped_key_check_sees_a_planted_key(family_piles):
    """Not vacuous: each dropped key, planted in the first row of each pile,
    is reported with its pile, case, group and path."""
    for pile, examples in family_piles.items():
        for key in _DROPPED_META_KEYS:
            planted = dataclasses.replace(examples[0], meta={"label": "none", key: "x"})
            assert _rows_carrying_dropped_keys({pile: [planted]}) == [
                (pile, planted.case, planted.group, f"meta.{key}")], (pile, key)


def test_the_dropped_key_check_sees_a_key_nested_under_a_workload(family_piles):
    """The per-workload meta is where `distractor_cause` used to sit."""
    example = family_piles["train"][0]
    planted = dataclasses.replace(example, meta={
        "workloads": {"ns/w": {"job": 1, "distractor_cause": "x"}}})
    assert _rows_carrying_dropped_keys({"train": [planted]}) == [
        ("train", planted.case, planted.group, "meta.workloads.ns/w.distractor_cause")]


def _unpaired_groups(pile):
    """The groups where the broken half and the healthy half do not match one
    for one. A pair is a `shared_origin` row and a `shared_origin_decoy` row
    with the same `Example.group` (Ruling 32)."""
    broken = Counter(e.group for e in _by_case(pile, "shared_origin"))
    healthy = Counter(e.group for e in _by_case(pile, "shared_origin_decoy"))
    return sorted((broken - healthy) + (healthy - broken))


def test_the_cull_takes_every_family_pair_whole(kept):
    """What the model reads holds both halves of every pair, or neither.

    `split` and `drop_held_out` work on the group, and both halves of a pair
    share one, so the cull takes a pair whole. Nothing else in the suite
    checks that it still does. The twin is the counter-example that keeps
    "a story is broken" from being a cue: a pile with the broken half and no
    healthy half teaches the cue back.

    2026-10-04 (Spec 4b-1): this replaces
    `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers`.
    That test counted origin read labels, and the family has none now. The
    thing it protected, whole pairs, is still true of the new rows, so it is
    checked directly.
    """
    assert _by_case(kept, "shared_origin"), "the filter took every shared_origin row"
    assert _unpaired_groups(kept) == []


def test_the_pair_check_sees_half_a_pair(kept):
    """Not vacuous: take one healthy twin out and its group is reported."""
    twin = _by_case(kept, "shared_origin_decoy")[0]
    cut = [e for e in kept if e is not twin]
    assert _unpaired_groups(cut) == [twin.group]


def test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows(kept):
    """job 3 grades two mirror failures, and this change can only push
    the model toward one of them.

    job3 grades a shared claim and a separate claim as mirror failures: if
    the shared answer becomes the usual answer to a multi-workload question,
    the model can swing to claiming a shared origin everywhere, trading one
    failure for its mirror.

    This test counts rows by case family -- how many were drawn from
    `shared_origin`, against `multi` plus `shared_origin_decoy` -- not by
    what the graded answer actually says. The 0.40 cap below guards that
    case-family share.

    This used to demand that `multi` alone outnumber `shared_origin`. That
    was a proxy from before the decoy twin existed: the twin answers
    "separate reasons" over the same workloads, so it is the direct
    counterweight and counts on the same side as `multi`. The proxy went red
    when the shared-origin share rose from 4 to 8 so that every scenario
    keeps at least 12 pairs in train (tests/test_shared_origin_floor.py);
    the claim it stood for did not. The claim was stated directly then: the
    case-family share was 0.368 of the multi-workload rows at 12/12 (0.384 at
    the build size).

    Re-measured 2026-09-19 (Task 9: the pool merge and the mix move to 15%
    on both shared-origin halves plus a 2-point `multi` raise, spec section
    6) -- 0.3822 at this module's size, 0.3839 at the build size (8000).
    This IS the raise spec section 7's decision check anticipated: moving
    `multi` up alongside the shared-origin halves is what keeps the
    case-family share under the 0.40 cap here rather than moving it once
    more.

    Re-measured 2026-09-24, after the case mix moved 7 points from
    `none_of_these` to `own_cause` and `wrong_attribution` -- 0.3810 at this
    module's size, 0.3836 at the build size.

    Re-measured 2026-10-04 (Spec 4b-1) -- 0.3810 at this module's size,
    0.3824 at the build size. This spec did not move either one: the case
    counts are the same. Main read 0.3810 and 0.3824 before the change, so
    the 0.3836 written above was already out of date.

    That case-family share is not the share of multi-workload rows whose
    graded answer actually claims a shared origin. That answer-level share
    used to be about 7 of every 100 -- 22 of 315 at this module's size and
    214 of 3,138 at build size 8000 (the 3,128 written here before was out
    of date), counted on the same kept pile the numbers above come from.
    Re-measured 2026-10-04 (Spec 4b-1): a plain-story `shared_origin` row
    now has a `shared` label whenever two or more of its victims are linked
    to the origin, not only a ruled row, so it is 78 of 315
    (25 of every 100) at this module's size and 795 of 3,138
    (25 of every 100) at build size 8000. This test still does not
    measure it and does not guard it.
    """
    shared = len(_by_case(kept, "shared_origin"))
    separate = (len(_by_case(kept, "multi"))
                + len(_by_case(kept, "shared_origin_decoy")))
    assert shared, "the filter took every shared_origin row"
    share = shared / (shared + separate)
    assert share <= 0.40, (
        f"shared_origin case family is {share:.3f} of multi-workload rows")


# ------------------------------------------------- the structural-cue killer

def test_node_memory_pressure_spells_no_taint_the_way_kubectl_does():
    """kubectl prints `Taints:  <none>`. The record said `Taints:  none`.

    2026-10-04 (Spec 4b-1): moved here from the origin-variant group. Its
    variant checks went with the variants. What stays is the
    `propagation` pool's healthy read text.
    """
    p = {q.key: q for q in propagation.trainable_scenarios()}["node-memory-pressure"]
    assert "Taints:  <none>" in p.healthy_origin_content
    assert "Taints:  none" not in p.healthy_origin_content


def _independent_share(rows):
    """Independent-answer share among rows that carry an origin read.

    `shared_origin_decoy` counts on the independent side and MUST: it is the
    counter-example class now. Leaving it out kept this instrument reading
    0.386 while the pile it measures had moved to 0.619 -- passing, and
    blind to the 169 rows the change was about.

    2026-10-04 (Spec 4b-1): the family's rows carry no read label now, so the
    family is counted by case: every `shared_origin` row on one side and every
    `shared_origin_decoy` row on the other. `multi` is still counted by its
    label, because only its negatives carry the read. The counts did not
    move: 120 + 120 + 35 at this module's SIZE, which is 0.5636.

    2026-10-05 (Spec 4b-3): `multi` carries no origin read now, so only the
    family counts, and the share is exactly 0.5.
    """
    shared = len(_by_case(rows, "shared_origin"))
    independent = len(_by_case(rows, "shared_origin_decoy"))
    return independent / (shared + independent)


def test_the_generator_emits_the_two_classes_near_evenly(rows):
    """History up to 2026-10-05 (Spec 4b-3), kept as written. Until then the
    every-third `multi` negatives existed, and this text argued for keeping
    them. They are gone; see the last paragraph for the live number.

    What the EMITTER controls, and it is no longer a coin flip: 0.568,
    re-measured 2026-09-19 (Task 9: pool merge + mix move, spec section 6)
    at 0.5636.

    Two sources feed the independent side now. The paired half is exact by
    construction -- every `shared_origin` row is emitted with a
    `shared_origin_decoy` twin from the same salt, so those two contribute
    120/120 at this module's SIZE (was 96/96 before Task 9's mix move to 15%
    on both shared-origin halves) and cannot drift. On top of that sit the
    surviving every-third-`multi` negatives, which have no positive
    counterpart, and they are the whole of the lean.

    Kept deliberately rather than balanced away: they are a DIFFERENT
    counter-example -- a healthy origin read over arbitrary victims, where
    the pair holds the victims fixed -- so removing them to reach 0.5 would
    trade coverage for a rounder number. The band is stated where the pile
    actually sits and still fails both degenerate ends.

    2026-10-04 (Spec 4b-1): unchanged at 0.5636. The family is built from
    stories now, but a pair is still one `shared_origin` row and one
    `shared_origin_decoy` twin from the same salt, so the paired half is
    still 120/120 at this module's SIZE, and `multi` was not touched, so its
    35 negatives are the same 35.

    2026-10-05 (Spec 4b-3): the every-third `multi` negatives are gone, so
    only the pair is left and the share is exactly 0.5 (it was 0.5636). The
    old band was 0.55-0.75; it is a test band, not a bar.
    """
    assert _independent_share(rows) == 0.5


def test_the_trained_pile_is_not_one_sided_among_origin_read_rows(kept):
    """History up to 2026-10-05 (Spec 4b-3), kept as written. Until then the
    `multi` negatives had no twin and the lean ran toward the independent
    answer. They are gone; see the last paragraph for the live number.

    What the MODEL reads, which is the number that decides what it learns.

    A 9:1 split is a prior, not a cue kill. This is the assertion the module
    docstring's argument actually depends on, and the one that was missing.

    It used to record a ~62/38 lean toward the SHARED answer and name the
    remedy it had not paid for: "closing the gap the rest of the way means
    emitting more counter-examples, which moves dataset bytes". That was
    paid. `shared_origin_decoy` emits one counter-example per positive from
    the same salt, and the lean now runs the other way -- 0.556 toward the
    independent answer, from the `multi` negatives that have no twin. It read
    0.619 while the halves held 4% each; doubling them to 8% moved it toward
    even, and the band's floor is now close.

    The direction matters less than what it is no longer confounded with.
    Before, the two classes differed in their victims as well as in their
    read, so symptom coherence separated them without reading the origin at
    all; the paired half holds the victims byte-identical, so it cannot.
    `drop_held_out` splits on group keys and both halves of a pair share
    one, so it takes pairs whole and the paired core survives the filter
    exactly -- the residual lean is the negatives, not the filter.

    The band still fails loudly at the state this module was written to end
    — 1.00/0.00, no counter-examples at all — and now also fails if the
    pairing ever emits one-sidedly.

    The floor moved from 0.55 to 0.52 on 2026-09-08 when the halves went to
    12%: the kept pile then read 0.556 at this size and 0.546 at the build
    size, and 0.52 keeps three points of room below both.

    Re-measured 2026-09-19 (Task 9: pool merge + mix move to 15% on both
    shared-origin halves, spec section 6) -- 0.5455 at this size, 0.5430 at
    the build size. Both readings moved down slightly toward the floor
    because the shared-origin pair grew faster than the surviving `multi`
    negatives; 0.52 still keeps room below both.

    Re-measured 2026-10-04 (Spec 4b-1) -- 0.5385 at this size, 0.5461 at the
    build size. Both are unchanged, because the rewrite moved no case count,
    so the floor keeps 0.0185 and 0.0261 of room. The family has no read
    label now, so "origin read rows" means the family's two cases, counted
    by case, plus the `multi` rows that carry a label (see
    `_independent_share`).

    2026-10-05 (Spec 4b-3): 0.5 exactly (it was 0.5385 at this size).
    `drop_held_out` takes pairs whole, so the kept pile is the pair alone.
    The old band was 0.52-0.70; it is a test band, not a bar.
    """
    share = _independent_share(kept)
    assert share == 0.5, f"kept-pile independent share {share:.3f}"


def test_a_negative_multi_row_still_says_separate_reasons(rows):
    """2026-10-05 (Spec 4b-3): a `multi` row says "separate reasons" only when
    its rows show it: the rules confirmed different causes, or every row names
    its own different cause. Otherwise it says the rules confirmed no shared
    cause (4b-1's fallback)."""
    for e in _by_case(rows, "multi"):
        causes = ["" if v == contract.NONE_OF_THESE else v for v in e.meta["expected"].values()]
        assert (propagation.SEPARATE_REASONS in e.assistant) == gold.separate_for(
            e.meta["label"], causes), e.group


def test_a_shared_origin_training_row_never_says_separate_reasons(rows):
    for e in _by_case(rows, "shared_origin"):
        assert propagation.SEPARATE_REASONS not in e.assistant


def test_a_shared_ruled_row_decides_every_workload(rows):
    """A ruled story is decided end to end, and its label says so.

    Spec section 3, ruling C asked this of every `shared`-labelled row: every
    workload decided, one cause for the origin, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback), which can decide several
    victims to several PVC causes and still be one `shared` group. The
    exemption became a live path on 2026-09-19, when the two ruled PVC stories
    joined the trainable pool.

    2026-10-04 (Spec 4b-1): a plain story's broken-world row is `shared` too
    now, whenever two or more of its victims are linked to the origin
    (`gold.label_for`), and a plain story is not decided: the model names the
    cause from the evidence. So the claim is narrowed to the ruled stories
    (`cls == "R"`). The PVC exemption used to be a named set of keys. It is the
    story's own `origin_kind` now, so no key list can drift.
    """
    by_key = stories.by_key()
    seen = 0
    for e in _by_case(rows, "shared_origin"):
        st = by_key[e.meta["origin"]]
        if st.cls != "R" or e.meta["label"] != "shared":
            continue
        seen += 1
        assert all(w["decided"] for w in e.meta["workloads"].values()), st.key
        if st.origin_kind != "pvc":
            assert len(set(e.meta["expected"].values())) == 1, st.key
    assert seen, "no ruled shared_origin row reached the label shared"


# ------------------------------------------------------ the eval must not move

def test_the_eval_set_is_two_hundred_and_forty_nine_rows():
    """253 until `shared_origin_decoy_probe` appended its ten, then 263
    until the 2026-09-24 job-2 generator fix cut the `none_of_these` slice
    from 19 rows to 8, then 252 until 2026-09-26 (faithful prompts), when
    `truncated`, `injection` and `positional_probe` came to cover only the
    17 entries the rules decide (-6) and the new
    `pvc-unbound-unschedulable` entry added one row to each of five other
    cases (+5). Then 251 until later that day, when `contradiction_probe`
    came to cover the same 17 entries: three entries' rows left it and the
    new entry's row joined it (-2).

    This test exists so the TRAINING half of the shared-origin work cannot
    move the exam by accident — a curriculum change that grows the test set
    invalidates every banked scoreboard silently. It does not forbid moving
    the exam on purpose; the decoy slice did that, in its own commit, with
    `tests/test_shared_origin_decoy_probe.py` proving the training set stayed
    byte-identical across the change. The 2026-09-24 generator fix moved it
    on purpose too, and re-pinned both exam digests below in the same
    commit. The 2026-09-26 job-1 change did too, and re-pinned all three
    exam digests in the same commit. So did the 2026-09-26 contradiction
    change.
    """
    # 2026-09-26 (faithful prompts): see the docstring. 252 -> 251.
    # 2026-09-26 (faithful prompts): see the docstring. 251 -> 249.
    assert len(generate.test_set()) == 249


# The frozen slice, byte for byte: the first 253 rows until 2026-09-24,
# the first 242 since (see the fifth entry below). From 0830 until
# 2026-09-16 this pin never moved, and that is what let every scoreboard on
# the 253 compare against every other. It moved once, on purpose: the node-not-ready and
# registry-unreachable builders were rewritten and the system prompt moved
# out of `contract.py` into `contract/system_prompt.txt`, and both changed
# the rendered bytes of every row. A number on the 253 measured before that
# rewrite is not comparable to one measured after it. The row count above
# cannot see a rewrite that keeps the count; this can.
#
# It moved a second time, on 2026-09-16, and for a plain reason: no prompt
# carried a `decided by rules:` line. Job 1 grades the model on echoing that
# line, so every row it should appear in was missing the thing being graded.
# Adding it changed the rendered bytes of every decided row. A job-1 number
# from before this fix measures something else and is retired on purpose.
#
# It moved a third time, on 2026-09-19, for `_render_shared_origin`'s
# decided-row fix (section 3 of the 2026-09-19 training-targets design): all ten
# `shared_origin_probe` rows (244-253, inside this frozen slice) change.
# A decided victim's row cause and rationale now come from the rules
# (`result.cause`, `_rule_rationale(result)`) instead of always the
# formatted `shared_cause`, and a `none`-labeled row's summary now says
# "kubeagent's rules did not confirm one cause on two or more of them"
# instead of falsely claiming a shared one. A key-by-key diff of the exam
# before and after the fix measured the footprint: exactly these 10 rows
# plus 4 of the 10 `shared_origin_decoy_probe` rows (outside this frozen
# slice, see `EVAL_SET_SHA256` below) change, and nothing else does.
#
# It moved a fourth time, on 2026-09-23, for the exam-grader fix
# (2026-09-23-exam-grader-fix-design.md, sections 2 and 5). Every
# UNDECIDED shared-origin workload's `meta.own_cause_keywords` goes from
# `[]` to a curated two-word pair -- the victim's own in the healthy world,
# the scenario's shared pair in the broken one. A DECIDED one still carries
# `[]`, because it is job 1 and graded by echo. Inside this slice that is
# the four `shared_origin_probe` workloads that scored 0.0 against their own
# gold answer; the other sixteen live in the ten rows outside it, and
# `EVAL_SET_SHA256` below moves for them. `_digest` hashes
# `generate.to_row`, which carries `meta`, so the digest moves although not
# one RENDERED byte does. That is pinned separately and independently:
# `tests/test_exam_prompt_stability.py` compares the regenerated exam's
# `messages` -- system, user and gold answer -- against the banked
# `out/dataset-0920/test.jsonl` row for row, and a key-by-key diff of the
# exam before and after this fix reports `meta` as the only top-level key
# that changed. That is what makes this a meta-only move and not a new exam.
#
# It moved a fifth time, on 2026-09-24, for the job-2 generator fix
# (2026-09-24-job2-generator-fix-design.md), and was renamed from
# `FROZEN_253_SHA256`: that fix shrinks the `none_of_these` slice, so the
# slice stops being 253 rows long. It keeps its meaning -- every exam row
# before the trailing ten `shared_origin_decoy_probe` rows -- and
# `test_the_frozen_slice_is_every_row_before_the_decoy_probe` pins its
# length on its own. This time rendered bytes move, not only `meta`, and
# the new exam is a new baseline: no number on it compares with one from
# before. What moved it, in commit order:
# - The catalogue stopped doubling the `log cause: ` prefix
#   (`crashloop-pod`, `init-crashloop`, `restart-loop`) and quotes the
#   container in `restart-loop`'s evidence, as kubeagent prints it. 41
#   rows move, in the user message only: 8 `attributed`, 6
#   `multi_misattribution_probe`, and 3 in each of the other nine cases
#   outside the two shared-origin probes.
# - One builder now makes every undecided row (`none_of_these`,
#   `own_cause`, `wrong_attribution`, `misattribution_probe`). The
#   `none_of_these` slice falls from 19 rows to 8: two for each thin entry
#   (`crashloop-pod`, `coredns-corefile-broken`, `init-crashloop`,
#   `restart-loop`), one per undecided shape, answered `none_of_these` at
#   `low`. The held-out rows interleave by entry, so every row from the
#   first changed entry on shifts, and the slice ends 11 rows shorter. Of
#   the rows that stay, keyed by case and group: all 19 `own_cause` rows
#   change their user message (every candidate is now ruled out, so no
#   object is read, and crash-family rows gain a log read) and 16 of them
#   their gold answer and meta (the entry's own confidence, not a flat
#   `medium`); all 19 `misattribution_probe` rows change their user message
#   the same way (its menu was already fully ruled out before this fix; the
#   header goes because the builder now computes it with `header_for`
#   instead of forcing the entry's flat confidence); and 9 of 19
#   `wrong_attribution` rows change their user message (4
#   take the header kubeagent's confidence rule gives the attributed cause,
#   the other 5 gain a log read). No other row moves.
# - A multi-workload row keeps the log read kubeagent makes for every
#   crash-family workload, and `multi_misattribution_probe` prints the
#   header kubeagent's confidence rule gives each constituent's attributed
#   cause instead of the entry's own confidence. 13 of the 19
#   `multi_misattribution_probe` rows change their user message: 4 take
#   only a new header, 5 only gain a log read, and 4 get both. Their gold
#   answer and meta do not move, and no other row does.
# - `empty_candidates` answers at the entry's own confidence instead of a
#   flat `medium`, and a crash-family entry keeps its log read. 16 of its
#   19 rows change their gold answer and meta (`medium` to `high`, one per
#   direct entry), and 5 of those 16 also change their user message (one
#   per crash-family entry). The other 3 are the indirect entries, whose
#   own confidence is `medium`. No other row moves.
#
# 2026-09-26 (faithful prompts): a row with a node candidate now opens its
# inventory with kubeagent's cluster-health block. 150 of the 242 rows here
# gain it in the user message and change by exactly that block; no gold
# answer or meta moves, and no other row does. Every number banked against
# the old bytes is retired.
# aff7cc96aaec86bf7ce7d972632966a2c770adcde9facd4c8ef2b427f2f8c490 ->
# e6a2a5091c1ca2cc9edde8dfaf08afe221113e83b72011ea5889927c780684a1
#
# 2026-09-26 (faithful prompts), again: the catalog now uses the detector and
# kubelet text kubeagent really prints. The catalog feeds every case here,
# so 222 of the 242 rows move. 218 change their user message: the finding
# and event lines carry kubeagent's own words, a node describe prints its
# four conditions, and five impossible PVC decoys became node decoys or went
# away. 89 change their meta: eleven entries have new keyword pairs, the
# decoy causes follow the PVC swap, and the `oversized`
# `contradiction_probe` row is undecided now, so it moves from job 1 to
# job 2. 6 change their gold answer: `worker-containerd-stop`'s own cause
# now uses the kubelet's words. No system message moves. Every number
# banked against the old bytes is retired.
# e6a2a5091c1ca2cc9edde8dfaf08afe221113e83b72011ea5889927c780684a1 ->
# e9d3ba75a00fbeac9f50749fa432908874320d650a9783a7ab0171cc0fc7f6fa
#
# 2026-09-26 (faithful prompts): the undecided rows now take their reads and
# candidates from the ported gather. 71 of the 242 rows change their user
# message, all in the five undecided cases: `own_cause`,
# `wrong_attribution` and `misattribution_probe` 19 each, `none_of_these`
# 8, `empty_candidates` 6. Each reads its pod's events first, as kubeagent
# does. A refuted row's ruled-out node no longer gets a describe.
# `deployment-bad-image-tag`'s refuted row now shows its registry ruled out,
# since one failing workload does not reach the threshold of 2. That row is
# the only meta change: its `decoy_cause` and `decoy_by_workload` now name
# `registry registry.example.com`, the cause its candidate line prints. No
# system message, gold answer, label or `flagged` list moves.
# e9d3ba75a00fbeac9f50749fa432908874320d650a9783a7ab0171cc0fc7f6fa ->
# 24cc3f4beefb4ab3865d1bb4424d5d590323586e0f082abaaad1889f9df9d29b
#
# 2026-09-26 (faithful prompts): the job-1 rows now take their reads,
# candidates and gold answer from the gather. The slice goes from 242 rows
# to 241, and only 127 rows stay byte for byte. 31 corpus rows the rules do
# not decide (`deployment-bad-image-tag` 24, `node-cordon-diskfull` 4,
# `oversized-job-unschedulable` 3) are `own_cause` rows now, not
# `attributed`. `truncated`, `injection` and `positional_probe` lose those
# three entries' rows and gain one for the new `pvc-unbound-unschedulable`
# entry, which also adds one row each to `own_cause`, `empty_candidates`,
# `wrong_attribution`, `misattribution_probe` and
# `multi_misattribution_probe` (there it takes the wrap pair's place, so one
# old pair goes and two new ones come). The 70 job-1 rows that stay
# (`attributed` 22, the other three 16 each) change their user message,
# gold answer and meta: the gold cause is the rules' own decision, the
# summary is one line, and `truncated` loses its flat "low" and its "treat
# with caution" line. IS-10 moves 4 more rows: `node-cordon-diskfull`'s
# `wrong_attribution` row (user message), its `contradiction_probe` row
# (user message and meta: it is undecided now, so it moves from job 1 to
# job 2), and two `multi_misattribution_probe` rows (user message). No
# system message moves. Every number banked against the old bytes is
# retired.
# 24cc3f4beefb4ab3865d1bb4424d5d590323586e0f082abaaad1889f9df9d29b ->
# 41e7abdecf2d914d4eb741fa755bcf113c7eb681965023e3620fa38e88712af1
#
# 2026-09-26 (faithful prompts): the `contradiction_probe` rows now take
# their reads from the gather and their gold answer from the rules, over
# the 17 entries the rules decide. The slice goes from 241 rows to 239.
# The 19 old `contradiction_probe` rows go and 17 new ones come: the rows
# of `deployment-bad-image-tag`, `node-cordon-diskfull` and
# `oversized-job-unschedulable` leave, and the new
# `pvc-unbound-unschedulable` entry joins. The other 16 entries keep their
# place and their drawn names, but every one of their rows changes its user
# message, gold answer and meta: the gold is the rules' cause, not
# `none_of_these`, and `decoy_cause` is gone. The other 222 rows are byte
# for byte the old ones, in the same order; the ten `shared_origin_probe`
# rows at the end of the slice sit two places earlier. No system message moves.
# Every number banked against the old bytes is retired.
# 41e7abdecf2d914d4eb741fa755bcf113c7eb681965023e3620fa38e88712af1 ->
# e562f79462dc3897931262aece841ccfb57d8788d9612e6141327c87ef0b7043
#
# 2026-09-26 (faithful prompts): the `multi` rows moved onto the gather, and
# the node list grew from three workers to five so that a row of up to four
# workloads can put each one on a node of its own. The slice stays at 239
# rows, and 152 of them move. The 20 `multi_misattribution_probe` rows move
# because they now take their reads from one gather over the whole row. The
# other 132 move only because the node list grew: every name drawn after a
# node draw shifts, so drawn names, nodes and victims change. Rebuilt with
# the old three-worker list, only the 20 `multi_misattribution_probe` rows
# differ from the old bytes. By case: `own_cause` 22, `attributed` 20,
# `truncated` 11, `injection` 13, `empty_candidates` 2, `wrong_attribution`
# 15, `none_of_these` 6, `positional_probe` 12, `misattribution_probe` 13,
# `contradiction_probe` 14, `shared_origin_probe` 4. No system message
# moves. Every number banked against the old bytes is retired.
# e562f79462dc3897931262aece841ccfb57d8788d9612e6141327c87ef0b7043 ->
# b71ec0b940aae861dd1fcc7008340b48db7250dafd075a7084ba910f5f8138e1
#
# 2026-09-26 (faithful prompts): coredns-corefile-broken now draws its
# restarts from 6, not 1. Its finding text fixes restartCount=6, and
# kubeagent's workload line sums its containers' restarts
# (internal/inventory/inventory.go:158-170, 488), so a line below 6 was one
# kubeagent cannot print. The slice stays at 239 rows, and the 16
# coredns-corefile-broken rows move: each one changes one line of its user
# message, the workload line's restart count. No group, gold answer, meta
# or system message moves, and no other row moves. Every number banked
# against the old bytes is retired.
# b71ec0b940aae861dd1fcc7008340b48db7250dafd075a7084ba910f5f8138e1 ->
# 99916709329ca5b9d027afb18b83c27ae99566f8dc87206ddfa8953c3aa691d1
#
# 2026-09-26 (faithful prompts): the suggested fix line names the pod
# `<pod>`, as kubeagent's prompt does (internal/explain/explain.go:148-171).
# A drawn pod name is never the workload's own, so every fix command in the
# slice changes: all 239 rows move, and each changes only in its fix lines,
# 273 commands in all. No group, gold answer, meta or system message moves.
# Every number banked against the old bytes is retired.
# 99916709329ca5b9d027afb18b83c27ae99566f8dc87206ddfa8953c3aa691d1 ->
# 9d548bee64a9519a3ca080fcde14846b4f0beb0fac4381c582002b3828dbdde6
#
# 2026-09-28 (final review): a `multi_misattribution_probe` row now lists
# every down node for every workload, as kubeagent does: a node the
# workload has no pod on is "ruled out — no pod of this workload is
# scheduled on it" (internal/rootcause/rootcause.go:24-56). Before, each
# workload listed only its own node. The slice stays at 239 rows, and the
# 20 `multi_misattribution_probe` rows move: each changes only its user
# message, which gains ruled-out node lines, 36 in all, and loses none. No
# group, gold answer, meta, decoy or system message moves, and no other row
# moves. Every number banked against the old bytes is retired.
# 9d548bee64a9519a3ca080fcde14846b4f0beb0fac4381c582002b3828dbdde6 ->
# 48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69
#
# 2026-09-29 (Spec 4a): meta only, no message moves. Every workload's meta
# gains `own_cause_must_not`, and the two init bad-tag entries gain `init`
# in their `own_cause_keywords`. The slice stays at 239 rows, and all 239
# move, each in its meta alone. No group, prompt, gold answer, decoy or
# system message moves. Every number banked against the old bytes is
# retired.
# 48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69 ->
# f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a
#
# 2026-10-04 (Spec 4b-1): the shared-origin family is rebuilt on kubeagent's
# real pipeline (2026-10-03-shared-origin-rewrite-design.md). The slice
# stays at 239 rows. Its 10 `shared_origin_probe` rows move: 10 user
# messages, 10 gold answers and 10 metas; their meta drops
# `distractor_cause`, `expected_confidence`, `wrong_summary_phrase`. The other 229 rows do not move
# (`OTHER_FAMILIES_SHA256` in tests/test_generate.py). Every number banked
# against the old bytes is retired.
# f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a ->
# d7d609f9e63cb0d52c74a92f33242b8967dc46e4670924be0d15288d29ef941b
# 2026-10-04 (Spec 4b-2): the catalog gold rests on anchors in own lines.
# Exam answers and meta move (reasons, causes, confidence, two entries'
# keys); no prompt byte moves (tests/test_catalog_gold.py).
# d7d609f9e63cb0d52c74a92f33242b8967dc46e4670924be0d15288d29ef941b ->
# 660f2b55fbc08426122381285d40a628f8a2a666f2756348086e71acf773f8b3
FROZEN_SLICE_SHA256 = "660f2b55fbc08426122381285d40a628f8a2a666f2756348086e71acf773f8b3"

# The whole exam, the frozen slice plus the ten `shared_origin_decoy_probe`
# rows (263 until 2026-09-24, 252 since). First captured on `main` @
# `ee2980e` as `e8cbb549…b49de`; 0902 and 0905 were scored against that
# set in one go, 0901 covered the same rows as two runs
# (which is why its paired join reported `unpaired`), and 0830 predates the
# ten decoy rows entirely. Re-pinned on 2026-09-05 when `healthy_evidence`
# corrected the two node-disk-pressure decoy rows (257 and 262), whose
# inventory named the disk-pressure taint in a world whose node read showed
# none: those two rows changed in one line each, the other 261 did not, and
# the training and validation rows regenerated byte-identical. So a decoy
# number measured before that date is not comparable to one measured after
# it. On 2026-09-05 the 253 stayed put -- only the ten decoy rows changed --
# so a number on the 253 measured before that date was still comparable to
# one measured after it. A change that moves this hash is wrong
# unless it means to retire that comparison, and says so here.
#
# Re-pinned again on 2026-09-16, when the node-not-ready and
# registry-unreachable builders were rewritten and the system prompt moved
# out of `contract.py` into `contract/system_prompt.txt`: the rendered bytes
# of every row changed, so every number banked against the old bytes is
# retired by this change on purpose. Unlike 2026-09-05, this time the 253 moved
# too -- a number on the 253 from before this rewrite is not comparable to
# one after it either.
#
# Re-pinned once more on 2026-09-16, in the same commit that fixed the
# missing `decided by rules:` line. Two things moved the bytes. The line
# itself now renders on all 157 rule-decided workloads, where before it
# rendered on none. And every decoy row names its `decoy_cause` in the meta
# again, which the decoy-rate and length-gap readings both read. The ten
# `shared_origin_decoy_probe` rows also changed label from `none` to
# `separate`. Every decoy and job-1 number banked before this is retired.
#
# Re-pinned a final time on 2026-09-16: the `separate` override above was
# reverted (see `cases.shared_origin_decoy_probe`). The label the rules
# derive for those ten rows is `none` -- they carry neither the "shared
# cause" nor the "no shared cause" line -- and `**r.meta` already carried
# that derived value before anything overrode it. The `decided by rules:`
# line and the `decoy_cause` key from the previous re-pin stay; only the
# label moved, from `separate` back to `none`. This changes the rendered
# bytes of the ten decoy rows again, so every job-3 number banked against
# the `separate` re-pin above is retired.
#
# Re-pinned once more on 2026-09-19, in the same commit and for the same
# `_render_shared_origin` fix that moved `FROZEN_SLICE_SHA256` above (see
# its 2026-09-19 entry). Four of the ten `shared_origin_decoy_probe` rows
# change too -- exactly the ones with a decided victim this draw (two
# coredns-down, two node-disk-pressure): their decided victim's row cause
# and rationale move the same way, off the SAME per-victim decide, which
# never read `healthy` before or after this fix. The other six decoy rows
# (the three origin-object stories, whose healthy world decides nothing)
# do not move. 14 of the 263 rows change in total, byte for byte, and
# each only in the assistant message and the meta that mirrors it.
#
# Re-pinned a fourth time on 2026-09-23, in the same commit and for the
# same exam-grader fix that moved `FROZEN_SLICE_SHA256` above (see its
# 2026-09-23 entry). This digest covers the frozen slice AND the ten
# `shared_origin_decoy_probe` rows outside it, so it carries that entry's
# four workloads plus the sixteen in those ten rows -- the twenty that
# scored 0.0 against their own gold answer before this fix. Same meta-only
# reason, and no `messages` byte moves in either slice.
#
# Re-pinned a fifth time on 2026-09-24, in the same commits and for the
# same job-2 generator fix that moved `FROZEN_SLICE_SHA256` above (see its
# 2026-09-24 entry). None of the ten `shared_origin_decoy_probe` rows
# moves, so this digest moves only because the frozen slice inside it does.
#
# 2026-09-26 (faithful prompts): the cluster-health block that moved
# `FROZEN_SLICE_SHA256` above. The ten `shared_origin_decoy_probe` rows have
# no node candidate and do not move, so this digest moves only because the
# frozen slice inside it does.
# 97a89e93fc5fdfdfebd0689fb5b74e060b68ba6879236ca12533e33a4ecb9c81 ->
# d6fc0eda06a3a032fb0f827ea5c886df3d1c408e6ff40ac4c17dd0922a466d31
#
# 2026-09-26 (faithful prompts), again: the catalog text change that moved
# `FROZEN_SLICE_SHA256` above. The ten `shared_origin_decoy_probe` rows come
# from `dataset.propagation`, not the catalog, and do not move, so this
# digest moves only because the frozen slice inside it does.
# d6fc0eda06a3a032fb0f827ea5c886df3d1c408e6ff40ac4c17dd0922a466d31 ->
# f4be6c578dd5756eb0d0d279bbe25b7dba24d75696443b7daac66f3cde9323eb
#
# 2026-09-26 (faithful prompts): the undecided rows moved onto the gather,
# which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows are not undecided catalog rows and do not
# move, so this digest moves only because the frozen slice inside it does.
# f4be6c578dd5756eb0d0d279bbe25b7dba24d75696443b7daac66f3cde9323eb ->
# f02889fb9a682ac761ac00eac8c4395bab280a3d1ea3b65bc8d5fffb117a2bee
#
# 2026-09-26 (faithful prompts): the job-1 rows moved onto the gather,
# which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows are not job-1 catalog rows and do not
# move, so this digest moves only because the frozen slice inside it does.
# f02889fb9a682ac761ac00eac8c4395bab280a3d1ea3b65bc8d5fffb117a2bee ->
# 8a79d7a9d9d13cb7ab9adaafd83278932b652fd70b1482ce16f513429f312d89
#
# 2026-09-26 (faithful prompts): the contradiction rows moved onto the
# gather and the rules, which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows are not catalog rows and do not move,
# so this digest moves only because the frozen slice inside it does.
# 8a79d7a9d9d13cb7ab9adaafd83278932b652fd70b1482ce16f513429f312d89 ->
# e57c15c107bf52aa416533a6b246e2a3ba6ab8b7b893ef3708e4a54431184835
#
# 2026-09-26 (faithful prompts): the `multi` gather and the five-worker node
# list that moved `FROZEN_SLICE_SHA256` above. This time four of the ten
# `shared_origin_decoy_probe` rows move too. They draw nodes and victims from
# the same name lists, so the longer node list moves their draws; their user
# message changes, and in two of them the gold answer does as well. The
# other six decoy rows do not move.
# e57c15c107bf52aa416533a6b246e2a3ba6ab8b7b893ef3708e4a54431184835 ->
# 31b599744777e430b51fe7ab8235891db869e62fbc2860d832bb19f67f87072e
#
# 2026-09-26 (faithful prompts): coredns-corefile-broken draws its restarts
# from 6, which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows hold no coredns-corefile-broken workload
# and do not move, so this digest moves only because the frozen slice
# inside it does.
# 31b599744777e430b51fe7ab8235891db869e62fbc2860d832bb19f67f87072e ->
# 423a96003e6f34d7bcb3828081ed58e7ec4a71ad9356e7aa34e164a852fd28a4
#
# 2026-09-26 (faithful prompts): the fix line names the pod `<pod>`, which
# moved `FROZEN_SLICE_SHA256` above. The ten `shared_origin_decoy_probe` rows
# move too, for the same reason: their 24 fix commands name `<pod>` now.
# Only their fix lines change; no gold answer or meta moves.
# 423a96003e6f34d7bcb3828081ed58e7ec4a71ad9356e7aa34e164a852fd28a4 ->
# 85388c7e17b60d0c4dc6dfc3448b0ff82226e028ecebf6443f20d00082163b5f
#
# 2026-09-28 (final review): the `multi_misattribution_probe` rows list
# every down node for every workload, which moved `FROZEN_SLICE_SHA256`
# above. The ten `shared_origin_decoy_probe` rows are not `multi` rows and
# do not move, so this digest moves only because the frozen slice inside
# it does.
# 85388c7e17b60d0c4dc6dfc3448b0ff82226e028ecebf6443f20d00082163b5f ->
# b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653
#
# 2026-09-29 (Spec 4a): meta only, no message moves. Every workload's meta
# gains `own_cause_must_not`, which moved `FROZEN_SLICE_SHA256` above. The
# ten `shared_origin_decoy_probe` rows move too, for the same reason; no
# prompt, gold answer or decoy of theirs moves.
# b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653 ->
# a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2
#
# 2026-10-04 (Spec 4b-1): the shared-origin rows are rebuilt on kubeagent's
# real pipeline, which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows move too: 10 user messages,
# 10 gold answers and 10 metas.
# a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2 ->
# 0a9b308a210157c3147cdc8c5b39471cbb50522f27bd792e39fded423f525a0d
# 2026-10-04 (Spec 4b-2): the catalog gold rests on anchors in own lines.
# Exam answers and meta move (reasons, causes, confidence, two entries'
# keys), which moved `FROZEN_SLICE_SHA256` above; no prompt byte moves
# (tests/test_catalog_gold.py).
# 0a9b308a210157c3147cdc8c5b39471cbb50522f27bd792e39fded423f525a0d ->
# 94b384623a66bbee21520275c0282973ade7b089c3e8cdab94447398c218661e
EVAL_SET_SHA256 = "94b384623a66bbee21520275c0282973ade7b089c3e8cdab94447398c218661e"


def _digest(rows) -> str:
    blob = json.dumps([generate.to_row(e) for e in rows],
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_the_frozen_slice_is_every_row_before_the_decoy_probe():
    """The frozen slice is named by what it holds, not by a row number:
    every exam row before the trailing ten `shared_origin_decoy_probe`
    rows. Its length is pinned here, apart from its digest: 253 until the
    2026-09-24 job-2 generator fix, 242 until the 2026-09-26 job-1 change,
    241 until the 2026-09-26 contradiction change (see
    `FROZEN_SLICE_SHA256`), 239 since."""
    rows = generate.test_set()
    assert [e.case for e in rows[-10:]] == ["shared_origin_decoy_probe"] * 10
    assert "shared_origin_decoy_probe" not in {e.case for e in rows[:-10]}
    # 2026-09-26 (faithful prompts): see `FROZEN_SLICE_SHA256`. 242 -> 241.
    # 2026-09-26 (faithful prompts): see `FROZEN_SLICE_SHA256`. 241 -> 239.
    assert len(rows[:-10]) == 239


def test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used():
    assert _digest(generate.test_set()[:-10]) == FROZEN_SLICE_SHA256, (
        "the frozen slice moved; every banked scoreboard comparison is now void")


def test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used():
    assert _digest(generate.test_set()) == EVAL_SET_SHA256, (
        "the exam moved; decoy numbers measured before this are no longer comparable")


def test_no_eval_row_comes_from_the_trainable_pool():
    train = {p.key for p in propagation.trainable_scenarios()}
    train |= {st.key for st in stories.trainable()}
    for e in generate.test_set():
        assert e.meta.get("origin") not in train
        for part in e.group.split("+"):
            assert not any(f"propagation:{k}:" in part for k in train), part


def test_the_probe_still_draws_only_held_out_origins():
    held = {st.key for st in stories.exam()}
    exam = generate.test_set()
    for case in ("shared_origin_probe", "shared_origin_decoy_probe"):
        probes = [e for e in exam if e.case == case]
        assert len(probes) == 10, case
        for e in probes:
            assert e.meta["origin"] in held, (case, e.meta["origin"])


def test_training_still_contaminates_nothing(rows):
    test = generate.test_set()
    train, val = generate.split(rows, seed=SEED)
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    held = {part for e in test for part in e.group.split("+")}
    for e in kept:
        assert not any(part in held for part in e.group.split("+")), e.group


DRAWS = 48  # plain-story shared_origin rows per story at BIG; see below.
RULED_DRAWS = 70  # ruled-story shared_origin rows per story at BIG.
# 2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, 35 plain
# stories (`cls == "P"`) then 6 ruled ones (`cls == "R"`). 15% of 14000 is
# 2100 pairs: four in five go to the plain stories (1680 = 35 x 48) and one
# in five to the ruled ones (420 = 6 x 70). Origin variants are gone, so the
# sampling argument below no longer applies: the two numbers now pin only
# the equal shares inside each pool. The comment below is history.
# Re-measured 2026-09-19 (Task 9, spec section 7 ruling A): `BIG` is now a
# FIXED literal, not `275 * len(propagation.trainable_scenarios())`. Scaling
# by pool size stopped being safe once the pool split into two differently
# weighted sub-pools (spec section 6's selection loop gives ruled stories
# roughly twice the plain per-story share, by design -- a fifth of pairs
# spread over six ruled stories versus four fifths over forty-eight plain
# ones): a pool-scaled BIG would silently drift the exact 33/66 draw counts
# the sampling argument below depends on, on every future pool change. BIG =
# 13200 deals shared_origin 1980 rows total: 1584 over the 48 plain stories
# (33 each) and 396 over the 6 ruled stories (66 each) -- confirmed by
# direct measurement against this build. Why 33 (and 66) and not 11: the
# variant-rendering check below is a sampling check. With 4 variants drawn
# uniformly, P(fewer than 3 distinct in n draws) = (6 * 2**n - 8) / 4**n,
# and a fifth variant only lowers it. At n=11 that is 0.3% per scenario and
# 7% across twenty-four -- a deterministic failure with correct data. At
# n=33 it is 7.0e-10 per scenario, 3.4e-8 across forty-eight; n=66 is
# smaller still.
BIG = 14000


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS plain-story rows and RULED_DRAWS ruled-story
    rows per story, not one uniform rate over the whole pool (spec
    section 7 ruling A: "within each pool every story gets an equal share",
    checked per pool, not across them). Re-measured 2026-09-19, Task 9.
    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, split on
    `Story.cls`."""
    pool = stories.trainable()
    plain = sum(1 for st in pool if st.cls == "P")
    ruled = sum(1 for st in pool if st.cls == "R")
    assert (plain, ruled) == (35, 6)
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * plain + RULED_DRAWS * ruled


def test_the_trainable_pool_exercises_every_issue_kind():
    """A kind absent from the curriculum is a kind the shared-origin rule was
    never taught over -- and `vocab.ISSUE_KINDS` is what the eval draws from.

    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`. Measured
    before the named edits, the 41 kept stories' victims cover all 16 kinds;
    three of them (Init:ErrImagePull, Init:ImagePullBackOff, Init:OOMKilled)
    rest on one victim each.
    """
    seen = {v.issue for st in stories.trainable() for v in st.victims}
    missing = sorted(set(vocab.ISSUE_KINDS) - seen)
    assert not missing, f"no trainable story exercises: {missing}"


# The pool grew by group across Tasks 5–9 of the 2026-09-08 coverage plan.
# Twenty-four is what it held when the 0907 run failed deciders 1 and 5;
# forty-eight was that plan's end. On 2026-09-19 the training-targets fix
# merged six ruled stories on top (section 6 of its design): 48 to 54.
# On 2026-10-03 (Spec 4b-1) the family moved to `stories.trainable()`: the
# 12 X stories and runtime-class-removed left it, 54 to 41 (35 plain, then 6
# ruled). `multi` keeps `propagation.trainable_scenarios()`, still 54.
EXPECTED_POOL = 41


def test_the_trainable_pool_holds_the_planned_count():
    """The pool is pinned so a story cannot fall out of the tuple unseen."""
    pool = stories.trainable()
    assert len(pool) == EXPECTED_POOL
    assert len({st.key for st in pool}) == EXPECTED_POOL
    assert [st.cls for st in pool] == ["P"] * 35 + ["R"] * 6
    assert len(propagation.trainable_scenarios()) == 54


# One marker per exam read layout, and the fewest trainable scenarios that
# must teach it. A scenario counts once per layout when its read label
# starts the way the exam's does and any half of any of its origin
# variants carries the marker text. The floors are the spec's, and are
# minimums the measured count only needs to clear, not match; the measured
# counts after the coverage branch were node 13, deployment 7, events 4,
# storageclass 6, networkpolicy 6.
#
# Re-measured 2026-09-19 (Task 9, spec section 6): node 15, deployment 7,
# events 4, storageclass 6, networkpolicy 6. Ruled stories add node,
# storage-class and events layouts per spec section 7 rulings E/F; only
# "node" moved here because the two ruled node stories
# (`node-kubelet-halted`, `node-kubelet-unresponsive`) both teach that
# layout, while the ruled PVC and registry stories' layouts (storageclass,
# events) were already above their floor from the plain pool. All five
# floors below are unchanged and all five measured counts still clear them.
EXAM_LAYOUT_FLOORS = {
    "node": 13,
    "deployment": 4,
    "events": 4,
    "storageclass": 6,
    "networkpolicy": 6,
}


def _teaches_layout(p, layout: str) -> bool:
    label = p.origin_read[0]
    halves = [p.origin_read[1], p.healthy_origin_content]
    for broken, healthy in p.origin_variants:
        halves.extend((broken, healthy))
    if layout == "node":
        return (label.startswith("describe node ")
                and any("Conditions:" in h and "Taints:" in h for h in halves))
    if layout == "deployment":
        return (label.startswith("describe ") and label.endswith("(Deployment)")
                and any("Replicas:" in h for h in halves))
    if layout == "events":
        return label.startswith("get_events (cluster-wide, reason=")
    if layout == "storageclass":
        return (label.startswith("get_related storageclass")
                and any("bound in the last" in h for h in halves))
    if layout == "networkpolicy":
        return (label.startswith("get_related networkpolicy")
                and any("podSelector:" in h for h in halves))
    raise ValueError(layout)


def test_every_exam_layout_has_a_trained_floor():
    """The 0907 model read five exam layouts it had seen once or never in
    training. Each layout now has a floor: the fewest trainable scenarios
    that carry the exam's read shape. A drop below a floor is a regression
    the pool count cannot see, because it counts scenarios, not shapes."""
    short = {}
    for layout, floor in EXAM_LAYOUT_FLOORS.items():
        keys = sorted(p.key for p in propagation.trainable_scenarios()
                      if _teaches_layout(p, layout))
        if len(keys) < floor:
            short[layout] = (len(keys), floor, keys)
    assert not short, f"layouts under their floor (count, floor, keys): {short}"


def test_every_held_out_read_kind_has_a_trained_cousin():
    """On the 0905 wide probe the model said "shared" on 1 of 15 pairs for the
    three held-out origins whose discriminating read has no trained cousin of
    the same kind -- a kube-system Deployment describe, a StorageClass
    `get_related`, a NetworkPolicy `get_related` (one storage pair could not
    be graded; the one pair it got right was coredns-down). And it said
    "shared" on both halves for node-disk-pressure, the one node scenario
    whose read turns on a pressure condition line, 0 of 5. Trained cousins it
    had seen scored 5 of 5. So the gap is the read kind, and this test pins
    the fix: every read kind the exam uses must appear, in shape, in the
    trainable pool.

    Labels are matched by prefix, and the Deployment read by its suffix as
    well, so a renamed component or a namespace slug cannot satisfy the check
    by accident. The memory cousin is recognised by the condition line
    itself: `MemoryPressure` followed by `True`, whatever the column spacing.
    """
    pool = propagation.trainable_scenarios()
    labels = [p.origin_read[0] for p in pool]
    broken = [p.origin_read[1] for p in pool]
    missing = []
    if not any(label.startswith("describe kube-system/")
               and label.endswith("(Deployment)") for label in labels):
        missing.append("describe kube-system/... (Deployment)")
    if not any(label.startswith("get_related storageclass ") for label in labels):
        missing.append("get_related storageclass ...")
    if not any(label.startswith("get_related networkpolicy ") for label in labels):
        missing.append("get_related networkpolicy ...")
    if not any(re.search(r"MemoryPressure\s+True", content) for content in broken):
        missing.append("describe node with a MemoryPressure True condition")
    assert not missing, f"no trainable cousin for: {missing}"


def test_every_trainable_scenario_is_taught_equally(big_rows):
    """Equal shares are what make a constant answer chance-level: a scenario
    the curriculum shows twice as often is one the model can afford to answer
    by name.

    Re-measured 2026-09-19 (Task 9, spec section 6): checked WITHIN each
    pool separately now, not across the whole 54-scenario pool at once. The
    selection loop gives ruled stories roughly twice the plain per-story
    rate by design -- a fifth of pairs spread over six ruled stories versus
    four fifths over forty-eight plain ones (DRAWS=33 plain, RULED_DRAWS=66
    ruled at `BIG`, above) -- so a single across-pool equality check would
    fail on the intended shape, not a bug. Equal shares still hold inside
    each pool: every plain story gets the same count and every ruled story
    gets the same count.

    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, split on
    `Story.cls`, and the shares are pinned exactly: DRAWS for every plain
    story and RULED_DRAWS for every ruled one.
    """
    pool = stories.trainable()
    plain_keys = {st.key for st in pool if st.cls == "P"}
    ruled_keys = {st.key for st in pool if st.cls == "R"}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == plain_keys | ruled_keys, (
            f"{case}: {sorted((plain_keys | ruled_keys) ^ set(counts))}")
        plain_shares = {v for k, v in counts.items() if k in plain_keys}
        ruled_shares = {v for k, v in counts.items() if k in ruled_keys}
        assert plain_shares == {DRAWS}, f"{case}: plain shares {dict(counts)}"
        assert ruled_shares == {RULED_DRAWS}, f"{case}: ruled shares {dict(counts)}"


def test_no_shared_origin_cause_dominates_the_curriculum(big_rows):
    """The flattening the slice exists for.

    Measured on the four-scenario pool before this slice, at `BIG` = 11000
    (this test's size at the time): 15 distinct causes, top one 0.263 and top
    three 0.609. A model that
    answers the single most common cause on every shared-origin row was right a
    quarter of the time. The bar is 0.12 and 0.30 -- both of which the old pool
    failed by a wide margin, which is what makes this check non-vacuous.

    The size is named because top three moves with it: 0.633 at 5500, 0.618 at
    8000, 0.609 at 11000, 0.602 at 20000, as the tail keeps gaining distinct
    causes. Top one is stable at 0.263 across all four.

    Re-measured 2026-09-19 (Task 9: pool merge to 54 scenarios and `BIG`
    fixed at 13200, spec section 6/7 ruling A) -- 185 distinct causes, top
    one 0.0249, top three 0.0698. Both PVC-scoped ruled stories widen the
    tail further: their per-victim causes name the victim's own PVC
    (`f"PVC {pvc} (...)"`), so each ruled PVC draw can add several new
    distinct causes at once. The bar stays 0.12 and 0.30; the new pool
    clears both with more room than the old one did.

    Re-measured 2026-10-03 (Spec 4b-1: 41 stories, `BIG` = 14000).
    `none_of_these` is left out of the count: it is the answer "nothing in
    this workload's own lines says why", not a cause a model can name by
    rote, and the ceiling test in test_shared_origin_floor.py bounds it on
    its own. Measured: 97 distinct causes, top one 0.0665, top three
    0.1228. The bar stays 0.12 and 0.30.
    """
    causes = Counter(cause
                     for e in big_rows if e.case == "shared_origin"
                     for cause in e.meta["expected"].values()
                     if cause != contract.NONE_OF_THESE)
    total = sum(causes.values())
    top = causes.most_common(3)
    assert top[0][1] / total <= 0.12, (
        f"{top[0][0]!r} is {top[0][1] / total:.3f} of all shared-origin causes")
    assert sum(n for _c, n in top) / total < 0.30, (
        f"top three are {sum(n for _c, n in top) / total:.3f} of all causes")


def test_one_training_only_separate_prompt_exists_at_the_frozen_seed():
    """The `separate` label is pinned three ways (a rules unit test, a scorer
    unit test, and this one): at least one real training prompt must reach
    `label == "separate"`, every workload in it confirmed with a cause of
    its own, or the label exists only in isolated unit tests and never in
    a prompt a model actually trains on. `separate` stays at 0 in the exam
    (R42), so this prompt has to live in the training split.

    2026-09-26 (faithful prompts): the first such row used to hold two
    `worker-containerd-stop` workloads on two different nodes. Job-1 rows
    now rotate over 17 entries, so the rng stream moved, and the new
    `pvc-unbound-unschedulable` entry joined the `multi` pool. The first
    `separate` row now holds three workloads: one decided on its own PVC
    and two on two different NotReady nodes. The check reads "every cause
    is distinct" instead of "two nodes".

    2026-09-26 (faithful prompts): the node list grew to five and a `multi`
    row now redraws any draw that shares a workload, a node or a claim with
    one already in the row, so the rng stream moved again. The first
    `separate` row now holds four workloads: one decided on its own PVC and
    three on three different nodes. The self-pair row (two
    `worker-containerd-stop` workloads) is also `separate`. It comes last
    in this split, and the training build drops it: one of its workloads
    (`worker-containerd-stop:media/scheduler`) is an exam row's identity.
    """
    train, _ = generate.split(generate.generate(seed=17, size=8000), seed=17)
    separate_rows = [e for e in train
                     if e.meta.get("case") == "multi" and e.meta.get("label") == "separate"]
    assert separate_rows, "no training-only separate-label multi prompt at seed=17"
    row = separate_rows[0]
    workloads = row.meta["workloads"]
    # 2026-09-26 (faithful prompts): see the docstring. 2 -> 3.
    # 2026-09-26 (faithful prompts): five nodes and clash redraws moved the
    # rng stream; see the docstring. 3 -> 4.
    assert len(workloads) == 4
    for meta in workloads.values():
        assert meta["decided"] is True
    # decided_evidence is a template sentence ("Ready condition is False
    # now") shared by every worker-containerd-stop draw regardless of which
    # node it lands on, so it carries no node identity. decided_cause does
    # ("node worker-2 (NotReady)" vs. "node worker-3 (NotReady)" vs.
    # "PVC data-0 (MissingStorageClass)") -- the per-workload field this
    # assert actually needs.
    causes = {meta["decided_cause"] for meta in workloads.values()}
    assert len(causes) == len(workloads), "every workload must have its own cause"
