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
# Five nodes, so a multi row can put each of its up to four workloads on a
# node of its own and still find a free node for a healthy node read.
NODES = ("worker-1", "worker-2", "worker-3", "worker-4", "worker-5")
PVCS = ("data-0", "cache-0", "media-assets")
# A fixed decoy-PVC pool, never drawn by the rng. No catalog entry names
# one, so a pad never collides with a drawn {pvc}, and every pad sorts
# before every drawn PVC, so in the rules' trace a pad comes first. Three
# builders use them: `attributed` adds an unmounted aux-0 on a coin;
# `positional_probe` puts a mounted, refuted aux-0 ahead of a claim winner;
# and `truncated` appends all nine, unmounted, to push a claim winner past
# the 8-candidate cap (render.PAD_PVC_OBJECTS).
PAD_PVCS = ("aux-0", "aux-1", "aux-2", "aux-3", "aux-4", "aux-5",
            "aux-6", "aux-7", "aux-8")
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
    nodes: int = 3


def pod_name(rng: random.Random, name: str) -> str:
    mid = "".join(rng.choice(_HEX) for _ in range(9))
    tail = "".join(rng.choice(_SUFFIX) for _ in range(5))
    return f"{name}-{mid}-{tail}"


def draw(rng: random.Random, *, min_restarts: int = 1) -> Names:
    """Draw one row's names. `restarts` is drawn from min_restarts..40, last,
    so a different floor changes no other field of the same draw."""
    ns = rng.choice(NAMESPACES)
    name = rng.choice(NAMES)
    return Names(
        ns=ns, name=name, pod=pod_name(rng, name),
        container=rng.choice(CONTAINERS), init_container=rng.choice(INIT_CONTAINERS),
        image=f"registry.example.com/{ns}/{name}:v{rng.randint(1, 3)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}",
        node=rng.choice(NODES), pvc=rng.choice(PVCS), restarts=rng.randint(min_restarts, 40),
    )
