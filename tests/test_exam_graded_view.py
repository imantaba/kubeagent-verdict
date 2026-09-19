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
