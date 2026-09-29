# Grader Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make job 2's grader harder to fool and fairer to right answers.
A pasted line with its first words cut scores 0, a right answer that names
the registry host scores 1, and seven answer keys stop grading a wrong
cause right. No prompt and no gold answer moves.

**Architecture:** Five tasks, each one commit, in dependency order.

1. One cleaning step (NFKC) and one keyword rule, `_keywords_match`, with
   must-not words. The grader reads `own_cause_must_not` when a meta has
   it. No meta has it yet, so no exam score moves.
2. G3b also catches a line with its first 1 or 2 words cut, and G2 skips
   a decoy under 3 words. The two known-gap tests flip.
3. `decoy_rate` counts job-2 workloads only.
4. Must-not words on five answer keys, and `init` on two more. The
   workload meta goes from seven keys to eight, and the three test hashes
   move.
5. Build `out/dataset-0929`, gate it against `out/dataset-0928`, replay
   0920 under the new grader, and record both in the docs.

Tasks 1 to 3 touch only `score.py` and its tests. Task 4 touches only the
dataset code and its tests. Task 5 touches no code.

**Tech Stack:** Python 3, pytest, ruff. No cluster, no model call, no
training. No dependency moves.

**Spec:** [docs/superpowers/specs/2026-09-29-grader-guard-design.md](../specs/2026-09-29-grader-guard-design.md)
(approved, commit `883e663`). Read it before Task 1. This plan argues from
it and does not restate its reasoning.

## How the code in this plan was made

Tasks 1 to 4 each have two `diff` blocks: the tests first, then the
source. Task 5 has one `diff` block, the docs. They were cut from a
prototype branch built on `883e663`, one commit per task. For every task:

- the task's tests, applied alone on the commit before it, failed with
  exactly the list in Step 2;
- the full suite and ruff passed on the task's commit.

Task 5's build, gate and replay were also run on the prototype. The
hashes, the gate's output and the scoreboard in Task 5 are what those runs
printed.

So the diffs are exact. Apply them with `git apply`. Do not retype them.
Read every block before you apply it: you own the change, and the review
will ask you to explain it.

Every step that applies a diff shows the same extraction. It cuts diff
block `k` out of your brief file,
`.superpowers/sdd/2026-09-29-grader-guard/task-<N>-brief.md`. If that file
does not exist (you are working from the plan, not from a brief), the
first line of the step makes it from the plan.

Each task names the rulings that bind it. They live in the Rulings
section below, not in the brief, so the controller cuts them into a
second file and hands both over. List the numbers with spaces, with a
space at each end (Task 5: `" 12 13 14 15 16 17 "`):

```bash
cd /home/ubuntu/git/kubeagent-verdict && awk -v want=" 12 13 14 15 16 17 " '/^## /{r=($0=="## Rulings");k=0;next} r&&/^[0-9]+\. /{k=index(want," " ($1+0) " ")} r&&k' docs/superpowers/plans/2026-09-29-grader-guard.md > .superpowers/sdd/2026-09-29-grader-guard/task-5-rulings.md
```

## Global Constraints

- **Where:** the checkout at `/home/ubuntu/git/kubeagent-verdict`, branch
  `spec4a-grader`. Never commit to `main`. Start every command with
  `cd /home/ubuntu/git/kubeagent-verdict &&` (or run it from there).
- **Python:** `env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider …`.
  Unset `ALL_PROXY`/`all_proxy`: with a socks proxy set, some tests fail on
  import. `PYTHONPATH=src` makes the venv's editable install point at this
  checkout's `src/`.
- **ruff:** `.venv/bin/ruff check --ignore EXE002 .` must print
  `All checks passed!` on every commit.
- **git:** use `git -c core.fileMode=false` for `apply`, `add` and `commit`.
  Never `git add -A` or `git add .` — name each file. Never run
  `git config`. Never stage `.gitignore` or `train-v2.log`.
- **If `git apply --check` fails, STOP and report.** Do not hand-edit
  around it.
- **If a measured value differs from this plan, STOP and report.** Do not
  paste your value in. Every count, hash, failure list and scoreboard line
  below was observed on the prototype.
- **No bar moves.** `JOB1_BAR = 0.9`, `JOB2_BAR = 0.7`, `JOB3_BAR = 0.9`
  in `src/kubeagent_verdict/evals/score.py` keep their values.
- **Never run a test with `-update`.** Every pinned value in the diffs was
  written by hand with a dated comment,
  `# 2026-09-29 (Spec 4a): <why> <old> -> <new>`. A hash pin puts the old
  and new hashes on their own comment lines, `# <old> ->` then `# <new>`,
  because a hash does not fit on one line with the reason.
- **TDD.** Apply the tests, watch them fail with the listed failures, then
  apply the source. Task 5 is the one exception: it changes no code and no
  test, so it has no failing step. Its proof is the bank check, the gate
  and the scoreboard diff.
- **Commits:** each task's last step holds the exact command:
  `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F -`,
  with the message on standard input. No AI attribution of any kind: no
  `Co-Authored-By` trailer, no "generated with" line. No commit message
  names a plan task number.
- **Read-only elsewhere.** This plan never touches the kubeagent
  repository at `/home/ubuntu/git/kubeagent`. Nothing under an existing
  `out/` directory is touched. Task 5 creates `out/dataset-0929` and
  `out/eval/0920-exam0929-replay`, and nothing else under `out/`. No
  tracked file names the training host or any real identifier.
- **The exam.** "The exam" is `generate.test_set()`, which equals
  `out/dataset-0928/test.jsonl`: 249 rows, 177 job-2 workloads (169 graded
  by keyword, 8 `none_of_these`). The tests build it in-process. Only
  `tests/test_exam_prompt_stability.py` reads a file under `out/`.

## Rulings

Places where this plan departs from the spec's letter, or settles what the
spec left open. Each was measured on the prototype. Do not re-open them.
The task named in brackets is the one the ruling binds.

