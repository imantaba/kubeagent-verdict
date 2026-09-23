"""Pins the "graded view" of the exam: what every gated number reads.

The gated numbers -- the three job bars, contract validity, decoy rate
and suggestion echo -- never see a whole row. They see the system and
user messages, which workloads the gold JSON's `verdicts` list flags,
and the per-workload meta fields job 1 and job 2 grade. `view(row)`
reduces a row to that shape. It drops the `meta["expected"]` dict and
each workload's `expected_cause` string -- a model never sees either --
and keeps one boolean instead, `expects_none_of_these`, the only fact
about `expected_cause` job 2 switches on (exact match vs. keyword
match).

Two gold fields do survive, at the top of `meta`, where a
single-workload row mirrors them: `expected_cause` on 224 of the 263
rows and `expected_confidence` on 234. This view keeps both. That makes
the pin stricter than the gated numbers need, never looser: a gold
cause or confidence that moved on one of those rows fails this test
instead of slipping past it. So the ungated extras -- cause accuracy,
confidence carried, overconfidence and the length gap -- are only
partly free to move. They read those two fields, and a row that carries
one of them is pinned on it.

`GRADED_VIEW_SHA256` pins the sha256 of that view over the whole exam
(`generate.test_set()`, 263 rows). This is not a TDD red test: it
passes today, before the training-targets fix, because the fix only
touches shared-origin rows, and this view keeps none of the fields it
changes there -- their gold cause lives in the `meta["expected"]` dict.
The 14-row exam move in a later task must leave this hash unchanged --
that is the whole point of pinning it here first.

Re-pinned on 2026-09-23 for the exam-grader fix
(2026-09-23-exam-grader-fix-design.md). Unlike the training-targets fix
above, this one moves a field the view DOES keep: `own_cause_keywords`
is a per-workload meta field, not `expected_cause`, so `view()`'s
"everything except `expected_cause`" rule carries it through untouched.
Twenty shared-origin workloads' `own_cause_keywords` move from `[]` to a
curated pair (see `tests/test_shared_origin_training.py`'s matching
2026-09-23 entries), and the digest moves with them -- on the same 11
rows, nothing else.
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


GRADED_VIEW_SHA256 = "b82b87977414e01e5d58eeb64defc5dec350bab6f567006d02ea96932700b03e"


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
