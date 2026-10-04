"""Spec 4b-2: the catalog's answer kits, and the gold they give.

Every named catalog gold rests on an anchor in the workload's own lines.
See docs/superpowers/specs/2026-10-04-catalog-gold-design.md.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, generate, gold, stories
from kubeagent_verdict.dataset import names as names_mod

ENTRIES = {e.key: e for e in catalog.all_entries()}

# The spec's kit table (§3): key -> (anchor, cause, keys, confidence).
# Written out here, not imported, so a change to a kit fails.
KITS = {
    "memory-limit-oomkill": (
        "issue: oomkilled", "container killed at its memory limit",
        ("memory", "limit"), "high"),
    "deployment-bad-image-tag": (
        '": not found', "the image tag does not exist in the registry",
        ("image", "registry"), "high"),
    "node-cordon-diskfull": (
        "were unschedulable",
        ("one node is unschedulable (cordoned) and the others have taints the pod does not "
         "tolerate"),
        ("unschedulable", "taint"), "high"),
    "networkpolicy-deny-all": (
        "network policy: pods selected by",
        "a default-deny network policy blocks the probe's traffic to the pod",
        ("network", "policy"), "medium"),
    "coredns-corefile-broken": (
        "log cause: configuration parse",
        "the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
        ("coredns", "error"), "high"),
    "worker-containerd-stop": (
        "containerd task: context deadline exceeded",
        "containerd on the pod's node is not responding (context deadline exceeded)",
        ("containerd", "deadline"), "high"),
    "oversized-job-unschedulable": (
        "insufficient memory",
        "the pod's memory request is larger than any node can allocate",
        ("memory", "node"), "high"),
    "crashloop-pod": (
        "log cause: bad command or entrypoint",
        "the container's command or entrypoint is wrong and it exits immediately",
        ("entrypoint", "exit"), "high"),
    "probe-failure": (
        "http 500", "the application answers its readiness endpoint with errors",
        ("readiness", "endpoint"), "high"),
    "container-start-error": (
        "no such file or directory",
        "the container's entrypoint names a path that does not exist in the image",
        ("container", "image"), "high"),
    "create-container-config-error": (
        "couldn't find key",
        "the pod spec references a ConfigMap key that was never added or was renamed",
        ("configmap", "key"), "high"),
    "init-crashloop": (
        "log cause: cannot reach a dependency",
        "the init container cannot reach a dependency it waits for before the pod can start",
        ("init", "dependency"), "high"),
    "init-config-error": (
        "secret migration-creds not found",
        "a Secret the init container references does not exist",
        ("secret", "init"), "high"),
    "init-errimagepull": (
        '": not found', "the init container's image tag does not exist in the registry",
        ("init", "registry", "tag"), "high"),
    "init-imagepullbackoff": (
        "back-off pulling image",
        "the init container's image cannot be pulled, and the kubelet keeps backing off",
        ("init", "pull"), "high"),
    "init-oomkilled": (
        "init:oomkilled", "the init container is killed at its memory limit",
        ("memory", "init"), "high"),
    "restart-loop": (
        "log cause: application panic",
        "the container panics (a code bug) and keeps restarting",
        ("panic", "container"), "high"),
    "volume-attach-error": (
        "multi-attach error", "the volume is still attached to another node",
        ("attached", "node"), "high"),
    "volume-mount-error": (
        "issue: volumemounterror", "the pod's volume times out while mounting on its node",
        ("volume", "pod"), "high"),
    "pvc-unbound-unschedulable": (
        "unbound immediate persistentvolumeclaims",
        "a claim the pod mounts is still waiting for its volume to be provisioned",
        ("claim", "volume"), "high"),
}

# The spec's draft reasons, as templates ({image} is filled per row).
REASONS = {
    "memory-limit-oomkill":
        "Its finding says the container exceeded its memory limit and was killed, with "
        "exit code 137.",
    "deployment-bad-image-tag":
        'The pull of {image} fails with "not found", so the tag does not exist in the '
        "registry.",
    "node-cordon-diskfull":
        "The scheduler says 1 node was unschedulable and 2 had taints the pod does not "
        "tolerate, so no node can take it.",
    "networkpolicy-deny-all":
        "The readiness probe times out, and kubeagent names the default-deny network policy "
        "that selects its pods as a possible cause, so the policy likely blocks the probe.",
    "coredns-corefile-broken":
        "The coredns container keeps crashing, and its previous log classifies as a "
        "configuration parse or validation error, so CoreDNS cannot load its Corefile.",
    "worker-containerd-stop":
        'Starting the container fails with "failed to create containerd task: context '
        "deadline exceeded\", so containerd on the pod's node does not answer in time.",
    "oversized-job-unschedulable":
        "The scheduler rejects all 3 nodes for insufficient memory, so the pod's memory "
        "request is larger than any node can give.",
    "crashloop-pod":
        "The container keeps exiting after it starts, and its previous log classifies as a "
        "bad command or entrypoint.",
    "probe-failure":
        "The readiness probe fails with HTTP 500, so the application answers its health "
        "endpoint with an error.",
    "container-start-error":
        'The container cannot start: its entrypoint path gives "no such file or directory", '
        "so that path is not in the image.",
    "create-container-config-error":
        "The kubelet couldn't find the key the container needs in the ConfigMap it names, "
        "so the pod spec points at a key that is not there.",
    "init-crashloop":
        "The init container keeps crashing, and its previous log classifies as connection "
        "refused, so it cannot reach a dependency it waits for.",
    "init-config-error":
        "The init container cannot start because the Secret it references is not found.",
    "init-errimagepull":
        "The init container's image pull fails with \"not found\", so its tag does not "
        "exist in the registry.",
    "init-imagepullbackoff":
        "The kubelet keeps backing off pulling the init container's image, so the pod "
        "cannot start. Its own lines do not say why the pull fails.",
    "init-oomkilled":
        "The init container is OOMKilled with exit code 137, so it is killed at its own "
        "memory limit.",
    "restart-loop":
        "The container keeps exiting with an error, and its previous log classifies as an "
        "application panic.",
    "volume-attach-error":
        "Attaching fails with a multi-attach error: the volume is already attached to "
        "another node.",
    "volume-mount-error":
        "Mounting the pod's volume times out waiting for the condition, so the volume does "
        "not mount on its node.",
    "pvc-unbound-unschedulable":
        "The scheduler says the pod has unbound immediate PersistentVolumeClaims, so a "
        "claim it mounts has no volume yet.",
}

NONE_PHRASES = {
    "memory-limit-oomkill": "its container keeps being killed for memory",
    "deployment-bad-image-tag": "its image cannot be pulled",
    "node-cordon-diskfull": "its pod cannot be scheduled",
    "networkpolicy-deny-all": "its readiness probe fails",
    "coredns-corefile-broken": "its container keeps crashing",
    "worker-containerd-stop": "its container fails to start",
    "oversized-job-unschedulable": "its pod cannot be scheduled",
    "crashloop-pod": "its container keeps crashing",
    "probe-failure": "its readiness probe fails",
    "container-start-error": "its container fails to start",
    "create-container-config-error": "its container fails to start",
    "init-crashloop": "its init container keeps crashing",
    "init-config-error": "its init container fails to start",
    "init-errimagepull": "its init container's image cannot be pulled",
    "init-imagepullbackoff": "its init container's image cannot be pulled",
    "init-oomkilled": "its init container keeps being killed for memory",
    "restart-loop": "its container keeps restarting",
    "volume-attach-error": "its volume cannot attach",
    "volume-mount-error": "its volume cannot be mounted",
    "pvc-unbound-unschedulable": "its pod cannot be scheduled",
}

# The 7 recommendations the spec rewrites (§3). The other 13 stay.
RECOMMENDATIONS = {
    "node-cordon-diskfull": "uncordon the node, or check why the other nodes are tainted",
    "worker-containerd-stop": "check whether the container runtime on the pod's node is healthy",
    "init-imagepullbackoff": "check the init image's tag and the registry credentials",
    "init-oomkilled": "raise the init container's memory limit",
    "restart-loop": "check the previous log for the panic",
    "volume-mount-error": "check why the volume does not mount on the pod's node",
    "pvc-unbound-unschedulable": "check why the pod's claim has no bound volume yet",
}


# ------------------------------------------------------------ the kits


def test_every_trainable_entry_has_a_kit_and_no_other_entry_does():
    for e in catalog.all_entries():
        if e.trains:
            assert isinstance(e.answer, stories.Answer), e.key
            assert e.none_phrase, e.key
        else:
            assert e.answer is None and e.none_phrase == "", e.key
    assert set(KITS) == {e.key for e in catalog.trainable()}


def test_the_kits_are_the_spec_table():
    got = {e.key: (e.answer.anchor, e.answer.cause, e.answer.keys, e.answer.confidence)
           for e in catalog.trainable()}
    assert got == KITS


def test_the_kit_reasons_are_the_spec_drafts():
    assert {e.key: e.answer.rationale for e in catalog.trainable()} == REASONS


def test_the_none_phrases_are_the_spec_list():
    assert {e.key: e.none_phrase for e in catalog.trainable()} == NONE_PHRASES


def test_no_kit_links_and_no_anchor_or_cause_holds_a_placeholder():
    for e in catalog.trainable():
        a = e.answer
        assert a.link is False, e.key
        assert "{" not in a.anchor and "{" not in a.cause, e.key
        stories.validate_answer(a)


def test_no_kit_cause_or_key_holds_one_of_its_must_not_words():
    for e in catalog.trainable():
        for word in e.own_cause_must_not:
            assert word not in e.answer.cause.lower(), (e.key, word)
            assert word not in e.answer.keys, (e.key, word)


def test_the_seven_recommendations_are_rewritten():
    for key, text in RECOMMENDATIONS.items():
        assert ENTRIES[key].recommendation == text, key


def test_no_trainable_recommendation_names_a_drawn_name():
    for e in catalog.trainable():
        for placeholder in ("{node}", "{pvc}", "{image}", "{pod}"):
            assert placeholder not in e.recommendation, (e.key, placeholder)


# ------------------------------------------------------------ the prompts

DATASET_1004 = Path(__file__).resolve().parents[1] / "out" / "dataset-1004"


@pytest.fixture(scope="module")
def build_1004() -> dict[str, list]:
    """The out/dataset-1004 pipeline: generate(17, 8000), split, drop held-out."""
    ex = generate.generate(17, 8000)
    tr, va = generate.split(ex, 17)
    te = generate.test_set()
    return {"train": generate.drop_held_out(tr, te),
            "val": generate.drop_held_out(va, te), "test": te}


@pytest.mark.skipif(not DATASET_1004.is_dir(), reason="out/dataset-1004 is not on this machine")
@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_no_prompt_byte_moves_from_dataset_1004(build_1004, split):
    """Spec test 5. The gold changes; the prompts never do. A builder that
    raises and is drawn again would shift every later row, so this also
    guards the random stream."""
    path = DATASET_1004 / f"{split}.jsonl"
    old = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    new = [generate.to_row(e) for e in build_1004[split]]
    assert len(new) == len(old)
    for i, (a, b) in enumerate(zip(new, old)):
        assert a["messages"][:2] == b["messages"][:2], (split, i)


# ------------------------------------------------------------ the gold

# The probe's fact pattern (spec test 2): a number with an optional unit,
# or a CamelCase word. Compared lowercase against the own lines.
FACT = re.compile(r"\b(?:\d+(?:\.\d+)?[A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]+|[a-z]+[A-Z][A-Za-z]+)\b")
GATED = "; none of its own lines says why."
# Task 3 rebuilds these two on the gate and empties this set.
MULTI_CASES = {"multi", "multi_misattribution_probe"}


@pytest.fixture(scope="module")
def examples() -> list:
    """Every catalog case over three seeds, plus the exam. About 7 s."""
    rows = []
    for seed in (17, 18, 19):
        rows += generate.generate(seed, 8000)
    return rows + generate.test_set()


def catalog_rows(examples, skip=frozenset()):
    """(example, workload, entry, verdict, workload meta, own lines) for every
    catalog workload. A catalog group is `entry:ns/name`, joined by `+`."""
    for ex in examples:
        if ex.case.startswith("shared_origin") or ex.case in skip:
            continue
        entry_of = {wl: ENTRIES[key] for key, wl in
                    (part.split(":", 1) for part in ex.group.split("+"))}
        own = gold.own_lines(ex.user, list(entry_of))
        verdicts = {v["workload"]: v for v in json.loads(ex.assistant)["verdicts"]}
        for wl, e in entry_of.items():
            yield ex, wl, e, verdicts[wl], ex.meta["workloads"][wl], sorted(own[wl])


def _names() -> names_mod.Names:
    return names_mod.Names(
        ns="shop", name="web", pod="web-5d8f7c9b4-x2k9p", container="app",
        init_container="init-config", image="registry.example.com/shop/web:v1.2.3",
        node="worker-1", pvc="data-0", restarts=5)


def test_every_named_answer_rests_on_its_own_lines(examples):
    """Spec test 2: the cause is the kit's, and the anchor, every key and
    every fact in the reason are on the workload's own lines."""
    named = 0
    for ex, wl, e, v, wm, own in catalog_rows(examples, skip=MULTI_CASES):
        if wm["decided"] or v["cause"] == c.NONE_OF_THESE:
            continue
        named += 1
        a, text, where = e.answer, "\n".join(own), (ex.case, ex.group, wl)
        assert v["cause"] == cases._fmt(a.cause, _names()), where
        assert any(gold._norm_cause(a.anchor) in ln for ln in own), where
        assert all(any(k in ln for ln in own) for k in a.keys), where
        unshown = [t for t in FACT.findall(v["rationale"]) if t.lower() not in text]
        assert unshown == [], (*where, unshown)
    assert named > 1000


