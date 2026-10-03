# Shared-origin rewrite (Spec 4b-1) — design

**Date:** 2026-10-03
**Branch:** `spec4b1-shared-origin` (cut off `main` @ `ff6527e`)
**Status:** draft, for review

## What this is

Spec 4b is split into four specs. Each gets its own branch, in this
order:

1. **4b-1, this spec:** rewrite the shared-origin family.
2. **4b-2:** gold that says more than its prompt, in the other families.
3. **4b-3:** `multi` rows and decoys.
4. **4b-4:** grader leftovers.

The shared-origin family is four cases:

- `shared_origin` and `shared_origin_decoy`: the broken and healthy twins
  in train and val;
- `shared_origin_probe` and `shared_origin_decoy_probe`: the same pair on
  the exam.

In `out/dataset-0929` they are 2,420 of 7,427 rows: 1,200 + 1,200 in
train and val, and 10 + 10 on the exam.

4b-1 has seven parts:

1. Each story becomes a small cluster, built from objects, in two worlds.
   47 stories stay. 13 go.
2. One real pipeline builds each row: kubeagent's report order, one
   gather, the rules over every candidate, then the renderer. The
   hand-typed reads and the hand-typed candidate menu go.
3. `render.cluster_health` becomes a copy of kubeagent's
   `clusterhealth.Assess`.
4. Gold is set for each rendered row from anchors in its own lines. A
   row whose own lines don't show why gets `none_of_these`. The job-3
   label follows what the prompt shows.
5. Two new Go capture fixtures check the new lines against kubeagent
   v1.24.0, byte for byte.
6. The checker exemption goes. B7 is rewritten. The system-line pattern
   is fixed.
7. The mix keeps its shares. The test-only `BIG` changes so every story
   gets a whole share.

Then: a new build, three hashes moved by hand, and the docs.

The bars do not move: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9.

## Why

### The prompts show lines kubeagent never prints

Today `_render_shared_origin` (`cases.py:920-1123`) skips the gather. It
types the inventory, a 3-line candidate menu, and an "origin read" by
hand. kubeagent v1.24.0 prints none of these.

The checker knows it. `EXEMPT_CASES` (`checker.py:179-196`) skips the
evidence rules and the propagation text rules for these four cases.
Take the skip away and 10 rules fire on today's rows.

There is a second bug in the same code. The rules decide each victim
over one object, while the prompt shows three candidates. So the
"decided by rules" line and the menu can disagree.

### Gold says more than its prompt

Many gold answers name a cause the victim's own lines never show.
PIN.md (`:420-421`) counts 14 such victims. The real count is 20.
Model-card limit 9 says the same thing about rationales: they quote
reads the prompt never shows.

A model trained on these rows learns to name a cause it cannot see.

### The label follows the story, not the prompt

Every plain broken twin gets the same "none" summary, whatever its
prompt shows. Model-card limit 6 describes this. A prompt where two
victims' own events point at the origin is graded the same as one where
nothing does.

### 12 stories show their origin only in the invented read

For 12 stories, the only line that names the origin is the hand-typed
origin read. With real lines, nothing in the prompt points at the
origin at all. These are the "X stories" listed under Design §1.

## What stays the same

- **The grader.** No change to `evals/score.py` or `contract.py`. No
  must-not word is added.
- **The checker's rule count:** 50.
- **Every other family keeps its exact bytes.** The generator still draws
  exactly one number from the main random stream per shared-origin pair
  (the `salt`), so every later family draws the same values. The
  train/val split is a hash of the row's group, so no other row changes
  split. A test checks the exam's 229 rows from other families stay
  byte-identical.
- **The exam stays 249 rows.** Only its 20 family rows change.
- **No 0920 replay in 4b-1.** See "The build and the re-pin".
- **The kubeagent repo is read-only.** Captures run from a `git archive`
  copy in a scratch folder.
- **`multi` keeps `origin_read_label`.** 244 `multi` rows use it, and
  `multi` belongs to 4b-3.
- **The ruled share:** 1 shared-origin pair in 5 still comes from the
  ruled pool.

## Design

### 1. The story set

Each story is now classed by what kubeagent's rules really do with its
objects. The class is not the author's choice.

**R stories: the rules confirm one cause on 2+ victims.** That needs
three things, all from the Go code:
- a candidate of kind node, PVC or registry (the only three kinds
  `check` handles);
