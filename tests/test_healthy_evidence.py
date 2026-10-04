"""A healthy-world finding must not say the origin is broken.

A twin pair is one story built twice from one draw: the broken world, and the
healthy world, which is the broken world with the origin fixed plus any
victim-side edits the story declares. The victim-side edits matter. Where a
victim's own finding names a fact of the origin, a healthy twin that reuses
the text carries a finding that says the origin is broken, a cluster block
that says it is fine, and a label that says "none". The node-disk-pressure
decoy did exactly that -- `untolerated taint node.kubernetes.io/disk-pressure`
in the prompt of a world whose node has no disk pressure -- and the model
believed the finding. `VictimText.evidence_healthy` and `events_healthy` are
the fix: the same finding in the world where the origin is fine, printed only
by the healthy half.

Spec 4b-1: these tests read the rows a story builds through the real pipeline.
Two tests still read `propagation.py`'s own data, which does not change and
which `multi` still draws: the first one, and the fault-token sweep further down.
"""

import random
import re

from kubeagent_verdict.dataset import cases, stories
from kubeagent_verdict.dataset import propagation as prop
from kubeagent_verdict.dataset import shared_origin as so

TAINT = "node.kubernetes.io/disk-pressure"
NETWORK_TAINT = "node.kubernetes.io/network-unavailable"
HEALTHY_TAINT = "dedicated=gpu"
EVIDENCE_MARK = "== BEGIN evidence =="
DECIDED_PREFIX = "    decided by rules: "
_UNTOLERATED = re.compile(r"untolerated taint ([^\s,)]+)")

# A maximal run of these characters, at least 6 long, is a "token" for the
# fault-token sweep further down.
_TOKEN_RE = re.compile(r"[A-Za-z0-9._/=-]{6,}")


def _scenario(key: str) -> prop.Propagation:
    return next(p for p in (*prop.trainable_scenarios(), *prop.all_scenarios())
                if p.key == key)


def _decided(user: str) -> list[str]:
    return [line for line in user.splitlines() if line.startswith(DECIDED_PREFIX)]


def _pair(st: stories.Story) -> tuple[cases.Example, cases.Example]:
    """The broken probe and its healthy twin, from one seed and so one draw."""
    return (cases.shared_origin_probe(st, random.Random(7)),
            cases.shared_origin_decoy_probe(st, random.Random(7)))


def _built(st: stories.Story, world: str) -> so.Built:
    d = so.draw(st, random.Random(7), width=len(st.victims))
    return so.build(st, d, world=world)


def _entry(user: str, key: str) -> str:
    """One workload's inventory entry: its `- ns/name (` line and the indented
    lines under it. The entry ends at the next `- ` line or at any line that
    does not start with a space."""
    inventory = user.split("== BEGIN inventory ==")[1].split("== END inventory ==")[0]
    kept, inside = [], False
    for line in inventory.split("\n"):
        if line.startswith("- "):
            inside = line.startswith(f"- {key} (")
        elif not line.startswith(" "):
            inside = False
        if inside:
            kept.append(line)
    return "\n".join(kept)


def _read(user: str, label: str) -> str:
    """One evidence read: the text under its `== label ==` line, up to the next
    `== ` line. Empty when the prompt prints no such read."""
    evidence = user.split(EVIDENCE_MARK)[1].split("== END evidence ==")[0]
    parts = evidence.split(f"== {label} ==\n")
    return parts[1].split("\n== ")[0] if len(parts) > 1 else ""


def _victim_row(built: so.Built, index: int) -> so.Row:
    return next(r for r in built.rows if r.role == "victim" and r.index == index)


def test_the_one_victim_whose_evidence_names_the_origin_has_a_healthy_twin():
    v = _scenario("node-disk-pressure").victims[0]
    assert TAINT in v.evidence
    assert v.healthy_evidence
    assert TAINT not in v.healthy_evidence


def test_the_disk_pressure_healthy_world_never_prints_the_taint():
    """The first leak, on the new rows: the broken world names the taint, and
    the healthy world, whose node has no pressure, names it nowhere -- not in
    the finding line and not in the scheduler's event."""
    probe, decoy = _pair(stories.by_key()["node-disk-pressure"])
    assert TAINT in probe.user
    assert TAINT not in decoy.user


def test_the_healthy_finding_and_the_healthy_events_name_the_same_taint():
    """The two places a prompt names the untolerated taint agree, in each world.

    The broken world names the disk-pressure taint in the finding and in the
    pod's events. The healthy world names an operator's own taint in both. A
    finding that names one taint above events that name another would be two
    stories in one prompt.
    """
    st = stories.by_key()["node-disk-pressure"]
    for world, taint in (("broken", TAINT), ("healthy", HEALTHY_TAINT)):
        built = _built(st, world)
        seen = 0
        for row in built.rows:
            finding = _UNTOLERATED.findall(_entry(built.user, row.key))
            if not finding:
                continue
            events = _UNTOLERATED.findall(
                _read(built.user, f"events {row.names.ns}/{row.names.pod}"))
            assert finding == events == [taint], (world, row.key, finding, events)
            seen += 1
        assert seen, f"no {world} victim names an untolerated taint"


