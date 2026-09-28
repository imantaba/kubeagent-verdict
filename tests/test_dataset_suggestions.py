"""Every `suggested fix` line in a generated prompt must be one kubeagent emits.

This is the class-level guard behind the one-row fix. A hand-written next_step
in the catalog is not a nicer wording of kubeagent's — it is a different field.
kubeagent's strings restate the symptom generically ("the probe keeps failing");
a catalog author's name the cause ("check whether a NetworkPolicy now blocks the
probe's traffic"). Train on the second and serve the first and the model has
learned that this line carries the answer, on a serving distribution where it
never does.
"""
import re

import pytest

from kubeagent_verdict import remediation as r
from kubeagent_verdict.dataset import generate as g

# One issue per arm of the mirror's switch, plus one it does not know so the
# default arm is covered too.
ISSUES = ("CrashLoopBackOff", "RestartLoop", "ImagePullBackOff", "ErrImagePull",
          "OOMKilled", "Unschedulable", "CreateContainerConfigError",
          "Init:CreateContainerConfigError", "ProbeFailure", "VolumeAttachError",
          "VolumeMountError", "Init:ImagePullBackOff", "Init:ErrImagePull",
          "Init:CrashLoopBackOff", "Init:OOMKilled", "FailedCreate", "JobFailed",
          "RolloutStuck", "ContainerStartError")

LINE = re.compile(r"suggested fix \(deterministic, pre-reviewed — do not "
                  r"substitute\): (.*?) \| run: (.*)")


@pytest.fixture(scope="module")
def rendered():
    examples = g.generate(seed=7, size=900) + g.test_set()
    return [m for ex in examples for m in LINE.finditer(ex.user)]


def test_the_corpus_actually_renders_suggestion_lines(rendered):
    # Guards the guard: a regex that stopped matching would make every
    # assertion below vacuously true.
    assert len(rendered) > 1000


def test_every_rendered_suggestion_is_one_kubeagent_can_emit(rendered):
    bad = sorted({m.group(1) for m in rendered} - r.VOCABULARY)
    assert not bad, (
        f"{len(bad)} suggestion string(s) kubeagent never emits reached a prompt: "
        + "; ".join(repr(b) for b in bad[:5]))


# A DNS-1123-ish object name. Deliberately excludes "/": the Go builder is
# handed an already-split namespace and pod, so a slashed value reaching either
# slot is the exact caller bug this shape check exists to catch.
NAME = r"[a-z0-9][a-z0-9.-]*"

# The issues whose finding sits on the workload object itself, so kubeagent's
# prompt keeps the name (internal/explain/explain.go:162-171): a JobFailed
# finding names the Job or the CronJob (remediation.go:74-81, 87-95), a
# RolloutStuck finding the controller (remediation.go:97-109). Every other arm
# addresses a pod, and the prompt names it `<pod>`.
OBJECT_ISSUES = ("JobFailed", "RolloutStuck")


def _command_shapes() -> set[re.Pattern[str]]:
    """Every command kubeagent's prompt can carry, as an anchored regex.

    Rendered with sentinel names through `remediation.suggest_for` and then
    substituted, so the shape comes from the source itself rather than from a
    second hand-written list that could drift away from it. Both container
    variants are generated because the empty one drops the `-c` flag. A
    pod-addressed arm keeps `<pod>` as it is: a real pod name there is a
    command kubeagent never sends.
    """
    out = set()
    for issue in ISSUES:
        pod = "WORKLOAD" if issue in OBJECT_ISSUES else "POD"
        for kind in ("", "CronJob"):
            for container in ("", "CTR"):
                cmd = r.suggest_for(issue, ns="NS", pod=pod, container=container,
                                    kind=kind, workload="WORKLOAD").command
                pat = re.escape(cmd)
                for sentinel in ("NS", "WORKLOAD", "CTR"):
                    pat = pat.replace(sentinel, NAME)
                out.add(re.compile("^" + pat + "$"))
    return out


def test_every_rendered_command_is_one_kubeagent_can_build(rendered):
    shapes = _command_shapes()
    bad = sorted({m.group(2) for m in rendered
                  if not any(p.match(m.group(2)) for p in shapes)})
    assert not bad, (
        f"{len(bad)} command(s) kubeagent never builds reached a prompt: "
        + "; ".join(repr(b) for b in bad[:5]))


def test_a_real_pod_name_is_not_a_shape_kubeagent_can_build():
    # Guards the guard: the shapes must refuse the pod name kubeagent masks.
    shapes = _command_shapes()
    for cmd in ("kubectl -n shop describe pod web-7d9f-abcde",
                "kubectl -n shop logs cart-6b8d94f7c5-q2xzt -c cart --previous"):
        assert not any(p.match(cmd) for p in shapes), cmd
    for cmd in ("kubectl -n shop describe pod <pod>",
                "kubectl -n shop logs <pod> -c cart --previous",
                "kubectl -n shop get events --field-selector involvedObject.name=web"):
        assert any(p.match(cmd) for p in shapes), cmd


# The two arms that address a pod by name (remediation.go:66-72 and :83-85).
POD_SLOT = re.compile(r"^kubectl -n \S+ (?:logs (?!job/)|describe pod )(\S+)")


def test_every_pod_addressed_command_names_the_pod_placeholder(rendered):
    # kubeagent's prompt names `<pod>` where a command addresses a pod
    # (explain.go:162-171). A generated pod name never equals its workload's
    # (names.pod_name adds two suffixes), so no generated command keeps one.
    slots = [s.group(1) for m in rendered if (s := POD_SLOT.match(m.group(2)))]
    assert len(slots) > 1000
    bad = sorted({s for s in slots if s != "<pod>"})
    assert not bad, (
        f"{len(bad)} pod name(s) reached a suggested fix command: "
        + "; ".join(repr(b) for b in bad[:5]))
