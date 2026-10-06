"""Every service line in a build is one kubeagent's svchealth can print
(exam rebuild, item 9). The type in the brackets is the Service type. The
detail is one of svchealth's forms. The contract golden and the Go
fixtures are not built rows, so they keep their old line."""

from __future__ import annotations

import re

import pytest

from kubeagent_verdict.dataset import cases, catalog, generate, health
from kubeagent_verdict.dataset.names import Names

_LINE = re.compile(r"^  - (\S+)/(\S+) \(([^)]*)\): (.*)$")
_TYPES = ("ClusterIP", "NodePort", "LoadBalancer")
_DETAIL = re.compile(
    r"^(no external address|no ready endpoints"
    r"|no ready endpoints — declared via kubeagent\.io/expected-empty"
    r"|no ready endpoints \(backs (CronJob|Job) — expected between runs\)"
    r"|no ready endpoints \(backs DaemonSet — 0 desired\)"
    r"|no ready endpoints \(backs (Deployment|StatefulSet) — scaled to 0\)"
    r"|no ready endpoints — (the selector matches no pods"
    r"|matching pods on down node \S+ \(.+\)|matching pods on \d+ down nodes"
    r"|\d+ matching pods?, 0 ready))$")


def _service_lines(user: str) -> list[str]:
    lines = user.split("\n")
    if "Service issues:" not in lines:
        return []
    out = []
    for ln in lines[lines.index("Service issues:") + 1:]:
        if not ln.startswith("  - "):
            break
        out.append(ln)
    return out


@pytest.fixture(scope="module")
def built_rows() -> list[dict]:
    return [generate.to_row(ex) for ex in generate.generate(17, 8000)] + \
           [generate.to_row(ex) for ex in generate.test_set()]


def test_every_built_service_line_is_one_svchealth_prints(built_rows):
    seen = 0
    for row in built_rows:
        for ln in _service_lines(row["messages"][1]["content"]):
            seen += 1
            m = _LINE.match(ln)
            assert m, ln
            _ns, _name, typ, detail = m.groups()
            assert typ in _TYPES, ln
            assert _DETAIL.match(detail), ln
            if detail == "no external address":
                assert typ == "LoadBalancer", ln
    assert seen > 0


def test_the_probe_failure_entry_names_a_service_type():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    assert e.service_type == "ClusterIP"


def _names():
    return Names(ns="shop", name="api", pod="api-7d9", container="api",
                 init_container="init", image="shop/api:1.0", node="worker-1",
                 pvc="data", restarts=5)


def test_a_service_on_a_live_node_says_2_matching_pods_0_ready():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    (issue,) = cases._service_issues(e, _names(), ())
    assert (issue.type, issue.detail) == ("ClusterIP", "no ready endpoints — 2 matching pods, 0 ready")


def test_a_service_on_a_down_node_names_the_node():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    (issue,) = cases._service_issues(e, _names(), (health.DownNode("worker-1", "NotReady"),))
    assert issue.detail == "no ready endpoints — matching pods on down node worker-1 (NotReady)"
