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


CASE_MIX = (("attributed", 30), ("none_of_these", 15), ("own_cause", 10),
            ("multi", 15), ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 10))

# The held-out test set draws one example per (trainable entry, case) for each
# of these. `multi` is excluded deliberately: its group is a "+"-join of two to
# four constituent groups, so holding one out drops every training example that
# shares ANY constituent — a disproportionate bite out of the training set for
# a case the single-workload slices already cover.
HELD_OUT_CASES = ("none_of_these", "own_cause", "truncated", "injection",
                  "empty_candidates", "wrong_attribution")


def counts_for(size: int) -> dict[str, int]:
    counts = {case: size * pct // 100 for case, pct in CASE_MIX}
    counts["attributed"] += size - sum(counts.values())
    return counts


def generate(seed: int, size: int) -> list[Example]:
    from kubeagent_verdict.dataset import cases, catalog, names

    rng = random.Random(seed)
    entries = catalog.trainable()
    counts = counts_for(size)
    out: list[Example] = []

    def rotate(i: int):
        return entries[i % len(entries)]

    for i in range(counts["attributed"]):
        out.append(cases.attributed(rotate(i), names.draw(rng), rng))
    for i in range(counts["none_of_these"]):
        out.append(cases.none_of_these_case(rotate(i), names.draw(rng), rng))
    for i in range(counts["own_cause"]):
        out.append(cases.own_cause_case(rotate(i), names.draw(rng), rng))
    for i in range(counts["multi"]):
        k = rng.randint(2, 4)
        pairs, seen = [], set()
        picked = rng.sample(entries, k=min(k, len(entries)))
        for e in picked:
            n = names.draw(rng)
            while (n.ns, n.name) in seen:
                n = names.draw(rng)
            seen.add((n.ns, n.name))
            pairs.append((e, n))
        out.append(cases.multi(pairs, rng))
    for i in range(counts["truncated"]):
        out.append(cases.truncated(rotate(i), names.draw(rng), rng))
    for i in range(counts["injection"]):
        payload = cases.INJECTION_PAYLOADS[i % len(cases.INJECTION_PAYLOADS)]
        out.append(cases.injection(rotate(i), names.draw(rng), payload, rng))
    for i in range(counts["empty_candidates"]):
        out.append(cases.empty_candidates(rotate(i), names.draw(rng)))
    for i in range(counts["wrong_attribution"]):
        out.append(cases.wrong_attribution(rotate(i), names.draw(rng), rng))
    return out


def split(examples: list[Example], seed: int) -> tuple[list[Example], list[Example]]:
    import hashlib

    train, val = [], []
    for ex in examples:
        h = hashlib.sha256(f"{seed}:{ex.group}".encode()).digest()
        (val if h[0] < 26 else train).append(ex)  # ~10% by group, never straddling
    return train, val


def drop_held_out(examples: list[Example], test: list[Example]) -> list[Example]:
    """Remove any example that reuses a corpus-test fixture's group.

    Test fixtures draw (entry, ns/name) from the same synthetic pools the
    train/val rotation uses, so collisions are expected at full size; the
    spec's split-integrity rule is that a test fixture appears in neither
    train nor val. A multi example is dropped when ANY of its "+"-joined
    constituent groups collides.
    """
    held = {ex.group for ex in test}
    return [ex for ex in examples
            if not any(part in held for part in ex.group.split("+"))]


def corpus_test_set() -> list[Example]:
    import hashlib

    from kubeagent_verdict.dataset import cases, catalog, corpus, names

    # __file__ is src/kubeagent_verdict/dataset/generate.py; repo root is parents[3]
    data_dir = Path(__file__).resolve().parents[3] / "data" / "corpus"
    load = corpus.load_corpus(sorted(data_dir.glob("chaos-corpus-*.jsonl")))
    slugs = catalog.by_slug()
    out: list[Example] = []
    for row in load.rows:
        entry = slugs.get(row.fault)
        if row.skipped or entry is None or not entry.trains:
            continue
        digest = hashlib.sha256(
            f"{row.scenario}|{row.fault}|{row.k8s}|{row.distro}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        ex = cases.attributed(entry, names.draw(rng), rng)
        meta = dict(ex.meta, source={"scenario": row.scenario, "fault": row.fault,
                                     "k8s": row.k8s, "distro": row.distro, "rc": row.rc})
        out.append(Example(case=ex.case, group=ex.group, system=ex.system,
                           user=ex.user, assistant=ex.assistant, meta=meta))
    return out


def _entry_rng(*parts: str) -> random.Random:
    import hashlib

    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def held_out_case_set() -> list[Example]:
    """One held-out example per (trainable entry, non-attributed case).

    Without this the test set is 100% `attributed` — the shape corpus rows
    happen to take — so roughly half the curriculum trains and is never
    scored, and a metric computed over it describes one case while being
    reported as an overall rate.
    """
    from kubeagent_verdict.dataset import cases, catalog, names

    builders = {
        "none_of_these": cases.none_of_these_case,
        "own_cause": cases.own_cause_case,
        "truncated": cases.truncated,
        "empty_candidates": lambda e, n, rng: cases.empty_candidates(e, n),
        "wrong_attribution": cases.wrong_attribution,
    }
    out: list[Example] = []
    for entry in catalog.trainable():
        for case in HELD_OUT_CASES:
            rng = _entry_rng("held-out", case, entry.key)
            n = names.draw(rng)
            if case == "injection":
                payload = cases.INJECTION_PAYLOADS[
                    int.from_bytes(entry.key.encode()[:2], "big") % len(cases.INJECTION_PAYLOADS)]
                out.append(cases.injection(entry, n, payload, rng))
            else:
                out.append(builders[case](entry, n, rng))
    return out


def probe_sets() -> list[Example]:
    """The two adversarial eval-only slices, one row per trainable entry.

    `positional_probe` puts the correct answer last with an honest tag;
    `misattribution_probe` puts it last AND hands `attributed` to the decoy.
    Neither is ever generated into train or val — they exist to make a
    shortcut visible, and a shortcut the training data rewards is not a
    shortcut the eval can detect.
    """
    from kubeagent_verdict.dataset import cases, catalog, names

    out: list[Example] = []
    for entry in catalog.trainable():
        if not entry.losers:
            continue
        out.append(cases.positional_probe(
            entry, names.draw(_entry_rng("positional-probe", entry.key))))
        out.append(cases.misattribution_probe(
            entry, names.draw(_entry_rng("misattribution-probe", entry.key))))
    return out


def test_set() -> list[Example]:
    """The whole held-out evaluation set: corpus-grounded + curriculum + probes."""
    return corpus_test_set() + held_out_case_set() + probe_sets()


def manifest(seed: int, size: int, train: list[Example], val: list[Example],
             test: list[Example]) -> dict:
    from collections import Counter

    return {
        "seed": seed, "size": size,
        "train": len(train), "val": len(val), "test": len(test),
        "case_counts": dict(Counter(ex.case for ex in train + val)),
        "test_case_counts": dict(Counter(ex.case for ex in test)),
        "corpus_files": sorted(
            p.name for p in
            (Path(__file__).resolve().parents[3] / "data" / "corpus").glob("*.jsonl")),
    }
