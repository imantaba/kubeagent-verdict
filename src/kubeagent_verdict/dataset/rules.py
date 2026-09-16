"""Pure port of kubeagent's root-cause rules: attribution, decision, sharing.

Ports three kubeagent v1.24.0 Go packages, pinned to
`tests/fixtures/rules_golden.json` (captured from kubeagent tag v1.24.0,
commit 15ec5649bbd2d07558eae945b71430afc8f231fd, by Task 2):

- `internal/rootcause` (node/PVC/registry candidate attribution) -> attribute()
- `internal/hypothesis` (fresh-read decision, storage-class grouping,
  shared-cause lines) -> decide(), shared()
- `internal/investigate/reader.go` (the gather's describe formats) -> read_text()

Every cause, reason and evidence string below is copied verbatim from
kubeagent's own Go source; nothing here is paraphrased. This module is
pure: no I/O, no cluster client, no randomness. Given the same tuple of
declared `objects.Object`s it always returns the same answer.

Two scope notes:

1. `attribute()` returns EVERY candidate it considers, never just the first
   8. kubeagent's own 8-candidate cap (Go's `maxCandidatesPerWorkload`) is a
   RENDER concern, applied by `contract.render_candidates` in a later task.
   A caller that wants the capped view slices this function's result
   itself.
2. `read_text()` covers only "node" and "pvc" objects. A registry
   candidate's fresh read is the pulling pod's events, not a describe of
   the registry itself — kubeagent's own gather skips it outright
   (`internal/investigate/gather.go`: `continue // registry: no object to
   read`). Calling `read_text()` with a registry object raises
   `ValueError`.
"""
from __future__ import annotations

import string
from dataclasses import dataclass

from kubeagent_verdict.dataset import objects as ds_objects
from kubeagent_verdict.dataset.objects import (
    AUTH_LITERALS,
    CONNECTION_LITERALS,
    IMAGE_LITERALS,
    Object,
)

VERDICTS = ("attributed", "ruled_out", "outranked")          # scan verdicts
OUTCOMES = ("confirmed", "refuted", "unverified")             # fresh-read outcomes
LABELS = ("shared", "separate", "none")                       # job-3 labels
REGISTRY_THRESHOLD = 2
REGISTRY_ISSUES = ("ImagePullBackOff", "ErrImagePull")        # exact match; Init: variants never qualify
MAX_CANDIDATES = 8                                             # kubeagent's maxCandidatesPerWorkload


@dataclass(frozen=True)
class Candidate:
    """One root-cause candidate attribute() considered for one workload."""

    cause: str
    verdict: str
    reason: str
    obj: Object
    ns: str  # the workload's namespace; decide()'s PVC group key is "pvc/<ns>/<name>"


@dataclass(frozen=True)
class Decision:
    """One non-ruled-out candidate, re-checked against its fresh read."""

    candidate: str
    outcome: str
    evidence: str


@dataclass(frozen=True)
class Result:
    """decide()'s verdict for one workload."""

    decided: bool
    cause: str
    outcome: str
    evidence: str
    group_key: str
    group_text: str
    decisions: tuple[Decision, ...]


def _parenthesized(text: str) -> str:
    """The text inside the LAST "(...)" pair in text, or "" if there is none.

    Port of decide.go's parenthesized(): "PVC a (b) (c)" -> "c"; no parens,
    or an unbalanced pair, -> "".
    """
    end = text.rfind(")")
    if end < 0:
        return ""
    start = text.rfind("(", 0, end)
    if start < 0:
        return ""
    return text[start + 1 : end]