- a fresh read that confirms it;
- a group key that 2+ victims share (`shared.go`, `group`). A node
  groups by node name and a registry by host. A PVC groups by
  `storageclass/<class>/<reason>`, but only for the reasons
  `ProvisionerNotResponding` and `MissingStorageClass` with a plain
  class name. Every other PVC reason groups per claim, and one claim is
  one victim.

**P stories: everything else.** Their victims may still get candidates,
but the rules never group 2+ of them.

Six stories looked like R and stay P, checked against the Go code:
- **image-pull-secret-expired:** an auth error in a pull event is
  `Unverified` ("that can be one image or the whole host"), never
  confirmed.
- **storageclass-pool-retired, provisioner-credentials-rotated,
  storage-backend-full:** the PVC reason is `ProvisioningFailed`, which
  groups per claim.
- **csi-controller-oomkilled, csi-controller-unschedulable:** no PVC
  candidate reaches the victims.

They do start getting real candidates through the gather. They just
never reach a shared group.

**What stays: 47 stories, 38 P and 9 R.** 3 stay as they are and 44
change.

| Group | Stories |
|---|---|
| R (9) | node-kubelet-halted, node-kubelet-unresponsive, node-not-ready\*, pvc-provisioner-not-responding, pvc-storageclass-missing, registry-mirror-unreachable, registry-rate-limited, registry-unreachable\*, storage-provisioner-down\* |
| P, unchanged (3) | node-corrupt-overlay, node-network-unavailable, node-runtime-restarting |
| P, with edits (35) | cert-manager-down, cluster-maintenance-taint, cni-ip-pool-exhausted, coredns-down\*, csi-controller-oomkilled, csi-controller-unschedulable, csi-driver-version-mismatch, csi-node-driver-crashed, external-secrets-operator-down, image-pull-secret-expired, metrics-server-down, namespace-egress-proxy-down, namespace-limitrange-lowered, network-operator-down, networkpolicy-allow-selector-typo, networkpolicy-deny-all\*, networkpolicy-dns-egress-missing, networkpolicy-egress-allowlist-stale, networkpolicy-ingress-deny-all, networkpolicy-namespace-label-drifted, networkpolicy-port-mismatch, node-cordoned-draining, node-disk-pressure\*, node-memory-pressure, node-pid-pressure, node-readonly-filesystem, pod-identity-webhook-down, provisioner-credentials-rotated, shared-configmap-deleted, shared-dependency-scaled-to-zero, shared-nfs-server-down, shared-pvc-multi-attach, shared-secret-key-renamed, storage-backend-full, storageclass-pool-retired |

\* = an exam story. There are 6: three R (node-not-ready,
storage-provisioner-down, registry-unreachable) and three P
(coredns-down, networkpolicy-deny-all, node-disk-pressure).

So training draws from **41 stories: 35 P and 6 R.**

**What goes: 13 stories.**
- **The 12 X stories:** cluster-autoscaler-at-capacity,
  internal-ca-expired, kube-proxy-degraded, namespace-migration-lock-held,
  namespace-shared-pvc-full, node-clock-skew, node-conntrack-full,
  node-frequent-kubelet-restart, node-kernel-deadlock,
  shared-base-image-tag-moved, shared-gateway-refusing,
  sidecar-injector-broken. With real lines, neither world shows the
  origin.
- **runtime-class-removed:** its two worlds print the same lines.

**Rule for keeping a story:** its two worlds must differ in at least one
printed line. A test checks every kept pair.

**Named edits:**
- **node-pid-pressure** gets a real `PIDPressure` condition, so the
  health block shows it.
- **networkpolicy-deny-all:** in the healthy world, no policy selects
  the pods.
- **8 stories get victim-side healthy texts,** so the healthy world
  differs on the victim's own lines: the 6 network-policy stories,
  shared-pvc-multi-attach and csi-driver-version-mismatch.
- About **24 new victim texts** in all.

**The unverified twin stays.** Today about 1 node ruled pair in 3
renders a third world: the broken world where the fresh read of the node
fails. At size 8000 that is 26 of 80 node ruled pairs. In the new
pipeline, the gather's read of the origin node is refused with
kubeagent's own message, `nodes "<node>" is forbidden`. The rules then
decide each victim `unverified` and confirm nothing, so the label is
"none". This is the label rule in §4 working as written: "shared" needs
the rules to confirm. This world is in training only; the exam has no
such row today.

### 2. One pipeline builds each row

