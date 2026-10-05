# `multi` rows and decoys (Spec 4b-3) — design

**Date:** 2026-10-05
**Branch:** `spec4b3-multi-decoys` (cut off `main` @ `5b46542`)
**Status:** approved; amended 2026-10-05 while planning (IS-22 header half only; 4b-1 answers with 4+ workloads move; node count 172)

## What this is

Spec 4b is four specs. 4b-1 (the shared-origin family) and 4b-2 (catalog
gold) are merged. This is 4b-3: **`multi` rows and decoys.**

`multi` is the case with 2 to 4 flagged workloads in one row, each failing
for its own reason. It has 652 train rows and 86 val rows. It has no exam
rows. Its exam cousin is `multi_misattribution_probe` (20 exam rows).

4b-3 has six parts:

1. **Remove the healthy-origin read** from `multi`.
2. **D4: decoy lists from what the prompt shows.** A workload's decoy list
   becomes the causes its prompt shows as ruled out or refuted.
3. **Summary wording.** Say "separate reasons" only when the rows show it,
   and name every workload.
4. **The empty-anchor guard**, carried over from 4b-2's final review.
5. **Node counts that agree.** The scheduler's "0/N nodes are available"
   says the same N as the cluster-health header.
6. **Close the container-name clash** as not a defect.

Then: a new build, the gates, any hand re-pins, and the docs.

The bars do not move: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9.
The grader does not change. Only two of its comments do.

## Why

Measured on `out/dataset-1004-4b2`.

### The healthy-origin read is a read kubeagent never makes

244 `multi` rows (213 train, 31 val, 0 exam) start with a "healthy origin"
read: a shared-origin story's origin, shown healthy. It was the negative
half of the old shared-origin lessons.

kubeagent v1.24.0 never prints a read like it. Its gather makes only
`events ns/pod`, `describe node /X`, `describe pvc ns/X` and
`log causes …` reads, and it always starts with events. The checker has a
special exemption for read 0 just to let this read through
(`checker.py:21`, `:486`). The lesson it taught now lives in
`shared_origin_decoy`, which 4b-1 rebuilt from real reads.

### A decoy list can hold the workload's own gold (D4)

`multi` builds each workload's decoy list from object **intent**: every
candidate whose object was declared a decoy. But 4b-2's gate can name a
decoy-intent object's cause as gold, when the rules leave it unverified
and the workload's own lines show its anchor.

So a workload's own gold sits in its own decoy list for 1,013 train
workloads and 149 val workloads (565 of 652 train rows, 79 of 86 val
rows). All are job 1. It is 0 for job 2 and 0 for every other case.

No grader is hurt today. The decoy gate tests job-2 workloads only. But
the list says "naming this is taking the bait" about the right answer,
and any later grader that reads it for job 1 would mark the right answer
wrong.

### The summary says more than the rows show

Every `multi` gold summary opens with "N workloads are failing for
separate reasons." Two problems:

- **It can be false.** One train row has a `none_of_these` gold. Its
  summary still claims separate reasons.
- **It drops a workload.** The summary lists `rows[:3]`. So 207 train and
  24 val rows say "4 workloads" and then name only 3.

4b-1 already wrote the right rule for its own family (`gold._summary`):
say "separate reasons" only when every row has its own, different cause.
`multi` never got it.

### An empty anchor would match every line

4b-2's gate names a cause when the workload's own lines hold the kit's
anchor. An empty anchor is in every line, so it would always name the
cause. No anchor is empty today, and a test pins that, but nothing makes
it impossible. (4b-2 final review, Minor 5.)

### The scheduler's node count disagrees with the header

Three catalog texts hardcode three nodes:

- `entries_kinds.py:8` (`_UNBOUND_CLAIM`): "0/3 nodes are available: pod
  has unbound immediate PersistentVolumeClaims. preemption: 0/3 nodes are
  available: 3 Preemption is not helpful for scheduling."
- `entries_slugs.py:99-106` (node-cordon-diskfull): "0/3 nodes are
  available: 1 node(s) were unschedulable, 2 node(s) had untolerated
  taint(s). preemption: 0/3 …: 3 Preemption …"
