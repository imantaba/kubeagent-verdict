"""Check a finished row against what kubeagent v1.24.0 can send.

The checker is an independent text parser. It reads the system prompt, the
user message and the answer of a finished row, and nothing else. It never
rebuilds a row from the row's own data, and it imports nothing from this
package: every kubeagent string it needs is its own copy below, and each
copy cites the Go line it comes from (internal/<path>.go:<line> at v1.24.0).
tests/test_checker.py pins each copy the builder also holds.

Each rule is one function. It returns how many lines (or items) it looked
at and where the row differs from kubeagent. `check` parses the prompt once
and runs every rule over that parse. A `where` names a section line
(`inventory line 4`, `candidates app/api line 7`, both counted from 1), an
evidence read (`evidence read 0 (events app/api-6d5f)`, counted from 0 like
the spec's "read index 0"), `answer`, `prompt` or `system`.

What the checker reads from `meta`, and nothing else:

- `meta["case"]`: rows of the four shared-origin cases skip the evidence
  rules and the rules propagation.py's own text fails (EXEMPT_CASES,
  EVIDENCE_RULES, PROPAGATION_TEXT_RULES).
- `meta["origin_read_label"]`: the healthy-origin read at index 0 is left
  out of the gathered reads (`_Ctx.gathered`) and so out of the per-workload
  read groups. The rules that walk those, E2-order, E4 and E6-E10 among
  them, never see it. It still counts toward E1, and E3, E5, the F rules
  and the TXT rules still read it.
- the keys of `meta["workloads"]`: ANS-1's workload set.
- each workload's `own_cause_keywords`: ANS-2.

With `meta=None` (the golden file has none), no exemption applies, ANS-1
skips its meta clause, ANS-2 is skipped, and every other rule runs.

A few rules check the builder's own model where kubeagent's output depends
on cluster state the prompt does not show (B7's node count, for one). Each
such rule says so.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cache
from itertools import pairwise
from pathlib import Path

# --- kubeagent's limits --------------------------------------------------

MAX_PROMPT_BYTES = 64 * 1024        # investigate/local.go:28
MAX_SERVICE_ISSUES = 10             # investigate/local.go:27
MAX_TOOL_CALLS = 8                  # investigate/investigate.go:22
MAX_READ_BYTES = 4096               # investigate/gather.go:23
MAX_GATHER_WORKLOADS = 10           # investigate/gather.go:24
MAX_CANDIDATES_PER_WORKLOAD = 8     # investigate/prime.go:38
MAX_FINDING_BLOCKS_PER_WORKLOAD = 3  # explain/explain.go:238
MAX_MODEL_LINE_RUNES = 512          # investigate/local.go:113
MAX_LINE = 512                      # safetext/safetext.go:28
MAX_COMBINING = 4                   # safetext/safetext.go:40
RESTART_THRESHOLD = 3               # diagnose/restartloop.go:15
REGISTRY_THRESHOLD = 2              # rootcause/rootcause.go:127-133
NOT_READY_MESSAGE_RUNES = 120       # clusterhealth/clusterhealth.go:206
SYSTEM_NAMESPACE = "kube-system"    # clusterhealth/clusterhealth.go:18

# --- kubeagent's fixed strings -------------------------------------------

# The section frame: section() and the closing sentence
# (investigate/local.go:57-63 and :81).
SECTIONS = ("inventory", "candidates", "evidence")
CLOSING_INSTRUCTION = "Judge each listed workload now and answer with the JSON object only."
NONE_BODY = "(none)"                                   # investigate/local.go:59
TRUNCATION_MARKER = "[truncated by kubeagent]"         # investigate/gather.go:25
# The three verdict words, as prime.go prints them: "_" becomes " "
# (inventory/inventory.go:79-81, investigate/prime.go:69).
VERDICTS = ("attributed", "ruled out", "outranked")
# The three fresh-read outcomes (hypothesis/hypothesis.go:34-36).
OUTCOMES = ("confirmed", "refuted", "unverified")
# The issues whose previous log the gather classifies
# (investigate/gather.go:195-197).
CRASH_FAMILY = ("CrashLoopBackOff", "ContainerStartError", "OOMKilled")
# The pull issues a registry candidate and its fresh read key on
# (rootcause/rootcause.go:155, hypothesis/decide.go:141).
PULL_ISSUES = ("ImagePullBackOff", "ErrImagePull")
# A down node's reasons (clusterhealth/clusterhealth.go:38) and a PVC
# issue's reasons (pvchealth/pvchealth.go:27).
NODE_REASONS = ("NotReady", "no kubelet lease", "kubelet not heartbeating")
PVC_REASONS = ("ProvisioningFailed", "FailedBinding", "MissingStorageClass",
               "NoMatchingPV", "PVSelectorMismatch", "ProvisionerNotResponding")
# ForRootCause's cause prefixes (confidence/confidence.go:36-47).
CONFIDENCE_BY_PREFIX = (("node ", "high"), ("PVC ", "high"), ("registry ", "medium"))
# The closed pull-event literals (hypothesis/decide.go:125-131).
CONNECTION_LITERALS = (
    "dial tcp", "i/o timeout", "connection refused", "connection reset",
    "no such host", "network is unreachable", "tls handshake", "x509:",
    "502 bad gateway", "503 service unavailable", "504 gateway timeout",
    "toomanyrequests", "429 too many requests",
)
AUTH_LITERALS = ("pull access denied", "no basic auth credentials", "unauthorized", "denied")
IMAGE_LITERALS = (
    "manifest unknown", "not found", "name unknown",
    "repository does not exist", "invalid reference format",
)
# The ten causes logscan.Classify returns (logscan/logscan.go:31, 32, 46,
# 48, 49, 62, 67, 68, 69 and the fallback at 126).
LOG_CAUSES = (
    "application panic (code bug)",
    "bad command or entrypoint",
    "cannot reach a dependency — connection refused",
    "DNS resolution failed (name lookup)",
    "ran out of memory in-process",
    "configuration parse/validation error",
    "port already in use",
    "authentication/authorization failure to a dependency",
    "permission denied — check securityContext / file permissions",
    "last output before exit (no signature in the last 25 lines)",
)
# A log read's fixed bodies (investigate/reader.go:473-487). `%q` of a
# container name only adds the double quotes.
LOG_REFUSED = ("reading the previous log of {ns}/{pod} was refused: "
               "this identity lacks the pods/log get permission")
LOG_NO_PREVIOUS = ('no previous-instance log for {ns}/{pod} container "{container}" '
                   "(nothing was refused; the container may not have restarted)")
LOG_NO_CLASSIFIABLE = 'the previous log of {ns}/{pod} container "{container}" has no classifiable output'
LOG_CAUSE_PREFIX = "log cause: "
# A failed read's content (investigate/gather.go:85, 117, 126).
READ_FAILED_PREFIX = "read failed: "

# The fresh-read evidence sentences (hypothesis/decide.go).
NEVER_READ = "not re-read: the read budget was spent first"          # decide.go:13
FAILED_PREFIX = "fresh read failed: "                                # decide.go:14
NO_RULE = "no rule re-checks this candidate kind"                    # decide.go:15
NODE_SENTENCES = {                                                   # decide.go:55-65
    "confirmed": ("the node has no Ready condition", "Ready condition is False now",
                  "Ready condition is Unknown now"),
    "refuted": ("Ready condition is True now",),
    "unverified": ("Ready condition is True, but the kubelet lease was not re-read",
                   "Ready condition is not one kubeagent expects"),
}
HEARTBEAT_REASONS = ("kubelet not heartbeating", "no kubelet lease")  # decide.go:49-51
PVC_SENTENCES = {                                                    # decide.go:86-92
    "confirmed": ("phase is still Pending", "phase is Lost"),
    "refuted": ("phase is Bound now",),
    "unverified": ("phase is not one kubeagent expects",),
}
NO_PULL_EVENT = "no pull event names the failure; events may have aged out"  # decide.go:134
PULL_POD_UNREAD = "events of the pulling pod were not read"                  # decide.go:135
_CONNECTION_SENTENCE = "a pull event shows a connection error: {}"           # decide.go:208
_AUTH_SENTENCE = "a pull event shows an auth error: {}; that can be one image or the whole host"  # :211
_IMAGE_SENTENCE = ("a pull event shows an image error: {}; "                  # decide.go:214
                   "this pull fails for this image, not the host")

# The verdict reasons rootcause writes (rootcause/rootcause.go).
NODE_RULED_OUT = "no pod of this workload is scheduled on it"                # rootcause.go:47
PVC_RULED_OUT = "not mounted by this workload's pods"                        # rootcause.go:214
REGISTRY_UNKNOWN_REASON = "image reference undeterminable"                   # rootcause.go:108
REGISTRY_BELOW_THRESHOLD = "only workload failing to pull from this host; threshold is 2"  # :128
_NODE_ATTRIBUTED = re.compile(r"^pod (\S+) is scheduled on it$")            # rootcause.go:50
_PVC_ATTRIBUTED = re.compile(r"^pod (\S+) mounts it$")                      # rootcause.go:217
_OUTRANKED = re.compile(r"^(.+) is the stronger cause$")                    # rootcause.go:52, 114, 219
_REGISTRY_ATTRIBUTED = re.compile(                                          # rootcause.go:133
    r"^(\d+) workloads failing to pull from this host clear the threshold of 2$")

# kubeagent's address pattern (redact/redact.go:44-47). Go's RE2 classes
# are ASCII, hence re.ASCII.
ADDR = re.compile(
    r"\[[0-9a-fA-F:]+\]:\d+"
    r"|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?"
    r"|\b[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+:\d+",
    re.ASCII,
)

# The system prompt kubeagent sends, as re-captured from
# investigate/local.go:34-45. Found the way generate.manifest finds data/.
_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[3] / "contract" / "system_prompt.txt"

# --- the rules and the exemptions ----------------------------------------

EXEMPT_CASES = frozenset({
    "shared_origin", "shared_origin_decoy", "shared_origin_probe", "shared_origin_decoy_probe",
})
# The shared-origin cases skip two sets of rules. The first is every rule
# that reads the evidence section.
EVIDENCE_RULES = frozenset({
    "E1", "E2-order", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E-min", "D3",
})
# The second: propagation.py writes its own inventory and candidate text, not
# only its reads, and these are the rules that text fails. Spec 4 rewrites it
# and removes both sets (spec lines 776-777). tests/test_checker.py checks
# that each rule here still fires on a shared-origin row.
PROPAGATION_TEXT_RULES = frozenset({
    "B1", "C1-conf", "C1-cause", "C5/D4", "D1-onefresh", "TXT-IS9", "TXT-IS11",
})


@dataclass(frozen=True)
class Violation:
    """One place a row differs from what kubeagent sends."""

    rule: str    # a RULES id, such as "C1-conf"
    where: str   # such as "candidates app/api line 3"
    quote: str   # the offending text, cut to 200 characters


@dataclass(frozen=True)
class Report:
    """Every violation in one row, and how much each rule looked at."""

    violations: tuple[Violation, ...]
    inspected: dict[str, int]


# --- the parse -----------------------------------------------------------

_FRAME = re.compile(
    r"== BEGIN inventory ==\n(?P<inventory>.*?)\n== END inventory ==\n\n"
    r"== BEGIN candidates ==\n(?P<candidates>.*?)\n== END candidates ==\n\n"
    r"== BEGIN evidence ==\n(?P<evidence>.*?)\n== END evidence ==\n\n"
    r"(?P<tail>.*)",
    re.DOTALL,
)
_SECTION_MARK = re.compile(r"^== (BEGIN|END) \S+ ==$")
_READ_SPLIT = re.compile(r"\n\n(?=== .* ==(?:\n|$))")
_READ_HEADER = re.compile(r"^== (.*) ==$")

# explain/explain.go:179-221 and :295-310.
_HEALTH_HEADER = re.compile(r"^Cluster health \(P1\): DEGRADED — (\d+)/(\d+) nodes Ready\.$")
_HEALTH_NODE = re.compile(
    r"^  node (\S+) (MemoryPressure|DiskPressure|PIDPressure|SchedulingDisabled|no kubelet lease"
    r"|kubelet not heartbeating \(lease \S+ stale\)|NotReady(?:: .+)?"
    r"|expected but absent from the cluster)$")
_HEALTH_SYSTEM = re.compile(r"^  system kube-system/(\S+) (?:(\d+)/(\d+) )?(\S+)$")
_CPU_LINE = re.compile(r"^  CPU: allocatable \S+ cores, requests \S+ \(\d+%\), limits \S+ \(\d+%\)"
                       r"(, usage \S+ \(\d+%\))?$")
_MEMORY_LINE = re.compile(r"^  Memory: allocatable \S+, requests \S+ \(\d+%\), limits \S+ \(\d+%\)"
                          r"(, usage \S+ \(\d+%\))?$")
_WORKLOAD_LINE = re.compile(r"^- (\S+)/(\S+) \((\S+)\): (\d+)/(\d+) ready, status ([^,]+), (\d+) restarts$")
_ISSUE_LINE = re.compile(r"^    issue: (\S+) — (.*?) \((.*)\)$")
_COLLAPSE = re.compile(r" \(×(\d+)\)$")
_ISSUE_PREFIX = "    issue: "
_LOG_CAUSE_LINE = "      log cause: "
_RESOURCES_LINE = re.compile(r"^      container resources: memory req=\S* limit=\S*, cpu req=\S* limit=\S*$")
_FIX_PREFIX = "      suggested fix (deterministic, pre-reviewed — do not substitute): "
_MORE_LINE = re.compile(r"^    … and (\d+) more of the same kind$")
_NETPOL_LINE = re.compile(r"^    network policy: pods selected by .+ \(possible cause\)$")
_ROLLOUT_PREFIX = "    recent change: rolled out to revision "
_SERVICE_LINE = re.compile(r"^  - (\S+)/(\S+) \((\S+)\): (.+)$")
_BLOCK_SHAPE = re.compile(r"^(?:(?:IL?R?F){3}M|(?:IL?R?F){0,3})$")

# investigate/prime.go:58-99.
_HEADING = re.compile(r"^- (\S+)/(\S+) \((\S+)\)( \[confidence: (\S+)\])?:$")
_CANDIDATE = re.compile(r"^    considered (.+?): (attributed|ruled out|outranked) — (.+)$")
_CANDIDATE_LOOSE = re.compile(r"^    considered (.+?): (.+?) — (.*)$")
_FRESH = re.compile(r"^      fresh read: (confirmed|refuted|unverified) — (.+)$")
_FRESH_LOOSE = re.compile(r"^      fresh read: (.*?) — (.*)$")
_MARKER_LINE = "    " + TRUNCATION_MARKER
_DECIDED = re.compile(r"^    decided by rules: (.+) — (\S+)$")

# The five cause shapes rootcause writes (rootcause/rootcause.go:44, 108,
# 113-114, 132, 211).
_NODE_CAUSE = re.compile(r"^node (\S+) \((NotReady|no kubelet lease|kubelet not heartbeating)\)$")
_REGISTRY_UNKNOWN = "registry unknown"
_REGISTRY_COUNTED = re.compile(r"^registry (\S+) \((\d+) workloads failing to pull\)$")
_REGISTRY_PLAIN = re.compile(r"^registry (\S+)$")
_PVC_CAUSE = re.compile(r"^PVC (\S+) \((" + "|".join(PVC_REASONS) + r")\)$")

# The four read labels (investigate/gather.go:90, 132, 153).
_EVENTS_LABEL = re.compile(r"^events (\S+)/(\S+)$")
_NODE_LABEL = re.compile(r"^describe node /(\S+)$")
_PVC_LABEL = re.compile(r"^describe pvc (\S+)/(\S+)$")
_LOG_LABEL = re.compile(r"^log causes (\S+)/(\S+) container (\S+)$")

# The read bodies (investigate/reader.go:238-257 and :312-322).
_EVENT_LINE = re.compile(r"^  (.+?): (.*) \(x(\d+)\)$")
_NODE_HEAD = re.compile(r"^node (\S+): unschedulable=(true|false)$")
_CONDITION_LINE = re.compile(r"^  condition ([^=\s]+)=(\S*) \((.*?)\): (.*)$")
_TAINT_LINE = re.compile(r"^  taint ([^=\s]+)=([^:\s]*):(\S+)$")
_PVC_BODY = re.compile(r"^pvc (\S+)/(\S+): phase=(\S*) storageClass=(\S*) volume=(\S*)$")
_READY_CONDITION = re.compile(r"^  condition Ready=(\S*) ", re.MULTILINE)


@dataclass
class _Line:
    no: int     # 1-based, within its section
    text: str


@dataclass
class _Entry:
    """One inventory workload: its `- ns/name (Kind): …` line and sub-lines."""

    line: _Line
    ns: str
    name: str
    kind: str
    match: re.Match | None
    subs: list[_Line] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.ns}/{self.name}"


@dataclass
class _Item:
    """One line under a candidate heading."""

    kind: str               # cand | fresh | marker | decided | other
    line: _Line
    strict: bool = False    # the strict regex matched
    cause: str = ""         # cand and decided
    verdict: str = ""       # cand
    reason: str = ""        # cand
    outcome: str = ""       # fresh and decided
    sentence: str = ""      # fresh
    fresh: list[_Item] = field(default_factory=list)  # cand: its fresh lines


@dataclass
class _Block:
    heading: _Line
    ns: str
    name: str
    kind: str
    tag: str | None
    items: list[_Item] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.ns}/{self.name}"

    @property
    def cands(self) -> list[_Item]:
        return [i for i in self.items if i.kind == "cand"]

    @property
    def truncated(self) -> bool:
        return any(i.kind == "marker" for i in self.items)

    def where(self, line: _Line) -> str:
        return f"candidates {self.key} line {line.no}"


@dataclass
class _Read:
    index: int
    label: str
    content: str

    @property
    def where(self) -> str:
        return f"evidence read {self.index} ({self.label})"

    @property
    def failed(self) -> bool:
        return self.content.startswith(READ_FAILED_PREFIX)

    @property
    def capped(self) -> bool:
        """The cut capContent makes (investigate/gather.go:174-183)."""
        return self.content.endswith("\n" + TRUNCATION_MARKER) or self.content == TRUNCATION_MARKER


@dataclass
class _Prompt:
    framed: bool = False
    inventory: str = ""
    candidates: str = ""
    evidence: str = ""
    tail: str = ""
    inv: list[_Line] = field(default_factory=list)
    health: list[_Line] = field(default_factory=list)
    entries: list[_Entry] = field(default_factory=list)
    services: list[_Line] = field(default_factory=list)
    stray: list[_Line] = field(default_factory=list)   # candidate lines before any heading
    blocks: list[_Block] = field(default_factory=list)
    reads: list[_Read] = field(default_factory=list)


def _lines(body: str) -> list[_Line]:
    return [_Line(i + 1, t) for i, t in enumerate(body.split("\n"))] if body else []


def _parse_inventory(p: _Prompt) -> None:
    p.inv = _lines(p.inventory)
    texts = [ln.text for ln in p.inv]
    if texts and texts[0].startswith("Cluster health (P1): "):
        end = texts.index("") if "" in texts else len(texts)
        p.health = p.inv[:end]
    service = texts.index("Service issues:") if "Service issues:" in texts else len(texts)
    if "Workload problems (P2):" in texts[:service]:
        entry = None
        for ln in p.inv[texts.index("Workload problems (P2):") + 1:service]:
            if ln.text.startswith("- "):
                m = _WORKLOAD_LINE.match(ln.text)
                head = re.match(r"^- ([^/\s]+)/(\S+) \((\S+)\)", ln.text)
                ns, name, kind = head.groups() if head else ("", ln.text[2:], "")
                entry = _Entry(ln, ns, name, kind, m)
                p.entries.append(entry)
            elif entry is not None and ln.text.startswith("    "):
                entry.subs.append(ln)
            else:
                entry = None
    p.services = [ln for ln in p.inv[service + 1:] if ln.text.startswith("  ")]


def _parse_candidates(p: _Prompt) -> None:
    if p.candidates == NONE_BODY:
        return
    block = None
    for ln in _lines(p.candidates):
        head = _HEADING.match(ln.text)
        if head:
            block = _Block(ln, head.group(1), head.group(2), head.group(3), head.group(5))
            p.blocks.append(block)
            continue
        if block is None:
            p.stray.append(ln)
            continue
        item = _Item("other", ln)
        if m := _CANDIDATE.match(ln.text) or _CANDIDATE_LOOSE.match(ln.text):
            item = _Item("cand", ln, bool(_CANDIDATE.match(ln.text)),
                         cause=m.group(1), verdict=m.group(2), reason=m.group(3))
        elif m := _FRESH.match(ln.text) or _FRESH_LOOSE.match(ln.text):
            item = _Item("fresh", ln, bool(_FRESH.match(ln.text)),
                         outcome=m.group(1), sentence=m.group(2))
            prev = block.items[-1] if block.items else None
            owner = None
            if prev is not None and prev.kind == "cand":
                owner = prev
            elif prev is not None and prev.kind == "fresh":
                owner = next((c for c in reversed(block.items) if c.kind == "cand"), None)
            if owner is not None:
                owner.fresh.append(item)
        elif ln.text == _MARKER_LINE:
            item = _Item("marker", ln)
        elif m := _DECIDED.match(ln.text):
            item = _Item("decided", ln, True, cause=m.group(1), outcome=m.group(2))
        block.items.append(item)


def _parse_evidence(p: _Prompt) -> None:
    if p.evidence in ("", NONE_BODY):
        return
    for i, chunk in enumerate(_READ_SPLIT.split(p.evidence)):
        header, _, content = chunk.partition("\n")
        m = _READ_HEADER.match(header)
        if m:
            p.reads.append(_Read(i, m.group(1), content))
        else:
            p.reads.append(_Read(i, "", chunk))


def _parse(user: str) -> _Prompt:
    p = _Prompt()
    m = _FRAME.fullmatch(user)
    if not m:
        return p
    p.framed = True
    p.inventory, p.candidates, p.evidence, p.tail = (
        m.group("inventory"), m.group("candidates"), m.group("evidence"), m.group("tail"))
    _parse_inventory(p)
    _parse_candidates(p)
    _parse_evidence(p)
    return p


# --- the row context -----------------------------------------------------

@dataclass
class _Ctx:
    system: str
    user: str
    assistant: str
    meta: dict | None
    p: _Prompt
    healthy: _Read | None = None
    groups: list[list[_Read]] = field(default_factory=list)   # group k is entry k's reads
    orphans: list[_Read] = field(default_factory=list)        # gathered reads before any events read

    @property
    def gathered(self) -> list[_Read]:
        """Every read but the healthy-origin read."""
        return [r for r in self.p.reads if r is not self.healthy]

    def block(self, key: str) -> _Block | None:
        return next((b for b in self.p.blocks if b.key == key), None)

    def group_of(self, key: str) -> list[_Read] | None:
        for k, e in enumerate(self.p.entries):
            if e.key == key:
                return self.groups[k] if k < len(self.groups) else None
        return None

    def budget_spent(self) -> bool:
        return len(self.p.reads) >= MAX_TOOL_CALLS


def _context(system: str, user: str, assistant: str, meta: dict | None) -> _Ctx:
    x = _Ctx(system, user, assistant, meta, _parse(user))
    reads = x.p.reads
    if meta is not None and reads and reads[0].label == meta.get("origin_read_label"):
        x.healthy = reads[0]
    for r in x.gathered:
        if _EVENTS_LABEL.match(r.label):
            x.groups.append([r])
        elif x.groups:
            x.groups[-1].append(r)
        else:
            x.orphans.append(r)
    return x


# --- shared helpers ------------------------------------------------------

def _shape(cause: str) -> tuple[str, str, str] | None:
    """(kind, object, reason or count) for a cause kubeagent can write, else None.

    Kinds: node, pvc, registry (below threshold or outranked), registry-n
    (the counted group), registry-unknown.
    """
    if m := _NODE_CAUSE.match(cause):
        return "node", m.group(1), m.group(2)
    if m := _PVC_CAUSE.match(cause):
        return "pvc", m.group(1), m.group(2)
    if cause == _REGISTRY_UNKNOWN:
        return "registry-unknown", "", ""
    if m := _REGISTRY_COUNTED.match(cause):
        return "registry-n", m.group(1), m.group(2)
    if m := _REGISTRY_PLAIN.match(cause):
        return "registry", m.group(1), ""
    return None


def _for_root_cause(cause: str) -> str | None:
    """confidence.ForRootCause (confidence/confidence.go:36-47); None for ""."""
    for prefix, level in CONFIDENCE_BY_PREFIX:
        if cause.startswith(prefix):
            return level
    return None


def _sub_kind(text: str) -> str:
    """One inventory sub-line's letter (explain/explain.go:252-310)."""
    if text.startswith(_ISSUE_PREFIX):
        return "I"
    if text.startswith(_LOG_CAUSE_LINE):
        return "L"
    if _RESOURCES_LINE.match(text):
        return "R"
    if text.startswith(_FIX_PREFIX) and " | run: " in text:
        return "F"
    if (m := _MORE_LINE.match(text)) and int(m.group(1)) >= 1:
        return "M"
    if _NETPOL_LINE.match(text):
        return "N"
    if text.startswith(_ROLLOUT_PREFIX):
        return "C"
    return "X"


