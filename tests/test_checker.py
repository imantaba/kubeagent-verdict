"""The checker: a finished row, read against what kubeagent v1.24.0 can send.

The checker is the net that keeps every row faithful to the gather. These
tests pin four things:

- the rows pass: the golden, the seed set and the exam pool, 0 violations;
- each rule catches something: one broken copy per rule, and no rule that
  never looks at anything;
- no case is exempt: the shared-origin family is checked by every rule;
- the checker stays independent: stdlib only, and its own copies of
  kubeagent's strings still equal the builder's.
"""
from __future__ import annotations

import ast
import copy
import json
import random
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import (
    cases,
    checker,
    gather,
    generate,
    gold,
    health,
    objects,
    render,
    rules,
    stories,
)

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
GOLDEN = ROOT / "contract" / "golden"
CHECKER_PY = ROOT / "src" / "kubeagent_verdict" / "dataset" / "checker.py"
SEED, SIZE = 17, 800


def _golden() -> tuple[str, str, str, None]:
    return ((ROOT / "contract" / "system_prompt.txt").read_text(encoding="utf-8"),
            (GOLDEN / "user_message.txt").read_text(encoding="utf-8"),
            (GOLDEN / "answer.json").read_text(encoding="utf-8"),
            None)


def _parts(row: dict) -> tuple[str, str, str, dict]:
    system, user, assistant = (m["content"] for m in row["messages"])
    return system, user, assistant, row["meta"]


def _fired(report: checker.Report) -> set[str]:
    return {v.rule for v in report.violations}


def _where(report: checker.Report) -> list[str]:
    return [f"{v.rule} at {v.where}: {v.quote}" for v in report.violations]


@pytest.fixture(scope="module")
def seed_rows() -> list[dict]:
    return [generate.to_row(ex) for ex in generate.generate(SEED, SIZE)]


@pytest.fixture(scope="module")
def exam_rows() -> list[dict]:
    """The exam pool, built once for this module (as each module does)."""
    return [generate.to_row(ex)
            for ex in generate.generate(SEED, 8000) + generate.test_set()]


@pytest.fixture(scope="module")
def seed_reports(seed_rows) -> list[checker.Report]:
    return [checker.check_row(r) for r in seed_rows]


@pytest.fixture(scope="module")
def exam_reports(exam_rows) -> list[checker.Report]:
    return [checker.check_row(r) for r in exam_rows]


# --- the rows pass --------------------------------------------------------

def test_the_golden_passes():
    assert _where(checker.check(*_golden())) == []


def test_the_seed_set_passes(seed_rows, seed_reports):
    failed = [(r["meta"]["case"], _where(rep)[:3])
              for r, rep in zip(seed_rows, seed_reports) if rep.violations]
    assert failed == []


def test_the_exam_pool_passes(exam_rows, exam_reports):
    failed = [(r["meta"]["case"], _where(rep)[:3])
              for r, rep in zip(exam_rows, exam_reports) if rep.violations]
    assert failed == []


def test_no_rule_is_dead(seed_reports, exam_reports):
    """Every rule looks at something in the golden, the seed set or the exam."""
    seen: Counter[str] = Counter(checker.check(*_golden()).inspected)
    for rep in seed_reports + exam_reports:
        seen.update(rep.inspected)
    assert [rule for rule in checker.RULES if seen[rule] == 0] == []


# --- one broken copy per rule --------------------------------------------
#
# Each entry takes a passing prompt, breaks it in one place, and names the
# rule that must catch it. The source is the golden (None) or the first
# seed row a predicate picks.

def _user(fn):
    def brk(system, user, assistant, meta):
        return system, fn(user), assistant, meta
    return brk


def _replace(old: str, new: str):
    def fn(user: str) -> str:
        assert old in user, old
        return user.replace(old, new, 1)
    return _user(fn)


def _regex(pattern: str, repl: str):
    def fn(user: str) -> str:
        out, n = re.subn(pattern, repl, user, count=1, flags=re.MULTILINE)
        assert n == 1, pattern
        return out
    return _user(fn)


def _in_block(key: str, old: str, new: str):
    """Replace `old` inside the candidate block of workload `key` only."""
    def fn(user: str) -> str:
        start = user.index(f"\n- {key} (", user.index("== BEGIN candidates ==\n"))
        end = user.find("\n- ", start + 1)
        if end == -1:
            end = user.index("\n== END candidates ==")
        block = user[start:end]
        assert old in block, old
        return user[:start] + block.replace(old, new, 1) + user[end:]
    return _user(fn)


def _answer(fn):
    def brk(system, user, assistant, meta):
        doc = json.loads(assistant)
        fn(doc)
        return system, user, json.dumps(doc, ensure_ascii=False), meta
    return brk


def _set_verdict(workload: str, key: str, value: str):
    def fn(doc: dict) -> None:
        v = next(v for v in doc["verdicts"] if v["workload"] == workload)
        v[key] = value
    return _answer(fn)


def _add_keyword(system, user, assistant, meta):
    meta = copy.deepcopy(meta)
    w = next(w for w in meta["workloads"].values() if w.get("own_cause_keywords"))
    w["own_cause_keywords"].append("made-up-keyword-nowhere")
    return system, user, assistant, meta


_UNSCHEDULABLE = (r"^(    issue: Unschedulable .*?) preemption: 0/\d+ nodes are available: "
                  r"[^)]*\)$")
_RESTART_LOOP = r'^(    issue: RestartLoop .*container "[^"]*", )\d+( restarts, last exit)'
_DETECTOR_AGE = r"^(    issue: .*, last exit -?\d+ \([^)]*\), )(\S+)( ago)"
_LOG_CAUSE_READ = r"^log cause: .*$"


def _has(pattern: str):
    return lambda row: re.search(pattern, row["messages"][1]["content"], re.MULTILINE) is not None


def _has_own_keywords(row: dict) -> bool:
    return any((w or {}).get("own_cause_keywords") for w in row["meta"]["workloads"].values())


_APP_API_ISSUE = '(Failed to pull image "registry.invalid/app/api:1.4")'

