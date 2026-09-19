"""`cases._rule_rationale` builds a rule row's rationale from the rules'
own evidence sentence, so it can never disagree with the fresh read it
describes.

Two things are checked here:

1. Every REACHABLE confirmed/unverified branch of `rules._check_node`,
   `rules._check_pvc` and `rules._check_registry` -- built from real
   `objects.Object`s, decided with the real `rules.attribute`/`decide`
   pair -- produces a rationale that `score.job1` accepts. A branch
   `rules.py` itself marks unreachable (its one `# pragma: no cover`
   default, closed by a validated `Object`) is not in this list.
2. Every valid `objects.unverify(kind, how)` ending -- the six
   (kind, how) pairs `objects.unverify` accepts -- produces evidence
   that holds no denial phrase and no overclaim word, checked with
   `score`'s own phrase lists and its own word-boundary matcher
   (`score._word_bounded_signal`), never a copy of either. This is the
   authoring rule the spec calls out by name: a failed-read message
   must not accidentally deny the very kind of object it is reporting
   on, or claim the read was verified when it was not.
"""

from __future__ import annotations

import pytest

from kubeagent_verdict.dataset import cases, render, rules
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.evals import score

# ---------------------------------------------------------- branch fixtures

_NODE = o.Object(kind="node", name="worker-1", scan_reason="NotReady",
                 placement="on", fresh=o.Fresh(how="read", ready="False"), intent="cause")
_PVC = o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
                placement="mounted", fresh=o.Fresh(how="read", phase="Pending"), intent="cause")
_REGISTRY = o.Object(kind="registry", name="registry.example.com", scan_reason="2",
                     placement="", fresh=o.Fresh(how="read", literal="dial tcp"), intent="cause")


def _decide(obj: o.Object, *, issue: str = "CrashLoopBackOff") -> rules.Result:
    candidates = rules.attribute((obj,), ns="payments", pod="worker-0", issue=issue)
    return rules.decide(candidates)


# (id, Result-producing object, issue) -- one entry per reachable branch.
NODE_BRANCHES = [
    ("node-confirmed-missing",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="missing"), intent="cause")),
    ("node-confirmed-false",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="False"), intent="cause")),
    ("node-confirmed-unknown",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="read", ready="Unknown"), intent="cause")),
    ("node-unverified-read-failed", o.unverify(_NODE, "read_failed")),
    ("node-unverified-not-read",
     o.Object(kind="node", name="worker-1", scan_reason="NotReady", placement="on",
              fresh=o.Fresh(how="not_read"), intent="cause")),
    ("node-unverified-lease", o.unverify(_NODE, "lease")),
]

PVC_BRANCHES = [
    ("pvc-confirmed-pending",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Pending"), intent="cause")),
    ("pvc-confirmed-lost",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Lost"), intent="cause")),
    ("pvc-unverified-read-failed", o.unverify(_PVC, "read_failed")),
    ("pvc-unverified-not-read",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="not_read"), intent="cause")),
    ("pvc-unverified-unexpected-phase",
     o.Object(kind="pvc", name="data-0", scan_reason="ProvisionerNotResponding",
              placement="mounted", fresh=o.Fresh(how="read", phase="Released"), intent="cause")),
]

REGISTRY_BRANCHES = [
    ("registry-confirmed-connection",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", literal="dial tcp"), intent="cause")),
    ("registry-unverified-read-failed", o.unverify(_REGISTRY, "read_failed")),
    ("registry-unverified-not-read",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="not_read"), intent="cause")),
    ("registry-unverified-wrong-pod",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", wrong_pod=True, literal=""), intent="cause")),
    ("registry-unverified-no-literal",
     o.Object(kind="registry", name="registry.example.com", scan_reason="2",
              placement="", fresh=o.Fresh(how="read", literal=""), intent="cause")),
    ("registry-unverified-auth", o.unverify(_REGISTRY, "auth")),
]

ALL_BRANCHES = (
    [(i, obj, "CrashLoopBackOff") for i, obj in NODE_BRANCHES]
    + [(i, obj, "CrashLoopBackOff") for i, obj in PVC_BRANCHES]
    + [(i, obj, "ImagePullBackOff") for i, obj in REGISTRY_BRANCHES]
)


@pytest.mark.parametrize("case_id,obj,issue", ALL_BRANCHES, ids=[c[0] for c in ALL_BRANCHES])
def test_rule_rationale_passes_job1_on_every_reachable_branch(case_id, obj, issue):
    result = _decide(obj, issue=issue)
    assert result.decided, case_id
    rationale = cases._rule_rationale(result)
    meta = render.workload_meta(result, expected_cause=result.cause, own_cause_keywords=[])
    reply_row = {"cause": result.cause, "rationale": rationale}
    assert score.job1(meta, reply_row) == 1.0, (case_id, rationale)


# --------------------------------------------------- objects.unverify authoring rule

# Every valid (kind, how) pair `objects.unverify` accepts, built from a
# minimal starting object of that kind. `_decide` re-checks it exactly the
# way a rule row would, so the evidence text is the same text
# `_rule_rationale` would embed.
UNVERIFY_CASES = [
    ("node/read_failed", _NODE, "read_failed", "CrashLoopBackOff"),
    ("node/lease", _NODE, "lease", "CrashLoopBackOff"),
    ("pvc/read_failed", _PVC, "read_failed", "CrashLoopBackOff"),
    ("registry/read_failed", _REGISTRY, "read_failed", "ImagePullBackOff"),
    ("registry/auth", _REGISTRY, "auth", "ImagePullBackOff"),
    ("registry/no_event", _REGISTRY, "no_event", "ImagePullBackOff"),
]


@pytest.mark.parametrize("case_id,base,how,issue", UNVERIFY_CASES,
                         ids=[c[0] for c in UNVERIFY_CASES])
def test_every_valid_unverify_message_holds_no_denial_or_overclaim_phrase(
        case_id, base, how, issue):
    ended = o.unverify(base, how)
    result = _decide(ended, issue=issue)
    assert result.decided and result.outcome == "unverified", case_id
    kind = ended.kind
    assert not score._word_bounded_signal(result.evidence, score.DENIAL_PHRASES.get(kind, ())), (
        case_id, result.evidence)
    assert not score._word_bounded_signal(result.evidence, score.OVERCLAIM_WORDS), (
        case_id, result.evidence)
