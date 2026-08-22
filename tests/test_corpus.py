import json
from pathlib import Path

from kubeagent_verdict.dataset import corpus

DATA = Path(__file__).resolve().parent.parent / "data" / "corpus"


def test_loads_committed_snapshots():
    paths = sorted(DATA.glob("chaos-corpus-*.jsonl"))
    assert len(paths) == 4
    load = corpus.load_corpus(paths)
    assert load.withheld == 0, load.reasons
    assert len(load.rows) == 4 * 23
    faults = {r.fault for r in load.rows}
    assert "crashloop-pod" in faults
    assert all(isinstance(r.rc, int) for r in load.rows)


def test_withholds_unknown_slug_and_malformed(tmp_path):
    p = tmp_path / "c.jsonl"
    good = {"scenario": "19. crashloop", "fault": "crashloop-pod", "k8s": "v1.34",
            "distro": "kind", "rc": 0, "assertions": ["PASS\tsignal"], "skipped": False,
            "skip_reason": ""}
    unknown = dict(good, fault="unknown-scenario")
    missing = {k: v for k, v in good.items() if k != "rc"}
    lines = [json.dumps(good), json.dumps(unknown), "not json", json.dumps(missing)]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load = corpus.load_corpus([p])
    assert len(load.rows) == 1
    assert load.withheld == 3
    assert any("unknown-scenario" in r for r in load.reasons)


def test_never_raises_on_bad_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    load = corpus.load_corpus([p])
    assert load.rows == () and load.withheld == 0
