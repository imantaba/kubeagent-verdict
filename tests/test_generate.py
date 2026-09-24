import collections
import json
import random
import re

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, generate, names
from kubeagent_verdict.evals import score

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
    exs = generate.generate(seed=17, size=1)
    row = generate.to_row(exs[0])
    assert set(row) == {"messages", "meta"}
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]


def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 60, "none_of_these": 40, "own_cause": 130,
                      "multi": 130, "shared_origin": 150,
                      "shared_origin_decoy": 150, "truncated": 50,
                      "injection": 100, "empty_candidates": 50,
                      "wrong_attribution": 140}
    assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed
    # 997 is the awkward size: it is prime, so every share truncates.
    for size in (10, 100, 997, 1000, 4232):
        c = generate.counts_for(size)
        assert c["shared_origin"] == c["shared_origin_decoy"], size


def test_case_mix_present_in_generated_set():
    """Every case the mix DECLARES must actually be emitted.

    Derived from `CASE_MIX` rather than repeating it: the literal lives in
    `test_counts_for_follows_the_mix` above, and repeating it here made this
    test a second copy of that one. Read off the mix it catches the failure it
    is for -- a case given a percentage that `generate` has no branch to build.
    """
    exs = generate.generate(seed=17, size=200)
    assert {ex.case for ex in exs} == {case for case, _pct in generate.CASE_MIX}


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
        # Single-workload probe rows carry exactly one workload's decoy list.
        decoys = next(iter(ex.meta["decoy_by_workload"].values()))
        assert decoys
        assert ex.meta["expected_cause"] not in decoys
        for decoy in decoys:
            assert decoy in ex.user


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
                     "shared_origin_probe", "shared_origin_decoy_probe"]


def test_contradiction_probe_is_appended_last_one_row_per_entry():
    from kubeagent_verdict.dataset import catalog, generate
    probes = generate.probe_sets()
    trainable = [e for e in catalog.trainable() if e.losers and e.contradiction]
    tail = [ex for ex in probes if ex.case == "contradiction_probe"]
    assert len(tail) == len(trainable)
    # Appended, never interleaved: every earlier probe row keeps its position, so
    # a scoreboard banked against the previous test file still lines up. The run
    # is no longer the LAST rows in the file — the two shared-origin slices were
    # appended after it — so what is asserted is that the run is contiguous and
    # that nothing but those blocks follows it. A slice appended after this one
    # is allowed by construction; a row interleaved INTO this one is not.
    cases = [ex.case for ex in probes]
    first = cases.index("contradiction_probe")
    assert cases[first:first + len(tail)] == ["contradiction_probe"] * len(tail)
    assert set(cases[first + len(tail):]) == {"shared_origin_probe",
                                              "shared_origin_decoy_probe"}
    for ex in tail:
        assert ex.meta["expected_cause"] == c.NONE_OF_THESE
        decoys = next(iter(ex.meta["decoy_by_workload"].values()))
        for decoy in decoys:
            assert decoy in ex.user


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
    # `contradiction_probe` is the only one that renders its `contradiction`
    # text. Full coverage on these two is what carries every entry's
    # per-entry prose through the scan.
    for case in ("own_cause", "contradiction_probe"):
        assert by_case.get(case) == trainable, (
            f"{case} renders {len(by_case.get(case, ()))} of {len(trainable)} "
            f"trainable entries; missing {sorted(trainable - by_case.get(case, set()))}"
        )
    assert set().union(*by_case.values()) == trainable

    # Until 2026-09-24 `none_of_these` rendered the `contradiction` text too,
    # for every entry. The job-2 generator fix builds it from thin evidence
    # instead: four entries, one row per undecided shape, and a fixed
    # rationale that names no entry's prose.
    thin = collections.Counter(
        (ex.meta["entry"], "refuted" if "fresh read: refuted" in ex.user else "ruled_out")
        for ex in generate.test_set() if ex.case == "none_of_these")
    assert thin == {(key, shape): 1 for key in cases.THIN_ENTRIES
                    for shape in ("refuted", "ruled_out")}


