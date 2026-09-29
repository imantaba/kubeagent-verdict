# Grader guard and weak keywords (Spec 4a) — design

**Date:** 2026-09-29
**Branch:** `spec4a-grader` (cut off `main` @ `ce6688f`)
**Status:** approved (883e663); implemented on `spec4a-grader`

## What this is

Spec 4 is split in two. Both halves land before the one retrain.

- **4a, this spec**, fixes how the exam grades job 2. It changes the
  grader and seven answer keys. It changes no prompt and no gold answer.
- **4b, the next spec**, fixes the training data: the shared-origin
  stories, facts in gold text that the prompt does not show, and the
  fidelity items. It gets its own branch after 4a merges.

4a goes first. It is small, it moves no training message, and 4b then
works against a grader it can trust.

4a has six parts:

1. One cleaning step, with Unicode NFKC, for every job-2 text match.
2. G3b also zeroes a pasted line with its first 1 or 2 words cut off.
3. G2 skips a decoy shorter than 3 words.
4. `decoy_rate` counts job-2 workloads only.
5. Seven answer keys get "must-not" words. Two of those also get the
   required word `init`.
6. The keyword rule is written once, not twice.

The bars do not move: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9.

## Why

Every number below is measured on the Spec 3 exam,
`out/dataset-0928/test.jsonl`: 249 rows, 177 job-2 workloads. The bots
are the suite's own, in `tests/test_score.py`.

### A cut paste clears the job-2 bar (model-card limit 11)

G3b zeroes an answer that holds a whole line of the workload's own block.
Cut one word off the front of each line and no whole line is left.

| Bot (reads nothing) | Job 2 today |
|---|---|
| Own lines, first word cut (`_trimmed_paste_bot`) | 147 of 177 = 0.8305 |
| Own lines, first 2 words cut | 147 of 177 = 0.8305 |
| Own lines, first 2 words swapped | 153 of 177 = 0.8644 |

All three are over the 0.7 bar.

### A right answer that names the registry host scores 0 (limit 12)

30 job-2 workloads have the gold answer "the image tag does not exist in
the registry". 29 of them carry the decoy `registry registry.example.com`.
Add the host to the gold answer and the decoy sits inside it, so G2
zeroes a right answer. The gold reply with the host scores 148 of 177 =
0.8362. The plain gold reply scores 177 of 177.

That decoy is 2 words long. It is the only exam decoy under 3 words: 35
mentions, all on job-2 workloads. The other 536 decoy mentions are 3
words or longer.

### Weak keywords grade a wrong cause right

A job-2 answer scores 1 when it holds every keyword. Some keys use common
words, so another story's answer can pass them.

- The exam has 33 answer keys. In 34 pairs, one story's gold answer
  passes a different story's key.
- 0920 got 2 wrong answers graded right this way. Both are
  `multi_misattribution_probe` rows (0-based rows 197 and 198). The
  answer key is "the pod's memory request is larger than any node can
  allocate", with the keywords `memory` and `node`. 0920 wrote "the pod's
  node has a MemoryPressure condition …" and "the pod's node is cordoned
  and reporting Insufficient memory …". Both hold `memory` and `node`.

### `decoy_rate` counts right job-1 answers as decoys

The loop at `score.py:747-760` reads every workload's decoy list, with no
job filter. A decided (job-1) workload's right answer can equal a decoy
in the row-level list, so it counts as "named a decoy". The gold reply
itself names a decoy on 10 of 190 measured rows. 0920 does on 8 of 190.
Counting job-2 workloads only, both are 0 of 128.

## What stays the same

- **No prompt, gold answer, system message or decoy changes.** A scratch
  build with the two `init` keys changed matched `out/dataset-0928` on
  the messages of all 7,427 rows.
- **The bars.**
- **`none_of_these` is still an exact match** on `cause.strip().lower()`.
  The new cleaning step does not apply to it, so `none_of_these.` still
  scores 0.
