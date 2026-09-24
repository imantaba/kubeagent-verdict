"""Unit tests for render.py's helpers — no builder or catalog calls.

Every fixture Object here is built by hand; none of these tests import
cases.py or generate.py. That is deliberate: this file is what proves
Commit A (render.py alone) is additive-only — nothing here can move either
frozen hash.
"""

import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import render, rules


def test_bind_formats_every_string_field():
    obj = o.Object(kind="node", name="{node}", scan_reason="NotReady",
                    placement="on", fresh=o.Fresh(ready="False"), intent="cause")
    names = {"ns": "shop", "name": "api", "pod": "api-0", "container": "api",
              "init_container": "init", "node": "worker-1", "pvc": "data-0",
              "image": "registry.example.com/api:1", "restarts": 5}
    bound = render.bind(obj, names)
    assert bound.name == "worker-1"
    assert bound.kind == "node"
    assert bound.scan_reason == "NotReady"
    assert bound.placement == "on"
    assert bound.intent == "cause"
    assert bound.fresh == obj.fresh
    assert obj.name == "{node}"


def test_bind_leaves_a_literal_name_unchanged():
    obj = o.Object(kind="pvc", name="aux-0", scan_reason="ProvisioningFailed",
                    placement="unmounted", fresh=o.Fresh(how="read", phase="Pending"))
    names = {"ns": "shop", "name": "api", "pod": "api-0", "container": "api",
              "init_container": "init", "node": "worker-1", "pvc": "data-0",
              "image": "registry.example.com/api:1", "restarts": 0}
    bound = render.bind(obj, names)
    assert bound.name == "aux-0"


def test_draw_ending_node_matches_seed_1_sequence():
    rng = random.Random(1)
    obj = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                    placement="on", fresh=o.Fresh(how="read", ready="False"))
    drawn = [render.draw_ending(obj, rng) for _ in range(6)]
    assert drawn[0].scan_reason == "NotReady"
    assert drawn[0].fresh.ready == "True"
    assert drawn[0].fresh.how == "read"
    assert drawn[1].fresh.how == "read_failed"
    assert drawn[1].fresh.message == 'nodes "worker-1" is forbidden'
    assert drawn[2].scan_reason == "NotReady"
    assert drawn[2].fresh.ready == "True"
    assert drawn[3].scan_reason == "no kubelet lease"
    assert drawn[3].fresh.ready == "True"
    assert drawn[4].scan_reason == "NotReady"
    assert drawn[4].fresh.ready == "True"
    assert drawn[5].scan_reason == "no kubelet lease"
    assert drawn[5].fresh.ready == "True"


def test_draw_ending_pvc_matches_seed_1_sequence():
    rng = random.Random(1)
    obj = o.Object(kind="pvc", name="data-0", scan_reason="FailedBinding",
                    placement="mounted", fresh=o.Fresh(how="read", phase="Pending"))
    drawn = [render.draw_ending(obj, rng) for _ in range(6)]
    assert drawn[0].fresh.phase == "Bound"
    assert drawn[0].fresh.how == "read"
    assert drawn[1].fresh.phase == "Bound"
    assert drawn[2].fresh.how == "read_failed"
    assert drawn[2].fresh.message == 'persistentvolumeclaims "data-0" is forbidden'
    assert drawn[3].fresh.phase == "Bound"
    assert drawn[4].fresh.how == "read_failed"
    assert drawn[4].fresh.message == 'persistentvolumeclaims "data-0" is forbidden'
    assert drawn[5].fresh.how == "read_failed"


def test_draw_ending_registry_matches_seed_1_sequence():
    rng = random.Random(1)
    obj = o.Object(kind="registry", name="registry.example.com", scan_reason="3",
                    placement="", fresh=o.Fresh(how="read", literal="manifest unknown"))
    drawn = [render.draw_ending(obj, rng) for _ in range(6)]
    assert drawn[0].fresh.literal == "manifest unknown"
    assert drawn[0].fresh.how == "read"
    assert drawn[1].fresh.literal == ""
    assert drawn[2].fresh.literal == "manifest unknown"
    assert drawn[3].fresh.literal == "unauthorized"
    assert drawn[4].fresh.literal == "manifest unknown"
    assert drawn[5].fresh.literal == "unauthorized"


