"""The cousin probe: one fresh twin pair per trainable story.

The wide probe (tests/test_probe_wide.py) asks the six held-out stories five
times each. This probe asks each trained story once: 41 stories, so 41 pairs
and 82 rows. (It was 54 pairs and 108 rows on the old made-up menu.) Every
pair is at full width.

A pair is one story told in two worlds. In the broken world the origin is
broken. In the healthy world it is not. Both halves carry the same
`Example.group`, and their printed lines differ. The probe is in-distribution
on purpose. A model that reads the origin on the stories it studied and still
fails the exam has a coverage problem. One that fails here has a recipe
problem. It is written to its own file, scored on its own, and decides
nothing. The frozen exam does not move.
"""

from kubeagent_verdict.dataset import generate, stories


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group.

    A group is `propagation:<story>:<ns>/<name>` for each victim, joined by
    `+`. It names victims only, and it is the same in both worlds. The broken
    world can add an origin row to `expected`. The group never lists it.
    """
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {st.key for st in stories.trainable()}
    # 2026-10-04 (Spec 4b-1): the probe draws from stories.trainable(), 41 stories
    # (35 plain, 6 ruled), one pair each; was 54 stories and 108 rows.
    assert len(trainable) == 41
    assert len(rows) == len(trainable) * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == trainable
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 1, origin
        assert case_list.count("shared_origin_decoy_probe") == 1, origin


def test_cousin_probe_uses_only_trainable_origins():
    # The mirror of the wide probe's leak guard. This probe is the
    # in-distribution check, so an exam story or a dropped story here would
    # score the exam twice and tell us nothing new.
    kept_out = set(stories.EXAM_KEYS) | set(stories.DROPPED)
    for ex in generate.shared_origin_cousin_probes():
        assert ex.meta["origin"] not in kept_out, ex.meta["origin"]


def test_cousin_rows_are_adjacent_twins_with_unique_groups():
    """Twins are matched on `Example.group`, not on the workload set.

    The broken world can add an origin row that the healthy world lacks, so
    the two halves may flag different workloads. They never name different
    victims. Two things are checked per pair. The halves print different lines
    (otherwise the pair asks nothing). And on a `shared` probe at least one
    workload both halves flag gets a different cause, so the answer really
    flips with the read.

    A ruled (R) story is checked harder. Its probe is `shared`, every victim
    is decided by the rules (job 1), and the victims' causes appear nowhere
    in the decoy's answer. A plain (P) story is `shared` only when two or
    more victims are linked, so a P pair may be `none` on both halves. Only
    the decoy half is always `none`.
    """
    rows = generate.shared_origin_cousin_probes()
    by_key = stories.by_key()
    seen: set[str] = set()
    saw_shared = 0
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        origin = probe.meta["origin"]
        assert origin == decoy.meta["origin"]
        assert probe.group == decoy.group, origin
        # A repeated group would merge two pairs in the paired scoring.
        assert probe.group not in seen, origin
        seen.add(probe.group)
        victims = _victim_keys(probe)
        assert victims <= set(probe.meta["expected"]), origin
        assert victims <= set(decoy.meta["expected"]), origin
        # The reads must differ, or the pair asks nothing.
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), origin
        assert decoy.meta["label"] == "none", origin
        if by_key[origin].cls == "R":
            assert probe.meta["label"] == "shared", origin
            for w in victims:
                assert probe.meta["workloads"][w]["job"] == 1, (origin, w)
            probe_causes = {probe.meta["expected"][w] for w in victims}
            assert probe_causes.isdisjoint(set(decoy.meta["expected"].values())), origin
        if probe.meta["label"] == "shared":
            saw_shared += 1
            common = set(probe.meta["expected"]) & set(decoy.meta["expected"])
            assert any(probe.meta["expected"][w] != decoy.meta["expected"][w]
                       for w in common), origin
    # The six ruled stories are always shared. If fewer than six pairs are,
    # the ruled stories have fallen out of `stories.trainable()`.
    assert saw_shared >= len(stories.RULED_ORDER), saw_shared


def test_every_cousin_decoy_carries_a_verdict_for_every_victim():
    # Full width on purpose. A ruled story has 3 or more victims, but a plain
    # story can have only 2, so the old claim "three or more verdicts
    # everywhere" is gone. What still holds is that every drawn victim gets its
    # own verdict, and that some decoys are wide enough to carry three (the
    # shape the 0907 model broke its JSON on).
    by_key = stories.by_key()
    wide = 0
    for ex in generate.shared_origin_cousin_probes():
        if ex.case != "shared_origin_decoy_probe":
            continue
        story = by_key[ex.meta["origin"]]
        assert len(_victim_keys(ex)) == len(story.victims), story.key
        assert len(ex.meta["expected"]) >= len(story.victims), story.key
        if len(ex.meta["expected"]) >= 3:
            wide += 1
    assert wide > 0


def test_cousin_probe_is_deterministic():
    a = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    b = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    assert a == b


def test_cousin_probe_is_not_in_the_exam():
    # Its own file, never the frozen exam: no cousin row shares an origin
    # with any exam row, and the exam's row count does not move.
    # 263 to 252 on 2026-09-24: the job-2 generator fix cut the exam's
    # `none_of_these` slice from 19 rows to 8. The cousin probe added none.
    # 2026-09-26 (faithful prompts): `truncated`, `injection` and
    # `positional_probe` are built only for the 17 entries the rules decide,
    # not all 19 (-6); the new `pvc-unbound-unschedulable` entry adds one
    # row to each of five other cases (+5); and 31 corpus rows moved from
    # `attributed` to `own_cause` (no count change). The cousin probe still
    # added none. 252 -> 251.
    # 2026-09-26 (faithful prompts): `contradiction_probe` is built only for
    # the 17 entries the rules decide, not the 19 with a scripted
    # contradiction: three entries' rows go and the new entry's row comes.
    # The cousin probe still added none. 251 -> 249.
    exam = generate.test_set()
    assert len(exam) == 249
    exam_origins = {ex.meta.get("origin") for ex in exam
                    if ex.case in ("shared_origin_probe",
                                   "shared_origin_decoy_probe")}
    cousin_origins = {ex.meta["origin"]
                      for ex in generate.shared_origin_cousin_probes()}
    assert exam_origins.isdisjoint(cousin_origins)


def test_cli_probe_cousins_writes_only_the_standalone_file(tmp_path, monkeypatch):
    import json

    from kubeagent_verdict.dataset import cli

    out = tmp_path / "probe-cousins.jsonl"
    monkeypatch.setattr("sys.argv", ["kv-dataset", "--probe-cousins", str(out)])
    cli.main()
    lines = out.read_text(encoding="utf-8").splitlines()
    # 2026-10-04 (Spec 4b-1): the cousin probe draws from stories.trainable(),
    # 41 stories, one pair each; was 108.
    assert len(lines) == 82
    first = json.loads(lines[0])
    assert first["meta"]["case"] == "shared_origin_probe"
    # Standalone means standalone: no train/val/test/manifest beside it.
    assert [p.name for p in tmp_path.iterdir()] == ["probe-cousins.jsonl"]


def test_cli_rejects_both_probe_flags_together(tmp_path, monkeypatch):
    import pytest

    from kubeagent_verdict.dataset import cli

    wide = tmp_path / "probe-wide.jsonl"
    cousins = tmp_path / "probe-cousins.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        ["kv-dataset", "--probe-wide", str(wide), "--probe-cousins", str(cousins)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []
