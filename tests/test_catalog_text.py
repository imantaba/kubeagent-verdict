"""The catalog prints the text kubeagent really prints.

Every expected string here is written by hand from kubeagent v1.24.0's
own source, cited next to it:

- the node describe, a port of `describeNode`
  (internal/investigate/reader.go:238-248), with the kubelet's own
  condition reasons and messages;
- each finding line, copied from the detector that prints it
  (internal/diagnose/);
- the scheduler messages, with the preemption suffix the default
  scheduler profile adds.

The tests assert the rendered prompt text, not only the catalog field.
"""
from __future__ import annotations

import collections
import dataclasses
import random
import re

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, gather, generate, names, render
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import rules as r

N = names.Names(ns="shop", name="api", pod="api-7f9c4d5b6-x2x9k", container="app",
                init_container="init-config", image="registry.example.com/shop/api:v1.2.3",
                node="worker-2", pvc="data-0", restarts=14)
NAMES = dataclasses.asdict(N)

# The kubelet's condition text (pkg/kubelet/nodestatus/setters.go), in the
# order the kubelet sets the conditions: MemoryPressure, DiskPressure,
# PIDPressure, Ready.
MEMORY_OK = ("  condition MemoryPressure=False (KubeletHasSufficientMemory): "
             "kubelet has sufficient memory available\n")
DISK_OK = "  condition DiskPressure=False (KubeletHasNoDiskPressure): kubelet has no disk pressure\n"
DISK_PRESSURE = "  condition DiskPressure=True (KubeletHasDiskPressure): kubelet has disk pressure\n"
PID_OK = ("  condition PIDPressure=False (KubeletHasSufficientPID): "
          "kubelet has sufficient PID available\n")
READY_TRUE = "  condition Ready=True (KubeletReady): kubelet is posting ready status\n"
READY_DESCRIBE = "node worker-2: unschedulable=false\n" + MEMORY_OK + DISK_OK + PID_OK + READY_TRUE
# pkg/kubelet/runtime.go:129
READY_FALSE = "  condition Ready=False (KubeletNotReady): container runtime is down\n"

# The default scheduler profile adds this after every FailedScheduling
# message when preemption cannot help.
PREEMPTION = " preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling."


def _entry(key: str) -> catalog.CatalogEntry:
    return next(e for e in catalog.all_entries() if e.key == key)


def _node(fresh: o.Fresh, *, name: str = "worker-2") -> o.Object:
    return o.Object(kind="node", name=name, scan_reason="NotReady", placement="on", fresh=fresh)


# --- describeNode port ------------------------------------------------------

def test_describe_node_redacts_an_address_in_a_condition_message():
    # internal/investigate/reader_test.go:361
    # (TestReader_DescribeNode_SanitizesConditionMessage)
    got = r.describe_node("node-1", unschedulable=False, conditions=(
        ("Ready", "False", "KubeletNotReady", "container runtime unreachable at 10.96.0.30:6443"),
    ), taints=())
    assert "10.96.0.30:6443" not in got
    assert got == ("node node-1: unschedulable=false\n"
                   "  condition Ready=False (KubeletNotReady): "
                   "container runtime unreachable at <redacted>\n")


def test_describe_node_writes_the_go_format():
    # reader.go:240-246: the header, one line per condition in the node's own
    # order, then one line per taint. Go's %s prints an empty taint value as
    # nothing, so a taint with no value reads `key=:Effect`.
    got = r.describe_node("worker-1", unschedulable=True, conditions=(
        ("DiskPressure", "True", "KubeletHasDiskPressure", "kubelet has disk pressure"),
        ("Ready", "True", "KubeletReady", "kubelet is posting ready status"),
    ), taints=(
        ("node.kubernetes.io/unschedulable", "", "NoSchedule"),
        ("dedicated", "gpu", "NoExecute"),
    ))
    assert got == ("node worker-1: unschedulable=true\n"
                   + DISK_PRESSURE + READY_TRUE
                   + "  taint node.kubernetes.io/unschedulable=:NoSchedule\n"
                   "  taint dedicated=gpu:NoExecute\n")


