# Catalog gold from anchors (Spec 4b-2) — design

**Date:** 2026-10-04
**Branch:** `spec4b2-catalog-gold` (cut off `main` @ `e5b0ee8`)
**Status:** draft, for review

## What this is

Spec 4b is four specs. 4b-1 (the shared-origin family) is merged. This
is 4b-2: **gold that says more than its prompt, in the other families.**

4b-1's gold rule, now applied to the 20 trainable catalog entries:

> A workload's gold names a cause only when the cause's anchor is in
> that workload's own lines. If it is not, the gold is `none_of_these`.

4b-2 has four parts:

1. Each of the 20 trainable entries gets one **answer kit**: anchor,
   cause, keys, confidence and reason, plus a `none_phrase`. It reuses
   4b-1's `stories.Answer`. The fields `own_cause`, `own_cause_keywords`,
   `rationale` and `direct` go.
2. One **gate** in the builder: a case names an entry's cause only when
   the anchor is in the workload's own lines. Otherwise the gold is
   `none_of_these` at low.
3. **Confidence follows 4b-1's rule.** Rules-decided rows are high, and
   named rows carry the kit's value. The fixed `direct` flag is gone.
4. **Recommendations** that assume more than the prompt shows are
   rewritten.

Then: a new build, three hashes moved by hand, and the docs.

Prompts do not change. Not one byte of a user message moves. 4b-2
changes answers and meta only.

The bars do not move: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9.

## Why

Measured on `out/dataset-1004`, with shared-origin rows left out.

### Reasons claim what the prompt never prints

714 of 5,300 train verdicts that name a cause have a reason with a fact
the workload's own lines never show. 32 of 241 on the exam do. By case,
in train:

