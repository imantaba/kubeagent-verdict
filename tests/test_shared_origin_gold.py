import dataclasses
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, gold, render, rules, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score

PILOTS = ("node-not-ready", "coredns-down", "networkpolicy-deny-all")


def _built(key, world, width=None, **kw):
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(11), width=width or len(st.victims))
    return so.build(st, d, world=world, **kw)


@pytest.mark.parametrize("key", PILOTS)
@pytest.mark.parametrize("world", ["broken", "healthy"])
def test_own_lines_equal_the_graders(key, world):
    b = _built(key, world)
    keys = [r.key for r in b.rows]
    assert gold.own_lines(b.user, keys) == score._own_blocks(b.user, keys)


def test_decided_rows_take_the_rules_cause():
    b = _built("node-not-ready", "broken")
    g = gold.gold_for(b)
    for r in b.rows:
        rg = g.rows[r.key]
        assert rg.verdict == "decided" and rg.confidence == "high"
        assert rg.cause == r.result.cause
        assert rg.rationale == render.rule_rationale(r.result)
    assert g.label == "shared"


def test_rule_rationale_moved_to_render():
    assert cases._rule_rationale is render.rule_rationale


def test_decided_gold_passes_job1():
    for kw in ({}, {"unverified": True}):
        b = _built("node-not-ready", "broken", **kw)
        g = gold.gold_for(b)
        for r in b.rows:
            rg = g.rows[r.key]
            wm = {"decided_cause": r.result.cause, "decided_outcome": r.result.outcome,
                  "decided_evidence": r.result.evidence}
            assert score.job1(wm, {"cause": rg.cause, "rationale": rg.rationale}) == 1.0


def test_unverified_twin_is_decided_and_labelled_none():
    # Ruling 31: a refused node read decides every row (job 1) but confirms
    # nothing, so rules.shared is () and the label is "none".
    g = gold.gold_for(_built("node-not-ready", "broken", unverified=True))
    assert g.label == "none"
    assert all(rg.verdict == "decided" for rg in g.rows.values())
    assert g.summary.startswith(f"{g.n} workloads are failing, and kubeagent's rules did not ")


def test_named_needs_its_anchor_and_none_otherwise():
    g = gold.gold_for(_built("coredns-down", "broken"))
    verdicts = sorted(rg.verdict for rg in g.rows.values())
    assert verdicts.count("named") == 4          # 3 victims + the coredns origin row
    h = gold.gold_for(_built("node-not-ready", "healthy"))
    for rg in h.rows.values():
        assert rg.verdict == "none_of_these" and rg.confidence == "low" and rg.keys == ()
        assert rg.rationale.endswith("; none of its own lines says why.")


def test_labels_per_world_and_width():
    assert gold.gold_for(_built("coredns-down", "broken")).label == "shared"
    assert gold.gold_for(_built("coredns-down", "broken", width=2)).label == "none"
    assert gold.gold_for(_built("coredns-down", "healthy")).label == "none"
    assert gold.gold_for(_built("networkpolicy-deny-all", "broken")).label == "shared"
    assert gold.gold_for(_built("networkpolicy-deny-all", "healthy")).label == "none"


def test_rules_separate_maps_to_none():
    lines = ("no shared cause among the 2 workloads confirmed by rules",)
    assert rules.label(lines) == "separate"
    assert gold.label_for(lines, linked=0, cls="R", world="broken") == "none"


def test_cross_world_keys_do_not_overlap():
    for key in PILOTS:
        b = gold.gold_for(_built(key, "broken"))
        h = gold.gold_for(_built(key, "healthy"))
        for k in set(b.rows) & set(h.rows):
            assert not set(b.rows[k].keys) & set(h.rows[k].keys), k


def test_planted_key_in_an_excluded_line_is_refused():
    with pytest.raises(ValueError, match="only in excluded lines"):
        gold.check_keys(("deny",), anchors=["probe failed"], own=["probe failed", "policy deny"])


def test_excluded_causes_skips_the_non_excluded_and_does_not_zip():
    # rules.decide skips a ruled-out candidate, so decisions is shorter than
    # candidates and the two do not line up by position. The ruled-out
    # candidate comes first here: a zip would pair its position with the
    # refuted decision and miss the refuted cause.
    base = _built("node-not-ready", "broken").rows[0]
    cands = (
        c.Candidate("node worker-1 (NotReady)", "ruled_out", "taint matches"),
        c.Candidate("node worker-2 (NotReady)", "attributed", "first"),
        c.Candidate("node worker-3 (NotReady)", "attributed", "second"),
    )
    decisions = (
        rules.Decision("node worker-2 (NotReady)", "refuted", "node is Ready"),
        rules.Decision("node worker-3 (NotReady)", "confirmed", "node is NotReady"),
    )
    row = base._replace(candidates=cands,
                        result=dataclasses.replace(base.result, decisions=decisions))
    got = gold.excluded_causes(row)
    assert sorted(got) == ["node worker-1 (NotReady)", "node worker-2 (NotReady)"]
    assert "node worker-3 (NotReady)" not in got