- **Keyword exposure** still counts required words only. It stays 169 of
  169 with the new `init` word.
- **The checker.** No rule changes. ANS-2 finds nothing on any of the
  7,427 rows with the new `init` word.
- **An old exam file still grades.** Its meta has no
  `own_cause_must_not`, so the must-not list is empty. The guard changes
  apply to it. The must-not check does not.

## Design

### 1. One cleaning step

`_norm_cause(s)` becomes: NFKC, then lowercase, then strip, then strip
trailing periods, then collapse whitespace. Today it does all but NFKC.

All job-2 matching goes through it:

- G2, on the cause and on each decoy.
- G3b, on the cause. The own lines already pass through it in
  `_own_blocks`, so they get NFKC too.
- The keyword match. Today this reads `cause.strip().lower()`; it moves
  to `_norm_cause`. Every keyword is one word today, so collapsing
  whitespace changes no match. The only new effect is NFKC: a decoy or a
  keyword written in full-width letters now matches.
- The must-not match.

NFKC changes 0 of the 4,301 exam texts measured, so no exam score moves
because of it.

### 2. G3b: a line with its first words cut

Today G3b zeroes a cause that holds a whole own line. It now also zeroes a
cause that holds the line minus its first 1 word, or minus its first 2
words, as long as at least 3 words are left.

```python
def _g3b(c: str, own_lines: Iterable[str]) -> bool:
    for line in own_lines:
        if not line:
            continue
        if line in c:
            return True
        words = line.split()
        for cut in (1, 2):
            if len(words) - cut < 3:
                break
            if " ".join(words[cut:]) in c:
                return True
    return False
```

**Why a 3-word floor.** Without it, 1- and 2-word pieces of a line sit
inside right answers. Measured with no floor: gold 176 of 177, and 0920
loses a right answer.

**Why not cut 3 words.** A 3-word cut zeroes 6 gold answers (171 of 177)
and takes 0920 to 134 of 177 = 0.7571. Gold must stay 177 of 177.

**What it does not catch.** A single clause lifted out of the middle of a
printed line still passes. 0920 wrote 5 right answers this way (exam rows
53, 56, 156, 192 and 211). Each cuts 3 leading tokens, `issue: oomkilled
—`, and two also cut the tail, for example `container exceeded its memory
limit and was killed`. A sixth copy, on row 196, names the wrong cause
and scores 0 anyway. These
answers name the right cause in the prompt's own words. A rule that
zeroes them would also zero gold answers: 17 gold sentences are printed
in their own prompts. So 4a keeps them, and the model card says plainly
that on those rows job 2 cannot tell reading from copying.

### 3. G2: skip a decoy under 3 words

G2 skips any decoy that is under 3 words after cleaning. On the exam that
is only `registry registry.example.com`. A hedge between the cause and
that decoy now passes too. That cost is measured and pinned (the hedge
bot, below).

### 4. `decoy_rate` counts job-2 workloads only

The loop at `score.py:747-760` skips any workload whose `job` is not 2. A
row with no job-2 workload that has a decoy gets `named_decoy = None`,
not `False`, so it is left out of the rate, not counted as a pass. That
is the contract the loop already keeps for a row with no decoy.

### 5. Must-not words, and `init`

**The field.** `CatalogEntry` gains `own_cause_must_not: tuple[str, ...]
= ()`. Every workload's meta gains `own_cause_must_not`, a list. It is
always present, the same as `own_cause_keywords`.

**Where it comes from.** It travels with the keywords. A workload whose
keywords come from catalog entry `e` gets `e.own_cause_must_not`. A
workload with no keywords gets `[]`: a decided workload, a
`none_of_these` workload, or a shared-origin workload whose keys come
from `propagation.py`. `render.workload_meta` takes it as a required
keyword argument, so no caller can forget it. The meta dict goes from
seven keys to eight.

**The rule.** A named-cause job-2 answer scores 1 when the cleaned cause
holds every required word and no must-not word.

