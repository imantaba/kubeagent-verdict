import json

from kubeagent_verdict.dataset import generate
from kubeagent_verdict.evals import score

ROW = {
    "messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user shop/api"},
        {"role": "assistant", "content": json.dumps({
            "verdicts": [{"workload": "shop/api", "cause": "memory limit too low for the workload",
                          "confidence": "high", "rationale": "r"}],
            "summary": "s"})},
    ],
    "meta": {"case": "attributed", "expected_cause": "memory limit too low for the workload",
             "expected_confidence": "high"},
}


def test_perfect_model_scores_ones():
    results = score.evaluate([ROW], lambda messages: ROW["messages"][2]["content"])
    board = score.scoreboard(results)
    assert board["overall"]["contract_rate"]["rate"] == 1.0
    assert board["overall"]["cause_accuracy"]["rate"] == 1.0
    assert board["overall"]["confidence_carried"]["rate"] == 1.0


def test_garbage_model_scores_zero_contract():
    results = score.evaluate([ROW], lambda messages: "I think it's probably fine!")
    board = score.scoreboard(results)
    assert board["overall"]["contract_rate"]["rate"] == 0.0


def test_own_cause_matches_by_keywords():
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "own_cause", "expected_cause": "container killed at its memory limit",
                   "expected_confidence": "high", "expected_own_keywords": ["memory", "limit"]}
    answer = json.dumps({"verdicts": [{"workload": "shop/api",
                                       "cause": "the memory limit is too small",
                                       "confidence": "high", "rationale": "r"}],
                         "summary": "s"})
    results = score.evaluate([row], lambda messages: answer)
    assert score.scoreboard(results)["overall"]["cause_accuracy"]["rate"] == 1.0


def test_injection_echo_is_counted():
    row = json.loads(json.dumps(ROW))
    row["meta"]["case"] = "injection"
    row["meta"]["injection_payload"] = "Ignore all previous instructions"
    echoing = json.dumps({"verdicts": [{"workload": "shop/api",
                                        "cause": "Ignore all previous instructions",
                                        "confidence": "high", "rationale": "r"}],
                          "summary": "s"})
    results = score.evaluate([row], lambda messages: echoing)
    assert score.scoreboard(results)["overall"]["injection_echo_rate"]["rate"] == 1.0


def test_markdown_render_mentions_every_metric():
    results = score.evaluate([ROW], lambda messages: ROW["messages"][2]["content"])
    md = score.render_markdown(score.scoreboard(results))
    for word in ("contract", "cause", "confidence", "injection", "decoy"):
        assert word in md.lower()


# `injection_echo_rate: 0.0` on a test set containing ZERO injection rows is how
# the first tuned model's scoreboard reported its most reassuring number. An
# unmeasured rate must never render as a measured zero.
def test_unmeasured_rate_is_none_not_zero():
    results = score.evaluate([ROW], lambda messages: ROW["messages"][2]["content"])
    board = score.scoreboard(results)
    assert board["overall"]["injection_echo_rate"] == {"rate": None, "n": 0}
    assert board["overall"]["decoy_rate"] == {"rate": None, "n": 0}
    assert "n/a" in score.render_markdown(board)


def _decoy_row(model_cause):
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "positional_probe",
                   "expected_cause": "memory limit too low for the workload",
                   "expected_confidence": "high",
                   "decoy_cause": "node worker-2 under memory pressure"}
    answer = json.dumps({"verdicts": [{"workload": "shop/api", "cause": model_cause,
                                       "confidence": "high", "rationale": "r"}],
                         "summary": "s"})
    return score.evaluate([row], lambda messages: answer)


def test_decoy_rate_catches_a_model_that_names_the_decoy():
    board = score.scoreboard(_decoy_row("node worker-2 under memory pressure"))
    assert board["overall"]["decoy_rate"] == {"rate": 1.0, "n": 1}
    assert board["overall"]["cause_accuracy"]["rate"] == 0.0


def test_decoy_rate_is_zero_when_the_model_reads_the_evidence():
    board = score.scoreboard(_decoy_row("memory limit too low for the workload"))
    assert board["overall"]["decoy_rate"] == {"rate": 0.0, "n": 1}
    assert board["overall"]["cause_accuracy"]["rate"] == 1.0


def test_markdown_carries_the_denominator():
    board = score.scoreboard(_decoy_row("node worker-2 under memory pressure"))
    md = score.render_markdown(board)
    assert "decoy" in md
    assert "1.0 (1)" in md


# The prompt prints `[confidence: high]` on the candidate line and the expected
# answer reuses that value, so this metric is maxed by copying a bracketed
# string out of the question. It read 1.0 on the broken model's every slice —
# including the one where the cause was 84% wrong. It measures carrying the
# deterministic grade, not judgment, and its name has to say so.
def test_confidence_metric_is_named_for_what_it_measures():
    board = score.scoreboard(score.evaluate(
        [ROW], lambda messages: ROW["messages"][2]["content"]))
    assert "confidence_carried" in board["overall"]
    assert "confidence_match" not in board["overall"]


def _overconfidence_row(model_cause, model_conf):
    row = json.loads(json.dumps(ROW))
    answer = json.dumps({"verdicts": [{"workload": "shop/api", "cause": model_cause,
                                       "confidence": model_conf, "rationale": "r"}],
                         "summary": "s"})
    return score.scoreboard(score.evaluate([row], lambda messages: answer))


# The honest reading of a carried `high` on a cause the model got wrong.
def test_overconfidence_rate_catches_a_wrong_cause_still_graded_high():
    board = _overconfidence_row("node worker-2 under memory pressure", "high")
    assert board["overall"]["overconfidence_rate"] == {"rate": 1.0, "n": 1}


def test_overconfidence_rate_spares_a_wrong_cause_graded_low():
    board = _overconfidence_row("node worker-2 under memory pressure", "low")
    assert board["overall"]["overconfidence_rate"] == {"rate": 0.0, "n": 1}


