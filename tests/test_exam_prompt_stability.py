"""The banked exam's prompts must not move.

`out/dataset-0924/test.jsonl` is the exam the job-2 generator fix
(2026-09-24-job2-generator-fix-design.md) banks: 252 rows, and a new
baseline. Every model scored after that fix answers these questions, the
0920 build's one live run included. Re-scoring banked replies against a
corrected `meta` is only honest if the QUESTIONS are the same ones the
model saw. This module is that proof: regenerate the exam and compare
`messages` row for row, byte for byte.

Until 2026-09-24 it pointed at `out/dataset-0920/test.jsonl`, the 263-row
exam the 0920 build answered. The generator fix moves rendered bytes on
purpose, so that bank no longer matches this generator. Between the
commit that re-points this module and the one that regenerates the bank,
the new bank does not exist yet and this module skips.

`messages` is all three -- system, user and the gold assistant answer.
`score.evaluate` reads the gold answer back out of `messages[2]` to build
its expected verdicts, so a moved gold answer would change the grading as
surely as a moved prompt would change the question.

The bank is gitignored working data, not a committed fixture. When it is
absent this module SKIPS and names the path it wanted, rather than passing
on nothing.
"""
import json
from pathlib import Path

import pytest

from kubeagent_verdict.dataset import generate

BANK = Path(__file__).resolve().parents[1] / "out" / "dataset-0924" / "test.jsonl"

pytestmark = pytest.mark.skipif(
    not BANK.exists(), reason=f"banked exam not present at {BANK}")


def _banked_rows() -> list[dict]:
    return [json.loads(line) for line in
            BANK.read_text(encoding="utf-8").splitlines() if line]


def test_the_banked_exam_is_the_252_row_exam():
    """A guard on the guard. Comparing row for row proves nothing if the
    two sides are different lengths and the zip silently truncates.
    """
    assert len(_banked_rows()) == 252


def test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam():
    """Every rendered byte of the exam -- prompt and gold answer -- comes
    out of `generate.test_set()` today exactly as it went into the bank.

    This is what lets a later change to `meta` be called a re-score rather
    than a new exam.
    """
    banked = _banked_rows()
    fresh = [generate.to_row(e) for e in generate.test_set()]
    assert len(fresh) == len(banked)
    moved = [i for i, (f, b) in enumerate(zip(fresh, banked))
             if f["messages"] != b["messages"]]
    assert not moved, f"rows whose messages moved: {moved}"
