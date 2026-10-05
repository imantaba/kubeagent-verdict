# `multi` rows and decoys (Spec 4b-3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `multi` rows show only reads kubeagent makes, list decoys from
what the prompt shows, write summaries that never claim more than the rows,
refuse empty anchors, and keep every scheduler node count equal to the
cluster-health header.

**Architecture:** Five small code changes in `src/kubeagent_verdict/dataset/`
(`stories.py`, `cases.py`, `gold.py`, `render.py`, `checker.py`,
`generate.py`, three catalog text files), each with its own tests. One new
test file, `tests/test_multi_decoys.py`, holds the cross-build tests and
compares a fresh build with `out/dataset-1004-4b2`. Then a new build in
`out/dataset-1005`, measurements, and docs.

**Tech Stack:** Python 3, pytest, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-05-multi-decoys-design.md`
(commits 1887ece and 3ae79fd). Read it with this plan; where they disagree,
the spec wins.

## Global Constraints

- Repo: `/home/ubuntu/git/kubeagent-verdict`, branch `spec4b3-multi-decoys`. Never work on `main`.
- Every shell call starts with `cd /home/ubuntu/git/kubeagent-verdict &&` (the cwd resets each call).
- PYTEST: `env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` (full suite about 100 s; use a 600000 ms timeout). Baseline: 1937 passed.
- Ruff: `.venv/bin/ruff check --ignore EXE002 .` must print `All checks passed!`.
- TDD: write each test first, run it, see it fail, then write the code.
- Never use `-update`. Re-pins are by hand, with a `2026-10-05 (Spec 4b-3)` comment saying why.
- The bars never move: 0.9 / 0.7 / 0.9, FLOOR, BALANCE 0.10, CEILING 0.30, LABEL_CUE, 0.40/5, 0.12/0.30. A rate pinned at 1.0 stays 1.0.
- Commit only with: `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "<msg>"`. No `Co-Authored-By` trailer and no AI attribution of any kind.
- `git add` only explicit paths. Never `git add -A` or `git add .`. Never commit `.gitignore` or `train-v2.log`.
- Never touch `out/dataset-1004`, `out/dataset-0929`, `out/dataset-1004-4b2`, `.venv`, or `train-v2.log`. Reading `out/` is fine.
- Never name the training host in a tracked file.
- Docs use simple voice: short sentences, plain words, numbers explained.
- The exam (`test.jsonl`) must stay byte-identical. If any exam pin moves, stop and report BLOCKED.

## Review Focus

1. **A non-`multi` row changes by accident.** `Names` gains a field, and `dataclasses.asdict(n)` feeds `str.format` in five places. A reader expects every non-`multi` prompt unchanged. Test 13 (Task 2) pins it on every split.
2. **The rebuild draws randomness.** If `multi`'s second build drew from `rng`, every later row would shift. Test 13 and the row counts (6439 / 739 / 249) catch it; Task 5 Step 3 asserts T is stable.
3. **A summary line over 512 runes or a summary over 4 lines** for a 4-workload row with long causes. Test 6 (Task 2) checks every `multi` and probe row.
4. **A decoy list that holds the workload's own gold** in a case other than `multi`. Test 4 (Task 3) runs over every case and must see more than 1,000 non-empty lists.
5. **IS-22 passing because it looks at nothing.** Test 12 (Task 5) proves it fails a broken copy, and Task 6 checks its inspected count on the build is above 0.

---

### Task 1: The empty-anchor guard

**Files:**
- Modify: `src/kubeagent_verdict/dataset/stories.py` (`Answer.__post_init__`)
- Modify: `src/kubeagent_verdict/dataset/cases.py:427-448` (`_entry_gold`)
- Create: `tests/test_anchor_guard.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `stories.Answer(...)` raises `ValueError("…: the anchor is empty")`; `cases._entry_gold` raises `ValueError("<key>: the anchor is empty after formatting")`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_anchor_guard.py`:

```python
"""Spec 4b-3 test 9: an empty anchor would match every line, so it is refused."""
import dataclasses
import random

import pytest

from kubeagent_verdict.dataset import cases, catalog, stories
from kubeagent_verdict.dataset import names as names_mod


@pytest.mark.parametrize("anchor", ["", "  "])
def test_an_empty_anchor_is_refused(anchor):
    with pytest.raises(ValueError, match="anchor is empty"):
        stories.Answer(anchor=anchor, cause="the disk is full", keys=("disk",), rationale="r")


def test_an_anchor_that_formats_to_empty_is_refused():
    e = next(x for x in catalog.trainable() if x.answer is not None)
    e = dataclasses.replace(e, answer=dataclasses.replace(e.answer, anchor="{image}"))
    n = dataclasses.replace(names_mod.draw(random.Random(11)), image="")
    with pytest.raises(ValueError, match="empty after formatting"):
        cases._entry_gold(e, n, ["any line"], [])
```

Before running, open `stories.py` and check `Answer`'s field names and
required fields. If `Answer` needs more fields than `anchor`, `cause`,
`keys`, `rationale`, add them with plain valid values so only the anchor is
wrong. If `catalog.trainable()` entries' `answer` is a different class than
`stories.Answer`, `dataclasses.replace` still works; if its own
`__post_init__` rejects `"{image}"`, note it in the report.

- [ ] **Step 2: Run them and see them fail**

Run: `PYTEST tests/test_anchor_guard.py`
Expected: 3 FAILED (`DID NOT RAISE`, or for the third, a pass through to a `none_of_these` gold).

- [ ] **Step 3: Write the guards**

In `stories.py`, make this the **first** check in `Answer.__post_init__`
(the key checks come after it today, and an empty anchor must be named
first):

```python
        if not self.anchor.strip():
            raise ValueError(f"{self.cause!r}: the anchor is empty")
```

In `cases._entry_gold`, right after
`anchor = gold._norm_cause(_fmt(a.anchor, n))`:

```python
    if not anchor.strip():
        raise ValueError(f"{e.key}: the anchor is empty after formatting")
```

- [ ] **Step 4: Run the new tests, then the full suite**

Run: `PYTEST tests/test_anchor_guard.py` → 3 passed.
Run: `PYTEST` → 1940 passed. Run ruff → `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_anchor_guard.py src/kubeagent_verdict/dataset/stories.py src/kubeagent_verdict/dataset/cases.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(dataset): refuse an empty anchor"
```

---

### Task 2: One summary rule for `multi`, the probe and 4b-1

**Files:**
- Modify: `src/kubeagent_verdict/dataset/gold.py` (new `summary_lines`, `separate_for`; `_summary` at :219-238 uses them)
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`multi_misattribution_probe` :783-797, `multi` summary lines near its end)
- Modify: `tests/test_shared_origin_training.py` (`test_a_negative_multi_row_still_says_separate_reasons`, about :705)
- Modify: `tests/test_shared_origin_decided.py:195-208`
- Create: `tests/test_multi_decoys.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `gold.summary_lines(rows: Sequence[tuple[str, str]], *, separate: bool) -> str` — `rows` is `(workload key, cause)` in row order; cause `""` means "its own lines do not show why".
  - `gold.separate_for(label: str, causes: Sequence[str]) -> bool` — `causes` uses `""` for a `none_of_these` row.
  - `tests/test_multi_decoys.py` with fixtures `build` (fresh build), `OLD` path, `_old(split)` loader. Tasks 3-5 add tests to this file.

