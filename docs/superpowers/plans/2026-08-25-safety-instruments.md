# Safety Instruments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock in the 0/253 contamination result with four machine-checked guards, and add the one metric that makes the model's weakest axis fail in both directions.

**Architecture:** Five new or extended test modules plus two small production edits. Four guards (contamination lock, `ast` structure guard, evidence-duplication guard, pinned slice counts) run against the in-process `Example` objects the generator produces — never against JSONL, because `Example.group` is not serialized. One new scored axis (`false_shared_rate`) threads a new meta field from `dataset/cases.py` through `evals/score.py` without breaking `score.py`'s import boundary: it keeps importing only `contract` and `evals.contract_check`, never `dataset`.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), pytest, stdlib only (`ast`, `hashlib`, `collections`, `re`). `pyproject.toml` declares `dependencies = []` and this slice adds none.

**Spec:** [docs/superpowers/specs/2026-08-25-safety-instruments-design.md](../specs/2026-08-25-safety-instruments-design.md)

## Global Constraints

- Branch `safety-instruments`, already cut off `main` @ `7bc8ac8`. **Never commit to `main`.**
- Every commit `git commit -s` (DCO). Identity `imantaba <itn.taba@gmail.com>`.
- **No AI attribution of any kind, anywhere** — no `Co-Authored-By`, no "generated with", not in commits, code, comments, or docs.
- Python is `.venv/bin/python` (3.12). The system `python3` is 3.14 and **must not be used**.
- Tests run with `.venv/bin/pytest`. The eval CLI is the console script `.venv/bin/kv-eval` — `python -m kubeagent_verdict.evals.cli` is a **silent no-op** and must never be used.
- **Stdlib only.** Do not add a dependency, do not touch `pyproject.toml`'s `dependencies`.
- `ruff` line length **100**, target **py311**. Run `.venv/bin/ruff check .` before every commit.
- **Never run `kv-train`, `kv-export`, or anything that writes `dist/`.**
- **Never run a test with `-update`.**
- No live identifiers, secrets, private IPs, or internal hostnames in any tracked file.
- The release configuration is **`--seed 17 --size 5500`**. Every pinned number in this plan was measured at exactly that configuration.
- Standing rule for the whole slice: **an eval change that could not fail the model it replaced is not a fix.**

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `tests/test_generate.py` | modify | Gains the pinned slice-count table and the builder-raise test; its banned set gains `shared_origin_probe` (Task 1) |
| `src/kubeagent_verdict/dataset/cases.py` | modify | `multi_misattribution_probe` gains a distinctness `raise` (Task 1) and the `shared_claim_phrases` meta field (Task 5) |
| `src/kubeagent_verdict/dataset/generate.py` | modify | `probe_sets()` loses the silent `continue` (Task 1). Nothing else changes. |
| `tests/test_contamination.py` | **create** | Instrument 1 — the contamination lock, two assertions (Task 2) |
| `tests/test_generator_structure.py` | **create** | Instrument 2 — the `ast` guard over `generate.py` (Task 3) |
| `tests/test_evidence_overlap.py` | **create** | Instrument 3 — per-read identity-masked duplication guard + declared allowlist (Task 4) |
| `src/kubeagent_verdict/evals/score.py` | modify | `false_shared_rate`: module constant, two per-row fields, one aggregate rate, one column, one prose line (Task 5) |
| `tests/test_score.py` | modify | Five unit cases for the three-way resolution (Task 5) |
| `docs/runbooks/train.md` | modify | The fifth release decider (Task 6) |
| `docs/model-card.md` | modify | The measured v0.1.0 baseline (Task 7) |

## A note on testing style for this slice

**Instruments 1–4 are not ordinary TDD and must not be reported as if they were.** They guard a tree that is *already correct*: contamination is already 0, the eval-only builders are already absent from the training mix, and the slice counts are already right. Written against today's tree, every one passes on its first run.

**A guard that has only ever been observed passing is not known to be a guard.** So each of Tasks 1–4 carries a **demonstrated failure**: perturb the thing it guards, observe the *named* failure, revert the perturbation, confirm green. The perturbation is throwaway and never committed — only the observation is, in the commit message.

Task 5 (`false_shared_rate`) is the one piece that *is* ordinary failing-first TDD: the code does not exist yet, so its tests fail first for the ordinary reason.

---

### Task 1: Pin the denominators, and make a lost row loud

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py:353-356` (add a third guard to `multi_misattribution_probe`)
- Modify: `src/kubeagent_verdict/dataset/generate.py:242-247` (delete the silent `continue`)
- Test: `tests/test_generate.py` (add two tests; modify the banned set at `109-110`; add one import)

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the first task).
- Produces: `cases.multi_misattribution_probe` raises `ValueError` containing the words `distinct workloads` when two pairs carry the same `(ns, name)`. Tasks 2–4 depend on the test set being exactly **253** rows with the slice counts pinned here.

**Why first:** every later number in this slice — the contamination lock's per-slice zeroes, the duplication guard's `47 / 50`, the release bar's `≤ 1 of 19` — is divided by a denominator that nothing currently pins. `generate.py:244-245` can silently drop a `multi_misattribution_probe` row, turning "≤1 of 19" into "≤1 of 18" with the whole suite green.

- [ ] **Step 1: Write the failing test for the pinned slice counts**

Add to `tests/test_generate.py`. Also add `import collections` to the file's imports (it currently imports only `json` and `re`); keep imports alphabetically ordered — `collections`, `json`, `re`.

```python
def test_test_set_slice_counts_are_pinned():
    """Every probe rate's denominator, pinned.

    `multi_misattribution_probe` had 19 rows and nothing said so, while its
    caller silently skipped a row on a name collision. A slice that quietly
    shrinks turns a "<=1 of 19" release bar into "<=1 of 18" with the suite
    green. The literals `253` and `19` appeared nowhere in `tests/` before
    this test existed.
    """
    counts = collections.Counter(ex.case for ex in generate.test_set())
    assert dict(counts) == {
        "attributed": 53,
        "contradiction_probe": 19,
        "empty_candidates": 19,
        "injection": 19,
        "misattribution_probe": 19,
        "multi_misattribution_probe": 19,
        "none_of_these": 19,
        "own_cause": 19,
        "positional_probe": 19,
        "shared_origin_probe": 10,
        "truncated": 19,
        "wrong_attribution": 19,
    }
    assert sum(counts.values()) == 253
```

- [ ] **Step 2: Run it — it should PASS on today's tree**

Run: `.venv/bin/pytest tests/test_generate.py::test_test_set_slice_counts_are_pinned -v`
Expected: **PASS**. This is a guard over an already-correct tree, not failing-first TDD. If it FAILS, stop and report the actual counts — the tree has drifted from the measurement and the plan's numbers need re-deriving before anything else proceeds.

- [ ] **Step 3: Write the failing test for the builder's distinctness guard**

Add to `tests/test_generate.py`. `pytest` is a declared dev dependency and `pytest.raises` is already used in `tests/test_contract.py` and `tests/test_knownissues.py`, so this style matches the repo.

```python
def test_multi_probe_builder_rejects_colliding_workloads():
    """A name collision must raise, not silently drop the row.

    Two pairs with the same (ns, name) render one merged answer row instead
    of two, so the example silently stops testing what it was built to test.
    The check lives in the builder, so every caller gets it — including any
    future one that does not know to look.
    """
    import random

    import pytest

    from kubeagent_verdict.dataset import catalog, cases, names

    entry = next(e for e in catalog.trainable() if e.losers)
    n = names.draw(random.Random(0))
    with pytest.raises(ValueError, match="distinct workloads"):
        cases.multi_misattribution_probe([(entry, n), (entry, n)], random.Random(0))
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_generate.py::test_multi_probe_builder_rejects_colliding_workloads -v`
Expected: **FAIL** — `DID NOT RAISE <class 'ValueError'>`. The builder currently accepts colliding pairs.

- [ ] **Step 5: Add the guard to the builder**

In `src/kubeagent_verdict/dataset/cases.py`, inside `multi_misattribution_probe`, directly after the existing `if not all(e.losers for e, _n in pairs):` guard (currently ending at line 356):

```python
    # A collision merges the two answer rows, so the example silently stops
    # being a multi-workload probe. The caller used to skip such a pair,
    # which shrank the slice and every rate divided by it. Raising here
    # gives every caller the check, including future ones.
    seen = [(n.ns, n.name) for _e, n in pairs]
    if len(set(seen)) != len(seen):
        raise ValueError(
            f"multi_misattribution_probe needs distinct workloads: {sorted(seen)}")