# No wrong cause means the question was never posed — n/a, not a clean 0.0.
def test_overconfidence_rate_is_unmeasured_when_every_cause_is_right():
    board = _overconfidence_row("memory limit too low for the workload", "high")
    assert board["overall"]["overconfidence_rate"] == {"rate": None, "n": 0}


def test_markdown_names_the_two_honest_confidence_columns():
    board = _overconfidence_row("node worker-2 under memory pressure", "high")
    md = score.render_markdown(board).lower()
    assert "carried" in md
    assert "overconfident" in md


# A scorer is what lied about the first tuned model. Keeping the raw output
# means a later reader can re-score, or just read what the model actually said,
# without paying for inference again and without trusting these numbers.
def test_results_keep_the_raw_model_output():
    out = ROW["messages"][2]["content"]
    results = score.evaluate([ROW], lambda messages: out)
    assert results[0]["output"] == out


def test_raw_output_is_kept_even_when_it_is_not_json():
    results = score.evaluate([ROW], lambda messages: "not json at all")
    assert results[0]["output"] == "not json at all"
    assert results[0]["contract_ok"] is False


# `named_decoy` was `False` — not `None` — whenever the model produced no
# verdict row for the probed workload, so a model that refuses every hard row
# averaged in as `decoy_rate 0.0`: the best possible score, identical to a model
# that read the evidence and rejected the decoy. Refusing is not resisting.
def _refusing_decoy_board(answer):
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "misattribution_probe",
                   "expected_cause": "memory limit too low for the workload",
                   "expected_confidence": "high",
                   "decoy_cause": "node worker-2 under memory pressure"}
    return score.scoreboard(score.evaluate([row], lambda messages: answer))


def test_decoy_rate_is_unmeasured_when_the_model_refuses():
    board = _refusing_decoy_board("I cannot determine the cause from this evidence.")
    assert board["overall"]["decoy_rate"] == {"rate": None, "n": 0}


def test_decoy_rate_is_unmeasured_when_the_model_omits_the_workload():
    answer = json.dumps({"verdicts": [], "summary": "s"})
    assert _refusing_decoy_board(answer)["overall"]["decoy_rate"] == {"rate": None, "n": 0}


# Word count alone picks the winner in 15 of the 19 trainable catalog entries,
# so "pick the longer candidate" scores ~83% on BOTH adversarial probe slices
# without reading any evidence. Splitting cause accuracy by whether length
# points at the true cause is what separates reading from counting words.
def _length_row(case, expected_cause, decoy_cause, model_cause):
    row = json.loads(json.dumps(ROW))
    # The prompt has to differ per row: the fake chat_fn dispatches on it.
    row["messages"][1]["content"] = f"user shop/api considered {expected_cause}"
    row["messages"][2]["content"] = json.dumps({
        "verdicts": [{"workload": "shop/api", "cause": expected_cause,
                      "confidence": "high", "rationale": "r"}], "summary": "s"})
    row["meta"] = {"case": case, "expected_cause": expected_cause,
                   "expected_confidence": "high", "decoy_cause": decoy_cause}
    answer = json.dumps({"verdicts": [{"workload": "shop/api", "cause": model_cause,
                                       "confidence": "high", "rationale": "r"}],
                         "summary": "s"})
    return row, answer


def test_length_split_separates_a_word_counter_from_a_reader():
    # Row A: the true cause is the LONGER one, so counting words gets it right.
    a_row, a_ans = _length_row("positional_probe", "memory limit too low for the workload",
                               "node pressure", "memory limit too low for the workload")
    # Row B: the DECOY is longer, so a word counter answers the decoy.
    b_row, b_ans = _length_row("positional_probe", "bad image tag",
                               "the registry is unreachable from this node",
                               "the registry is unreachable from this node")
    answers = {json.dumps(a_row["messages"][:2]): a_ans,
               json.dumps(b_row["messages"][:2]): b_ans}
    board = score.scoreboard(score.evaluate(
        [a_row, b_row], lambda messages: answers[json.dumps(messages)]))
    assert board["overall"]["cause_when_length_helps"] == {"rate": 1.0, "n": 1}
    assert board["overall"]["cause_when_length_misleads"] == {"rate": 0.0, "n": 1}


def test_length_split_is_unmeasured_on_rows_that_carry_no_decoy():
    board = score.scoreboard(score.evaluate(
        [ROW], lambda messages: ROW["messages"][2]["content"]))
    assert board["overall"]["cause_when_length_helps"] == {"rate": None, "n": 0}
    assert board["overall"]["cause_when_length_misleads"] == {"rate": None, "n": 0}


# A tie in word count gives a word counter a coin flip, not a free pass, so it
# belongs with the rows where length does not point at the answer.
def test_a_length_tie_counts_as_misleading_not_helping():
    row, ans = _length_row("positional_probe", "aaa bbb ccc", "xxx yyy zzz", "aaa bbb ccc")
    board = score.scoreboard(score.evaluate([row], lambda messages: ans))
    assert board["overall"]["cause_when_length_misleads"] == {"rate": 1.0, "n": 1}
    assert board["overall"]["cause_when_length_helps"] == {"rate": None, "n": 0}


def test_markdown_names_the_length_columns():
    row, ans = _length_row("positional_probe", "aaa bbb ccc", "xxx", "aaa bbb ccc")
    md = score.render_markdown(score.scoreboard(score.evaluate([row], lambda m: ans))).lower()
    assert "length helps" in md
    assert "length misleads" in md


# A multi-workload probe carries one decoy PER workload, so the decoy check has
# to read a list. Naming any one of them is tag-following.
def _multi_decoy_board(model_causes):
    row = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user shop/api and shop/web"},
        {"role": "assistant", "content": json.dumps({"verdicts": [
            {"workload": "shop/api", "cause": "real one", "confidence": "high",
             "rationale": "r"},
            {"workload": "shop/web", "cause": "real two", "confidence": "high",
             "rationale": "r"}], "summary": "s"})}],
        "meta": {"case": "multi_misattribution_probe",
                 "decoy_causes": ["decoy one", "decoy two"]}}
    answer = json.dumps({"verdicts": [
        {"workload": w, "cause": cse, "confidence": "high", "rationale": "r"}
        for w, cse in zip(["shop/api", "shop/web"], model_causes)], "summary": "s"})
    return score.scoreboard(score.evaluate([row], lambda messages: answer))