- [ ] **Step 1: Write the helper unit tests (spec test 5)**

Create `tests/test_multi_decoys.py`:

```python
"""Spec 4b-3: multi rows and decoys.

The build here is the out/dataset-MMDD pipeline: generate(17, 8000), split,
drop held-out. Tests that compare with the last build read
out/dataset-1004-4b2 and skip when it is not on this machine.
"""
import json
from pathlib import Path

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import generate, gold
from kubeagent_verdict.evals import score

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "out" / "dataset-1004-4b2"
SPLITS = ("train", "val", "test")
_needs_old = pytest.mark.skipif(not OLD.is_dir(), reason="out/dataset-1004-4b2 is not on this machine")


@pytest.fixture(scope="module")
def build() -> dict[str, list]:
    ex = generate.generate(17, 8000)
    tr, va = generate.split(ex, 17)
    te = generate.test_set()
    return {"train": generate.drop_held_out(tr, te),
            "val": generate.drop_held_out(va, te), "test": te}


def _old(split: str) -> list[dict]:
    path = OLD / f"{split}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _all(build):
    return [e for split in SPLITS for e in build[split]]


_FALLBACK = ("4 workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them.")


# --- test 5: the summary rule ------------------------------------------------

def test_named_and_different_causes_are_separate():
    assert gold.separate_for("none", ["w", "x"])


def test_one_none_of_these_row_is_not_separate():
    assert not gold.separate_for("none", ["w", ""])


def test_two_rows_with_one_cause_are_not_separate():
    assert not gold.separate_for("none", ["w", "w"])


def test_a_separate_label_is_separate_even_with_a_none_row():
    assert gold.separate_for("separate", ["w", ""])


def test_four_rows_put_the_third_and_fourth_on_the_last_line():
    s = gold.summary_lines([("a/one", "w"), ("b/two", "x"), ("c/three", ""), ("d/four", "z")],
                           separate=False)
    assert s.split("\n") == [_FALLBACK, "a/one: w.", "b/two: x.",
                             "c/three: its own lines do not show why. d/four: z."]


@pytest.mark.parametrize("n", [2, 3])
def test_two_and_three_rows_get_one_line_each(n):
    rows = [(f"ns/w{i}", f"cause {i}") for i in range(n)]
    lines = gold.summary_lines(rows, separate=True).split("\n")
    assert lines[0] == f"{n} workloads are failing for separate reasons."
    assert lines[1:] == [f"ns/w{i}: cause {i}." for i in range(n)]
```

- [ ] **Step 2: Run them and see them fail**

Run: `PYTEST tests/test_multi_decoys.py`
Expected: FAIL with `AttributeError: module 'kubeagent_verdict.dataset.gold' has no attribute 'separate_for'` (and `summary_lines`).

- [ ] **Step 3: Write the helper**

In `gold.py`, add `from collections.abc import Iterable, Sequence` (keep
`Iterable`) and `from kubeagent_verdict import contract as c`. Add, above
`_summary`:

```python
def summary_lines(rows: Sequence[tuple[str, str]], *, separate: bool) -> str:
    """A non-shared summary (Spec 4b-3 §3). An opening line, then one line
    per workload in row order: `key: cause.`, or `key: its own lines do not
    show why.` when the cause is "". At most c.MAX_SUMMARY_LINES lines: from
    the 3rd workload on, the rest share the last line, joined by a space.
    The caller decides `separate`; this only writes it."""
    n = len(rows)
    lines = [f"{n} workloads are failing for separate reasons." if separate else
             f"{n} workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them."]
    parts = [f"{k}: {cause}." if cause else f"{k}: its own lines do not show why."
             for k, cause in rows]
    keep = c.MAX_SUMMARY_LINES - 2
    lines += parts[:keep] + ([" ".join(parts[keep:])] if parts[keep:] else [])
    return "\n".join(lines)


def separate_for(label: str, causes: Sequence[str]) -> bool:
    """`multi`'s and the probe's rule: separate when the rules confirmed
    different causes (label `separate`), or when every row names its own
    cause ("" is none_of_these) and no two rows share one."""
    return label == "separate" or (all(causes) and len(set(causes)) == len(causes))
```

Replace the tail of `_summary` (from `lines = [...]` to the end) so it keeps
the `shared` branch and the `separate = (...)` computation as they are and
ends with:

```python
    return summary_lines([(r.key, rows[r.key].cause) for r in built.rows], separate=separate)
```

Update `_summary`'s docstring: add one sentence, "Every workload is named;
from the 3rd one on they share the last line (Spec 4b-3)."

- [ ] **Step 4: Use the helper in the probe and in `multi`**

In `cases.multi_misattribution_probe`, delete the two `lines = …` /
`lines += …` statements, move `label = rules.label(rules.shared(tuple(res.results)))`
above where the summary is built, and build it as:

```python
    label = rules.label(rules.shared(tuple(res.results)))
    causes = ["" if r["cause"] == c.NONE_OF_THESE else r["cause"] for r in rows]
    summary = gold.summary_lines(list(zip(keys, causes)),
                                 separate=gold.separate_for(label, causes))
```

and pass `assistant=_answer(rows, summary)`.

In `cases.multi`, delete the two `lines = …` / `lines += …` statements after
`extra_meta = …` and do the same (`label` is already computed there; `keys`
exists):

```python
    causes = ["" if r["cause"] == c.NONE_OF_THESE else r["cause"] for r in rows]
    summary = gold.summary_lines(list(zip(keys, causes)),
                                 separate=gold.separate_for(label, causes))
```

with `assistant=_answer(rows, summary)`.

- [ ] **Step 5: Run the unit tests**

Run: `PYTEST tests/test_multi_decoys.py` → 7 passed.

- [ ] **Step 6: Write the build tests (spec tests 6, 7, 8, 13)**

Append to `tests/test_multi_decoys.py`:

