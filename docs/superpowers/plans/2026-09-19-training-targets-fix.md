# Training Targets Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every gold answer in the training data agree with kubeagent v1.24.0's own rules, and prove it with oracle gates, before the next ~33-hour retrain.

**Architecture:** Two row builders stop overwriting the rules' decided cause (`cases.multi`, `cases._render_shared_origin`), and the shared-origin summary follows the label the rules computed. Six new "ruled" stories give the rules an origin object to check, so training finally carries `shared`-labelled rows; one node pair in three shows the rules unable to check. A new case mix keeps every plain story above its floor, and oracle tests score each row's own gold answer as if a model wrote it.

**Tech Stack:** Python 3.12, `dataclasses`, `pytest`, `ruff`; the Qwen3-0.6B tokenizer from the local Hugging Face cache for the length gate only.

**Spec:** `docs/superpowers/specs/2026-09-19-training-targets-fix-design.md`

## Global Constraints

- **kubeagent is not changed.** `/home/ubuntu/git/kubeagent` is read-only.
- **Work on branch `fix-training-targets`** (off `main` @ `abdc0be`).
  Never commit on `main`.
- **These do not change:** `evals/score.py`, the three job bars, the five
  deciders, `contract/system_prompt.txt`, the prompt renderer and
  `contract/golden/`.
- **The training recipe does not change:** base model, LoRA settings,
  2 epochs, batch 16, seed 17, size 8000, CPU on the training host.
- **`split`, `drop_held_out` and every group string do not change.**
- **The 48 plain stories' text and every catalog entry's text do not
  change.** Confidence in every gold row stays as the catalog declares it.
- **The exam's prompts do not change.** 14 exam rows change their gold
  answer and the meta that mirrors it, in Task 5 only. The graded-view
  hash never changes.
- **No training, no export in this plan.** `kv-train` and `kv-export` are
  not run. Nothing writes under `dist/`. The run is spec §11, after this
  plan.
- **Tests:** `.venv/bin/python -m pytest -q`. Lint: `.venv/bin/ruff check .`.
  Both green before every commit. Clear `__pycache__` first and set
  `PYTHONDONTWRITEBYTECODE=1`.
- **TDD.** The failing test first, then the code.
- **Commits:** `git add <named files>` (never `-A`), then
  `git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "<msg>"`.
  No `Co-Authored-By`, no AI words, in any message or file. No commit
  message cites a path under `docs/testing/`.
- **Never run a test with `-update`.** Every re-pin is by hand, with a
  dated comment (2026-09-19). If a re-pin step's value differs from the
  plan's expected value, stop and report; do not paste your value in.
- **No real identifier in any tracked file.** Only `worker-1`..`worker-7`,
  `registry.invalid`, `mirror.invalid`, `registry.example.com`,
  `<ADDRESS>` and the names in `names.py`. No personal paths.
- **Simple voice in every doc line.** Short sentences, plain words, the
  decision first, numbers explained.
- **The promise rule.** A comment, doc line, test name or reason string
  that promises what the code does not keep is a defect. Close the gap or
  narrow the claim.
- **`docs/superpowers/specs/` and `plans/` are a frozen dated archive.**
  Do not edit older files there.
- **`kv-eval` is always given `--endpoint`** if it is run at all. No
  `ANTHROPIC_API_KEY`, and no key value is ever printed.

## Working rules for every task

- Repo: `/home/ubuntu/git/kubeagent-verdict`. Start every shell command
  with `cd /home/ubuntu/git/kubeagent-verdict && …`.
- Use `command grep`, not `grep`, in shell steps.
- Never `pkill -f` a pattern that matches your own command.
- Line numbers in this plan are at `b5b3e65` and drift as tasks land.
  Find code by function name.

## File structure

Paths are relative to the repo root. "Create" means a new file.

| File | What it holds | Tasks |
|------|---------------|-------|
| `src/kubeagent_verdict/dataset/cases.py` | The row builders. `_rule_rationale` and `_NOUN` (new), `multi`, `_render_shared_origin`, `shared_origin`, `_shared_origin_row` (new) | 2, 3, 4, 5, 6, 8, 10 |
| `src/kubeagent_verdict/dataset/objects.py` | `validate` accepts a registry story's `{count}` | 6 |
| `src/kubeagent_verdict/dataset/propagation.py` | `_RULED_SCENARIOS`, `ruled_scenarios()` (new), the trainable pool | 7, 9, 10 |
| `src/kubeagent_verdict/dataset/generate.py` | `CASE_MIX` and the shared-origin selection loop | 9 |
| `tests/test_exam_graded_view.py` | Create. Pins the sha256 of the exam view every gated number reads | 1 |
| `tests/test_rule_rationale.py` | Create. `_rule_rationale` and the failed-read message | 2 |
| `tests/test_oracle.py` | Create. Scores each row's own gold answer as if a model wrote it | 3, 5, 9 |
| `tests/test_multi_collision.py` | Create. The healthy-origin read never contradicts a `multi` row | 4, 9 |
| `tests/test_shared_origin_decided.py` | Create. Decided victims and the label-driven summary | 5, 9 |
| `tests/test_ruled_scenarios.py` | Create. The six ruled stories and the unverified node twin | 7, 8, 9 |
| `tests/test_cases.py`, `test_objects.py`, `test_propagation.py`, `test_probe_wide.py`, `test_probe_cousins.py`, `test_shared_origin_decoy_probe.py`, `test_shared_origin_training.py`, `test_shared_origin_training_pair.py`, `test_shared_origin_floor.py`, `test_evidence_overlap.py`, `test_generate.py` | Existing tests whose values or claims move | 3-9 |
| `contract/PIN.md` | A dated "Dataset pin moves" entry for the exam re-pin | 5 |
| `README.md`, `docs/design.md`, `docs/how-training-works.md`, `docs/model-card.md`, `docs/runbooks/train.md` | Doc lines this branch makes false, plus the disclosed limits (spec §12) | 10 |

## Build order

- Run the tasks in order, 1 to 11. Each task starts from the one before.
- Every commit is green on its own: the full suite and ruff pass.
- Task 1 goes first on purpose. It pins the exam view every gated number
  reads before any code moves, so Task 5 can prove that view did not change.
- Task 5 is the only task that changes exam rows (14 of 263). It re-pins
  `FROZEN_253_SHA256` and `EVAL_SET_SHA256` by hand. No later task may
  move either hash.
- Tasks 6 to 8 build the six ruled stories and the unverified node twin.
  They do not enter training until Task 9 merges them into the pool.
- Tasks 9 and 10 have two commits each. Every other task has one.
- Task 11 runs gates and writes no tracked file. Gate 7 is a hand read by
  a person, and it comes before any training.

---

### Task 1: the graded-view pin

**Spec:** §9 "The exam: what moves and how it is pinned"

**Files:**
- New: `tests/test_exam_graded_view.py`

**Interfaces:**
- Consumes: `generate.test_set()`, `generate.to_row(ex)` (existing).
- Produces: `view(row)` and `GRADED_VIEW_SHA256`, both local to this test
  file. Task 5's footprint check reads this file's `view` function and
  pin by name; no other task imports from it.

This task is a pin, not a TDD red test. `view(row)` reduces a row to
what every gated number reads: the system and user messages, the
workload names in the gold JSON's `verdicts` list, and each workload's
meta minus the gold cause string (kept only as one boolean,
`expects_none_of_these`, since that is the only thing about the cause
job 2 branches on). Hashing that view over the whole exam gives a number
that must not move when a later task changes 14 rows' gold *cause* —
proving the change touched nothing a gated number reads. The ungated
extras (cause accuracy, confidence carried, overconfidence and the
length gap) also read the gold answer's cause or confidence, which the
view drops, so they may move while this pin holds.

- [ ] **Step 1: Write the test file**

```python
"""Pins the "graded view" of the exam: what every gated number reads.

The gated numbers -- the three job bars, contract validity, decoy rate
and suggestion echo -- never see a whole row. They see the system and
user messages, which workloads the gold JSON's `verdicts` list flags,
and the per-workload meta fields job 1 and job 2 grade. `view(row)`
reduces a row to that shape. It drops `meta["expected"]` and each
workload's `expected_cause` string -- a model never sees either -- and
keeps one boolean instead, `expects_none_of_these`, the only fact about
`expected_cause` job 2 switches on (exact match vs. keyword match).
The ungated extras -- cause accuracy, confidence carried, overconfidence
and the length gap -- also read the gold answer's cause or confidence,
which this view drops, so they can move while this pin holds.

`GRADED_VIEW_SHA256` pins the sha256 of that view over the whole exam
(`generate.test_set()`, 263 rows). This is not a TDD red test: it
passes today, before the training-targets fix, because the fix only
ever touches the gold answer, never anything this view keeps.
The 14-row exam move in a later task must leave this hash unchanged --
that is the whole point of pinning it here first.
"""

from __future__ import annotations

import hashlib
import json

from kubeagent_verdict.dataset import generate

NONE = "none_of_these"


def view(row):
    meta = dict(row["meta"])
    meta.pop("expected", None)
    ws = {}
    for k, w in meta["workloads"].items():
        d = {f: v for f, v in w.items() if f != "expected_cause"}
        d["expects_none_of_these"] = w.get("expected_cause") == NONE
        ws[k] = d
    meta["workloads"] = ws
    gold = json.loads(row["messages"][2]["content"])
    return {"messages": row["messages"][:2], "meta": meta,
            "flagged": [v["workload"] for v in gold["verdicts"]]}


GRADED_VIEW_SHA256 = "cac6361b0bab69956d386a9d77193b82c14957014430f95bfbbd45008ae309d2"


def _digest(views) -> str:
    blob = json.dumps(views, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _views() -> list[dict]:
    rows = [generate.to_row(e) for e in generate.test_set()]
    return [view(r) for r in rows]


def test_graded_view_is_pinned():
    assert _digest(_views()) == GRADED_VIEW_SHA256, (
        "the graded view moved; something a gated number reads changed")


def test_graded_view_notices_a_changed_flagged_workload():
    """The pin above is only useful if `view()` is sensitive to changes.

    Drop one workload from the first exam row's `flagged` list -- the
    field job 1 and job 3 both key off -- and check the digest moves.
    If it did not, the pin above would pass no matter what changed.
    """
    views = _views()
    before = _digest(views)
    mutated = json.loads(json.dumps(views[0]))  # deep copy, first row's view
    assert mutated["flagged"], "the first exam row has no flagged workload to mutate"
    mutated["flagged"] = mutated["flagged"][1:]
    views[0] = mutated
    after = _digest(views)
    assert after != before
    assert before == GRADED_VIEW_SHA256
```

- [ ] **Step 2: Run it — it passes immediately (a pin, not a red test)**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_exam_graded_view.py -q`
Expected: `2 passed in 0.13s`. `test_graded_view_is_pinned` passes because the
fix in later tasks never changes what `view()` keeps. What proves the pin
is not a rubber stamp is `test_graded_view_notices_a_changed_flagged_workload`:
it mutates one row's `flagged` list and checks the digest moves — that
one is the closest thing this task has to a red/green step, and it
already passes here because the mutation and the assertion are written
together.

- [ ] **Step 3: (no implementation step — this task adds only the test file)**

Nothing in `src/` changes for this task. `view()` and
`GRADED_VIEW_SHA256` live only in the test file above.

- [ ] **Step 4: Run the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: `653 passed, 6 warnings` (baseline 651 plus this file's 2); ruff
`All checks passed!`. The 6 warnings are pre-existing `peft` checkpoint
warnings, unrelated to this change.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_exam_graded_view.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "test(eval): pin the exam view every gated number reads"
```

### Task 2: `_rule_rationale` and the failed-read message rule

**Spec:** §1 "The multi fix"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py`
- New: `tests/test_rule_rationale.py`

**Interfaces:**
- Consumes: `rules.Result`, `rules.attribute`/`rules.decide` (existing),
  `objects.Object`/`objects.Fresh`/`objects.unverify` (existing),
  `render.workload_meta` (existing), `score.job1`,
  `score._word_bounded_signal`, `score.DENIAL_PHRASES`,
  `score.OVERCLAIM_WORDS` (existing).
- Produces: `cases._NOUN` and `cases._rule_rationale(result: rules.Result)
  -> str`. Task 3's `multi()` fix and Task 5's `_render_shared_origin()`
  fix both call `_rule_rationale` for a decided row's rationale.

A rule row's cause must come straight from `rules.decide`, never a
hand-written string, so its rationale has to agree with the same
evidence the rules found. `_rule_rationale` builds that rationale out
of `result.evidence` itself, so the two can never drift apart. This
task adds the function and proves two things about it: every reachable
decided branch of `_check_node`/`_check_pvc`/`_check_registry` produces
a rationale job 1 accepts, and every valid `objects.unverify(kind,
how)` ending's evidence holds no denial phrase and no overclaim word —
the authoring rule the spec calls out by name, checked with `score`'s
own phrase lists and its own word-boundary matcher, never a copy of
either.

- [ ] **Step 1: Write the failing test file**

```python
"""`cases._rule_rationale` builds a rule row's rationale from the rules'
own evidence sentence, so it can never disagree with the fresh read it
describes.

Two things are checked here:

1. Every REACHABLE confirmed/unverified branch of `rules._check_node`,
   `rules._check_pvc` and `rules._check_registry` -- built from real
   `objects.Object`s, decided with the real `rules.attribute`/`decide`
   pair -- produces a rationale that `score.job1` accepts. A branch
   `rules.py` itself marks unreachable (its one `# pragma: no cover`
   default, closed by a validated `Object`) is not in this list.
2. Every valid `objects.unverify(kind, how)` ending -- the six
   (kind, how) pairs `objects.unverify` accepts -- produces evidence
   that holds no denial phrase and no overclaim word, checked with
   `score`'s own phrase lists and its own word-boundary matcher
   (`score._word_bounded_signal`), never a copy of either. This is the
   authoring rule the spec calls out by name: a failed-read message
   must not accidentally deny the very kind of object it is reporting
   on, or claim the read was verified when it was not.
"""

from __future__ import annotations

import pytest

from kubeagent_verdict.dataset import cases, render, rules
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.evals import score

# ---------------------------------------------------------- branch fixtures

_NODE = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                 placement="on", fresh=o.Fresh(how="read", ready="False"), intent="cause")
_PVC = o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
                placement="mounted", fresh=o.Fresh(how="read", phase="Pending"), intent="cause")
_REGISTRY = o.Object(kind="registry", name="registry.example.com", scan_reason="2",
                     placement="", fresh=o.Fresh(how="read", literal="dial tcp"), intent="cause")


def _decide(obj: o.Object, *, issue: str = "CrashLoopBackOff") -> rules.Result:
    candidates = rules.attribute((obj,), ns="payments", pod="worker-0", issue=issue)
    return rules.decide(candidates)


# (id, Result-producing object, issue) -- one entry per reachable branch.
NODE_BRANCHES = [
    ("node-confirmed-missing",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="missing"), intent="cause")),
    ("node-confirmed-false",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="False"), intent="cause")),
    ("node-confirmed-unknown",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="Unknown"), intent="cause")),
    ("node-unverified-read-failed", o.unverify(_NODE, "read_failed")),
    ("node-unverified-not-read",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="not_read"), intent="cause")),
    ("node-unverified-lease", o.unverify(_NODE, "lease")),
]

PVC_BRANCHES = [
    ("pvc-confirmed-pending",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Pending"), intent="cause")),
    ("pvc-confirmed-lost",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Lost"), intent="cause")),
    ("pvc-unverified-read-failed", o.unverify(_PVC, "read_failed")),
    ("pvc-unverified-not-read",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="not_read"), intent="cause")),
    ("pvc-unverified-unexpected-phase",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Released"), intent="cause")),
]

REGISTRY_BRANCHES = [
    ("registry-confirmed-connection",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", literal="dial tcp"), intent="cause")),
    ("registry-unverified-read-failed", o.unverify(_REGISTRY, "read_failed")),
    ("registry-unverified-not-read",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="not_read"), intent="cause")),
    ("registry-unverified-wrong-pod",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", wrong_pod=True, literal=""), intent="cause")),
    ("registry-unverified-no-literal",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", literal=""), intent="cause")),
    ("registry-unverified-auth", o.unverify(_REGISTRY, "auth")),
]

ALL_BRANCHES = (
    [(i, obj, "CrashLoopBackOff") for i, obj in NODE_BRANCHES]
    + [(i, obj, "CrashLoopBackOff") for i, obj in PVC_BRANCHES]
    + [(i, obj, "ImagePullBackOff") for i, obj in REGISTRY_BRANCHES]
)


@pytest.mark.parametrize("case_id,obj,issue", ALL_BRANCHES, ids=[c[0] for c in ALL_BRANCHES])
def test_rule_rationale_passes_job1_on_every_reachable_branch(case_id, obj, issue):
    result = _decide(obj, issue=issue)
    assert result.decided, case_id
    rationale = cases._rule_rationale(result)
    meta = render.workload_meta(result, expected_cause=result.cause, own_cause_keywords=[])
    reply_row = {"cause": result.cause, "rationale": rationale}
    assert score.job1(meta, reply_row) == 1.0, (case_id, rationale)


# --------------------------------------------------- objects.unverify authoring rule

# Every valid (kind, how) pair `objects.unverify` accepts, built from a
# minimal starting object of that kind. `_decide` re-checks it exactly the
# way a rule row would, so the evidence text is the same text
# `_rule_rationale` would embed.
UNVERIFY_CASES = [
    ("node/read_failed", _NODE, "read_failed", "CrashLoopBackOff"),
    ("node/lease", _NODE, "lease", "CrashLoopBackOff"),
    ("pvc/read_failed", _PVC, "read_failed", "CrashLoopBackOff"),
    ("registry/read_failed", _REGISTRY, "read_failed", "ImagePullBackOff"),
    ("registry/auth", _REGISTRY, "auth", "ImagePullBackOff"),
    ("registry/no_event", _REGISTRY, "no_event", "ImagePullBackOff"),
]


@pytest.mark.parametrize("case_id,base,how,issue", UNVERIFY_CASES,
                         ids=[c[0] for c in UNVERIFY_CASES])
def test_every_valid_unverify_message_holds_no_denial_or_overclaim_phrase(
        case_id, base, how, issue):
    ended = o.unverify(base, how)
    result = _decide(ended, issue=issue)
    assert result.decided and result.outcome == "unverified", case_id
    kind = ended.kind
    assert not score._word_bounded_signal(result.evidence, score.DENIAL_PHRASES.get(kind, ())), (
        case_id, result.evidence)
    assert not score._word_bounded_signal(result.evidence, score.OVERCLAIM_WORDS), (
        case_id, result.evidence)
```

- [ ] **Step 2: Run it — watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_rule_rationale.py -q`
Expected: `17 failed, 6 passed in 0.15s`. The 6 passes are the
`objects.unverify`-authoring-rule tests, which do not touch
`_rule_rationale`. Every one of the 17 failures is the same error:

```
AttributeError: module 'kubeagent_verdict.dataset.cases' has no attribute '_rule_rationale'
```

- [ ] **Step 3: Add `_NOUN` and `_rule_rationale` to `cases.py`**

Insert right after `_fmt` (before `_suggestion`):

```python
# before
def _fmt(tpl: str, n: Names) -> str:
    return tpl.format(ns=n.ns, name=n.name, pod=n.pod, container=n.container,
                      init_container=n.init_container, image=n.image, node=n.node,
                      pvc=n.pvc, restarts=n.restarts)


def _suggestion(issue: str, n: Names) -> rem.Suggestion:

# after
def _fmt(tpl: str, n: Names) -> str:
    return tpl.format(ns=n.ns, name=n.name, pod=n.pod, container=n.container,
                      init_container=n.init_container, image=n.image, node=n.node,
                      pvc=n.pvc, restarts=n.restarts)


_NOUN = {"node": "node", "pvc": "claim", "registry": "registry"}


def _rule_rationale(result: rules.Result) -> str:
    """A decided rule row's rationale, built from the rules' own evidence.

    Every rule row's cause comes straight from `rules.decide` (never a
    hand-written string), so the rationale explaining it must agree with
    the same evidence the rules found -- this is what makes that true.
    `result.outcome` is always "confirmed" or "unverified" here:
    `rules.decide` never returns a decided Result with any other outcome.
    """
    kind, name = result.cause.split(" ", 2)[:2]
    noun = _NOUN[kind.lower()]
    evidence = result.evidence[0].lower() + result.evidence[1:]
    if result.outcome == "confirmed":
        return (f"The fresh read of {noun} {name} confirms it: {evidence}, "
                f"so the {noun}'s own state is why the flagged workload is failing.")
    return (f"The fresh read of {noun} {name} did not clear the earlier finding: "
            f"{evidence}, so {name} stays the named cause rather than something "
            f"the read ruled out.")


def _suggestion(issue: str, n: Names) -> rem.Suggestion:
```

`rules` is already imported in `cases.py` (`from kubeagent_verdict.dataset
import render, rules`), so no import changes there. This code is copied
exactly from spec §1.

- [ ] **Step 4: Run the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: `676 passed, 6 warnings` (653 from Task 1 plus this file's 23).
`tests/test_rule_rationale.py` alone: `23 passed in 0.07s`.

Watch for ruff's `I001` on the new test file's import block: a line
mixing a plain name and an `as`-aliased name from the same module (for
example `from kubeagent_verdict.dataset import cases, objects as o,
render, rules`) sorts as un-sorted. Split it into two `from
kubeagent_verdict.dataset import ...` lines, one plain and one for the
aliased import, and ruff passes.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/cases.py tests/test_rule_rationale.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "feat(dataset): build a rule row's rationale from the rules' own evidence"
```

### Task 3: the `multi` gold fix

**Spec:** §1 "The multi fix"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`multi`)
- Modify: `tests/test_cases.py` (`test_multi_derives_job_and_label_from_the_objects`)
- New: `tests/test_oracle.py`

**Interfaces:**
- Consumes: `cases._rule_rationale` (Task 2), `generate.generate`/`split`/
  `drop_held_out`/`test_set`/`to_row` (existing), `score.evaluate`,
  `score.scoreboard`, `score.job2`, `score._is_job2_keyword_graded`,
  `score.NONE_OF_THESE` (existing).
- Produces: no new public names. `multi`'s per-workload gold cause and
  rationale now come from `rules.decide`'s own result when the workload
  decides, rather than the catalog's hand-written `winner_cause`.
  `tests/test_oracle.py`'s two cached build helpers
  (`_train_and_val`/`_train_results`/`_val_results`) are local to that
  file; Task 5 extends the same file and reuses them.

`cases.multi` already ran the real rules on each workload, then threw
the answer away and wrote the catalog entry's `winner_cause` into the
gold row regardless of what the rules found. The fix, per workload: a
**decided** workload's gold cause is `result.cause`, rationale
`_rule_rationale(result)`; an **undecided** workload's gold cause is
`_fmt(e.own_cause, n)`, rationale stays `_fmt(e.rationale, n)`
(unchanged). Everything else in `multi` stays: confidence, the keyword
rule (`own_cause_keywords` empty when the row is decided or the cause
is `none_of_these`, now computed off the fixed `expected_cause`), the
summary, and the healthy-origin read.

The existing test at `tests/test_cases.py:404-425` pinned the bug as a
contract: it asserted `ex.meta["expected"]` equalled the catalog's
`winner_cause` for both workloads. The two node-bearing entries it
draws (`catalog.trainable()`'s first two entries with a node object,
names from `random.Random(1)`/`random.Random(2)`, `cases.multi` seeded
`random.Random(11)`) happen to be the sharpest possible regression
case: multi's foreign-node injection (each pair gains the other pair's
node object, ruled out) still leaves both workloads able to decide, and
here they decide on the OTHER workload's node rather than their own
catalog story -- so before the fix, the gold cause named a completely
different object than the one the rules actually found.

- [ ] **Step 1: Rewrite the test to expect the rules' own decision, and watch it fail**

```python
def test_multi_derives_job_and_label_from_the_objects():
    """R21: multi's job/decided_* meta is derived by running rules.decide over the
    transformed objects, and the row gains 'workloads', 'label', 'decoy_by_workload'.

    These two node-bearing entries decide on a DIFFERENT object than either
    entry's own hand-written `winner_cause`: multi's foreign-node injection
    (each pair gains the other pair's node, ruled out) still leaves both
    workloads' own combined objects able to decide, and here they decide
    on the other workload's node rather than their own catalog story. That
    makes this pair a real regression check, not just a shape check: the
    gold cause and rationale must follow what `rules.decide` actually
    found, never the catalog's `winner_cause`."""
    node_entries = [e for e in catalog.trainable() if any(o.kind == "node" for o in e.objects)]
    assert len(node_entries) >= 2
    e1, e2 = node_entries[0], node_entries[1]
    n1 = names_mod.draw(random.Random(1))
    n2 = names_mod.draw(random.Random(2))

    ex = cases.multi([(e1, n1), (e2, n2)], random.Random(11))

    key1, key2 = f"{n1.ns}/{n1.name}", f"{n2.ns}/{n2.name}"
    assert set(ex.meta["workloads"]) == {key1, key2}
    for meta in ex.meta["workloads"].values():
        assert set(meta) == {
            "job", "decided", "decided_cause", "decided_outcome",
            "decided_evidence", "expected_cause", "own_cause_keywords"}
        assert meta["job"] in (1, 2)
    assert ex.meta["label"] in ("shared", "separate", "none")
    assert set(ex.meta["decoy_by_workload"]) == {key1, key2}

    wm1, wm2 = ex.meta["workloads"][key1], ex.meta["workloads"][key2]
    assert wm1["decided"] and wm2["decided"], "fixture drifted: both rows must decide here"
    # The bug this pins against: the catalog's own winner_cause is NOT what
    # the rules decided for either workload in this exact draw.
    assert wm1["decided_cause"] != cases._fmt(e1.winner_cause, n1)
    assert wm2["decided_cause"] != cases._fmt(e2.winner_cause, n2)
    assert ex.meta["expected"] == {key1: wm1["decided_cause"], key2: wm2["decided_cause"]}

    answer = json.loads(ex.assistant)
    verdicts = {r["workload"]: r for r in answer["verdicts"]}
    for key, wm in ((key1, wm1), (key2, wm2)):
        assert verdicts[key]["cause"] == wm["decided_cause"]
        assert score.job1(wm, verdicts[key]) == 1.0, key
```

Add `from kubeagent_verdict.evals import score` to the file's imports
(alongside the existing `kubeagent_verdict.dataset` imports).

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_cases.py::test_multi_derives_job_and_label_from_the_objects -q`
Expected failure (against the unfixed `multi`):

```
AssertionError: assert {'payments/no...isk pressure'} == {'payments/no...belet lease)'}

Differing items:
{'payments/notifier': 'memory limit too low for the workload'} != {'payments/notifier': 'node worker-1 (no kubelet lease)'}
{'shop/frontend': 'node worker-2 is cordoned and under disk pressure'} != {'shop/frontend': 'node worker-2 (no kubelet lease)'}
```

- [ ] **Step 2: Fix `multi` in `cases.py`**

```python
# before
        workloads.append(workload)
        results.append(result)
        expected_cause = _fmt(e.winner_cause, n)
        all_reads.extend(reads[:2])  # stay under the 8-read budget at 4 workloads
        rows.append({"workload": f"{n.ns}/{n.name}", "cause": expected_cause,
                     "confidence": conf, "rationale": _fmt(e.rationale, n)})

# after
        workloads.append(workload)
        results.append(result)
        if result.decided:
            expected_cause = result.cause
            rationale = _rule_rationale(result)
        else:
            expected_cause = _fmt(e.own_cause, n)
            rationale = _fmt(e.rationale, n)
        all_reads.extend(reads[:2])  # stay under the 8-read budget at 4 workloads
        rows.append({"workload": f"{n.ns}/{n.name}", "cause": expected_cause,
                     "confidence": conf, "rationale": rationale})
```

The `own_cause_keywords` line right below stays exactly as written --
it already reads `result.decided` and `expected_cause`, both correct
now that `expected_cause` is assigned before it in the loop body.

Run the same single test again: `1 passed in 0.11s`.

- [ ] **Step 3: Add the oracle test file**

`tests/test_oracle.py` scores every row against its OWN gold answer, as
if a model wrote it byte for byte -- the oracle read. It builds
train/val once per module (seed 17, size 8000, after `split` and
`drop_held_out`, exactly what `kv-dataset --seed 17 --size 8000` runs)
and caches both the build and the scored results with
`functools.lru_cache`.

```python
"""Oracle gates: score every row against ITS OWN gold answer, as if a
model wrote it byte for byte. On a correct dataset job 1 and the
keyword-graded slice of job 2 read 1.0 wherever the scorer can reach
them -- this is what proves the `multi` fix (Task 3) closed the gap
between the gold cause and what `rules.decide` actually found, across
the whole built dataset rather than the one pair `test_cases.py` pins
by hand.

`generate.generate` + `split` + `drop_held_out` (seed 17, size 8000,
exactly what `kv-dataset --seed 17 --size 8000` runs) plus scoring both
take about a second, so the oracle runs as an ordinary pytest
module. The build and its scored results are cached at module scope --
every test below shares the same train/val split and the same gold-as-
reply results, built once.
"""

from __future__ import annotations

import functools
import json

from kubeagent_verdict.dataset import generate
from kubeagent_verdict.evals import score

SEED = 17
SIZE = 8000


@functools.lru_cache(maxsize=1)
def _train_and_val() -> tuple[list, list]:
    examples = generate.generate(seed=SEED, size=SIZE)
    train, val = generate.split(examples, seed=SEED)
    test = generate.test_set()
    train = generate.drop_held_out(train, test)
    val = generate.drop_held_out(val, test)
    return train, val


def _gold_results(examples: list) -> list[dict]:
    """`score.evaluate`, fed each row's OWN gold assistant content as the
    model's reply -- the oracle read, byte for byte. `evaluate` calls
    `chat_fn` once per row, in order, so a plain iterator over the same
    rows' gold content lines up with no row identity lookup needed.
    """
    rows = [generate.to_row(e) for e in examples]
    gold = iter(r["messages"][2]["content"] for r in rows)
    return score.evaluate(rows, lambda _messages: next(gold))


@functools.lru_cache(maxsize=1)
def _train_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[0]))


@functools.lru_cache(maxsize=1)
def _val_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[1]))


def _job2_gate(examples: list) -> dict:
    """job2 averaged over exactly the population spec section 10 gate 1
    defines: a workload where `score._is_job2_keyword_graded` is true, or
    whose `expected_cause` is `none_of_these` (exact match).

    NOT `scoreboard()`'s own job2 rate: `evaluate` puts every job==2
    workload in `job2_scores`, and `job2` itself scores a keyword-less,
    non-`none_of_these` workload 0.0 whatever the reply says -- that
    workload is out of scope for this gate, not a failure of it.
    """
    hits, total = 0.0, 0
    for ex in examples:
        row = generate.to_row(ex)
        gold = {v["workload"]: v for v in json.loads(row["messages"][2]["content"])["verdicts"]}
        for key, wm in row["meta"]["workloads"].items():
            if wm["job"] != 2:
                continue
            keywords = wm["own_cause_keywords"]
            graded = (score._is_job2_keyword_graded(wm, keywords)
                      or wm["expected_cause"] == score.NONE_OF_THESE)
            if not graded:
                continue
            total += 1
            hits += score.job2(wm, gold.get(key), keywords)
    return {"rate": round(hits / total, 4) if total else None, "n": total}


def _job2_keyword_only(examples: list) -> dict:
    """job2 restricted to `_is_job2_keyword_graded` ALONE, excluding
    `none_of_these` -- the narrower slice spec section 10 gate 1 cites by
    number ("today, on the keyword-graded workloads: 0.9149, 1990 of
    2175 in train"). `_job2_gate` above is the actual gate; this exists
    only to check that one number.
    """
    hits, total = 0.0, 0
    for ex in examples:
        row = generate.to_row(ex)
        gold = {v["workload"]: v for v in json.loads(row["messages"][2]["content"])["verdicts"]}
        for key, wm in row["meta"]["workloads"].items():
            if wm["job"] != 2:
                continue
            keywords = wm["own_cause_keywords"]
            if not score._is_job2_keyword_graded(wm, keywords):
                continue
            total += 1
            hits += score.job2(wm, gold.get(key), keywords)
    return {"rate": round(hits / total, 4) if total else None, "n": total}


def test_oracle_job1_is_perfect_on_train():
    board = score.scoreboard(list(_train_results()))
    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 2570}


def test_oracle_job1_is_perfect_on_val():
    board = score.scoreboard(list(_val_results()))
    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 289}


def test_oracle_job2_gate_is_perfect_on_train():
    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3121}


def test_oracle_job2_gate_is_perfect_on_val():
    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 352}


def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect."""
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2175}


def test_oracle_multi_job1_matches_the_spec_measurement():
    """The exact number spec section 1 cites for the `multi` fix alone:
    every decided `multi` workload passes job1, 996 of 996 in train and
    121 of 121 in val."""
    def multi_job1(results):
        scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
        return sum(scores), len(scores)

    assert multi_job1(_train_results()) == (996.0, 996)
    assert multi_job1(_val_results()) == (121.0, 121)
```

Why job2 needs a hand-rolled gate rather than reading `scoreboard()`'s
own `jobs.job2` rate: `evaluate` puts every job==2 workload into
`job2_scores`, including one with no keywords at all (`job2` scores
that 0.0 unconditionally, whatever the reply says -- out of scope for
this gate, not a failure of it). Read directly, `scoreboard()`'s job2
rate on today's (unfixed) train is 0.9407 over 3121 -- higher than the
0.9149 the spec cites, because that raw rate already averages in 946
`none_of_these` workloads that score near-perfectly today. Gate 1
defines the population as keyword-graded OR `none_of_these`
(`_job2_gate` above, matching that exactly); the narrower keyword-only
slice (`_job2_keyword_only`) is kept as a second test only because the
spec cites that exact number (0.9149, 1990 of 2175) to check against.

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_oracle.py -q`
Expected: `6 passed in 1.34s`.

- [ ] **Step 4: Run the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: `682 passed, 6 warnings` (676 from Task 2 plus this file's 6);
ruff `All checks passed!`.

**Measured** (with the fix applied, seed 17 size 8000, after split and
drop_held_out):

| metric | before | after |
|---|---|---|
| job 1, train (all cases, decided workloads) | 0.6125 (n=2570) | 1.0 (n=2570) |
| job 1, val (all cases, decided workloads) | 0.5813 (n=289) | 1.0 (n=289) |
| job 1, `multi` rows only, train | -- | 996 of 996 |
| job 1, `multi` rows only, val | -- | 121 of 121 |
| job 2, gate population (keyword-graded or `none_of_these`), train | 0.9407 (n=3121) | 1.0 (n=3121) |
| job 2, gate population, val | -- | 1.0 (n=352) |
| job 2, keyword-graded only, train | 0.9149 (1990/2175) | 1.0 (2175/2175) |

The "before" numbers were measured against the state right after Task
2's commit (`git worktree add` at that commit, same build recipe, same
scoring code -- Task 2 never touches `multi`, so this is the same as
measuring at `b5b3e65`), and match the spec's own cited numbers
exactly (0.6125 train job1; 0.9149, 1990 of 2175, train job2
keyword-graded; 996/996 and 121/121 for `multi`-only job1 after the
fix).

job 1 is already 1.0 overall after this task alone -- not just on
`multi` rows -- which answers the brief's caution about shared-origin
rows: today, every `shared_origin*` row's workloads are still job==2
(undecided by construction, pending Task 5's `_render_shared_origin`
fix), so none of them are in job 1's population yet and none can drag
it below 1.0. Task 5 will move some of them into job==1 and must keep
this file's pinned counts (2570/289/3121/352/2175) in step with that
move; this task's numbers describe the dataset as it stands after
Tasks 1-3 only.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/cases.py tests/test_cases.py tests/test_oracle.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "fix(dataset): multi's gold cause and rationale follow what the rules decided"
```

### Task 4: `multi` collision rules

**Spec:** §2 "The `multi` healthy-origin read"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`multi`, ~lines 1154-1231)
- New: `tests/test_multi_collision.py`

**Interfaces:**
- Consumes: `prop.Propagation` (`origin_read`, `healthy_origin_content`,
  `origin_object`), `objects.Object`/`objects.Fresh` (existing),
  `generate.generate` (existing).
- Produces: `cases._WORKER_NAMES`, `cases._is_node_story`,
  `cases._node_clashes`, `cases._multi_healthy_origin_node`,
  `cases._resolve_multi_healthy_origin` -- all module-private, used only
  inside `multi`. No public signature changes; `multi`'s own signature
  and return shape are unchanged, and its meta still gains
  `origin_read_label`/`origin_healthy` only when the healthy read is
  actually shown.

`multi`'s `healthy_origin` branch always named the read against
`pairs[0]`'s own node (`h.node`), even when the row's OWN objects (the
per-workload decoys and the foreign-node injection from `_multi_objects`)
already put a node of that same name on the menu in a bad state -- a
failed read, or a confirmed NotReady/Unknown. Shown together, the row
would show one read saying the node is fine and another saying it is
not. The fix adds two independent collision rules, checked once, right
where the read is built:

- **Node rule.** Only a "node story" -- a healthy-origin scenario whose
  read label or its healthy content still carries the `{node}`
  placeholder -- can clash. The row keeps `h.node` unless some node
  object in the row's combined objects (across every workload, decoys
  included) carries that same name with `fresh.how == "read_failed"` or
  (`fresh.how == "read"` and `fresh.ready != "True"`); it does not clash
  when the object reads Ready `True` (a node the rules refuted, or left
  on a stale lease). On a clash it renames to the first of `worker-1`,
  `worker-2`, `worker-3` that does not itself clash; if all three clash
  too, the read is dropped. No RNG draw either way -- a row with no
  clash never moves the stream, and the rename walks a fixed list.
- **Registry rule.** A healthy-origin story whose `origin_object` is a
  registry is a cluster-wide events read; if the row holds any registry
  object of its own, that read would sit next to a registry candidate's
  own (different) account and contradict it, so the read is dropped
  outright. No trainable story declares a registry `origin_object` yet
  (a later task adds two), so this path is exercised only synthetically
  here.

- [ ] **Step 1: Write the failing tests**

```python
"""`cases.multi`'s prepended healthy-origin read (spec section 2) must
never contradict the row it heads: a node-story read naming a node that
some other object in the row already shows in a bad state, or a
registry-story read sitting next to a registry candidate of its own.

Unit tests build synthetic `Propagation`/`Object`/`Names` values directly,
one per rule branch (keep, rename, drop-all-three, registry-drop). The
build-level test spies on the real per-story decision functions during a
real `generate.generate(seed=17, size=8000)` run, so it exercises the
exact rotation and RNG stream `kv-dataset` runs, not a hand-picked replay.

No story in today's trainable pool declares a registry `origin_object`
(the two ruled registry stories are a later task), so the registry rule
is unit-tested against a synthetic story only; the build-level test
confirms that absence directly against `propagation.trainable_scenarios`
rather than assuming it.
"""

from __future__ import annotations

from kubeagent_verdict.dataset import cases, generate
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import propagation as prop
from kubeagent_verdict.dataset.names import Names

# --------------------------------------------------------------- fixtures


def _names(node: str = "worker-1") -> Names:
    return Names(ns="payments", name="notifier", pod="notifier-0-abc12",
                 container="app", init_container="init-config",
                 image="registry.example.com/payments/notifier:v1.0.0",
                 node=node, pvc="data-0", restarts=3)


def _node_story() -> prop.Propagation:
    return prop.Propagation(
        key="test-node-story", blast_radius="cluster", scope_field="node",
        origin="{node} is not Ready", shared_cause="the node is down",
        shared_reason="reason", distractor_cause="distractor",
        distractor_reason="distractor reason", rationale="rationale template",
        remedy="fix {node}", confidence="high",
        origin_read=("describe node {node}", "broken content for {node}"),
        healthy_origin_content="Conditions:\n  Ready  True  KubeletReady",
        victims=(),
    )


def _registry_story() -> prop.Propagation:
    return prop.Propagation(
        key="test-registry-story", blast_radius="cluster", scope_field=None,
        origin="the registry is unreachable", shared_cause="the registry is down",
        shared_reason="reason", distractor_cause="distractor",
        distractor_reason="distractor reason", rationale="rationale template",
        remedy="restore the registry", confidence="high",
        origin_read=("get_events (cluster-wide, reason=Failed)",
                     "12 pods report the same pull error"),
        healthy_origin_content="pods report unrelated pull errors",
        victims=(),
        origin_object=o.Object(kind="registry", name="registry.example.com",
                               scan_reason="3", placement="",
                               fresh=o.Fresh(how="read", literal="dial tcp"),
                               intent="cause"),
    )


def _node_object(name: str, *, ready: str = "True", how: str = "read") -> o.Object:
    return o.Object(kind="node", name=name, scan_reason="NotReady", placement="on",
                    fresh=o.Fresh(how=how, ready=ready,
                                  message="boom" if how == "read_failed" else ""),
                    intent="decoy")


def _registry_object() -> o.Object:
    return o.Object(kind="registry", name="registry.example.com", scan_reason="1",
                    placement="", fresh=o.Fresh(how="read", literal="manifest unknown"),
                    intent="decoy")


# ------------------------------------------------------------ unit tests


def test_is_node_story_true_when_the_label_names_a_node():
    assert cases._is_node_story(_node_story())


def test_is_node_story_false_for_a_cluster_wide_story():
    assert not cases._is_node_story(_registry_story())


def test_node_clashes_on_a_failed_read():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", how="read_failed"),))


def test_node_clashes_on_ready_false():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", ready="False"),))


def test_node_clashes_on_ready_unknown():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", ready="Unknown"),))


def test_node_does_not_clash_on_ready_true():
    assert not cases._node_clashes("worker-1", (_node_object("worker-1", ready="True"),))


def test_node_does_not_clash_on_a_different_name():
    assert not cases._node_clashes("worker-1", (_node_object("worker-2", ready="False"),))


def test_healthy_origin_node_keeps_the_anchor_with_no_clash():
    assert cases._multi_healthy_origin_node("worker-1", ()) == "worker-1"


def test_healthy_origin_node_renames_to_the_first_free_worker_on_a_clash():
    all_objects = (_node_object("worker-1", ready="False"),)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-2"


def test_healthy_origin_node_skips_a_second_clashing_worker_too():
    all_objects = (_node_object("worker-1", how="read_failed"),
                   _node_object("worker-2", ready="Unknown"))
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-3"


def test_healthy_origin_node_drops_when_all_three_workers_clash():
    all_objects = tuple(_node_object(w, ready="False") for w in cases._WORKER_NAMES)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) is None


def test_healthy_origin_node_ignores_a_stale_lease_state():
    # A node the rules refuted or left on a stale lease still reads Ready
    # True -- section 2's own example of a non-clash.
    all_objects = (_node_object("worker-1", ready="True"),)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-1"


def test_resolve_keeps_the_anchor_node_with_no_clash():
    story = _node_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, ())
    assert result == ("describe node worker-1", "Conditions:\n  Ready  True  KubeletReady")


def test_resolve_renames_on_a_clash():
    story = _node_story()
    h = _names(node="worker-1")
    all_objects = (_node_object("worker-1", ready="False"),)
    result = cases._resolve_multi_healthy_origin(story, h, all_objects)
    assert result == ("describe node worker-2", "Conditions:\n  Ready  True  KubeletReady")


def test_resolve_drops_the_read_when_all_three_workers_clash():
    story = _node_story()
    h = _names(node="worker-1")
    all_objects = tuple(_node_object(w, ready="False") for w in cases._WORKER_NAMES)
    assert cases._resolve_multi_healthy_origin(story, h, all_objects) is None


def test_resolve_keeps_a_non_node_story_regardless_of_node_objects():
    story = _registry_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, (_node_object("worker-1", ready="False"),))
    assert result == ("get_events (cluster-wide, reason=Failed)",
                      "pods report unrelated pull errors")


def test_resolve_drops_a_registry_story_read_when_the_row_holds_a_registry_object():
    story = _registry_story()
    h = _names(node="worker-1")
    assert cases._resolve_multi_healthy_origin(story, h, (_registry_object(),)) is None


def test_resolve_keeps_a_registry_story_read_with_no_registry_object_in_the_row():
    story = _registry_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, (_node_object("worker-1"),))
    assert result is not None


# --------------------------------------------------------- build-level tests


def test_no_trainable_story_declares_a_registry_origin_yet():
    """The registry rule is exercised only synthetically today: no story in
    the trainable pool sets a registry `origin_object` (that is a later
    task's addition), so a build never reaches the registry-drop branch.
    This pins that absence directly rather than assuming it."""
    assert not any(
        s.origin_object is not None and s.origin_object.kind == "registry"
        for s in prop.trainable_scenarios())


def test_no_real_healthy_node_read_names_a_clashing_node(monkeypatch):
    """Spies on the real per-story node decision during the exact
    `kv-dataset --seed 17 --size 8000` build, so this exercises the real
    rotation and RNG stream. A kept or renamed read's chosen name never
    clashes with the row it heads; a dropped read really did have all
    three worker names clashing. Also counts keep/rename/drop for the
    measured footnote.
    """
    calls: list[tuple[str, tuple, str | None]] = []
    original = cases._multi_healthy_origin_node

    def spy(h_node, all_objects):
        result = original(h_node, all_objects)
        calls.append((h_node, all_objects, result))
        return result

    monkeypatch.setattr(cases, "_multi_healthy_origin_node", spy)
    generate.generate(seed=17, size=8000)

    assert calls, "the rotation must reach at least one node story"

    kept = renamed = dropped = 0
    for h_node, all_objects, result in calls:
        if result is None:
            dropped += 1
            assert cases._node_clashes(h_node, all_objects)
            for w in cases._WORKER_NAMES:
                assert cases._node_clashes(w, all_objects)
            continue
        assert not cases._node_clashes(result, all_objects)
        if result == h_node:
            kept += 1
        else:
            renamed += 1

    # Measured over this exact build (seed 17, size 8000): 79 multi rows
    # draw a node-story healthy origin; the rule keeps 41, renames 37 and
    # drops 1.
    assert (len(calls), kept, renamed, dropped) == (79, 41, 37, 1)
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_multi_collision.py -q`
Expected failure: 19 of the 20 tests fail with
`AttributeError: module 'kubeagent_verdict.dataset.cases' has no attribute '_is_node_story'`
(or `_node_clashes`, `_multi_healthy_origin_node`, `_resolve_multi_healthy_origin`,
`_WORKER_NAMES`, depending on which name a given test reaches first);
`test_no_trainable_story_declares_a_registry_origin_yet` passes on its
own, since it touches none of the new names:

```
19 failed, 1 passed in 0.15s
```

- [ ] **Step 2: Add the collision-rule helpers to `cases.py`**

Insert right before `def multi(...)`:

```python
_WORKER_NAMES = ("worker-1", "worker-2", "worker-3")


def _is_node_story(p: prop.Propagation) -> bool:
    """A node story's healthy origin read names a node: its label or its
    healthy-content template still carries the `{node}` placeholder."""
    return "{node}" in p.origin_read[0] or "{node}" in p.healthy_origin_content


def _node_clashes(name: str, objects: tuple) -> bool:
    """True when the row already carries a node object of this name whose
    fresh read failed, or whose Ready condition is not True -- a healthy
    origin read naming it would contradict that object. A node the rules
    refuted or left on a stale lease still reads Ready True, so it does
    not clash."""
    return any(
        obj.kind == "node" and obj.name == name
        and (obj.fresh.how == "read_failed"
             or (obj.fresh.how == "read" and obj.fresh.ready != "True"))
        for obj in objects)


def _multi_healthy_origin_node(h_node: str, all_objects: tuple) -> str | None:
    """The node name a node-story healthy-origin read should use: `h_node`
    itself when it does not clash, else the first of worker-1/2/3 free of
    a clash, else None when all three clash too (the read is dropped).
    No RNG draw: a row without a clash never moves the stream."""
    for candidate in (h_node, *_WORKER_NAMES):
        if not _node_clashes(candidate, all_objects):
            return candidate
    return None


def _resolve_multi_healthy_origin(
        healthy_origin: prop.Propagation, h: Names, all_objects: tuple,
) -> tuple[str, str] | None:
    """The (label, content) for `multi`'s prepended healthy-origin read, or
    None when section 2's collision rules say to drop it entirely.

    Registry rule: the two ruled registry stories' read is a cluster-wide
    events read; showing it next to a registry candidate's own account
    would contradict that candidate, so the read is dropped outright.

    Node rule: see `_multi_healthy_origin_node`.
    """
    if (healthy_origin.origin_object is not None
            and healthy_origin.origin_object.kind == "registry"
            and any(obj.kind == "registry" for obj in all_objects)):
        return None
    node_name = h.node
    if _is_node_story(healthy_origin):
        node_name = _multi_healthy_origin_node(h.node, all_objects)
        if node_name is None:
            return None
    hh = h if node_name == h.node else dataclasses.replace(h, node=node_name)
    return (_fmt(healthy_origin.origin_read[0], hh),
           _fmt(healthy_origin.healthy_origin_content, hh))
```

- [ ] **Step 3: Wire the helpers into `multi`**

```python
# before
    results: list[rules.Result] = []
    if healthy_origin is not None:
        # Formatted against the first workload's names, as the positive case
        # formats against its anchor. A cluster-scoped read names nothing
        # workload-specific; a node- or namespace-scoped one names this row's.
        h = pairs[0][1]
        all_reads.append(c.EvidenceRead(
            label=_fmt(healthy_origin.origin_read[0], h),
            content=_fmt(healthy_origin.healthy_origin_content, h)))

# after
    results: list[rules.Result] = []
    healthy_read: tuple[str, str] | None = None
    if healthy_origin is not None:
        # Formatted against the first workload's names, as the positive case
        # formats against its anchor. A cluster-scoped read names nothing
        # workload-specific; a node- or namespace-scoped one names this row's.
        # The collision rules (section 2) can rename the node or drop the
        # read outright, so the read is resolved against every object the
        # row will carry, not against `h` alone.
        h = pairs[0][1]
        all_objects = tuple(obj for objs in combined_objects for obj in objs)
        healthy_read = _resolve_multi_healthy_origin(healthy_origin, h, all_objects)
        if healthy_read is not None:
            all_reads.append(c.EvidenceRead(label=healthy_read[0], content=healthy_read[1]))
```

And, in the same function's `return`, the meta gate moves from
`healthy_origin is None` to `healthy_read is None` -- a dropped read now
leaves no `origin_read_label`/`origin_healthy` trace, same as no read
being drawn at all:

```python
# before
                         **({} if healthy_origin is None else {
                             "origin_read_label": healthy_origin.origin_read[0],
                             "origin_healthy": True}),

# after
                         **({} if healthy_read is None else {
                             "origin_read_label": healthy_origin.origin_read[0],
                             "origin_healthy": True}),
```

- [ ] **Step 4: Run it green, then measure the counts**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_multi_collision.py -q`
Expected: `20 passed`. The last test's own assertion
(`(len(calls), kept, renamed, dropped) == (79, 41, 37, 1)`) is itself the
measurement: over `generate.generate(seed=17, size=8000)`, 79 `multi`
rows draw a node-story healthy origin; the rule keeps the anchor's own
node on 41, renames on 37, and drops the read on 1.

A second number, not asserted by a test (the plan's own footnote,
matching spec section 2's "In train.jsonl... 22 of the 48 such rows
clash"): of the 79, 48 survive `split` + `drop_held_out` into
`train.jsonl` and 9 into `val.jsonl`; 22 of the 48 in train clash
(rename or drop), and 6 of the 9 in val. Measured with:

```bash
cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "
from kubeagent_verdict.dataset import generate, cases

node_calls = []
orig_node = cases._multi_healthy_origin_node
def spy_node(h_node, all_objects):
    r = orig_node(h_node, all_objects)
    node_calls.append((h_node, r))
    return r
cases._multi_healthy_origin_node = spy_node

info = {}
orig_multi = cases.multi
def spy_multi(pairs, rng, healthy_origin=None):
    before = len(node_calls)
    ex = orig_multi(pairs, rng, healthy_origin=healthy_origin)
    if len(node_calls) > before:
        info[ex.group] = node_calls[-1]
    return ex
cases.multi = spy_multi

examples = generate.generate(seed=17, size=8000)
cases.multi, cases._multi_healthy_origin_node = orig_multi, orig_node
train, val = generate.split(examples, seed=17)
test = generate.test_set()
train = generate.drop_held_out(train, test)
val = generate.drop_held_out(val, test)

def clash_count(exs):
    groups = {e.group for e in exs}
    total = sum(1 for g in groups if g in info)
    clashed = sum(1 for g in groups if g in info and info[g][1] != info[g][0])
    return clashed, total

print('train:', clash_count(train))
print('val:', clash_count(val))
"
```
Expected: `train: (22, 48)` and `val: (6, 9)`.

Then run the full suite and ruff:

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: `702 passed, 6 warnings`; ruff `All checks passed!`.

**Measured:**

| metric | value |
|---|---|
| multi rows drawing a node-story healthy origin (pre-split, seed 17 size 8000) | 79 |
| ...kept (anchor's own node, no clash) | 41 |
| ...renamed (first free of worker-1/2/3) | 37 |
| ...dropped (all three clash) | 1 |
| of the 79, surviving into `train.jsonl` after split + drop_held_out | 48 |
| ...of those, clash (rename or drop) | 22 |
| of the 79, surviving into `val.jsonl` | 9 |
| ...of those, clash | 6 |
| full suite | 702 passed, 6 warnings |

Every one of these matches spec section 2's own numbers exactly (79
total, 41/37/1 split, 48 in train with 22 clashing) -- no deviation to
record for this task. The multi rotation comment in `generate.py`
(the "960/960"/"~0.55" paragraph) names no node-name or collision fact,
so it is left untouched; that re-measurement is Task 9's, not this
one's.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/cases.py tests/test_multi_collision.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "fix(dataset): multi's healthy-origin read never contradicts the row"
```

### Task 5: `_render_shared_origin` -- decided rows and a label-driven summary

**Spec:** §3 "Shared-origin rows: a decided victim and the summary label"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_render_shared_origin`,
  two new private helpers)
- New: `tests/test_shared_origin_decided.py`
- Modify (ripple, existing assertions that assumed the old behavior):
  `tests/test_propagation.py`, `tests/test_probe_wide.py`,
  `tests/test_probe_cousins.py`, `tests/test_shared_origin_decoy_probe.py`
- Modify: `tests/test_oracle.py` (adds the job-3 gates for train, val and
  the frozen exam)
- Modify: `tests/test_shared_origin_training.py` (a ripple fix to
  `test_every_shared_origin_row_names_one_cause_for_every_workload`, plus
  re-pins of `FROZEN_253_SHA256`/`EVAL_SET_SHA256` with a dated history
  comment)
- Modify: `contract/PIN.md` ("Dataset pin moves" entry, dated history)

**Interfaces:**
- Consumes: `rules.Result`, `rules.decide`, `rules.label`, `rules.shared`
  (existing), `cases._rule_rationale` (Task 2).
- Produces: `cases._shared_origin_row(result, *, healthy, decoy,
  shared_cause) -> tuple[str, str | None]` and
  `cases._shared_origin_summary(label, *, healthy, count, origin,
  shared_cause, remedy, rows, key) -> list[str]`. Both module-private,
  called only from `_render_shared_origin`. No public builder's signature
  or return shape changes.

`_render_shared_origin` already ran `rules.decide` on every victim, and
already showed the "decided by rules: ..." line on the workload's own
candidate menu -- but the ROW's own graded cause and rationale (what job 1
and job 3 actually score) ignored that result and always rendered the
row's formatted `shared_cause` sentence in the broken world, or the
victim's local `decoy` cause in the healthy world. A victim the rules had
already decided on its own local evidence -- unrelated to the row's shared
origin -- was graded on an answer that was not the rules' own. The fix
routes a decided victim's row cause and rationale through the rules'
result instead, and makes the row's summary line depend on `rules.label`
(what the rules actually confirmed together) rather than on `healthy`
alone, so a row that decided nothing in common no longer claims a shared
cause it did not find.

- [ ] **Step 1: Write the failing tests**

New file, unit tests against the two helpers directly plus a handful of
build-level checks against the real eval scenarios:

```python
"""`_render_shared_origin`'s decided-row cause/rationale and its
label-driven summary (spec section 3).

Unit tests build synthetic `rules.Result` values and row dicts directly,
one per branch of the two small pure helpers `_render_shared_origin`
delegates to: `_shared_origin_row` (per-victim cause/rationale) and
`_shared_origin_summary` (the four-way summary table). Build-level tests
then confirm the wiring against the real eval scenarios, where the
decided/undecided split actually occurs today (see the trainable pool's
own oracle tests for the training side, which never decides).
"""

from __future__ import annotations

import json

import pytest

from kubeagent_verdict.dataset import cases, generate, rules
from kubeagent_verdict.dataset import propagation as prop

# --------------------------------------------------------------- fixtures


def _confirmed_result(cause: str = "node worker-2 (NotReady)") -> rules.Result:
    return rules.Result(decided=True, cause=cause, outcome="confirmed",
                        evidence="Ready condition is False now",
                        group_key="node/worker-2", group_text=cause,
                        decisions=())


def _unverified_result(cause: str = "node worker-1 (no kubelet lease)") -> rules.Result:
    return rules.Result(decided=True, cause=cause, outcome="unverified",
                        evidence="Ready condition is True, but the kubelet "
                                 "lease was not re-read",
                        group_key="", group_text="", decisions=())


def _undecided_result() -> rules.Result:
    return rules.Result(decided=False, cause="", outcome="", evidence="",
                        group_key="", group_text="", decisions=())


# ---------------------------------------------------- _shared_origin_row


def test_decided_confirmed_row_gets_the_rules_cause_and_rationale():
    result = _confirmed_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=False, decoy="the wrong decoy cause",
        shared_cause="the story's shared cause")
    assert cause == result.cause
    assert rationale == cases._rule_rationale(result)


