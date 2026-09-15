import dataclasses
import inspect
import json
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, render
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset.render import object_reads


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


def test_none_of_these_contradicts_and_answers_none():
    n = names_mod.draw(random.Random(21))
    ex = cases.none_of_these_case(_entry("memory-limit-oomkill"), n, random.Random(21))
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == c.NONE_OF_THESE
    assert row["confidence"] == "medium"
    assert "exit code 1" in ex.user  # the contradiction evidence is in the prompt
    assert "OOMKilled, exit code 137" not in ex.user.split("== BEGIN evidence ==")[1]


def test_own_cause_omits_winner_from_candidates():
    n = names_mod.draw(random.Random(22))
    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n, random.Random(22))
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
    assert row["confidence"] == "medium"


def test_empty_candidates_has_no_candidates_and_the_fixed_sentence():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(13))
    ex = cases.empty_candidates(e, n)
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)
    assert answer["verdicts"][0]["rationale"].endswith(
        "The candidate list shown did not include this cause.")
    assert ex.user.count("considered") == 0


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


def test_none_of_these_refutes_every_declared_object():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(5))
    menu = cases._refuted_menu(n, e.objects)
    assert len(menu) == len(e.objects) == 2
    reads = object_reads(menu, ns=n.ns, pod=n.pod)
    assert len(reads) == 2


def test_none_of_these_answer_is_still_none_of_these():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(5))
    ex = cases.none_of_these_case(e, n, random.Random(5))
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == c.NONE_OF_THESE
    assert answer["verdicts"][0]["confidence"] == "medium"


def test_own_cause_menu_is_refuted_not_hand_written():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(9))
    ex = cases.own_cause_case(e, n, random.Random(9))
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.own_cause, n)
    assert ex.meta["expected_own_keywords"] == list(e.own_cause_keywords)
    assert answer["verdicts"][0]["rationale"].endswith(
        "The candidate list shown did not include this cause.")
    menu = cases._refuted_menu(n, e.objects)
    assert len(object_reads(menu, ns=n.ns, pod=n.pod)) == len(e.objects)


def test_wrong_attribution_drops_decoy_cause_meta_and_expects_the_own_cause():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(21))
    ex = cases.wrong_attribution(e, n, random.Random(5))
    answer = json.loads(ex.assistant)
    assert "decoy_cause" not in ex.meta
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
    for builder in (cases.attributed, cases.none_of_these_case, cases.truncated):
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
    transformed objects, and the row gains 'workloads', 'label', 'decoy_by_workload'."""
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
    assert ex.meta["expected"] == {key1: cases._fmt(e1.winner_cause, n1),
                                   key2: cases._fmt(e2.winner_cause, n2)}


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
    """Item 1 of the Task 6 fix round: `render.check_prompt_size` has to run on
    every prompt a builder assembles, not just on the strings its own unit
    tests hand it directly. Lowering the real cap -- rather than fabricating
    a giant catalog entry -- is what makes a REAL builder's REAL prompt
    exceed it: the wiring under test is the funnel, not any one entry's byte
    count. If the funnel is unwired this raises nothing and the `with`
    block fails instead.
    """
    monkeypatch.setattr(render, "MAX_PROMPT_BYTES", 10)
    e = _entry("memory-limit-oomkill")
    n = names_mod.draw(random.Random(11))
    with pytest.raises(ValueError) as excinfo:
        cases.attributed(e, n, random.Random(11))
    assert str(excinfo.value).startswith(f"entry {e.key}: prompt is ")
    assert "over the 10-byte cap" in str(excinfo.value)


def test_check_prompt_size_refuses_an_oversize_multi_workload_prompt(monkeypatch):
    """Same net, the multi-workload key shape: the funnel's key is a join of
    every paired entry's own key, never a placeholder, so the raised error
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


def test_every_build_user_message_call_goes_through_the_checked_funnel():
    """`check_prompt_size` only ever runs if every c.build_user_message(...)
    call routes through the one funnel that pairs the two. This does not
    care what the funnel is named -- it cares that no OTHER line in
    cases.py calls c.build_user_message directly, so a thirteenth call site
    added later (or the funnel removed) fails this test instead of quietly
    reopening the gap Item 1 closed.
    """
    source = inspect.getsource(cases)
    call_lines = [ln for ln in source.splitlines() if "c.build_user_message(" in ln]
    assert len(call_lines) == 1, (
        f"expected exactly one c.build_user_message(...) call site in cases.py "
        f"(the shared funnel); found {len(call_lines)}: {call_lines}"
    )
