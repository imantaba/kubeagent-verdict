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
    # Rendered by BOTH healthy-origin cases -- `shared_origin_decoy` (training)
    # and `shared_origin_decoy_probe` (eval) -- and needed wherever
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
    # The discriminating read, rendered several ways. Each entry is
    # (broken content, healthy content) and entry 0 must equal
    # (origin_read[1], healthy_origin_content). Two call sites reach that pair
    # directly: `_render_shared_origin` takes it as the fallback when a
    # scenario declares no variants, and `cases.multi`'s `healthy_origin`
    # branch renders `healthy_origin_content` on its own, never going through
    # the draw -- so the legacy wording is rendered whatever the variants say,
    # and keeping it as entry 0 is what keeps those sites showing content the
    # model has actually seen. Empty on the eval six: the exam is frozen and
    # must consume the same RNG.
    origin_variants: tuple[tuple[str, str], ...] = ()
    # (broken token, healthy token). A word, not only a number -- the two
    # scenarios that failed at eval were separated by a quantity and the two
    # that passed by a lexical state token. Enforced over the trainable pool
    # only; the eval six are asked, not taught.
    origin_state: tuple[str, str] = ("", "")
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
        "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
         "Pods:      coredns-7d8f9c4b5-2xk4m   1/1  Running  0 restarts\n"
         "           coredns-7d8f9c4b5-qp7rt   1/1  Running  0 restarts\n"
         "Last log:  [INFO] plugin/reload: Running configuration SHA512 unchanged"
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
        "Conditions:\n"
         "  Ready            True    KubeletReady   kubelet is posting ready status\n"
         "  MemoryPressure   False   KubeletHasSufficientMemory\n"
         "  DiskPressure     False   KubeletHasNoDiskPressure\n"
         "Taints:  <none>"
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
        "provisioner: example.com/local-path\n"
         "controller local-path-storage/local-path-provisioner: 1/1 ready, Running\n"
         "PersistentVolumes bound in the last 20m: 7"
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
        "pods reporting an image pull error name no registry host in common, and\n"
         "no two of them fail the same way: manifest unknown, unauthorized,\n"
         "no such host\n"
         "distinct registry hosts in the failing set: one per failing pod"
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
        "Conditions:\n"
         "  DiskPressure   False  KubeletHasNoDiskPressure  kubelet has no disk pressure\n"
         "  Ready          True   KubeletReady\n"
         "Taints:  <none>\n"
         "Allocated resources:\n"
         "  cpu     1200m (30%)\n"
         "  memory  2Gi (41%)"
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
        "podSelector: app=metrics-collector\n"
         "policyTypes: Ingress\n"
         "ingress: allow from namespaceSelector kube-system\n"
         "pods selected: 0 of 6"
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
    origin_state=("expired", "remaining"),
    origin_variants=(
        (("notAfter: expired 2h ago\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 14 across 6 namespaces"),
         ("notAfter: 288 days remaining\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 14 across 6 namespaces")),
        (("verification of the presented chain failed\n"
          "the signing certificate in the cluster-internal-ca bundle expired 41m ago\n"
          "9 workloads present certificates signed by that bundle"),
         ("verification of the presented chain succeeded\n"
          "the signing certificate in the cluster-internal-ca bundle has 112 days remaining\n"
          "9 workloads present certificates signed by that bundle")),
        (("notAfter: expired 6d ago\n"
          "issuer: cluster-internal-ca\n"
          "served to: 23 workloads across 8 namespaces"),
         ("notAfter: 401 days remaining\n"
          "issuer: cluster-internal-ca\n"
          "served to: 23 workloads across 8 namespaces")),
        (("validity: expired\n"
          "bundle: cluster-internal-ca\n"
          "renewal: no successful renewal recorded\n"
          "mounted by: 6 workloads"),
         ("validity: 74 days remaining\n"
          "bundle: cluster-internal-ca\n"
          "renewal: last renewal completed\n"
          "mounted by: 6 workloads")),
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
            healthy_read_content=("classified cause: peer certificate rejected as "
                                  "untrusted (3 of 3 sampled restarts)"),
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
        ("Service route programming: stale\n"
         "last sync 11m ago (peers synced 4s ago)\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kube-proxy pod on this node: 1/1 Running, 0 restarts"),
    ),
    healthy_origin_content=(
        "Service route programming: fresh\n"
        "last sync 3s ago (peers synced 4s ago)\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kube-proxy pod on this node: 1/1 Running, 0 restarts"
    ),
    origin_state=("stale", "fresh"),
    origin_variants=(
        (("Service route programming: stale\n"
          "last sync 11m ago (peers synced 4s ago)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kube-proxy pod on this node: 1/1 Running, 0 restarts"),
         ("Service route programming: fresh\n"
          "last sync 3s ago (peers synced 4s ago)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kube-proxy pod on this node: 1/1 Running, 0 restarts")),
        (("route table on this node: stale\n"
          "no route update applied for 14m while peers are within 5s\n"
          "kube-proxy pod on this node: 1/1 Running"),
         ("route table on this node: fresh\n"
          "last route update applied 2s ago, within 5s of peers\n"
          "kube-proxy pod on this node: 1/1 Running")),
        (("kube-proxy reports its Service route table stale\n"
          "last successful sync: 9m ago\n"
          "peer nodes applied their tables seconds ago"),
         ("kube-proxy reports its Service route table fresh\n"
          "last successful sync: 4s ago\n"
          "peer nodes applied their tables seconds ago")),
        (("Service route sync: stale\n"
          "endpoint changes queued and unapplied: 62\n"
          "kube-proxy has not logged a sync in 12m"),
         ("Service route sync: fresh\n"
          "endpoint changes queued and unapplied: 0\n"
          "kube-proxy logged its last sync 3s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="connection refused dialing the checkout Service address",
            # Worded to CONTRAST with this scenario's shared cause, not to
            # restate it. "the upstream is refusing connections" was both:
            # kube-proxy failing to program Service routes IS pods reaching no
            # Service, so the victim's supposedly-separate cause told the same
            # story as the shared one, and the decoy half lost its teaching
            # point. It also spoke `SHARED_CLAIM_PHRASES`' "upstream" inside a
            # correct separate-reasons answer. This scenario has exactly two
            # victims, so `p.victims[:count]` always draws this one.
            local_cause="the workload's own config still dials a retired Service address",
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
    origin_state=("NotFound", "keys"),
    origin_variants=(
        (("Error from server (NotFound): the ConfigMap app-settings does not exist\n"
          "namespace {ns}: Active\n"
          "pods in {ns} referencing it: 6 of 6"),
         ("Name: app-settings, 7 keys\n"
          "namespace {ns}: Active\n"
          "pods in {ns} referencing it: 6 of 6")),
        (("app-settings: NotFound\n"
          "namespace {ns}: Active\n"
          "workloads in {ns} mounting it: 4 of 4"),
         ("app-settings: present, 5 keys\n"
          "namespace {ns}: Active\n"
          "workloads in {ns} mounting it: 4 of 4")),
        (("the shared app-settings ConfigMap: NotFound\n"
          "last seen in the namespace event log 12m ago\n"
          "pods in {ns} referencing it: 9 of 9"),
         ("the shared app-settings ConfigMap: 11 keys\n"
          "last written 12m ago\n"
          "pods in {ns} referencing it: 9 of 9")),
        (("the ConfigMap every flagged workload mounts resolves NotFound\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "mounted by every workload flagged here"),
         ("the ConfigMap every flagged workload mounts resolves with 6 keys\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "mounted by every workload flagged here")),
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
            healthy_read_content=("Events: Warning  Failed  kubelet  Error: couldn't "
                                  "find key api-timeout in ConfigMap {ns}/checkout-settings"),
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
            healthy_read_content=("Warning  Failed  kubelet  Error: configmap "
                                  "\"{name}-revision-settings\" not found"),
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
    origin_state=("replicas to 0", "Running"),
    origin_variants=(
        (("Replicas:  0 desired | 0 updated | 0 total | 0 available\n"
          "Pods:      none\n"
          "Last scale event: 34m ago, 4 replicas to 0"),
         ("Replicas:  4 desired | 4 updated | 4 total | 4 available\n"
          "Pods:      4 Running, 0 restarts\n"
          "Last scale event: none in the last 24h")),
        (("scale subresource reports a spec replica count of 0\n"
          "the last recorded event took it from 6 replicas to 0\n"
          "no pod belonging to this Deployment is scheduled"),
         ("scale subresource reports a spec replica count of 6\n"
          "the last recorded event predates the retention window\n"
          "6 pods belonging to this Deployment are Running")),
        (("desired replicas: 0, available: 0\n"
          "scale history: 11m ago, 3 replicas to 0\n"
          "no pod has been scheduled for this Deployment since"),
         ("desired replicas: 3, available: 3\n"
          "scale history: unchanged for 9d\n"
          "3 pods Running for this Deployment")),
        (("the session Deployment was scaled from 5 replicas to 0\n"
          "current pods: 0\n"
          "no endpoint is registered for its Service"),
         ("the session Deployment holds 5 replicas\n"
          "current pods: 5 Running\n"
          "5 endpoints are registered for its Service")),
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

_T_IMAGE_PULL_SECRET = Propagation(
    key="image-pull-secret-expired",
    blast_radius="cluster",
    scope_field=None,
    origin="the registry pull secret used cluster-wide has an expired token",
    shared_cause="the cluster-wide image pull secret's registry token expired, so no "
                 "workload can pull its image",
    shared_reason="the shared regcred Secret used by every pull reports its token "
                  "expired eighteen minutes ago",
    distractor_cause="each workload's own imagePullSecrets reference was dropped in "
                      "its last rollout",
    distractor_reason="every failing pod spec still lists the shared regcred secret "
                      "in imagePullSecrets",
    rationale="the workload cannot pull because the cluster-wide pull secret "
              "authorizing every pull has expired, which is true of every image "
              "request right now",
    remedy="Rotate the shared pull secret's registry token; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_related secret shared-regcred (cluster-wide)",
        ("auth token: expired 18m ago\n"
         "registry: the cluster's private image registry\n"
         "workloads referencing this secret: 11 across 5 namespaces"),
    ),
    healthy_origin_content=(
        "auth token: current, 29 days remaining\n"
        "registry: the cluster's private image registry\n"
        "workloads referencing this secret: 11 across 5 namespaces"
    ),
    origin_state=("expired", "current"),
    origin_variants=(
        (("auth token: expired 18m ago\n"
          "registry: the cluster's private image registry\n"
          "workloads referencing this secret: 11 across 5 namespaces"),
         ("auth token: current, 29 days remaining\n"
          "registry: the cluster's private image registry\n"
          "workloads referencing this secret: 11 across 5 namespaces")),
        (("verification of the pull secret against the registry failed\n"
          "the presented token is expired\n"
          "11 workloads authenticate through this secret"),
         ("verification of the pull secret against the registry succeeded\n"
          "the presented token is current\n"
          "11 workloads authenticate through this secret")),
        (("Warning  Failed  11x  kubelet  Failed to pull image: unauthorized: the "
          "registry token has expired"),
         ("Normal  Pulled  11x  kubelet  Successfully pulled image using a current "
          "registry token")),
        (("regcred status: expired\n"
          "last successful pull cluster-wide: 18m before the token lapsed\n"
          "workloads relying on it: 11"),
         ("regcred status: current\n"
          "last successful pull cluster-wide: seconds ago\n"
          "workloads relying on it: 11")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="ErrImagePull", issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to authenticate pulling {image}",
            local_cause="this workload's own image tag no longer exists in the registry",
            local_reason="the pull fails immediately rather than retrying",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  unauthorized: authentication token has "
                   "expired")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  manifest unknown: tag not found"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="ImagePullBackOff", issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the agent's pinned image digest was removed by a registry "
                        "garbage collection",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image {image}: "
                   "unauthorized: the presented pull secret token has expired")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image {image}: "
                "manifest unknown for digest"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job", status="Init:ErrImagePull", issue="Init:ErrImagePull",
            reason="init container {init_container} cannot pull its image",
            evidence="failed to authenticate pulling the init image",
            local_cause="the migration Job's init image reference has a typo",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n    State: Waiting\n"
                   "    Reason: ErrImagePull\n"
                   "  Warning  Failed  kubelet  unauthorized: authentication token "
                   "has expired")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ErrImagePull\n"
                "  Warning  Failed  kubelet  manifest unknown: tag not found"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="Init:ImagePullBackOff",
            issue="Init:ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container {init_container}",
            local_cause="the StatefulSet's init image was retagged to a version that "
                        "was never pushed",
            local_reason="the init container's pull is backed off on every retry",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n    State: Waiting\n"
                   "    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  unauthorized: the shared pull secret "
                   "token has expired")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  manifest unknown: tag not found"),
            pass_confidence="medium",
        ),
    ),
)

_T_SECRET_KEY_RENAMED = Propagation(
    key="shared-secret-key-renamed",
    blast_radius="cluster",
    scope_field=None,
    origin="the shared Secret every workload reads a key from was renamed by a "
           "platform change",
    shared_cause="the shared platform Secret's key was renamed cluster-wide, so "
                 "every workload that reads it fails to start",
    shared_reason="every workload referencing the shared Secret's old key name "
                  "reports the same missing-key error",
    distractor_cause="the workloads' RBAC permission to read Secrets was revoked in "
                      "the last policy sync",
    distractor_reason="each pod's service account can still describe the Secret "
                      "object itself, only the key it wants is gone",
    rationale="the workload cannot start because the key it reads from the shared "
              "Secret no longer exists under that name, which is true of every "
              "workload reading this Secret right now",
    remedy="Restore the shared Secret's original key name (or add both keys during "
           "the rename); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related secret platform/shared-credentials (cluster-wide)",
        ("lookup result: missing\n"
         "requested key: api-token\n"
         "keys defined on the secret: db-password, tls-cert, svc-token\n"
         "workloads referencing this secret: 9 across 4 namespaces"),
    ),
    healthy_origin_content=(
        "lookup result: intact\n"
        "requested key: api-token\n"
        "keys defined on the secret: api-token, db-password, tls-cert\n"
        "workloads referencing this secret: 9 across 4 namespaces"
    ),
    origin_state=("missing", "intact"),
    origin_variants=(
        (("lookup result: missing\n"
          "requested key: api-token\n"
          "keys defined on the secret: db-password, tls-cert, svc-token\n"
          "workloads referencing this secret: 9 across 4 namespaces"),
         ("lookup result: intact\n"
          "requested key: api-token\n"
          "keys defined on the secret: api-token, db-password, tls-cert\n"
          "workloads referencing this secret: 9 across 4 namespaces")),
        (("verification that the shared Secret carries the expected key failed\n"
          "the key api-token is missing from the Secret's data\n"
          "9 workloads request that key"),
         ("verification that the shared Secret carries the expected key succeeded\n"
          "the key api-token is intact in the Secret's data\n"
          "9 workloads request that key")),
        (("Warning  Failed  9x  kubelet  couldn't find key api-token in Secret "
          "platform/shared-credentials: missing"),
         ("Normal  Synced  9x  kubelet  key api-token in Secret "
          "platform/shared-credentials: intact")),
        (("shared-credentials data keys: db-password, tls-cert, svc-token\n"
          "api-token: missing since the last platform sync\n"
          "9 workloads mount this secret"),
         ("shared-credentials data keys: api-token, db-password, tls-cert\n"
          "api-token: intact, unchanged since creation\n"
          "9 workloads mount this secret")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CreateContainerConfigError",
            issue="CreateContainerConfigError",
            reason="container {container} cannot build its environment",
            evidence="couldn't find key api-token in Secret shared-credentials",
            local_cause="this workload's own manifest requests a key from its own "
                        "Secret that it renamed in the last deploy",
            local_reason="the container never starts and reports a missing key",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Error: couldn't find key "
                   "api-token in Secret shared-credentials: missing")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Error: couldn't find key "
                "legacy-token in Secret {ns}/app-secrets"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="panic: required credential api-token not found in environment",
            local_cause="this replica's own manifest never added api-token to its "
                        "envFrom list",
            local_reason="the container panics immediately after reading its "
                        "environment",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: missing required credential api-token "
                   "(3 of 3 sampled restarts)")),
            healthy_read_content=(
                "classified cause: environment variable api-token never declared "
                "in this replica's own manifest (3 of 3 sampled restarts)"),
            pass_confidence="medium",
        ),
    ),
)

