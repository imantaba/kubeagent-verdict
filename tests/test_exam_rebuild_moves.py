"""What the exam rebuild moved (2026-10-05). It compares an in-process
build with out/dataset-1005, the last build before the rebuild. Rows stay
aligned: the same counts and the same case at every index. Every changed
prompt line is one of three kinds: a refused-read line (item 6), a
scheduler line (item 1) or a service line (item 9). Skips when the old
folder is not on this machine."""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from kubeagent_verdict.dataset import generate

OLD = pathlib.Path(__file__).resolve().parents[1] / "out" / "dataset-1005"
_SERVICE = re.compile(r"^  - \S+/\S+ \(")

pytestmark = pytest.mark.skipif(not (OLD / "test.jsonl").exists(),
                                reason="out/dataset-1005 is not on this machine")


def _old(split: str) -> list[dict]:
    return [json.loads(ln) for ln in (OLD / f"{split}.jsonl").read_text().splitlines()]


def _allowed(line: str) -> bool:
    return ("is forbidden" in line or "nodes are available" in line
            or "FailedScheduling" in line or _SERVICE.match(line) is not None)


@pytest.fixture(scope="module")
def new() -> dict[str, list[dict]]:
    """The build kv-dataset writes for --seed 17 --size 8000, in process
    (the same calls as dataset/cli.py:58-65)."""
    examples = generate.generate(seed=17, size=8000)
    train, val = generate.split(examples, seed=17)
    test = generate.test_set()
    return {"train": [generate.to_row(e) for e in generate.drop_held_out(train, test)],
            "val": [generate.to_row(e) for e in generate.drop_held_out(val, test)],
            "test": [generate.to_row(e) for e in test]}


@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_rows_stay_aligned(new, split):
    old = _old(split)
    assert len(new[split]) == len(old)
    assert [r["meta"]["case"] for r in new[split]] == [r["meta"]["case"] for r in old]


@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_every_changed_prompt_line_is_one_of_the_three_kinds(new, split):
    bad = []
    for i, (a, b) in enumerate(zip(_old(split), new[split])):
        old_lines = a["messages"][1]["content"].split("\n")
        new_lines = b["messages"][1]["content"].split("\n")
        if len(old_lines) != len(new_lines):
            bad.append((i, "line count"))
            continue
        bad += [(i, n) for o, n in zip(old_lines, new_lines) if o != n and not _allowed(n)]
    assert bad == []
