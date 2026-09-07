# Final retrain coverage — design

**Date:** 2026-09-08
**Branch:** `final-retrain-coverage` (off `main` @ `f22c07c`)
**Status:** approved in chat in three sections; written here for review

## Why this slice exists

The 0907 model sat the frozen exam and was refused. Two deciders failed:
decider 1, and decider 5 in two of its three parts.

| Decider | Bar | 0907 result |
|---|---|---|
| 1. Contract validity | 263 of 263 valid JSON | **262 of 263** |
| 2. Decoy rate on the three probes plus `wrong_attribution` | low | met |
| 3. Length gap | signed gap ≤ 0.15, abstains below 0.5 | met |
| 4. Overconfidence | read with its denominator | not measured (small n) |
| 5a. False "shared" on the multi-workload probe | at most 1 of 19 | **2 of 19** |
| 5b. False "shared" on the decoy probe | at most 1 of 10 | met |
| 5c. Pairs where both halves are right | at least 7 of 10 | **4 of 9** |
| 6. Withdrawn | — | — |

The broken JSON was on a node-disk-pressure decoy half with three victims.
The model wrote the second and third verdicts inside the first one, closed
with `}}`, and then wrote a second summary. Every cause in it was right. The
shape was wrong. Across the exam and the wide probe, 4 of 6 three-verdict
node decoy answers were broken this way.

We measured why, rather than guessing.

- **Three-verdict decoys are rare in training.** 15 of the 24 trained
  scenarios have only 2 victims. 6 of the 7 node-scoped ones have 2. So a
  node decoy with three verdicts comes from one scenario, about 8 rows in
  all. The training verdict counts are 2 victims: 317 rows, 3 victims: 74,
  4 victims: 6.
- **The exam's reads use real kubectl layouts the training never shows.**
  The exam's node reads are a `Conditions:` table with `Taints:` under it.
  Its Deployment reads are a `Replicas:` line, a `Pods:` table and a
  `Last log:` line. Its registry read is a cluster-wide events summary,
  "12 pods across 5 namespaces report the same error". Its StorageClass
  read names the controller's readiness and the volumes bound in the last
  20 minutes. The trained cousins use one-line labels instead, such as
  "Process table: exhausted". Only node-memory-pressure's first variant
  has a `Conditions:` table.
- **The StorageClass read with a crashed controller is 0 of 7 on all three
  models.** The trained cousin says "controller 1/1 ready, Running; pool
  status: retired". The exam says "0/1 ready, CrashLoopBackOff" and "bound
  in the last 20m: 0". The model has never seen a crashed controller.
- **Capacity is not the limit.** The loss over the last 50 steps averaged
  0.0005. The model memorised the textbook. What it lacks is shapes, not
  room.
- **More threads do not help.** 16 threads and 32 threads took the same
  wall time on the smoke run. Time scales with rows only, about 8 seconds
  per example pass.

This is the last retrain. It must pass all six deciders in one run. So the
design is full coverage: many more scenarios, every exam read layout
taught, every scenario able to produce three verdicts, and a bigger
textbook so each scenario still gets enough pairs.

## What does not change

- **The exam is byte-identical.** `test_set()` draws only the six held-out
  scenarios. The 253-row pin and the 263-row pin stay. Adding trainable
  scenarios moves only `train` and `val`.
- **The held-out promise holds.** No trainable scenario shares a key or an
  answer sentence with an exam scenario. The tests that check this stay.
- **The recipe is the same.** Qwen3-0.6B, seed 17, 2 epochs, learning rate
  2e-4, batch 1, gradient accumulation 16, sequence length 4096, LoRA
  r16 / alpha 32 / dropout 0.05, checkpoint every 25 steps. CPU only, on
  the training host, 16 threads through the existing wrapper.
- **The deciders are the same.** No eval code moves. No new dependency. No
  schema moves.
- **The wide probe file is frozen.** It is reported, not regenerated.

## Approach chosen

Three approaches were weighed.

| | Cost | What we learn | Downside |
|---|---|---|---|
| **A. Full coverage (chosen)** — 24 new scenarios, widen 15, exam layouts on 12 existing scenarios, bigger textbook | about 28 hours of training, about 4 days of writing | whether the shape gap was the whole problem | the most data to write and review |
| B. Bigger model (Qwen3-1.7B) | about 80 hours, a new baseline | whether capacity mattered | the loss says it did not; every past number stops comparing |
| C. Six cousins only | about 23 hours | the same as A on a thin margin | 5c is 4 of 9 today, the bar is 7 of 10; a thin fix is a coin flip |

A is the recommendation and the user approved it.

**How close a new cousin may sit to an exam scenario.** The user chose:
same read shape, different fault, different answer sentence. A cousin uses
the exam's kubectl layout line for line. Its fault is a different thing
going wrong in that layout. Its shared cause is its own sentence, and the
tests keep every sentence unique across both pools.

## Section 1 — the 24 new scenarios

The pool grows from 24 to 48 trained scenarios. Every new scenario is added
to `_TRAINING_SCENARIOS` in `src/kubeagent_verdict/dataset/propagation.py`.
The exact Python lives in the plan. This section fixes what each one must
be.

### Rules every new scenario follows

The enforced rules are the module docstring's, and the suite fails on any
of them: a key shape disjoint from the exam six; a shared cause and a
distractor cause unique across the pool and different from every exam
answer; every local cause unique within the scenario and across the pool;
victims with kinds from `vocab.ISSUE_KINDS`; `pass_confidence` that varies
inside the scenario; `scope_field` agreeing with `blast_radius`; a
non-empty healthy origin read; at least four origin variants whose first
entry is the origin read and healthy content, with literal and distinct
first lines; a state word pair present in every variant of its half and
absent from the other; no banned identifier shape (no dotted quads, no
`http://` or `https://`, no "kubeconfig", no "/home/", no "@").

