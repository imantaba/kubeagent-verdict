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


@functools.lru_cache(maxsize=1)
def _exam() -> tuple[list, tuple[dict, ...]]:
    exam = generate.test_set()
    return exam, tuple(_gold_results(exam))


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
    """The exact number spec section 1 cites for the `multi` fix alone:
    every decided `multi` workload passes job1, 996 of 996 in train and
    121 of 121 in val."""
    def multi_job1(results):
        scores = [s for r in results if r["case"] == "multi" for s in r["job1_scores"]]
        return sum(scores), len(scores)

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