```

- [ ] **Step 6: Run it to verify it passes**

Run: `.venv/bin/pytest tests/test_generate.py::test_multi_probe_builder_rejects_colliding_workloads -v`
Expected: **PASS**

- [ ] **Step 7: Delete the caller's silent skip**

In `src/kubeagent_verdict/dataset/generate.py`, in `probe_sets()`, replace these lines (currently `242-247`):

```python
        first = names.draw(_entry_rng("multi-probe-a", entry.key))
        second = names.draw(_entry_rng("multi-probe-b", entry.key, other.key))
        if (first.ns, first.name) == (second.ns, second.name):
            continue  # a name collision would merge the two answer rows
        out.append(cases.multi_misattribution_probe(
            [(entry, first), (other, second)], _entry_rng("multi-probe", entry.key)))
```

with:

```python
        first = names.draw(_entry_rng("multi-probe-a", entry.key))
        second = names.draw(_entry_rng("multi-probe-b", entry.key, other.key))
        # A collision used to `continue` here, which silently shrank the slice
        # and the denominator every rate on it is divided by. The builder now
        # raises instead, so a collision is a named failure rather than a
        # missing row nobody counts.
        out.append(cases.multi_misattribution_probe(
            [(entry, first), (other, second)], _entry_rng("multi-probe", entry.key)))
```

- [ ] **Step 8: Add `shared_origin_probe` to the banned set**

In `tests/test_generate.py`, in `test_probe_rows_never_enter_train_or_val`, change the set at lines `109-110`:

```python
    banned = {"positional_probe", "misattribution_probe", "contradiction_probe",
              "multi_misattribution_probe"}
```

to:

```python
    banned = {"positional_probe", "misattribution_probe", "contradiction_probe",
              "multi_misattribution_probe", "shared_origin_probe"}
```

It is the only eval-only slice missing from that set, for no reason other than that it was added after the set was written.

- [ ] **Step 9: Run the whole suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: all PASS. In particular `test_multi_probe_rows_carry_two_distinct_workloads` (line 194) still passes — it now asserts the builder's own guarantee rather than a property that happened to hold.

- [ ] **Step 10: Demonstrate the failure — the pinned counts**

The spec requires each guard be *observed failing*. Perturb, observe, revert.

```bash
cd "$(git rev-parse --show-toplevel)"
# Perturbation: drop one entry from the multi-probe loop's source list.
# In generate.py's probe_sets(), temporarily change
#   with_losers = [e for e in catalog.trainable() if e.losers]
# to
#   with_losers = [e for e in catalog.trainable() if e.losers][:-1]
.venv/bin/pytest tests/test_generate.py::test_test_set_slice_counts_are_pinned -q
```

Expected: **FAIL**, and the assertion diff shows `'multi_misattribution_probe': 18` against the pinned `19`.

Then revert and confirm green:

```bash
git checkout -- src/kubeagent_verdict/dataset/generate.py   # ONLY if you have not yet
                                                            # staged Step 7's edit;
                                                            # otherwise undo by hand
.venv/bin/pytest tests/test_generate.py -q
```

**Safer ordering:** do this demonstration *before* staging, or re-apply Step 7's edit by hand after reverting. Verify with `git diff` that Step 7's change is still present before committing.

- [ ] **Step 11: Demonstrate the failure — the builder's raise**

```bash
# Perturbation: in probe_sets(), force both draws to the same name by
# temporarily changing the `second = ...` line to
#   second = first
.venv/bin/pytest tests/test_generate.py -q
```

Expected: **FAIL** with the builder's `ValueError: multi_misattribution_probe needs distinct workloads: [...]` — a named failure, not a silently smaller slice. Revert by hand and confirm green.

- [ ] **Step 12: Lint and commit**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check .
git add tests/test_generate.py src/kubeagent_verdict/dataset/cases.py \
        src/kubeagent_verdict/dataset/generate.py
git commit -s -m "test: pin every test-set slice count, and make a lost probe row loud

No test pinned any slice count -- the literals 253 and 19 appeared nowhere
in tests/ -- while generate.py's multi-probe loop silently skipped a row on
a name collision. Together those let multi_misattribution_probe go from 19
rows to 18 with the suite green, quietly turning a '<=1 of 19' release bar
into '<=1 of 18'.

The distinctness check moves into cases.multi_misattribution_probe as a
raise, so every caller gets it, and the caller's `continue` is deleted so
the raise propagates. On today's tree the two seeded draws never collide,
so this is a no-op on behaviour and a named failure on any tree where it
is not.

shared_origin_probe joins the banned set in
test_probe_rows_never_enter_train_or_val; it was the only eval-only slice
missing from it.

Demonstrated failures (perturbation reverted, not committed):
  - dropped one entry from with_losers -> pinned table failed with
    multi_misattribution_probe 18 != 19
  - forced both multi-probe draws to the same name -> ValueError
    'needs distinct workloads', not a silent skip"
```

---

### Task 2: Instrument 1 — the contamination lock

**Files:**
- Create: `tests/test_contamination.py`

**Interfaces:**
- Consumes: the pinned slice counts from Task 1 — this test asserts *zero contamination per slice*, which is only meaningful because Task 1 independently guarantees all twelve slices exist at their pinned sizes. A missing slice contributes zero rows and would pass this test vacuously.
- Produces: nothing later tasks consume.

**Background the implementer needs:** the shipped v0.1.0 weights were trained at `8bd9d28`, where 33 of 253 test rows were contaminated. Commit `baf173e` fixed the cause — `drop_held_out` now splits compound group keys on `+` on **both** sides. Today contamination is 0/253. **Nothing recomputes that intersection**, so a regression would ship green, which is exactly how the original leak shipped.

The definition must match `drop_held_out`'s own contract (`generate.py:114-134`). Reading either side unsplit re-derives the very blind spot `baf173e` fixed — `tests/test_generate.py:112-114` records that this exact mistake once let a test assert the buggy rule against itself and pass while 103 train rows leaked.

`Example.group` is **never serialized** (`to_row()` writes only `ex.meta`, which has no `group` key), so this test operates on in-process `Example` objects, never on JSONL.

- [ ] **Step 1: Write the test module**

Create `tests/test_contamination.py`:

```python
"""The contamination lock.

The shipped v0.1.0 weights were trained at 8bd9d28, where 33 of 253 test
rows shared a workload identity with training data -- concentrated in
multi_misattribution_probe (19/19) and contradiction_probe (14/19), which
is what forced both slices to be withdrawn in docs/model-card.md.

Commit baf173e fixed the cause: drop_held_out splits compound group keys
on "+" on BOTH sides. Nothing recomputed the intersection afterwards, so a
regression would have shipped green -- which is how the original leak
shipped. This is that recomputation.

The split-on-both-sides rule is not incidental. Reading either side unsplit
re-derives the blind spot baf173e fixed; tests/test_generate.py:112-114
records that mistake letting a test assert the buggy rule against itself and
pass while 103 train rows leaked.
"""

import collections

from kubeagent_verdict.dataset import generate

# The release configuration, from docs/runbooks/train.md. Contamination is a
# function of seed and size, so a number measured at any other configuration
# says nothing about what ships.
SEED, SIZE = 17, 5500


def _parts(examples: list) -> set[str]:
    """Every group key, split on "+" -- drop_held_out's own unit."""
    return {part for ex in examples for part in ex.group.split("+")}


def _build() -> tuple[list, list, list]:
    exs = generate.generate(seed=SEED, size=SIZE)
    train, val = generate.split(exs, seed=SEED)
    return train, val, generate.test_set()


def test_no_test_row_shares_an_identity_with_training_data():
    """Per slice, not a single total -- a total hides which slice regressed."""
    train, val, test = _build()
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    trained = _parts(kept)
    tainted = collections.Counter(
        ex.case for ex in test
        if any(part in trained for part in ex.group.split("+")))
    assert dict(tainted) == {}


def test_the_filter_is_actually_doing_work():
    """Non-vacuity.

    Without this the lock above passes the moment generate() stops producing
    collisions for an unrelated reason, and a vacuous green is the exact
    failure mode this slice exists to prevent.

    Asserted as `> 0`, never as the measured 913: that figure is a function
    of seed and size, and pinning it would fail the test on an innocent
    curriculum change while proving nothing extra.
    """
    train, val, test = _build()
    held = _parts(test)
    before = sum(1 for ex in train + val
                 if any(part in held for part in ex.group.split("+")))
    assert before > 0, (
        "no train/val row collides with a test identity before filtering, so "
        "the contamination lock above cannot fail and proves nothing")
```

