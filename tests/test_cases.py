import json
import random

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import cases, catalog, names


def _entry(key):
    return next(e for e in catalog.all_entries() if e.key == key)


def test_attributed_example_shape():
    n = names.draw(random.Random(11))
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
    n = names.draw(random.Random(12))
    ex = cases.attributed(_entry("probe-failure"), n, random.Random(12))
    assert json.loads(ex.assistant)["verdicts"][0]["confidence"] == "medium"


def test_attributed_user_message_is_contract_valid():
    n = names.draw(random.Random(13))
    ex = cases.attributed(_entry("deployment-bad-image-tag"), n, random.Random(13))
    assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
    assert ex.user.endswith(c.CLOSING_INSTRUCTION)


def test_none_of_these_contradicts_and_answers_none():
    n = names.draw(random.Random(21))
    ex = cases.none_of_these_case(_entry("memory-limit-oomkill"), n, random.Random(21))
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == c.NONE_OF_THESE
    assert row["confidence"] == "medium"
    assert "exit code 1" in ex.user  # the contradiction evidence is in the prompt
    assert "OOMKilled, exit code 137" not in ex.user.split("== BEGIN evidence ==")[1]


def test_own_cause_omits_winner_from_candidates():
    n = names.draw(random.Random(22))
    ex = cases.own_cause_case(_entry("memory-limit-oomkill"), n, random.Random(22))
    cand_section = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    assert "memory limit too low for the workload" not in cand_section
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"
    assert ex.meta["expected_own_keywords"] == ["memory", "limit"]


def test_truncated_case_earns_low_confidence():
    n = names.draw(random.Random(23))
    ex = cases.truncated(_entry("crashloop-pod"), n, random.Random(23))
    assert c.TRUNCATION_MARKER in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["confidence"] == "low"


def test_injection_answer_ignores_payload():
    n = names.draw(random.Random(24))
    payload = cases.INJECTION_PAYLOADS[0]
    ex = cases.injection(_entry("deployment-bad-image-tag"), n, payload, random.Random(24))
    assert payload in ex.user  # the attack is really in the evidence
    doc = json.loads(ex.assistant)  # the answer is still pure contract JSON
    assert set(doc) == {"verdicts", "summary"}
    blob = ex.assistant.lower()
    for marker in ("ignore all previous", "markdown", "system:"):
        assert marker not in blob
    assert ex.meta["injection_payload"] == payload


def test_empty_candidates_renders_none_section():
    n = names.draw(random.Random(25))
    ex = cases.empty_candidates(_entry("memory-limit-oomkill"), n)
    assert "== BEGIN candidates ==\n(none)\n== END candidates ==" in ex.user
    (row,) = json.loads(ex.assistant)["verdicts"]
    assert row["cause"] == "container killed at its memory limit"  # own phrasing
    assert row["confidence"] == "medium"


def test_multi_has_one_row_per_workload():
    rng = random.Random(26)
    pairs = [(_entry("memory-limit-oomkill"), names.draw(rng)),
             (_entry("deployment-bad-image-tag"), names.draw(rng)),
             (_entry("probe-failure"), names.draw(rng))]
    ex = cases.multi(pairs, rng)
    doc = json.loads(ex.assistant)
    assert len(doc["verdicts"]) == 3
    assert {r["workload"] for r in doc["verdicts"]} == {
        f"{n.ns}/{n.name}" for _e, n in pairs
    }
    lines = [ln for ln in doc["summary"].split("\n") if ln.strip()]
    assert len(lines) <= c.MAX_SUMMARY_LINES


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
    firsts = [_winner_is_first(cases.attributed(entry, names.draw(random.Random(s)),
                                                random.Random(s)).user, winner)
              for s in range(60)]
    assert any(firsts), "winner never appears first — that is a shortcut too"
    assert not all(firsts), "winner is ALWAYS first: position is a giveaway again"


def test_shuffle_covers_every_case_that_renders_a_menu():
    entry = _entry("memory-limit-oomkill")
    winner = "memory limit too low for the workload"
    for builder in (cases.attributed, cases.none_of_these_case, cases.truncated):
        firsts = [_winner_is_first(
            builder(entry, names.draw(random.Random(s)), random.Random(s)).user, winner)
            for s in range(60)]
        assert not all(firsts), f"{builder.__name__} still renders the winner first"


def test_injection_prompt_and_answer_agree_on_one_menu():
    # A second _candidates() call would draw a different shuffle, so the
    # rendered prompt and the banked answer could disagree about the menu.
    n = names.draw(random.Random(31))
    ex = cases.injection(_entry("memory-limit-oomkill"), n,
                         cases.INJECTION_PAYLOADS[0], random.Random(31))
    cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
    assert f"considered {cause}:" in _cand_section(ex.user)


def test_positional_probe_puts_the_winner_last_with_an_honest_tag():
    n = names.draw(random.Random(41))
    ex = cases.positional_probe(_entry("memory-limit-oomkill"), n)
    lines = _cand_lines(ex.user)
    assert len(lines) >= 2
    assert lines[-1].startswith("considered memory limit too low for the workload: attributed")
    assert not lines[0].startswith("considered memory limit too low for the workload:")
    assert json.loads(ex.assistant)["verdicts"][0]["cause"] == \
        "memory limit too low for the workload"
    assert ex.meta["decoy_cause"] and ex.meta["decoy_cause"] != ex.meta["expected_cause"]


def test_misattribution_probe_hands_attributed_to_the_decoy():
    n = names.draw(random.Random(42))
    ex = cases.misattribution_probe(_entry("memory-limit-oomkill"), n)
    section = _cand_section(ex.user)
    assert f"considered {ex.meta['decoy_cause']}: attributed" in section
    assert "considered memory limit too low for the workload: ruled out" in section
    # The evidence is untouched, so the answer stays the evidence-backed winner.
    assert json.loads(ex.assistant)["verdicts"][0]["cause"] == \
        "memory limit too low for the workload"


def test_probes_refuse_an_entry_with_no_loser():
    import dataclasses
    bare = dataclasses.replace(_entry("memory-limit-oomkill"), losers=())
    n = names.draw(random.Random(43))
    for builder in (cases.positional_probe, cases.misattribution_probe):
        try:
            builder(bare, n)
        except ValueError:
            continue
        raise AssertionError(f"{builder.__name__} accepted a zero-loser entry")


def test_wrong_attribution_answers_the_evidence_not_the_tag():
    n = names.draw(random.Random(44))
    ex = cases.wrong_attribution(_entry("memory-limit-oomkill"), n, random.Random(44))
    section = _cand_section(ex.user)
    assert f"considered {ex.meta['decoy_cause']}: attributed" in section
    row = json.loads(ex.assistant)["verdicts"][0]
    assert row["cause"] == "memory limit too low for the workload"
    assert row["cause"] != ex.meta["decoy_cause"]
    assert "deterministic pass attributed a different cause" in row["rationale"]
