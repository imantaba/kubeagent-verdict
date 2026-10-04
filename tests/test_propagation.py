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
import random
from dataclasses import replace

from kubeagent_verdict import contract as c
from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, generate, objects, propagation, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.dataset.objects import Fresh, Object


def test_victim_and_propagation_gain_the_declaration_fields():
    v = propagation.Victim(
        workload_kind="Deployment", status="Running", issue="ProbeFailure",
        reason="r", evidence="e", local_cause="c", local_reason="cr",
        read=("label", "content"),
    )
    assert v.on_origin is False
    assert v.objects == ()
    p = propagation.Propagation(
        key="t", blast_radius="node", scope_field="node", origin="o",
        shared_cause="sc", shared_reason="sr", distractor_cause="dc",
        distractor_reason="dr", rationale="ra", remedy="re", confidence="high",
        origin_read=("label", "content"), victims=(v,),
    )
    assert p.origin_object is None
    assert p.healthy_origin_fresh is None


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

    The local decoy leads and carries `attributed`, as in
    `multi_misattribution_probe`; here the shared cause trails. A slice
    where the tag happened to be right would measure nothing a passing
    `attributed` row does not.
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
        for v in p.victims:
            assert isinstance(v.network_policies, tuple), (
                f"{p.key}: network_policies must be a tuple, not "
                f"{type(v.network_policies).__name__} -- a bare str is truthy, "
                "survives the `or ()`, and would be joined character by "
                "character, so every pattern below would silently miss it")
        blob = "\n".join([p.origin, p.shared_cause, p.shared_reason, p.distractor_cause,
                          p.distractor_reason, p.rationale, p.remedy,
                          p.origin_read[0], p.origin_read[1],
                          p.healthy_origin_content, p.notes]
                         + [f"{v.reason}\n{v.evidence}\n{v.log_cause}\n{v.local_cause}\n"
                            f"{v.local_reason}\n"
                            f"{v.read[0]}\n{v.read[1]}\n{v.healthy_read_content}\n"
                            + "\n".join(str(x) for x in (v.network_policies or ()))
                            for v in p.victims])
        for pat in banned:
            assert not pat.search(blob), f"{p.key}: {pat.pattern}"


# ---------------------------------------------------------------- the builder
#
# Spec 4b-1: the shared-origin family is built from `stories.Story` through
# the real pipeline, so the tests below read the rows a story produces and
# the lines a model sees. `propagation` is still the source of `multi`'s
# scenarios, which is why the data tests above stay.


def _probe(st, **kw):
    return cases.shared_origin_probe(st, generate._entry_rng("t", st.key), **kw)


def _built(st, world, width=None, seed=7):
    d = so.draw(st, random.Random(seed), width=width or len(st.victims))
    return so.build(st, d, world=world)


def _candidate_blocks(user):
    """The candidate section, split into one block of lines per workload."""
    menu = user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    blocks, key = {}, None
    for line in menu.split("\n"):
        if line.startswith("- "):
            key = line[2:].split(" (")[0]
            blocks[key] = []
        elif key is not None:
            blocks[key].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


def test_builder_renders_one_verdict_row_per_victim():
    """One verdict per flagged workload: the victims, plus the origin's own
    row when the broken world has one (`coredns-down` lists kube-system/coredns)."""
    for st in stories.exam():
        rows = json.loads(_probe(st).assistant)["verdicts"]
        extra = 1 if st.broken.origin_row is not None else 0
        assert len(rows) == len(st.victims) + extra, st.key
        assert len({r["workload"] for r in rows}) == len(rows), st.key