A story lists these objects, for each world:
- **nodes:** Ready condition, pressure conditions, cordon, kubelet lease;
- **PVCs, storage classes and the registry:** the object model the port
  already has;
- **the origin workload,** when the origin is a workload (for example
  coredns, cert-manager or a CSI controller);
- **the victims:** pods, findings, events and container logs;
- **service issues and network policies,** when the story has them.

The healthy world is the broken world with the origin fixed, plus any
victim-side edits from §1.

Each row is built the way `multi()` builds its rows:
1. `_report_order` sorts every flagged workload. The origin is included
   when kubeagent would flag it.
2. One `gather.gather()` does every read, with kubeagent's rule for each
   read type. Limits: 8 reads, 10 workloads.
3. The rules decide each workload over its full candidate list.
4. The renderer builds the prompt. It includes the real cluster-health
   block and the real service-issue lines.

The hand-typed reads, the 3-line candidate menu and the per-victim rule
calls all go.

**What real rules and real reads change:**
- **RestartLoop victims lose their log reads.** kubeagent reads logs
  only for CrashLoopBackOff, ContainerStartError and OOMKilled.
- **Some node conditions print no health line,** because kubeagent never
  checks them: NetworkUnavailable, a read-only disk, runtime restarts
  and a corrupt overlay. Those stories rely on the victims' own lines.
- **A network-policy line prints only when** all of that workload's
  findings are probe failures, or it has no findings. This is
  kubeagent's own gate.
- **A log read prints one of kubeagent's 10 log-cause labels,** never
  raw log text. A victim text stores the label, not log lines. No label
  names a service, so a log line can't carry a link to the origin.
- **Every pull event uses the kubelet's wording,** "Failed to pull image
  …". image-pull-secret-expired then reaches the auth sentence. Its text
  today has no "pull" in it, so kubeagent would skip the event.

**The origin gets its own row** when kubeagent would flag it. 10 stories
have one: coredns-down, cert-manager-down,
external-secrets-operator-down, metrics-server-down,
network-operator-down, namespace-egress-proxy-down,
pod-identity-webhook-down, csi-controller-oomkilled,
csi-controller-unschedulable and csi-node-driver-crashed. It is graded
like any other row.

**Not used:** `--expected-nodes`, and the Platform and cluster-resources
lines. No other family uses them either.

### 3. Cluster health: a copy of kubeagent's code

Today `render.cluster_health` guesses the block from candidate text. It
knows two reasons. It becomes
`cluster_health(nodes, leases, now, threshold, workloads)`, a copy of
`clusterhealth.Assess`.

**Header:** `Cluster health (P1): DEGRADED — R/T nodes Ready.` T is the
story's real node count. Today it is made up as `max(3, named + 1)`.

**Node lines,** in node-name order. One node may have several lines, in
this order:
1. pressure: `MemoryPressure`, `DiskPressure`, `PIDPressure`;
2. NotReady: `NotReady`, `NotReady: <reason>`, `NotReady: <message>`, or
   `NotReady: <reason> — <message>`. The message is cut at 120 runes,
   then "…" is added;
3. `SchedulingDisabled`;
4. lease: `no kubelet lease`, or
   `kubelet not heartbeating (lease 1m35s stale)`.

The lease age uses a port of Go's duration text. It rounds to whole
seconds, with halves rounded away from zero. A lease must be more than
40s old to get a line.

**System lines:** one for every flagged kube-system workload, not only
the first 10:
- `  system kube-system/<name> <ready>/<desired> <status>`;
- Jobs and CronJobs get no counts: `  system kube-system/<name> <status>`.
  The status may hold spaces, for example "Last run failed".

**`multi` switches to it** with its bytes unchanged. It passes the nodes
its old parser assumed.

**The "unknown reason raises" test is redesigned.** Reasons now come
from node objects, not parsed text. The new test: a story whose node
carries a condition type outside a closed list fails when the story
loads. The list is the four types kubeagent reads, plus the
problem-detector types the kept stories use.

### 4. Gold, keys and the label

#### Which rows get a named cause

- **The rules decide the row:** job 1. The gold is the rules' cause, as
  today.
- **Otherwise:** each victim text and each origin row carries an
  **anchor**, a short piece of exact text. The builder looks for it in
  that workload's **own lines**:
  - its inventory entry;
  - its candidate blocks that are not ruled out or refuted;
  - its own reads.

  Anchor found → a named cause. Anchor not found → `none_of_these`. So a
  read that was cut at 4096 bytes, refused, or never reached by the
  8-read budget gives `none_of_these` with no extra rule.