def attribute(objects: tuple[Object, ...], *, ns: str, pod: str, issue: str) -> tuple[Candidate, ...]:
    """Port of rootcause.Annotate + AnnotatePVC + AnnotateRegistry, per workload.

    `objects` is the menu already scoped to this one workload: kubeagent's
    Go annotators fold in every flagged workload and every down node,
    broken PVC and registry host at once; a declared story instead hands
    each workload's own candidates straight to this call, so there is no
    cross-workload state to thread through here. The one place kubeagent's
    Go genuinely needs OTHER workloads is the registry threshold count, and
    that count is baked into the declared registry Object's `scan_reason`
    (see objects.py's Object docstring) rather than computed in this
    function.

    Node candidates are processed first, then PVC, then registry —
    kubeagent's own call order (rootcause.go's Annotate, AnnotatePVC,
    AnnotateRegistry, in that order, from internal/scan/scan.go). Within a
    kind, candidates are processed in ascending name order, matching Go's
    `sort.Strings(names)` / `sort.Strings(keys)`.

    `ns` is stamped onto every `Candidate` this function returns: `decide()`
    needs it to build the Go PVC group key `"pvc/" + namespace + "/" + name`
    (shared.go's `group()`), and `attribute()` is the only place a
    `Candidate` is ever constructed from a declared story, so this is the
    one place that has `ns` to give it.
    """
    candidates: list[Candidate] = []
    root_cause: str | None = None

    nodes = sorted((o for o in objects if o.kind == "node"), key=lambda o: o.name)
    for obj in nodes:
        cause = f"node {obj.name} ({obj.scan_reason})"
        if obj.placement != "on":
            verdict, reason = "ruled_out", "no pod of this workload is scheduled on it"
        elif root_cause is None:
            root_cause = cause
            verdict, reason = "attributed", f"pod {pod} is scheduled on it"
        else:
            verdict, reason = "outranked", f"{root_cause} is the stronger cause"
        candidates.append(Candidate(cause, verdict, reason, obj, ns))

    pvcs = sorted((o for o in objects if o.kind == "pvc"), key=lambda o: o.name)
    for obj in pvcs:
        cause = f"PVC {obj.name} ({obj.scan_reason})"
        if obj.placement != "mounted":
            verdict, reason = "ruled_out", "not mounted by this workload's pods"
        elif root_cause is None:
            root_cause = cause
            verdict, reason = "attributed", f"pod {pod} mounts it"
        else:
            verdict, reason = "outranked", f"{root_cause} is the stronger cause"
        candidates.append(Candidate(cause, verdict, reason, obj, ns))

    if issue in REGISTRY_ISSUES:
        registries = sorted((o for o in objects if o.kind == "registry"), key=lambda o: o.name)
        for obj in registries:
            if obj.name == "":
                candidates.append(
                    Candidate("registry unknown", "ruled_out", "image reference undeterminable", obj, ns)
                )
                continue
            bare_cause = f"registry {obj.name}"
            if root_cause is not None:
                candidates.append(
                    Candidate(
                        bare_cause, "outranked", f"{root_cause} is the stronger cause", obj, ns
                    )
                )
                continue
            count = int(obj.scan_reason)
            if count < REGISTRY_THRESHOLD:
                candidates.append(
                    Candidate(
                        bare_cause,
                        "ruled_out",
                        "only workload failing to pull from this host; threshold is 2",
                        obj,
                        ns,
                    )
                )
            else:
                cause = f"registry {obj.name} ({count} workloads failing to pull)"
                root_cause = cause
                candidates.append(
                    Candidate(
                        cause,
                        "attributed",
                        f"{count} workloads failing to pull from this host clear the threshold of 2",
                        obj,
                        ns,
                    )
                )
    return tuple(candidates)


def _check_node(candidate: Candidate) -> tuple[str, str]:
    fresh = candidate.obj.fresh
    if fresh.how == "read_failed":
        return "unverified", "fresh read failed: " + fresh.message
    if fresh.how == "not_read":
        return "unverified", "not re-read: the read budget was spent first"
    heartbeat = _parenthesized(candidate.cause) in ("kubelet not heartbeating", "no kubelet lease")
    ready = fresh.ready
    if ready == "missing":
        return "confirmed", "the node has no Ready condition"
    if ready == "False":
        return "confirmed", "Ready condition is False now"
    if ready == "Unknown":
        return "confirmed", "Ready condition is Unknown now"
    if ready == "True" and heartbeat:
        return "unverified", "Ready condition is True, but the kubelet lease was not re-read"
    if ready == "True":
        return "refuted", "Ready condition is True now"
    # Unreachable via a validated Object: objects.NODE_READY closes `ready`
    # to True | False | Unknown | missing. Kept to mirror decide.go's own
    # default case exactly.
    return "unverified", "Ready condition is not one kubeagent expects"  # pragma: no cover


def _check_pvc(candidate: Candidate) -> tuple[str, str]:
    fresh = candidate.obj.fresh
    if fresh.how == "read_failed":
        return "unverified", "fresh read failed: " + fresh.message
    if fresh.how == "not_read":
        return "unverified", "not re-read: the read budget was spent first"
    phase = fresh.phase
    if phase == "Bound":
        return "refuted", "phase is Bound now"
    if phase == "Pending":
        return "confirmed", "phase is still Pending"
    if phase == "Lost":
        return "confirmed", "phase is Lost"
    return "unverified", "phase is not one kubeagent expects"


