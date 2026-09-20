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

Each scenario is one ORIGIN and three or four VICTIMS. A victim renders as an
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

Authoring a trainable scenario
------------------------------

The rules below come in two groups. The first is enforced by
`tests/test_shared_origin_training.py` and will fail the suite. The second is
judgment: no test expresses it, which is why it is written here. Most rules in
the second group cost a defect to learn.

Enforced: the key's shape and its disjointness from the eval six; both cause
strings unique across the pool; every `local_cause` unique within the scenario
and across the pool; 3-4 victims with kinds from `vocab.ISSUE_KINDS`;
`pass_confidence` varying within the scenario; `scope_field` agreeing with
`blast_radius`; a non-empty `healthy_origin_content`; at least four
`origin_variants` whose first entry is the legacy pair and whose first lines
are literal and distinct; an `origin_state` word pair present in every variant
of its own half and absent from the other; no banned identifier shape
anywhere; and, across the pool, every scenario taught **within its own
sub-pool** in equal shares (ruling A in section 7 of
docs/superpowers/specs/2026-09-19-training-targets-fix-design.md) —
forty-eight plain stories sharing one rate, and, since the six "ruled"
stories joined the pool on 2026-09-19 (section 4 of the same spec), six
ruled stories sharing a second rate: a fifth of `shared_origin` pairs is
spread over six ruled stories and the other four fifths over forty-eight
plain ones, so a ruled story gets twice a plain story's share. Together
they exercise all sixteen issue kinds, each scenario rendering at least
three of its variants, with no cause template over 12% and the top three
under 30%.

Judgment, and unenforced:

- Put the state word where it stands on its own. `notAfter: expired 2h ago`
  is read; a bare `11m ago` was measured not to be. The enforced rule only
  says a word is present somewhere.
- Write decoy causes a reader would have to check. A decoy dismissible on
  plausibility teaches the model to dismiss decoys, not to read the origin.
- A victim read must be able to be true beside the *healthy* origin content.
  The enforced half catches only the case where the `origin_state` broken
  token appears literally in the victim's own read -- a read naming the
  shared component in other words never trips the check at all, so it
  passes vacuously. `_T_CONFIGMAP`'s two `healthy_read_content` swaps are
  what the mechanised case looks like.
- Staleness belongs in a trace sentence, never in a read. A candidate whose
  `reason` describes the origin as it was a minute ago is correct and is the
  skill being taught: the read above it settles the question. The same
  staleness inside a read has nothing above it to resolve against, so the row
  simply lies. On the shared half, no trace sentence may contradict the broken
  origin read or the `shared_cause`; staleness runs one way only.
- A trace sentence must not contradict its victim's own inventory row -- its
  `issue` kind, `status`, `evidence` or `log cause` -- on either half. Kinds
  carry semantics: `ContainerStartError` never ran, `CrashLoopBackOff` and
  `RestartLoop` ran and died, `ProbeFailure` is running and failing a probe,
  `OOMKilled` was killed by the kernel. So do termination modes: a kubelet
  kill is exit 137 or 143, while exit 1 is the entrypoint returning 1 itself.
- `log_cause` renders on both halves -- it belongs to the Finding, not the
  read (`cases.py:461`). Each `local_cause` must be compatible with it.
- Do not reuse another scenario's `shared_reason` skeleton. The uniqueness
  rules cover the cause strings and not the reason sentences, so two scenarios
  can pass every test while reading as one template with the nouns swapped.
- Scenarios sharing a blast radius must not share a cause shape. Four
  node-scoped scenarios that all read "the node is out of something" are one
  scenario spelled four ways.
- Never hard-code a namespace, node or workload name. `{ns}`, `{node}` and
  `{name}` are substituted from `names.py`.
- Render both halves and read them. This is the step that found a defect on
  each of Tasks 7 and 8, both after a review had approved the scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kubeagent_verdict.dataset.objects import Fresh, Object

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
    # The SAME finding's evidence in the world where the origin is fine. Empty
    # means `evidence` is already true there and is reused verbatim. Needed
    # only where `evidence` itself names the origin's fact -- an untolerated
    # taint the healthy node no longer carries -- because the finding block is
    # rendered on BOTH halves of a twin pair, and a healthy half whose
    # inventory asserts the origin is broken argues against its own label.
    healthy_evidence: str = ""
    log_cause: str = ""
    # The deterministic pass's OWN grade for its (wrong) local attribution.
    # Varied within a scenario on purpose — see the module docstring on
    # confidence_carried.
    pass_confidence: str = "high"
    network_policies: tuple[str, ...] = ()
    # Whether this victim hangs off a shared origin that has its own drawn
    # Object. True on every victim of a scenario that declares an
    # origin_object, False on every victim of one that does not. Among the
    # eval six it is True for the three whose job-3 label is "shared/none"
    # (node-not-ready, storage-provisioner-down, registry-unreachable) and
    # False for the other three (coredns-down, node-disk-pressure,
    # networkpolicy-deny-all). Since 2026-09-19, six training-only "ruled"
    # stories declare their own origin_object too (section 4 of the
    # 2026-09-19 training-targets design): node-kubelet-halted,
    # node-kubelet-unresponsive, pvc-provisioner-not-responding,
    # pvc-storageclass-missing, registry-mirror-unreachable and
    # registry-rate-limited. It is True on their victims as well. It is
    # therefore redundant with `origin_object is not None` today; it is a
    # per-victim field because the binding it drives is per-victim — it
    # lets Task 6's builder bind the origin's own Object for this victim
    # instead of a separate decoy.
    on_origin: bool = False
    # This victim's own decoy objects — a node, PVC or registry its local,
    # wrong candidate points at. Exactly one node decoy on every victim of
    # the three scenarios with no origin_object; empty on every victim where
    # on_origin is True, because the origin's own object already covers it.
    # The decoy is not chosen from the victim's local_cause wording: several
    # victims name nothing from the node/PVC/registry vocabulary and still
    # carry a node decoy.
    # The declared `fresh` here is a placeholder, not a claim: the builder
    # draws an ending for every decoy, and each ending replaces `fresh`
    # outright (see objects.refute and objects.unverify). Only `kind`, `name`
    # and `placement` survive every ending. `scan_reason` is a placeholder
    # too, under two of the three: `refute` writes "NotReady" over it, and the
    # lease ending writes "no kubelet lease". Only the read_failed ending
    # keeps the declared value. It reads as preserved here for one reason —
    # every victim decoy already declares "NotReady", which is what `refute`
    # writes.
    objects: tuple[Object, ...] = ()


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
    # The origin's own declared identity. Among the eval six it is set for
    # the three whose job-3 label is "shared/none" (node-not-ready,
    # storage-provisioner-down, registry-unreachable) and None for the
    # three "none/none" scenarios, whose victims still carry their own
    # local decoys but whose shared origin is never itself offered as a
    # candidate object. Since 2026-09-19 (section 4 of the training-targets
    # design) it is also set on the six training-only "ruled" stories (two
    # node, two PVC, two registry), so the rules pass has an origin object
    # it can check on its own and training carries rows the rules label
    # "shared" (before, no training row carried that label). A row can
    # still come out "none" on a ruled scenario: the unverified node twin
    # (section 5 of the same design) declares an origin_object the rules
    # cannot check at all, and the healthy-read decoy twin (every scenario
    # has one) declares one the rules refute.
    origin_object: Object | None = None
    # The origin's Fresh state once decided healthy — what
    # shared_origin_decoy_probe reads instead of the broken state. None
    # wherever origin_object is None.
    healthy_origin_fresh: Fresh | None = None


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
            objects=(
                Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="worker-2", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="worker-3", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
    origin_object=Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                          fresh=Fresh(ready="False"), intent="cause"),
    healthy_origin_fresh=Fresh(ready="True"),
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
            workload_kind="Deployment", status="Degraded", issue="ContainerStartError",
            reason="the container image was resolved but the container could not be started",
            evidence=("RunContainerError: failed to create containerd task: context deadline "
                      "exceeded"),
            local_cause="the pod requests more CPU than any remaining node has free",
            local_reason="the scheduler reports Insufficient cpu on both healthy nodes",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: RunContainerError: failed to create "
                   "containerd task: context deadline exceeded")),
            # No node is unschedulable while the origin node is Ready, so the two
            # remaining nodes carry no extra load and the container starts cleanly.
            healthy_read_content=(
                "Normal  Started  kubelet  Started container"),
            pass_confidence="high",
            on_origin=True,
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
            on_origin=True,
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
    origin_object=Object(kind="pvc", name="{pvc}", scan_reason="ProvisionerNotResponding",
                          placement="mounted",
                          fresh=Fresh(phase="Pending", storage_class="standard"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(phase="Bound", storage_class="standard"),
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
            on_origin=True,
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
            on_origin=True,
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
            on_origin=True,
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
    origin_object=Object(kind="registry", name="registry.example.com", scan_reason="3",
                          placement="", fresh=Fresh(literal="dial tcp"), intent="cause"),
    healthy_origin_fresh=Fresh(literal="manifest unknown"),
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
            on_origin=True,
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
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="ImagePullBackOff", issue="ImagePullBackOff",
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
            on_origin=True,
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
            healthy_evidence="1 node(s) had untolerated taint dedicated=gpu",
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
            objects=(
                Object(kind="node", name="{node}", scan_reason="NotReady", placement="off",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            objects=(
                Object(kind="node", name="worker-2", scan_reason="NotReady", placement="on",
                       fresh=Fresh(ready="False"), intent="decoy"),
            ),
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
            healthy_read_content=(
                "Warning  Unhealthy  8x  kubelet  Readiness probe failed: "
                "connect: connection refused on the probe port"),
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
        (("node view of kube-proxy: stale\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "kube-proxy: Service routes stale (last sync 11m ago)"),
         ("node view of kube-proxy: fresh\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "kube-proxy: Service routes fresh (last sync 12s ago)")),
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
            # correct separate-reasons answer. This victim sits first in the
            # tuple, so `p.victims[:count]` always draws it.
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
            healthy_read_content=(
                "Warning  Unhealthy  14x  kubelet  Readiness probe failed: "
                "probe timed out after 1s, successThreshold 5 not met"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-service: dial tcp: connection timed out",
            local_cause="this StatefulSet's init container waits on a Service name "
                        "that was renamed in the last chart release",
            local_reason="the init container's own log names a Service that no "
                         "longer exists in {ns}",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: wait for a dependency Service timed out "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
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
        (("Deployment scale state: replicas to 0\n"
          "Replicas:  0 desired | 0 updated | 0 total | 0 available | 0 unavailable\n"
          "Pods:      <none>\n"
          "Last log:  deployment scaled replicas to 0 (manual)"),
         ("Deployment scale state: 2 of 2 Running\n"
          "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
          "Pods:      session-5b7c9d6f4-k3p8w   1/1  Running  0 restarts\n"
          "           session-5b7c9d6f4-r9x2n   1/1  Running  0 restarts\n"
          "Last log:  serving, 2 of 2 Running")),
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
            healthy_read_content=(
                "Warning  Unhealthy  6x  kubelet  Readiness probe failed: "
                "HTTP probe returned 503, dependency check added in this revision"),
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
        Victim(
            workload_kind="Job", status="Init:CreateContainerConfigError",
            issue="Init:CreateContainerConfigError",
            reason="init container {init_container} could not build its environment",
            evidence="secret key not found for env var API_TOKEN",
            local_cause="this Job's own init container reads the key name from a "
                        "chart value that was set with a typo in its own values file",
            local_reason="the init container's own envFrom names the key with a "
                         "typo that appears in no other workload's manifest",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nInit Containers:\n  {init_container}: waiting, "
                   "CreateContainerConfigError\nEvents: Warning  Failed  kubelet  "
                   "Error: secret key not found for env var API_TOKEN")),
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
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 3 Insufficient cpu",
            local_cause="this StatefulSet's own CPU request was raised in its last "
                        "rollout to more cores than any node in the pool has",
            local_reason="the StatefulSet's own pod spec asks for 12 cores and the "
                         "largest node in the pool has 8",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                   "available: 3 Insufficient cpu")),
            pass_confidence="high",
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
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="exec format error at init entrypoint",
            local_cause="this Job's own init image was built for a different CPU "
                        "architecture than the nodes run",
            local_reason="the init container's own image manifest lists only an "
                         "arm64 layer and every node is amd64",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init container exited at startup, exec "
                   "format error (3 of 3 sampled restarts)")),
            pass_confidence="high",
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
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container {container}: timed out preparing "
                     "volume {pvc}",
            local_cause="this Deployment's own start hook copies data into its "
                        "volume and the copy runs past the kubelet's start deadline",
            local_reason="the container's own postStart copy moves 40 GiB on every "
                         "start and the kubelet's start timeout is 2 minutes",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed "
                   "to start container {container}: timed out preparing volume "
                   "{pvc}")),
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
        Victim(
            workload_kind="StatefulSet", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox: IPAM returned no address for "
                     "this pod",
            local_cause="this StatefulSet's own pod annotation pins an address "
                        "from a range that was removed from the IPAM config",
            local_reason="the pod's own address annotation names a range the IPAM "
                         "config no longer lists",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  FailedCreatePodSandBox  kubelet  "
                   "Failed to create pod sandbox: plugin type cni failed: IPAM "
                   "returned no address for this pod")),
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
        (("node view of the CSI plugin: crashed\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "CSI node plugin: crashed (CrashLoopBackOff, 4 restarts)"),
         ("node view of the CSI plugin: healthy\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "CSI node plugin: healthy (Running, 0 restarts)")),
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
        Victim(
            workload_kind="Job", status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume {pvc}: timed out "
                     "waiting for the external attacher",
            local_cause="this Job's own claim references a volume handle that was "
                        "deleted from the storage backend last week",
            local_reason="the backend lists no volume with the handle this Job's "
                         "PersistentVolume names",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nVolume: pv-{pvc}\nEvents: Warning  "
                   "FailedAttachVolume  attachdetach-controller  "
                   "AttachVolume.Attach failed for volume {pvc}: timed out "
                   "waiting for the external attacher")),
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
        (("PID condition on this node: exhausted\n"
          "Conditions:\n"
          "  PIDPressure      True    KubeletHasInsufficientPID   process table exhausted\n"
          "  Ready            True    KubeletReady                kubelet is posting ready status\n"
          "Taints:  node.kubernetes.io/pid-pressure:NoSchedule"),
         ("PID condition on this node: available\n"
          "Conditions:\n"
          "  PIDPressure      False   KubeletHasSufficientPID     pids available\n"
          "  Ready            True    KubeletReady                kubelet is posting ready status\n"
          "Taints:  <none>")),
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
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="worker pool start failed: cannot allocate thread",
            local_cause="this StatefulSet's own thread pool size was raised past "
                        "the container's pids limit in the last config change",
            local_reason="the container's own pids limit is lower than the thread "
                         "count its config now asks for",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: thread creation failed, cannot allocate "
                   "resources (3 of 3 sampled restarts)")),
            pass_confidence="high",
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
        (("kubelet view of the runtime: restarting\n"
          "Conditions:\n"
          "  Ready            False   KubeletNotReady   "
          "container runtime is restarting (PLEG is not healthy)\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  node.kubernetes.io/not-ready:NoSchedule"),
         ("kubelet view of the runtime: stable\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   container runtime is stable\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>")),
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
        Victim(
            workload_kind="Job", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: context deadline exceeded",
            local_cause="this Job's own container runs a start hook that blocks "
                        "for longer than the kubelet's start deadline",
            local_reason="the container's own postStart hook waits on a remote "
                         "call with no timeout, and the kubelet gives up on it",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed "
                   "to create containerd task: context deadline exceeded while "
                   "starting {container}")),
            pass_confidence="high",
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
        (("clock state on this node: skewed\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "System clock: skewed by 6m42s against the cluster time source"),
         ("clock state on this node: synced\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "System clock: synced (offset 4ms)")),
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
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="token validation failed: token is not yet valid",
            local_cause="this Job's own init container checks a token that a "
                        "misconfigured issuer minted with a future not-before time",
            local_reason="the token's own not-before claim is ten minutes ahead, "
                         "set by the issuer's config, on every node it is checked",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: token rejected, not yet valid "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
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
        (("node view of conntrack: full\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Conntrack: full (262144 of 262144 entries)"),
         ("node view of conntrack: clear\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Conntrack: clear (31200 of 262144 entries)")),
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
                  ("Warning  Unhealthy  11x  kubelet  Readiness probe failed: dial "
                   "tcp: i/o timeout")),
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
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="last state terminated with exit code 1",
            log_cause="outbound dial failed after 5 retries",
            local_cause="this agent's own connection pool opens a new socket per "
                        "sample and never closes the old ones",
            local_reason="the agent's own open socket count climbs to its file "
                         "descriptor limit right before each restart",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: outbound dial failed, too many open "
                   "connections (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
    ),
)