def test_test_set_slice_counts_are_pinned():
    """Every probe rate's denominator, pinned.

    `multi_misattribution_probe` had 19 rows and nothing said so, while its
    caller silently skipped a row on a name collision. A slice that quietly
    shrinks turns a "<=1 of 19" release bar into "<=1 of 18" with the suite
    green. The literals `263` and `19` appeared nowhere in `tests/` before
    this test existed.

    The total moves only when a slice is deliberately APPENDED, and every
    append leaves the earlier rows at their original indices — which is what
    lets a scoreboard banked against the shorter file still line up row for
    row over the slices it shares.

    2026-09-24 broke that rule once, on purpose. The job-2 generator fix
    rebuilt `none_of_these` from thin evidence on four entries, so the slice
    fell from 19 rows to 8. Those rows sit inside the held-out block, one
    entry at a time, so rows moved from the first changed entry onward and
    the probe slices after the block moved up 11 places. A scoreboard
    banked before that date does not line up row for row with this exam;
    the frozen-slice and eval-set hashes moved with it.
    """
    counts = collections.Counter(ex.case for ex in generate.test_set())
    assert dict(counts) == {
        "attributed": 53,
        "contradiction_probe": 19,
        "empty_candidates": 19,
        "injection": 19,
        "misattribution_probe": 19,
        "multi_misattribution_probe": 19,
        "none_of_these": 8,
        "own_cause": 19,
        "positional_probe": 19,
        "shared_origin_decoy_probe": 10,
        "shared_origin_probe": 10,
        "truncated": 19,
        "wrong_attribution": 19,
    }
    assert sum(counts.values()) == 252


def test_the_job2_keyword_exposure_is_pinned_per_case():
    """How much of job 2 the corpus gives away for free, measured.

    job 2 grades a workload by keyword containment: all of its
    `own_cause_keywords` must appear in the reply's cause. Where every one of
    those keywords is already printed in the prompt, a cause assembled from
    words on screen grades as correct, so the slice cannot separate "read the
    evidence and concluded" from "restated the evidence".

    Pinned per case as well as in total: a corpus edit that raised the
    exposure of one slice while lowering another's would slide past a
    total-only assertion. `76 of 134` is what the implementation measures
    today. It is a measurement, not a target -- a change here is a real
    change in how much the slice gives away, and the number is updated
    deliberately with the reason, never tuned back to a stale value.

    The population moved for the v1.24.0 rescope. It used to be the retired
    `cause_acc` slice -- two case names, `own_cause` and `empty_candidates`,
    counted once per row -- which read 19 of 38. Design spec line 547 asks for all of
    job 2 instead, which is one entry per undecided workload that carries
    keywords, and adds three more cases: `wrong_attribution`,
    `misattribution_probe` and `multi_misattribution_probe`.

    Re-pinned on 2026-09-23 for the exam-grader fix
    (2026-09-23-exam-grader-fix-design.md). Before this fix, every
    `shared_origin_probe` and `shared_origin_decoy_probe` workload carried
    `own_cause_keywords=[]`, so `_keyword_exposure` never counted either
    case as measured. The 22 curated pairs give both cases a non-empty
    list on every undecided workload, adding two new case entries: 4 of 4
    `shared_origin_probe` workloads and 16 of 16 `shared_origin_decoy_probe`
    workloads, all fully derivable -- the victim's own local cause or the
    scenario's shared cause is always printed on that workload's own
    candidate menu. 114 + 20 = 134 graded, 56 + 20 = 76 derivable.
    """
    by_case = collections.Counter()
    graded = collections.Counter()
    for ex in generate.test_set():
        row = generate.to_row(ex)
        prompt = row["messages"][1]["content"]
        derivable, measured = score._keyword_exposure(row["meta"], prompt)
        if not measured:
            continue
        graded[ex.case] += measured
        by_case[ex.case] += derivable

    assert dict(graded) == {"own_cause": 19, "empty_candidates": 19,
                            "wrong_attribution": 19, "misattribution_probe": 19,
                            "multi_misattribution_probe": 38,
                            "shared_origin_probe": 4,
                            "shared_origin_decoy_probe": 16}
    assert dict(by_case) == {"own_cause": 9, "empty_candidates": 10,
                             "wrong_attribution": 9, "misattribution_probe": 9,
                             "multi_misattribution_probe": 19,
                             "shared_origin_probe": 4,
                             "shared_origin_decoy_probe": 16}
    assert sum(graded.values()) == 134
    assert sum(by_case.values()) == 76


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


