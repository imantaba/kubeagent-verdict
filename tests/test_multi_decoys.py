"""Spec 4b-3: multi rows and decoys.

The build here is the out/dataset-MMDD pipeline: generate(17, 8000), split,
drop held-out. Tests that compare with an older build live in
tests/test_exam_rebuild_moves.py (2026-10-05).
"""
import dataclasses
import inspect
import json
import random
import re
from pathlib import Path

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import (
    cases,
    catalog,
    checker,
    gather,
    generate,
    gold,
    render,
)
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.evals import score

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "val", "test")
# 2026-10-05 (exam rebuild): the _needs_old helper and _old() went with their tests.


@pytest.fixture(scope="module")
def build() -> dict[str, list]:
    ex = generate.generate(17, 8000)
    tr, va = generate.split(ex, 17)
    te = generate.test_set()
    return {"train": generate.drop_held_out(tr, te),
            "val": generate.drop_held_out(va, te), "test": te}


def _all(build):
    return [e for split in SPLITS for e in build[split]]


_FALLBACK = ("4 workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them.")


# --- test 5: the summary rule ------------------------------------------------

def test_named_and_different_causes_are_separate():
    assert gold.separate_for("none", ["w", "x"])


def test_one_none_of_these_row_is_not_separate():
    assert not gold.separate_for("none", ["w", ""])


def test_two_rows_with_one_cause_are_not_separate():
    assert not gold.separate_for("none", ["w", "w"])


def test_a_separate_label_is_separate_even_with_a_none_row():
    assert gold.separate_for("separate", ["w", ""])


def test_four_rows_put_the_third_and_fourth_on_the_last_line():
    s = gold.summary_lines([("a/one", "w"), ("b/two", "x"), ("c/three", ""), ("d/four", "z")],
                           separate=False)
    assert s.split("\n") == [_FALLBACK, "a/one: w.", "b/two: x.",
                             "c/three: its own lines do not show why. d/four: z."]


@pytest.mark.parametrize("n", [2, 3])
def test_two_and_three_rows_get_one_line_each(n):
    rows = [(f"ns/w{i}", f"cause {i}") for i in range(n)]
    lines = gold.summary_lines(rows, separate=True).split("\n")
    assert lines[0] == f"{n} workloads are failing for separate reasons."
    assert lines[1:] == [f"ns/w{i}: cause {i}." for i in range(n)]


_SUMMARY_CASES = ("multi", "multi_misattribution_probe")


# --- test 6: every multi and probe summary -----------------------------------

def test_every_multi_and_probe_summary_names_every_workload_and_scores(build):
    seen = 0
    for e in _all(build):
        if e.case not in _SUMMARY_CASES:
            continue
        seen += 1
        doc = json.loads(e.assistant)
        s = doc["summary"]
        lines = s.split("\n")
        assert len(lines) <= c.MAX_SUMMARY_LINES, e.group
        assert all(len(ln) <= c.MAX_MODEL_LINE_RUNES for ln in lines), e.group
        for v in doc["verdicts"]:
            assert f"{v['workload']}: " in s, (e.group, v["workload"])
        assert score.job3(e.meta["label"], s) == 1.0, (e.group, e.meta["label"], s)
    assert seen == 758  # 738 multi + 20 multi_misattribution_probe


# 2026-10-05 (exam rebuild): replaced by tests/test_exam_rebuild_moves.py.
# (was test 7, test 8 and test 13: the three tests that read out/dataset-1004-4b2.)


# --- test 3: a multi decoy list is what the prompt rules out -----------------

def test_a_multi_decoy_list_is_what_the_prompt_rules_out(monkeypatch):
    last = {}
    real_gather, real_multi = gather.gather, cases.multi

    def spy_gather(*a, **kw):
        last["res"] = real_gather(*a, **kw)
        return last["res"]

    checked = 0

    def spy_multi(*a, **kw):
        nonlocal checked
        ex = real_multi(*a, **kw)
        res = last["res"]
        for key, cands, result in zip(ex.meta["expected"], res.candidates, res.results, strict=True):
            assert ex.meta["decoy_by_workload"][key] == gold.excluded_from(cands, result), key
            checked += 1
        return ex

    monkeypatch.setattr(gather, "gather", spy_gather)
    monkeypatch.setattr(cases, "multi", spy_multi)
    generate.generate(17, 800)
    assert checked > 100


# --- test 4: no workload lists its own gold as a decoy -----------------------

def test_no_workload_lists_its_own_gold_as_a_decoy(build):
    with_list = 0
    for e in _all(build):
        decoys = e.meta.get("decoy_by_workload") or {}
        for key, w in (e.meta.get("workloads") or {}).items():
            gold_cause = w.get("expected_cause") or ""
            listed = decoys.get(key) or []
            with_list += bool(listed)
            # none_of_these has no cause to find in a decoy list.
            if not gold_cause or gold_cause == c.NONE_OF_THESE:
                continue
            assert gold._norm_cause(gold_cause) not in {gold._norm_cause(d) for d in listed}, (
                e.case, e.group, key)
    assert with_list > 1000


# --- test 1: no healthy-origin read -----------------------------------------

def _labels(user: str) -> list[str]:
    section = user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]
    return re.findall(r"^== (.+) ==$", section, re.MULTILINE)