- **One meaning of "own lines."** The dataset code must not import the
  grader. A test checks the builder's own lines equal the grader's
  `_own_blocks` on every family row.

#### What a named cause says

- **Only what the prompt shows.** The link to the origin comes from the
  workload's own lines. The origin's state may come from anywhere in the
  prompt: a service line, the cluster-health block, or the origin's own
  row. Nothing more. If the prompt shows only NotReady, the gold does not
  say "the kubelet crashed".
- **Reworded, never copied.** The real grader's G2 and G3b must give
  every gold full marks.
- **Keys:**
  - 2 per gold (1 to 3 allowed);
  - lowercase, at least 4 letters, and inside the cleaned gold text;
  - one names the origin thing, one names how it failed;
  - fixed words, never a drawn name.
- **No must-not words in 4b-1.** Model-card limit 14 (a reply that says
  "not the X" trips the word "X") is fixed in 4b-4 first.

#### A `none_of_these` row

- The cause is exactly `none_of_these`, with confidence low and no keys.
- The rationale is "<what its own lines show>; none of its own lines says
  why."
  - The first half is a fixed phrase per issue kind. For example,
    CrashLoopBackOff gives "its container keeps crashing after it
    starts". A victim text may override it.
  - It never names the origin.

#### Confidence

Confidence is never graded. It feeds two scoreboard numbers.
- Rules-decided rows: high.
- Named rows, set per text:
  - **high** when one own line states the cause as Kubernetes state;
  - **medium** when the gold joins an own line with a line from
    elsewhere in the prompt.
- `none_of_these` rows: low.

#### Special cases

- **shared-dependency-scaled-to-zero:** a linked victim's gold joins its
  own event with the service line "scaled to 0". Confidence medium. Keys
  `session` and `endpoint`.
- **namespace-egress-proxy-down:** the origin's log label is the
  no-signature fallback in all 4 of its versions, and its gold is
  `none_of_these`. Naming "a code bug" would teach a wrong cause.
- **OOMKilled origins** (network-operator-down,
  csi-controller-oomkilled): named, "…was killed at its memory limit".
  Keys `memory` and `limit`. Confidence high. The gold does not claim
  the effect on other workloads, because no line shows it.
- **Every named gold gets keys.** The pool check in Tests enforces it.

#### The job-3 label

A row is **"shared"** in one of two cases:
- the rules confirm one shared cause on 2+ workloads (an R story's
  broken world, when the fresh read confirms);
- a P story's broken world where 2+ victims' link anchors are in their
  own lines.

Every other row is **"none"**. That includes every healthy world and the
unverified twin. The "separate" branch stays unreachable, as today.

#### The summary

- **"shared":** today's 3-line shape. The first line stays "N workloads
  share one upstream cause: …". N counts the linked victims only. The
  root-cause and remedy lines come from two new per-story fields,
  `shown_cause` and `shown_remedy`, cut to what the prompt shows.
- **"none":** the header is "N workloads are failing, and kubeagent's
  rules did not confirm one cause on two or more of them." Then up to 3
  lines:
  - "ns/name: cause." for a named or decided row;
  - "ns/name: its own lines do not show why." for the rest.

  It holds no un-negated claim phrase.
- In a healthy world, "failing for separate reasons" is used only when
  every row is named and the causes differ.

### 5. Captures: checking the new lines against kubeagent

The new Python lines need a Go check. Two new fixtures, because one
cluster can't show both the candidate cap and the registry sentences:
kubeagent lists down nodes first, and 9+ down nodes push the registry
candidate out of view.

**CLUSTER fixture,** 16 nodes named n01–n16:
- **NotReady, 4 kinds:** False with a reason and a long message; Unknown;
  message only; no Ready condition. The long message has a non-ASCII
  letter before the 120-rune cut, so a byte cut would show up.
- **No lease, 2 kinds:** no lease object; a lease with no renew time.
- **Stale leases:** 40.4s prints "40s"; 42.5s prints "43s"; 95s prints
  "1m35s"; 3600s prints "1h0m0s"; 3700s prints "1h1m40s".
- **One node at exactly 40s,** which gets no line.
- **Ready nodes with problems:** one with two pressure conditions (to
  check their order); one cordoned; one pressured, NotReady and cordoned
  at once.