def test_describe_node_sanitizes_the_reason_too():
    # reader.go:242 passes cond.Reason through sanitize, not only cond.Message.
    got = r.describe_node("worker-1", unschedulable=False, conditions=(
        ("Ready", "False", "Kubelet\x07NotReady", "container runtime is down"),
    ), taints=())
    assert got.endswith(READY_FALSE)


def test_describe_node_with_no_conditions_is_its_header():
    # investigate/gather_test.go:49 describes a node with no conditions.
    got = r.describe_node("worker-1", unschedulable=False, conditions=(), taints=())
    assert got == "node worker-1: unschedulable=false\n"


# --- K2 and K4: the node read -------------------------------------------------

def test_a_ready_node_prints_the_four_healthy_conditions():
    label, content = r.read_text(_node(o.Fresh(ready="True")), ns="shop", pod="p")
    assert label == "describe node /worker-2"
    assert content == ("node worker-2: unschedulable=false\n"
                       + MEMORY_OK + DISK_OK + PID_OK + READY_TRUE)


def test_a_not_ready_node_prints_the_kubelet_not_ready_text():
    _, content = r.read_text(_node(o.NODE_NOT_READY), ns="shop", pod="p")
    assert content == ("node worker-2: unschedulable=false\n"
                       + MEMORY_OK + DISK_OK + PID_OK + READY_FALSE)


def test_the_not_ready_text_is_one_shared_value():
    assert o.NOT_READY_REASON == "KubeletNotReady"
    assert o.NOT_READY_MESSAGE == "container runtime is down"
    assert o.NODE_NOT_READY == o.Fresh(ready="False", ready_reason="KubeletNotReady",
                                       ready_message="container runtime is down")


def test_a_bare_not_ready_node_is_refused():
    with pytest.raises(ValueError, match="KubeletNotReady"):
        r.read_text(_node(o.Fresh(ready="False")), ns="shop", pod="p")


def test_a_not_ready_node_with_other_text_is_refused():
    fresh = o.Fresh(ready="False", ready_reason="KubeletNotReady",
                    ready_message="PLEG is not healthy")
    with pytest.raises(ValueError, match="container runtime is down"):
        r.read_text(_node(fresh), ns="shop", pod="p")


def test_an_unknown_node_prints_the_node_controllers_text():
    # 2026-10-03: the unresponsive-kubelet story needs it. The kubelet stopped
    # talking, so the node lifecycle controller marks every condition Unknown
    # (NodeStatusUnknown, "Kubelet stopped posting node status.").
    _, content = r.read_text(_node(o.Fresh(ready="Unknown")), ns="shop", pod="p")
    assert content == (
        "node worker-2: unschedulable=false\n"
        "  condition MemoryPressure=Unknown (NodeStatusUnknown): Kubelet stopped posting node status.\n"
        "  condition DiskPressure=Unknown (NodeStatusUnknown): Kubelet stopped posting node status.\n"
        "  condition PIDPressure=Unknown (NodeStatusUnknown): Kubelet stopped posting node status.\n"
        "  condition Ready=Unknown (NodeStatusUnknown): Kubelet stopped posting node status.\n")


def test_a_node_with_no_conditions_prints_its_header_and_taints():
    fresh = o.Fresh(ready="missing", taints=(("node.kubernetes.io/not-ready", "", "NoSchedule"),))
    _, content = r.read_text(_node(fresh), ns="shop", pod="p")
    assert content == ("node worker-2: unschedulable=false\n"
                       "  taint node.kubernetes.io/not-ready=:NoSchedule\n")


def test_the_cordoned_disk_pressure_node_prints_its_story():
    (obj,) = _entry("node-cordon-diskfull").objects
    label, content = r.read_text(render.bind(obj, NAMES), ns=N.ns, pod=N.pod)
    assert label == "describe node /worker-2"
    assert content == ("node worker-2: unschedulable=true\n"
                       + MEMORY_OK + DISK_PRESSURE + PID_OK + READY_TRUE
                       + "  taint node.kubernetes.io/unschedulable=:NoSchedule\n"
                       "  taint node.kubernetes.io/disk-pressure=:NoSchedule\n")