Three rules are new for this slice and hold for every new scenario:

1. **The first variant is the exam's layout.** Its broken and healthy
   content follow the matching exam read line for line: the same field
   names, the same order, the same column style. The cousin test reads the
   first variant, so this is what makes the check true.
2. **Every scenario has 3 or 4 victims.** Never 2. This is what lets the
   generator draw three-verdict rows from every scenario.
3. **The other variants keep the exam's field names but start differently.**
   The test that counts rendered variants matches on the first line, so no
   two variants of one scenario may share a first line. Variants may drop
   or reorder a field, add a line, or change the column spacing. They may
   not be the same rendering with different numbers.

The judgment rules from the docstring hold too, and the plan repeats them
in every task: put the state word where it stands on its own; write decoy
local causes a reader has to check; a victim read must be able to be true
beside the healthy origin; never reuse another scenario's reason skeleton;
never hard-code a namespace, node or workload name; render both halves and
read them.

State word pairs below are the tokens for `origin_state`. The match is a
substring match. A healthy token must not appear anywhere in a broken read,
and a broken token must not appear in a healthy read or in a victim read.

### Group A — node scope, `Conditions:` table with `Taints:` (6 scenarios)

Read label for all six: `describe node {node}`, the exam's exact label.
First variant layout, copied from the exam:

    Conditions:
      <Type>   <True|False|Unknown>   <Reason>   <message>
      Ready    True                   KubeletReady
    Taints:  <taint or <none>>

Only two of the six carry a real kubelet taint on the broken half. The
other four show `Taints:  <none>` on both halves. That is deliberate: the
condition line and its message are the cue, and the model must read them
rather than the taint line.

| Key | Broken condition line (first variant) | Healthy condition line | Taint on the broken half | State words (broken / healthy) | Victims |
|---|---|---|---|---|---|
| `node-network-unavailable` | `NetworkUnavailable  True  NoRouteCreated  route to the pod network is missing` | `NetworkUnavailable  False  RouteCreated  route to the pod network is installed` | `node.kubernetes.io/network-unavailable:NoSchedule` | missing / installed | 3: ContainerStartError, Unschedulable, ProbeFailure |
| `node-kernel-deadlock` | `KernelDeadlock  True  KernelHasDeadlock  task blocked for more than 120 seconds` | `KernelDeadlock  False  KernelHasNoDeadlock  no task blocked` | none | blocked / no task blocked | 3: ContainerStartError, ProbeFailure, RestartLoop |
| `node-readonly-filesystem` | `ReadonlyFilesystem  True  FilesystemIsReadOnly  root filesystem remounted read-only after an I/O error` | `ReadonlyFilesystem  False  FilesystemIsNotReadOnly  root filesystem is writable` | none | read-only / writable | 3: CrashLoopBackOff, ContainerStartError, VolumeMountError |
| `node-frequent-kubelet-restart` | `FrequentKubeletRestart  True  FrequentKubeletRestart  kubelet is flapping: 6 restarts in 20 minutes` | `FrequentKubeletRestart  False  NoFrequentKubeletRestart  kubelet is steady: 0 restarts in 20 minutes` | none | flapping / steady | 3: ProbeFailure, RestartLoop, ContainerStartError |
| `node-cordoned-draining` | `Ready  True  KubeletReady  kubelet is posting ready status` with `Unschedulable: true` above the table and an event line `NodeNotSchedulable  node {node} is cordoned and draining` | the same table with `Unschedulable: false` and an event line `NodeSchedulable  node {node} is accepting pods` | `node.kubernetes.io/unschedulable:NoSchedule` | cordoned / accepting | 3: Unschedulable, RestartLoop, Init:CrashLoopBackOff |
| `node-corrupt-overlay` | `CorruptDockerOverlay2  True  CorruptDockerOverlay2  overlay2 layer store is corrupt: cached layers unreadable` | `CorruptDockerOverlay2  False  NoCorruptDockerOverlay2  overlay2 layer store is intact` | none | corrupt / intact | 3: ContainerStartError, CrashLoopBackOff, Init:CrashLoopBackOff |

Shared cause sentences, one per scenario:

- `node-network-unavailable`: node {node} has no route to the pod network,
  so no pod placed there can get a sandbox
- `node-kernel-deadlock`: the kernel on node {node} has a deadlocked task,
  so every container operation on that node hangs
- `node-readonly-filesystem`: the root filesystem on node {node} is mounted
  read-only, so no container there can write to disk
- `node-frequent-kubelet-restart`: the kubelet on node {node} keeps
  restarting, so its pods keep losing probes and container starts
- `node-cordoned-draining`: node {node} is cordoned and draining, so its
  pods are being evicted and nothing new lands there
- `node-corrupt-overlay`: the container layer store on node {node} is
  corrupt, so containers there cannot start from cached image layers

Note on `node-cordoned-draining`: its `Ready` line is `True`. The exam's
node-not-ready shows `Ready Unknown`. The cousin teaches that a node can be
Ready and still be the shared cause. Its state cue is the `Unschedulable`
line and the taint.

### Group B — cluster scope, Deployment describe with `Replicas:`, `Pods:`, `Last log:` (4 scenarios)

