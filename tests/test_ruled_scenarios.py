"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.ruled_scenarios()` is a pool separate from
`trainable_scenarios()` -- merging the two is a later task -- but it has to
clear the same authoring floor and the same eval-disjointness rules that
pool already clears, which is why several checks below mirror a named test
in `test_shared_origin_training.py` rather than inventing a new shape.

Mechanically, a ruled story's BROKEN twin puts every victim on the SAME
origin object, so the rules pass confirms each one against the same group
key and `rules.label` reports "shared"; the HEALTHY twin overrides that
object's fresh read (`healthy_origin_fresh`), every victim comes back
refuted, and the label flips to "none". That is asserted directly, by
rendering both twins, rather than trusted from the story's shape.
"""

import json
import random
import re

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, propagation
from kubeagent_verdict.evals import score

RULED = propagation.ruled_scenarios()
TRAINABLE = propagation.trainable_scenarios()
EVAL = propagation.all_scenarios()

NODE_KEYS = {"node-kubelet-halted", "node-kubelet-unresponsive"}
PVC_STORAGE_CLASSES = {
    "pvc-provisioner-not-responding": "capacity-hdd",
    "pvc-storageclass-missing": "cache-nvme",
}
REGISTRY_KEYS = {"registry-mirror-unreachable", "registry-rate-limited"}

# Spec section 4: the four labels the EXAM already pins to one origin each.
# A trainable or ruled story that reused one would let the model answer from
# the label alone, so neither pool may declare it.
_EXAM_ONLY_LABELS = frozenset({
    "describe kube-system/coredns (Deployment)",
    "get_related storageclass standard",
    "get_events (cluster-wide, reason=Failed)",
    "get_related networkpolicy {ns}/default-deny",
})

# Duplicated from score.py's own vocabulary rather than imported, matching
# how score.py itself keeps its shared-claim and independence phrase tuples
# separate. cases.SHARED_CLAIM_PHRASES is the shared-claim half.
_INDEPENDENCE_PHRASES = (
    "separate reasons", "separate causes", "independent", "independently",
    "unrelated", "distinct causes", "different causes", "not related",
    "no shared", "no common",
)

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL = re.compile(r"https?://")


def _victim_blob(v):
    parts = [v.reason, v.evidence, v.log_cause, v.local_cause, v.local_reason,
             v.read[0], v.read[1], v.healthy_read_content, v.healthy_evidence]
    parts += list(v.network_policies)
    return parts


def _scenario_blob(p):
    parts = [p.origin, p.shared_cause, p.shared_reason, p.distractor_cause,
             p.distractor_reason, p.rationale, p.remedy, p.origin_read[0],
             p.origin_read[1], p.healthy_origin_content, p.origin_state[0],
             p.origin_state[1], p.notes]
    for broken, healthy in p.origin_variants:
        parts += [broken, healthy]
    for v in p.victims:
        parts += _victim_blob(v)
    return parts


# ---------------------------------------------------------------- the pool

def test_a_ruled_scenario_pool_exists_with_six_stories():
    assert len(RULED) == 6


def test_ruled_scenario_keys_are_disjoint_from_eval_and_trainable():
    ruled_keys = {p.key for p in RULED}
    assert len(ruled_keys) == len(RULED), "a ruled key repeats within the pool"
    assert not ruled_keys & {p.key for p in EVAL}
    assert not ruled_keys & {p.key for p in TRAINABLE}


def test_no_ruled_scenario_reuses_an_eval_or_trainable_answer_string():
    """Mirrors `test_no_trainable_scenario_reuses_an_eval_answer_string`:
    a ruled story's `shared_cause`/`distractor_cause` must not equal one
    from either existing pool, or a pass could be explained by having seen
    the string rather than having read the evidence."""
    def answers(pool):
        out = set()
        for p in pool:
            out.add(p.shared_cause)
            out.add(p.distractor_cause)
        return out

    ruled_answers = answers(RULED)
    assert len(ruled_answers) == 2 * len(RULED), "a ruled answer repeats within the pool"
    assert not ruled_answers & answers(EVAL)
    assert not ruled_answers & answers(TRAINABLE)


def test_no_ruled_scenario_shares_a_local_cause_with_trainable():
    """Mirrors `test_no_two_trainable_scenarios_share_a_local_cause`."""
    def local_causes(pool):
        return [v.local_cause for p in pool for v in p.victims]

    ruled_causes = local_causes(RULED)
    assert len(ruled_causes) == len(set(ruled_causes)), "a ruled local_cause repeats"
    assert not set(ruled_causes) & set(local_causes(TRAINABLE))


@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
def test_every_ruled_scenario_obeys_the_authoring_floor(p):
    """Mirrors `test_trainable_scenarios_obey_every_rule_the_eval_table_obeys`."""
    assert p.blast_radius in ("cluster", "node", "namespace")
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p.key)
    assert 2 <= len(p.victims) <= 4
    assert p.shared_verdict != "attributed"
    assert p.confidence in ("high", "medium", "low")
    for v in p.victims:
        assert v.issue in vocab.ISSUE_KINDS
        assert v.pass_confidence in ("high", "medium", "low")
    local_causes = [v.local_cause for v in p.victims]
    assert len(local_causes) == len(set(local_causes))


def test_blast_radius_and_scope_field_agree_for_every_ruled_scenario():
    scope_for_radius = {"cluster": None, "node": "node", "namespace": "ns"}
    for p in RULED:
        assert p.scope_field == scope_for_radius[p.blast_radius], p.key


def test_every_ruled_scenario_has_at_least_three_victims():
    for p in RULED:
        assert len(p.victims) >= 3, p.key


def test_pass_confidence_varies_within_every_ruled_scenario():
    for p in RULED:
        grades = {v.pass_confidence for v in p.victims}
        assert len(grades) > 1, p.key


def test_every_ruled_scenario_carries_a_healthy_origin_read():
    for p in RULED:
        assert p.healthy_origin_content.strip(), p.key


def test_every_ruled_scenario_declares_at_least_four_origin_variants():
    for p in RULED:
        assert len(p.origin_variants) >= 4, p.key
        assert p.origin_variants[0] == (p.origin_read[1], p.healthy_origin_content), p.key


def test_every_ruled_variant_first_line_is_literal_and_unique_within_its_scenario():
    for p in RULED:
        first_lines = []
        for broken, healthy in p.origin_variants:
            for text in (broken, healthy):
                line = text.split("\n")[0]
                assert line, p.key
                assert "{" not in line, (p.key, line)
                first_lines.append(line)
        assert len(first_lines) == len(set(first_lines)), p.key


def test_every_ruled_scenario_names_its_state_in_words():
    for p in RULED:
        broken_token, healthy_token = p.origin_state
        assert broken_token and any(ch.isalpha() for ch in broken_token), p.key
        assert healthy_token and any(ch.isalpha() for ch in healthy_token), p.key
        for broken, healthy in p.origin_variants:
            assert broken_token in broken and broken_token not in healthy, p.key
            assert healthy_token in healthy and healthy_token not in broken, p.key


def test_a_ruled_victim_read_never_asserts_a_broken_origin_on_the_healthy_half():
    for p in RULED:
        broken_token = p.origin_state[0]
        for v in p.victims:
            if broken_token in v.read[1]:
                assert v.healthy_read_content, (p.key, v.workload_kind)
                assert broken_token not in v.healthy_read_content, (p.key, v.workload_kind)


def test_no_ruled_scenario_text_carries_a_banned_identifier_shape():
    """Mirrors `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`."""
    for p in RULED:
        blob = "\n".join(_scenario_blob(p))
        assert not _IPV4.search(blob), p.key
        assert not _URL.search(blob), p.key
        assert "kubeconfig" not in blob.lower(), p.key
        assert "/home/" not in blob, p.key
        assert "@" not in blob, p.key


def test_no_ruled_scenario_phrase_leaks_a_shared_or_independence_claim():
    """Spec section 4, 'Phrases': origin, shared_cause and remedy contain no
    independence phrase and no shared-claim phrase, so the wording itself
    cannot give the label away."""
    banned = tuple(x.lower() for x in cases.SHARED_CLAIM_PHRASES) + _INDEPENDENCE_PHRASES
    for p in RULED:
        for field_name in ("origin", "shared_cause", "remedy"):
            text = getattr(p, field_name).lower()
            for phrase in banned:
                assert phrase not in text, (p.key, field_name, phrase)


def test_ruled_origin_read_label_is_never_an_exam_only_label():
    """Spec section 4: the pinned exam-only label set. A trainable OR ruled
    story's origin_read label must never be one of the four."""
    for p in list(RULED) + list(TRAINABLE):
        assert p.origin_read[0] not in _EXAM_ONLY_LABELS, p.key