def _check_registry(candidate: Candidate) -> tuple[str, str]:
    fresh = candidate.obj.fresh
    if fresh.how == "read_failed":
        return "unverified", "fresh read failed: " + fresh.message
    if fresh.how == "not_read":
        return "unverified", "not re-read: the read budget was spent first"
    if fresh.wrong_pod:
        return "unverified", "events of the pulling pod were not read"
    literal = fresh.literal
    if literal == "":
        return "unverified", "no pull event names the failure; events may have aged out"
    if literal in CONNECTION_LITERALS:
        return "confirmed", f"a pull event shows a connection error: {literal}"
    if literal in AUTH_LITERALS:
        return (
            "unverified",
            f"a pull event shows an auth error: {literal}; that can be one image or the whole host",
        )
    assert literal in IMAGE_LITERALS  # objects.validate() closes fresh.literal to PULL_LITERALS
    return (
        "refuted",
        f"a pull event shows an image error: {literal}; this pull fails for this image, not the host",
    )


_CHECKERS = {"node": _check_node, "pvc": _check_pvc, "registry": _check_registry}


def _is_plain_class(name: str) -> bool:
    """Port of shared.go's plainName: lowercase ASCII [a-z0-9.-] only, non-empty."""
    alphabet = string.ascii_lowercase + string.digits + ".-"
    return name != "" and all(ch in alphabet for ch in name)


def _group(candidate: Candidate) -> tuple[str, str]:
    """Port of shared.go's group(). Called only on a confirmed winner.

    The PVC fallback key is `"pvc/" + ns + "/" + name`, matching
    kubeagent's own `"pvc/" + w.Namespace + "/" + h.Object` (shared.go).
    `Candidate.ns` carries the workload's namespace for exactly this —
    `attribute()` is the only place a `Candidate` is ever built from a
    declared story, and it always stamps `ns` on every one it returns.
    """
    kind = candidate.obj.kind
    if kind == "node":
        return f"node/{candidate.obj.name}", candidate.cause
    if kind == "registry":
        return f"registry/{candidate.obj.name}", candidate.cause
    reason = _parenthesized(candidate.cause)
    if reason in ("ProvisionerNotResponding", "MissingStorageClass"):
        storage_class = candidate.obj.fresh.storage_class
        if storage_class and _is_plain_class(storage_class):
            return (
                f"storageclass/{storage_class}/{reason}",
                f"storage class {storage_class} ({reason})",
            )
    return f"pvc/{candidate.ns}/{candidate.obj.name}", candidate.cause


def decide(candidates: tuple[Candidate, ...]) -> Result:
    """Port of hypothesis.Decide.

    Ruled-out candidates are skipped entirely — never re-checked, never in
    `decisions`. Every other candidate is re-checked and kept, in candidate
    order. The first CONFIRMED decision wins; failing that, the first
    UNVERIFIED decision wins; failing that, the workload stays undecided —
    a refuted candidate never wins by itself, even if it is the only one.
    """
    pairs: list[tuple[Candidate, Decision]] = []
    for candidate in candidates:
        if candidate.verdict == "ruled_out":
            continue
        outcome, evidence = _CHECKERS[candidate.obj.kind](candidate)
        pairs.append((candidate, Decision(candidate=candidate.cause, outcome=outcome, evidence=evidence)))
    decisions = tuple(decision for _, decision in pairs)

    for candidate, decision in pairs:
        if decision.outcome == "confirmed":
            group_key, group_text = _group(candidate)
            return Result(
                True, decision.candidate, decision.outcome, decision.evidence, group_key, group_text, decisions
            )
    for _, decision in pairs:
        if decision.outcome == "unverified":
            return Result(True, decision.candidate, decision.outcome, decision.evidence, "", "", decisions)
    return Result(False, "", "", "", "", "", decisions)


def shared(results: tuple[Result, ...]) -> tuple[str, ...]:
    """Port of hypothesis.Shared.

    Counts every Decided-and-Confirmed result, whether or not it has a
    group key. Fewer than 2 such results -> no line at all, not even the
    "no shared cause" fallback. Groups of size >= 2 sort by count
    descending, ties by key ascending, capped at 4 lines plus one
    truncation marker line. 2+ confirmed results but every group size 1 ->
    the single "no shared cause" fallback line.
    """
    confirmed = 0
    order: list[str] = []
    counts: dict[str, int] = {}
    texts: dict[str, str] = {}
    for result in results:
        if not result.decided or result.outcome != "confirmed":
            continue
        confirmed += 1
        if result.group_key == "":
            continue
        if result.group_key not in counts:
            counts[result.group_key] = 0
            texts[result.group_key] = result.group_text
            order.append(result.group_key)
        counts[result.group_key] += 1

    if confirmed < 2:
        return ()

    groups = sorted(order, key=lambda key: (-counts[key], key))
    lines: list[str] = []
    for key in groups:
        n = counts[key]
        if n < 2:
            continue
        if len(lines) == 4:
            lines.append("[truncated by kubeagent]")
            return tuple(lines)
        lines.append(f"{n} workloads share one upstream cause: {texts[key]}")
    if not lines:
        return (f"no shared cause among the {confirmed} workloads confirmed by rules",)
    return tuple(lines)


