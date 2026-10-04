"""The shared-origin family's decided rows and its label-driven summary.

A row the rules decide (job 1) takes its cause and rationale from the rules.
A row they do not decide (job 2) is `named` from its own lines, or it is
`none_of_these`. The label is `shared` or `none`. Nothing in this family is
ever labelled `separate`.

The summary follows the label. A `shared` row gets three lines: the count and
the origin, the root cause, and the remedy. A `none` row gets a header and then
one line per row, at most three. The header says "failing for separate
reasons" only in a healthy world where every row has its own, different cause
(a named cause or a rules-decided one). Anywhere else it says the rules did not
confirm one cause, because anything stronger would claim more than the rows show.
"""

from __future__ import annotations

import json
import random
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, generate, gold, render, stories
from kubeagent_verdict.dataset import shared_origin as so

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")
_ROW_LINE = re.compile(r"^[^\s:]+/[^\s:]+: ")


def _verdicts(ex) -> dict[str, dict]:
    return {v["workload"]: v for v in json.loads(ex.assistant)["verdicts"]}


def _summary(ex) -> str:
    return json.loads(ex.assistant)["summary"]


def _built(key, world, width=None, **kw):
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(11), width=width or len(st.victims))
    return so.build(st, d, world=world, **kw)


def _answers(st):
    """Every `Answer` a story can print: victims in both worlds, then origin rows."""
    for v in st.victims:
        for a in (v.broken, v.healthy):
            if a is not None:
                yield a
    for w in (st.broken, st.healthy):
        if w.origin_row is not None and w.origin_row.answer is not None:
            yield w.origin_row.answer


@pytest.fixture(scope="module")
def fam():
    """The exam probes, the exam decoy probes and the cousin probes."""
    rows = (generate.shared_origin_probes()
            + generate.shared_origin_decoy_probes()
            + generate.shared_origin_cousin_probes())
    narrow = sum(1 for st in stories.exam() if len(st.victims) >= 3)
    assert len(rows) == 2 * (len(stories.EXAM_KEYS) + narrow) + 2 * len(stories.trainable())
    return rows


# ------------------------------------------------------- decided rows


def test_a_confirmed_row_gets_the_rules_cause_and_rationale():
    b = _built("node-not-ready", "broken")
    g = gold.gold_for(b)
    victims = [r for r in b.rows if r.role == "victim"]
    assert victims
    for row in victims:
        res = row.result
        assert res.decided and res.outcome == "confirmed", row.key
        rg = g.rows[row.key]
        assert rg.verdict == "decided", row.key
        assert rg.cause == res.cause, row.key
        assert rg.rationale == render.rule_rationale(res), row.key
        assert rg.keys == (), row.key

    # The same draw, rendered as an example: the reply and the meta agree.
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_probe(st, random.Random(11))
    verdicts = _verdicts(ex)
    assert {r.key for r in victims} <= set(verdicts)
    for row in victims:
        assert verdicts[row.key]["cause"] == row.result.cause
        assert verdicts[row.key]["rationale"] == render.rule_rationale(row.result)
        m = ex.meta["workloads"][row.key]
        assert m["job"] == 1 and m["decided"], row.key
        assert m["decided_cause"] == row.result.cause, row.key
        assert m["decided_outcome"] == "confirmed", row.key
        assert m["own_cause_keywords"] == [], row.key


def test_an_unverified_row_is_decided_and_the_label_is_none():
    """A refused node read still decides (job 1, outcome "unverified"), but it
    confirms nothing, so the rules do not call the cause shared (Ruling 31)."""
    st = stories.by_key()["node-not-ready"]
    b = _built("node-not-ready", "broken", unverified=True)
    victims = [r for r in b.rows if r.role == "victim"]
    assert victims
    assert all(r.result.decided and r.result.outcome == "unverified" for r in victims)
    g = gold.gold_for(b)
    assert g.label == "none"
    header = (f"{len(b.rows)} workloads are failing, and kubeagent's rules did not "
              "confirm one cause on two or more of them.")
    assert g.summary.split("\n")[0] == header

    ex = cases.shared_origin(st, random.Random(11), unverified=True)
    assert ex.meta["label"] == "none"
    for row in victims:
        m = ex.meta["workloads"][row.key]
        assert m["job"] == 1 and m["decided_outcome"] == "unverified", row.key
    assert _summary(ex).split("\n")[0] == header

    # A story with no down node has nothing to refuse, so it cannot be unverified.
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(stories.by_key()["registry-unreachable"],
                            random.Random(11), unverified=True)


