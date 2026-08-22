"""kv-dataset: render the training dataset. Task 8 adds split/test/manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from kubeagent_verdict.dataset import generate


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-dataset")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    examples = generate.generate(seed=args.seed, size=args.size)
    generate.write_jsonl(args.out / "train.jsonl", examples)
    print(f"wrote {len(examples)} examples to {args.out}")