_T_AUTOSCALER_CAPACITY = Propagation(
    key="cluster-autoscaler-at-capacity",
    blast_radius="cluster",
    scope_field=None,
    origin="the cluster autoscaler cannot add a node because its node group is "
           "already at maximum size",
    shared_cause="the cluster autoscaler cannot add a node because the node group "
                 "is already at its configured maximum, so pending pods stay "
                 "unscheduled",
    shared_reason="the autoscaler's own status reports the node group at max size "
                  "with a scale-up event refused nine minutes ago",
    distractor_cause="a NoSchedule taint left behind by last night's maintenance "
                     "window still covers the whole node pool",
    distractor_reason="every node's taint list is unchanged from what it was "
                      "before the maintenance window opened",
    rationale="the workload cannot be scheduled because the autoscaler has nowhere "
              "left to grow the cluster, which is true of every pending pod "
              "cluster-wide right now",
    remedy="Raise the node group's maximum size (or free capacity elsewhere); the "
           "flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related deployment kube-system/cluster-autoscaler (cluster-wide)",
        ("scale-up status: blocked\n"
         "node group at 10 of 10 nodes (max size reached)\n"
         "last scale-up attempt: refused 9m ago\n"
         "pending pods cluster-wide: 7"),
    ),
    healthy_origin_content=(
        "scale-up status: eligible\n"
        "node group at 10 of 16 nodes\n"
        "last scale-up attempt: succeeded 9m ago\n"
        "pending pods cluster-wide: 2"
    ),
    origin_state=("blocked", "eligible"),
    origin_variants=(
        (("scale-up status: blocked\n"
          "node group at 10 of 10 nodes (max size reached)\n"
          "last scale-up attempt: refused 9m ago\n"
          "pending pods cluster-wide: 7"),
         ("scale-up status: eligible\n"
          "node group at 10 of 16 nodes\n"
          "last scale-up attempt: succeeded 9m ago\n"
          "pending pods cluster-wide: 2")),
        (("requesting one more node from the node group was refused\n"
          "the node group's scale-up path is blocked at its configured maximum\n"
          "7 pods are pending on this node group's capacity"),
         ("requesting one more node from the node group succeeded\n"
          "the node group's scale-up path is eligible below its raised maximum\n"
          "2 pods are pending for reasons another node would not fix")),
        (("Warning  NotTriggerScaleUp  9x  cluster-autoscaler  scale-up blocked: "
          "max node group size reached"),
         ("Normal  TriggeredScaleUp  cluster-autoscaler  scale-up eligible: node "
          "group provisioned a new node")),
        (("autoscaler status: blocked\n"
          "reason: MaxNodeGroupSizeReached\n"
          "nodes: 10/10\n"
          "unschedulable pods tracked: 7"),
         ("autoscaler status: eligible\n"
          "reason: none\n"
          "nodes: 10/16\n"
          "unschedulable pods tracked: 2")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Pending", issue="Unschedulable",
            reason="0/10 nodes are available",
            evidence="10 node(s) had insufficient memory",
            local_cause="this Deployment's own memory request was raised in its "
                        "last rollout above what a single node in this pool "
                        "can allocate",
            local_reason="the previous ReplicaSet is still Running on these nodes "
                        "with the smaller request",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/10 nodes are "
                   "available: 10 Insufficient memory.")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="0/10 nodes are available",
            evidence="pod triggered a scale-up request that was refused",
            local_cause="the Job's own resource request was rounded up by a "
                        "defaulting webhook to more than any node provides",
            local_reason="the request, not the cluster, is why no node fits",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/10 nodes are "
                   "available: 10 Insufficient cpu.\n"
                   "Warning  NotTriggerScaleUp  cluster-autoscaler  scale-up "
                   "blocked: max node group size reached")),
            healthy_read_content=(
                "Warning  FailedScheduling  default-scheduler  0/10 nodes are "
                "available: 10 Insufficient cpu.\n"
                "Warning  NotTriggerScaleUp  cluster-autoscaler  no scale-up "
                "would help: pod requests exceed the largest node type"),
            pass_confidence="medium",
        ),
    ),
)