- `entries_slugs.py:282-287` (oversized-job-unschedulable): "0/3 nodes are
  available: 3 Insufficient memory. preemption: 0/3 …: 3 Preemption …"

The header counts nodes as T = max(3, named nodes + 1)
(`render.cluster_health`). A single-workload row names at most two nodes,
so T is 3 and the texts agree. A `multi` row can name more nodes: each
other workload's node shows up as a ruled-out candidate. Then T is 4 or 5,
and the prompt says both "3/4 nodes Ready" and "0/3 nodes are available".

Measured: 172 rows disagree (159 train, 13 val). Every one is `multi`.
Every other case agrees, including the shared-origin family, whose stories
already write `0/{nodes}` and fill it with the row's count.

### The container-name clash is not a defect

96 `multi` rows (86 train, 10 val) quote the same container name on two
or more workloads' `issue:` lines. That is normal. A container name only
has to be unique inside one pod, and kubeagent tells logs apart by
namespace, pod and container (`internal/investigate/gather.go:146`).
Nothing to fix. (The older count of 51 does not reproduce.)

## What stays the same

- The bars, the grader's logic, and every score rule.
- `propagation.py` stays. Deleting it is for later.
- `multi_misattribution_probe`'s prompts and decoy lists. Its summary
  moves to the shared helper (part 3), but its 20 rows must come out byte
  for byte the same (see Tests).
- Every non-`multi` prompt. The node fix fills `{nodes}` with 3 outside
  `multi`, which is what the texts say today.
- Labels. `multi`'s label stays `rules.label(rules.shared(...))`.

## Design

### 1. Remove the healthy-origin read

- `cases.multi` loses its `healthy_origin` parameter, the paragraph about
  it in its docstring, and the four helpers that serve only it:
  `_is_node_story`, `_node_clashes`, `_multi_healthy_origin_node`,
  `_resolve_multi_healthy_origin`.
- The gather always gets the full budget, `c.MAX_TOOL_CALLS` (8).
- The meta keys `origin_read_label` and `origin_healthy` go from `multi`.
- `generate.py` stops computing `healthy` (line 213) and stops passing it.
  Line 213 is the only user of `train_scen`, so the
  `propagation.trainable_scenarios()` call at line 156 goes, and so does
  `propagation` from the import at line 138. The comments at lines 195-212
  and 241 are cut to what still holds. The `propagation:` group prefix
  (lines 519-533) is a string and stays.
- The checker loses its read-0 exemption (`checker.py:21` docstring line
  and the check at `:486`).
- Tests that pinned the read are deleted or rewritten (see Tests).

`healthy` drew no randomness, so removing it moves only those 244 rows.
Each one gains its first read back: its gather now has 8 reads, not 7.

### 2. D4: decoy lists from what the prompt shows

In `multi`, a workload's decoy list becomes:

```python
decoy_by_workload[key] = list(gold.excluded_from(candidates, result))
```

That is the causes the prompt shows as ruled out, plus the rules' refuted
decisions — the same set 4b-2's gate already strips from a workload's own
lines. The `rules.attribute` call that only fed the old list goes.

One new test runs over **every case** in a full build: no workload's gold
cause is ever in its own `decoy_by_workload` list. This holds by
construction for `multi` (a gold never comes from an excluded line), and
the test keeps it true for every other case too.

`score.py` comments at `:215` and `:795` say a `shared_origin_probe` row
lists a decided workload's own cause as a decoy. That has been false since
4b-1, and the new test now pins it false everywhere. The comments are
rewritten to say why job 1 is still skipped: widening the decoy gate to
job 1 is a grader change, and grader changes belong to 4b-4. The code does
not change.

### 3. Summary wording

One helper builds the summary for `multi` and `multi_misattribution_probe`.
It lives in `gold.py`, next to 4b-1's `_summary`, and 4b-1's `_summary`
uses it for its non-shared lines so the rule is written once.

The helper takes `separate: bool` from its caller and writes the lines.
Each caller decides `separate` by its own rule:

