"""Score model outputs against the corpus-derived and synthetic test rows.

The expected answer travels inside each test row (its assistant message),
so scoring needs no second source of truth: the flagged-workload set and
the expected cause both come from what the generator committed to.
"""

from __future__ import annotations

import json
import re

from kubeagent_verdict.contract import NONE_OF_THESE, TRUNCATION_MARKER
from kubeagent_verdict.evals.contract_check import contract_check

# The top of the three-grade vocabulary the catalog emits (high/medium/low).
HIGHEST_CONFIDENCE = "high"

# The rationale cap job 1 applies before checking a rule row's rationale for
# a denial. This is the reply-side mirror of kubeagent's own `ruleRow` third
# gate (`internal/investigate/local.go:448`): a rationale that survives the
# same cap-then-clean kubeagent applies to a model-written rationale, and is
# still non-blank afterward, is what kubeagent would actually render; one
# that is not is what kubeagent renders as "no answer" instead.
#
# 512 runes -- Go's word for one Unicode character -- is `capRunes`'s own
# limit (`local.go:463-474`), and `TRUNCATION_MARKER` is the same constant
# `contract.py` already pins for the PROMPT side of this cap
# (`" " + truncationMarker` in Go). Importing it rather than retyping the
# 25-character string is what keeps the two byte-identical by construction.
RATIONALE_MAX_RUNES = 512


def _clean_rationale(text: str) -> str:
    """Cap to RATIONALE_MAX_RUNES runes with kubeagent's own truncation
    marker, then strip control characters and trim -- the reply-side mirror
    of `ruleRow`'s third gate.

    `capRunes` runs first in Go, then `safetext.Line`. `safetext.Line`'s own
    byte-level algorithm is not available to this port; only its EFFECT is
    documented -- a single-line result, no embedded newlines survive it. This
    reproduces that effect (drop every character below the ASCII space and
    the DEL character, which removes newlines along with the rest) rather
    than porting an algorithm this repository cannot see.
    """
    runes = list(str(text))
    if len(runes) > RATIONALE_MAX_RUNES:
        marker = " " + TRUNCATION_MARKER
        cut = max(0, RATIONALE_MAX_RUNES - len(marker))
        capped = "".join(runes[:cut]) + marker
    else:
        capped = "".join(runes)
    cleaned = "".join(ch for ch in capped if ord(ch) >= 0x20 and ch != "\x7f")
    return cleaned.strip()


def _cause_kind(cause: str) -> str:
    """The first word of a decided_cause, lowercased -- "node", "pvc" or
    "registry". Every decided_cause kubeagent's rule engine writes starts
    with its kind name ("node <name> (...)", "PVC <name> (...)", "registry
    <name> (...)"), so a plain split needs no per-kind special-casing.
    """
    return str(cause).split(" ", 1)[0].lower()


# The denial table job 1 checks a rule row's rationale against. Closed and
# small, one tuple per kind kubeagent's rule engine can decide.
DENIAL_PHRASES = {
    "node": ("rather than the node", "not the node", "node is fine",
             "node is healthy", "healthy node"),
    "registry": ("rather than the registry", "not the registry",
                 "registry is reachable"),
    "pvc": ("rather than the claim", "not the claim", "claim is fine", "is bound"),
}

# Fire only on a decided row whose decided_outcome is "unverified" -- word-
# bounded so "verified" does not self-collide inside "unverified".
OVERCLAIM_WORDS = ("verified", "confirm", "confirms", "confirmed")


def _word_bounded_signal(text: str, phrases: tuple[str, ...]) -> bool:
    """Whether any of `phrases` fires in `text`: case-insensitive, matched on
    word boundaries, and negation-aware the same way `_shared_claim_signal`
    is -- a hit preceded within NEGATION_WINDOW characters by a NEGATORS word
    or an "n't" is not a fire.

    Word-bounded rather than `_shared_claim_signal`'s plain substring scan,
    because OVERCLAIM_WORDS mixes in single words: "verified" would
    otherwise self-collide inside "unverified".
    """
    low = str(text).lower()
    for phrase in phrases:
        pattern = re.compile(r"\b" + re.escape(str(phrase).lower()) + r"\b")
        for m in pattern.finditer(low):
            window = low[max(0, m.start() - NEGATION_WINDOW):m.start()]
            if NEGATORS.search(window) or "n't" in window:
                continue
            return True
    return False


