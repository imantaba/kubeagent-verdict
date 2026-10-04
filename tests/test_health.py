"""The pure port of kubeagent's cluster health, service health and
network-policy pieces (v1.24.0). The CLUSTER capture pins the same code
byte for byte (tests/test_gather_byte_equal.py); these tests name each rule."""

from __future__ import annotations

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import health as h


def _wl(name, *, ns="kube-system", kind="Deployment", ready=0, desired=2,
        status="CrashLoopBackOff", findings=()):
    return c.Workload(ns, name, kind, ready, desired, status, 0, findings)


def _f(issue="CrashLoopBackOff"):
    return c.Finding(issue, "r", "e", "n", "cmd")


def _down(reason="KubeletNotReady", message="container runtime is down"):
    return h.Condition("Ready", "False", reason, message)


@pytest.mark.parametrize("ms, want", [
    (0, "0s"), (499, "0s"), (500, "1s"), (40_400, "40s"), (42_500, "43s"),
    (59_500, "1m0s"), (95_000, "1m35s"), (3_600_000, "1h0m0s"),
    (3_700_000, "1h1m40s"), (90_061_000, "25h1m1s"),
])
def test_go_duration_is_round_to_the_second_then_string(ms, want):
    assert h.go_duration(ms) == want


def test_notready_message_cut_counts_runes():
    msg = "a" * 114 + "é" + "b" * 15  # 130 runes, 131 bytes
    got = h.not_ready_issue("KubeletNotReady", msg)
    assert got == "NotReady: KubeletNotReady — " + "a" * 114 + "é" + "b" * 5 + "…"


@pytest.mark.parametrize("reason, message, want", [
    ("KubeletNotReady", "runtime down", "NotReady: KubeletNotReady — runtime down"),
    ("KubeletNotReady", "", "NotReady: KubeletNotReady"),
    ("", "PLEG is not healthy", "NotReady: PLEG is not healthy"),
    ("", "", "NotReady"),
])
def test_not_ready_issue_forms(reason, message, want):
    assert h.not_ready_issue(reason, message) == want


def test_an_unknown_condition_type_fails_at_load():
    with pytest.raises(ValueError, match="FrequentKubeletRestart"):
        h.Condition("FrequentKubeletRestart", "True")


def test_an_unknown_lease_fails_at_load():
    with pytest.raises(ValueError, match="stale"):
        h.Node("a", (h.READY,), lease="stale")


def test_issue_order_is_pressure_then_notready_then_cordon():
    n = h.Node("a", (h.Condition("MemoryPressure", "True"), h.Condition("DiskPressure", "True"),
                     _down()), unschedulable=True)
    got, down = h.assess([n, h.Node("b", (h.READY,)), h.Node("c", (h.READY,))], [])
    assert got.node_issues == ("a MemoryPressure", "a DiskPressure",
                               "a NotReady: KubeletNotReady — container runtime is down",
                               "a SchedulingDisabled")
    assert down == (h.DownNode("a", "NotReady"),)
    assert (got.nodes_ready, got.nodes_total) == (2, 3)


def test_the_lease_line_comes_after_the_cordon():
    n = h.Node("a", (h.READY,), unschedulable=True, lease_age_ms=41_000)
    got, _ = h.assess([n], [])
    assert got.node_issues == ("a SchedulingDisabled",
                               "a kubelet not heartbeating (lease 41s stale)")


def test_stale_lease_node_still_counts_ready():
    nodes = [h.Node("a", (h.READY,), lease_age_ms=50_000), h.Node("b", (h.READY,)),
             h.Node("c", (h.READY,))]
    got, down = h.assess(nodes, [])
    assert (got.degraded, got.nodes_ready, got.nodes_total) == (True, 3, 3)
    assert got.node_issues == ("a kubelet not heartbeating (lease 50s stale)",)
    assert down == (h.DownNode("a", "kubelet not heartbeating"),)


def test_staleness_is_judged_on_raw_milliseconds():
    at, over = h.Node("a", (h.READY,), lease_age_ms=40_000), h.Node("a", (h.READY,), lease_age_ms=40_001)
    assert h.assess([at], []) == (None, ())
    assert h.assess([over], [])[0].node_issues == ("a kubelet not heartbeating (lease 40s stale)",)
    assert h.assess([h.Node("a", (h.READY,), lease_age_ms=3_600_000)], [], threshold_ms=0) == (None, ())


