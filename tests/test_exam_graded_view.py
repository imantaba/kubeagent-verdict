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
single-workload row mirrors them: `expected_cause` on 209 of the 249
rows and `expected_confidence` on 219 (211 and 221 of 251 before the
contradiction rows were decided by the rules on 2026-09-26; 213 and 223
of 252 before the job-1 rows moved onto the gather that day; 224 and 234
of 263 before the 2026-09-24 generator fix removed 11 `none_of_these`
rows). This view
keeps both. That makes
the pin stricter than the gated numbers need, never looser: a gold
cause or confidence that moved on one of those rows fails this test
instead of slipping past it. So the ungated extras -- cause accuracy,
confidence carried, overconfidence and the length gap -- are only
partly free to move. They read those two fields, and a row that carries
one of them is pinned on it.

`GRADED_VIEW_SHA256` pins the sha256 of that view over the whole exam
(`generate.test_set()`, 249 rows since the contradiction rows were
decided by the rules on 2026-09-26; 251 from when the job-1 rows moved
onto the gather that day; 252 from 2026-09-24; 263 before). This is not
a TDD red test: it
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

Re-pinned on 2026-09-24 for the job-2 generator fix
(2026-09-24-job2-generator-fix-design.md). This time the user message
moves, and this view keeps it whole, so the digest follows every rendered
change `FROZEN_SLICE_SHA256`'s 2026-09-24 entry lists in
`tests/test_shared_origin_training.py`. The new exam is a new baseline.
It moved four times on that branch: once for the catalogue's log-cause
text, once for the single undecided builder, which also cut the exam from
263 rows to 252, once for the multi-workload rows' log reads and headers,
and once for `empty_candidates`' confidence and log read.

Re-pinned on 2026-09-26 for the faithful prompts. A row with a node
candidate now opens its inventory with kubeagent's cluster-health block,
so 150 of the 252 user messages gain it. Each of them changes by exactly
that block; no meta field and no gold answer moves, and no other row does.

Re-pinned again on 2026-09-26, when the catalog began using the detector
and kubelet text kubeagent really prints. 218 of the 252 user messages
change: the finding, event and describe-node lines now carry
kubeagent's own words. Meta fields move too. Eleven entries have new
keyword pairs (66 workloads' `own_cause_keywords`, 22 rows'
`expected_own_keywords`). Five impossible PVC decoys became node decoys or
went away, so `decoy_cause` moves on 16 rows, `decoy_causes` on 7 and
`decoy_by_workload` on 50. `worker-containerd-stop`'s own cause now uses
the kubelet's words, which moves `expected_cause` on 4 single-workload
rows. Three `contradiction_probe` workloads now decide on a node decoy
instead of a PVC one, and the `oversized` one is undecided now, so it
moves from job 1 to job 2. No row's `flagged` list and no system message
moves.

Re-pinned again on 2026-09-26, when the undecided job-2 rows began taking
their reads and candidates from the ported gather. 71 of the 252 user
messages change, all in the five undecided cases: each row reads its pod's
events first, as kubeagent does, a ruled-out node gets no describe, and
`deployment-bad-image-tag`'s refuted row shows its registry ruled out. That
row's `decoy_cause` and `decoy_by_workload` now name `registry
registry.example.com`, the cause its candidate line prints; no other meta
field moves. No gold answer, `flagged` list or system message moves.

Re-pinned again on 2026-09-26, when the job-1 rows began taking their
reads, candidates and gold from the gather and the rules. The exam is a
new baseline: it has 251 rows, not 252, and rows move from the first one
on, because the corpus rows lead the file. 114 of the 251 user messages
are new: every `attributed`, `truncated`, `injection` and
`positional_probe` row (73); the 31 corpus rows whose entry the rules do
not decide, which are `own_cause` rows now; the new entry
`pvc-unbound-unschedulable`'s rows (one each in `own_cause`,
`empty_candidates`, `wrong_attribution` and `misattribution_probe`, and
two `multi_misattribution_probe` pairs that replace one); and the four
rows where `node-cordon-diskfull`'s node is now ruled out (one each in
`wrong_attribution` and `contradiction_probe`, two in
`multi_misattribution_probe`). The other 137 user messages are byte for
byte ones the old exam had. A job-1 row's gold is now the rules' cause,
so `expected_cause`, the confidence, the rationale, the summary and
`decoy_by_workload` move on every job-1 row.

Re-pinned again on 2026-09-26, when the `contradiction_probe` rows began
taking their reads from the gather and their gold from the rules. The
exam has 249 rows, not 251: the loop runs over the 17 entries the rules
decide, so the rows of `deployment-bad-image-tag` (job 1),
`node-cordon-diskfull` and `oversized-job-unschedulable` (both job 2)
leave it, and the new entry `pvc-unbound-unschedulable` joins it. Job 1
keeps 118 workloads and job 2 goes from 181 to 179. All 17
`contradiction_probe` user
messages are new; the other 232 rows are byte for byte the old ones, in
the same order. Each of the 17 rows is job 1 and its gold is the rules'
cause; the 16 older ones answered `none_of_these` before. So
`expected_cause`, the confidence, the rationale, the summary and
`decoy_by_workload` move on every one of them, and `decoy_cause` is gone
from their meta. No other row's meta, `flagged` list or system message
moves.
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


# 2026-09-26 (faithful prompts): 150 user messages gain the cluster-health block
# 250f2bc2bc6860ec5e04e9574e36b8cf23cea2625961b735bb1a0888914d5b18 ->
# 2833890df618364320a7d3932931ae093c8950c14c24e235bbcced390f5c59a7
# 2026-09-26 (faithful prompts): kubeagent's own detector and kubelet text,
# new keyword pairs, and node decoys where PVC decoys could not happen
# 2833890df618364320a7d3932931ae093c8950c14c24e235bbcced390f5c59a7 ->
# 00ee341349ee02ff2635eeee3db508ba7991a3ca980c14a0061bb5bfe031aba5
# 2026-09-26 (faithful prompts): the undecided rows read what the gather
# reads, events first, and show the registry kubeagent rules out
# 00ee341349ee02ff2635eeee3db508ba7991a3ca980c14a0061bb5bfe031aba5 ->
# 08a419b9c3e34487be700bff6c97904dfd0fbc3e4fb1d6508be6391071f600ab
# 2026-09-26 (faithful prompts): the job-1 rows are built on the gather with
# the rules' gold, the corpus rows the rules do not decide ask for their own
# cause, a new entry joins, and node-cordon-diskfull's node is ruled out
# 08a419b9c3e34487be700bff6c97904dfd0fbc3e4fb1d6508be6391071f600ab ->
# 39ff30183aafa929e594770e43ae04d3d2e43eeda8bb77dc47b92c9a459b195d
# 2026-09-26 (faithful prompts): the contradiction rows are decided by the
# rules, on the gather, over the 17 entries the rules decide
# 39ff30183aafa929e594770e43ae04d3d2e43eeda8bb77dc47b92c9a459b195d ->
# 8f227d0b35cb125235cac095e46a6448bb23cdfc3afa6bebb73f8fb40a7401f3
GRADED_VIEW_SHA256 = "8f227d0b35cb125235cac095e46a6448bb23cdfc3afa6bebb73f8fb40a7401f3"


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
