"""The job-2 answer keys: required words and must-not words (Spec 4a).

A named-cause job-2 answer scores 1 when its cleaned cause holds every
required word and no must-not word. Seven catalog entries change: five
gain must-not words, and the two init bad-tag entries gain `init`. These
tests pin that table, the meta it reaches in a build, and what it does to
the exam. See docs/superpowers/specs/2026-09-29-grader-guard-design.md,
sections 5 and 7.
"""

from __future__ import annotations

import json

import pytest

from kubeagent_verdict.dataset import catalog, generate
from kubeagent_verdict.evals import score

# Written out here, not imported, so a change to the constant fails.
INIT = ("init container", "init-container", "initcontainer")

# The seven entries that change: (required words, must-not words).
CHANGED = {
    "memory-limit-oomkill": (("memory", "limit"), INIT),
    "deployment-bad-image-tag": (("image", "registry"), INIT),
    "container-start-error": (("container", "image"), (*INIT, "tag")),
    "init-errimagepull": (("init", "registry", "tag"), ()),
    "init-imagepullbackoff": (("init", "tag", "registry"), ()),
    "oversized-job-unschedulable": (("memory", "node"), ("cordon", "pressure")),
    "volume-mount-error": (("volume", "pod"), ("provision",)),
}

MEMORY_REQUEST = "the pod's memory request is larger than any node can allocate"


def _entry(key: str) -> catalog.CatalogEntry:
    [e] = [e for e in catalog.all_entries() if e.key == key]
    return e


def _gold(row: dict) -> dict[str, str]:
    return {v["workload"]: v["cause"]
            for v in json.loads(row["messages"][2]["content"])["verdicts"]}


@pytest.fixture(scope="module")
def exam_rows() -> list[dict]:
    return [generate.to_row(ex) for ex in generate.test_set()]


@pytest.fixture(scope="module")
def pool_rows() -> list[dict]:
    """The 8,000-row pool the training build splits. About 1.4 s."""
    return [generate.to_row(ex) for ex in generate.generate(17, 8000)]


# ------------------------------------------------------------ the catalog


def test_init_container_is_the_three_spellings_and_never_bare_init():
    assert catalog.INIT_CONTAINER == INIT


def test_the_seven_changed_entries_carry_the_spec_table():
    for key, (required, must_not) in CHANGED.items():
        e = _entry(key)
        assert (e.own_cause_keywords, e.own_cause_must_not) == (required, must_not), key


def test_every_other_entry_has_no_must_not_words():
    assert [e.key for e in catalog.all_entries()
            if e.key not in CHANGED and e.own_cause_must_not] == []


@pytest.mark.parametrize("spelling", INIT)
def test_each_init_spelling_trips_the_main_container_memory_key(spelling):
    e = _entry("memory-limit-oomkill")
    cause = f"the {spelling}'s memory limit is too small"
    assert not score._keywords_match(cause, e.own_cause_keywords, e.own_cause_must_not)


@pytest.mark.parametrize("cause", [
    "the memory limit is too small for the initial heap size",
    "the memory limit is too small to initialize the cache",
])
def test_initial_and_initialize_do_not_trip_it(cause):
    e = _entry("memory-limit-oomkill")
    assert score._keywords_match(cause, e.own_cause_keywords, e.own_cause_must_not)


# ------------------------------------------------------------ the build


def test_every_pool_workload_carries_its_entrys_must_not_list(pool_rows):
    """Every workload's meta carries `own_cause_must_not`, a list. It is the
    must-not list of the catalog entry whose keywords the workload carries,
    and [] when no entry carries them: a decided workload, a
    `none_of_these` workload, or a shared-origin key from propagation.py.

    Measured 2026-09-29: 13,677 workloads, 1,084 with a non-empty list.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    The pool now holds 13946 workloads, 1084 with a non-empty list (was 13677 and 1084). A
    shared-origin key now comes from a story's answer, not from propagation.py, and still has an
    empty list.

    2026-10-04 (Spec 4b-1, Ruling 47): a story's key can equal a catalog entry's, and then the
    entry's must-not list is not the story's. Three stories carry ('memory', 'limit'), the key of
    the entry that carries the init-container must-not words. Their workloads carry [], so on a
    shared-origin row the expected list is [] whatever the catalog says. Exactly 83 pool workloads
    sit in that case (28 + 28 + 27), and the count is pinned below so the exception cannot widen.
    """
    by_keywords: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    for e in catalog.all_entries():
        if e.own_cause_keywords:
            by_keywords.setdefault(e.own_cause_keywords, set()).add(e.own_cause_must_not)
    # One list per keyword set, or a workload's list would be ambiguous.
    assert all(len(v) == 1 for v in by_keywords.values())

    total = non_empty = story_keyed = 0
    for row in pool_rows:
        shared_origin_row = row["meta"]["case"].startswith("shared_origin")
        for name, wm in row["meta"]["workloads"].items():
            total += 1
            kw = tuple(wm["own_cause_keywords"])
            want = list(next(iter(by_keywords[kw]))) if kw in by_keywords else []
            if shared_origin_row:
                # A story's key is its own, even when it equals an entry's.
                story_keyed += bool(want)
                want = []
            assert wm["own_cause_must_not"] == want, (row["meta"]["case"], name)
            non_empty += bool(wm["own_cause_must_not"])
    # 2026-10-04 (Spec 4b-1, Ruling 47): the shared-origin workloads whose key equals an entry's
    # that carries a must-not list, and which carry none themselves.
    assert story_keyed == 83
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was (13677, 1084).
    assert (total, non_empty) == (13946, 1084)


