# Exam rebuild — design

**Date:** 2026-10-05
**Branch:** `spec-exam-rebuild` (cut off `main` @ `c23dab3`)
**Status:** approved in chat 2026-10-05; written for review

## What this is

Spec 4b-4 changed only the grader. It left a list in PIN.md, "Left for the
exam rebuild": nine items that change exam rows, or belong with a build.
This spec takes **eight of the nine**. Any change to exam rows moves all
three hash pins (`FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256`,
`GRADED_VIEW_SHA256`), so the eight land together with **one re-pin**.

The eight:

1. **IS-22's sum half.** In "0/N nodes are available: ...", the counts add
   up to N.
2. **node-disk-pressure's ContainerStartError keys.** ("containerd",
   "task") becomes ("space", "containerd").
3. **The weak pairs.** 3 becomes 1.
4. **The G2 registry skip.** The bad-image-tag entry gets must-not words
   for a registry fault.
5. **Must-not words for the shared-origin family.** Story answers get a
   must-not field.
6. **B6.** A refused read prints the API server's full "is forbidden"
   text.
7. **The tighter checker checks.** Six checks get closer to kubeagent's
   Go output. They move no row.
8. **image-pull-secret-expired graded as unverified.** It already is. A
   test pins it.

**Left out:** B4's fourth arm, the shared-cause cap. It needs a new Go
capture. It stays on the list.

After this spec: the 0920 live run, then the one retrain, then the untuned
baseline.

## What stays the same

- **The bars:** 0.9 / 0.7 / 0.9 (`JOB2_BAR = 0.7`), FLOOR, BALANCE 0.10,
  CEILING 0.30, LABEL_CUE, 0.40/5, 0.12/0.30.
- **The grader.** `score.py` does not change. Only row meta (keys and
  must-not words) changes what it reads.
- **The exam's size and seed.** 249 rows, built by
  `kv-dataset --seed 17 --size 8000`.
- **The Go fixtures.** `tests/fixtures/gather_go*/`, the four
  `gather_fixture*.yaml` files and `contract/golden/` keep their bytes. See
  item 6.
- **The old build folders.** `out/dataset-1004`, `out/dataset-1004-4b2`,
  `out/dataset-1005` and every other folder in `out/` are only read.

## Why, and the design, item by item

### 1. IS-22's sum half

**Today.** IS-22 (`checker.py:1890-1920`) checks only that N in "0/N nodes
are available" matches the cluster header. It does not check the reasons
after the colon. Some story texts in `stories.py` hard-code counts, while
a world draws 3 to 5 nodes:

- node-disk-pressure (`:1061`, `:1070`): "1 node(s) had untolerated taint
  ..., 2 Insufficient cpu." That is 3, which is wrong when there are 4 or 5
  nodes.
- the network-unavailable victim (`:791`, `:801`): "and the other nodes
  have insufficient memory". It has no count, and it is not real scheduler
  wording.
- node-cordoned-draining (`:916-926`): "1 node(s) were unschedulable, 2
  node(s) had volume node affinity conflict", and its healthy twin "3
  node(s) had volume node affinity conflict".
- a Job victim (`:1166`): "no node fits this pod". This is not real
  wording either.

**Rule (the checker).** The sum must equal N.
- A message is split at " preemption: ". Each "0/N nodes are available:
  <reasons>" part is checked on its own. The preemption part that
  `shared_origin._scheduler_text` adds already sums to N.
- Each reason is a comma-separated clause. Its count is the number it
  starts with.
- If every clause has a count, the counts must add up to N.
- If no clause has a count, the part is skipped. The PVC PreFilter message
  "pod has unbound immediate PersistentVolumeClaims" is like this in real
  Kubernetes.
- If some clauses have counts and some do not, the part fails.

Real Kubernetes can give one node two reasons, for example "Insufficient
cpu" and "Insufficient memory". Then the counts add up to more than N. Our
builder never writes a node with two reasons, so equality is the right
check for it. The rule's docstring says so.

**Generator.** `shared_origin._sub` gains an `{other_nodes}` slot, filled
as `len(d.nodes) - 1`. The catalog already has this slot. Then:

- "2 Insufficient cpu" → "{other_nodes} Insufficient cpu";
- "and the other nodes have insufficient memory" → "{other_nodes}
  Insufficient memory";
