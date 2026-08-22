"""Soft-degrading loader for the chaos correctness corpus snapshots.

The one place in this repository that degrades instead of raising: a row
that cannot be trusted (bad JSON, missing or mistyped keys, a fault slug
outside the closed vocabulary — including chaos/run.sh's "unknown-scenario"
fallback) is withheld and counted, never guessed at. Callers decide what a
nonzero withheld count means to them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kubeagent_verdict import vocab

_REQUIRED = {
    "scenario": str, "fault": str, "k8s": str, "distro": str,
    "rc": int, "assertions": list, "skipped": bool, "skip_reason": str,
}


@dataclass(frozen=True)
class CorpusRow:
    scenario: str
    fault: str
    k8s: str
    distro: str
    rc: int
    assertions: tuple[str, ...]
    skipped: bool
    skip_reason: str


@dataclass(frozen=True)
class CorpusLoad:
    rows: tuple[CorpusRow, ...]
    withheld: int
    reasons: tuple[str, ...]


def load_corpus(paths: Iterable[Path]) -> CorpusLoad:
    rows: list[CorpusRow] = []
    reasons: list[str] = []
    for path in paths:
        for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            where = f"{Path(path).name}:{lineno}"
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                reasons.append(f"{where}: not valid JSON")
                continue
            if not isinstance(obj, dict) or set(obj) != set(_REQUIRED):
                reasons.append(f"{where}: keys do not match the corpus row schema")
                continue
            # bool is an int subclass: check bool keys first, and reject
            # a bool where an int is required.
            bad_type = False
            for key, typ in _REQUIRED.items():
                v = obj[key]
                if typ is int:
                    ok = isinstance(v, int) and not isinstance(v, bool)
                elif typ is bool:
                    ok = isinstance(v, bool)
                else:
                    ok = isinstance(v, typ)
                if not ok:
                    reasons.append(f"{where}: field {key} has the wrong type")
                    bad_type = True
                    break
            if bad_type:
                continue
            if not all(isinstance(a, str) for a in obj["assertions"]):
                reasons.append(f"{where}: assertions must all be strings")
                continue
            if obj["fault"] not in vocab.FAULT_SLUGS:
                reasons.append(f"{where}: fault slug {obj['fault']!r} outside the closed vocabulary")
                continue
            rows.append(CorpusRow(
                scenario=obj["scenario"], fault=obj["fault"], k8s=obj["k8s"],
                distro=obj["distro"], rc=obj["rc"],
                assertions=tuple(obj["assertions"]),
                skipped=obj["skipped"], skip_reason=obj["skip_reason"],
            ))
    return CorpusLoad(rows=tuple(rows), withheld=len(reasons), reasons=tuple(reasons))
