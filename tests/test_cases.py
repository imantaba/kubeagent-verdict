import ast
import dataclasses
import json
import pathlib
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, render
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset.render import object_reads
from kubeagent_verdict.evals import score


def _entry(key):
    return next(e for e in catalog.all_entries() if e.key == key)


def test_attributed_example_shape():
    n = names_mod.draw(random.Random(11))
    ex = cases.attributed(_entry("memory-limit-oomkill"), n, random.Random(11))
    assert ex.case == "attributed"
    assert ex.group == f"memory-limit-oomkill:{n.ns}/{n.name}"
    assert ex.system == c.SYSTEM_PROMPT
    assert f"- {n.ns}/{n.name} (Deployment)" in ex.user
    assert "== BEGIN candidates ==" in ex.user
    assert "considered memory limit too low for the workload: attributed" in ex.user
    doc = json.loads(ex.assistant)
    assert set(doc) == {"verdicts", "summary"}
    (row,) = doc["verdicts"]
    assert row["workload"] == f"{n.ns}/{n.name}"
    assert row["cause"] == "memory limit too low for the workload"
    assert row["confidence"] == "high"  # direct=True entry with full evidence
    assert ex.meta["expected_cause"] == row["cause"]


def test_attributed_indirect_entry_gets_medium():
    n = names_mod.draw(random.Random(12))
    ex = cases.attributed(_entry("probe-failure"), n, random.Random(12))
    assert json.loads(ex.assistant)["verdicts"][0]["confidence"] == "medium"


def test_attributed_user_message_is_contract_valid():
    n = names_mod.draw(random.Random(13))
    ex = cases.attributed(_entry("deployment-bad-image-tag"), n, random.Random(13))
    assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
    assert ex.user.endswith(c.CLOSING_INSTRUCTION)


def test_attributed_menu_comes_from_declared_objects_not_losers():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(7))
    stripped = dataclasses.replace(e, objects=())
    ex_full = cases.attributed(e, n, random.Random(7))
    ex_stripped = cases.attributed(stripped, n, random.Random(7))
    assert ex_full.user.count("considered") > ex_stripped.user.count("considered")


def test_none_of_these_names_no_cause_and_answers_none_at_low():
    n = names_mod.draw(random.Random(21))
    ex = cases.none_of_these_case(_entry("crashloop-pod"), n, shape="refuted")
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == c.NONE_OF_THESE
    assert row["confidence"] == "low"
    # Thin evidence: the finding's log-cause line is gone; the log read
    # stays but its content no longer names a cause.
    assert "log cause:" not in ex.user


def test_own_cause_omits_winner_from_candidates():
    n = names_mod.draw(random.Random(22))
    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n)
    cand_section = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    assert "memory limit too low for the workload" not in cand_section
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"
    assert ex.meta["expected_own_keywords"] == ["memory", "limit"]


def test_truncated_case_earns_low_confidence():
    n = names_mod.draw(random.Random(23))
    ex = cases.truncated(_entry("crashloop-pod"), n, random.Random(23))
    assert c.TRUNCATION_MARKER in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["confidence"] == "low"


def test_injection_answer_ignores_payload():
    n = names_mod.draw(random.Random(24))
    payload = cases.INJECTION_PAYLOADS[0]
    ex = cases.injection(_entry("deployment-bad-image-tag"), n, payload, random.Random(24))
    assert payload in ex.user  # the attack is really in the evidence
    doc = json.loads(ex.assistant)  # the answer is still pure contract JSON
    assert set(doc) == {"verdicts", "summary"}
    blob = ex.assistant.lower()
    for marker in ("ignore all previous", "markdown", "system:"):
        assert marker not in blob
    assert ex.meta["injection_payload"] == payload


def test_injection_payload_lands_on_the_first_object_read():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(3))
    payload = cases.INJECTION_PAYLOADS[0]
    ex = cases.injection(e, n, payload, random.Random(3))
    assert payload in ex.user
    assert payload.lower() not in ex.assistant.lower()
    assert ex.meta["injection_payload"] == payload
    ex_attr = cases.attributed(e, n, random.Random(3))
    assert ex.user.count("== BEGIN read") == ex_attr.user.count("== BEGIN read")


def test_empty_candidates_renders_none_section():
    n = names_mod.draw(random.Random(25))
    ex = cases.empty_candidates(_entry("memory-limit-oomkill"), n)
    assert "== BEGIN candidates ==\n(none)\n== END candidates ==" in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"  # own phrasing
    assert row["confidence"] == "high"  # a direct entry; was a flat "medium"


def test_empty_candidates_has_no_candidates_and_the_fixed_sentence():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(13))
    ex = cases.empty_candidates(e, n)
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)
    assert answer["verdicts"][0]["rationale"].endswith(
        "The candidate list shown did not include this cause.")
    assert ex.user.count("considered") == 0


def test_empty_candidates_answers_at_the_entrys_confidence_and_keeps_the_log_read():
    """An empty candidate list does not make the reads say less. The row
    answers the entry's own cause at the entry's own confidence, like every
    clear undecided row, and a crash-family entry keeps the log read
    kubeagent makes for it."""
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(25))
        ex = cases.empty_candidates(e, n)
        (row,) = json.loads(ex.assistant)["verdicts"]
        assert row["confidence"] == cases._confidence(e), e.key
        assert ex.meta["expected_confidence"] == cases._confidence(e), e.key
        log = cases._log_read(e, n, "clear")
        if log is not None:
            assert f"== {log.label} ==\n{log.content}" in ex.user, e.key


def test_multi_has_one_row_per_workload():
    rng = random.Random(26)
    pairs = [(_entry("memory-limit-oomkill"), names_mod.draw(rng)),
             (_entry("deployment-bad-image-tag"), names_mod.draw(rng)),
             (_entry("probe-failure"), names_mod.draw(rng))]
    ex = cases.multi(pairs, rng)
    doc = json.loads(ex.assistant)
    assert len(doc["verdicts"]) == 3
    assert {r["workload"] for r in doc["verdicts"]} == {
        f"{n.ns}/{n.name}" for _e, n in pairs
    }
    lines = [ln for ln in doc["summary"].split("\n") if ln.strip()]
    assert len(lines) <= c.MAX_SUMMARY_LINES


def test_truncated_menu_overflows_the_render_cap():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(11))
    ex_trunc = cases.truncated(e, n, random.Random(11))
    ex_attr = cases.attributed(e, n, random.Random(11))
    assert ex_attr.user.count("considered") + 9 > c.MAX_CANDIDATES_PER_WORKLOAD
    assert ex_trunc.user.count("considered") == c.MAX_CANDIDATES_PER_WORKLOAD
    assert c.TRUNCATION_MARKER in ex_trunc.user


def test_truncated_expected_cause_matches_attributed_for_the_same_seed():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(11))
    ex_trunc = cases.truncated(e, n, random.Random(11))
    ex_attr = cases.attributed(e, n, random.Random(11))
    assert ex_trunc.meta["expected_cause"] == ex_attr.meta["expected_cause"]


def test_refuted_menu_refutes_every_declared_object():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(5))
    menu = cases._refuted_menu(n, e.objects)
    assert len(menu) == len(e.objects) == 2
    reads = object_reads(menu, ns=n.ns, pod=n.pod)
    assert len(reads) == 2


def test_none_of_these_refuses_an_entry_without_thin_evidence():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(5))
    with pytest.raises(ValueError, match="worker-containerd-stop is not a thin entry"):
        cases.none_of_these_case(e, n, shape="refuted")


def test_own_cause_is_the_ruled_out_shape():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(9))
    ex = cases.own_cause_case(e, n)
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)
    assert answer["verdicts"][0]["confidence"] == cases._confidence(e)
    assert ex.meta["expected_own_keywords"] == list(e.own_cause_keywords)
    assert answer["verdicts"][0]["rationale"].endswith(
        "The candidate list shown did not include this cause.")
    assert ": attributed" not in _cand_section(ex.user)
    assert "fresh read:" not in ex.user
    assert "== describe " not in ex.user


def test_wrong_attribution_names_its_decoy_cause_and_expects_the_own_cause():
    """`decoy_cause` is the row's first decoy, taken from the same
    `decoy_by_workload` list the decoy-rate gate reads, so the two cannot
    name different strings. The length-gap decider is measured over this
    key and has no population without it."""
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(21))
    ex = cases.wrong_attribution(e, n)
    answer = json.loads(ex.assistant)
    key = f"{n.ns}/{n.name}"
    assert ex.meta["decoy_cause"] == ex.meta["decoy_by_workload"][key][0]
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)


def test_positional_probe_takes_rng_and_raises_on_empty_objects():
    e = _entry("worker-containerd-stop")
    stripped = dataclasses.replace(e, objects=())
    n = names_mod.draw(random.Random(9))
    with pytest.raises(ValueError, match="positional_probe needs at least one object"):
        cases.positional_probe(stripped, n, random.Random(3))


def test_misattribution_probe_raises_on_empty_objects_not_losers():
    e = _entry("worker-containerd-stop")
    stripped = dataclasses.replace(e, objects=())
    n = names_mod.draw(random.Random(11))
    with pytest.raises(ValueError, match="misattribution_probe needs at least one object"):
        cases.misattribution_probe(stripped, n)


def test_ruled_out_menu_forces_registry_decoy_below_threshold():
    """A registry decoy that would otherwise be a real confirmed cause (enough pullers,
    a connection literal) is forced below REGISTRY_THRESHOLD, so attribute() rules it out
    and decide() can never pick it."""
    from kubeagent_verdict.dataset import objects as o
    from kubeagent_verdict.dataset import rules

    n = names_mod.draw(random.Random(7))
    registry = o.Object(kind="registry", name="registry.example.com", scan_reason="5",
                        placement="", fresh=o.Fresh(how="read", literal="dial tcp"))
    menu = cases._ruled_out_menu(n, (registry,))
    assert int(menu[0].scan_reason) < rules.REGISTRY_THRESHOLD
    raw = rules.attribute(menu, ns=n.ns, pod=n.pod, issue="ImagePullBackOff")
    assert raw[0].verdict == "ruled_out"
    assert rules.decide(raw).decided is False


def test_contradiction_probe_raises_on_empty_objects_not_losers():
    e = _entry("worker-containerd-stop")
    stripped = dataclasses.replace(e, objects=())
    n = names_mod.draw(random.Random(13))
    with pytest.raises(ValueError, match="contradiction_probe needs at least one object"):
        cases.contradiction_probe(stripped, n)


