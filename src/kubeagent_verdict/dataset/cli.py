"""kv-dataset: render the training dataset. Task 8 adds split/test/manifest.

`--probe-wide FILE` is a separate mode: it writes only the widened
shared-origin probe (a standalone diagnostic file, deterministic, never part
of the exam) and exits. It needs no seed and touches no other file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kubeagent_verdict.dataset import generate


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-dataset")
    p.add_argument("--seed", type=int)
    p.add_argument("--size", type=int)
    p.add_argument("--out", type=Path)
    p.add_argument(
        "--probe-wide", type=Path, metavar="FILE",
        help="write the widened shared-origin probe (five twin pairs per "
             "held-out origin; diagnostic only, gates no release) to FILE "
             "and exit; --seed/--size/--out are not used")
    args = p.parse_args()
    if args.probe_wide is not None:
        rows = generate.shared_origin_wide_probes()
        args.probe_wide.parent.mkdir(parents=True, exist_ok=True)
        generate.write_jsonl(args.probe_wide, rows)
        print(f"wrote {len(rows)} rows ({len(rows) // 2} twin pairs) "
              f"to {args.probe_wide}")
        return
    if args.seed is None or args.size is None or args.out is None:
        p.error("--seed, --size and --out are required (unless --probe-wide)")
    args.out.mkdir(parents=True, exist_ok=True)
    examples = generate.generate(seed=args.seed, size=args.size)
    train, val = generate.split(examples, seed=args.seed)
    test = generate.test_set()
    train = generate.drop_held_out(train, test)
    val = generate.drop_held_out(val, test)
    generate.write_jsonl(args.out / "train.jsonl", train)
    generate.write_jsonl(args.out / "val.jsonl", val)
    generate.write_jsonl(args.out / "test.jsonl", test)
    man = generate.manifest(args.seed, args.size, train, val, test)
    (args.out / "manifest.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(man, indent=2, sort_keys=True))