_T_SIDECAR_INJECTOR = Propagation(
    key="sidecar-injector-broken",
    blast_radius="cluster",
    scope_field=None,
    origin="a mutating webhook injects a sidecar image into every pod it admits, "
           "and that image cannot start",
    shared_cause="the sidecar injector webhook is injecting a broken sidecar image "
                 "into every pod it mutates, so any pod admitted with that sidecar "
                 "fails to start",
    shared_reason="the injector's own webhook configuration still points at a "
                  "sidecar image tag that was retracted from the registry two "
                  "hours ago",
    distractor_cause="the injected sidecar's own configuration file has a syntax "
                      "error introduced in the last mesh upgrade",
    distractor_reason="the very same configuration parses successfully on the "
                      "injector's own health check, and each pod's container "
                      "reports a distinct startup failure",
    rationale="the workload cannot start because the sidecar injected into every "
              "pod it mutates cannot run, which is true of every pod this webhook "
              "touches right now",
    remedy="Point the sidecar injector webhook at a working image tag; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_read=(
        "describe mutatingwebhookconfiguration mesh-sidecar-injector",
        ("image status: retracted\n"
         "injected sidecar image: proxy:v1.19.2\n"
         "pods mutated by this webhook in the last hour: 8"),
    ),
    healthy_origin_content=(
        "image status: validated\n"
        "injected sidecar image: proxy:v1.19.1\n"
        "pods mutated by this webhook in the last hour: 8"
    ),
    origin_state=("retracted", "validated"),
    origin_variants=(
        (("image status: retracted\n"
          "injected sidecar image: proxy:v1.19.2\n"
          "pods mutated by this webhook in the last hour: 8"),
         ("image status: validated\n"
          "injected sidecar image: proxy:v1.19.1\n"
          "pods mutated by this webhook in the last hour: 8")),
        (("verification of the injected sidecar image against the registry failed\n"
          "the image tag was retracted after publishing\n"
          "8 pods were mutated with this sidecar in the last hour"),
         ("verification of the injected sidecar image against the registry "
          "succeeded\n"
          "the image tag is validated and current\n"
          "8 pods were mutated with this sidecar in the last hour")),
        (("Warning  FailedCreate  8x  mesh-sidecar-injector  webhook injected a "
          "retracted sidecar image into the pod spec"),
         ("Normal  Injected  8x  mesh-sidecar-injector  webhook injected a "
          "validated sidecar image into the pod spec")),
        (("sidecar injector status: retracted image pinned\n"
          "last successful injection with a working image: nine days ago\n"
          "pods mutated since: 8, all failing"),
         ("sidecar injector status: validated image pinned\n"
          "last successful injection with a working image: seconds ago\n"
          "pods mutated since: 8, all healthy")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="exec format error: injected sidecar binary is not compatible "
                      "with this image tag",
            local_cause="this pod's own image predates the sidecar's expected base "
                        "OS and the two are incompatible",
            local_reason="the init container fails on every attempt, immediately",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: retracted sidecar image failed to execute "
                   "(3 of 3 sampled restarts)")),
            healthy_read_content=(
                "classified cause: incompatible base OS between the pod's image "
                "and its sidecar (3 of 3 sampled restarts)"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="dial unix /var/run/sidecar.sock: connect: connection refused",
            local_cause="this replica's own service mesh configuration was applied "
                        "before the sidecar was ready",
            local_reason="the container exits waiting on a local sidecar socket "
                        "that never appears",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: local sidecar socket unavailable, image never "
                   "started listening (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 10 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="this workload's own readiness probe was pointed at the "
                        "wrong port during its last rollout",
            local_reason="every probe attempt is refused rather than reaching the "
                        "sidecar",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  10x  kubelet  Readiness probe failed: "
                   "connection refused: the injected sidecar image (retracted) "
                   "never opened its port")),
            healthy_read_content=(
                "Warning  Unhealthy  10x  kubelet  Readiness probe failed: "
                "connection refused: probe targets port 9090 but the container "
                "listens on 8080"),
            pass_confidence="high",
        ),
    ),
)

