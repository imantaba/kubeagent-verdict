"""The job-2 answer keys: required words and must-not words (Spec 4a).

A named-cause job-2 answer scores 1 when its cleaned cause holds every
required word and no must-not word. Seven catalog entries change: five
gain must-not words, and the two init bad-tag entries gain `init`. These
tests pin that table, the meta it reaches in a build, and what it does to
the exam. 2026-10-04 (Spec 4b-2): the required words now live on the
entry's answer kit (`e.answer.keys`). See
docs/superpowers/specs/2026-09-29-grader-guard-design.md, sections 5 and 7.
"""

from __future__ import annotations

import dataclasses
import json
import random

import pytest

from kubeagent_verdict.dataset import cases, catalog, generate, gold, stories
from kubeagent_verdict.evals import score

# Written out here, not imported, so a change to the constant fails.
INIT = ("init container", "init-container", "initcontainer")
# Written out here, not imported, so a change to the constant fails.
REGISTRY_FAULT = ("unreachable", "refused", "timed out", "timeout", "unauthorized",
                  "authentication", "rate limit", "dial tcp", "no such host")

# The seven entries that change: (required words, must-not words).
CHANGED = {
    "memory-limit-oomkill": (("memory", "limit"), INIT),
    # 2026-10-05 (exam rebuild, item 4): was INIT alone.
    "deployment-bad-image-tag": (("image", "registry"), (*INIT, *REGISTRY_FAULT)),
    # 2026-10-05 (exam rebuild, item 3): a liveness answer is not this readiness cause.
    "networkpolicy-deny-all": (("network", "policy"), ("liveness",)),
    "container-start-error": (("container", "image"), (*INIT, "tag")),
    "init-errimagepull": (("init", "registry", "tag"), ()),
    # 2026-10-04 (Spec 4b-2): was ("init", "tag", "registry").
    "init-imagepullbackoff": (("init", "pull"), ()),
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


def test_the_changed_entries_carry_the_spec_table():
    """2026-10-05 (exam rebuild): renamed from `test_the_seven_changed_entries_carry_the_spec_table`;
    eight entries now."""
    for key, (required, must_not) in CHANGED.items():
        e = _entry(key)
        assert (e.answer.keys, e.own_cause_must_not) == (required, must_not), key


def test_registry_fault_is_the_spec_tuple():
    assert catalog.REGISTRY_FAULT == REGISTRY_FAULT


def test_a_registry_fault_answer_scores_0_on_the_bad_tag_workloads(exam_rows):
    """The new probe (spec, "Numbers to record"). Before item 4 these
    answers passed the key ("image", "registry")."""
    hit = 0
    for row in exam_rows:
        for name, wm in row["meta"]["workloads"].items():
            if wm["expected_cause"] != "the image tag does not exist in the registry":
                continue
            kw, must_not = wm["own_cause_keywords"], wm["own_cause_must_not"]
            for cause in ("the image registry is unreachable",
                          "pulling the image from the registry timed out",
                          "the registry returned unauthorized for the image"):
                assert score.job2(wm, {"cause": cause}, kw, workload=name,
                                  own_cause_must_not=must_not) == 0.0
            assert score.job2(wm, {"cause": "the registry is not unreachable; the image tag is wrong"},
                              kw, workload=name, own_cause_must_not=must_not) == 1.0
            hit += 1
    assert hit > 0


def test_every_other_entry_has_no_must_not_words():
    assert [e.key for e in catalog.all_entries()
            if e.key not in CHANGED and e.own_cause_must_not] == []


@pytest.mark.parametrize("spelling", INIT)
def test_each_init_spelling_trips_the_main_container_memory_key(spelling):
    e = _entry("memory-limit-oomkill")
    cause = f"the {spelling}'s memory limit is too small"
    assert not score._keywords_match(cause, e.answer.keys, e.own_cause_must_not)


@pytest.mark.parametrize("cause", [
    "the memory limit is too small for the initial heap size",
    "the memory limit is too small to initialize the cache",
])
def test_initial_and_initialize_do_not_trip_it(cause):
    e = _entry("memory-limit-oomkill")
    assert score._keywords_match(cause, e.answer.keys, e.own_cause_must_not)


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
        if e.answer:
            by_keywords.setdefault(e.answer.keys, set()).add(e.own_cause_must_not)
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
                own = gold.own_lines(row["messages"][1]["content"], [name])[name]
                init_victim = any("init:" in ln for ln in own)  # own_lines are lowercased
                got = wm["own_cause_must_not"]
                if not kw:
                    assert got == [], (row["meta"]["case"], name)
                elif init_victim:
                    assert not set(INIT) & set(got), (row["meta"]["case"], name)
                else:
                    assert got[-len(INIT):] == list(INIT), (row["meta"]["case"], name)
                story_keyed += bool(want)
                non_empty += bool(got)
                continue
            assert wm["own_cause_must_not"] == want, (row["meta"]["case"], name)
            non_empty += bool(wm["own_cause_must_not"])
    # 2026-10-04 (Spec 4b-1, Ruling 47): the shared-origin workloads whose key equals an entry's
    # that carries a must-not list, and which carry none themselves.
    assert story_keyed == 83
    # 2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real
    # lines; was (13677, 1084).
    # 2026-10-05 (Spec 4b-3): multi rows lose the healthy-origin read; was (13946, 1084).
    # 2026-10-05 (exam rebuild): was (13946, 1085). The +3978 non-empty lists are story
    # victims and other workloads that now carry "init container" (Task 3): 1750 shared_origin
    # and 2053 shared_origin_decoy rows, plus 175 in the own_cause, multi, empty_candidates and
    # wrong_attribution cases.
    assert (total, non_empty) == (13946, 5063)


def test_every_pool_gold_passes_its_own_key_with_must_not(pool_rows):
    """A gold answer the key refuses would teach a model an answer the
    grader then marks wrong. Measured 2026-09-29: 3,694 keyword-graded
    job-2 golds, and every one passes.

    2026-10-04 (Spec 4b-1): the shared-origin rows of the training pool were rebuilt on real lines.
    7976 keyword-graded job-2 golds now (was 3694), and every one passes.

    2026-10-04 (Spec 4b-2): 7972 now (was 7976): the 4 gated coredns multi rows in the pool lose
    their named job-2 workload, and every one passes."""
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
    # 2026-10-04 (Spec 4b-2): the 4 gated coredns multi rows lose their keys; was 7976.
    # 2026-10-05 (Spec 4b-3): multi rows lose the healthy-origin read; was 7972.
    assert checked == 7979


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
    # 2026-10-05 (exam rebuild): was (2, False) 140 and (2, True) 57. 30 job-2 workloads gain a
    # must-not list (Task 3): 24 in the shared_origin_probe and shared_origin_decoy_probe rows,
    # 6 in other cases.
    assert counts == {(1, False): 102, (2, False): 110, (2, True): 87}


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
# 2026-10-04 (Spec 4b-2): the catalog gold rests on anchors in own lines. The network-policy entry's
# gold is now "a default-deny network policy blocks the probe's traffic to the pod", and the
# disk-pressure and node-and-pod answers moved off the list: 3 pairs, was 9. Regenerated with the
# test's own formula.
# Every ordered pair of exam answer keys (A, B), with different gold
# sentences, where B's gold passes A's key: (A's cause, A's keywords, B's
# cause, B's keywords). All 3 are left for Spec 4b-4 (the Spec 4b-1 design,
# "Left for 4b-2, 4b-3 and 4b-4"). 4b-4 must shrink this list. A change that grows
# it fails here.
# 2026-10-05 (exam rebuild, items 3 and 5): 1 pair, was 3. The liveness
# victim's gold now trips the catalog key's must-not word "liveness", and the
# coredns readiness key's must-not word "containerd" refuses the corefile
# entry's gold. The pair left is the same cause in two wordings: both golds
# say a default-deny NetworkPolicy is behind a failing readiness probe, so
# passing it is right.
WEAK_PAIRS = [
    ("a default-deny network policy blocks the probe's traffic to the pod", ('network', 'policy'),
     'its pods are selected by the NetworkPolicy default-deny, a possible cause of its failing readiness probe', ('readiness', 'policy')),
]


def _exam_keys(exam_rows):
    keys = set()
    for row in exam_rows:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    return keys


def test_the_exam_has_34_keys(exam_rows):
    """Before 4a the exam had 34 weak pairs. The two init bad-tag entries
    share one gold sentence but have different word lists, so they are two
    keys.

    2026-10-04 (Spec 4b-1): the exam now has 34 keys, was 33.

    2026-10-05 (exam rebuild): split from the weak-pairs test, so the key
    count and the pairs fail apart."""
    assert len(_exam_keys(exam_rows)) == 34


def test_the_exam_has_exactly_the_1_weak_pair(exam_rows):
    """2026-10-04 (Spec 4b-1): 9 weak pairs, was 21. (Spec 4b-2): 3, was 9.

    2026-10-05 (exam rebuild): 1 pair, was 3. Renamed from
    `test_the_exam_has_34_keys_and_exactly_the_3_weak_pairs`."""
    keys = _exam_keys(exam_rows)
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
    `init`. Every other workload keeps it. 197 of 197 -> 185 of 197 (rate 0.9391)."""
    # 2026-10-04 (Spec 4b-2): init-imagepullbackoff's key is now `init`, `pull`; its old answer is
    # still "registry tag", which lacks both. Was ("init", "tag", "registry").
    old = {("init", "registry", "tag"): ["tag", "registry"],
           ("init", "pull"): ["registry", "tag"]}
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
    # 2026-10-04 (Spec 4b-2): init-imagepullbackoff's key changed to `init`, `pull`; the 12
    # workloads on the two keys still lose their point, so the rate is unchanged at 0.9391.
    assert board["jobs"]["job2"] == {"rate": 0.9391, "n": 197}


# ------------------------------------------------ story must-not words (items 2, 3, 5)

def test_a_story_answer_refuses_a_must_not_word_in_its_own_cause():
    with pytest.raises(ValueError, match="must-not"):
        stories.Answer(anchor="x", cause="containerd is slow", keys=("slow",),
                       rationale="r", must_not=("containerd",))


def test_a_story_must_not_word_is_lowercase_and_not_empty():
    for bad in (("",), ("Containerd",)):
        with pytest.raises(ValueError):
            stories.Answer(anchor="x", cause="the probe is slow", keys=("slow",),
                           rationale="r", must_not=bad)


def _answers(cause: str) -> list[stories.Answer]:
    """Every story Answer with this cause, found by text, so a reorder of
    the story list cannot point a test at the wrong answer."""
    out = []
    for st in stories.by_key().values():
        for v in st.victims:
            out += [a for a in (v.broken, v.healthy) if a is not None and a.cause == cause]
    return out


def test_the_coredns_readiness_answer_refuses_containerd():
    """Item 5: this key ("deadline", "exceeded") passed the corefile entry's
    gold, which names containerd."""
    got = _answers("its readiness probe exceeded its deadline on a slow dependency")
    assert got and {a.must_not for a in got} == {("containerd",)}


def test_the_disk_pressure_cse_keys_name_the_origin():
    """Item 2: ("containerd", "task") named no origin."""
    got = _answers("its container cannot start because containerd failed to create its "
                   "task, with no space left on the device")
    assert got and {a.keys for a in got} == {("space", "containerd")}


def test_a_story_gold_holding_its_own_must_not_word_fails_the_build():
    """Review Focus 1: a gold that names one of its own must-not words is
    refused at build time, not shipped for the grader to mark wrong.
    Answer.__post_init__ cannot see this: gold adds INIT_CONTAINER later,
    for every victim that is not an init victim."""
    word = catalog.INIT_CONTAINER[0]

    def poison(a):
        return None if a is None else dataclasses.replace(a, cause=f"{a.cause} ({word})")

    st = stories.by_key()["coredns-down"]
    victims = tuple(v if v.status.startswith("Init:") or v.issue.startswith("Init:")
                    else dataclasses.replace(v, broken=poison(v.broken), healthy=poison(v.healthy))
                    for v in st.victims)
    st = dataclasses.replace(st, victims=victims)
    raised = 0
    for seed in range(10):
        try:
            cases.shared_origin(st, random.Random(seed))
        except ValueError as err:
            assert "must-not" in str(err), err
            raised += 1
    assert raised > 0


@pytest.mark.parametrize("spelling", ["init_container", "init\u2011container", "INIT  CONTAINER"])
def test_a_must_not_word_in_another_spelling_fails_the_build(spelling):
    """The grader folds "_" to a space and odd hyphens to "-" before it looks
    for a must-not word. The build check folds the same way, so a gold cannot
    slip past the build with "init_container" and then be marked wrong."""
    def poison(a):
        return None if a is None else dataclasses.replace(a, cause=f"{a.cause} ({spelling})")

    st = stories.by_key()["coredns-down"]
    victims = tuple(v if v.status.startswith("Init:") or v.issue.startswith("Init:")
                    else dataclasses.replace(v, broken=poison(v.broken), healthy=poison(v.healthy))
                    for v in st.victims)
    st = dataclasses.replace(st, victims=victims)
    raised = 0
    for seed in range(10):
        try:
            cases.shared_origin(st, random.Random(seed))
        except ValueError as err:
            assert "must-not" in str(err), err
            raised += 1
    assert raised > 0


# 2026-10-05 (exam rebuild): measured on this build; was (208, 178) on main
# (re-measured on main c23dab3: also (208, 178)). The key count did not move;
# 16 pairs went away: 11 init container, 1 liveness, 2 containerd, 1 auth, 1 retired key
# (see contract/PIN.md, exam rebuild).
POOL_KEYS, POOL_PAIRS = 208, 162


def test_the_pool_weak_pair_count_does_not_grow(pool_rows, exam_rows):
    """Spec item 5: most pool pairs are benign (the same cause in other
    words, init vs main container, two NetworkPolicy names), so they are not
    swept. This pins their number so it cannot grow unnoticed. 178 before
    the rebuild (208 keys)."""
    keys = set()
    for row in pool_rows + exam_rows:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    pairs = {(a, ka, b) for a, ka, ma in keys for b, _, _ in keys
             if a != b and score._keywords_match(b, ka, ma)}
    assert (len(keys), len(pairs)) == (POOL_KEYS, POOL_PAIRS)