def test_multi_has_no_healthy_origin_read(build):
    assert "healthy_origin" not in inspect.signature(cases.multi).parameters
    seen = 0
    for e in _all(build):
        if e.case != "multi":
            continue
        seen += 1
        assert "origin_read_label" not in e.meta and "origin_healthy" not in e.meta, e.group
        assert _labels(e.user)[0].startswith("events "), e.group
    assert seen == 738


# --- test 10: the node fill --------------------------------------------------

_SCHED_ENTRIES = ("pvc-unbound-unschedulable", "node-cordon-diskfull", "oversized-job-unschedulable")


def _sched_texts(e) -> list[str]:
    return [e.evidence] + [ev[1] for ev in e.events]


def test_the_default_fill_gives_the_old_text():
    n = names_mod.draw(random.Random(5))
    assert n.nodes == 3
    by = {x.key: x for x in catalog.all_entries()}
    texts = [cases._fmt(t, n) for k in _SCHED_ENTRIES for t in _sched_texts(by[k])]
    joined = "\n".join(texts)
    assert "{" not in joined
    assert "0/3 nodes are available" in joined
    assert "3 Preemption is not helpful" in joined
    assert "3 Insufficient memory" in joined
    assert "1 node(s) were unschedulable, 2 node(s) had untolerated taint(s)" in joined


def test_five_nodes_fill_five():
    n = dataclasses.replace(names_mod.draw(random.Random(5)), nodes=5)
    by = {x.key: x for x in catalog.all_entries()}
    joined = "\n".join(cases._fmt(t, n) for k in _SCHED_ENTRIES for t in _sched_texts(by[k]))
    assert "0/3" not in joined
    assert "0/5 nodes are available" in joined
    assert "5 Preemption is not helpful" in joined
    assert "5 Insufficient memory" in joined
    assert "1 node(s) were unschedulable, 4 node(s) had untolerated taint(s)" in joined


# --- test 11: node_total is the header's T -----------------------------------

def test_node_total_is_the_headers_count(monkeypatch):
    real = render.cluster_health
    checked = 0

    def spy(workloads, reads):
        nonlocal checked
        block = real(workloads, reads)
        if block is not None:
            assert block.nodes_total == render.node_total(workloads, reads)
            checked += 1
        return block

    monkeypatch.setattr(render, "cluster_health", spy)
    generate.generate(17, 800)
    assert checked > 0


# --- test 12: IS-22 ----------------------------------------------------------

def test_is22_finds_nothing_on_the_build(build):
    inspected = 0
    for e in _all(build):
        rep = checker.check(e.system, e.user, e.assistant, e.meta)
        assert not [v for v in rep.violations if v.rule == "TXT-IS22"], (e.case, e.group)
        inspected += rep.inspected["TXT-IS22"]
    assert inspected > 0


def test_is22_passes_a_row_with_no_header():
    user = "Workload problems (P2):\n- a/b (Deployment): 0/1 ready\n  0/3 nodes are available"
    assert checker._txt_is22(checker._context("", user, "", None)) == (0, [])


# --- test 12b: every multi scheduler count is the header's -------------------

_HEADER = re.compile(r"— (\d+)/(\d+) nodes Ready\.")
_SCHED = re.compile(r"\b0/(\d+) nodes are available")


def test_every_multi_scheduler_count_is_the_headers(build):
    checked = 0
    for e in _all(build):
        if e.case != "multi":
            continue
        h = _HEADER.search(e.user)
        if not h:
            continue
        for m in _SCHED.finditer(e.user):
            checked += 1
            assert m.group(1) == h.group(2), e.group
    assert checked > 0


# --- the answer's node counts are the header's (fix round 1) -----------------

def test_a_rebuilt_rows_answer_counts_the_headers_nodes():
    rows = [e for e in generate.generate(17, 8000) if e.case == "multi"]
    checked = 0
    for e in rows:
        h = _HEADER.search(e.user)
        if not h or h.group(2) == "3" or "node-cordon-diskfull" not in e.group:
            continue
        total = int(h.group(2))
        a = e.assistant
        for m in re.finditer(r"(\d+) had taints", a):
            checked += 1
            assert int(m.group(1)) == total - 1, e.group
        for pat in (r"0/(\d+) nodes", r"(\d+) Insufficient", r"(\d+) Preemption"):
            for m in re.finditer(pat, a):
                assert int(m.group(1)) == total, e.group
    assert checked > 0


# --- the rebuild guard -------------------------------------------------------

def test_multi_refuses_a_node_count_that_moves_on_rebuild(monkeypatch):
    real = render.node_total
    seen = []

    def moving(workloads, reads):
        seen.append(1)
        return real(workloads, reads) + len(seen)

    monkeypatch.setattr(render, "node_total", moving)
    rng = random.Random(3)
    by = {x.key: x for x in catalog.all_entries()}
    while True:
        pairs = [(by["crashloop-pod"], names_mod.draw(rng)),
                 (by["node-cordon-diskfull"], names_mod.draw(rng))]
        if not cases.multi_clash([n for _e, n in pairs]):
            break
    with pytest.raises(RuntimeError, match="the node count moved from"):
        cases.multi(pairs, random.Random(4))
