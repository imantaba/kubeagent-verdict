import dataclasses
import random
import re

import pytest

from kubeagent_verdict.dataset import catalog, gather, gold
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.dataset import stories as s
from kubeagent_verdict.dataset.checker import LOG_CAUSES


def test_answer_keys_are_checked():
    with pytest.raises(ValueError, match="key"):
        s.Answer(anchor="x", cause="its probe fails", keys=("Probe",), rationale="r")
    with pytest.raises(ValueError, match="key"):
        s.Answer(anchor="x", cause="its probe fails", keys=("dns",), rationale="r")
    with pytest.raises(ValueError, match="inside"):
        s.Answer(anchor="x", cause="its probe fails", keys=("timeout",), rationale="r")
    with pytest.raises(ValueError, match="1 to 3"):
        s.Answer(anchor="x", cause="a b c d", keys=(), rationale="r")
    with pytest.raises(ValueError, match="rationale"):
        s.Answer(anchor="x", cause="its probe fails", keys=("probe",), rationale="")


def test_log_label_never_links():
    a = s.Answer(anchor="log cause: port already in use", cause="its port is already in use",
                 keys=("port",), rationale="r", link=True)
    with pytest.raises(ValueError, match="log"):
        s.validate_answer(a)


def test_pilots_are_present_and_valid():
    by = s.by_key()
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        st = by[key]
        assert st.cls in s.CLASSES and st.scope_field in s.SCOPES
        assert st.origin_kind in s.ORIGIN_KINDS
        assert len(st.victims) >= 2
        for v in st.victims:
            for log in (v.log, v.log_healthy):
                assert log in (None, "", s.NO_PREVIOUS, s.NO_CLASSIFIABLE) or log in LOG_CAUSES


def test_exam_order_and_trainable_disjoint():
    exam = [st.key for st in s.exam()]
    assert exam == [k for k in s.EXAM_KEYS if k in s.by_key()]
    assert not {st.key for st in s.trainable()} & set(s.EXAM_KEYS)


def test_crash_family_logs_are_never_empty():
    # gather reads a log for a crash-family issue; an empty one would print a
    # bare "log cause: ". _pick treats "" as set, so log_healthy="" is refused too.
    for key, st in s.by_key().items():
        rows = list(st.victims)
        for world in (st.broken, st.healthy):
            if world.origin_row is not None:
                rows.append(world.origin_row)
        for t in rows:
            if t.issue not in gather.CRASH_FAMILY:
                continue
            assert t.log, (key, t.issue, "log")
            if getattr(t, "log_healthy", None) is not None:
                assert t.log_healthy, (key, t.issue, "log_healthy")


def _both(st, seed=0):
    d = so.draw(st, random.Random(seed), width=len(st.victims))
    return so.build(st, d, world="broken"), so.build(st, d, world="healthy")


def _all():
    return tuple(s.by_key().values())


def test_no_dropped_story_is_kept():
    assert not set(s.DROPPED) & set(s.by_key())
    assert len(s.DROPPED) == 13


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_worlds_differ_in_a_printed_line(st):
    b, h = _both(st)
    assert set(b.user.splitlines()) != set(h.user.splitlines())


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_every_answer_anchor_shows_in_its_world(st):
    b, h = _both(st)
    for built, pick in ((b, "broken"), (h, "healthy")):
        own = gold.own_lines(built.user, [r.key for r in built.rows])
        for row in built.rows:
            a = row.text.answer if row.role == "origin" else getattr(row.text, pick)
            if a is None or row.result.decided:
                continue
            s.validate_answer(a)
            anchor = gold._norm_cause(so._sub(a.anchor, row.names, built.draw))
            assert any(anchor in ln for ln in gold.anchor_lines(own[row.key], row)), \
                (st.key, pick, row.key, anchor)


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_cross_world_keys_share_nothing(st):
    for v in st.victims:
        if v.broken and v.healthy:
            assert not set(v.broken.keys) & set(v.healthy.keys), st.key


@pytest.mark.parametrize("st", [x for x in _all() if x.cls == "R"], ids=lambda st: st.key)
def test_r_stories_confirm_in_broken_only(st):
    b, h = _both(st)
    assert gold.gold_for(b).label == "shared"
    assert all(r.result.decided for r in b.rows if r.role == "victim")
    assert not any(r.result.decided for r in h.rows)
    assert gold.gold_for(h).label == "none"


