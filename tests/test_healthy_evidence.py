"""A healthy-world finding must not say the origin is broken.

A twin pair swaps the reads and keeps the inventory fixed. That is fine when a
victim's finding is a local symptom that reads the same either way. It is
wrong when the finding's own evidence names the origin's fact: the healthy
half then carries a finding that says the origin is broken, a read that says
it is fine, and a label that says "separate". The node-disk-pressure decoy did
exactly that -- `untolerated taint node.kubernetes.io/disk-pressure` in the
inventory of a prompt whose node read shows no taint at all -- and the model
believed the inventory. `Victim.healthy_evidence` is the fix: the same
finding's evidence in the world where the origin is fine, rendered only by
the healthy half, the way `healthy_read_content` already works for reads.
"""

import random

from kubeagent_verdict.dataset import cases
from kubeagent_verdict.dataset import propagation as prop

TAINT = "node.kubernetes.io/disk-pressure"
EVIDENCE_MARK = "== BEGIN evidence =="


def _scenario(key: str) -> prop.Propagation:
    return next(p for p in prop.all_scenarios() if p.key == key)


def _before_reads(user: str) -> str:
    """The inventory and candidate sections: everything a pair holds fixed."""
    return user.split(EVIDENCE_MARK)[0]


def _reads(user: str) -> str:
    return user.split(EVIDENCE_MARK)[1]


def _pair(p: prop.Propagation) -> tuple[cases.Example, cases.Example]:
    return (cases.shared_origin_probe(p, random.Random(7)),
            cases.shared_origin_decoy_probe(p, random.Random(7)))


def test_the_one_victim_whose_evidence_names_the_origin_has_a_healthy_twin():
    v = _scenario("node-disk-pressure").victims[0]
    assert TAINT in v.evidence
    assert v.healthy_evidence
    assert TAINT not in v.healthy_evidence


def test_the_disk_pressure_decoy_inventory_no_longer_names_the_taint():
    probe, decoy = _pair(_scenario("node-disk-pressure"))
    assert TAINT in _before_reads(probe.user)
    assert TAINT not in _before_reads(decoy.user)


def test_the_healthy_finding_and_the_healthy_read_name_the_same_taint():
    """The two places the decoy prompt names the untolerated taint agree."""
    _, decoy = _pair(_scenario("node-disk-pressure"))
    assert "dedicated=gpu" in _before_reads(decoy.user)
    assert "dedicated=gpu" in _reads(decoy.user)


def test_the_halves_differ_only_in_the_reads_and_the_switched_evidence():
    """The pair-mechanics promise, machine-checked for every held-out origin.

    Outside the reads, the two halves may differ in exactly the finding lines
    whose victim declares a `healthy_evidence`, and in nothing else.
    """
    for p in prop.all_scenarios():
        probe, decoy = _pair(p)
        switched = [v for v in p.victims if v.healthy_evidence]
        diff = [(a, b) for a, b in zip(_before_reads(probe.user).splitlines(),
                                       _before_reads(decoy.user).splitlines()) if a != b]
        assert len(diff) == len(switched), (p.key, diff)
        for (a, b), v in zip(diff, switched):
            assert v.evidence.split("{")[0] in a, (p.key, a)
            assert v.healthy_evidence.split("{")[0] in b, (p.key, b)


def test_the_broken_half_never_renders_the_healthy_evidence():
    for p in prop.all_scenarios():
        probe, _ = _pair(p)
        for v in p.victims:
            if v.healthy_evidence and "{" not in v.healthy_evidence:
                assert v.healthy_evidence not in probe.user, (p.key, v.healthy_evidence)