def test_anchor_lines_drop_lines_naming_an_excluded_cause():
    base = _built("node-not-ready", "broken").rows[0]
    cands = (c.Candidate("node worker-1 (NotReady)", "ruled_out", "taint matches"),
             c.Candidate("node worker-2 (NotReady)", "attributed", "kept"))
    decisions = (rules.Decision("node worker-2 (NotReady)", "refuted", "ready"),)
    row = base._replace(candidates=cands,
                        result=dataclasses.replace(base.result, decisions=decisions))
    own = ["- a/b (x): node worker-1 (notready)", "node worker-2 (notready) again",
           "node worker-3 (notready)"]
    assert gold.anchor_lines(own, row) == ["node worker-3 (notready)"]


def test_summaries():
    g = gold.gold_for(_built("networkpolicy-deny-all", "broken"))
    assert g.summary.startswith("2 workloads share one upstream cause: the NetworkPolicy ")
    assert "Root cause: " in g.summary
    h = gold.gold_for(_built("networkpolicy-deny-all", "healthy"))
    assert h.summary.startswith("2 workloads are failing, and kubeagent's rules did not "
                                "confirm one cause on two or more of them.\n")
    assert h.summary.count(": its own lines do not show why.") == 2


def test_summary_is_one_to_four_lines():
    for key in PILOTS:
        for world in ("broken", "healthy"):
            lines = gold.gold_for(_built(key, world)).summary.split("\n")
            assert 1 <= len(lines) <= 4 and all(ln.strip() for ln in lines), (key, world)


def test_separate_reasons_only_when_every_healthy_row_has_its_own_cause():
    b = _built("coredns-down", "healthy")
    rows = {r.key: gold.RowGold("named", f"cause {i}", "high", ("x",), "r", False)
            for i, r in enumerate(b.rows)}
    n = len(rows)
    assert gold._summary(b, rows, "none", n).startswith(
        f"{n} workloads are failing for separate reasons.\n")
    same = {k: g._replace(cause="cause 0") for k, g in rows.items()}
    assert "separate reasons" not in gold._summary(b, same, "none", n)
    first = next(iter(rows))
    unnamed = {**rows, first: gold.RowGold("none_of_these", "", "low", (), "r", False)}
    assert "separate reasons" not in gold._summary(b, unnamed, "none", n)
    bb = _built("coredns-down", "broken", width=2)
    rows_b = {r.key: gold.RowGold("named", f"cause {i}", "high", ("x",), "r", False)
              for i, r in enumerate(bb.rows)}
    assert "separate reasons" not in gold._summary(bb, rows_b, "none", len(rows_b))


def test_refused_origin_read_keeps_shared_label():
    b = _built("coredns-down", "broken", origin_events_failed=so.ORIGIN_EVENTS_FORBIDDEN)
    assert "forbidden" in b.user
    assert gold.gold_for(b).label == "shared"


def test_budget_cut_victim_falls_back_to_none_of_these():
    cut_seen = False
    for budget in range(1, 9):
        b = _built("coredns-down", "broken", budget=budget)
        g = gold.gold_for(b)
        own = gold.own_lines(b.user, [r.key for r in b.rows])
        linked = 0
        for row in b.rows:
            if row.role != "victim" or row.text.broken is None:
                continue
            anchor = gold._norm_cause(so._sub(row.text.broken.anchor, row.names, b.draw))
            seen = any(anchor in line for line in gold.anchor_lines(own[row.key], row))
            if not seen:
                cut_seen = True
                assert g.rows[row.key].verdict == "none_of_these"
            elif row.text.broken.link:
                linked += 1
        confirmed = sum(1 for r in b.rows if g.rows[r.key].verdict == "decided")
        assert g.n == (max(linked, confirmed) if g.label == "shared" else len(b.rows))
        assert g.label == ("shared" if linked >= 2 else "none")
    assert cut_seen, "no budget in 1..8 cut a victim's anchor; the test proves nothing"


def test_a_key_that_sits_in_no_own_line_is_refused():
    # A typo in a story's keys used to pass: the key was in neither the
    # anchor lines nor the excluded ones, so nothing complained.
    with pytest.raises(ValueError, match="sits in no own line"):
        gold.check_keys(("lookups",), anchors=["dns failed"], own=["dns failed"])
