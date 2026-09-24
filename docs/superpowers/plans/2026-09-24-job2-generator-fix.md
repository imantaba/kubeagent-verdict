# Job-2 Generator Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every job-2 prompt one that kubeagent could send, with one
answer per prompt. Today `none_of_these` and `wrong_attribution` build the
same bytes for 27 of 28 catalogue entries and give them opposite answers,
so no model can learn to override a wrong `attributed` tag.

**Architecture:** Nine tasks, each one commit, in dependency order.

1. The grader's diagnostics count job 2 the way `job2()` does.
2. `render.header_for` ports kubeagent's confidence rule.
3. Two catalogue fixes: the doubled `log cause: ` prefix and restart-loop's
   unquoted container.
4. `cases._log_read` builds kubeagent's previous-log read.
5. One builder, `_undecided_example`, makes every undecided job-2 row.
6. The case mix moves 7 points from `none_of_these` to the clear cases.
7. `multi` keeps its crash-family log reads and prints its header by rule.
8. `empty_candidates` answers at the entry's own confidence and keeps its
   log read.
9. The docs, then a dataset regeneration that proves the banked exam is what
   the code builds.

**Tech Stack:** Python 3, pytest, ruff. No new dependency. No cluster, no
model call, no training host.

**Spec:** [docs/superpowers/specs/2026-09-24-job2-generator-fix-design.md](../specs/2026-09-24-job2-generator-fix-design.md)
(commit `e4b0053`). Read it before Task 1. This plan argues from it and
does not restate its reasoning.

## How the code in this plan was made

Each task's code is two `diff` blocks: the tests first, then the source.
They were cut from a prototype branch built on `e4b0053`, one commit per
task. For every task:

- the task's tests, run against the commit before it, failed with exactly
  the list in Step 2;
- the full suite and ruff passed on the task's commit.

So the diffs are exact. Apply them with `git apply`. Do not retype them.
Read both blocks before you apply them: you own the change, and the review
will ask you to explain it.

Every task's Step 1 shows the same extraction. It cuts diff block `k` out of
your brief file, `.superpowers/sdd/2026-09-24-job2-generator-fix/task-<N>-brief.md`.
If that file does not exist (you are working from the plan, not from a
brief), the first line of Step 1 makes it from the plan.

## Global Constraints

- **Where:** the checkout at `/home/ubuntu/git/kubeagent-verdict`, branch
  `spec-wrong-attribution-generator`. Never commit to `main`. Start every
  command with `cd /home/ubuntu/git/kubeagent-verdict &&` (or run it from
  there).
- **Python:** `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider …`.
  The venv's editable install points at this checkout's `src/`;
  `PYTHONPATH=src` makes that true in any worktree too.
- **ruff:** `.venv/bin/ruff check --ignore EXE002 .` must print
  `All checks passed!` on every commit. `EXE002` is noise from stale mode
  bits (next item): 67 of them at `e4b0053`, and the count can only fall.
- **Stale mode bits.** 109 tracked files in this checkout show as modified
  only because their mode changed. 12 of the files this plan touches are
  among them. So:
  - use `git -c core.fileMode=false` for `apply`, `add` and `commit`;
  - never `git add -A` or `git add .` — name each file;
  - `git apply` may write a file back as `644`. That is expected and fine.
- **If `git apply --check` fails, STOP and report.** Do not hand-edit
  around it.
- **If a measured value differs from this plan, STOP and report.** Do not
  paste your value in. Every count, hash and failure list below was
  observed on the prototype.
- **No bar moves.** `JOB1_BAR = 0.9`, `JOB2_BAR = 0.7`, `JOB3_BAR = 0.9`
  in `src/kubeagent_verdict/evals/score.py` keep their values.
- **Never run a test with `-update`.** Every pinned value in the diffs was
  written by hand with a dated comment.
- **TDD.** Apply the tests, watch them fail with the listed failures, then
  apply the source.
- **Commits:** each task's last step holds the exact command:
  `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F -`,
  with the message on standard input. No AI attribution of any kind: no
  `Co-Authored-By` trailer, no "generated with" line. No commit message
  names a plan task number or a `docs/testing/` path.
- **Read-only elsewhere.** The kubeagent repository is read-only. Nothing
  writes under `dist/`. No tracked file names the training host or any
  real identifier; the diffs use only the generator's own names
  (`worker-1`…`worker-7`, `registry.invalid`, …).

## Rulings

Places where this plan departs from the spec's letter, or settles what the
spec left open. Each was measured on the prototype. Do not re-open them.

1. **`_undecided_example` takes no `rng`.** Spec section 2 writes the
   signature with `rng`. But the same section forbids a shuffle, and every
   entry declares at most two objects, already in gather order. Nothing is
   drawn, so an `rng` parameter would be a promise the code does not keep.
   The builder and its four wrappers take none, and `generate.py` stops
   passing one (Task 5). Cost: `generate()` shares one `rng` across all
   cases, so removing draws shifts every later draw, and every train and
   val count moves. The exam uses a keyed `rng` per entry, so it moves only
   where the spec says.
2. **Meta stays per case.** The prompt never depends on `case`; the meta
   does, as today. `expected_own_keywords` is set only on `own_cause`. The
   `_row_decoy` keys are set only on `wrong_attribution` and
   `misattribution_probe`. Spec section 2: "`case` names the example and
   its meta."
3. **No read budget in the builder.** An undecided row has at most 2 object
   reads and 1 log read. `apply_budget` could never cut, so it is not
   called. Only `multi` can pass 8 reads (Task 7).
4. **An empty evidence section is a real row.** Spec section 2, "A known
   consequence": a ruled-out row outside the crash family has no reads and
   renders `(none)`. `tests/test_evidence_overlap.py`'s `_reads` used to
   refuse that shape; it now returns `[]` for it (Task 5).
5. **The eval-only reuse allowlist moves twice.** `DECLARED` in
   `tests/test_evidence_overlap.py`: `misattribution_probe` goes
   `(14, 20)` → `(5, 5)` in Task 5 (its describe reads are gone), and
   `multi_misattribution_probe` goes `(39, 40)` → `(47, 48)` in Task 7 (it
   gains log reads that crash-family training rows also carry).
   `contradiction_probe` stays `(19, 38)`; only its comment changes.
6. **The restart-loop citation is `restartloop.go:47`.** The spec's table
   says `:44`. At kubeagent v1.24.0 the `Evidence` format string is on
   line 47. The test in Task 3 cites `:47`.
7. **The header test exempts the four shared-origin cases.** The spec's
   success criteria say every job-2 header equals kubeagent's rule. Its
   "Out of scope" says the shared-origin builders are not touched, and
   they hand-pass their header. Scope wins. Task 7's test exempts
   `shared_origin`, `shared_origin_decoy`, `shared_origin_probe` and
   `shared_origin_decoy_probe` by name. The gap is reported, not fixed.
8. **`multi`'s numbers were re-measured.** Spec section 6 gives 3,160
   blocks, 836 crash-family, 780 losses, 125 over-cap rows and 33 cut log
   reads. After Task 6's mix change they are 3,157, 847, 784, 127 and 34.
   The rule is unchanged. Task 7's docstrings carry 847, 784 and 34. Task
   9's `docs/design.md` carries 3,157. 127 is recorded here only.
9. **Task 1's rewrite test retires a fourth number: the length decider.**
   `test_rewriting_the_job2_answer_keys_…` measures which banked numbers
   a rewrite of job 2's answer keys would move. `wrong_attribution` and
   `misattribution_probe` rows carry a decoy, so they carry a length
   verdict. Once cause accuracy grades job 2 per workload, their cause is
   keyword-graded: 38 of the 56 "length helps" rows. So the rewrite now
   moves the length decider too. For the test's keyword bot,
   `cause_when_length_helps` goes 0.6786 → 0.0 (n = 56), and so does
   `length_gap`. It is a diagnostic, not a gate. The test is renamed from
   `…retires_three_numbers…` to `…retires_four_numbers…`.
10. **The paste-the-prompt guard still holds.** The spec says to stop if it
    fails. On the new exam the paste bot scores 76/142 = 0.5352 on job 2,
    below `JOB2_BAR` (0.7). Task 5 pins it.
11. **The prompt-stability test skips from Task 3 to Task 9.** Task 3
    changes prompts, so the test is re-pointed at the new bank,
    `out/dataset-0924`. That bank does not exist until Task 9 builds it.
    Its 2 tests skip in between. That is expected.
12. **`tests/test_multi_collision.py`'s pins move in Task 6.** They count
    real rows at build size, and the mix change moves them.
13. **`docs/design.md`'s "~55% of the mix" is left alone.** It was already
    stale before this branch, and this branch does not change the rows it
    sums.

## The pins that move

The three hashes, by the commit that moves them. Tasks 1, 2, 4, 6 and 9
move none. `FROZEN_253_SHA256` is renamed `FROZEN_SLICE_SHA256` in Task 3.

| After | `GRADED_VIEW_SHA256` | `FROZEN_SLICE_SHA256` | `EVAL_SET_SHA256` |
|---|---|---|---|
| `e4b0053` | `b82b87977414e01e5d58eeb64defc5dec350bab6f567006d02ea96932700b03e` | `2532b7908adfc91f22c56710eb5f9e47e500b4060460ae7de373a003afed1bc9` | `d40dabc9fafec54a46398a13e7e984a965824d550399c09c60c7fc848e9a3288` |
| Task 3 | `100ec57cebcc2d8c25c62466116e7886a2689faea071f25d6e47acecbf76412d` | `1aead0803e798d40fa535300177e5156883c908e4e790255ee685f132da554fa` | `6e1f553be2956b2b5a1217632b4787027875fb3b4c1335f5fcf1e4bc96327ad3` |
| Task 5 | `046bf2b87b20aa20ebb79ca6ee199a47d9f8f54e25f42df76894033df09063a5` | `b6f61e68c7615288452b48935031b649f502e21c1fad3ba7c7d7a96f11758294` | `ae4e0885d6b0ea705b77794781dd0c4fed37fbb5b32969ab484c2d0564db8c34` |
| Task 7 | `74f55a1d64eaeb5fec11d5b871ac69b93dfc4d60700936843477a6e7063a4a81` | `b3c5c98a8084183e3c141647c757d294b6776895efd721c35f4e45116060e5f2` | `a8ecb21ddbc2f3fc2fde7620c7a8df9fd0213be9a6747a6b7966c1fcea87e2ac` |
| Task 8 | `250f2bc2bc6860ec5e04e9574e36b8cf23cea2625961b735bb1a0888914d5b18` | `aff7cc96aaec86bf7ce7d972632966a2c770adcde9facd4c8ef2b427f2f8c490` | `97a89e93fc5fdfdfebd0689fb5b74e060b68ba6879236ca12533e33a4ecb9c81` |

The diffs write these values. The table is here so a reviewer can check a
hash without reading the tests.

## Full-suite counts

This checkout holds `out/dataset-0920` (the old bank) and, until Task 9,
no `out/dataset-0924`. So the 2 prompt-stability tests run in Tasks 1-2,
skip in Tasks 3-8, and run again after Task 9's regeneration.

| After | Full suite |
|---|---|
| `e4b0053` (before Task 1) | 821 passed |
| Task 1 | 824 passed |
| Task 2 | 833 passed |
| Task 3 | 834 passed, 2 skipped |
| Task 4 | 853 passed, 2 skipped |
| Task 5 | 906 passed, 2 skipped |
| Task 6 | 907 passed, 2 skipped |
| Task 7 | 910 passed, 2 skipped |
| Task 8 | 911 passed, 2 skipped |
| Task 9, before the regeneration | 911 passed, 2 skipped |
| Task 9, after the regeneration | 913 passed |

"6 warnings" also prints on every run. They are pre-existing.

## What comes after this plan

Not tasks here. They follow the merge, in the spec's run order:

1. Run the 0920 model on the new exam, live, with `--endpoint`.
2. Merge, push, and pull on the training host.
3. Retrain, export, serve locally, run `kv-eval --endpoint`.
4. Write the new baseline and the model-card sections.

---

### Task 1: Grade cause accuracy on job 2's own population

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py` (remove `KEYWORD_CASES` and `_is_keyword_graded`; change how `evaluate` grades a row's cause; update two comments)
- Test: `tests/test_score.py`, `tests/test_generate.py` (one docstring)

**Interfaces:**
- Consumes: nothing from this plan.
- Produces: `score.evaluate` grades each row's cause per workload, by the
  rule `job2()` already uses. A workload whose meta has `job == 2` and
  passes the existing `_is_job2_keyword_graded(wm, keywords)` is graded by
  keyword containment: every keyword in `wm["own_cause_keywords"]`,
  lower-cased, must appear in the reply's `cause`. Every other workload is
  graded by exact match. `score.KEYWORD_CASES` and
  `score._is_keyword_graded` no longer exist. Tasks 5 to 8 change which
  cases carry keywords; this rule follows them with no further edit.

**Why (spec section 7):** the row-level cause diagnostics use keywords on
two case names only, `own_cause` and `empty_candidates`. After Task 5,
`wrong_attribution` and `misattribution_probe` answer a free-text cause
too, and exact match would mark every right answer wrong. No bar and no
gate changes. Ruling 9 covers the renamed rewrite test.

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

9. **Task 1's rewrite test retires a fourth number: the length decider.**
   `test_rewriting_the_job2_answer_keys_…` measures which banked numbers
   a rewrite of job 2's answer keys would move. `wrong_attribution` and
   `misattribution_probe` rows carry a decoy, so they carry a length
   verdict. Once cause accuracy grades job 2 per workload, their cause is
   keyword-graded: 38 of the 56 "length helps" rows. So the rewrite now
   moves the length decider too. For the test's keyword bot,
   `cause_when_length_helps` goes 0.6786 → 0.0 (n = 56), and so does
   `length_gap`. It is a diagnostic, not a gate. The test is renamed from
   `…retires_three_numbers…` to `…retires_four_numbers…`.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-1
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=1 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_generate.py b/tests/test_generate.py
index 683c7f6..3a2d7d7 100644
--- a/tests/test_generate.py
+++ b/tests/test_generate.py
@@ -325,8 +325,8 @@ def test_the_job2_keyword_exposure_is_pinned_per_case():
     deliberately with the reason, never tuned back to a stale value.
 
     The population moved for the v1.24.0 rescope. It used to be the retired
-    `cause_acc` slice -- the two case names in `score.KEYWORD_CASES`, counted
-    once per row -- which read 19 of 38. Design spec line 547 asks for all of
+    `cause_acc` slice -- two case names, `own_cause` and `empty_candidates`,
+    counted once per row -- which read 19 of 38. Design spec line 547 asks for all of
     job 2 instead, which is one entry per undecided workload that carries
     keywords, and adds three more cases: `wrong_attribution`,
     `misattribution_probe` and `multi_misattribution_probe`.
diff --git a/tests/test_score.py b/tests/test_score.py
index 5bb18b6..f59e4df 100644
--- a/tests/test_score.py
+++ b/tests/test_score.py
@@ -1166,6 +1166,8 @@ def test_a_prompt_with_no_suggestion_line_is_not_measured():
 # rescope fix it counted the retired `cause_acc` slice instead -- the two case
 # names in `KEYWORD_CASES`, at the row level -- and printed 19 of 38 where the
 # spec's population was 56 of 114 (76 of 134 since the 2026-09-23 grader fix).
+# Since the 2026-09-24 generator fix `KEYWORD_CASES` is gone: the row-level
+# cause diagnostics grade by the same per-workload rule as job 2.
 #
 # It measures the corpus, not the model. Every test below therefore holds the
 # row fixed and varies nothing about the answer, except the one that varies
@@ -1270,17 +1272,55 @@ def test_a_decided_workload_is_out_of_the_denominator():
 def test_the_population_does_not_depend_on_the_case_name():
     """The retired `cause_acc` slice gated on `KEYWORD_CASES`, two case names.
     job 2 does not: it grades by keyword wherever a workload carries keywords
-    and does not expect `none_of_these`. A case outside `KEYWORD_CASES` --
+    and does not expect `none_of_these`. A case outside those two names --
     `wrong_attribution` and `multi_misattribution_probe` are two real ones --
-    is measured here, which is where the extra 76 workloads come from."""
+    is measured here, which is where the extra 76 workloads come from.
+
+    Since the 2026-09-24 generator fix the case-name list itself is gone, so
+    nothing in the grader can pick the population by case name again."""
     row = _keyword_row("the memory limit was exceeded", ["memory", "limit"],
                        case="wrong_attribution")
-    assert "wrong_attribution" not in score.KEYWORD_CASES
+    assert not hasattr(score, "KEYWORD_CASES")
+    assert not hasattr(score, "_is_keyword_graded")
     board = score.scoreboard(score.evaluate([row], lambda m: _answer()))
     assert board["overall"]["keyword_graded_n"] == 1
     assert board["overall"]["keyword_derivable_n"] == 1
 
 
+def test_cause_accuracy_grades_a_job2_workload_by_its_keywords_on_any_case():
+    """The row-level cause diagnostic grades a job-2 workload the way `job2`
+    does: by its own keywords, whatever the row's case is called.
+
+    Before the 2026-09-24 generator fix only `own_cause` and
+    `empty_candidates` rows were keyword-graded here, so a right own-cause
+    answer on `wrong_attribution` -- the answer `job2` scores 1.0 -- counted
+    as wrong in `cause_acc`."""
+    row = _keyword_row("the container exited", ["memory", "limit"],
+                       case="wrong_attribution")
+    results = score.evaluate([row], lambda m: _answer())
+    assert results[0]["job2_scores"] == [1.0]
+    assert results[0]["cause_acc"] == 1.0
+
+
+def test_cause_accuracy_exact_matches_a_none_of_these_workload():
+    """A `none_of_these` workload is exact-matched, here and in `job2`, even
+    when its meta carries keywords: a reply that holds every keyword but
+    names a cause scores 0 on both, and `none_of_these` itself scores 1."""
+    row = _keyword_row("the container exited", ["memory", "limit"],
+                       case="none_of_these")
+    row["meta"]["workloads"]["shop/api"]["expected_cause"] = NONE_OF_THESE
+    row["messages"][2]["content"] = json.dumps({
+        "verdicts": [{"workload": "shop/api", "cause": NONE_OF_THESE,
+                      "confidence": "low", "rationale": "r"}],
+        "summary": "s"})
+    named = score.evaluate([row], lambda m: _answer())
+    assert named[0]["job2_scores"] == [0.0]
+    assert named[0]["cause_acc"] == 0.0
+    abstained = score.evaluate([row], lambda m: _answer(NONE_OF_THESE))
+    assert abstained[0]["job2_scores"] == [1.0]
+    assert abstained[0]["cause_acc"] == 1.0
+
+
 def test_exposure_does_not_move_with_the_model_answer():
     """The discriminating test for option C: this measures the CORPUS. A row
     the model refused, answered wrongly, or answered perfectly reports the
@@ -2085,40 +2125,49 @@ def _own_keyword_bot(rows: list[dict]):
     return chat_fn
 
 
-def _rewrite_keyword_answer_keys(rows: list[dict], token: str) -> tuple[list[dict], int, int]:
+def test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row():
+    """The row-level cause diagnostic grades exactly job 2's keyword-graded
+    population, checked over the whole exam rather than one fixture.
+
+    On a row whose every workload is job 2, `cause_acc` and the mean of the
+    row's `job2_scores` grade the same workloads by the same rule, so they
+    must agree for any reply. The own-keyword bot is a reply that tells them
+    apart when they do not: before the 2026-09-24 generator fix it disagreed
+    on 64 of these 121 rows, every `wrong_attribution`,
+    `misattribution_probe`, `multi_misattribution_probe` and shared-origin
+    probe row among them."""
+    rows = _corpus_rows()
+    results = score.evaluate(rows, _own_keyword_bot(rows))
+    checked = 0
+    for row, res in zip(rows, results):
+        workloads = list(row["meta"]["workloads"].values())
+        if not workloads or any(wm.get("job") != 2 for wm in workloads):
+            continue
+        checked += 1
+        assert res["cause_acc"] == pytest.approx(
+            sum(res["job2_scores"]) / len(res["job2_scores"])), row["meta"]["case"]
+    assert checked == 121
+
+
+def _rewrite_keyword_answer_keys(rows: list[dict], token: str) -> tuple[list[dict], int]:
     """Rewrites every job-2 keyword answer key to a word no prompt contains.
 
     The catalog stores each entry's `own_cause_keywords` once and the row
-    builders copy it into two places: `meta["expected_own_keywords"]` on the
-    `own_cause` and `empty_candidates` rows, which is what `evaluate` grades
-    `cause_acc` by, and `meta["workloads"][name]["own_cause_keywords"]` on
-    every keyword-graded job-2 workload, which is what `job2` grades by. A
-    real rewrite edits the catalog and moves both, so this moves both.
+    builders copy it onto every keyword-graded job-2 workload,
+    `meta["workloads"][name]["own_cause_keywords"]`. Since the 2026-09-24
+    generator fix that one key is what both `job2` and `evaluate`'s cause
+    diagnostics grade by. The row-level `meta["expected_own_keywords"]` copy
+    on `own_cause` and `empty_candidates` rows is no longer read by the
+    grader, so this leaves it alone.
     """
     rewritten = copy.deepcopy(rows)
-    row_level = workload_level = 0
+    workload_level = 0
     for row in rewritten:
-        if score._is_keyword_graded(row["meta"]):
-            row["meta"]["expected_own_keywords"] = [token]
-            row_level += 1
         for wm in row["meta"]["workloads"].values():
             if isinstance(wm, dict) and wm.get("job") == 2 and wm.get("own_cause_keywords"):
                 wm["own_cause_keywords"] = [token]
                 workload_level += 1
-    return rewritten, row_level, workload_level
-
-
-def _every_keyword_graded_row_has_no_length_verdict(rows: list[dict]) -> bool:
-    """Whether no keyword-graded row carries a `length_helps` verdict.
-
-    This is why a keyword rewrite cannot move `length_gap`. `evaluate` sets
-    `length_helps` only on a row that has a decoy cause to compare against,
-    and neither `own_cause` nor `empty_candidates` has one.
-    """
-    results = score.evaluate(rows, lambda messages: "")
-    return all(res["length_helps"] is None
-               for row, res in zip(rows, results)
-               if score._is_keyword_graded(row["meta"]))
+    return rewritten, workload_level
 
 
 def test_the_exposed_workloads_trace_back_to_eleven_catalog_entries():
@@ -2190,14 +2239,23 @@ def test_the_exposed_workloads_trace_back_to_eleven_catalog_entries():
     assert n_fully + n_partly < board["overall"]["keyword_derivable_n"]
 
 
-def test_rewriting_the_job2_answer_keys_retires_three_numbers_and_spares_the_rest():
-    """Closing job 2's keyword exposure costs three banked numbers, not one.
+def test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest():
+    """Closing job 2's keyword exposure costs four banked numbers, not one.
 
     `docs/model-card.md` limit 7 names rewriting the answer keys as the way
     to close the exposure, so the price of that rewrite belongs next to it
-    as a measurement. `score.py`'s own comment above `_is_keyword_graded`
-    states the coupling -- a rewrite "makes every historical score on those
-    two slices incomparable" -- and this pins which numbers that is.
+    as a measurement. `score.py`'s comment above `_keyword_exposure` states
+    the coupling -- a rewrite "makes every historical job-2 score
+    incomparable" -- and this pins which numbers that is.
+
+    Re-pinned on 2026-09-24 for the job-2 generator fix
+    (2026-09-24-job2-generator-fix-design.md). The cause diagnostics now
+    grade by job 2's own per-workload rule instead of two case names, and
+    that adds a fourth number: the length decider. `wrong_attribution` and
+    `misattribution_probe` rows carry a decoy, so they carry a length
+    verdict, and their cause is now keyword-graded -- 38 of the 56
+    `length helps` rows. The paragraphs below are the 2026-09-23 account;
+    where they say `length_gap` does not move, that held until this fix.
 
     Three move: job 2, because it grades by keyword containment; cause
     accuracy, because the `own_cause` and `empty_candidates` rows are graded
@@ -2252,10 +2310,10 @@ def test_rewriting_the_job2_answer_keys_retires_three_numbers_and_spares_the_res
     """
     rows = _corpus_rows()
     bot = _own_keyword_bot(rows)          # replies pinned to today's keys
-    rewritten, row_level, workload_level = _rewrite_keyword_answer_keys(
+    rewritten, workload_level = _rewrite_keyword_answer_keys(
         rows, "nonexistentkeywordtoken")
 
-    assert (row_level, workload_level) == (38, 134)
+    assert workload_level == 134
 
     before = score.scoreboard(score.evaluate(rows, bot))
     after = score.scoreboard(score.evaluate(rewritten, bot))
@@ -2265,24 +2323,25 @@ def test_rewriting_the_job2_answer_keys_retires_three_numbers_and_spares_the_res
     assert after["overall"]["keyword_derivable_n"] == 0
     assert after["overall"]["keyword_graded_n"] == 134
 
-    # Three numbers retire: the same replies now score differently.
+    # Four numbers retire: the same replies now score differently.
     assert before["jobs"]["job2"]["rate"] == pytest.approx(1.0, abs=0.005)
     assert after["jobs"]["job2"]["rate"] == pytest.approx(0.1242, abs=0.005)
-    assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.289, abs=0.005)
+    assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.5387, abs=0.005)
     assert after["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.1445, abs=0.005)
-    assert before["overall"]["overconfidence_rate"]["n"] == 187
+    assert before["overall"]["overconfidence_rate"]["n"] == 123
     assert after["overall"]["overconfidence_rate"]["n"] == 225
-
-    # Everything else is untouched, including length_gap.
-    assert _every_keyword_graded_row_has_no_length_verdict(rows)
-    for field in ("length_gap", "cause_when_length_helps", "cause_when_length_misleads",
-                  "contract_rate", "decoy_rate", "suggestion_echo_rate",
-                  "injection_echo_rate", "confidence_carried"):
+    assert before["overall"]["cause_when_length_helps"] == {"rate": 0.6786, "n": 56}
+    assert after["overall"]["cause_when_length_helps"] == {"rate": 0.0, "n": 56}
+    assert before["overall"]["length_gap"] == pytest.approx(0.6786, abs=0.005)
+    assert after["overall"]["length_gap"] == pytest.approx(0.0, abs=0.005)
+
+    # Everything else is untouched.
+    for field in ("cause_when_length_misleads", "contract_rate", "decoy_rate",
+                  "suggestion_echo_rate", "injection_echo_rate", "confidence_carried"):
         assert before["overall"][field] == after["overall"][field], field
     for job in ("job1", "job3"):
         assert before["jobs"][job] == after["jobs"][job], job
     assert before["overall"]["n"] == after["overall"]["n"]
-    assert before["overall"]["length_gap_ok"] == after["overall"]["length_gap_ok"]
 
     # Every per-case block is accounted for, so "spares the rest" is a
     # measurement rather than a claim about the fields this test happened to
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_generate.py tests/test_score.py
```

