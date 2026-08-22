from kubeagent_verdict.export import modelfile
from kubeagent_verdict.train import data


def test_modelfile_bytes_are_pinned():
    assert modelfile.modelfile_text(modelfile.GGUF_NAME) == (
        "FROM ./kubeagent-verdict-0.6b-q8_0.gguf\n"
        'TEMPLATE """{{- range .Messages }}<|im_start|>{{ .Role }}\n'
        "{{ .Content }}<|im_end|>\n"
        '{{ end }}<|im_start|>assistant\n"""\n'
        "PARAMETER stop <|im_end|>\n"
        "PARAMETER temperature 0\n"
        "PARAMETER num_ctx 32768\n"
    )


def _expand_ollama(messages):
    """Mimic what Ollama's Go template engine renders for OLLAMA_TEMPLATE."""
    out = ""
    for m in messages:
        out += f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n"
    return out + "<|im_start|>assistant\n"


def test_serving_template_matches_training_format():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    assert _expand_ollama(msgs) == data.prompt_prefix("S", "U")


def test_sha256sums_format(tmp_path):
    a = tmp_path / "a.bin"
    a.write_bytes(b"hello")
    out = modelfile.sha256sums([a])
    line = out.splitlines()[0]
    digest, name = line.split("  ")
    assert name == "a.bin"
    assert len(digest) == 64 and out.endswith("\n")