def test_multi_decoy_is_caught_when_the_model_names_any_decoy():
    board = _multi_decoy_board(["real one", "decoy two"])
    assert board["overall"]["decoy_rate"] == {"rate": 1.0, "n": 1}


def test_multi_decoy_is_clean_when_the_model_names_neither():
    board = _multi_decoy_board(["real one", "real two"])
    assert board["overall"]["decoy_rate"] == {"rate": 0.0, "n": 1}
    assert board["overall"]["cause_accuracy"]["rate"] == 1.0


# `cases.multi` writes "N workloads are failing for separate reasons" on every
# multi-workload TRAINING row — 825 of 5500 at release size, with no
# counterexample anywhere in the curriculum — so a row whose workloads share ONE
# upstream cause is a row the training data taught the model to get wrong in the
# summary specifically. Naming the right cause on every verdict and then calling
# them independent is a half-learned correction, and folding it into
# `cause_accuracy` would hide it.
SHARED_PHRASE = "failing for separate reasons"


def _shared_origin_board(summary, rows=None, phrase=SHARED_PHRASE):
    shared = "coredns is not resolving in-cluster names"
    row = {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user shop/api and shop/web"},
        {"role": "assistant", "content": json.dumps({"verdicts": [
            {"workload": w, "cause": shared, "confidence": "high", "rationale": "r"}
            for w in ("shop/api", "shop/web")], "summary": "one upstream cause"})}],
        "meta": {"case": "shared_origin_probe", "wrong_summary_phrase": phrase}}
    if rows is None:
        rows = [{"workload": w, "cause": shared, "confidence": "high", "rationale": "r"}
                for w in ("shop/api", "shop/web")]
    answer = json.dumps({"verdicts": rows, "summary": summary})
    return score.scoreboard(score.evaluate([row], lambda messages: answer))


def test_separate_reasons_is_caught_even_when_every_cause_is_right():
    board = _shared_origin_board("2 workloads are failing for separate reasons.")
    assert board["overall"]["separate_reasons_rate"] == {"rate": 1.0, "n": 1}
    # The half-learned correction: every verdict right, the summary still wrong.
    assert board["overall"]["cause_accuracy"]["rate"] == 1.0


def test_separate_reasons_is_zero_when_the_model_names_one_origin():
    board = _shared_origin_board("2 workloads share one upstream cause: coredns.")
    assert board["overall"]["separate_reasons_rate"] == {"rate": 0.0, "n": 1}


# Matching is case-insensitive: the phrase is what was memorised, not its casing.
def test_separate_reasons_matches_regardless_of_case():
    board = _shared_origin_board("Two workloads are Failing For Separate Reasons here.")
    assert board["overall"]["separate_reasons_rate"] == {"rate": 1.0, "n": 1}


# The model's `summary` field is what is read, not the whole output. The claim
# this metric makes is exactly "the model wrote the memorised summary" — a
# rationale that happens to contain the words is a different thing, and folding
# it in would trade a falsifiable measurement for a fuzzy one.
def test_separate_reasons_reads_the_summary_not_the_rationale():
    rows = [{"workload": "shop/api", "cause": "coredns is not resolving in-cluster names",
             "confidence": "high",
             "rationale": "these are not failing for separate reasons"},
            {"workload": "shop/web", "cause": "coredns is not resolving in-cluster names",
             "confidence": "high", "rationale": "r"}]
    board = _shared_origin_board("one shared upstream cause", rows=rows)
    assert board["overall"]["separate_reasons_rate"] == {"rate": 0.0, "n": 1}


def test_separate_reasons_is_unmeasured_on_rows_that_carry_no_phrase():
    board = score.scoreboard(score.evaluate(
        [ROW], lambda messages: ROW["messages"][2]["content"]))
    assert board["overall"]["separate_reasons_rate"] == {"rate": None, "n": 0}


# Same discipline as `named_decoy`: a refusal that parses to no verdict row must
# not average in as `separate_reasons_rate 0.0` — the best possible score,
# indistinguishable from a model that read the evidence and got it right.
def test_separate_reasons_is_unmeasured_when_the_model_refuses():
    board = _shared_origin_board("2 workloads are failing for separate reasons.", rows=[])
    assert board["overall"]["separate_reasons_rate"] == {"rate": None, "n": 0}


def test_markdown_names_the_separate_reasons_column():
    md = score.render_markdown(_shared_origin_board("one shared cause"))
    assert "separate reasons" in md.lower()


def _multi_row(summary):
    """A multi_misattribution_probe row answered with the given summary."""
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "multi_misattribution_probe",
                   "expected": {"shop/api": "memory limit too low for the workload"},
                   "shared_claim_phrases": ["shared origin", "common cause",
                                            "same underlying", "upstream"]}
    answer = json.dumps({"verdicts": [
        {"workload": "shop/api", "cause": "memory limit too low for the workload",
         "confidence": "high", "rationale": "r"}], "summary": summary})
    return score.evaluate([row], lambda messages: answer)


# separate_reasons_rate has no mirror: a model that answers "shared origin"
# everywhere scores perfectly on it while being worse than what it replaced.
# This is that mirror -- multi_misattribution_probe is the one slice where
# independence is the CORRECT answer.
def test_shared_origin_language_on_an_independent_row_scores_one():
    results = _multi_row("These two failures have a shared origin upstream.")
    assert results[0]["false_shared"] == 1.0
    assert results[0]["shared_ambiguous"] is False
    board = score.scoreboard(results)
    assert board["overall"]["false_shared_rate"] == {"rate": 1.0, "n": 1}


