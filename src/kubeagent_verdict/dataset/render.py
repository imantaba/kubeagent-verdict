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
from kubeagent_verdict.dataset import health, names, rules
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset.objects import drop, refute, unverify

# render.py's public surface. Each step that adds a new function or a new
# re-exported name appends it here, so ruff's F401 (unused import) never
# has a window where an already-imported name looks unused.
__all__ = ["bind", "check_prompt_size", "cluster_health", "deciding_ending",
           "down_nodes", "draw_ending", "drop", "header_for", "node_total", "prompt_meta",
           "refute", "rule_rationale", "unverify", "workload_meta"]

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

# Nine always-ruled-out PVC decoys. `truncated` appends all nine to push the
# winner's line past kubeagent's 8-candidate cap, and `attributed` adds the
# first on a coin. Unmounted, so the rules rule each one out and the gather
# never reads it. Never drawn by any rng (fresh.how="not_read" — draw_ending
# is never called on them), so no seed's draw sequence moves when they are
# added.
PAD_PVC_OBJECTS = tuple(
    o.Object(kind="pvc", name=pad_name, scan_reason="ProvisioningFailed",
             placement="unmounted", fresh=o.Fresh(how="not_read"), intent="decoy")
    for pad_name in names.PAD_PVCS
)

# `positional_probe`'s first candidate, per winner kind. It is live, so the
# rules attribute it, and its fresh read refutes it, so they pass over it
# and decide the winner. Each sorts before any winner of its kind:
# worker-1 is the first node name (the builder moves a row's own worker-1
# to worker-2), and a pad sorts before every drawn PVC. The claim's scan
# reason is one of pvchealth's six (internal/pvchealth/pvchealth.go:27);
# "Pending" is a phase, not a reason.
POSITIONAL_DECOYS = {
    "node": o.Object(kind="node", name=names.NODES[0], scan_reason="NotReady", placement="on",
                     fresh=o.Fresh(ready="True"), intent="decoy"),
    "pvc": o.Object(kind="pvc", name=names.PAD_PVCS[0], scan_reason="ProvisioningFailed",
                    placement="mounted",
                    fresh=o.Fresh(phase="Bound", storage_class="standard"), intent="decoy"),
}


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


# The endings `deciding_ending` may give a winner, per kind. "declared"
# keeps the object as the entry wrote it; every other name is a `how`
# unverify() takes. There is no registry row: a single-workload row never
# clears the registry threshold, so no registry is ever a winner.
DECIDING_ENDINGS = {
    "node": ("declared", "lease", "read_failed"),
    "pvc": ("declared", "read_failed"),
}


def deciding_ending(obj: o.Object, rng: random.Random) -> o.Object:
    """Draw the ending of a job-1 row's winner, one `rng.choice`.

    The winner must still decide the row, so the choice is between the
    object as declared and the two unverified shapes the rules keep:
    `lease` (a node that is Ready but has no kubelet lease) and
    `read_failed` (the describe failed). The declared object is a choice
    only when the rules confirm it; a declared fresh read that refutes it
    would leave the row undecided. `obj` is judged as given, placement
    included, so an object the rules rule out gets no ending that decides.
    """
    if obj.kind not in DECIDING_ENDINGS:
        raise ValueError(f"no deciding ending for a {obj.kind}: {obj.name}")
    choices = DECIDING_ENDINGS[obj.kind]
    declared = rules.decide(rules.attribute((obj,), ns="", pod="", issue=""))
    if declared.outcome != "confirmed":
        choices = choices[1:]
    choice = rng.choice(choices)
    if choice == "declared":
        return obj
    return unverify(obj, choice)


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