```python
_SUMMARY_CASES = ("multi", "multi_misattribution_probe")


# --- test 6: every multi and probe summary -----------------------------------

def test_every_multi_and_probe_summary_names_every_workload_and_scores(build):
    seen = 0
    for e in _all(build):
        if e.case not in _SUMMARY_CASES:
            continue
        seen += 1
        doc = json.loads(e.assistant)
        s = doc["summary"]
        lines = s.split("\n")
        assert len(lines) <= c.MAX_SUMMARY_LINES, e.group
        assert all(len(ln) <= c.MAX_MODEL_LINE_RUNES for ln in lines), e.group
        for v in doc["verdicts"]:
            assert f"{v['workload']}: " in s, (e.group, v["workload"])
        assert score.job3(e.meta["label"], s) == 1.0, (e.group, e.meta["label"], s)
    assert seen == 758  # 738 multi + 20 multi_misattribution_probe


# --- test 7: the probe rows do not move --------------------------------------

@_needs_old
def test_the_probe_rows_are_the_old_ones(build):
    new = [generate.to_row(e) for e in build["test"] if e.case == "multi_misattribution_probe"]
    old = [r for r in _old("test") if r["meta"]["case"] == "multi_misattribution_probe"]
    assert len(new) == len(old) == 20
    assert new == old


# --- test 8: 4b-1's answers move only to name every workload -----------------

@_needs_old
def test_only_wide_non_shared_family_answers_move(build):
    moved = 0
    for split in SPLITS:
        old = _old(split)
        assert len(build[split]) == len(old), split
        for i, (e, o) in enumerate(zip(build[split], old)):
            if not e.case.startswith("shared_origin"):
                continue
            na, oa = e.assistant, o["messages"][2]["content"]
            if na == oa:
                continue
            moved += 1
            nd, od = json.loads(na), json.loads(oa)
            assert nd["verdicts"] == od["verdicts"], (split, i)
            assert e.meta["label"] != "shared", (split, i)
            assert len(nd["verdicts"]) >= 4, (split, i)
            nl, ol = nd["summary"].split("\n"), od["summary"].split("\n")
            assert len(nl) == len(ol) == 4, (split, i)
            assert nl[:3] == ol[:3], (split, i)
            assert nl[3].startswith(ol[3] + " "), (split, i)
            for v in nd["verdicts"]:
                assert f"{v['workload']}: " in nd["summary"], (split, i)
    # Spec 4b-3 §3 (amended 2026-10-05): 77 train and val rows, no exam row.
    assert moved == 77


# --- test 13: non-multi prompts do not move ----------------------------------

@_needs_old
@pytest.mark.parametrize("split", SPLITS)
def test_no_non_multi_prompt_moves(build, split):
    old = _old(split)
    assert len(build[split]) == len(old)
    for i, (e, o) in enumerate(zip(build[split], old)):
        if e.case == "multi":
            continue
        assert generate.to_row(e)["messages"][:2] == o["messages"][:2], (split, i)
```

`e.case` is a field of `generate.Example` (checked); `to_row` rows carry
it as `meta["case"]`.

- [ ] **Step 7: Run the build tests**

Run: `PYTEST tests/test_multi_decoys.py`
Expected: all pass. If test 8 counts a number other than 77, or test 6
counts other than 758, stop and report it with the number; do not change
the pin.

- [ ] **Step 8: Rewrite the two old tests this changes**

In `tests/test_shared_origin_training.py`, replace the body of
`test_a_negative_multi_row_still_says_separate_reasons`:

```python
def test_a_negative_multi_row_still_says_separate_reasons(rows):
    """2026-10-05 (Spec 4b-3): a `multi` row says "separate reasons" only when
    its rows show it: the rules confirmed different causes, or every row names
    its own different cause. Otherwise it says the rules confirmed no shared
    cause (4b-1's fallback)."""
    for e in _by_case(rows, "multi"):
        causes = ["" if v == contract.NONE_OF_THESE else v for v in e.meta["expected"].values()]
        assert (propagation.SEPARATE_REASONS in e.assistant) == gold.separate_for(
            e.meta["label"], causes), e.group
```

Add `gold` to the file's `from kubeagent_verdict.dataset import …` line.
Check that `contract.NONE_OF_THESE` exists (it is `c.NONE_OF_THESE` in
`cases.py`, imported as `contract as c`).

In `tests/test_shared_origin_decided.py` (the 4-row loop near :195-208),
change the comment above it to say the summary now names every row, the
3rd and 4th sharing the last line (Spec 4b-3), and after the existing
`assert [ln.split(":")[0] ...]` line add:

```python
            assert all(f"{r.key}: " in lines[3] for r in b.rows[2:]), (st.key, world)
```

- [ ] **Step 9: Run the full suite and ruff**

Run: `PYTEST` and ruff. Expected: all pass, `All checks passed!`. If any
other test fails because a `multi` answer changed, report it (name and
assertion) rather than loosening it, unless it only pinned the old
"first 3 rows" wording, in which case update it to the new rule with a
`2026-10-05 (Spec 4b-3)` comment and say so in the report.

- [ ] **Step 10: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/gold.py src/kubeagent_verdict/dataset/cases.py tests/test_multi_decoys.py tests/test_shared_origin_training.py tests/test_shared_origin_decided.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(dataset): one summary rule for multi, the probe and 4b-1"
```

---

### Task 3: D4 — decoy lists from what the prompt shows

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`multi`'s workload loop)
- Modify: `src/kubeagent_verdict/evals/score.py:215-217` and `:794-798` (comments only)
- Test: `tests/test_multi_decoys.py`

**Interfaces:**
- Consumes: `gold.excluded_from(candidates, result) -> list[str]` (exists).
- Produces: `meta["decoy_by_workload"][key] == gold.excluded_from(candidates, result)` for every `multi` workload.

- [ ] **Step 1: Write the failing tests (spec tests 3 and 4)**

Append to `tests/test_multi_decoys.py` (add `from kubeagent_verdict.dataset import cases, gather` to the imports):

```python
# --- test 3: a multi decoy list is what the prompt rules out -----------------

def test_a_multi_decoy_list_is_what_the_prompt_rules_out(monkeypatch):
    last = {}
    real_gather, real_multi = gather.gather, cases.multi

    def spy_gather(*a, **kw):
        last["res"] = real_gather(*a, **kw)
        return last["res"]

    checked = 0

    def spy_multi(*a, **kw):
        nonlocal checked
        ex = real_multi(*a, **kw)
        res = last["res"]
        for key, cands, result in zip(ex.meta["expected"], res.candidates, res.results):
            assert ex.meta["decoy_by_workload"][key] == gold.excluded_from(cands, result), key
            checked += 1
        return ex

    monkeypatch.setattr(gather, "gather", spy_gather)
    monkeypatch.setattr(cases, "multi", spy_multi)
    generate.generate(17, 800)
    assert checked > 100


# --- test 4: no workload lists its own gold as a decoy -----------------------

def test_no_workload_lists_its_own_gold_as_a_decoy(build):
    with_list = 0
    for e in _all(build):
        decoys = e.meta.get("decoy_by_workload") or {}
        for key, w in (e.meta.get("workloads") or {}).items():
            gold_cause = w.get("expected_cause") or ""
            listed = decoys.get(key) or []
            with_list += bool(listed)
            if not gold_cause or gold_cause == c.NONE_OF_THESE:
                continue
            assert gold._norm_cause(gold_cause) not in {gold._norm_cause(d) for d in listed}, (
                e.case, e.group, key)
    assert with_list > 1000
```

Check before running: `generate.py` calls `cases.multi` through the
module attribute (`cases.multi(...)`), so the spy is seen; and
`ex.meta["expected"]` keys are in row order, the same order as
`res.candidates`. If `generate` imports `multi` by name, patch it where
`generate` looks it up instead and say so in the report.

- [ ] **Step 2: Run them and see test 3 fail**

Run: `PYTEST tests/test_multi_decoys.py -k "decoy"`
Expected: test 3 FAILS (the old list is the decoy-intent objects' causes,
not `excluded_from`). Test 4 may already pass; that is fine — it is the
cross-case guard, and its count assertion must hold.

- [ ] **Step 3: Change `multi`'s decoy list**

In `cases.multi`'s first workload loop, replace the `trace = rules.attribute(...)`
line, its two comment lines and the `decoy_by_workload[...] = [...]`
statement with:

```python
        decoy_by_workload[f"{n.ns}/{n.name}"] = gold.excluded_from(candidates, result)