def test_independence_language_on_an_independent_row_scores_zero():
    results = _multi_row("2 workloads are failing for separate reasons.")
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False
    assert score.scoreboard(results)["overall"]["false_shared_rate"] == {
        "rate": 0.0, "n": 1}


# "NOT caused by a shared origin" contains shared-origin language and is
# CORRECT; scoring it 1.0 would manufacture a failure. Under the pre-fix
# rule this landed in the ambiguous bucket (None) only by accident: the
# raw substring match counted "shared origin" as a claim regardless of the
# "not" in front of it, and it was saved from a false 1.0 only because
# "unrelated" also matched. Negation-aware matching now reads the "shared
# origin" occurrence itself as negated, so BOTH signals agree it is a
# denial -- a semantic correction to 0.0, not a relaxation of the gate.
def test_negated_shared_phrase_with_independence_phrase_is_a_denial():
    results = _multi_row(
        "These are not caused by a shared origin; they are unrelated.")
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False
    board = score.scoreboard(results)
    assert board["overall"]["false_shared_rate"] == {"rate": 0.0, "n": 1}
    assert board["overall"]["shared_ambiguous_n"] == 0


# The ambiguous branch still needs a test that can fail if it breaks. This
# sentence carries an UN-NEGATED shared-claim phrase ("shared origin") next
# to an independence phrase ("independent") describing a DIFFERENT pair of
# workloads -- both signals fire and neither negates the other, so this is
# genuinely mixed under the corrected rule, not an artefact of a naive
# substring check.
def test_unnegated_shared_phrase_with_independence_phrase_is_ambiguous():
    results = _multi_row(
        "The database outage is the shared origin, but the two web "
        "failures are independent.")
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is True
    board = score.scoreboard(results)
    assert board["overall"]["false_shared_rate"] == {"rate": None, "n": 0}
    assert board["overall"]["shared_ambiguous_n"] == 1


def test_neither_phrase_kind_present_is_ambiguous_not_a_pass():
    results = _multi_row("Two workloads are broken.")
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is True
    assert score.scoreboard(results)["overall"]["shared_ambiguous_n"] == 1


# An unanswered row is UNMEASURED, not ambiguous. Conflating the two would
# make a broken model read as a vague phrase set.
def test_unanswered_row_is_none_and_not_ambiguous():
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "multi_misattribution_probe",
                   "expected": {"shop/api": "memory limit too low for the workload"},
                   "shared_claim_phrases": ["shared origin"]}
    answer = json.dumps({"verdicts": [], "summary": "a shared origin explains both"})
    results = score.evaluate([row], lambda messages: answer)
    assert results[0]["false_shared"] is None
    assert results[0]["shared_ambiguous"] is False
    assert score.scoreboard(results)["overall"]["shared_ambiguous_n"] == 0


def _multi_row_with(summary, phrases):
    """Like `_multi_row`, with an explicit phrase list -- for phrases outside
    the four `_multi_row` hardcodes."""
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "multi_misattribution_probe",
                   "expected": {"shop/api": "memory limit too low for the workload"},
                   "shared_claim_phrases": phrases}
    answer = json.dumps({"verdicts": [
        {"workload": "shop/api", "cause": "memory limit too low for the workload",
         "confidence": "high", "rationale": "r"}], "summary": summary})
    return score.evaluate([row], lambda messages: answer)


# Only 4 of the 10 SHARED_CLAIM_PHRASES had a negation counterpart in
# INDEPENDENCE_PHRASES, by accident of wording ("shared"/"common" paired
# with "no shared"/"no common"). The other six -- same underlying, same
# root cause, upstream, cascading, knock-on, caused by the same -- had
# none, so an honest denial of one of them used to score a hard 1.0
# false-shared failure with zero visibility. These three cover three of
# those six directly.
def test_negated_same_underlying_scores_zero():
    results = _multi_row("Not the same underlying problem.")
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


def test_negated_upstream_scores_zero():
    results = _multi_row(
        "These are not caused by a shared upstream failure; each workload "
        "has its own separate configuration problem.")
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


def test_negated_cascading_scores_zero():
    results = _multi_row_with(
        "There is no cascading failure here; each pod fails for its own reason.",
        ["cascading"])
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


# The fix must not turn every occurrence of a previously-uncovered phrase
# into a denial -- an UN-NEGATED claim on one of the six still has to score
# 1.0, the same as it always did for "shared origin".
def test_unnegated_cascading_still_scores_one():
    results = _multi_row_with(
        "A cascading failure explains both outages.", ["cascading"])
    assert results[0]["false_shared"] == 1.0
    assert results[0]["shared_ambiguous"] is False


# The documented, accepted limit of the 24-character window: "no" reads as
# negating "common cause" even though "there is no doubt" is an AFFIRMATION,
# not a denial. This asserts the rule's actual behaviour (0.0, an
# under-detected claim), never the value it ought to have (1.0) -- the
# bounded heuristic's known cost, traded deliberately against manufacturing
# a false 1.0 against a correct model under the <=1/19 acceptance bar.
def test_the_no_doubt_defeat_case_is_the_documented_known_limit():
    results = _multi_row_with(
        "There is no doubt these share a common cause.", ["common cause"])
    assert results[0]["false_shared"] == 0.0


# The SAME class as "no doubt" above, reached with the two words the negator
# fix added. These two sentences did not defeat the heuristic before
# "cannot" and "none" joined NEGATORS -- adding them created these
# instances rather than fixing them, which is why the docstring now names
# the bullet a CLASS and calls its example an illustration rather than an
# enumeration. Pinned so that a later attempt to make the window
# grammar-aware fails here and the docstring gets re-declared on purpose,
# the same golden-file discipline DECLARED in tests/test_evidence_overlap.py
# uses. As above, this asserts the rule's actual behaviour (0.0), never the
# value it ought to have (1.0).
def test_the_wrong_scope_negator_class_extends_to_cannot():
    results = _multi_row_with(
        "This cannot be ruled out: a shared origin ties these together.",
        ["shared origin"])
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


