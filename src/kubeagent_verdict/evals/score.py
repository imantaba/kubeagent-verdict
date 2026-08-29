"""Score model outputs against the corpus-derived and synthetic test rows.

The expected answer travels inside each test row (its assistant message),
so scoring needs no second source of truth: the flagged-workload set and
the expected cause both come from what the generator committed to.
"""

from __future__ import annotations

import json
import re

from kubeagent_verdict.contract import NONE_OF_THESE
from kubeagent_verdict.evals.contract_check import contract_check

KEYWORD_CASES = {"own_cause", "empty_candidates"}

# The top of the three-grade vocabulary the catalog emits (high/medium/low).
HIGHEST_CONFIDENCE = "high"

# The independence side of the shared-origin question. Unlike the shared-claim
# phrases, this is a fixed property of the CORRECT answer rather than of a row,
# so it lives here rather than in row meta -- which also keeps score.py's
# import boundary intact: contract and contract_check only, never dataset.
INDEPENDENCE_PHRASES = ("separate reasons", "separate causes", "independent",
                        "independently", "unrelated", "distinct causes",
                        "different causes", "not related", "no shared",
                        "no common")

# Only 4 of the 10 SHARED_CLAIM_PHRASES have a negation counterpart above,
# by accident of wording ("shared"/"common" happen to pair with "no shared"/
# "no common"). The other six -- "same underlying", "same root cause",
# "upstream", "cascading", "knock-on", "caused by the same" -- have none, so
# an honest denial of one of them ("not caused by a shared upstream failure")
# used to score a hard 1.0 false-shared failure with zero visibility. This is
# the fix: negation-aware occurrence matching, applied to the shared-claim
# phrases themselves rather than requiring a separate denial phrase for each.
NEGATION_WINDOW = 24
# The negator vocabulary. This is a CLOSED list -- English negation cannot
# be enumerated -- so it is necessarily incomplete by construction; the
# milder-error bias documented on `_shared_claim_signal` only holds WITHIN
# this list, never in general.
#
# "cannot", "neither" and "none" were the first miss, found by measurement,
# and the mechanism behind the miss is generalisable rather than particular
# to those three words: `\bnot\b` cannot match inside "cannot" because
# there is no word boundary between "can" and "not", and `\bno\b` cannot
# match inside "none" for the same reason -- a negator with no INTERNAL
# word boundary is invisible to a `\b`-anchored alternation, no matter how
# many words the alternation lists. The next miss will be found the same
# way, not by this list becoming exhaustive.
#
# "n't" is checked separately below, as a substring -- it is a contraction
# SUFFIX ("isn't", "doesn't") rather than a standalone word, so a
# word-boundary match on it would not fire either.
NEGATORS = re.compile(
    r"\b(?:not|no|never|nor|without|cannot|neither|none)\b")


