from kubeagent_verdict.export import export


def test_export_chain_commands(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(export, "run_cmd", lambda cmd, cwd=None: calls.append((cmd, cwd)))
    monkeypatch.setattr(export, "merge_adapter", lambda base, adapter, merged: merged.mkdir(parents=True))

    out = tmp_path / "dist"
    # Pre-create the fake artifact: run_cmd is stubbed, so quantize never
    # writes it, but export_all's final packaging step hashes its bytes.
    out.mkdir()
    (out / "kubeagent-verdict-0.6b-q8_0.gguf").write_bytes(b"fake gguf bytes")
    gguf = export.export_all(base="Qwen/Qwen3-0.6B",
                             adapter_dir=tmp_path / "adapter",
                             workdir=tmp_path / "work", out_dir=out)
    joined = [" ".join(str(part) for part in cmd) for cmd, _ in calls]

    clone = next(cl for cl in joined if "clone" in cl)
    assert f"--branch {export.LLAMA_CPP_TAG}" in clone and "--depth 1" in clone
    assert any("convert_hf_to_gguf.py" in cl for cl in joined)
    assert any("llama-quantize" in cl and cl.endswith("Q8_0") for cl in joined)
    assert any("llama-cli" in cl for cl in joined)  # load-verify step
    assert gguf == out / "kubeagent-verdict-0.6b-q8_0.gguf"


def test_write_release_files(tmp_path):
    gguf = tmp_path / "kubeagent-verdict-0.6b-q8_0.gguf"
    gguf.write_bytes(b"fake gguf bytes")
    export.write_release_files(tmp_path, gguf)
    assert (tmp_path / "Modelfile").read_text().startswith("FROM ./kubeagent-verdict")
    sums = (tmp_path / "SHA256SUMS").read_text()
    assert "kubeagent-verdict-0.6b-q8_0.gguf" in sums and "Modelfile" in sums
