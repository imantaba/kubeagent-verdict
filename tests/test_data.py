from kubeagent_verdict.train import data


class DummyTok:
    """Byte-per-token tokenizer: makes masking arithmetic exactly checkable."""

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(ch) for ch in text]}


def test_prompt_prefix_is_explicit_chatml():
    got = data.prompt_prefix("S", "U")
    assert got == ("<|im_start|>system\nS<|im_end|>\n"
                   "<|im_start|>user\nU<|im_end|>\n"
                   "<|im_start|>assistant\n")


def test_full_text_appends_assistant_and_end():
    assert data.full_text("S", "U", "A") == data.prompt_prefix("S", "U") + "A<|im_end|>"


def test_encode_masks_exactly_the_prompt():
    tok = DummyTok()
    ids, labels = data.encode_example(tok, "S", "U", "ANSWER", max_len=4096)
    prompt = data.prompt_prefix("S", "U")
    assert len(ids) == len(labels)
    assert labels[:len(prompt)] == [-100] * len(prompt)
    tail = labels[len(prompt):]
    assert tail == [ord(ch) for ch in "ANSWER" + data.IM_END]
    assert ids[:len(prompt)] == [ord(ch) for ch in prompt]  # prefix by construction


def test_encode_drops_overlong():
    assert data.encode_example(DummyTok(), "S", "U", "A" * 5000, max_len=64) is None


def test_load_jsonl_roundtrip(tmp_path):
    import json

    row = {"messages": [{"role": "system", "content": "s"},
                        {"role": "user", "content": "u"},
                        {"role": "assistant", "content": "a"}], "meta": {}}
    p = tmp_path / "train.jsonl"
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert data.load_jsonl(p) == [("s", "u", "a")]