Expected: the summary line reads `4 failed, 191 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_score.py::test_the_population_does_not_depend_on_the_case_name
FAILED tests/test_score.py::test_cause_accuracy_grades_a_job2_workload_by_its_keywords_on_any_case
FAILED tests/test_score.py::test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row
FAILED tests/test_score.py::test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-1
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=1 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/evals/score.py b/src/kubeagent_verdict/evals/score.py
index 1ac1018..0a53c0b 100644
--- a/src/kubeagent_verdict/evals/score.py
+++ b/src/kubeagent_verdict/evals/score.py
@@ -13,8 +13,6 @@ import re
 from kubeagent_verdict.contract import NONE_OF_THESE, TRUNCATION_MARKER
 from kubeagent_verdict.evals.contract_check import contract_check
 
-KEYWORD_CASES = {"own_cause", "empty_candidates"}
-
 # The top of the three-grade vocabulary the catalog emits (high/medium/low).
 HIGHEST_CONFIDENCE = "high"
 
@@ -180,9 +178,10 @@ def _is_job2_keyword_graded(meta_workload: dict,
     """Whether `job2` grades this workload by keyword containment.
 
     The ONE definition of that population. `job2` calls it to choose the
-    grading rule and `_keyword_exposure` calls it to choose whom to measure,
-    so the footnote's denominator IS the grader's population rather than a
-    second hand-written copy of the same condition. A `none_of_these`
+    grading rule, `evaluate` calls it to grade the row-level cause
+    diagnostics the same way, and `_keyword_exposure` calls it to choose whom
+    to measure, so the footnote's denominator IS the grader's population
+    rather than a second hand-written copy of the same condition. A `none_of_these`
     workload is graded by exact match against that one string; a named-cause
     workload with no keywords is refused by `job2` (`UngradableWorkload`)
     rather than scored, so it is excluded from this population the same way
@@ -411,13 +410,13 @@ def _norm_cause(s: str) -> str:
     return " ".join(str(s).lower().strip().rstrip(".").split())
 
 
-# The `own_cause` and `empty_candidates` slices are graded by keyword
-# containment rather than exact match, which is the right rule for slices whose
-# answer is not a menu selection and also the loosest rule on the board. This
-# measures how much of that looseness the CORPUS hands over for free: on a row
-# where every expected keyword is already printed in the prompt, a cause string
-# assembled from words on screen grades as correct, so the slice cannot separate
-# "read the evidence and concluded" from "restated the evidence".
+# Job 2 grades most of its workloads by keyword containment rather than exact
+# match -- the right rule for an answer that is not a menu selection, and also
+# the loosest rule on the board. `_keyword_exposure` measures how much of that
+# looseness the CORPUS hands over for free: on a workload where every expected
+# keyword is already printed in the prompt, a cause string assembled from words
+# on screen grades as correct, so the grader cannot separate "read the evidence
+# and concluded" from "restated the evidence".
 #
 # It is a diagnostic, not a score, and the distinction is load-bearing. It
 # measures the corpus rather than the model — the model's output is not an input
@@ -426,23 +425,11 @@ def _norm_cause(s: str) -> str:
 # model exploited the looseness; it is a claim that the looseness is there to
 # exploit, printed where whoever reads the release bar will see it.
 #
-# The real fix is a keyword the prompt does not contain, on every keyword row.
-# That rewrites 38 answer keys and makes every historical score on those two
-# slices incomparable, so it waits for evidence a model is actually clearing the
-# slice while failing elsewhere. This number is what would supply that evidence.
-def _is_keyword_graded(meta: dict) -> bool:
-    """Whether this row is graded by keyword containment rather than exact match.
-
-    The ONE definition of that population. `evaluate` calls it to choose the
-    grading rule and `_keyword_derivable` calls it to choose whom to measure,
-    so the diagnostic's denominator IS the grader's population rather than a
-    second hand-written copy of the same condition -- which is what a claim
-    that the two cannot drift has to rest on. A shared predicate makes it true
-    structurally; `test_the_keyword_graded_population_is_the_measured_population`
-    keeps it true when a call site is edited instead of the predicate.
-    """
-    return bool(meta.get("case") in KEYWORD_CASES
-                and meta.get("expected_own_keywords"))
+# The real fix is a keyword the prompt does not contain, on every keyword-graded
+# workload. That rewrites the catalog's answer keys and makes every historical
+# job-2 score incomparable, so it waits for evidence a model is actually
+# clearing job 2 while failing elsewhere. This number is what would supply that
+# evidence.
 
 
 def _keyword_exposure(meta: dict, prompt: str) -> tuple[int, int]:
@@ -450,10 +437,9 @@ def _keyword_exposure(meta: dict, prompt: str) -> tuple[int, int]:
 
     Counted per WORKLOAD, not per row: design spec line 547 prints this "over
     all job-2 rows", and job 2 scores one workload at a time. Before the
-    v1.24.0 rescope fix this counted the retired `cause_acc` slice instead --
-    the two case names in `KEYWORD_CASES`, once per row -- and printed 19 of
-    38 where job 2's own population was 56 of 114 (76 of 134 since the
-    2026-09-23 grader fix).
+    v1.24.0 rescope fix this counted two case names, `own_cause` and
+    `empty_candidates`, once per row -- and printed 19 of 38 where job 2's own
+    population was 56 of 114 (76 of 134 since the 2026-09-23 grader fix).
 
     Whom to measure comes from `_is_job2_keyword_graded` -- the same predicate
     `job2` grades by, handed the same keyword list `evaluate` hands `job2` --
@@ -528,9 +514,14 @@ def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict
             got = by_workload.get(exp["workload"])
             if not got:
                 continue
-            if _is_keyword_graded(meta):
-                kws = [k.lower() for k in meta["expected_own_keywords"]]
-                matched = all(k in str(got.get("cause", "")).lower() for k in kws)
+            # The same per-workload population `job2` grades by keyword, so a
+            # right own-cause answer counts here on every case that carries
+            # one, not only on the two cases that used to be named.
+            wm = (meta.get("workloads") or {}).get(exp["workload"]) or {}
+            keywords = wm.get("own_cause_keywords") or []
+            if wm.get("job") == 2 and _is_job2_keyword_graded(wm, keywords):
+                matched = all(str(k).lower() in str(got.get("cause", "")).lower()
+                              for k in keywords)
             else:
                 matched = got.get("cause") == exp["cause"]
             if matched:
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `824 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_generate.py tests/test_score.py src/kubeagent_verdict/evals/score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(evals): grade cause accuracy on job 2's own per-workload population

The row-level cause diagnostics graded by keyword on two case names
only, own_cause and empty_candidates. job2() already grades per
workload. Use the same rule here, so a right free-text answer counts on
every case that carries keywords, and keeps counting when a case starts
to carry them.

KEYWORD_CASES and _is_keyword_graded go. No bar and no gate changes.

The answer-key rewrite test now retires four numbers, not three: the
length decider moves too, because 38 of its 56 "length helps" rows are
now keyword-graded.
EOF
```

### Task 2: Print the job-2 header by kubeagent's confidence rule

**Files:**
- Modify: `src/kubeagent_verdict/dataset/render.py` (add `header_for` and `_HEADER_BY_PREFIX`; export `header_for`; `render_workload` sets the header)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: nothing from this plan.
- Produces: `render.header_for(candidates: tuple[c.Candidate, ...]) -> str`.
  It looks at the one candidate whose `verdict == "attributed"` and returns
  `"high"` if its cause starts with `node ` or `PVC `, `"medium"` if it
  starts with `registry `, and `""` otherwise. No attributed candidate
  gives `""`. Two or more raise `ValueError`. It is in `render.__all__`.
  `render.render_workload` now fills `Workload.confidence` from it.
  Tasks 5 and 7 call it.

**Why (spec section 1):** kubeagent prints `[confidence: …]` over a trace
from `confidence.ForRootCause`, which reads only the attributed cause's
prefix (`internal/confidence/confidence.go:36-47` at v1.24.0). Today the
generator hand-passes a header per case, and some cases pass one kubeagent
would never print. No pinned hash moves in this task.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-2
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=2 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_render.py b/tests/test_render.py
index d1c580f..8d7fd11 100644
--- a/tests/test_render.py
+++ b/tests/test_render.py
@@ -8,6 +8,9 @@ frozen hash.
 
 import random
 
+import pytest
+
+from kubeagent_verdict import contract as c
 from kubeagent_verdict.dataset import objects as o
 from kubeagent_verdict.dataset import render, rules
 
@@ -235,6 +238,62 @@ def test_render_workload_builds_candidates_reads_and_result():
     assert len(reads) == 1
     assert reads[0].label == "describe node /worker-1"
     assert result.cause == "node worker-1 (NotReady)"
+    assert workload.confidence == "high"
+
+
+def test_render_workload_prints_no_header_when_every_candidate_is_ruled_out():
+    node = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
+                     placement="off", fresh=o.Fresh(how="read", ready="False"),
+                     intent="decoy")
+    workload, _reads, _result = render.render_workload(
+        (node,), ns="shop", name="api", pod="api-0",
+        image="registry.example.com/api:1", issue="CrashLoopBackOff",
+        kind="Deployment", status="degraded",
+    )
+    assert workload.candidates[0].verdict == "ruled_out"
+    assert workload.confidence == ""
+
+
+# ------------------------------------------------------------- header_for
+#
+# A port of kubeagent v1.24.0's `confidence.ForRootCause`
+# (internal/confidence/confidence.go:36-47), applied to the one attributed
+# candidate's cause. `internal/investigate/prime.go:58-64` prints the header
+# for any non-empty value, `high` included.
+
+
+def _cand(cause: str, verdict: str) -> c.Candidate:
+    return c.Candidate(cause=cause, verdict=verdict, reason="r")
+
+
+@pytest.mark.parametrize("cause, level", [
+    ("node worker-1 (NotReady)", "high"),
+    ("PVC data-0 (FailedBinding)", "high"),
+    ("registry registry.invalid (3 workloads failing to pull)", "medium"),
+    ("image tag v9 does not exist", ""),
+    ("pvc data-0 (FailedBinding)", ""),   # the Go prefix match is case-sensitive
+])
+def test_header_for_ports_for_root_cause(cause, level):
+    assert render.header_for((_cand(cause, "attributed"),)) == level
+
+
+def test_header_for_reads_only_the_attributed_candidate():
+    cands = (_cand("node worker-1 (NotReady)", "ruled_out"),
+             _cand("registry registry.invalid (2 workloads failing to pull)", "attributed"))
+    assert render.header_for(cands) == "medium"
+
+
+def test_header_for_is_empty_with_no_attributed_candidate():
+    assert render.header_for((_cand("node worker-1 (NotReady)", "ruled_out"),
+                              _cand("PVC data-0 (FailedBinding)", "outranked"))) == ""
+    assert render.header_for(()) == ""
+
+
+def test_header_for_refuses_two_attributed_candidates():
+    """kubeagent's trace has at most one winner, so two is a generator bug."""
+    with pytest.raises(ValueError, match="2 attributed"):
+        render.header_for((_cand("node worker-1 (NotReady)", "attributed"),
+                           _cand("PVC data-0 (FailedBinding)", "attributed")))
 
 
 def test_workload_meta_has_exactly_seven_keys():
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_render.py
```

Expected: the summary line reads `9 failed, 22 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_render.py::test_render_workload_builds_candidates_reads_and_result
FAILED tests/test_render.py::test_header_for_ports_for_root_cause[node worker-1 (NotReady)-high]
FAILED tests/test_render.py::test_header_for_ports_for_root_cause[PVC data-0 (FailedBinding)-high]
FAILED tests/test_render.py::test_header_for_ports_for_root_cause[registry registry.invalid (3 workloads failing to pull)-medium]
FAILED tests/test_render.py::test_header_for_ports_for_root_cause[image tag v9 does not exist-]
FAILED tests/test_render.py::test_header_for_ports_for_root_cause[pvc data-0 (FailedBinding)-]
FAILED tests/test_render.py::test_header_for_reads_only_the_attributed_candidate
FAILED tests/test_render.py::test_header_for_is_empty_with_no_attributed_candidate
FAILED tests/test_render.py::test_header_for_refuses_two_attributed_candidates
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-2
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=2 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/render.py b/src/kubeagent_verdict/dataset/render.py
index d71013e..a77311e 100644
--- a/src/kubeagent_verdict/dataset/render.py
+++ b/src/kubeagent_verdict/dataset/render.py
@@ -21,7 +21,7 @@ from kubeagent_verdict.dataset.objects import drop, refute, unverify
 # render.py's public surface. Each step that adds a new function or a new
 # re-exported name appends it here, so ruff's F401 (unused import) never
 # has a window where an already-imported name looks unused.
-__all__ = ["apply_budget", "bind", "check_prompt_size", "draw_ending", "drop",
+__all__ = ["apply_budget", "bind", "check_prompt_size", "draw_ending", "drop", "header_for",
            "object_reads", "prompt_meta", "refute", "registry_events_read",
            "render_workload", "unverify", "workload_meta"]
 
@@ -183,6 +183,31 @@ def object_reads(
     return tuple(reads)
 
 
+# kubeagent's `confidence.ForRootCause` (internal/confidence/confidence.go:36-47
+# at v1.24.0), keyed by the attributed cause's prefix, in the Go switch's order.
+_HEADER_BY_PREFIX = (("node ", "high"), ("PVC ", "high"), ("registry ", "medium"))
+
+
+def header_for(candidates: tuple[c.Candidate, ...]) -> str:
+    """The `[confidence: ...]` header kubeagent prints over a trace.
+
+    A port of `ForRootCause`, applied to the one attributed candidate's
+    cause. No attributed candidate gives "" -- kubeagent prints no header.
+    Two or more raise ValueError: kubeagent's trace has at most one winner,
+    so two is a generator bug, not a prompt to render.
+    """
+    attributed = [cand for cand in candidates if cand.verdict == "attributed"]
+    if len(attributed) > 1:
+        raise ValueError(
+            f"{len(attributed)} attributed candidates; kubeagent attributes at most one")
+    if not attributed:
+        return ""
+    for prefix, level in _HEADER_BY_PREFIX:
+        if attributed[0].cause.startswith(prefix):
+            return level
+    return ""
+
+
 def render_workload(
     objects: tuple[o.Object, ...],
     *,
@@ -205,9 +230,10 @@ def render_workload(
 
     The returned Workload fills only the fields this module owns —
     namespace, name, kind, status, candidates, decided, decided_cause,
-    decided_outcome. findings, confidence, network_policies, rollout,
-    ready, and desired stay at their dataclass defaults; a caller building
-    a full prompt-ready Workload merges those in separately.
+    decided_outcome, and confidence (the trace header, via `header_for`).
+    findings, network_policies, rollout, ready, and desired stay at their
+    dataclass defaults; a caller building a full prompt-ready Workload
+    merges those in separately.
     """
     candidates = rules.attribute(objects, ns=ns, pod=pod, issue=issue)
     result = rules.decide(candidates)
@@ -232,6 +258,7 @@ def render_workload(
         restarts=0, findings=(), candidates=contract_candidates,
         decided=result.decided, decided_cause=result.cause,
         decided_outcome=result.outcome,
+        confidence=header_for(contract_candidates),
     )
     return workload, reads, result
 
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `833 passed` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_render.py src/kubeagent_verdict/dataset/render.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(dataset): print the job-2 header by kubeagent's confidence rule

header_for ports kubeagent's confidence.ForRootCause: the prefix of
the one attributed candidate's cause decides the [confidence: ...]
header. node and PVC give high, registry gives medium, anything else
gives no header. Two attributed candidates raise, because kubeagent's
trace has at most one winner.

render_workload now takes its header from it.
EOF
```

### Task 3: Fix the two catalogue strings kubeagent would never print