def test_decided_unverified_row_also_gets_the_rules_cause_and_rationale():
    result = _unverified_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=True, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == result.cause
    assert rationale == cases._rule_rationale(result)


def test_undecided_broken_row_keeps_the_shared_cause():
    result = _undecided_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=False, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == "the story's shared cause"
    assert rationale is None  # caller keeps today's rationale template


def test_undecided_healthy_row_keeps_the_decoy_cause():
    result = _undecided_result()
    cause, rationale = cases._shared_origin_row(
        result, healthy=True, decoy="the decoy cause",
        shared_cause="the story's shared cause")
    assert cause == "the decoy cause"
    assert rationale is None


# ------------------------------------------------ _shared_origin_summary


_ROWS = [{"workload": "ns1/a", "cause": "cause A"},
        {"workload": "ns2/b", "cause": "cause B"},
        {"workload": "ns3/c", "cause": "cause C"}]


def test_shared_label_keeps_todays_three_lines():
    lines = cases._shared_origin_summary(
        "shared", healthy=False, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines == ["3 workloads share one upstream cause: the origin is broken.",
                     "Root cause: the shared cause.", "fix the origin"]


def test_none_label_healthy_twin_all_different_says_separate_reasons():
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines[0] == "3 workloads are failing for separate reasons."
    assert lines[1:] == ["ns1/a: cause A.", "ns2/b: cause B.", "ns3/c: cause C."]


def test_none_label_broken_says_rules_did_not_confirm_one_cause():
    lines = cases._shared_origin_summary(
        "none", healthy=False, count=3, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=_ROWS, key="test-story")
    assert lines[0] == ("3 workloads are failing, and kubeagent's rules did not "
                        "confirm one cause on two or more of them.")
    assert lines[1:] == ["ns1/a: cause A.", "ns2/b: cause B.", "ns3/c: cause C."]
    assert "fix the origin" not in lines


def test_none_label_healthy_twin_with_a_repeated_cause_uses_the_other_branch():
    rows = [{"workload": "ns1/a", "cause": "same cause"},
           {"workload": "ns2/b", "cause": "same cause"}]
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=2, origin="the origin is broken",
        shared_cause="the shared cause", remedy="fix the origin",
        rows=rows, key="test-story")
    assert lines[0] == ("2 workloads are failing, and kubeagent's rules did not "
                        "confirm one cause on two or more of them.")


def test_separate_label_raises():
    with pytest.raises(ValueError, match="separate"):
        cases._shared_origin_summary(
            "separate", healthy=False, count=3, origin="x", shared_cause="y",
            remedy="z", rows=_ROWS, key="test-story")


def test_summary_lines_cap_at_three_rows():
    rows = _ROWS + [{"workload": "ns4/d", "cause": "cause D"}]
    lines = cases._shared_origin_summary(
        "none", healthy=True, count=4, origin="x", shared_cause="y",
        remedy="z", rows=rows, key="test-story")
    assert len(lines) == 4  # 1 header + 3 rows, never the fourth


# --------------------------------------------------------- build-level tests


def test_no_story_shared_cause_or_local_cause_holds_a_shared_claim_phrase():
    """A cause holding a shared-claim phrase would make job 3 read a `none`
    row's per-workload cause line as a claim and fail it (spec section 3).
    """
    phrases = cases.SHARED_CLAIM_PHRASES
    for pool in (prop.trainable_scenarios(), prop.all_scenarios()):
        for p in pool:
            low = p.shared_cause.lower()
            assert not any(ph in low for ph in phrases), (p.key, "shared_cause")
            for v in p.victims:
                low = v.local_cause.lower()
                assert not any(ph in low for ph in phrases), (p.key, "local_cause")


def test_a_shared_label_only_comes_from_an_origin_object():
    """Every `shared` row is a ruled story's broken twin or one of the exam's
    three origin-object stories -- never a plain story, which has no
    candidate the rules could confirm twice under one group key.
    """
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key


def test_exactly_two_of_ten_shared_origin_probe_rows_families_are_shared():
    """The three origin-object eval stories (node-not-ready,
    storage-provisioner-down, registry-unreachable) label `shared`; the
    other three (coredns-down, node-disk-pressure, networkpolicy-deny-all)
    label `none` -- pinned so a future story addition is a deliberate
    edit here, not a silent drift.
    """
    labels = {}
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        labels[p.key] = ex.meta["label"]
    assert labels == {
        "coredns-down": "none",
        "node-not-ready": "shared",
        "storage-provisioner-down": "shared",
        "registry-unreachable": "shared",
        "node-disk-pressure": "none",
        "networkpolicy-deny-all": "none",
    }


def test_a_decided_shared_origin_probe_workload_carries_the_rules_cause():
    """`node-not-ready`'s two victims share one node, so both decide against
    the SAME `origin_object` and both get the identical rules' cause."""
    p = {q.key: q for q in prop.all_scenarios()}["node-not-ready"]
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    verdicts = json.loads(ex.assistant)["verdicts"]
    causes = {v["cause"] for v in verdicts}
    assert len(causes) == 1
    only_cause = causes.pop()
    assert only_cause != p.shared_cause  # the rules' own terse cause, not the sentence
    assert only_cause.startswith("node ")
```

The committed file holds these fourteen tests exactly -- ten unit tests
against the two helpers (four over `_shared_origin_row`'s branches, six
over `_shared_origin_summary`'s), and four build-level tests against the
real eval scenarios.

- [ ] **Step 2: Run it -- watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_decided.py -q`
Watched failure: the ten tests that call `cases._shared_origin_row` or
`cases._shared_origin_summary` directly error identically, since neither
helper exists yet --
`AttributeError: module 'kubeagent_verdict.dataset.cases' has no
attribute '_shared_origin_row'` (and, once that one is added in isolation,
the same for `_shared_origin_summary`). The four build-level tests only
call the existing `cases.shared_origin_probe` and pass already, before
either helper exists. `10 failed, 4 passed`.

- [ ] **Step 3: Add the two helpers and wire them into `_render_shared_origin`**

Insert both helpers directly after `_victim_finding` and before
`class _SharedOrigin(NamedTuple):`:

```python
# ... end of _victim_finding ...
        next_step=sug.next_step, command=sug.command,
    )


def _shared_origin_row(result: rules.Result, *, healthy: bool, decoy: str,
                       shared_cause: str) -> tuple[str, str | None]:
    """One victim's (cause, rationale) for a shared-origin row.

    A decided workload -- confirmed or unverified -- gets the rules' own
    cause and rationale, exactly as `multi` already does (spec section 3):
    a decided workload never disagrees with what the rules found, whatever
    world the row is rendered in. An undecided workload keeps today's
    answer, held fixed by `healthy` alone: the decoy in the healthy world,
    the shared cause in the broken one. The `None` rationale tells the
    caller to keep applying its own per-world template, since there is no
    rules evidence to build one from.
    """
    if result.decided:
        return result.cause, _rule_rationale(result)
    return (decoy if healthy else shared_cause), None


def _shared_origin_summary(label: str, *, healthy: bool, count: int, origin: str,
                           shared_cause: str, remedy: str, rows: list[dict],
                           key: str) -> list[str]:
    """The shared-origin row's summary lines, chosen by `rules.label` rather
    than by `healthy` alone (spec section 3).

    `label == "shared"` means the rules themselves confirmed one group
    across two or more victims: today's unchanged three-line summary.
    `label == "separate"` cannot happen here and is refused rather than
    silently mis-rendered -- every victim in one propagation scenario binds
    the SAME origin object (or none), so two confirmed results always fall
    in one `rules.shared` group; `label` only reads `separate` off a lone
    size-1 group, which this builder cannot produce. Otherwise (`"none"`):
    a healthy-world row whose per-workload causes are now all distinct
    still reads as ordinary independent failures; every other `"none"` row
    -- broken-world, or healthy with a repeated cause -- says plainly that
    the rules did not confirm one cause on two or more workloads, and
    carries no remedy, because none was confirmed.
    """
    if label == "separate":
        raise ValueError(
            f"{key}: rules.label returned 'separate' for a shared-origin row, "
            "which _render_shared_origin cannot produce -- every victim in "
            "one propagation scenario binds the same origin object (or none), "
            "so two confirmed results always share one rules.shared group")
    if label == "shared":
        lines = [f"{count} workloads share one upstream cause: {origin}.",
                f"Root cause: {shared_cause}.", remedy]
    else:
        causes = {r["cause"] for r in rows}
        if healthy and len(causes) == len(rows):
            lines = [f"{count} workloads are failing for separate reasons."]
        else:
            lines = [(f"{count} workloads are failing, and kubeagent's rules "
                     "did not confirm one cause on two or more of them.")]
        lines += [f"{r['workload']}: {r['cause']}." for r in rows[:3]]
    return lines
```

Inside the per-victim loop, the row build changes from a flat `healthy`
branch to going through the first helper, falling back to today's
per-world rationale template only when the helper declines to build one:

The `before` text below must match the real file byte for byte, including
the two comment lines already sitting inside it -- find that text with an
exact search, not a paraphrase:

```python
# before
        row_cause = decoy if healthy else shared_cause
        rows.append({"workload": f"{n.ns}/{n.name}",
                     "cause": row_cause,
                     # The pass's own grade for its own attribution. When that
                     # attribution is right, so is the grade -- see
                     # `shared_origin_decoy_probe` on what that costs.
                     "confidence": v.pass_confidence if healthy else p.confidence,
                     "rationale": _fmt(v.local_reason if healthy else p.rationale, n)})

# after
        row_cause, row_rationale = _shared_origin_row(
            result, healthy=healthy, decoy=decoy, shared_cause=shared_cause)
        if row_rationale is None:
            row_rationale = _fmt(v.local_reason if healthy else p.rationale, n)
        rows.append({"workload": f"{n.ns}/{n.name}",
                     "cause": row_cause,
                     # The pass's own grade for its own attribution. When that
                     # attribution is right, so is the grade -- see
                     # `shared_origin_decoy_probe` on what that costs.
                     "confidence": v.pass_confidence if healthy else p.confidence,
                     "rationale": row_rationale})
```

The comment stays untouched in both versions -- this change never touches
`confidence`, only `cause` and `rationale`.

And after the loop, the summary build goes through the second helper
instead of branching on `healthy` directly (`label` was already computed
here for `extra_meta`, just unused by the summary until now):

Again the `before` text carries a pre-existing comment the plan's search
must match exactly, this time only on the `healthy` branch (the `else`
branch has none):

```python
# before
    if healthy:
        # Verbatim `multi`'s shape: this IS the ordinary independent answer,
        # and a different wording would separate the classes by phrasing.
        lines = [f"{count} workloads are failing for separate reasons."]
        lines += [f"{r['workload']}: {r['cause']}." for r in rows[:3]]
    else:
        lines = [f"{count} workloads share one upstream cause: {_fmt(p.origin, anchor)}.",
                 f"Root cause: {shared_cause}.",
                 _fmt(p.remedy, anchor)]

# after
    lines = _shared_origin_summary(
        label, healthy=healthy, count=count, origin=_fmt(p.origin, anchor),
        shared_cause=shared_cause, remedy=_fmt(p.remedy, anchor), rows=rows,
        key=p.key)
```

That comment's own point -- "this IS the ordinary independent answer" --
moves into `_shared_origin_summary`'s docstring above instead: the logic it
was attached to now lives there, so the comment is deleted here rather than
carried forward orphaned.