- **System lines:** a failing kube-system Deployment, StatefulSet,
  DaemonSet, Job and CronJob, and more than 10 failing workloads in all.
- **Services:** 13 service issues, one per detail wording. The cap keeps
  10.
- **Network policies:** 2 that select one probe-failing workload, plus 1
  in another namespace that must not show.
- **A rules line about a cut candidate:** one pod sits on a down node
  past the 8-candidate cap, so its "decided by rules" line names a
  candidate the list cut.

**REGISTRY fixture:** no down nodes. Five workloads pull from one host,
one per outcome: connection error, auth error, image error, no pull
event, and pulling pod not read. One more pulls alone from a second host,
which gives the "threshold is 2" line.

Both fixtures stay within the 8-read budget.

**Harness** (`contract/capture/kv_capture_test.go.txt`):
- A mode replaces `golden bool`: main, logs, cluster or registry. Each
  mode has its own "must contain" list and self-checks.
- New fixture fields are optional: node conditions, cordon, lease age in
  milliseconds or no lease, services, endpoint slices and network
  policies. The 22 existing dump files must stay byte-identical.
- The capture calls kubeagent's real code for every line:
  `clusterhealth.Assess`, `svchealth.Assess`, `AnnotateEndpointCause`
  and `netpolicy.Annotate`.
- Same fixed clock, same 40s threshold.

**Python:** the byte-equal tests run over all 4 capture folders. A guard
test fails if a `gather_go*` folder exists that no test checks.

**Left out on purpose:**
- **Rows that show the no-pull sentence.** The capture proves its bytes.
  Built rows still reach it 0 times, and PIN.md says so. Reaching it
  needs a victim whose events have aged out, which real clusters rarely
  show.
- **The 5 log causes the logs capture doesn't cover.** The line format
  is captured. A test pins the 10 strings to Go's list.
- **B6, expected-absent nodes, and lease-unavailable.**

### 6. The checker

**6.1 Remove the exemption.** Delete `EXEMPT_CASES`, `EVIDENCE_RULES`
and `PROPAGATION_TEXT_RULES` (`checker.py:179-196`) and the skip in
`check()` (`:2049-2063`). Update the module docstring (`:17-31`). The
rule count stays 50.

**6.2 Rewrite B7.** It is the one rule that rejects real kubeagent
output.
- **Several lines per node.** Nodes stay in name order. Inside one node
  the order is pressure, NotReady, SchedulingDisabled, lease.
- **Only down lines need a candidate.** Down lines are NotReady, no
  lease and not heartbeating. `by_name` is built from down lines only.
  The "every down candidate has its line" check stays.
- **Header total.** Today it must equal `max(_B7_MIN_NODES, named + 1)`
  (`:1001-1004`). The new rule: the total is at least the number of
  distinct nodes the block names. B5 still ties Ready to total minus
  NotReady lines.
- **When the block exists.** It is required when there is a down
  candidate or a rendered kube-system row. It is allowed with only
  pressure, cordon or system lines. It is never header-only.

**6.3 Fix the system-line pattern.** `_HEALTH_SYSTEM` (`:232`) ends in
`(\S+)`, so "Last run failed" and "0/0 Scaled Down" fail. The last group
becomes `(.+)`.

**6.4 `origin_read_label`** stays for `multi` (244 rows). Shared-origin
rows stop setting it (`cases.py:1152`, `:1190`).

**6.5 No answer-rule change.** The grader is stricter than the checker
in 6 places: a named gold with no keys, an empty rationale, more than 10
rows, more than 4 summary lines, a misspelled `none_of_these`, and claim
phrases. The pool check in Tests catches all 6 with the real grader. The
checker does not copy the grader. One gap neither catches is a key found
only in a ruled-out line. The builder checks that itself.

**6.6 Rules the new rows must pass,** as these rules run on this family
for the first time:
- node messages hold no IP, no "dial tcp", no "i/o timeout" and no
  `Get "` (kubeagent does not redact the health block);
- every "nodes are available:" text uses the real scheduler wording with
  " preemption: 0/" (TXT-IS9);
- a pull event's matching phrase sits in the first 512 runes;
- lease ages are whole seconds;
- the "shared" summary's first line is as in §4;
- a "none" summary holds no un-negated claim phrase.

**6.7 No story-type rules.** The checker reads text only. Whether a
row's label and gold match its anchors is a story test, not a checker
rule.