# --------------------------------------------------------- story-specific

def test_ruled_node_stories_never_mention_a_lease_or_heartbeat():
    for p in RULED:
        if p.key not in NODE_KEYS:
            continue
        blob = "\n".join(_scenario_blob(p)).lower()
        assert "lease" not in blob, p.key
        assert "heartbeat" not in blob, p.key


def test_ruled_pvc_storage_classes_are_new_and_plain():
    taken = {"fast-ssd", "standard", "ssd-premium", "block-ssd", "archive-hdd",
             "encrypted-ssd", "bulk-nvme", "replicated-ssd"}
    seen = set()
    for p in RULED:
        if p.key not in PVC_STORAGE_CLASSES:
            continue
        sc = PVC_STORAGE_CLASSES[p.key]
        assert sc not in taken, sc
        assert sc not in seen, sc
        seen.add(sc)
        alphabet = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
        assert sc and all(ch in alphabet for ch in sc), sc
        assert p.origin_object.fresh.storage_class == sc
        assert p.healthy_origin_fresh.storage_class == sc
        # Spec section 4, "Healthy PVC and registry content": the
        # storage-class read names no specific claim, container or image --
        # none of the four Names placeholders appears anywhere in it, so it
        # reads true for every claim in the row, not just one.
        for placeholder in ("{pvc}", "{pod}", "{image}", "{name}"):
            assert placeholder not in p.origin_read[1], (p.key, placeholder)
            assert placeholder not in p.healthy_origin_content, (p.key, placeholder)
            for broken, healthy in p.origin_variants:
                assert placeholder not in broken, (p.key, placeholder)
                assert placeholder not in healthy, (p.key, placeholder)


