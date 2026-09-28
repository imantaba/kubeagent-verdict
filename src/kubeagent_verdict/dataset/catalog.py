"""The scenario catalog: one curated entry per fault slug and per issue kind.

An entry is a template kit, not an example: Task 7's case builders
substitute synthetic names (names.py) into the {placeholder} fields and
assemble full prompts through the contract renderers. Cause phrasing
(winner_cause) is hand-authored per entry, not lifted from
internal/rootcause/rootcause.go — none of its node/registry/PVC shapes
match a winner_cause value. Reason phrasing echoes kubeagent's own
kubelet/API-server reason strings, not text copied from the known-issues
snapshot. Literal braces inside a template must be doubled ({{ }}) because
templates go through str.format.
"""

from __future__ import annotations

from dataclasses import dataclass

from kubeagent_verdict.dataset.objects import Object


@dataclass(frozen=True)
class CatalogEntry:
    key: str
    covered_slugs: tuple[str, ...]
    covered_kinds: tuple[str, ...]
    trains: bool
    # Everything below is a str.format template over the names.py fields:
    # {ns} {name} {pod} {container} {init_container} {image} {node} {pvc} {restarts}
    workload_kind: str = "Deployment"
    status: str = "Progressing"
    issue: str = ""
    reason: str = ""
    evidence: str = ""
    log_cause: str = ""
    recommendation: str = ""  # closes the ANSWER's summary; never a prompt field
    resources: tuple[str, str, str, str] | None = None  # mem req, mem limit, cpu req, cpu limit
    winner_cause: str = ""
    winner_reason: str = ""
    losers: tuple[tuple[str, str, str], ...] = ()  # (cause, "ruled_out"|"outranked", reason)
    reads: tuple[tuple[str, str], ...] = ()  # (label template, content template)
    # What the events read of the workload's pod lists: (reason, message,
    # count) in the order kubeagent lists them, the shape
    # `gather.GatherWorkload.events` takes. The reason and message are
    # templates. A count is an int, or a template that formats to one, such
    # as "{restarts}". Three entries had kubectl-table text in `reads`
    # instead: each row became one tuple (reason = the REASON column,
    # message = the text after `pod/{pod} `, count 1), rows with the same
    # reason and message became one event counted once per row, and the
    # rows kept their written order.
    events: tuple[tuple[str, str, int | str], ...] = ()
    rationale: str = ""
    direct: bool = True  # True: full evidence earns "high" confidence; False: "medium"
    contradiction: str = ""  # read content that rules the winner out (contradiction_probe)
    own_cause: str = ""  # the cause phrase when the winner is omitted from candidates
    own_cause_keywords: tuple[str, ...] = ()
    grounding: tuple[str, ...] = ()  # substrings that must appear in this slug's corpus assertions
    degraded: bool = False
    network_policies: tuple[str, ...] = ()
    service_issue: tuple[str, str] | None = None  # (type, detail template)
    notes: str = ""
    # The nodes, PVCs and registries this entry puts on the menu. Empty for
    # the 9 entries with no fault-side object (control-plane read failures,
    # Service-only issues, a deleted namespace, policy/GitOps findings with
    # no workload, and the two healthy-cluster entries). Every producing
    # entry declares exactly one object.
    objects: tuple[Object, ...] = ()
    # The lowest restart count names.draw may give this entry's workload.
    # A finding that prints its restart count only fires from 3 restarts
    # on (kubeagent internal/diagnose/restartloop.go:15, 35-37;
    # crashloop.go:46 prints the last exit only from 3), so those entries
    # set 3.
    min_restarts: int = 1


def all_entries() -> tuple[CatalogEntry, ...]:
    from kubeagent_verdict.dataset import entries_kinds, entries_slugs

    return tuple(entries_slugs.ENTRIES) + tuple(entries_kinds.ENTRIES)


def by_slug() -> dict[str, CatalogEntry]:
    return {s: e for e in all_entries() for s in e.covered_slugs}


def trainable() -> tuple[CatalogEntry, ...]:
    return tuple(e for e in all_entries() if e.trains)
