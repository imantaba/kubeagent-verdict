"""Merge the LoRA adapter, convert to GGUF, quantize to Q8_0, verify, package.

Every external step is a subprocess through run_cmd, so the chain is
testable with a recording fake and the real run is fully reproducible:
llama.cpp is cloned at a pinned release tag, never at HEAD.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kubeagent_verdict.export import modelfile

# llama.cpp release tag (the project moved to semver tags in 2026; verified
# current at plan time). Bump deliberately and re-run the full export + eval.
LLAMA_CPP_TAG = "v0.2.0"
LLAMA_CPP_REPO = "https://github.com/ggml-org/llama.cpp"


def run_cmd(cmd: list, cwd: Path | None = None) -> None:
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def merge_adapter(base: str, adapter_dir: Path, merged_dir: Path) -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float32)
    merged = PeftModel.from_pretrained(model, adapter_dir).merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_dir, safe_serialization=True)
    AutoTokenizer.from_pretrained(base).save_pretrained(merged_dir)


def export_all(base: str, adapter_dir: Path, workdir: Path, out_dir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    merged = workdir / "merged"
    merge_adapter(base, adapter_dir, merged)

    llama = workdir / "llama.cpp"
    if not llama.exists():
        run_cmd(["git", "clone", "--depth", "1", "--branch", LLAMA_CPP_TAG,
                 LLAMA_CPP_REPO, llama])

    f16 = workdir / "kubeagent-verdict-0.6b-f16.gguf"
    run_cmd([sys.executable, llama / "convert_hf_to_gguf.py", merged,
             "--outfile", f16, "--outtype", "f16"])

    run_cmd(["cmake", "-B", "build", "-DLLAMA_BUILD_TESTS=OFF"], cwd=llama)
    run_cmd(["cmake", "--build", "build", "--target", "llama-quantize",
             "llama-cli", "llama-server", "-j"], cwd=llama)

    gguf = out_dir / modelfile.GGUF_NAME
    run_cmd([llama / "build" / "bin" / "llama-quantize", f16, gguf, "Q8_0"])

    # Load-verify: the quantized file must produce tokens before we ship it.
    run_cmd([llama / "build" / "bin" / "llama-cli", "-m", gguf,
             "-p", "hello", "-n", "4", "--temp", "0"])

    write_release_files(out_dir, gguf)
    return gguf


def write_release_files(out_dir: Path, gguf: Path) -> None:
    mf = out_dir / "Modelfile"
    mf.write_text(modelfile.modelfile_text(gguf.name), encoding="utf-8")
    (out_dir / "SHA256SUMS").write_text(
        modelfile.sha256sums([gguf, mf]), encoding="utf-8")