**6.8 The build stays report-only** for checker violations. The pytest
manifest test is the gate.

### 7. The mix

At size 8000, `counts_for` still gives the family 15%: 1,200 pairs, 2,400
rows. The loop in `generate.py:245-283` keeps its shape:
- `i % 5 == 4` takes the ruled pool, otherwise the plain pool;
- victim width is still `2 + (t // 3) % (len(p.victims) - 1)`;
- the unverified twin is still `node kind and t % 3 == 2`;
- one `salt` per pair, and both twins use `random.Random(salt)`.

**Per story at size 8000,** before the train/val split:
- P: 960 pairs over 35 stories, about 27 each (today about 20 over 48);
- R: 240 pairs over 6 stories, 40 each (as today).

**The test-only `BIG`** moves from 13,200 to 14,000. Then the family gets
2,100 pairs = 35 × 48 + 6 × 70, so `DRAWS` = 48 and `RULED_DRAWS` = 70,
both whole. 14,000 is the closest whole-share size to today's 13,200.

**The `none_of_these` share rises.** Over the whole training bank it goes
from 251 of 10,991 answers (2.3%) to about 2,900 (about 26%). This was
accepted in the design review. Two tests guard it:
- **Balance:** the family's broken-world and healthy-world
  `none_of_these` shares stay within 10 points of each other.
- **Ceiling:** the whole-bank share stays at or under 30%.

If the ceiling breaks, I report it to you. I don't raise it.

## The build and the re-pin

1. **Build** with the same seed and size into a new folder:
   `kv-dataset --seed 17 --size 8000 --out out/dataset-MMDD`, named for
   the build day. No existing `out/` folder is touched.
2. **The gate:** the checker manifest over the new build shows zero
   failures. Every number the docs quote comes from this build.
3. **Re-pin by hand,** never with `-update`. Each gets a dated comment
   saying what moved it:
   - `FROZEN_SLICE_SHA256` (`tests/test_shared_origin_training.py:1036`,
     today `f3d05a3d…897a`);
   - `EVAL_SET_SHA256` (`:1177`, today `a5304170…06e2`);
   - `GRADED_VIEW_SHA256` (`tests/test_exam_graded_view.py:215`, today
     `efed5140…caa4`).

   What moves them: the exam's 20 family rows. The other 229 stay
   byte-identical. The exam's job-1 and job-2 counts will move (job 2 is
   177 today), because victims become named, decided or
   `none_of_these`, and some origins get a row. The plan measures the new
   counts and records them.
4. **No 0920 replay.** The 20 changed exam rows have new prompts, so
   0920's saved answers to them answer a different question. The 229
   unchanged rows would score the same as before. The live 0920 run comes
   once, after 4b-4.

No training, no live model run, and nothing under `dist/`.

## Tests

TDD: each test is written first and seen to fail.

**1. Byte tests: the Go ports match kubeagent**
- All 4 `gather_go` folders match byte for byte, including the cluster
  and registry folders.
- A guard fails if a `gather_go*` folder exists that no test checks.
- The 22 old dump files stay byte-identical.
- `multi` keeps its exact bytes after the switch to `cluster_health`.
  This covers `test_cluster_health.py` and its 3 other callers.
- A table test pins the duration text: 40.4s, 42.5s, 95s, 3600s, 3700s.
- The exam's 229 rows from other families stay byte-identical.

**2. Checker tests: no exemption**
- The built family passes all 50 rules. The manifest test
  (`test_checker.py:816-830`) shows zero failures.
- **No rule passes by looking at nothing.** One test puts each of the 50
  rules on one of two lists: "inspects at least 1 item on this family"
  or "inspects none here". The first list holds ANS-2, D3, E6–E9, B5,
  B7, TXT-IS15 and the 10 rules that fire today. A rule that moves list
  fails the test. Both lists are fixed from the first build.
- **New B7 mutations:** wrong order inside a node; a down line with no
  candidate; a header total below the named nodes; a header with no
  lines. The old B5 and B7 mutations still fire with the same messages.
- `_HEALTH_SYSTEM` parses "Last run failed" and "0/0 Scaled Down".
- The rule-still-fires test builds its own bad rows.
- **Removed:** the exemption pin tests, the set pins
  (`test_checker.py:574-586`) and the `_HEADER_EXEMPT` copy in
  `test_generate.py`.