- [ ] **Step 4: Run it green, then fix the ripple**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_decided.py -q`
Expected: `14 passed`.

Running the full suite at this point surfaces the ripple: nine test IDs
(eight test functions, one of them parametrized twice) in
`tests/test_propagation.py`, `tests/test_probe_wide.py` and
`tests/test_shared_origin_decoy_probe.py` fail --

```
FAILED tests/test_probe_wide.py::test_wide_rows_are_adjacent_twins_with_unique_pair_keys
FAILED tests/test_propagation.py::test_every_row_names_the_same_shared_cause
FAILED tests/test_propagation.py::test_the_decoy_leads_every_candidate_menu_and_the_answer_trails
FAILED tests/test_propagation.py::test_the_shared_cause_is_a_candidate_line_on_every_workload
FAILED tests/test_shared_origin_decoy_probe.py::test_the_shared_cause_is_the_decoy_the_scorer_watches
FAILED tests/test_shared_origin_decoy_probe.py::test_no_tag_heuristic_wins_both_shared_origin_slices[attributed]
FAILED tests/test_shared_origin_decoy_probe.py::test_no_tag_heuristic_wins_both_shared_origin_slices[outranked]
FAILED tests/test_shared_origin_decoy_probe.py::test_a_model_that_always_claims_a_shared_origin_fails_this_slice
FAILED tests/test_shared_origin_decoy_probe.py::test_a_model_that_reads_the_evidence_passes_this_slice
```

Each had asserted the OLD, always-shared-cause behavior directly -- "every
verdict in a shared-origin row names the same one cause" is no longer true
in general once a decided victim renders its own cause instead. It is
still true for a `shared`-labeled row on FIVE of the six eval origins --
every victim there decided against the same node, registry name, or (for
the two scope-pinned origins) literally the same string -- but
`storage-provisioner-down` groups by storage class
(`rules.py`'s group-key storage-class fallback), and its `shared` group can
hold two or three DIFFERENT per-PVC causes under one shared label. So the
real invariant a `shared`-labeled row keeps is narrower than "one cause":
every victim on it is decided, and one cause per row holds for every
origin except `storage-provisioner-down`. Each fix below is a narrowing of
what the test may assume, never a new behavior:

- `test_every_row_names_the_same_shared_cause` (docstring rewritten; same
  name) now checks, on a `shared`-labeled row, that every victim is
  decided and that the one-cause promise holds everywhere except
  `storage-provisioner-down`; it also requires that both a `shared`- and a
  `none`-labeled row are exercised across the six eval origins, so the
  `none` branch is never silently untested.
- `test_the_decoy_leads_every_candidate_menu_and_the_answer_trails` and
  `test_the_shared_cause_is_a_candidate_line_on_every_workload` read the
  shared-cause candidate off the fixed three-line MENU (built from
  `p.shared_cause`/`p.shared_verdict` regardless of what the rules later
  decide) instead of off `verdicts[0]["cause"]`, which a decided workload
  can now carry a cause the menu never lists.
- `test_wide_rows_are_adjacent_twins_with_unique_pair_keys` only checks
  "every victim shares one cause, disjoint from its decoy twin" on a
  `shared`-labeled probe half, and skips the one-cause part of that check
  on `storage-provisioner-down` for the same group-key reason as above.
- Four tests in `test_shared_origin_decoy_probe.py`
  (`test_the_shared_cause_is_the_decoy_the_scorer_watches`,
  `test_no_tag_heuristic_wins_both_shared_origin_slices`,
  `test_a_model_that_always_claims_a_shared_origin_fails_this_slice`,
  `test_a_model_that_reads_the_evidence_passes_this_slice`) are discussed
  below -- `score.py`'s own grading logic, not just the builder's shape,
  has to be re-derived against the fix.

Two more tests do NOT fail either -- no defensive edit is required for the
suite to pass -- but this task widens both to the same label-aware shape
anyway, since a future draw could decide a victim even though none does
today, and applying this task's text literally must reproduce the commit
byte for byte:

- `tests/test_probe_cousins.py`'s twin check
  (`test_cousin_rows_are_adjacent_twins_with_unique_pair_keys`): the cousin
  pool is trainable-origins-only, and no trainable scenario decides today
  (the trainable pool's own oracle tests hold job 3 at 1.0 without ever
  reaching a `decided` victim).
- `tests/test_shared_origin_training.py`'s
  `test_every_shared_origin_row_names_one_cause_for_every_workload`, for the
  same reason -- it draws from the same trainable-origins-only pool as the
  cousin probes, just over the full training set rather than a paired
  subset, so it is future-proofing rather than a live path today too.

Fixed versions, each as an exact `old`/`new` pair against the file at the
start of this task -- find the `old` text with an exact search:

```python
# tests/test_propagation.py -- old
def test_every_row_names_the_same_shared_cause():
    """The whole point: one origin, one answer, repeated.

    `multi` renders N different causes and says so. This row renders N
    workloads whose correct cause is one string.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        causes = {r["cause"] for r in json.loads(ex.assistant)["verdicts"]}
        assert len(causes) == 1, p.key

# tests/test_propagation.py -- new
def test_every_row_names_the_same_shared_cause():
    """The whole point, on a `shared`-labeled row: every victim's cause
    comes from ONE `rules.shared()` group, and every victim is decided.

    `multi` renders N different causes and says so. A `shared`-labeled
    shared-origin row instead renders N workloads the rules confirmed
    together under one shared-origin object. On the two scope-pinned
    stories (`node-not-ready`, `registry-unreachable`) that means the
    identical cause string, because every victim binds the same node or
    registry name. `storage-provisioner-down`'s origin binds a PER-VICTIM
    PVC name, so its `shared` group holds one storage class across
    DIFFERENT PVC causes (`rules.py`'s group-key storage-class fallback)
    -- still one group, not one string. A `none`-labeled row makes neither
    promise (spec section 3): its undecided victims still share
    `p.shared_cause`, but a victim the rules separately decided, off its
    own unrelated evidence, carries its own cause instead.
    `test_a_shared_label_only_comes_from_an_origin_object` in
    `tests/test_shared_origin_decided.py` is the reverse check: no
    `none`-labeled row is ever mistaken for a `shared` one.
    """
    from kubeagent_verdict.dataset import cases, generate
    saw_shared = saw_none = False
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        verdicts = json.loads(ex.assistant)["verdicts"]
        if ex.meta["label"] == "shared":
            saw_shared = True
            assert all(ex.meta["workloads"][v["workload"]]["decided"]
                      for v in verdicts), p.key
            causes = {v["cause"] for v in verdicts}
            if p.key != "storage-provisioner-down":
                assert len(causes) == 1, p.key
        else:
            saw_none = True
    assert saw_shared and saw_none, "both labels must be exercised"
```

```python
# tests/test_propagation.py -- old
def test_the_decoy_leads_every_candidate_menu_and_the_answer_trails():
    """Tag AND position both point away from the answer, on every workload.

    Three candidates per victim in a fixed order: the local decoy carrying
    `attributed` first, the evidence-refuted distractor second, the shared
    cause carrying `outranked` last. A model answering by index or by tag
    scores zero; a model reading the evidence is unaffected.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        blocks = _menu_blocks(ex)
        assert len(blocks) == len(p.victims), p.key
        cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
        for block, decoy in zip(blocks, ex.meta["decoy_causes"]):
            assert len(block) == 3, p.key
            assert block[0].startswith(f"{decoy}: attributed "), p.key
            assert block[1].startswith(f"{ex.meta['distractor_cause']}: ruled out "), p.key
            assert block[2].startswith(f"{cause}: outranked "), p.key

# tests/test_propagation.py -- new
def test_the_decoy_leads_every_candidate_menu_and_the_answer_trails():
    """Tag AND position both point away from the shared-cause candidate, on
    every workload.

    Three candidates per victim in a fixed order: the local decoy carrying
    `attributed` first, the evidence-refuted distractor second, the shared
    cause carrying `outranked` last. A model answering by index or by tag
    scores zero; a model reading the evidence is unaffected.

    The menu is built from `p.shared_cause`/`p.shared_verdict` regardless of
    what the rules later decide (spec section 3), so its shape never moves;
    what CAN move off it is a workload's own verdict, checked by
    `test_every_row_names_the_same_shared_cause` above. This reads the
    shared-cause candidate straight off the menu rather than off
    `verdicts[0]`, which a decided workload can now carry a cause the menu
    never lists.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        blocks = _menu_blocks(ex)
        assert len(blocks) == len(p.victims), p.key
        for block, decoy in zip(blocks, ex.meta["decoy_causes"]):
            assert len(block) == 3, p.key
            assert block[0].startswith(f"{decoy}: attributed "), p.key
            assert block[1].startswith(f"{ex.meta['distractor_cause']}: ruled out "), p.key
            assert f": {p.shared_verdict} " in block[2], p.key
```

```python
# tests/test_propagation.py -- old
def test_the_shared_cause_is_a_candidate_line_on_every_workload():
    """Verbatim-matchable, which is what `score.evaluate` compares.

    The contract tells the model it may answer with "a candidate cause
    verbatim". Putting the shared cause on each menu keeps the correct answer
    inside that vocabulary, so a wrong answer is a judgement failure and never
    a phrasing one.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        menu = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
        cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
        assert menu.count(f"considered {cause}: ") == len(p.victims), p.key

# tests/test_propagation.py -- new
def test_the_shared_cause_is_a_candidate_line_on_every_workload():
    """Verbatim-matchable, which is what `score.evaluate` compares.

    The contract tells the model it may answer with "a candidate cause
    verbatim". Putting the shared cause on each menu keeps the correct answer
    inside that vocabulary, so a wrong answer is a judgement failure and never
    a phrasing one.

    Read off the menu's own shared-cause candidate (every block's third line,
    byte-identical across a row's workloads by construction) rather than off
    `verdicts[0]["cause"]`, which a decided workload can now move off the
    menu entirely (spec section 3).
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        menu = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
        blocks = _menu_blocks(ex)
        cause = blocks[0][2].split(f": {p.shared_verdict} ")[0]
        assert menu.count(f"considered {cause}: ") == len(p.victims), p.key
```

```python
# tests/test_probe_wide.py -- old
def test_wide_rows_are_adjacent_twins_with_unique_pair_keys():
    rows = generate.shared_origin_wide_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        # Probe half: every victim shares ONE cause. Decoy half: none of the
        # victims' correct causes is that shared cause.
        shared = set(probe.meta["expected"].values())
        assert len(shared) == 1
        assert shared.isdisjoint(set(decoy.meta["expected"].values()))

# tests/test_probe_wide.py -- new
def test_wide_rows_are_adjacent_twins_with_unique_pair_keys():
    """A `shared`-labeled probe half is decided end to end: every victim's
    cause comes from the rules, disjoint from its decoy twin's causes (spec
    section 3). On the two scope-pinned origins (node-not-ready,
    registry-unreachable) that is one string, because every victim binds the
    same node or registry name. storage-provisioner-down's origin binds a
    PER-VICTIM PVC name, so its `shared` group can hold more than one PVC
    cause (`rules.py`'s group-key storage-class fallback) -- still disjoint
    from the decoy twin, just not one string.

    A `none`-labeled probe half makes neither promise. A victim the rules
    decide on its own evidence gets the same cause regardless of `healthy` --
    the per-victim decide branch never reads it -- so it can appear on BOTH
    halves of the pair; only the undecided victims still swap between the
    decoy and shared causes.
    """
    rows = generate.shared_origin_wide_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        shared = set(probe.meta["expected"].values())
        if probe.meta["label"] == "shared":
            assert all(w["decided"] for w in probe.meta["workloads"].values())
            if probe.meta["origin"] != "storage-provisioner-down":
                assert len(shared) == 1
            assert shared.isdisjoint(set(decoy.meta["expected"].values()))
```

`tests/test_probe_cousins.py`'s change, included for the same
byte-for-byte reason even though no data draw exercises the `shared`
branch it adds (see above):

```python
# tests/test_probe_cousins.py -- old
def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    rows = generate.shared_origin_cousin_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        # Probe half: every victim shares ONE cause. Decoy half: none of the
        # victims' correct causes is that shared cause.
        shared = set(probe.meta["expected"].values())
        assert len(shared) == 1
        assert shared.isdisjoint(set(decoy.meta["expected"].values()))

# tests/test_probe_cousins.py -- new
def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    """Label-aware, the same way `test_probe_wide.py`'s twin check is (spec
    section 3, ruling C). No trainable scenario decides today -- the
    trainable pool's own oracle tests hold job 3 at 1.0 without ever
    reaching a `decided` victim -- so every cousin pair is `none`-labeled in
    practice and the `shared` branch below is future-proofing rather than a
    live path; `test_cousin_probe_uses_only_trainable_origins` above already
    pins the pool this draws from.
    """
    rows = generate.shared_origin_cousin_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        # A `shared`-labeled probe half is decided end to end and disjoint
        # from its decoy twin. A `none`-labeled half makes neither promise:
        # a decided victim's cause does not depend on `healthy`, so it can
        # repeat across the pair.
        if probe.meta["label"] == "shared":
            shared = set(probe.meta["expected"].values())
            assert all(w["decided"] for w in probe.meta["workloads"].values())
            assert shared.isdisjoint(set(decoy.meta["expected"].values()))
```

```python
# tests/test_shared_origin_training.py -- old
def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    for e in _by_case(rows, "shared_origin"):
        causes = set(e.meta["expected"].values())
        assert len(causes) == 1, e.meta["origin"]

# tests/test_shared_origin_training.py -- new
def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    """Label-aware (spec section 3, ruling C): a `shared`-labeled row is
    decided end to end, one cause per victim, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback) can decide several
    victims to several PVC causes and still be one `shared` group. No
    trainable scenario decides today (the trainable pool's own oracle tests
    hold job 3 at 1.0 without ever reaching a decided victim), so this is
    future-proofing rather than a live path today.
    """
    for e in _by_case(rows, "shared_origin"):
        if e.meta["label"] != "shared":
            continue
        causes = set(e.meta["expected"].values())
        assert all(w["decided"] for w in e.meta["workloads"].values())
        if e.meta["origin"] != "storage-provisioner-down":
            assert len(causes) == 1, e.meta["origin"]
```

```python
# tests/test_shared_origin_decoy_probe.py -- old
def test_the_shared_cause_is_the_decoy_the_scorer_watches(decoys, probes):
    """`named_decoy` must fire on the trap this slice sets, not on nothing.

    Compared against the TWIN's expected answers rather than the raw
    `shared_cause` template: `{node}` and `{ns}` are substituted per row, and
    the twin -- same salt, same names -- is where the formatted string lives.
    """
    for d, t in zip(decoys, probes):
        want = set(t.meta["expected"].values())
        assert len(want) == 1, d.meta["origin"]
        assert d.meta["decoy_causes"] == list(want), d.meta["origin"]

# tests/test_shared_origin_decoy_probe.py -- new
def test_the_shared_cause_is_the_decoy_the_scorer_watches(decoys):
    """`named_decoy` must fire on the trap this slice sets, not on nothing.

    `decoy_causes` (spec section 9: protected, unconditional) is always the
    one formatted `shared_cause` sentence, never a decided victim's own
    terse cause -- checked against the scenario's own `shared_cause`
    template rather than against either twin's `expected` values, because
    neither half is a reliable source any more: this row's own `expected`
    never holds it (a decoy row's undecided victims render their own local
    cause, not the shared one -- `test_the_correct_answer_is_each_workload_
    s_own_local_cause` above), and the twin probe's `expected` only holds it
    when the probe still has an undecided victim left -- an origin-object
    story that happens to draw every victim decided leaves nothing in `expected`
    for the trap to match, even though the trap itself is still set.
    """
    for e in decoys:
        assert len(e.meta["decoy_causes"]) == 1, e.meta["origin"]
        template = propagation.by_key()[e.meta["origin"]].shared_cause
        pattern = re.sub(r"\\\{\w+\\\}", ".+", re.escape(template))
        assert re.fullmatch(pattern, e.meta["decoy_causes"][0]), e.meta["origin"]
```

```python
# tests/test_shared_origin_decoy_probe.py -- old
def test_no_tag_heuristic_wins_both_shared_origin_slices(decoys, probes, verdict):
    """One tag sweeps one slice and scores zero on the other, both ways."""
    def hits(examples):
        got = total = 0
        for e in examples:
            picks = _menu_pick(e, verdict)
            for workload, want in e.meta["expected"].items():
                total += 1
                got += int(picks.get(workload) == want)
        return got, total

    on_decoy, on_probe = hits(decoys), hits(probes)
    assert on_decoy[1] == on_probe[1] > 0
    won, lost = (on_decoy, on_probe) if verdict == "attributed" else (on_probe, on_decoy)
    assert won[0] == won[1], f"{verdict} should sweep its slice: {won}"
    assert lost[0] == 0, f"{verdict} should score zero on the other: {lost}"

# tests/test_shared_origin_decoy_probe.py -- new
def test_no_tag_heuristic_wins_both_shared_origin_slices(decoys, probes, verdict):
    """One tag sweeps one slice and scores zero on the other, both ways.

    Over the workloads UNDECIDED ON BOTH HALVES of the pair -- the
    local-decoy-vs-shared-cause tension this tag pair exists to measure.
    Excluded jointly, not per half: an origin-object story's victims decide
    on the broken half and undecide on the healthy half (a healthy origin object
    confirms nothing), so a per-half filter would drop a different set of
    workloads from each side and the two totals would stop matching. A
    decided workload's correct answer is the rules' terse cause, which
    never appears on the fixed three-candidate menu (decoy/distractor/
    shared_cause) at all; it lives on the separate `decided by rules:` line
    `_menu_pick` does not read, so every tag pick misses it on both slices
    and it carries no signal either way.
    """
    got_decoy = total_decoy = got_probe = total_probe = 0
    for d, p in zip(decoys, probes):
        decoy_picks, probe_picks = _menu_pick(d, verdict), _menu_pick(p, verdict)
        for workload, want_decoy in d.meta["expected"].items():
            if d.meta["workloads"][workload]["decided"] or \
                    p.meta["workloads"][workload]["decided"]:
                continue
            total_decoy += 1
            got_decoy += int(decoy_picks.get(workload) == want_decoy)
            total_probe += 1
            got_probe += int(probe_picks.get(workload) == p.meta["expected"][workload])

    on_decoy, on_probe = (got_decoy, total_decoy), (got_probe, total_probe)
    assert on_decoy[1] == on_probe[1] > 0
    won, lost = (on_decoy, on_probe) if verdict == "attributed" else (on_probe, on_decoy)
    assert won[0] == won[1], f"{verdict} should sweep its slice: {won}"
    assert lost[0] == 0, f"{verdict} should score zero on the other: {lost}"
```

```python
# tests/test_shared_origin_decoy_probe.py -- old
def test_a_model_that_always_claims_a_shared_origin_fails_this_slice(decoys, probes):
    """The failure mode a shared-origin correction can plausibly introduce.

    The fake answer is not invented: it is the TWIN row's own assistant
    message, verbatim. Same salt means same workload names, so the twin's
    answer is exactly what a model that had learned "a cluster-wide read means
    one shared cause" would emit here -- the real failure, not a caricature of
    it.

    Averaged across the whole corpus this would barely move `cause_accuracy`.
    This is the measurement that makes it cost something: cause accuracy
    collapses to 0, every row names the decoy, and job3 -- which grades this
    `label: none` slice on whether the summary claims a shared cause -- reads
    0.0, on a slice where the 0830 model, which answered independence
    everywhere, would have scored perfectly.
    """
    twin = {d.user: t.assistant for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: twin[m[1]["content"]])
    assert all(r["contract_ok"] for r in results)
    assert all(r["cause_acc"] == 0.0 for r in results)
    assert all(r["named_decoy"] is True for r in results)
    assert all(r["job3"] == 0.0 for r in results)

# tests/test_shared_origin_decoy_probe.py -- new
def test_a_model_that_always_claims_a_shared_origin_fails_this_slice(decoys, probes):
    """The failure mode a shared-origin correction can plausibly introduce.

    The fake answer is not invented: it is the TWIN row's own assistant
    message, verbatim. Same salt means same workload names, so the twin's
    answer is exactly what a model that had learned "a cluster-wide read means
    one shared cause" would emit here -- the real failure, not a caricature of
    it.

    Cause accuracy no longer collapses to a flat 0 on every row: a decided
    workload's cause does not depend on `healthy` (its own local evidence,
    not the row's origin, decides it), so the twin's answer for it is
    already correct here too.

    `named_decoy` splits by the PROBE's own label, not this row's (which is
    always `none` -- see `test_the_shared_cause_is_the_decoy_the_scorer_
    watches`'s docstring). On the three `none`-labeled origins the twin's
    answer still fires the trap on every row, but not the trap this
    docstring's title names: `decoy_by_workload` (spec section 9: protected,
    unchanged) holds `[result.cause]` for a workload the rules decided, and
    the twin decides that SAME workload to that SAME cause (healthy-
    insensitive), so the twin's own reply matches its own listed decoy --
    the pre-existing quirk `test_a_model_that_reads_the_evidence_passes_
    this_slice` below names on a fully honest reply. On the three
    `shared`-labeled origins (ruled stories) the twin is fully decided too,
    but `decoy_by_workload` is unconditionally empty there (spec section
    12's "no decoy rate on ruled stories"), and the row-level trap
    (`shared_cause`) never appears in a fully-decided twin's answer, so
    nothing fires.

    job3 grades the summary against THIS row's own `none` label, so it
    tracks what the twin's summary actually claims, not which origin it is:
    a `shared`-labeled twin (the three origin-object stories) still writes "N
    workloads share one upstream cause", which is false here, so job3 reads
    0.0. A `none`-labeled twin (the other three) already writes today's
    honest "kubeagent's rules did not confirm one cause on two or more of
    them" -- the label-driven summary's whole point is that this no longer claims a shared
    origin on a `none`-labeled row, so pasting it here, where the label is
    also `none`, is not the failure this test is naming, and job3 reads 1.0.
    """
    twin = {d.user: t.assistant for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: twin[m[1]["content"]])
    assert all(r["contract_ok"] for r in results)
    for e, t, r in zip(decoys, probes, results):
        decided = [w["decided"] for w in e.meta["workloads"].values()]
        assert r["cause_acc"] == sum(decided) / len(decided), e.meta["origin"]
        assert r["named_decoy"] is (t.meta["label"] != "shared"), e.meta["origin"]
        assert r["job3"] == (0.0 if t.meta["label"] == "shared" else 1.0), e.meta["origin"]
```

```python
# tests/test_shared_origin_decoy_probe.py -- old
def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape."""
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]])
    assert all(r["cause_acc"] == 1.0 for r in results)
    assert all(r["conf_acc"] == 1.0 for r in results)
    assert all(r["named_decoy"] is False for r in results)
    assert all(r["job3"] == 1.0 for r in results)

# tests/test_shared_origin_decoy_probe.py -- new
def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape.

    `named_decoy` no longer reads False across the board: `decoy_by_workload`
    (spec section 9: protected, unchanged) holds a decided workload's own
    candidate list, which -- for the per-victim decided branch this slice's
    two `none`-labeled rows with an embedded decided victim exercise -- is
    just `[result.cause]`, so even the CORRECT reply names its own workload
    as its own "decoy". It reads True exactly where the row decides at
    least one workload, never on a fully undecided row.
    """
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]])
    assert all(r["cause_acc"] == 1.0 for r in results)
    assert all(r["conf_acc"] == 1.0 for r in results)
    assert all(r["job3"] == 1.0 for r in results)
    for e, r in zip(decoys, results):
        n_decided = sum(1 for w in e.meta["workloads"].values() if w["decided"])
        assert r["named_decoy"] is (n_decided > 0), e.meta["origin"]
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_decoy_probe.py tests/test_propagation.py tests/test_probe_wide.py tests/test_probe_cousins.py tests/test_shared_origin_training.py -q`
Expected: `110 passed, 2 failed` across the five files
(`test_shared_origin_decoy_probe.py` alone is `15 passed`). The two
failures are the hash pins in `test_shared_origin_training.py`,
`test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used`
and `test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used`:
the exam bytes moved, as they must. They go green in Step 7, after gates 4
and 5 prove the move is the right one. Any other failure is a STOP.

- [ ] **Step 5: Gate 4 -- oracle job 3 stays 1.0 on train, val and the exam**

Three separate insertions into the existing `tests/test_oracle.py`, each
at its own position -- find each `old` text with an exact search, since
this file is not append-only.

First, a new cached `_exam()` fixture, right after the existing
`_val_results()` and before `_job2_gate`:

```python
# old
@functools.lru_cache(maxsize=1)
def _val_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[1]))


def _job2_gate(examples: list) -> dict:

# new
@functools.lru_cache(maxsize=1)
def _val_results() -> tuple[dict, ...]:
    return tuple(_gold_results(_train_and_val()[1]))


@functools.lru_cache(maxsize=1)
def _exam() -> tuple[list, tuple[dict, ...]]:
    exam = generate.test_set()
    return exam, tuple(_gold_results(exam))


def _job2_gate(examples: list) -> dict:
```

Second, the train/val job-3 gates, right after the existing
`test_oracle_job2_keyword_only_matches_the_spec_measurement` and before
`test_oracle_multi_job1_matches_the_spec_measurement`:

```python
# old
def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect."""
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2175}


def test_oracle_multi_job1_matches_the_spec_measurement():