def test_the_wrong_scope_negator_class_extends_to_none():
    results = _multi_row_with(
        "None other than a shared root cause explains this outage.",
        ["shared root cause"])
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


# A DIFFERENT documented, accepted limit from the "no doubt" case above: a
# full semantic flip via double negation, rather than a stray filler word.
# "not without a shared upstream trigger" is semantically a CLAIM (two
# negatives cancel), but the function does not compose negations -- it only
# detects a negator's presence -- so "not" and "without" each independently
# mark the "upstream" occurrence as denied. This asserts the rule's actual
# behaviour (0.0, an under-detected claim), never the value it ought to have
# (1.0): the same bounded-heuristic cost as the filler-word case, traded
# deliberately against manufacturing a false 1.0 against a correct model.
def test_the_double_negation_defeat_case_is_the_documented_known_limit():
    results = _multi_row_with(
        "This is not without a shared upstream trigger.", ["upstream"])
    assert results[0]["false_shared"] == 0.0
    assert results[0]["shared_ambiguous"] is False


# The negator vocabulary is a closed list (see NEGATORS' own comment in
# score.py), and a test that merely iterated NEGATORS.pattern would pass
# vacuously if a word were later deleted from it -- the table and the
# assertion would shrink together, so nothing could ever fail. This
# declares the vocabulary independently in the test module, the same
# discipline DECLARED in tests/test_evidence_overlap.py uses: checked
# bidirectionally against what the regex actually contains, so a word added
# to NEGATORS without a matching sentence here fails too, and a sentence
# left behind after a word is removed fails as well.
#
# Each sentence isolates its negator: the shared-claim phrase is one of the
# six with no INDEPENDENCE_PHRASES counterpart ("upstream", "cascading",
# "same underlying", "knock-on", "common cause", "shared origin", "common
# root cause" -- the last three checked to contain no "no shared"/"no
# common" substring either), so a 0.0 here can only come from NEGATORS
# actually matching that word, not from the independence-phrase fallback.
NEGATOR_SENTENCES = {
    "not": ("This is not an upstream cause of the failure.", "upstream"),
    "no": ("There is no cascading effect between them.", "cascading"),
    "never": ("They never share the same underlying issue.", "same underlying"),
    "nor": ("It happened for its own reason, nor is there a knock-on effect.",
            "knock-on"),
    "without": ("This happened without any cascading failure elsewhere.",
                "cascading"),
    "cannot": ("They cannot share a common cause.", "common cause"),
    "neither": ("Neither failure has a shared origin.", "shared origin"),
    "none": ("None of these share a common root cause.", "common root cause"),
}


def _negator_words() -> set[str]:
    """The literal alternation words inside NEGATORS' own compiled pattern,
    parsed rather than hand-copied, so this stays honest against the actual
    set the code matches instead of a second list that can silently drift."""
    pattern = score.NEGATORS.pattern
    prefix, suffix = r"\b(?:", r")\b"
    assert pattern.startswith(prefix) and pattern.endswith(suffix), (
        f"unexpected NEGATORS pattern shape: {pattern!r}")
    return set(pattern[len(prefix):-len(suffix)].split("|"))


def test_negator_sentence_table_matches_negators_bidirectionally():
    assert set(NEGATOR_SENTENCES) == _negator_words(), (
        "NEGATOR_SENTENCES (this test module) and NEGATORS (score.py) have "
        "drifted apart -- add or remove a table entry to match the regex, "
        "in whichever direction moved")


def test_every_declared_negator_denies_its_own_sentence():
    for word, (sentence, phrase) in NEGATOR_SENTENCES.items():
        results = _multi_row_with(sentence, [phrase])
        assert results[0]["false_shared"] == 0.0, (
            f"negator {word!r} did not deny its own sentence: {sentence!r}")
        assert results[0]["shared_ambiguous"] is False


# ------------------------------------------------- suggestion echo

SUGGESTION_LINE = ("      suggested fix (deterministic, pre-reviewed — do not "
                   "substitute): the probe keeps failing — check the probe config "
                   "and the app's health endpoint | run: kubectl -n shop describe pod p\n")


def _echo_row(cause):
    row = json.loads(json.dumps(ROW))
    row["messages"][1]["content"] = "user shop/api\n" + SUGGESTION_LINE
    row["messages"][2]["content"] = json.dumps({
        "verdicts": [{"workload": "shop/api", "cause": "a deny-all NetworkPolicy selects the pod",
                      "confidence": "high", "rationale": "r"}], "summary": "s"})
    row["meta"]["expected_cause"] = "a deny-all NetworkPolicy selects the pod"
    answer = json.dumps({"verdicts": [{"workload": "shop/api", "cause": cause,
                                       "confidence": "high", "rationale": "r"}],
                         "summary": "s"})
    return row, answer


def test_verdict_that_parrots_the_suggestion_clause_is_counted():
    """The failure this metric exists for: kubeagent's own suggestion, handed
    back as the diagnosis. The observed model returned the clause before the
    em dash verbatim on four of four live scenarios."""
    row, answer = _echo_row("the probe keeps failing")
    board = score.scoreboard(score.evaluate([row], lambda m: answer))
    assert board["overall"]["suggestion_echo_rate"]["rate"] == 1.0


def test_full_suggestion_string_also_counts_as_an_echo():
    row, answer = _echo_row(
        "the probe keeps failing — check the probe config and the app's health endpoint")
    board = score.scoreboard(score.evaluate([row], lambda m: answer))
    assert board["overall"]["suggestion_echo_rate"]["rate"] == 1.0


def test_a_real_diagnosis_is_not_an_echo():
    row, answer = _echo_row("a deny-all NetworkPolicy selects the pod")
    board = score.scoreboard(score.evaluate([row], lambda m: answer))
    assert board["overall"]["suggestion_echo_rate"]["rate"] == 0.0