def test_generate_wraps_nothing_in_try_except():
    """R45: generate() lets a ValueError from any case builder propagate uncaught —
    no call site inside it may swallow the exception."""
    import inspect

    from kubeagent_verdict.dataset import generate

    assert "except" not in inspect.getsource(generate.generate)


def test_generate_stops_at_first_error_and_writes_nothing(tmp_path, monkeypatch):
    """A ValueError raised while building any row propagates out of generate(), and
    write_jsonl is never reached — R45: generate stops at the first error, writes
    nothing, so a half-rendered exam can never land."""
    from kubeagent_verdict.dataset import cases, generate

    def boom(*args, **kwargs):
        raise ValueError("worker-1: object node:'worker-1' outside the closed table")

    monkeypatch.setattr(cases, "attributed", boom)
    out = tmp_path / "would-be-written.jsonl"

    with pytest.raises(ValueError, match="outside the closed table"):
        train, val = generate.generate(seed=17, size=50)
        generate.write_jsonl(out, train + val)

    assert not out.exists()


def test_generate_appends_one_training_only_separate_multi_row():
    """The training-only separate prompt is one extra multi() call, appended once, not
    part of the CASE_MIX-counted 11 multi rows -- pairs worker-containerd-stop with
    itself at two different (ns, node) draws so the two workloads decide different
    causes and rules.label comes out 'separate'."""
    from kubeagent_verdict.dataset import generate

    rows = generate.generate(seed=5, size=200)
    doubled = [ex for ex in rows if ex.case == "multi"
              and ex.group.count("worker-containerd-stop:") == 2]
    assert len(doubled) == 1
    ex = doubled[0]
    assert ex.meta["label"] == "separate"
    workloads = list(ex.meta["workloads"].values())
    assert len(workloads) == 2
    assert workloads[0]["decided_cause"] != workloads[1]["decided_cause"]


def test_job_population_counts_match_the_pinned_exam_shape():
    """Every workload answer is job 1 (decided) or job 2 (not decided); every
    prompt with 2+ workloads is job 3, labelled shared/separate/none by
    rules.label. These counts are a direct read of the pinned 13-case-count
    exam (job 3's count and label split) plus one measurement over the
    workload-level job field (job 1 and job 2), taken once and pinned here so
    a case-count or job-derivation regression is caught by a moving number
    rather than silently accepted.
    """
    rows = generate.test_set()
    job1 = job2 = 0
    job3_labels = {"shared": 0, "separate": 0, "none": 0}
    job3_prompts = 0
    for e in rows:
        workloads = e.meta.get("workloads", {})
        for wl in workloads.values():
            assert wl["job"] in (1, 2)
            if wl["job"] == 1:
                job1 += 1
            else:
                job2 += 1
        if len(workloads) >= 2:
            job3_prompts += 1
            job3_labels[e.meta["label"]] += 1

    # job1 and job2 are measured, not derived -- R40 states them as "about 70"
    # and "about 210"; Step 51's actual measurement over the v1.24.0 exam
    # printed 157 and 153, so those are the pinned literals, not R40's
    # rounded figures. job2 fell from 153 to 142 on 2026-09-24: the job-2
    # generator fix cut the `none_of_these` slice from 19 rows to 8.
    assert job1 == 157
    assert job2 == 142
    assert job3_prompts == 39
    assert job3_labels == {"shared": 5, "separate": 0, "none": 34}