def test_multi_misattribution_probe_raises_on_empty_objects_not_losers():
    e = _entry("worker-containerd-stop")
    stripped = dataclasses.replace(e, objects=())
    n1 = names_mod.draw(random.Random(31))
    n2 = names_mod.draw(random.Random(32))
    pairs = [(stripped, n1), (e, n2)]
    with pytest.raises(ValueError,
                       match="multi_misattribution_probe needs an object in every entry"):
        cases.multi_misattribution_probe(pairs, random.Random(4))


def test_contradiction_probe_defeats_every_known_shortcut():
    entry = _entry("memory-limit-oomkill")
    n = names_mod.draw(random.Random(46))
    ex = cases.contradiction_probe(entry, n)
    answer = json.loads(ex.assistant)["verdicts"][0]["cause"]
    lines = _cand_lines(ex.user)
    assert lines, "the probe must still render a menu to be misled by"
    causes = [ln.split("considered ", 1)[1].rsplit(": ", 1)[0] for ln in lines]
    # A tag-copier answers whichever line carries `attributed`.
    tagged = [ln for ln in lines if ": attributed" in ln]
    assert tagged
    assert all(not ln.startswith(f"considered {answer}:") for ln in tagged)
    # An entry-lookup model answers the entry's stored winner from the finding
    # block, which this row keeps byte-identical to every other case.
    assert answer != entry.winner_cause.format(**_fmt_kwargs(n))
    # A word counter answers the longest candidate phrase.
    assert answer != max(causes, key=lambda s: len(s.split()))
    # And the answer is not on the menu at all, so it cannot be copied.
    assert answer not in causes


def test_contradiction_probe_reads_contradict_the_winner():
    n = names_mod.draw(random.Random(47))
    entry = _entry("memory-limit-oomkill")
    ex = cases.contradiction_probe(entry, n)
    evidence = ex.user.split("== BEGIN evidence ==")[1]
    assert entry.contradiction.format(**_fmt_kwargs(n)) in evidence
    assert "OOMKilled, exit code 137" not in evidence


def _cand_section(user):
    return user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]


def _cand_lines(user):
    return [ln.strip() for ln in _cand_section(user).splitlines() if "considered " in ln]


def _winner_is_first(user, winner_cause):
    return _cand_lines(user)[0].startswith(f"considered {winner_cause}:")


# The regression test for the defect that compromised the first tuned model:
# _candidates() appended the winner first unconditionally, so in 100% of
# training rows with a winner the answer was candidate #1, and the model
# learned to answer by index. kubeagent's own annotators walk a verdict-blind
# sort.Strings key, so position carries no information in the field either.
def test_candidate_order_is_shuffled_not_winner_first():
    entry = _entry("memory-limit-oomkill")
    winner = "memory limit too low for the workload"
    firsts = [_winner_is_first(cases.attributed(entry, names_mod.draw(random.Random(s)),
                                                random.Random(s)).user, winner)
              for s in range(60)]
    assert any(firsts), "winner never appears first — that is a shortcut too"
    assert not all(firsts), "winner is ALWAYS first: position is a giveaway again"


def test_shuffle_covers_every_case_that_renders_a_menu():
    entry = _entry("memory-limit-oomkill")
    winner = "memory limit too low for the workload"
    for builder in (cases.attributed, cases.truncated):
        firsts = [_winner_is_first(
            builder(entry, names_mod.draw(random.Random(s)), random.Random(s)).user, winner)
            for s in range(60)]
        assert not all(firsts), f"{builder.__name__} still renders the winner first"


def test_injection_prompt_and_answer_agree_on_one_menu():
    # A second _candidates() call would draw a different shuffle, so the
    # rendered prompt and the banked answer could disagree about the menu.
    n = names_mod.draw(random.Random(31))
    ex = cases.injection(_entry("memory-limit-oomkill"), n,
                         cases.INJECTION_PAYLOADS[0], random.Random(31))
    cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
    assert f"considered {cause}:" in _cand_section(ex.user)


def test_positional_probe_puts_the_winner_last_with_an_honest_tag():
    n = names_mod.draw(random.Random(41))
    ex = cases.positional_probe(_entry("memory-limit-oomkill"), n, random.Random(41))
    lines = _cand_lines(ex.user)
    assert len(lines) >= 2
    assert lines[-1].startswith("considered memory limit too low for the workload: attributed")
    assert not lines[0].startswith("considered memory limit too low for the workload:")
    assert json.loads(ex.assistant)["verdicts"][0]["cause"] == \
        "memory limit too low for the workload"