@pytest.mark.parametrize("ready", ["True", "Unknown", "missing"])
def test_the_not_ready_text_is_only_for_a_not_ready_node(ready):
    with pytest.raises(ValueError, match="ready_reason"):
        _node(o.Fresh(ready=ready, ready_reason="KubeletNotReady",
                      ready_message="container runtime is down"))


def test_disk_pressure_needs_a_node_with_conditions():
    with pytest.raises(ValueError, match="disk_pressure"):
        _node(o.Fresh(ready="missing", disk_pressure=True))


def test_refute_and_the_lease_ending_clear_the_not_ready_text():
    obj = _node(o.NODE_NOT_READY)
    for ended in (o.refute(obj), o.unverify(obj, "lease")):
        assert (ended.fresh.ready, ended.fresh.ready_reason, ended.fresh.ready_message) == (
            "True", "", "")
        _, content = r.read_text(ended, ns="shop", pod="p")
        assert content.endswith(READY_TRUE)


def test_refute_keeps_the_cordon_the_disk_pressure_and_the_taints():
    (obj,) = _entry("node-cordon-diskfull").objects
    ended = o.refute(obj)
    assert ended.fresh.unschedulable and ended.fresh.disk_pressure
    assert ended.fresh.taints == obj.fresh.taints


def test_the_cluster_health_block_reads_the_shared_not_ready_text(monkeypatch):
    monkeypatch.setattr(o, "NOT_READY_REASON", "SomeReason")
    monkeypatch.setattr(o, "NOT_READY_MESSAGE", "some message")
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Degraded", restarts=0, findings=(), candidates=(
                       c.Candidate(cause="node worker-2 (NotReady)", verdict="attributed",
                                   reason="pod api-0 is scheduled on it"),))
    got = render.cluster_health((w,), ())
    assert got.node_issues == ("worker-2 NotReady: SomeReason — some message",)


def test_every_not_ready_catalog_node_carries_the_kubelet_text():
    not_ready = [obj for e in catalog.all_entries() for obj in e.objects
                 if obj.kind == "node" and obj.fresh.ready == "False"]
    assert len(not_ready) == 17
    assert all(obj.fresh == o.NODE_NOT_READY for obj in not_ready)


def test_the_contradiction_rows_node_describe_is_what_read_text_prints():
    """A node ended on its lease is Ready, so its describe is a healthy
    node's, byte for byte. The cordoned node's own describe is pinned by
    test_the_cordoned_disk_pressure_node_prints_its_story; no row shows it."""
    healthy = _node(o.Fresh(ready="True"), name=N.node)
    label, content = r.read_text(healthy, ns=N.ns, pod=N.pod)
    for e in catalog.job1_entries():
        for node in (obj for obj in e.objects if obj.kind == "node"):
            ended = o.unverify(render.bind(node, NAMES), "lease")
            assert r.read_text(ended, ns=N.ns, pod=N.pod) == (label, content), e.key
            user = cases.contradiction_probe(e, N).user
            assert f"== {label} ==\n{content}" in user, e.key


def test_the_cordoned_node_is_ruled_out_and_never_described():
    # The pod is unscheduled, so no pod of the workload is on the node, and
    # kubeagent reads only a live candidate's object
    # (internal/investigate/gather.go:92-133). The describe text itself is
    # pinned by test_the_cordoned_disk_pressure_node_prints_its_story.
    user = cases.wrong_attribution(_entry("node-cordon-diskfull"), N).user
    assert ("    considered node worker-2 (NotReady): ruled out — no pod of this workload "
            "is scheduled on it\n") in user
    assert "== describe node" not in user


