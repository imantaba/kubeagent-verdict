"""Teaching shared-origin reasoning without teaching the test.

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

That closes the obvious shortcut. This module exists mostly for the second,
which is not obvious: `multi` builds its reads per constituent
(`_reads(e, n)[:2]`), so before this change a cluster-scoped read at the head
of the list appeared in shared-origin rows and NOWHERE else. Train the
positive case alone and "an origin read is present" separates the two classes
perfectly — the model would pass the probe on the prompt's shape without
reading a word of the evidence, and every rate on the slice would improve for
a reason that is not the skill. The counterweight is a negative case: `multi`
rows carrying the SAME origin read label with content showing the component
HEALTHY, where "separate reasons" is still the right answer. Same shape, both
answers, so only the evidence separates them.

Two residuals, asserted below rather than claimed away. The counterweight is
lighter than the generator makes it look: `drop_held_out` removes about a
third of the `multi` counter-examples and none of the `shared_origin` rows,
so the emitted ~48/52 reaches the optimizer as ~62/38. And the exam cannot
detect this shortcut even now — seven of the ten `shared_origin_probe` rows
carry a read label that appears in none of the other 243, so label-matching
alone passes both halves of decider 5. Fixing that is an exam-side change and
does not belong in this module.
"""

import hashlib
import json
import re
from collections import Counter

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import generate, propagation

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
    group; a `shared_origin` row is built from the train-only propagation
    pool the exam never touches. So `multi` loses about a third of its
    origin-read rows here and `shared_origin` loses none.

    Per-row invariants stay on `rows`: it is a superset of this pile, so
    checking it is the stronger check, not the weaker one.
    """
    train, val = generate.split(rows, seed=SEED)
    test = generate.test_set()
    return generate.drop_held_out(train, test) + generate.drop_held_out(val, test)


def _by_case(rows, case):
    return [e for e in rows if e.case == case]


# ------------------------------------------------- the held-out origin split

def test_a_trainable_scenario_pool_exists():
    assert propagation.trainable_scenarios()


def test_no_trainable_origin_is_an_eval_origin():
    """The whole point. A shared key would make the probe a memory test."""
    train = {p.key for p in propagation.trainable_scenarios()}
    held = {p.key for p in propagation.all_scenarios()}
    assert train & held == set()


def test_no_trainable_scenario_reuses_an_eval_answer_string():
    """Disjoint keys are not enough — the probe grades the cause STRING.

    Two scenarios could carry different keys and the same `shared_cause`, and
    then the model has seen the graded answer verbatim while `drop_held_out`
    reports a clean split, because it keys on group identity and never looks
    at the text.
    """
    held = {p.shared_cause for p in propagation.all_scenarios()}
    held |= {p.distractor_cause for p in propagation.all_scenarios()}
    for p in propagation.trainable_scenarios():
        assert p.shared_cause not in held, p.key
        assert p.distractor_cause not in held, p.key


def test_every_trainable_scenario_carries_a_healthy_origin_read():
    """The negative case's raw material: the same read, component healthy."""
    for p in propagation.trainable_scenarios():
        assert p.healthy_origin_content.strip(), p.key


def test_trainable_scenarios_obey_every_rule_the_eval_table_obeys():
    for p in propagation.trainable_scenarios():
        assert p.blast_radius in propagation.BLAST_RADII, p.key
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p.key), p.key
        assert 2 <= len(p.victims) <= 4, p.key
        assert p.shared_verdict != "attributed", p.key
        assert p.confidence in ("high", "medium", "low"), p.key
        for v in p.victims:
            assert v.issue in vocab.ISSUE_KINDS, f"{p.key}: {v.issue}"
            assert v.pass_confidence in ("high", "medium", "low"), p.key
        locals_ = [v.local_cause for v in p.victims]
        assert len(set(locals_)) == len(locals_), f"{p.key}: duplicate decoys"


def test_every_trainable_scenario_declares_at_least_four_origin_variants():
    """Four literal strings per scenario is a lookup; several renderings of one
    relation is not. Variant 0 must be the legacy pair because `multi`'s
    healthy-origin read renders `healthy_origin_content` without going through
    the draw, and the pool invariants below read `origin_read[1]` /
    `healthy_origin_content` directly -- all of them must keep showing content
    the model has actually seen.
    """
    for p in propagation.trainable_scenarios():
        assert len(p.origin_variants) >= 4, f"{p.key}: {len(p.origin_variants)}"
        assert p.origin_variants[0] == (p.origin_read[1], p.healthy_origin_content), (
            f"{p.key}: variant 0 is not the legacy pair")