def test_ruled_registry_hosts_are_new_and_scan_reason_is_the_count_template():
    seen = set()
    for p in RULED:
        if p.key not in REGISTRY_KEYS:
            continue
        host = p.origin_object.name
        assert host not in ("registry.example.com",), host
        assert host not in seen, host
        seen.add(host)
        assert p.origin_object.scan_reason == "{count}", p.key
        assert p.origin_object.fresh.literal in (
            "no such host", "toomanyrequests"), p.key
        assert p.healthy_origin_fresh.literal == "manifest unknown", p.key
        for v in p.victims:
            assert v.issue in ("ImagePullBackOff", "ErrImagePull"), (p.key, v.issue)


_WORKLOAD_KINDS = ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob")


_COUNT_PHRASE = re.compile(
    r"\d+\s*(workloads?|pods?|replicas?|hosts?|instances?|callers?)\b",
    re.IGNORECASE,
)


def test_ruled_registry_content_carries_no_count_and_names_no_workload():
    """Spec section 4, "Healthy PVC and registry content": a registry
    story's own scan_reason is the `{count}` template filled in at render
    time (Task 6), so the free-form origin content must never also bake in
    a fixed count of its own -- that would either duplicate the rendered
    number by luck or contradict it on a row that draws a different one.
    A response code or port number is not a count (e.g. "429" or "200" in
    a status-code reading), so the check targets a digit next to a
    countable noun rather than every digit. Registry content also names no
    workload kind: the origin is about the registry, not one caller of it.
    """
    for p in RULED:
        if p.key not in REGISTRY_KEYS:
            continue
        texts = [p.origin_read[1], p.healthy_origin_content]
        for broken, healthy in p.origin_variants:
            texts += [broken, healthy]
        for text in texts:
            assert not _COUNT_PHRASE.search(text), (p.key, text)
            for kind in _WORKLOAD_KINDS:
                assert kind not in text, (p.key, kind, text)