_T_LIMITRANGE_LOWERED = Propagation(
    key="namespace-limitrange-lowered",
    blast_radius="namespace",
    scope_field="ns",
    origin="a LimitRange in the namespace had its default memory limit lowered "
          "under the workloads' real footprint",
    shared_cause="the {ns} namespace's LimitRange had its default memory limit "
                 "lowered, so every pod there without its own explicit limit "
                 "inherits too little",
    shared_reason="the LimitRange {ns}/default-limits sets a default container "
                  "memory limit of 64Mi, lowered from 512Mi eighteen minutes ago",
    distractor_cause="the nodes these pods landed on are under memory pressure "
                     "and evicting workloads",
    distractor_reason="every node these pods run on reports no MemoryPressure "
                      "condition",
    rationale="the container is OOMKilled at a memory limit it inherited from "
              "the namespace's own LimitRange, which is true of every workload "
              "in {ns} without its own explicit limit",
    remedy="Raise the LimitRange's default memory limit in {ns} back to its "
          "previous value; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe {ns}/default-limits (LimitRange)",
        ("container memory default: lowered\n"
         "Type       Resource  Default  DefaultRequest\n"
         "Container  memory    64Mi     64Mi\n"
         "changed 18m ago from 512Mi"),
    ),
    healthy_origin_content=(
        "container memory default: restored\n"
        "Type       Resource  Default  DefaultRequest\n"
        "Container  memory    512Mi    512Mi\n"
        "changed 18m ago to 512Mi"
    ),
    origin_state=("lowered", "restored"),
    origin_variants=(
        (("container memory default: lowered\n"
          "Type       Resource  Default  DefaultRequest\n"
          "Container  memory    64Mi     64Mi\n"
          "changed 18m ago from 512Mi"),
         ("container memory default: restored\n"
          "Type       Resource  Default  DefaultRequest\n"
          "Container  memory    512Mi    512Mi\n"
          "changed 18m ago to 512Mi")),
        (("the namespace's memory default is lowered\n"
          "namespace {ns}: Active\n"
          "workloads under this LimitRange: 5 of 5"),
         ("the namespace's memory default is restored\n"
          "namespace {ns}: Active\n"
          "workloads under this LimitRange: 5 of 5")),
        (("LimitRange default-limits: memory default lowered 18m ago\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "containers without their own limit inherit it"),
         ("LimitRange default-limits: memory default restored 18m ago\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "containers without their own limit inherit it")),
        (("the LimitRange every flagged workload falls under: memory default "
          "lowered\n"
          "last changed 18m ago\n"
          "applies to every container without its own limit"),
         ("the LimitRange every flagged workload falls under: memory default "
          "restored\n"
          "last changed 18m ago\n"
          "applies to every container without its own limit")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="OOMKilled", issue="OOMKilled",
            reason="container {container} was OOMKilled at its inherited memory "
                  "limit",
            evidence="container {container} last terminated with reason "
                     "OOMKilled, exit code 137",
            local_cause="this Deployment's own container genuinely needs more "
                        "memory than the namespace default currently provides",
            local_reason="its memory usage climbs past the current default "
                        "within minutes of starting, on every attempt",
            read=("describe {ns}/{pod} (Pod)",
                  ("Last State:  Terminated\n"
                   "  Reason:    OOMKilled\n"
                   "  Exit Code: 137\n"
                   "  Started:   3m ago")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Init:OOMKilled", issue="Init:OOMKilled",
            reason="init container {init_container} was OOMKilled before the "
                  "main container could start",
            evidence='init container "{init_container}" (1/2), exitCode=137',
            local_cause="this Job's own init container loads a dataset too "
                        "large for the namespace default to cover",
            local_reason="the init step allocates more than the current "
                        "default allows before the main container ever runs",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n"
                   "  {init_container}:\n"
                   "    State:      Terminated\n"
                   "    Reason:     OOMKilled\n"
                   "    Exit Code:  137")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="heap reservation failed: cannot allocate memory",
            local_cause="this StatefulSet's own heap flag is set above the "
                        "container's memory limit, so its runtime refuses to start",
            local_reason="the container's own maximum heap flag is larger than its "
                         "memory limit, a mismatch inside its own manifest",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: heap reservation failed, cannot allocate "
                   "memory (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
    ),
)

_T_EGRESS_PROXY_DOWN = Propagation(
    key="namespace-egress-proxy-down",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's egress proxy Deployment has no ready replicas",
    shared_cause="the {ns} egress proxy Deployment has no ready replicas, so "
                 "every pod in {ns} that reaches out through it fails",
    shared_reason="the {ns}/egress-proxy Deployment has been restarting "
                  "continuously for eleven minutes and has never reached one "
                  "ready replica",
    distractor_cause="the namespace's NetworkPolicy began blocking egress "
                     "traffic",
    distractor_reason="the {ns} NetworkPolicy's egress rules are unchanged and "
                      "still permit the traffic these pods send",
    rationale="the workload's own outbound call fails because the {ns} egress "
              "proxy it routes through has no ready replica, which is true of "
              "everything that routes through it",
    remedy="Restore the {ns} egress proxy Deployment to a ready replica; the "
          "flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe {ns}/egress-proxy (Deployment)",
        ("egress-proxy Deployment: restarting\n"
         "Replicas:  3 desired | 3 updated | 0 available | 3 unavailable\n"
         "Pods:      egress-proxy-6f9c8d7b4-2k9pl   0/1  CrashLoopBackOff  9 "
         "restarts\n"
         "           egress-proxy-6f9c8d7b4-7h3qx   0/1  CrashLoopBackOff  9 "
         "restarts\n"
         "           egress-proxy-6f9c8d7b4-mvw2n   0/1  CrashLoopBackOff  9 "
         "restarts\n"
         "Last log:  panic: failed to load proxy TLS certificate"),
    ),
    healthy_origin_content=(
        "egress-proxy Deployment: steady\n"
        "Replicas:  3 desired | 3 updated | 3 available | 0 unavailable\n"
        "Pods:      egress-proxy-6f9c8d7b4-2k9pl   1/1  Running  0 restarts\n"
        "           egress-proxy-6f9c8d7b4-7h3qx   1/1  Running  0 restarts\n"
        "           egress-proxy-6f9c8d7b4-mvw2n   1/1  Running  0 restarts\n"
        "Last log:  proxy ready, serving"
    ),
    origin_state=("restarting", "steady"),
    origin_variants=(
        (("egress-proxy Deployment: restarting\n"
          "Replicas:  3 desired | 3 updated | 0 available | 3 unavailable\n"
          "Pods:      egress-proxy-6f9c8d7b4-2k9pl   0/1  CrashLoopBackOff  9 "
          "restarts\n"
          "           egress-proxy-6f9c8d7b4-7h3qx   0/1  CrashLoopBackOff  9 "
          "restarts\n"
          "           egress-proxy-6f9c8d7b4-mvw2n   0/1  CrashLoopBackOff  9 "
          "restarts\n"
          "Last log:  panic: failed to load proxy TLS certificate"),
         ("egress-proxy Deployment: steady\n"
          "Replicas:  3 desired | 3 updated | 3 available | 0 unavailable\n"
          "Pods:      egress-proxy-6f9c8d7b4-2k9pl   1/1  Running  0 "
          "restarts\n"
          "           egress-proxy-6f9c8d7b4-7h3qx   1/1  Running  0 "
          "restarts\n"
          "           egress-proxy-6f9c8d7b4-mvw2n   1/1  Running  0 "
          "restarts\n"
          "Last log:  proxy ready, serving")),
        (("the namespace's egress proxy is restarting\n"
          "namespace {ns}: Active\n"
          "pods in {ns} that use it: 6 of 6"),
         ("the namespace's egress proxy is steady\n"
          "namespace {ns}: Active\n"
          "pods in {ns} that use it: 6 of 6")),
        (("egress-proxy status: restarting, 0 of 3 pods ready\n"
          "last crash 40s ago\n"
          "crash log: panic: failed to load proxy TLS certificate"),
         ("egress-proxy status: steady, 3 of 3 pods ready\n"
          "last crash: none in the last hour\n"
          "crash log: none, proxy serving normally")),
        (("the egress proxy every flagged workload routes through: "
          "restarting\n"
          "Deployment {ns}/egress-proxy: 0 of 3 available\n"
          "routed through by every workload flagged here"),
         ("the egress proxy every flagged workload routes through: steady\n"
          "Deployment {ns}/egress-proxy: 3 of 3 available\n"
          "routed through by every workload flagged here")),
        (("proxy rollout state: restarting\n"
          "Replicas:  3 desired | 3 updated | 3 total | 0 available | 3 unavailable\n"
          "Pods:      egress-proxy-7f4d8c9b5-a2k7m   0/1  CrashLoopBackOff  12 restarts\n"
          "           egress-proxy-7f4d8c9b5-q8w3r   0/1  CrashLoopBackOff  12 restarts\n"
          "           egress-proxy-7f4d8c9b5-z5n1t   0/1  CrashLoopBackOff  12 restarts\n"
          "Last log:  restarting: proxy config invalid"),
         ("proxy rollout state: steady\n"
          "Replicas:  3 desired | 3 updated | 3 total | 3 available | 0 unavailable\n"
          "Pods:      egress-proxy-7f4d8c9b5-a2k7m   1/1  Running  0 restarts\n"
          "           egress-proxy-7f4d8c9b5-q8w3r   1/1  Running  0 restarts\n"
          "           egress-proxy-7f4d8c9b5-z5n1t   1/1  Running  0 restarts\n"
          "Last log:  steady, 0 errors in 1h")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 10 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container "
                     "{container}",
            local_cause="this workload's own readiness probe budget is too "
                        "tight for a normal external round trip",
            local_reason="the probe fails on its own short deadline regardless "
                        "of what it calls",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  10x  kubelet  Readiness probe failed: "
                   "outbound check blocked waiting on the egress proxy")),
            healthy_read_content=(
                "Warning  Unhealthy  10x  kubelet  Readiness probe failed: "
                "outbound check exceeded its own 900ms timeout budget"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="dial tcp: i/o timeout while establishing an outbound "
                      "connection",
            local_cause="this workload's own outbound connection timeout was "
                        "set too aggressively for a normal round trip",
            local_reason="the container gives up before a normal outbound "
                        "call would complete",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: outbound connections failing before the "
                   "handshake completes (4 of 4 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="seed download through the proxy failed",
            local_cause="this Job's own init container downloads its seed data "
                        "from a host that was decommissioned last month",
            local_reason="the init container's own download address names a host "
                         "that no longer resolves anywhere",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init download through the proxy failed "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
    ),
)

_T_NS_PVC_FULL = Propagation(
    key="namespace-shared-pvc-full",
    blast_radius="namespace",
    scope_field="ns",
    origin="a PVC shared by every workload in the namespace is completely full",
    shared_cause="the shared PVC in {ns} is full, so any pod there that writes "
                 "to it fails",
    shared_reason="the shared-data PVC in {ns} reports 100Gi used against a "
                  "100Gi capacity, with every write to it now failing",
    distractor_cause="the disk behind the shared PVC is failing at the "
                     "hardware level",
    distractor_reason="the underlying disk reports no I/O errors and passes "
                      "its own health check",
    rationale="the workload's own write fails because the shared PVC it "
              "writes to in {ns} has no space left, which is true of every "
              "workload writing to it",
    remedy="Expand or clear the shared PVC in {ns}; the flagged workloads "
          "need no change.",
    confidence="high",
    origin_read=(
        "get_related pvc {ns}/shared-data",
        ("shared-data PVC: full\n"
         "Capacity: 100Gi  Used: 100Gi\n"
         "claimed by every pod in {ns} that writes to it"),
    ),
    healthy_origin_content=(
        "shared-data PVC: free\n"
        "Capacity: 100Gi  Used: 35Gi\n"
        "claimed by every pod in {ns} that writes to it"
    ),
    origin_state=("full", "free"),
    origin_variants=(
        (("shared-data PVC: full\n"
          "Capacity: 100Gi  Used: 100Gi\n"
          "claimed by every pod in {ns} that writes to it"),
         ("shared-data PVC: free\n"
          "Capacity: 100Gi  Used: 35Gi\n"
          "claimed by every pod in {ns} that writes to it")),
        (("the namespace's shared PVC is full\n"
          "StorageClass: standard-rwx\n"
          "pods writing to it: 6 of 6"),
         ("the namespace's shared PVC is free\n"
          "StorageClass: standard-rwx\n"
          "pods writing to it: 6 of 6")),
        (("shared-data: full, 0 bytes of headroom left\n"
          "last write failure 3m ago\n"
          "mounted read-write by every pod in {ns} that uses it"),
         ("shared-data: free, 65Gi of headroom left\n"
          "last write failure: none in the last hour\n"
          "mounted read-write by every pod in {ns} that uses it")),
        (("the PVC every flagged workload writes to: full\n"
          "Capacity 100Gi, Used 100Gi\n"
          "shared read-write by every workload flagged here"),
         ("the PVC every flagged workload writes to: free\n"
          "Capacity 100Gi, Used 35Gi\n"
          "shared read-write by every workload flagged here")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="write to /var/log/app/debug.log: no space left on "
                      "device",
            local_cause="this StatefulSet's own container writes debug dumps "
                        "to a local path that nobody rotates",
            local_reason="its own local disk fills from unrotated debug "
                        "dumps on every extended run",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: failed to write to "
                   "volume: no space left on device")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: failed to write to the "
                "container's ephemeral storage: no space left on device"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe failed 8 times in the last five minutes",
            evidence="Unhealthy: readiness probe failed for container "
                     "{container}",
            local_cause="this Deployment's own health check endpoint times "
                        "out under ordinary load, unrelated to storage",
            local_reason="the probe fails on its own even when nothing about "
                        "storage has changed",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  8x  kubelet  Readiness probe failed: "
                   "health check reports the shared volume is full")),
            healthy_read_content=(
                "Warning  Unhealthy  8x  kubelet  Readiness probe failed: "
                "health check endpoint returns 503 under its own load"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="last state terminated with exit code 1",
            log_cause="write to output path failed: no space left on device",
            local_cause="this agent's own scratch directory sits on a small tmpfs "
                        "mount that each rotation overflows",
            local_reason="the agent's own tmpfs mount is 64 MiB and its rotation "
                         "writes 80 MiB before deleting the old file",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: write to its output path failed, no space "
                   "left on device (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
    ),
)

_T_MIGRATION_LOCK = Propagation(
    key="namespace-migration-lock-held",
    blast_radius="namespace",
    scope_field="ns",
    origin="a schema-migration advisory lock in the namespace is still held "
          "by a pod that no longer exists",
    shared_cause="a schema-migration advisory lock in {ns} is still held by a "
                 "pod that no longer exists, so every workload waiting on the "
                 "migration blocks",
    shared_reason="the schema-migration Lease in {ns} shows a holder identity "
                  "that stopped renewing nineteen minutes ago and was never "
                  "released",
    distractor_cause="the namespace's database Service has no ready endpoints",
    distractor_reason="the database Service in {ns} shows a ready endpoint, "
                      "and a direct connection check against it succeeds",
    rationale="the workload cannot get past its migration check because the "
              "schema-migration lock in {ns} is still held by a pod that is "
              "gone, which is true of everything waiting on it",
    remedy="Force-release the schema-migration lock in {ns}; the flagged "
          "workloads need no change.",
    confidence="high",
    origin_read=(
        "describe {ns}/schema-migration-lock (Lease)",
        ("schema-migration-lock Lease: held\n"
         "namespace {ns}: Active\n"
         "HolderIdentity: a pod ID that stopped renewing 19 minutes ago"),
    ),
    healthy_origin_content=(
        "schema-migration-lock Lease: released\n"
        "namespace {ns}: Active\n"
        "HolderIdentity: <none>"
    ),
    origin_state=("held", "released"),
    origin_variants=(
        (("schema-migration-lock Lease: held\n"
          "namespace {ns}: Active\n"
          "HolderIdentity: a pod ID that stopped renewing 19 minutes ago"),
         ("schema-migration-lock Lease: released\n"
          "namespace {ns}: Active\n"
          "HolderIdentity: <none>")),
        (("the namespace's migration lock is held\n"
          "namespace {ns}: Active\n"
          "workloads blocked on it: 5 of 5"),
         ("the namespace's migration lock is released\n"
          "namespace {ns}: Active\n"
          "workloads blocked on it: 0 of 5")),
        (("migration lock status: held, last renewed 19m ago\n"
          "owner process no longer exists\n"
          "every workload in {ns} waiting on the migration is blocked"),
         ("migration lock status: released, no owner recorded\n"
          "nothing currently holds it\n"
          "every workload in {ns} waiting on the migration can proceed")),
        (("the migration lock every flagged workload waits on: held\n"
          "last renewed 19 minutes ago by a pod that is gone\n"
          "relevant to every workload flagged here"),
         ("the migration lock every flagged workload waits on: released\n"
          "not renewed because nothing holds it\n"
          "relevant to every workload flagged here")),
    ),
    victims=(
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} "
                  "times",
            evidence="last state terminated with exit code 1",
            log_cause="timed out waiting to acquire the schema-migration lock",
            local_cause="this Job's own lock-acquisition timeout is too short "
                        "for even a normal migration window",
            local_reason="it gives up waiting well before a normal, brief "
                        "hold on the lock would clear",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n"
                   "  {init_container}:\n"
                   "    State: Waiting\n"
                   "    Reason: CrashLoopBackOff\n"
                   "    Restarts: 6")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="schema validation failed: expected migration version "
                      "not yet applied",
            local_cause="this Deployment's own database client expects a "
                        "schema version that has not been migrated yet in "
                        "this rollout",
            local_reason="every replica fails the same schema version check "
                        "on startup",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed "
                   "container {container}: waiting on the schema-migration "
                   "lock held by a stale pod")),
            healthy_read_content=(
                "Warning  BackOff  kubelet  back-off restarting failed "
                "container {container}: schema version check failed on "
                "startup"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this StatefulSet's own readiness endpoint stays not-ready "
                        "through a warm-up that outlasts its probe's failure threshold",
            local_reason="the container's own warm-up log shows 4 minutes of "
                         "loading and its probe gives up after 90 seconds",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP "
                   "probe failed with statuscode: 503")),
            pass_confidence="medium",
        ),
    ),
)

_T_POD_IDENTITY_WEBHOOK = Propagation(
    key="pod-identity-webhook-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the pod identity webhook has no ready replica, so pods are admitted "
           "without their identity volume",
    shared_cause="the pod identity webhook has no ready replica, so every pod "
                 "admitted since it went down started without its identity volume",
    shared_reason="kube-system/pod-identity-webhook shows 0 of 2 replicas available "
                  "and no ready endpoint, and its failure policy is Ignore, so "
                  "admission went ahead without the mutation",
    distractor_cause="each workload's own service account lost its identity "
                     "annotation",
    distractor_reason="the identity annotation is present and unchanged on every "
                      "service account involved, and the last edit to any of those "
                      "service accounts predates this incident by weeks",
    rationale="the workload started without its identity volume because the webhook "
              "that mounts it had no ready replica at admission time, which is true "
              "of every pod admitted since",
    remedy="Restore a ready replica of kube-system/pod-identity-webhook and restart "
           "the flagged pods so they are admitted again; the workloads themselves "
           "need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/pod-identity-webhook (Deployment)",
        ("Admission backend: down\n"
         "Replicas:  2 desired | 2 updated | 2 total | 0 available | 2 unavailable\n"
         "Conditions:  Available False  MinimumReplicasUnavailable\n"
         "Endpoints: 0 of 2 ready\n"
         "failurePolicy: Ignore (pods admitted without the identity volume)\n"
         "Pods: pod-identity-webhook-6c9d7f4b8-q2xnv 0/1 CrashLoopBackOff 7 restarts\n"
         "Last log: admission listener failed to start: certificate secret not found"),
    ),
    healthy_origin_content=(
        "Admission backend: serving\n"
        "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
        "Conditions:  Available True  MinimumReplicasAvailable\n"
        "Endpoints: 2 of 2 ready\n"
        "failurePolicy: Ignore (no admission skipped in the last 24h)\n"
        "Pods: pod-identity-webhook-6c9d7f4b8-q2xnv 1/1 Running 0 restarts\n"
        "Last log: admission listener ready, mutating pods on create"
    ),
    origin_state=("down", "serving"),
    origin_variants=(
        (("Admission backend: down\n"
          "Replicas:  2 desired | 2 updated | 2 total | 0 available | 2 unavailable\n"
          "Conditions:  Available False  MinimumReplicasUnavailable\n"
          "Endpoints: 0 of 2 ready\n"
          "failurePolicy: Ignore (pods admitted without the identity volume)\n"
          "Pods: pod-identity-webhook-6c9d7f4b8-q2xnv 0/1 CrashLoopBackOff 7 restarts\n"
          "Last log: admission listener failed to start: certificate secret not found"),
         ("Admission backend: serving\n"
          "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
          "Conditions:  Available True  MinimumReplicasAvailable\n"
          "Endpoints: 2 of 2 ready\n"
          "failurePolicy: Ignore (no admission skipped in the last 24h)\n"
          "Pods: pod-identity-webhook-6c9d7f4b8-q2xnv 1/1 Running 0 restarts\n"
          "Last log: admission listener ready, mutating pods on create")),
        (("kubelet events show the identity webhook down\n"
          "every pod created in the last 40m was admitted without a mutation\n"
          "both webhook replicas are crash-looping on startup"),
         ("kubelet events show the identity webhook serving\n"
          "every pod created in the last 24h was mutated on admission\n"
          "both webhook replicas are Running with 0 restarts")),
        (("Warning  WebhookUnavailable  admission  pod-identity-webhook down: "
          "failurePolicy Ignore, mutation skipped for new pods"),
         ("Normal  WebhookReady  admission  pod-identity-webhook serving: mutation "
          "applied to new pods")),
        (("Identity webhook status: down\n"
          "ready endpoints: 0 of 2\n"
          "last successful mutation: 40m ago"),
         ("Identity webhook status: serving\n"
          "ready endpoints: 2 of 2\n"
          "last successful mutation: 3s ago")),
        (("webhook Deployment: down\n"
          "Replicas:  2 desired | 2 updated | 2 total | 0 available | 2 unavailable\n"
          "Pods:      pod-identity-webhook-6c9d7f8b4-x2k9q   0/1  CrashLoopBackOff  6 restarts\n"
          "           pod-identity-webhook-6c9d7f8b4-m4v7t   0/1  CrashLoopBackOff  6 restarts\n"
          "Last log:  webhook down: listener failed to bind"),
         ("webhook Deployment: serving\n"
          "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
          "Pods:      pod-identity-webhook-6c9d7f8b4-x2k9q   1/1  Running  0 restarts\n"
          "           pod-identity-webhook-6c9d7f8b4-m4v7t   1/1  Running  0 restarts\n"
          "Last log:  serving admission requests, 0 errors")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="no credential source found: identity token file is absent",
            local_cause="this workload's own pod template opts out of identity "
                        "injection with a disable annotation",
            local_reason="the pod template carries the injection opt-out annotation, "
                         "so no token volume is ever requested for it",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: no credential source found, identity token "
                   "file absent (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="config fetch refused: request carried no identity token",
            local_cause="this StatefulSet's init container runs an image too old to "
                        "read the mounted identity token",
            local_reason="the init image predates token-file support and sends an "
                         "unauthenticated request every attempt",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed init "
                   "container {init_container}: config fetch refused, no identity "
                   "token presented")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this agent's own signing key rotated and its readiness "
                        "handler still loads the previous key",
            local_reason="the readiness handler logs a signing failure against the "
                         "old key id on every probe",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                   "failed with statuscode: 503, body: token signing unavailable")),
            pass_confidence="low",
        ),
    ),
)

_T_STORAGECLASS_POOL_RETIRED = Propagation(
    key="storageclass-pool-retired",
    blast_radius="cluster",
    scope_field=None,
    origin="the ssd-premium StorageClass names a storage pool that was retired, so the "
           "provisioner refuses every claim on it",
    shared_cause="the ssd-premium StorageClass points at a storage pool that was "
                 "retired, so the provisioner refuses every new claim on that class",
    shared_reason="the class parameters name pool ssd-tier-a, the backend lists that "
                  "pool as retired, and the provisioner has bound 0 claims on "
                  "ssd-premium since the pool went away while binding normally on "
                  "every other class",
    distractor_cause="the workloads' claims ask for a volume mode the class does not "
                     "support",
    distractor_reason="every claim asks for the same Filesystem volume mode it bound "
                      "with last month, and Filesystem is the mode the class has "
                      "served since it was created",
    rationale="the workload's storage on ssd-premium is refused because the class "
              "points at a retired pool, which is true of every claim and volume on "
              "that class right now",
    remedy="Point the ssd-premium StorageClass at a live pool (or recreate the class); "
           "the flagged workloads and their claims need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass ssd-premium",
        ("Pool status: retired\n"
         "provisioner: example.com/ssd-csi\n"
         "parameters: pool=ssd-tier-a, fstype=ext4\n"
         "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
         "backend pool ssd-tier-a: retired 3d ago, 0 volumes accepted\n"
         "PersistentVolumes bound on ssd-premium in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "Pool status: online\n"
        "provisioner: example.com/ssd-csi\n"
        "parameters: pool=ssd-tier-b, fstype=ext4\n"
        "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
        "backend pool ssd-tier-b: online, 412 volumes accepted\n"
        "PersistentVolumes bound on ssd-premium in the last 20m: 9"
    ),
    origin_state=("retired", "online"),
    origin_variants=(
        (("Pool status: retired\n"
          "provisioner: example.com/ssd-csi\n"
          "parameters: pool=ssd-tier-a, fstype=ext4\n"
          "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
          "backend pool ssd-tier-a: retired 3d ago, 0 volumes accepted\n"
          "PersistentVolumes bound on ssd-premium in the last 20m: 0"),
         ("Pool status: online\n"
          "provisioner: example.com/ssd-csi\n"
          "parameters: pool=ssd-tier-b, fstype=ext4\n"
          "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
          "backend pool ssd-tier-b: online, 412 volumes accepted\n"
          "PersistentVolumes bound on ssd-premium in the last 20m: 9")),
        (("the storage backend reports the pool behind ssd-premium retired\n"
          "no claim on the class has bound for 3d\n"
          "the provisioner controller is healthy and refusing each request by name"),
         ("the storage backend reports the pool behind ssd-premium online\n"
          "claims on the class bind within seconds\n"
          "the provisioner controller is healthy and accepting each request")),
        (("Warning  ProvisioningFailed  ssd-csi  pool ssd-tier-a is retired: "
          "refusing every claim on StorageClass ssd-premium"),
         ("Normal  ProvisioningSucceeded  ssd-csi  pool ssd-tier-b is online: claim "
          "on StorageClass ssd-premium bound in 4s")),
        (("ssd-premium pool state: retired\n"
          "claims refused in the last 3d: 14\n"
          "provisioner controller: healthy"),
         ("ssd-premium pool state: online\n"
          "claims refused in the last 24h: 0\n"
          "provisioner controller: healthy")),
        (("ssd-premium class: retired\n"
          "provisioner: example.com/ssd-csi\n"
          "controller storage-system/ssd-csi-controller: 1/1 ready, Running\n"
          "pool ssd-tier-a status: retired\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("ssd-premium class: online\n"
          "provisioner: example.com/ssd-csi\n"
          "controller storage-system/ssd-csi-controller: 1/1 ready, Running\n"
          "pool ssd-tier-b status: online\n"
          "PersistentVolumes bound in the last 20m: 5")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
            reason="pod has an unbound PersistentVolumeClaim and cannot be scheduled",
            evidence="0/3 nodes are available: pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="this StatefulSet's volume claim template asks for more "
                        "capacity than the class's per-volume maximum",
            local_reason="the claim's requested size exceeds the largest volume the "
                         "class will hand out",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\n"
                   "StorageClass: ssd-premium\n"
                   "Events: Warning  ProvisioningFailed  ssd-csi  pool ssd-tier-a is "
                   "retired, claim refused")),
            # The decoy half shows the pool online, so the refusal must be the
            # claim's own: its size, not the pool.
            healthy_read_content=(
                "Status: Pending\n"
                "StorageClass: ssd-premium\n"
                "Events: Warning  ProvisioningFailed  ssd-csi  requested size 2Ti "
                "exceeds the class maximum of 1Ti"
            ),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed: backend refused the attach because "
                     "the volume's pool is retired",
            healthy_evidence="AttachVolume.Attach failed: volume is still marked "
                             "attached to a node that no longer exists",
            local_cause="this Deployment's volume is still attached to a node that "
                        "was deleted before it detached",
            local_reason="the volume's attachment record points at a node object "
                         "that no longer exists",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  attachdetach-controller  "
                   "AttachVolume.Attach failed for volume {pvc}: pool ssd-tier-a is "
                   "retired")),
            healthy_read_content=(
                "Warning  FailedAttachVolume  attachdetach-controller  "
                "AttachVolume.Attach failed for volume {pvc}: volume is still "
                "attached to a deleted node"
            ),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="the Job's pod is waiting on a PersistentVolumeClaim that has not "
                   "bound",
            evidence="0/3 nodes are available: pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="this Job's claim uses WaitForFirstConsumer with a node "
                        "selector that matches no zone the class serves",
            local_reason="the claim is waiting on a first consumer whose node "
                         "selector no zone of the class can satisfy",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                   "available: pod has unbound immediate PersistentVolumeClaims; "
                   "claim refused by provisioner: pool retired")),
            healthy_read_content=(
                "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                "available: pod has unbound immediate PersistentVolumeClaims; claim "
                "is waiting for first consumer in a zone with no node"
            ),
            pass_confidence="low",
        ),
    ),
)

