"""The suggestion vocabulary must be kubeagent's, not the catalog author's.

Every `suggested fix (deterministic, pre-reviewed — do not substitute): …`
line kubeagent renders is filled by internal/remediation.For, which switches
on the finding's issue kind and returns one of a fixed set of strings. A
training prompt that carries any other string teaches the model to read an
answer off a field that, at serve time, will say something else — which is a
train/serve skew, not a cosmetic difference.

The two golden rows are the anchor: contract/golden/input.json is a
byte-for-byte capture of the real binary's output, so its next_step and
command values are ground truth rather than a transcription of the Go source.
"""
import json
from pathlib import Path

from kubeagent_verdict import remediation as r

GOLDEN = Path(__file__).resolve().parent.parent / "contract" / "golden"


def test_mirror_reproduces_the_captured_golden_rows():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    rows = [(f, w) for w in d["workloads"] for f in w["findings"]]
    assert rows, "golden capture carries no findings — the anchor is gone"
    for f, w in rows:
        # The capture renders "<pod>" literally where the pod name was redacted.
        got = r.suggest(f["issue"], ns=w["namespace"], pod="<pod>", container="app")
        assert got.next_step == f["next_step"], f["issue"]
        assert got.command == f["command"], f["issue"]


def test_unknown_issue_falls_to_kubeagents_default_arm():
    got = r.suggest("ContainerStartError", ns="shop", pod="p", container="app")
    assert got.next_step == "inspect the object for details"
    assert got.command == "kubectl -n shop describe pod p"


def test_crashloop_uses_previous_logs_and_drops_an_empty_container():
    assert r.suggest("CrashLoopBackOff", ns="shop", pod="p", container="").command == (
        "kubectl -n shop logs p --previous")