BROKEN = {
    # the frame
    "A1": (None, _replace("== BEGIN evidence ==", "== BEGIN proof ==")),
    "A2": (None, _replace(checker.CLOSING_INSTRUCTION, "Judge each workload now.")),
    "A3": (None, _replace("\n  taint node.kubernetes.io/",
                          "\n" + checker.TRUNCATION_MARKER + "\n  taint node.kubernetes.io/")),
    "A4": (None, lambda s, u, a, m: (s + " ", u, a, m)),
    "A5": (None, _replace("\n== END candidates ==", "\n\n== END candidates ==")),
    "A6": (None, _replace("\nWorkload problems (P2):", "\nPlatform: k3s\n\nWorkload problems (P2):")),
    # the inventory
    "B1": (None, _replace("- img/two (Deployment): 0/1 ready", "- img/aaa (Deployment): 0/1 ready")),
    "B2": (None, _replace("0/2 ready, status Degraded, 7 restarts", "0/2 ready, Degraded, 7 restarts")),
    "B3": (None, _replace("(back-off 5m0s restarting failed container)",
                          "(back-off 5m0s restarting failed container) (×1)")),
    "B4": (None, _replace("- app/api (Deployment): 0/2 ready, status Degraded, 0 restarts\n",
                          "- app/api (Deployment): 0/2 ready, status Degraded, 0 restarts\n"
                          "    network policy: pods selected by app=api (possible cause)\n")),
    "B5": (None, _replace("2/4 nodes Ready.", "3/4 nodes Ready.")),
    "B6": (None, _replace("  - shop/api (NoReadyEndpoints): ", "  - shop/api: ")),
    "B7": (None, _replace("  node worker-2 no kubelet lease\n", "")),
    "B8": (None, _in_block("img/solo", "\n    considered node worker-2 (no kubelet lease): ruled out — "
                                       "no pod of this workload is scheduled on it", "")),
    # the candidates
    "C1": (None, _replace("- img/two (Deployment) [confidence: medium]:",
                          "- img/two (StatefulSet) [confidence: medium]:")),
    "C1-conf": (None, _replace("- app/api (Deployment) [confidence: high]:",
                               "- app/api (Deployment) [confidence: medium]:")),
    "C1-cause": (None, _replace("considered registry mirror.invalid: ruled out",
                                "considered the mirror host: ruled out")),
    "C2-vocab": (None, _in_block("app/api", "(no kubelet lease): ruled out —",
                                 "(no kubelet lease): dismissed —")),
    "C2-reason": (None, _in_block("app/api", "ruled out — no pod of this workload is scheduled on it",
                                  "ruled out — no pod of this workload runs on it")),
    "C3": (lambda r: "\n    [truncated by kubeagent]\n" in r["messages"][1]["content"],
           _replace("\n    [truncated by kubeagent]\n",
                    "\n    [truncated by kubeagent]\n    [truncated by kubeagent]\n")),
    "C4-order": (None, _replace("(ProvisioningFailed): outranked — node worker-1 (NotReady) is the",
                                "(ProvisioningFailed): outranked — node worker-7 (NotReady) is the")),
    "C4-dedup": (None, _in_block("kube-system/coredns", "considered node worker-2 (no kubelet lease)",
                                 "considered node worker-2 (NotReady)")),
    "C5/D4": (None, _replace("\n    decided by rules: node worker-1 (NotReady) — confirmed", "")),
    # the fresh reads
    "D1": (None, _in_block("app/api", "ruled out — no pod of this workload is scheduled on it",
                           "ruled out — no pod of this workload is scheduled on it\n"
                           "      fresh read: unverified — " + checker.NEVER_READ)),
    "D1-onefresh": (None, _in_block(
        "app/api", '\n      fresh read: unverified — fresh read failed: nodes "worker-7" is forbidden', "")),
    "D2-vocab": (None, _replace("fresh read: confirmed — Ready condition is False now",
                                "fresh read: confirmed — Ready condition is False")),
    "D3": (None, _replace("  condition Ready=False (KubeletNotReady): container runtime is down",
                          "  condition Ready=True (KubeletReady): kubelet is posting ready status")),
    # the evidence
    "E1": (None, _replace("\n== END evidence ==",
                          "\n\n== events web/frontend-5b8d7f6c9-q2w3e ==\n"
                          "no events for web/frontend-5b8d7f6c9-q2w3e\n== END evidence ==")),
    "E2-order": (None, _replace("== events app/api-6d5f7c8b9-k2m4p ==",
                                "== events app/web-6d5f7c8b9-k2m4p ==")),
    "E3": (None, _replace("pvc db/aux-0: phase=Bound storageClass=fast-ssd volume=pv-0442",
                          "pvc db/aux-0: phase=Bound storageClass=fast-ssd volume=pv-0442\n"
                          + "x" * 4100)),
    "E4": (None, _replace("== describe pvc db/aux-1 ==", "== describe persistentvolumeclaim db/aux-1 ==")),
    "E5": (None, _replace("== describe pvc db/aux-1 ==", "== describe pvc db/aux-0 ==")),
    "E6": (None, _replace("events for db/orders-0:", "events for db/orders-1:")),
    "E7": (None, _replace("  condition Ready=False (KubeletNotReady): container",
                          "  condition Ready=False (): container")),
    "E8": (None, _replace("pvc db/data-0: phase=Lost storageClass=fast-ssd volume=pv-0821",
                          "pvc db/data-0: phase=Lost")),
    "E9": (_has(_LOG_CAUSE_READ), _regex(_LOG_CAUSE_READ, "log cause: a cause logscan never returns")),
    "E10": (None, _replace("\nread failed: events is forbidden", "\nread failed: events is forbidden\nby policy")),
    "E-min": (None, _replace("\n\n== events img/seven-7c9d4b5f6-fghij ==\nread failed: events is forbidden",
                             "")),
    # the text
    "F1": (None, _replace("service has 0 ready endpoints", "service has 0 ready\x07 endpoints")),
    "F2": (None, _replace("dial tcp <redacted>: connect", "dial tcp registry.invalid:5000: connect")),
    "F3": (None, _set_verdict("app/api", "rationale", "x" * 513)),
    "TXT-IS8": (None, _replace(_APP_API_ISSUE, '(Failed to pull image "": manifest unknown)')),
    "TXT-IS9": (_has(_UNSCHEDULABLE), _regex(_UNSCHEDULABLE, r"\1)")),
    "TXT-IS11": (None, _replace(_APP_API_ISSUE,
                                '(Failed to pull image "registry.invalid/app/api:1.4": dial tcp: i/o timeout)')),
    "TXT-IS14": (_has(_RESTART_LOOP), _regex(_RESTART_LOOP, r"\g<1>2\g<2>")),
    "TXT-IS15": (_has(_DETECTOR_AGE), _regex(_DETECTOR_AGE, r"\g<1>90s\g<3>")),
    "TXT-IS17": (None, _replace("logs <pod> -c coredns --previous", "logs <pod> --previous")),
    "TXT-IS22": (None, _replace("(0/4 nodes are available: pod has unbound",
                                "(0/3 nodes are available: pod has unbound")),
    "TXT-POD": (None, _replace("kubectl -n web describe pod <pod>",
                               "kubectl -n web describe pod frontend-5b8d7f6c9-q2w3e")),
    # the answer
    "ANS-1": (None, _set_verdict("app/api", "cause", "node worker-2 (no kubelet lease)")),
    "ANS-2": (_has_own_keywords, _add_keyword),
}


