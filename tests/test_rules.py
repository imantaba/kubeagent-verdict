"""Tests for dataset/rules.py: attribution, decision, sharing, reads.

Two kinds of test live here. The unit tests build small, hand-picked
Objects to hit one branch of attribute()/decide()/shared()/label()/
read_text()/check_declaration() at a time — including branches the
capture fixture below never reaches. The replay tests at the bottom
declare the same 12 workloads, 6 down nodes, 8 PVCs and 2 registries
kubeagent's own v1.24.0 capture (Task 2) declared, run them through
attribute() and decide(), and check the result against
tests/fixtures/rules_golden.json byte for byte. If a value here ever
disagrees with the fixture, the fixture is right and this file is wrong.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import rules as r

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rules_golden.json"


def node(**kw):
    base = {"kind": "node", "name": "worker-1", "scan_reason": "NotReady",
            "placement": "on", "fresh": o.Fresh(how="read", ready="False")}
    base.update(kw)
    return o.Object(**base)


def pvc(**kw):
    base = {"kind": "pvc", "name": "aux-0", "scan_reason": "ProvisioningFailed",
            "placement": "mounted", "fresh": o.Fresh(how="read", phase="Pending", storage_class="fast-ssd")}
    base.update(kw)
    return o.Object(**base)


def registry(**kw):
    base = {"kind": "registry", "name": "registry.invalid", "scan_reason": "2",
            "placement": "", "fresh": o.Fresh(how="read", literal="connection refused")}
    base.update(kw)
    return o.Object(**base)


# ---------------------------------------------------------------------------
# attribute(): node candidates
# ---------------------------------------------------------------------------

def test_attribute_node_precedence_and_ordering():
    objs = (
        node(name="worker-2", placement="on"),
        node(name="worker-1", placement="on"),
        node(name="worker-3", placement="off"),
    )
    cands = r.attribute(objs, ns="web", pod="web-abc", issue="CrashLoopBackOff")
    assert [c.cause for c in cands] == [
        "node worker-1 (NotReady)", "node worker-2 (NotReady)", "node worker-3 (NotReady)",
    ]
    assert (cands[0].verdict, cands[0].reason) == ("attributed", "pod web-abc is scheduled on it")
    assert (cands[1].verdict, cands[1].reason) == (
        "outranked", "node worker-1 (NotReady) is the stronger cause")
    assert (cands[2].verdict, cands[2].reason) == (
        "ruled_out", "no pod of this workload is scheduled on it")


def test_attribute_returns_every_candidate_uncapped():
    objs = tuple(node(name=f"worker-{i}", placement="off") for i in range(9))
    cands = r.attribute(objs, ns="web", pod="p", issue="CrashLoopBackOff")
    assert len(cands) == 9  # attribute() never applies MAX_CANDIDATES; that is a render concern


# ---------------------------------------------------------------------------
# attribute(): PVC candidates
# ---------------------------------------------------------------------------

def test_attribute_pvc_precedence_and_ordering():
    objs = (
        pvc(name="aux-1", placement="mounted"),
        pvc(name="aux-0", placement="mounted"),
        pvc(name="aux-2", placement="unmounted"),
    )
    cands = r.attribute(objs, ns="db", pod="db-xyz", issue="Pending")
    assert [c.cause for c in cands] == [
        "PVC aux-0 (ProvisioningFailed)", "PVC aux-1 (ProvisioningFailed)", "PVC aux-2 (ProvisioningFailed)",
    ]
    assert (cands[0].verdict, cands[0].reason) == ("attributed", "pod db-xyz mounts it")
    assert (cands[1].verdict, cands[1].reason) == (
        "outranked", "PVC aux-0 (ProvisioningFailed) is the stronger cause")
    assert (cands[2].verdict, cands[2].reason) == (
        "ruled_out", "not mounted by this workload's pods")


def test_attribute_node_outranks_pvc():
    objs = (node(name="worker-1", placement="on"), pvc(name="aux-0", placement="mounted"))
    cands = r.attribute(objs, ns="db", pod="db-xyz", issue="Pending")
    assert cands[0].verdict == "attributed"
    assert cands[1].verdict == "outranked"
    assert cands[1].reason == "node worker-1 (NotReady) is the stronger cause"


# ---------------------------------------------------------------------------
# attribute(): registry candidates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("count, verdict, cause, reason", [
    (2, "attributed", "registry registry.invalid (2 workloads failing to pull)",
     "2 workloads failing to pull from this host clear the threshold of 2"),
    (5, "attributed", "registry registry.invalid (5 workloads failing to pull)",
     "5 workloads failing to pull from this host clear the threshold of 2"),
    (1, "ruled_out", "registry registry.invalid",
     "only workload failing to pull from this host; threshold is 2"),
    (0, "ruled_out", "registry registry.invalid",
     "only workload failing to pull from this host; threshold is 2"),
])
def test_attribute_registry_threshold(count, verdict, cause, reason):
    objs = (registry(name="registry.invalid", scan_reason=str(count)),)
    cands = r.attribute(objs, ns="img", pod="img-1", issue="ImagePullBackOff")
    assert len(cands) == 1
    assert (cands[0].cause, cands[0].verdict, cands[0].reason) == (cause, verdict, reason)


def test_attribute_registry_outranked_when_something_else_already_won():
    objs = (node(name="worker-1", placement="on"), registry(name="registry.invalid", scan_reason="9"))
    cands = r.attribute(objs, ns="img", pod="img-1", issue="ImagePullBackOff")
    # An outranked registry cause never carries the puller count.
    assert cands[1].cause == "registry registry.invalid"
    assert cands[1].verdict == "outranked"
    assert cands[1].reason == "node worker-1 (NotReady) is the stronger cause"


def test_attribute_registry_unknown_when_image_is_empty():
    objs = (registry(name="", scan_reason="0"),)
    cands = r.attribute(objs, ns="img", pod="img-2", issue="ImagePullBackOff")
    assert cands[0].cause == "registry unknown"
    assert cands[0].verdict == "ruled_out"
    assert cands[0].reason == "image reference undeterminable"


def test_attribute_skips_registry_entirely_for_an_init_issue():
    # Init:ImagePullBackOff and Init:ErrImagePull are real kubeagent issue
    # strings but never equal REGISTRY_ISSUES' exact entries.
    objs = (registry(name="registry.invalid", scan_reason="9"),)
    cands = r.attribute(objs, ns="img", pod="img-3", issue="Init:ImagePullBackOff")
    assert cands == ()


def test_attribute_skips_registry_for_an_unrelated_issue():
    objs = (registry(name="registry.invalid", scan_reason="9"),)
    cands = r.attribute(objs, ns="img", pod="img-3", issue="CrashLoopBackOff")
    assert cands == ()


# ---------------------------------------------------------------------------
# decide(): node checker branches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ready, outcome, evidence", [
    ("missing", "confirmed", "the node has no Ready condition"),
    ("False", "confirmed", "Ready condition is False now"),
    ("Unknown", "confirmed", "Ready condition is Unknown now"),
])
def test_decide_node_confirmed_branches(ready, outcome, evidence):
    c = r.Candidate("node worker-1 (NotReady)", "attributed", "pod x is scheduled on it",
                     node(placement="on", fresh=o.Fresh(how="read", ready=ready)), "web")
    res = r.decide((c,))
    assert res.decided and res.outcome == outcome and res.evidence == evidence
    assert res.group_key == "node/worker-1" and res.group_text == "node worker-1 (NotReady)"


def test_decide_node_true_without_heartbeat_cause_is_refuted_and_undecided():
    # Not reached by the capture fixture: every fixture node whose Ready
    # comes back True also carries a heartbeat scan_reason.
    c = r.Candidate("node worker-1 (NotReady)", "attributed", "r",
                     node(placement="on", fresh=o.Fresh(how="read", ready="True")), "web")
    res = r.decide((c,))
    assert res.decisions[0].outcome == "refuted"
    assert res.decisions[0].evidence == "Ready condition is True now"
    assert res.decided is False and res.cause == "" and res.outcome == ""


@pytest.mark.parametrize("cause", ["node worker-2 (no kubelet lease)", "node worker-3 (kubelet not heartbeating)"])
def test_decide_node_true_with_heartbeat_cause_is_unverified(cause):
    scan_reason = cause.split("(")[1].rstrip(")")
    c = r.Candidate(cause, "attributed", "r",
                     node(name="worker-2", scan_reason=scan_reason, placement="on",
                          fresh=o.Fresh(how="read", ready="True")), "web")
    res = r.decide((c,))
    assert res.outcome == "unverified"
    assert res.evidence == "Ready condition is True, but the kubelet lease was not re-read"


def test_decide_node_read_failed_and_not_read():
    failed = r.Candidate("node worker-7 (NotReady)", "attributed", "r",
                          node(name="worker-7", placement="on",
                               fresh=o.Fresh(how="read_failed", message='nodes "worker-7" is forbidden')), "web")
    res = r.decide((failed,))
    assert res.outcome == "unverified"
    assert res.evidence == 'fresh read failed: nodes "worker-7" is forbidden'

    not_read = r.Candidate("node worker-3 (kubelet not heartbeating)", "attributed", "r",
                            node(name="worker-3", scan_reason="kubelet not heartbeating", placement="on",
                                 fresh=o.Fresh(how="not_read")), "web")
    res = r.decide((not_read,))
    assert res.outcome == "unverified"
    assert res.evidence == "not re-read: the read budget was spent first"


# ---------------------------------------------------------------------------
# decide(): PVC checker branches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase, outcome, evidence", [
    ("Bound", "refuted", "phase is Bound now"),
    ("Pending", "confirmed", "phase is still Pending"),
    ("Lost", "confirmed", "phase is Lost"),
    ("Released", "unverified", "phase is not one kubeagent expects"),
])
def test_decide_pvc_phase_branches(phase, outcome, evidence):
    c = r.Candidate("PVC aux-0 (ProvisioningFailed)", "attributed", "r",
                     pvc(placement="mounted", fresh=o.Fresh(how="read", phase=phase, storage_class="fast-ssd")), "db")
    res = r.decide((c,))
    if outcome == "confirmed":
        assert res.decided and res.outcome == outcome and res.evidence == evidence
    else:
        # refuted and unverified-only-candidate cases: unverified still wins
        # as a Result (there is no confirmed candidate to beat it), refuted
        # never does.
        if outcome == "refuted":
            assert res.decided is False
            assert res.decisions[0].outcome == "refuted" and res.decisions[0].evidence == evidence
        else:
            assert res.decided and res.outcome == "unverified" and res.evidence == evidence


def test_decide_pvc_read_failed_and_not_read():
    failed = r.Candidate("PVC aux-1 (ProvisioningFailed)", "attributed", "r",
                          pvc(name="aux-1", placement="mounted",
                              fresh=o.Fresh(how="read_failed", message='persistentvolumeclaims "aux-1" is forbidden')), "db")
    res = r.decide((failed,))
    assert res.outcome == "unverified"
    assert res.evidence == 'fresh read failed: persistentvolumeclaims "aux-1" is forbidden'

    not_read = r.Candidate("PVC aux-4 (ProvisioningFailed)", "attributed", "r",
                            pvc(name="aux-4", placement="mounted", fresh=o.Fresh(how="not_read")),
                            "db")
    res = r.decide((not_read,))
    assert res.outcome == "unverified"
    assert res.evidence == "not re-read: the read budget was spent first"


# ---------------------------------------------------------------------------
# decide(): registry checker branches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("literal, outcome, evidence", [
    ("connection refused", "confirmed", "a pull event shows a connection error: connection refused"),
    ("i/o timeout", "confirmed", "a pull event shows a connection error: i/o timeout"),
    ("unauthorized", "unverified",
     "a pull event shows an auth error: unauthorized; that can be one image or the whole host"),
    ("manifest unknown", "refuted",
     "a pull event shows an image error: manifest unknown; this pull fails for this image, not the host"),
    ("", "unverified", "no pull event names the failure; events may have aged out"),
])
def test_decide_registry_literal_branches(literal, outcome, evidence):
    c = r.Candidate("registry registry.invalid (8 workloads failing to pull)", "attributed", "r",
                     registry(scan_reason="8", fresh=o.Fresh(how="read", literal=literal)), "img")
    res = r.decide((c,))
    if outcome == "refuted":
        assert res.decided is False
        assert res.decisions[0].outcome == "refuted" and res.decisions[0].evidence == evidence
    else:
        assert res.decided and res.outcome == outcome and res.evidence == evidence


def test_decide_registry_wrong_pod():
    c = r.Candidate("registry registry.invalid (8 workloads failing to pull)", "attributed", "r",
                     registry(scan_reason="8", fresh=o.Fresh(how="read", wrong_pod=True)), "img")
    res = r.decide((c,))
    assert res.outcome == "unverified"
    assert res.evidence == "events of the pulling pod were not read"


def test_decide_registry_read_failed_and_not_read():
    failed = r.Candidate("registry registry.invalid (8 workloads failing to pull)", "attributed", "r",
                          registry(scan_reason="8", fresh=o.Fresh(how="read_failed", message="events is forbidden")), "img")
    res = r.decide((failed,))
    assert res.outcome == "unverified" and res.evidence == "fresh read failed: events is forbidden"

    not_read = r.Candidate("registry registry.invalid (8 workloads failing to pull)", "attributed", "r",
                            registry(scan_reason="8", fresh=o.Fresh(how="not_read")), "img")
    res = r.decide((not_read,))
    assert res.outcome == "unverified" and res.evidence == "not re-read: the read budget was spent first"


# ---------------------------------------------------------------------------
# decide(): candidate-list-level rules
# ---------------------------------------------------------------------------

def test_decide_ruled_out_candidates_are_never_rechecked():
    ruled = r.Candidate("node worker-7 (NotReady)", "ruled_out", "no pod of this workload is scheduled on it",
                         node(name="worker-7", placement="off"), "web")
    res = r.decide((ruled,))
    assert res.decisions == () and res.decided is False


def test_decide_first_confirmed_wins_even_over_an_earlier_unverified():
    unverified_first = r.Candidate("node worker-2 (no kubelet lease)", "attributed", "r",
                                    node(name="worker-2", scan_reason="no kubelet lease", placement="on",
                                         fresh=o.Fresh(how="read", ready="True")), "web")
    confirmed_second = r.Candidate("PVC aux-0 (ProvisioningFailed)", "outranked", "r",
                                    pvc(placement="mounted", fresh=o.Fresh(how="read", phase="Pending")), "db")
    res = r.decide((unverified_first, confirmed_second))
    assert res.decided and res.outcome == "confirmed" and res.cause == "PVC aux-0 (ProvisioningFailed)"


def test_decide_empty_candidates_is_undecided():
    res = r.decide(())
    assert res == r.Result(False, "", "", "", "", "", ())


def test_decide_all_refuted_is_undecided():
    c = r.Candidate("PVC aux-0 (ProvisioningFailed)", "attributed", "r",
                     pvc(placement="mounted", fresh=o.Fresh(how="read", phase="Bound")), "db")
    res = r.decide((c,))
    assert res.decided is False and res.cause == "" and res.outcome == ""


# ---------------------------------------------------------------------------
# shared() and label()
# ---------------------------------------------------------------------------

def _confirmed(cause, obj, ns="db"):
    return r.decide((r.Candidate(cause, "attributed", "r", obj, ns),))


def test_shared_groups_by_key_counts_desc_then_key_asc():
    a = _confirmed("node worker-1 (NotReady)", node(placement="on", fresh=o.Fresh(how="read", ready="False")))
    b = _confirmed("node worker-1 (NotReady)", node(placement="on", fresh=o.Fresh(how="read", ready="False")))
    c1 = _confirmed(
        "PVC search-0 (ProvisionerNotResponding)",
        pvc(name="search-0", placement="mounted", fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    lines = r.shared((a, b, c1))
    assert lines == ("2 workloads share one upstream cause: node worker-1 (NotReady)",)
    assert r.label(lines) == "shared"


def test_shared_caps_at_four_lines_plus_truncation_marker():
    results = []
    for i in range(5):
        n = node(name=f"worker-{i}", placement="on", scan_reason="NotReady",
                 fresh=o.Fresh(how="read", ready="False"))
        results.append(_confirmed(f"node worker-{i} (NotReady)", n))
        results.append(_confirmed(f"node worker-{i} (NotReady)", n))
    lines = r.shared(tuple(results))
    assert len(lines) == 5
    assert lines[-1] == "[truncated by kubeagent]"
    assert r.label(lines) == "shared"


def test_shared_fewer_than_two_confirmed_is_no_line_at_all():
    a = _confirmed("node worker-1 (NotReady)", node(placement="on", fresh=o.Fresh(how="read", ready="False")))
    assert r.shared(()) == ()
    assert r.shared((a,)) == ()
    assert r.label(r.shared((a,))) == "none"


def test_shared_two_or_more_confirmed_but_no_group_of_two_falls_back():
    a = _confirmed("node worker-1 (NotReady)", node(placement="on", fresh=o.Fresh(how="read", ready="False")))
    b = _confirmed("node worker-5 (NotReady)",
                    node(name="worker-5", placement="on", fresh=o.Fresh(how="read", ready="Unknown")))
    lines = r.shared((a, b))
    assert lines == ("no shared cause among the 2 workloads confirmed by rules",)
    assert r.label(lines) == "separate"


def test_shared_ignores_undecided_and_unverified_results():
    a = _confirmed("node worker-1 (NotReady)", node(placement="on", fresh=o.Fresh(how="read", ready="False")))
    unverified = r.decide((r.Candidate(
        "node worker-2 (no kubelet lease)", "attributed", "r",
        node(name="worker-2", scan_reason="no kubelet lease", placement="on", fresh=o.Fresh(how="read", ready="True")),
        "web",
    ),))
    undecided = r.decide(())
    assert r.shared((a, unverified, undecided)) == ()


def test_shared_pvc_group_by_storage_class_when_reason_and_class_are_plain():
    a = _confirmed(
        "PVC cache-0 (ProvisionerNotResponding)",
        pvc(name="cache-0", placement="mounted", fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    b = _confirmed(
        "PVC search-0 (ProvisionerNotResponding)",
        pvc(name="search-0", placement="mounted", fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    assert a.group_key == "storageclass/standard/ProvisionerNotResponding"
    assert a.group_text == "storage class standard (ProvisionerNotResponding)"
    lines = r.shared((a, b))
    assert lines == ("2 workloads share one upstream cause: storage class standard (ProvisionerNotResponding)",)


def test_shared_pvc_group_by_class_only_for_the_two_qualifying_reasons():
    # ProvisioningFailed is not one of the two grouping reasons, so this
    # groups per claim name even though two PVCs share a storage class.
    a = _confirmed(
        "PVC aux-0 (ProvisioningFailed)",
        pvc(name="aux-0", placement="mounted", fresh=o.Fresh(how="read", phase="Pending", storage_class="fast-ssd")))
    assert a.group_key == "pvc/db/aux-0"


def test_shared_pvc_group_falls_back_to_claim_name_for_a_hostile_class():
    a = _confirmed(
        "PVC cache-0 (ProvisionerNotResponding)",
        pvc(name="cache-0", placement="mounted",
            fresh=o.Fresh(how="read", phase="Pending", storage_class="Not Plain!")))
    assert a.group_key == "pvc/db/cache-0"


def test_shared_registry_groups_by_host():
    a = _confirmed("registry registry.invalid (8 workloads failing to pull)",
                    registry(scan_reason="8", fresh=o.Fresh(how="read", literal="connection refused")))
    b = _confirmed("registry registry.invalid (8 workloads failing to pull)",
                    registry(scan_reason="8", fresh=o.Fresh(how="read", literal="i/o timeout")))
    assert a.group_key == b.group_key == "registry/registry.invalid"
    lines = r.shared((a, b))
    assert lines == (
        "2 workloads share one upstream cause: registry registry.invalid (8 workloads failing to pull)",)


def test_shared_three_pvcs_provisioner_not_responding_group_by_class():
    a = _confirmed("PVC aux-0 (ProvisionerNotResponding)",
                    pvc(name="aux-0", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    b = _confirmed("PVC aux-1 (ProvisionerNotResponding)",
                    pvc(name="aux-1", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    c = _confirmed("PVC aux-2 (ProvisionerNotResponding)",
                    pvc(name="aux-2", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    lines = r.shared((a, b, c))
    assert lines == ("3 workloads share one upstream cause: storage class standard (ProvisionerNotResponding)",)
    assert r.label(lines) == "shared"


def test_shared_three_pvcs_provisioning_failed_stays_separate():
    a = _confirmed("PVC aux-0 (ProvisioningFailed)",
                    pvc(name="aux-0", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    b = _confirmed("PVC aux-1 (ProvisioningFailed)",
                    pvc(name="aux-1", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    c = _confirmed("PVC aux-2 (ProvisioningFailed)",
                    pvc(name="aux-2", placement="mounted",
                        fresh=o.Fresh(how="read", phase="Pending", storage_class="standard")))
    lines = r.shared((a, b, c))
    assert lines == ("no shared cause among the 3 workloads confirmed by rules",)
    assert r.label(lines) == "separate"


# ---------------------------------------------------------------------------
# read_text()
# ---------------------------------------------------------------------------

def test_read_text_node_ready_read():
    n = node(placement="on", fresh=o.Fresh(
        how="read", ready="False", unschedulable=False,
        extra=(
            "  condition Ready=False (KubeletNotReady): container runtime is down",
            "  taint node.kubernetes.io/not-ready=:NoSchedule",
        )))
    label, content = r.read_text(n, ns="web", pod="web-abc")
    assert label == "describe node /worker-1"
    assert content == (
        "node worker-1: unschedulable=false\n"
        "  condition Ready=False (KubeletNotReady): container runtime is down\n"
        "  taint node.kubernetes.io/not-ready=:NoSchedule\n"
    )


def test_read_text_node_unschedulable_true():
    n = node(placement="on", fresh=o.Fresh(how="read", ready="Unknown", unschedulable=True))
    _, content = r.read_text(n, ns="web", pod="web-abc")
    assert content.startswith("node worker-1: unschedulable=true\n")


def test_read_text_node_read_failed():
    n = node(name="worker-7", placement="on",
             fresh=o.Fresh(how="read_failed", message='nodes "worker-7" is forbidden'))
    label, content = r.read_text(n, ns="web", pod="web-abc")
    assert label == "describe node /worker-7"
    assert content == 'read failed: nodes "worker-7" is forbidden'


def test_read_text_pvc_read():
    p = pvc(placement="mounted", fresh=o.Fresh(how="read", phase="Bound", storage_class="fast-ssd", volume="pv-0442"))
    label, content = r.read_text(p, ns="db", pod="db-xyz")
    assert label == "describe pvc db/aux-0"
    assert content == "pvc db/aux-0: phase=Bound storageClass=fast-ssd volume=pv-0442\n"


def test_read_text_pvc_read_failed():
    p = pvc(name="aux-1", placement="mounted",
            fresh=o.Fresh(how="read_failed", message='persistentvolumeclaims "aux-1" is forbidden'))
    label, content = r.read_text(p, ns="db", pod="db-xyz")
    assert label == "describe pvc db/aux-1"
    assert content == 'read failed: persistentvolumeclaims "aux-1" is forbidden'


def test_read_text_refuses_a_registry_object():
    reg = registry()
    with pytest.raises(ValueError) as err:
        r.read_text(reg, ns="img", pod="img-1")
    assert "registry" in str(err.value) and "no object to read" in str(err.value)


# ---------------------------------------------------------------------------
# check_declaration()
# ---------------------------------------------------------------------------

def test_check_declaration_accepts_a_winning_cause_of_each_kind():
    r.check_declaration("e1", (node(placement="on", intent="cause"),))
    r.check_declaration("e2", (pvc(placement="mounted", intent="cause"),))
    r.check_declaration("e3", (registry(scan_reason="2", intent="cause"),))


def test_check_declaration_rejects_a_node_cause_that_is_not_on():
    with pytest.raises(ValueError) as err:
        r.check_declaration("e1", (node(placement="off", intent="cause"),))
    assert "e1" in str(err.value) and "node/worker-1" in str(err.value)


def test_check_declaration_rejects_a_pvc_cause_that_is_not_mounted():
    with pytest.raises(ValueError) as err:
        r.check_declaration("e1", (pvc(placement="unmounted", intent="cause"),))
    assert "pvc/aux-0" in str(err.value)


def test_check_declaration_rejects_a_registry_cause_with_no_name():
    with pytest.raises(ValueError) as err:
        r.check_declaration("e1", (registry(name="", scan_reason="0", intent="cause"),))
    assert "registry" in str(err.value) and "no name" in str(err.value)


def test_check_declaration_rejects_a_registry_cause_below_threshold():
    with pytest.raises(ValueError) as err:
        r.check_declaration("e1", (registry(scan_reason="1", intent="cause"),))
    assert "registry/registry.invalid" in str(err.value) and "REGISTRY_THRESHOLD" in str(err.value)


def test_check_declaration_ignores_a_decoy_with_the_same_shape():
    # A decoy candidate never needs to be able to win; only a declared
    # cause does.
    r.check_declaration("e1", (node(placement="off", intent="decoy"),))


def test_check_declaration_still_runs_objects_check_objects():
    with pytest.raises(ValueError) as err:
        r.check_declaration("e1", (node(placement="on"), node(placement="off")))
    assert "declared twice" in str(err.value)


# ---------------------------------------------------------------------------
# Replay: the v1.24.0 capture fixture (Task 2), byte for byte
# ---------------------------------------------------------------------------
#
# This roster is Task 2's own capture roster (kv_capture_test.go.txt),
# carried into Python: the same 6 down nodes, the same 8 PVC issues in
# db, the same 2 registry hosts, and the same 12 workloads, in the same
# order captureWorkloads() returns them. registry.invalid's puller count
# (7) is copied straight from the fixture's own `shared` line — see
# _REGISTRY_INVALID_COUNT below. Everything else here is this file's own
# best reading of the capture test source. If Task 2's real capture
# differs from any of it, the values below are wrong and must be
# corrected to match — the fixture is always the pin, never this file
# (see the module docstring).

_NODE_DEFS = {
    "worker-1": {"scan_reason": "NotReady", "fresh": o.Fresh(
        how="read", ready="False",
        extra=(
            "  condition Ready=False (KubeletNotReady): container runtime is down",
            "  taint node.kubernetes.io/not-ready=:NoSchedule",
        ))},
    "worker-2": {"scan_reason": "no kubelet lease", "fresh": o.Fresh(
        how="read", ready="True",
        extra=(
            "  condition Ready=True (KubeletReady): kubelet is posting ready status",
        ))},
    "worker-3": {"scan_reason": "kubelet not heartbeating", "fresh": o.Fresh(how="not_read")},
    "worker-5": {"scan_reason": "NotReady", "fresh": o.Fresh(
        how="read", ready="Unknown",
        extra=(
            "  condition Ready=Unknown (NodeStatusUnknown): Kubelet stopped posting node status.",
        ))},
    "worker-6": {"scan_reason": "NotReady", "fresh": o.Fresh(how="read", ready="missing")},
    "worker-7": {"scan_reason": "NotReady",
                      "fresh": o.Fresh(how="read_failed", message='nodes "worker-7" is forbidden')},
}
_NODE_NAMES = ("worker-1", "worker-2", "worker-3", "worker-5", "worker-6", "worker-7")


def _nodes_for(on: frozenset[str]) -> tuple[o.Object, ...]:
    return tuple(
        o.Object(kind="node", name=name, placement=("on" if name in on else "off"), **_NODE_DEFS[name])
        for name in _NODE_NAMES
    )


_PVC_DEFS = {
    "aux-0": {"scan_reason": "ProvisioningFailed",
              "fresh": o.Fresh(how="read", phase="Bound", storage_class="fast-ssd", volume="pv-0442")},
    "aux-1": {"scan_reason": "ProvisioningFailed",
              "fresh": o.Fresh(how="read_failed", message='persistentvolumeclaims "aux-1" is forbidden')},
    "aux-2": {"scan_reason": "ProvisioningFailed",
              "fresh": o.Fresh(how="read", phase="Released", storage_class="fast-ssd")},
    "aux-3": {"scan_reason": "ProvisioningFailed", "fresh": o.Fresh(how="not_read")},
    "aux-4": {"scan_reason": "ProvisioningFailed", "fresh": o.Fresh(how="not_read")},
    "cache-0": {"scan_reason": "ProvisionerNotResponding",
                     "fresh": o.Fresh(how="read", phase="Pending", storage_class="standard")},
    "data-0": {"scan_reason": "FailedBinding",
                    "fresh": o.Fresh(how="read", phase="Lost", storage_class="fast-ssd", volume="pv-0821")},
    "search-0": {"scan_reason": "ProvisionerNotResponding",
                      "fresh": o.Fresh(how="read", phase="Pending", storage_class="standard")},
}
_PVC_NAMES = ("aux-0", "aux-1", "aux-2", "aux-3", "aux-4", "cache-0", "data-0", "search-0")


def _pvcs_for(mounted: frozenset[str]) -> tuple[o.Object, ...]:
    return tuple(
        o.Object(kind="pvc", name=name, placement=("mounted" if name in mounted else "unmounted"),
                  **_PVC_DEFS[name])
        for name in _PVC_NAMES
    )


# registry.invalid's puller count is pinned at 7, matching real Go's
# AnnotateRegistry: web/frontend also references registry.invalid, but its
# RootCause is already set by the earlier node pass (worker-1 is "on"), so
# AnnotateRegistry excludes it from the host's tally — real Go only counts
# workloads that are still undecided when the registry pass runs. This
# roster's own img/* count referencing registry.invalid is also 7 (one,
# two, three, five, six, seven, eight); web/frontend is the 8th reference
# and is the one AnnotateRegistry skips. scan_reason is a declarative
# input, so it is set straight from the pin rather than computed here.
# mirror.invalid never clears the threshold: it is img/lone's sole puller.
_REGISTRY_INVALID_COUNT = "7"
_MIRROR_INVALID_COUNT = "1"


def _registry(name: str, count: str, **fresh_kw) -> tuple[o.Object, ...]:
    return (o.Object(kind="registry", name=name, scan_reason=count, placement="",
                      fresh=o.Fresh(how="read", **fresh_kw)),)


# (namespace, name, pod, issue, objects) — captureWorkloads()'s own order.
ROSTER = [
    {"namespace": "web", "name": "frontend", "pod": "frontend-5b8d7f6c9-q2w3e", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset({"worker-1", "worker-3", "worker-5", "worker-6", "worker-7"}))
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, literal="manifest unknown")},
    {"namespace": "db", "name": "postgres", "pod": "postgres-0", "issue": "Pending",
     "objects": _nodes_for(frozenset())
                 + _pvcs_for(frozenset({"aux-0", "aux-1", "aux-2", "data-0"}))},
    {"namespace": "db", "name": "cache", "pod": "cache-0", "issue": "Pending",
     "objects": _nodes_for(frozenset({"worker-2"}))
                 + _pvcs_for(frozenset({"cache-0"}))},
    {"namespace": "db", "name": "search", "pod": "search-0", "issue": "Pending",
     "objects": _nodes_for(frozenset())
                 + _pvcs_for(frozenset({"search-0"}))},
    {"namespace": "img", "name": "one", "pod": "one-7c9d4b5f6-abcde", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset())
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, literal="connection refused")},
    {"namespace": "img", "name": "two", "pod": "two-7c9d4b5f6-bcdef", "issue": "ErrImagePull",
     "objects": _nodes_for(frozenset())
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, literal="i/o timeout")},
    {"namespace": "img", "name": "three", "pod": "three-7c9d4b5f6-cdefg", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset())
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, literal="unauthorized")},
    {"namespace": "img", "name": "five", "pod": "five-7c9d4b5f6-defgh", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset())
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, literal="")},
    {"namespace": "img", "name": "six", "pod": "six-6f8e9d0a1-crash", "issue": "ImagePullBackOff",
     # The fixture's own pod for img/six is the CRASH pod (six-a), the
     # first finding kubeagent's own eventsPod(w) reads — not the pull
     # pod (six-b). Its events read hits the crash pod, so its registry
     # candidate's fresh read is wrong_pod=True. See Task 2's own note:
     # "For img/six the fixture's pod is the crash pod, and Python's
     # Object for its registry carries wrong_pod=True." attribute()'s
     # own `issue` argument still has to be "ImagePullBackOff" here —
     # that is what makes a registry candidate exist at all — even
     # though the workload's first *finding* is CrashLoopBackOff; the
     # caller (a later task's builder) is the one that decides which of
     # a multi-finding workload's issues governs registry attribution.
     "objects": _nodes_for(frozenset())
                 + _registry("registry.invalid", _REGISTRY_INVALID_COUNT, wrong_pod=True)},
    {"namespace": "img", "name": "lone", "pod": "lone-7c9d4b5f6-efghi", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset())
                 + _registry("mirror.invalid", _MIRROR_INVALID_COUNT)},
    {"namespace": "img", "name": "seven", "pod": "seven-7c9d4b5f6-fghij", "issue": "ImagePullBackOff",
     # _registry()'s **fresh_kw shortcut only ever sets how="read"; a
     # read-failed registry needs its own how and message, so it is
     # built directly rather than through that helper.
     "objects": _nodes_for(frozenset())
                 + (o.Object(kind="registry", name="registry.invalid", scan_reason=_REGISTRY_INVALID_COUNT,
                             placement="", fresh=o.Fresh(how="read_failed", message="events is forbidden")),)},
    {"namespace": "img", "name": "eight", "pod": "eight-7c9d4b5f6-ghijk", "issue": "ImagePullBackOff",
     "objects": _nodes_for(frozenset())
                 + (o.Object(kind="registry", name="registry.invalid", scan_reason=_REGISTRY_INVALID_COUNT,
                             placement="", fresh=o.Fresh(how="not_read")),)},
]


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _replay(entry):
    candidates = r.attribute(entry["objects"], ns=entry["namespace"], pod=entry["pod"], issue=entry["issue"])
    result = r.decide(candidates)
    return candidates, result


@pytest.mark.parametrize("index", range(12))
def test_port_matches_fixture_candidates_and_result(index):
    fixture = _fixture()
    fx_workload = fixture["workloads"][index]
    entry = ROSTER[index]
    assert (fx_workload["namespace"], fx_workload["name"]) == (entry["namespace"], entry["name"])

    candidates, result = _replay(entry)
    got_candidates = [{"cause": c.cause, "verdict": c.verdict, "reason": c.reason} for c in candidates]
    fx_candidates = [{"cause": c["cause"], "verdict": c["verdict"], "reason": c["reason"]}
                      for c in fx_workload["candidates"]]
    assert got_candidates == fx_candidates

    fx_result = fx_workload["result"]
    assert result.decided == fx_result["decided"]
    assert result.cause == fx_result["cause"]
    assert result.outcome == fx_result["outcome"]
    assert result.evidence == fx_result["evidence"]
    assert result.group_key == fx_result["group_key"]
    assert result.group_text == fx_result["group_text"]
    got_decisions = [{"candidate": d.candidate, "outcome": d.outcome, "evidence": d.evidence}
                      for d in result.decisions]
    fx_decisions = [{"candidate": d["candidate"], "outcome": d["outcome"], "evidence": d["evidence"]}
                     for d in fx_result["decisions"]]
    assert got_decisions == fx_decisions


def test_shared_matches_fixture_over_all_twelve_results():
    fixture = _fixture()
    results = tuple(_replay(entry)[1] for entry in ROSTER)
    assert list(r.shared(results)) == fixture["shared"]


# Six of the fixture's eight reads are a node or a PVC describe; read_text()
# covers both. The other two are "events ..." reads (img/one and img/five),
# outside read_text()'s scope (see the module docstring) — they are pinned
# directly against the fixture's own bytes instead of round-tripped through
# a function.
_READ_TEXT_CASES = [
    # (fixture index, roster index, object name/kind lookup, ns, pod)
    (0, 0, ("node", "worker-1"), "web", "frontend-5b8d7f6c9-q2w3e"),
    (1, 2, ("node", "worker-2"), "db", "cache-0"),
    (2, 1, ("pvc", "aux-0"), "db", "postgres-0"),
    (3, 1, ("pvc", "data-0"), "db", "postgres-0"),
    (4, 2, ("pvc", "cache-0"), "db", "cache-0"),
    (7, 0, ("node", "worker-7"), "web", "frontend-5b8d7f6c9-q2w3e"),
]


@pytest.mark.parametrize("fixture_index, roster_index, lookup, ns, pod", _READ_TEXT_CASES)
def test_read_text_matches_fixture(fixture_index, roster_index, lookup, ns, pod):
    fixture = _fixture()
    fx_read = fixture["reads"][fixture_index]
    kind, name = lookup
    entry = ROSTER[roster_index]
    obj = next(o for o in entry["objects"] if o.kind == kind and o.name == name)
    label, content = r.read_text(obj, ns=ns, pod=pod)
    assert label == fx_read["label"]
    assert content == fx_read["content"]


def test_events_reads_are_pinned_literals_outside_read_text_scope():
    fixture = _fixture()
    one, five = fixture["reads"][5], fixture["reads"][6]
    assert one["label"] == "events img/one-7c9d4b5f6-abcde"
    assert one["content"] == (
        'events for img/one-7c9d4b5f6-abcde:\n'
        '  Failed: Failed to pull image "registry.invalid/img/one:1.0": connection refused (x4)\n'
    )
    assert five["label"] == "events img/five-7c9d4b5f6-defgh"
    assert five["content"] == "no events for img/five-7c9d4b5f6-defgh"


def test_fixture_pins_the_kubeagent_version():
    fixture = _fixture()
    assert fixture["kubeagent"] == {"tag": "v1.24.0", "commit": "15ec5649bbd2d07558eae945b71430afc8f231fd"}
    assert len(fixture["workloads"]) == 12
    assert len(fixture["reads"]) == 8
