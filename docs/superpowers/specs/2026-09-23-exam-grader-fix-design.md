# Exam grader fix — design

**Date:** 2026-09-23
**Branch:** `fix-exam-then-override` (cut off `main` @ `116092b`)
**Status:** approved as written

## What this is

The release exam scores 20 of its 153 job-2 workloads as wrong no matter
what the model answers. This spec fixes that, then re-scores the run we
already paid for.

It does **not** try to make the release pass. It makes the number true.
Whether the number then clears the bar is a separate question with its
own spec.

## The defect

`render.workload_meta`
([render.py:239](../../../src/kubeagent_verdict/dataset/render.py)) accepts
an empty `own_cause_keywords` list for a workload whose expected answer is
a named cause. `score.job2`
([score.py:158](../../../src/kubeagent_verdict/evals/score.py)) then returns
`0.0` for that workload, whatever the reply says, because
`_is_job2_keyword_graded` ([score.py:142](../../../src/kubeagent_verdict/evals/score.py))
is false and the workload is not the `none_of_these` sentinel.

The missing data is not the bug. The bug is that **missing data is
silently legal**. Nothing refuses it, nothing reports it, and the
workload simply scores zero.

`_render_shared_origin` passes `own_cause_keywords=[]` for every
undecided shared-origin workload
([cases.py:1012](../../../src/kubeagent_verdict/dataset/cases.py)). The
comment there is honest about the gap. Nobody traced what it cost.

### What it cost

20 of 153 job-2 workloads, all in the two shared-origin slices:

| slice | workloads | scored | actually right |
|---|---|---|---|
| `shared_origin_decoy_probe` | 16 | 0.0% | about 13 of 16 |
| `shared_origin_probe` | 4 | 0.0% | 2 of 4 |

Published job 2 is 89 of 153 = 0.5817. Graded properly it is about
104 of 153 = 0.68.

### Why nobody caught it

`tests/test_oracle.py` feeds the exam its own gold answers and checks
that a perfect model scores perfectly. It pins that ceiling for job 1
and job 3. **There is no `test_exam_oracle_job2`.** The one job with a
broken ceiling is the one job whose ceiling nobody pinned.

## Design

### 1. Refuse in the grader, not in the renderer

`score.py` raises when it meets a job-2 workload whose expected cause is
a named cause and whose keyword list is empty. It names the workload. It
does not return `0.0`.

**Why the grader and not the renderer.** `_render_shared_origin` is
shared by the 6 eval scenarios and the 54 training ones. Raising where
the data is created would force curating all 217 cause templates
(163 victim causes + 54 shared causes) just to generate training data
that no grader ever reads. The grader only ever sees the exam, so it is
the narrow seam. An exam it cannot grade is a corpus defect and should
say so out loud.

The refusal is narrow: job 2 only, named cause only, empty list only.
`none_of_these` workloads need no keywords and are untouched. Job-1
workloads are untouched.

### 2. Twenty-two curated keyword pairs

Add `own_cause_keywords: tuple[str, ...] = ()` to `propagation.Victim`
and to `propagation.Propagation`.

The eval set is `propagation.all_scenarios()` — 6 scenarios, 16 victims.
So 16 victim pairs plus 6 shared-cause pairs = **22 pairs**. The default
of `()` leaves the 163 training victims and 54 training scenarios alone.

### 3. The curation rule

**Pick two words that tell this cause apart from the other causes on the
same menu.** Not the first two words of the sentence.

This is not a style preference. Here is the failure, measured on the
banked replies:

- gold cause: `node worker-3 is under disk pressure, so it is evicting pods and refusing new ones`
- first-two-words keywords: `node`, `worker-3`
- the model answered: `node worker-3 (no kubelet lease)`
- result: **scored correct**

Right node, wrong reason, full credit. With `pressure` as a keyword it
scores wrong, which it is. Two of the four override rows fail this way
under naive keywords.

Every curated pair already in the repo follows the distinguishing rule —
`application`+`readiness`, `configmap`+`key`, `memory`+`init`. This spec
writes the rule down rather than inventing it.

### 4. Curate blind

The pairs are chosen by reading the cause string and the other causes on
its menu. **They are never chosen by checking what they do to the
score.** No pair may be revised because it lowered the result.

This matters more than anything else in this spec. The exam fix must not
become the way the model passes. If the keywords are tuned toward a
passing number, the number stops meaning anything and every later build
inherits the lie.

A test enforces it mechanically: for each eval scenario, a victim's
keywords must **not** all appear in its twin's gold cause. Keywords that
fail to discriminate fail the suite, whatever they do to the score.

### 5. Pass them through

