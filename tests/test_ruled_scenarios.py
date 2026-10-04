"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.trainable_scenarios()` now returns the 48 plain
stories plus these six (spec section 6's pool merge), so every check below
that means "disjoint from the plain pool" filters `trainable_scenarios()`
down to `PLAIN` first rather than comparing against the merged pool --
comparing the six ruled stories against a pool that now contains them
would always pass, vacuously. It still has to clear the same authoring
floor and the same eval-disjointness rules the plain pool already clears,
which is why several checks below mirror a named test in
`test_shared_origin_training.py` rather than inventing a new shape.

Two groups of tests live here. The table tests read `propagation.py`'s
`ruled_scenarios()` directly: that data is unchanged and `multi` still
draws it. The rendered-row tests (the last section) build the same six
keys from `stories.py` through the real pipeline. A ruled story's BROKEN
world puts a real object behind every victim (a NotReady node, a Pending
claim, a registry whose pulls fail), so the rules pass confirms each one
against the same group key and the label is "shared"; the HEALTHY world
has no such object, no victim is decided, and the label is "none". That is
asserted directly, by building both worlds, rather than trusted from the
story's shape.
"""

import json
import random
import re

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, propagation, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score

RULED = propagation.ruled_scenarios()
PLAIN = tuple(p for p in propagation.trainable_scenarios() if p.origin_object is None)
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
    assert not ruled_keys & {p.key for p in PLAIN}


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
    assert not ruled_answers & answers(PLAIN)


def test_no_ruled_scenario_shares_a_local_cause_with_trainable():
    """Mirrors `test_no_two_trainable_scenarios_share_a_local_cause`."""
    def local_causes(pool):
        return [v.local_cause for p in pool for v in p.victims]

    ruled_causes = local_causes(RULED)
    assert len(ruled_causes) == len(set(ruled_causes)), "a ruled local_cause repeats"
    assert not set(ruled_causes) & set(local_causes(PLAIN))


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
    for p in list(RULED) + list(PLAIN):
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

# The rendered-row tests below build each ruled story through the real
# pipeline (`so.draw` then `so.build`) and read the prompt it prints.
# `propagation.ruled_scenarios()` above and `stories.RULED_ORDER` here must
# name the same six keys, or the two halves of this file would be checking
# different things.

DECIDED = "    decided by rules: "
REGISTRY_HOST = "registry.example.com"


def _story(key):
    return stories.by_key()[key]


def _widths(st):
    """Every row width the story can render: 2 up to all of its victims."""
    return range(2, len(st.victims) + 1)


def _built(st, world, width, salt=7, unverified=False):
    d = so.draw(st, random.Random(salt), width=width)
    return so.build(st, d, world=world, unverified=unverified)


def _summary(ex):
    return json.loads(ex.assistant)["summary"]


RULED_ROWS = [(key, w) for key in stories.RULED_ORDER for w in _widths(_story(key))]
RULED_IDS = [f"{key}-{w}" for key, w in RULED_ROWS]
NODE_ROWS = [(key, w) for key, w in RULED_ROWS if key in NODE_KEYS]
NODE_IDS = [f"{key}-{w}" for key, w in NODE_ROWS]

PVC_KEYS = set(PVC_STORAGE_CLASSES)

# What each node story's broken prompt prints for the origin node's state
# (measured at Task 8): the halted node is NotReady; the unresponsive one is
# Ready with a stale lease, and its cause reads "kubelet not heartbeating".
NODE_STATE_MARK = {
    "node-kubelet-halted": "NotReady",
    "node-kubelet-unresponsive": "kubelet not heartbeating",
}
NODE_CAUSE_END = {
    "node-kubelet-halted": "(NotReady)",
    "node-kubelet-unresponsive": "(kubelet not heartbeating)",
}
NOT_NODE_KEYS = PVC_KEYS | REGISTRY_KEYS


def test_the_ruled_stories_are_the_six_ruled_scenarios():
    """The table tests read `propagation.ruled_scenarios()`; the rendered-row
    tests read `stories.RULED_ORDER`. Both must name the same six keys."""
    assert set(stories.RULED_ORDER) == {p.key for p in RULED}
    assert len(stories.RULED_ORDER) == 6
    assert set(stories.RULED_ORDER) == NODE_KEYS | PVC_KEYS | REGISTRY_KEYS


@pytest.mark.parametrize("key,victims", RULED_ROWS, ids=RULED_IDS)
def test_ruled_scenario_renders_shared_on_broken_and_none_on_healthy(key, victims):
    st = _story(key)
    for salt in (1, 2, 3, 4, 5):
        broken = cases.shared_origin(st, random.Random(salt), victims=victims)
        healthy = cases.shared_origin_decoy(st, random.Random(salt), victims=victims)
        assert broken.meta["label"] == "shared", (key, victims, salt)
        assert healthy.meta["label"] == "none", (key, victims, salt)


@pytest.mark.parametrize("key", stories.RULED_ORDER)
def test_ruled_scenario_coherence_across_victim_counts_and_salts(key):
    """Spec section 4, 'Coherence', checked on the BUILT prompt: in the
    broken world every victim is decided by the rules and the prompt shows
    the origin's own state (a NotReady node, the claim's storage class, the
    registry cause line); in the healthy world no victim is decided and none
    of that state is printed."""
    st = _story(key)
    for victims in _widths(st):
        for salt in (1, 2, 3):
            broken = _built(st, "broken", victims, salt)
            healthy = _built(st, "healthy", victims, salt)
            where = (key, victims, salt)
            assert all(r.result.decided for r in broken.rows), where
            assert not any(r.result.decided for r in healthy.rows), where
            assert broken.user.count(DECIDED) == victims, where
            assert DECIDED not in healthy.user, where
            if key in NODE_KEYS:
                # Task 8: a halted kubelet's node is NotReady; an unresponsive
                # kubelet's node is still Ready, with a stale lease, and the
                # fresh read shows Ready=Unknown. The healthy prompt says
                # neither.
                mark = NODE_STATE_MARK[key]
                assert mark in broken.user, where
                assert mark not in healthy.user, where
                assert "NotReady" not in healthy.user, where
                assert "kubelet not heartbeating" not in healthy.user, where
                if key == "node-kubelet-unresponsive":
                    assert "NotReady" not in broken.user, where
                    assert "Ready=Unknown (NodeStatusUnknown)" in broken.user, where
            if key in PVC_KEYS:
                mark = f"storageClass={st.broken.pvc_class}"
                assert mark in broken.user, where
                assert mark not in healthy.user, where
            if key in REGISTRY_KEYS:
                assert f"{DECIDED}registry {REGISTRY_HOST} (" in broken.user, where


@pytest.mark.parametrize("key", sorted(REGISTRY_KEYS))
def test_ruled_registry_row_names_its_own_rendered_victim_count(key):
    """The Task 6 fix (spec section 4, 'Registry count'), applied to the real
    ruled registry stories: the rules pass's own cause line names however
    many victims THIS row draws, never a fixed digit."""
    st = _story(key)
    for victims in _widths(st):
        b = _built(st, "broken", victims)
        cause = f"registry {REGISTRY_HOST} ({victims} workloads failing to pull)"
        assert b.user.count(f"{DECIDED}{cause} — confirmed") == victims, (key, victims)


# --------------------------------------------------- the unverified twin

# Spec section 5: one node pair in three gets an unverified broken twin
# instead of the confirmed one. `shared_origin(..., unverified=True)` is
# only ever the BROKEN half -- there is no unverified decoy variant --
# so every check below compares it against the healthy twin's names and
# label only where the two are expected to agree, and reads its own
# prompt, verdicts and meta everywhere else. (A refused read cannot be
# unverified when there is no down node to refuse, hence the ValueError
# guards: Ruling 31.)


@pytest.mark.parametrize("key", sorted(NOT_NODE_KEYS))
def test_unverified_true_raises_for_a_ruled_pvc_or_registry_story(key):
    st = _story(key)
    with pytest.raises(ValueError, match="unverified"):
        _built(st, "broken", 2, salt=1, unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(st, random.Random(1), victims=2, unverified=True)


def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = next(st for st in stories.trainable() if st.cls == "P")
    with pytest.raises(ValueError, match="unverified"):
        _built(plain, "broken", 2, salt=1, unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(plain, random.Random(1), victims=2, unverified=True)


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_labels_none_with_the_did_not_confirm_summary(key, victims):
    st = _story(key)
    for salt in (1, 2, 3, 4, 5):
        ex = cases.shared_origin(st, random.Random(salt), victims=victims, unverified=True)
        assert ex.meta["label"] == "none", (key, victims, salt)
        assert _summary(ex).startswith(
            f"{victims} workloads are failing, and kubeagent's rules did "
            "not confirm one cause on two or more of them."), (key, victims, salt)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_origin_read_says_read_failed_is_forbidden(key):
    st = _story(key)
    b = _built(st, "broken", 2, salt=1, unverified=True)
    node = b.draw.scope_value
    assert node, key
    assert f'read failed: nodes "{node}" is forbidden' in b.user


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_every_row_decided_unverified_with_rules_cause(key, victims):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(2), victims=victims, unverified=True)
    rows = json.loads(ex.assistant)["verdicts"]
    assert len(rows) == victims
    for row in rows:
        assert row["cause"].startswith("node ") and row["cause"].endswith(NODE_CAUSE_END[key]), row
        assert "did not clear the earlier finding" in row["rationale"], row
        assert "is forbidden" in row["rationale"], row


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_workloads_meta_marks_decided_outcome_unverified(key):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(3), victims=2, unverified=True)
    assert ex.meta["workloads"], key
    for wm in ex.meta["workloads"].values():
        assert wm["decided"] is True, key
        assert wm["decided_outcome"] == "unverified", key
        assert wm["job"] == 1, key


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_job1_accepts_every_row(key, victims):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(4), victims=victims, unverified=True)
    verdicts = {row["workload"]: row for row in json.loads(ex.assistant)["verdicts"]}
    assert set(verdicts) == set(ex.meta["workloads"])
    for wkey, wm in ex.meta["workloads"].items():
        assert score.job1(wm, verdicts[wkey]) == 1.0, (key, victims, wkey)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_matches_the_healthy_twins_names_and_labels(key):
    """`so.draw` makes every rng call before it looks at the world (Ruling
    11), so at the same salt the unverified twin and the healthy twin share
    a pair name, an origin node and the same workloads in the same order.
    Both are labelled "none". What each prompt prints, and what each
    verdict says, is allowed to differ and is not compared here."""
    st = _story(key)
    for victims in _widths(st):
        for salt in (1, 2, 3):
            unverified = cases.shared_origin(
                st, random.Random(salt), victims=victims, unverified=True)
            healthy = cases.shared_origin_decoy(st, random.Random(salt), victims=victims)
            where = (key, victims, salt)
            assert unverified.group == healthy.group, where
            assert unverified.meta["origin"] == healthy.meta["origin"] == key, where
            assert unverified.meta["scope_value"] == healthy.meta["scope_value"], where
            assert list(unverified.meta["workloads"]) == list(healthy.meta["workloads"]), where
            assert list(unverified.meta["expected"]) == list(healthy.meta["expected"]), where
            assert unverified.meta["label"] == healthy.meta["label"] == "none", where
