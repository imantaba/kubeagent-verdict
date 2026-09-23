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

There is a second blind spot, and it is wider. The oracle answers from
the gold, never from the prompt. So it cannot see a question the prompt
does not contain enough information to answer. It would score such a row
perfectly and report a clean ceiling. This spec fixes the defect the
oracle *could* have caught. A separate one, named below, fixes a defect
it structurally cannot.

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

- **Job 2 still misses.** 104 of 153 = 0.680 against a 0.70 bar. The bar
  needs 108, so it is 4 workloads short.
- **Job 3 still misses.** 35 of 39 rows; the bar needs 36. All four
  misses are one shape: the model claims the workloads share an upstream
  cause on rows whose gold label says they do not. Two of the four have
  every per-workload verdict correct, and only the summary sentence wrong.
- **The real weakness is untouched, and it is not the one an earlier
  reading of this spec named.** That reading said the model scores 2 of
  42 where it must override a wrong tag. Measured per workload, the
  model does not take the wrong tag on this exam. It **abstains**: 38 of
  the 49 job-2 misses remaining after this fix answer `none_of_these`,
  every one of them carrying the gold rationale of the `none_of_these`
  case word for word.

  It abstains because on 19 of those rows it is not being asked an
  answerable question. Given one catalogue entry and one set of names,
  `none_of_these_case` (`cases.py:301`) and `wrong_attribution`
  (`cases.py:401`) build **byte-identical prompts for 27 of the 28
  catalogue entries**; the 28th differs only in the order of two lines of
  a menu whose every entry is refuted. Their gold answers are opposite —
  `none_of_these` against the workload's own cause. In the training set
  that pair is 1,315 of 6,377 rows, 20.6%, split 689 to 626. The model
  resolved the coin flip toward the more frequent label and applies it
  everywhere: `none_of_these` scores 18 of 19, `wrong_attribution` 0 of
  19. Eighteen of those 38 workloads is close to the most any model can
  score.

  `wrong_attribution`'s own docstring describes a different construction
  than its code performs — "the evidence is untouched and still supports
  the catalog winner, but the trace hands `attributed` to the decoy",
  where the code refutes every candidate. That is the promise rule: a
  comment promising what the code does not keep is a defect.

  The spillover is visible too. `misattribution_probe` is a genuinely
  distinct case — its candidates are ruled out, not refuted — and the
  model answers `none_of_these` on 17 of its 19 rows anyway. Having been
  taught that an exhausted menu means abstain, it over-applies the rule.

## Out of scope

**Job 1's ceiling.** A perfect model scores 0.879 on job 1 against a 0.90
bar, because contradiction probes grade the echo while their gold answer
disagrees with it. That is the same class of defect and arguably worse.
The current build passes job 1 at 0.9554, so it blocks nothing today. It
gets its own spec.

**The generator fix.** Separate spec. It is a removal, not an addition:
make `wrong_attribution` build the case its docstring describes, so its
prompts stop colliding with `none_of_these`. This is what "fix the
training data" now means — not more override examples, which is the one
intervention with a history of backfiring here. It changes the training
set and the exam together, so it needs a retrain and a fresh eval, and
every score it produces is a new baseline rather than a comparable one.
It must be specified from that docstring, which predates any score
pressure, and not tuned until the number clears. Same rule as section 4.

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