_T_BASE_IMAGE_TAG = Propagation(
    key="shared-base-image-tag-moved",
    blast_radius="cluster",
    scope_field=None,
    origin="a shared base image tag was repointed to a broken build",
    shared_cause="the shared base image tag was repointed to a broken build, so "
                 "every image built from it fails to start",
    shared_reason="the platform/runtime-base:stable tag was repointed 22m ago and "
                  "its own smoke test is failing",
    distractor_cause="the container registry is intermittently corrupting layers "
                     "during a bulk rebuild",
    distractor_reason="every pull for these images completes and matches its "
                      "expected digest, and the same layers verify against the "
                      "registry's own manifest on every node that holds them",
    rationale="the workload's failure is what happens when the shared base image "
              "tag it was built from ships a broken build, which is true of every "
              "image tracking that tag right now",
    remedy="Repoint the shared base image tag back to a known-good build; the "
           "flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related image-tag platform/runtime-base:stable (cluster-wide)",
        ("build status: failing\n"
         "digest: repointed 22m ago to a build that fails its own smoke test\n"
         "images built FROM this tag: 13 across 7 namespaces"),
    ),
    healthy_origin_content=(
        "build status: passing\n"
        "digest: unchanged for 46 days, smoke test passing\n"
        "images built FROM this tag: 13 across 7 namespaces"
    ),
    origin_state=("failing", "passing"),
    origin_variants=(
        (("build status: failing\n"
          "digest: repointed 22m ago to a build that fails its own smoke test\n"
          "images built FROM this tag: 13 across 7 namespaces"),
         ("build status: passing\n"
          "digest: unchanged for 46 days, smoke test passing\n"
          "images built FROM this tag: 13 across 7 namespaces")),
        (("verification of the shared base image tag's smoke test is failing\n"
          "the platform/runtime-base:stable tag was repointed to a new build 22m "
          "ago\n"
          "13 images across 7 namespaces are built FROM this tag"),
         ("verification of the shared base image tag's smoke test is passing\n"
          "the platform/runtime-base:stable tag has been unchanged for 46 days\n"
          "13 images across 7 namespaces are built FROM this tag")),
        (("Warning  BuildFailed  9x  image-scanner  smoke test failing for "
          "platform/runtime-base:stable"),
         ("Normal  BuildPassed  9x  image-scanner  smoke test passing for "
          "platform/runtime-base:stable")),
        (("runtime-base tag status: failing\n"
          "last known-good build: 46 days ago before the repoint\n"
          "fleet images tracking this tag: 13"),
         ("runtime-base tag status: passing\n"
          "last known-good build: seconds ago\n"
          "fleet images tracking this tag: 13")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff", issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="error while loading shared libraries: libssl.so.3: cannot "
                      "open shared object file",
            local_cause="this workload's own image pinned a libssl version its "
                        "base image does not ship",
            local_reason="the container exits before it can bind its listening port",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: missing shared library libssl.so.3 (3 of 3 "
                   "sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task for container {container}",
            local_cause="this workload's own image build script never copied the "
                        "server binary into the final image",
            local_reason="the runtime cannot find an executable to launch",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Error: failed to create "
                   "containerd task: OCI runtime create failed: exec: "
                   "\"/app/server\": stat /app/server: no such file or directory")),
            pass_confidence="medium",
        ),
    ),
)

