"""Deterministic example generation and dataset assembly.

Task 7 ships the core (attributed-only, no split); Task 8 wires the full
curriculum, the group split, the corpus-derived test set, and the manifest.
One rule holds throughout: same seed, same bytes — no wall clock, no
unseeded randomness. `generate` must define Example before importing
cases (cases imports Example from here), so the import sits inside the
function.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Example:
    case: str
    group: str
    system: str
    user: str
    assistant: str
    meta: dict


def to_row(ex: Example) -> dict:
    return {
        "messages": [
            {"role": "system", "content": ex.system},
            {"role": "user", "content": ex.user},
            {"role": "assistant", "content": ex.assistant},
        ],
        "meta": ex.meta,
    }


def write_jsonl(path: Path, examples: list[Example]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(to_row(ex), ensure_ascii=False) + "\n" for ex in examples)


def generate(seed: int, size: int) -> list[Example]:
    from kubeagent_verdict.dataset import cases, catalog, names

    rng = random.Random(seed)
    entries = catalog.trainable()
    out: list[Example] = []
    for i in range(size):
        entry = entries[i % len(entries)]
        out.append(cases.attributed(entry, names.draw(rng)))
    return out
