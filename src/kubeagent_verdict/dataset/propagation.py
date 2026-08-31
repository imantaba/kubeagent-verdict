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

This module is the counterexample as data. `_SCENARIOS` — the six reached by
`all_scenarios()` — is EVAL-ONLY and stays that way; `_TRAINING_SCENARIOS`,
reached by `trainable_scenarios()`, is a disjoint pool added afterwards and is
the only part training ever sees. The order matters and was kept: the
measurement had to exist and had to FAIL before any attempt was made to teach
the correction — an eval change that could not fail the model it replaced is
not a fix. It failed on 2026-08-30, `separate_reasons_rate` 1.0 on all ten
probe rows, and the trainable pool is the answer to that.

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
A pass is evidence of generalisation only while the probe's own six scenarios
stay out of training — the day one of them is trained on, a pass stops meaning
that. Training now teaches this shape, so the guarantee rests entirely on the
two pools being disjoint, and disjoint in the graded ANSWER STRING as well as
in the key: `drop_held_out` compares group identity and never reads the text,
so two scenarios could carry different keys, the same `shared_cause`, and a
clean contamination report over a model that had memorised the answer.
`tests/test_shared_origin_training.py` asserts both halves.

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
    local_cause: str  # the decoy: locally plausible, carries `attributed`
    local_reason: str
    read: tuple[str, str]  # (label, content) — this victim's own evidence read
    # The SAME read, same label, in the world where the origin is fine. Empty
    # means `read[1]` is already true there and is reused verbatim.
    #
    # Only `shared_origin_decoy_probe` renders this, and it needs one wherever
    # the victim's own read ASSERTS the origin is broken -- a probe event
    # naming a resolver failure, a PVC saying the node is not Ready. Left
    # empty, that row would show a healthy origin and evidence contradicting
    # it, and its "correct" answer would be indefensible. Five of the sixteen
    # eval victims need none: their evidence is a local symptom that reads the
    # same either way.
    healthy_read_content: str = ""
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
    # The SAME origin read, showing the component healthy. Every scenario
    # carries one, and the two pools render it for different reasons: a
    # trainable one is what a `multi` row puts at the head of its reads so that
    # "an origin read is present" stops being a free answer (`cases.multi`),
    # and an eval one is the whole of `cases.shared_origin_decoy_probe`, which
    # asks the same question with this content in place of `origin_read[1]`
    # and takes the opposite answer. The eval six carried `""` until that
    # slice existed; nothing rendered it, and the exam could not tell a model
    # that reads the content from one that matches the label.
    healthy_origin_content: str = ""
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
    healthy_origin_content=(
        ("Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
         "Pods:      coredns-7d8f9c4b5-2xk4m   1/1  Running  0 restarts\n"
         "           coredns-7d8f9c4b5-qp7rt   1/1  Running  0 restarts\n"
         "Last log:  [INFO] plugin/reload: Running configuration SHA512 unchanged")
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="dial tcp: lookup postgres.data.svc.cluster.local: no such host",
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
            local_cause="the readiness probe timeout is too short for this workload",
            local_reason="every probe attempt ends at its deadline",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  12x  kubelet  Readiness probe failed: "
                   "checking dependency: lookup sessions.auth.svc.cluster.local: "
                   "server misbehaving")),
            # A resolver answering SERVFAIL is a broken resolver. With CoreDNS
            # healthy the probe still fails, on its own one-second budget.
            healthy_read_content=(
                "Warning  Unhealthy  12x  kubelet  Readiness probe failed: "
                "checking dependency sessions.auth.svc.cluster.local: "
                "context deadline exceeded after 1s"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 2",
            log_cause="cannot join cluster peer {name}-0.{name}.{ns}.svc.cluster.local",
            local_cause="the headless Service for the StatefulSet was deleted",
            local_reason="peer discovery by name is failing for every replica",
            read=("get_related service {ns}/{name}",
                  ("type: ClusterIP (headless)\nselector: app={name}\n"
                   "ready endpoints: 0 of 3")),
            # Deleted, not merely endpoint-less: with DNS healthy the local cause
            # is only true if the Service is actually gone.
            healthy_read_content=(
                "type: <none>\nselector: n/a\n"
                "ready endpoints: n/a  (no Service named {name} in {ns})"),
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
    healthy_origin_content=(
        ("Conditions:\n"
         "  Ready            True    KubeletReady   kubelet is posting ready status\n"
         "  MemoryPressure   False   KubeletHasSufficientMemory\n"
         "  DiskPressure     False   KubeletHasNoDiskPressure\n"
         "Taints:  <none>")
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Pending", issue="Unschedulable",
            reason="0/3 nodes are available",
            evidence="1 node(s) were unschedulable, 2 Insufficient cpu",
            local_cause="the pod requests more CPU than any remaining node has free",
            local_reason="the scheduler reports Insufficient cpu on both healthy nodes",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  kubelet  0/3 nodes are available: "
                   "1 node(s) were unschedulable, 2 Insufficient cpu.")),
            # No node is unschedulable while the origin node is Ready, so the
            # shortfall has to be capacity on all three.
            healthy_read_content=(
                "Warning  FailedScheduling  kubelet  0/3 nodes are available: "
                "3 Insufficient cpu."),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating", issue="VolumeAttachError",
            reason="volume {pvc} could not be attached",
            evidence="Multi-Attach error: volume is already exclusively attached to one node",
            local_cause="a second pod already holds the ReadWriteOnce claim {pvc}",
            local_reason="the volume reports an exclusive attachment elsewhere",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nAccess Modes: RWO\n"
                   "Attached to node: {node}  (node is not Ready)")),
            healthy_read_content=(
                "Status: Bound\nAccess Modes: RWO\n"
                "Attached to node: {node}  (node is Ready)"),
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
    healthy_origin_content=(
        ("provisioner: example.com/local-path\n"
         "controller local-path-storage/local-path-provisioner: 1/1 ready, Running\n"
         "PersistentVolumes bound in the last 20m: 7")
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/3 nodes are available: 3 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the StatefulSet asks for a storage class that does not exist",
            local_reason="the claim never leaves Pending",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: standard\n"
                   "Events: Normal  ExternalProvisioning  waiting for a volume to be "
                   "created by the external provisioner")),
            # The origin read shows `standard` provisioning normally, so a claim
            # that never binds has to name a class that does not exist.
            healthy_read_content=(
                "Status: Pending\nStorageClass: fast-ssd\n"
                "Events: Warning  ProvisioningFailed  persistentvolume-controller  "
                "storageclass.storage.k8s.io \"fast-ssd\" not found"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/3 nodes are available: 3 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the Job requests a volume larger than the cluster can provide",
            local_reason="no node advertises enough free storage for the claim",
            read=("get_events {ns}/{name}",
                  ("Normal  WaitForFirstConsumer  persistentvolume-controller  "
                   "waiting for first consumer to be created before binding\n"
                   "Normal  ExternalProvisioning  waiting for a volume to be created")),
            # A working provisioner that refuses one claim refuses it for a
            # reason, and says so.
            healthy_read_content=(
                "Normal   WaitForFirstConsumer  persistentvolume-controller  "
                "waiting for first consumer to be created before binding\n"
                "Warning  ProvisioningFailed    example.com/local-path  failed to "
                "provision volume: requested 4Ti exceeds the 512Gi free on every node"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating", issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the condition",
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
    healthy_origin_content=(
        ("pods reporting an image pull error name no registry host in common, and\n"
         "no two of them fail the same way: manifest unknown, unauthorized,\n"
         "no such host\n"
         "distinct registry hosts in the failing set: one per failing pod")
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff", issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the image tag {image} does not exist in the registry",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image {image}: "
                   "dial tcp: i/o timeout")),
            # The only healthy-world read that reaches the registry at all, and
            # the one that leaves `distractor_reason` stale -- see the module
            # docstring on what the evidence overrides.
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image {image}: "
                "manifest unknown"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull", issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            local_cause="the image pull secret in this namespace is missing or wrong",
            local_reason="the pull fails before the image layers are fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  failed to resolve reference: dial tcp: "
                   "i/o timeout")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  failed to resolve reference: "
                "unauthorized: authentication required"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job", status="Init:ImagePullBackOff", issue="Init:ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container {init_container}",
            local_cause="the init container image name has a typo",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n    State: Waiting\n"
                   "    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  dial tcp: i/o timeout")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  no such host"),
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
    healthy_origin_content=(
        ("Conditions:\n"
         "  DiskPressure   False  KubeletHasNoDiskPressure  kubelet has no disk pressure\n"
         "  Ready          True   KubeletReady\n"
         "Taints:  <none>\n"
         "Allocated resources:\n"
         "  cpu     1200m (30%)\n"
         "  memory  2Gi (41%)")
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Pending", issue="Unschedulable",
            reason="0/3 nodes are available",
            evidence="1 node(s) had untolerated taint node.kubernetes.io/disk-pressure",
            local_cause="the pod is missing a toleration for a tainted node",
            local_reason="the scheduler names an untolerated taint",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                   "available: 1 node(s) had untolerated taint "
                   "node.kubernetes.io/disk-pressure, 2 Insufficient cpu.")),
            # A node with no DiskPressure carries no disk-pressure taint, so the
            # taint the pod fails to tolerate must be one an operator set.
            healthy_read_content=(
                "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                "available: 1 node(s) had untolerated taint dedicated=gpu, "
                "2 Insufficient cpu."),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: no space left on device",
            local_cause="the workload's emptyDir volume has no size limit and filled up",
            local_reason="the container cannot write its writable layer",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                   "create containerd task: no space left on device")),
            # Pod-local exhaustion, not the node's: the emptyDir fills the pod's
            # own ephemeral budget while the node reports no disk pressure.
            healthy_read_content=(
                "Node: {node}\n"
                "Ephemeral storage: pod limit 1Gi, currently used 1Gi\n"
                "Events: Warning  Failed  kubelet  Error: failed to create "
                "containerd task: no space left on device"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 137",
            log_cause="cannot write checkpoint: no space left on device",
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
    healthy_origin_content=(
        ("podSelector: app=metrics-collector\n"
         "policyTypes: Ingress\n"
         "ingress: allow from namespaceSelector kube-system\n"
         "pods selected: 0 of 6")
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="connection timed out reaching payments-api.payments.svc.cluster.local",
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


# ------------------------------------------------------- the trainable pool
#
# The six scenarios above stay EVAL-ONLY. These are what training sees, and
# they exist because of the sentence in this module's docstring: once the eval
# scenarios are trained on, a pass on the probe stops being evidence of
# generalisation and becomes evidence of memory. `catalog` already solved this
# shape -- 19 trainable entries, 9 held out -- and this is the same split
# applied to propagation. Nothing here shares a key, a `shared_cause` or a
# `distractor_cause` with the eval six; `tests/test_shared_origin_training.py`
# fails the suite if that ever stops being true.
#
# Every one also carries `healthy_origin_content`: the same read, same label,
# showing the component fine. `multi` puts that at the head of its reads on a
# third of its rows, which is the only reason a model cannot answer this whole
# slice by noticing that a cluster-scoped read exists.

_T_CA = Propagation(
    key="internal-ca-expired",
    blast_radius="cluster",
    scope_field=None,
    origin="the cluster's internal certificate authority expired",
    shared_cause="the internal certificate authority expired, so every mutual-TLS "
                 "connection between workloads is refused",
    shared_reason="the shared trust bundle's issuing certificate passed its notAfter "
                  "date two hours ago",
    distractor_cause="the workloads' service account tokens were rotated without a reload",
    distractor_reason="every container still presents a token the API server accepts",
    rationale="the workload's failure is a refused TLS handshake, which is what an "
              "expired issuer does to every connection in the cluster",
    remedy="Reissue the internal CA and roll the trust bundle; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_related secret shared-trust-bundle (cluster-wide)",
        ("notAfter: expired 2h ago\n"
         "issuer: cluster-internal-ca\n"
         "workloads mounting this bundle: 14 across 6 namespaces"),
    ),
    healthy_origin_content=(
        "notAfter: 288 days remaining\n"
        "issuer: cluster-internal-ca\n"
        "workloads mounting this bundle: 14 across 6 namespaces"
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="tls: failed to verify certificate: certificate has expired",
            local_cause="the workload's own client certificate was never renewed",
            local_reason="the container exits during its first outbound call",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: TLS certificate verification failed "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 8 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="the readiness probe points at a port the container stopped serving",
            local_reason="every probe attempt is refused rather than timing out",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  8x  kubelet  Readiness probe failed: "
                   "remote error: tls: bad certificate")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="x509: certificate has expired or is not yet valid",
            local_cause="the peer trust store mounted by {name} was replaced with a bad file",
            local_reason="the replicas refuse each other's certificates",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: peer certificate rejected as expired "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
    ),
)