def test_the_contradiction_row_shows_a_ready_describe():
    # worker-containerd-stop has no contradicting event line: its lease
    # ending is the contradiction, a node the kubelet says is Ready.
    user = cases.contradiction_probe(_entry("worker-containerd-stop"), N).user
    assert ("== describe node /worker-2 ==\n"
            "node worker-2: unschedulable=false\n"
            + MEMORY_OK + DISK_OK + PID_OK + READY_TRUE) in user


def test_the_contradiction_menu_ends_a_node_on_its_lease_and_a_claim_on_a_failed_read():
    """Every node the row reads ends on its lease, and every claim it reads
    ends on a refused describe. Both leave the rules' decision standing,
    unverified. No job-1 entry has a registry: kubeagent rules a lone
    registry out (its threshold is two workloads), so no row reads one."""
    kinds = collections.Counter(obj.kind for e in catalog.job1_entries() for obj in e.objects)
    assert kinds == {"node": 16, "pvc": 1}
    for e in catalog.job1_entries():
        user = cases.contradiction_probe(e, N).user
        for obj in e.objects:
            if obj.kind == "node":
                assert ("    considered node worker-2 (no kubelet lease): attributed — "
                        "pod api-7f9c4d5b6-x2x9k is scheduled on it\n"
                        "      fresh read: unverified — Ready condition is True, but the "
                        "kubelet lease was not re-read\n") in user, e.key
                assert f"== describe node /worker-2 ==\n{READY_DESCRIBE}" in user, e.key
            else:
                failed = 'persistentvolumeclaims "data-0" is forbidden'
                assert ("    considered PVC data-0 (MissingStorageClass): attributed — "
                        "pod api-7f9c4d5b6-x2x9k mounts it\n"
                        f"      fresh read: unverified — fresh read failed: {failed}\n"
                        ) in user, e.key
                assert f"== describe pvc shop/data-0 ==\nread failed: {failed}\n" in user, e.key


def test_no_contradiction_row_shows_a_node_described_twice():
    """One read per label. The cordoned node's row used to show the node
    cordoned, then healthy, under the same label; that row is gone."""
    rows = [ex for ex in generate.probe_sets() if ex.case == "contradiction_probe"]
    assert [ex.meta["entry"] for ex in rows] == [e.key for e in catalog.job1_entries()]
    for ex in rows:
        labels = re.findall(r"^== (describe node /.+) ==$", ex.user, re.MULTILINE)
        assert len(labels) == len(set(labels)), (ex.meta["entry"], labels)


@pytest.mark.parametrize("key", ["networkpolicy-deny-all", "probe-failure", "restart-loop"])
def test_the_contradiction_row_keeps_kubeagents_header(key):
    # internal/confidence/confidence.go:36-47: an attributed node is `high`.
    user = cases.contradiction_probe(_entry(key), N).user
    assert re.findall(r"^- shop/api \(\w+\)( \[confidence: \w+\])?:$", user, re.MULTILINE) == [
        " [confidence: high]"]


# --- K3 and K5: the finding lines ---------------------------------------------