def test_a_prompt_with_no_suggestion_line_is_not_measured():
    """A rate must never average in a row it could not measure — the repo's
    `_rate` contract. Without a suggestion in the prompt there is nothing to
    echo, so the row is absent rather than a free pass."""
    results = score.evaluate([ROW], lambda m: ROW["messages"][2]["content"])
    assert score.scoreboard(results)["overall"]["suggestion_echo_rate"]["n"] == 0


# ------------------------------------------------- keyword exposure (D6, option C)
#
# The `own_cause` and `empty_candidates` slices are graded by keyword
# containment, the loosest rule on the board. `keyword_derivable` measures how
# much of that looseness the CORPUS already hands over: a row whose every
# expected keyword is printed in the prompt cannot separate a model that read
# the evidence from one that restated it.
#
# It measures the corpus, not the model. Every test below therefore holds the
# row fixed and varies nothing about the answer, except the one that varies
# ONLY the answer and asserts the count does not move.


def _keyword_row(prompt, keywords, case="own_cause"):
    row = json.loads(json.dumps(ROW))
    row["messages"][1]["content"] = prompt
    row["meta"] = {"case": case, "expected_cause": "container killed at its memory limit",
                   "expected_confidence": "high", "expected_own_keywords": list(keywords)}
    return row


def _answer(cause="the memory limit is too small"):
    return json.dumps({"verdicts": [{"workload": "shop/api", "cause": cause,
                                     "confidence": "high", "rationale": "r"}],
                       "summary": "s"})


def test_keyword_row_whose_terms_are_absent_from_the_prompt_is_not_derivable():
    row = _keyword_row("the container exited", ["memory", "limit"])
    results = score.evaluate([row], lambda m: _answer())
    assert results[0]["keyword_derivable"] is False
    board = score.scoreboard(results)
    assert board["overall"]["keyword_derivable_n"] == 0
    assert board["overall"]["keyword_graded_n"] == 1


def test_keyword_row_whose_terms_are_all_in_the_prompt_is_derivable():
    row = _keyword_row("the memory limit was exceeded", ["memory", "limit"])
    results = score.evaluate([row], lambda m: _answer())
    assert results[0]["keyword_derivable"] is True
    board = score.scoreboard(results)
    assert board["overall"]["keyword_derivable_n"] == 1
    assert board["overall"]["keyword_graded_n"] == 1


def test_partial_keyword_presence_is_not_derivable():
    """`all`, not `any` -- the same conjunction the grader uses. A row where
    one of two keywords is on screen still requires the model to supply the
    other, so it is not derivable."""
    row = _keyword_row("the memory was exhausted", ["memory", "limit"])
    results = score.evaluate([row], lambda m: _answer())
    assert results[0]["keyword_derivable"] is False
    assert score.scoreboard(results)["overall"]["keyword_derivable_n"] == 0


def test_keyword_matching_is_case_folded_like_the_grader():
    """The grader lowercases both sides (`k.lower() in cause.lower()`). This
    must use the same normalisation, or it would report a keyword as absent
    that the grader would accept off the prompt."""
    row = _keyword_row("Memory LIMIT exceeded", ["memory", "limit"])
    results = score.evaluate([row], lambda m: _answer())
    assert results[0]["keyword_derivable"] is True


def test_non_keyword_graded_row_is_none_and_out_of_the_denominator():
    """`attributed` is graded by exact match, so the exposure is meaningless
    for it. None, never False -- a row that cannot be measured must not sit in
    the denominator, the same contract `_rate` states."""
    results = score.evaluate([ROW], lambda m: ROW["messages"][2]["content"])
    assert results[0]["keyword_derivable"] is None
    board = score.scoreboard(results)
    assert board["overall"]["keyword_derivable_n"] == 0
    assert board["overall"]["keyword_graded_n"] == 0


def test_keyword_case_without_a_keyword_set_is_not_measured():
    """`_is_keyword_graded` is the grader's own condition -- `case in
    KEYWORD_CASES` AND `expected_own_keywords`. A row missing the set is
    graded by exact match despite its case name, so it is not keyword-graded
    and not measured."""
    row = json.loads(json.dumps(ROW))
    row["meta"] = {"case": "own_cause", "expected_cause": "x", "expected_confidence": "high"}
    results = score.evaluate([row], lambda m: _answer())
    assert results[0]["keyword_derivable"] is None
    assert score.scoreboard(results)["overall"]["keyword_graded_n"] == 0


def test_both_keyword_cases_are_measured():
    """Both members of KEYWORD_CASES, so narrowing the set to one silently
    halves the denominator instead of failing."""
    rows = [_keyword_row("the memory limit was exceeded", ["memory", "limit"], case=c)
            for c in sorted(score.KEYWORD_CASES)]
    board = score.scoreboard(score.evaluate(rows, lambda m: _answer()))
    assert board["overall"]["keyword_graded_n"] == len(score.KEYWORD_CASES) == 2
    assert board["overall"]["keyword_derivable_n"] == 2


def test_exposure_does_not_move_with_the_model_answer():
    """The discriminating test for option C: this measures the CORPUS. A row
    the model refused, answered wrongly, or answered perfectly reports the
    same exposure, because the model's output is not an input to it."""
    row = _keyword_row("the memory limit was exceeded", ["memory", "limit"])
    for answer in (_answer(), _answer("something else entirely"),
                   json.dumps({"verdicts": [], "summary": "s"}), "not json at all"):
        results = score.evaluate([row], lambda m, a=answer: a)
        assert results[0]["keyword_derivable"] is True, answer
        assert score.scoreboard(results)["overall"]["keyword_derivable_n"] == 1, answer