def test_every_variant_first_line_is_literal_and_unique_within_its_scenario():
    """Two tests and one measurement identify a rendered variant by its first
    line, so a first line carrying `{ns}` or repeated across variants would
    make them silently unable to tell variants apart.
    """
    for p in propagation.trainable_scenarios():
        firsts = []
        for broken, healthy in p.origin_variants:
            for content in (broken, healthy):
                first = content.split("\n")[0]
                assert "{" not in first, f"{p.key}: placeholder in {first!r}"
                assert first.strip(), f"{p.key}: empty first line"
                firsts.append(first)
        assert len(set(firsts)) == len(firsts), f"{p.key}: duplicate first line"


def test_every_trainable_scenario_names_its_state_in_words():
    """The 0.5 in-distribution score decomposes into two scenarios read and two
    constant. The two read are separated by a lexical state token; the two
    constant by a quantity, and the UNIT ablation showed making the units
    consistent moved nothing. So a discriminator that is only a number is a
    discriminator two of four scenarios demonstrably did not read.

    Necessary and demonstrably not sufficient: `internal-ca-expired` already
    satisfies this and still failed. The other half -- "the token is not buried
    in a numeric phrase" -- is authoring guidance in the module docstring,
    because no honest test expresses it.
    """
    for p in propagation.trainable_scenarios():
        broken_token, healthy_token = p.origin_state
        assert broken_token.strip(), f"{p.key}: no broken state token"
        assert healthy_token.strip(), f"{p.key}: no healthy state token"
        assert re.search(r"[A-Za-z]", broken_token), f"{p.key}: {broken_token!r}"
        assert re.search(r"[A-Za-z]", healthy_token), f"{p.key}: {healthy_token!r}"
        for broken, healthy in p.origin_variants:
            assert broken_token in broken, f"{p.key}: {broken_token!r} missing"
            assert healthy_token not in broken, f"{p.key}: {healthy_token!r} in a broken read"
            assert healthy_token in healthy, f"{p.key}: {healthy_token!r} missing"
            assert broken_token not in healthy, f"{p.key}: {broken_token!r} in a healthy read"


_SCOPE_FOR_RADIUS = {"cluster": None, "node": "node", "namespace": "ns"}


def test_blast_radius_and_scope_field_agree():
    """A node-scoped origin is only coherent if every victim is on that node.
    `_propagation_names` pins the field named by `scope_field`, so a radius
    that disagrees with it asserts a blast radius its own inventory
    contradicts.
    """
    for p in propagation.trainable_scenarios():
        assert p.scope_field == _SCOPE_FOR_RADIUS[p.blast_radius], p.key


def test_no_two_trainable_scenarios_share_an_answer_string():
    """A cause string reused across scenarios is a lookup key spanning both."""
    seen = {}
    for p in propagation.trainable_scenarios():
        for field, value in (("shared_cause", p.shared_cause),
                             ("distractor_cause", p.distractor_cause)):
            assert value not in seen, f"{p.key}.{field} repeats {seen[value]}"
            seen[value] = f"{p.key}.{field}"


def test_no_two_trainable_scenarios_share_a_local_cause():
    """Same reason, on the decoy half's answers."""
    seen = {}
    for p in propagation.trainable_scenarios():
        for v in p.victims:
            assert v.local_cause not in seen, (
                f"{p.key}: local_cause repeats {seen[v.local_cause]}")
            seen[v.local_cause] = p.key


def test_pass_confidence_varies_within_every_trainable_scenario():
    """Guidance in the module docstring until now. With sixteen new scenarios
    written at once, "vary the confidence" as guidance will not hold, and a
    scenario whose victims all carry one grade reopens the confidence-copy
    shortcut the docstring says is closed.
    """
    for p in propagation.trainable_scenarios():
        grades = {v.pass_confidence for v in p.victims}
        assert len(grades) > 1, f"{p.key}: every victim carries {grades}"