def test_every_row_names_the_same_shared_cause():
    """The whole point, on a ruled exam story: the rules confirmed one cause
    group on every victim.

    A node story and a registry story bind one name, so the cause string is
    identical on every victim. A PVC story binds one claim per victim, so the
    strings differ and every one names a PVC. The plain exam stories make no
    such promise: their victims are named from their own lines, and the label
    follows the gold rule (two or more linked victims). The exam must still
    hold both labels, or this check proves nothing about either.
    """
    saw_shared = saw_none = False
    for st in stories.exam():
        ex = _probe(st)
        saw_shared |= ex.meta["label"] == "shared"
        saw_none |= ex.meta["label"] == "none"
        if st.cls != "R":
            continue
        verdicts = json.loads(ex.assistant)["verdicts"]
        assert ex.meta["label"] == "shared", st.key
        for v in verdicts:
            meta = ex.meta["workloads"][v["workload"]]
            assert meta["decided"] and meta["decided_outcome"] == "confirmed", st.key
        causes = {v["cause"] for v in verdicts}
        if st.origin_kind == "pvc":
            assert len(causes) >= 2, st.key
            assert all(cause.startswith("PVC ") for cause in causes), st.key
        else:
            assert len(causes) == 1, st.key
    assert saw_shared and saw_none, "both labels must be exercised"


def test_the_summary_never_says_the_workloads_fail_for_separate_reasons():
    """A broken world never calls its workloads separate: the rules either
    confirmed one cause ("share one upstream cause") or did not confirm it
    ("did not confirm one cause"). The phrase belongs to a healthy world only
    (Ruling 33), so only the broken probe is checked here."""
    for st in stories.exam():
        summary = json.loads(_probe(st).assistant)["summary"]
        assert propagation.SEPARATE_REASONS not in summary, st.key
        lines = [ln for ln in summary.split("\n") if ln.strip()]
        assert len(lines) <= c.MAX_SUMMARY_LINES, st.key


def test_the_shared_cause_is_a_candidate_line_on_every_workload():
    """The rules' cause is a candidate line on every workload it decides.

    The contract tells the model it may answer with "a candidate cause
    verbatim". When the rules confirm a cause, that cause is printed as a
    `considered` line in the workload's own block, so the right answer is
    inside the model's vocabulary and a wrong answer is a judgement failure,
    never a phrasing one. Read off the built rows and the printed section,
    not off a menu the test invented.
    """
    for st in stories.exam():
        if st.cls != "R":
            continue
        b = _built(st, "broken")
        blocks = _candidate_blocks(b.user)
        for row in b.rows:
            assert row.result.decided, (st.key, row.key)
            assert row.result.cause in {cd.cause for cd in row.candidates}, (st.key, row.key)
            assert f"considered {row.result.cause}: " in blocks[row.key], (st.key, row.key)


def test_the_origin_is_read_once_not_once_per_victim():
    """One shared cause means one read of the origin, not N copies of it.

    Restating the origin under every victim would make "the same sentence
    appears N times" a countable shortcut. The gather reads each node or
    claim once across the row, and prints each read once. (The old test also
    asked that the origin read come first. The real gather orders reads per
    workload, events then describe then log, so that half no longer holds and
    is not asserted.)
    """
    for st in stories.exam():
        b = _built(st, "broken")
        labels = [r.label for r in b.gathered.reads]
        assert len(set(labels)) == len(labels), st.key
        evidence = b.user.split("== BEGIN evidence ==")[1].split("== END evidence ==")[0]
        for label in labels:
            assert evidence.count(f"== {label} ==") == 1, (st.key, label)
        if st.cls == "R" and st.origin_kind == "node":
            node = [lb for lb in labels if lb.startswith("describe node ")]
            assert node == [f"describe node /{b.draw.scope_value}"], st.key


def test_meta_names_the_story_and_has_no_made_up_decoys():
    for st in stories.exam():
        ex = _probe(st)
        assert ex.meta["case"] == "shared_origin_probe", st.key
        assert ex.meta["origin"] == st.key
        assert ex.meta["blast_radius"] == st.blast_radius
        assert ex.meta["decoy_causes"] == [], st.key
        assert set(ex.meta["decoy_by_workload"]) == set(ex.meta["workloads"]), st.key
        for decoys in ex.meta["decoy_by_workload"].values():
            for decoy in decoys:
                assert decoy in ex.user, (st.key, decoy)