def workload_meta(result: rules.Result, *, expected_cause: str,
                  own_cause_keywords: list[str],
                  own_cause_must_not: list[str]) -> dict:
    """Build the eight-key per-workload meta dict: job, decided,
    decided_cause, decided_outcome, decided_evidence, expected_cause,
    own_cause_keywords, own_cause_must_not.
    `job` is derived from `result` itself — 1 when the workload decided, 2
    when it did not — never passed in by the caller. The four decided_*
    keys read straight off `result`, falling back to Result's own ""
    defaults when the workload was never decided. `own_cause_keywords` is
    passed through as given — job 2's grading list for this one
    workload's own cause; the caller is responsible for the
    interface-sheet rule that it is non-empty only when job == 2 and
    expected_cause is a named cause (never on none_of_these, never on a
    decided workload). `own_cause_must_not` travels with the keywords: the
    same entry's list when the keywords come from a catalog entry, and []
    everywhere else. It is required, so no caller can forget it.
    """
    return {
        "job": 1 if result.decided else 2,
        "decided": result.decided,
        "decided_cause": result.cause,
        "decided_outcome": result.outcome,
        "decided_evidence": result.evidence,
        "expected_cause": expected_cause,
        "own_cause_keywords": own_cause_keywords,
        "own_cause_must_not": own_cause_must_not,
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
# because the container runtime is down. The NodeReady condition's reason
# and message kubeagent would read for that node are objects.NOT_READY_REASON
# and NOT_READY_MESSAGE, the same text the node describe prints.
_NO_LEASE = "no kubelet lease"  # clusterhealth.go:140
_SYSTEM_NAMESPACE = "kube-system"  # clusterhealth.go:18
_MIN_NODES = 3
# A node candidate's cause, `node <name> (<reason>)` (rootcause/rootcause.go:44).
_NODE_CAUSE = re.compile(r"^node ([^ ()]+) \((.+)\)$")
# The gather's label for a node describe: its namespace is empty, so the
# label reads `describe node /<name>` (investigate/gather.go:132).
_DESCRIBE_NODE = "describe node /"


# Kept for the callers that import these names from render (the checker's
# docs, tests/test_checker.py, tests/test_cluster_health.py and
# tests/test_gather_byte_equal.py). The code lives in health.py.
_trim_line = health.trim_line
_not_ready_issue = health.not_ready_issue
_flagged = health.flagged


def _node_reasons(workloads: tuple[c.Workload, ...]) -> dict[str, set[str]]:
    """Every node candidate's name and its reasons."""
    reasons: dict[str, set[str]] = {}
    for w in workloads:
        for cand in w.candidates:
            m = _NODE_CAUSE.match(cand.cause)
            if m:
                reasons.setdefault(m.group(1), set()).add(m.group(2))
    return reasons


def _named_nodes(reasons: dict[str, set[str]], reads: tuple[c.EvidenceRead, ...]) -> set[str]:
    """The nodes the prompt names: node candidates and `describe node /<name>` reads."""
    return set(reasons) | {r.label[len(_DESCRIBE_NODE):] for r in reads
                           if r.label.startswith(_DESCRIBE_NODE)}


def node_total(workloads: tuple[c.Workload, ...], reads: tuple[c.EvidenceRead, ...]) -> int:
    """The cluster-health header's node count T = max(3, named nodes + 1)
    (see `cluster_health`)."""
    return max(_MIN_NODES, len(_named_nodes(_node_reasons(workloads), reads)) + 1)


def _assess(workloads: tuple[c.Workload, ...], reads: tuple[c.EvidenceRead, ...]
            ) -> tuple[c.ClusterHealth | None, tuple[health.DownNode, ...]]:
    """Run `health.assess` once: (the block, the down nodes)."""
    reasons = _node_reasons(workloads)
    named = _named_nodes(reasons, reads)
    nodes = []
    for name in sorted(named):
        rs = reasons.get(name, set())
        unknown = rs - {"NotReady", _NO_LEASE}
        if unknown:
            raise ValueError(f"node {name}: no cluster-health text for reason "
                             f"{min(unknown)!r}")
        if "NotReady" in rs:
            nodes.append(health.Node(name, (health.Condition(
                "Ready", "False", o.NOT_READY_REASON, o.NOT_READY_MESSAGE),)))
        elif rs:
            nodes.append(health.Node(name, (health.READY,), lease="missing"))
        else:
            nodes.append(health.Node(name, (health.READY,)))
    total = node_total(workloads, reads)
    # Healthy nodes the prompt never names. They print nothing; only the
    # count T sees them. The leading space keeps them off any real name.
    nodes += [health.Node(f" healthy-{i}", (health.READY,)) for i in range(total - len(nodes))]
    return health.assess(nodes, workloads)


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

    It builds synthetic nodes from the candidates and hands them to
    `health.assess`, the port the CLUSTER capture pins.
    """
    return _assess(workloads, reads)[0]


def down_nodes(workloads: tuple[c.Workload, ...],
               reads: tuple[c.EvidenceRead, ...]) -> tuple[health.DownNode, ...]:
    """The nodes `cluster_health` judges down, from the same `health.assess`
    call: what svchealth's endpoint cause sees (AnnotateEndpointCause)."""
    return _assess(workloads, reads)[1]


_NOUN = {"node": "node", "pvc": "claim", "registry": "registry"}


def rule_rationale(result: rules.Result) -> str:
    """A decided rule row's rationale, built from the rules' own evidence.

    Every rule row's cause comes straight from `rules.decide` (never a
    hand-written string), so the rationale explaining it must agree with
    the same evidence the rules found -- this is what makes that true.
    `result.outcome` is always "confirmed" or "unverified" here:
    `rules.decide` never returns a decided Result with any other outcome.
    """
    kind, name = result.cause.split(" ", 2)[:2]
    noun = _NOUN[kind.lower()]
    evidence = result.evidence[0].lower() + result.evidence[1:]
    if result.outcome == "confirmed":
        return (f"The fresh read of {noun} {name} confirms it: {evidence}, "
                f"so the {noun}'s own state is why the flagged workload is failing.")
    return (f"The fresh read of {noun} {name} did not clear the earlier finding: "
            f"{evidence}, so {name} stays the named cause rather than something "
            f"the read ruled out.")
