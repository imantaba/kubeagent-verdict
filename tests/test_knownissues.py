from pathlib import Path

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import knownissues

DATA = Path(__file__).resolve().parent.parent / "data" / "knownissues" / "knownissues.json"


def test_snapshot_covers_exactly_the_16_kinds():
    ki = knownissues.load_knownissues(DATA)
    assert set(ki) == vocab.ISSUE_KINDS


def test_kubeagent_style_invariants_hold():
    ki = knownissues.load_knownissues(DATA)
    for entry in ki.values():
        assert entry.summary == entry.summary.strip()
        assert not entry.summary.endswith(".")
        assert entry.summary[0].islower() or not entry.summary[0].isalpha()
        assert entry.detail and entry.causes and entry.checks


def test_loader_is_strict(tmp_path):
    p = tmp_path / "ki.json"
    p.write_text('[{"kind": "CrashLoopBackOff"}]', encoding="utf-8")
    with pytest.raises(ValueError):
        knownissues.load_knownissues(p)