def test_misattribution_probe_menu_never_tags_attributed():
    n = names_mod.draw(random.Random(42))
    e = _entry("memory-limit-oomkill")
    ex = cases.misattribution_probe(e, n)
    section = _cand_section(ex.user)
    assert ": attributed" not in section
    # The evidence is untouched, so the answer is the workload's own cause.
    assert json.loads(ex.assistant)["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)


# The three probes above all leave the finding block untouched — they perturb
# only the candidate menu — and every catalog entry appears in train, so a model
# that ignores the menu entirely and recites a memorised entry-to-winner lookup
# table would still be caught here: contradiction_probe both demotes the
# catalog winner AND contradicts it with a fresh read, so the only correct
# answer is a phrase that appears on no candidate line at all.
def test_contradiction_probe_answers_none_of_these():
    n = names_mod.draw(random.Random(45))
    ex = cases.contradiction_probe(_entry("memory-limit-oomkill"), n)
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == c.NONE_OF_THESE
    assert row["confidence"] == "medium"
    assert ex.meta["case"] == "contradiction_probe"
    assert ex.meta["expected_cause"] == c.NONE_OF_THESE


def _fmt_kwargs(n):
    return {"ns": n.ns, "name": n.name, "pod": n.pod, "container": n.container,
            "init_container": n.init_container, "image": n.image, "node": n.node,
            "pvc": n.pvc, "restarts": n.restarts}


def test_multi_objects_injects_foreign_nodes_ruled_out():
    """Fact 1: each pair's combined objects gain the OTHER pair's declared node
    object(s), placement forced to 'off' (ruled out -- this workload's pod is not
    on that node)."""
    node_entries = [e for e in catalog.trainable() if any(o.kind == "node" for o in e.objects)]
    assert len(node_entries) >= 2, "need at least 2 catalog entries with a node object"
    e1, e2 = node_entries[0], node_entries[1]
    e1_node_count = sum(1 for obj in e1.objects if obj.kind == "node")
    e2_node_count = sum(1 for obj in e2.objects if obj.kind == "node")
    n1 = names_mod.draw(random.Random(1))
    n2 = names_mod.draw(random.Random(2))

    combined = cases._multi_objects([(e1, n1), (e2, n2)], random.Random(11))

    foreign_in_0 = [obj for obj in combined[0] if obj.kind == "node" and obj.placement == "off"]
    foreign_in_1 = [obj for obj in combined[1] if obj.kind == "node" and obj.placement == "off"]
    assert len(foreign_in_0) == e2_node_count
    assert len(foreign_in_1) == e1_node_count
    assert len(combined[0]) == len(e1.objects) + e2_node_count
    assert len(combined[1]) == len(e2.objects) + e1_node_count


def test_multi_derives_job_and_label_from_the_objects():
    """R21: multi's job/decided_* meta is derived by running rules.decide over the
    transformed objects, and the row gains 'workloads', 'label', 'decoy_by_workload'.

    These two node-bearing entries decide on a DIFFERENT object than either
    entry's own hand-written `winner_cause`: multi's foreign-node injection
    (each pair gains the other pair's node, ruled out) still leaves both
    workloads' own combined objects able to decide, and here they decide
    on the other workload's node rather than their own catalog story. That
    makes this pair a real regression check, not just a shape check: the
    gold cause and rationale must follow what `rules.decide` actually
    found, never the catalog's `winner_cause`."""
    node_entries = [e for e in catalog.trainable() if any(o.kind == "node" for o in e.objects)]
    assert len(node_entries) >= 2
    e1, e2 = node_entries[0], node_entries[1]
    n1 = names_mod.draw(random.Random(1))
    n2 = names_mod.draw(random.Random(2))

    ex = cases.multi([(e1, n1), (e2, n2)], random.Random(11))

    key1, key2 = f"{n1.ns}/{n1.name}", f"{n2.ns}/{n2.name}"
    assert set(ex.meta["workloads"]) == {key1, key2}
    for meta in ex.meta["workloads"].values():
        assert set(meta) == {
            "job", "decided", "decided_cause", "decided_outcome",
            "decided_evidence", "expected_cause", "own_cause_keywords"}
        assert meta["job"] in (1, 2)
    assert ex.meta["label"] in ("shared", "separate", "none")
    assert set(ex.meta["decoy_by_workload"]) == {key1, key2}

    wm1, wm2 = ex.meta["workloads"][key1], ex.meta["workloads"][key2]
    assert wm1["decided"] and wm2["decided"], "fixture drifted: both rows must decide here"
    # The bug this pins against: the catalog's own winner_cause is NOT what
    # the rules decided for either workload in this exact draw.
    assert wm1["decided_cause"] != cases._fmt(e1.winner_cause, n1)
    assert wm2["decided_cause"] != cases._fmt(e2.winner_cause, n2)
    assert ex.meta["expected"] == {key1: wm1["decided_cause"], key2: wm2["decided_cause"]}

    answer = json.loads(ex.assistant)
    verdicts = {r["workload"]: r for r in answer["verdicts"]}
    for key, wm in ((key1, wm1), (key2, wm2)):
        assert verdicts[key]["cause"] == wm["decided_cause"]
        assert score.job1(wm, verdicts[key]) == 1.0, key


# `multi` is 12.7% of the curriculum and had ZERO test rows, and cases.multi()
# never swaps a tag — so across all 604 multi training rows the `attributed`
# tag was right 1757 times out of 1757. "Trust the tag" is a perfect strategy
# there, and no single-workload probe can catch a model using it, because the
# multi prompt is a different shape. This probe is the only row that can.
def _two_entries():
    ents = [e for e in catalog.trainable() if e.objects]
    return ents[0], ents[1]


def test_multi_probe_hands_attributed_to_the_decoy_in_every_workload():
    e1, e2 = _two_entries()
    rng = random.Random(7)
    ex = cases.multi_misattribution_probe(
        [(e1, names_mod.draw(random.Random(1))), (e2, names_mod.draw(random.Random(2)))], rng)
    expected = json.loads(ex.assistant)["verdicts"]
    causes = {r["workload"]: r["cause"] for r in expected}
    assert len(causes) == 2, "the two workloads must be distinct"
    # Every `attributed` line in the prompt must point somewhere OTHER than the
    # answer, so a tag-copier scores zero on this row.
    tagged = [ln for ln in ex.user.splitlines() if ": attributed —" in ln]
    assert len(tagged) == 2  # one per workload -- guards the loop below against a vacuous pass
    for line in tagged:
        cause = line.split("considered ", 1)[1].rsplit(": attributed", 1)[0]
        assert cause not in causes.values(), f"tag points at the answer: {cause}"


def test_multi_probe_answers_are_still_the_catalog_own_causes():
    e1, e2 = _two_entries()
    n1 = names_mod.draw(random.Random(1))
    n2 = names_mod.draw(random.Random(2))
    ex = cases.multi_misattribution_probe([(e1, n1), (e2, n2)], random.Random(7))
    causes = {r["cause"] for r in json.loads(ex.assistant)["verdicts"]}
    assert causes == {cases._fmt(e1.own_cause, n1), cases._fmt(e2.own_cause, n2)}


def test_multi_probe_meta_lists_every_decoy():
    e1, e2 = _two_entries()
    ex = cases.multi_misattribution_probe(
        [(e1, names_mod.draw(random.Random(1))), (e2, names_mod.draw(random.Random(2)))],
        random.Random(7))
    assert ex.meta["case"] == "multi_misattribution_probe"
    assert len(ex.meta["decoy_by_workload"]) == 2


def test_prose_decoy_helpers_are_retired():
    """After Task 6, no builder reads e.losers through these three helpers, and no
    builder renders its evidence panel by hand through _reads -- multi() (Step 36)
    was the last caller of both _candidates and _reads."""
    for helper_name in ("_candidates", "_swapped_candidates", "_decoy_cause", "_reads"):
        assert not hasattr(cases, helper_name), (
            f"cases.{helper_name} should be deleted once every builder reads e.objects")


def test_check_prompt_size_refuses_an_oversize_single_workload_prompt(monkeypatch):
    """`render.check_prompt_size` has to run on every prompt a builder
    assembles, not just on the strings its own unit tests hand it directly.
    Lowering the real cap -- rather than fabricating a giant catalog entry --
    is what makes a REAL builder's REAL prompt exceed it: the wiring under
    test is the funnel, not any one entry's byte count. If the funnel is
    unwired this raises nothing and the `with` block fails instead.
    """
    monkeypatch.setattr(render, "MAX_PROMPT_BYTES", 10)
    e = _entry("memory-limit-oomkill")
    n = names_mod.draw(random.Random(11))
    with pytest.raises(ValueError) as excinfo:
        cases.attributed(e, n, random.Random(11))
    assert str(excinfo.value).startswith(f"entry {e.key}: prompt is ")
    assert "over the 10-byte cap" in str(excinfo.value)


def test_check_prompt_size_refuses_an_oversize_multi_workload_prompt(monkeypatch):
    """Same net, the multi-workload key shape: the funnel's key is the row's
    own `group` string -- each paired entry's key plus its namespace/name,
    joined across workloads -- never a placeholder, so the raised error
    names both real entries.
    """
    monkeypatch.setattr(render, "MAX_PROMPT_BYTES", 10)
    e1, e2 = _two_entries()
    n1 = names_mod.draw(random.Random(1))
    n2 = names_mod.draw(random.Random(2))
    with pytest.raises(ValueError) as excinfo:
        cases.multi([(e1, n1), (e2, n2)], random.Random(11))
    msg = str(excinfo.value)
    assert e1.key in msg, msg
    assert e2.key in msg, msg


def _is_build_user_message_call(node: ast.AST) -> bool:
    """True for a call to something named `build_user_message` -- as an
    attribute (`c.build_user_message(...)`, `contract.build_user_message(...)`,
    whatever the import is aliased to) or as a bare name (a call site that did
    `from ... import build_user_message` directly). Matches by name only, not
    by which module the name resolves to.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "build_user_message"
    if isinstance(func, ast.Name):
        return func.id == "build_user_message"
    return False


def _build_user_message_calls_outside_the_funnel() -> list[str]:
    """Every call to `build_user_message` found by parsing every module under
    `src/kubeagent_verdict/dataset/`, except the one call inside
    `cases._user_message` itself -- the funnel. Returns "path:lineno" strings
    for whatever is left; an empty list means every call site in the package
    is routed through the funnel (and so through `render.check_prompt_size`).
    """
    dataset_dir = pathlib.Path(cases.__file__).parent
    funnel_call_ids: set[int] = set()
    findings: list[str] = []
    for path in sorted(dataset_dir.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        if path.name == "cases.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "_user_message":
                    funnel_call_ids = {
                        id(sub) for sub in ast.walk(node) if _is_build_user_message_call(sub)
                    }
        for node in ast.walk(tree):
            if _is_build_user_message_call(node) and id(node) not in funnel_call_ids:
                findings.append(f"{path.name}:{node.lineno}")
    return findings


def test_every_build_user_message_call_goes_through_the_checked_funnel():
    """`check_prompt_size` only ever runs if every `build_user_message(...)`
    call routes through `cases._user_message`, the one funnel that pairs the
    two. This parses every module under `src/kubeagent_verdict/dataset/` with
    `ast` and flags any `build_user_message` call it finds outside that one
    funnel function -- by attribute, under any import alias
    (`c.build_user_message`, `contract.build_user_message`, ...), or by bare
    name (a direct `from ... import build_user_message`). That covers a call
    added under any spelling in any module in the package, not just the
    `c.build_user_message(` substring in cases.py a plain text search would
    have caught. It does not follow a renamed bare import (`import
    build_user_message as x`), and it does not reach outside
    `src/kubeagent_verdict/dataset/` -- `contract.build_messages`'s own call to
    `contract.build_user_message` is a different, unused entry point and is
    intentionally out of scope.
    """
    findings = _build_user_message_calls_outside_the_funnel()
    assert findings == [], (
        f"expected every build_user_message(...) call under "
        f"src/kubeagent_verdict/dataset/ to route through cases._user_message "
        f"(the shared funnel); found call(s) outside it: {findings}"
    )


# kubeagent's previous-log read, pinned to its source at v1.24.0. The label
# is internal/investigate/gather.go:153, `log causes %s/%s container %s`,
# the container not quoted. The content is one arm of `logCauseResult`,
# internal/investigate/reader.go:473-487, where `%q` quotes the container.
# The two cause strings are internal/logscan/logscan.go:32 (entrypoint) and
# :62 (config).
_NO_CLASSIFIABLE = 'the previous log of {ns}/{pod} container "{container}" has no classifiable output'
_NO_PREVIOUS = ('no previous-instance log for {ns}/{pod} container "{container}" '
                "(nothing was refused; the container may not have restarted)")


def test_log_reads_cover_exactly_the_crash_family():
    """kubeagent reads the previous log only for three issues (`crashFamily`,
    internal/investigate/gather.go:195-197). A new trainable entry with one
    of them fails here until it gets a row."""
    crash = {"CrashLoopBackOff", "ContainerStartError", "OOMKilled"}
    assert set(cases.LOG_READS) == {e.key for e in catalog.trainable() if e.issue in crash}


@pytest.mark.parametrize(("key", "evidence", "content"), [
    ("crashloop-pod", "clear", "log cause: bad command or entrypoint"),
    ("crashloop-pod", "thin", _NO_CLASSIFIABLE),
    ("coredns-corefile-broken", "clear", "log cause: configuration parse/validation error"),
    ("coredns-corefile-broken", "thin", _NO_CLASSIFIABLE),
    ("memory-limit-oomkill", "clear", _NO_CLASSIFIABLE),
    ("container-start-error", "clear", _NO_PREVIOUS),
    ("worker-containerd-stop", "clear", _NO_PREVIOUS),
])
def test_log_read_is_the_read_kubeagent_makes(key, evidence, content):
    n = names_mod.draw(random.Random(5))
    # The finding's container: coredns-corefile-broken's finding pins
    # `coredns`; every other entry's is the drawn one.
    container = "coredns" if key == "coredns-corefile-broken" else n.container
    assert cases._log_read(_entry(key), n, evidence) == c.EvidenceRead(
        label=f"log causes {n.ns}/{n.pod} container {container}",
        content=content.format(ns=n.ns, pod=n.pod, container=container))


@pytest.mark.parametrize("key", ["init-crashloop", "restart-loop", "deployment-bad-image-tag"])
@pytest.mark.parametrize("evidence", ["clear", "thin"])
def test_log_read_is_none_outside_the_crash_family(key, evidence):
    """Init:CrashLoopBackOff and RestartLoop are not crash family in
    kubeagent, so neither version of the row carries a log read."""
    n = names_mod.draw(random.Random(5))
    assert cases._log_read(_entry(key), n, evidence) is None


@pytest.mark.parametrize("key", ["memory-limit-oomkill", "container-start-error",
                                 "worker-containerd-stop"])
def test_log_read_has_no_thin_arm_for_a_neutral_clear_read(key):
    n = names_mod.draw(random.Random(5))
    with pytest.raises(ValueError, match="no thin log read"):
        cases._log_read(_entry(key), n, "thin")


def test_log_read_refuses_an_unknown_evidence():
    n = names_mod.draw(random.Random(5))
    with pytest.raises(ValueError, match="evidence"):
        cases._log_read(_entry("crashloop-pod"), n, "vague")


def test_crashloop_pods_clear_log_read_names_its_findings_cause():
    """The finding's `log cause:` line and the clear log read agree."""
    e = _entry("crashloop-pod")
    n = names_mod.draw(random.Random(5))
    assert cases._log_read(e, n, "clear").content == "log cause: " + e.log_cause


# One builder for every undecided job-2 row. kubeagent leaves a workload
# undecided in two shapes. Refuted: one candidate is attributed and a fresh
# read refutes it. Ruled out: every candidate is ruled out. The evidence is
# clear (the prompt names the cause) or thin (it does not). The prompt is a
# function of (entry, names, shape, evidence) and never of the case, so one
# prompt never carries two expected answers.
SHAPES = ("refuted", "ruled_out")
CLEAR_CASES = ("wrong_attribution", "own_cause", "misattribution_probe")


def _evidence_section(user):
    return user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]


