"""The cousin probe: one fresh twin pair per trainable scenario.

The wide probe (tests/test_probe_wide.py) asks the six held-out origins
five times each. This probe asks the 48 trained scenarios once each: 48
pairs, 96 rows, every pair at full width, so every decoy half carries three
or four verdicts. It is in-distribution on purpose. A model that reads the
origin on the scenarios it studied and still fails the exam has a coverage
problem; one that fails here has a recipe problem. It is written to its
own file, scored on its own, and decides nothing. The frozen exam does not
move.
"""

from kubeagent_verdict.dataset import generate, propagation


def _pair_key(ex) -> str:
    return "|".join(sorted(ex.meta["expected"]))


def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {p.key for p in propagation.trainable_scenarios()}
    assert len(trainable) == 48
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
    # in-distribution check, so a held-out origin here would score the exam
    # twice and tell us nothing new.
    held_out = {p.key for p in propagation.all_scenarios()}
    for ex in generate.shared_origin_cousin_probes():
        assert ex.meta["origin"] not in held_out


def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    rows = generate.shared_origin_cousin_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        # Probe half: every victim shares ONE cause. Decoy half: none of the
        # victims' correct causes is that shared cause.
        shared = set(probe.meta["expected"].values())
        assert len(shared) == 1
        assert shared.isdisjoint(set(decoy.meta["expected"].values()))


def test_every_cousin_decoy_carries_three_or_more_verdicts():
    # Full width on purpose: three-verdict decoy halves are the shape the
    # 0907 model broke its JSON on, and every trainable scenario now has at
    # least three victims, so every cousin decoy can carry three.
    for ex in generate.shared_origin_cousin_probes():
        if ex.case == "shared_origin_decoy_probe":
            assert len(ex.meta["expected"]) >= 3, ex.meta["origin"]



def test_cousin_probe_is_deterministic():
    a = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    b = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    assert a == b


def test_cousin_probe_is_not_in_the_exam():
    # Its own file, never the frozen exam: no cousin row shares an origin
    # with any exam row, and the exam's row count does not move.
    exam = generate.test_set()
    assert len(exam) == 263
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
    assert len(lines) == 96
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
