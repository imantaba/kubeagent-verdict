# Read-kind coverage — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four trained shared-origin scenarios so that every read kind the six held-out exam origins use also appears, in shape, in the trainable pool. The exam itself does not change.

**Architecture:** Four new `Propagation` records go into `src/kubeagent_verdict/dataset/propagation.py`, appended to `_TRAINING_SCENARIOS`. Nothing in the renderer, the generator, the scorer or the eval CLI changes. Two tests are written first and stay red until the pool reaches twenty-four. One sample-size constant in the pool tests moves so that equal shares still divide evenly. One doc page gains a section that says what the 0905 exam showed and what this change does about it.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), pytest, stdlib `random`/`dataclasses`. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-05-read-kind-coverage-design.md` (commit `2ff20bf`). The spec is the authority. This plan is its argument.

## Global Constraints

- Work on branch `read-kind-coverage`, off `main` at `4dba2f6`. Never commit to `main`.
- Every commit is signed off: `git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "…"`. No other identity.
- No AI attribution anywhere: no `Co-Authored-By` trailer, no "generated with" line, no model name in any commit, comment, doc or test.
- A commit message never cites a path under `docs/testing/` or a scenario record ID.
- No secret, credential, private IP, internal hostname or real cluster name in any tracked file. Scenario text must not contain a dotted quad, `http://`, `https://`, the word `kubeconfig`, the string `/home/`, or `@` (the pool test bans these shapes). The training host is called "the training host" in every tracked file, never by name.
- Python is always `.venv/bin/python` (3.12). Never the system `python3` (3.14). Pytest is `.venv/bin/python -m pytest`.
- NEVER run `kv-train`, `kv-export`, `chaos/run.sh`, or any test with `-update`. This plan does not authorise a retrain. A retrain is a separate decision the user makes after the branch is merged.
- `CASE_MIX` in `src/kubeagent_verdict/dataset/generate.py` is frozen. Do not touch it.
- The exam is frozen. `generate.test_set()[:253]` must still hash to `9f5fb341f620306d1d003d1617da613139f7bccf03cec768bd78539df75abb96` and all 263 rows to `9d59a8f881862bc9035605d206a2cc9269bf5b59300f8fb8af3a030aff04f1b9`. Two tests pin these. If either moves, stop: something is wrong.
- The six held-out scenarios in `propagation.py` (`_SCENARIOS`, returned by `all_scenarios()`) are not edited. The model card, `contract.py`, the golden files and the scorer are not edited.
- Simple voice in every doc line this plan writes: short sentences, plain words, numbers explained ("3 of 10 pairs"), the decision first.
- A comment, docstring or doc line that promises something the code does not keep is a defect. Fix the claim or fix the code. Do not leave it.
- Scenario text must never contain the literal word `BROKEN` (a pair test asserts the decoy half never shows it).
- Scenario text may only use the nine placeholders the renderer formats: `{ns}`, `{name}`, `{pod}`, `{container}`, `{init_container}`, `{image}`, `{node}`, `{pvc}`, `{restarts}`. No other brace anywhere in a scenario string. Never write `podSelector: {}`.
- Local causes must not contain any of the shared-claim phrases: "shared origin", "shared root cause", "common cause", "common root cause", "same underlying", "same root cause", "upstream", "cascading", "knock-on", "caused by the same".

## File Structure

| File | Change | Owner task |
|---|---|---|
| `tests/test_shared_origin_training.py` | Rename the count test to twenty-four; add the read-kind cousin test; raise `BIG` to 13200 with a refreshed comment; refresh the ≥3-variants docstring numbers | Tasks 1, 3 |
| `src/kubeagent_verdict/dataset/propagation.py` | Append four `_T_*` records before `_TRAINING_SCENARIOS`; extend the tuple; docstring line 82 "twenty" → "twenty-four" | Tasks 2, 3 |
| `docs/how-training-works.md` | Status bullet, pool-size sentences, the "No retrain has run" paragraph, one new section | Task 4 |
| `src/kubeagent_verdict/dataset/{generate,cases,names}.py`, `src/kubeagent_verdict/evals/*`, `src/kubeagent_verdict/contract.py`, `docs/runbooks/train.md` | Untouched | — |

Why the tasks split the way they do: the pool test `test_every_trainable_scenario_is_taught_equally` draws `BIG` rows and demands that every scenario get the same count. Each half gets `BIG * 4 // 100` rows. At `BIG = 11000` that is 440 per half, which divides by 20 and by 22 but not by 21 or 23. So scenarios land in pairs: Task 2 takes the pool to 22, Task 3 takes it to 24 and moves `BIG` to 13200 (528 per half, 22 rows per scenario). Between Task 1 and the end of Task 3 exactly two tests are red, and both are named in each task.

