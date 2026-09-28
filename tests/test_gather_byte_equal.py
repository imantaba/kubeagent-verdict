"""The gather, checked byte for byte against kubeagent.

Two YAML fixtures describe a cluster: `tests/fixtures/gather_fixture.yaml`
and `tests/fixtures/gather_fixture_logs.yaml`. A Go harness ran the real
kubeagent v1.24.0 code over each one and wrote eleven dumps per fixture, to
`tests/fixtures/gather_go/` and `tests/fixtures/gather_go_logs/`. That
folder's README is the dump format. This test loads the same YAML, runs the
Python port over it and writes the same dumps, then compares them byte for
byte. It needs no Go.

The split of work:

- The dataset code decides everything a dump shows: `gather.gather` (the
  scope, the reads, their order, the budget, the dedup, and what each
  candidate and finding got), `rules.decide` and `rules.shared`,
  `render.header_for`, `render.cluster_health`, and the contract renderers.
- This file only builds the input and formats the lines. The one rule it
  ports itself is `inventory.Prioritize`'s filter and sort
  (`_prioritize`), because nothing in `src/` orders a scan's workloads.
- It builds each finding's suggestion with the pod named `<pod>`, as
  kubeagent's prompt does (`suggestionFor`, internal/explain/explain.go:162-171).

Log classification happens on the Go side only. A finding's `log_read` is
the body kubeagent made of its log text, and Python copies it as it is. So
this test covers the log reads' labels, order, budget, dedup and cap, not
the classifier.

The main fixture's prompt is also the golden prompt:
`contract/golden/user_message.txt`.
"""

from __future__ import annotations

import dataclasses
import functools
import json
from pathlib import Path

import pytest
import yaml

from kubeagent_verdict import contract as c
from kubeagent_verdict import remediation as rem
from kubeagent_verdict.dataset import cases, gather, render, rules
from kubeagent_verdict.dataset import objects as o

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN_PROMPT = ROOT / "contract" / "golden" / "user_message.txt"

MAIN = ("gather_fixture.yaml", "gather_go")
LOGS = ("gather_fixture_logs.yaml", "gather_go_logs")
DUMPS = (
    "01-order.txt", "02-events.txt", "03-candidates.txt", "04-nodes.txt",
    "05-pvcs.txt", "06-logs.txt", "07-trail.txt", "08-bundle.txt",
    "09-decide.txt", "10-prompt.txt",
)

# --- Loading: yaml.safe_load, plus a check that refuses what it would let by.

_FRESH_KEYS = frozenset(f.name for f in dataclasses.fields(o.Fresh))
_LINE_KEYS = ("allocatable", "requests", "requests_pct", "limits", "limits_pct")
_FINDING_KEYS = ("pod", "issue", "reason", "evidence", "container", "image")
_WORKLOAD_KEYS = ("namespace", "name", "kind", "ready", "desired", "status", "restarts",
                  "pod", "pods", "findings", "events", "events_failed", "decoy_events")


def _no_duplicate_keys(node: yaml.Node, where: str = "fixture") -> None:
    """`yaml.safe_load` keeps the last of two equal keys without a word. Go's
    loader may not, so a duplicate key would make the two sides read two
    different files."""
    if isinstance(node, yaml.MappingNode):
        seen = set()
        for key, value in node.value:
            if key.value in seen:
                raise ValueError(f"{where}: duplicate key {key.value!r}")
            seen.add(key.value)
            _no_duplicate_keys(value, f"{where}.{key.value}")
    elif isinstance(node, yaml.SequenceNode):
        for i, item in enumerate(node.value):
            _no_duplicate_keys(item, f"{where}[{i}]")


def _keys(where: str, value: object, required, optional=()) -> dict:
    """Refuse a mapping with a key missing or a key nobody reads."""
    if not isinstance(value, dict):
        raise TypeError(f"{where}: want a mapping, got {type(value).__name__}")
    missing = set(required) - set(value)
    unknown = set(value) - set(required) - set(optional)
    if missing:
        raise ValueError(f"{where}: missing keys {sorted(missing)}")
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
    return value