**Files:**
- Modify: `src/kubeagent_verdict/dataset/entries_kinds.py` (init-crashloop's and restart-loop's `log_cause`; restart-loop's `evidence`)
- Modify: `src/kubeagent_verdict/dataset/entries_slugs.py` (crashloop-pod's `log_cause`)
- Modify: `src/kubeagent_verdict/dataset/catalog.py` (one stale comment)
- Test: `tests/test_catalog.py`, `tests/test_exam_graded_view.py`, `tests/test_exam_prompt_stability.py`, `tests/test_oracle.py`, `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: nothing from this plan.
- Produces: every entry's `log_cause` holds the bare cause; the renderer
  adds the `log cause: ` prefix. restart-loop's `evidence` quotes the
  container. In `tests/test_shared_origin_training.py`, `FROZEN_253_SHA256`
  is renamed `FROZEN_SLICE_SHA256`. `tests/test_exam_prompt_stability.py`
  reads the bank `out/dataset-0924`.

**Why (spec "Prompts kubeagent could never send"):** three entries stored
`log cause: …` in `log_cause`, and the renderer adds the prefix again, so
their prompts said `log cause: log cause: …`. restart-loop printed
`container app`, where kubeagent's `%q` prints `container "app"`
(`restartloop.go:47`, ruling 6). The three pinned hashes move; the tests diff
writes their new values. The 2 prompt-stability tests skip from here until
Task 9 (ruling 11).

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

6. **The restart-loop citation is `restartloop.go:47`.** The spec's table
   says `:44`. At kubeagent v1.24.0 the `Evidence` format string is on
   line 47. The test in Task 3 cites `:47`.
11. **The prompt-stability test skips from Task 3 to Task 9.** Task 3
    changes prompts, so the test is re-pointed at the new bank,
    `out/dataset-0924`. That bank does not exist until Task 9 builds it.
    Its 2 tests skip in between. That is expected.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-3
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=3 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_catalog.py b/tests/test_catalog.py
index be81a30..245bd33 100644
--- a/tests/test_catalog.py
+++ b/tests/test_catalog.py
@@ -224,3 +224,17 @@ def test_grounding_substrings_appear_in_corpus():
             joined = "\n".join(a for r in rows for a in r.assertions)
             for g in e.grounding:
                 assert g in joined, f"{e.key}: grounding {g!r} not in corpus assertions for {slug}"
+
+
+def test_log_cause_carries_no_prefix():
+    """The renderer adds `log cause: ` once (`contract._finding_block`), so a
+    value that already starts with it prints `log cause: log cause: …`."""
+    for e in catalog.all_entries():
+        assert not e.log_cause.startswith("log cause"), e.key
+
+
+def test_restart_loop_evidence_quotes_the_container():
+    """kubeagent prints `container %q, %d restarts, …`
+    (internal/diagnose/restartloop.go:47 at v1.24.0)."""
+    e = next(e for e in catalog.all_entries() if e.key == "restart-loop")
+    assert e.evidence.format(**SAMPLE).startswith('container "app", 14 restarts, ')
diff --git a/tests/test_exam_graded_view.py b/tests/test_exam_graded_view.py
index 8f54800..d72590c 100644
--- a/tests/test_exam_graded_view.py
+++ b/tests/test_exam_graded_view.py
@@ -37,6 +37,12 @@ Twenty shared-origin workloads' `own_cause_keywords` move from `[]` to a
 curated pair (see `tests/test_shared_origin_training.py`'s matching
 2026-09-23 entries), and the digest moves with them -- on the same 11
 rows, nothing else.
+
+Re-pinned on 2026-09-24 for the job-2 generator fix
+(2026-09-24-job2-generator-fix-design.md). This time the user message
+moves, and this view keeps it whole, so the digest follows every rendered
+change `FROZEN_SLICE_SHA256`'s 2026-09-24 entry lists in
+`tests/test_shared_origin_training.py`. The new exam is a new baseline.
 """
 
 from __future__ import annotations
@@ -63,7 +69,7 @@ def view(row):
             "flagged": [v["workload"] for v in gold["verdicts"]]}
 
 
-GRADED_VIEW_SHA256 = "b82b87977414e01e5d58eeb64defc5dec350bab6f567006d02ea96932700b03e"
+GRADED_VIEW_SHA256 = "100ec57cebcc2d8c25c62466116e7886a2689faea071f25d6e47acecbf76412d"
 
 
 def _digest(views) -> str:
diff --git a/tests/test_exam_prompt_stability.py b/tests/test_exam_prompt_stability.py
index 8e22d60..f1b3448 100644
--- a/tests/test_exam_prompt_stability.py
+++ b/tests/test_exam_prompt_stability.py
@@ -1,10 +1,18 @@
 """The banked exam's prompts must not move.
 
-`out/dataset-0920/test.jsonl` is the exam the 0920 build answered and
-`out/eval-0920/results.jsonl` holds its replies verbatim. Re-scoring those
-replies against a corrected `meta` is only honest if the QUESTIONS are the
-same ones the model saw. This module is that proof: regenerate the exam and
-compare `messages` row for row, byte for byte.
+`out/dataset-0924/test.jsonl` is the exam the job-2 generator fix
+(2026-09-24-job2-generator-fix-design.md) banks: 252 rows, and a new
+baseline. Every model scored after that fix answers these questions, the
+0920 build's one live run included. Re-scoring banked replies against a
+corrected `meta` is only honest if the QUESTIONS are the same ones the
+model saw. This module is that proof: regenerate the exam and compare
+`messages` row for row, byte for byte.
+
+Until 2026-09-24 it pointed at `out/dataset-0920/test.jsonl`, the 263-row
+exam the 0920 build answered. The generator fix moves rendered bytes on
+purpose, so that bank no longer matches this generator. Between the
+commit that re-points this module and the one that regenerates the bank,
+the new bank does not exist yet and this module skips.
 
 `messages` is all three -- system, user and the gold assistant answer.
 `score.evaluate` reads the gold answer back out of `messages[2]` to build
@@ -22,7 +30,7 @@ import pytest
 
 from kubeagent_verdict.dataset import generate
 
-BANK = Path(__file__).resolve().parents[1] / "out" / "dataset-0920" / "test.jsonl"
+BANK = Path(__file__).resolve().parents[1] / "out" / "dataset-0924" / "test.jsonl"
 
 pytestmark = pytest.mark.skipif(
     not BANK.exists(), reason=f"banked exam not present at {BANK}")
@@ -33,11 +41,11 @@ def _banked_rows() -> list[dict]:
             BANK.read_text(encoding="utf-8").splitlines() if line]
 
 
-def test_the_banked_exam_is_the_263_row_exam():
+def test_the_banked_exam_is_the_252_row_exam():
     """A guard on the guard. Comparing row for row proves nothing if the
     two sides are different lengths and the zip silently truncates.
     """
-    assert len(_banked_rows()) == 263
+    assert len(_banked_rows()) == 252
 
 
 def test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam():
diff --git a/tests/test_oracle.py b/tests/test_oracle.py
index c4bf6c5..4cf42ba 100644
--- a/tests/test_oracle.py
+++ b/tests/test_oracle.py
@@ -225,7 +225,7 @@ def test_exam_oracle_job3_is_perfect():
     """spec section 10 gate 2's other half, and a stop condition: if the
     exam's own job3, oracle-read, were not 1.0 after the label-driven
     summary, the gold summaries would be wrong and re-pinning
-    `FROZEN_253_SHA256` / `EVAL_SET_SHA256` over them would bank the error.
+    `FROZEN_SLICE_SHA256` / `EVAL_SET_SHA256` over them would bank the error.
     It reads 1.0 -- 5 of 5 `shared`-labeled rows (the three origin-object
     stories' `shared_origin_probe` halves) and 34 of 34 `none`-labeled
     rows."""
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index 4eb9783..329c00e 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -811,7 +811,23 @@ def test_the_eval_set_is_two_hundred_and_sixty_three_rows():
 # `out/dataset-0920/test.jsonl` row for row, and a key-by-key diff of the
 # exam before and after this fix reports `meta` as the only top-level key
 # that changed. That is what makes this a meta-only move and not a new exam.
-FROZEN_253_SHA256 = "2532b7908adfc91f22c56710eb5f9e47e500b4060460ae7de373a003afed1bc9"
+#
+# It moved a fifth time, on 2026-09-24, for the job-2 generator fix
+# (2026-09-24-job2-generator-fix-design.md), and was renamed from
+# `FROZEN_253_SHA256`: that fix shrinks the `none_of_these` slice, so the
+# slice stops being 253 rows long. It keeps its meaning -- every exam row
+# before the trailing ten `shared_origin_decoy_probe` rows -- and
+# `test_the_frozen_slice_is_every_row_before_the_decoy_probe` pins its
+# length on its own. This time rendered bytes move, not only `meta`, and
+# the new exam is a new baseline: no number on it compares with one from
+# before. What moved it, in commit order:
+# - The catalogue stopped doubling the `log cause: ` prefix
+#   (`crashloop-pod`, `init-crashloop`, `restart-loop`) and quotes the
+#   container in `restart-loop`'s evidence, as kubeagent prints it. 41
+#   rows move, in the user message only: 8 `attributed`, 6
+#   `multi_misattribution_probe`, and 3 in each of the other nine cases
+#   outside the two shared-origin probes.
+FROZEN_SLICE_SHA256 = "1aead0803e798d40fa535300177e5156883c908e4e790255ee685f132da554fa"
 
 # The whole exam, 253 plus the ten `shared_origin_decoy_probe` rows. First
 # captured on `main` @ `ee2980e` as `e8cbb549…b49de`; 0902 and 0905 were
@@ -855,7 +871,7 @@ FROZEN_253_SHA256 = "2532b7908adfc91f22c56710eb5f9e47e500b4060460ae7de373a003afe
 # the `separate` re-pin above is retired.
 #
 # Re-pinned once more on 2026-09-19, in the same commit and for the same
-# `_render_shared_origin` fix that moved `FROZEN_253_SHA256` above (see
+# `_render_shared_origin` fix that moved `FROZEN_SLICE_SHA256` above (see
 # its 2026-09-19 entry). Four of the ten `shared_origin_decoy_probe` rows
 # change too -- exactly the ones with a decided victim this draw (two
 # coredns-down, two node-disk-pressure): their decided victim's row cause
@@ -866,13 +882,18 @@ FROZEN_253_SHA256 = "2532b7908adfc91f22c56710eb5f9e47e500b4060460ae7de373a003afe
 # each only in the assistant message and the meta that mirrors it.
 #
 # Re-pinned a fourth time on 2026-09-23, in the same commit and for the
-# same exam-grader fix that moved `FROZEN_253_SHA256` above (see its
+# same exam-grader fix that moved `FROZEN_SLICE_SHA256` above (see its
 # 2026-09-23 entry). This digest covers the frozen slice AND the ten
 # `shared_origin_decoy_probe` rows outside it, so it carries that entry's
 # four workloads plus the sixteen in those ten rows -- the twenty that
 # scored 0.0 against their own gold answer before this fix. Same meta-only
 # reason, and no `messages` byte moves in either slice.
-EVAL_SET_SHA256 = "d40dabc9fafec54a46398a13e7e984a965824d550399c09c60c7fc848e9a3288"
+#
+# Re-pinned a fifth time on 2026-09-24, in the same commits and for the
+# same job-2 generator fix that moved `FROZEN_SLICE_SHA256` above (see its
+# 2026-09-24 entry). None of the ten `shared_origin_decoy_probe` rows
+# moves, so this digest moves only because the frozen slice inside it does.
+EVAL_SET_SHA256 = "6e1f553be2956b2b5a1217632b4787027875fb3b4c1335f5fcf1e4bc96327ad3"
 
 
 def _digest(rows) -> str:
@@ -881,9 +902,19 @@ def _digest(rows) -> str:
     return hashlib.sha256(blob.encode("utf-8")).hexdigest()
 
 
-def test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used():
-    assert _digest(generate.test_set()[:253]) == FROZEN_253_SHA256, (
-        "the frozen 253 moved; every banked scoreboard comparison is now void")
+def test_the_frozen_slice_is_every_row_before_the_decoy_probe():
+    """The frozen slice is named by what it holds, not by a row number:
+    every exam row before the trailing ten `shared_origin_decoy_probe`
+    rows. Its length is pinned here, apart from its digest."""
+    rows = generate.test_set()
+    assert [e.case for e in rows[-10:]] == ["shared_origin_decoy_probe"] * 10
+    assert "shared_origin_decoy_probe" not in {e.case for e in rows[:-10]}
+    assert len(rows[:-10]) == 253
+
+
+def test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used():
+    assert _digest(generate.test_set()[:-10]) == FROZEN_SLICE_SHA256, (
+        "the frozen slice moved; every banked scoreboard comparison is now void")
 
 
 def test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used():
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_catalog.py tests/test_exam_graded_view.py tests/test_exam_prompt_stability.py tests/test_oracle.py tests/test_shared_origin_training.py
```

Expected: the summary line reads `6 failed, 76 passed, 2 skipped`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_catalog.py::test_log_cause_carries_no_prefix
FAILED tests/test_catalog.py::test_restart_loop_evidence_quotes_the_container
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-3
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=3 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/catalog.py b/src/kubeagent_verdict/dataset/catalog.py
index 859a33d..6336549 100644
--- a/src/kubeagent_verdict/dataset/catalog.py
+++ b/src/kubeagent_verdict/dataset/catalog.py
@@ -40,7 +40,7 @@ class CatalogEntry:
     reads: tuple[tuple[str, str], ...] = ()  # (label template, content template)
     rationale: str = ""
     direct: bool = True  # True: full evidence earns "high" confidence; False: "medium"
-    contradiction: str = ""  # read content that rules the winner out (none_of_these case)
+    contradiction: str = ""  # read content that rules the winner out (contradiction_probe)
     own_cause: str = ""  # the cause phrase when the winner is omitted from candidates
     own_cause_keywords: tuple[str, ...] = ()
     grounding: tuple[str, ...] = ()  # substrings that must appear in this slug's corpus assertions
diff --git a/src/kubeagent_verdict/dataset/entries_kinds.py b/src/kubeagent_verdict/dataset/entries_kinds.py
index 8e9c3e9..4b872ae 100644
--- a/src/kubeagent_verdict/dataset/entries_kinds.py
+++ b/src/kubeagent_verdict/dataset/entries_kinds.py
@@ -131,7 +131,7 @@ ENTRIES = [
         issue="Init:CrashLoopBackOff",
         reason="an init container is crash-looping — the pod cannot start its main containers",
         evidence='init container "{init_container}" (1/2), restartCount={restarts}',
-        log_cause="log cause: cannot reach a dependency — connection refused",
+        log_cause="cannot reach a dependency — connection refused",
         recommendation="check what the init container is waiting for and why it cannot reach it",
         winner_cause="the init container cannot reach the dependency it waits for",
         winner_reason="the previous-instance log classifies as a refused connection on every "
@@ -326,8 +326,8 @@ ENTRIES = [
         status="Degraded",
         issue="RestartLoop",
         reason="Container keeps exiting with an error and restarting",
-        evidence="container {container}, {restarts} restarts, last exit 1 (Error), 90s ago",
-        log_cause="log cause: application panic (code bug)",
+        evidence='container "{container}", {restarts} restarts, last exit 1 (Error), 90s ago',
+        log_cause="application panic (code bug)",
         recommendation="check the previous log for the panic and what request triggered it",
         winner_cause="the container panics intermittently under load",
         winner_reason="the previous-instance log carries a panic trace, and the restarts "
diff --git a/src/kubeagent_verdict/dataset/entries_slugs.py b/src/kubeagent_verdict/dataset/entries_slugs.py
index 206e7c1..764d602 100644
--- a/src/kubeagent_verdict/dataset/entries_slugs.py
+++ b/src/kubeagent_verdict/dataset/entries_slugs.py
@@ -364,7 +364,7 @@ ENTRIES = [
         issue="CrashLoopBackOff",
         reason="Container repeatedly crashes after starting",
         evidence='container "{container}", restartCount={restarts}',
-        log_cause="log cause: bad command or entrypoint",
+        log_cause="bad command or entrypoint",
         recommendation="check the container's command and args against what the image expects to run",
         winner_cause="the container exits immediately on startup",
         winner_reason="the previous-instance log shows an entrypoint failure, and the image "
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `834 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_catalog.py tests/test_exam_graded_view.py tests/test_exam_prompt_stability.py tests/test_oracle.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_kinds.py src/kubeagent_verdict/dataset/entries_slugs.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(dataset): drop the doubled log-cause prefix and quote restart-loop's container

Three entries stored "log cause: ..." in log_cause, and the renderer
adds that prefix again, so their prompts said it twice. restart-loop
printed its container unquoted, where kubeagent's %q quotes it.
kubeagent prints neither string.

The exam's three pinned hashes move, re-pinned by hand with the reason.
The frozen slice's pin is renamed FROZEN_SLICE_SHA256: the slice will
not stay 253 rows long. The prompt-stability test now reads the
out/dataset-0924 bank and skips until that bank is built.
EOF
```

### Task 4: Build kubeagent's previous-log read

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (add `_NO_CLASSIFIABLE`, `_NO_PREVIOUS`, `LOG_READS`, `_LOG_CONTAINER`, `_log_read`)
- Test: `tests/test_cases.py`

**Interfaces:**
- Consumes: `CatalogEntry` and `Names` (existing).
- Produces, in `cases.py`:
  - `LOG_READS: dict[str, tuple[str, str | None]]` — entry key to
    `(clear, thin)` content templates, `thin` is `None` where no thin row
    exists. Its keys are exactly the five crash-family entries.
  - `_log_read(e: CatalogEntry, n: Names, evidence: str) -> c.EvidenceRead | None`
    — `evidence` is `"clear"` or `"thin"`. It returns `None` outside the
    crash family, and raises `ValueError` on any other `evidence` value or
    on a thin request for an entry with no thin arm. The label is
    `log causes {ns}/{pod} container {container}`, container not quoted;
    the container is `coredns` for `coredns-corefile-broken` and
    `n.container` for every other entry.

  Tasks 5, 7 and 8 call `_log_read`. Nothing calls it yet, so no prompt
  and no hash changes in this task.

**Why (spec section 3):** kubeagent makes one previous-log read per
crash-family finding (`internal/investigate/gather.go:44-157` at
v1.24.0). A row that shows a crash-family finding but no log read is a
prompt kubeagent could never send.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-4
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=4 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_cases.py b/tests/test_cases.py
index 390eb50..0c1341d 100644
--- a/tests/test_cases.py
+++ b/tests/test_cases.py
@@ -598,3 +598,71 @@ def test_every_build_user_message_call_goes_through_the_checked_funnel():
         f"src/kubeagent_verdict/dataset/ to route through cases._user_message "
         f"(the shared funnel); found call(s) outside it: {findings}"
     )
+
+
+# kubeagent's previous-log read, pinned to its source at v1.24.0. The label
+# is internal/investigate/gather.go:153, `log causes %s/%s container %s`,
+# the container not quoted. The content is one arm of `logCauseResult`,
+# internal/investigate/reader.go:473-487, where `%q` quotes the container.
+# The two cause strings are internal/logscan/logscan.go:32 (entrypoint) and
+# :62 (config).
+_NO_CLASSIFIABLE = 'the previous log of {ns}/{pod} container "{container}" has no classifiable output'
+_NO_PREVIOUS = ('no previous-instance log for {ns}/{pod} container "{container}" '
+                "(nothing was refused; the container may not have restarted)")
+
+
+def test_log_reads_cover_exactly_the_crash_family():
+    """kubeagent reads the previous log only for three issues (`crashFamily`,
+    internal/investigate/gather.go:195-197). A new trainable entry with one
+    of them fails here until it gets a row."""
+    crash = {"CrashLoopBackOff", "ContainerStartError", "OOMKilled"}
+    assert set(cases.LOG_READS) == {e.key for e in catalog.trainable() if e.issue in crash}
+
+
+@pytest.mark.parametrize(("key", "evidence", "content"), [
+    ("crashloop-pod", "clear", "log cause: bad command or entrypoint"),
+    ("crashloop-pod", "thin", _NO_CLASSIFIABLE),
+    ("coredns-corefile-broken", "clear", "log cause: configuration parse/validation error"),
+    ("coredns-corefile-broken", "thin", _NO_CLASSIFIABLE),
+    ("memory-limit-oomkill", "clear", _NO_CLASSIFIABLE),
+    ("container-start-error", "clear", _NO_PREVIOUS),
+    ("worker-containerd-stop", "clear", _NO_PREVIOUS),
+])
+def test_log_read_is_the_read_kubeagent_makes(key, evidence, content):
+    n = names_mod.draw(random.Random(5))
+    # The finding's container: coredns-corefile-broken's finding pins
+    # `coredns`; every other entry's is the drawn one.
+    container = "coredns" if key == "coredns-corefile-broken" else n.container
+    assert cases._log_read(_entry(key), n, evidence) == c.EvidenceRead(
+        label=f"log causes {n.ns}/{n.pod} container {container}",
+        content=content.format(ns=n.ns, pod=n.pod, container=container))
+
+
+@pytest.mark.parametrize("key", ["init-crashloop", "restart-loop", "deployment-bad-image-tag"])
+@pytest.mark.parametrize("evidence", ["clear", "thin"])
+def test_log_read_is_none_outside_the_crash_family(key, evidence):
+    """Init:CrashLoopBackOff and RestartLoop are not crash family in
+    kubeagent, so neither version of the row carries a log read."""
+    n = names_mod.draw(random.Random(5))
+    assert cases._log_read(_entry(key), n, evidence) is None
+
+
+@pytest.mark.parametrize("key", ["memory-limit-oomkill", "container-start-error",
+                                 "worker-containerd-stop"])
+def test_log_read_has_no_thin_arm_for_a_neutral_clear_read(key):
+    n = names_mod.draw(random.Random(5))
+    with pytest.raises(ValueError, match="no thin log read"):
+        cases._log_read(_entry(key), n, "thin")
+
+
+def test_log_read_refuses_an_unknown_evidence():
+    n = names_mod.draw(random.Random(5))
+    with pytest.raises(ValueError, match="evidence"):
+        cases._log_read(_entry("crashloop-pod"), n, "vague")
+
+
+def test_crashloop_pods_clear_log_read_names_its_findings_cause():
+    """The finding's `log cause:` line and the clear log read agree."""
+    e = _entry("crashloop-pod")
+    n = names_mod.draw(random.Random(5))
+    assert cases._log_read(e, n, "clear").content == "log cause: " + e.log_cause
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_cases.py
```

Expected: the summary line reads `19 failed, 40 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_cases.py::test_log_reads_cover_exactly_the_crash_family
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[crashloop-pod-clear-log cause: bad command or entrypoint]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[crashloop-pod-thin-the previous log of {ns}/{pod} container "{container}" has no classifiable output]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[coredns-corefile-broken-clear-log cause: configuration parse/validation error]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[coredns-corefile-broken-thin-the previous log of {ns}/{pod} container "{container}" has no classifiable output]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[memory-limit-oomkill-clear-the previous log of {ns}/{pod} container "{container}" has no classifiable output]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[container-start-error-clear-no previous-instance log for {ns}/{pod} container "{container}" (nothing was refused; the container may not have restarted)]
FAILED tests/test_cases.py::test_log_read_is_the_read_kubeagent_makes[worker-containerd-stop-clear-no previous-instance log for {ns}/{pod} container "{container}" (nothing was refused; the container may not have restarted)]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[clear-init-crashloop]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[clear-restart-loop]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[clear-deployment-bad-image-tag]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[thin-init-crashloop]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[thin-restart-loop]
FAILED tests/test_cases.py::test_log_read_is_none_outside_the_crash_family[thin-deployment-bad-image-tag]
FAILED tests/test_cases.py::test_log_read_has_no_thin_arm_for_a_neutral_clear_read[memory-limit-oomkill]
FAILED tests/test_cases.py::test_log_read_has_no_thin_arm_for_a_neutral_clear_read[container-start-error]
FAILED tests/test_cases.py::test_log_read_has_no_thin_arm_for_a_neutral_clear_read[worker-containerd-stop]
FAILED tests/test_cases.py::test_log_read_refuses_an_unknown_evidence
FAILED tests/test_cases.py::test_crashloop_pods_clear_log_read_names_its_findings_cause
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-4
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=4 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/cases.py b/src/kubeagent_verdict/dataset/cases.py
index ffd1ee3..98e1e92 100644
--- a/src/kubeagent_verdict/dataset/cases.py
+++ b/src/kubeagent_verdict/dataset/cases.py
@@ -127,6 +127,53 @@ def _workload(e: CatalogEntry, n: Names, candidates: tuple[c.Candidate, ...],
     )
 
 
+# kubeagent's previous-log read, one per crash-family finding: CrashLoopBackOff,
+# ContainerStartError, OOMKilled (`crashFamily`,
+# internal/investigate/gather.go:195-197 at v1.24.0). Its content is one arm of
+# `logCauseResult` (internal/investigate/reader.go:473-487), where `%q` quotes
+# the container. Keyed by entry, not guessed from the issue text: each value is
+# (clear, thin), thin None where no thin row exists.
+_NO_CLASSIFIABLE = 'the previous log of {ns}/{pod} container "{container}" has no classifiable output'
+_NO_PREVIOUS = ('no previous-instance log for {ns}/{pod} container "{container}" '
+                "(nothing was refused; the container may not have restarted)")
+LOG_READS: dict[str, tuple[str, str | None]] = {
+    # internal/logscan/logscan.go:32
+    "crashloop-pod": ("log cause: bad command or entrypoint", _NO_CLASSIFIABLE),
+    # internal/logscan/logscan.go:62
+    "coredns-corefile-broken": ("log cause: configuration parse/validation error",
+                                _NO_CLASSIFIABLE),
+    "memory-limit-oomkill": (_NO_CLASSIFIABLE, None),
+    "container-start-error": (_NO_PREVIOUS, None),
+    "worker-containerd-stop": (_NO_PREVIOUS, None),
+}
+
+# The container kubeagent reads is the finding's own. coredns-corefile-broken's
+# finding pins `coredns`; every other entry's is the drawn `n.container`.
+_LOG_CONTAINER = {"coredns-corefile-broken": "coredns"}
+
+
+def _log_read(e: CatalogEntry, n: Names, evidence: str) -> c.EvidenceRead | None:
+    """The previous-log read kubeagent makes for this entry, or None.
+
+    `evidence` is "clear" or "thin". The label is
+    internal/investigate/gather.go:153, container not quoted. An entry outside
+    the crash family gets no read in either version; asking a crash-family
+    entry with no thin arm for a thin read raises.
+    """
+    if evidence not in ("clear", "thin"):
+        raise ValueError(f"evidence must be 'clear' or 'thin', not {evidence!r}")
+    if e.key not in LOG_READS:
+        return None
+    clear, thin = LOG_READS[e.key]
+    if evidence == "thin" and thin is None:
+        raise ValueError(f"{e.key} has no thin log read")
+    container = _LOG_CONTAINER.get(e.key, n.container)
+    content = clear if evidence == "clear" else thin
+    return c.EvidenceRead(
+        label=f"log causes {n.ns}/{n.pod} container {container}",
+        content=content.format(ns=n.ns, pod=n.pod, container=container))
+
+
 def _row_decoy(decoys: list[str]) -> dict:
     """The row-level `decoy_cause` key, from the row's own decoy list.
 
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `853 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_cases.py src/kubeagent_verdict/dataset/cases.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(dataset): build kubeagent's previous-log read for crash-family entries

kubeagent makes one previous-log read per crash-family finding:
CrashLoopBackOff, ContainerStartError and OOMKilled. _log_read builds
that read for the five crash-family entries, in a clear version that
names the cause and, where one exists, a thin version that does not.
The label and every content string are kubeagent's own.

Nothing calls it yet, so no prompt changes.
EOF
```

### Task 5: One builder for every undecided job-2 row

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (add `THIN_ENTRIES`, `_THIN_RATIONALE`, `_CLEAR_WORDING`, `_MENUS`, `_undecided_example`; rewrite `wrong_attribution`, `own_cause_case`, `none_of_these_case` and `misattribution_probe` as wrappers; `_workload` gains `with_log_cause`; move `_ruled_out_menu` up; comment fixes)
- Modify: `src/kubeagent_verdict/dataset/generate.py` (`generate` rotates `none_of_these` through the thin entries and stops passing `rng` to the four builders; `held_out_case_set` builds `none_of_these` per thin entry and shape; docstring and comment fixes)
- Test: `tests/test_cases.py`, `tests/test_evidence_overlap.py`, `tests/test_exam_graded_view.py`, `tests/test_generate.py`, `tests/test_oracle.py`, `tests/test_probe_cousins.py`, `tests/test_score.py`, `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `render.header_for` (Task 2), `cases._log_read` (Task 4), and
  the per-workload job-2 grading in `score.evaluate` (Task 1).
- Produces, in `cases.py`:
  - `THIN_ENTRIES = ("crashloop-pod", "coredns-corefile-broken", "init-crashloop", "restart-loop")`
  - `_undecided_example(e: CatalogEntry, n: Names, *, case: str, shape: str, evidence: str) -> Example`
    — `shape` is `"refuted"` or `"ruled_out"`; `evidence` is `"thin"` for
    `case="none_of_these"` and `"clear"` for `wrong_attribution`,
    `own_cause` and `misattribution_probe`. Anything else raises
    `ValueError`, and so does a thin row for an entry outside
    `THIN_ENTRIES` or an entry with no objects.
  - `wrong_attribution(e, n) -> Example` (refuted, clear)
  - `own_cause_case(e, n) -> Example` (ruled_out, clear)
  - `none_of_these_case(e, n, *, shape: str) -> Example` (thin)
  - `misattribution_probe(e, n) -> Example` (ruled_out, clear)
  - `_workload(e, n, candidates, confidence, *, result, with_log_cause: bool = True)`

  None of the four wrappers takes an `rng`.
- Produces, in `generate.py`: `held_out_case_set()` gives 8
  `none_of_these` rows (4 thin entries × 2 shapes), each drawn from
  `_entry_rng("held-out", "none_of_these", entry.key, shape)`.

**Why (spec sections 2, 3, 4 and 6):** today `none_of_these` and
`wrong_attribution` build the same bytes for 27 of 28 entries and answer
them oppositely. After this task the prompt is a function of
`(entry, names, shape, evidence)` only, never of the case, so one prompt
cannot carry two answers. Rulings 1 to 5 and 10 apply here. The three
pinned hashes move (the tests diff writes their new values), and every
train and val count moves (ruling 1).

**Step 2 note:** `tests/test_cases.py` imports names this task creates, so
pytest cannot collect it until Step 3. The run below passes
`--continue-on-collection-errors` so the other seven files still report.

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

1. **`_undecided_example` takes no `rng`.** Spec section 2 writes the
   signature with `rng`. But the same section forbids a shuffle, and every
   entry declares at most two objects, already in gather order. Nothing is
   drawn, so an `rng` parameter would be a promise the code does not keep.
   The builder and its four wrappers take none, and `generate.py` stops
   passing one (Task 5). Cost: `generate()` shares one `rng` across all
   cases, so removing draws shifts every later draw, and every train and
   val count moves. The exam uses a keyed `rng` per entry, so it moves only
   where the spec says.
2. **Meta stays per case.** The prompt never depends on `case`; the meta
   does, as today. `expected_own_keywords` is set only on `own_cause`. The
   `_row_decoy` keys are set only on `wrong_attribution` and
   `misattribution_probe`. Spec section 2: "`case` names the example and
   its meta."
3. **No read budget in the builder.** An undecided row has at most 2 object
   reads and 1 log read. `apply_budget` could never cut, so it is not
   called. Only `multi` can pass 8 reads (Task 7).
4. **An empty evidence section is a real row.** Spec section 2, "A known
   consequence": a ruled-out row outside the crash family has no reads and
   renders `(none)`. `tests/test_evidence_overlap.py`'s `_reads` used to
   refuse that shape; it now returns `[]` for it (Task 5).
5. **The eval-only reuse allowlist moves twice.** `DECLARED` in
   `tests/test_evidence_overlap.py`: `misattribution_probe` goes
   `(14, 20)` → `(5, 5)` in Task 5 (its describe reads are gone), and
   `multi_misattribution_probe` goes `(39, 40)` → `(47, 48)` in Task 7 (it
   gains log reads that crash-family training rows also carry).
   `contradiction_probe` stays `(19, 38)`; only its comment changes.
10. **The paste-the-prompt guard still holds.** The spec says to stop if it
    fails. On the new exam the paste bot scores 76/142 = 0.5352 on job 2,
    below `JOB2_BAR` (0.7). Task 5 pins it.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-5
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=5 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_cases.py b/tests/test_cases.py
index 0c1341d..1fd296f 100644
--- a/tests/test_cases.py
+++ b/tests/test_cases.py
@@ -57,19 +57,19 @@ def test_attributed_menu_comes_from_declared_objects_not_losers():
     assert ex_full.user.count("considered") > ex_stripped.user.count("considered")
 
 
-def test_none_of_these_contradicts_and_answers_none():
+def test_none_of_these_names_no_cause_and_answers_none_at_low():
     n = names_mod.draw(random.Random(21))
-    ex = cases.none_of_these_case(_entry("memory-limit-oomkill"), n, random.Random(21))
+    ex = cases.none_of_these_case(_entry("crashloop-pod"), n, shape="refuted")
     (row,) = json.loads(ex.assistant)["verdicts"]
     assert row["cause"] == c.NONE_OF_THESE
-    assert row["confidence"] == "medium"
-    assert "exit code 1" in ex.user  # the contradiction evidence is in the prompt
-    assert "OOMKilled, exit code 137" not in ex.user.split("== BEGIN evidence ==")[1]
+    assert row["confidence"] == "low"
+    # Thin evidence: the finding's log-cause line and the classified read are gone.
+    assert "log cause:" not in ex.user
 
 
 def test_own_cause_omits_winner_from_candidates():
     n = names_mod.draw(random.Random(22))
-    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n, random.Random(22))
+    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n)
     cand_section = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
     assert "memory limit too low for the workload" not in cand_section
     (row,) = json.loads(ex.assistant)["verdicts"]
@@ -163,7 +163,7 @@ def test_truncated_expected_cause_matches_attributed_for_the_same_seed():
     assert ex_trunc.meta["expected_cause"] == ex_attr.meta["expected_cause"]
 
 
-def test_none_of_these_refutes_every_declared_object():
+def test_refuted_menu_refutes_every_declared_object():
     e = _entry("worker-containerd-stop")
     n = names_mod.draw(random.Random(5))
     menu = cases._refuted_menu(n, e.objects)
@@ -172,26 +172,26 @@ def test_none_of_these_refutes_every_declared_object():
     assert len(reads) == 2
 
 
-def test_none_of_these_answer_is_still_none_of_these():
+def test_none_of_these_refuses_an_entry_without_thin_evidence():
     e = _entry("worker-containerd-stop")
     n = names_mod.draw(random.Random(5))
-    ex = cases.none_of_these_case(e, n, random.Random(5))
-    answer = json.loads(ex.assistant)
-    assert answer["verdicts"][0]["cause"] == c.NONE_OF_THESE
-    assert answer["verdicts"][0]["confidence"] == "medium"
+    with pytest.raises(ValueError, match="worker-containerd-stop is not a thin entry"):
+        cases.none_of_these_case(e, n, shape="refuted")
 
 
-def test_own_cause_menu_is_refuted_not_hand_written():
+def test_own_cause_is_the_ruled_out_shape():
     e = _entry("worker-containerd-stop")
     n = names_mod.draw(random.Random(9))
-    ex = cases.own_cause_case(e, n, random.Random(9))
+    ex = cases.own_cause_case(e, n)
     answer = json.loads(ex.assistant)
     assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)
+    assert answer["verdicts"][0]["confidence"] == cases._confidence(e)
     assert ex.meta["expected_own_keywords"] == list(e.own_cause_keywords)
     assert answer["verdicts"][0]["rationale"].endswith(
         "The candidate list shown did not include this cause.")
-    menu = cases._refuted_menu(n, e.objects)
-    assert len(object_reads(menu, ns=n.ns, pod=n.pod)) == len(e.objects)
+    assert ": attributed" not in _cand_section(ex.user)
+    assert "fresh read:" not in ex.user
+    assert "== describe " not in ex.user
 
 
 def test_wrong_attribution_names_its_decoy_cause_and_expects_the_own_cause():
@@ -201,7 +201,7 @@ def test_wrong_attribution_names_its_decoy_cause_and_expects_the_own_cause():
     key and has no population without it."""
     e = _entry("worker-containerd-stop")
     n = names_mod.draw(random.Random(21))
-    ex = cases.wrong_attribution(e, n, random.Random(5))
+    ex = cases.wrong_attribution(e, n)
     answer = json.loads(ex.assistant)
     key = f"{n.ns}/{n.name}"
     assert ex.meta["decoy_cause"] == ex.meta["decoy_by_workload"][key][0]
@@ -320,7 +320,7 @@ def test_candidate_order_is_shuffled_not_winner_first():
 def test_shuffle_covers_every_case_that_renders_a_menu():
     entry = _entry("memory-limit-oomkill")
     winner = "memory limit too low for the workload"
-    for builder in (cases.attributed, cases.none_of_these_case, cases.truncated):
+    for builder in (cases.attributed, cases.truncated):
         firsts = [_winner_is_first(
             builder(entry, names_mod.draw(random.Random(s)), random.Random(s)).user, winner)
             for s in range(60)]
@@ -666,3 +666,238 @@ def test_crashloop_pods_clear_log_read_names_its_findings_cause():
     e = _entry("crashloop-pod")
     n = names_mod.draw(random.Random(5))
     assert cases._log_read(e, n, "clear").content == "log cause: " + e.log_cause
+
+
+# One builder for every undecided job-2 row. kubeagent leaves a workload
+# undecided in two shapes. Refuted: one candidate is attributed and a fresh
+# read refutes it. Ruled out: every candidate is ruled out. The evidence is
+# clear (the prompt names the cause) or thin (it does not). The prompt is a
+# function of (entry, names, shape, evidence) and never of the case, so one
+# prompt never carries two expected answers.
+SHAPES = ("refuted", "ruled_out")
+CLEAR_CASES = ("wrong_attribution", "own_cause", "misattribution_probe")
+
+
+def _evidence_section(user):
+    return user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]
+
+
+def _undecided(key, *, case, shape, evidence, seed=5):
+    n = names_mod.draw(random.Random(seed))
+    return cases._undecided_example(_entry(key), n, case=case, shape=shape,
+                                    evidence=evidence), n
+
+
+def test_the_refuted_shape_has_a_header_a_fresh_read_and_the_describe_read():
+    ex, n = _undecided("memory-limit-oomkill", case="wrong_attribution",
+                       shape="refuted", evidence="clear")
+    section = _cand_section(ex.user)
+    assert "[confidence: high]" in section
+    assert ": attributed — " in section
+    assert "fresh read: refuted — " in section
+    evidence = _evidence_section(ex.user)
+    # Object reads first, then the log read: kubeagent's own order.
+    assert evidence.index("== describe node /") < evidence.index(
+        f"== log causes {n.ns}/{n.pod} container {n.container} ==")
+
+
+def test_the_ruled_out_shape_has_no_header_no_fresh_read_and_no_object_read():
+    ex, n = _undecided("crashloop-pod", case="own_cause", shape="ruled_out",
+                       evidence="clear")
+    assert "[confidence:" not in ex.user
+    assert ": attributed" not in _cand_section(ex.user)
+    assert "fresh read:" not in ex.user
+    assert _evidence_section(ex.user) == (
+        f"== log causes {n.ns}/{n.pod} container {n.container} ==\n"
+        "log cause: bad command or entrypoint")
+
+
+def test_a_ruled_out_row_outside_the_crash_family_has_an_empty_evidence_section():
+    """kubeagent would still show the per-workload events read here. Every
+    job-2 builder lacks that read; adding it is Spec 3."""
+    ex, _ = _undecided("probe-failure", case="own_cause", shape="ruled_out",
+                       evidence="clear")
+    assert _evidence_section(ex.user) == "(none)"
+
+
+@pytest.mark.parametrize(("key", "header"), [
+    ("deployment-bad-image-tag", "medium"),  # a registry cause; the entry says high
+    ("networkpolicy-deny-all", "high"),      # a node cause; the entry says medium
+    ("probe-failure", "high"),               # a node cause; the entry says medium
+    ("restart-loop", "high"),                # a node cause; the entry says medium
+    ("memory-limit-oomkill", "high"),        # the rule and the entry agree
+])
+def test_the_refuted_header_follows_kubeagents_rule_not_the_entry(key, header):
+    ex, _ = _undecided(key, case="wrong_attribution", shape="refuted", evidence="clear")
+    assert f"[confidence: {header}]" in _cand_section(ex.user)
+
+
+@pytest.mark.parametrize("key", cases.THIN_ENTRIES)
+@pytest.mark.parametrize("shape", SHAPES)
+def test_a_thin_row_names_no_cause_and_answers_none_of_these_at_low(key, shape):
+    ex, _ = _undecided(key, case="none_of_these", shape=shape, evidence="thin")
+    assert "log cause:" not in ex.user
+    (row,) = json.loads(ex.assistant)["verdicts"]
+    assert (row["cause"], row["confidence"]) == (c.NONE_OF_THESE, "low")
+    assert row["rationale"] == {
+        "refuted": "A fresh read refutes the attributed cause, and no read names another.",
+        "ruled_out": "Every candidate was ruled out, and no read names a cause.",
+    }[shape]
+    assert (ex.meta["expected_cause"], ex.meta["expected_confidence"]) == (
+        c.NONE_OF_THESE, "low")
+
+
+@pytest.mark.parametrize("key", cases.THIN_ENTRIES)
+@pytest.mark.parametrize("shape", SHAPES)
+def test_a_thin_entrys_clear_row_names_the_cause_its_thin_row_drops(key, shape):
+    clear, _ = _undecided(key, case="wrong_attribution" if shape == "refuted" else "own_cause",
+                          shape=shape, evidence="clear")
+    thin, _ = _undecided(key, case="none_of_these", shape=shape, evidence="thin")
+    assert "log cause:" in clear.user
+    assert clear.user != thin.user
+
+
+def test_thin_evidence_raises_for_every_entry_outside_the_thin_set():
+    n = names_mod.draw(random.Random(5))
+    outside = [e for e in catalog.trainable() if e.key not in cases.THIN_ENTRIES]
+    assert len(outside) == 15
+    for e in outside:
+        for shape in SHAPES:
+            with pytest.raises(ValueError, match=f"{e.key} is not a thin entry"):
+                cases._undecided_example(e, n, case="none_of_these", shape=shape,
+                                         evidence="thin")
+
+
+@pytest.mark.parametrize(("case", "evidence"), [
+    ("none_of_these", "clear"), ("own_cause", "thin"), ("wrong_attribution", "thin"),
+    ("misattribution_probe", "thin"), ("own_cause", "vague"),
+])
+def test_thin_evidence_is_the_none_of_these_case_and_only_it(case, evidence):
+    n = names_mod.draw(random.Random(5))
+    with pytest.raises(ValueError, match=f"{case} takes .* evidence, not '{evidence}'"):
+        cases._undecided_example(_entry("crashloop-pod"), n, case=case, shape="refuted",
+                                 evidence=evidence)
+
+
+def test_undecided_example_refuses_an_unknown_shape_or_case():
+    n = names_mod.draw(random.Random(5))
+    with pytest.raises(ValueError, match="shape must be 'refuted' or 'ruled_out'"):
+        cases._undecided_example(_entry("crashloop-pod"), n, case="own_cause",
+                                 shape="decided", evidence="clear")
+    with pytest.raises(ValueError, match="not an undecided case: 'attributed'"):
+        cases._undecided_example(_entry("crashloop-pod"), n, case="attributed",
+                                 shape="refuted", evidence="clear")
+
+
+@pytest.mark.parametrize("shape", SHAPES)
+def test_the_prompt_never_depends_on_the_case(shape):
+    for e in catalog.trainable():
+        n = names_mod.draw(random.Random(5))
+        users = {cases._undecided_example(e, n, case=case, shape=shape, evidence="clear").user
+                 for case in CLEAR_CASES}
+        assert len(users) == 1, e.key
+
+
+def test_the_public_builders_give_one_prompt_one_answer():
+    """Build every undecided row for one entry and one set of names, the
+    way generate.py calls them. Until 2026-09-24, none_of_these_case and
+    wrong_attribution built the same prompt with different answers for
+    every trainable entry. A random draw of names rarely makes two
+    dataset rows collide, so this test builds the collision on purpose."""
+    for e in catalog.trainable():
+        n = names_mod.draw(random.Random(5))
+        rows = [cases.wrong_attribution(e, n), cases.own_cause_case(e, n),
+                cases.misattribution_probe(e, n)]
+        if e.key in cases.THIN_ENTRIES:
+            rows += [cases.none_of_these_case(e, n, shape=shape) for shape in SHAPES]
+        answers: dict[str, set] = {}
+        for ex in rows:
+            gold = json.loads(ex.assistant)["verdicts"]
+            answers.setdefault(ex.user, set()).add(tuple(sorted(
+                (v["workload"], v["cause"], v["confidence"]) for v in gold)))
+        assert all(len(a) == 1 for a in answers.values()), e.key
+
+
+@pytest.mark.parametrize("case", CLEAR_CASES)
+@pytest.mark.parametrize("shape", SHAPES)
+def test_a_clear_row_answers_the_own_cause_at_the_entrys_confidence(case, shape):
+    for e in catalog.trainable():
+        n = names_mod.draw(random.Random(5))
+        ex = cases._undecided_example(e, n, case=case, shape=shape, evidence="clear")
+        (row,) = json.loads(ex.assistant)["verdicts"]
+        assert row["cause"] == cases._fmt(e.own_cause, n) == ex.meta["expected_cause"]
+        assert row["confidence"] == ("high" if e.direct else "medium") \
+            == ex.meta["expected_confidence"], e.key
+
+
+@pytest.mark.parametrize(("case", "suffix", "last_line"), [
+    ("wrong_attribution",
+     " The deterministic pass attributed a different cause, but the evidence supports this one.",
+     "The deterministic pass attributed a different cause."),
+    ("own_cause", " The candidate list shown did not include this cause.",
+     "The deterministic pass did not consider this cause."),
+    ("misattribution_probe", "", None),
+])
+def test_each_clear_case_keeps_its_own_wording(case, suffix, last_line):
+    e = _entry("crashloop-pod")
+    n = names_mod.draw(random.Random(5))
+    ex = cases._undecided_example(e, n, case=case, shape="ruled_out", evidence="clear")
+    doc = json.loads(ex.assistant)
+    assert doc["verdicts"][0]["rationale"] == cases._fmt(e.rationale, n) + suffix
+    want = last_line or cases._fmt(e.recommendation, n).capitalize() + "."
+    assert doc["summary"] == f"{n.ns}/{n.name} is failing: {cases._fmt(e.own_cause, n)}.\n{want}"
+
+
+def test_each_case_keeps_its_own_meta_keys():
+    """Only `own_cause` carries `expected_own_keywords`; only
+    `wrong_attribution` and `misattribution_probe` carry `decoy_cause`, the
+    length-gap decider's population. Kept as they were."""
+    n = names_mod.draw(random.Random(5))
+    e = _entry("crashloop-pod")
+    keys = {case: set(cases._undecided_example(e, n, case=case, shape="refuted",
+                                               evidence="clear").meta)
+            for case in CLEAR_CASES}
+    keys["none_of_these"] = set(cases.none_of_these_case(e, n, shape="refuted").meta)
+    assert {case: ("expected_own_keywords" in k, "decoy_cause" in k)
+            for case, k in keys.items()} == {
+        "wrong_attribution": (False, True), "own_cause": (True, False),
+        "misattribution_probe": (False, True), "none_of_these": (False, False)}
+
+
+def test_the_menu_keeps_trace_order():
+    """No shuffle: kubeagent prints candidates in trace order, and the answer
+    is on no candidate line, so position gives nothing away. The order is the
+    entry's declared order, node then PVC, on every draw."""
+    e = _entry("worker-containerd-stop")
+    for build in (cases.wrong_attribution, cases.own_cause_case):
+        orders = {tuple(ln.split()[1] for ln in _cand_lines(
+            build(e, names_mod.draw(random.Random(s))).user)) for s in range(20)}
+        assert orders == {("node", "PVC")}, build.__name__
+
+
+@pytest.mark.parametrize(("key", "content"), [
+    ("memory-limit-oomkill", _NO_CLASSIFIABLE),
+    ("container-start-error", _NO_PREVIOUS),
+    ("worker-containerd-stop", _NO_PREVIOUS),
+])
+@pytest.mark.parametrize("shape", SHAPES)
+def test_a_neutral_log_line_appears_in_clear_rows_too(key, content, shape):
+    """So a neutral line is not, by itself, a sign to abstain."""
+    ex, n = _undecided(key, case="own_cause", shape=shape, evidence="clear")
+    assert content.format(ns=n.ns, pod=n.pod, container=n.container) in \
+        _evidence_section(ex.user)
+
+
+def test_each_wrapper_is_its_shape_and_evidence():
+    e = _entry("crashloop-pod")
+    n = names_mod.draw(random.Random(5))
+
+    def built(case, shape, evidence):
+        return cases._undecided_example(e, n, case=case, shape=shape, evidence=evidence)
+
+    assert cases.wrong_attribution(e, n) == built("wrong_attribution", "refuted", "clear")
+    assert cases.own_cause_case(e, n) == built("own_cause", "ruled_out", "clear")
+    assert cases.misattribution_probe(e, n) == built("misattribution_probe", "ruled_out", "clear")
+    for shape in SHAPES:
+        assert cases.none_of_these_case(e, n, shape=shape) == \
+            built("none_of_these", shape, "thin")
diff --git a/tests/test_evidence_overlap.py b/tests/test_evidence_overlap.py
index e9dc033..bdd9a85 100644
--- a/tests/test_evidence_overlap.py
+++ b/tests/test_evidence_overlap.py
@@ -59,15 +59,24 @@ DECLARED = {
     # Reuses attributed's reads by design -- the candidate menu is the only
     # perturbation, which IS the whole measurement. Costs nothing.
     "positional_probe": (20, 20),
-    "misattribution_probe": (14, 20),
+    # Since 2026-09-24 this probe builds `own_cause`'s ruled-out prompt: no
+    # object reads, and one log read on each of the five crash-family
+    # entries. All five are reused, from `own_cause` and `wrong_attribution`
+    # training rows, by design: the probe asks the same question those rows
+    # train. The other fourteen rows render no reads. It read (14, 20) when
+    # its menu still carried describe reads.
+    "misattribution_probe": (5, 5),
     # Same, in the multi shape: _reads(e, n)[:2] per constituent.
     "multi_misattribution_probe": (39, 40),
-    # THIS ROW IS THE POINT OF THE INSTRUMENT. It reuses none_of_these_case's
-    # read text verbatim, and none_of_these is a fixed 15% of every curriculum
-    # via CASE_MIX -- which is why this slice cannot catch a model reciting an
-    # entry-lookup table. Negative control v4 measured the known-broken first
-    # tune at 1.0 cause / 0.0 decoy here. When that confound is closed this
-    # becomes 0/19 and this entry must be deleted, not updated.
+    # THIS ROW WAS THE POINT OF THE INSTRUMENT. It was written to catch this
+    # slice reusing none_of_these_case's read text, which is why the slice
+    # cannot catch a model reciting an entry-lookup table. Negative control v4
+    # measured the known-broken first tune at 1.0 cause / 0.0 decoy here.
+    # Re-measured 2026-09-24, per read: all 19 hits are the generic describe
+    # reads ("node worker-2: unschedulable=false", a PVC's phase line) that
+    # most refuted-menu training rows also render, and none of the 19
+    # contradiction lines is reused. That was already so before
+    # `none_of_these` moved to thin evidence, which left the count at 19.
     # It read 17/19 while `attributed` held 26% of the mix. Raising the two
     # shared-origin halves from 4% to 8% took the budget out of `attributed`,
     # which moved every later random draw, and one `none_of_these` training
@@ -119,7 +128,12 @@ DECLARED = {
 
 
 def _reads(ex) -> list[str]:
-    """Split a rendered evidence block into its individual reads."""
+    """Split a rendered evidence block into its individual reads.
+
+    An empty block, rendered "(none)", has no reads. It is never hashed:
+    the literal "(none)" would make every empty row collide with every
+    other one regardless of content.
+    """
     user = ex.user
     start = user.find(BEGIN)
     end = user.find(END, start)
@@ -127,10 +141,8 @@ def _reads(ex) -> list[str]:
         f"a {ex.case} row has no delimited evidence block; the guard refuses "
         f"to score a shape it cannot read")
     body = user[start + len(BEGIN):end]
-    assert body.strip() != "(none)", (
-        f"a {ex.case} row rendered an empty evidence block; the guard refuses "
-        f"to score it rather than hashing the literal '(none)', which would "
-        f"make every such row collide with every other regardless of content")
+    if body.strip() == "(none)":
+        return []
     return [part for part in READ_DELIM.split(body) if part.strip()]
 
 
@@ -171,26 +183,28 @@ def _fake(user: str) -> generate.Example:
                             system="", user=user, assistant="", meta={})
 
 
-# `_reads` carries two refusals, and BOTH are unreachable on today's tree --
-# measured over every row the guard can reach, 7029 kept + 263 test = 7292,
-# all of which render a delimited, non-empty evidence block. That is the
-# superset: the allowlist test below actually calls `_reads` on 7125 of them,
-# because it reads only the six DECLARED slices out of the test set.
-# Unreachable is exactly why they need tests: deleting
-# either assert changes no other test's outcome, so without these two the
-# guards are the vacuous shape this whole branch exists to prevent. They
-# assert the REFUSAL, not a value, because a refusal is the entire
-# behaviour: hashing an undelimited row would silently score zero reads, and
-# hashing the literal "(none)" would make every empty row collide with every
-# other one regardless of content -- a 100% reuse count that means nothing.
+# `_reads` refuses one shape and is unreachable on today's tree: every row
+# the guard can reach renders a delimited evidence block. Unreachable is why
+# it needs a test: deleting the assert changes no other test's outcome. It
+# asserts the REFUSAL, not a value, because hashing an undelimited row would
+# silently score zero reads.
+#
+# An EMPTY block is reachable, and has been since 2026-09-24: a ruled-out
+# row outside the crash family has no object read and no log read, so it
+# renders "(none)". Measured at SEED/SIZE: 725 of 7135 kept rows and 30 of
+# 252 test rows, 14 of them in the DECLARED `misattribution_probe` slice.
+# (kubeagent would still show its per-workload events read there; adding
+# that read to the generator is later work.) Such a row has no reads, so it
+# adds nothing to the trained set and nothing to a slice's count. The
+# `assert pairs` in the allowlist test still fails a slice that goes wholly
+# empty.
 def test_reads_refuses_a_row_with_no_delimited_evidence_block():
     with pytest.raises(AssertionError, match="no delimited evidence block"):
         _reads(_fake("a user turn that never opens an evidence section"))
 
 
-def test_reads_refuses_an_empty_evidence_block_rather_than_hashing_none():
-    with pytest.raises(AssertionError, match="empty evidence block"):
-        _reads(_fake(f"{BEGIN}(none){END}"))
+def test_reads_gives_no_reads_for_an_empty_evidence_block_rather_than_hashing_none():
+    assert _reads(_fake(f"{BEGIN}(none){END}")) == []
 
 
 def test_reads_splits_a_well_formed_block_into_its_reads():
diff --git a/tests/test_exam_graded_view.py b/tests/test_exam_graded_view.py
index d72590c..c8aaf34 100644
--- a/tests/test_exam_graded_view.py
+++ b/tests/test_exam_graded_view.py
@@ -11,8 +11,10 @@ about `expected_cause` job 2 switches on (exact match vs. keyword
 match).
 
 Two gold fields do survive, at the top of `meta`, where a
-single-workload row mirrors them: `expected_cause` on 224 of the 263
-rows and `expected_confidence` on 234. This view keeps both. That makes
+single-workload row mirrors them: `expected_cause` on 213 of the 252
+rows and `expected_confidence` on 223 (224 and 234 of 263 before the
+2026-09-24 generator fix removed 11 `none_of_these` rows). This view
+keeps both. That makes
 the pin stricter than the gated numbers need, never looser: a gold
 cause or confidence that moved on one of those rows fails this test
 instead of slipping past it. So the ungated extras -- cause accuracy,
@@ -21,7 +23,7 @@ partly free to move. They read those two fields, and a row that carries
 one of them is pinned on it.
 
 `GRADED_VIEW_SHA256` pins the sha256 of that view over the whole exam
-(`generate.test_set()`, 263 rows). This is not a TDD red test: it
+(`generate.test_set()`, 252 rows since 2026-09-24; 263 before). This is not a TDD red test: it
 passes today, before the training-targets fix, because the fix only
 touches shared-origin rows, and this view keeps none of the fields it
 changes there -- their gold cause lives in the `meta["expected"]` dict.
@@ -43,6 +45,9 @@ Re-pinned on 2026-09-24 for the job-2 generator fix
 moves, and this view keeps it whole, so the digest follows every rendered
 change `FROZEN_SLICE_SHA256`'s 2026-09-24 entry lists in
 `tests/test_shared_origin_training.py`. The new exam is a new baseline.
+It moved twice on that branch: once for the catalogue's log-cause text,
+once for the single undecided builder, which also cut the exam from 263
+rows to 252.
 """
 
 from __future__ import annotations
@@ -69,7 +74,7 @@ def view(row):
             "flagged": [v["workload"] for v in gold["verdicts"]]}
 
 
-GRADED_VIEW_SHA256 = "100ec57cebcc2d8c25c62466116e7886a2689faea071f25d6e47acecbf76412d"
+GRADED_VIEW_SHA256 = "046bf2b87b20aa20ebb79ca6ee199a47d9f8f54e25f42df76894033df09063a5"
 
 
 def _digest(views) -> str:
diff --git a/tests/test_generate.py b/tests/test_generate.py
index 3a2d7d7..9d61831 100644
--- a/tests/test_generate.py
+++ b/tests/test_generate.py
@@ -264,16 +264,26 @@ def test_provenance_scan_reaches_every_catalog_entry():
             by_case.setdefault(ex.case, set()).add(entry)
 
     # `own_cause` is the only case that renders an entry's `own_cause` text;
-    # `none_of_these` and `contradiction_probe` are the only ones that render
-    # its `contradiction` text. Full coverage on these three is what carries
-    # every entry's per-entry prose through the scan.
-    for case in ("own_cause", "none_of_these", "contradiction_probe"):
+    # `contradiction_probe` is the only one that renders its `contradiction`
+    # text. Full coverage on these two is what carries every entry's
+    # per-entry prose through the scan.
+    for case in ("own_cause", "contradiction_probe"):
         assert by_case.get(case) == trainable, (
             f"{case} renders {len(by_case.get(case, ()))} of {len(trainable)} "
             f"trainable entries; missing {sorted(trainable - by_case.get(case, set()))}"
         )
     assert set().union(*by_case.values()) == trainable
 
+    # Until 2026-09-24 `none_of_these` rendered the `contradiction` text too,
+    # for every entry. The job-2 generator fix builds it from thin evidence
+    # instead: four entries, one row per undecided shape, and a fixed
+    # rationale that names no entry's prose.
+    thin = collections.Counter(
+        (ex.meta["entry"], "refuted" if "fresh read: refuted" in ex.user else "ruled_out")
+        for ex in generate.test_set() if ex.case == "none_of_these")
+    assert thin == {(key, shape): 1 for key in cases.THIN_ENTRIES
+                    for shape in ("refuted", "ruled_out")}
+
 
 def test_test_set_slice_counts_are_pinned():
     """Every probe rate's denominator, pinned.
@@ -288,6 +298,14 @@ def test_test_set_slice_counts_are_pinned():
     append leaves the earlier rows at their original indices — which is what
     lets a scoreboard banked against the shorter file still line up row for
     row over the slices it shares.
+
+    2026-09-24 broke that rule once, on purpose. The job-2 generator fix
+    rebuilt `none_of_these` from thin evidence on four entries, so the slice
+    fell from 19 rows to 8. Those rows sit inside the held-out block, one
+    entry at a time, so rows moved from the first changed entry onward and
+    the probe slices after the block moved up 11 places. A scoreboard
+    banked before that date does not line up row for row with this exam;
+    the frozen-slice and eval-set hashes moved with it.
     """
     counts = collections.Counter(ex.case for ex in generate.test_set())
     assert dict(counts) == {
@@ -297,7 +315,7 @@ def test_test_set_slice_counts_are_pinned():
         "injection": 19,
         "misattribution_probe": 19,
         "multi_misattribution_probe": 19,
-        "none_of_these": 19,
+        "none_of_these": 8,
         "own_cause": 19,
         "positional_probe": 19,
         "shared_origin_decoy_probe": 10,
@@ -305,7 +323,7 @@ def test_test_set_slice_counts_are_pinned():
         "truncated": 19,
         "wrong_attribution": 19,
     }
-    assert sum(counts.values()) == 263
+    assert sum(counts.values()) == 252
 
 
 def test_the_job2_keyword_exposure_is_pinned_per_case():
@@ -456,9 +474,10 @@ def test_job_population_counts_match_the_pinned_exam_shape():
     # job1 and job2 are measured, not derived -- R40 states them as "about 70"
     # and "about 210"; Step 51's actual measurement over the v1.24.0 exam
     # printed 157 and 153, so those are the pinned literals, not R40's
-    # rounded figures.
+    # rounded figures. job2 fell from 153 to 142 on 2026-09-24: the job-2
+    # generator fix cut the `none_of_these` slice from 19 rows to 8.
     assert job1 == 157
-    assert job2 == 153
+    assert job2 == 142
     assert job3_prompts == 39
     assert job3_labels == {"shared": 5, "separate": 0, "none": 34}
 
@@ -677,3 +696,28 @@ def test_the_length_gap_decider_has_rows_in_both_slices():
     assert len(measured) == 57
     assert sum(1 for m in measured if m) > 0
     assert sum(1 for m in measured if not m) > 0
+
+
+def test_one_prompt_has_one_answer():
+    """No two rows share a user prompt but differ in what they expect.
+
+    Before the 2026-09-24 generator fix, `wrong_attribution` and
+    `none_of_these` could print the same prompt and expect opposite answers:
+    the entry's own cause at one confidence, or `none_of_these` at another.
+    Gradient descent cannot fit both, and the model learned a coin flip for
+    exactly the rows the exam's job 2 grades hardest. The prompt now depends
+    only on (entry, names, shape, evidence), never on the case, so this
+    holds by construction; this test is what keeps it holding.
+
+    Checked over the full training build and the exam together, because a
+    collision across the two is the same contradiction. Rationales and
+    summaries may differ -- they are not graded.
+    """
+    rows = generate.generate(seed=17, size=8000) + generate.test_set()
+    answers: dict[str, set] = collections.defaultdict(set)
+    for ex in rows:
+        gold = json.loads(ex.assistant)["verdicts"]
+        answers[ex.user].add(tuple(sorted(
+            (v["workload"], v["cause"], v["confidence"]) for v in gold)))
+    clashes = {prompt[:200]: sorted(a) for prompt, a in answers.items() if len(a) > 1}
+    assert not clashes, clashes
diff --git a/tests/test_oracle.py b/tests/test_oracle.py
index 4cf42ba..414a119 100644
--- a/tests/test_oracle.py
+++ b/tests/test_oracle.py
@@ -126,23 +126,30 @@ def test_oracle_job1_is_perfect_on_train():
     board = score.scoreboard(list(_train_results()))
     # Re-measured 2026-09-19 (Task 9: pool merge + mix change, spec section
     # 6) -- 2570 to 3056. Rate unchanged at 1.0.
-    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3056}
+    # Re-measured 2026-09-24 (job-2 generator fix: the undecided builders no
+    # longer draw from the rng, which moves every later draw, and the
+    # held-out `none_of_these` slice is 8 groups, not 19) -- 3056 to 3081.
+    # Rate unchanged.
+    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3081}
 
 
 def test_oracle_job1_is_perfect_on_val():
     board = score.scoreboard(list(_val_results()))
     # Re-measured 2026-09-19, same reason. 289 to 355. Rate unchanged.
-    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 355}
+    # Re-measured 2026-09-24, job-2 generator fix. 355 to 357. Rate unchanged.
+    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 357}
 
 
 def test_oracle_job2_gate_is_perfect_on_train():
     # Re-measured 2026-09-19, same reason. 3121 to 2975. Rate unchanged.
-    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 2975}
+    # Re-measured 2026-09-24, job-2 generator fix. 2975 to 3000. Rate unchanged.
+    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3000}
 
 
 def test_oracle_job2_gate_is_perfect_on_val():
     # Re-measured 2026-09-19, same reason. 352 to 304. Rate unchanged.
-    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 304}
+    # Re-measured 2026-09-24, job-2 generator fix. 304 to 321. Rate unchanged.
+    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 321}
 
 
 def test_oracle_job2_keyword_only_matches_the_spec_measurement():
@@ -150,8 +157,11 @@ def test_oracle_job2_keyword_only_matches_the_spec_measurement():
     After it, this narrower slice is also perfect.
 
     Re-measured 2026-09-19 (Task 9: pool merge + mix change, spec section
-    6) -- 2175 to 2286. Rate still 1.0."""
-    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2286}
+    6) -- 2175 to 2286. Rate still 1.0.
+
+    Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
+    above) -- 2286 to 2324. Rate still 1.0."""
+    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2324}
 
 
 def test_oracle_job3_is_perfect_on_train():
@@ -170,13 +180,17 @@ def test_oracle_job3_is_perfect_on_train():
     This test now covers those ruled rows too: the gold summary for each
     of them still matches its own label, so `shared`'s rate stays a
     perfect 1.0 here -- spec section 10 gate 1, job 1 and job 3 still 1.0
-    after the pool merge."""
+    after the pool merge.
+
+    Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
+    above) -- 2790 to 2803; all 13 new rows are `none`-labeled. Rate still
+    1.0."""
     board = score.scoreboard(list(_train_results()))
     assert board["jobs"]["job3"] == {
-        "rate": 1.0, "n": 2790,
+        "rate": 1.0, "n": 2803,
         "by_label": {"shared": {"rate": 1.0, "n": 192},
                      "separate": {"rate": 1.0, "n": 1},
-                     "none": {"rate": 1.0, "n": 2597}}}
+                     "none": {"rate": 1.0, "n": 2610}}}
 
 
 def test_oracle_job3_is_perfect_on_val():
@@ -197,12 +211,17 @@ def test_oracle_multi_job1_matches_the_spec_measurement():
 
     Re-measured 2026-09-19 (Task 9: the `multi` share of the mix rose from
     11% to 13%, spec section 6) -- 996 of 996 to 1209 of 1209 in train, 121
-    of 121 to 145 of 145 in val. Still perfect."""
+    of 121 to 145 of 145 in val. Still perfect.
+
+    Re-measured 2026-09-24 (job-2 generator fix: the undecided builders no
+    longer draw from the rng, so every `multi` row draws new names, and the
+    held-out `none_of_these` slice is 8 groups, not 19) -- 1209 to 1227 in
+    train; val unchanged at 145. Still perfect."""
     def multi_job1(results):
         scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
         return sum(scores), len(scores)
 
-    assert multi_job1(_train_results()) == (1209.0, 1209)
+    assert multi_job1(_train_results()) == (1227.0, 1227)
     assert multi_job1(_val_results()) == (145.0, 145)
 
 
@@ -247,7 +266,10 @@ def test_exam_oracle_job2_is_perfect():
     -- was the one nobody pinned, and 20 of its 153 workloads scored 0.0
     against their own gold answer because their grading keywords were empty.
     A ceiling below 1.0 here means the corpus, not the model, is at fault.
+
+    Re-measured 2026-09-24 (job-2 generator fix: the exam's `none_of_these`
+    slice is 8 thin-evidence rows, not 19) -- 153 to 142. Still perfect.
     """
     _, results = _exam()
     board = score.scoreboard(list(results))