def test_every_pool_gold_passes_its_own_key_with_must_not(pool_rows):
    """A gold answer the key refuses would teach a model an answer the
    grader then marks wrong. Measured 2026-09-29: 3,694 keyword-graded
    job-2 golds, and every one passes.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    7976 keyword-graded job-2 golds now (was 3694), and every one passes."""
    checked = 0
    for row in pool_rows:
        gold = _gold(row)
        for name, wm in row["meta"]["workloads"].items():
            kw = wm["own_cause_keywords"]
            if wm["job"] != 2 or not score._is_job2_keyword_graded(wm, kw):
                continue
            checked += 1
            assert score._keywords_match(gold[name], kw, wm["own_cause_must_not"]), (
                row["meta"]["case"], name, gold[name])
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was 3694.
    assert checked == 7976


def test_only_exam_job2_workloads_carry_must_not_words(exam_rows):
    """57 of the exam's 177 job-2 workloads carry a must-not list, and no
    job-1 workload does: 30 on deployment-bad-image-tag's key, 9 on
    oversized-job-unschedulable's, and 6 each on memory-limit-oomkill's,
    container-start-error's and volume-mount-error's.

    2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines. The exam's
    job-2 workloads split 140 without a must-not list and 57 with one, and no job-1 workload carries
    one. No shared-origin workload carries one."""
    counts: dict[tuple[int, bool], int] = {}
    for row in exam_rows:
        for wm in row["meta"]["workloads"].values():
            k = (wm["job"], bool(wm["own_cause_must_not"]))
            counts[k] = counts.get(k, 0) + 1
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was (1,
    # False) 120, (2, False) 120, (2, True) 57.
    assert counts == {(1, False): 102, (2, False): 140, (2, True): 57}


# ------------------------------------------------------------ the exam

# 0920's causes on the exam's two memory-request workloads, 0-based rows
# 197 and 198, copied from out/eval/0920-exam0928/results.jsonl. Both are
# wrong, and both hold `memory` and `node`, so both scored 1 before 4a.
_0920_WRONG = {
    197: ("billing/frontend",
          ("the pod's node has a MemoryPressure condition and the pod requests "
           "a 32Mi resolution")),
    198: ("batch/notifier",
          ("the pod's node is cordoned and reporting Insufficient memory as a "
           "charge against its own memory limit")),
}


@pytest.mark.parametrize("index", sorted(_0920_WRONG))
def test_0920s_wrong_memory_request_answers_score_0(exam_rows, index):
    name, cause = _0920_WRONG[index]
    row = exam_rows[index]
    assert row["meta"]["case"] == "multi_misattribution_probe"
    wm = row["meta"]["workloads"][name]
    assert wm["expected_cause"] == MEMORY_REQUEST
    assert wm["own_cause_must_not"] == ["cordon", "pressure"]
    kw = wm["own_cause_keywords"]
    must_not = wm["own_cause_must_not"]
    # The keywords alone pass it: the must-not list is what zeroes it.
    assert score.job2(wm, {"cause": cause}, kw, workload=name,
                      own_cause_must_not=[]) == 1.0
    assert score.job2(wm, {"cause": cause}, kw, workload=name,
                      own_cause_must_not=must_not) == 0.0
    assert score.job2(wm, {"cause": _gold(row)[name]}, kw, workload=name,
                      own_cause_must_not=must_not) == 1.0


# 2026-10-04 (Spec 4b-1): the shared-origin exam rows were rebuilt on real lines. This list and its
# header were regenerated by the test below, with its own formula: 9 pairs, was 21. The group
# comments are generated too.
# Every ordered pair of exam answer keys (A, B), with different gold
# sentences, where B's gold passes A's key: (A's cause, A's keywords, B's
# cause, B's keywords). All 9 are left for Spec 4b-4 (the Spec 4b-1 design,
# "Left for 4b-2, 4b-3 and 4b-4"). 4b-4 must shrink this list. A change that grows
# it fails here.
WEAK_PAIRS = [
    # The key ('network', 'policy') of "a NetworkPolicy now blocks traffic to the pod's probe
    # port" also passes these other answers:
    ("a NetworkPolicy now blocks traffic to the pod's probe port", ('network', 'policy'),
     'its pods are selected by the NetworkPolicy default-deny, a possible cause of its failing liveness probe', ('liveness', 'policy')),
    ("a NetworkPolicy now blocks traffic to the pod's probe port", ('network', 'policy'),
     'its pods are selected by the NetworkPolicy default-deny, a possible cause of its failing readiness probe', ('readiness', 'policy')),
    # The key ('disk', 'pressure') of 'its pod is kept off one node by an untolerated
    # disk-pressure taint' also passes these other answers:
    ('its pod is kept off one node by an untolerated disk-pressure taint', ('disk', 'pressure'),
     "the pod's node is cordoned and reporting disk pressure", ('node', 'pod')),
    # The key ('deadline', 'exceeded') of 'its readiness probe exceeded its deadline on a slow
    # dependency' also passes these other answers:
    ('its readiness probe exceeded its deadline on a slow dependency', ('deadline', 'exceeded'),
     "containerd on the pod's node is not responding (context deadline exceeded)", ('containerd', 'deadline')),
    # The key ('node', 'pod') of "the pod's node is cordoned and reporting disk pressure" also
    # passes these other answers:
    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
     "containerd on the pod's node is not responding (context deadline exceeded)", ('containerd', 'deadline')),
    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
     'its pod is kept off one node by an untolerated disk-pressure taint', ('disk', 'pressure')),
    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
     'the PVC is still attached to the node the previous pod ran on', ('attached', 'node')),
    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
     "the PVC's underlying volume is unhealthy or unreachable on the pod's node", ('volume', 'pod')),
    ("the pod's node is cordoned and reporting disk pressure", ('node', 'pod'),
     MEMORY_REQUEST, ('memory', 'node')),
]