def test_every_declared_down_node_appears_ruled_out_on_every_other_workload():
    """A multi-workload prompt declares a down node once per prompt, but
    placement is per workload: a workload whose pod is not on a given down
    node must still see that node named in its own candidate menu, ruled out
    there. This is what stops a model from treating an absent candidate as
    evidence the node was never considered. Scoped to case == "multi": a
    shared_origin* row's shared node is deliberately "outranked" on every
    victim's own menu, never "ruled out" -- a different, intentional shape
    this fact does not describe.

    Pulled from the training corpus (seed=17, size=8000, matching
    test_evidence_overlap.py's frozen SEED/SIZE), not test_set(): "multi" is
    a CASE_MIX-only case and never appears in the held-out exam
    (test_set()'s multi-workload rows are all multi_misattribution_probe,
    shared_origin_probe or shared_origin_decoy_probe -- none is a plain
    "multi" row), and Example.case is a top-level field, not a meta key.
    Reads the rendered prompt straight off ex.user, since to_row()'s dict
    carries no "prompt" key (only "messages" and "meta").

    The section boundaries are cut inside the candidates block alone, not
    the whole prompt: a workload's "ns/name" key also opens its inventory
    line, which comes first in every rendered prompt, so slicing on each
    key's first whole-prompt occurrence lands the cut inside the inventory
    block (one line long) rather than the candidates block this fact is
    about. Restricting the search to the text between the candidates
    section's own BEGIN/END markers makes each key's first occurrence there
    the candidates heading itself, which is the cut this fact needs.

    The declared-down-node owner is read off the rendered candidates, not
    off meta["workloads"][...]["expected_cause"]: for a multi() row that
    field is the workload's OWN catalog-entry cause (a PVC, a Secret, a
    NetworkPolicy, ...), which is independent of the shared decoy nodes
    _multi_objects layers onto every workload's menu -- a workload can win
    on a decoy node (decided_cause) while its expected_cause names something
    that never renders as a candidate at all. The fact this test pins is
    about the rendered decoy nodes themselves, so each owner's node is found
    by scanning that owner's own section for an "attributed" candidate whose
    cause starts with "node ".
    """
    rows = generate.generate(seed=17, size=8000)
    multi_workload_rows = [e for e in rows
                           if e.case == "multi"
                           and len(e.meta.get("workloads", {})) >= 2]
    assert multi_workload_rows, "the training corpus must carry at least one multi-workload multi() row"
    attributed_node = re.compile(r"^    considered (node .+): attributed — ", re.MULTILINE)
    for e in multi_workload_rows:
        prompt = e.user
        cand_start = prompt.index("== BEGIN candidates ==")
        cand_end = prompt.index("== END candidates ==")
        candidates = prompt[cand_start:cand_end]
        workloads = e.meta["workloads"]
        keys = sorted(workloads, key=lambda k: candidates.index(k))
        bounds = [candidates.index(k) for k in keys] + [len(candidates)]
        sections = {k: candidates[bounds[i]:bounds[i + 1]] for i, k in enumerate(keys)}
        down_nodes = {wl: m.group(1) for wl, text in sections.items()
                     for m in [attributed_node.search(text)] if m}
        for owner, node in down_nodes.items():
            for other in workloads:
                if other == owner:
                    continue
                # The node this OTHER workload does not own must still show up,
                # ruled out, inside its OWN section of the prompt -- not just
                # anywhere in the prompt, since the owner's own section also
                # names the node (there, as the attributed cause). render_candidates
                # renders a ruled-out candidate as
                # "    considered <cause>: ruled out — <reason>", so the literal
                # marker to check for is "<node>: ruled out".
                assert f"{node}: ruled out" in sections[other], (
                    f"{node} (declared for {owner}) missing a ruled-out line in "
                    f"{other}'s own section")