# new
def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect."""
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2175}


def test_oracle_job3_is_perfect_on_train():
    """Task 5's label-driven summary: every gold summary in the built
    dataset matches its own row's label, train side. `shared` never
    appears here -- no trainable scenario decides today (see
    `test_shared_origin_training.py`'s docstring on the same point) -- and
    `separate` is `multi`'s own bucket, not a shared-origin one; the
    `_render_shared_origin` `ValueError` guards a label `rules.label` can
    never actually return, not this one."""
    board = score.scoreboard(list(_train_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 2263,
        "by_label": {"shared": {"rate": None, "n": 0},
                     "separate": {"rate": 1.0, "n": 1},
                     "none": {"rate": 1.0, "n": 2262}}}


def test_oracle_job3_is_perfect_on_val():
    board = score.scoreboard(list(_val_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 265,
        "by_label": {"shared": {"rate": None, "n": 0},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 265}}}


def test_oracle_multi_job1_matches_the_spec_measurement():
```

Third, the frozen-exam gates, appended after the existing
`test_oracle_multi_job1_matches_the_spec_measurement` at the end of the
file:

```python
# old (the file's last lines)
    assert multi_job1(_train_results()) == (996.0, 996)
    assert multi_job1(_val_results()) == (121.0, 121)

# new
    assert multi_job1(_train_results()) == (996.0, 996)
    assert multi_job1(_val_results()) == (121.0, 121)


def test_exam_oracle_job1_misses_only_contradiction_probe():
    """spec section 10 gate 2: the frozen exam's own job1, oracle-read.
    138 of 157 pass; the 19 misses are exactly the `contradiction_probe`
    rows, a case whose gold reply is engineered to contradict what job1
    grades by design -- not a shared-origin regression. No `multi`,
    `shared_origin_probe` or `shared_origin_decoy_probe` row misses."""
    exam, results = _exam()
    scores = [s for r in results for s in r["job1_scores"]]
    assert (len(scores), sum(scores)) == (157, 138.0)
    misses = [e.case for e, r in zip(exam, results)
             if sum(r["job1_scores"]) < len(r["job1_scores"])]
    assert len(misses) == 19
    assert set(misses) == {"contradiction_probe"}


def test_exam_oracle_job3_is_perfect():
    """spec section 10 gate 2's other half, and a stop condition: if the
    exam's own job3, oracle-read, were not 1.0 after the label-driven
    summary, the gold summaries would be wrong and re-pinning
    `FROZEN_253_SHA256` / `EVAL_SET_SHA256` over them would bank the error.
    It reads 1.0 -- 5 of 5 `shared`-labeled rows (the three origin-object
    stories' `shared_origin_probe` halves) and 34 of 34 `none`-labeled
    rows."""
    _, results = _exam()
    board = score.scoreboard(list(results))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 39,
        "by_label": {"shared": {"rate": 1.0, "n": 5},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 34}}}
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_oracle.py -q`
Expected: `10 passed`. The exam's own job 3 stays at 1.0, so the STOP
condition is not triggered and the footprint check in Step 6, then the
re-pin in Step 7, proceed.

- [ ] **Step 6: Gate 5 -- the footprint check**

Builds the exam at the pre-Task-5 base commit and at the fixed working
tree, into two scratch directories, then diffs every row's full JSON
structure key path by key path (not just top-level equality), so a change
outside the two allowed fields would be caught and named, not merged into
the row count.

```bash
BASE=abdc0be   # the branch's root, before Task 1 -- literal, not
               # `git merge-base main HEAD`: if `main` moves while this
               # plan is being implemented, merge-base would silently pick
               # up main's later commits into "before Task 1" and the
               # footprint below would no longer be Task 5's alone
WORK=$(mktemp -d -t kv-footprint.XXXXXX)   # outside the repo, so pytest
                                           # and ruff never see the worktree
git -C /home/ubuntu/git/kubeagent-verdict worktree add "$WORK/base" "$BASE"

PYTHONPATH="$WORK/base/src" .venv/bin/python -c "
import sys
sys.argv = ['kv-dataset', '--seed', '17', '--size', '8000', '--out', '$WORK/out_base']
from kubeagent_verdict.dataset import cli
cli.main()
"
PYTHONPATH=src .venv/bin/python -c "
import sys
sys.argv = ['kv-dataset', '--seed', '17', '--size', '8000', '--out', '$WORK/out_head']
from kubeagent_verdict.dataset import cli
cli.main()
"

.venv/bin/python -c "
import json

def load(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f]

base = load('$WORK/out_base/test.jsonl')
head = load('$WORK/out_head/test.jsonl')
assert len(base) == len(head) == 263

def leaf_diffs(a, b, prefix=''):
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            diffs += leaf_diffs(a.get(k, '<missing>'), b.get(k, '<missing>'),
                                f'{prefix}.{k}' if prefix else k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((f'{prefix}.<len>', len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diffs += leaf_diffs(x, y, f'{prefix}[{i}]')
    elif a != b:
        diffs.append((prefix, a, b))
    return diffs

changed, bad = [], 0
for i, (b_row, h_row) in enumerate(zip(base, head)):
    diffs = leaf_diffs(b_row, h_row)
    if not diffs:
        continue
    changed.append(i)
    for path, *_ in diffs:
        ok = (path.startswith('messages[2].content') or path.startswith('meta.expected')
              or (path.startswith('meta.workloads') and path.endswith('.expected_cause')))
        if not ok:
            bad += 1
            print('BAD PATH row', i, h_row['meta']['case'], path)

print('rows changed:', len(changed))
print('1-based row numbers:', [r + 1 for r in changed])
print('cases:', [base[r]['meta']['case'] for r in changed])
print('bad entries:', bad)
"

git -C /home/ubuntu/git/kubeagent-verdict worktree remove "$WORK/base" --force
rm -rf "$WORK"
```

Measured output (the `cases` line is shortened here; it prints the full
14-item list):

```
rows changed: 14
1-based row numbers: [244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 258, 260, 263]
cases: ['shared_origin_probe'] * 10 + ['shared_origin_decoy_probe'] * 4
bad entries: 0
```

Exactly the footprint the spec names: rows 244-253 (all ten
`shared_origin_probe` rows, inside `FROZEN_253_SHA256`'s slice) plus 4 of
the 10 `shared_origin_decoy_probe` rows (254-263, outside it) -- the two
origins (`coredns-down`, `node-disk-pressure`) whose victims decide the
same way whether or not the origin is healthy, each drawn twice into the
exam. `bad entries: 0` confirms every one of the 14 changed rows differs
only in the assistant message and, inside `meta`, only `expected`/each
workload's `expected_cause` -- no other field, no row count change, no
row reordering. The base is the branch root, so this diff covers Tasks 1
to 5 together. Every changed row is a shared-origin row, and Task 5 is the
only one of them that changes how those rows render, so the footprint is
Task 5's.

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_exam_graded_view.py -q`
Expected: `2 passed` -- the graded-view pin (Task 1) is unaffected, as the
STOP condition also requires.

- [ ] **Step 7: Re-pin the two hashes**

Neither `FROZEN_253_SHA256` nor `EVAL_SET_SHA256` may be re-pinned with
`-update`; both are typed in by hand, from the value `tests/test_shared_
origin_training.py`'s own `_digest` helper computes, with a dated history
comment explaining why. Both changes are old/new pairs against the file's
existing comment history -- find the `old` text with an exact search:

```python
# old
# It moved a second time, on 2026-09-16, and for a plain reason: no prompt
# carried a `decided by rules:` line. Job 1 grades the model on echoing that
# line, so every row it should appear in was missing the thing being graded.
# Adding it changed the rendered bytes of every decided row. A job-1 number
# from before this fix measures something else and is retired on purpose.
FROZEN_253_SHA256 = "4d772776179aa6406c73d8fbe7714b6f14e26af09ecf25322a5a0088529ffc4f"

# new
# It moved a second time, on 2026-09-16, and for a plain reason: no prompt
# carried a `decided by rules:` line. Job 1 grades the model on echoing that
# line, so every row it should appear in was missing the thing being graded.
# Adding it changed the rendered bytes of every decided row. A job-1 number
# from before this fix measures something else and is retired on purpose.
#
# It moved a third time, on 2026-09-19, for `_render_shared_origin`'s
# decided-row fix (section 3 of the 2026-09-19 training-targets design): all ten
# `shared_origin_probe` rows (244-253, inside this frozen slice) change.
# A decided victim's row cause and rationale now come from the rules
# (`result.cause`, `_rule_rationale(result)`) instead of always the
# formatted `shared_cause`, and a `none`-labeled row's summary now says
# "kubeagent's rules did not confirm one cause on two or more of them"
# instead of falsely claiming a shared one. A key-by-key diff of the exam
# before and after the fix measured the footprint: exactly these 10 rows
# plus 4 of the 10 `shared_origin_decoy_probe` rows (outside this frozen
# slice, see `EVAL_SET_SHA256` below) change, and nothing else does.
FROZEN_253_SHA256 = "b327cc397c0e0550881791be5d7d14c45bce5d9030a11fd5d5f2c5d4d6be6faf"
```

```python
# old
# line and the `decoy_cause` key from the previous re-pin stay; only the
# label moved, from `separate` back to `none`. This changes the rendered
# bytes of the ten decoy rows again, so every job-3 number banked against
# the `separate` re-pin above is retired. `FROZEN_253_SHA256` does not
# move: the ten relabelled rows are 254-263, outside the frozen slice.
EVAL_SET_SHA256 = "0b943307d46a052a7f24c097d353cee27be1de2d81d9d873360179bbf9233468"

# new
# line and the `decoy_cause` key from the previous re-pin stay; only the
# label moved, from `separate` back to `none`. This changes the rendered
# bytes of the ten decoy rows again, so every job-3 number banked against
# the `separate` re-pin above is retired.
#
# Re-pinned once more on 2026-09-19, in the same commit and for the same
# `_render_shared_origin` fix that moved `FROZEN_253_SHA256` above (see
# its 2026-09-19 entry). Four of the ten `shared_origin_decoy_probe` rows
# change too -- exactly the ones with a decided victim this draw (two
# coredns-down, two node-disk-pressure): their decided victim's row cause
# and rationale move the same way, off the SAME per-victim decide, which
# never read `healthy` before or after this fix. The other six decoy rows
# (the three origin-object stories, whose healthy world decides nothing)
# do not move. 14 of the 263 rows change in total, byte for byte, and
# each only in the assistant message and the meta that mirrors it.
EVAL_SET_SHA256 = "b962dad6c287f06832058bb4be7e899f3dc0d6a21f1f8cd3881bdc9f626f01e7"
```

Add the matching entry to `contract/PIN.md`, after the last existing entry
(the 2026-09-16 "revert the `separate` relabel" one), in the same style,
naming the same 14-row footprint:

```markdown
# old (the file's last lines)
  `:845`). The override is removed; `**r.meta`'s derived label stands
  again. Every job-3 number measured against the `separate` re-pin above
  is retired.

# new
  `:845`). The override is removed; `**r.meta`'s derived label stands
  again. Every job-3 number measured against the `separate` re-pin above
  is retired.

- **2026-09-19 — `_render_shared_origin`'s decided-row fix.** Both hashes
  moved again. A decided victim's row cause and rationale used to render
  the row's formatted `shared_cause` sentence even when the rules had
  already decided that victim on its own local evidence; they now render
  the rules' own answer (`result.cause`, `_rule_rationale(result)`)
  instead, and a `none`-labeled row's summary no longer claims a shared
  cause it did not find — it now says kubeagent's rules did not confirm
  one cause on two or more workloads. The footprint was measured by
  building the exam at the pre-fix commit and at the fixed one and diffing
  every row: exactly 14 of the 263 rows change, byte for byte, and nothing
  else does — the ten `shared_origin_probe` rows (244-253, inside the
  frozen slice, which is why `FROZEN_253_SHA256` moved) plus 4 of the ten
  `shared_origin_decoy_probe` rows (254-263, outside it — the two origins
  whose victims decide the same way regardless of `healthy`; the other six
  decoy rows, whose healthy world decides nothing, do not move). Each of
  the 14 changed rows differs only in the assistant message and, inside
  `meta`, only `expected`/`expected_cause`. The exam's own job 3, oracle-
  read, stays at 1.0 after the fix (5 of 5 `shared`-labeled rows, 34 of 34
  `none`-labeled rows), and the graded-view pin (`tests/
  test_exam_graded_view.py`) passes unchanged, so this re-pin is the two
  hashes only — no other frozen artifact moved.
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_training.py -q`
Expected: `50 passed`.

Then the full suite and ruff:

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: `720 passed, 6 warnings`; ruff `All checks passed!`.

**Measured:**

| metric | value |
|---|---|
| new file `tests/test_shared_origin_decided.py`, before the fix | 10 failed, 4 passed |
| ...after the fix | 14 passed |
| ripple, live failures before the fix (9 test IDs, 8 functions) | `test_probe_wide.py`, `test_propagation.py` x3, `test_shared_origin_decoy_probe.py` x4 (one parametrized twice) |
| ripple, defensive-only (no failure before the fix) | `test_probe_cousins.py`, `test_shared_origin_training.py` |
| ...after the fix, those 5 files together | 110 passed, 2 failed (the two hash pins, green after Step 7) |
| `tests/test_shared_origin_decoy_probe.py`, after the ripple fix | 15 passed |
| `tests/test_oracle.py` job3, train | rate 1.0, n 2263 (shared n 0, separate n 1 rate 1.0, none n 2262 rate 1.0) |
| `tests/test_oracle.py` job3, val | rate 1.0, n 265 (shared n 0, separate n 0, none n 265 rate 1.0) |
| exam oracle job1 (gate 2) | 138.0 / 157, 19 misses, all `contradiction_probe` |
| exam oracle job3 (gate 2) | rate 1.0, n 39 (shared n 5 rate 1.0, none n 34 rate 1.0) |
| footprint check (gate 5), rows changed | 14 of 263 |
| ...row numbers (1-based) | 244-253, 254, 258, 260, 263 |
| ...bad entries (fields outside the two allowed) | 0 |
| graded-view pin after the fix | 2 passed |
| `FROZEN_253_SHA256` | `b327cc397c0e0550881791be5d7d14c45bce5d9030a11fd5d5f2c5d4d6be6faf` |
| `EVAL_SET_SHA256` | `b962dad6c287f06832058bb4be7e899f3dc0d6a21f1f8cd3881bdc9f626f01e7` |
| full suite | 720 passed, 6 warnings |

No STOP: the footprint is exactly the 14 rows the spec names, the
graded-view pin holds, and the exam's own job 3 stays at 1.0, so the
re-pin in Step 7 stands.

> **Deviation from the spec:** the spec's gate 5 wording describes the
> footprint by field name ("the assistant message and `meta["expected"]`/
> workloads' `expected_cause`"); this task's check verifies that
> description by walking every key path in every one of the 263 rows,
> rather than trusting it, and found no exception. No other deviation.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add contract/PIN.md src/kubeagent_verdict/dataset/cases.py \
    tests/test_oracle.py tests/test_probe_cousins.py tests/test_probe_wide.py \
    tests/test_propagation.py tests/test_shared_origin_decided.py \
    tests/test_shared_origin_decoy_probe.py tests/test_shared_origin_training.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s \
    -m "fix(dataset): render a decided shared-origin victim's own cause" \
    -m "_render_shared_origin used to print the row's formatted shared_cause sentence for every victim, even one the rules had already decided on its own local evidence. It now renders the rules' own cause and rationale for a decided victim, and the summary line is label-driven: a none-labeled row no longer claims a shared cause it did not find." \
    -m "Re-pins FROZEN_253_SHA256 and EVAL_SET_SHA256 in test_shared_origin_training.py. Measured footprint: exactly 14 of 263 exam rows change (the ten shared_origin_probe rows plus 4 of the ten shared_origin_decoy_probe rows), each only in the assistant message and meta[\"expected\"]/expected_cause. The exam's own job 3 stays at 1.0 and the graded-view pin is unaffected."
```

### Task 6: a ruled registry story fills in its own victim count

**Spec:** §4 "Registry count", §4 "Registry hosts"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/objects.py` (`validate`, the
  registry branch)
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_render_shared_origin`)
- Test: `tests/test_objects.py`
- Test: `tests/test_propagation.py`

**Interfaces:**
- Consumes: `objects.Object`, `objects.validate` (existing);
  `render.bind(obj, names)` (existing -- formats every string field of
  `obj` against a plain dict via `.format(**names)`); `cases._render_shared_origin`,
  `cases._propagation_names` (existing); `propagation.all_scenarios()`,
  the `"registry-unreachable"` eval scenario's `origin_object` (existing,
  `name="registry.example.com"`).
- Produces: a registry `Object.scan_reason` may now be the literal string
  `"{count}"` as well as a digit string; `_render_shared_origin` fills that
  template in with the row's own rendered victim count before binding, and
  rewrites every drawn victim's image to the origin registry's own host.
  Task 7's six ruled stories depend on both: the two ruled registry stories
  declare `scan_reason="{count}"` on their origin object.

This is the fix for the bug the exam's row 252 disclosed: kubeagent's
rules pass builds a registry cause string as
`f"registry {name} ({count} workloads failing to pull)"`, where `count`
came from a scan-time count baked into the story as a fixed digit. A row
that rendered fewer victims than that fixed digit still had the rules
pass claim the bigger number, because nothing tied the digit to how many
victims the row actually drew. The fix ties the two together: the count
is now filled in when the row renders, always equal to what the row
shows.

- [ ] **Step 1: Write the failing tests**

`tests/test_objects.py` -- add right before
`test_refute_gives_each_kind_its_healthy_ending`:

```python
def test_registry_scan_reason_accepts_the_count_template():
    """A ruled registry story fills `scan_reason` in at render time (spec
    section 4, "Registry count"): the literal template string `"{count}"`
    must construct, alongside the digit strings every other registry
    object already uses."""
    registry(scan_reason="{count}")
```

`tests/test_propagation.py` -- add right after
`test_registry_unreachable_shared_read_agrees_with_the_declared_object` and
before `test_shared_origin_wrappers_merge_the_new_meta_without_losing_existing_keys`
(`from dataclasses import replace` and `propagation` are already imported
at the top of this file):

```python
def test_registry_count_template_fills_in_the_rendered_victim_count():
    """A ruled registry story's `scan_reason` is the literal `"{count}"`
    template (spec section 4, "Registry count"): `_render_shared_origin`
    fills it in with however many victims that row actually renders. This
    is the fix for the bug the exam's row 252 disclosed, where a fixed
    count baked into `scan_reason` (`"3"`) stayed "3" even on a row that
    rendered only 2 victims, so the rules pass's own cause line claimed
    more workloads than the row showed.
    """
    import random

    from kubeagent_verdict.dataset import cases

    base = next(s for s in propagation.all_scenarios() if s.key == "registry-unreachable")
    p = replace(base, origin_object=replace(
        base.origin_object, name="mirror.invalid", scan_reason="{count}"))

    two = cases.shared_origin(p, random.Random(1), victims=2)
    assert "registry mirror.invalid (2 workloads failing to pull)" in two.user

    three = cases.shared_origin(p, random.Random(1), victims=3)
    assert "registry mirror.invalid (3 workloads failing to pull)" in three.user


def test_registry_origin_rewrites_victim_images_to_the_declared_host():
    """Spec section 4, "Registry hosts": a ruled registry story's victim
    images are rewritten to the story's own host at render time, with no
    random draw, so the row never shows a victim pulling from a registry
    other than the one the origin object names."""
    import random

    from kubeagent_verdict.dataset import cases

    base = next(s for s in propagation.all_scenarios() if s.key == "registry-unreachable")
    p = replace(base, origin_object=replace(base.origin_object, name="mirror.invalid"))

    e = cases.shared_origin(p, random.Random(4), victims=3)
    assert "registry.example.com/" not in e.user
    assert e.user.count("mirror.invalid/") >= 3


def test_registry_example_com_host_is_a_no_op_rewrite():
    """The exam's own registry story already names `registry.example.com`
    -- the rewrite must leave its images untouched so the exam's rows and
    hashes do not move."""
    import dataclasses
    import random

    from kubeagent_verdict.dataset import cases

    p = next(s for s in propagation.all_scenarios() if s.key == "registry-unreachable")
    assert p.origin_object.name == "registry.example.com"

    drawn, _scope = cases._propagation_names(p, random.Random(9), 3)
    rewritten = [
        dataclasses.replace(n, image=p.origin_object.name + n.image[n.image.index("/"):])
        for n in drawn
    ]
    assert [n.image for n in drawn] == [n.image for n in rewritten]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_objects.py::test_registry_scan_reason_accepts_the_count_template tests/test_propagation.py::test_registry_count_template_fills_in_the_rendered_victim_count tests/test_propagation.py::test_registry_origin_rewrites_victim_images_to_the_declared_host tests/test_propagation.py::test_registry_example_com_host_is_a_no_op_rewrite -q`

Expected: FAIL -- `3 failed, 1 passed`.
- `test_registry_scan_reason_accepts_the_count_template`: `ValueError: object registry/mirror.invalid: scan_reason must be the count of workloads failing to pull` -- `objects.validate`'s registry branch rejects anything that is not all digits.
- `test_registry_count_template_fills_in_the_rendered_victim_count`: the same `ValueError`, raised while building the test's `Propagation` (a registry `Object`'s `__post_init__` calls `validate` immediately).
- `test_registry_origin_rewrites_victim_images_to_the_declared_host`: `AssertionError: assert 'registry.example.com/' not in ...` -- the rewrite does not exist yet, so victim images still read `registry.example.com/<ns>/<name>:v<X>.<Y>.<Z>`.
- `test_registry_example_com_host_is_a_no_op_rewrite` passes already -- it only checks the rewrite formula in isolation, with no dependency on `_render_shared_origin`'s own code path, so it stays green through Step 3 as a standing regression check.

- [ ] **Step 3: Implement**

`src/kubeagent_verdict/dataset/objects.py`, in `validate`, the registry
(`else`) branch -- old:

```python
    else:
        if not obj.scan_reason.isdigit():
            raise _err(obj, "scan_reason must be the count of workloads failing to pull")
        if obj.placement != "":
            raise _err(obj, "placement must be empty on a registry")
        if f.how == "read" and f.literal and f.literal not in PULL_LITERALS:
            raise _err(obj, "literal must be one of the pull literals or empty")
```

new:

```python
    else:
        if obj.scan_reason != "{count}" and not obj.scan_reason.isdigit():
            raise _err(obj, "scan_reason must be the count of workloads failing to "
                            'pull, or the "{count}" template filled in at render time')
        if obj.placement != "":
            raise _err(obj, "placement must be empty on a registry")
        if f.how == "read" and f.literal and f.literal not in PULL_LITERALS:
            raise _err(obj, "literal must be one of the pull literals or empty")
```

`src/kubeagent_verdict/dataset/cases.py`, in `_render_shared_origin` --
old (right after `drawn, scope_value = _propagation_names(p, rng, count)`):

```python
    drawn, scope_value = _propagation_names(p, rng, count)
    # The pinned field is identical across `drawn`, so formatting the shared
```

new:

```python
    drawn, scope_value = _propagation_names(p, rng, count)
    # A ruled registry story's victim images move to the origin's own host
    # (spec section 4, "Registry hosts"): every drawn Names' image is
    # rewritten from names.draw()'s default `registry.example.com/...` to
    # `<host>/...`, no rng draw. For registry.example.com -- the exam's own
    # host -- the two strings are equal, so this is a no-op and the exam's
    # rows and hashes do not move.
    if p.origin_object is not None and p.origin_object.kind == "registry":
        host = p.origin_object.name
        drawn = [dataclasses.replace(n, image=host + n.image[n.image.index("/"):])
                for n in drawn]
    # The pinned field is identical across `drawn`, so formatting the shared
```

and, further down in the same function, in the per-victim loop -- old:

```python
        names_dict = dataclasses.asdict(n)
        key = f"{n.ns}/{n.name}"
        if p.origin_object is not None:
```

new:

```python
        names_dict = dataclasses.asdict(n)
        # A ruled registry story's scan_reason may be the literal "{count}"
        # template (spec section 4, "Registry count"): filled in here with
        # however many victims THIS row renders, so the rules pass's own
        # cause line never claims a workload count the row does not show.
        # A harmless no-op for every other story -- render.bind's .format()
        # only consumes a key a template actually names.
        names_dict["count"] = str(count)
        key = f"{n.ns}/{n.name}"
        if p.origin_object is not None:
```

Both edits stay outside the `row_cause`/`_rule_rationale`/summary
(`lines = [...]`) block further down in the same loop -- that block is
Task 5's, and this task does not touch it.

- [ ] **Step 4: Run it green, then the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`

Expected: `724 passed` (measured baseline of 720 after Task 5, plus this
task's 4 new tests); ruff `All checks passed!`. The 720 baseline is Task
5's own Step 4 count -- if Tasks 1-5 land with a different count in the
real repo, read the suite's own total rather than trusting `724`
literally.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/objects.py \
    tests/test_objects.py tests/test_propagation.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "$(cat <<'EOF'
fix(dataset): let a ruled registry story fill in its own victim count

objects.validate now accepts the literal "{count}" scan_reason on a
registry object, alongside a digit string. _render_shared_origin fills
it in at render time with however many victims that row renders, so
the rules pass's cause line never claims a workload count higher than
what the row shows -- the bug the exam's row 252 disclosed.

Also rewrite a registry-origin row's victim images to the story's own
host right after names are drawn, no rng draw. For registry.example.com
this is a no-op, so the exam's rows and hashes do not move.
EOF
)"
```

Measured (this commit's own diff): `4 files changed, 89 insertions(+),
2 deletions(-)`. Verified standalone on top of Task 5 (`724 passed`, ruff
clean) and again with Task 7 applied on top of it (`769 passed`, ruff
clean) -- the combination needed no fix beyond the two commits below.

### Task 7: six ruled stories give the rules pass a shared origin to confirm

**Spec:** §4 "Six ruled stories" (table, rules each story relies on, authoring rules, coherence)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (new, appended after `trainable_scenarios()`: `_RULED_NODE_1`, `_RULED_NODE_2`, `_RULED_PVC_1`, `_RULED_PVC_2`, `_RULED_REGISTRY_1`, `_RULED_REGISTRY_2`, `_RULED_SCENARIOS`, `ruled_scenarios()`)
- Test: `tests/test_ruled_scenarios.py` (new file)

**Interfaces:**
- Consumes: `Propagation`, `Object`, `Fresh`, `Victim` (existing dataclasses in `propagation.py`); `propagation.all_scenarios()`, `propagation.trainable_scenarios()` (existing); `cases.shared_origin`, `cases.shared_origin_decoy`, `cases._render_shared_origin` (existing -- Task 6's registry `{count}` fill-in and host rewrite already live in this file, both exercised by this task's registry stories); `cases.SHARED_CLAIM_PHRASES` (existing); `vocab.ISSUE_KINDS` (existing).
- Produces: `propagation.ruled_scenarios() -> tuple[Propagation, ...]`, six stories in a pool separate from `trainable_scenarios()` -- merging the two pools so training draws from them is Task 9, not this one, so no pool count moves yet. Every story here sets `origin_object` (unlike most of `trainable_scenarios()`), so every victim's `decide_objects` all point at the same object: the rules pass can confirm all of them at once and `rules.label` reports `"shared"`. The healthy twin overrides `healthy_origin_fresh` so the same object refutes instead, and the label flips to `"none"`.

> **Note:** measured against the combined Task 1-7 build: the baseline
> after Task 5 is `720 passed`, after Task 6 (this task's registry fix)
> `724 passed`, and after this task's six stories `769 passed` (see
> Steps 2 and 4 below). If Tasks 1-6 land with a different count in the
> real repo, read the suite's own total rather than trusting these
> numbers literally.
>
> **Fresh-eyes check on this task's stories.** Before finalizing the six
> stories below, an earlier draft of the two ruled registry stories
> copied the exam's own `_REGISTRY` phrasing and named a fixed victim
> count inside the free-form origin content itself ("distinct registry
> hosts in the failing set: N"). Spec section 4's "registry content
> carries no counts" rule forbids that: the whole point of Task 6's
> `{count}` template is that the row's own rendered count is the only
> count that appears anywhere in the row, never a second, fixed one
> baked into the origin text alongside it. That phrasing is not present
> in the stories below -- it was found and removed before this task's
> commit, and `test_ruled_registry_content_carries_no_count_and_names_no_workload`
> (Step 1) now guards against it returning. A second, independent
> check against every other rule spec section 4 lists -- storage
> classes new and unused, registry hosts new and unused, the exam-only
> label set, the phrase rule, the banned-identifier rule, the node
> stories' lease/heartbeat rule, and the rendered-row coherence checks
> across victim counts and salts -- found nothing else wrong.

> **Test-file scope.** This task adds one self-contained `tests/test_ruled_scenarios.py` rather than parametrizing the existing functions in `test_shared_origin_training.py` over `ruled_scenarios()`. Those existing functions build their assertions around `trainable_scenarios()`'s specific shape (`SIZE`/`SEED` generation fixtures, the `_by_case` split), and retrofitting them to also walk a second, structurally-identical-but-separate pool would touch shared fixtures Task 8 and Task 9 still need to extend for the unverified twin and the pool merge. A new file covers every rule spec §4 lists -- eval/trainable disjointness, the authoring-floor bundle, the exam-only label pin (checked against both pools), the phrase and leak rules, and the coherence checks -- against `ruled_scenarios()` on its own, and is easy to fold into the existing file's fixtures later if Task 9's pool merge makes that the better shape.

- [ ] **Step 1: Write the failing test**

`tests/test_ruled_scenarios.py` (new file):

```python
"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.ruled_scenarios()` is a pool separate from
`trainable_scenarios()` -- merging the two is a later task -- but it has to
clear the same authoring floor and the same eval-disjointness rules that
pool already clears, which is why several checks below mirror a named test
in `test_shared_origin_training.py` rather than inventing a new shape.

Mechanically, a ruled story's BROKEN twin puts every victim on the SAME
origin object, so the rules pass confirms each one against the same group
key and `rules.label` reports "shared"; the HEALTHY twin overrides that
object's fresh read (`healthy_origin_fresh`), every victim comes back
refuted, and the label flips to "none". That is asserted directly, by
rendering both twins, rather than trusted from the story's shape.
"""

import random
import re

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, propagation

RULED = propagation.ruled_scenarios()
TRAINABLE = propagation.trainable_scenarios()
EVAL = propagation.all_scenarios()

NODE_KEYS = {"node-kubelet-halted", "node-kubelet-unresponsive"}
PVC_STORAGE_CLASSES = {
    "pvc-provisioner-not-responding": "capacity-hdd",
    "pvc-storageclass-missing": "cache-nvme",
}
REGISTRY_KEYS = {"registry-mirror-unreachable", "registry-rate-limited"}

# Spec section 4: the four labels the EXAM already pins to one origin each.
# A trainable or ruled story that reused one would let the model answer from
# the label alone, so neither pool may declare it.
_EXAM_ONLY_LABELS = frozenset({
    "describe kube-system/coredns (Deployment)",
    "get_related storageclass standard",
    "get_events (cluster-wide, reason=Failed)",
    "get_related networkpolicy {ns}/default-deny",
})

# Duplicated from score.py's own vocabulary rather than imported, matching
# how score.py itself keeps its shared-claim and independence phrase tuples
# separate. cases.SHARED_CLAIM_PHRASES is the shared-claim half.
_INDEPENDENCE_PHRASES = (
    "separate reasons", "separate causes", "independent", "independently",
    "unrelated", "distinct causes", "different causes", "not related",
    "no shared", "no common",
)

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL = re.compile(r"https?://")


def _victim_blob(v):
    parts = [v.reason, v.evidence, v.log_cause, v.local_cause, v.local_reason,
             v.read[0], v.read[1], v.healthy_read_content, v.healthy_evidence]
    parts += list(v.network_policies)
    return parts


def _scenario_blob(p):
    parts = [p.origin, p.shared_cause, p.shared_reason, p.distractor_cause,
             p.distractor_reason, p.rationale, p.remedy, p.origin_read[0],
             p.origin_read[1], p.healthy_origin_content, p.origin_state[0],
             p.origin_state[1], p.notes]
    for broken, healthy in p.origin_variants:
        parts += [broken, healthy]
    for v in p.victims:
        parts += _victim_blob(v)
    return parts


# ---------------------------------------------------------------- the pool

def test_a_ruled_scenario_pool_exists_with_six_stories():
    assert len(RULED) == 6


def test_ruled_scenario_keys_are_disjoint_from_eval_and_trainable():
    ruled_keys = {p.key for p in RULED}
    assert len(ruled_keys) == len(RULED), "a ruled key repeats within the pool"
    assert not ruled_keys & {p.key for p in EVAL}
    assert not ruled_keys & {p.key for p in TRAINABLE}


def test_no_ruled_scenario_reuses_an_eval_or_trainable_answer_string():
    """Mirrors `test_no_trainable_scenario_reuses_an_eval_answer_string`:
    a ruled story's `shared_cause`/`distractor_cause` must not equal one
    from either existing pool, or a pass could be explained by having seen
    the string rather than having read the evidence."""
    def answers(pool):
        out = set()
        for p in pool:
            out.add(p.shared_cause)
            out.add(p.distractor_cause)
        return out

    ruled_answers = answers(RULED)
    assert len(ruled_answers) == 2 * len(RULED), "a ruled answer repeats within the pool"
    assert not ruled_answers & answers(EVAL)
    assert not ruled_answers & answers(TRAINABLE)


def test_no_ruled_scenario_shares_a_local_cause_with_trainable():
    """Mirrors `test_no_two_trainable_scenarios_share_a_local_cause`."""
    def local_causes(pool):
        return [v.local_cause for p in pool for v in p.victims]

    ruled_causes = local_causes(RULED)
    assert len(ruled_causes) == len(set(ruled_causes)), "a ruled local_cause repeats"
    assert not set(ruled_causes) & set(local_causes(TRAINABLE))


@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
def test_every_ruled_scenario_obeys_the_authoring_floor(p):
    """Mirrors `test_trainable_scenarios_obey_every_rule_the_eval_table_obeys`."""
    assert p.blast_radius in ("cluster", "node", "namespace")
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p.key)
    assert 2 <= len(p.victims) <= 4
    assert p.shared_verdict != "attributed"
    assert p.confidence in ("high", "medium", "low")
    for v in p.victims:
        assert v.issue in vocab.ISSUE_KINDS
        assert v.pass_confidence in ("high", "medium", "low")
    local_causes = [v.local_cause for v in p.victims]
    assert len(local_causes) == len(set(local_causes))


def test_blast_radius_and_scope_field_agree_for_every_ruled_scenario():
    scope_for_radius = {"cluster": None, "node": "node", "namespace": "ns"}
    for p in RULED:
        assert p.scope_field == scope_for_radius[p.blast_radius], p.key


def test_every_ruled_scenario_has_at_least_three_victims():
    for p in RULED:
        assert len(p.victims) >= 3, p.key


def test_pass_confidence_varies_within_every_ruled_scenario():
    for p in RULED:
        grades = {v.pass_confidence for v in p.victims}
        assert len(grades) > 1, p.key


def test_every_ruled_scenario_carries_a_healthy_origin_read():
    for p in RULED:
        assert p.healthy_origin_content.strip(), p.key


def test_every_ruled_scenario_declares_at_least_four_origin_variants():
    for p in RULED:
        assert len(p.origin_variants) >= 4, p.key
        assert p.origin_variants[0] == (p.origin_read[1], p.healthy_origin_content), p.key


def test_every_ruled_variant_first_line_is_literal_and_unique_within_its_scenario():
    for p in RULED:
        first_lines = []
        for broken, healthy in p.origin_variants:
            for text in (broken, healthy):
                line = text.split("\n")[0]
                assert line, p.key
                assert "{" not in line, (p.key, line)
                first_lines.append(line)
        assert len(first_lines) == len(set(first_lines)), p.key


def test_every_ruled_scenario_names_its_state_in_words():
    for p in RULED:
        broken_token, healthy_token = p.origin_state
        assert broken_token and any(ch.isalpha() for ch in broken_token), p.key
        assert healthy_token and any(ch.isalpha() for ch in healthy_token), p.key
        for broken, healthy in p.origin_variants:
            assert broken_token in broken and broken_token not in healthy, p.key
            assert healthy_token in healthy and healthy_token not in broken, p.key


def test_a_ruled_victim_read_never_asserts_a_broken_origin_on_the_healthy_half():
    for p in RULED:
        broken_token = p.origin_state[0]
        for v in p.victims:
            if broken_token in v.read[1]:
                assert v.healthy_read_content, (p.key, v.workload_kind)
                assert broken_token not in v.healthy_read_content, (p.key, v.workload_kind)


def test_no_ruled_scenario_text_carries_a_banned_identifier_shape():
    """Mirrors `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`."""
    for p in RULED:
        blob = "\n".join(_scenario_blob(p))
        assert not _IPV4.search(blob), p.key
        assert not _URL.search(blob), p.key
        assert "kubeconfig" not in blob.lower(), p.key
        assert "/home/" not in blob, p.key
        assert "@" not in blob, p.key


def test_no_ruled_scenario_phrase_leaks_a_shared_or_independence_claim():
    """Spec section 4, 'Phrases': origin, shared_cause and remedy contain no
    independence phrase and no shared-claim phrase, so the wording itself
    cannot give the label away."""
    banned = tuple(x.lower() for x in cases.SHARED_CLAIM_PHRASES) + _INDEPENDENCE_PHRASES
    for p in RULED:
        for field_name in ("origin", "shared_cause", "remedy"):
            text = getattr(p, field_name).lower()
            for phrase in banned:
                assert phrase not in text, (p.key, field_name, phrase)


def test_ruled_origin_read_label_is_never_an_exam_only_label():
    """Spec section 4: the pinned exam-only label set. A trainable OR ruled
    story's origin_read label must never be one of the four."""
    for p in list(RULED) + list(TRAINABLE):
        assert p.origin_read[0] not in _EXAM_ONLY_LABELS, p.key


# --------------------------------------------------------- story-specific

def test_ruled_node_stories_never_mention_a_lease_or_heartbeat():
    for p in RULED:
        if p.key not in NODE_KEYS:
            continue
        blob = "\n".join(_scenario_blob(p)).lower()
        assert "lease" not in blob, p.key
        assert "heartbeat" not in blob, p.key


def test_ruled_pvc_storage_classes_are_new_and_plain():
    taken = {"fast-ssd", "standard", "ssd-premium", "block-ssd", "archive-hdd",
             "encrypted-ssd", "bulk-nvme", "replicated-ssd"}
    seen = set()
    for p in RULED:
        if p.key not in PVC_STORAGE_CLASSES:
            continue
        sc = PVC_STORAGE_CLASSES[p.key]
        assert sc not in taken, sc
        assert sc not in seen, sc
        seen.add(sc)
        alphabet = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
        assert sc and all(ch in alphabet for ch in sc), sc
        assert p.origin_object.fresh.storage_class == sc
        assert p.healthy_origin_fresh.storage_class == sc
        # Spec section 4, "Healthy PVC and registry content": the
        # storage-class read names no specific claim, container or image --
        # none of the four Names placeholders appears anywhere in it, so it
        # reads true for every claim in the row, not just one.
        for placeholder in ("{pvc}", "{pod}", "{image}", "{name}"):
            assert placeholder not in p.origin_read[1], (p.key, placeholder)
            assert placeholder not in p.healthy_origin_content, (p.key, placeholder)
            for broken, healthy in p.origin_variants:
                assert placeholder not in broken, (p.key, placeholder)
                assert placeholder not in healthy, (p.key, placeholder)


def test_ruled_registry_hosts_are_new_and_scan_reason_is_the_count_template():
    seen = set()
    for p in RULED:
        if p.key not in REGISTRY_KEYS:
            continue
        host = p.origin_object.name
        assert host not in ("registry.example.com",), host
        assert host not in seen, host
        seen.add(host)
        assert p.origin_object.scan_reason == "{count}", p.key
        assert p.origin_object.fresh.literal in (
            "no such host", "toomanyrequests"), p.key
        assert p.healthy_origin_fresh.literal == "manifest unknown", p.key
        for v in p.victims:
            assert v.issue in ("ImagePullBackOff", "ErrImagePull"), (p.key, v.issue)


_WORKLOAD_KINDS = ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob")


_COUNT_PHRASE = re.compile(
    r"\d+\s*(workloads?|pods?|replicas?|hosts?|instances?|callers?)\b",
    re.IGNORECASE,
)


def test_ruled_registry_content_carries_no_count_and_names_no_workload():
    """Spec section 4, "Healthy PVC and registry content": a registry
    story's own scan_reason is the `{count}` template filled in at render
    time (Task 6), so the free-form origin content must never also bake in
    a fixed count of its own -- that would either duplicate the rendered
    number by luck or contradict it on a row that draws a different one.
    A response code or port number is not a count (e.g. "429" or "200" in
    a status-code reading), so the check targets a digit next to a
    countable noun rather than every digit. Registry content also names no
    workload kind: the origin is about the registry, not one caller of it.
    """
    for p in RULED:
        if p.key not in REGISTRY_KEYS:
            continue
        texts = [p.origin_read[1], p.healthy_origin_content]
        for broken, healthy in p.origin_variants:
            texts += [broken, healthy]
        for text in texts:
            assert not _COUNT_PHRASE.search(text), (p.key, text)
            for kind in _WORKLOAD_KINDS:
                assert kind not in text, (p.key, kind, text)


# ----------------------------------------------------------- rendered rows

@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
@pytest.mark.parametrize("victims", (2, 3))
def test_ruled_scenario_renders_shared_on_broken_and_none_on_healthy(p, victims):
    for salt in (1, 2, 3, 4, 5):
        broken = cases.shared_origin(p, random.Random(salt), victims=victims)
        healthy = cases.shared_origin_decoy(p, random.Random(salt), victims=victims)
        assert broken.meta["label"] == "shared", (p.key, victims, salt)
        assert healthy.meta["label"] == "none", (p.key, victims, salt)


@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
def test_ruled_scenario_coherence_across_victim_counts_and_salts(p):
    """Spec section 4, 'Coherence', checked on the RENDERED row rather than
    the literal alone: the broken twin's origin read carries the broken
    state word, the healthy twin's carries the healthy one, and a node
    story never renders a lease or heartbeat mention either way."""
    broken_token, healthy_token = p.origin_state
    for victims in (2, 3):
        for salt in (1, 2, 3):
            r_broken = cases._render_shared_origin(p, random.Random(salt), victims,
                                                    healthy=False)
            r_healthy = cases._render_shared_origin(p, random.Random(salt), victims,
                                                     healthy=True)
            assert broken_token in r_broken.user, (p.key, victims, salt)
            assert healthy_token in r_healthy.user, (p.key, victims, salt)
            if p.key in NODE_KEYS:
                assert "lease" not in r_broken.user.lower()
                assert "heartbeat" not in r_broken.user.lower()
                assert "lease" not in r_healthy.user.lower()
                assert "heartbeat" not in r_healthy.user.lower()
            if p.key in PVC_STORAGE_CLASSES:
                assert PVC_STORAGE_CLASSES[p.key] in r_broken.user
            if p.key in REGISTRY_KEYS:
                host = p.origin_object.name
                assert host in r_broken.user
                assert p.origin_object.fresh.literal in r_broken.user


@pytest.mark.parametrize(
    "key,host", [("registry-mirror-unreachable", "mirror.invalid"),
                 ("registry-rate-limited", "registry.invalid")])
def test_ruled_registry_row_names_its_own_rendered_victim_count(key, host):
    """The Task 6 fix (spec section 4, 'Registry count'), applied to the real
    ruled registry stories rather than a scenario built in the test: the
    rules pass's own cause line names however many victims THIS row draws,
    never a fixed digit."""
    p = next(s for s in RULED if s.key == key)
    for victims in (2, 3):
        r = cases._render_shared_origin(p, random.Random(7), victims, healthy=False)
        assert f"registry {host} ({victims} workloads failing to pull)" in r.user
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_ruled_scenarios.py -q`

Expected: FAIL -- a collection error, not individual test failures, because `RULED = propagation.ruled_scenarios()` runs at import time:
```
ERROR tests/test_ruled_scenarios.py - AttributeError: module 'kubeagent_verdict.dataset.propagation' has no attribute 'ruled_scenarios'. Did you mean: 'all_scenarios'?
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

- [ ] **Step 3: Implement**

Append to the end of `src/kubeagent_verdict/dataset/propagation.py`, right after the existing `trainable_scenarios()` function:

```python
_RULED_NODE_1 = Propagation(
    key="node-kubelet-halted",
    blast_radius="node",
    scope_field="node",
    origin="a node's kubelet process crashed outright, so the node reports "
           "Ready False",
    shared_cause="node {node}'s kubelet process crashed and the node reports "
                 "Ready False, so the pods it held cannot come back on it",
    shared_reason="{node} shows Ready False and its kubelet reports no "
                  "successful status update",
    distractor_cause="an operator cordoned {node} for planned maintenance",
    distractor_reason="{node} carries no cordon annotation and stays "
                      "schedulable",
    rationale="the workload's symptom is what a crashed kubelet on {node} "
              "does to it, not a change in the workload itself",
    remedy="Restart the kubelet on {node} or replace the node; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_object=Object(kind="node", name="{node}", scan_reason="NotReady",
                          placement="on", fresh=Fresh(ready="False"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(ready="True"),
    origin_read=(
        "describe node {node}",
        ("Ready condition: False\nConditions:\n"
         "  Ready   False   KubeletNotReady   PLEG is not healthy: pleg was "
         "last seen active\n"
         "Taints:  node.kubernetes.io/not-ready:NoExecute\n"
         "         node.kubernetes.io/not-ready:NoSchedule"),
    ),
    healthy_origin_content=(
        "Ready condition: True\nConditions:\n"
        "  Ready   True    KubeletReady   kubelet is posting ready status\n"
        "Taints:  <none>"
    ),
    origin_variants=(
        (("Ready condition: False\nConditions:\n"
          "  Ready   False   KubeletNotReady   PLEG is not healthy: pleg was "
          "last seen active\n"
          "Taints:  node.kubernetes.io/not-ready:NoExecute\n"
          "         node.kubernetes.io/not-ready:NoSchedule"),
         ("Ready condition: True\nConditions:\n"
          "  Ready   True    KubeletReady   kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("systemd unit kubelet.service: failed\n"
          "ExitCode=137, restart suppressed by admin override\n"
          "node condition Ready: False"),
         ("systemd unit kubelet.service: active (running)\n"
          "restart count: 0\n"
          "node condition Ready: True")),
        (("node agent process: not running\n"
          "process exited 4 minutes ago and has not restarted\n"
          "node condition Ready: False"),
         ("node agent process: running\n"
          "process has been running for 9 days without a restart\n"
          "node condition Ready: True")),
        (("cluster view of the node: unreachable from the API server\n"
          "kubelet process exited with signal 9\n"
          "node condition Ready: False"),
         ("cluster view of the node: reachable from the API server\n"
          "kubelet process has not restarted\n"
          "node condition Ready: True")),
    ),
    origin_state=("False", "True"),
    victims=(
        Victim(
            workload_kind="Deployment", status="Degraded",
            issue="ContainerStartError",
            reason="the container image was resolved but the container "
                   "could not be started",
            evidence="RunContainerError: failed to create containerd task: "
                     "failed to create shim task: context deadline exceeded",
            local_cause="the container's init step waits on a config file a "
                        "sidecar has not written yet",
            local_reason="the container exits before the sidecar finishes "
                         "writing its config",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: RunContainerError: "
                   "failed to create containerd task: failed to create shim "
                   "task: context deadline exceeded")),
            healthy_read_content="Normal  Started  kubelet  Started container",
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted for {pod}",
            evidence="MountVolume.SetUp failed: rpc error: code = "
                     "DeadlineExceeded desc = context deadline exceeded",
            local_cause="the CSI node plugin on this pod's node is stuck "
                        "initializing",
            local_reason="the mount request never reaches a running CSI node "
                         "plugin",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  MountVolume.SetUp "
                   "failed: rpc error: code = DeadlineExceeded desc = "
                   "context deadline exceeded")),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="back-off restarting failed container",
            log_cause="dial tcp: i/o timeout dialing a local endpoint",
            local_cause="the agent's own retry budget runs out before its "
                        "dependency starts answering",
            local_reason="the agent gives up after a fixed retry budget "
                         "instead of waiting",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: connection attempt timed out dialing a "
                   "local endpoint (3 of 3 sampled restarts)")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_NODE_2 = Propagation(
    key="node-kubelet-unresponsive",
    blast_radius="node",
    scope_field="node",
    origin="a node's kubelet stopped answering the control plane, so its "
           "status reads Unknown",
    shared_cause="node {node} reports Ready Unknown because its kubelet "
                 "stopped answering the control plane, so the pods it held "
                 "are gone",
    shared_reason="{node} shows Ready Unknown and the control plane cannot "
                  "reach its kubelet at all",
    distractor_cause="a rollout paused every workload on {node} mid-deploy",
    distractor_reason="every controller on {node} still reports its prior "
                      "generation as current",
    rationale="the workload's symptom is what {node} going unreachable does "
              "to it, not a change in the workload itself",
    remedy="Restore network reachability to {node} or replace it; the "
           "flagged workloads need no change.",
    confidence="high",
    origin_object=Object(kind="node", name="{node}", scan_reason="NotReady",
                          placement="on", fresh=Fresh(ready="Unknown"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(ready="True"),
    origin_read=(
        "describe node {node}",
        ("Ready condition: Unknown\nConditions:\n"
         "  Ready   Unknown   NodeStatusUnknown   node has not responded to "
         "the control plane\n"
         "Taints:  node.kubernetes.io/unreachable:NoExecute\n"
         "         node.kubernetes.io/unreachable:NoSchedule"),
    ),
    healthy_origin_content=(
        "Ready condition: True\nConditions:\n"
        "  Ready   True    KubeletReady   kubelet is posting ready status\n"
        "Taints:  <none>"
    ),
    origin_variants=(
        (("Ready condition: Unknown\nConditions:\n"
          "  Ready   Unknown   NodeStatusUnknown   node has not responded to "
          "the control plane\n"
          "Taints:  node.kubernetes.io/unreachable:NoExecute\n"
          "         node.kubernetes.io/unreachable:NoSchedule"),
         ("Ready condition: True\nConditions:\n"
          "  Ready   True    KubeletReady   kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("control plane connection to the node: timed out\n"
          "the node has not been reachable this cycle\n"
          "node condition Ready: Unknown"),
         ("control plane connection to the node: established\n"
          "the node answered this cycle\n"
          "node condition Ready: True")),
        (("node network interface: no response to any probe\n"
          "every probe to the node has failed this cycle\n"
          "node condition Ready: Unknown"),
         ("node network interface: responds to every probe\n"
          "every probe to the node has succeeded this cycle\n"
          "node condition Ready: True")),
        (("kube-apiserver's node watcher: marked the node unreachable\n"
          "no update has arrived from this node\n"
          "node condition Ready: Unknown"),
         ("kube-apiserver's node watcher: marked the node reachable\n"
          "updates keep arriving from this node\n"
          "node condition Ready: True")),
    ),
    origin_state=("Unknown", "True"),
    victims=(
        Victim(
            workload_kind="Deployment", status="Degraded", issue="RestartLoop",
            reason="container {container} keeps restarting on this node",
            evidence="Back-off restarting failed container {container}",
            local_cause="a leftover lock file from a prior run blocks the "
                        "container's own startup",
            local_reason="the container's own init step refuses to proceed "
                         "while the lock file exists",
            read=("get_events {ns}/{name}",
                  ("Warning  BackOff  kubelet  Back-off restarting failed "
                   "container {container}")),
            healthy_read_content="Normal  Started  kubelet  Started container",
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="StatefulSet", status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to this pod's node",
            evidence="AttachVolume.Attach failed: rpc error: code = "
                     "Unavailable desc = the node is not answering attach "
                     "requests",
            local_cause="a second pod on a different node already holds the "
                        "exclusive attachment for {pvc}",
            local_reason="the attach controller reports the claim already "
                         "attached from elsewhere",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nAccess Modes: RWO\n"
                   "Attached to node: {node}  (node condition Ready: "
                   "Unknown)")),
            healthy_read_content=(
                "Status: Bound\nAccess Modes: RWO\n"
                "Attached to node: {node}  (node condition Ready: True)"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="Degraded", issue="ProbeFailure",
            reason="container {container}'s readiness probe fails from this "
                   "node",
            evidence="Readiness probe failed: dial tcp: i/o timeout",
            local_cause="the probe's own timeout is shorter than the "
                        "dependency it checks ever answers within",
            local_reason="the probe fails on its own schedule, regardless of "
                         "what is reachable",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Unhealthy  kubelet  Readiness probe "
                   "failed: dial tcp: i/o timeout")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_PVC_1 = Propagation(
    key="pvc-provisioner-not-responding",
    blast_radius="cluster",
    scope_field=None,
    origin="the dynamic provisioner for one storage class stopped "
           "responding to new claims",
    shared_cause="the capacity-hdd storage class's provisioner is not "
                 "responding, so no claim against it can bind",
    shared_reason="no PersistentVolume on the capacity-hdd class has bound "
                  "cluster-wide in the current window",
    distractor_cause="a namespace quota is refusing new pods",
    distractor_reason="the quota reports well under its pod limit in every "
                      "namespace",
    rationale="the workload is waiting on a capacity-hdd volume that "
              "nothing is left to create",
    remedy="Restore the capacity-hdd provisioner; the pending claims bind "
           "on their own afterwards.",
    confidence="high",
    origin_object=Object(kind="pvc", name="{pvc}",
                          scan_reason="ProvisionerNotResponding",
                          placement="mounted",
                          fresh=Fresh(phase="Pending",
                                     storage_class="capacity-hdd"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(phase="Bound", storage_class="capacity-hdd"),
    origin_read=(
        "get_related storageclass capacity-hdd",
        ("provisioner status: stalled\n"
         "provisioner: example.com/capacity-hdd-csi\n"
         "controller capacity-hdd-provisioner: 0/1 ready, CrashLoopBackOff\n"
         "PersistentVolumes bound on this class in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "provisioner status: healthy\n"
        "provisioner: example.com/capacity-hdd-csi\n"
        "controller capacity-hdd-provisioner: 1/1 ready, Running\n"
        "PersistentVolumes bound on this class in the last 20m: 6"
    ),
    origin_variants=(
        (("provisioner status: stalled\n"
          "provisioner: example.com/capacity-hdd-csi\n"
          "controller capacity-hdd-provisioner: 0/1 ready, CrashLoopBackOff\n"
          "PersistentVolumes bound on this class in the last 20m: 0"),
         ("provisioner status: healthy\n"
          "provisioner: example.com/capacity-hdd-csi\n"
          "controller capacity-hdd-provisioner: 1/1 ready, Running\n"
          "PersistentVolumes bound on this class in the last 20m: 6")),
        (("controller capacity-hdd-provisioner: CrashLoopBackOff, restart "
          "count climbing\n"
          "provisioner status: stalled\n"
          "last successful provision: none this window"),
         ("controller capacity-hdd-provisioner: Running, no restarts\n"
          "provisioner status: healthy\n"
          "last successful provision: within the last minute")),
        (("capacity-hdd claims waiting on a volume: 4\n"
          "provisioner status: stalled\n"
          "provisioner pod is not accepting new work"),
         ("capacity-hdd claims waiting on a volume: 0\n"
          "provisioner status: healthy\n"
          "provisioner pod is accepting new work")),
        (("capacity-hdd provision requests: queued, none completing\n"
          "provisioner status: stalled\n"
          "the provisioner container has not emitted a log line this "
          "window"),
         ("capacity-hdd provision requests: none queued, all completing\n"
          "provisioner status: healthy\n"
          "the provisioner container is emitting log lines normally")),
    ),
    origin_state=("stalled", "healthy"),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending",
            issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the claim asks for more capacity than any volume in "
                        "the pool can offer",
            local_reason="the claim never leaves Pending because no volume "
                         "that size exists",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: capacity-hdd\n"
                   "Events: Normal  ExternalProvisioning  waiting for a "
                   "volume to be created by the external provisioner")),
            healthy_read_content=(
                "Status: Bound\nStorageClass: capacity-hdd\n"
                "Events: Normal  ProvisioningSucceeded  successfully "
                "provisioned volume"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the Job's own retry backoff keeps it from ever "
                        "re-requesting the claim",
            local_reason="the pod template's own restart policy stalls the "
                         "request rather than retrying it",
            read=("get_events {ns}/{name}",
                  ("Normal  WaitForFirstConsumer  persistentvolume-controller "
                   " waiting for first consumer to be created before "
                   "binding\n"
                   "Normal  ExternalProvisioning  waiting for a volume to be "
                   "created")),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the "
                     "condition",
            local_cause="the filesystem on {pvc} needs an fsck that has not "
                        "been triggered",
            local_reason="the mount times out rather than failing outright",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  Unable to attach "
                   "or mount volumes: unmounted volumes=[{pvc}], timed out "
                   "waiting for the condition")),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)

_RULED_PVC_2 = Propagation(
    key="pvc-storageclass-missing",
    blast_radius="cluster",
    scope_field=None,
    origin="a storage class every new claim names was deleted, so nothing "
           "on it can provision",
    shared_cause="the cache-nvme storage class no longer exists, so no "
                 "claim naming it can bind",
    shared_reason="cache-nvme is absent from the cluster's storage class "
                  "list and every claim on it stays Pending",
    distractor_cause="the cluster autoscaler is refusing to add capacity",
    distractor_reason="the autoscaler reports headroom on every existing "
                      "node",
    rationale="the workload is waiting on a cache-nvme volume that no "
              "storage class exists to create",
    remedy="Recreate the cache-nvme storage class; the pending claims bind "
           "on their own afterwards.",
    confidence="high",
    origin_object=Object(kind="pvc", name="{pvc}",
                          scan_reason="MissingStorageClass",
                          placement="mounted",
                          fresh=Fresh(phase="Pending",
                                     storage_class="cache-nvme"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(phase="Bound", storage_class="cache-nvme"),
    origin_read=(
        "get_related storageclass cache-nvme",
        ("storage class lookup: missing\n"
         "requested class: cache-nvme\n"
         "matching StorageClass objects in the cluster: 0\n"
         "PersistentVolumeClaims stuck Pending on this class: 5"),
    ),
    healthy_origin_content=(
        "storage class lookup: present\n"
        "requested class: cache-nvme\n"
        "matching StorageClass objects in the cluster: 1\n"
        "PersistentVolumeClaims bound on this class in the last 20m: 4"
    ),
    origin_variants=(
        (("storage class lookup: missing\n"
          "requested class: cache-nvme\n"
          "matching StorageClass objects in the cluster: 0\n"
          "PersistentVolumeClaims stuck Pending on this class: 5"),
         ("storage class lookup: present\n"
          "requested class: cache-nvme\n"
          "matching StorageClass objects in the cluster: 1\n"
          "PersistentVolumeClaims bound on this class in the last 20m: 4")),
        (("PersistentVolumeClaims referencing cache-nvme: 5 Pending\n"
          "storage class lookup: missing\n"
          "no provisioner is registered for this class name"),
         ("PersistentVolumeClaims referencing cache-nvme: 0 Pending, 4 "
          "Bound\n"
          "storage class lookup: present\n"
          "a provisioner is registered for this class name")),
        (("cluster storage class list: cache-nvme is absent\n"
          "storage class lookup: missing\n"
          "no operator has recreated it since it was removed"),
         ("cluster storage class list: cache-nvme is present\n"
          "storage class lookup: present\n"
          "the class has been recreated and claims are binding again")),
        (("admission check for new claims naming cache-nvme: rejected, "
          "unknown class\n"
          "storage class lookup: missing\n"
          "every new claim on this class fails at admission"),
         ("admission check for new claims naming cache-nvme: accepted\n"
          "storage class lookup: present\n"
          "new claims on this class pass admission normally")),
    ),
    origin_state=("missing", "present"),
    victims=(
        Victim(
            workload_kind="StatefulSet", status="Pending",
            issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the StatefulSet's replica count outgrew the volumes "
                        "already provisioned for it",
            local_reason="the newest replica's claim is the only one still "
                         "Pending",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Pending\nStorageClass: cache-nvme\n"
                   "Events: Warning  ProvisioningFailed  "
                   "persistentvolume-controller  storageclass.storage.k8s.io "
                   '"cache-nvme" not found')),
            healthy_read_content=(
                "Status: Bound\nStorageClass: cache-nvme\n"
                "Events: Normal  ProvisioningSucceeded  successfully "
                "provisioned volume"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="Pending", issue="Unschedulable",
            reason="pod has unbound immediate PersistentVolumeClaims",
            evidence="0/4 nodes are available: 4 pod has unbound immediate "
                     "PersistentVolumeClaims",
            local_cause="the Job's claim template was copied from a cluster "
                        "that used a different class name",
            local_reason="the claim requests a class name this cluster never "
                         "had",
            read=("get_events {ns}/{name}",
                  ("Warning  ProvisioningFailed  persistentvolume-controller "
                   ' storageclass.storage.k8s.io "cache-nvme" not found')),
            healthy_read_content=(
                "Normal  ProvisioningSucceeded  persistentvolume-controller "
                " successfully provisioned volume for this claim"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Deployment", status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted",
            evidence="MountVolume.SetUp failed: timed out waiting for the "
                     "condition",
            local_cause="a stale CSI socket file on this pod's node blocks "
                        "the mount",
            local_reason="the mount times out rather than failing outright",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  FailedMount  kubelet  Unable to attach "
                   "or mount volumes: unmounted volumes=[{pvc}], timed out "
                   "waiting for the condition")),
            pass_confidence="low",
            on_origin=True,
        ),
    ),
)

_RULED_REGISTRY_1 = Propagation(
    key="registry-mirror-unreachable",
    blast_radius="cluster",
    scope_field=None,
    origin="the cluster's image mirror stopped resolving in DNS, so every "
           "pull through it fails before any manifest is requested",
    shared_cause="the mirror.invalid registry cannot be resolved, so no "
                 "workload pulling through it can start",
    shared_reason="every pull naming mirror.invalid fails at DNS "
                  "resolution, before any manifest is requested",
    distractor_cause="the images were removed from the mirror's catalog",
    distractor_reason="the pulls never get far enough to ask for a "
                      "manifest",
    rationale="the workload cannot start because the mirror it pulls from "
              "cannot be resolved at all, which is true of every image "
              "behind it right now",
    remedy="Restore DNS resolution for mirror.invalid; no workload manifest "
           "needs editing.",
    confidence="high",
    origin_object=Object(kind="registry", name="mirror.invalid",
                          scan_reason="{count}", placement="",
                          fresh=Fresh(literal="no such host"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(literal="manifest unknown"),
    origin_read=(
        "get_events (cluster-wide, type=Warning)",
        ("pulls through mirror.invalid: all failing\n"
         "every pod pulling through mirror.invalid reports the same "
         "error:\n"
         "  Failed to pull image: rpc error: code = Unknown desc = failed "
         "to resolve reference: dial tcp: lookup mirror.invalid: no such "
         "host"),
    ),
    healthy_origin_content=(
        "pulls through mirror.invalid: succeeding\n"
        "pods pulling through mirror.invalid report ordinary image errors, "
        "not connection errors:\n"
        "  Failed to pull image: rpc error: code = Unknown desc = manifest "
        "unknown"
    ),
    origin_variants=(
        (("pulls through mirror.invalid: all failing\n"
          "every pod pulling through mirror.invalid reports the same "
          "error:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = failed "
          "to resolve reference: dial tcp: lookup mirror.invalid: no such "
          "host"),
         ("pulls through mirror.invalid: succeeding\n"
          "pods pulling through mirror.invalid report ordinary image "
          "errors, not connection errors:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "manifest unknown")),
        (("DNS lookup for mirror.invalid: NXDOMAIN\n"
          "resolution failures this window: every pull naming "
          "mirror.invalid\n"
          "sample error: dial tcp: lookup mirror.invalid: no such host"),
         ("DNS lookup for mirror.invalid: resolves normally\n"
          "resolution failures this window: none naming mirror.invalid\n"
          "sample error: manifest unknown")),
        (("mirror.invalid reachability probe: failed\n"
          "every image pull naming this host times out at resolution\n"
          "sample error: no such host"),
         ("mirror.invalid reachability probe: succeeded\n"
          "image pulls naming this host resolve and proceed to the "
          "manifest\n"
          "sample error: manifest unknown")),
        (("image pull error clustering: one failure mode, one host\n"
          "all failures name mirror.invalid and the same resolution "
          "error\n"
          "sample error: no such host"),
         ("image pull error clustering: ordinary per-image errors\n"
          "failures name several images behind mirror.invalid, no "
          "resolution error among them\n"
          "sample error: manifest unknown")),
    ),
    origin_state=("no such host", "manifest unknown"),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the image tag {image} was retagged and no longer "
                        "points at a built image",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image "
                   "{image}: dial tcp: lookup mirror.invalid: no such "
                   "host")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image "
                "{image}: manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull",
            issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            local_cause="the image reference for {image} was built against "
                        "a registry path this cluster never mirrors",
            local_reason="the pull fails before the image layers are "
                         "fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  failed to resolve reference: "
                   "dial tcp: lookup mirror.invalid: no such host")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  failed to resolve reference: "
                "manifest unknown"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container "
                     "{init_container}",
            local_cause="the init container's image name carries a typo "
                        "that only this Job's template has",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n"
                   "    State: Waiting\n    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  dial tcp: lookup "
                   "mirror.invalid: no such host")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)

_RULED_REGISTRY_2 = Propagation(
    key="registry-rate-limited",
    blast_radius="cluster",
    scope_field=None,
    origin="the image registry is throttling every pull from inside the "
           "cluster",
    shared_cause="registry.invalid is rate-limiting the cluster's pulls, so "
                 "no workload pulling from it can finish",
    shared_reason="every pull naming registry.invalid fails with the same "
                  "rate-limit response, before any manifest is served",
    distractor_cause="a new admission policy blocks the affected pods' "
                     "image references",
    distractor_reason="the policy's own audit log shows no denial for any "
                      "of the affected pods",
    rationale="the workload cannot start because the registry it pulls "
              "from is throttling every request right now, which is true "
              "of every image behind it",
    remedy="Raise or clear the rate limit on registry.invalid; no workload "
           "manifest needs editing.",
    confidence="high",
    origin_object=Object(kind="registry", name="registry.invalid",
                          scan_reason="{count}", placement="",
                          fresh=Fresh(literal="toomanyrequests"),
                          intent="cause"),
    healthy_origin_fresh=Fresh(literal="manifest unknown"),
    origin_read=(
        "get_events (cluster-wide, type=Warning)",
        ("pulls from registry.invalid: all rate-limited\n"
         "every pod pulling from registry.invalid reports the same error:\n"
         "  Failed to pull image: rpc error: code = Unknown desc = "
         "toomanyrequests: too many requests to registry.invalid"),
    ),
    healthy_origin_content=(
        "pulls from registry.invalid: succeeding\n"
        "pods pulling from registry.invalid report ordinary image errors, "
        "not rate-limit errors:\n"
        "  Failed to pull image: rpc error: code = Unknown desc = manifest "
        "unknown"
    ),
    origin_variants=(
        (("pulls from registry.invalid: all rate-limited\n"
          "every pod pulling from registry.invalid reports the same "
          "error:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "toomanyrequests: too many requests to registry.invalid"),
         ("pulls from registry.invalid: succeeding\n"
          "pods pulling from registry.invalid report ordinary image "
          "errors, not rate-limit errors:\n"
          "  Failed to pull image: rpc error: code = Unknown desc = "
          "manifest unknown")),
        (("registry.invalid response code on every pull: 429\n"
          "rate-limit window: exceeded for the whole cluster\n"
          "sample error: toomanyrequests"),
         ("registry.invalid response code on every pull: 200 to the "
          "manifest request\n"
          "rate-limit window: not exceeded\n"
          "sample error: manifest unknown")),
        (("registry.invalid request budget: exhausted\n"
          "every pull queues behind the same limit\n"
          "sample error: toomanyrequests"),
         ("registry.invalid request budget: available\n"
          "pulls proceed without queuing\n"
          "sample error: manifest unknown")),
        (("pull error signature across the cluster: single host, single "
          "failure mode\n"
          "all failures name registry.invalid and the same rate-limit "
          "error\n"
          "sample error: toomanyrequests"),
         ("pull error signature across the cluster: many hosts, many "
          "failure modes\n"
          "failures name several images behind registry.invalid, no "
          "rate-limit error among them\n"
          "sample error: manifest unknown")),
    ),
    origin_state=("toomanyrequests", "manifest unknown"),
    victims=(
        Victim(
            workload_kind="Deployment", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="container {container} cannot pull {image}",
            evidence="Back-off pulling image {image}",
            local_cause="the image {image} was deleted from the registry's "
                        "catalog",
            local_reason="the pull is retried and backed off repeatedly",
            read=("describe {ns}/{pod} (Pod)",
                  ("Events: Warning  Failed  kubelet  Failed to pull image "
                   "{image}: toomanyrequests: too many requests to "
                   "registry.invalid")),
            healthy_read_content=(
                "Events: Warning  Failed  kubelet  Failed to pull image "
                "{image}: manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
        Victim(
            workload_kind="DaemonSet", status="ErrImagePull",
            issue="ErrImagePull",
            reason="container {container} cannot pull {image}",
            evidence="failed to resolve reference for {image}",
            local_cause="the image {image} was built for a different CPU "
                        "architecture than this node runs",
            local_reason="the pull fails before the image layers are "
                         "fetched",
            read=("get_events {ns}/{name}",
                  ("Warning  Failed  kubelet  Error: ErrImagePull\n"
                   "Warning  Failed  kubelet  toomanyrequests: too many "
                   "requests to registry.invalid")),
            healthy_read_content=(
                "Warning  Failed  kubelet  Error: ErrImagePull\n"
                "Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="medium",
            on_origin=True,
        ),
        Victim(
            workload_kind="Job", status="ImagePullBackOff",
            issue="ImagePullBackOff",
            reason="init container {init_container} cannot pull its image",
            evidence="Back-off pulling image for init container "
                     "{init_container}",
            local_cause="the init container's image reference still names a "
                        "tag that was retired last release",
            local_reason="the init container never starts",
            read=("describe {ns}/{pod} (Pod)",
                  ("Init Containers:\n  {init_container}:\n"
                   "    State: Waiting\n    Reason: ImagePullBackOff\n"
                   "  Warning  Failed  kubelet  toomanyrequests: too many "
                   "requests to registry.invalid")),
            healthy_read_content=(
                "Init Containers:\n  {init_container}:\n"
                "    State: Waiting\n    Reason: ImagePullBackOff\n"
                "  Warning  Failed  kubelet  manifest unknown"),
            pass_confidence="high",
            on_origin=True,
        ),
    ),
)


_RULED_SCENARIOS = (_RULED_NODE_1, _RULED_NODE_2, _RULED_PVC_1, _RULED_PVC_2,
                    _RULED_REGISTRY_1, _RULED_REGISTRY_2)


def ruled_scenarios() -> tuple[Propagation, ...]:
    """The six stories whose origin the rules pass itself decides (spec
    section 4). Not part of `trainable_scenarios()` -- the pool merge is a
    later task."""
    return _RULED_SCENARIOS
```

- [ ] **Step 4: Run it green, then the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`

Expected: `769 passed` (measured baseline of 724 after Task 6, plus this
task's 45 new tests); ruff `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/propagation.py tests/test_ruled_scenarios.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "$(cat <<'EOF'
feat(dataset): add six ruled stories so the rules pass can confirm a shared origin

trainable_scenarios() had no story where a shared-origin row's victims
all point at the same origin object, so the rules pass never got a
chance to confirm one and training carried no shared-labelled rows from
that path. ruled_scenarios() adds six: two node (Ready False, Ready
Unknown), two PVC (ProvisionerNotResponding on capacity-hdd,
MissingStorageClass on cache-nvme), and two registry (mirror.invalid,
registry.invalid, both using the {count} template from the prior
commit). Every story's healthy twin overrides the origin's fresh read
so every victim comes back refuted and the label flips from shared to
none.

tests/test_ruled_scenarios.py covers the pool the same way the existing
trainable-scenario tests cover theirs: key and answer disjointness
against eval and trainable, the authoring-floor bundle, first-line and
state-token checks, banned-identifier and phrase-leak checks, the two
new storage classes and two new registry hosts, the pinned exam-only
label set (checked against both pools), and a rendered check across
victim counts and salts that the broken twin always labels shared and
the healthy twin always labels none.
EOF
)"
```

Measured (this commit's own diff): `2 files changed, 1148 insertions(+)`.
Full suite with this commit applied on top of Task 6: `769 passed, 6
warnings`; ruff `All checks passed!`.

### Task 8: the unverified node twin (spec section 5)

**Spec:** §5 "The unverified twin (node only)"

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_render_shared_origin`, `shared_origin`)
- Test: `tests/test_ruled_scenarios.py`