```

If `objects` is no longer used in that loop, drop it from the `zip` and
the loop variables. Keep `rules` imported if anything else in `cases.py`
uses it (it does: `rules.label`).

- [ ] **Step 4: Fix the two `score.py` comments (no code change)**

At `src/kubeagent_verdict/evals/score.py:215-217`, replace the sentences
that say a `shared_origin_probe` row lists a decided workload's own cause
as a decoy with:

```python
    # No case lists a workload's own gold as its decoy (pinned by
    # tests/test_multi_decoys.py since Spec 4b-3). Job 1 is still skipped:
    # widening the decoy gate to job 1 is a grader change, left for 4b-4.
```

At `:794-798`, replace the reason given there with: the 4a reason (a
decided workload's own cause in its decoy list) stopped holding at 4b-1,
and 4b-3 pins it false; testing job 1 is left for 4b-4. Keep the sentence
that begins "A row with no job-2 workload…". Match the surrounding
comment style. Nothing pins `score.py`'s bytes.

- [ ] **Step 5: Run the tests, the full suite, ruff**

Run: `PYTEST tests/test_multi_decoys.py` → all pass.
Run: `PYTEST` and ruff → all pass, `All checks passed!`. If a
pin in `tests/test_catalog_gold.py` (`GATED_POOL`) or `tests/test_oracle.py`
moves, re-pin it by hand only when the rate it guards stays 1.0, with a
`2026-10-05 (Spec 4b-3)` comment giving the old value. If an **exam** pin
moves, stop and report BLOCKED.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/evals/score.py tests/test_multi_decoys.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(dataset): multi decoy lists come from what the prompt rules out"
```

(Add the re-pinned test files to `git add` if Step 5 touched them.)

---

### Task 4: Remove `multi`'s healthy-origin read

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (delete :1002-1056 helpers; `multi` signature, docstring, body; drop `prop` import)
- Modify: `src/kubeagent_verdict/dataset/generate.py` (:137 import, :156 `train_scen`, :184-214 comment and call, :230-232)
- Modify: `src/kubeagent_verdict/dataset/checker.py` (docstring :17-25, `_Ctx.healthy`, `gathered`, `_context` :486-487)
- Modify: `tests/test_checker.py` (:613-667 block; :669 filter)
- Modify: `tests/test_cases.py:1097-1118`
- Modify: `tests/test_generate.py:1069-1090`
- Modify: `tests/test_shared_origin_training.py`
- Modify: `tests/test_catalog_gold.py` (the dataset-1004 byte test, :270)
- Delete: `tests/test_multi_collision.py`
- Test: `tests/test_multi_decoys.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `cases.multi(pairs, rng) -> Example` (no `healthy_origin`); no `origin_read_label` / `origin_healthy` in `multi` meta; `checker._Ctx.gathered` returns every read.

- [ ] **Step 1: Write the failing tests (spec tests 1 and 2)**

Append to `tests/test_multi_decoys.py` (add `import inspect` and `import re`):

```python
# --- test 1: no healthy-origin read -----------------------------------------

def _labels(user: str) -> list[str]:
    section = user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]
    return re.findall(r"^== (.+) ==$", section, re.MULTILINE)


def test_multi_has_no_healthy_origin_read(build):
    assert "healthy_origin" not in inspect.signature(cases.multi).parameters
    seen = 0
    for e in _all(build):
        if e.case != "multi":
            continue
        seen += 1
        assert "origin_read_label" not in e.meta and "origin_healthy" not in e.meta, e.group
        assert _labels(e.user)[0].startswith("events "), e.group
    assert seen == 738
```

In `tests/test_checker.py`, replace the whole block from the
`# --- the healthy-origin read (multi) ---` heading through
`test_a_healthy_origin_read_at_index_1_is_caught` (about :613-667: the
`_SKIPS_THE_HEALTHY_READ` set, `test_a_healthy_read_is_not_flagged_by_the_rules_that_exempt_it`,
`_READ_BOUNDARY`, `_healthy_row`, `test_a_healthy_origin_read_at_index_0_passes`,
`test_a_label_off_by_one_character_is_caught`,
`test_a_healthy_origin_read_at_index_1_is_caught`) with:

```python
# --- no read is exempt (Spec 4b-3) -------------------------------------------

# The evidence rules that walk the gathered reads. Until 2026-10-05 a
# healthy-origin read at index 0 was left out of them; now every read is in.
_GATHER_RULES = frozenset({"E2-order", "E4", "E6", "E7", "E8", "E9", "E10"})


def test_a_first_read_that_is_not_an_events_read_is_caught(seed_rows):
    """A `multi` row whose read 0 is not an events read fails the checker,
    even when its meta names that read as an origin read."""
    row = next(r for r in seed_rows if r["meta"]["case"] == "multi")
    system, user, assistant, meta = _parts(row)
    label = "describe node /worker-9"
    user = user.replace("== BEGIN evidence ==\n",
                        f"== BEGIN evidence ==\n== {label} ==\nName: worker-9\n\n", 1)
    meta = {**meta, "origin_read_label": label}
    fired = _fired(checker.check(system, user, assistant, meta))
    assert fired & _GATHER_RULES, fired
```

In `test_meta_none_skips_only_ans1s_meta_clause_and_ans2` (about :669),
drop the `and not r["meta"].get("origin_read_label")` clause from its
filter.

- [ ] **Step 2: Run them and see them fail**

Run: `PYTEST tests/test_multi_decoys.py::test_multi_has_no_healthy_origin_read tests/test_checker.py::test_a_first_read_that_is_not_an_events_read_is_caught`
Expected: test 1 FAILS (`healthy_origin` is in the signature); test 2
FAILS (the exemption hides the read, so no gather rule fires).

- [ ] **Step 3: Remove it from `cases.py`**

- Delete `_is_node_story`, `_node_clashes`, `_multi_healthy_origin_node`
  and `_resolve_multi_healthy_origin` (:1002-1056).
- `def multi(pairs: list[tuple[CatalogEntry, Names]], rng: random.Random) -> Example:`
- In its docstring, delete the paragraph that begins "`healthy_origin` is
  the negative half…".
- In its body, delete `healthy_read` and the whole `if healthy_origin is not None:` block.
- The gather call: `res = gather.gather([...])` with no `budget=` argument (the default is `c.MAX_TOOL_CALLS`, gather.py:514-515).
- `reads = res.reads`, with no prepend. Use `res.reads` directly in `_user_message` if `reads` has no other use.
- Delete the `**({} if healthy_read is None else {...})` entry from `meta`.
- Delete `from kubeagent_verdict.dataset import propagation as prop` if
  nothing else in `cases.py` uses `prop` (grep for `prop\.`).

- [ ] **Step 4: Remove it from `generate.py`**

- Drop `propagation` from the import at :137.
- Delete `train_scen = …` at :156.
- Cut the comment at :184-212 to what still holds: `multi` draws 2-4
  catalog pairs; a clash raises and the caller draws again. Remove every
  sentence about the healthy-origin read, the rotation, or "every third".
