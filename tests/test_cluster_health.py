"""The cluster-health block: `render.cluster_health` and the prompt it opens.

When kubeagent's cluster verdict is Degraded, the inventory starts with
`Cluster health (P1): DEGRADED — R/T nodes Ready.`, then one `  node` line
per node issue, one `  system` line per system issue and a blank line
(internal/explain/explain.go:178-186 at v1.24.0). The verdict is Degraded
when there is any node issue or any system issue
(internal/clusterhealth/clusterhealth.go:60-108).

The dataset has no node list. `render.cluster_health` builds the verdict
from what the row already shows: its node candidates, its `describe node`
reads and its flagged kube-system workloads.

Port vectors cite their Go test as `file:line` under kubeagent's
`internal/`. These clusterhealth_test.go tests are not ported, because
they need inputs the dataset never builds:

- `:38` TestNodeHealth (DiskPressure and SchedulingDisabled; its bare
  NotReady vector is the same as `:160`);
- `:93` TestNamespaceScopeNote (a `-n` scope);
- `:231`, `:249`, `:289`, `:319`, `:334` (lease timestamps, heartbeat
  thresholds and an unreadable lease list; `:301`'s rule, no lease issue
  on a NotReady node, is kept by the precedence test below);
- `:363`, `:374`, `:382`, `:397`, `:408` (expected node names);
- `:420`, `:456` (the DownNodes list, which the block does not print);
- `:473` (hostile reason and message text). The block's reason and
  message are two fixed strings, and `safetext.Line` is ported as `gather.safetext_line`.
"""
from __future__ import annotations

import re

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, gather, generate, health, render, stories

K4 = "NotReady: KubeletNotReady — container runtime is down"


def _wl(name="api", *, ns="shop", kind="Deployment", ready=0, desired=2,
        status="Degraded", candidates=()):
    return c.Workload(namespace=ns, name=name, kind=kind, ready=ready, desired=desired,
                      status=status, restarts=0, findings=(), candidates=candidates)


def _node(name, reason="NotReady", verdict="attributed"):
    """A node candidate in kubeagent's shape, `node X (reason)`
    (rootcause/rootcause.go:44)."""
    return c.Candidate(cause=f"node {name} ({reason})", verdict=verdict,
                       reason="pod api-0 is scheduled on it")


def _describe(name):
    """A node describe read, labelled as `rules.read_text` labels it."""
    return c.EvidenceRead(label=f"describe node /{name}",
                          content=f"node {name}: unschedulable=false\n")


# --- port tests --------------------------------------------------------------

def test_render_inventory_leads_with_the_degraded_cluster():
    """explain/explain_test.go:110 (TestBuildInventoryPrompt_LeadsWithDegradedCluster),
    against `contract.render_inventory`: the header line with the node count,
    the node line, the blank line, and no workloads section when there are
    no workloads. kubeagent's closing line is trimmed off
    (investigate/local.go:74-76), so this is the whole inventory."""
    cluster = c.ClusterHealth(degraded=True, nodes_total=3, nodes_ready=1,
                              node_issues=("n2 NotReady",))
    got = c.render_inventory(cluster, None, "", (), ())
    assert got == ("Cluster health (P1): DEGRADED — 1/3 nodes Ready.\n"
                   "  node n2 NotReady\n"
                   "\n")
    assert "Workload problems" not in got


def test_render_inventory_prints_no_block_for_a_healthy_cluster():
    """explain/explain.go:178: only a Degraded verdict prints the block."""
    assert c.render_inventory(c.ClusterHealth(degraded=False, nodes_total=3,
                                              nodes_ready=3), None, "", (), ()) == ""


def test_not_ready_issue_includes_reason_and_message():
    """clusterhealth/clusterhealth_test.go:130."""
    got = render._not_ready_issue(
        "KubeletNotReady", "container runtime network not ready: cni config uninitialized")
    assert got == ("NotReady: KubeletNotReady — container runtime network not ready: "
                   "cni config uninitialized")