def test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half():
    """The mechanised half of constraint 10.

    On the decoy half the origin read shows the component healthy. A victim
    read that still carries the scenario's broken state token contradicts it
    in the same prompt, and the row teaches nothing except that the evidence
    disagrees with itself. Deciding whether a read "asserts the origin is
    broken" is a judgment about English and is not mechanised; the token is
    the case where it is mechanical, and it is checked.
    """
    for p in propagation.trainable_scenarios():
        broken_token = p.origin_state[0]
        if not broken_token:
            continue
        for v in p.victims:
            if broken_token not in v.read[1]:
                continue
            assert v.healthy_read_content, (
                f"{p.key}: a victim read carries {broken_token!r} with no healthy swap")
            assert broken_token not in v.healthy_read_content, (
                f"{p.key}: the healthy swap still carries {broken_token!r}")


_QUANTITY = re.compile(r"\d+[A-Za-z]*")


def _canonical_rendering(content: str) -> str:
    """A variant with its quantities and its line order taken away.

    Every number-plus-unit token collapses to `N` and the lines are sorted, so
    two renderings that differ only in their numbers -- or only in the order
    they present the same fields -- reduce to the same string. Two genuinely
    different renderings do not.
    """
    return "\n".join(sorted(
        re.sub(r"\s+", " ", _QUANTITY.sub("N", line)).strip()
        for line in content.split("\n") if line.strip()))


def test_no_two_variants_are_the_same_rendering_with_different_numbers():
    """The variant axis is renderings, not numbers.

    A scenario can satisfy the count check, the first-line check and the state
    check with four copies of one template carrying different quantities --
    which is exactly the lookup the variant axis exists to defeat, dressed as
    diversity. This is the mechanical half of "vary the rendering". The rest
    stays authoring guidance in the module docstring, because judging whether
    two English sentences say the same thing in different words is not a test.

    Not vacuous, and not hypothetically: `internal-ca-expired` and
    `shared-dependency-scaled-to-zero` both failed this at `a861e91`, on both
    halves, after passing every other test in this file and a full task
    review. One was the same three-line template with two numbers swapped; the
    other was those lines reordered. Sorting is what catches the second, and
    collapsing the unit letter along with the digits is what catches the first
    -- `2h` against `41m` leaves `h` against `m` if only digits are stripped,
    and the collision is missed.
    """
    for p in propagation.trainable_scenarios():
        for half, which in ((0, "broken"), (1, "healthy")):
            seen = {}
            for i, pair in enumerate(p.origin_variants):
                form = _canonical_rendering(pair[half])
                assert form not in seen, (
                    f"{p.key}: {which} variant {i} is variant {seen[form]} with "
                    f"different numbers or a different line order")
                seen[form] = i


def test_no_trainable_scenario_text_carries_a_banned_identifier_shape():
    banned = (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"https?://"),
              re.compile(r"kubeconfig", re.IGNORECASE), re.compile(r"/home/"),
              re.compile(r"@"))
    for p in propagation.trainable_scenarios():
        for v in p.victims:
            assert isinstance(v.network_policies, tuple), (
                f"{p.key}: network_policies must be a tuple, not "
                f"{type(v.network_policies).__name__} -- a bare str is truthy, "
                "survives the `or ()`, and would be joined character by "
                "character, so every pattern below would silently miss it")
        blob = "\n".join([p.origin, p.shared_cause, p.shared_reason,
                          p.distractor_cause, p.distractor_reason, p.rationale,
                          p.remedy, p.origin_read[0], p.origin_read[1],
                          p.healthy_origin_content,
                          p.origin_state[0], p.origin_state[1], p.notes]
                         + [f"{b}\n{h}" for b, h in p.origin_variants]
                         + [f"{v.reason}\n{v.evidence}\n{v.log_cause}\n"
                            f"{v.local_cause}\n{v.local_reason}\n"
                            f"{v.read[0]}\n{v.read[1]}\n{v.healthy_read_content}\n"
                            + "\n".join(str(x) for x in (v.network_policies or ()))
                            for v in p.victims])
        for pat in banned:
            assert not pat.search(blob), f"{p.key}: {pat.pattern}"