FINDING_LINES = [
    # internal/diagnose/oomkilled.go:22-24
    ("memory-limit-oomkill", (
     'OOMKilled — Container exceeded its memory limit and was killed '
     '(container "app", exitCode=137)')),
    # internal/diagnose/imagepull.go:18-20
    ("deployment-bad-image-tag", (
     'ImagePullBackOff — Bad image reference or registry authentication '
     '(container "app": Failed to pull image "registry.example.com/shop/api:v1.2.3": not found)')),
    # internal/diagnose/configerror.go:24-26
    ("create-container-config-error", (
     "CreateContainerConfigError — a referenced ConfigMap or Secret is missing, or a required "
     "key is absent — the container cannot start "
     '(container "app": couldn\'t find key API_TOKEN in ConfigMap shop/app-config)')),
    # internal/diagnose/probefailure.go:346, 363-372
    ("probe-failure", (
     "ProbeFailure — the readiness probe keeps failing — the pod is kept out of Service "
     'endpoints (container "app": readiness probe failed — HTTP 500)')),
    # internal/diagnose/probefailure.go:363-372
    ("networkpolicy-deny-all", (
     "ProbeFailure — the readiness probe keeps failing — the pod is kept out of Service "
     'endpoints (container "app": readiness probe failed — timed out)')),
    # internal/diagnose/initcontainer.go:41, 43-49
    ("init-errimagepull", (
     "Init:ErrImagePull — an init container's image cannot be pulled — the pod cannot start "
     '(init container "init-config" (1/2): Failed to pull image '
     '"registry.example.com/shop/migrate:v0.9.0": not found)')),
    ("init-imagepullbackoff", (
     "Init:ImagePullBackOff — an init container's image cannot be pulled — the pod cannot "
     'start (init container "init-config" (1/2): Back-off pulling image '
     '"registry.example.com/shop/migrate:v0.9.0")')),
    # internal/diagnose/initcontainer.go:41, 64-71
    ("init-config-error", (
     "Init:CreateContainerConfigError — an init container's ConfigMap or Secret is missing, "
     "or a required key is absent — the pod cannot start "
     '(init container "init-config" (1/2): secret migration-creds not found)')),
    # internal/diagnose/volumemount.go:35-42, evidence the kubelet volume
    # manager's message
    ("volume-mount-error", (
     "VolumeMountError — a volume the pod needs could not be mounted — the pod cannot start "
     "(Unable to attach or mount volumes: unmounted volumes=[data], unattached volumes=[], "
     "failed to process volumes=[]: timed out waiting for the condition)")),
    # internal/diagnose/restartloop.go:45-47; Go's time.Duration prints 90s as 1m30s
    ("restart-loop", (
     "RestartLoop — Container keeps exiting with an error and restarting "
     '(container "app", 14 restarts, last exit 1 (Error), 1m30s ago)')),
    # internal/diagnose/crashloop.go:44-56
    ("crashloop-pod", (
     "CrashLoopBackOff — Container repeatedly crashes after starting "
     '(container "app", restartCount=14, last exit 1 (Error), 3m0s ago)')),
    ("coredns-corefile-broken", (
     "CrashLoopBackOff — Container repeatedly crashes after starting "
     '(container "coredns", restartCount=6, last exit 1 (Error), 42s ago)')),
    # internal/diagnose/pending.go:20-22, the PodScheduled message
    ("oversized-job-unschedulable", (
     "Unschedulable — No node can schedule this pod "
     "(0/3 nodes are available: 3 Insufficient memory." + PREEMPTION + ")")),
    ("node-cordon-diskfull", (
     "Unschedulable — No node can schedule this pod "
     "(0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) had untolerated "
     "taint(s)." + PREEMPTION + ")")),
    ("pvc-unbound-unschedulable", (
     "Unschedulable — No node can schedule this pod "
     "(0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims."
     + PREEMPTION + ")")),
]


@pytest.mark.parametrize("key, line", FINDING_LINES, ids=[k for k, _ in FINDING_LINES])
def test_the_finding_line_is_the_detector_text(key, line):
    # own_cause builds a row for every trainable entry; attributed builds
    # one only for an entry the rules decide.
    user = cases.own_cause_case(_entry(key), N).user
    assert f"    issue: {line}\n" in user


def test_the_oversized_job_events_read_carries_the_preemption_suffix():
    user = cases.empty_candidates(_entry("oversized-job-unschedulable"), N).user
    assert ("  FailedScheduling: 0/3 nodes are available: 3 Insufficient memory."
            + PREEMPTION + " (x5)\n") in user


def test_the_cordoned_node_events_read_carries_the_preemption_suffix():
    w = cases.gather_workload(_entry("node-cordon-diskfull"), N, ())
    assert gather.format_events(N.ns, N.pod, w.events) == (
        "events for shop/api-7f9c4d5b6-x2x9k:\n"
        "  FailedScheduling: 0/3 nodes are available: 1 node(s) were unschedulable, "
        "2 node(s) had untolerated taint(s)." + PREEMPTION + " (x6)\n")


