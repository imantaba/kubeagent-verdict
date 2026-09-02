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


# `multi` gave up four points to `shared_origin` rather than the mix growing:
# `false_shared_rate` is the other half of the same release decider, and a model
# that learns to claim a shared origin everywhere has traded one failure for its
# mirror. `multi` stays the larger of the two, asserted by test.
# `shared_origin` and `shared_origin_decoy` MUST hold equal shares. They are
# not two cases but two halves of one: every row of the first is emitted with a
# twin from the same salt, differing only in what the origin read says. An
# unequal share would mean some scenarios appear under a single answer, and
# scenario identity would predict the label again for exactly those -- which is
# the shortcut the pairing exists to remove. The budget for the second half
# came out of `attributed`, which is the filler case and absorbs the remainder
# anyway; `multi` and `shared_origin` keep the 11/4 they were set to.
CASE_MIX = (("attributed", 26), ("none_of_these", 15), ("own_cause", 10),
            ("multi", 11), ("shared_origin", 4), ("shared_origin_decoy", 4),
            ("truncated", 5), ("injection", 10),
            ("empty_candidates", 5), ("wrong_attribution", 10))

# The held-out test set draws one example per (trainable entry, case) for each
# of these. `multi` is excluded deliberately: its group is a "+"-join of two to
# four constituent groups, so holding one out drops every training example that
# shares ANY constituent — a disproportionate bite out of the training set for
# a case the single-workload slices already cover.
# `shared_origin` is excluded for a second reason on top of `multi`'s: its
# examples come from `propagation.trainable_scenarios()`, and `held_out_case_set`
# mints its rows from the TRAINING pool. Listing it here would put trainable
# origins into the test set -- the leak the split exists to prevent, arriving by
# the other door. The eval's shared-origin rows come from `probe_sets` and draw
# only from `all_scenarios()`.
HELD_OUT_CASES = ("none_of_these", "own_cause", "truncated", "injection",
                  "empty_candidates", "wrong_attribution")


