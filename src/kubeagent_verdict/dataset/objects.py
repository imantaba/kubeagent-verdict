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
    ready_reason: str = ""     # node: the Ready=False condition's reason (NOT_READY_REASON)
    ready_message: str = ""    # node: the Ready=False condition's message (NOT_READY_MESSAGE)
    unschedulable: bool = False
    disk_pressure: bool = False  # node: the kubelet reports DiskPressure=True
    taints: tuple[tuple[str, str, str], ...] = ()  # node: (key, value, effect), in order
    phase: str = ""            # pvc: Bound | Pending | Lost | anything else
    storage_class: str = ""
    volume: str = ""
    literal: str = ""          # registry: one of PULL_LITERALS, or "" for no event
    wrong_pod: bool = False    # registry: the events read hit a different pod


# The one Ready=False story the dataset tells: the kubelet reports
# KubeletNotReady because the container runtime is down. This is the
# kubelet's own fixed text for that case (kubelet pkg/kubelet/runtime.go:129).
# Every NotReady node object carries it, and the node describe and the
# cluster-health block both read it from here.
NOT_READY_REASON = "KubeletNotReady"
NOT_READY_MESSAGE = "container runtime is down"
NODE_NOT_READY = Fresh(ready="False", ready_reason=NOT_READY_REASON,
                       ready_message=NOT_READY_MESSAGE)
# A node whose kubelet stopped posting status: the node lifecycle controller
# marks it Ready=Unknown (rules._node_conditions prints its text).
NODE_UNKNOWN = Fresh(ready="Unknown")


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
        if (f.ready_reason or f.ready_message) and f.ready != "False":
            raise _err(obj, "ready_reason and ready_message are only for a Ready=False node")
        if f.disk_pressure and f.ready == "missing":
            raise _err(obj, "disk_pressure needs a node that reports conditions")
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
    """The healthy ending: the fresh read says the object is fine.

    A node comes back Ready, so its Ready=False text goes. Its cordon, disk
    pressure and taints stay: they are not what the NotReady scan reason
    claimed.
    """
    if obj.kind == "node":
        return replace(obj, scan_reason="NotReady",
                       fresh=replace(obj.fresh, how="read", message="", ready="True",
                                     ready_reason="", ready_message=""))
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
                       fresh=replace(obj.fresh, how="read", message="", ready="True",
                                     ready_reason="", ready_message=""))
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