def load_fixture(text: str) -> dict:
    """Load a gather fixture with `yaml.safe_load`, refusing duplicate and
    unknown keys. The header of `tests/fixtures/gather_fixture.yaml` names
    every key."""
    _no_duplicate_keys(yaml.compose(text, Loader=yaml.SafeLoader))
    doc = _keys("fixture", yaml.safe_load(text),
                ("kubeagent", "summary", "platform_line", "service_issues",
                 "nodes", "pvcs", "workloads"))
    _keys("kubeagent", doc["kubeagent"], ("tag", "commit"))
    summary = _keys("summary", doc["summary"], ("cpu", "memory", "metrics_available"))
    for part in ("cpu", "memory"):
        _keys(f"summary.{part}", summary[part], _LINE_KEYS, ("usage", "usage_pct"))
    for i, s in enumerate(doc["service_issues"]):
        _keys(f"service_issues[{i}]", s, ("namespace", "name", "type", "detail"))
    for i, n in enumerate(doc["nodes"]):
        _keys(f"nodes[{i}]", n, ("name", "scan_reason", "fresh"))
        _keys(f"nodes[{i}].fresh", n["fresh"], (), _FRESH_KEYS)
    for i, p in enumerate(doc["pvcs"]):
        _keys(f"pvcs[{i}]", p, ("namespace", "name", "scan_reason", "fresh"))
        _keys(f"pvcs[{i}].fresh", p["fresh"], (), _FRESH_KEYS)
    for i, w in enumerate(doc["workloads"]):
        where = f"workloads[{i}]"
        _keys(where, w, _WORKLOAD_KEYS)
        for j, pod in enumerate(w["pods"]):
            _keys(f"{where}.pods[{j}]", pod, ("name", "node", "claims"))
        for j, f in enumerate(w["findings"]):
            # log_refused only tells the Go harness to refuse the read;
            # log_read already holds the text the refusal makes.
            _keys(f"{where}.findings[{j}]", f, _FINDING_KEYS, ("log", "log_read", "log_refused"))
        for j, d in enumerate(w["decoy_events"]):
            _keys(f"{where}.decoy_events[{j}]", d, ("object", "events"))
    return doc


