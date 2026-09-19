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
    """A `shared`-labeled probe half is decided end to end: every victim's
    cause comes from the rules, disjoint from its decoy twin's causes (spec
    section 3). On the two scope-pinned origins (node-not-ready,
    registry-unreachable) that is one string, because every victim binds the
    same node or registry name. storage-provisioner-down's origin binds a
    PER-VICTIM PVC name, so its `shared` group can hold more than one PVC
    cause (`rules.py`'s group-key storage-class fallback) -- still disjoint
    from the decoy twin, just not one string.

    A `none`-labeled probe half makes neither promise. A victim the rules
    decide on its own evidence gets the same cause regardless of `healthy` --
    the per-victim decide branch never reads it -- so it can appear on BOTH
    halves of the pair; only the undecided victims still swap between the
    decoy and shared causes.
    """
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
        shared = set(probe.meta["expected"].values())
        if probe.meta["label"] == "shared":
            assert all(w["decided"] for w in probe.meta["workloads"].values())
            if probe.meta["origin"] != "storage-provisioner-down":
                assert len(shared) == 1
            assert shared.isdisjoint(set(decoy.meta["expected"].values()))


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
