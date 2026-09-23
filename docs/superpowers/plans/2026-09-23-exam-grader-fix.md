# Exam Grader Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the exam gradable — 20 job-2 workloads currently score 0.0
whatever the model answers, because their grading keywords are empty — then
re-score the banked 0920 replies against the corrected grader with no new
inference.

**Architecture:** Four layers, in order. A prompt-stability harness pins the
banked exam's `messages` so later tasks can prove they moved only `meta`.
Twenty-two curated keyword pairs go onto `propagation.Victim` and
`propagation.Propagation` and flow through the one branch
`_shared_origin_row` already has. The grader then refuses a job-2 workload it
cannot grade instead of scoring it zero. Finally `kv-eval --replay` re-scores
stored replies and records where they came from.

**Tech Stack:** Python 3, pytest, ruff. No new dependency. No cluster, no
model call, no training host.

**Spec:** [docs/superpowers/specs/2026-09-23-exam-grader-fix-design.md](../specs/2026-09-23-exam-grader-fix-design.md)
(commits `b212eb8` + `6248302`). Read it before Task 1 — this plan argues
from it and does not restate its reasoning.

## Global Constraints

- **No bar moves.** `JOB1_BAR = 0.9` (score.py:104), `JOB2_BAR = 0.7`
  (score.py:139), `JOB3_BAR = 0.9` (score.py:176) keep their values.
- **Never run a test with `-update`.** Every pinned value is re-written by
  hand with a dated comment.
- **If a measured value differs from this plan's expected value, STOP and
  report it. Do not paste your value in.** The expected values here were
  derived, not observed; a mismatch means the derivation was wrong and that
  is worth knowing.
- **Curate blind (spec section 4).** No keyword pair may be revised because
  of what it did to a score. The 22 pairs in Task 2 are final input, not
  suggestions.
- **TDD.** Failing test first, watch it fail, then implement.
- **Commits:** `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "..."`.
  Never `git add -A` — name each file. **No Claude/Anthropic attribution of
  any kind** in any commit message.
- **Branch:** `fix-exam-then-override`. Never commit to `main`.
- Run everything from `.venv`: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest`.
  `ruff` must pass on every commit. Note: ruff currently reports 78 `EXE002`
  errors from pre-existing stale file-mode bits, unrelated to this work.
  Those 78 are the baseline — your commits must not add a 79th.
- **Promise rule.** A comment, docstring, test name or error string that
  promises what the code does not keep is a defect. Every comment you
  replace in this plan is being replaced because it broke this rule.

---

## Rulings

Two things the approved spec did not anticipate. Both were measured during
planning. They are settled here; do not re-open them.

### Ruling 1: six pinned values move, not four

The spec's "The pins that move" table names four. It is six.
`generate.to_row` includes `meta` in the row it returns, and
`tests/test_shared_origin_training.py`'s `_digest` hashes `to_row`'s output.
Adding keywords to `meta` therefore moves both dataset digests:

- `FROZEN_253_SHA256` (tests/test_shared_origin_training.py:797)
- `EVAL_SET_SHA256` (tests/test_shared_origin_training.py:850)

This is expected and harmless, and Task 1 exists to prove it: the
prompt-stability test shows `messages` are byte-identical, so the digest
moved on `meta` alone. Both constants already carry a comment block
documenting three previous moves; each gets a fourth dated entry in the
same style.

### Ruling 2: the refusal is scoped to corpora that are being graded on job 2

Spec section 1 justifies raising in the grader with "The grader only ever
sees the exam." That is false. `tests/test_oracle.py` feeds train and val
to the same `score.evaluate`. Measured:

| corpus | job-2 workloads with a named cause and no keywords |
|---|---|
| exam | 20 |
| train | 4,823 |
| val | 589 |

An unconditional raise breaks `_train_results()` and `_val_results()`
(tests/test_oracle.py:51, :56) and the six assertions behind them (:116,
:123, :164, :176, :195, :196) — none of which read job 2.

**The ruling, chosen by the user:** the grader raises, exactly as section 1
says. `evaluate` gains `grade_job2: bool = True`. The exam path never passes
it. The oracle's train/val dataset self-check passes `grade_job2=False`,
because it is not grading job 2 there — `_job2_gate` (tests/test_oracle.py:66)
already scores job 2 over its own population and its docstring already says
keyword-less workloads are out of scope for it.

Rejected: curating the 163 training victims and 54 training scenarios
(spec section 1 names this as the cost being avoided), and leaving `job2`
returning 0.0 behind a separate check a caller can skip.

**Consequence, stated rather than hidden.** A new *training* case with
missing keywords is still only caught if it reaches the exam. That is the
price of not curating 217 pairs no grader reads.

---

## File Structure

| file | responsibility | task |
|---|---|---|
| `tests/test_exam_prompt_stability.py` (new) | Proves the regenerated exam's `messages` match the banked `out/dataset-0920/test.jsonl` row for row. The net under every later task. | 1 |
| `src/kubeagent_verdict/dataset/propagation.py` | Gains `own_cause_keywords` on `Victim` and `Propagation`, plus the 22 curated values. | 2 |
| `src/kubeagent_verdict/dataset/cases.py` | `_shared_origin_row` decides cause, rationale and keywords in one branch; `_render_shared_origin` passes the keywords to `render.workload_meta`. | 2 |
| `tests/test_shared_origin_keywords.py` (new) | Coverage, self-containment and discrimination over the eval six. | 2 |
| `tests/test_oracle.py` | Gains `test_exam_oracle_job2_is_perfect` (Task 2); train/val helpers pass `grade_job2=False` (Task 3). | 2, 3 |
| `tests/test_shared_origin_training.py` | Two digests re-pinned by hand. | 2 |
| `tests/test_score.py` | Paste-the-prompt-bot pins re-written by hand; new refusal tests. | 2, 3 |
| `src/kubeagent_verdict/evals/score.py` | `UngradableWorkload`, `_require_job2_gradable`, `evaluate(..., grade_job2=)`. | 3 |
| `src/kubeagent_verdict/evals/cli.py` | `--replay`, and `rescored_from` in the run block. | 4 |
| `tests/test_eval_cli.py` (or the existing CLI test module) | `--replay` argument rules and alignment refusal. | 4 |

---

## Task 1: Pin the banked exam's prompts

**Why first.** Spec section 6 calls this "the entire basis" for re-scoring
stored replies instead of paying for another run. It must exist *before* the
data changes, so that when the digests move in Task 2 there is already a
green test saying the prompts did not.

**Files:**
- Create: `tests/test_exam_prompt_stability.py`

**Interfaces:**
- Consumes: `generate.test_set()`, `generate.to_row(example)` (both in
  `src/kubeagent_verdict/dataset/generate.py`).
- Produces: nothing importable. Task 2 re-runs this module as its guard.

- [ ] **Step 1: Confirm the bank is present and has 263 rows**

```bash
cd /home/ubuntu/git/kubeagent-verdict && wc -l out/dataset-0920/test.jsonl
```

Expected: `263 out/dataset-0920/test.jsonl`. If the file is missing, STOP and
report — every later task's justification depends on it.

- [ ] **Step 2: Write the test module**

Create `tests/test_exam_prompt_stability.py`:

```python
"""The banked exam's prompts must not move.

`out/dataset-0920/test.jsonl` is the exam the 0920 build answered and
`out/eval-0920/results.jsonl` holds its replies verbatim. Re-scoring those
replies against a corrected `meta` is only honest if the QUESTIONS are the
same ones the model saw. This module is that proof: regenerate the exam and
compare `messages` row for row, byte for byte.

`messages` is all three -- system, user and the gold assistant answer.
`score.evaluate` reads the gold answer back out of `messages[2]` to build
its expected verdicts, so a moved gold answer would change the grading as
surely as a moved prompt would change the question.

The bank is gitignored working data, not a committed fixture. When it is
absent this module SKIPS and names the path it wanted, rather than passing
on nothing.
"""
import json
from pathlib import Path

