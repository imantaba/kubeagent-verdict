"""A scoreboard has to say what it scored.

The release argument is two scoreboards side by side. Without this block the
directories are distinguishable only by name, and `--endpoint`'s Ollama
default makes the confusable case a realistic one rather than a contrived
one.
"""

import json
from pathlib import Path

from kubeagent_verdict.evals import score
from kubeagent_verdict.evals.cli import dataset_provenance, provenance

ENDPOINT = "http://127.0.0.1:8080/v1"


def _manifest(dirpath: Path, **fields) -> Path:
    """Write a manifest.json beside a test.jsonl; return the test path.

    The defaults are out/dataset/manifest.json's real shape, so a test that
    overrides one field varies exactly what it says it varies.
    """
    m = {"seed": 17, "size": 5500, "train": 4155, "val": 432, "test": 253,
         "corpus_files": ["chaos-corpus-v1.34-kind.jsonl"]}
    m.update(fields)
    (dirpath / "manifest.json").write_text(
        json.dumps(m, indent=2) + "\n", encoding="utf-8")
    test = dirpath / "test.jsonl"
    test.write_text("", encoding="utf-8")
    return test


def _bare(dirpath: Path, manifest_text: str | None = None) -> Path:
    if manifest_text is not None:
        (dirpath / "manifest.json").write_text(manifest_text, encoding="utf-8")
    test = dirpath / "test.jsonl"
    test.write_text("", encoding="utf-8")
    return test


def _run(test: Path) -> dict:
    return provenance("m", ENDPOINT, test, 253, 253,
                      dataset=dataset_provenance(test))


def test_records_what_was_scored():
    p = provenance("kubeagent-verdict", "http://127.0.0.1:8080/v1",
                   Path("out/dataset/test.jsonl"), 243, 243)
    assert p == {
        "model": "kubeagent-verdict",
        "endpoint": "http://127.0.0.1:8080/v1",
        "test_file": "test.jsonl",
        "rows_scored": 243,
        "rows_available": 243,
        "limited": False,
        "dataset": None,
    }


def test_a_limited_run_says_so():
    p = provenance("m", "http://localhost:11434/v1", Path("t.jsonl"), 40, 243)
    assert p["limited"] and p["rows_scored"] == 40 and p["rows_available"] == 243


def test_model_path_is_reduced_to_a_basename():
    """`/home/` is one of the five shapes the provenance denylist catches."""
    p = provenance("/home/someone/git/kubeagent-verdict/dist/kv-0.6b-q8_0.gguf",
                   "http://127.0.0.1:8080/v1", Path("t.jsonl"), 1, 1)
    assert p["model"] == "kv-0.6b-q8_0.gguf"
    assert "/home/" not in p["model"]


def test_endpoint_userinfo_is_dropped():
    p = provenance("m", "https://user:sekrit@api.example.com:443/v1",
                   Path("t.jsonl"), 1, 1)
    assert p["endpoint"] == "https://api.example.com:443/v1"
    assert "sekrit" not in p["endpoint"] and "user" not in p["endpoint"]


def test_two_endpoints_that_differ_stay_distinguishable():
    """The reduction must not collapse the mistake it exists to catch."""
    llama = provenance("m", "http://127.0.0.1:8080/v1", Path("t.jsonl"), 1, 1)
    ollama = provenance("m", "http://localhost:11434/v1", Path("t.jsonl"), 1, 1)
    assert llama["endpoint"] != ollama["endpoint"]


def test_markdown_render_ignores_the_new_key():
    """`render_markdown` reads `overall` and `by_case`; `run` must not disturb it."""
    board = score.scoreboard([])
    before = score.render_markdown(board)
    board["run"] = provenance("m", "http://127.0.0.1:8080/v1", Path("t.jsonl"), 0, 0)
    assert score.render_markdown(board) == before