-    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 153}
+    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 142}
diff --git a/tests/test_probe_cousins.py b/tests/test_probe_cousins.py
index 7a17216..6e16c4f 100644
--- a/tests/test_probe_cousins.py
+++ b/tests/test_probe_cousins.py
@@ -101,8 +101,10 @@ def test_cousin_probe_is_deterministic():
 def test_cousin_probe_is_not_in_the_exam():
     # Its own file, never the frozen exam: no cousin row shares an origin
     # with any exam row, and the exam's row count does not move.
+    # 263 to 252 on 2026-09-24: the job-2 generator fix cut the exam's
+    # `none_of_these` slice from 19 rows to 8. The cousin probe added none.
     exam = generate.test_set()
-    assert len(exam) == 263
+    assert len(exam) == 252
     exam_origins = {ex.meta.get("origin") for ex in exam
                     if ex.case in ("shared_origin_probe",
                                    "shared_origin_decoy_probe")}
diff --git a/tests/test_score.py b/tests/test_score.py
index f59e4df..127e47b 100644
--- a/tests/test_score.py
+++ b/tests/test_score.py
@@ -1848,8 +1848,11 @@ def test_empty_reply_bot_scores_zero_on_every_job_with_full_n():
     assert board["jobs"]["job3"]["n"] == expected_job3_n
     # The two numbers the spec and the model card name. A corpus change that
     # moves them fails here instead of quietly restating a bar.
