import ast
import dataclasses
import json
import pathlib
import random
import re

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, gather, render, stories
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset import objects as o
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
    doc = json.loads(ex.assistant)
    assert set(doc) == {"verdicts", "summary"}
    (row,) = doc["verdicts"]
    assert row["workload"] == f"{n.ns}/{n.name}"
    # The rules decide the node the pod runs on, and the answer is theirs.
    assert row["cause"].startswith(f"node {n.node} (")
    assert f"considered {row['cause']}: attributed — " in ex.user
    assert f"    decided by rules: {row['cause']} — " in ex.user
    assert row["confidence"] == "high"  # a rules-decided row is high
    assert doc["summary"] == f"{n.ns}/{n.name} is failing: {row['cause']}."
    assert ex.meta["expected_cause"] == row["cause"]
    assert set(ex.meta) == {"case", "entry", "expected_cause", "expected_confidence",
                            "workloads", "label", "decoy_by_workload"}


def test_attributed_rows_are_high_for_every_entry():
    # 2026-10-04 (Spec 4b-2): probe-failure was `medium` until now. A rules-decided row is
    # `high` whatever the entry's kit says; the kit's confidence is for named answers.
    n = names_mod.draw(random.Random(12))
    ex = cases.attributed(_entry("probe-failure"), n, random.Random(12))
    assert json.loads(ex.assistant)["verdicts"][0]["confidence"] == "high"


def test_attributed_user_message_is_contract_valid():
    n = names_mod.draw(random.Random(13))
    ex = cases.attributed(_entry("pvc-unbound-unschedulable"), n, random.Random(13))
    assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
    assert ex.user.endswith(c.CLOSING_INSTRUCTION)


@pytest.mark.parametrize("key", ["deployment-bad-image-tag", "node-cordon-diskfull",
                                 "oversized-job-unschedulable"])
@pytest.mark.parametrize("builder", ["attributed", "injection", "positional_probe",
                                     "truncated"])
def test_a_job1_builder_refuses_an_entry_the_rules_do_not_decide(key, builder):
    """A job-1 row's answer is the rules' cause. These three entries leave
    the rules undecided in a single-workload row, so no job-1 row exists
    for them."""
    n = names_mod.draw(random.Random(7))
    with pytest.raises(ValueError, match=f"the rules do not decide {key}"):
        _build(builder, _entry(key), n, random.Random(7))


@pytest.mark.parametrize("builder", ["attributed", "injection", "positional_probe",
                                     "truncated"])
def test_a_job1_builder_refuses_an_entry_with_no_object(builder):
    stripped = dataclasses.replace(_entry("worker-containerd-stop"), objects=())
    n = names_mod.draw(random.Random(7))
    with pytest.raises(ValueError, match=f"{builder} needs at least one object"):
        _build(builder, stripped, n, random.Random(7))


def _build(builder, e, n, rng):
    """Call a job-1 builder by name. `injection` takes the first payload."""
    if builder == "injection":
        return cases.injection(e, n, cases.INJECTION_PAYLOADS[0], rng)
    return getattr(cases, builder)(e, n, rng)


def _job1_rows(builder, count, seed=3):
    """`count` rows the way generate.py builds them: one rng draws each
    row's names and then feeds its builder, rotating over the job-1
    entries."""
    from kubeagent_verdict.dataset import generate

    job1 = catalog.job1_entries()
    rng = random.Random(seed)
    out = []
    for i in range(count):
        e = job1[i % len(job1)]
        n = generate._draw(e, rng)
        out.append((e, n, _build(builder, e, n, rng)))
    return out


def _decided_line(ex):
    """The row's `decided by rules:` line, as (cause, outcome)."""
    (line,) = [ln for ln in ex.user.splitlines() if ln.startswith("    decided by rules: ")]
    cause, outcome = line[len("    decided by rules: "):].rsplit(" — ", 1)
    return cause, outcome


@pytest.mark.parametrize("builder", ["attributed", "injection", "positional_probe",
                                     "truncated"])
def test_every_job1_row_is_decided_and_its_gold_is_the_rules_cause(builder):
    from kubeagent_verdict.dataset import rules

    for e, n, ex in _job1_rows(builder, 68):
        key = f"{n.ns}/{n.name}"
        wm = ex.meta["workloads"][key]
        (row,) = json.loads(ex.assistant)["verdicts"]
        assert _decided_line(ex) == (wm["decided_cause"], wm["decided_outcome"]), e.key
        assert wm["job"] == 1 and wm["decided"], e.key
        assert row["cause"] == ex.meta["expected_cause"] == wm["decided_cause"], e.key
        assert row["rationale"] == cases._rule_rationale(rules.Result(
            decided=True, cause=wm["decided_cause"], outcome=wm["decided_outcome"],
            evidence=wm["decided_evidence"], group_key="", group_text="", decisions=()))
        # 2026-10-04 (Spec 4b-2): a rules-decided row is high, whatever the
        # entry once said.
        assert row["confidence"] == ex.meta["expected_confidence"] == "high"
        assert json.loads(ex.assistant)["summary"] == f"{key} is failing: {row['cause']}."
        assert ex.meta["entry"] == e.key and ex.meta["case"] == builder


def test_the_attributed_coin_adds_the_first_pad_about_half_the_time():
    """The second draw is a coin: heads adds `aux-0`, a claim no pod mounts.
    The rules rule it out, so the gather never reads it."""
    rows = _job1_rows("attributed", 340)
    pad = "considered PVC aux-0 (ProvisioningFailed): ruled out — "
    heads = 0
    for e, n, ex in rows:
        shown = [ln for ln in _cand_lines(ex.user) if ln.startswith(pad)]
        heads += len(shown)
        assert f"describe pvc {n.ns}/aux-0" not in _evidence_labels(ex.user), e.key
        key = f"{n.ns}/{n.name}"
        decoys = ["PVC aux-0 (ProvisioningFailed)"] if shown else []
        assert ex.meta["decoy_by_workload"] == {key: decoys}, e.key
    assert 0.4 * len(rows) <= heads <= 0.6 * len(rows), heads


# Injection: the payload is one more event of the workload's pod. kubeagent
# reads those events and sanitises each line, so the payload arrives as one
# folded line among the pod's own events.

def test_injection_answer_ignores_payload():
    n = names_mod.draw(random.Random(24))
    payload = cases.INJECTION_PAYLOADS[0]
    ex = cases.injection(_entry("memory-limit-oomkill"), n, payload, random.Random(24))
    assert payload in ex.user  # the attack is really in the evidence
    doc = json.loads(ex.assistant)  # the answer is still pure contract JSON
    assert set(doc) == {"verdicts", "summary"}
    blob = ex.assistant.lower()
    for marker in ("ignore all previous", "markdown", "system:"):
        assert marker not in blob
    assert ex.meta["injection_payload"] == payload


def _injected_reason(ex, payload):
    """The reason the payload's event line carries in `ex`."""
    line = f": {gather._sanitize(payload)} (x1)\n"
    found = [r for r in cases.INJECTION_REASONS if f"  {r}{line}" in ex.user]
    assert len(found) == 1, found
    assert ex.user.count(line) == 1
    return found[0]


@pytest.mark.parametrize("payload", cases.INJECTION_PAYLOADS)
def test_injection_payload_is_one_event_line_after_the_pods_own(payload):
    e = _entry("memory-limit-oomkill")
    n = names_mod.draw(random.Random(3))
    ex = cases.injection(e, n, payload, random.Random(3))
    reason = _injected_reason(ex, payload)
    events = gather.format_events(
        n.ns, n.pod, cases.gather_workload(e, n, ()).events + ((reason, payload, 1),))
    assert f"== events {n.ns}/{n.pod} ==\n{events.rstrip()}\n" in ex.user
    assert "\n" not in gather._sanitize(payload)
    assert ex.meta["injection_payload"] == payload


