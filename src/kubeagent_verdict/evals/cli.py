from __future__ import annotations

import argparse
import json
from pathlib import Path

from kubeagent_verdict.evals import client, score


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
        rows = rows[: args.limit]

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
