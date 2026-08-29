"""Kubernetes failure propagation: one origin, several downstream symptoms.

Every other table in this package describes ONE workload — a catalog entry is
a single pod's presentation with a single winning cause and its rivals. That
shape cannot express the thing an operator most wants named during an
incident: that six flagged workloads are six views of one broken component.

The gap is not neutral. `cases.multi` builds its constituents with
`rng.sample` over *distinct* catalog entries and summarises them as
"N workloads are failing for separate reasons." At seed 17 / size 5500 that
sentence appears in 825 of the 5500 training examples, no two constituents
ever share an entry, and no row anywhere in the curriculum contradicts it. So
the released model was trained *against* cross-workload attribution, in the
exact prompt shape `--investigate`'s local verdict mode sends: up to ten
flagged workloads and one summary.

This module is the counterexample as data, and it is EVAL-ONLY. Nothing here
is generated into train or val. The measurement has to exist and has to fail
before any attempt is made to teach the correction — an eval change that could
not fail the model it replaced is not a fix.

Each scenario is one ORIGIN and two to four VICTIMS. A victim renders as an
ordinary flagged workload with an ordinary pod-level symptom and an ordinary,
locally-plausible candidate carrying `attributed` — because that is what
kubeagent's deterministic pass really produces. Its attribution runs per
workload and has no cross-workload view, so it attributes locally and it is
confidently wrong. The shared cause is on every menu too, trailing and tagged
`outranked`, so tag and position both point away from the answer.

TWO causes appear on all N menus: the shared cause and a `distractor_cause`
that the evidence rules out. That is deliberate. Without it, "name the string
that appears on every menu" scores the slice while reading nothing — a
shortcut that happens to be right here, and one that no other slice would
catch because no other slice has a common string. With it, the common-string
heuristic is a coin flip and only the evidence separates the two.

A fourth shortcut is closed the same way. `confidence_carried` is maxed by
copying the `[confidence: X]` string off the candidate head line, so a slice
whose victims all carry the same grade would let a copier score the row's
confidence without judging anything. `pass_confidence` therefore VARIES within
a scenario — it is the deterministic pass's own grade for its own wrong local
attribution — while the expected answer is one scenario-level grade for the
shared cause. Copying now produces a disagreement instead of a pass.

What this slice CANNOT detect: the same limit every probe in this repo has.
Its scenarios are not in training at all today, so a pass here is evidence the
model generalises to a shape it never saw — but once these scenarios are ever
trained on, a pass stops meaning that, and the slice needs held-out origins
the way `contradiction_probe` needed held-out entries.

Two real propagation families are deliberately ABSENT: a blocking admission
webhook and an exhausted ResourceQuota. Both stop the pod from being created
at all, so they surface as `FailedCreate` on the workload — a kind
`internal/knownissues` does not document and `vocab.ISSUE_KINDS` does not
admit. Adding them would mean widening a closed vocabulary from the eval side,
which is backwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The blast radius answers "how much of the cluster does this origin reach" —
# the field that makes a propagation graph useful rather than decorative.
BLAST_RADII = ("cluster", "node", "namespace")

# The memorised sentence this slice exists to measure. `cases.multi` writes it
# on every multi-workload training row; here it is always the wrong answer.
SEPARATE_REASONS = "failing for separate reasons"


@dataclass(frozen=True)
class Victim:
    """One downstream workload as the deterministic pass would present it."""

    workload_kind: str
    status: str
    issue: str  # must be one of vocab.ISSUE_KINDS
    reason: str
    evidence: str
    next_step: str
    command: str
    local_cause: str  # the decoy: locally plausible, carries `attributed`
    local_reason: str
    read: tuple[str, str]  # (label, content) — this victim's own evidence read
    log_cause: str = ""
    # The deterministic pass's OWN grade for its (wrong) local attribution.
    # Varied within a scenario on purpose — see the module docstring on
    # confidence_carried.
    pass_confidence: str = "high"
    network_policies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Propagation:
    key: str
    blast_radius: str
    # None for cluster-wide origins; "ns" or "node" for the field every victim
    # must share, so the rendered scenario is coherent and the answer string can
    # name it.
    scope_field: str | None
    origin: str  # one clause naming the broken component
    shared_cause: str  # the ONE correct cause, verbatim on every menu
    shared_reason: str
    distractor_cause: str  # also on every menu; the evidence rules it out
    distractor_reason: str
    rationale: str  # per-victim rationale template
    remedy: str  # the second summary line: fix the origin, not the victims
    confidence: str  # the expected grade for the shared attribution
    origin_read: tuple[str, str]
    victims: tuple[Victim, ...]
    shared_verdict: str = "outranked"
    distractor_verdict: str = "ruled_out"
    notes: str = field(default="")


_COREDNS = Propagation(
    key="coredns-down",
    blast_radius="cluster",
    scope_field=None,
    origin="CoreDNS has no ready replicas",
    shared_cause="CoreDNS is down cluster-wide, so no pod can resolve service names",
    shared_reason="kube-system/coredns reports 0 of 2 replicas ready",
    distractor_cause="the cluster network plugin is dropping pod-to-pod traffic",
    distractor_reason="pods on separate nodes still reach each other on their pod addresses",
    rationale="the workload's own failure is a name lookup that cannot succeed while "
              "CoreDNS has no ready replica",
    remedy="Repair the CoreDNS Corefile; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/coredns (Deployment)",
        ("Replicas:  2 desired | 2 updated | 2 total | 0 available | 2 unavailable\n"
         "Pods:      coredns-7d8f9c4b5-2xk4m   0/1  CrashLoopBackOff  9 restarts\n"
         "           coredns-7d8f9c4b5-qp7rt   0/1  CrashLoopBackOff  9 restarts\n"
         "Last log:  Corefile:8 - Error during parsing: unknown directive 'foward'"),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="dial tcp: lookup postgres.data.svc.cluster.local: no such host",
            next_step="check the database hostname the container is configured with",
            command="kubectl -n {ns} get deploy {name} -o yaml",
            local_cause="the database service name is misspelled in the workload's configuration",
            local_reason="the container exits immediately after a failed lookup",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: name resolution failed for "
                   "postgres.data.svc.cluster.local (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 12 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            next_step="check the readiness probe timeout for {name}",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the readiness probe timeout is too short for this workload",
            local_reason="every probe attempt ends at its deadline",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  12x  kubelet  Readiness probe failed: "
                   "checking dependency: lookup sessions.auth.svc.cluster.local: "
                   "server misbehaving")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 2",
            log_cause="cannot join cluster peer {name}-0.{name}.{ns}.svc.cluster.local",
            next_step="check that the headless Service for {name} exists",
            command="kubectl -n {ns} get svc {name} -o yaml",
            local_cause="the headless Service for the StatefulSet was deleted",
            local_reason="peer discovery by name is failing for every replica",
            read=("get_related service {ns}/{name}",
                  ("type: ClusterIP (headless)\nselector: app={name}\n"
                   "ready endpoints: 0 of 3")),
            pass_confidence="high",
        ),
    ),
)

_NODE_LOST = Propagation(
    key="node-not-ready",
    blast_radius="node",
    scope_field="node",
    origin="the kubelet on one node stopped posting status",
    shared_cause="node {node} is NotReady, so the pods it held are gone and their "
                 "replacements have nowhere to run",
    shared_reason="{node} has been Ready=Unknown for six minutes and carries the "
                  "unreachable taint",
    distractor_cause="the workloads were scaled down to zero replicas",
    distractor_reason="each controller still declares its original replica count",
    rationale="the workload's symptom is what losing {node} does to it, not a change "
              "in the workload itself",
    remedy="Recover or drain {node}; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Conditions:\n"
         "  Ready            Unknown   NodeStatusUnknown   Kubelet stopped posting node status.\n"
         "  MemoryPressure   Unknown   NodeStatusUnknown\n"
         "  DiskPressure     Unknown   NodeStatusUnknown\n"
         "Taints:  node.kubernetes.io/unreachable:NoExecute\n"
         "         node.kubernetes.io/unreachable:NoSchedule"),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Pending", issue="Unschedulable",
            reason="0/3 nodes are available",
            evidence="1 node(s) were unschedulable, 2 Insufficient cpu",
            next_step="lower the CPU request for {container} or add capacity",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the pod requests more CPU than any remaining node has free",
            local_reason="the scheduler reports Insufficient cpu on both healthy nodes",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  kubelet  0/3 nodes are available: "
                   "1 node(s) were unschedulable, 2 Insufficient cpu.")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeAttachError",
            reason="volume {pvc} could not be attached",
            evidence="Multi-Attach error: volume is already exclusively attached to one node",
            next_step="confirm no other pod holds {pvc}",
            command="kubectl -n {ns} describe pvc {pvc}",
            local_cause="a second pod already holds the ReadWriteOnce claim {pvc}",
            local_reason="the volume reports an exclusive attachment elsewhere",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nAccess Modes: RWO\n"
                   "Attached to node: {node}  (node is not Ready)")),
            pass_confidence="medium",
        ),
    ),
)

_STORAGE = Propagation(
    key="storage-provisioner-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the dynamic volume provisioner has no ready replica",
    shared_cause="the storage provisioner is down, so no new PersistentVolumeClaim "
                 "can bind",
    shared_reason="no PersistentVolume has been provisioned cluster-wide for twenty "
                  "minutes",
    distractor_cause="the namespace ResourceQuota is refusing new pods",
    distractor_reason="the quota reports two of ten pods used in each namespace",
    rationale="the workload is waiting on a volume that nothing is left to create",
    remedy="Restore the provisioner; the pending claims bind on their own afterwards.",
    confidence="high",
    origin_read=(
        "get_related storageclass standard",
        ("provisioner: example.com/local-path\n"
         "controller local-path-storage/local-path-provisioner: 0/1 ready, "
         "CrashLoopBackOff\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/3 nodes are available: 3 pod has unbound immediate "
                     "PersistentVolumeClaims",
            next_step="check whether {pvc} has bound",
            command="kubectl -n {ns} get pvc {pvc}",
            local_cause="the StatefulSet asks for a storage class that does not exist",
            local_reason="the claim never leaves Pending",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: standard\n"
                   "Events: Normal  ExternalProvisioning  waiting for a volume to be "
                   "created by the external provisioner")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/3 nodes are available: 3 pod has unbound immediate "
                     "PersistentVolumeClaims",
            next_step="check whether {pvc} has bound",
            command="kubectl -n {ns} get pvc {pvc}",
            local_cause="the Job requests a volume larger than the cluster can provide",
            local_reason="no node advertises enough free storage for the claim",
            read=("get_events {ns}/{name}",
                  ("Normal  WaitForFirstConsumer  persistentvolume-controller  "
                   "waiting for first consumer to be created before binding\n"
                   "Normal  ExternalProvisioning  waiting for a volume to be created")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating", issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the condition",
            next_step="check the volume backing {pvc}",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the filesystem on {pvc} is corrupt and will not mount",
            local_reason="the mount times out rather than failing outright",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  Unable to attach or mount "
                   "volumes: unmounted volumes=[{pvc}], timed out waiting for the "
                   "condition")),
            pass_confidence="high",
        ),
    ),
)

_REGISTRY = Propagation(
    key="registry-unreachable",
    blast_radius="cluster",
    scope_field=None,
    origin="the image registry stopped answering from inside the cluster",
    shared_cause="the image registry is unreachable, so no workload can pull an image",
    shared_reason="every pull in the cluster fails at the same registry host, before "
                  "any manifest is requested",
    distractor_cause="the images were deleted from the registry",
    distractor_reason="the pulls never get far enough to ask for a manifest",
    rationale="the workload cannot start because the registry it pulls from is not "
              "answering, which is true of every image in the cluster right now",
    remedy="Restore registry reachability; no workload manifest needs editing.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=Failed)",
        ("12 pods across 5 namespaces report the same error:\n"
         "  Failed to pull image: rpc error: code = Unknown desc = failed to resolve "
         "reference: dial tcp: i/o timeout\n"
         "distinct registry hosts in the failing set: 1"),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff", issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            next_step="confirm the tag {image} exists",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the image tag {image} does not exist in the registry",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image {image}: "
                   "dial tcp: i/o timeout")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull", issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            next_step="check the pull secret in {ns}",
            command="kubectl -n {ns} get secrets",
            local_cause="the image pull secret in this namespace is missing or wrong",
            local_reason="the pull fails before the image layers are fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  failed to resolve reference: dial tcp: "
                   "i/o timeout")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job", status="Init:ImagePullBackOff", issue="Init:ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container {init_container}",
            next_step="check the init container image name",
            command="kubectl -n {ns} get job {name} -o yaml",
            local_cause="the init container image name has a typo",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n    State: Waiting\n"
                   "    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  dial tcp: i/o timeout")),
            pass_confidence="high",
        ),
    ),
)

_DISK_PRESSURE = Propagation(
    key="node-disk-pressure",
    blast_radius="node",
    scope_field="node",
    origin="one node filled its disk and started refusing and evicting pods",
    shared_cause="node {node} is under disk pressure, so it is evicting pods and "
                 "refusing new ones",
    shared_reason="{node} reports DiskPressure=True and carries the disk-pressure taint",
    distractor_cause="the cluster has run out of allocatable memory",
    distractor_reason="memory requests stand at 41 percent of allocatable on every node",
    rationale="the workload's symptom follows from {node} having no disk left, not "
              "from anything in the workload",
    remedy="Reclaim disk on {node}; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Conditions:\n"
         "  DiskPressure   True   KubeletHasDiskPressure   kubelet has disk pressure\n"
         "  Ready          True   KubeletReady\n"
         "Taints:  node.kubernetes.io/disk-pressure:NoSchedule\n"
         "Allocated resources:\n  cpu     1200m (30%)\n  memory  2Gi (41%)"),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Pending", issue="Unschedulable",
            reason="0/3 nodes are available",
            evidence="1 node(s) had untolerated taint node.kubernetes.io/disk-pressure",
            next_step="review the scheduling constraints for {name}",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the pod is missing a toleration for a tainted node",
            local_reason="the scheduler names an untolerated taint",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                   "available: 1 node(s) had untolerated taint "
                   "node.kubernetes.io/disk-pressure, 2 Insufficient cpu.")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: no space left on device",
            next_step="check disk usage where {name} is scheduled",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the workload's emptyDir volume has no size limit and filled up",
            local_reason="the container cannot write its writable layer",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                   "create containerd task: no space left on device")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 137",
            log_cause="cannot write checkpoint: no space left on device",
            next_step="check the volume the agent writes to",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the agent's checkpoint volume is too small for its retention "
                        "setting",
            local_reason="the agent dies while writing its checkpoint",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: write failed, device full (3 of 3 sampled "
                   "restarts)")),
            pass_confidence="high",
        ),
    ),
)

_NETPOL = Propagation(
    key="networkpolicy-deny-all",
    blast_radius="namespace",
    scope_field="ns",
    origin="a default-deny NetworkPolicy was applied to a whole namespace",
    shared_cause="a default-deny NetworkPolicy in {ns} blocks all egress from its pods",
    shared_reason="every pod in {ns} is selected by a policy that declares no egress rule",
    distractor_cause="the workloads' service accounts lost permission to read Secrets",
    distractor_reason="no Secret read appears in any of the failing containers' logs",
    rationale="the workload's connection failures are what a namespace-wide egress "
              "deny does to everything in {ns}",
    remedy="Add the egress rules {ns} needs, or remove the deny-all policy.",
    confidence="medium",
    origin_read=(
        "get_related networkpolicy {ns}/default-deny",
        ("podSelector: empty (selects every pod in the namespace)\n"
         "policyTypes: Ingress, Egress\n"
         "egress: [] (no rules — all egress denied)\n"
         "pods selected: 6 of 6"),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="connection timed out reaching payments-api.payments.svc.cluster.local",
            next_step="check whether the payments API is reachable from {ns}",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the payments API the workload depends on is down",
            local_reason="every outbound connection ends in a timeout",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: outbound connection timed out (3 of 3 sampled "
                   "restarts)")),
            pass_confidence="high",
            network_policies=("default-deny",),
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 9 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            next_step="check the readiness endpoint for {name}",
            command="kubectl -n {ns} describe pod {pod}",
            local_cause="the readiness endpoint for this workload returns an error",
            local_reason="the probe consistently reports the pod not ready",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  9x  kubelet  Readiness probe failed: "
                   "upstream check timed out")),
            pass_confidence="medium",
            network_policies=("default-deny",),
        ),
    ),
)

_SCENARIOS = (_COREDNS, _NODE_LOST, _STORAGE, _REGISTRY, _DISK_PRESSURE, _NETPOL)


def all_scenarios() -> tuple[Propagation, ...]:
    return _SCENARIOS


def by_key() -> dict[str, Propagation]:
    return {p.key: p for p in _SCENARIOS}