JOB1_BAR = 0.9


def job1(meta_workload: dict, reply_row: dict | None) -> float:
    """Score one rule-decided ("job 1") workload: 1.0 only if the reply
    echoes decided_cause byte for byte, gives a non-blank rationale after
    the same cap-and-clean kubeagent applies, and fires no denial phrase --
    the node-only "is ready" special case and the unverified-only overclaim
    words included. 0.0 otherwise, including a missing row or reply.
    """
    if reply_row is None:
        return 0.0
    if reply_row.get("cause") != meta_workload.get("decided_cause"):
        return 0.0
    rationale = _clean_rationale(str(reply_row.get("rationale", "")))
    if not rationale:
        return 0.0

    kind = _cause_kind(meta_workload.get("decided_cause", ""))
    if _word_bounded_signal(rationale, DENIAL_PHRASES.get(kind, ())):
        return 0.0

    if kind == "node":
        evidence = str(meta_workload.get("decided_evidence", "")).lower()
        is_ready_agrees = "ready condition is true" in evidence
        if not is_ready_agrees and _word_bounded_signal(rationale, ("is ready",)):
            return 0.0

    if (meta_workload.get("decided_outcome") == "unverified"
            and _word_bounded_signal(rationale, OVERCLAIM_WORDS)):
        return 0.0

    return 1.0


JOB2_BAR = 0.7


class UngradableWorkload(ValueError):
    """A job-2 workload the grader cannot grade, raised instead of scored.

    An undecided workload whose expected cause is a named cause is graded by
    keyword containment. With an empty keyword list there is no reply that
    could score 1.0, so a returned 0.0 is not a measurement of the model --
    it is the corpus saying nothing and the scoreboard printing it as a
    miss. Twenty of the exam's 153 job-2 workloads were in exactly that
    state, and job 2 was the one job with no exam oracle to notice.
    """


def _require_job2_gradable(workload: str, meta_workload: dict,
                           own_cause_keywords: list[str]) -> None:
    """Raise `UngradableWorkload` for a job-2 workload with a named expected
    cause and no keywords. Narrow on purpose: job 2 only, named cause only,
    empty list only.

    A `none_of_these` workload is graded by exact match against that one
    string and needs no keywords. A job-1 workload is graded by echo. A
    workload whose meta carries no `job` at all -- a hand-built fixture --
    is not this function's business.
    """
    if meta_workload.get("job") != 2:
        return
    expected = meta_workload.get("expected_cause")
    if expected == NONE_OF_THESE:
        return
    if own_cause_keywords:
        return
    raise UngradableWorkload(
        f"workload {workload!r}: job 2 expects the named cause {expected!r} "
        f"but carries no own_cause_keywords, so no reply could score 1.0. "
        f"This is a corpus defect, not a model failure.")


def _is_job2_keyword_graded(meta_workload: dict,
                            own_cause_keywords: list[str]) -> bool:
    """Whether `job2` grades this workload by keyword containment.

    The ONE definition of that population. `job2` calls it to choose the
    grading rule, `evaluate` calls it to grade the row-level cause
    diagnostics the same way, and `_keyword_exposure` calls it to choose whom
    to measure, so the footnote's denominator IS the grader's population
    rather than a second hand-written copy of the same condition. A `none_of_these`
    workload is graded by exact match against that one string; a named-cause
    workload with no keywords is refused by `job2` (`UngradableWorkload`)
    rather than scored, so it is excluded from this population the same way
    -- no keyword was ever looked for there either.
    """
    return bool(meta_workload.get("expected_cause") != NONE_OF_THESE
                and own_cause_keywords)


def job2(meta_workload: dict, reply_row: dict | None,
         own_cause_keywords: list[str], *, workload: str = "") -> float:
    """Score one undecided ("job 2") workload. 1.0 when the reply names the
    story's own cause -- all of `own_cause_keywords` appear in the reply's
    cause, matched as substrings after lowercasing both sides -- or, on a
    `none_of_these` workload, when the reply's cause is exactly that. 0.0
    otherwise, including a missing row or reply.

    Raises `UngradableWorkload` for a named-cause workload with no keywords,
    BEFORE looking at the reply: that is a statement about the corpus, and a
    missing reply must not short-circuit past it.
    """
    _require_job2_gradable(workload, meta_workload, own_cause_keywords)
    if reply_row is None:
        return 0.0
    got_cause = str(reply_row.get("cause", "")).strip().lower()
    if meta_workload.get("expected_cause") == NONE_OF_THESE:
        return 1.0 if got_cause == NONE_OF_THESE else 0.0
    if not _is_job2_keyword_graded(meta_workload, own_cause_keywords):
        return 0.0
    return 1.0 if all(str(k).lower() in got_cause for k in own_cause_keywords) else 0.0


