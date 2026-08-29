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


def test_every_rendered_command_is_one_kubeagent_can_build(rendered):
    shapes = {re.sub(r"[^ ]*$", "", c) if c.startswith("kubectl") else c
              for _, c in ((m.group(1), m.group(2)) for m in rendered)}
    for s in shapes:
        assert s.startswith("kubectl -n "), s
