"""The widened shared-origin probe: a diagnostic file, not a release decider.

The frozen exam asks the shared-origin question with ten twin pairs spread over
six stories. That is enough to score a model, but not enough to diagnose one:
"it always fails on CoreDNS" resting on two pairs could be a coin landing badly
twice. The wide probe mints five twin pairs per exam story (30 pairs, 60 rows)
so a per-story verdict rests on five observations. Odd-numbered draws of a
story with three or more victims are narrowed to two, so each story is seen at
more than one width. It is written to its own file and scored on its own. The
frozen 249-row exam does not move.

Twins are matched on `Example.group`. The group names the victims, and it is
the same in both worlds. The broken world can add an origin row that the
healthy world lacks, so the two halves may flag different workloads.
"""

from kubeagent_verdict.dataset import generate, stories


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def test_wide_probe_counts_and_balance():
    rows = generate.shared_origin_wide_probes()
    exam_keys = {st.key for st in stories.exam()}
    assert len(exam_keys) == 6
    assert len(rows) == len(exam_keys) * 5 * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == exam_keys
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 5, origin
        assert case_list.count("shared_origin_decoy_probe") == 5, origin


def test_wide_probe_uses_no_trainable_origin():
    # The leak guard: a trainable story in the probe would score the model on
    # stories it memorised during training. A dropped story would be a story
    # no part of the pipeline builds any more.
    barred = {st.key for st in stories.trainable()} | set(stories.DROPPED)
    for ex in generate.shared_origin_wide_probes():
        assert ex.meta["origin"] not in barred, ex.meta["origin"]


def test_wide_rows_are_adjacent_twins_with_unique_groups():
    """Twins are matched on `Example.group`, and the halves must print
    different lines (Ruling 35).

    A ruled (R) exam story is `shared` on its probe half at every width: the
    rules confirm one cause on its victims. Every victim is job 1, and the
    victims' causes appear nowhere in the decoy's answer. There are three R
    exam stories (node-not-ready, storage-provisioner-down,
    registry-unreachable) and five probes of each, so at least fifteen probes
    are `shared`. A plain (P) story is `shared` only when two or more victims
    are linked, so a P pair may be `none` on both halves. The decoy half is
    always `none`.
    """
    rows = generate.shared_origin_wide_probes()
    by_key = stories.by_key()
    seen: set[str] = set()
    shared_n = 0
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
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), origin
        assert decoy.meta["label"] == "none", origin
        if by_key[origin].cls == "R":
            assert probe.meta["label"] == "shared", origin
            for w in victims:
                assert probe.meta["workloads"][w]["job"] == 1, (origin, w)
            probe_causes = {probe.meta["expected"][w] for w in victims}
            assert probe_causes.isdisjoint(set(decoy.meta["expected"].values())), origin
        if probe.meta["label"] == "shared":
            shared_n += 1
            common = set(probe.meta["expected"]) & set(decoy.meta["expected"])
            assert any(probe.meta["expected"][w] != decoy.meta["expected"][w]
                       for w in common), origin
    r_exam = [st for st in stories.exam() if st.cls == "R"]
    assert len(r_exam) == 3
    assert shared_n >= 5 * len(r_exam), shared_n


def test_wide_probe_widths_follow_the_story():
    """Draw i of a story is narrowed to two victims when i is odd and the story
    has three or more. Every other draw is full width."""
    rows = generate.shared_origin_wide_probes()
    probes = rows[0::2]
    order = [st for st in stories.exam() for _ in range(5)]
    assert [ex.meta["origin"] for ex in probes] == [st.key for st in order]
    for flat, (st, ex) in enumerate(zip(order, probes)):
        i = flat % 5
        want = 2 if i % 2 == 1 and len(st.victims) >= 3 else len(st.victims)
        assert len(_victim_keys(ex)) == want, (st.key, i)


def test_wide_probe_is_deterministic():
    a = [generate.to_row(ex) for ex in generate.shared_origin_wide_probes()]
    b = [generate.to_row(ex) for ex in generate.shared_origin_wide_probes()]
    assert a == b


def test_cli_probe_wide_writes_only_the_standalone_file(tmp_path, monkeypatch):
    import json

    from kubeagent_verdict.dataset import cli

    out = tmp_path / "probe-wide.jsonl"
    monkeypatch.setattr("sys.argv", ["kv-dataset", "--probe-wide", str(out)])
    cli.main()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 60
    first = json.loads(lines[0])
    assert first["meta"]["case"] == "shared_origin_probe"
    # Standalone means standalone: no train/val/test/manifest beside it.
    assert [p.name for p in tmp_path.iterdir()] == ["probe-wide.jsonl"]