_T_KUBE_PROXY = Propagation(
    key="kube-proxy-degraded",
    blast_radius="node",
    scope_field="node",
    origin="kube-proxy on one node stopped programming Service routes",
    shared_cause="kube-proxy on node {node} stopped programming Service routes, so "
                 "pods scheduled there reach no Service",
    shared_reason="{node} has applied no Service route update for eleven minutes while "
                  "its peers are current",
    distractor_cause="the Services these workloads call have no ready endpoints",
    distractor_reason="every Service named in the failing calls reports its full "
                      "complement of ready endpoints",
    rationale="the workload cannot reach a Service from {node}, which is true of "
              "everything scheduled there right now",
    remedy="Restart kube-proxy on {node}; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("last Service route sync: 11m ago (peer nodes: 4s ago)\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kube-proxy pod on this node: 1/1 Running, 0 restarts"),
    ),
    healthy_origin_content=(
        "last Service route sync: 3s ago (peer nodes: 4s ago)\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kube-proxy pod on this node: 1/1 Running, 0 restarts"
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="connection refused dialing the checkout Service address",
            local_cause="the upstream the workload calls is refusing connections",
            local_reason="every outbound call is refused immediately",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection refused to a Service address "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 14 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="the agent's readiness threshold is set too aggressively",
            local_reason="the probe never reports the pod ready",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  14x  kubelet  Readiness probe failed: "
                   "dependency check could not reach its Service")),
            pass_confidence="medium",
        ),
    ),
)