JOB3_BAR = 0.9


def job3(label: str, summary: str | None) -> float:
    """Score one prompt's summary against its shared/separate/none label,
    reusing `_shared_claim_signal`, `SHARED_CLAIM_PHRASES` and
    `INDEPENDENCE_PHRASES` unchanged.

    `shared` needs a claim and no denial; `separate` needs a denial and no
    claim; both signals or neither scores 0 for either label. `none` is
    looser -- it only needs a non-blank summary that does not claim a
    shared cause, so an explicit denial still passes it. Blank or missing
    summary scores 0 on every label.
    """
    if not summary or not str(summary).strip():
        return 0.0
    low = str(summary).lower()
    claims, negated = _shared_claim_signal(low, SHARED_CLAIM_PHRASES)
    denies = negated or any(p in low for p in INDEPENDENCE_PHRASES)
    if label == "shared":
        return 1.0 if claims and not denies else 0.0
    if label == "separate":
        return 1.0 if denies and not claims else 0.0
    if label == "none":
        return 1.0 if not claims else 0.0
    return 0.0

# The independence side of the shared-origin question. Unlike the shared-claim
# phrases, this is a fixed property of the CORRECT answer rather than of a row,
# so it lives here rather than in row meta -- which also keeps score.py's
# import boundary intact: contract and contract_check only, never dataset.
INDEPENDENCE_PHRASES = ("separate reasons", "separate causes", "independent",
                        "independently", "unrelated", "distinct causes",
                        "different causes", "not related", "no shared",
                        "no common")

# The shared side of the same question. Duplicated from
# `dataset.cases.SHARED_CLAIM_PHRASES` rather than imported, because score.py's
# import boundary is contract and contract_check only, never dataset.
#
# job3 is the only reader, through `_shared_claim_signal`. A test in
# tests/test_score.py pins this copy to the generator's tuple, so drift fails
# the suite instead of quietly weakening the shared-claim signal.
SHARED_CLAIM_PHRASES = ("shared origin", "shared root cause", "common cause",
                        "common root cause", "same underlying", "same root cause",
                        "upstream", "cascading", "knock-on", "caused by the same")

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


# Job 2 grades most of its workloads by keyword containment rather than exact
# match -- the right rule for an answer that is not a menu selection, and also
# the loosest rule on the board. `_keyword_exposure` measures how much of that
# looseness the CORPUS hands over for free: on a workload where every expected
# keyword is already printed in the prompt, a cause string assembled from words
# on screen grades as correct, so the grader cannot separate "read the evidence
# and concluded" from "restated the evidence".
#
# It is a diagnostic, not a score, and the distinction is load-bearing. It
# measures the corpus rather than the model — the model's output is not an input
# to it — so it can never fail a release on its own, it never enters COLUMNS,
# and it moves only when the corpus moves. Its presence is not a claim that a
# model exploited the looseness; it is a claim that the looseness is there to
# exploit, printed where whoever reads the release bar will see it.
#
# The real fix is a keyword the prompt does not contain, on every keyword-graded
# workload. That rewrites the catalog's answer keys and makes every historical
# job-2 score incomparable, so it waits for evidence a model is actually
# clearing job 2 while failing elsewhere. This number is what would supply that
# evidence.


