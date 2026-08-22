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