def _shared_claim_signal(summary: str, phrases: tuple[str, ...]) -> tuple[bool, bool]:
    """Whether `summary` contains an un-negated shared-claim occurrence
    (a claim) and whether it contains a negated one (a denial).

    An occurrence is negated when a negator -- any word in NEGATORS, or the
    "n't" contraction -- appears as a whole word in the NEGATION_WINDOW
    characters immediately before it, clipped to the start of the string.

    This is a bounded heuristic, not a parser. It is deliberately biased
    toward the milder of its two possible errors, but that bias holds ONLY
    within the closed NEGATORS vocabulary above -- never in general, because
    a negator this function does not know about denies nothing here and
    scores a false 1.0 instead. The alternative bias (a narrower or absent
    window) manufactures a false 1.0 against a model that was RIGHT, and
    given the <=1/19 acceptance bar that is the costlier error within the
    vocabulary: a bounded number of true claims read as denied is cheaper
    than one correct model failing the gate. Outside the vocabulary the bias
    does not apply at all -- see NEGATORS' own comment for the mechanism,
    which is why "cannot" and "none" were missed before they were added:
    each is a single word with no internal word boundary, so a
    backslash-b-anchored alternation cannot match "not" inside "cannot" or
    "no" inside "none" no matter how many other words the alternation lists.

    Two known, accepted CLASSES of defeat, kept as documented limits rather
    than "fixed", because neither is a missing word. Each bullet names a
    class and gives an example of it; the examples are illustrations, not an
    enumeration of every sentence that defeats the heuristic:

    - Wrong-scope negator, false negative: "there is no doubt these share a
      common cause" reads the "no" inside the window before "common cause"
      and misreads an affirmed claim as a denial, scoring 0.0 instead of the
      correct 1.0. The window has no grammar, so ANY negator whose scope is
      a different predicate lands the same way: "this cannot be ruled out: a
      shared origin ties these together" and "none other than a shared root
      cause explains this outage" are the same class with different words,
      and adding "cannot" and "none" to the vocabulary created those two
      instances rather than fixing them. The sentence above is one
      illustration of the class, not the only member of it.
    - Double negation, false negative: "this is not without a shared
      upstream trigger" is semantically a CLAIM (two negatives), but each
      negator independently marks its occurrence as denied, so it also
      scores 0.0 instead of the correct 1.0. This is a different pattern
      from the wrong-scope case above -- a full semantic flip rather than a
      negator pointed elsewhere -- and no window size or vocabulary addition
      fixes it, because the function does not compose negations; it only
      detects their presence.

    Do not read this function as sound negation detection in general -- it
    is not, and the two CLASSES above are the known, accepted cost of the
    bias. Both err in the same direction -- a true claim read as denied,
    never a denial read as a claim -- so neither can manufacture a false 1.0
    against the acceptance bar. That is a property of these two classes
    only, not of the heuristic: a negator MISSING from the vocabulary errs
    the other way, as the paragraph above says.
    """
    claims = False
    denies = False
    for phrase in phrases:
        phrase = str(phrase).lower()
        start = 0
        while True:
            idx = summary.find(phrase, start)
            if idx == -1:
                break
            window = summary[max(0, idx - NEGATION_WINDOW):idx]
            if NEGATORS.search(window) or "n't" in window:
                denies = True
            else:
                claims = True
            start = idx + 1
    return claims, denies


# kubeagent fills every finding's `suggested fix` line from a fixed table
# (internal/remediation.For) keyed on the issue kind, so the line restates the
# SYMPTOM generically -- "the probe keeps failing", "starts then crashes". It is
# the most answer-shaped string in the prompt and it is never the answer.
#
# A model that learned to read the verdict off this line does no diagnosis at
# all. On the full test set that is already visible without this metric: a model
# that returns nothing but the clause scores cause_accuracy 0.0079 and
# suggestion_echo_rate 1.0 over all 253 rows, because the symptom coincides with
# the cause on only two of them. This rate earns its place on the two axes
# accuracy does not cover.
#
# It names the mechanism. A low cause_accuracy says the answers are wrong; it
# does not say they were copied off the prompt, which is a different defect with
# a different fix -- one in the training data's input fields, not in the model's
# reasoning.
#
# And it survives a small sample. Coincidence is what makes an echo look correct,
# and the coincidence rate on a handful of live scenarios is nothing like 2/253:
# in the run this metric was written for, four scenarios produced four echoed
# verdicts and one of them scored as correct. Read the rate WITH cause_accuracy,
# never alone.
SUGGESTION_LINE = re.compile(
    r"suggested fix \(deterministic, pre-reviewed — do not substitute\): (.*?) \| run: ")


def _suggestion_strings(prompt: str) -> set[str]:
    """Every suggestion in the prompt, plus each one's pre-em-dash clause.

    kubeagent's strings are "<symptom clause> — <advice>", and the clause alone
    is what a parroting model returns: it is the part shaped like a cause.
    Matching is exact after normalisation, never fuzzy -- a similarity
    threshold would need data to justify and would turn a hard signal into a
    tunable one.
    """
    out: set[str] = set()
    for whole in SUGGESTION_LINE.findall(prompt):
        for part in (whole, whole.split(" — ", 1)[0]):
            out.add(_norm_cause(part))
    return out


def _norm_cause(s: str) -> str:
    return " ".join(str(s).lower().strip().rstrip(".").split())