1. **[Task 1] `none_of_these` stays an exact match.** Its branch in `job2`
   still compares `cause.strip().lower()` with `none_of_these`: no NFKC,
   no period strip. So `none_of_these.` still scores 0 (spec, "What stays
   the same"). The test that pins this,
   `test_job2_none_of_these_is_still_an_exact_match`, passes before the
   source, because nothing on that branch changes. So Step 2 lists 6
   failures, not the 7 new tests. Cost if wrong: a reviewer reads the
   passing test as a missed failure.
2. **[Task 1] Keyword exposure gets no NFKC.** `_keyword_exposure` keeps
   its own lowercase match. Only its docstring changes, to say the grader
   applies NFKC and exposure does not. NFKC changes 0 of the 4,301
   exam texts the spec measured, so exposure stays 169 of 169. Cost if
   wrong: a prompt written in full-width letters would count as not
   exposed though the grader matches it; none exists today. The
   docstring names that case.
3. **[Task 1] An old meta still grades.** Both callers in `evaluate` pass
   `wm.get("own_cause_must_not") or []`. A meta with no such key (every
   bank built before Task 4, `out/dataset-0928` among them) grades with no
   must-not words. Task 2's guard changes still apply to it.
   `test_evaluate_grades_a_meta_with_no_must_not_key_and_reads_the_key_when_present`
   pins both halves. Cost if wrong: replaying an old bank would crash, or
   a new bank would skip its must-not words without a sound.
4. **[Task 2] The `none_of_these` guard test uses an own line now.**
   `test_job2_guards_a_none_of_these_workload_too` used a made-up 1-word
   decoy, `none_of_these`. G2 now skips it, so that assert moves 0.0 ->
   1.0 with a dated comment. The test now zeroes the reply with
   `none_of_these` as a made-up own line. G3b matches a whole own line
   of any length, so it still proves the guard runs before the exact
   match. Cost if wrong: none; the old assert
   stays, flipped and dated.
5. **[Task 2] One parametrized test for the three cut-paste bots.**
   `test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut` runs
   first word cut, first 2 words cut, and first 2 words swapped. Each
   scores 0 of 177 with the guard. Each case also asserts that the bot
   scores at least `JOB2_BAR` with the guard off (147, 147 and 153 of
   177). That proves the guard, not a weak bot, is what zeroes it. The
   old known-gap test is renamed into this one. Cost if wrong: a bot that
   never had the keywords would pass for the wrong reason.
6. **[Task 2] The hedge bot's new score is pinned, not hidden.** G2's
   3-word floor lets a hedge with the 2-word registry decoy through: 29
   bad-tag hedges now pass. The hedge bot goes from 32 of 177 = 0.1808 to
   61 of 177 = 0.3446, pinned with a dated comment and still asserted
   under `JOB2_BAR`. Cost if wrong: a hedge bot that learns the 2-word
   decoy gains points; the pin shows how many.
7. **[Task 3] The `shop/api` fixture moves from job 1 to job 2.**
   `test_decoy_by_workload_is_none_when_that_workload_is_never_answered`
   put its decoy on a job-1 workload. After Task 3 a job-1 decoy reads
   None for that reason alone, and the test would stop testing the
   unanswered path. So `shop/api` becomes job 2, and a new assert shows
   it is measured: a reply that names its decoy reads `True`. This test
   passes before the source, so it is not in Step 2's list. Cost if
   wrong: none; the fixture only chooses which path the test walks.
8. **[Task 3] The gold reply's `decoy_rate` is pinned.**
   `test_the_gold_reply_names_no_decoy_on_any_exam_row` pins
   `{"rate": 0.0, "n": 128}`. Before, 190 rows were measured and the gold
   reply read `True` on 10 (0.0526), all on the two shared-origin cases.
   The two shared-origin probe tests move too: "True on 5 of 10 -> 2 of
   10" for the always-claims twin, "True on 5 of 10 -> 0 of 10" for the
   reads-the-evidence twin, and `None` on the 3 rows where every workload
   is decided. Cost if wrong: none; these are measured values.
9. **[Task 4] The two `init` keys use the spec's word order.**
   `init-errimagepull` gets `("init", "registry", "tag")` and
   `init-imagepullbackoff` gets `("init", "tag", "registry")`. Order does
   not change a grade, but it is part of the meta, so it is part of the
   three hashes and of Task 5's gate. Cost if wrong: every hash in this
   plan misses.
10. **[Task 4] `test_exam_prompt_stability` stays on `out/dataset-0928`.**
    It compares `messages` only, and no message moves, so the old bank is
    still the right reference. It is the only test that reads `out/`. It
    skips when the file is missing. Cost if wrong: none; Task 5's gate
    also checks every message against 0928.
11. **[Task 4] The new tests read nothing under `out/`.** The weak-pair
    test builds the exam in-process with `generate.test_set()`. The pool
    tests build `generate(17, 8000)` in-process, once per module (about
    1.4 s). So Task 4's tests pass before Task 5 builds anything. Cost if
    wrong: none; the in-process exam is the same exam (see "The exam").
12. **[Task 5] The gate runs inline and is not committed.** It is a
    one-time check of one build against one other, so it lives in Step 3
    as a heredoc. Cost if wrong: a later spec that wants the same check
    copies it from this plan.
13. **[Task 5] Both docs get the bot table; the model card gets a new
    section.** `contract/PIN.md` and `docs/model-card.md` both list the
    bots before and after. The model card also gets "0920 re-scored under
    the 4a grader (2026-09-29)" with the replay numbers, and closes limits
    11 and 12 in dated notes. Cost if wrong: one table is in two places.
14. **[Task 5] Only the 2026-09-28 "Left for Spec 4" list is split.** It
    becomes "Done in 4a" and "Left for 4b" in a new PIN.md entry. The
    2026-09-26 list itself is not edited; the new 2026-09-29 entry says
    every item on it is still open. On the 2026-09-28 list, only the
    intro line changes, to point at the split. Cost if wrong: one list
    reads as older than it is.
15. **[Task 5] Two moved numbers are pinned by the scoreboard, not the
    docs.** Overconfident moves 0.3529 -> 0.3714 (12 of 34 -> 13 of 35)
    and `multi_misattribution_probe`'s cause moves 0.75 -> 0.7. Both come
    from the grader changes, and neither is in a doc. The scoreboard diff
    in Step 5 pins them. Cost if wrong: a reader of the docs alone does
    not see them.
16. **[Task 5] PIN.md's bank hashes are checked before the docs land.**
    Step 2 runs `sha256sum -c` on the three new files. The docs diff
    writes the same three hashes. Cost if wrong: none; a mismatch stops
    the task before any doc changes.
17. **[Task 5] The whole scoreboard and the manifest are pinned.** Step 5
    diffs the full `scoreboard.md` against the prototype's. Step 2 checks
    that `manifest.json` is byte-equal to 0928's with `cmp`. Cost if
    wrong: none; both are exact checks.

## The pins that move

The three test hashes. Only Task 4 moves them. Tasks 1, 2, 3 and 5 move
none.

| Pin | File | `883e663` | After Task 4 |
|---|---|---|---|
| `FROZEN_SLICE_SHA256` | `tests/test_shared_origin_training.py` | `48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69` | `f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a` |
| `EVAL_SET_SHA256` | `tests/test_shared_origin_training.py` | `b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653` | `a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2` |
| `GRADED_VIEW_SHA256` | `tests/test_exam_graded_view.py` | `396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108` | `efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4` |

The other dated pins, by task:

| Task | Test | Before -> after |
|---|---|---|
| 2 | `test_job2_guards_a_none_of_these_workload_too` | G2 skips a 1-word decoy: 0.0 -> 1.0 |
| 2 | `test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut` | G3b crops 1 or 2 front words: `{0.8305, 177}` -> `{0.0, 177}` |
| 2 | `test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2` | (bad-tag workloads, zeroed) (30, 29) -> (30, 0); gold with host `{0.8362, 177}` -> `{1.0, 177}` |
| 2 | `test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy` | `{0.1808, 177}` -> `{0.3446, 177}` (61 of 177) |
| 3 | `test_a_model_that_always_claims_a_shared_origin_fails_this_slice` | `named_decoy` True on 5 of 10 -> 2 of 10 |
| 3 | `test_a_model_that_reads_the_evidence_passes_this_slice` | `named_decoy` True on 5 of 10 -> 0 of 10 |
| 4 | `test_workload_meta_has_exactly_eight_keys` and the key-set asserts in `test_cases.py` and `test_propagation.py` | 7 keys -> 8 |

The diffs write these values. The tables are here so a reviewer can check
a pin without reading the tests.

## Full-suite counts

`out/dataset-0928` exists in this checkout, so the 2 prompt-stability
tests run on every commit. Without it they skip, and each count below
reads `2 skipped` with 2 fewer passed.

| After | Full suite |
|---|---|
| `883e663` (before Task 1) | 1517 passed |
| Task 1 | 1524 passed |
| Task 2 | 1529 passed |
| Task 3 | 1531 passed |
| Task 4 | 1547 passed |
| Task 5 | 1547 passed |

"6 warnings" also prints on every run. They are pre-existing.

## What comes after this plan

These are not tasks here. They follow the merge, in the spec's run order
("Run order"):

1. Merge and push.
2. Brainstorm Spec 4b: the shared-origin stories, facts in gold text the
   prompt does not show, and the fidelity items (spec, "Left for 4b").
3. After 4b lands: regenerate the bank, re-pin, and run 0920 live again.
4. Retrain once (about 32 hours, CPU recipe).
5. Run the untuned baseline once on the final exam.

## Review focus

A reviewer of any task here should check three things first:

- **The failing run.** Step 2's list is exact. A test that fails for a
  different reason, or passes before the source, is a defect in the task,
  even if the suite is green afterwards. Rulings 1 and 7 name the two
  new or changed tests that pass before their source, on purpose. Task 5
  has no failing run; its Steps 2, 3 and 5 check the bank and the replay
  instead.
- **Pins.** Every moved value carries
  `# 2026-09-29 (Spec 4a): <why> <old> -> <new>`, and its old and new
  values match the pins tables above. No test ran with `-update`. No bar
  moved.
- **The net.**
  `test_the_gold_answer_passes_the_grader_guard_on_every_exam_job2_workload`
  passes on every commit. If it ever fails, the change is wrong. Gold must
  stay 177 of 177.

Five inputs the spec implies and a person using the grader is most likely
to meet. Each has a test in the task that owns the code:

1. **A cause written in full-width letters.** Its decoy is still caught
   and its keywords still match. Task 1:
   `test_job2_guard_g2_finds_a_decoy_written_in_full_width_letters` and
   `test_job2_matches_keywords_written_in_full_width_letters`.
2. **A right answer that says "initial" or "initialize".** It must not
   trip the init-container must-not words. Task 4:
   `test_initial_and_initialize_do_not_trip_it`.
3. **A right answer that holds a 2-word piece of an own line.** G3b must
   not zero it: no cut leaves fewer than 3 words. Task 2:
   `test_job2_guard_g3b_crops_no_line_below_3_words`.
4. **A row whose only decoy sits on a job-1 workload.** `named_decoy` is
   None and the row stays out of `decoy_rate`. Task 3:
   `test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload`.
5. **An old bank whose meta has no `own_cause_must_not`.** It grades,
   with no must-not words. Task 1:
   `test_evaluate_grades_a_meta_with_no_must_not_key_and_reads_the_key_when_present`.

### Task 1: One cleaning step and one keyword rule

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `score.py` on `883e663`: `_norm_cause`, `job2`, `evaluate`,
  `_job2_guarded`, `_keyword_exposure`.
- Produces (module `kubeagent_verdict.evals.score`):
  - `_norm_cause(s: str) -> str` — NFKC, then lowercase, strip, trailing
    periods off, whitespace squeezed to one space.
  - `_keywords_match(cause: str, keywords: Iterable[str], must_not: Iterable[str] = ()) -> bool`
    — the cleaned cause holds every keyword and no must-not word, both
    lowercased, matched as substrings.
  - `job2(meta_workload, reply_row, own_cause_keywords, *, workload="", decoys=(), own_lines=(), own_cause_must_not: Iterable[str] = ()) -> float`
    — one new keyword argument.
  - `evaluate` passes `wm.get("own_cause_must_not") or []` to both
    `_keywords_match` (the `cause_acc` count) and `job2`.

**What this does.** Spec, Design parts 1 ("One cleaning step") and 6
("The keyword rule, written once"). `job2` and `evaluate`'s `cause_acc`
count used to each write the keyword rule. Both now call
`_keywords_match`. NFKC changes 0 of the 4,301 exam texts the spec measured, and no meta has
`own_cause_must_not` until Task 4, so no exam score moves.

**Rulings that bind this task:** 1, 2 and 3.

**Pins in this task.** None move.

**Watch for.**
- `_keywords_match` reads the raw cause and cleans it itself. The
  `none_of_these` branch in `job2` still uses `got_cause`, the old
  `.strip().lower()` form (ruling 1).
- The must-not list reaches `job2` as a keyword argument after `**guards[w]`.
  The guard dict holds only `decoys` and `own_lines`, so the names do not
  clash.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-1
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=1 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_score.py b/tests/test_score.py
index 2fd460b..8597c35 100644
--- a/tests/test_score.py
+++ b/tests/test_score.py
@@ -549,6 +549,85 @@ def test_job2_refuses_an_ungradable_workload_before_the_guard_runs():
         score.job2(wm, reply, [], workload="prod/api", decoys=["node worker-1 (NotReady)"])
 
 
+# --------------------------------------------------- job 2: one cleaning step, must-not words
+
+
+def test_norm_cause_folds_full_width_letters_first():
+    """NFKC runs before the lowercase, so full-width letters, a full-width
+    space and a full-width period fold to their plain forms."""
+    assert score._norm_cause("ＭＥＭＯＲＹ　Ｌｉｍｉｔ．") == "memory limit"
+
+
+def test_job2_guard_g2_finds_a_decoy_written_in_full_width_letters():
+    decoys = ["node worker-1 (NotReady)"]
+    assert score._job2_guarded("memory limit too low, or ｎｏｄｅ ｗｏｒｋｅｒ－１ （ＮｏｔＲｅａｄｙ）",
+                               decoys, ())
+
+
+def test_job2_matches_keywords_written_in_full_width_letters():
+    wm = {"job": 2, "decided": False, "expected_cause": "container killed at its memory limit"}
+    reply = {"cause": "the ＭＥＭＯＲＹ ＬＩＭＩＴ is too small", "confidence": "high", "rationale": "r"}
+    assert score.job2(wm, reply, ["memory", "limit"]) == 1.0
+
+
+def test_job2_none_of_these_is_still_an_exact_match():
+    """The cleaning step is for the keyword rule and the guard. The
+    `none_of_these` match stays `cause.strip().lower()`, exact."""
+    wm = {"job": 2, "decided": False, "expected_cause": score.NONE_OF_THESE}
+    assert score.job2(wm, {"cause": "  None_Of_These "}, []) == 1.0
+    assert score.job2(wm, {"cause": "none_of_these."}, []) == 0.0
+    assert score.job2(wm, {"cause": "ｎｏｎｅ＿ｏｆ＿ｔｈｅｓｅ"}, []) == 0.0
+
+
+def test_keywords_match_needs_every_keyword_and_no_must_not_word():
+    assert score._keywords_match("The Memory LIMIT.", ["memory", "limit"])
+    assert not score._keywords_match("the memory is low", ["memory", "limit"])
+    assert not score._keywords_match("the init container's memory limit is too small",
+                                     ["memory", "limit"], ["init container"])
+    # A must-not word is a substring rule, like a keyword. "initial" does
+    # not hold "init container".
+    assert score._keywords_match("the initial memory limit is too small",
+                                 ["memory", "limit"], ["init container"])
+
+
+# 0920's two wrong answers that the old key graded right: exam rows 197
+# and 198 (0-based), both `multi_misattribution_probe`, both on an
+# `oversized-job-unschedulable` workload.
+_OVERSIZED_KEYWORDS = ["memory", "node"]
+_OVERSIZED_GOLD = "the pod's memory request is larger than any node can allocate"
+_0920_ROW_197 = ("the pod's node has a MemoryPressure condition and the pod requests a "
+                 "32Mi resolution")
+_0920_ROW_198 = ("the pod's node is cordoned and reporting Insufficient memory as a charge "
+                 "against its own memory limit")
+
+
+def test_job2_zeroes_a_cause_that_holds_a_must_not_word():
+    wm = {"job": 2, "decided": False, "expected_cause": _OVERSIZED_GOLD}
+    must_not = ["cordon", "pressure"]
+    for cause in (_0920_ROW_197, _0920_ROW_198):
+        reply = {"cause": cause, "confidence": "high", "rationale": "r"}
+        assert score.job2(wm, reply, _OVERSIZED_KEYWORDS) == 1.0
+        assert score.job2(wm, reply, _OVERSIZED_KEYWORDS, own_cause_must_not=must_not) == 0.0
+    gold = {"cause": _OVERSIZED_GOLD, "confidence": "high", "rationale": "r"}
+    assert score.job2(wm, gold, _OVERSIZED_KEYWORDS, own_cause_must_not=must_not) == 1.0
+
+
+def test_evaluate_grades_a_meta_with_no_must_not_key_and_reads_the_key_when_present():
+    """An exam file built before the must-not words has no
+    `own_cause_must_not` in its meta. It still grades: the list is empty.
+    When the key is there, both cause graders read it."""
+    row = _row_with_job2_workload(["memory", "limit"])
+    assert "own_cause_must_not" not in row["meta"]["workloads"]["shop/api"]
+    init_answer = _one_verdict("shop/api", "the init container's memory limit is too small")
+
+    [res] = score.evaluate([row], lambda _messages: init_answer)
+    assert (res["cause_acc"], res["job2_scores"]) == (1.0, [1.0])
+
+    row["meta"]["workloads"]["shop/api"]["own_cause_must_not"] = ["init container"]
+    [res] = score.evaluate([row], lambda _messages: init_answer)
+    assert (res["cause_acc"], res["job2_scores"]) == (0.0, [0.0])
+
+
 # --------------------------------------------------- job 3: the summary scorer
 
 
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_score.py
```

Expected: the summary line reads `6 failed, 187 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_score.py::test_norm_cause_folds_full_width_letters_first
FAILED tests/test_score.py::test_job2_guard_g2_finds_a_decoy_written_in_full_width_letters
FAILED tests/test_score.py::test_job2_matches_keywords_written_in_full_width_letters
FAILED tests/test_score.py::test_keywords_match_needs_every_keyword_and_no_must_not_word
FAILED tests/test_score.py::test_job2_zeroes_a_cause_that_holds_a_must_not_word
FAILED tests/test_score.py::test_evaluate_grades_a_meta_with_no_must_not_key_and_reads_the_key_when_present
```

The seventh new test, `test_job2_none_of_these_is_still_an_exact_match`,
passes here and is not in the list (ruling 1).

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-1
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=1 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/evals/score.py b/src/kubeagent_verdict/evals/score.py
index fc67a28..7eba62e 100644
--- a/src/kubeagent_verdict/evals/score.py
+++ b/src/kubeagent_verdict/evals/score.py
@@ -9,6 +9,7 @@ from __future__ import annotations
 
 import json
 import re
+import unicodedata
 from collections.abc import Iterable
 
 from kubeagent_verdict.contract import NONE_OF_THESE, TRUNCATION_MARKER
@@ -332,14 +333,26 @@ def _job2_guarded(cause: str, decoys: Iterable[str], own_lines: Iterable[str]) -
     return any(line and line in c for line in own_lines)
 
 
+def _keywords_match(cause: str, keywords: Iterable[str],
+                    must_not: Iterable[str] = ()) -> bool:
+    """The keyword rule, written once for `job2` and `cause_acc`: the cause,
+    cleaned by `_norm_cause`, holds every keyword and no must-not word. Both
+    lists are lowercased and matched as substrings."""
+    c = _norm_cause(cause)
+    return (all(str(k).lower() in c for k in keywords)
+            and not any(str(m).lower() in c for m in must_not))
+
+
 def job2(meta_workload: dict, reply_row: dict | None,
          own_cause_keywords: list[str], *, workload: str = "",
-         decoys: Iterable[str] = (), own_lines: Iterable[str] = ()) -> float:
+         decoys: Iterable[str] = (), own_lines: Iterable[str] = (),
+         own_cause_must_not: Iterable[str] = ()) -> float:
     """Score one undecided ("job 2") workload. 1.0 when the reply names the
-    story's own cause -- all of `own_cause_keywords` appear in the reply's
-    cause, matched as substrings after lowercasing both sides -- or, on a
-    `none_of_these` workload, when the reply's cause is exactly that. 0.0
-    otherwise, including a missing row or reply.
+    story's own cause -- the reply's cause, cleaned by `_norm_cause`, holds
+    every one of `own_cause_keywords` and none of `own_cause_must_not`, both
+    matched as lowercase substrings -- or, on a `none_of_these` workload,
+    when the reply's cause is exactly that. 0.0 otherwise, including a
+    missing row or reply.
 
     The grader guard runs first and scores 0.0 when the cause holds one of
     `decoys` (G2) or one of `own_lines` (G3b). It runs before the keyword
@@ -361,7 +374,8 @@ def job2(meta_workload: dict, reply_row: dict | None,
         return 1.0 if got_cause == NONE_OF_THESE else 0.0
     if not _is_job2_keyword_graded(meta_workload, own_cause_keywords):
         return 0.0
-    return 1.0 if all(str(k).lower() in got_cause for k in own_cause_keywords) else 0.0
+    return 1.0 if _keywords_match(str(reply_row.get("cause", "")), own_cause_keywords,
+                                  own_cause_must_not) else 0.0
 
 
 JOB3_BAR = 0.9
@@ -557,7 +571,11 @@ def _suggestion_strings(prompt: str) -> set[str]:
 
 
 def _norm_cause(s: str) -> str:
-    return " ".join(str(s).lower().strip().rstrip(".").split())
+    """One cleaning step for every cause the grader reads: NFKC first, so a
+    full-width letter, space or period folds to its plain form, then
+    lowercase, strip, trailing periods off, and runs of whitespace
+    squeezed to one space."""
+    return " ".join(unicodedata.normalize("NFKC", str(s)).lower().strip().rstrip(".").split())
 
 
 # Job 2 grades most of its workloads by keyword containment rather than exact
@@ -601,7 +619,8 @@ def _keyword_exposure(meta: dict, prompt: str) -> tuple[int, int]:
     so the two cannot drift into measuring different populations. The matching
     is the grader's own normalisation: lowercase substring containment, `all`
     and not `any`. Anything looser would report an exposure the grader would
-    not accept.
+    not accept. The grader also applies NFKC (`_norm_cause`) and exposure does
+    not; NFKC changes 0 of the exam's prompt texts, so the counts are the same.
 
     A workload that is not keyword-graded is absent from both counts, never a
     zero in the denominator -- the same contract `_rate` states.
@@ -697,8 +716,8 @@ def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict
             if guard is not None and _job2_guarded(str(got.get("cause", "")), **guard):
                 matched = False
             elif wm.get("job") == 2 and _is_job2_keyword_graded(wm, keywords):
-                matched = all(str(k).lower() in str(got.get("cause", "")).lower()
-                              for k in keywords)
+                matched = _keywords_match(str(got.get("cause", "")), keywords,
+                                          wm.get("own_cause_must_not") or [])
             else:
                 matched = got.get("cause") == exp["cause"]
             if matched:
@@ -791,7 +810,8 @@ def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict
         job1_scores = [job1(wm, by_workload.get(w))
                        for w, wm in workloads.items() if wm.get("job") == 1]
         job2_scores = ([job2(wm, by_workload.get(w), wm.get("own_cause_keywords") or [],
-                             workload=w, **guards[w])
+                             workload=w, **guards[w],
+                             own_cause_must_not=wm.get("own_cause_must_not") or [])
                         for w, wm in workloads.items() if wm.get("job") == 2]
                        if grade_job2 else [])
         row_job3 = (job3(meta.get("label", ""), (doc or {}).get("summary"))
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `1524 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_score.py src/kubeagent_verdict/evals/score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(score): one cleaning step and one keyword rule for job 2

Every job-2 text match now goes through _norm_cause, and _norm_cause
applies Unicode NFKC first. A decoy or a keyword written in full-width
letters now matches. NFKC changes none of the exam's texts, so no exam
score moves.

The keyword rule was written twice, in job2 and in evaluate's cause
count. Both now call _keywords_match. It also takes must-not words: an
answer that holds every keyword and any must-not word scores 0. The
grader reads them from a workload's own_cause_must_not. No meta has
that key yet, and a meta without it grades as before.

none_of_these is still an exact match, and keyword exposure still
counts required words only. It stays 169 of 169.
EOF
```

Then `git status --short` must list nothing from this task: every file above is committed. `.gitignore` and `train-v2.log` may show; leave them.

### Task 2: Catch a pasted line with its first words cut, and skip short decoys

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: Task 1's `_norm_cause` (with NFKC). `_own_blocks` already
  returns cleaned own lines.
- Produces (module `kubeagent_verdict.evals.score`):
  - `_g3b(c: str, own_lines: Iterable[str]) -> bool` — whether the cleaned
    cause `c` holds an own line, whole or with its first 1 or 2 words
    cut. A cut is made only when at least 3 words are left.
  - `_job2_guarded(cause, decoys, own_lines) -> bool` — same signature.
    G2 now skips a cleaned decoy under 3 words, and G3b is `_g3b`.

**What this does.** Spec, Design parts 2 ("G3b: a line with its first
words cut") and 3 ("G2: skip a decoy under 3 words").
The trimmed-paste bot and its two new siblings score 0 of 177. The gold
reply that names the registry host scores 177 of 177. The guard comment
block and both docstrings say why both limits are 3 words.

**Rulings that bind this task:** 4, 5 and 6.

**Pins in this task.** The four dated pins in the table "The other dated
pins, by task" marked Task 2. No hash moves.

**Watch for.**
- `_g3b` stops at `break`, not `continue`: once a cut leaves fewer than 3
  words, a bigger cut would leave fewer still.
- G2's floor counts the words of the cleaned decoy, after `_norm_cause`.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-2
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=2 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_score.py b/tests/test_score.py
index 8597c35..3f222b3 100644
--- a/tests/test_score.py
+++ b/tests/test_score.py
@@ -501,6 +501,43 @@ def test_job2_guard_does_not_fire_on_part_of_a_line():
     assert not score._job2_guarded("node worker-1 (NotReady)", (), own)
 
 
+def test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut():
+    """G3b also zeroes a cause that holds an own line minus its first word,
+    or minus its first 2 words. A 3-word cut is not made: the cause below
+    that holds the line minus its first 3 words passes."""
+    own = _normalized(_GUARD_API_INVENTORY)
+    words = score._norm_cause(_GUARD_API_INVENTORY[1]).split()
+    assert score._job2_guarded("memory limit: " + " ".join(words[1:]), (), own)
+    assert score._job2_guarded("memory limit: " + " ".join(words[2:]), (), own)
+    assert not score._job2_guarded("memory limit: " + " ".join(words[3:]), (), own)
+
+
+def test_job2_guard_g3b_crops_no_line_below_3_words():
+    """The 3-word floor. A cut that would leave fewer than 3 words is not
+    made. `exit: memory limit` is 3 words, so it is matched whole and never
+    cropped, and a right answer that holds `memory limit` is not zeroed.
+    `no events for web/api-gw-5c6b-fghij` is 4 words, so it loses its first
+    word and never its first 2."""
+    own = _normalized(["    exit: memory limit", "no events for web/api-gw-5c6b-fghij"])
+    assert not score._job2_guarded("the container's memory limit is too small", (), own)
+    assert score._job2_guarded("exit: memory limit", (), own)
+    assert score._job2_guarded("see events for web/api-gw-5c6b-fghij", (), own)
+    assert not score._job2_guarded("see for web/api-gw-5c6b-fghij", (), own)
+
+
+def test_job2_guard_g2_skips_a_decoy_under_3_words():
+    """G2 skips a decoy shorter than 3 words after cleaning. On the exam the
+    only one is `registry registry.example.com`. So a right bad-tag answer
+    that names the host passes, and so does a hedge with that decoy: that
+    is the cost, pinned by the hedge bot. A 3-word decoy still zeroes a
+    hedge."""
+    short, long_ = ["registry registry.example.com"], ["node worker-1 (NotReady)"]
+    gold = "the image tag does not exist in the registry"
+    assert not score._job2_guarded(gold + " registry.example.com", short, ())
+    assert not score._job2_guarded(gold + " or registry registry.example.com", short, ())
+    assert score._job2_guarded(gold + " or node worker-1 (NotReady)", long_, ())
+
+
 def test_job2_guard_skips_an_empty_decoy_or_line():
     """An empty string sits inside every cause. Skipping it keeps one blank
     decoy from zeroing every reply."""
@@ -527,12 +564,19 @@ def test_job2_zeroes_a_guarded_reply_even_when_every_keyword_is_present():
 
 def test_job2_guards_a_none_of_these_workload_too():
     """The guard runs before the exact `none_of_these` match as well. The
-    decoy here is made up: it is the one way to show that order, since any
-    other guarded reply would miss the exact match anyway."""
+    own line here is made up: it is the one way to show that order, since
+    any other guarded reply would miss the exact match anyway.
+
+    2026-09-29 (Spec 4a): this test used a made-up decoy, `none_of_these`.
+    That decoy is 1 word, and G2 now skips a decoy under 3 words, so the
+    reply passes it. G3b matches a whole own line of any length, so a
+    made-up own line shows the order instead."""
     wm = {"job": 2, "decided": False, "expected_cause": score.NONE_OF_THESE}
     reply = {"cause": score.NONE_OF_THESE, "confidence": "medium", "rationale": "r"}
     assert score.job2(wm, reply, []) == 1.0
-    assert score.job2(wm, reply, [], decoys=[score.NONE_OF_THESE]) == 0.0
+    assert score.job2(wm, reply, [], own_lines={score.NONE_OF_THESE}) == 0.0
+    # 2026-09-29 (Spec 4a): G2 skips a 1-word decoy 0.0 -> 1.0
+    assert score.job2(wm, reply, [], decoys=[score.NONE_OF_THESE]) == 1.0
 
 
 def test_job2_missing_reply_still_scores_zero_with_the_guard_on():
@@ -2674,8 +2718,12 @@ def test_the_grader_guard_zeroes_a_bot_that_pastes_the_prompt():
     alone keeps any bot that reads nothing under the bar. That was too
     strong. It holds a verbatim paste to 0, but a near-copy is a known gap:
     the same own lines with the first word of each line cut score 147 of
-    177 = 0.8305 with the guard on, over JOB2_BAR. See
-    `test_a_trimmed_paste_clears_the_job2_bar_a_known_gap_in_the_guard`.
+    177 = 0.8305 with the guard on, over JOB2_BAR.
+
+    2026-09-29 (Spec 4a): that gap is closed. G3b also matches a line with
+    its first 1 or 2 words cut, and the near-copy scores 0 of 177. See
+    `test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut`. A
+    single clause lifted out of the middle of a line still passes.
 
     2026-09-26 (faithful prompts), when the job-1 rows moved onto the
     evidence gather: 31 exam rows whose entry has no job-1 rule ask become
@@ -2867,11 +2915,23 @@ def _own_reads(prompt: str, name: str, names: list[str]) -> list[str]:
     return reads
 
 
-def _trimmed_paste_bot(rows: list[dict]):
+def _first_word_cut(words: list[str]) -> list[str]:
+    return words[1:]
+
+
+def _first_2_words_cut(words: list[str]) -> list[str]:
+    return words[2:]
+
+
+def _first_2_words_swapped(words: list[str]) -> list[str]:
+    return words[1:2] + words[:1] + words[2:]
+
+
+def _trimmed_paste_bot(rows: list[dict], trim=_first_word_cut):
     """Answers every flagged workload with its own inventory entry and its
-    own evidence reads, with the first word of each line cut off, joined by
-    newlines. It is the paste bot cut down to one workload, and cut just
-    enough that no whole line is left. It reads nothing."""
+    own evidence reads, each line changed by `trim`, joined by newlines. It
+    is the paste bot cut down to one workload, and changed just enough that
+    no whole line is left. It reads nothing."""
     by_prompt = {r["messages"][1]["content"]: r for r in rows}
 
     def chat_fn(messages: list[dict]) -> str:
@@ -2881,7 +2941,7 @@ def _trimmed_paste_bot(rows: list[dict]):
         for name in names:
             lines = _own_entry(prompt, "inventory", name) + _own_reads(prompt, name, names)
             verdicts.append({"workload": name,
-                             "cause": "\n".join(" ".join(line.split()[1:]) for line in lines),
+                             "cause": "\n".join(" ".join(trim(line.split())) for line in lines),
                              "confidence": "medium",
                              "rationale": "restating this workload's own lines, trimmed"})
         return json.dumps({"verdicts": verdicts,
@@ -2890,69 +2950,60 @@ def _trimmed_paste_bot(rows: list[dict]):
     return chat_fn
 
 
-def test_a_trimmed_paste_clears_the_job2_bar_a_known_gap_in_the_guard():
-    """This is a known gap. A bot that reads nothing clears JOB2_BAR by
-    copying its own lines with one word cut from each.
-
-    The bot takes each workload's own inventory entry and its own evidence
-    reads, and drops the first word of every line. G3b zeroes a cause only
-    when it holds a whole line of the workload's own block, so it never
-    fires: no whole line is left. The keywords are still there, so job 2
-    marks the cause right. The guard takes nothing away from this bot. It
-    scores 147 of 177 with the guard and 147 of 177 without it, 0.8305,
-    above JOB2_BAR (0.7). A verbatim paste of the same lines scores 0 (see
-    the paste and echo tests above), so the guard holds a verbatim copy
-    down, and not a near-copy.
-
-    Closing the gap needs a stronger G3b, such as matching part of a line.
-    That changes what the grader promises, so it is a spec amendment, and
-    Spec 4 owns it. Until then, a job-2 rate near 0.83 does not show on its
-    own that a model reads the evidence.
-
-    Measured 2026-09-28 (final review). If a change moves this number, the
-    gap moved. Re-pin it and say why; if G3b got stronger, this test's
-    last bar check is the one to flip.
+@pytest.mark.parametrize(("trim", "unguarded_wins"), [
+    (_first_word_cut, 147),
+    (_first_2_words_cut, 147),
+    (_first_2_words_swapped, 153),
+])
+def test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut(trim, unguarded_wins):
+    """A bot that reads nothing copies its own lines with the front of each
+    line changed: the first word cut, the first 2 words cut, or the first 2
+    words swapped. No whole line is left, but the keywords are, so with no
+    guard the bot clears JOB2_BAR: 147, 147 and 153 of 177.
+
+    G3b also matches a line with its first 1 or 2 words cut, as long as 3
+    words are left. Each of these causes holds such a piece of some line,
+    so the guard zeroes all of them: 0 of 177.
+
+    2026-09-29 (Spec 4a): renamed from
+    `test_a_trimmed_paste_clears_the_job2_bar_a_known_gap_in_the_guard`,
+    which pinned the first-word bot at 147 of 177 = 0.8305 guarded, over
+    the bar. The 2-word bots are new. The unguarded numbers measure the
+    corpus, not the guard, and do not move.
     """
     rows = _corpus_rows()
-    bot = _trimmed_paste_bot(rows)
+    bot = _trimmed_paste_bot(rows, trim)
     board = score.scoreboard(score.evaluate(rows, bot))
     unguarded = _unguarded_job2_scores(rows, bot)
 
-    # The guarded pair: 147 of 177 with the guard on.
-    assert board["jobs"]["job2"] == {"rate": 0.8305, "n": 177}
-    assert round(board["jobs"]["job2"]["rate"] * board["jobs"]["job2"]["n"]) == 147
-    # The unguarded pair: the same 147 of 177. The guard zeroes none of them.
-    assert (sum(unguarded), len(unguarded)) == (147, 177)
-    assert round(sum(unguarded) / len(unguarded), 4) == 0.8305
-    # The gap itself: this bot is over the bar.
-    assert board["jobs"]["job2"]["rate"] >= score.JOB2_BAR
+    # 2026-09-29 (Spec 4a): G3b crops 1 or 2 front words {0.8305, 177} -> {0.0, 177}
+    assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}
+    assert (sum(unguarded), len(unguarded)) == (unguarded_wins, 177)
+    assert sum(unguarded) / len(unguarded) >= score.JOB2_BAR
 
 
 _BAD_TAG_GOLD = "the image tag does not exist in the registry"
 
 
-def test_a_right_bad_tag_answer_that_names_the_registry_host_is_zeroed_by_g2():
-    """This is a known gap. A right answer can lose job 2 for naming the
-    registry host.
+def test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2():
+    """A right answer does not lose job 2 for naming the registry host.
 
     The bad-image-tag rows print the candidate `registry
     registry.example.com` and rule it out, so it is the workload's decoy.
-    G2 zeroes any cause that contains a decoy. The gold cause is "the image
-    tag does not exist in the registry", and it passes. Add the host, "...
-    in the registry registry.example.com", and the words "registry
-    registry.example.com" now sit inside the answer, so G2 zeroes it,
-    although it is right.
-
-    Plan ruling 37 accepted this decoy, because the gold answer does not
-    contain it and the gold net test stays green. That is still true. The
-    cost is the one below, and a narrower G2 is a spec amendment that
-    Spec 4 owns.
-
-    Measured 2026-09-28 (final review) on the exam: 30 of the 177 job-2
-    workloads have the gold bad-tag cause. 29 of them carry the decoy and
-    lose the point. The one left, on an `empty_candidates` row, has no
-    decoy. The gold reply with the host added scores 148 of 177 = 0.8362,
-    where the gold reply scores 177 of 177.
+    The gold cause is "the image tag does not exist in the registry". Add
+    the host, "... in the registry registry.example.com", and the decoy
+    sits inside the answer. G2 skips a decoy under 3 words, and this decoy
+    is 2, so the answer passes.
+
+    On the exam, 30 of the 177 job-2 workloads have the gold bad-tag cause.
+    29 of them carry the decoy. The one left, on an `empty_candidates` row,
+    has none. The gold reply with the host added scores 177 of 177, the
+    same as the gold reply.
+
+    2026-09-29 (Spec 4a): renamed from
+    `test_a_right_bad_tag_answer_that_names_the_registry_host_is_zeroed_by_g2`.
+    Measured 2026-09-28, G2 zeroed 29 of the 30 and the reply scored 148 of
+    177 = 0.8362.
     """
     rows = _corpus_rows()
     by_prompt = {r["messages"][1]["content"]: r for r in rows}
@@ -2979,10 +3030,11 @@ def test_a_right_bad_tag_answer_that_names_the_registry_host_is_zeroed_by_g2():
                 zeroed += score._job2_guarded(_BAD_TAG_GOLD + " registry.example.com",
                                               decoys, own[name])
 
-    assert (bad_tag, zeroed) == (30, 29)
+    # 2026-09-29 (Spec 4a): G2 skips the 2-word registry decoy (30, 29) -> (30, 0)
+    assert (bad_tag, zeroed) == (30, 0)
     board = score.scoreboard(score.evaluate(rows, chat_fn))
-    assert board["jobs"]["job2"] == {"rate": 0.8362, "n": 177}
-    assert round(board["jobs"]["job2"]["rate"] * board["jobs"]["job2"]["n"]) == 177 - 29
+    # 2026-09-29 (Spec 4a): same reason {0.8362, 177} -> {1.0, 177}
+    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 177}
 
 
 def _name_the_decoy_bot(rows: list[dict]):
@@ -3101,6 +3153,12 @@ def test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy():
     workloads net. The workloads with no own decoy are still 32. Job 2
     counts 177. Unguarded the hedge wins all 169 keyword-graded workloads, 0.9548;
     the other 8 expect `none_of_these`. Guarded it is 32 of 177 = 0.1808.
+
+    2026-09-29 (Spec 4a): G2 skips a decoy under 3 words. 29 bad-tag
+    workloads' first own decoy is the 2-word `registry
+    registry.example.com`, so their hedge passes now. Guarded it is 32 + 29
+    = 61 of 177 = 0.3446. That is the measured cost of letting a right
+    answer name the registry host, and it stays under JOB2_BAR.
     """
     rows = _corpus_rows()
     bot = _hedge_bot(rows)
@@ -3117,7 +3175,10 @@ def test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy():
     # 2026-09-26 (faithful prompts): five workers; two job-2 workloads leave
     # net and the 32 with no own decoy stay {0.1788, 179} -> {0.1808, 177}
     # (32 of 177)
-    assert board["jobs"]["job2"] == {"rate": 0.1808, "n": 177}
+    # 2026-09-29 (Spec 4a): G2 skips the 2-word registry decoy, 29 hedges pass
+    # {0.1808, 177} -> {0.3446, 177} (61 of 177)
+    assert board["jobs"]["job2"] == {"rate": 0.3446, "n": 177}
+    assert board["jobs"]["job2"]["rate"] < score.JOB2_BAR
     # 2026-09-26 (faithful prompts): same workload (134, 142) -> (134, 143),
     # 0.9437 -> 0.9371
     # 2026-09-26 (faithful prompts): 37 new keyword-graded workloads, all won
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_score.py
```

Expected: the summary line reads `9 failed, 189 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_score.py::test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut
FAILED tests/test_score.py::test_job2_guard_g3b_crops_no_line_below_3_words
FAILED tests/test_score.py::test_job2_guard_g2_skips_a_decoy_under_3_words
FAILED tests/test_score.py::test_job2_guards_a_none_of_these_workload_too
FAILED tests/test_score.py::test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut[_first_word_cut-147]
FAILED tests/test_score.py::test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut[_first_2_words_cut-147]
FAILED tests/test_score.py::test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut[_first_2_words_swapped-153]
FAILED tests/test_score.py::test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2
FAILED tests/test_score.py::test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-2
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=2 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/evals/score.py b/src/kubeagent_verdict/evals/score.py
index 7eba62e..b216c71 100644
--- a/src/kubeagent_verdict/evals/score.py
+++ b/src/kubeagent_verdict/evals/score.py
@@ -196,8 +196,16 @@ def _is_job2_keyword_graded(meta_workload: dict,
 # The grader guard. Job 2 marks a cause right when every keyword is in it, so
 # a reply can collect the keywords without judging anything: paste the lines
 # the prompt printed about the workload, or name the real cause next to a
-# decoy. Two checks zero such a reply. G2: the cause holds a decoy. G3b: the
-# cause holds a full printed line of the workload's own block.
+# decoy. Two checks zero such a reply. G2: the cause holds a decoy of 3 words
+# or more. G3b: the cause holds a printed line of the workload's own block,
+# whole or with its first 1 or 2 words cut, as long as 3 words are left.
+#
+# Both limits are 3 words (2026-09-29, Spec 4a). A shorter piece sits inside
+# right answers: the 2-word decoy `registry registry.example.com` is inside a
+# right bad-tag answer that names the host, and with no floor on the crop the
+# gold reply loses a workload. A 3-word cut zeroes 6 gold answers. A single
+# clause lifted out of the middle of a line still passes, and must: 17 gold
+# sentences are printed in their own prompts.
 #
 # Both read the RAW cause, normalized by `_norm_cause` and nothing else. No
 # 512-rune cap and no `_clean_rationale`: a capped cause cuts off the lines
@@ -322,15 +330,34 @@ def _workload_decoys(meta: dict, workload: str) -> list[str]:
 def _job2_guarded(cause: str, decoys: Iterable[str], own_lines: Iterable[str]) -> bool:
     """Whether the grader guard zeroes this job-2 cause.
 
-    G2: the normalized cause holds a normalized decoy. G3b: it holds one of
-    `own_lines`, which are already normalized (what `_own_blocks` returns).
-    An empty decoy or line is skipped: an empty string sits inside every
-    cause.
+    G2: the normalized cause holds a normalized decoy of 3 words or more. A
+    shorter decoy is skipped. G3b: it holds one of `own_lines`, which are
+    already normalized (what `_own_blocks` returns), whole or with its first
+    1 or 2 words cut (see `_g3b`). An empty decoy or line is skipped: an
+    empty string sits inside every cause.
     """
     c = _norm_cause(cause)
-    if any(n and n in c for n in (_norm_cause(d) for d in decoys if d)):
+    if any(len(n.split()) >= 3 and n in c for n in (_norm_cause(d) for d in decoys if d)):
         return True
-    return any(line and line in c for line in own_lines)
+    return _g3b(c, own_lines)
+
+
+def _g3b(c: str, own_lines: Iterable[str]) -> bool:
+    """Whether the cleaned cause `c` holds one of `own_lines`, whole or with
+    its first 1 or 2 words cut. A cut is made only when at least 3 words are
+    left, so a 3-word line is matched whole only."""
+    for line in own_lines:
+        if not line:
+            continue
+        if line in c:
+            return True
+        words = line.split()
+        for cut in (1, 2):
+            if len(words) - cut < 3:
+                break
+            if " ".join(words[cut:]) in c:
+                return True
+    return False
 
 
 def _keywords_match(cause: str, keywords: Iterable[str],
@@ -355,7 +382,7 @@ def job2(meta_workload: dict, reply_row: dict | None,
     missing row or reply.
 
     The grader guard runs first and scores 0.0 when the cause holds one of
-    `decoys` (G2) or one of `own_lines` (G3b). It runs before the keyword
+    `decoys` (G2) or one of `own_lines`, whole or cut (G3b). It runs before the keyword
     rule because a pasted block or a hedge carries the keywords too, and
     the keyword rule alone would mark it right. With no `decoys` and no
     `own_lines`, nothing is guarded: that is the unguarded score.
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `1529 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_score.py src/kubeagent_verdict/evals/score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(score): catch a pasted line with its first words cut

G3b zeroed an answer that held a whole line of the workload's own
block. Cutting one word off the front of each line got past it: that
bot scored 147 of 177 on job 2, over the 0.7 bar. G3b now also matches
a line with its first 1 or 2 words cut, as long as 3 words are left.
The three cut-paste bots (first word cut, first 2 cut, first 2 swapped)
now score 0 of 177.

G2 now skips a decoy under 3 words. The only one on the exam is
"registry registry.example.com", and it sits inside a right bad-tag
answer that names the host. The gold reply with the host goes from 148
to 177 of 177.

Both limits are 3 words. A shorter piece sits inside right answers,
and a 3-word cut zeroes 6 gold answers. The cost is pinned: the hedge
bot goes from 32 to 61 of 177, still under the bar.
EOF
```

Then `git status --short` must list nothing from this task: every file above is committed. `.gitignore` and `train-v2.log` may show; leave them.

### Task 3: Count decoys on job-2 workloads only

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py`
- Test: `tests/test_score.py`, `tests/test_shared_origin_decoy_probe.py`

**Interfaces:**
- Consumes: `evaluate`'s decoy loop as Task 2 left it.
- Produces: `evaluate`'s per-row `named_decoy` tests job-2 workloads only.
  A row with no job-2 workload that carries a decoy gets `None`, the same
  as a row with no decoy at all, so it stays out of `decoy_rate`. No
  signature changes.

**What this does.** Spec, Design part 4 ("`decoy_rate` counts job-2
workloads only"). On a `shared_origin_probe` row,
`decoy_by_workload` lists a decided workload's own decided cause, which
is its job-1 gold, so the right answer read as naming a decoy. The loop
now skips any workload whose `job` is not 2. The gold reply's
`decoy_rate` goes from 10 of 190 to 0 of 128.

**Rulings that bind this task:** 7 and 8.

**Pins in this task.** The two dated pins marked Task 3 in the table
above, and the gold reply's `{0.0, 128}`. No hash moves.

**Watch for.**
- The job test reads `meta["workloads"][workload]["job"]` through
  `.get(...) or {}` at each level, so a workload that `decoy_by_workload`
  names but `workloads` does not is skipped too, not a `KeyError`.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-3
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=3 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_score.py b/tests/test_score.py
index 3f222b3..fd90fde 100644
--- a/tests/test_score.py
+++ b/tests/test_score.py
@@ -1346,7 +1346,12 @@ def test_decoy_by_workload_is_none_when_that_workload_is_never_answered():
     decoy sits on ONE workload must not read as "resisted" just because a
     DIFFERENT workload in the same row was answered. Before decoy_by_workload,
     the row-level `answered` gate saw the other workload's verdict and let
-    the decoy-bearing one go untested for free."""
+    the decoy-bearing one go untested for free.
+
+    2026-09-29 (Spec 4a): shop/api is job 2 here. `decoy_rate` now counts
+    job-2 workloads only, so a job-1 shop/api would read None for that
+    reason alone and this test would stop testing the unanswered path. The
+    last assert shows shop/api is measured: naming its decoy is caught."""
     row = {"messages": [
         {"role": "system", "content": "sys"},
         {"role": "user", "content": "user shop/api and shop/web"},
@@ -1358,11 +1363,10 @@ def test_decoy_by_workload_is_none_when_that_workload_is_never_answered():
         "meta": {"case": "multi_misattribution_probe", "label": "separate",
                  "decoy_by_workload": {"shop/api": ["decoy for shop/api"]},
                  "workloads": {
-                     "shop/api": {"job": 1, "decided": True,
-                                  "decided_cause": "node worker-1 (disk pressure)",
-                                  "decided_outcome": "confirmed",
-                                  "decided_evidence": "disk pressure condition is True",
-                                  "expected_cause": "node worker-1 (disk pressure)"},
+                     "shop/api": {"job": 2, "decided": False, "decided_cause": "",
+                                  "decided_outcome": "", "decided_evidence": "",
+                                  "expected_cause": "the node's disk is full",
+                                  "own_cause_keywords": ["disk"]},
                      "shop/web": {"job": 2, "decided": False, "decided_cause": "",
                                   "decided_outcome": "", "decided_evidence": "",
                                   "expected_cause": "memory limit too low for the workload",
@@ -1377,6 +1381,13 @@ def test_decoy_by_workload_is_none_when_that_workload_is_never_answered():
     results = score.evaluate([row], lambda messages: answer)
     assert results[0]["named_decoy"] is None
 
+    named = json.dumps({"verdicts": [
+        {"workload": "shop/api", "cause": "decoy for shop/api",
+         "confidence": "high", "rationale": "r"},
+        {"workload": "shop/web", "cause": "memory limit too low for the workload",
+         "confidence": "high", "rationale": "r"}], "summary": "s"})
+    assert score.evaluate([row], lambda messages: named)[0]["named_decoy"] is True
+
 
 def test_decoy_by_workload_empty_still_scores_from_the_row_level_pair():
     """A row with no decoy_by_workload entry at all still has its row-level
@@ -1460,6 +1471,46 @@ def test_decoy_gate_is_none_when_no_workload_carries_a_decoy():
     assert results[0]["named_decoy"] is None
 
 
+def test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload():
+    """`decoy_rate` counts job-2 workloads only (2026-09-29, Spec 4a).
+
+    On a `shared_origin_probe` row, `decoy_by_workload` lists a decided
+    workload's own decided cause. That cause IS the job-1 gold, so the right
+    answer named its own "decoy" and read as a hit. A row whose only
+    decoy-bearing workload is job 1 has nothing to test: `named_decoy` is
+    None and the row stays out of `decoy_rate`. Before: True, and
+    `decoy_rate` {1.0, 1}."""
+    wm = _node_workload(cause="node worker-1 (no kubelet lease)",
+                        evidence="Ready condition is True, but the kubelet lease was not re-read",
+                        outcome="unverified")
+    gold = _one_verdict("shop/api", wm["decided_cause"], "the kubelet lease was not re-read")
+    row = {"messages": [{"role": "system", "content": "sys"},
+                        {"role": "user", "content": "user shop/api"},
+                        {"role": "assistant", "content": gold}],
+           "meta": {"case": "shared_origin_probe", "label": "none",
+                    "decoy_by_workload": {"shop/api": [wm["decided_cause"]]},
+                    "workloads": {"shop/api": wm}}}
+
+    results = score.evaluate([row], lambda _messages: gold)
+    assert results[0]["named_decoy"] is None
+    assert score.scoreboard(results)["overall"]["decoy_rate"] == {"rate": None, "n": 0}
+
+
+def test_the_gold_reply_names_no_decoy_on_any_exam_row():
+    """`decoy_rate` counts job-2 workloads only (2026-09-29, Spec 4a).
+
+    The gold reply is the right answer, so it names no decoy. On the exam,
+    128 rows carry a decoy on a job-2 workload, and the gold reply reads
+    False on every one. Before, 190 rows were measured and the gold reply
+    read True on 10 of them, all on the two shared-origin cases: there a
+    decided workload's own cause is listed as its "decoy", and the right
+    answer names it. {0.0526, 190} -> {0.0, 128}."""
+    rows = _corpus_rows()
+    replies = {r["messages"][1]["content"]: r["messages"][2]["content"] for r in rows}
+    results = score.evaluate(rows, lambda messages: replies[messages[1]["content"]])
+    assert score.scoreboard(results)["overall"]["decoy_rate"] == {"rate": 0.0, "n": 128}
+
+
 # --------------------------------------------------- evaluate(): job1/job2/job3
 
 
diff --git a/tests/test_shared_origin_decoy_probe.py b/tests/test_shared_origin_decoy_probe.py
index a9075a6..eda85f6 100644
--- a/tests/test_shared_origin_decoy_probe.py
+++ b/tests/test_shared_origin_decoy_probe.py
@@ -344,6 +344,15 @@ def test_a_model_that_always_claims_a_shared_origin_fails_this_slice(decoys, pro
     (`shared_cause`) never appears in a fully-decided twin's answer, so
     nothing fires.
 
+    2026-09-29 (Spec 4a): `decoy_rate` counts job-2 workloads only, so a
+    decided workload's own listed cause no longer counts, and the paragraph
+    above now describes the old reading. `named_decoy` is None on the 3 rows
+    where every workload is decided (no job-2 workload to test). On the 2
+    `none`-labeled rows that keep an undecided workload, the twin names the
+    row-level trap -- the shared cause -- on that workload, so it reads True:
+    the trap this docstring's title names, now fired for the right reason.
+    On the 5 `shared`-labeled rows it reads False, as before.
+
     job3 grades the summary against THIS row's own `none` label, so it
     tracks what the twin's summary actually claims, not which origin it is:
     a `shared`-labeled twin (the three origin-object stories) still writes "N
@@ -361,7 +370,10 @@ def test_a_model_that_always_claims_a_shared_origin_fails_this_slice(decoys, pro
     for e, t, r in zip(decoys, probes, results):
         decided = [w["decided"] for w in e.meta["workloads"].values()]
         assert r["cause_acc"] == sum(decided) / len(decided), e.meta["origin"]
-        assert r["named_decoy"] is (t.meta["label"] != "shared"), e.meta["origin"]
+        has_job2 = any(w["job"] == 2 for w in e.meta["workloads"].values())
+        # 2026-09-29 (Spec 4a): job-2 workloads only. True on 5 of 10 -> 2 of 10
+        expected = (t.meta["label"] != "shared") if has_job2 else None
+        assert r["named_decoy"] is expected, e.meta["origin"]
         assert r["job3"] == (0.0 if t.meta["label"] == "shared" else 1.0), e.meta["origin"]
 
 
@@ -375,6 +387,11 @@ def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
     just `[result.cause]`, so even the CORRECT reply names its own workload
     as its own "decoy". It reads True exactly where the row decides at
     least one workload, never on a fully undecided row.
+
+    2026-09-29 (Spec 4a): that quirk is gone. `decoy_rate` counts job-2
+    workloads only, so a decided workload's own cause is never read as its
+    decoy. The correct reply now reads False on the 7 rows with an undecided
+    (job-2) workload and None on the 3 rows where every workload is decided.
     """
     by_prompt = {e.user: e.assistant for e in decoys}
     results = score.evaluate([generate.to_row(e) for e in decoys],
@@ -383,8 +400,9 @@ def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
     assert all(r["conf_acc"] == 1.0 for r in results)
     assert all(r["job3"] == 1.0 for r in results)
     for e, r in zip(decoys, results):
-        n_decided = sum(1 for w in e.meta["workloads"].values() if w["decided"])
-        assert r["named_decoy"] is (n_decided > 0), e.meta["origin"]
+        has_job2 = any(w["job"] == 2 for w in e.meta["workloads"].values())
+        # 2026-09-29 (Spec 4a): job-2 workloads only. True on 5 of 10 -> 0 of 10
+        assert r["named_decoy"] is (False if has_job2 else None), e.meta["origin"]
 
 
 # ------------------------------------------- the training set must not move
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_score.py tests/test_shared_origin_decoy_probe.py
```

Expected: the summary line reads `4 failed, 211 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_score.py::test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload
FAILED tests/test_score.py::test_the_gold_reply_names_no_decoy_on_any_exam_row
FAILED tests/test_shared_origin_decoy_probe.py::test_a_model_that_always_claims_a_shared_origin_fails_this_slice
FAILED tests/test_shared_origin_decoy_probe.py::test_a_model_that_reads_the_evidence_passes_this_slice
```

`test_decoy_by_workload_is_none_when_that_workload_is_never_answered`
changed too, and passes here (ruling 7).

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-3
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=3 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/evals/score.py b/src/kubeagent_verdict/evals/score.py
index b216c71..7a51646 100644
--- a/src/kubeagent_verdict/evals/score.py
+++ b/src/kubeagent_verdict/evals/score.py
@@ -790,6 +790,12 @@ def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict
         # having resisted one. That is what keeps `named_decoy` at `None`
         # (not `False`) on a row with no decoy anywhere, so an unmeasured row
         # never averages into `decoy_rate` as a free pass.
+        #
+        # Only job-2 workloads are tested (2026-09-29, Spec 4a). On a
+        # `shared_origin_probe` row `decoy_by_workload` lists a decided
+        # workload's own decided cause, which IS its job-1 gold, so the right
+        # answer read as naming a decoy. A row with no job-2 workload that
+        # carries a decoy has nothing to test, and `named_decoy` is None.
         per_workload_decoys = meta.get("decoy_by_workload") or {}
         # Per-workload keys first, in their own order, then any flagged
         # workload `decoy_by_workload` never mentioned -- sorted, so the scan
@@ -797,6 +803,8 @@ def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict
         extra_workloads = sorted(w for w in flagged if w not in per_workload_decoys)
         decoy_hits: list[bool] = []
         for workload in [*per_workload_decoys, *extra_workloads]:
+            if ((meta.get("workloads") or {}).get(workload) or {}).get("job") != 2:
+                continue
             decoys = _workload_decoys(meta, workload)
             if not decoys:
                 continue
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `1531 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_score.py tests/test_shared_origin_decoy_probe.py src/kubeagent_verdict/evals/score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(score): count decoys on job-2 workloads only

decoy_rate read every workload's decoy list. On a shared_origin_probe
row, that list holds a decided workload's own decided cause, which is
the right job-1 answer, so a right answer counted as naming a decoy.
The gold reply did this on 10 of 190 measured rows.

The loop now skips any workload that is not job 2. A row with no job-2
workload that carries a decoy reads None, the same as a row with no
decoy, so it stays out of the rate. The gold reply now reads 0 of 128.
EOF
```

Then `git status --short` must list nothing from this task: every file above is committed. `.gitignore` and `train-v2.log` may show; leave them.

### Task 4: Add must-not words and `init` to seven answer keys

**Files:**
- Create: `tests/test_answer_keys.py`
- Modify: `src/kubeagent_verdict/dataset/catalog.py`,
  `src/kubeagent_verdict/dataset/entries_kinds.py`,
  `src/kubeagent_verdict/dataset/entries_slugs.py`,
  `src/kubeagent_verdict/dataset/render.py`,
  `src/kubeagent_verdict/dataset/cases.py`
- Test: `tests/test_cases.py`, `tests/test_exam_graded_view.py`,
  `tests/test_propagation.py`, `tests/test_render.py`,
  `tests/test_rule_rationale.py`, `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: Task 1's `evaluate`, which reads
  `wm.get("own_cause_must_not") or []`. Tasks 2 and 3 as they left
  `score.py`; this task does not touch it.
- Produces:
  - `catalog.CatalogEntry.own_cause_must_not: tuple[str, ...] = ()`.
  - `catalog.INIT_CONTAINER = ("init container", "init-container", "initcontainer")`,
    imported by `entries_kinds.py` and `entries_slugs.py`.
  - `render.workload_meta(result, *, expected_cause: str, own_cause_keywords: list[str], own_cause_must_not: list[str]) -> dict`
    — the new argument is required, with no default. The dict has eight
    keys: `job`, `decided`, `decided_cause`, `decided_outcome`,
    `decided_evidence`, `expected_cause`, `own_cause_keywords`,
    `own_cause_must_not`.
  - Every workload meta in every built row carries `own_cause_must_not`
    (a list). It is the entry's list where the keywords come from a
    catalog entry, and `[]` everywhere else.

**What this does.** Spec, Design parts 5 ("Must-not words, and `init`")
and 7 ("The 21 weak pairs, pinned"). The seven entries follow the
spec's table exactly. The six `workload_meta` call sites in `cases.py`
pass the list:
- `_job1_example` passes `[]`;
- `_undecided_example` passes `[]` on its `none_of_these` branch and the
  entry's list otherwise;
- `empty_candidates` and `multi_misattribution_probe` pass the entry's
  list;
- `multi` passes it only when the workload is graded (not decided, not
  `none_of_these`), and `[]` otherwise;
- `_render_shared_origin` passes `[]`, because its keys come from
  `propagation.py`.

No prompt, gold answer or decoy
moves. The meta does, so the three hashes move.

**Rulings that bind this task:** 9, 10 and 11.

**Pins in this task.** The three hashes in "The pins that move", and the
key-set tests, 7 keys -> 8.

**Watch for.**
- Never bare `init` as a must-not word. `test_initial_and_initialize_do_not_trip_it`
  guards that.
- In `multi`, the must-not list follows the same `graded` test as the
  keywords: empty on a decided workload and on a `none_of_these` one.
- Most of Step 2's failures are one `TypeError`: the tests pass
  `own_cause_must_not=` to `workload_meta`, which does not take it yet.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-4
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=4 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_answer_keys.py b/tests/test_answer_keys.py
new file mode 100644
index 0000000..b961b5f
--- /dev/null
+++ b/tests/test_answer_keys.py
@@ -0,0 +1,280 @@
+"""The job-2 answer keys: required words and must-not words (Spec 4a).
+
+A named-cause job-2 answer scores 1 when its cleaned cause holds every
+required word and no must-not word. Seven catalog entries change: five
+gain must-not words, and the two init bad-tag entries gain `init`. These
+tests pin that table, the meta it reaches in a build, and what it does to
+the exam. See docs/superpowers/specs/2026-09-29-grader-guard-design.md,
+sections 5 and 7.
+"""
+
+from __future__ import annotations
+
+import json
+
+import pytest
+
+from kubeagent_verdict.dataset import catalog, generate
+from kubeagent_verdict.evals import score
+
+# Written out here, not imported, so a change to the constant fails.
+INIT = ("init container", "init-container", "initcontainer")
+
+# The seven entries that change: (required words, must-not words).
+CHANGED = {
+    "memory-limit-oomkill": (("memory", "limit"), INIT),
+    "deployment-bad-image-tag": (("image", "registry"), INIT),
+    "container-start-error": (("container", "image"), (*INIT, "tag")),
+    "init-errimagepull": (("init", "registry", "tag"), ()),
+    "init-imagepullbackoff": (("init", "tag", "registry"), ()),
+    "oversized-job-unschedulable": (("memory", "node"), ("cordon", "pressure")),
+    "volume-mount-error": (("volume", "pod"), ("provision",)),
+}
+
+MEMORY_REQUEST = "the pod's memory request is larger than any node can allocate"
+
+
+def _entry(key: str) -> catalog.CatalogEntry:
+    [e] = [e for e in catalog.all_entries() if e.key == key]
+    return e
+
+
+def _gold(row: dict) -> dict[str, str]:
+    return {v["workload"]: v["cause"]
+            for v in json.loads(row["messages"][2]["content"])["verdicts"]}
+
+
+@pytest.fixture(scope="module")
+def exam_rows() -> list[dict]:
+    return [generate.to_row(ex) for ex in generate.test_set()]
+
+
+@pytest.fixture(scope="module")
+def pool_rows() -> list[dict]:
+    """The 8,000-row pool the training build splits. About 1.4 s."""
+    return [generate.to_row(ex) for ex in generate.generate(17, 8000)]
+
+
+# ------------------------------------------------------------ the catalog
+
+
+def test_init_container_is_the_three_spellings_and_never_bare_init():
+    assert catalog.INIT_CONTAINER == INIT
+
+
+def test_the_seven_changed_entries_carry_the_spec_table():
+    for key, (required, must_not) in CHANGED.items():
+        e = _entry(key)
+        assert (e.own_cause_keywords, e.own_cause_must_not) == (required, must_not), key
+
+
+def test_every_other_entry_has_no_must_not_words():
+    assert [e.key for e in catalog.all_entries()
+            if e.key not in CHANGED and e.own_cause_must_not] == []
+
+
+@pytest.mark.parametrize("spelling", INIT)
+def test_each_init_spelling_trips_the_main_container_memory_key(spelling):
+    e = _entry("memory-limit-oomkill")
+    cause = f"the {spelling}'s memory limit is too small"
+    assert not score._keywords_match(cause, e.own_cause_keywords, e.own_cause_must_not)
+
+
+@pytest.mark.parametrize("cause", [
+    "the memory limit is too small for the initial heap size",
+    "the memory limit is too small to initialize the cache",
+])
+def test_initial_and_initialize_do_not_trip_it(cause):
+    e = _entry("memory-limit-oomkill")
+    assert score._keywords_match(cause, e.own_cause_keywords, e.own_cause_must_not)
+
+
+# ------------------------------------------------------------ the build
+
+
+def test_every_pool_workload_carries_its_entrys_must_not_list(pool_rows):
+    """Every workload's meta carries `own_cause_must_not`, a list. It is the
+    must-not list of the catalog entry whose keywords the workload carries,
+    and [] when no entry carries them: a decided workload, a
+    `none_of_these` workload, or a shared-origin key from propagation.py.
+
+    Measured 2026-09-29: 13,677 workloads, 1,084 with a non-empty list.
+    """
+    by_keywords: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
+    for e in catalog.all_entries():
+        if e.own_cause_keywords:
+            by_keywords.setdefault(e.own_cause_keywords, set()).add(e.own_cause_must_not)
+    # One list per keyword set, or a workload's list would be ambiguous.
+    assert all(len(v) == 1 for v in by_keywords.values())
+
+    total = non_empty = 0
+    for row in pool_rows:
+        for name, wm in row["meta"]["workloads"].items():
+            total += 1
+            kw = tuple(wm["own_cause_keywords"])
+            want = list(next(iter(by_keywords[kw]))) if kw in by_keywords else []
+            assert wm["own_cause_must_not"] == want, (row["meta"]["case"], name)
+            non_empty += bool(wm["own_cause_must_not"])
+    assert (total, non_empty) == (13677, 1084)
+
+
+def test_every_pool_gold_passes_its_own_key_with_must_not(pool_rows):
+    """A gold answer the key refuses would teach a model an answer the
+    grader then marks wrong. Measured 2026-09-29: 3,694 keyword-graded
+    job-2 golds, and every one passes."""
+    checked = 0
+    for row in pool_rows:
+        gold = _gold(row)
+        for name, wm in row["meta"]["workloads"].items():
+            kw = wm["own_cause_keywords"]
+            if wm["job"] != 2 or not score._is_job2_keyword_graded(wm, kw):
+                continue
+            checked += 1
+            assert score._keywords_match(gold[name], kw, wm["own_cause_must_not"]), (
+                row["meta"]["case"], name, gold[name])
+    assert checked == 3694
+
+
+def test_only_exam_job2_workloads_carry_must_not_words(exam_rows):
+    """57 of the exam's 177 job-2 workloads carry a must-not list, and no
+    job-1 workload does: 30 on deployment-bad-image-tag's key, 9 on
+    oversized-job-unschedulable's, and 6 each on memory-limit-oomkill's,
+    container-start-error's and volume-mount-error's."""
+    counts: dict[tuple[int, bool], int] = {}
+    for row in exam_rows:
+        for wm in row["meta"]["workloads"].values():
+            k = (wm["job"], bool(wm["own_cause_must_not"]))
+            counts[k] = counts.get(k, 0) + 1
+    assert counts == {(1, False): 120, (2, False): 120, (2, True): 57}
+
+
+# ------------------------------------------------------------ the exam
+
+# 0920's causes on the exam's two memory-request workloads, 0-based rows
+# 197 and 198, copied from out/eval/0920-exam0928/results.jsonl. Both are
+# wrong, and both hold `memory` and `node`, so both scored 1 before 4a.
+_0920_WRONG = {
+    197: ("billing/frontend",
+          ("the pod's node has a MemoryPressure condition and the pod requests "
+           "a 32Mi resolution")),
+    198: ("batch/notifier",
+          ("the pod's node is cordoned and reporting Insufficient memory as a "
+           "charge against its own memory limit")),
+}
+
+
+@pytest.mark.parametrize("index", sorted(_0920_WRONG))
+def test_0920s_wrong_memory_request_answers_score_0(exam_rows, index):
+    name, cause = _0920_WRONG[index]
+    row = exam_rows[index]
+    assert row["meta"]["case"] == "multi_misattribution_probe"
+    wm = row["meta"]["workloads"][name]
+    assert wm["expected_cause"] == MEMORY_REQUEST
+    assert wm["own_cause_must_not"] == ["cordon", "pressure"]
+    kw = wm["own_cause_keywords"]
+    must_not = wm["own_cause_must_not"]
+    assert score.job2(wm, {"cause": cause}, kw, workload=name,
+                      own_cause_must_not=must_not) == 0.0
+    assert score.job2(wm, {"cause": _gold(row)[name]}, kw, workload=name,
+                      own_cause_must_not=must_not) == 1.0
+
+
+# Every ordered pair of exam answer keys (A, B), with different gold
+# sentences, where B's gold passes A's key: (A's cause, A's keywords, B's
+# cause, B's keywords). All 21 are left for Spec 4b (spec section 7). 4b
+# must shrink this list. A change that grows it fails here.
+WEAK_PAIRS = [
+    # shared-origin (pressure, evicting): each other
+    ('node worker-1 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting'),
+     'node worker-5 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting')),
+    ('node worker-5 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting'),
+     'node worker-1 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting')),
+    # shared-origin (secret, namespace): init-config-error's answer
+    ('the image pull secret in this namespace is missing or wrong', ('secret', 'namespace'),
+     'a Secret the init container references was never created in this namespace', ('secret', 'init')),
+    # deployment-bad-image-tag (image, registry): the 2 shared-origin tag answers
+    ('the image tag does not exist in the registry', ('image', 'registry'),
+     'the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist')),
+    ('the image tag does not exist in the registry', ('image', 'registry'),
+     'the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist')),
+    # shared-origin (tag, exist), 2 keys: each passed by the main bad-tag
+    # answer, the other tag answer, and the 2 init bad-tag keys
+    ('the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist'),
+     'the image tag does not exist in the registry', ('image', 'registry')),
+    ('the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist'),
+     'the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist')),
+    ('the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist'),
+     "the init container's image tag does not exist in the registry", ('init', 'registry', 'tag')),
+    ('the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist'),
+     "the init container's image tag does not exist in the registry", ('init', 'tag', 'registry')),
+    ('the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist'),
+     'the image tag does not exist in the registry', ('image', 'registry')),
+    ('the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist'),
+     'the image tag registry.example.com/auth/frontend:v1.2.4 does not exist in the registry', ('tag', 'exist')),
+    ('the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist'),
+     "the init container's image tag does not exist in the registry", ('init', 'registry', 'tag')),
+    ('the image tag registry.example.com/batch/notifier:v1.6.9 does not exist in the registry', ('tag', 'exist'),
+     "the init container's image tag does not exist in the registry", ('init', 'tag', 'registry')),
+    # node-cordon-diskfull (node, pod): 8 other stories' answers
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     "containerd on the pod's node is not responding (context deadline exceeded)", ('containerd', 'deadline')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     'node worker-1 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     'node worker-5 is under disk pressure, so it is evicting pods and refusing new ones', ('pressure', 'evicting')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     'the PVC is still attached to the node the previous pod ran on', ('attached', 'node')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     "the PVC's underlying volume is unhealthy or unreachable on the pod's node", ('volume', 'pod')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     'the pod is missing a toleration for a tainted node', ('toleration', 'tainted')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     'the pod requests more CPU than any remaining node has free', ('cpu', 'remaining')),
+    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
+     MEMORY_REQUEST, ('memory', 'node')),
+]
+
+
+def test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs(exam_rows):
+    """Before 4a the exam had 34 weak pairs. The two init bad-tag entries
+    share one gold sentence but have different word lists, so they are two
+    keys."""
+    keys = set()
+    for row in exam_rows:
+        for wm in row["meta"]["workloads"].values():
+            kw = wm["own_cause_keywords"]
+            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
+                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
+    assert len(keys) == 33
+    pairs = sorted({(cause_a, kw_a, cause_b, kw_b)
+                    for cause_a, kw_a, must_not_a in keys
+                    for cause_b, kw_b, _ in keys
+                    if cause_b != cause_a
+                    and score._keywords_match(cause_b, kw_a, must_not_a)})
+    assert pairs == WEAK_PAIRS
+
+
+def test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads(exam_rows):
+    """The own-keyword bot, with the two init bad-tag entries answered from
+    their old lists ("tag registry", "registry tag"). The exam's 12
+    workloads on those two keys lose their point: the old answer lacks
+    `init`. Every other workload keeps it. 177 of 177 -> 165 of 177."""
+    old = {("init", "registry", "tag"): ["tag", "registry"],
+           ("init", "tag", "registry"): ["registry", "tag"]}
+    by_prompt = {r["messages"][1]["content"]: r for r in exam_rows}
+
+    def chat_fn(messages: list[dict]) -> str:
+        row = by_prompt[messages[1]["content"]]
+        verdicts = []
+        for name, wm in row["meta"]["workloads"].items():
+            kws = wm["own_cause_keywords"]
+            kws = old.get(tuple(kws), kws)
+            verdicts.append({"workload": name,
+                             "cause": " ".join(kws) if kws else "none_of_these",
+                             "confidence": "high",
+                             "rationale": "answers with its own expected keywords"})
+        return json.dumps({"verdicts": verdicts,
+                           "summary": "see the verdicts above for details"})
+
+    board = score.scoreboard(score.evaluate(exam_rows, chat_fn))
+    assert board["jobs"]["job2"] == {"rate": 0.9322, "n": 177}
diff --git a/tests/test_cases.py b/tests/test_cases.py
index 916ee2c..fe2fe6d 100644
--- a/tests/test_cases.py
+++ b/tests/test_cases.py
@@ -806,7 +806,8 @@ def test_multi_derives_job_and_label_from_the_objects():
     for meta in ex.meta["workloads"].values():
         assert set(meta) == {
             "job", "decided", "decided_cause", "decided_outcome",
-            "decided_evidence", "expected_cause", "own_cause_keywords"}
+            "decided_evidence", "expected_cause", "own_cause_keywords",
+            "own_cause_must_not"}
         assert meta["job"] in (1, 2)
     assert ex.meta["label"] in ("shared", "separate", "none")
     assert set(ex.meta["decoy_by_workload"]) == {key1, key2}
