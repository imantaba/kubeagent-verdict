"""Modelfile and SHA256SUMS emitters. Stdlib-only.

OLLAMA_TEMPLATE must render byte-identically to train.data.prompt_prefix
for a (system, user) conversation — that agreement is the whole reason the
model answers in the format it was trained on, and
tests/test_modelfile.py::test_serving_template_matches_training_format
pins it. Change either side only together.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

GGUF_NAME = "kubeagent-verdict-0.6b-q8_0.gguf"

OLLAMA_TEMPLATE = ("{{- range .Messages }}<|im_start|>{{ .Role }}\n"
                   "{{ .Content }}<|im_end|>\n"
                   "{{ end }}<|im_start|>assistant\n")


def modelfile_text(gguf_name: str) -> str:
    return (f"FROM ./{gguf_name}\n"
            f'TEMPLATE """{OLLAMA_TEMPLATE}"""\n'
            "PARAMETER stop <|im_end|>\n"
            "PARAMETER temperature 0\n"
            "PARAMETER num_ctx 32768\n")


def sha256sums(paths: list[Path]) -> str:
    lines = []
    for p in paths:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  {p.name}")
    return "\n".join(lines) + "\n"