- [ ] **Step 2: Run it — both should PASS on today's tree**

Run: `.venv/bin/pytest tests/test_contamination.py -v`
Expected: **2 passed**. These are guards over an already-correct tree. If either fails, stop and report — the tree has regressed and that is a finding, not a plan defect.

Note this test builds a 5500-row curriculum twice; expect it to take a few seconds, not milliseconds.

- [ ] **Step 3: Demonstrate the failure — the lock**

```bash
cd "$(git rev-parse --show-toplevel)"
# Perturbation: revert drop_held_out to the pre-baf173e unsplit comparison.
# In generate.py, temporarily change the body of drop_held_out to:
#     held = {ex.group for ex in test}
#     return [ex for ex in examples if ex.group not in held]
.venv/bin/pytest tests/test_contamination.py::test_no_test_row_shares_an_identity_with_training_data -q
```

Expected: **FAIL**, with the counter naming non-zero counts in `multi_misattribution_probe` and `contradiction_probe` — the two slices `docs/model-card.md:378-379` withdrew. Revert with `git checkout -- src/kubeagent_verdict/dataset/generate.py` (Task 1's edit to this file is already committed, so `checkout --` is safe here) and confirm green.

- [ ] **Step 4: Demonstrate the failure — the non-vacuity half**

```bash
# Perturbation: in test_the_filter_is_actually_doing_work, temporarily
# replace the `before = sum(...)` expression with `before = 0`.
.venv/bin/pytest tests/test_contamination.py::test_the_filter_is_actually_doing_work -q
```

Expected: **FAIL** on the `> 0` assertion, printing the "cannot fail and proves nothing" message. Revert by hand and confirm green.

- [ ] **Step 5: Lint and commit**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check .
git add tests/test_contamination.py
git commit -s -m "test: lock in the 0/253 contamination result

v0.1.0 trained at 8bd9d28 with 33 of 253 test rows contaminated; baf173e
took that to 0 by splitting compound group keys on '+' on both sides. No
test recomputed the intersection afterwards, so a regression would ship
green -- which is how the original leak shipped.

Two assertions, both required. The lock counts tainted rows PER SLICE, not
as one total, because a total hides which slice regressed. The non-vacuity
half asserts the pre-filter collision count is greater than zero, so the
lock cannot pass by the curriculum quietly ceasing to collide. It asserts
'> 0' rather than the measured 913: that figure is a function of seed and
size and pinning it would fail on an innocent curriculum change.

Operates on in-process Example objects -- Example.group is never
serialized, so this can never be computed from the JSONL.

Demonstrated failures (perturbations reverted, not committed):
  - reverted drop_held_out to the pre-baf173e unsplit comparison ->
    non-zero counts in multi_misattribution_probe and contradiction_probe
  - stubbed the pre-filter collision count to 0 -> the '> 0' assertion"
```

---

### Task 3: Instrument 2 — the `ast` guard over the generator

**Files:**
- Create: `tests/test_generator_structure.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks consume.

**Background:** the five eval-only case builders must never become reachable from the training-construction path. A *negative* guard alone passes trivially if the thing it forbids stops existing, so a *positive* half is required too: every name in `HELD_OUT_CASES` must actually be built by `held_out_case_set()`. That positive half catches a case silently dropping out of the test set — a name removed from the builder while staying in the tuple produces a smaller test set and no failure anywhere else.

**The refusal discipline matters.** The guard must **fail by name** on a shape it cannot read, never skip it. This mirrors `internal/diagnose/knownissues_test.go` in the kubeagent repo, which exists for the same reason: a best-effort guard that silently skips an unfamiliar shape is not a guard.

Note for the implementer: `held_out_case_set()` handles `injection` in an `if case == "injection":` branch rather than through its `builders` dict, so the string-constant scan below (not a dict-key scan) is the correct positive check.

- [ ] **Step 1: Write the test module**

Create `tests/test_generator_structure.py`:

```python
"""Structural guards over the generator, read with `ast`.

An eval-only probe that leaks into the training mix destroys the slice it
belongs to -- silently, because the row still renders and still scores. A
runtime check cannot see this: by the time generate() has run, a probe row
in the training set looks exactly like any other row.

Two halves, both required. A negative guard alone passes trivially if the
thing it forbids stops existing.

This guard REFUSES shapes it cannot read rather than skipping them. If
CASE_MIX stops being a tuple of literal pairs, or generate()'s calls stop
being plain `cases.<attr>(...)` calls, it fails by name -- widening it is
then a deliberate edit, not an accident. A best-effort guard that silently
skips an unfamiliar shape is not a guard.
"""

import ast
from pathlib import Path

from kubeagent_verdict.dataset import generate

GENERATE_PY = (Path(__file__).resolve().parents[1]
               / "src" / "kubeagent_verdict" / "dataset" / "generate.py")

# The five builders that exist to make a shortcut visible. A shortcut the
# training data rewards is not a shortcut the eval can detect.
EVAL_ONLY = frozenset({"positional_probe", "misattribution_probe",
                       "multi_misattribution_probe", "contradiction_probe",
                       "shared_origin_probe"})


def _module() -> ast.Module:
    return ast.parse(GENERATE_PY.read_text(encoding="utf-8"))


def _module_assign(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(
        f"{name} is no longer a module-level assignment in generate.py. "
        f"This guard refuses shapes it cannot read; widen it deliberately.")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(
        f"generate.py no longer defines a function named {name}. "
        f"This guard refuses shapes it cannot read; widen it deliberately.")


def _literal_case_names(value: ast.expr, what: str) -> list[str]:
    """The case-name strings out of CASE_MIX, refusing any other shape."""
    assert isinstance(value, ast.Tuple), (
        f"{what} is no longer a literal tuple ({type(value).__name__}). "
        f"A computed value cannot be read statically; this guard refuses it "
        f"rather than skipping it.")
    names = []
    for elt in value.elts:
        assert isinstance(elt, ast.Tuple) and len(elt.elts) == 2, (
            f"{what} entry is no longer a 2-tuple literal; refused.")
        head = elt.elts[0]
        assert isinstance(head, ast.Constant) and isinstance(head.value, str), (
            f"{what} entry's case name is no longer a string literal; refused.")
        names.append(head.value)
    return names


def test_case_mix_names_no_eval_only_case():
    names = _literal_case_names(_module_assign(_module(), "CASE_MIX"), "CASE_MIX")
    leaked = EVAL_ONLY & set(names)
    assert not leaked, f"eval-only cases in the training mix: {sorted(leaked)}"


def test_generate_calls_no_eval_only_builder():
    """generate() builds train/val. None of the five may be reachable from it."""
    fn = _function(_module(), "generate")
    called = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        assert not isinstance(func, ast.Subscript), (
            "generate() dispatches a call through a subscript, which cannot be "
            "read statically; refused rather than skipped.")
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "cases"):
            called.add(func.attr)
    leaked = EVAL_ONLY & called
    assert not leaked, f"generate() builds eval-only cases: {sorted(leaked)}"


def test_every_held_out_case_is_built():
    """The positive half.

    A name removed from held_out_case_set() while staying in HELD_OUT_CASES
    produces a smaller test set and no failure anywhere else.

    What this proves is narrower than "the case is built": it reads every
    string constant in the function, so a name kept only as a comparison
    operand -- `elif case == "x": continue` -- still counts as named. That
    shape is covered by the behavioural sibling below, not by this test, and
    the assertion says "named" rather than "built" for that reason.
    """
    tree = _module()
    value = _module_assign(tree, "HELD_OUT_CASES")
    assert isinstance(value, ast.Tuple), (
        "HELD_OUT_CASES is no longer a literal tuple; refused.")
    declared = []
    for elt in value.elts:
        assert isinstance(elt, ast.Constant) and isinstance(elt.value, str), (
            "HELD_OUT_CASES entry is no longer a string literal; refused.")
        declared.append(elt.value)

    fn = _function(tree, "held_out_case_set")
    handled = {node.value for node in ast.walk(fn)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    missing = [case for case in declared if case not in handled]
    assert not missing, (
        f"declared in HELD_OUT_CASES but never named in held_out_case_set(): "
        f"{missing}")


def test_held_out_cases_all_reach_the_test_set():
    """The positive half again, behaviourally.

    The static check above reads names; this one checks rows actually arrive.
    Together they catch both a name that stops being built and a builder that
    stops producing.
    """
    present = {ex.case for ex in generate.test_set()}
    missing = set(generate.HELD_OUT_CASES) - present
    assert not missing, f"held-out cases absent from the test set: {sorted(missing)}"
```

- [ ] **Step 2: Run it — all four should PASS on today's tree**

Run: `.venv/bin/pytest tests/test_generator_structure.py -v`
Expected: **4 passed**.

- [ ] **Step 3: Demonstrate the failure — the negative half**

```bash
cd "$(git rev-parse --show-toplevel)"
# Perturbation: temporarily add ("positional_probe", 5) to CASE_MIX in
# generate.py.
.venv/bin/pytest tests/test_generator_structure.py::test_case_mix_names_no_eval_only_case -q
```

Expected: **FAIL** — `eval-only cases in the training mix: ['positional_probe']`. Revert with `git checkout -- src/kubeagent_verdict/dataset/generate.py` and confirm green.

- [ ] **Step 4: Demonstrate the failure — the positive half**

```bash
# Perturbation: in held_out_case_set(), temporarily delete the
# "wrong_attribution": cases.wrong_attribution entry from the builders dict,
# and skip the case WITHOUT naming it -- dispatch on the dict itself:
#     elif case in builders:
#         ...
# The name must leave the function body entirely. An
# `elif case == "wrong_attribution": continue` does NOT work: the static half
# reads every string constant in the function, so the literal left behind in
# the comparison still counts as named and only the behavioural test fails.
.venv/bin/pytest tests/test_generator_structure.py -q
```

Expected: **FAIL** on `test_every_held_out_case_is_built` with `declared in HELD_OUT_CASES but never named in held_out_case_set(): ['wrong_attribution']`, and on `test_held_out_cases_all_reach_the_test_set`. Revert and confirm green.

That the two shapes fail differently is the point rather than a wrinkle: the
static half proves a name is *mentioned*, the behavioural half proves rows
*arrive*, and only the pair covers both a name that stops being built and a
builder that stops producing. Neither alone is the guard.

- [ ] **Step 5: Demonstrate the failure — the refusal**

```bash
# Perturbation: temporarily rewrite CASE_MIX as a computed value, e.g.
#     CASE_MIX = tuple(zip(("attributed", "none_of_these"), (30, 15)))
.venv/bin/pytest tests/test_generator_structure.py::test_case_mix_names_no_eval_only_case -q
```

Expected: **FAIL** with `CASE_MIX is no longer a literal tuple (Call)` — refused **by name**, not silently skipped. This is the observation that matters most: it proves the guard cannot be disabled by making it unreadable. Revert and confirm green.

- [ ] **Step 6: Lint and commit**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check .
git add tests/test_generator_structure.py
git commit -s -m "test: ast guard keeping eval-only probes out of the training mix

An eval-only probe that leaks into training destroys the slice it belongs
to, silently -- the row still renders and still scores, so no runtime check
can see it.

Two halves, both required. Negative: none of the five eval-only builders may
appear in CASE_MIX or as a cases.<name> call inside generate(). Positive:
every name in HELD_OUT_CASES must be built by held_out_case_set(), which is
what catches a case dropping out of the test set -- a name removed from the
builder while staying in the tuple produces a smaller test set and no
failure anywhere else. A fourth test checks the same positive property
behaviourally, so a builder that stops producing rows fails too.

The guard refuses shapes it cannot read rather than skipping them: a
computed CASE_MIX, a non-literal entry, or a call dispatched through a
subscript fails by name. Widening it is then a deliberate edit. Same
discipline as kubeagent's internal/diagnose/knownissues_test.go, for the
same reason.

Demonstrated failures (perturbations reverted, not committed):
  - added ('positional_probe', 5) to CASE_MIX -> the eval-only assertion
  - dropped wrong_attribution from held_out_case_set() -> both positive
    assertions
  - rewrote CASE_MIX as tuple(zip(...)) -> refused by name, not skipped"
```

---

### Task 4: Instrument 3 — the evidence-duplication guard

**Files:**
- Create: `tests/test_evidence_overlap.py`

**Interfaces:**
- Consumes: Task 1's pinned slice counts (the read denominators `25`, `50`, `19`, `34` below are a function of those row counts).
- Produces: nothing later tasks consume.

**Background — read this before writing code.** Contamination has a second shape group keys cannot see: two rows with different identities and byte-identical evidence text. That is `contradiction_probe`'s structural confound, and today it is prose in a docstring (`cases.py:282-300`).

**This instrument was specified one way, measured, and rejected.** Whole-block raw SHA-256 finds only **2 of 86** eval-only rows sharing a training block, because `_fmt` substitutes each row's freshly drawn namespace, workload name, pod name and image into every read — so two rows built from the same template are never byte-identical. A guard that cannot see the sharing it was built to document is not a guard; it is a comment that runs. Two changes fix it, **both measured**:

1. **Per-read, not per-block.** A `multi_misattribution_probe` row concatenates two entries' reads, so its *block* matches only on a coincidental entry pair. Its individual *reads* are plain `attributed` reads (`cases.py:361`, `all_reads.extend(_reads(e, n)[:2])`) and are reused wholesale.
2. **Identity-masked, not raw.** Mask the row's own namespace and workload name — both recoverable from `ex.group` — then collapse the derived `<NAME>-<suffix>` pod form.

The pod-suffix mask is **load-bearing**, and these are the measured numbers proving it:

| slice | ns + name + pod mask | ns + name only |
| --- | --- | --- |
| `positional_probe` | 23 / 25 | 6 / 25 |
| `misattribution_probe` | 24 / 25 | 6 / 25 |
| `multi_misattribution_probe` | 47 / 50 | 12 / 50 |
| `contradiction_probe` | 17 / 19 | 3 / 19 |
| `shared_origin_probe` | **0 / 34** | **0 / 34** |

**Exact hashing after masking, never similarity.** There is no repo precedent for a similarity metric (zero hits for `difflib`, `SequenceMatcher`, `levenshtein`, `jaccard`, `cosine`, `embedding`), and a similarity threshold is a number nobody can defend. Masked-exact needs no threshold, is a set lookup, and stays stdlib-only.

**Pin counts, not booleans.** A boolean allowlist detects sharing *appearing*. A pinned count also detects it *disappearing* — so when `contradiction_probe`'s confound is eventually closed, `17 / 19` becomes `0 / 19`, the test fails, and the allowlist entry has to be deleted **deliberately** rather than remembered.

**`multi_misattribution_probe` gets an entry.** It was specified to get none, on the reasoning that any sharing there is a defect. Measurement says 47 of its 50 reads are reused, by exactly the same design as `positional_probe`'s — the guard as originally specified would have failed on a correct tree. `shared_origin_probe`'s `0 / 34` is what shows the guard discriminates rather than rubber-stamping every slice put in front of it: its rows come from `dataset.propagation`, not the catalog.

**Group-key shapes.** A catalog group is `entry.key:ns/name` (one colon). A `shared_origin_probe` group is `propagation:<scenario>:ns/name` (**two** colons). The mask must therefore `rsplit(":", 1)`, not `split(":", 1)` — both forms happen to produce identical counts today, but only `rsplit` is correct by construction for both shapes.

- [ ] **Step 1: Write the test module**

Create `tests/test_evidence_overlap.py`:

```python
"""The duplication guard: evidence text shared between eval and training.

Group keys cannot see this shape of contamination -- two rows with different
identities and byte-identical evidence. That is contradiction_probe's
structural confound, and until now it was prose in a docstring
(cases.py:282-300). This makes it a machine-checked fact.

Two design decisions, both forced by measurement rather than assumed:

PER-READ, NOT PER-BLOCK. Whole-block raw hashing finds 2 of 86 rows, because
_fmt substitutes each row's freshly drawn namespace, name, pod and image, so
two rows from the same template are never byte-identical. A multi row's
BLOCK matches only on a coincidental entry pair; its individual READS are
plain attributed reads and are reused wholesale.

IDENTITY-MASKED, NOT RAW. Masking the row's own ns and name, then collapsing
the derived pod form, is what takes positional_probe from 6/25 to 23/25.
Without the pod mask the guard still fires, but detects only reads that
happen not to mention a pod -- a signal shaped by which template mentions
which field, not by what is shared.

Exact hashing after masking, never similarity. There is no repo precedent
for a similarity metric and a similarity threshold is a number nobody can
defend. Masked-exact needs no threshold and is a set lookup.

The counts below are PINNED, not bounded. A pinned count detects sharing
disappearing as well as appearing -- so when contradiction_probe's confound
is closed, 17/19 becomes 0/19, this fails, and the entry gets deleted
deliberately rather than remembered. Same discipline as a golden file: a
curriculum change that moves these fails the test and the new numbers get
re-declared on purpose.
"""

import hashlib
import re

from kubeagent_verdict.dataset import generate

# The release configuration. These counts are deterministic at exactly this
# seed and size and mean nothing at any other.
SEED, SIZE = 17, 5500

# contract.section() writes "== BEGIN <name> ==\n<body>\n== END <name> ==\n\n";
# render_evidence() writes one "== <label> ==\n<content>\n\n" per read inside it.
BEGIN = "== BEGIN evidence ==\n"
END = "\n== END evidence =="
READ_DELIM = re.compile(r"(?m)^== .* ==$\n")

# names.draw() derives the pod from the workload name as <name>-<suffix>, so
# after the name is masked the pod reads <NAME>-<suffix>. Collapsing it is
# load-bearing: without it positional_probe reads 6/25 instead of 23/25.
POD = re.compile(r"<NAME>-[a-z0-9]{3,}(?:-[a-z0-9]{3,})?")

# slice -> (reads reused from train/val, total reads). Every entry is a
# measured fact with a reason; see the module docstring and the design spec.
DECLARED = {
    # Reuses attributed's reads by design -- the candidate menu is the only
    # perturbation, which IS the whole measurement. Costs nothing.
    "positional_probe": (23, 25),
    "misattribution_probe": (24, 25),
    # Same, in the multi shape: _reads(e, n)[:2] per constituent.
    "multi_misattribution_probe": (47, 50),
    # THIS ROW IS THE POINT OF THE INSTRUMENT. It reuses none_of_these_case's
    # read text verbatim, and none_of_these is a fixed 15% of every curriculum
    # via CASE_MIX -- which is why this slice cannot catch a model reciting an
    # entry-lookup table. Negative control v4 measured the known-broken first
    # tune at 1.0 cause / 0.0 decoy here. When that confound is closed this
    # becomes 0/19 and this entry must be deleted, not updated.
    "contradiction_probe": (17, 19),
    # THIS ROW IS THE POINT OF THE ALLOWLIST. Its rows come from
    # dataset.propagation, not the catalog, so it shares nothing -- which is
    # what shows the guard discriminates rather than rubber-stamping.
    "shared_origin_probe": (0, 34),
}


def _reads(ex) -> list[str]:
    """Split a rendered evidence block into its individual reads."""
    user = ex.user
    start = user.find(BEGIN)
    end = user.find(END, start)
    assert start >= 0 and end > start, (
        f"a {ex.case} row has no delimited evidence block; the guard refuses "
        f"to score a shape it cannot read")
    body = user[start + len(BEGIN):end]
    return [part for part in READ_DELIM.split(body) if part.strip()]


def _mask(text: str, ex) -> str:
    """Blank the row's own identity so two rows from one template collide.

    A catalog group is `entry.key:ns/name`; a shared_origin_probe group is
    `propagation:<scenario>:ns/name`. rsplit takes the last field in both.
    """
    for part in ex.group.split("+"):
        if ":" not in part or "/" not in part:
            continue
        ns, _, name = part.rsplit(":", 1)[1].partition("/")
        if ns:
            text = text.replace(ns, "<NS>")
        if name:
            text = text.replace(name, "<NAME>")
    return POD.sub("<POD>", text)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_eval_only_evidence_reuse_matches_the_declared_allowlist():
    exs = generate.generate(seed=SEED, size=SIZE)
    train, val = generate.split(exs, seed=SEED)
    test = generate.test_set()
    # What actually TRAINS -- post-filter, not the raw split.
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    trained = {_digest(_mask(read, ex)) for ex in kept for read in _reads(ex)}

    measured = {}
    for case in DECLARED:
        pairs = [(ex, read) for ex in test if ex.case == case
                 for read in _reads(ex)]
        assert pairs, f"{case} produced no reads; the slice is missing"
        hits = sum(1 for ex, read in pairs if _digest(_mask(read, ex)) in trained)
        measured[case] = (hits, len(pairs))

    assert measured == DECLARED, (
        "declared evidence reuse moved. This is a golden-file-shaped failure: "
        "re-measure, understand WHY it moved, and re-declare on purpose. "
        "A count going DOWN is as meaningful as one going up.")
```

- [ ] **Step 2: Run it — it should PASS on today's tree**

Run: `.venv/bin/pytest tests/test_evidence_overlap.py -v`
Expected: **PASS**. If it fails, print `measured` and stop — do **not** edit `DECLARED` to match. The declared numbers are the measurement this instrument exists to defend; silently updating them is exactly the failure mode the whole slice was built to prevent.

- [ ] **Step 3: Demonstrate the failure — sharing appearing**

```bash
cd "$(git rev-parse --show-toplevel)"
# Perturbation: make shared_origin_probe reuse a catalog read. In
# tests/test_evidence_overlap.py temporarily change the shared_origin_probe
# entry to (1, 34) and confirm the test fails -- OR, better, temporarily add
# a catalog-derived read to cases.shared_origin_probe.
# The cheap version: change DECLARED["shared_origin_probe"] to (1, 34).
.venv/bin/pytest tests/test_evidence_overlap.py -q
```

Expected: **FAIL**, the diff showing `shared_origin_probe: (0, 34)` measured against `(1, 34)` declared. Revert.

- [ ] **Step 4: Demonstrate the failure — sharing disappearing**

```bash
# Perturbation: temporarily change DECLARED["contradiction_probe"] to (0, 19)
# -- simulating its structural confound being closed.
.venv/bin/pytest tests/test_evidence_overlap.py -q
```

Expected: **FAIL**, showing `(17, 19)` measured against `(0, 19)` declared. This is the observation that proves the *pinned count* does something a boolean allowlist could not. Revert.

- [ ] **Step 5: Demonstrate the failure — the mask is load-bearing**

```bash
# Perturbation: temporarily neuter the pod mask by changing the last line of
# _mask() from `return POD.sub("<POD>", text)` to `return text`.
.venv/bin/pytest tests/test_evidence_overlap.py -q
```

Expected: **FAIL** with **every** declared count breaking at once — measured `(6, 25)`, `(6, 25)`, `(12, 50)`, `(3, 19)`, `(0, 34)`. Revert and confirm green.

- [ ] **Step 6: Lint and commit**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check .
git add tests/test_evidence_overlap.py
git commit -s -m "test: pin evidence reuse between the eval slices and training

Group keys cannot see two rows with different identities and identical
evidence text. That is contradiction_probe's structural confound, and until
now it was prose in a docstring.

Specified first as whole-block raw SHA-256, measured, and REJECTED: that
finds 2 of 86 rows, because _fmt substitutes each row's freshly drawn ns,
name, pod and image, so two rows from one template are never byte-identical.
It would have shipped green and stayed green through almost any regression.

Two measured changes fix it. Per-read rather than per-block: a multi row's
block matches only on a coincidental entry pair, while its individual reads
are plain attributed reads reused wholesale. Identity-masked rather than
raw: masking ns and name and collapsing the derived pod form takes
positional_probe from 6/25 to 23/25. Exact hashing after masking, never
similarity -- no repo precedent for a similarity metric, and a threshold is
a number nobody can defend.

Counts are PINNED, not bounded, so sharing disappearing fails too: when
contradiction_probe's confound is closed its 17/19 becomes 0/19 and the
entry must be deleted deliberately rather than remembered.

multi_misattribution_probe was specified to get no entry on the reasoning
that any sharing there is a defect. Measurement: 47 of 50 reads reused, by
exactly positional_probe's design -- the guard as specified would have
failed on a correct tree. shared_origin_probe's 0/34 is what shows the
guard discriminates rather than rubber-stamping.

Demonstrated failures (perturbations reverted, not committed):
  - declared shared_origin_probe 1/34 -> failed against measured 0/34
  - declared contradiction_probe 0/19 -> failed against measured 17/19
  - dropped the pod-suffix mask -> all five counts broke at once"
```

---

### Task 5: The new axis — `false_shared_rate`

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py:370-374` (add one meta field and a module constant)
- Modify: `src/kubeagent_verdict/evals/score.py` (module constant, two per-row fields, one aggregate rate + count, one column, one prose line)
- Test: `tests/test_score.py` (five new cases)

**Interfaces:**
- Consumes: Task 1's pinned `multi_misattribution_probe` count of **19** — the denominator the release bar in Task 6 divides by.
- Produces:
  - `cases.SHARED_CLAIM_PHRASES: tuple[str, ...]` — the shared-origin vocabulary, written into each `multi_misattribution_probe` row's meta as `shared_claim_phrases: list[str]`.
  - `score.INDEPENDENCE_PHRASES: tuple[str, ...]` — the independence vocabulary, a module constant.
  - Per-row result keys `false_shared: float | None` and `shared_ambiguous: bool`.
  - Aggregate keys `false_shared_rate` (a `_rate()` dict) and `shared_ambiguous_n` (a plain `int`).

**Background.** `separate_reasons_rate` (`score.py:188-190`, n=10 on `shared_origin_probe`) measures the model wrongly claiming independence where a shared origin is true. **It has no mirror**, so a model that answers "shared origin" everywhere scores perfectly on it and is worse than what it replaced. `false_shared_rate` is that mirror: the rate at which the model claims a shared origin on `multi_misattribution_probe` (n=19), the one slice where independence is the **correct** answer.

Resolution is three-way, and the third row is an honesty gate:

| summary contains | verdict |
| --- | --- |
| a shared-claim phrase, no independence phrase | **1.0** — false shared claim |
| an independence phrase, no shared-claim phrase | **0.0** — correct |
| both, or neither | **`None`** — ambiguous, counted separately |

A summary reading "these are **not** caused by a shared origin" contains shared-origin language and is correct; scoring it 1.0 would manufacture a failure. `None` rather than `False` follows `score.py:63-71`'s established rule — a case the metric cannot read must never average in as the best possible score.

**Where the phrases live, and why.** `score.py` imports only `kubeagent_verdict.contract` and `evals.contract_check` — **never** `dataset`, and it must stay that way. So the error side travels with the row as meta (exactly as `wrong_summary_phrase` does at `cases.py:517`), and the independence side, which is a fixed property of the correct answer rather than of a row, lives as a module constant in `score.py`.

- [ ] **Step 1: Write the five failing tests**

Add to `tests/test_score.py`. Read the file's existing `ROW` fixture and `_decoy_row` helper first and match their style.

```python
def _multi_row(summary):
    """A multi_misattribution_probe row answered with the given summary."""
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "multi_misattribution_probe",
                   "expected": {"shop/api": "memory limit too low for the workload"},
                   "shared_claim_phrases": ["shared origin", "common cause",
                                            "same underlying", "upstream"]}
    answer = json.dumps({"verdicts": [
        {"workload": "shop/api", "cause": "memory limit too low for the workload",
         "confidence": "high", "rationale": "r"}], "summary": summary})
    return score.evaluate([row], lambda messages: answer)