# ----------------------------------------------------------- rendered rows

@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
@pytest.mark.parametrize("victims", (2, 3))
def test_ruled_scenario_renders_shared_on_broken_and_none_on_healthy(p, victims):
    for salt in (1, 2, 3, 4, 5):
        broken = cases.shared_origin(p, random.Random(salt), victims=victims)
        healthy = cases.shared_origin_decoy(p, random.Random(salt), victims=victims)
        assert broken.meta["label"] == "shared", (p.key, victims, salt)
        assert healthy.meta["label"] == "none", (p.key, victims, salt)


@pytest.mark.parametrize("p", RULED, ids=[p.key for p in RULED])
def test_ruled_scenario_coherence_across_victim_counts_and_salts(p):
    """Spec section 4, 'Coherence', checked on the RENDERED row rather than
    the literal alone: the broken twin's origin read carries the broken
    state word, the healthy twin's carries the healthy one, and a node
    story never renders a lease or heartbeat mention either way."""
    broken_token, healthy_token = p.origin_state
    for victims in (2, 3):
        for salt in (1, 2, 3):
            r_broken = cases._render_shared_origin(p, random.Random(salt), victims,
                                                    healthy=False)
            r_healthy = cases._render_shared_origin(p, random.Random(salt), victims,
                                                     healthy=True)
            assert broken_token in r_broken.user, (p.key, victims, salt)
            assert healthy_token in r_healthy.user, (p.key, victims, salt)
            if p.key in NODE_KEYS:
                assert "lease" not in r_broken.user.lower()
                assert "heartbeat" not in r_broken.user.lower()
                assert "lease" not in r_healthy.user.lower()
                assert "heartbeat" not in r_healthy.user.lower()
            if p.key in PVC_STORAGE_CLASSES:
                assert PVC_STORAGE_CLASSES[p.key] in r_broken.user
            if p.key in REGISTRY_KEYS:
                host = p.origin_object.name
                assert host in r_broken.user
                assert p.origin_object.fresh.literal in r_broken.user


@pytest.mark.parametrize(
    "key,host", [("registry-mirror-unreachable", "mirror.invalid"),
                 ("registry-rate-limited", "registry.invalid")])
def test_ruled_registry_row_names_its_own_rendered_victim_count(key, host):
    """The Task 6 fix (spec section 4, 'Registry count'), applied to the real
    ruled registry stories rather than a scenario built in the test: the
    rules pass's own cause line names however many victims THIS row draws,
    never a fixed digit."""
    p = next(s for s in RULED if s.key == key)
    for victims in (2, 3):
        r = cases._render_shared_origin(p, random.Random(7), victims, healthy=False)
        assert f"registry {host} ({victims} workloads failing to pull)" in r.user


# --------------------------------------------------- the unverified twin

# Spec section 5: one node pair in three gets an unverified broken twin
# instead of the confirmed one. `shared_origin(..., unverified=True)` is
# only ever the BROKEN half -- there is no unverified decoy variant --
# so every check below compares it against the plain broken twin's
# names/menus/labels (both consume the rng identically: the origin
# variant draw, then one draw per victim's own name) and against the
# healthy twin's summary shape only where the two are expected to differ.

PVC_KEYS = set(PVC_STORAGE_CLASSES)
NOT_NODE_KEYS = PVC_KEYS | REGISTRY_KEYS