def _node_decoy(n):
    return o.Object(kind="node", name=f"worker-{n}", scan_reason="NotReady",
                     placement="on", fresh=o.Fresh(how="read", ready="True"))


def test_apply_budget_marks_a_decoy_past_the_budget_not_read():
    objects = tuple(_node_decoy(i) for i in range(8)) + (
        o.Object(kind="pvc", name="aux-0", scan_reason="ProvisioningFailed",
                  placement="unmounted", fresh=o.Fresh(how="read", phase="Pending")),
    )
    out = render.apply_budget(objects, workload_order=(0,) * 9,
                               entry_or_scenario_key="e1")
    assert len(out) == 9
    assert out[8].kind == "pvc"
    assert out[8].fresh.how == "not_read"
    assert out[8].fresh.phase == ""
    assert out[0].fresh.how == "read"


def test_apply_budget_raises_when_a_cause_would_be_starved():
    cause = o.Object(kind="pvc", name="data-0", scan_reason="FailedBinding",
                      placement="mounted", fresh=o.Fresh(how="read", phase="Pending"),
                      intent="cause")
    objects = tuple(_node_decoy(i) for i in range(8)) + (cause,)
    try:
        render.apply_budget(objects, workload_order=(0,) * 9,
                             entry_or_scenario_key="e1")
        raise AssertionError("expected ValueError")
    except ValueError as err:
        assert str(err) == (
            "entry e1: the 8-read budget would leave pvc/data-0 "
            "(intent=cause) unread; pass allow_overflow=True if that is "
            "the point"
        )


def test_apply_budget_allow_overflow_starves_the_cause_on_purpose():
    cause = o.Object(kind="pvc", name="data-0", scan_reason="FailedBinding",
                      placement="mounted", fresh=o.Fresh(how="read", phase="Pending"),
                      intent="cause")
    objects = tuple(_node_decoy(i) for i in range(8)) + (cause,)
    out = render.apply_budget(objects, workload_order=(0,) * 9,
                               entry_or_scenario_key="e1", allow_overflow=True)
    assert out[8].kind == "pvc"
    assert out[8].fresh.how == "not_read"


def test_apply_budget_reorders_registry_before_node_before_pvc():
    node = _node_decoy(0)
    pvc = o.Object(kind="pvc", name="aux-0", scan_reason="ProvisioningFailed",
                    placement="unmounted", fresh=o.Fresh(how="read", phase="Pending"))
    registry = o.Object(kind="registry", name="registry.example.com", scan_reason="3",
                         placement="", fresh=o.Fresh(how="read", literal="manifest unknown"))
    out = render.apply_budget((pvc, node, registry), workload_order=(0, 0, 0),
                               entry_or_scenario_key="e1")
    assert [obj.kind for obj in out] == ["registry", "node", "pvc"]


def _registry(literal):
    return o.Object(kind="registry", name="registry.example.com", scan_reason="3",
                     placement="", fresh=o.Fresh(how="read", literal=literal))


def test_registry_events_read_literal_shape():
    read = render.registry_events_read(_registry("manifest unknown"), ns="shop",
                                        pod="api-0", image="registry.example.com/api:1")
    assert read.label == "events shop/api-0"
    assert read.content == (
        'events for shop/api-0:\n'
        '  Failed: Failed to pull image "registry.example.com/api:1": manifest unknown (x4)\n'
    )


def test_registry_events_read_no_event_shape():
    read = render.registry_events_read(_registry(""), ns="shop", pod="api-0",
                                        image="registry.example.com/api:1")
    assert read.label == "events shop/api-0"
    assert read.content == "no events for shop/api-0"