- "2 node(s) had volume node affinity conflict" → "{other_nodes} node(s)
  had volume node affinity conflict", and "3 node(s) had ..." →
  "{nodes} node(s) had ...";
- "no node fits this pod" → "{nodes} Insufficient cpu".

An anchor or evidence string that holds one of these counts changes the
same way. If an anchor is not run through `_sub`, it drops the count:
"node(s) had volume node affinity conflict". The healthy anchor "the other
nodes have insufficient memory" becomes "Insufficient memory". The cause
and rationale sentences that quote the old wording follow it.

The whole 4b-1 story set is swept, not only the lines above. The new rule
finds any line that is missed. The build must show 0 IS-22 violations.

### 2. node-disk-pressure's ContainerStartError keys

`stories.py:1077-1090`. The keys ("containerd", "task") name no origin:
any containerd-task story passes them. They become ("space",
"containerd"). The cause already holds both words: "... containerd failed
to create its task, with no space left on the device". Only meta changes.
This also removes one pool pair, ('containerd', 'task') against "creating
its containerd task exceeded ...".

### 3. The weak pairs: 3 to 1

A weak pair is an ordered pair of exam keys (A, B) with different golds,
where B's gold passes A's key (`tests/test_answer_keys.py:237-274`).

- **Pair 3** is a real clash. A is the coredns-down healthy readiness
  victim, "its readiness probe exceeded its deadline on a slow dependency",
  keyed ("deadline", "exceeded") at `stories.py:243`. B is the catalog
  entry "containerd on the pod's node is not responding (context deadline
  exceeded)". A gets must-not `("containerd",)`. This uses the field from
  item 5.
- **Pair 1.** A is the catalog `networkpolicy-deny-all` entry, keyed
  ("network", "policy"). Its probe is a readiness probe. B is the shared
  default-deny victim whose gold names a failing **liveness** probe. A
  gets must-not `("liveness",)`.
- **Pair 2 stays.** A is the same catalog entry. B is the shared
  default-deny readiness victim. Both golds say a default-deny NetworkPolicy
  is behind a failing readiness probe. That is the same cause, so passing
  it is right. The test's comment says so.

`WEAK_PAIRS` goes from 3 to 1.

### 4. The G2 registry skip

G2 skips a decoy shorter than 3 words. The `deployment-bad-image-tag`
entry's only decoy, "registry registry.example.com", is 2 words, so it
never zeroes an answer. A wrong answer such as "the registry is
unreachable" passes the key ("image", "registry").

The entry (`entries_slugs.py:43-76`, the only catalog entry with a
`registry` decoy object) gets a new tuple in `catalog.py`, next to
`INIT_CONTAINER`:

```python
REGISTRY_FAULT = ("unreachable", "refused", "timed out", "timeout",
                  "unauthorized", "authentication", "rate limit",
                  "dial tcp", "no such host")
```

Its `own_cause_must_not` becomes `INIT_CONTAINER + REGISTRY_FAULT`. The
gold, "the image tag does not exist in the registry", holds none of these
words. The must-not window from 4b-4 still lets a right answer rule one
out: "the registry is not unreachable" does not trip it. G2's 3-word floor
stays.

### 5. Must-not words for the shared-origin family

`stories.Answer` (`stories.py:32-57`) has no must-not field.
`cases.py:1070-1081` passes `own_cause_must_not=[]` to
`render.workload_meta`.

- `Answer` gains `must_not: tuple[str, ...] = ()`. It flows through
  `gold.RowGold` to the row meta's `own_cause_must_not`.
- **Every victim that is not an init-container victim** gets
  `INIT_CONTAINER` added to its must-not words, as the catalog already
  does. An init-container victim is one whose issue or status names an
  init container (for example `Init:ErrImagePull`). Its answers keep their
  own words.
- Item 3's `("containerd",)` sits on top of that.
- The gold check "a key sits only in excluded lines" (`gold.check_keys`)
  also runs on story must-not words: no story gold may hold one of its
  own must-not words.

Across the whole pool there are 178 weak pairs today (208 keys, train, val
and exam together). Most are benign: the same cause in other words, init
vs main container, or two NetworkPolicy names. Keys only grade answers,
and training learns from the gold text. So this spec does not sweep them.
A new test counts the pool's pairs on the build and pins the number, so it
cannot grow unnoticed.

