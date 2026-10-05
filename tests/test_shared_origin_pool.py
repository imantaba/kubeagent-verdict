import json
import random
import re
from collections import Counter

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, checker, generate, gold, stories
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


# ---- Whole-family checks (Task 8): every family row the build and the
# probe sets make, at the runbook recipe.

BROKEN = ("shared_origin", "shared_origin_probe")
HEALTHY = ("shared_origin_decoy", "shared_origin_decoy_probe")
_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")


@pytest.fixture(scope="module")
def pairs():
    """Every family pair as (broken, healthy). The training loop and
    `_shared_origin_twin_pairs` append the broken half then its twin, and
    `split` and `drop_held_out` move a whole group at once, so adjacent
    family rows are twins. The exam's two probe lists walk the same stories
    in the same order, so they zip."""
    rows = generate.generate(17, 8000)
    train, val = generate.split(rows, seed=17)
    test = generate.test_set()
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    alternating = ([e for e in kept if e.case.startswith("shared_origin")]
                   + generate.shared_origin_wide_probes()
                   + generate.shared_origin_cousin_probes())
    assert len(alternating) % 2 == 0, len(alternating)
    out = (list(zip(alternating[::2], alternating[1::2]))
           + list(zip(generate.shared_origin_probes(),
                      generate.shared_origin_decoy_probes())))
    for a, b in out:
        assert a.case in BROKEN and b.case in HEALTHY, (a.case, b.case)
        assert a.group == b.group, (a.group, b.group)
    return out


@pytest.fixture(scope="module")
def family(pairs):
    return [e for pair in pairs for e in pair]


def test_every_family_gold_scores_full_marks(family):
    misses = full_marks_misses(family)
    assert misses == [], f"{len(misses)} rows lose a mark: {misses[:20]}"


def test_own_lines_equal_the_graders_on_every_row(family):
    """Ruling 7: the dataset's copy of the grader's own-lines rule agrees
    with the grader on every family row, not only on the pilots."""
    bad = []
    for e in family:
        ws = list(e.meta["workloads"])
        if gold.own_lines(e.user, ws) != score._own_blocks(e.user, ws):
            bad.append(f"{e.case} {e.group}")
    assert bad == [], f"{len(bad)} rows: {bad[:20]}"


def test_every_log_cause_is_one_kubeagent_prints(family):
    """A log read's body says `log cause: <one of logscan's ten causes>`."""
    bad = set()
    for e in family:
        for ln in e.user.splitlines():
            s = ln.strip()
            if (s.startswith(checker.LOG_CAUSE_PREFIX)
                    and s[len(checker.LOG_CAUSE_PREFIX):] not in checker.LOG_CAUSES):
                bad.add(s)
    assert not bad, sorted(bad)[:20]


def test_one_verdict_per_workload(family):
    """Every workload gets exactly one answer, and the answer is the one
    the meta expects."""
    for e in family:
        verdicts = json.loads(e.assistant)["verdicts"]
        names = [v["workload"] for v in verdicts]
        where = (e.case, e.group)
        assert len(names) == len(set(names)), (where, names)
        assert set(names) == set(e.meta["workloads"]) == set(e.meta["expected"]), where
        assert {v["workload"]: v["cause"] for v in verdicts} == e.meta["expected"], where


def test_label_and_summary_agree(family):
    """The label is "shared" or "none", the summary's first line claims a
    shared cause exactly when the label is "shared", and a healthy world is
    always "none"."""
    for e in family:
        label = e.meta["label"]
        first = json.loads(e.assistant)["summary"].split("\n")[0]
        where = (e.case, e.group, first)
        assert label in ("shared", "none"), (where, label)
        assert bool(_SHARED_HEAD.match(first)) == (label == "shared"), where
        if e.case in HEALTHY:
            assert label == "none", where


def test_each_answer_kind_carries_its_confidence_and_keys(family):
    """`none_of_these` is low with no keys; a decided workload (job 1) is
    high with no keys; a named job-2 workload has keys to grade on."""
    for e in family:
        for v in json.loads(e.assistant)["verdicts"]:
            wm = e.meta["workloads"][v["workload"]]
            where = (e.case, e.group, v["workload"], v["cause"])
            if v["cause"] == contract.NONE_OF_THESE:
                assert v["confidence"] == "low", where
                assert wm["own_cause_keywords"] == [], where
            elif wm["job"] == 1:
                assert v["confidence"] == "high", where
                assert wm["own_cause_keywords"] == [], where
            else:
                assert wm["job"] == 2 and wm["own_cause_keywords"], where


