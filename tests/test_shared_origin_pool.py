import random

import pytest

from kubeagent_verdict.dataset import cases, generate, gold, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score


def full_marks_misses(examples) -> list[str]:
    """Every row whose own gold, read back as the model's reply, loses a
    mark: contract, a decoy named, or any job-1, job-2 or job-3 score
    below 1.0. G2 and G3b gate the job-2 scores, so they are covered."""
    rows = [generate.to_row(e) for e in examples]
    gold_iter = iter(r["messages"][2]["content"] for r in rows)
    results = score.evaluate(rows, lambda _messages: next(gold_iter), grade_job2=True)
    misses = []
    for e, r in zip(examples, results):
        bad = [name for name, ok in (
            ("contract", r["contract_ok"]),
            ("decoy", not r["named_decoy"]),
            ("job1", all(s == 1.0 for s in r["job1_scores"])),
            ("job2", all(s == 1.0 for s in r["job2_scores"])),
            ("job3", r["job3"] in (None, 1.0))) if not ok]
        if bad:
            misses.append(f"{e.case} {e.group}: {bad}")
    return misses


@pytest.mark.parametrize("key", ["node-not-ready", "coredns-down", "networkpolicy-deny-all"])
def test_gold_scores_full_marks(key):
    st = stories.by_key()[key]
    exs = [cases.shared_origin(st, random.Random(3)),
           cases.shared_origin_decoy(st, random.Random(3))]
    assert full_marks_misses(exs) == []


def test_a_wrong_answer_loses_marks():
    """The check can fail: the healthy twin's gold, sent as the broken
    twin's reply, must lose a mark."""
    st = stories.by_key()["node-not-ready"]
    broken = cases.shared_origin(st, random.Random(3))
    healthy = cases.shared_origin_decoy(st, random.Random(3))
    row = generate.to_row(broken)
    [r] = score.evaluate([row], lambda _m: healthy.assistant, grade_job2=True)
    assert not (all(s == 1.0 for s in r["job1_scores"] + r["job2_scores"])
                and r["job3"] in (None, 1.0))


def test_generate_builds_the_family_from_stories():
    """Training draws only trainable stories, the exam only the six exam
    stories, and no family row carries an origin read label."""
    by = stories.by_key()
    train = [e for e in generate.generate(17, 200) if e.case.startswith("shared_origin")]
    exam = [e for e in generate.test_set() if e.case.startswith("shared_origin")]
    assert train and len(exam) == 20
    for e in train + exam:
        assert e.meta["origin"] in by
        assert "origin_read_label" not in e.meta
    assert {e.meta["origin"] for e in exam} == {st.key for st in stories.exam()}
    assert not {e.meta["origin"] for e in train} & set(stories.EXAM_KEYS)


def test_decoys_are_the_causes_the_rules_threw_out():
    """The meta's decoy list for a workload is gold.excluded_causes(row):
    ruled-out candidates plus refuted decisions. The two do not line up
    one-to-one with the candidates (rules.decide skips ruled-out ones), so
    the list is not built by zipping decisions with candidates."""
    seen_nonempty = 0
    for st in stories.trainable():
        for world in ("broken", "healthy"):
            d = so.draw(st, random.Random(5), width=len(st.victims))
            built = so.build(st, d, world=world)
            ex = cases._shared_origin_example("shared_origin", built)
            for row in built.rows:
                want = gold.excluded_causes(row)
                assert ex.meta["decoy_by_workload"][row.key] == want, (st.key, world, row.key)
                seen_nonempty += bool(want)
    assert seen_nonempty > 0
