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


def _gold_results(examples: list, *, grade_job2: bool = True) -> list[dict]:
    """`score.evaluate`, fed each row's OWN gold assistant content as the
    model's reply -- the oracle read, byte for byte. `evaluate` calls
    `chat_fn` once per row, in order, so a plain iterator over the same
    rows' gold content lines up with no row identity lookup needed.

    `grade_job2=False` for the train and val pools, and only there. Nothing
    grades the training pool by keyword: 4,880 train and 532 val job-2
    workloads carry a named expected cause and no keywords (measured
    2026-09-24 against `out/dataset-0924`; the job-2 generator fix moved
    this count from the 0923 bank's 4,823/589; 2026-09-26 (faithful
    prompts): `out/dataset-0926` counts 4,900 train and 512 val, every one
    in a `shared_origin` or `shared_origin_decoy` row; 2026-09-28 (final
    review): `out/dataset-0928`, which replaced it, counts the same), and
    `score.evaluate`
    refuses such a corpus rather than scoring it zero.
    Job 2 on those pools is measured by `_job2_gate` below, over the
    population spec section 10 gate 1 defines. The exam passes nothing and
    is graded in full -- see `test_exam_oracle_job2_is_perfect`.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    No train or val workload is named without keys any more: the unkeyed counts above read 0 on both
    sides (measured in step D3), because every named job-2 workload of a rebuilt row carries the
    keys of its answer. `grade_job2=False` stays: the pools are still measured by `_job2_gate` and
    `_job2_keyword_only` below, not by `evaluate`.
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


@functools.lru_cache(maxsize=1)
def _exam() -> tuple[list, tuple[dict, ...]]:
    exam = generate.test_set()
    return exam, tuple(_gold_results(exam))


def _job2_gate(examples: list) -> dict:
    """job2 averaged over exactly the population spec section 10 gate 1
    defines: a workload where `score._is_job2_keyword_graded` is true, or
    whose `expected_cause` is `none_of_these` (exact match).

    NOT `scoreboard()`'s own job2 rate: `evaluate` puts every job==2
    workload in `job2_scores`, and `job2` itself now refuses a keyword-less,
    non-`none_of_these` workload outright. This gate filters such a
    workload out before calling `job2` at all -- it is out of scope for
    this gate, which never meets one.
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
    # Re-measured 2026-09-19 (Task 9: pool merge + mix change, spec section
    # 6) -- 2570 to 3056. Rate unchanged at 1.0.
    # Re-measured 2026-09-24 (job-2 generator fix: the undecided builders no
    # longer draw from the rng, which moves every later draw, and the
    # held-out `none_of_these` slice is 8 groups, not 19) -- 3056 to 3081.
    # Rate unchanged.
    # Re-measured 2026-09-24 again (case mix: `none_of_these` 11% -> 4%,
    # `own_cause` 10% -> 13%, `wrong_attribution` 10% -> 14%; the row
    # counts change, and so does every later rng draw) -- 3081 to 3120.
    # Rate unchanged.
    # 2026-09-26 (faithful prompts): the catalog now uses the text kubeagent
    # prints. Five impossible PVC decoys became node decoys or went away,
    # and restarts start at 3, so those entries draw from the rng a
    # different number of times; every later name moves, and so does the
    # group-hash split (841 val rows before the held-out drop, not 736). The
    # case mix is unchanged. 3120 -> 3072. Rate unchanged.
    # 2026-09-26 (faithful prompts): the `attributed`, `truncated` and
    # `injection` rows now rotate over the 17 entries the rules decide, not
    # all 19, and build their prompt from the evidence gather. A new entry
    # (`pvc-unbound-unschedulable`) joins the catalog. Every later rng draw
    # moves, and so does the split. 3072 -> 3030. Rate unchanged.
    # 2026-09-26 (faithful prompts): `contradiction_probe` now runs over the
    # 17 entries the rules decide, so the exam's groups changed and
    # `drop_held_out` drops different training rows. No training row is
    # built differently. The exam lost `node-cordon-diskfull:edge/worker`,
    # which lets one `own_cause` row back in (job 2), and gained
    # `pvc-unbound-unschedulable:billing/gateway`, which drops one
    # `wrong_attribution` row (job 2) and one `multi` row with two decided
    # workloads (job 1). 3030 -> 3028. Rate unchanged.
    # 2026-09-26 (faithful prompts): the `multi` rows moved onto the gather.
    # The node list grew from three workers to five, so every name drawn
    # after a node draw moves, and so do the groups and the split (6424
    # train rows -> 6415, 727 val rows -> 749). A `multi` row now redraws
    # any workload that shares a workload, a node or a claim with one
    # already in the row, and the worker-containerd-stop self-pair takes
    # the last counted `multi` slot, so a build has exactly `size` rows.
    # 3028 -> 3058. Rate unchanged.
    # 2026-09-26 (faithful prompts): coredns-corefile-broken draws its
    # restarts from 6, not 1, because its finding text fixes restartCount=6
    # and kubeagent's workload line sums its containers' restarts. The
    # restart count is the last field `names.draw` draws, so no other field
    # of that draw changes, but `randint(6, 40)` sometimes throws away a raw
    # draw that `randint(1, 40)` kept. From the first such draw on every
    # later name moves, and so do the groups and the split (kept rows: 6415
    # train -> 6457, 749 val -> 721). The case mix is unchanged. 3058 ->
    # 3074. Rate unchanged.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 3074.
    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3151}