| Case | Rows with an unshown fact |
|---|---|
| own_cause | 175 of 830 |
| multi | 259 of 1,924 |
| wrong_attribution | 194 of 892 |
| empty_candidates | 86 of 327 |
| attributed, truncated, injection | 0 (they use kubeagent's rule reason) |

Examples, each from a hand-written `rationale`:

- oversized-job-unschedulable: "none carry SchedulingDisabled";
- restart-loop: "the restarts cluster around load", "no liveness probe is
  configured";
- networkpolicy-deny-all: "start exactly when the deny-all policy is
  created";
- init-errimagepull / init-imagepullbackoff: "the main image pulls
  successfully from the same registry";
- init-oomkilled: "the node reports no memory pressure".

### A few causes claim more than any row shows

- **node-cordon-diskfull** says "reporting disk pressure". No own line
  shows disk pressure. This is model-card limit 10.
- **init-imagepullbackoff** says "the tag does not exist". Its lines only
  show "back-off pulling image", never "not found".
- **restart-loop** says "intermittently, most often under load".
- **init-config-error** says "never created in this namespace". The line
  says "not found".
- **init-oomkilled** says "too small for the work it does at startup".
- **volume-mount-error** says "unhealthy or unreachable".
- **volume-attach-error** says "the PVC" and "the node the previous pod
  ran on". The line says the volume is attached to another node.
- **networkpolicy-deny-all** says "now blocks".

### Labels barely move

With the new causes and anchors, only 1 of 2,917 verdicts (train plus
exam) that name an entry's cause lacks its anchor. It is a train `multi` row for coredns-corefile-broken:
the read budget ran out before its previous log was read, so the line
`log cause: configuration parse/validation error` is never printed. The
exam has 0 such rows.

### Confidence comes from a fixed flag

`_confidence(e)` (`cases.py:267`) gives high when `e.direct`, else
medium. That means:

- probe-failure and restart-loop are medium, though an own line states
  their cause;
- the three `direct=False` entries are medium even on rules-decided rows:
  238 train rows and 15 exam rows.

## What stays the same

- Every prompt byte. The same seed builds byte-identical user messages.
- The cases, the mix and the row counts.
- kubeagent's rule reason on rules-decided rows (`render.rule_rationale`).
- The thin reasons (`_THIN_RATIONALE`) and `_CLEAR_WORDING`'s suffixes and
  second lines. Each is true by construction: the prompt prints the
  candidate list it talks about.
- `_thin_multi`. It stays, and the new gate runs after it.
- `own_cause_must_not` on each entry.
- The 9 non-trainable entries.
- The grader. No change to `score.py` or the checker rules.

## Design

### 1. The answer kit

`CatalogEntry` loses `own_cause`, `own_cause_keywords`, `rationale` and
`direct`. It gains:

- `answer: stories.Answer | None`, set on every trainable entry and on
  none of the others;
- `none_phrase: str`, set on every trainable entry.

`stories.Answer` already checks:

- 1 to 3 keys, each at least 4 lowercase letters;
- every key inside the cause;
- no placeholder in a key;
- a non-empty reason;
- a known confidence.

`link` stays False on every catalog answer.

**Rules for writing a kit:**

- **Anchor:** one exact lowercase piece of text from one own line. It may
  hold a `{placeholder}`. It is filled the same way as the other
  templates.
- **Cause:** says only what the anchor shows, plus one plain inference at
  most. Reworded, never copied: the real grader's G2 and G3b give it full
  marks.
- **Keys:** every key sits in an own line that names no ruled-out or
  refuted cause (4b-1's `check_keys` over `anchor_lines`).
- **Reason:** one or two sentences. Each claim comes from an own line.
  Every fact token (a number, a CamelCase word) appears in the own lines.
- **Confidence:**
  - **high** when one own line states the cause as Kubernetes state. A
    `log cause:` line counts: it is kubeagent's reading of the
    container's own log.
  - **medium** when the gold joins an own line with an inference, or the
    line itself says "possible cause".
- **none_phrase:** what the issue line shows, in plain words, for
  example "its pod cannot be scheduled".

**The 20 kits.** Anchors are written as `own_lines` returns them
(lowercase). The reasons below are the drafts. The plan may reword them,
but each must pass the anchor test (§4).

| Entry | Anchor | Cause | Keys | Conf. |
|---|---|---|---|---|
| memory-limit-oomkill | `issue: oomkilled` | container killed at its memory limit | memory, limit | high |
| deployment-bad-image-tag | `": not found` | the image tag does not exist in the registry | image, registry | high |
| node-cordon-diskfull | `were unschedulable` | one node is unschedulable (cordoned) and the others have taints the pod does not tolerate | unschedulable, taint | high |
| networkpolicy-deny-all | `network policy: pods selected by` | a default-deny network policy blocks the probe's traffic to the pod | network, policy | medium |
| coredns-corefile-broken | `log cause: configuration parse` | the Corefile has a syntax or plugin error that crashes CoreDNS on startup | coredns, error | high |
| worker-containerd-stop | `containerd task: context deadline exceeded` | containerd on the pod's node is not responding (context deadline exceeded) | containerd, deadline | high |
| oversized-job-unschedulable | `insufficient memory` | the pod's memory request is larger than any node can allocate | memory, node | high |
| crashloop-pod | `log cause: bad command or entrypoint` | the container's command or entrypoint is wrong and it exits immediately | entrypoint, exit | high |
| probe-failure | `http 500` | the application answers its readiness endpoint with errors | readiness, endpoint | high |
| container-start-error | `no such file or directory` | the container's entrypoint names a path that does not exist in the image | container, image | high |
| create-container-config-error | `couldn't find key` | the pod spec references a ConfigMap key that was never added or was renamed | configmap, key | high |
| init-crashloop | `log cause: cannot reach a dependency` | the init container cannot reach a dependency it waits for before the pod can start | init, dependency | high |
| init-config-error | `secret migration-creds not found` | a Secret the init container references does not exist | secret, init | high |
| init-errimagepull | `": not found` | the init container's image tag does not exist in the registry | init, registry, tag | high |
| init-imagepullbackoff | `back-off pulling image` | the init container's image cannot be pulled, and the kubelet keeps backing off | init, pull | high |
| init-oomkilled | `init:oomkilled` | the init container is killed at its memory limit | memory, init | high |
| restart-loop | `log cause: application panic` | the container panics (a code bug) and keeps restarting | panic, container | high |
| volume-attach-error | `multi-attach error` | the volume is still attached to another node | attached, node | high |
| volume-mount-error | `issue: volumemounterror` | the pod's volume times out while mounting on its node | volume, pod | high |
| pvc-unbound-unschedulable | `unbound immediate persistentvolumeclaims` | a claim the pod mounts is still waiting for its volume to be provisioned | claim, volume | high |

Notes on the table:

- **init-errimagepull** keeps its cause. `not found` and `tag` sit on its
  own lines: the issue line and kubeagent's suggested fix ("verify the
  tag and registry credentials").
- **init-config-error's** anchor is the waiting message. The Secret's
  name is fixed in the catalog, so the anchor is exact. The cause adds
  nothing beyond "secret … not found".
- **volume-attach-error** was not in the brainstorm's list of changed
  causes. It is added here: the line names a volume attached to "one
  node", not a PVC or a previous pod.
- **node-cordon-diskfull's** keys move from `node`, `pod` to
  `unschedulable`, `taint`. Both are printed words. "cordon" is not, so
  it is not a key. This closes model-card limit 10.

**Draft reasons:**

| Entry | Reason |
|---|---|
| memory-limit-oomkill | Its finding says the container exceeded its memory limit and was killed, with exit code 137. |
| deployment-bad-image-tag | The pull of {image} fails with "not found", so the tag does not exist in the registry. |
| node-cordon-diskfull | The scheduler says 1 node was unschedulable and 2 had taints the pod does not tolerate, so no node can take it. |
| networkpolicy-deny-all | The readiness probe times out, and kubeagent names the default-deny network policy that selects its pods as a possible cause, so the policy likely blocks the probe. |
| coredns-corefile-broken | The coredns container keeps crashing, and its previous log classifies as a configuration parse or validation error, so CoreDNS cannot load its Corefile. |
| worker-containerd-stop | Starting the container fails with "failed to create containerd task: context deadline exceeded", so containerd on the pod's node does not answer in time. |
| oversized-job-unschedulable | The scheduler rejects all 3 nodes for insufficient memory, so the pod's memory request is larger than any node can give. |
| crashloop-pod | The container keeps exiting after it starts, and its previous log classifies as a bad command or entrypoint. |
| probe-failure | The readiness probe fails with HTTP 500, so the application answers its health endpoint with an error. |
| container-start-error | The container cannot start: its entrypoint path gives "no such file or directory", so that path is not in the image. |
| create-container-config-error | The kubelet couldn't find the key the container needs in the ConfigMap it names, so the pod spec points at a key that is not there. |
| init-crashloop | The init container keeps crashing, and its previous log classifies as connection refused, so it cannot reach a dependency it waits for. |
| init-config-error | The init container cannot start because the Secret it references is not found. |
| init-errimagepull | The init container's image pull fails with "not found", so its tag does not exist in the registry. |
| init-imagepullbackoff | The kubelet keeps backing off pulling the init container's image, so the pod cannot start. Its own lines do not say why the pull fails. |
| init-oomkilled | The init container is OOMKilled with exit code 137, so it is killed at its own memory limit. |
| restart-loop | The container keeps exiting with an error, and its previous log classifies as an application panic. |
| volume-attach-error | Attaching fails with a multi-attach error: the volume is already attached to another node. |
| volume-mount-error | Mounting the pod's volume times out waiting for the condition, so the volume does not mount on its node. |
| pvc-unbound-unschedulable | The scheduler says the pod has unbound immediate PersistentVolumeClaims, so a claim it mounts has no volume yet. |

**none_phrase per entry:**

| Entries | Phrase |
|---|---|
| memory-limit-oomkill | its container keeps being killed for memory |
| deployment-bad-image-tag | its image cannot be pulled |
| node-cordon-diskfull, oversized-job-unschedulable, pvc-unbound-unschedulable | its pod cannot be scheduled |
| networkpolicy-deny-all, probe-failure | its readiness probe fails |
| coredns-corefile-broken, crashloop-pod | its container keeps crashing |
| worker-containerd-stop, container-start-error, create-container-config-error | its container fails to start |
| init-crashloop | its init container keeps crashing |
| init-config-error | its init container fails to start |
| init-errimagepull, init-imagepullbackoff | its init container's image cannot be pulled |
| init-oomkilled | its init container keeps being killed for memory |
| restart-loop | its container keeps restarting |
| volume-attach-error | its volume cannot attach |
| volume-mount-error | its volume cannot be mounted |

The phrases match 4b-1's wording where the two overlap.

### 2. The gate

One helper in `cases.py` decides an undecided workload's gold from its
own lines:

- Input: the entry, the names, and the workload's own lines (via
  `gold.own_lines` on the built user message, the same lines the grader
  reads).
- **If the filled anchor is in `anchor_lines`** (own lines minus every
  line that names a ruled-out or refuted cause): the gold is the kit's
  cause, confidence, keys and reason. `check_keys` runs and raises on a
  bad key.
- **Otherwise:** the gold is `none_of_these`, confidence low, no keys.
  The reason is `"<none_phrase>; none of its own lines says why."`

**Where the gate runs:** every place that writes an entry's own cause
today:

- `_undecided_example` (own_cause, wrong_attribution and
  misattribution_probe);
- the empty_candidates builder;
- the `multi` helper at `cases.py:728` (multi_misattribution_probe);
- `multi` (`cases.py:1067-1078`), after `_thin_multi`.

`none_of_these` and the thin cases do not change.

**When the gate gives `none_of_these`,** the row follows the existing
none paths:

- its meta `expected_cause` is `none_of_these`, its keywords are empty,
  and it is not job-2 graded;
- in a single-workload row the summary uses today's ruled-out wording;
- in `multi` the row joins the group summary the way a `_thin_multi` row
  does.

Today the gate fires on 1 train row and 0 exam rows. It is there so a
later case or budget change cannot quietly bring overclaiming back.

**Rules-decided rows** (attributed, truncated, injection,
positional_probe, contradiction_probe, and decided `multi` rows) keep
kubeagent's rule reason. Their confidence becomes high. `_confidence` is
deleted.

### 3. Recommendations and summaries

An undecided row's summary stays `"<ns/name> is failing: <cause>."`,
followed by the entry's recommendation or the case's fixed second line.

**The rule:** a recommendation is advice. It names no object the
workload's own lines don't print, and it assumes no fact they don't show.

| Entry | Today | New |
|---|---|---|
| node-cordon-diskfull | uncordon the node or free disk space, then confirm DiskPressure clears | uncordon the node, or check why the other nodes are tainted |
| init-imagepullbackoff | fix the init image's tag or push the missing image | check the init image's tag and the registry credentials |
| init-oomkilled | raise the init container's memory limit or stream the migration instead of loading it whole | raise the init container's memory limit |
| restart-loop | check the previous log for the panic and what request triggered it | check the previous log for the panic |
| volume-mount-error | check the CSI driver and the underlying volume's health on {node} | check why the volume does not mount on the pod's node |
| worker-containerd-stop | check whether the container runtime on {node} is healthy | check whether the container runtime on the pod's node is healthy |
| pvc-unbound-unschedulable | create the storage class the claim {pvc} asks for, or point the claim at one that exists | check why the pod's claim has no bound volume yet |

The other 13 recommendations stay.

### 4. What moves

| What | Train | Exam |
|---|---|---|
| Reasons rewritten (every named catalog row) | all | all |
| Rows with an unshown fact in the reason | 714 → 0 | 32 → 0 |
| Causes rewritten (8 entries) | every row of those entries | same |
| Labels moved to `none_of_these` | 1 | 0 |
| probe-failure, restart-loop named rows: medium → high | 258 | 12 |
| Rules-decided rows of the three old `direct=False` entries: medium → high | 238 | 15 |
| Keys changed | node-cordon-diskfull, init-imagepullbackoff | same |

**Job-2 grading on the exam moves for two keys.** node-cordon-diskfull's
and init-imagepullbackoff's exam rows grade against new words. The
weak-pair list (`tests/test_answer_keys.py`, 9 pairs today, 6 of them on
node-cordon-diskfull's old key) is expected to shrink to about 3. The
plan measures it. It must not grow.

## Tests

TDD: each test is written first and seen to fail.

1. **Kit shape.** Every trainable entry has an `answer` and a
   `none_phrase`. No non-trainable entry has either. Keys are not
   must-not words of their own entry, and the cause holds no must-not
   word. A guard fails if `direct`, `own_cause`, `own_cause_keywords` or
   `rationale` comes back as a `CatalogEntry` field.
2. **Anchors hold everywhere.** Build every case for every trainable
   entry over several seeds. For each verdict that names an entry's
   cause, check against that workload's own lines:
   - the filled anchor is in `anchor_lines`;
   - every key is in `anchor_lines` (`check_keys`);
   - every fact token in the reason is in the own lines. Fact tokens use
     the probe's pattern:
     `\b(?:\d+(?:\.\d+)?[A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]+|[a-z]+[A-Z][A-Za-z]+)\b`,
     compared lowercase;
   - the filled recommendation names no drawn name (node, PVC, image,
     pod) that the own lines don't print.

   Run against today's catalog, this test fails on the 714 rows.
3. **The gate.** A built row whose anchor is missing gets
   `none_of_these`, low, no keys, and the kit's `none_phrase` reason. Two
   cases: the real coredns `multi` shape (budget spent before its log
   read) and a hand-cut own lines list.
4. **Confidence.** Rules-decided rows are high. Named rows carry the
   kit's confidence. `none_of_these` rows are low. Meta's
   `expected_confidence` matches the answer on every row.
5. **Prompts don't move.** `generate(seed=17, size=…)` gives the same user
   message, byte for byte, as `out/dataset-1004` on every row. The test
   reads `out/` and skips when the folder is missing.
6. **The real grader gives full marks.** On every built named gold:
   - G2 and G3b leave it at full marks;
   - job 2 scores it 1.0 against its own keys and must-not words.
7. **Rewritten by hand, with a dated comment each:** every test that
   reads `e.own_cause`, `e.rationale`, `e.direct` or `_confidence(e)`
   (`tests/test_catalog.py`, `tests/test_cases.py`), and
   `tests/test_answer_keys.py`'s key count, weak-pair list and the old
   init-keys bot.

## The build and the re-pin

1. **Build** with the same seed and size into a new folder:
   `kv-dataset --seed 17 --size 8000 --out out/dataset-MMDD`, named for
   the build day. No existing `out/` folder is touched.
2. **The gates:**
   - the checker manifest over the new build shows zero failures;
   - the whole-bank `none_of_these` share stays at or under 30%;
   - the probe from §Why finds 0 rows with an unshown fact, in train and
     on the exam.

   Every number the docs quote comes from this build.
3. **Re-pin by hand,** never with `-update`. Each pin gets a dated
   comment saying what moved it:
   - `FROZEN_SLICE_SHA256` (`tests/test_shared_origin_training.py:1008`);
   - `EVAL_SET_SHA256` (`:1156`);
   - `GRADED_VIEW_SHA256` (`tests/test_exam_graded_view.py:232`).

   What moves them: exam answers and meta (reasons, confidence, two
   entries' keys). The plan measures the exam's job-1 and job-2 counts
   and records them.
4. **No 0920 replay.** The live 0920 run comes once, after 4b-4.

No training, no live model run, and nothing under `dist/`.

## Docs

All in simple voice.

**`contract/PIN.md`**
- A 4b-2 entry:
  - the gold rule as it now applies to the catalog;
  - the gate;
  - the confidence moves (probe-failure and restart-loop to high, and
    rules-decided rows to high);
  - the 8 changed causes and 7 changed recommendations;
  - the measured counts.
- A new line under "Dataset pin moves": the three hashes, old to new.
- The "Left for Spec 4" node-cordon-diskfull line (`:483-486`) marked
  closed.

**`docs/model-card.md`**
- Limit 10 closed, with a dated note and the new counts.
- The weak-keyword paragraph (`:928-934`) updated with the new pair
  count.

**`docs/how-training-works.md`**
- One line: every named gold, in every family, rests on an anchor in the
  workload's own lines.

**The 4b-1 spec's "Left for" list**
- 4b-2 marked done, with a pointer to this spec.

## Run order

1. Kit shape: `stories.Answer` on `CatalogEntry`, the 20 kits, fields
   removed.
2. The gate and confidence in the builders.
3. Recommendations.
4. The anchor test, the prompt-bytes test and the grader test go green.
5. The rewritten tests.
6. The build, the gates, the re-pin.
7. Docs.

## Done when

| Check | Target |
|---|---|
| Rows with an unshown fact in a reason | 0 in train, 0 on the exam |
| Prompt bytes | identical to `out/dataset-1004` |
| Checker manifest | zero failures |
| Whole-bank `none_of_these` share | at or under 30% |
| Weak pairs | measured, fewer than 9 |
| Exam job-1 and job-2 counts | measured and recorded |
| Bars | unchanged |
| Full test suite | green, no `-update` |
| Ruff | "All checks passed!" |

## Out of scope

- `multi`'s own problems: the container-name clash, `healthy_origin`, D4
  (4b-3).
- Every grader change: limits 13 and 14, folding, the weak pairs
  themselves, B4, B6, G2 (4b-4).
- Must-not words for the changed keys. 4b-4 first fixes limit 14.
- Any prompt byte, any new read, any catalog `events` or `evidence`
  change.
- The 9 non-trainable entries.
- The kubeagent repo, training, the GPU, and the bars.
