"""The widened shared-origin probe: a diagnostic file, not a release decider.

The frozen exam asks the shared-origin question with ten twin pairs spread
over six origins — one or two pairs per origin. That is enough to score a
model, but not enough to diagnose one: "it always fails on CoreDNS" resting
on two pairs could be a coin landing badly twice. The wide probe mints five
twin pairs per held-out origin (30 pairs, 60 rows) so a per-origin verdict
rests on five observations. It is written to its own file and scored on its
own; the frozen 263-row exam does not move.
"""

from kubeagent_verdict.dataset import generate, propagation


def _pair_key(ex) -> str:
    return "|".join(sorted(ex.meta["expected"]))


def test_wide_probe_counts_and_balance():
    rows = generate.shared_origin_wide_probes()
    held_out = {p.key for p in propagation.all_scenarios()}
    assert len(rows) == len(held_out) * 5 * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == held_out
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 5, origin
        assert case_list.count("shared_origin_decoy_probe") == 5, origin


def test_wide_probe_uses_no_trainable_origin():
    # The leak guard: a trainable origin in the probe would score the model
    # on scenarios it memorised during training.
    trainable = {p.key for p in propagation.trainable_scenarios()}
    for ex in generate.shared_origin_wide_probes():
        assert ex.meta["origin"] not in trainable


def test_wide_rows_are_adjacent_twins_with_unique_pair_keys():
    rows = generate.shared_origin_wide_probes()
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


def test_wide_probe_fails_a_constant_answer_model():
    # The standing rule: an eval change that could not fail the model it
    # replaced is not a fix. A model that answers every row the same way —
    # always "shared" or always "separate" — must score zero pairs.
    from kubeagent_verdict.evals.score import paired_contrast

    rows = generate.shared_origin_wide_probes()
    for verdict in ("shared", "separate"):
        results = [{"pair_key": _pair_key(ex), "case": ex.case,
                    "shared_verdict": verdict} for ex in rows]
        board = paired_contrast(results)
        assert board["both_correct"]["rate"] == 0.0
        assert board["both_correct"]["n"] == len(rows) // 2
        assert board["unpaired"] == 0
        assert board["ambiguous"] == 0


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