import pytest

from kubeagent_verdict.dataset import generate

BANK = Path(__file__).resolve().parents[1] / "out" / "dataset-0920" / "test.jsonl"

pytestmark = pytest.mark.skipif(
    not BANK.exists(), reason=f"banked exam not present at {BANK}")


def _banked_rows() -> list[dict]:
    return [json.loads(line) for line in
            BANK.read_text(encoding="utf-8").splitlines() if line]


def test_the_banked_exam_is_the_263_row_exam():
    """A guard on the guard. Comparing row for row proves nothing if the
    two sides are different lengths and the zip silently truncates.
    """
    assert len(_banked_rows()) == 263


def test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam():
    """Every rendered byte of the exam -- prompt and gold answer -- comes
    out of `generate.test_set()` today exactly as it went into the bank.

    This is what lets a later change to `meta` be called a re-score rather
    than a new exam.
    """
    banked = _banked_rows()
    fresh = [generate.to_row(e) for e in generate.test_set()]
    assert len(fresh) == len(banked)
    moved = [i for i, (f, b) in enumerate(zip(fresh, banked))
             if f["messages"] != b["messages"]]
    assert not moved, f"rows whose messages moved: {moved}"
```

- [ ] **Step 3: Run it — it must PASS on an unchanged tree**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_exam_prompt_stability.py -v
```

Expected: 2 passed. This test is a regression guard, not a TDD red — it
passes now by construction, and its whole job is to fail in Task 2 if the
field change touches a rendered byte.

If it FAILS now, STOP and report: the banked exam and the generator have
already diverged, and nothing downstream in this plan is safe.

- [ ] **Step 4: Prove the guard can fail**

Temporarily corrupt one row in the comparison to confirm the assertion
actually fires — append ` ` to `fresh[0]["messages"][1]["content"]` in a
scratch copy, run, see it fail, then discard the scratch change. Do not
commit the corruption.

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff --stat tests/test_exam_prompt_stability.py
```

Expected after discarding: the file matches Step 2 exactly.

- [ ] **Step 5: Full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -5 && .venv/bin/ruff check . 2>&1 | tail -3
```

Expected: 794 passed (792 + the 2 new). ruff: 78 `EXE002` errors, unchanged.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s tests/test_exam_prompt_stability.py -m "test(exam): pin the banked exam's messages byte for byte

The exam-grader fix changes per-workload meta and nothing else. That claim
needs a test before the change, not after: regenerate test_set() and compare
messages -- system, user and gold answer -- against out/dataset-0920/test.jsonl
row for row. Skips with a named path when the bank is absent."
```

---

## Task 2: Twenty-two curated keyword pairs

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (two dataclasses, six scenario literals)
- Modify: `src/kubeagent_verdict/dataset/cases.py:758` (`_shared_origin_row`) and `:1012-1016` (the defect site)
- Create: `tests/test_shared_origin_keywords.py`
- Modify: `tests/test_oracle.py` (add `test_exam_oracle_job2_is_perfect`)
- Modify: `tests/test_shared_origin_training.py:797, :850` (two digests)
- Modify: `tests/test_score.py:1919-1923` (bot pins)

**Interfaces:**
- Produces: `propagation.Victim.own_cause_keywords: tuple[str, ...]` and
  `propagation.Propagation.own_cause_keywords: tuple[str, ...]`, both
  defaulting to `()`.
- Produces: `cases._shared_origin_row(result, *, healthy, decoy, shared_cause,
  decoy_keywords, shared_keywords) -> tuple[str, str | None, list[str]]`
  — a THREE-tuple now, where it returned a two-tuple.
- Consumes: `render.workload_meta(result, *, expected_cause, own_cause_keywords)`,
  unchanged.

### The 22 pairs

These are final. They were curated by reading each cause string and the other
causes on its menu, and validated mechanically for self-containment (each
keyword is a lowercase substring of its own cause) and discrimination (no
pair appears in full in the scenario's shared cause, its distractor cause, or
any sibling victim's cause). Zero violations. **They were never checked
against a score** — spec section 4.

| scenario | shared pair | victim index | victim `local_cause` (for placement) | victim pair |
|---|---|---|---|---|
| `coredns-down` | `("coredns", "resolve")` | 0 | the database service name is misspelled in the workload's configuration | `("database", "misspelled")` |
| | | 1 | the readiness probe timeout is too short for this workload | `("readiness", "timeout")` |
| | | 2 | the headless Service for the StatefulSet was deleted | `("headless", "statefulset")` |
| `node-not-ready` | `("notready", "replacements")` | 0 | the pod requests more CPU than any remaining node has free | `("cpu", "remaining")` |
| | | 1 | a second pod already holds the ReadWriteOnce claim {pvc} | `("readwriteonce", "claim")` |
| `storage-provisioner-down` | `("provisioner", "bind")` | 0 | the StatefulSet asks for a storage class that does not exist | `("statefulset", "class")` |
| | | 1 | the Job requests a volume larger than the cluster can provide | `("larger", "provide")` |
| | | 2 | the filesystem on {pvc} is corrupt and will not mount | `("filesystem", "corrupt")` |
| `registry-unreachable` | `("unreachable", "workload")` | 0 | the image tag {image} does not exist in the registry | `("tag", "exist")` |
| | | 1 | the image pull secret in this namespace is missing or wrong | `("secret", "namespace")` |
| | | 2 | the init container image name has a typo | `("init", "typo")` |
| `node-disk-pressure` | `("pressure", "evicting")` | 0 | the pod is missing a toleration for a tainted node | `("toleration", "tainted")` |
| | | 1 | the workload's emptyDir volume has no size limit and filled up | `("emptydir", "filled")` |
| | | 2 | the agent's checkpoint volume is too small for its retention setting | `("checkpoint", "retention")` |
| `networkpolicy-deny-all` | `("networkpolicy", "egress")` | 0 | the payments API the workload depends on is down | `("payments", "depends")` |
| | | 1 | the readiness endpoint for this workload returns an error | `("readiness", "endpoint")` |

Every keyword is a literal word outside every `{node}`/`{pvc}`/`{image}`/`{ns}`
placeholder, so it survives `_fmt`'s substitution unchanged.

Note `node-disk-pressure`'s shared pair. Spec section 3 measured the failure
it exists to prevent: with naive keywords `node`,`worker-3` the reply
`node worker-3 (no kubelet lease)` scored **correct** — right node, wrong
reason, full credit. `("pressure", "evicting")` scores it wrong, which it is.

- [ ] **Step 1: Write the failing coverage and discrimination tests**

Create `tests/test_shared_origin_keywords.py`:

```python
"""The eval six's job-2 grading keywords.

Sixteen victims and six shared causes, one curated pair each. Three
properties, and the second and third are the ones that matter:

- COVERAGE: every eval scenario and victim carries a pair, so no exam
  workload can fall back to the empty list that scored 20 of them 0.0
  whatever the model answered.
- SELF-CONTAINMENT: each keyword is a substring of its own cause. A typo
  here would make the workload unanswerable -- the exact defect being
  fixed, re-introduced one layer up.
- DISCRIMINATION: a pair must not appear in full in any OTHER cause on the
  same menu. Spec section 3 measured what happens without this: a pair of
  `node`,`worker-3` scored `node worker-3 (no kubelet lease)` as correct
  against a gold answer about disk pressure.

The twin leg of the discrimination check is the one spec section 9 names:
a shared-origin workload's gold answer is its own local cause in the
healthy world and the scenario's shared cause in the broken one, so those
two strings are each other's twin and a pair that cannot tell them apart
grades both worlds the same.
"""
from kubeagent_verdict.dataset import propagation as prop