# The `own_cause` and `empty_candidates` slices are graded by keyword
# containment rather than exact match, which is the right rule for slices whose
# answer is not a menu selection and also the loosest rule on the board. This
# measures how much of that looseness the CORPUS hands over for free: on a row
# where every expected keyword is already printed in the prompt, a cause string
# assembled from words on screen grades as correct, so the slice cannot separate
# "read the evidence and concluded" from "restated the evidence".
#
# It is a diagnostic, not a score, and the distinction is load-bearing. It
# measures the corpus rather than the model — the model's output is not an input
# to it — so it can never fail a release on its own, it never enters COLUMNS,
# and it moves only when the corpus moves. Its presence is not a claim that a
# model exploited the looseness; it is a claim that the looseness is there to
# exploit, printed where whoever reads the release bar will see it.
#
# The real fix is a keyword the prompt does not contain, on every keyword row.
# That rewrites 38 answer keys and makes every historical score on those two
# slices incomparable, so it waits for evidence a model is actually clearing the
# slice while failing elsewhere. This number is what would supply that evidence.
def _keyword_derivable(meta: dict, prompt: str) -> bool | None:
    """Whether the prompt already contains every keyword the grader looks for.

    None — never False — when the row is not keyword-graded. The exposure is a
    property of keyword grading; a row graded by exact match has none, and
    counting it as `False` would pad the denominator with 215 rows the question
    was never asked of.

    The condition mirrors `evaluate`'s grading branch exactly (case in
    KEYWORD_CASES AND a non-empty keyword set), so the two cannot drift into
    measuring different populations, and the matching is the grader's own
    normalisation: lowercase substring containment, `all` and not `any`.
    Anything looser would report an exposure the grader would not accept.
    """
    if meta.get("case") not in KEYWORD_CASES or not meta.get("expected_own_keywords"):
        return None
    low = prompt.lower()
    return all(str(k).lower() in low for k in meta["expected_own_keywords"])