_T_PVC_MULTI_ATTACH = Propagation(
    key="shared-pvc-multi-attach",
    blast_radius="cluster",
    scope_field=None,
    origin="a ReadWriteOnce PVC's attachment will not release, wedging the "
           "cluster's attach/detach queue",
    shared_cause="one ReadWriteOnce PVC's VolumeAttachment will not release, "
                 "wedging the cluster's attach/detach queue so every other pod's "
                 "volume attach or mount stalls behind it",
    shared_reason="the attach/detach queue has been wedged for 26 minutes behind "
                  "one VolumeAttachment that never released, and every operation "
                  "behind it is blocked",
    distractor_cause="the storage backend's control plane is unreachable",
    distractor_reason="the storage backend's own API answers every other query "
                      "the CSI driver sends it during this window",
    rationale="the workload's volume operation is stuck behind the one "
              "VolumeAttachment wedging the shared queue, which is true of every "
              "pending attach or mount cluster-wide right now",
    remedy="Force-clear the stuck VolumeAttachment; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related volumeattachment (cluster-wide)",
        ("attach/detach queue: wedged\n"
         "the oldest unresolved VolumeAttachment has been retrying release for 26m\n"
         "operations blocked behind it: 11 across 9 namespaces"),
    ),
    healthy_origin_content=(
        "attach/detach queue: flowing\n"
        "the oldest unresolved VolumeAttachment resolved within its normal window\n"
        "operations blocked behind it: 0 across 9 namespaces"
    ),
    origin_state=("wedged", "flowing"),
    origin_variants=(
        (("attach/detach queue: wedged\n"
          "the oldest unresolved VolumeAttachment has been retrying release for "
          "26m\n"
          "operations blocked behind it: 11 across 9 namespaces"),
         ("attach/detach queue: flowing\n"
          "the oldest unresolved VolumeAttachment resolved within its normal "
          "window\n"
          "operations blocked behind it: 0 across 9 namespaces")),
        (("the attach/detach controller's queue is wedged\n"
          "the oldest unresolved VolumeAttachment has retried release for 31m "
          "without success\n"
          "9 other volume operations are stuck behind it"),
         ("the attach/detach controller's queue is flowing\n"
          "the oldest unresolved VolumeAttachment resolved in under a second\n"
          "0 other volume operations are stuck behind it")),
        (("Warning  VolumeAttachmentStuck  attachdetach-controller  attach/detach "
          "queue wedged behind one unresolved VolumeAttachment"),
         ("Normal  VolumeAttachmentResolved  attachdetach-controller  "
          "attach/detach queue flowing, no unresolved VolumeAttachment")),
        (("queue status: wedged\n"
          "detach retries on the oldest item: 14, all failed\n"
          "volume operations waiting cluster-wide: 11"),
         ("queue status: flowing\n"
          "detach retries on the oldest item: 0 outstanding\n"
          "volume operations waiting cluster-wide: 0")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="VolumeAttachError",
            reason="the pod's volume could not be attached",
            evidence="Multi-Attach error for volume {pvc}",
            local_cause="this workload's own StatefulSet rescheduled its pod to a "
                        "new node before the previous pod's attachment released",
            local_reason="the FailedAttachVolume event names Multi-Attach for this "
                        "pod's own PVC specifically",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  8x  attachdetach-controller  "
                   "Multi-Attach error for volume {pvc} Volume is already "
                   "exclusively attached to one node and can't be attached to "
                   "another")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="VolumeMountError",
            reason="a volume the pod needs could not be mounted",
            evidence="unmounted volumes=[data] on container {container}",
            local_cause="this workload's own PVC has a failing underlying disk "
                        "that predates this incident",
            local_reason="the mount times out while the PVC itself already "
                        "describes as Bound",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedMount  6x  kubelet  Unable to attach or mount "
                   "volumes: unmounted volumes=[data], timed out waiting for the "
                   "condition")),
            pass_confidence="medium",
        ),
    ),
)