def test_every_eval_scenario_and_victim_carries_a_keyword_pair():
    for p in prop.all_scenarios():
        assert len(p.own_cause_keywords) == 2, p.key
        for v in p.victims:
            assert len(v.own_cause_keywords) == 2, (p.key, v.local_cause)


def test_every_eval_keyword_appears_in_its_own_cause():
    for p in prop.all_scenarios():
        shared = p.shared_cause.lower()
        for k in p.own_cause_keywords:
            assert k == k.lower(), (p.key, k)
            assert k in shared, (p.key, k)
        for v in p.victims:
            local = v.local_cause.lower()
            for k in v.own_cause_keywords:
                assert k == k.lower(), (p.key, k)
                assert k in local, (p.key, v.local_cause, k)


def test_every_eval_keyword_pair_discriminates_on_its_own_menu():
    """No pair matches in full any other cause the same menu prints.

    The menu is three candidates: the victim's own local cause
    (`attributed`), the scenario's distractor, and the shared cause. A
    scenario's victims also share a prompt, so a victim's pair is checked
    against its siblings' causes too.
    """
    for p in prop.all_scenarios():
        shared = p.shared_cause.lower()
        distractor = p.distractor_cause.lower()
        assert not all(k in distractor for k in p.own_cause_keywords), p.key
        for v in p.victims:
            local = v.local_cause.lower()
            kws = v.own_cause_keywords
            assert not all(k in shared for k in kws), (p.key, v.local_cause)
            assert not all(k in distractor for k in kws), (p.key, v.local_cause)
            assert not all(k in local for k in p.own_cause_keywords), (
                p.key, v.local_cause)
            for other in p.victims:
                if other is v:
                    continue
                assert not all(k in other.local_cause.lower() for k in kws), (
                    p.key, v.local_cause, other.local_cause)
```

- [ ] **Step 2: Run them — expect 1 failure, 2 passes**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_keywords.py -v
```

Expected: `test_every_eval_scenario_and_victim_carries_a_keyword_pair` FAILS
with `AttributeError: 'Propagation' object has no attribute
'own_cause_keywords'`. The other two pass vacuously (empty loops over
nothing, since the first `for k in ...` never runs) — they become real in
Step 4.

- [ ] **Step 3: Add the two dataclass fields**

In `src/kubeagent_verdict/dataset/propagation.py`, add to `Victim` among the
defaulted fields (after `objects`, at the end of the class):

```python
    # The two words that tell THIS victim's own cause apart from the other
    # causes on its menu -- job 2's grading list when a shared-origin row
    # renders the HEALTHY world, where the local cause is the answer.
    # Chosen by reading the cause strings, never by checking what they do
    # to a score (2026-09-23 exam-grader-fix design, section 4).
    # Empty on every training victim: nothing grades the training pool by
    # keyword, so curating 163 more pairs would buy no measurement.
    own_cause_keywords: tuple[str, ...] = ()
```

and to `Propagation`, after `healthy_origin_fresh`:

```python
    # The two words that tell the SHARED cause apart from the other causes
    # on every victim's menu -- job 2's grading list when a shared-origin
    # row renders the BROKEN world, where the shared cause is the answer.
    # Same curation rule, and empty on every training scenario for the same
    # reason as Victim's.
    own_cause_keywords: tuple[str, ...] = ()
```

- [ ] **Step 4: Add the 22 values**

Place each pair from the table above into its literal in
`propagation.py`'s `_SCENARIOS` (the EVAL-ONLY six). Use `local_cause` to
identify each victim — victim order in the table is declaration order.

Do not touch `trainable_scenarios()`'s pool. Verify the split afterwards:

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from kubeagent_verdict.dataset import propagation as prop
ev = sum(1 for p in prop.all_scenarios() if p.own_cause_keywords) \
   + sum(1 for p in prop.all_scenarios() for v in p.victims if v.own_cause_keywords)
tr = sum(1 for p in prop.trainable_scenarios() if p.own_cause_keywords) \
   + sum(1 for p in prop.trainable_scenarios() for v in p.victims if v.own_cause_keywords)
