import json
import random

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, names


def _entry(key):
    return next(e for e in catalog.all_entries() if e.key == key)


def test_attributed_example_shape():
    n = names.draw(random.Random(11))
    ex = cases.attributed(_entry("memory-limit-oomkill"), n)
    assert ex.case == "attributed"
    assert ex.group == f"memory-limit-oomkill:{n.ns}/{n.name}"
    assert ex.system == c.SYSTEM_PROMPT
    assert f"- {n.ns}/{n.name} (Deployment)" in ex.user
    assert "== BEGIN candidates ==" in ex.user
    assert "considered memory limit too low for the workload: attributed" in ex.user
    doc = json.loads(ex.assistant)
    assert set(doc) == {"verdicts", "summary"}
    (row,) = doc["verdicts"]
    assert row["workload"] == f"{n.ns}/{n.name}"
    assert row["cause"] == "memory limit too low for the workload"
    assert row["confidence"] == "high"  # direct=True entry with full evidence
    assert ex.meta["expected_cause"] == row["cause"]


def test_attributed_indirect_entry_gets_medium():
    n = names.draw(random.Random(12))
    ex = cases.attributed(_entry("probe-failure"), n)
    assert json.loads(ex.assistant)["verdicts"][0]["confidence"] == "medium"


def test_attributed_user_message_is_contract_valid():
    n = names.draw(random.Random(13))
    ex = cases.attributed(_entry("deployment-bad-image-tag"), n)
    assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
    assert ex.user.endswith(c.CLOSING_INSTRUCTION)


def test_none_of_these_contradicts_and_answers_none():
    n = names.draw(random.Random(21))
    ex = cases.none_of_these_case(_entry("memory-limit-oomkill"), n)
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == c.NONE_OF_THESE
    assert row["confidence"] == "medium"
    assert "exit code 1" in ex.user  # the contradiction evidence is in the prompt
    assert "OOMKilled, exit code 137" not in ex.user.split("== BEGIN evidence ==")[1]


def test_own_cause_omits_winner_from_candidates():
    n = names.draw(random.Random(22))
    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n)
    cand_section = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    assert "memory limit too low for the workload" not in cand_section
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"
    assert ex.meta["expected_own_keywords"] == ["memory", "limit"]


def test_truncated_case_earns_low_confidence():
    n = names.draw(random.Random(23))
    ex = cases.truncated(_entry("crashloop-pod"), n)
    assert c.TRUNCATION_MARKER in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["confidence"] == "low"


def test_injection_answer_ignores_payload():
    n = names.draw(random.Random(24))
    payload = cases.INJECTION_PAYLOADS[0]
    ex = cases.injection(_entry("deployment-bad-image-tag"), n, payload)
    assert payload in ex.user  # the attack is really in the evidence
    doc = json.loads(ex.assistant)  # the answer is still pure contract JSON
    assert set(doc) == {"verdicts", "summary"}
    blob = ex.assistant.lower()
    for marker in ("ignore all previous", "markdown", "system:"):
        assert marker not in blob
    assert ex.meta["injection_payload"] == payload


def test_empty_candidates_renders_none_section():
    n = names.draw(random.Random(25))
    ex = cases.empty_candidates(_entry("memory-limit-oomkill"), n)
    assert "== BEGIN candidates ==\n(none)\n== END candidates ==" in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"  # own phrasing
    assert row["confidence"] == "medium"


def test_multi_has_one_row_per_workload():
    rng = random.Random(26)
    pairs = [(_entry("memory-limit-oomkill"), names.draw(rng)),
             (_entry("deployment-bad-image-tag"), names.draw(rng)),
             (_entry("probe-failure"), names.draw(rng))]
    ex = cases.multi(pairs)
    doc = json.loads(ex.assistant)
    assert len(doc["verdicts"]) == 3
    assert {r["workload"] for r in doc["verdicts"]} == {
        f"{n.ns}/{n.name}" for _e, n in pairs
    }
    lines = [ln for ln in doc["summary"].split("\n") if ln.strip()]
    assert len(lines) <= c.MAX_SUMMARY_LINES