_T_CNI_IP_POOL = Propagation(
    key="cni-ip-pool-exhausted",
    blast_radius="cluster",
    scope_field=None,
    origin="the CNI's shared address pool is exhausted",
    shared_cause="the CNI's shared address pool is exhausted (0 of 512 addresses "
                 "free), so no new pod cluster-wide can be assigned an address",
    shared_reason="the pool's own accounting reports 0 of 512 addresses free, "
                  "unchanged for six hours despite pods churning",
    distractor_cause="the container runtime on these nodes is refusing to create "
                     "new sandboxes",
    distractor_reason="the runtime's own health check passes on these nodes, and "
                      "every sandbox failure names the CNI plugin rather than "
                      "containerd",
    rationale="the workload cannot get a pod address or be scheduled with one "
              "because the shared address pool has nothing left to give it, which "
              "is true of every new pod cluster-wide right now",
    remedy="Free or expand the CNI's shared address pool; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_related ipamconfig cluster-pod-network (cluster-wide)",
        ("pool status: depleted\n"
         "free addresses: 0 of 512\n"
         "pods waiting on an address: 9 across 6 namespaces"),
    ),
    healthy_origin_content=(
        "pool status: available\n"
        "free addresses: 340 of 512\n"
        "pods waiting on an address: 0 across 6 namespaces"
    ),
    origin_state=("depleted", "available"),
    origin_variants=(
        (("pool status: depleted\n"
          "free addresses: 0 of 512\n"
          "pods waiting on an address: 9 across 6 namespaces"),
         ("pool status: available\n"
          "free addresses: 340 of 512\n"
          "pods waiting on an address: 0 across 6 namespaces")),
        (("verification of the shared pod-network address pool found it depleted\n"
          "0 of 512 addresses remain free\n"
          "9 pods are waiting on the pool to free an address"),
         ("verification of the shared pod-network address pool found it available\n"
          "188 of 512 addresses remain free\n"
          "0 pods are waiting on the pool to free an address")),
        (("Warning  IPAMPoolExhausted  9x  ipam-controller  pod-network address "
          "pool depleted: 0 of 512 free"),
         ("Normal  IPAMPoolHealthy  ipam-controller  pod-network address pool "
          "available: 340 of 512 free")),
        (("address pool: depleted\n"
          "last successful allocation: 6h ago\n"
          "allocation requests queued: 9"),
         ("address pool: available\n"
          "last successful allocation: seconds ago\n"
          "allocation requests queued: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="the pod's network sandbox could not be created",
            evidence="failed to create pod sandbox for container {container}",
            local_cause="this workload's own CNI annotation requests a static IP "
                        "address that is already allocated to another pod",
            local_reason="the sandbox failure names an address that is "
                        "unavailable specifically for this workload's static "
                        "request",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedCreatePodSandBox  kubelet  Failed to "
                   "create pod sandbox: plugin type=\"cni\" failed (add): no "
                   "available IP addresses in the pool")),
            healthy_read_content=(
                "Events: Warning  FailedCreatePodSandBox  kubelet  Failed to "
                "create pod sandbox: plugin type=\"cni\" failed (add): requested "
                "static IP address already allocated"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="0/12 nodes are available",
            evidence="0/12 nodes accepted the pod",
            local_cause="the Job's own pod spec requests a secondary network "
                        "interface that most other workloads do not",
            local_reason="the FailedScheduling message names insufficient network "
                        "addresses, and this workload's own spec is the one asking "
                        "for extra interfaces per pod",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/12 nodes are "
                   "available: 12 Insufficient pod-network addresses.")),
            healthy_read_content=(
                "Warning  FailedScheduling  default-scheduler  0/12 nodes are "
                "available: 12 node(s) had no free secondary network interface "
                "slot for this pod."),
            pass_confidence="medium",
        ),
    ),
)

