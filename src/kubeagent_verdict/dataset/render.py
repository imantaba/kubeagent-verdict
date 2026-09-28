"""Render kubeagent-shaped candidates and reads from declared objects.

A case builder in cases.py declares one CatalogEntry/scenario's decoy
objects, transforms each with an Option-A ending (as declared, refuted, or
unverified), then hands the finished tuple to this module to turn into the
EvidenceRead/Candidate shapes contract.py's prompt assembly expects. No
builder ever imports objects.py directly — cases.py imports everything it
needs from here.
"""

from __future__ import annotations

import dataclasses
import random
import re

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import names, rules
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset.objects import drop, refute, unverify

# render.py's public surface. Each step that adds a new function or a new
# re-exported name appends it here, so ruff's F401 (unused import) never
# has a window where an already-imported name looks unused.
__all__ = ["apply_budget", "bind", "check_prompt_size", "cluster_health", "draw_ending", "drop",
           "header_for", "object_reads", "prompt_meta", "refute", "registry_events_read",
           "render_workload", "unverify", "workload_meta"]

MAX_READS = 8
MAX_PROMPT_BYTES = 64 * 1024

# The closed set of Option-A endings draw_ending() may pick, per kind. Each
# name past "refuted" is the `how` unverify() takes for that kind — matches
# objects.py's own unverify() vocabulary (node: read_failed, lease; pvc:
# read_failed; registry: read_failed, auth, no_event), minus registry's
# read_failed: the interface sheet says registry read_failed is never
# drawn. There is no "confirmed"/as-declared entry: a decoy left as
# declared could independently satisfy rules.decide()'s first-CONFIRMED-
# wins rule and win outright, which no decoy may do.
ENDINGS = {
    "node": ("refuted", "lease", "read_failed"),
    "pvc": ("refuted", "read_failed"),
    "registry": ("refuted", "auth", "no_event"),
}

# Nine always-ruled-out PVC decoys `truncated` appends to overflow the 8-read
# budget. Never drawn by any rng (fresh.how="not_read" — draw_ending is never
# called on them), so no seed's draw sequence moves when they are added.
PAD_PVC_OBJECTS = tuple(
    o.Object(kind="pvc", name=pad_name, scan_reason="ProvisioningFailed",
             placement="unmounted", fresh=o.Fresh(how="not_read"), intent="decoy")
    for pad_name in names.PAD_PVCS
)


def bind(obj: o.Object, names: dict) -> o.Object:
    """Fill in an object's `{ns}`/`{pod}`/... placeholders from `names`.

    `names` is the same dict shape `names.draw(rng)` returns. Every string
    field on `obj` is run through `str.format(**names)`; every other field
    (bool, tuple, the nested `Fresh`) passes through unchanged. `obj` is
    never mutated — a new Object is returned. A name with no placeholders
    (a literal PVC name such as one of `names.PAD_PVCS`) passes through
    `.format()` as a no-op.
    """
    changes = {}
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        if isinstance(value, str):
            changes[field.name] = value.format(**names)
    return dataclasses.replace(obj, **changes)


def draw_ending(obj: o.Object, rng: random.Random) -> o.Object:
    """Draw one Option-A ending for `obj` and return the transformed copy.

    Picks uniformly from ENDINGS[obj.kind] with rng.choice(). "refuted"
    calls refute(obj). Every other name is a `how` string passed straight
    to unverify(obj, how). There is no as-declared choice: every decoy
    this function draws for comes back either refuted or unverified, never
    left as declared.
    """
    choice = rng.choice(ENDINGS[obj.kind])
    if choice == "refuted":
        return refute(obj)
    return unverify(obj, choice)


_PHASE = {"registry": 0, "node": 1, "pvc": 2}


def apply_budget(
    objects: tuple[o.Object, ...],
    *,
    workload_order: tuple[int, ...],
    entry_or_scenario_key: str,
    allow_overflow: bool = False,
) -> tuple[o.Object, ...]:
    """Reorder into gather order, then apply the 8-read budget.

    Walks `objects` in kubeagent's own gather order — registry events
    first, then node describes, then PVC describes, ties broken by
    `workload_order[i]` — and returns them in that order. Any object past
    the 8th (MAX_READS) has its `fresh` replaced with `Fresh(how="not_read")`,
    matching what a real gather does when the read budget runs out before
    it reaches an object. An `intent="cause"` object that would be starved
    this way raises ValueError, since a scenario that silently loses its
    own cause's evidence is almost always an authoring mistake — pass
    `allow_overflow=True` for the one builder that starves the cause on
    purpose.
    """
    order = sorted(range(len(objects)),
                    key=lambda i: (_PHASE[objects[i].kind], workload_order[i]))
    ordered = tuple(objects[i] for i in order)
    out = []
    for idx, obj in enumerate(ordered):
        if idx < MAX_READS:
            out.append(obj)
            continue
        if obj.intent == "cause" and not allow_overflow:
            raise ValueError(
                f"entry {entry_or_scenario_key}: the {MAX_READS}-read budget "
                f"would leave {obj.kind}/{obj.name} (intent=cause) unread; "
                "pass allow_overflow=True if that is the point"
            )
        out.append(dataclasses.replace(obj, fresh=o.Fresh(how="not_read")))
    return tuple(out)


