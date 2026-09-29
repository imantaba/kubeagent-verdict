"""The scenario catalog: one curated entry per fault slug and per issue kind.

An entry is a template kit, not an example: the case builders in cases.py
substitute synthetic names (names.py) into the {placeholder} fields and
assemble full prompts through the contract renderers. A job-1 row's cause
is never written here: the rules decide it from the entry's objects, in
kubeagent's own words. The cause an entry does write is its own_cause, the
answer when the rules leave the workload undecided. Reason phrasing echoes
kubeagent's own kubelet/API-server reason strings, not text copied from
the known-issues snapshot. Literal braces inside a template must be
doubled ({{ }}) because templates go through str.format.
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
    # What the events read of the workload's pod lists: (reason, message,
    # count) in the order kubeagent lists them, the shape
    # `gather.GatherWorkload.events` takes. The reason and message are
    # templates. A count is an int, or a template that formats to one, such
    # as "{restarts}". Three entries were first written as kubectl-table
    # text: each row became one tuple (reason = the REASON column,
    # message = the text after `pod/{pod} `, count 1), rows with the same
    # reason and message became one event counted once per row, and the
    # rows kept their written order.
    events: tuple[tuple[str, str, int | str], ...] = ()
    # More events for the same pod, in the same shape, that only a
    # `contradiction_probe` row lists. They print after `events`, in the
    # one events read, and seem to argue against the rules' cause. They
    # change nothing the rules read, so the row's answer is still the
    # rules' cause. Only entries the rules decide have them, and two of
    # those have none: worker-containerd-stop's node already describes as
    # healthy and Ready on its lease ending, and pvc-unbound-unschedulable
    # was never written with one.
    contradiction_events: tuple[tuple[str, str, int | str], ...] = ()
    rationale: str = ""
    direct: bool = True  # True: full evidence earns "high" confidence; False: "medium"
    own_cause: str = ""  # the cause phrase when the winner is omitted from candidates
    own_cause_keywords: tuple[str, ...] = ()
    # Words a right job-2 answer never holds. An answer that holds every
    # keyword and any one of these scores 0. Matched as lowercase
    # substrings, the same as the keywords.
    own_cause_must_not: tuple[str, ...] = ()
    grounding: tuple[str, ...] = ()  # substrings that must appear in this slug's corpus assertions
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
    # set 3. coredns-corefile-broken sets 6: its evidence fixes
    # restartCount=6, and a workload's count is the sum over its pods'
    # containers (inventory/inventory.go:158-170, 488).
    min_restarts: int = 1


# The three ways an answer writes "init container". Each is its own
# must-not word on the main-container stories. Never bare "init":
# "initial" and "initialize" would trip it.
INIT_CONTAINER = ("init container", "init-container", "initcontainer")


def all_entries() -> tuple[CatalogEntry, ...]:
    from kubeagent_verdict.dataset import entries_kinds, entries_slugs

    return tuple(entries_slugs.ENTRIES) + tuple(entries_kinds.ENTRIES)


def by_slug() -> dict[str, CatalogEntry]:
    return {s: e for e in all_entries() for s in e.covered_slugs}


def trainable() -> tuple[CatalogEntry, ...]:
    return tuple(e for e in all_entries() if e.trains)


# The trainable entries the rules decide in a single-workload row: the
# job-1 rows (attributed, injection, positional_probe, truncated,
# contradiction_probe) draw only from these. Listed, not computed, so a
# catalog edit that changes the set fails tests/test_catalog.py instead of
# quietly moving the rotation. The three trainable entries left out cannot
# decide: deployment-bad-image-tag's registry counts one workload against
# a threshold of 2, and node-cordon-diskfull's and
# oversized-job-unschedulable's nodes hold no pod of the workload.
_JOB1_KEYS = frozenset({
    "memory-limit-oomkill", "networkpolicy-deny-all", "coredns-corefile-broken",
    "worker-containerd-stop", "crashloop-pod", "probe-failure", "container-start-error",
    "create-container-config-error", "init-crashloop", "init-config-error",
    "init-errimagepull", "init-imagepullbackoff", "init-oomkilled", "restart-loop",
    "volume-attach-error", "volume-mount-error", "pvc-unbound-unschedulable",
})


def job1_entries() -> tuple[CatalogEntry, ...]:
    """The 17 trainable entries the rules decide, in `trainable()` order."""
    return tuple(e for e in trainable() if e.key in _JOB1_KEYS)