def test_the_unbound_claim_events_read_carries_the_preemption_suffix():
    # The pod's own event. The claim's ProvisioningFailed event is recorded
    # on the claim, and kubeagent reads events by the pod's name
    # (internal/investigate/reader.go:302).
    w = cases.gather_workload(_entry("pvc-unbound-unschedulable"), N, ())
    assert gather.format_events(N.ns, N.pod, w.events) == (
        "events for shop/api-7f9c4d5b6-x2x9k:\n"
        "  FailedScheduling: 0/3 nodes are available: pod has unbound immediate "
        "PersistentVolumeClaims." + PREEMPTION + " (x5)\n")


def test_the_unbound_claim_row_prints_its_candidate_and_its_describe():
    e = _entry("pvc-unbound-unschedulable")
    users = [cases.attributed(e, N, random.Random(seed)).user for seed in range(20)]
    line = ("    considered PVC data-0 (MissingStorageClass): attributed — "
            "pod api-7f9c4d5b6-x2x9k mounts it\n")
    assert all(line in user for user in users)
    confirmed = [user for user in users
                 if line + "      fresh read: confirmed — phase is still Pending\n" in user]
    assert confirmed
    for user in confirmed:
        # internal/investigate/reader.go:250-257, describePVC
        assert ("== describe pvc shop/data-0 ==\n"
                "pvc shop/data-0: phase=Pending storageClass=fast-ssd volume=\n") in user


def test_the_volume_mount_events_read_is_the_kubelet_text():
    user = cases.empty_candidates(_entry("volume-mount-error"), N).user
    assert ("  FailedMount: Unable to attach or mount volumes: unmounted volumes=[data], "
            "unattached volumes=[], failed to process volumes=[]: timed out waiting for the "
            "condition (x5)\n") in user


# --- the events field ---------------------------------------------------------------
#
# An entry's events are (reason, message, count) templates in the order
# kubeagent lists them (internal/investigate/reader.go:300-310 keeps the API
# order), and `gather.format_events` prints them (reader.go:312-322).

# The three entries whose old events read was kubectl-table text. Each row
# became one tuple: the reason is the REASON column, the message is the text
# after `pod/{pod} `, as written, and a row counts 1. Two rows with the same
# reason and message are one event, counted once per row: probe-failure's
# two Unhealthy rows are one event at x2. The rows keep their written order.
TABLE_FORM = {
    "memory-limit-oomkill": (
        "events for shop/api-7f9c4d5b6-x2x9k:\n"
        "  BackOff: back-off restarting failed container app (x1)\n"
        "  Pulled: container image already present on machine (x1)\n"),
    "deployment-bad-image-tag": (
        "events for shop/api-7f9c4d5b6-x2x9k:\n"
        '  Failed: Failed to pull image "registry.example.com/shop/api:v1.2.3": not found (x1)\n'
        "  Failed: Error: ErrImagePull (x1)\n"
        '  BackOff: Back-off pulling image "registry.example.com/shop/api:v1.2.3" (x1)\n'),
    "probe-failure": (
        "events for shop/api-7f9c4d5b6-x2x9k:\n"
        "  Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 500 (x2)\n"),
}


@pytest.mark.parametrize("key", sorted(TABLE_FORM))
def test_a_table_form_read_becomes_kubeagents_form(key):
    w = cases.gather_workload(_entry(key), N, ())
    assert gather.format_events(N.ns, N.pod, w.events) == TABLE_FORM[key]


# The two contradicting lines that were kubectl-table text, converted by
# the same rules: the REASON column, the MESSAGE column as written, and a
# count of 1 per row, in the written order. They print after the entry's
# own lines, in the one events read. Neither BackOff message's tail nor
# the Killing message's "(node … shutting down)" is kubelet text; they
# keep their words.
CONTRADICTION_TABLE_FORM = {
    "memory-limit-oomkill": (
        "  BackOff: back-off restarting failed container app in pod api-7f9c4d5b6-x2x9k: "
        "last state terminated with exit code 1 (Error), node reports ample allocatable "
        "memory (x1)\n"),
    "probe-failure": (
        "  Started: Started container app (x1)\n"
        "  Killing: Stopping container app (node worker-2 shutting down) (x1)\n"),
}