def test_registry_events_read_contradiction_probe_two_lines():
    read = render.registry_events_read(_registry("unauthorized"), ns="shop", pod="api-0",
                                        image="registry.example.com/api:1",
                                        own_line="manifest unknown")
    assert read.content == (
        'events for shop/api-0:\n'
        '  Failed: Failed to pull image "registry.example.com/api:1": unauthorized (x4)\n'
        '  Failed: Failed to pull image "registry.example.com/api:1": manifest unknown (x4)\n'
    )


def test_object_reads_uses_rules_read_text_for_node_and_pvc():
    node = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                     placement="on", fresh=o.Fresh(how="read", ready="False"))
    pvc = o.Object(kind="pvc", name="data-0", scan_reason="FailedBinding",
                    placement="mounted",
                    fresh=o.Fresh(how="read", phase="Pending",
                                   storage_class="standard", volume=""))
    reads = render.object_reads((node, pvc), ns="shop", pod="api-0")
    assert reads[0].label == "describe node /worker-1"
    assert reads[0].content == "node worker-1: unschedulable=false\n"
    assert reads[1].label == "describe pvc shop/data-0"
    assert reads[1].content == (
        "pvc shop/data-0: phase=Pending storageClass=standard volume=\n"
    )


def test_object_reads_skips_not_read_objects():
    starved = o.Object(kind="pvc", name="data-0", scan_reason="FailedBinding",
                        placement="mounted", fresh=o.Fresh(how="not_read"))
    assert render.object_reads((starved,), ns="shop", pod="api-0") == ()


def test_object_reads_delegates_registry_to_registry_events_read():
    reg = _registry("manifest unknown")
    reads = render.object_reads((reg,), ns="shop", pod="api-0",
                                 image="registry.example.com/api:1")
    assert reads[0] == render.registry_events_read(
        reg, ns="shop", pod="api-0", image="registry.example.com/api:1"
    )


def test_render_workload_builds_candidates_reads_and_result():
    node = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                     placement="on", fresh=o.Fresh(how="read", ready="False"),
                     intent="cause")
    workload, reads, result = render.render_workload(
        (node,), ns="shop", name="api", pod="api-0",
        image="registry.example.com/api:1", issue="CrashLoopBackOff",
        kind="Deployment", status="degraded",
    )
    assert workload.namespace == "shop"
    assert workload.name == "api"
    assert workload.kind == "Deployment"
    assert workload.status == "degraded"
    assert len(workload.candidates) == 1
    cand = workload.candidates[0]
    assert cand.cause == "node worker-1 (NotReady)"
    assert cand.verdict == "attributed"
    assert cand.fresh_read_outcome == "confirmed"
    assert cand.fresh_read_evidence == "Ready condition is False now"
    assert workload.decided is True
    assert workload.decided_cause == "node worker-1 (NotReady)"
    assert workload.decided_outcome == "confirmed"
    assert len(reads) == 1
    assert reads[0].label == "describe node /worker-1"
    assert result.cause == "node worker-1 (NotReady)"
    assert workload.confidence == "high"


def test_render_workload_prints_no_header_when_every_candidate_is_ruled_out():
    node = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                     placement="off", fresh=o.Fresh(how="read", ready="False"),
                     intent="decoy")
    workload, _reads, _result = render.render_workload(
        (node,), ns="shop", name="api", pod="api-0",
        image="registry.example.com/api:1", issue="CrashLoopBackOff",
        kind="Deployment", status="degraded",
    )
    assert workload.candidates[0].verdict == "ruled_out"
    assert workload.confidence == ""


# ------------------------------------------------------------- header_for
#
# A port of kubeagent v1.24.0's `confidence.ForRootCause`
# (internal/confidence/confidence.go:36-47), applied to the one attributed
# candidate's cause. `internal/investigate/prime.go:58-64` prints the header
# for any non-empty value, `high` included.


def _cand(cause: str, verdict: str) -> c.Candidate:
    return c.Candidate(cause=cause, verdict=verdict, reason="r")