def _finding_blocks(e: _Entry) -> list[list[_Line]]:
    """The visible finding blocks: each `issue:` line and the lines under it."""
    blocks: list[list[_Line]] = []
    for ln in e.subs:
        k = _sub_kind(ln.text)
        if k == "I":
            blocks.append([ln])
        elif k in "LRF" and blocks:
            blocks[-1].append(ln)
    return blocks


def _issues(e: _Entry) -> list[str]:
    out = []
    for ln in e.subs:
        if ln.text.startswith(_ISSUE_PREFIX):
            out.append(ln.text[len(_ISSUE_PREFIX):].split(" ", 1)[0])
    return out


def _has_more_line(e: _Entry) -> bool:
    return any(_sub_kind(ln.text) == "M" for ln in e.subs)


def _pod_of(pod: str, name: str) -> bool:
    return pod == name or pod.startswith(name + "-")


def _describe_key(label: str, ns: str = "") -> tuple[str, str, str] | None:
    if m := _NODE_LABEL.match(label):
        return "node", "", m.group(1)
    if m := _PVC_LABEL.match(label):
        return "pvc", m.group(1), m.group(2)
    return None


def _cand_key(c: _Item, ns: str) -> tuple[str, str, str] | None:
    s = _shape(c.cause)
    if s is None or s[0] not in ("node", "pvc"):
        return None
    return s[0], ns if s[0] == "pvc" else "", s[1]