def test_every_rule_has_a_broken_copy():
    assert set(BROKEN) == set(checker.RULES)
    # 2026-09-26 (faithful prompts): TXT-POD checks the pod slot of a fix command 48 -> 49
    # 2026-09-28 (final review): B8 checks each block lists the row's down nodes and its
    # namespace's broken PVCs 49 -> 50
    # 2026-10-05 (Spec 4b-3): TXT-IS22 checks every scheduler node count against the header 50 -> 51
    assert len(checker.RULES) == len(set(checker.RULES)) == 51


# `_source` and two other pickers keep skipping the shared-origin family so
# each broken copy keeps the source row it had before Spec 4b-1 (the other
# families' rows are byte-identical). The family's own rows are checked by
# test_shared_origin_row_passes_every_rule and the manifest test.
def _family(row: dict) -> bool:
    return row["meta"]["case"].startswith("shared_origin")


def _source(pick, seed_rows) -> tuple:
    if pick is None:
        return _golden()
    row = next(r for r in seed_rows if not _family(r) and pick(r))
    return _parts(row)


@pytest.mark.parametrize("rule", list(BROKEN))
def test_the_broken_copy_is_caught(rule, seed_rows):
    pick, brk = BROKEN[rule]
    source = _source(pick, seed_rows)
    assert rule not in _fired(checker.check(*source))
    broken = checker.check(*brk(*source))
    assert rule in _fired(broken), _where(broken)


def test_a_second_attributed_candidate_counts_whatever_its_cause_says():
    """C4-order counts every attributed candidate, not only the ones whose
    cause kubeagent can write: a made-up cause is C1-cause's to catch, and a
    second attributed line is still C4-order's."""
    system, user, assistant, meta = _golden()
    user = _in_block("app/api", "    considered node worker-2 (no kubelet lease)",
                     "    considered the mirror host: attributed — it looks slow\n"
                     "    considered node worker-2 (no kubelet lease)")(system, user, assistant, meta)[1]
    assert "C4-order" in _fired(checker.check(system, user, assistant, meta))


_CRASH_FIX = re.compile(
    r'^(    issue: (?:CrashLoopBackOff|RestartLoop) — .*\(container "[^"]*", .*\n'
    r'(?:      log cause: .*\n)?'
    r'      suggested fix .* logs \S+ -c )(\S+)( --previous)$', re.MULTILINE)


def test_a_crash_findings_logs_command_names_its_own_container(seed_rows):
    """TXT-IS17 reads the container from the finding, so it guards generated
    rows too, whose workload names are drawn."""
    row = next(r for r in seed_rows
               if not _family(r) and _CRASH_FIX.search(r["messages"][1]["content"]))
    system, user, assistant, meta = _parts(row)
    report = checker.check(system, user, assistant, meta)
    assert report.inspected["TXT-IS17"] > 0
    assert "TXT-IS17" not in _fired(report)
    broken = _CRASH_FIX.sub(r"\g<1>sidecar\g<3>", user, count=1)
    assert broken != user
    assert "TXT-IS17" in _fired(checker.check(system, broken, assistant, meta))


def test_the_pod_slot_holds_the_placeholder_or_the_workloads_own_name():
    """TXT-POD reads every arm that has a name slot. suggestionFor swaps the
    finding's pod for `<pod>` unless the finding sits on the workload itself
    (explain.go:162-171). RolloutStuck and JobFailed name the workload
    (objectEventsCmd, jobLogsCmd, describeCronJobCmd), so those arms keep its
    name. A pod finding on a controller's workload is always swapped, and
    `-n` is always the workload's own namespace.

    2026-09-28 (final review): `describe pod frontend` passed here, and
    `<pod>` passed in the RolloutStuck and JobFailed arms. web/frontend is a
    Deployment, so kubeagent masks its pod, and it never masks a workload's
    own name. Both now fire."""
    system, user, assistant, meta = _golden()
    assert checker.check(system, user, assistant, meta).inspected["TXT-POD"] == 11
    fix, pod = "kubectl -n web describe pod <pod>", "frontend-5b8d7f6c9-q2w3e"
    for cmd in ("kubectl -n web get events --field-selector involvedObject.name=frontend",
                "kubectl -n web logs job/frontend",
                "kubectl -n web describe cronjob frontend",
                "kubectl -n web logs <pod> -c app --previous"):
        report = checker.check(system, user.replace(fix, cmd, 1), assistant, meta)
        assert "TXT-POD" not in _fired(report), cmd
    for cmd in (f"kubectl -n web get events --field-selector involvedObject.name={pod}",
                f"kubectl -n web logs {pod} -c app --previous",
                f"kubectl -n web logs job/{pod}",
                f"kubectl -n web describe cronjob {pod}",
                "kubectl -n web describe pod api",
                # a Deployment's pod finding: kubeagent swaps even the workload's name
                "kubectl -n web describe pod frontend",
                "kubectl -n web logs frontend -c app --previous",
                # a finding on the workload: kubeagent never swaps its name
                "kubectl -n web get events --field-selector involvedObject.name=<pod>",
                "kubectl -n web logs job/<pod>",
                "kubectl -n web describe cronjob <pod>",
                # another namespace
                "kubectl -n shop describe pod <pod>",
                "kubectl -n shop get events --field-selector involvedObject.name=frontend",
                "kubectl -n  describe pod <pod>"):
        report = checker.check(system, user.replace(fix, cmd, 1), assistant, meta)
        assert "TXT-POD" in _fired(report), cmd