def test_oracle_job1_is_perfect_on_val():
    board = score.scoreboard(list(_val_results()))
    # Re-measured 2026-09-19, same reason. 289 to 355. Rate unchanged.
    # Re-measured 2026-09-24, job-2 generator fix. 355 to 357. Rate unchanged.
    # Re-measured 2026-09-24 again, case mix. 357 to 309. Rate unchanged.
    # 2026-09-26 (faithful prompts): same reason as train; the split moved
    # and val grew. 309 -> 356. Rate unchanged.
    # 2026-09-26 (faithful prompts): job-1 rows on the gather, same reason
    # as train. 356 -> 319. Rate unchanged.
    # 2026-09-26 (faithful prompts): `multi` rows on the gather and five
    # workers, same reason as train; val grew. 319 -> 376. Rate unchanged.
    # 2026-09-26 (faithful prompts): coredns draws its restarts from 6, same
    # reason as train; the split moved. 376 -> 387. Rate unchanged.
    assert board["jobs"]["job1"] == {"rate": 1.0, "n": 387}


def test_oracle_job2_gate_is_perfect_on_train():
    # Re-measured 2026-09-19, same reason. 3121 to 2975. Rate unchanged.
    # Re-measured 2026-09-24, job-2 generator fix. 2975 to 3000. Rate unchanged.
    # Re-measured 2026-09-24 again, case mix. 3000 to 3030. Rate unchanged.
    # 2026-09-26 (faithful prompts): the rng stream and the split moved, as
    # for job 1. 3030 -> 2859. Rate unchanged.
    # 2026-09-26 (faithful prompts): job-1 rows on the gather, same reason
    # as job 1. 2859 -> 2999. Rate unchanged.
    # 2026-09-26 (faithful prompts): coredns draws its restarts from 6, same
    # reason as job 1; the split moved. 2999 -> 3017. Rate unchanged.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 3017.
    assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 8041}


def test_oracle_job2_gate_is_perfect_on_val():
    # Re-measured 2026-09-19, same reason. 352 to 304. Rate unchanged.
    # Re-measured 2026-09-24, job-2 generator fix. 304 to 321. Rate unchanged.
    # Re-measured 2026-09-24 again, case mix. 321 to 298. Rate unchanged.
    # 2026-09-26 (faithful prompts): same reason. 298 -> 315. Rate unchanged.
    # 2026-09-26 (faithful prompts): job-1 rows on the gather, same reason.
    # 315 -> 336. Rate unchanged.
    # 2026-09-26 (faithful prompts): the exam lost
    # `oversized-job-unschedulable:web/checkout`, so `drop_held_out` lets
    # four `own_cause` val rows in that group back in, one job-2 workload
    # each. 336 -> 340. Rate unchanged.
    # 2026-09-26 (faithful prompts): `multi` rows on the gather and five
    # workers, same reason as job 1; the split moved. 340 -> 321. Rate
    # unchanged. (Train stays at 2999 by chance.)
    # 2026-09-26 (faithful prompts): coredns draws its restarts from 6, same
    # reason as job 1; the split moved. 321 -> 326. Rate unchanged.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 326.
    assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 906}