@pytest.mark.parametrize("lease", ["missing", "no_renew"])
def test_a_missing_or_unrenewed_lease_prints_no_kubelet_lease(lease):
    got, down = h.assess([h.Node("a", (h.READY,), lease=lease)], [])
    assert got.node_issues == ("a no kubelet lease",)
    assert down == (h.DownNode("a", "no kubelet lease"),)
    assert got.nodes_ready == 1


def test_a_not_ready_node_is_not_lease_checked():
    got, down = h.assess([h.Node("a", (_down(),), lease="missing")], [])
    assert got.node_issues == ("a NotReady: KubeletNotReady — container runtime is down",)
    assert down == (h.DownNode("a", "NotReady"),)


def test_no_ready_condition_is_not_ready():
    got, _ = h.assess([h.Node("a", (h.Condition("DiskPressure", "False"),))], [])
    assert got.node_issues == ("a NotReady",)


def test_the_last_ready_condition_wins():
    got, _ = h.assess([h.Node("a", (_down(), h.READY))], [])
    assert got is None


def test_detector_conditions_print_nothing():
    n = h.Node("a", (h.Condition("NetworkUnavailable", "True", "NoRouteCreated"),
                     h.Condition("ReadonlyFilesystem", "True", "FilesystemIsReadOnly"),
                     h.Condition("CorruptDockerOverlay2", "True"), h.READY))
    assert h.assess([n], []) == (None, ())


def test_node_lines_are_in_name_order():
    nodes = [h.Node("b", (_down(),)), h.Node("a", (_down(),))]
    got, down = h.assess(nodes, [])
    assert [i.split()[0] for i in got.node_issues] == ["a", "b"]
    assert [d.name for d in down] == ["a", "b"]


def test_job_system_line_has_no_counts():
    cron = _wl("nightly", kind="CronJob", ready=0, desired=1,
               status="BackoffLimitExceeded (3 of 3 failed)")
    dns = _wl("coredns", ready=0, desired=2, findings=(_f(),))
    calm = _wl("kube-proxy", kind="DaemonSet", ready=3, desired=3, status="Running")
    other = _wl("api", ns="shop", findings=(_f(),))
    got, _ = h.assess([h.Node("a", (h.READY,))], [cron, dns, calm, other])
    assert got.system_issues == ("kube-system/coredns 0/2 CrashLoopBackOff",
                                 "kube-system/nightly BackoffLimitExceeded (3 of 3 failed)")
    assert got.node_issues == ()


def test_a_healthy_cluster_has_no_block():
    assert h.assess([h.Node(x, (h.READY,)) for x in "abc"], [_wl("x", ns="shop")]) == (None, ())


def test_condition_text_passes_safetext_first():
    got, _ = h.assess([h.Node("a", (_down("KubeletNotReady", "runtime\ndown\x07"),))], [])
    assert got.node_issues == ("a NotReady: KubeletNotReady — runtime down",)


# --- Service issues (svchealth.Assess, AnnotateEndpointCause).

_SEL = (("app", "x"),)


def _svc(name="s", **kw):
    return h.Service("svc", name, selector=kw.pop("selector", _SEL), **kw)


def _details(services, slices=(), backends=(), pods=(), down=()):
    issues = h.service_issues(services, slices, backends)
    return [i.detail for i in h.annotate_endpoint_cause(issues, services, pods, down)]


def test_a_load_balancer_with_no_ingress_has_no_external_address():
    s = _svc(type="LoadBalancer")
    pod = h.Pod("svc", "p", "w1", _SEL, True)
    assert _details([s], [h.EndpointSlice("svc", "s", ("true",))], pods=[pod]) == ["no external address"]


def test_an_empty_selector_gets_no_endpoint_check():
    assert _details([_svc(selector=())]) == []


def test_external_name_is_skipped():
    assert _details([_svc(type="ExternalName")]) == []


def test_unset_ready_counts_as_ready():
    pod = h.Pod("svc", "p", "w1", _SEL, False)
    assert _details([_svc()], [h.EndpointSlice("svc", "s", ("unset",))], pods=[pod]) == []


def test_a_slice_for_another_service_does_not_count():
    pod = h.Pod("svc", "p", "w1", _SEL, True)
    assert _details([_svc()], [h.EndpointSlice("svc", "other", ("true",))], pods=[pod]) == \
        ["no ready endpoints"]


def test_expected_empty_annotation():
    s = _svc(annotations=(("kubeagent.io/expected-empty", "TRUE"),))
    assert _details([s]) == ["no ready endpoints — declared via kubeagent.io/expected-empty"]