def test_ruled_broken_worlds_are_shared_unless_a_check_was_unverified(family):
    """Ruling 31: rules confirm the shared cause in a ruled story's broken
    world, except in the unverified twin, whose label is "none"."""
    by = stories.by_key()
    for e in family:
        if e.case not in BROKEN or by[e.meta["origin"]].cls != "R":
            continue
        unverified = any(wm["decided_outcome"] == "unverified"
                         for wm in e.meta["workloads"].values())
        assert e.meta["label"] == ("none" if unverified else "shared"), (e.case, e.group)


def test_named_keys_fail_the_other_world_and_every_decoy(pairs):
    """Ruling 39: a workload's keys must not also match its other world's
    answer or any decoy its own row shows. Otherwise a model scores by
    naming the wrong thing."""
    bad = []
    for a, b in pairs:
        for row, other in ((a, b), (b, a)):
            for w, wm in row.meta["workloads"].items():
                keys = wm["own_cause_keywords"]
                if not keys:
                    continue
                own = row.meta["expected"][w]
                assert score._keywords_match(own, keys, []), (row.case, row.group, w, keys)
                rivals = list(row.meta["decoy_by_workload"][w])
                theirs = other.meta["expected"].get(w)
                if theirs is not None and theirs != contract.NONE_OF_THESE:
                    rivals.append(theirs)
                bad += [f"{row.case} {row.group} {w}: {keys} match {cause!r}"
                        for cause in rivals if score._keywords_match(cause, keys, [])]
    assert bad == [], f"{len(bad)}: {bad[:20]}"


# Ruling 38. The spec's nine, plus the 23 rules that read at least one item
# of the old family (2026-10-03, 2420 rows of generate(17, 8000) +
# test_set(), 0 violations).
MUST_INSPECT = frozenset({
    "ANS-2", "D3", "E6", "E7", "E8", "E9", "B5", "B7", "TXT-IS15",
    "A1", "A2", "A3", "A4", "A5", "A6", "ANS-1", "B2", "B3", "B4", "B8",
    "C1", "C2-vocab", "C3", "C4-order", "D1", "F1", "F2", "F3", "TXT-IS8",
    "TXT-POD",
})
# Pinned from the 2026-10-03 build (Task 8 Step 5, after fix round 1). A rule
# moves between these two lists only with a dated comment saying why.
# TXT-IS14 inspects nothing: no family row prints a restart-loop finding
# whose evidence carries a restart count.
# 2026-10-05 (Spec 4b-3): TXT-IS22 joins INSPECTS: family rows with a header print
# a scheduler "0/N nodes are available" line.
INSPECTS = frozenset({
    "A1", "A2", "A3", "A4", "A5", "A6", "ANS-1", "ANS-2", "B1", "B2", "B3",
    "B4", "B5", "B6", "B7", "B8", "C1", "C1-cause", "C1-conf", "C2-reason",
    "C2-vocab", "C3", "C4-dedup", "C4-order", "C5/D4", "D1", "D1-onefresh",
    "D2-vocab", "D3", "E-min", "E1", "E10", "E2-order", "E3", "E4", "E5",
    "E6", "E7", "E8", "E9", "F1", "F2", "F3", "TXT-IS11", "TXT-IS15",
    "TXT-IS17", "TXT-IS22", "TXT-IS8", "TXT-IS9", "TXT-POD",
})
INSPECTS_NONE = frozenset({
    "TXT-IS14",
})


def test_no_rule_passes_by_looking_at_nothing(family):
    """Spec Tests section 2: every one of the 51 rules is on exactly one
    list, the "inspects" list is what the family really exercises, and the
    must-inspect rules are on it."""
    seen = Counter()
    for e in family:
        for rule, n in checker.check_row(generate.to_row(e)).inspected.items():
            seen[rule] += n
    assert INSPECTS | INSPECTS_NONE == set(checker.RULES)
    assert not INSPECTS & INSPECTS_NONE
    measured = {r for r in checker.RULES if seen[r] > 0}
    assert measured == INSPECTS, (
        f"now inspect: {sorted(measured - INSPECTS)}; "
        f"now inspect nothing: {sorted(INSPECTS - measured)}")
    assert MUST_INSPECT <= INSPECTS, sorted(MUST_INSPECT - INSPECTS)
