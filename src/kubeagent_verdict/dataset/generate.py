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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kubeagent_verdict.dataset.propagation import Propagation


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


# `multi` gave up four points to `shared_origin` when the case was added,
# rather than the mix growing: job3's honesty check is the other half of the
# same release decider, and a model that learns to claim a shared origin
# everywhere fails it on the decoy twin, trading one failure for its
# mirror. The shared answer stays the minority among multi-workload rows,
# asserted by test: every
# `shared_origin` row has a `shared_origin_decoy` twin that answers "separate
# reasons", and `multi` answers the same.
# `shared_origin` and `shared_origin_decoy` MUST hold equal shares. They are
# not two cases but two halves of one: every row of the first is emitted with a
# twin from the same salt, differing only in what the origin read says. An
# unequal share would mean some scenarios appear under a single answer, and
# scenario identity would predict the label again for exactly those -- which is
# the shortcut the pairing exists to remove.
# Both halves sit at 8. They started at 4, which gave each of the 24 trainable
# scenarios about 9 pairs at the build size (seed 17, size 5500). The
# validation split takes groups by hash, not by count, so some scenarios
# reached the optimizer with 5 pairs. The model trained on that pile said
# "shared" on 6 of the exam's 10 decoy rows. At 8 every scenario keeps at
# least 14 pairs in train; 7 left one scenario at 11.
# tests/test_shared_origin_floor.py pins the floor at 12. The budget for both
# raises came out of `attributed`, which is the filler case and absorbs the
# remainder anyway.
# 2026-09-08: both halves move again, from 8% to 12%, and `attributed` gives
# up the 8 points (18% -> 10%). The 0907 model failed decider 5 with 15 of 24
# scenarios holding only two victims and no exam layout in training. The
# pool doubles to 48 scenarios in this slice; at 12% and size 8000 each half
# is 960 rows, 20 pairs per scenario, about 18 in train after the split.
# tests/test_shared_origin_floor.py still pins the floor at 12.
# 2026-09-19 (spec section 6): both halves move again, 12% -> 15%, so a
# shared_origin/shared_origin_decoy pair can be spent on the six ruled
# stories one pair in five (the rest still walk the 48 plain stories,
# spec section 6's loop). `attributed` and `none_of_these` each give up
# four points; two of the eight go to `multi` (11% -> 13%) rather than to
# the shared-origin halves alone, because raising only the shared side
# would put the shared answer's share of multi-workload rows exactly on
# the 0.40 cap (test_the_shared_answer_stays_the_minority_among_multi_workload_rows)
# -- Task 9 of the 2026-09-19 training-targets plan measures the mixes
# this was chosen over.
CASE_MIX = (("attributed", 6), ("none_of_these", 11), ("own_cause", 10),
            ("multi", 13), ("shared_origin", 15), ("shared_origin_decoy", 15),
            ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 10))

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
        # residual lean: the paired core is exactly even (1200/1200 at the
        # build size, re-measured 2026-09-19 after Task 9's mix move to 15%
        # on both shared-origin halves -- was 960/960) and the kept pile
        # reads ~0.543 toward the INDEPENDENT answer (was ~0.55; still
        # tests/test_shared_origin_training.py's own re-measurement, not
        # re-derived here). That is the opposite
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
    # Training-only: worker-containerd-stop paired with itself at two different
    # (ns, node) draws. Both stay confirmed (its node object is intent="cause",
    # so _multi_objects never draws it) -- two different node names give two
    # different group_text values, so this row's label always comes out
    # "separate". Not one of the CASE_MIX-counted "multi" rows.
    worker_containerd_stop = catalog.by_slug()["worker-containerd-stop"]
    names_a = names.draw(rng)
    while True:
        names_b = names.draw(rng)
        if names_b.ns != names_a.ns and names_b.node != names_a.node:
            break
    out.append(cases.multi(
        [(worker_containerd_stop, names_a), (worker_containerd_stop, names_b)],
        rng, healthy_origin=None))
    # 2026-09-19 (spec section 6): one pair in five now comes from the six
    # ruled stories instead of the 48 plain ones, so the rules pass gets a
    # shared origin it can confirm itself and training finally carries
    # `shared`-labelled rows. The two pools are walked with their own
    # indices (`k` skips the one ruled slot out of every five `i`s, `j`/`t`
    # count ruled draws and full trips around the ruled pool) so each pool
    # cycles through its own stories evenly (20 draws per plain story, 40
    # per ruled story, at size 8000), the same way the single
    # `i % len(train_scen)` walk did before the ruled stories existed.
    # Widths are near-even, not even: each ruled story's 40 draws split 21
    # at width 2 against 19 at width 3 at size 8000, since 40 does not
    # divide evenly across the two widths. One node ruled
    # pair in three (every
    # third trip around the six-story ruled pool) renders the unverified
    # twin instead of the confirmed one (spec section 5); the label comes
    # out "none" either way, which is what lets a plain `shared_origin` row
    # and an unverified one share one case name and one budget.
    plain = tuple(p for p in train_scen if p.origin_object is None)
    ruled = tuple(p for p in train_scen if p.origin_object is not None)
    for i in range(counts["shared_origin"]):
        if i % 5 == 4:
            j = i // 5
            p = ruled[j % len(ruled)]
            t = j // len(ruled)
            # Vary the width the way `probe_sets` does: a row that always
            # renders every victim teaches the count, not the reasoning.
            victims = 2 + (t // 3) % (len(p.victims) - 1)
            unverified = p.origin_object.kind == "node" and t % 3 == 2
        else:
            k = i - (i + 1) // 5
            p = plain[k % len(plain)]
            victims = 2 + (k // len(plain)) % (len(p.victims) - 1)
            unverified = False
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins draw
        # the same names and render the same inventory, the same candidate
        # menus with the same tags in the same order, and the same read labels
        # in the same order. Only the read CONTENTS differ, and the answer
        # flips with them -- which is the whole point: the pair is a minimal
        # contrast in the curriculum, the same instrument the exam uses.
        #
        # `unverified` never applies to the decoy twin: the healthy read it
        # draws already refutes every victim outright, so there is no second,
        # "could not check" world for it to render (Task 8's docstring).
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims,
                                       unverified=unverified))
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
        if not entry.objects:
            continue
        positional_rng = _entry_rng("positional-probe", entry.key)
        out.append(cases.positional_probe(
            entry, names.draw(positional_rng), positional_rng))
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
    with_objects = [e for e in catalog.trainable() if e.objects]
    for i, entry in enumerate(with_objects):
        other = with_objects[(i + 1) % len(with_objects)]
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
        if not entry.objects or not entry.contradiction:
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


