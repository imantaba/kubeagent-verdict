"""Minimal OpenAI-compatible chat client over stdlib urllib.

Talks to whatever serves /v1/chat/completions — llama-server or Ollama.
DEFAULT_ENDPOINT is local, but `--endpoint` accepts any host, so this can
reach a remote API; that is the caller's choice, not a restriction here.
temperature 0 always: the eval measures the model, not sampling.
"""

from __future__ import annotations

import json
import urllib.request

DEFAULT_ENDPOINT = "http://localhost:11434/v1"


def chat(endpoint: str, model: str, messages: list[dict], timeout: float = 300.0) -> str:
    url = endpoint.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages,
                       "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]