+    # Re-pinned 2026-09-24 for the job-2 generator fix: the exam's
+    # `none_of_these` slice is 8 thin-evidence rows, not 19, so job 2 falls
+    # from 153 to 142. Job 1 is untouched.
     assert expected_job1_n == 157
-    assert expected_job2_n == 153
+    assert expected_job2_n == 142
 
 
 def _echo_the_decided_cause_bot(rows: list[dict]):
@@ -1990,7 +1993,9 @@ def test_a_regex_copier_scores_the_job1_ceiling_the_model_card_states():
     board = score.scoreboard(results)
 
     assert board["jobs"]["job1"] == {"rate": 1.0, "n": 157}
-    assert board["jobs"]["job2"] == {"rate": 0.0, "n": 153}
+    # 153 to 142 on 2026-09-24: the job-2 generator fix left 8
+    # `none_of_these` rows in the exam, not 19.
+    assert board["jobs"]["job2"] == {"rate": 0.0, "n": 142}
 
 
 def _always_none_of_these_bot(rows: list[dict]):
@@ -2033,13 +2038,20 @@ def test_always_none_of_these_bot_scores_well_under_the_job2_bar():
     bot that always says "none of these" scores far below the job2 bar --
     is asserted on its own so it never depends on getting the exact figure
     right.
+
+    Re-pinned on 2026-09-24 for the job-2 generator fix
+    (2026-09-24-job2-generator-fix-design.md). `none_of_these` is now built
+    only from the four entries with thin evidence, once per undecided shape,
+    so the exam holds 8 such rows, not 19. 8 of the 142 undecided workloads
+    expect `none_of_these`, and this bot scores 8/142 = 0.0563. The
+    paragraphs above are the older account.
     """
     rows = _corpus_rows()
     results = score.evaluate(rows, _always_none_of_these_bot(rows))
     board = score.scoreboard(results)
 
     assert board["jobs"]["job2"]["n"] > 0
-    assert board["jobs"]["job2"]["rate"] == pytest.approx(0.1242, abs=0.005)
+    assert board["jobs"]["job2"]["rate"] == pytest.approx(0.0563, abs=0.005)
     assert board["jobs"]["job2"]["rate"] < score.JOB2_BAR
 
 
@@ -2087,6 +2099,13 @@ def test_paste_the_prompt_bot_measures_the_job2_keyword_ceiling():
     The bot still scores below JOB2_BAR, but the margin narrows from 0.334
     to 0.203 -- so any future proposal to lower that bar now has a hard
     floor of 0.50, not 0.37. Below 0.50, a bot that reads nothing passes.
+
+    Re-pinned on 2026-09-24 for the job-2 generator fix
+    (2026-09-24-job2-generator-fix-design.md). The exam loses 11
+    `none_of_these` workloads, none of them keyword-graded, so the 76 and
+    the 134 stay and the denominator falls from 153 to 142: 76/142 =
+    0.5352. The margin under JOB2_BAR narrows again, from 0.203 to 0.165,
+    and the floor for any proposal to lower the bar rises to 0.54.
     """
     rows = _corpus_rows()
     results = score.evaluate(rows, _paste_the_prompt_bot(rows))
@@ -2094,8 +2113,8 @@ def test_paste_the_prompt_bot_measures_the_job2_keyword_ceiling():
 
     assert board["overall"]["keyword_derivable_n"] == 76
     assert board["overall"]["keyword_graded_n"] == 134
-    assert board["jobs"]["job2"]["n"] == 153
-    assert board["jobs"]["job2"]["rate"] == pytest.approx(0.497, abs=0.005)
+    assert board["jobs"]["job2"]["n"] == 142
+    assert board["jobs"]["job2"]["rate"] == pytest.approx(0.535, abs=0.005)
     assert board["jobs"]["job2"]["rate"] < score.JOB2_BAR
 
 
@@ -2133,9 +2152,10 @@ def test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row():
     row's `job2_scores` grade the same workloads by the same rule, so they
     must agree for any reply. The own-keyword bot is a reply that tells them
     apart when they do not: before the 2026-09-24 generator fix it disagreed
-    on 64 of these 121 rows, every `wrong_attribution`,
+    on 64 of the 121 rows then checked, every `wrong_attribution`,
     `misattribution_probe`, `multi_misattribution_probe` and shared-origin
-    probe row among them."""
+    probe row among them. The same fix cut the exam's `none_of_these` slice
+    from 19 rows to 8, so 110 rows are checked now."""
     rows = _corpus_rows()
     results = score.evaluate(rows, _own_keyword_bot(rows))
     checked = 0
@@ -2146,7 +2166,7 @@ def test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row():
         checked += 1
         assert res["cause_acc"] == pytest.approx(
             sum(res["job2_scores"]) / len(res["job2_scores"])), row["meta"]["case"]
-    assert checked == 121
+    assert checked == 110
 
 
 def _rewrite_keyword_answer_keys(rows: list[dict], token: str) -> tuple[list[dict], int]:
@@ -2282,7 +2302,11 @@ def test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest
     a word the reply does not contain, the only job-2 workloads left to win
     are the 19 whose answer is `none_of_these`, which is the exact set that
     bot wins. 19/153 = 0.1242 either way. If the corpus's `none_of_these`
-    count moves, both tests move together.
+    count moves, both tests move together -- and on 2026-09-24 it did: the
+    job-2 generator fix left 8 such rows, so both read 8/142 = 0.0563.
+    Cause accuracy moves with it, 0.5387 to 0.5185 before the rewrite and
+    0.1445 to 0.1071 after: the 11 removed rows were all right both times,
+    and the population falls from 263 rows to 252.
 
     Re-pinned on 2026-09-23 for the exam-grader fix
     (2026-09-23-exam-grader-fix-design.md). `workload_level` moves from 114
@@ -2306,7 +2330,8 @@ def test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest
     job-2 workload in the corpus. Before the fix, the 20 shared-origin
     workloads' real answer was never `none_of_these`, so the bot's
     `none_of_these` fallback missed all 20 of them: 114 + 19 = 133,
-    133/153 = 0.8693.
+    133/153 = 0.8693. (Since the 2026-09-24 generator fix the corpus holds 8
+    `none_of_these` workloads, not 19: 134 + 8 = 142, still every one.)
     """
     rows = _corpus_rows()
     bot = _own_keyword_bot(rows)          # replies pinned to today's keys
@@ -2325,9 +2350,9 @@ def test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest
 
     # Four numbers retire: the same replies now score differently.
     assert before["jobs"]["job2"]["rate"] == pytest.approx(1.0, abs=0.005)
-    assert after["jobs"]["job2"]["rate"] == pytest.approx(0.1242, abs=0.005)
-    assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.5387, abs=0.005)
-    assert after["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.1445, abs=0.005)
+    assert after["jobs"]["job2"]["rate"] == pytest.approx(0.0563, abs=0.005)
+    assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.5185, abs=0.005)
+    assert after["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.1071, abs=0.005)
     assert before["overall"]["overconfidence_rate"]["n"] == 123
     assert after["overall"]["overconfidence_rate"]["n"] == 225
     assert before["overall"]["cause_when_length_helps"] == {"rate": 0.6786, "n": 56}
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index 329c00e..f344934 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -755,22 +755,27 @@ def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
 
 # ------------------------------------------------------ the eval must not move
 
-def test_the_eval_set_is_two_hundred_and_sixty_three_rows():
-    """253 until `shared_origin_decoy_probe` appended its ten.
+def test_the_eval_set_is_two_hundred_and_fifty_two_rows():
+    """253 until `shared_origin_decoy_probe` appended its ten, then 263
+    until the 2026-09-24 job-2 generator fix cut the `none_of_these` slice
+    from 19 rows to 8.
 
     This test exists so the TRAINING half of the shared-origin work cannot
     move the exam by accident — a curriculum change that grows the test set
     invalidates every banked scoreboard silently. It does not forbid moving
     the exam on purpose; the decoy slice did that, in its own commit, with
     `tests/test_shared_origin_decoy_probe.py` proving the training set stayed
-    byte-identical across the change.
+    byte-identical across the change. The 2026-09-24 generator fix moved it
+    on purpose too, and re-pinned both exam digests below in the same
+    commit.
     """
-    assert len(generate.test_set()) == 263
+    assert len(generate.test_set()) == 252
 
 
-# The first 253 rows, byte for byte. From 0830 until 2026-09-16 this pin
-# never moved, and that is what let every scoreboard on the 253 compare
-# against every other. It moved once, on purpose: the node-not-ready and
+# The frozen slice, byte for byte: the first 253 rows until 2026-09-24,
+# the first 242 since (see the fifth entry below). From 0830 until
+# 2026-09-16 this pin never moved, and that is what let every scoreboard on
+# the 253 compare against every other. It moved once, on purpose: the node-not-ready and
 # registry-unreachable builders were rewritten and the system prompt moved
 # out of `contract.py` into `contract/system_prompt.txt`, and both changed
 # the rendered bytes of every row. A number on the 253 measured before that
@@ -827,11 +832,28 @@ def test_the_eval_set_is_two_hundred_and_sixty_three_rows():
 #   rows move, in the user message only: 8 `attributed`, 6
 #   `multi_misattribution_probe`, and 3 in each of the other nine cases
 #   outside the two shared-origin probes.
-FROZEN_SLICE_SHA256 = "1aead0803e798d40fa535300177e5156883c908e4e790255ee685f132da554fa"
-
-# The whole exam, 253 plus the ten `shared_origin_decoy_probe` rows. First
-# captured on `main` @ `ee2980e` as `e8cbb549…b49de`; 0902 and 0905 were
-# scored against that set in one go, 0901 covered the same rows as two runs
+# - One builder now makes every undecided row (`none_of_these`,
+#   `own_cause`, `wrong_attribution`, `misattribution_probe`). The
+#   `none_of_these` slice falls from 19 rows to 8: two for each thin entry
+#   (`crashloop-pod`, `coredns-corefile-broken`, `init-crashloop`,
+#   `restart-loop`), one per undecided shape, answered `none_of_these` at
+#   `low`. The held-out rows interleave by entry, so every row from the
+#   first changed entry on shifts, and the slice ends 11 rows shorter. Of
+#   the rows that stay, keyed by case and group: all 19 `own_cause` rows
+#   change their user message (every candidate is now ruled out, so no
+#   object is read, and crash-family rows gain a log read) and 16 of them
+#   their gold answer and meta (the entry's own confidence, not a flat
+#   `medium`); all 19 `misattribution_probe` rows change their user message
+#   the same way (the decoy is no longer attributed, so the header goes
+#   too); and 9 of 19 `wrong_attribution` rows change their user message (4
+#   take the header kubeagent's confidence rule gives the attributed cause,
+#   the other 5 gain a log read). No other row moves.
+FROZEN_SLICE_SHA256 = "b6f61e68c7615288452b48935031b649f502e21c1fad3ba7c7d7a96f11758294"
+
+# The whole exam, the frozen slice plus the ten `shared_origin_decoy_probe`
+# rows (263 until 2026-09-24, 252 since). First captured on `main` @
+# `ee2980e` as `e8cbb549…b49de`; 0902 and 0905 were scored against that
+# set in one go, 0901 covered the same rows as two runs
 # (which is why its paired join reported `unpaired`), and 0830 predates the
 # ten decoy rows entirely. Re-pinned on 2026-09-05 when `healthy_evidence`
 # corrected the two node-disk-pressure decoy rows (257 and 262), whose
@@ -893,7 +915,7 @@ FROZEN_SLICE_SHA256 = "1aead0803e798d40fa535300177e5156883c908e4e790255ee685f132
 # same job-2 generator fix that moved `FROZEN_SLICE_SHA256` above (see its
 # 2026-09-24 entry). None of the ten `shared_origin_decoy_probe` rows
 # moves, so this digest moves only because the frozen slice inside it does.
-EVAL_SET_SHA256 = "6e1f553be2956b2b5a1217632b4787027875fb3b4c1335f5fcf1e4bc96327ad3"
+EVAL_SET_SHA256 = "ae4e0885d6b0ea705b77794781dd0c4fed37fbb5b32969ab484c2d0564db8c34"
 
 
 def _digest(rows) -> str:
@@ -905,11 +927,12 @@ def _digest(rows) -> str:
 def test_the_frozen_slice_is_every_row_before_the_decoy_probe():
     """The frozen slice is named by what it holds, not by a row number:
     every exam row before the trailing ten `shared_origin_decoy_probe`
-    rows. Its length is pinned here, apart from its digest."""
+    rows. Its length is pinned here, apart from its digest: 253 until the
+    2026-09-24 job-2 generator fix, 242 since."""
     rows = generate.test_set()
     assert [e.case for e in rows[-10:]] == ["shared_origin_decoy_probe"] * 10
     assert "shared_origin_decoy_probe" not in {e.case for e in rows[:-10]}
-    assert len(rows[:-10]) == 253
+    assert len(rows[:-10]) == 242
 
 
 def test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used():
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --continue-on-collection-errors --tb=line -rfE tests/test_cases.py tests/test_evidence_overlap.py tests/test_exam_graded_view.py tests/test_generate.py tests/test_oracle.py tests/test_probe_cousins.py tests/test_score.py tests/test_shared_origin_training.py
```

Expected: the summary line reads `25 failed, 247 passed, 1 error`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_evidence_overlap.py::test_eval_only_evidence_reuse_matches_the_declared_allowlist
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_generate.py::test_provenance_scan_reaches_every_catalog_entry
FAILED tests/test_generate.py::test_test_set_slice_counts_are_pinned
FAILED tests/test_generate.py::test_job_population_counts_match_the_pinned_exam_shape
FAILED tests/test_oracle.py::test_oracle_job1_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_job1_is_perfect_on_val
FAILED tests/test_oracle.py::test_oracle_job2_gate_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_job2_gate_is_perfect_on_val
FAILED tests/test_oracle.py::test_oracle_job2_keyword_only_matches_the_spec_measurement
FAILED tests/test_oracle.py::test_oracle_job3_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_multi_job1_matches_the_spec_measurement
FAILED tests/test_oracle.py::test_exam_oracle_job2_is_perfect
FAILED tests/test_probe_cousins.py::test_cousin_probe_is_not_in_the_exam
FAILED tests/test_score.py::test_empty_reply_bot_scores_zero_on_every_job_with_full_n
FAILED tests/test_score.py::test_a_regex_copier_scores_the_job1_ceiling_the_model_card_states
FAILED tests/test_score.py::test_always_none_of_these_bot_scores_well_under_the_job2_bar
FAILED tests/test_score.py::test_paste_the_prompt_bot_measures_the_job2_keyword_ceiling
FAILED tests/test_score.py::test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row
FAILED tests/test_score.py::test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_two_hundred_and_fifty_two_rows
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_every_row_before_the_decoy_probe
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
ERROR tests/test_cases.py
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-5
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=5 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/cases.py b/src/kubeagent_verdict/dataset/cases.py
index 98e1e92..eaf3aca 100644
--- a/src/kubeagent_verdict/dataset/cases.py
+++ b/src/kubeagent_verdict/dataset/cases.py
@@ -107,7 +107,8 @@ def _finding(e: CatalogEntry, n: Names, with_log_cause: bool = True) -> c.Findin
 
 
 def _workload(e: CatalogEntry, n: Names, candidates: tuple[c.Candidate, ...],
-              confidence: str, *, result: rules.Result) -> c.Workload:
+              confidence: str, *, result: rules.Result,
+              with_log_cause: bool = True) -> c.Workload:
     """Build the rendered workload, decided line included.
 
     `result` is the SAME `rules.Result` the row's meta is built from, in