def _content_lines(r: _Read) -> list[str]:
    """A read's lines, the capContent marker dropped."""
    lines = r.content.split("\n")
    if lines and lines[-1] == TRUNCATION_MARKER:
        lines = lines[:-1]
    return lines


def _classify_pull(r: _Read) -> tuple[str, str]:
    """classifyPullEvents over the rendered events (hypothesis/decide.go:195-230)."""
    if r.failed:
        return "unverified", FAILED_PREFIX + r.content[len(READ_FAILED_PREFIX):]
    msgs = []
    for line in _content_lines(r)[1:]:
        if (m := _EVENT_LINE.match(line)) and m.group(1) in ("Failed", "BackOff") \
                and "pull" in m.group(2).lower():
            msgs.append(m.group(2).lower())
    for literals, outcome, sentence in (
            (CONNECTION_LITERALS, "confirmed", _CONNECTION_SENTENCE),
            (AUTH_LITERALS, "unverified", _AUTH_SENTENCE),
            (IMAGE_LITERALS, "refuted", _IMAGE_SENTENCE)):
        for lit in literals:
            if any(lit in m for m in msgs):
                return outcome, sentence.format(lit)
    return "unverified", NO_PULL_EVENT


def _runes_over(s: str, limit: int = MAX_LINE) -> bool:
    return len(s) > limit


# Go's time.Duration.String (/usr/local/go/src/time/time.go:947-1034, go1.26.4).
def _fmt_frac(v: int, prec: int) -> tuple[str, int]:
    digits = []
    printed = False
    for _ in range(prec):
        d = v % 10
        printed = printed or d != 0
        if printed:
            digits.append(str(d))
        v //= 10
    return ("." + "".join(reversed(digits)) if printed else ""), v


def _go_duration(u: int) -> str:
    if u < 10**9:
        if u == 0:
            return "0s"
        prec, unit = (0, "ns") if u < 1000 else (3, "µs") if u < 10**6 else (6, "ms")
        frac, u = _fmt_frac(u, prec)
        return str(u) + frac + unit
    frac, u = _fmt_frac(u, 9)
    s = str(u % 60) + frac + "s"
    u //= 60
    if u > 0:
        s = str(u % 60) + "m" + s
        u //= 60
        if u > 0:
            s = str(u) + "h" + s
    return s


# Go's time.ParseDuration for the unsigned forms an age can take
# (/usr/local/go/src/time/format.go:1615 unitMap, :1631 ParseDuration).
_UNIT_NS = {"ns": 1, "us": 10**3, "µs": 10**3, "μs": 10**3, "ms": 10**6,
            "s": 10**9, "m": 60 * 10**9, "h": 3600 * 10**9}
_DURATION_PART = re.compile(r"(\d*)(?:\.(\d*))?(ns|us|µs|μs|ms|s|m|h)(?![a-zµμ])")


def _parse_duration(s: str) -> int | None:
    if s == "0":
        return 0
    total, pos = 0, 0
    while pos < len(s):
        m = _DURATION_PART.match(s, pos)
        if not m or (m.group(1) == "" and not m.group(2)):
            return None
        unit = _UNIT_NS[m.group(3)]
        total += int(m.group(1) or 0) * unit
        if m.group(2):
            total += int(m.group(2)) * unit // 10 ** len(m.group(2))
        pos = m.end()
    return total if s else None


_LEASE_AGE = re.compile(r"\(lease (\S+) stale\)")


# --- the frame -----------------------------------------------------------

_Finding = list[tuple[str, str]]


def _a1(x: _Ctx) -> tuple[int, _Finding]:
    """The three sections, in order (investigate/local.go:77-82)."""
    if not x.p.framed:
        return 1, [("prompt", x.user)]
    out = []
    for name, body in zip(SECTIONS, (x.p.inventory, x.p.candidates, x.p.evidence)):
        for i, line in enumerate(body.split("\n")):
            if _SECTION_MARK.match(line):
                out.append((f"{name} line {i + 1}", line))
    return 1, out


def _a2(x: _Ctx) -> tuple[int, _Finding]:
    """The closing sentence (investigate/local.go:81)."""
    if not x.p.framed:
        return 0, []
    return 1, [] if x.p.tail == CLOSING_INSTRUCTION else [("prompt", x.p.tail)]


def _a3(x: _Ctx) -> tuple[int, _Finding]:
    """The 64 KiB cap; only a read's (or the evidence's) last line is a
    column-0 truncation marker (investigate/local.go:84-103, gather.go:174-183)."""
    out = []
    size = len(x.user.encode("utf-8"))
    if size > MAX_PROMPT_BYTES:
        out.append(("prompt", f"{size} bytes"))
    for ln in x.p.inv:
        if ln.text == TRUNCATION_MARKER:
            out.append((f"inventory line {ln.no}", ln.text))
    for ln in _lines(x.p.candidates):
        if ln.text == TRUNCATION_MARKER:
            out.append((f"candidates line {ln.no}", ln.text))
    for r in x.p.reads:
        if TRUNCATION_MARKER in r.content.split("\n")[:-1]:
            out.append((r.where, TRUNCATION_MARKER))
    return 1 + len(x.p.reads), out


@cache
def _system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _a4(x: _Ctx) -> tuple[int, _Finding]:
    """The system prompt, word for word (investigate/local.go:34-45)."""
    if x.system == _system_prompt():
        return 1, []
    want = _system_prompt().split("\n")
    got = x.system.split("\n")
    diff = next((g for w, g in zip(want, got) if w != g), got[-1] if got else "")
    return 1, [("system", diff)]


def _a5(x: _Ctx) -> tuple[int, _Finding]:
    """`(none)` for an empty section, and no trailing newline
    (investigate/local.go:57-63)."""
    if not x.p.framed:
        return 0, []
    out = []
    for name, body in zip(SECTIONS, (x.p.inventory, x.p.candidates, x.p.evidence)):
        if body.strip() == "":
            out.append((f"{name} section", repr(body)))
        elif body.endswith("\n"):
            out.append((f"{name} section", "ends with a blank line"))
        elif body != NONE_BODY and NONE_BODY in body.split("\n"):
            out.append((f"{name} section", NONE_BODY))
    return 3, out


