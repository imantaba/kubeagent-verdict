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
alone clears job 3 and the decoy rate. Fixing that is an exam-side change and
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


def test_every_trainable_scenario_has_at_least_three_victims():
    """The 0907 model failed decider 5 on three-victim decoy halves it had
    never seen: 15 of 24 trainable scenarios held two victims, so the
    generator could only ever render two. Three is the floor now."""
    thin = {p.key: len(p.victims) for p in propagation.trainable_scenarios()
            if len(p.victims) < 3}
    assert thin == {}, f"scenarios with fewer than three victims: {thin}"


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


# The exam's six reads use real kubectl layouts. These markers, with the
# exam's own spacing, say "this half is laid out the way the exam is".
_EXAM_LAYOUT_MARKERS = {
    "node-pid-pressure": ("Conditions:\n", "Taints:  "),
    "kube-proxy-degraded": ("Conditions:\n", "Taints:  "),
    "csi-node-driver-crashed": ("Conditions:\n", "Taints:  "),
    "node-runtime-restarting": ("Conditions:\n", "Taints:  "),
    "node-clock-skew": ("Conditions:\n", "Taints:  "),
    "node-conntrack-full": ("Conditions:\n", "Taints:  "),
    "pod-identity-webhook-down": ("Replicas:  ", "Pods:      ", "Last log:  "),
    "shared-dependency-scaled-to-zero": ("Replicas:  ", "Pods:      ",
                                         "Last log:  "),
    "namespace-egress-proxy-down": ("Replicas:  ", " total | ", "Pods:      ",
                                    "Last log:  "),
    "storageclass-pool-retired": ("provisioner: ",
                                  "PersistentVolumes bound in the last 20m: "),
    "networkpolicy-egress-allowlist-stale": ("podSelector: ", "policyTypes: ",
                                             "\negress: ", "pods selected: "),
}


def test_the_eleven_named_scenarios_carry_an_exam_layout_variant():
    """The 0907 model read `describe node` in the exam and had never seen a
    `Conditions:` table with a `Taints:` line in training. Each scenario
    named here shares a read kind with one of the six exam origins, and
    must carry at least one variant laid out the way the exam is."""
    by_key = {p.key: p for p in propagation.trainable_scenarios()}
    missing = []
    for key, markers in _EXAM_LAYOUT_MARKERS.items():
        halves = [h for pair in by_key[key].origin_variants for h in pair]
        if not any(all(m in half for m in markers) for half in halves):
            missing.append(key)
    assert missing == [], f"scenarios without an exam-layout variant: {missing}"