_T_NETPOL_EGRESS_ALLOWLIST = Propagation(
    key="networkpolicy-egress-allowlist-stale",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's egress allow-list policy no longer matches the datastore "
           "pods, so every pod's datastore traffic is dropped",
    shared_cause="the egress allow-list policy in {ns} no longer matches the datastore "
                 "pods, so every pod's connection to the datastore is dropped",
    shared_reason="{ns}/egress-allowlist selects every pod in the namespace and its "
                  "datastore rule matches 0 pods, because the datastore pods carry "
                  "tier=data since the chart upgrade and the rule still says "
                  "tier=datastore",
    distractor_cause="the datastore in {ns} has stopped accepting connections",
    distractor_reason="the datastore's own readiness probe passes on every check, and "
                      "a connection from outside {ns} reaches it and runs a query",
    rationale="the workload cannot reach the datastore because the egress policy that "
              "selects it matches no datastore pod any more, which is true of every "
              "pod in {ns} right now",
    remedy="Update the datastore rule in {ns}/egress-allowlist to the pods' current "
           "tier=data label; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-allowlist",
        ("Datastore egress: blocked\n"
         "podSelector: all pods in the namespace\n"
         "policyTypes: Egress\n"
         "egress rule 1: to podSelector tier=datastore  (matches 0 pods; datastore "
         "pods carry tier=data since the chart upgrade)\n"
         "egress rule 2: to namespaceSelector kube-system, port 53/UDP  (matches 2 "
         "pods)\n"
         "pods selected: 6 of 6"),
    ),
    healthy_origin_content=(
        "Datastore egress: allowed\n"
        "podSelector: all pods in the namespace\n"
        "policyTypes: Egress\n"
        "egress rule 1: to podSelector tier=data  (matches 3 pods)\n"
        "egress rule 2: to namespaceSelector kube-system, port 53/UDP  (matches 2 "
        "pods)\n"
        "pods selected: 6 of 6"
    ),
    origin_state=("blocked", "allowed"),
    origin_variants=(
        (("Datastore egress: blocked\n"
          "podSelector: all pods in the namespace\n"
          "policyTypes: Egress\n"
          "egress rule 1: to podSelector tier=datastore  (matches 0 pods; datastore "
          "pods carry tier=data since the chart upgrade)\n"
          "egress rule 2: to namespaceSelector kube-system, port 53/UDP  (matches 2 "
          "pods)\n"
          "pods selected: 6 of 6"),
         ("Datastore egress: allowed\n"
          "podSelector: all pods in the namespace\n"
          "policyTypes: Egress\n"
          "egress rule 1: to podSelector tier=data  (matches 3 pods)\n"
          "egress rule 2: to namespaceSelector kube-system, port 53/UDP  (matches 2 "
          "pods)\n"
          "pods selected: 6 of 6")),
        (("the namespace egress policy leaves datastore traffic blocked\n"
          "its datastore rule matches no pod since the chart upgrade relabelled them\n"
          "DNS egress still matches and resolves"),
         ("the namespace egress policy leaves datastore traffic allowed\n"
          "its datastore rule matches all 3 datastore pods\n"
          "DNS egress still matches and resolves")),
        (("Warning  PolicyDrop  network-plugin  egress to datastore blocked by "
          "egress-allowlist: rule selector tier=datastore matches 0 pods"),
         ("Normal  PolicyAllow  network-plugin  egress to datastore allowed by "
          "egress-allowlist: rule selector tier=data matches 3 pods")),
        (("datastore path from this namespace: blocked\n"
          "selector drift: rule says tier=datastore, pods say tier=data\n"
          "connections dropped in the last 10m: 1284"),
         ("datastore path from this namespace: allowed\n"
          "selector drift: none, rule and pods both say tier=data\n"
          "connections dropped in the last 10m: 0")),
        (("policy match state: blocked\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to tier=datastore tcp/5432 (datastore pods now carry tier=data)\n"
          "connections to datastore: blocked\n"
          "pods selected: 6 of 6"),
         ("policy match state: allowed\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to tier=data tcp/5432\n"
          "connections to datastore: allowed\n"
          "pods selected: 6 of 6")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="datastore connection timed out during startup",
            local_cause="this workload's own datastore host setting still points at "
                        "the previous release's service name",
            local_reason="the connection string names a service that was renamed in "
                         "the previous release",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection to the datastore timed out before "
                   "the first query (3 of 3 sampled restarts)")),
            pass_confidence="high",
            network_policies=("egress-allowlist",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-datastore gave up after 120s",
            local_cause="this StatefulSet's init wait uses a 120s deadline shorter "
                        "than the datastore's own startup time",
            local_reason="the init container's deadline expires before the datastore "
                         "reports ready on every attempt",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed init "
                   "container {init_container}: wait-for-datastore gave up after "
                   "120s")),
            pass_confidence="medium",
            network_policies=("egress-allowlist",),
        ),
        Victim(
            workload_kind="Deployment", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this workload's readiness check runs a datastore query with "
                        "a 1s timeout that the query never meets",
            local_reason="the readiness query's own timeout is shorter than the "
                         "query's usual latency",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                   "failed with statuscode: 503, body: datastore check timed out")),
            pass_confidence="low",
            network_policies=("egress-allowlist",),
        ),
    ),
)

_T_NODE_MEMORY_PRESSURE = Propagation(
    key="node-memory-pressure",
    blast_radius="node",
    scope_field="node",
    origin="the node is under memory pressure and its kubelet is evicting pods and "
           "refusing new ones",
    shared_cause="node {node} is under memory pressure, so the kubelet is evicting its "
                 "largest pods and turning new ones away",
    shared_reason="the kubelet on {node} has been in memory-pressure eviction for 12m, "
                  "with the node's working set within 2 GiB of its 64 GiB allocatable "
                  "and the memory-pressure taint keeping new pods off it",
    distractor_cause="the workloads' own memory limits were lowered in the last "
                     "rollout",
    distractor_reason="the container limits are unchanged since the previous release, "
                      "and the last rollout changed only the image tag",
    rationale="the kubelet on {node} is reclaiming memory from every pod it hosts, and "
              "this workload is one of them; the pressure is the node's, not the "
              "workload's",
    remedy="Relieve the memory pressure on {node} (drain the largest tenants or add "
           "capacity) and let the evicted pods reschedule; the flagged workloads need "
           "no change.",
    confidence="high",
    origin_read=(
        "describe node {node} (memory)",
        ("Memory: reclaiming\n"
         "Conditions:\n"
         "  MemoryPressure   True    KubeletHasInsufficientMemory   kubelet has "
         "insufficient memory available\n"
         "  Ready            True    KubeletReady                   kubelet is "
         "posting ready status\n"
         "Taints:  node.kubernetes.io/memory-pressure:NoSchedule\n"
         "Allocatable memory: 64Gi\n"
         "Working set: 61.8Gi (97%)\n"
         "Evictions in the last 10m: 4"),
    ),
    healthy_origin_content=(
        "Memory: headroom\n"
        "Conditions:\n"
        "  MemoryPressure   False   KubeletHasSufficientMemory     kubelet has "
        "sufficient memory available\n"
        "  Ready            True    KubeletReady                   kubelet is "
        "posting ready status\n"
        "Taints:  <none>\n"
        "Allocatable memory: 64Gi\n"
        "Working set: 23.4Gi (37%)\n"
        "Evictions in the last 10m: 0"
    ),
    origin_state=("reclaiming", "headroom"),
    origin_variants=(
        (("Memory: reclaiming\n"
          "Conditions:\n"
          "  MemoryPressure   True    KubeletHasInsufficientMemory   kubelet has "
          "insufficient memory available\n"
          "  Ready            True    KubeletReady                   kubelet is "
          "posting ready status\n"
          "Taints:  node.kubernetes.io/memory-pressure:NoSchedule\n"
          "Allocatable memory: 64Gi\n"
          "Working set: 61.8Gi (97%)\n"
          "Evictions in the last 10m: 4"),
         ("Memory: headroom\n"
          "Conditions:\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory     kubelet has "
          "sufficient memory available\n"
          "  Ready            True    KubeletReady                   kubelet is "
          "posting ready status\n"
          "Taints:  <none>\n"
          "Allocatable memory: 64Gi\n"
          "Working set: 23.4Gi (37%)\n"
          "Evictions in the last 10m: 0")),
        (("kubelet on the node is reclaiming memory from its pods\n"
          "the working set has sat within 2Gi of allocatable for 12m\n"
          "the memory-pressure taint is keeping new pods off it"),
         ("kubelet on the node reports memory headroom\n"
          "the working set has sat under 40% of allocatable all day\n"
          "no pressure taint is set")),
        (("Warning  EvictionThresholdMet  kubelet  memory: reclaiming, working set "
          "above the eviction threshold, evicting pods"),
         ("Normal  NodeHasSufficientMemory  kubelet  memory: headroom, working set "
          "below every eviction threshold")),
        (("node memory state: reclaiming\n"
          "available: 1.9Gi of 64Gi\n"
          "oom kills logged by the node in the last 10m: 6"),
         ("node memory state: headroom\n"
          "available: 40.6Gi of 64Gi\n"
          "oom kills logged by the node in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="OOMKilled", issue="OOMKilled",
            reason="container {container} was killed by the kernel out-of-memory "
                   "handler",
            evidence="last state terminated with reason OOMKilled, exit code 137",
            local_cause="this workload's own request cache grows without bound until "
                        "the kernel kills it",
            local_reason="the container's working set climbs steadily from start to "
                         "kill on every instance",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\n"
                   "Last State: Terminated, Reason: OOMKilled, Exit Code: 137\n"
                   "Events: Warning  SystemOOM  kubelet  System OOM encountered, "
                   "victim process: {container}")),
            # A node with memory headroom raises no system-wide OOM, so on the
            # decoy half the kill comes from the container's own cgroup limit.
            healthy_read_content=(
                "Node: {node}\n"
                "Last State: Terminated, Reason: OOMKilled, Exit Code: 137\n"
                "Events: Warning  OOMKilling  kubelet  memory cgroup out of memory: "
                "killed process in container {container} at its own limit"
            ),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: context deadline exceeded after 2s",
            local_cause="this StatefulSet's readiness handler runs a full index scan "
                        "that outgrows its 2s probe timeout as the data set grows",
            local_reason="the probe handler's own scan time has grown past the probe "
                         "timeout with the data set",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: Get "
                   "readiness endpoint: context deadline exceeded after 2s")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="last state terminated with exit code 137",
            log_cause="process killed by signal 9 while flushing its buffer",
            local_cause="this agent's own liveness check kills it whenever a flush "
                        "runs longer than the check's 5s deadline",
            local_reason="the container's liveness probe fails during each long flush "
                         "and the kubelet kills it every time",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: process received signal 9 mid-flush and "
                   "restarted (3 of 3 sampled restarts)")),
            pass_confidence="low",
        ),
    ),
)

_T_NODE_NETWORK_UNAVAILABLE = Propagation(
    key="node-network-unavailable",
    blast_radius="node",
    scope_field="node",
    origin="the node lost its route to the pod network, so no pod placed there can get "
           "a sandbox",
    shared_cause="node {node} has no route to the pod network, so no pod placed there "
                 "can get a sandbox",
    shared_reason="{node} reports NetworkUnavailable True with reason NoRouteCreated, "
                  "the network-unavailable taint is on the node, and every pod that "
                  "landed there in the last 9m is stuck creating its sandbox",
    distractor_cause="the CNI plugin binary was removed from these pods' images in the "
                     "last rebuild",
    distractor_reason="the CNI plugin is installed on the node, not in a workload "
                      "image, and the failing pods were built from unrelated images",
    rationale="the node has no route to the pod network, so the kubelet cannot give "
              "any pod on it a network sandbox; this workload is one of the pods "
              "placed there, and its own spec is unchanged",
    remedy="Restore the pod-network route on {node} (restart the network agent or "
           "re-run the route controller) and let the stuck pods retry; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Pod network route on this node: missing\n"
         "Conditions:\n"
         "  NetworkUnavailable   True    NoRouteCreated   route to the pod network is "
         "missing\n"
         "  Ready                True    KubeletReady     kubelet is posting ready "
         "status\n"
         "Taints:  node.kubernetes.io/network-unavailable:NoSchedule"),
    ),
    healthy_origin_content=(
        "Pod network route on this node: installed\n"
        "Conditions:\n"
        "  NetworkUnavailable   False   RouteCreated     route to the pod network is "
        "installed\n"
        "  Ready                True    KubeletReady     kubelet is posting ready "
        "status\n"
        "Taints:  <none>"
    ),
    origin_state=("missing", "installed"),
    origin_variants=(
        (("Pod network route on this node: missing\n"
          "Conditions:\n"
          "  NetworkUnavailable   True    NoRouteCreated   route to the pod network is "
          "missing\n"
          "  Ready                True    KubeletReady     kubelet is posting ready "
          "status\n"
          "Taints:  node.kubernetes.io/network-unavailable:NoSchedule"),
         ("Pod network route on this node: installed\n"
          "Conditions:\n"
          "  NetworkUnavailable   False   RouteCreated     route to the pod network is "
          "installed\n"
          "  Ready                True    KubeletReady     kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("the route controller reports this node's pod-network route missing\n"
          "no sandbox has been created on the node for 9m\n"
          "the network-unavailable taint is set"),
         ("the route controller reports this node's pod-network route installed\n"
          "sandboxes are being created on the node normally\n"
          "no network-unavailable taint is set")),
        (("Warning  NetworkNotReady  kubelet  pod network route missing: cannot set up "
          "a sandbox on this node"),
         ("Normal  NetworkReady  kubelet  pod network route installed: sandboxes are "
          "being set up on this node")),
        (("route state: missing\n"
          "sandboxes created in the last 10m: 0 of 14 attempts\n"
          "kubelet has logged NetworkPluginNotReady for 9m"),
         ("route state: installed\n"
          "sandboxes created in the last 10m: 14 of 14 attempts\n"
          "kubelet has logged no network plugin error")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox: network plugin returned error: no "
                     "route to the pod network",
            local_cause="this Deployment's own pod spec asks for a host network it is "
                        "not allowed to use",
            local_reason="the pod spec sets hostNetwork true and the namespace's "
                         "pod security policy rejects it",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  FailedCreatePodSandBox  kubelet  "
                  "Failed to create pod sandbox: network plugin returned error")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 1 node(s) had untolerated taint "
                     "node.kubernetes.io/network-unavailable, 2 Insufficient memory",
            healthy_evidence="0/3 nodes are available: 1 node(s) had untolerated taint "
                             "dedicated=gpu, 2 Insufficient memory",
            local_cause="this StatefulSet's own memory request was doubled in its last "
                        "rollout past what the two remaining nodes can offer",
            local_reason="the pod asks for 24Gi and the two schedulable nodes have "
                         "16Gi free each",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: 1 node(s) had an untolerated taint, 2 Insufficient memory")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dial tcp: connect: network is unreachable",
            local_cause="this agent's own readiness probe checks a port the last config "
                        "change moved",
            local_reason="the probe dials 9100 and the agent now listens on 9101",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: dial tcp: "
                  "connect: network is unreachable")),
            pass_confidence="high",
        ),
    ),
)

_T_NODE_KERNEL_DEADLOCK = Propagation(
    key="node-kernel-deadlock",
    blast_radius="node",
    scope_field="node",
    origin="the node's kernel has a deadlocked task, so every container operation on "
           "it hangs",
    shared_cause="the kernel on node {node} has a deadlocked task, so every container "
                 "operation on that node hangs",
    shared_reason="{node} reports KernelDeadlock True with a task hung for more than "
                  "120 seconds, and every container start, exec and probe on the node "
                  "has stalled since",
    distractor_cause="the container runtime on the node was upgraded to a build that "
                     "hangs on cgroup v2",
    distractor_reason="the runtime version on the node is unchanged since last month "
                      "and the same build runs fine on its peers",
    rationale="a hung kernel task on {node} is blocking every container operation the "
              "kubelet issues there; this workload is on that node, and its hang is "
              "the node's, not its own",
    remedy="Reboot {node} (or drain it and let the hung task clear) and let its pods "
           "reschedule; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Kernel task state on this node: hung\n"
         "Conditions:\n"
         "  KernelDeadlock   True    KernelHasDeadlock   a task has hung for more than "
         "120 seconds\n"
         "  Ready            True    KubeletReady        kubelet is posting ready "
         "status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Kernel task state on this node: responsive\n"
        "Conditions:\n"
        "  KernelDeadlock   False   KernelHasNoDeadlock   every task is responsive\n"
        "  Ready            True    KubeletReady          kubelet is posting ready "
        "status\n"
        "Taints:  <none>"
    ),
    origin_state=("hung", "responsive"),
    origin_variants=(
        (("Kernel task state on this node: hung\n"
          "Conditions:\n"
          "  KernelDeadlock   True    KernelHasDeadlock   a task has hung for more than "
          "120 seconds\n"
          "  Ready            True    KubeletReady        kubelet is posting ready "
          "status\n"
          "Taints:  <none>"),
         ("Kernel task state on this node: responsive\n"
          "Conditions:\n"
          "  KernelDeadlock   False   KernelHasNoDeadlock   every task is responsive\n"
          "  Ready            True    KubeletReady          kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("the node problem detector reports a kernel task hung on this node\n"
          "container starts and execs on the node have stalled for 6m\n"
          "the kubelet is still posting ready status"),
         ("the node problem detector reports every kernel task responsive on this "
          "node\n"
          "container starts and execs on the node complete normally\n"
          "the kubelet is posting ready status")),
        (("Warning  KernelDeadlock  node-problem-detector  task hung for 120s: "
          "INFO: task containerd-shim:4821 blocked for more than 120 seconds"),
         ("Normal  KernelResponsive  node-problem-detector  every task responsive: no "
          "blocked task in the last 30m")),
        (("kernel watchdog: hung\n"
          "blocked tasks: 3\n"
          "oldest blocked task age: 6m14s"),
         ("kernel watchdog: responsive\n"
          "blocked tasks: 0\n"
          "oldest blocked task age: n/a")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: context deadline exceeded",
            local_cause="this Deployment's own entrypoint waits on a lock file that a "
                        "previous run left behind",
            local_reason="the container's start script blocks on a stale lock in its "
                         "own working directory",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: context deadline exceeded")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: command timed out after 5s",
            local_cause="this StatefulSet's own exec probe runs a query that no longer "
                        "finishes inside its 5s timeout",
            local_reason="the probe query scans a table that has grown past what the "
                         "timeout allows",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: command timed "
                  "out after 5s")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="Liveness probe failed: command timed out; container will be "
                     "restarted",
            local_cause="this agent's own liveness hook forks a helper that blocks on "
                        "a pipe nobody reads",
            local_reason="the hook's helper writes to a pipe with no reader and the "
                         "hook waits on it",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: liveness command timed out, killed by kubelet "
                  "(3 of 3 sampled restarts)")),
            log_cause="liveness command timed out, killed by kubelet",
            pass_confidence="high",
        ),
    ),
)

_T_NODE_READONLY_FILESYSTEM = Propagation(
    key="node-readonly-filesystem",
    blast_radius="node",
    scope_field="node",
    origin="the node's root filesystem remounted read-only after an I/O error, so no "
           "container there can write to disk",
    shared_cause="the root filesystem on node {node} is mounted read-only, so no "
                 "container there can write to disk",
    shared_reason="{node} reports ReadonlyFilesystem True after an I/O error, and "
                  "every container on the node that writes to its own filesystem has "
                  "failed since the remount 8m ago",
    distractor_cause="the workloads' own images were rebuilt with a read-only root "
                     "filesystem setting",
    distractor_reason="the pod specs declare no readOnlyRootFilesystem and the images "
                      "are unchanged since last week",
    rationale="the root filesystem on {node} is read-only, so every container write on "
              "the node fails; this workload writes on start and is one of them",
    remedy="Repair the disk behind {node}'s root filesystem and remount it writable "
           "(or replace the node) and let the pods reschedule; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Root filesystem on this node: read-only\n"
         "Conditions:\n"
         "  ReadonlyFilesystem   True    FilesystemIsReadOnly   root filesystem "
         "remounted read-only after an I/O error\n"
         "  Ready                True    KubeletReady           kubelet is posting "
         "ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Root filesystem on this node: writable\n"
        "Conditions:\n"
        "  ReadonlyFilesystem   False   FilesystemIsNotReadOnly   root filesystem is "
        "writable\n"
        "  Ready                True    KubeletReady              kubelet is posting "
        "ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("read-only", "writable"),
    origin_variants=(
        (("Root filesystem on this node: read-only\n"
          "Conditions:\n"
          "  ReadonlyFilesystem   True    FilesystemIsReadOnly   root filesystem "
          "remounted read-only after an I/O error\n"
          "  Ready                True    KubeletReady           kubelet is posting "
          "ready status\n"
          "Taints:  <none>"),
         ("Root filesystem on this node: writable\n"
          "Conditions:\n"
          "  ReadonlyFilesystem   False   FilesystemIsNotReadOnly   root filesystem is "
          "writable\n"
          "  Ready                True    KubeletReady              kubelet is posting "
          "ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports this node's root filesystem read-only\n"
          "the remount followed an I/O error 8m ago\n"
          "every container write on the node has failed since"),
         ("the node problem detector reports this node's root filesystem writable\n"
          "no I/O error has been logged on the node\n"
          "container writes on the node succeed")),
        (("Warning  FilesystemIsReadOnly  node-problem-detector  root filesystem "
          "remounted read-only: EXT4-fs error on sda1"),
         ("Normal  FilesystemIsWritable  node-problem-detector  root filesystem "
          "writable: no error on sda1 in the last 24h")),
        (("mount state of the root filesystem: read-only\n"
          "I/O errors on the root device in the last 1h: 37\n"
          "container writes failing on the node: all"),
         ("mount state of the root filesystem: writable\n"
          "I/O errors on the root device in the last 1h: 0\n"
          "container writes failing on the node: none")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="open /var/run/app.pid: input/output error",
            local_cause="this Deployment's own container writes its pid file to a path "
                        "its image marks immutable",
            local_reason="the image sets the pid directory immutable at build time and "
                         "the entrypoint still writes there",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: write to the container filesystem failed "
                  "(3 of 3 sampled restarts)")),
            log_cause="write to the container filesystem failed",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: mkdir /run/containerd: "
                     "input/output error",
            local_cause="this Job's own container image is corrupt in the registry "
                        "and fails to unpack",
            local_reason="the image manifest lists a layer whose digest does not "
                         "match its content",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: input/output error")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.SetUp failed for volume {pvc}: mkdir on the node's "
                     "kubelet directory: input/output error",
            local_cause="this StatefulSet's own claim asks for a filesystem type the "
                        "node's kernel cannot mount",
            local_reason="the claim's storage class sets fsType xfs and the node "
                         "image ships no xfs module",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nVolume: pv-{pvc}\nEvents: Warning  FailedMount  "
                  "kubelet  MountVolume.SetUp failed for volume {pvc}")),
            pass_confidence="high",
        ),
    ),
)

