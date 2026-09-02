"""Resume must be indistinguishable from never having been interrupted.

A checkpoint that restores *almost* everything is worse than none at all: it
finishes, writes an adapter, and reports a clean run, while having silently
trained a model that is not the recipe. Nothing downstream would catch it --
the eval scoreboard cannot tell "this recipe scored 0.4" from "some other
recipe scored 0.4".

So the guard here is an equality, not an inspection. An interrupted-and-resumed
run must produce a **bit-for-bit identical** adapter to an uninterrupted one at
the same seed. That cannot pass vacuously: every piece of state resume has to
carry -- optimizer moments, the torch RNG that LoRA dropout draws from, the
Python RNG that orders each epoch, the position within the epoch -- moves the
weights if it is dropped, and moving the weights fails this test by name.

One piece is the exception and so is asserted separately: the recorded loss
history. Dropping it leaves the weights untouched and truncates
`train_log.json`, so the equality above cannot see it -- a resumed run would
report a training curve missing everything before the crash while claiming to
be the same run.

`lora_dropout` is deliberately non-zero in these tests. With dropout at 0.0 the
forward pass consumes no torch randomness, and a resume that forgot the torch
RNG entirely would still pass -- the check would be measuring nothing on the
axis it most needs to measure.
"""

import json

import pytest

from kubeagent_verdict.train.config import TrainConfig

# 8 examples x 2 epochs = 16 forward passes; grad_accum 2 => 8 optimizer steps.
# Checkpointing every 2 steps puts a checkpoint after forwards 4, 8, 12, 16.
EXAMPLES = 8
CFG = TrainConfig(epochs=2, grad_accum=2, max_seq_len=256, lora_dropout=0.05,
                  checkpoint_every=2)

# Both crash points land mid-accumulation and strictly after a checkpoint, so a
# resume must redo discarded work -- including an odd forward that leaves a
# half-accumulated gradient. A crash exactly *on* a checkpoint would discard
# nothing and would not test that.
#
# The two differ in which resume branch they reach, and only running both
# covers the loop. Checkpoints fall at steps 2 and 4, i.e. forwards 4 and 8;
# epoch 0 is forwards 1-8 and epoch 1 is 9-16.
#
#   7  -> last checkpoint is mid-epoch (epoch 0, next index 4), so the resumed
#         epoch must reuse the order it was already running
#   11 -> last checkpoint fell on the epoch boundary (epoch 0, next index 8),
#         so the resumed epoch is empty and epoch 1 draws a fresh shuffle from
#         the restored Python RNG
#
# With only the second, the `resumed_order` branch never executes.
CRASH_POINTS = [pytest.param(7, id="mid-epoch"), pytest.param(11, id="epoch-boundary")]
CRASH_AT_FORWARD = 11

ROWS = [("sys", f"user {i}", '{"verdicts": [], "summary": "ok"}')
        for i in range(EXAMPLES)]


def build_model(tokenizer):
    """A tiny randomly-initialised Qwen3 wrapped in LoRA.

    Seeded immediately before construction on purpose. `get_peft_model`
    initialises `lora_A` from the ambient torch RNG, and it does so *before*
    `run_training` ever calls `torch.manual_seed(cfg.seed)` -- so two models
    built without this seeding start from different weights, and every
    comparison below would fail for a reason that has nothing to do with
    resume.
    """
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import Qwen3Config, Qwen3ForCausalLM

    torch.manual_seed(1234)
    tiny = Qwen3ForCausalLM(Qwen3Config(
        vocab_size=len(tokenizer), hidden_size=64, num_hidden_layers=2,
        num_attention_heads=4, num_key_value_heads=2, intermediate_size=128))
    lora = LoraConfig(r=4, lora_alpha=8, lora_dropout=CFG.lora_dropout,
                      target_modules=list(CFG.target_modules), task_type="CAUSAL_LM")
    return get_peft_model(tiny, lora)


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(TrainConfig().base)


def adapter_weights(out_dir):
    """The trained tensors, keyed by name, for exact comparison."""
    from safetensors.torch import load_file

    return load_file(out_dir / "adapter_model.safetensors")


def assert_identical(a, b, why):
    import torch

    assert a.keys() == b.keys(), f"{why}: different tensor names"
    differing = [k for k in a if not torch.equal(a[k], b[k])]
    assert differing == [], (
        f"{why}: {len(differing)} of {len(a)} tensors differ, first={differing[:3]}")