def test_confidence_follows_the_gold(examples):
    """Spec test 4: rules-decided rows are high, named rows carry the kit's
    confidence, none_of_these rows are low, and meta agrees."""
    for ex, wl, e, v, wm, _own in catalog_rows(examples, skip=MULTI_CASES):
        if wm["decided"]:
            want = "high"
        elif v["cause"] == c.NONE_OF_THESE:
            want = "low"
        else:
            want = e.answer.confidence
        assert v["confidence"] == want, (ex.case, ex.group, wl)
        if "expected_confidence" in ex.meta:
            first = json.loads(ex.assistant)["verdicts"][0]
            assert ex.meta["expected_confidence"] == first["confidence"], (ex.case, ex.group)


def _probe_own_lines(examples) -> list[str]:
    ex = next(x for x in examples
              if x.case == "own_cause" and x.group.startswith("probe-failure:"))
    wl = ex.group.split(":", 1)[1]
    return sorted(gold.own_lines(ex.user, [wl])[wl])


def test_the_gate_names_the_cause_only_on_its_anchor(examples):
    """Spec test 3, the hand-cut case: real own lines of a probe-failure row."""
    e, n = ENTRIES["probe-failure"], _names()
    own = _probe_own_lines(examples)
    named = cases._entry_gold(e, n, own, [])
    assert named == gold.RowGold("named", e.answer.cause, "high", ("readiness", "endpoint"),
                                 e.answer.rationale, False)
    none = gold.RowGold("none_of_these", "", "low", (),
                        "its readiness probe fails" + GATED, False)
    cut = [ln for ln in own if "http 500" not in ln]
    assert cases._entry_gold(e, n, cut, []) == none
    assert cases._entry_gold(e, n, own, ["http 500"]) == none