_T_NODE_FREQUENT_KUBELET_RESTART = Propagation(
    key="node-frequent-kubelet-restart",
    blast_radius="node",
    scope_field="node",
    origin="the node's kubelet keeps restarting, so its pods keep losing probes and "
           "container starts",
    shared_cause="the kubelet on node {node} keeps restarting, so its pods keep losing "
                 "probes and container starts",
    shared_reason="{node} reports FrequentKubeletRestart True with 6 kubelet restarts "
                  "in 20 minutes, and every probe and container start on the node "
                  "has been interrupted at least once in that window",
    distractor_cause="the workloads' own probes were tightened in the last chart "
                     "release",
    distractor_reason="the probe settings are unchanged since last month and the same "
                      "settings pass on pods scheduled to other nodes",
    rationale="the kubelet on {node} is flapping, so every probe and container start "
              "it owns is cut short; this workload is on that node and its own "
              "spec is unchanged",
    remedy="Stop the kubelet restart loop on {node} (read its journal, fix the "
           "crashing config or reprovision the node); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Kubelet on this node: flapping\n"
         "Conditions:\n"
         "  FrequentKubeletRestart   True    FrequentKubeletRestart     kubelet is "
         "flapping: 6 restarts in 20 minutes\n"
         "  Ready                    True    KubeletReady               kubelet is "
         "posting ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Kubelet on this node: steady\n"
        "Conditions:\n"
        "  FrequentKubeletRestart   False   NoFrequentKubeletRestart   kubelet is "
        "steady: 0 restarts in 20 minutes\n"
        "  Ready                    True    KubeletReady               kubelet is "
        "posting ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("flapping", "steady"),
    origin_variants=(
        (("Kubelet on this node: flapping\n"
          "Conditions:\n"
          "  FrequentKubeletRestart   True    FrequentKubeletRestart     kubelet is "
          "flapping: 6 restarts in 20 minutes\n"
          "  Ready                    True    KubeletReady               kubelet is "
          "posting ready status\n"
          "Taints:  <none>"),
         ("Kubelet on this node: steady\n"
          "Conditions:\n"
          "  FrequentKubeletRestart   False   NoFrequentKubeletRestart   kubelet is "
          "steady: 0 restarts in 20 minutes\n"
          "  Ready                    True    KubeletReady               kubelet is "
          "posting ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports the kubelet on this node flapping\n"
          "the kubelet has restarted 6 times in the last 20m\n"
          "each restart cut every probe and container start on the node short"),
         ("the node problem detector reports the kubelet on this node steady\n"
          "the kubelet has not restarted in the last 20m\n"
          "probes and container starts on the node complete normally")),
        (("Warning  FrequentKubeletRestart  node-problem-detector  kubelet flapping: "
          "6 restarts in 20m, last exit status 1"),
         ("Normal  KubeletSteady  node-problem-detector  kubelet steady: 0 restarts in "
          "20m, uptime 31d")),
        (("kubelet service state: flapping\n"
          "restarts in the last 20m: 6\n"
          "seconds since the last kubelet start: 48"),
         ("kubelet service state: steady\n"
          "restarts in the last 20m: 0\n"
          "seconds since the last kubelet start: 2678400")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: probe interrupted by kubelet restart",
            local_cause="this Deployment's own readiness handler returns 503 until a "
                        "cache warm-up that takes longer than its probe allows",
            local_reason="the handler reports not-ready for 90s after start and the "
                         "probe fails it after 30s",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="container was killed: kubelet restarted mid-start",
            local_cause="this agent's own config reload handler exits the process "
                        "whenever its watched file is rewritten",
            local_reason="the config file is rewritten every few minutes by a sidecar "
                         "and each rewrite exits the agent",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: process exited on config reload "
                  "(3 of 3 sampled restarts)")),
            log_cause="process exited on config reload",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: kubelet connection reset during "
                     "container create",
            local_cause="this Job's own container command names a binary the image "
                        "does not ship",
            local_reason="the command runs a tool that was dropped from the image "
                         "in its last rebuild",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container {container}")),
            pass_confidence="high",
        ),
    ),
)

_T_NODE_CORDONED_DRAINING = Propagation(
    key="node-cordoned-draining",
    blast_radius="node",
    scope_field="node",
    origin="the node is cordoned and draining, so its pods are being evicted and "
           "nothing new lands there",
    shared_cause="node {node} is cordoned and draining, so its pods are being evicted "
                 "and nothing new lands there",
    shared_reason="{node} is marked unschedulable with the unschedulable taint, a "
                  "drain has been evicting its pods for 7m, and every pod that "
                  "needs that node is either evicted or waiting on it",
    distractor_cause="the cluster is out of capacity and the pending pods are waiting "
                     "on the autoscaler",
    distractor_reason="the other nodes have room and the autoscaler reports no "
                      "scale-up in progress",
    rationale="{node} is cordoned and being drained, so its pods are evicted and any "
              "pod pinned to it waits; this workload's trouble is the drain, not its "
              "own spec",
    remedy="Finish or cancel the drain of {node} and uncordon it when it is ready; "
           "the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Scheduling on this node: cordoned\n"
         "Unschedulable: true\n"
         "Conditions:\n"
         "  Ready            True    KubeletReady   kubelet is posting ready status\n"
         "  MemoryPressure   False   KubeletHasSufficientMemory\n"
         "  DiskPressure     False   KubeletHasNoDiskPressure\n"
         "Taints:  node.kubernetes.io/unschedulable:NoSchedule\n"
         "Events: Normal  NodeNotSchedulable  kubelet  this node is cordoned and "
         "draining"),
    ),
    healthy_origin_content=(
        "Scheduling on this node: accepting\n"
        "Unschedulable: false\n"
        "Conditions:\n"
        "  Ready            True    KubeletReady   kubelet is posting ready status\n"
        "  MemoryPressure   False   KubeletHasSufficientMemory\n"
        "  DiskPressure     False   KubeletHasNoDiskPressure\n"
        "Taints:  <none>\n"
        "Events: Normal  NodeSchedulable  kubelet  this node is accepting pods"
    ),
    origin_state=("cordoned", "accepting"),
    origin_variants=(
        (("Scheduling on this node: cordoned\n"
          "Unschedulable: true\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  node.kubernetes.io/unschedulable:NoSchedule\n"
          "Events: Normal  NodeNotSchedulable  kubelet  this node is cordoned and "
          "draining"),
         ("Scheduling on this node: accepting\n"
          "Unschedulable: false\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Events: Normal  NodeSchedulable  kubelet  this node is accepting pods")),
        (("the node was cordoned 7m ago and a drain is evicting its pods\n"
          "12 pods have been evicted from it so far\n"
          "nothing new is being scheduled onto it"),
         ("the node is accepting pods and no drain is running\n"
          "0 pods have been evicted from it in the last hour\n"
          "new pods are scheduled onto it normally")),
        (("Normal  NodeNotSchedulable  kubelet  node cordoned: drain started by the "
          "maintenance controller"),
         ("Normal  NodeSchedulable  kubelet  node accepting pods: schedulable again per the "
          "maintenance controller")),
        (("drain status: cordoned\n"
          "pods evicted so far: 12 of 18\n"
          "time since cordon: 7m"),
         ("drain status: accepting pods\n"
          "pods evicted so far: 0 of 0\n"
          "time since cordon: n/a")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) "
                     "had volume node affinity conflict",
            local_cause="this StatefulSet's own volume is pinned to a zone none of "
                        "the schedulable nodes are in",
            local_reason="the claim's volume lives in one zone and the nodes with room "
                         "are all in the other",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: 1 node(s) were unschedulable, 2 node(s) had volume node "
                  "affinity conflict")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="pod evicted by drain; replacement started on another node and "
                     "was evicted again",
            local_cause="this Deployment's own pod disruption budget allows zero "
                        "disruptions, so every routine eviction is retried forever",
            local_reason="the budget sets maxUnavailable 0 with a single replica, so "
                         "no eviction can ever succeed cleanly",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: process received SIGTERM and exited "
                  "(3 of 3 sampled restarts)")),
            log_cause="process received SIGTERM and exited",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="wait-for-node: this pod's node affinity target is not "
                     "schedulable",
            local_cause="this Job's own init container waits for a node label that "
                        "the last node pool rollout renamed",
            local_reason="the init step polls for a node label that no node carries "
                         "since the rename",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init wait for a node label timed out "
                  "(3 of 3 sampled restarts)")),
            log_cause="init wait for a node label timed out",
            pass_confidence="high",
        ),
    ),
)

_T_NODE_CORRUPT_OVERLAY = Propagation(
    key="node-corrupt-overlay",
    blast_radius="node",
    scope_field="node",
    origin="the node's container layer store is corrupt, so containers there cannot "
           "start from cached image layers",
    shared_cause="the container layer store on node {node} is corrupt, so containers "
                 "there cannot start from cached image layers",
    shared_reason="{node} reports CorruptDockerOverlay2 True with unreadable cached "
                  "layers, and every container start on the node that reuses a cached "
                  "layer has failed since 11m ago",
    distractor_cause="the registry served a broken image layer to every pull in the "
                     "last hour",
    distractor_reason="the same images start normally on the other nodes, which pulled "
                      "them from the same registry in the same hour",
    rationale="the layer store on {node} is corrupt, so any container that starts "
              "from a cached layer there fails; this workload's image is cached on "
              "that node and its own build is sound",
    remedy="Clear the corrupt layer store on {node} (wipe the overlay2 directory and "
           "restart the runtime, or replace the node); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Layer store on this node: corrupt\n"
         "Conditions:\n"
         "  CorruptDockerOverlay2   True    CorruptDockerOverlay2     overlay2 layer "
         "store is corrupt: cached layers unreadable\n"
         "  Ready                   True    KubeletReady              kubelet is "
         "posting ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Layer store on this node: intact\n"
        "Conditions:\n"
        "  CorruptDockerOverlay2   False   NoCorruptDockerOverlay2   overlay2 layer "
        "store is intact\n"
        "  Ready                   True    KubeletReady              kubelet is "
        "posting ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("corrupt", "intact"),
    origin_variants=(
        (("Layer store on this node: corrupt\n"
          "Conditions:\n"
          "  CorruptDockerOverlay2   True    CorruptDockerOverlay2     overlay2 layer "
          "store is corrupt: cached layers unreadable\n"
          "  Ready                   True    KubeletReady              kubelet is "
          "posting ready status\n"
          "Taints:  <none>"),
         ("Layer store on this node: intact\n"
          "Conditions:\n"
          "  CorruptDockerOverlay2   False   NoCorruptDockerOverlay2   overlay2 layer "
          "store is intact\n"
          "  Ready                   True    KubeletReady              kubelet is "
          "posting ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports this node's overlay2 store corrupt\n"
          "cached image layers on the node are unreadable\n"
          "container starts that reuse a cached layer fail there"),
         ("the node problem detector reports this node's overlay2 store intact\n"
          "cached image layers on the node read normally\n"
          "container starts that reuse a cached layer succeed there")),
        (("Warning  CorruptDockerOverlay2  node-problem-detector  layer store corrupt: "
          "failed to read layer diff, input/output error"),
         ("Normal  OverlayHealthy  node-problem-detector  layer store intact: all "
          "cached layers verified")),
        (("overlay2 store state: corrupt\n"
          "unreadable cached layers: 41 of 212\n"
          "container starts failed on this node in the last 10m: 19"),
         ("overlay2 store state: intact\n"
          "unreadable cached layers: 0 of 212\n"
          "container starts failed on this node in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: failed to mount rootfs: "
                     "input/output error",
            local_cause="this Deployment's own image was pushed with a layer that "
                        "its build never finished writing",
            local_reason="the image's last layer is truncated in the registry and "
                         "fails to unpack anywhere",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: failed to mount rootfs")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="exec: unable to load shared library: input/output error",
            local_cause="this StatefulSet's own image links a library its final "
                        "build stage never copied in",
            local_reason="the entrypoint loads a library that is absent from the "
                         "image's final layer",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: shared library failed to load at start "
                  "(3 of 3 sampled restarts)")),
            log_cause="shared library failed to load at start",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="init: read /etc/app/schema.sql: input/output error",
            local_cause="this Job's own init container reads a seed file that its "
                        "image ships as an empty placeholder",
            local_reason="the seed file in the init image is zero bytes and the init "
                         "step fails to parse it",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init read of a bundled file failed "
                  "(3 of 3 sampled restarts)")),
            log_cause="init read of a bundled file failed",
            pass_confidence="high",
        ),
    ),
)

_T_EXTERNAL_SECRETS_DOWN = Propagation(
    key="external-secrets-operator-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the external-secrets operator is down, so the Secrets it syncs are no "
           "longer created and pods that mount them cannot start",
    shared_cause="the external-secrets operator is down, so the Secrets it syncs are "
                 "no longer created and pods that mount them cannot start",
    shared_reason="kube-system/external-secrets shows 0 of 1 replicas available with "
                  "its pod in CrashLoopBackOff after 7 restarts, its last log says "
                  "the secret store is unreachable, and every ExternalSecret it owns "
                  "has been SecretSyncedError since",
    distractor_cause="the workloads' own Secret names were changed in the last chart "
                     "release",
    distractor_reason="the Secret names in the pod specs match the ExternalSecret "
                      "targets exactly and neither has changed in weeks",
    rationale="the Secret this workload mounts is created by the external-secrets "
              "operator, and the operator has been down since its store became "
              "unreachable; the workload's own spec is unchanged",
    remedy="Restore the external-secrets operator (fix its store credentials or "
           "endpoint) and let it sync; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/external-secrets (Deployment)",
        ("Secret store from the operator's view: unreachable\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      external-secrets-5d8c7b9f6-t4k2p   0/1  CrashLoopBackOff  "
         "7 restarts\n"
         "Last log:  secret store unreachable: giving up after 5 attempts"),
    ),
    healthy_origin_content=(
        "Secret store from the operator's view: reconciled\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      external-secrets-5d8c7b9f6-t4k2p   1/1  Running  0 restarts\n"
        "Last log:  reconciled 42 ExternalSecrets, 0 errors"
    ),
    origin_state=("unreachable", "reconciled"),
    origin_variants=(
        (("Secret store from the operator's view: unreachable\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      external-secrets-5d8c7b9f6-t4k2p   0/1  CrashLoopBackOff  "
          "7 restarts\n"
          "Last log:  secret store unreachable: giving up after 5 attempts"),
         ("Secret store from the operator's view: reconciled\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      external-secrets-5d8c7b9f6-t4k2p   1/1  Running  0 restarts\n"
          "Last log:  reconciled 42 ExternalSecrets, 0 errors")),
        (("the external-secrets operator reports its store unreachable\n"
          "the operator pod has crashed 7 times in 12m\n"
          "42 ExternalSecrets are in SecretSyncedError"),
         ("the external-secrets operator reports every ExternalSecret reconciled\n"
          "the operator pod has been Running for 9d\n"
          "0 ExternalSecrets are in error")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "external-secrets (store unreachable)"),
         ("Normal  Started  kubelet  Started container external-secrets (store "
          "reconciled)")),
        (("operator status: unreachable store\n"
          "ExternalSecrets in error: 42 of 42\n"
          "last successful sync: 14m ago"),
         ("operator status: reconciled\n"
          "ExternalSecrets in error: 0 of 42\n"
          "last successful sync: 20s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="CreateContainerConfigError",
            issue="CreateContainerConfigError",
            reason="container {container} could not build its environment",
            evidence="secret \"{name}-credentials\" not found",
            local_cause="this Deployment's own pod spec references a Secret whose "
                        "name was misspelled in its last rollout",
            local_reason="the envFrom entry names a Secret one letter off from the "
                         "one that exists in the namespace",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: secret \"{name}-credentials\" "
                  "not found")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CreateContainerConfigError",
            issue="Init:CreateContainerConfigError",
            reason="init container {init_container} could not build its environment",
            evidence="couldn't find key DB_PASSWORD in Secret {ns}/{name}-db",
            local_cause="this Job's own init container asks for a Secret key that its "
                        "chart renamed in the last release",
            local_reason="the init step reads DB_PASSWORD and the chart now writes "
                         "DATABASE_PASSWORD",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}: waiting, "
                  "CreateContainerConfigError\nEvents: Warning  Failed  kubelet  "
                  "Error: couldn't find key DB_PASSWORD in Secret")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="MountVolume.SetUp failed for volume \"tls\": secret "
                     "\"{name}-tls\" not found",
            local_cause="this StatefulSet's own TLS Secret was deleted by a cleanup "
                        "job that matched its label by mistake",
            local_reason="the cleanup job's selector matched the StatefulSet's Secret "
                         "label and removed it",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  FailedMount  kubelet  "
                  "MountVolume.SetUp failed for volume \"tls\": secret not found")),
            pass_confidence="high",
        ),
    ),
)

_T_NETWORK_OPERATOR_DOWN = Propagation(
    key="network-operator-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the network operator keeps being OOM-killed, so the pod overlay network "
           "is no longer reconciled",
    shared_cause="the network operator keeps being OOM-killed, so the pod overlay "
                 "network is no longer reconciled and pods on different nodes cannot "
                 "reach each other",
    shared_reason="kube-system/network-operator shows 0 of 1 replicas available with "
                  "its pod OOMKilled 5 times at its 512Mi limit, its last log says "
                  "the overlay reconcile halted, and cross-node pod traffic has been "
                  "failing since",
    distractor_cause="the workloads' own Services lost their endpoints in a rollout",
    distractor_reason="every Service involved lists its ready endpoints and the "
                      "endpoints answer from the same node; only cross-node calls "
                      "fail",
    rationale="cross-node pod traffic depends on the overlay the network operator "
              "reconciles, and the operator has been OOM-killed out of running; "
              "this workload's peers are on other nodes",
    remedy="Raise the network operator's memory limit (or fix the leak) so it stays "
           "Running and reconciles the overlay; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe kube-system/network-operator (Deployment)",
        ("Overlay reconcile from the operator's view: halted\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      network-operator-7b6d9c8f5-q2m8x   0/1  OOMKilled  5 restarts\n"
         "Last log:  overlay reconcile halted: killed at 512Mi"),
    ),
    healthy_origin_content=(
        "Overlay reconcile from the operator's view: idle\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      network-operator-7b6d9c8f5-q2m8x   1/1  Running  0 restarts\n"
        "Last log:  overlay reconcile idle: 3 nodes in sync"
    ),
    origin_state=("halted", "idle"),
    origin_variants=(
        (("Overlay reconcile from the operator's view: halted\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      network-operator-7b6d9c8f5-q2m8x   0/1  OOMKilled  5 restarts\n"
          "Last log:  overlay reconcile halted: killed at 512Mi"),
         ("Overlay reconcile from the operator's view: idle\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      network-operator-7b6d9c8f5-q2m8x   1/1  Running  0 restarts\n"
          "Last log:  overlay reconcile idle: 3 nodes in sync")),
        (("the network operator reports its overlay reconcile halted\n"
          "the operator pod was OOM-killed 5 times at its 512Mi limit\n"
          "cross-node pod traffic has failed for 15m"),
         ("the network operator reports its overlay reconcile idle\n"
          "the operator pod has been Running for 6d within its limit\n"
          "cross-node pod traffic flows normally")),
        (("Warning  OOMKilling  kubelet  Memory cgroup out of memory: killed process "
          "network-operator (overlay reconcile halted)"),
         ("Normal  Started  kubelet  Started container network-operator (overlay "
          "reconcile idle, 3 nodes in sync)")),
        (("overlay reconcile loop: halted\n"
          "nodes out of sync: 3 of 3\n"
          "operator OOM kills in the last hour: 5"),
         ("overlay reconcile loop: idle\n"
          "nodes out of sync: 0 of 3\n"
          "operator OOM kills in the last hour: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dependency check to a peer on another "
                     "node timed out",
            local_cause="this Deployment's own readiness check calls a peer address "
                        "that was retired in the last release",
            local_reason="the check dials a peer hostname that no Service publishes "
                         "any more",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: dependency "
                  "check timed out")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="cluster join failed: peer on another node unreachable after 30s",
            local_cause="this StatefulSet's own peer list still names a member that "
                        "was scaled away last week",
            local_reason="the join step waits on a member ordinal that no longer "
                         "exists",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: peer join timed out (3 of 3 sampled restarts)"),
            log_cause="peer join timed out",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="wait-for-db: dial tcp: i/o timeout reaching a pod on another "
                     "node",
            local_cause="this Job's own init container dials the database by a pod "
                        "IP it cached from a previous run",
            local_reason="the init step reads a stale address file instead of the "
                         "Service name",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init wait for the database timed out "
                  "(3 of 3 sampled restarts)")),
            log_cause="init wait for the database timed out",
            pass_confidence="high",
        ),
    ),
)

_T_CERT_MANAGER_DOWN = Propagation(
    key="cert-manager-down",
    blast_radius="cluster",
    scope_field=None,
    origin="cert-manager is down, so certificates near expiry are not renewed and "
           "the workloads serving them fail their TLS checks once they lapse",
    shared_cause="cert-manager is down, so certificates near expiry are not renewed "
                 "and the workloads serving them fail their TLS checks once they "
                 "lapse",
    shared_reason="cert-manager/cert-manager shows 0 of 1 replicas available with its "
                  "pod in CrashLoopBackOff after 11 restarts, its last log says it "
                  "lost its leader lease, and 9 Certificates have passed their "
                  "renewal time without a new Secret",
    distractor_cause="the workloads' own TLS Secrets were overwritten by a manual "
                     "kubectl apply",
    distractor_reason="the TLS Secrets carry the same serial they had a month ago and "
                      "no manual write is in the audit log",
    rationale="the certificate this workload serves is renewed by cert-manager, and "
              "cert-manager has been down past the renewal window; the workload's "
              "own config is unchanged",
    remedy="Restore cert-manager (let it reacquire its leader lease) and let it renew "
           "the lapsed Certificates; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe cert-manager/cert-manager (Deployment)",
        ("Leader lease from the controller's view: lost\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      cert-manager-6f9b8d7c5-w7r3n   0/1  CrashLoopBackOff  "
         "11 restarts\n"
         "Last log:  lost leader lease, exiting"),
    ),
    healthy_origin_content=(
        "Leader lease from the controller's view: holding\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      cert-manager-6f9b8d7c5-w7r3n   1/1  Running  0 restarts\n"
        "Last log:  holding leader lease, 0 certificates pending"
    ),
    origin_state=("lost", "holding"),
    origin_variants=(
        (("Leader lease from the controller's view: lost\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      cert-manager-6f9b8d7c5-w7r3n   0/1  CrashLoopBackOff  "
          "11 restarts\n"
          "Last log:  lost leader lease, exiting"),
         ("Leader lease from the controller's view: holding\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      cert-manager-6f9b8d7c5-w7r3n   1/1  Running  0 restarts\n"
          "Last log:  holding leader lease, 0 certificates pending")),
        (("cert-manager reports its leader lease lost\n"
          "the controller pod has crashed 11 times in 40m\n"
          "9 Certificates are past their renewal time"),
         ("cert-manager reports it is holding its leader lease\n"
          "the controller pod has been Running for 12d\n"
          "0 Certificates are past their renewal time")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "cert-manager (leader lease lost)"),
         ("Normal  Started  kubelet  Started container cert-manager (holding leader "
          "lease)")),
        (("controller lease: lost\n"
          "Certificates past renewal: 9 of 31\n"
          "last renewal issued: 3h ago"),
         ("controller lease: holding\n"
          "Certificates past renewal: 0 of 31\n"
          "last renewal issued: 6m ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: tls: certificate has expired",
            local_cause="this Deployment's own probe pins a CA bundle that was "
                        "rotated out of the trust store last quarter",
            local_reason="the probe's CA file is a copy from before the routine "
                         "rotation and no longer validates anything",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: tls: "
                  "certificate has expired")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="tls: failed to load server certificate: certificate has expired",
            local_cause="this StatefulSet's own server certificate is self-signed "
                        "with a one-year validity nobody tracked",
            local_reason="the certificate was generated by hand a year ago and never "
                         "enrolled for renewal",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: server certificate expired "
                  "(3 of 3 sampled restarts)")),
            log_cause="server certificate expired",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="metrics push failed: x509: certificate has expired or is not "
                     "yet valid",
            local_cause="this agent's own client certificate is issued by a private "
                        "CA outside the cluster with a lapsed intermediate",
            local_reason="the agent's certificate chains to an intermediate that "
                         "expired last night",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: client certificate rejected as expired "
                  "(3 of 3 sampled restarts)")),
            log_cause="client certificate rejected as expired",
            pass_confidence="high",
        ),
    ),
)

