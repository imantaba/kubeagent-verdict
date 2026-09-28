"""The checker: a finished row, read against what kubeagent v1.24.0 can send.

The checker is the net that keeps every row faithful to the gather. These
tests pin four things:

- the rows pass: the golden, the seed set and the exam pool, 0 violations;
- each rule catches something: one broken copy per rule, and no rule that
  never looks at anything;
- the exemptions stay exactly as ruled;
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
from pathlib import Path

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, checker, gather, generate, objects, render, rules

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
    "TXT-POD": (None, _replace("kubectl -n web describe pod <pod>",
                               "kubectl -n web describe pod frontend-5b8d7f6c9-q2w3e")),
    # the answer
    "ANS-1": (None, _set_verdict("app/api", "cause", "node worker-2 (no kubelet lease)")),
    "ANS-2": (_has_own_keywords, _add_keyword),
}


def test_every_rule_has_a_broken_copy():
    assert set(BROKEN) == set(checker.RULES)
    # 2026-09-26 (faithful prompts): TXT-POD checks the pod slot of a fix command 48 -> 49
    assert len(checker.RULES) == len(set(checker.RULES)) == 49


def _source(pick, seed_rows) -> tuple:
    if pick is None:
        return _golden()
    row = next(r for r in seed_rows
               if r["meta"]["case"] not in checker.EXEMPT_CASES and pick(r))
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
    row = next(r for r in seed_rows if r["meta"]["case"] not in checker.EXEMPT_CASES
               and _CRASH_FIX.search(r["messages"][1]["content"]))
    system, user, assistant, meta = _parts(row)
    report = checker.check(system, user, assistant, meta)
    assert report.inspected["TXT-IS17"] > 0
    assert "TXT-IS17" not in _fired(report)
    broken = _CRASH_FIX.sub(r"\g<1>sidecar\g<3>", user, count=1)
    assert broken != user
    assert "TXT-IS17" in _fired(checker.check(system, broken, assistant, meta))


def test_the_pod_slot_holds_the_placeholder_or_the_workloads_own_name():
    """TXT-POD reads every arm that has a name slot. kubeagent keeps a name
    only when the finding sits on the workload itself (explain.go:162-171):
    a RolloutStuck finding names the controller, and a bare pod is its own
    workload. Any other name there is one kubeagent masks."""
    system, user, assistant, meta = _golden()
    assert checker.check(system, user, assistant, meta).inspected["TXT-POD"] == 11
    fix, pod = "kubectl -n web describe pod <pod>", "frontend-5b8d7f6c9-q2w3e"
    for cmd in ("kubectl -n web get events --field-selector involvedObject.name=frontend",
                "kubectl -n web describe pod frontend",
                "kubectl -n web logs <pod> -c app --previous"):
        report = checker.check(system, user.replace(fix, cmd, 1), assistant, meta)
        assert "TXT-POD" not in _fired(report), cmd
    for cmd in (f"kubectl -n web get events --field-selector involvedObject.name={pod}",
                f"kubectl -n web logs {pod} -c app --previous",
                f"kubectl -n web logs job/{pod}",
                f"kubectl -n web describe cronjob {pod}",
                "kubectl -n web describe pod api"):
        report = checker.check(system, user.replace(fix, cmd, 1), assistant, meta)
        assert "TXT-POD" in _fired(report), cmd


# --- the exemptions -------------------------------------------------------

def test_the_exempt_cases_are_the_four_shared_origin_cases():
    assert checker.EXEMPT_CASES == frozenset({
        "shared_origin", "shared_origin_decoy", "shared_origin_probe", "shared_origin_decoy_probe"})


def test_the_evidence_rules_are_as_ruled():
    assert checker.EVIDENCE_RULES == frozenset({
        "E1", "E2-order", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E-min", "D3"})


def test_the_propagation_text_rules_are_as_ruled():
    assert checker.PROPAGATION_TEXT_RULES == frozenset({
        "B1", "C1-conf", "C1-cause", "C5/D4", "D1-onefresh", "TXT-IS9", "TXT-IS11"})


def test_the_healthy_read_exemption_is_as_ruled():
    assert checker.HEALTHY_READ_EXEMPT == frozenset({"E2-order", "E4", "E6", "E7", "E8", "E9", "E10"})


def test_each_propagation_text_rule_still_fires_with_the_exemption_off(seed_rows):
    """The second set holds only what propagation.py's own text fails today.

    Spec 4 rewrites propagation.py and removes both sets. Until then, a rule
    it fixes must leave the set: each rule here fires on at least one
    shared-origin row once the row stops being exempt. Nothing outside the
    two sets fires there, and the exempt rows skip exactly the two sets.
    """
    shared = [r for r in seed_rows if r["meta"]["case"] in checker.EXEMPT_CASES]
    assert shared
    fired: set[str] = set()
    for row in shared:
        system, user, assistant, meta = _parts(row)
        exempt = checker.check(system, user, assistant, meta)
        skipped = {rule for rule, n in exempt.inspected.items() if n == 0}
        assert checker.EVIDENCE_RULES | checker.PROPAGATION_TEXT_RULES <= skipped
        fired |= _fired(checker.check(system, user, assistant, {**meta, "case": "multi"}))
    assert checker.PROPAGATION_TEXT_RULES <= fired
    assert fired <= checker.EVIDENCE_RULES | checker.PROPAGATION_TEXT_RULES


_READ_BOUNDARY = re.compile(r"\n\n(?=== .* ==\n)")


def _healthy_row(seed_rows) -> dict:
    for row in seed_rows:
        label = row["meta"].get("origin_read_label")
        evidence = row["messages"][1]["content"].split("== BEGIN evidence ==\n", 1)[1]
        if row["meta"]["case"] == "multi" and label and evidence.startswith(f"== {label} ==\n"):
            return row
    raise AssertionError("no multi row with a healthy-origin read")


def test_a_healthy_origin_read_at_index_0_passes(seed_rows):
    assert _where(checker.check_row(_healthy_row(seed_rows))) == []


def test_a_label_off_by_one_character_is_caught(seed_rows):
    system, user, assistant, meta = _parts(_healthy_row(seed_rows))
    label = meta["origin_read_label"]
    meta = {**meta, "origin_read_label": label[:-1] + ("y" if label[-1] == "x" else "x")}
    fired = _fired(checker.check(system, user, assistant, meta))
    assert fired & checker.HEALTHY_READ_EXEMPT


def test_a_healthy_origin_read_at_index_1_is_caught(seed_rows):
    system, user, assistant, meta = _parts(_healthy_row(seed_rows))
    head, rest = user.split("== BEGIN evidence ==\n", 1)
    evidence, tail = rest.split("\n== END evidence ==", 1)
    reads = _READ_BOUNDARY.split(evidence)
    reads[0], reads[1] = reads[1], reads[0]
    user = head + "== BEGIN evidence ==\n" + "\n\n".join(reads) + "\n== END evidence ==" + tail
    fired = _fired(checker.check(system, user, assistant, meta))
    assert fired & checker.HEALTHY_READ_EXEMPT


def test_meta_none_skips_only_ans1s_meta_clause_and_ans2(seed_rows):
    row = next(r for r in seed_rows
               if r["meta"]["case"] not in checker.EXEMPT_CASES
               and not r["meta"].get("origin_read_label") and _has_own_keywords(r))
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
    "EXEMPT_CASES (test_generate)": (checker.EXEMPT_CASES,
                                     lambda: frozenset(_literal("test_generate.py", "_HEADER_EXEMPT"))),
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