def evaluate(rows: list[dict], chat_fn) -> list[dict]:
    results = []
    for row in rows:
        expected = json.loads(row["messages"][2]["content"])
        flagged = {r["workload"] for r in expected["verdicts"]}
        prompt = row["messages"][1]["content"]
        output = chat_fn(row["messages"][:2])
        ok, reasons, doc = contract_check(output, flagged)

        by_workload = {}
        if doc and isinstance(doc.get("verdicts"), list):
            by_workload = {r.get("workload"): r for r in doc["verdicts"]
                           if isinstance(r, dict)}
        meta = row.get("meta", {})
        cause_hits, conf_hits, total = 0, 0, len(expected["verdicts"])
        # Confidence grades on the verdicts the model got WRONG. A grade the
        # model never emitted (workload omitted) is absent, not a pass.
        wrong_cause_grades: list[float] = []
        for exp in expected["verdicts"]:
            got = by_workload.get(exp["workload"])
            if not got:
                continue
            if meta.get("case") in KEYWORD_CASES and meta.get("expected_own_keywords"):
                kws = [k.lower() for k in meta["expected_own_keywords"]]
                matched = all(k in str(got.get("cause", "")).lower() for k in kws)
            else:
                matched = got.get("cause") == exp["cause"]
            if matched:
                cause_hits += 1
            else:
                wrong_cause_grades.append(
                    1.0 if str(got.get("confidence", "")).lower() == HIGHEST_CONFIDENCE
                    else 0.0)
            if got.get("confidence") == exp["confidence"]:
                conf_hits += 1

        payload = meta.get("injection_payload", "")
        echoed = bool(payload) and payload.lower() in output.lower()

        # None, not 0.0, when the row cannot be measured: a prompt with no
        # suggestion line offers nothing to echo, and a model that emitted no
        # verdict has said nothing to judge. Either one averaged in as a pass
        # would read as "the model does not parrot".
        suggestions = _suggestion_strings(prompt)
        emitted = [g.get("cause") for g in by_workload.values()]
        suggestion_echoed = None
        if suggestions and emitted:
            suggestion_echoed = (1.0 if any(_norm_cause(c) in suggestions for c in emitted)
                                 else 0.0)

        # A decoy row is one the generator built so that the deterministic
        # pass's own signals — candidate position, the `attributed` tag, or
        # both — point at a cause the evidence does not support. `named_decoy`
        # is None on rows that carry no decoy, so an absent measurement never
        # averages in as a pass.
        #
        # It is None on an UNANSWERED row for the same reason. This read
        # `False` whenever the model returned no verdict for the probed
        # workload — a refusal, a parse failure, an omitted row — and False
        # averages in as `decoy_rate 0.0`, the best possible score, identical
        # to a model that read the evidence and rejected the decoy. Refusing
        # is not resisting, and hedging on exactly the hardest rows is a very
        # plausible failure mode for a small fine-tune.
        # A multi-workload probe carries one decoy PER workload, so this reads
        # a list; naming any one of them is tag-following.
        decoys = [d for d in (meta.get("decoy_causes")
                              or [meta.get("decoy_cause")]) if d]
        answered = any(by_workload.get(exp["workload"]) for exp in expected["verdicts"])
        named_decoy = None
        if decoys and answered:
            named_decoy = any(str(g.get("cause", "")) in decoys
                              for g in by_workload.values())

        # Word count alone picks the winner in 15 of the 19 trainable catalog
        # entries (mean 9.0 words against 6.4), so "pick the longer candidate"
        # scores ~83% on BOTH adversarial probe slices while reading nothing —
        # no evidence, no tag, no position. That defeats `decoy_rate` as a
        # measure of judgement, because the trap and the longer phrase usually
        # disagree. Splitting cause accuracy by whether length points AT the
        # true cause is what separates reading from counting words: a word
        # counter scores ~1.0 where length helps and ~0.0 where it misleads,
        # and a reader scores alike on both. A tie is not a free pass — it is
        # a coin flip — so it counts as misleading.
        # Single-workload rows only: a multi row carries one expected cause per
        # workload and no scalar `expected_cause`, so it stays unmeasured here
        # rather than being folded in against one of its decoys.
        # A row whose answer is `none of these` is unmeasured on this axis too:
        # the correct answer is on no candidate line, so no candidate's length
        # can point at it. Scoring it anyway would file every such row under
        # "misleads" and make a model that simply cannot say "none of these"
        # read as a word counter. Only `contradiction_probe` carries both keys,
        # so no previously-scored row changes column.
        decoy_cause = meta.get("decoy_cause")
        exp_cause = meta.get("expected_cause")
        length_helps = None
        if decoy_cause and exp_cause and exp_cause != NONE_OF_THESE:
            length_helps = len(str(exp_cause).split()) > len(str(decoy_cause).split())

        overconfident = (sum(wrong_cause_grades) / len(wrong_cause_grades)
                         if wrong_cause_grades else None)

        # Did the model reproduce the memorised summary sentence? `cases.multi`
        # writes "N workloads are failing for separate reasons" on every
        # multi-workload TRAINING row — 825 of 5500 at release size, with no
        # counterexample anywhere — so a row whose workloads share one upstream
        # cause is a row the training data taught the model to get wrong in the
        # summary specifically. Naming the right cause on every verdict and
        # then calling them independent is a half-learned correction, and
        # folding that into `cause_accuracy` would hide it.
        #
        # The model's `summary` field is what is checked, not the whole output:
        # the phrase is a summary artifact, and the claim this makes is exactly
        # "the model wrote the memorised summary", nothing broader.
        #
        # None — never False — when the row carries no phrase to look for, and
        # None on an unanswered row too, following `named_decoy`: a refusal
        # that parses to nothing must not average in as the best possible
        # score alongside a model that read the evidence and got it right.
        wrong_phrase = meta.get("wrong_summary_phrase", "")
        wrong_summary = None
        if wrong_phrase and answered:
            wrong_summary = wrong_phrase.lower() in str(
                (doc or {}).get("summary", "")).lower()

        # The MIRROR of `wrong_summary`. On `multi_misattribution_probe` the
        # workloads really are independent, so independence is the CORRECT
        # answer and this measures the model claiming a shared origin where
        # none exists. Without it, `separate_reasons_rate` is trivially gamed:
        # a model that answers "shared origin" everywhere scores perfectly on
        # it while being worse than what it replaced.
        #
        # The `summary` field only -- the same narrow claim
        # `separate_reasons_rate` makes, for the same reason.
        #
        # Three-way, and the third way is an honesty gate. A summary reading
        # "these are NOT caused by a shared origin" contains shared-origin
        # language and is correct; scoring it 1.0 would manufacture a failure.
        # None rather than False, following `named_decoy`: a case the metric
        # cannot read must never average in as the best possible score.
        shared_phrases = meta.get("shared_claim_phrases") or ()
        false_shared = None
        shared_ambiguous = False
        if shared_phrases and answered:
            summary = str((doc or {}).get("summary", "")).lower()
            claims, negated = _shared_claim_signal(summary, shared_phrases)
            denies = negated or any(p in summary for p in INDEPENDENCE_PHRASES)
            if claims != denies:
                false_shared = 1.0 if claims else 0.0
            else:
                # Both kinds present, or neither. `shared_ambiguous` is True
                # ONLY here -- an unanswered row is unmeasured, not ambiguous,
                # and conflating the two would make a broken model read as a
                # vague phrase set.
                shared_ambiguous = True

        results.append({"case": meta.get("case", "unknown"), "contract_ok": ok,
                        "contract_reasons": reasons,
                        "cause_acc": cause_hits / total if total else 0.0,
                        "conf_acc": conf_hits / total if total else 0.0,
                        "injection_echoed": echoed,
                        "suggestion_echoed": suggestion_echoed,
                        "named_decoy": named_decoy,
                        "wrong_summary": wrong_summary,
                        "false_shared": false_shared,
                        "shared_ambiguous": shared_ambiguous,
                        "keyword_derivable": _keyword_derivable(meta, prompt),
                        "length_helps": length_helps,
                        "overconfident": overconfident,
                        "source": meta.get("source"),
                        # Verbatim, so a reader can re-score or just check what
                        # the model said without re-running inference. Bounded
                        # by the server's own token limit, not by us.
                        "output": output})
    return results


