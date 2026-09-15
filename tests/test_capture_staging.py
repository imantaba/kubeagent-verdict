import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "contract" / "capture" / "out"
FIXTURE = REPO / "tests" / "fixtures" / "rules_golden.json"


def test_capture_files_are_staged():
    assert (OUT / "system_prompt.txt").is_file()


def test_staged_system_prompt_has_the_decided_paragraph():
    text = (OUT / "system_prompt.txt").read_text(encoding="utf-8")
    assert 'A workload marked "decided by rules" has its cause fixed by kubeagent' in text


def test_rules_fixture_shape():
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert d["kubeagent"] == {
        "tag": "v1.24.0", "commit": "15ec5649bbd2d07558eae945b71430afc8f231fd"}
    assert len(d["workloads"]) == 12
    assert len(d["reads"]) == 8
    assert len(d["shared"]) == 2
    for w in d["workloads"]:
        assert set(w) == {"namespace", "name", "pod", "issue", "image",
                          "candidates", "result"}
        assert set(w["result"]) == {"decided", "cause", "outcome", "evidence",
                                    "group_key", "group_text", "decisions"}


def test_no_real_identifier_in_capture_outputs():
    banned = ("kubeconfig", "/home/", "@", "kubeagent-live", "http://", "https://")
    for path in (OUT / "system_prompt.txt", FIXTURE):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"{path.name} contains {b!r}"
