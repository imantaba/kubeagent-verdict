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
import re

from kubeagent_verdict.dataset import cases
from kubeagent_verdict.dataset import propagation as prop

TAINT = "node.kubernetes.io/disk-pressure"
NETWORK_TAINT = "node.kubernetes.io/network-unavailable"
EVIDENCE_MARK = "== BEGIN evidence =="

# A maximal run of these characters, at least 6 long, is a "token" for the
# fault-token sweep below.
_TOKEN_RE = re.compile(r"[A-Za-z0-9._/=-]{6,}")


def _scenario(key: str) -> prop.Propagation:
    return next(p for p in (*prop.trainable_scenarios(), *prop.all_scenarios())
                if p.key == key)


def _before_reads(user: str) -> str:
    """The inventory and candidate sections: everything a pair holds fixed."""
    return user.split(EVIDENCE_MARK)[0]


def _reads(user: str) -> str:
    return user.split(EVIDENCE_MARK)[1]


DECIDED_PREFIX = "    decided by rules: "


def _decided(user: str) -> list[str]:
    return [line for line in user.splitlines() if line.startswith(DECIDED_PREFIX)]


def _without_decided(text: str) -> str:
    """The same text with the `decided by rules:` lines taken out.

    v1.24.0 re-checks every candidate against the gather's fresh reads, so
    the two halves of a pair do not decide the same way: where the origin
    read is what decides a workload, the healthy half decides nothing. That
    difference is the evidence itself, restated by the rule engine, and it
    is checked on its own in
    `test_the_decided_line_is_the_rule_engine_re_reading_the_origin`.
    Everything else the pair holds fixed.
    """
    return "\n".join(line for line in text.splitlines()
                      if not line.startswith(DECIDED_PREFIX))


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


def test_the_halves_differ_only_in_the_reads_the_evidence_and_the_decided_line():
    """The pair-mechanics promise, machine-checked for every held-out origin.

    Outside the reads and the rule engine's own decided line, the two halves
    may differ in exactly the finding lines whose victim declares a
    `healthy_evidence`, and in nothing else.
    """
    for p in prop.all_scenarios():
        probe, decoy = _pair(p)
        switched = [v for v in p.victims if v.healthy_evidence]
        diff = [(a, b) for a, b in
                zip(_without_decided(_before_reads(probe.user)).splitlines(),
                    _without_decided(_before_reads(decoy.user)).splitlines()) if a != b]
        assert len(diff) == len(switched), (p.key, diff)
        for (a, b), v in zip(diff, switched):
            assert v.evidence.split("{")[0] in a, (p.key, a)
            assert v.healthy_evidence.split("{")[0] in b, (p.key, b)


def test_the_decided_line_is_the_rule_engine_re_reading_the_origin():
    """The one thing the pair cannot hold fixed, stated rather than hidden.

    v1.24.0 re-checks each candidate against the gather's fresh reads and
    prints what it decided. On the three scenarios whose origin read is the
    thing that decides a workload, the broken half decides and the healthy
    half does not, so the halves differ by that line. The claim "only the
    contents of the reads differ" is narrowed here rather than dropped: the
    line is the rule engine's reading of those contents, so a model
    separating the halves on it is separating them on the evidence, not on
    an artefact of how the pair was built. The other three scenarios decide
    off a victim's own object, which the healthy swap does not touch, so
    their lines are identical.
    """
    from_origin, from_victim = [], []
    for p in prop.all_scenarios():
        probe, decoy = _pair(p)
        assert _decided(probe.user), p.key
        if _decided(probe.user) == _decided(decoy.user):
            from_victim.append(p.key)
            assert p.origin_object is None, p.key
        else:
            from_origin.append(p.key)
            assert p.origin_object is not None, p.key
            assert _decided(decoy.user) == [], p.key
    assert len(from_origin) == 3, from_origin
    assert len(from_victim) == 3, from_victim


def test_the_broken_half_never_renders_the_healthy_evidence():
    for p in prop.all_scenarios():
        probe, _ = _pair(p)
        for v in p.victims:
            if v.healthy_evidence and "{" not in v.healthy_evidence:
                assert v.healthy_evidence not in probe.user, (p.key, v.healthy_evidence)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text))


def _looks_like_a_label(token: str) -> bool:
    """A Kubernetes taint/label key (`domain.tld/name`) or a `key=value` pair.

    Refinement of the raw token rule: the plain "appears only in broken
    content" test also caught generic prose that happens to differ between a
    scenario's broken and healthy wording -- "failed" vs. "succeeded",
    "MountVolume.MountDevice" vs. "MapVolume.MapPodDevice", an errno string
    like "input/output" that a truncated image layer could print too. None
    of those name a fact specific to the origin; a taint or label key does,
    which is exactly what both known bugs (node-disk-pressure and
    node-network-unavailable) leaked into their decoy's inventory.
    """
    return "=" in token or ("." in token and "/" in token)


def _fault_tokens(p: prop.Propagation) -> set[str]:
    """Label-shaped tokens present in a broken origin-read content but no
    healthy one.

    `origin_read[1]` is the frozen content every scenario carries;
    `origin_variants` (trainable pool only) pairs a broken content with its
    healthy twin. `healthy_origin_content` is the single healthy read every
    scenario carries. A fault token is one that names the origin's broken
    state and never appears in any of that scenario's healthy content.
    """
    broken = [p.origin_read[1], *(variant[0] for variant in p.origin_variants)]
    healthy = [p.healthy_origin_content, *(variant[1] for variant in p.origin_variants)]
    broken_tokens: set[str] = set()
    for content in broken:
        broken_tokens |= _tokens(content)
    healthy_tokens: set[str] = set()
    for content in healthy:
        healthy_tokens |= _tokens(content)
    return {t for t in broken_tokens - healthy_tokens if _looks_like_a_label(t)}


def test_a_victim_whose_evidence_names_a_fault_token_declares_healthy_evidence():
    """A decoy's inventory must never assert a fact only the broken origin has.

    Sweeps every victim of every trainable and held-out scenario. If a
    victim's `evidence` contains one of its scenario's fault tokens, that
    victim must declare `healthy_evidence`, and `healthy_evidence` must
    contain none of those tokens -- the same rule item 1 fixes by hand for
    `node-network-unavailable` victim 1.
    """
    for p in (*prop.trainable_scenarios(), *prop.all_scenarios()):
        fault_tokens = _fault_tokens(p)
        for i, v in enumerate(p.victims):
            hit = [t for t in fault_tokens if t in v.evidence]
            if not hit:
                continue
            assert v.healthy_evidence, (
                f"{p.key} victim {i}: evidence contains fault token {hit[0]!r} "
                "but declares no healthy_evidence")
            for t in fault_tokens:
                assert t not in v.healthy_evidence, (
                    f"{p.key} victim {i}: healthy_evidence still contains "
                    f"fault token {t!r}")


def test_the_network_unavailable_decoy_inventory_no_longer_names_the_taint():
    probe, decoy = _pair(_scenario("node-network-unavailable"))
    assert NETWORK_TAINT in _before_reads(probe.user)
    assert NETWORK_TAINT not in _before_reads(decoy.user)


def test_the_network_unavailable_healthy_finding_names_a_different_taint():
    _, decoy = _pair(_scenario("node-network-unavailable"))
    assert "dedicated=gpu" in _before_reads(decoy.user)
