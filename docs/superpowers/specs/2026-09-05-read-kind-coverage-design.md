# Read-kind coverage for the shared-origin curriculum — design

**Date:** 2026-09-05
**Branch:** `read-kind-coverage` (off `main` @ `4dba2f6`)
**Status:** approved, ready for an implementation plan

## Why this slice exists

The 0905 model was scored on the honest exam and refused. Decider 5 is the
one that fails. In simple terms, decider 5 asks one question: when two
workloads share one upstream cause, does the model read the origin before it
says "shared"? It is scored on two small probes of 10 questions each, and a
paired join of them.

| Check | Bar | 0905 result |
|---|---|---|
| False "shared" on the decoy probe (the origin read is healthy) | at most 1 of 10 | **2 of 10** |
| Pairs where both halves are right | at least 7 of 10 | **3 of 10** |
| False "shared" on the multi-workload probe | at most 1 of 19 | 1 of 19 (met) |

The exam did not move. The 261 of 263 outputs the model wrote on the
re-pinned exam are byte-identical to what it wrote on the old one, so the
failure is the model's own.

A wider probe was run to see *which* origins fail. It draws five fresh pairs
per held-out origin and is diagnostic only; it is not part of the exam.

| Held-out origin | Read kind the exam uses | Pairs right | What the model did |
|---|---|---|---|
| node-not-ready | `describe node` | 5 of 5 | reads correctly |
| registry-unreachable | `get_events` cluster-wide | 5 of 5 | reads correctly |
| coredns-down | `describe kube-system/… (Deployment)` | 1 of 5 | says "shared" on one pair in five |
| storage-provisioner-down | `get_related storageclass` | 0 of 4 | never says "shared" (one pair could not be graded) |
| networkpolicy-deny-all | `get_related networkpolicy` | 0 of 5 | never says "shared" |
| node-disk-pressure | `describe node` with a pressure condition | 0 of 5 | says "shared" on both halves |

Three spikes narrowed the mechanism. The wording of the healthy read makes
no difference. The victim's own cue makes no difference. Fresh, unseen pairs
built from *trained* scenarios score 7 of 10 (node-pid-pressure 3 of 5,
kube-proxy-degraded 4 of 5). So the model can learn this trap. It fails only
on read kinds it was never trained on.

That is the gap this slice closes. Nothing in the trainable pool reads a
kube-system Deployment through `describe kube-system/… (Deployment)`, a
StorageClass, or a NetworkPolicy. Six trained scenarios read a node, but
none shows a `…Pressure` condition line, so on node-disk-pressure the model
falls back to the candidate menu and says "shared" whatever the read says.

## What this slice changes

Four trained scenarios are added to `_TRAINING_SCENARIOS` in
`src/kubeagent_verdict/dataset/propagation.py`. Each is a *cousin* of one
held-out origin: it uses the same kind of read, in the same shape, with a
different key and a different answer. The pool grows from 20 to 24
scenarios.

Nothing else changes in the model's contract:

- **The exam does not move.** `test_set()` draws only `all_scenarios()`, the
  six held-out ones. The frozen 253 pin (`9f5fb341…`) and the 263-row pin
  (`9d59a8f8…`) stay as they are. Adding trainable scenarios moves only
  `train` and `val`.
- **The held-out promise is kept as the docs state it.** The two pools share
  no scenario key and no answer sentence, and the existing tests assert both.
  The four cousins carry their own sentences.
- **Equal shares are automatic.** The generator rotates over the pool, so
  every scenario is taught in equal shares without a code change.
- **No dependency, no schema, no eval change.** The scorer, the deciders, and
  the probes are untouched.

## The four scenarios

The exact Python lives in the plan. This section fixes the design each one
must follow: key, radius, read label and shape, state words, answer
sentences, victims, and what the reader must check.

Every one of them obeys the rules the module docstring lists and the tests
in `tests/test_shared_origin_training.py` enforce: 2 to 4 victims, each with
a unique `local_cause` across the whole pool; `pass_confidence` that varies
inside the scenario; a healthy origin read; at least four `origin_variants`
whose first entry is the legacy pair and whose first lines are literal and
distinct; an `origin_state` word pair where the broken word is in every broken
variant and absent from every healthy one, and the reverse; and no banned
identifier shape (a dotted-quad address, a URL scheme, the word for a
cluster credentials file, a home-directory path, or an at-sign).

### ① `pod-identity-webhook-down` — cousin of coredns-down