def _a6(x: _Ctx) -> tuple[int, _Finding]:
    """The inventory has BuildInventoryPrompt's shape (explain/explain.go:176-231)."""
    lines = x.p.inv
    if not lines or x.p.inventory == NONE_BODY:
        return len(lines), []
    t = [ln.text for ln in lines]
    n, i = len(t), 0

    def bad(k: int) -> tuple[int, _Finding]:
        return n, [(f"inventory line {lines[k].no}", t[k])] if k < n else [("inventory", "ends early")]

    def blank(k: int) -> bool:
        return k == n or t[k] == ""

    if t[i].startswith("Cluster health (P1): "):
        i += 1
        while i < n and t[i].startswith("  "):
            i += 1
        if not blank(i):
            return bad(i)
        i += 1
    if i < n and t[i].startswith("Platform: "):
        i += 1
        if not blank(i):
            return bad(i)
        i += 1
    if i < n and t[i] == "Cluster resources:":
        if i + 2 > n:
            return bad(i)
        cpu = _CPU_LINE.match(t[i + 1]) if i + 1 < n else None
        mem = _MEMORY_LINE.match(t[i + 2]) if i + 2 < n else None
        if not cpu:
            return bad(i + 1)
        if not mem or bool(cpu.group(1)) != bool(mem.group(1)):
            return bad(i + 2)
        i += 3
        if not blank(i):
            return bad(i)
        i += 1
    if i < n and t[i] == "Workload problems (P2):":
        i += 1
        if i == n or t[i] != "":
            return bad(i)
        i += 1
        if i == n or not t[i].startswith("- "):
            return bad(i)
        while i < n and (t[i].startswith("- ") or t[i].startswith("    ")):
            i += 1
    if i < n and t[i] == "Service issues:":
        i += 1
        while i < n and t[i].startswith("  "):
            i += 1
    if i < n:
        return bad(i)
    return n, []


# --- the inventory -------------------------------------------------------

def _b1(x: _Ctx) -> tuple[int, _Finding]:
    """Workloads sorted by (ns, name, kind), at most 10 (inventory/inventory.go:633-645,
    investigate/gather.go:31-42)."""
    es = x.p.entries
    out = []
    for a, b in pairwise(es):
        if (a.ns, a.name, a.kind) >= (b.ns, b.name, b.kind):
            out.append((f"inventory line {b.line.no}", b.line.text))
    if len(es) > MAX_GATHER_WORKLOADS:
        out.append((f"inventory line {es[MAX_GATHER_WORKLOADS].line.no}", es[MAX_GATHER_WORKLOADS].line.text))
    return len(es), out


def _b2(x: _Ctx) -> tuple[int, _Finding]:
    """Workload-line and finding-line shapes; at most 3 finding blocks
    (explain/explain.go:205, 252-310). A workload with no finding block is
    flagged some other way (inventory/inventory.go:102-104), so its events
    read names the workload itself and it has no pull or crash-family
    reads or candidates (investigate/gather.go:74-80)."""
    out = []
    for e in x.p.entries:
        if not e.match:
            out.append((f"inventory line {e.line.no}", e.line.text))
        seq = "".join(_sub_kind(ln.text) for ln in e.subs)
        if "X" in seq:
            ln = e.subs[seq.index("X")]
            out.append((f"inventory line {ln.no}", ln.text))
        elif not _BLOCK_SHAPE.match(seq.replace("N", "").replace("C", "")):
            out.append((f"inventory line {e.line.no}", f"finding lines {seq}: {e.line.text}"))
        for ln in e.subs:
            if ln.text.startswith(_ISSUE_PREFIX) and not _ISSUE_LINE.match(_COLLAPSE.sub("", ln.text)):
                out.append((f"inventory line {ln.no}", ln.text))
        if "I" in seq or not e.match:
            continue
        why = []
        ready, desired, status = int(e.match.group(4)), int(e.match.group(5)), e.match.group(6)
        if not (ready < desired or status == "Failed"):
            why.append("not flagged")
        group = x.group_of(e.key)
        if group is not None:
            if group[0].label != f"events {e.key}":
                why.append("its events read names a pod")
            if any(_LOG_LABEL.match(r.label) for r in group):
                why.append("it has a log read")
        elif not x.budget_spent():
            why.append("no events read")
        blk = x.block(e.key)
        if blk and any((_shape(c.cause) or ("",))[0].startswith("registry") for c in blk.cands):
            why.append("it has a registry candidate")
        if why:
            out.append((f"inventory line {e.line.no}", f"no finding block ({', '.join(why)}): {e.line.text}"))
    return len(x.p.entries) + sum(len(e.subs) for e in x.p.entries), out


def _b3(x: _Ctx) -> tuple[int, _Finding]:
    """The (×N) collapse: N ≥ 2, and no two shown blocks alike
    (explain/explain.go:252-282)."""
    out, n = [], 0
    for e in x.p.entries:
        blocks = _finding_blocks(e)
        n += len(blocks)
        bare = []
        for blk in blocks:
            m = _COLLAPSE.search(blk[0].text)
            if m and int(m.group(1)) < 2:
                out.append((f"inventory line {blk[0].no}", blk[0].text))
            bare.append("\n".join([_COLLAPSE.sub("", blk[0].text)] + [ln.text for ln in blk[1:]]))
        for k in range(1, len(bare)):
            if bare[k] == bare[k - 1]:
                out.append((f"inventory line {blocks[k][0].no}", blocks[k][0].text))
    return n, out


def _b4(x: _Ctx) -> tuple[int, _Finding]:
    """`network policy:` and `recent change:` come after the findings, once
    each, in that order (explain/explain.go:207-218)."""
    out = []
    for e in x.p.entries:
        seq = [_sub_kind(ln.text) for ln in e.subs]
        tail = [k for k in seq if k in "NC"]
        last_finding = max((i for i, k in enumerate(seq) if k in "ILRFM"), default=-1)
        first_extra = min((i for i, k in enumerate(seq) if k in "NC"), default=len(seq))
        if first_extra < last_finding or tail not in ([], ["N"], ["C"], ["N", "C"]):
            out.append((f"inventory line {e.line.no}", e.line.text))
    return len(x.p.entries), out


def _b5(x: _Ctx) -> tuple[int, _Finding]:
    """The cluster-health block's format (explain/explain.go:178-186,
    clusterhealth/clusterhealth.go:60-110)."""
    h = x.p.health
    if not h:
        return 0, []
    out = []
    m = _HEALTH_HEADER.match(h[0].text)
    if not m or int(m.group(1)) > int(m.group(2)):
        out.append((f"inventory line {h[0].no}", h[0].text))
    if len(h) == 1:
        out.append((f"inventory line {h[0].no}", "no node or system line"))
    seen_system = False
    not_ready = 0
    for ln in h[1:]:
        node = _HEALTH_NODE.match(ln.text)
        system = _HEALTH_SYSTEM.match(ln.text)
        if node and not seen_system:
            not_ready += node.group(2).startswith("NotReady")
        elif system:
            seen_system = True
        else:
            out.append((f"inventory line {ln.no}", ln.text))
    if m and not_ready != int(m.group(2)) - int(m.group(1)):
        out.append((f"inventory line {h[0].no}", f"{not_ready} NotReady lines: {h[0].text}"))
    return len(h), out


def _b6(x: _Ctx) -> tuple[int, _Finding]:
    """At most 10 service issues, each `  - ns/name (Type): detail`
    (investigate/local.go:48-53, explain/explain.go:221-224)."""
    out = [(f"inventory line {ln.no}", ln.text) for ln in x.p.services if not _SERVICE_LINE.match(ln.text)]
    if len(x.p.services) > MAX_SERVICE_ISSUES:
        ln = x.p.services[MAX_SERVICE_ISSUES]
        out.append((f"inventory line {ln.no}", ln.text))
    return len(x.p.services), out


# The builder's node-count floor (render._MIN_NODES). kubeagent's count is
# the cluster's, which the prompt does not show; B7 checks the builder's model.
_B7_MIN_NODES = 3


def _b7(x: _Ctx) -> tuple[int, _Finding]:
    """The cluster-health block appears if and only if there is a node
    candidate or a flagged kube-system workload, with the lines the builder's
    model gives (clusterhealth/clusterhealth.go:60-110; the node count is
    the builder's, see _B7_MIN_NODES)."""
    blocks = x.p.blocks
    truncated = any(b.truncated for b in blocks)
    nodes: dict[str, set[str]] = {}
    for b in blocks:
        for c in b.cands:
            s = _shape(c.cause)
            if s and s[0] == "node":
                nodes.setdefault(s[1], set()).add(s[2])
    system = [e for e in x.p.entries if e.ns == SYSTEM_NAMESPACE]
    h = x.p.health
    lines = [(ln, _HEALTH_NODE.match(ln.text)) for ln in h[1:]]
    node_lines = [(ln, m) for ln, m in lines if m]
    where = f"inventory line {h[0].no}" if h else "inventory"
    expected = bool(nodes) or bool(system)
    if bool(h) != expected and not (h and not expected and node_lines and truncated):
        return 1, [(where, h[0].text if h else "no cluster-health block")]
    if not h:
        return 1, []
    out = []
    names = [m.group(1) for _, m in node_lines]
    if names != sorted(set(names)):
        out.append((where, "node lines are not one per node in name order"))
    for ln, m in node_lines:
        issue = m.group(2)
        if not (issue.startswith(("NotReady", "kubelet not heartbeating"))
                or issue == "no kubelet lease"):
            out.append((f"inventory line {ln.no}", ln.text))
        if m.group(1) not in nodes and not truncated:
            out.append((f"inventory line {ln.no}", ln.text))
    by_name = {m.group(1): m.group(2) for _, m in node_lines}
    for name, reasons in sorted(nodes.items()):
        want = ("NotReady" if "NotReady" in reasons else
                "no kubelet lease" if "no kubelet lease" in reasons else "kubelet not heartbeating")
        got = by_name.get(name, "")
        if not (got.startswith(want) and (want != "NotReady" or got == want or got.startswith("NotReady: "))):
            out.append((where, f"node {name} ({want}): {got or 'no line'}"))
    described = set()
    for r in x.p.reads:
        if r.label.startswith("describe node /"):
            described.add(r.label[len("describe node /"):].split(" ", 1)[0])
    total = max(_B7_MIN_NODES, len(set(names) | described) + 1)
    head = _HEALTH_HEADER.match(h[0].text)
    if head and int(head.group(2)) != total:
        out.append((where, f"{total} nodes expected: {h[0].text}"))
    want_sys = []
    for e in system:
        if not e.match:
            continue
        ready, desired, status = e.match.group(4), e.match.group(5), e.match.group(6)
        if e.kind in ("Job", "CronJob"):
            want_sys.append(f"  system {e.ns}/{e.name} {status}")
        else:
            want_sys.append(f"  system {e.ns}/{e.name} {ready}/{desired} {status}")
    got_sys = [ln.text for ln, m in lines if not m]
    if len(x.p.entries) >= MAX_GATHER_WORKLOADS:
        ok = got_sys[:len(want_sys)] == want_sys
    else:
        ok = got_sys == want_sys
    if not ok:
        out.append((where, f"system lines {got_sys} expected {want_sys}"))
    return len(h), out


