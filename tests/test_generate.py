import collections
import json
import random
import re

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, generate, names

BANNED = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),  # any dotted-quad IP
    re.compile(r"https?://"),
    re.compile(r"kubeconfig", re.IGNORECASE),
    re.compile(r"/home/"),
    re.compile(r"@"),
)


def test_generate_is_deterministic():
    a = generate.generate(seed=17, size=40)
    b = generate.generate(seed=17, size=40)
    assert [generate.to_row(x) for x in a] == [generate.to_row(y) for y in b]
    assert a != generate.generate(seed=18, size=40)


def test_provenance_no_banned_text():
    for ex in generate.generate(seed=17, size=60):
        blob = ex.user + "\n" + ex.assistant
        for pat in BANNED:
            assert not pat.search(blob), f"{ex.meta}: {pat.pattern}"


def test_every_example_is_contract_valid():
    for ex in generate.generate(seed=17, size=60):
        assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
        assert ex.system == c.SYSTEM_PROMPT
        doc = json.loads(ex.assistant)
        assert set(doc) == {"verdicts", "summary"}
        assert 1 <= len(doc["verdicts"]) <= c.MAX_VERDICT_ROWS
        for row in doc["verdicts"]:
            assert row["confidence"] in c.CONFIDENCE_VALUES
            assert re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", row["workload"])
            assert row["workload"] in ex.user
        lines = [ln for ln in doc["summary"].split("\n") if ln.strip()]
        assert 1 <= len(lines) <= c.MAX_SUMMARY_LINES


def test_to_row_schema():
    (ex,) = generate.generate(seed=17, size=1)
    row = generate.to_row(ex)
    assert set(row) == {"messages", "meta"}
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]


def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 300, "none_of_these": 150, "own_cause": 100,
                      "multi": 150, "truncated": 50, "injection": 100,
                      "empty_candidates": 50, "wrong_attribution": 100}
    assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed


def test_case_mix_present_in_generated_set():
    exs = generate.generate(seed=17, size=200)
    seen = {ex.case for ex in exs}
    assert seen == {"attributed", "none_of_these", "own_cause", "multi",
                    "truncated", "injection", "empty_candidates",
                    "wrong_attribution"}


def test_split_never_straddles_a_group():
    exs = generate.generate(seed=17, size=300)
    train, val = generate.split(exs, seed=17)
    train_groups = {ex.group for ex in train}
    val_groups = {ex.group for ex in val}
    assert not (train_groups & val_groups)
    frac = len(val) / (len(train) + len(val))
    assert 0.04 <= frac <= 0.20


def test_corpus_test_set_derives_from_committed_rows():
    exs = generate.corpus_test_set()
    assert exs, "no corpus-derived test examples"
    for ex in exs:
        assert ex.meta["source"]["fault"]
        assert ex.meta["source"]["distro"] in {"kind", "k3s"}


def test_drop_held_out_removes_colliding_groups():
    exs = generate.generate(seed=17, size=60)
    fake_test = [exs[0]]  # pretend the first example's group is a test fixture
    kept = generate.drop_held_out(exs, fake_test)
    assert exs[0].group not in {ex.group for ex in kept}
    assert len(kept) < len(exs)


def test_test_set_is_not_all_one_case():
    # The first tuned model was scored on a held-out set that was 100%
    # `attributed`, so ~45% of the curriculum trained and was never measured.
    cases_seen = {ex.case for ex in generate.test_set()}
    assert "attributed" in cases_seen
    assert cases_seen >= set(generate.HELD_OUT_CASES)
    assert {"positional_probe", "misattribution_probe"} <= cases_seen


def test_probe_rows_never_enter_train_or_val():
    exs = generate.generate(seed=17, size=300)
    train, val = generate.split(exs, seed=17)
    test = generate.test_set()
    train = generate.drop_held_out(train, test)
    val = generate.drop_held_out(val, test)
    banned = {"positional_probe", "misattribution_probe", "contradiction_probe",
              "multi_misattribution_probe", "shared_origin_probe"}
    assert not banned & {ex.case for ex in train + val}
    # SPLIT on the test side too. This read `{ex.group for ex in test}` and so
    # re-derived production's own blind spot — it asserted the buggy rule
    # against itself and passed while 103 train rows leaked at release size.
    held = {part for ex in test for part in ex.group.split("+")}
    for ex in train + val:
        assert not any(part in held for part in ex.group.split("+"))