# ---------------------------------------------------------- summaries


def test_a_shared_summary_is_three_lines(fam):
    seen = 0
    for ex in fam:
        if ex.meta["label"] != "shared":
            continue
        seen += 1
        lines = _summary(ex).split("\n")
        assert len(lines) == 3, (ex.case, ex.group)
        assert _SHARED_HEAD.match(lines[0]), lines[0]
        assert lines[1].startswith("Root cause: "), lines[1]
        n = int(lines[0].split(" ", 1)[0])
        assert 2 <= n <= len(ex.meta["expected"]), (ex.group, n)
        assert lines[2].strip(), (ex.group, "empty remedy line")
    assert seen > 0


def test_a_healthy_summary_says_separate_reasons_only_when_the_rows_earn_it(fam):
    """Earned means: no row is `none_of_these`, and no two rows share a cause."""
    earned = unearned = 0
    for ex in fam:
        if ex.case != "shared_origin_decoy_probe":
            continue
        causes = list(ex.meta["expected"].values())
        n = len(causes)
        head = _summary(ex).split("\n")[0]
        if contract.NONE_OF_THESE not in causes and len(set(causes)) == n:
            earned += 1
            assert head == f"{n} workloads are failing for separate reasons.", ex.group
        else:
            unearned += 1
            assert head == (f"{n} workloads are failing, and kubeagent's rules did not "
                            "confirm one cause on two or more of them."), ex.group
    assert earned > 0 and unearned > 0, (earned, unearned)


def test_a_broken_none_summary_says_the_rules_did_not_confirm_one_cause(fam):
    seen = 0
    for ex in fam:
        if ex.case != "shared_origin_probe" or ex.meta["label"] != "none":
            continue
        seen += 1
        n = len(ex.meta["expected"])
        lines = _summary(ex).split("\n")
        assert lines[0] == (f"{n} workloads are failing, and kubeagent's rules did not "
                            "confirm one cause on two or more of them."), ex.group
        assert 3 <= len(lines) <= 4, (ex.group, len(lines))
        # Header, then one line per row. There is no remedy line on a `none` row.
        for ln in lines[1:]:
            assert _ROW_LINE.match(ln), (ex.group, ln)
    assert seen > 0


def test_the_family_never_carries_the_label_separate(fam):
    # Ruling 25: the rules' "separate" maps to "none". The word survives only
    # in a summary header, and only when a healthy world earns it.
    assert {ex.meta["label"] for ex in fam} == {"shared", "none"}


def test_a_summary_lists_at_most_three_rows(fam):
    for ex in fam:
        if ex.meta["label"] == "shared":
            continue
        n = len(ex.meta["expected"])
        assert len(_summary(ex).split("\n")) == 1 + min(3, n), ex.group

    # The loop above only reaches a fourth row if some example has one. Force
    # it: build every story in both worlds, and cap the ones with four rows.
    capped = 0
    for st in stories.by_key().values():
        for world in ("broken", "healthy"):
            b = _built(st.key, world)
            if len(b.rows) < 4:
                continue
            capped += 1
            g = gold.gold_for(b)
            lines = gold._summary(b, g.rows, "none", len(b.rows)).split("\n")
            assert len(lines) == 4, (st.key, world)
            assert [ln.split(":")[0] for ln in lines[1:]] == [r.key for r in b.rows[:3]]
    assert capped > 0


def test_no_story_answer_holds_a_shared_claim_phrase():
    """A cause with a shared-claim phrase would make job 3 read a `none` row's
    per-workload line as a claim and fail it. The shared summary is exempt: it
    carries the claim on purpose, and it is built from the story's shown text,
    not from an answer."""
    checked = 0
    for st in stories.by_key().values():
        for a in _answers(st):
            checked += 1
            low = a.cause.lower()
            for ph in cases.SHARED_CLAIM_PHRASES:
                assert ph not in low, (st.key, ph, a.cause)
    assert checked > 0


# ------------------------------------------------------------ labels