# separate_reasons_rate has no mirror: a model that answers "shared origin"
# everywhere scores perfectly on it while being worse than what it replaced.
# This is that mirror -- multi_misattribution_probe is the one slice where
# independence is the CORRECT answer.
def test_shared_origin_language_on_an_independent_row_scores_one():
    results = _multi_row("These two failures have a shared origin upstream.")
    assert results[0]["false_shared"] == 1.0
    assert results[0]["shared_ambiguous"] is False
    board = score.scoreboard(results)
    assert board["overall"]["false_shared_rate"] == {"rate": 1.0, "n": 1}


def test_independence_language_on_an_independent_row_scores_zero():
    results = _multi_row("2 workloads are failing for separate reasons.")
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False
    assert score.scoreboard(results)["overall"]["false_shared_rate"] == {
        "rate": 0.0, "n": 1}


# The honesty gate. "NOT caused by a shared origin" contains shared-origin
# language and is CORRECT; scoring it 1.0 would manufacture a failure.
def test_both_phrase_kinds_present_is_ambiguous_not_a_failure():
    results = _multi_row(
        "These are not caused by a shared origin; they are unrelated.")
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is True
    board = score.scoreboard(results)
    assert board["overall"]["false_shared_rate"] == {"rate": None, "n": 0}
    assert board["overall"]["shared_ambiguous_n"] == 1


