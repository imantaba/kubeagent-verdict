"""Plain-torch LoRA training loop. No Trainer class: the loop is ~40 lines
and owning it means seeding, masking, and logging have no hidden defaults."""

from __future__ import annotations

import json
import random
from pathlib import Path

from kubeagent_verdict.train import data
from kubeagent_verdict.train.config import TrainConfig


def load_model_and_tokenizer(cfg: TrainConfig):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(cfg.base)
    model = AutoModelForCausalLM.from_pretrained(cfg.base, torch_dtype=torch.float32)
    lora = LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha,
                      lora_dropout=cfg.lora_dropout,
                      target_modules=list(cfg.target_modules), task_type="CAUSAL_LM")
    return get_peft_model(model, lora), tok


def run_training(model, tokenizer, rows: list[tuple[str, str, str]],
                 cfg: TrainConfig, out_dir: Path) -> dict:
    import torch

    torch.manual_seed(cfg.seed)
    rng = random.Random(cfg.seed)

    encoded, dropped = [], 0
    for system, user, assistant in rows:
        enc = data.encode_example(tokenizer, system, user, assistant, cfg.max_seq_len)
        if enc is None:
            dropped += 1
        else:
            encoded.append(enc)
    if not encoded:
        raise ValueError("every example exceeded max_seq_len; nothing to train on")

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=cfg.lr)
    model.train()
    losses: list[float] = []
    step = 0
    for _epoch in range(cfg.epochs):
        order = list(range(len(encoded)))
        rng.shuffle(order)
        for i, idx in enumerate(order):
            ids, labels = encoded[idx]
            input_ids = torch.tensor([ids])
            label_t = torch.tensor([labels])
            loss = model(input_ids=input_ids, labels=label_t).loss / cfg.grad_accum
            loss.backward()
            if (i + 1) % cfg.grad_accum == 0:
                optimizer.step()
                optimizer.zero_grad()
                step += 1
                losses.append(float(loss) * cfg.grad_accum)
    optimizer.step()  # flush a trailing partial accumulation
    optimizer.zero_grad()

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    log = {"examples": len(encoded), "dropped_overlong": dropped,
           "optimizer_steps": step, "losses": losses,
           "config": {k: list(v) if isinstance(v, tuple) else v
                      for k, v in vars(cfg).items()}}
    (out_dir / "train_log.json").write_text(
        json.dumps(log, indent=2) + "\n", encoding="utf-8")
    return log