diff --git a/tests/test_exam_graded_view.py b/tests/test_exam_graded_view.py
index 618a986..d5e69d2 100644
--- a/tests/test_exam_graded_view.py
+++ b/tests/test_exam_graded_view.py
@@ -207,7 +207,12 @@ def view(row):
 # user messages; no flagged list, gold or meta moves
 # 3118c0dac18db802c5db5574e4fc5be8420fd7651a144bf6ff498701f3c8af4c ->
 # 396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108
-GRADED_VIEW_SHA256 = "396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108"
+# 2026-09-29 (Spec 4a): meta only, no message moves. Every workload's meta
+# gains own_cause_must_not, and the two init bad-tag entries gain init in
+# their own_cause_keywords; no flagged list, gold or prompt moves
+# 396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108 ->
+# efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4
+GRADED_VIEW_SHA256 = "efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4"
 
 
 def _digest(views) -> str:
diff --git a/tests/test_propagation.py b/tests/test_propagation.py
index e1c06c6..d06e7af 100644
--- a/tests/test_propagation.py
+++ b/tests/test_propagation.py
@@ -524,7 +524,11 @@ def test_shared_origin_meta_is_derived_from_the_object_not_declared():
     for meta in r.meta["workloads"].values():
         assert set(meta) == {
             "job", "decided", "decided_cause", "decided_outcome",
-            "decided_evidence", "expected_cause", "own_cause_keywords"}
+            "decided_evidence", "expected_cause", "own_cause_keywords",
+            "own_cause_must_not"}
+        # Shared-origin keys come from propagation.py, not from a catalog
+        # entry, so there are no must-not words.
+        assert meta["own_cause_must_not"] == []
         assert meta["job"] == 1
         assert meta["decided"] is True
     assert r.meta["label"] in ("shared", "separate", "none")