def _undecided(key, *, case, shape, evidence, seed=5):
    n = names_mod.draw(random.Random(seed))
    return cases._undecided_example(_entry(key), n, case=case, shape=shape,
                                    evidence=evidence), n


def test_the_refuted_shape_has_a_header_a_fresh_read_and_the_describe_read():
    ex, n = _undecided("memory-limit-oomkill", case="wrong_attribution",
                       shape="refuted", evidence="clear")
    section = _cand_section(ex.user)
    assert "[confidence: high]" in section
    assert ": attributed — " in section
    assert "fresh read: refuted — " in section
    evidence = _evidence_section(ex.user)
    # Object reads first, then the log read: kubeagent's own order.
    assert evidence.index("== describe node /") < evidence.index(
        f"== log causes {n.ns}/{n.pod} container {n.container} ==")


def test_the_ruled_out_shape_has_no_header_no_fresh_read_and_no_object_read():
    ex, n = _undecided("crashloop-pod", case="own_cause", shape="ruled_out",
                       evidence="clear")
    assert "[confidence:" not in ex.user
    assert ": attributed" not in _cand_section(ex.user)
    assert "fresh read:" not in ex.user
    assert _evidence_section(ex.user) == (
        f"== log causes {n.ns}/{n.pod} container {n.container} ==\n"
        "log cause: bad command or entrypoint")