@pytest.mark.parametrize("key", sorted(NOT_NODE_KEYS))
def test_unverified_true_raises_for_a_ruled_pvc_or_registry_story(key):
    p = next(s for s in RULED if s.key == key)
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(p, random.Random(1), 2, unverified=True)


def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = next(s for s in TRAINABLE if s.origin_object is None)
    with pytest.raises(ValueError, match="unverified"):
        cases._render_shared_origin(plain, random.Random(1), 2, unverified=True)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_labels_none_with_the_did_not_confirm_summary(key, victims):
    p = next(s for s in RULED if s.key == key)
    for salt in (1, 2, 3, 4, 5):
        r = cases._render_shared_origin(p, random.Random(salt), victims, unverified=True)
        assert r.meta["label"] == "none", (key, victims, salt)
        assert r.summary.startswith(
            f"{victims} workloads are failing, and kubeagent's rules did "
            "not confirm one cause on two or more of them."), (key, victims, salt)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_origin_read_says_read_failed_is_forbidden(key):
    p = next(s for s in RULED if s.key == key)
    r = cases._render_shared_origin(p, random.Random(1), 2, unverified=True)
    node = p.origin_object.name  # "{node}" -- the template, not the drawn value
    assert node == "{node}"
    drawn_node = r.drawn[0].node
    assert f'read failed: nodes "{drawn_node}" is forbidden' in r.user


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_every_row_decided_unverified_with_rules_cause(key, victims):
    p = next(s for s in RULED if s.key == key)
    r = cases._render_shared_origin(p, random.Random(2), victims, unverified=True)
    assert len(r.rows) == victims
    for row in r.rows:
        assert row["cause"].startswith("node ") and row["cause"].endswith("(NotReady)"), row
        assert "did not clear the earlier finding" in row["rationale"], row
        assert "is forbidden" in row["rationale"], row


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_workloads_meta_marks_decided_outcome_unverified(key):
    p = next(s for s in RULED if s.key == key)
    ex = cases.shared_origin(p, random.Random(3), victims=2, unverified=True)
    assert ex.meta["workloads"], key
    for wm in ex.meta["workloads"].values():
        assert wm["decided"] is True, key
        assert wm["decided_outcome"] == "unverified", key
        assert wm["job"] == 1, key


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
@pytest.mark.parametrize("victims", (2, 3))
def test_unverified_node_twin_job1_accepts_every_row(key, victims):
    p = next(s for s in RULED if s.key == key)
    ex = cases.shared_origin(p, random.Random(4), victims=victims, unverified=True)
    verdicts = {row["workload"]: row for row in json.loads(ex.assistant)["verdicts"]}
    assert set(verdicts) == set(ex.meta["workloads"])
    for wkey, wm in ex.meta["workloads"].items():
        assert score.job1(wm, verdicts[wkey]) == 1.0, (key, victims, wkey)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_matches_the_healthy_twins_names_menus_and_labels(key):
    """Both calls draw the origin variant, then one name per victim, in the
    same order and with no other rng draw (the origin-object branch takes
    no `render.draw_ending` draw) -- so at the same salt the two twins'
    drawn names, candidate menus and read labels line up exactly. Only the
    origin read's own content, and the per-victim reads a broken origin
    touches, are allowed to differ."""
    p = next(s for s in RULED if s.key == key)
    for victims in (2, 3):
        for salt in (1, 2, 3):
            unverified = cases._render_shared_origin(
                p, random.Random(salt), victims, unverified=True)
            healthy = cases._render_shared_origin(
                p, random.Random(salt), victims, healthy=True)
            assert unverified.drawn == healthy.drawn, (key, victims, salt)
            assert unverified.decoys == healthy.decoys, (key, victims, salt)
            assert unverified.shared_cause == healthy.shared_cause, (key, victims, salt)
            assert unverified.distractor_cause == healthy.distractor_cause, (key, victims, salt)
            assert [r["workload"] for r in unverified.rows] == \
                [r["workload"] for r in healthy.rows], (key, victims, salt)