_T_CSI_NODE_DRIVER = Propagation(
    key="csi-node-driver-crashed",
    blast_radius="node",
    scope_field="node",
    origin="the CSI node driver's DaemonSet pod on {node} crashed and has not "
           "recovered",
    shared_cause="the CSI node driver's pod on node {node} crashed, so no pod "
                 "scheduled there can mount or use a volume",
    shared_reason="the CSI node driver's DaemonSet pod on {node} shows crashed "
                  "with 4 failed restarts, while its peers on other nodes are "
                  "current",
    distractor_cause="the whole node {node} is unhealthy and about to be replaced",
    distractor_reason="the node's own Ready condition is True, and every other "
                      "pod scheduled on {node} is running normally",
    rationale="the workload's volume operation fails because the CSI node driver "
              "that would carry it out is not running on {node}, which is true of "
              "everything scheduled there right now",
    remedy="Restart or recover the CSI node driver pod on {node}; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (CSI status)",
        ("CSI node driver: crashed\n"
         "last restart 9m ago (peers on other nodes are current)\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "CSI node driver pod on this node: 0/1 CrashLoopBackOff, 4 restarts"),
    ),
    healthy_origin_content=(
        "CSI node driver: healthy\n"
        "last restart: none in the last 24h (peers on other nodes are current)\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "CSI node driver pod on this node: 1/1 Running, 0 restarts"
    ),
    origin_state=("crashed", "healthy"),
    origin_variants=(
        (("CSI node driver: crashed\n"
          "last restart 9m ago (peers on other nodes are current)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "CSI node driver pod on this node: 0/1 CrashLoopBackOff, 4 restarts"),
         ("CSI node driver: healthy\n"
          "last restart: none in the last 24h (peers on other nodes are current)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "CSI node driver pod on this node: 1/1 Running, 0 restarts")),
        (("verification of the CSI node driver on this node found it crashed\n"
          "the driver pod has failed to stay up for 9m across 4 restart attempts\n"
          "peer nodes' CSI drivers are current"),
         ("verification of the CSI node driver on this node found it healthy\n"
          "the driver pod has been steady for over a day\n"
          "peer nodes' CSI drivers are current")),
        (("Warning  BackOff  4x  kubelet  Back-off restarting failed container "
          "csi-node-driver (crashed)"),
         ("Normal  Started  kubelet  Started container csi-node-driver (healthy)")),
        (("CSI node driver status: crashed\n"
          "restart count: 4, none successful\n"
          "last known-good state: 9m ago"),
         ("CSI node driver status: healthy\n"
          "restart count: 0\n"
          "last known-good state: current")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="VolumeMountError",
            reason="a volume the pod needs could not be mounted",
            evidence="unmounted volumes=[data] on container {container}",
            local_cause="this workload's own PVC is stuck Terminating from a "
                        "delete that never finished",
            local_reason="the mount times out while this specific PVC's "
                        "finalizer never clears",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedMount  6x  kubelet  Unable to attach or mount "
                   "volumes: unmounted volumes=[data], timed out waiting for the "
                   "condition")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="open /data/lockfile: no such file or directory (volume not "
                      "yet mounted when the container started)",
            local_cause="this workload's own container starts before its volume "
                        "mount is verified ready",
            local_reason="the container always exits on its first read from the "
                        "unmounted path",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: read from an unmounted data path failed (3 "
                   "of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
    ),
)


_T_NODE_PID_PRESSURE = Propagation(
    key="node-pid-pressure",
    blast_radius="node",
    scope_field="node",
    origin="the node hit its kernel PID limit and can no longer fork new processes",
    shared_cause="node {node} is at its kernel PID limit, so no new process can be "
                 "forked for any pod scheduled there",
    shared_reason="{node} reports 32768 of 32768 PIDs in use and every fork on it now "
                  "fails, while its peers sit under half that count",
    distractor_cause="the node's CPU is fully saturated by another workload, starving "
                     "these processes",
    distractor_reason="the node's own CPU utilization is unremarkable, and no other "
                      "workload is consuming an unusual share of it",
    rationale="the workload cannot fork a new process because {node} itself has no "
              "PIDs left to give it, which is true of everything scheduled there right now",
    remedy="Recover the PID pressure on {node} (kill the offending process or raise "
           "pid_max); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (process table)",
        ("Process table: exhausted\n"
         "PIDs in use: 32768 of 32768\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kubelet log: fork() failing across pods scheduled here"),
    ),
    healthy_origin_content=(
        "Process table: available\n"
        "PIDs in use: 4102 of 32768\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kubelet log: fork() succeeding normally"
    ),
    origin_state=("exhausted", "available"),
    origin_variants=(
        (("Process table: exhausted\n"
          "PIDs in use: 32768 of 32768\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: fork() failing across pods scheduled here"),
         ("Process table: available\n"
          "PIDs in use: 4102 of 32768\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: fork() succeeding normally")),
        (("kubelet reports the node's process table exhausted\n"
          "fork attempts across the node have failed for 6m\n"
          "peer nodes show plenty of headroom"),
         ("kubelet reports the node's process table available\n"
          "no fork attempts have failed in the last 24h\n"
          "peer nodes show the same headroom")),
        (("Warning  SystemOOM  kubelet  Process table exhausted: fork/exec failing "
          "node-wide"),
         ("Normal  NodeReady  kubelet  Process table available: fork/exec succeeding "
          "node-wide")),
        (("PID table status: exhausted\n"
          "remaining PID budget: 0\n"
          "kubelet has logged fork failures for 9m"),
         ("PID table status: available\n"
          "remaining PID budget: 27000\n"
          "kubelet has logged no fork failures in the last hour")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: unable to start container "
                     "process: resource temporarily unavailable",
            local_cause="this pod's own PID cgroup was already exhausted by the other "
                        "containers in the same pod before this one was created",
            local_reason="the pod's own cgroup accounting already shows its PID "
                        "ceiling reached by its sidecar containers alone",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                   "create containerd task: unable to start container process: "
                   "resource temporarily unavailable")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                  "Running again between attempts",
            evidence="last state terminated with exit code 1",
            log_cause="fork retry failed: resource temporarily unavailable",
            local_cause="this workload's own batch routine leaks subprocesses until "
                        "it hits its own container's process ceiling",
            local_reason="the container's own process count climbs to its configured "
                        "ceiling right before each crash",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: fork of a new subprocess failed, resource "
                   "temporarily unavailable (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
    ),
)

_T_NODE_RUNTIME_RESTARTING = Propagation(
    key="node-runtime-restarting",
    blast_radius="node",
    scope_field="node",
    origin="the container runtime on the node is restarting under the workloads it "
           "hosts",
    shared_cause="the container runtime on node {node} keeps restarting, so every "
                 "container it hosts loses its connection to it mid-operation",
    shared_reason="{node}'s container runtime has restarted 5 times in the last ten "
                  "minutes while its peers' runtimes have stayed up the whole time",
    distractor_cause="a recent application rollout added a slow dependency call to "
                     "the request path",
    distractor_reason="neither workload's own image or config changed in the last "
                      "rollout window, so nothing in their own request path is new",
    rationale="the workload cannot keep a stable connection to the container runtime "
              "because {node}'s own runtime keeps restarting underneath it, which is "
              "true of everything scheduled there right now",
    remedy="Stabilize or restart the container runtime service on {node}; the "
           "flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (container runtime)",
        ("Container runtime: restarting\n"
         "containerd restarts in the last 10m: 5\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kubelet log: connection to the container runtime service was lost, "
         "reconnecting"),
    ),
    healthy_origin_content=(
        "Container runtime: stable\n"
        "containerd restarts in the last 24h: 0\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kubelet log: connection to the container runtime service is steady"
    ),
    origin_state=("restarting", "stable"),
    origin_variants=(
        (("Container runtime: restarting\n"
          "containerd restarts in the last 10m: 5\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: connection to the container runtime service was lost, "
          "reconnecting"),
         ("Container runtime: stable\n"
          "containerd restarts in the last 24h: 0\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: connection to the container runtime service is steady")),
        (("the container runtime on this node is restarting\n"
          "containerd has crashed and been relaunched 5 times in 10m\n"
          "kubelet reports itself Ready throughout"),
         ("the container runtime on this node is stable\n"
          "containerd has not crashed in the last 24h\n"
          "kubelet reports itself Ready throughout")),
        (("Warning  ContainerRuntimeRestarting  kubelet  containerd health check "
          "failed, restarting the runtime (5th time in 10m)"),
         ("Normal  ContainerRuntimeStable  kubelet  containerd health check passing, "
          "runtime stable")),
        (("containerd status: restarting\n"
          "last crash: 40s ago\n"
          "uptime since last crash: under a minute"),
         ("containerd status: stable\n"
          "last crash: none recorded\n"
          "uptime since last crash: over a week")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                  "Running again between attempts",
            evidence="last state terminated with exit code 137",
            log_cause="an in-container exec call never returned before the container "
                      "was torn down",
            local_cause="this workload's own exec-based liveness hook occasionally "
                        "hangs against a subprocess it launches",
            local_reason="the previous run's log shows the exec hook itself still "
                        "blocked at the moment the container was killed",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: liveness exec hook blocked past its timeout "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 10 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="the agent's own readiness probe script depends on a local "
                        "cache warm-up that has not finished",
            local_reason="the probe only fails in the first several minutes after "
                        "each restart of this pod, matching a cold cache",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  10x  kubelet  Readiness probe failed: exec "
                   "probe error: runtime did not respond within the exec timeout")),
            healthy_read_content=(
                "Warning  Unhealthy  10x  kubelet  Readiness probe failed: exec "
                "probe error: command exited 1 while the local cache was still "
                "warming"),
            pass_confidence="medium",
        ),
    ),
)