- :213-214 becomes `out.append(cases.multi(pairs, rng))`.
- At :230-232, drop the `healthy_origin=None` argument.
- Keep the `propagation:` group-prefix string (about :519-533): it is a string, not the module.
- Check `generate.py` still has no unused import (`ruff` will say).

- [ ] **Step 5: Remove the exemption from `checker.py`**

- Docstring: "all 50 rules" stays 50 in this task (IS-22 comes in Task 5);
  delete the whole `- meta["origin_read_label"]: …` bullet (:21-25).
- Delete the `healthy: _Read | None = None` field from `_Ctx`.
- `gathered` becomes:

```python
    @property
    def gathered(self) -> list[_Read]:
        """Every read."""
        return list(self.p.reads)
```

- In `_context`, delete `reads = x.p.reads` (if now unused) and the two
  lines `if meta is not None and reads and reads[0].label == meta.get("origin_read_label"):` / `x.healthy = reads[0]`.

- [ ] **Step 6: Run the two new tests**

Run the Step 2 command. Expected: both PASS.

- [ ] **Step 7: Rewrite or delete the old tests (spec test 14)**

- Delete `tests/test_multi_collision.py` (`git rm`).
- In `tests/test_cases.py`, delete `_plain_story` if only the removed
  parametrize used it (grep first). Replace
  `test_a_multi_row_runs_one_gather_under_one_budget` (:1097-1118) with:

```python
def test_a_multi_row_runs_one_gather_under_one_budget(monkeypatch):
    """One gather reads for every workload of the row, with the whole budget
    of 8. Three crash-family workloads want 9 reads, so the row uses all 8.
    2026-10-05 (Spec 4b-3): the healthy-origin read and its parametrize are
    gone."""
    calls = []
    real = gather.gather

    def spy(workloads, **kw):
        calls.append((len(workloads), kw.get("budget", c.MAX_TOOL_CALLS)))
        return real(workloads, **kw)

    monkeypatch.setattr(gather, "gather", spy)
    ex = cases.multi(_crash_pairs(), random.Random(26))
    labels = _evidence_labels(ex.user)
    assert calls == [(3, c.MAX_TOOL_CALLS)]
    assert len(labels) == c.MAX_TOOL_CALLS
    assert len(set(labels)) == len(labels)
    assert "origin_read_label" not in ex.meta
```

- In `tests/test_generate.py`, in
  `test_a_multi_row_reads_each_object_once_within_the_budget` (:1069-1076),
  set `gathered = labels` and change the docstring's last sentence to
  "Every read is part of the gather." Replace
  `test_a_multi_rows_origin_label_is_the_read_it_prints` (:1078-1090) with:

```python
def test_a_multi_row_has_no_origin_read(multi_rows):
    """2026-10-05 (Spec 4b-3): kubeagent's gather starts with a workload's
    events read, so a multi row's first read is one, and its meta names no
    origin read."""
    for ex in multi_rows:
        assert "origin_read_label" not in ex.meta, ex.group
        assert _evidence_labels(ex.user)[0].startswith("events "), ex.group
```

- In `tests/test_shared_origin_training.py`:
  - Module docstring: replace the paragraph that begins "`multi` was not
    rebuilt." with: "2026-10-05 (Spec 4b-3): `multi` no longer shows a
    healthy-origin read. kubeagent's gather never makes that read, so no
    case carries `origin_read_label` now. The family's side of the shortcut
    is checked in `tests/test_shared_origin_floor.py` and
    `tests/test_shared_origin_pool.py`."
  - The comment above `_DROPPED_META_KEYS`: drop "`multi` still carries
    `origin_read_label`, and nothing below looks at `multi`."
  - `test_both_trainable_pools_exist`'s and `test_no_trainable_origin_is_an_eval_origin`'s
    docstrings: drop the claim that `propagation` feeds `multi`; say the
    `propagation` pool is kept and still checked. Keep their asserts.
  - Delete `_template`, the comment block after it, `_multi_templates`,
    `test_the_multi_negatives_offer_every_origin_read_template`, and
    `test_a_negative_multi_row_shows_the_component_healthy`.
  - `test_node_memory_pressure_spells_no_taint_the_way_kubectl_does`: keep
    it; change its docstring's last sentence to "What stays is the
    `propagation` pool's healthy read text."
  - `_independent_share`: drop the `multi` term, so
    `independent = len(_by_case(rows, "shared_origin_decoy"))`. Add to its
    docstring: "2026-10-05 (Spec 4b-3): `multi` carries no origin read now,
    so only the family counts, and the share is exactly 0.5."
  - `test_the_generator_emits_the_two_classes_near_evenly`: assert
    `_independent_share(rows) == 0.5`. Add a dated note to its docstring:
    "2026-10-05 (Spec 4b-3): the every-third `multi` negatives are gone, so
    only the pair is left and the share is exactly 0.5 (it was 0.5636). The
    old band was 0.55-0.75; it is a test band, not a bar."
  - `test_the_trained_pile_is_not_one_sided_among_origin_read_rows`: assert
    `share == 0.5`, with a dated note: "2026-10-05 (Spec 4b-3): 0.5 exactly
    (it was 0.5385 at this size). `drop_held_out` takes pairs whole, so the
    kept pile is the pair alone. The old band was 0.52-0.70; it is a test
    band, not a bar."
  - Keep `big_rows` (other tests use it).
- In `tests/test_catalog_gold.py`, in `test_no_prompt_byte_moves_from_dataset_1004`
  (:270), skip rows whose old `meta["case"]` is `multi`, with this comment
  above the loop: `# 2026-10-05 (Spec 4b-3): multi prompts move (no healthy-origin read, node counts); tests/test_multi_decoys.py pins every other prompt against out/dataset-1004-4b2.`:

```python
    for i, (a, b) in enumerate(zip(new, old)):
        if b["meta"]["case"] == "multi":
            continue
        assert a["messages"][:2] == b["messages"][:2], (split, i)
```

- Grep the tests for any other `origin_read_label`, `origin_healthy`,
  `healthy_origin` or `_resolve_multi_healthy_origin` use:
  `grep -rn "origin_read_label\|origin_healthy\|healthy_origin\|_resolve_multi" tests src`.
  Leave `test_ruled_scenarios.py:190` (it checks the `propagation` pool,
  not `multi`) and tests about other families that assert the key is
  absent. Fix anything else that reads `multi`'s old read, and list it in
  the report.

- [ ] **Step 8: Run the full suite and ruff**

Run: `PYTEST` and ruff. Expected: all pass. Re-pin rules as in Task 3
Step 5 (`GATED_POOL`, `tests/test_oracle.py`): by hand, dated, only when
the guarded rate stays 1.0; an exam pin moving means BLOCKED.

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git rm -q tests/test_multi_collision.py && git add src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/generate.py src/kubeagent_verdict/dataset/checker.py tests/test_checker.py tests/test_cases.py tests/test_generate.py tests/test_shared_origin_training.py tests/test_catalog_gold.py tests/test_multi_decoys.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(dataset): multi shows only reads kubeagent makes"
```

(Add any re-pinned file from Step 8.)

---

### Task 5: Node counts that agree with the header

**Files:**
- Modify: `src/kubeagent_verdict/dataset/entries_kinds.py:8-10` (`_UNBOUND_CLAIM`)
- Modify: `src/kubeagent_verdict/dataset/entries_slugs.py:99-101`, `:105-107` (node-cordon / unschedulable entry), `:282-283`, `:287-288` (oversized-job-unschedulable)
- Modify: `src/kubeagent_verdict/dataset/catalog.py:28-29` (placeholder comment)
- Modify: `src/kubeagent_verdict/dataset/names.py` (`Names.nodes`)
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_fmt`, `multi`)
- Modify: `src/kubeagent_verdict/dataset/render.py:257-319` and `__all__`
- Modify: `src/kubeagent_verdict/dataset/checker.py` (IS-22, docstring count)
- Modify: `tests/test_checker.py` (`BROKEN`, rule counts at :289 and :858)
- Modify: `tests/test_shared_origin_pool.py:241-262` (rule lists, "50 rules")
- Test: `tests/test_multi_decoys.py`