def test_neither_phrase_kind_present_is_ambiguous_not_a_pass():
    results = _multi_row("Two workloads are broken.")
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is True
    assert score.scoreboard(results)["overall"]["shared_ambiguous_n"] == 1


# An unanswered row is UNMEASURED, not ambiguous. Conflating the two would
# make a broken model read as a vague phrase set.
def test_unanswered_row_is_none_and_not_ambiguous():
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "multi_misattribution_probe",
                   "expected": {"shop/api": "memory limit too low for the workload"},
                   "shared_claim_phrases": ["shared origin"]}
    answer = json.dumps({"verdicts": [], "summary": "a shared origin explains both"})
    results = score.evaluate([row], lambda messages: answer)
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is False
    assert score.scoreboard(results)["overall"]["shared_ambiguous_n"] == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_score.py -q -k "shared or ambiguous or independence"`
Expected: **FAIL** — `KeyError: 'false_shared'`. The field does not exist yet. This is ordinary failing-first TDD, unlike Tasks 1–4.

- [ ] **Step 3: Add the shared-claim vocabulary to `cases.py`**

In `src/kubeagent_verdict/dataset/cases.py`, add near the top of the module beside the other module constants:

```python
# Language that asserts a shared upstream origin. It travels with the row as
# meta -- the error side, exactly as `wrong_summary_phrase` does -- so
# `score.py` keys off the field's presence instead of special-casing a slice
# name, and keeps importing nothing from `dataset`.
#
# Deliberately over-inclusive for now. A row matching both these and an
# independence phrase scores None and is counted, so the cost of
# over-inclusion is visible rather than silent, and the counts are how the
# set gets narrowed later.
SHARED_CLAIM_PHRASES = ("shared origin", "shared root cause", "common cause",
                        "common root cause", "same underlying", "same root cause",
                        "upstream", "cascading", "knock-on", "caused by the same")