def test_node_memory_pressure_spells_no_taint_the_way_kubectl_does():
    """kubectl prints `Taints:  <none>`. The record said `Taints:  none`."""
    p = {q.key: q for q in propagation.trainable_scenarios()}["node-memory-pressure"]
    assert "Taints:  <none>" in p.healthy_origin_content
    assert "Taints:  none" not in p.healthy_origin_content
    healthy_halves = "\n".join(h for _b, h in p.origin_variants)
    assert "Taints:  none" not in healthy_halves
    assert p.origin_variants[0][1] == p.healthy_origin_content


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

    That case-family share is not the share of multi-workload rows whose
    graded answer actually claims a shared origin. That answer-level share
    is about 7 of every 100 -- 214 of 3,128 at build size 8000 (214 of
    3,126 before the 2026-09-24 case-mix change), counted on the same kept
    pile the numbers above come from -- and this test does not measure it
    and does not guard it.
    """
    shared = len(_by_case(kept, "shared_origin"))
    separate = (len(_by_case(kept, "multi"))
                + len(_by_case(kept, "shared_origin_decoy")))
    assert shared, "the filter took every shared_origin row"
    share = shared / (shared + separate)
    assert share <= 0.40, (
        f"shared_origin case family is {share:.3f} of multi-workload rows")


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
#
# 2026-09-08: the emitter's half runs at BIG now; its docstring says why.

def test_the_emitter_offers_every_origin_read_under_both_answers(big_rows):
    """The emitter's half, checked before the cull, where it is the emitter's.

    Every trainable origin read must be offered under a shared answer AND
    under an independent one. The negatives rotate over the pool one `multi`
    row in three, so the rotation completes only when the build holds at
    least three `multi` rows per scenario. `SIZE` stopped holding that at
    thirty-one scenarios; `BIG` holds it many times over. Asserting it on
    the kept pile instead would be asserting the cull's behaviour under the
    emitter's name.
    """
    shared = _origin_labels(big_rows, "shared_origin")
    negatives = _origin_labels(big_rows, "multi")
    assert shared, "no shared_origin row carries an origin read"
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert shared == negatives


def test_the_small_build_offers_no_negative_the_shared_half_lacks(rows):
    """The small build's share of the same contract.

    Every negative label is one the shared half also offers, so no label
    appears under the independent answer alone. Coverage the other way
    needs more rows than `SIZE` holds and is checked at `BIG` above.
    """
    shared = _origin_labels(rows, "shared_origin")
    negatives = _origin_labels(rows, "multi")
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert negatives <= shared


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
    """What the EMITTER controls, and it is no longer a coin flip: 0.568,
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
    """
    share = _independent_share(kept)
    assert 0.52 <= share <= 0.70, f"kept-pile independent share {share:.3f}"


def test_a_negative_multi_row_shows_the_component_healthy(rows):
    """Same label, opposite content — otherwise the label is still the answer.

    Several scenarios share one read label: every node scenario in the
    exam's layout heads `describe node {node}`. So the healthy first lines
    are collected per label, and a row must show one of them. A dict of one
    content per label kept only the last scenario registered and failed
    every other scenario's negative row.
    """
    healthy = {}
    for p in propagation.trainable_scenarios():
        first = p.healthy_origin_content.split("\n")[0]
        healthy.setdefault(p.origin_read[0], set()).add(first)
    broken = {p.origin_read[1].split("\n")[0]
              for p in propagation.trainable_scenarios()}
    seen = 0
    for e in _by_case(rows, "multi"):
        if "origin_read_label" not in e.meta:
            continue
        seen += 1
        assert e.meta["origin_healthy"] is True
        first_lines = healthy[e.meta["origin_read_label"]]
        assert any(line in e.user for line in first_lines), e.meta
        for b in broken:
            assert b not in e.user
    assert seen


def test_a_negative_multi_row_still_says_separate_reasons(rows):
    for e in _by_case(rows, "multi"):
        assert propagation.SEPARATE_REASONS in e.assistant


def test_a_shared_origin_training_row_never_says_separate_reasons(rows):
    for e in _by_case(rows, "shared_origin"):
        assert propagation.SEPARATE_REASONS not in e.assistant


_PVC_SCOPED_ORIGINS = frozenset({
    "storage-provisioner-down",       # eval-only (propagation.py:425)
    "pvc-provisioner-not-responding", # ruled, trainable (propagation.py:6932)
    "pvc-storageclass-missing",       # ruled, trainable (propagation.py:7060)
})


def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    """Label-aware (spec section 3, ruling C): a `shared`-labeled row is
    decided end to end, one cause per victim, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback) can decide several
    victims to several PVC causes and still be one `shared` group.

    Re-measured 2026-09-19 (Task 9, spec section 6): before Task 9 no
    trainable scenario decided, so this exemption covered only the
    eval-only `storage-provisioner-down` origin and was future-proofing
    rather than a live path. Task 9 merged the two ruled PVC stories,
    `pvc-provisioner-not-responding` and `pvc-storageclass-missing`, into
    `trainable_scenarios()`; both are PVC-scoped by the same storage-class
    group-key fallback and both now decide multiple victims to multiple PVC
    causes under one `shared` group, confirmed by direct measurement
    (distinct-cause counts of 1, 2 and 3 across their `shared`-labeled
    rows). The exemption set below is closed and named, not inferred from
    `rules.py` at test time, so widening it is a deliberate edit here.
    """
    for e in _by_case(rows, "shared_origin"):
        if e.meta["label"] != "shared":
            continue
        causes = set(e.meta["expected"].values())
        assert all(w["decided"] for w in e.meta["workloads"].values())
        if e.meta["origin"] not in _PVC_SCOPED_ORIGINS:
            assert len(causes) == 1, e.meta["origin"]


# ------------------------------------------------------ the eval must not move

def test_the_eval_set_is_two_hundred_and_fifty_two_rows():
    """253 until `shared_origin_decoy_probe` appended its ten, then 263
    until the 2026-09-24 job-2 generator fix cut the `none_of_these` slice
    from 19 rows to 8.

    This test exists so the TRAINING half of the shared-origin work cannot
    move the exam by accident — a curriculum change that grows the test set
    invalidates every banked scoreboard silently. It does not forbid moving
    the exam on purpose; the decoy slice did that, in its own commit, with
    `tests/test_shared_origin_decoy_probe.py` proving the training set stayed
    byte-identical across the change. The 2026-09-24 generator fix moved it
    on purpose too, and re-pinned both exam digests below in the same
    commit.
    """
    assert len(generate.test_set()) == 252


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
#   the same way (the decoy is no longer attributed, so the header goes
#   too); and 9 of 19 `wrong_attribution` rows change their user message (4
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
FROZEN_SLICE_SHA256 = "aff7cc96aaec86bf7ce7d972632966a2c770adcde9facd4c8ef2b427f2f8c490"

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
EVAL_SET_SHA256 = "97a89e93fc5fdfdfebd0689fb5b74e060b68ba6879236ca12533e33a4ecb9c81"


def _digest(rows) -> str:
    blob = json.dumps([generate.to_row(e) for e in rows],
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_the_frozen_slice_is_every_row_before_the_decoy_probe():
    """The frozen slice is named by what it holds, not by a row number:
    every exam row before the trailing ten `shared_origin_decoy_probe`
    rows. Its length is pinned here, apart from its digest: 253 until the
    2026-09-24 job-2 generator fix, 242 since."""
    rows = generate.test_set()
    assert [e.case for e in rows[-10:]] == ["shared_origin_decoy_probe"] * 10
    assert "shared_origin_decoy_probe" not in {e.case for e in rows[:-10]}
    assert len(rows[:-10]) == 242


def test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used():
    assert _digest(generate.test_set()[:-10]) == FROZEN_SLICE_SHA256, (
        "the frozen slice moved; every banked scoreboard comparison is now void")


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


DRAWS = 33  # plain-story shared_origin rows per scenario at BIG; see below.
RULED_DRAWS = 66  # ruled-story shared_origin rows per scenario at BIG.
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
BIG = 13200


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS plain-story rows and RULED_DRAWS ruled-story
    rows per scenario, not one uniform rate over the whole pool (spec
    section 7 ruling A: "within each pool every story gets an equal share",
    checked per pool, not across them). Re-measured 2026-09-19, Task 9."""
    pool = propagation.trainable_scenarios()
    plain = sum(1 for p in pool if p.origin_object is None)
    ruled = sum(1 for p in pool if p.origin_object is not None)
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * plain + RULED_DRAWS * ruled