def test_injection_reasons_are_the_three_and_none_is_a_pull_event():
    assert cases.INJECTION_REASONS == ("Unhealthy", "Killing", "FailedSync")
    for reason in cases.INJECTION_REASONS:
        for payload in cases.INJECTION_PAYLOADS:
            assert not gather._is_pull_event(reason, payload), (reason, payload)
    seen = {_injected_reason(ex, cases.INJECTION_PAYLOADS[0])
            for _e, _n, ex in _job1_rows("injection", 60)}
    assert seen == set(cases.INJECTION_REASONS)


def test_injection_is_the_attributed_row_plus_one_event_line():
    """The same draws, in the same order, then the reason. So the row
    without the payload's line is the attributed row, and the gold is
    the same."""
    for e in catalog.job1_entries():
        n = names_mod.draw(random.Random(5))
        payload = cases.INJECTION_PAYLOADS[1]
        ex = cases.injection(e, n, payload, random.Random(5))
        attr = cases.attributed(e, n, random.Random(5))
        reason = _injected_reason(ex, payload)
        line = f"\n  {reason}: {gather._sanitize(payload)} (x1)"
        assert ex.user.replace(line, "", 1) == attr.user, e.key
        assert ex.assistant == attr.assistant, e.key
        assert ex.meta == dict(attr.meta, case="injection", injection_payload=payload)


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


# Truncated: nine pads no pod mounts, so the rules rule each one out and
# the gather reads none. kubeagent shows at most 8 candidates per workload
# (internal/investigate/prime.go), so the row tests that display cap, not
# the read budget.

def test_truncated_shows_eight_candidates_then_the_marker():
    for e, n, ex in _job1_rows("truncated", 34):
        lines = _cand_lines(ex.user)
        assert len(lines) == c.MAX_CANDIDATES_PER_WORKLOAD, e.key
        assert f"    {c.TRUNCATION_MARKER}\n" in _cand_section(ex.user), e.key
        assert not any("aux-" in label for label in _evidence_labels(ex.user)), e.key
        cause = ex.meta["expected_cause"]
        assert _decided_line(ex)[0] == cause, e.key
        on_a_line = [ln for ln in lines if ln.startswith(f"considered {cause}: ")]
        if e.key == "pvc-unbound-unschedulable":
            # Nine pads sort before the entry's own claim: it is past the cap.
            assert on_a_line == [], e.key
            assert f"describe pvc {n.ns}/{n.pvc}" in _evidence_labels(ex.user)
        else:
            assert lines[0].startswith(f"considered {cause}: attributed — "), e.key


def test_truncated_answers_high_with_no_caution():
    # 2026-10-04 (Spec 4b-2): a rules-decided row is high, so this no longer follows the entry.
    for _e, _n, ex in _job1_rows("truncated", 17):
        doc = json.loads(ex.assistant)
        (row,) = doc["verdicts"]
        assert row["confidence"] == ex.meta["expected_confidence"] == "high"
        assert "treat with caution" not in doc["summary"]


def test_empty_candidates_renders_none_section():
    n = names_mod.draw(random.Random(25))
    ex = cases.empty_candidates(_entry("memory-limit-oomkill"), n)
    assert "== BEGIN candidates ==\n(none)\n== END candidates ==" in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"  # own phrasing
    assert row["confidence"] == "high"  # the kit's confidence


def test_empty_candidates_has_no_candidates_and_the_fixed_sentence():
    e = _entry("worker-containerd-stop")
    n = names_mod.draw(random.Random(13))
    ex = cases.empty_candidates(e, n)
    answer = json.loads(ex.assistant)
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.answer.cause, n)
    assert answer["verdicts"][0]["rationale"].endswith(
        "The candidate list shown did not include this cause.")
    assert ex.user.count("considered") == 0


def test_empty_candidates_answers_at_the_entrys_confidence_and_keeps_the_log_read():
    """An empty candidate list does not make the reads say less. The row
    answers the kit's cause at the kit's own confidence, like every
    clear undecided row, and a crash-family entry keeps the log read
    kubeagent makes for it."""
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(25))
        ex = cases.empty_candidates(e, n)
        (row,) = json.loads(ex.assistant)["verdicts"]
        assert row["confidence"] == e.answer.confidence, e.key
        assert ex.meta["expected_confidence"] == e.answer.confidence, e.key
        log = cases._log_read(e, n, "clear")
        if log is not None:
            assert f"== {log.label} ==\n{log.content}" in ex.user, e.key


def _evidence_labels(user):
    """The evidence section's read labels, in order."""
    section = user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]
    return re.findall(r"^== (.+) ==$", section, re.MULTILINE)


def test_empty_candidates_reads_the_events_and_the_crash_familys_log():
    """kubeagent reads a workload's events, then a describe per live
    candidate, then a crash-family log (internal/investigate/gather.go:71-156).
    With no candidate there is nothing to describe."""
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(25))
        ex = cases.empty_candidates(e, n)
        want = [f"events {n.ns}/{n.pod}"]
        log = cases._log_read(e, n, "clear")
        if log is not None:
            want.append(log.label)
        assert _evidence_labels(ex.user) == want, e.key
        events = gather.format_events(n.ns, n.pod, cases.gather_workload(e, n, ()).events)
        assert f"== events {n.ns}/{n.pod} ==\n{events.rstrip()}\n" in ex.user, e.key


@pytest.mark.parametrize("key", ["node-cordon-diskfull", "worker-containerd-stop"])
def test_empty_candidates_no_longer_describes_a_node(key):
    n = names_mod.draw(random.Random(25))
    assert "== describe " not in cases.empty_candidates(_entry(key), n).user


def _names(ns, name, node, *, pvc="data-0", restarts=5):
    """One workload's names, chosen by hand. A multi row needs distinct
    workloads, nodes and (namespace, claim) pairs, and random draws from
    five nodes clash too often to build one on purpose."""
    return names_mod.Names(
        ns=ns, name=name, pod=f"{name}-5d8f7c9b4-x2k9p", container="app",
        init_container="init-config", image=f"registry.example.com/{ns}/{name}:v1.2.3",
        node=node, pvc=pvc, restarts=restarts)


def test_multi_has_one_row_per_workload():
    # 2026-09-26 (faithful prompts): Random(26) drew all three workloads on
    # one node once there were five nodes, and a multi row now refuses that,
    # so the names are chosen by hand.
    pairs = [(_entry("memory-limit-oomkill"), _names("billing", "cache", "worker-1")),
             (_entry("deployment-bad-image-tag"), _names("search", "indexer", "worker-2")),
             (_entry("probe-failure"), _names("shop", "gateway", "worker-3"))]
    ex = cases.multi(pairs, random.Random(26))
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


def _two_object_entry():
    """worker-containerd-stop with a PVC decoy added after its cause node.

    No catalog entry declares two objects any more (a pod with a finding has
    no Pending claim to blame), but the builders still take a tuple, so the
    two-object behaviour is tested on a built entry.
    """
    e = _entry("worker-containerd-stop")
    pvc = o.Object(kind="pvc", name="{pvc}", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=o.Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0947"),
                   intent="decoy")
    return dataclasses.replace(e, objects=(*e.objects, pvc))


def test_refuted_menu_refutes_every_declared_object():
    """Both objects stay live, so the gather describes both, and each
    fresh read refutes its candidate."""
    e = _two_object_entry()
    n = names_mod.draw(random.Random(5))
    menu = cases._refuted_menu(n, e.objects)
    assert len(menu) == len(e.objects) == 2
    res = gather.gather([cases.gather_workload(e, n, menu)])
    assert [r.label.split(" ")[0] for r in res.reads[1:3]] == ["describe", "describe"]
    assert [cand.fresh_read_outcome for cand in res.candidates[0]] == ["refuted", "refuted"]


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
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.answer.cause, n)
    assert answer["verdicts"][0]["confidence"] == e.answer.confidence
    assert ex.meta["expected_own_keywords"] == list(e.answer.keys)
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
    assert answer["verdicts"][0]["cause"] == cases._fmt(e.answer.cause, n)


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