```

- [ ] **Step 4: Write the field into the probe's meta**

In `multi_misattribution_probe`, change the `meta=` block (currently `cases.py:372-374`) from:

```python
                   meta={"case": "multi_misattribution_probe",
                         "expected": {r["workload"]: r["cause"] for r in rows},
                         "decoy_causes": decoys})
```

to:

```python
                   meta={"case": "multi_misattribution_probe",
                         "expected": {r["workload"]: r["cause"] for r in rows},
                         "decoy_causes": decoys,
                         "shared_claim_phrases": list(SHARED_CLAIM_PHRASES)})
```

- [ ] **Step 5: Add the independence vocabulary to `score.py`**

In `src/kubeagent_verdict/evals/score.py`, beside `KEYWORD_CASES` and `HIGHEST_CONFIDENCE` (after line 18):

```python
# The independence side of the shared-origin question. Unlike the shared-claim
# phrases, this is a fixed property of the CORRECT answer rather than of a row,
# so it lives here rather than in row meta -- which also keeps score.py's
# import boundary intact: contract and contract_check only, never dataset.
INDEPENDENCE_PHRASES = ("separate reasons", "separate causes", "independent",
                        "independently", "unrelated", "distinct causes",
                        "different causes", "not related", "no shared",
                        "no common")
