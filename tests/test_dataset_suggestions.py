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


def _command_shapes() -> set[re.Pattern[str]]:
    """Every command `remediation.suggest` can build, as an anchored regex.

    Rendered with sentinel names and then substituted, so the shape comes from
    the mirror itself rather than from a second hand-written list that could
    drift away from it. Both container variants are generated because the
    empty one drops the `-c` flag.
    """
    out = set()
    for issue in ISSUES:
        for kind in ("", "CronJob"):
            for container in ("", "CTR"):
                cmd = r.suggest(issue, ns="NS", pod="POD", container=container,
                                kind=kind).command
                pat = re.escape(cmd)
                for sentinel in ("NS", "POD", "CTR"):
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