# The health-line issues that make a node a down node, the list rootcause
# walks (clusterhealth/clusterhealth.go:33-38, :71 and :79). A pressure, a
# cordon or an absent node is on the health block but is not down.
_DOWN_ISSUES = ("NotReady", "kubelet not heartbeating", "no kubelet lease")


def _b8(x: _Ctx) -> tuple[int, _Finding]:
    """Every block lists the row's down nodes and its namespace's broken
    PVCs, on a row with two or more blocks.

    rootcause.Annotate (rootcause/rootcause.go:24-56) walks every down node
    for every flagged workload and records each one: a node none of the
    workload's pods runs on is `ruled out — no pod of this workload is
    scheduled on it` (:47). So every down node, whether the health block
    names it or another block names it as a candidate, is a candidate in
    every block. rootcause.AnnotatePVC (:177-222) does the same for every
    broken PVC in the workload's own namespace, ruling out one its pods do
    not mount (:214); a PVC in another namespace is not a candidate (:207).
    It returns early only when no pod in the scan mounts a claim (:178),
    and a PVC candidate anywhere in the row means some pod does. So every
    PVC a block of namespace X names is a candidate in every block of
    namespace X.

    A block that carries the cap marker (investigate/prime.go:85-89) is
    exempt: the lines past the cap cannot be known."""
    blocks = x.p.blocks
    if len(blocks) < 2:
        return 0, []
    nodes: set[str] = set()
    for ln in x.p.health[1:]:
        m = _HEALTH_NODE.match(ln.text)
        if m and m.group(2).startswith(_DOWN_ISSUES):
            nodes.add(m.group(1))
    pvcs: dict[str, set[str]] = {}
    for b in blocks:
        for c in b.cands:
            s = _shape(c.cause)
            if s and s[0] == "node":
                nodes.add(s[1])
            elif s and s[0] == "pvc":
                pvcs.setdefault(b.ns, set()).add(s[1])
    out = []
    for b in blocks:
        if b.truncated:
            continue
        shown = {(s[0], s[1]) for c in b.cands if (s := _shape(c.cause))}
        out += [(b.where(b.heading), f"no candidate line for node {name}")
                for name in sorted(nodes) if ("node", name) not in shown]
        out += [(b.where(b.heading), f"no candidate line for PVC {b.ns}/{name}")
                for name in sorted(pvcs.get(b.ns, ())) if ("pvc", name) not in shown]
    return len(blocks), out


# --- the candidates ------------------------------------------------------

def _c1(x: _Ctx) -> tuple[int, _Finding]:
    """Heading shape and order: each block is an inventory workload, in
    inventory order, with at least one candidate (investigate/prime.go:78-104,
    :111-121)."""
    out = [(f"candidates line {ln.no}", ln.text) for ln in x.p.stray]
    k = 0
    entries = x.p.entries
    for b in x.p.blocks:
        for it in b.items:
            if it.kind == "other":
                out.append((b.where(it.line), it.line.text))
        j = next((i for i in range(k, len(entries)) if entries[i].key == b.key), None)
        if j is None or entries[j].kind != b.kind:
            out.append((b.where(b.heading), b.heading.text))
        else:
            k = j + 1
        if not b.cands:
            out.append((b.where(b.heading), "no candidate"))
    return len(x.p.blocks) + len(x.p.stray), out


def _c1_conf(x: _Ctx) -> tuple[int, _Finding]:
    """The confidence tag is ForRootCause of the attributed cause
    (confidence/confidence.go:36-47, :69-72; investigate/prime.go:58-64)."""
    out = []
    for b in x.p.blocks:
        attributed = next((c for c in b.cands if c.verdict == "attributed"), None)
        if attributed is not None:
            ok = b.tag == _for_root_cause(attributed.cause)
        else:
            ok = b.tag is None or (b.truncated and b.tag in ("high", "medium"))
        if not ok:
            out.append((b.where(b.heading), b.heading.text))
    return len(x.p.blocks), out


def _c1_cause(x: _Ctx) -> tuple[int, _Finding]:
    """A cause has one of kubeagent's 5 shapes; a counted registry's count
    fits the row (rootcause/rootcause.go:44, 108, 114, 128-135, 211)."""
    out = []
    n = 0
    counts: dict[str, set[int]] = {}
    attributed: Counter[str] = Counter()
    for b in x.p.blocks:
        for c in b.cands:
            n += 1
            s = _shape(c.cause)
            if s is None:
                out.append((b.where(c.line), c.line.text))
                continue
            if s[0] == "registry-n":
                counts.setdefault(s[1], set()).add(int(s[2]))
                if c.verdict == "attributed":
                    attributed[s[1]] += 1
    truncated = sum(b.truncated for b in x.p.blocks)
    for host, ns in sorted(counts.items()):
        count = min(ns)
        if len(ns) > 1 or count < REGISTRY_THRESHOLD or count < attributed[host] or (
                len(x.p.entries) < MAX_GATHER_WORKLOADS and count > attributed[host] + truncated):
            out.append(("candidates", (f"registry {host}: counts {sorted(ns)}, "
                                       f"{attributed[host]} attributed")))
    return n, out


def _c2_vocab(x: _Ctx) -> tuple[int, _Finding]:
    """The verdict is one of the 3 words (inventory/inventory.go:79-81,
    investigate/prime.go:67-70)."""
    out = []
    n = 0
    for b in x.p.blocks:
        for c in b.cands:
            n += 1
            if not c.strict:
                out.append((b.where(c.line), c.line.text))
    return n, out


def _reason_ok(shape: tuple[str, str, str] | None, verdict: str, reason: str) -> bool:
    kind = shape[0]
    if kind in ("node", "pvc"):
        if verdict == "ruled out":
            return reason == (NODE_RULED_OUT if kind == "node" else PVC_RULED_OUT)
        if verdict == "attributed":
            return bool((_NODE_ATTRIBUTED if kind == "node" else _PVC_ATTRIBUTED).match(reason))
        return bool(_OUTRANKED.match(reason))
    if kind == "registry-unknown":
        return verdict == "ruled out" and reason == REGISTRY_UNKNOWN_REASON
    if kind == "registry":
        if verdict == "ruled out":
            return reason == REGISTRY_BELOW_THRESHOLD
        return verdict == "outranked" and bool(_OUTRANKED.match(reason))
    m = _REGISTRY_ATTRIBUTED.match(reason)
    return verdict == "attributed" and bool(m) and m.group(1) == shape[2]


def _c2_reason(x: _Ctx) -> tuple[int, _Finding]:
    """The reason text is one rootcause writes for that verdict
    (rootcause/rootcause.go:47-52, 108, 113-114, 128-133, 214-219)."""
    out = []
    n = 0
    for b in x.p.blocks:
        for c in b.cands:
            s = _shape(c.cause)
            if s is None or c.verdict not in VERDICTS:
                continue
            n += 1
            if not _reason_ok(s, c.verdict, c.reason):
                out.append((b.where(c.line), c.line.text))
    return n, out


def _c3(x: _Ctx) -> tuple[int, _Finding]:
    """At most 8 candidates, then the truncation line (investigate/prime.go:85-89)."""
    out = []
    for b in x.p.blocks:
        cands = 0
        after_marker = False
        for k, it in enumerate(b.items):
            if after_marker and it.kind != "decided":
                out.append((b.where(it.line), it.line.text))
            if it.kind == "cand":
                cands += 1
                if cands > MAX_CANDIDATES_PER_WORKLOAD:
                    out.append((b.where(it.line), it.line.text))
            elif it.kind == "marker":
                prev = b.items[k - 1] if k else None
                if after_marker or cands != MAX_CANDIDATES_PER_WORKLOAD or prev is None \
                        or prev.kind not in ("cand", "fresh"):
                    out.append((b.where(it.line), it.line.text))
                after_marker = True
    return len(x.p.blocks), out


_KIND_ORDER = {"node": 0, "pvc": 1, "registry": 2, "registry-n": 2, "registry-unknown": 2}


def _c4_order(x: _Ctx) -> tuple[int, _Finding]:
    """Nodes by name, then PVCs by name, then one registry; at most one
    attributed candidate, ruled out before it, ruled out or outranked by it
    after it (scan/scan.go:815-817, rootcause/rootcause.go:36-53, 190-221,
    100-136)."""
    out = []
    for b in x.p.blocks:
        shaped = [(c, _shape(c.cause)) for c in b.cands]
        shaped = [(c, s) for c, s in shaped if s is not None]
        keys = [(_KIND_ORDER[s[0]], s[1] if s[0] in ("node", "pvc") else "") for _, s in shaped]
        registries = sum(k[0] == 2 for k in keys)
        # every candidate counts here, shaped or not: a block has at most one
        # attributed candidate whatever its cause says (rootcause/rootcause.go:36-53)
        attributed = [c for c in b.cands if c.verdict == "attributed"]
        bad = keys != sorted(keys) or registries > 1 or len(attributed) > 1
        seen_attr = None
        for c, s in shaped:
            if c.verdict == "attributed":
                seen_attr = c
            elif c.verdict == "outranked":
                m = _OUTRANKED.match(c.reason)
                if seen_attr is None or not m or m.group(1) != seen_attr.cause:
                    bad = True
            elif c.verdict != "ruled out":
                bad = True
            if seen_attr is not None and seen_attr is not c and s[0] in ("registry-n",):
                bad = True
            if seen_attr is not None and s[0] == "registry" and c.verdict == "ruled out":
                bad = True
        if bad:
            out.append((b.where(b.heading), b.heading.text))
    return len(x.p.blocks), out


def _c4_dedup(x: _Ctx) -> tuple[int, _Finding]:
    """No object twice in a block; one scan reason per node, and per PVC, in
    a row (rootcause/rootcause.go:27-35, 185-190)."""
    out = []
    reason_of: dict[tuple[str, str, str], str] = {}
    n = 0
    for b in x.p.blocks:
        seen: set[tuple[str, str]] = set()
        for c in b.cands:
            s = _shape(c.cause)
            if s is None:
                continue
            n += 1
            kind = "registry" if s[0].startswith("registry") else s[0]
            if (kind, s[1]) in seen:
                out.append((b.where(c.line), c.line.text))
            seen.add((kind, s[1]))
            if s[0] in ("node", "pvc"):
                key = (s[0], b.ns if s[0] == "pvc" else "", s[1])
                if reason_of.setdefault(key, s[2]) != s[2]:
                    out.append((b.where(c.line), c.line.text))
    return n, out


def _hidden(d: _Item | None, shown: set[str], outcomes: tuple[str, ...]) -> bool:
    """The decided line names a cause the cap hid, with one of `outcomes`."""
    return (d is not None and d.cause not in shown and _shape(d.cause) is not None
            and d.outcome in outcomes)