- **`multi` and the probe:** `separate` is true when the label is
  `separate` (the rules confirmed different causes on two or more
  workloads), or when every row has its own named cause (none is
  `none_of_these`) and no two rows share a cause.
- **4b-1's family:** its existing rule, unchanged (the two conditions
  above plus the healthy world).

The rule:

- **Opening line.** "N workloads are failing for separate reasons." when
  `separate` is true. Otherwise: "N workloads are failing, and
  kubeagent's rules did not confirm one cause on two or more of them."
  (4b-1's fallback, word for word.)
- **One line per workload**, in row order: `key: cause.`, or
  `key: its own lines do not show why.` for a `none_of_these` row.
- **At most 4 lines** (`c.MAX_SUMMARY_LINES`). With 4 or more workloads,
  the 3rd and every later one share the last line, joined by one space.

4b-1's `_summary` keeps its `shared` branch as it is and calls the helper
for the rest. Its summaries stay byte for byte the same, with one
exception. Today its non-shared branch names only the first 3 rows. The
helper names every row, so a non-shared 4b-1 row with 4 or 5 workloads
gains its missing names. That is 77 train and val rows (amended
2026-10-05, found while planning). No exam row moves: every 4b-1 exam row
with 4 or more workloads is `shared`, and the `shared` branch does not
change.

Scoring, checked on the real scorer: for label `none`, both openings score
job 3 = 1.0 (neither claims a shared cause). For label `separate`, only
"separate reasons" scores 1.0. In `multi` today, 13 train rows are
`separate` and the rest are `none`. Because a `separate` label always
sets `separate`, a `separate` row always gets the opening that scores.
A test checks every `multi` and probe row anyway (see Tests).

The longest possible last line (two keys and two causes) stays under
`c.MAX_MODEL_LINE_RUNES` (512). A test checks that too.

### 4. The empty-anchor guard

`stories.Answer` raises `ValueError` when its anchor is empty or only
whitespace. `cases._entry_gold` raises `ValueError` when the anchor is
empty **after formatting** (a template like `"{image}"` with an empty
name). The build then fails instead of naming a cause on every row.

### 5. Node counts that agree

**The texts.** The three catalog texts get placeholders, the way
`stories.py` already writes its scheduler texts:

- `0/3 nodes are available` → `0/{nodes} nodes are available` (both
  places in each text);
- `3 Preemption is not helpful` → `{nodes} Preemption is not helpful`;
- `3 Insufficient memory` → `{nodes} Insufficient memory`;
- `2 node(s) had untolerated taint(s)` → `{other_nodes} node(s) had
  untolerated taint(s)`, where `other_nodes` is `nodes − 1`.

The taint line stays true at 4 or 5 nodes. The extra nodes are the other
workloads' nodes. A NotReady node carries the `not-ready` taint, and a
Ready one carries whatever taint kept it from this pod; either way the
scheduler counts it under "untolerated taint(s)".

**The fill.** `Names` gets one more field, `nodes: int = 3`.
`names.draw` never sets it, so no draw changes. `cases._fmt` fills
`{nodes}` with `n.nodes` and `{other_nodes}` with `n.nodes - 1`. Every
case except `multi` leaves it at 3, so its bytes do not change.
`catalog.py`'s placeholder comment adds the two names.

**The count.** `render.py` gets `node_total(workloads, reads) -> int`.
It is the T that `cluster_health` already computes, pulled out so both
use one function. `cluster_health` calls it; its output does not change.

**`multi`.** It builds the row once with `nodes=3`, then asks
`render.node_total` for T. If T is 3, it is done. If not, it rebuilds the
workloads and the gather with `nodes=T` on every pair's `Names`. It
reuses the objects `_multi_objects` already drew; it never draws them
again. Neither step draws randomness, and the gather does not either, so the second
build has the same candidates, the same read labels and the same T. Only
the scheduler numbers change. (A digit for a digit: no read grows or
shrinks, so no cap moves.) The builder asserts that the second T equals
the first.

**The checker.** One new rule, IS-22, on every row: when the prompt prints
a cluster-health header with T nodes, every `0/N nodes are available` in
the prompt has N = T.

Today's checker would not catch the mismatch. This rule makes it a build
failure from now on.

(Amended 2026-10-05, found while planning. The draft had a second half:
the numbers that open a scheduler message's reasons add up to N. That
half fails on 4b-1's own stories, exam rows included, so adding it now
would break the exam. It is left for the exam rebuild.)

### 6. The container-name clash

No code. PIN.md and the 4b-1 spec record it as closed, with the count
(96 of 738) and the reason above.

### What moves

| What | Rows | Why |
|---|---|---|
| `multi` prompts that had the healthy-origin read | 244 (213 train, 31 val) | the read goes; the gather gets 8 reads |
| `multi` prompts with a node mismatch | 172 (159 train, 13 val) | scheduler numbers match the header |
| `multi` answers | most of 738 | new summary; some rows also move with the prompt |
| 4b-1 non-shared answers with 4-5 workloads | 77 (train and val) | the summary names every workload |
| `multi` meta | 738 | new decoy lists; `origin_*` keys gone |
| non-`multi` rows | 0 | nothing they use changes |
| exam (`test.jsonl`) | 0 expected | `multi` has no exam rows; the probe stays byte-identical |

The two prompt sets can overlap. The plan measures the real counts.

## Tests

TDD, as always: each test is written first and seen to fail.

1. **No healthy-origin read.** No `multi` row in a full build has
   `origin_read_label` or `origin_healthy` in its meta, and its first read
   is an `events` read. `multi` no longer accepts `healthy_origin`.
2. **Checker exemption gone.** A row whose read 0 is not an `events` read
   now fails the checker, even with `origin_read_label` in its meta.
3. **D4 per case.** For a `multi` row, each workload's decoy list equals
   `gold.excluded_from(candidates, result)`.
4. **D4 across cases.** Over a full build: no workload's gold cause is in
   its own decoy list, for every case. The test asserts it saw more than
   1,000 workloads with a decoy list, so it cannot pass empty.
5. **Summary rule.** Unit tests for the helper and `multi`'s `separate`
   rule: all named and different → "separate reasons"; one
   `none_of_these` → fallback; two rows with the same cause → fallback;
   label `separate` with one `none_of_these` row → "separate reasons";
   4 rows → 4 lines, rows 3 and 4 on the last line, every key named; 2
   and 3 rows → one line per row.
6. **Summary over the build.** Every `multi` and probe gold summary names
   every workload key, has at most 4 lines, has no line over 512 runes,
   and scores job 3 = 1.0 for its own label on the real scorer.
7. **Probe bytes.** The 20 `multi_misattribution_probe` rows are byte for
   byte the ones in `out/dataset-1004-4b2/test.jsonl`.
8. **4b-1 bytes.** Every shared-origin family row's answer is byte for
   byte the one in `out/dataset-1004-4b2`, except a non-shared row with 4
   or more workloads. Those rows differ only by naming every workload.
9. **Empty anchor.** `stories.Answer(anchor="", …)` and `anchor="  "`
   raise. `_entry_gold` raises on an anchor that formats to empty.
10. **Node fill.** `_fmt` with default `Names` gives the old text exactly.
    With `nodes=5` it gives `0/5`, `5 Preemption`, `5 Insufficient memory`
    and `1 … unschedulable, 4 … untolerated taint(s)`.
11. **`node_total`.** It returns what `cluster_health` printed before, on
    every row with a header in `out/dataset-1004-4b2`.
12. **IS-22.** It fails a row with "3/4 nodes Ready" and "0/3 nodes are
    available". It passes a row with no header. On a full new build it
    finds 0 violations.
13. **Non-`multi` prompts.** Every non-`multi` user message is byte for
    byte the one in `out/dataset-1004-4b2`.
14. **Old tests.** The tests that pinned the healthy-origin read
    (`test_checker.py:628-672`, `test_generate.py:1075-1088`,
    `test_cases.py:1115-1118`, `test_shared_origin_training.py:541`,
    `:694-698`, `:705`, and all of `tests/test_multi_collision.py`) are
    deleted or rewritten to the new rule. Tests that check other families
    never carry `origin_read_label` stay as they are, and so does
    `test_ruled_scenarios.py:190`, which checks the propagation pool, not
    `multi`.
    The two share tests in `test_shared_origin_training.py` (`:597` and
    the kept-pile test after it) measured the share of `multi` negatives.
    With the healthy-origin read gone, both shares are exactly 0.5, below
    their old floors (0.55 and 0.52). They are rewritten to assert 0.5,
    with a dated note. These floors are test bands, not the bars.

## The build and the re-pin

1. Build into a new folder, `out/dataset-MMDD` (the build date). Never
   touch `out/dataset-1004`, `out/dataset-0929` or `out/dataset-1004-4b2`.
2. Gates: checker violations 0; the full suite green; ruff "All checks
   passed!".
3. Measure and record in PIN.md:
   - how many `multi` rows moved, prompt and answer, train and val;
   - the `none_of_these` share in `multi`, before and after;
   - the label mix in `multi`, before and after;
   - D4: workloads whose gold is in their own decoy list (expect 0);
   - node mismatches (expect 0);
   - whether `test.jsonl` is byte-identical.
4. If `test.jsonl` is byte-identical, no exam hash moves. If any hash
   does move, it is re-pinned by hand with the reason written next to it.
   Never `-update`.

## Docs

- **`contract/PIN.md`:** a 2026-10-05 entry with the numbers above. In the
  "Left for 4b-2, 4b-3 and 4b-4" list and the D4 items (`:654`, `:767`),
  mark 4b-3's items done, and the container-name clash closed with its
  reason.
- **`docs/model-card.md:1106`** and **`docs/design.md:421`:** they say
  "Spec 4b-3 owns `multi`". Rewrite them to say what `multi` is now: no
  healthy-origin read, decoy lists from the prompt, and the summary rule.
- **`docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md`:**
  a "Done 2026-10-05" line under 4b-3 in its left-for list, pointing here.

Simple voice throughout: short sentences, plain words, numbers explained.

## Run order

1. Empty-anchor guard (small, alone).
2. Summary helper, used by `multi`, the probe and 4b-1's `_summary`.
3. D4 decoy lists, the cross-case test, and the `score.py` comments.
4. Remove the healthy-origin read, from `cases`, `generate`, the checker
   and the tests.
5. Node counts: placeholders, `Names.nodes`, `_fmt`, `node_total`,
   `multi`'s second build, and IS-22.
6. Build, gates, measurements, any re-pin.
7. Docs.

Parts 2-5 each move `multi` rows, so tests that compare against
`out/dataset-1004-4b2` must say which rows they allow to move.

## Done when

- The full suite passes and ruff prints "All checks passed!".
- A new build has 0 checker violations, including IS-22.
- No `multi` row has a healthy-origin read or an `origin_*` meta key.
- No workload, in any case, has its own gold in its own decoy list.
- Every `multi` and probe summary names every workload, fits 4 lines, and
  scores job 3 = 1.0 for its label.
- Every "0/N nodes are available" agrees with the header.
- Non-`multi` prompts, the probe rows and the 4b-1 family's answers are
  byte-identical to `out/dataset-1004-4b2` (4b-1's non-shared answers
  with 4 or more workloads excepted, see part 3).
- PIN.md, the model card, design.md and the 4b-1 spec say what changed.

## Out of scope

- The shared-origin container mismatch (389 train rows, a 4b-1
  leftover).
- Deleting `propagation.py`.
- The 4+-letter kit-key guard (the 3-letter keys are "key", "tag" and
  "pod"). It goes to 4b-4 with the other grader leftovers.
- Widening the decoy gate to job 1. That is a grader change, for 4b-4.
- IS-22's sum half (a scheduler message's reasons add up to N). It fails
  on 4b-1 stories, exam rows included, so it waits for the exam rebuild.
- The exam rebuild and re-pin, the 0920 live run, and the retrain. They
  come after 4b-4.
- Training, a live model run, and anything under `dist/`.
