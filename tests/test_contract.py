from pathlib import Path

from kubeagent_verdict import contract as c

REPO = Path(__file__).resolve().parent.parent


def test_system_prompt_matches_pin():
    pinned = (REPO / "contract" / "system_prompt.txt").read_text(encoding="utf-8")
    assert c.SYSTEM_PROMPT == pinned


def test_section_wraps_and_none():
    assert c.section("evidence", "line\n\n") == "== BEGIN evidence ==\nline\n== END evidence ==\n\n"
    assert c.section("evidence", "  \n") == "== BEGIN evidence ==\n(none)\n== END evidence ==\n\n"


def test_cap_content_cuts_on_line_and_marks():
    s = ("x" * 100 + "\n") * 50  # 5050 bytes
    capped = c.cap_content(s)
    assert capped.endswith("\n" + c.TRUNCATION_MARKER)
    body = capped.rsplit("\n", 1)[0]
    assert len(body.encode()) <= c.MAX_READ_BYTES
    assert all(len(ln) in (0, 100) for ln in body.split("\n"))  # only whole lines survive
    assert c.cap_content("short") == "short"


def test_render_evidence_appendread_shape():
    reads = (c.EvidenceRead(label="events shop/api-1", content="Warning BackOff\n\n"),)
    assert c.render_evidence(reads) == "== events shop/api-1 ==\nWarning BackOff\n\n"


def test_render_candidates_format_and_cap():
    cands = tuple(
        c.Candidate(cause=f"cause-{i}", verdict="ruled_out", reason=f"r{i}") for i in range(9)
    )
    w = c.Workload(
        namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
        status="Progressing", restarts=3, findings=(), candidates=cands, confidence="high",
    )
    out = c.render_candidates((w,))
    assert out.startswith("- shop/api (Deployment) [confidence: high]:\n")
    assert "    considered cause-0: ruled out — r0\n" in out
    assert "cause-8" not in out
    assert out.endswith("    " + c.TRUNCATION_MARKER + "\n")
    bare = c.Workload(
        namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
        status="Progressing", restarts=3, findings=(),
    )
    assert c.render_candidates((bare,)) == ""


def _finding(**over):
    base = {
        "issue": "CrashLoopBackOff", "reason": "back-off restarting failed container",
        "evidence": "container app restarted 14 times",
        "next_step": "inspect the previous container log", "command": "kubectl -n shop logs api -p",
    }
    base.update(over)
    return c.Finding(**base)


def test_render_inventory_full_shape():
    cluster = c.ClusterHealth(degraded=True, nodes_ready=2, nodes_total=3,
                              node_issues=("worker-2 NotReady (KubeletNotReady)",))
    summary = c.ResourceSummary(
        cpu=c.ResourceLine(allocatable="6", requests="4200m", requests_pct=70,
                           limits="5400m", limits_pct=90),
        memory=c.ResourceLine(allocatable="12Gi", requests="9Gi", requests_pct=75,
                              limits="11Gi", limits_pct=91),
    )
    w = c.Workload(
        namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
        status="Progressing", restarts=14,
        findings=(_finding(log_cause="fatal: config file /etc/app/app.yaml not found"),),
    )
    svc = (c.ServiceIssue(namespace="shop", name="api", type="NoReadyEndpoints",
                          detail="service has 0 ready endpoints"),)
    out = c.render_inventory(cluster, summary, "", svc, (w,))
    assert out.startswith("Cluster health (P1): DEGRADED — 2/3 nodes Ready.\n"
                          "  node worker-2 NotReady (KubeletNotReady)\n\n")
    assert "Cluster resources:\n" in out
    assert "  CPU: allocatable 6 cores, requests 4200m (70%), limits 5400m (90%)\n" in out
    assert "  Memory: allocatable 12Gi, requests 9Gi (75%), limits 11Gi (91%)\n" in out
    assert "Workload problems (P2):\n\n" in out
    assert "- shop/api (Deployment): 0/2 ready, status Progressing, 14 restarts\n" in out
    assert ("    issue: CrashLoopBackOff — back-off restarting failed container "
            "(container app restarted 14 times)\n") in out
    assert "      log cause: fatal: config file /etc/app/app.yaml not found\n" in out
    assert ("      suggested fix (deterministic, pre-reviewed — do not substitute): "
            "inspect the previous container log | run: kubectl -n shop logs api -p\n") in out
    assert "Service issues:\n  - shop/api (NoReadyEndpoints): service has 0 ready endpoints\n" in out
    assert "Explain each problem" not in out  # the --explain closing line is never rendered


