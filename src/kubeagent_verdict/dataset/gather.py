"""kubeagent's evidence gather, and the text layer under it.

Local verdict mode reads before the model answers. kubeagent picks the
reads itself, under a budget of 8, and its rules then re-check each
candidate cause against what came back. This module ports that from
kubeagent v1.24.0.

The text layer, byte for byte:

- `safetext_line` is `safetext.Line` (internal/safetext/safetext.go:69-107).
- `_sanitize` is the investigate package's `sanitize`: clean first, then
  redact addresses (internal/investigate/reader.go:88-90).
- `format_events` is `formatEvents` (internal/investigate/reader.go:312-322).
- `CRASH_FAMILY` names the issues whose previous log kubeagent reads.

The gather:

- `gather` runs the whole chain for one row of flagged workloads. It sizes
  each registry group (internal/rootcause/rootcause.go:99-139), scopes the
  row to its first 10 workloads (internal/investigate/gather.go:28-43),
  makes the reads in kubeagent's order (internal/investigate/gather.go:57-157),
  then decides each scoped workload (internal/investigate/local.go:216-219).
  It also says what it did with each candidate and each finding: a `Step`.
- The registry rule reads the pulling pod's events: `_pull_pod`,
  `_events_pod`, `_registry_fresh`, `_is_pull_event`, `_first_match` and
  `_classify_pull_events` port internal/hypothesis/decide.go:139-230.
  `rules.decide` writes the sentence.
- `pair_candidates` sets each decision beside its candidate, as the prompt
  prints them (internal/investigate/prime.go:80-104).

A node or PVC declares what its read would find. The gather decides
whether the read happens: an object the budget never reached is re-checked
as `not_read`. A registry declares neither its count nor its fresh state;
the gather works out both from the row.

The character rules lean on Unicode tables: Python's `unicodedata` here,
Go's `unicode` there. Python 3.12 and Go 1.26 both ship Unicode 15.0.0, so
the two agree on every character. Pure: no I/O, no state.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Sequence

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import rules

# The rune budget for one cleaned line, the ellipsis included
# (internal/safetext/safetext.go:28).
MAX_LINE = 512
# How many combining marks one base character may carry
# (internal/safetext/safetext.go:40).
MAX_COMBINING = 4

# The issues that mean a container crashed, so kubeagent reads and
# classifies its previous log (`crashFamily`,
# internal/investigate/gather.go:195-197).
CRASH_FAMILY = ("CrashLoopBackOff", "ContainerStartError", "OOMKilled")

# The whitespace controls and line separators that become a space
# (internal/safetext/safetext.go:79).
_FOLD = frozenset("\t\n\v\f\r\u2028\u2029")
# A run of lone surrogates. A str cannot hold bytes that are not UTF-8;
# decoding with errors="surrogateescape" keeps each one as a lone surrogate.
_SURROGATES = re.compile(r"[\ud800-\udfff]+")


def safetext_line(s: str) -> str:
    """Return `s` fit to print, as kubeagent's `safetext.Line` does.

    Four rules, in Go's order:

    1. Bytes that are not UTF-8 become U+FFFD, one for each run. Here they
       arrive as lone surrogates.
    2. Tab, newline, carriage return, vertical tab, form feed, U+2028 and
       U+2029 become a space. Every other control (Cc) and format (Cf)
       character is dropped.
    3. A combining mark (category M) is kept only while its base character
       carries fewer than MAX_COMBINING of them. A space is not a base, and
       a character dropped by rule 2 does not break the link to the base.
    4. The result is trimmed. Past MAX_LINE runes it is cut to one rune
       short, marks left at the cut go too, and "…" ends it.

    Idempotent: safetext_line(safetext_line(s)) == safetext_line(s).
    """
    # Rule 1 (safetext.go:70): strings.ToValidUTF8 writes one U+FFFD for
    # each run of bad bytes.
    s = _SURROGATES.sub("\ufffd", s)
    out = []
    base = False  # a base character is there for a mark to sit on
    marks = 0     # marks already on it
    for ch in s:
        # Rule 2 (safetext.go:78-84).
        if ch in _FOLD:
            ch = " "
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf"):
            continue  # dropped, and the base it interrupts outlives it
        # Rule 3 (safetext.go:85-94).
        if ch == " ":
            base, marks = False, 0
        elif cat[0] == "M":
            if not base or marks == MAX_COMBINING:
                continue
            marks += 1
        else:
            base, marks = True, 0
        out.append(ch)
    # Rule 4 (safetext.go:98-105). str.strip() also trims U+001C-U+001F,
    # which Go's TrimSpace does not, but rule 2 has already dropped them.
    s = "".join(out).strip()
    if len(s) > MAX_LINE:
        cut = s[:MAX_LINE - 1]
        while cut and unicodedata.category(cut[-1])[0] == "M":
            cut = cut[:-1]
        return cut + "…"
    return s


def _sanitize(s: str) -> str:
    """Clean one free-text field read from the cluster, such as an event's
    reason or message.

    Clean first, then redact, as kubeagent's `sanitize` does
    (internal/investigate/reader.go:88-90). A format character can sit
    inside an address and split it. Cleaning first joins the address back
    together, so the redaction still finds it.
    """
    return c.redact_addresses(safetext_line(s))


def format_events(namespace: str, name: str,
                  events: Sequence[tuple[str, str, int]]) -> str:
    """The events read's content, as kubeagent's `formatEvents` writes it
    (internal/investigate/reader.go:312-322).

    `events` holds (reason, message, count) tuples in the order kubeagent
    listed them. The reason and message are cleaned. The namespace and name
    are not: the API server already checks them. The count prints as it
    is, so 0 and 1 have no special form. With no events the content is one
    line with no newline at its end.
    """
    if not events:
        return f"no events for {namespace}/{name}"
    lines = [f"events for {namespace}/{name}:\n"]
    for reason, message, count in events:
        lines.append(f"  {_sanitize(reason)}: {_sanitize(message)} (x{count})\n")
    return "".join(lines)


# --- the gather ------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class GatherFinding:
    """One finding of a flagged workload, as the gather sees it.

    - `pod` is "namespace/name", like kubeagent's `Finding.Pod`.
    - `image` is the finding's image reference. Only a pull finding's image
      is used: the first one sets the workload's registry host.
    - `log_read` is the content of the log read kubeagent makes for this
      finding. It is set exactly when kubeagent reads a log for it: a
      crash-family issue, a container, and a pod with a namespace. It is
      None on every other finding.
    """

    issue: str
    pod: str
    container: str = ""
    log_read: str | None = None
    image: str = ""


@dataclasses.dataclass(frozen=True)
class GatherWorkload:
    """One flagged workload, and what the cluster answers when read.

    - `pod` and `issue` go to `rules.attribute`. The pod is the name its
      reasons print, and the issue decides whether a registry is a
      candidate.
    - `objects` is the workload's menu. A node or PVC declares what its
      describe finds. A registry is named for the first pull finding's host;
      its `scan_reason` and `fresh` are ignored, because the gather works
      out both.
    - `events` is what the events read of the workload's events pod lists:
      (reason, message, count) tuples, in list order, messages raw.
    - `events_failed` is the error of a refused events read, as kubeagent's
      `redact.Error` gives it, raw. It and `events` are never both set.
    """

    namespace: str
    name: str
    pod: str
    issue: str
    objects: tuple[o.Object, ...] = ()
    events: tuple[tuple[str, str, int], ...] = ()
    findings: tuple[GatherFinding, ...] = ()
    events_failed: str = ""


# What the gather did with one candidate, checked in the gather's own order
# (internal/investigate/gather.go:92-133):
#   budget     it stopped first: 8 reads were already made;
#   ruled_out  the verdict is ruled_out, so there is nothing to read;
#   no_object  the candidate names no object;
#   registry   a registry has no object to describe;
#   deduped    an earlier candidate in the row already read this object;
#   read       it described the object.
CANDIDATE_ACTIONS = ("budget", "ruled_out", "no_object", "registry", "deduped", "read")
# What the gather did with one finding (internal/investigate/gather.go:135-154):
#   budget   it stopped first;
#   skip     not a crash-family issue, no container, or no pod name;
#   deduped  an earlier finding in the row already read this container's log;
#   read     it read the previous log.
FINDING_ACTIONS = ("budget", "skip", "deduped", "read")


@dataclasses.dataclass(frozen=True)
class Step:
    """What the gather did with one candidate or one finding.

    `action` is one of CANDIDATE_ACTIONS or FINDING_ACTIONS. `ref` is the
    1-based place in `GatherResult.reads` of the read the step made (`read`)
    or reused (`deduped`). It is 0 for every other action.
    """

    action: str
    ref: int = 0


@dataclasses.dataclass(frozen=True)
class GatherResult:
    """What the gather read, and what the rules made of it.

    - `reads` is the evidence trail, in read order, at most MAX_TOOL_CALLS.
    - `candidates` and `results` hold one entry for each workload in the
      scope, the first MAX_GATHER_WORKLOADS, in row order. A candidate
      carries its fresh-read outcome and evidence when it has a decision.
    - `candidate_steps` and `finding_steps` also hold one entry per scoped
      workload: one `Step` per candidate, in trace order, and one per
      finding, in finding order. They say which read each object and each
      log came from, or why there was none. Every step of a workload the
      budget never reached is `budget`.
    - A workload past the scope has no entry in any of them. It gets no
      reads and no decision. It still counts toward its registry group.
    """

    reads: tuple[c.EvidenceRead, ...]
    candidates: tuple[tuple[c.Candidate, ...], ...]
    results: tuple[rules.Result, ...]
    candidate_steps: tuple[tuple[Step, ...], ...]
    finding_steps: tuple[tuple[Step, ...], ...]


def _pod_part(pod: str) -> str:
    """The name half of "namespace/name", or "" when there is no slash
    (`podPart`, internal/investigate/gather.go:186-191 and
    internal/hypothesis/decide.go:162-167)."""
    _, sep, name = pod.partition("/")
    return name if sep else ""


def _events_pod(w: GatherWorkload) -> str:
    """The pod whose events the gather reads: the first finding's pod, else
    the workload name (internal/investigate/gather.go:75-80; `eventsPod`,
    internal/hypothesis/decide.go:151-158)."""
    if w.findings:
        pod = _pod_part(w.findings[0].pod)
        if pod:
            return pod
    return w.name


def _pulls(w: GatherWorkload) -> list[GatherFinding]:
    """The pull findings, in finding order."""
    return [f for f in w.findings if f.issue in rules.REGISTRY_ISSUES]


def _pull_pod(w: GatherWorkload) -> str:
    """The first pull finding's pod, or "" (`pullPod`,
    internal/hypothesis/decide.go:139-146)."""
    pulls = _pulls(w)
    return _pod_part(pulls[0].pod) if pulls else ""


def _registry_host(image: str) -> str:
    """The registry an image is pulled from (`registryHost`,
    internal/rootcause/rootcause.go:158-164). The first segment is a host
    when it holds "." or ":", or is "localhost". Otherwise the image is on
    Docker Hub, and kubeagent names it "docker.io"."""
    seg, sep, _ = image.partition("/")
    if not sep or (not any(ch in seg for ch in ".:") and seg != "localhost"):
        return "docker.io"
    return seg


def _reads_log(f: GatherFinding) -> bool:
    """Whether kubeagent reads a log for this finding
    (internal/investigate/gather.go:139-145)."""
    return f.issue in CRASH_FAMILY and f.container != "" and _pod_part(f.pod) != ""


def _go_lower(s: str) -> str:
    """Lowercase `s` the way Go's `strings.ToLower` does, as far as matching
    an ASCII literal can tell.

    Go maps each rune on its own. Python's `str.lower` uses the full
    mapping, and only one character comes out different in a way an ASCII
    literal can see: U+0130 is "i" in Go and "i" plus U+0307 in Python.
    """
    return s.replace("\u0130", "i").lower()


def _is_pull_event(reason: str, message: str) -> bool:
    """A kubelet pull failure: reason Failed or BackOff, and a message that
    mentions a pull (`isPullEvent`, internal/hypothesis/decide.go:191-196)."""
    return reason in ("Failed", "BackOff") and "pull" in _go_lower(message)


def _first_match(msgs: Sequence[str], literals: Sequence[str]) -> str:
    """The first literal, in list order, that any message holds, or ""
    (`firstMatch`, internal/hypothesis/decide.go:221-230)."""
    for lit in literals:
        for m in msgs:
            if lit in m:
                return lit
    return ""


def _classify_pull_events(events: Sequence[tuple[str, str, int]]) -> str:
    """The literal the registry rule quotes, or "" when no pull event names
    one (`classifyPullEvents`, internal/hypothesis/decide.go:200-217).

    Connection beats auth, and auth beats image. The match runs on the raw
    message, lowercased: a format character inside a literal hides it here,
    though the events read prints the message cleaned. `rules.decide` turns
    the literal into the outcome and the sentence.
    """
    msgs = [_go_lower(message) for reason, message, _ in events
            if _is_pull_event(reason, message)]
    for literals in (o.CONNECTION_LITERALS, o.AUTH_LITERALS, o.IMAGE_LITERALS):
        lit = _first_match(msgs, literals)
        if lit:
            return lit
    return ""


def _registry_fresh(w: GatherWorkload, events_ok: dict[str, tuple[tuple[str, str, int], ...]],
                    events_failed: dict[str, str]) -> o.Fresh:
    """What a live registry candidate's re-check finds (`checkRegistry`,
    internal/hypothesis/decide.go:172-187).

    Any workload's events read counts, not only this one's: the rule looks
    up the pulling pod's events wherever they were read.
    """
    pod = _pull_pod(w)
    key = f"{w.namespace}/{pod}"
    if pod:
        if key in events_ok:
            return o.Fresh(literal=_classify_pull_events(events_ok[key]))
        if key in events_failed:
            return o.Fresh(how="read_failed", message=events_failed[key])
    if not pod or pod != _events_pod(w):
        return o.Fresh(wrong_pod=True)
    return o.Fresh(how="not_read")


def _registry_counts(workloads: Sequence[GatherWorkload]) -> dict[str, int]:
    """How many workloads fail to pull from each host (`AnnotateRegistry`,
    internal/rootcause/rootcause.go:99-139).

    The count spans the whole row, not just the scope: kubeagent's scan
    annotates every workload (internal/scan/scan.go:815-817) before the
    gather scopes them. A workload joins its host's group when its first
    pull finding names an image and no node or PVC already won it.
    """
    counts: dict[str, int] = {}
    for w in workloads:
        pulls = _pulls(w)
        if not pulls or not pulls[0].image:
            continue  # rootcause.go:104-110: no pull finding, or "registry unknown"
        others = tuple(obj for obj in w.objects if obj.kind != "registry")
        trace = rules.attribute(others, ns=w.namespace, pod=w.pod, issue=w.issue)
        if any(cand.verdict == "attributed" for cand in trace):
            continue  # rootcause.go:112-116: outranked, not grouped
        host = _registry_host(pulls[0].image)
        counts[host] = counts.get(host, 0) + 1
    return counts


def _object_key(obj: o.Object, namespace: str) -> str:
    """The describe dedup key (internal/investigate/gather.go:102-106). A
    node has no namespace."""
    ns = namespace if obj.kind == "pvc" else ""
    return f"{obj.kind}/{ns}/{obj.name}"


def _check(workloads: Sequence[GatherWorkload]) -> None:
    """Refuse a row the gather cannot read the way kubeagent would.

    One object has one state, one pod has one events list, and one
    container has one log, wherever they appear in the row. Raises
    ValueError naming the workload.
    """
    objects: dict[str, tuple[str, o.Fresh]] = {}
    events: dict[str, tuple[tuple[tuple[str, str, int], ...], str]] = {}
    logs: dict[str, str | None] = {}
    for w in workloads:
        where = f"workload {w.namespace}/{w.name}"
        seen: set[str] = set()
        for obj in w.objects:
            if f"{obj.kind}/{obj.name}" in seen:
                raise ValueError(f"{where}: object {obj.kind}/{obj.name} is declared twice")
            seen.add(f"{obj.kind}/{obj.name}")
            if obj.kind == "registry":
                continue
            key = _object_key(obj, w.namespace)
            if obj.fresh.how == "read_failed" and safetext_line(obj.fresh.message) != obj.fresh.message:
                raise ValueError(f"{where}: object {key}: a read_failed message must be clean "
                                 "text, since the read and the rules share it")
            state = (obj.scan_reason, obj.fresh)
            if objects.setdefault(key, state) != state:
                raise ValueError(f"{where}: object {key} has another scan reason or fresh "
                                 "state in an earlier workload")

        if w.events and w.events_failed:
            raise ValueError(f"{where}: events and events_failed are both set")
        if w.events_failed and not safetext_line(w.events_failed):
            raise ValueError(f"{where}: events_failed cleans to nothing")
        pod_key = f"{w.namespace}/{_events_pod(w)}"
        answer = (tuple(w.events), w.events_failed)
        if events.setdefault(pod_key, answer) != answer:
            raise ValueError(f"{where}: pod {pod_key} has other events in an earlier workload")

        for f in w.findings:
            if not _reads_log(f):
                if f.log_read is not None:
                    raise ValueError(f"{where}: {f.issue} on {f.pod}: kubeagent reads no log "
                                     "for this finding, so log_read must be None")
                continue
            if f.log_read is None:
                raise ValueError(f"{where}: {f.issue} on {f.pod} container {f.container}: "
                                 "kubeagent reads this log, so log_read must be set")
            log_key = f"{w.namespace}/{_pod_part(f.pod)}/{f.container}"
            if logs.setdefault(log_key, f.log_read) != f.log_read:
                raise ValueError(f"{where}: container {log_key} has two log_read values")

        pulls = _pulls(w)
        registries = [obj for obj in w.objects if obj.kind == "registry"]
        if len(registries) > 1:
            raise ValueError(f"{where}: a workload pulls from one registry, not {len(registries)}")
        if pulls and not registries:
            raise ValueError(f"{where}: a pull finding needs a registry object")
        if registries and not pulls:
            raise ValueError(f"{where}: a registry object needs a pull finding")
        if not registries:
            continue
        if w.issue not in rules.REGISTRY_ISSUES:
            raise ValueError(f"{where}: a registry object needs a pull issue, not {w.issue!r}")
        host = _registry_host(pulls[0].image) if pulls[0].image else ""
        if registries[0].name != host:
            raise ValueError(f"{where}: registry {registries[0].name!r} must be named "
                             f"{host!r}, the first pull finding's host")
        if safetext_line(host) != host:
            raise ValueError(f"{where}: registry host {host!r} must be clean text")


def _check_live(w: GatherWorkload, trace: Sequence[rules.Candidate]) -> None:
    """A live node or PVC declares what its read finds. Whether the read
    happens is the gather's call, so it may not declare `not_read`. A
    ruled-out one is never read, and may."""
    for cand in trace:
        if (cand.verdict != "ruled_out" and cand.obj.kind != "registry"
                and cand.obj.fresh.how == "not_read"):
            raise ValueError(f"workload {w.namespace}/{w.name}: {cand.cause} is "
                             f"{cand.verdict}, so it may not declare not_read")


def pair_candidates(candidates: Sequence[rules.Candidate],
                    result: rules.Result) -> tuple[c.Candidate, ...]:
    """Set each decision beside the candidate it re-checked, as the prompt
    prints them (internal/investigate/prime.go:80-104).

    A ruled-out candidate has no decision and does not move the cursor.
    Every other candidate takes the next decision. Go trusts the two to
    line up and prints nothing past a short list. Here they must line up
    one for one, or this raises ValueError. Every candidate is paired; the
    cap of 8 is `contract.render_candidates`' job.
    """
    live = [cand for cand in candidates if cand.verdict != "ruled_out"]
    if len(live) != len(result.decisions):
        raise ValueError(f"pair_candidates: {len(live)} candidates to re-check, "
                         f"but {len(result.decisions)} decisions")
    paired: list[c.Candidate] = []
    nxt = 0
    for cand in candidates:
        if cand.verdict == "ruled_out":
            paired.append(c.Candidate(cand.cause, cand.verdict, cand.reason))
            continue
        d = result.decisions[nxt]
        if d.candidate != cand.cause:
            raise ValueError(f"pair_candidates: decision {nxt} is for {d.candidate!r}, "
                             f"not {cand.cause!r}")
        paired.append(c.Candidate(cand.cause, cand.verdict, cand.reason, d.outcome, d.evidence))
        nxt += 1
    return tuple(paired)


def gather(workloads: Sequence[GatherWorkload]) -> GatherResult:
    """Read one row of flagged workloads the way kubeagent's local verdict
    mode does, then decide each one.

    1. Check the row, and size each registry group over the whole row.
    2. Scope to the first MAX_GATHER_WORKLOADS workloads
       (internal/investigate/gather.go:28-43).
    3. Read, per workload, until MAX_TOOL_CALLS reads are made
       (internal/investigate/gather.go:71-156): the events of its events
       pod, a describe per live node or PVC candidate (once per object
       across the row), then a log per crash-family container (once per
       container). A refused read still costs one.
    4. Re-check each scoped workload's live candidates against the reads
       (internal/investigate/local.go:216-219). A node or PVC nobody read
       is `not_read`. A registry reads its pulling pod's events.

    Raises ValueError on a row it cannot read faithfully; see `_check`.
    """
    _check(workloads)
    counts = _registry_counts(workloads)
    filled = [
        dataclasses.replace(w, objects=tuple(
            dataclasses.replace(obj, scan_reason=str(counts.get(obj.name, 0)))
            if obj.kind == "registry" else obj
            for obj in w.objects))
        for w in workloads
    ]
    traces = []
    for w in filled:
        trace = rules.attribute(w.objects, ns=w.namespace, pod=w.pod, issue=w.issue)
        _check_live(w, trace)
        traces.append(trace)
    scoped = list(zip(filled, traces))[:c.MAX_GATHER_WORKLOADS]

    reads: list[c.EvidenceRead] = []
    described: dict[str, int] = {}  # dedup key -> the read's 1-based place
    logged: dict[str, int] = {}
    events_ok: dict[str, tuple[tuple[str, str, int], ...]] = {}
    events_failed: dict[str, str] = {}
    candidate_steps: list[list[Step]] = [[] for _ in scoped]
    finding_steps: list[list[Step]] = [[] for _ in scoped]
    for (w, trace), cand_steps, find_steps in zip(scoped, candidate_steps, finding_steps):
        if len(reads) >= c.MAX_TOOL_CALLS:
            break
        pod = _events_pod(w)
        key = f"{w.namespace}/{pod}"
        if w.events_failed:
            # gather.go:84-85: the rules see it cleaned, the read shows it raw.
            events_failed[key] = safetext_line(w.events_failed)
            content = "read failed: " + w.events_failed
        else:
            events_ok[key] = w.events
            content = format_events(w.namespace, pod, w.events)
        reads.append(c.EvidenceRead(f"events {key}", content))

        for cand in trace:
            if len(reads) >= c.MAX_TOOL_CALLS:
                break
            obj = cand.obj
            if cand.verdict == "ruled_out":
                cand_steps.append(Step("ruled_out"))
                continue
            if obj.name == "":
                cand_steps.append(Step("no_object"))
                continue
            if obj.kind not in ("node", "pvc"):
                cand_steps.append(Step("registry"))  # gather.go:100: no object to read
                continue
            obj_key = _object_key(obj, w.namespace)
            if obj_key in described:
                cand_steps.append(Step("deduped", described[obj_key]))
                continue
            reads.append(c.EvidenceRead(*rules.read_text(obj, ns=w.namespace, pod=w.pod)))
            described[obj_key] = len(reads)
            cand_steps.append(Step("read", len(reads)))

        for f in w.findings:
            if len(reads) >= c.MAX_TOOL_CALLS:
                break
            if not _reads_log(f):
                find_steps.append(Step("skip"))
                continue
            log_key = f"{w.namespace}/{_pod_part(f.pod)}/{f.container}"
            if log_key in logged:
                find_steps.append(Step("deduped", logged[log_key]))
                continue
            reads.append(c.EvidenceRead(
                f"log causes {w.namespace}/{_pod_part(f.pod)} container {f.container}",
                f.log_read))
            logged[log_key] = len(reads)
            find_steps.append(Step("read", len(reads)))

    candidates: list[tuple[c.Candidate, ...]] = []
    results: list[rules.Result] = []
    for w, trace in scoped:
        final = []
        for cand in trace:
            obj = cand.obj
            if cand.verdict == "ruled_out":
                pass
            elif obj.kind == "registry":
                fresh = _registry_fresh(w, events_ok, events_failed)
                cand = dataclasses.replace(cand, obj=dataclasses.replace(obj, fresh=fresh))
            elif _object_key(obj, w.namespace) not in described:
                cand = dataclasses.replace(
                    cand, obj=dataclasses.replace(obj, fresh=o.Fresh(how="not_read")))
            final.append(cand)
        result = rules.decide(tuple(final))
        results.append(result)
        candidates.append(pair_candidates(final, result))
    # The loop stops at the budget: every step it never reached is `budget`.
    budget = Step("budget")
    return GatherResult(
        tuple(reads), tuple(candidates), tuple(results),
        candidate_steps=tuple(
            tuple(steps) + (budget,) * (len(trace) - len(steps))
            for steps, (_, trace) in zip(candidate_steps, scoped)),
        finding_steps=tuple(
            tuple(steps) + (budget,) * (len(w.findings) - len(steps))
            for steps, (w, _) in zip(finding_steps, scoped)))