def test_not_ready_issue_trims_a_long_message():
    """clusterhealth/clusterhealth_test.go:141: 120 runes of message, then an
    ellipsis."""
    got = render._not_ready_issue("KubeletNotReady", "x" * 200)
    assert got == "NotReady: KubeletNotReady — " + "x" * 120 + "…"
    assert len(got) <= 160


def test_not_ready_issue_falls_back_when_empty():
    """clusterhealth/clusterhealth_test.go:160, and the bare NotReady vector
    of :38."""
    assert render._not_ready_issue("", "") == "NotReady"


def test_not_ready_issue_with_a_reason_only_or_a_message_only():
    """The two one-sided arms of notReadyIssue (clusterhealth.go:210-213).
    Go has no test of its own for them."""
    assert render._not_ready_issue("KubeletNotReady", "") == "NotReady: KubeletNotReady"
    assert render._not_ready_issue("", "runtime down") == "NotReady: runtime down"


def test_a_multi_line_message_folds_to_one_line():
    """clusterhealth/clusterhealth_test.go:176. nodeHealth passes both
    strings through safetext.Line first (clusterhealth.go:181), which folds
    the newline to a space, so trimLine's first-line cut never fires."""
    got = render._not_ready_issue(gather.safetext_line("KubeletNotReady"),
                                  gather.safetext_line("first line\nsecond line"))
    assert got == "NotReady: KubeletNotReady — first line second line"


def test_a_long_message_stays_bounded():
    """clusterhealth/clusterhealth_test.go:495: the message is cut at 120
    runes, plus the ellipsis."""
    got = render._not_ready_issue("", "x" * 400)
    assert len(got) == len("NotReady: ") + 121


def test_the_not_ready_issue_carries_the_node_name():
    """clusterhealth/clusterhealth_test.go:183. Go's vector has the message
    "kubelet stopped posting node status"; the dataset's one down-node story
    uses the kubelet's "container runtime is down". So the name join is
    checked on the block and Go's own string on the helper."""
    assert (render._not_ready_issue("KubeletNotReady", "kubelet stopped posting node status")
            == "NotReady: KubeletNotReady — kubelet stopped posting node status")
    got = render.cluster_health((_wl(candidates=(_node("worker-2"),)),), ())
    assert got is not None and got.degraded
    assert got.node_issues == ("worker-2 " + K4,)


def test_down_nodes_names_the_node_the_block_prints_not_ready():
    """Exam rebuild, item 9: the service line's endpoint cause reads the
    same down nodes the cluster-health block judged."""
    workloads = (_wl(candidates=(_node("worker-2"),)),)
    assert render.cluster_health(workloads, ()).node_issues[0].startswith("worker-2 ")
    assert render.down_nodes(workloads, ()) == (health.DownNode("worker-2", "NotReady"),)


def test_a_system_job_omits_the_count():
    """clusterhealth/clusterhealth_test.go:107: a Job or CronJob prints its
    status only. A Failed status alone flags the workload
    (inventory/inventory.go:102-104)."""
    job = _wl("migrate", ns="kube-system", kind="Job", ready=0, desired=0, status="Failed")
    got = render.cluster_health((job,), ())
    assert got is not None and got.degraded
    assert got.system_issues == ("kube-system/migrate Failed",)
    cron = _wl("backup", ns="kube-system", kind="CronJob", ready=0, desired=0,
               status="Failed")
    assert render.cluster_health((cron,), ()).system_issues == ("kube-system/backup Failed",)


def test_degraded_by_node_and_system():
    """clusterhealth/clusterhealth_test.go:193. Go's cluster there has two
    nodes, so it reads 1/2; the dataset's rule is T = max(3, named + 1), so
    the same two named nodes read 2/3. The system line is Go's exactly."""
    coredns = _wl("coredns", ns="kube-system", ready=1, desired=2, status="Degraded",
                  candidates=(_node("b"),))
    got = render.cluster_health((coredns,), (_describe("a"),))
    assert got is not None and got.degraded
    assert (got.nodes_ready, got.nodes_total) == (2, 3)
    assert got.node_issues == ("b " + K4,)
    assert got.system_issues == ("kube-system/coredns 1/2 Degraded",)