def test_a_shared_label_is_earned():
    """`shared` needs two confirmed rows, or (for a plain story) two linked
    victims. A healthy world is never `shared`. Every story at its narrowest
    and widest width, so the width rule is exercised too."""
    seen: set[str] = set()
    for st in stories.by_key().values():
        for width in sorted({2, len(st.victims)}):
            for world in ("broken", "healthy"):
                d = so.draw(st, random.Random(5), width=width)
                b = so.build(st, d, world=world)
                g = gold.gold_for(b)
                confirmed = sum(1 for r in b.rows if r.result.outcome == "confirmed")
                linked = sum(1 for r in b.rows
                             if r.role == "victim" and g.rows[r.key].linked)
                tag = (st.key, width, world)
                if world == "healthy":
                    assert g.label == "none", tag
                    seen.add("healthy-none")
                elif g.label == "shared":
                    assert confirmed >= 2 or (st.cls == "P" and linked >= 2), tag
                    seen.add("broken-shared")
                else:
                    if st.cls == "P":
                        assert linked < 2, tag
                    seen.add("broken-none")
    assert seen == {"healthy-none", "broken-shared", "broken-none"}


def test_every_r_story_is_shared_in_the_broken_world_at_every_width():
    """Task 5 checks full width. This checks the narrow width as well, because
    the wide probe and the training loop draw ruled stories at width 2."""
    checked = 0
    for st in stories.by_key().values():
        if st.cls != "R":
            continue
        for width in sorted({2, len(st.victims)}):
            d = so.draw(st, random.Random(5), width=width)
            broken = so.build(st, d, world="broken")
            healthy = so.build(st, d, world="healthy")
            tag = (st.key, width)
            assert gold.gold_for(broken).label == "shared", tag
            for r in broken.rows:
                if r.role == "victim":
                    assert r.result.decided and r.result.outcome == "confirmed", (tag, r.key)
            assert gold.gold_for(healthy).label == "none", tag
            assert not any(r.result.decided for r in healthy.rows), tag
            checked += 1
    assert checked >= sum(1 for st in stories.by_key().values() if st.cls == "R")


# 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
# was ['none', 'shared', 'shared', 'shared', 'none', 'none', 'none', 'shared', 'shared', 'none'].
EXAM_PROBE_LABELS = ["shared", "shared", "shared", "shared", "none",
                     "shared", "none", "shared", "shared", "none"]


def test_the_exam_probe_labels_are_pinned():
    """Six full-width probes in exam order, then the width-2 probes of the four
    exam stories with three or more victims. Pinned so a story edit that moves
    a label is a deliberate edit here, not a silent drift."""
    probes = generate.shared_origin_probes()
    decoys = generate.shared_origin_decoy_probes()
    full = [st.key for st in stories.exam()]
    narrow = [st.key for st in stories.exam() if len(st.victims) >= 3]
    assert [e.meta["origin"] for e in probes] == full + narrow
    assert [e.meta["label"] for e in probes] == EXAM_PROBE_LABELS
    assert {e.meta["label"] for e in decoys} == {"none"}
    by_key = stories.by_key()
    for e in probes:
        if by_key[e.meta["origin"]].cls == "R":
            assert e.meta["label"] == "shared", e.group


def test_a_decided_shared_origin_probe_workload_carries_the_rules_cause():
    """`node-not-ready`'s victims share one node, so every one decides against
    it and gets the identical rules' cause."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_probe(st, generate._entry_rng("t", st.key))
    causes = {v["cause"] for v in json.loads(ex.assistant)["verdicts"]}
    assert len(causes) == 1
    only = causes.pop()
    assert only.startswith("node ")
    assert ex.meta["scope_value"] in only
    d = so.draw(st, generate._entry_rng("t", st.key), width=len(st.victims))
    # The rules' own terse cause, not the story's shown sentence.
    assert only != so._sub(st.shown_cause, None, d)


# ------------------------------------------------------------ the job split


def test_the_job_split_follows_the_rules_decision(fam):
    decided = undecided = 0
    for ex in fam:
        expected = ex.meta["expected"]
        for name, m in ex.meta["workloads"].items():
            if m["decided"]:
                decided += 1
                assert m["job"] == 1, (ex.group, name)
                assert m["own_cause_keywords"] == [], (ex.group, name)
                assert m["decided_cause"] == expected[name], (ex.group, name)
                assert m["decided_outcome"] in ("confirmed", "unverified"), (ex.group, name)
            else:
                undecided += 1
                assert m["job"] == 2, (ex.group, name)
    assert decided > 0 and undecided > 0, (decided, undecided)