def _shared_origin_twin_pairs(origins: Sequence[Propagation], pairs_per_origin: int,
                              salt: str, width_of: Callable[[Propagation, int], int | None],
                              error_prefix: str) -> list[Example]:
    """Build twin pairs (a probe row and its decoy) over a list of origins.

    Both halves of a pair use the same salted rng, so they draw identical
    names and differ only in what the origin read says. `width_of(p, i)`
    picks the victim count for pair `i` of origin `p`; returning `None`
    means the full victim set. A repeated expected-workload key would merge
    two pairs in the paired scoring, so it raises instead.
    """
    from kubeagent_verdict.dataset import cases

    out: list[Example] = []
    seen: dict[str, str] = {}
    for p in origins:
        for i in range(pairs_per_origin):
            width = width_of(p, i)
            probe = cases.shared_origin_probe(
                p, _entry_rng(salt, p.key, str(i)), victims=width)
            decoy = cases.shared_origin_decoy_probe(
                p, _entry_rng(salt, p.key, str(i)), victims=width)
            key = "|".join(sorted(probe.meta["expected"]))
            if key in seen:
                raise ValueError(
                    f"{error_prefix} pair key collision: {seen[key]} and "
                    f"{p.key}#{i} both drew {key!r}; a collision would "
                    "merge two pairs in the paired scoring")
            seen[key] = f"{p.key}#{i}"
            out.append(probe)
            out.append(decoy)
    return out


def shared_origin_wide_probes(pairs_per_origin: int = 5) -> list[Example]:
    """EVAL-ONLY, DIAGNOSTIC-ONLY: five twin pairs per held-out origin.

    The frozen exam carries one or two shared-origin pairs per origin --
    enough to score a model, too few to diagnose one. "It always fails on
    CoreDNS" resting on two pairs could be a coin landing badly twice. This
    widened set answers the diagnostic question: when the model gets an
    origin wrong, does it get that origin wrong every time? Five pairs per
    origin make a per-origin verdict rest on five observations.

    It goes to its own file, never into `test_set()`, and its numbers gate
    no release. Fresh salts keep every pair distinct from the frozen exam's
    pairs; the SAME salt on both halves keeps each pair a minimal contrast
    (same names, same menus, same read labels -- only the read contents and
    the answer differ). Widths alternate between the full victim set and a
    two-victim subset where the scenario has a victim to spare. A repeated
    pair key would silently merge two pairs in the paired scoring, so a
    collision raises instead of shrinking the set.
    """
    from kubeagent_verdict.dataset import propagation

    return _shared_origin_twin_pairs(
        propagation.all_scenarios(), pairs_per_origin, "shared-origin-wide",
        lambda p, i: 2 if i % 2 == 1 and len(p.victims) >= 3 else None,
        "wide-probe")


def shared_origin_cousin_probes(pairs_per_origin: int = 1) -> list[Example]:
    """EVAL-ONLY, DIAGNOSTIC-ONLY: one fresh twin pair per TRAINABLE origin.

    The wide probe asks the six held-out origins five times each. This one
    asks the other question: on the scenarios the model studied, does it
    read the origin at all? One pair per trainable scenario, at full width,
    so every decoy half carries three or four verdicts, which is the shape
    the 0907 model broke its JSON on.

    It is in-distribution on purpose. A model that scores well here and
    fails the exam has a coverage gap; one that fails here has a recipe
    problem. It goes to its own file, never into `test_set()`, and its
    numbers gate no release. Fresh salts keep every pair distinct from the
    training rows' draws; the SAME salt on both halves keeps each pair a
    minimal contrast. A repeated pair key would silently merge two pairs in
    the paired scoring, so a collision raises instead of shrinking the set.
    """
    from kubeagent_verdict.dataset import propagation

    return _shared_origin_twin_pairs(
        propagation.trainable_scenarios(), pairs_per_origin,
        "shared-origin-cousin", lambda p, i: None, "cousin-probe")


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