@pytest.mark.parametrize("key", sorted(CONTRADICTION_TABLE_FORM))
def test_a_table_form_contradiction_becomes_kubeagents_form(key):
    user = cases.contradiction_probe(_entry(key), N).user
    events = TABLE_FORM[key] + CONTRADICTION_TABLE_FORM[key]
    assert f"== events shop/api-7f9c4d5b6-x2x9k ==\n{events}\n" in user


def test_the_coredns_contradiction_prints_in_the_rows_own_namespace():
    """The old line was written for kube-system. It now prints in the one
    events read, which kubeagent labels with the workload's own namespace
    and pod (internal/investigate/reader.go:302)."""
    user = cases.contradiction_probe(_entry("coredns-corefile-broken"), N).user
    assert ("== events shop/api-7f9c4d5b6-x2x9k ==\n"
            "events for shop/api-7f9c4d5b6-x2x9k:\n"
            "  BackOff: Back-off restarting failed container coredns in pod "
            "api-7f9c4d5b6-x2x9k (x14)\n"
            "  Killing: Stopping container coredns (node worker-2 shutting down) (x1)\n\n"
            ) in user
    assert "kube-system/" not in user


def test_every_trainable_entry_declares_its_events():
    assert [e.key for e in catalog.trainable() if not e.events] == []


def test_every_event_count_formats_to_an_int():
    """A count is an int, or a template that formats to one: the three
    restart-counting BackOff lines print the drawn restart count."""
    templated = set()
    for e in catalog.trainable():
        for _reason, _message, count in e.events:
            if isinstance(count, str):
                templated.add(e.key)
                assert int(count.format(**NAMES)) >= 1, e.key
            else:
                assert type(count) is int and count >= 1, e.key
        for _reason, _message, count in cases.gather_workload(e, N, ()).events:
            assert type(count) is int, e.key
    assert templated == {"crashloop-pod", "init-crashloop", "restart-loop"}
    w = cases.gather_workload(_entry("crashloop-pod"), N, ())
    assert [count for _r, _m, count in w.events] == [N.restarts]


def test_the_restart_loop_contradiction_counts_the_drawn_restarts():
    """restart-loop's Liveness line counts the drawn restarts, as its old
    line did (x{restarts}), and prints the count as an int."""
    (event,) = _entry("restart-loop").contradiction_events
    assert event[2] == "{restarts}"
    user = cases.contradiction_probe(_entry("restart-loop"), N).user
    assert "  Unhealthy: Liveness probe failed: HTTP probe failed with statuscode: 503 (x14)\n" in user


# --- restarts -------------------------------------------------------------------

def test_the_draw_can_start_at_three():
    rng = random.Random(0)
    got = {names.draw(rng, min_restarts=3).restarts for _ in range(3000)}
    assert (min(got), max(got)) == (3, 40)
    assert not got & {1, 2}


def test_the_default_draw_still_starts_at_one():
    rng = random.Random(0)
    got = {names.draw(rng).restarts for _ in range(3000)}
    assert (min(got), max(got)) == (1, 40)


def test_only_the_two_restart_counting_entries_start_at_three():
    # internal/diagnose/restartloop.go:15, 35-37: RestartThreshold is 3, and
    # crashloop.go:46 prints the last exit only from 3 restarts on.
    # 2026-09-26 (faithful prompts): coredns-corefile-broken now starts at 6
    # (see the test below), so a third entry leaves 1. The two that start at
    # 3 are unchanged. {crashloop-pod: 3, restart-loop: 3} ->
    # {crashloop-pod: 3, restart-loop: 3, coredns-corefile-broken: 6}.
    starts = {e.key: e.min_restarts for e in catalog.all_entries()}
    assert {k: v for k, v in starts.items() if v != 1} == {
        "crashloop-pod": 3, "restart-loop": 3, "coredns-corefile-broken": 6}