### 6. B6: the real "is forbidden" text

`objects.unverify(obj, "read_failed")` (`objects.py:152-160`) writes a
short text: `nodes "<name>" is forbidden`. kubeagent writes
`read failed: ` + `redact.Error(err)` (`internal/investigate/gather.go`).
`redact.Error` changes only URL errors, so the API server's full text
reaches the prompt. That text names the user and the scope.

The user is always kubeagent's own service account,
`system:serviceaccount:kubeagent:kubeagent`. This is the account the
`deploy/rbac-*.yaml` manifests in kubeagent create. The three texts:

```
nodes "<name>" is forbidden: User "system:serviceaccount:kubeagent:kubeagent" cannot get resource "nodes" in API group "" at the cluster scope
persistentvolumeclaims "<name>" is forbidden: User "system:serviceaccount:kubeagent:kubeagent" cannot get resource "persistentvolumeclaims" in API group "" in the namespace "<ns>"
events is forbidden: User "system:serviceaccount:kubeagent:kubeagent" cannot list resource "events" in API group "" in the namespace "<ns>"
```

`objects.py` needs the PVC's and the events' namespace to write the last
two. `shared_origin.ORIGIN_EVENTS_FORBIDDEN` follows the same form. Every
line stays under the 512-rune cap.

**The Go fixtures keep their bytes.** Each fixture sets a refused read's
message as input, and the Go harness's `kvForbidden(msg)` returns an error
whose text is exactly that message. So the byte-equal test proves that the
text passes through unchanged, whatever it is. No new capture is needed.
Tests that pin the short text built by the generator (not a fixture's
input) move to the long text.

### 7. The tighter checker checks

These are checks that real output already passes. None moves a row. Each
one tightens a rule that already exists, so the count stays at 51 rules.

- **Service lines (`_b6`, `checker.py:918-925`).** The problem wording
  must be one of the wordings kubeagent's `svchealth` prints. Lines must be
  sorted by namespace, then name, then problem (`svchealth.go:33-75`).
- **The network-policy gate (`_b4`, `:876-886`).** A workload's policy
  line may appear only when all its findings are ProbeFailure, or it has
  none (`netpolicy.go:28-42`).
- **A message-only NotReady line (`_f3`, `:1728-1737`).** kubeagent cuts a
  NotReady message at 120 runes plus "…" (`clusterhealth.go:206`). A
  message line longer than that fails. A reason (one CamelCase word, no
  spaces) keeps the 512 cap.
- **Lease ages (IS-15, `_txt_is15`, `:1836-1855`).** kubeagent shows the
  line only when a lease is more than 40s stale, and it rounds to the
  second (`clusterhealth.go:137-144`). So the smallest age it can print is
  40s. Ages from 0s to 39s fail. 40s passes.
- **System lines at 10 rows (`_b7`, `:998-1000`).** Today an extra system
  line passes at 10 rows. An extra line is allowed only when the row has a
  matching flagged kube-system workload past the first 10. Anything else
  fails.
- **ANS-2 (`_ans2`, `:2009-2035`).** It counts only the candidate lines
  that are not ruled out or refuted, by the same rule as
  `gold.drop_excluded` (`gold.py:140-166`).

Each check gets a row in the `tests/test_checker.py` mutation table: a
built row broken in the one way only the new check catches.

### 8. image-pull-secret-expired graded as unverified

This is already true. In `out/dataset-1005`, every pull victim of this
story is job 1 with outcome `unverified`: 71 in train and 6 in val. The two
init victims are job 2 with their own keys. The exam has no row from this
story. A new test builds the story's rows and pins three facts:

- every victim with a registry candidate is job 1, `unverified`;
- the cause is the decided cause;
- its rationale holds no overclaim word (verified, confirm, confirms,
  confirmed).

No generator change.

## The build and the re-pin

**The build.** `kv-dataset --seed 17 --size 8000 --out
out/dataset-1005-exam`.

