import dataclasses
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import health, rules, stories
from kubeagent_verdict.dataset import names as names_mod
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


def test_pvc_candidate_only_when_the_claim_is_flagged():
    b, h = _twins("storage-provisioner-down")
    assert any(cd.obj.kind == "pvc" for r in b.rows for cd in r.trace)
    assert not any(cd.obj.kind == "pvc" for r in h.rows for cd in r.trace)


def test_pvc_victims_group_by_storage_class():
    b, _ = _twins("pvc-storageclass-missing")
    assert rules.shared(tuple(r.result for r in b.rows))
    assert "fast-ssd" in b.user


def test_registry_candidate_reads_the_pull_literal():
    b, _ = _twins("registry-unreachable")
    assert "connection refused" in b.user
    assert all(r.result.decided for r in b.rows if r.role == "victim")


REGISTRY_STORIES = ("registry-mirror-unreachable", "registry-rate-limited",
                    "registry-unreachable")


@pytest.mark.parametrize("key", REGISTRY_STORIES)
def test_registry_literal_is_in_every_broken_pull_event(key):
    st = stories.by_key()[key]
    b, h = _twins(key)
    pulling = [v for v in st.victims if v.pulls]
    assert len(pulling) == len(st.victims)
    for r in b.rows:
        # The printed events read carries the full pull message for this image.
        # An address is redacted in the printed read, so the exam story's
        # literal (it names one) is matched by its tail.
        shown = st.broken.pull_literal if key not in stories.EXAM_KEYS else \
            st.broken.pull_literal.rsplit(": ", 1)[-1]
        assert f'Failed to pull image "{r.names.image}": ' in b.user
        assert shown in b.user
    assert st.broken.pull_literal not in h.user
    for r in h.rows:
        assert f'Failed to pull image "{r.names.image}": ' in h.user


@pytest.mark.parametrize("key", REGISTRY_STORIES)
def test_healthy_twin_has_a_refuted_registry_candidate(key):
    # [C]: every pulling victim gets a registry object in both worlds. In the
    # healthy world the pull events hold an image-side literal, so the
    # registry candidate is present but refuted, never confirmed.
    b, h = _twins(key)
    for built in (b, h):
        for r in built.rows:
            regs = [cd for cd in r.trace if cd.obj.kind == "registry"]
            assert len(regs) == 1, (key, built.world_name, r.key)
    for r in h.rows:
        paired = [cd for cd in r.candidates if cd.cause.startswith("registry ")]
        assert len(paired) == 1
        assert paired[0].fresh_read_outcome == "refuted", (key, r.key, paired[0])
        assert not r.result.decided
    for r in b.rows:
        paired = [cd for cd in r.candidates if cd.cause.startswith("registry ")]
        assert paired[0].fresh_read_outcome == "confirmed"


@pytest.mark.parametrize("key", REGISTRY_STORIES)
def test_registry_count_is_filled_in_every_world(key):
    # [D]: the count is the number of pulling workloads in the row, and the
    # "{count}" template never reaches a trace or the prompt.
    st = stories.by_key()[key]
    n = len(st.victims)
    for built in _twins(key):
        assert "{count}" not in built.user
        for r in built.rows:
            for cd in r.trace:
                assert "{count}" not in cd.cause
                assert "{count}" not in cd.obj.scan_reason
            for cd in r.candidates:
                assert "{count}" not in cd.cause
    b, _ = _twins(key)
    assert f"({n} workloads failing to pull)" in b.user
    for r in b.rows:
        assert r.result.cause.endswith(f"({n} workloads failing to pull)")


def test_registry_count_follows_the_width():
    b, _ = _twins("registry-rate-limited", width=2)
    assert "(2 workloads failing to pull)" in b.user
    assert "(3 workloads failing to pull)" not in b.user


@pytest.mark.parametrize("key", ["node-kubelet-halted", "node-kubelet-unresponsive"])
def test_node_r_stories_describe_the_down_node(key):
    b, h = _twins(key)
    assert all(r.result.decided for r in b.rows)
    assert f"describe node /{b.draw.scope_value}" in b.user
    assert "NotReady" in b.user and "NotReady" not in h.user


def test_unresponsive_node_carries_a_lease_older_than_the_threshold():
    # health.LEASES has no "stale": a lease is "renewed" and its age is what
    # goes stale (health._stale). The brief's lease="stale" is lease="renewed"
    # with a 95 s age, past the scan's 40 s threshold.
    st = stories.by_key()["node-kubelet-unresponsive"]
    assert st.broken.lease == "renewed" and st.broken.lease_age_ms == 95_000
    assert st.broken.lease_age_ms > health.THRESHOLD_MS