**Interfaces:**
- Consumes: `objects.unverify(obj, how)` (existing -- `how="read_failed"` on
  a node object sets `fresh=Fresh(how="read_failed", message=f'nodes
  "{obj.name}" is forbidden')`, already imported into `cases.py` as
  `unverify`); `rules._check_node`, `rules.decide`, `rules.shared`,
  `rules.label` (existing -- an unverified node outcome still decides,
  `shared()` only groups `confirmed` outcomes, so an all-unverified set of
  victims labels `"none"`); `propagation.ruled_scenarios()` (Task 7 --
  every story's `origin_object`, node, PVC or registry); `cases._fmt`,
  `cases._rule_rationale`, `cases._answer` (existing).
- Produces: `cases._render_shared_origin(p, rng, victims, healthy=False,
  unverified=False)` and `cases.shared_origin(p, rng, victims=None,
  unverified=False)` -- a third, broken-world variant that a node-origin
  ruled story can render, where the origin read fails outright instead of
  confirming or refuting anything. `unverified=True` on any other story
  (a PVC origin, a registry origin, or `origin_object is None`) raises
  `ValueError`. Task 9's selection loop is the first caller that passes
  `unverified=True` for real; this task only adds the capability and
  tests it directly.

This is spec section 5's "one node pair in three" mechanism: the rules
pass sometimes cannot confirm a shared cause at all, because the one read
that would confirm it -- describing the node -- is itself forbidden. The
origin read's content changes to a failed read, `objects.unverify` marks
the bound origin object's fresh state as `"read_failed"` before the rules
pass sees it, and every victim decides `"unverified"` instead of
`"confirmed"`. `rules.shared()` only groups confirmed outcomes, so the
label comes back `"none"` -- the same value the healthy twin already
produces, but for a different reason, under the same "did not confirm one
cause" summary a mixed-outcome broken row already uses. A PVC or registry
origin, or a story with no origin object, has no coherent way to render
this: a PVC origin is named per claim (one read per victim, so there is
no single origin read to fail), and a registry origin's unverified ending
would contradict the broken pull events the victims already show (spec
section 5). Both raise rather than rendering something incoherent.

- [ ] **Step 1: Write the failing tests**

`tests/test_ruled_scenarios.py` -- add `import json` next to the existing
`import random` / `import re` block, and `from kubeagent_verdict.evals
import score` next to the existing `from kubeagent_verdict.dataset import
cases, propagation`:

```python
import json
import random
import re

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, propagation
from kubeagent_verdict.evals import score
```

Then append, at the end of the file, after
`test_ruled_registry_row_names_its_own_rendered_victim_count`:

```python
# --------------------------------------------------- the unverified twin

# Spec section 5: one node pair in three gets an unverified broken twin
# instead of the confirmed one. `shared_origin(..., unverified=True)` is
# only ever the BROKEN half -- there is no unverified decoy variant --
# so every check below compares it against the plain broken twin's
# names/menus/labels (both consume the rng identically: the origin
# variant draw, then one draw per victim's own name) and against the
# healthy twin's summary shape only where the two are expected to differ.

PVC_KEYS = set(PVC_STORAGE_CLASSES)
NOT_NODE_KEYS = PVC_KEYS | REGISTRY_KEYS


@pytest.mark.parametrize("key", sorted(NOT_NODE_KEYS))
def test_unverified_true_raises_for_a_ruled_pvc_or_registry_story(key):
    p = next(s for s in RULED if s.key == key)
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(p, random.Random(1), 2, unverified=True)


def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = next(s for s in TRAINABLE if s.origin_object is None)
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(plain, random.Random(1), 2, unverified=True)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_labels_none_with_the_did_not_confirm_summary(key, victims):
    p = next(s for s in RULED if s.key == key)
    for salt in (1, 2, 3, 4, 5):
        r = cases._render_shared_origin(p, random.Random(salt), victims, unverified=True)
        assert r.meta["label"] == "none", (key, victims, salt)
        assert r.summary.startswith(
            f"{victims} workloads are failing, and kubeagent's rules did "
            "not confirm one cause on two or more of them."), (key, victims, salt)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_origin_read_says_read_failed_is_forbidden(key):
    p = next(s for s in RULED if s.key == key)
    r = cases._render_shared_origin(p, random.Random(1), 2, unverified=True)
    node = p.origin_object.name  # "{node}" -- the template, not the drawn value
    assert node == "{node}"
    drawn_node = r.drawn[0].node
    assert f'read failed: nodes "{drawn_node}" is forbidden' in r.user


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_every_row_decided_unverified_with_rules_cause(key, victims):
    p = next(s for s in RULED if s.key == key)
    r = cases._render_shared_origin(p, random.Random(2), victims, unverified=True)
    assert len(r.rows) == victims
    for row in r.rows:
        assert row["cause"].startswith("node ") and row["cause"].endswith("(NotReady)"), row
        assert "did not clear the earlier finding" in row["rationale"], row
        assert "is forbidden" in row["rationale"], row


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_workloads_meta_marks_decided_outcome_unverified(key):
    p = next(s for s in RULED if s.key == key)
    ex = cases.shared_origin(p, random.Random(3), victims=2, unverified=True)
    assert ex.meta["workloads"], key
    for wm in ex.meta["workloads"].values():
        assert wm["decided"] is True, key
        assert wm["decided_outcome"] == "unverified", key
        assert wm["job"] == 1, key


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_job1_accepts_every_row(key, victims):
    p = next(s for s in RULED if s.key == key)
    ex = cases.shared_origin(p, random.Random(4), victims=victims, unverified=True)
    verdicts = {row["workload"]: row for row in json.loads(ex.assistant)["verdicts"]}
    assert set(verdicts) == set(ex.meta["workloads"])
    for wkey, wm in ex.meta["workloads"].items():
        assert score.job1(wm, verdicts[wkey]) == 1.0, (key, victims, wkey)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_matches_the_healthy_twins_names_menus_and_labels(key):
    """Both calls draw the origin variant, then one name per victim, in the
    same order and with no other rng draw (the origin-object branch takes
    no `render.draw_ending` draw) -- so at the same salt the two twins'
    drawn names, candidate menus and read labels line up exactly. Only the
    origin read's own content, and the per-victim reads a broken origin
    touches, are allowed to differ."""
    p = next(s for s in RULED if s.key == key)
    for victims in (2, 3):
        for salt in (1, 2, 3):
            unverified = cases._render_shared_origin(
                p, random.Random(salt), victims, unverified=True)
            healthy = cases._render_shared_origin(
                p, random.Random(salt), victims, healthy=True)
            assert unverified.drawn == healthy.drawn, (key, victims, salt)
            assert unverified.decoys == healthy.decoys, (key, victims, salt)
            assert unverified.shared_cause == healthy.shared_cause, (key, victims, salt)
            assert unverified.distractor_cause == healthy.distractor_cause, (key, victims, salt)
            assert [r["workload"] for r in unverified.rows] == \
                [r["workload"] for r in healthy.rows], (key, victims, salt)


```

`NODE_KEYS`, `PVC_STORAGE_CLASSES` and `REGISTRY_KEYS` are the module-level
fixtures Task 7 already defined near the top of this file; this step reuses
them rather than redeclaring them.

- [ ] **Step 2: Run it and watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_ruled_scenarios.py -q -k unverified`

Expected: FAIL -- `23 failed, 45 deselected`. Every failure is the same
shape, e.g.:

```
    p = next(s for s in RULED if s.key == key)
    with pytest.raises(ValueError, match="unverified"):
>       cases._render_shared_origin(p, random.Random(1), 2, unverified=True)
E       TypeError: _render_shared_origin() got an unexpected keyword argument 'unverified'
```

(`shared_origin()` raises the same `TypeError`, with its own name, for the
tests that call it instead of `_render_shared_origin` directly.)

- [ ] **Step 3: Implement**

`src/kubeagent_verdict/dataset/cases.py` -- old text:

```python
def _render_shared_origin(p: prop.Propagation, rng: random.Random,
                          victims: int | None,
                          healthy: bool = False) -> _SharedOrigin:
    """Render one propagation scenario, in the broken world or the healthy one.

    `healthy=True` swaps the CONTENT of the origin read for
```

new text:

```python
def _render_shared_origin(p: prop.Propagation, rng: random.Random,
                          victims: int | None,
                          healthy: bool = False,
                          unverified: bool = False) -> _SharedOrigin:
    """Render one propagation scenario, in the broken world or the healthy one.

    `healthy=True` swaps the CONTENT of the origin read for
```

old text (the end of the same docstring, right before its closing `"""`):

```python
    staleness reaches one `distractor_reason` (registry-unreachable's), which
    is collateral rather than the subject; the healthy origin read refutes
    that distractor on its own.
    """
    count = len(p.victims) if victims is None else victims
```

new text:

```python
    staleness reaches one `distractor_reason` (registry-unreachable's), which
    is collateral rather than the subject; the healthy origin read refutes
    that distractor on its own.

    `unverified=True` (spec section 5) is a third, BROKEN-world variant: the
    origin read fails outright rather than confirming or refuting anything.
    It requires a node `origin_object` -- a PVC story's origin is named per
    claim, one read per victim, and a registry story's unverified endings all
    contradict the broken pull events the victims already show (see the
    spec) -- and it is mutually exclusive with `healthy`, which is a
    different, refuting world. The origin variant is still drawn, spending
    the same rng call the healthy and plain-broken twins spend, so all three
    stay in lockstep and a caller building more than one from the same salt
    gets the same names and the same candidate menus. Only the origin read's
    own content, and `objects.unverify`'s fresh read on the decided object,
    differ.
    """
    if unverified and (p.origin_object is None or p.origin_object.kind != "node"):
        raise ValueError(f"{p.key}: unverified=True requires a node origin_object "
                         "(spec section 5) -- this story has none, or a different kind")
    if unverified and healthy:
        raise ValueError(f"{p.key}: unverified and healthy are different broken/healthy "
                         "worlds and cannot both be rendered in one call")
    count = len(p.victims) if victims is None else victims
```

old text (the origin-read content line, further down the same function):

```python
    # The origin read leads: the evidence for the one cause is stated once,
    # not restated per victim, which is how a real gather would present it.
    origin_content = healthy_origin if healthy else broken_origin
    reads = [c.EvidenceRead(label=_fmt(p.origin_read[0], anchor),
                            content=_fmt(origin_content, anchor))]
```

new text:

```python
    # The origin read leads: the evidence for the one cause is stated once,
    # not restated per victim, which is how a real gather would present it.
    origin_content = healthy_origin if healthy else broken_origin
    if unverified:
        # Spec section 5: the origin read fails outright. `{node}` is the
        # same anchor field the origin_object's own name template binds to
        # below, so the read names the same node the decided cause does.
        origin_content = 'read failed: nodes "{node}" is forbidden'
    reads = [c.EvidenceRead(label=_fmt(p.origin_read[0], anchor),
                            content=_fmt(origin_content, anchor))]
```

old text (the decided-object branch, further down the same function):

```python
            decide_obj = render.bind(p.origin_object, names_dict)
            if healthy:
                decide_obj = dataclasses.replace(decide_obj, fresh=p.healthy_origin_fresh)
            decide_objects: tuple = (decide_obj,)
```

new text:

```python
            decide_obj = render.bind(p.origin_object, names_dict)
            if healthy:
                decide_obj = dataclasses.replace(decide_obj, fresh=p.healthy_origin_fresh)
            elif unverified:
                # Spec section 5: `objects.unverify`'s own "read_failed"
                # message for a node is `nodes "{name}" is forbidden` --
                # exactly what the origin read above already says, prefixed
                # with "read failed: " there and with "fresh read failed: "
                # by `rules._check_node` in the rationale.
                decide_obj = unverify(decide_obj, "read_failed")
            decide_objects: tuple = (decide_obj,)
```

old text (`shared_origin`'s signature and docstring):

```python
def shared_origin(p: prop.Propagation, rng: random.Random,
                  victims: int | None = None) -> Example:
    """TRAINING: the counterexample `multi` never gave the model.

    Same shape as `shared_origin_probe` and deliberately so, drawn from
```

new text:

```python
def shared_origin(p: prop.Propagation, rng: random.Random,
                  victims: int | None = None,
                  unverified: bool = False) -> Example:
    """TRAINING: the counterexample `multi` never gave the model.

    Same shape as `shared_origin_probe` and deliberately so, drawn from
```

old text (the end of `shared_origin`'s docstring and its call into
`_render_shared_origin`):

```python
    component healthy, and the two sets are asserted equal. It is the RAW
    template, not the formatted label -- `describe node {node}` renders
    differently per row, and a set of formatted labels would never match.
    """
    r = _render_shared_origin(p, rng, victims)
```

new text:

```python
    component healthy, and the two sets are asserted equal. It is the RAW
    template, not the formatted label -- `describe node {node}` renders
    differently per row, and a set of formatted labels would never match.

    `unverified=True` (spec section 5) renders the third, unverified-origin
    world instead of the plain broken one -- see `_render_shared_origin`.
    """
    r = _render_shared_origin(p, rng, victims, unverified=unverified)
```

`unverify` is already imported at the top of `cases.py` (`from
kubeagent_verdict.dataset.render import (... unverify, ...)`), so no
import line changes.

- [ ] **Step 4: Run it green, then the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`

Expected: `792 passed` (measured baseline of `769` after Task 7, plus this
task's 23 new tests); ruff `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/cases.py tests/test_ruled_scenarios.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "$(cat <<'EOF'
feat(dataset): add the unverified node twin (spec section 5)

_render_shared_origin and shared_origin take unverified=False. On a
node-origin ruled story, unverified=True still draws the origin
variant (keeping the rng in lockstep with the plain and healthy
twins), then overrides the origin read with "read failed: nodes
"{node}" is forbidden" and runs the bound origin object through
objects.unverify(obj, "read_failed") before the rules pass sees it.
Every victim decides unverified rather than confirmed, so
rules.shared never groups them and the label comes back none, under
the same "did not confirm one cause" summary a mixed-outcome broken
row already uses.

A PVC or registry origin, or a story with no origin object at all,
raises rather than rendering something incoherent -- see the
docstring and spec section 5 for why each is excluded.

tests/test_ruled_scenarios.py: the ValueError on every non-node
story, label/summary, the origin read text, every row's unverified
cause and rationale, workloads meta's decided_outcome, job 1
accepting every row, and the twin's names/menus/labels matching the
healthy twin's at the same salt.
EOF
)"
```

Measured (this commit's own diff): `2 files changed, 149 insertions(+), 3
deletions(-)`.
Full suite with this commit applied on top of Task 7: `792 passed, 6
warnings`; ruff `All checks passed!`.

### Task 9: merge the six ruled stories into the trainable pool

**Spec:** §6 (the pool merge, the mix move, the selection loop, both decision
checks), §7 (rulings A, C, E, F and "Other moves" -- the re-pin of every
count the merge and mix move)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (`trainable_scenarios`)
- Modify: `src/kubeagent_verdict/dataset/generate.py` (`CASE_MIX`, the
  `shared_origin`/`shared_origin_decoy` loop in `generate`)
- Test: `tests/test_generate.py`, `tests/test_probe_cousins.py`,
  `tests/test_ruled_scenarios.py`, `tests/test_shared_origin_floor.py`,
  `tests/test_evidence_overlap.py`, `tests/test_multi_collision.py`,
  `tests/test_oracle.py`, `tests/test_shared_origin_training.py`,
  `tests/test_shared_origin_training_pair.py`, `tests/test_shared_origin_decided.py`

**Interfaces:**
- Consumes: `propagation.ruled_scenarios()` (Task 7, six stories);
  `propagation._TRAINING_SCENARIOS` (existing, the 48 plain stories);
  `cases.shared_origin`/`cases.shared_origin_decoy` and their `unverified`
  flag (Task 8); `generate.counts_for`, `generate.split`,
  `generate.drop_held_out`, `generate.test_set` (existing).
- Produces: `propagation.trainable_scenarios()` now returns 54 stories (the
  48 plain ones plus the six ruled ones) instead of 48. `generate.CASE_MIX`
  moves to `attributed 6, none_of_these 11, own_cause 10, multi 13,
  shared_origin 15, shared_origin_decoy 15, truncated 5, injection 10,
  empty_candidates 5, wrong_attribution 10`. The `shared_origin`/
  `shared_origin_decoy` emission loop in `generate.generate` now walks two
  sub-pools it derives from `train_scen` itself (`plain = tuple(p for p in
  train_scen if p.origin_object is None)`, `ruled = tuple(p for p in
  train_scen if p.origin_object is not None)`) rather than one flat list --
  every fifth draw (`i % 5 == 4`) comes from `ruled`, the other four from
  `plain`. This is the plan's last dataset-shape task: nothing later
  consumes a name this task introduces.

> **Two commits, both green on their own.** The core change --
> `trainable_scenarios()`'s merge plus the mix move -- breaks close to a
> dozen existing tests at once, because several test modules read the pool
> at import time (`RULED = propagation.ruled_scenarios()`-style module
> constants, and `EXPECTED_POOL`/`DECLARED`/`CASE_MIX`-shaped literals
> elsewhere) and every one of them has to move together or the suite sits
> red between edits. Steps 1-5 below are that single commit, matching how it
> was actually built and verified: every dependent test edited alongside the
> two production edits, run to green as one unit. A second, small commit
> (Steps 6-10) adds one test spec section 7 names -- extending
> `test_a_shared_label_only_comes_from_an_origin_object` from the eval pool
> to the newly-merged trainable pool -- as its own, separately green change
> on top.

- [ ] **Step 1: Write the failing tests**

Across the nine files below, every numeric literal that depends on
`trainable_scenarios()`'s length or `CASE_MIX`'s percentages moves. Each
block shows the exact old text and the exact new text.

`tests/test_generate.py` -- `test_counts_for_follows_the_mix`, old:

```python
def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 100, "none_of_these": 150, "own_cause": 100,
                      "multi": 110, "shared_origin": 120,
                      "shared_origin_decoy": 120, "truncated": 50,
                      "injection": 100, "empty_candidates": 50,
                      "wrong_attribution": 100}
    assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed
```

new:

```python
def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 60, "none_of_these": 110, "own_cause": 100,
                      "multi": 130, "shared_origin": 150,
                      "shared_origin_decoy": 150, "truncated": 50,
                      "injection": 100, "empty_candidates": 50,
                      "wrong_attribution": 100}
    assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed
```

`tests/test_probe_cousins.py` -- module docstring, old:

```python
"""The cousin probe: one fresh twin pair per trainable scenario.

The wide probe (tests/test_probe_wide.py) asks the six held-out origins
five times each. This probe asks the 48 trained scenarios once each: 48
pairs, 96 rows, every pair at full width, so every decoy half carries three
or four verdicts. It is in-distribution on purpose. A model that reads the
origin on the scenarios it studied and still fails the exam has a coverage
problem; one that fails here has a recipe problem. It is written to its
own file, scored on its own, and decides nothing. The frozen exam does not
move.
"""
```

new:

```python
"""The cousin probe: one fresh twin pair per trainable scenario.

The wide probe (tests/test_probe_wide.py) asks the six held-out origins
five times each. This probe asks the trained scenarios once each -- 54
pairs, 108 rows since Task 9 merged the six ruled stories into
`trainable_scenarios()` (spec section 6; was 48 pairs, 96 rows) -- every
pair at full width, so every decoy half carries three or four verdicts. It
is in-distribution on purpose. A model that reads the origin on the
scenarios it studied and still fails the exam has a coverage problem; one
that fails here has a recipe problem. It is written to its own file, scored
on its own, and decides nothing. The frozen exam does not move.
"""
```

`tests/test_probe_cousins.py` -- `test_cousin_probe_counts_and_balance`, old:

```python
def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {p.key for p in propagation.trainable_scenarios()}
    assert len(trainable) == 48
    assert len(rows) == len(trainable) * 2
```

new:

```python
def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {p.key for p in propagation.trainable_scenarios()}
    # Re-measured 2026-09-19 (Task 9's pool merge, spec section 6): 48 to 54.
    assert len(trainable) == 54
    assert len(rows) == len(trainable) * 2
```

`tests/test_probe_cousins.py` -- `test_cousin_rows_are_adjacent_twins_with_unique_pair_keys`'s
docstring, old:

```python
def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    """Label-aware, the same way `test_probe_wide.py`'s twin check is (spec
    section 3, ruling C). No trainable scenario decides today -- the
    trainable pool's own oracle tests hold job 3 at 1.0 without ever
    reaching a `decided` victim -- so every cousin pair is `none`-labeled in
    practice and the `shared` branch below is future-proofing rather than a
    live path; `test_cousin_probe_uses_only_trainable_origins` above already
    pins the pool this draws from.
    """
```

new:

```python
def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    """Label-aware, the same way `test_probe_wide.py`'s twin check is (spec
    section 3, ruling C). Re-measured 2026-09-19: before Task 9, no
    trainable scenario decided, so every cousin pair was `none`-labeled and
    the `shared` branch below was future-proofing rather than a live path.
    Task 9 merged the six ruled stories into `trainable_scenarios()` (spec
    section 6); their broken-origin twins DO decide, so 6 of the 54 cousin
    pairs are now `shared`-labeled and this branch is live.
    `test_cousin_probe_uses_only_trainable_origins` above already pins the
    pool this draws from.
    """
```

`tests/test_probe_cousins.py` -- `test_cli_probe_cousins_writes_only_the_standalone_file`,
old:

```python
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 96
```

new:

```python
    lines = out.read_text(encoding="utf-8").splitlines()
    # Re-measured 2026-09-19 (Task 9's pool merge, spec section 6): 96 to 108.
    assert len(lines) == 108
```

`tests/test_ruled_scenarios.py` -- module docstring, old:

```python
"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.ruled_scenarios()` is a pool separate from
`trainable_scenarios()` -- merging the two is a later task -- but it has to
clear the same authoring floor and the same eval-disjointness rules that
pool already clears, which is why several checks below mirror a named test
in `test_shared_origin_training.py` rather than inventing a new shape.
```

new:

```python
"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.trainable_scenarios()` now returns the 48 plain
stories plus these six (spec section 6's pool merge), so every check below
that means "disjoint from the plain pool" filters `trainable_scenarios()`
down to `PLAIN` first rather than comparing against the merged pool --
comparing the six ruled stories against a pool that now contains them
would always pass, vacuously. It still has to clear the same authoring
floor and the same eval-disjointness rules the plain pool already clears,
which is why several checks below mirror a named test in
`test_shared_origin_training.py` rather than inventing a new shape.
```

`tests/test_ruled_scenarios.py` -- the module-level pool constants, old:

```python
RULED = propagation.ruled_scenarios()
TRAINABLE = propagation.trainable_scenarios()
EVAL = propagation.all_scenarios()
```

new:

```python
RULED = propagation.ruled_scenarios()
PLAIN = tuple(p for p in propagation.trainable_scenarios() if p.origin_object is None)
EVAL = propagation.all_scenarios()
```

`tests/test_ruled_scenarios.py` -- every remaining `TRAINABLE` reference
becomes `PLAIN`, in four tests. `test_ruled_scenario_keys_are_disjoint_from_eval_and_trainable`,
old: `assert not ruled_keys & {p.key for p in TRAINABLE}` -- new: `assert not
ruled_keys & {p.key for p in PLAIN}`. `test_no_ruled_scenario_reuses_an_eval_or_trainable_answer_string`,
old: `assert not ruled_answers & answers(TRAINABLE)` -- new: `assert not
ruled_answers & answers(PLAIN)`. `test_no_ruled_scenario_shares_a_local_cause_with_trainable`,
old: `assert not set(ruled_causes) & set(local_causes(TRAINABLE))` -- new:
`assert not set(ruled_causes) & set(local_causes(PLAIN))`.
`test_ruled_origin_read_label_is_never_an_exam_only_label`, old: `for p in
list(RULED) + list(TRAINABLE):` -- new: `for p in list(RULED) + list(PLAIN):`.

`tests/test_ruled_scenarios.py` -- `test_unverified_true_raises_for_a_plain_trainable_story`,
old:

```python
def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = next(s for s in TRAINABLE if s.origin_object is None)
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(plain, random.Random(1), 2, unverified=True)
```

new:

```python
def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = PLAIN[0]  # every PLAIN entry has origin_object is None, by definition
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(plain, random.Random(1), 2, unverified=True)
```

`tests/test_shared_origin_floor.py` -- append to the module docstring, old
ending:

```python
On 2026-09-08 the recipe moved to size 8000, both halves to 12 percent, and
the pool to forty-eight scenarios. That is 960 rows per half, 20 pairs per
scenario before the split. The smallest scenario keeps 13 pairs in train
and the largest 20. The floor stays at 12: the extra room is the point,
because the split still takes groups by hash, not by count.
"""
```

new:

```python
On 2026-09-08 the recipe moved to size 8000, both halves to 12 percent, and
the pool to forty-eight scenarios. That is 960 rows per half, 20 pairs per
scenario before the split. The smallest scenario keeps 13 pairs in train
and the largest 20. The floor stays at 12: the extra room is the point,
because the split still takes groups by hash, not by count.