**The table.** These are the seven entries that change. Every other
entry keeps its keys and gets no must-not words.

| Entry | Required (was) | Required (now) | Must not |
|---|---|---|---|
| `memory-limit-oomkill` | memory, limit | same | init container |
| `deployment-bad-image-tag` | image, registry | same | init container |
| `container-start-error` | container, image | same | init container, tag |
| `init-errimagepull` | tag, registry | init, registry, tag | — |
| `init-imagepullbackoff` | registry, tag | init, tag, registry | — |
| `oversized-job-unschedulable` | memory, node | same | cordon, pressure |
| `volume-mount-error` | volume, pod | same | provision |

"Init container" is written three ways, and each one is its own must-not
word: `init container`, `init-container`, `initcontainer`. Never bare
`init`: "initial" and "initialize" would trip it.

The two new init lists use the word order this spec's numbers were
measured with. Order does not change a grade, but it is part of the
meta, so the build uses exactly these lists.

**Why each one.**

- The first three are the main-container stories. Today an
  init-container story's answer passes each of their keys:
  - "the init container's memory limit is too small …" passes
    `memory-limit-oomkill`;
  - "the init container's image tag does not exist in the registry"
    passes `deployment-bad-image-tag` and `container-start-error`;
  - "the init container image name has a typo" passes
    `container-start-error`.

  The init-container must-not words stop all of them.
  `container-start-error` also blocks `tag`, as a second lock. A bad-tag
  answer that drops "init", such as "the container's image tag does not
  exist", also holds `container` and `image`.
- The two init bad-tag stories gain `init`. Without it, the main
  container's answer, "the image tag does not exist in the registry",
  passes their keys, and so do the two shared-origin tag answers.
- `oversized-job-unschedulable` blocks `cordon` and `pressure`. No gold
  answer on the exam passes this key today. The two words are there for
  wrong answers like 0920's two. A node that is cordoned, or under memory
  pressure, is a different cause from a request no node can fit.
- `volume-mount-error` blocks `provision`. That stops "a claim the pod
  mounts is still waiting for its volume to be provisioned" from passing
  `volume` and `pod`.

**What it does.**

| | Today | 4a |
|---|---|---|
| Gold reply, job 2 | 177 of 177 | 177 of 177 |
| 0920 replay, job 2 | 144 of 177 | 142 of 177 (rows 197 and 198 only) |
| Key pairs where one story's gold passes another's key | 34 | 21 |

**How these were picked.** The first try had a script pick new required
words for each weak key. Several of its picks were odd words for the
cause they graded. So the words here are picked by hand. The old required words stay, and must-not words are added. No old
right answer loses its point. Only the two wrong ones do.

### 6. The keyword rule, written once

Today the rule is written twice: in `job2`, and in the `cause_acc` count
inside `evaluate`. Both move to one helper:

```python
def _keywords_match(cause: str, keywords: Iterable[str],
                    must_not: Iterable[str] = ()) -> bool:
    c = _norm_cause(cause)
    return (all(str(k).lower() in c for k in keywords)
            and not any(str(m).lower() in c for m in must_not))
```

`job2` gains a keyword argument, `own_cause_must_not`, default `()`.
`evaluate` passes `wm.get("own_cause_must_not") or []` to both callers.
`test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row` keeps the
two in step.

### 7. The 21 weak pairs, pinned

A new test builds the exam in-process with `generate.test_set()`. It
collects each keyword-graded job-2 answer key: required words, must-not
words, and expected cause. The exam has 33 keys. The two init bad-tag
entries share one gold sentence but have different word lists, so they
are two keys.

The test then lists every ordered pair of keys (A, B) with different
gold sentences where B's gold sentence passes A's rule. It pins that
list, exactly:

| Key A | Passed by B | Pairs |
|---|---|---|
| `node-cordon-diskfull` (node, pod) | 8 other stories' answers | 8 |
| shared-origin (tag, exist), 2 keys | each: the main bad-tag key, the 2 init bad-tag keys, the other tag key | 8 |
| `deployment-bad-image-tag` (image, registry) | the 2 shared-origin tag answers | 2 |
| shared-origin (pressure, evicting), 2 keys | each other | 2 |
| shared-origin (secret, namespace) | `init-config-error`'s answer | 1 |
| **Total** | | **21** |

All 21 are 4b's. `node-cordon-diskfull`'s key is weak because its story
is being rewritten (model-card limit 10). The other 13 involve
shared-origin keys, which 4b rewrites. 4b must shrink this list. A change
that grows it fails the test.

## The build and the re-pin

1. Build with the same seed and size into a new folder:
   `kv-dataset --seed 17 --size 8000 --out out/dataset-0929`. Nothing
   under `out/` that exists today is touched.
2. **The gate.** Compare `out/dataset-0929` with `out/dataset-0928`, row
   by row, over all 7,427 rows:
   - `messages` byte-equal on every row;
   - `meta` equal once the planned changes are taken out:
     - `own_cause_must_not` on every workload;
     - the two init entries' `own_cause_keywords` (316 workloads in the
       bank);
     - the row-level `expected_own_keywords` on those two entries'
       `own_cause` rows.

   Any other difference stops the work, and I report it.
3. **Re-pin by hand.** Never with `-update`.
   - `contract/PIN.md`: the three bank hashes, `test.jsonl`,
     `train.jsonl` and `val.jsonl`, for `out/dataset-0929`.
   - `FROZEN_SLICE_SHA256` and `EVAL_SET_SHA256` in
     `tests/test_shared_origin_training.py`, and `GRADED_VIEW_SHA256` in
     `tests/test_exam_graded_view.py`. All three hash each row's meta, so
     all three move. Each gets a dated comment: meta only, no message
     moves.
4. **Replay 0920** under the new grader. No model is called:
   `kv-eval --replay out/eval/0920-exam0928 --test out/dataset-0929/test.jsonl --out out/eval/0920-exam0929-replay`.
   Expected: job 1 0.95, job 2 142 of 177 = 0.8023, job 3 0.875.

No training, no live run, and nothing under `dist/`.

## Tests

TDD: each test is written first and seen to fail.

**Flip the two known-gap tests.**
- `test_a_trimmed_paste_clears_the_job2_bar_a_known_gap_in_the_guard`
  becomes a test that the trimmed-paste bot scores 0 of 177. It gets a new
  name that says so.
- Two new bots join it: first 2 words cut, and first 2 words swapped.
  Both score 0 of 177.
- `test_a_right_bad_tag_answer_that_names_the_registry_host_is_zeroed_by_g2`
  becomes a test that the gold reply with the host scores 177 of 177. It
  also gets a new name.

**The guard.**
- The 3-word floor: a line whose cut would leave 2 words is not cropped.
  A right answer that holds such a 2-word piece is not zeroed.
- NFKC: a cause that holds a decoy in full-width letters is zeroed. A
  right answer in full-width letters passes its keywords.
- G2 floor: a hedge with a 2-word decoy passes G2; a hedge with a 3-word
  decoy is zeroed.

**Must-not.**
- The answers 0920 wrote on rows 197 and 198 score 0.
- Every exam gold answer passes its own key: 177 of 177.
- Each of the three init spellings trips `memory-limit-oomkill`'s key.
  "initial" does not.
- A build test: meta carries `own_cause_must_not` on every workload,
  matching the table, and empty everywhere else.

**Pinned numbers that move.**

| Test | Today | 4a |
|---|---|---|
| Hedge bot, job 2 | 32 of 177 = 0.1808 | 61 of 177 = 0.3446 |
| Own-keyword bot, job 2 | 177 of 177 | 177 of 177 (reads the new keys) |

The 29 new hedge passes are the bad-tag rows whose first decoy is the
2-word registry decoy.

