from __future__ import annotations

import argparse
import json
from pathlib import Path

from kubeagent_verdict.evals import client, score


def _stratified(rows: list[dict], limit: int) -> list[dict]:
    """Take `limit` rows round-robin across cases, not off the front.

    The test file is written case-block by case-block, so a positional slice
    keeps whichever case happens to be first and silently drops the rest —
    including both adversarial probe slices, which sit at the end. A short
    run must sample the shape of the test set, not its prefix.
    """
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(row.get("meta", {}).get("case", "unknown"), []).append(row)
    out: list[dict] = []
    for i in range(max(len(b) for b in buckets.values())):
        for case in sorted(buckets):
            if i < len(buckets[case]):
                out.append(buckets[case][i])
    return out[:limit]


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-eval")
    p.add_argument("--test", type=Path, required=True)
    p.add_argument("--endpoint", default=client.DEFAULT_ENDPOINT)
    p.add_argument("--model", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    rows = [json.loads(line) for line in
            args.test.read_text(encoding="utf-8").splitlines() if line]
    if args.limit:
        rows = _stratified(rows, args.limit)

    results = score.evaluate(
        rows, lambda messages: client.chat(args.endpoint, args.model, messages))
    board = score.scoreboard(results)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "results.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in results)
    (args.out / "scoreboard.json").write_text(
        json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = score.render_markdown(board)
    (args.out / "scoreboard.md").write_text(md, encoding="utf-8")
    print(md)