Re-measured 2026-09-19 (Task 9: pool merge to fifty-four scenarios and both
halves to 15 percent, spec section 6). That is 1200 rows per half before
the split, 20 pairs per plain scenario and 40 per ruled scenario -- the
selection loop gives ruled stories roughly twice the plain per-story rate
by design (spec section 7 ruling A), not evenly across all fifty-four. The
smallest scenario keeps 15 pairs in train (a plain story) and the largest
39 (a ruled story). The floor stays at 12: it was set once, against the
smallest surviving count, and every scenario -- plain or ruled -- still
clears it with room to spare.
"""
```

`tests/test_evidence_overlap.py` -- the `DECLARED` dict's three
`shared_origin*` rows, old:

```python
    # THIS ROW IS THE POINT OF THE ALLOWLIST. Its rows come from
    # dataset.propagation, not the catalog, so it shares nothing -- which is
    # what shows the guard discriminates rather than rubber-stamping.
    "shared_origin_probe": (0, 34),
    # Its healthy-origin twin, and declared rather than left out on purpose:
    # an undeclared slice is not measured at all, so the guard's coverage
    # would silently lag the exam every time the exam grows. Same structural
    # reason for the zero -- the rows come from dataset.propagation, whose
    # eval scenarios never enter the training pile. It does share 6 of its 34
    # reads with `shared_origin_probe` itself, by construction: five of the
    # sixteen eval victims carry evidence that reads the same whether the
    # origin is broken or not, and those are rendered verbatim in both worlds.
    # That is sharing WITHIN the exam, which this instrument does not measure
    # and does not need to -- neither slice is anything the model studied.
    "shared_origin_decoy_probe": (0, 34),
```

new:

```python
    # THIS ROW WAS THE POINT OF THE ALLOWLIST at 0/34: its rows come from
    # dataset.propagation, not the catalog, so an eval scenario itself is
    # never trained on. That is still true. What moved is generic PVC
    # boilerplate: Task 9 (2026-09-19) merged two ruled PVC-provisioning
    # stories (`pvc-provisioner-not-responding`) into the trainable pool
    # (spec section 6), and their provisioner-stall events -- "Normal
    # WaitForFirstConsumer ... waiting for first consumer to be created" and
    # "Unable to attach or mount volumes" -- are the same generic PVC-events
    # vocabulary the eval-only `storage-provisioner-down` scenario reads.
    # After identity masking the two are byte-identical, so 3 of the eval
    # scenario's reads now land in the trained set. No eval SCENARIO is
    # trained on; a training scenario now happens to narrate the same kind
    # of PVC stall in the same event vocabulary, which is the sharing this
    # guard is built to detect and re-declare, not to prevent.
    "shared_origin_probe": (3, 34),
    # Its healthy-origin twin, declared rather than left out on purpose: an
    # undeclared slice is not measured at all, so the guard's coverage would
    # silently lag the exam every time the exam grows. One hit is the same
    # ruled-PVC boilerplate as `shared_origin_probe` above (the "Unable to
    # attach or mount volumes" read). The other comes straight from Task 9's
    # pool merge (spec section 6): "Normal Started kubelet Started container"
    # is generic enough that it also appears verbatim on the two ruled
    # node-story training rows (`node-kubelet-halted`,
    # `node-kubelet-unresponsive`), and that merge is what first puts those
    # two stories in the trained pool at all. The shared text is kubelet
    # boilerplate both stories happen to narrate the same way, not the exam's
    # own wording. It also still shares 6 of its 34 reads with
    # `shared_origin_probe` itself, by construction: five of the sixteen
    # eval victims carry evidence that reads the same whether the origin is
    # broken or not, and those are rendered verbatim in both worlds. That is
    # sharing WITHIN the exam, which this instrument does not measure and
    # does not need to.
    "shared_origin_decoy_probe": (2, 34),
```

`tests/test_multi_collision.py` -- module docstring, old:

```python
No story in today's trainable pool declares a registry `origin_object`
(the two ruled registry stories are a later task), so the registry rule
is unit-tested against a synthetic story only; the build-level test
confirms that absence directly against `propagation.trainable_scenarios`
rather than assuming it.
"""
```

new:

```python
Two ruled registry stories are in the trainable pool now (spec section 6's
pool merge), so the registry-drop branch is exercised for real during a
build, not only against the synthetic story the unit tests still use.
"""
```

`tests/test_multi_collision.py` -- the registry build-level test, old:

```python
def test_no_trainable_story_declares_a_registry_origin_yet():
    """The registry rule is exercised only synthetically today: no story in
    the trainable pool sets a registry `origin_object` (that is a later
    task's addition), so a build never reaches the registry-drop branch.
    This pins that absence directly rather than assuming it."""
    assert not any(
        s.origin_object is not None and s.origin_object.kind == "registry"
        for s in prop.trainable_scenarios())
```

new:

```python
def test_a_real_registry_healthy_origin_read_is_dropped_next_to_its_own_candidate(monkeypatch):
    """The registry branch of `_resolve_multi_healthy_origin` (spec section 2)
    used to be exercised only synthetically: no story in the trainable pool
    set a registry `origin_object`, so a build never reached the
    registry-drop branch. `trainable_scenarios()` now includes the two ruled
    registry stories (spec section 6's pool merge), so it does. This spies
    on the real per-row decision during the exact `kv-dataset --seed 17
    --size 8000` build: a registry-story healthy origin is kept only when no
    victim in that row carries a registry candidate of its own, and dropped
    (the function returns `None`) whenever one does -- against the real
    rotation and RNG stream, not a hand-picked replay.
    """
    calls: list[tuple[bool, bool]] = []  # (row has a registry candidate, kept)
    original = cases._resolve_multi_healthy_origin

    def spy(healthy_origin, h, all_objects):
        result = original(healthy_origin, h, all_objects)
        if (healthy_origin.origin_object is not None
                and healthy_origin.origin_object.kind == "registry"):
            has_candidate = any(obj.kind == "registry" for obj in all_objects)
            calls.append((has_candidate, result is not None))
        return result

    monkeypatch.setattr(cases, "_resolve_multi_healthy_origin", spy)
    generate.generate(seed=17, size=8000)

    assert calls, "the rotation must reach at least one registry story"
    for has_candidate, kept in calls:
        assert kept != has_candidate, (has_candidate, kept)

    dropped = sum(1 for _, kept in calls if not kept)
    # Measured over this exact build (seed 17, size 8000): 12 multi rows draw
    # a registry-story healthy origin; the rule drops 2 of them and keeps 10.
    assert (len(calls), dropped) == (12, 2)
```

`tests/test_multi_collision.py` -- `test_no_real_healthy_node_read_names_a_clashing_node`'s
final assertion, old:

```python
    # Measured over this exact build (seed 17, size 8000): 79 multi rows
    # draw a node-story healthy origin; the rule keeps 41, renames 37 and
    # drops 1.
    assert (len(calls), kept, renamed, dropped) == (79, 41, 37, 1)
```

new:

```python
    # Re-measured 2026-09-19 over this exact build (seed 17, size 8000)
    # after the mix and pool changes in spec section 6: 96 multi rows draw a
    # node-story healthy origin; the rule keeps 59, renames 35 and drops 2.
    assert (len(calls), kept, renamed, dropped) == (96, 59, 35, 2)
```

`tests/test_oracle.py` -- six functions move together. `test_oracle_job1_is_perfect_on_train`,
old: `assert board["jobs"]["job1"] == {"rate": 1.0, "n": 2570}` -- new (with
a comment line added above it): `# Re-measured 2026-09-19 (Task 9: pool
merge + mix change, spec section 6) -- 2570 to 3056. Rate unchanged at
1.0.` then `assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3056}`.
`test_oracle_job1_is_perfect_on_val`, old: `assert board["jobs"]["job1"] ==
{"rate": 1.0, "n": 289}` -- new (comment `# Re-measured 2026-09-19, same
reason. 289 to 355. Rate unchanged.` above): `assert board["jobs"]["job1"]
== {"rate": 1.0, "n": 355}`. `test_oracle_job2_gate_is_perfect_on_train`,
old: `assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3121}`
-- new (comment `# Re-measured 2026-09-19, same reason. 3121 to 2975. Rate
unchanged.` above): `assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0,
"n": 2975}`. `test_oracle_job2_gate_is_perfect_on_val`, old: `assert
_job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 352}` -- new (comment
`# Re-measured 2026-09-19, same reason. 352 to 304. Rate unchanged.` above):
`assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 304}`.

`tests/test_oracle.py` -- `test_oracle_job2_keyword_only_matches_the_spec_measurement`,
old:

```python
def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect."""
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2175}
```

new:

```python
def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect.

    Re-measured 2026-09-19 (Task 9: pool merge + mix change, spec section
    6) -- 2175 to 2286. Rate still 1.0."""
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2286}
```

`tests/test_oracle.py` -- `test_oracle_job3_is_perfect_on_train`, old:

```python
def test_oracle_job3_is_perfect_on_train():
    """Task 5's label-driven summary: every gold summary in the built
    dataset matches its own row's label, train side. `shared` never
    appears here -- no trainable scenario decides today (see
    `test_shared_origin_training.py`'s docstring on the same point) -- and
    `separate` is `multi`'s own bucket, not a shared-origin one; the
    `_render_shared_origin` `ValueError` guards a label `rules.label` can
    never actually return, not this one."""
    board = score.scoreboard(list(_train_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 2263,
        "by_label": {"shared": {"rate": None, "n": 0},
                     "separate": {"rate": 1.0, "n": 1},
                     "none": {"rate": 1.0, "n": 2262}}}
```

new:

```python
def test_oracle_job3_is_perfect_on_train():
    """Task 5's label-driven summary: every gold summary in the built
    dataset matches its own row's label, train side. `separate` is
    `multi`'s own bucket, not a shared-origin one; the
    `_render_shared_origin` `ValueError` guards a label `rules.label` can
    never actually return, not this one.

    `shared` used to read 0 here: no trainable scenario decided, so a
    trained row was never labeled `shared` (see
    `test_shared_origin_training.py`'s docstring on the same point, before
    Task 9). Task 9 (2026-09-19) merged the six ruled stories into
    `trainable_scenarios()` (spec section 6); their broken-origin twins DO
    decide, and every one of those trained rows carries the `shared` label.
    This test now covers those ruled rows too: the gold summary for each
    of them still matches its own label, so `shared`'s rate stays a
    perfect 1.0 here -- spec section 10 gate 1, job 1 and job 3 still 1.0
    after the pool merge."""
    board = score.scoreboard(list(_train_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 2790,
        "by_label": {"shared": {"rate": 1.0, "n": 192},
                     "separate": {"rate": 1.0, "n": 1},
                     "none": {"rate": 1.0, "n": 2597}}}
```

`tests/test_oracle.py` -- `test_oracle_job3_is_perfect_on_val`, old:

```python
def test_oracle_job3_is_perfect_on_val():
    board = score.scoreboard(list(_val_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 265,
        "by_label": {"shared": {"rate": None, "n": 0},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 265}}}
```

new:

```python
def test_oracle_job3_is_perfect_on_val():
    """Val side of the same extension: 22 of the split's rows are a ruled
    story's broken twin, labeled `shared`, and the gold summary matches on
    every one -- re-measured 2026-09-19, Task 9."""
    board = score.scoreboard(list(_val_results()))
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 336,
        "by_label": {"shared": {"rate": 1.0, "n": 22},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 314}}}
```

`tests/test_oracle.py` -- `test_oracle_multi_job1_matches_the_spec_measurement`,
old:

```python
def test_oracle_multi_job1_matches_the_spec_measurement():
    """The exact number spec section 1 cites for the `multi` fix alone:
    every decided `multi` workload passes job1, 996 of 996 in train and
    121 of 121 in val."""
    def multi_job1(results):
        scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
        return sum(scores), len(scores)

    assert multi_job1(_train_results()) == (996.0, 996)
    assert multi_job1(_val_results()) == (121.0, 121)
```

new:

```python
def test_oracle_multi_job1_matches_the_spec_measurement():
    """The exact number spec section 1 cites for the `multi` fix alone:
    every decided `multi` workload passes job1.

    Re-measured 2026-09-19 (Task 9: the `multi` share of the mix rose from
    11% to 13%, spec section 6) -- 996 of 996 to 1209 of 1209 in train, 121
    of 121 to 145 of 145 in val. Still perfect."""
    def multi_job1(results):
        scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
        return sum(scores), len(scores)

    assert multi_job1(_train_results()) == (1209.0, 1209)
    assert multi_job1(_val_results()) == (145.0, 145)
```

`tests/test_shared_origin_training.py` -- `test_the_shared_answer_stays_the_minority_among_multi_workload_rows`'s
docstring, old ending:

```python
    counterweight and counts on the same side as `multi`. The proxy went red
    when the shared-origin share rose from 4 to 8 so that every scenario
    keeps at least 12 pairs in train (tests/test_shared_origin_floor.py);
    the claim it stood for did not. The claim is stated directly now: the
    shared answer is 0.368 of the multi-workload rows at 12/12 (0.384 at the
    build size), and the cap of 0.40 leaves no room for another raise: the
    next one must move `multi` up with it.

    Measured on the kept pile, not the generator's output: `drop_held_out`
    takes `multi` rows and no `shared_origin` rows, so a mix that looks safe
    as emitted is not necessarily safe by the time it reaches the optimizer.
    """
```

new:

```python
    counterweight and counts on the same side as `multi`. The proxy went red
    when the shared-origin share rose from 4 to 8 so that every scenario
    keeps at least 12 pairs in train (tests/test_shared_origin_floor.py);
    the claim it stood for did not. The claim was stated directly then: the
    shared answer was 0.368 of the multi-workload rows at 12/12 (0.384 at the
    build size).

    Re-measured 2026-09-19 (Task 9: the pool merge and the mix move to 15%
    on both shared-origin halves plus a 2-point `multi` raise, spec section
    6) -- 0.3822 at this module's size, 0.3839 at the build size (8000).
    This IS the raise spec section 7's decision check anticipated: moving
    `multi` up alongside the shared-origin halves is what keeps the share
    under the 0.40 cap here rather than moving it once more.
    """
```

`tests/test_shared_origin_training.py` -- `test_the_generator_emits_the_two_classes_near_evenly`'s
docstring, old:

```python
def test_the_generator_emits_the_two_classes_near_evenly(rows):
    """What the EMITTER controls, and it is no longer a coin flip: 0.568.

    Two sources feed the independent side now. The paired half is exact by
    construction -- every `shared_origin` row is emitted with a
    `shared_origin_decoy` twin from the same salt, so those two contribute
    96/96 at this module's SIZE and cannot drift. On top of that sit the surviving
    every-third-`multi` negatives, which have no positive counterpart, and
    they are the whole of the lean.
```

new:

```python
def test_the_generator_emits_the_two_classes_near_evenly(rows):
    """What the EMITTER controls, and it is no longer a coin flip: 0.568,
    re-measured 2026-09-19 (Task 9: pool merge + mix move, spec section 6)
    at 0.5636.

    Two sources feed the independent side now. The paired half is exact by
    construction -- every `shared_origin` row is emitted with a
    `shared_origin_decoy` twin from the same salt, so those two contribute
    120/120 at this module's SIZE (was 96/96 before Task 9's mix move to 15%
    on both shared-origin halves) and cannot drift. On top of that sit the
    surviving every-third-`multi` negatives, which have no positive
    counterpart, and they are the whole of the lean.
```

`tests/test_shared_origin_training.py` -- `test_the_trained_pile_is_not_one_sided_among_origin_read_rows`'s
docstring, append after the existing "0.55 to 0.52" paragraph, old ending:

```python
    The floor moved from 0.55 to 0.52 on 2026-09-08 when the halves went to
    12%: the kept pile then read 0.556 at this size and 0.546 at the build
    size, and 0.52 keeps three points of room below both.
    """
```

new:

```python
    The floor moved from 0.55 to 0.52 on 2026-09-08 when the halves went to
    12%: the kept pile then read 0.556 at this size and 0.546 at the build
    size, and 0.52 keeps three points of room below both.

    Re-measured 2026-09-19 (Task 9: pool merge + mix move to 15% on both
    shared-origin halves, spec section 6) -- 0.5455 at this size, 0.5430 at
    the build size. Both readings moved down slightly toward the floor
    because the shared-origin pair grew faster than the surviving `multi`
    negatives; 0.52 still keeps room below both.
    """
```

`tests/test_shared_origin_training.py` -- the "one cause per workload"
check, old:

```python
def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    """Label-aware (spec section 3, ruling C): a `shared`-labeled row is
    decided end to end, one cause per victim, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback) can decide several
    victims to several PVC causes and still be one `shared` group. No
    trainable scenario decides today (the trainable pool's own oracle tests
    hold job 3 at 1.0 without ever reaching a decided victim), so this is
    future-proofing rather than a live path today.
    """
    for e in _by_case(rows, "shared_origin"):
        if e.meta["label"] != "shared":
            continue
        causes = set(e.meta["expected"].values())
        assert all(w["decided"] for w in e.meta["workloads"].values())
        if e.meta["origin"] != "storage-provisioner-down":
            assert len(causes) == 1, e.meta["origin"]
```

new:

```python
_PVC_SCOPED_ORIGINS = frozenset({
    "storage-provisioner-down",       # eval-only (propagation.py:425)
    "pvc-provisioner-not-responding", # ruled, trainable (propagation.py:6932)
    "pvc-storageclass-missing",       # ruled, trainable (propagation.py:7060)
})


def test_every_shared_origin_row_names_one_cause_for_every_workload(rows):
    """Label-aware (spec section 3, ruling C): a `shared`-labeled row is
    decided end to end, one cause per victim, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback) can decide several
    victims to several PVC causes and still be one `shared` group.

    Re-measured 2026-09-19 (Task 9, spec section 6): before Task 9 no
    trainable scenario decided, so this exemption covered only the
    eval-only `storage-provisioner-down` origin and was future-proofing
    rather than a live path. Task 9 merged the two ruled PVC stories,
    `pvc-provisioner-not-responding` and `pvc-storageclass-missing`, into
    `trainable_scenarios()`; both are PVC-scoped by the same storage-class
    group-key fallback and both now decide multiple victims to multiple PVC
    causes under one `shared` group, confirmed by direct measurement
    (distinct-cause counts of 1, 2 and 3 across their `shared`-labeled
    rows). The exemption set below is closed and named, not inferred from
    `rules.py` at test time, so widening it is a deliberate edit here.
    """
    for e in _by_case(rows, "shared_origin"):
        if e.meta["label"] != "shared":
            continue
        causes = set(e.meta["expected"].values())
        assert all(w["decided"] for w in e.meta["workloads"].values())
        if e.meta["origin"] not in _PVC_SCOPED_ORIGINS:
            assert len(causes) == 1, e.meta["origin"]
```

`tests/test_shared_origin_training.py` -- `DRAWS`/`BIG` and the row-count
check, old:

```python
DRAWS = 33  # shared_origin rows per scenario at BIG; see the note below.
BIG = 275 * len(propagation.trainable_scenarios())
# Each shared_origin half is BIG * 12 // 100 rows, and the generator deals
# them round-robin over the pool, so every scenario gets exactly DRAWS rows
# per half (275 * 12 // 100 == 33). The pool grows in this slice, and the
# constant grows with it: 6600 rows at twenty-four scenarios, 13200 at
# forty-eight. Why 33 and not 11: the variant-rendering check below is a
# sampling check. With 4 variants drawn uniformly, P(fewer than 3 distinct
# in n draws) = (6 * 2**n - 8) / 4**n, and a fifth variant only lowers
# it. At n=11 that is 0.3% per scenario and 7% across twenty-four -- a
# deterministic failure with correct data. At n=33 it is 7.0e-10 per
# scenario, 3.4e-8 across forty-eight.


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS shared_origin rows per scenario. Check it."""
    pool = len(propagation.trainable_scenarios())
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * pool
```

new:

```python
DRAWS = 33  # plain-story shared_origin rows per scenario at BIG; see below.
RULED_DRAWS = 66  # ruled-story shared_origin rows per scenario at BIG.
# Re-measured 2026-09-19 (Task 9, spec section 7 ruling A): `BIG` is now a
# FIXED literal, not `275 * len(propagation.trainable_scenarios())`. Scaling
# by pool size stopped being safe once the pool split into two differently
# weighted sub-pools (spec section 6's selection loop gives ruled stories
# roughly twice the plain per-story share, by design -- a fifth of pairs
# spread over six ruled stories versus four fifths over forty-eight plain
# ones): a pool-scaled BIG would silently drift the exact 33/66 draw counts
# the sampling argument below depends on, on every future pool change. BIG =
# 13200 deals shared_origin 1980 rows total: 1584 over the 48 plain stories
# (33 each) and 396 over the 6 ruled stories (66 each) -- confirmed by
# direct measurement against this build. Why 33 (and 66) and not 11: the
# variant-rendering check below is a sampling check. With 4 variants drawn
# uniformly, P(fewer than 3 distinct in n draws) = (6 * 2**n - 8) / 4**n,
# and a fifth variant only lowers it. At n=11 that is 0.3% per scenario and
# 7% across twenty-four -- a deterministic failure with correct data. At
# n=33 it is 7.0e-10 per scenario, 3.4e-8 across forty-eight; n=66 is
# smaller still.
BIG = 13200


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS plain-story rows and RULED_DRAWS ruled-story
    rows per scenario, not one uniform rate over the whole pool (spec
    section 7 ruling A: "within each pool every story gets an equal share",
    checked per pool, not across them). Re-measured 2026-09-19, Task 9."""
    pool = propagation.trainable_scenarios()
    plain = sum(1 for p in pool if p.origin_object is None)
    ruled = sum(1 for p in pool if p.origin_object is not None)
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * plain + RULED_DRAWS * ruled
```

`tests/test_shared_origin_training.py` -- `EXPECTED_POOL`, old:

```python
# The pool grows by group across Tasks 5–9. Twenty-four is what it held when
# the 0907 run failed deciders 1 and 5; forty-eight is the planned end.
EXPECTED_POOL = 48
```

new:

```python
# The pool grew by group across Tasks 5–9 of the 2026-09-08 coverage plan.
# Twenty-four is what it held when the 0907 run failed deciders 1 and 5;
# forty-eight was that plan's end. On 2026-09-19 the training-targets fix
# merged six ruled stories on top (section 6 of its design): 48 to 54.
EXPECTED_POOL = 54
```

`tests/test_shared_origin_training.py` -- the `EXAM_LAYOUT_FLOORS` comment,
old:

```python
# One marker per exam read layout, and the fewest trainable scenarios that
# must teach it. A scenario counts once per layout when its read label
# starts the way the exam's does and any half of any of its origin
# variants carries the marker text. The floors are the spec's; the
# measured counts after the coverage branch are node 13, deployment 7,
# events 4, storageclass 6, networkpolicy 6.
```

new:

```python
# One marker per exam read layout, and the fewest trainable scenarios that
# must teach it. A scenario counts once per layout when its read label
# starts the way the exam's does and any half of any of its origin
# variants carries the marker text. The floors are the spec's, and are
# minimums the measured count only needs to clear, not match; the measured
# counts after the coverage branch were node 13, deployment 7, events 4,
# storageclass 6, networkpolicy 6.
#
# Re-measured 2026-09-19 (Task 9, spec section 6): node 15, deployment 7,
# events 4, storageclass 6, networkpolicy 6. Ruled stories add node,
# storage-class and events layouts per spec section 7 rulings E/F; only
# "node" moved here because the two ruled node stories
# (`node-kubelet-halted`, `node-kubelet-unresponsive`) both teach that
# layout, while the ruled PVC and registry stories' layouts (storageclass,
# events) were already above their floor from the plain pool. All five
# floors below are unchanged and all five measured counts still clear them.
```

(`EXAM_LAYOUT_FLOORS`'s dict literal itself -- `{"node": 13, "deployment": 4,
"events": 4, "storageclass": 6, "networkpolicy": 6}` -- does not change; the
dict holds minimum floors, not the measured counts the comment states.)

`tests/test_shared_origin_training.py` -- `test_every_trainable_scenario_is_taught_equally`,
old:

```python
def test_every_trainable_scenario_is_taught_equally(big_rows):
    """Equal shares are what make a constant answer chance-level: a scenario
    the curriculum shows twice as often is one the model can afford to answer
    by name.
    """
    keys = {p.key for p in propagation.trainable_scenarios()}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == keys, f"{case}: {sorted(keys ^ set(counts))}"
        assert len(set(counts.values())) == 1, f"{case}: uneven shares {dict(counts)}"
```

new:

```python
def test_every_trainable_scenario_is_taught_equally(big_rows):
    """Equal shares are what make a constant answer chance-level: a scenario
    the curriculum shows twice as often is one the model can afford to answer
    by name.

    Re-measured 2026-09-19 (Task 9, spec section 6): checked WITHIN each
    pool separately now, not across the whole 54-scenario pool at once. The
    selection loop gives ruled stories roughly twice the plain per-story
    rate by design -- a fifth of pairs spread over six ruled stories versus
    four fifths over forty-eight plain ones (DRAWS=33 plain, RULED_DRAWS=66
    ruled at `BIG`, above) -- so a single across-pool equality check would
    fail on the intended shape, not a bug. Equal shares still hold inside
    each pool: every plain story gets the same count and every ruled story
    gets the same count.
    """
    pool = propagation.trainable_scenarios()
    plain_keys = {p.key for p in pool if p.origin_object is None}
    ruled_keys = {p.key for p in pool if p.origin_object is not None}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == plain_keys | ruled_keys, (
            f"{case}: {sorted((plain_keys | ruled_keys) ^ set(counts))}")
        plain_shares = {v for k, v in counts.items() if k in plain_keys}
        ruled_shares = {v for k, v in counts.items() if k in ruled_keys}
        assert len(plain_shares) == 1, f"{case}: uneven plain shares {dict(counts)}"
        assert len(ruled_shares) == 1, f"{case}: uneven ruled shares {dict(counts)}"
```

`tests/test_shared_origin_training.py` -- `test_no_shared_origin_cause_dominates_the_curriculum`'s
docstring, append after the existing "Top one is stable at 0.263" line, old
ending:

```python
    The size is named because top three moves with it: 0.633 at 5500, 0.618 at
    8000, 0.609 at 11000, 0.602 at 20000, as the tail keeps gaining distinct
    causes. Top one is stable at 0.263 across all four.
    """
