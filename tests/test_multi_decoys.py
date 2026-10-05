"""Spec 4b-3: multi rows and decoys.

The build here is the out/dataset-MMDD pipeline: generate(17, 8000), split,
drop held-out. Tests that compare with the last build read
out/dataset-1004-4b2 and skip when it is not on this machine.
"""
import json
from pathlib import Path

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import generate, gold
from kubeagent_verdict.evals import score

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "out" / "dataset-1004-4b2"
SPLITS = ("train", "val", "test")
_needs_old = pytest.mark.skipif(not OLD.is_dir(), reason="out/dataset-1004-4b2 is not on this machine")


@pytest.fixture(scope="module")
def build() -> dict[str, list]:
    ex = generate.generate(17, 8000)
    tr, va = generate.split(ex, 17)
    te = generate.test_set()
    return {"train": generate.drop_held_out(tr, te),
            "val": generate.drop_held_out(va, te), "test": te}


def _old(split: str) -> list[dict]:
    path = OLD / f"{split}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _all(build):
    return [e for split in SPLITS for e in build[split]]


_FALLBACK = ("4 workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them.")


# --- test 5: the summary rule ------------------------------------------------

def test_named_and_different_causes_are_separate():
    assert gold.separate_for("none", ["w", "x"])


def test_one_none_of_these_row_is_not_separate():
    assert not gold.separate_for("none", ["w", ""])


def test_two_rows_with_one_cause_are_not_separate():
    assert not gold.separate_for("none", ["w", "w"])


def test_a_separate_label_is_separate_even_with_a_none_row():
    assert gold.separate_for("separate", ["w", ""])


def test_four_rows_put_the_third_and_fourth_on_the_last_line():
    s = gold.summary_lines([("a/one", "w"), ("b/two", "x"), ("c/three", ""), ("d/four", "z")],
                           separate=False)
    assert s.split("\n") == [_FALLBACK, "a/one: w.", "b/two: x.",
                             "c/three: its own lines do not show why. d/four: z."]


@pytest.mark.parametrize("n", [2, 3])
def test_two_and_three_rows_get_one_line_each(n):
    rows = [(f"ns/w{i}", f"cause {i}") for i in range(n)]
    lines = gold.summary_lines(rows, separate=True).split("\n")
    assert lines[0] == f"{n} workloads are failing for separate reasons."
    assert lines[1:] == [f"ns/w{i}: cause {i}." for i in range(n)]


_SUMMARY_CASES = ("multi", "multi_misattribution_probe")


# --- test 6: every multi and probe summary -----------------------------------

def test_every_multi_and_probe_summary_names_every_workload_and_scores(build):
    seen = 0
    for e in _all(build):
        if e.case not in _SUMMARY_CASES:
            continue
        seen += 1
        doc = json.loads(e.assistant)
        s = doc["summary"]
        lines = s.split("\n")
        assert len(lines) <= c.MAX_SUMMARY_LINES, e.group
        assert all(len(ln) <= c.MAX_MODEL_LINE_RUNES for ln in lines), e.group
        for v in doc["verdicts"]:
            assert f"{v['workload']}: " in s, (e.group, v["workload"])
        assert score.job3(e.meta["label"], s) == 1.0, (e.group, e.meta["label"], s)
    assert seen == 758  # 738 multi + 20 multi_misattribution_probe


# --- test 7: the probe rows do not move --------------------------------------

@_needs_old
def test_the_probe_rows_are_the_old_ones(build):
    new = [generate.to_row(e) for e in build["test"] if e.case == "multi_misattribution_probe"]
    old = [r for r in _old("test") if r["meta"]["case"] == "multi_misattribution_probe"]
    assert len(new) == len(old) == 20
    assert new == old


# --- test 8: 4b-1's answers move only to name every workload -----------------

@_needs_old
def test_only_wide_non_shared_family_answers_move(build):
    moved = 0
    for split in SPLITS:
        old = _old(split)
        assert len(build[split]) == len(old), split
        for i, (e, o) in enumerate(zip(build[split], old)):
            if not e.case.startswith("shared_origin"):
                continue
            na, oa = e.assistant, o["messages"][2]["content"]
            if na == oa:
                continue
            moved += 1
            nd, od = json.loads(na), json.loads(oa)
            assert nd["verdicts"] == od["verdicts"], (split, i)
            assert e.meta["label"] != "shared", (split, i)
            assert len(nd["verdicts"]) >= 4, (split, i)
            nl, ol = nd["summary"].split("\n"), od["summary"].split("\n")
            assert len(nl) == len(ol) == 4, (split, i)
            assert nl[:3] == ol[:3], (split, i)
            assert nl[3].startswith(ol[3] + " "), (split, i)
            for v in nd["verdicts"]:
                assert f"{v['workload']}: " in nd["summary"], (split, i)
    # Spec 4b-3 §3 (amended 2026-10-05): 77 train and val rows, no exam row.
    assert moved == 77


# --- test 13: non-multi prompts do not move ----------------------------------

@_needs_old
@pytest.mark.parametrize("split", SPLITS)
def test_no_non_multi_prompt_moves(build, split):
    old = _old(split)
    assert len(build[split]) == len(old)
    for i, (e, o) in enumerate(zip(build[split], old)):
        if e.case == "multi":
            continue
        assert generate.to_row(e)["messages"][:2] == o["messages"][:2], (split, i)