**3. Gold tests: every gold earns full marks**
- **Pool check:** every train, val and exam gold gets full marks from the
  real grader with job-2 grading on: contract, G2, G3b, and jobs 1, 2
  and 3. It catches a named gold with no keys, an empty rationale, more
  than 10 rows, more than 4 summary lines, a misspelled
  `none_of_these`, and a claim phrase in a "none" summary.
- **Cross-world check:** a victim's keys fail its other world's gold and
  every decoy in its row.
- Every log-cause label is one of kubeagent's 10 Go strings.
- The builder's own lines equal the grader's `_own_blocks` on every
  family row.
- No key appears only in ruled-out or refuted lines. A test plants a bad
  key to show the builder's check trips.

**4. Story tests: the answers match the prompt**
- **Label:** a row is "shared" only in a broken world, and only when the
  rules confirm one shared cause, or it is a P story where 2+ victims'
  own lines hold their link anchor. Every other row is "none", including
  every healthy world and every unverified twin.
- **Gold:** a workload gets a named gold only if its anchor is in its
  own lines. Otherwise it gets `none_of_these`. A rules-decided row goes
  to job 1 with the rules' cause.
- **Worlds differ:** in every kept pair, the two prompts differ in at
  least one printed line.
- **Exactly one answer per workload:** named, decided or
  `none_of_these`. This replaces "names one cause for every workload".

**5. Mix tests**
- **Floor:** at least 12 pairs per story in train.
- **Ruled share:** 1 pair in 5, with `DRAWS` 48 and `RULED_DRAWS` 70 at
  `BIG` 14,000.
- **Balance** within 10 points, and the **ceiling** at 30%, as in §7.
- **The cause-spread test** (`test_shared_origin_training.py:1445`)
  counts named causes only. `none_of_these` is not a cause, and the
  balance and ceiling tests govern it. Its 0.12 and 0.30 bars stay.
- The three-verdict decoy test stays.

**6. Cue tests and the old tests**
- The origin-read cue tests (`test_shared_origin_training.py:551-745`)
  run on `multi` only. Shared-origin rows no longer carry an origin-read
  label.
- **New cue test:** at least 5 of the 35 trainable P stories end
  "shared" and at least 5 end "none". A story is counted by the label
  most of its broken-world train rows get, since the victim width can
  change it. The estimate is 11 and 24. If the
  real rows miss this, I report it to you. I don't move the number.
- **The "3 of 4 origin variants" test leaves this family.** Those
  variants are invented read text.
- About 16 test files check today's bytes for this family. Each is
  rewritten against the new rows. A test is deleted only if it checks
  something the new rows no longer have: the made-up menu, the 12 X
  stories, or the invented origin read. The plan gives a one-line reason
  for each deletion.

## Docs

**`contract/PIN.md`**
- A new entry under "Dataset pin moves": the three hashes, old to new,
  and why. One line each on the real rows, the exemption removed, the
  gold rules and B7.
- These close in place, each with a dated note. The old text stays.
  - **`:420-421`,** victims whose gold names a node their lines never
    show. The count was 14; it is really 20. The gold rules in §4 close
    it.
  - **`:424-425`,** the kube-system line past the first 10 workloads.
    Closed by the `cluster_health` port.
  - **`:428-429`,** the candidate-cap marker missing from the golden.
    Closed by the cluster fixture.
  - **B4 (`:537-539`, `:647`).** The captures close the three arms it
    names. Its wording is corrected: a fourth arm, the shared-cause cap,
    has no capture. That arm moves to 4b-4.
  - **Node state at scan time (`:547`, `:651`).** Closed by the cordon
    and pressure lines.
- A new section, "Capture record (v1.24.0, cluster and registry
  capture)": kubeagent commit `15ec5649bbd2…` (the full hash), the Go
  version, the sha256 of both fixtures and both dumps, and a note that
  the capture ran from a `git archive` copy.
- "Left for 4b-2/3/4": the lists below.

**`docs/model-card.md`**
- Each of "Known limits of the training data" 1–9 gets a dated note,
  with numbers from the new build:
  - **expected to close or narrow:** 1 ("Unknown" against "False"), 2
    (two reasons on one node), 4 (says 3 workloads, shows 2), 8 (two
    read formats for one node), 9 (a rationale that quotes reads the
    prompt never shows);
  - **6 is rewritten:** broken twins say "shared" when 2+ victims' own
    lines show the origin. New counts;
  - **3, 5 and 7** are re-measured;
  - **10** is not in this family. Unchanged.