```

new:

```python
    The size is named because top three moves with it: 0.633 at 5500, 0.618 at
    8000, 0.609 at 11000, 0.602 at 20000, as the tail keeps gaining distinct
    causes. Top one is stable at 0.263 across all four.

    Re-measured 2026-09-19 (Task 9: pool merge to 54 scenarios and `BIG`
    fixed at 13200, spec section 6/7 ruling A) -- 185 distinct causes, top
    one 0.0249, top three 0.0698. Both PVC-scoped ruled stories widen the
    tail further: their per-victim causes name the victim's own PVC
    (`f"PVC {pvc} (...)"`), so each ruled PVC draw can add several new
    distinct causes at once. The bar stays 0.12 and 0.30; the new pool
    clears both with more room than the old one did.
    """
```

`tests/test_shared_origin_training_pair.py` -- `test_the_answer_flips_with_the_read`,
old:

```python
def test_the_answer_flips_with_the_read(rows):
    for shared, decoy in _pairs(rows):
        one = json.loads(shared.assistant)
        sep = json.loads(decoy.assistant)
        assert propagation.SEPARATE_REASONS not in one["summary"]
        assert propagation.SEPARATE_REASONS in sep["summary"]
        # One cause for every workload on the shared half; each workload's own
        # local cause on the decoy half. Same workloads, different answers.
        causes = {v["cause"] for v in one["verdicts"]}
        assert len(causes) == 1
        assert shared.meta["expected"] != decoy.meta["expected"]
```

new:

```python
# A PVC-scoped origin groups by storage class (`rules.py`'s group-key
# fallback), so several distinct PVC objects on the same class can decide to
# several distinct per-PVC causes under one `shared` verdict -- see the same
# exemption in tests/test_shared_origin_training.py. Re-measured 2026-09-19
# (Task 9, spec section 6): the two ruled PVC stories now exercise this for
# real, e.g. `{'PVC cache-0 (ProvisionerNotResponding)',
# 'PVC media-assets (ProvisionerNotResponding)'}` on
# `pvc-provisioner-not-responding`.
_PVC_SCOPED_ORIGINS = frozenset({
    "storage-provisioner-down",
    "pvc-provisioner-not-responding",
    "pvc-storageclass-missing",
})


def test_the_answer_flips_with_the_read(rows):
    for shared, decoy in _pairs(rows):
        one = json.loads(shared.assistant)
        sep = json.loads(decoy.assistant)
        assert propagation.SEPARATE_REASONS not in one["summary"]
        assert propagation.SEPARATE_REASONS in sep["summary"]
        # One cause for every workload on the shared half, except a
        # PVC-scoped origin, which may decide several workloads to several
        # per-PVC causes; each workload's own local cause on the decoy half.
        # Same workloads, different answers.
        causes = {v["cause"] for v in one["verdicts"]}
        if shared.meta["origin"] not in _PVC_SCOPED_ORIGINS:
            assert len(causes) == 1
        assert shared.meta["expected"] != decoy.meta["expected"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_shared_origin_training.py::test_the_trainable_pool_holds_the_planned_count tests/test_generate.py::test_counts_for_follows_the_mix -q`

Expected: FAIL --

```
_______________ test_the_trainable_pool_holds_the_planned_count ________________
    pool = propagation.trainable_scenarios()
>   assert len(pool) == EXPECTED_POOL
E   assert 48 == 54
tests/test_shared_origin_training.py:938: AssertionError
_______________________ test_counts_for_follows_the_mix ________________________
>   assert counts == {"attributed": 60, "none_of_these": 110, "own_cause": 100,
                      "multi": 130, "shared_origin": 150, ...}
E   AssertionError: assert {'attributed'...ti': 110, ...} == {'attributed'...ti': 130, ...}
E   Differing items:
E   {'multi': 110} != {'multi': 130}
E   {'none_of_these': 150} != {'none_of_these': 110}
E   {'shared_origin_decoy': 120} != {'shared_origin_decoy': 150}
E   {'shared_origin': 120} != {'shared_origin': 150}
E   {'attributed': 100} != {'attributed': 60}
2 failed in 0.21s
```

Then the full suite, with every test edit above applied but neither
production file touched yet: `find . -name __pycache__ -prune -exec rm -rf
{} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q` -- Expected:
`16 failed, 776 passed` (measured in the clone; the other fourteen failures
are the remaining re-pinned tests above, each failing on its own old-vs-new
number the same way).

- [ ] **Step 3: Implement**

`src/kubeagent_verdict/dataset/propagation.py`, `trainable_scenarios` -- old:

```python
def trainable_scenarios() -> tuple[Propagation, ...]:
    """The origins training may see. Disjoint from `all_scenarios()` by test."""
    return _TRAINING_SCENARIOS
```

new:

```python
def trainable_scenarios() -> tuple[Propagation, ...]:
    """The origins training may see: the 48 plain stories plus the six ruled
    stories (spec section 4), whose origin object lets the rules pass itself
    confirm the shared cause. Disjoint from `all_scenarios()` by test."""
    return _TRAINING_SCENARIOS + _RULED_SCENARIOS
```

`src/kubeagent_verdict/dataset/generate.py`, `CASE_MIX` -- old:

```python
CASE_MIX = (("attributed", 10), ("none_of_these", 15), ("own_cause", 10),
            ("multi", 11), ("shared_origin", 12), ("shared_origin_decoy", 12),
            ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 10))
```

new:

```python
# 2026-09-19 (spec section 6): both halves move again, 12% -> 15%, so a
# shared_origin/shared_origin_decoy pair can be spent on the six ruled
# stories one pair in five (the rest still walk the 48 plain stories,
# spec section 6's loop). `attributed` and `none_of_these` each give up
# four points; two of the eight go to `multi` (11% -> 13%) rather than to
# the shared-origin halves alone, because raising only the shared side
# would put the shared answer's share of multi-workload rows exactly on
# the 0.40 cap (test_the_shared_answer_stays_the_minority_among_multi_workload_rows)
# -- Task 9 of the 2026-09-19 training-targets plan measures the mixes
# this was chosen over.
CASE_MIX = (("attributed", 6), ("none_of_these", 11), ("own_cause", 10),
            ("multi", 13), ("shared_origin", 15), ("shared_origin_decoy", 15),
            ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 10))
```

`src/kubeagent_verdict/dataset/generate.py`, the comment above the `multi`
loop -- old:

```python
        # They also have no positive twin, so they are the whole of the
        # residual lean: the paired core is exactly even (960/960 at the
        # build size) and the kept pile reads ~0.55 toward the INDEPENDENT
        # answer. That is the opposite
```

new:

```python
        # They also have no positive twin, so they are the whole of the
        # residual lean: the paired core is exactly even (1200/1200 at the
        # build size, re-measured 2026-09-19 after Task 9's mix move to 15%
        # on both shared-origin halves -- was 960/960) and the kept pile
        # reads ~0.543 toward the INDEPENDENT answer (was ~0.55; still
        # tests/test_shared_origin_training.py's own re-measurement, not
        # re-derived here). That is the opposite
```

`src/kubeagent_verdict/dataset/generate.py`, the `shared_origin`/
`shared_origin_decoy` loop in `generate` -- old:

```python
    for i in range(counts["shared_origin"]):
        p = train_scen[i % len(train_scen)]
        # Vary the width the way `probe_sets` does: a row that always renders
        # every victim teaches the count, not the reasoning.
        victims = 2 + (i // len(train_scen)) % (len(p.victims) - 1)
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins draw
        # the same names and render the same inventory, the same candidate
```

new:

```python
    # 2026-09-19 (spec section 6): one pair in five now comes from the six
    # ruled stories instead of the 48 plain ones, so the rules pass gets a
    # shared origin it can confirm itself and training finally carries
    # `shared`-labelled rows. The two pools are walked with their own
    # indices (`k` skips the one ruled slot out of every five `i`s, `j`/`t`
    # count ruled draws and full trips around the ruled pool) so each pool
    # still cycles through its own stories and widths evenly on its own
    # schedule, the same way the single `i % len(train_scen)` walk did
    # before the ruled stories existed. One node ruled pair in three (every
    # third trip around the six-story ruled pool) renders the unverified
    # twin instead of the confirmed one (spec section 5); the label comes
    # out "none" either way, which is what lets a plain `shared_origin` row
    # and an unverified one share one case name and one budget.
    plain = tuple(p for p in train_scen if p.origin_object is None)
    ruled = tuple(p for p in train_scen if p.origin_object is not None)
    for i in range(counts["shared_origin"]):
        if i % 5 == 4:
            j = i // 5
            p = ruled[j % len(ruled)]
            t = j // len(ruled)
            # Vary the width the way `probe_sets` does: a row that always
            # renders every victim teaches the count, not the reasoning.
            victims = 2 + (t // 3) % (len(p.victims) - 1)
            unverified = p.origin_object.kind == "node" and t % 3 == 2
        else:
            k = i - (i + 1) // 5
            p = plain[k % len(plain)]
            victims = 2 + (k // len(plain)) % (len(p.victims) - 1)
            unverified = False
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins draw
        # the same names and render the same inventory, the same candidate
```

and, further down in the same loop, its `unverified` note plus the
`shared_origin` call -- old:

```python
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims))
        out.append(cases.shared_origin_decoy(
            p, random.Random(salt), victims=victims))
```

new:

```python
        # `unverified` never applies to the decoy twin: the healthy read it
        # draws already refutes every victim outright, so there is no second,
        # "could not check" world for it to render (Task 8's docstring).
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims,
                                       unverified=unverified))
        out.append(cases.shared_origin_decoy(
            p, random.Random(salt), victims=victims))
```

- [ ] **Step 4: Run it green, then the full suite and ruff, then check both
      of spec §6's decision checks by hand**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`

Expected: `792 passed` (measured baseline of `792` after Task 8 -- this
task's edits add no new test function, so the count does not move, only the
values inside existing ones do); ruff `All checks passed!`.

Both of spec §6's decision checks, measured against this exact build (seed
17, size 8000, both re-measured in the clone as part of getting Step 4
green):
- **Floor check.** The lowest plain-story pair count kept in train is 15
  (`sidecar-injector-broken`), against a floor of 12 -- well clear, so the
  primary mix ships and the fallback mix (`attributed` 5, `none_of_these`
  10, `multi` 13, both shared-origin halves at 16%) is not needed.
- **Ratio check.** The shared answer is 0.3822 of multi-workload rows at
  `tests/test_shared_origin_training.py`'s module size and 0.3839 at the
  build size (8000). Two different numbers matter here, and they are not
  the same check: `assert share <= 0.40` in that test is the code's real
  cap (`tests/test_shared_origin_training.py:506`), the one a build must
  pass; the spec's 0.395 (section 6) is a stricter, design-time trigger --
  simulated ahead of the real build, to decide whether one more point
  should move from `none_of_these` to `multi` before shipping, with no
  test asserting it. Both measured numbers, 0.3822 and 0.3839, sit under
  both figures, so no further point moves. The mix as implemented in
  Step 3 (with the 2-point `multi` raise, 11% to 13%, already included) is
  final; it was chosen specifically because raising only the two
  shared-origin halves, with no `multi` raise, would have put the ratio at
  0.4000 at the build size -- right on the code's 0.40 cap, with no room
  to spare (see the `CASE_MIX` comment in Step 3).

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add src/kubeagent_verdict/dataset/generate.py src/kubeagent_verdict/dataset/propagation.py \
    tests/test_evidence_overlap.py tests/test_generate.py tests/test_multi_collision.py \
    tests/test_oracle.py tests/test_probe_cousins.py tests/test_ruled_scenarios.py \
    tests/test_shared_origin_floor.py tests/test_shared_origin_training.py \
    tests/test_shared_origin_training_pair.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "$(cat <<'EOF'
feat(dataset): merge the six ruled stories into the trainable pool

trainable_scenarios() now returns the 48 plain stories plus the six ruled
ones (spec section 6), so a training row can carry a shared origin the
rules pass itself confirms. CASE_MIX moves both shared-origin halves from
12% to 15% (one pair in five now walks the six-story ruled pool) and multi
from 11% to 13%, funded by attributed and none_of_these giving up four
points each; the generator's selection loop walks the two sub-pools on
their own indices so each still cycles its own stories and widths evenly.

Both of spec section 7's decision checks pass on the shipped mix, measured
against this exact build (seed 17, size 8000): every plain story keeps at
least 15 pairs in train (floor 12, so no fallback mix), and the shared
answer is 0.3822 of multi-workload rows at this module's size and 0.3839
at the build size (cap 0.40, so no further point move off none_of_these).

Re-pinned every test whose count moved with the pool/mix, by hand, against
this build:
  - oracle: job1 2570->3056 train, 289->355 val; job2 gate 3121->2975
    train, 352->304 val; job2 keyword-only 2175->2286; job3 train
    n=2790 (shared 192, none 2597), val n=336 (shared 22, none 314); multi
    job1 996/996->1209/1209 train, 121/121->145/145 val.
  - probe_cousins: pool 48->54, rows 96->108.
  - evidence_overlap: shared_origin_probe (0,34)->(3,34), decoy (0,34)->
    (2,34) -- generic PVC-provisioning event text the two ruled PVC
    stories now share with the eval-only storage-provisioner-down
    scenario, plus one coincidental "Started container" collision.
  - shared_origin_training: BIG fixed at 13200 (was pool-scaled, which
    would silently drift once the pool split into unevenly weighted
    sub-pools) with DRAWS=33 plain / RULED_DRAWS=66 ruled; EXPECTED_POOL
    48->54; the "taught equally" check now compares within each sub-pool
    rather than across the whole pool, since ruled stories get roughly
    double the plain per-story rate by design; EXAM_LAYOUT_FLOORS'
    measured node count 13->15 (the two ruled node stories); dominance
    check 15->185 distinct causes, top one 0.263->0.0249, top three
    0.609->0.0698; independent-share bands re-measured (0.568->0.5636
    emitted, 0.556/0.546->0.5455/0.5430 kept); the "one cause per
    workload" check's PVC exemption widens from one eval-only origin to
    three (the eval one plus the two ruled PVC stories), since a
    storage-class-scoped group can now decide several victims to several
    PVC causes for real.
  - shared_origin_training_pair: the same PVC exemption, for
    test_the_answer_flips_with_the_read.

No test used -update; every number above was measured against the actual
built dataset, not carried over from the spec's own simulation.
EOF
)"
```

Measured (this commit's own diff): `11 files changed, 357 insertions(+),
137 deletions(-)`. Full suite: `792 passed, 6 warnings`; ruff `All checks
passed!`.

- [ ] **Step 6: Write the second commit's failing test**

Spec section 7 names one more check: "A shared label only comes from an
origin object." `tests/test_shared_origin_decided.py` already had
this check, but only against the six eval scenarios (`prop.all_scenarios()`)
-- before this task no trainable story ever decided, so there was no
trainable pool to check it against. Now that Step 5 merged the six ruled
stories in, extend it to `trainable_scenarios()` too, with the TRAINING
row-builder (`cases.shared_origin`, not the eval-only
`shared_origin_probe`).

`tests/test_shared_origin_decided.py` -- old:

```python
def test_a_shared_label_only_comes_from_an_origin_object():
    """Every `shared` row is a ruled story's broken twin or one of the exam's
    three origin-object stories -- never a plain story, which has no
    candidate the rules could confirm twice under one group key.
    """
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key
```

new:

```python
def test_a_shared_label_only_comes_from_an_origin_object():
    """Every `shared` row is a ruled story's broken twin or one of the exam's
    three origin-object stories -- never a plain story, which has no
    candidate the rules could confirm twice under one group key.

    Extended 2026-09-19 (Task 9, spec section 6): before Task 9 no trainable
    story decided, so only the eval half of this claim had a pool to check
    against. Task 9 merged the six ruled stories into `trainable_scenarios()`;
    the second loop below walks that fifty-four-story pool with the TRAINING
    builder (`cases.shared_origin`, not the eval-only `shared_origin_probe`)
    and confirms the same rule holds there too -- exactly the six ruled
    stories decide, and every one of the forty-eight plain stories does not.
    """
    for p in prop.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key
    for p in prop.trainable_scenarios():
        ex = cases.shared_origin(p, generate._entry_rng("t", p.key), victims=2)
        if ex.meta["label"] == "shared":
            assert p.origin_object is not None, p.key
        else:
            assert p.origin_object is None, p.key
```

- [ ] **Step 7: Run it and watch it fail**

This edit is additive (a second loop appended to an already-passing test),
so it is not RED in the usual sense -- there is no bug for it to catch,
because the invariant holds by construction (`shared_origin`'s render path
can only decide a victim when `p.origin_object is not None`, since the
rules pass has nothing to confirm against otherwise). Confirm that
directly rather than assuming it:

Run: `cd /home/ubuntu/git/kubeagent-verdict && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "
import random
from kubeagent_verdict.dataset import cases, propagation as prop
bad = []
for p in prop.trainable_scenarios():
    e = cases.shared_origin(p, random.Random(1), victims=2)
    if e.meta['label'] == 'shared' and p.origin_object is None:
        bad.append(p.key)
    if e.meta['label'] != 'shared' and p.origin_object is not None:
        bad.append(('unexpected-none', p.key))
print('bad:', bad)
print('shared count:', sum(1 for p in prop.trainable_scenarios()
      if cases.shared_origin(p, random.Random(1), victims=2).meta['label'] == 'shared'))
"`

Expected: `bad: []` and `shared count: 6` -- the check is true before Step 8
touches anything, because Step 8 is a test-only addition. This step's job is
producing that evidence, not producing a failure.

- [ ] **Step 8: Implement**

No production code changes. `test_a_shared_label_only_comes_from_an_origin_object`
above is the whole of this step.

- [ ] **Step 9: Run it green, then the full suite and ruff**

Run: `cd /home/ubuntu/git/kubeagent-verdict && find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q && .venv/bin/ruff check .`

Expected: `792 passed` (the edit extends an existing test function rather
than adding a new one, so the count does not move); ruff `All checks
passed!`.

- [ ] **Step 10: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && \
  git add tests/test_shared_origin_decided.py && \
  git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "$(cat <<'EOF'
test(dataset): confirm a shared label never comes from a plain trainable story

test_a_shared_label_only_comes_from_an_origin_object covered only the six
eval scenarios, since no trainable story decided until the ruled stories
entered the pool. Now that trainable_scenarios() carries the six ruled
stories alongside the 48 plain ones, extend the same check to that pool
with the training row-builder:
exactly the six ruled stories label shared and every plain one labels none,
confirmed by direct measurement, matching the docstring's own claim that a
shared row is always a ruled story's broken twin or an eval origin-object
story.
EOF
)"
```

Measured (this commit's own diff): `1 file changed, 14 insertions(+)`. Full
suite with both of this task's commits applied on top of Task 8: `792
passed, 6 warnings`; ruff `All checks passed!`.

This is the plan's last code task. `trainable_scenarios()` now stands at its
planned end (54: 48 plain + 6 ruled), `CASE_MIX` and the selection loop are
final, and every dependent test is re-pinned by hand against the real
build -- no `-update` anywhere in Tasks 6-9.

### Task 10: correct every doc line and comment the earlier tasks made false

**Spec:** §8 "Doc moves" (every bullet) and §12 "Disclosed limits". The
promise rule covers the rest: any doc line or comment that Tasks 1-9 made
false.

**Files:**
- Modify: `README.md`
- Modify: `docs/design.md` (in both commits)
- Modify: `docs/how-training-works.md`
- Modify: `docs/model-card.md` (in both commits)
- Modify: `docs/runbooks/train.md`
- Modify: `src/kubeagent_verdict/dataset/cases.py` (one comment in
  `_render_shared_origin`)
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (the module
  docstring, and the comments on `Victim.on_origin`, `Victim.decoys` and
  `Propagation.origin_object`)

**Interfaces:**
- Consumes: the tree after Task 9. The case mix, the 54-story pool, the
  14 changed exam rows and every test value are already in place.
- Produces: no code, no test and no value. Two commits of words. Task 11
  checks that the build these words describe is the one the tree makes.

This task changes words only. No function, test or value moves, so there
is no failing test to write first. The check is different: every number
in these words was measured on one exact build, and Task 11 proves the
tree still makes that build, byte for byte.

**How to apply the blocks.** Each block is an exact replace. Find the
"Replace" text in the file, and put the "with" text in its place. The
text sits between a `~~~~text` line and a `~~~~` line. Copy it exactly,
blank lines included. Apply a file's blocks in the order given. Before
each one, check that its Replace text appears exactly once in the file.
If it appears zero times or twice, stop and report. That means an earlier
task left the file different from what this plan expects, and a guessed
edit would hide it.

**Where the numbers come from.** Every number in the blocks is measured,
except the run time.

- The mix (`shared_origin` and `shared_origin_decoy` 15% each, `multi`
  13%, `attributed` 6%, `none_of_these` 11%) and the 54-story pool:
  `CASE_MIX` in `dataset/generate.py` and the pool in
  `dataset/propagation.py`, after Task 9.
- 6377 train rows, 718 val and 263 exam, and the case counts: the
  manifest of `kv-dataset --seed 17 --size 8000`.
- 796 optimizer steps: the trainer counts one step per 16 rows inside an
  epoch. The 9 rows left at the end of each epoch add no counted step. So
  it is 398 steps per epoch (6377 ÷ 16, rounded down), times 2 epochs.
- 6,579,981 train tokens per epoch: gate 3 in Task 11, with the real
  tokenizer.
- 192 ruled broken twins in train and 22 in val, 25 and 1 unverified
  node twins, and limit 8's counts: counted on that build's rows.
- 0908's exam hash, `c2d22b6e…`: `run.dataset.test_sha256` in
  `out/eval/0908/scoreboard.json`. Step 1 checks it.
- **The one estimate is the run time, 33h16m.** It scales the one timed
  run (17h42m) by the new build's token count. The runbook says so, and
  says the measured time replaces it after the run.

**Where the text differs from the spec, on purpose.** Spec §8 and §12
were written before this build existed. The words use what the build
measured. A reviewer should not flag these as drift:

1. **Limit 2.** The spec says "one node under two scan reasons". The
   card names them: worker-3, under "NotReady" and "no kubelet lease".
2. **Limit 3.** The spec says healthy victim reads say `Pending` while
   the fresh read says `Bound`. Measured: the prompt always says
   `Pending`. `Bound` sits on a table field the prompt never prints.
3. **Limit 6.** The spec says "about 186 to 190" ruled broken twins in
   train. The build has 192 in train and 22 in val. The card also names a
   third pattern: 25 train and 1 val unverified node twins, label `none`.
4. **Limit 7.** The spec cites `dataset/cases.py:877-878`. The card names
   the function, `_render_shared_origin`, because line numbers drift.
5. **Limit 8.** The spec says the exam's node story shows both formats.
   Measured: the exam's node rows print only the story form. In train, 62
   `multi` rows print both (42 of them with the same node both times). In
   val, 9 do.
6. **The design doc's paired-core paragraph** says "440 against 440" and
   "~0.57". It predates this branch. At this build the tests pin 1200
   against 1200 and ~0.543, so commit 2 writes those.
7. **The runbook's run time.** Spec §8 says the runbook gets "this run's
   measured numbers". The run has not happened yet. The row counts and
   step count are measured on the build. The time is the one estimate,
   33h16m, marked as one, and "After this plan" replaces it with the
   measured time.

- [ ] **Step 1: Check the starting point**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git status --short && git log --oneline -1 && \
  find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -1 && \
  .venv/bin/python -c "import json; print(json.load(open('/home/ubuntu/git/kubeagent-verdict/out/eval/0908/scoreboard.json'))['run']['dataset']['test_sha256'])"
```

Expected:
- `git status --short` prints nothing.
- The last commit is Task 9's second one:
  `test(dataset): confirm a shared label never comes from a plain trainable story`.
- `792 passed, 6 warnings in …`.
- `c2d22b6e2d3b3ceeda82c7cadd150d67945e69afe85ac43b7f2eec3e9d9b45e2`.

The model-card block in Step 5 writes that hash. If the file prints a
different one, stop and report. The scoreboard file is read, never
written.

- [ ] **Step 2: `README.md`**

**`README.md`**

Replace:

~~~~text
The slice puts 2–4 flagged workloads in one prompt, all downstream of a
single broken component, so the correct answer names the same shared cause
on every row. When it was added, nothing like it was in the training data —
every multi-workload example there drew its constituents from distinct
catalog entries and summarised them as "N workloads are failing for separate
reasons," 825 rows of it with no counterexample anywhere. It added no
training rows and removed none: its group keys are namespaced, so
`drop_held_out` cut exactly the same 913 rows with and without it.

~~~~

with:

~~~~text
The slice puts 2–4 flagged workloads in one prompt, all downstream of a
single broken component. When it was added, the correct answer named the
same shared cause on every row, and nothing like it was in the training
data — every multi-workload example there drew its constituents from
distinct catalog entries and summarised them as "N workloads are failing
for separate reasons," 825 rows of it with no counterexample anywhere. It added no
training rows and removed none: its group keys are namespaced, so
`drop_held_out` cut exactly the same 913 rows with and without it. Since
2026-09-19 the answer follows kubeagent's rules: a row the rules decide
takes the rules' own cause instead, and the answer calls the cause shared
only when the rules confirm it.

~~~~

Replace:

~~~~text
trained scenarios went from 24 to 48, and the build size went from 5500 to
8000, all for the final retrain. Every number on this page still comes from
a model that never saw the shape.

~~~~

with:

~~~~text
trained scenarios went from 24 to 48, and the build size went from 5500 to
8000, all for the final retrain. On 2026-09-19 the share went to 15% each,
the pool went from 48 to 54 (six new stories the rules pass can confirm),
and `multi` moved up too, to 13%, so the shared answer still stays the
minority answer to a multi-workload question. Every number on this page
still comes from a model that never saw the shape.

~~~~

- [ ] **Step 3: `docs/design.md`**

**`docs/design.md`**

Replace:

~~~~text
|---|---|---|
| Candidate attributed, evidence supports it | ~10% | Pick the candidate **verbatim**; calibrate confidence |
| `none_of_these` — evidence rules all candidates out | ~15% | Refusing the offered menu |
| Own evidence-grounded cause (unlisted) | ~10% | Naming what the deterministic pass missed |
| Multi-workload prompts (2–4 flagged, mixed causes) | ~11% | One verdict row per listed workload, no extras |
| `shared_origin` — 2–4 flagged, all downstream of one broken component | ~12% | Naming the SAME cause on every row when the evidence says one thing broke |
| `shared_origin_decoy` — the same scenario, origin read HEALTHY | ~12% | Taking each workload's own cause when the read refutes the shared story. Emitted as `shared_origin`'s twin from one salt, never independently; the two shares must stay equal |
| Truncated evidence (marker present) | ~5% | Judging honestly under cut evidence — lower confidence |
~~~~

with:

~~~~text
|---|---|---|
| Candidate attributed, evidence supports it | ~6% | Pick the candidate **verbatim**; calibrate confidence |
| `none_of_these` — evidence rules all candidates out | ~11% | Refusing the offered menu |
| Own evidence-grounded cause (unlisted) | ~10% | Naming what the deterministic pass missed |
| Multi-workload prompts (2–4 flagged, mixed causes) | ~13% | One verdict row per listed workload, no extras |
| `shared_origin` — 2–4 flagged, all downstream of one broken component | ~15% | Naming the story's cause on every row the rules do not decide and the rules' own cause on every row they do; calling it shared only when the rules confirm it |
| `shared_origin_decoy` — the same scenario, origin read HEALTHY | ~15% | Taking each workload's own cause when the read refutes the shared story. Emitted as `shared_origin`'s twin from one salt, never independently; the two shares must stay equal |
| Truncated evidence (marker present) | ~5% | Judging honestly under cut evidence — lower confidence |
~~~~

Replace:

~~~~text
pairs in train after the validation split; a test pins that floor at the
build recipe (seed 17, size 8000). The shared answer stays the minority
answer to a multi-workload question: in the pile the model reads it is
about 38 of every 100 of the `multi`, `shared_origin` and
`shared_origin_decoy` rows together, and a test fails above 40 of every
100.
~~~~

with:

~~~~text
pairs in train after the validation split; a test pins that floor at the
build recipe (seed 17, size 8000). On 2026-09-19 it rose again, to 15%,
paid out of `attributed` and `none_of_these` together this time, and
`multi` moved up too, to 13%, so raising the shared-origin halves alone
could not push the shared answer's share of multi-workload rows onto the
cap below. The shared answer stays the minority
answer to a multi-workload question: in the pile the model reads it is
about 38 of every 100 of the `multi`, `shared_origin` and
`shared_origin_decoy` rows together (re-measured at the 15% mix: still
about 38 of every 100), and a test fails above 40 of every
100.
~~~~

- [ ] **Step 4: `docs/how-training-works.md`**

**`docs/how-training-works.md`**

Replace:

~~~~text
|---|---|---|
| `attributed` | 10% | The obvious candidate is right — pick it, word for word |
| `none_of_these` | 15% | Sometimes *every* offered candidate is wrong. Say so. |
| `own_cause` | 10% | Sometimes the right answer is not on the menu at all. Name it. |
~~~~

with:

~~~~text
|---|---|---|
| `attributed` | 6% | The obvious candidate is right — pick it, word for word |
| `none_of_these` | 11% | Sometimes *every* offered candidate is wrong. Say so. |
| `own_cause` | 10% | Sometimes the right answer is not on the menu at all. Name it. |
~~~~

Replace:

~~~~text
| `injection` | 10% | The evidence may contain text saying "ignore your instructions." It is data. Ignore *it*. |
| `multi` | 11% | Several broken workloads in one question, each broken for its **own separate reason** |
| `truncated` | 5% | The evidence was cut short. Answer honestly and lower your confidence. |
| `empty_candidates` | 5% | Nothing is actually wrong. Do not invent a problem. |
| `shared_origin` | 12% | Several broken workloads, **all broken by one single thing** — name the same cause on every one |
| `shared_origin_decoy` | 12% | The *same* question with the one thing shown **healthy** — so the answer is separate reasons after all |

~~~~

with:

~~~~text
| `injection` | 10% | The evidence may contain text saying "ignore your instructions." It is data. Ignore *it*. |
| `multi` | 13% | Several broken workloads in one question, each broken for its **own separate reason** |
| `truncated` | 5% | The evidence was cut short. Answer honestly and lower your confidence. |
| `empty_candidates` | 5% | Nothing is actually wrong. Do not invent a problem. |
| `shared_origin` | 15% | Several broken workloads, all downstream of one thing — name that thing on every one (in the rules' own words where the rules checked it), and call it one shared cause only when the rules confirm it |
| `shared_origin_decoy` | 15% | The *same* question with the one thing shown **healthy** — so the answer is separate reasons after all |

~~~~

Replace:

~~~~text

`shared_origin` entered the curriculum at 4% (it is 12% now: Change 4 below
says how it reached 8%, and the last section of Part 3 says why it went on
to 12%): several workloads, one upstream cause, the same answer on every
row.

~~~~

with:

~~~~text

`shared_origin` entered the curriculum at 4% (it is 15% now: Change 4 below
says how it reached 8%, the last section of Part 3 says why it went on to
12%, and a 2026-09-19 change took it to 15% so a pair in five could come
from six new stories the rules pass can confirm on its own): several
workloads, one upstream cause, and an answer that calls it shared only when
the rules confirm it.

~~~~

Replace:

~~~~text

| | 4% build | 8% build | 12% build |
~~~~

with:

~~~~text

On 2026-09-19 both halves moved again, to 15%, and `multi` moved with them,
to 13%: the budget came out of `attributed` and `none_of_these` this time,
not out of `attributed` alone, because raising only the shared-origin
halves would have pushed the shared answer's share of multi-workload rows
onto the 0.40 cap a test pins. The pool also grew, from 48 stories to 54:
six new "ruled" stories give kubeagent's own rules pass an origin object it
can check, so a fifth of shared-origin pairs can now carry a `shared`
label the rules confirm. Before this, no training row carried one. Spec
section 6 of
`docs/superpowers/specs/2026-09-19-training-targets-fix-design.md` has the
detail.

| | 4% build | 8% build | 12% build |
~~~~

Replace:

~~~~text
- **A cousin probe.** `kv-dataset --probe-cousins` writes one fresh pair per
  trained scenario, 48 pairs and 96 rows, every decoy half at full width.
  It asks whether the model reads the origin on what it studied. It decides
~~~~

with:

~~~~text
- **A cousin probe.** `kv-dataset --probe-cousins` writes one fresh pair per
  trained scenario, 54 pairs and 108 rows since the 2026-09-19 pool grew
  from 48 to 54 stories, every decoy half at full width.
  It asks whether the model reads the origin on what it studied. It decides
~~~~

- [ ] **Step 5: `docs/model-card.md`**

**`docs/model-card.md`**

Replace:

~~~~text
held. That is the proof the revert touched nothing else (`contract/PIN.md`).

~~~~

with:

~~~~text
held. That is the proof the revert touched nothing else (`contract/PIN.md`).
This run's exam hash: `test_sha256` `c2d22b6e2d3b3ceeda82c7cadd150d67945e69afe85ac43b7f2eec3e9d9b45e2`
(`out/eval/0908/scoreboard.json`).

The exam has since been re-pinned a third time, on 2026-09-19, for
`_render_shared_origin`'s decided-row fix (section 3 of
`docs/superpowers/specs/2026-09-19-training-targets-fix-design.md`): 14 of
the 263 rows change their gold answer, byte for byte, and nothing else
does. All ten `shared_origin_probe` rows (244-253) change — a decided
victim's row cause and rationale now come from the rules
(`result.cause`, `_rule_rationale(result)`) instead of always the
formatted shared cause, and a `none`-labelled row's summary now says
kubeagent's rules did not confirm one cause instead of falsely claiming a
shared one. Four of the ten `shared_origin_decoy_probe` rows (254-263)
change too — the two `coredns-down` and two `node-disk-pressure` rows,
whose decided victim moves off the same per-victim decide; the other six
decoy rows (the three stories with an origin object, whose healthy world
decides nothing) do not move. The graded view — everything the three job
bars, contract validity, decoy rate and suggestion echo read off a row —
does not move; a pinned hash over that view proves it. The table below
still reads on the old exam bytes: 0908 was scored before this re-pin.
Replaying 0908's banked outputs against the new exam gives the same job
1, job 2 and job 3 numbers, and the same contract validity, decoy rate,
length gap and suggestion echo. Overconfidence, which no bar gates, moves from
0.1717 (167 rows) to 0.2093 (176 rows): it compares replies with the gold
cause, and 14 gold causes changed.

~~~~

- [ ] **Step 6: `docs/runbooks/train.md`**

**`docs/runbooks/train.md`**

Replace:

~~~~text

1. **Dataset** (seconds):
~~~~

with:

~~~~text

**2026-09-19 pre-run estimate for this retrain's build (not yet run).**
Budget about **33 hours**, not the 28 above. The 28 scales 0907's time
per example by rows. This estimate scales 0908's time by tokens, the
formula spec section 11 of
`docs/superpowers/specs/2026-09-19-training-targets-fix-design.md` uses.
0908, the most recent full run, took 31.8 hours for 12,577,240 training
tokens (both epochs). This build's train split is 6,579,981 tokens per
epoch with the real Qwen3-0.6B tokenizer, 13,159,962 across both epochs.
So the training step takes about 31.8h × (13,159,962 ÷ 12,577,240) ≈
**33h16m**. That is an estimate, not a measurement. `train_log.json`
records no duration, so once the run finishes, measure it the way the
17h42m figure below was measured — from process start to the adapter's
own mtime — and put that number here and everywhere else this runbook
quotes the estimate. The step count is exact, not estimated: the train
split is 6,377 rows, so at grad_accum 16 the run is 2 × ⌊6377 ÷ 16⌋ =
**796 optimizer steps**, and `train_log.json`'s `optimizer_steps`
confirms it when the run ends.

1. **Dataset** (seconds):
~~~~

Replace:

~~~~text
   incremental snapshots emitted several times within a single generation.
   Note the endpoint: `kv-eval`
~~~~

with:

~~~~text
   incremental snapshots emitted several times within a single generation.
   **2026-09-19 estimate:** the exam is 263 rows now, not 243. At the same
   ~1.8 rows/minute that is about 146 minutes, **~2½ hours**. It is scaled
   from the 149-row measurement above, not timed afresh: the 2026-09-19
   fix replayed 0908's banked outputs instead of re-serving (see below),
   so it produced no new timing.
   Note the endpoint: `kv-eval`
~~~~

Replace:

~~~~text
   and every metric is recomputed by today's code. It cost seconds where
   re-serving costs the ~2¼ hours below. It is valid only when the rows are the
   same rows — assert `len(banked) == len(rows)` and confirm the test bytes
~~~~

with:

~~~~text
   and every metric is recomputed by today's code. It cost seconds where
   re-serving costs the ~2¼ hours above (~2½ hours at today's 263-row exam,
   2026-09-19 estimate). It is valid only when the rows are the
   same rows — assert `len(banked) == len(rows)` and confirm the test bytes
~~~~

Replace:

~~~~text

3. **Train** (~17½ hours, CPU):

~~~~

with:

~~~~text

3. **Train** (~33 hours at this build, a pre-run estimate; CPU):

~~~~

Replace:

~~~~text

   **Budget about 17½ hours.** That is measured now, not estimated: one
   run has been timed end to end at **17h42m** — 4,292 examples, two
   epochs, 536 optimizer steps, just under two minutes per step. Two
   earlier versions of this line under-budgeted, first at "several hours"
~~~~

with:

~~~~text

   **The older 4,292-example build took about 17½ hours.** That is
   measured, not estimated: one run has been timed end to end at
   **17h42m** — 4,292 examples, two epochs, 536 optimizer steps, just
   under two minutes per step. Two
   earlier versions of this line under-budgeted, first at "several hours"
~~~~

Replace:

~~~~text

   A smoke run first is cheap and catches config errors:
~~~~

with:

~~~~text

   That 17h42m run and 0908 (31.8 hours, spec section 11) are both older,
   smaller builds. **2026-09-19 pre-run estimate for this retrain's
   build:** about **33h16m**, by the token-ratio formula in the box near
   the top of this runbook. It is an estimate, not a measurement: nothing
   has been trained on this build yet. Measure the real duration the way
   the 17h42m was measured, and put it here in place of the estimate.

   A smoke run first is cheap and catches config errors:
~~~~

Replace:

~~~~text
   `progress.json` for this. At the pinned recipe the run is ~536 optimizer
   steps, so at the default interval the file is rewritten about 21 times
   across the whole run — tens of minutes apart on this hardware. An mtime
   that has not moved for a few minutes means nothing.

~~~~

with:

~~~~text
   `progress.json` for this. At the pinned recipe the run is ~536 optimizer
   steps on the older build measured above; this retrain's build is
   **796 optimizer steps** (2 × ⌊6,377 ÷ 16⌋, exact — spec section 11 says
   "about 796"), so at the default interval the file is rewritten about 32
   times across the whole run — tens of minutes apart on this hardware. An
   mtime that has not moved for a few minutes means nothing.

~~~~

Replace:

~~~~text
   launch — so they stay bounds rather than durations, and the measurement
   above does not come from them.

~~~~

with:

~~~~text
   launch — so they stay bounds rather than durations, and the measurement
   above does not come from them. The 17h42m measurement is history now
   too: it is the 4,292-example build, not this one. **This retrain's build
   is 6,377 train rows and 796 optimizer steps, and its own duration is not
   measured yet.** The box near the top of this runbook carries the
   2026-09-19 pre-run estimate (~33h16m) and says what replaces it.

~~~~

- [ ] **Step 7: `cases.py` and `propagation.py`**

These are comments and a docstring. No code line moves.

**`src/kubeagent_verdict/dataset/cases.py`**

Replace:

~~~~text
    # strings the model can memorise. Drawn from the passed-in rng, before the
    # `healthy` branch: `generate.py:156-159` draws ONE salt and builds a
    # separate `random.Random(salt)` for each half, so both replay an identical
    # stream and both draw the SAME variant -- exactly the way they already
    # draw the same names. Only when the scenario declares variants; the eval
    # six declare none and must consume the RNG exactly as they did before.
    broken_origin, healthy_origin = p.origin_read[1], p.healthy_origin_content
~~~~

with:

~~~~text
    # strings the model can memorise. Drawn from the passed-in rng, before the
    # `healthy` branch: `generate.generate`'s shared-origin selection loop
    # draws ONE salt and builds a separate `random.Random(salt)` for each
    # half, so both replay an identical stream and both draw the SAME
    # variant -- exactly the way they already draw the same names. Only when
    # the scenario declares variants; the eval six declare none and must
    # consume the RNG exactly as they did before.
    broken_origin, healthy_origin = p.origin_read[1], p.healthy_origin_content
~~~~

**`src/kubeagent_verdict/dataset/propagation.py`**

Replace:

~~~~text
of its own half and absent from the other; no banned identifier shape
anywhere; and, across the pool, forty-eight scenarios taught in equal shares,
exercising all sixteen issue kinds, each rendering at least three of its
variants, with no cause template over 12% and the top three under 30%.

~~~~

with:

~~~~text
of its own half and absent from the other; no banned identifier shape
anywhere; and, across the pool, every scenario taught **within its own
sub-pool** in equal shares (ruling A in section 7 of
docs/superpowers/specs/2026-09-19-training-targets-fix-design.md) —
forty-eight plain stories sharing one rate, and, since the six "ruled"
stories joined the pool on 2026-09-19 (section 4 of the same spec), six
ruled stories sharing a second rate: a fifth of `shared_origin` pairs is
spread over six ruled stories and the other four fifths over forty-eight
plain ones, so a ruled story gets twice a plain story's share. Together
they exercise all sixteen issue kinds, each scenario rendering at least
three of its variants, with no cause template over 12% and the top three
under 30%.

~~~~

Replace:

~~~~text
    # Whether this victim hangs off a shared origin that has its own drawn
    # Object. True on every victim of the three scenarios that declare an
    # origin_object (node-not-ready, storage-provisioner-down,
    # registry-unreachable), False on every victim of the three that do not
    # (coredns-down, node-disk-pressure, networkpolicy-deny-all). It is
    # therefore redundant with `origin_object is not None` today; it is a
    # per-victim field because the binding it drives is per-victim — it lets
    # Task 6's builder bind the origin's own Object for this victim instead
    # of a separate decoy.
    on_origin: bool = False
~~~~

with:

~~~~text
    # Whether this victim hangs off a shared origin that has its own drawn
    # Object. True on every victim of a scenario that declares an
    # origin_object, False on every victim of one that does not. Among the
    # eval six it is True for the three whose job-3 label is "shared/none"
    # (node-not-ready, storage-provisioner-down, registry-unreachable) and
    # False for the other three (coredns-down, node-disk-pressure,
    # networkpolicy-deny-all). Since 2026-09-19, six training-only "ruled"
    # stories declare their own origin_object too (section 4 of the
    # 2026-09-19 training-targets design): node-kubelet-halted,
    # node-kubelet-unresponsive, pvc-provisioner-not-responding,
    # pvc-storageclass-missing, registry-mirror-unreachable and
    # registry-rate-limited. It is True on their victims as well. It is
    # therefore redundant with `origin_object is not None` today; it is a
    # per-victim field because the binding it drives is per-victim — it
    # lets Task 6's builder bind the origin's own Object for this victim
    # instead of a separate decoy.
    on_origin: bool = False
~~~~

Replace:

~~~~text
    # wrong candidate points at. Exactly one node decoy on every victim of
    # the three scenarios with no origin_object; empty on every victim where
    # on_origin is True, because the origin's own object already covers it.
~~~~

with:

~~~~text
    # wrong candidate points at. Exactly one node decoy on every victim of
    # a scenario with no origin_object; empty on every victim where
    # on_origin is True, because the origin's own object already covers it.
~~~~

Replace:

~~~~text
    notes: str = field(default="")
    # The origin's own declared identity, for the three scenarios whose
    # job-3 label is "shared/none": node-not-ready, storage-provisioner-down,
    # registry-unreachable. None for the three "none/none" scenarios, whose
    # victims still carry their own local decoys but whose shared origin is
    # never itself offered as a candidate object.
    origin_object: Object | None = None
~~~~

with:

~~~~text
    notes: str = field(default="")
    # The origin's own declared identity. Among the eval six it is set for
    # the three whose job-3 label is "shared/none" (node-not-ready,
    # storage-provisioner-down, registry-unreachable) and None for the
    # three "none/none" scenarios, whose victims still carry their own
    # local decoys but whose shared origin is never itself offered as a
    # candidate object. Since 2026-09-19 (section 4 of the training-targets
    # design) it is also set on the six training-only "ruled" stories (two
    # node, two PVC, two registry), so the rules pass has an origin object
    # it can check on its own and training carries rows the rules label
    # "shared" (before, no training row carried that label). A row can
    # still come out "none" on a ruled scenario: the unverified node twin
    # (section 5 of the same design) declares an origin_object the rules
    # cannot check at all, and the healthy-read decoy twin (every scenario
    # has one) declares one the rules refute.
    origin_object: Object | None = None
~~~~

- [ ] **Step 8: Check the first commit's changes**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff --stat | tail -1; \
  command grep -n "Task [0-9]" src/kubeagent_verdict/dataset/propagation.py; \
  command grep -c "this plan" docs/runbooks/train.md; \
  command grep -n "own cause when the rules" README.md docs/design.md docs/how-training-works.md; \
  command grep -c "Budget about 17" docs/runbooks/train.md; \
  command grep -c "33h16m" docs/runbooks/train.md
```

Expected, in order:
- `7 files changed, 169 insertions(+), 55 deletions(-)`.
- One line, the comment ending `lets Task 6's builder bind the origin's
  own Object for this victim`. It predates this branch and stays. Any
  other line means a block brought in a plan task number.
- `0`. The runbook is for whoever runs training. It does not point at
  this plan.
- Nothing. That phrase is the wrong rule. An undecided victim takes the
  story's cause, not its own.
- `0`. The old 17½-hour budget is now history, not a budget.
- `3`. The estimate appears three times.

Then run the suite and ruff:

```bash
cd /home/ubuntu/git/kubeagent-verdict && find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -1 && .venv/bin/ruff check .
```

Expected: `792 passed, 6 warnings in …` and `All checks passed!`.

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add README.md docs/design.md docs/how-training-works.md \
  docs/model-card.md docs/runbooks/train.md src/kubeagent_verdict/dataset/cases.py \
  src/kubeagent_verdict/dataset/propagation.py && \
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s \
  -m "docs: catch every doc and comment the mix move and rules fix made false" \
  -m "The case mix moved (shared-origin halves to 15%, multi to 13%), the pool grew from 48 stories to 54, and 14 exam rows took the rules' own answer. The README, design doc, training explainer, model card, runbook and two source comments still described the old state. Each line now says what the code does, with the dates and numbers that changed, and the runbook budgets about 33 hours for the next run."
```

- [ ] **Step 10: Write the known limits (spec §12)**

The first block fixes the paired-core paragraph in `docs/design.md`. The
second adds the "Known limits" section to `docs/model-card.md`, after the
last line of the section before it.

**`docs/design.md`**

Replace:

~~~~text
about the scenario predicts the label. `drop_held_out` takes pairs whole,
since both halves share a group key, so the paired core (440 against 440 at
the build size) survives the filter exactly. The residual lean is now the
surviving `multi` negatives, which have no positive twin: the kept pile reads
~0.57 toward the INDEPENDENT answer,
the opposite direction from the ~62/38 toward shared recorded before, and no
~~~~

with:

~~~~text
about the scenario predicts the label. `drop_held_out` takes pairs whole,
since both halves share a group key, so the paired core (1200 against 1200 at
the build size) survives the filter exactly. The residual lean is now the
surviving `multi` negatives, which have no positive twin: the kept pile reads
~0.543 toward the INDEPENDENT answer,
the opposite direction from the ~62/38 toward shared recorded before, and no
~~~~

**`docs/model-card.md`**

Replace:

~~~~text
   exposure — its job-2 number simply cannot prove it read anything.
~~~~

with:

~~~~text
   exposure — its job-2 number simply cannot prove it read anything.

## Known limits of the training data and the exam

These are known limits of the training data and the exam this build uses.
They are written down here before training, from the design that fixed the
training targets (`docs/superpowers/specs/2026-09-19-training-targets-fix-design.md`,
section 12). They are not new problems found after a run — they are choices
and trade-offs made on purpose, disclosed up front so a reader can weigh a
future result against them. When the next retrain's results are added to
this file, that section must link back here and check its numbers
against these.

1. **The exam's `node-not-ready` row says two things about node readiness.**
   The gold rationale says the Ready condition is False. The origin read
   printed in the same row says `Unknown`. Both are true readings of the
   same fault, worded two different ways — a model that expects the two
   words to match will not find them matching here.
2. **The exam's decoy-node rows put two reasons on one node.** In
   `coredns-down` and `node-disk-pressure`, the rule rationale talks about
   the decoy node while the rest of the row is about CoreDNS or disk
   pressure. Rows 248 and 258 (both `node-disk-pressure`) go further: the
   same node, worker-3, is named under two different rule reasons —
   "NotReady" and "no kubelet lease" — in the same row, and neither reason
   is what the row's own evidence shows for that node (disk pressure).
3. **The exam's storage story shows `Pending` where an internal field says
   `Bound`.** The row a model reads always says the claim is `Pending`,
   which is correct — the claim really is stuck. The propagation table that
   built the row also carries a `Bound` value, on the field that would
   apply if the origin were healthy. That field is never printed into the
   prompt; the mismatch is a fact about the code, not something a model
   can read.
4. **The exam's row 252 says "3 workloads failing to pull" and shows 2.**
   The rule's cause string names a fixed count from the story: "3
   workloads failing to pull". This probe row flags only 2 of those 3
   workloads, so the count written into the text and the count of rows a
   model is asked to judge do not match.
5. **One fixed rationale template.** Every rule row's rationale comes from
   one function, `_rule_rationale` in `dataset/cases.py`. A model could
   learn the template's wording instead of the reasoning behind it — job 1,
   which grades whether the model repeats the decided cause, cannot tell
   the two apart.
6. **Plain broken twins always deny a shared cause, even though both rows
   name the same origin.** A plain story's two twin rows both point at the
   same real cause, but the rules cannot check a plain story's origin, so
   the summary on both rows says the rules did not confirm one cause. A
   model could learn "never call a cause shared" from this pattern alone.
   The ruled broken twins teach the other side, because the rules can check
   a ruled story's origin: in this build 192 of them land in train and 22
   in val, all carrying the `shared` label. This build has 960 plain pairs
   and 240 ruled pairs (1,200 in all), and every one of the 48 plain
   stories keeps at least 15 of its 20 pairs in train. Three stories tie
   for the lowest, at 15 (`sidecar-injector-broken`, `node-corrupt-overlay`
   and `cluster-maintenance-taint`), and the highest is 20. A further 26 of the 240
   ruled pairs, drawn only from the two node-kind ruled stories, are
   deliberately rendered "unverified" instead of confirmed (25 land in
   train, 1 in val): the origin read is made to fail, so the rules cannot
   confirm or deny it, and the label is `none`, not `shared`. That is a
   third pattern, not a second copy of "plain" — it teaches "the rules
   could not check" as its own answer.
7. **No decoy rate on ruled stories.** Every ruled-story row, both twins in
   the pair, carries an empty `decoy_by_workload` — the field the
   decoy-rate check reads — because `_render_shared_origin` in
   `dataset/cases.py` leaves it empty whenever the story has a fixed origin
   object: a ruled story, or one of the exam-only stories that also fixes
   one. Today that covers 3 exam-only stories: `node-not-ready`,
   `storage-provisioner-down` and `registry-unreachable`. After this build
   it also covers the 240 ruled pairs, so the decoy-rate diagnostic sees
   none of them.
8. **Two read formats for one node.** kubeagent labels a node's own trail
   read `describe node /worker-2`, with a leading slash, and `read_text` in
   `dataset/rules.py` copies that label. The node stories in
   `dataset/propagation.py` write their own evidence heading as `describe
   node worker-2`, with no slash. Most rows print only one of the two. In
   this build, 62 `multi` rows in train and 9 in val print both in the same
   row, and in 42 of the 62 train rows it is the same node both times. The
   exam's node-story rows print only the story form. A model that expects
   one fixed format will see both.
~~~~

- [ ] **Step 11: Check the second commit's changes**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff --stat | tail -1; \
  command grep -c "440 against 440" docs/design.md; \
  command grep -c "^## Known limits" docs/model-card.md; \
  find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -1 && .venv/bin/ruff check .
```

Expected, in order: `2 files changed, 79 insertions(+), 2 deletions(-)`,
`0`, `1`, `792 passed, 6 warnings in …`, `All checks passed!`.

- [ ] **Step 12: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add docs/design.md docs/model-card.md && \
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s \
  -m "docs: write the known limits of the training data into the model card" \
  -m "Eight limits of this build's training data and exam, written down before the run so its results can be read against them: two readiness words in one exam row, two rule reasons on one decoy node, a Bound value the prompt never shows, a count that names three workloads where two are flagged, one fixed rationale template, plain twins that always deny a shared cause, no decoy rate on ruled stories, and two read formats for one node. The design doc's paired-core size and INDEPENDENT lean now match what the tests pin at the build size."
```

### Task 11: run the gates before any training

**Spec:** §10 "Gates before any training", gates 1 to 7.

**Files:** none tracked. Every script and every output goes under
`out/gates-2026-09-19/` in the repo. `out/` is in `.gitignore`, so git
does not see it and ruff does not lint it.

**Interfaces:**
- Consumes: the branch head after Task 10.
  - `kv-dataset --seed 17 --size 8000 --out <dir>`.
  - `kubeagent_verdict.train.config.TrainConfig` (its `base` names the
    tokenizer and its `max_seq_len` is 4096).
  - `kubeagent_verdict.train.data.encode_example(tok, system, user,
    assistant, max_len)`. It returns `(ids, labels)`, or `None` when the
    row is too long.
  - `kubeagent_verdict.evals.score.evaluate(rows, reply_fn)`,
    `scoreboard(results)`, and `JOB1_BAR`, `JOB2_BAR`, `JOB3_BAR`.
  - 0908's banked replies, `out/eval/0908/results.jsonl`. Read only.
- Produces: `out/gates-2026-09-19/gate7-sample.md` for a person to read,
  and the gate table in the task report. No commit.

This task measures. It does not fix. If a gate prints anything other than
its "Expected", stop and report the output. Do not change code to make a
gate pass. A failed gate means an earlier task went wrong, and the fix
belongs there, with its own test.

Every command starts with `cd /home/ubuntu/git/kubeagent-verdict` and sets
`G=out/gates-2026-09-19`. Shell state does not carry between commands, so
each one sets it again. Write each script with the Write tool, at the path
the step names, exactly as shown.

- [ ] **Step 1: Gate 4, the suite and ruff on a clean tree**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git status --short && \
  find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q 2>&1 | tail -1 && .venv/bin/ruff check .
```

Expected: `git status --short` prints nothing, then
`792 passed, 6 warnings in …`, then `All checks passed!`.

- [ ] **Step 2: Build the dataset, and check it is the reference build**

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && mkdir -p $G && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/kv-dataset --seed 17 --size 8000 --out $G/head && \
  (cd $G/head && sha256sum manifest.json train.jsonl val.jsonl test.jsonl)
```

Expected, exactly:

```text
400674b30f54d8ad21e64b92ef91c16edd287bfd9a02055fd6622a372fbf1653  manifest.json
41d384b16ab16096e665589c7bc7a15da9813173c6632213a986d4ee5d6837e3  train.jsonl
cd12e94485257919f4b8a9467f6c40bd7c0a0715b658e988533f5e990c3e9623  val.jsonl
e29dd9b8993577521b8c2f5b7d544cbdfa1916d9598fe93295f539954100b59b  test.jsonl
```

If any hash differs, stop and report. Every number in Task 10's words,
and every gate below, was measured on this exact build. These four hashes
are also the check the training host makes before the run.

- [ ] **Step 3: Gates 1 and 2, the oracle tests**

The oracle scores each row's own gold answer as if a model wrote it. A
gold answer that disagrees with the rules loses points here.

```bash
cd /home/ubuntu/git/kubeagent-verdict && find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_oracle.py -v 2>&1 | tail -14
```

Expected: `10 passed`. Which test is which gate:

| gate | tests | what they hold |
|------|-------|----------------|
| 1: train and val | `test_oracle_job1_is_perfect_on_train`, `…_on_val`; `test_oracle_job2_gate_is_perfect_on_train`, `…_on_val`; `test_oracle_job3_is_perfect_on_train`, `…_on_val` | job 1 and job 3 = 1.0; keyword-graded job 2 = 1.0 |
| 1: spec numbers | `test_oracle_job2_keyword_only_matches_the_spec_measurement`, `test_oracle_multi_job1_matches_the_spec_measurement` | the counts spec §10 measured |
| 2: the exam | `test_exam_oracle_job1_misses_only_contradiction_probe`, `test_exam_oracle_job3_is_perfect` | job 1 = 138 of 157 (0.879), job 3 = 1.0 |

The 19 exam rows job 1 misses are all `contradiction_probe`. They fail
with the gold answer too, and spec "Out of scope" leaves them alone.

- [ ] **Step 4: Gate 3, every row fits with the real tokenizer**

Write `out/gates-2026-09-19/gate3.py`:

```python
"""Gate 3: every row fits max_seq_len with the real tokenizer.