def test_a_scenario_with_variants_renders_more_than_one_of_them():
    """The mechanism, exercised on a scenario built for the test.

    Asserted here rather than only on the real pool because the real pool's
    scenarios are added in later commits, and a draw site that silently
    ignored `origin_variants` would otherwise land green.
    """
    import dataclasses
    import random

    from kubeagent_verdict.dataset import cases

    base = propagation.trainable_scenarios()[0]
    variants = tuple(
        (f"state: broken variant {i}\n{base.origin_read[1]}",
         f"state: healthy variant {i}\n{base.healthy_origin_content}")
        for i in range(4))
    p = dataclasses.replace(base, origin_variants=variants)

    seen = set()
    for salt in range(40):
        e = cases.shared_origin(p, random.Random(salt), victims=2)
        seen |= {i for i, (b, _h) in enumerate(variants)
                 if b.split("\n")[0] in e.user}
    assert len(seen) > 1, f"only variant(s) {seen} ever rendered"


def test_a_pair_built_from_one_salt_draws_the_same_variant():
    """`generate.py:156-159` spends one salt twice, so the twins replay one
    stream. The draw sits before the `healthy` branch precisely so both halves
    reach it in the same RNG state -- otherwise a pair could contrast variant
    2's broken blob against variant 0's healthy one, which is two changes at
    once and no longer isolates the origin's state.
    """
    import dataclasses
    import random

    from kubeagent_verdict.dataset import cases

    base = propagation.trainable_scenarios()[0]
    variants = tuple(
        (f"state: broken variant {i}\n{base.origin_read[1]}",
         f"state: healthy variant {i}\n{base.healthy_origin_content}")
        for i in range(4))
    p = dataclasses.replace(base, origin_variants=variants)

    for salt in range(40):
        one = cases.shared_origin(p, random.Random(salt), victims=2)
        other = cases.shared_origin_decoy(p, random.Random(salt), victims=2)
        drawn = [i for i, (b, _h) in enumerate(variants)
                 if b.split("\n")[0] in one.user]
        assert len(drawn) == 1, f"salt {salt}: {len(drawn)} broken variants matched"
        assert variants[drawn[0]][1].split("\n")[0] in other.user, (
            f"salt {salt}: the twin drew a different variant")


def test_a_scenario_without_variants_renders_exactly_what_it_did_before():
    """The eval six declare none and must consume the RNG identically."""
    import random

    from kubeagent_verdict.dataset import cases

    for p in propagation.all_scenarios():
        assert p.origin_variants == (), p.key
        e = cases.shared_origin_probe(p, random.Random(3))
        assert p.origin_read[1].split("\n")[0] in e.user, p.key


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
    train = {p.key for p in propagation.trainable_scenarios()}
    for e in _by_case(rows, "shared_origin"):
        assert e.meta["origin"] in train, e.meta["origin"]


def test_multi_survives_as_the_majority_of_multi_workload_rows(kept):
    """Decider 5 has two halves and this change can only break the other one.

    `false_shared_rate` is 0.0 today. If shared origins stop being the
    minority answer the model swings to claiming them everywhere, and the
    scoreboard trades one failure for its mirror.

    Measured on the kept pile, not the generator's output: `drop_held_out`
    takes `multi` rows and no `shared_origin` rows, so a mix that looks
    safely majority-`multi` as emitted is not necessarily majority-`multi`
    by the time it reaches the optimizer.
    """
    assert len(_by_case(kept, "multi")) > len(_by_case(kept, "shared_origin"))


# ------------------------------------------------- the structural-cue killer

def _origin_labels(rows, *cases):
    return {e.meta["origin_read_label"] for e in rows
            if e.case in cases and "origin_read_label" in e.meta}


# These two replace a single assertion that compared `shared_origin` against
# `multi` on the KEPT pile and demanded the sets be equal. That assertion was
# written before the decoy twin existed, and the twin superseded its premise:
# it read the surviving `multi` negatives as the only thing standing between a
# read label and a free giveaway, when the pair already carries every label
# under both answers. Its docstring said a label the filter strips from every
# `multi` row "is a giveaway in the data the model reads". Measured, it is not
# — the twin survives the cull holding the same label and the opposite answer.
#
# It also could not have survived this branch. The negative budget is fixed at
# ~30 rows however large the pool grows, the cull takes about 30% of them, and
# the plan ends at twenty scenarios — 1.5 negatives each before the cull. The
# equality first went red at eleven scenarios, and no arrangement of the data
# fixes it: raising the negatives to ~4 per scenario would mean making nearly
# every `multi` row a negative, which is the class balance
# `test_the_generator_emits_the_two_classes_near_evenly` exists to hold.
#
# So the claim is narrowed to the two things that are separately true, each
# checked where it is actually decided. Neither is vacuous: the first goes red
# if the rotation stops offering some scenario a negative, the second if the
# cull ever takes half a pair or the decoy stops being emitted.

