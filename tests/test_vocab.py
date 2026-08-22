from kubeagent_verdict import vocab


def test_fault_slugs_closed_at_17():
    assert len(vocab.FAULT_SLUGS) == 17
    assert "unknown-scenario" not in vocab.FAULT_SLUGS
    assert "crashloop-pod" in vocab.FAULT_SLUGS


def test_issue_kinds_closed_at_16():
    assert len(vocab.ISSUE_KINDS) == 16
    assert "CrashLoopBackOff" in vocab.ISSUE_KINDS
    assert "Init:OOMKilled" in vocab.ISSUE_KINDS


def test_verdicts():
    assert vocab.VERDICTS == frozenset({"attributed", "ruled_out", "outranked"})