@pytest.mark.parametrize("cause, level", [
    ("node worker-1 (NotReady)", "high"),
    ("PVC data-0 (FailedBinding)", "high"),
    ("registry registry.invalid (3 workloads failing to pull)", "medium"),
    ("image tag v9 does not exist", ""),
    ("pvc data-0 (FailedBinding)", ""),   # the Go prefix match is case-sensitive
])
def test_header_for_ports_for_root_cause(cause, level):
    assert render.header_for((_cand(cause, "attributed"),)) == level


def test_header_for_reads_only_the_attributed_candidate():
    cands = (_cand("node worker-1 (NotReady)", "ruled_out"),
             _cand("registry registry.invalid (2 workloads failing to pull)", "attributed"))
    assert render.header_for(cands) == "medium"


def test_header_for_is_empty_with_no_attributed_candidate():
    assert render.header_for((_cand("node worker-1 (NotReady)", "ruled_out"),
                              _cand("PVC data-0 (FailedBinding)", "outranked"))) == ""
    assert render.header_for(()) == ""


def test_header_for_refuses_two_attributed_candidates():
    """kubeagent's trace has at most one winner, so two is a generator bug."""
    with pytest.raises(ValueError, match="2 attributed"):
        render.header_for((_cand("node worker-1 (NotReady)", "attributed"),
                           _cand("PVC data-0 (FailedBinding)", "attributed")))


def test_workload_meta_has_exactly_seven_keys():
    result = rules.Result(decided=True, cause="node worker-1 (NotReady)",
                           outcome="confirmed", evidence="Ready condition is False now",
                           group_key="", group_text="", decisions=())
    meta = render.workload_meta(result,
                                 expected_cause="node worker-1 (NotReady)",
                                 own_cause_keywords=[])
    assert meta == {
        "job": 1,
        "decided": True,
        "decided_cause": "node worker-1 (NotReady)",
        "decided_outcome": "confirmed",
        "decided_evidence": "Ready condition is False now",
        "expected_cause": "node worker-1 (NotReady)",
        "own_cause_keywords": [],
    }


def test_workload_meta_falls_back_to_empty_strings_when_undecided():
    result = rules.Result(decided=False, cause="", outcome="", evidence="",
                           group_key="", group_text="", decisions=())
    meta = render.workload_meta(result, expected_cause="",
                                 own_cause_keywords=["disk pressure"])
    assert meta["job"] == 2
    assert meta["decided"] is False
    assert meta["decided_cause"] == ""
    assert meta["decided_outcome"] == ""
    assert meta["decided_evidence"] == ""
    assert meta["own_cause_keywords"] == ["disk pressure"]


def test_prompt_meta_adds_label_and_decoy_by_workload():
    workload_metas = {"web/frontend": {"job": 1, "decided": True,
                        "decided_cause": "x", "decided_outcome": "confirmed",
                        "decided_evidence": "y", "expected_cause": "x"}}
    meta = render.prompt_meta(workload_metas, label="shared",
                               decoy_by_workload={"web/frontend": ["node/worker-2"]})
    assert meta == {
        "workloads": workload_metas,
        "label": "shared",
        "decoy_by_workload": {"web/frontend": ["node/worker-2"]},
    }


def test_prompt_meta_refuses_empty_workload_metas():
    try:
        render.prompt_meta({}, label="none", decoy_by_workload={})
        raise AssertionError("expected ValueError")
    except ValueError as err:
        assert str(err) == "prompt_meta: workload_metas must not be empty"


def test_check_prompt_size_passes_under_the_cap():
    render.check_prompt_size("short prompt", entry_or_scenario_key="e1")


def test_check_prompt_size_raises_over_the_cap():
    big = "x" * (render.MAX_PROMPT_BYTES + 1)
    try:
        render.check_prompt_size(big, entry_or_scenario_key="e1")
        raise AssertionError("expected ValueError")
    except ValueError as err:
        assert str(err) == (
            f"entry e1: prompt is {len(big)} bytes, over the "
            f"{render.MAX_PROMPT_BYTES}-byte cap"
        )