- **New limit 15: the `none_of_these` share,** about 26% of answers. It
  explains the balance and ceiling tests, and the risk: if the model
  over-learns this answer, we only see it after the retrain.
- The 0920 sections (`:798`, `:864`) get a dated note: "scored on the
  exam's shared-origin rows as they were before <the build day>", with
  the real date filled in.

**Other docs, in simple voice**
- **`docs/how-training-works.md:92-96` and `:212-213`:** they say "same
  candidate menus" and that the healthy twin's answer is "separate
  reasons". Both become false. They are rewritten: the healthy twin's
  answer is each workload's own cause, or `none_of_these`.
- **`docs/design.md:280-281`:** the mix rows are updated. A dated
  paragraph says the invented origin read is retired for this family.
  The history above it stays.
- **`README.md`:** one dated line in the probe section.
- **`docs/runbooks/train.md`:** its row counts are re-checked. 249 should
  hold.
- Old specs and plans are history. They are not edited.
- No tracked file names the training host.

## Run order

1. **Captures and the port:** the harness modes, the two fixtures (run
   from a `git archive` copy), the Python `cluster_health` and duration
   text, the byte tests, and `multi`'s switch with unchanged bytes.
2. **Stories as objects:** the 47 stories in two worlds, the X stories
   and runtime-class-removed removed, and the named edits.
3. **The pipeline:** report order, gather, rules over every candidate,
   render. The origin rows.
4. **Gold:** anchors, own lines, keys, `none_of_these`, confidence, the
   label and the summaries.
5. **The checker:** the exemption removed, B7, `_HEALTH_SYSTEM`.
6. **The mix:** the loop, `BIG`, the mix tests.
7. **The old tests,** rewritten.
8. **The build** into `out/dataset-MMDD`, the manifest gate, the
   measured counts, the three hashes.
9. **Docs.**
10. **Full suite green,** and a diff check that the bars did not move.

After 4b-1: 4b-2, 4b-3 and 4b-4, then the exam rebuild and re-pin, then
0920 live, then the one retrain (about 32 hours on the training host),
then the untuned baseline.

## Done when

| Check | Target |
|---|---|
| Capture folders, byte-equal | 4 of 4, plus the folder guard |
| Old dump files | 22 unchanged |
| `multi` bytes after the switch | unchanged |
| Exam rows from other families | 229 byte-identical |
| Exam size | 249 rows |
| Checker manifest on the new build | 0 failures, 50 rules |
| Pool check (every gold, real grader, job-2 on) | full marks on every row |
| Label | "shared" only in a confirmed or 2+-linked broken world |
| Kept pairs whose worlds print the same lines | 0 |
| Trainable P stories ending "shared" / "none" | at least 5 each |
| Pairs per story in train | at least 12 |
| Broken vs healthy `none_of_these` share | within 10 points |
| Whole-bank `none_of_these` share | at most 30% (expect about 26%) |
| New exam job-1 and job-2 counts | measured and recorded |
| Bars | unchanged |
| Full test suite | green, no `-update` |

## Left for 4b-2, 4b-3 and 4b-4

**4b-2: gold that says more than its prompt, in the other families.**
The same rule as §4: a gold says only what its prompt shows.

**4b-3: `multi` rows and decoys.**
- the container-name clash count, 96 of 738 `multi` rows;
- `multi`'s `healthy_origin` and its `origin_read_label` path;
- D4.

**4b-4: grader leftovers.**
- model-card limits 13 (the G3b log-cause label tail) and 14 (must-not
  words tripped by a negation);
- hyphen and underscore folding in the cleaning step;
- the 21 weak pairs;
- image-pull-secret-expired graded as unverified;
- B6;
- the G2 registry skip;
- must-not words for this family;
- B4's fourth arm, the shared-cause cap;
- tighter checker checks that real output does not need: service-line
  wording and sort order, the network-policy gate, a message-only
  NotReady line over 120 runes, lease ages from 0s to 39s, an extra
  system line at 10 rows, and ANS-2 counting ruled-out lines.

## Out of scope

- Training, a live model run, and anything under `dist/`.
- Any grader change.
- Model-card limit 10 (`node-cordon-diskfull`).
- `--expected-nodes`, and the Platform and cluster-resources lines.
- Any edit to the kubeagent repo.
- The GPU.
- Moving a bar.