def test_registry_fresh_read_literal_is_a_substring_of_the_events_read():
    """Every workload with a registry candidate renders two things about the
    same object: a fresh-read line or a decided-by-rules line, in the
    prompt's `candidates` section, and an `events for <ns>/<pod>` read, in
    its `evidence` section (what `classifyPullEvents` actually scans).
    `rules._check_registry` always writes the candidate line's literal
    verbatim after the fixed phrase `a pull event shows a ... error:`, and
    `render.registry_events_read` writes the same `obj.fresh.literal` into
    the events read's `Failed:` line -- so whatever literal a candidate line
    names has to appear in the evidence section too (case-insensitively), or
    a model reading only the events text would reach a different answer than
    the candidate menu claims. The two sections are found by the real
    `== BEGIN <name> ==` / `== END <name> ==` markers `contract.section()`
    writes; both sections render every workload's own text concatenated
    together, so the check compares the two sections as a whole rather than
    scoping to one workload -- no per-workload ns/pod lookup is needed.
    """
    rows = generate.test_set()
    for e in rows:
        prompt = e.user.lower()
        cand_start = prompt.index("== begin candidates ==")
        cand_end = prompt.index("== end candidates ==")
        ev_start = prompt.index("== begin evidence ==")
        ev_end = prompt.index("== end evidence ==")
        candidates_text = prompt[cand_start:cand_end]
        evidence_text = prompt[ev_start:ev_end]
        for line in candidates_text.splitlines():
            if "pull event shows" not in line or " error: " not in line:
                continue
            literal = line.split(" error: ", 1)[1].split(";", 1)[0].strip()
            assert literal in evidence_text, (
                f"{literal!r} named in the candidates section but missing "
                "from the evidence section's events read")


def test_no_pull_event_line_has_no_events_for_in_it():
    """The `no_event` ending's rendered events read must say `no events for`,
    never a literal a `Failed:` line would carry -- the DECISION's second
    invariant, checked directly rather than as a byproduct of the substring
    check above.
    """
    rows = generate.test_set()
    saw_no_event = False
    for e in rows:
        prompt = e.user
        if "no events for" in prompt:
            saw_no_event = True
            for line in prompt.splitlines():
                if "no events for" in line:
                    assert "Failed:" not in line
    assert saw_no_event, "the exam must carry at least one no_event registry ending"


# ------------------------------------------- the decided line in the prompt

_CANDIDATE_HEADING = re.compile(r"^- (\S+) \(")
_DECIDED_LINE = re.compile(r"^    decided by rules: (.+) — (\S+)$")


def _decided_lines(prompt: str) -> dict[str, tuple[str, str]]:
    """Read every `decided by rules:` line back off a rendered prompt, keyed
    by the `ns/name` its candidates heading names.

    The candidates block is sliced out first. A workload's `ns/name` also
    opens its inventory line, which comes earlier in the prompt, so a scan
    over the whole prompt would key the wrong section.
    """
    start = prompt.index("== BEGIN candidates ==")
    end = prompt.index("== END candidates ==")
    out: dict[str, tuple[str, str]] = {}
    key = None
    for line in prompt[start:end].split("\n"):
        heading = _CANDIDATE_HEADING.match(line)
        if heading:
            key = heading.group(1)
            continue
        decided = _DECIDED_LINE.match(line)
        if decided is not None and key is not None:
            out[key] = (decided.group(1), decided.group(2))
    return out


def test_every_job1_workload_prints_its_decided_line_and_no_job2_one_does():
    """Job 1 grades a byte-for-byte echo of the rule engine's cause, so the
    cause has to be in the prompt.

    kubeagent v1.24.0 prints it under the workload's candidate menu as
    `    decided by rules: <cause> — <outcome>`. The exam renders the same
    line from the same `rules.Result` its meta records, so the two cannot
    drift. Without it job 1 would measure recall of a string the model was
    never shown.
    """
    rows = generate.test_set()
    decided_total = 0
    for e in rows:
        lines = _decided_lines(e.user)
        for key, wm in e.meta["workloads"].items():
            if wm["job"] == 1:
                assert key in lines, (e.meta["case"], key)
                assert lines[key] == (wm["decided_cause"], wm["decided_outcome"])
                decided_total += 1
            else:
                assert key not in lines, (e.meta["case"], key)
    assert decided_total == 157