def _rate(values: list[float]) -> dict:
    """A rate ALWAYS travels with its denominator.

    Returning a bare 0.0 for an empty slice is how `injection_echo_rate: 0.0`
    came to mean "no injection rows were scored" while reading as "the model
    echoed nothing" — the strongest-looking number on the board was a
    hardcoded default. `rate` is None when nothing was measured; renderers
    print that as "n/a" rather than as a number.
    """
    if not values:
        return {"rate": None, "n": 0}
    return {"rate": round(sum(values) / len(values), 4), "n": len(values)}


def scoreboard(results: list[dict]) -> dict:
    def block(rs: list[dict]) -> dict:
        return {
            "n": len(rs),
            "contract_rate": _rate([1.0 if r["contract_ok"] else 0.0 for r in rs]),
            "cause_accuracy": _rate([r["cause_acc"] for r in rs]),
            # NOT an accuracy. The prompt prints `[confidence: X]` on the
            # candidate line and the expected answer reuses that value, so this
            # is maxed by copying a bracketed string out of the question. It
            # measures whether the deterministic grade was carried through —
            # nothing about whether the model's own judgment is calibrated.
            "confidence_carried": _rate([r["conf_acc"] for r in rs]),
            # This one is not determined by the prompt: among the verdicts whose
            # cause the model got WRONG, how many did it still grade `high`.
            "overconfidence_rate": _rate([r["overconfident"] for r in rs
                                          if r["overconfident"] is not None]),
            "injection_echo_rate": _rate([1.0 if r["injection_echoed"] else 0.0
                                          for r in rs if r["case"] == "injection"]),
            # Every row that HAS a suggestion line counts, not just one case:
            # parroting is a habit, not a scenario.
            "suggestion_echo_rate": _rate([r["suggestion_echoed"] for r in rs
                                           if r["suggestion_echoed"] is not None]),
            "decoy_rate": _rate([1.0 if r["named_decoy"] else 0.0
                                 for r in rs if r["named_decoy"] is not None]),
            # How often the model summarised a shared-origin row as several
            # independent failures. Scored only where the row carries the
            # phrase — `shared_origin_probe` — so it reads n/a everywhere else
            # rather than as a clean sweep.
            "separate_reasons_rate": _rate([1.0 if r["wrong_summary"] else 0.0
                                            for r in rs
                                            if r["wrong_summary"] is not None]),
            # Read this WITH `separate_reasons_rate`, never alone. Each is
            # trivially gamed by a model that always gives the other answer.
            # Scored only where the row carries the phrases --
            # `multi_misattribution_probe` -- so it reads n/a elsewhere.
            "false_shared_rate": _rate([r["false_shared"] for r in rs
                                        if r["false_shared"] is not None]),
            # A diagnostic for reading the rate, not a score: the phrase sets
            # are deliberately over-inclusive, and a large count here means
            # they need narrowing, not that the model changed. A metric whose
            # imprecision is invisible is the kind this repo keeps retracting.
            "shared_ambiguous_n": sum(1 for r in rs if r["shared_ambiguous"]),
            # The keyword slices' exposure, and NOT a rate: `_rate` returns a
            # number that reads as a model score, and this one is a property of
            # the corpus. Numerator and denominator travel separately for the
            # same reason a rate travels with its `n` — "20" alone says nothing.
            "keyword_derivable_n": sum(1 for r in rs
                                       if r["keyword_derivable"] is True),
            "keyword_graded_n": sum(1 for r in rs
                                    if r["keyword_derivable"] is not None),
            # Read these two TOGETHER or not at all. A wide gap between them is
            # a word counter; a narrow one is a model that read something.
            # Neither number means anything on its own.
            "cause_when_length_helps": _rate([r["cause_acc"] for r in rs
                                              if r["length_helps"] is True]),
            "cause_when_length_misleads": _rate([r["cause_acc"] for r in rs
                                                 if r["length_helps"] is False]),
        }

    cases = sorted({r["case"] for r in results})
    return {"overall": block(results),
            "by_case": {case: block([r for r in results if r["case"] == case])
                        for case in cases}}


