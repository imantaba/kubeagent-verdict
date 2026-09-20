"""Declared objects: the nodes, PVCs and registries a story puts on the menu.

An Object says what kubeagent's scan saw (scan_reason, placement) and what
its fresh read finds (Fresh). rules.py turns a tuple of Objects into the
candidate list and the decision kubeagent v1.24.0 prints. Every value is
from a closed table; anything else raises ValueError naming the object.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

KINDS = ("node", "pvc", "registry")
NODE_SCAN_REASONS = ("NotReady", "no kubelet lease", "kubelet not heartbeating")
PVC_SCAN_REASONS = (
    "ProvisioningFailed", "FailedBinding", "MissingStorageClass",
    "NoMatchingPV", "PVSelectorMismatch", "ProvisionerNotResponding",
)
NODE_PLACEMENTS = ("on", "off")
PVC_PLACEMENTS = ("mounted", "unmounted")
NODE_READY = ("True", "False", "Unknown", "missing")
FRESH_HOW = ("read", "read_failed", "not_read")
INTENTS = ("cause", "decoy")

# Copied verbatim from kubeagent internal/hypothesis/decide.go at v1.24.0.
CONNECTION_LITERALS = (
    "dial tcp", "i/o timeout", "connection refused", "connection reset",
    "no such host", "network is unreachable", "tls handshake", "x509:",
    "502 bad gateway", "503 service unavailable", "504 gateway timeout",
    "toomanyrequests", "429 too many requests",
)
AUTH_LITERALS = ("pull access denied", "no basic auth credentials", "unauthorized", "denied")
IMAGE_LITERALS = (
    "manifest unknown", "not found", "name unknown",
    "repository does not exist", "invalid reference format",
)
PULL_LITERALS = CONNECTION_LITERALS + AUTH_LITERALS + IMAGE_LITERALS


@dataclass(frozen=True)
class Fresh:
    """What the fresh read finds.

    The fields are grouped by kind, and the reader for a kind reads only its
    own group. Nothing enforces the grouping except `wrong_pod`, which
    `validate` refuses on a non-registry. A node carrying `phase` is a valid
    `Object`; the node readers just never look at it.
    """

    how: str = "read"          # read | read_failed | not_read
    message: str = ""          # the failed-read message, when how == read_failed
    ready: str = ""            # node: True | False | Unknown | missing
    unschedulable: bool = False
    extra: tuple[str, ...] = ()  # node: extra condition/taint lines, gather format
    phase: str = ""            # pvc: Bound | Pending | Lost | anything else
    storage_class: str = ""
    volume: str = ""
    literal: str = ""          # registry: one of PULL_LITERALS, or "" for no event
    wrong_pod: bool = False    # registry: the events read hit a different pod


@dataclass(frozen=True)
class Object:
    kind: str
    name: str
    scan_reason: str
    placement: str
    fresh: Fresh
    intent: str = "decoy"

    def __post_init__(self) -> None:
        validate(self)


def _err(obj: Object, what: str) -> ValueError:
    return ValueError(f"object {obj.kind}/{obj.name}: {what}")


def validate(obj: Object) -> None:
    f = obj.fresh
    if obj.kind not in KINDS:
        raise _err(obj, f"kind must be one of {KINDS}")
    if obj.intent not in INTENTS:
        raise _err(obj, f"intent must be one of {INTENTS}")
    if f.how not in FRESH_HOW:
        raise _err(obj, f"how must be one of {FRESH_HOW}")
    if f.how == "read_failed" and not f.message:
        raise _err(obj, "read_failed needs a message")
    if f.wrong_pod and obj.kind != "registry":
        raise _err(obj, "wrong_pod is only for a registry")
    if obj.kind == "node":
        if obj.scan_reason not in NODE_SCAN_REASONS:
            raise _err(obj, f"scan_reason must be one of {NODE_SCAN_REASONS}")
        if obj.placement not in NODE_PLACEMENTS:
            raise _err(obj, f"placement must be one of {NODE_PLACEMENTS}")
        if f.how == "read" and f.ready not in NODE_READY:
            raise _err(obj, f"ready must be one of {NODE_READY}")
    elif obj.kind == "pvc":
        if obj.scan_reason not in PVC_SCAN_REASONS:
            raise _err(obj, f"scan_reason must be one of {PVC_SCAN_REASONS}")
        if obj.placement not in PVC_PLACEMENTS:
            raise _err(obj, f"placement must be one of {PVC_PLACEMENTS}")
        if f.how == "read" and not f.phase:
            raise _err(obj, "phase must be set on a read PVC")
    else:
        if obj.scan_reason != "{count}" and not obj.scan_reason.isdigit():
            raise _err(obj, "scan_reason must be the count of workloads failing to "
                            'pull, or the "{count}" template filled in at render time')
        if obj.placement != "":
            raise _err(obj, "placement must be empty on a registry")
        if f.how == "read" and f.literal and f.literal not in PULL_LITERALS:
            raise _err(obj, "literal must be one of the pull literals or empty")


def refute(obj: Object) -> Object:
    """The healthy ending: the fresh read says the object is fine."""
    if obj.kind == "node":
        return replace(obj, scan_reason="NotReady",
                       fresh=replace(obj.fresh, how="read", message="", ready="True"))
    if obj.kind == "pvc":
        return replace(obj, fresh=replace(obj.fresh, how="read", message="", phase="Bound"))
    return replace(obj, fresh=replace(obj.fresh, how="read", message="",
                                      literal="manifest unknown", wrong_pod=False))


def unverify(obj: Object, how: str) -> Object:
    """An ending the rules cannot settle: the object stays decided but unverified."""
    if how == "read_failed":
        message = {
            "node": f'nodes "{obj.name}" is forbidden',
            "pvc": f'persistentvolumeclaims "{obj.name}" is forbidden',
            "registry": "events is forbidden",
        }[obj.kind]
        return replace(obj, fresh=Fresh(how="read_failed", message=message))
    if obj.kind == "node" and how == "lease":
        return replace(obj, scan_reason="no kubelet lease",
                       fresh=replace(obj.fresh, how="read", message="", ready="True"))
    if obj.kind == "registry" and how == "auth":
        return replace(obj, fresh=replace(obj.fresh, how="read", message="",
                                          literal="unauthorized", wrong_pod=False))
    if obj.kind == "registry" and how == "no_event":
        return replace(obj, fresh=replace(obj.fresh, how="read", message="",
                                          literal="", wrong_pod=False))
    raise _err(obj, f"cannot unverify a {obj.kind} by {how!r}")


def drop(objects: tuple[Object, ...], obj: Object) -> tuple[Object, ...]:
    return tuple(o for o in objects if o != obj)


def check_objects(entry_key: str, objects: tuple[Object, ...]) -> None:
    seen: set[str] = set()
    for obj in objects:
        try:
            validate(obj)
        except ValueError as err:
            raise ValueError(f"entry {entry_key}: {err}") from None
        key = f"{obj.kind}/{obj.name}"
        if key in seen:
            raise ValueError(f"entry {entry_key}: object {key} is declared twice")
        seen.add(key)