`_render_shared_origin` uses the victim's keywords in the healthy world
and the scenario's shared-cause keywords in the broken one. That mirrors
the branch `_shared_origin_row` already has
([cases.py:758](../../../src/kubeagent_verdict/dataset/cases.py)), so
there is one rule, not two. Decided workloads are job 1 and are
unaffected.

This also settles a question no spec had answered. The rescope design
([2026-09-14-v1240-rescope-design.md:533](2026-09-14-v1240-rescope-design.md))
writes the job-2 rule only for a row "whose `expected_cause` is the
story's own cause". An override row's expected cause is the **shared
origin's** cause, so the rule never covered it. The rule is now: grade
an undecided shared-origin workload by the distinguishing keywords of
whatever string is its expected cause.

### 6. The prompts must not move

A test asserts that the regenerated exam has byte-identical `messages`
to the banked `out/dataset-0920/test.jsonl`, row for row. Only `meta`
changes.

This is the entire basis for re-scoring stored replies instead of paying
for another run. Without it we would be comparing two different exams
and calling it a correction.

### 7. Re-score, do not re-run

`out/eval-0920/results.jsonl` stores every reply verbatim. Re-score those
bytes against the fixed meta. No inference, no training host, no cost.

Publish with a `rescored_from` key naming the run the replies came from.
The precedent is the v0.1.0 GGUF replay
([model-card.md:313](../../model-card.md)).

## The pins that move

Four pinned numbers change. Each is re-written **by hand with a dated
comment**. No test is ever run with `-update`.

| pinned value | now | after | why |
|---|---|---|---|
| `keyword_graded_n` | 114 | 134 | the 20 gain keywords |
| `keyword_derivable_n` | 56 | 76 | all 20 have their answer printed in the menu |
| paste-the-prompt bot, job 2 | 0.366 | about 0.497 | same reason |
| the 0920 build, job 2 | 0.5817 | about 0.68 | the correction itself |

**No bar moves.** `JOB1_BAR`, `JOB2_BAR` and `JOB3_BAR` keep their values
([score.py:104](../../../src/kubeagent_verdict/evals/score.py),
[:139](../../../src/kubeagent_verdict/evals/score.py),
[:176](../../../src/kubeagent_verdict/evals/score.py)).

One guard is worth naming. `tests/test_score.py` asserts the
paste-the-prompt bot scores **below** `JOB2_BAR`. That bot rises from
0.366 to about 0.497, so the margin narrows from 0.334 to 0.203. It still
holds, but any future proposal to lower the bar now has a hard floor of
0.50, not 0.37 — below that, a bot that reads nothing passes the exam.

## What this costs

The fix makes the exam **easier for a bot that reads nothing**, from
0.366 to about 0.497. That is not a flaw in the fix. The 20 rows being
un-broken happen to have their answers printed in the candidate menu, so
grading them at all hands a copier half the exam.

The model's lead over that bot is about 22 points before the fix
(0.582 vs 0.366) and about 18 after (0.68 vs 0.497). The correction
flatters nobody — it narrows the model's lead slightly.

## What this does not fix

- **Job 2 still misses.** About 104 of 153 = 0.68 against a 0.70 bar.
  The bar needs 108, so it is about 4 workloads short.
- **Job 3 still misses.** 35 of 39 rows; the bar needs 36.
- **The real weakness is untouched.** The model scores 2 of 42 on
  workloads where it must override a wrong tag, against 90.8% and 94.7%
  on workloads where the tag is honest. That is one defect worth 42
  workloads, and no grader fix moves it.

## Out of scope

**Job 1's ceiling.** A perfect model scores 0.879 on job 1 against a 0.90
bar, because contradiction probes grade the echo while their gold answer
disagrees with it. That is the same class of defect and arguably worse.
The current build passes job 1 at 0.9554, so it blocks nothing today. It
gets its own spec.

**The training fix.** Separate spec, designed against the corrected
numbers this one produces.

## Testing

TDD throughout — failing test first, watch it fail, then implement.

1. The grader refuses a keyword-less named-cause job-2 workload, naming it.
2. `test_exam_oracle_job2` — a perfect model scores 1.000 on job 2. This
   is the test whose absence hid the bug; it goes in first.
3. Discrimination: each eval victim's keywords do not all appear in its
   twin's gold cause.
4. Prompt stability: regenerated `messages` are byte-identical to
   `out/dataset-0920/test.jsonl`, row for row.
5. Every eval scenario and victim carries a non-empty keyword pair.
6. The four re-pinned values, each with a dated comment.

## Success criteria

- A perfect model scores 1.000 on job 2.
- A keyword-less graded workload raises instead of scoring zero.
- Regenerated prompts are byte-identical to the banked exam.
- The 0920 run is re-scored from stored replies, with `rescored_from`
  recording where they came from.
- No bar has moved and no test was run with `-update`.