_T_CONFIGMAP = Propagation(
    key="shared-configmap-deleted",
    blast_radius="namespace",
    scope_field="ns",
    origin="the ConfigMap every workload in one namespace mounts was deleted",
    shared_cause="the shared ConfigMap in {ns} was deleted, so no pod there can build "
                 "its container environment",
    shared_reason="every pod in {ns} references a ConfigMap the API server no longer has",
    distractor_cause="the namespace {ns} is being torn down",
    distractor_reason="{ns} is Active and its other objects are untouched",
    rationale="the workload cannot start because the ConfigMap it mounts is gone, "
              "which is true of every pod in {ns}",
    remedy="Restore the shared ConfigMap in {ns}; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related configmap {ns}/app-settings",
        ("Error from server (NotFound): the ConfigMap app-settings does not exist\n"
         "namespace {ns}: Active\n"
         "pods in {ns} referencing it: 6 of 6"),
    ),
    healthy_origin_content=(
        "Name: app-settings, 7 keys\n"
        "namespace {ns}: Active\n"
        "pods in {ns} referencing it: 6 of 6"
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CreateContainerConfigError",
            issue="CreateContainerConfigError",
            reason="container {container} cannot build its environment",
            evidence="configmap app-settings not found",
            local_cause="the key {container} reads was removed from its own ConfigMap",
            local_reason="the container never starts and reports a missing key",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Error: configmap "
                   "\"app-settings\" not found")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Init:CreateContainerConfigError",
            issue="Init:CreateContainerConfigError",
            reason="init container {init_container} cannot build its environment",
            evidence="configmap app-settings not found",
            local_cause="the init container references a ConfigMap key that was renamed",
            local_reason="the init container fails before the main container runs",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n    State: Waiting\n"
                   "    Reason: CreateContainerConfigError")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CreateContainerConfigError",
            issue="CreateContainerConfigError",
            reason="container {container} cannot build its environment",
            evidence="configmap app-settings not found",
            local_cause="the StatefulSet was rolled to a revision that mounts a new ConfigMap",
            local_reason="only the newest replicas fail to start",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: configmap \"app-settings\" "
                   "not found")),
            pass_confidence="high",
        ),
    ),
)