@pytest.mark.parametrize("kind, desired, want", [
    ("CronJob", 1, "no ready endpoints (backs CronJob — expected between runs)"),
    ("Job", 1, "no ready endpoints (backs Job — expected between runs)"),
    ("DaemonSet", 0, "no ready endpoints (backs DaemonSet — 0 desired)"),
    ("Deployment", 0, "no ready endpoints (backs Deployment — scaled to 0)"),
    ("StatefulSet", 0, "no ready endpoints (backs StatefulSet — scaled to 0)"),
])
def test_a_backing_workload_explains_the_empty_service(kind, desired, want):
    assert _details([_svc()], backends=[h.Backend("svc", kind, _SEL, desired)]) == [want]


def test_a_live_backend_makes_the_service_unexpected():
    backends = [h.Backend("svc", "CronJob", _SEL, 1), h.Backend("svc", "Deployment", _SEL, 2)]
    assert _details([_svc()], backends=backends) == ["no ready endpoints — the selector matches no pods"]


def test_the_backing_kind_is_the_first_in_go_order():
    backends = [h.Backend("svc", "Deployment", _SEL, 0), h.Backend("svc", "Job", _SEL, 1)]
    assert _details([_svc()], backends=backends) == \
        ["no ready endpoints (backs Job — expected between runs)"]


@pytest.mark.parametrize("pods, down, want", [
    ((), (), "no ready endpoints — the selector matches no pods"),
    ((("p1", "w1", False),), (h.DownNode("w1", "NotReady"),),
     "no ready endpoints — matching pods on down node w1 (NotReady)"),
    ((("p1", "w1", False), ("p2", "w1", False)), (h.DownNode("w1", "no kubelet lease"),),
     "no ready endpoints — matching pods on down node w1 (no kubelet lease)"),
    ((("p1", "w1", False), ("p2", "w2", False)),
     (h.DownNode("w1", "NotReady"), h.DownNode("w2", "NotReady")),
     "no ready endpoints — matching pods on 2 down nodes"),
    ((("p1", "w3", False),), (), "no ready endpoints — 1 matching pod, 0 ready"),
    ((("p1", "w3", False), ("p2", "w3", False), ("p3", "", False)), (),
     "no ready endpoints — 3 matching pods, 0 ready"),
    ((("p1", "w3", True),), (), "no ready endpoints"),
])
def test_the_endpoint_cause(pods, down, want):
    hp = [h.Pod("svc", n, node, _SEL, ready) for n, node, ready in pods]
    assert _details([_svc()], pods=hp, down=down) == [want]


def test_pods_in_another_namespace_do_not_match():
    pod = h.Pod("other", "p", "w1", _SEL, False)
    assert _details([_svc()], pods=[pod]) == ["no ready endpoints — the selector matches no pods"]


def test_service_issues_sort_by_namespace_name_problem():
    lb = _svc("a", type="LoadBalancer")
    got = h.service_issues([_svc("b"), lb], (), ())
    assert [(i.name, i.problem) for i in got] == [("a", "NoEndpoints"), ("a", "NoExternalAddress"),
                                                 ("b", "NoEndpoints")]
    assert got[0].contract() == c.ServiceIssue("svc", "a", "LoadBalancer", "no ready endpoints")


# --- Network policies (netpolicy.Annotate).

_POD = h.Pod("app", "web-1", "w1", (("app", "web"), ("tier", "fe")))


def test_selecting_policies_sorted_and_deduped():
    pols = [h.NetworkPolicy("app", "deny-web", (("app", "web"),)),
            h.NetworkPolicy("app", "allow-web", (("app", "web"),)),
            h.NetworkPolicy("app", "other", (("app", "db"),)),
            h.NetworkPolicy("elsewhere", "far", (("app", "web"),))]
    assert h.selecting_policies("app", [_POD, _POD], pols) == ("allow-web", "deny-web")


def test_an_empty_pod_selector_selects_every_pod():
    assert h.selecting_policies("app", [_POD], [h.NetworkPolicy("app", "all")]) == ("all",)


def test_policies_print_only_when_every_finding_is_a_probe_failure():
    pols = [h.NetworkPolicy("app", "deny-web", (("app", "web"),))]
    probe = _wl("web", ns="app", findings=(_f("ProbeFailure"),))
    mixed = _wl("web", ns="app", findings=(_f("ProbeFailure"), _f()))
    bare = _wl("web", ns="app", ready=0, desired=2)
    calm = _wl("web", ns="app", ready=2, desired=2, status="Running")
    assert h.network_policies_for(probe, [_POD], pols) == ("deny-web",)
    assert h.network_policies_for(mixed, [_POD], pols) == ()
    assert h.network_policies_for(bare, [_POD], pols) == ("deny-web",)
    assert h.network_policies_for(calm, [_POD], pols) == ()
