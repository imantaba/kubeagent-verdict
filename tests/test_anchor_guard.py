"""Spec 4b-3 test 9: an empty anchor would match every line, so it is refused."""
import dataclasses
import random

import pytest

from kubeagent_verdict.dataset import cases, catalog, stories
from kubeagent_verdict.dataset import names as names_mod


@pytest.mark.parametrize("anchor", ["", "  "])
def test_an_empty_anchor_is_refused(anchor):
    with pytest.raises(ValueError, match="anchor is empty"):
        stories.Answer(anchor=anchor, cause="the disk is full", keys=("disk",), rationale="r")


def test_an_anchor_that_formats_to_empty_is_refused():
    e = next(x for x in catalog.trainable() if x.answer is not None)
    e = dataclasses.replace(e, answer=dataclasses.replace(e.answer, anchor="{image}"))
    n = dataclasses.replace(names_mod.draw(random.Random(11)), image="")
    with pytest.raises(ValueError, match="empty after formatting"):
        cases._entry_gold(e, n, ["any line"], [])