print("eval pairs:", ev, "| training pairs:", tr)
PY
```

Expected: `eval pairs: 22 | training pairs: 0`. Anything else, STOP and report.

- [ ] **Step 5: Run the keyword tests — all three must pass**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_keywords.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Write the failing exam-oracle job-2 test**

Spec Testing item 2: "the test whose absence hid the bug." Add to
`tests/test_oracle.py`, directly after `test_exam_oracle_job3_is_perfect`
(:214):

```python
def test_exam_oracle_job2_is_perfect():
    """The exam's own job2, oracle-read: a model that answers each row with
    that row's gold content must score every job-2 workload.

    This is the gate whose absence hid the defect. job1 and job3 have had an
    exam oracle since the rescope; job 2 -- the one job with a broken ceiling
    -- was the one nobody pinned, and 20 of its 153 workloads scored 0.0
    against their own gold answer because their grading keywords were empty.
    A ceiling below 1.0 here means the corpus, not the model, is at fault.
    """
    _, results = _exam()
    board = score.scoreboard(list(results))
    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 153}
```

- [ ] **Step 7: Run it**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_oracle.py::test_exam_oracle_job2_is_perfect -v
```

Expected: FAILS, reporting a rate below 1.0 with `n == 153`. The keywords
exist now but nothing carries them into `meta` yet — that is Step 8.

Record the observed rate in the task report. Expected: `0.8693` (133 of
153). If it differs, note it but continue — the only value this plan pins
is 1.0 after Step 8.

- [ ] **Step 8: Carry the keywords through the renderer**

Two edits in `src/kubeagent_verdict/dataset/cases.py`.

First, `_shared_origin_row` (:758) decides cause, rationale AND keywords in
its one branch, so the three can never drift apart. Replace the function
with:

```python
def _shared_origin_row(result: rules.Result, *, healthy: bool, decoy: str,
                       shared_cause: str,
                       decoy_keywords: tuple[str, ...],
                       shared_keywords: tuple[str, ...],
                       ) -> tuple[str, str | None, list[str]]:
    """One victim's (cause, rationale, job-2 keywords) for a shared-origin row.

    A decided workload -- confirmed or unverified -- gets the rules' own
    cause and rationale, exactly as `multi` already does (spec section 3):
    a decided workload never disagrees with what the rules found, whatever
    world the row is rendered in. An undecided workload keeps today's
    answer, held fixed by `healthy` alone: the decoy in the healthy world,
    the shared cause in the broken one. The `None` rationale tells the
    caller to keep applying its own per-world template, since there is no
    rules evidence to build one from.

    The keyword list is decided in the SAME branch as the cause, which is
    the point of returning it from here rather than from a second `if
    healthy` at the call site: job 2 grades the reply against whichever
    string this function chose, so a branch that could pick one without the
    other is a branch that could grade an answer by another answer's words.
    A decided workload is job 1 and is graded by echo, not by keyword, so
    its list is empty.
    """
    if result.decided:
        return result.cause, _rule_rationale(result), []
    if healthy:
        return decoy, None, list(decoy_keywords)
    return shared_cause, None, list(shared_keywords)
```

Second, the call site and the defect site in `_render_shared_origin`
(:994-1016). Replace

```python
        row_cause, row_rationale = _shared_origin_row(
            result, healthy=healthy, decoy=decoy, shared_cause=shared_cause)
```

with

```python
        row_cause, row_rationale, row_keywords = _shared_origin_row(
            result, healthy=healthy, decoy=decoy, shared_cause=shared_cause,
            decoy_keywords=v.own_cause_keywords,
            shared_keywords=p.own_cause_keywords)
```

and replace the three-line comment plus `own_cause_keywords=[]` with

```python
        # The keywords come from the SAME branch that chose `row_cause`, so
        # job 2 grades this workload by the distinguishing words of the very
        # string that is its expected answer -- the victim's own pair in the
        # healthy world, the scenario's shared pair in the broken one. Empty
        # only on a decided workload, which is job 1 and graded by echo.
        workloads_meta[key] = render.workload_meta(
            result, expected_cause=row_cause, own_cause_keywords=row_keywords)
```

- [ ] **Step 9: Run the oracle test — it must pass now**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_oracle.py::test_exam_oracle_job2_is_perfect -v
```

Expected: PASS, `{"rate": 1.0, "n": 153}`.

If the rate is above 0.8693 but below 1.0, STOP and report which workloads
still score 0 — a residual means a shared-origin workload this plan did not
account for.

- [ ] **Step 10: Confirm the prompts did NOT move**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_exam_prompt_stability.py -v
```

Expected: 2 passed. **If this fails, STOP.** A moved prompt invalidates
Task 4 entirely and means the field change touched a rendered byte.

- [ ] **Step 11: Measure the meta footprint before re-pinning the digests**

The 2026-09-19 entries in `tests/test_shared_origin_training.py` were written
from a measured key-by-key diff. Match that practice:

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json, collections
from pathlib import Path
from kubeagent_verdict.dataset import generate
bank = [json.loads(l) for l in
        Path("out/dataset-0920/test.jsonl").read_text(encoding="utf-8").splitlines() if l]
fresh = [generate.to_row(e) for e in generate.test_set()]
moved_keys, moved_cases = collections.Counter(), collections.Counter()
for f, b in zip(fresh, bank):
    if f == b:
        continue
    moved_cases[f["meta"].get("case", "?")] += 1
    for k in set(f) | set(b):
        if f.get(k) != b.get(k):
            moved_keys[k] += 1
print("rows changed:", sum(moved_cases.values()), "of", len(fresh))
print("top-level keys that changed:", dict(moved_keys))
print("by case:", dict(moved_cases))
PY
```

Expected: `top-level keys that changed: {'meta': N}` and nothing else —
`messages` must NOT appear. Record the row count and the per-case breakdown;
they go into the comments in Step 12.

- [ ] **Step 12: Re-pin the two digests by hand**

Get the new values:

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import hashlib, json
from kubeagent_verdict.dataset import generate
def digest(rows):
    blob = json.dumps([generate.to_row(e) for e in rows], sort_keys=True,
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
print("FROZEN_253_SHA256 =", digest(generate.test_set()[:253]))
print("EVAL_SET_SHA256   =", digest(generate.test_set()))
PY
```

These are hashes — this plan cannot predict them, and that is the one place
where "compute it and write it in" is correct. What makes it safe is Step 10:
the prompts are pinned separately and did not move.

Append a fourth dated entry above `FROZEN_253_SHA256` (tests/test_shared_origin_training.py:797),
in the style of the three above it, then write the new value:

```python
# It moved a fourth time, on 2026-09-23, for the exam-grader fix
# (2026-09-23-exam-grader-fix-design.md, sections 2 and 5). Every
# UNDECIDED shared-origin workload's `meta.own_cause_keywords` goes from
# `[]` to a curated two-word pair -- the victim's own in the healthy world,
# the scenario's shared pair in the broken one. A DECIDED one still carries
# `[]`, because it is job 1 and graded by echo. Inside this slice that is
# the four `shared_origin_probe` workloads that scored 0.0 against their own
# gold answer; the other sixteen live in the ten rows outside it, and
# `EVAL_SET_SHA256` below moves for them. `_digest` hashes
# `generate.to_row`, which carries `meta`, so the digest moves although not
# one RENDERED byte does. That is pinned separately and independently:
# `tests/test_exam_prompt_stability.py` compares the regenerated exam's
# `messages` -- system, user and gold answer -- against the banked
# `out/dataset-0920/test.jsonl` row for row, and a key-by-key diff of the
# exam before and after this fix reports `meta` as the only top-level key
# that changed. That is what makes this a meta-only move and not a new exam.
```

Append the matching entry above `EVAL_SET_SHA256` (:850):

```python
# Re-pinned a fourth time on 2026-09-23, in the same commit and for the
# same exam-grader fix that moved `FROZEN_253_SHA256` above (see its
# 2026-09-23 entry). This digest covers the frozen slice AND the ten
# `shared_origin_decoy_probe` rows outside it, so it carries that entry's
# four workloads plus the sixteen in those ten rows -- the twenty that
# scored 0.0 against their own gold answer before this fix. Same meta-only
# reason, and no `messages` byte moves in either slice.
```

- [ ] **Step 13: Re-pin the paste-the-prompt-bot values by hand**

In `tests/test_score.py`, replace the four assertions at :1919-1923 and
extend the docstring. The expected values are derived, not observed — the
bot pastes the whole prompt as every cause, so its hit count *equals*
`keyword_derivable_n`, and all 20 newly-graded workloads have their cause
printed in their own candidate menu:

```python
def test_paste_the_prompt_bot_measures_the_job2_keyword_ceiling():
    """A bot that reads nothing still clears the job-2 workloads whose
    answer keywords the prompt already prints.

    The scoreboard's footnote counts that exposure from the corpus alone:
    76 of the 134 keyword-graded job-2 workloads have every required
    keyword in their own prompt. This bot converts that footnote into a
    score, so the exposure is a measurement rather than an estimate.

    Re-pinned on 2026-09-23 for the exam-grader fix
    (2026-09-23-exam-grader-fix-design.md). Twenty shared-origin job-2
    workloads carried no keywords and so scored 0.0 whatever the reply
    said; they are graded now. 114 + 20 = 134 graded, and every one of the
    20 has its answer printed in its own candidate menu, so 56 + 20 = 76
    derivable and the bot rises from 0.366 to 76/153 = 0.4967.

    The last assertion is the one that matters and it is why no bar moves.
    The bot still scores below JOB2_BAR, but the margin narrows from 0.334
    to 0.203 -- so any future proposal to lower that bar now has a hard
    floor of 0.50, not 0.37. Below 0.50, a bot that reads nothing passes.
    """
    rows = _corpus_rows()
    results = score.evaluate(rows, _paste_the_prompt_bot(rows))
    board = score.scoreboard(results)

    assert board["overall"]["keyword_derivable_n"] == 76
    assert board["overall"]["keyword_graded_n"] == 134
    assert board["jobs"]["job2"]["n"] == 153
    assert board["jobs"]["job2"]["rate"] == pytest.approx(0.497, abs=0.005)
    assert board["jobs"]["job2"]["rate"] < score.JOB2_BAR
```

**If any measured value differs from 76, 134, 153 or ~0.497, STOP and report
it.** Do not paste the observed value in.

- [ ] **Step 14: Full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -20 && .venv/bin/ruff check . 2>&1 | tail -3
```

Expected: 798 passed (794 + 3 keyword tests + 1 oracle test), 78 `EXE002`.

Other tests may fail here if they assert on shared-origin `meta`. Each such
failure is a pin that moved for the same meta-only reason — fix it by hand
with a dated comment referencing this design, and report every one you
touched in the task report. Do not use `-update`.

- [ ] **Step 15: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s \
  src/kubeagent_verdict/dataset/propagation.py \
  src/kubeagent_verdict/dataset/cases.py \
  tests/test_shared_origin_keywords.py \
  tests/test_oracle.py \
  tests/test_shared_origin_training.py \
  tests/test_score.py \
  -m "fix(exam): grade the 20 shared-origin job-2 workloads that scored zero

A shared-origin row passed own_cause_keywords=[] for every undecided
workload, so job 2 returned 0.0 for 20 of the exam's 153 whatever the model
answered. Twenty-two curated pairs -- 16 victims and 6 shared causes -- now
ride on propagation.Victim and propagation.Propagation, and
_shared_origin_row picks the cause and its keywords in one branch so the two
cannot grade each other's answer.

Each pair is two words that tell its cause apart from the others on the same
menu, chosen by reading the strings and never by checking a score. A perfect
model now scores 1.000 on job 2; test_exam_oracle_job2_is_perfect is the gate
whose absence hid this.

Six pinned values re-written by hand: both dataset digests move on meta alone
(the prompts are pinned separately and byte-identical), keyword_graded_n
114->134, keyword_derivable_n 56->76, and the paste-the-prompt bot 0.366->0.497.
No bar moved."
```

---

## Task 3: The grader refuses what it cannot grade

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py` (near `JOB2_BAR`:139, `job2`:158, `evaluate`:438, the job-2 loop :561, the exposure call :547)
- Modify: `tests/test_oracle.py:51, :56` (train/val helpers)
- Modify: `tests/test_score.py` (new refusal tests)

**Interfaces:**
- Produces: `score.UngradableWorkload(ValueError)`.
- Produces: `score.job2(meta_workload, reply_row, own_cause_keywords, *, workload="")`
  — a new keyword-only parameter, defaulted, so existing calls keep working.
- Produces: `score.evaluate(rows, chat_fn, *, grade_job2=True)`.

- [ ] **Step 1: Write the failing refusal tests**

Add to `tests/test_score.py`, in the `evaluate(): validation` section
(around :741):

```python
def test_job2_refuses_a_named_cause_workload_with_no_keywords():
    """Spec section 1: a job-2 workload whose expected cause is a named
    cause and whose keyword list is empty cannot be graded, and saying so
    is the point. Returning 0.0 there is a claim the model got it wrong.
    """
    wm = {"job": 2, "expected_cause": "the registry is unreachable",
          "decided_cause": "", "own_cause_keywords": []}
    with pytest.raises(score.UngradableWorkload) as exc:
        score.job2(wm, {"cause": "anything"}, [], workload="prod/api")
    assert "prod/api" in str(exc.value)
    assert "the registry is unreachable" in str(exc.value)