Read label: `describe <namespace>/<name> (Deployment)`. Three live in
kube-system, so their labels start with `describe kube-system/` and end
with `(Deployment)`, which is what the cousin test looks for. First
variant layout, copied from the exam:

    Replicas:  <n> desired | <n> updated | <n> total | <n> available | <n> unavailable
    Pods:      <pod>   <ready>/<total>  <state>  <n> restarts
    Last log:  <one line>

| Key | Label | Broken half | Healthy half | State words | Victims |
|---|---|---|---|---|---|
| `external-secrets-operator-down` | `describe kube-system/external-secrets (Deployment)` | 0 available; pod `0/1  CrashLoopBackOff  7 restarts`; `Last log:  secret store unreachable: giving up after 5 attempts` | 1 available; pod `1/1  Running  0 restarts`; `Last log:  reconciled 42 ExternalSecrets, 0 errors` | unreachable / reconciled | 3: CreateContainerConfigError, Init:CreateContainerConfigError, ContainerStartError |
| `network-operator-down` | `describe kube-system/network-operator (Deployment)` | 0 available; pod `0/1  OOMKilled  5 restarts`; `Last log:  overlay reconcile halted: killed at 512Mi` | 1 available; pod `1/1  Running  0 restarts`; `Last log:  overlay reconcile idle: 3 nodes in sync` | halted / idle | 3: ProbeFailure, CrashLoopBackOff, Init:CrashLoopBackOff |
| `cert-manager-down` | `describe cert-manager/cert-manager (Deployment)` | 0 available; pod `0/1  CrashLoopBackOff  11 restarts`; `Last log:  lost leader lease, exiting` | 1 available; pod `1/1  Running  0 restarts`; `Last log:  holding leader lease, 0 certificates pending` | lost / holding | 3: ProbeFailure, CrashLoopBackOff, RestartLoop |
| `metrics-server-down` | `describe kube-system/metrics-server (Deployment)` | 0 available; pod `0/1  CrashLoopBackOff  8 restarts`; `Last log:  unable to fetch node metrics: scrape timeout` | 1 available; pod `1/1  Running  0 restarts`; `Last log:  scraped 3 nodes, 41 pods` | unable / scraped | 3: ProbeFailure, OOMKilled, RestartLoop |

Shared cause sentences:

- `external-secrets-operator-down`: the external-secrets operator is down,
  so the Secrets it syncs are no longer created and pods that mount them
  cannot start
- `network-operator-down`: the network operator keeps being OOM-killed, so
  the pod overlay network is no longer reconciled and pods on different
  nodes cannot reach each other
- `cert-manager-down`: cert-manager is down, so certificates near expiry
  are not renewed and the workloads serving them fail their TLS checks
  once they lapse
- `metrics-server-down`: metrics-server is down, so every autoscaler is
  frozen at its last size and overloaded pods are not scaled out

One change from the chat design: `network-operator-down` was described in
chat as "pod address allocation stopped". That is the same effect as the
trained `cni-ip-pool-exhausted`, and two cluster-scoped scenarios must not
share a cause shape. Its effect is now the overlay network, which no other
scenario claims.

### Group C — cluster scope, cluster-wide events summary (4 scenarios)

Read label: `get_events (cluster-wide, reason=<Reason>)`, the exam's label
shape with a different reason. First variant layout, copied from the exam:

    <N> pods across <M> namespaces report the same error:
      <the error line>
    distinct <things> in the failing set: 1

Healthy half, copied from the exam's shape:

    pods reporting <this kind of error> name no <thing> in common, and
    no two of them fail the same way: <a>, <b>, <c>
    distinct <things> in the failing set: one per failing pod

| Key | Reason | Broken error line | Distinct thing | Healthy "no two fail the same way" list | State words | Victims |
|---|---|---|---|---|---|---|
| `shared-nfs-server-down` | `FailedMount` | `MountVolume.SetUp failed: mount.nfs: Connection timed out` | NFS servers | wrong fs type, permission denied, no such export | timed out / one per failing pod | 3: VolumeMountError, VolumeAttachError, ContainerStartError |
| `cluster-maintenance-taint` | `FailedScheduling` | `0/3 nodes are available: 3 node(s) had untolerated taint {maintenance: true}` | taints (healthy line reads `distinct taints in the failing set: none`) | insufficient cpu, node affinity mismatch, unbound claim | maintenance / none | 3: Unschedulable, Unschedulable, Unschedulable |
| `shared-gateway-refusing` | `Unhealthy` | `Readiness probe failed: upstream gateway: connection refused` | upstream gateways | HTTP 500, timeout, missing path | refused / one per failing pod | 3: ProbeFailure, ProbeFailure, CrashLoopBackOff |
| `runtime-class-removed` | `FailedCreatePodSandBox` | `Failed to create pod sandbox: no runtime for "sandboxed" is configured` | runtime handlers | cgroup limit, seccomp profile missing, hostPort in use | no runtime / one per failing pod | 3: ContainerStartError, ContainerStartError, ContainerStartError |

Shared cause sentences:

- `shared-nfs-server-down`: the shared NFS server is down, so every pod
  that mounts a volume from it is stuck at mount
- `cluster-maintenance-taint`: every node carries a maintenance taint no
  workload tolerates, so no new pod can be scheduled anywhere
- `shared-gateway-refusing`: the shared API gateway refuses connections,
  so every pod whose readiness check calls through it fails its probe
- `runtime-class-removed`: the sandboxed RuntimeClass handler was removed
  from the nodes, so every pod that asks for it fails to create its
  sandbox

