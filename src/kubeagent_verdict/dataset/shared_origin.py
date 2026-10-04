"""One shared-origin world through kubeagent's real pipeline (Spec 4b-1 §5).

`draw` makes every rng call for a pair; `build` runs one world with no rng:
report order → one gather → the rules over every candidate → the prompt.
This module never imports `cases` or `generate` (Ruling 26).
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import NamedTuple

from kubeagent_verdict import contract as c
from kubeagent_verdict import remediation as rem
from kubeagent_verdict.dataset import gather, health, objects, render, rules, stories
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset.checker import LOG_CAUSE_PREFIX, LOG_NO_CLASSIFIABLE, LOG_NO_PREVIOUS
from kubeagent_verdict.dataset.names import Names

ORIGIN_EVENTS_FORBIDDEN = ('events is forbidden: User "kubeagent" cannot list '
                           'resource "events" in API group "" in the namespace "kube-system"')


class Draw(NamedTuple):
    scope_value: str
    victims: tuple[Names, ...]
    origin: Names | None
    nodes: tuple[str, ...]
    width: int


class Row(NamedTuple):
    key: str
    role: str
    index: int
    names: Names
    workload: c.Workload
    text: stories.VictimText | stories.OriginRow
    result: rules.Result
    candidates: tuple[c.Candidate, ...]
    trace: tuple


class Built(NamedTuple):
    story: stories.Story
    world_name: str
    draw: Draw
    group: str
    user: str
    rows: tuple[Row, ...]
    health: c.ClusterHealth | None
    service_issues: tuple[c.ServiceIssue, ...]
    gathered: gather.GatherResult
    unverified: bool


def _draw_in(rng: random.Random, ns: str | None) -> Names:
    n = names_mod.draw(rng)
    ns = ns or n.ns
    tag = n.image.rsplit(":", 1)[-1]
    return replace(n, ns=ns, pod=names_mod.pod_name(rng, n.name),
                   image=f"registry.example.com/{ns}/{n.name}:{tag}")


def draw(story: stories.Story, rng: random.Random, *, width: int) -> Draw:
    """Every rng call for a pair, before any branch on the world (Ruling 11)."""
    if not 2 <= width <= len(story.victims):
        raise ValueError(f"{story.key}: width {width} outside 2..{len(story.victims)}")
    if story.scope_field == "ns":
        scope = rng.choice(names_mod.NAMESPACES)
    elif story.scope_field == "node":
        scope = rng.choice(names_mod.NODES)
    else:
        scope = ""
    victims: list[Names] = []
    seen: set[tuple[str, str]] = set()
    for _ in story.victims[:width]:
        while True:
            n = _draw_in(rng, scope if story.scope_field == "ns" else None)
            if story.scope_field == "node":
                n = replace(n, node=scope)
            if (n.ns, n.name) not in seen:
                break
        seen.add((n.ns, n.name))
        victims.append(n)
    row = story.broken.origin_row or story.healthy.origin_row
    origin = None
    if row is not None:
        o = names_mod.draw(rng)
        origin = replace(o, ns=row.namespace, name=row.name, container=row.container,
                         pod=names_mod.pod_name(rng, row.name))
    named = {n.node for n in victims} | ({origin.node} if origin else set())
    lo = max(3, len(named) + 1)
    total = rng.randint(lo, max(lo, 5))
    nodes = sorted(named)
    for extra in names_mod.NODES:
        if len(nodes) >= total:
            break
        if extra not in nodes:
            nodes.append(extra)
    return Draw(scope, tuple(victims), origin, tuple(sorted(nodes)), width)


def _sub(text: str, n: Names | None, d: Draw) -> str:
    return text.format_map({
        "scope": d.scope_value, "node": n.node if n else d.scope_value,
        "ns": n.ns if n else d.scope_value, "name": n.name if n else "",
        "pod": n.pod if n else "", "pvc": n.pvc if n else "",
        "image": n.image if n else "", "nodes": str(len(d.nodes))})


def _kind(t) -> str:
    return t.kind if isinstance(t, stories.OriginRow) else t.workload_kind


def _container(t, n: Names) -> str:
    return n.init_container if t.status.startswith("Init:") else n.container


def _log_body(value: str) -> str:
    if not value:
        raise ValueError("a crash-family log is empty: it would print a bare log-cause label")
    if value == stories.NO_PREVIOUS:
        return LOG_NO_PREVIOUS
    if value == stories.NO_CLASSIFIABLE:
        return LOG_NO_CLASSIFIABLE
    return LOG_CAUSE_PREFIX + value


def _pick(t, field: str, healthy: bool):
    alt = getattr(t, field + "_healthy", None)
    return alt if healthy and alt is not None else getattr(t, field)


def build(story: stories.Story, d: Draw, *, world: str, unverified: bool = False,
          budget: int = c.MAX_TOOL_CALLS, origin_events_failed: str = "") -> Built:
    if world not in ("broken", "healthy"):
        raise ValueError(f"world {world!r}")
    healthy = world == "healthy"
    w = story.healthy if healthy else story.broken
    entries = [("victim", i, n, v) for i, (v, n) in enumerate(zip(story.victims, d.victims))]
    if w.origin_row is not None:
        entries.append(("origin", -1, d.origin, w.origin_row))
    entries.sort(key=lambda e: (e[2].ns, e[2].name, _kind(e[3])))   # _report_order's key

    def finding(t, n: Names) -> c.Finding:
        s = rem.suggest_for(t.issue, ns=n.ns, pod=n.pod, container=_container(t, n),
                            kind=_kind(t), workload=n.name)
        return c.Finding(issue=t.issue, reason=t.reason,
                         evidence=_sub(_pick(t, "evidence", healthy), n, d),
                         next_step=s.next_step, command=s.command)

    def bare(t, n: Names) -> c.Workload:
        ready = t.ready if isinstance(t, stories.OriginRow) else 0
        desired = t.desired if isinstance(t, stories.OriginRow) else 1
        return c.Workload(namespace=n.ns, name=n.name, kind=_kind(t), ready=ready,
                          desired=desired, status=t.status, restarts=n.restarts,
                          findings=(finding(t, n),))

    origin_node = d.scope_value if story.origin_kind == "node" else ""
    nodes = tuple(
        health.Node(name, conditions=w.conditions, unschedulable=w.unschedulable,
                    lease=w.lease, lease_age_ms=w.lease_age_ms) if name == origin_node
        else health.Node(name, conditions=(health.READY,))
        for name in d.nodes)
    cluster, down = health.assess(nodes, [bare(t, n) for _, _, n, t in entries])
    if unverified and not down:
        raise ValueError(f"{story.key}: unverified needs a down node to refuse")

    pods = tuple(health.Pod(n.ns, n.pod, n.node, labels=(("app", n.name),))
                 for _, _, n, _ in entries)
    svcs, slices, backends, svc_pods = [], [], [], list(pods)
    for spec in w.services:
        svcs.append(health.Service(spec.namespace, spec.name, selector=spec.selector))
        slices.append(health.EndpointSlice(spec.namespace, spec.name, ready=spec.ready))
        if spec.backend is not None:
            backends.append(health.Backend(spec.namespace, spec.backend[0], spec.selector,
                                           spec.backend[1]))
        svc_pods += [health.Pod(spec.namespace, f"{spec.name}-{i}", d.nodes[0],
                                labels=spec.selector, ready=r == "true")
                     for i, r in enumerate(spec.ready)]
    issues = health.annotate_endpoint_cause(
        health.service_issues(tuple(svcs), tuple(slices), tuple(backends)),
        tuple(svcs), tuple(svc_pods), down)
    policies = tuple(replace(p, namespace=_sub(p.namespace, None, d)) for p in w.policies)

    gws, objs = [], []
    for role, _, n, t in entries:
        ob = []
        for dn in down:
            o = objects.Object(kind="node", name=dn.name, scan_reason=dn.reason,
                               placement="on" if n.node == dn.name else "off",
                               fresh=objects.NODE_NOT_READY, intent="cause")
            ob.append(objects.unverify(o, "read_failed") if unverified else o)
        if w.pvc_reason and role == "victim":
            ob.append(objects.Object(
                kind="pvc", name=n.pvc, scan_reason=w.pvc_reason, placement="mounted",
                fresh=objects.Fresh(phase=w.pvc_phase, storage_class=w.pvc_class),
                intent="cause"))
        if getattr(t, "pulls", False):
            # The literal is never declared: gather reads it back from the
            # pulling pod's events (gather._registry_fresh), so a healthy twin
            # whose events hold an image-side literal refutes this candidate.
            ob.append(objects.Object(
                kind="registry", name=gather._registry_host(n.image), scan_reason="{count}",
                placement="", fresh=objects.Fresh(), intent="cause"))
        objs.append(tuple(ob))
        container = _container(t, n)
        log = _pick(t, "log", healthy)
        reads_log = t.issue in gather.CRASH_FAMILY
        f = gather.GatherFinding(issue=t.issue, pod=f"{n.ns}/{n.pod}", container=container,
                                 log_read=_log_body(log) if reads_log else None,
                                 image=n.image if getattr(t, "pulls", False) else "")
        refused = role == "origin" and bool(origin_events_failed)
        # gather refuses a workload with both events and events_failed set.
        events = () if refused else tuple(
            (r, _sub(m, n, d), k) for r, m, k in _pick(t, "events", healthy))
        gws.append(gather.GatherWorkload(
            namespace=n.ns, name=n.name, pod=n.pod, issue=t.issue, objects=tuple(ob),
            events=events, findings=(f,),
            events_failed=origin_events_failed if refused else ""))
    gathered = gather.gather(gws, budget=budget)

    # The same fill gather.gather does (gather.py:538-541): the trace below must
    # see each registry object's real count, never the "{count}" template.
    counts = gather._registry_counts(gws)
    rows, workloads = [], []
    for i, (role, idx, n, t) in enumerate(entries):
        candidates = gathered.candidates[i]
        result = gathered.results[i]
        base = bare(t, n)
        wl = replace(base, candidates=candidates, confidence=render.header_for(candidates),
                     decided=result.decided, decided_cause=result.cause if result.decided else "",
                     decided_outcome=result.outcome if result.decided else "",
                     network_policies=health.network_policies_for(base, (pods[i],), policies))
        workloads.append(wl)
        filled = tuple(replace(obj, scan_reason=str(counts.get(obj.name, 0)))
                       if obj.kind == "registry" else obj for obj in objs[i])
        trace = rules.attribute(filled, ns=n.ns, pod=n.pod, issue=t.issue)
        rows.append(Row(f"{n.ns}/{n.name}", role, idx, n, wl, t, result, candidates, trace))

    issues_c = tuple(i.contract() for i in issues)
    user = c.build_user_message(cluster, None, "", issues_c, tuple(workloads), gathered.reads)
    group = "+".join(f"propagation:{story.key}:{n.ns}/{n.name}" for n in d.victims)
    render.check_prompt_size(user, entry_or_scenario_key=group)
    return Built(story, world, d, group, user, tuple(rows), cluster, issues_c, gathered,
                 unverified)
