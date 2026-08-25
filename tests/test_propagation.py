"""The shared-origin propagation table and the eval slice built from it.

The curriculum's `multi` case draws its constituents with `rng.sample` over
distinct catalog entries and summarises every one of them as "N workloads are
failing for separate reasons." At release size that sentence is in 825 of 5500
training examples and there is no counterexample anywhere in the data: not one
row where several flagged workloads share a single upstream cause. The model
was therefore trained *against* the answer an operator most wants during an
incident, and `--investigate`'s local verdict mode hands it exactly that shape
— up to ten flagged workloads and one summary.

This table is the counterexample, as data. Nothing here trains anything yet;
these rows are eval-only, and their job is to make the bias measurable before
any attempt is made to correct it.
"""

import json

from kubeagent_verdict import contract as c
from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import propagation


def test_every_scenario_has_a_closed_blast_radius():
    assert propagation.all_scenarios()
    for p in propagation.all_scenarios():
        assert p.blast_radius in propagation.BLAST_RADII, p.key


def test_scenario_keys_are_unique_and_slug_shaped():
    import re
    keys = [p.key for p in propagation.all_scenarios()]
    assert len(keys) == len(set(keys))
    for k in keys:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", k), k


def test_every_victim_issue_is_in_the_closed_kind_vocabulary():
    """A victim is a pod-level symptom, so it must name one of the 16 kinds.

    This is what excludes the propagation scenarios that have no pod to
    diagnose — a blocking admission webhook and an exhausted ResourceQuota
    both surface as `FailedCreate` on the workload, a kind
    `internal/knownissues` does not document and `vocab.ISSUE_KINDS` does not
    admit. They are real propagation, and they are deliberately absent.
    """
    for p in propagation.all_scenarios():
        for v in p.victims:
            assert v.issue in vocab.ISSUE_KINDS, f"{p.key}: {v.issue}"


def test_every_victim_verdict_label_is_a_real_verdict():
    for p in propagation.all_scenarios():
        for verdict in (p.shared_verdict, p.distractor_verdict):
            assert verdict in vocab.VERDICTS, p.key


def test_no_scenario_hands_the_shared_cause_the_attributed_tag():
    """Tag and position must both point AWAY from the answer.

    Same rule as `misattribution_probe`: the local decoy leads and carries
    `attributed`, the shared cause trails. A slice where the tag happened to
    be right would measure nothing a passing `attributed` row does not.
    """
    for p in propagation.all_scenarios():
        assert p.shared_verdict != "attributed", p.key


def test_scenarios_have_two_to_four_victims():
    for p in propagation.all_scenarios():
        assert 2 <= len(p.victims) <= 4, p.key


def test_each_victim_carries_its_own_local_decoy():
    """The decoys must differ from each other and from the shared cause.

    A scenario whose victims all carry the same local decoy would let a model
    score by naming the one repeated wrong string, which is the failure mode
    this slice exists to catch.
    """
    for p in propagation.all_scenarios():
        locals_ = [v.local_cause for v in p.victims]
        assert len(set(locals_)) == len(locals_), p.key
        assert p.shared_cause not in locals_, p.key
        assert p.distractor_cause not in locals_, p.key
        assert p.distractor_cause != p.shared_cause, p.key


def test_the_pass_confidence_varies_inside_at_least_one_scenario():
    """`confidence_carried` is maxed by copying the bracketed prompt string.

    The prompt prints `[confidence: X]` per workload from the deterministic
    pass's own grade. If every victim in a row carried the same grade and the
    expected answer reused it, this slice would hand a copier a free 1.0 on
    that column. Varying the grade WITHIN a row, while the expected answer is
    one value for the whole row, makes copying impossible to score with.
    """
    assert any(len({v.pass_confidence for v in p.victims}) > 1
               for p in propagation.all_scenarios())


def test_blast_radii_are_all_exercised():
    seen = {p.blast_radius for p in propagation.all_scenarios()}
    assert seen == set(propagation.BLAST_RADII)


def test_scoped_scenarios_declare_the_field_they_pin():
    for p in propagation.all_scenarios():
        if p.blast_radius == "cluster":
            assert p.scope_field is None, p.key
        else:
            assert p.scope_field in ("ns", "node"), p.key


def test_a_pinned_scope_field_appears_in_the_shared_cause():
    """A node- or namespace-scoped origin has to name the thing it is scoped to.

    Otherwise the row claims a blast radius its answer text cannot express,
    and two different node outages render the same expected string.
    """
    for p in propagation.all_scenarios():
        if p.scope_field is not None:
            assert "{" + p.scope_field + "}" in p.shared_cause, p.key


def test_no_scenario_text_carries_a_banned_identifier_shape():
    """The provenance denylist, applied at the table rather than the render.

    `test_provenance_no_banned_text_in_test_set` scans the rendered rows, but
    it only sees text a builder actually emits. Checking the source table too
    means a field added and not yet rendered cannot smuggle one in.
    """
    import re
    banned = (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"https?://"),
              re.compile(r"kubeconfig", re.IGNORECASE), re.compile(r"/home/"),
              re.compile(r"@"))
    for p in propagation.all_scenarios():
        blob = "\n".join([p.origin, p.shared_cause, p.shared_reason, p.distractor_cause,
                          p.distractor_reason, p.rationale, p.remedy,
                          p.origin_read[0], p.origin_read[1]]
                         + [f"{v.reason}\n{v.evidence}\n{v.log_cause}\n{v.local_cause}\n"
                            f"{v.local_reason}\n{v.next_step}\n{v.command}\n"
                            f"{v.read[0]}\n{v.read[1]}" for v in p.victims])
        for pat in banned:
            assert not pat.search(blob), f"{p.key}: {pat.pattern}"


