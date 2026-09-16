"""The smoke set: three real kubeagent v1.24.0 prompt/reply pairs.

Redacted, tracked under `contract/smoke/`, and scored by the same job 1 the
exam uses on a rule row -- but never gating a pass bar. These tests check
the six files on disk carry none of the banned shapes, that they hold
exactly the twelve rule rows the live run produced, and that scoring them
gives the echoed count measured against the real `job1`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from kubeagent_verdict.evals.smoke import score_smoke_pair

SMOKE = Path(__file__).resolve().parent.parent / "contract" / "smoke"
PAIRS = ("02", "03", "04")
RULE_ROW_COUNTS = {"02": 2, "03": 4, "04": 6}

DOTTED_QUAD = re.compile(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}")
SCHEME_HOST = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s\"]+")
ALLOWED_HOSTS = {"https://registry.invalid", "https://mirror.invalid"}
BANNED_LITERALS = ("kubeconfig", "/home/", "@", "kubeagent-live")


def _files() -> list[Path]:
    return [SMOKE / f"{pair}-{half}.json" for pair in PAIRS for half in ("request", "response")]


def _load(pair: str, half: str) -> dict:
    return json.loads((SMOKE / f"{pair}-{half}.json").read_text(encoding="utf-8"))


def test_the_six_files_exist():
    for path in _files():
        assert path.is_file(), path


def test_no_dotted_quad_ip_in_any_file():
    for path in _files():
        text = path.read_text(encoding="utf-8")
        assert not DOTTED_QUAD.search(text), path


def test_no_host_but_the_two_invalid_ones():
    for path in _files():
        text = path.read_text(encoding="utf-8")
        hosts = set(SCHEME_HOST.findall(text))
        assert hosts <= ALLOWED_HOSTS, (path, hosts - ALLOWED_HOSTS)


@pytest.mark.parametrize("literal", BANNED_LITERALS)
def test_no_banned_literal_in_any_file(literal):
    for path in _files():
        assert literal not in path.read_text(encoding="utf-8"), (literal, path)


def _rule_row_count(request: dict) -> int:
    content = request["messages"][1]["content"]
    return sum(1 for line in content.split("\n") if line.startswith("    decided by rules: "))


def test_rule_row_counts_match_the_live_run():
    counts = {pair: _rule_row_count(_load(pair, "request")) for pair in PAIRS}
    assert counts == RULE_ROW_COUNTS
    assert sum(counts.values()) == 12


def test_score_smoke_pair_finds_one_score_per_rule_row():
    for pair, expected in RULE_ROW_COUNTS.items():
        request = _load(pair, "request")
        response = _load(pair, "response")
        assert len(score_smoke_pair(request, response)) == expected


def test_every_score_is_zero_or_one():
    for pair in PAIRS:
        request = _load(pair, "request")
        response = _load(pair, "response")
        for value in score_smoke_pair(request, response):
            assert value in (0.0, 1.0)


_HEADING_RE = re.compile(r"^- (\S+) \(")
_DECIDED_RE = re.compile(r"^    decided by rules: (.+) — (\w+)$")


def _verbatim_echo_count(request: dict, response: dict) -> tuple[int, int]:
    """(echoed, total): rows where the reply's `cause` matches the prompt's
    `decided_cause` byte for byte -- independent of `job1`'s rationale and
    denial-phrase checks. This is the "echoed on 4" figure the design spec
    and the interface sheet cite; `job1`'s own score over the same rows can
    be lower (see `test_the_live_run_scores_under_job1` below).
    """
    lines = request["messages"][1]["content"].split("\n")
    reply = json.loads(response["choices"][0]["message"]["content"])
    by_workload = {row["workload"]: row for row in reply["verdicts"]}
    workload = None
    total = echoed = 0
    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            workload = heading.group(1)
            continue
        decided = _DECIDED_RE.match(line)
        if not decided:
            continue
        total += 1
        reply_row = by_workload.get(workload)
        if reply_row is not None and reply_row.get("cause") == decided.group(1):
            echoed += 1
    return echoed, total


def test_the_live_run_echoed_the_cause_verbatim_on_four_of_twelve():
    # This count needs no job1 and cannot move: it is a direct byte
    # comparison between the reply's cause and the prompt's decided cause
    # (see the note above this task's step list for why this is a
    # different, and both-real, number from job1's own score below).
    total = 0
    echoed = 0
    for pair in PAIRS:
        e, t = _verbatim_echo_count(_load(pair, "request"), _load(pair, "response"))
        echoed += e
        total += t
    assert total == 12
    assert echoed == 4


def test_the_live_run_scores_under_job1():
    # job1's mechanical score differs from the verbatim-echo count above:
    # shop/cart in pair 03 echoes the cause byte for byte, but its
    # rationale trips the registry denial phrase "rather than the
    # registry" ("...so the reference is stale rather than the registry
    # being unreachable"), so job1 scores it 0.0. Measured by hand against
    # the design's job 1 rules (see the note above this task's step
    # list); re-measure against Task 7's actual `job1` once it exists,
    # and if the real run measures something other than 3, change this
    # pinned number to match. Never change job1, DENIAL_PHRASES, or the
    # fixture files to force a match.
    total = 0
    scored = 0
    for pair in PAIRS:
        request = _load(pair, "request")
        response = _load(pair, "response")
        pair_scores = score_smoke_pair(request, response)
        total += len(pair_scores)
        scored += sum(1 for value in pair_scores if value == 1.0)
    assert total == 12
    assert scored == 3


def test_a_decided_row_with_no_reply_scores_zero():
    request = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": (
            "- shop/api (Deployment) [confidence: high]:\n"
            "    considered node worker-2 (NotReady): attributed — pod api is scheduled on it\n"
            "      fresh read: confirmed — Ready condition is Unknown now\n"
            "    decided by rules: node worker-2 (NotReady) — confirmed\n"
        )},
    ]}
    response = {"choices": [{"message": {"content": json.dumps(
        {"summary": "s", "verdicts": []})}}]}
    assert score_smoke_pair(request, response) == [0.0]


def test_an_exact_echo_with_a_clean_rationale_scores_one():
    request = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": (
            "- shop/api (Deployment) [confidence: high]:\n"
            "    considered node worker-2 (NotReady): attributed — pod api is scheduled on it\n"
            "      fresh read: confirmed — Ready condition is Unknown now\n"
            "    decided by rules: node worker-2 (NotReady) — confirmed\n"
        )},
    ]}
    response = {"choices": [{"message": {"content": json.dumps({
        "summary": "s",
        "verdicts": [{
            "workload": "shop/api",
            "cause": "node worker-2 (NotReady)",
            "confidence": "high",
            "rationale": "the pod is scheduled on this node, which is Unknown right now.",
        }],
    })}}]}
    assert score_smoke_pair(request, response) == [1.0]


def test_a_denial_phrase_in_the_rationale_scores_zero():
    request = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": (
            "- shop/cart (Deployment) [confidence: high]:\n"
            "    considered registry registry.invalid: attributed — pull is failing\n"
            "      fresh read: confirmed — 401 from registry.invalid\n"
            "    decided by rules: registry registry.invalid — confirmed\n"
        )},
    ]}
    response = {"choices": [{"message": {"content": json.dumps({
        "summary": "s",
        "verdicts": [{
            "workload": "shop/cart",
            "cause": "registry registry.invalid",
            "confidence": "high",
            "rationale": "the reference is stale rather than the registry being unreachable.",
        }],
    })}}]}
    assert score_smoke_pair(request, response) == [0.0]


def test_evidence_is_matched_by_cause_not_by_the_line_above_it():
    # A workload with two non-ruled-out candidates: node worker-2 (no
    # kubelet lease) is listed first and is the one `decided by rules:`
    # names, but node worker-3 (NotReady) is listed second, and its own
    # fresh-read line is the one that sits directly above the decided
    # line. kubeagent's writeWorkloadCandidates
    # (internal/investigate/prime.go) prints a fresh-read line for every
    # non-ruled-out candidate and the decided line once, after the whole
    # per-workload loop -- so the line directly above `decided by rules:`
    # is not always the decided candidate's own. This pins that the
    # scorer ties evidence to the candidate named on the decided line, by
    # its cause, not to whichever fresh read happens to render last.
    request = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": (
            "- shop/edge (Deployment) [confidence: medium]:\n"
            "    considered node worker-2 (no kubelet lease): attributed — pod edge is scheduled on it\n"
            "      fresh read: unverified — Ready condition is True, but the kubelet lease was not re-read\n"
            "    considered node worker-3 (NotReady): outranked — a more specific node candidate already attributed\n"
            "      fresh read: refuted — Ready condition is False now\n"
            "    decided by rules: node worker-2 (no kubelet lease) — unverified\n"
        )},
    ]}
    response = {"choices": [{"message": {"content": json.dumps({
        "summary": "s",
        "verdicts": [{
            "workload": "shop/edge",
            "cause": "node worker-2 (no kubelet lease)",
            "confidence": "medium",
            "rationale": (
                "the node is ready right now, but it stopped renewing "
                "its kubelet lease a few minutes ago, so this may "
                "already be stale."
            ),
        }],
    })}}]}
    # The decided candidate's own evidence says "Ready condition is
    # True", so job1's "is ready" exception treats the rationale's "is
    # ready" as agreement, not a denial: 1.0. Keyed to the wrong (second)
    # candidate's evidence instead -- "Ready condition is False now",
    # which does not say "Ready condition is True" -- the same rationale
    # would score 0.0.
    assert score_smoke_pair(request, response) == [1.0]
