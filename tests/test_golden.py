import json
from pathlib import Path

from kubeagent_verdict import contract as c
from kubeagent_verdict.evals.contract_check import contract_check

GOLDEN = Path(__file__).resolve().parent.parent / "contract" / "golden"


def load_golden_input():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    cluster = c.ClusterHealth(
        degraded=d["cluster"]["degraded"], nodes_ready=d["cluster"]["nodes_ready"],
        nodes_total=d["cluster"]["nodes_total"],
        node_issues=tuple(d["cluster"]["node_issues"]),
        system_issues=tuple(d["cluster"]["system_issues"]),
    )
    def line(x):
        return c.ResourceLine(**x)
    summary = c.ResourceSummary(cpu=line(d["summary"]["cpu"]), memory=line(d["summary"]["memory"]),
                                metrics_available=d["summary"]["metrics_available"])
    svc = tuple(c.ServiceIssue(**s) for s in d["service_issues"])
    workloads = tuple(
        c.Workload(
            namespace=w["namespace"], name=w["name"], kind=w["kind"], ready=w["ready"],
            desired=w["desired"], status=w["status"], restarts=w["restarts"],
            confidence=w.get("confidence", ""),
            findings=tuple(c.Finding(**f) for f in w["findings"]),
            candidates=tuple(c.Candidate(**cd) for cd in w.get("candidates", [])),
            decided=w.get("decided", False),
            decided_cause=w.get("decided_cause", ""),
            decided_outcome=w.get("decided_outcome", ""),
        )
        for w in d["workloads"]
    )
    reads = tuple(c.EvidenceRead(**r) for r in d["reads"])
    return cluster, summary, d["platform_line"], svc, workloads, reads


def test_no_transcription_markers_left():
    assert "TRANSCRIBE-FROM-CAPTURE" not in (GOLDEN / "input.json").read_text(encoding="utf-8")


def test_user_message_matches_kubeagent_bytes():
    expected = (GOLDEN / "user_message.txt").read_text(encoding="utf-8")
    cluster, summary, platform_line, svc, workloads, reads = load_golden_input()
    got = c.build_user_message(cluster, summary, platform_line, svc, workloads, reads)
    assert got == expected


def test_user_message_has_the_v1240_shapes():
    text = (GOLDEN / "user_message.txt").read_text(encoding="utf-8")
    assert "      fresh read: " in text
    assert "      fresh read: confirmed — " in text
    assert "    decided by rules: " in text
    assert "    " + c.TRUNCATION_MARKER + "\n" in text


def test_answer_is_contract_shaped():
    doc = json.loads((GOLDEN / "answer.json").read_text(encoding="utf-8"))
    assert set(doc) == {"verdicts", "summary"}
    rows = doc["verdicts"]
    assert {r["workload"] for r in rows} == {
        "web/frontend", "db/postgres", "db/cache", "db/search",
        "img/one", "img/two", "img/three", "img/five", "img/six", "img/lone",
    }
    for r in rows:
        assert set(r) == {"workload", "cause", "confidence", "rationale"}
        assert r["confidence"] in c.CONFIDENCE_VALUES
    assert len(doc["summary"].split("\n")) <= c.MAX_SUMMARY_LINES


def test_answer_passes_contract_check():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    flagged = {f"{w['namespace']}/{w['name']}" for w in d["workloads"]}
    text = (GOLDEN / "answer.json").read_text(encoding="utf-8")
    ok, reasons, _ = contract_check(text, flagged)
    assert ok, reasons


def test_answer_echoes_every_decided_cause_verbatim():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    doc = json.loads((GOLDEN / "answer.json").read_text(encoding="utf-8"))
    by_workload = {r["workload"]: r for r in doc["verdicts"]}
    for w in d["workloads"]:
        key = f"{w['namespace']}/{w['name']}"
        if w.get("decided"):
            assert by_workload[key]["cause"] == w["decided_cause"], key


def test_input_candidates_have_exact_shape_and_ruled_out_fresh_read_is_empty():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    decided = [w for w in d["workloads"] if w.get("decided")]
    assert decided, "at least one workload is decided by rules"
    for w in d["workloads"]:
        assert set(w) >= {"decided", "decided_cause", "decided_outcome", "candidates"}
        for cd in w["candidates"]:
            assert set(cd) == {"cause", "verdict", "reason",
                               "fresh_read_outcome", "fresh_read_evidence"}
            if cd["verdict"] == "ruled_out":
                assert cd["fresh_read_outcome"] == "" and cd["fresh_read_evidence"] == ""


def test_no_real_identifier_in_golden_files():
    banned = ("kubeconfig", "/home/", "@", "kubeagent-live", "http://", "https://")
    for name in ("user_message.txt", "input.json", "answer.json"):
        text = (GOLDEN / name).read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"{name} contains {b!r}"