```

- [ ] **Step 6: Derive the two per-row fields in `evaluate()`**

In `evaluate()`, directly after the `wrong_summary` block (currently ending at line 131), add:

```python
        # The MIRROR of `wrong_summary`. On `multi_misattribution_probe` the
        # workloads really are independent, so independence is the CORRECT
        # answer and this measures the model claiming a shared origin where
        # none exists. Without it, `separate_reasons_rate` is trivially gamed:
        # a model that answers "shared origin" everywhere scores perfectly on
        # it while being worse than what it replaced.
        #
        # The `summary` field only -- the same narrow claim
        # `separate_reasons_rate` makes, for the same reason.
        #
        # Three-way, and the third way is an honesty gate. A summary reading
        # "these are NOT caused by a shared origin" contains shared-origin
        # language and is correct; scoring it 1.0 would manufacture a failure.
        # None rather than False, following `named_decoy`: a case the metric
        # cannot read must never average in as the best possible score.
        shared_phrases = meta.get("shared_claim_phrases") or ()
        false_shared = None
        shared_ambiguous = False
        if shared_phrases and answered:
            summary = str((doc or {}).get("summary", "")).lower()
            claims = any(str(p).lower() in summary for p in shared_phrases)
            denies = any(p in summary for p in INDEPENDENCE_PHRASES)
            if claims != denies:
                false_shared = 1.0 if claims else 0.0
            else:
                # Both kinds present, or neither. `shared_ambiguous` is True
                # ONLY here -- an unanswered row is unmeasured, not ambiguous,
                # and conflating the two would make a broken model read as a
                # vague phrase set.
                shared_ambiguous = True
```

Then add both keys to the `results.append({...})` dict, immediately after `"wrong_summary": wrong_summary,`:

```python
                        "false_shared": false_shared,
                        "shared_ambiguous": shared_ambiguous,
```

- [ ] **Step 7: Reduce them in `scoreboard()`**

In `scoreboard()`'s `block()`, immediately after the `separate_reasons_rate` entry (currently ending line 190):

```python
            # Read this WITH `separate_reasons_rate`, never alone. Each is
            # trivially gamed by a model that always gives the other answer.
            # Scored only where the row carries the phrases --
            # `multi_misattribution_probe` -- so it reads n/a elsewhere.
            "false_shared_rate": _rate([r["false_shared"] for r in rs
                                        if r["false_shared"] is not None]),
            # A diagnostic for reading the rate, not a score: the phrase sets
            # are deliberately over-inclusive, and a large count here means
            # they need narrowing, not that the model changed. A metric whose
            # imprecision is invisible is the kind this repo keeps retracting.
            "shared_ambiguous_n": sum(1 for r in rs if r["shared_ambiguous"]),
```

- [ ] **Step 8: Add the column and the prose line**

Extend `COLUMNS` (currently `206-212`) — one new entry, placed beside its pair:

```python
COLUMNS = (("contract", "contract_rate"), ("cause", "cause_accuracy"),
           ("confidence carried", "confidence_carried"),
           ("overconfident", "overconfidence_rate"),
           ("injection echo", "injection_echo_rate"), ("decoy", "decoy_rate"),
           ("separate reasons", "separate_reasons_rate"),
           ("false shared", "false_shared_rate"),
           ("length helps", "cause_when_length_helps"),
           ("length misleads", "cause_when_length_misleads"))
```

`shared_ambiguous_n` is **not** a column — it is a diagnostic for reading the rate, not a score. Report it in prose. At the end of `render_markdown`, replace the final `return`:

```python
    lines.append(row("overall", board["overall"]))
    for case, b in board["by_case"].items():
        lines.append(row(case, b))
    # Not a column: a diagnostic for reading `false shared`, not a score.
    ambiguous = board["overall"].get("shared_ambiguous_n", 0)
    lines.append("")
    lines.append(f"Shared-origin summaries that could not be resolved either "
                 f"way (scored n/a): {ambiguous}. A large count means the "
                 f"phrase sets need narrowing, not that the model changed.")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_score.py -v`
Expected: all PASS, including the pre-existing tests. `tests/test_score.py:59-61` and `:101-103` assert substrings of the markdown, not a golden snapshot, so the new column and prose line do not break them — confirm that is still true.

- [ ] **Step 10: Run the whole suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: all PASS. Task 4's `test_evidence_overlap.py` reads `ex.user`, not meta, so the new meta field does not move its counts — confirm it still passes.

- [ ] **Step 11: Lint and commit**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check .
git add src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/evals/score.py \
        tests/test_score.py
git commit -s -m "feat: false_shared_rate, the mirror of separate_reasons_rate

separate_reasons_rate measures the model claiming independence where a
shared origin is true. It has no mirror, so a model that answers 'shared
origin' everywhere scores perfectly on it while being worse than what it
replaced. That is the obvious failure mode of the obvious correction, and
nothing measured it.

false_shared_rate is that mirror: the rate at which the model claims a
shared origin on multi_misattribution_probe, the one slice where
independence is the correct answer. Read the two TOGETHER or not at all.

Resolution is three-way. A summary reading 'these are NOT caused by a
shared origin' contains shared-origin language and is correct, so both-or-
neither scores None and is counted separately rather than scored 1.0 --
None rather than False, following named_decoy: a case the metric cannot
read must never average in as the best possible score. An unanswered row
is None and NOT ambiguous; it is unmeasured, and conflating the two would
make a broken model read as a vague phrase set.

The ambiguous count is reported in prose, not as a column: it is a
diagnostic for reading the rate. The phrase sets are deliberately over-
inclusive, so seeing how many rows land there is how they get narrowed. A
metric whose imprecision is invisible is the kind this repo keeps having
to retract.

The shared-claim phrases travel with the row as meta, the error side,
exactly as wrong_summary_phrase does; the independence phrases are a fixed
property of the correct answer and live in score.py. That keeps score.py
importing contract and contract_check only, never dataset."
```

---

### Task 6: The release bar

**Files:**
- Modify: `docs/runbooks/train.md:103-133`

**Interfaces:**
- Consumes: `false_shared_rate` and `shared_ambiguous_n` from Task 5; the pinned denominator **19** from Task 1.
- Produces: the written bar Task 7's measurement is read against.

**Background.** `docs/runbooks/train.md:104-133` names four things that decide a release. **None of them names `separate_reasons_rate`**, so a regression on it ships green today. The operator has set the bar: **`false_shared_rate` ≤ 1 of 19.**

- [ ] **Step 1: Add the fifth decider**