def test_every_decoy_probe_row_names_its_decoy_cause():
    """The length-gap decider reads `decoy_cause` off the row meta.

    Without the key the decider has no population at all: both of its
    slices come out empty and it can only print `not measured`. The four
    probe builders that carry one row-level decoy name it again, and the
    multi-workload probe names one decoy per workload, the way the base
    revision did.
    """
    rows = generate.test_set()
    named = collections.Counter(e.meta["case"] for e in rows if e.meta.get("decoy_cause"))
    assert dict(named) == {"wrong_attribution": 19, "positional_probe": 19,
                           "misattribution_probe": 19, "contradiction_probe": 19}
    for e in rows:
        if not e.meta.get("decoy_cause"):
            continue
        key = next(iter(e.meta["workloads"]))
        assert e.meta["decoy_cause"] == e.meta["decoy_by_workload"][key][0]
    multi = [e for e in rows if e.meta["case"] == "multi_misattribution_probe"]
    assert len(multi) == 19
    for e in multi:
        assert e.meta["decoy_causes"] == [v[0] for v in e.meta["decoy_by_workload"].values()]


def test_the_length_gap_decider_has_rows_in_both_slices():
    """57 of the 263 exam rows carry both a decoy cause and an expected cause
    that is not `none_of_these`, which is what the length gap is measured
    over. Both slices have to be non-empty: a decider with one empty slice
    reads `not measured` and tells a release reviewer nothing.
    """
    rows = [generate.to_row(e) for e in generate.test_set()]
    results = score.evaluate(rows, lambda messages: "")
    measured = [r["length_helps"] for r in results if r["length_helps"] is not None]
    assert len(measured) == 57
    assert sum(1 for m in measured if m) > 0
    assert sum(1 for m in measured if not m) > 0


def test_one_prompt_has_one_answer():
    """No two rows share a user prompt but differ in what they expect.

    Before the 2026-09-24 generator fix, `wrong_attribution` and
    `none_of_these` could print the same prompt and expect opposite answers:
    the entry's own cause at one confidence, or `none_of_these` at another.
    Gradient descent cannot fit both, and the model learned a coin flip for
    exactly the rows the exam's job 2 grades hardest. The prompt now depends
    only on (entry, names, shape, evidence), never on the case, so this
    holds by construction; this test is what keeps it holding.

    Checked over the full training build and the exam together, because a
    collision across the two is the same contradiction. Rationales and
    summaries may differ -- they are not graded.
    """
    rows = generate.generate(seed=17, size=8000) + generate.test_set()
    answers: dict[str, set] = collections.defaultdict(set)
    for ex in rows:
        gold = json.loads(ex.assistant)["verdicts"]
        answers[ex.user].add(tuple(sorted(
            (v["workload"], v["cause"], v["confidence"]) for v in gold)))
    clashes = {prompt[:200]: sorted(a) for prompt, a in answers.items() if len(a) > 1}
    assert not clashes, clashes


def test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape():
    """A thin row and a clear row of the same entry and shape differ in one
    read. If thin rows outnumber clear ones, "none of these" becomes the
    likelier answer for that entry whatever the reads say. Counted in
    train, the way `kv-dataset` builds it: split, then drop held-out groups.
    """
    train, _val = generate.split(generate.generate(seed=17, size=8000), seed=17)
    train = generate.drop_held_out(train, generate.test_set())
    clear_case = {"refuted": "wrong_attribution", "ruled_out": "own_cause"}
    n = collections.Counter(
        (ex.meta["entry"], "refuted" if "fresh read: refuted" in ex.user else "ruled_out",
         ex.case)
        for ex in train if ex.case in ("none_of_these", *clear_case.values()))
    for key in cases.THIN_ENTRIES:
        for shape, clear in clear_case.items():
            assert n[(key, shape, clear)] > n[(key, shape, "none_of_these")] > 0, (key, shape)