Two scenarios repeat one kind across all three victims. A taint that
blocks scheduling can only produce Unschedulable pods, and a missing
runtime handler can only produce pods that never start. Repeating the kind
is honest there. The three victims differ in workload kind and in local
cause, which is what the decoy half needs.

### Group D — cluster scope, StorageClass with `provisioner:`, controller line, `bound in the last 20m` (5 scenarios)

Read label: `get_related storageclass <name>`, the exam's label shape. The
class names are new: `block-ssd`, `archive-hdd`, `encrypted-ssd`,
`bulk-nvme`, `replicated-ssd`. Never `standard` (the exam's), `fast-ssd`
or `ssd-premium` (already trained). Provisioners are `example.com/<x>-csi`
and controllers live in `storage-system/<x>-csi-controller`. First variant
layout, copied from the exam:

    provisioner: example.com/<x>-csi
    controller storage-system/<x>-csi-controller: <n>/<n> ready, <state>
    <one extra line, see table>
    PersistentVolumes bound in the last 20m: <n>

This group is the direct answer to the storage-provisioner-down read that
scored 0 of 7 across three models. All five share the effect "no new
volume binds" and differ in the fault. That is what the closeness rule
allows: same read shape, different fault, different answer sentence.

| Key | Class | Broken controller line and extra line | Healthy controller line and extra line | Bound (broken / healthy) | State words | Victims |
|---|---|---|---|---|---|---|
| `csi-controller-oomkilled` | block-ssd | `0/2 ready, OOMKilled`; `last restart: 40s ago, exit 137` | `2/2 ready, Running`; `last restart: none in 7d` | 0 / 5 | OOMKilled / Running | 3: Unschedulable, Unschedulable, VolumeMountError |
| `csi-controller-unschedulable` | archive-hdd | `0/1 ready, Pending (node selector matches no node)`; `node selector: storage-tier=archive` | `1/1 ready, Running`; `node selector: storage-tier=archive (1 node)` | 0 / 3 | matches no node / Running | 3: Unschedulable, Unschedulable, Init:CrashLoopBackOff |
| `provisioner-credentials-rotated` | encrypted-ssd | `1/1 ready, Running`; `last provision error: backend refused credentials (401)` | `1/1 ready, Running`; `last provision error: none` | 0 / 6 | refused credentials / none | 3: Unschedulable, Unschedulable, VolumeAttachError |
| `storage-backend-full` | bulk-nvme | `1/1 ready, Running`; `backend capacity: out of space (0 GiB free of 4 TiB)` | `1/1 ready, Running`; `backend capacity: space remaining 1.9 TiB of 4 TiB` | 0 / 4 | out of space / space remaining | 3: Unschedulable, Unschedulable, VolumeAttachError |
| `csi-driver-version-mismatch` | replicated-ssd | `1/1 ready, Running`; `driver API: controller v2, node plugins v1 (mismatch)` | `1/1 ready, Running`; `driver API: controller v2, node plugins v2, in step` | 0 / 5 | mismatch / in step | 3: VolumeMountError, VolumeAttachError, ContainerStartError |

Three of the five show a healthy-looking controller (`1/1 ready, Running`)
on the broken half. The cue sits in the extra line and in the bound
count. This is deliberate: it teaches that "the controller is Running" is
not the same as "the class works".

Shared cause sentences:

- `csi-controller-oomkilled`: the block-ssd CSI controller is OOM-killed
  on every start, so no claim on that class gets a volume
- `csi-controller-unschedulable`: the archive-hdd CSI controller cannot
  be scheduled, so claims on that class are never provisioned
- `provisioner-credentials-rotated`: the encrypted-ssd provisioner's
  backend credentials were rotated, so the backend refuses every new
  volume request
- `storage-backend-full`: the bulk-nvme storage backend is out of space,
  so the provisioner cannot carve a new volume for any claim on that
  class
- `csi-driver-version-mismatch`: the replicated-ssd CSI controller was
  upgraded ahead of its node plugins, so volumes it provisions cannot be
  staged on any node

The `Unschedulable` victims are pods whose PersistentVolumeClaim never
binds, so the scheduler will not place them. Their victim reads must say
"unbound PersistentVolumeClaim" and must not name the class's controller
state, because the same read has to be true beside the healthy origin.

### Group E — namespace scope, NetworkPolicy with `podSelector:`, `policyTypes:`, rules, `pods selected:` (5 scenarios)

Read label: `get_related networkpolicy {ns}/<name>`, the exam's label
shape. First variant layout, copied from the exam:

    podSelector: <selector or empty (selects every pod in the namespace)>
    policyTypes: <Ingress|Egress|Ingress, Egress>
    <rule lines>
    pods selected: <n> of <n>

| Key | Policy name | Broken half (after the podSelector line) | Healthy half | State words | Victims |
|---|---|---|---|---|---|
| `networkpolicy-dns-egress-missing` | `{ns}/egress-to-app` | `podSelector: empty (selects every pod in the namespace)`; `policyTypes: Egress`; `egress: allow to app=backend tcp/8080`; `DNS udp/53 allowed: no`; `pods selected: 6 of 6` | same, plus `egress: allow to kube-system udp/53`; `DNS udp/53 allowed: yes` | allowed: no / allowed: yes | 3: CrashLoopBackOff, ProbeFailure, Init:CrashLoopBackOff |
| `networkpolicy-namespace-label-drifted` | `{ns}/egress-to-messaging` | `podSelector: app=orders`; `policyTypes: Egress`; `egress: allow to namespaceSelector team=messaging tcp/5672`; `namespaces matched: 0 (matches no namespace; label renamed)`; `pods selected: 3 of 6` | same rule; `namespaces matched: 1 (the messaging namespace)` | no namespace / messaging namespace | 3: CrashLoopBackOff, Init:CrashLoopBackOff, ProbeFailure |
| `networkpolicy-port-mismatch` | `{ns}/egress-to-cache` | `podSelector: role=worker`; `policyTypes: Egress`; `egress: allow to app=cache tcp/6379`; `cache listening port: 6380`; `port match: no`; `pods selected: 5 of 6` | `egress: allow to app=cache tcp/6380`; `port match: yes` | port match: no / port match: yes | 3: CrashLoopBackOff, ProbeFailure, RestartLoop |
| `networkpolicy-allow-selector-typo` | `{ns}/allow-frontend-egress` | `podSelector: role=fronted (selects no pod)`; `policyTypes: Egress`; `egress: allow to app=api tcp/443`; `pods selected: 0 of 6`; `baseline: default-deny egress applies to the 6 unselected pods` | `podSelector: role=frontend (selects every frontend pod)`; `pods selected: 6 of 6`; `baseline: default-deny egress applies to 0 unselected pods` | selects no pod / every frontend pod | 3: CrashLoopBackOff, ProbeFailure, Init:CrashLoopBackOff |
| `networkpolicy-ingress-deny-all` | `{ns}/deny-all-ingress` | `podSelector: empty (selects every pod in the namespace)`; `policyTypes: Ingress`; `ingress: [] (no rules — all ingress denied)`; `pods selected: 6 of 6` | `podSelector: app=legacy-batch`; `policyTypes: Ingress`; `ingress: allow from podSelector app=scheduler`; `pods selected: 1 of 6` | all ingress denied / allow from | 3: CrashLoopBackOff, ProbeFailure, RestartLoop |

Shared cause sentences:

- `networkpolicy-dns-egress-missing`: the egress policy in {ns} allows no
  DNS traffic, so every pod there fails to resolve any name
- `networkpolicy-namespace-label-drifted`: the egress policy in {ns}
  names the messaging namespace by a label that was renamed, so no pod
  there can reach the message broker
- `networkpolicy-port-mismatch`: the egress policy in {ns} opens the
  cache's old port, so every connection to its new port is dropped
- `networkpolicy-allow-selector-typo`: the {ns} frontend allow policy has
  a typo in its pod selector, so it selects nothing and the namespace's
  default-deny blocks every frontend pod's egress
- `networkpolicy-ingress-deny-all`: a deny-all ingress policy in {ns}
  blocks every inbound connection, so pods there that need their peers
  or their callers cannot become ready

Two notes on this group:

- `networkpolicy-allow-selector-typo` turns the exam's healthy cue (`pods
  selected: 0 of 6`) into a broken cue. The model has to read the
  selector and the baseline line, not just the count. That is the point.
- `networkpolicy-ingress-deny-all` is the closest cousin to the exam's
  networkpolicy-deny-all: same layout, Ingress instead of Egress, a
  different answer sentence. This was raised in chat and accepted under
  the closeness rule.

One change from the chat design: `networkpolicy-port-mismatch` was
described in chat as a datastore port. The trained
`networkpolicy-egress-allowlist-stale` already names a datastore, and two
namespace-scoped scenarios must not lean on the same dependency. The
dependency is now a cache.

### Kind coverage after the change

All 16 issue kinds stay covered. The 24 new scenarios carry 72 victims
between them. By kind: Unschedulable 13, ProbeFailure 13,
ContainerStartError 11, CrashLoopBackOff 10, RestartLoop 7,
Init:CrashLoopBackOff 7, VolumeMountError 4, VolumeAttachError 4,
CreateContainerConfigError 1, Init:CreateContainerConfigError 1,
OOMKilled 1. The five kinds no new scenario uses (ImagePullBackOff,
ErrImagePull, Init:ImagePullBackOff, Init:ErrImagePull, Init:OOMKilled)
are already covered by the trained 24 and stay covered. The plan may move
a kind between two new scenarios if a victim read cannot be written
honestly, as long as the pool test that every kind appears at least once
still passes.

## Section 2 — the existing 24, the generator, the shares, the tests, the docs

### 2a. Every two-victim scenario gets a third victim

15 of the trained 24 have exactly 2 victims. The generator draws a
three-verdict decoy only from a scenario with 3 or more victims, so those
15 never produce one. Each gets a third victim.

The rule for the third victim: pick a kind the scenario does not yet use,
where the origin can honestly cause it. If no such kind is honest, repeat
a kind the scenario already has and vary the workload kind and the local
cause. The third victim's read must be true beside the healthy origin,
like every other victim read.

| Scenario | Has | Third victim | Why |
|---|---|---|---|
| `kube-proxy-degraded` | CrashLoopBackOff, ProbeFailure | Init:CrashLoopBackOff | an init container that waits on a Service address never gets one |
| `shared-secret-key-renamed` | CreateContainerConfigError, CrashLoopBackOff | Init:CreateContainerConfigError | an init container that reads the same key fails the same way |
| `cluster-autoscaler-at-capacity` | Unschedulable, Unschedulable | Unschedulable (repeat; a Job) | a blocked autoscaler produces only Pending pods |
| `shared-base-image-tag-moved` | CrashLoopBackOff, ContainerStartError | Init:CrashLoopBackOff | an init container built on the moved base fails at start |
| `shared-pvc-multi-attach` | VolumeAttachError, VolumeMountError | ContainerStartError | the container waits on a volume that never attaches |
| `cni-ip-pool-exhausted` | ContainerStartError, Unschedulable | ContainerStartError (repeat; a Job) | no address means no sandbox, in any workload kind |
| `csi-node-driver-crashed` | VolumeMountError, CrashLoopBackOff | VolumeAttachError | the node plugin cannot stage, so the attach never completes |
| `node-pid-pressure` | ContainerStartError, RestartLoop | CrashLoopBackOff | a process that cannot fork exits and restarts |
| `node-runtime-restarting` | RestartLoop, ProbeFailure | ContainerStartError | a container created while the runtime is down never starts |
| `node-clock-skew` | CrashLoopBackOff, ProbeFailure | Init:CrashLoopBackOff | an init container that checks a token's validity window fails |
| `node-conntrack-full` | ProbeFailure, CrashLoopBackOff | RestartLoop | a pod whose outbound connections drop restarts on its own health loop |
| `namespace-limitrange-lowered` | OOMKilled, Init:OOMKilled | CrashLoopBackOff | a container below its working set is killed and restarts |
| `namespace-egress-proxy-down` | ProbeFailure, CrashLoopBackOff | Init:CrashLoopBackOff | an init container that fetches through the proxy fails |
| `namespace-shared-pvc-full` | CrashLoopBackOff, ProbeFailure | RestartLoop | a writer that hits a full disk exits and restarts |
| `namespace-migration-lock-held` | Init:CrashLoopBackOff, CrashLoopBackOff | ProbeFailure | a pod that came up before the lock and now cannot reach the schema fails its probe |

After this change every scenario in the pool has 3 or 4 victims. A new
test pins that.

### 2b. Eleven existing scenarios get one exam-layout variant

The exam's layouts appear in training only if a trained scenario renders
them. Eleven existing scenarios gain one variant in the matching exam
layout, and a twelfth gets a one-word spelling fix. The variant is not the first variant, so the legacy pair does not
move. Its first line must be unique inside its scenario, and it must
carry the scenario's state words. The plan writes the exact text.

| Scenario | Layout | Broken variant, in short | Healthy variant, in short |
|---|---|---|---|
| `node-pid-pressure` | Conditions + Taints | `PIDPressure  True  KubeletHasInsufficientPID  process table exhausted`; `Taints:  node.kubernetes.io/pid-pressure:NoSchedule` | `PIDPressure  False  KubeletHasSufficientPID  pids available`; `Taints:  <none>` |
| `kube-proxy-degraded` | Conditions + Taints | healthy table; `Taints:  <none>`; `kube-proxy: Service routes stale (last sync 41m ago)` | same table; `kube-proxy: Service routes fresh (last sync 12s ago)` |
| `csi-node-driver-crashed` | Conditions + Taints | healthy table; `Taints:  <none>`; `CSI node plugin: crashed (CrashLoopBackOff, 9 restarts)` | same table; `CSI node plugin: healthy (Running, 0 restarts)` |
| `node-runtime-restarting` | Conditions + Taints | `Ready  False  KubeletNotReady  container runtime is restarting (PLEG not healthy)`; `Taints:  node.kubernetes.io/not-ready:NoSchedule` | `Ready  True  KubeletReady  container runtime is stable`; `Taints:  <none>` |
| `node-clock-skew` | Conditions + Taints | healthy table; `Taints:  <none>`; `System clock: skewed by 340s (ntp unsynchronised)` | same table; `System clock: synced (offset 4ms)` |
| `node-conntrack-full` | Conditions + Taints | healthy table; `Taints:  <none>`; `Conntrack: full (262144 of 262144 entries)` | same table; `Conntrack: clear (31200 of 262144 entries)` |
| `pod-identity-webhook-down` | Replicas / Pods / Last log | `0 available`; `0/1  CrashLoopBackOff  6 restarts`; `Last log:  webhook down: listener failed to bind` | `1 available`; `1/1  Running  0 restarts`; `Last log:  serving admission requests, 0 errors` |
| `shared-dependency-scaled-to-zero` | Replicas / Pods / Last log | `0 desired \| 0 updated \| 0 total \| 0 available \| 0 unavailable`; `Pods:      <none>`; `Last log:  deployment scaled replicas to 0 (manual)` | `2 desired … 2 available`; `1/1  Running  0 restarts`; `Last log:  serving, 2 of 2 Running` |
| `namespace-egress-proxy-down` | Replicas / Pods / Last log | `0 available`; `0/1  CrashLoopBackOff  12 restarts`; `Last log:  restarting: upstream config invalid` | `1 available`; `1/1  Running  0 restarts`; `Last log:  steady, 0 errors in 1h` |
| `storageclass-pool-retired` | StorageClass | `provisioner: example.com/ssd-csi`; `controller storage-system/ssd-csi-controller: 1/1 ready, Running`; `pool status: retired`; `PersistentVolumes bound in the last 20m: 0` | same two lines; `pool status: online`; `bound in the last 20m: 5` |
| `networkpolicy-egress-allowlist-stale` | NetworkPolicy | `podSelector: role=worker`; `policyTypes: Egress`; `egress: allow to app=datastore-v1 tcp/5432 (datastore pods now labelled app=datastore-v2)`; `connections to datastore: blocked`; `pods selected: 6 of 6` | `egress: allow to app=datastore-v2 tcp/5432`; `connections to datastore: allowed` |
| `node-memory-pressure` | Conditions + Taints | already renders the table and `Taints:  node.kubernetes.io/memory-pressure:NoSchedule`; no new variant | its healthy `Taints:  none` becomes `Taints:  <none>`, the exam's spelling, in both variants that carry it |

Six node scenarios, three Deployment scenarios, one StorageClass, one
NetworkPolicy, plus the spelling fix on `node-memory-pressure`. Together
with the new 24, every exam layout is rendered by at least 4 scenarios
in the pool, and the node layout by 13. The exact floors are in 2e.

The state words are the scenario's existing pair. The variant text must
contain the broken token on the broken half and the healthy token on the
healthy half. For `kube-proxy-degraded` that is "stale" and "fresh"; the
kube-proxy line above carries them. The plan checks each pair against the
existing `origin_state` before writing the variant.

### 2c. The mix and the build size

`CASE_MIX` in `src/kubeagent_verdict/dataset/generate.py` changes in
three entries and nowhere else:

| Case | Now | After |
|---|---|---|
| `attributed` | 18 | 10 |
| `shared_origin` | 8 | 12 |
| `shared_origin_decoy` | 8 | 12 |

The other seven entries do not move. The total stays 100.

The build size for the run moves from 5500 to 8000. Reasoning, in
numbers:

- at 12 percent, each shared half is 960 rows of 8000
- 960 rows over 48 scenarios is 20 pairs per scenario
- after the 90/10 split about 18 pairs per scenario land in train
- the floor test asks for at least 12 pairs per scenario in train; 18
  clears it with room

The victim draw does not change. The exam is byte-identical. The wide
probe file is frozen. The cousin probe is regenerated over all 48
scenarios: one fresh pair per scenario, 48 pairs, 96 rows.

### 2d. Measured shares at the new mix

These were measured on the current pool of 24 at the new mix. They depend
only on the mix and the fixed cull set, not on which scenarios are in the
pool, so they hold at 48 too.

| Share | Size 800 | Size 8000 | Band today |
|---|---|---|---|
| shared answer among multi-workload rows (kept) | 0.373 | 0.385 | at most 0.40 |
| independent share, emitted | 0.568 | 0.566 | 0.55 to 0.75 |
| independent share, kept | 0.551 | 0.546 | 0.55 to 0.70 |

The kept-pile independent share sits at 0.546 at size 8000. The band's
floor is 0.55. That is 0.004 under. The floor is restated to 0.52. This
still fails the three degenerate cases the band exists to catch: a pile
of only independent rows (1.00), a pile of only shared rows (0.00), and a
pile where every decoy row pairs with a shared row and nothing else
(0.50). The docstring numbers move with it: 0.34 becomes 0.373 and 0.385,
0.595 becomes 0.568, 0.565 becomes 0.551. This was found while writing
the spec, not designed in chat.

### 2e. Tests

The suite must fail on every regression this slice could introduce. The
changes, by file:

`tests/test_shared_origin_training.py`

- The pool pin moves from 24 to 48, with the reason in the docstring.
- The cousin test keeps its label and first-variant checks and gains
  per-layout floors counted over every variant of every scenario:
  - node reads with a `Conditions:` table and a `Taints:` line: at
    least 13 scenarios
  - `describe kube-system/… (Deployment)` reads with a `Replicas:`
    line: at least 4 scenarios
  - `get_events (cluster-wide, reason=…)` labels: at least 4 scenarios
  - StorageClass reads with `bound in the last`: at least 6 scenarios
  - NetworkPolicy reads with `podSelector:`: at least 6 scenarios
- New: every trainable scenario has at least 3 victims.
- New, at the build size: among shared_origin_decoy rows, at least 40
  percent carry 3 or more verdicts, and node-scoped decoy rows with 3 or
  more verdicts come from at least 5 different scenarios.
- The floor test's SIZE moves to 8000 and FLOOR stays 12.
- The kept-pile independent band floor moves from 0.55 to 0.52; the
  docstring numbers move as in 2d.
- Every docstring that says "twenty-four" says "forty-eight".
- The `BIG` comment is stale today: it still says 4 percent and 22 draws
  per scenario, though the mix has been 8 percent since the floor merge.
  It is restated once, at 12 percent and 48 scenarios: each half is 1584
  rows of 13200, which is 33 draws per scenario. The docstring's odds move
  with it: fewer than 3 distinct variants in 33 uniform draws from 4 is
  about 7 in 10 billion per scenario, about 3 in 100 million across the
  pool. The formula is (6 times 2 to the n, minus 8) over 4 to the n.

`tests/test_generate.py`

- `test_counts_for_follows_the_mix` at size 1000: `attributed` 100,
  `shared_origin` 120, `shared_origin_decoy` 120. The other seven counts
  do not move. The test-set slice counts do not move.

`tests/test_evidence_overlap.py`

- SIZE moves from 5500 to 8000.
- Every row of `DECLARED` is re-measured at seed 17 and size 8000 and
  re-justified in its comment. A row that no longer holds is fixed in the
  data or the declared number moves with a reason. The file's own comment
  says the numbers are deterministic at exactly one seed and size, so
  moving the size means re-measuring all of them.

`tests/test_propagation.py`

- No new rule. The existing rules run over 48 scenarios. Every new
  scenario and every new variant passes them.
- The module docstring of `propagation.py` says "twenty-four scenarios
  taught in equal shares". It says forty-eight.

Every test above must fail before its change lands and pass after. A test
that could not fail on the tree it replaces is not a test.

### 2f. Docs

All in simple voice. Numbers explained.

Lines that state the current recipe change. Lines that narrate a past
decision (what 4 percent gave, what 7 percent was tried at) stay as they
are, because they were true when they were written and still are.

- `docs/runbooks/train.md`: the build command becomes
  `kv-dataset --seed 17 --size 8000 --out out/dataset`, and "train+val ≤
  5500" becomes "train+val ≤ 8000". The six deciders do not move.
- `README.md`: the build command and the dataset line say 8000.
- `docs/design.md`: the floor-test line and the row-count line say
  8000; the shares line says 10 / 12 / 12.
- `docs/how-training-works.md`: the mix table says 10 / 12 / 12; "The
  pool is now twenty-four" says forty-eight; a new section after
  "Covering the exam's read kinds" and before the glossary explains, in
  simple voice, what the 0907 model got wrong and what this change does
  about it: the broken JSON on three-verdict decoys, the exam layouts
  training never showed, the storage read at 0 of 7, and the four
  measured bullets from "Why this slice exists".
- The training doc's list of possible outcomes did not foresee the 0906
  and 0907 results. That list is updated in the same new section.
- `docs/model-card.md` keeps its historical line about size 5500. It
  describes an older tree, and it is still true of that tree.

## Section 3 — the run

### Order of work

1. Merge `shared-origin-floor` into `main`. Done: `main` is at `f22c07c`.
2. This spec, on branch `final-retrain-coverage`, reviewed by the user.
3. The implementation plan, from this spec, with the full Python for
   every new scenario, every third victim and every new variant, in the
   style of the `_T_NODE_PID_PRESSURE` record.
4. Execution by subagent-driven development: a fresh implementer and an
   independent reviewer per task, both on a mid model; TDD; every commit
   signed off; a whole-branch review on the most capable model; then the
   finishing menu, where the user picks merge, PR or keep.
5. On the training host, at the finished commit:
   - build the dataset with `kv-dataset --seed 17 --size 8000 --out
     out/dataset`
   - read `out/dataset/manifest.json` and report train, val and kept
     counts
   - run the floor test on the host and report it
6. Encode every train row with the training tokenizer at the run's
   maximum length of 4096. Report how many rows would be dropped. The
   number must be 0. If it is not, the fix is in the data, never in the
   length.
7. Report steps 5 and 6. Launch only after the user says go.
8. The retrain: the same recipe as 0907 (same base model, same LoRA
   rank, same learning rate, same 2 epochs, same seed), 16 threads through
   the wrapper, a dated adapter directory, refusing to overwrite, with a
   meta file that names the dataset commit and the manifest hash.
9. Export to a dated `dist-retrain-<date>/` directory. Never `dist/`.
10. The exam (263 rows), the wide probe (60 rows) and the new cousin
    probe (96 rows), all through kv-eval with an explicit endpoint.
11. The six-decider report, in simple voice.

Steps 5 to 11 happen on the training host. Nothing trains on the
workstation. No subagent runs kv-train, kv-export or the chaos harness.

### Time

| Piece | Rows | Estimate |
|---|---|---|
| training | about 6332 kept rows, 2 epochs, about 8 s per row pass | about 28 hours |
| exam | 263 | about 25 minutes |
| wide probe | 60 | about 6 minutes |
| cousin probe | 96 | about 10 minutes |

The estimate comes from the 0907 run, which took about 8 seconds per
example pass at 16 threads. 16 and 32 threads gave the same wall time
there. Check every 30 minutes; report loss, step, and elapsed time.

### What passes

All six deciders on the frozen exam in one run, as the runbook defines
them:

| Decider | Bar |
|---|---|
| 1. contract validity | 263 of 263 |
| 2. decoy rate | low on the three probe cases and on wrong_attribution, as the runbook defines low |
| 3. length gap | signed gap at most 0.15; abstains when the length-helps count is under 0.5 |
| 4. overconfidence | as the runbook defines it; "not measured" at small n |
| 5. false shared | at most 1 of 19 on multi_misattribution_probe and at most 1 of 10 on shared_origin_decoy_probe; paired both-right at least 7 of 10 |
| 6. withdrawn | nothing to check |

The wide probe and the cousin probe are reported beside the deciders.
They do not decide. A model that passes the exam and scores badly on a
probe passes, and the report says both.

### Risks, stated plainly

- Decider 5c asks for 7 of 10 pairs both right. The 0907 model got 4 of
  9. This is the biggest jump asked of one retrain.
- The storage-provisioner-down pairs scored 0 of 7 across three models.
  Group D is the answer, and it has not been tested on any model yet.
- Three-verdict decoys were rare in 0907's data. The new pool makes them
  common. Whether that is enough to fix the JSON shape is the run's
  question, not something the data can prove.
- A bigger build takes longer to train. 28 hours is an estimate from one
  run.

### If it fails

The same report as before: every decider with its number, the wide and
cousin probes, and a plain list of which rows failed and how. The next
step is the user's. Nothing in this spec authorises a second retrain.

## Rejected and out of scope

- **A larger base model (1.7B).** Rejected in chat. The 0907 loss was
  0.0005, so capacity is not the limit. A bigger model doubles the time
  and changes the recipe, which breaks comparability with every run so
  far.
- **Only six close cousins, one per exam scenario.** Rejected in chat. It
  would teach the exam's six shapes and nothing else, and a model that
  has seen one cousin per shape has not learned to read the shape.
- **Grounding the rationale on the read.** Out of scope. It would change
  the answer contract, and the contract is frozen with the exam.
- **A GPU run.** Ruled out earlier. The venv's torch is CPU-only, the
  device is not in the resume fingerprint, and a GPU run would not
  compare with the CPU runs.
- **Changing the exam, the wide probe, the deciders or any schema.**
  Never. Listed under "What does not change".
- **A new dependency.** None.