@@ -116,10 +117,14 @@ def _workload(e: CatalogEntry, n: Names, candidates: tuple[c.Candidate, ...],
     `decided_cause`/`decided_outcome` come from one value, so they cannot
     drift. Job 1 grades a byte-for-byte echo of that cause, so a prompt
     that does not carry the line turns job 1 into a recall test.
+
+    `with_log_cause=False` drops the finding's `log cause:` line. Only a
+    thin-evidence row passes it.
     """
     return c.Workload(
         namespace=n.ns, name=n.name, kind=e.workload_kind, ready=0, desired=2,
-        status=e.status, restarts=n.restarts, findings=(_finding(e, n),),
+        status=e.status, restarts=n.restarts,
+        findings=(_finding(e, n, with_log_cause),),
         candidates=candidates, confidence=confidence,
         network_policies=tuple(_fmt(p, n) for p in e.network_policies),
         decided=result.decided, decided_cause=result.cause,
@@ -345,55 +350,147 @@ def _refuted_menu(n: Names, objects: tuple) -> tuple:
     return tuple(refute(bind(obj, names)) for obj in objects)
 
 
-def none_of_these_case(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
-    menu = _refuted_menu(n, e.objects)
-    raw = rules.attribute(menu, ns=n.ns, pod=n.pod, issue=e.issue)
-    result = rules.decide(raw)  # always undecided: refuted alone never wins
-    candidates = _to_contract_candidates(raw, result)
-    w = _workload(e, n, candidates, confidence=_confidence(e), result=result)
-    reads = object_reads(menu, ns=n.ns, pod=n.pod)
-    user = _user_message(None, None, "", _service_issues(e, n), (w,), reads, key=e.key)
-    rows = [{"workload": f"{n.ns}/{n.name}", "cause": c.NONE_OF_THESE,
-             "confidence": "medium",
-             "rationale": "The evidence contradicts every listed candidate rather than "
-                          "supporting one."}]
-    summary = (f"{n.ns}/{n.name} is failing, but the evidence rules out the listed causes.\n"
-               "A closer look at the workload is needed.")
-    key = f"{n.ns}/{n.name}"
-    wm = workload_meta(result, expected_cause=c.NONE_OF_THESE, own_cause_keywords=[])
-    decoys = [cand.cause for cand in candidates]
-    meta = {"case": "none_of_these", "entry": e.key,
-            "expected_cause": c.NONE_OF_THESE, "expected_confidence": "medium"}
-    meta.update(prompt_meta({key: wm}, label="none", decoy_by_workload={key: decoys}))
-    return Example(case="none_of_these", group=f"{e.key}:{n.ns}/{n.name}",
-                   system=c.SYSTEM_PROMPT, user=user, assistant=_answer(rows, summary),
-                   meta=meta)
+def _ruled_out_menu(n: Names, objects: tuple) -> tuple:
+    """Bind every declared object, then force each one into a ruled-out
+    ending below rules.decide()'s threshold: node placement="off", pvc
+    placement="unmounted", registry scan_reason below REGISTRY_THRESHOLD.
+    No Option-A draw, so the menu never wins outright.
+    """
+    names = dataclasses.asdict(n)
+    out = []
+    for obj in objects:
+        bound = bind(obj, names)
+        if bound.kind == "node":
+            bound = dataclasses.replace(bound, placement="off")
+        elif bound.kind == "pvc":
+            bound = dataclasses.replace(bound, placement="unmounted")
+        elif bound.kind == "registry":
+            bound = dataclasses.replace(bound, scan_reason="1")
+        out.append(bound)
+    return tuple(out)
+
+
+# One builder for every undecided job-2 row. kubeagent leaves a workload
+# undecided in two shapes: "refuted" (one candidate attributed, a fresh read
+# refutes it) and "ruled_out" (every candidate ruled out). The evidence is
+# "clear" (a read names the cause) or "thin" (nothing does). The prompt is a
+# function of (entry, names, shape, evidence) alone, never of the case, so a
+# prompt cannot carry two expected answers. Thin evidence exists only for the
+# four entries whose one cause-naming line can be dropped.
+THIN_ENTRIES = ("crashloop-pod", "coredns-corefile-broken", "init-crashloop", "restart-loop")
+_THIN_RATIONALE = {
+    "refuted": "A fresh read refutes the attributed cause, and no read names another.",
+    "ruled_out": "Every candidate was ruled out, and no read names a cause.",
+}
+# Per clear case: (rationale suffix, summary second line). A None second line
+# means the entry's own recommendation.
+_CLEAR_WORDING = {
+    "wrong_attribution": ((" The deterministic pass attributed a different cause, but the"
+                           " evidence supports this one."),
+                          "The deterministic pass attributed a different cause."),
+    "own_cause": (" The candidate list shown did not include this cause.",
+                  "The deterministic pass did not consider this cause."),
+    "misattribution_probe": ("", None),
+}
+_MENUS = {"refuted": _refuted_menu, "ruled_out": _ruled_out_menu}
+
 
+def _undecided_example(e: CatalogEntry, n: Names, *, case: str, shape: str,
+                       evidence: str) -> Example:
+    """Build one undecided row: `shape` is "refuted" or "ruled_out",
+    `evidence` is "clear" or "thin". Thin evidence is the `none_of_these`
+    case and only it; clear evidence answers the entry's own cause at its
+    own confidence.
 
-def own_cause_case(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
-    menu = _refuted_menu(n, e.objects)
+    No rng: nothing here is drawn. kubeagent prints candidates in trace
+    order, and the answer is on no candidate line, so order gives nothing
+    away. No read budget either: every entry declares at most two objects,
+    already in gather order.
+    """
+    if not e.objects:
+        raise ValueError(f"{case} needs at least one object: {e.key}")
+    if shape not in _MENUS:
+        raise ValueError(f"shape must be 'refuted' or 'ruled_out', not {shape!r}")
+    if case != "none_of_these" and case not in _CLEAR_WORDING:
+        raise ValueError(f"not an undecided case: {case!r}")
+    want = "thin" if case == "none_of_these" else "clear"
+    if evidence != want:
+        raise ValueError(f"{case} takes {want} evidence, not {evidence!r}")
+    thin = evidence == "thin"
+    if thin and e.key not in THIN_ENTRIES:
+        raise ValueError(f"{e.key} is not a thin entry")
+    menu = _MENUS[shape](n, e.objects)
     raw = rules.attribute(menu, ns=n.ns, pod=n.pod, issue=e.issue)
-    result = rules.decide(raw)
+    result = rules.decide(raw)  # never decided: refuted and ruled out alone never win
     candidates = _to_contract_candidates(raw, result)
-    w = _workload(e, n, candidates, confidence="", result=result)
-    reads = object_reads(menu, ns=n.ns, pod=n.pod)
+    w = _workload(e, n, candidates, render.header_for(candidates), result=result,
+                  with_log_cause=not thin)
+    reads = tuple(object_reads(menu, ns=n.ns, pod=n.pod)) if shape == "refuted" else ()
+    log = _log_read(e, n, evidence)
+    reads += (log,) if log else ()
     user = _user_message(None, None, "", _service_issues(e, n), (w,), reads, key=e.key)
-    cause = _fmt(e.own_cause, n)
-    rows = [{"workload": f"{n.ns}/{n.name}", "cause": cause, "confidence": "medium",
-             "rationale": _fmt(e.rationale, n)
-                          + " The candidate list shown did not include this cause."}]
-    summary = f"{n.ns}/{n.name} is failing: {cause}.\nThe deterministic pass did not consider this cause."
     key = f"{n.ns}/{n.name}"
-    wm = workload_meta(result, expected_cause=cause,
-                       own_cause_keywords=list(e.own_cause_keywords))
+    if thin:
+        cause, conf, keywords = c.NONE_OF_THESE, "low", []
+        rationale = _THIN_RATIONALE[shape]
+        summary = (f"{key} is failing, but the evidence rules out the listed causes.\n"
+                   "A closer look at the workload is needed.")
+    else:
+        cause, conf, keywords = _fmt(e.own_cause, n), _confidence(e), list(e.own_cause_keywords)
+        suffix, last = _CLEAR_WORDING[case]
+        rationale = _fmt(e.rationale, n) + suffix
+        last = last or f"{_fmt(e.recommendation, n).capitalize()}."
+        summary = f"{key} is failing: {cause}.\n{last}"
+    rows = [{"workload": key, "cause": cause, "confidence": conf, "rationale": rationale}]
+    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=keywords)
     decoys = [cand.cause for cand in candidates]
-    meta = {"case": "own_cause", "entry": e.key, "expected_cause": cause,
-            "expected_confidence": "medium",
-            "expected_own_keywords": list(e.own_cause_keywords)}
+    meta = {"case": case, "entry": e.key, "expected_cause": cause,
+            "expected_confidence": conf}
+    if case == "own_cause":
+        meta["expected_own_keywords"] = keywords
     meta.update(prompt_meta({key: wm}, label="none", decoy_by_workload={key: decoys}))
-    return Example(case="own_cause", group=f"{e.key}:{n.ns}/{n.name}",
-                   system=c.SYSTEM_PROMPT, user=user, assistant=_answer(rows, summary),
-                   meta=meta)
+    if case in ("wrong_attribution", "misattribution_probe"):
+        meta.update(_row_decoy(decoys))
+    return Example(case=case, group=f"{e.key}:{key}", system=c.SYSTEM_PROMPT,
+                   user=user, assistant=_answer(rows, summary), meta=meta)
+
+
+def wrong_attribution(e: CatalogEntry, n: Names) -> Example:
+    """TRAINING case: kubeagent attributed a cause and a fresh read refuted
+    it, while a read names the real one. The answer is the entry's own
+    cause, which is on no candidate line.
+    """
+    return _undecided_example(e, n, case="wrong_attribution", shape="refuted",
+                              evidence="clear")
+
+
+def own_cause_case(e: CatalogEntry, n: Names) -> Example:
+    """TRAINING case: kubeagent ruled out every candidate, while a read names
+    the real cause. The answer is the entry's own cause.
+    """
+    return _undecided_example(e, n, case="own_cause", shape="ruled_out", evidence="clear")
+
+
+def none_of_these_case(e: CatalogEntry, n: Names, *, shape: str) -> Example:
+    """TRAINING case: kubeagent left the workload undecided and no read names
+    a cause. The answer is "none of these" at low confidence. Only the
+    entries in THIN_ENTRIES can be built this way.
+    """
+    return _undecided_example(e, n, case="none_of_these", shape=shape, evidence="thin")
+
+
+def misattribution_probe(e: CatalogEntry, n: Names) -> Example:
+    """EVAL-ONLY: every candidate ruled out, and a read may name the cause.
+
+    It builds the same prompt as `own_cause_case`; only the case name, the
+    wording of the gold answer and one meta key differ: this row carries
+    `decoy_cause` where `own_cause_case` carries `expected_own_keywords`.
+    The name predates that: a ruled-out menu has no `attributed`
+    candidate, so nothing here is misattributed. It keeps its name so the
+    exam's slice names stay put.
+    """
+    return _undecided_example(e, n, case="misattribution_probe", shape="ruled_out",
+                              evidence="clear")
 
 
 def truncated(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
@@ -445,47 +542,6 @@ def injection(e: CatalogEntry, n: Names, payload: str, rng: random.Random) -> Ex
                            {"injection_payload": payload})
 
 
-def wrong_attribution(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
-    """TRAINING case: the deterministic pass tagged the wrong candidate.
-
-    The evidence is untouched and still supports the catalog winner, but the
-    trace hands `attributed` to the decoy. Shuffling alone would not reach
-    this: it defeats position while leaving the tag a perfectly reliable
-    signal, so a shuffle-only retrain buys a tag-copier instead of a
-    position-copier. This case is what makes the tag merely *usually* right,
-    which is what it is in the field.
-    """
-    names = dataclasses.asdict(n)
-    declared = tuple(bind(obj, names) for obj in e.objects)
-    refuted = tuple(refute(obj) for obj in declared)
-    raw = rules.attribute(refuted, ns=n.ns, pod=n.pod, issue=e.issue)
-    result = rules.decide(raw)
-    candidates = _to_contract_candidates(raw, result)
-    cands = list(candidates)
-    rng.shuffle(cands)
-    w = _workload(e, n, tuple(cands), confidence=_confidence(e), result=result)
-    reads = object_reads(refuted, ns=n.ns, pod=n.pod)
-    user = _user_message(None, None, "", _service_issues(e, n), (w,), reads, key=e.key)
-    cause = _fmt(e.own_cause, n)
-    rows = [{"workload": f"{n.ns}/{n.name}", "cause": cause, "confidence": _confidence(e),
-             "rationale": _fmt(e.rationale, n)
-                          + " The deterministic pass attributed a different cause, but the"
-                            " evidence supports this one."}]
-    summary = (f"{n.ns}/{n.name} is failing: {cause}.\n"
-               "The deterministic pass attributed a different cause.")
-    key = f"{n.ns}/{n.name}"
-    wm = workload_meta(result, expected_cause=cause,
-                       own_cause_keywords=list(e.own_cause_keywords))
-    decoys = [cand.cause for cand in candidates]
-    meta = {"case": "wrong_attribution", "entry": e.key, "expected_cause": cause,
-            "expected_confidence": _confidence(e)}
-    meta.update(prompt_meta({key: wm}, label="none", decoy_by_workload={key: decoys}))
-    meta.update(_row_decoy(decoys))
-    return Example(case="wrong_attribution", group=f"{e.key}:{n.ns}/{n.name}",
-                   system=c.SYSTEM_PROMPT, user=user, assistant=_answer(rows, summary),
-                   meta=meta)
-
-
 def positional_probe(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
     """EVAL-ONLY: the honest `attributed` tag, but the winner placed LAST.
 
@@ -504,58 +560,6 @@ def positional_probe(e: CatalogEntry, n: Names, rng: random.Random) -> Example:
                            _row_decoy([cand.cause for cand in candidates]))
 
 
-def _ruled_out_menu(n: Names, objects: tuple) -> tuple:
-    """Bind every declared object, then force each one into a ruled-out
-    ending below rules.decide()'s threshold: node placement="off", pvc
-    placement="unmounted", registry scan_reason below REGISTRY_THRESHOLD.
-    Used by `misattribution_probe`, whose menu must stay honest (no Option-A
-    randomness) while still never winning outright.
-    """
-    names = dataclasses.asdict(n)
-    out = []
-    for obj in objects:
-        bound = bind(obj, names)
-        if bound.kind == "node":
-            bound = dataclasses.replace(bound, placement="off")
-        elif bound.kind == "pvc":
-            bound = dataclasses.replace(bound, placement="unmounted")
-        elif bound.kind == "registry":
-            bound = dataclasses.replace(bound, scan_reason="1")
-        out.append(bound)
-    return tuple(out)
-
-
-def misattribution_probe(e: CatalogEntry, n: Names) -> Example:
-    """EVAL-ONLY: tag and position BOTH point away from the evidence.
-
-    The adversarial slice. Deterministic ordering, decoy first, decoy tagged
-    `attributed`, evidence unchanged and still supporting the winner. See
-    _ruled_out_menu for why this is a lower bound on tag-following.
-    """
-    if not e.objects:
-        raise ValueError(f"misattribution_probe needs at least one object: {e.key}")
-    menu = _ruled_out_menu(n, e.objects)
-    candidates, result = _decoy_result(e, n, menu)
-    w = _workload(e, n, candidates, confidence=_confidence(e), result=result)
-    reads = object_reads(menu, ns=n.ns, pod=n.pod)
-    user = _user_message(None, None, "", _service_issues(e, n), (w,), reads, key=e.key)
-    cause = _fmt(e.own_cause, n)
-    rows = [{"workload": f"{n.ns}/{n.name}", "cause": cause, "confidence": _confidence(e),
-             "rationale": _fmt(e.rationale, n)}]
-    summary = f"{n.ns}/{n.name} is failing: {cause}.\n{_fmt(e.recommendation, n).capitalize()}."
-    key = f"{n.ns}/{n.name}"
-    wm = workload_meta(result, expected_cause=cause,
-                       own_cause_keywords=list(e.own_cause_keywords))
-    decoys = [cand.cause for cand in candidates]
-    meta = {"case": "misattribution_probe", "entry": e.key, "expected_cause": cause,
-            "expected_confidence": _confidence(e)}
-    meta.update(prompt_meta({key: wm}, label="none", decoy_by_workload={key: decoys}))
-    meta.update(_row_decoy(decoys))
-    return Example(case="misattribution_probe", group=f"{e.key}:{n.ns}/{n.name}",
-                   system=c.SYSTEM_PROMPT, user=user, assistant=_answer(rows, summary),
-                   meta=meta)
-
-
 def _contradiction_menu(n: Names, objects: tuple) -> tuple[tuple, tuple]:
     """Bind every declared object, then unverify each one with a fixed,
     kind-specific "how" that always contradicts. Returns (bound, unverified)
@@ -592,10 +596,13 @@ def contradiction_probe(e: CatalogEntry, n: Names) -> Example:
     v4 scored the known-broken first tune on this slice: 1.0 cause, 0.0 decoy
     — a clean pass by a model proven elsewhere to follow the `attributed` tag
     79% of the time, emitting the expected rationale and summary VERBATIM. The
-    confound is that this builder reuses `none_of_these_case`'s read
+    confound was that this builder reused `none_of_these_case`'s read
     construction exactly — same label, same `e.contradiction` content — and
-    `none_of_these` is 15% of the curriculum, so the contradiction sentence is
-    itself a memorised trigger for a memorised answer template. Holding the
+    `none_of_these` was 15% of the curriculum, so the contradiction sentence
+    was itself a memorised trigger for a memorised answer template. (Since
+    2026-09-24 `none_of_these` rows are built from thin evidence on four
+    entries, at low confidence, and share neither this row's reads nor its
+    rationale.) Holding the
     adversarial menu roughly fixed and changing only the read text moves cause
     accuracy from 0.1579 (`misattribution_probe`) and 0.4737
     (`wrong_attribution`) to 1.0 here. The menu is what this row perturbs, and
diff --git a/src/kubeagent_verdict/dataset/generate.py b/src/kubeagent_verdict/dataset/generate.py
index 288d1fa..0a48c97 100644
--- a/src/kubeagent_verdict/dataset/generate.py
+++ b/src/kubeagent_verdict/dataset/generate.py
@@ -130,10 +130,14 @@ def generate(seed: int, size: int) -> list[Example]:
 
     for i in range(counts["attributed"]):
         out.append(cases.attributed(rotate(i), names.draw(rng), rng))
+    # Thin evidence exists for four entries only. Rotate through them, and
+    # alternate the two undecided shapes once per full pass.
+    thin = [next(e for e in entries if e.key == key) for key in cases.THIN_ENTRIES]
     for i in range(counts["none_of_these"]):
-        out.append(cases.none_of_these_case(rotate(i), names.draw(rng), rng))
+        shape = ("refuted", "ruled_out")[(i // len(thin)) % 2]
+        out.append(cases.none_of_these_case(thin[i % len(thin)], names.draw(rng), shape=shape))
     for i in range(counts["own_cause"]):
-        out.append(cases.own_cause_case(rotate(i), names.draw(rng), rng))
+        out.append(cases.own_cause_case(rotate(i), names.draw(rng)))
     for i in range(counts["multi"]):
         k = rng.randint(2, 4)
         pairs, seen = [], set()
@@ -251,7 +255,7 @@ def generate(seed: int, size: int) -> list[Example]:
     for i in range(counts["empty_candidates"]):
         out.append(cases.empty_candidates(rotate(i), names.draw(rng)))
     for i in range(counts["wrong_attribution"]):
-        out.append(cases.wrong_attribution(rotate(i), names.draw(rng), rng))
+        out.append(cases.wrong_attribution(rotate(i), names.draw(rng)))
     return out
 
 
@@ -327,19 +331,28 @@ def held_out_case_set() -> list[Example]:
     happen to take — so roughly half the curriculum trains and is never
     scored, and a metric computed over it describes one case while being
     reported as an overall rate.
+
+    `none_of_these` is the exception to one row per entry: thin evidence
+    exists only for `cases.THIN_ENTRIES`, so that case gives one row per thin
+    entry per undecided shape, 8 rows in all.
     """
     from kubeagent_verdict.dataset import cases, catalog, names
 
     builders = {
-        "none_of_these": cases.none_of_these_case,
-        "own_cause": cases.own_cause_case,
+        "own_cause": lambda e, n, rng: cases.own_cause_case(e, n),
         "truncated": cases.truncated,
         "empty_candidates": lambda e, n, rng: cases.empty_candidates(e, n),
-        "wrong_attribution": cases.wrong_attribution,
+        "wrong_attribution": lambda e, n, rng: cases.wrong_attribution(e, n),
     }
     out: list[Example] = []
     for entry in catalog.trainable():
         for case in HELD_OUT_CASES:
+            if case == "none_of_these":
+                if entry.key in cases.THIN_ENTRIES:
+                    for shape in ("refuted", "ruled_out"):
+                        n = names.draw(_entry_rng("held-out", case, entry.key, shape))
+                        out.append(cases.none_of_these_case(entry, n, shape=shape))
+                continue
             rng = _entry_rng("held-out", case, entry.key)
             n = names.draw(rng)
             if case == "injection":
@@ -355,18 +368,20 @@ def probe_sets() -> list[Example]:
     """The four adversarial eval-only slices, one row per trainable entry.
 
     `positional_probe` puts the correct answer last with an honest tag;
-    `misattribution_probe` puts it last AND hands `attributed` to the decoy;
-    `multi_misattribution_probe` does the same in the multi-workload shape the
-    single-workload probes cannot reach; `contradiction_probe` adds a read that
+    `misattribution_probe` rules every candidate out, so the answer is on no
+    candidate line (since 2026-09-24; it used to hand `attributed` to the
+    decoy); `multi_misattribution_probe` hands `attributed` to the decoy in the
+    multi-workload shape the single-workload probes cannot reach;
+    `contradiction_probe` adds a read that
     rules the winner out, so the answer is on no candidate line at all. None is
     ever generated into train or val — they exist to make a shortcut visible,
     and a shortcut the training data rewards is not a shortcut the eval can
     detect.
 
     That last sentence is the limit of all four, and `contradiction_probe`
-    found it the hard way: the training data rewards answering `none of these`
-    to the very contradiction sentence that slice reuses, so a memorising
-    model passes it. Every catalog entry appears in train, val and test, so no
+    found it the hard way: the training data rewarded answering `none of these`
+    to the very contradiction sentence that slice reused, so a memorising
+    model passed it. Every catalog entry appears in train, val and test, so no
     slice here can separate a model that reads from one that recites per-entry
     answers. Ruling that out needs held-out entries and a retrain.
     """
@@ -411,10 +426,12 @@ def probe_sets() -> list[Example]:
     # It was built to also catch a model reciting a memorised entry-to-winner
     # lookup table, and it DOES NOT — negative control v4 measured the
     # known-broken first tune at 1.0 cause / 0.0 decoy here. The read text it
-    # reuses is `none_of_these_case`'s verbatim, which makes the contradiction
-    # sentence a trained trigger rather than something to reason about. See
-    # `cases.contradiction_probe`'s docstring for the full retraction; the
-    # slice is kept for the three shortcuts it does defeat.
+    # reused was `none_of_these_case`'s verbatim, which made the contradiction
+    # sentence a trained trigger rather than something to reason about (since
+    # 2026-09-24 `none_of_these` rows use thin evidence and share no read text
+    # with this slice). See `cases.contradiction_probe`'s docstring for the
+    # full retraction; the slice is kept for the three shortcuts it does
+    # defeat.
     for entry in catalog.trainable():
         if not entry.objects or not entry.contradiction:
             continue
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `906 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_cases.py tests/test_evidence_overlap.py tests/test_exam_graded_view.py tests/test_generate.py tests/test_oracle.py tests/test_probe_cousins.py tests/test_score.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/generate.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(dataset): build every undecided job-2 row from one builder

none_of_these and wrong_attribution built the same prompt for 27 of
28 catalogue entries and gave it opposite answers, so no model could
learn to override a wrong attributed tag.

_undecided_example now builds every undecided job-2 row from the entry,
the names, the shape (refuted or ruled out) and the evidence (clear or
thin). The case names the row and its meta, and never changes the
prompt. Clear evidence answers the entry's own cause at its own
confidence. Thin evidence exists for four entries only and answers
"none of these". Headers come from header_for, crash-family rows carry
their log read, and ruled-out rows read no objects, as kubeagent does.

The builders take no rng, since nothing is drawn. The exam moves where
the design says; train and val counts move everywhere.
EOF
```

### Task 6: Move seven points of the case mix to the clear cases

**Files:**
- Modify: `src/kubeagent_verdict/dataset/generate.py` (`CASE_MIX` and its comment)
- Test: `tests/test_evidence_overlap.py`, `tests/test_generate.py`, `tests/test_multi_collision.py`, `tests/test_oracle.py`

**Interfaces:**
- Consumes: the thin rotation over `cases.THIN_ENTRIES` in `generate`
  (Task 5).
- Produces: `generate.CASE_MIX` gives `none_of_these` 4, `own_cause` 13
  and `wrong_attribution` 14. The other seven cases keep their shares.

**Why (spec section 5):** thin evidence exists for 4 entries only. At 11%,
each of those entries had about 110 thin rows per shape against 42 clear
ones, so "none of these" was the likelier answer on the very prompts that
name a cause. At 4%, each has 40 thin rows per shape, and clear rows
outnumber them in every cell. The exam does not read the mix, so no hash
moves. The multi-collision pins move (ruling 12).

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

12. **`tests/test_multi_collision.py`'s pins move in Task 6.** They count
    real rows at build size, and the mix change moves them.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-6
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=6 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_evidence_overlap.py b/tests/test_evidence_overlap.py
index bdd9a85..2448cbf 100644
--- a/tests/test_evidence_overlap.py
+++ b/tests/test_evidence_overlap.py
@@ -191,7 +191,7 @@ def _fake(user: str) -> generate.Example:
 #
 # An EMPTY block is reachable, and has been since 2026-09-24: a ruled-out
 # row outside the crash family has no object read and no log read, so it
-# renders "(none)". Measured at SEED/SIZE: 725 of 7135 kept rows and 30 of
+# renders "(none)". Measured at SEED/SIZE: 746 of 7151 kept rows and 30 of
 # 252 test rows, 14 of them in the DECLARED `misattribution_probe` slice.
 # (kubeagent would still show its per-workload events read there; adding
 # that read to the generator is later work.) Such a row has no reads, so it
diff --git a/tests/test_generate.py b/tests/test_generate.py
index 9d61831..f1513af 100644
--- a/tests/test_generate.py
+++ b/tests/test_generate.py
@@ -56,11 +56,11 @@ def test_to_row_schema():
 
 def test_counts_for_follows_the_mix():
     counts = generate.counts_for(1000)
-    assert counts == {"attributed": 60, "none_of_these": 110, "own_cause": 100,
+    assert counts == {"attributed": 60, "none_of_these": 40, "own_cause": 130,
                       "multi": 130, "shared_origin": 150,
                       "shared_origin_decoy": 150, "truncated": 50,
                       "injection": 100, "empty_candidates": 50,
-                      "wrong_attribution": 100}
+                      "wrong_attribution": 140}
     assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed
     # 997 is the awkward size: it is prime, so every share truncates.
     for size in (10, 100, 997, 1000, 4232):
@@ -721,3 +721,21 @@ def test_one_prompt_has_one_answer():
             (v["workload"], v["cause"], v["confidence"]) for v in gold)))
     clashes = {prompt[:200]: sorted(a) for prompt, a in answers.items() if len(a) > 1}
     assert not clashes, clashes
+
+
+def test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape():
+    """A thin row and a clear row of the same entry and shape differ in one
+    read. If thin rows outnumber clear ones, "none of these" becomes the
+    likelier answer for that entry whatever the reads say. Counted in
+    train, the way `kv-dataset` builds it: split, then drop held-out groups.
+    """
+    train, _val = generate.split(generate.generate(seed=17, size=8000), seed=17)
+    train = generate.drop_held_out(train, generate.test_set())
+    clear_case = {"refuted": "wrong_attribution", "ruled_out": "own_cause"}
+    n = collections.Counter(
+        (ex.meta["entry"], "refuted" if "fresh read: refuted" in ex.user else "ruled_out",
+         ex.case)
+        for ex in train if ex.case in ("none_of_these", *clear_case.values()))
+    for key in cases.THIN_ENTRIES:
+        for shape, clear in clear_case.items():
+            assert n[(key, shape, clear)] > n[(key, shape, "none_of_these")] > 0, (key, shape)
diff --git a/tests/test_multi_collision.py b/tests/test_multi_collision.py
index 5e1f286..f5d4c1c 100644
--- a/tests/test_multi_collision.py
+++ b/tests/test_multi_collision.py
@@ -212,7 +212,10 @@ def test_a_real_registry_healthy_origin_read_is_dropped_next_to_its_own_candidat
     dropped = sum(1 for _, kept in calls if not kept)
     # Measured over this exact build (seed 17, size 8000): 12 multi rows draw
     # a registry-story healthy origin; the rule drops 2 of them and keeps 10.
-    assert (len(calls), dropped) == (12, 2)
+    # Re-measured 2026-09-24 (job-2 generator fix: the case mix moved, so
+    # every `multi` row draws new names): still 12 rows, the rule drops 1
+    # and keeps 11. The drop branch is still reached.
+    assert (len(calls), dropped) == (12, 1)
 
 
 def test_no_real_healthy_node_read_names_a_clashing_node(monkeypatch):
@@ -253,4 +256,7 @@ def test_no_real_healthy_node_read_names_a_clashing_node(monkeypatch):
     # Re-measured 2026-09-19 over this exact build (seed 17, size 8000)
     # after the mix and pool changes in spec section 6: 96 multi rows draw a
     # node-story healthy origin; the rule keeps 59, renames 35 and drops 2.
-    assert (len(calls), kept, renamed, dropped) == (96, 59, 35, 2)
+    # Re-measured 2026-09-24 (job-2 generator fix: the case mix moved, so
+    # every `multi` row draws new names): still 96 rows; the rule keeps 54,
+    # renames 41 and drops 1. The drop branch is still reached.
+    assert (len(calls), kept, renamed, dropped) == (96, 54, 41, 1)
diff --git a/tests/test_oracle.py b/tests/test_oracle.py
index 414a119..ab0631a 100644
--- a/tests/test_oracle.py
+++ b/tests/test_oracle.py
@@ -130,26 +130,33 @@ def test_oracle_job1_is_perfect_on_train():
     # longer draw from the rng, which moves every later draw, and the
     # held-out `none_of_these` slice is 8 groups, not 19) -- 3056 to 3081.
     # Rate unchanged.
-    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3081}
+    # Re-measured 2026-09-24 again (case mix: `none_of_these` 11% -> 4%,
+    # `own_cause` 10% -> 13%, `wrong_attribution` 10% -> 14%; the row
+    # counts change, and so does every later rng draw) -- 3081 to 3120.
+    # Rate unchanged.
+    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3120}
 
 
 def test_oracle_job1_is_perfect_on_val():
     board = score.scoreboard(list(_val_results()))
     # Re-measured 2026-09-19, same reason. 289 to 355. Rate unchanged.
     # Re-measured 2026-09-24, job-2 generator fix. 355 to 357. Rate unchanged.
-    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 357}
+    # Re-measured 2026-09-24 again, case mix. 357 to 309. Rate unchanged.
+    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 309}
 
 
 def test_oracle_job2_gate_is_perfect_on_train():
     # Re-measured 2026-09-19, same reason. 3121 to 2975. Rate unchanged.
     # Re-measured 2026-09-24, job-2 generator fix. 2975 to 3000. Rate unchanged.
-    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3000}
+    # Re-measured 2026-09-24 again, case mix. 3000 to 3030. Rate unchanged.
+    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3030}
 
 
 def test_oracle_job2_gate_is_perfect_on_val():
     # Re-measured 2026-09-19, same reason. 352 to 304. Rate unchanged.
     # Re-measured 2026-09-24, job-2 generator fix. 304 to 321. Rate unchanged.
-    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 321}
+    # Re-measured 2026-09-24 again, case mix. 321 to 298. Rate unchanged.
+    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 298}
 
 
 def test_oracle_job2_keyword_only_matches_the_spec_measurement():
@@ -160,8 +167,12 @@ def test_oracle_job2_keyword_only_matches_the_spec_measurement():
     6) -- 2175 to 2286. Rate still 1.0.
 
     Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
-    above) -- 2286 to 2324. Rate still 1.0."""
-    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2324}
+    above) -- 2286 to 2324. Rate still 1.0.
+
+    Re-measured 2026-09-24 again (case mix, same reason as job 1 above)
+    -- 2324 to 2785. Most of the rise is the extra `own_cause` and
+    `wrong_attribution` rows, which are keyword-graded. Rate still 1.0."""
+    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2785}
 
 
 def test_oracle_job3_is_perfect_on_train():
@@ -184,25 +195,32 @@ def test_oracle_job3_is_perfect_on_train():
 
     Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
     above) -- 2790 to 2803; all 13 new rows are `none`-labeled. Rate still