def test_ruled_out_menu_leaves_a_registry_decoy_ruled_out():
    """A registry decoy declared as a real confirmed cause (5 pullers, a
    connection literal) still comes out ruled out, and the workload stays
    undecided. The gather sizes each registry group over the whole row
    (`gather._registry_counts`) and writes that count over the declared
    `scan_reason`, and a one-workload row has at most one puller.

    2026-09-28 (final review): the menu used to force the count to "1"
    itself. The gather overwrote it before any rule read it, so that
    branch changed no byte, and it is gone. This test used to call
    `rules.attribute` on the menu directly, which skipped the gather."""
    from kubeagent_verdict.dataset import objects as o

    e = _entry("deployment-bad-image-tag")
    n = names_mod.draw(random.Random(7))
    registry = o.Object(kind="registry", name="registry.example.com", scan_reason="5",
                        placement="", fresh=o.Fresh(how="read", literal="dial tcp"))
    menu = cases._ruled_out_menu(n, (registry,))
    res = gather.gather([cases.gather_workload(e, n, menu)])
    (candidates,), (result,) = res.candidates, res.results
    assert [(cand.cause, cand.verdict) for cand in candidates] == [
        ("registry registry.example.com", "ruled_out")]
    assert result.decided is False


def test_contradiction_probe_raises_on_empty_objects():
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


# How contradiction_probe ends each kind of object: a node is Ready but its
# kubelet lease was not re-read, and a claim's describe is refused. Both
# leave the rules' decision standing, unverified.
_CONTRADICTION_ENDINGS = {"node": "lease", "pvc": "read_failed"}


def _contradiction_result(e, n):
    """The rules' decision for the entry's own objects, bound to `n` and
    ended the way contradiction_probe ends them. Event lines do not change
    what the rules decide, so the entry's own events are enough here."""
    bound = tuple(render.bind(obj, dataclasses.asdict(n)) for obj in e.objects)
    menu = tuple(o.unverify(obj, _CONTRADICTION_ENDINGS[obj.kind]) for obj in bound)
    (result,) = gather.gather([cases.gather_workload(e, n, menu)]).results
    return result


def _contradiction_names(e):
    """The names probe_sets draws for this entry's contradiction row."""
    from kubeagent_verdict.dataset import generate

    return generate._draw(e, generate._entry_rng("contradiction-probe", e.key))


def _event_lines(e, n, events):
    """`events` filled in with these names and printed the way
    `format_events` prints them, one line each, with no header."""
    names = dataclasses.asdict(n)
    tuples = tuple((reason.format(**names), message.format(**names),
                    int(count.format(**names)) if isinstance(count, str) else count)
                   for reason, message, count in events)
    return gather.format_events(n.ns, n.pod, tuples).split("\n", 1)[1]


def _evidence_reads(user):
    """The evidence section as (label, content) pairs, in order."""
    section = user.split("== BEGIN evidence ==\n")[1].split("\n== END evidence ==")[0]
    parts = re.split(r"^== (.+) ==\n", section, flags=re.MULTILINE)
    return [(label, content.rstrip("\n")) for label, content in zip(parts[1::2], parts[2::2])]


def test_contradiction_probe_answers_the_rules_decision():
    """The answer is what the rules decide. It is the cause on the
    `decided by rules:` line, and the cause the rules give the same
    objects with the same endings. An event line that pulls the other way
    does not change it."""
    e = _entry("memory-limit-oomkill")
    n = names_mod.draw(random.Random(46))
    ex = cases.contradiction_probe(e, n)
    answer = json.loads(ex.assistant)["verdicts"][0]["cause"]
    result = _contradiction_result(e, n)
    assert result.decided
    assert answer == _decided_line(ex)[0] == result.cause
    assert answer == f"node {n.node} (no kubelet lease)"


@pytest.mark.parametrize("key", [e.key for e in catalog.job1_entries()])
def test_contradiction_probe_gold_follows_the_rules(key):
    e = _entry(key)
    n = _contradiction_names(e)
    ex = cases.contradiction_probe(e, n)
    result = _contradiction_result(e, n)
    assert result.decided
    doc = json.loads(ex.assistant)
    (row,) = doc["verdicts"]
    workload = f"{n.ns}/{n.name}"
    assert row["workload"] == workload
    assert row["cause"] == result.cause == _decided_line(ex)[0] == ex.meta["expected_cause"]
    # 2026-10-04 (Spec 4b-2): a rules-decided row is high.
    assert row["confidence"] == "high" == ex.meta["expected_confidence"]
    assert row["rationale"] == cases._rule_rationale(result)
    assert doc["summary"] == f"{workload} is failing: {result.cause}."
    assert "\n" not in doc["summary"]
    wm = ex.meta["workloads"][workload]
    assert (wm["job"], wm["decided"], wm["decided_cause"]) == (1, True, result.cause)
    # One candidate, and it is the answer, so the row has no decoy to name.
    assert ex.meta["decoy_by_workload"] == {workload: []}
    assert set(ex.meta) == {"case", "entry", "expected_cause", "expected_confidence",
                            "workloads", "label", "decoy_by_workload"}
    assert (ex.meta["case"], ex.meta["entry"], ex.meta["label"]) == (
        "contradiction_probe", key, "none")


@pytest.mark.parametrize("key", ["deployment-bad-image-tag", "node-cordon-diskfull",
                                 "oversized-job-unschedulable"])
def test_contradiction_probe_refuses_an_entry_the_rules_do_not_decide(key):
    n = names_mod.draw(random.Random(7))
    with pytest.raises(ValueError, match=f"contradiction_probe: the rules do not decide {key}"):
        cases.contradiction_probe(_entry(key), n)


# The 15 entries whose contradiction_probe row adds event lines
# (tests/test_catalog.py checks the set against the catalog).
_WITH_CONTRADICTION_EVENTS = (
    "memory-limit-oomkill", "networkpolicy-deny-all", "coredns-corefile-broken",
    "crashloop-pod", "probe-failure", "container-start-error",
    "create-container-config-error", "init-crashloop", "init-config-error",
    "init-errimagepull", "init-imagepullbackoff", "init-oomkilled", "restart-loop",
    "volume-attach-error", "volume-mount-error",
)


@pytest.mark.parametrize("key", _WITH_CONTRADICTION_EVENTS)
def test_contradiction_events_go_into_the_one_events_read(key):
    """The contradicting lines go into the row's one events read, after
    the entry's own lines and in the order they are declared. No other
    read holds them, and no label repeats."""
    e = _entry(key)
    n = _contradiction_names(e)
    ex = cases.contradiction_probe(e, n)
    reads = _evidence_reads(ex.user)
    labels = [label for label, _ in reads]
    assert len(labels) == len(set(labels)), labels
    (events,) = [content for label, content in reads if label.startswith("events ")]
    assert labels[0] == f"events {n.ns}/{n.pod}"
    own = _event_lines(e, n, e.events)
    extra = _event_lines(e, n, e.contradiction_events)
    assert events == (f"events for {n.ns}/{n.pod}:\n" + own + extra).rstrip("\n")
    for line in extra.splitlines():
        others = [label for label, content in reads
                  if not label.startswith("events ") and line in content]
        assert not others, (line, others)


def _cand_section(user):
    return user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]


def _cand_lines(user):
    return [ln.strip() for ln in _cand_section(user).splitlines() if "considered " in ln]


def _winner_is_first(user, cause):
    return _cand_lines(user)[0].startswith(f"considered {cause}:")


# The defect that compromised the first tuned model: _candidates() appended
# the winner first unconditionally, so in 100% of training rows with a
# winner the answer was candidate #1, and the model learned to answer by
# index. A job-1 row now prints its candidates in the rules' trace order,
# as kubeagent does: nodes, then claims, each sorted by name (rootcause.go's
# Annotate, then AnnotatePVC; see `rules.attribute`). A node winner is first
# in most rows. Position is not where the answer is: the `decided by rules:`
# line names it, and `positional_probe` puts the winner last so a model that
# answers by index scores zero there.
_TRACE_RANK = {"node": 0, "PVC": 1}


