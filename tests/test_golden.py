import json
from pathlib import Path

from kubeagent_verdict import contract as c

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


def test_answer_is_contract_shaped():
    doc = json.loads((GOLDEN / "answer.json").read_text(encoding="utf-8"))
    assert set(doc) == {"verdicts", "summary"}
    rows = doc["verdicts"]
    assert {r["workload"] for r in rows} == {"shop/api", "web/frontend"}
    for r in rows:
        assert set(r) == {"workload", "cause", "confidence", "rationale"}
        assert r["confidence"] in c.CONFIDENCE_VALUES
    assert len(doc["summary"].split("\n")) <= c.MAX_SUMMARY_LINES