usage: HF_HUB_OFFLINE=1 gate3.py <dataset-dir>
"""

import json
import sys

from kubeagent_verdict.train.config import TrainConfig
from kubeagent_verdict.train.data import encode_example
from transformers import AutoTokenizer

DATASET = sys.argv[1]
cfg = TrainConfig()
tok = AutoTokenizer.from_pretrained(cfg.base)

total_rows = dropped = longest = train_tokens = 0
longest_row = None
for split in ("train", "val", "test"):
    with open(f"{DATASET}/{split}.jsonl", encoding="utf-8") as f:
        for i, line in enumerate(f):
            system, user, assistant = (m["content"] for m in json.loads(line)["messages"])
            total_rows += 1
            enc = encode_example(tok, system, user, assistant, cfg.max_seq_len)
            if enc is None:
                dropped += 1
                print(f"DROPPED: {split} line {i + 1}")
                continue
            ids, _labels = enc
            if len(ids) > longest:
                longest, longest_row = len(ids), f"{split} line {i + 1}"
            if split == "train":
                train_tokens += len(ids)

print(f"max_seq_len {cfg.max_seq_len}")
print(f"rows {total_rows}, dropped {dropped}")
print(f"longest {longest} tokens, at {longest_row}")
print(f"train tokens per epoch {train_tokens}, over both epochs {2 * train_tokens}")
```

Run it. It reads the tokenizer from the local Hugging Face cache and
never downloads.

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && \
  PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python $G/gate3.py $G/head
```

Expected, exactly:

```text
max_seq_len 4096
rows 7358, dropped 0
longest 2030 tokens, at train line 2777
train tokens per epoch 6579981, over both epochs 13159962
```

If the tokenizer will not load offline, stop and report. Do not turn
`HF_HUB_OFFLINE` off.

- [ ] **Step 5: Gate 5, the exam footprint**

Build the exam from the commit before this branch, `b5b3e65`. `git
archive` copies that tree out without touching the working tree, and
`PYTHONPATH` puts its source ahead of the installed one.

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && mkdir -p $G/base-src && \
  git archive b5b3e65 | tar -x -C $G/base-src && \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD/$G/base-src/src .venv/bin/kv-dataset \
    --seed 17 --size 8000 --out $G/base && \
  (cd $G/base && sha256sum manifest.json test.jsonl)
```

Expected, exactly:

```text
b84498570e62dd03b32e3a64ffc6fc0c64de6119e9337d0fb437564108f8ab26  manifest.json
c2d22b6e2d3b3ceeda82c7cadd150d67945e69afe85ac43b7f2eec3e9d9b45e2  test.jsonl
```

The `test.jsonl` hash is the one 0908's scoreboard recorded, so this is
the exam 0908 was scored on. If either hash differs, stop and report.

Write `out/gates-2026-09-19/footprint.py`:

```python
"""Gate 5: list the exam rows that differ from the baseline, and what moved.

usage: footprint.py <head-dataset-dir> <baseline-dataset-dir>
"""

import json
import sys

HEAD, BASE = sys.argv[1], sys.argv[2]


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


head = load(f"{HEAD}/test.jsonl")
base = load(f"{BASE}/test.jsonl")
assert len(head) == len(base) == 263, (len(head), len(base))

changed = [i for i, (h, b) in enumerate(zip(head, base)) if h != b]
print("changed rows, 1-based:", [i + 1 for i in changed])

for i in changed:
    h, b = head[i], base[i]
    # The prompt never moves. Only the gold answer and the meta that mirrors it.
    assert h["messages"][:2] == b["messages"][:2], f"row {i + 1}: the prompt moved"
    moved = sorted(
        k for k in set(h["meta"]) | set(b["meta"]) if h["meta"].get(k) != b["meta"].get(k)
    )
    assert set(moved) <= {"expected", "workloads"}, f"row {i + 1}: meta {moved} moved"
    for w, hw in h["meta"]["workloads"].items():
        bw = b["meta"]["workloads"][w]
        rest = {k for k in set(hw) | set(bw) if k != "expected_cause" and hw.get(k) != bw.get(k)}
        assert not rest, f"row {i + 1}, {w}: {sorted(rest)} moved"
    gold = h["messages"][2] != b["messages"][2]
    print(
        f"row {i + 1}: {h['meta']['case']}, {h['meta']['origin']}; gold answer moved: {gold}; meta moved: {moved}"
    )
```

Run it:

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python $G/footprint.py $G/head $G/base
```

Expected, exactly:

```text
changed rows, 1-based: [244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 258, 260, 263]
row 244: shared_origin_probe, coredns-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 245: shared_origin_probe, node-not-ready; gold answer moved: True; meta moved: ['expected', 'workloads']
row 246: shared_origin_probe, storage-provisioner-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 247: shared_origin_probe, registry-unreachable; gold answer moved: True; meta moved: ['expected', 'workloads']
row 248: shared_origin_probe, node-disk-pressure; gold answer moved: True; meta moved: ['expected', 'workloads']
row 249: shared_origin_probe, networkpolicy-deny-all; gold answer moved: True; meta moved: []
row 250: shared_origin_probe, coredns-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 251: shared_origin_probe, storage-provisioner-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 252: shared_origin_probe, registry-unreachable; gold answer moved: True; meta moved: ['expected', 'workloads']
row 253: shared_origin_probe, node-disk-pressure; gold answer moved: True; meta moved: ['expected', 'workloads']
row 254: shared_origin_decoy_probe, coredns-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 258: shared_origin_decoy_probe, node-disk-pressure; gold answer moved: True; meta moved: ['expected', 'workloads']
row 260: shared_origin_decoy_probe, coredns-down; gold answer moved: True; meta moved: ['expected', 'workloads']
row 263: shared_origin_decoy_probe, node-disk-pressure; gold answer moved: True; meta moved: ['expected', 'workloads']
```

Rows 244 to 253 are all ten `shared_origin_probe` rows. Rows 254, 258,
260 and 263 are four of the ten `shared_origin_decoy_probe` rows: every
one on `coredns-down` or `node-disk-pressure`. On every changed row, the
prompt is the same. Row 249 changes only its gold answer; its meta
already matched.

Then run the pin tests. They prove the view the scorer reads did not
move:

```bash
cd /home/ubuntu/git/kubeagent-verdict && find src tests -name __pycache__ -prune -exec rm -rf {} + && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_exam_graded_view.py \
  "tests/test_shared_origin_training.py::test_the_frozen_253_are_byte_identical_to_the_ones_every_scoreboard_used" \
  2>&1 | tail -1
```

Expected: `3 passed in …`.

- [ ] **Step 6: Gate 6, the negative control**

Replay 0908's banked replies against the new exam. 0908 was trained on
the old targets, so it must score exactly what it scored before on every
gated number, and still miss all three bars. The script checks row order
first, so a banked file in the wrong order fails loudly instead of
scoring the wrong rows.

Write `out/gates-2026-09-19/gate6.py`:

```python
"""Gate 6: replay 0908's banked replies against the new exam.

usage: gate6.py <test.jsonl> <0908 results.jsonl>
The results file is read, never written.
"""

import json
import sys

from kubeagent_verdict.evals.score import (
    JOB1_BAR,
    JOB2_BAR,
    JOB3_BAR,
    evaluate,
    scoreboard,
)


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


rows = load(sys.argv[1])
banked = load(sys.argv[2])
assert len(banked) == len(rows), (len(banked), len(rows))

# The banked file must be the exam, row for row, in the same order.
for i, (row, b) in enumerate(zip(rows, banked)):
    m = row["meta"]
    exam_key = (m["case"], m["label"], m.get("source"))
    banked_key = (b["case"], b["label"], b.get("source"))
    assert exam_key == banked_key, f"row {i + 1}: exam {exam_key!r}, banked {banked_key!r}"

replies = iter(b["output"] for b in banked)
board = scoreboard(evaluate(rows, lambda messages: next(replies)))
jobs, overall = board["jobs"], board["overall"]


def cell(d):
    return (d["rate"], d["n"])


must = {
    "job1": (cell(jobs["job1"]), (0.1783, 157)),
    "job2": (cell(jobs["job2"]), (0.2418, 153)),
    "job3": (cell(jobs["job3"]), (0.7179, 39)),
    "job3 shared": (cell(jobs["job3"]["by_label"]["shared"]), (1.0, 5)),
    "job3 none": (cell(jobs["job3"]["by_label"]["none"]), (0.6765, 34)),
    "contract validity": (cell(overall["contract_rate"]), (0.9696, 263)),
    "decoy rate": (cell(overall["decoy_rate"]), (0.0988, 243)),
    "suggestion echo": (cell(overall["suggestion_echo_rate"]), (0.0, 262)),
}
for name, (got, want) in must.items():
    status = "ok" if got == want else "MISMATCH"
    print(f"must reproduce  {name}: {got[0]} ({got[1]})  expected {want[0]} ({want[1]})  {status}")

for name, key in (
    ("cause accuracy", "cause_accuracy"),
    ("confidence carried", "confidence_carried"),
    ("overconfidence", "overconfidence_rate"),
):
    rate, n = cell(overall[key])
    print(f"reported        {name}: {rate} ({n})")

misses = (
    jobs["job1"]["rate"] < JOB1_BAR
    and jobs["job2"]["rate"] < JOB2_BAR
    and jobs["job3"]["rate"] < JOB3_BAR
)
print(f"0908 misses all three bars ({JOB1_BAR}, {JOB2_BAR}, {JOB3_BAR}): {misses}")

assert all(got == want for got, want in must.values()), (
    "a must-reproduce value moved; stop and report"
)
assert misses, "0908 passed a bar it should miss; stop and report"
print("gate 6 passed")
```

Run it:

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python $G/gate6.py $G/head/test.jsonl out/eval/0908/results.jsonl
```

Expected, exactly:

```text
must reproduce  job1: 0.1783 (157)  expected 0.1783 (157)  ok
must reproduce  job2: 0.2418 (153)  expected 0.2418 (153)  ok
must reproduce  job3: 0.7179 (39)  expected 0.7179 (39)  ok
must reproduce  job3 shared: 1.0 (5)  expected 1.0 (5)  ok
must reproduce  job3 none: 0.6765 (34)  expected 0.6765 (34)  ok
must reproduce  contract validity: 0.9696 (263)  expected 0.9696 (263)  ok
must reproduce  decoy rate: 0.0988 (243)  expected 0.0988 (243)  ok
must reproduce  suggestion echo: 0.0 (262)  expected 0.0 (262)  ok
reported        cause accuracy: 0.3302 (263)
reported        confidence carried: 0.5431 (263)
reported        overconfidence: 0.2093 (176)
0908 misses all three bars (0.9, 0.7, 0.9): True
gate 6 passed
```

The three "reported" lines may move. Spec §9 lists them as "may move,
reported". Overconfidence was 0.1717 on 167 rows before. It moves because
14 exam rows changed their gold answer, which changes which rows it
counts. Every "must reproduce" line must say `ok`.

- [ ] **Step 7: Gate 7, the hand-read sample**

The script picks rows by rule, never by line number, and fails if a rule
matches nothing. Each group opens with a "What to check" line for the
reader.

Write `out/gates-2026-09-19/gate7.py`:

```python
"""Write the gate 7 hand-read sample. Picks rows by rule, never by index.

usage: gate7.py <head-dataset-dir> <baseline-dataset-dir> <out.md>
"""

import json
import sys

HEAD, BASE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

RULED = [
    "node-kubelet-halted",
    "node-kubelet-unresponsive",
    "pvc-provisioner-not-responding",
    "pvc-storageclass-missing",
    "registry-mirror-unreachable",
    "registry-rate-limited",
]


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


train = load(f"{HEAD}/train.jsonl")
test = load(f"{HEAD}/test.jsonl")
base_test = load(f"{BASE}/test.jsonl")


def outcomes(row):
    """The set of decided outcomes on a row's workloads."""
    ws = row["meta"]["workloads"].values()
    return frozenset(w["decided_outcome"] for w in ws if w["decided"])


def first(pred, rows, skip=()):
    for i, r in enumerate(rows):
        if i not in skip and pred(r):
            return i
    raise SystemExit("no row matches a gate 7 rule; stop and report")


groups = []

# 1. Each ruled story: its first confirmed broken row, and the decoy twin
#    the generator writes right after it.
g = []
for story in RULED:
    i = first(
        lambda r, s=story: (
            r["meta"]["case"] == "shared_origin"
            and r["meta"]["origin"] == s
            and r["meta"]["label"] == "shared"
        ),
        train,
    )
    twin = train[i + 1]["meta"]
    assert twin["case"] == "shared_origin_decoy" and twin["origin"] == story, (i, twin)
    g += [
        (f"{story}, broken twin", "train", i),
        (f"{story}, decoy twin", "train", i + 1),
    ]
groups.append(
    (
        "1. Ruled stories, both twins",
        (
            "The broken twin: every victim names the rules' cause, and the summary calls it one "
            "shared cause. The decoy twin: each workload names its own cause, and the summary "
            "says the reasons are separate."
        ),
        g,
    )
)

# 2. Two ruled broken rows the rules could not check (label none).
g, seen = [], set()
for _ in range(2):
    i = first(
        lambda r: (
            r["meta"]["case"] == "shared_origin"
            and r["meta"]["origin"] in RULED
            and r["meta"]["label"] == "none"
        ),
        train,
        seen,
    )
    assert outcomes(train[i]) == {"unverified"}, i
    assert train[i]["meta"]["origin"].startswith("node-"), i
    seen.add(i)
    g.append((f"{train[i]['meta']['origin']}, unverified", "train", i))
groups.append(
    (
        "2. Unverified node twins",
        (
            "The origin read failed, so the rules could not check the node. Each victim still "
            "names the rules' cause, and the summary does not call it shared."
        ),
        g,
    )
)

# 3. Two plain broken rows, from two different stories.
g, stories = [], set()
for i, r in enumerate(train):
    m = r["meta"]
    if m["case"] == "shared_origin" and m["origin"] not in RULED and m["origin"] not in stories:
        stories.add(m["origin"])
        g.append((f"{m['origin']}, plain broken twin", "train", i))
        if len(g) == 2:
            break
groups.append(
    (
        "3. Plain broken twins",
        (
            "The rules cannot check a plain story's origin. Each victim names the story's cause, "
            "and the summary does not call it shared. Model-card limit 6 is about this pairing."
        ),
        g,
    )
)

# 4. Five multi rows with a decided workload.


def is_multi(r):
    return r["meta"]["case"] == "multi"


picks = [
    ("confirmed only", lambda r: is_multi(r) and outcomes(r) == {"confirmed"}),
    (
        "confirmed and unverified",
        lambda r: is_multi(r) and outcomes(r) == {"confirmed", "unverified"},
    ),
    ("unverified only", lambda r: is_multi(r) and outcomes(r) == {"unverified"}),
    ("unverified only", lambda r: is_multi(r) and outcomes(r) == {"unverified"}),
    (
        "healthy origin read",
        lambda r: is_multi(r) and r["meta"].get("origin_healthy") and outcomes(r),
    ),
]
g, seen = [], set()
for name, pred in picks:
    i = first(pred, train, seen)
    seen.add(i)
    g.append((f"multi, {name}", "train", i))
groups.append(
    (
        "4. Fixed multi rows",
        (
            "A decided workload names the rules' cause (a node line such as "
            "`node worker-3 (NotReady)`), not a catalog cause. An undecided one keeps its own cause."
        ),
        g,
    )
)

# 5. Every exam row whose bytes differ from the baseline build.
assert len(test) == len(base_test) == 263, (len(test), len(base_test))
changed = [i for i, (a, b) in enumerate(zip(test, base_test)) if a != b]
assert len(changed) == 14, changed
groups.append(
    (
        "5. The 14 changed exam rows",
        (
            "Compare the two gold answers; the prompt is the same. A decided workload now names "
            "the rules' cause, and the summary calls the cause shared only when the label is "
            "`shared`."
        ),
        [(f"exam row {i + 1} of 263", "test", i) for i in changed],
    )
)

out = [
    "# Gate 7 hand-read sample",
    "",
    "Read every row before any training. For each row, check that the gold",
    "answer is what kubeagent's rules would say for that prompt.",
    "",
    "## The system prompt (the same on every row)",
    "",
    "~~~~text",
    train[0]["messages"][0]["content"],
    "~~~~",
    "",
]
total = 0
for title, note, rows in groups:
    out += [f"## {title} ({len(rows)} rows)", "", f"What to check: {note}", ""]
    for name, split, i in rows:
        row = (train if split == "train" else test)[i]
        m = row["meta"]
        out += [f"### {name} ({split}.jsonl line {i + 1})", ""]
        out += [f"- case `{m['case']}`, label `{m['label']}`, origin `{m.get('origin', '-')}`"]
        for w, v in m["workloads"].items():
            out += [f"- `{w}`: decided {v['decided']}, outcome `{v['decided_outcome'] or '-'}`"]
        out += [
            "",
            "Prompt:",
            "",
            "~~~~text",
            row["messages"][1]["content"],
            "~~~~",
            "",
        ]
        if split == "test":
            out += ["Gold answer before this branch:", "", "~~~~json"]
            out += [base_test[i]["messages"][2]["content"], "~~~~", ""]
        out += [
            "Gold answer:",
            "",
            "~~~~json",
            row["messages"][2]["content"],
            "~~~~",
            "",
        ]
        total += 1

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print(f"wrote {total} rows to {OUT}")
for title, _note, rows in groups:
    print(title, [f"{s}:{i + 1}" for _, s, i in rows])
```

Run it:

```bash
cd /home/ubuntu/git/kubeagent-verdict && G=out/gates-2026-09-19 && \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python $G/gate7.py $G/head $G/base $G/gate7-sample.md
```

Expected, exactly:

```text
wrote 35 rows to out/gates-2026-09-19/gate7-sample.md
1. Ruled stories, both twins ['train:2357', 'train:2358', 'train:2367', 'train:2368', 'train:2377', 'train:2378', 'train:2387', 'train:2388', 'train:2397', 'train:2398', 'train:2405', 'train:2406']
2. Unverified node twins ['train:2475', 'train:2629']
3. Plain broken twins ['train:2349', 'train:2351']
4. Fixed multi rows ['train:1725', 'train:1706', 'train:1703', 'train:1704', 'train:1708']
5. The 14 changed exam rows ['test:244', 'test:245', 'test:246', 'test:247', 'test:248', 'test:249', 'test:250', 'test:251', 'test:252', 'test:253', 'test:254', 'test:258', 'test:260', 'test:263']
```

The five groups are the ones spec §10 gate 7 names: both twins of each
ruled story (12 rows), 2 unverified node twins, 2 plain broken twins, 5
fixed `multi` rows, and all 14 changed exam rows. That is 35 rows.

**Stop here.** Gate 7 is read by a person, not by an agent. Do not mark it
passed. Report the file's full path,
`/home/ubuntu/git/kubeagent-verdict/out/gates-2026-09-19/gate7-sample.md`,
and say that no training starts until the person has read it and says go.

- [ ] **Step 8: Report the gates**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git status --short
```

Expected: nothing. The gates wrote only under `out/`.

Put this table in the task report, with each value as measured:

| gate | what it checks | result |
|------|----------------|--------|
| 1 | oracle, train and val | job 1, job 2 (keyword-graded) and job 3 all 1.0 |
| 2 | oracle, exam | job 1 0.879 (138 of 157), job 3 1.0 |
| 3 | length | 7358 rows, 0 dropped, longest 2030 tokens |
| 4 | suite and ruff | 792 passed; ruff clean |
| 5 | exam footprint | 14 rows changed, prompts the same; 3 pin tests pass |
| 6 | negative control | every must-reproduce value ok; 0908 misses all three bars |
| 7 | hand read | 35 rows written; waiting for the person's read |

## After this plan

This plan ends at gate 7. Three things come next, in this order. None of
them is a plan task.

1. **A person reads the gate 7 sample.** It is
   `out/gates-2026-09-19/gate7-sample.md`, 35 rows. Training waits for
   their go. A gold answer that looks wrong there is a finding against the
   build, and it goes back to the task that built it.
2. **Merge the branch** with superpowers:finishing-a-development-branch,
   after the whole-branch review.
3. **The run, spec §11.** This plan does not cover it, on purpose.
   - On the training host, build the dataset first. Its four sha256
     values must match Task 11 Step 2's table. A different hash means the
     host's tree is not this branch; stop there.
   - At step 400, stop only if job 1 or job 3 is below 0.5 on val.
   - After the run, replace the runbook's 33h16m estimate with the
     measured time: from the training process's start to the adapter
     file's modification time.
   - The model card's new section for the run links to "Known limits of
     the training data and the exam". It reads its numbers against those
     limits before calling anything a surprise.