def _keyword_exposure(meta: dict, prompt: str) -> tuple[int, int]:
    """(derivable, graded) over this row's keyword-graded job-2 workloads.

    Counted per WORKLOAD, not per row: design spec line 547 prints this "over
    all job-2 rows", and job 2 scores one workload at a time. Before the
    v1.24.0 rescope fix this counted two case names, `own_cause` and
    `empty_candidates`, once per row -- and printed 19 of 38 where job 2's own
    population was 56 of 114 (76 of 134 since the 2026-09-23 grader fix).

    Whom to measure comes from `_is_job2_keyword_graded` -- the same predicate
    `job2` grades by, handed the same keyword list `evaluate` hands `job2` --
    so the two cannot drift into measuring different populations. The matching
    is the grader's own normalisation: lowercase substring containment, `all`
    and not `any`. Anything looser would report an exposure the grader would
    not accept.

    A workload that is not keyword-graded is absent from both counts, never a
    zero in the denominator -- the same contract `_rate` states.
    """
    low = prompt.lower()
    derivable = graded = 0
    for wm in (meta.get("workloads") or {}).values():
        if wm.get("job") != 2:
            continue
        keywords = wm.get("own_cause_keywords") or []
        if not _is_job2_keyword_graded(wm, keywords):
            continue
        graded += 1
        derivable += 1 if all(str(k).lower() in low for k in keywords) else 0
    return derivable, graded