def test_job2_refuses_before_it_looks_at_the_reply():
    """The refusal is about the CORPUS, not the reply. A missing reply
    returns 0.0 on every other path, and letting that short-circuit run
    first would hide the defect on exactly the workloads a model said
    nothing about.
    """
    wm = {"job": 2, "expected_cause": "the registry is unreachable",
          "decided_cause": "", "own_cause_keywords": []}
    with pytest.raises(score.UngradableWorkload):
        score.job2(wm, None, [], workload="prod/api")


def test_job2_does_not_refuse_a_none_of_these_workload():
    """`none_of_these` is graded by exact match against that one string and
    needs no keywords. The refusal is narrow on purpose.
    """
    wm = {"job": 2, "expected_cause": score.NONE_OF_THESE,
          "decided_cause": "", "own_cause_keywords": []}
    assert score.job2(wm, {"cause": score.NONE_OF_THESE}, []) == 1.0


def test_job2_does_not_refuse_a_job1_workload():
    wm = {"job": 1, "expected_cause": "the registry is unreachable",
          "decided_cause": "the registry is unreachable",
          "own_cause_keywords": []}
    assert score.job2(wm, {"cause": "whatever"}, []) == 0.0


def test_evaluate_refuses_an_ungradable_corpus_before_any_model_call():
    """The validation pre-pass's own contract: a fixture bug must never
    spend a chat_fn call finding that out.
    """
    row = _row_with_job2_workload(keywords=[])   # see helper below
    calls = []
    with pytest.raises(score.UngradableWorkload):
        score.evaluate([row], lambda messages: calls.append(messages) or "{}")
    assert calls == []


def test_evaluate_scores_no_job2_when_told_it_is_not_grading_job2():
    """`grade_job2=False` is for a corpus that is not being graded on job 2
    -- the oracle's train/val dataset self-check. It suppresses the refusal,
    the job-2 scores AND the keyword exposure counts together, because a
    board reporting an exposure under a job-2 rate of n=0 reads as a
    measurement and is not one.
    """
    row = _row_with_job2_workload(keywords=[])
    results = score.evaluate([row], lambda messages: "{}", grade_job2=False)
    board = score.scoreboard(results)
    assert board["jobs"]["job2"] == {"rate": None, "n": 0}
    assert board["overall"]["keyword_graded_n"] == 0
    assert board["overall"]["keyword_derivable_n"] == 0
```

Write `_row_with_job2_workload(keywords)` beside them, modelled on the
existing hand-built `ROW` fixture in that module: one workload, `job == 2`,
`expected_cause` a named cause, `own_cause_keywords` as given, a valid
`messages` triple and a `meta` carrying `label`, `workloads` and
`decoy_by_workload`. Read the existing `ROW` first and follow its shape.

- [ ] **Step 2: Run them — every one must fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_score.py -k "refuse or grade_job2" -v
```

Expected: `AttributeError: module ... has no attribute 'UngradableWorkload'`
on the ones that reference it; the `grade_job2` ones fail on an unexpected
keyword argument.

- [ ] **Step 3: Add the exception and the check**

In `src/kubeagent_verdict/evals/score.py`, directly after `JOB2_BAR = 0.7`
(:139):

```python
class UngradableWorkload(ValueError):
    """A job-2 workload the grader cannot grade, raised instead of scored.

    An undecided workload whose expected cause is a named cause is graded by
    keyword containment. With an empty keyword list there is no reply that
    could score 1.0, so a returned 0.0 is not a measurement of the model --
    it is the corpus saying nothing and the scoreboard printing it as a
    miss. Twenty of the exam's 153 job-2 workloads were in exactly that
    state, and job 2 was the one job with no exam oracle to notice.
    """


def _require_job2_gradable(workload: str, meta_workload: dict,
                           own_cause_keywords: list[str]) -> None:
    """Raise `UngradableWorkload` for a job-2 workload with a named expected
    cause and no keywords. Narrow on purpose: job 2 only, named cause only,
    empty list only.

    A `none_of_these` workload is graded by exact match against that one
    string and needs no keywords. A job-1 workload is graded by echo. A
    workload whose meta carries no `job` at all -- a hand-built fixture --
    is not this function's business.
    """
    if meta_workload.get("job") != 2:
        return
    expected = meta_workload.get("expected_cause")
    if expected == NONE_OF_THESE:
        return
    if own_cause_keywords:
        return
    raise UngradableWorkload(
        f"workload {workload!r}: job 2 expects the named cause {expected!r} "
        f"but carries no own_cause_keywords, so no reply could score 1.0. "
        f"This is a corpus defect, not a model failure.")
```

- [ ] **Step 4: Make `job2` refuse first**

Change `job2`'s signature and put the check at the very top, before the
`reply_row is None` short-circuit:

```python
def job2(meta_workload: dict, reply_row: dict | None,
         own_cause_keywords: list[str], *, workload: str = "") -> float:
    """Score one undecided ("job 2") workload. 1.0 when the reply names the
    story's own cause -- all of `own_cause_keywords` appear in the reply's
    cause, matched as substrings after lowercasing both sides -- or, on a
    `none_of_these` workload, when the reply's cause is exactly that. 0.0
    otherwise, including a missing row or reply.

    Raises `UngradableWorkload` for a named-cause workload with no keywords,
    BEFORE looking at the reply: that is a statement about the corpus, and a
    missing reply must not short-circuit past it.
    """
    _require_job2_gradable(workload, meta_workload, own_cause_keywords)
    if reply_row is None:
        return 0.0
    got_cause = str(reply_row.get("cause", "")).strip().lower()
    if meta_workload.get("expected_cause") == NONE_OF_THESE:
        return 1.0 if got_cause == NONE_OF_THESE else 0.0
    if not _is_job2_keyword_graded(meta_workload, own_cause_keywords):
        return 0.0
    return 1.0 if all(str(k).lower() in got_cause for k in own_cause_keywords) else 0.0
```

Leave the `_is_job2_keyword_graded` branch in place. It is still reachable
for a workload whose meta carries no `job` key, and `_keyword_exposure`
calls the same predicate — the two must keep sharing one definition.

- [ ] **Step 5: Add `grade_job2` to `evaluate`**

Signature (:438):

```python
def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict]:
    """...

    `grade_job2=False` says this corpus is not being graded on job 2. It
    suppresses the refusal, the per-workload job-2 scores and the keyword
    exposure counts -- all three, because they are one diagnostic and a
    board that printed an exposure beside a job-2 rate of n=0 would read as
    a measurement it is not.

    The exam path never passes it. Its one caller is the oracle's train/val
    dataset self-check, where 4,823 train and 589 val job-2 workloads carry
    a named cause and no keywords: nothing grades the training pool by
    keyword, and `tests/test_oracle.py`'s `_job2_gate` already scores job 2
    over its own population. Curating 217 more pairs to satisfy a grader
    that never reads them is the cost this parameter exists to avoid.
    """
```