- **Radius:** cluster (`scope_field=None`).
- **Read label:** `describe kube-system/pod-identity-webhook (Deployment)`.
- **What it teaches:** a kube-system Deployment describe. Broken shows
  `0 available | 2 unavailable` and `Available False`; healthy shows
  `2 available | 0 unavailable` and `Available True`. This is the shape the
  coredns exam read uses.
- **Story:** the mutating webhook that adds the identity token volume to
  every pod has no ready replica. Its failure policy is *Ignore*, so pods are
  admitted without the volume and start with no credentials.
- **State words:** `down` (broken) / `serving` (healthy), on the first line:
  `Admission backend: down` / `Admission backend: serving`.
- **Shared cause:** "the pod identity webhook has no ready replica, so every
  pod admitted since it went down started without its identity volume".
- **Distractor:** "each workload's own service account lost its identity
  annotation". **Distractor reason:** the identity annotation is present and
  unchanged on every service account involved, and the last edit to any of
  those service accounts predates this incident by weeks.
- **Victims (three):** a Deployment in `CrashLoopBackOff` (the app exits
  when no credential source is found; `high`); a StatefulSet in
  `Init:CrashLoopBackOff` (an init container fetches its config with the
  identity and fails; `medium`); a DaemonSet in `ProbeFailure` (its readiness
  check signs a token and cannot; `low`).
- **What the reader must check:** the replica line and the endpoint line of
  the webhook Deployment. The candidate menu names the webhook on both
  halves.
- **Distance from the pool:** `sidecar-injector-broken` is the nearest
  neighbour. There the webhook is up and injects a broken image; here the
  webhook is down and injects nothing. Different read kind, different cause
  shape.

### ② `storageclass-pool-retired` — cousin of storage-provisioner-down

- **Radius:** cluster (`scope_field=None`).
- **Read label:** `get_related storageclass ssd-premium`.
- **What it teaches:** a StorageClass read. The exam's storage read shows the
  provisioner controller at `0/1 ready`. This cousin shows the controller at
  `1/1 ready, Running` on **both** halves; what differs is the pool line. A
  reader who stops at the controller line gets it wrong.
- **Story:** the class's parameters name a storage pool that was retired. The
  provisioner is healthy and refuses every claim because the pool does not
  exist.
- **State words:** `retired` / `online`, on the first line:
  `Pool status: retired` / `Pool status: online`.
- **Shared cause:** "the ssd-premium StorageClass points at a storage pool that
  was retired, so the provisioner refuses every new claim on that class".
- **Distractor:** "the workloads' claims ask for a volume mode the class does
  not support". **Distractor reason:** every claim asks for the same
  Filesystem volume mode it bound with last month, and Filesystem is the
  mode the class has served since it was created.
- **Victims (three):** a StatefulSet in `Unschedulable` (a new replica's claim
  never binds, so the pod has an unbound claim; `high`); a Deployment in
  `VolumeAttachError` (an existing volume in the retired pool cannot be
  attached; `medium`); a Job in `Unschedulable` (`low`).
- **Distance from the pool:** `shared-pvc-multi-attach`,
  `csi-node-driver-crashed` and `namespace-shared-pvc-full` are the storage
  neighbours. None reads a StorageClass and none turns on the class's own
  parameters.

### ③ `networkpolicy-egress-allowlist-stale` — cousin of networkpolicy-deny-all

- **Radius:** namespace (`scope_field="ns"`).
- **Read label:** `get_related networkpolicy {ns}/egress-allowlist`.
- **What it teaches:** a NetworkPolicy read. The exam's read shows
  `policyTypes: Ingress, Egress` and an empty egress list. This cousin shows
  `policyTypes: Egress` with two rules: rule 1 to the datastore pods, rule 2
  to kube-system on port 53. Broken: rule 1 matches **0 pods**, because the
  datastore pods carry `tier=data` since a chart upgrade and the rule still
  says `tier=datastore`. Healthy: rule 1 matches 3 pods. DNS works on both
  halves; only the datastore is cut off.
- **Story:** the allow-list is stale. Every pod in the namespace is selected
  by it, so every pod's connection to the datastore is dropped.
- **State words:** `blocked` / `allowed`, on the first line:
  `Datastore egress: blocked` / `Datastore egress: allowed`.
- **Shared cause:** "the egress allow-list policy in {ns} no longer matches
  the datastore pods, so every pod's connection to the datastore is dropped".
- **Distractor:** "the datastore in {ns} has stopped accepting connections".
  **Distractor reason:** the datastore's own readiness probe passes on every
  check, and a connection from outside {ns} reaches it and runs a query.
