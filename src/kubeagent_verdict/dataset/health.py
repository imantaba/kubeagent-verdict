"""A pure port of kubeagent's cluster health, service health and
network-policy pieces, at v1.24.0:

- internal/clusterhealth/clusterhealth.go (`Assess`, `nodeHealth`,
  `staleHeartbeat`, `notReadyIssue`, `trimLine`);
- internal/svchealth/svchealth.go (`Assess`, `ReadyEndpoints`,
  `classifyBacking`, `AnnotateEndpointCause`);
- internal/netpolicy/netpolicy.go (`Annotate`, `selectingPolicies`).

It reads no cluster and draws no random number. The CLUSTER capture
(tests/fixtures/gather_go_cluster/) pins every line it makes, byte for
byte, through tests/test_gather_byte_equal.py.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset.gather import safetext_line

# Kubelet conditions, and the node-problem-detector conditions the stories
# use. kubeagent reads only the first four; the other three it ignores, so
# they print no health line (clusterhealth.go nodeHealth).
KUBELET_TYPES = ("MemoryPressure", "DiskPressure", "PIDPressure", "Ready")
DETECTOR_TYPES = ("NetworkUnavailable", "ReadonlyFilesystem", "CorruptDockerOverlay2")
CONDITION_TYPES = KUBELET_TYPES + DETECTOR_TYPES
_PRESSURE = ("MemoryPressure", "DiskPressure", "PIDPressure")
_STATUSES = ("True", "False", "Unknown")
SYSTEM_NAMESPACE = "kube-system"
NO_LEASE = "no kubelet lease"
NOT_HEARTBEATING = "kubelet not heartbeating"
THRESHOLD_MS = 40_000  # the scan's lease threshold; the harness's kvThreshold
LEASES = ("renewed", "missing", "no_renew")
_NOT_READY_RUNES = 120


@dataclasses.dataclass(frozen=True)
class Condition:
    """One node condition, as the scan lists it."""

    type: str
    status: str
    reason: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if self.type not in CONDITION_TYPES:
            raise ValueError(f"condition type {self.type!r} is not one of {CONDITION_TYPES}")
        if self.status not in _STATUSES:
            raise ValueError(f"condition status {self.status!r} is not one of {_STATUSES}")


READY = Condition("Ready", "True")


@dataclasses.dataclass(frozen=True)
class Node:
    """One node at scan time. `lease` is "renewed" (renewed `lease_age_ms`
    before the scan), "missing" (no lease object) or "no_renew" (a lease
    with no renew time)."""

    name: str
    conditions: tuple[Condition, ...] = ()
    unschedulable: bool = False
    lease: str = "renewed"
    lease_age_ms: int = 10_000

    def __post_init__(self) -> None:
        if self.lease not in LEASES:
            raise ValueError(f"node {self.name}: lease {self.lease!r} is not one of {LEASES}")


@dataclasses.dataclass(frozen=True)
class DownNode:
    """`clusterhealth.DownNode`: a node the root-cause pass may blame."""

    name: str
    reason: str


def flagged(w: c.Workload) -> bool:
    """A port of `Workload.Flagged` (inventory/inventory.go:102-104)."""
    return len(w.findings) > 0 or w.ready < w.desired or w.status == "Failed"


def trim_line(s: str, limit: int) -> str:
    """A port of `trimLine` (clusterhealth.go:218-229): the first line,
    stripped, cut to `limit` runes plus an ellipsis when it is longer.
    A Python str counts code points, which are Go's runes."""
    i = s.find("\n")
    if i >= 0:
        s = s[:i]
    s = s.strip()
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def not_ready_issue(reason: str, message: str) -> str:
    """A port of `notReadyIssue` (clusterhealth.go:197-216)."""
    s = "NotReady"
    m = trim_line(message, _NOT_READY_RUNES)
    if reason and m:
        s += ": " + reason + " — " + m
    elif reason:
        s += ": " + reason
    elif m:
        s += ": " + m
    return s


def go_duration(ms: int) -> str:
    """Go's `time.Duration.Round(time.Second).String()` for a non-negative
    count of milliseconds: half a second rounds up, then h/m/s."""
    s = (ms + 500) // 1000
    if s == 0:
        return "0s"
    hours, rem = divmod(s, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes}m{sec}s"
    if minutes:
        return f"{minutes}m{sec}s"
    return f"{sec}s"


def _node_health(n: Node) -> tuple[bool, list[str]]:
    """A port of `nodeHealth`: the last Ready condition decides; pressure
    conditions that are True print in the order listed; then NotReady,
    then SchedulingDisabled. Other condition types are ignored."""
    ready, reason, message, issues = False, "", "", []
    for cond in n.conditions:
        if cond.type == "Ready":
            ready = cond.status == "True"
            reason, message = safetext_line(cond.reason), safetext_line(cond.message)
        elif cond.type in _PRESSURE and cond.status == "True":
            issues.append(cond.type)
    if not ready:
        issues.append(not_ready_issue(reason, message))
    if n.unschedulable:
        issues.append("SchedulingDisabled")
    return ready, issues