---

### Task 1: The two tests, written first and red

**Files:**
- Modify: `tests/test_shared_origin_training.py:698-704` (the count test)
- Test: `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `propagation.trainable_scenarios() -> tuple[Propagation, ...]`; `Propagation.origin_read: tuple[str, str]` (label, content).
- Produces: `test_the_trainable_pool_holds_twenty_four_scenarios` and `test_every_held_out_read_kind_has_a_trained_cousin`. Tasks 2 and 3 turn them green. Nothing else may be changed to make them pass.

- [ ] **Step 1: Rename the count test and move the bar to 24**

At `tests/test_shared_origin_training.py:698-704` the test currently reads:

```python
def test_the_trainable_pool_holds_twenty_scenarios():
    """Four scenarios is what the pool held when it scored 0.5 in-distribution
    and 0.1 out. The count is asserted so shrinking it back is a deliberate
    edit rather than a merge artefact.
    """
    assert len(propagation.trainable_scenarios()) == 20
```

Replace it, in place, with:

```python
def test_the_trainable_pool_holds_twenty_four_scenarios():
    """Four scenarios is what the pool held when it scored 0.5 in-distribution
    and 0.1 out. Twenty is what it held when the 0905 run failed decider 5
    (pairs 3 of 10, false "shared" on the decoy probe 2 of 10). The count is
    asserted so shrinking it back is a deliberate edit rather than a merge
    artefact.
    """
    assert len(propagation.trainable_scenarios()) == 24
```

- [ ] **Step 2: Add the read-kind cousin test directly below it**

Insert this immediately after the test above and before `test_every_trainable_scenario_is_taught_equally`:

```python
def test_every_held_out_read_kind_has_a_trained_cousin():
    """On the 0905 wide probe the model never said "shared" for the three
    held-out origins whose discriminating read has no trained cousin of the
    same kind -- a kube-system Deployment describe, a StorageClass
    `get_related`, a NetworkPolicy `get_related` -- 0 of 15 pairs. And it said
    "shared" on both halves for node-disk-pressure, the one node scenario
    whose read turns on a pressure condition line, 0 of 5. Trained cousins it
    had seen scored 5 of 5. So the gap is the read kind, and this test pins
    the fix: every read kind the exam uses must appear, in shape, in the
    trainable pool.

    Labels are matched by prefix and suffix so a renamed component or a
    namespace slug cannot satisfy the check by accident. The memory cousin is
    recognised by the condition line itself, exactly as the held-out node
    reads spell it (three spaces).
    """
    pool = propagation.trainable_scenarios()
    labels = [p.origin_read[0] for p in pool]
    broken = [p.origin_read[1] for p in pool]
    missing = []
    if not any(label.startswith("describe kube-system/")
               and label.endswith("(Deployment)") for label in labels):
        missing.append("describe kube-system/... (Deployment)")
    if not any(label.startswith("get_related storageclass ") for label in labels):
        missing.append("get_related storageclass ...")
    if not any(label.startswith("get_related networkpolicy ") for label in labels):
        missing.append("get_related networkpolicy ...")
    if not any("MemoryPressure   True" in content for content in broken):
        missing.append("describe node with a MemoryPressure   True condition")
    assert not missing, f"no trainable cousin for: {missing}"
```

- [ ] **Step 3: Run the file and watch exactly two tests fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -q`

