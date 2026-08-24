import json

from kubeagent_verdict.evals.contract_check import contract_check

FLAGGED = {"shop/api"}


def _good():
    return {"verdicts": [{"workload": "shop/api", "cause": "x", "confidence": "high",
                          "rationale": "because"}], "summary": "one line"}


def test_valid_answer_passes():
    ok, reasons, doc = contract_check(json.dumps(_good()), FLAGGED)
    assert ok and not reasons and doc["summary"] == "one line"


def test_text_outside_json_fails():
    ok, _reasons, _ = contract_check("Sure! " + json.dumps(_good()), FLAGGED)
    assert not ok  # kubeagent would salvage this; the eval counts it


def test_markdown_fence_fails():
    ok, _, _ = contract_check("```json\n" + json.dumps(_good()) + "\n```", FLAGGED)
    assert not ok


def test_missing_workload_fails():
    ok, reasons, _ = contract_check(json.dumps(_good()), {"shop/api", "web/frontend"})
    assert not ok and any("web/frontend" in r for r in reasons)


def test_extra_workload_fails():
    doc = _good()
    doc["verdicts"].append({"workload": "other/thing", "cause": "x",
                            "confidence": "low", "rationale": "y"})
    ok, _reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok


def test_bad_confidence_fails():
    doc = _good()
    doc["verdicts"][0]["confidence"] = "certain"
    assert not contract_check(json.dumps(doc), FLAGGED)[0]


def test_overlong_line_fails():
    doc = _good()
    doc["verdicts"][0]["rationale"] = "x" * 513
    assert not contract_check(json.dumps(doc), FLAGGED)[0]


def test_five_line_summary_fails():
    doc = _good()
    doc["summary"] = "a\nb\nc\nd\ne"
    assert not contract_check(json.dumps(doc), FLAGGED)[0]


def test_extra_key_fails():
    doc = _good()
    doc["notes"] = "hi"
    assert not contract_check(json.dumps(doc), FLAGGED)[0]


def test_duplicate_workload_fails():
    """The one malformation that satisfies every other check.

    Two rows for the same flagged workload pass the row-key, field-type and
    confidence checks, and the flagged set is fully covered, so nothing else
    in the checker objects. Without this branch a model could answer the same
    workload twice — with two different causes — and score as valid.
    """
    doc = _good()
    doc["verdicts"] = doc["verdicts"] + [dict(doc["verdicts"][0], cause="y")]
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("duplicate workload" in r for r in reasons)


def test_verdicts_not_a_list_fails():
    doc = _good()
    doc["verdicts"] = {"workload": "shop/api"}
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("not a list" in r for r in reasons)


def test_empty_verdicts_fails():
    doc = _good()
    doc["verdicts"] = []
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("not a list" in r for r in reasons)


def test_too_many_rows_fails():
    doc = _good()
    doc["verdicts"] = [dict(doc["verdicts"][0], workload=f"ns/w{i}") for i in range(11)]
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("not a list" in r for r in reasons)


def test_row_missing_a_key_fails():
    doc = _good()
    del doc["verdicts"][0]["rationale"]
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("keys are not exactly" in r for r in reasons)


def test_row_that_is_not_an_object_fails():
    doc = _good()
    doc["verdicts"] = ["shop/api"]
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("keys are not exactly" in r for r in reasons)


def test_non_string_field_fails():
    doc = _good()
    doc["verdicts"][0]["cause"] = 42
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("non-string or empty" in r for r in reasons)


def test_empty_field_fails():
    doc = _good()
    doc["verdicts"][0]["cause"] = ""
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("non-string or empty" in r for r in reasons)


def test_non_string_summary_fails():
    doc = _good()
    doc["summary"] = ["one line"]
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("summary is not a non-empty string" in r for r in reasons)


def test_whitespace_only_summary_fails():
    doc = _good()
    doc["summary"] = "   \n  "
    ok, reasons, _ = contract_check(json.dumps(doc), FLAGGED)
    assert not ok and any("summary is not a non-empty string" in r for r in reasons)