def test_the_loader_refuses_a_duplicate_key():
    text = (FIXTURES / MAIN[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key 'tag'"):
        load_fixture(text.replace('  tag: "v1.24.0"\n', '  tag: "v1.24.0"\n  tag: "v1.23.0"\n', 1))


def test_the_loader_refuses_an_unknown_key():
    text = (FIXTURES / MAIN[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown keys \['log_reed'\]"):
        load_fixture(text.replace("log_read:", "log_reed:", 1))


# --- The input: what kubeagent's scan hands the gather.

_PROBLEM, _RESTART, _CRON = 2, 3, 4  # inventory/inventory.go:587-591


def _suggested(issue: str, ns: str, container: str) -> rem.Suggestion:
    """The suggestion the prompt carries. The pod is `<pod>`: every fixture
    finding names a pod, not the workload itself (explain.go:162-171)."""
    return rem.suggest(issue, ns=ns, pod="<pod>", container=container)


def _prompt_findings(w: dict) -> tuple[c.Finding, ...]:
    out = []
    for f in w["findings"]:
        sug = _suggested(f["issue"], w["namespace"], f["container"])
        out.append(c.Finding(f["issue"], f["reason"], f["evidence"], sug.next_step, sug.command))
    return tuple(out)


def _prompt_workload(w: dict, **decided) -> c.Workload:
    return c.Workload(w["namespace"], w["name"], w["kind"], w["ready"], w["desired"],
                      w["status"], w["restarts"], _prompt_findings(w), **decided)


def _prioritize(workloads: list[dict]) -> tuple[list[tuple[int, dict]], int, int, list[dict]]:
    """`inventory.Prioritize` with the scan's default options, which show
    neither restart-only workloads nor quiet CronJobs
    (internal/inventory/inventory.go:598-647).

    Returns the shown workloads with their priority, in report order (sorted
    by priority, namespace, name, kind), the two hidden counts, and the
    workloads it drops. Whether a workload is flagged is
    `render._flagged`, the port of `Workload.Flagged`.
    """
    shown, hidden_restarts, hidden_cron, dropped = [], 0, 0, []
    for w in workloads:
        flagged = render._flagged(_prompt_workload(w))
        if w["kind"] == "CronJob":
            if flagged:
                shown.append((_PROBLEM, w))
            else:
                hidden_cron += 1
                dropped.append(w)
        elif flagged:
            shown.append((_PROBLEM, w))
        else:
            if w["restarts"] > 0:
                hidden_restarts += 1
            dropped.append(w)
    shown.sort(key=lambda pw: (pw[0], pw[1]["namespace"], pw[1]["name"], pw[1]["kind"]))
    dropped.sort(key=lambda w: (w["namespace"], w["name"], w["kind"]))
    return shown, hidden_restarts, hidden_cron, dropped


def _fresh(d: dict) -> o.Fresh:
    d = dict(d)
    if "taints" in d:
        d["taints"] = tuple(tuple(t) for t in d["taints"])
    return o.Fresh(**d)


def _gather_workload(w: dict, doc: dict) -> gather.GatherWorkload:
    """One shown workload, as `gather()` takes it.

    - Every down node is a candidate object: `on` when one of the
      workload's pods is scheduled on it (rootcause.go:36-44).
    - Every broken PVC in the workload's namespace is one: `mounted` when
      one of its pods claims it.
    - A workload with a pull finding gets one registry, named for the first
      pull finding's host. The gather counts its group.
    - Its issue is the first pull finding's issue when it has one
      (`pullImage` takes a pull finding in any position), else the first
      finding's.
    """
    on = {p["node"] for p in w["pods"]}
    claims = {claim for p in w["pods"] for claim in p["claims"]}
    objects = [o.Object("node", n["name"], n["scan_reason"],
                        "on" if n["name"] in on else "off", _fresh(n["fresh"]))
               for n in doc["nodes"] if n["scan_reason"]]
    objects += [o.Object("pvc", p["name"], p["scan_reason"],
                         "mounted" if p["name"] in claims else "unmounted", _fresh(p["fresh"]))
                for p in doc["pvcs"] if p["namespace"] == w["namespace"]]
    pulls = [f for f in w["findings"] if f["issue"] in rules.REGISTRY_ISSUES]
    if pulls:
        host = gather._registry_host(pulls[0]["image"]) if pulls[0]["image"] else ""
        objects.append(o.Object("registry", host, "{count}", "", o.Fresh()))
    issue = pulls[0]["issue"] if pulls else (w["findings"][0]["issue"] if w["findings"] else "")
    return gather.GatherWorkload(
        namespace=w["namespace"], name=w["name"], pod=w["pod"], issue=issue,
        objects=tuple(objects),
        events=tuple((r, m, n) for r, m, n in w["events"]),
        findings=tuple(gather.GatherFinding(f["issue"], f["pod"], f["container"],
                                            f.get("log_read"), f["image"])
                       for f in w["findings"]),
        events_failed=w["events_failed"])


@dataclasses.dataclass(frozen=True)
class Run:
    """One fixture, run through the Python port."""

    doc: dict
    shown: tuple[tuple[int, dict], ...]
    hidden_restarts: int
    hidden_cron: int
    dropped: tuple[dict, ...]
    gathered: tuple[gather.GatherWorkload, ...]  # every shown workload, in report order
    result: gather.GatherResult
    workloads: tuple[c.Workload, ...]  # the scoped workloads, as the prompt prints them
    prompt: str


@functools.cache
def run(fixture: str) -> Run:
    doc = load_fixture((FIXTURES / fixture).read_text(encoding="utf-8"))
    shown, hidden_restarts, hidden_cron, dropped = _prioritize(doc["workloads"])
    gathered = tuple(_gather_workload(w, doc) for _, w in shown)
    result = gather.gather(gathered)
    workloads = []
    for (_, w), cands, res in zip(shown, result.candidates, result.results):
        workloads.append(_prompt_workload(
            w, candidates=cands, confidence=render.header_for(cands), decided=res.decided,
            decided_cause=res.cause, decided_outcome=res.outcome))
    s = doc["summary"]
    summary = c.ResourceSummary(c.ResourceLine(**s["cpu"]), c.ResourceLine(**s["memory"]),
                                s["metrics_available"])
    services = tuple(c.ServiceIssue(**x) for x in doc["service_issues"])
    prompt = cases._user_message(summary, doc["platform_line"], services, tuple(workloads),
                                 result.reads, key=fixture)
    return Run(doc, tuple(shown), hidden_restarts, hidden_cron, tuple(dropped), gathered,
               result, tuple(workloads), prompt)


# --- The dumps. Formatting only: every value comes from `run()`.

def _rec(*fields: object) -> str:
    out = []
    for f in fields:
        s = ("true" if f else "false") if isinstance(f, bool) else str(f)
        if any(ch in s for ch in "\t\n\r"):
            raise ValueError(f"field {s!r} holds a tab or a line break")
        out.append(s)
    return "\t".join(out) + "\n"


def _block(name: str, value: str) -> str:
    return f"block\t{name}\t{len(value.encode('utf-8'))}\n{value}\n"


def _content(read: c.EvidenceRead) -> str:
    """A read's section body, as the bundle holds it (gather.go:163-169)."""
    return _block("content", c.cap_content(read.content).rstrip("\n"))


def _ref(step: gather.Step) -> str:
    return str(step.ref) if step.ref else ""


def _kind_object(cause: str) -> tuple[str, str]:
    """The kind and object a cause names: `node X (...)`, `PVC X (...)` or
    `registry X ...`."""
    word, _, rest = cause.partition(" ")
    return {"node": "node", "PVC": "pvc", "registry": "registry"}[word], rest.split(" ")[0]


_FAILED = "read failed: "
_EVENTS = "events "
_NODE = "describe node /"
_PVC = "describe pvc "


def _events_by_key(r: Run) -> dict[str, gather.GatherWorkload]:
    """The scoped workloads by the `<namespace>/<pod>` their events read names."""
    out = {}
    for read in r.result.reads:
        if read.label.startswith(_EVENTS):
            key = read.label[len(_EVENTS):]
            ns = key.partition("/")[0]
            # The k-th events read is the k-th scoped workload's.
            out[key] = r.gathered[len(out)]
            assert out[key].namespace == ns
    return out


def dump_order(r: Run) -> str:
    scoped = len(r.result.results)
    out = [_rec("row", i, w["namespace"], w["name"], w["kind"], prio,
                "scoped" if i <= scoped else "unscoped")
           for i, (prio, w) in enumerate(r.shown, 1)]
    out.append(_rec("hidden_restarts", r.hidden_restarts))
    out.append(_rec("hidden_cron", r.hidden_cron))
    out += [_rec("dropped", w["namespace"], w["name"], w["kind"]) for w in r.dropped]
    return "".join(out)


def dump_events(r: Run) -> str:
    by_key = _events_by_key(r)
    out = []
    for i, read in enumerate(r.result.reads, 1):
        if not read.label.startswith(_EVENTS):
            continue
        key = read.label[len(_EVENTS):]
        ns, _, pod = key.partition("/")
        w = by_key[key]
        if w.events_failed:
            out.append(_rec("events", i, ns, pod, "failed", "", gather.safetext_line(w.events_failed)))
        else:
            out.append(_rec("events", i, ns, pod, "ok", len(w.events), ""))
        out += [_rec("event", reason, message, count) for reason, message, count in w.events]
        out.append(_content(read))
    return "".join(out)


def dump_candidates(r: Run) -> str:
    out = [_rec("down", n["name"], n["scan_reason"])
           for n in sorted(r.doc["nodes"], key=lambda n: n["name"]) if n["scan_reason"]]
    for i, (w, cands, steps) in enumerate(zip(r.gathered, r.result.candidates,
                                              r.result.candidate_steps), 1):
        attributed = [cd.cause for cd in cands if cd.verdict == "attributed"]
        out.append(_rec("workload", i, w.namespace, w.name,
                        attributed[0] if attributed else "", render.header_for(cands)))
        for cd, step in zip(cands, steps, strict=True):
            kind, obj = _kind_object(cd.cause)
            out.append(_rec("candidate", kind, obj, cd.verdict, step.action, _ref(step),
                            cd.cause, cd.reason))
    return "".join(out)


def _describe(r: Run, prefix: str, record: str) -> str:
    out = []
    for i, read in enumerate(r.result.reads, 1):
        if not read.label.startswith(prefix):
            continue
        where = read.label[len(prefix):].split("/") if record == "pvc" else [read.label[len(prefix):]]
        if read.content.startswith(_FAILED):
            out.append(_rec(record, i, *where, "failed", read.content[len(_FAILED):]))
        else:
            out.append(_rec(record, i, *where, "ok", ""))
        out.append(_content(read))
    return "".join(out)


def dump_nodes(r: Run) -> str:
    return _describe(r, _NODE, "node")


def dump_pvcs(r: Run) -> str:
    return _describe(r, _PVC, "pvc")


def dump_logs(r: Run) -> str:
    out = []
    for i, (w, steps) in enumerate(zip(r.gathered, r.result.finding_steps), 1):
        for f, step in zip(w.findings, steps, strict=True):
            out.append(_rec("log", i, w.namespace, gather._pod_part(f.pod), f.container,
                            f.issue, step.action, _ref(step)))
            if step.action == "read":
                out.append(_content(r.result.reads[step.ref - 1]))
    return "".join(out)


def dump_trail(r: Run) -> str:
    return "".join(_rec(i, read.label) for i, read in enumerate(r.result.reads, 1))


def dump_bundle(r: Run) -> str:
    return _block("bundle", c.render_evidence(r.result.reads))


def dump_decide(r: Run) -> str:
    by_key = _events_by_key(r)
    nodes, pvcs, events, failed = [], [], [], []
    for read in r.result.reads:
        label, content = read.label, read.content
        if label.startswith(_NODE):
            name = label[len(_NODE):]
            if content.startswith(_FAILED):
                failed.append(("node/" + name, content[len(_FAILED):]))
            else:
                nodes.append(name)
        elif label.startswith(_PVC):
            key = label[len(_PVC):]
            if content.startswith(_FAILED):
                failed.append(("pvc/" + key, content[len(_FAILED):]))
            else:
                pvcs.append(key)
        elif label.startswith(_EVENTS):
            key = label[len(_EVENTS):]
            w = by_key[key]
            if w.events_failed:
                failed.append(("events/" + key, gather.safetext_line(w.events_failed)))
            else:
                events.append((key, len(w.events)))
    out = [_rec("read_node", k) for k in sorted(nodes)]
    out += [_rec("read_pvc", k) for k in sorted(pvcs)]
    out += [_rec("read_events", k, n) for k, n in sorted(events)]
    out += [_rec("failed", k, m) for k, m in sorted(failed)]
    for i, (w, res) in enumerate(zip(r.gathered, r.result.results), 1):
        out.append(_rec("result", i, f"{w.namespace}/{w.name}", res.decided, res.outcome,
                        res.cause, res.evidence, res.group_key, res.group_text))
        for d in res.decisions:
            out.append(_rec("decision", *_kind_object(d.candidate), d.outcome, d.candidate,
                            d.evidence))
    return "".join(out)


def dump_prompt(r: Run) -> str:
    health = render.cluster_health(r.workloads, r.result.reads)
    if health is None:
        # Python models no counts for a Healthy cluster: it prints no block.
        # Every fixture node is Ready then.
        total = len(r.doc["nodes"])
        out = [_rec("cluster", "Healthy", total, total)]
    else:
        out = [_rec("cluster", "Degraded" if health.degraded else "Healthy",
                    health.nodes_ready, health.nodes_total)]
        out += [_rec("node_issue", x) for x in health.node_issues]
        out += [_rec("system_issue", x) for x in health.system_issues]
    out += [_rec("shared", line) for line in rules.shared(r.result.results)]
    out.append(_block("prompt", r.prompt))
    return "".join(out)


_DUMPERS = dict(zip(DUMPS, (dump_order, dump_events, dump_candidates, dump_nodes, dump_pvcs,
                            dump_logs, dump_trail, dump_bundle, dump_decide, dump_prompt)))


@pytest.mark.parametrize("fixture, folder", [MAIN, LOGS])
def test_dump0_is_the_fixture_as_python_loads_it(fixture, folder):
    got = load_fixture((FIXTURES / fixture).read_text(encoding="utf-8"))
    want = json.loads((FIXTURES / folder / "00-fixture.json").read_text(encoding="utf-8"))
    assert got == want


@pytest.mark.parametrize("dump", DUMPS)
@pytest.mark.parametrize("fixture, folder", [MAIN, LOGS])
def test_the_dump_matches_kubeagent_byte_for_byte(fixture, folder, dump):
    want = (FIXTURES / folder / dump).read_bytes()
    got = _DUMPERS[dump](run(fixture)).encode("utf-8")
    assert got.decode("utf-8") == want.decode("utf-8")
    assert got == want


def test_the_main_prompt_is_the_golden_user_message():
    assert run(MAIN[0]).prompt.encode("utf-8") == GOLDEN_PROMPT.read_bytes()
