"""Strict loader for the vendored known-issues snapshot.

Unlike the corpus loader this one raises: the snapshot is a hand-derived,
committed file, so any defect in it is a repository bug, not field data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kubeagent_verdict import vocab

_FIELDS = ("kind", "summary", "detail", "causes", "checks", "docs")


@dataclass(frozen=True)
class KnownIssue:
    kind: str
    summary: str
    detail: str
    causes: tuple[str, ...]
    checks: tuple[str, ...]
    docs: str


def load_knownissues(path: Path) -> dict[str, KnownIssue]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("knownissues snapshot must be a JSON array")
    out: dict[str, KnownIssue] = {}
    for i, obj in enumerate(raw):
        if not isinstance(obj, dict) or set(obj) != set(_FIELDS):
            raise ValueError(f"entry {i}: fields must be exactly {_FIELDS}")
        kind = obj["kind"]
        if kind not in vocab.ISSUE_KINDS:
            raise ValueError(f"entry {i}: kind {kind!r} outside the closed vocabulary")
        if kind in out:
            raise ValueError(f"duplicate kind {kind!r}")
        out[kind] = KnownIssue(
            kind=kind, summary=obj["summary"], detail=obj["detail"],
            causes=tuple(obj["causes"]), checks=tuple(obj["checks"]), docs=obj["docs"],
        )
    if set(out) != vocab.ISSUE_KINDS:
        missing = vocab.ISSUE_KINDS - set(out)
        raise ValueError(f"snapshot missing kinds: {sorted(missing)}")
    return out