**Interfaces:**
- Consumes: `cases.multi(pairs, rng)` from Task 4.
- Produces: `Names.nodes: int = 3`; `_fmt` fills `{nodes}` and `{other_nodes}`; `render.node_total(workloads: tuple[c.Workload, ...], reads: tuple[c.EvidenceRead, ...]) -> int`; checker rule `"TXT-IS22"`.

- [ ] **Step 1: Write the failing tests (spec tests 10, 11, 12, 12b)**

Append to `tests/test_multi_decoys.py` (add `import dataclasses`, `import random`,
and `catalog`, `checker`, `render` to the dataset import; add
`from kubeagent_verdict.dataset import names as names_mod`):

```python
# --- test 10: the node fill --------------------------------------------------

_SCHED_ENTRIES = ("pvc-unbound-unschedulable", "node-cordon-diskfull", "oversized-job-unschedulable")


def _sched_texts(e) -> list[str]:
    return [e.evidence] + [ev[1] for ev in e.events]


def test_the_default_fill_gives_the_old_text():
    n = names_mod.draw(random.Random(5))
    assert n.nodes == 3
    by = {x.key: x for x in catalog.all_entries()}
    texts = [cases._fmt(t, n) for k in _SCHED_ENTRIES for t in _sched_texts(by[k])]
    joined = "\n".join(texts)
    assert "{" not in joined
    assert "0/3 nodes are available" in joined
    assert "3 Preemption is not helpful" in joined
    assert "3 Insufficient memory" in joined
    assert "1 node(s) were unschedulable, 2 node(s) had untolerated taint(s)" in joined


def test_five_nodes_fill_five():
    n = dataclasses.replace(names_mod.draw(random.Random(5)), nodes=5)
    by = {x.key: x for x in catalog.all_entries()}
    joined = "\n".join(cases._fmt(t, n) for k in _SCHED_ENTRIES for t in _sched_texts(by[k]))
    assert "0/3" not in joined
    assert "0/5 nodes are available" in joined
    assert "5 Preemption is not helpful" in joined
    assert "5 Insufficient memory" in joined
    assert "1 node(s) were unschedulable, 4 node(s) had untolerated taint(s)" in joined


# --- test 11: node_total is the header's T -----------------------------------

def test_node_total_is_the_headers_count(monkeypatch):
    real = render.cluster_health
    checked = 0

    def spy(workloads, reads):
        nonlocal checked
        block = real(workloads, reads)
        if block is not None:
            assert block.nodes_total == render.node_total(workloads, reads)
            checked += 1
        return block

    monkeypatch.setattr(render, "cluster_health", spy)
    generate.generate(17, 800)
    assert checked > 0


# --- test 12: IS-22 ----------------------------------------------------------

def test_is22_finds_nothing_on_the_build(build):
    inspected = 0
    for e in _all(build):
        rep = checker.check(e.system, e.user, e.assistant, e.meta)
        assert not [v for v in rep.violations if v.rule == "TXT-IS22"], (e.case, e.group)
        inspected += rep.inspected["TXT-IS22"]
    assert inspected > 0


def test_is22_passes_a_row_with_no_header():
    user = "Workload problems (P2):\n- a/b (Deployment): 0/1 ready\n  0/3 nodes are available"
    assert checker._txt_is22(checker._context("", user, "", None)) == (0, [])


# --- test 12b: every multi scheduler count is the header's -------------------

_HEADER = re.compile(r"— (\d+)/(\d+) nodes Ready\.")
_SCHED = re.compile(r"\b0/(\d+) nodes are available")


def test_every_multi_scheduler_count_is_the_headers(build):
    checked = 0
    for e in _all(build):
        if e.case != "multi":
            continue
        h = _HEADER.search(e.user)
        if not h:
            continue
        for m in _SCHED.finditer(e.user):
            checked += 1
            assert m.group(1) == h.group(2), e.group
    assert checked > 0
```

Checked while writing this plan: the three keys are the entries that hold
the texts (`entries_kinds.py:375`, `entries_slugs.py:91` and `:274`);
`catalog.all_entries()` covers both files; `checker.Report` has
`violations` (items with `.rule`) and `inspected` (a dict by rule);
`checker._context(system, user, assistant, meta)` builds the context (:483).

In `tests/test_checker.py`, add to `BROKEN` after `"TXT-IS17"`:

```python
    "TXT-IS22": (None, _replace("(0/4 nodes are available: pod has unbound",
                                "(0/3 nodes are available: pod has unbound")),
```

Change the rule count at :289 to 51, with a comment line above it:
`# 2026-10-05 (Spec 4b-3): TXT-IS22 checks every scheduler node count against the header 50 -> 51`.
Change the count at :858 to 51.

- [ ] **Step 2: Run them and see them fail**

Run: `PYTEST tests/test_multi_decoys.py -k "fill or node_total or is22 or scheduler_count" tests/test_checker.py -k "broken or every_rule or exemption"`
Expected: FAIL (`Names` has no `nodes`; `render` has no `node_total`;
`checker` has no `_txt_is22`; the 0/3 vs header mismatch in `multi`).

- [ ] **Step 3: Write the code**

`names.py`, last field of `Names`:

```python
    nodes: int = 3
```

`cases._fmt`:

```python
def _fmt(tpl: str, n: Names) -> str:
    return tpl.format(ns=n.ns, name=n.name, pod=n.pod, container=n.container,
                      init_container=n.init_container, image=n.image, node=n.node,
                      pvc=n.pvc, restarts=n.restarts, nodes=n.nodes,
                      other_nodes=n.nodes - 1)
```

Catalog texts (each place, both copies in each text):
- `0/3 nodes are available` → `0/{nodes} nodes are available`
- `3 Preemption is not helpful` → `{nodes} Preemption is not helpful`
- `3 Insufficient memory` → `{nodes} Insufficient memory`
- `2 node(s) had untolerated` → `{other_nodes} node(s) had untolerated`

