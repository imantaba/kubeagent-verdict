"""The counter-example half of the shared-origin exam.

`tests/test_shared_origin_training.py` closes the shortcut on the TRAINING
side: `multi` rows now carry a cluster-scoped origin read showing the
component healthy, so "an origin read is present" stops separating the two
classes in the curriculum. Its docstring names the residual it could not
close and says the fix belongs elsewhere:

    the exam cannot detect this shortcut even now -- seven of the ten
    `shared_origin_probe` rows carry a read label that appears in none of the
    other 243, so label-matching alone passes both halves of decider 5.

This is elsewhere. `shared_origin_decoy_probe` renders the SAME six scenarios
with the origin read showing the component healthy, and the correct answer
becomes each workload's own local cause under the ordinary "N workloads are
failing for separate reasons" summary. The two rows draw the same names from
the same seed, so the pair is a minimal contrast: identical inventory,
identical candidate menus, identical evidence LABELS in identical order. Only
what the reads SAY differs.

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
* the summary -- `false_shared` fires on this slice where
  `separate_reasons_rate` fires on its twin, so a model that answers "shared
  origin" everywhere and one that answers "separate reasons" everywhere both
  fail, each on the slice the other passes.

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

    If the inventory or the candidate menu moved even slightly between the
    two, a model could separate them on something other than the evidence and
    every conclusion drawn from the pair would be about that something.
    """
    for d, p in zip(decoys, probes):
        ds, ps = _sections(d.user), _sections(p.user)
        assert ds["inventory"] == ps["inventory"], d.meta["origin"]
        assert ds["candidates"] == ps["candidates"], d.meta["origin"]


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


def test_the_shared_cause_is_the_decoy_the_scorer_watches(decoys, probes):
    """`named_decoy` must fire on the trap this slice sets, not on nothing.

    Compared against the TWIN's expected answers rather than the raw
    `shared_cause` template: `{node}` and `{ns}` are substituted per row, and
    the twin -- same salt, same names -- is where the formatted string lives.
    """
    for d, t in zip(decoys, probes):
        want = set(t.meta["expected"].values())
        assert len(want) == 1, d.meta["origin"]
        assert d.meta["decoy_causes"] == list(want), d.meta["origin"]


def test_the_slice_feeds_false_shared_rather_than_separate_reasons(decoys):
    """The mirror metric, and never the one its twin feeds.

    `wrong_summary_phrase` on this slice would score the CORRECT summary as a
    failure -- independence is the right answer here.
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
    """One tag sweeps one slice and scores zero on the other, both ways."""
    def hits(examples):
        got = total = 0
        for e in examples:
            picks = _menu_pick(e, verdict)
            for workload, want in e.meta["expected"].items():
                total += 1
                got += int(picks.get(workload) == want)
        return got, total

    on_decoy, on_probe = hits(decoys), hits(probes)
    assert on_decoy[1] == on_probe[1] > 0
    won, lost = (on_decoy, on_probe) if verdict == "attributed" else (on_probe, on_decoy)
    assert won[0] == won[1], f"{verdict} should sweep its slice: {won}"
    assert lost[0] == 0, f"{verdict} should score zero on the other: {lost}"


# -------------------------------------------------- the exam-side closure

def test_every_origin_read_label_in_the_exam_carries_both_answers(exam):
    """The hole this slice exists to close.

    Before it, the distinctive cluster-wide read labels appeared ONLY on rows
    whose answer was one shared cause, so a model could answer the whole slice
    by matching the label and never reading the content -- and would pass both
    halves of decider 5 doing it. Now every label that appears under one
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

    `separate_reasons_rate` alone is gamed by that answer. This is the
    measurement that makes it cost something: cause accuracy collapses to 0,
    every row names the decoy, and `false_shared` reads 1.0 -- on a slice
    where the 0830 model, which answered independence everywhere, would have
    scored perfectly.
    """
    twin = {d.user: t.assistant for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: twin[m[1]["content"]])
    assert all(r["contract_ok"] for r in results)
    assert all(r["cause_acc"] == 0.0 for r in results)
    assert all(r["named_decoy"] is True for r in results)
    assert all(r["false_shared"] == 1.0 for r in results)
    assert not any(r["shared_ambiguous"] for r in results)


def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape."""
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]])
    assert all(r["cause_acc"] == 1.0 for r in results)
    assert all(r["conf_acc"] == 1.0 for r in results)
    assert all(r["named_decoy"] is False for r in results)
    assert all(r["false_shared"] == 0.0 for r in results)


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