def test_drop_held_out_splits_compound_test_groups():
    # A multi-workload test row's group is a "+"-join, so an exclusion set built
    # from raw test groups never carries its constituents as standalone keys and
    # a train row reusing one is not recognised as a collision. Both sides must
    # be split, not just the candidate's.
    exs = generate.generate(seed=17, size=60)
    victim = next(ex for ex in exs if "+" not in ex.group)
    compound = generate.Example(case="multi_misattribution_probe",
                                group=victim.group + "+other-entry:probes/second",
                                system="", user="", assistant="", meta={})
    kept = generate.drop_held_out(exs, [compound])
    assert victim.group not in {ex.group for ex in kept}


def test_test_set_is_deterministic():
    assert [generate.to_row(x) for x in generate.test_set()] == \
           [generate.to_row(y) for y in generate.test_set()]


def test_every_probe_row_carries_a_decoy_that_is_not_the_answer():
    for ex in generate.test_set():
        if ex.case not in ("positional_probe", "misattribution_probe"):
            continue
        assert ex.meta["decoy_cause"]
        assert ex.meta["decoy_cause"] != ex.meta["expected_cause"]
        assert ex.meta["decoy_cause"] in ex.user


# The multi probe is APPENDED after the two single-workload probe slices, never
# interleaved: the existing 205 test rows keep their exact positions, so a
# scoreboard banked against the old file still lines up row-for-row with the
# new one and the negative control stays comparable.
def test_multi_probe_is_appended_without_disturbing_the_existing_probes():
    from kubeagent_verdict.dataset import catalog, generate
    probes = generate.probe_sets()
    trainable = [e for e in catalog.trainable() if e.losers]
    head = probes[:2 * len(trainable)]
    assert [ex.case for ex in head] == ["positional_probe", "misattribution_probe"] * len(
        trainable)
    # Each new slice is a LAYER appended after the last, never interleaved, so
    # every row a previous scoreboard scored keeps its index.
    tail = probes[2 * len(trainable):]
    assert tail, "no multi probe rows were generated"
    seen, order = [], []
    for ex in tail:
        if not order or order[-1] != ex.case:
            assert ex.case not in seen, f"{ex.case} rows are interleaved, not appended"
            seen.append(ex.case)
            order.append(ex.case)
    assert order == ["multi_misattribution_probe", "contradiction_probe",
                     "shared_origin_probe"]


def test_contradiction_probe_is_appended_last_one_row_per_entry():
    from kubeagent_verdict.dataset import catalog, generate
    probes = generate.probe_sets()
    trainable = [e for e in catalog.trainable() if e.losers and e.contradiction]
    tail = [ex for ex in probes if ex.case == "contradiction_probe"]
    assert len(tail) == len(trainable)
    # Appended, never interleaved: every earlier probe row keeps its position, so
    # a scoreboard banked against the previous test file still lines up. The run
    # is no longer the LAST rows in the file — `shared_origin_probe` was appended
    # after it — so what is asserted is that the run is contiguous and that
    # nothing but the shared-origin block follows it. A slice appended after this
    # one is allowed by construction; a row interleaved INTO this one is not.
    cases = [ex.case for ex in probes]
    first = cases.index("contradiction_probe")
    assert cases[first:first + len(tail)] == ["contradiction_probe"] * len(tail)
    assert set(cases[first + len(tail):]) == {"shared_origin_probe"}
    for ex in tail:
        assert ex.meta["expected_cause"] == c.NONE_OF_THESE
        assert ex.meta["decoy_cause"] in ex.user


