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
    from kubeagent_verdict.dataset.stories import Story


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
# mirror. The shared answer stays the minority among multi-workload rows:
# every `shared_origin` row has a `shared_origin_decoy` twin that answers
# "separate reasons". A `multi` row says it only when its rows show it (see
# `gold.summary_lines`). The cap test below pins
# the `shared_origin` case family's share, about 38 of every 100. The share
# of rows whose answer actually claims a shared origin is a different and
# much smaller number, about 7 of every 100; no test caps it.
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
# would put the `shared_origin` case family's share of multi-workload rows
# exactly on the 0.40 cap
# (test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows)
# -- Task 9 of the 2026-09-19 training-targets plan measures the mixes
# this was chosen over.
# 2026-09-24: `none_of_these` drops 11% -> 4%, and its 7 points go to
# `own_cause` (10% -> 13%) and `wrong_attribution` (10% -> 14%); the three
# keep their combined 31%. Thin evidence exists for the four
# `cases.THIN_ENTRIES` only, so at 11% each of those entries had about 110
# thin rows per shape against 42 clear ones, and "none of these" was the
# likelier answer on the very prompts that name a cause. At 4% each thin
# entry has 40 thin rows per shape, and clear rows outnumber them in every
# cell (test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape).
# 2026-10-03 (Spec 4b-1): the shared-origin halves keep 15% each, but their
# rows now come from `stories` through kubeagent's real pipeline. The twins
# no longer differ in an origin read: they are the broken and the healthy
# world of one story, and they differ in at least one printed line.
CASE_MIX = (("attributed", 6), ("none_of_these", 4), ("own_cause", 13),
            ("multi", 13), ("shared_origin", 15), ("shared_origin_decoy", 15),
            ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 14))

# The held-out test set draws one example per (trainable entry, case) for each
# of these. `multi` is excluded deliberately: its group is a "+"-join of two to
# four constituent groups, so holding one out drops every training example that
# shares ANY constituent — a disproportionate bite out of the training set for
# a case the single-workload slices already cover.
# `shared_origin` is excluded for a second reason on top of `multi`'s: its
# examples come from `stories.trainable()`, and `held_out_case_set` mints its
# rows from the TRAINING pool. Listing it here would put trainable origins into
# the test set -- the leak the split exists to prevent, arriving by the other
# door. The eval's shared-origin rows come from `probe_sets` and draw only from
# `stories.exam()`.
HELD_OUT_CASES = ("none_of_these", "own_cause", "truncated", "injection",
                  "empty_candidates", "wrong_attribution")