def _stale(n: Node, threshold_ms: int) -> tuple[str, str] | None:
    """A port of `staleHeartbeat`: (issue, down reason), or None. Stale
    means older than the threshold, judged on raw milliseconds; only the
    printed age is rounded."""
    if n.lease in ("missing", "no_renew"):
        return NO_LEASE, NO_LEASE
    if n.lease_age_ms > threshold_ms:
        return (f"{NOT_HEARTBEATING} (lease {go_duration(n.lease_age_ms)} stale)",
                NOT_HEARTBEATING)
    return None


def assess(nodes: Sequence[Node], workloads: Sequence[c.Workload], *,
           threshold_ms: int = THRESHOLD_MS) -> tuple[c.ClusterHealth | None, tuple[DownNode, ...]]:
    """A port of `clusterhealth.Assess`: the health block and the down nodes.

    Nodes are judged in name order, the order the API server lists them.
    A Ready node counts toward R even when its lease is stale; only a Ready
    node is lease-checked, and `threshold_ms` 0 turns the check off. The
    system lines are every flagged kube-system workload in `workloads`
    (all of them, not only the scoped ones), sorted by namespace, name and
    kind as the scan sorts them before `Assess`; a Job or CronJob prints
    no counts. With no node line and no system line the cluster is
    Healthy and kubeagent prints no block, so the first value is None.
    """
    ready_count, node_issues, down = 0, [], []
    for n in sorted(nodes, key=lambda n: n.name):
        ready, issues = _node_health(n)
        if not ready:
            down.append(DownNode(n.name, "NotReady"))
        else:
            ready_count += 1
            stale = _stale(n, threshold_ms) if threshold_ms > 0 else None
            if stale is not None:
                issues.append(stale[0])
                down.append(DownNode(n.name, stale[1]))
        node_issues += [f"{n.name} {iss}" for iss in issues]
    system = []
    for w in sorted(workloads, key=lambda w: (w.namespace, w.name, w.kind)):
        if w.namespace != SYSTEM_NAMESPACE or not flagged(w):
            continue
        if w.kind in ("Job", "CronJob"):
            system.append(f"{w.namespace}/{w.name} {w.status}")
        else:
            system.append(f"{w.namespace}/{w.name} {w.ready}/{w.desired} {w.status}")
    if not node_issues and not system:
        return None, tuple(down)
    return (c.ClusterHealth(degraded=True, nodes_ready=ready_count, nodes_total=len(nodes),
                            node_issues=tuple(node_issues), system_issues=tuple(system)),
            tuple(down))


# --- Service issues (svchealth.go).

EXPECTED_EMPTY = "kubeagent.io/expected-empty"
_BACKING_ORDER = ("CronJob", "Job", "DaemonSet", "Deployment", "StatefulSet")
_EPHEMERAL = ("Job", "CronJob")
_BACKING_DETAIL = {
    "CronJob": "no ready endpoints (backs CronJob — expected between runs)",
    "Job": "no ready endpoints (backs Job — expected between runs)",
    "DaemonSet": "no ready endpoints (backs DaemonSet — 0 desired)",
    "Deployment": "no ready endpoints (backs Deployment — scaled to 0)",
    "StatefulSet": "no ready endpoints (backs StatefulSet — scaled to 0)",
}
_NO_ENDPOINTS = "no ready endpoints"


@dataclasses.dataclass(frozen=True)
class Service:
    namespace: str
    name: str
    type: str = "ClusterIP"
    selector: tuple[tuple[str, str], ...] = ()
    annotations: tuple[tuple[str, str], ...] = ()
    lb_ingress: bool = False


@dataclasses.dataclass(frozen=True)
class EndpointSlice:
    """One slice for `service`: one address per `ready` entry, each "true",
    "false" or "unset" (a nil Ready condition, which counts as ready)."""

    namespace: str
    service: str
    ready: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Backend:
    """A workload a service may front: its pod-template labels and its
    desired count. A Job or CronJob is ephemeral."""

    namespace: str
    kind: str
    labels: tuple[tuple[str, str], ...]
    desired: int


@dataclasses.dataclass(frozen=True)
class Pod:
    namespace: str
    name: str
    node: str
    labels: tuple[tuple[str, str], ...] = ()
    ready: bool = False


@dataclasses.dataclass(frozen=True)
class SvcIssue:
    """`svchealth.Issue`. `.contract()` is the line the prompt prints;
    an expected issue prints too."""

    namespace: str
    name: str
    type: str
    problem: str
    detail: str
    expected: bool = False

    def contract(self) -> c.ServiceIssue:
        return c.ServiceIssue(self.namespace, self.name, self.type, self.detail)