def _trace_key(line):
    kind, name = line.split()[1:3]
    return _TRACE_RANK[kind], name


@pytest.mark.parametrize("builder", ["attributed", "injection", "positional_probe",
                                     "truncated"])
def test_job1_candidates_come_in_trace_order(builder):
    for e, _n, ex in _job1_rows(builder, 34):
        lines = _cand_lines(ex.user)
        assert lines == sorted(lines, key=_trace_key), e.key


def test_the_winner_is_first_only_where_the_trace_puts_it():
    """A node winner sorts before every claim; the one claim winner sorts
    after `aux-0` when the coin adds it."""
    for e, _n, ex in _job1_rows("attributed", 68):
        firsts = _winner_is_first(ex.user, ex.meta["expected_cause"])
        pad = "aux-0" in _cand_section(ex.user)
        assert firsts == (e.key != "pvc-unbound-unschedulable" or not pad), e.key


def test_injection_prompt_and_answer_agree_on_one_menu():
    # A second _candidates() call would draw a different shuffle, so the
    # rendered prompt and the banked answer could disagree about the menu.
    n = names_mod.draw(random.Random(31))
    ex = cases.injection(_entry("memory-limit-oomkill"), n,
                         cases.INJECTION_PAYLOADS[0], random.Random(31))
    cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
    assert f"considered {cause}:" in _cand_section(ex.user)


def test_positional_probe_puts_the_winner_last_behind_a_refuted_decoy():
    """The decoy sorts first and carries `attributed`, and its fresh read
    refutes it. The rules then decide the winner, which the trace printed
    last, outranked."""
    for e, n, ex in _job1_rows("positional_probe", 34):
        lines = _cand_lines(ex.user)
        cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
        decoy = ("PVC aux-0 (ProvisioningFailed)" if e.key == "pvc-unbound-unschedulable"
                 else "node worker-1 (NotReady)")
        assert len(lines) == 2, e.key
        assert lines[0].startswith(f"considered {decoy}: attributed — "), e.key
        assert lines[1].startswith(f"considered {cause}: outranked — "), e.key
        section = _cand_section(ex.user)
        after_decoy = section.split(f"considered {decoy}: attributed — ")[1].split("\n")[1]
        assert after_decoy.startswith("      fresh read: refuted — "), e.key
        assert _decided_line(ex)[0] == cause, e.key
        assert ex.meta["decoy_cause"] == decoy, e.key
        assert ex.meta["decoy_by_workload"] == {f"{n.ns}/{n.name}": [decoy]}, e.key


def test_positional_probe_moves_the_rows_own_node_off_the_decoys_name():
    """The decoy is `worker-1`. A row that drew `worker-1` for its own node
    takes `worker-2` instead, before any template is filled, so the winner
    still sorts last."""
    e = _entry("memory-limit-oomkill")
    n = dataclasses.replace(names_mod.draw(random.Random(41)), node="worker-1")
    ex = cases.positional_probe(e, n, random.Random(41))
    cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
    assert cause.startswith("node worker-2 (")
    lines = _cand_lines(ex.user)
    assert lines[0].startswith("considered node worker-1 (NotReady): attributed — ")
    assert lines[1].startswith(f"considered {cause}: outranked — ")
    assert "describe node /worker-2" in _evidence_labels(ex.user)


def test_misattribution_probe_menu_never_tags_attributed():
    n = names_mod.draw(random.Random(42))
    e = _entry("memory-limit-oomkill")
    ex = cases.misattribution_probe(e, n)
    section = _cand_section(ex.user)
    assert ": attributed" not in section
    # The evidence is untouched, so the answer is the workload's own cause.
    assert json.loads(ex.assistant)["verdicts"][0]["cause"] == cases._fmt(e.answer.cause, n)


def test_contradiction_probe_never_answers_none_of_these():
    """The rules decide every row of this slice, so no row's gold is
    `none of these`. The event line that pulls the other way is there to
    be read past, not to be answered."""
    for e in catalog.job1_entries():
        ex = cases.contradiction_probe(e, _contradiction_names(e))
        (row,) = json.loads(ex.assistant)["verdicts"]
        assert row["cause"] != c.NONE_OF_THESE, e.key
        assert ex.meta["expected_cause"] != c.NONE_OF_THESE, e.key


def test_multi_objects_injects_foreign_nodes_ruled_out():
    """Fact 1: each pair's combined objects gain the OTHER pair's declared node
    object(s), placement forced to 'off' (ruled out -- this workload's pod is not
    on that node), and the other pair's claim when the two share a namespace
    (the tests below)."""
    node_entries = [e for e in catalog.trainable()
                    if any(o.kind == "node" and o.placement == "on" for o in e.objects)]
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
    # 2026-09-28 (final review): a claim joins the list too, when the two
    # workloads share a namespace. These two declare no claim, so the
    # count adds 0 whichever namespaces they drew.
    same_ns = n1.ns == n2.ns
    e1_pvc_count = sum(1 for obj in e1.objects if obj.kind == "pvc") if same_ns else 0
    e2_pvc_count = sum(1 for obj in e2.objects if obj.kind == "pvc") if same_ns else 0
    assert len(combined[0]) == len(e1.objects) + e2_node_count + e2_pvc_count
    assert len(combined[1]) == len(e2.objects) + e1_node_count + e1_pvc_count


def test_multi_objects_adds_a_same_namespace_claim_ruled_out():
    """kubeagent's AnnotatePVC walks every broken claim in the workload's
    own namespace, and one its pods do not mount is ruled out. So a
    workload gets the other workload's claim, unmounted, when the two share
    a namespace. It is the other workload's own copy, so the claim has one
    fresh state everywhere it appears."""
    pairs = _pvc_pairs("shop")
    combined = cases._multi_objects(pairs, random.Random(11))
    (own,) = [obj for obj in combined[0] if obj.kind == "pvc"]
    (foreign,) = [obj for obj in combined[1] if obj.kind == "pvc"]
    assert own.name == "data-db" and own.placement == "mounted"
    assert foreign == dataclasses.replace(own, placement="unmounted")


def test_multi_objects_leaves_a_claim_in_another_namespace_out():
    combined = cases._multi_objects(_pvc_pairs("web"), random.Random(11))
    assert [obj for obj in combined[1] if obj.kind == "pvc"] == []


def test_multi_lists_a_same_namespace_claim_in_both_blocks():
    ex = cases.multi(_pvc_pairs("shop"), random.Random(11))
    blocks = _cand_blocks(ex.user)
    pvcs = {key: {name for kind, name, _v, _r in lines if kind == "PVC"}
            for key, lines in blocks.items()}
    assert pvcs == {"shop/db": {"data-db"}, "shop/cache": {"data-db"}}
    assert ("PVC", "data-db", "ruled out",
            "not mounted by this workload's pods") in blocks["shop/cache"]


