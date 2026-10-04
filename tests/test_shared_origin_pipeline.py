import dataclasses
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset import rules, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.dataset.checker import LOG_CAUSE_PREFIX, LOG_CAUSES


def _twins(key, seed=7, width=None, unverified=False):
    # The healthy twin has no down node, so it never takes `unverified` (Ruling 31).
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(seed), width=width or len(st.victims))
    return (so.build(st, d, world="broken", unverified=unverified),
            so.build(st, d, world="healthy"))


@pytest.mark.parametrize("key", ["node-not-ready", "coredns-down", "networkpolicy-deny-all"])
def test_twins_share_names_and_differ_in_a_line(key):
    b, h = _twins(key)
    assert [r.key for r in b.rows if r.role == "victim"] == \
           [r.key for r in h.rows if r.role == "victim"]
    assert b.group == h.group
    assert set(b.user.splitlines()) != set(h.user.splitlines())


def test_rows_are_in_report_order():
    b, _ = _twins("coredns-down")
    keys = [(r.workload.namespace, r.workload.name, r.workload.kind) for r in b.rows]
    assert keys == sorted(keys)


def test_down_node_is_confirmed_on_both_victims():
    b, h = _twins("node-not-ready")
    assert all(r.result.decided for r in b.rows)
    assert not any(r.result.decided for r in h.rows)
    assert b.health is not None and "NotReady" in b.user
    # The printed line carries both halves (contract.py:212), never a bare "— ".
    for r in b.rows:
        assert r.workload.decided_outcome == r.result.outcome != ""
        assert f"decided by rules: {r.result.cause} — {r.result.outcome}\n" in b.user


def test_unverified_twin_shows_the_refused_node_read():
    # A refused read still decides: rules.decide returns outcome "unverified"
    # (rules.py:325-330), which is job 1 but never counts toward rules.shared.
    b = _twins("node-not-ready", unverified=True)[0]
    node = b.draw.scope_value
    assert f'nodes "{node}" is forbidden' in b.user
    assert all(r.result.decided and r.result.outcome == "unverified" for r in b.rows)
    assert all(r.workload.decided_outcome == "unverified" for r in b.rows)
    assert b.user.count(" — unverified\n") == len(b.rows)
    assert rules.shared(tuple(r.result for r in b.rows)) == ()


def test_unverified_needs_a_down_node():
    st = stories.by_key()["coredns-down"]
    d = so.draw(st, random.Random(7), width=len(st.victims))
    with pytest.raises(ValueError, match="unverified"):
        so.build(st, d, world="broken", unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        so.build(st, d, world="healthy", unverified=True)


def test_health_header_counts_the_down_node():
    b, h = _twins("node-not-ready")
    total = len(b.draw.nodes)
    assert 3 <= total <= 5
    assert f"{total - 1}/{total} nodes Ready" in b.user
    assert b.health.nodes_total == total and b.health.nodes_ready == total - 1
    assert h.health is None or not h.health.degraded


def test_netpol_line_only_in_the_broken_world():
    b, h = _twins("networkpolicy-deny-all")
    assert "default-deny" in b.user and "default-deny" not in h.user


def test_log_reads_print_a_known_label():
    b, h = _twins("coredns-down")
    for built in (b, h):
        for line in built.user.splitlines():
            if LOG_CAUSE_PREFIX in line:
                assert line.split(LOG_CAUSE_PREFIX, 1)[1].strip() in LOG_CAUSES


def test_origin_row_only_in_the_broken_world():
    b, h = _twins("coredns-down")
    assert [r.key for r in b.rows if r.role == "origin"] == ["kube-system/coredns"]
    assert not [r for r in h.rows if r.role == "origin"]
    assert "kube-system/kube-dns" in b.user and "kube-system/kube-dns" not in h.user


def test_width_two_drops_the_third_victim():
    b, _ = _twins("coredns-down", width=2)
    assert len([r for r in b.rows if r.role == "victim"]) == 2


def test_prompt_fits_and_has_at_most_ten_workloads():
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        for built in _twins(key):
            assert len(built.rows) <= c.MAX_GATHER_WORKLOADS
            assert len(built.gathered.reads) <= c.MAX_TOOL_CALLS


def test_draw_survives_five_named_nodes():
    # Four victims plus the origin can name all 5 of names.NODES; the old
    # randint(6, 5) raised ValueError there.
    base = stories.by_key()["coredns-down"]
    st = dataclasses.replace(base, victims=base.victims + base.victims)
    for seed in range(2000):
        # Stop at the first seed whose victims and origin name every node.
        d = so.draw(st, random.Random(seed), width=4)
        named = {n.node for n in d.victims} | {d.origin.node}
        if len(named) == 5:
            break
    else:
        pytest.fail("no seed in 2000 names all five nodes")
    assert d.nodes == tuple(sorted(names_mod.NODES))
    assert len(d.nodes) >= 3


def test_log_body_refuses_an_empty_log():
    with pytest.raises(ValueError, match="empty"):
        so._log_body("")