def test_the_trainable_pool_exercises_every_issue_kind():
    """A kind absent from the curriculum is a kind the shared-origin rule was
    never taught over -- and `vocab.ISSUE_KINDS` is what the eval draws from.
    """
    seen = {v.issue for p in propagation.trainable_scenarios() for v in p.victims}
    missing = sorted(set(vocab.ISSUE_KINDS) - seen)
    assert not missing, f"no trainable scenario exercises: {missing}"


# The pool grew by group across Tasks 5–9 of the 2026-09-08 coverage plan.
# Twenty-four is what it held when the 0907 run failed deciders 1 and 5;
# forty-eight was that plan's end. On 2026-09-19 the training-targets fix
# merged six ruled stories on top (section 6 of its design): 48 to 54.
EXPECTED_POOL = 54


def test_the_trainable_pool_holds_the_planned_count():
    """The pool is pinned so a scenario cannot fall out of the tuple unseen."""
    pool = propagation.trainable_scenarios()
    assert len(pool) == EXPECTED_POOL
    assert len({p.key for p in pool}) == EXPECTED_POOL


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
    """
    pool = propagation.trainable_scenarios()
    plain_keys = {p.key for p in pool if p.origin_object is None}
    ruled_keys = {p.key for p in pool if p.origin_object is not None}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == plain_keys | ruled_keys, (
            f"{case}: {sorted((plain_keys | ruled_keys) ^ set(counts))}")
        plain_shares = {v for k, v in counts.items() if k in plain_keys}
        ruled_shares = {v for k, v in counts.items() if k in ruled_keys}
        assert len(plain_shares) == 1, f"{case}: uneven plain shares {dict(counts)}"
        assert len(ruled_shares) == 1, f"{case}: uneven ruled shares {dict(counts)}"


def test_every_trainable_scenario_renders_at_least_three_origin_variants(big_rows):
    """Declaring four variants is not the same as rendering them. If the draw
    were keyed on something constant per scenario, every row would carry
    variant 0 and the whole mechanism would be inert while its own unit test
    still passed.

    The bar is 3 of 4 rather than 4 of 4 because the draw is uniform and
    random: this is a sampling check, and its strength is a function of
    `DRAWS`. At 33 draws a correct pool trips it about once in thirty
    million runs across a pool of forty-eight. Lowering `BIG` is not a free
    speed-up -- at 11 draws it is about 7%, and the failure names a scenario
    whose data is fine.
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


def test_one_training_only_separate_prompt_exists_at_the_frozen_seed():
    """The `separate` label is pinned three ways (a rules unit test, a scorer
    unit test, and this one): at least one real training prompt must reach
    `label == "separate"`, both its workloads confirmed and on different
    nodes, or the label exists only in isolated unit tests and never in a
    prompt a model actually trains on. `separate` stays at 0 in the exam
    (R42), so this prompt has to live in the training split.
    """
    train, _ = generate.split(generate.generate(seed=17, size=8000), seed=17)
    separate_rows = [e for e in train
                     if e.meta.get("case") == "multi" and e.meta.get("label") == "separate"]
    assert separate_rows, "no training-only separate-label multi prompt at seed=17"
    row = separate_rows[0]
    workloads = row.meta["workloads"]
    assert len(workloads) == 2
    for meta in workloads.values():
        assert meta["decided"] is True
    # decided_evidence is a template sentence ("Ready condition is False
    # now") shared by every worker-containerd-stop draw regardless of which
    # node it lands on, so it carries no node identity. decided_cause does
    # ("node worker-2 (NotReady)" vs. "node worker-1 (NotReady)") -- the
    # per-workload field this assert actually needs.
    nodes = {meta["decided_cause"] for meta in workloads.values()}
    assert len(nodes) == 2, "both workloads must be on different nodes"