def test_a_missing_lease_is_flagged_and_counts_ready():
    """clusterhealth/clusterhealth_test.go:258 and :274: the issue is
    `w1 no kubelet lease`, the cluster is Degraded, and the node still
    counts as Ready, because the lease check runs only on a Ready node
    (clusterhealth.go:73-82)."""
    got = render.cluster_health((_wl(candidates=(_node("w1", "no kubelet lease"),)),), ())
    assert got is not None and got.degraded
    assert got.node_issues == ("w1 no kubelet lease",)
    assert (got.nodes_ready, got.nodes_total) == (3, 3)


def test_a_healthy_system_workload_and_an_other_namespace_give_no_block():
    """clusterhealth/clusterhealth_test.go:70: a kube-system workload that is
    not flagged, and a flagged workload outside kube-system, are not system
    issues. With no node issue either, the cluster is Healthy."""
    coredns = _wl("coredns", ns="kube-system", ready=2, desired=2, status="Running")
    web = _wl("web", ns="default", ready=1, desired=2, status="Degraded")
    assert render.cluster_health((coredns, web), ()) is None


# --- the rule ----------------------------------------------------------------

@pytest.mark.parametrize("verdict", ["attributed", "ruled_out", "outranked"])
def test_a_node_candidate_of_any_verdict_makes_the_block(verdict):
    got = render.cluster_health((_wl(candidates=(_node("worker-1", verdict=verdict),)),), ())
    assert got == c.ClusterHealth(degraded=True, nodes_ready=2, nodes_total=3,
                                  node_issues=("worker-1 " + K4,))


def test_a_flagged_kube_system_workload_makes_the_block():
    got = render.cluster_health((_wl("coredns", ns="kube-system"),), ())
    assert got == c.ClusterHealth(degraded=True, nodes_ready=3, nodes_total=3,
                                  system_issues=("kube-system/coredns 0/2 Degraded",))


def test_no_node_candidate_and_no_system_workload_gives_no_block():
    """A PVC candidate, a hand-typed cause that only mentions a node, and a
    describe read are none of them a node candidate."""
    w = _wl(candidates=(
        c.Candidate(cause="PVC data-0 (ProvisioningFailed)", verdict="ruled_out",
                    reason="not mounted by this workload's pods"),
        c.Candidate(cause="node worker-2 is cordoned and under disk pressure",
                    verdict="attributed", reason="the scheduler says so"),
    ))
    assert render.cluster_health((w,), (_describe("worker-2"),)) is None
    assert render.cluster_health((), ()) is None


@pytest.mark.parametrize("down, ready_total", [
    (("worker-1",), (2, 3)),
    (("worker-1", "worker-2"), (1, 3)),
    (("worker-1", "worker-2", "worker-3"), (1, 4)),
])
def test_total_and_ready_count_the_not_ready_nodes(down, ready_total):
    """T = max(3, named nodes + 1) and R = T minus the NotReady nodes."""
    w = _wl(candidates=tuple(_node(n) for n in down))
    got = render.cluster_health((w,), ())
    assert (got.nodes_ready, got.nodes_total) == ready_total


def test_a_describe_read_names_a_healthy_node():
    """A node the prompt names only in a `describe node /<name>` label
    counts toward T and is Ready. It gets no node line."""
    w = _wl(candidates=(_node("worker-1"), _node("worker-2")))
    without = render.cluster_health((w,), ())
    with_label = render.cluster_health((w,), (_describe("worker-1"), _describe("worker-3")))
    assert (without.nodes_ready, without.nodes_total) == (1, 3)
    assert (with_label.nodes_ready, with_label.nodes_total) == (2, 4)
    assert with_label.node_issues == without.node_issues