def test_a_bare_pods_slot_holds_its_own_name():
    """A bare pod is its own workload (inventory/inventory.go:402), so its
    finding's pod is the workload and suggestionFor keeps the name."""
    system, user, assistant, meta = _golden()
    user = user.replace("- web/frontend (Deployment): ", "- web/frontend (Pod): ", 1)
    fix = "kubectl -n web describe pod <pod>"
    for cmd, fires in (("kubectl -n web describe pod frontend", False),
                       ("kubectl -n web logs frontend -c app --previous", False),
                       ("kubectl -n web describe pod <pod>", True),
                       ("kubectl -n web logs <pod> -c app --previous", True),
                       ("kubectl -n shop describe pod frontend", True)):
        report = checker.check(system, user.replace(fix, cmd, 1), assistant, meta)
        assert ("TXT-POD" in _fired(report)) is fires, cmd


# --- TXT-IS15: the lease and rollout arms ---------------------------------

_WORKER_2 = "  node worker-2 no kubelet lease\n"
_FRONTEND_FIX = ("verify the tag exists and the registry credentials | run: "
                 "kubectl -n web describe pod <pod>\n")


def _is15(user: str) -> tuple[bool, int]:
    system, _user, assistant, meta = _golden()
    report = checker.check(system, user, assistant, meta)
    return "TXT-IS15" in _fired(report), report.inspected["TXT-IS15"]


def test_is15_reads_a_lease_age_in_go_duration_form():
    """clusterhealth.go:144 prints a stale lease as time.Duration.String,
    rounded to the second: `2m5s`, never `125s` or `2m5.5s`."""
    _s, user, _a, _m = _golden()
    assert _WORKER_2 in user
    _fired0, n0 = _is15(user)

    def lease(age: str) -> str:
        return user.replace(_WORKER_2,
                            f"  node worker-2 kubelet not heartbeating (lease {age} stale)\n", 1)

    assert _is15(lease("2m5s")) == (False, n0 + 1)
    assert _is15(lease("125s")) == (True, n0 + 1)
    assert _is15(lease("2m5.5s")) == (True, n0 + 1)


def test_is15_reads_a_rollout_age_in_human_age_form():
    """explain.go:212 prints a recent change's age as inventory.HumanAge: one
    number and one of d, h, m, s, such as `3h`, never `3h0m0s`."""
    _s, user, _a, _m = _golden()
    assert _FRONTEND_FIX in user
    _fired0, n0 = _is15(user)

    def rollout(age: str) -> str:
        line = (f"    recent change: rolled out to revision 4 {age} ago, image "
                "registry.invalid/web/frontend:2.0 → registry.invalid/web/frontend:2.1\n")
        return user.replace(_FRONTEND_FIX, _FRONTEND_FIX + line, 1)

    assert _is15(rollout("3h")) == (False, n0 + 1)
    assert _is15(rollout("3h0m0s")) == (True, n0 + 1)
    assert _is15(rollout("03h")) == (True, n0 + 1)


# --- B8: every block lists the row's down nodes and its namespace's PVCs --

def _block_span(user: str, key: str) -> tuple[int, int]:
    """Where workload `key`'s candidate block sits in `user`."""
    section_end = user.index("\n== END candidates ==")
    start = user.index(f"\n- {key} (", user.index("== BEGIN candidates ==\n"))
    end = user.find("\n- ", start + 1)
    return start, section_end if end == -1 or end > section_end else end


def _without_cand(user: str, key: str, cause: str) -> str:
    """`user` with `key`'s candidate line for `cause`, and its fresh lines, gone."""
    start, end = _block_span(user, key)
    kept, skip = [], False
    for ln in user[start:end].split("\n"):
        if ln.startswith(f"    considered {cause}: "):
            skip = True
            continue
        if skip and ln.startswith("      fresh read: "):
            continue
        skip = False
        kept.append(ln)
    return user[:start] + "\n".join(kept) + user[end:]


_RANK = {"node": 0, "PVC": 1}
_CONSIDERED_OBJECT = re.compile(r"^    considered (node|PVC|registry) (\S+)")


def _with_ruled_out(user: str, key: str, kind: str, name: str, reason: str) -> str:
    """`user` with `key`'s ruled-out line for node or PVC `name`, where
    rootcause puts it: nodes by name, then PVCs by name, then the registry."""
    start, end = _block_span(user, key)
    lines = user[start:end].split("\n")
    sentence = checker.NODE_RULED_OUT if kind == "node" else checker.PVC_RULED_OUT
    at = len(lines)
    for i, ln in enumerate(lines):
        m = _CONSIDERED_OBJECT.match(ln)
        if m and (_RANK.get(m.group(1), 2), m.group(2)) > (_RANK[kind], name):
            at = i
            break
        if ln.startswith("    decided by rules: ") or ln == "    " + checker.TRUNCATION_MARKER:
            at = i
            break
    lines.insert(at, f"    considered {kind} {name} ({reason}): ruled out — {sentence}")
    return user[:start] + "\n".join(lines) + user[end:]


def _own(block, kind: str) -> dict[str, str]:
    """The block's own objects of `kind`: name -> reason, for each candidate
    rootcause did not rule out (so one of the workload's pods uses it)."""
    return {s[1]: s[2] for c in block.cands
            if c.verdict != "ruled out" and (s := checker._shape(c.cause)) and s[0] == kind}


def _owed(user: str, kind: str, pick) -> list[tuple[str, str, str]]:
    """(block, name, reason) for each `kind` object one workload uses that
    another block `b` owes a ruled-out line for. `pick(a, b)` says whether
    block `b` owes one for block `a`'s objects."""
    blocks = checker._parse(user).blocks
    return [(b.key, name, reason)
            for a in blocks for name, reason in sorted(_own(a, kind).items())
            for b in blocks if b is not a and pick(a, b) and name not in _own(b, kind)]