def crash_at(model, nth_forward):
    """Wrap `model.forward` so the nth call raises, simulating a power loss.

    Patching the forward rather than the checkpoint writer is what makes the
    interruption land at an arbitrary point in the loop -- which is where a
    power loss actually lands. Raising from inside the checkpoint writer would
    only ever crash at a boundary where no work is pending, and would leave the
    "discarded work is correctly redone" half of resume untested.
    """
    calls = {"n": 0}
    original = model.forward

    def counting_forward(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == nth_forward:
            raise RuntimeError("simulated power loss")
        return original(*args, **kwargs)

    model.forward = counting_forward
    return calls


@pytest.mark.network
@pytest.mark.slow
@pytest.mark.parametrize("crash_forward", CRASH_POINTS)
def test_a_resumed_run_is_bit_identical_to_an_uninterrupted_one(
        tokenizer, tmp_path, crash_forward):
    from kubeagent_verdict.train import train as t

    uninterrupted = tmp_path / "uninterrupted"
    t.run_training(build_model(tokenizer), tokenizer, ROWS, CFG, uninterrupted)

    resumed = tmp_path / "resumed"
    crashed_model = build_model(tokenizer)
    crash_at(crashed_model, crash_forward)
    with pytest.raises(RuntimeError, match="simulated power loss"):
        t.run_training(crashed_model, tokenizer, ROWS, CFG, resumed)
    assert not resumed.exists(), (
        "a run that died mid-loop must not leave an adapter directory -- its "
        "presence is the signal that a run finished")

    progress = json.loads(
        (t.checkpoint_dir(resumed) / "progress.json").read_text(encoding="utf-8"))
    assert progress["optimizer_steps"] > 0
    assert progress["epochs_total"] == CFG.epochs
    assert progress["examples_per_epoch"] == EXAMPLES

    t.run_training(build_model(tokenizer), tokenizer, ROWS, CFG, resumed, resume=True)

    assert_identical(adapter_weights(uninterrupted), adapter_weights(resumed),
                     "resumed run diverged from the uninterrupted one")

    # Not implied by the weights: `losses` is carried through the checkpoint
    # and never read back into the model, so dropping it passes the check
    # above and silently truncates the training curve.
    a, b = (json.loads((d / "train_log.json").read_text(encoding="utf-8"))
            for d in (uninterrupted, resumed))
    assert a["losses"] == b["losses"], (
        f"resumed run recorded {len(b['losses'])} losses, uninterrupted "
        f"recorded {len(a['losses'])}")
    assert a["optimizer_steps"] == b["optimizer_steps"]


@pytest.mark.network
@pytest.mark.slow
def test_checkpointing_does_not_change_what_the_run_produces(tokenizer, tmp_path):
    """Default-on must be recipe-neutral.

    Checkpointing is on by default, which is only defensible if writing a
    checkpoint cannot perturb the trajectory. Saving RNG state reads it without
    consuming it -- this asserts that, rather than assuming it.
    """
    import dataclasses

    from kubeagent_verdict.train import train as t

    with_ckpt = tmp_path / "with"
    t.run_training(build_model(tokenizer), tokenizer, ROWS, CFG, with_ckpt)

    without = tmp_path / "without"
    off = dataclasses.replace(CFG, checkpoint_every=0)
    t.run_training(build_model(tokenizer), tokenizer, ROWS, off, without)

    assert_identical(adapter_weights(with_ckpt), adapter_weights(without),
                     "writing checkpoints perturbed the training trajectory")


@pytest.mark.network
@pytest.mark.slow
def test_resume_refuses_a_checkpoint_from_a_different_recipe(tokenizer, tmp_path):
    """A mismatched checkpoint must fail loudly, not train something new.

    This is the failure mode that has no downstream detector: resuming yesterday's
    checkpoint into today's dataset produces a model no scoreboard can identify as
    wrong. Refusing by name is the only place it can be caught.
    """
    import dataclasses

    from kubeagent_verdict.train import train as t

    out = tmp_path / "adapter"
    crashed_model = build_model(tokenizer)
    crash_at(crashed_model, CRASH_AT_FORWARD)
    with pytest.raises(RuntimeError, match="simulated power loss"):
        t.run_training(crashed_model, tokenizer, ROWS, CFG, out)

    other_recipe = dataclasses.replace(CFG, lr=CFG.lr * 2)
    with pytest.raises(ValueError, match="does not match"):
        t.run_training(build_model(tokenizer), tokenizer, ROWS, other_recipe, out,
                       resume=True)

    different_data = [*ROWS[:-1], ("sys", "a different last example", "{}")]
    with pytest.raises(ValueError, match="does not match"):
        t.run_training(build_model(tokenizer), tokenizer, different_data, CFG, out,
                       resume=True)


@pytest.mark.network
@pytest.mark.slow
def test_a_finished_run_leaves_no_checkpoint_behind(tokenizer, tmp_path):
    """Otherwise a later --resume silently continues a run that already ended."""
    from kubeagent_verdict.train import train as t

    out = tmp_path / "adapter"
    t.run_training(build_model(tokenizer), tokenizer, ROWS, CFG, out)

    assert not t.checkpoint_dir(out).exists(), (
        "a completed run left its checkpoint in place; a later --resume would "
        "read it instead of starting fresh")


def test_checkpointing_can_be_turned_off_from_the_command_line(monkeypatch, tmp_path):
    """`--checkpoint-every 0` must reach the config.

    The override filter this replaced was `if v`, which treats a deliberate 0
    as "not supplied" and silently leaves checkpointing on at its default. The
    flag would have appeared to work -- no error, a clean run -- while doing
    the opposite of what was asked. Fast enough to run without the model, so it
    carries no `slow` marker.
    """
    import sys

    from kubeagent_verdict.train import cli

    seen = {}
    monkeypatch.setattr(cli.data, "load_jsonl", lambda _p: [("s", "u", "a")])
    monkeypatch.setattr(cli.train, "load_model_and_tokenizer", lambda cfg: (None, None))

    def fake_run(model, tok, rows, cfg, out, resume=False):
        seen["checkpoint_every"] = cfg.checkpoint_every
        seen["resume"] = resume
        return {"examples": 1, "dropped_overlong": 0, "optimizer_steps": 1}

    monkeypatch.setattr(cli.train, "run_training", fake_run)
    monkeypatch.setattr(sys, "argv", ["kv-train", "--dataset", str(tmp_path),
                                      "--out", str(tmp_path / "a"),
                                      "--checkpoint-every", "0"])
    cli.main()
    assert seen["checkpoint_every"] == 0
    assert seen["resume"] is False

    monkeypatch.setattr(sys, "argv", ["kv-train", "--dataset", str(tmp_path),
                                      "--out", str(tmp_path / "a"), "--resume"])
    cli.main()
    assert seen["checkpoint_every"] == TrainConfig().checkpoint_every
    assert seen["resume"] is True