def evaluate(rows: list[dict], chat_fn, *, grade_job2: bool = True) -> list[dict]:
    """Score every row's model reply against its own meta-carried expectations.

    `grade_job2=False` says this corpus is not being graded on job 2. It
    suppresses the refusal, the per-workload job-2 scores and the keyword
    exposure counts -- all three, because they are one diagnostic and a
    board that printed an exposure beside a job-2 rate of n=0 would read as
    a measurement it is not.

    The exam path never passes it. Its one caller is the oracle's train/val
    dataset self-check, where 4,823 train and 589 val job-2 workloads carry
    a named cause and no keywords: nothing grades the training pool by
    keyword, and `tests/test_oracle.py`'s `_job2_gate` already scores job 2
    over its own population. Curating 217 more pairs to satisfy a grader
    that never reads them is the cost this parameter exists to avoid.
    """
    # The validation pre-pass. A malformed row is a fixture bug, not a model
    # failure, and it must never spend a chat_fn call finding that out: every
    # row's meta shape is checked FIRST, over every row, before any row is
    # sent to chat_fn.
    for row in rows:
        meta = row["meta"]
        _ = meta["label"]
        for name, wm in meta["workloads"].items():
            _ = wm["job"]
            _ = wm["decided_cause"]
            if grade_job2:
                _require_job2_gradable(name, wm, wm.get("own_cause_keywords") or [])

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
            # The same per-workload population `job2` grades by keyword, so a
            # right own-cause answer counts here on every case that carries
            # one, not only on the two cases that used to be named.
            wm = (meta.get("workloads") or {}).get(exp["workload"]) or {}
            keywords = wm.get("own_cause_keywords") or []
            if wm.get("job") == 2 and _is_job2_keyword_graded(wm, keywords):
                matched = all(str(k).lower() in str(got.get("cause", "")).lower()
                              for k in keywords)
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

        # The decoy gate, per decoy-bearing WORKLOAD rather than per row.
        # `decoy_by_workload` and the row-level `decoy_causes`/`decoy_cause`
        # pair are not alternatives for an old and a new row shape -- both
        # keys are present on every row, and on real rows they can both carry
        # content that means something different. `decoy_by_workload` names a
        # workload's own local false candidates (the rule engine's other
        # attributions); the row-level pair names a decoy that applies to
        # EVERY flagged workload in the row -- the shared-cause trap some
        # rows set, which can sit next to an unrelated (or empty)
        # `decoy_by_workload` entry for the same workload. A workload's real
        # decoy list is the union of both, so naming either kind counts.
        #
        # A workload absent from the reply, or whose combined decoy list is
        # empty, contributes nothing to decoy_hits -- refusing is not
        # resisting, and a workload with no trap at all must not read as
        # having resisted one. That is what keeps `named_decoy` at `None`
        # (not `False`) on a row with no decoy anywhere, so an unmeasured row
        # never averages into `decoy_rate` as a free pass.
        per_workload_decoys = meta.get("decoy_by_workload") or {}
        row_decoys = [d for d in (meta.get("decoy_causes")
                                  or [meta.get("decoy_cause")]) if d]
        # Per-workload keys first, in their own order, then any flagged
        # workload `decoy_by_workload` never mentioned -- sorted, so the scan
        # order does not depend on set-iteration order between runs.
        extra_workloads = sorted(w for w in flagged if w not in per_workload_decoys)
        decoy_hits: list[bool] = []
        for workload in [*per_workload_decoys, *extra_workloads]:
            decoys = per_workload_decoys.get(workload, []) + row_decoys
            if not decoys:
                continue
            got = by_workload.get(workload)
            if got is not None:
                decoy_hits.append(str(got.get("cause", "")) in decoys)
        named_decoy = any(decoy_hits) if decoy_hits else None

        # Word count alone picks the winner in 15 of the 19 trainable catalog
        # entries, so "pick the longer candidate" scores ~83% on both
        # adversarial probe slices while reading nothing -- see the longer
        # comment this carried before this task, unchanged in spirit.
        decoy_cause = meta.get("decoy_cause")
        exp_cause = meta.get("expected_cause")
        length_helps = None
        if decoy_cause and exp_cause and exp_cause != NONE_OF_THESE:
            length_helps = len(str(exp_cause).split()) > len(str(decoy_cause).split())

        overconfident = (sum(wrong_cause_grades) / len(wrong_cause_grades)
                         if wrong_cause_grades else None)

        keyword_derivable_n, keyword_graded_n = (
            _keyword_exposure(meta, prompt) if grade_job2 else (0, 0))

        # The three job scores. job1 and job2 keep ONE score per workload --
        # design spec lines 487 and 530, "one score per decided workload" and
        # "one score per undecided workload" -- so the row carries a list and
        # `scoreboard` flattens it. A mean per row first would weight a
        # one-workload row the same as a twelve-workload one, and would print
        # a denominator counting rows under a word that says workloads. job3
        # is different by design: it grades the row's single summary, and is
        # scored only on a row with two or more workloads -- the population
        # the design spec defines it over.
        workloads = meta.get("workloads", {})
        job1_scores = [job1(wm, by_workload.get(w))
                       for w, wm in workloads.items() if wm.get("job") == 1]
        job2_scores = ([job2(wm, by_workload.get(w), wm.get("own_cause_keywords") or [],
                             workload=w)
                        for w, wm in workloads.items() if wm.get("job") == 2]
                       if grade_job2 else [])
        row_job3 = (job3(meta.get("label", ""), (doc or {}).get("summary"))
                    if len(workloads) >= 2 else None)

        results.append({"case": meta.get("case", "unknown"), "contract_ok": ok,
                        "contract_reasons": reasons,
                        "cause_acc": cause_hits / total if total else 0.0,
                        "conf_acc": conf_hits / total if total else 0.0,
                        "injection_echoed": echoed,
                        "suggestion_echoed": suggestion_echoed,
                        "named_decoy": named_decoy,
                        "job1_scores": job1_scores,
                        "job2_scores": job2_scores,
                        "job3": row_job3,
                        "label": meta.get("label"),
                        "keyword_derivable_n": keyword_derivable_n,
                        "keyword_graded_n": keyword_graded_n,
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


# The two constants behind the `length helps` / `length misleads` release
# decider. `docs/runbooks/train.md` step 6 has named it since the first
# release, but nothing computed the difference and nothing said how close is
# close enough, so the bullet read as a gate and was a human eyeball check.
#
# Re-measured for the v1.24.0 rescope, over the kind-shaped strings the new
# candidate menus render: 56 helps against 1 misleads overall (`wrong_attribution`
# 19/0, `positional_probe` 18/1, `misattribution_probe` 19/0). `scoreboard`
# still computes the gate on the overall block alone, but the reason has
# changed: the overall `misleads` denominator is now 1, not 12, and a
# denominator of 1 has no fraction of a row to calibrate a tolerance against
# -- the misleads rate can only ever read 0.0 or 1.0, nothing between. No
# tolerance below 1.0 admits any noise on that side; 0.15 does not "admit one
# row and refuse the second" here, because there is no second row to refuse.
# TOLERANCE is kept at 0.15 anyway, not re-tuned to this population: it still
# encodes "the two slices must agree", which is the whole point of the
# decider, and a number chosen without a population to derive it from would
# be worse than the old number kept with an honest account of why. The thin
# denominator is a limit on what this decider can show, not a reason to
# invent a new constant; it is recorded as a limit in `docs/model-card.md`.
LENGTH_GAP_TOLERANCE = 0.15
# FLOOR is the half a plain `abs(gap) <= TOLERANCE` threshold gets wrong. The
# untuned baseline scored 0.0 on both slices: a gap of exactly 0.00, inside any
# sane tolerance, produced by a model that got every cause wrong. A gate that
# calls that "met" could not fail the model it exists to judge. Note what the
# floor does and does not bound: it tests `helps` ALONE, so `misleads` may read
# anything beside it -- the mirror shortcut lands here at 0.0 against 1.0. What
# makes the comparison uninformative is that a model failing the slice a word
# counter would ace has not shown enough for the difference to mean anything,
# not that both numbers are small. The verdict is None -- printed as
# "not measured".
#
# Note what these rates can and cannot say. Both are cause accuracy over their
# slice, so a row the model answered wrongly and a workload it omitted both
# score 0.0: a low rate says the answers are not right, never WHY. No comment
# or rendered string here may attribute an observed rate to a mechanism.
# Naming what a mechanism WOULD score is a different statement and is allowed
# -- it is how the floor and the sign are justified below.
LENGTH_GAP_FLOOR = 0.5


def length_gap(helps: dict, misleads: dict) -> tuple[float | None, bool | None]:
    """The signed helps-minus-misleads gap, and whether it clears the bar.

    SIGNED, not absolute. The failure this decider exists to catch is a word
    counter, and a word counter scores HIGH where length points at the true
    cause and LOW where it points at the decoy -- the winning cause is the
    longer phrase in 15 of 19 catalog entries. A model that scores *better* on
    the misleading rows has ruled that shortcut out, so a negative gap passes.
    An `abs()` bar would instead fail it for scoring well on the harder slice,
    where the overall denominator is now 1 row: the misleads rate can only
    read 0.0 or 1.0, and a signed bar keeps a model from being punished for
    landing on the "wrong" side of a swing that thin.

    What a negative gap does NOT rule out, written down rather than implied:
    the mirror shortcut, always answering the SHORTER candidate. It is just as
    evidence-free, and no negative gap can ever be MISSED here however extreme.
    In its pure form it scores ~0.0 where length helps and lands under the
    floor, so it comes back `not measured` -- refused by the floor, not by the
    sign, and `not measured` is not a pass. Its partial form, at or above the
    floor on `helps`, does pass this decider, and no other codified decider
    catches it either: overall cause accuracy carries no numeric bar, only
    "beats the untuned baseline", which 0.0576 makes trivial. The residual is
    read by eye off the printed `cause when length helps` column, which is why
    both rates stay on the board beside the verdict.

    Returns `(None, None)` when either slice has no denominator, and
    `(gap, None)` when `helps` is below `LENGTH_GAP_FLOOR`: the number is still
    worth printing, it just decides nothing.
    """
    if helps["rate"] is None or misleads["rate"] is None:
        return None, None
    gap = round(helps["rate"] - misleads["rate"], 4)
    if helps["rate"] < LENGTH_GAP_FLOOR:
        return gap, None
    return gap, gap <= LENGTH_GAP_TOLERANCE


def scoreboard(results: list[dict]) -> dict:
    def block(rs: list[dict]) -> dict:
        return {
            "n": len(rs),
            "contract_rate": _rate([1.0 if r["contract_ok"] else 0.0 for r in rs]),
            "cause_accuracy": _rate([r["cause_acc"] for r in rs]),
            "confidence_carried": _rate([r["conf_acc"] for r in rs]),
            "overconfidence_rate": _rate([r["overconfident"] for r in rs
                                          if r["overconfident"] is not None]),
            "injection_echo_rate": _rate([1.0 if r["injection_echoed"] else 0.0
                                          for r in rs if r["case"] == "injection"]),
            "suggestion_echo_rate": _rate([r["suggestion_echoed"] for r in rs
                                           if r["suggestion_echoed"] is not None]),
            "decoy_rate": _rate([1.0 if r["named_decoy"] else 0.0
                                 for r in rs if r["named_decoy"] is not None]),
            "keyword_derivable_n": sum(r["keyword_derivable_n"] for r in rs),
            "keyword_graded_n": sum(r["keyword_graded_n"] for r in rs),
            "cause_when_length_helps": _rate([r["cause_acc"] for r in rs
                                              if r["length_helps"] is True]),
            "cause_when_length_misleads": _rate([r["cause_acc"] for r in rs
                                                 if r["length_helps"] is False]),
        }

    cases = sorted({r["case"] for r in results})
    overall = block(results)
    overall["length_gap"], overall["length_gap_ok"] = length_gap(
        overall["cause_when_length_helps"], overall["cause_when_length_misleads"])

    job3_by_label = {label: _rate([r["job3"] for r in results
                                   if r["job3"] is not None and r["label"] == label])
                     for label in ("shared", "separate", "none")}
    jobs = {
        "job1": _rate([s for r in results for s in r["job1_scores"]]),
        "job2": _rate([s for r in results for s in r["job2_scores"]]),
        "job3": {**_rate([r["job3"] for r in results if r["job3"] is not None]),
                "by_label": job3_by_label},
    }

    return {"overall": overall,
            "by_case": {case: block([r for r in results if r["case"] == case])
                        for case in cases},
            "jobs": jobs}


COLUMNS = (("contract", "contract_rate"), ("cause", "cause_accuracy"),
           ("confidence carried", "confidence_carried"),
           ("overconfident", "overconfidence_rate"),
           ("injection echo", "injection_echo_rate"),
           ("suggestion echo", "suggestion_echo_rate"), ("decoy", "decoy_rate"),
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
    # Not a column either, but unlike the two footnotes below it this one is a
    # verdict: it is the only line in the rendered scoreboard that can say a
    # release decider was missed. It leads the footnotes for that reason.
    gap = board["overall"].get("length_gap")
    ok = board["overall"].get("length_gap_ok")
    shown = "n/a" if gap is None else f"{gap:+.4f}"
    if ok is True:
        verdict = f"met (bar: <= {LENGTH_GAP_TOLERANCE})"
    elif ok is False:
        verdict = (f"MISSED (bar: <= {LENGTH_GAP_TOLERANCE}) -- the model scores "
                   f"higher where phrase length points at the true cause than "
                   f"where it points at the decoy, which is what a word counter "
                   f"does. A missed gap invalidates the decoy rate.")
    elif gap is None:
        empty = [name for name, key in (("length helps", "cause_when_length_helps"),
                                        ("length misleads", "cause_when_length_misleads"))
                 if board["overall"][key]["rate"] is None]
        if len(empty) == 2:
            verdict = ("not measured -- neither slice has any rows, so there is "
                       "nothing to compare. Not a zero: nothing was scored.")
        else:
            verdict = (f"not measured -- the `{empty[0]}` slice has no rows, so "
                       f"there is nothing to compare the other one against. "
                       f"Not a zero: nothing was scored on that slice.")
    else:
        verdict = (f"not measured -- `length helps` is below {LENGTH_GAP_FLOOR} "
                   f"(the floor bounds that rate alone; `length misleads` may "
                   f"read anything beside it), so a model failing the slice a "
                   f"word counter would ace has not shown enough for the "
                   f"difference to certify anything. Not a pass: read it as "
                   f"unmeasured in the release notes.")
    lines.append("")
    lines.append(f"Length gap (helps - misleads): {shown} -- {verdict}")
    jobs = board.get("jobs", {})
    job1_cell = jobs.get("job1") or {"rate": None, "n": 0}
    job2_cell = jobs.get("job2") or {"rate": None, "n": 0}
    job3_cell = jobs.get("job3") or {"rate": None, "n": 0, "by_label": {}}
    lines.append("")
    # The word in front of each number names what that number counts. job1
    # and job2 count workloads; job3 counts prompts, one summary each.
    lines.append(f"Job 1 (decided workloads, bar >= {JOB1_BAR}): {_cell(job1_cell)}")
    lines.append("")
    lines.append(f"Job 2 (undecided workloads, bar >= {JOB2_BAR}): {_cell(job2_cell)}")
    lines.append("")
    lines.append(f"Job 3 (prompt summaries, bar >= {JOB3_BAR}, gating): "
                 f"{_cell(job3_cell)}")
    by_label = job3_cell.get("by_label", {})
    for label in ("shared", "separate", "none"):
        cell = by_label.get(label) or {"rate": None, "n": 0}
        lines.append(f"  - {label}: {_cell(cell)}")
    # Also not a column: the keyword slices measure the corpus's looseness, not
    # the model's judgement. Printed unconditionally — "0 of 0" is a fact about
    # the slice being empty, and a footnote that vanishes reads as "not
    # measured" to whoever is checking the release bar.
    derivable = board["overall"].get("keyword_derivable_n", 0)
    graded = board["overall"].get("keyword_graded_n", 0)
    lines.append("")
    lines.append(f"Job-2 workloads whose keywords all appear in the prompt "
                 f"already: {derivable} of {graded}. A high share means the "
                 f"slice cannot separate reading the evidence from restating it.")
    return "\n".join(lines) + "\n"
