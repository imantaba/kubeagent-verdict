"""kv-dataset: render the training dataset. Task 8 adds split/test/manifest.

`--probe-wide FILE` and `--probe-cousins FILE` are separate modes: each
writes only its standalone diagnostic file (deterministic, never part of the
exam) and exits. Neither needs a seed and neither touches any other file.
The wide probe asks the six held-out origins five times each; the cousin
probe asks each trainable scenario once.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kubeagent_verdict.dataset import generate


def _write_probe_file(path: Path, rows: list[generate.Example]) -> None:
    """Write a diagnostic probe file and print its summary line.

    Makes the parent directory if needed, writes the rows as JSONL, then
    prints how many rows and twin pairs went to which file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    generate.write_jsonl(path, rows)
    print(f"wrote {len(rows)} rows ({len(rows) // 2} twin pairs) to {path}")


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
    p.add_argument(
        "--probe-cousins", type=Path, metavar="FILE",
        help="write the cousin probe (one twin pair per trainable "
             "scenario, full width; diagnostic only, gates no release) to "
             "FILE and exit; --seed/--size/--out are not used")
    args = p.parse_args()
    if args.probe_wide is not None and args.probe_cousins is not None:
        p.error("--probe-wide and --probe-cousins are separate modes; pass one of them")
    if args.probe_wide is not None:
        _write_probe_file(args.probe_wide, generate.shared_origin_wide_probes())
        return
    if args.probe_cousins is not None:
        _write_probe_file(args.probe_cousins, generate.shared_origin_cousin_probes())
        return
    if args.seed is None or args.size is None or args.out is None:
        p.error("--seed, --size and --out are required "
                "(unless --probe-wide or --probe-cousins)")
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