R_TRAINABLE = ("node-kubelet-halted", "node-kubelet-unresponsive",
               "pvc-provisioner-not-responding", "pvc-storageclass-missing",
               "registry-mirror-unreachable", "registry-rate-limited")


def test_the_r_stories_are_present():
    by = s.by_key()
    for key in R_TRAINABLE + ("storage-provisioner-down", "registry-unreachable"):
        assert by[key].cls == "R", key
    assert [st.key for st in s.trainable() if st.cls == "R"] == list(R_TRAINABLE)
    assert {"storage-provisioner-down", "registry-unreachable"} <= {st.key for st in s.exam()}
    for key in R_TRAINABLE:
        assert len(by[key].victims) == 3, key


# --- shape guards over every story ---------------------------------------

_BANNED = (
    ("an IPv4 address", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("a URL", re.compile(r"https?://")),
    ("kubeconfig", re.compile(r"kubeconfig", re.IGNORECASE)),
    ("a home path", re.compile(r"/home/")),
    ("an @", re.compile(r"@")),
)


def _strings(obj, path="story"):
    """Every string inside a (nested) dataclass or tuple, with where it sits."""
    if isinstance(obj, str):
        yield path, obj
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _strings(getattr(obj, f.name), f"{path}.{f.name}")
    elif isinstance(obj, (tuple, list)):
        for i, x in enumerate(obj):
            yield from _strings(x, f"{path}[{i}]")


def _answers(obj):
    if isinstance(obj, s.Answer):
        yield obj
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _answers(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for x in obj:
            yield from _answers(x)


def test_the_string_walker_sees_nested_fields():
    st = s.by_key()["coredns-down"]
    seen = dict(_strings(st))
    assert "story.broken.origin_row.answer.cause" in seen
    assert any(p.startswith("story.victims[1].events[0]") for p in seen)


@pytest.mark.parametrize("st", s.trainable(), ids=lambda st: st.key)
def test_trainable_stories_carry_no_banned_shape(st):
    for path, text in _strings(st):
        for what, rx in _BANNED:
            assert not rx.search(text), (st.key, path, what, text)


def test_exam_origin_keys_match_no_catalog_entry():
    # D3 checks the catalog's own-cause keywords against the exam's origin
    # keys; this fails at authoring time rather than late.
    own = {tuple(e.own_cause_keywords) for e in catalog.all_entries()}
    assert own
    for st in s.exam():
        for w in (st.broken, st.healthy):
            if w.origin_row is not None and w.origin_row.answer is not None:
                assert w.origin_row.answer.keys not in own, st.key


def test_every_answer_key_is_lowercase():
    # gold.check_keys tests `k in line.lower()` and never lowers k.
    n = 0
    for st in _all():
        for a in _answers(st):
            n += 1
            assert all(k == k.lower() for k in a.keys), (st.key, a.keys)
    assert n


def test_counts():
    by = s.by_key()
    assert len(by) == 47
    assert sum(st.cls == "P" for st in by.values()) == 38
    tr = s.trainable()
    assert len(tr) == 41
    assert [st.cls for st in tr] == ["P"] * 35 + ["R"] * 6
    assert [st.key for st in tr[35:]] == list(s.RULED_ORDER)
    assert [st.key for st in s.exam()] == list(s.EXAM_KEYS)


def test_named_edits():
    by = s.by_key()
    assert any(cd.type == "PIDPressure" and cd.status == "True"
               for cd in by["node-pid-pressure"].broken.conditions)
    assert by["networkpolicy-deny-all"].healthy.policies == ()
    for key in ("networkpolicy-egress-allowlist-stale", "networkpolicy-dns-egress-missing",
                "networkpolicy-namespace-label-drifted", "networkpolicy-port-mismatch",
                "networkpolicy-allow-selector-typo", "networkpolicy-ingress-deny-all",
                "shared-pvc-multi-attach", "csi-driver-version-mismatch"):
        assert any(v.events_healthy is not None or v.evidence_healthy is not None
                   or v.log_healthy is not None for v in by[key].victims), key


def test_p_labels_are_mixed():
    labels = []
    for st in s.trainable():
        if st.cls != "P":
            continue
        b, _ = _both(st)
        labels.append(gold.gold_for(b).label)
    assert labels.count("shared") >= 5 and labels.count("none") >= 5, labels