_T_METRICS_SERVER_DOWN = Propagation(
    key="metrics-server-down",
    blast_radius="cluster",
    scope_field=None,
    origin="metrics-server is down, so every autoscaler is frozen at its last size",
    shared_cause="metrics-server is down, so every autoscaler is frozen at its last "
                 "size and overloaded pods are not scaled out",
    shared_reason="kube-system/metrics-server shows 0 of 1 replicas available with "
                  "its pod in CrashLoopBackOff after 8 restarts, its last log says "
                  "node metric scrapes time out, and every HorizontalPodAutoscaler "
                  "reports FailedGetResourceMetric",
    distractor_cause="the workloads' own autoscalers were deleted in the last chart "
                     "release",
    distractor_reason="every HorizontalPodAutoscaler is present and its target "
                      "reference is unchanged; each one reports it cannot read "
                      "metrics",
    rationale="this workload is overloaded because its autoscaler cannot read "
              "metrics, and it cannot read them because metrics-server is down; "
              "the same is true of every autoscaled workload",
    remedy="Restore kube-system/metrics-server (fix its kubelet scrape timeout) and "
           "let the autoscalers resume; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/metrics-server (Deployment)",
        ("Node metrics from the server's view: unable to fetch\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      metrics-server-8c7d6b9f4-h5n2k   0/1  CrashLoopBackOff  "
         "8 restarts\n"
         "Last log:  unable to fetch node metrics: scrape timeout"),
    ),
    healthy_origin_content=(
        "Node metrics from the server's view: scraped\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      metrics-server-8c7d6b9f4-h5n2k   1/1  Running  0 restarts\n"
        "Last log:  scraped 3 nodes, 41 pods"
    ),
    origin_state=("unable", "scraped"),
    origin_variants=(
        (("Node metrics from the server's view: unable to fetch\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      metrics-server-8c7d6b9f4-h5n2k   0/1  CrashLoopBackOff  "
          "8 restarts\n"
          "Last log:  unable to fetch node metrics: scrape timeout"),
         ("Node metrics from the server's view: scraped\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      metrics-server-8c7d6b9f4-h5n2k   1/1  Running  0 restarts\n"
          "Last log:  scraped 3 nodes, 41 pods")),
        (("metrics-server reports it is unable to fetch node metrics\n"
          "the server pod has crashed 8 times in 25m\n"
          "every HorizontalPodAutoscaler reports FailedGetResourceMetric"),
         ("metrics-server reports it scraped every node\n"
          "the server pod has been Running for 20d\n"
          "every HorizontalPodAutoscaler reads its metrics normally")),
        (("Warning  FailedGetResourceMetric  horizontal-pod-autoscaler  unable to "
          "fetch metrics from resource metrics API"),
         ("Normal  SuccessfulRescale  horizontal-pod-autoscaler  metrics scraped, "
          "New size: 4; reason: cpu resource utilization above target")),
        (("metrics API: unable to serve\n"
          "autoscalers frozen: 17 of 17\n"
          "last successful scrape: 25m ago"),
         ("metrics API: scraped and serving\n"
          "autoscalers frozen: 0 of 17\n"
          "last successful scrape: 15s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503 "
                     "(overloaded, queue depth 4000)",
            local_cause="this Deployment's own request queue is unbounded and a "
                        "single slow client can fill it",
            local_reason="the queue has no cap and one client is holding 4000 "
                         "requests open",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="OOMKilled",
            issue="OOMKilled",
            reason="container {container} was killed by the kernel out-of-memory "
                   "handler",
            evidence="container exceeded its memory limit under load that would have "
                     "been spread across more replicas",
            local_cause="this StatefulSet's own in-memory index doubles on every "
                        "compaction and never releases the old copy",
            local_reason="the index keeps both copies after compaction and grows "
                         "until the kernel kills it",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: memory limit exceeded under load "
                  "(3 of 3 sampled restarts)")),
            log_cause="memory limit exceeded under load",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="scrape target overloaded: collector restarted after 30s of "
                     "backpressure",
            local_cause="this agent's own scrape interval was set to one second in "
                        "its last config push",
            local_reason="the agent scrapes every target every second and restarts "
                         "when its buffer fills",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: collector restarted under backpressure "
                  "(3 of 3 sampled restarts)")),
            log_cause="collector restarted under backpressure",
            pass_confidence="high",
        ),
    ),
)


_T_SHARED_NFS_SERVER_DOWN = Propagation(
    key="shared-nfs-server-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the shared NFS server is down, so every pod that mounts a volume from "
           "it is stuck at mount",
    shared_cause="the shared NFS server is down, so every pod that mounts a volume "
                 "from it is stuck at mount",
    shared_reason="9 pods across 4 namespaces report the same FailedMount error, "
                  "mount.nfs timed out, and every one of them names the same NFS "
                  "server; that server has answered no mount in 20m",
    distractor_cause="the workloads' own volume specs were rewritten to the wrong "
                     "export path in the last chart release",
    distractor_reason="the export paths in the failing pods' specs match what the "
                      "server published last week, and the error is a timeout, not "
                      "a missing export",
    rationale="this workload's volume is served by the shared NFS server, and that "
              "server has stopped answering mounts for every pod that uses it; the "
              "workload's own volume spec is unchanged",
    remedy="Bring the shared NFS server back (or fail over to its replica) and let "
           "the kubelets retry their mounts; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedMount)",
        ("NFS mount failures across the cluster: timed out against one server\n"
         "9 pods across 4 namespaces report the same error:\n"
         "  MountVolume.SetUp failed: mount.nfs: Connection timed out\n"
         "distinct NFS servers in the failing set: 1"),
    ),
    healthy_origin_content=(
        "NFS mount failures across the cluster: one per failing pod, no server in "
        "common\n"
        "pods reporting a mount error name no NFS server in common, and\n"
        "no two of them fail the same way: wrong fs type, permission denied,\n"
        "no such export\n"
        "distinct NFS servers in the failing set: one per failing pod"
    ),
    origin_state=("timed out", "one per failing pod"),
    origin_variants=(
        (("NFS mount failures across the cluster: timed out against one server\n"
          "9 pods across 4 namespaces report the same error:\n"
          "  MountVolume.SetUp failed: mount.nfs: Connection timed out\n"
          "distinct NFS servers in the failing set: 1"),
         ("NFS mount failures across the cluster: one per failing pod, no server in "
          "common\n"
          "pods reporting a mount error name no NFS server in common, and\n"
          "no two of them fail the same way: wrong fs type, permission denied,\n"
          "no such export\n"
          "distinct NFS servers in the failing set: one per failing pod")),
        (("every FailedMount event in the last 20m names the same NFS server\n"
          "each of the 9 mounts timed out after 30s\n"
          "the server has answered no mount request since the failures began"),
         ("the FailedMount events in the last 20m name a different server each: "
          "one per failing pod\n"
          "each mount fails for its own reason: a wrong fs type, a denied "
          "permission, a missing export\n"
          "every named server answers mount requests")),
        (("Warning  FailedMount  kubelet  MountVolume.SetUp failed: mount.nfs: "
          "Connection timed out (same server for 9 of 9 failing pods)"),
         ("Warning  FailedMount  kubelet  MountVolume.SetUp failed: mount.nfs: no "
          "such export (servers named: one per failing pod)")),
        (("NFS server in common across failing mounts: 1\n"
          "mount outcome for every pod that uses it: timed out\n"
          "failing pods: 9 in 4 namespaces"),
         ("NFS server in common across failing mounts: 0, one per failing pod\n"
          "mount outcome: a different error for each pod\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.SetUp failed for volume \"{pvc}\": mount.nfs: "
                     "mount failed",
            local_cause="this Deployment's own volume names an NFS export path that "
                        "was renamed on the server last week",
            local_reason="the pod spec still mounts the old export path and the "
                         "server now publishes it under a new name",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.SetUp failed for volume "
                  "\"{pvc}\": mount.nfs: mount failed")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the NFS CSI "
                     "node plugin reported the attach as failed",
            local_cause="this StatefulSet's own volume attachment is pinned to a "
                        "node that was rebuilt without the NFS client package",
            local_reason="the attachment names a node whose image lost the NFS "
                         "client in the last rebuild",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: mount source for the agent's "
                     "shared volume is not ready",
            local_cause="this agent's own hostPath mount points at a directory the "
                        "node image no longer ships",
            local_reason="the DaemonSet mounts a host directory that the last node "
                         "image dropped",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container \"{container}\": mount source not ready")),
            pass_confidence="high",
        ),
    ),
)

_T_CLUSTER_MAINTENANCE_TAINT = Propagation(
    key="cluster-maintenance-taint",
    blast_radius="cluster",
    scope_field=None,
    origin="every node carries a maintenance taint no workload tolerates, so no new "
           "pod can be scheduled anywhere",
    shared_cause="every node carries a maintenance taint no workload tolerates, so "
                 "no new pod can be scheduled anywhere",
    shared_reason="12 pods across 5 namespaces report the same FailedScheduling "
                  "error, 0/3 nodes available because all 3 carry an untolerated "
                  "maintenance taint, and no pending pod has tolerated it",
    distractor_cause="the workloads' own tolerations were dropped in the last chart "
                     "release",
    distractor_reason="the pending pods never carried a toleration for this taint, "
                      "because the taint did not exist before the maintenance "
                      "window opened",
    rationale="this workload cannot be scheduled because every node carries the "
              "maintenance taint, and no pod in the cluster can be scheduled for "
              "the same reason; the workload's own spec is unchanged",
    remedy="Remove the maintenance taint from the nodes once the window closes (or "
           "untaint one node now); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedScheduling)",
        ("Untolerated taint across the cluster: maintenance, on every node\n"
         "12 pods across 5 namespaces report the same error:\n"
         "  0/3 nodes are available: 3 node(s) had untolerated taint "
         "{{maintenance: true}}\n"
         "distinct taints in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Untolerated taint across the cluster: none\n"
        "pods reporting a scheduling failure name no taint in common, and\n"
        "no two of them fail the same way: insufficient cpu, node affinity "
        "mismatch,\n"
        "unbound claim\n"
        "distinct taints in the failing set: none"
    ),
    origin_state=("maintenance", "none"),
    origin_variants=(
        (("Untolerated taint across the cluster: maintenance, on every node\n"
          "12 pods across 5 namespaces report the same error:\n"
          "  0/3 nodes are available: 3 node(s) had untolerated taint "
          "{{maintenance: true}}\n"
          "distinct taints in the failing set: 1"),
         ("Untolerated taint across the cluster: none\n"
          "pods reporting a scheduling failure name no taint in common, and\n"
          "no two of them fail the same way: insufficient cpu, node affinity "
          "mismatch,\n"
          "unbound claim\n"
          "distinct taints in the failing set: none")),
        (("every FailedScheduling event in the last 20m names the maintenance "
          "taint\n"
          "all 3 nodes carry it and no pending pod tolerates it\n"
          "pods pending on it: 12 in 5 namespaces"),
         ("the FailedScheduling events in the last 20m name a taint in common: "
          "none\n"
          "each pending pod waits for its own reason: cpu, affinity, a claim\n"
          "pods pending: 3 in 3 namespaces")),
        (("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "3 node(s) had an untolerated maintenance taint (12 of 12 pending pods)"),
         ("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "1 Insufficient cpu, 2 node(s) didn't match affinity (shared taint: "
          "none)")),
        (("taint shared by every pending pod: maintenance\n"
          "nodes carrying it: 3 of 3\n"
          "pending pods that tolerate it: 0 of 12"),
         ("taint shared by every pending pod: none\n"
          "nodes carrying an untolerated taint: 0 of 3\n"
          "pending pods: 3, each for its own reason")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this Deployment's own required node affinity names an "
                        "instance type the pool no longer has",
            local_reason="the affinity rule asks for a node label no node in the "
                         "pool carries since the last resize",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: no node fits this pod")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this StatefulSet's own pod anti-affinity forbids two "
                        "replicas per node and it now asks for more replicas than "
                        "there are nodes",
            local_reason="the anti-affinity rule leaves no node for the fourth "
                         "replica of a three-node cluster",
            read=("describe {ns}/{pod} (Pod)",
                  ("Status: Pending\nEvents: Warning  FailedScheduling  "
                  "default-scheduler  0/3 nodes are available: no node fits this "
                  "pod")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this Job's own resource request asks for a GPU that no node "
                        "in the cluster has",
            local_reason="the pod requests one GPU and the cluster has no GPU node",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: no node fits this pod")),
            pass_confidence="high",
        ),
    ),
)

_T_SHARED_GATEWAY_REFUSING = Propagation(
    key="shared-gateway-refusing",
    blast_radius="cluster",
    scope_field=None,
    origin="the shared API gateway refuses connections, so every pod whose readiness "
           "check calls through it fails its probe",
    shared_cause="the shared API gateway refuses connections, so every pod whose "
                 "readiness check calls through it fails its probe",
    shared_reason="14 pods across 6 namespaces report the same Unhealthy error, "
                  "readiness probe failed because the API gateway refused the "
                  "connection, and every one of them names the same gateway",
    distractor_cause="the workloads' own readiness probes were pointed at the wrong "
                     "path in the last rollout",
    distractor_reason="the probe paths are unchanged and answer when called "
                      "directly; only the hop through the gateway fails",
    rationale="this workload's readiness check calls through the shared API "
              "gateway, and the gateway is refusing every connection; the "
              "workload's own probe is unchanged",
    remedy="Restore the shared API gateway (restart it or roll back its last "
           "config) and let the probes pass; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=Unhealthy)",
        ("Gateway named by failing readiness probes: one, and it refused every "
         "call\n"
         "14 pods across 6 namespaces report the same error:\n"
         "  Readiness probe failed: API gateway: connection refused\n"
         "distinct gateways in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Gateway named by failing readiness probes: one per failing pod\n"
        "pods reporting a readiness failure name no gateway in common, and\n"
        "no two of them fail the same way: HTTP 500, timeout, missing path\n"
        "distinct gateways in the failing set: one per failing pod"
    ),
    origin_state=("refused", "one per failing pod"),
    origin_variants=(
        (("Gateway named by failing readiness probes: one, and it refused every "
          "call\n"
          "14 pods across 6 namespaces report the same error:\n"
          "  Readiness probe failed: API gateway: connection refused\n"
          "distinct gateways in the failing set: 1"),
         ("Gateway named by failing readiness probes: one per failing pod\n"
          "pods reporting a readiness failure name no gateway in common, and\n"
          "no two of them fail the same way: HTTP 500, timeout, missing path\n"
          "distinct gateways in the failing set: one per failing pod")),
        (("every Unhealthy event in the last 20m names the same API gateway\n"
          "the gateway refused all 14 probe calls\n"
          "the gateway's own listener has accepted nothing since"),
         ("the Unhealthy events in the last 20m name a different gateway each: "
          "one per failing pod\n"
          "each probe fails for its own reason: a 500, a timeout, a missing path\n"
          "every named gateway accepts connections")),
        (("Warning  Unhealthy  kubelet  Readiness probe failed: API gateway: "
          "connection refused (same gateway for 14 of 14 failing pods)"),
         ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed "
          "with statuscode: 500 (gateways named: one per failing pod)")),
        (("API gateway in common across failing probes: 1\n"
          "outcome of every probe call through it: refused\n"
          "failing pods: 14 in 6 namespaces"),
         ("API gateway in common across failing probes: 0, one per failing pod\n"
          "outcome: a different error for each pod\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this Deployment's own readiness path was renamed in its "
                        "last image and the probe still calls the old one",
            local_reason="the probe asks for a path the new image answers with 404 "
                         "and the handler reports that as not ready",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dependency check did not pass",
            local_cause="this StatefulSet's own readiness check calls a sidecar that "
                        "its last rollout removed from the pod",
            local_reason="the check dials a sidecar port that nothing in the pod "
                         "listens on any more",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nReady: False\nEvents: Warning  Unhealthy  kubelet  "
                  "Readiness probe failed: dependency check did not pass")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="first outbound call failed on start, exiting",
            local_cause="this Job's own container exits on its first failed outbound call "
                        "because its retry budget is set to zero",
            local_reason="the retry count is 0, so one failed call ends the process",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: first outbound call failed on start "
                  "(3 of 3 sampled restarts)")),
            log_cause="first outbound call failed on start",
            pass_confidence="high",
        ),
    ),
)

_T_RUNTIME_CLASS_REMOVED = Propagation(
    key="runtime-class-removed",
    blast_radius="cluster",
    scope_field=None,
    origin="the sandboxed RuntimeClass handler was removed from the nodes, so every "
           "pod that asks for it fails to create its sandbox",
    shared_cause="the sandboxed RuntimeClass handler was removed from the nodes, so "
                 "every pod that asks for it fails to create its sandbox",
    shared_reason="8 pods across 4 namespaces report the same FailedCreatePodSandBox "
                  "error, no runtime for the sandboxed handler is configured, and "
                  "every one of them asks for that one handler",
    distractor_cause="the workloads' own pod specs gained a runtimeClassName in the "
                     "last chart release",
    distractor_reason="the failing pods have asked for the sandboxed class for "
                      "months and ran fine until the node runtime config changed",
    rationale="this workload asks for the sandboxed RuntimeClass, and the nodes no "
              "longer have a handler for it; every pod that asks for the same "
              "class fails the same way and the workload's own spec is unchanged",
    remedy="Restore the sandboxed handler in the container runtime config on every "
           "node (or roll back the runtime config change); the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedCreatePodSandBox)",
        ("Sandbox handler across the cluster: no runtime for the sandboxed class\n"
         "8 pods across 4 namespaces report the same error:\n"
         "  Failed to create pod sandbox: no runtime for \"sandboxed\" is "
         "configured\n"
         "distinct runtime handlers in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Sandbox handler across the cluster: one per failing pod\n"
        "pods reporting a sandbox failure name no handler in common, and\n"
        "no two of them fail the same way: cgroup limit, seccomp profile "
        "missing,\n"
        "hostPort in use\n"
        "distinct runtime handlers in the failing set: one per failing pod"
    ),
    origin_state=("no runtime", "one per failing pod"),
    origin_variants=(
        (("Sandbox handler across the cluster: no runtime for the sandboxed class\n"
          "8 pods across 4 namespaces report the same error:\n"
          "  Failed to create pod sandbox: no runtime for \"sandboxed\" is "
          "configured\n"
          "distinct runtime handlers in the failing set: 1"),
         ("Sandbox handler across the cluster: one per failing pod\n"
          "pods reporting a sandbox failure name no handler in common, and\n"
          "no two of them fail the same way: cgroup limit, seccomp profile "
          "missing,\n"
          "hostPort in use\n"
          "distinct runtime handlers in the failing set: one per failing pod")),
        (("every FailedCreatePodSandBox event in the last 20m names the sandboxed "
          "handler\n"
          "the nodes report no runtime configured for it since the last runtime "
          "config push\n"
          "pods failing on it: 8 in 4 namespaces"),
         ("the FailedCreatePodSandBox events in the last 20m name a handler in "
          "common: none, one per failing pod\n"
          "each sandbox fails for its own reason: a cgroup limit, a missing "
          "seccomp profile, a busy hostPort\n"
          "every handler the nodes list is configured")),
        (("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
          "no runtime for \"sandboxed\" is configured (8 of 8 failing pods)"),
         ("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
          "hostPort 8080 already in use (handlers named: one per failing pod)")),
        (("runtime handler in common across failing sandboxes: 1, sandboxed\n"
          "handler state on the nodes: no runtime configured\n"
          "failing pods: 8 in 4 namespaces"),
         ("runtime handler in common across failing sandboxes: 0, one per failing "
          "pod\n"
          "handler state on the nodes: every listed handler configured\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this Deployment's own pod spec asks for a seccomp profile "
                        "the node image never shipped",
            local_reason="the securityContext names a localhost seccomp profile "
                         "that no node has on disk",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod "
                  "sandbox: sandbox creation failed")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this StatefulSet's own container requests a hostPort that "
                        "another pod on every node already holds",
            local_reason="the hostPort it asks for is taken on each node by a "
                         "DaemonSet that arrived last week",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nRuntimeClassName: sandboxed\nEvents: Warning  "
                  "FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
                  "sandbox creation failed")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this Job's own pod spec sets a cgroup parent that does not "
                        "exist on the nodes",
            local_reason="the pod asks for a cgroup parent path the nodes' cgroup "
                         "tree does not contain",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod "
                  "sandbox: sandbox creation failed")),
            pass_confidence="high",
        ),
    ),
)

