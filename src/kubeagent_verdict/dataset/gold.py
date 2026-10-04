"""Gold for a shared-origin row (Spec 4b-1 §6), from anchors in own lines."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import NamedTuple

from kubeagent_verdict.dataset import render, rules
from kubeagent_verdict.dataset import shared_origin as so

# Verbatim port of the grader's own-lines reader (evals/score.py), kept here
# so the dataset package never imports the grader. A test pins them equal.

_SECTION_MARK = re.compile(r"^== (BEGIN|END) (\w+) ==$")
_READ_LABEL = re.compile(r"^== (.+) ==$")
# The read that opens a workload's gather group: kubeagent reads the events
# of the workload's pod first (internal/investigate/gather.go:75-90 at v1.24.0).
_GATHER_GROUP_LABEL = re.compile(r"^events \S+/\S+$")


def _read_owner(label: str, workloads: list[str]) -> str | None:
    """The workload an evidence read's label names, or None.

    Each whitespace token shaped `ns/x` names workload `ns/name` when `x` is
    the name or starts with `name-` (a pod of it). When two workloads match,
    the longer name wins, so `web/api-gw-5c6b` goes to `web/api-gw`, not to
    `web/api`.

    A name is not an owner on its own: a claim called `cache-0` starts with
    `cache-` too. So `own_lines` asks this only of a label that opens a
    gather group, or of a label in a trail that has no gather group.
    """
    owner = None
    for token in label.split():
        ns, slash, x = token.partition("/")
        if not slash:
            continue
        for w in workloads:
            wns, _, name = w.partition("/")
            named = wns == ns and (x == name or x.startswith(name + "-"))
            if named and (owner is None or len(w) > len(owner)):
                owner = w
    return owner


def own_lines(prompt: str, workloads: Iterable[str]) -> dict[str, frozenset[str]]:
    """Each workload's own printed lines, normalized by `_norm_cause`, with
    empty results dropped. Every workload gets a key; one the prompt never
    prints gets an empty set.

    A workload's own lines are:
    - its inventory entry: the line starting `- {w} (` and the lines under
      it that start with a space;
    - its candidate entry, by the same rule;
    - its evidence reads: its gather group, when the trail has one, or else
      the reads from a label that names it up to the next label that names
      another workload.

    An entry ends at the next line starting `- ` or at any line that does not
    start with a space.

    kubeagent reads one workload's events, describes and logs before the
    next workload's (`gatherEvidence`, internal/investigate/gather.go:71-155
    at v1.24.0). So each workload's gather group opens with an `events
    <ns>/<pod>` read, and every read up to the next `events` read is in that
    group: `describe node /worker-1`, `describe pvc web/cache-0`, `log causes
    ...`. The group's owner is the workload the `events` label names (see
    `_read_owner`), or nobody when it names no flagged workload. No other
    label in the group can move the owner, so a claim named `cache-0` in
    `web/indexer`'s group stays `web/indexer`'s even when `web/cache` is
    flagged too.

    A trail with no `events` read yet (the tool loop's labels on a
    shared-origin row, or the one healthy-origin read printed before the
    gather) has no group. There every label that names a workload moves the
    owner, by `_read_owner`'s name rule, and a read whose label names no
    workload stays with the workload before it.

    Lines before the first entry, or before the first read that names a
    workload, belong to nobody. So do lines outside the three sections.
    """
    names = list(workloads)
    lines: dict[str, set[str]] = {w: set() for w in names}
    section = None
    current = None
    grouped = False
    for line in prompt.split("\n"):
        mark = _SECTION_MARK.match(line)
        if mark:
            section = mark.group(2) if mark.group(1) == "BEGIN" else None
            current = None
            grouped = False
            continue
        if section in ("inventory", "candidates"):
            if line.startswith("- "):
                current = next((w for w in names if line.startswith(f"- {w} (")), None)
            elif not line.startswith(" "):
                current = None
        elif section == "evidence":
            label = _READ_LABEL.match(line)
            if label and _GATHER_GROUP_LABEL.match(label.group(1)):
                grouped = True
                current = _read_owner(label.group(1), names)
            elif label and not grouped:
                current = _read_owner(label.group(1), names) or current
        else:
            continue
        if current is not None:
            normalized = _norm_cause(line)
            if normalized:
                lines[current].add(normalized)
    return {w: frozenset(own) for w, own in lines.items()}


def _norm_cause(s: str) -> str:
    """One cleaning step for every cause the grader reads: NFKC first, so a
    full-width letter, space or period folds to its plain form, then
    lowercase, strip, trailing periods off, and runs of whitespace
    squeezed to one space."""
    return " ".join(unicodedata.normalize("NFKC", str(s)).lower().strip().rstrip(".").split())


class RowGold(NamedTuple):
    verdict: str
    cause: str
    confidence: str
    keys: tuple[str, ...]
    rationale: str
    linked: bool


class Gold(NamedTuple):
    rows: dict[str, RowGold]
    label: str
    n: int
    summary: str


def excluded_causes(row: so.Row) -> list[str]:
    """Causes the rules threw out for this row: every candidate ruled out
    at attribution, plus every candidate refuted by its fresh read."""
    ruled_out = [cand.cause for cand in row.candidates if cand.verdict == "ruled_out"]
    refuted = [d.candidate for d in row.result.decisions if d.outcome == "refuted"]
    return ruled_out + refuted


def anchor_lines(own: Iterable[str], row: so.Row) -> list[str]:
    """A row's own lines minus every line that names a ruled-out or refuted
    candidate's cause: a gold may not lean on a cause the rules threw out."""
    dropped = [_norm_cause(x) for x in excluded_causes(row)]
    return [ln for ln in own if not any(x and x in _norm_cause(ln) for x in dropped)]


def check_keys(keys: tuple[str, ...], *, anchors: list[str], own: list[str]) -> None:
    for k in keys:
        if any(k in ln.lower() for ln in anchors):
            continue
        if any(k in ln.lower() for ln in own):
            raise ValueError(f"key {k!r} sits only in excluded lines")
        raise ValueError(f"key {k!r} sits in no own line")


def label_for(rule_lines: tuple[str, ...], *, linked: int, cls: str, world: str) -> str:
    if rules.label(rule_lines) == "shared":
        return "shared"
    if cls == "P" and world == "broken" and linked >= 2:
        return "shared"
    return "none"                                   # "separate" maps here (Ruling 25)


def _row_gold(row: so.Row, own: list[str], built: so.Built) -> RowGold:
    t = row.text
    if row.result.decided:                          # confirmed or unverified: job 1
        return RowGold("decided", row.result.cause, "high", (),
                       render.rule_rationale(row.result), False)
    if row.role == "origin":
        answer = t.answer
    else:
        answer = t.healthy if built.world_name == "healthy" else t.broken
    if answer is not None:
        anchor = _norm_cause(so._sub(answer.anchor, row.names, built.draw))
        anchors = anchor_lines(own, row)
        if any(anchor in ln for ln in anchors):
            check_keys(answer.keys, anchors=anchors, own=own)
            return RowGold("named", so._sub(answer.cause, row.names, built.draw),
                           answer.confidence, answer.keys, answer.rationale,
                           answer.link and built.world_name == "broken")
    return RowGold("none_of_these", "", "low", (),
                   f"{t.none_phrase}; none of its own lines says why.", False)


def gold_for(built: so.Built) -> Gold:
    blocks = own_lines(built.user, [r.key for r in built.rows])
    rows = {r.key: _row_gold(r, sorted(blocks[r.key]), built) for r in built.rows}
    rule_lines = rules.shared(tuple(r.result for r in built.rows))
    linked = sum(1 for r in built.rows if r.role == "victim" and rows[r.key].linked)
    label = label_for(rule_lines, linked=linked, cls=built.story.cls, world=built.world_name)
    if label == "shared":
        confirmed = sum(1 for r in built.rows
                        if rows[r.key].verdict == "decided" and r.result.outcome == "confirmed")
        n = max(linked, confirmed)
    else:
        n = len(built.rows)
    return Gold(rows, label, n, _summary(built, rows, label, n))


def _summary(built: so.Built, rows: dict[str, RowGold], label: str, n: int) -> str:
    """1 to 4 lines, joined with "\\n" (Ruling 33). "Failing for separate
    reasons" is said only in a healthy world where every row has its own,
    different cause, named or rule-decided; anywhere else it would claim more
    than the rows show."""
    st, d = built.story, built.draw
    if label == "shared":
        return "\n".join((
            f"{n} workloads share one upstream cause: {so._sub(st.shown_origin, None, d)}.",
            f"Root cause: {so._sub(st.shown_cause, None, d)}.",
            so._sub(st.shown_remedy, None, d)))
    separate = (built.world_name == "healthy"
                and all(g.verdict != "none_of_these" for g in rows.values())
                and len({g.cause for g in rows.values()}) == len(rows))
    lines = [f"{n} workloads are failing for separate reasons." if separate else
             f"{n} workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them."]
    for r in built.rows[:3]:
        g = rows[r.key]
        lines.append(f"{r.key}: {g.cause}." if g.cause else
                     f"{r.key}: its own lines do not show why.")
    return "\n".join(lines)
