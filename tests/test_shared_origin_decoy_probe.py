"""The counter-example half of the shared-origin exam.

`tests/test_shared_origin_training.py` closes the shortcut on the TRAINING
side: `multi` rows now carry a cluster-scoped origin read showing the
component healthy, so "an origin read is present" stops separating the two
classes in the curriculum. Its docstring names the residual it could not
close and says the fix belongs elsewhere:

    the exam cannot detect this shortcut even now -- seven of the ten
    `shared_origin_probe` rows carry a read label that appears in none of the
    other 243, so label-matching alone clears job 3 and the decoy rate.

This is elsewhere. `shared_origin_decoy_probe` renders the SAME six scenarios
with the origin read showing the component healthy, and the correct answer
becomes each workload's own local cause under the ordinary "N workloads are
failing for separate reasons" summary. The two rows draw the same names from
the same seed, so the pair is a minimal contrast: identical candidate menus,
identical evidence LABELS in identical order, and an identical inventory except
where a finding's evidence would have named the origin's fact (the victim's
`healthy_evidence` renders there instead). Only what the reads SAY differs,
plus that one line.

That gives the pair teeth on three axes at once, and the second is the one
that matters most:

* label-matching -- every read label in the exam now appears under both
  answers, so seeing `describe kube-system/coredns (Deployment)` no longer
  predicts anything;
* the tag -- the menu is byte-identical across the pair, the local cause
  carrying `attributed` and the shared cause `outranked` on BOTH. So "trust
  the attributed tag" scores 1.0 here and 0.0 on `shared_origin_probe`, and
  "always take the outranked candidate" scores exactly the reverse. Neither
  heuristic can win both, and the menu offers no third tag to try;
* the summary -- job3 grades each row against its own label, and neither
  constant answer wins both slices: a constant "shared origin" scores 0 of
  10 here and 5 of 10 on the probe twin. The twin does not mirror this
  slice -- a constant "separate reasons" sweeps this slice 10 of 10 and
  still only reaches 5 of 10 there, because half the probe rows carry
  label `none`, which a denial passes.

Two things it does NOT do, stated rather than implied.

The 0830 model would ace this slice: it answered "separate reasons" on all ten
probe rows, which is this slice's correct answer. Under the rule that an eval
change which could not fail the model it replaced is not a fix, this slice
alone is not a fix -- it is the second half of a pair, and the PAIR could
always fail 0830. What it guards is the opposite failure, the one a correction
trained on counter-examples can plausibly introduce.

And `confidence_carried` is copyable here in a way it is not on the twin: the
expected grade is the deterministic pass's own per-workload grade, printed in
the prompt, because when the local attribution is right its grade is right
too. That is a property of the scenario, not a choice, and inventing a
different grade to defeat the copy would be inventing evidence.
"""

import json
import re

import pytest

from kubeagent_verdict.dataset import cases, generate, propagation
from kubeagent_verdict.evals import score

CASE = "shared_origin_decoy_probe"
SECTION = re.compile(r"^== (BEGIN|END) (\w+) ==$")
LABEL = re.compile(r"^== (?!BEGIN |END ).* ==$")


@pytest.fixture(scope="module")
def exam():
    return generate.test_set()


@pytest.fixture(scope="module")
def decoys(exam):
    rows = [e for e in exam if e.case == CASE]
    # Without this, every loop below passes over an empty list and the slice
    # could be unwired from `probe_sets` with a green suite.
    assert rows, f"{CASE} is not in the exam"
    return rows


@pytest.fixture(scope="module")
def probes(exam):
    return [e for e in exam if e.case == "shared_origin_probe"]