def test_a_ruled_out_row_outside_the_crash_family_has_an_empty_evidence_section():
    """kubeagent would still show the per-workload events read here. Every
    job-2 builder lacks that read; adding it is Spec 3."""
    ex, _ = _undecided("probe-failure", case="own_cause", shape="ruled_out",
                       evidence="clear")
    assert _evidence_section(ex.user) == "(none)"


@pytest.mark.parametrize(("key", "header"), [
    ("deployment-bad-image-tag", "medium"),  # a registry cause; the entry says high
    ("networkpolicy-deny-all", "high"),      # a node cause; the entry says medium
    ("probe-failure", "high"),               # a node cause; the entry says medium
    ("restart-loop", "high"),                # a node cause; the entry says medium
    ("memory-limit-oomkill", "high"),        # the rule and the entry agree
])
def test_the_refuted_header_follows_kubeagents_rule_not_the_entry(key, header):
    ex, _ = _undecided(key, case="wrong_attribution", shape="refuted", evidence="clear")
    assert f"[confidence: {header}]" in _cand_section(ex.user)


@pytest.mark.parametrize("key", cases.THIN_ENTRIES)
@pytest.mark.parametrize("shape", SHAPES)
def test_a_thin_row_names_no_cause_and_answers_none_of_these_at_low(key, shape):
    ex, _ = _undecided(key, case="none_of_these", shape=shape, evidence="thin")
    assert "log cause:" not in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert (row["cause"], row["confidence"]) == (c.NONE_OF_THESE, "low")
    assert row["rationale"] == {
        "refuted": "A fresh read refutes the attributed cause, and no read names another.",
        "ruled_out": "Every candidate was ruled out, and no read names a cause.",
    }[shape]
    assert (ex.meta["expected_cause"], ex.meta["expected_confidence"]) == (
        c.NONE_OF_THESE, "low")