def _c5_d4(x: _Ctx) -> tuple[int, _Finding]:
    """The decided line appears if and only if Decide decides, names that
    cause, and is confirmed or unverified (hypothesis/hypothesis.go:62-82,
    investigate/prime.go:100-102). A candidate past the cap can decide."""
    out = []
    for b in x.p.blocks:
        decided = [it for it in b.items if it.kind == "decided"]
        d = decided[0] if decided else None
        where = b.where(d.line if d else b.heading)
        if len(decided) > 1 or (d is not None and b.items[-1] is not d):
            out.append((where, "the decided line is not last and alone"))
            continue
        if d is not None and d.outcome not in ("confirmed", "unverified"):
            out.append((where, d.line.text))
            continue
        live = [c for c in b.cands if c.verdict != "ruled out" and c.fresh]
        confirmed = next((c for c in live if c.fresh[0].outcome == "confirmed"), None)
        unverified = next((c for c in live if c.fresh[0].outcome == "unverified"), None)
        shown = {c.cause for c in b.cands}
        if confirmed is not None:
            ok = d is not None and d.cause == confirmed.cause and d.outcome == "confirmed"
        elif b.truncated and unverified is not None:
            ok = d is not None and ((d.cause == unverified.cause and d.outcome == "unverified")
                                    or _hidden(d, shown, ("confirmed",)))
        elif b.truncated:
            ok = d is None or _hidden(d, shown, ("confirmed", "unverified"))
        elif unverified is not None:
            ok = d is not None and d.cause == unverified.cause and d.outcome == "unverified"
        else:
            ok = d is None
        if not ok:
            out.append((where, d.line.text if d else "no decided line"))
    return len(x.p.blocks), out


# --- the fresh reads -----------------------------------------------------

def _d1(x: _Ctx) -> tuple[int, _Finding]:
    """No fresh line after a ruled-out candidate (investigate/prime.go:91-93)."""
    out = []
    n = 0
    for b in x.p.blocks:
        for c in b.cands:
            if c.verdict == "ruled out":
                n += 1
                out.extend((b.where(f.line), f.line.text) for f in c.fresh)
    return n, out


def _d1_onefresh(x: _Ctx) -> tuple[int, _Finding]:
    """Exactly one fresh line per shown non-ruled-out candidate, right after
    it (investigate/prime.go:94-98)."""
    out = []
    n = 0
    for b in x.p.blocks:
        owned = set()
        for c in b.cands:
            owned.update(id(f) for f in c.fresh)
            if c.verdict != "ruled out":
                n += 1
                if len(c.fresh) != 1:
                    out.append((b.where(c.line), c.line.text))
        for it in b.items:
            if it.kind == "fresh" and id(it) not in owned:
                out.append((b.where(it.line), it.line.text))
    return n, out


def _sentence_ok(shape: tuple[str, str, str] | None, outcome: str, sentence: str) -> bool:
    if shape is None:
        return outcome == "unverified" and sentence == NO_RULE
    if outcome == "unverified" and (sentence == NEVER_READ or (
            sentence.startswith(FAILED_PREFIX) and len(sentence) > len(FAILED_PREFIX))):
        return True
    kind, _, reason = shape
    if kind == "node":
        heartbeat = reason in HEARTBEAT_REASONS
        if sentence == NODE_SENTENCES["refuted"][0]:
            return outcome == "refuted" and not heartbeat
        if sentence == NODE_SENTENCES["unverified"][0]:
            return outcome == "unverified" and heartbeat
        return sentence in NODE_SENTENCES.get(outcome, ())
    if kind == "pvc":
        return sentence in PVC_SENTENCES.get(outcome, ())
    if kind in ("registry", "registry-n"):
        if outcome == "unverified" and sentence in (NO_PULL_EVENT, PULL_POD_UNREAD):
            return True
        for literals, want, template in (
                (CONNECTION_LITERALS, "confirmed", _CONNECTION_SENTENCE),
                (AUTH_LITERALS, "unverified", _AUTH_SENTENCE),
                (IMAGE_LITERALS, "refuted", _IMAGE_SENTENCE)):
            if outcome == want and sentence in {template.format(lit) for lit in literals}:
                return True
    return False


def _d2_vocab(x: _Ctx) -> tuple[int, _Finding]:
    """The outcome is one of the 3 words, with a sentence the rule for that
    kind writes (hypothesis/decide.go:13-15, 34-92, 134-135, 195-215)."""
    out = []
    n = 0
    for b in x.p.blocks:
        for c in b.cands:
            for f in c.fresh:
                n += 1
                if not f.strict or not _sentence_ok(_shape(c.cause), f.outcome, f.sentence):
                    out.append((b.where(f.line), f.line.text))
    return n, out


def _expected_fresh(x: _Ctx, b: _Block, c: _Item) -> set[tuple[str, str]] | None:
    """The fresh outcomes the reads allow for one candidate, or None when the
    text cannot tell (a capped read, an unparsed body)."""
    s = _shape(c.cause)
    if s is None:
        return None
    gathered = x.gathered
    never = {("unverified", NEVER_READ)}
    if s[0] in ("node", "pvc"):
        label = f"describe node /{s[1]}" if s[0] == "node" else f"describe pvc {b.ns}/{s[1]}"
        r = next((r for r in gathered if r.label == label), None)
        if r is None:
            return never if x.budget_spent() else set()
        if r.capped:
            return None
        if r.failed:
            return {("unverified", FAILED_PREFIX + r.content[len(READ_FAILED_PREFIX):])}
        if s[0] == "node":
            m = _READY_CONDITION.search(r.content)
            status = m.group(1) if m else None
            if status is None:
                return {("confirmed", "the node has no Ready condition")}
            if status in ("False", "Unknown"):
                return {("confirmed", f"Ready condition is {status} now")}
            if status == "True":
                if s[2] in HEARTBEAT_REASONS:
                    return {("unverified", NODE_SENTENCES["unverified"][0])}
                return {("refuted", "Ready condition is True now")}
            return {("unverified", "Ready condition is not one kubeagent expects")}
        m = _PVC_BODY.match(r.content)
        if not m:
            return None
        return {{"Bound": ("refuted", "phase is Bound now"),
                 "Pending": ("confirmed", "phase is still Pending"),
                 "Lost": ("confirmed", "phase is Lost")}.get(
            m.group(3), ("unverified", "phase is not one kubeagent expects"))}
    if s[0] not in ("registry", "registry-n"):
        return None
    unread = {("unverified", PULL_POD_UNREAD)}
    group = x.group_of(b.key)
    entry = next((e for e in x.p.entries if e.key == b.key), None)
    issues = _issues(entry) if entry else []
    pull_first = bool(issues) and issues[0] in PULL_ISSUES
    if group is None:
        if not x.budget_spent():
            return set()
        return never if pull_first else never | unread
    if group[0].capped:
        return None
    result = {_classify_pull(group[0])}
    return result if pull_first else result | unread


def _d3(x: _Ctx) -> tuple[int, _Finding]:
    """Each fresh line is what the rule gives over the reads in the evidence:
    a node's describe, a PVC's describe, the pulling pod's events
    (hypothesis/decide.go:34-92, 157-230). A candidate with no read was
    never read, which needs a spent budget (investigate/gather.go:74)."""
    out = []
    n = 0
    for b in x.p.blocks:
        for c in b.cands:
            if c.verdict == "ruled out" or len(c.fresh) != 1 or not c.fresh[0].strict:
                continue
            want = _expected_fresh(x, b, c)
            if want is None:
                continue
            n += 1
            f = c.fresh[0]
            if (f.outcome, f.sentence) not in want:
                out.append((b.where(f.line), f.line.text))
    return n, out


# --- the evidence --------------------------------------------------------

def _e1(x: _Ctx) -> tuple[int, _Finding]:
    """At most 8 reads (investigate/investigate.go:22, gather.go:74)."""
    reads = x.p.reads
    if len(reads) > MAX_TOOL_CALLS:
        return len(reads), [(reads[MAX_TOOL_CALLS].where, reads[MAX_TOOL_CALLS].label)]
    return len(reads), []


def _e2_order(x: _Ctx) -> tuple[int, _Finding]:
    """Per workload, in inventory order: its events, then a describe per
    surviving node or PVC candidate not described before, then its logs
    (investigate/gather.go:57-157)."""
    out = [(r.where, r.label) for r in x.orphans]
    entries = x.p.entries
    groups = x.groups
    described: set[tuple[str, str, str]] = set()
    for k, group in enumerate(groups):
        if k >= len(entries):
            out.extend((r.where, r.label) for r in group)
            continue
        e = entries[k]
        head = _EVENTS_LABEL.match(group[0].label)
        if head.group(1) != e.ns or not _pod_of(head.group(2), e.name):
            out.append((group[0].where, group[0].label))
        last = k == len(groups) - 1 and x.budget_spent()
        blk = x.block(e.key)
        want = []
        if blk is not None:
            for c in blk.cands:
                key = _cand_key(c, e.ns)
                if c.verdict != "ruled out" and key and key not in described and key not in want:
                    want.append(key)
        got = []
        phase = "describe"
        crash = any(i in CRASH_FAMILY for i in _issues(e)) or _has_more_line(e)
        for r in group[1:]:
            key = _describe_key(r.label)
            log = _LOG_LABEL.match(r.label)
            if key is not None:
                if phase != "describe":
                    out.append((r.where, r.label))
                got.append((r, key))
            elif log:
                phase = "log"
                if not crash or log.group(1) != e.ns or not _pod_of(log.group(2), e.name):
                    out.append((r.where, r.label))
        keys = [key for _, key in got]
        shown = keys[:len(want)]
        if shown != want and not (last and want[:len(shown)] == shown and len(keys) <= len(want)):
            out.append((group[0].where, f"describes {keys} expected {want}"))
        for r, key in got[len(want):]:
            if not (blk and blk.truncated) or key in described or (key[0] == "pvc" and key[1] != e.ns):
                out.append((r.where, r.label))
        described.update(keys)
    return len(x.gathered), out


def _e3(x: _Ctx) -> tuple[int, _Finding]:
    """Each read at most 4096 bytes, or a cut ending in the marker
    (investigate/gather.go:174-183)."""
    out = []
    for r in x.p.reads:
        body = r.content
        if r.capped:
            body = body[:-len(TRUNCATION_MARKER)].removesuffix("\n")
        if len(body.encode("utf-8")) > MAX_READ_BYTES:
            out.append((r.where, f"{len(body.encode('utf-8'))} bytes"))
    return len(x.p.reads), out


def _e4(x: _Ctx) -> tuple[int, _Finding]:
    """The label has one of the 4 shapes (investigate/gather.go:90, 132, 153)."""
    out = []
    for r in x.gathered:
        if not (_EVENTS_LABEL.match(r.label) or _NODE_LABEL.match(r.label)
                or _PVC_LABEL.match(r.label) or _LOG_LABEL.match(r.label)):
            out.append((r.where, r.label))
    return len(x.gathered), out


def _e5(x: _Ctx) -> tuple[int, _Finding]:
    """No label repeats (investigate/gather.go:109-113, 147-151)."""
    seen: set[str] = set()
    out = []
    for r in x.p.reads:
        if r.label in seen:
            out.append((r.where, r.label))
        seen.add(r.label)
    return len(x.p.reads), out