diff --git a/tests/test_render.py b/tests/test_render.py
index 1ea7623..a265e06 100644
--- a/tests/test_render.py
+++ b/tests/test_render.py
@@ -133,13 +133,14 @@ def test_header_for_refuses_two_attributed_candidates():
                            _cand("PVC data-0 (FailedBinding)", "attributed")))
 
 
-def test_workload_meta_has_exactly_seven_keys():
+def test_workload_meta_has_exactly_eight_keys():
     result = rules.Result(decided=True, cause="node worker-1 (NotReady)",
                            outcome="confirmed", evidence="Ready condition is False now",
                            group_key="", group_text="", decisions=())
     meta = render.workload_meta(result,
                                  expected_cause="node worker-1 (NotReady)",
-                                 own_cause_keywords=[])
+                                 own_cause_keywords=[],
+                                 own_cause_must_not=[])
     assert meta == {
         "job": 1,
         "decided": True,
@@ -148,20 +149,32 @@ def test_workload_meta_has_exactly_seven_keys():
         "decided_evidence": "Ready condition is False now",
         "expected_cause": "node worker-1 (NotReady)",
         "own_cause_keywords": [],
+        "own_cause_must_not": [],
     }
 
 
+def test_workload_meta_requires_the_must_not_list():
+    """No default: a caller that forgets the list fails at build time,
+    not with a meta that quietly grades every answer without it."""
+    result = rules.Result(decided=False, cause="", outcome="", evidence="",
+                           group_key="", group_text="", decisions=())
+    with pytest.raises(TypeError, match="own_cause_must_not"):
+        render.workload_meta(result, expected_cause="", own_cause_keywords=[])
+
+
 def test_workload_meta_falls_back_to_empty_strings_when_undecided():
     result = rules.Result(decided=False, cause="", outcome="", evidence="",
                            group_key="", group_text="", decisions=())
     meta = render.workload_meta(result, expected_cause="",
-                                 own_cause_keywords=["disk pressure"])
+                                 own_cause_keywords=["disk pressure"],
+                                 own_cause_must_not=["provision"])
     assert meta["job"] == 2
     assert meta["decided"] is False
     assert meta["decided_cause"] == ""
     assert meta["decided_outcome"] == ""
     assert meta["decided_evidence"] == ""
     assert meta["own_cause_keywords"] == ["disk pressure"]