def registry_events_read(
    obj: o.Object,
    *,
    ns: str,
    pod: str,
    image: str,
    own_line: str | None = None,
) -> c.EvidenceRead:
    """Build the `events {ns}/{pod}` read for a registry object.

    Mirrors kubeagent's own formatEvents: no literal (the "no_event"
    ending) reads as "no events for ns/pod"; any other literal reads as
    one "Failed:" line naming it. `own_line`, when given, appends a SECOND
    "Failed:" line built from it, after the object's own line — this is
    the contradiction_probe shape, where the events read carries both the
    unverified-auth literal (first, so classifyPullEvents settles on
    "auth") and the entry's own image-error literal (second, the cause the
    read still points at).
    """
    label = f"events {ns}/{pod}"
    if obj.fresh.literal == "" and own_line is None:
        return c.EvidenceRead(label=label, content=f"no events for {ns}/{pod}")
    content = (
        f"events for {ns}/{pod}:\n"
        f'  Failed: Failed to pull image "{image}": {obj.fresh.literal} (x4)\n'
    )
    if own_line is not None:
        content += f'  Failed: Failed to pull image "{image}": {own_line} (x4)\n'
    return c.EvidenceRead(label=label, content=content)


def object_reads(
    objects: tuple[o.Object, ...],
    *,
    ns: str,
    pod: str,
    image: str = "",
) -> tuple[c.EvidenceRead, ...]:
    """Turn ended objects into the EvidenceRead tuple a prompt renders.

    Node and PVC objects reuse rules.read_text unchanged. Registry objects
    go through registry_events_read (image is only used for those). An
    object with fresh.how == "not_read" produces no read — the read
    budget never reached it, so there is nothing to show.
    """
    reads = []
    for obj in objects:
        if obj.fresh.how == "not_read":
            continue
        if obj.kind == "registry":
            reads.append(registry_events_read(obj, ns=ns, pod=pod, image=image))
            continue
        label, content = rules.read_text(obj, ns=ns, pod=pod)
        reads.append(c.EvidenceRead(label=label, content=content))
    return tuple(reads)


# kubeagent's `confidence.ForRootCause` (internal/confidence/confidence.go:36-47
# at v1.24.0), keyed by the attributed cause's prefix, in the Go switch's order.
_HEADER_BY_PREFIX = (("node ", "high"), ("PVC ", "high"), ("registry ", "medium"))


def header_for(candidates: tuple[c.Candidate, ...]) -> str:
    """The `[confidence: ...]` header kubeagent prints over a trace.

    A port of `ForRootCause`, applied to the one attributed candidate's
    cause. No attributed candidate gives "" — kubeagent prints no header.
    Two or more raise ValueError: kubeagent's trace has at most one winner,
    so two is a generator bug, not a prompt to render.
    """
    attributed = [cand for cand in candidates if cand.verdict == "attributed"]
    if len(attributed) > 1:
        raise ValueError(
            f"{len(attributed)} attributed candidates; kubeagent attributes at most one")
    if not attributed:
        return ""
    for prefix, level in _HEADER_BY_PREFIX:
        if attributed[0].cause.startswith(prefix):
            return level
    return ""