def test_finding_block_collapse_and_cap():
    w = c.Workload(
        namespace="shop", name="api", kind="Deployment", ready=0, desired=5,
        status="Progressing", restarts=20,
        findings=(_finding(), _finding(), _finding(reason="r2"), _finding(reason="r3"),
                  _finding(reason="r4"), _finding(reason="r5")),
    )
    out = c.render_inventory(None, None, "", (), (w,))
    assert ("    issue: CrashLoopBackOff — back-off restarting failed container "
            "(container app restarted 14 times) (×2)\n") in out
    assert "    … and 2 more of the same kind\n" in out  # 5 groups, 3 shown


def test_build_user_message_assembly_and_closing():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),),
                   candidates=(c.Candidate(cause="a bad image", verdict="attributed", reason="tag missing"),))
    reads = (c.EvidenceRead(label="events shop/api-1", content="Warning BackOff"),)
    msg = c.build_user_message(None, None, "", (), (w,), reads)
    assert msg.count("== BEGIN inventory ==") == 1
    assert msg.count("== BEGIN candidates ==") == 1
    assert msg.count("== BEGIN evidence ==") == 1
    assert msg.endswith("== END evidence ==\n\n" + c.CLOSING_INSTRUCTION)


def test_build_user_message_evidence_cut_to_budget():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),))
    # 20 reads would exceed MAX_TOOL_CALLS; use 8 fat reads to overflow 64 KiB
    reads = tuple(
        c.EvidenceRead(label=f"events shop/api-{i}", content=("e" * 90 + "\n") * 45)
        for i in range(8)
    )
    # 8 × ~4KiB ≈ 32 KiB does not overflow; inflate via a long platform line instead
    msg = c.build_user_message(None, None, "p" * 40000, (), (w,), reads)
    assert len(msg.encode("utf-8")) <= c.MAX_PROMPT_BYTES
    assert (c.TRUNCATION_MARKER + "\n== END evidence ==") in msg


def test_build_messages_roles():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),))
    msgs = c.build_messages(None, None, "", (), (w,), ())
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == c.SYSTEM_PROMPT


def test_bounds_enforced():
    import pytest
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),))
    with pytest.raises(ValueError):
        c.build_user_message(None, None, "", (), (w,) * 11, ())
    with pytest.raises(ValueError):
        c.build_user_message(None, None, "", (), (w,),
                             tuple(c.EvidenceRead(label=f"l{i}", content="x") for i in range(9)))


# --- Fix round 1: FINDING 1 — cap_content / build_user_message must not crash on a
# byte cut that straddles a multi-byte UTF-8 character; the invalid tail is replaced
# with U+FFFD instead of raising, matching Go's own pipeline (json.Marshal substitutes
# invalid UTF-8, capContent never decodes at all).

def test_cap_content_replaces_invalid_utf8_at_cut():
    # "a" * 4095 puts the byte-4096 cut exactly on the leading byte of the em dash
    # (a 3-byte UTF-8 sequence), with no newline anywhere in the string to rescue it.
    s = "a" * 4095 + "—" + "b" * 100
    capped = c.cap_content(s)  # must not raise UnicodeDecodeError
    assert capped.endswith("\n" + c.TRUNCATION_MARKER)
    assert "�" in capped  # the straddled byte becomes U+FFFD, not a crash


