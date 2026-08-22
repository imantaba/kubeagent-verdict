"""kv-dataset: render the training dataset. Task 8 adds split/test/manifest."""

from __future__ import annotations

import argparse
import json
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
    train, val = generate.split(examples, seed=args.seed)
    test = generate.corpus_test_set()
    train = generate.drop_held_out(train, test)
    val = generate.drop_held_out(val, test)
    generate.write_jsonl(args.out / "train.jsonl", train)
    generate.write_jsonl(args.out / "val.jsonl", val)
    generate.write_jsonl(args.out / "test.jsonl", test)
    man = generate.manifest(args.seed, args.size, train, val, test)
    (args.out / "manifest.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(man, indent=2, sort_keys=True))