def render_workload(
    objects: tuple[o.Object, ...],
    *,
    ns: str,
    name: str,
    pod: str,
    image: str,
    issue: str,
    kind: str,
    status: str,
    rng: random.Random | None = None,
) -> tuple[c.Workload, tuple[c.EvidenceRead, ...], rules.Result]:
    """Assemble a partial Workload, its reads, and the rules.Result.

    `objects` must already carry each object's final drawn ending — this
    function does not call bind/draw_ending/apply_budget; the builder runs
    those before handing objects in here. `rng` is accepted for signature
    symmetry with this module's other helpers but is unused: every draw
    already happened upstream.

    The returned Workload fills only the fields this module owns —
    namespace, name, kind, status, candidates, decided, decided_cause,
    decided_outcome, and confidence (the trace header, via `header_for`).
    findings, network_policies, rollout, ready, and desired stay at their
    dataclass defaults; a caller building a full prompt-ready Workload
    merges those in separately.
    """
    candidates = rules.attribute(objects, ns=ns, pod=pod, issue=issue)
    result = rules.decide(candidates)
    decisions = {d.candidate: d for d in result.decisions}
    contract_candidates = tuple(
        c.Candidate(
            cause=cand.cause,
            verdict=cand.verdict,
            reason=cand.reason,
            fresh_read_outcome=(
                decisions[cand.cause].outcome if cand.cause in decisions else ""
            ),
            fresh_read_evidence=(
                decisions[cand.cause].evidence if cand.cause in decisions else ""
            ),
        )
        for cand in candidates
    )
    reads = object_reads(objects, ns=ns, pod=pod, image=image)
    workload = c.Workload(
        namespace=ns, name=name, kind=kind, ready=0, desired=0, status=status,
        restarts=0, findings=(), candidates=contract_candidates,
        decided=result.decided, decided_cause=result.cause,
        decided_outcome=result.outcome,
        confidence=header_for(contract_candidates),
    )
    return workload, reads, result


def workload_meta(result: rules.Result, *, expected_cause: str,
                  own_cause_keywords: list[str]) -> dict:
    """Build the seven-key per-workload meta dict: job, decided,
    decided_cause, decided_outcome, decided_evidence, expected_cause,
    own_cause_keywords.
    `job` is derived from `result` itself — 1 when the workload decided, 2
    when it did not — never passed in by the caller. The four decided_*
    keys read straight off `result`, falling back to Result's own ""
    defaults when the workload was never decided. `own_cause_keywords` is
    passed through as given — job 2's grading list for this one
    workload's own cause; the caller is responsible for the
    interface-sheet rule that it is non-empty only when job == 2 and
    expected_cause is a named cause (never on none_of_these, never on a
    decided workload).
    """
    return {
        "job": 1 if result.decided else 2,
        "decided": result.decided,
        "decided_cause": result.cause,
        "decided_outcome": result.outcome,
        "decided_evidence": result.evidence,
        "expected_cause": expected_cause,
        "own_cause_keywords": own_cause_keywords,
    }


def prompt_meta(
    workload_metas: dict[str, dict],
    *,
    label: str,
    decoy_by_workload: dict,
) -> dict:
    """Add the two prompt-level meta keys to an already-built dict of
    per-workload meta dicts, keyed by "{ns}/{name}". Does not call
    workload_meta itself — both `label` (from
    rules.label(rules.shared(results))) and `decoy_by_workload` are
    computed by the caller.
    """
    if not workload_metas:
        raise ValueError("prompt_meta: workload_metas must not be empty")
    return {
        "workloads": workload_metas,
        "label": label,
        "decoy_by_workload": decoy_by_workload,
    }


def check_prompt_size(prompt: str, *, entry_or_scenario_key: str) -> None:
    """Raise if `prompt`, UTF-8 encoded, is over MAX_PROMPT_BYTES.

    Call this right after contract.build_user_message, before writing an
    example out — build_user_message itself only truncates, it never
    raises (that is kubeagent's own runtime policy; this module's job is
    to refuse the truncation before it ever reaches a training example).
    """
    size = len(prompt.encode("utf-8"))
    if size > MAX_PROMPT_BYTES:
        raise ValueError(
            f"entry {entry_or_scenario_key}: prompt is {size} bytes, over "
            f"the {MAX_PROMPT_BYTES}-byte cap"
        )


# The cluster-health block. A port of kubeagent's `clusterhealth.Assess`
# (internal/clusterhealth/clusterhealth.go at v1.24.0), fed from what the
# prompt already shows, because the dataset has no node list.
#
# The dataset tells one NotReady story: the kubelet reports KubeletNotReady
# because the container runtime is down. These are the NodeReady
# condition's reason and message kubeagent would read for that node.
_NOT_READY_REASON = "KubeletNotReady"
_NOT_READY_MESSAGE = "container runtime is down"
_NO_LEASE = "no kubelet lease"  # clusterhealth.go:140
_SYSTEM_NAMESPACE = "kube-system"  # clusterhealth.go:18
_MIN_NODES = 3
# A node candidate's cause, `node <name> (<reason>)` (rootcause/rootcause.go:44).
_NODE_CAUSE = re.compile(r"^node ([^ ()]+) \((.+)\)$")
# The gather's label for a node describe: its namespace is empty, so the
# label reads `describe node /<name>` (investigate/gather.go:132).
_DESCRIBE_NODE = "describe node /"