def test_the_draw_can_start_at_six():
    rng = random.Random(0)
    got = {names.draw(rng, min_restarts=6).restarts for _ in range(3000)}
    assert (min(got), max(got)) == (6, 40)


def test_coredns_starts_at_its_own_restart_count():
    # Its finding text fixes restartCount=6, and kubeagent's workload line
    # sums the restarts of its pods' containers (internal/inventory/
    # inventory.go:158-170, 488), so the line can never show fewer than 6.
    e = _entry("coredns-corefile-broken")
    assert 'restartCount=6,' in e.evidence
    assert e.min_restarts == 6


_CRASH_COUNT = re.compile(
    r"issue: CrashLoopBackOff — Container repeatedly crashes after starting "
    r'\(container "[^"]+", restartCount=(\d+)')
_LOOP_COUNT = re.compile(
    r"issue: RestartLoop — Container keeps exiting with an error and restarting "
    r'\(container "[^"]+", (\d+) restarts')


def test_no_generated_row_shows_a_restart_count_the_detector_would_not_print():
    counts = []
    for ex in generate.generate(seed=17, size=800) + generate.test_set():
        counts += [int(m) for m in _CRASH_COUNT.findall(ex.user) + _LOOP_COUNT.findall(ex.user)]
    assert len(counts) > 100
    assert min(counts) >= 3


# --- keywords, own cause and the coredns command ----------------------------------

KEYWORDS = {
    "deployment-bad-image-tag": ("image", "registry"),
    "node-cordon-diskfull": ("node", "pod"),
    "networkpolicy-deny-all": ("network", "policy"),
    "coredns-corefile-broken": ("coredns", "error"),
    "worker-containerd-stop": ("containerd", "deadline"),
    "oversized-job-unschedulable": ("memory", "node"),
    "probe-failure": ("readiness", "endpoint"),
    "container-start-error": ("container", "image"),
    "restart-loop": ("panic", "container"),
    "volume-attach-error": ("attached", "node"),
    "volume-mount-error": ("volume", "pod"),
    "pvc-unbound-unschedulable": ("claim", "volume"),
}


@pytest.mark.parametrize("key", sorted(KEYWORDS))
def test_the_new_keywords_are_on_a_line_the_prompt_shows(key):
    e = _entry(key)
    assert e.own_cause_keywords == KEYWORDS[key]
    user = cases.own_cause_case(e, N).user.lower()
    for word in KEYWORDS[key]:
        assert word in user, word


def test_worker_containerd_stop_names_containerd_in_its_own_cause():
    assert _entry("worker-containerd-stop").own_cause == (
        "containerd on the pod's node is not responding (context deadline exceeded)")


def test_the_coredns_command_names_the_coredns_container():
    # internal/remediation/remediation.go:21, 25, 44: the --previous log
    # command addresses the finding's own container. The pod is `<pod>`, as
    # kubeagent's prompt names it (internal/explain/explain.go:162-171).
    user = cases.attributed(_entry("coredns-corefile-broken"), N, random.Random(0)).user
    assert "| run: kubectl -n shop logs <pod> -c coredns --previous\n" in user
    user = cases.attributed(_entry("crashloop-pod"), N, random.Random(0)).user
    assert "| run: kubectl -n shop logs <pod> -c app --previous\n" in user


# --- P1: the decoys a pod past scheduling can have ----------------------------------

@pytest.mark.parametrize("key", ["create-container-config-error", "volume-attach-error",
                                 "volume-mount-error", "oversized-job-unschedulable"])
def test_the_swapped_decoy_is_a_node_on_the_prompt(key):
    # own_cause shows the declared objects alone: an attributed row may add
    # a ruled-out PVC of its own.
    user = cases.own_cause_case(_entry(key), N).user
    assert "    considered node worker-2 (" in user
    assert "considered PVC " not in user
