from kubeagent_verdict.train.config import TrainConfig


def test_defaults_are_the_pinned_recipe():
    cfg = TrainConfig()
    assert cfg.base == "Qwen/Qwen3-0.6B"
    assert (cfg.seed, cfg.epochs, cfg.lr) == (17, 2, 2e-4)
    assert (cfg.batch_size, cfg.grad_accum, cfg.max_seq_len) == (1, 16, 4096)
    assert (cfg.lora_r, cfg.lora_alpha, cfg.lora_dropout) == (16, 32, 0.05)
    assert cfg.target_modules == ("q_proj", "k_proj", "v_proj", "o_proj",
                                  "gate_proj", "up_proj", "down_proj")