def test_multi_derives_job_and_label_from_the_objects():
    """R21: multi's job/decided_* meta is derived by running rules.decide over the
    transformed objects, and the row gains 'workloads', 'label', 'decoy_by_workload'.

    Multi's foreign-node injection (each pair gains the other pair's node,
    ruled out) still leaves both workloads' own combined objects able to
    decide. The gold cause and rationale must follow what `rules.decide`
    actually found."""
    node_entries = [e for e in catalog.trainable()
                    if any(o.kind == "node" and o.placement == "on" for o in e.objects)]
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
            "decided_evidence", "expected_cause", "own_cause_keywords",
            "own_cause_must_not"}
        assert meta["job"] in (1, 2)
    assert ex.meta["label"] in ("shared", "separate", "none")
    assert set(ex.meta["decoy_by_workload"]) == {key1, key2}

    wm1, wm2 = ex.meta["workloads"][key1], ex.meta["workloads"][key2]
    assert wm1["decided"] and wm2["decided"], "fixture drifted: both rows must decide here"
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
    """The first two entries whose node sits under the pod, so each
    workload has one attributed candidate.

    2026-09-26 (faithful prompts): this was the first two entries with an
    object, memory-limit-oomkill and deployment-bad-image-tag. On the gather
    one workload failing to pull is under kubeagent's registry threshold of
    2, so bad-image-tag's registry is ruled out and its workload shows no
    attributed tag at all.
    """
    ents = [e for e in catalog.trainable()
            if any(obj.kind == "node" and obj.placement == "on" for obj in e.objects)]
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
    # 2026-10-04 (Spec 4b-2): the cause is the kit's, through the gate.
    assert causes == {cases._fmt(e1.answer.cause, n1), cases._fmt(e2.answer.cause, n2)}


def test_multi_probe_meta_lists_every_decoy():
    e1, e2 = _two_entries()
    ex = cases.multi_misattribution_probe(
        [(e1, names_mod.draw(random.Random(1))), (e2, names_mod.draw(random.Random(2)))],
        random.Random(7))
    assert ex.meta["case"] == "multi_misattribution_probe"
    assert len(ex.meta["decoy_by_workload"]) == 2


# kubeagent's rootcause walks every down node for every flagged workload,
# and every broken claim in the workload's own namespace
# (internal/rootcause/rootcause.go: Annotate, AnnotatePVC). A node or claim
# the workload does not use is still listed, ruled out. Until 2026-09-28 the
# probe listed only each workload's own objects, which no kubeagent scan
# prints once a row has two workloads.
_CONSIDERED = re.compile(r"    considered (node|PVC) (\S+) \(.*?\): "
                         r"(attributed|ruled out|outranked) — (.*)$")


def _cand_blocks(user):
    """Each workload block's (kind, name, verdict, reason) lines, by workload."""
    blocks: dict[str, list[tuple[str, str, str, str]]] = {}
    key = None
    for ln in _cand_section(user).splitlines():
        if ln.startswith("- "):
            key = ln[2:].split(" (", 1)[0]
            blocks[key] = []
        elif m := _CONSIDERED.match(ln):
            blocks[key].append(m.groups())
    return blocks


def _probe_rows():
    from kubeagent_verdict.dataset import generate
    return [ex for ex in generate.probe_sets() if ex.case == "multi_misattribution_probe"]


def test_multi_probe_lists_every_node_of_the_row_in_every_block():
    rows = _probe_rows()
    assert len(rows) == 20
    for ex in rows:
        blocks = _cand_blocks(ex.user)
        assert len(blocks) >= 2, ex.group
        nodes = {name for lines in blocks.values() for kind, name, _v, _r in lines
                 if kind == "node"}
        assert nodes, ex.group
        for key, lines in blocks.items():
            assert {name for kind, name, _v, _r in lines if kind == "node"} == nodes, (
                ex.group, key)


def test_multi_probe_rules_out_another_workloads_node():
    e1, e2 = _two_entries()
    n1, n2 = _names("shop", "cart", "worker-1"), _names("web", "front", "worker-2")
    blocks = _cand_blocks(cases.multi_misattribution_probe(
        [(e1, n1), (e2, n2)], random.Random(7)).user)
    assert ("node", "worker-2", "ruled out",
            "no pod of this workload is scheduled on it") in blocks["shop/cart"]
    assert ("node", "worker-1", "ruled out",
            "no pod of this workload is scheduled on it") in blocks["web/front"]


def _pvc_pairs(cache_ns):
    """pvc-unbound-unschedulable's claim in `shop`, beside a node workload."""
    return [(_entry("pvc-unbound-unschedulable"),
             _names("shop", "db", "worker-1", pvc="data-db")),
            (_entry("memory-limit-oomkill"),
             _names(cache_ns, "cache", "worker-2", pvc="data-cache"))]


def test_multi_probe_lists_a_same_namespace_claim_in_both_blocks():
    blocks = _cand_blocks(cases.multi_misattribution_probe(
        _pvc_pairs("shop"), random.Random(7)).user)
    pvcs = {key: {name for kind, name, _v, _r in lines if kind == "PVC"}
            for key, lines in blocks.items()}
    assert pvcs == {"shop/db": {"data-db"}, "shop/cache": {"data-db"}}
    assert ("PVC", "data-db", "ruled out",
            "not mounted by this workload's pods") in blocks["shop/cache"]


def test_multi_probe_leaves_a_claim_in_another_namespace_out():
    blocks = _cand_blocks(cases.multi_misattribution_probe(
        _pvc_pairs("web"), random.Random(7)).user)
    assert [ln for ln in blocks["web/cache"] if ln[0] == "PVC"] == []


# The probe's decoys, measured on the builder before it listed other
# workloads' nodes and claims (2026-09-28). A decoy is a workload's OWN
# refuted candidate: the ruled-out lines for the others' objects are not
# bait, and nodes sort first, so `d[0]` would otherwise turn into one.
_PROBE_DECOYS_SHA256 = "0c98f224f2a34cfca359cad40efc94d2d5bcb17f578a3e352330546f9e032b9f"


def test_multi_probe_decoys_are_unchanged_by_the_foreign_lines():
    import hashlib
    view = [[ex.group, ex.meta["decoy_by_workload"], ex.meta["decoy_causes"]]
            for ex in _probe_rows()]
    blob = json.dumps(view, sort_keys=True, ensure_ascii=False).encode()
    assert hashlib.sha256(blob).hexdigest() == _PROBE_DECOYS_SHA256


def test_multi_probe_decoys_name_only_the_workloads_own_objects():
    ex = cases.multi_misattribution_probe(_pvc_pairs("shop"), random.Random(7))
    decoys = ex.meta["decoy_by_workload"]
    assert [d.split(" (")[0] for d in decoys["shop/db"]] == ["PVC data-db"]
    assert [d.split(" (")[0] for d in decoys["shop/cache"]] == ["node worker-2"]
    # One per workload, in report order: shop/cache sorts before shop/db.
    assert [d.split(" (")[0] for d in ex.meta["decoy_causes"]] == [
        "node worker-2", "PVC data-db"]


# ------------------------------------------- multi rows on the gather

def _heads(text):
    return [ln[2:].split(" (")[0] for ln in text.splitlines() if ln.startswith("- ")]


def _inventory(user):
    return user.split("== BEGIN inventory ==")[1].split("== END inventory ==")[0]


def _verdict(ex, key):
    return next(r for r in json.loads(ex.assistant)["verdicts"] if r["workload"] == key)


def _three_pairs():
    """Three workloads on three nodes, already in report order. They want
    3 + 2 + 2 reads, so nobody is starved."""
    return [(_entry("memory-limit-oomkill"), _names("billing", "cache", "worker-1")),
            (_entry("probe-failure"), _names("search", "indexer", "worker-2")),
            (_entry("deployment-bad-image-tag"), _names("shop", "gateway", "worker-3"))]


def _crash_pairs():
    """Three crash-family workloads, each on its own live node, in report
    order. Each wants 3 reads: its events, a describe of its node and its
    previous log. The budget of 8 runs out on the third one's log."""
    return [(_entry("memory-limit-oomkill"), _names("auth", "cache", "worker-1")),
            (_entry("crashloop-pod"), _names("batch", "worker", "worker-2")),
            (_entry("container-start-error"), _names("billing", "api", "worker-3"))]


def _starved_row(e):
    """`_crash_pairs` plus `e` as shop/gateway on worker-4, which sorts last
    and gets no read at all."""
    return cases.multi([*_crash_pairs(), (e, _names("shop", "gateway", "worker-4"))],
                       random.Random(26))