Expected: exactly 2 failed, everything else passed. The two failures are `test_the_trainable_pool_holds_twenty_four_scenarios` (`20 == 24` is false) and `test_every_held_out_read_kind_has_a_trained_cousin` (its message lists all four kinds as missing). If any other test fails, stop and report; do not edit anything else.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "test(dataset): demand a trained cousin for every exam read kind and a pool of twenty-four"
```

---

### Task 2: Scenarios ① and ② — the kube-system Deployment and the StorageClass

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — insert two records immediately before the line `_TRAINING_SCENARIOS = (` (currently line 2716, right after the closing `)` of `_T_MIGRATION_LOCK`), then extend the tuple.
- Test: `tests/test_shared_origin_training.py`, `tests/test_propagation.py`, `tests/test_shared_origin_training_pair.py` (all existing; no new test in this task).

**Interfaces:**
- Consumes: `Propagation` and `Victim` dataclasses from `propagation.py`; the style of `_T_NODE_PID_PRESSURE` (lines 1902-1998), which the two records below copy exactly: 4-space indent, parenthesised string pieces, `origin_variants` as `((broken), (healthy))` pairs, variant 0 identical to `(origin_read[1], healthy_origin_content)`.
- Produces: `_T_POD_IDENTITY_WEBHOOK` (key `pod-identity-webhook-down`) and `_T_STORAGECLASS_POOL_RETIRED` (key `storageclass-pool-retired`) as members 21 and 22 of `_TRAINING_SCENARIOS`. Task 3 appends after them.

- [ ] **Step 1: Insert the first record, `_T_POD_IDENTITY_WEBHOOK`**

Paste this verbatim before `_TRAINING_SCENARIOS = (`:

```python
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
                      "service account involved; the webhook that reads it has no "
                      "ready endpoint to act on it",
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
```

Why these words: the state pair is `down` / `serving`. Every broken half carries `down` and never `serving`; every healthy half carries `serving` and never `down` (so no "download", "downstream" or "shutdown" in a healthy line either). The pool test checks both directions as plain substrings.

- [ ] **Step 2: Insert the second record, `_T_STORAGECLASS_POOL_RETIRED`, right after the first**

```python
_T_STORAGECLASS_POOL_RETIRED = Propagation(
    key="storageclass-pool-retired",
    blast_radius="cluster",
    scope_field=None,
    origin="the fast-ssd StorageClass names a storage pool that was retired, so the "
           "provisioner refuses every claim on it",
    shared_cause="the fast-ssd StorageClass points at a storage pool that was "
                 "retired, so the provisioner refuses every new claim on that class",
    shared_reason="the class parameters name pool ssd-tier-a, the backend lists that "
                  "pool as retired, and the provisioner has bound 0 claims on "
                  "fast-ssd since the pool went away while binding normally on "
                  "every other class",
    distractor_cause="the workloads' claims ask for a volume mode the class does not "
                     "support",
    distractor_reason="every claim asks for the same Filesystem volume mode it bound "
                      "with last month, and the provisioner's refusal names the "
                      "pool, not the mode",
    rationale="the workload's storage on fast-ssd is refused because the class "
              "points at a retired pool, which is true of every claim and volume on "
              "that class right now",
    remedy="Point the fast-ssd StorageClass at a live pool (or recreate the class); "
           "the flagged workloads and their claims need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass fast-ssd",
        ("Pool status: retired\n"
         "provisioner: example.com/ssd-csi\n"
         "parameters: pool=ssd-tier-a, fstype=ext4\n"
         "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
         "backend pool ssd-tier-a: retired 3d ago, 0 volumes accepted\n"
         "PersistentVolumes bound on fast-ssd in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "Pool status: online\n"
        "provisioner: example.com/ssd-csi\n"
        "parameters: pool=ssd-tier-b, fstype=ext4\n"
        "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
        "backend pool ssd-tier-b: online, 412 volumes accepted\n"
        "PersistentVolumes bound on fast-ssd in the last 20m: 9"
    ),
    origin_state=("retired", "online"),
    origin_variants=(
        (("Pool status: retired\n"
          "provisioner: example.com/ssd-csi\n"
          "parameters: pool=ssd-tier-a, fstype=ext4\n"
          "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
          "backend pool ssd-tier-a: retired 3d ago, 0 volumes accepted\n"
          "PersistentVolumes bound on fast-ssd in the last 20m: 0"),
         ("Pool status: online\n"
          "provisioner: example.com/ssd-csi\n"
          "parameters: pool=ssd-tier-b, fstype=ext4\n"
          "controller ssd-csi/ssd-csi-controller: 1/1 ready, Running\n"
          "backend pool ssd-tier-b: online, 412 volumes accepted\n"
          "PersistentVolumes bound on fast-ssd in the last 20m: 9")),
        (("the storage backend reports the pool behind fast-ssd retired\n"
          "no claim on the class has bound for 3d\n"
          "the provisioner controller is healthy and refusing each request by name"),
         ("the storage backend reports the pool behind fast-ssd online\n"
          "claims on the class bind within seconds\n"
          "the provisioner controller is healthy and accepting each request")),
        (("Warning  ProvisioningFailed  ssd-csi  pool ssd-tier-a is retired: "
          "refusing every claim on StorageClass fast-ssd"),
         ("Normal  ProvisioningSucceeded  ssd-csi  pool ssd-tier-b is online: claim "
          "on StorageClass fast-ssd bound in 4s")),
        (("fast-ssd pool state: retired\n"
          "claims refused in the last 3d: 14\n"
          "provisioner controller: healthy"),
         ("fast-ssd pool state: online\n"
          "claims refused in the last 24h: 0\n"
          "provisioner controller: healthy")),
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
                   "StorageClass: fast-ssd\n"
                   "Events: Warning  ProvisioningFailed  ssd-csi  pool ssd-tier-a is "
                   "retired, claim refused")),
            # The decoy half shows the pool online, so the refusal must be the
            # claim's own: its size, not the pool.
            healthy_read_content=(
                "Status: Pending\n"
                "StorageClass: fast-ssd\n"
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
```

Why the three `healthy_read_content` swaps: the state word is `retired`. Each victim read names the retired pool, and the pool test `test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half` demands a healthy swap without that word whenever a victim read carries it. The second victim's finding line also names the pool, so it gets a `healthy_evidence` too (the same mechanism `_NODE_LOST` uses for its taint at line 565).

- [ ] **Step 3: Extend the tuple to twenty-two**

Replace the `_TRAINING_SCENARIOS` tuple with:

```python
_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO,
                       _T_IMAGE_PULL_SECRET, _T_SECRET_KEY_RENAMED,
                       _T_AUTOSCALER_CAPACITY, _T_SIDECAR_INJECTOR,
                       _T_BASE_IMAGE_TAG, _T_PVC_MULTI_ATTACH, _T_CNI_IP_POOL,
                       _T_CSI_NODE_DRIVER, _T_NODE_PID_PRESSURE,
                       _T_NODE_RUNTIME_RESTARTING, _T_NODE_CLOCK_SKEW,
                       _T_NODE_CONNTRACK_FULL, _T_LIMITRANGE_LOWERED,
                       _T_EGRESS_PROXY_DOWN, _T_NS_PVC_FULL, _T_MIGRATION_LOCK,
                       _T_POD_IDENTITY_WEBHOOK, _T_STORAGECLASS_POOL_RETIRED)
```

- [ ] **Step 4: Run the pool tests — still exactly two red, and the red has narrowed**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -q`

Expected: exactly 2 failed. `test_the_trainable_pool_holds_twenty_four_scenarios` fails with `22 == 24`. `test_every_held_out_read_kind_has_a_trained_cousin` fails and its message now lists only two kinds: `get_related networkpolicy ...` and `describe node with a MemoryPressure   True condition`. Every other test in the file passes, including the equal-shares test (440 rows per half divide by 22) and the ≥3-variants test. If any other test fails, the record text is wrong: read the failure, fix the record, do not touch the test.

- [ ] **Step 5: Run the whole suite**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest -q`

Expected: the same 2 failures and nothing else. In particular the two pin tests (`test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used`, `test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used`) pass, which proves the exam did not move.

- [ ] **Step 6: Render both halves of both scenarios and read them**

`propagation.by_key()` covers only the six held-out scenarios, so build the lookup from the trainable pool. Save the output under this plan's SDD workspace (git-ignored; never commit it):

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF' > .superpowers/sdd/2026-09-05-read-kind-coverage/task-2-render.txt
import random
from kubeagent_verdict.dataset import cases, propagation
pool = {p.key: p for p in propagation.trainable_scenarios()}
for key in ("pod-identity-webhook-down", "storageclass-pool-retired"):
    p = pool[key]
    for salt in (1, 2):
        for name, fn in (("SHARED", cases.shared_origin), ("DECOY", cases.shared_origin_decoy)):
            ex = fn(p, random.Random(salt), victims=3)
            print(f"===== {key} salt={salt} {name}\n{ex.user}\n--- answer\n{ex.assistant}\n")
EOF
```

Then read the file end to end. Check, for each of the 8 renderings: the prompt has no stray `{` or `}`; the SHARED half's origin read shows the broken state and its answer names the shared cause; the DECOY half's origin read shows the component healthy, every victim line in it is consistent with a healthy component, and its answer says the workloads fail for separate reasons; no line contains a real hostname, IP, or the word `BROKEN`. Note in the report which salt drew which variant. If something reads wrong, fix the record and re-render.

- [ ] **Step 7: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "feat(dataset): teach a kube-system webhook Deployment and a retired StorageClass pool as shared origins"
```

---

### Task 3: Scenarios ③ and ④ — the NetworkPolicy and the memory-pressure node; the pool reaches twenty-four

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — insert two records right after `_T_STORAGECLASS_POOL_RETIRED` (before `_TRAINING_SCENARIOS = (`); extend the tuple; module docstring line 82.
- Modify: `tests/test_shared_origin_training.py:677-681` (`BIG` and its comment) and the docstring of `test_every_trainable_scenario_renders_at_least_three_origin_variants` (currently lines 718-729).
- Test: `tests/test_shared_origin_training.py` (the two red tests go green), then the whole suite.

**Interfaces:**
- Consumes: `_T_POD_IDENTITY_WEBHOOK` and `_T_STORAGECLASS_POOL_RETIRED` from Task 2 (already in the tuple); the two tests from Task 1.
- Produces: `_T_NETPOL_EGRESS_ALLOWLIST` (key `networkpolicy-egress-allowlist-stale`) and `_T_NODE_MEMORY_PRESSURE` (key `node-memory-pressure`) as members 23 and 24; `BIG = 13200`. Task 4 only writes docs and relies on the count being 24.

- [ ] **Step 1: Insert the third record, `_T_NETPOL_EGRESS_ALLOWLIST`**

Paste this verbatim after `_T_STORAGECLASS_POOL_RETIRED` and before `_TRAINING_SCENARIOS = (`:

```python
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
    distractor_reason="the datastore's own readiness probe passes and its connection "
                      "count sits near zero; the packets are dropped before they "
                      "reach it",
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
```

Why these words: the state pair is `blocked` / `allowed`. "allow-list" and "allowlist" are safe in a broken line because neither contains the letters `allowed` in a row. No healthy line may contain `blocked`. The scope field is `ns`, so `{ns}` must appear in `shared_cause` (a `tests/test_propagation.py` rule) and the victims all sit in one namespace. `network_policies` is a tuple, never a bare string.

- [ ] **Step 2: Insert the fourth record, `_T_NODE_MEMORY_PRESSURE`, right after the third**

```python
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
                      "and each kill is logged by the node's out-of-memory handler "
                      "rather than by the container's own limit",
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
        "Taints:  none\n"
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
          "Taints:  none\n"
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
```

Why these words: the state pair is `reclaiming` / `headroom`, not "insufficient" / "sufficient", because "insufficient" contains "sufficient" and the pool test checks plain substrings in both directions. The broken read carries the exact condition line `MemoryPressure   True` (three spaces, as the held-out node reads spell it), which is what the Task 1 cousin test looks for. The scope field is `node`, so `{node}` appears in `shared_cause` and every victim carries the node.

- [ ] **Step 3: Extend the tuple to twenty-four**

```python
_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO,
                       _T_IMAGE_PULL_SECRET, _T_SECRET_KEY_RENAMED,
                       _T_AUTOSCALER_CAPACITY, _T_SIDECAR_INJECTOR,
                       _T_BASE_IMAGE_TAG, _T_PVC_MULTI_ATTACH, _T_CNI_IP_POOL,
                       _T_CSI_NODE_DRIVER, _T_NODE_PID_PRESSURE,
                       _T_NODE_RUNTIME_RESTARTING, _T_NODE_CLOCK_SKEW,
                       _T_NODE_CONNTRACK_FULL, _T_LIMITRANGE_LOWERED,
                       _T_EGRESS_PROXY_DOWN, _T_NS_PVC_FULL, _T_MIGRATION_LOCK,
                       _T_POD_IDENTITY_WEBHOOK, _T_STORAGECLASS_POOL_RETIRED,
                       _T_NETPOL_EGRESS_ALLOWLIST, _T_NODE_MEMORY_PRESSURE)
```

- [ ] **Step 4: Update the module docstring count**

At `src/kubeagent_verdict/dataset/propagation.py:82` the docstring says:

```
anywhere; and, across the pool, twenty scenarios taught in equal shares,
```

Change `twenty` to `twenty-four`. Nothing else in that paragraph changes. (Line 375, "for twenty minutes", is a held-out scenario's text and stays.)

- [ ] **Step 5: Raise `BIG` so equal shares still divide, and keep the comment honest**

At `tests/test_shared_origin_training.py:677-681` the block currently reads:

```python
BIG = 11000  # 0.54s; 22 rows of each half per scenario at 20 scenarios.
             # Not 5500: 11 draws from 4 variants shows <3 distinct 0.3% of
             # the time per scenario, 5.7% across twenty -- a deterministic
             # failure with correct data. 22 draws puts it at 1.4e-6 per
             # scenario, 2.9e-5 across twenty.
```

Replace it with the block below, then measure the time (Step 7) and write the measured number into the first comment line in place of `<measured>s`. Do not leave the placeholder in and do not invent the number.

```python
BIG = 13200  # <measured>s; 22 rows of each half per scenario at 24 scenarios
             # (each half is BIG * 4 // 100 = 528 rows, and 528 / 24 = 22).
             # Not 6600: 11 draws from 4 variants shows <3 distinct 0.3% of
             # the time per scenario, 7% across twenty-four -- a deterministic
             # failure with correct data. 22 draws puts it at 1.4e-6 per
             # scenario, 3.4e-5 across twenty-four.
```

- [ ] **Step 6: Refresh the ≥3-variants docstring numbers**

In the docstring of `test_every_trainable_scenario_renders_at_least_three_origin_variants` (currently lines 718-729) the last paragraph reads:

```
    The bar is 3 of 4 rather than 4 of 4 because the draw is uniform and
    random: this is a sampling check, and its strength is a function of `BIG`.
    At 22 draws a correct pool trips it about once in 35,000 runs across the
    whole pool. Lowering `BIG` is not a free speed-up -- at 11 draws it is 5.7%,
    and the failure names a scenario whose data is fine.
```

Replace it with:

```
    The bar is 3 of 4 rather than 4 of 4 because the draw is uniform and
    random: this is a sampling check, and its strength is a function of `BIG`.
    At 22 draws a correct pool trips it about once in 29,000 runs across the
    whole pool of twenty-four. Lowering `BIG` is not a free speed-up -- at 11
    draws it is about 7%, and the failure names a scenario whose data is fine.
```

The arithmetic behind both numbers, so a reviewer can check it: the chance that n uniform draws from 4 variants show fewer than 3 distinct ones is `(6 * (2**n - 2) + 4) / 4**n`. At n = 22 that is 1.43e-6 per scenario, times 24 scenarios is 3.4e-5, about once in 29,000 runs. At n = 11 it is 2.9e-3 per scenario, times 24 is about 7%.

- [ ] **Step 7: Run the pool tests and measure `big_rows`**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -q --durations=3`

Expected: all passed, 0 failed. The two Task 1 tests are now green. The durations list shows the `big_rows` fixture setup time; copy that number (to two decimals, e.g. `0.66s`) into the `BIG` comment from Step 5 and re-run once to confirm the file is still green.

- [ ] **Step 8: Run the whole suite**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest -q`

Expected: all passed, 0 failed, 0 errors.

- [ ] **Step 9: Print the two exam digests and compare them to the pins**

The pin tests passed in Step 8. Print the digests anyway so the report carries them and a reviewer can see the exam did not move. This mirrors `_digest` in `tests/test_shared_origin_training.py` (lines 636-639); check that function first and copy its encoding exactly if it differs from the below.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import hashlib, json
from kubeagent_verdict.dataset import generate
def digest(rows):
    blob = json.dumps([generate.to_row(e) for e in rows], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
rows = generate.test_set()
print("rows:", len(rows))
print("first 253:", digest(rows[:253]))
print("expect   : 9f5fb341f620306d1d003d1617da613139f7bccf03cec768bd78539df75abb96")
print("all rows :", digest(rows))
print("expect   : 9d59a8f881862bc9035605d206a2cc9269bf5b59300f8fb8af3a030aff04f1b9")
EOF
```

Expected: `rows: 263`, and each printed digest equals the `expect` line under it. Paste all five lines into the task report.

- [ ] **Step 10: Render both halves of both new scenarios and read them**

Same method as Task 2, other two keys, saved next to the Task 2 render:

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF' > .superpowers/sdd/2026-09-05-read-kind-coverage/task-3-render.txt
import random
from kubeagent_verdict.dataset import cases, propagation
pool = {p.key: p for p in propagation.trainable_scenarios()}
for key in ("networkpolicy-egress-allowlist-stale", "node-memory-pressure"):
    p = pool[key]
    for salt in (1, 2):
        for name, fn in (("SHARED", cases.shared_origin), ("DECOY", cases.shared_origin_decoy)):
            ex = fn(p, random.Random(salt), victims=3)
            print(f"===== {key} salt={salt} {name}\n{ex.user}\n--- answer\n{ex.assistant}\n")
EOF
```

Read the file end to end with the same checks as Task 2 Step 6. For the memory scenario also confirm the DECOY half's node read shows `MemoryPressure   False` and no taint, and that the first victim's pod read on that half names a cgroup kill, not a system OOM. For the NetworkPolicy scenario confirm every rendered victim sits in the same namespace as the policy.

- [ ] **Step 11: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "feat(dataset): teach a stale egress NetworkPolicy and a memory-pressure node; pool at twenty-four"
```

---

### Task 4: The training page records the 0905 refusal and the four cousins

**Files:**
- Modify: `docs/how-training-works.md:606-637` (the status bullets), `:689-694`, `:696-699`, `:706-711`, and a new subsection inserted before the `---` at line 713 (line numbers as of `2ff20bf`; find each by its quoted text, not by number).
- Test: none (docs only). Three greps at the end stand in for a test.

**Interfaces:**
- Consumes: the pool count of 24 from Task 3 and the four keys from Tasks 2 and 3, exactly as spelled there.
- Produces: nothing code-facing.

Every line written here is in simple voice: short sentences, plain words, numbers explained, the decision first. Nothing in this task names the training host. Nothing in this task authorises a retrain.

- [ ] **Step 1: Add the 0905 status bullet**

Under `### Where this currently stands`, the last bullet is:

```
- Publishing: nothing is published, and nothing may be. The exam has now been
  scored and the model did not pass it.
```

Add this bullet directly after it:

```
- Second training run (0905), on the twenty-scenario textbook from the
  section *Widening the curriculum* below: **done, exported to
  `dist-retrain-0905/`, and refused on decider 5** — pairs 3 of 10 against a
  bar of 7, false "shared" on the decoy probe 2 of 10 against a bar of 1. The
  exam did not move, so the failure is the model's own. The response is four
  new trained scenarios, one per read kind the exam uses and training did
  not; the section *Covering the exam's read kinds* below says why. Still
  nothing is published.
```

- [ ] **Step 2: Make the pool-size sentences current**

Under `### Widening the curriculum`, this paragraph:

```
The response is not a further training run. It is a change to the textbook a
future run would use. The shared-origin curriculum now has twenty scenarios
instead of four, and inside each one the discriminating read itself varies
from lesson to lesson instead of repeating one of a small handful of fixed
strings. The right answer now depends on what the read actually says, not on
which of a few familiar shapes the question is.
```

becomes:

```
The response is not a further training run. It is a change to the textbook a
future run would use. This change took the shared-origin curriculum from four
scenarios to twenty (the section after this one takes it to twenty-four), and
inside each one the discriminating read itself varies from lesson to lesson
instead of repeating one of a small handful of fixed strings. The right answer
now depends on what the read actually says, not on which of a few familiar
shapes the question is.
```

And these lines:

```
What changed, measured on the built dataset (the four percentages below are
all taken at the same sample size, so they are directly comparable):

- The pool: **4 scenarios → 20 scenarios**.
```

become:

```
What changed, measured on the built dataset at the time (the four percentages
below are all taken at the same sample size, so they are directly comparable;
they were measured on the twenty-scenario pool, and the pool tests re-check
the two bars they stand on, 12% for one cause and 30% for the top three, on
every commit):

- The pool: **4 scenarios → 20 scenarios**, and since the next section,
  **→ 24**.
```

The two bars are real: `test_no_shared_origin_cause_dominates_the_curriculum` in `tests/test_shared_origin_training.py` asserts the top cause at or under 12% and the top three under 30%. Do not write a bar the test does not check.

- [ ] **Step 3: Rewrite the paragraph that says no retrain has run**

This paragraph:

```
What this does **not** say: that the model reads better, scores higher, or has
learned anything. No retrain has run, and this page does not authorise one.
This is a measurement of the textbook, not of a student — whether a wider,
less repetitive curriculum actually moves the paired shared-origin score is a
question only a retrain can answer.
```

becomes:

```
What this did **not** say: that the model reads better. That question needed
a retrain, and one then ran on this twenty-scenario textbook (the 0905 run).
It did not move decider 5: pairs **3 of 10** against a bar of 7, and false
"shared" on the decoy probe **2 of 10** against a bar of 1. So a wider, less
repetitive textbook was not enough on its own. A wider probe then located
the gap. The next section says what it found and what changed in response.
```

- [ ] **Step 4: Insert the new subsection**

Directly after the paragraph from Step 3 and before the `---` that precedes `## Small glossary`, insert:

```
### Covering the exam's read kinds

The 0905 run sat the frozen exam and was refused on decider 5. In simple
terms, decider 5 asks: when two workloads share one upstream cause, does the
model read the origin before it says "shared"? Two probes of 10 questions
each score it, plus a paired join of the two.

| Check | Bar | 0905 result |
|---|---|---|
| False "shared" on the decoy probe (the origin read is healthy) | at most 1 of 10 | **2 of 10** |
| Pairs where both halves are right | at least 7 of 10 | **3 of 10** |
| False "shared" on the multi-workload probe | at most 1 of 19 | 1 of 19 (met) |

The exam did not move, so the failure is the model's own.

A wider probe then asked *which* origins fail. It draws five fresh pairs per
held-out origin. It is diagnostic only and is not part of the exam.

| Held-out origin | Read kind the exam uses | Pairs right | What the model did |
|---|---|---|---|
| node-not-ready | `describe node` | 5 of 5 | reads correctly |
| registry-unreachable | `get_events` cluster-wide | 5 of 5 | reads correctly |
| coredns-down | `describe kube-system/… (Deployment)` | 0 of 5 | never says "shared" |
| storage-provisioner-down | `get_related storageclass` | 0 of 5 | never says "shared" |
| networkpolicy-deny-all | `get_related networkpolicy` | 0 of 5 | never says "shared" |
| node-disk-pressure | `describe node` with a pressure condition | 0 of 5 | says "shared" on both halves |

The pattern is the read kind. The two origins the model reads correctly use
read kinds that trained scenarios also use. The four it fails use read kinds
no trained scenario used: nothing in the pool described a kube-system
Deployment, a StorageClass or a NetworkPolicy, and none of the five trained
node scenarios showed a pressure condition line. Fresh, unseen pairs built
from trained scenarios score 7 of 10, so the model can learn this trap. It
fails only on shapes it has never seen.

The response is four new trained scenarios, one cousin per gap. Each uses the
same kind of read as its held-out origin, in the same shape, with a different
key and a different answer. The pool is now twenty-four.

| Trained cousin | Held-out origin it covers | Read kind | State words |
|---|---|---|---|
| `pod-identity-webhook-down` | coredns-down | `describe kube-system/… (Deployment)` | down / serving |
| `storageclass-pool-retired` | storage-provisioner-down | `get_related storageclass` | retired / online |
| `networkpolicy-egress-allowlist-stale` | networkpolicy-deny-all | `get_related networkpolicy` | blocked / allowed |
| `node-memory-pressure` | node-disk-pressure | `describe node` with a `MemoryPressure` condition | reclaiming / headroom |

The held-out promise holds. The two pools share no scenario key and no answer
sentence, and the tests that enforce both still pass. The exam is still 263
questions with the same checksum. A test now also demands that every read
kind the exam uses has a trained cousin, so the gap cannot quietly reopen.

What the next retrain will tell us:

- **Decider 5 met, all four origins move:** coverage was the gap.
- **The three "never shared" origins move but disk-pressure does not:** the
  habit of saying "shared" on a pressure condition needs its own lesson.
- **Nothing moves:** coverage was not the gap, and the next step looks at the
  loss or the recipe rather than the data.

This page does not authorise that retrain. It records what the textbook now
holds and why.
```

- [ ] **Step 5: Check the page with three greps**

```bash
cd /home/ubuntu/git/kubeagent-verdict
grep -n "No retrain has run" docs/how-training-works.md
grep -n "twenty-four\|→ 24\|Covering the exam" docs/how-training-works.md
grep -n -E "kubeconfig|/home/|@|https?://|([0-9]{1,3}\.){3}[0-9]{1,3}" docs/how-training-works.md
```

Expected: the first grep prints nothing (exit code 1 is the pass here). The second prints at least four lines (the Widening paragraph, the pool bullet, the section heading, and the status bullet's pointer). The third prints nothing. Then read the four edited places once, top to bottom, and check that the read-kind table and the cousin table each have exactly the rows shown above.

The spec says the runbook changes only if it states the pool size. It does not, and neither does the README. Confirm with:

```bash
grep -n -i "twenty scenarios\|20 scenarios\|twenty-four" docs/runbooks/train.md README.md
```

Expected: nothing (exit code 1). Do not edit either file.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add docs/how-training-works.md
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "docs(training): record the 0905 refusal and the four read-kind cousins"
```

---

## Done when

- `.venv/bin/python -m pytest -q` passes with 0 failures on the branch tip.
- `propagation.trainable_scenarios()` has 24 members and the two Task 1 tests are green.
- The two exam digests printed in Task 3 Step 9 equal their pins.
- Both render files under `.superpowers/sdd/2026-09-05-read-kind-coverage/` have been read and nothing in them contradicts its own half.
- Every commit on the branch carries a `Signed-off-by: imantaba <itn.taba@gmail.com>` line and no AI attribution.
- `git grep -n -E "kubeconfig|/home/|@|https?://|([0-9]{1,3}\.){3}[0-9]{1,3}" -- src/kubeagent_verdict/dataset/propagation.py docs/how-training-works.md` prints nothing new against `main` (compare with `git grep` on `main`; the banned-shape test in `tests/test_propagation.py` covers the scenario text either way).

## Not in this plan

The retrain, the export and the exam sitting are the second half of the user's choice, and they happen on the training host after this branch is merged. The spec's *After the branch* section holds the recipe. This plan does not run `kv-train`, `kv-export`, or `kv-eval`, and no task in it may. The launch is confirmed with the user in so many words before it happens.

## Post-review corrections

The whole-branch review corrected five things after the four tasks above
were transcribed. The code, the tests, the training page and the spec carry
the corrected text; the task blocks above keep the text as it was written.

- Wide probe: coredns-down got 1 pair of 5 right, not 0. One
  storage-provisioner-down pair could not be graded, so that row is 0 of 4.
  Six trained scenarios read a node before this branch, not five.
- The four new distractor reasons now hold on both halves of a pair, like
  the twenty older records. The plan's versions asserted the broken world.
- The StorageClass cousin is named `ssd-premium`, so the two pools share no
  identifier.
- The memory-cousin check matches `MemoryPressure` then `True` with any
  spacing.
- The curriculum-test docstring names the size its 0.609 was measured at.