def label(lines: tuple[str, ...]) -> str:
    """Classify shared()'s output into the job-3 label kubeagent-verdict trains on.

    `()` (fewer than 2 confirmed) -> "none". A single fallback line
    starting "no shared cause among the" -> "separate". Anything else (one
    or more real shared-cause lines, with or without the truncation
    marker) -> "shared".
    """
    if not lines:
        return "none"
    if len(lines) == 1 and lines[0].startswith("no shared cause among the"):
        return "separate"
    return "shared"


def read_text(obj: Object, *, ns: str, pod: str) -> tuple[str, str]:
    """Port of reader.go's describeNode/describePVC and gather.go's read label.

    Returns (trail label, content) in the shape gather.go's appendRead
    records for a node or PVC candidate's fresh read. Only "node" and "pvc"
    kinds have a read here — a registry candidate's fresh read is the pulling
    pod's events, out of scope for this function (see the module docstring).
    Calling this with a registry object raises ValueError.

    Every line this function writes itself is byte-for-byte the Go format: the
    label, the `read failed: ` prefix, the node's `unschedulable=` line and the
    whole PVC line. The node's condition and taint lines are not written here.
    describeNode builds one line per condition and one per taint, in the
    node's own order, with the reason and message sanitized; this port takes
    them ready-made from `fresh.extra` and joins them. So their fidelity is
    the fixture author's, not this function's, and `fresh.ready` is not read
    at all — a node's Ready condition reaches the content only because
    `extra` carries it.

    `pod` is accepted for signature symmetry with the events read this
    function does not cover; neither the node nor the PVC read format uses
    it.
    """
    if obj.kind == "registry":
        raise ValueError(
            f"read_text: registry {obj.name!r} has no object to read "
            '(gather.go: "registry: no object to read")'
        )
    fresh = obj.fresh
    if obj.kind == "node":
        trail_label = f"describe node /{obj.name}"
        if fresh.how == "read_failed":
            return trail_label, f"read failed: {fresh.message}"
        lines = [f"node {obj.name}: unschedulable={'true' if fresh.unschedulable else 'false'}"]
        lines.extend(fresh.extra)
        return trail_label, "\n".join(lines) + "\n"
    # obj.kind == "pvc"
    trail_label = f"describe pvc {ns}/{obj.name}"
    if fresh.how == "read_failed":
        return trail_label, f"read failed: {fresh.message}"
    content = f"pvc {ns}/{obj.name}: phase={fresh.phase} storageClass={fresh.storage_class} volume={fresh.volume}\n"
    return trail_label, content


def check_declaration(entry_key: str, objects: tuple[Object, ...]) -> None:
    """Wraps objects.check_objects with the rules-only checks it cannot make.

    objects.check_objects() only knows the closed vocabularies; it has no
    view of attribute()'s own logic. This adds the one check attribute()
    would otherwise silently absorb: a declared object marked
    `intent == "cause"` must actually be capable of WINNING attribution —
    otherwise the story's own claim ("this is the cause") is false, and
    attribute() would quietly turn it into a ruled_out candidate instead.

    - node cause: placement must be "on".
    - pvc cause: placement must be "mounted".
    - registry cause: name must be non-empty, and its scan_reason (the
      puller count) must clear REGISTRY_THRESHOLD.

    Raises ValueError naming the entry and the object, same shape as
    objects.check_objects.
    """
    ds_objects.check_objects(entry_key, objects)
    for obj in objects:
        if obj.intent != "cause":
            continue
        if obj.kind == "node" and obj.placement != "on":
            raise ValueError(
                f"entry {entry_key}: object node/{obj.name} is declared as the cause but "
                'placement is not "on" — attribute() would rule it out'
            )
        if obj.kind == "pvc" and obj.placement != "mounted":
            raise ValueError(
                f"entry {entry_key}: object pvc/{obj.name} is declared as the cause but "
                'placement is not "mounted" — attribute() would rule it out'
            )
        if obj.kind == "registry":
            if obj.name == "":
                raise ValueError(
                    f"entry {entry_key}: object registry/{obj.name!r} is declared as the cause "
                    'but has no name — attribute() would rule it out as "registry unknown"'
                )
            if int(obj.scan_reason) < REGISTRY_THRESHOLD:
                raise ValueError(
                    f"entry {entry_key}: object registry/{obj.name} is declared as the cause but "
                    f"scan_reason={obj.scan_reason!r} is below REGISTRY_THRESHOLD "
                    f"({REGISTRY_THRESHOLD}) — attribute() would rule it out"
                )