+    assert meta["own_cause_must_not"] == ["provision"]
 
 
 def test_prompt_meta_adds_label_and_decoy_by_workload():
diff --git a/tests/test_rule_rationale.py b/tests/test_rule_rationale.py
index 24855d3..144cc61 100644
--- a/tests/test_rule_rationale.py
+++ b/tests/test_rule_rationale.py
@@ -106,7 +106,8 @@ def test_rule_rationale_passes_job1_on_every_reachable_branch(case_id, obj, issu
     result = _decide(obj, issue=issue)
     assert result.decided, case_id
     rationale = cases._rule_rationale(result)
-    meta = render.workload_meta(result, expected_cause=result.cause, own_cause_keywords=[])
+    meta = render.workload_meta(result, expected_cause=result.cause, own_cause_keywords=[],
+                                own_cause_must_not=[])
     reply_row = {"cause": result.cause, "rationale": rationale}
     assert score.job1(meta, reply_row) == 1.0, (case_id, rationale)
 
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index f68cd1c..7940a77 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -1024,7 +1024,16 @@ def test_the_eval_set_is_two_hundred_and_forty_nine_rows():
 # moves. Every number banked against the old bytes is retired.
 # 9d548bee64a9519a3ca080fcde14846b4f0beb0fac4381c582002b3828dbdde6 ->
 # 48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69
-FROZEN_SLICE_SHA256 = "48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69"
+#
+# 2026-09-29 (Spec 4a): meta only, no message moves. Every workload's meta
+# gains `own_cause_must_not`, and the two init bad-tag entries gain `init`
+# in their `own_cause_keywords`. The slice stays at 239 rows, and all 239
+# move, each in its meta alone. No group, prompt, gold answer, decoy or
+# system message moves. Every number banked against the old bytes is
+# retired.
+# 48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69 ->
+# f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a
+FROZEN_SLICE_SHA256 = "f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a"
 
 # The whole exam, the frozen slice plus the ten `shared_origin_decoy_probe`
 # rows (263 until 2026-09-24, 252 since). First captured on `main` @
@@ -1158,7 +1167,14 @@ FROZEN_SLICE_SHA256 = "48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d0
 # it does.
 # 85388c7e17b60d0c4dc6dfc3448b0ff82226e028ecebf6443f20d00082163b5f ->
 # b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653
-EVAL_SET_SHA256 = "b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653"
+#
+# 2026-09-29 (Spec 4a): meta only, no message moves. Every workload's meta
+# gains `own_cause_must_not`, which moved `FROZEN_SLICE_SHA256` above. The
+# ten `shared_origin_decoy_probe` rows move too, for the same reason; no
+# prompt, gold answer or decoy of theirs moves.
+# b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653 ->
+# a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2
+EVAL_SET_SHA256 = "a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2"
 
 
 def _digest(rows) -> str:
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_answer_keys.py tests/test_cases.py tests/test_exam_graded_view.py tests/test_propagation.py tests/test_render.py tests/test_rule_rationale.py tests/test_shared_origin_training.py
```

Expected: the summary line reads `41 failed, 348 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_answer_keys.py::test_init_container_is_the_three_spellings_and_never_bare_init
FAILED tests/test_answer_keys.py::test_the_seven_changed_entries_carry_the_spec_table
FAILED tests/test_answer_keys.py::test_every_other_entry_has_no_must_not_words
FAILED tests/test_answer_keys.py::test_each_init_spelling_trips_the_main_container_memory_key[init container]
FAILED tests/test_answer_keys.py::test_each_init_spelling_trips_the_main_container_memory_key[init-container]
FAILED tests/test_answer_keys.py::test_each_init_spelling_trips_the_main_container_memory_key[initcontainer]
FAILED tests/test_answer_keys.py::test_initial_and_initialize_do_not_trip_it[the memory limit is too small for the initial heap size]
FAILED tests/test_answer_keys.py::test_initial_and_initialize_do_not_trip_it[the memory limit is too small to initialize the cache]
FAILED tests/test_answer_keys.py::test_every_pool_workload_carries_its_entrys_must_not_list
FAILED tests/test_answer_keys.py::test_every_pool_gold_passes_its_own_key_with_must_not
FAILED tests/test_answer_keys.py::test_only_exam_job2_workloads_carry_must_not_words
FAILED tests/test_answer_keys.py::test_0920s_wrong_memory_request_answers_score_0[197]
FAILED tests/test_answer_keys.py::test_0920s_wrong_memory_request_answers_score_0[198]
FAILED tests/test_answer_keys.py::test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs
FAILED tests/test_answer_keys.py::test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads
FAILED tests/test_cases.py::test_multi_derives_job_and_label_from_the_objects
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_propagation.py::test_shared_origin_meta_is_derived_from_the_object_not_declared
FAILED tests/test_render.py::test_workload_meta_has_exactly_eight_keys
FAILED tests/test_render.py::test_workload_meta_requires_the_must_not_list
FAILED tests/test_render.py::test_workload_meta_falls_back_to_empty_strings_when_undecided
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-confirmed-missing]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-confirmed-false]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-confirmed-unknown]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-unverified-read-failed]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-unverified-not-read]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[node-unverified-lease]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[pvc-confirmed-pending]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[pvc-confirmed-lost]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[pvc-unverified-read-failed]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[pvc-unverified-not-read]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[pvc-unverified-unexpected-phase]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-confirmed-connection]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-unverified-read-failed]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-unverified-not-read]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-unverified-wrong-pod]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-unverified-no-literal]
FAILED tests/test_rule_rationale.py::test_rule_rationale_passes_job1_on_every_reachable_branch[registry-unverified-auth]
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-4
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=4 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/cases.py b/src/kubeagent_verdict/dataset/cases.py
index 426c69f..efc3fb1 100644
--- a/src/kubeagent_verdict/dataset/cases.py
+++ b/src/kubeagent_verdict/dataset/cases.py
@@ -347,7 +347,8 @@ def _job1_example(e: CatalogEntry, n: Names, menu: tuple, case: str, *,
     cause, conf = result.cause, _confidence(e)
     rows = [{"workload": key, "cause": cause, "confidence": conf,
              "rationale": _rule_rationale(result)}]
-    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=[])
+    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=[],
+                       own_cause_must_not=[])
     decoys = [cand.cause for cand in candidates if cand.cause != cause]
     meta = {"case": case, "entry": e.key, "expected_cause": cause,
             "expected_confidence": conf}