@pytest.mark.parametrize("key", cases.THIN_ENTRIES)
@pytest.mark.parametrize("shape", SHAPES)
def test_a_thin_entrys_clear_row_names_the_cause_its_thin_row_drops(key, shape):
    clear, _ = _undecided(key, case="wrong_attribution" if shape == "refuted" else "own_cause",
                          shape=shape, evidence="clear")
    thin, _ = _undecided(key, case="none_of_these", shape=shape, evidence="thin")
    assert "log cause:" in clear.user
    assert clear.user != thin.user


def test_thin_evidence_raises_for_every_entry_outside_the_thin_set():
    n = names_mod.draw(random.Random(5))
    outside = [e for e in catalog.trainable() if e.key not in cases.THIN_ENTRIES]
    assert len(outside) == 15
    for e in outside:
        for shape in SHAPES:
            with pytest.raises(ValueError, match=f"{e.key} is not a thin entry"):
                cases._undecided_example(e, n, case="none_of_these", shape=shape,
                                         evidence="thin")


@pytest.mark.parametrize(("case", "evidence"), [
    ("none_of_these", "clear"), ("own_cause", "thin"), ("wrong_attribution", "thin"),
    ("misattribution_probe", "thin"), ("own_cause", "vague"),
])
def test_thin_evidence_is_the_none_of_these_case_and_only_it(case, evidence):
    n = names_mod.draw(random.Random(5))
    with pytest.raises(ValueError, match=f"{case} takes .* evidence, not '{evidence}'"):
        cases._undecided_example(_entry("crashloop-pod"), n, case=case, shape="refuted",
                                 evidence=evidence)


def test_undecided_example_refuses_an_unknown_shape_or_case():
    n = names_mod.draw(random.Random(5))
    with pytest.raises(ValueError, match="shape must be 'refuted' or 'ruled_out'"):
        cases._undecided_example(_entry("crashloop-pod"), n, case="own_cause",
                                 shape="decided", evidence="clear")
    with pytest.raises(ValueError, match="not an undecided case: 'attributed'"):
        cases._undecided_example(_entry("crashloop-pod"), n, case="attributed",
                                 shape="refuted", evidence="clear")


@pytest.mark.parametrize("shape", SHAPES)
def test_the_prompt_never_depends_on_the_case(shape):
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        users = {cases._undecided_example(e, n, case=case, shape=shape, evidence="clear").user
                 for case in CLEAR_CASES}
        assert len(users) == 1, e.key


def test_the_public_builders_give_one_prompt_one_answer():
    """Build every undecided row for one entry and one set of names, the
    way generate.py calls them. Until 2026-09-24, none_of_these_case and
    wrong_attribution built the same prompt with different answers for
    every trainable entry. A random draw of names rarely makes two
    dataset rows collide, so this test builds the collision on purpose."""
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        rows = [cases.wrong_attribution(e, n), cases.own_cause_case(e, n),
                cases.misattribution_probe(e, n)]
        if e.key in cases.THIN_ENTRIES:
            rows += [cases.none_of_these_case(e, n, shape=shape) for shape in SHAPES]
        answers: dict[str, set] = {}
        for ex in rows:
            gold = json.loads(ex.assistant)["verdicts"]
            answers.setdefault(ex.user, set()).add(tuple(sorted(
                (v["workload"], v["cause"], v["confidence"]) for v in gold)))
        assert all(len(a) == 1 for a in answers.values()), e.key


