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
    p.add_argument("--checkpoint-every", type=int, default=None, metavar="STEPS",
                   help="write a resumable checkpoint every N optimizer steps "
                        f"(default {TrainConfig().checkpoint_every}; 0 disables)")
    p.add_argument("--resume", action="store_true",
                   help="continue from the checkpoint beside --out instead of "
                        "starting over; refuses a checkpoint written from a "
                        "different recipe or dataset")
    args = p.parse_args()

    # `if v` would silently drop --checkpoint-every 0, the one value whose whole
    # purpose is to turn checkpointing off. Every override is compared against
    # None so a deliberate zero survives.
    overrides = {k: v for k, v in (("base", args.base), ("epochs", args.epochs),
                                   ("checkpoint_every", args.checkpoint_every))
                 if v is not None}
    cfg = dataclasses.replace(TrainConfig(), **overrides)
    rows = data.load_jsonl(args.dataset / "train.jsonl")
    if args.limit:
        rows = rows[: args.limit]
    model, tok = train.load_model_and_tokenizer(cfg)
    log = train.run_training(model, tok, rows, cfg, args.out, resume=args.resume)
    print(f"trained on {log['examples']} examples "
          f"({log['dropped_overlong']} dropped overlong), "
          f"{log['optimizer_steps']} optimizer steps -> {args.out}")