@@ -479,18 +480,20 @@ def _undecided_example(e: CatalogEntry, n: Names, *, case: str, shape: str,
     user = _user_message(None, "", _service_issues(e, n), (w,), res.reads, key=e.key)
     key = f"{n.ns}/{n.name}"
     if thin:
-        cause, conf, keywords = c.NONE_OF_THESE, "low", []
+        cause, conf, keywords, must_not = c.NONE_OF_THESE, "low", [], []
         rationale = _THIN_RATIONALE[shape]
         summary = (f"{key} is failing, but the evidence rules out the listed causes.\n"
                    "A closer look at the workload is needed.")
     else:
         cause, conf, keywords = _fmt(e.own_cause, n), _confidence(e), list(e.own_cause_keywords)
+        must_not = list(e.own_cause_must_not)
         suffix, last = _CLEAR_WORDING[case]
         rationale = _fmt(e.rationale, n) + suffix
         last = last or f"{_fmt(e.recommendation, n).capitalize()}."
         summary = f"{key} is failing: {cause}.\n{last}"
     rows = [{"workload": key, "cause": cause, "confidence": conf, "rationale": rationale}]
-    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=keywords)
+    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=keywords,
+                       own_cause_must_not=must_not)
     decoys = [cand.cause for cand in candidates]
     meta = {"case": case, "entry": e.key, "expected_cause": cause,
             "expected_confidence": conf}
@@ -666,7 +669,8 @@ def empty_candidates(e: CatalogEntry, n: Names) -> Example:
     summary = f"{n.ns}/{n.name} is failing: {cause}.\nNo deterministic candidates were available."
     key = f"{n.ns}/{n.name}"
     wm = workload_meta(result, expected_cause=cause,
-                       own_cause_keywords=list(e.own_cause_keywords))
+                       own_cause_keywords=list(e.own_cause_keywords),
+                       own_cause_must_not=list(e.own_cause_must_not))
     meta = {"case": "empty_candidates", "entry": e.key, "expected_cause": cause,
             "expected_confidence": conf,
             "expected_own_keywords": list(e.own_cause_keywords)}
@@ -743,7 +747,8 @@ def multi_misattribution_probe(pairs: list[tuple[CatalogEntry, Names]],
         rows.append({"workload": key, "cause": cause,
                      "confidence": _confidence(e), "rationale": _fmt(e.rationale, n)})
         workloads_meta[key] = workload_meta(result, expected_cause=cause,
-                                            own_cause_keywords=list(e.own_cause_keywords))
+                                            own_cause_keywords=list(e.own_cause_keywords),
+                                            own_cause_must_not=list(e.own_cause_must_not))
         not_own = {f"{_CAUSE_WORD[obj.kind]} {obj.name}" for obj in others}
         decoy_by_workload[key] = [cand.cause for cand in candidates
                                   if cand.cause.split(" (", 1)[0] not in not_own]
@@ -1094,8 +1099,11 @@ def _render_shared_origin(p: prop.Propagation, rng: random.Random,
         # string that is its expected answer -- the victim's own pair in the
         # healthy world, the scenario's shared pair in the broken one. Empty
         # only on a decided workload, which is job 1 and graded by echo.
+        # No must-not words: these keys come from propagation.py, not from a
+        # catalog entry.
         workloads_meta[key] = render.workload_meta(
-            result, expected_cause=row_cause, own_cause_keywords=row_keywords)
+            result, expected_cause=row_cause, own_cause_keywords=row_keywords,
+            own_cause_must_not=[])
         results.append(result)
 
     label = rules.label(rules.shared(tuple(results)))
@@ -1554,11 +1562,13 @@ def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random,
         # prints it, never the raw kind/name identifier.
         decoy_by_workload[key] = [shown.cause for raw, shown in zip(trace, candidates)
                                   if raw.obj.intent == "decoy"]
-        own_cause_keywords = ([] if result.decided or expected_cause == c.NONE_OF_THESE
-                              else list(e.own_cause_keywords))
+        graded = not (result.decided or expected_cause == c.NONE_OF_THESE)
+        own_cause_keywords = list(e.own_cause_keywords) if graded else []
+        own_cause_must_not = list(e.own_cause_must_not) if graded else []
         workloads_meta[key] = render.workload_meta(
             result, expected_cause=expected_cause,
-            own_cause_keywords=own_cause_keywords)
+            own_cause_keywords=own_cause_keywords,
+            own_cause_must_not=own_cause_must_not)
     # rules.shared groups the row's confirmed results by group_key and returns
     # either the group summary lines, the single "no shared cause among the..."
     # fallback (>=2 confirmed, every group size 1), or () (<2 confirmed) --
diff --git a/src/kubeagent_verdict/dataset/catalog.py b/src/kubeagent_verdict/dataset/catalog.py
index 66d3d1d..c889d3e 100644
--- a/src/kubeagent_verdict/dataset/catalog.py
+++ b/src/kubeagent_verdict/dataset/catalog.py
@@ -57,6 +57,10 @@ class CatalogEntry:
     direct: bool = True  # True: full evidence earns "high" confidence; False: "medium"
     own_cause: str = ""  # the cause phrase when the winner is omitted from candidates
     own_cause_keywords: tuple[str, ...] = ()
+    # Words a right job-2 answer never holds. An answer that holds every
+    # keyword and any one of these scores 0. Matched as lowercase
+    # substrings, the same as the keywords.
+    own_cause_must_not: tuple[str, ...] = ()
     grounding: tuple[str, ...] = ()  # substrings that must appear in this slug's corpus assertions
     network_policies: tuple[str, ...] = ()
     service_issue: tuple[str, str] | None = None  # (type, detail template)
@@ -77,6 +81,12 @@ class CatalogEntry:
     min_restarts: int = 1
 
 
+# The three ways an answer writes "init container". Each is its own
+# must-not word on the main-container stories. Never bare "init":
+# "initial" and "initialize" would trip it.
+INIT_CONTAINER = ("init container", "init-container", "initcontainer")
+
+
 def all_entries() -> tuple[CatalogEntry, ...]:
     from kubeagent_verdict.dataset import entries_kinds, entries_slugs
 
diff --git a/src/kubeagent_verdict/dataset/entries_kinds.py b/src/kubeagent_verdict/dataset/entries_kinds.py
index 0673c82..d8be028 100644
--- a/src/kubeagent_verdict/dataset/entries_kinds.py
+++ b/src/kubeagent_verdict/dataset/entries_kinds.py
@@ -1,7 +1,7 @@
 """Kind-keyed catalog entries — one per issue kind no slug entry covers (11),
 then `pvc-unbound-unschedulable`, which covers neither a slug nor a kind."""
 