**Gates.** All must hold before any pin moves:
- train, val and test row counts are recorded, and the exam is 249 rows;
- the checker shows 0 violations of every kind on all splits;
- the gold reply scores 1.0 on job 1, job 2 and job 3;
- the gold reply names a decoy on 0 rows (`decoy_rate`);
- the `none_of_these` share is under 30% in train;
- against `out/dataset-1005`, every changed prompt line is either a
  refused-read line (item 6) or a scheduler line (item 1).

**One re-pin, in the last code task.** Earlier tasks may leave only a named
list of hash and count pins red. Their reports list each red pin with its
old and new value. The last task re-pins all of them at once:

- `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and `GRADED_VIEW_SHA256`;
- `OTHER_FAMILIES_SHA256` (`tests/test_generate.py:1154`), if it moves;
- `_PROBE_DECOYS_SHA256` (`tests/test_cases.py:968`) hashes decoys only and
  should not move. If it does, the task stops and the report says why;
- count pins: `test_oracle`, `test_answer_keys` (`WEAK_PAIRS` 3 to 1, and
  the key count, which counts must-not words too), the `test_score` probes
  and `GATED_POOL` in `test_catalog_gold`.

Each re-pin gets a comment dated "2026-10-05 (exam rebuild)" with the old
value. No test is run with `-update`.

**Tests tied to a fixed folder.**
- `tests/test_exam_prompt_stability.py` reads `BANK` from
  `out/dataset-1005-exam/test.jsonl`.
- The byte tests against `out/dataset-1004`
  (`test_catalog_gold.py:270-285`) and `out/dataset-1004-4b2`
  (`test_multi_decoys.py`) can no longer hold, since items 1 and 6 change
  prompts. They become one "what moved" test against `out/dataset-1005`:
  every changed prompt line is a refused-read line or a scheduler line. It
  skips when the folder is not on the machine, as they do today.

## Numbers to record

Each is measured before (on main) and after (on the branch):

- prompt rows moved and gold rows moved, for train, val and exam;
- IS-22 sum violations before (with the new rule run on the old build) and
  after (0);
- the exam's job counts (102 job-1 workloads, 197 job-2 workloads, 40
  job-3 rows today);
- `WEAK_PAIRS` on the exam (3 to 1), and the pool's pair count (178 today);
- the bots and probes from 4b-4 on job 2: the hedge bot (0.4162), the three
  cut-paste bots (0.0), the two label-strip bots (0.0), the decoy probe
  ({1.0, 174}), the right-answer negator probe (1.0) and the wrong-answer
  negator probe (0.7411). A new probe: answers that name a registry fault
  for the bad-image-tag workloads, which should score 0 on them after
  item 4.

## Docs

- **PIN.md:** a new entry, "### 2026-10-05 — Exam rebuild", with:
  - the three new hashes;
  - the build folder;
  - every number above, before and after;
  - the hand re-pins, each with its old and new value;
  - a "Left" list: B4's fourth arm, and the benign pool pairs.

  The 4b-4 entry's "Left for the exam rebuild" list gets a dated pointer to
  the new entry.
- **docs/model-card.md:**
  - a dated note on each limit whose numbers move;
  - the decoy-rate bullet, if its n moves;
  - the two 0920 sections say they scored the exam as it was before this
    rebuild.
- The writing is simple voice: short sentences, plain words, numbers
  explained.

## Run order

1. The checker checks (item 7). They move no row, so they go first. The
   tests are green after this task.
2. The must-not field and the key changes (items 2, 3, 4 and 5). Only meta
   moves. Hash and key-count pins may go red.
3. IS-22's sum half and the scheduler texts (item 1). The new rule is
   written first. It must fail on the old texts and pass on the new ones.
4. B6 (item 6).
5. The expired-secret test (item 8). It should pass at once. Its purpose is
   to pin the current behavior. A pin test that passes at once is accepted
   here, and the report says so.
6. Build, gates, the "what moved" test, the folder pointers and the one
   re-pin.
7. Docs.

## Done when

- The eight items are in, as above.
- The build passes every gate.
- The full suite is green, with 0 skipped on this machine. Ruff prints
  "All checks passed!".
- The PIN.md entry and the model-card notes are written.
- No bar moved, `score.py` did not change, and no Go fixture byte moved.

## Out of scope

- B4's fourth arm (needs a new Go capture).
- A sweep of the 178 pool pairs.
- Any grader change.
- The 0920 live run, the retrain and the untuned baseline. These come
  after.