_T_NODE_CLOCK_SKEW = Propagation(
    key="node-clock-skew",
    blast_radius="node",
    scope_field="node",
    origin="the node's clock has drifted far enough off that certificate and token "
           "validation fails there",
    shared_cause="node {node}'s system clock has drifted out of tolerance, so every "
                 "certificate and token it checks fails validation",
    shared_reason="{node}'s clock reports 6m42s of skew against the cluster's time "
                  "source, past the one-minute tolerance every validator enforces, "
                  "while its peers show no measurable skew",
    distractor_cause="the workloads' bound service account tokens simply expired and "
                     "were never refreshed",
    distractor_reason="each token's own issued and expiry timestamps are still "
                      "comfortably within their validity window",
    rationale="the workload's own certificate check fails because {node}'s clock "
              "disagrees with everyone else's about what time it is, which is true "
              "of everything validated there right now",
    remedy="Correct the system clock on {node} (restart or resync its time "
           "service); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (system clock)",
        ("System clock: skewed\n"
         "offset from cluster time source: 6m42s ahead\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kubelet log: certificate and token validation are failing node-wide"),
    ),
    healthy_origin_content=(
        "System clock: synced\n"
        "offset from cluster time source: under 50ms\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kubelet log: certificate and token validation are passing normally"
    ),
    origin_state=("skewed", "synced"),
    origin_variants=(
        (("System clock: skewed\n"
          "offset from cluster time source: 6m42s ahead\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: certificate and token validation are failing node-wide"),
         ("System clock: synced\n"
          "offset from cluster time source: under 50ms\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: certificate and token validation are passing normally")),
        (("the node's system clock is skewed against the cluster\n"
          "it reads 6m42s ahead of every peer's clock\n"
          "kubelet itself still posts Ready"),
         ("the node's system clock is synced with the cluster\n"
          "it reads within 50ms of every peer's clock\n"
          "kubelet itself still posts Ready")),
        (("Warning  ClockSkewDetected  kubelet  system clock is skewed by 6m42s "
          "from the cluster's time source"),
         ("Normal  ClockSkewCleared  kubelet  system clock is synced with the "
          "cluster's time source")),
        (("time sync status: skewed\n"
          "drift measured: 402s\n"
          "last successful sync: none in the current session"),
         ("time sync status: synced\n"
          "drift measured: under 1s\n"
          "last successful sync: 4s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="x509: certificate has expired or is not yet valid",
            local_cause="this workload's own client certificate genuinely expired "
                        "and was never renewed",
            local_reason="the certificate's own notAfter timestamp had already "
                        "passed before this restart began",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: x509 certificate validity check failed (3 of 3 "
                   "sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 9 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="this replica's own mounted certificate bundle is a stale "
                        "copy from before the last routine rotation",
            local_reason="the mounted bundle's own serial number does not match the "
                        "one currently issued",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  9x  kubelet  Readiness probe failed: x509: "
                   "certificate has expired or is not yet valid")),
            pass_confidence="medium",
        ),
    ),
)

_T_NODE_CONNTRACK_FULL = Propagation(
    key="node-conntrack-full",
    blast_radius="node",
    scope_field="node",
    origin="the node's conntrack table is full, so it drops new connections",
    shared_cause="node {node}'s conntrack table is full, so any new connection "
                 "opened from a pod scheduled there is dropped",
    shared_reason="new connections through {node}'s netfilter path are being refused "
                  "rather than tracked, and the drops are logged there continuously "
                  "while no other node logs any",
    distractor_cause="the Services these workloads call are throttling requests "
                     "under load",
    distractor_reason="each called Service reports normal request latency and no "
                      "throttling in its own metrics",
    rationale="the workload cannot open a new connection because {node}'s conntrack "
              "table has no room for one, which is true of everything scheduled "
              "there right now",
    remedy="Clear or expand the conntrack table on {node} (raise nf_conntrack_max "
           "or clear stale entries); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (conntrack)",
        ("Conntrack table: full\n"
         "entries in use: 262144 of 262144\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kubelet log: new connections are being dropped node-wide"),
    ),
    healthy_origin_content=(
        "Conntrack table: clear\n"
        "entries in use: 8192 of 262144\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kubelet log: new connections are succeeding normally"
    ),
    origin_state=("full", "clear"),
    origin_variants=(
        (("Conntrack table: full\n"
          "entries in use: 262144 of 262144\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: new connections are being dropped node-wide"),
         ("Conntrack table: clear\n"
          "entries in use: 8192 of 262144\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kubelet log: new connections are succeeding normally")),
        (("this node's conntrack table is full\n"
          "new connection attempts here are being refused at the netfilter layer\n"
          "peer nodes' tables are far from their limit"),
         ("this node's conntrack table is clear\n"
          "new connection attempts here are succeeding at the netfilter layer\n"
          "peer nodes' tables show the same headroom")),
        (("Warning  ConntrackTableFull  kubelet  nf_conntrack: table full, dropping "
          "packet"),
         ("Normal  ConntrackTableClear  kubelet  nf_conntrack: table clear, "
          "accepting packets")),
        (("conntrack status: full\n"
          "free entries: 0\n"
          "insertion failures logged in the last 5m: 1400"),
         ("conntrack status: clear\n"
          "free entries: 253952\n"
          "insertion failures logged in the last 5m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 11 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container {container}",
            local_cause="this replica's own readiness probe timeout is shorter than "
                        "the dependency it checks needs under any load",
            local_reason="the probe's own timeout window is tighter than the "
                        "dependency's typical response time",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  11x  kubelet  Readiness probe failed: dial "
                  "tcp: i/o timeout"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="failed to reach its peer: dial tcp: connection timed out",
            local_cause="this workload's own peer-discovery retry budget is too "
                        "small for a dependency that is merely slow to respond",
            local_reason="the container gives up and exits before a slow connection "
                        "would eventually succeed",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: outbound connection attempts timing out (3 of "
                   "3 sampled restarts)")),
            pass_confidence="high",
        ),
    ),
)

_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO,
                       _T_IMAGE_PULL_SECRET, _T_SECRET_KEY_RENAMED,
                       _T_AUTOSCALER_CAPACITY, _T_SIDECAR_INJECTOR,
                       _T_BASE_IMAGE_TAG, _T_PVC_MULTI_ATTACH, _T_CNI_IP_POOL,
                       _T_CSI_NODE_DRIVER, _T_NODE_PID_PRESSURE,
                       _T_NODE_RUNTIME_RESTARTING, _T_NODE_CLOCK_SKEW,
                       _T_NODE_CONNTRACK_FULL)


def trainable_scenarios() -> tuple[Propagation, ...]:
    """The origins training may see. Disjoint from `all_scenarios()` by test."""
    return _TRAINING_SCENARIOS