`catalog.py:28-29`: add `{nodes}` (the cluster's node count) and
`{other_nodes}` (`nodes` minus 1) to the placeholder comment.

`render.py`: pull the count out of `cluster_health`, add `"node_total"` to
`__all__` (keep it sorted), and have `cluster_health` use the helpers:

```python
def _node_reasons(workloads: tuple[c.Workload, ...]) -> dict[str, set[str]]:
    """Every node candidate's name and its reasons."""
    reasons: dict[str, set[str]] = {}
    for w in workloads:
        for cand in w.candidates:
            m = _NODE_CAUSE.match(cand.cause)
            if m:
                reasons.setdefault(m.group(1), set()).add(m.group(2))
    return reasons


def _named_nodes(reasons: dict[str, set[str]], reads: tuple[c.EvidenceRead, ...]) -> set[str]:
    """The nodes the prompt names: node candidates and `describe node /<name>` reads."""
    return set(reasons) | {r.label[len(_DESCRIBE_NODE):] for r in reads
                           if r.label.startswith(_DESCRIBE_NODE)}


def node_total(workloads: tuple[c.Workload, ...], reads: tuple[c.EvidenceRead, ...]) -> int:
    """The cluster-health header's node count T = max(3, named nodes + 1)
    (see `cluster_health`)."""
    return max(_MIN_NODES, len(_named_nodes(_node_reasons(workloads), reads)) + 1)
```

In `cluster_health`, replace the `reasons` loop and `named = …` with
`reasons = _node_reasons(workloads)` and `named = _named_nodes(reasons, reads)`,
and `total = …` with `total = node_total(workloads, reads)`. The rest stays.

`cases.multi`: put the build of workloads and gather into a helper and run
it once or twice. Keep `combined_objects = _multi_objects(pairs, rng)`
before it; never call `_multi_objects` again.

```python
def _multi_build(pairs: list[tuple[CatalogEntry, Names]], combined_objects: list[tuple]):
    """The gather and the workloads for one `multi` row. Draws no randomness."""
    res = gather.gather([gather_workload(e, n, objects)
                         for (e, n), objects in zip(pairs, combined_objects)])
    workloads = [_workload(e, n, candidates, render.header_for(candidates), result=result)
                 for (e, n), candidates, result in zip(pairs, res.candidates, res.results)]
    return res, workloads
```

In `multi`, after `combined_objects = …`:

```python
    res, workloads = _multi_build(pairs, combined_objects)
    total = render.node_total(tuple(workloads), res.reads)
    if total != 3:
        # The scheduler counts every node the header counts (Spec 4b-3 §5).
        # The second build reuses the drawn objects and draws nothing, so
        # only the scheduler numbers change.
        pairs = [(e, dataclasses.replace(n, nodes=total)) for e, n in pairs]
        res, workloads = _multi_build(pairs, combined_objects)
        again = render.node_total(tuple(workloads), res.reads)
        if again != total:
            raise RuntimeError(f"multi: the node count moved from {total} to {again} on rebuild")
```

Then the loop that fills `decoy_by_workload` iterates over
`zip(pairs, res.candidates, res.results)` only (the `workloads` list is
already built). Everything after it uses `pairs`, `res` and `workloads` as
before. `group` uses `n.ns`/`n.name`, which the replace does not change.

`checker.py`: add after `_txt_is17`:

```python
_SCHED_TOTAL = re.compile(r"\b0/(\d+) nodes are available")


def _txt_is22(x: _Ctx) -> tuple[int, _Finding]:
    """Every scheduler message counts the nodes the cluster-health header
    counts. kubeagent's header T is the node list's length
    (clusterhealth/clusterhealth.go:60-110), and the scheduler's `0/N nodes
    are available` counts the same nodes. IS-22 was a `multi` row whose header
    said 4 nodes and whose FailedScheduling event said 0/3. A row with no
    header shows no total and is not checked. The builder's model, not a
    kubeagent string: the rule checks that the row agrees with itself."""
    if not x.p.health:
        return 0, []
    m = _HEALTH_HEADER.match(x.p.health[0].text)
    if not m:
        return 0, []
    total = m.group(2)
    out: _Finding = []
    n = 0
    for ln in x.p.inv:
        for s in _SCHED_TOTAL.finditer(ln.text):
            n += 1
            if s.group(1) != total:
                out.append((f"inventory line {ln.no}", ln.text))
    for r in x.p.reads:
        for text in _content_lines(r):
            for s in _SCHED_TOTAL.finditer(text):
                n += 1
                if s.group(1) != total:
                    out.append((r.where, text))
    return n, out
```

Register `"TXT-IS22": _txt_is22,` in `_RULE_FUNCS` right after
`"TXT-IS17": _txt_is17,`. Change "all 50 rules" in the module docstring to
"all 51 rules". Add a short line to the docstring's model-rules paragraph:
"TXT-IS22 is another: it checks that the scheduler's node count agrees with
the header the builder drew."

`tests/test_shared_origin_pool.py:241-262`: run its rule-list test, see
which side TXT-IS22 lands on (inspects something on the family rows, or
nothing), and add it to `INSPECTS` or `INSPECTS_NONE` by that measurement.
Change "every one of the 50 rules" to 51 in the docstring.

- [ ] **Step 4: Run the new tests, then the full suite and ruff**

Run the Step 2 command → all pass. Run `PYTEST tests/test_multi_decoys.py`
→ all pass (test 13 proves no non-`multi` prompt moved; test 7 proves the
probe did not). Run `PYTEST` and ruff → all pass. Re-pin rules as in
Task 3 Step 5.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/entries_kinds.py src/kubeagent_verdict/dataset/entries_slugs.py src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/names.py src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/render.py src/kubeagent_verdict/dataset/checker.py tests/test_checker.py tests/test_shared_origin_pool.py tests/test_multi_decoys.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(dataset): scheduler node counts agree with the header; checker IS-22"
```

---

### Task 6: Build, gates and measurements

**Files:**
- Create (not committed): `out/dataset-1005/`
- Create: scratch measurement notes in the task report (numbers go into PIN.md in Task 7)

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: `out/dataset-1005/{train,val,test}.jsonl` and `manifest.json`; the numbers Task 7 writes down.

- [ ] **Step 1: Build**

```bash
cd /home/ubuntu/git/kubeagent-verdict && test ! -e out/dataset-1005 && env -u ALL_PROXY -u all_proxy PYTHONPATH=src .venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-1005
```

Expected rows: train 6439, val 739, test 249 (`wc -l out/dataset-1005/*.jsonl`).

- [ ] **Step 2: Gates**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -c "import json; v=json.load(open('out/dataset-1005/manifest.json'))['checker_violations']; print(v); assert not any(v.values())"
cd /home/ubuntu/git/kubeagent-verdict && cmp out/dataset-1004-4b2/test.jsonl out/dataset-1005/test.jsonl && echo EXAM-IDENTICAL
```

Then `PYTEST` (full) and ruff. Expected: 0 violations, EXAM-IDENTICAL,
suite green, `All checks passed!`. If `test.jsonl` differs, stop and
report BLOCKED with the first differing line's case.

- [ ] **Step 3: Measure**

Write the script to the scratchpad (not the repo) and run it. It compares
`out/dataset-1004-4b2` with `out/dataset-1005` per split and prints:

- `multi` rows whose user message moved, whose answer moved, and both, per split;
- `multi` rows with a `none_of_these` verdict share (verdicts that are `none_of_these` / all `multi` verdicts), before and after;
- the `multi` label mix (`meta["label"]` counts), before and after;
- D4: workloads in any case whose normalized gold is in their own decoy list (expect 0);
- node mismatches: rows with a header whose `0/N nodes are available` has N ≠ T (expect 0), before and after;
- whether `test.jsonl` is byte-identical;
- IS-22's inspected count (`manifest.json` if it records it, else from the checker over the build).

```python
import json, re, sys
from pathlib import Path
sys.path.insert(0, "src")
from kubeagent_verdict.dataset import gold

OLD, NEW = Path("out/dataset-1004-4b2"), Path("out/dataset-1005")
H = re.compile(r"— (\d+)/(\d+) nodes Ready\."); S = re.compile(r"\b0/(\d+) nodes are available")

def rows(d, s): return [json.loads(x) for x in (d / f"{s}.jsonl").read_text().splitlines() if x.strip()]

def mismatches(rs):
    n = 0
    for r in rs:
        u = r["messages"][1]["content"]; h = H.search(u)
        n += bool(h and any(m.group(1) != h.group(2) for m in S.finditer(u)))
    return n

for s in ("train", "val", "test"):
    o, n = rows(OLD, s), rows(NEW, s)
    assert len(o) == len(n), s
    pm = am = both = 0
    for a, b in zip(o, n):
        if b["meta"]["case"] != "multi": continue
        p = a["messages"][1] != b["messages"][1]; q = a["messages"][2] != b["messages"][2]
        pm += p; am += q; both += p and q
    print(s, "multi prompt moved", pm, "answer moved", am, "both", both,
          "mismatch before", mismatches(o), "after", mismatches(n))
    for name, rs in (("before", o), ("after", n)):
        m = [r for r in rs if r["meta"]["case"] == "multi"]
        v = [x for r in m for x in json.loads(r["messages"][2]["content"])["verdicts"]]
        none = sum(x["cause"] == "none_of_these" for x in v)
        labels = {}
        for r in m: labels[r["meta"]["label"]] = labels.get(r["meta"]["label"], 0) + 1
        print(" ", name, "multi rows", len(m), "none_of_these", f"{none}/{len(v)}", "labels", labels)
    d4 = 0
    for r in n:
        dec = r["meta"].get("decoy_by_workload") or {}
        for k, w in (r["meta"].get("workloads") or {}).items():
            g = w.get("expected_cause") or ""
            if g and g != "none_of_these" and gold._norm_cause(g) in {gold._norm_cause(x) for x in dec.get(k) or []}:
                d4 += 1
    print(" ", "D4 own-gold decoys", d4)
print("exam identical", (OLD / "test.jsonl").read_bytes() == (NEW / "test.jsonl").read_bytes())
```

Run it with `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src .venv/bin/python <scratch>/measure.py`.
Put every number in the report. Expected: D4 0, mismatches after 0, exam
identical True; prompt moves near 244 + 172 minus their overlap.

- [ ] **Step 4: Re-pin only if needed**

If the full suite was green in Step 2, there is nothing to re-pin. Do not
commit `out/`. No commit in this task unless a re-pin was needed; then
commit only the test file, with a `2026-10-05 (Spec 4b-3)` comment next to
each new value:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add <the re-pinned test file> && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "test: re-pin for the 4b-3 build"
```

---

### Task 7: Docs

**Files:**
- Modify: `contract/PIN.md` (:182 section, D4 items at :654 and :767, a new 2026-10-05 entry after about :799, the "Left for 4b-2, 4b-3 and 4b-4" list at about :899-905)
- Modify: `docs/model-card.md:1102-1106`
- Modify: `docs/design.md:418-422`
- Modify: `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md:738-741`

**Interfaces:**
- Consumes: Task 6's numbers (from its report).
- Produces: docs only.

- [ ] **Step 1: PIN.md**

Read each place first. Then, in simple voice:

- `:182` section (it describes `multi`'s healthy-origin read or the
  `origin_read_label` exemption): say that as of 2026-10-05 (Spec 4b-3)
  `multi` shows only reads kubeagent's gather makes, and the checker has no
  exemption.
- D4 items at `:654` and `:767`: mark them done on 2026-10-05: every
  `multi` decoy list is `gold.excluded_from(...)`, and
  `tests/test_multi_decoys.py` checks that no workload in any case lists
  its own gold. Widening the decoy gate to job 1 is left for 4b-4.
- A new `### 2026-10-05 — Spec 4b-3: multi rows and decoys` entry after
  the 4b-2 entry (about :799), with Task 6's numbers: build folder
  `out/dataset-1005`; row counts; `multi` prompts and answers moved per
  split; the 77 4b-1 answers that now name every workload; the
  `none_of_these` share and label mix before and after; D4 = 0; node
  mismatches before and after (after = 0); checker 51 rules, 0
  violations; `test.jsonl` byte-identical, so no exam hash moved; any
  re-pin with its old and new value.
- The "Left for 4b-2, 4b-3 and 4b-4" list (about :899-905): mark 4b-3's
  items done. Record the container-name clash as **closed, no change**:
  96 of 738 `multi` rows have it, and it is what kubeagent does too
  (`internal/investigate/gather.go:146`); see the spec's §6. Name what is
  still open for 4b-4: the 4+-letter kit-key guard, widening the decoy
  gate to job 1, and IS-22's sum half (it fails on 4b-1 stories, exam rows
  included, so it waits for the exam rebuild).

- [ ] **Step 2: model card, design.md, 4b-1 spec**

- `docs/model-card.md:1102-1106` and `docs/design.md:418-422` say "Spec
  4b-3 owns `multi`". Replace that with what `multi` is now, in 2-4 short
  sentences: no healthy-origin read; decoy lists are the causes the prompt
  rules out; the summary says "separate reasons" only when the rows show
  it, and names every workload; scheduler node counts match the header.
- `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md:738-741`:
  under 4b-3 in its left-for list, add
  `Done 2026-10-05: see docs/superpowers/specs/2026-10-05-multi-decoys-design.md.`

- [ ] **Step 3: Check and commit**

Grep the four files for the training host's name and for any leftover
"4b-3 owns" text: `grep -n "4b-3 owns" contract/PIN.md docs/model-card.md docs/design.md`
(expect nothing). Run the full suite once more (some tests read PIN.md or
docs): `PYTEST` → green.

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add contract/PIN.md docs/model-card.md docs/design.md docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "docs: record Spec 4b-3 (multi rows and decoys)"
```

---

## Notes for the controller

- Where this plan departs from the spec, and why:
  - IS-22 has only its first half (the spec's amendment of 2026-10-05).
  - 77 4b-1 rows with 4 or more workloads move (spec §3, amended).
  - The two share tests go to `== 0.5` (spec test 14).
  - Spec test 11 compares with `out/dataset-1004-4b2`; this plan checks
    `node_total` against `cluster_health` live over `generate(17, 800)`
    instead, and test 13 proves no non-`multi` prompt moved. Together they
    say the same thing without reparsing old headers.
  - `test_shared_origin_pool.py`'s rule lists gain TXT-IS22.
  - The separate-reasons test rewrite is in Task 2, not Task 4: Task 2's
    summary change is what breaks it.
  - `test_catalog_gold.py`'s dataset-1004 byte test skips `multi` rows.
  - `GATED_POOL` and `tests/test_oracle.py` pins may need a hand re-pin
    in Tasks 3-5; the rates stay 1.0, and an exam pin moving stops the run.