Pre-pass — add the refusal inside the existing per-workload loop:

```python
    for row in rows:
        meta = row["meta"]
        _ = meta["label"]
        for name, wm in meta["workloads"].items():
            _ = wm["job"]
            _ = wm["decided_cause"]
            if grade_job2:
                _require_job2_gradable(name, wm, wm.get("own_cause_keywords") or [])
```

Exposure call (:547):

```python
        keyword_derivable_n, keyword_graded_n = (
            _keyword_exposure(meta, prompt) if grade_job2 else (0, 0))
```

Job-2 loop (:561):

```python
        job2_scores = ([job2(wm, by_workload.get(w), wm.get("own_cause_keywords") or [],
                             workload=w)
                        for w, wm in workloads.items() if wm.get("job") == 2]
                       if grade_job2 else [])
```

- [ ] **Step 6: Run the refusal tests**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_score.py -k "refuse or grade_job2" -v
```

Expected: 6 passed.

- [ ] **Step 7: Exempt the oracle's train/val self-check**

`tests/test_oracle.py`'s `_gold_results` (:39) serves train, val AND the
exam, so the switch goes on the helper, not inside it. Change its signature
and the two callers:

```python
def _gold_results(examples: list, *, grade_job2: bool = True) -> list[dict]:
    """`score.evaluate`, fed each row's OWN gold assistant content as the
    model's reply -- the oracle read, byte for byte. `evaluate` calls
    `chat_fn` once per row, in order, so a plain iterator over the same
    rows' gold content lines up with no row identity lookup needed.

    `grade_job2=False` for the train and val pools, and only there. Nothing
    grades the training pool by keyword: 4,823 train and 589 val job-2
    workloads carry a named expected cause and no keywords, and
    `score.evaluate` refuses such a corpus rather than scoring it zero.
    Job 2 on those pools is measured by `_job2_gate` below, over the
    population spec section 10 gate 1 defines. The exam passes nothing and
    is graded in full -- see `test_exam_oracle_job2_is_perfect`.
    """
    rows = [generate.to_row(e) for e in examples]
    gold = iter(r["messages"][2]["content"] for r in rows)
    return score.evaluate(rows, lambda _messages: next(gold),
                          grade_job2=grade_job2)


@functools.lru_cache(maxsize=1)
def _train_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[0], grade_job2=False))


@functools.lru_cache(maxsize=1)
def _val_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[1], grade_job2=False))
```

`_exam()` (:61) is untouched — it must keep grading job 2 in full.

- [ ] **Step 8: Full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -20 && .venv/bin/ruff check . 2>&1 | tail -3
```

Expected: 804 passed (798 + 6), 78 `EXE002`.

Hand-built fixtures elsewhere may now raise. A fixture that declares a job-2
workload with a named expected cause and no keywords is a fixture that was
asserting on an ungradable workload — give it a keyword pair that appears in
its own expected cause. Do not reach for `grade_job2=False` to silence a
fixture; that parameter is for corpora, not for tests that find the refusal
inconvenient. Report every fixture you touched.

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s \
  src/kubeagent_verdict/evals/score.py \
  tests/test_score.py \
  tests/test_oracle.py \
  -m "fix(score): refuse a job-2 workload with no keywords instead of scoring it zero

An undecided workload whose expected cause is a named cause is graded by
keyword containment. With an empty list no reply can score 1.0, so the
returned 0.0 was the corpus saying nothing and the scoreboard printing it as
a model miss. job2 now raises UngradableWorkload naming the workload, before
it looks at the reply -- the refusal is about the corpus, and a missing reply
must not short-circuit past it. evaluate's validation pre-pass raises the
same way, so no inference is spent discovering a fixture bug.

evaluate gains grade_job2, default True. The exam path never passes it. The
oracle's train/val dataset self-check does: 4,823 train and 589 val job-2
workloads carry a named cause and no keywords, nothing grades the training
pool by keyword, and _job2_gate already scores job 2 there over its own
population. It suppresses the refusal, the job-2 scores and the keyword
exposure counts together, so a board can never print an exposure beside a
job-2 rate of n=0."
```

---

## Task 4: Re-score the banked replies

Spec section 7. `out/eval-0920/results.jsonl` stores every reply verbatim;
re-score those bytes against the fixed meta. No inference, no endpoint, no
cost.

**Files:**
- Modify: `src/kubeagent_verdict/evals/cli.py` (`main`:179)
- Modify or create the CLI test module (check for an existing
  `tests/test_eval_cli.py` first and follow it; create it only if absent)

**Interfaces:**
- Consumes: `score.evaluate(rows, chat_fn)` — Task 3's signature, with
  `grade_job2` left at its default.
- Produces: `kv-eval --test <file> --replay <prior run dir> --out <dir>`.

- [ ] **Step 1: Write the failing CLI tests**

```python
def test_replay_refuses_a_model(capsys):
    """A replay calls nothing. Accepting --model would write a scoreboard
    naming a model that produced none of its replies.
    """
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior),
                  "--out", str(out), "--model", "some.gguf"])


def test_replay_refuses_a_limit():
    """`evaluate` calls chat_fn once per row in order, so a replay lines up
    by position. --limit drops rows and breaks that alignment silently.
    """
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--replay", str(prior),
                  "--out", str(out), "--limit", "10"])


def test_model_is_still_required_without_replay():
    with pytest.raises(SystemExit):
        _run_cli(["--test", str(test_file), "--out", str(out)])


def test_replay_refuses_a_prior_run_of_a_different_length():
    """Positional alignment is the whole contract. A length mismatch means
    the stored replies answered a different set of rows.
    """
    ...  # build a prior results.jsonl with one row fewer
    with pytest.raises(SystemExit):
        _run_cli([...])


def test_replay_records_where_the_replies_came_from():
    """`rescored_from` names the run, reduced the same way `provenance`
    reduces `model`: a basename, because --replay /home/<user>/... is
    accepted and /home/ is one of the five leak shapes the provenance
    denylist exists to catch. The model and endpoint are carried forward
    from the replayed run's own scoreboard -- that is who produced these
    replies, and inventing anything else would be a false provenance.
    """
    board = json.loads((out / "scoreboard.json").read_text())
    assert board["run"]["rescored_from"] == "eval-0920-fixture"
    assert board["run"]["model"] == "kubeagent-verdict-0.6b-q8_0.gguf"
