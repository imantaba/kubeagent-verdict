"""The synthetic-name allowlist: the ONLY identifier vocabulary examples may use.

Everything here is deliberately fictional (RFC 2606 registry domain,
generic node/namespace names). The provenance test in test_generate.py
enforces that no generated example carries an identifier outside these
pools, which is what makes "no live identifier in any tracked file"
checkable rather than aspirational.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

NAMESPACES = ("shop", "web", "payments", "billing", "search", "auth", "media", "batch", "data", "edge")
NAMES = ("api", "frontend", "worker", "cache", "ingest", "checkout", "gateway", "scheduler", "indexer", "notifier")
CONTAINERS = ("app", "web", "worker", "main")
INIT_CONTAINERS = ("init-config", "init-migrate")
NODES = ("worker-1", "worker-2", "worker-3")
PVCS = ("data-0", "cache-0", "media-assets")
DNS_NAMESPACE = "kube-system"  # fixed pair for the CoreDNS entries
DNS_NAME = "coredns"

_HEX = "0123456789abcdef"
_SUFFIX = "abcdefghijklmnopqrstuvwxyz0123456789"


@dataclass(frozen=True)
class Names:
    ns: str
    name: str
    pod: str
    container: str
    init_container: str
    image: str
    node: str
    pvc: str
    restarts: int


def pod_name(rng: random.Random, name: str) -> str:
    mid = "".join(rng.choice(_HEX) for _ in range(9))
    tail = "".join(rng.choice(_SUFFIX) for _ in range(5))
    return f"{name}-{mid}-{tail}"


def draw(rng: random.Random) -> Names:
    ns = rng.choice(NAMESPACES)
    name = rng.choice(NAMES)
    return Names(
        ns=ns, name=name, pod=pod_name(rng, name),
        container=rng.choice(CONTAINERS), init_container=rng.choice(INIT_CONTAINERS),
        image=f"registry.example.com/{ns}/{name}:v{rng.randint(1, 3)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}",
        node=rng.choice(NODES), pvc=rng.choice(PVCS), restarts=rng.randint(1, 40),
    )