+    1.0.
+
+    Re-measured 2026-09-24 again (case mix, same reason as job 1 above) --
+    2803 to 2832: `shared` 192 to 195, `none` 2610 to 2636. Rate still
     1.0."""
     board = score.scoreboard(list(_train_results()))
     assert board["jobs"]["job3"] == {
-        "rate": 1.0, "n": 2803,
-        "by_label": {"shared": {"rate": 1.0, "n": 192},
+        "rate": 1.0, "n": 2832,
+        "by_label": {"shared": {"rate": 1.0, "n": 195},
                      "separate": {"rate": 1.0, "n": 1},
-                     "none": {"rate": 1.0, "n": 2610}}}
+                     "none": {"rate": 1.0, "n": 2636}}}
 
 
 def test_oracle_job3_is_perfect_on_val():
-    """Val side of the same extension: 22 of the split's rows are a ruled
+    """Val side of the same extension: 19 of the split's rows are a ruled
     story's broken twin, labeled `shared`, and the gold summary matches on
-    every one -- re-measured 2026-09-19, Task 9."""
+    every one -- re-measured 2026-09-19, Task 9 (22 rows then).
+
+    Re-measured 2026-09-24 (case mix, same reason as job 1 above) -- 336 to
+    296: `shared` 22 to 19, `none` 314 to 277. Rate still 1.0."""
     board = score.scoreboard(list(_val_results()))
     assert board["jobs"]["job3"] == {
-        "rate": 1.0, "n": 336,
-        "by_label": {"shared": {"rate": 1.0, "n": 22},
+        "rate": 1.0, "n": 296,
+        "by_label": {"shared": {"rate": 1.0, "n": 19},
                      "separate": {"rate": None, "n": 0},
-                     "none": {"rate": 1.0, "n": 314}}}
+                     "none": {"rate": 1.0, "n": 277}}}
 
 
 def test_oracle_multi_job1_matches_the_spec_measurement():
@@ -216,13 +234,17 @@ def test_oracle_multi_job1_matches_the_spec_measurement():
     Re-measured 2026-09-24 (job-2 generator fix: the undecided builders no
     longer draw from the rng, so every `multi` row draws new names, and the
     held-out `none_of_these` slice is 8 groups, not 19) -- 1209 to 1227 in
-    train; val unchanged at 145. Still perfect."""
+    train; val unchanged at 145. Still perfect.
+
+    Re-measured 2026-09-24 again (case mix: the `multi` share is unchanged,
+    but every `multi` row draws new names, so the split moves) -- 1227 to
+    1226 in train, 145 to 132 in val. Still perfect."""
     def multi_job1(results):
         scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
         return sum(scores), len(scores)
 
-    assert multi_job1(_train_results()) == (1227.0, 1227)
-    assert multi_job1(_val_results()) == (145.0, 145)
+    assert multi_job1(_train_results()) == (1226.0, 1226)
+    assert multi_job1(_val_results()) == (132.0, 132)
 
 
 def test_exam_oracle_job1_misses_only_contradiction_probe():
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_evidence_overlap.py tests/test_generate.py tests/test_multi_collision.py tests/test_oracle.py
```

Expected: the summary line reads `12 failed, 58 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_generate.py::test_counts_for_follows_the_mix
FAILED tests/test_generate.py::test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape
FAILED tests/test_multi_collision.py::test_a_real_registry_healthy_origin_read_is_dropped_next_to_its_own_candidate
FAILED tests/test_multi_collision.py::test_no_real_healthy_node_read_names_a_clashing_node
FAILED tests/test_oracle.py::test_oracle_job1_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_job1_is_perfect_on_val
FAILED tests/test_oracle.py::test_oracle_job2_gate_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_job2_gate_is_perfect_on_val
FAILED tests/test_oracle.py::test_oracle_job2_keyword_only_matches_the_spec_measurement
FAILED tests/test_oracle.py::test_oracle_job3_is_perfect_on_train
FAILED tests/test_oracle.py::test_oracle_job3_is_perfect_on_val
FAILED tests/test_oracle.py::test_oracle_multi_job1_matches_the_spec_measurement
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-6
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=6 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/generate.py b/src/kubeagent_verdict/dataset/generate.py
index 0a48c97..c5ef0fe 100644
--- a/src/kubeagent_verdict/dataset/generate.py
+++ b/src/kubeagent_verdict/dataset/generate.py
@@ -89,10 +89,18 @@ def write_jsonl(path: Path, examples: list[Example]) -> None:
 # (test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows)
 # -- Task 9 of the 2026-09-19 training-targets plan measures the mixes
 # this was chosen over.
-CASE_MIX = (("attributed", 6), ("none_of_these", 11), ("own_cause", 10),
+# 2026-09-24: `none_of_these` drops 11% -> 4%, and its 7 points go to
+# `own_cause` (10% -> 13%) and `wrong_attribution` (10% -> 14%); the three
+# keep their combined 31%. Thin evidence exists for the four
+# `cases.THIN_ENTRIES` only, so at 11% each of those entries had about 110
+# thin rows per shape against 42 clear ones, and "none of these" was the
+# likelier answer on the very prompts that name a cause. At 4% each thin
+# entry has 40 thin rows per shape, and clear rows outnumber them in every
+# cell (test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape).
+CASE_MIX = (("attributed", 6), ("none_of_these", 4), ("own_cause", 13),
             ("multi", 13), ("shared_origin", 15), ("shared_origin_decoy", 15),
             ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
-            ("wrong_attribution", 10))
+            ("wrong_attribution", 14))
 
 # The held-out test set draws one example per (trainable entry, case) for each
 # of these. `multi` is excluded deliberately: its group is a "+"-join of two to
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `907 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_evidence_overlap.py tests/test_generate.py tests/test_multi_collision.py tests/test_oracle.py src/kubeagent_verdict/dataset/generate.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
feat(dataset): move seven points of the case mix from none_of_these to clear rows

Thin evidence exists for four entries only. At 11% of the mix, each of
them had about 110 thin rows per shape against 42 clear ones, so "none
of these" was the likelier answer on prompts that name a cause.

none_of_these drops to 4%. own_cause goes to 13% and wrong_attribution
to 14%. Clear rows now outnumber thin rows for every thin entry and
shape. The exam does not read the mix.
EOF
```

### Task 7: `multi` keeps crash-family log reads and prints headers by rule

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (add `_multi_reads` and `_cap_reads`; `multi` and `multi_misattribution_probe` build their reads through them; `multi_misattribution_probe` takes its header from `render.header_for`)
- Test: `tests/test_cases.py`, `tests/test_evidence_overlap.py`, `tests/test_exam_graded_view.py`, `tests/test_generate.py`, `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `cases._log_read` (Task 4), `render.header_for` (Task 2).
- Produces, in `cases.py`:
  - `_multi_reads(e: CatalogEntry, n: Names, object_reads: tuple[c.EvidenceRead, ...]) -> list[tuple[c.EvidenceRead, bool]]`
    — at most two reads for one workload, each paired with `True` when the
    cap must keep it. A crash-family workload gives its first object read,
    then its clear log read (kept). Any other workload gives its first two
    object reads (droppable).
  - `_cap_reads(reads: list[tuple[c.EvidenceRead, bool]]) -> tuple[c.EvidenceRead, ...]`
    — drops droppable reads from the end until at most
    `c.MAX_TOOL_CALLS` (8) remain; never drops a kept read; raises
    `ValueError` if the kept reads alone pass 8.

  In `multi`, the healthy-origin read is marked kept.

**Why (spec section 6):** `multi` took each workload's first two object
reads and then cut the row at 8, so most crash-family workloads lost the
log read kubeagent would have made. Ruling 8 has the re-measured numbers,
ruling 5 the allowlist move, and ruling 7 the four shared-origin cases the
new header test exempts. The three pinned hashes move; the tests
diff writes their new values.

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

5. **The eval-only reuse allowlist moves twice.** `DECLARED` in
   `tests/test_evidence_overlap.py`: `misattribution_probe` goes
   `(14, 20)` → `(5, 5)` in Task 5 (its describe reads are gone), and
   `multi_misattribution_probe` goes `(39, 40)` → `(47, 48)` in Task 7 (it
   gains log reads that crash-family training rows also carry).
   `contradiction_probe` stays `(19, 38)`; only its comment changes.
7. **The header test exempts the four shared-origin cases.** The spec's
   success criteria say every job-2 header equals kubeagent's rule. Its
   "Out of scope" says the shared-origin builders are not touched, and
   they hand-pass their header. Scope wins. Task 7's test exempts
   `shared_origin`, `shared_origin_decoy`, `shared_origin_probe` and
   `shared_origin_decoy_probe` by name. The gap is reported, not fixed.
8. **`multi`'s numbers were re-measured.** Spec section 6 gives 3,160
   blocks, 836 crash-family, 780 losses, 125 over-cap rows and 33 cut log
   reads. After Task 6's mix change they are 3,157, 847, 784, 127 and 34.
   The rule is unchanged. Task 7's docstrings carry 847, 784 and 34. Task
   9's `docs/design.md` carries 3,157. 127 is recorded here only.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-7
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=7 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_cases.py b/tests/test_cases.py
index 1fd296f..eb7606f 100644
--- a/tests/test_cases.py
+++ b/tests/test_cases.py
@@ -901,3 +901,17 @@ def test_each_wrapper_is_its_shape_and_evidence():
     for shape in SHAPES:
         assert cases.none_of_these_case(e, n, shape=shape) == \
             built("none_of_these", shape, "thin")
+
+
+def test_cap_reads_drops_droppable_reads_from_the_end_and_never_a_kept_one():
+    """A multi-workload row can pass 8 reads only with a healthy origin read
+    and 4 workloads. The cap cuts droppable object reads from the end and
+    keeps the origin read and every log read. A row with more than 8 reads
+    it may not drop is a generator bug, so it raises."""
+    r = [c.EvidenceRead(label=f"r{i}", content="x") for i in range(10)]
+    reads = [(r[0], True)] + [(x, False) for x in r[1:8]] + [(r[8], True), (r[9], False)]
+    assert [x.label for x in cases._cap_reads(reads)] == [
+        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r8"]
+    assert cases._cap_reads([(x, False) for x in r[:3]]) == tuple(r[:3])
+    with pytest.raises(ValueError, match="budget"):
+        cases._cap_reads([(x, True) for x in r[:9]])
diff --git a/tests/test_evidence_overlap.py b/tests/test_evidence_overlap.py
index 2448cbf..909b11a 100644
--- a/tests/test_evidence_overlap.py
+++ b/tests/test_evidence_overlap.py
@@ -66,8 +66,15 @@ DECLARED = {
     # train. The other fourteen rows render no reads. It read (14, 20) when
     # its menu still carried describe reads.
     "misattribution_probe": (5, 5),
-    # Same, in the multi shape: _reads(e, n)[:2] per constituent.
-    "multi_misattribution_probe": (39, 40),
+    # Same, in the multi shape. Since 2026-09-24 a crash-family constituent
+    # reads its first object read and then its clear log read, the read
+    # kubeagent makes for every crash-family workload; any other constituent
+    # reads its first two object reads, as before. That adds 10 log reads and
+    # drops 2 second object reads. All 10 log reads are reused: the clear log
+    # read is one template per entry, and crash-family training rows render
+    # it too. The one miss is the same events read as before. It read
+    # (39, 40) when every constituent took its first two object reads.
+    "multi_misattribution_probe": (47, 48),
     # THIS ROW WAS THE POINT OF THE INSTRUMENT. It was written to catch this
     # slice reusing none_of_these_case's read text, which is why the slice
     # cannot catch a model reciting an entry-lookup table. Negative control v4
diff --git a/tests/test_exam_graded_view.py b/tests/test_exam_graded_view.py
index c8aaf34..55e6769 100644
--- a/tests/test_exam_graded_view.py
+++ b/tests/test_exam_graded_view.py
@@ -45,9 +45,10 @@ Re-pinned on 2026-09-24 for the job-2 generator fix
 moves, and this view keeps it whole, so the digest follows every rendered
 change `FROZEN_SLICE_SHA256`'s 2026-09-24 entry lists in
 `tests/test_shared_origin_training.py`. The new exam is a new baseline.
-It moved twice on that branch: once for the catalogue's log-cause text,
-once for the single undecided builder, which also cut the exam from 263
-rows to 252.
+It moved three times on that branch: once for the catalogue's log-cause
+text, once for the single undecided builder, which also cut the exam from
+263 rows to 252, and once for the multi-workload rows' log reads and
+headers.
 """
 
 from __future__ import annotations
@@ -74,7 +75,7 @@ def view(row):
             "flagged": [v["workload"] for v in gold["verdicts"]]}
 
 
-GRADED_VIEW_SHA256 = "046bf2b87b20aa20ebb79ca6ee199a47d9f8f54e25f42df76894033df09063a5"
+GRADED_VIEW_SHA256 = "74f55a1d64eaeb5fec11d5b871ac69b93dfc4d60700936843477a6e7063a4a81"
 
 
 def _digest(views) -> str:
diff --git a/tests/test_generate.py b/tests/test_generate.py
index f1513af..90f628f 100644
--- a/tests/test_generate.py
+++ b/tests/test_generate.py
@@ -739,3 +739,75 @@ def test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape():
     for key in cases.THIN_ENTRIES:
         for shape, clear in clear_case.items():
             assert n[(key, shape, clear)] > n[(key, shape, "none_of_these")] > 0, (key, shape)
+
+
+def _evidence_labels(user: str) -> list[str]:
+    section = user.split("== BEGIN evidence ==\n")[1].split("== END evidence ==")[0]
+    return re.findall(r"^== (.+) ==$", section, flags=re.MULTILINE)
+
+
+def test_every_crash_family_workload_in_a_multi_row_keeps_its_log_read():
+    """kubeagent reads the previous log of every crash-family workload.
+    A multi-workload row gives each workload at most two reads and the row
+    at most 8, so a log read appended after two object reads, or a plain
+    `[:8]`, would silently lose it. Checked on every `multi` training row
+    and every `multi_misattribution_probe` exam row."""
+    rows = [ex for ex in generate.generate(seed=17, size=8000) if ex.case == "multi"]
+    rows += [ex for ex in generate.test_set() if ex.case == "multi_misattribution_probe"]
+    checked = 0
+    for ex in rows:
+        labels = _evidence_labels(ex.user)
+        assert len(labels) <= c.MAX_TOOL_CALLS, ex.group
+        for part in ex.group.split("+"):
+            key, workload = part.split(":")
+            if key not in cases.LOG_READS:
+                continue
+            ns, name = workload.split("/")
+            pattern = re.compile(rf"log causes {re.escape(ns)}/{re.escape(name)}-[^-]+-[^-]+ container \S+")
+            assert any(pattern.fullmatch(label) for label in labels), (ex.group, part)
+            checked += 1
+    assert checked > 0
+
+
+_CANDIDATE_HEAD = re.compile(r"^- (\S+) \(\w+\)(?: \[confidence: (\w+)\])?:$")
+_ATTRIBUTED = re.compile(r"^    considered (.+): attributed — ")
+# kubeagent's `ForRootCause` (internal/confidence/confidence.go:36-47 at v1.24.0).
+_RULE = (("node ", "high"), ("PVC ", "high"), ("registry ", "medium"))
+# The shared-origin builders still hand-pass their header. This branch leaves
+# them alone (spec: "Not touched here: the shared-origin builders").
+_HEADER_EXEMPT = {"shared_origin", "shared_origin_decoy", "shared_origin_probe",
+                  "shared_origin_decoy_probe"}
+
+
+def _headers(user: str) -> dict[str, tuple[str, list[str]]]:
+    section = user.split("== BEGIN candidates ==\n")[1].split("== END candidates ==")[0]
+    out: dict[str, tuple[str, list[str]]] = {}
+    for line in section.splitlines():
+        if m := _CANDIDATE_HEAD.match(line):
+            workload = m.group(1)
+            out[workload] = (m.group(2) or "", [])
+        elif m := _ATTRIBUTED.match(line):
+            out[workload][1].append(m.group(1))
+    return out
+
+
+def test_every_job2_header_follows_kubeagents_rule():
+    """The `[confidence: ...]` header over a job-2 workload is what
+    kubeagent would print for its one attributed candidate: node or PVC
+    gives high, registry gives medium, anything else or no attributed
+    candidate gives no header."""
+    checked = collections.Counter()
+    for ex in generate.generate(seed=17, size=8000) + generate.test_set():
+        if ex.case in _HEADER_EXEMPT or "== BEGIN candidates ==" not in ex.user:
+            continue
+        headers = _headers(ex.user)
+        for workload, wm in ex.meta["workloads"].items():
+            if wm["job"] != 2 or workload not in headers:
+                continue
+            header, attributed = headers[workload]
+            assert len(attributed) <= 1, (ex.group, workload)
+            want = next((level for prefix, level in _RULE
+                         if attributed and attributed[0].startswith(prefix)), "")
+            assert header == want, (ex.case, ex.group, workload)
+            checked[ex.case] += 1
+    assert {"multi", "multi_misattribution_probe", "wrong_attribution"} <= set(checked)
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index f344934..f848b8a 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -848,7 +848,14 @@ def test_the_eval_set_is_two_hundred_and_fifty_two_rows():
 #   too); and 9 of 19 `wrong_attribution` rows change their user message (4
 #   take the header kubeagent's confidence rule gives the attributed cause,
 #   the other 5 gain a log read). No other row moves.
-FROZEN_SLICE_SHA256 = "b6f61e68c7615288452b48935031b649f502e21c1fad3ba7c7d7a96f11758294"
+# - A multi-workload row keeps the log read kubeagent makes for every
+#   crash-family workload, and `multi_misattribution_probe` prints the
+#   header kubeagent's confidence rule gives each constituent's attributed
+#   cause instead of the entry's own confidence. 13 of the 19
+#   `multi_misattribution_probe` rows change their user message: 4 take
+#   only a new header, 5 only gain a log read, and 4 get both. Their gold
+#   answer and meta do not move, and no other row does.
+FROZEN_SLICE_SHA256 = "b3c5c98a8084183e3c141647c757d294b6776895efd721c35f4e45116060e5f2"
 
 # The whole exam, the frozen slice plus the ten `shared_origin_decoy_probe`
 # rows (263 until 2026-09-24, 252 since). First captured on `main` @
@@ -915,7 +922,7 @@ FROZEN_SLICE_SHA256 = "b6f61e68c7615288452b48935031b649f502e21c1fad3ba7c7d7a96f1
 # same job-2 generator fix that moved `FROZEN_SLICE_SHA256` above (see its
 # 2026-09-24 entry). None of the ten `shared_origin_decoy_probe` rows
 # moves, so this digest moves only because the frozen slice inside it does.
-EVAL_SET_SHA256 = "ae4e0885d6b0ea705b77794781dd0c4fed37fbb5b32969ab484c2d0564db8c34"
+EVAL_SET_SHA256 = "a8ecb21ddbc2f3fc2fde7620c7a8df9fd0213be9a6747a6b7966c1fcea87e2ac"
 
 
 def _digest(rows) -> str:
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_cases.py tests/test_evidence_overlap.py tests/test_exam_graded_view.py tests/test_generate.py tests/test_shared_origin_training.py
```

Expected: the summary line reads `8 failed, 198 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_cases.py::test_cap_reads_drops_droppable_reads_from_the_end_and_never_a_kept_one
FAILED tests/test_evidence_overlap.py::test_eval_only_evidence_reuse_matches_the_declared_allowlist
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_generate.py::test_every_crash_family_workload_in_a_multi_row_keeps_its_log_read
FAILED tests/test_generate.py::test_every_job2_header_follows_kubeagents_rule
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-7
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=7 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/cases.py b/src/kubeagent_verdict/dataset/cases.py
index eaf3aca..c9f440e 100644
--- a/src/kubeagent_verdict/dataset/cases.py
+++ b/src/kubeagent_verdict/dataset/cases.py
@@ -179,6 +179,40 @@ def _log_read(e: CatalogEntry, n: Names, evidence: str) -> c.EvidenceRead | None
         content=content.format(ns=n.ns, pod=n.pod, container=container))
 
 
+def _multi_reads(e: CatalogEntry, n: Names,
+                 object_reads: tuple[c.EvidenceRead, ...]) -> list[tuple[c.EvidenceRead, bool]]:
+    """One workload's reads in a multi-workload row, at most two, each paired
+    with whether the row's cap may drop it. A crash-family workload keeps
+    its first object read, then its clear log read, which the cap never
+    drops. Any other workload keeps its first two object reads.
+
+    Two object reads and then the log read would lose the log read in most
+    crash-family blocks: measured at seed 17, size 8000, 784 of 847.
+    """
+    log = _log_read(e, n, "clear")
+    if log is None:
+        return [(read, False) for read in object_reads[:2]]
+    return [(read, False) for read in object_reads[:1]] + [(log, True)]
+
+
+def _cap_reads(reads: list[tuple[c.EvidenceRead, bool]]) -> tuple[c.EvidenceRead, ...]:
+    """Cut a multi-workload row's reads to kubeagent's budget. Droppable
+    reads go from the end; a read marked keep (the origin read, a log
+    read) never goes. A plain `[:8]` would have cut a log read in 34 rows
+    at seed 17, size 8000.
+    """
+    out = list(reads)
+    for i in range(len(out) - 1, -1, -1):
+        if len(out) <= c.MAX_TOOL_CALLS:
+            break
+        if not out[i][1]:
+            del out[i]
+    if len(out) > c.MAX_TOOL_CALLS:
+        raise ValueError(f"{len(out)} reads the cap may not drop; the budget is "
+                         f"{c.MAX_TOOL_CALLS}")
+    return tuple(read for read, _keep in out)
+
+
 def _row_decoy(decoys: list[str]) -> dict:
     """The row-level `decoy_cause` key, from the row's own decoy list.
 
@@ -700,6 +734,12 @@ def multi_misattribution_probe(pairs: list[tuple[CatalogEntry, Names]],
     the trace hands `attributed` to a candidate the evidence does not
     support, while the evidence itself stays untouched and still points at
     each constituent's own cause.
+
+    Each constituent's header is the one kubeagent's confidence rule gives
+    that attributed cause, and each reads what it would read in `multi`:
+    its first two object reads, or for a crash-family entry its first
+    object read and then its log read. The answer keeps the entry's own
+    confidence.
     """
     if not 2 <= len(pairs) <= 4:
         raise ValueError("multi_misattribution_probe takes 2-4 workloads")
@@ -725,8 +765,9 @@ def multi_misattribution_probe(pairs: list[tuple[CatalogEntry, Names]],
         raw = rules.attribute(refuted, ns=n.ns, pod=n.pod, issue=e.issue)
         result = rules.decide(raw)
         candidates = _to_contract_candidates(raw, result)
-        workloads.append(_workload(e, n, candidates, confidence=conf, result=result))
-        all_reads.extend(object_reads(refuted, ns=n.ns, pod=n.pod)[:2])
+        workloads.append(_workload(e, n, candidates, render.header_for(candidates),
+                                   result=result))
+        all_reads.extend(_multi_reads(e, n, tuple(object_reads(refuted, ns=n.ns, pod=n.pod))))
         cause = _fmt(e.own_cause, n)
         rows.append({"workload": f"{n.ns}/{n.name}", "cause": cause,
                      "confidence": conf, "rationale": _fmt(e.rationale, n)})
@@ -736,8 +777,9 @@ def multi_misattribution_probe(pairs: list[tuple[CatalogEntry, Names]],
         decoy_by_workload[key] = [cand.cause for cand in candidates]
         results.append(result)
     group = "+".join(f"{e.key}:{n.ns}/{n.name}" for e, n in pairs)
+    # No origin read and at most 4 workloads of 2 reads each: never over 8.
     user = _user_message(None, None, "", (), tuple(workloads),
-                         tuple(all_reads[:c.MAX_TOOL_CALLS]), key=group)
+                         _cap_reads(all_reads), key=group)
     lines = [f"{len(pairs)} workloads are failing for separate reasons."]
     lines += [f"{r['workload']}: {r['cause']}." for r in rows[:3]]
     label = rules.label(rules.shared(tuple(results)))
@@ -1401,6 +1443,11 @@ def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random,
     Passing a trainable scenario here prepends the SAME origin read with the
     content showing that component healthy, and "separate reasons" stays the
     right answer. Only the read's content separates the two classes.
+
+    Each workload gives at most two reads (`_multi_reads`), and a
+    crash-family workload always keeps its log read. `_cap_reads` holds the
+    row to kubeagent's budget of 8 without dropping a log read or the
+    origin read.
     """
     if not 2 <= len(pairs) <= 4:
         raise ValueError("multi takes 2-4 workloads")
@@ -1421,7 +1468,8 @@ def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random,
         all_objects = tuple(obj for objs in combined_objects for obj in objs)
         healthy_read = _resolve_multi_healthy_origin(healthy_origin, h, all_objects)
         if healthy_read is not None:
-            all_reads.append(c.EvidenceRead(label=healthy_read[0], content=healthy_read[1]))
+            all_reads.append((c.EvidenceRead(label=healthy_read[0], content=healthy_read[1]),
+                              True))
     for i, (e, n) in enumerate(pairs):
         objects = combined_objects[i]
         conf = _confidence(e)
@@ -1436,7 +1484,7 @@ def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random,
         else:
             expected_cause = _fmt(e.own_cause, n)
             rationale = _fmt(e.rationale, n)
-        all_reads.extend(reads[:2])  # stay under the 8-read budget at 4 workloads
+        all_reads.extend(_multi_reads(e, n, reads))
         rows.append({"workload": f"{n.ns}/{n.name}", "cause": expected_cause,
                      "confidence": conf, "rationale": rationale})
         key = f"{n.ns}/{n.name}"
@@ -1461,8 +1509,8 @@ def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random,
     extra_meta = render.prompt_meta(workloads_meta, label=label,
                                     decoy_by_workload=decoy_by_workload)
     group = "+".join(f"{e.key}:{n.ns}/{n.name}" for e, n in pairs)
-    user = _user_message(None, None, "", (), tuple(workloads),
-                         tuple(all_reads[:c.MAX_TOOL_CALLS]), key=group)
+    user = _user_message(None, None, "", (), tuple(workloads), _cap_reads(all_reads),
+                         key=group)
     lines = [f"{len(pairs)} workloads are failing for separate reasons."]
     lines += [f"{r['workload']}: {r['cause']}." for r in rows[:3]]
     return Example(case="multi", group=group, system=c.SYSTEM_PROMPT, user=user,
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `910 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_cases.py tests/test_evidence_overlap.py tests/test_exam_graded_view.py tests/test_generate.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/cases.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(dataset): keep crash-family log reads and print headers in multi-workload rows

multi took each workload's first two object reads and then cut the
row at 8, so 784 of 847 crash-family workloads lost the log read
kubeagent would have made.

_multi_reads now gives a crash-family workload its first object read
and its log read, and _cap_reads cuts droppable reads from the end
without ever dropping a log read or the origin read.
multi_misattribution_probe does the same and takes its header from
header_for.
EOF
```

### Task 8: `empty_candidates` answers at the entry's confidence and keeps its log read

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`empty_candidates`; remove its dead `remaining` loop and the now-unused `drop` import)
- Test: `tests/test_cases.py`, `tests/test_exam_graded_view.py`, `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `cases._log_read` (Task 4) and the existing `_confidence(e)`.
- Produces: `empty_candidates(e, n)` answers at `_confidence(e)` (it
  answered a flat `medium`), and for a crash-family entry it appends the
  clear log read after the entry's first read. It still prints no header:
  it has no candidates.

**Why (spec sections 4 and 6):** every clear undecided row now answers the
entry's own cause at the entry's own confidence; `empty_candidates` is the
last clear row that did not. The three pinned hashes move; the tests
diff writes their new values.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the failing tests**

Run this. It cuts the tests diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-8
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=8 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_cases.py b/tests/test_cases.py
index eb7606f..e0a7fad 100644
--- a/tests/test_cases.py
+++ b/tests/test_cases.py
@@ -116,7 +116,7 @@ def test_empty_candidates_renders_none_section():
     assert "== BEGIN candidates ==\n(none)\n== END candidates ==" in ex.user
     (row,) = json.loads(ex.assistant)["verdicts"]
     assert row["cause"] == "container killed at its memory limit"  # own phrasing
-    assert row["confidence"] == "medium"
+    assert row["confidence"] == "high"  # a direct entry; was a flat "medium"
 
 
 def test_empty_candidates_has_no_candidates_and_the_fixed_sentence():
@@ -130,6 +130,22 @@ def test_empty_candidates_has_no_candidates_and_the_fixed_sentence():
     assert ex.user.count("considered") == 0
 
 
+def test_empty_candidates_answers_at_the_entrys_confidence_and_keeps_the_log_read():
+    """An empty candidate list does not make the reads say less. The row
+    answers the entry's own cause at the entry's own confidence, like every
+    clear undecided row, and a crash-family entry keeps the log read
+    kubeagent makes for it."""
+    for e in catalog.trainable():
+        n = names_mod.draw(random.Random(25))
+        ex = cases.empty_candidates(e, n)
+        (row,) = json.loads(ex.assistant)["verdicts"]
+        assert row["confidence"] == cases._confidence(e), e.key
+        assert ex.meta["expected_confidence"] == cases._confidence(e), e.key
+        log = cases._log_read(e, n, "clear")
+        if log is not None:
+            assert f"== {log.label} ==\n{log.content}" in ex.user, e.key
+
+
 def test_multi_has_one_row_per_workload():
     rng = random.Random(26)
     pairs = [(_entry("memory-limit-oomkill"), names_mod.draw(rng)),
diff --git a/tests/test_exam_graded_view.py b/tests/test_exam_graded_view.py
index 55e6769..b13e00e 100644
--- a/tests/test_exam_graded_view.py
+++ b/tests/test_exam_graded_view.py
@@ -45,10 +45,10 @@ Re-pinned on 2026-09-24 for the job-2 generator fix
 moves, and this view keeps it whole, so the digest follows every rendered
 change `FROZEN_SLICE_SHA256`'s 2026-09-24 entry lists in
 `tests/test_shared_origin_training.py`. The new exam is a new baseline.
-It moved three times on that branch: once for the catalogue's log-cause
+It moved four times on that branch: once for the catalogue's log-cause
 text, once for the single undecided builder, which also cut the exam from
-263 rows to 252, and once for the multi-workload rows' log reads and
-headers.
+263 rows to 252, once for the multi-workload rows' log reads and headers,
+and once for `empty_candidates`' confidence and log read.
 """
 
 from __future__ import annotations
@@ -75,7 +75,7 @@ def view(row):
             "flagged": [v["workload"] for v in gold["verdicts"]]}
 
 
