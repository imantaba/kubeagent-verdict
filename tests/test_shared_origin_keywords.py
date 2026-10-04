"""The exam's job-2 grading keywords, on the rebuilt shared-origin rows.

Job 2 grades a named cause by keywords. Three properties, and the second and
third are the ones that matter:

- COVERAGE: every named job-2 workload in the 20 shared-origin exam rows has
  one to three keywords. Every other workload (decided by the rules, or
  `none_of_these`) has none. A named workload with no keywords could score
  0.0 whatever the model answered. That is a defect in the data, not a
  failure of the model.
- SELF-CONTAINMENT: each keyword is a lowercase word of four letters or more
  and sits inside its own cause. A typo here would make the workload
  unanswerable.
- DISCRIMINATION: a keyword set must not match any other cause the same row
  asks about. Two legs. The sibling leg: a workload's keywords do not match
  a different cause on another workload in the same row. The twin leg: they do
  not match the same workload's answer in the other world, including
  `none_of_these`. A set that cannot tell the two worlds apart grades both
  worlds the same.
"""
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import generate
from kubeagent_verdict.evals import score

# 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 18.
EXAM_KEYWORDED = 24


@pytest.fixture(scope="module")
def probes():
    return generate.shared_origin_probes()


@pytest.fixture(scope="module")
def decoys():
    return generate.shared_origin_decoy_probes()


def _keyed(ex):
    """Yield (workload, cause, keywords) for each named job-2 workload."""
    for workload, m in ex.meta["workloads"].items():
        cause = m["expected_cause"]
        if m["job"] == 2 and cause != contract.NONE_OF_THESE:
            yield workload, cause, m["own_cause_keywords"]


def test_every_named_job2_workload_carries_one_to_three_keywords(probes, decoys):
    named = 0
    for ex in probes + decoys:
        for workload, m in ex.meta["workloads"].items():
            keys = m["own_cause_keywords"]
            if m["job"] == 2 and m["expected_cause"] != contract.NONE_OF_THESE:
                named += 1
                assert 1 <= len(keys) <= 3, (ex.group, workload, keys)
            else:
                assert keys == [], (ex.group, workload, keys)
    assert named > 0


def test_every_exam_keyword_appears_in_its_own_cause(probes, decoys):
    checked = 0
    for ex in probes + decoys:
        for workload, cause, keys in _keyed(ex):
            checked += 1
            for k in keys:
                assert re.fullmatch(r"[a-z]{4,}", k), (ex.group, workload, k)
                assert k in cause.lower(), (ex.group, workload, k, cause)
            assert score._keywords_match(cause, keys), (ex.group, workload)
    assert checked > 0


def test_every_exam_keyword_set_discriminates(probes, decoys):
    siblings = 0
    for ex in probes + decoys:
        named = list(_keyed(ex))
        for workload, cause, keys in named:
            for other, other_cause, _ in named:
                if other == workload or other_cause == cause:
                    continue
                siblings += 1
                assert not score._keywords_match(other_cause, keys), (
                    ex.group, workload, other)
    assert siblings > 0

    twins = 0
    for probe, decoy in zip(probes, decoys):
        for here, there in ((probe, decoy), (decoy, probe)):
            for workload, cause, keys in _keyed(here):
                other_cause = there.meta["expected"].get(workload)
                if other_cause is None or other_cause == cause:
                    continue
                twins += 1
                assert not score._keywords_match(other_cause, keys), (
                    here.group, workload, other_cause)
    assert twins > 0


def test_the_exam_keyword_count_is_pinned(probes, decoys):
    keyed = sum(len(list(_keyed(ex))) for ex in probes + decoys)
    # The pin guards the story data. A story edit that adds or drops a named
    # job-2 workload on the exam moves this number on purpose.
    assert keyed == EXAM_KEYWORDED