def test_the_emitter_offers_every_origin_read_under_both_answers(rows):
    """The emitter's half, checked before the cull, where it is the emitter's.

    Every trainable origin read must be offered under a shared answer AND
    under an independent one. This is the rotation's contract and it stays
    satisfiable as the pool grows: the negatives cover the pool as long as
    there is at least one per scenario. Asserting it on the kept pile instead
    would be asserting the cull's behaviour under the emitter's name.
    """
    shared = _origin_labels(rows, "shared_origin")
    negatives = _origin_labels(rows, "multi")
    assert shared, "no shared_origin row carries an origin read"
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert shared == negatives


def test_the_cull_never_leaves_an_origin_read_under_only_shared_answers(kept):
    """The cue guarantee proper, in the data the model actually reads.

    A read label is a giveaway only if, after the cull, it appears under a
    shared answer and under no independent one ANYWHERE. Both independent
    classes count: the `shared_origin_decoy` twin, which carries the label with
    per-workload causes, and the surviving `multi` negatives. Counting only the
    latter is what made the assertion this replaces go red over a label that
    was never a giveaway.

    This is what `drop_held_out` taking pairs whole buys, and nothing else in
    the suite checks that it still does.
    """
    shared = _origin_labels(kept, "shared_origin")
    independent = _origin_labels(kept, "shared_origin_decoy", "multi")
    assert shared, "no shared_origin row survived the cull"
    giveaways = sorted(shared - independent)
    assert not giveaways, (
        f"{len(giveaways)} origin read label(s) survive under a shared answer "
        f"and under no independent one: {giveaways}")


def _independent_share(rows):
    """Independent-answer share among rows that carry an origin read.

    `shared_origin_decoy` counts on the independent side and MUST: it is the
    counter-example class now. Leaving it out kept this instrument reading
    0.386 while the pile it measures had moved to 0.619 -- passing, and
    blind to the 169 rows the change was about.
    """
    shared = len(_by_case(rows, "shared_origin"))
    independent = (len(_by_case(rows, "shared_origin_decoy"))
                   + len([e for e in _by_case(rows, "multi")
                          if "origin_read_label" in e.meta]))
    return independent / (shared + independent)


def test_the_generator_emits_the_two_classes_near_evenly(rows):
    """What the EMITTER controls, and it is no longer a coin flip: 0.657.

    Two sources feed the independent side now. The paired half is exact by
    construction -- every `shared_origin` row is emitted with a
    `shared_origin_decoy` twin from the same salt, so those two contribute
    169/169 and cannot drift. On top of that sit the surviving
    every-third-`multi` negatives, which have no positive counterpart, and
    they are the whole of the lean.

    Kept deliberately rather than balanced away: they are a DIFFERENT
    counter-example -- a healthy origin read over arbitrary victims, where
    the pair holds the victims fixed -- so removing them to reach 0.5 would
    trade coverage for a rounder number. The band is stated where the pile
    actually sits and still fails both degenerate ends.
    """
    assert 0.55 <= _independent_share(rows) <= 0.75


def test_the_trained_pile_is_not_one_sided_among_origin_read_rows(kept):
    """What the MODEL reads, which is the number that decides what it learns.

    A 9:1 split is a prior, not a cue kill. This is the assertion the module
    docstring's argument actually depends on, and the one that was missing.

    It used to record a ~62/38 lean toward the SHARED answer and name the
    remedy it had not paid for: "closing the gap the rest of the way means
    emitting more counter-examples, which moves dataset bytes". That was
    paid. `shared_origin_decoy` emits one counter-example per positive from
    the same salt, and the lean now runs the other way -- 0.619 toward the
    independent answer, from the `multi` negatives that have no twin.

    The direction matters less than what it is no longer confounded with.
    Before, the two classes differed in their victims as well as in their
    read, so symptom coherence separated them without reading the origin at
    all; the paired half holds the victims byte-identical, so it cannot.
    `drop_held_out` splits on group keys and both halves of a pair share
    one, so it takes pairs whole and the 169/169 core survives the filter
    exactly -- the residual lean is the negatives, not the filter.

    The band still fails loudly at the state this module was written to end
    — 1.00/0.00, no counter-examples at all — and now also fails if the
    pairing ever emits one-sidedly.
    """
    share = _independent_share(kept)
    assert 0.55 <= share <= 0.70, f"kept-pile independent share {share:.3f}"