def test_the_halves_differ_in_at_least_one_printed_line():
    """The pair-mechanics promise, machine-checked for every story (Ruling 35).

    The two halves need not differ only in their reads, and the rule engine's
    decided line is one of the lines that may differ. They must differ in at
    least one printed line, or the pair teaches nothing. They must also stay
    one pair: the same draw, so the same victims, named by the same group.
    """
    for st in stories.by_key().values():
        probe, decoy = _pair(st)
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), st.key
        assert probe.group == decoy.group, st.key
        for part in probe.group.split("+"):
            victim = part.split(":", 2)[2]
            assert victim in probe.meta["workloads"], (st.key, victim)
            assert victim in decoy.meta["workloads"], (st.key, victim)
        assert "shared_claim_phrases" in decoy.meta, st.key
        assert "shared_claim_phrases" not in probe.meta, st.key


def test_the_decided_line_is_the_rule_engine_re_reading_the_origin():
    """The one thing the pair cannot hold fixed, stated rather than hidden.

    The rules re-check each candidate against the gather's fresh reads and
    the prompt prints what they decided. On the three ruled exam stories
    (node-not-ready, storage-provisioner-down, registry-unreachable) the
    fresh read of the origin is what decides every victim, so the broken half
    prints one decided line per victim and the healthy half prints none. The
    line is the rule engine's reading of the reads, so a model separating the
    halves on it is separating them on the evidence. The three plain exam
    stories give the rules no node, claim or registry to confirm, so neither
    half decides anything.
    """
    ruled = 0
    for st in stories.exam():
        probe, decoy = _pair(st)
        if st.cls == "P":
            assert _decided(probe.user) == [], st.key
            assert _decided(decoy.user) == [], st.key
            continue
        ruled += 1
        metas = probe.meta["workloads"].values()
        assert all(m["decided"] for m in metas), st.key
        want = sorted(f"{DECIDED_PREFIX}{m['decided_cause']} — {m['decided_outcome']}"
                      for m in metas)
        assert sorted(_decided(probe.user)) == want, st.key
        assert _decided(decoy.user) == [], st.key
        assert not any(m["decided"] for m in decoy.meta["workloads"].values()), st.key
    assert ruled == 3, ruled


def test_the_broken_half_never_renders_the_healthy_text():
    """A victim's healthy finding and healthy events are printed by the
    healthy half and never by the broken half.

    Swept over every story. A healthy finding is printed verbatim in the
    victim's inventory entry, so it is looked for there. A healthy event is
    run through kubeagent's redaction before it is printed (an address
    becomes `<redacted>`), so the event is compared as the printed read: the
    two halves must print different events for that pod. A healthy text that
    equals the broken one is skipped, because it cannot tell the halves apart.
    """
    checked = set()
    for st in stories.by_key().values():
        broken, healthy = _built(st, "broken"), _built(st, "healthy")
        for i, v in enumerate(st.victims[:broken.draw.width]):
            row = _victim_row(broken, i)
            if v.evidence_healthy is not None and v.evidence_healthy != v.evidence:
                text = so._sub(v.evidence_healthy, row.names, broken.draw)
                assert text in _entry(healthy.user, row.key), (st.key, row.key, text)
                assert text not in _entry(broken.user, row.key), (st.key, row.key, text)
                checked.add(st.key)
            if v.events_healthy is not None and v.events_healthy != v.events:
                label = f"events {row.names.ns}/{row.names.pod}"
                assert _read(healthy.user, label), (st.key, label)
                assert _read(healthy.user, label) != _read(broken.user, label), (st.key, label)
                checked.add(st.key)
    assert {"coredns-down", "node-disk-pressure", "node-network-unavailable"} <= checked, checked


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


def test_the_network_unavailable_healthy_world_never_prints_the_taint():
    """NetworkUnavailable prints no health line (kubeagent never checks it),
    so the victim's own finding is the only place the two worlds can differ."""
    probe, decoy = _pair(stories.by_key()["node-network-unavailable"])
    assert NETWORK_TAINT in probe.user
    assert NETWORK_TAINT not in decoy.user


def test_the_network_unavailable_healthy_finding_names_a_different_taint():
    st = stories.by_key()["node-network-unavailable"]
    _, decoy = _pair(st)
    built = _built(st, "healthy")
    assert any(HEALTHY_TAINT in _entry(decoy.user, row.key) for row in built.rows)


def _squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _broken_only_words(st: stories.Story) -> list[str]:
    """The names of the node conditions only the broken world carries: a
    pressure condition by its type, a Ready that is False as "NotReady"."""
    return [("NotReady" if cd.type == "Ready" else cd.type)
            for cd in st.broken.conditions if cd not in st.healthy.conditions]


def test_a_healthy_world_never_names_a_node_condition_only_the_broken_world_has():
    """A healthy prompt must not assert a fact only the broken origin has.

    Swept over every story whose broken world carries a node condition the
    healthy world does not (DiskPressure, PIDPressure, NotReady, ...). The
    condition's name, with case and punctuation removed, may appear nowhere
    in the healthy prompt. That also catches the taint spelling of the same
    fact (`node.kubernetes.io/disk-pressure` squashes to a string holding
    `diskpressure`), which is how both known leaks, node-disk-pressure and
    node-network-unavailable, got into a healthy inventory.
    """
    checked = set()
    for st in stories.by_key().values():
        words = _broken_only_words(st)
        if not words:
            continue
        healthy = _squash(_built(st, "healthy").user)
        for word in words:
            assert _squash(word) not in healthy, (st.key, word)
        checked.add(st.key)
    assert {"node-not-ready", "node-pid-pressure", "node-disk-pressure"} <= checked, checked