_T_CSI_CONTROLLER_OOMKILLED = Propagation(
    key="csi-controller-oomkilled",
    blast_radius="cluster",
    scope_field=None,
    origin="the block-ssd CSI controller is OOM-killed on every start, so no claim "
           "on that class gets a volume",
    shared_cause="the block-ssd CSI controller is OOM-killed on every start, so no "
                 "claim on that class gets a volume",
    shared_reason="storage-system/block-ssd-csi-controller shows 0 of 2 ready with "
                  "both pods OOMKilled, its last restart 40s ago with exit 137, and "
                  "0 PersistentVolumes have bound on block-ssd in the last 20m",
    distractor_cause="the workloads' own claims were recreated with the wrong access "
                     "mode in the last chart release",
    distractor_reason="the claims ask for the same access mode they always did and "
                      "the class supports it; the provisioner has simply not "
                      "answered any of them",
    rationale="this workload's claim is on the block-ssd class, and that class's "
              "controller is OOM-killed before it can provision anything; the "
              "workload's own claim is unchanged",
    remedy="Raise the block-ssd CSI controller's memory limit (or fix its leak) so "
           "it stays up and provisions; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass block-ssd",
        ("block-ssd controller state: OOMKilled on every start\n"
         "provisioner: example.com/block-ssd-csi\n"
         "controller storage-system/block-ssd-csi-controller: 0/2 ready, OOMKilled\n"
         "last restart: 40s ago, exit 137\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "block-ssd controller state: Running\n"
        "provisioner: example.com/block-ssd-csi\n"
        "controller storage-system/block-ssd-csi-controller: 2/2 ready, Running\n"
        "last restart: none in 7d\n"
        "PersistentVolumes bound in the last 20m: 5"
    ),
    origin_state=("OOMKilled", "Running"),
    origin_variants=(
        (("block-ssd controller state: OOMKilled on every start\n"
          "provisioner: example.com/block-ssd-csi\n"
          "controller storage-system/block-ssd-csi-controller: 0/2 ready, "
          "OOMKilled\n"
          "last restart: 40s ago, exit 137\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("block-ssd controller state: Running\n"
          "provisioner: example.com/block-ssd-csi\n"
          "controller storage-system/block-ssd-csi-controller: 2/2 ready, Running\n"
          "last restart: none in 7d\n"
          "PersistentVolumes bound in the last 20m: 5")),
        (("the block-ssd CSI controller is OOMKilled at its 256Mi limit on every "
          "start\n"
          "both controller pods have exit 137 in their last termination\n"
          "no block-ssd claim has bound in 20m"),
         ("the block-ssd CSI controller has been Running within its limit for 7d\n"
          "both controller pods report 0 restarts\n"
          "5 block-ssd claims bound in the last 20m")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "block-ssd-csi-controller (OOMKilled, exit 137)"),
         ("Normal  Started  kubelet  Started container block-ssd-csi-controller "
          "(Running, 2 of 2 ready)")),
        (("class block-ssd provisioner health: OOMKilled\n"
          "controller pods ready: 0 of 2\n"
          "claims waiting on this class: 5, bound in 20m: 0"),
         ("class block-ssd provisioner health: Running\n"
          "controller pods ready: 2 of 2\n"
          "claims waiting on this class: 0, bound in 20m: 5")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim asks for a storage class name "
                        "with a typo, so no provisioner picks it up",
            local_reason="the claim names a class one letter off from any class in "
                         "the cluster",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this StatefulSet's own volumeClaimTemplate asks for 10 TiB, "
                        "more than the class's per-volume cap",
            local_reason="the template requests a size the class will never "
                         "provision",
            read=("describe {ns}/{pod} (Pod)",
                  ("Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.MountDevice failed for volume \"{pvc}\": the "
                     "controller has not published the volume",
            local_cause="this Job's own pod mounts the same claim twice with "
                        "conflicting mount options",
            local_reason="two volumeMounts name the same claim, one read-only and "
                         "one read-write, and the second mount fails",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.MountDevice failed for volume "
                  "\"{pvc}\": mount failed")),
            pass_confidence="high",
        ),
    ),
)

_T_CSI_CONTROLLER_UNSCHEDULABLE = Propagation(
    key="csi-controller-unschedulable",
    blast_radius="cluster",
    scope_field=None,
    origin="the archive-hdd CSI controller cannot be scheduled, so claims on that "
           "class are never provisioned",
    shared_cause="the archive-hdd CSI controller cannot be scheduled, so claims on "
                 "that class are never provisioned",
    shared_reason="storage-system/archive-hdd-csi-controller shows 0 of 1 ready and "
                  "Pending because its node selector storage-tier=archive matches "
                  "no node, and 0 PersistentVolumes have bound on archive-hdd in "
                  "the last 20m",
    distractor_cause="the workloads' own claim templates were switched to a class "
                     "name with a typo in the last chart release",
    distractor_reason="the claims name archive-hdd exactly and the class exists; "
                      "its controller has no node to run on",
    rationale="this workload's claim is on the archive-hdd class, and that class's "
              "controller is Pending with no node matching its selector, so "
              "nothing on the class is provisioned; the workload's own claim is "
              "unchanged",
    remedy="Label a node storage-tier=archive (or fix the controller's node "
           "selector) so the archive-hdd controller can run; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass archive-hdd",
        ("archive-hdd controller placement: its node selector matches no node\n"
         "provisioner: example.com/archive-hdd-csi\n"
         "controller storage-system/archive-hdd-csi-controller: 0/1 ready, Pending "
         "(node selector matches no node)\n"
         "node selector: storage-tier=archive\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "archive-hdd controller placement: Running on its archive node\n"
        "provisioner: example.com/archive-hdd-csi\n"
        "controller storage-system/archive-hdd-csi-controller: 1/1 ready, Running\n"
        "node selector: storage-tier=archive (1 node)\n"
        "PersistentVolumes bound in the last 20m: 3"
    ),
    origin_state=("matches no node", "Running"),
    origin_variants=(
        (("archive-hdd controller placement: its node selector matches no node\n"
          "provisioner: example.com/archive-hdd-csi\n"
          "controller storage-system/archive-hdd-csi-controller: 0/1 ready, "
          "Pending (node selector matches no node)\n"
          "node selector: storage-tier=archive\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("archive-hdd controller placement: Running on its archive node\n"
          "provisioner: example.com/archive-hdd-csi\n"
          "controller storage-system/archive-hdd-csi-controller: 1/1 ready, "
          "Running\n"
          "node selector: storage-tier=archive (1 node)\n"
          "PersistentVolumes bound in the last 20m: 3")),
        (("the archive-hdd CSI controller is Pending because its node selector "
          "matches no node\n"
          "the label storage-tier=archive is on 0 of 3 nodes since the last node "
          "pool rollout\n"
          "no archive-hdd claim has bound in 20m"),
         ("the archive-hdd CSI controller is Running on the node labelled "
          "storage-tier=archive\n"
          "the label is on 1 of 3 nodes\n"
          "3 archive-hdd claims bound in the last 20m")),
        (("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "3 node(s) didn't match Pod's node affinity/selector "
          "(archive-hdd-csi-controller: selector matches no node)"),
         ("Normal  Scheduled  default-scheduler  Successfully assigned "
          "storage-system/archive-hdd-csi-controller to the archive node "
          "(Running)")),
        (("class archive-hdd provisioner placement: matches no node\n"
          "controller pods ready: 0 of 1\n"
          "claims waiting on this class: 3, bound in 20m: 0"),
         ("class archive-hdd provisioner placement: Running, 1 node matched\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 0, bound in 20m: 3")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim pins a volume by name that "
                        "another claim already holds",
            local_reason="the claim's volumeName points at a PersistentVolume bound "
                         "to a different claim",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Job's own claim asks for ReadWriteMany on a class that "
                        "only offers ReadWriteOnce",
            local_reason="the claim's access mode is one the class cannot provide",
            read=("describe {ns}/{pod} (Pod)",
                  ("Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="init step waited 120s for its data volume and gave up",
            local_cause="this StatefulSet's own init container polls a volume path "
                        "that its last chart release renamed, so it never sees the "
                        "disk that is mounted",
            local_reason="the init step waits on a path the chart no longer mounts "
                         "the disk at",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init step gave up waiting for its data volume "
                  "(3 of 3 sampled restarts)")),
            log_cause="init step gave up waiting for its data volume",
            pass_confidence="high",
        ),
    ),
)

_T_PROVISIONER_CREDENTIALS_ROTATED = Propagation(
    key="provisioner-credentials-rotated",
    blast_radius="cluster",
    scope_field=None,
    origin="the encrypted-ssd provisioner's backend credentials were rotated, so the "
           "backend refuses every new volume request",
    shared_cause="the encrypted-ssd provisioner's backend credentials were rotated, "
                 "so the backend refuses every new volume request",
    shared_reason="storage-system/encrypted-ssd-csi-controller is 1 of 1 ready, but "
                  "its last provision error says the backend refused credentials "
                  "(401), and 0 PersistentVolumes have bound on encrypted-ssd in "
                  "the last 20m",
    distractor_cause="the workloads' own service accounts lost the storage role in "
                     "the last RBAC change",
    distractor_reason="claims need no service account role to bind, and the refusal "
                      "comes from the storage backend, not the API server",
    rationale="this workload's claim is on the encrypted-ssd class, and that "
              "class's backend refuses the provisioner's credentials, so no claim "
              "on it binds; the workload's own claim is unchanged",
    remedy="Update the encrypted-ssd provisioner's backend secret with the rotated "
           "credentials and restart it; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass encrypted-ssd",
        ("encrypted-ssd backend provision errors: refused credentials on every "
         "call\n"
         "provisioner: example.com/encrypted-ssd-csi\n"
         "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
         "Running\n"
         "last provision error: backend refused credentials (401)\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "encrypted-ssd backend provision errors: none\n"
        "provisioner: example.com/encrypted-ssd-csi\n"
        "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
        "Running\n"
        "last provision error: none\n"
        "PersistentVolumes bound in the last 20m: 6"
    ),
    origin_state=("refused credentials", "none"),
    origin_variants=(
        (("encrypted-ssd backend provision errors: refused credentials on every "
          "call\n"
          "provisioner: example.com/encrypted-ssd-csi\n"
          "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "last provision error: backend refused credentials (401)\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("encrypted-ssd backend provision errors: none\n"
          "provisioner: example.com/encrypted-ssd-csi\n"
          "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "last provision error: none\n"
          "PersistentVolumes bound in the last 20m: 6")),
        (("the encrypted-ssd controller is up but its backend has refused "
          "credentials on all 6 provision calls in 20m\n"
          "the backend rotated its access credentials overnight and the provisioner still "
          "holds the old ones\n"
          "no encrypted-ssd claim has bound since"),
         ("the encrypted-ssd controller is up and its backend accepted all 6 "
          "provision calls in 20m\n"
          "provision errors in that window: none\n"
          "6 encrypted-ssd claims bound in the last 20m")),
        (("Warning  ProvisioningFailed  example.com/encrypted-ssd-csi  failed to "
          "provision volume: backend refused credentials (401)"),
         ("Normal  ProvisioningSucceeded  example.com/encrypted-ssd-csi  "
          "Successfully provisioned volume (errors in 20m: none)")),
        (("class encrypted-ssd backend auth: refused credentials\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 6, bound in 20m: 0"),
         ("class encrypted-ssd backend auth: accepted, errors none\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 0, bound in 20m: 6")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim was created in the wrong "
                        "namespace by its chart, so the pod never finds it",
            local_reason="the chart rendered the claim into a different namespace "
                         "than the Deployment",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this StatefulSet's own claim template sets a selector that "
                        "no PersistentVolume label matches",
            local_reason="the template's selector asks for a volume label nothing "
                         "in the cluster carries",
            read=("describe {ns}/{pod} (Pod)",
                  ("Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the backend "
                     "did not complete the attach",
            local_cause="this Job's own claim is bound to a volume still attached to "
                        "a node that was deleted without detaching",
            local_reason="the volume's attachment record names a node that no "
                         "longer exists",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed")),
            pass_confidence="high",
        ),
    ),
)

_T_STORAGE_BACKEND_FULL = Propagation(
    key="storage-backend-full",
    blast_radius="cluster",
    scope_field=None,
    origin="the bulk-nvme storage backend is out of space, so the provisioner cannot "
           "carve a new volume for any claim on that class",
    shared_cause="the bulk-nvme storage backend is out of space, so the provisioner "
                 "cannot carve a new volume for any claim on that class",
    shared_reason="storage-system/bulk-nvme-csi-controller is 1 of 1 ready, but the "
                  "backend reports out of space with 0 GiB free of 4 TiB, and 0 "
                  "PersistentVolumes have bound on bulk-nvme in the last 20m",
    distractor_cause="the workloads' own claims ask for more space than their "
                     "namespace quota allows",
    distractor_reason="every namespace involved has quota to spare, and the claims "
                      "were admitted; the backend has no space to fill them",
    rationale="this workload's claim is on the bulk-nvme class, and that class's "
              "backend has no free space to provision from; the workload's own "
              "claim is unchanged",
    remedy="Free or add capacity on the bulk-nvme backend (delete released volumes "
           "or extend the pool); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass bulk-nvme",
        ("bulk-nvme backend: out of space\n"
         "provisioner: example.com/bulk-nvme-csi\n"
         "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
         "backend capacity: out of space (0 GiB free of 4 TiB)\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "bulk-nvme backend: space remaining\n"
        "provisioner: example.com/bulk-nvme-csi\n"
        "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
        "backend capacity: space remaining 1.9 TiB of 4 TiB\n"
        "PersistentVolumes bound in the last 20m: 4"
    ),
    origin_state=("out of space", "space remaining"),
    origin_variants=(
        (("bulk-nvme backend: out of space\n"
          "provisioner: example.com/bulk-nvme-csi\n"
          "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
          "backend capacity: out of space (0 GiB free of 4 TiB)\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("bulk-nvme backend: space remaining\n"
          "provisioner: example.com/bulk-nvme-csi\n"
          "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
          "backend capacity: space remaining 1.9 TiB of 4 TiB\n"
          "PersistentVolumes bound in the last 20m: 4")),
        (("the bulk-nvme backend is out of space: 0 GiB free of 4 TiB\n"
          "the controller is up and every provision call fails on capacity\n"
          "no bulk-nvme claim has bound in 20m"),
         ("the bulk-nvme backend has space remaining: 1.9 TiB free of 4 TiB\n"
          "the controller is up and every provision call in 20m succeeded\n"
          "4 bulk-nvme claims bound in the last 20m")),
        (("Warning  ProvisioningFailed  example.com/bulk-nvme-csi  failed to "
          "provision volume: backend out of space (0 GiB free)"),
         ("Normal  ProvisioningSucceeded  example.com/bulk-nvme-csi  Successfully "
          "provisioned volume (space remaining 1.9 TiB)")),
        (("class bulk-nvme backend capacity: out of space\n"
          "free: 0 GiB of 4 TiB\n"
          "claims waiting on this class: 4, bound in 20m: 0"),
         ("class bulk-nvme backend capacity: space remaining\n"
          "free: 1.9 TiB of 4 TiB\n"
          "claims waiting on this class: 0, bound in 20m: 4")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim asks for a size below the "
                        "class's minimum, which the provisioner rejects",
            local_reason="the claim requests 100Mi and the class provisions nothing "
                         "under 1Gi",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Job's own claim names a snapshot as its data source "
                        "that was pruned by the retention policy",
            local_reason="the claim's dataSource points at a VolumeSnapshot that no "
                         "longer exists",
            read=("describe {ns}/{pod} (Pod)",
                  ("Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the backend "
                     "could not allocate the attach",
            local_cause="this StatefulSet's own volume was resized past the "
                        "backend's per-volume cap and the failed resize left it "
                        "detached",
            local_reason="the claim's last resize was refused by the backend and "
                         "the volume has not reattached since",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed")),
            pass_confidence="high",
        ),
    ),
)

_T_CSI_DRIVER_VERSION_MISMATCH = Propagation(
    key="csi-driver-version-mismatch",
    blast_radius="cluster",
    scope_field=None,
    origin="the replicated-ssd CSI controller was upgraded ahead of its node "
           "plugins, so volumes it provisions cannot be staged on any node",
    shared_cause="the replicated-ssd CSI controller was upgraded ahead of its node "
                 "plugins, so volumes it provisions cannot be staged on any node",
    shared_reason="storage-system/replicated-ssd-csi-controller is 1 of 1 ready at "
                  "driver API v2 while every node plugin is still at v1, and of the "
                  "5 PersistentVolumes bound on replicated-ssd in the last 20m, 0 "
                  "have been staged on any node",
    distractor_cause="the workloads' own pods were moved to nodes without the CSI "
                     "node plugin in the last node pool rollout",
    distractor_reason="every node runs the replicated-ssd node plugin and reports "
                      "it healthy; the plugin is a version the controller no longer "
                      "speaks to",
    rationale="this workload's volume is on the replicated-ssd class, and that "
              "class's controller provisions volumes its older node plugins cannot "
              "stage; the workload's own volume spec is unchanged",
    remedy="Roll the replicated-ssd node plugin DaemonSet to the controller's "
           "version (or roll the controller back); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related storageclass replicated-ssd",
        ("replicated-ssd driver versions: mismatch between controller and node "
         "plugins\n"
         "provisioner: example.com/replicated-ssd-csi\n"
         "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
         "Running\n"
         "driver API: controller v2, node plugins v1 (mismatch)\n"
         "PersistentVolumes bound in the last 20m: 5, staged on a node: 0"),
    ),
    healthy_origin_content=(
        "replicated-ssd driver versions: in step\n"
        "provisioner: example.com/replicated-ssd-csi\n"
        "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
        "Running\n"
        "driver API: controller v2, node plugins v2, in step\n"
        "PersistentVolumes bound in the last 20m: 5, staged on a node: 5"
    ),
    origin_state=("mismatch", "in step"),
    origin_variants=(
        (("replicated-ssd driver versions: mismatch between controller and node "
          "plugins\n"
          "provisioner: example.com/replicated-ssd-csi\n"
          "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "driver API: controller v2, node plugins v1 (mismatch)\n"
          "PersistentVolumes bound in the last 20m: 5, staged on a node: 0"),
         ("replicated-ssd driver versions: in step\n"
          "provisioner: example.com/replicated-ssd-csi\n"
          "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "driver API: controller v2, node plugins v2, in step\n"
          "PersistentVolumes bound in the last 20m: 5, staged on a node: 5")),
        (("the replicated-ssd controller speaks driver API v2 and every node "
          "plugin still speaks v1: a mismatch\n"
          "the controller was upgraded 25m ago and the node plugin DaemonSet was "
          "not\n"
          "5 volumes bound since then, 0 staged on any node"),
         ("the replicated-ssd controller and every node plugin speak driver API "
          "v2, in step\n"
          "both were upgraded together 3d ago\n"
          "5 volumes bound in 20m, all 5 staged")),
        (("Warning  FailedMount  kubelet  MountVolume.MountDevice failed: node "
          "plugin v1 cannot stage a v2 volume (driver version mismatch)"),
         ("Normal  SuccessfulMountVolume  kubelet  MapVolume.MapPodDevice "
          "succeeded (driver versions in step, v2/v2)")),
        (("class replicated-ssd driver API: mismatch\n"
          "controller: v2, node plugins: v1 on 3 of 3 nodes\n"
          "volumes bound in 20m: 5, staged: 0"),
         ("class replicated-ssd driver API: in step\n"
          "controller: v2, node plugins: v2 on 3 of 3 nodes\n"
          "volumes bound in 20m: 5, staged: 5")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.MountDevice failed for volume \"{pvc}\": the node "
                     "plugin could not stage the volume",
            local_cause="this Deployment's own volume mount asks for a mount option "
                        "the driver does not support",
            local_reason="the claim's mountOptions carry a flag the driver rejects "
                         "at stage",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.MountDevice failed for volume "
                  "\"{pvc}\": stage failed")),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the node "
                     "plugin did not acknowledge the attach",
            local_cause="this StatefulSet's own volume was left attached to a node "
                        "that was removed from the cluster before its pod moved",
            local_reason="the volume's attachment still names the removed node and "
                         "the new node cannot take it",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed")),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: the data volume was not staged "
                     "before the container's start deadline",
            local_cause="this Job's own container entrypoint runs a filesystem check "
                        "that fails on the volume's unclean journal",
            local_reason="the entrypoint's fsck refuses the volume and exits before "
                         "the main process starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container \"{container}\": data volume not ready")),
            pass_confidence="high",
        ),
    ),
)

_T_NETPOL_DNS_EGRESS_MISSING = Propagation(
    key="networkpolicy-dns-egress-missing",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's egress policy has no DNS rule, so every pod's name "
           "lookups are dropped",
    shared_cause="the egress policy in {ns} allows no DNS traffic, so every pod "
                 "there fails to resolve any name",
    shared_reason="{ns}/egress-to-app selects every pod in the namespace with "
                  "policyTypes Egress and one rule, to app=backend on tcp/8080; "
                  "it has no rule to kube-system on udp/53, so DNS is not "
                  "allowed for any of the 6 selected pods",
    distractor_cause="the workloads' own DNS settings were changed to a "
                     "nameserver outside the cluster in the last chart release",
    distractor_reason="every pod still uses the cluster DNS service address from "
                      "its dnsPolicy ClusterFirst; the queries leave the pod and "
                      "are dropped at the policy",
    rationale="the workload cannot resolve any name because the egress policy "
              "that selects it has no DNS rule, and that is true of every pod "
              "in {ns} right now",
    remedy="Add an egress rule to {ns}/egress-to-app allowing udp/53 to "
           "kube-system; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-app",
        ("DNS egress allowed: no\n"
         "podSelector: empty (selects every pod in the namespace)\n"
         "policyTypes: Egress\n"
         "egress: allow to app=backend tcp/8080\n"
         "DNS udp/53 allowed: no\n"
         "pods selected: 6 of 6"),
    ),
    healthy_origin_content=(
        "DNS egress allowed: yes\n"
        "podSelector: empty (selects every pod in the namespace)\n"
        "policyTypes: Egress\n"
        "egress: allow to app=backend tcp/8080\n"
        "egress: allow to kube-system udp/53\n"
        "DNS udp/53 allowed: yes\n"
        "pods selected: 6 of 6"
    ),
    origin_state=("allowed: no", "allowed: yes"),
    origin_variants=(
        (("DNS egress allowed: no\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=backend tcp/8080\n"
          "DNS udp/53 allowed: no\n"
          "pods selected: 6 of 6"),
         ("DNS egress allowed: yes\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=backend tcp/8080\n"
          "egress: allow to kube-system udp/53\n"
          "DNS udp/53 allowed: yes\n"
          "pods selected: 6 of 6")),
        (("the namespace egress policy selects all 6 pods and lists one rule, to "
          "the backend on tcp/8080\n"
          "DNS to kube-system udp/53 allowed: no\n"
          "name lookups from every selected pod time out"),
         ("the namespace egress policy selects all 6 pods and lists two rules, "
          "to the backend and to kube-system udp/53\n"
          "DNS to kube-system udp/53 allowed: yes\n"
          "name lookups from every selected pod answer in under 5ms")),
        (("Warning  PolicyDrop  network-plugin  DNS query to kube-system udp/53 "
          "dropped by egress-to-app (DNS allowed: no)"),
         ("Normal  PolicyAllow  network-plugin  DNS query to kube-system udp/53 "
          "passed egress-to-app (DNS allowed: yes)")),
        (("egress-to-app DNS rule: missing, allowed: no\n"
          "selected pods: 6 of 6\n"
          "dropped udp/53 packets in the last 10m: 2410"),
         ("egress-to-app DNS rule: present, allowed: yes\n"
          "selected pods: 6 of 6\n"
          "dropped udp/53 packets in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="name resolution failed on start",
            local_cause="this Deployment's own pod spec sets dnsPolicy None with an "
                        "empty nameserver list, so it has nowhere to send a query",
            local_reason="the pod's own dnsConfig lists no nameserver at all",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: name resolution failed on start (3 of 3 "
                  "sampled restarts)")),
            pass_confidence="high",
            network_policies=("egress-to-app",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: peer lookup failed",
            local_cause="this StatefulSet's own readiness check resolves a hostname "
                        "with a typo that no zone serves",
            local_reason="the probe's own peer hostname is misspelled in the "
                         "StatefulSet's config",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: peer lookup failed")),
            pass_confidence="medium",
            network_policies=("egress-to-app",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-backend could not resolve the backend name",
            local_cause="this Job's own init container looks up a search domain "
                        "that its chart dropped from the pod's dnsConfig",
            local_reason="the init step queries a short name whose search domain "
                         "the pod no longer carries",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-backend could not resolve "
                  "the backend name")),
            pass_confidence="high",
            network_policies=("egress-to-app",),
        ),
    ),
)