def test_meta_drops_the_keys_the_made_up_menu_needed():
    """`origin_read_label`, `distractor_cause`, `wrong_summary_phrase` and
    `expected_confidence` described the invented origin read, the invented
    distractor and the old per-story confidence. The new rows have none of
    them (Ruling 8), on any of the four cases."""
    st = stories.by_key()["node-not-ready"]
    for build in (cases.shared_origin, cases.shared_origin_decoy,
                  cases.shared_origin_probe, cases.shared_origin_decoy_probe):
        meta = build(st, random.Random(3)).meta
        for gone in ("origin_read_label", "distractor_cause", "wrong_summary_phrase",
                     "expected_confidence"):
            assert gone not in meta, (build.__name__, gone)


def test_the_prompt_is_contract_valid():
    for st in stories.exam():
        ex = _probe(st)
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
    for st in stories.exam():
        if not st.scope_field:
            continue
        b = _built(st, "broken")
        scope = b.draw.scope_value
        assert scope, st.key
        pinned = [n.node if st.scope_field == "node" else n.ns for n in b.draw.victims]
        assert pinned == [scope] * len(pinned), st.key
        ex = _probe(st)
        assert ex.meta["scope_value"], st.key
        if st.cls == "R" and st.origin_kind == "node":
            causes = {v["cause"] for v in json.loads(ex.assistant)["verdicts"]}
            assert all(ex.meta["scope_value"] in cause for cause in causes), st.key


def test_the_builder_is_deterministic():
    for st in stories.exam():
        a = _probe(st)
        b = _probe(st)
        assert generate.to_row(a) == generate.to_row(b), st.key


def test_a_subset_row_renders_fewer_victims_from_the_same_scenario():
    st = next(s for s in stories.exam() if len(s.victims) >= 3)
    ex = _probe(st, victims=2)
    extra = 1 if st.broken.origin_row is not None else 0
    assert len(json.loads(ex.assistant)["verdicts"]) == 2 + extra
    assert ex.group.count("propagation:") == 2


def test_the_eval_six_declare_no_variants_and_no_state():
    """The exam is frozen this slice.

    `origin_variants` and `origin_state` are trainable-pool fields. Populating
    them on an eval scenario would change what the exam renders and void every
    banked scoreboard; the draw in `_render_shared_origin` is guarded on the
    field being non-empty precisely so the six consume the same RNG they always
    have. The eval six are asked, not taught.
    """
    for p in propagation.all_scenarios():
        assert p.origin_variants == (), p.key
        assert p.origin_state == ("", ""), p.key


def test_the_shared_scenarios_declare_an_origin_object():
    by_key = {p.key: p for p in propagation.all_scenarios()}

    node_lost = by_key["node-not-ready"]
    assert node_lost.origin_object == Object(
        kind="node", name="{node}", scan_reason="NotReady", placement="on",
        fresh=Fresh(ready="False"), intent="cause")
    assert node_lost.healthy_origin_fresh == Fresh(ready="True")

    storage = by_key["storage-provisioner-down"]
    assert storage.origin_object == Object(
        kind="pvc", name="{pvc}", scan_reason="ProvisionerNotResponding",
        placement="mounted",
        fresh=Fresh(phase="Pending", storage_class="standard"), intent="cause")
    assert storage.healthy_origin_fresh == Fresh(phase="Bound", storage_class="standard")

    registry = by_key["registry-unreachable"]
    assert registry.origin_object == Object(
        kind="registry", name="registry.example.com", scan_reason="3", placement="",
        fresh=Fresh(literal="dial tcp"), intent="cause")
    assert registry.healthy_origin_fresh == Fresh(literal="manifest unknown")

    for key in ("coredns-down", "node-disk-pressure", "networkpolicy-deny-all"):
        p = by_key[key]
        assert p.origin_object is None, key
        assert p.healthy_origin_fresh is None, key


