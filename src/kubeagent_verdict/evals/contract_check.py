"""Strict verdict-contract-v1 acceptance: stricter than kubeagent on purpose.

kubeagent's runtime parser is lenient — it salvages prose-wrapped JSON,
drops out-of-set rows, and rewrites unknown confidence to "unstated" —
because at runtime a repaired answer beats none. Here every repair
kubeagent would have performed is a counted failure, so training pushes
the model toward output that needs no repair at all.
"""

from __future__ import annotations

import json

from kubeagent_verdict import contract as c

_ROW_KEYS = {"workload", "cause", "confidence", "rationale"}


def _line_ok(text: str) -> bool:
    return all(len(line) <= c.MAX_MODEL_LINE_RUNES for line in text.split("\n"))


def contract_check(text: str, flagged: set[str]) -> tuple[bool, list[str], dict | None]:
    reasons: list[str] = []
    try:
        doc = json.loads(text.strip())
    except json.JSONDecodeError:
        return False, ["not a bare JSON object (parse error)"], None
    if not isinstance(doc, dict):
        return False, ["top level is not a JSON object"], None
    if set(doc) != {"verdicts", "summary"}:
        reasons.append(f"top-level keys {sorted(doc)} != ['summary', 'verdicts']")

    rows = doc.get("verdicts")
    seen: set[str] = set()
    if not isinstance(rows, list) or not 1 <= len(rows) <= c.MAX_VERDICT_ROWS:
        reasons.append("verdicts is not a list of 1..10 rows")
    else:
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != _ROW_KEYS:
                reasons.append(f"row {i}: keys are not exactly {sorted(_ROW_KEYS)}")
                continue
            if not all(isinstance(v, str) and v for v in row.values()):
                reasons.append(f"row {i}: non-string or empty field")
                continue
            if row["workload"] in seen:
                reasons.append(f"row {i}: duplicate workload {row['workload']}")
            seen.add(row["workload"])
            if row["workload"] not in flagged:
                reasons.append(f"row {i}: workload {row['workload']} was not flagged")
            if row["confidence"] not in c.CONFIDENCE_VALUES:
                reasons.append(f"row {i}: confidence {row['confidence']!r} out of vocabulary")
            if not (_line_ok(row["cause"]) and _line_ok(row["rationale"])):
                reasons.append(f"row {i}: line over {c.MAX_MODEL_LINE_RUNES} runes")
        for missing in sorted(flagged - seen):
            reasons.append(f"no verdict row for flagged workload {missing}")

    summary = doc.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        reasons.append("summary is not a non-empty string")
    else:
        lines = [ln for ln in summary.split("\n") if ln.strip()]
        if len(lines) > c.MAX_SUMMARY_LINES:
            reasons.append(f"summary has {len(lines)} lines (max {c.MAX_SUMMARY_LINES})")
        if not _line_ok(summary):
            reasons.append(f"summary line over {c.MAX_MODEL_LINE_RUNES} runes")

    return (not reasons), reasons, doc