def _sections(user: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in user.splitlines():
        m = SECTION.match(line)
        if m and m.group(1) == "BEGIN":
            current = m.group(2)
            out[current] = []
            continue
        if m and m.group(1) == "END":
            current = None
            continue
        if current is not None:
            out[current].append(line)
    return out


# --------------------------------------------------------------- the slice

def test_the_slice_mirrors_the_probe_row_for_row(decoys, probes):
    """Same scenarios, same widths, same order -- one counter-example each."""
    assert len(decoys) == len(probes) == 10
    assert [e.meta["origin"] for e in decoys] == [e.meta["origin"] for e in probes]


def test_every_eval_scenario_declares_a_healthy_origin_read():
    for p in propagation.all_scenarios():
        assert p.healthy_origin_content.strip(), p.key


def test_the_pair_shows_the_same_workloads_with_the_same_menus(decoys, probes):
    """The claim that makes the pair a contrast rather than two questions.

    If the inventory or the candidate menu moved between the two on anything
    but the evidence, a model could separate them on that something and every
    conclusion drawn from the pair would be about it. Two moves are allowed.
    A finding line whose victim declares a `healthy_evidence`: without it the
    healthy half's inventory would assert the origin is broken and argue
    against its own label. And the `decided by rules:` line, which v1.24.0
    prints from a fresh re-check of the origin read -- on the scenarios that
    decide off that read the broken half decides and the healthy half does
    not. That line is the rule engine's reading of the evidence, so it is
    not a way of separating the halves without reading; the full accounting
    is in `tests/test_healthy_evidence.py`.
    """
    from kubeagent_verdict.dataset import propagation as prop

    def without_decided(lines):
        return [x for x in lines if not x.startswith("    decided by rules: ")]

    for d, p in zip(decoys, probes):
        ds, ps = _sections(d.user), _sections(p.user)
        assert without_decided(ds["candidates"]) == without_decided(ps["candidates"]), \
            d.meta["origin"]
        assert len(ds["inventory"]) == len(ps["inventory"]), d.meta["origin"]
        moved = [(a, b) for a, b in zip(ps["inventory"], ds["inventory"]) if a != b]
        scenario = next(x for x in prop.all_scenarios() if x.key == d.meta["origin"])
        allowed = [v for v in scenario.victims if v.healthy_evidence]
        assert len(moved) == len(allowed), (d.meta["origin"], moved)
        for (a, b), v in zip(moved, allowed):
            assert "issue:" in a and "issue:" in b, (d.meta["origin"], a, b)
            assert v.healthy_evidence.split("{")[0] in b, (d.meta["origin"], b)


def test_the_pair_reads_the_same_things_in_the_same_order(decoys, probes):
    """Same labels, same order, different content -- and content must differ."""
    for d, p in zip(decoys, probes):
        ds, ps = _sections(d.user), _sections(p.user)
        assert [x for x in ds["evidence"] if LABEL.match(x)] == \
               [x for x in ps["evidence"] if LABEL.match(x)], d.meta["origin"]
        assert ds["evidence"] != ps["evidence"], d.meta["origin"]


def test_no_decoy_prompt_carries_a_BROKEN_line_of_the_origin_read(decoys):
    """Every line the two worlds do not share must be gone from this one.

    Not every line: the two reads are the same report of the same component,
    so section headers (`Conditions:`) and facts the outage never changed
    (`memory  2Gi (41%)`) appear in both by construction, and demanding their
    absence would be demanding a different report rather than a healthy one.
    What must not survive is any line the broken read carries and the healthy
    content does not -- `DiskPressure   True`, `0 available | 2 unavailable`.
    """
    checked = 0
    for e in decoys:
        p = propagation.by_key()[e.meta["origin"]]
        healthy = {x.strip() for x in p.healthy_origin_content.splitlines()}
        for line in p.origin_read[1].splitlines():
            if not line.strip() or line.strip() in healthy:
                continue
            checked += 1
            assert line.strip() not in e.user, (p.key, line)
    assert checked >= len(decoys), "nothing distinctive was actually checked"


def test_the_correct_answer_is_each_workload_s_own_local_cause(decoys):
    """One cause per workload, all different -- the opposite of the twin."""
    for e in decoys:
        causes = list(e.meta["expected"].values())
        assert len(set(causes)) == len(causes), e.meta["origin"]
        p = propagation.by_key()[e.meta["origin"]]
        assert p.shared_cause not in causes, e.meta["origin"]
        assert p.distractor_cause not in causes, e.meta["origin"]


def test_the_summary_says_separate_reasons(decoys):
    for e in decoys:
        summary = json.loads(e.assistant)["summary"]
        assert propagation.SEPARATE_REASONS in summary, e.meta["origin"]


def test_the_shared_cause_is_the_decoy_the_scorer_watches(decoys):
    """`named_decoy` must fire on the trap this slice sets, not on nothing.

    `decoy_causes` (spec section 9: protected, unconditional) is always the
    one formatted `shared_cause` sentence, never a decided victim's own
    terse cause -- checked against the scenario's own `shared_cause`
    template rather than against either twin's `expected` values, because
    neither half is a reliable source any more: this row's own `expected`
    never holds it (a decoy row's undecided victims render their own local
    cause, not the shared one -- `test_the_correct_answer_is_each_workload_
    s_own_local_cause` above), and the twin probe's `expected` only holds it
    when the probe still has an undecided victim left -- an origin-object
    story that happens to draw every victim decided leaves nothing in `expected`
    for the trap to match, even though the trap itself is still set.
    """
    for e in decoys:
        assert len(e.meta["decoy_causes"]) == 1, e.meta["origin"]
        template = propagation.by_key()[e.meta["origin"]].shared_cause
        pattern = re.sub(r"\\\{\w+\\\}", ".+", re.escape(template))
        assert re.fullmatch(pattern, e.meta["decoy_causes"][0]), e.meta["origin"]


def test_the_slice_carries_shared_claim_phrases_and_no_wrong_summary_phrase(decoys):
    """The one meta field this slice needs, and the one it must not carry.

    `shared_claim_phrases` is kept for the pinned hash blob and read by
    no scorer -- job3's honesty check runs on its own copy of the phrases in
    score.py, not on this key. `wrong_summary_phrase` on this slice would
    score the CORRECT summary as a failure -- independence is the right
    answer here.
    """
    for e in decoys:
        assert e.meta["shared_claim_phrases"] == list(cases.SHARED_CLAIM_PHRASES)
        assert "wrong_summary_phrase" not in e.meta


# ------------------------------------------------- neither heuristic wins both

def _menu_pick(example, verdict: str) -> dict[str, str]:
    """Answer every workload with the candidate the prompt tags `verdict`.

    Parsed back out of the rendered prompt rather than read off the builder,
    so this measures the shortcut a model can actually take.
    """
    marker = f": {'ruled out' if verdict == 'ruled_out' else verdict} — "
    picks: dict[str, str] = {}
    workload = None
    for line in _sections(example.user)["candidates"]:
        header = re.match(r"^- (\S+) \(\w+\) \[confidence: \w+\]:$", line.strip())
        if header:
            workload = header.group(1)
            continue
        body = line.strip()
        if workload and body.startswith("considered ") and marker in body:
            picks.setdefault(workload, body[len("considered "):].split(marker)[0])
    return picks


@pytest.mark.parametrize("verdict", ["attributed", "outranked"])
def test_no_tag_heuristic_wins_both_shared_origin_slices(decoys, probes, verdict):
    """One tag sweeps one slice and scores zero on the other, both ways.

    Over the workloads UNDECIDED ON BOTH HALVES of the pair -- the
    local-decoy-vs-shared-cause tension this tag pair exists to measure.
    Excluded jointly, not per half: an origin-object story's victims decide
    on the broken half and undecide on the healthy half (a healthy origin object
    confirms nothing), so a per-half filter would drop a different set of
    workloads from each side and the two totals would stop matching. A
    decided workload's correct answer is the rules' terse cause, which
    never appears on the fixed three-candidate menu (decoy/distractor/
    shared_cause) at all; it lives on the separate `decided by rules:` line
    `_menu_pick` does not read, so every tag pick misses it on both slices
    and it carries no signal either way.
    """
    got_decoy = total_decoy = got_probe = total_probe = 0
    for d, p in zip(decoys, probes):
        decoy_picks, probe_picks = _menu_pick(d, verdict), _menu_pick(p, verdict)
        for workload, want_decoy in d.meta["expected"].items():
            if d.meta["workloads"][workload]["decided"] or \
                    p.meta["workloads"][workload]["decided"]:
                continue
            total_decoy += 1
            got_decoy += int(decoy_picks.get(workload) == want_decoy)
            total_probe += 1
            got_probe += int(probe_picks.get(workload) == p.meta["expected"][workload])

    on_decoy, on_probe = (got_decoy, total_decoy), (got_probe, total_probe)
    assert on_decoy[1] == on_probe[1] > 0
    won, lost = (on_decoy, on_probe) if verdict == "attributed" else (on_probe, on_decoy)
    assert won[0] == won[1], f"{verdict} should sweep its slice: {won}"
    assert lost[0] == 0, f"{verdict} should score zero on the other: {lost}"


# -------------------------------------------------- the exam-side closure

def test_every_origin_read_label_in_the_exam_carries_both_answers(exam):
    """The hole this slice exists to close.

    Before it, the distinctive cluster-wide read labels appeared ONLY on rows
    whose answer was one shared cause, so a model could answer the whole slice
    by matching the label and never reading the content -- and nothing then
    scored would have caught it. Now every label that appears under one
    answer appears under the other too.
    """
    shared, separate = set(), set()
    for e in exam:
        key = e.meta.get("origin")
        if key is None:
            continue
        label = propagation.by_key()[key].origin_read[0]
        (shared if e.case == "shared_origin_probe" else separate).add(label)
    assert shared, "no shared-origin rows in the exam"
    assert shared == separate


# ------------------------------------------------------------ the teeth

def test_a_model_that_always_claims_a_shared_origin_fails_this_slice(decoys, probes):
    """The failure mode a shared-origin correction can plausibly introduce.

    The fake answer is not invented: it is the TWIN row's own assistant
    message, verbatim. Same salt means same workload names, so the twin's
    answer is exactly what a model that had learned "a cluster-wide read means
    one shared cause" would emit here -- the real failure, not a caricature of
    it.

    Cause accuracy no longer collapses to a flat 0 on every row: a decided
    workload's cause does not depend on `healthy` (its own local evidence,
    not the row's origin, decides it), so the twin's answer for it is
    already correct here too.

    `named_decoy` splits by the PROBE's own label, not this row's (which is
    always `none` -- see `test_the_shared_cause_is_the_decoy_the_scorer_
    watches`'s docstring). On the three `none`-labeled origins the twin's
    answer still fires the trap on every row, but not the trap this
    docstring's title names: `decoy_by_workload` (spec section 9: protected,
    unchanged) holds `[result.cause]` for a workload the rules decided, and
    the twin decides that SAME workload to that SAME cause (healthy-
    insensitive), so the twin's own reply matches its own listed decoy --
    the pre-existing quirk `test_a_model_that_reads_the_evidence_passes_
    this_slice` below names on a fully honest reply. On the three
    `shared`-labeled origins (ruled stories) the twin is fully decided too,
    but `decoy_by_workload` is unconditionally empty there (spec section
    12's "no decoy rate on ruled stories"), and the row-level trap
    (`shared_cause`) never appears in a fully-decided twin's answer, so
    nothing fires.

    job3 grades the summary against THIS row's own `none` label, so it
    tracks what the twin's summary actually claims, not which origin it is:
    a `shared`-labeled twin (the three origin-object stories) still writes "N
    workloads share one upstream cause", which is false here, so job3 reads
    0.0. A `none`-labeled twin (the other three) already writes today's
    honest "kubeagent's rules did not confirm one cause on two or more of
    them" -- the label-driven summary's whole point is that this no longer claims a shared
    origin on a `none`-labeled row, so pasting it here, where the label is
    also `none`, is not the failure this test is naming, and job3 reads 1.0.
    """
    twin = {d.user: t.assistant for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: twin[m[1]["content"]])
    assert all(r["contract_ok"] for r in results)
    for e, t, r in zip(decoys, probes, results):
        decided = [w["decided"] for w in e.meta["workloads"].values()]
        assert r["cause_acc"] == sum(decided) / len(decided), e.meta["origin"]
        assert r["named_decoy"] is (t.meta["label"] != "shared"), e.meta["origin"]
        assert r["job3"] == (0.0 if t.meta["label"] == "shared" else 1.0), e.meta["origin"]


def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape.

    `named_decoy` no longer reads False across the board: `decoy_by_workload`
    (spec section 9: protected, unchanged) holds a decided workload's own
    candidate list, which -- for the per-victim decided branch this slice's
    two `none`-labeled rows with an embedded decided victim exercise -- is
    just `[result.cause]`, so even the CORRECT reply names its own workload
    as its own "decoy". It reads True exactly where the row decides at
    least one workload, never on a fully undecided row.
    """
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]])
    assert all(r["cause_acc"] == 1.0 for r in results)
    assert all(r["conf_acc"] == 1.0 for r in results)
    assert all(r["job3"] == 1.0 for r in results)
    for e, r in zip(decoys, results):
        n_decided = sum(1 for w in e.meta["workloads"].values() if w["decided"])
        assert r["named_decoy"] is (n_decided > 0), e.meta["origin"]


# ------------------------------------------- the training set must not move

def test_the_slice_drops_no_training_row():
    """Groups are `propagation:<eval key>:...`, which no training row can hold.

    The whole point of appending rather than editing: `drop_held_out` removes
    a train/val row whose group collides with an exam group, so an exam slice
    built from training-reachable groups would silently shrink the curriculum
    and make this change incomparable with the run it is measured against.
    """
    examples = generate.generate(seed=17, size=800)
    train, val = generate.split(examples, seed=17)
    full = generate.test_set()
    without = [e for e in full if e.case != CASE]
    for pile in (train, val):
        assert [generate.to_row(e) for e in generate.drop_held_out(pile, full)] == \
               [generate.to_row(e) for e in generate.drop_held_out(pile, without)]