def _one_owed(rows: list[dict], case: str, kind: str, pick) -> dict:
    """The first `case` row with exactly one owed line, missing or not."""
    return next(row for row in rows if row["meta"]["case"] == case
                and len(_owed(row["messages"][1]["content"], kind, pick)) == 1)


def _missing_then_added(row: dict, kind: str, pick) -> tuple[tuple, tuple]:
    """Two copies of `row`: one whose block lacks the line it owes for
    another workload's `kind` object, and one with the ruled-out line
    added back."""
    system, user, assistant, meta = _parts(row)
    ((key, name, reason),) = _owed(user, kind, pick)
    word = "node" if kind == "node" else "PVC"
    missing = _without_cand(user, key, f"{word} {name} ({reason})")
    added = _with_ruled_out(missing, key, word, name, reason)
    return (system, missing, assistant, meta), (system, added, assistant, meta)


def _any(a, b) -> bool:
    return True


def _same_ns(a, b) -> bool:
    return a.ns == b.ns


def test_b8_catches_a_probe_block_missing_another_workloads_node(exam_rows):
    """rootcause.Annotate (rootcause.go:24-56) walks every down node for
    every flagged workload, so a node one workload runs on is a ruled-out
    candidate on every other. A probe row missing that line is one
    kubeagent cannot send."""
    row = _one_owed(exam_rows, "multi_misattribution_probe", "node", _any)
    missing, added = _missing_then_added(row, "node", _any)
    assert "B8" in _fired(checker.check(*missing))
    assert "B8" not in _fired(checker.check(*added))


def test_b8_catches_a_same_namespace_block_missing_a_pvc(exam_rows):
    """rootcause.AnnotatePVC (rootcause.go:177-222) walks every broken PVC
    in the workload's own namespace, so a claim one workload mounts is a
    ruled-out candidate on every other workload of that namespace."""
    row = _one_owed(exam_rows, "multi", "pvc", _same_ns)
    missing, added = _missing_then_added(row, "pvc", _same_ns)
    assert "B8" in _fired(checker.check(*missing))
    assert "B8" not in _fired(checker.check(*added))


def test_b8_leaves_a_pvc_in_another_namespace_alone():
    """A PVC in another namespace is not a candidate (rootcause.go:205-207)."""
    system, user, assistant, meta = _golden()
    assert "PVC aux-0" not in user[slice(*_block_span(user, "store/cache"))]
    assert "B8" not in _fired(checker.check(system, user, assistant, meta))


def test_b8_owes_every_block_a_line_for_each_down_node_in_the_health_block():
    system, user, assistant, meta = _golden()
    user = user.replace("  node worker-7 NotReady: KubeletNotReady — container runtime is down\n",
                        "  node worker-7 NotReady: KubeletNotReady — container runtime is down\n"
                        "  node worker-9 NotReady\n", 1)
    assert "B8" in _fired(checker.check(system, user, assistant, meta))


def test_b8_exempts_a_truncated_block():
    """A block past the cap of 8 lost lines nobody can name, so it owes none."""
    system, user, assistant, meta = _golden()
    worker2 = "node worker-2 (no kubelet lease)"
    missing = _without_cand(user, "db/orders", worker2)
    assert "B8" in _fired(checker.check(system, missing, assistant, meta))
    cut = missing.replace("\n    decided by rules: node worker-1 (NotReady) — confirmed\n- img/seven",
                          "\n    " + checker.TRUNCATION_MARKER
                          + "\n    decided by rules: node worker-1 (NotReady) — confirmed\n- img/seven", 1)
    assert cut != missing
    assert "B8" not in _fired(checker.check(system, cut, assistant, meta))


# --- no exemptions (Spec 4b-1) --------------------------------------------

# The 19 rules the shared-origin family skipped until Spec 4b-1 (the old
# EVIDENCE_RULES and PROPAGATION_TEXT_RULES). The family's rows now pass them.
_ONCE_EXEMPT = frozenset({"E1", "E2-order", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10",
                          "E-min", "D3", "B1", "C1-conf", "C1-cause", "C5/D4", "D1-onefresh",
                          "TXT-IS9", "TXT-IS11"})


def test_each_once_exempt_rule_still_fires_on_its_own_bad_row(seed_rows):
    """Each rule still fires on a bad row built for it (its BROKEN copy), and
    a bad row whose meta names a shared-origin case fails the same way: no
    case name turns a rule off."""
    assert _ONCE_EXEMPT <= set(BROKEN)
    for rule in sorted(_ONCE_EXEMPT):
        pick, brk = BROKEN[rule]
        system, user, assistant, meta = brk(*_source(pick, seed_rows))
        assert rule in _fired(checker.check(system, user, assistant, meta)), rule
        if meta is not None:
            for case in ("shared_origin", "shared_origin_decoy", "shared_origin_probe",
                         "shared_origin_decoy_probe"):
                fired = _fired(checker.check(system, user, assistant, {**meta, "case": case}))
                assert rule in fired, (rule, case)


# --- no read is exempt (Spec 4b-3) -------------------------------------------

# The evidence rules that walk the gathered reads. Until 2026-10-05 a
# healthy-origin read at index 0 was left out of them; now every read is in.
_GATHER_RULES = frozenset({"E2-order", "E4", "E6", "E7", "E8", "E9", "E10"})


def test_a_first_read_that_is_not_an_events_read_is_caught(seed_rows):
    """A `multi` row whose read 0 is not an events read fails the checker,
    even when its meta names that read as an origin read."""
    row = next(r for r in seed_rows if r["meta"]["case"] == "multi"
               and "origin_read_label" not in r["meta"])
    system, user, assistant, meta = _parts(row)
    label = "describe node /worker-9"
    user = user.replace("== BEGIN evidence ==\n",
                        f"== BEGIN evidence ==\n== {label} ==\nName: worker-9\n\n", 1)
    meta = {**meta, "origin_read_label": label}
    fired = _fired(checker.check(system, user, assistant, meta))
    assert fired & _GATHER_RULES, fired


