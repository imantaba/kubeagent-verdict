"""Spec 4b-2: the catalog's answer kits, and the gold they give.

Every named catalog gold rests on an anchor in the workload's own lines.
See docs/superpowers/specs/2026-10-04-catalog-gold-design.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kubeagent_verdict.dataset import catalog, generate, stories

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
