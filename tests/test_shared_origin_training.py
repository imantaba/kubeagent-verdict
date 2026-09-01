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

import re

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


def test_no_trainable_scenario_text_carries_a_banned_identifier_shape():
    banned = (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"https?://"),
              re.compile(r"kubeconfig", re.IGNORECASE), re.compile(r"/home/"),
              re.compile(r"@"))
    for p in propagation.trainable_scenarios():
        blob = "\n".join([p.origin, p.shared_cause, p.shared_reason,
                          p.distractor_cause, p.distractor_reason, p.rationale,
                          p.remedy, p.origin_read[0], p.origin_read[1],
                          p.healthy_origin_content]
                         + [f"{v.reason}\n{v.evidence}\n{v.log_cause}\n"
                            f"{v.local_cause}\n{v.local_reason}\n"
                            f"{v.read[0]}\n{v.read[1]}" for v in p.victims])
        for pat in banned:
            assert not pat.search(blob), f"{p.key}: {pat.pattern}"


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

def _origin_labels(rows, case):
    return {e.meta["origin_read_label"] for e in rows
            if e.case == case and "origin_read_label" in e.meta}


def test_an_origin_shaped_read_no_longer_predicts_a_shared_answer(kept):
    """The cue test. Every trainable origin read must appear under BOTH answers.

    If these two sets differ, some read label is a free giveaway: seeing it
    settles the answer without reading its content. Asserted on the kept
    pile, because a label the filter removes every instance of is a giveaway
    in the data the model reads however even the generator's output looked.
    """
    shared = _origin_labels(kept, "shared_origin")
    independent = _origin_labels(kept, "multi")
    assert shared, "no shared_origin row carries an origin read"
    assert independent, "no multi row carries an origin read — the cue is alive"
    assert shared == independent


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
