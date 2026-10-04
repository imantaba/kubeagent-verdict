"""The shared-origin stories as data (Spec 4b-1 §4).

A story is one upstream fault seen from 2 or more victims. Each story has
two worlds: `broken` (the fault is real) and `healthy` (it is not). Victim
texts hold the victim's own lines; `{node}`, `{ns}`, `{name}`, `{pod}`,
`{pvc}` and `{scope}` are filled by `shared_origin.build`. Gold comes from
`Answer` anchors found in a victim's own lines (dataset/gold.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kubeagent_verdict.dataset import health

NO_PREVIOUS = "<no previous>"
NO_CLASSIFIABLE = "<no classifiable>"
CLASSES = ("P", "R")
SCOPES = ("node", "ns", "")
ORIGIN_KINDS = ("node", "pvc", "registry", "workload", "other")
CONFIDENCES = ("high", "medium")
EXAM_KEYS = ("coredns-down", "node-not-ready", "storage-provisioner-down",
             "registry-unreachable", "node-disk-pressure", "networkpolicy-deny-all")
RULED_ORDER = ("node-kubelet-halted", "node-kubelet-unresponsive",
               "pvc-provisioner-not-responding", "pvc-storageclass-missing",
               "registry-mirror-unreachable", "registry-rate-limited")
_KEY = re.compile(r"^[a-z]{4,}$")


@dataclass(frozen=True)
class Answer:
    anchor: str
    cause: str
    keys: tuple[str, ...]
    rationale: str
    confidence: str = "high"
    link: bool = False

    def __post_init__(self) -> None:
        if not 1 <= len(self.keys) <= 3:
            raise ValueError(f"{self.cause!r}: 1 to 3 keys, got {len(self.keys)}")
        for k in self.keys:
            if not _KEY.match(k):
                raise ValueError(f"{self.cause!r}: key {k!r} is not 4+ lowercase letters")
            if k not in self.cause.lower():
                raise ValueError(f"{self.cause!r}: key {k!r} is not inside the cause")
        if "{" in "".join(self.keys):
            raise ValueError(f"{self.cause!r}: a key may not hold a placeholder")
        if not self.rationale.strip():
            raise ValueError(f"{self.cause!r}: the rationale is empty")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"{self.cause!r}: confidence {self.confidence!r}")


def validate_answer(a: Answer) -> None:
    """Checks that need the story: a log label never links (Ruling 19)."""
    if a.link and a.anchor.startswith("log cause: "):
        raise ValueError(f"{a.cause!r}: a log-cause label never carries link=True")


@dataclass(frozen=True)
class VictimText:
    workload_kind: str
    status: str
    issue: str
    reason: str
    evidence: str
    events: tuple[tuple[str, str, int], ...] = ()
    log: str = ""
    broken: Answer | None = None
    healthy: Answer | None = None
    events_healthy: tuple[tuple[str, str, int], ...] | None = None
    evidence_healthy: str | None = None
    log_healthy: str | None = None
    on_origin: bool = False
    pulls: bool = False
    none_phrase: str = ""


@dataclass(frozen=True)
class OriginRow:
    namespace: str
    name: str
    kind: str
    status: str
    issue: str
    reason: str
    evidence: str
    container: str
    ready: int = 0
    desired: int = 2
    events: tuple[tuple[str, str, int], ...] = ()
    log: str = ""
    answer: Answer | None = None
    none_phrase: str = ""


@dataclass(frozen=True)
class ServiceSpec:
    namespace: str
    name: str
    selector: tuple[tuple[str, str], ...]
    ready: tuple[str, ...]
    backend: tuple[str, int] | None = None


@dataclass(frozen=True)
class World:
    conditions: tuple[health.Condition, ...] = (health.READY,)
    unschedulable: bool = False
    lease: str = "renewed"
    lease_age_ms: int = 10_000
    origin_row: OriginRow | None = None
    pvc_reason: str = ""
    pvc_phase: str = ""
    pvc_class: str = ""
    pull_literal: str = ""
    services: tuple[ServiceSpec, ...] = ()
    policies: tuple[health.NetworkPolicy, ...] = ()


@dataclass(frozen=True)
class Story:
    key: str
    cls: str
    blast_radius: str
    scope_field: str
    origin_kind: str
    victims: tuple[VictimText, ...]
    broken: World
    healthy: World
    shown_origin: str
    shown_cause: str
    shown_remedy: str


_NOT_READY = health.Condition("Ready", "False", "KubeletNotReady", "container runtime is down")

_STORIES: tuple[Story, ...] = (
    Story(
        key="node-not-ready", cls="R", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff",
                issue="ContainerStartError", reason="RunContainerError",
                evidence="container {name} failed to start (RunContainerError)",
                events=(("Failed", ("Error: RunContainerError: failed to create containerd "
                           "task: context deadline exceeded"), 3),),
                log=NO_PREVIOUS, on_origin=True,
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating",
                issue="VolumeAttachError", reason="FailedAttachVolume",
                evidence="volume pvc-{pvc} cannot attach",
                events=(("FailedAttachVolume", ('Multi-Attach error for volume "pvc-{pvc}" '
                           "Volume is already exclusively attached to one node and can't be "
                           "attached to another"), 4),),
                on_origin=True, none_phrase="its volume cannot attach"),
        ),
        broken=World(conditions=(_NOT_READY,)),
        healthy=World(),
        shown_origin="node {node} is NotReady",
        shown_cause="node {node} reports Ready False: container runtime is down",
        shown_remedy="Recover or drain {node}; the flagged workloads need no change.",
    ),
    Story(
        key="coredns-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff",
                issue="CrashLoopBackOff", reason="Error",
                evidence="container {name} exited with code 1",
                log="DNS resolution failed (name lookup)",
                broken=Answer(anchor="log cause: DNS resolution failed (name lookup)",
                              cause="its container crashes because DNS name resolution "
                                    "fails on lookup",
                              keys=("resolution", "lookup"),
                              rationale="its log read names a DNS lookup failure"),
                log_healthy="cannot reach a dependency — connection refused",
                healthy=Answer(anchor="log cause: cannot reach a dependency — connection refused",
                               cause="its container crashes because a dependency refuses "
                                     "connections",
                               keys=("refuses", "connections"),
                               rationale="its log read names a refused connection"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Deployment", status="Running",
                issue="ProbeFailure", reason="Unhealthy",
                evidence="readiness probe failing",
                events=(("Unhealthy", ("Readiness probe failed: Get \"http://10.0.0.1:8080/ready\": "
                           "lookup sessions.auth.svc.cluster.local: server misbehaving"), 6),),
                broken=Answer(anchor="lookup sessions.auth.svc.cluster.local: server misbehaving",
                              cause="its readiness probe fails because DNS lookups are "
                                    "misbehaving",
                              keys=("lookups", "misbehaving"), confidence="medium",
                              rationale="its probe event shows a failed DNS lookup", link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: Get "
                           "\"http://10.0.0.1:8080/ready\": context deadline exceeded "
                           "after 1s"), 6),),
                healthy=Answer(anchor="context deadline exceeded after 1s",
                               cause="its readiness probe hits a timeout on a slow dependency",
                               keys=("timeout", "dependency"), confidence="medium",
                               rationale="its probe event shows a deadline exceeded"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running",
                issue="ProbeFailure", reason="Unhealthy",
                evidence="readiness probe failing",
                events=(("Unhealthy", ("Readiness probe failed: lookup "
                           "{name}-0.{name}.{ns}.svc.cluster.local: server misbehaving"), 5),),
                broken=Answer(anchor="svc.cluster.local: server misbehaving",
                              cause="its readiness probe fails because DNS lookups are "
                                    "misbehaving",
                              keys=("lookups", "misbehaving"), confidence="medium",
                              rationale="its probe event shows a failed DNS lookup", link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: HTTP probe failed "
                           "with statuscode: 503"), 5),),
                healthy=Answer(anchor="HTTP probe failed with statuscode: 503",
                               cause="its readiness probe gets a 503 status code",
                               keys=("status", "code"), confidence="medium",
                               rationale="its probe event shows a 503 answer"),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(
            origin_row=OriginRow(
                namespace="kube-system", name="coredns", kind="Deployment",
                status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
                evidence="container coredns exited with code 1", container="coredns",
                events=(("BackOff", ("Back-off restarting failed container coredns in pod "
                           "{pod}"), 9),),
                log="configuration parse/validation error",
                answer=Answer(anchor="log cause: configuration parse/validation error",
                              cause="CoreDNS keeps crashing because its configuration fails "
                                    "to parse",
                              keys=("configuration", "parse"),
                              rationale="its log read names a configuration parse error")),
            services=(ServiceSpec("kube-system", "kube-dns", (("k8s-app", "kube-dns"),),
                                  ready=("false", "false"), backend=("Deployment", 2)),),
        ),
        healthy=World(),
        shown_origin="CoreDNS is down",
        shown_cause="CoreDNS keeps crashing on a configuration parse error, so the kube-dns "
                    "service has no ready endpoints",
        shown_remedy="Fix the CoreDNS configuration; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-deny-all", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="liveness probe failing",
                events=(("Unhealthy", "Liveness probe failed: dependency check timed out", 7),),
                broken=Answer(anchor="default-deny",
                              cause="the NetworkPolicy default-deny selects its pods and "
                                    "blocks its traffic, so its liveness probe fails",
                              keys=("policy", "deny"),
                              rationale="its network policy line names default-deny",
                              link=True),
                none_phrase="its liveness probe fails"),
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe failing",
                events=(("Unhealthy", "Readiness probe failed: upstream check timed out", 5),),
                broken=Answer(anchor="default-deny",
                              cause="the NetworkPolicy default-deny selects its pods and "
                                    "blocks its traffic, so its readiness probe fails",
                              keys=("policy", "deny"),
                              rationale="its network policy line names default-deny",
                              link=True),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "default-deny", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy default-deny in {scope}",
        shown_cause="the NetworkPolicy default-deny in {scope} selects every pod and blocks "
                    "their traffic",
        shown_remedy="Allow the needed traffic in {scope} or remove default-deny; the "
                     "flagged workloads need no change.",
    ),
)


def by_key() -> dict[str, Story]:
    return {st.key: st for st in _STORIES}


def exam() -> tuple[Story, ...]:
    by = by_key()
    return tuple(by[k] for k in EXAM_KEYS if k in by)


def trainable() -> tuple[Story, ...]:
    rest = [st for st in _STORIES if st.key not in EXAM_KEYS]
    p = sorted((st for st in rest if st.cls == "P"), key=lambda st: st.key)
    r = sorted((st for st in rest if st.cls == "R"),
               key=lambda st: RULED_ORDER.index(st.key) if st.key in RULED_ORDER else 99)
    return tuple(p + r)
