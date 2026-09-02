"""Plain-torch LoRA training loop. No Trainer class: the loop is ~40 lines
and owning it means seeding, masking, and logging have no hidden defaults."""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
from pathlib import Path

from kubeagent_verdict.train import data
from kubeagent_verdict.train.config import TrainConfig

CHECKPOINT_FILE = "checkpoint.pt"


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


def checkpoint_dir(out_dir: Path) -> Path:
    """A sibling of the output directory, never a child of it.

    `out/adapter/` existing means a run finished -- that is the signal the
    runbook tells an operator to read after a crash, and the one that told us a
    12-hour run had produced nothing. Putting checkpoints inside it would
    create the directory hours before the run ends and destroy that signal.
    """
    return out_dir.parent / (out_dir.name + "-checkpoint")


def _fingerprint(cfg: TrainConfig, encoded: list) -> str:
    """Identifies the recipe and the data, so a resume cannot cross runs.

    Resuming a checkpoint into a different recipe or a different dataset is the
    one failure with no downstream detector: it finishes, writes an adapter,
    and reports a clean run, having trained something no scoreboard can
    identify as wrong. This is what makes it loud instead.

    `checkpoint_every` is deliberately excluded. It is the one config field
    that provably does not affect the weights -- that is what
    `test_checkpointing_does_not_change_what_the_run_produces` asserts -- so it
    is not part of the recipe, and changing it between a crash and a resume is
    not a mismatch.
    """
    recipe = {k: list(v) if isinstance(v, tuple) else v
              for k, v in vars(cfg).items() if k != "checkpoint_every"}
    h = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode("utf-8"))
    h.update(str(len(encoded)).encode("utf-8"))
    for ids, labels in encoded:
        h.update(b"\x00".join((repr(ids).encode("utf-8"), repr(labels).encode("utf-8"))))
    return h.hexdigest()


def _save_checkpoint(ckpt_dir: Path, model, optimizer, *, fingerprint: str,
                     epoch: int, next_index: int, order: list[int], step: int,
                     losses: list[float], py_rng_state, torch_rng_state) -> None:
    """Write resume state. Called only at an accumulation boundary.

    Every caller sits immediately after `optimizer.zero_grad()`, so there are
    no half-accumulated gradients in flight and none need saving -- the awkward
    piece of state is avoided by where this is called from rather than by
    serialising it.

    Everything resume needs is one file, so the update is a single
    `os.replace` and is atomic: a power loss during a checkpoint write leaves
    the *previous* checkpoint intact rather than a half-written one. The
    adapter snapshot beside it is operator convenience -- something loadable to
    look at after a crash -- and is explicitly not resume-critical, which is
    why it does not need the same guarantee.
    """
    import torch

    ckpt_dir.mkdir(parents=True, exist_ok=True)
    blob = {
        "fingerprint": fingerprint,
        "epoch": epoch,
        "next_index": next_index,
        "order": order,
        "step": step,
        "losses": losses,
        "py_rng_state": py_rng_state,
        "torch_rng_state": torch_rng_state,
        "model": _peft_state_dict(model),
        "optimizer": optimizer.state_dict(),
    }
    tmp = ckpt_dir / (CHECKPOINT_FILE + ".tmp")
    torch.save(blob, tmp)
    os.replace(tmp, ckpt_dir / CHECKPOINT_FILE)
    model.save_pretrained(ckpt_dir / "adapter")


def _peft_state_dict(model):
    from peft import get_peft_model_state_dict

    return get_peft_model_state_dict(model)


def _load_checkpoint(ckpt_dir: Path, model, optimizer, fingerprint: str) -> dict:
    import torch
    from peft import set_peft_model_state_dict

    path = ckpt_dir / CHECKPOINT_FILE
    if not path.exists():
        raise ValueError(
            f"--resume was given but there is no checkpoint at {path}. A run that "
            "died before its first checkpoint has nothing to resume; start it "
            "normally. Check --out names the same directory the dead run used.")
    blob = torch.load(path, weights_only=True)
    if blob["fingerprint"] != fingerprint:
        raise ValueError(
            f"the checkpoint at {path} does not match this recipe and dataset. "
            "Resuming it would train a model that is neither run, and nothing "
            "downstream could tell. Delete the checkpoint to start fresh, or "
            "resume with the config and dataset it was written from.")
    set_peft_model_state_dict(model, blob["model"])
    optimizer.load_state_dict(blob["optimizer"])
    return blob


def run_training(model, tokenizer, rows: list[tuple[str, str, str]],
                 cfg: TrainConfig, out_dir: Path, resume: bool = False) -> dict:
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

    ckpt_dir = checkpoint_dir(out_dir)
    fingerprint = _fingerprint(cfg, encoded)
    losses: list[float] = []
    step = 0
    start_epoch, start_index, resumed_order = 0, 0, None
    if resume:
        blob = _load_checkpoint(ckpt_dir, model, optimizer, fingerprint)
        start_epoch, start_index = blob["epoch"], blob["next_index"]
        resumed_order, step, losses = blob["order"], blob["step"], list(blob["losses"])
        # Restoring both generators is what makes a resumed run identical rather
        # than merely similar: the Python one decides each epoch's order, and the
        # torch one is drawn from by LoRA dropout on every forward pass. Restore
        # after the seeding above, which would otherwise overwrite them.
        rng.setstate(blob["py_rng_state"])
        torch.set_rng_state(blob["torch_rng_state"])

    for epoch in range(start_epoch, cfg.epochs):
        if resumed_order is not None and epoch == start_epoch:
            # The interrupted epoch keeps the order it was already running. It
            # cannot be redrawn: `rng` has moved past that shuffle, and drawing
            # a fresh one here would reorder the remaining examples.
            order = resumed_order
        else:
            order = list(range(len(encoded)))
            rng.shuffle(order)
        begin = start_index if epoch == start_epoch else 0
        for i in range(begin, len(order)):
            ids, labels = encoded[order[i]]
            input_ids = torch.tensor([ids])
            label_t = torch.tensor([labels])
            loss = model(input_ids=input_ids, labels=label_t).loss / cfg.grad_accum
            loss.backward()
            if (i + 1) % cfg.grad_accum == 0:
                optimizer.step()
                optimizer.zero_grad()
                step += 1
                losses.append(float(loss.detach()) * cfg.grad_accum)
                if cfg.checkpoint_every and step % cfg.checkpoint_every == 0:
                    _save_checkpoint(
                        ckpt_dir, model, optimizer, fingerprint=fingerprint,
                        epoch=epoch, next_index=i + 1, order=order, step=step,
                        losses=losses, py_rng_state=rng.getstate(),
                        torch_rng_state=torch.get_rng_state())
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
    # Only once the adapter is on disk. A stale checkpoint left beside a
    # finished run would let a later --resume continue a run that already ended.
    shutil.rmtree(ckpt_dir, ignore_errors=True)
    return log