**Pinned numbers that do not move.**
- Keyword exposure: 169 of 169.
- The weak-pair list: exactly the 21 above.
- `decoy_rate`: job-2 scope. A row whose only decoys sit on job-1
  workloads is unmeasured (`None`).

Tests that assert the seven-key meta dict move to eight keys. The full
suite must be green at the end.

## Docs

- **`docs/model-card.md`**:
  - Add a short entry, "0920 re-scored under the 4a grader", with the
    replay numbers.
  - Close limit 12. The gold reply with the host now scores 177 of 177.
  - Close limit 11 for pastes: the three cut-paste bots score 0. Then
    restate what is left, in plain words: a single clause lifted out of a
    printed line still passes, and why it must.
  - Update the weak-keyword note: 34 pairs down to 21, with the 21 left
    for 4b.
  - Update the bot table: hedge 0.3446, the cut pastes 0, gold with host
    1.0, own-keyword bot 1.0. A reply built from the old keys, without
    `init`, now scores 165 of 177.
- **`contract/PIN.md`**: the new bank hashes. Split "Left for Spec 4"
  into "Done in 4a" and "Left for 4b".
- **This spec**, committed on `spec4a-grader`.

## Run order

1. Spec 4a: this spec, the plan, the build, the re-pin, the 0920 replay.
2. Spec 4b: regenerate the bank, re-pin, then 0920 live again.
3. Retrain once, about 32 hours.
4. The untuned baseline.

## Done when

| Check | Target |
|---|---|
| Message differences, `out/dataset-0929` vs `out/dataset-0928` | 0 of 7,427 rows |
| Meta differences | only the planned ones |
| Gold reply, job 2 | 177 of 177 |
| Cut-paste bots (first word cut, first 2 cut, first 2 swapped) | 0 of 177 each |
| Gold reply with the registry host | 177 of 177 |
| 0920 replay | job 1 0.95, job 2 142 of 177 = 0.8023, job 3 0.875 |
| Hedge bot | 61 of 177 |
| Keyword exposure | 169 of 169 |
| Weak pairs | exactly the 21 left for 4b |
| `decoy_rate` on 0920 and on the gold reply | job-2 scope, 0 of 128 each |
| Bars | unchanged |
| Full test suite | green, no `-update` |

## Left for 4b

- **The shared-origin stories.** 2,420 rows. `EXEMPT_CASES` skips 19 of
  the checker's 49 rules for them. They carry prose candidates and "decided
  by rules" node lines kubeagent could not print. All 5 of 0920's job-3
  misses are these rows. kubeagent has only three candidate kinds (node,
  PVC, registry), sets a group key only on a confirmed cause, and never
  shows the model the Shared line.
- **`node-cordon-diskfull`'s made-up disk pressure** (model-card limit
  10): 236 rows, 10 on the exam. It is also the weakest key in the 21.
- **The 13 shared-origin weak pairs** in the pinned list.
- **Gold confidence** comes from a fixed flag, `_confidence(e)`: 45
  verdicts on 40 exam rows.
- **Gold rationale facts** the prompt does not show, across many
  stories.
- **`probe-failure`'s "no restart" text**: 155 rows.
- **`coredns-corefile-broken`**: `restartCount=6` contradicts its
  evidence on 96% of its rows, and its namespace is never `kube-system`.
- **Pending pods with restarts**: 648 rows.
- **Container-name clashes**: 51 of 738 multi rows.
- **The B6 short form "is forbidden"**: 987 rows.
- **Not-ready taint captures**: these need the Go side.
- **`multi`'s `decoy_by_workload`** is keyed on the static intent
  (`cases.py:1555-1556`).
- **`log_cause` is never swapped** on the decoy half.
- **Model-card limits 1 to 9** have no spec yet.

## Out of scope

- Any prompt, gold answer, system message or decoy change. That is 4b.
- Training, a live model run, and anything under `dist/`.
- Moving a bar.