def _selector_matches(selector: tuple[tuple[str, str], ...],
                      labels: tuple[tuple[str, str], ...]) -> bool:
    """svchealth's `selectorMatches`: an empty selector matches nothing."""
    if not selector:
        return False
    have = dict(labels)
    return all(have.get(k) == v for k, v in selector)


def _ready_endpoints(s: Service, slices: Sequence[EndpointSlice]) -> int:
    return sum(1 for sl in slices if sl.namespace == s.namespace and sl.service == s.name
               for r in sl.ready if r in ("true", "unset"))


def _backing(s: Service, backends: Sequence[Backend]) -> str | None:
    """`classifyBacking`: the backing kind when every matching backend is
    ephemeral or scaled to zero, else None."""
    matches = [b for b in backends
               if b.namespace == s.namespace and _selector_matches(s.selector, b.labels)]
    if not matches or any(b.kind not in _EPHEMERAL and b.desired > 0 for b in matches):
        return None
    return min(matches, key=lambda b: _BACKING_ORDER.index(b.kind)).kind


def service_issues(services: Sequence[Service], slices: Sequence[EndpointSlice],
                   backends: Sequence[Backend]) -> tuple[SvcIssue, ...]:
    """A port of `svchealth.Assess`, sorted by namespace, name and problem."""
    out = []
    for s in services:
        if s.type == "ExternalName":
            continue
        if s.type == "LoadBalancer" and not s.lb_ingress:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoExternalAddress",
                                "no external address"))
        if not s.selector or _ready_endpoints(s, slices) > 0:
            continue
        kind = _backing(s, backends)
        if kind is not None:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints",
                                _BACKING_DETAIL[kind], expected=True))
        elif dict(s.annotations).get(EXPECTED_EMPTY, "").lower() == "true":
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints",
                                f"{_NO_ENDPOINTS} — declared via {EXPECTED_EMPTY}", expected=True))
        else:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints", _NO_ENDPOINTS))
    return tuple(sorted(out, key=lambda i: (i.namespace, i.name, i.problem)))


def _endpoint_cause(s: Service, pods: Sequence[Pod], down: dict[str, str]) -> str:
    matching = [p for p in pods
                if p.namespace == s.namespace and _selector_matches(s.selector, p.labels)]
    if not matching:
        return "the selector matches no pods"
    seen, hits = set(), []
    for p in matching:
        if not p.node or p.node in seen:
            continue
        if p.node in down:
            seen.add(p.node)
            hits.append(f"{p.node} ({down[p.node]})")
    if len(hits) == 1:
        return "matching pods on down node " + hits[0]
    if hits:
        return f"matching pods on {len(hits)} down nodes"
    if not any(p.ready for p in matching):
        return f"{len(matching)} matching {'pod' if len(matching) == 1 else 'pods'}, 0 ready"
    return ""


def annotate_endpoint_cause(issues: Sequence[SvcIssue], services: Sequence[Service],
                            pods: Sequence[Pod], down: Sequence[DownNode]) -> tuple[SvcIssue, ...]:
    """A port of `AnnotateEndpointCause`: an unexpected NoEndpoints issue
    gets "no ready endpoints — <cause>" when the pods say why."""
    by_key = {(s.namespace, s.name): s for s in services}
    down_reason = {d.name: d.reason for d in down}
    out = []
    for i in issues:
        s = by_key.get((i.namespace, i.name))
        if i.problem == "NoEndpoints" and not i.expected and s is not None:
            cause = _endpoint_cause(s, pods, down_reason)
            if cause:
                i = dataclasses.replace(i, detail=f"{_NO_ENDPOINTS} — {cause}")
        out.append(i)
    return tuple(out)


# --- Network policies (netpolicy.go).

@dataclasses.dataclass(frozen=True)
class NetworkPolicy:
    """A policy's pod selector as match labels; empty selects every pod."""

    namespace: str
    name: str
    pod_selector: tuple[tuple[str, str], ...] = ()


def selecting_policies(namespace: str, pods: Sequence[Pod],
                       policies: Sequence[NetworkPolicy]) -> tuple[str, ...]:
    """A port of `selectingPolicies`: the sorted, deduped names of the
    policies in `namespace` whose selector matches any of `pods`."""
    names = set()
    for pol in policies:
        if pol.namespace != namespace:
            continue
        for p in pods:
            have = dict(p.labels)
            if all(have.get(k) == v for k, v in pol.pod_selector):
                names.add(pol.name)
                break
    return tuple(sorted(names))


def network_policies_for(w: c.Workload, pods: Sequence[Pod],
                         policies: Sequence[NetworkPolicy]) -> tuple[str, ...]:
    """A port of `netpolicy.Annotate` for one workload and its own pods:
    the selecting policies when the workload is flagged and every finding
    is a ProbeFailure (none at all counts), else ()."""
    if not flagged(w) or not all(f.issue == "ProbeFailure" for f in w.findings):
        return ()
    return selecting_policies(w.namespace, pods, policies)
