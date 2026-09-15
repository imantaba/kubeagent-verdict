import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "contract" / "capture" / "out"
FIXTURE = REPO / "tests" / "fixtures" / "rules_golden.json"


def test_capture_files_are_staged():
    for name in ("user_message.txt", "input.json", "system_prompt.txt"):
        assert (OUT / name).is_file(), name


def test_staged_input_carries_the_new_fields():
    d = json.loads((OUT / "input.json").read_text(encoding="utf-8"))
    decided = [w for w in d["workloads"] if w["decided"]]
    assert decided, "at least one workload is decided by rules"
    for w in d["workloads"]:
        assert set(w) >= {"decided", "decided_cause", "decided_outcome", "candidates"}
        for cd in w["candidates"]:
            assert set(cd) == {"cause", "verdict", "reason",
                               "fresh_read_outcome", "fresh_read_evidence"}
            if cd["verdict"] == "ruled_out":
                assert cd["fresh_read_outcome"] == "" and cd["fresh_read_evidence"] == ""


def test_staged_prompt_has_the_three_new_shapes():
    text = (OUT / "user_message.txt").read_text(encoding="utf-8")
    assert "      fresh read: confirmed — " in text
    assert "    decided by rules: " in text
    assert "    [truncated by kubeagent]\n" in text


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
    for path in (OUT / "user_message.txt", OUT / "input.json", FIXTURE):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"{path.name} contains {b!r}"