def counts_for(size: int) -> dict[str, int]:
    counts = {case: size * pct // 100 for case, pct in CASE_MIX}
    counts["attributed"] += size - sum(counts.values())
    return counts


def generate(seed: int, size: int) -> list[Example]:
    from kubeagent_verdict.dataset import cases, catalog, names, propagation

    rng = random.Random(seed)
    entries = catalog.trainable()
    counts = counts_for(size)
    out: list[Example] = []

    def rotate(i: int):
        return entries[i % len(entries)]

    train_scen = propagation.trainable_scenarios()

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
        # Every third `multi` row carries a healthy origin read, rotating over
        # the trainable pool so every label that heads a `shared_origin` row
        # also heads an independent one. This was the ONLY counter-example
        # until the `shared_origin_decoy` pairing below, and on its own it
        # closed the weaker shortcut while leaving a better one open: its
        # victims are `rng.sample(entries)`, arbitrary catalog entries whose
        # symptoms have nothing to do with the read, where a `shared_origin`
        # row's victims are the scenario's own and cohere with it. So the two
        # classes differed in the VICTIMS as well as in the read, and symptom
        # coherence separated them without reading the origin at all. The
        # pairing closes that; these rows stay because a healthy read over
        # arbitrary victims is a different counter-example, not a worse copy
        # of the same one.
        #
        # They also have no positive twin, so they are the whole of the
        # residual lean: the paired core is exactly 169/169 and the kept pile
        # reads ~0.62 toward the INDEPENDENT answer. That is the opposite
        # direction from the ~62/38 toward SHARED this comment used to
        # record, and it is un-confounded now, which is the part that
        # mattered. `drop_held_out` still takes about a third of these (a
        # `multi` group is a `+`-join of two to four catalog entries and dies
        # if any one collides with an exam group) but takes pairs whole,
        # since both halves of a pair share one group. Both splits are
        # asserted, separately, in tests/test_shared_origin_training.py --
        # neither stands in for the other.
        healthy = train_scen[(i // 3) % len(train_scen)] if i % 3 == 0 else None
        out.append(cases.multi(pairs, rng, healthy_origin=healthy))
    for i in range(counts["shared_origin"]):
        p = train_scen[i % len(train_scen)]
        # Vary the width the way `probe_sets` does: a row that always renders
        # every victim teaches the count, not the reasoning.
        victims = 2 + (i // len(train_scen)) % (len(p.victims) - 1)
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins draw
        # the same names and render the same inventory, the same candidate
        # menus with the same tags in the same order, and the same read labels
        # in the same order. Only the read CONTENTS differ, and the answer
        # flips with them -- which is the whole point: the pair is a minimal
        # contrast in the curriculum, the same instrument the exam uses.
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims))
        out.append(cases.shared_origin_decoy(
            p, random.Random(salt), victims=victims))
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

    BOTH sides are split. Building `held` from raw test groups — as this did
    until the leak was found — never inserts a compound test row's individual
    constituents as standalone keys, so an ordinary `multi` training row that
    reuses one exact constituent identity is not recognised as a collision.
    Only the multi-workload test rows have compound groups, which is precisely
    where it mattered: at seed 17 / size 5500, 103 train and 15 val rows shared
    an identity with a `multi_misattribution_probe` row that exists to test
    whether the model weighs evidence over a swapped tag.
    """
    held = {part for ex in test for part in ex.group.split("+")}
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
    """The four adversarial eval-only slices, one row per trainable entry.

    `positional_probe` puts the correct answer last with an honest tag;
    `misattribution_probe` puts it last AND hands `attributed` to the decoy;
    `multi_misattribution_probe` does the same in the multi-workload shape the
    single-workload probes cannot reach; `contradiction_probe` adds a read that
    rules the winner out, so the answer is on no candidate line at all. None is
    ever generated into train or val — they exist to make a shortcut visible,
    and a shortcut the training data rewards is not a shortcut the eval can
    detect.

    That last sentence is the limit of all four, and `contradiction_probe`
    found it the hard way: the training data rewards answering `none of these`
    to the very contradiction sentence that slice reuses, so a memorising
    model passes it. Every catalog entry appears in train, val and test, so no
    slice here can separate a model that reads from one that recites per-entry
    answers. Ruling that out needs held-out entries and a retrain.
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

    # APPENDED, never interleaved: the two slices above keep their exact row
    # positions, so a scoreboard banked against the previous test file still
    # lines up row-for-row and the negative control stays comparable.
    #
    # `multi` is ~13% of the curriculum and had no test row at all, while
    # `cases.multi()` never swaps a tag — so "trust the attributed tag" is a
    # strategy the training data never once contradicts in that shape. Neither
    # probe above can catch it there: both render a single workload. Each entry
    # is paired with the next so every entry appears twice, in both positions.
    with_losers = [e for e in catalog.trainable() if e.losers]
    for i, entry in enumerate(with_losers):
        other = with_losers[(i + 1) % len(with_losers)]
        first = names.draw(_entry_rng("multi-probe-a", entry.key))
        second = names.draw(_entry_rng("multi-probe-b", entry.key, other.key))
        # A collision used to `continue` here, which silently shrank the slice
        # and the denominator every rate on it is divided by. The builder now
        # raises instead, so a collision is a named failure rather than a
        # missing row nobody counts.
        out.append(cases.multi_misattribution_probe(
            [(entry, first), (other, second)], _entry_rng("multi-probe", entry.key)))

    # APPENDED again, for the same comparability reason. This slice contradicts
    # the winner in the reads AND hands `attributed` to the decoy, so the only
    # correct answer appears on no candidate line: a tag-copier, an
    # index-copier and a word counter all score zero on it.
    #
    # It was built to also catch a model reciting a memorised entry-to-winner
    # lookup table, and it DOES NOT — negative control v4 measured the
    # known-broken first tune at 1.0 cause / 0.0 decoy here. The read text it
    # reuses is `none_of_these_case`'s verbatim, which makes the contradiction
    # sentence a trained trigger rather than something to reason about. See
    # `cases.contradiction_probe`'s docstring for the full retraction; the
    # slice is kept for the three shortcuts it does defeat.
    for entry in catalog.trainable():
        if not entry.losers or not entry.contradiction:
            continue
        out.append(cases.contradiction_probe(
            entry, names.draw(_entry_rng("contradiction-probe", entry.key))))

    # APPENDED again, same comparability rule. Every slice above perturbs the
    # candidate menu of an otherwise ordinary row; this one changes what the
    # row is ABOUT. `multi` — training and eval alike — samples distinct
    # catalog entries and summarises them as "N workloads are failing for
    # separate reasons", 825 of 5500 rows at release size with no
    # counterexample anywhere in the curriculum. So the model was trained to
    # assert independence in exactly the shape `--investigate` sends it, and
    # nothing here could measure that until now.
    #
    # These rows come from `dataset.propagation`, not from the catalog, so they
    # share no group namespace with any training row: every group is prefixed
    # `propagation:`, `drop_held_out` drops nothing, and no training example is
    # lost to the slice.
    out.extend(shared_origin_probes())

    # APPENDED once more, same comparability rule, and the counter-example the
    # slice above cannot supply on its own. Seven of its ten rows carry an
    # origin read label that appears on no other row in the exam, and on every
    # one of them the answer is a shared cause — so "a cluster-wide read is
    # present, therefore one shared cause" scored the whole slice without
    # reading a byte of it. These rows put the SAME labels under the opposite
    # answer, drawn from the same salts so each is a minimal contrast with its
    # twin. Groups are `propagation:` too, so `drop_held_out` still drops
    # nothing and the training set does not move.
    out.extend(shared_origin_decoy_probes())
    return out


def shared_origin_probes() -> list[Example]:
    """EVAL-ONLY: one row per propagation scenario, plus narrower subsets.

    Full-width rows come first and subset rows after, so dropping the subsets
    later would leave the first six at their original indices. A subset exists
    only where a scenario has a victim to spare: it renders the same origin at
    two workloads instead of three or four, which is what tells a two-workload
    failure apart from a genuinely wide one when the scoreboard is read by
    victim count.
    """
    from kubeagent_verdict.dataset import cases, propagation

    out: list[Example] = []
    for p in propagation.all_scenarios():
        out.append(cases.shared_origin_probe(p, _entry_rng("shared-origin", p.key)))
    for p in propagation.all_scenarios():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
    return out


def shared_origin_decoy_probes() -> list[Example]:
    """EVAL-ONLY: `shared_origin_probes` with the origin reading healthy.

    Same scenarios, same order, same widths — and the SAME two rng salts, which
    is what makes each row a minimal contrast with its twin rather than a
    second question about the same cluster. Identical names give identical
    inventories, identical candidate menus and identical read labels in
    identical order; only the read contents differ, and with them the answer.
    """
    from kubeagent_verdict.dataset import cases, propagation

    out: list[Example] = []
    for p in propagation.all_scenarios():
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin", p.key)))
    for p in propagation.all_scenarios():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
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