def test_a_negative_multi_row_shows_the_component_healthy(rows):
    """Same label, opposite content — otherwise the label is still the answer."""
    healthy = {p.origin_read[0]: p.healthy_origin_content
               for p in propagation.trainable_scenarios()}
    broken = {p.origin_read[1] for p in propagation.trainable_scenarios()}
    seen = 0
    for e in _by_case(rows, "multi"):
        if "origin_read_label" not in e.meta:
            continue
        seen += 1
        assert e.meta["origin_healthy"] is True
        content = healthy[e.meta["origin_read_label"]]
        assert content.split("\n")[0] in e.user
        for b in broken:
            assert b.split("\n")[0] not in e.user
    assert seen


def test_a_negative_multi_row_still_says_separate_reasons(rows):
    for e in _by_case(rows, "multi"):
        assert propagation.SEPARATE_REASONS in e.assistant


def test_a_shared_origin_training_row_never_says_separate_reasons(rows):
    for e in _by_case(rows, "shared_origin"):
        assert propagation.SEPARATE_REASONS not in e.assistant


def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    for e in _by_case(rows, "shared_origin"):
        causes = set(e.meta["expected"].values())
        assert len(causes) == 1, e.meta["origin"]


# ------------------------------------------------------ the eval must not move

def test_the_eval_set_is_two_hundred_and_sixty_three_rows():
    """253 until `shared_origin_decoy_probe` appended its ten.

    This test exists so the TRAINING half of the shared-origin work cannot
    move the exam by accident — a curriculum change that grows the test set
    invalidates every banked scoreboard silently. It does not forbid moving
    the exam on purpose; the decoy slice did that, in its own commit, with
    `tests/test_shared_origin_decoy_probe.py` proving the training set stayed
    byte-identical across the change.
    """
    assert len(generate.test_set()) == 263


# The first 253 rows, byte for byte, as every scoreboard since 0830 has seen
# them. This pin has never moved and must not: it is what makes a number on
# the 253 comparable across runs. The row count above cannot see a rewrite
# that keeps the count; this can.
FROZEN_253_SHA256 = "9f5fb341f620306d1d003d1617da613139f7bccf03cec768bd78539df75abb96"

# The whole exam, 253 plus the ten `shared_origin_decoy_probe` rows. First
# captured on `main` @ `ee2980e` as `e8cbb549…b49de`; 0902 and 0905 were
# scored against that set in one go, 0901 covered the same rows as two runs
# (which is why its paired join reported `unpaired`), and 0830 predates the
# ten decoy rows entirely. Re-pinned on 2026-09-05 when `healthy_evidence`
# corrected the two node-disk-pressure decoy rows (257 and 262), whose
# inventory named the disk-pressure taint in a world whose node read showed
# none: those two rows changed in one line each, the other 261 did not, and
# the training and validation rows regenerated byte-identical. So a decoy
# number measured before that date is not comparable to one measured after
# it, and numbers on the 253 are. A change that moves this hash is wrong
# unless it means to retire that comparison, and says so here.
EVAL_SET_SHA256 = "9d59a8f881862bc9035605d206a2cc9269bf5b59300f8fb8af3a030aff04f1b9"


