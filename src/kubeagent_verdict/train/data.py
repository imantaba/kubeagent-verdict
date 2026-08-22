"""ChatML encoding with assistant-only loss. Torch-free on purpose.

The template is written out explicitly instead of calling
tokenizer.apply_chat_template: Qwen3's bundled chat template injects
think-block scaffolding, and the serving side (Ollama's TEMPLATE in the
exported Modelfile) must render byte-identically to what the model was
trained on. tests/test_modelfile.py pins the two together.

Prompt and answer are tokenized separately and concatenated, so the
prompt's token ids are a prefix of the full sequence by construction —
no reliance on BPE merging identically across the boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

IM_START = "<|im_start|>"
IM_END = "<|im_end|>"


def prompt_prefix(system: str, user: str) -> str:
    return (f"{IM_START}system\n{system}{IM_END}\n"
            f"{IM_START}user\n{user}{IM_END}\n"
            f"{IM_START}assistant\n")


def full_text(system: str, user: str, assistant: str) -> str:
    return prompt_prefix(system, user) + assistant + IM_END


def encode_example(tok, system: str, user: str, assistant: str,
                   max_len: int) -> tuple[list[int], list[int]] | None:
    prompt_ids = tok(prompt_prefix(system, user), add_special_tokens=False)["input_ids"]
    target_ids = tok(assistant + IM_END, add_special_tokens=False)["input_ids"]
    ids = prompt_ids + target_ids
    if len(ids) > max_len:
        return None
    labels = [-100] * len(prompt_ids) + target_ids
    return ids, labels


def load_jsonl(path: Path) -> list[tuple[str, str, str]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            msgs = json.loads(line)["messages"]
            roles = [m["role"] for m in msgs]
            if roles != ["system", "user", "assistant"]:
                raise ValueError(f"{path}: unexpected roles {roles}")
            out.append((msgs[0]["content"], msgs[1]["content"], msgs[2]["content"]))
    return out