# ---------------------------------------------------------------- the builder

def _first():
    return propagation.all_scenarios()[0]


def test_builder_renders_one_verdict_row_per_victim():
    from kubeagent_verdict.dataset import cases, generate
    p = _first()
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    rows = json.loads(ex.assistant)["verdicts"]
    assert len(rows) == len(p.victims)
    assert len({r["workload"] for r in rows}) == len(rows)


def test_every_row_names_the_same_shared_cause():
    """The whole point: one origin, one answer, repeated.

    `multi` renders N different causes and says so. This row renders N
    workloads whose correct cause is one string.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        causes = {r["cause"] for r in json.loads(ex.assistant)["verdicts"]}
        assert len(causes) == 1, p.key


def test_the_summary_never_says_the_workloads_fail_for_separate_reasons():
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        summary = json.loads(ex.assistant)["summary"]
        assert propagation.SEPARATE_REASONS not in summary, p.key
        assert len([ln for ln in summary.split("\n") if ln.strip()]) <= c.MAX_SUMMARY_LINES


def _menu_blocks(ex):
    """The candidate section, split into one list of candidate lines per workload."""
    menu = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    blocks = []
    for line in menu.split("\n"):
        if line.startswith("- "):
            blocks.append([])
        elif line.strip().startswith("considered "):
            blocks[-1].append(line.strip()[len("considered "):])
    return blocks


def test_the_decoy_leads_every_candidate_menu_and_the_answer_trails():
    """Tag AND position both point away from the answer, on every workload.

    Three candidates per victim in a fixed order: the local decoy carrying
    `attributed` first, the evidence-refuted distractor second, the shared
    cause carrying `outranked` last. A model answering by index or by tag
    scores zero; a model reading the evidence is unaffected.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        blocks = _menu_blocks(ex)
        assert len(blocks) == len(p.victims), p.key
        cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
        for block, decoy in zip(blocks, ex.meta["decoy_causes"]):
            assert len(block) == 3, p.key
            assert block[0].startswith(f"{decoy}: attributed "), p.key
            assert block[1].startswith(f"{ex.meta['distractor_cause']}: ruled out "), p.key
            assert block[2].startswith(f"{cause}: outranked "), p.key


def test_the_shared_cause_is_a_candidate_line_on_every_workload():
    """Verbatim-matchable, which is what `score.evaluate` compares.

    The contract tells the model it may answer with "a candidate cause
    verbatim". Putting the shared cause on each menu keeps the correct answer
    inside that vocabulary, so a wrong answer is a judgement failure and never
    a phrasing one.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        menu = ex.user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
        cause = json.loads(ex.assistant)["verdicts"][0]["cause"]
        assert menu.count(f"considered {cause}: ") == len(p.victims), p.key


def test_the_origin_evidence_is_read_once_and_leads():
    """One shared cause means one read of the origin, not N copies of it.

    Restating the origin under every victim would make "the same sentence
    appears N times" a countable shortcut, which is the opposite of what this
    slice asks for.
    """
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        evidence = ex.user.split("== BEGIN evidence ==")[1].split("== END evidence ==")[0]
        labels = [ln for ln in evidence.split("\n") if ln.startswith("== ")]
        assert len(labels) == len(p.victims) + 1, p.key
        assert len(set(labels)) == len(labels), p.key
        first_line = p.origin_read[1].split("\n")[0].split("{")[0]
        assert evidence.count(first_line) == 1, p.key
        assert evidence.lstrip("\n").index(labels[0]) == 0, p.key


def test_meta_carries_every_local_decoy_so_the_scorer_can_see_tag_following():
    from kubeagent_verdict.dataset import cases, generate
    p = _first()
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    assert ex.meta["case"] == "shared_origin_probe"
    assert len(ex.meta["decoy_causes"]) == len(p.victims)
    for decoy in ex.meta["decoy_causes"]:
        assert decoy in ex.user
    assert ex.meta["origin"] == p.key
    assert ex.meta["blast_radius"] == p.blast_radius


def test_meta_names_the_memorised_summary_phrase_to_score_against():
    from kubeagent_verdict.dataset import cases, generate
    p = _first()
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    assert ex.meta["wrong_summary_phrase"] == propagation.SEPARATE_REASONS


def test_the_prompt_is_contract_valid():
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        assert ex.system == c.SYSTEM_PROMPT
        assert ex.user.endswith(c.CLOSING_INSTRUCTION)
        assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
        doc = json.loads(ex.assistant)
        assert set(doc) == {"verdicts", "summary"}
        assert 1 <= len(doc["verdicts"]) <= c.MAX_VERDICT_ROWS
        for row in doc["verdicts"]:
            assert row["confidence"] in c.CONFIDENCE_VALUES
            assert row["workload"] in ex.user


def test_a_pinned_scope_is_the_same_for_every_victim():
    from kubeagent_verdict.dataset import cases, generate
    for p in propagation.all_scenarios():
        if p.scope_field is None:
            continue
        ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
        assert ex.meta["scope_value"]
        assert ex.meta["scope_value"] in json.loads(ex.assistant)["verdicts"][0]["cause"]


def test_the_builder_is_deterministic():
    from kubeagent_verdict.dataset import cases, generate
    p = _first()
    a = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    b = cases.shared_origin_probe(p, generate._entry_rng("t", p.key))
    assert generate.to_row(a) == generate.to_row(b)


def test_a_subset_row_renders_fewer_victims_from_the_same_scenario():
    from kubeagent_verdict.dataset import cases, generate
    p = next(s for s in propagation.all_scenarios() if len(s.victims) >= 3)
    ex = cases.shared_origin_probe(p, generate._entry_rng("t", p.key), victims=2)
    assert len(json.loads(ex.assistant)["verdicts"]) == 2