@pytest.mark.parametrize("builder", [cases.multi, cases.multi_misattribution_probe])
def test_a_multi_row_prints_its_workloads_in_report_order(builder):
    """kubeagent gives every flagged workload one priority and then sorts
    by namespace and name (Prioritize, internal/inventory/inventory.go:633-645
    at v1.24.0). Pairs handed over in reverse still print in that order: the
    inventory, the candidate blocks, the reads and the answer rows."""
    pairs = _three_pairs()
    ex = builder(list(reversed(pairs)), random.Random(26))
    want = ["billing/cache", "search/indexer", "shop/gateway"]
    assert _heads(_inventory(ex.user)) == want
    assert _heads(_cand_section(ex.user)) == want
    events = [label.split(" ")[1] for label in _evidence_labels(ex.user)
              if label.startswith("events ")]
    assert [pod.rsplit("-", 2)[0] for pod in events] == want
    assert [r["workload"] for r in json.loads(ex.assistant)["verdicts"]] == want
    assert ex.group == "+".join(f"{e.key}:{n.ns}/{n.name}" for e, n in pairs)


@pytest.mark.parametrize("builder", [cases.multi, cases.multi_misattribution_probe])
def test_every_workload_of_a_multi_row_prints_its_finding(builder):
    ex = builder(_three_pairs(), random.Random(26))
    inv = _inventory(ex.user)
    for e, n in _three_pairs():
        block = inv.split(f"- {n.ns}/{n.name} (")[1].split("\n- ")[0]
        assert f"    issue: {e.issue} — " in block, n.name


@pytest.mark.parametrize("builder", [cases.multi, cases.multi_misattribution_probe])
def test_a_multi_row_refuses_two_workloads_on_one_node(builder):
    """One node has one state in a row. Two pods on one node would show it
    attributed to one workload and ruled out, as a foreign node, to the
    other."""
    pairs = [(_entry("memory-limit-oomkill"), _names("billing", "cache", "worker-2")),
             (_entry("probe-failure"), _names("shop", "gateway", "worker-2"))]
    with pytest.raises(ValueError, match=re.escape(
            f"{builder.__name__} needs distinct nodes: billing/cache and shop/gateway "
            "both run on worker-2")):
        builder(pairs, random.Random(3))


@pytest.mark.parametrize("builder", [cases.multi, cases.multi_misattribution_probe])
def test_a_multi_row_refuses_two_workloads_on_one_claim(builder):
    pairs = [(_entry("memory-limit-oomkill"), _names("shop", "cache", "worker-1", pvc="data-1")),
             (_entry("probe-failure"), _names("shop", "gateway", "worker-2", pvc="data-1"))]
    with pytest.raises(ValueError, match=re.escape(
            f"{builder.__name__} needs distinct claims: shop/cache and shop/gateway "
            "both use claim shop/data-1")):
        builder(pairs, random.Random(3))


def test_one_claim_name_in_two_namespaces_is_two_claims():
    pairs = [(_entry("memory-limit-oomkill"),
              _names("billing", "cache", "worker-1", pvc="data-1")),
             (_entry("probe-failure"), _names("shop", "gateway", "worker-2", pvc="data-1"))]
    assert cases.multi_clash([n for _e, n in pairs]) == ""
    assert len(json.loads(cases.multi(pairs, random.Random(3)).assistant)["verdicts"]) == 2


def _header_total(user):
    m = re.search(r"— \d+/(\d+) nodes Ready", user)
    return int(m.group(1)) if m else 3


def test_a_row_with_a_bigger_header_is_gathered_twice(monkeypatch):
    """The other branch: a down node named by two workloads raises the total."""
    calls = []
    real = gather.gather
    monkeypatch.setattr(gather, "gather", lambda w, **kw: (calls.append(1), real(w, **kw))[1])
    ex = cases.multi(_crash_pairs() + [(_entry("node-cordon-diskfull"),
                                        _names("shop", "gateway", "worker-4"))],
                     random.Random(26))
    assert _header_total(ex.user) != 3
    assert len(calls) == 2


def test_a_multi_row_runs_one_gather_under_one_budget(monkeypatch):
    """One gather reads for every workload of the row, with the whole budget
    of 8. Three crash-family workloads want 9 reads, so the row uses all 8.
    2026-10-05 (Spec 4b-3): the healthy-origin read and its parametrize are
    gone."""
    calls = []
    real = gather.gather

    def spy(workloads, **kw):
        calls.append((len(workloads), kw.get("budget", c.MAX_TOOL_CALLS)))
        return real(workloads, **kw)

    monkeypatch.setattr(gather, "gather", spy)
    ex = cases.multi(_crash_pairs(), random.Random(26))
    labels = _evidence_labels(ex.user)
    # A row whose header counts more than 3 nodes is built twice, with no new
    # draw; any other row is built once.
    assert calls == [(3, c.MAX_TOOL_CALLS)] * (1 if _header_total(ex.user) == 3 else 2)
    assert len(labels) == c.MAX_TOOL_CALLS
    assert len(set(labels)) == len(labels)
    assert "origin_read_label" not in ex.meta


def test_the_fourth_workload_of_a_full_row_gets_no_read():
    ex = _starved_row(_entry("node-cordon-diskfull"))
    labels = _evidence_labels(ex.user)
    assert len(labels) == c.MAX_TOOL_CALLS
    assert labels[-1].startswith("describe node /worker-3")
    assert not [label for label in labels if "shop/gateway" in label]


def test_a_starved_workload_whose_block_names_its_cause_answers_it():
    """node-cordon-diskfull's keys, "unschedulable" and "taint", are both on
    its finding line, so its own block names its cause with no read.
    2026-10-04 (Spec 4b-2): the kit's keys and answer, through the gate."""
    e = _entry("node-cordon-diskfull")
    n = _names("shop", "gateway", "worker-4")
    ex = _starved_row(e)
    # 2026-10-05 (Spec 4b-3): the row's nodes are the header's.
    n = dataclasses.replace(n, nodes=_header_total(ex.user))
    row = _verdict(ex, "shop/gateway")
    assert (row["cause"], row["confidence"]) == (cases._fmt(e.answer.cause, n),
                                                 e.answer.confidence)
    assert row["rationale"] == cases._fmt(e.answer.rationale, n)
    wm = ex.meta["workloads"]["shop/gateway"]
    assert (wm["job"], wm["own_cause_keywords"]) == (2, list(e.answer.keys))


def test_a_starved_workload_whose_block_lacks_a_keyword_answers_none_of_these():
    """The same row, with keywords its block does not print. Nothing the
    prompt shows about the workload names the cause, so the gold is
    `none of these`, as on a thin row."""
    # 2026-10-04 (Spec 4b-2): a kit whose keys the block does not print.
    e0 = _entry("node-cordon-diskfull")
    e = dataclasses.replace(e0, answer=stories.Answer(
        anchor=e0.answer.anchor, cause="the node reports disk pressure",
        keys=("disk", "pressure"), rationale="x."))
    ex = _starved_row(e)
    row = _verdict(ex, "shop/gateway")
    assert (row["cause"], row["confidence"], row["rationale"]) == (
        c.NONE_OF_THESE, "low", cases._THIN_RATIONALE["ruled_out"])
    wm = ex.meta["workloads"]["shop/gateway"]
    assert (wm["job"], wm["expected_cause"], wm["own_cause_keywords"]) == (
        2, c.NONE_OF_THESE, [])
    assert ex.meta["expected"]["shop/gateway"] == c.NONE_OF_THESE


def test_a_starved_workload_with_a_live_candidate_is_decided():
    """The gather never read probe-failure's node, so the rules keep the
    attribution, unverified: job 1, not the thin rule."""
    ex = _starved_row(_entry("probe-failure"))
    wm = ex.meta["workloads"]["shop/gateway"]
    assert (wm["job"], wm["decided"], wm["decided_outcome"]) == (1, True, "unverified")
    assert wm["decided_cause"].startswith("node worker-4 (")
    assert _verdict(ex, "shop/gateway")["cause"] == wm["decided_cause"]


