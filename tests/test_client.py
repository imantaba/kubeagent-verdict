import io
import json

from kubeagent_verdict.evals import client


def test_chat_builds_the_request(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        reply = {"choices": [{"message": {"content": "OUT"}}]}
        return io.BytesIO(json.dumps(reply).encode("utf-8"))

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    out = client.chat("http://localhost:8080/v1", "kubeagent-verdict",
                      [{"role": "user", "content": "hi"}])
    assert out == "OUT"
    assert captured["url"] == "http://localhost:8080/v1/chat/completions"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["model"] == "kubeagent-verdict"