def test_oracle_job2_keyword_only_matches_the_spec_measurement():
    """Before this fix the spec measures 0.9149 (1990 of 2175) here.
    After it, this narrower slice is also perfect.

    Re-measured 2026-09-19 (Task 9: pool merge + mix change, spec section
    6) -- 2175 to 2286. Rate still 1.0.

    Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
    above) -- 2286 to 2324. Rate still 1.0.

    Re-measured 2026-09-24 again (case mix, same reason as job 1 above)
    -- 2324 to 2785. Most of the rise is the extra `own_cause` and
    `wrong_attribution` rows, which are keyword-graded. Rate still 1.0.

    2026-09-26 (faithful prompts): the rng stream and the split moved, as
    for job 1 above. 2785 -> 2621. Rate still 1.0.

    2026-09-26 (faithful prompts): job-1 rows on the gather, same reason
    as job 1 above. 2621 -> 2748. Rate still 1.0.

    2026-09-26 (faithful prompts): `multi` rows on the gather and five
    workers, same reason as job 1 above. 2748 -> 2747. Rate still 1.0.

    2026-09-26 (faithful prompts): coredns-corefile-broken draws its
    restarts from 6, same reason as job 1 above. 2747 -> 2766. Rate still
    1.0.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    2766 -> 6580. Every named job-2 workload of a rebuilt row is keyword-graded now, so the family
    adds to this slice. Rate still 1.0."""
    # 2026-09-26 (faithful prompts): see the docstring. 2748 -> 2747.
    # 2026-09-26 (faithful prompts): see the docstring. 2747 -> 2766.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 2766.
    assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 6580}


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
    after the pool merge.

    Re-measured 2026-09-24 (job-2 generator fix, same reason as job 1
    above) -- 2790 to 2803; all 13 new rows are `none`-labeled. Rate still
    1.0.

    Re-measured 2026-09-24 again (case mix, same reason as job 1 above) --
    2803 to 2832: `shared` 192 to 195, `none` 2610 to 2636. Rate still
    1.0.

    2026-09-26 (faithful prompts): the rng stream and the split moved, as
    for job 1 above. 2832 -> 2736: `shared` 195 -> 183, `none` 2636 ->
    2552, `separate` still 1. Rate still 1.0.

    2026-09-26 (faithful prompts): job-1 rows on the gather, same reason
    as job 1 above. 2736 -> 2793: `shared` 183 -> 190, `none` 2552 ->
    2590, `separate` 1 -> 13. All 12 new `separate` rows are `multi` rows
    that pair the new `pvc-unbound-unschedulable` entry (its PVC
    confirmed) with `worker-containerd-stop` (its node confirmed): two
    confirmed causes, and no shared one. The 13th is still two
    `worker-containerd-stop` workloads on different nodes. Rate still
    1.0.

    2026-09-26 (faithful prompts): the exam's `contradiction_probe` groups
    changed, so `drop_held_out` drops the one `multi` row in the new
    `pvc-unbound-unschedulable:billing/gateway` group, labeled `none` (see
    job 1 above). 2793 -> 2792: `none` 2590 -> 2589. Rate still 1.0.

    2026-09-26 (faithful prompts): `multi` rows on the gather and five
    workers, same reason as job 1 above. 2792 -> 2766: `shared` 190 ->
    186, `separate` 13 -> 11, `none` 2589 -> 2569. The 11 `separate` rows
    still pair `pvc-unbound-unschedulable` (its PVC confirmed) with
    `worker-containerd-stop` (its node confirmed). The self-pair row is
    `separate` too, but one of its two workloads
    (`worker-containerd-stop:media/scheduler`) is an exam
    `wrong_attribution` row's identity, so `drop_held_out` drops it.
    Rate still 1.0.

    2026-09-26 (faithful prompts): coredns-corefile-broken draws its
    restarts from 6, same reason as job 1 above. 2766 -> 2830: `shared`
    186 -> 194, `separate` 11 -> 13, `none` 2569 -> 2623. 12 of the 13
    `separate` rows still pair `pvc-unbound-unschedulable` (its PVC
    confirmed) with `worker-containerd-stop` (its node confirmed). The 13th
    is the self-pair row: it drew new names that no exam row holds, so
    `drop_held_out` keeps it now. Rate still 1.0.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    2830 -> 2812: `shared` 194 -> 712, `separate` 13 -> 13 (the `multi` rows only; the shared-origin
    rows are labelled `shared` or `none`), `none` 2623 -> 2087. Rate still 1.0."""
    board = score.scoreboard(list(_train_results()))
    # 2026-09-26 (faithful prompts): see the docstring. 2792 -> 2766;
    # shared 190 -> 186, separate 13 -> 11, none 2589 -> 2569.
    # 2026-09-26 (faithful prompts): see the docstring. 2766 -> 2830;
    # shared 186 -> 194, separate 11 -> 13, none 2569 -> 2623.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 2830: shared 194, separate 13, none 2623.
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 2812,
        "by_label": {"shared": {"rate": 1.0, "n": 712},
                     "separate": {"rate": 1.0, "n": 13},
                     "none": {"rate": 1.0, "n": 2087}}}


def test_oracle_job3_is_perfect_on_val():
    """Val side of the same extension: 19 of the split's rows are a ruled
    story's broken twin, labeled `shared`, and the gold summary matches on
    every one -- re-measured 2026-09-19, Task 9 (22 rows then).

    Re-measured 2026-09-24 (case mix, same reason as job 1 above) -- 336 to
    296: `shared` 22 to 19, `none` 314 to 277. Rate still 1.0.

    2026-09-26 (faithful prompts): the rng stream and the split moved, as
    for job 1 above. 296 -> 351: `shared` 19 -> 31, `none` 277 -> 320.
    Rate still 1.0.

    2026-09-26 (faithful prompts): job-1 rows on the gather, same reason
    as job 1 above. 351 -> 313: `shared` 31 -> 24, `none` 320 -> 288,
    `separate` 0 -> 1 (a `pvc-unbound-unschedulable` workload next to a
    `worker-containerd-stop` one, as on the train side). Rate still
    1.0.

    2026-09-26 (faithful prompts): `multi` rows on the gather and five
    workers, same reason as job 1 above. 313 -> 346: `shared` 24 -> 28,
    `none` 288 -> 318, `separate` 1 -> 0. No `separate` row lands in val
    at this seed, so its rate is None; the train side still has 11.
    Rate still 1.0.

    2026-09-26 (faithful prompts): coredns-corefile-broken draws its
    restarts from 6, same reason as job 1 above; val shrank. 346 -> 308:
    `shared` 28 -> 20, `none` 318 -> 288, `separate` still 0. Rate still
    1.0.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    308 -> 326: `shared` 20 -> 83, `none` 288 -> 243, `separate` still 0. Rate still 1.0."""
    board = score.scoreboard(list(_val_results()))
    # 2026-09-26 (faithful prompts): see the docstring. 313 -> 346;
    # shared 24 -> 28, separate 1 -> 0, none 288 -> 318.
    # 2026-09-26 (faithful prompts): see the docstring. 346 -> 308;
    # shared 28 -> 20, separate 0 -> 0, none 318 -> 288.
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 308: shared 20, none 288.
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 326,
        "by_label": {"shared": {"rate": 1.0, "n": 83},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 243}}}


def test_oracle_multi_job1_matches_the_spec_measurement():
    """The exact number spec section 1 cites for the `multi` fix alone:
    every decided `multi` workload passes job1.

    Re-measured 2026-09-19 (Task 9: the `multi` share of the mix rose from
    11% to 13%, spec section 6) -- 996 of 996 to 1209 of 1209 in train, 121
    of 121 to 145 of 145 in val. Still perfect.

    Re-measured 2026-09-24 (job-2 generator fix: the undecided builders no
    longer draw from the rng, so every `multi` row draws new names, and the
    held-out `none_of_these` slice is 8 groups, not 19) -- 1209 to 1227 in
    train; val unchanged at 145. Still perfect.

    Re-measured 2026-09-24 again (case mix: the `multi` share is unchanged,
    but every `multi` row draws new names, so the split moves) -- 1227 to
    1226 in train, 145 to 132 in val. Still perfect.

    2026-09-26 (faithful prompts): the `multi` share is unchanged again,
    but the rng stream moved (five PVC decoys became node decoys or went
    away), so the names and the split moved -- 1226 -> 1240 in train, 132 -> 118 in val. Still
    perfect.

    2026-09-26 (faithful prompts): job-1 rows on the gather. The `multi`
    share is unchanged, but the rng stream moved and a new entry joined
    the pool, so the names and the split moved -- 1240 -> 1161 in train,
    118 -> 109 in val. Still perfect.

    2026-09-26 (faithful prompts): the exam's `contradiction_probe` groups
    changed, so `drop_held_out` drops one `multi` train row with two decided
    workloads (see job 1 above) -- 1161 -> 1159 in train; val unchanged at
    109. Still perfect.

    2026-09-26 (faithful prompts): `multi` rows are built on the gather.
    Their gold cause is the rules' own decision over the gathered reads,
    the node list grew to five workers, and a row redraws any workload
    that clashes with one already in it, so more workloads decide and the
    split moved (see job 1 above) -- 1159 -> 1188 in train, 109 -> 140 in
    val. Still perfect.

    2026-09-26 (faithful prompts): coredns-corefile-broken draws its
    restarts from 6, so the rng stream and the split moved (see job 1
    above) -- 1188 -> 1207 in train, 140 -> 163 in val. Still perfect."""
    def multi_job1(results):
        scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
        return sum(scores), len(scores)

    # 2026-09-26 (faithful prompts): see the docstring. (1240.0, 1240) ->
    # (1161.0, 1161); (118.0, 118) -> (109.0, 109).
    # 2026-09-26 (faithful prompts): see the docstring. (1161.0, 1161) ->
    # (1159.0, 1159).
    # 2026-09-26 (faithful prompts): see the docstring. (1159.0, 1159) ->
    # (1188.0, 1188); (109.0, 109) -> (140.0, 140).
    # 2026-09-26 (faithful prompts): see the docstring. (1188.0, 1188) ->
    # (1207.0, 1207); (140.0, 140) -> (163.0, 163).
    assert multi_job1(_train_results()) == (1207.0, 1207)
    assert multi_job1(_val_results()) == (163.0, 163)


def test_exam_oracle_job1_is_perfect():
    """spec section 10 gate 2: the frozen exam's own job1, oracle-read.
    138 of 156 pass; the 18 misses are exactly the `contradiction_probe`
    rows, a case whose gold reply is engineered to contradict what job1
    grades by design -- not a shared-origin regression. No `multi`,
    `shared_origin_probe` or `shared_origin_decoy_probe` row misses.

    2026-09-26 (faithful prompts): the `oversized` entry's node decoy now
    sits on another node, so kubeagent rules it out. Its
    `contradiction_probe` row has no attributed candidate any more; it is
    undecided, so it moved from job 1 to job 2. 157 -> 156 graded, 19 -> 18
    misses; the 138 passes do not move.

    2026-09-26 (faithful prompts): job-1 rows are built on the gather now.
    `attributed` fell from 53 rows to 22, and the corpus rows the rules do
    not decide became `own_cause` rows, which are job 2. `truncated`,
    `injection` and `positional_probe` fell from 19 rows to 17. The
    `node-cordon-diskfull` `contradiction_probe` row also left job 1: its
    node object now names a node the pod is not on, so the rules rule it
    out and the row is undecided. 156 -> 118
    graded, 138 -> 101 passes, 18 -> 17 misses -- still exactly the
    `contradiction_probe` rows.

    2026-09-26 (faithful prompts): `contradiction_probe` rows are built on
    the gather and answer the rules' cause, so job 1 grades them like any
    other decided row and they pass. The 17 old job-1 rows are replaced by
    17 new ones. 118 graded, 101 -> 118 passes, 17 -> 0 misses: a model that
    answers each row with that row's gold content scores every job-1
    workload.

    2026-09-26 (faithful prompts): the node list grew from three workers
    to five, so two shared-origin stories drew differently. In the
    `networkpolicy-deny-all` probe row and its decoy twin, two victims
    that were undecided are now decided on a node their pod runs on (+4
    job 1). In the `node-disk-pressure` probe row and its decoy twin, the
    drawn victims changed and one decided victim per row is now undecided
    (-2 job 1). The `multi_misattribution_probe` rows stay all job 2.
    118 -> 120 graded, all 120 pass, still no misses.

    2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines. (120, 120.0)
    -> (102, 102.0): every graded job-1 workload passes, still no misses."""
    exam, results = _exam()
    scores = [s for r in results for s in r["job1_scores"]]
    # 2026-09-26 (faithful prompts): oversized's contradiction row left
    # job 1. 157 -> 156; passes stay 138.
    # 2026-09-26 (faithful prompts): see the docstring. (156, 138.0) ->
    # (118, 101.0).
    # 2026-09-26 (faithful prompts): contradiction rows answer the rules'
    # cause. (118, 101.0) -> (118, 118.0)
    # 2026-09-26 (faithful prompts): five workers moved two shared-origin
    # stories' draws; see the docstring. (118, 118.0) -> (120, 120.0)
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was (120,
    # 120.0).
    assert (len(scores), sum(scores)) == (102, 102.0)
    misses = [e.case for e, r in zip(exam, results)
             if sum(r["job1_scores"]) < len(r["job1_scores"])]
    # 2026-09-26 (faithful prompts): same reason. 19 -> 18.
    # 2026-09-26 (faithful prompts): node-cordon-diskfull's row left job 1
    # too. 18 -> 17.
    # 2026-09-26 (faithful prompts): contradiction rows pass. 17 -> 0
    assert misses == []
    contradiction = [s for e, r in zip(exam, results) if e.case == "contradiction_probe"
                     for s in r["job1_scores"]]
    assert contradiction == [1.0] * 17


def test_exam_oracle_job3_is_perfect():
    """spec section 10 gate 2's other half, and a stop condition: if the
    exam's own job3, oracle-read, were not 1.0 after the label-driven
    summary, the gold summaries would be wrong and re-pinning
    `FROZEN_SLICE_SHA256` / `EVAL_SET_SHA256` over them would bank the error.
    It reads 1.0 -- 5 of 5 `shared`-labeled rows (the three origin-object
    stories' `shared_origin_probe` halves) and 34 of 34 `none`-labeled
    rows.

    2026-09-26 (faithful prompts): the new `pvc-unbound-unschedulable`
    entry adds one `multi_misattribution_probe` row, labeled `none`. 39 ->
    40 rows, `none` 34 -> 35. Still 1.0.

    2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines. The exam has
    40 job-3 rows: 7 `shared` and 33 `none`, was 5 and 35. Still 1.0."""
    _, results = _exam()
    board = score.scoreboard(list(results))
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 40
    # rows: shared 5, none 35.
    assert board["jobs"]["job3"] == {
        "rate": 1.0, "n": 40,
        "by_label": {"shared": {"rate": 1.0, "n": 7},
                     "separate": {"rate": None, "n": 0},
                     "none": {"rate": 1.0, "n": 33}}}


def test_exam_oracle_job2_is_perfect():
    """The exam's own job2, oracle-read: a model that answers each row with
    that row's gold content must score every job-2 workload.

    This is the gate whose absence hid the defect. job1 and job3 have had an
    exam oracle since the rescope; job 2 -- the one job with a broken ceiling
    -- was the one nobody pinned, and 20 of its 153 workloads scored 0.0
    against their own gold answer because their grading keywords were empty.
    A ceiling below 1.0 here means the corpus, not the model, is at fault.

    Re-measured 2026-09-24 (job-2 generator fix: the exam's `none_of_these`
    slice is 8 thin-evidence rows, not 19) -- 153 to 142. Still perfect.

    2026-09-26 (faithful prompts): the `oversized` `contradiction_probe`
    row is now undecided (its node decoy is ruled out), so it joined job 2
    -- 142 to 143. Still perfect.

    2026-09-26 (faithful prompts): job-1 rows are built on the gather.
    31 corpus rows the rules do not decide became `own_cause` rows (+31).
    The new `pvc-unbound-unschedulable` entry adds its `own_cause`,
    `empty_candidates`, `wrong_attribution` and `misattribution_probe`
    rows and one two-workload `multi_misattribution_probe` row (+6).
    `node-cordon-diskfull`'s `contradiction_probe` row is now undecided
    (+1). 143 -> 181. Still perfect.

    2026-09-26 (faithful prompts): `contradiction_probe` is built only for
    the entries the rules decide, so the two undecided rows
    (`node-cordon-diskfull` and `oversized-job-unschedulable`) are gone.
    181 -> 179. Still perfect.

    2026-09-26 (faithful prompts): the same two shared-origin stories that
    moved job 1 (see `test_exam_oracle_job1_is_perfect`): four victims
    left job 2 and two joined it. The `multi_misattribution_probe` rows are
    built on the gather and keep their 40 job-2 workloads. 179 -> 177.
    Still perfect.

    2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines. 177 -> 197.
    Still perfect.
    """
    _, results = _exam()
    board = score.scoreboard(list(results))
    # 2026-09-26 (faithful prompts): see the docstring. 179 -> 177.
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 177.
    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 197}