def test_the_six_scenarios_declare_what_the_graft_table_says():
    by_key = {p.key: p for p in propagation.all_scenarios()}

    coredns = by_key["coredns-down"]
    names = [v.objects[0].name for v in coredns.victims]
    assert names == ["worker-1", "worker-2", "worker-3"]
    for v in coredns.victims:
        assert len(v.objects) == 1
        assert v.objects[0].kind == "node"
        assert v.objects[0].placement == "on"
        assert v.on_origin is False

    node_lost = by_key["node-not-ready"]
    v1, v2 = node_lost.victims
    assert v1.on_origin is True and v1.objects == ()
    assert v2.on_origin is True and v2.objects == ()

    storage = by_key["storage-provisioner-down"]
    sv1, sv2, sv3 = storage.victims
    assert sv1.on_origin is True and sv1.objects == ()
    assert sv2.on_origin is True and sv2.objects == ()
    assert sv3.on_origin is True and sv3.objects == ()

    registry = by_key["registry-unreachable"]
    for v in registry.victims:
        assert v.on_origin is True
        assert v.objects == ()

    disk = by_key["node-disk-pressure"]
    d1, d2, d3 = disk.victims
    assert [v.objects[0].placement for v in (d1, d2, d3)] == ["off", "on", "on"]
    for v in disk.victims:
        assert v.on_origin is False
        assert len(v.objects) == 1
        assert v.objects[0].kind == "node"
        assert v.objects[0].name == "{node}"

    netpol = by_key["networkpolicy-deny-all"]
    n1, n2 = netpol.victims
    assert n1.objects[0].name == "worker-1"
    assert n2.objects[0].name == "worker-2"
    for v in netpol.victims:
        assert v.on_origin is False
        assert len(v.objects) == 1
        assert v.objects[0].kind == "node"
        assert v.objects[0].placement == "on"


def test_every_scenario_object_passes_check_declaration():
    from kubeagent_verdict.dataset import rules

    for p in propagation.all_scenarios():
        origin_objects = (p.origin_object,) if p.origin_object is not None else ()
        rules.check_declaration(p.key, origin_objects)
        for i, v in enumerate(p.victims):
            rules.check_declaration(f"{p.key}/victim{i}", v.objects)


def test_victim_decoy_objects_declare_their_contents():
    """Every victim decoy is a node decoy, declared the same way."""
    for prop in propagation.all_scenarios():
        for i, v in enumerate(prop.victims, 1):
            for obj in v.objects:
                where = f"{prop.key}/victim{i}/{obj.kind}:{obj.name}"
                assert obj.intent == "decoy", where
                assert obj.kind == "node", where
                assert obj.scan_reason == "NotReady", where
                assert obj.fresh.how == "read", where
    # A victim decoy's declared `fresh` never reaches a prompt: every node
    # ending replaces it. Pin that, so the comment above `objects` stays true.
    for ending in ("lease", "read_failed"):
        sample = propagation.by_key()["coredns-down"].victims[0].objects[0]
        assert objects.unverify(sample, ending).fresh != sample.fresh, ending
    sample = propagation.by_key()["coredns-down"].victims[0].objects[0]
    assert objects.refute(sample).fresh.ready == "True"
    # `kind`, `name` and `placement` are the only declared values every ending
    # keeps. Pin all three endings, so the comment above `objects` stays true.
    for drawn in (objects.refute(sample), objects.unverify(sample, "lease"),
                  objects.unverify(sample, "read_failed")):
        assert (drawn.kind, drawn.name, drawn.placement) == (
            sample.kind, sample.name, sample.placement)
    # `scan_reason` is a placeholder under two of the three endings. Declare a
    # different one, so the check cannot pass by coincidence.
    probe = replace(sample, scan_reason="kubelet not heartbeating")
    assert objects.refute(probe).scan_reason == "NotReady"
    assert objects.unverify(probe, "lease").scan_reason == "no kubelet lease"
    assert objects.unverify(probe, "read_failed").scan_reason == (
        "kubelet not heartbeating")


