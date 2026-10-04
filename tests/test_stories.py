import pytest

from kubeagent_verdict.dataset import gather
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
