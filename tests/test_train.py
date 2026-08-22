import pytest

from kubeagent_verdict.train.config import TrainConfig


@pytest.mark.network
@pytest.mark.slow
def test_one_pass_on_a_tiny_random_model(tmp_path):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM

    from kubeagent_verdict.train import train as t

    cfg = TrainConfig(epochs=1, grad_accum=2, max_seq_len=256)
    tok = AutoTokenizer.from_pretrained(cfg.base)  # tokenizer only — a few MB
    tiny = Qwen3ForCausalLM(Qwen3Config(
        vocab_size=len(tok), hidden_size=64, num_hidden_layers=2,
        num_attention_heads=4, num_key_value_heads=2, intermediate_size=128))
    lora = LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0,
                      target_modules=list(cfg.target_modules), task_type="CAUSAL_LM")
    model = get_peft_model(tiny, lora)

    rows = [("sys", f"user {i}", '{"verdicts": [], "summary": "ok"}') for i in range(4)]
    log = t.run_training(model, tok, rows, cfg, tmp_path / "adapter")
    assert log["examples"] == 4
    assert log["optimizer_steps"] >= 1
    assert all(x == x for x in log["losses"])  # finite, no NaN  # noqa: PLR0124
    assert (tmp_path / "adapter" / "train_log.json").exists()
    assert (tmp_path / "adapter" / "adapter_config.json").exists()