```

Build small fixtures under `tmp_path` — a two-row test file and a matching
prior run directory holding `results.jsonl` and `scoreboard.json`. Do not
reach for the real `out/eval-0920`; a test that needs gitignored working
data is a test that skips on CI.

- [ ] **Step 2: Run them — all must fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -k replay -v
```

Expected: `unrecognized arguments: --replay`.

- [ ] **Step 3: Implement `--replay`**

In `cli.py`'s `main` (:179):

```python
    p.add_argument("--model")
    p.add_argument("--replay", type=Path,
                   help="a prior run's output directory. Re-score the replies "
                        "it stored instead of calling a model.")
```

(`--model` loses `required=True`; argparse cannot express "required unless
`--replay`", so the rule moves into `RunE`-style validation below, where the
error wording stays ours.)

After `args = p.parse_args()`:

```python
    if args.replay:
        if args.model:
            p.error("--replay re-scores stored replies and calls no model; "
                    "--model would name a model that produced none of them")
        if args.limit:
            p.error("--replay lines its stored replies up with the test rows "
                    "by position; --limit drops rows and breaks that")
    elif not args.model:
        p.error("--model is required")
```

Then a loader beside `provenance`:

```python
def replay_chat_fn(run_dir: Path, rows: list[dict]):
    """Stored replies from a prior run, as a `chat_fn`.

    `evaluate` calls `chat_fn` once per row, in order, so the stored
    `output` strings line up by position with no row identity lookup --
    the same alignment `tests/test_oracle.py`'s `_gold_results` relies on.
    Two guards keep that from being a hope: the counts must match, and each
    stored result's `case` must match its row's. Neither is a full identity
    check and neither pretends to be; together they refuse the mistake that
    actually happens, which is replaying one run's replies over another
    run's rows.

    Returns (chat_fn, prior_board). The board is the replayed run's own
    `scoreboard.json` -- its `run.model` and `run.endpoint` are carried into
    the new board, because that is who produced these replies.
    """
```

Raise `SystemExit` (via `p.error`, or a `ValueError` the caller converts)
with a message naming the file when `results.jsonl` or `scoreboard.json` is
missing, when the counts differ, or when a `case` mismatches at index *i*.
A replay with no scoreboard beside it has no provenance, and inventing one
is worse than refusing.

Then in `main`:

```python
    if args.replay:
        chat_fn, prior = replay_chat_fn(args.replay, rows)
        model = prior["run"]["model"]
        endpoint = prior["run"]["endpoint"]
    else:
        chat_fn = lambda messages: client.chat(args.endpoint, args.model, messages)
        model, endpoint = args.model, args.endpoint

    results = score.evaluate(rows, chat_fn)
    board = score.scoreboard(results)
    board["run"] = provenance(model, endpoint, args.test, len(rows), available,
                              dataset=dataset_provenance(args.test))
    if args.replay:
        board["run"]["rescored_from"] = PurePosixPath(args.replay).name
```

`provenance` itself is unchanged and stays pure.

The smoke block at the end of `main` reads local contract fixtures and makes
no model call, so it runs on a replay unchanged.

- [ ] **Step 4: Run the CLI tests**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -k replay -v
```

Expected: all pass.

- [ ] **Step 5: Full suite and ruff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -10 && .venv/bin/ruff check . 2>&1 | tail -3
```

Expected: 809 passed (804 + 5), 78 `EXE002`.

- [ ] **Step 6: Commit the CLI change**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s \
  src/kubeagent_verdict/evals/cli.py \
  tests/test_eval_cli.py \
  -m "feat(kv-eval): --replay re-scores a prior run's stored replies

results.jsonl already stores every reply verbatim, so a grader fix can be
applied to a finished run without paying for inference again. --replay takes
the prior run's directory, lines its stored outputs up with the test rows by
position -- guarded on both the count and each row's case -- and carries the
replayed run's own model and endpoint into the new board, because that is who
produced the replies. rescored_from names the run, reduced to a basename the
same way provenance reduces --model.

--model and --limit are refused with --replay rather than ignored: one would
name a model that answered nothing, the other would drop rows and break the
positional alignment silently."
```

- [ ] **Step 7: Run the actual re-score**

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m kubeagent_verdict.evals.cli \
  --test out/dataset-0920/test.jsonl \
  --replay out/eval-0920 \
  --out out/eval-0920-rescored
```

(Use the module path only if `kv-eval` is not on the venv's PATH; check
`.venv/bin/kv-eval` first.)

Expected job 2: **about 0.680** (104 of 153), up from 0.5817. Job 1 and
job 3 must be **unchanged** — this fix touches neither. If either moves,
STOP and report: the re-score was supposed to change one job's grading and
nothing else.

`out/` is gitignored, so there is nothing to commit here. Record the before
and after board in the task report.

- [ ] **Step 8: Report the four numbers**

In the task report, state plainly: job 1 before/after, job 2 before/after,
job 3 before/after, and whether each bar is cleared. Expected: job 2 rises
to about 0.680 against a 0.70 bar and **still misses by about 4 workloads**.
That is spec section "What this does not fix", not a failure of this plan.

---

## Self-Review

**Spec coverage.** Section 1 → Task 3 (with Ruling 2). Section 2 → Task 2
Steps 3-4. Section 3 → the 22-pair table and Task 2 Step 1's discrimination
test. Section 4 → Global Constraints and the discrimination test. Section 5
→ Task 2 Step 8. Section 6 → Task 1. Section 7 → Task 4. "The pins that
move" → Task 2 Steps 12-13, extended by Ruling 1 from four pins to six.
Testing items 1-6 → Task 3 Step 1, Task 2 Step 6, Task 2 Step 1, Task 1
Step 2, Task 2 Step 1, Task 2 Steps 12-13.

**Additions beyond the spec, and why.** (a) Self-containment
(`test_every_eval_keyword_appears_in_its_own_cause`): a typo'd keyword makes
a workload unanswerable, which is the defect being fixed re-introduced one
layer up. (b) The discrimination test covers the distractor and sibling
victims, not only the twin: spec section 3's rule is menu-wide and Testing
item 3 states its narrowest form. (c) `grade_job2` suppresses the keyword
exposure counts as well as the job-2 scores, so a board cannot print an
exposure beside `n: 0`. (d) `--replay` refuses `--limit` and checks
positional alignment, which section 7 does not specify but which its
"re-score those bytes" claim requires.

**Out of scope, deliberately.** Job 1's ceiling (0.879 against a 0.90 bar).
The generator fix for `wrong_attribution`. Both have their own spec. Nothing
in this plan moves a bar, retrains, or touches the training pool.