def _judged(x: _Ctx, label: re.Pattern) -> list[tuple[_Read, re.Match]]:
    return [(r, m) for r in x.gathered if (m := label.match(r.label)) and not r.failed]


def _e6(x: _Ctx) -> tuple[int, _Finding]:
    """The events format (investigate/reader.go:312-322)."""
    out = []
    reads = _judged(x, _EVENTS_LABEL)
    for r, m in reads:
        lines = _content_lines(r)
        ns, pod = m.group(1), m.group(2)
        if lines == [f"no events for {ns}/{pod}"]:
            continue
        ok = lines[0] == f"events for {ns}/{pod}:" and (len(lines) > 1 or r.capped)
        bad = next((ln for ln in lines[1:] if not _EVENT_LINE.match(ln)), None)
        if not ok or bad is not None:
            out.append((r.where, bad if bad is not None else lines[0]))
    return len(reads), out


def _e7(x: _Ctx) -> tuple[int, _Finding]:
    """The node describe format; a condition that is not True names its
    reason and message (investigate/reader.go:238-248)."""
    out = []
    reads = _judged(x, _NODE_LABEL)
    for r, m in reads:
        lines = _content_lines(r)
        head = _NODE_HEAD.match(lines[0])
        if not head or head.group(1) != m.group(1):
            out.append((r.where, lines[0]))
            continue
        taints = False
        for ln in lines[1:]:
            cond = _CONDITION_LINE.match(ln)
            if cond and not taints:
                if cond.group(2) != "True" and not (cond.group(3) and cond.group(4)):
                    out.append((r.where, ln))
            elif _TAINT_LINE.match(ln):
                taints = True
            else:
                out.append((r.where, ln))
    return len(reads), out


def _e8(x: _Ctx) -> tuple[int, _Finding]:
    """The PVC describe format (investigate/reader.go:250-257)."""
    out = []
    reads = _judged(x, _PVC_LABEL)
    for r, m in reads:
        body = _PVC_BODY.match(r.content)
        if not body or body.group(1, 2) != m.group(1, 2):
            out.append((r.where, r.content))
    return len(reads), out


_LOG_BODY_PREFIXES = ("reading the previous log of ", "no previous-instance log for ",
                      "the previous log of ", LOG_CAUSE_PREFIX, READ_FAILED_PREFIX)


def _e9(x: _Ctx) -> tuple[int, _Finding]:
    """A log read is one of the fixed bodies, a cause is one of the 10
    strings, or else one reduced error line (investigate/reader.go:473-487)."""
    out = []
    reads = [(r, m) for r in x.gathered if (m := _LOG_LABEL.match(r.label))]
    for r, m in reads:
        ns, pod, container = m.groups()
        fixed = {LOG_REFUSED.format(ns=ns, pod=pod),
                 LOG_NO_PREVIOUS.format(ns=ns, pod=pod, container=container),
                 LOG_NO_CLASSIFIABLE.format(ns=ns, pod=pod, container=container)}
        fixed |= {LOG_CAUSE_PREFIX + c for c in LOG_CAUSES}
        c = r.content
        if c in fixed:
            continue
        if "\n" in c or not c or c.startswith(_LOG_BODY_PREFIXES):
            out.append((r.where, c))
    return len(reads), out


def _e10(x: _Ctx) -> tuple[int, _Finding]:
    """A failed read reads `read failed: <message>` on one line; a log read
    never does (investigate/gather.go:85, 117, 126; reader.go:473-477)."""
    out = []
    n = 0
    for r in x.gathered:
        log = bool(_LOG_LABEL.match(r.label))
        if not (r.failed or log):
            continue
        n += 1
        if r.failed and (log or "\n" in r.content
                         or not r.content[len(READ_FAILED_PREFIX):].strip()):
            out.append((r.where, r.content))
    return n, out


def _e_min(x: _Ctx) -> tuple[int, _Finding]:
    """Every scoped workload has its events read, unless the budget ran out
    first (investigate/gather.go:73-76)."""
    out = []
    if not x.budget_spent():
        for e in x.p.entries[len(x.groups):]:
            out.append((f"inventory line {e.line.no}", e.line.text))
    return len(x.p.entries), out


# --- the text ------------------------------------------------------------

def _f1_scan(text: str) -> list[str]:
    """safetext.Line's promises (safetext/safetext.go:58-100) over a text
    whose lines were each cleaned on their own."""
    bad = []
    base, marks = False, 0
    for ch in text:
        if ch == "\n":
            base, marks = False, 0
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Cs") or ch in "  ":
            bad.append(f"U+{ord(ch):04X}")
        elif ch == " ":
            base, marks = False, 0
        elif cat.startswith("M"):
            marks += 1
            if not base or marks > MAX_COMBINING:
                bad.append(f"U+{ord(ch):04X} mark")
        else:
            base, marks = True, 0
    return bad


def _answer_strings(x: _Ctx) -> list[str]:
    try:
        doc = json.loads(x.assistant)
    except ValueError:
        return []
    out: list[str] = []

    def walk(v: object) -> None:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for k, w in v.items():
                walk(k)
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
    walk(doc)
    return out


def _f1(x: _Ctx) -> tuple[int, _Finding]:
    """No control or format character, no stray or piled-up combining mark,
    in the prompt or any answer string (safetext/safetext.go:40, 58-100)."""
    out = []
    lines = x.user.split("\n")
    for i, line in enumerate(lines):
        if bad := _f1_scan(line):
            out.append((f"prompt line {i + 1}", f"{', '.join(bad)}: {line}"))
    strings = _answer_strings(x)
    for s in strings:
        if bad := _f1_scan(s):
            out.append(("answer", f"{', '.join(bad)}: {s}"))
    return len(lines) + len(strings), out


def _f2(x: _Ctx) -> tuple[int, _Finding]:
    """No raw IP address and no host:port (redact/redact.go:44-47)."""
    lines = x.user.split("\n")
    out = [(f"prompt line {i + 1}", line) for i, line in enumerate(lines) if ADDR.search(line)]
    return len(lines), out


def _answer(x: _Ctx) -> dict | None:
    try:
        doc = json.loads(x.assistant)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _f3(x: _Ctx) -> tuple[int, _Finding]:
    """Every line of API text and every answer line is at most 512 runes
    (safetext/safetext.go:28, investigate/local.go:113; a NotReady message
    at most 120 runes and its ellipsis, clusterhealth/clusterhealth.go:206)."""
    out = []
    n = 0
    for r in x.p.reads:
        for ln in _content_lines(r):
            parts: tuple[str, ...] = ()
            if m := _EVENT_LINE.match(ln):
                parts = (m.group(1), m.group(2))
            elif m := _CONDITION_LINE.match(ln):
                parts = (m.group(3), m.group(4))
            n += len(parts)
            if any(_runes_over(p) for p in parts):
                out.append((r.where, ln))
    for ln in x.p.health[1:]:
        if (m := _HEALTH_NODE.match(ln.text)) and m.group(2).startswith("NotReady: "):
            n += 1
            text = m.group(2)[len("NotReady: "):]
            if " — " in text:
                over = _runes_over(text.split(" — ", 1)[1], NOT_READY_MESSAGE_RUNES + 1)
            else:
                over = _runes_over(text)
            if over:
                out.append((f"inventory line {ln.no}", ln.text))
    doc = _answer(x)
    if doc is not None:
        texts = []
        for v in doc.get("verdicts") or []:
            if isinstance(v, dict):
                texts += [v.get("cause"), v.get("rationale")]
        if isinstance(doc.get("summary"), str):
            texts += doc["summary"].split("\n")
        for t in texts:
            if isinstance(t, str):
                n += 1
                if _runes_over(t, MAX_MODEL_LINE_RUNES):
                    out.append(("answer", t))
    return n, out


def _txt_is8(x: _Ctx) -> tuple[int, _Finding]:
    """No `image "":` -- a pull failure names its image (IS-8)."""
    lines = x.user.split("\n")
    return len(lines), [(f"prompt line {i + 1}", ln) for i, ln in enumerate(lines) if 'image "":' in ln]


def _txt_is9(x: _Ctx) -> tuple[int, _Finding]:
    """The scheduler's message carries its ` preemption: 0/` clause, and no
    node `had disk pressure` (IS-9).

    The scheduler's message reaches kubeagent's prompt in two places: the
    Unschedulable finding quotes it (diagnose/pending.go:17-22) and the
    FailedScheduling event carries it (investigate/reader.go:312-322). The
    clause check reads those two; the disk-pressure check reads every line.
    """
    out = []
    n = 0
    for ln in x.p.inv:
        if ln.text.startswith("    issue: Unschedulable ") and "nodes are available:" in ln.text:
            n += 1
            if " preemption: 0/" not in ln.text:
                out.append((f"inventory line {ln.no}", ln.text))
    for r in x.p.reads:
        for line in _content_lines(r):
            if "nodes are available:" in line:
                n += 1
                if " preemption: 0/" not in line:
                    out.append((r.where, line))
    lines = x.user.split("\n")
    out += [(f"prompt line {i + 1}", ln) for i, ln in enumerate(lines) if "had disk pressure" in ln]
    return n + len(lines), out


def _txt_is11(x: _Ctx) -> tuple[int, _Finding]:
    """No `dial tcp`, `i/o timeout` or `Get "` in the inventory: a probe or
    pull message reaches the prompt only through a read (IS-11)."""
    out = [(f"inventory line {ln.no}", ln.text) for ln in x.p.inv
           if any(s in ln.text for s in ("dial tcp", "i/o timeout", 'Get "'))]
    return len(x.p.inv), out


_RESTARTS_IN_EVIDENCE = re.compile(r'container "[^"]*", (\d+) restarts, last exit')
_RESTART_COUNT_IN_EVIDENCE = re.compile(r"restartCount=(\d+), last exit")


def _txt_is14(x: _Ctx) -> tuple[int, _Finding]:
    """A restart-loop or crash-loop finding with a last exit has at least 3
    restarts (diagnose/restartloop.go:15, :35; diagnose/crashloop.go:46).
    Its workload line shows at least as many: that count is the sum over
    the workload's pods and containers (inventory/inventory.go:158-170,
    488), and the finding's count is one container's."""
    out = []
    n = 0
    for e in x.p.entries:
        for ln in e.subs:
            m = None
            if ln.text.startswith("    issue: RestartLoop "):
                m = _RESTARTS_IN_EVIDENCE.search(ln.text)
            elif ln.text.startswith("    issue: CrashLoopBackOff "):
                m = _RESTART_COUNT_IN_EVIDENCE.search(ln.text)
            if m is None:
                continue
            n += 1
            count = int(m.group(1))
            # A workload line that does not parse is B2's to report.
            total = int(e.match.group(7)) if e.match else count
            if count < RESTART_THRESHOLD or total < count:
                out.append((f"inventory line {ln.no}", ln.text))
    return n, out