_T_NETPOL_NAMESPACE_LABEL_DRIFTED = Propagation(
    key="networkpolicy-namespace-label-drifted",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's broker egress policy names the messaging namespace by a "
           "label that was renamed, so no pod can reach the broker",
    shared_cause="the egress policy in {ns} names the messaging namespace by a "
                 "label that was renamed, so no pod there can reach the message "
                 "broker",
    shared_reason="{ns}/egress-to-messaging selects app=orders pods, 3 of 6, with "
                  "one Egress rule to namespaceSelector team=messaging on "
                  "tcp/5672; that selector matches 0 namespaces since the "
                  "messaging namespace was relabelled, so broker traffic from "
                  "every selected pod is dropped",
    distractor_cause="the message broker has stopped accepting connections from "
                     "every namespace",
    distractor_reason="the broker's own readiness passes and a pod in another "
                      "namespace publishes to it without error",
    rationale="the workload cannot reach the broker because the egress policy "
              "that selects it matches no namespace any more, and that is true "
              "of every selected pod in {ns} right now",
    remedy="Update the namespaceSelector in {ns}/egress-to-messaging to the "
           "messaging namespace's current label; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-messaging",
        ("Broker namespace match: no namespace carries the rule's label\n"
         "podSelector: app=orders\n"
         "policyTypes: Egress\n"
         "egress: allow to namespaceSelector team=messaging tcp/5672\n"
         "namespaces matched: 0 (matches no namespace; label renamed)\n"
         "pods selected: 3 of 6"),
    ),
    healthy_origin_content=(
        "Broker namespace match: the messaging namespace\n"
        "podSelector: app=orders\n"
        "policyTypes: Egress\n"
        "egress: allow to namespaceSelector team=messaging tcp/5672\n"
        "namespaces matched: 1 (the messaging namespace)\n"
        "pods selected: 3 of 6"
    ),
    origin_state=("no namespace", "messaging namespace"),
    origin_variants=(
        (("Broker namespace match: no namespace carries the rule's label\n"
          "podSelector: app=orders\n"
          "policyTypes: Egress\n"
          "egress: allow to namespaceSelector team=messaging tcp/5672\n"
          "namespaces matched: 0 (matches no namespace; label renamed)\n"
          "pods selected: 3 of 6"),
         ("Broker namespace match: the messaging namespace\n"
          "podSelector: app=orders\n"
          "policyTypes: Egress\n"
          "egress: allow to namespaceSelector team=messaging tcp/5672\n"
          "namespaces matched: 1 (the messaging namespace)\n"
          "pods selected: 3 of 6")),
        (("the broker egress rule's namespaceSelector matches no namespace\n"
          "the label team=messaging was renamed to owner=messaging 40m ago\n"
          "broker connections from the 3 selected pods: all dropped"),
         ("the broker egress rule's namespaceSelector matches the messaging "
          "namespace\n"
          "the label team=messaging is present on it\n"
          "broker connections from the 3 selected pods: all open")),
        (("Warning  PolicyDrop  network-plugin  egress to tcp/5672 dropped by "
          "egress-to-messaging: namespaceSelector matches no namespace"),
         ("Normal  PolicyAllow  network-plugin  egress to tcp/5672 passed "
          "egress-to-messaging: namespaceSelector matches the messaging namespace")),
        (("egress-to-messaging target: no namespace matched\n"
          "selected pods: 3 of 6\n"
          "dropped tcp/5672 connections in the last 10m: 96"),
         ("egress-to-messaging target: the messaging namespace, 1 matched\n"
          "selected pods: 3 of 6\n"
          "dropped tcp/5672 connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="broker connection timed out during startup",
            local_cause="this Deployment's own broker setting names a virtual host "
                        "that was deleted from the broker last week",
            local_reason="the connection setting's vhost no longer exists on the "
                         "broker",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection to the broker timed out before the "
                  "first publish (3 of 3 sampled restarts)")),
            pass_confidence="high",
            network_policies=("egress-to-messaging",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-broker gave up after 120s",
            local_cause="this Job's own init container waits on a broker queue that "
                        "was renamed in the last release",
            local_reason="the init step polls a queue name the broker no longer "
                         "declares",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-broker gave up after 120s")),
            pass_confidence="medium",
            network_policies=("egress-to-messaging",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: broker check timed out",
            local_cause="this StatefulSet's own readiness check publishes a test "
                        "message with credentials the broker revoked",
            local_reason="the probe's own broker login was revoked in the broker's "
                         "last user cleanup",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: broker check timed out")),
            pass_confidence="high",
            network_policies=("egress-to-messaging",),
        ),
    ),
)

_T_NETPOL_PORT_MISMATCH = Propagation(
    key="networkpolicy-port-mismatch",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's cache egress policy opens the cache's old port, so "
           "every connection to its new port is dropped",
    shared_cause="the egress policy in {ns} opens the cache's old port, so every "
                 "connection to its new port is dropped",
    shared_reason="{ns}/egress-to-cache selects role=worker pods, 5 of 6, with one "
                  "Egress rule to app=cache on tcp/6379, while the cache now "
                  "listens on tcp/6380; the port does not match, so every "
                  "connection from the selected pods is dropped",
    distractor_cause="the workloads' own cache client settings still name the "
                     "cache's old port",
    distractor_reason="the clients dial tcp/6380, the port the cache now listens "
                      "on; it is the policy that still says tcp/6379",
    rationale="the workload cannot reach the cache because the egress policy that "
              "selects it opens a port the cache no longer listens on, and that "
              "is true of every selected pod in {ns} right now",
    remedy="Change the cache rule in {ns}/egress-to-cache from tcp/6379 to "
           "tcp/6380; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-cache",
        ("Cache port match: no\n"
         "podSelector: role=worker\n"
         "policyTypes: Egress\n"
         "egress: allow to app=cache tcp/6379\n"
         "cache listening port: 6380\n"
         "port match: no\n"
         "pods selected: 5 of 6"),
    ),
    healthy_origin_content=(
        "Cache port match: yes\n"
        "podSelector: role=worker\n"
        "policyTypes: Egress\n"
        "egress: allow to app=cache tcp/6380\n"
        "cache listening port: 6380\n"
        "port match: yes\n"
        "pods selected: 5 of 6"
    ),
    origin_state=("port match: no", "port match: yes"),
    origin_variants=(
        (("Cache port match: no\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to app=cache tcp/6379\n"
          "cache listening port: 6380\n"
          "port match: no\n"
          "pods selected: 5 of 6"),
         ("Cache port match: yes\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to app=cache tcp/6380\n"
          "cache listening port: 6380\n"
          "port match: yes\n"
          "pods selected: 5 of 6")),
        (("the cache egress rule opens tcp/6379 and the cache listens on "
          "tcp/6380, port match: no\n"
          "the cache moved ports in its last rollout and the policy was not "
          "updated\n"
          "cache connections from the 5 selected pods: all dropped"),
         ("the cache egress rule opens tcp/6380 and the cache listens on "
          "tcp/6380, port match: yes\n"
          "the policy was updated with the cache's last rollout\n"
          "cache connections from the 5 selected pods: all open")),
        (("Warning  PolicyDrop  network-plugin  egress to app=cache tcp/6380 "
          "dropped by egress-to-cache (rule opens tcp/6379, port match: no)"),
         ("Normal  PolicyAllow  network-plugin  egress to app=cache tcp/6380 "
          "passed egress-to-cache (rule opens tcp/6380, port match: yes)")),
        (("egress-to-cache rule port: 6379, cache port: 6380, port match: no\n"
          "selected pods: 5 of 6\n"
          "dropped cache connections in the last 10m: 3120"),
         ("egress-to-cache rule port: 6380, cache port: 6380, port match: yes\n"
          "selected pods: 5 of 6\n"
          "dropped cache connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="cache connection timed out during startup",
            local_cause="this Deployment's own cache client pins a protocol version "
                        "the cache stopped serving in its last upgrade",
            local_reason="the client's own protocol setting is one the cache no "
                         "longer answers",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection to the cache timed out before the "
                  "first command (3 of 3 sampled restarts)")),
            pass_confidence="high",
            network_policies=("egress-to-cache",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: cache check timed out",
            local_cause="this StatefulSet's own readiness check pings the cache with "
                        "an auth token that expired",
            local_reason="the probe's own cache token passed its expiry last night",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: cache check timed out")),
            pass_confidence="medium",
            network_policies=("egress-to-cache",),
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="cache write-behind queue overflowed, exiting to flush",
            log_cause="cache write-behind queue overflowed",
            local_cause="this agent's own cache connection pool is sized larger than "
                        "the cache's per-client connection cap",
            local_reason="the agent's own pool opens more connections than the cache "
                         "admits and the extras stall its queue",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: cache write-behind queue overflowed (3 of 3 "
                  "sampled restarts)")),
            pass_confidence="high",
            network_policies=("egress-to-cache",),
        ),
    ),
)

_T_NETPOL_ALLOW_SELECTOR_TYPO = Propagation(
    key="networkpolicy-allow-selector-typo",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's frontend allow policy has a typo in its pod selector, "
           "so it selects nothing and the default-deny blocks every frontend pod",
    shared_cause="the {ns} frontend allow policy has a typo in its pod selector, "
                 "so it selects nothing and the namespace's default-deny blocks "
                 "every frontend pod's egress",
    shared_reason="{ns}/allow-frontend-egress carries podSelector role=fronted, "
                  "which selects 0 of 6 pods, while the pods carry role=frontend; "
                  "its one Egress rule to app=api on tcp/443 applies to nobody, "
                  "and the namespace's default-deny egress applies to all 6",
    distractor_cause="the workloads' own images lost their CA bundle in the last "
                     "rebuild",
    distractor_reason="the API's certificate verifies from a pod in another "
                      "namespace running the same image; the connection from "
                      "{ns} never leaves the pod",
    rationale="the workload cannot reach the API because the policy meant to allow "
              "it selects no pod, so the default-deny applies, and that is true "
              "of every frontend pod in {ns} right now",
    remedy="Fix the podSelector in {ns}/allow-frontend-egress from role=fronted "
           "to role=frontend; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/allow-frontend-egress",
        ("Frontend selector: selects no pod\n"
         "podSelector: role=fronted (selects no pod)\n"
         "policyTypes: Egress\n"
         "egress: allow to app=api tcp/443\n"
         "pods selected: 0 of 6\n"
         "baseline: default-deny egress applies to the 6 unselected pods"),
    ),
    healthy_origin_content=(
        "Frontend selector: every frontend pod\n"
        "podSelector: role=frontend (selects every frontend pod)\n"
        "policyTypes: Egress\n"
        "egress: allow to app=api tcp/443\n"
        "pods selected: 6 of 6\n"
        "baseline: default-deny egress applies to 0 unselected pods"
    ),
    origin_state=("selects no pod", "every frontend pod"),
    origin_variants=(
        (("Frontend selector: selects no pod\n"
          "podSelector: role=fronted (selects no pod)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=api tcp/443\n"
          "pods selected: 0 of 6\n"
          "baseline: default-deny egress applies to the 6 unselected pods"),
         ("Frontend selector: every frontend pod\n"
          "podSelector: role=frontend (selects every frontend pod)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=api tcp/443\n"
          "pods selected: 6 of 6\n"
          "baseline: default-deny egress applies to 0 unselected pods")),
        (("the frontend allow policy's selector says role=fronted and selects no "
          "pod\n"
          "the 6 frontend pods carry role=frontend\n"
          "with nothing selected, the namespace default-deny drops their egress"),
         ("the frontend allow policy's selector says role=frontend and selects "
          "every frontend pod\n"
          "all 6 frontend pods carry role=frontend\n"
          "their egress to the API passes the allow rule")),
        (("Warning  PolicyDrop  network-plugin  egress to app=api tcp/443 dropped "
          "by default-deny: allow-frontend-egress selects no pod (role=fronted)"),
         ("Normal  PolicyAllow  network-plugin  egress to app=api tcp/443 passed "
          "allow-frontend-egress: selector matches every frontend pod")),
        (("allow-frontend-egress selector: role=fronted, selects no pod\n"
          "frontend pods under default-deny: 6 of 6\n"
          "dropped tcp/443 connections in the last 10m: 870"),
         ("allow-frontend-egress selector: role=frontend, every frontend pod\n"
          "frontend pods under default-deny: 0 of 6\n"
          "dropped tcp/443 connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="API connection timed out during startup",
            local_cause="this Deployment's own API client pins a TLS version the "
                        "API stopped accepting last month",
            local_reason="the client's own TLS floor is one the API no longer "
                         "negotiates",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection to the API timed out before the "
                  "first request (3 of 3 sampled restarts)")),
            pass_confidence="high",
            network_policies=("allow-frontend-egress",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: API check timed out",
            local_cause="this StatefulSet's own readiness check sends the API a "
                        "token from a service account that was deleted",
            local_reason="the probe's own service account no longer exists, so its "
                         "token is rejected",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: API check timed out")),
            pass_confidence="medium",
            network_policies=("allow-frontend-egress",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-api gave up after 120s",
            local_cause="this Job's own init container calls the API through a proxy "
                        "setting that names a proxy nobody runs any more",
            local_reason="the init step's own proxy variable points at a host that "
                         "was decommissioned",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-api gave up after 120s")),
            pass_confidence="high",
            network_policies=("allow-frontend-egress",),
        ),
    ),
)

_T_NETPOL_INGRESS_DENY_ALL = Propagation(
    key="networkpolicy-ingress-deny-all",
    blast_radius="namespace",
    scope_field="ns",
    origin="a deny-all ingress policy selects every pod in the namespace, so no "
           "inbound connection reaches any of them",
    shared_cause="a deny-all ingress policy in {ns} blocks every inbound "
                 "connection, so pods there that need their peers or their "
                 "callers cannot become ready",
    shared_reason="{ns}/deny-all-ingress selects every pod in the namespace, 6 of "
                  "6, with policyTypes Ingress and an empty ingress list, so all "
                  "ingress is denied to every pod",
    distractor_cause="the workloads' own readiness ports were changed in the last "
                     "chart release",
    distractor_reason="the probe ports match the containers' listening ports; the "
                      "probes fail because nothing inbound reaches the pods",
    rationale="the workload cannot take any inbound connection because a deny-all "
              "ingress policy selects it, and that is true of every pod in {ns} "
              "right now",
    remedy="Narrow or delete {ns}/deny-all-ingress and add allow rules for the "
           "peers and callers each pod needs; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/deny-all-ingress",
        ("Ingress into this namespace: all ingress denied\n"
         "podSelector: empty (selects every pod in the namespace)\n"
         "policyTypes: Ingress\n"
         "ingress: [] (no rules — all ingress denied)\n"
         "pods selected: 6 of 6"),
    ),
    healthy_origin_content=(
        "Ingress into this namespace: allow from the scheduler, on one pod\n"
        "podSelector: app=legacy-batch\n"
        "policyTypes: Ingress\n"
        "ingress: allow from podSelector app=scheduler\n"
        "pods selected: 1 of 6"
    ),
    origin_state=("all ingress denied", "allow from"),
    origin_variants=(
        (("Ingress into this namespace: all ingress denied\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Ingress\n"
          "ingress: [] (no rules — all ingress denied)\n"
          "pods selected: 6 of 6"),
         ("Ingress into this namespace: allow from the scheduler, on one pod\n"
          "podSelector: app=legacy-batch\n"
          "policyTypes: Ingress\n"
          "ingress: allow from podSelector app=scheduler\n"
          "pods selected: 1 of 6")),
        (("the ingress policy selects all 6 pods and lists no rule, so all "
          "ingress denied\n"
          "peer and caller connections into every pod are dropped\n"
          "the policy was applied 30m ago by a cluster-wide hardening job"),
         ("the ingress policy selects 1 of 6 pods and lists one rule, allow from "
          "the scheduler\n"
          "peer and caller connections into the other 5 pods are untouched\n"
          "the policy has not changed in 30d")),
        (("Warning  PolicyDrop  network-plugin  ingress to every pod dropped by "
          "deny-all-ingress: no rules, all ingress denied"),
         ("Normal  PolicyAllow  network-plugin  ingress to app=legacy-batch passed "
          "deny-all-ingress: allow from app=scheduler")),
        (("deny-all-ingress scope: 6 of 6 pods, all ingress denied\n"
          "inbound connections dropped in the last 10m: 4280\n"
          "pods with a passing readiness probe: 0 of 6"),
         ("deny-all-ingress scope: 1 of 6 pods, allow from app=scheduler\n"
          "inbound connections dropped in the last 10m: 0\n"
          "pods with a passing readiness probe: 6 of 6")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="cluster join got no reply from any peer",
            local_cause="this Deployment's own cluster-join step expects a reply on a "
                        "port its container never opens",
            local_reason="the join step's own reply port is not in the container's "
                         "listen list",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: cluster join got no reply from any peer (3 of "
                  "3 sampled restarts)")),
            pass_confidence="high",
            network_policies=("deny-all-ingress",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: peer handshake did not complete",
            local_cause="this StatefulSet's own readiness check waits on a quorum "
                        "vote its own config sets one member too high",
            local_reason="the quorum size in the StatefulSet's config is one more "
                         "than its replica count",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: peer handshake did not "
                  "complete")),
            pass_confidence="medium",
            network_policies=("deny-all-ingress",),
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="watchdog: no scrape received in 60s, restarting",
            log_cause="watchdog saw no scrape in 60s",
            local_cause="this agent's own watchdog restarts it whenever its metrics "
                        "endpoint goes 60s without a scrape, and the scrape "
                        "interval is 90s",
            local_reason="the agent's own watchdog window is shorter than the "
                         "scrape interval it is configured with",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: watchdog saw no scrape in 60s (3 of 3 sampled "
                  "restarts)")),
            pass_confidence="high",
            network_policies=("deny-all-ingress",),
        ),
    ),
)


_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO,
                       _T_IMAGE_PULL_SECRET, _T_SECRET_KEY_RENAMED,
                       _T_AUTOSCALER_CAPACITY, _T_SIDECAR_INJECTOR,
                       _T_BASE_IMAGE_TAG, _T_PVC_MULTI_ATTACH, _T_CNI_IP_POOL,
                       _T_CSI_NODE_DRIVER, _T_NODE_PID_PRESSURE,
                       _T_NODE_RUNTIME_RESTARTING, _T_NODE_CLOCK_SKEW,
                       _T_NODE_CONNTRACK_FULL, _T_LIMITRANGE_LOWERED,
                       _T_EGRESS_PROXY_DOWN, _T_NS_PVC_FULL, _T_MIGRATION_LOCK,
                       _T_POD_IDENTITY_WEBHOOK, _T_STORAGECLASS_POOL_RETIRED,
                       _T_NETPOL_EGRESS_ALLOWLIST, _T_NODE_MEMORY_PRESSURE,
                       _T_NODE_NETWORK_UNAVAILABLE, _T_NODE_KERNEL_DEADLOCK,
                       _T_NODE_READONLY_FILESYSTEM,
                       _T_NODE_FREQUENT_KUBELET_RESTART, _T_NODE_CORDONED_DRAINING,
                       _T_NODE_CORRUPT_OVERLAY, _T_EXTERNAL_SECRETS_DOWN,
                       _T_NETWORK_OPERATOR_DOWN, _T_CERT_MANAGER_DOWN,
                       _T_METRICS_SERVER_DOWN, _T_SHARED_NFS_SERVER_DOWN,
                       _T_CLUSTER_MAINTENANCE_TAINT, _T_SHARED_GATEWAY_REFUSING,
                       _T_RUNTIME_CLASS_REMOVED, _T_CSI_CONTROLLER_OOMKILLED,
                       _T_CSI_CONTROLLER_UNSCHEDULABLE,
                       _T_PROVISIONER_CREDENTIALS_ROTATED, _T_STORAGE_BACKEND_FULL,
                       _T_CSI_DRIVER_VERSION_MISMATCH, _T_NETPOL_DNS_EGRESS_MISSING,
                       _T_NETPOL_NAMESPACE_LABEL_DRIFTED, _T_NETPOL_PORT_MISMATCH,
                       _T_NETPOL_ALLOW_SELECTOR_TYPO, _T_NETPOL_INGRESS_DENY_ALL)


def trainable_scenarios() -> tuple[Propagation, ...]:
    """The origins training may see: the 48 plain stories plus the six ruled
    stories (spec section 4), whose origin object lets the rules pass itself
    confirm the shared cause. Disjoint from `all_scenarios()` by test."""
    return _TRAINING_SCENARIOS + _RULED_SCENARIOS


