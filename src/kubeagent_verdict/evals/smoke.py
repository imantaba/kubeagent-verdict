"""Score the smoke set: three real kubeagent v1.24.0 prompt/reply pairs.

The smoke set never trains a bar. `score_smoke_pair` reads a prompt's
`decided by rules:` lines the same way an exam row's meta carries a rule
row, then grades the real reply with `job1` -- the same function that
grades a rule row in the exam. `kv-eval` prints the result under
`smoke (not gated)`; nothing here changes a scoreboard number.
"""
from __future__ import annotations

import json
import re

from kubeagent_verdict.evals.score import job1

_HEADING = re.compile(r"^- (\S+) \(")
_CONSIDERED = re.compile(r"^    considered (.+): \S+(?: \S+)? — .+$")
_DECIDED = re.compile(r"^    decided by rules: (.+) — (\w+)$")
_FRESH_READ = re.compile(r"^      fresh read: \S+ — (.+)$")


def score_smoke_pair(request: dict, response: dict) -> list[float]:
    """`job1` over every rule row in `request`, scored against `response`.

    Reads the prompt's `decided by rules: <cause> — <outcome>` lines in
    prompt order, the same shape an exam row's meta carries for a rule row.
    Each rule row's evidence comes from the `fresh read: <outcome> —
    <evidence>` line under the `considered <cause>:` line that names the
    SAME cause as the decided line -- matched by cause text, not by
    position. kubeagent (`internal/investigate/prime.go`'s
    `writeWorkloadCandidates`) prints a `considered`/`fresh read` pair for
    every non-ruled-out candidate in trace order and appends the single
    `decided by rules:` line only after the whole per-workload loop
    finishes, so on a workload with two or more non-ruled-out candidates
    the line directly above `decided by rules:` is not always the decided
    candidate's own fresh read; a positional lookback would silently tie
    the evidence to the wrong candidate. The most recent workload heading
    line (`- <ns>/<name> (...`) before a decided line names that row's
    workload. `response` is graded by the same `job1` an exam row uses; a
    workload with no reply row scores 0.0, same as a missing exam reply.
    """
    lines = request["messages"][1]["content"].split("\n")
    reply = json.loads(response["choices"][0]["message"]["content"])
    by_workload = {row["workload"]: row for row in reply["verdicts"]}

    scores: list[float] = []
    workload = None
    evidence_by_cause: dict[str, str] = {}
    pending_cause: str | None = None
    for line in lines:
        heading = _HEADING.match(line)
        if heading:
            workload = heading.group(1)
            evidence_by_cause = {}
            pending_cause = None
            continue
        considered = _CONSIDERED.match(line)
        if considered:
            pending_cause = considered.group(1)
            continue
        fresh = _FRESH_READ.match(line)
        if fresh and pending_cause is not None:
            evidence_by_cause[pending_cause] = fresh.group(1)
            pending_cause = None
            continue
        decided = _DECIDED.match(line)
        if not decided:
            continue
        cause, outcome = decided.group(1), decided.group(2)
        meta_workload = {
            "decided_cause": cause,
            "decided_outcome": outcome,
            "decided_evidence": evidence_by_cause.get(cause, ""),
        }
        scores.append(job1(meta_workload, by_workload.get(workload)))
    return scores
