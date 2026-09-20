"""`_render_shared_origin`'s decided-row cause/rationale and its
label-driven summary (spec section 3).

Unit tests build synthetic `rules.Result` values and row dicts directly,
one per branch of the two small pure helpers `_render_shared_origin`
delegates to: `_shared_origin_row` (per-victim cause/rationale) and
`_shared_origin_summary` (the four-way summary table). Build-level tests
then confirm the wiring against the real eval scenarios, where the
decided/undecided split actually occurs today (see the trainable pool's
own oracle tests for the training side, which never decides).
"""

from __future__ import annotations

import json

import pytest

from kubeagent_verdict.dataset import cases, generate, rules
from kubeagent_verdict.dataset import propagation as prop

# --------------------------------------------------------------- fixtures


def _confirmed_result(cause: str = "node worker-2 (NotReady)") -> rules.Result:
    return rules.Result(decided=True, cause=cause, outcome="confirmed",
                        evidence="Ready condition is False now",
                        group_key="node/worker-2", group_text=cause,
                        decisions=())


def _unverified_result(cause: str = "node worker-1 (no kubelet lease)") -> rules.Result:
    return rules.Result(decided=True, cause=cause, outcome="unverified",
                        evidence="Ready condition is True, but the kubelet "
                                 "lease was not re-read",
                        group_key="", group_text="", decisions=())


def _undecided_result() -> rules.Result:
    return rules.Result(decided=False, cause="", outcome="", evidence="",
                        group_key="", group_text="", decisions=())


# ---------------------------------------------------- _shared_origin_row


def test_decided_confirmed_row_gets_the_rules_cause_and_rationale():
    result = _confirmed_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=False, decoy="the wrong decoy cause",
        shared_cause="the story's shared cause")
    assert cause == result.cause
    assert rationale == cases._rule_rationale(result)


def test_decided_unverified_row_also_gets_the_rules_cause_and_rationale():
    result = _unverified_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=True, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == result.cause
    assert rationale == cases._rule_rationale(result)


def test_undecided_broken_row_keeps_the_shared_cause():
    result = _undecided_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=False, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == "the story's shared cause"
    assert rationale is None  # caller keeps today's rationale template


def test_undecided_healthy_row_keeps_the_decoy_cause():
    result = _undecided_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=True, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == "the decoy cause"
    assert rationale is None


# ------------------------------------------------ _shared_origin_summary


_ROWS = [{"workload": "ns1/a", "cause": "cause A"},
        {"workload": "ns2/b", "cause": "cause B"},
        {"workload": "ns3/c", "cause": "cause C"}]


def test_shared_label_keeps_todays_three_lines():
    lines = cases._shared_origin_summary(
        "shared", healthy=False, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines == ["3 workloads share one upstream cause: the origin is broken.",
                     "Root cause: the shared cause.", "fix the origin"]


def test_none_label_healthy_twin_all_different_says_separate_reasons():
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines[0] == "3 workloads are failing for separate reasons."
    assert lines[1:] == ["ns1/a: cause A.", "ns2/b: cause B.", "ns3/c: cause C."]


def test_none_label_broken_says_rules_did_not_confirm_one_cause():
    lines = cases._shared_origin_summary(
        "none", healthy=False, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines[0] == ("3 workloads are failing, and kubeagent's rules did not "
                        "confirm one cause on two or more of them.")
    assert lines[1:] == ["ns1/a: cause A.", "ns2/b: cause B.", "ns3/c: cause C."]
    assert "fix the origin" not in lines


def test_none_label_healthy_twin_with_a_repeated_cause_uses_the_other_branch():
    rows = [{"workload": "ns1/a", "cause": "same cause"},
           {"workload": "ns2/b", "cause": "same cause"}]
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=2, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=rows, key="test-story")
    assert lines[0] == ("2 workloads are failing, and kubeagent's rules did not "
                        "confirm one cause on two or more of them.")


def test_separate_label_raises():
    with pytest.raises(ValueError, match="separate"):
        cases._shared_origin_summary(
            "separate", healthy=False, count=3, origin="x", shared_cause="y",
            remedy="z", rows=_ROWS, key="test-story")


def test_summary_lines_cap_at_three_rows():
    rows = _ROWS + [{"workload": "ns4/d", "cause": "cause D"}]
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=4, origin="x", shared_cause="y",
        remedy="z", rows=rows, key="test-story")
    assert len(lines) == 4  # 1 header + 3 rows, never the fourth


# --------------------------------------------------------- build-level tests


def test_no_story_shared_cause_or_local_cause_holds_a_shared_claim_phrase():
    """A cause holding a shared-claim phrase would make job 3 read a `none`
    row's per-workload cause line as a claim and fail it (spec section 3).
    """
    phrases = cases.SHARED_CLAIM_PHRASES
    for pool in (prop.trainable_scenarios(), prop.all_scenarios()):
        for p in pool:
            low = p.shared_cause.lower()
            assert not any(ph in low for ph in phrases), (p.key, "shared_cause")
            for v in p.victims:
                low = v.local_cause.lower()
                assert not any(ph in low for ph in phrases), (p.key, "local_cause")


def test_a_shared_label_only_comes_from_an_origin_object():
    """Every `shared` row is a ruled story's broken twin or one of the exam's
    three origin-object stories -- never a plain story, which has no
    candidate the rules could confirm twice under one group key.

    Extended 2026-09-19 (Task 9, spec section 6): before Task 9 no trainable
    story decided, so only the eval half of this claim had a pool to check
    against. Task 9 merged the six ruled stories into `trainable_scenarios()`;
    the second loop below walks that fifty-four-story pool with the TRAINING
    builder (`cases.shared_origin`, not the eval-only `shared_origin_probe`)
    and confirms the same rule holds there too -- exactly the six ruled
    stories decide, and every one of the forty-eight plain stories does not.
    """
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key
    for p in prop.trainable_scenarios():
        ex = cases.shared_origin(p, generate._entry_rng("t", p.key), victims=2)
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key
        else:
            assert p.origin_object is None, p.key


def test_exactly_two_of_ten_shared_origin_probe_rows_families_are_shared():
    """The three origin-object eval stories (node-not-ready,
    storage-provisioner-down, registry-unreachable) label `shared`; the
    other three (coredns-down, node-disk-pressure, networkpolicy-deny-all)
    label `none` -- pinned so a future story addition is a deliberate
    edit here, not a silent drift.
    """
    labels = {}
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        labels[p.key] = ex.meta["label"]
    assert labels == {
        "coredns-down": "none",
        "node-not-ready": "shared",
        "storage-provisioner-down": "shared",
        "registry-unreachable": "shared",
        "node-disk-pressure": "none",
        "networkpolicy-deny-all": "none",
    }


def test_a_decided_shared_origin_probe_workload_carries_the_rules_cause():
    """`node-not-ready`'s two victims share one node, so both decide against
    the SAME `origin_object` and both get the identical rules' cause."""
    p = {q.key: q for q in prop.all_scenarios()}["node-not-ready"]
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    verdicts = json.loads(ex.assistant)["verdicts"]
    causes = {v["cause"] for v in verdicts}
    assert len(causes) == 1
    only_cause = causes.pop()
    assert only_cause != p.shared_cause  # the rules' own terse cause, not the sentence
    assert only_cause.startswith("node ")