def test_build_user_message_evidence_cut_replaces_invalid_utf8():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),))
    # A single-character em-dash label with ascii padding after it: render_evidence's
    # own "== <label> ==\n" header is the only region reachable by the byte-budget cut
    # (any later newline in the bundle always wins the "cut back to the last newline"
    # rescue), so the multi-byte character to straddle has to live in the label. A
    # large platform_line forces the assembled prompt far enough over MAX_PROMPT_BYTES
    # that the computed cut lands one byte into the em dash's 3-byte UTF-8 sequence.
    reads = (c.EvidenceRead(label="—", content="z" * 50),)
    msg = c.build_user_message(None, None, "p" * 64950, (), (w,), reads)  # must not raise
    assert (c.TRUNCATION_MARKER + "\n== END evidence ==") in msg
    assert "�" in msg  # the straddled byte becomes U+FFFD, not a crash


# --- Fix round 1: FINDING 2 — _finding_block must redact network addresses out of
# Finding.evidence and Finding.log_cause before rendering, mirroring kubeagent's
# internal/redact.Addresses (internal/explain/explain.go:284,297).

def test_redact_addresses_cases():
    assert c.redact_addresses("dial tcp 10.96.0.10:53: connect: connection refused") == (
        "dial tcp <redacted>: connect: connection refused"
    )
    assert c.redact_addresses("[::1]:8080") == "<redacted>"
    assert c.redact_addresses("redis:6379") == "redis:6379"  # R248: single-label host, no dot
    assert c.redact_addresses("v1.32.8") == "v1.32.8"  # dotted but no port: not an address
    assert c.redact_addresses("checked 10.244.1.7 twice") == "checked <redacted> twice"


def test_finding_block_redacts_evidence_and_log_cause():
    f = _finding(
        evidence="dial tcp 10.96.0.10:53: connect: connection refused",
        log_cause="dial tcp 10.96.0.10:53: connect: connection refused",
    )
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(f,))
    out = c.render_inventory(None, None, "", (), (w,))
    assert ("    issue: CrashLoopBackOff — back-off restarting failed container "
            "(dial tcp <redacted>: connect: connection refused)\n") in out
    assert "      log cause: dial tcp <redacted>: connect: connection refused\n" in out
    assert "10.96.0.10" not in out


# --- Fix round 1: MINORS — pin the three branch shapes the reviewer verified by hand.

def test_finding_block_resources_line():
    f = _finding(resources=c.ContainerResources(
        mem_request="256Mi", mem_limit="512Mi", cpu_request="250m", cpu_limit="500m",
    ))
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(f,))
    out = c.render_inventory(None, None, "", (), (w,))
    assert ("      container resources: memory req=256Mi limit=512Mi, "
            "cpu req=250m limit=500m\n") in out


def test_render_inventory_network_policies_line():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),),
                   network_policies=("deny-all", "allow-dns"))
    out = c.render_inventory(None, None, "", (), (w,))
    assert "    network policy: pods selected by deny-all, allow-dns (possible cause)\n" in out


def test_render_inventory_rollout_line_with_image():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),),
                   rollout=c.Rollout(revision="7", since="3m ago",
                                      old_image="app:1.2.2", new_image="app:1.2.3"))
    out = c.render_inventory(None, None, "", (), (w,))
    assert ("    recent change: rolled out to revision 7 3m ago, "
            "image app:1.2.2 → app:1.2.3\n") in out


def test_render_inventory_rollout_line_without_image():
    w = c.Workload(namespace="shop", name="api", kind="Deployment", ready=0, desired=2,
                   status="Progressing", restarts=3, findings=(_finding(),),
                   rollout=c.Rollout(revision="7", since="3m ago"))
    out = c.render_inventory(None, None, "", (), (w,))
    assert "    recent change: rolled out to revision 7 3m ago\n" in out
