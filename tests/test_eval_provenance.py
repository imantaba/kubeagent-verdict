"""A scoreboard has to say what it scored.

The release argument is two scoreboards side by side. Without this block the
directories are distinguishable only by name, and `--endpoint`'s Ollama
default makes the confusable case a realistic one rather than a contrived
one.
"""

from pathlib import Path

from kubeagent_verdict.evals import score
from kubeagent_verdict.evals.cli import provenance


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