def _trim_line(s: str, limit: int) -> str:
    """A port of `trimLine` (clusterhealth.go:218-229): the first line,
    stripped, cut to `limit` runes plus an ellipsis when it is longer."""
    i = s.find("\n")
    if i >= 0:
        s = s[:i]
    s = s.strip()
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _not_ready_issue(reason: str, message: str) -> str:
    """A port of `notReadyIssue` (clusterhealth.go:197-216): `NotReady`,
    plus the condition's reason and its trimmed message when they are
    there. kubeagent passes both through `safetext.Line` first
    (clusterhealth.go:181); the caller here does the same or passes
    constants."""
    s = "NotReady"
    m = _trim_line(message, 120)
    if reason and m:
        s += ": " + reason + " — " + m
    elif reason:
        s += ": " + reason
    elif m:
        s += ": " + m
    return s


def _flagged(w: c.Workload) -> bool:
    """A port of `Workload.Flagged` (inventory/inventory.go:102-104)."""
    return len(w.findings) > 0 or w.ready < w.desired or w.status == "Failed"


def cluster_health(workloads: tuple[c.Workload, ...],
                   reads: tuple[c.EvidenceRead, ...]) -> c.ClusterHealth | None:
    """The cluster-health verdict kubeagent would compute for this prompt.

    kubeagent calls a cluster Degraded when it has any node issue or any
    system issue (clusterhealth.go:104-108). Here:

    - A node issue is a node candidate, `node <name> (<reason>)`, of any
      verdict. kubeagent makes one candidate per down node on every
      flagged workload (rootcause.go:36-44), so the candidates name every
      down node. That includes a candidate the 8-candidate cap later hides.
      Reason `NotReady` prints `<name> NotReady: KubeletNotReady —
      container runtime is down`; reason `no kubelet lease` prints
      `<name> no kubelet lease` (clusterhealth.go:71, :84, :140). Any
      other reason raises ValueError: the dataset has no block text for it.
    - A node named both ways is NotReady. kubeagent checks the lease only
      on a Ready node (clusterhealth.go:73-82).
    - A system issue is a flagged kube-system workload:
      `kube-system/<name> <ready>/<desired> <status>`, or
      `kube-system/<name> <status>` for a Job or CronJob
      (clusterhealth.go:93-103), in kubeagent's workload order
      (inventory/inventory.go:534-547).

    The node count is T = max(3, named nodes + 1). The named nodes are the
    node candidates' names and the names in `describe node /<name>` read
    labels; the +1 is a healthy node the prompt never names. R = T minus
    the NotReady nodes. A node with no kubelet lease is still Ready
    (clusterhealth.go:73-74).

    With no node issue and no system issue the cluster is Healthy and
    kubeagent prints no block, so this returns None.
    """
    reasons: dict[str, set[str]] = {}
    for w in workloads:
        for cand in w.candidates:
            m = _NODE_CAUSE.match(cand.cause)
            if m:
                reasons.setdefault(m.group(1), set()).add(m.group(2))
    system = []
    flagged = [w for w in workloads if w.namespace == _SYSTEM_NAMESPACE and _flagged(w)]
    for w in sorted(flagged, key=lambda w: (w.name, w.kind)):
        if w.kind in ("Job", "CronJob"):
            system.append(f"{w.namespace}/{w.name} {w.status}")
        else:
            system.append(f"{w.namespace}/{w.name} {w.ready}/{w.desired} {w.status}")
    if not reasons and not system:
        return None
    named = set(reasons) | {r.label[len(_DESCRIBE_NODE):] for r in reads
                            if r.label.startswith(_DESCRIBE_NODE)}
    total = max(_MIN_NODES, len(named) + 1)
    node_issues = []
    for name in sorted(reasons):
        unknown = reasons[name] - {"NotReady", _NO_LEASE}
        if unknown:
            raise ValueError(f"node {name}: no cluster-health text for reason "
                             f"{min(unknown)!r}")
        if "NotReady" in reasons[name]:
            node_issues.append(name + " " + _not_ready_issue(_NOT_READY_REASON,
                                                             _NOT_READY_MESSAGE))
        else:
            node_issues.append(name + " " + _NO_LEASE)
    not_ready = sum(1 for rs in reasons.values() if "NotReady" in rs)
    return c.ClusterHealth(degraded=True, nodes_ready=total - not_ready, nodes_total=total,
                           node_issues=tuple(node_issues), system_issues=tuple(system))