- **Victims (three), each carrying `network_policies=("egress-allowlist",)`
  on both halves:** a Deployment in `CrashLoopBackOff` (exits when the
  datastore is unreachable; `high`); a StatefulSet in `Init:CrashLoopBackOff`
  (an init container waits for the datastore; `medium`); a Deployment in
  `ProbeFailure` (its readiness check queries the datastore; `low`).
- **Why the policy is listed on the healthy half too:** the exam's victims
  list `default-deny` on both halves. The lesson is that a policy in the
  inventory row is not by itself the answer; the read decides.
- **Distance from the pool:** `namespace-egress-proxy-down` is the namespace
  neighbour. There a Deployment is down; here a selector matches nothing.
  Different read kind, different cause shape.

### ④ `node-memory-pressure` — cousin of node-disk-pressure

- **Radius:** node (`scope_field="node"`).
- **Read label:** `describe node {node} (memory)`.
- **What it teaches:** a node describe with a pressure condition. Broken:
  `MemoryPressure True KubeletHasInsufficientMemory`, the memory-pressure
  taint, and a working set near the allocatable line. Healthy:
  `MemoryPressure False KubeletHasSufficientMemory`, no taint, a working set
  well under the line. The exam's disk read has exactly this shape with
  `DiskPressure`.
- **State words:** `reclaiming` / `headroom`, on the first line:
  `Memory: reclaiming` / `Memory: headroom`. The words "insufficient" and
  "sufficient" cannot be the state pair, because one is inside the other.
- **Shared cause:** "node {node} is under memory pressure, so the kubelet is
  evicting its largest pods and turning new ones away". This is not the
  disk-pressure sentence, and it is not the disk scenario's distractor ("the
  cluster has run out of allocatable memory").
- **Distractor:** "the workloads' own memory limits were lowered in the last
  rollout". **Distractor reason:** the container limits are unchanged since
  the previous release, and the last rollout changed only the image tag.
- **Victims (three):** a Deployment in `OOMKilled` (the kernel killed it
  during node-wide exhaustion; `high`); a StatefulSet in `ProbeFailure`
  (readiness times out while the node reclaims; `medium`); a DaemonSet in
  `RestartLoop` with exit code 137 and a `log_cause` (`low`).
- **Kind semantics to honour:** `OOMKilled` is a kernel kill; `RestartLoop`
  with 137 is a kill, not an entrypoint exit; `ProbeFailure` is running and
  failing a probe.
- **Distance from the pool:** `node-pid-pressure` is the nearest neighbour
  and is deliberately the template. Both are node-scoped resource pressure.
  They share no cause sentence, no reason skeleton and no state words.

### Why exactly these four

The wide probe names three origins the model never calls "shared" and one it
always calls "shared". The three map one-to-one onto three read kinds the
pool never shows. The fourth is a node read the pool shows often, but never
with a pressure condition. One cousin per gap is the smallest change that
tests the claim "coverage was the gap" on all four at once.

Widening further (say, two cousins per gap) would cost twice the authoring
and tell us nothing more about the claim. If this retrain moves the four
origins, a second slice can decide whether depth matters.

## The held-out promise, kept

`docs/how-training-works.md` promises that the exam and training pools share
no scenario key and no answer sentence. Both are enforced by tests that run
on every commit:

- `test_no_trainable_origin_is_an_eval_origin` — no key overlap.
- `test_no_trainable_scenario_reuses_an_eval_answer_string` — no shared
  cause or distractor string, compared exactly.
- `test_no_two_trainable_scenarios_share_an_answer_string` — unique inside
  the pool as well.
- `test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used`
  and `test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used`
  — the exam pins.

The cousins are *close* to their exam origins on purpose. That closeness is
in the read kind and the read shape, which the docs never promised to keep
apart. It is not in the key, the cause sentence, the distractor, or the
victims' local causes.

## Tests this slice adds or changes

- `test_the_trainable_pool_holds_twenty_scenarios` becomes
  `test_the_trainable_pool_holds_twenty_four_scenarios` and asserts 24. Its
  docstring keeps the reason the count is asserted.
- A new test, `test_every_held_out_read_kind_has_a_trained_cousin`, states
  the slice's claim: for each of the four read kinds named above, at least
  one trainable scenario uses it. It checks the label shape (`describe
  kube-system/… (Deployment)`, `get_related storageclass …`, `get_related
  networkpolicy …`) and, for the node case, that a trainable broken origin
  read contains a `MemoryPressure   True` condition line. This test is
  written first and fails on the 20-scenario pool.