In `docs/runbooks/train.md`, in the bulleted list under "Four things decide a release", add a fifth bullet **after** the `overconfidence rate` bullet (which currently ends at line 132) and **before** the "**What this bar does NOT decide…**" paragraph at line 134:

```markdown
   - **Does it distinguish shared origins from coincidence?** Read
     `separate reasons` and `false shared` **together, or not at all.**
     Alone, either is trivially gamed: a model that always answers
     "independent" scores 0 on `false_shared_rate`, and a model that always
     answers "shared origin" scores 0 on `separate_reasons_rate`. The second
     is the obvious failure mode of the obvious correction to the first, and
     nothing measured it until now. **`false_shared_rate` must be ≤ 1 of
     19** — the whole `multi_misattribution_probe` slice, whose count is
     pinned by `tests/test_generate.py`. Check the ambiguous count printed
     under the table beside it: a large one means the phrase sets need
     narrowing, not that the model changed, and it shrinks the denominator
     the ratio above is read against.
```

- [ ] **Step 2: Fix the count in the sentence introducing the list**

The phrase is **wrapped across two lines**: line 106 ends `… and nothing else. Four` and line 107 begins `things decide a release:`. Change the `Four` at the end of line 106 to `Five` — do not search for the whole phrase on one line, it is not there.

Search the surrounding prose for any other "four" that refers to this list and update it too:

```bash
cd "$(git rev-parse --show-toplevel)"
grep -n -i "four things\|four bullets\|the four" docs/runbooks/train.md
```

Note the paragraph at line 134 begins "**What this bar does NOT decide, and a decider that was withdrawn.** A fifth bullet used to stand first here…". That "fifth" refers to the *withdrawn* decider, not the new one — leave its wording alone, but read it to be sure the two do not now read as the same bullet. If they do, change the withdrawn one's wording to "An earlier bullet used to stand first here".

- [ ] **Step 3: Verify the document still reads correctly**

Run: `.venv/bin/python -c "import pathlib; t = pathlib.Path('docs/runbooks/train.md').read_text(); print(t[t.index('6. **Read the scoreboard'):t.index('What this bar does NOT')])"`
Expected: five bullets, the new one last, and the "Five things decide a release" lead-in.

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add docs/runbooks/train.md
git commit -s -m "docs: add the fifth release decider

The codified bar named four things and none of them was
separate_reasons_rate, so a regression on the model's weakest measured
axis shipped green.

The fifth decider names it and its new mirror together, because neither
means anything alone: a model that always answers 'independent' scores 0
on false_shared_rate, and one that always answers 'shared origin' scores 0
on separate_reasons_rate. Same read-these-together discipline the existing
'length helps / length misleads' bullet already establishes.

The bar is false_shared_rate <= 1 of 19, against the whole
multi_misattribution_probe slice, whose count is now pinned by a test. The
ambiguous count is to be read beside it -- it shrinks the denominator."
```

---

### Task 7: The v0.1.0 baseline measurement

> **Controller-executed.** This task needs `llama-server` running against the shipped v0.1.0 GGUF and is not dispatched to an implementer subagent. It is its own commit so the instruments are reviewed separately from the measurement they enable.

**Files:**
- Modify: `docs/model-card.md`

**Interfaces:**
- Consumes: Task 5's `false_shared_rate` and Task 6's written bar.
- Produces: the measured baseline that turns "≤1 of 19" from a guess into a number.

**Stated in advance so the run can contradict it:** v0.1.0 emits separate-reasons language on this slice, so `false_shared_rate` should be at or near **0/19** — while `separate_reasons_rate` is **1.0**, because the same habit that makes it safe here makes it wrong on all ten `shared_origin_probe` rows. A baseline reading "0.0 and 1.0" is not a contradiction; it is the pair demonstrating on its first run why neither number means anything alone.

- [ ] **Step 1: Regenerate the dataset at the release configuration**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/kv-dataset --seed 17 --size 5500
```

This writes `train.jsonl`, `val.jsonl` and `test.jsonl`. It does **not** touch `dist/`.

- [ ] **Step 2: Serve the shipped v0.1.0 GGUF**

Start `llama-server` against the **already-shipped** GGUF at temperature 0. **Do not run `kv-export`** — that writes `dist/` and would overwrite the signed artifact.

- [ ] **Step 3: Score**

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/kv-eval --endpoint <local endpoint> --model <served model name>
```

Never `python -m kubeagent_verdict.evals.cli` — it is a silent no-op.

- [ ] **Step 4: Read the two numbers together**

Record `false_shared_rate` and its `n`, `separate_reasons_rate` and its `n`, and the ambiguous count from the prose line. A denominator below 19 on `false_shared_rate` is itself the signal that the phrase sets are too loose — record it rather than reporting the rate alone.

- [ ] **Step 5: Write the measurement into the model card, and honour the escape clause**

If measured `false_shared_rate` **≤ 1/19**: record the number and note the bar is a measurement.

If it **exceeds 1/19**: the bar is wrong and gets revised **against the measurement, with the revision written down**. A bar quietly relaxed to fit the number it was meant to constrain is not a bar — so the revision names the old value, the measured value, and why the new one is defensible.

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add docs/model-card.md
git commit -s -m "docs: baseline v0.1.0 on false_shared_rate

<measured numbers>. Its own commit, so the instruments are reviewed
separately from the measurement they enable, and so the <=1/19 bar is a
measurement rather than a guess."
```

---

## Self-Review

**1. Spec coverage.** Every section of the spec maps to a task:

| Spec section | Task |
| --- | --- |
| Instrument 1 — contamination lock | 2 |
| Instrument 2 — `ast` guard | 3 |
| Instrument 3 — duplication guard + allowlist | 4 |
| Instrument 4 — pin the denominators + two hardenings | 1 |
| The new axis `false_shared_rate` | 5 |
| The release bar | 6 |
| The baseline measurement | 7 |
| Testing (demonstrated-failure table) | Steps 10–11 of Task 1; 3–4 of Task 2; 3–5 of Task 3; 3–5 of Task 4 |
| Sequencing (4 → 1 → 2 → 3 → axis → train.md → baseline) | Task order 1 → 2 → 3 → 4 → 5 → 6 → 7 |
| Constraints | Global Constraints |

Every row of the spec's demonstrated-failure table is a step in this plan except two, deliberately folded: "3, appearing" and "3, disappearing" are implemented as declared-value perturbations rather than generator edits, because editing `cases.shared_origin_probe` to draw a catalog read is a larger change than the observation warrants and risks being left behind. The observation is identical — a declared count failing against a measured one.

**2. Placeholder scan.** No `TBD`/`TODO`. Two intentional placeholders remain, both in Task 7 and both controller-executed with values that cannot be known until the run: `<local endpoint>` / `<served model name>` in Step 3, and `<measured numbers>` in the Step 6 commit message.

**3. Type consistency.**
- `SHARED_CLAIM_PHRASES` is defined in `cases.py` (Task 5, Step 3) and read in `cases.py` (Step 4) — same module. `score.py` never imports it; it reads the serialized `shared_claim_phrases` list from meta. Boundary intact.
- `INDEPENDENCE_PHRASES` is defined and used only in `score.py`.
- `false_shared` (`float | None`) and `shared_ambiguous` (`bool`) are written in `evaluate()` (Step 6) and read in `scoreboard()` (Step 7) under exactly those names.
- `false_shared_rate` is produced in Step 7 and consumed by `COLUMNS` in Step 8, by the tests in Step 1, and by the bar in Task 6 — same spelling throughout.
- `shared_ambiguous_n` is produced in Step 7 and read in `render_markdown` (Step 8) via `.get(..., 0)` so a hand-built board in an older test cannot raise.
- The `ValueError` message from Task 1 Step 5 contains `distinct workloads`, which is exactly what Task 1 Step 3's `pytest.raises(match=...)` looks for.

**4. Numbers.** Every pinned figure — `253`, the twelve slice counts, `(23, 25)`, `(24, 25)`, `(47, 50)`, `(17, 19)`, `(0, 34)`, and the `≤ 1 of 19` bar — was measured at `--seed 17 --size 5500` and is stated with that configuration attached.