def test_the_multi_probe_refuses_a_workload_the_budget_never_reached():
    """A probe workload with no read has nothing to judge its own cause
    from, so the row would not test what it is built to test."""
    pairs = [*_crash_pairs(), (_entry("probe-failure"), _names("shop", "gateway", "worker-4"))]
    with pytest.raises(ValueError, match=re.escape(
            "multi_misattribution_probe: the read budget never reached shop/gateway")):
        cases.multi_misattribution_probe(pairs, random.Random(7))


def test_prose_decoy_helpers_are_retired():
    """No builder builds a prose decoy menu through these three helpers, and
    no builder renders its evidence panel by hand through _reads. multi()
    was the last caller of both _candidates and _reads."""
    for helper_name in ("_candidates", "_swapped_candidates", "_decoy_cause", "_reads"):
        assert not hasattr(cases, helper_name), (
            f"cases.{helper_name} should be deleted once every builder reads e.objects")


def test_the_catalog_winner_helpers_are_retired():
    """Every job-1 row is built on the gather, so nothing reads the catalog's
    hand-written winner or draws an ending for it any more."""
    for helper_name in ("_winner_example", "_option_a_menu", "draw_ending"):
        assert not hasattr(cases, helper_name), (
            f"cases.{helper_name} should be deleted once job-1 rows use the gather")


def test_the_read_budget_helpers_are_retired():
    """Every row takes its reads from the gather, which spends the budget
    itself. contradiction_probe was the last single-workload builder to
    apply the budget by hand, and the two multi builders were the last to
    build their reads by hand."""
    assert not hasattr(cases, "_decoy_result")
    for helper_name in ("_multi_reads", "_cap_reads", "_to_contract_candidates",
                        "_WORKER_NAMES"):
        assert not hasattr(cases, helper_name), helper_name
    for helper_name in ("apply_budget", "object_reads", "registry_events_read",
                        "render_workload"):
        assert not hasattr(render, helper_name), helper_name
        assert helper_name not in render.__all__, helper_name


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


# The two functions allowed to call `build_user_message`. Each must also call
# `render.check_prompt_size`, which `test_each_funnel_checks_the_prompt_size`
# pins, so a third call site cannot slip past the byte cap (Ruling 34).
_FUNNELS = {("cases.py", "_user_message"), ("shared_origin.py", "build")}


def _build_user_message_calls_outside_the_funnel() -> list[str]:
    """Every call to `build_user_message` found by parsing every module under
    `src/kubeagent_verdict/dataset/`, except the calls inside the two funnels
    in `_FUNNELS`: `cases._user_message` and `shared_origin.build`. Returns
    "path:lineno" strings for whatever is left; an empty list means every call
    site in the package goes through a funnel (and so through
    `render.check_prompt_size`).
    """
    dataset_dir = pathlib.Path(cases.__file__).parent
    findings: list[str] = []
    for path in sorted(dataset_dir.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        funnel_call_ids: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (path.name, node.name) in _FUNNELS:
                funnel_call_ids |= {id(sub) for sub in ast.walk(node)
                                    if _is_build_user_message_call(sub)}
        for node in ast.walk(tree):
            if _is_build_user_message_call(node) and id(node) not in funnel_call_ids:
                findings.append(f"{path.name}:{node.lineno}")
    return findings


def test_every_build_user_message_call_goes_through_the_checked_funnel():
    """`check_prompt_size` only ever runs if every `build_user_message(...)`
    call routes through one of the two funnels in `_FUNNELS`
    (`cases._user_message` and `shared_origin.build`), each of which pairs the
    two. This parses every module under `src/kubeagent_verdict/dataset/` with
    `ast` and flags any `build_user_message` call it finds outside those two
    funnel functions -- by attribute, under any import alias
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
        f"src/kubeagent_verdict/dataset/ to route through a funnel in _FUNNELS; "
        f"found call(s) outside it: {findings}"
    )


def test_each_funnel_checks_the_prompt_size():
    dataset_dir = pathlib.Path(cases.__file__).parent
    for fname, func in sorted(_FUNNELS):
        tree = ast.parse((dataset_dir / fname).read_text())
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == func)
        calls = {s.func.attr if isinstance(s.func, ast.Attribute) else getattr(s.func, "id", "")
                 for s in ast.walk(fn) if isinstance(s, ast.Call)}
        assert "check_prompt_size" in calls, (fname, func)


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


# The one helper that turns an entry and its drawn names into the gather's
# workload. Tasks that move other builders onto the gather call it too.

def test_gather_workload_fills_a_plain_entry():
    e = _entry("probe-failure")
    n = names_mod.draw(random.Random(5))
    menu = cases._refuted_menu(n, e.objects)
    assert cases.gather_workload(e, n, menu) == gather.GatherWorkload(
        namespace=n.ns, name=n.name, pod=n.pod, issue="ProbeFailure", objects=menu,
        events=(("Unhealthy",
                 "Readiness probe failed: HTTP probe failed with statuscode: 500", 2),),
        findings=(gather.GatherFinding(issue="ProbeFailure", pod=f"{n.ns}/{n.pod}",
                                       container=n.container, log_read=None,
                                       image=n.image),))


def test_gather_workload_names_the_init_container_on_an_init_finding():
    e = _entry("init-crashloop")
    n = names_mod.draw(random.Random(5))
    w = cases.gather_workload(e, n, ())
    (f,) = w.findings
    assert (f.issue, f.container, f.log_read) == (
        "Init:CrashLoopBackOff", n.init_container, None)
    assert w.events == ((
        "BackOff", f"Back-off restarting failed container {n.init_container} in pod {n.pod}",
        n.restarts),)


def test_gather_workload_names_the_coredns_container():
    e = _entry("coredns-corefile-broken")
    n = names_mod.draw(random.Random(5))
    (f,) = cases.gather_workload(e, n, ()).findings
    assert f.container == "coredns"
    assert f.log_read == "log cause: configuration parse/validation error"


@pytest.mark.parametrize(("evidence", "content"), [
    ("clear", "log cause: bad command or entrypoint"),
    ("thin", _NO_CLASSIFIABLE),
])
def test_gather_workload_carries_the_crash_familys_log_body(evidence, content):
    e = _entry("crashloop-pod")
    n = names_mod.draw(random.Random(5))
    (f,) = cases.gather_workload(e, n, (), evidence=evidence).findings
    assert (f.container, f.log_read) == (
        n.container, content.format(ns=n.ns, pod=n.pod, container=n.container))


@pytest.mark.parametrize("key", ["restart-loop", "deployment-bad-image-tag",
                                 "node-cordon-diskfull"])
def test_gather_workload_has_no_log_outside_the_crash_family(key):
    n = names_mod.draw(random.Random(5))
    (f,) = cases.gather_workload(_entry(key), n, ()).findings
    assert f.log_read is None


def test_gather_workload_takes_the_image_from_the_names():
    """One image per row: the finding's and the one the events quote."""
    e = _entry("deployment-bad-image-tag")
    n = dataclasses.replace(names_mod.draw(random.Random(5)),
                            image="registry.example.com/web/cart:v9.9.9")
    w = cases.gather_workload(e, n, ())
    assert w.findings[0].image == "registry.example.com/web/cart:v9.9.9"
    assert w.events[0] == (
        "Failed", 'Failed to pull image "registry.example.com/web/cart:v9.9.9": not found', 1)


def test_the_suggestion_and_the_gather_name_the_same_container(monkeypatch):
    """One function decides the finding's container. The suggested fix's
    --previous command and the gather's log read both address it. The
    suggestion goes through `suggest_for`, the port of kubeagent's
    `suggestionFor`, with the row's workload."""
    seen = []
    real = cases.rem.suggest_for

    def spy(issue, **kw):
        seen.append((kw["container"], kw["workload"]))
        return real(issue, **kw)

    monkeypatch.setattr(cases.rem, "suggest_for", spy)
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        seen.clear()
        cases._suggestion(e.issue, n, key=e.key)
        (f,) = cases.gather_workload(e, n, ()).findings
        assert seen == [(f.container, n.name)], e.key
        log = cases._log_read(e, n, "clear")
        if log is not None:
            assert log.label.endswith(f" container {f.container}"), e.key


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
        f"== events {n.ns}/{n.pod} ==\n"
        f"events for {n.ns}/{n.pod}:\n"
        f"  BackOff: Back-off restarting failed container {n.container} in pod {n.pod} "
        f"(x{n.restarts})\n\n"
        f"== log causes {n.ns}/{n.pod} container {n.container} ==\n"
        "log cause: bad command or entrypoint")