def test_multi_probe_rows_carry_two_distinct_workloads():
    import json as _json

    from kubeagent_verdict.dataset import generate
    tail = [ex for ex in generate.probe_sets() if ex.case == "multi_misattribution_probe"]
    for ex in tail:
        rows = _json.loads(ex.assistant)["verdicts"]
        assert len({r["workload"] for r in rows}) == len(rows) >= 2


def test_multi_probe_is_deterministic():
    from kubeagent_verdict.dataset import generate
    a = [ex.user for ex in generate.probe_sets()]
    b = [ex.user for ex in generate.probe_sets()]
    assert a == b


def test_provenance_no_banned_text_in_test_set():
    """The same denylist, over the rows `test_provenance_no_banned_text` cannot see.

    That test scans `generate(seed=17, size=60)` — train/val shaped. The test
    set comes from a different code path (`test_set`), draws on the
    corpus-derived and held-out-case fixtures, and appends four probe slices
    that no train/val batch contains. Those rows ship in
    `out/dataset/test.jsonl` and get quoted into scoreboards and docs, so they
    need the same guard.
    """
    for ex in generate.test_set():
        blob = ex.user + "\n" + ex.assistant
        for pat in BANNED:
            assert not pat.search(blob), f"{ex.meta}: {pat.pattern}"


def test_provenance_scan_reaches_every_catalog_entry():
    """Coverage, not just patterns: a denylist only guards text it renders.

    `generate(seed=17, size=60)` samples cases at random, so it renders
    `own_cause` for just 6 of the 19 trainable entries and `contradiction` for
    9 — the rest of that prose is never scanned at all, however many patterns
    the denylist grows. `test_set()` renders every trainable entry once per
    case, which is what makes the test above a real guard rather than a spot
    check. This fails if that coverage regresses.
    """
    from kubeagent_verdict.dataset import catalog
    trainable = {e.key for e in catalog.trainable()}
    by_case: dict[str, set[str]] = {}
    for ex in generate.test_set():
        entry = ex.meta.get("entry")
        if entry is not None:  # multi_misattribution_probe rows name several
            by_case.setdefault(ex.case, set()).add(entry)

    # `own_cause` is the only case that renders an entry's `own_cause` text;
    # `none_of_these` and `contradiction_probe` are the only ones that render
    # its `contradiction` text. Full coverage on these three is what carries
    # every entry's per-entry prose through the scan.
    for case in ("own_cause", "none_of_these", "contradiction_probe"):
        assert by_case.get(case) == trainable, (
            f"{case} renders {len(by_case.get(case, ()))} of {len(trainable)} "
            f"trainable entries; missing {sorted(trainable - by_case.get(case, set()))}"
        )
    assert set().union(*by_case.values()) == trainable


def test_test_set_slice_counts_are_pinned():
    """Every probe rate's denominator, pinned.

    `multi_misattribution_probe` had 19 rows and nothing said so, while its
    caller silently skipped a row on a name collision. A slice that quietly
    shrinks turns a "<=1 of 19" release bar into "<=1 of 18" with the suite
    green. The literals `253` and `19` appeared nowhere in `tests/` before
    this test existed.
    """
    counts = collections.Counter(ex.case for ex in generate.test_set())
    assert dict(counts) == {
        "attributed": 53,
        "contradiction_probe": 19,
        "empty_candidates": 19,
        "injection": 19,
        "misattribution_probe": 19,
        "multi_misattribution_probe": 19,
        "none_of_these": 19,
        "own_cause": 19,
        "positional_probe": 19,
        "shared_origin_probe": 10,
        "truncated": 19,
        "wrong_attribution": 19,
    }
    assert sum(counts.values()) == 253


def test_multi_probe_builder_rejects_colliding_workloads():
    """A name collision must raise, not silently drop the row.

    Two pairs with the same (ns, name) render one merged answer row instead
    of two, so the example silently stops testing what it was built to test.
    The check lives in the builder, so every caller gets it — including any
    future one that does not know to look.
    """
    entry = next(e for e in catalog.trainable() if e.losers)
    n = names.draw(random.Random(0))
    with pytest.raises(ValueError, match="distinct workloads"):
        cases.multi_misattribution_probe([(entry, n), (entry, n)], random.Random(0))
