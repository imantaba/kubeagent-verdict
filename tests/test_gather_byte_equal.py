"""The gather, checked byte for byte against kubeagent.

Four YAML fixtures describe a cluster: `tests/fixtures/gather_fixture.yaml`,
`gather_fixture_logs.yaml`, `gather_fixture_cluster.yaml` and
`gather_fixture_registry.yaml`. A Go harness ran the real
kubeagent v1.24.0 code over each one and wrote eleven dumps per fixture, to
`tests/fixtures/gather_go/`, `gather_go_logs/`, `gather_go_cluster/` and
`gather_go_registry/`. The README in `gather_go/` is the dump format. This
test loads the same YAML, runs the Python port over it and writes the same
dumps, then compares them byte for byte. It needs no Go.

The split of work:

- The dataset code decides everything a dump shows: `gather.gather` (the
  scope, the reads, their order, the budget, the dedup, and what each
  candidate and finding got), `rules.decide` and `rules.shared`,
  `render.header_for`, `render.cluster_health`, and the contract renderers.
- This file only builds the input and formats the lines. The one rule it
  ports itself is `inventory.Prioritize`'s filter and sort
  (`_prioritize`), because nothing in `src/` orders a scan's workloads.
- It builds each finding's suggestion with `remediation.suggest_for`, the
  port of kubeagent's `suggestionFor` (internal/explain/explain.go:148-171),
  so the dumps check that the prompt names `<pod>` where kubeagent does.

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
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from kubeagent_verdict import contract as c
from kubeagent_verdict import remediation as rem
from kubeagent_verdict.dataset import cases, gather, health, render, rules
from kubeagent_verdict.dataset import objects as o

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN_PROMPT = ROOT / "contract" / "golden" / "user_message.txt"

MAIN = ("gather_fixture.yaml", "gather_go")
LOGS = ("gather_fixture_logs.yaml", "gather_go_logs")
CLUSTER = ("gather_fixture_cluster.yaml", "gather_go_cluster")
REGISTRY = ("gather_fixture_registry.yaml", "gather_go_registry")
FOLDERS = (MAIN, LOGS, CLUSTER, REGISTRY)
DUMPS = (
    "01-order.txt", "02-events.txt", "03-candidates.txt", "04-nodes.txt",
    "05-pvcs.txt", "06-logs.txt", "07-trail.txt", "08-bundle.txt",
    "09-decide.txt", "10-prompt.txt",
)

# --- Loading: yaml.safe_load, plus a check that refuses what it would let by.

_FRESH_KEYS = frozenset(f.name for f in dataclasses.fields(o.Fresh))
_LINE_KEYS = ("allocatable", "requests", "requests_pct", "limits", "limits_pct")
_FINDING_KEYS = ("pod", "issue", "reason", "evidence", "container", "image")
# The seven condition types kubeagent's own fixtures use: the kubelet's four and
# the node-problem-detector's three. Go ignores the three detector types.
_CONDITION_TYPES = ("MemoryPressure", "DiskPressure", "PIDPressure", "Ready",
                    "NetworkUnavailable", "ReadonlyFilesystem", "CorruptDockerOverlay2")
_LEASES = ("", "renewed", "missing", "no_renew")
_CONDITION_KEYS = ("type", "status", "reason", "message")
# The optional top-level lists the cluster capture mode reads, each a list of
# mappings with exactly these keys.
_LIST_KEYS = {
    "services": ("namespace", "name", "type", "selector", "annotations", "lb_ingress"),
    "endpoint_slices": ("namespace", "service", "ready"),
    "backends": ("namespace", "name", "kind", "labels", "desired"),
    "network_policies": ("namespace", "name", "pod_selector"),
}
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
                 "nodes", "pvcs", "workloads"), tuple(_LIST_KEYS))
    _keys("kubeagent", doc["kubeagent"], ("tag", "commit"))
    summary = _keys("summary", doc["summary"], ("cpu", "memory", "metrics_available"))
    for part in ("cpu", "memory"):
        _keys(f"summary.{part}", summary[part], _LINE_KEYS, ("usage", "usage_pct"))
    for i, s in enumerate(doc["service_issues"]):
        _keys(f"service_issues[{i}]", s, ("namespace", "name", "type", "detail"))
    for i, n in enumerate(doc["nodes"]):
        _keys(f"nodes[{i}]", n, ("name", "scan_reason", "fresh"),
              ("conditions", "unschedulable", "lease", "lease_age_ms"))
        _keys(f"nodes[{i}].fresh", n["fresh"], (), _FRESH_KEYS)
        for j, cond in enumerate(n.get("conditions", ())):
            _keys(f"nodes[{i}].conditions[{j}]", cond, _CONDITION_KEYS)
            if cond["type"] not in _CONDITION_TYPES:
                raise ValueError(f"nodes[{i}].conditions[{j}]: type {cond['type']!r} is not one of "
                                 f"{list(_CONDITION_TYPES)}")
        if n.get("lease", "") not in _LEASES:
            raise ValueError(f"nodes[{i}]: lease {n['lease']!r} is not one of {list(_LEASES)}")
    for i, p in enumerate(doc["pvcs"]):
        _keys(f"pvcs[{i}]", p, ("namespace", "name", "scan_reason", "fresh"))
        _keys(f"pvcs[{i}].fresh", p["fresh"], (), _FRESH_KEYS)
    for i, w in enumerate(doc["workloads"]):
        where = f"workloads[{i}]"
        _keys(where, w, _WORKLOAD_KEYS)
        for j, pod in enumerate(w["pods"]):
            _keys(f"{where}.pods[{j}]", pod, ("name", "node", "claims"), ("labels", "ready"))
        for j, f in enumerate(w["findings"]):
            # log_refused only tells the Go harness to refuse the read;
            # log_read already holds the text the refusal makes.
            _keys(f"{where}.findings[{j}]", f, _FINDING_KEYS, ("log", "log_read", "log_refused"))
        for j, d in enumerate(w["decoy_events"]):
            _keys(f"{where}.decoy_events[{j}]", d, ("object", "events"))
    for name, keys in _LIST_KEYS.items():
        for i, item in enumerate(doc.get(name, ())):
            _keys(f"{name}[{i}]", item, keys)
    return doc


def test_the_loader_refuses_a_duplicate_key():
    text = (FIXTURES / MAIN[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key 'tag'"):
        load_fixture(text.replace('  tag: "v1.24.0"\n', '  tag: "v1.24.0"\n  tag: "v1.23.0"\n', 1))


def test_the_loader_refuses_an_unknown_key():
    text = (FIXTURES / MAIN[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown keys \['log_reed'\]"):
        load_fixture(text.replace("log_read:", "log_reed:", 1))


def test_the_loader_refuses_an_unknown_condition_type():
    text = (FIXTURES / CLUSTER[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="type 'MemoryPressur' is not one of"):
        load_fixture(text.replace('type: "MemoryPressure"', 'type: "MemoryPressur"', 1))


def test_the_loader_refuses_a_bad_lease():
    text = (FIXTURES / CLUSTER[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="lease 'stale' is not one of"):
        load_fixture(text.replace('lease: "missing"', 'lease: "stale"', 1))


def test_the_loader_refuses_an_unknown_key_in_a_service():
    text = (FIXTURES / CLUSTER[0]).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown keys \['lb_ingres'\]"):
        load_fixture(text.replace("lb_ingress: false}", "lb_ingres: false, lb_ingress: false}", 1))


# --- The input: what kubeagent's scan hands the gather.

_PROBLEM, _RESTART, _CRON = 2, 3, 4  # inventory/inventory.go:587-591


def _suggested(f: dict, w: dict) -> rem.Suggestion:
    """The suggestion the prompt carries, from the finding's own pod and the
    workload it hangs off (explain.go:148-171)."""
    ns, pod = f["pod"].split("/", 1)
    assert ns == w["namespace"], f["pod"]
    return rem.suggest_for(f["issue"], ns=ns, pod=pod, container=f["container"],
                           workload=w["name"])


def _prompt_findings(w: dict) -> tuple[c.Finding, ...]:
    out = []
    for f in w["findings"]:
        sug = _suggested(f, w)
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
    cluster: c.ClusterHealth | None
    prompt: str


def _cluster_mode(doc: dict) -> bool:
    """The CLUSTER fixture spells out node conditions. The Python port then
    computes the health block, the service issues and the network-policy
    lines from the fixture's objects, the way kubeagent's scan does."""
    return any("conditions" in n for n in doc["nodes"])


def _labels(d: dict | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((d or {}).items()))


def _health_nodes(doc: dict) -> tuple[health.Node, ...]:
    return tuple(health.Node(n["name"], tuple(health.Condition(**x) for x in n["conditions"]),
                             unschedulable=n.get("unschedulable", False), lease=n["lease"],
                             lease_age_ms=n.get("lease_age_ms", 0))
                 for n in doc["nodes"])


def _health_pods(w: dict) -> tuple[health.Pod, ...]:
    return tuple(health.Pod(w["namespace"], p["name"], p["node"], _labels(p.get("labels")),
                            p.get("ready", False)) for p in w["pods"])


def _cluster_services(doc: dict, down: tuple[health.DownNode, ...]) -> tuple[c.ServiceIssue, ...]:
    services = tuple(health.Service(s["namespace"], s["name"], s["type"], _labels(s["selector"]),
                                    _labels(s["annotations"]), s["lb_ingress"])
                     for s in doc.get("services", []))
    slices = tuple(health.EndpointSlice(s["namespace"], s["service"], tuple(s["ready"]))
                   for s in doc.get("endpoint_slices", []))
    backends = tuple(health.Backend(b["namespace"], b["kind"], _labels(b["labels"]), b["desired"])
                     for b in doc.get("backends", []))
    pods = tuple(p for w in doc["workloads"] for p in _health_pods(w))
    issues = health.service_issues(services, slices, backends)
    return tuple(i.contract() for i in health.annotate_endpoint_cause(issues, services, pods, down))


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
    if _cluster_mode(doc):
        cluster, down = health.assess(_health_nodes(doc),
                                      [_prompt_workload(w) for w in doc["workloads"]])
        assert [(d.name, d.reason) for d in down] == \
            [(n["name"], n["scan_reason"]) for n in doc["nodes"] if n["scan_reason"]]
        policies = tuple(health.NetworkPolicy(p["namespace"], p["name"], _labels(p["pod_selector"]))
                         for p in doc.get("network_policies", []))
        workloads = [dataclasses.replace(pw, network_policies=health.network_policies_for(
                         pw, _health_pods(w), policies))
                     for pw, (_, w) in zip(workloads, shown)]
        services = _cluster_services(doc, down)
        prompt = c.build_user_message(cluster, summary, doc["platform_line"], services,
                                      tuple(workloads), result.reads)
        render.check_prompt_size(prompt, entry_or_scenario_key=fixture)
    else:
        cluster = render.cluster_health(tuple(workloads), result.reads)
        services = tuple(c.ServiceIssue(**x) for x in doc["service_issues"])
        prompt = cases._user_message(summary, doc["platform_line"], services, tuple(workloads),
                                     result.reads, key=fixture)
    return Run(doc, tuple(shown), hidden_restarts, hidden_cron, tuple(dropped), gathered,
               result, tuple(workloads), cluster, prompt)


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
    block = r.cluster
    if block is None:
        # Python models no counts for a Healthy cluster: it prints no block.
        # Every fixture node is Ready then.
        total = len(r.doc["nodes"])
        out = [_rec("cluster", "Healthy", total, total)]
    else:
        out = [_rec("cluster", "Degraded" if block.degraded else "Healthy",
                    block.nodes_ready, block.nodes_total)]
        out += [_rec("node_issue", x) for x in block.node_issues]
        out += [_rec("system_issue", x) for x in block.system_issues]
    out += [_rec("shared", line) for line in rules.shared(r.result.results)]
    out.append(_block("prompt", r.prompt))
    return "".join(out)


_DUMPERS = dict(zip(DUMPS, (dump_order, dump_events, dump_candidates, dump_nodes, dump_pvcs,
                            dump_logs, dump_trail, dump_bundle, dump_decide, dump_prompt)))


@pytest.mark.parametrize("fixture, folder", FOLDERS)
def test_dump0_is_the_fixture_as_python_loads_it(fixture, folder):
    got = load_fixture((FIXTURES / fixture).read_text(encoding="utf-8"))
    want = json.loads((FIXTURES / folder / "00-fixture.json").read_text(encoding="utf-8"))
    assert got == want


@pytest.mark.parametrize("dump", DUMPS)
@pytest.mark.parametrize("fixture, folder", FOLDERS)
def test_the_dump_matches_kubeagent_byte_for_byte(fixture, folder, dump):
    want = (FIXTURES / folder / dump).read_bytes()
    got = _DUMPERS[dump](run(fixture)).encode("utf-8")
    assert got.decode("utf-8") == want.decode("utf-8")
    assert got == want


def test_the_main_prompt_is_the_golden_user_message():
    assert run(MAIN[0]).prompt.encode("utf-8") == GOLDEN_PROMPT.read_bytes()


def test_every_capture_folder_is_checked():
    """A gather_go* folder no test reads would be a capture nobody checks."""
    on_disk = {p.name for p in FIXTURES.iterdir() if p.is_dir() and p.name.startswith("gather_go")}
    assert on_disk == {folder for _, folder in FOLDERS}


def test_the_old_dumps_are_unchanged():
    """The 22 old dump files are the v1.24.0 main and logs captures. The new
    modes must not move a byte of them."""
    want = {  # sha256 of each file, taken from git before the new modes were added
        "gather_go/00-fixture.json": "ab3a26896f3ad954ebf19cd96de70c632342e35b539517be54addaccb2f2e1bd",
        "gather_go/01-order.txt": "dad23d8f17434db82d5c8ce7cdc583fdaf338ed710ee88c22f32a88a16208dd0",
        "gather_go/02-events.txt": "567226efbc46746ad729f11661fc4aa7532e56cab4d97e7c9db4b3d4b2ac660f",
        "gather_go/03-candidates.txt": "a942ca6bed65403d243dfcf6eed3aa20932c40a5bef20bebd8e11a07b03693fe",
        "gather_go/04-nodes.txt": "60de777bcade7797f9839716e8348fcfcfb599e75b62f8897aecc9008f1f5790",
        "gather_go/05-pvcs.txt": "7fb93736bbf51aeda3a66545a2b4b187ed33eac7a4880a5939d1cb9f58319646",
        "gather_go/06-logs.txt": "f810d6c5c704150292a2ce18db6b6bf16f940dcc5b5c1216082310c79e3489ab",
        "gather_go/07-trail.txt": "4d077d4f247fc753d9485d93c7012b4883268ccdefd24fc5c1688da338bd6439",
        "gather_go/08-bundle.txt": "81b04efe627ef6ca718bbcea1e2b395007c8221a6cbb33f5f996752e720c4338",
        "gather_go/09-decide.txt": "905daa030dce3a906cbead5830c3f062101a51e68033a698713786ddaa6cb447",
        "gather_go/10-prompt.txt": "ebe206866fbffc334af7fb194c7187b4b4048ac78b1d876b4501b2049f3ab89f",
        "gather_go_logs/00-fixture.json": "890c82502f4c4aaadf0029e802828cc365bf7d8ed74c64420617ca01f85eef56",
        "gather_go_logs/01-order.txt": "32d2e308c7a5cf9e409feca5eed1a19054b023b23b03d9b1ccbf256e0200bfe5",
        "gather_go_logs/02-events.txt": "075405e3576b4d31981c7fe3e1114c96cfdcf53ea4321c944d2faad5917287ce",
        "gather_go_logs/03-candidates.txt": "5e86be8ab6cd26e51456144dc4cf46a0a70e5c2f9ef89882f33cb9471fab0b01",
        "gather_go_logs/04-nodes.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "gather_go_logs/05-pvcs.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "gather_go_logs/06-logs.txt": "0b8c38ecb210e62a09947795ffaa4f7b3697dfacf24182b9f0154d06d91ae7da",
        "gather_go_logs/07-trail.txt": "d6f5ac89a239d3d78de0ffb959d140090dbff4707169739592f54df7db049969",
        "gather_go_logs/08-bundle.txt": "e8e0ae71e7076c8834e59f852232d5c94d29b9fa11352f71cc2e557b5d8ab33d",
        "gather_go_logs/09-decide.txt": "a552ca5476546e4a8f0640ad53b0818dbd9e1c29700293ecdca00fc1008b5f42",
        "gather_go_logs/10-prompt.txt": "2f4d8036ba00ba36868937b241fafa805ec93da87b5405d4c4007fe338867f05",
    }
    got = {f"{folder}/{name}": hashlib.sha256((FIXTURES / folder / name).read_bytes()).hexdigest()
           for _, folder in (MAIN, LOGS) for name in ("00-fixture.json", *DUMPS)}
    assert got == want