_RULED_NODE_1 = Propagation(
    key="node-kubelet-halted",
    blast_radius="node",
    scope_field="node",
    origin="a node's kubelet process crashed outright, so the node reports "
           "Ready False",
    shared_cause="node {node}'s kubelet process crashed and the node reports "
                 "Ready False, so the pods it held cannot come back on it",
    shared_reason="{node} shows Ready False and its kubelet reports no "
                  "successful status update",
    distractor_cause="an operator cordoned {node} for planned maintenance",
    distractor_reason="{node} carries no cordon annotation and stays "
                      "schedulable",
    rationale="the workload's symptom is what a crashed kubelet on {node} "
              "does to it, not a change in the workload itself",
    remedy="Restart the kubelet on {node} or replace the node; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_object=Object(kind="node", name="{node}", scan_reason="NotReady",
                          placement="on", fresh=Fresh(ready="False"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(ready="True"),
    origin_read=(
        "describe node {node}",
        ("Ready condition: False\nConditions:\n"
         "  Ready   False   KubeletNotReady   PLEG is not healthy: pleg was "
         "last seen active\n"
         "Taints:  node.kubernetes.io/not-ready:NoExecute\n"
         "         node.kubernetes.io/not-ready:NoSchedule"),
    ),
    healthy_origin_content=(
        "Ready condition: True\nConditions:\n"
        "  Ready   True    KubeletReady   kubelet is posting ready status\n"
        "Taints:  <none>"
    ),
    origin_variants=(
        (("Ready condition: False\nConditions:\n"
          "  Ready   False   KubeletNotReady   PLEG is not healthy: pleg was "
          "last seen active\n"
          "Taints:  node.kubernetes.io/not-ready:NoExecute\n"
          "         node.kubernetes.io/not-ready:NoSchedule"),
         ("Ready condition: True\nConditions:\n"
          "  Ready   True    KubeletReady   kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("systemd unit kubelet.service: failed\n"
          "ExitCode=137, restart suppressed by admin override\n"
          "node condition Ready: False"),
         ("systemd unit kubelet.service: active (running)\n"
          "restart count: 0\n"
          "node condition Ready: True")),
        (("node agent process: not running\n"
          "process exited 4 minutes ago and has not restarted\n"
          "node condition Ready: False"),
         ("node agent process: running\n"
          "process has been running for 9 days without a restart\n"
          "node condition Ready: True")),
        (("cluster view of the node: unreachable from the API server\n"
          "kubelet process exited with signal 9\n"
          "node condition Ready: False"),
         ("cluster view of the node: reachable from the API server\n"
          "kubelet process has not restarted\n"
          "node condition Ready: True")),
    ),
    origin_state=("False", "True"),
    victims=(
        Victim(
            workload_kind="Deployment", status="Degraded",
            issue="ContainerStartError",
            reason="the container image was resolved but the container "
                   "could not be started",
            evidence="RunContainerError: failed to create containerd task: "
                     "failed to create shim task: context deadline exceeded",
            local_cause="the container's init step waits on a config file a "
                        "sidecar has not written yet",
            local_reason="the container exits before the sidecar finishes "
                         "writing its config",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: RunContainerError: "
                   "failed to create containerd task: failed to create shim "
                   "task: context deadline exceeded")),
            healthy_read_content="Normal  Started  kubelet  Started container",
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted for {pod}",
            evidence="MountVolume.SetUp failed: rpc error: code = "
                     "DeadlineExceeded desc = context deadline exceeded",
            local_cause="the CSI node plugin on this pod's node is stuck "
                        "initializing",
            local_reason="the mount request never reaches a running CSI node "
                         "plugin",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  MountVolume.SetUp "
                   "failed: rpc error: code = DeadlineExceeded desc = "
                   "context deadline exceeded")),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="back-off restarting failed container",
            log_cause="dial tcp: i/o timeout dialing a local endpoint",
            local_cause="the agent's own retry budget runs out before its "
                        "dependency starts answering",
            local_reason="the agent gives up after a fixed retry budget "
                         "instead of waiting",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection attempt timed out dialing a "
                   "local endpoint (3 of 3 sampled restarts)")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_NODE_2 = Propagation(
    key="node-kubelet-unresponsive",
    blast_radius="node",
    scope_field="node",
    origin="a node's kubelet stopped answering the control plane, so its "
           "status reads Unknown",
    shared_cause="node {node} reports Ready Unknown because its kubelet "
                 "stopped answering the control plane, so the pods it held "
                 "are gone",
    shared_reason="{node} shows Ready Unknown and the control plane cannot "
                  "reach its kubelet at all",
    distractor_cause="a rollout paused every workload on {node} mid-deploy",
    distractor_reason="every controller on {node} still reports its prior "
                      "generation as current",
    rationale="the workload's symptom is what {node} going unreachable does "
              "to it, not a change in the workload itself",
    remedy="Restore network reachability to {node} or replace it; the "
           "flagged workloads need no change.",
    confidence="high",
    origin_object=Object(kind="node", name="{node}", scan_reason="NotReady",
                          placement="on", fresh=Fresh(ready="Unknown"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(ready="True"),
    origin_read=(
        "describe node {node}",
        ("Ready condition: Unknown\nConditions:\n"
         "  Ready   Unknown   NodeStatusUnknown   node has not responded to "
         "the control plane\n"
         "Taints:  node.kubernetes.io/unreachable:NoExecute\n"
         "         node.kubernetes.io/unreachable:NoSchedule"),
    ),
    healthy_origin_content=(
        "Ready condition: True\nConditions:\n"
        "  Ready   True    KubeletReady   kubelet is posting ready status\n"
        "Taints:  <none>"
    ),
    origin_variants=(
        (("Ready condition: Unknown\nConditions:\n"
          "  Ready   Unknown   NodeStatusUnknown   node has not responded to "
          "the control plane\n"
          "Taints:  node.kubernetes.io/unreachable:NoExecute\n"
          "         node.kubernetes.io/unreachable:NoSchedule"),
         ("Ready condition: True\nConditions:\n"
          "  Ready   True    KubeletReady   kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("control plane connection to the node: timed out\n"
          "the node has not been reachable this cycle\n"
          "node condition Ready: Unknown"),
         ("control plane connection to the node: established\n"
          "the node answered this cycle\n"
          "node condition Ready: True")),
        (("node network interface: no response to any probe\n"
          "every probe to the node has failed this cycle\n"
          "node condition Ready: Unknown"),
         ("node network interface: responds to every probe\n"
          "every probe to the node has succeeded this cycle\n"
          "node condition Ready: True")),
        (("kube-apiserver's node watcher: marked the node unreachable\n"
          "no update has arrived from this node\n"
          "node condition Ready: Unknown"),
         ("kube-apiserver's node watcher: marked the node reachable\n"
          "updates keep arriving from this node\n"
          "node condition Ready: True")),
    ),
    origin_state=("Unknown", "True"),
    victims=(
        Victim(
            workload_kind="Deployment", status="Degraded", issue="RestartLoop",
            reason="container {container} keeps restarting on this node",
            evidence="Back-off restarting failed container {container}",
            local_cause="a leftover lock file from a prior run blocks the "
                        "container's own startup",
            local_reason="the container's own init step refuses to proceed "
                         "while the lock file exists",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  Back-off restarting failed "
                   "container {container}")),
            healthy_read_content="Normal  Started  kubelet  Started container",
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to this pod's node",
            evidence="AttachVolume.Attach failed: rpc error: code = "
                     "Unavailable desc = the node is not answering attach "
                     "requests",
            local_cause="a second pod on a different node already holds the "
                        "exclusive attachment for {pvc}",
            local_reason="the attach controller reports the claim already "
                         "attached from elsewhere",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nAccess Modes: RWO\n"
                   "Attached to node: {node}  (node condition Ready: "
                   "Unknown)")),
            healthy_read_content=(
                "Status: Bound\nAccess Modes: RWO\n"
                "Attached to node: {node}  (node condition Ready: True)"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="Degraded", issue="ProbeFailure",
            reason="container {container}'s readiness probe fails from this "
                   "node",
            evidence="Readiness probe failed: dial tcp: i/o timeout",
            local_cause="the probe's own timeout is shorter than the "
                        "dependency it checks ever answers within",
            local_reason="the probe fails on its own schedule, regardless of "
                         "what is reachable",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Unhealthy  kubelet  Readiness probe "
                   "failed: dial tcp: i/o timeout")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_PVC_1 = Propagation(
    key="pvc-provisioner-not-responding",
    blast_radius="cluster",
    scope_field=None,
    origin="the dynamic provisioner for one storage class stopped "
           "responding to new claims",
    shared_cause="the capacity-hdd storage class's provisioner is not "
                 "responding, so no claim against it can bind",
    shared_reason="no PersistentVolume on the capacity-hdd class has bound "
                  "cluster-wide in the current window",
    distractor_cause="a namespace quota is refusing new pods",
    distractor_reason="the quota reports well under its pod limit in every "
                      "namespace",
    rationale="the workload is waiting on a capacity-hdd volume that "
              "nothing is left to create",
    remedy="Restore the capacity-hdd provisioner; the pending claims bind "
           "on their own afterwards.",
    confidence="high",
    origin_object=Object(kind="pvc", name="{pvc}",
                          scan_reason="ProvisionerNotResponding",
                          placement="mounted",
                          fresh=Fresh(phase="Pending",
                                     storage_class="capacity-hdd"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(phase="Bound", storage_class="capacity-hdd"),
    origin_read=(
        "get_related storageclass capacity-hdd",
        ("provisioner status: stalled\n"
         "provisioner: example.com/capacity-hdd-csi\n"
         "controller capacity-hdd-provisioner: 0/1 ready, CrashLoopBackOff\n"
         "PersistentVolumes bound on this class in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "provisioner status: healthy\n"
        "provisioner: example.com/capacity-hdd-csi\n"
        "controller capacity-hdd-provisioner: 1/1 ready, Running\n"
        "PersistentVolumes bound on this class in the last 20m: 6"
    ),
    origin_variants=(
        (("provisioner status: stalled\n"
          "provisioner: example.com/capacity-hdd-csi\n"
          "controller capacity-hdd-provisioner: 0/1 ready, CrashLoopBackOff\n"
          "PersistentVolumes bound on this class in the last 20m: 0"),
         ("provisioner status: healthy\n"
          "provisioner: example.com/capacity-hdd-csi\n"
          "controller capacity-hdd-provisioner: 1/1 ready, Running\n"
          "PersistentVolumes bound on this class in the last 20m: 6")),
        (("controller capacity-hdd-provisioner: CrashLoopBackOff, restart "
          "count climbing\n"
          "provisioner status: stalled\n"
          "last successful provision: none this window"),
         ("controller capacity-hdd-provisioner: Running, no restarts\n"
          "provisioner status: healthy\n"
          "last successful provision: within the last minute")),
        (("capacity-hdd claims waiting on a volume: 4\n"
          "provisioner status: stalled\n"
          "provisioner pod is not accepting new work"),
         ("capacity-hdd claims waiting on a volume: 0\n"
          "provisioner status: healthy\n"
          "provisioner pod is accepting new work")),
        (("capacity-hdd provision requests: queued, none completing\n"
          "provisioner status: stalled\n"
          "the provisioner container has not emitted a log line this "
          "window"),
         ("capacity-hdd provision requests: none queued, all completing\n"
          "provisioner status: healthy\n"
          "the provisioner container is emitting log lines normally")),
    ),
    origin_state=("stalled", "healthy"),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending",
            issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the claim asks for more capacity than any volume in "
                        "the pool can offer",
            local_reason="the claim never leaves Pending because no volume "
                         "that size exists",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: capacity-hdd\n"
                   "Events: Normal  ExternalProvisioning  waiting for a "
                   "volume to be created by the external provisioner")),
            healthy_read_content=(
                "Status: Bound\nStorageClass: capacity-hdd\n"
                "Events: Normal  ProvisioningSucceeded  successfully "
                "provisioned volume"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the Job's own retry backoff keeps it from ever "
                        "re-requesting the claim",
            local_reason="the pod template's own restart policy stalls the "
                         "request rather than retrying it",
            read=("get_events {ns}/{name}",
                  ("Normal  WaitForFirstConsumer  persistentvolume-controller "
                   " waiting for first consumer to be created before "
                   "binding\n"
                   "Normal  ExternalProvisioning  waiting for a volume to be "
                   "created")),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the "
                     "condition",
            local_cause="the filesystem on {pvc} needs an fsck that has not "
                        "been triggered",
            local_reason="the mount times out rather than failing outright",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  Unable to attach "
                   "or mount volumes: unmounted volumes=[{pvc}], timed out "
                   "waiting for the condition")),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)

_RULED_PVC_2 = Propagation(
    key="pvc-storageclass-missing",
    blast_radius="cluster",
    scope_field=None,
    origin="a storage class every new claim names was deleted, so nothing "
           "on it can provision",
    shared_cause="the cache-nvme storage class no longer exists, so no "
                 "claim naming it can bind",
    shared_reason="cache-nvme is absent from the cluster's storage class "
                  "list and every claim on it stays Pending",
    distractor_cause="the cluster autoscaler is refusing to add capacity",
    distractor_reason="the autoscaler reports headroom on every existing "
                      "node",
    rationale="the workload is waiting on a cache-nvme volume that no "
              "storage class exists to create",
    remedy="Recreate the cache-nvme storage class; the pending claims bind "
           "on their own afterwards.",
    confidence="high",
    origin_object=Object(kind="pvc", name="{pvc}",
                          scan_reason="MissingStorageClass",
                          placement="mounted",
                          fresh=Fresh(phase="Pending",
                                     storage_class="cache-nvme"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(phase="Bound", storage_class="cache-nvme"),
    origin_read=(
        "get_related storageclass cache-nvme",
        ("storage class lookup: missing\n"
         "requested class: cache-nvme\n"
         "matching StorageClass objects in the cluster: 0\n"
         "PersistentVolumeClaims stuck Pending on this class: 5"),
    ),
    healthy_origin_content=(
        "storage class lookup: present\n"
        "requested class: cache-nvme\n"
        "matching StorageClass objects in the cluster: 1\n"
        "PersistentVolumeClaims bound on this class in the last 20m: 4"
    ),
    origin_variants=(
        (("storage class lookup: missing\n"
          "requested class: cache-nvme\n"
          "matching StorageClass objects in the cluster: 0\n"
          "PersistentVolumeClaims stuck Pending on this class: 5"),
         ("storage class lookup: present\n"
          "requested class: cache-nvme\n"
          "matching StorageClass objects in the cluster: 1\n"
          "PersistentVolumeClaims bound on this class in the last 20m: 4")),
        (("PersistentVolumeClaims referencing cache-nvme: 5 Pending\n"
          "storage class lookup: missing\n"
          "no provisioner is registered for this class name"),
         ("PersistentVolumeClaims referencing cache-nvme: 0 Pending, 4 "
          "Bound\n"
          "storage class lookup: present\n"
          "a provisioner is registered for this class name")),
        (("cluster storage class list: cache-nvme is absent\n"
          "storage class lookup: missing\n"
          "no operator has recreated it since it was removed"),
         ("cluster storage class list: cache-nvme is present\n"
          "storage class lookup: present\n"
          "the class has been recreated and claims are binding again")),
        (("admission check for new claims naming cache-nvme: rejected, "
          "unknown class\n"
          "storage class lookup: missing\n"
          "every new claim on this class fails at admission"),
         ("admission check for new claims naming cache-nvme: accepted\n"
          "storage class lookup: present\n"
          "new claims on this class pass admission normally")),
    ),
    origin_state=("missing", "present"),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending",
            issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the StatefulSet's replica count outgrew the volumes "
                        "already provisioned for it",
            local_reason="the newest replica's claim is the only one still "
                         "Pending",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: cache-nvme\n"
                   "Events: Warning  ProvisioningFailed  "
                   "persistentvolume-controller  storageclass.storage.k8s.io "
                   '"cache-nvme" not found')),
            healthy_read_content=(
                "Status: Bound\nStorageClass: cache-nvme\n"
                "Events: Normal  ProvisioningSucceeded  successfully "
                "provisioned volume"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the Job's claim template was copied from a cluster "
                        "that used a different class name",
            local_reason="the claim requests a class name this cluster never "
                         "had",
            read=("get_events {ns}/{name}",
                  ("Warning  ProvisioningFailed  persistentvolume-controller "
                   ' storageclass.storage.k8s.io "cache-nvme" not found')),
            healthy_read_content=(
                "Normal  ProvisioningSucceeded  persistentvolume-controller "
                " successfully provisioned volume for this claim"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the "
                     "condition",
            local_cause="a stale CSI socket file on this pod's node blocks "
                        "the mount",
            local_reason="the mount times out rather than failing outright",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  Unable to attach "
                   "or mount volumes: unmounted volumes=[{pvc}], timed out "
                   "waiting for the condition")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_REGISTRY_1 = Propagation(
    key="registry-mirror-unreachable",
    blast_radius="cluster",
    scope_field=None,
    origin="the cluster's image mirror stopped resolving in DNS, so every "
           "pull through it fails before any manifest is requested",
    shared_cause="the mirror.invalid registry cannot be resolved, so no "
                 "workload pulling through it can start",
    shared_reason="every pull naming mirror.invalid fails at DNS "
                  "resolution, before any manifest is requested",
    distractor_cause="the images were removed from the mirror's catalog",
    distractor_reason="the pulls never get far enough to ask for a "
                      "manifest",
    rationale="the workload cannot start because the mirror it pulls from "
              "cannot be resolved at all, which is true of every image "
              "behind it right now",
    remedy="Restore DNS resolution for mirror.invalid; no workload manifest "
           "needs editing.",
    confidence="high",
    origin_object=Object(kind="registry", name="mirror.invalid",
                          scan_reason="{count}", placement="",
                          fresh=Fresh(literal="no such host"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(literal="manifest unknown"),
    origin_read=(
        "get_events (cluster-wide, type=Warning)",
        ("pulls through mirror.invalid: all failing\n"
         "every pod pulling through mirror.invalid reports the same "
         "error:\n"
         "  Failed to pull image: rpc error: code = Unknown desc = failed "
         "to resolve reference: dial tcp: lookup mirror.invalid: no such "
         "host"),
    ),
    healthy_origin_content=(
        "pulls through mirror.invalid: succeeding\n"
        "pods pulling through mirror.invalid report ordinary image errors, "
        "not connection errors:\n"
        "  Failed to pull image: rpc error: code = Unknown desc = manifest "
        "unknown"
    ),
    origin_variants=(
        (("pulls through mirror.invalid: all failing\n"
          "every pod pulling through mirror.invalid reports the same "
          "error:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = failed "
          "to resolve reference: dial tcp: lookup mirror.invalid: no such "
          "host"),
         ("pulls through mirror.invalid: succeeding\n"
          "pods pulling through mirror.invalid report ordinary image "
          "errors, not connection errors:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "manifest unknown")),
        (("DNS lookup for mirror.invalid: NXDOMAIN\n"
          "resolution failures this window: every pull naming "
          "mirror.invalid\n"
          "sample error: dial tcp: lookup mirror.invalid: no such host"),
         ("DNS lookup for mirror.invalid: resolves normally\n"
          "resolution failures this window: none naming mirror.invalid\n"
          "sample error: manifest unknown")),
        (("mirror.invalid reachability probe: failed\n"
          "every image pull naming this host times out at resolution\n"
          "sample error: no such host"),
         ("mirror.invalid reachability probe: succeeded\n"
          "image pulls naming this host resolve and proceed to the "
          "manifest\n"
          "sample error: manifest unknown")),
        (("image pull error clustering: one failure mode, one host\n"
          "all failures name mirror.invalid and the same resolution "
          "error\n"
          "sample error: no such host"),
         ("image pull error clustering: ordinary per-image errors\n"
          "failures name several images behind mirror.invalid, no "
          "resolution error among them\n"
          "sample error: manifest unknown")),
    ),
    origin_state=("no such host", "manifest unknown"),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the image tag {image} was retagged and no longer "
                        "points at a built image",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image "
                   "{image}: dial tcp: lookup mirror.invalid: no such "
                   "host")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image "
                "{image}: manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull",
            issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            local_cause="the image reference for {image} was built against "
                        "a registry path this cluster never mirrors",
            local_reason="the pull fails before the image layers are "
                         "fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  failed to resolve reference: "
                   "dial tcp: lookup mirror.invalid: no such host")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  failed to resolve reference: "
                "manifest unknown"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container "
                     "{init_container}",
            local_cause="the init container's image name carries a typo "
                        "that only this Job's template has",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n"
                   "    State: Waiting\n    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  dial tcp: lookup "
                   "mirror.invalid: no such host")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)

_RULED_REGISTRY_2 = Propagation(
    key="registry-rate-limited",
    blast_radius="cluster",
    scope_field=None,
    origin="the image registry is throttling every pull from inside the "
           "cluster",
    shared_cause="registry.invalid is rate-limiting the cluster's pulls, so "
                 "no workload pulling from it can finish",
    shared_reason="every pull naming registry.invalid fails with the same "
                  "rate-limit response, before any manifest is served",
    distractor_cause="a new admission policy blocks the affected pods' "
                     "image references",
    distractor_reason="the policy's own audit log shows no denial for any "
                      "of the affected pods",
    rationale="the workload cannot start because the registry it pulls "
              "from is throttling every request right now, which is true "
              "of every image behind it",
    remedy="Raise or clear the rate limit on registry.invalid; no workload "
           "manifest needs editing.",
    confidence="high",
    origin_object=Object(kind="registry", name="registry.invalid",
                          scan_reason="{count}", placement="",
                          fresh=Fresh(literal="toomanyrequests"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(literal="manifest unknown"),
    origin_read=(
        "get_events (cluster-wide, type=Warning)",
        ("pulls from registry.invalid: all rate-limited\n"
         "every pod pulling from registry.invalid reports the same error:\n"
         "  Failed to pull image: rpc error: code = Unknown desc = "
         "toomanyrequests: too many requests to registry.invalid"),
    ),
    healthy_origin_content=(
        "pulls from registry.invalid: succeeding\n"
        "pods pulling from registry.invalid report ordinary image errors, "
        "not rate-limit errors:\n"
        "  Failed to pull image: rpc error: code = Unknown desc = manifest "
        "unknown"
    ),
    origin_variants=(
        (("pulls from registry.invalid: all rate-limited\n"
          "every pod pulling from registry.invalid reports the same "
          "error:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "toomanyrequests: too many requests to registry.invalid"),
         ("pulls from registry.invalid: succeeding\n"
          "pods pulling from registry.invalid report ordinary image "
          "errors, not rate-limit errors:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "manifest unknown")),
        (("registry.invalid response code on every pull: 429\n"
          "rate-limit window: exceeded for the whole cluster\n"
          "sample error: toomanyrequests"),
         ("registry.invalid response code on every pull: 200 to the "
          "manifest request\n"
          "rate-limit window: not exceeded\n"
          "sample error: manifest unknown")),
        (("registry.invalid request budget: exhausted\n"
          "every pull queues behind the same limit\n"
          "sample error: toomanyrequests"),
         ("registry.invalid request budget: available\n"
          "pulls proceed without queuing\n"
          "sample error: manifest unknown")),
        (("pull error signature across the cluster: single host, single "
          "failure mode\n"
          "all failures name registry.invalid and the same rate-limit "
          "error\n"
          "sample error: toomanyrequests"),
         ("pull error signature across the cluster: many hosts, many "
          "failure modes\n"
          "failures name several images behind registry.invalid, no "
          "rate-limit error among them\n"
          "sample error: manifest unknown")),
    ),
    origin_state=("toomanyrequests", "manifest unknown"),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the image {image} was deleted from the registry's "
                        "catalog",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image "
                   "{image}: toomanyrequests: too many requests to "
                   "registry.invalid")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image "
                "{image}: manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull",
            issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            local_cause="the image {image} was built for a different CPU "
                        "architecture than this node runs",
            local_reason="the pull fails before the image layers are "
                         "fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  toomanyrequests: too many "
                   "requests to registry.invalid")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container "
                     "{init_container}",
            local_cause="the init container's image reference still names a "
                        "tag that was retired last release",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n"
                   "    State: Waiting\n    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  toomanyrequests: too many "
                   "requests to registry.invalid")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)


_RULED_SCENARIOS = (_RULED_NODE_1, _RULED_NODE_2, _RULED_PVC_1, _RULED_PVC_2,
                    _RULED_REGISTRY_1, _RULED_REGISTRY_2)


def ruled_scenarios() -> tuple[Propagation, ...]:
    """The six stories whose origin the rules pass itself decides (spec
    section 4). Not part of `trainable_scenarios()` -- the pool merge is a
    later task."""
    return _RULED_SCENARIOS