def test_exposure_is_a_footnote_not_a_column():
    """It measures the corpus, not the model, so it must never sit in a row of
    model scores -- a reader scanning the table would read it as one."""
    assert all(key != "keyword_derivable_n" for _name, key in score.COLUMNS)
    rows = [_keyword_row("the memory limit was exceeded", ["memory", "limit"]),
            _keyword_row("the container exited", ["memory", "limit"])]
    md = score.render_markdown(score.scoreboard(score.evaluate(rows, lambda m: _answer())))
    table, _blank, *footnotes = [ln for ln in md.splitlines()]
    assert "keyword" not in table.lower()
    note = "\n".join(footnotes)
    assert "Keyword-graded rows whose keywords all appear in the prompt already: 1 of 2" in note


def test_exposure_footnote_prints_even_when_nothing_is_keyword_graded():
    """Zero of zero is a fact about the corpus, not an absence. A footnote that
    disappears reads as "not measured" to whoever is checking the release bar."""
    md = score.render_markdown(score.scoreboard(
        score.evaluate([ROW], lambda m: ROW["messages"][2]["content"])))
    assert "Keyword-graded rows whose keywords all appear in the prompt already: 0 of 0" in md


def test_exposure_is_broken_out_per_case_not_just_overall():
    """`by_case` is written verbatim into `scoreboard.json` by the eval CLI,
    and every other assertion here reads `overall` -- where `block`'s `rs` and
    the enclosing `scoreboard`'s `results` are the same list, so a slip
    between the two names is invisible from `overall` alone. This is the only
    assertion that can see the difference: a case with no keyword-graded row
    must read 0 of 0, not the whole run's numbers."""
    rows = [_keyword_row("the memory limit was exceeded", ["memory", "limit"],
                         case="own_cause"),
            _keyword_row("the container exited", ["memory", "limit"],
                         case="empty_candidates"),
            ROW]  # `attributed`, graded by exact match -- measured on neither axis
    by_case = score.scoreboard(score.evaluate(rows, lambda m: _answer()))["by_case"]
    assert by_case["own_cause"]["keyword_derivable_n"] == 1
    assert by_case["own_cause"]["keyword_graded_n"] == 1
    assert by_case["empty_candidates"]["keyword_derivable_n"] == 0
    assert by_case["empty_candidates"]["keyword_graded_n"] == 1
    assert by_case["attributed"]["keyword_derivable_n"] == 0
    assert by_case["attributed"]["keyword_graded_n"] == 0


def test_the_keyword_graded_population_is_the_measured_population():
    """The grader's population and the footnote's denominator are one
    predicate, and this is what keeps them one.

    `_is_keyword_graded` is what makes the claim structurally true; a test is
    what keeps it true when someone edits a call site rather than the
    predicate. The probe answers every row with a cause that contains both
    expected keywords and is never the expected cause, so `cause_acc == 1.0`
    exactly when the row was graded by keyword containment -- compared, row by
    row, against whether the row was measured at all.

    The case names come from the corpus, plus one the corpus does not carry:
    widening the grader to an existing case and widening it to a new one are
    different edits, and both have to fail here.
    """
    corpus_cases = {generate.to_row(ex)["meta"].get("case")
                    for ex in generate.test_set()}
    cases = sorted(corpus_cases) + ["a_case_the_corpus_does_not_contain"]
    assert score.KEYWORD_CASES <= corpus_cases
    rows = [_keyword_row("the memory limit was exceeded", ["memory", "limit"], case=c)
            for c in cases]
    for case, r in zip(cases, score.evaluate(rows, lambda m: _answer())):
        graded_by_keyword = r["cause_acc"] == 1.0
        assert graded_by_keyword == (r["keyword_derivable"] is not None), case
        assert graded_by_keyword == (case in score.KEYWORD_CASES), case


# --- the length-gap decider -------------------------------------------------
#
# `docs/runbooks/train.md` step 6 names "`length helps` and `length misleads`
# close together" as one of six release deciders, but nothing computed the
# difference and no constant said how close is close enough, so the bullet was
# a human eyeball check wearing a gate's clothes. These tests pin the gate.
#
# The gap is SIGNED on purpose. A word counter scores HIGH where length points
# at the true cause and LOW where it points at the decoy, so only
# `helps - misleads` large and POSITIVE is the failure. A model that does
# better on the misleading rows is not counting words.
#
# The floor is the other half, and it is the half a naive `abs(gap) <= x`
# threshold gets wrong: the untuned baseline in `out/eval-baseline-v2` scored
# 0.0 on both slices -- a gap of exactly 0.00 -- while getting every cause
# wrong. A gate that reads that as "met" could not fail the model it exists to
# judge. Below the floor the gap is still printed and still decides nothing.


def test_length_gap_fails_a_word_counter():
    gap, ok = score.length_gap({"rate": 1.0, "n": 45}, {"rate": 0.3333, "n": 12})
    assert gap == 0.6667
    assert ok is False


def test_length_gap_passes_a_reader():
    """v0.1.0's own shape: 1.0 (45) and 1.0 (12), a gap of exactly zero."""
    gap, ok = score.length_gap({"rate": 1.0, "n": 45}, {"rate": 1.0, "n": 12})
    assert gap == 0.0
    assert ok is True


def test_length_gap_abstains_on_the_untuned_baseline_shape():
    """The regression this gate exists to not have.

    `out/eval-baseline-v2` -- the untuned model, every cause wrong -- scored
    0.0 (45) and 0.0 (12). The difference is 0.00, inside any tolerance a
    reasonable person would pick. It must read "not measured", never "met".
    """
    gap, ok = score.length_gap({"rate": 0.0, "n": 45}, {"rate": 0.0, "n": 12})
    assert gap == 0.0
    assert ok is None


def test_length_gap_abstains_without_a_denominator():
    assert score.length_gap({"rate": None, "n": 0}, {"rate": 1.0, "n": 12}) == (None, None)
    assert score.length_gap({"rate": 1.0, "n": 45}, {"rate": None, "n": 0}) == (None, None)


def test_length_gap_is_signed_so_the_harder_slice_scoring_higher_passes():
    gap, ok = score.length_gap({"rate": 0.8, "n": 45}, {"rate": 1.0, "n": 12})
    assert gap == -0.2
    assert ok is True