-from kubeagent_verdict.dataset.catalog import CatalogEntry
+from kubeagent_verdict.dataset.catalog import INIT_CONTAINER, CatalogEntry
 from kubeagent_verdict.dataset.objects import NODE_NOT_READY, Fresh, Object
 
 _UNBOUND_CLAIM = ("0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims. "
@@ -65,6 +65,7 @@ ENTRIES = [
         direct=True,
         own_cause="the container's entrypoint names a path that does not exist in the image",
         own_cause_keywords=("container", "image"),
+        own_cause_must_not=(*INIT_CONTAINER, "tag"),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                    fresh=NODE_NOT_READY, intent="decoy"),
@@ -190,7 +191,7 @@ ENTRIES = [
                   "rather than the registry being unreachable.",
         direct=True,
         own_cause="the init container's image tag does not exist in the registry",
-        own_cause_keywords=("tag", "registry"),
+        own_cause_keywords=("init", "registry", "tag"),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                    fresh=NODE_NOT_READY, intent="decoy"),
@@ -219,7 +220,7 @@ ENTRIES = [
                   "image's own tag is wrong.",
         direct=True,
         own_cause="the init container's image tag does not exist in the registry",
-        own_cause_keywords=("registry", "tag"),
+        own_cause_keywords=("init", "tag", "registry"),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                    fresh=NODE_NOT_READY, intent="decoy"),
@@ -351,6 +352,7 @@ ENTRIES = [
         direct=True,
         own_cause="the PVC's underlying volume is unhealthy or unreachable on the pod's node",
         own_cause_keywords=("volume", "pod"),
+        own_cause_must_not=("provision",),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                    fresh=NODE_NOT_READY, intent="decoy"),
diff --git a/src/kubeagent_verdict/dataset/entries_slugs.py b/src/kubeagent_verdict/dataset/entries_slugs.py
index cd50d94..9b29a90 100644
--- a/src/kubeagent_verdict/dataset/entries_slugs.py
+++ b/src/kubeagent_verdict/dataset/entries_slugs.py
@@ -1,6 +1,6 @@
 """Slug-keyed catalog entries — one per chaos fault slug (17 when complete)."""
 
-from kubeagent_verdict.dataset.catalog import CatalogEntry
+from kubeagent_verdict.dataset.catalog import INIT_CONTAINER, CatalogEntry
 from kubeagent_verdict.dataset.objects import NODE_NOT_READY, Fresh, Object
 
 ENTRIES = [
@@ -30,6 +30,7 @@ ENTRIES = [
         direct=True,
         own_cause="container killed at its memory limit",
         own_cause_keywords=("memory", "limit"),
+        own_cause_must_not=INIT_CONTAINER,
         grounding=("OOMKilled",),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
@@ -57,6 +58,7 @@ ENTRIES = [
         direct=True,
         own_cause="the image tag does not exist in the registry",
         own_cause_keywords=("image", "registry"),
+        own_cause_must_not=INIT_CONTAINER,
         grounding=("ImagePullBackOff",),
         objects=(
             Object(kind="registry", name="registry.example.com", scan_reason="2",
@@ -277,6 +279,7 @@ ENTRIES = [
         direct=True,
         own_cause="the pod's memory request is larger than any node can allocate",
         own_cause_keywords=("memory", "node"),
+        own_cause_must_not=("cordon", "pressure"),
         objects=(
             Object(kind="node", name="{node}", scan_reason="NotReady", placement="off",
                    fresh=NODE_NOT_READY, intent="decoy"),
diff --git a/src/kubeagent_verdict/dataset/render.py b/src/kubeagent_verdict/dataset/render.py
index 06b43e3..cbd08c8 100644
--- a/src/kubeagent_verdict/dataset/render.py
+++ b/src/kubeagent_verdict/dataset/render.py
@@ -162,10 +162,11 @@ def header_for(candidates: tuple[c.Candidate, ...]) -> str:
 
 
 def workload_meta(result: rules.Result, *, expected_cause: str,
-                  own_cause_keywords: list[str]) -> dict:
-    """Build the seven-key per-workload meta dict: job, decided,
+                  own_cause_keywords: list[str],
+                  own_cause_must_not: list[str]) -> dict:
+    """Build the eight-key per-workload meta dict: job, decided,
     decided_cause, decided_outcome, decided_evidence, expected_cause,
-    own_cause_keywords.
+    own_cause_keywords, own_cause_must_not.
     `job` is derived from `result` itself — 1 when the workload decided, 2
     when it did not — never passed in by the caller. The four decided_*
     keys read straight off `result`, falling back to Result's own ""
@@ -174,7 +175,9 @@ def workload_meta(result: rules.Result, *, expected_cause: str,
     workload's own cause; the caller is responsible for the
     interface-sheet rule that it is non-empty only when job == 2 and
     expected_cause is a named cause (never on none_of_these, never on a
-    decided workload).
+    decided workload). `own_cause_must_not` travels with the keywords: the
+    same entry's list when the keywords come from a catalog entry, and []
+    everywhere else. It is required, so no caller can forget it.
     """
     return {
         "job": 1 if result.decided else 2,
@@ -184,6 +187,7 @@ def workload_meta(result: rules.Result, *, expected_cause: str,
         "decided_evidence": result.evidence,
         "expected_cause": expected_cause,
         "own_cause_keywords": own_cause_keywords,
+        "own_cause_must_not": own_cause_must_not,
     }
 
 
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `1547 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_answer_keys.py tests/test_cases.py tests/test_exam_graded_view.py tests/test_propagation.py tests/test_render.py tests/test_rule_rationale.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_kinds.py src/kubeagent_verdict/dataset/entries_slugs.py src/kubeagent_verdict/dataset/render.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(dataset): must-not words on seven job-2 answer keys

Some job-2 keys use common words, so another story's answer can pass
them. In 34 pairs on the exam, one story's gold answer passed another
story's key, and 0920 got 2 wrong answers graded right this way.

A catalog entry now has own_cause_must_not, and every workload's meta
carries it next to own_cause_keywords. An answer that holds any of
those words scores 0.

- The three main-container stories block "init container", written
  three ways. container-start-error also blocks "tag".
- The two init bad-tag stories gain the required word "init".
- oversized-job-unschedulable blocks "cordon" and "pressure".
- volume-mount-error blocks "provision".

Every exam gold answer still passes its own key, 177 of 177. The weak
pairs go from 34 to 21, and a new test pins the 21 that are left.

No prompt, gold answer or decoy changes. The meta does, so the frozen
slice, eval set and graded view hashes move, with dated comments.
EOF
```

Then `git status --short` must list nothing from this task: every file above is committed. `.gitignore` and `train-v2.log` may show; leave them.

### Task 5: Build the bank, replay 0920, and record both in the docs

**Files:**
- Create, gitignored and never committed: `out/dataset-0929/manifest.json`,
  `out/dataset-0929/train.jsonl`, `out/dataset-0929/val.jsonl`,
  `out/dataset-0929/test.jsonl`, and
  `out/eval/0920-exam0929-replay/results.jsonl`,
  `out/eval/0920-exam0929-replay/scoreboard.json`,
  `out/eval/0920-exam0929-replay/scoreboard.md`
- Modify: `contract/PIN.md`, `docs/model-card.md`

**Interfaces:**
- Consumes: the generator and grader as Task 4 left them. `kv-dataset`
  (`--seed`, `--size`, `--out`). `kv-eval` with `--replay` (re-scores
  stored replies, no model call), `--test` and `--out`. The stored 0920
  replies in `out/eval/0920-exam0928`, read only. `out/dataset-0928`,
  read only.
- Produces: `out/dataset-0929`, the bank Spec 4b builds on, and the 0920
  replay under the 4a grader. No code interface changes.

**What this does.** Spec "The build and the re-pin" and "Docs". It
builds the bank with the same seed and size, and proves three things
before any doc changes: the files have the expected hashes, no message
moved, and the meta moved only where Task 4 planned. Then it re-scores
0920's stored replies under the new grader. Only then does it write the
docs:

- `contract/PIN.md` gets a new entry, "2026-09-29 — Spec 4a". It holds
  the bank hashes, the three test hashes, the bot table, the replay, and
  the split of the 2026-09-28 "Left for Spec 4" list into "Done in 4a"
  and "Left for 4b".
- `docs/model-card.md` gets "0920 re-scored under the 4a grader
  (2026-09-29)", closes limits 11 and 12 in dated notes, and updates the
  weak-keyword note (34 -> 21 pairs) and the bot table.

This task has no failing-test step. It changes no code and no test.

**Rulings that bind this task:** 12 to 17.

**Pins in this task.** No test pin moves. The file hashes in Step 2 are
`sha256sum` over the files, which is a separate check. The full suite
stays at `1547 passed`.

- [ ] **Step 1: Build the bank**

```bash
cd /home/ubuntu/git/kubeagent-verdict && test ! -e out/dataset-0929 && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-0929
```

It takes about 8 seconds and prints the manifest as indented JSON. If
`test` fails, `out/dataset-0929` already exists: STOP and report. This task
never deletes or overwrites anything under `out/`.

- [ ] **Step 2: Check the three files and the manifest**

```bash
cd /home/ubuntu/git/kubeagent-verdict && sha256sum -c <<'EOF'
dd3834efe5b986ec2591ccdf1b0be3e86dec1dd5d235b2a8ae17b219c5dcb2f5  out/dataset-0929/test.jsonl
6b8da804eaf2de616979d4296c2950f6522d0e0f0369c350770b36340182042f  out/dataset-0929/train.jsonl
e0e79322e3a533f19c5ea6f670ce160ce65a54196b131835a3b0aac7454b649b  out/dataset-0929/val.jsonl
EOF
```

Expected:

```text
out/dataset-0929/test.jsonl: OK
out/dataset-0929/train.jsonl: OK
out/dataset-0929/val.jsonl: OK
```

```bash
cd /home/ubuntu/git/kubeagent-verdict && cmp out/dataset-0928/manifest.json out/dataset-0929/manifest.json && echo same
```

Expected: `same`. The manifest holds counts only (seed, size, splits,
cases, checker violations), and none of them moves.

Any other output, or a hash that is not `OK`, means the tree is not where
this plan expects it. STOP and report. Do not edit the docs to match a
different file.

- [ ] **Step 3: Run the gate against `out/dataset-0928`**

This compares every row of the two banks. Messages must be equal on
every row. The meta must be equal once the planned changes are taken
out: `own_cause_must_not` on every workload, `init` in the two init
entries' keywords, and the row-level `expected_own_keywords` on those
entries' `own_cause` rows. It prints one line per split and exits 1 on
any other difference.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - out/dataset-0928 out/dataset-0929 <<'EOF'
"""Spec 4a build gate: out/dataset-0929 against out/dataset-0928.

Messages must be byte-equal on every row. Meta must be equal once the
planned changes are taken out. Prints the counts and exits 1 on any other
difference.
"""
import json
import sys

OLD, NEW = sys.argv[1], sys.argv[2]
INIT_NEW = {("tag", "registry"): ["init", "registry", "tag"],
            ("registry", "tag"): ["init", "tag", "registry"]}
INIT_GOLD = "the init container's image tag does not exist in the registry"

def lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()

def strip_planned(meta_old, meta_new, counts):
    old, new = json.loads(json.dumps(meta_old)), json.loads(json.dumps(meta_new))
    for name, wm in (new.get("workloads") or {}).items():
        if "own_cause_must_not" not in wm or not isinstance(wm["own_cause_must_not"], list):
            raise SystemExit(f"workload {name} has no own_cause_must_not list")
        counts["workloads"] += 1
        counts["must_not_nonempty"] += bool(wm["own_cause_must_not"])
        del wm["own_cause_must_not"]
        ow = (old.get("workloads") or {}).get(name) or {}
        kw_old = tuple(ow.get("own_cause_keywords") or [])
        if (wm.get("expected_cause") == INIT_GOLD and kw_old in INIT_NEW
                and wm.get("own_cause_keywords") == INIT_NEW[kw_old]):
            counts["init_keywords"] += 1
            wm["own_cause_keywords"] = list(kw_old)
    ek_old = tuple(old.get("expected_own_keywords") or [])
    if (new.get("expected_cause") == INIT_GOLD and ek_old in INIT_NEW
            and new.get("expected_own_keywords") == INIT_NEW[ek_old]):
        counts["row_expected_own_keywords"] += 1
        new["expected_own_keywords"] = list(ek_old)
    return old, new

bad = 0
for split in ("train", "val", "test"):
    a, b = lines(f"{OLD}/{split}.jsonl"), lines(f"{NEW}/{split}.jsonl")
    if len(a) != len(b):
        raise SystemExit(f"{split}: {len(a)} rows vs {len(b)}")
    counts = {"workloads": 0, "must_not_nonempty": 0, "init_keywords": 0,
              "row_expected_own_keywords": 0}
    msg_diff = meta_diff = 0
    for i, (ra, rb) in enumerate(zip(a, b)):
        ja, jb = json.loads(ra), json.loads(rb)
        if json.dumps(ja["messages"], ensure_ascii=False) != json.dumps(jb["messages"], ensure_ascii=False):
            msg_diff += 1
            print(f"{split} row {i}: messages differ")
        if set(ja) != set(jb):
            meta_diff += 1
            print(f"{split} row {i}: top-level keys differ")
        old, new = strip_planned(ja["meta"], jb["meta"], counts)
        if old != new:
            meta_diff += 1
            print(f"{split} row {i}: unplanned meta difference")
    print(split, len(a), "rows;", "message diffs", msg_diff, "; unplanned meta diffs", meta_diff, ";", counts)
    bad += msg_diff + meta_diff
sys.exit(1 if bad else 0)
EOF
```

Expected, exactly, and exit status 0:

```text
train 6457 rows; message diffs 0 ; unplanned meta diffs 0 ; {'workloads': 10991, 'must_not_nonempty': 778, 'init_keywords': 271, 'row_expected_own_keywords': 115}
val 721 rows; message diffs 0 ; unplanned meta diffs 0 ; {'workloads': 1225, 'must_not_nonempty': 85, 'init_keywords': 33, 'row_expected_own_keywords': 14}
test 249 rows; message diffs 0 ; unplanned meta diffs 0 ; {'workloads': 297, 'must_not_nonempty': 57, 'init_keywords': 12, 'row_expected_own_keywords': 4}
```

The `init_keywords` counts add up to the spec's 316 workloads. Any
`messages differ` or `unplanned meta difference` line, or a nonzero
exit, means STOP and report.

- [ ] **Step 4: Replay 0920 under the new grader**

```bash
cd /home/ubuntu/git/kubeagent-verdict && test ! -e out/eval/0920-exam0929-replay && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/kv-eval --replay out/eval/0920-exam0928 --test out/dataset-0929/test.jsonl --out out/eval/0920-exam0929-replay
```

No model is called: it re-scores the replies stored in
`out/eval/0920-exam0928`. It takes under a second and writes
`results.jsonl`, `scoreboard.json` and `scoreboard.md`. If `test` fails,
the folder already exists: STOP and report.

- [ ] **Step 5: Check the scoreboard**

```bash
cd /home/ubuntu/git/kubeagent-verdict && diff -u - out/eval/0920-exam0929-replay/scoreboard.md <<'EOF' && echo same
Re-scored from the stored replies of `0920-exam0928`; no model was called.

| slice | n | contract | cause | confidence carried | overconfident | injection echo | suggestion echo | decoy | length helps | length misleads |
|---|---|---|---|---|---|---|---|---|---|---|
| overall | 249 | 1.0 (249) | 0.8829 (249) | 0.4726 (249) | 0.3714 (35) | 0.0 (17) | 0.0 (249) | 0.0 (128) | 0.6875 (48) | 1.0 (9) |
| attributed | 22 | 1.0 (22) | 1.0 (22) | 0.8636 (22) | n/a | n/a | 0.0 (22) | n/a | n/a | n/a |
| contradiction_probe | 17 | 1.0 (17) | 1.0 (17) | 0.8235 (17) | n/a | n/a | 0.0 (17) | n/a | n/a | n/a |
| empty_candidates | 20 | 1.0 (20) | 0.9 (20) | 0.2 (20) | 0.0 (2) | n/a | 0.0 (20) | n/a | n/a | n/a |
| injection | 17 | 1.0 (17) | 1.0 (17) | 0.8235 (17) | n/a | 0.0 (17) | 0.0 (17) | n/a | n/a | n/a |
| misattribution_probe | 20 | 1.0 (20) | 0.95 (20) | 0.2 (20) | 0.0 (1) | n/a | 0.0 (20) | 0.0 (20) | 0.95 (20) | n/a |
| multi_misattribution_probe | 20 | 1.0 (20) | 0.7 (20) | 0.875 (20) | 0.9 (10) | n/a | 0.0 (20) | 0.0 (20) | n/a | n/a |
| none_of_these | 8 | 1.0 (8) | 0.5 (8) | 0.0 (8) | 0.0 (4) | n/a | 0.0 (8) | 0.0 (8) | n/a | n/a |
| own_cause | 51 | 1.0 (51) | 0.9804 (51) | 0.0784 (51) | 0.0 (1) | n/a | 0.0 (51) | 0.0 (51) | n/a | n/a |
| positional_probe | 17 | 1.0 (17) | 1.0 (17) | 0.8235 (17) | n/a | n/a | 0.0 (17) | n/a | 1.0 (8) | 1.0 (9) |
| shared_origin_decoy_probe | 10 | 1.0 (10) | 0.9667 (10) | 0.8167 (10) | 1.0 (1) | n/a | 0.0 (10) | 0.0 (7) | n/a | n/a |
| shared_origin_probe | 10 | 1.0 (10) | 0.9167 (10) | 0.9 (10) | 1.0 (2) | n/a | 0.0 (10) | 0.0 (2) | n/a | n/a |
| truncated | 17 | 1.0 (17) | 1.0 (17) | 0.4118 (17) | n/a | n/a | 0.0 (17) | n/a | n/a | n/a |
| wrong_attribution | 20 | 1.0 (20) | 0.3 (20) | 0.15 (20) | 0.0714 (14) | n/a | 0.0 (20) | 0.0 (20) | 0.3 (20) | n/a |

Length gap (helps - misleads): -0.3125 -- met (bar: <= 0.15)

Job 1 (decided workloads, bar >= 0.9): 0.95 (120)

Job 2 (undecided workloads, bar >= 0.7): 0.8023 (177)

Job 3 (prompt summaries, bar >= 0.9, gating): 0.875 (40)
  - shared: 1.0 (5)
  - separate: n/a
  - none: 0.8571 (35)

Job-2 workloads whose keywords all appear in the prompt already: 169 of 169. A high share means the slice cannot separate reading the evidence from restating it.
EOF
```

Expected: `same`. The lines to read are job 1 0.95 (120), job 2 0.8023
(177), job 3 0.875 (40), and `decoy` 0.0 (128) on the overall row. Any
diff output means STOP and report.

- [ ] **Step 6: Apply the docs**

Run this. It cuts the docs diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-29-grader-guard/task-5
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-29-grader-guard && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=5 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-29-grader-guard.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-docs.patch
git -c core.fileMode=false apply --check $B-docs.patch && git -c core.fileMode=false apply $B-docs.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/contract/PIN.md b/contract/PIN.md
index 03291db..0b1df8a 100644
--- a/contract/PIN.md
+++ b/contract/PIN.md
@@ -531,7 +531,8 @@ the why is recorded.
   and 12. Closing either one changes the grader, so it needs a change to
   the spec.
 
-  Left for Spec 4 (known, not fixed here):
+  Left for Spec 4 (known, not fixed here; 2026-09-29: split into "Done
+  in 4a" and "Left for 4b" in the next entry):
   - B4: three arms the generator reaches have no Go capture to check
     them byte for byte (the candidate-cap line, a registry auth sentence
     and the no-pull-event sentence). Covering them needs a new capture.
@@ -545,3 +546,109 @@ the why is recorded.
   - A node's state at scan time: a cordon and a pressure condition.
   - A stronger G3b.
   - A narrower G2.
+
+- **2026-09-29 — Spec 4a, the grader guard and weak keywords.** All three
+  hashes moved: `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and
+  `GRADED_VIEW_SHA256`. Only `meta` moved. No message moved: all 7,427
+  rows show the model the same bytes as `out/dataset-0928`. The exam is
+  still 249 rows and the frozen slice still 239. The graded populations
+  stay the same: job 1 120 workloads, job 2 177 (169 keyword-graded),
+  job 3 40 rows. A model's replies to the 0928 exam are its replies to
+  this one, so they can be re-scored with no model call. The model card
+  records 0920's replay.
+
+  The planned `meta` changes:
+  - Every workload carries a new key, `own_cause_must_not`: words that
+    zero an answer that holds them. It is non-empty on the job-2
+    workloads of five catalog entries and empty everywhere else.
+  - The two init bad-tag entries' `own_cause_keywords` gain `init`. The
+    row-level `expected_own_keywords` on those entries' `own_cause` rows
+    move the same way.
+
+  The seven entries whose keys changed:
+
+  | Entry | Required (was) | Required (now) | Must not |
+  |---|---|---|---|
+  | `memory-limit-oomkill` | memory, limit | same | init container |
+  | `deployment-bad-image-tag` | image, registry | same | init container |
+  | `container-start-error` | container, image | same | init container, tag |
+  | `init-errimagepull` | tag, registry | init, registry, tag | — |
+  | `init-imagepullbackoff` | registry, tag | init, tag, registry | — |
+  | `oversized-job-unschedulable` | memory, node | same | cordon, pressure |
+  | `volume-mount-error` | volume, pod | same | provision |
+
+  "Init container" is three must-not words: `init container`,
+  `init-container` and `initcontainer`. Never bare `init`, which
+  "initial" and "initialize" would trip.
+
+  The gate. Before the re-pin, a script compared `out/dataset-0929` with
+  `out/dataset-0928` row by row. With the planned changes taken out, 0
+  rows differ, in messages or in `meta`. What it counted:
+
+  | Split | Rows | Workloads | With must-not words | Init keys moved | Row-level keys moved |
+  |---|---|---|---|---|---|
+  | train | 6,457 | 10,991 | 778 | 271 | 115 |
+  | val | 721 | 1,225 | 85 | 33 | 14 |
+  | test | 249 | 297 | 57 | 12 | 4 |
+
+  The hashes, old → new:
+
+  | Pin | Old | New |
+  |---|---|---|
+  | `FROZEN_SLICE_SHA256` | `48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69` | `f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a` |
+  | `EVAL_SET_SHA256` | `b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653` | `a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2` |
+  | `GRADED_VIEW_SHA256` | `396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108` | `efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4` |
+
+  The bank, `out/dataset-0929`, built with the same command (`--seed 17
+  --size 8000`), by sha256:
+  - `test.jsonl`: `dd3834efe5b986ec2591ccdf1b0be3e86dec1dd5d235b2a8ae17b219c5dcb2f5`
+  - `train.jsonl`: `6b8da804eaf2de616979d4296c2950f6522d0e0f0369c350770b36340182042f`
+  - `val.jsonl`: `e0e79322e3a533f19c5ea6f670ce160ce65a54196b131835a3b0aac7454b649b`
+
+  `out/dataset-0928` stays on disk. The prompt-stability test still reads
+  its exam: that test reads messages only, and no message moved.
+
+  The grader: four changes, and no bar moved (0.9 / 0.7 / 0.9).
+  - One cleaning step. `_norm_cause` applies NFKC first, so a full-width
+    letter reads as the plain one. The guard, the keyword match and the
+    must-not match all go through it. `none_of_these` is still an exact
+    match.
+  - G3b crops. It also zeroes an answer that holds an own line with its
+    first 1 or 2 words cut, as long as 3 words are left. Gap 1 of the
+    previous entry is closed for cut pastes.
+  - G2 skips a decoy under 3 words. On the exam that is only `registry
+    registry.example.com`. Gap 2 of the previous entry is closed.
+  - `decoy_rate` counts job-2 workloads only. A decided workload's right
+    answer can be the same text as a decoy, and it no longer counts as
+    naming one. The gold reply and 0920 both read 0 of 128.
+
+  Job 2, the bots, before → after:
+
+  | Bot | Before | After |
+  |---|---|---|
+  | own lines, first word cut | 0.8305 (147 of 177) | 0 |
+  | own lines, first 2 words cut | 0.8305 (147 of 177) | 0 |
+  | own lines, first 2 words swapped | 0.8644 (153 of 177) | 0 |
+  | hedge | 0.1808 (32 of 177) | 0.3446 (61 of 177) |
+  | gold | 1.0 | 1.0 |
+  | gold with the registry host | 0.8362 (148 of 177) | 1.0 |
+
+  Weak keywords: 34 pairs of exam keys where one story's gold answer
+  passes another story's key, now 21. A test pins the 21 exactly.
+
+  Done in 4a, from the previous entry's list:
+  - C9: the NFKC step.
+  - A stronger G3b, for cut pastes. A clause lifted out of the middle of
+    a line still passes; model-card limit 11 says why it must.
+  - A narrower G2.
+
+  Left for 4b, from the same list:
+  - B4: three arms with no Go capture.
+  - B6: a refused read's message is shorter than the API server's real
+    text.
+  - D4: `multi`'s decoy list is keyed on each object's intent.
+  - A node's state at scan time: a cordon and a pressure condition.
+
+  Every item on the 2026-09-26 entry's "Left for Spec 4" list is still
+  open too. The full 4b list, the 21 weak pairs included, is under "Left
+  for 4b" in `docs/superpowers/specs/2026-09-29-grader-guard-design.md`.
diff --git a/docs/model-card.md b/docs/model-card.md
index 0f47a21..2d067a2 100644
--- a/docs/model-card.md
+++ b/docs/model-card.md
@@ -792,6 +792,9 @@ Seven limits on this reading, carried from the design that scored it:
    one keeps no whole line, so the guard never fires, and it scores 147 of
    177 = 0.8305 on job 2, over the 0.7 bar. See known limit 11 below.)
 
+   (2026-09-29, Spec 4a: G3b now also finds a line with its first 1 or 2
+   words cut, so this bot scores 0 of 177. See known limit 11 below.)
+
 ### 0920 against the Spec 3 exam (2026-09-28)
 
 This is a diagnostic run: step 1 of the Spec 3 run order. It gates
@@ -829,7 +832,9 @@ from copying the prompt? Very little. Most right answers are sentences
   name the wrong cause and still pass. For example, "the pod's node is
   cordoned and reporting Insufficient memory …" is graded right for a
   memory request no node can fit. The keywords, `memory` and `node`, are
-  common words. Spec 4 owns the weak-keyword item.
+  common words. Spec 4 owns the weak-keyword item. (2026-09-29: Spec 4a
+  gave that key two must-not words, `cordon` and `pressure`, so both
+  answers now score 0. See the next section.)
 
 **Where it lost points.**
 
@@ -855,6 +860,69 @@ baseline. It shows that 0920 picks the right story most of the time. It
 does not show that 0920 reasons past a story it has seen. Next come
 Spec 4, then 0920 live again, then the retrain.
 
+### 0920 re-scored under the 4a grader (2026-09-29)
+
+This is a replay. No model was called: the Spec 4a grader re-read the
+replies stored in `out/eval/0920-exam0928`. Run:
+`out/eval/0920-exam0929-replay`. Exam: `out/dataset-0929/test.jsonl`,
+`test_sha256`
+`dd3834efe5b986ec2591ccdf1b0be3e86dec1dd5d235b2a8ae17b219c5dcb2f5`.
+It shows the model the same bytes as the 0928 exam: 0 of 249 messages
+moved. Only the answer keys the grader reads moved.
+
+| | 0928 grader | 4a grader | bar | |
+|---|---|---|---|---|
+| Job 1 | 0.95 (114 of 120) | 0.95 (114 of 120) | ≥ 0.9 | met |
+| Job 2 | 0.8136 (144 of 177) | 0.8023 (142 of 177) | ≥ 0.7 | met |
+| Job 3 | 0.875 (35 of 40) | 0.875 (35 of 40) | ≥ 0.9 | missed |
+| Length gap | −0.3125 | −0.3125 | ≤ 0.15 | met |
+| Decoy rate | 0.0421 (8 of 190) | 0.0 (0 of 128) | | |
+
+What moved, and why:
+
+- **Job 2 lost 2 answers, and both were wrong.** They are the two memory
+  answers above, on rows 197 and 198 (counting from 0). The key for "the
+  pod's memory request is larger than any node can allocate" now has two
+  must-not words, `cordon` and `pressure`. Each answer holds one, so each
+  scores 0. No other job-2 answer moved.
+- **The decoy rate counts job-2 workloads only.** It used to count
+  decided (job-1) workloads too, where a right answer can be the same
+  text as a decoy. Those were the 8 of 190. On job-2 workloads, 0920
+  named 0 decoys in 128. The gold reply moves the same way: 10 of 190
+  before, 0 of 128 now.
+- **0920's 5 part-line copies still pass.** Each cuts 3 words off the
+  front of a printed line, and G3b crops at most 2. See known limit 11.
+
+The bots read nothing. Job 2, under each grader:
+
+| Bot | 0928 grader | 4a grader |
+|---|---|---|
+| Own lines, first word cut | 147 of 177 = 0.8305 | 0 of 177 |
+| Own lines, first 2 words cut | 147 of 177 = 0.8305 | 0 of 177 |
+| Own lines, first 2 words swapped | 153 of 177 = 0.8644 | 0 of 177 |
+| Hedge: the cause, then a decoy | 32 of 177 = 0.1808 | 61 of 177 = 0.3446 |
+| Gold reply | 177 of 177 | 177 of 177 |
+| Gold reply with the registry host | 148 of 177 = 0.8362 | 177 of 177 |
+| Own keywords, pasted | 177 of 177 | 177 of 177 (reads the new keys) |
+| Own keywords, old `init` keys | 177 of 177 | 165 of 177 = 0.9322 |
+
+The hedge bot gains 29 workloads. They are the bad-tag rows whose first
+decoy is the 2-word registry decoy, which G2 now skips. That is the cost
+of closing known limit 12, and the bot stays far under the 0.7 bar. The
+last row is a reply built from the two init bad-tag keys as they were,
+without `init`: the exam's 12 workloads on those keys lose their point.
+
+**Weak keywords.** On the 0928 exam, 34 pairs of answer keys had one
+story's gold answer pass a different story's key. The must-not words and
+the new `init` word take that to 21. A test pins the 21 exactly, so a
+change that adds a pair fails it. All 21 are left for Spec 4b. 8 are on
+`node-cordon-diskfull`'s key, `node` and `pod` (see known limit 10). The
+other 13 involve the shared-origin keys, which 4b rewrites.
+
+**What this changes:** nothing in the plan. Job 2's 0.8023 is the
+baseline under the new grader. Next come Spec 4b, then 0920 live again,
+then the retrain.
+
 ## Known limits of the training data and the exam
 
 These are known limits of the training data and the exam this build uses.
@@ -991,6 +1059,17 @@ against these.
     `test_a_trimmed_paste_clears_the_job2_bar_a_known_gap_in_the_guard`).
     A stronger G3b changes the grader, so it needs a change to the spec.
     A later design (Spec 4) owns it.
+
+    (2026-09-29, Spec 4a: closed for cut pastes. G3b now also zeroes an
+    answer that holds an own line with its first 1 or 2 words cut, as
+    long as 3 words are left. The bot above scores 0 of 177, and so do
+    two more: first 2 words cut, and first 2 words swapped. The test is
+    now `test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut`.
+    One kind of copy still passes, and it has to: a single clause lifted
+    out of the middle of a printed line. 0920 wrote 5 right answers this
+    way. A rule that zeroes such a clause would zero gold answers too,
+    because 17 gold sentences are printed in their own prompts. On those
+    rows job 2 cannot tell reading from copying.)
 12. **A right bad-image-tag answer scores 0 if it names the registry
     host.** (Added 2026-09-28.) The bad-image-tag rows print the
     candidate `registry registry.example.com` and rule it out, so it is
@@ -1008,3 +1087,12 @@ against these.
     `test_a_right_bad_tag_answer_that_names_the_registry_host_is_zeroed_by_g2`).
     A narrower G2 changes the grader, so it needs a change to the spec. A
     later design (Spec 4) owns it.
+
+    (2026-09-29, Spec 4a: closed. G2 now skips a decoy under 3 words.
+    `registry registry.example.com` is 2 words, and it is the only exam
+    decoy that short. The gold reply with the host scores 177 of 177. The
+    test is now
+    `test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2`.
+    The cost: a hedge that names the cause and that decoy passes too. The
+    hedge bot goes from 32 to 61 of 177 = 0.3446, still under the 0.7
+    bar.)
```

- [ ] **Step 7: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `1547 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add contract/PIN.md docs/model-card.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
docs: record Spec 4a's bank, gate and 0920 replay

The bank is rebuilt with the same seed and size into
out/dataset-0929. A row-by-row check against out/dataset-0928 found no
message change on any of the 7,427 rows, and meta changes only where
they were planned: own_cause_must_not on every workload, and init in
the two init bad-tag keys.

contract/PIN.md records the new bank hashes, the three test hashes,
the bots before and after, and splits the 2026-09-28 "Left for Spec 4"
list into what 4a did and what is left for 4b.

docs/model-card.md adds 0920 re-scored under the new grader, with no
model call: job 1 0.95, job 2 142 of 177 = 0.8023, job 3 0.875. Job 2
loses only the two wrong memory-request answers the old keys graded
right. It also closes limits 11 and 12 and updates the weak-key note,
34 pairs down to 21.
EOF
```

Then `git status --short` must list nothing from this task: both files are committed. `.gitignore` and `train-v2.log` may show; leave them. `out/` is gitignored, so the new bank and replay do not show.