@pytest.mark.parametrize("case", CLEAR_CASES)
@pytest.mark.parametrize("shape", SHAPES)
def test_a_clear_row_answers_the_own_cause_at_the_entrys_confidence(case, shape):
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        ex = cases._undecided_example(e, n, case=case, shape=shape, evidence="clear")
        (row,) = json.loads(ex.assistant)["verdicts"]
        assert row["cause"] == cases._fmt(e.own_cause, n) == ex.meta["expected_cause"]
        assert row["confidence"] == ("high" if e.direct else "medium") \
            == ex.meta["expected_confidence"], e.key


@pytest.mark.parametrize(("case", "suffix", "last_line"), [
    ("wrong_attribution",
     " The deterministic pass attributed a different cause, but the evidence supports this one.",
     "The deterministic pass attributed a different cause."),
    ("own_cause", " The candidate list shown did not include this cause.",
     "The deterministic pass did not consider this cause."),
    ("misattribution_probe", "", None),
])
def test_each_clear_case_keeps_its_own_wording(case, suffix, last_line):
    e = _entry("crashloop-pod")
    n = names_mod.draw(random.Random(5))
    ex = cases._undecided_example(e, n, case=case, shape="ruled_out", evidence="clear")
    doc = json.loads(ex.assistant)
    assert doc["verdicts"][0]["rationale"] == cases._fmt(e.rationale, n) + suffix
    want = last_line or cases._fmt(e.recommendation, n).capitalize() + "."
    assert doc["summary"] == f"{n.ns}/{n.name} is failing: {cases._fmt(e.own_cause, n)}.\n{want}"


def test_each_case_keeps_its_own_meta_keys():
    """Only `own_cause` carries `expected_own_keywords`; only
    `wrong_attribution` and `misattribution_probe` carry `decoy_cause`, the
    length-gap decider's population. Kept as they were."""
    n = names_mod.draw(random.Random(5))
    e = _entry("crashloop-pod")
    keys = {case: set(cases._undecided_example(e, n, case=case, shape="refuted",
                                               evidence="clear").meta)
            for case in CLEAR_CASES}
    keys["none_of_these"] = set(cases.none_of_these_case(e, n, shape="refuted").meta)
    assert {case: ("expected_own_keywords" in k, "decoy_cause" in k)
            for case, k in keys.items()} == {
        "wrong_attribution": (False, True), "own_cause": (True, False),
        "misattribution_probe": (False, True), "none_of_these": (False, False)}


def test_the_menu_keeps_trace_order():
    """No shuffle: kubeagent prints candidates in trace order, and the answer
    is on no candidate line, so position gives nothing away. The order is the
    entry's declared order, node then PVC, on every draw."""
    e = _entry("worker-containerd-stop")
    for build in (cases.wrong_attribution, cases.own_cause_case):
        orders = {tuple(ln.split()[1] for ln in _cand_lines(
            build(e, names_mod.draw(random.Random(s))).user)) for s in range(20)}
        assert orders == {("node", "PVC")}, build.__name__


@pytest.mark.parametrize(("key", "content"), [
    ("memory-limit-oomkill", _NO_CLASSIFIABLE),
    ("container-start-error", _NO_PREVIOUS),
    ("worker-containerd-stop", _NO_PREVIOUS),
])
@pytest.mark.parametrize("shape", SHAPES)
def test_a_neutral_log_line_appears_in_clear_rows_too(key, content, shape):
    """So a neutral line is not, by itself, a sign to abstain."""
    ex, n = _undecided(key, case="own_cause", shape=shape, evidence="clear")
    assert content.format(ns=n.ns, pod=n.pod, container=n.container) in \
        _evidence_section(ex.user)


def test_each_wrapper_is_its_shape_and_evidence():
    e = _entry("crashloop-pod")
    n = names_mod.draw(random.Random(5))

    def built(case, shape, evidence):
        return cases._undecided_example(e, n, case=case, shape=shape, evidence=evidence)

    assert cases.wrong_attribution(e, n) == built("wrong_attribution", "refuted", "clear")
    assert cases.own_cause_case(e, n) == built("own_cause", "ruled_out", "clear")
    assert cases.misattribution_probe(e, n) == built("misattribution_probe", "ruled_out", "clear")
    for shape in SHAPES:
        assert cases.none_of_these_case(e, n, shape=shape) == \
            built("none_of_these", shape, "thin")


def test_cap_reads_drops_droppable_reads_from_the_end_and_never_a_kept_one():
    """A multi-workload row can pass 8 reads only with a healthy origin read
    and 4 workloads. The cap cuts droppable object reads from the end and
    keeps the origin read and every log read. A row with more than 8 reads
    it may not drop is a generator bug, so it raises."""
    r = [c.EvidenceRead(label=f"r{i}", content="x") for i in range(10)]
    reads = [(r[0], True)] + [(x, False) for x in r[1:8]] + [(r[8], True), (r[9], False)]
    assert [x.label for x in cases._cap_reads(reads)] == [
        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r8"]
    assert cases._cap_reads([(x, False) for x in r[:3]]) == tuple(r[:3])
    with pytest.raises(ValueError, match="budget"):
        cases._cap_reads([(x, True) for x in r[:9]])