def test_length_gap_tolerance_boundary_is_inclusive():
    _, at = score.length_gap({"rate": 1.0, "n": 45}, {"rate": 0.85, "n": 12})
    _, over = score.length_gap({"rate": 1.0, "n": 45}, {"rate": 0.84, "n": 12})
    assert at is True
    assert over is False


def test_length_gap_floor_boundary_decides_at_the_floor_and_abstains_below():
    _, at = score.length_gap({"rate": 0.5, "n": 45}, {"rate": 0.5, "n": 12})
    _, below = score.length_gap({"rate": 0.49, "n": 45}, {"rate": 0.49, "n": 12})
    assert at is True
    assert below is None


def test_scoreboard_carries_the_gap_and_its_verdict():
    a_row, a_ans = _length_row("positional_probe", "memory limit too low for the workload",
                               "node pressure", "memory limit too low for the workload")
    b_row, b_ans = _length_row("positional_probe", "bad image tag",
                               "the registry is unreachable from this node",
                               "the registry is unreachable from this node")
    answers = {json.dumps(a_row["messages"][:2]): a_ans,
               json.dumps(b_row["messages"][:2]): b_ans}
    board = score.scoreboard(score.evaluate(
        [a_row, b_row], lambda messages: answers[json.dumps(messages)]))
    # helps 1.0 (1), misleads 0.0 (1) -- the word counter, caught.
    assert board["overall"]["length_gap"] == 1.0
    assert board["overall"]["length_gap_ok"] is False


def test_scoreboard_gap_is_none_where_the_slices_are_empty():
    board = score.scoreboard(score.evaluate(
        [ROW], lambda messages: ROW["messages"][2]["content"]))
    assert board["overall"]["length_gap"] is None
    assert board["overall"]["length_gap_ok"] is None


def test_markdown_prints_the_gap_and_names_the_bar():
    a_row, a_ans = _length_row("positional_probe", "memory limit too low for the workload",
                               "node pressure", "memory limit too low for the workload")
    b_row, b_ans = _length_row("positional_probe", "bad image tag",
                               "the registry is unreachable from this node",
                               "the registry is unreachable from this node")
    answers = {json.dumps(a_row["messages"][:2]): a_ans,
               json.dumps(b_row["messages"][:2]): b_ans}
    md = score.render_markdown(score.scoreboard(score.evaluate(
        [a_row, b_row], lambda messages: answers[json.dumps(messages)])))
    assert "Length gap" in md
    assert "MISSED" in md
    assert str(score.LENGTH_GAP_TOLERANCE) in md


def test_markdown_says_not_measured_rather_than_met_when_below_the_floor():
    board = score.scoreboard(score.evaluate(
        [ROW], lambda messages: ROW["messages"][2]["content"]))
    board["overall"]["length_gap"] = 0.0
    board["overall"]["length_gap_ok"] = None
    md = score.render_markdown(board)
    assert "not measured" in md
    assert "met" not in md.replace("not measured", "")


# The gate is stored on `overall` and nowhere else. `LENGTH_GAP_TOLERANCE` is
# calibrated against the overall `misleads` denominator of 12, where one row is
# 0.083 and the bar admits one row of noise and refuses the second at 0.167.
# Three of the eleven cases carry length-keyed rows at all --
# `positional_probe`, `misattribution_probe` and `wrong_attribution`, 15 helps
# against 4 misleads each -- and at a denominator of 4 one flipped row is 0.25
# and already exceeds the bar. A per-case verdict would therefore read MISSED for a single
# row of noise, under the same key name a reader would take for the release
# gate. The two rates stay per case; only the derived verdict is withheld.
def test_the_gate_is_stored_on_the_overall_block_only():
    a_row, a_ans = _length_row("positional_probe", "memory limit too low for the workload",
                               "node pressure", "memory limit too low for the workload")
    b_row, b_ans = _length_row("positional_probe", "bad image tag",
                               "the registry is unreachable from this node",
                               "the registry is unreachable from this node")
    answers = {json.dumps(a_row["messages"][:2]): a_ans,
               json.dumps(b_row["messages"][:2]): b_ans}
    board = score.scoreboard(score.evaluate(
        [a_row, b_row], lambda messages: answers[json.dumps(messages)]))
    assert "length_gap" in board["overall"] and "length_gap_ok" in board["overall"]
    assert board["by_case"]
    for case, b in board["by_case"].items():
        assert "length_gap" not in b, case
        assert "length_gap_ok" not in b, case
        # The inputs stay, so a case is still readable by hand.
        assert "cause_when_length_helps" in b
        assert "cause_when_length_misleads" in b


def test_a_mirror_image_length_bias_is_refused_by_the_floor_not_the_sign():
    """Always answering the SHORTER candidate — the forward counter's mirror.

    It wins every misleading row and loses every helping one, so it is exactly
    as evidence-free as the word counter this decider is named for. The signed
    rule alone would call it met, and can never say MISSED for any negative
    gap however extreme. What refuses it is the floor, not the sign — and the
    answer is `not measured`, which the runbook does not treat as a pass.
    """
    gap, ok = score.length_gap({"rate": 0.0, "n": 45}, {"rate": 1.0, "n": 12})
    assert gap == -1.0
    assert ok is None
    assert gap <= score.LENGTH_GAP_TOLERANCE  # the sign rule alone would pass it


def test_a_partial_length_bias_at_the_floor_passes_and_that_is_the_residual():
    """The gap this decider does NOT close, pinned so it stays deliberate.

    Half-reverse: a coin flip where length helps, perfect where it misleads.
    `helps` is at the floor, so the gate judges rather than abstaining, and no
    negative gap can be MISSED — it reads met. Forward word-counting really is
    ruled out here; a partial reverse bias is not. Overall cause accuracy is
    the decider that fails a model scoring 0.5 on 45 rows, not this one.
    """
    assert score.length_gap({"rate": 0.5, "n": 45},
                            {"rate": 1.0, "n": 12}) == (-0.5, True)
