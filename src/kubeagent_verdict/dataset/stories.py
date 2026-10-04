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


# The 13 propagation scenarios Spec 4b-1 retires from training (Ruling 15):
# the twelve whose origin kubeagent's rules cannot see, and runtime-class-removed.
DROPPED = (
    "cluster-autoscaler-at-capacity", "internal-ca-expired", "kube-proxy-degraded",
    "namespace-migration-lock-held", "namespace-shared-pvc-full", "node-clock-skew",
    "node-conntrack-full", "node-frequent-kubelet-restart", "node-kernel-deadlock",
    "shared-base-image-tag-moved", "shared-gateway-refusing", "sidecar-injector-broken",
    "runtime-class-removed",
)

_PULL = 'Failed to pull image "{image}": '
_IMAGE_SIDE = "rpc error: code = NotFound desc = manifest unknown"


def _pull(literal: str) -> tuple[tuple[str, str, int], ...]:
    """A pulling victim's events in the world that holds `literal` (the
    story's World.pull_literal). `shared_origin.build` never reads the
    literal from the World: the rules read it back from these events."""
    return (("Failed", _PULL + literal, 3),
            ("BackOff", 'Back-off pulling image "{image}"', 8))


_PULL_HEALTHY = _pull(_IMAGE_SIDE)
_REGISTRY_MIRROR_UNREACHABLE = "dial tcp: lookup registry.example.com: i/o timeout"
_REGISTRY_RATE_LIMITED = "429 Too Many Requests: toomanyrequests: rate limit exceeded"
_REGISTRY_UNREACHABLE = "dial tcp 10.0.0.9:443: connect: connection refused"
_PULL_SECRET_EXPIRED = "unauthorized: authentication token has expired"
_UNBOUND = "pod has unbound immediate PersistentVolumeClaims"

_NOT_READY = health.Condition("Ready", "False", "KubeletNotReady", "container runtime is down")
_NO_SIGNATURE = "last output before exit (no signature in the last 25 lines)"
_CSE = "the container image was resolved but the container could not be started"
_OOM = "container was killed by the kernel out-of-memory handler"