def test_a_label_that_is_not_kubeagents_node_describe_names_no_node():
    """Only the gather's own label shape counts (investigate/gather.go:132)."""
    w = _wl(candidates=(_node("worker-1"),))
    other = c.EvidenceRead(label="describe node worker-3 (CSI status)", content="x\n")
    assert render.cluster_health((w,), (other,)).nodes_total == 3


def test_node_lines_are_in_name_order_one_per_node():
    """A node that is a candidate on two workloads gets one line. Lines are
    in node-name order, not candidate order."""
    a = _wl("api", candidates=(_node("worker-3"), _node("worker-1", "no kubelet lease")))
    b = _wl("web", candidates=(_node("worker-2", verdict="ruled_out"),
                               _node("worker-3", verdict="ruled_out")))
    got = render.cluster_health((a, b), ())
    assert got.node_issues == ("worker-1 no kubelet lease",
                               "worker-2 " + K4,
                               "worker-3 " + K4)
    assert (got.nodes_ready, got.nodes_total) == (2, 4)


def test_a_not_ready_candidate_wins_over_a_lease_candidate_for_one_node():
    """Go runs the lease check only on a Ready node (clusterhealth.go:73-82),
    so a NotReady node never also reads `no kubelet lease`
    (clusterhealth/clusterhealth_test.go:301). A row that
    declares both for one node gets the NotReady line only."""
    a = _wl("api", candidates=(_node("worker-3", "no kubelet lease"),))
    b = _wl("web", candidates=(_node("worker-3"),))
    for order in ((a, b), (b, a)):
        got = render.cluster_health(order, ())
        assert got.node_issues == ("worker-3 " + K4,)
        assert (got.nodes_ready, got.nodes_total) == (2, 3)


def test_system_lines_are_in_go_order():
    """inventory.Assemble sorts flagged workloads by namespace, name, kind
    (inventory/inventory.go:534-547), and Assess keeps that order."""
    ws = (_wl("metrics-server", ns="kube-system"),
          _wl("coredns", ns="kube-system", kind="StatefulSet", ready=1),
          _wl("coredns", ns="kube-system", kind="Deployment", ready=1))
    got = render.cluster_health(ws, ())
    assert got.system_issues == ("kube-system/coredns 1/2 Degraded",
                                 "kube-system/coredns 1/2 Degraded",
                                 "kube-system/metrics-server 0/2 Degraded")


def test_an_unknown_node_reason_raises():
    """The dataset builds three node-down stories. This block has text for two
    reasons: NotReady and no kubelet lease. Any other reason has no block
    text here, so it raises."""
    w = _wl(candidates=(_node("worker-1", "kubelet not heartbeating"),))
    with pytest.raises(ValueError, match="worker-1"):
        render.cluster_health((w,), ())


# --- the wiring --------------------------------------------------------------

def test_user_message_computes_the_block_itself():
    """`cases._user_message` takes no cluster argument: the block comes from
    the workloads and reads it is given."""
    w = _wl(candidates=(_node("worker-2"),))
    user = cases._user_message(None, "", (), (w,), (_describe("worker-2"),), key="k")
    assert user.startswith("== BEGIN inventory ==\n"
                           "Cluster health (P1): DEGRADED — 2/3 nodes Ready.\n"
                           "  node worker-2 " + K4 + "\n"
                           "\n"
                           "Workload problems (P2):\n")
    plain = cases._user_message(None, "", (), (_wl(),), (), key="k")
    assert plain.startswith("== BEGIN inventory ==\nWorkload problems (P2):\n")


_BLOCK = "== BEGIN inventory ==\nCluster health (P1): DEGRADED — "
_NODE_CANDIDATE = re.compile(
    r"^    considered node ([^ ()]+) \((.+)\): (?:attributed|ruled out|outranked) — ",
    re.MULTILINE)
