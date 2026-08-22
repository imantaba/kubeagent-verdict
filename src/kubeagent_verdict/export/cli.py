from __future__ import annotations

import argparse
from pathlib import Path

from kubeagent_verdict.export import export


def main() -> None:
    p = argparse.ArgumentParser(prog="kv-export")
    p.add_argument("--base", default="Qwen/Qwen3-0.6B")
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    gguf = export.export_all(base=args.base, adapter_dir=args.adapter,
                             workdir=args.workdir, out_dir=args.out)
    print(f"exported {gguf} + Modelfile + SHA256SUMS")