-GRADED_VIEW_SHA256 = "74f55a1d64eaeb5fec11d5b871ac69b93dfc4d60700936843477a6e7063a4a81"
+GRADED_VIEW_SHA256 = "250f2bc2bc6860ec5e04e9574e36b8cf23cea2625961b735bb1a0888914d5b18"
 
 
 def _digest(views) -> str:
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index f848b8a..459d785 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -855,7 +855,13 @@ def test_the_eval_set_is_two_hundred_and_fifty_two_rows():
 #   `multi_misattribution_probe` rows change their user message: 4 take
 #   only a new header, 5 only gain a log read, and 4 get both. Their gold
 #   answer and meta do not move, and no other row does.
-FROZEN_SLICE_SHA256 = "b3c5c98a8084183e3c141647c757d294b6776895efd721c35f4e45116060e5f2"
+# - `empty_candidates` answers at the entry's own confidence instead of a
+#   flat `medium`, and a crash-family entry keeps its log read. 16 of its
+#   19 rows change their gold answer and meta (`medium` to `high`, one per
+#   direct entry), and 5 of those 16 also change their user message (one
+#   per crash-family entry). The other 3 are the indirect entries, whose
+#   own confidence is `medium`. No other row moves.
+FROZEN_SLICE_SHA256 = "aff7cc96aaec86bf7ce7d972632966a2c770adcde9facd4c8ef2b427f2f8c490"
 
 # The whole exam, the frozen slice plus the ten `shared_origin_decoy_probe`
 # rows (263 until 2026-09-24, 252 since). First captured on `main` @
@@ -922,7 +928,7 @@ FROZEN_SLICE_SHA256 = "b3c5c98a8084183e3c141647c757d294b6776895efd721c35f4e45116
 # same job-2 generator fix that moved `FROZEN_SLICE_SHA256` above (see its
 # 2026-09-24 entry). None of the ten `shared_origin_decoy_probe` rows
 # moves, so this digest moves only because the frozen slice inside it does.
-EVAL_SET_SHA256 = "a8ecb21ddbc2f3fc2fde7620c7a8df9fd0213be9a6747a6b7966c1fcea87e2ac"
+EVAL_SET_SHA256 = "97a89e93fc5fdfdfebd0689fb5b74e060b68ba6879236ca12533e33a4ecb9c81"
 
 
 def _digest(rows) -> str:
```

- [ ] **Step 2: Run the changed tests and watch them fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_cases.py tests/test_exam_graded_view.py tests/test_shared_origin_training.py
```

Expected: the summary line reads `6 failed, 160 passed`. The `FAILED` and `ERROR` lines name exactly these tests, in this order. The text after ` - ` on each line is the assertion and is not part of the check.

```text
FAILED tests/test_cases.py::test_empty_candidates_renders_none_section
FAILED tests/test_cases.py::test_empty_candidates_answers_at_the_entrys_confidence_and_keeps_the_log_read
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
```

Any other failure, or a missing one, means the tree is not where this plan expects it. STOP and report.

- [ ] **Step 3: Apply the source**

Run this. It cuts the source diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-8
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=8 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/src/kubeagent_verdict/dataset/cases.py b/src/kubeagent_verdict/dataset/cases.py
index c9f440e..54c5511 100644
--- a/src/kubeagent_verdict/dataset/cases.py
+++ b/src/kubeagent_verdict/dataset/cases.py
@@ -25,7 +25,6 @@ from kubeagent_verdict.dataset.render import (
     apply_budget,
     bind,
     draw_ending,
-    drop,
     object_reads,
     prompt_meta,
     refute,
@@ -689,18 +688,24 @@ def contradiction_probe(e: CatalogEntry, n: Names) -> Example:
 
 
 def empty_candidates(e: CatalogEntry, n: Names) -> Example:
-    names = dataclasses.asdict(n)
-    bound = tuple(bind(obj, names) for obj in e.objects)
-    remaining = bound
-    for obj in bound:
-        remaining = drop(remaining, obj)
+    """No candidates at all: the reads alone name the cause.
+
+    The row answers the entry's own cause at `_confidence(e)`, as every
+    clear undecided row does; until 2026-09-24 it answered a flat `medium`.
+    It reads the entry's first read and, for a crash-family entry, the clear
+    log read kubeagent makes for it. No candidates means no header.
+    """
     result = rules.Result(decided=False, cause="", outcome="", evidence="",
                           group_key="", group_text="", decisions=())
     w = _workload(e, n, (), confidence="", result=result)
     reads = (c.EvidenceRead(label=_fmt(e.reads[0][0], n), content=_fmt(e.reads[0][1], n)),)
+    log = _log_read(e, n, "clear")
+    if log is not None:
+        reads += (log,)
     user = _user_message(None, None, "", _service_issues(e, n), (w,), reads, key=e.key)
     cause = _fmt(e.own_cause, n)
-    rows = [{"workload": f"{n.ns}/{n.name}", "cause": cause, "confidence": "medium",
+    conf = _confidence(e)
+    rows = [{"workload": f"{n.ns}/{n.name}", "cause": cause, "confidence": conf,
              "rationale": _fmt(e.rationale, n)
                           + " The candidate list shown did not include this cause."}]
     summary = f"{n.ns}/{n.name} is failing: {cause}.\nNo deterministic candidates were available."
@@ -708,7 +713,7 @@ def empty_candidates(e: CatalogEntry, n: Names) -> Example:
     wm = workload_meta(result, expected_cause=cause,
                        own_cause_keywords=list(e.own_cause_keywords))
     meta = {"case": "empty_candidates", "entry": e.key, "expected_cause": cause,
-            "expected_confidence": "medium",
+            "expected_confidence": conf,
             "expected_own_keywords": list(e.own_cause_keywords)}
     meta.update(prompt_meta({key: wm}, label="none", decoy_by_workload={key: []}))
     return Example(case="empty_candidates", group=f"{e.key}:{n.ns}/{n.name}",
```

- [ ] **Step 4: Run the full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `911 passed, 2 skipped` (plus the 6 old warnings), then `All checks passed!`. A different count, or any failure, means STOP and report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_cases.py tests/test_exam_graded_view.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/cases.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
fix(dataset): answer empty_candidates at the entry's confidence and keep its log read

empty_candidates answered a flat medium. Every other clear undecided
row answers at the entry's own confidence, so this one does too. A
crash-family entry also gets the log read kubeagent makes.

The dead loop that dropped every object and was never read goes, and
with it the unused drop import.
EOF
```

### Task 9: Record the fix, then regenerate the dataset

**Files:**
- Modify: `contract/PIN.md` (header text; a "2026-09-24 — the job-2 generator fix." entry)
- Modify: `docs/design.md` (case-mix table; a dated paragraph on the fix; the multi-workload numbers; the contradiction paragraph, now in the past tense)
- Test: `tests/test_shared_origin_training.py` (one docstring)
- Generated, never committed: `out/dataset-0924/` (`out/` is gitignored)

**Interfaces:**
- Consumes: everything Tasks 1 to 8 built.
- Produces: `out/dataset-0924`, the bank `tests/test_exam_prompt_stability.py`
  reads since Task 3. After this task its 2 tests run instead of
  skipping.

**Why (spec "The pins that move" and "Run order"):** `contract/PIN.md` is
where every pin move records its reason, and `docs/design.md` must match
the code. The regeneration proves that the exam the code builds is the
exam the pins describe.

This task changes no code, so it has no red phase. Its test change is a
docstring.

**Rulings that bind this task** (copied from the plan head; the
numbers are the head's):

11. **The prompt-stability test skips from Task 3 to Task 9.** Task 3
    changes prompts, so the test is re-pointed at the new bank,
    `out/dataset-0924`. That bank does not exist until Task 9 builds it.
    Its 2 tests skip in between. That is expected.
13. **`docs/design.md`'s "~55% of the mix" is left alone.** It was already
    stale before this branch, and this branch does not change the rows it
    sums.

**Constraints** (from the plan head, so this brief stands alone): work in
`/home/ubuntu/git/kubeagent-verdict` on branch
`spec-wrong-attribution-generator`. Apply the diffs with the commands
given; never retype them. If `git apply --check` fails, or any count,
hash or failure list differs from this brief, STOP and report; do not
paste your value in. Never run a test with `-update`. `JOB1_BAR`,
`JOB2_BAR` and `JOB3_BAR` keep their values. Name each file on
`git add`, never `-A` or `.`. The commit carries no AI attribution of any
kind.

- [ ] **Step 1: Apply the docstring change**

Run this. It cuts the docstring diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-9
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=9 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=1 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-tests.patch
git -c core.fileMode=false apply --check $B-tests.patch && git -c core.fileMode=false apply $B-tests.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/tests/test_shared_origin_training.py b/tests/test_shared_origin_training.py
index 459d785..d9bdd84 100644
--- a/tests/test_shared_origin_training.py
+++ b/tests/test_shared_origin_training.py
@@ -504,11 +504,16 @@ def test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_r
     case-family share under the 0.40 cap here rather than moving it once
     more.
 
+    Re-measured 2026-09-24, after the case mix moved 7 points from
+    `none_of_these` to `own_cause` and `wrong_attribution` -- 0.3810 at this
+    module's size, 0.3836 at the build size.
+
     That case-family share is not the share of multi-workload rows whose
     graded answer actually claims a shared origin. That answer-level share
-    is about 7 of every 100 -- 214 of 3,126 at build size 8000, counted on
-    the same kept pile the numbers above come from -- and this test does
-    not measure it and does not guard it.
+    is about 7 of every 100 -- 214 of 3,128 at build size 8000 (214 of
+    3,126 before the 2026-09-24 case-mix change), counted on the same kept
+    pile the numbers above come from -- and this test does not measure it
+    and does not guard it.
     """
     shared = len(_by_case(kept, "shared_origin"))
     separate = (len(_by_case(kept, "multi"))
```

- [ ] **Step 2: Run the changed test file**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --tb=line -rfE tests/test_shared_origin_training.py
```

Expected: `51 passed`, no failure. There is nothing to watch fail: only a
docstring changed. A different count, or any failure, means STOP and
report. Never edit a pinned value to match what you see.

- [ ] **Step 3: Apply the docs**

Run this. It cuts the docs diff below out of your brief and applies it:

```bash
cd /home/ubuntu/git/kubeagent-verdict
B=.superpowers/sdd/2026-09-24-job2-generator-fix/task-9
[ -s $B-brief.md ] || { mkdir -p .superpowers/sdd/2026-09-24-job2-generator-fix && printf '*\n' > .superpowers/sdd/.gitignore; awk -v n=9 '/^```/{f=!f} !f&&/^#+[ \t]+Task[ \t]+[0-9]+/{t=($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))} t' docs/superpowers/plans/2026-09-24-job2-generator-fix.md > $B-brief.md; }
awk -v k=2 '/^```diff$/{n++; if(n==k){on=1; next}} on&&/^```$/{exit} on' $B-brief.md > $B-src.patch
git -c core.fileMode=false apply --check $B-src.patch && git -c core.fileMode=false apply $B-src.patch
```

If `apply --check` prints an error, STOP and report it. The diff it applies:

```diff
diff --git a/contract/PIN.md b/contract/PIN.md
index 3e12de0..125e9f5 100644
--- a/contract/PIN.md
+++ b/contract/PIN.md
@@ -65,7 +65,9 @@ contract version.
 ## Dataset pin moves
 
 The exam's two hashes live in `tests/test_shared_origin_training.py`:
-`FROZEN_253_SHA256` over the first 253 rows and `EVAL_SET_SHA256` over all
+`FROZEN_SLICE_SHA256` over every row before the ten
+`shared_origin_decoy_probe` rows (242 rows) and `EVAL_SET_SHA256` over all
+252. Until 2026-09-24 the first was `FROZEN_253_SHA256`, over 253 rows of
 263. They are pinned so a change to the generators cannot move the exam
 without someone saying why. This is where the why is recorded.
 
@@ -140,3 +142,41 @@ without someone saying why. This is where the why is recorded.
   their answer on their own menu. A job-2 number measured before this was
   scored by a grader that zeroed those 20 workloads for every reply, so it
   does not compare with one measured after.
+
+- **2026-09-24 — the job-2 generator fix.** Both hashes moved, and so did
+  the graded-view pin (`tests/test_exam_graded_view.py`). Before the fix,
+  `none_of_these` and `wrong_attribution` built the same prompt for 27 of
+  28 catalogue entries and gave it two different answers, so the model
+  could not learn to override a wrong tag. Now one builder makes every
+  undecided row, and the reads decide the answer. `FROZEN_253_SHA256` is
+  renamed `FROZEN_SLICE_SHA256`: the `none_of_these` slice falls from 19
+  rows to 8, so the exam falls from 263 rows to 252 and the frozen slice
+  from 253 to 242. The frozen slice still means every row before the ten
+  `shared_origin_decoy_probe` rows, and a test pins its length. This time
+  rendered bytes move, not only `meta`, so the new exam is a new baseline:
+  no number on it compares with one from before. The banked exam the
+  prompt-stability test reads is now `out/dataset-0924/test.jsonl`. The
+  footprint, in commit order, measured by diffing the exam before and
+  after each change:
+  - The catalogue stopped doubling the `log cause: ` prefix and quotes the
+    container in `restart-loop`'s evidence. 41 rows change, in the user
+    message only.
+  - One builder makes every undecided row. All 19 `own_cause` rows change
+    their user message, and 16 of them their gold answer and meta. All 19
+    `misattribution_probe` rows change their user message. 9 of 19
+    `wrong_attribution` rows change their user message. The held-out rows
+    interleave by entry, so every row after the first changed entry
+    shifts.
+  - A multi-workload row keeps its crash-family log reads, and
+    `multi_misattribution_probe` prints the header kubeagent's confidence
+    rule gives. 13 of its 19 rows change their user message only.
+  - `empty_candidates` answers at the entry's own confidence and keeps its
+    log read. 16 of its 19 rows change their gold answer and meta, and 5
+    of those 16 also change their user message.
+
+  No other row moves. The paste-the-prompt bot scores 76/142 = 0.5352 on
+  job 2, up from 76/153 = 0.4967: the exam lost 11 `none_of_these`
+  workloads, none of them keyword-graded. It still scores below
+  `JOB2_BAR` (0.7), which does not move. The full per-change footprint is
+  in the comment above `FROZEN_SLICE_SHA256` in
+  `tests/test_shared_origin_training.py`.
diff --git a/docs/design.md b/docs/design.md
index eb9477c..276ff00 100644
--- a/docs/design.md
+++ b/docs/design.md
@@ -263,15 +263,15 @@ The case mix is what adjudication means, in approximate proportions:
 | Case | Share | Teaches |
 |---|---|---|
 | Candidate attributed, evidence supports it | ~6% | Pick the candidate **verbatim**; calibrate confidence |
-| `none_of_these` — evidence rules all candidates out | ~11% | Refusing the offered menu |
-| Own evidence-grounded cause (unlisted) | ~10% | Naming what the deterministic pass missed |
+| `none_of_these` — thin evidence: every candidate is ruled out or refuted, and no read names a cause | ~4% | Abstaining: saying no cause is shown when the reads name none |
+| Own evidence-grounded cause (unlisted) | ~13% | Naming what the deterministic pass missed |
 | Multi-workload prompts (2–4 flagged, mixed causes) | ~13% | One verdict row per listed workload, no extras |
 | `shared_origin` — 2–4 flagged, all downstream of one broken component | ~15% | Naming the story's cause on every row the rules do not decide and the rules' own cause on every row they do; calling it shared only when the rules confirm it |
 | `shared_origin_decoy` — the same scenario, origin read HEALTHY | ~15% | Taking each workload's own cause when the read refutes the shared story. Emitted as `shared_origin`'s twin from one salt, never independently; the two shares must stay equal |
 | Truncated evidence (marker present) | ~5% | Judging honestly under cut evidence — lower confidence |
 | Injection attempts inside evidence | ~10% | Evidence is data; fake `== END ==` markers and "ignore your instructions" text change nothing |
 | Empty candidates / healthy distractors mixed in | ~5% | Not inventing problems |
-| `wrong_attribution` — the `attributed` tag is on a candidate the evidence contradicts | ~10% | The tag is a hint, not an answer: evidence overrides it |
+| `wrong_attribution` — the `attributed` tag is on a candidate the evidence contradicts | ~14% | The tag is a hint, not an answer: evidence overrides it |
 
 That table is `CASE_MIX` in `src/kubeagent_verdict/dataset/generate.py`, and
 it is meant to be read against it rather than trusted on its own. An earlier
@@ -281,6 +281,22 @@ tag-copying, which is the shortcut this whole section is about. It was
 wrong from the commit that introduced the case until a pre-publication
 audit recomputed it.
 
+On 2026-09-24 three rows of the table moved together. `none_of_these`
+went from ~11% to ~4%, and its points went to own cause (~10% to ~13%)
+and `wrong_attribution` (~10% to ~14%). The three still add up to 31%.
+Before that, `none_of_these` and `wrong_attribution` built the same
+prompt for 27 of 28 catalogue entries and gave it two different answers,
+so the model could not learn to override a wrong tag. Now one builder
+makes all three cases, and the reads decide the answer. A clear row's
+reads name the entry's own cause, and the row answers it. A thin row's
+reads rule out or refute every candidate and name no cause, and the row
+answers `none_of_these` at `low`. Thin evidence exists for four entries
+only: `crashloop-pod`, `coredns-corefile-broken`, `init-crashloop` and
+`restart-loop`. For each of them, and for each shape (ruled out or
+refuted), clear rows outnumber thin ones: 54 to 59 clear rows against 40
+thin at build size 8000, before the exam's groups are dropped. A test
+pins that, so "none of these" never becomes the easy answer for an entry.
+
 `shared_origin` took its four points from `multi` rather than from the mix
 growing, and that is a deliberate cost. Job 3 now grades both failure modes
 as one number: never claiming a shared cause fails as soon as one is real,
@@ -298,7 +314,8 @@ rows onto the cap below. That case family stays the minority of the
 100), and a test fails above 40 of every 100. The cap guards that
 case-family share, not the answer itself: of the rows the model actually
 reads, about 7 of every 100 multi-workload rows carry a gold answer that
-claims a shared origin (214 of 3,126 at build size 8000).
+claims a shared origin (214 of 3,128 at build size 8000, re-measured
+on 2026-09-24; it was 214 of 3,126 before that day's case-mix change).
 
 Its scenarios come from `propagation.trainable_scenarios()`, a pool disjoint
 from the six the `shared_origin_probe` eval slice draws from — disjoint in key
@@ -414,8 +431,9 @@ truncated or thin → low), so calibration is trained, not guessed.
   so the model has never seen that (entry, workload) pair.
 - The third closes a hole the first two could not see. `multi` is ~13% of
   the curriculum and had no test row at all, and `cases.multi()` never
-  swaps a tag — so across all 2,127 constituent workloads it contributes to
-  train and val at `--seed 17 --size 8000` (3,160 before `drop_held_out`),
+  swaps a tag — so across all 2,140 constituent workloads it contributes to
+  train and val at `--seed 17 --size 8000` (3,157 before `drop_held_out`;
+  2,127 and 3,160 before the 2026-09-24 case-mix change),
   "trust the `attributed` tag" is a strategy the training data never once
   contradicts in that shape. Both single-workload probes render one
   workload, so neither can reach it. `multi_misattribution_probe` renders
@@ -620,10 +638,12 @@ touched.
 A fourth slice, `contradiction_probe`, was then built specifically to be
 one, and negative control v4 scored the same broken model on it: **1.0
 cause, 0.0 decoy**, with the expected rationale and summary reproduced
-verbatim. It reuses `none_of_these_case`'s read text, and `none_of_these`
-is 15% of the curriculum, so the contradiction sentence is a trained
+verbatim. It reused `none_of_these_case`'s read text, and `none_of_these`
+was 15% of the curriculum, so the contradiction sentence was a trained
 trigger for a trained answer template rather than something to reason
-about. Holding the adversarial menu roughly fixed and changing only the
+about. (Since 2026-09-24 `none_of_these` rows are built from thin evidence
+on four entries, at `low` confidence, and share neither this slice's reads
+nor its rationale.) Holding the adversarial menu roughly fixed and changing only the
 read text moves cause accuracy from 0.1579 (`misattribution_probe`) and
 0.4737 (`wrong_attribution`) to 1.0. The slice is kept — it does defeat an
 index-copier, a tag-copier and a word counter — but not as a memorisation
```

- [ ] **Step 4: Full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `911 passed, 2 skipped` (plus the 6 old warnings), then
`All checks passed!`. A different count, or any failure, means STOP and
report. Never edit a pinned value to match what you see.

- [ ] **Step 5: Regenerate the dataset**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-0924
```

Use the `kv-dataset` entry point. `python -m kubeagent_verdict.dataset.cli`
does nothing: the module has no `__main__` guard. `PYTHONPATH=src` matters
here too.

- [ ] **Step 6: Check what it built**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -c "import json; m=json.load(open('out/dataset-0924/manifest.json')); print(json.dumps({k: m[k] for k in ('seed', 'size', 'train', 'val', 'test')})); print(json.dumps(m['case_counts'], sort_keys=True)); print(json.dumps(m['test_case_counts'], sort_keys=True))" && sha256sum out/dataset-0924/*.jsonl
```

Expected, exactly:

```text
{"seed": 17, "size": 8000, "train": 6496, "val": 655, "test": 252}
{"attributed": 410, "empty_candidates": 353, "injection": 709, "multi": 728, "none_of_these": 278, "own_cause": 920, "shared_origin": 1200, "shared_origin_decoy": 1200, "truncated": 358, "wrong_attribution": 995}
{"attributed": 53, "contradiction_probe": 19, "empty_candidates": 19, "injection": 19, "misattribution_probe": 19, "multi_misattribution_probe": 19, "none_of_these": 8, "own_cause": 19, "positional_probe": 19, "shared_origin_decoy_probe": 10, "shared_origin_probe": 10, "truncated": 19, "wrong_attribution": 19}
b10ff8da85ba8aae707fc646c63d56c7eabb431423b689399e387c543370254b  out/dataset-0924/test.jsonl
cdbbd6513146bd4929a1ce32035531e316e0e2f94ed801e728b8f7e4babe20db  out/dataset-0924/train.jsonl
6253cf8d43979e1ec5804025d2602eb8450f76677add0eb3cfbfebe1494dd020  out/dataset-0924/val.jsonl
```

Read the counts. `none_of_these` is 8 in the exam (4 thin entries × 2
shapes), and 278 of the 7,151 train and val rows. `own_cause` and
`wrong_attribution` together hold 1,915 of them.

A different count or hash means STOP and report. Do not rebuild with
other flags, and never edit a pinned value to match what you see.

- [ ] **Step 7: The prompt-stability test runs again, and the full suite**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_exam_prompt_stability.py && PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider && .venv/bin/ruff check --ignore EXE002 .
```

Expected: `2 passed`, then `913 passed` with no skip, then
`All checks passed!`. A different count, or any failure, means STOP and
report. Never edit a pinned value to match what you see.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c core.fileMode=false add tests/test_shared_origin_training.py contract/PIN.md docs/design.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -F - <<'EOF'
docs: record the job-2 generator fix in PIN.md and the design

PIN.md gets the dated entry for every pin this fix moved, and why.
design.md's case-mix table, multi-workload numbers and contradiction
paragraph now match the code.
EOF
```

Nothing from `out/` is committed; it is gitignored. After the commit,
`git -c core.fileMode=false status --short` prints nothing.