def test_two_seeds_produce_distinguishable_run_blocks(tmp_path):
    """The defect this block exists to close.

    A retrain overwrites `out/dataset/test.jsonl` in place. Every other field
    of `run` is a property of the serving side — model, endpoint, row counts —
    and `test_file` is the basename, which does not change. So two scoreboards
    scored against two different datasets were byte-identical in the one block
    that claims to say what was scored, and the release argument compares two
    numbers whose denominators it cannot prove are the same rows.
    """
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    one, two = _run(_manifest(a, seed=17)), _run(_manifest(b, seed=23))
    assert one != two
    assert one["dataset"]["seed"] == 17
    assert two["dataset"]["seed"] == 23


def test_the_hash_covers_fields_the_block_does_not_name(tmp_path):
    """Two manifests agreeing on all four named fields still differ.

    The block names four scalars; the hash is over the whole file. That is
    what lets the block stay a short list of paths-free scalars without the
    guarantee narrowing to those four.
    """
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    one = _run(_manifest(a, corpus_files=["chaos-corpus-v1.34-kind.jsonl"]))
    two = _run(_manifest(b, corpus_files=["chaos-corpus-v1.34-kind.jsonl",
                                          "chaos-corpus-v1.35-k3s.jsonl"]))
    d1, d2 = one["dataset"], two["dataset"]
    assert (d1["seed"], d1["size"], d1["test_rows"]) == \
           (d2["seed"], d2["size"], d2["test_rows"])
    assert d1["manifest_sha256"] != d2["manifest_sha256"]


def test_the_dataset_block_carries_no_path(tmp_path):
    """`corpus_files` holds basenames today; nothing enforces that it always will.

    The block names four scalars and never copies a manifest string, so a path
    that appeared there could not reach the scoreboard even so. A file whose
    corpus list is absolute still hashes to something distinguishable.
    """
    test = _manifest(tmp_path, corpus_files=["/home/someone/out/corpus.jsonl"])
    d = dataset_provenance(test)
    assert "/home/" not in json.dumps(d)
    assert len(d["manifest_sha256"]) == 64


def test_no_manifest_is_not_an_error(tmp_path):
    """A hand-made `--test` file has no manifest. That is a null, not a failure."""
    assert dataset_provenance(_bare(tmp_path)) is None


def test_an_unparseable_manifest_is_not_an_error(tmp_path):
    assert dataset_provenance(_bare(tmp_path, "{not json")) is None


def test_a_manifest_that_is_not_an_object_is_not_an_error(tmp_path):
    """Valid JSON, wrong shape — `.get` would raise. Refuse instead."""
    assert dataset_provenance(_bare(tmp_path, "[1, 2, 3]")) is None


def test_a_manifest_missing_a_field_reports_it_absent(tmp_path):
    d = dataset_provenance(_bare(tmp_path, '{"size": 10}'))
    assert d["seed"] is None
    assert d["size"] == 10
    assert d["test_rows"] is None
    assert len(d["manifest_sha256"]) == 64


def test_the_hash_is_over_the_bytes_on_disk(tmp_path):
    import hashlib
    test = _manifest(tmp_path)
    raw = (tmp_path / "manifest.json").read_bytes()
    assert dataset_provenance(test)["manifest_sha256"] == \
        hashlib.sha256(raw).hexdigest()


def test_markdown_render_ignores_the_dataset_block(tmp_path):
    """`run` is provenance, not a score. Neither half may reach the table."""
    board = score.scoreboard([])
    before = score.render_markdown(board)
    board["run"] = _run(_manifest(tmp_path))
    assert score.render_markdown(board) == before


def test_a_non_integer_field_is_dropped_rather_than_copied(tmp_path):
    """The three named values are integers or absent — never arbitrary strings.

    That is what makes "this block cannot carry a path" structural rather than
    a property of what the generator happens to write today. Identity is not
    lost: the hash still separates the two files.
    """
    a = dataset_provenance(_bare(tmp_path, '{"seed": "/home/someone/seed"}'))
    assert a["seed"] is None
    assert "/home/" not in json.dumps(a)


def test_a_boolean_is_not_a_count(tmp_path):
    """`isinstance(True, int)` is true in Python; a flag is still not a seed."""
    d = dataset_provenance(_bare(tmp_path, '{"seed": true, "size": 5500}'))
    assert d["seed"] is None
    assert d["size"] == 5500