- Every existing pool test runs over the 24 scenarios unchanged. That is
  where the authoring rules are enforced.

## Docs this slice touches

All in simple voice.

- `src/kubeagent_verdict/dataset/propagation.py` module docstring: the
  sentence that says "twenty scenarios taught in equal shares" says
  twenty-four.
- `docs/how-training-works.md`:
  - every sentence that states the *current* pool size says twenty-four;
    history sentences ("4 scenarios → 20 scenarios") stay as history and gain
    the next step;
  - a new subsection after *Widening the curriculum* and before the glossary,
    titled *Covering the exam's read kinds*, that says what the 0905 exam
    showed, what the wide probe showed, what the four cousins are, and what
    the next retrain will tell us;
  - a new bullet under *Where this currently stands* recording that the 0905
    model was refused on decider 5 and that this slice is the response;
  - the closing paragraph of *Widening the curriculum* says "No retrain has
    run". That is no longer true. It is rewritten to say the retrain ran, the
    wider textbook alone did not move decider 5 (paired 3 of 10, decoy
    false-shared 2 of 10), and the wide probe located the gap, with a pointer
    to the new subsection.
- `docs/runbooks/train.md` is not changed unless it states the pool size.

## Files touched

| File | Change |
|---|---|
| `src/kubeagent_verdict/dataset/propagation.py` | four `Propagation` records appended after `_T_MIGRATION_LOCK`; four entries appended to `_TRAINING_SCENARIOS`; docstring count |
| `tests/test_shared_origin_training.py` | count test renamed and raised to 24; new read-kind coverage test |
| `docs/how-training-works.md` | counts, new subsection, new status bullet |
| `docs/superpowers/specs/2026-09-05-read-kind-coverage-design.md` | this document |
| `docs/superpowers/plans/2026-09-05-read-kind-coverage.md` | the plan |

No other source file changes. `generate.py`, `cases.py`, `names.py`, the
scorer and the eval CLI are untouched.

## Verification

Before the branch is offered for merge:

1. The full suite passes with `.venv/bin/python -m pytest`.
2. The two exam pins are unmoved. The existing pin tests prove it; the plan
   also prints the sha256 of the 253 and 263 rows for the record.
3. Both halves of every new scenario are rendered and read by a person, as
   the docstring asks. The plan includes the render step with its exact
   command.
4. Distinctness is checked by the tests, not by eye: keys, cause strings,
   local causes, state words.
5. No real identifier appears in any tracked file. The four scenarios use only
   the placeholder pools in `names.py` and synthetic names.

## After the branch: the retrain

The retrain is the second half of Option A. It is **not** part of the
implementation plan and is launched only after the operator confirms the
exact command. The plan must not run `kv-train`, `kv-export`, or any test
with `-update`.

Recipe, to be confirmed at launch:

1. On the training host, on the merged code: regenerate the dataset with
   `kv-dataset --seed 17 --size 5500 --out out/dataset`. Only `train` and
   `val` change; the plan's pin check runs there too.
2. Negative control: the exam is byte-identical to the one the 0905 model
   already sat, so the 0905 scoreboard stands as the control. No second
   `kv-eval` of the old model is needed.
3. Train on CPU only, no GPU, with the same recipe as 0905, letting torch use
   the host's cores. The 0905 run's thread setting is checked before launch
   so "more cores" is a measured change and not a guess.
4. Export the GGUF into a dated `dist-retrain-<date>/` directory, never
   `dist/`, under its own authorisation.
5. Sit the exam with `kv-eval` (about 75 minutes) and then the wide probe
   (diagnostic). Report decider 5 in simple voice: the decoy false-shared
   count, the paired count, and the per-origin wide-probe table beside the
   0905 numbers.

What a result means:

- **Decider 5 met, all four origins move:** coverage was the gap. Publish.
- **The three "never shared" origins move, disk-pressure does not:** the
  candidate-menu shortcut on pressure conditions needs its own lesson.
- **Nothing moves:** coverage was not the gap, and the next slice looks at
  the loss or the recipe rather than the data.

## What this slice does not claim

- It does not claim the model will pass. It tests one hypothesis, on four
  origins, in one retrain.
- It does not change the exam, the deciders, the scorer or the probes.
- It does not touch the recipe. A recipe change would be its own slice with
  its own control.
- It does not add depth (more than one cousin per gap). That is a decision
  for after the numbers are in.