_DETECTOR_AGE = re.compile(r", last exit -?\d+ \(.*\), (\S+) ago(?:\)| \(×\d+\)|$)")
_ROLLOUT_AGE = re.compile(r"^    recent change: rolled out to revision \S+ (\S+) ago(?:, |$)")
_HUMAN_AGE = re.compile(r"^(?:0|[1-9]\d*)[dhms]$")


def _duration_ok(token: str) -> bool:
    ns = _parse_duration(token)
    return ns is not None and ns % 10**9 == 0 and _go_duration(ns) == token


def _txt_is15(x: _Ctx) -> tuple[int, _Finding]:
    """Every age kubeagent prints is in the form it prints it.

    A finding's last exit and a lease's staleness are Go's
    time.Duration.String in whole seconds (diagnose/crashloop.go:55-56,
    diagnose/restartloop.go:42-47, clusterhealth/clusterhealth.go:144). A
    recent change's age is inventory.HumanAge: one number and one of d, h, m,
    s (inventory/inventory.go:115-146, rollout/rollout.go:61). An age inside
    text the cluster wrote, such as an event message, keeps the cluster's
    own form and is not read.
    """
    out = []
    n = 0
    for ln in x.p.inv:
        tokens = [(m.group(1), _duration_ok) for m in _LEASE_AGE.finditer(ln.text)]
        if ln.text.startswith(_ISSUE_PREFIX):
            tokens += [(m.group(1), _duration_ok) for m in _DETECTOR_AGE.finditer(ln.text)]
        if m := _ROLLOUT_AGE.match(ln.text):
            tokens.append((m.group(1), lambda t: bool(_HUMAN_AGE.match(t))))
        for token, ok in tokens:
            n += 1
            if not ok(token):
                out.append((f"inventory line {ln.no}", ln.text))
    return n, out


_LOGS_ISSUE = re.compile(r'^    issue: (?:CrashLoopBackOff|RestartLoop) — .*\(container "([^"]*)", ')


def _txt_is17(x: _Ctx) -> tuple[int, _Finding]:
    """A crash finding's logs command names the finding's container. kubeagent
    builds it from the finding's own container (remediation/remediation.go:24-25,
    :65-72). IS-17 was coredns's command naming another container. The rule
    reads the container from the issue text when it names one, and a workload
    named coredns expects the coredns container either way (the golden's issue
    text names no container)."""
    out = []
    n = 0
    for e in x.p.entries:
        container = None
        for ln in e.subs:
            if ln.text.startswith(_ISSUE_PREFIX):
                m = _LOGS_ISSUE.match(ln.text)
                container = m.group(1) if m else ("coredns" if e.name == "coredns" else None)
                continue
            if not ln.text.startswith(_FIX_PREFIX):
                continue  # a "log cause:" line can sit between the issue and its fix
            command = ln.text.split(" | run: ", 1)[-1]
            if container and " logs " in command:
                n += 1
                if f" -c {container} --previous" not in command:
                    out.append((f"inventory line {ln.no}", ln.text))
            container = None
    return n, out


# The commands of remediation.For that put an object's name in a slot
# (remediation/remediation.go:21-57): logsCmd :66-72, jobLogsCmd :79-81,
# describeCmd :83-85, describeCronJobCmd :93-95 and objectEventsCmd :107-109.
# eventsCmd (:111-113) names a reason, not an object. The flag says whether the
# arm's finding sits on the workload itself: JobFailed carries the workload's
# key as its pod (batchhealth/batchhealth.go:113) and picks jobLogsCmd or
# describeCronJobCmd, and RolloutStuck does too (rollouthealth/rollouthealth.go:125)
# and picks objectEventsCmd. Every other arm's finding sits on a pod.
_NAME_SLOT = (
    (re.compile(r"^kubectl -n (\S*) logs (\S+)(?: -c \S+)? --previous$"), False),
    (re.compile(r"^kubectl -n (\S*) logs job/(\S+)$"), True),
    (re.compile(r"^kubectl -n (\S*) describe pod (\S+)$"), False),
    (re.compile(r"^kubectl -n (\S*) describe cronjob (\S+)$"), True),
    (re.compile(r"^kubectl -n (\S*) get events --field-selector involvedObject\.name=(\S+)$"), True),
)


def _txt_pod(x: _Ctx) -> tuple[int, _Finding]:
    """A fix command's name slot holds what suggestionFor leaves there
    (explain/explain.go:148-171). It swaps the finding's pod for `<pod>`
    unless the pod is the workload's own identity (:163, the mask at :165 and
    :167), and it keeps the namespace. So the `-n` value is the workload's own
    namespace, and the slot is:
    - the workload's own name, when the finding sits on the workload: a
      JobFailed or RolloutStuck arm, or any arm of a bare pod, which kubeagent
      makes its own workload (inventory/inventory.go:402);
    - `<pod>` otherwise, since a controller's pod name is drawn per replica
      and explains nothing."""
    out = []
    n = 0
    for e in x.p.entries:
        for ln in e.subs:
            if not ln.text.startswith(_FIX_PREFIX):
                continue
            command = ln.text.split(" | run: ", 1)[-1]
            hit = next(((m, on_workload) for arm, on_workload in _NAME_SLOT
                        if (m := arm.match(command))), None)
            if hit is None:
                continue
            n += 1
            m, on_workload = hit
            ns, slot = m.groups()
            kept = on_workload or e.kind == "Pod"
            if ns != e.ns or slot != (e.name if kept else "<pod>"):
                out.append((f"inventory line {ln.no}", ln.text))
    return n, out


# --- the answer ----------------------------------------------------------

_VERDICT_KEYS = {"workload", "cause", "confidence", "rationale"}


def _ans1(x: _Ctx) -> tuple[int, _Finding]:
    """The answer is the contract's JSON; with meta, it names exactly the
    row's workloads. A decided workload's cause is the decided cause, and no
    cause is one its candidates ruled out or a fresh read refuted
    (investigate/local.go:34-45)."""
    doc = _answer(x)
    verdicts = doc.get("verdicts") if doc else None
    if (doc is None or set(doc) != {"verdicts", "summary"} or not isinstance(doc["summary"], str)
            or not isinstance(verdicts, list)
            or not all(isinstance(v, dict) and set(v) == _VERDICT_KEYS
                       and all(isinstance(v[k], str) for k in _VERDICT_KEYS)
                       and v["confidence"] in ("low", "medium", "high") for v in verdicts)):
        return 1, [("answer", x.assistant)]
    out = []
    names = [v["workload"] for v in verdicts]
    if x.meta is not None:
        want = set((x.meta.get("workloads") or {}).keys())
        if len(names) != len(set(names)) or set(names) != want:
            out.append(("answer", f"workloads {sorted(names)} expected {sorted(want)}"))
    for i, v in enumerate(verdicts):
        b = x.block(v["workload"])
        if b is None:
            continue
        decided = next((it for it in b.items if it.kind == "decided"), None)
        if decided is not None and v["cause"] != decided.cause:
            out.append((f"answer verdict {i}", v["cause"]))
        for c in b.cands:
            refuted = any(f.outcome == "refuted" for f in c.fresh)
            if (c.verdict == "ruled out" or refuted) and v["cause"] == c.cause:
                out.append((f"answer verdict {i}", v["cause"]))
    return 1 + len(verdicts), out


def _ans2(x: _Ctx) -> tuple[int, _Finding]:
    """Every own-cause keyword is in that workload's own block: its inventory
    entry, its candidate block and its reads (the grader's containment rule,
    evals/score.py:209-214)."""
    if x.meta is None:
        return 0, []
    out = []
    n = 0
    for name, w in (x.meta.get("workloads") or {}).items():
        keywords = (w or {}).get("own_cause_keywords") or []
        if not keywords:
            continue
        n += 1
        parts = []
        entry = next((e for e in x.p.entries if e.key == name), None)
        if entry is not None:
            parts += [entry.line.text] + [ln.text for ln in entry.subs]
        b = x.block(name)
        if b is not None:
            parts += [b.heading.text] + [it.line.text for it in b.items]
        for r in x.group_of(name) or []:
            parts += [r.label, r.content]
        text = "\n".join(parts).lower()
        missing = [k for k in keywords if str(k).lower() not in text]
        if missing:
            out.append((f"workload {name}", f"missing {missing}"))
    return n, out


_Rule = Callable[[_Ctx], tuple[int, _Finding]]
_RULE_FUNCS: dict[str, _Rule] = {
    "A1": _a1, "A2": _a2, "A3": _a3, "A4": _a4, "A5": _a5, "A6": _a6,
    "B1": _b1, "B2": _b2, "B3": _b3, "B4": _b4, "B5": _b5, "B6": _b6, "B7": _b7, "B8": _b8,
    "C1": _c1, "C1-conf": _c1_conf, "C1-cause": _c1_cause, "C2-vocab": _c2_vocab,
    "C2-reason": _c2_reason, "C3": _c3, "C4-order": _c4_order, "C4-dedup": _c4_dedup,
    "C5/D4": _c5_d4,
    "D1": _d1, "D1-onefresh": _d1_onefresh, "D2-vocab": _d2_vocab, "D3": _d3,
    "E1": _e1, "E2-order": _e2_order, "E3": _e3, "E4": _e4, "E5": _e5, "E6": _e6,
    "E7": _e7, "E8": _e8, "E9": _e9, "E10": _e10, "E-min": _e_min,
    "F1": _f1, "F2": _f2, "F3": _f3,
    "TXT-IS8": _txt_is8, "TXT-IS9": _txt_is9, "TXT-IS11": _txt_is11,
    "TXT-IS14": _txt_is14, "TXT-IS15": _txt_is15, "TXT-IS17": _txt_is17,
    "TXT-POD": _txt_pod,
    "ANS-1": _ans1, "ANS-2": _ans2,
}
RULES: tuple[str, ...] = tuple(_RULE_FUNCS)


def check(system: str, user: str, assistant: str, meta: dict | None) -> Report:
    """Every place one row differs from what kubeagent v1.24.0 can send."""
    x = _context(system, user, assistant, meta)
    exempt = meta is not None and meta.get("case") in EXEMPT_CASES
    violations: list[Violation] = []
    inspected: dict[str, int] = {}
    for rule, func in _RULE_FUNCS.items():
        if exempt and (rule in EVIDENCE_RULES or rule in PROPAGATION_TEXT_RULES):
            inspected[rule] = 0
            continue
        n, found = func(x)
        inspected[rule] = n
        violations.extend(Violation(rule, where, str(quote)[:200]) for where, quote in found)
    return Report(tuple(violations), inspected)


def check_row(row: dict) -> Report:
    """`check` over one row in the generate.to_row shape."""
    system, user, assistant = (m["content"] for m in row["messages"])
    return check(system, user, assistant, row.get("meta"))


def count_by_case(rows: Iterable[dict]) -> dict[str, int]:
    """Each case's violation count, every case present, zeros included."""
    counts: Counter[str] = Counter()
    for row in rows:
        case = row["meta"]["case"]
        counts[case] += len(check_row(row).violations)
    return dict(sorted(counts.items()))