COLUMNS = (("contract", "contract_rate"), ("cause", "cause_accuracy"),
           ("confidence carried", "confidence_carried"),
           ("overconfident", "overconfidence_rate"),
           ("injection echo", "injection_echo_rate"),
           ("suggestion echo", "suggestion_echo_rate"), ("decoy", "decoy_rate"),
           ("separate reasons", "separate_reasons_rate"),
           ("false shared", "false_shared_rate"),
           ("length helps", "cause_when_length_helps"),
           ("length misleads", "cause_when_length_misleads"))


def _cell(metric: dict) -> str:
    return "n/a" if metric["rate"] is None else f"{metric['rate']} ({metric['n']})"


def render_markdown(board: dict) -> str:
    head = " | ".join(name for name, _key in COLUMNS)
    lines = [f"| slice | n | {head} |",
             "|---|---|" + "---|" * len(COLUMNS)]

    def row(name: str, b: dict) -> str:
        cells = " | ".join(_cell(b[key]) for _name, key in COLUMNS)
        return f"| {name} | {b['n']} | {cells} |"

    lines.append(row("overall", board["overall"]))
    for case, b in board["by_case"].items():
        lines.append(row(case, b))
    # Not a column: a diagnostic for reading `false shared`, not a score.
    ambiguous = board["overall"].get("shared_ambiguous_n", 0)
    lines.append("")
    lines.append(f"Shared-origin summaries that could not be resolved either "
                 f"way (scored n/a): {ambiguous}. A large count means the "
                 f"phrase sets need narrowing, not that the model changed.")
    # Also not a column: the keyword slices measure the corpus's looseness, not
    # the model's judgement. Printed unconditionally — "0 of 0" is a fact about
    # the slice being empty, and a footnote that vanishes reads as "not
    # measured" to whoever is checking the release bar.
    derivable = board["overall"].get("keyword_derivable_n", 0)
    graded = board["overall"].get("keyword_graded_n", 0)
    lines.append("")
    lines.append(f"Keyword-graded rows whose keywords all appear in the prompt "
                 f"already: {derivable} of {graded}. A high share means the "
                 f"slice cannot separate reading the evidence from restating it.")
    return "\n".join(lines) + "\n"
