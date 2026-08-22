"""The pinned training recipe. Changing any default is a deliberate,
committed decision — the eval scoreboard is only comparable across runs
that share this recipe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainConfig:
    base: str = "Qwen/Qwen3-0.6B"
    seed: int = 17
    epochs: int = 2
    lr: float = 2e-4
    batch_size: int = 1
    grad_accum: int = 16
    max_seq_len: int = 4096
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: tuple[str, ...] = ("q_proj", "k_proj", "v_proj", "o_proj",
                                       "gate_proj", "up_proj", "down_proj")