def _backoff(n: int) -> tuple[tuple[str, str, int], ...]:
    """The kubelet's own restart back-off event, `n` times."""
    return (("BackOff", "Back-off restarting failed container in pod {pod}", n),)

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
    Story(
        key="node-kubelet-halted", cls="R", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded",
                issue="ContainerStartError",
                reason="the container image was resolved but the container could not be started",
                evidence=("RunContainerError: failed to create containerd task: failed to "
                          "create shim task: context deadline exceeded"),
                events=(("Failed", ("Error: RunContainerError: failed to create containerd "
                           "task: failed to create shim task: context deadline exceeded"), 3),),
                log=NO_PREVIOUS, on_origin=True,
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating",
                issue="VolumeMountError", reason="volume could not be mounted",
                evidence=("MountVolume.SetUp failed: rpc error: code = DeadlineExceeded "
                          "desc = context deadline exceeded"),
                events=(("FailedMount", ("MountVolume.SetUp failed for volume \"pvc-{pvc}\": "
                           "rpc error: code = DeadlineExceeded desc = context deadline "
                           "exceeded"), 4),),
                on_origin=True, none_phrase="its volume cannot be mounted"),
            VictimText(
                workload_kind="DaemonSet", status="CrashLoopBackOff",
                issue="CrashLoopBackOff", reason="container keeps restarting",
                evidence="back-off restarting failed container",
                events=(("BackOff", "Back-off restarting failed container in pod {pod}", 7),),
                log="cannot reach a dependency — connection refused", on_origin=True,
                none_phrase="its container keeps crashing"),
        ),
        broken=World(conditions=(_NOT_READY,)),
        healthy=World(),
        shown_origin="node {node} is NotReady",
        shown_cause="node {node} reports Ready False: container runtime is down",
        shown_remedy="Recover or drain {node}; the flagged workloads need no change.",
    ),
    Story(
        key="node-kubelet-unresponsive", cls="R", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting on this node",
                evidence="Back-off restarting failed container {name}",
                events=(("BackOff", "Back-off restarting failed container in pod {pod}", 6),),
                on_origin=True, none_phrase="its container keeps restarting"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating",
                issue="VolumeAttachError",
                reason="volume could not be attached to this pod's node",
                evidence=("AttachVolume.Attach failed: rpc error: code = Unavailable desc = "
                          "the node is not answering attach requests"),
                events=(("FailedAttachVolume", ("AttachVolume.Attach failed for volume "
                           "\"pvc-{pvc}\": rpc error: code = Unavailable desc = the node is "
                           "not answering attach requests"), 4),),
                evidence_healthy="volume pvc-{pvc} cannot attach",
                events_healthy=(("FailedAttachVolume", ('Multi-Attach error for volume '
                           '"pvc-{pvc}" Volume is already exclusively attached to one node '
                           "and can't be attached to another"), 4),),
                on_origin=True, none_phrase="its volume cannot attach"),
            VictimText(
                workload_kind="DaemonSet", status="Degraded", issue="ProbeFailure",
                reason="container's readiness probe fails from this node",
                evidence="Readiness probe failed: dial tcp: i/o timeout",
                events=(("Unhealthy", "Readiness probe failed: dial tcp: i/o timeout", 5),),
                on_origin=True, none_phrase="its readiness probe fails"),
        ),
        broken=World(conditions=(_NOT_READY,), lease="renewed", lease_age_ms=95_000),
        healthy=World(),
        shown_origin="node {node} is NotReady",
        shown_cause="node {node} reports Ready False: container runtime is down",
        shown_remedy="Recover or drain {node}; the flagged workloads need no change.",
    ),
    Story(
        key="pvc-provisioner-not-responding", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="pvc",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims", 4),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims", 6),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims", 3),),
                none_phrase="its pod cannot be scheduled"),
        ),
        broken=World(pvc_reason="ProvisionerNotResponding", pvc_phase="Pending", pvc_class="standard"),
        healthy=World(),
        shown_origin="storage class standard cannot provision",
        shown_cause="the provisioner for storage class standard is not responding",
        shown_remedy="Fix the provisioner for standard; the flagged workloads need no change.",
    ),
    Story(
        key="pvc-storageclass-missing", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="pvc",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.", 5),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.", 4),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for scheduling.", 7),),
                none_phrase="its pod cannot be scheduled"),
        ),
        broken=World(pvc_reason="MissingStorageClass", pvc_phase="Pending", pvc_class="fast-ssd"),
        healthy=World(),
        shown_origin="storage class fast-ssd cannot provision",
        shown_cause="the storage class fast-ssd does not exist",
        shown_remedy="Recreate the storage class fast-ssd; the flagged workloads need no change.",
    ),
    Story(
        key="registry-mirror-unreachable", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="registry",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}"',
                events=_pull(_REGISTRY_MIRROR_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="DaemonSet", status="ErrImagePull", issue="ErrImagePull",
                reason="container cannot pull its image",
                evidence='failed to resolve reference for {image}',
                events=_pull(_REGISTRY_MIRROR_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="Job", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}" for the job pod',
                events=_pull(_REGISTRY_MIRROR_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its job image cannot be pulled"),
        ),
        broken=World(pull_literal=_REGISTRY_MIRROR_UNREACHABLE),
        healthy=World(),
        shown_origin="registry registry.example.com is unreachable",
        shown_cause="pulls from registry.example.com fail with: dial tcp: lookup registry.example.com: i/o timeout",
        shown_remedy="Restore access to registry.example.com; the flagged workloads need no change.",
    ),
    Story(
        key="registry-rate-limited", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="registry",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}"',
                events=_pull(_REGISTRY_RATE_LIMITED),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="DaemonSet", status="ErrImagePull", issue="ErrImagePull",
                reason="container cannot pull its image",
                evidence='failed to resolve reference for {image}',
                events=_pull(_REGISTRY_RATE_LIMITED),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="Job", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}" for the job pod',
                events=_pull(_REGISTRY_RATE_LIMITED),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its job image cannot be pulled"),
        ),
        broken=World(pull_literal=_REGISTRY_RATE_LIMITED),
        healthy=World(),
        shown_origin="registry registry.example.com rate limits pulls",
        shown_cause="pulls from registry.example.com fail with: 429 Too Many Requests: toomanyrequests: rate limit exceeded",
        shown_remedy="Restore access to registry.example.com; the flagged workloads need no change.",
    ),
    Story(
        key="storage-provisioner-down", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="pvc",
        victims=(
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.", 5),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.", 3),),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.",
                events=(("FailedScheduling", "0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims.", 6),),
                none_phrase="its pod cannot be scheduled"),
        ),
        broken=World(pvc_reason="ProvisionerNotResponding", pvc_phase="Pending", pvc_class="standard"),
        healthy=World(),
        shown_origin="storage class standard cannot provision",
        shown_cause="the provisioner for storage class standard is not responding",
        shown_remedy="Fix the provisioner for standard; the flagged workloads need no change.",
    ),
    Story(
        key="registry-unreachable", cls="R", blast_radius="namespace", scope_field="ns",
        origin_kind="registry",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}"',
                events=_pull(_REGISTRY_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="DaemonSet", status="ErrImagePull", issue="ErrImagePull",
                reason="container cannot pull its image",
                evidence='failed to resolve reference for {image}',
                events=_pull(_REGISTRY_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="Job", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}" for the job pod',
                events=_pull(_REGISTRY_UNREACHABLE),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its job image cannot be pulled"),
        ),
        broken=World(pull_literal=_REGISTRY_UNREACHABLE),
        healthy=World(),
        shown_origin="registry registry.example.com is unreachable",
        shown_cause="pulls from registry.example.com fail with: dial tcp 10.0.0.9:443: connect: connection refused",
        shown_remedy="Restore access to registry.example.com; the flagged workloads need no change.",
    ),
    Story(
        key="node-pid-pressure", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="RunContainerError: unable to start container process: resource temporarily unavailable",
                events=(("Failed", ("Error: failed to create containerd task: unable to start "
                           "container process: resource temporarily unavailable"), 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="resource temporarily unavailable",
                              cause="its container cannot start because a new process is "
                                    "unavailable on the node",
                              keys=("process", "unavailable"), confidence="medium",
                              rationale="its start event shows a process that cannot be created, "
                                        "on a node that reports PID pressure", link=True),
                evidence_healthy="RunContainerError: pids limit of the pod cgroup reached",
                events_healthy=(("Failed", ("Error: failed to create containerd task: pids limit "
                                 "of the pod cgroup reached by its sidecar containers"), 3),),
                healthy=Answer(anchor="pids limit of the pod cgroup reached by its sidecar containers",
                               cause="its container cannot start because the pod's pids limit is "
                                     "reached by its sidecar containers",
                               keys=("pids", "sidecar"),
                               rationale="its start event names the pod's own pids limit"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="DaemonSet", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 1",
                events=_backoff(8), none_phrase="its container keeps restarting"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 1",
                events=_backoff(6), log=_NO_SIGNATURE,
                none_phrase="its container keeps crashing"),
        ),
        broken=World(conditions=(health.READY, health.Condition(
            "PIDPressure", "True", "KubeletHasInsufficientPID", "")),),
        healthy=World(),
        shown_origin="node {node} is under PID pressure",
        shown_cause="node {node} reports PIDPressure, and a pod there cannot create a new process",
        shown_remedy="Relieve the PID pressure on {node}; the flagged workloads need no change.",
    ),
    Story(
        key="node-runtime-restarting", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 137",
                events=_backoff(7), none_phrase="its container keeps restarting"),
            VictimText(
                workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe failed 10 times in the last five minutes",
                events=(("Unhealthy", ("Readiness probe failed: exec probe error: runtime did not "
                           "respond within the exec timeout"), 10),),
                broken=Answer(anchor="runtime did not respond within the exec timeout",
                              cause="its readiness probe fails because the container runtime "
                                    "did not respond within the exec timeout",
                              keys=("runtime", "respond"),
                              rationale="its probe event says the runtime did not respond",
                              link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: exec probe error: command "
                                 "exited 1 while the local cache was still warming"), 10),),
                healthy=Answer(anchor="command exited 1 while the local cache was still warming",
                               cause="its readiness probe exits 1 while its local cache is "
                                     "still warming",
                               keys=("cache", "warming"),
                               rationale="its probe event names a cache that is still warming"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="Job", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="RunContainerError: failed to create containerd task: context deadline exceeded",
                events=(("Failed", ("Error: failed to create containerd task: context deadline "
                           "exceeded while starting the container"), 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="context deadline exceeded while starting the container",
                              cause="its container fails to start because creating its "
                                    "containerd task exceeded the deadline",
                              keys=("containerd", "deadline"), confidence="medium",
                              rationale="its start event shows the containerd task timing out",
                              link=True),
                evidence_healthy="RunContainerError: postStart hook did not return before the start deadline",
                events_healthy=(("FailedPostStartHook", ("PostStartHook failed: its poststart call "
                                 "to a remote host never returned before the start deadline"), 3),),
                healthy=Answer(anchor="its poststart call to a remote host never returned",
                               cause="its container fails to start because its own postStart "
                                     "hook waits on a remote call that never returns",
                               keys=("poststart", "remote"),
                               rationale="its start event names its own postStart hook"),
                none_phrase="its container fails to start"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the container runtime on node {node} is not answering",
        shown_cause="the container runtime on node {node} did not respond in time, so "
                    "containers there fail to start or to pass an exec probe",
        shown_remedy="Stabilize the container runtime on {node}; the flagged workloads need "
                     "no change.",
    ),
    Story(
        key="node-memory-pressure", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="OOMKilled", issue="OOMKilled",
                reason=_OOM,
                evidence="last state terminated with reason OOMKilled, exit code 137",
                events=(("SystemOOM", "System OOM encountered, victim process killed", 2),),
                log=_NO_SIGNATURE,
                broken=Answer(anchor="system oom encountered",
                              cause="its container was killed in a system out-of-memory "
                                    "event on the node",
                              keys=("system", "killed"), confidence="medium",
                              rationale="its event shows a system-wide OOM on a node that "
                                        "reports memory pressure", link=True),
                events_healthy=(("OOMKilling", ("Memory cgroup out of memory: killed process in "
                                 "container at its own limit"), 2),),
                healthy=Answer(anchor="at its own limit",
                               cause="its container was killed at its own memory limit",
                               keys=("memory", "limit"),
                               rationale="its event says the container hit its own limit"),
                none_phrase="its container is killed for memory"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", ("Readiness probe failed: Get readiness endpoint: context "
                           "deadline exceeded after 2s"), 6),),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="DaemonSet", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 137",
                events=_backoff(9), none_phrase="its container keeps restarting"),
        ),
        broken=World(conditions=(health.READY, health.Condition(
            "MemoryPressure", "True", "KubeletHasInsufficientMemory", "")),),
        healthy=World(),
        shown_origin="node {node} is under memory pressure",
        shown_cause="node {node} reports MemoryPressure, and a container there was killed in a "
                    "system out-of-memory event",
        shown_remedy="Relieve the memory pressure on {node}; the flagged workloads need no change.",
    ),
    Story(
        key="node-network-unavailable", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to create pod sandbox: network plugin returned error: no route to the pod network",
                events=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: network plugin "
                           "returned error: no route to the pod network"), 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="no route to the pod network",
                              cause="its pod sandbox cannot be created because the node has "
                                    "no route to the pod network",
                              keys=("route", "network"),
                              rationale="its sandbox event says there is no route to the pod network",
                              link=True),
                evidence_healthy="failed to create pod sandbox: the pod spec sets hostNetwork but the policy forbids it",
                events_healthy=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: the pod "
                                 "spec sets hostNetwork true and the namespace policy rejects it"), 3),),
                healthy=Answer(anchor="sets hostnetwork true and the namespace policy rejects it",
                               cause="its pod sandbox is rejected because the pod spec sets "
                                     "hostNetwork and the namespace policy forbids it",
                               keys=("hostnetwork", "policy"),
                               rationale="its sandbox event names the hostNetwork setting"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="1 node(s) had untolerated taint node.kubernetes.io/network-unavailable",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: 1 node(s) had "
                           "untolerated taint node.kubernetes.io/network-unavailable, and the "
                           "other nodes have insufficient memory"), 4),),
                broken=Answer(anchor="untolerated taint node.kubernetes.io/network-unavailable",
                              cause="its pod is kept off one node by an untolerated "
                                    "network-unavailable taint",
                              keys=("taint", "network"),
                              rationale="its scheduling event names the network-unavailable taint",
                              link=True),
                evidence_healthy="1 node(s) had untolerated taint dedicated=gpu",
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: 1 node(s) had "
                                 "untolerated taint dedicated=gpu, and the other nodes have "
                                 "insufficient memory"), 4),),
                healthy=Answer(anchor="the other nodes have insufficient memory",
                               cause="its pod cannot be scheduled because the other nodes have "
                                     "insufficient memory",
                               keys=("insufficient", "memory"),
                               rationale="its scheduling event says the other nodes lack memory"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: dial tcp: connect: network is unreachable", 5),),
                broken=Answer(anchor="connect: network is unreachable",
                              cause="its readiness probe fails because the network is "
                                    "unreachable from the node",
                              keys=("probe", "unreachable"), confidence="medium",
                              rationale="its probe event says the network is unreachable",
                              link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: dial tcp: connect: connection refused", 5),),
                healthy=Answer(anchor="connect: connection refused",
                               cause="its readiness probe gets a refused connection when it dials",
                               keys=("refused", "connection"),
                               rationale="its probe event shows a refused connection"),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="node {node} has no route to the pod network",
        shown_cause="node {node} has no route to the pod network, so pods there cannot get a "
                    "sandbox and probes see the network as unreachable",
        shown_remedy="Restore the pod-network route on {node}; the flagged workloads need no "
                     "change.",
    ),
    Story(
        key="node-readonly-filesystem", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="open /var/run/app.pid: input/output error",
                events=_backoff(8), log=_NO_SIGNATURE,
                broken=Answer(anchor="open /var/run/app.pid: input/output error",
                              cause="its container fails because writing its pid file returns "
                                    "an input/output error",
                              keys=("input", "output"), confidence="medium",
                              rationale="its crash evidence shows an input/output error on a write",
                              link=True),
                evidence_healthy="open /var/run/app.pid: operation not permitted",
                healthy=Answer(anchor="open /var/run/app.pid: operation not permitted",
                               cause="its container fails because the operation on its pid file "
                                     "is not permitted",
                               keys=("operation", "permitted"),
                               rationale="its crash evidence shows a refused file operation"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="RunContainerError: failed to create containerd task: mkdir /run/containerd: input/output error",
                events=(("Failed", ("Error: failed to create containerd task: input/output "
                           "error"), 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="containerd task: input/output error",
                              cause="its container cannot start because creating its task "
                                    "returns an input/output error",
                              keys=("task", "output"), confidence="medium",
                              rationale="its start event shows an input/output error",
                              link=True),
                evidence_healthy="RunContainerError: failed to create containerd task: image layer digest mismatch",
                events_healthy=(("Failed", ("Error: failed to create containerd task: failed to "
                                 "unpack image layer: digest mismatch"), 3),),
                healthy=Answer(anchor="layer: digest mismatch",
                               cause="its container cannot start because an image layer fails "
                                     "to unpack on a digest mismatch",
                               keys=("layer", "digest"),
                               rationale="its start event names a layer digest mismatch"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence="MountVolume.SetUp failed for volume pvc-{pvc}: input/output error",
                events=(("FailedMount", ("MountVolume.SetUp failed for volume \"pvc-{pvc}\": mkdir "
                           "on the node's kubelet directory: input/output error"), 4),),
                broken=Answer(anchor="kubelet directory: input/output error",
                              cause="its volume cannot mount because the kubelet directory on "
                                    "the node returns an input/output error",
                              keys=("kubelet", "directory"),
                              rationale="its mount event shows an input/output error on the node",
                              link=True),
                evidence_healthy="MountVolume.SetUp failed for volume pvc-{pvc}: unknown filesystem type",
                events_healthy=(("FailedMount", ("MountVolume.SetUp failed for volume \"pvc-{pvc}\": "
                                 "mount failed: unknown filesystem type 'xfs'"), 4),),
                healthy=Answer(anchor="unknown filesystem type 'xfs'",
                               cause="its volume cannot mount because the node has an unknown "
                                     "filesystem type xfs",
                               keys=("filesystem", "unknown"),
                               rationale="its mount event names an unknown filesystem type"),
                none_phrase="its volume cannot be mounted"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the root filesystem on node {node} is read-only",
        shown_cause="the root filesystem on node {node} fails every write with an "
                    "input/output error, so containers there cannot write to disk",
        shown_remedy="Repair the disk behind {node} and remount it writable; the flagged "
                     "workloads need no change.",
    ),
    Story(
        key="node-cordoned-draining", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="0/{nodes} nodes are available: 1 node(s) were unschedulable",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: 1 node(s) were "
                           "unschedulable, 2 node(s) had volume node affinity conflict"), 4),),
                broken=Answer(anchor="1 node(s) were unschedulable",
                              cause="its pod cannot be scheduled because one node is "
                                    "unschedulable and the other nodes conflict with its volume",
                              keys=("unschedulable", "conflict"), confidence="medium",
                              rationale="its scheduling event says a node is unschedulable",
                              link=True),
                evidence_healthy="0/{nodes} nodes are available: 3 node(s) had volume node affinity conflict",
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: 3 node(s) had "
                                 "volume node affinity conflict"), 4),),
                healthy=Answer(anchor="3 node(s) had volume node affinity conflict",
                               cause="its pod cannot be scheduled because its volume is "
                                     "pinned to a zone the nodes are not in",
                               keys=("volume", "zone"),
                               rationale="its scheduling event names a volume node affinity "
                                         "conflict on every node"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="pod evicted by drain; replacement started on another node and was evicted again",
                events=(("Evicted", "The pod was evicted by drain and its replacement was evicted again", 5),),
                broken=Answer(anchor="evicted by drain",
                              cause="its pods keep being evicted by a node drain",
                              keys=("evicted", "drain"), confidence="medium",
                              rationale="its evidence says each replacement was evicted by a drain",
                              link=True),
                evidence_healthy="pod evicted; its PodDisruptionBudget allows zero disruptions so each eviction is retried",
                events_healthy=(("Evicted", ("The pod was evicted again because its PodDisruptionBudget "
                                  "allows zero disruptions"), 5),),
                healthy=Answer(anchor="its poddisruptionbudget allows zero disruptions",
                               cause="its pod is retried forever because its own "
                                     "PodDisruptionBudget allows zero disruptions",
                               keys=("budget", "disruptions"),
                               rationale="its event names its own disruption budget"),
                none_phrase="its container keeps restarting"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="wait-for-node: this pod's node affinity target is not schedulable",
                events=_backoff(6),
                broken=Answer(anchor="node affinity target is not schedulable",
                              cause="its init container waits for a node target that is not "
                                    "schedulable",
                              keys=("init", "schedulable"), confidence="medium",
                              rationale="its init evidence names a node target that is not "
                                        "schedulable"),
                evidence_healthy="wait-for-node: waiting for a node label that the last pool rollout renamed",
                healthy=Answer(anchor="a node label that the last pool rollout renamed",
                               cause="its init container waits for a node label that a "
                                     "pool rollout renamed",
                               keys=("label", "renamed"),
                               rationale="its init evidence names a renamed node label"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(unschedulable=True),
        healthy=World(),
        shown_origin="node {node} is cordoned and draining",
        shown_cause="node {node} is cordoned and draining, so its pods are evicted and nothing "
                    "new lands there",
        shown_remedy="Uncordon {node} once the drain is done; the flagged workloads need no change.",
    ),
    Story(
        key="node-corrupt-overlay", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="RunContainerError: failed to create containerd task: failed to mount rootfs: input/output error",
                events=(("Failed", ("Error: failed to create containerd task: failed to mount "
                           "rootfs: input/output error"), 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="failed to mount rootfs: input/output error",
                              cause="its container cannot start because mounting its rootfs "
                                    "returns an input/output error",
                              keys=("rootfs", "output"), confidence="medium",
                              rationale="its start event shows an input/output error on the rootfs",
                              link=True),
                evidence_healthy="RunContainerError: failed to create containerd task: failed to unpack image layer: unexpected EOF",
                events_healthy=(("Failed", ("Error: failed to create containerd task: failed to "
                                 "unpack image layer: unexpected EOF in its last layer"), 3),),
                healthy=Answer(anchor="unexpected eof in its last layer",
                               cause="its container cannot start because its image's last "
                                     "layer is truncated",
                               keys=("layer", "truncated"),
                               rationale="its start event shows an unexpected end of file in "
                                         "its last layer"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="exec: unable to load shared library: input/output error",
                events=_backoff(7), log=_NO_SIGNATURE,
                broken=Answer(anchor="unable to load shared library: input/output error",
                              cause="its container crashes because a shared library cannot be "
                                    "read, with an input/output error",
                              keys=("library", "output"), confidence="medium",
                              rationale="its crash evidence shows an input/output error "
                                        "while loading a library", link=True),
                evidence_healthy="exec: unable to load shared library libssl.so.3: no such file",
                healthy=Answer(anchor="shared library libssl.so.3: no such file",
                               cause="its container crashes because the libssl library is "
                                     "missing from its image",
                               keys=("libssl", "missing"),
                               rationale="its crash evidence names a library that is missing"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="init: read /etc/app/schema.sql: input/output error",
                events=_backoff(5),
                broken=Answer(anchor="read /etc/app/schema.sql: input/output error",
                              cause="its init container fails to read a bundled file, with an "
                                    "input/output error",
                              keys=("bundled", "output"), confidence="medium",
                              rationale="its init evidence shows an input/output error on a read",
                              link=True),
                evidence_healthy="init: parse /etc/app/schema.sql: file is empty, the image ships a placeholder",
                healthy=Answer(anchor="file is empty, the image ships a placeholder",
                               cause="its init container parses a seed file that its image "
                                     "ships as an empty placeholder",
                               keys=("seed", "placeholder"),
                               rationale="its init evidence says the file is an empty placeholder"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(conditions=(health.READY, health.Condition(
            "CorruptDockerOverlay2", "True", "CorruptDockerOverlay2", "")),),
        healthy=World(),
        shown_origin="the container layer store on node {node} is corrupt",
        shown_cause="the overlay2 layer store on node {node} is corrupt, so containers there "
                    "cannot read cached image layers",
        shown_remedy="Clear the layer store on {node} or replace the node; the flagged "
                     "workloads need no change.",
    ),
    Story(
        key="node-disk-pressure", cls="P", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="1 node(s) had untolerated taint node.kubernetes.io/disk-pressure",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: 1 node(s) had "
                           "untolerated taint node.kubernetes.io/disk-pressure, 2 Insufficient cpu."), 4),),
                broken=Answer(anchor="untolerated taint node.kubernetes.io/disk-pressure",
                              cause="its pod is kept off one node by an untolerated "
                                    "disk-pressure taint",
                              keys=("disk", "pressure"),
                              rationale="its scheduling event names the disk-pressure taint",
                              link=True),
                evidence_healthy="1 node(s) had untolerated taint dedicated=gpu",
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: 1 node(s) had "
                                 "untolerated taint dedicated=gpu, 2 Insufficient cpu."), 4),),
                healthy=Answer(anchor="untolerated taint dedicated=gpu",
                               cause="its pod is missing a toleration for the dedicated gpu taint",
                               keys=("dedicated", "taint"),
                               rationale="its scheduling event names the dedicated=gpu taint"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to create containerd task: no space left on device",
                events=(("Failed", "Error: failed to create containerd task: no space left on device", 3),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="failed to create containerd task: no space left on device",
                              cause="its container cannot start because there is no space "
                                    "left on the device",
                              keys=("space", "device"), confidence="medium",
                              rationale="its start event says the device has no space left"),
                events_healthy=(("Failed", ("Error: failed to create containerd task: no space left "
                                 "on device. Ephemeral storage: pod limit 1Gi, currently used 1Gi"), 3),),
                healthy=Answer(anchor="ephemeral storage: pod limit 1gi, currently used 1gi",
                               cause="its container fills its own 1Gi ephemeral storage limit",
                               keys=("ephemeral", "limit"),
                               rationale="its event shows the pod used its whole storage limit"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="DaemonSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 137; cannot write checkpoint: no space left on device",
                events=_backoff(8), log=_NO_SIGNATURE,
                broken=Answer(anchor="cannot write checkpoint: no space left on device",
                              cause="its agent dies while writing its checkpoint, with no "
                                    "space left on the device",
                              keys=("checkpoint", "space"), confidence="medium",
                              rationale="its crash evidence shows a failed checkpoint write"),
                evidence_healthy="last state terminated with exit code 137; cannot write checkpoint: volume smaller than the retention setting",
                healthy=Answer(anchor="volume smaller than the retention setting",
                               cause="its checkpoint volume is smaller than its retention setting",
                               keys=("retention", "volume"),
                               rationale="its crash evidence names its own retention setting"),
                none_phrase="its container keeps crashing"),
        ),
        broken=World(conditions=(health.READY, health.Condition(
            "DiskPressure", "True", "KubeletHasDiskPressure", "kubelet has disk pressure")),),
        healthy=World(),
        shown_origin="node {node} is under disk pressure",
        shown_cause="node {node} reports DiskPressure, so it refuses new pods and evicts "
                    "running ones",
        shown_remedy="Free disk space on {node}; the flagged workloads need no change.",
    ),
    Story(
        key="cluster-maintenance-taint", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="0/{nodes} nodes are available for this pod",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) had "
                           "untolerated taint maintenance=true"), 5),),
                broken=Answer(anchor="untolerated taint maintenance=true",
                              cause="its pod is kept off every node by an untolerated "
                                    "maintenance taint",
                              keys=("maintenance", "taint"),
                              rationale="its scheduling event names the maintenance taint "
                                        "on every node", link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) "
                                 "didn't match Pod's node affinity/selector"), 5),),
                healthy=Answer(anchor="didn't match pod's node affinity/selector",
                               cause="its pod asks for an instance type that no node carries",
                               keys=("instance", "carries"),
                               rationale="its scheduling event says no node matches its affinity"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="0/{nodes} nodes are available for this pod",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) had "
                           "untolerated taint maintenance=true"), 5),),
                broken=Answer(anchor="untolerated taint maintenance=true",
                              cause="its pod is kept off every node by an untolerated "
                                    "maintenance taint",
                              keys=("maintenance", "taint"),
                              rationale="its scheduling event names the maintenance taint "
                                        "on every node", link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) "
                                 "didn't match pod anti-affinity rules"), 5),),
                healthy=Answer(anchor="didn't match pod anti-affinity rules",
                               cause="its pod anti-affinity leaves no node for another replica",
                               keys=("anti", "replica"),
                               rationale="its scheduling event names pod anti-affinity"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="0/{nodes} nodes are available for this pod",
                events=(("FailedScheduling", "0/{nodes} nodes are available: no node fits this pod", 5),),
                none_phrase="its pod cannot be scheduled"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="every node carries the maintenance taint",
        shown_cause="every node carries a maintenance taint that no workload tolerates, so no "
                    "new pod can be scheduled anywhere",
        shown_remedy="Remove the maintenance taint when the work is done; the flagged workloads "
                     "need no change.",
    ),
    Story(
        key="cni-ip-pool-exhausted", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to create pod sandbox",
                events=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: plugin type cni "
                           "failed (add): no available IP addresses in the pool"), 4),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="no available ip addresses in the pool",
                              cause="its pod sandbox cannot be created because the CNI has no "
                                    "available addresses in the pool",
                              keys=("addresses", "pool"),
                              rationale="its sandbox event says the address pool has nothing free",
                              link=True),
                events_healthy=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: plugin "
                                 "type cni failed (add): requested static IP address already "
                                 "allocated"), 4),),
                healthy=Answer(anchor="requested static ip address already allocated",
                               cause="its pod asks for a static address that is already "
                                     "allocated to another pod",
                               keys=("static", "allocated"),
                               rationale="its sandbox event names a static address request"),
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="0/{nodes} nodes accepted the pod",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} Insufficient "
                           "pod-network addresses."), 4),),
                broken=Answer(anchor="insufficient pod-network addresses",
                              cause="its pod cannot be scheduled because the nodes have "
                                    "insufficient pod-network addresses",
                              keys=("insufficient", "network"),
                              rationale="its scheduling event names missing network addresses",
                              link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) "
                                 "had no free secondary network interface slot for this pod."), 4),),
                healthy=Answer(anchor="no free secondary network interface slot",
                               cause="its pod asks for a secondary interface that no node has "
                                     "a free slot for",
                               keys=("secondary", "interface"),
                               rationale="its scheduling event names a secondary interface slot"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="Failed to create pod sandbox: IPAM returned no address for this pod",
                events=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: plugin type cni "
                           "failed: IPAM returned no address for this pod"), 4),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="ipam returned no address for this pod",
                              cause="its sandbox fails because IPAM returned no address for the pod",
                              keys=("ipam", "address"),
                              rationale="its sandbox event says IPAM had no address to give",
                              link=True),
                evidence_healthy="Failed to create pod sandbox: its address annotation names a range IPAM no longer lists",
                events_healthy=(("FailedCreatePodSandBox", ("Failed to create pod sandbox: plugin "
                                 "type cni failed: pod annotation pins an address from a range "
                                 "the config no longer lists"), 4),),
                healthy=Answer(anchor="pod annotation pins an address from a range",
                               cause="its pod annotation pins an address from a range that was "
                                     "removed",
                               keys=("annotation", "range"),
                               rationale="its sandbox event names its own address annotation"),
                none_phrase="its container fails to start"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the CNI address pool is exhausted",
        shown_cause="the CNI's shared address pool has no free addresses, so new pods cannot "
                    "get a sandbox",
        shown_remedy="Grow the CNI address pool; the flagged workloads need no change.",
    ),
    Story(
        key="csi-node-driver-crashed", cls="P", blast_radius="node", scope_field="node",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence="unmounted volumes=[data]",
                events=(("FailedMount", ("Unable to attach or mount volumes: unmounted volumes=[data], "
                           "timed out waiting for the condition"), 6),),
                broken=Answer(anchor="timed out waiting for the condition",
                              cause="its volume cannot mount because the mount timed out "
                                    "waiting for the condition",
                              keys=("mount", "timed"), confidence="medium",
                              rationale="its mount event shows a timeout on the node",
                              link=True),
                events_healthy=(("FailedMount", ("Unable to attach or mount volumes: unmounted "
                                 "volumes=[data]: its claim is stuck Terminating, the finalizer "
                                 "never cleared"), 6),),
                healthy=Answer(anchor="its claim is stuck terminating",
                               cause="its claim is stuck Terminating because a finalizer "
                                     "never cleared",
                               keys=("terminating", "finalizer"),
                               rationale="its mount event names its own stuck claim"),
                none_phrase="its volume cannot be mounted"),
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="open /data/lockfile: no such file or directory (volume not yet mounted when the container started)",
                events=_backoff(8), log=_NO_SIGNATURE,
                broken=Answer(anchor="volume not yet mounted when the container started",
                              cause="its container exits reading a data path whose volume was "
                                    "not yet mounted",
                              keys=("volume", "mounted"), confidence="medium",
                              rationale="its crash evidence says the volume was not mounted yet"),
                evidence_healthy="open /data/lockfile: no such file or directory (the entrypoint never creates the lock directory)",
                healthy=Answer(anchor="the entrypoint never creates the lock directory",
                               cause="its entrypoint never creates the lock directory it reads",
                               keys=("entrypoint", "directory"),
                               rationale="its crash evidence names a directory nobody creates"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence="AttachVolume.Attach failed for volume pvc-{pvc}: timed out waiting for the external attacher",
                events=(("FailedAttachVolume", ("AttachVolume.Attach failed for volume \"pvc-{pvc}\": "
                           "timed out waiting for the external attacher"), 4),),
                broken=Answer(anchor="timed out waiting for the external attacher",
                              cause="its volume cannot attach because the external attacher "
                                    "timed out",
                              keys=("attacher", "timed"), confidence="medium",
                              rationale="its attach event shows the attacher timing out",
                              link=True),
                evidence_healthy="AttachVolume.Attach failed for volume pvc-{pvc}: volume handle not found on the storage backend",
                events_healthy=(("FailedAttachVolume", ("AttachVolume.Attach failed for volume "
                                 "\"pvc-{pvc}\": volume handle not found on the storage backend"), 4),),
                healthy=Answer(anchor="volume handle not found on the storage backend",
                               cause="its volume handle was deleted from the storage backend",
                               keys=("handle", "backend"),
                               rationale="its attach event says the backend has no such handle"),
                none_phrase="its volume cannot attach"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="kube-system", name="csi-node-driver", kind="DaemonSet",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container csi-node-driver exited with code 1", container="csi-node-driver",
            ready=0, desired=1,
            events=(("BackOff", "Back-off restarting failed container csi-node-driver in pod {pod}", 4),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="the CSI node driver on node {node} is crashing",
        shown_cause="the CSI node driver pod on node {node} keeps crashing, so volumes cannot "
                    "mount or attach there",
        shown_remedy="Recover the CSI node driver on {node}; the flagged workloads need no change.",
    ),
    Story(
        key="namespace-egress-proxy-down", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe failed 10 times in the last five minutes",
                events=(("Unhealthy", ("Readiness probe failed: outbound check blocked waiting on "
                           "the egress proxy"), 10),),
                broken=Answer(anchor="outbound check blocked waiting on the egress proxy",
                              cause="its readiness probe fails because its outbound check is "
                                    "blocked waiting on the egress proxy",
                              keys=("outbound", "proxy"),
                              rationale="its probe event names the egress proxy", link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: outbound check exceeded its "
                                 "own 900ms timeout budget"), 10),),
                healthy=Answer(anchor="outbound check exceeded its own 900ms timeout budget",
                               cause="its readiness probe gives up on its own short timeout budget",
                               keys=("budget", "short"),
                               rationale="its probe event names its own timeout budget"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="dial tcp: i/o timeout while establishing an outbound connection",
                events=_backoff(7), log=_NO_SIGNATURE,
                broken=Answer(anchor="i/o timeout while establishing an outbound connection",
                              cause="its container exits after a timeout while it opens an "
                                    "outbound connection",
                              keys=("timeout", "opens"), confidence="medium",
                              rationale="its crash evidence shows an outbound connect timing out"),
                evidence_healthy="dial tcp: connect timeout of 200ms, set below a normal round trip",
                healthy=Answer(anchor="connect timeout of 200ms, set below a normal round trip",
                               cause="its connect timeout is set below a normal round trip",
                               keys=("connect", "round"),
                               rationale="its crash evidence names its own 200ms setting"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="last state terminated with exit code 1; seed download through the proxy failed",
                events=_backoff(5),
                broken=Answer(anchor="seed download through the proxy failed",
                              cause="its init container fails to download its seed data "
                                    "through the proxy",
                              keys=("download", "proxy"), confidence="medium",
                              rationale="its init evidence says the proxy download failed"),
                evidence_healthy="last state terminated with exit code 1; seed download from a decommissioned host no longer resolves",
                healthy=Answer(anchor="seed download from a decommissioned host no longer resolves",
                               cause="its init container downloads from a decommissioned host "
                                     "that no longer resolves",
                               keys=("decommissioned", "resolves"),
                               rationale="its init evidence names a host that no longer resolves"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="egress-system", name="egress-proxy", kind="Deployment",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container egress-proxy exited with code 1", container="egress-proxy",
            ready=0, desired=3,
            events=(("BackOff", "Back-off restarting failed container egress-proxy in pod {pod}", 9),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="the egress proxy serving {scope} is down",
        shown_cause="the egress proxy serving {scope} has no ready replicas, so outbound "
                    "calls from {scope} hang",
        shown_remedy="Restore the egress proxy for {scope}; the flagged workloads need no change.",
    ),
    Story(
        key="pod-identity-webhook-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="no credential source found: identity token file is absent",
                events=_backoff(7), log=_NO_SIGNATURE,
                broken=Answer(anchor="no credential source found: identity token file is absent",
                              cause="its container crashes because no credential source is "
                                    "found and its identity token file is absent",
                              keys=("credential", "absent"), confidence="medium",
                              rationale="its crash evidence shows an absent identity token file",
                              link=True),
                evidence_healthy="no credential source found: its pod template carries the identity injection opt-out annotation",
                healthy=Answer(anchor="its pod template carries the identity injection opt-out annotation",
                               cause="its pod template opts out of identity injection with an "
                                     "annotation",
                               keys=("injection", "annotation"),
                               rationale="its crash evidence names an opt-out annotation"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
                issue="Init:CrashLoopBackOff", reason="init container keeps restarting",
                evidence="config fetch refused: request carried no identity token",
                events=_backoff(6),
                broken=Answer(anchor="request carried no identity token",
                              cause="its init config fetch is refused because the request "
                                    "carried no identity token",
                              keys=("refused", "identity"), confidence="medium",
                              rationale="its init evidence says the request had no token"),
                evidence_healthy="config fetch refused: the init image predates token-file support",
                healthy=Answer(anchor="the init image predates token-file support",
                               cause="its init image predates token-file support",
                               keys=("predates", "support"),
                               rationale="its init evidence names an old init image"),
                none_phrase="its init container keeps crashing"),
            VictimText(
                workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", ("Readiness probe failed: HTTP probe failed with statuscode: "
                           "503, body: token signing unavailable"), 6),),
                broken=Answer(anchor="body: token signing unavailable",
                              cause="its readiness probe gets a 503 because token signing is "
                                    "unavailable",
                              keys=("signing", "unavailable"), confidence="medium",
                              rationale="its probe event says token signing is unavailable"),
                events_healthy=(("Unhealthy", ("Readiness probe failed: HTTP probe failed with "
                                 "statuscode: 503, body: signing key rotated, handler still loads "
                                 "the previous key"), 6),),
                healthy=Answer(anchor="signing key rotated, handler still loads the previous key",
                               cause="its handler still loads the previous key after the signing key rotated",
                               keys=("rotated", "previous"),
                               rationale="its probe event names a key rotation"),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="kube-system", name="pod-identity-webhook", kind="Deployment",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container pod-identity-webhook exited with code 1",
            container="pod-identity-webhook", ready=0, desired=2,
            events=(("BackOff", "Back-off restarting failed container pod-identity-webhook in pod {pod}", 7),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="the pod identity webhook is down",
        shown_cause="the pod identity webhook has no ready replica, so pods are admitted "
                    "without their identity token volume",
        shown_remedy="Restore the pod identity webhook; the flagged workloads need no change.",
    ),
    Story(
        key="external-secrets-operator-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CreateContainerConfigError",
                issue="CreateContainerConfigError",
                reason="container could not build its environment",
                evidence="secret \"{name}-credentials\" not found",
                events=(("Failed", "Error: secret \"{name}-credentials\" not found", 5),),
                broken=Answer(anchor="secret \"{name}-credentials\" not found",
                              cause="its container cannot start because a Secret it references "
                                    "is not found",
                              keys=("secret", "found"), confidence="medium",
                              rationale="its event says a referenced Secret does not exist",
                              link=True),
                evidence_healthy="secret \"{name}-credentails\" not found; the Secret one letter off exists",
                events_healthy=(("Failed", ("Error: secret \"{name}-credentails\" not found, a "
                                 "Secret one letter off exists in the namespace"), 5),),
                healthy=Answer(anchor="a secret one letter off exists in the namespace",
                               cause="its pod spec misspells the Secret name by one letter",
                               keys=("misspells", "letter"),
                               rationale="its event says a similar Secret name exists"),
                none_phrase="its container cannot build its environment"),
            VictimText(
                workload_kind="Job", status="Init:CreateContainerConfigError",
                issue="Init:CreateContainerConfigError",
                reason="init container could not build its environment",
                evidence="couldn't find key DB_PASSWORD in Secret {ns}/{name}-db",
                events=(("Failed", "Error: couldn't find key DB_PASSWORD in Secret {ns}/{name}-db", 5),),
                broken=Answer(anchor="couldn't find key db_password in secret",
                              cause="its init container asks for a Secret key that is missing",
                              keys=("secret", "missing"), confidence="medium",
                              rationale="its event names a Secret key that cannot be found"),
                events_healthy=(("Failed", ("Error: couldn't find key DB_PASSWORD in Secret "
                                 "{ns}/{name}-db, the chart now writes DATABASE_PASSWORD"), 5),),
                healthy=Answer(anchor="the chart now writes database_password",
                               cause="its chart renamed the key to DATABASE_PASSWORD",
                               keys=("chart", "renamed"),
                               rationale="its event names the renamed key"),
                none_phrase="its init container cannot build its environment"),
            VictimText(
                workload_kind="StatefulSet", status="Degraded", issue="ContainerStartError",
                reason=_CSE,
                evidence="MountVolume.SetUp failed for volume tls: secret \"{name}-tls\" not found",
                events=(("FailedMount", ("MountVolume.SetUp failed for volume \"tls\": secret "
                           "\"{name}-tls\" not found"), 4),),
                log=NO_PREVIOUS,
                broken=Answer(anchor="secret \"{name}-tls\" not found",
                              cause="its volume cannot mount because the Secret behind it is "
                                    "not found",
                              keys=("volume", "secret"), confidence="medium",
                              rationale="its mount event says the Secret behind the volume is gone"),
                evidence_healthy="MountVolume.SetUp failed for volume tls: secret \"{name}-tls\" not found",
                events_healthy=(("FailedMount", ("MountVolume.SetUp failed for volume \"tls\": secret "
                                 "\"{name}-tls\" not found, removed by a cleanup job that matched "
                                 "its label"), 4),),
                healthy=Answer(anchor="removed by a cleanup job that matched its label",
                               cause="its TLS Secret was removed by a cleanup job",
                               keys=("cleanup", "removed"),
                               rationale="its mount event names a cleanup job"),
                none_phrase="its container fails to start"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="kube-system", name="external-secrets", kind="Deployment",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container external-secrets exited with code 1",
            container="external-secrets", ready=0, desired=1,
            events=(("BackOff", "Back-off restarting failed container external-secrets in pod {pod}", 7),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="the external-secrets operator is down",
        shown_cause="the external-secrets operator is down, so the Secrets it syncs are no "
                    "longer created and pods that mount them cannot start",
        shown_remedy="Restore the external-secrets operator; the flagged workloads need no change.",
    ),
    Story(
        key="network-operator-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", ("Readiness probe failed: dependency check to a peer on "
                           "another node timed out"), 6),),
                broken=Answer(anchor="dependency check to a peer on another node timed out",
                              cause="its readiness probe fails because a peer on another node "
                                    "times out",
                              keys=("peer", "another"), confidence="medium",
                              rationale="its probe event shows a cross-node peer timing out",
                              link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: dependency check dials a "
                                 "peer hostname that no Service publishes any more"), 6),),
                healthy=Answer(anchor="a peer hostname that no service publishes any more",
                               cause="its check dials a hostname that no Service publishes",
                               keys=("hostname", "publishes"),
                               rationale="its probe event names a hostname nobody publishes"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="cluster join failed: peer on another node unreachable after 30s",
                events=_backoff(7), log=_NO_SIGNATURE,
                broken=Answer(anchor="peer on another node unreachable after 30s",
                              cause="its cluster join fails because a peer on another node is "
                                    "unreachable",
                              keys=("join", "unreachable"), confidence="medium",
                              rationale="its crash evidence shows a peer on another node "
                                        "unreachable", link=True),
                evidence_healthy="cluster join failed: member ordinal 3 no longer exists, the peer list is stale",
                healthy=Answer(anchor="member ordinal 3 no longer exists",
                               cause="its stale peer list still names a member ordinal that no "
                                     "longer exists",
                               keys=("ordinal", "stale"),
                               rationale="its crash evidence names a missing member"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="wait-for-db: dial tcp: i/o timeout reaching a pod on another node",
                events=_backoff(5),
                broken=Answer(anchor="i/o timeout reaching a pod on another node",
                              cause="its init wait for the database times out",
                              keys=("database", "times"), confidence="medium",
                              rationale="its init evidence shows a timeout reaching a pod"),
                evidence_healthy="wait-for-db: reads a stale address file instead of the Service name",
                healthy=Answer(anchor="reads a stale address file instead of the service name",
                               cause="its init step reads a stale address file",
                               keys=("stale", "address"),
                               rationale="its init evidence names a stale address file"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="kube-system", name="network-operator", kind="Deployment",
            status="OOMKilled", issue="OOMKilled", reason=_OOM,
            evidence="last state terminated with reason OOMKilled, exit code 137",
            container="network-operator", ready=0, desired=1,
            events=(("OOMKilling", ("Memory cgroup out of memory: killed process in container "
                       "network-operator at its memory limit"), 5),),
            log=_NO_SIGNATURE,
            answer=Answer(anchor="last state terminated with reason oomkilled, exit code 137",
                          cause="the network operator was killed at its memory limit",
                          keys=("memory", "limit"),
                          rationale="its last state shows it was OOMKilled"))),
        healthy=World(),
        shown_origin="the network operator is OOM-killed",
        shown_cause="the network operator keeps being OOM-killed, so the pod overlay network "
                    "is no longer reconciled",
        shown_remedy="Raise the network operator's memory limit; the flagged workloads need no change.",
    ),
    Story(
        key="cert-manager-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: tls: certificate has expired", 8),),
                broken=Answer(anchor="tls: certificate has expired",
                              cause="its readiness probe fails because a TLS certificate has expired",
                              keys=("expired", "certificate"),
                              rationale="its probe event says a certificate has expired",
                              link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: x509: certificate signed by "
                                 "unknown authority, the probe's CA bundle predates the trust store "
                                 "rotation"), 8),),
                healthy=Answer(anchor="the probe's ca bundle predates the trust store rotation",
                               cause="its probe pins a CA bundle that predates the trust store "
                                     "rotation",
                               keys=("bundle", "trust"),
                               rationale="its probe event names an old CA bundle"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="tls: failed to load server certificate: certificate has expired",
                events=_backoff(8), log=_NO_SIGNATURE,
                broken=Answer(anchor="failed to load server certificate: certificate has expired",
                              cause="its container crashes because its server certificate has "
                                    "expired",
                              keys=("expired", "server"),
                              rationale="its crash evidence says the server certificate expired",
                              link=True),
                evidence_healthy="tls: failed to load server certificate: self-signed, one-year validity, never enrolled for renewal",
                healthy=Answer(anchor="self-signed, one-year validity, never enrolled for renewal",
                               cause="its self-signed certificate was never enrolled for renewal",
                               keys=("signed", "enrolled"),
                               rationale="its crash evidence names a hand-made certificate"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="DaemonSet", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="metrics push failed: x509: certificate has expired or is not yet valid",
                events=_backoff(6),
                broken=Answer(anchor="x509: certificate has expired or is not yet valid",
                              cause="its metrics push fails because a certificate has expired",
                              keys=("metrics", "expired"), confidence="medium",
                              rationale="its evidence shows an x509 expiry on the push",
                              link=True),
                evidence_healthy="metrics push failed: x509: chain ends at a private CA intermediate that lapsed",
                healthy=Answer(anchor="chain ends at a private ca intermediate that lapsed",
                               cause="its certificate chain ends at a private intermediate that "
                                     "lapsed",
                               keys=("private", "intermediate"),
                               rationale="its evidence names a lapsed private intermediate"),
                none_phrase="its container keeps restarting"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="cert-manager", name="cert-manager", kind="Deployment",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container cert-manager exited with code 1", container="cert-manager",
            ready=0, desired=1,
            events=(("BackOff", "Back-off restarting failed container cert-manager in pod {pod}", 11),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="cert-manager is down",
        shown_cause="cert-manager is down, so certificates near expiry are not renewed and the "
                    "workloads serving them fail their TLS checks once they lapse",
        shown_remedy="Restore cert-manager and let it renew the lapsed Certificates; the "
                     "flagged workloads need no change.",
    ),
    Story(
        key="metrics-server-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503", 6),),
                events_healthy=(("Unhealthy", ("Readiness probe failed: HTTP probe failed with "
                                 "statuscode: 503 (overloaded, queue depth 4000)"), 6),),
                healthy=Answer(anchor="overloaded, queue depth 4000",
                               cause="its request queue is overloaded at a depth of 4000",
                               keys=("overloaded", "queue"),
                               rationale="its probe event shows a full request queue"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="OOMKilled", issue="OOMKilled",
                reason=_OOM,
                evidence="container exceeded its memory limit under load that would have been spread across more replicas",
                events=_backoff(6), log="ran out of memory in-process",
                broken=Answer(anchor="load that would have been spread across more replicas",
                              cause="its container exceeded its memory limit under load that "
                                    "more replicas would share",
                              keys=("memory", "replicas"), confidence="medium",
                              rationale="its evidence says more replicas would have shared the load",
                              link=True),
                evidence_healthy="container exceeded its memory limit: its in-memory index doubles on every compaction",
                healthy=Answer(anchor="its in-memory index doubles on every compaction",
                               cause="its in-memory index doubles on every compaction",
                               keys=("index", "compaction"),
                               rationale="its evidence names its own growing index"),
                none_phrase="its container is killed for memory"),
            VictimText(
                workload_kind="DaemonSet", status="Degraded", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="scrape target overloaded: collector restarted after 30s of backpressure",
                events=_backoff(6),
                evidence_healthy="collector restarted: its scrape interval is one second so its buffer fills",
                healthy=Answer(anchor="its scrape interval is one second so its buffer fills",
                               cause="its scrape interval is one second so its buffer fills",
                               keys=("interval", "buffer"),
                               rationale="its evidence names its own scrape interval"),
                none_phrase="its container keeps restarting"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="kube-system", name="metrics-server", kind="Deployment",
            status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
            evidence="container metrics-server exited with code 1", container="metrics-server",
            ready=0, desired=1,
            events=(("BackOff", "Back-off restarting failed container metrics-server in pod {pod}", 8),),
            log=_NO_SIGNATURE, answer=None)),
        healthy=World(),
        shown_origin="metrics-server is down",
        shown_cause="metrics-server is down, so every autoscaler is frozen at its last size "
                    "and overloaded pods are not scaled out",
        shown_remedy="Restore metrics-server and let the autoscalers resume; the flagged "
                     "workloads need no change.",
    ),
    Story(
        key="csi-controller-oomkilled", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                           "immediate PersistentVolumeClaims"), 5),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims, its claim names a class one "
                                 "letter off from any class"), 5),),
                healthy=Answer(anchor="its claim names a class one letter off from any class",
                               cause="its claim names a storage class one letter off",
                               keys=("class", "letter"),
                               rationale="its event names a misspelled class"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                           "immediate PersistentVolumeClaims"), 5),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims, its template asks for 10 TiB "
                                 "above the per-volume cap"), 5),),
                healthy=Answer(anchor="its template asks for 10 tib above the per-volume cap",
                               cause="its volume template asks for more than the per-volume cap",
                               keys=("template", "volume"),
                               rationale="its event says the template asks for 10 TiB"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="ContainerCreating", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence="MountVolume.MountDevice failed for volume pvc-{pvc}: the controller has not published the volume",
                events=(("FailedMount", ("MountVolume.MountDevice failed for volume \"pvc-{pvc}\": "
                           "the controller has not published the volume"), 4),),
                broken=Answer(anchor="the controller has not published the volume",
                              cause="its volume cannot mount because the controller has not "
                                    "published it",
                              keys=("controller", "published"), confidence="medium",
                              rationale="its mount event says the controller never published "
                                        "the volume"),
                evidence_healthy="MountVolume.MountDevice failed for volume pvc-{pvc}: two volumeMounts name the same claim",
                events_healthy=(("FailedMount", ("MountVolume.MountDevice failed for volume "
                                 "\"pvc-{pvc}\": two volumeMounts name the same claim with "
                                 "conflicting options"), 4),),
                healthy=Answer(anchor="two volumemounts name the same claim",
                               cause="its pod mounts the same claim twice with conflicting options",
                               keys=("twice", "conflicting"),
                               rationale="its mount event names a doubled mount"),
                none_phrase="its volume cannot be mounted"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="storage-system", name="block-ssd-csi-controller", kind="Deployment",
            status="OOMKilled", issue="OOMKilled", reason=_OOM,
            evidence="last state terminated with reason OOMKilled, exit code 137",
            container="block-ssd-csi-controller", ready=0, desired=2,
            events=(("OOMKilling", ("Memory cgroup out of memory: killed process in container "
                       "block-ssd-csi-controller at its memory limit"), 6),),
            log=_NO_SIGNATURE,
            answer=Answer(anchor="last state terminated with reason oomkilled, exit code 137",
                          cause="the block-ssd CSI controller was killed at its memory limit",
                          keys=("memory", "limit"),
                          rationale="its last state shows it was OOMKilled"))),
        healthy=World(),
        shown_origin="the block-ssd CSI controller is OOM-killed",
        shown_cause="the block-ssd CSI controller is OOM-killed on every start, so no claim on "
                    "that class gets a volume",
        shown_remedy="Raise the block-ssd CSI controller's memory limit; the flagged workloads "
                     "need no change.",
    ),
    Story(
        key="csi-controller-unschedulable", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                           "immediate PersistentVolumeClaims"), 5),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims, its volumeName points at a "
                                 "volume held by another claim"), 5),),
                healthy=Answer(anchor="its volumename points at a volume held by another claim",
                               cause="its claim pins a volume that another claim already holds",
                               keys=("pins", "holds"),
                               rationale="its event names a volume held by another claim"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason="no node has room for the pod",
                evidence="pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                           "immediate PersistentVolumeClaims"), 5),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims, its claim asks for "
                                 "ReadWriteMany but the class offers ReadWriteOnce"), 5),),
                healthy=Answer(anchor="its claim asks for readwritemany but the class offers readwriteonce",
                               cause="its claim asks for an access mode the class cannot offer",
                               keys=("access", "offer"),
                               rationale="its event names an access mode the class lacks"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
                issue="Init:CrashLoopBackOff", reason="init container keeps restarting",
                evidence="init step waited 120s for its data volume and gave up",
                events=_backoff(6),
                broken=Answer(anchor="waited 120s for its data volume and gave up",
                              cause="its init step gave up after waiting for its data volume",
                              keys=("waiting", "volume"), confidence="medium",
                              rationale="its init evidence says the data volume never showed up"),
                evidence_healthy="init step polls a volume path that its last chart release renamed",
                healthy=Answer(anchor="a volume path that its last chart release renamed",
                               cause="its init step polls a path that the chart renamed",
                               keys=("polls", "renamed"),
                               rationale="its init evidence names a renamed path"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(origin_row=OriginRow(
            namespace="storage-system", name="archive-hdd-csi-controller", kind="Deployment",
            status="Pending", issue="Unschedulable", reason="no node has room for the pod",
            evidence="0/{nodes} nodes are available: {nodes} node(s) didn't match Pod's node affinity/selector.",
            container="archive-hdd-csi-controller", ready=0, desired=1,
            events=(("FailedScheduling", ("0/{nodes} nodes are available: {nodes} node(s) didn't "
                       "match Pod's node affinity/selector."), 8),),
            answer=Answer(anchor="didn't match pod's node affinity/selector",
                          cause="the archive-hdd CSI controller cannot be scheduled because no "
                                "node can match its node selector",
                          keys=("match", "selector"),
                          rationale="its scheduling event says no node matches its selector"))),
        healthy=World(),
        shown_origin="the archive-hdd CSI controller cannot be scheduled",
        shown_cause="the archive-hdd CSI controller cannot be scheduled because its node "
                    "selector matches no node, so claims on that class are never provisioned",
        shown_remedy="Label a node for the archive-hdd controller; the flagged workloads need "
                     "no change.",
    ),
    Story(
        key="shared-configmap-deleted", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CreateContainerConfigError",
                issue="CreateContainerConfigError",
                reason="container could not build its environment",
                evidence="configmap app-settings not found",
                events=(("Failed", 'Error: configmap "app-settings" not found', 4),),
                broken=Answer(anchor="configmap app-settings not found",
                              cause="the ConfigMap app-settings its container needs was not found",
                              keys=("configmap", "found"),
                              rationale="its evidence says the ConfigMap app-settings is missing",
                              link=True),
                evidence_healthy="couldn't find key api-timeout in ConfigMap {ns}/checkout-settings",
                events_healthy=(("Failed", "Error: couldn't find key api-timeout in ConfigMap {ns}/checkout-settings", 4),),
                healthy=Answer(anchor="couldn't find key api-timeout",
                               cause="the api-timeout key its container reads was removed from "
                                     "its own ConfigMap",
                               keys=("removed", "reads"),
                               rationale="its evidence names one missing key in its own ConfigMap"),
                none_phrase="its container cannot build its environment"),
            VictimText(
                workload_kind="Job", status="Init:CreateContainerConfigError",
                issue="Init:CreateContainerConfigError",
                reason="init container could not build its environment",
                evidence="configmap app-settings not found",
                events=(("Failed", 'Error: configmap "app-settings" not found', 3),),
                broken=Answer(anchor="configmap app-settings not found",
                              cause="the ConfigMap app-settings its init container needs was "
                                    "not found",
                              keys=("configmap", "found"),
                              rationale="its evidence says the ConfigMap app-settings is missing",
                              link=True),
                evidence_healthy="init container references a ConfigMap key that was renamed",
                events_healthy=(("Failed", "Error: init container references a ConfigMap key that was renamed", 3),),
                healthy=Answer(anchor="references a configmap key that was renamed",
                               cause="its init container references a ConfigMap key that was "
                                     "renamed",
                               keys=("references", "renamed"),
                               rationale="its event says the key it references was renamed"),
                none_phrase="its init container cannot build its environment"),
            VictimText(
                workload_kind="StatefulSet", status="CreateContainerConfigError",
                issue="CreateContainerConfigError",
                reason="container could not build its environment",
                evidence="configmap app-settings not found",
                events=(("Failed", 'Error: configmap "app-settings" not found', 5),),
                broken=Answer(anchor="configmap app-settings not found",
                              cause="the ConfigMap app-settings its container needs was not found",
                              keys=("configmap", "found"),
                              rationale="its evidence says the ConfigMap app-settings is missing",
                              link=True),
                evidence_healthy="configmap {name}-revision-settings not found",
                events_healthy=(("Failed", 'Error: configmap "{name}-revision-settings" not found', 5),),
                healthy=Answer(anchor="configmap {name}-revision-settings not found",
                               cause="its newest revision mounts a ConfigMap that was never "
                                     "created",
                               keys=("revision", "mounts"),
                               rationale="its evidence names a revision-specific ConfigMap"),
                none_phrase="its container cannot build its environment"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the shared ConfigMap app-settings in {scope}",
        shown_cause="the shared ConfigMap in {scope} was deleted, so no pod there can build its "
                    "container environment",
        shown_remedy="Restore the shared ConfigMap in {scope}; the flagged workloads need no change.",
    ),
    Story(
        key="shared-dependency-scaled-to-zero", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 1",
                events=_backoff(8), log="cannot reach a dependency — connection refused",
                broken=Answer(anchor="log cause: cannot reach a dependency — connection refused",
                              cause="its container cannot reach a dependency, the connection "
                                    "is refused",
                              keys=("dependency", "refused"),
                              rationale="its log cause says a dependency refused the connection"),
                log_healthy="application panic (code bug)",
                healthy=Answer(anchor="log cause: application panic (code bug)",
                               cause="its application panics, a code bug",
                               keys=("panic", "code"),
                               rationale="its log cause says the application panicked"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: dependency session has no endpoints", 6),),
                broken=Answer(anchor="dependency session has no endpoints",
                              cause="its readiness probe fails because the session dependency "
                                    "has no endpoints",
                              keys=("session", "endpoint"), confidence="medium",
                              rationale="its probe event says the session dependency has no endpoints",
                              link=True),
                events_healthy=(("Unhealthy", ("Readiness probe failed: HTTP probe returned 503, "
                                 "dependency check added in this revision"), 6),),
                healthy=Answer(anchor="dependency check added in this revision",
                               cause="its readiness check gained a dependency check in this "
                                     "revision",
                               keys=("check", "revision"),
                               rationale="its probe event names a check added in this revision"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="RestartLoop", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="session dependency has no endpoints; the worker exits and is restarted",
                events=_backoff(6),
                broken=Answer(anchor="session dependency has no endpoints",
                              cause="its worker restarts because the session dependency has no "
                                    "endpoints",
                              keys=("session", "endpoint"), confidence="medium",
                              rationale="its evidence says the session dependency has no endpoints",
                              link=True),
                evidence_healthy="the worker exits zero when it finds no work queued and is restarted",
                healthy=Answer(anchor="exits zero when it finds no work queued",
                               cause="its worker exits zero when it finds no work queued",
                               keys=("exits", "queued"),
                               rationale="its evidence says it exits cleanly with an empty queue"),
                none_phrase="its container keeps restarting"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the session service is scaled to zero",
        shown_cause="the shared session service was scaled to zero replicas, so every workload "
                    "that calls it fails",
        shown_remedy="Scale the session service back up; the flagged workloads need no change.",
    ),
    Story(
        key="image-pull-secret-expired", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ErrImagePull", issue="ErrImagePull",
                reason="container cannot pull its image",
                evidence="failed to authenticate pulling {image}",
                events=_pull(_PULL_SECRET_EXPIRED),
                events_healthy=_PULL_HEALTHY,
                broken=Answer(anchor="authentication token has expired",
                              cause="its image pull is refused because the registry "
                                    "authentication token has expired",
                              keys=("token", "expired"),
                              rationale="its pull event says the authentication token expired",
                              link=True),
                healthy=Answer(anchor="manifest unknown",
                               cause="its image manifest is unknown to the registry",
                               keys=("manifest", "unknown"),
                               rationale="its pull event says the manifest is unknown"),
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="DaemonSet", status="ImagePullBackOff", issue="ImagePullBackOff",
                reason="container cannot pull its image",
                evidence='Back-off pulling image "{image}"',
                events=_pull(_PULL_SECRET_EXPIRED),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its image cannot be pulled"),
            VictimText(
                workload_kind="Job", status="ErrImagePull", issue="ErrImagePull",
                reason="container cannot pull its image",
                evidence="failed to authenticate pulling the job image",
                events=_pull(_PULL_SECRET_EXPIRED),
                events_healthy=_PULL_HEALTHY,
                pulls=True, none_phrase="its job image cannot be pulled"),
        ),
        broken=World(pull_literal=_PULL_SECRET_EXPIRED),
        healthy=World(),
        shown_origin="the cluster-wide image pull secret",
        shown_cause="the cluster-wide image pull secret's registry token expired, so no workload "
                    "can pull its image",
        shown_remedy="Rotate the shared pull secret's registry token; the flagged workloads need "
                     "no change.",
    ),
    Story(
        key="shared-secret-key-renamed", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CreateContainerConfigError",
                issue="CreateContainerConfigError",
                reason="container could not build its environment",
                evidence="couldn't find key api-token in Secret shared-credentials",
                events=(("Failed", "Error: couldn't find key api-token in Secret shared-credentials: missing", 4),),
                broken=Answer(anchor="couldn't find key api-token in secret shared-credentials",
                              cause="the key api-token it reads is missing from the Secret "
                                    "shared-credentials",
                              keys=("token", "secret"),
                              rationale="its evidence says api-token is missing from the shared Secret",
                              link=True),
                evidence_healthy="couldn't find key legacy-token in Secret {ns}/app-secrets",
                events_healthy=(("Failed", "Error: couldn't find key legacy-token in Secret {ns}/app-secrets", 4),),
                healthy=Answer(anchor="couldn't find key legacy-token",
                               cause="its own manifest asks for legacy-token, which its Secret "
                                     "app-secrets does not hold",
                               keys=("legacy", "secrets"),
                               rationale="its evidence names a key missing from its own Secret"),
                none_phrase="its container cannot build its environment"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="panic: required credential api-token not found in environment",
                events=_backoff(7), log=_NO_SIGNATURE,
                broken=Answer(anchor="required credential api-token not found in environment",
                              cause="its container panics because the credential api-token it "
                                    "requires is not in its environment",
                              keys=("panics", "credential"),
                              rationale="its crash evidence says a required credential is missing",
                              link=True),
                evidence_healthy="panic: environment variable api-token never declared in this replica's own manifest",
                healthy=Answer(anchor="never declared in this replica's own manifest",
                               cause="its own manifest never declares the api-token variable",
                               keys=("manifest", "never"),
                               rationale="its crash evidence says its manifest never declared it"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Job", status="Init:CreateContainerConfigError",
                issue="Init:CreateContainerConfigError",
                reason="init container could not build its environment",
                evidence="secret key not found for env var API_TOKEN",
                events=(("Failed", "Error: secret key not found for env var API_TOKEN", 3),),
                broken=Answer(anchor="secret key not found for env var api_token",
                              cause="its init container cannot find the secret key for the env "
                                    "var API_TOKEN",
                              keys=("secret", "cannot"),
                              rationale="its init event says the secret key was not found"),
                none_phrase="its init container cannot build its environment"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the shared Secret shared-credentials",
        shown_cause="the shared platform Secret's key was renamed cluster-wide, so every workload "
                    "that reads it fails to start",
        shown_remedy="Restore the shared Secret's original key name (or add both keys during the "
                     "rename); the flagged workloads need no change.",
    ),
    Story(
        key="shared-pvc-multi-attach", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence="Multi-Attach error for volume pvc-{pvc}",
                events=(("FailedAttachVolume", ("Multi-Attach error for volume \"pvc-{pvc}\" Volume "
                           "is already exclusively attached to one node and can't be attached "
                           "to another"), 8),),
                broken=Answer(anchor="already exclusively attached to one node",
                              cause="its volume is still exclusively attached to another node",
                              keys=("exclusively", "attached"),
                              rationale="its attach event says the volume is held by one node",
                              link=True),
                events_healthy=(("FailedAttachVolume", ("Multi-Attach error for volume \"pvc-{pvc}\" "
                                 "Volume is already exclusively attached to one node, held by its "
                                 "own previous pod that is still terminating"), 8),),
                healthy=Answer(anchor="held by its own previous pod",
                               cause="its volume is held by its own previous pod, which is "
                                     "still terminating",
                               keys=("previous", "terminating"),
                               rationale="its attach event names its own previous pod"),
                none_phrase="its volume cannot be attached"),
            VictimText(
                workload_kind="Job", status="Pending", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence="unmounted volumes=[data]",
                events=(("FailedMount", ("Unable to attach or mount volumes: unmounted volumes=[data], "
                           "timed out waiting for the condition"), 6),),
                broken=Answer(anchor="timed out waiting for the condition",
                              cause="its volume cannot mount because the mount timed out "
                                    "waiting for the condition",
                              keys=("mount", "timed"), confidence="medium",
                              rationale="its mount event shows a timeout",
                              link=True),
                events_healthy=(("FailedMount", ("Unable to attach or mount volumes: unmounted "
                                 "volumes=[data]: underlying disk reports I/O errors"), 6),),
                healthy=Answer(anchor="underlying disk reports i/o errors",
                               cause="its underlying disk reports I/O errors",
                               keys=("disk", "errors"),
                               rationale="its mount event names a failing disk"),
                none_phrase="its volume cannot be mounted"),
            VictimText(
                workload_kind="Deployment", status="ContainerStartError", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to start container: timed out preparing volume pvc-{pvc}",
                events=(("Failed", "Error: failed to start container: timed out preparing volume pvc-{pvc}", 3),),
                log=_NO_SIGNATURE,
                broken=Answer(anchor="timed out preparing volume",
                              cause="its container cannot start because preparing its volume "
                                    "timed out",
                              keys=("preparing", "timed"),
                              rationale="its start error says volume preparation timed out"),
                evidence_healthy="failed to start container: postStart copy of 40 GiB ran past the 2 minute start deadline",
                healthy=Answer(anchor="poststart copy of 40 gib ran past",
                               cause="its postStart copy of 40 GiB ran past the start deadline",
                               keys=("poststart", "deadline"),
                               rationale="its start error names its own long copy"),
                none_phrase="its container could not be started"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="a stuck VolumeAttachment",
        shown_cause="one ReadWriteOnce PVC's VolumeAttachment will not release, wedging the "
                    "cluster's attach/detach queue so every other pod's volume attach or mount "
                    "stalls behind it",
        shown_remedy="Force-clear the stuck VolumeAttachment; the flagged workloads need no change.",
    ),
    Story(
        key="namespace-limitrange-lowered", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="OOMKilled", issue="OOMKilled",
                reason=_OOM,
                evidence="container exceeded its memory limit of 64Mi inherited from the namespace default",
                events=_backoff(7), log="ran out of memory in-process",
                broken=Answer(anchor="inherited from the namespace default",
                              cause="its container is killed at a 64Mi memory limit inherited "
                                    "from the namespace default",
                              keys=("memory", "inherited"),
                              rationale="its evidence says the limit came from the namespace default",
                              link=True),
                evidence_healthy="container exceeded its memory limit: its memory usage climbs past the default within minutes",
                healthy=Answer(anchor="its memory usage climbs past the default within minutes",
                               cause="its memory usage climbs past the default within minutes",
                               keys=("climbs", "default"),
                               rationale="its evidence names its own growing memory use"),
                none_phrase="its container is killed for memory"),
            VictimText(
                workload_kind="Job", status="Init:OOMKilled", issue="Init:OOMKilled",
                reason="init container was killed by the kernel out-of-memory handler",
                evidence="init container exceeded its memory limit of 64Mi inherited from the namespace default",
                events=_backoff(5),
                broken=Answer(anchor="inherited from the namespace default",
                              cause="its init container is killed at a 64Mi memory limit "
                                    "inherited from the namespace default",
                              keys=("memory", "inherited"),
                              rationale="its evidence says the limit came from the namespace default",
                              link=True),
                evidence_healthy="init container exceeded its memory limit: it loads a dataset larger than the 512Mi default",
                healthy=Answer(anchor="loads a dataset larger than the 512mi default",
                               cause="its init container loads a dataset larger than the 512Mi "
                                     "default",
                               keys=("dataset", "larger"),
                               rationale="its evidence names a dataset bigger than the limit"),
                none_phrase="its init container is killed for memory"),
            VictimText(
                workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="heap reservation failed: cannot allocate memory",
                events=_backoff(8), log="ran out of memory in-process",
                evidence_healthy="heap reservation failed: its -Xmx flag is above its own memory limit",
                healthy=Answer(anchor="its -xmx flag is above its own memory limit",
                               cause="its heap flag is set above its own memory limit",
                               keys=("heap", "limit"),
                               rationale="its evidence says its heap flag exceeds its limit"),
                none_phrase="its container keeps crashing"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the LimitRange in {scope}",
        shown_cause="the {scope} namespace's LimitRange had its default memory limit lowered, so "
                    "every pod there without its own explicit limit inherits too little",
        shown_remedy="Raise the LimitRange's default memory limit in {scope} back to its previous "
                     "value; the flagged workloads need no change.",
    ),
    Story(
        key="storageclass-pool-retired", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims; claim refused by provisioner: pool ssd-tier-a "
                           "is retired"), 5),),
                broken=Answer(anchor="pool ssd-tier-a is retired",
                              cause="its claim is refused because the storage pool ssd-tier-a "
                                    "is retired",
                              keys=("pool", "retired"),
                              rationale="its scheduling event says the pool is retired",
                              link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; requested size 2Ti exceeds the "
                                 "class maximum of 1Ti"), 5),),
                healthy=Answer(anchor="exceeds the class maximum of 1ti",
                               cause="its claim asks for more than the class maximum size",
                               keys=("class", "maximum"),
                               rationale="its scheduling event says the size is over the maximum"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Deployment", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence="AttachVolume.Attach failed for volume pvc-{pvc}: pool ssd-tier-a is retired",
                events=(("FailedAttachVolume", ("AttachVolume.Attach failed for volume \"pvc-{pvc}\": "
                           "pool ssd-tier-a is retired"), 4),),
                broken=Answer(anchor="pool ssd-tier-a is retired",
                              cause="its volume cannot attach because pool ssd-tier-a is retired",
                              keys=("attach", "retired"),
                              rationale="its attach event says the pool is retired",
                              link=True),
                evidence_healthy="AttachVolume.Attach failed for volume pvc-{pvc}: volume is still attached to a deleted node",
                events_healthy=(("FailedAttachVolume", ("AttachVolume.Attach failed for volume "
                                 "\"pvc-{pvc}\": volume is still attached to a deleted node"), 4),),
                healthy=Answer(anchor="still attached to a deleted node",
                               cause="its volume is still attached to a deleted node",
                               keys=("attached", "deleted"),
                               rationale="its attach event names a deleted node"),
                none_phrase="its volume cannot attach"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims"), 6),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; claim is waiting for first "
                                 "consumer in a zone with no node"), 6),),
                healthy=Answer(anchor="waiting for first consumer in a zone with no node",
                               cause="its claim waits for a first consumer in a zone with no node",
                               keys=("consumer", "zone"),
                               rationale="its scheduling event names an empty zone"),
                none_phrase="its pod cannot be scheduled"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the StorageClass ssd-premium",
        shown_cause="the ssd-premium StorageClass points at a storage pool that was retired, so "
                    "the provisioner refuses every new claim on that class",
        shown_remedy="Point the ssd-premium StorageClass at a live pool (or recreate the class); "
                     "the flagged workloads and their claims need no change.",
    ),
    Story(
        key="shared-nfs-server-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ContainerCreating", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence='MountVolume.SetUp failed for volume "{pvc}": mount.nfs: Connection timed out',
                events=(("FailedMount", 'MountVolume.SetUp failed for volume "{pvc}": mount.nfs: Connection timed out', 6),),
                broken=Answer(anchor="mount.nfs: connection timed out",
                              cause="its volume cannot mount because mount.nfs connection "
                                    "timed out",
                              keys=("mount", "timed"),
                              rationale="its mount event shows an NFS connection timeout",
                              link=True),
                evidence_healthy='MountVolume.SetUp failed for volume "{pvc}": mount.nfs: access denied by server while mounting /exports/old',
                events_healthy=(("FailedMount", ('MountVolume.SetUp failed for volume "{pvc}": mount.nfs: '
                                 "access denied by server while mounting /exports/old"), 6),),
                healthy=Answer(anchor="access denied by server while mounting",
                               cause="its mount is denied access by the server",
                               keys=("denied", "server"),
                               rationale="its mount event says the server denied access"),
                none_phrase="its volume cannot be mounted"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence='AttachVolume.Attach failed for volume "{pvc}": NFS server not responding',
                events=(("FailedAttachVolume", 'AttachVolume.Attach failed for volume "{pvc}": NFS server not responding', 4),),
                broken=Answer(anchor="nfs server not responding",
                              cause="its volume cannot attach because the NFS server is not "
                                    "responding",
                              keys=("attach", "responding"),
                              rationale="its attach event says the NFS server is not responding"),
                evidence_healthy='AttachVolume.Attach failed for volume "{pvc}": node image lacks the NFS client package',
                events_healthy=(("FailedAttachVolume", ('AttachVolume.Attach failed for volume "{pvc}": '
                                 "node image lacks the NFS client package"), 4),),
                healthy=Answer(anchor="lacks the nfs client package",
                               cause="its node image lacks the NFS client package",
                               keys=("client", "package"),
                               rationale="its attach event names a missing client package"),
                none_phrase="its volume cannot attach"),
            VictimText(
                workload_kind="DaemonSet", status="ContainerStartError", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to start container: mount source not ready",
                events=(("Failed", "Error: failed to start container: mount source not ready", 3),),
                log=_NO_SIGNATURE,
                broken=Answer(anchor="mount source not ready",
                              cause="its container cannot start because its mount source is "
                                    "not ready",
                              keys=("mount", "ready"),
                              rationale="its start error says the mount source is not ready"),
                evidence_healthy="failed to start container: hostPath directory missing from the node image",
                events_healthy=(("Failed", "Error: failed to start container: hostPath directory missing from the node image", 3),),
                healthy=Answer(anchor="hostpath directory missing from the node image",
                               cause="its hostPath directory is missing from the node image",
                               keys=("hostpath", "missing"),
                               rationale="its start error names a missing host directory"),
                none_phrase="its container could not be started"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the shared NFS server",
        shown_cause="the shared NFS server is down, so every pod that mounts a volume from it is "
                    "stuck at mount",
        shown_remedy="Bring the shared NFS server back (or fail over to its replica) and let the "
                     "kubelets retry their mounts; the flagged workloads need no change.",
    ),
    Story(
        key="provisioner-credentials-rotated", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims; provisioner: backend refused credentials"), 5),),
                broken=Answer(anchor="backend refused credentials",
                              cause="the provisioner's backend refused its credentials",
                              keys=("backend", "credentials"), confidence="medium",
                              rationale="its scheduling event says the backend refused the credentials",
                              link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; claim was rendered into a "
                                 "different namespace"), 5),),
                healthy=Answer(anchor="claim was rendered into a different namespace",
                               cause="its chart rendered the claim into a different namespace",
                               keys=("chart", "namespace"),
                               rationale="its scheduling event says the claim is in another namespace"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims"), 4),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; claim selector matches no "
                                 "PersistentVolume label"), 4),),
                healthy=Answer(anchor="selector matches no persistentvolume label",
                               cause="its claim selector matches no PersistentVolume label",
                               keys=("selector", "label"),
                               rationale="its scheduling event says the selector matches nothing"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence='AttachVolume.Attach failed for volume "{pvc}": attach failed',
                events=(("FailedAttachVolume", 'AttachVolume.Attach failed for volume "{pvc}": attach failed', 4),),
                evidence_healthy='AttachVolume.Attach failed for volume "{pvc}": volume is still attached to a node that was deleted',
                events_healthy=(("FailedAttachVolume", ('AttachVolume.Attach failed for volume "{pvc}": '
                                 "volume is still attached to a node that was deleted"), 4),),
                healthy=Answer(anchor="still attached to a node that was deleted",
                               cause="its volume is still attached to a node that was deleted",
                               keys=("attached", "deleted"),
                               rationale="its attach event names a deleted node"),
                none_phrase="its volume cannot attach"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the encrypted-ssd provisioner",
        shown_cause="the encrypted-ssd provisioner's backend credentials were rotated, so the "
                    "backend refuses every new volume request",
        shown_remedy="Update the encrypted-ssd provisioner's backend secret with the rotated "
                     "credentials and restart it; the flagged workloads need no change.",
    ),
    Story(
        key="storage-backend-full", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims; provisioner: backend out of space"), 5),),
                broken=Answer(anchor="backend out of space",
                              cause="the storage backend is out of space",
                              keys=("backend", "space"), confidence="medium",
                              rationale="its scheduling event says the backend is out of space",
                              link=True),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; claim requests 100Mi, below the "
                                 "class minimum of 1Gi"), 5),),
                healthy=Answer(anchor="below the class minimum of 1gi",
                               cause="its claim asks for less than the class minimum size",
                               keys=("class", "minimum"),
                               rationale="its scheduling event says the size is under the minimum"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="Job", status="Pending", issue="Unschedulable",
                reason=_UNBOUND,
                evidence="0/{nodes} nodes are available: {nodes} pod has unbound immediate PersistentVolumeClaims",
                events=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound immediate "
                           "PersistentVolumeClaims"), 6),),
                events_healthy=(("FailedScheduling", ("0/{nodes} nodes are available: pod has unbound "
                                 "immediate PersistentVolumeClaims; claim dataSource points at a "
                                 "VolumeSnapshot that no longer exists"), 6),),
                healthy=Answer(anchor="volumesnapshot that no longer exists",
                               cause="the snapshot its claim restores from no longer exists",
                               keys=("snapshot", "exists"),
                               rationale="its scheduling event names a pruned snapshot"),
                none_phrase="its pod cannot be scheduled"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence='AttachVolume.Attach failed for volume "{pvc}": attach failed',
                events=(("FailedAttachVolume", 'AttachVolume.Attach failed for volume "{pvc}": attach failed', 4),),
                none_phrase="its volume cannot attach"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the bulk-nvme storage backend",
        shown_cause="the bulk-nvme storage backend is out of space, so the provisioner cannot "
                    "carve a new volume for any claim on that class",
        shown_remedy="Free or add capacity on the bulk-nvme backend (delete released volumes or "
                     "extend the pool); the flagged workloads need no change.",
    ),
    Story(
        key="csi-driver-version-mismatch", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="ContainerCreating", issue="VolumeMountError",
                reason="volume could not be mounted",
                evidence='MountVolume.MountDevice failed for volume "{pvc}": stage failed',
                events=(("FailedMount", ('MountVolume.MountDevice failed for volume "{pvc}": stage '
                           "failed, node plugin does not implement the controller's CSI API version"), 5),),
                broken=Answer(anchor="does not implement the controller's csi api version",
                              cause="the node plugin does not implement the CSI API version "
                                    "the controller uses",
                              keys=("plugin", "version"), confidence="medium",
                              rationale="its mount event names a CSI API version mismatch",
                              link=True),
                evidence_healthy='MountVolume.MountDevice failed for volume "{pvc}": mount option nobarrier is not supported by the driver',
                events_healthy=(("FailedMount", ('MountVolume.MountDevice failed for volume "{pvc}": '
                                 "mount option nobarrier is not supported by the driver"), 5),),
                healthy=Answer(anchor="mount option nobarrier is not supported",
                               cause="its mount asks for an option the driver does not support",
                               keys=("option", "driver"),
                               rationale="its mount event names an unsupported option"),
                none_phrase="its volume cannot be mounted"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeAttachError",
                reason="volume could not be attached to the pod's node",
                evidence='AttachVolume.Attach failed for volume "{pvc}": api version mismatch with controller',
                events=(("FailedAttachVolume", ('AttachVolume.Attach failed for volume "{pvc}": '
                           "node plugin did not acknowledge the attach, api version mismatch with controller"), 4),),
                broken=Answer(anchor="api version mismatch with controller",
                              cause="its volume cannot attach because the node plugin's API "
                                    "version mismatches the controller",
                              keys=("version", "mismatches"), confidence="medium",
                              rationale="its attach event names an API version mismatch",
                              link=True),
                evidence_healthy='AttachVolume.Attach failed for volume "{pvc}": attachment names a node removed from the cluster',
                events_healthy=(("FailedAttachVolume", ('AttachVolume.Attach failed for volume "{pvc}": '
                                 "attachment names a node removed from the cluster"), 4),),
                healthy=Answer(anchor="attachment names a node removed from the cluster",
                               cause="its attachment names a node removed from the cluster",
                               keys=("attachment", "removed"),
                               rationale="its attach event names a removed node"),
                none_phrase="its volume cannot attach"),
            VictimText(
                workload_kind="Job", status="ContainerStartError", issue="ContainerStartError",
                reason=_CSE,
                evidence="failed to start container: the data volume was not staged before the start deadline",
                events=(("Failed", "Error: failed to start container: data volume not ready", 3),),
                log=_NO_SIGNATURE,
                evidence_healthy="failed to start container: its entrypoint fsck refuses the volume's unclean journal",
                events_healthy=(("Failed", "Error: failed to start container: entrypoint fsck refused the volume", 3),),
                healthy=Answer(anchor="its entrypoint fsck refuses the volume's unclean journal",
                               cause="its entrypoint fsck refuses the volume's unclean journal",
                               keys=("fsck", "journal"),
                               rationale="its start error names its own fsck check"),
                none_phrase="its container could not be started"),
        ),
        broken=World(),
        healthy=World(),
        shown_origin="the replicated-ssd CSI driver",
        shown_cause="the replicated-ssd CSI controller was upgraded ahead of its node plugins, so "
                    "volumes it provisions cannot be staged on any node",
        shown_remedy="Roll the replicated-ssd node plugin DaemonSet to the controller's version "
                     "(or roll the controller back); the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-egress-allowlist-stale", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: datastore check timed out", 6),),
                broken=Answer(anchor="egress-allowlist",
                              cause="the NetworkPolicy egress-allowlist no longer matches the datastore pods, so its readiness probe fails",
                              keys=('policy', 'datastore'),
                              rationale="its network policy line names egress-allowlist", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: datastore query exceeded its 1s timeout", 6),),
                healthy=Answer(anchor="query exceeded its 1s timeout",
                               cause="its readiness query exceeds its own 1s timeout",
                               keys=('query', 'timeout'),
                               rationale="its probe event names its own query timeout"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: datastore unreachable", 5),),
                broken=Answer(anchor="egress-allowlist",
                              cause="the NetworkPolicy egress-allowlist no longer matches the datastore pods, so its readiness probe fails",
                              keys=('policy', 'datastore'),
                              rationale="its network policy line names egress-allowlist", link=True),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
                issue="Init:CrashLoopBackOff", reason="init container keeps restarting",
                evidence="wait-for-datastore gave up after 120s", events=_backoff(6),
                broken=Answer(anchor="wait-for-datastore gave up after 120s",
                              cause="its init container gave up waiting for the datastore "
                                    "after 120s",
                              keys=("datastore", "waiting"),
                              rationale="its init evidence says the datastore wait gave up"),
                evidence_healthy="wait-for-datastore gave up after 120s, a deadline shorter than the datastore's own startup time",
                healthy=Answer(anchor="a deadline shorter than the datastore's own startup time",
                               cause="its init wait deadline is shorter than the datastore's own "
                                     "startup time",
                               keys=("deadline", "startup"),
                               rationale="its init evidence compares the deadline with startup"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "egress-allowlist", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy egress-allowlist in {scope}",
        shown_cause="the egress allow-list policy in {scope} no longer matches the datastore pods, so every pod's connection to the datastore is dropped",
        shown_remedy="Update the datastore rule in {scope}/egress-allowlist to the pods' current tier=data label; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-dns-egress-missing", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="last state terminated with exit code 1",
                events=_backoff(7), log="DNS resolution failed (name lookup)",
                broken=Answer(anchor="log cause: DNS resolution failed (name lookup)",
                              cause="its container fails a DNS name lookup",
                              keys=("name", "lookup"),
                              rationale="its log cause says a DNS name lookup failed"),
                evidence_healthy="last state terminated with exit code 1; its pod sets dnsPolicy None with no nameserver",
                healthy=Answer(anchor="dnspolicy none with no nameserver",
                               cause="its pod sets dnsPolicy None with no nameserver",
                               keys=("dnspolicy", "nameserver"),
                               rationale="its evidence names its own empty DNS config"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: peer lookup failed", 5),),
                broken=Answer(anchor="egress-to-app",
                              cause="the NetworkPolicy egress-to-app allows no DNS traffic, so its readiness probe fails",
                              keys=('policy', 'traffic'),
                              rationale="its network policy line names egress-to-app", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: peer hostname is misspelled in the StatefulSet's config", 5),),
                healthy=Answer(anchor="peer hostname is misspelled",
                               cause="its peer hostname is misspelled in its own config",
                               keys=('hostname', 'misspelled'),
                               rationale="its probe event names a misspelled hostname"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="wait-for-backend could not resolve the backend name",
                events=_backoff(5),
                broken=Answer(anchor="could not resolve the backend name",
                              cause="its init container could not resolve the backend name",
                              keys=("resolve", "backend"),
                              rationale="its init evidence says the backend name did not resolve"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "egress-to-app", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy egress-to-app in {scope}",
        shown_cause="the egress policy in {scope} allows no DNS traffic, so every pod there fails to resolve any name",
        shown_remedy="Add an egress rule to {scope}/egress-to-app allowing udp/53 to kube-system; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-namespace-label-drifted", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: broker check timed out", 6),),
                broken=Answer(anchor="egress-to-messaging",
                              cause="the NetworkPolicy egress-to-messaging blocks its broker traffic, so its readiness probe fails",
                              keys=('policy', 'broker'),
                              rationale="its network policy line names egress-to-messaging", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: broker login was revoked", 6),),
                healthy=Answer(anchor="broker login was revoked",
                               cause="its broker login was revoked in the last user cleanup",
                               keys=('login', 'revoked'),
                               rationale="its probe event says its broker login was revoked"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: broker publish timed out", 4),),
                broken=Answer(anchor="egress-to-messaging",
                              cause="the NetworkPolicy egress-to-messaging blocks its broker traffic, so its readiness probe fails",
                              keys=('policy', 'broker'),
                              rationale="its network policy line names egress-to-messaging", link=True),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="Job", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="broker connection timed out during startup",
                events=_backoff(6), log=_NO_SIGNATURE,
                broken=Answer(anchor="broker connection timed out during startup",
                              cause="its container cannot connect to the broker during startup",
                              keys=("broker", "startup"),
                              rationale="its crash evidence says the broker connection timed out"),
                none_phrase="its container keeps crashing"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "egress-to-messaging", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy egress-to-messaging in {scope}",
        shown_cause="the egress policy in {scope} names the messaging namespace by a label that was renamed, so no pod there can reach the message broker",
        shown_remedy="Update the namespaceSelector in {scope}/egress-to-messaging to the messaging namespace's current label; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-port-mismatch", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: cache check timed out", 6),),
                broken=Answer(anchor="egress-to-cache",
                              cause="the NetworkPolicy egress-to-cache opens the wrong cache port, so its readiness probe fails",
                              keys=('policy', 'cache'),
                              rationale="its network policy line names egress-to-cache", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: cache token has expired", 6),),
                healthy=Answer(anchor="cache token has expired",
                               cause="its probe pings the cache with a token that has expired",
                               keys=('token', 'expired'),
                               rationale="its probe event says its cache token expired"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
                reason="container keeps restarting",
                evidence="cache connection timed out during startup",
                events=_backoff(8), log=_NO_SIGNATURE,
                broken=Answer(anchor="cache connection timed out during startup",
                              cause="its container cannot connect to the cache during startup",
                              keys=("cache", "startup"),
                              rationale="its crash evidence says the cache connection timed out"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="cache write-behind queue overflowed, exiting to flush",
                events=_backoff(6),
                none_phrase="its container keeps restarting"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "egress-to-cache", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy egress-to-cache in {scope}",
        shown_cause="the egress policy in {scope} opens the cache's old port, so every connection to its new port is dropped",
        shown_remedy="Change the cache rule in {scope}/egress-to-cache from tcp/6379 to tcp/6380; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-allow-selector-typo", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: API check timed out", 6),),
                broken=Answer(anchor="allow-frontend-egress",
                              cause="the NetworkPolicy allow-frontend-egress selects nothing, so default-deny blocks its API traffic",
                              keys=('policy', 'selects'),
                              rationale="its network policy line names allow-frontend-egress", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: token rejected, service account that was deleted", 6),),
                healthy=Answer(anchor="service account that was deleted",
                               cause="its probe sends a token from a service account that was deleted",
                               keys=('service', 'account'),
                               rationale="its probe event names a deleted service account"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: API handshake timed out", 5),),
                broken=Answer(anchor="allow-frontend-egress",
                              cause="the NetworkPolicy allow-frontend-egress selects nothing, so default-deny blocks its API traffic",
                              keys=('policy', 'selects'),
                              rationale="its network policy line names allow-frontend-egress", link=True),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="Job", status="Init:CrashLoopBackOff", issue="Init:CrashLoopBackOff",
                reason="init container keeps restarting",
                evidence="wait-for-api gave up after 120s", events=_backoff(5),
                broken=Answer(anchor="wait-for-api gave up after 120s",
                              cause="its init container gave up waiting for the API after 120s",
                              keys=("waiting", "gave"),
                              rationale="its init evidence says the API wait gave up"),
                evidence_healthy="wait-for-api gave up after 120s: its proxy variable points at a host that was decommissioned",
                healthy=Answer(anchor="its proxy variable points at a host that was decommissioned",
                               cause="its proxy variable points at a host that was decommissioned",
                               keys=("proxy", "decommissioned"),
                               rationale="its init evidence names a dead proxy host"),
                none_phrase="its init container keeps crashing"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "allow-frontend-egress", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy allow-frontend-egress in {scope}",
        shown_cause="the {scope} frontend allow policy has a typo in its pod selector, so it selects nothing and the namespace's default-deny blocks every frontend pod's egress",
        shown_remedy="Fix the podSelector in {scope}/allow-frontend-egress from role=fronted to role=frontend; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-ingress-deny-all", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: cluster join got no reply", 6),),
                broken=Answer(anchor="deny-all-ingress",
                              cause="the NetworkPolicy deny-all-ingress blocks inbound traffic, so its readiness probe fails",
                              keys=('policy', 'inbound'),
                              rationale="its network policy line names deny-all-ingress", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: join step expects a reply on a port its container never opens", 6),),
                healthy=Answer(anchor="expects a reply on a port its container never opens",
                               cause="its join step expects a reply on a port its container never opens",
                               keys=('reply', 'opens'),
                               rationale="its probe event names a port nothing opens"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe on the container is failing",
                events=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: peer handshake did not complete", 4),),
                broken=Answer(anchor="deny-all-ingress",
                              cause="the NetworkPolicy deny-all-ingress blocks inbound traffic, so its readiness probe fails",
                              keys=('policy', 'inbound'),
                              rationale="its network policy line names deny-all-ingress"),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503, body: quorum size is one more than its replica count", 4),),
                healthy=Answer(anchor="quorum size is one more than its replica count",
                               cause="its quorum size is one more than its replica count",
                               keys=('quorum', 'replica'),
                               rationale="its probe event names its own quorum setting"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
                reason="container keeps restarting",
                evidence="watchdog: no scrape received in 60s, restarting",
                events=_backoff(6),
                none_phrase="its container keeps restarting"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "deny-all-ingress", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy deny-all-ingress in {scope}",
        shown_cause="a deny-all ingress policy in {scope} blocks every inbound connection, so pods there that need their peers or their callers cannot become ready",
        shown_remedy="Narrow or delete {scope}/deny-all-ingress and add allow rules for the peers and callers each pod needs; the flagged workloads need no change.",
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
