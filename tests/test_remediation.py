"""The suggestion vocabulary must be kubeagent's, not the catalog author's.

Every `suggested fix (deterministic, pre-reviewed — do not substitute): …`
line kubeagent renders is filled by internal/remediation.For, which switches
on the finding's issue kind and returns one of a fixed set of strings. A
training prompt that carries any other string teaches the model to read an
answer off a field that, at serve time, will say something else — which is a
train/serve skew, not a cosmetic difference.

The golden rows are the anchor: contract/golden/input.json is a byte-for-byte
capture of the real binary's output, so its next_step and command values are
ground truth rather than a transcription of the Go source.
"""
import json
from pathlib import Path

import yaml

from kubeagent_verdict import remediation as r

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "contract" / "golden"
FIXTURE = ROOT / "tests" / "fixtures" / "gather_fixture.yaml"


def test_mirror_reproduces_the_captured_golden_rows():
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    # The capture ran on this fixture. A golden finding has no container field,
    # so each one's container comes from the fixture, in finding order.
    containers = {f"{w['namespace']}/{w['name']}": [f["container"] for f in w["findings"]]
                  for w in yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["workloads"]}
    rows = [(f, w, container) for w in d["workloads"]
            for f, container in zip(w["findings"], containers[f"{w['namespace']}/{w['name']}"],
                                    strict=True)]
    assert rows, "golden capture carries no findings — the anchor is gone"
    assert any(container for _, _, container in rows), "no captured command names a container"
    for f, w, container in rows:
        # The capture renders "<pod>" literally where the pod name was redacted.
        got = r.suggest(f["issue"], ns=w["namespace"], pod="<pod>", container=container)
        assert got.next_step == f["next_step"], f["issue"]
        assert got.command == f["command"], f["issue"]


def test_unknown_issue_falls_to_kubeagents_default_arm():
    got = r.suggest("ContainerStartError", ns="shop", pod="p", container="app")
    assert got.next_step == "inspect the object for details"
    assert got.command == "kubectl -n shop describe pod p"


def test_crashloop_uses_previous_logs_and_drops_an_empty_container():
    assert r.suggest("CrashLoopBackOff", ns="shop", pod="p", container="").command == (
        "kubectl -n shop logs p --previous")


# suggest_for is kubeagent's suggestionFor (internal/explain/explain.go:148-171):
# the prompt's command names `<pod>`, not the pod, unless the finding sits on
# the workload itself. Each vector below is a Go test's, cited where it stands.

def test_suggest_for_masks_a_crashloop_pod():
    # explain_test.go:321-337: finding shop/web-abc on workload shop/web.
    got = r.suggest_for("CrashLoopBackOff", ns="shop", pod="web-abc", container="web",
                        workload="web")
    assert got.command == "kubectl -n shop logs <pod> -c web --previous"  # :334


def test_suggest_for_masks_an_image_pull_pod():
    # incident_test.go:15-43 and :108-119: finding shop/web-7d9f-abcde on shop/web.
    got = r.suggest_for("ImagePullBackOff", ns="shop", pod="web-7d9f-abcde", workload="web")
    assert got.command == "kubectl -n shop describe pod <pod>"  # :112


def test_suggest_for_keeps_the_container_when_it_masks_the_pod():
    # incident_test.go:15-43 and :108-119: finding shop/cart-6b8d94f7c5-q2xzt,
    # container cart, on shop/cart.
    got = r.suggest_for("CrashLoopBackOff", ns="shop", pod="cart-6b8d94f7c5-q2xzt",
                        container="cart", workload="cart")
    assert got.command == "kubectl -n shop logs <pod> -c cart --previous"  # :113


def test_suggest_for_keeps_the_name_of_a_finding_on_the_workload_itself():
    # incident_test.go:125-139: RolloutStuck sets the finding's pod to shop/web,
    # the workload's own identity, so the command keeps the name.
    got = r.suggest_for("RolloutStuck", ns="shop", pod="web", workload="web")
    assert got.command == "kubectl -n shop get events --field-selector involvedObject.name=web"


def test_suggest_for_changes_only_the_command():
    # The next step is the issue's, whoever the pod is.
    for issue in ("CrashLoopBackOff", "ImagePullBackOff", "JobFailed", "RolloutStuck"):
        masked = r.suggest_for(issue, ns="shop", pod="web-abc", workload="web")
        assert masked.next_step == r.suggest(issue, ns="shop", pod="web-abc").next_step


def test_suggest_for_reproduces_the_golden_from_the_real_pod_names():
    # The same anchor as the first test, but from the fixture's real pod names:
    # the capture ran on them, and kubeagent put `<pod>` in each command.
    d = json.loads((GOLDEN / "input.json").read_text(encoding="utf-8"))
    fixture = {f"{w['namespace']}/{w['name']}": w["findings"]
               for w in yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["workloads"]}
    n = 0
    for w in d["workloads"]:
        for f, src in zip(w["findings"], fixture[f"{w['namespace']}/{w['name']}"], strict=True):
            ns, pod = src["pod"].split("/", 1)
            assert ns == w["namespace"]
            got = r.suggest_for(f["issue"], ns=ns, pod=pod, container=src["container"],
                                workload=w["name"])
            assert got.command == f["command"], (f["issue"], src["pod"])
            n += 1
    assert n, "golden capture carries no findings — the anchor is gone"