def test_shared_origin_meta_is_derived_from_the_rules_not_declared():
    """R21: job/decided_* meta for a shared-origin victim comes from the rules
    pass over the built world, not from a hand-set 'job: 1' literal."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin(st, random.Random(7), victims=2)
    b = _built(st, "broken", width=2)

    metas = ex.meta["workloads"]
    assert len(metas) == 2
    for row in b.rows:
        meta = metas[row.key]
        assert set(meta) == {
            "job", "decided", "decided_cause", "decided_outcome",
            "decided_evidence", "expected_cause", "own_cause_keywords",
            "own_cause_must_not"}
        # Shared-origin keys come from stories, not from a catalog entry,
        # so there are no must-not words.
        assert meta["own_cause_must_not"] == []
        assert meta["job"] == 1
        assert meta["decided"] is True
        assert meta["decided_outcome"] == "confirmed"
        assert meta["decided_cause"] == row.result.cause
        assert meta["decided_evidence"] == row.result.evidence
    assert ex.meta["label"] in ("shared", "none")
    assert set(ex.meta["decoy_by_workload"]) == set(metas)


def test_shared_origin_decoy_meta_is_not_decided_when_healthy():
    """The healthy world has the origin fixed; no victim is confirmed on it,
    so the rules decide none of them and every workload is graded on job 2."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_decoy(st, random.Random(7), victims=2)

    assert len(ex.meta["workloads"]) == 2
    for meta in ex.meta["workloads"].values():
        assert meta["decided"] is False
        assert meta["job"] == 2
    assert ex.meta["label"] == "none"


def test_registry_unreachable_shared_read_agrees_with_the_decision():
    """The registry-events consistency rule: the rules decide a registry from
    the pulling pod's own events, so the broken world must print a connection
    error there and the healthy world must not."""
    st = stories.by_key()["registry-unreachable"]
    broken = _built(st, "broken", width=2)
    healthy = _built(st, "healthy", width=2)

    for row in broken.rows:
        assert row.result.decided, row.key
        assert row.result.outcome == "confirmed", row.key
    assert not any(row.result.decided for row in healthy.rows)

    def pull_events(built):
        return [r.content.lower() for r in built.gathered.reads if r.label.startswith("events ")]

    for text in pull_events(broken):
        assert any(lit in text for lit in objects.CONNECTION_LITERALS), text
    for text in pull_events(healthy):
        assert not any(lit in text for lit in objects.CONNECTION_LITERALS), text


def test_registry_count_template_fills_in_the_rendered_victim_count():
    """A registry cause counts the workloads the row renders (spec section 4,
    "Registry count"): 2 victims say 2 and 3 victims say 3. This is the fix
    for the bug the exam's row 252 disclosed, where a count fixed in the data
    stayed "3" on a row that showed only 2 victims, so the rules pass's own
    cause line claimed more workloads than the row showed.

    Victim images always pull from `registry.example.com`, so that is the host
    the cause names, and no other host is printed.
    """
    st = stories.by_key()["registry-unreachable"]
    assert len(st.victims) >= 3

    two = cases.shared_origin(st, random.Random(1), victims=2)
    assert "registry registry.example.com (2 workloads failing to pull)" in two.user
    assert "(3 workloads failing to pull)" not in two.user

    three = cases.shared_origin(st, random.Random(1), victims=3)
    assert "registry registry.example.com (3 workloads failing to pull)" in three.user
    assert "(2 workloads failing to pull)" not in three.user

    for row in _built(st, "broken", width=3).rows:
        assert row.names.image.startswith("registry.example.com/"), row.key


def test_shared_origin_wrappers_merge_the_new_meta_without_losing_existing_keys():
    """The four thin wrappers share one meta builder: each keeps the keys it
    writes today and gains 'workloads', 'label' and 'decoy_by_workload'. The
    four keys the made-up menu needed are gone (Ruling 8)."""
    st = stories.by_key()["node-not-ready"]
    common = ("workloads", "label", "decoy_by_workload", "case", "origin", "blast_radius",
              "scope_value", "expected", "decoy_causes")

    for build in (cases.shared_origin, cases.shared_origin_decoy,
                  cases.shared_origin_probe, cases.shared_origin_decoy_probe):
        meta = build(st, random.Random(3)).meta
        for key in common:
            assert key in meta, (build.__name__, key)
        assert meta["decoy_causes"] == [], build.__name__

    probe = cases.shared_origin_decoy_probe(st, random.Random(3))
    phrases = probe.meta["shared_claim_phrases"]
    assert phrases and all(isinstance(p, str) and p for p in phrases)
    for build in (cases.shared_origin, cases.shared_origin_decoy, cases.shared_origin_probe):
        assert "shared_claim_phrases" not in build(st, random.Random(3)).meta, build.__name__