def test_meta_none_skips_only_ans1s_meta_clause_and_ans2(seed_rows):
    row = next(r for r in seed_rows
               if not _family(r)
               and _has_own_keywords(r))
    system, user, assistant, meta = _parts(row)
    with_meta = checker.check(system, user, assistant, meta)
    without = checker.check(system, user, assistant, None)
    assert with_meta.inspected["ANS-2"] > 0 and without.inspected["ANS-2"] == 0
    assert {k: v for k, v in with_meta.inspected.items() if k != "ANS-2"} == \
           {k: v for k, v in without.inspected.items() if k != "ANS-2"}
    # ANS-1's meta clause: the answer names the row's workloads.
    doc = json.loads(assistant)
    doc["verdicts"] = doc["verdicts"][1:]
    short = json.dumps(doc, ensure_ascii=False)
    assert "ANS-1" in _fired(checker.check(system, user, short, meta))
    assert "ANS-1" not in _fired(checker.check(system, user, short, None))


# --- independence ---------------------------------------------------------

_STDLIB_ALLOWED = {"__future__", "collections", "dataclasses", "functools", "itertools",
                   "json", "pathlib", "re", "unicodedata"}


def test_the_checker_imports_only_the_standard_library():
    tree = ast.parse(CHECKER_PY.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import"
            names.append(node.module or "")
    tops = {n.split(".")[0] for n in names}
    assert tops <= _STDLIB_ALLOWED
    assert tops <= set(sys.stdlib_module_names) | {"__future__"}
    assert "kubeagent_verdict" not in tops and "random" not in tops


def _literal(test_module: str, name: str):
    """A top-level constant of another test module, read without importing it."""
    tree = ast.parse((TESTS / test_module).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(f"{test_module}: {name}")


def _go_format(s: str) -> str:
    """reader.go's format string with Go's verbs as the checker's fields."""
    return s.replace("%s/%s", "{ns}/{pod}").replace("%q", '"{container}"')


# (the checker's copy, the builder's copy): each pair must stay equal.
COPIES = {
    "MAX_PROMPT_BYTES": (checker.MAX_PROMPT_BYTES, contract.MAX_PROMPT_BYTES),
    "MAX_PROMPT_BYTES (render)": (checker.MAX_PROMPT_BYTES, render.MAX_PROMPT_BYTES),
    "MAX_READ_BYTES": (checker.MAX_READ_BYTES, contract.MAX_READ_BYTES),
    "MAX_TOOL_CALLS": (checker.MAX_TOOL_CALLS, contract.MAX_TOOL_CALLS),
    "MAX_GATHER_WORKLOADS": (checker.MAX_GATHER_WORKLOADS, contract.MAX_GATHER_WORKLOADS),
    "MAX_CANDIDATES_PER_WORKLOAD": (checker.MAX_CANDIDATES_PER_WORKLOAD,
                                    contract.MAX_CANDIDATES_PER_WORKLOAD),
    "MAX_CANDIDATES (rules)": (checker.MAX_CANDIDATES_PER_WORKLOAD, rules.MAX_CANDIDATES),
    "MAX_FINDING_BLOCKS_PER_WORKLOAD": (checker.MAX_FINDING_BLOCKS_PER_WORKLOAD,
                                        contract.MAX_FINDING_BLOCKS_PER_WORKLOAD),
    "MAX_SERVICE_ISSUES": (checker.MAX_SERVICE_ISSUES, contract.MAX_SERVICE_ISSUES),
    "MAX_MODEL_LINE_RUNES": (checker.MAX_MODEL_LINE_RUNES, contract.MAX_MODEL_LINE_RUNES),
    "MAX_LINE": (checker.MAX_LINE, gather.MAX_LINE),
    "MAX_COMBINING": (checker.MAX_COMBINING, gather.MAX_COMBINING),
    "_FOLD": (checker._FOLD, gold._FOLD),
    "REGISTRY_THRESHOLD": (checker.REGISTRY_THRESHOLD, rules.REGISTRY_THRESHOLD),
    "SYSTEM_NAMESPACE": (checker.SYSTEM_NAMESPACE, render._SYSTEM_NAMESPACE),
    "TRUNCATION_MARKER": (checker.TRUNCATION_MARKER, contract.TRUNCATION_MARKER),
    "CLOSING_INSTRUCTION": (checker.CLOSING_INSTRUCTION, contract.CLOSING_INSTRUCTION),
    "the system prompt": (checker._system_prompt(), contract.SYSTEM_PROMPT),
    "VERDICTS": (checker.VERDICTS, tuple(v.replace("_", " ") for v in rules.VERDICTS)),
    "OUTCOMES": (checker.OUTCOMES, rules.OUTCOMES),
    "CRASH_FAMILY": (checker.CRASH_FAMILY, gather.CRASH_FAMILY),
    "PULL_ISSUES": (checker.PULL_ISSUES, rules.REGISTRY_ISSUES),
    "NODE_REASONS": (checker.NODE_REASONS, objects.NODE_SCAN_REASONS),
    "PVC_REASONS": (checker.PVC_REASONS, objects.PVC_SCAN_REASONS),
    "CONNECTION_LITERALS": (checker.CONNECTION_LITERALS, objects.CONNECTION_LITERALS),
    "AUTH_LITERALS": (checker.AUTH_LITERALS, objects.AUTH_LITERALS),
    "IMAGE_LITERALS": (checker.IMAGE_LITERALS, objects.IMAGE_LITERALS),
    "CONFIDENCE_BY_PREFIX": (checker.CONFIDENCE_BY_PREFIX, render._HEADER_BY_PREFIX),
    "ADDR": ((checker.ADDR.pattern, checker.ADDR.flags), (contract._ADDR.pattern, contract._ADDR.flags)),
    "LOG_NO_PREVIOUS": (checker.LOG_NO_PREVIOUS, cases._NO_PREVIOUS),
    "LOG_NO_CLASSIFIABLE": (checker.LOG_NO_CLASSIFIABLE, cases._NO_CLASSIFIABLE),
}

# The same, where the second copy lives in another test module.
TEST_COPIES = {
    "LOG_CAUSES": (checker.LOG_CAUSES,
                   lambda: tuple(_literal("test_gather_text.py", "LOGSCAN_CAUSES").values())),
    "LOG_NO_PREVIOUS (Go format)": (checker.LOG_NO_PREVIOUS,
                                    lambda: _go_format(_literal("test_gather_text.py", "_GO_NO_PREVIOUS"))),
    "LOG_NO_CLASSIFIABLE (Go format)": (
        checker.LOG_NO_CLASSIFIABLE,
        lambda: _go_format(_literal("test_gather_text.py", "_GO_NO_CLASSIFIABLE"))),
    "READ_FAILED_PREFIX": (checker.READ_FAILED_PREFIX,
                           lambda: _literal("test_gather_byte_equal.py", "_FAILED")),
    "NEVER_READ": (checker.NEVER_READ, lambda: _literal("test_gather.py", "NOT_READ")),
    "NO_PULL_EVENT": (checker.NO_PULL_EVENT, lambda: _literal("test_gather.py", "NO_PULL_EVENT")),
    "PULL_POD_UNREAD": (checker.PULL_POD_UNREAD, lambda: _literal("test_gather.py", "WRONG_POD")),
    "CONFIDENCE_BY_PREFIX (test_generate)": (checker.CONFIDENCE_BY_PREFIX,
                                             lambda: _literal("test_generate.py", "_RULE")),
}


@pytest.mark.parametrize("name", list(COPIES))
def test_the_checkers_copy_equals_the_builders(name):
    mine, theirs = COPIES[name]
    assert mine == theirs


@pytest.mark.parametrize("name", list(TEST_COPIES))
def test_the_checkers_copy_equals_the_tests(name):
    mine, theirs = TEST_COPIES[name]
    assert mine == theirs()


def test_the_not_ready_message_cap_is_renders():
    issue = render._not_ready_issue("KubeletNotReady", "x" * 200)
    assert len(issue.split(" — ", 1)[1]) == checker.NOT_READY_MESSAGE_RUNES + 1  # and the ellipsis


def test_the_empty_section_is_contracts():
    for name in checker.SECTIONS:
        assert contract.section(name, "") == \
            f"== BEGIN {name} ==\n{checker.NONE_BODY}\n== END {name} ==\n\n"


def test_the_sentences_rules_writes_inline_are_the_checkers():
    """rules.py writes these as inline literals, not named constants: each
    checker string (or each fixed part of a template) is in its source."""
    source = Path(rules.__file__).read_text(encoding="utf-8")
    fixed = [checker.NODE_RULED_OUT, checker.PVC_RULED_OUT, checker.REGISTRY_UNKNOWN_REASON,
             checker.REGISTRY_BELOW_THRESHOLD, checker.FAILED_PREFIX, checker.NEVER_READ,
             checker.NO_PULL_EVENT, checker.PULL_POD_UNREAD, " is scheduled on it", " mounts it",
             " is the stronger cause",
             " workloads failing to pull from this host clear the threshold of 2"]
    for sentences in (checker.NODE_SENTENCES, checker.PVC_SENTENCES):
        fixed += [s for group in sentences.values() for s in group]
    for template in (checker._CONNECTION_SENTENCE, checker._AUTH_SENTENCE, checker._IMAGE_SENTENCE):
        fixed += [part for part in template.split("{}") if part]
    assert [s for s in fixed if s not in source] == []
    heartbeat = "(" + ", ".join(f'"{s}"' for s in checker.HEARTBEAT_REASONS) + ")"
    assert heartbeat in source


# --- the manifest ---------------------------------------------------------

def test_the_manifest_reports_the_checkers_counts():
    examples = generate.generate(SEED, 120)
    train, val = generate.split(examples, seed=SEED)
    test = generate.test_set()
    train, val = generate.drop_held_out(train, test), generate.drop_held_out(val, test)
    everything = train + val + test
    man = generate.manifest(SEED, 120, train, val, test)
    before = random.getstate()
    counts = checker.count_by_case(generate.to_row(ex) for ex in everything)
    assert random.getstate() == before
    assert man["checker_violations"] == counts
    assert set(counts) == {ex.case for ex in everything}
    assert set(counts.values()) == {0}
    assert list(counts) == sorted(counts)


# --- the shared-origin family (Spec 4b-1) ---------------------------------

def _so_row(key="node-not-ready", seed=1):
    return cases.shared_origin(stories.by_key()[key], random.Random(seed))


def _rule_fails(ex, user, rule):
    rep = checker.check(ex.system, user, ex.assistant, ex.meta)
    return [v for v in rep.violations if v.rule == rule]


def test_shared_origin_row_passes_every_rule():
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        ex = _so_row(key)
        rep = checker.check(ex.system, ex.user, ex.assistant, ex.meta)
        assert not rep.violations, (key, rep.violations)


def test_no_exemption_names_remain():
    for name in ("EXEMPT_CASES", "EVIDENCE_RULES", "PROPAGATION_TEXT_RULES"):
        assert not hasattr(checker, name)
    assert len(checker.RULES) == 51


def test_health_system_status_may_hold_spaces():
    for text in ("  system kube-system/backup Last run failed",
                 "  system kube-system/metrics-server 0/0 Scaled Down",
                 "  system kube-system/nightly BackoffLimitExceeded (3 of 3 failed)"):
        m = checker._HEALTH_SYSTEM.match(text)
        assert m, text
    m = checker._HEALTH_SYSTEM.match("  system kube-system/coredns 0/2 CrashLoopBackOff")
    assert m.group(2, 3, 4) == ("0", "2", "CrashLoopBackOff")


def _swap_first_two_node_lines(user, node):
    lines = user.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith(f"  node {node} ")]
    assert len(idx) >= 2
    lines[idx[0]], lines[idx[1]] = lines[idx[1]], lines[idx[0]]
    return "\n".join(lines) + "\n"


def test_b7_mutations():
    st = stories.by_key()["node-not-ready"]
    # The broken node gets a second line: PIDPressure prints before NotReady.
    pid = replace(st, broken=replace(st.broken, conditions=(
        health.Condition("PIDPressure", "True", "", ""), *st.broken.conditions)))
    ex = cases.shared_origin(pid, random.Random(1))
    node = ex.meta["scope_value"]
    assert not _rule_fails(ex, ex.user, "B7")
    # wrong order inside a node
    assert _rule_fails(ex, _swap_first_two_node_lines(ex.user, node), "B7")
    # a down line with no candidate
    extra = ex.user.replace(f"  node {node} NotReady",
                            f"  node worker-9 NotReady\n  node {node} NotReady", 1)
    assert _rule_fails(ex, extra, "B7")
    # a header total below the named nodes
    low = re.sub(r"— (\d+)/(\d+) nodes Ready", "— 0/0 nodes Ready", ex.user, count=1)
    assert _rule_fails(ex, low, "B7")
    # a header with no lines
    bare = "\n".join(ln for ln in ex.user.splitlines()
                     if not ln.startswith(("  node ", "  system "))) + "\n"
    assert _rule_fails(ex, bare, "B7")


# ------------------------------------------------ exam rebuild, item 7

def _golden_with(old: str, new: str) -> checker.Report:
    system, user, assistant, meta = _golden()
    assert old in user
    return checker.check(system, user.replace(old, new, 1), assistant, meta)


_SVC = "  - shop/api (NoReadyEndpoints): service has 0 ready endpoints\n"


@pytest.mark.parametrize("extra, fires", [
    ("  - zz/api (ClusterIP): no ready endpoints\n", False),
    ("  - aa/api (ClusterIP): no ready endpoints\n", True),            # out of order
    (_SVC, True),                                                       # duplicate key
    ("  - shop/api (LoadBalancer): no external address\n", False),      # NoExternalAddress after NoEndpoints
])
def test_b6_service_lines_sort_by_namespace_name_problem(extra, fires):
    rep = _golden_with(_SVC, _SVC + extra)
    assert ("B6" in _fired(rep)) is fires, _where(rep)


def test_b6_no_external_address_before_no_endpoints_fails():
    rep = _golden_with(_SVC, "  - shop/api (LoadBalancer): no external address\n" + _SVC)
    assert "B6" in _fired(rep), _where(rep)


_W1 = "  node worker-1 NotReady: KubeletNotReady — container runtime is down\n"


@pytest.mark.parametrize("tail, fires", [
    ("x " * 70, True),        # a 140-rune message with spaces
    ("y" * 121, False),       # 120 runes plus the cut mark fits
    ("y" * 122, True),
])
def test_f3_a_message_only_not_ready_line_is_cut_at_120_runes(tail, fires):
    rep = _golden_with(_W1, f"  node worker-1 NotReady: {tail.rstrip()}\n")
    assert ("F3" in _fired(rep)) is fires, _where(rep)


def test_f3_a_reason_keeps_the_512_cap():
    rep = _golden_with(_W1, "  node worker-1 NotReady: K" + "a" * 199 + "\n")
    assert "F3" not in _fired(rep), _where(rep)


@pytest.mark.parametrize("age, fires", [("0s", True), ("39s", True), ("40s", False),
                                        ("1m5s", False)])
def test_is15_a_lease_age_under_40s_fails(age, fires):
    """clusterhealth.go:137-144: a lease is stale only past 40s, so a
    younger age is never printed."""
    _s, user, _a, _m = _golden()
    assert _WORKER_2 in user
    fired, inspected = _is15(user.replace(
        _WORKER_2, f"  node worker-2 kubelet not heartbeating (lease {age} stale)\n", 1))
    assert inspected and fired is fires


def test_b7_extra_system_lines_at_the_gather_cap(monkeypatch):
    system, user, assistant, meta = _golden()
    entries = len(checker._context(system, user, assistant, meta).p.entries)
    sys_line = "  system kube-system/coredns 0/2 Degraded\n"

    def run(extra: str, patch: bool) -> bool:
        if patch:
            monkeypatch.setattr(checker, "MAX_GATHER_WORKLOADS", entries)
        else:
            # the golden has 10 entries, so a cap of 10 is "at the cap";
            # one more puts it below the cap, where an extra line is wrong
            monkeypatch.setattr(checker, "MAX_GATHER_WORKLOADS", entries + 1)
        rep = checker.check(system, user.replace(sys_line, sys_line + extra, 1), assistant, meta)
        return "B7" in _fired(rep)

    assert not run("  system kube-system/metrics-server 0/1 CrashLoopBackOff\n", True)
    assert run(sys_line, True)                                  # a rendered entry again
    assert run("  system kube-system/metrics-server\n", True)  # not a system line
    assert run("  system kube-system/metrics-server 0/1 CrashLoopBackOff\n", False)


def test_b4_policy_line_needs_only_probe_failures(exam_rows):
    for row in exam_rows:
        system, user, assistant, meta = _parts(row)
        if "    network policy: pods selected by" not in user:
            continue
        x = checker._context(system, user, assistant, meta)
        e = next(e for e in x.p.entries
                 if any(checker._sub_kind(s.text) == "N" for s in e.subs)
                 and not any(checker._sub_kind(s.text) == "M" for s in e.subs))
        probe = next(s.text for s in e.subs
                     if s.text.startswith(checker._ISSUE_PREFIX + "ProbeFailure"))
        broken = user.replace(probe, probe.replace("ProbeFailure", "RestartLoop", 1), 1)
        assert "B4" not in _fired(checker.check(system, user, assistant, meta))
        assert "B4" in _fired(checker.check(system, broken, assistant, meta))
        return
    pytest.fail("no exam row carries a network-policy line")


def test_ans2_does_not_count_a_ruled_out_candidate_line(exam_rows):
    for row in exam_rows:
        system, user, assistant, meta = _parts(row)
        x = checker._context(system, user, assistant, meta)
        for name, wm in meta["workloads"].items():
            b = x.block(name)
            if not wm["own_cause_keywords"] or b is None:
                continue
            for cd in b.cands:
                if cd.verdict != "ruled out" or user.lower().count(cd.cause.lower()) != 1:
                    continue
                m = copy.deepcopy(meta)
                m["workloads"][name]["own_cause_keywords"] = [cd.cause.lower()]
                assert "ANS-2" in _fired(checker.check(system, user, assistant, m))
                return
    pytest.fail("no exam row has a ruled-out candidate whose cause is unique in the prompt")