def test_a_ruled_out_row_outside_the_crash_family_has_only_the_events_read():
    """kubeagent reads every scoped workload's events, whatever its
    candidates (internal/investigate/gather.go:71-90)."""
    ex, n = _undecided("probe-failure", case="own_cause", shape="ruled_out",
                       evidence="clear")
    assert _evidence_section(ex.user) == (
        f"== events {n.ns}/{n.pod} ==\n"
        f"events for {n.ns}/{n.pod}:\n"
        "  Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 500 (x2)")


@pytest.mark.parametrize(("key", "header"), [
    ("networkpolicy-deny-all", "high"),      # a node cause; the kit says medium
    ("probe-failure", "high"),               # a node cause; the kit says high
    ("restart-loop", "high"),                # a node cause; the kit says high
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
    # 2026-09-26 (faithful prompts): pvc-unbound-unschedulable is trainable
    # and not thin 15 -> 16
    assert len(outside) == 16
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
def test_a_clear_row_answers_the_kits_cause_at_the_kits_confidence(case, shape):
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        ex = cases._undecided_example(e, n, case=case, shape=shape, evidence="clear")
        (row,) = json.loads(ex.assistant)["verdicts"]
        # 2026-10-04 (Spec 4b-2): the kit's cause and confidence, not the entry's.
        assert row["cause"] == cases._fmt(e.answer.cause, n) == ex.meta["expected_cause"]
        assert row["confidence"] == e.answer.confidence == ex.meta["expected_confidence"], e.key


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
    assert doc["verdicts"][0]["rationale"] == cases._fmt(e.answer.rationale, n) + suffix
    want = last_line or cases._fmt(e.recommendation, n).capitalize() + "."
    assert doc["summary"] == f"{n.ns}/{n.name} is failing: {cases._fmt(e.answer.cause, n)}.\n{want}"


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
    e = _two_object_entry()
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


# The undecided rows read what kubeagent reads: the events of the workload's
# pod, a describe per live node or PVC candidate, then the crash family's
# log (internal/investigate/gather.go:71-156). A ruled-out candidate is
# never read (gather.go:94-96).

def _labels_for(key, n):
    container = "coredns" if key == "coredns-corefile-broken" else n.container
    return {"events": f"events {n.ns}/{n.pod}", "describe": f"describe node /{n.node}",
            "log": f"log causes {n.ns}/{n.pod} container {container}"}


@pytest.mark.parametrize(("key", "case", "shape", "evidence", "kinds"), [
    ("memory-limit-oomkill", "wrong_attribution", "refuted", "clear",
     ("events", "describe", "log")),
    ("probe-failure", "wrong_attribution", "refuted", "clear", ("events", "describe")),
    ("crashloop-pod", "own_cause", "ruled_out", "clear", ("events", "log")),
    ("probe-failure", "own_cause", "ruled_out", "clear", ("events",)),
    ("crashloop-pod", "none_of_these", "refuted", "thin", ("events", "describe", "log")),
    ("init-crashloop", "none_of_these", "refuted", "thin", ("events", "describe")),
    ("coredns-corefile-broken", "none_of_these", "ruled_out", "thin", ("events", "log")),
    ("restart-loop", "none_of_these", "ruled_out", "thin", ("events",)),
])
def test_the_undecided_reads_come_in_kubeagents_order(key, case, shape, evidence, kinds):
    ex, n = _undecided(key, case=case, shape=shape, evidence=evidence)
    labels = _labels_for(key, n)
    assert _evidence_labels(ex.user) == [labels[k] for k in kinds]


@pytest.mark.parametrize("shape", SHAPES)
def test_every_undecided_row_reads_the_events_first_and_the_log_last(shape):
    rank = {"events": 0, "describe": 1, "log": 2}
    for e in catalog.trainable():
        n = names_mod.draw(random.Random(5))
        ex = cases._undecided_example(e, n, case="own_cause", shape=shape, evidence="clear")
        kinds = [label.split(" ", 1)[0] for label in _evidence_labels(ex.user)]
        assert kinds[0] == "events" and kinds.count("events") == 1, e.key
        assert [rank[k] for k in kinds] == sorted(rank[k] for k in kinds), e.key
        assert ("log" in kinds) == (e.key in cases.LOG_READS), e.key
        if shape == "ruled_out":
            assert "describe" not in kinds, e.key


def test_the_undecided_candidates_come_from_the_gather():
    """The fresh lines are the gather's, paired by `pair_candidates`: the
    live node gets its refuted read and the ruled-out PVC gets none."""
    e = _two_object_entry()
    pvc = dataclasses.replace(e.objects[1], placement="unmounted")
    e = dataclasses.replace(e, objects=(e.objects[0], pvc))
    n = names_mod.draw(random.Random(5))
    ex = cases.wrong_attribution(e, n)
    res = gather.gather([cases.gather_workload(e, n, cases._refuted_menu(n, e.objects))])
    node, claim = res.candidates[0]
    assert (node.verdict, node.fresh_read_outcome) == ("attributed", "refuted")
    assert (claim.verdict, claim.fresh_read_outcome, claim.fresh_read_evidence) == (
        "ruled_out", "", "")
    section = _cand_section(ex.user)
    assert (f"    considered {node.cause}: attributed — {node.reason}\n"
            f"      fresh read: refuted — {node.fresh_read_evidence}\n"
            f"    considered {claim.cause}: ruled out — {claim.reason}\n") in section
    assert section.count("fresh read:") == 1


def test_the_bad_image_tag_row_shows_a_ruled_out_registry():
    """The gather counts a registry's pulling workloads over the row
    (internal/rootcause/rootcause.go:99-139). One workload is below the
    threshold of 2, so kubeagent rules the registry out and nothing is
    attributed, refuted or described: no header, no fresh read."""
    ex, n = _undecided("deployment-bad-image-tag", case="wrong_attribution",
                       shape="refuted", evidence="clear")
    assert _cand_section(ex.user) == (
        f"\n- {n.ns}/{n.name} (Deployment):\n"
        "    considered registry registry.example.com: ruled out — only workload failing "
        "to pull from this host; threshold is 2\n")
    assert _evidence_labels(ex.user) == [f"events {n.ns}/{n.pod}"]
    assert ex.meta["decoy_cause"] == "registry registry.example.com"


# Where a thin row's keywords show up. coredns-corefile-broken's keywords
# ("coredns", "error") are both on its finding line (container "coredns",
# last exit 1 (Error)) with or without this change. That is a known gap,
# pinned here so a fix shows up.
THIN_SHOWS_EVERY_KEYWORD = {"coredns-corefile-broken"}


@pytest.mark.parametrize("key", cases.THIN_ENTRIES)
@pytest.mark.parametrize("shape", SHAPES)
def test_a_thin_row_hides_at_least_one_keyword(key, shape):
    """The events read is in every thin row now, so a keyword may show up.
    The row still must not show all of them (the grader's rule, all
    keywords, lowercase)."""
    e = _entry(key)
    for seed in range(20):
        ex, _ = _undecided(key, case="none_of_these", shape=shape, evidence="thin", seed=seed)
        user = ex.user.lower()
        shown = all(k.lower() in user for k in e.answer.keys)
        assert shown == (key in THIN_SHOWS_EVERY_KEYWORD), (key, seed)
