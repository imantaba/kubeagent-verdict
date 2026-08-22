from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

from kubeagent_verdict.train import data, train
from kubeagent_verdict.train.config import TrainConfig


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-train")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--base")
    p.add_argument("--epochs", type=int)
    p.add_argument("--limit", type=int, help="train on the first N examples (smoke runs)")
    args = p.parse_args()

    overrides = {k: v for k, v in (("base", args.base), ("epochs", args.epochs)) if v}
    cfg = dataclasses.replace(TrainConfig(), **overrides)
    rows = data.load_jsonl(args.dataset / "train.jsonl")
    if args.limit:
        rows = rows[: args.limit]
    model, tok = train.load_model_and_tokenizer(cfg)
    log = train.run_training(model, tok, rows, cfg, args.out)
    print(f"trained on {log['examples']} examples "
          f"({log['dropped_overlong']} dropped overlong), "
          f"{log['optimizer_steps']} optimizer steps -> {args.out}")