_NODE_LINE = re.compile(r"^  node (\S+) ", re.MULTILINE)
_DESCRIBE = re.compile(r"^== describe node /(\S+) ==$", re.MULTILINE)


def _section(user: str, name: str) -> str:
    return user.split(f"== BEGIN {name} ==\n", 1)[1].split(f"\n== END {name} ==", 1)[0]


def _story_of(group: str) -> str:
    """The story key of a propagation row: its group begins `propagation:<key>`
    and joins the row's workloads with `+`, every part naming the same story.
    Any other group has no story, and the caller fails on the empty string."""
    keys = {part.split(":")[1] for part in group.split("+") if part.startswith("propagation:")}
    return keys.pop() if group.startswith("propagation:") and len(keys) == 1 else ""


def _story_block_line(story: str, node: str) -> str:
    """The `  node` line the cluster-health block prints for `node` when the
    node is in `story`'s broken-world state. It is read the way the real
    pipeline reads it, through `health.assess` on the story's own node
    fields, so no reason text or lease age is copied into this test."""
    w = stories.by_key()[story].broken
    got, _ = health.assess((health.Node(node, conditions=w.conditions,
                                        unschedulable=w.unschedulable, lease=w.lease,
                                        lease_age_ms=w.lease_age_ms),), ())
    assert got is not None and len(got.node_issues) == 1, (story, node)
    return "  node " + got.node_issues[0]


def _check_rows(rows) -> tuple[int, int]:
    with_block = without = 0
    for ex in rows:
        user = ex.user
        candidates = _section(user, "candidates")
        shown: dict[str, set[str]] = {}
        for name, reason in _NODE_CANDIDATE.findall(candidates):
            shown.setdefault(name, set()).add(reason)
        system = "\n- kube-system/" in "\n" + _section(user, "inventory")
        has_block = user.startswith(_BLOCK)
        if shown or system:
            assert has_block, ex.group
        if not has_block:
            without += 1
            continue
        with_block += 1
        block = user[len("== BEGIN inventory ==\n"):].split("\n\n", 1)[0]
        lines = block.split("\n")
        story = _story_of(ex.group)
        for name, reasons in shown.items():
            # A training row that names one node both ways gets the
            # NotReady line (see the precedence test above).
            if "NotReady" in reasons:
                line = f"  node {name} " + K4
            elif reasons == {"no kubelet lease"}:
                line = f"  node {name} no kubelet lease"
            elif reasons == {"kubelet not heartbeating"}:
                # A stale lease on a Ready node: the block prints the age, which only
                # the story's world knows.
                assert story, (ex.group, name)
                line = _story_block_line(story, name)
            else:
                raise AssertionError((ex.group, name, reasons))
            assert line in lines, (ex.group, name)
        # A node line with no candidate on screen has one of two causes. Either it
        # is a candidate past the per-workload cap of 8 (contract.py:200), whose
        # describe read is still in the evidence; or the row is a propagation
        # row whose story breaks a node in a way no candidate names (a pressure
        # condition, a cordon). The block reads node state, not candidates, so
        # it prints exactly what the story's broken world makes of that node.
        described = set(_DESCRIBE.findall(_section(user, "evidence")))
        for line in lines:
            m = _NODE_LINE.match(line)
            if not m or m.group(1) in shown:
                continue
            name = m.group(1)
            if c.TRUNCATION_MARKER in candidates and name in described:
                continue
            assert story, (ex.group, name)
            assert line == _story_block_line(story, name), (ex.group, name, story)
    return with_block, without


def test_every_exam_row_opens_with_the_block_iff_it_shows_a_node_or_system_problem():
    with_block, without = _check_rows(generate.test_set())
    assert with_block and without


def test_every_training_row_opens_with_the_block_iff_it_shows_a_node_or_system_problem():
    with_block, without = _check_rows(generate.generate(seed=17, size=800))
    assert with_block and without