def counts_for(size: int) -> dict[str, int]:
    counts = {case: size * pct // 100 for case, pct in CASE_MIX}
    counts["attributed"] += size - sum(counts.values())
    return counts


def _draw(entry, rng: random.Random):
    """Draw one row's names for `entry`, at the entry's restart floor."""
    from kubeagent_verdict.dataset import names

    return names.draw(rng, min_restarts=entry.min_restarts)


def generate(seed: int, size: int) -> list[Example]:
    from kubeagent_verdict.dataset import cases, catalog, stories

    rng = random.Random(seed)
    entries = catalog.trainable()
    counts = counts_for(size)
    out: list[Example] = []

    def rotate(i: int):
        return entries[i % len(entries)]

    # `attributed`, `truncated` and `injection` answer with the rules' own
    # cause, so they rotate over the entries the rules decide. The other
    # cases rotate over every trainable entry.
    job1 = catalog.job1_entries()

    def rotate_job1(i: int):
        return job1[i % len(job1)]

    for i in range(counts["attributed"]):
        e = rotate_job1(i)
        out.append(cases.attributed(e, _draw(e, rng), rng))
    # Thin evidence exists for four entries only. Rotate through them, and
    # alternate the two undecided shapes once per full pass.
    thin = [next(e for e in entries if e.key == key) for key in cases.THIN_ENTRIES]
    for i in range(counts["none_of_these"]):
        shape = ("refuted", "ruled_out")[(i // len(thin)) % 2]
        e = thin[i % len(thin)]
        out.append(cases.none_of_these_case(e, _draw(e, rng), shape=shape))
    for i in range(counts["own_cause"]):
        e = rotate(i)
        out.append(cases.own_cause_case(e, _draw(e, rng)))
    # The last counted `multi` slot is the worker-containerd-stop self-pair,
    # below, so this loop builds one row fewer.
    # Each row draws 2-4 catalog pairs. A clash raises, and the caller draws
    # again.
    for _ in range(counts["multi"] - 1):
        k = rng.randint(2, 4)
        pairs = []
        picked = rng.sample(entries, k=min(k, len(entries)))
        for e in picked:
            # Draw again until the workload is new to the row, runs on a
            # node of its own and uses a claim of its own (`cases.multi_clash`).
            n = _draw(e, rng)
            while cases.multi_clash([*(pn for _pe, pn in pairs), n]):
                n = _draw(e, rng)
            pairs.append((e, n))
        out.append(cases.multi(pairs, rng))
    # The last counted `multi` slot, training-only: worker-containerd-stop
    # paired with itself at two different (ns, node) draws. Both stay
    # confirmed (its node object is intent="cause", so _multi_objects never
    # draws it) -- two different node names give two different group_text
    # values, so this row's label always comes out "separate". A different
    # namespace and a different node also keep the two workloads and their
    # claims apart, so the pair never clashes. A build with no `multi` slot
    # has no self-pair, and every build has exactly `size` rows.
    if counts["multi"] >= 1:
        worker_containerd_stop = catalog.by_slug()["worker-containerd-stop"]
        names_a = _draw(worker_containerd_stop, rng)
        while True:
            names_b = _draw(worker_containerd_stop, rng)
            if names_b.ns != names_a.ns and names_b.node != names_a.node:
                break
        out.append(cases.multi(
            [(worker_containerd_stop, names_a), (worker_containerd_stop, names_b)],
            rng))
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
    # divide evenly across the two widths. About one node ruled
    # pair in three, 26 of 80 at size 8000 (every
    # third trip around the six-story ruled pool) renders the unverified
    # twin instead of the confirmed one (spec section 5); the label comes
    # out "none" either way, which is what lets a plain `shared_origin` row
    # and an unverified one share one case name and one budget.
    # 2026-10-03 (Spec 4b-1): the pools are `stories.trainable()`, 35 plain
    # stories then 6 ruled ones (`cls == "R"`), about 27 pairs per plain story
    # and 40 per ruled story at size 8000.
    pool = stories.trainable()
    plain = tuple(st for st in pool if st.cls == "P")
    ruled = tuple(st for st in pool if st.cls == "R")
    for i in range(counts["shared_origin"]):
        if i % 5 == 4:
            j = i // 5
            p = ruled[j % len(ruled)]
            t = j // len(ruled)
            # Vary the width the way `probe_sets` does: a row that always
            # renders every victim teaches the count, not the reasoning.
            victims = 2 + (t // 3) % (len(p.victims) - 1)
            unverified = p.origin_kind == "node" and t % 3 == 2
        else:
            k = i - (i + 1) // 5
            p = plain[k % len(plain)]
            victims = 2 + (k // len(plain)) % (len(p.victims) - 1)
            unverified = False
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins make
        # the same draws (`shared_origin.draw` draws everything before it
        # branches on the world). Only the world differs -- broken or healthy --
        # and with it at least one printed line and the answer: the pair is a
        # minimal contrast in the curriculum, the same instrument the exam uses.
        #
        # `unverified` never applies to the decoy twin: the healthy world has
        # no origin candidate, so there is no "could not check" world for it.
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims,
                                       unverified=unverified))
        out.append(cases.shared_origin_decoy(p, random.Random(salt), victims=victims))
    for i in range(counts["truncated"]):
        e = rotate_job1(i)
        out.append(cases.truncated(e, _draw(e, rng), rng))
    for i in range(counts["injection"]):
        payload = cases.INJECTION_PAYLOADS[i % len(cases.INJECTION_PAYLOADS)]
        e = rotate_job1(i)
        out.append(cases.injection(e, _draw(e, rng), payload, rng))
    for i in range(counts["empty_candidates"]):
        e = rotate(i)
        out.append(cases.empty_candidates(e, _draw(e, rng)))
    for i in range(counts["wrong_attribution"]):
        e = rotate(i)
        out.append(cases.wrong_attribution(e, _draw(e, rng)))
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

    from kubeagent_verdict.dataset import cases, catalog, corpus

    # __file__ is src/kubeagent_verdict/dataset/generate.py; repo root is parents[3]
    data_dir = Path(__file__).resolve().parents[3] / "data" / "corpus"
    load = corpus.load_corpus(sorted(data_dir.glob("chaos-corpus-*.jsonl")))
    slugs = catalog.by_slug()
    job1 = {e.key for e in catalog.job1_entries()}
    out: list[Example] = []
    for row in load.rows:
        entry = slugs.get(row.fault)
        if row.skipped or entry is None or not entry.trains:
            continue
        digest = hashlib.sha256(
            f"{row.scenario}|{row.fault}|{row.k8s}|{row.distro}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        # A fault whose entry the rules do not decide has no rule cause to
        # be the gold, so its row asks for the entry's own cause instead.
        if entry.key in job1:
            ex = cases.attributed(entry, _draw(entry, rng), rng)
        else:
            ex = cases.own_cause_case(entry, _draw(entry, rng))
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

    `truncated` and `injection` are the exceptions on the other side: they
    answer with the rules' cause, so they give one row per entry the rules
    decide (`catalog.job1_entries()`) and none for the rest.

    Without this the test set is 100% `attributed` — the shape corpus rows
    happen to take — so roughly half the curriculum trains and is never
    scored, and a metric computed over it describes one case while being
    reported as an overall rate.

    `none_of_these` is the exception to one row per entry: thin evidence
    exists only for `cases.THIN_ENTRIES`, so that case gives one row per thin
    entry per undecided shape, 8 rows in all.
    """
    from kubeagent_verdict.dataset import cases, catalog

    builders = {
        "own_cause": lambda e, n, rng: cases.own_cause_case(e, n),
        "truncated": cases.truncated,
        "empty_candidates": lambda e, n, rng: cases.empty_candidates(e, n),
        "wrong_attribution": lambda e, n, rng: cases.wrong_attribution(e, n),
    }
    job1 = {e.key for e in catalog.job1_entries()}
    out: list[Example] = []
    for entry in catalog.trainable():
        for case in HELD_OUT_CASES:
            if case in ("truncated", "injection") and entry.key not in job1:
                continue
            if case == "none_of_these":
                if entry.key in cases.THIN_ENTRIES:
                    for shape in ("refuted", "ruled_out"):
                        n = _draw(entry, _entry_rng("held-out", case, entry.key, shape))
                        out.append(cases.none_of_these_case(entry, n, shape=shape))
                continue
            rng = _entry_rng("held-out", case, entry.key)
            n = _draw(entry, rng)
            if case == "injection":
                payload = cases.INJECTION_PAYLOADS[
                    int.from_bytes(entry.key.encode()[:2], "big") % len(cases.INJECTION_PAYLOADS)]
                out.append(cases.injection(entry, n, payload, rng))
            else:
                out.append(builders[case](entry, n, rng))
    return out


def probe_sets() -> list[Example]:
    """The four adversarial eval-only slices, one row per trainable entry
    that declares an object.

    `positional_probe` gives one row only per entry the rules decide
    (`catalog.job1_entries()`): its winner prints last, behind a decoy the
    rules attribute and then refute;
    `misattribution_probe` rules every candidate out, so the answer is on no
    candidate line (no attributed candidate since 2026-09-16; since
    2026-09-24 also no header and no object reads); `multi_misattribution_probe`
    hands `attributed` to the decoy in the multi-workload shape the
    single-workload probes cannot reach;
    `contradiction_probe` gives one row per entry the rules decide: a
    fresh read and an event line argue against the rules' cause, and the
    answer is still that cause. None is
    ever generated into train or val — they exist to make a shortcut visible,
    and a shortcut the training data rewards is not a shortcut the eval can
    detect.

    That is also the limit of all four. Every catalog entry is in train,
    val and test, so no slice here can tell a model that reads from one
    that recites each entry's answer. Ruling that out needs held-out
    entries and a retrain.
    """
    from kubeagent_verdict.dataset import cases, catalog

    job1 = {e.key for e in catalog.job1_entries()}
    out: list[Example] = []
    for entry in catalog.trainable():
        if not entry.objects:
            continue
        if entry.key in job1:
            positional_rng = _entry_rng("positional-probe", entry.key)
            out.append(cases.positional_probe(
                entry, _draw(entry, positional_rng), positional_rng))
        out.append(cases.misattribution_probe(
            entry, _draw(entry, _entry_rng("misattribution-probe", entry.key))))

    # APPENDED, never interleaved: the two slices above keep their exact row
    # positions, so a scoreboard banked against the previous test file still
    # lines up row-for-row and the negative control stays comparable. That
    # held until 2026-09-26 (faithful prompts): `positional_probe` dropped
    # its rows for the entries the rules do not decide, and a new entry
    # joined both slices, so a scoreboard banked before then no longer lines
    # up with this file.
    #
    # `multi` is ~13% of the curriculum and had no test row at all, while
    # `cases.multi()` never swaps a tag — so "trust the attributed tag" is a
    # strategy the training data never once contradicts in that shape. Neither
    # probe above can catch it there: both render a single workload. Each entry
    # is paired with the next so every entry appears twice, in both positions.
    with_objects = [e for e in catalog.trainable() if e.objects]
    for i, entry in enumerate(with_objects):
        other = with_objects[(i + 1) % len(with_objects)]
        first = _draw(entry, _entry_rng("multi-probe-a", entry.key))
        second_rng = _entry_rng("multi-probe-b", entry.key, other.key)
        second = _draw(other, second_rng)
        # A collision used to `continue` here, which silently shrank the slice
        # and the denominator every rate on it is divided by. The builder now
        # raises instead, so a collision is a named failure rather than a
        # missing row nobody counts. Since 2026-09-26 (faithful prompts) a
        # collision redraws the second workload from its own rng, as
        # `generate()`'s `multi` loop does, so a pair that does not collide
        # draws exactly what it drew before. A collision is any clash
        # `cases.multi_clash` names: one workload, one node or one claim.
        while cases.multi_clash([first, second]):
            second = _draw(other, second_rng)
        out.append(cases.multi_misattribution_probe(
            [(entry, first), (other, second)], _entry_rng("multi-probe", entry.key)))

    # APPENDED again, for the same comparability reason. One row per entry
    # the rules decide, in catalog order. Each row's object ends on a fresh
    # read that cannot confirm it, and for 15 of them the entry's
    # `contradiction_events` add event lines that point somewhere else. The
    # rules still decide the row, so the answer is their cause. The slice
    # checks that an answer keeps to the rules' decision when the evidence
    # pulls the other way.
    #
    # Until 2026-09-26 (faithful prompts) the answer here was `none of
    # these`, and the slice was meant to catch a model that recites each
    # entry's answer. It could not: every entry is in train, val and test.
    # The row is now built on the gather, so the three entries the rules do
    # not decide left it (19 rows -> 17), and a scoreboard banked before
    # then does not line up with this slice.
    for entry in catalog.job1_entries():
        out.append(cases.contradiction_probe(
            entry, _draw(entry, _entry_rng("contradiction-probe", entry.key))))

    # APPENDED again, same comparability rule. Every slice above perturbs the
    # candidate menu of an otherwise ordinary row; this one changes what the
    # row is ABOUT. `multi` — training and eval alike — samples distinct
    # catalog entries and summarises them as "N workloads are failing for
    # separate reasons", 825 of 5500 rows at release size with no
    # counterexample anywhere in the curriculum. So the model was trained to
    # assert independence in exactly the shape `--investigate` sends it, and
    # nothing here could measure that until now.
    #
    # These rows come from `dataset.stories` (`dataset.propagation` until
    # 2026-10-03), not from the catalog, so they share no group namespace with
    # any training row: every group is still prefixed `propagation:`,
    # `drop_held_out` drops nothing, and no training example is lost to the
    # slice.
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
    # 2026-10-03 (Spec 4b-1): no family row carries an origin read label any
    # more. Each twin pair is the broken and the healthy world of one story.
    out.extend(shared_origin_decoy_probes())
    return out


def shared_origin_probes() -> list[Example]:
    """EVAL-ONLY: one row per exam story, plus narrower subsets.

    Full-width rows come first and subset rows after, so dropping the subsets
    later would leave the first six at their original indices. A subset exists
    only where a story has a victim to spare: it renders the same origin at
    two workloads instead of three or four, which is what tells a two-workload
    failure apart from a genuinely wide one when the scoreboard is read by
    victim count.
    """
    from kubeagent_verdict.dataset import cases, stories

    out: list[Example] = []
    for p in stories.exam():
        out.append(cases.shared_origin_probe(p, _entry_rng("shared-origin", p.key)))
    for p in stories.exam():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
    return out


def shared_origin_decoy_probes() -> list[Example]:
    """EVAL-ONLY: `shared_origin_probes` in each story's healthy world.

    Same stories, same order, same widths — and the SAME two rng salts, which
    is what makes each row a minimal contrast with its twin rather than a
    second question about the same cluster. Identical salts give identical
    draws; only the world differs (healthy instead of broken), and with it at
    least one printed line and the answer.
    """
    from kubeagent_verdict.dataset import cases, stories

    out: list[Example] = []
    for p in stories.exam():
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin", p.key)))
    for p in stories.exam():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
    return out


def _shared_origin_twin_pairs(origins: Sequence[Story], pairs_per_origin: int,
                              salt: str, width_of: Callable[[Story, int], int | None],
                              error_prefix: str) -> list[Example]:
    """Build twin pairs (a probe row and its decoy) over a list of stories.

    Both halves of a pair use the same salted rng, so they draw the same
    values and differ only in the world (broken or healthy). `width_of(p, i)`
    picks the victim count for pair `i` of story `p`; returning `None`
    means the full victim set. A pair is keyed on its group, which names
    the victims and is the same in both worlds. A repeated group would merge
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
            assert probe.group == decoy.group, (probe.group, decoy.group)
            key = probe.group
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
    (same draws -- only the world, at least one printed line and the answer
    differ). Widths alternate between the full victim set and a two-victim
    subset where the story has a victim to spare. A repeated group would
    silently merge two pairs in the paired scoring, so a collision raises
    instead of shrinking the set.
    """
    from kubeagent_verdict.dataset import stories

    return _shared_origin_twin_pairs(
        stories.exam(), pairs_per_origin, "shared-origin-wide",
        lambda p, i: 2 if i % 2 == 1 and len(p.victims) >= 3 else None,
        "wide-probe")


def shared_origin_cousin_probes(pairs_per_origin: int = 1) -> list[Example]:
    """EVAL-ONLY, DIAGNOSTIC-ONLY: one fresh twin pair per TRAINABLE origin.

    The wide probe asks the six held-out origins five times each. This one
    asks the other question: on the stories the model studied, does it
    read the origin at all? One pair per trainable story, at full width
    (every victim the story has). Every trainable story has three or more
    victims (Ruling 50), so every decoy half carries three or more verdicts,
    the shape the 0907 model broke its JSON on.

    It is in-distribution on purpose. A model that scores well here and
    fails the exam has a coverage gap; one that fails here has a recipe
    problem. It goes to its own file, never into `test_set()`, and its
    numbers gate no release. Fresh salts keep every pair distinct from the
    training rows' draws; the SAME salt on both halves keeps each pair a
    minimal contrast. A repeated group would silently merge two pairs in
    the paired scoring, so a collision raises instead of shrinking the set.
    """
    from kubeagent_verdict.dataset import stories

    return _shared_origin_twin_pairs(
        stories.trainable(), pairs_per_origin,
        "shared-origin-cousin", lambda p, i: None, "cousin-probe")


def test_set() -> list[Example]:
    """The whole held-out evaluation set: corpus-grounded + curriculum + probes."""
    return corpus_test_set() + held_out_case_set() + probe_sets()


def manifest(seed: int, size: int, train: list[Example], val: list[Example],
             test: list[Example]) -> dict:
    """The dataset's summary. `checker_violations` is a report: each case's
    count of places its rows differ from what kubeagent sends. It never
    blocks a write."""
    from collections import Counter

    from kubeagent_verdict.dataset import checker

    return {
        "seed": seed, "size": size,
        "train": len(train), "val": len(val), "test": len(test),
        "case_counts": dict(Counter(ex.case for ex in train + val)),
        "test_case_counts": dict(Counter(ex.case for ex in test)),
        "corpus_files": sorted(
            p.name for p in
            (Path(__file__).resolve().parents[3] / "data" / "corpus").glob("*.jsonl")),
        "checker_violations": checker.count_by_case(
            to_row(ex) for ex in train + val + test),
    }