def test_the_exam_has_34_keys_and_exactly_the_9_weak_pairs(exam_rows):
    """Before 4a the exam had 34 weak pairs. The two init bad-tag entries
    share one gold sentence but have different word lists, so they are two
    keys.

    2026-10-04 (Spec 4b-1): Renamed from `test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs`:
    the exam now has 34 keys, was 33, and 9 weak pairs, was 21."""
    keys = set()
    for row in exam_rows:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 33.
    assert len(keys) == 34
    pairs = sorted({(cause_a, kw_a, cause_b, kw_b)
                    for cause_a, kw_a, must_not_a in keys
                    for cause_b, kw_b, _ in keys
                    if cause_b != cause_a
                    and score._keywords_match(cause_b, kw_a, must_not_a)})
    assert pairs == WEAK_PAIRS


def test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads(exam_rows):
    """The own-keyword bot, with the two init bad-tag entries answered from
    their old lists ("tag registry", "registry tag"). The exam's 12
    workloads on those two keys lose their point: the old answer lacks
    `init`. Every other workload keeps it. 177 of 177 -> 165 of 177."""
    old = {("init", "registry", "tag"): ["tag", "registry"],
           ("init", "tag", "registry"): ["registry", "tag"]}
    by_prompt = {r["messages"][1]["content"]: r for r in exam_rows}

    def chat_fn(messages: list[dict]) -> str:
        row = by_prompt[messages[1]["content"]]
        verdicts = []
        for name, wm in row["meta"]["workloads"].items():
            kws = wm["own_cause_keywords"]
            kws = old.get(tuple(kws), kws)
            verdicts.append({"workload": name,
                             "cause": " ".join(kws) if kws else "none_of_these",
                             "confidence": "high",
                             "rationale": "answers with its own expected keywords"})
        return json.dumps({"verdicts": verdicts,
                           "summary": "see the verdicts above for details"})

    board = score.scoreboard(score.evaluate(exam_rows, chat_fn))
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was
    # {"rate": 0.9322, "n": 177}.
    assert board["jobs"]["job2"] == {"rate": 0.9391, "n": 197}