def _digest(rows) -> str:
    blob = json.dumps([generate.to_row(e) for e in rows],
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used():
    assert _digest(generate.test_set()[:253]) == FROZEN_253_SHA256, (
        "the frozen 253 moved; every banked scoreboard comparison is now void")


def test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used():
    assert _digest(generate.test_set()) == EVAL_SET_SHA256, (
        "the exam moved; decoy numbers measured before this are no longer comparable")


def test_no_eval_row_comes_from_the_trainable_pool():
    train = {p.key for p in propagation.trainable_scenarios()}
    for e in generate.test_set():
        assert e.meta.get("origin") not in train
        for part in e.group.split("+"):
            assert not any(f"propagation:{k}:" in part for k in train), part


def test_the_probe_still_draws_only_held_out_origins():
    held = {p.key for p in propagation.all_scenarios()}
    probes = [e for e in generate.test_set() if e.case == "shared_origin_probe"]
    assert len(probes) == 10
    for e in probes:
        assert e.meta["origin"] in held


def test_training_still_contaminates_nothing(rows):
    test = generate.test_set()
    train, val = generate.split(rows, seed=SEED)
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    held = {part for e in test for part in e.group.split("+")}
    for e in kept:
        assert not any(part in held for part in e.group.split("+")), e.group


BIG = 11000  # 0.54s; 22 rows of each half per scenario at 20 scenarios.
             # Not 5500: 11 draws from 4 variants shows <3 distinct 0.3% of
             # the time per scenario, 5.7% across twenty -- a deterministic
             # failure with correct data. 22 draws puts it at 1.4e-6 per
             # scenario, 2.9e-5 across twenty.


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_the_trainable_pool_exercises_every_issue_kind():
    """A kind absent from the curriculum is a kind the shared-origin rule was
    never taught over -- and `vocab.ISSUE_KINDS` is what the eval draws from.
    """
    seen = {v.issue for p in propagation.trainable_scenarios() for v in p.victims}
    missing = sorted(set(vocab.ISSUE_KINDS) - seen)
    assert not missing, f"no trainable scenario exercises: {missing}"


def test_the_trainable_pool_holds_twenty_scenarios():
    """Four scenarios is what the pool held when it scored 0.5 in-distribution
    and 0.1 out. The count is asserted so shrinking it back is a deliberate
    edit rather than a merge artefact.
    """
    assert len(propagation.trainable_scenarios()) == 20


def test_every_trainable_scenario_is_taught_equally(big_rows):
    """Equal shares are what make a constant answer chance-level: a scenario
    the curriculum shows twice as often is one the model can afford to answer
    by name.
    """
    keys = {p.key for p in propagation.trainable_scenarios()}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == keys, f"{case}: {sorted(keys ^ set(counts))}"
        assert len(set(counts.values())) == 1, f"{case}: uneven shares {dict(counts)}"


def test_every_trainable_scenario_renders_at_least_three_origin_variants(big_rows):
    """Declaring four variants is not the same as rendering them. If the draw
    were keyed on something constant per scenario, every row would carry
    variant 0 and the whole mechanism would be inert while its own unit test
    still passed.

    The bar is 3 of 4 rather than 4 of 4 because the draw is uniform and
    random: this is a sampling check, and its strength is a function of `BIG`.
    At 22 draws a correct pool trips it about once in 35,000 runs across the
    whole pool. Lowering `BIG` is not a free speed-up -- at 11 draws it is 5.7%,
    and the failure names a scenario whose data is fine.
    """
    by_key = {p.key: p for p in propagation.trainable_scenarios()}
    seen = {k: set() for k in by_key}
    for e in big_rows:
        if e.case != "shared_origin":
            continue
        p = by_key[e.meta["origin"]]
        for i, (broken, _healthy) in enumerate(p.origin_variants):
            if broken.split("\n")[0] in e.user:
                seen[p.key].add(i)
    thin = {k: sorted(v) for k, v in seen.items() if len(v) < 3}
    assert not thin, f"scenarios rendering fewer than 3 variants: {thin}"


def test_no_shared_origin_cause_dominates_the_curriculum(big_rows):
    """The flattening the slice exists for.

    Measured on the four-scenario pool before this slice, at this test's own
    `BIG`: 15 distinct causes, top one 0.263 and top three 0.609. A model that
    answers the single most common cause on every shared-origin row was right a
    quarter of the time. The bar is 0.12 and 0.30 -- both of which the old pool
    failed by a wide margin, which is what makes this check non-vacuous.

    The size is named because top three moves with it: 0.633 at 5500, 0.618 at
    8000, 0.609 here, 0.602 at 20000, as the tail keeps gaining distinct causes.
    Top one is stable at 0.263 across all four.
    """
    causes = Counter(cause
                     for e in big_rows if e.case == "shared_origin"
                     for cause in e.meta["expected"].values())
    total = sum(causes.values())
    top = causes.most_common(3)
    assert top[0][1] / total <= 0.12, (
        f"{top[0][0]!r} is {top[0][1] / total:.3f} of all shared-origin causes")
    assert sum(n for _c, n in top) / total < 0.30, (
        f"top three are {sum(n for _c, n in top) / total:.3f} of all causes")