_T_SCALED_TO_ZERO = Propagation(
    key="shared-dependency-scaled-to-zero",
    blast_radius="cluster",
    scope_field=None,
    origin="a shared platform service was scaled to zero replicas",
    shared_cause="the shared session service was scaled to zero replicas, so every "
                 "workload that calls it fails",
    shared_reason="the session Deployment declares zero desired replicas and has no pods",
    distractor_cause="an upstream gateway is rate limiting the callers",
    distractor_reason="no sampled log line from any caller carries a rate-limit response",
    rationale="the workload depends on a service that currently has nothing running, "
              "which is true of every caller in the cluster",
    remedy="Scale the session service back up; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe platform/session (Deployment)",
        ("Replicas:  0 desired | 0 updated | 0 total | 0 available\n"
         "Pods:      none\n"
         "Last scale event: 34m ago, 4 replicas to 0"),
    ),
    healthy_origin_content=(
        "Replicas:  4 desired | 4 updated | 4 total | 4 available\n"
        "Pods:      4 Running, 0 restarts\n"
        "Last scale event: none in the last 24h"
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="no healthy upstream for the session dependency",
            local_cause="the workload's retry budget is too small for a slow dependency",
            local_reason="the container gives up after its first attempt",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: no healthy upstream for a dependency "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 6 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="the workload's readiness check was made stricter in the last roll",
            local_reason="the probe fails on a dependency check it did not used to make",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  6x  kubelet  Readiness probe failed: "
                   "dependency session has no endpoints")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times without crashing",
            evidence="the container exits cleanly and is restarted",
            local_cause="the workload exits zero when it finds no work queued",
            local_reason="each restart follows a clean exit rather than a crash",
            read=("describe {ns}/{pod} (Pod)",
                  ("Last State: Terminated, Exit Code: 0, Reason: Completed\n"
                   "Restart Count: {restarts}")),
            pass_confidence="medium",
        ),
    ),
)

_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO)


def trainable_scenarios() -> tuple[Propagation, ...]:
    """The origins training may see. Disjoint from `all_scenarios()` by test."""
    return _TRAINING_SCENARIOS