def test_a_key_only_on_an_excluded_line_fails_the_build():
    e = dataclasses.replace(ENTRIES["probe-failure"], answer=stories.Answer(
        anchor="http 500", cause="the readiness endpoint fails",
        keys=("readiness", "endpoint"), rationale="x."))
    own = ["probe says http 500", "readiness endpoint is down"]
    with pytest.raises(ValueError, match="sits only in excluded lines"):
        cases._entry_gold(e, _names(), own, ["readiness endpoint is down"])
    with pytest.raises(ValueError, match="sits in no own line"):
        cases._entry_gold(e, _names(), own[:1], [])


def test_an_entry_with_no_kit_cannot_answer():
    e = next(x for x in catalog.all_entries() if not x.trains)
    with pytest.raises(ValueError, match="has no answer kit"):
        cases._entry_gold(e, _names(), [], [])


def _unprinted(key: str) -> catalog.CatalogEntry:
    """`key`'s entry with an anchor no prompt ever prints."""
    e = ENTRIES[key]
    return dataclasses.replace(e, answer=dataclasses.replace(
        e.answer, anchor="this line is never printed"))


@pytest.mark.parametrize("case", ["own_cause", "wrong_attribution", "misattribution_probe"])
def test_a_single_row_with_no_anchor_names_nothing(case):
    e, n = _unprinted("probe-failure"), _names()
    shape = "refuted" if case == "wrong_attribution" else "ruled_out"
    ex = cases._undecided_example(e, n, case=case, shape=shape, evidence="clear")
    doc = json.loads(ex.assistant)
    (row,) = doc["verdicts"]
    assert (row["cause"], row["confidence"], row["rationale"]) == (
        c.NONE_OF_THESE, "low", "its readiness probe fails" + GATED)
    assert doc["summary"] == cases._ruled_out_summary("shop/web")
    wm = ex.meta["workloads"]["shop/web"]
    assert (wm["own_cause_keywords"], wm["own_cause_must_not"]) == ([], [])
    assert ex.meta["expected_cause"] == c.NONE_OF_THESE


def test_an_empty_candidates_row_with_no_anchor_does_not_claim_a_list():
    ex = cases.empty_candidates(_unprinted("probe-failure"), _names())
    doc = json.loads(ex.assistant)
    (row,) = doc["verdicts"]
    assert (row["cause"], row["confidence"]) == (c.NONE_OF_THESE, "low")
    assert doc["summary"] == ("shop/web is failing, but its own lines do not show why.\n"
                              "No deterministic candidates were available.")
    assert ex.meta["expected_own_keywords"] == []
