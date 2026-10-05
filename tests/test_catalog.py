from pathlib import Path

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import catalog, corpus

DATA = Path(__file__).resolve().parent.parent / "data" / "corpus"

SAMPLE = {
    "ns": "shop", "name": "api", "pod": "api-7f9c4d5b6-x2x9k", "container": "app",
    "init_container": "init-config", "image": "registry.example.com/shop/api:v1.2.3",
    "node": "worker-2", "pvc": "data-0", "restarts": 14, "nodes": 3,
}
# 2026-10-05 (Spec 4b-3): the fill also gives {other_nodes}, nodes minus 1.
FILL = {**SAMPLE, "other_nodes": 2}


def test_catalog_entry_objects_field_defaults_to_empty():
    e = catalog.CatalogEntry(key="t", covered_slugs=(), covered_kinds=(), trains=False)
    assert e.objects == ()


# The shared Ready=False text every NotReady node object carries: the
# kubelet's own reason and message when the container runtime is down
# (kubelet pkg/kubelet/runtime.go:129). Written out here, not imported, so
# a change to the constant fails these pins.
def _not_ready():
    from kubeagent_verdict.dataset.objects import Fresh

    return Fresh(ready="False", ready_reason="KubeletNotReady",
                 ready_message="container runtime is down")


def _node_decoy():
    from kubeagent_verdict.dataset.objects import Object

    return Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                  fresh=_not_ready(), intent="decoy")


def test_entries_slugs_declare_their_objects():
    from kubeagent_verdict.dataset.objects import Fresh, Object

    expected = {
        "memory-limit-oomkill": (_node_decoy(),),
        "deployment-bad-image-tag": (
            Object(kind="registry", name="registry.example.com", scan_reason="2",
                   placement="", fresh=Fresh(literal="dial tcp"), intent="decoy"),
        ),
        # Cordoned, under disk pressure and still Ready, with the two
        # NoSchedule taints the node lifecycle controller adds for those.
        # 2026-09-26 (faithful prompts): the pod is unscheduled, so no pod
        # of the workload is on the node, and the rules rule it out. on -> off
        "node-cordon-diskfull": (
            Object(kind="node", name="{node}", scan_reason="no kubelet lease",
                   placement="off",
                   fresh=Fresh(ready="True", unschedulable=True, disk_pressure=True,
                               taints=(("node.kubernetes.io/unschedulable", "", "NoSchedule"),
                                       ("node.kubernetes.io/disk-pressure", "", "NoSchedule"))),
                   intent="decoy"),
        ),
        "networkpolicy-deny-all": (_node_decoy(),),
        "coredns-corefile-broken": (_node_decoy(),),
        "worker-containerd-stop": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=_not_ready(), intent="cause"),
        ),
        # A Pending pod has no mounted claim to blame, so its decoy is a
        # node the pod is not placed on.
        "oversized-job-unschedulable": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="off",
                   fresh=_not_ready(), intent="decoy"),
        ),
        "crashloop-pod": (_node_decoy(),),
    }
    by_key = {e.key: e.objects for e in catalog.all_entries()}
    for key, objects in expected.items():
        assert by_key[key] == objects, key


def test_entries_kinds_declare_their_objects():
    from kubeagent_verdict.dataset.objects import Fresh, Object

    # A pod with a config or volume finding is past scheduling, so every
    # claim it mounts is Bound: a mounted, Pending PVC decoy cannot happen
    # there. Those three entries carry a node decoy instead.
    node_decoy = _node_decoy()
    expected = {
        "probe-failure": (node_decoy,),
        "container-start-error": (node_decoy,),
        "create-container-config-error": (node_decoy,),
        "init-crashloop": (node_decoy,),
        "init-config-error": (node_decoy,),
        "init-errimagepull": (node_decoy,),
        "init-imagepullbackoff": (node_decoy,),
        "init-oomkilled": (node_decoy,),
        "restart-loop": (node_decoy,),
        "volume-attach-error": (node_decoy,),
        "volume-mount-error": (node_decoy,),
        # A pod waiting to schedule on an unbound claim: the claim is the
        # cause, mounted by the pod and still Pending.
        "pvc-unbound-unschedulable": (
            Object(kind="pvc", name="{pvc}", scan_reason="MissingStorageClass",
                   placement="mounted", fresh=Fresh(phase="Pending", storage_class="fast-ssd"),
                   intent="cause"),
        ),
    }
    by_key = {e.key: e.objects for e in catalog.all_entries()}
    for key, objects in expected.items():
        assert by_key[key] == objects, key


def test_20_entries_declare_an_object_and_9_declare_none():
    entries = catalog.all_entries()
    # 2026-09-26 (faithful prompts): pvc-unbound-unschedulable is new. 28 -> 29
    assert len(entries) == 29
    with_objects = {e.key for e in entries if e.objects}
    without_objects = {e.key for e in entries if not e.objects}
    # 2026-09-26 (faithful prompts): pvc-unbound-unschedulable declares one. 19 -> 20
    assert len(with_objects) == 20
    assert len(without_objects) == 9
    assert with_objects.isdisjoint(without_objects)
    assert with_objects | without_objects == {e.key for e in entries}


def test_worker_containerd_stop_declares_only_its_cause_node():
    entry = next(e for e in catalog.all_entries() if e.key == "worker-containerd-stop")
    assert [(o.kind, o.intent) for o in entry.objects] == [("node", "cause")]


def test_every_producing_entry_declares_exactly_one_object():
    for e in catalog.all_entries():
        assert len(e.objects) in (0, 1), e.key


def test_every_declared_catalog_object_passes_check_declaration():
    from kubeagent_verdict.dataset import rules

    for e in catalog.all_entries():
        rules.check_declaration(e.key, e.objects)


def test_every_slug_covered_exactly_once():
    count = {s: 0 for s in vocab.FAULT_SLUGS}
    for e in catalog.all_entries():
        for s in e.covered_slugs:
            count[s] += 1
    assert all(v == 1 for v in count.values()), count


def test_every_kind_covered_exactly_once():
    count = {k: 0 for k in vocab.ISSUE_KINDS}
    for e in catalog.all_entries():
        for k in e.covered_kinds:
            count[k] += 1
    assert all(v == 1 for v in count.values()), count


def test_29_entries_unique_keys():
    entries = catalog.all_entries()
    # 2026-09-26 (faithful prompts): pvc-unbound-unschedulable is new. 28 -> 29
    assert len(entries) == 29
    assert len({e.key for e in entries}) == 29


def test_trainable_entries_are_complete():
    # A job-1 row takes its cause from the rules, and the prompt's events
    # come from `events`, so these are all a trainable entry needs.
    for e in catalog.trainable():
        assert e.issue and e.reason and e.evidence and e.recommendation, e.key
        assert e.events, e.key
        # 2026-10-04 (Spec 4b-2): the kit and the none phrase replace the
        # old rationale, own_cause and own_cause_keywords.
        assert e.answer and e.none_phrase, e.key


# The six fields no builder reads any more. The rules give a row its cause
# and its candidates, and the events read comes from `events` and
# `contradiction_events`. `degraded` has been dead since the cluster-health
# block started to follow the row itself.
GONE = ("contradiction", "winner_cause", "winner_reason", "losers", "reads", "degraded")


def test_the_old_fields_are_gone():
    import dataclasses

    fields = {f.name for f in dataclasses.fields(catalog.CatalogEntry)}
    assert fields.isdisjoint(GONE), sorted(fields & set(GONE))
    assert "contradiction_events" in fields


# The job-1 entries whose contradiction_probe row adds event lines. Every
# job-1 entry but two: worker-containerd-stop's lease ending already prints
# its node Ready=True, and pvc-unbound-unschedulable never had a
# contradicting line.
CONTRADICTION_EVENT_KEYS = (
    "memory-limit-oomkill", "networkpolicy-deny-all", "coredns-corefile-broken",
    "crashloop-pod", "probe-failure", "container-start-error",
    "create-container-config-error", "init-crashloop", "init-config-error",
    "init-errimagepull", "init-imagepullbackoff", "init-oomkilled", "restart-loop",
    "volume-attach-error", "volume-mount-error",
)


def test_contradiction_events_are_on_exactly_the_15():
    have = tuple(e.key for e in catalog.all_entries() if e.contradiction_events)
    assert have == CONTRADICTION_EVENT_KEYS
    assert len(have) == 15
    assert set(have) <= {e.key for e in catalog.job1_entries()}


def test_contradiction_events_have_the_events_shape():
    """Same shape as `events`: (reason, message, count). A count is an int,
    or a template that formats to one."""
    for e in catalog.all_entries():
        for reason, message, count in e.contradiction_events:
            assert reason.format(**FILL) and message.format(**FILL), e.key
            if isinstance(count, str):
                assert int(count.format(**FILL)) > 0, e.key
            else:
                assert isinstance(count, int) and count > 0, e.key


def test_kit_keys_are_satisfied_by_their_own_cause():
    """The answer key must be able to score its own reference answer.

    `evals/score.py` grades the `own_cause` and `empty_candidates` slices with
    `all(k in cause for k in keys)`. A key the kit's own cause text does not
    contain makes that conjunction unsatisfiable: the ground truth itself
    scores zero, and so does every model, however good. A rate built from
    such a row measures the catalog, not the model.
    2026-10-04 (Spec 4b-2): `stories.Answer` checks this at import too; this
    keeps the grader's view.
    """
    broken = {}
    for e in catalog.trainable():
        cause = e.answer.cause.format(**FILL).lower()
        missing = [k for k in e.answer.keys if k.lower() not in cause]
        if missing:
            broken[e.key] = (missing, cause)
    assert not broken, "keywords absent from their own expected cause: " + "; ".join(
        f"{k}: {m} not in {c!r}" for k, (m, c) in sorted(broken.items()))


def test_kit_keys_are_discriminating():
    """Two keywords minimum, so the check cannot pass on one common word."""
    for e in catalog.trainable():
        assert len(e.answer.keys) >= 2, e.key


def test_untrainable_entries_say_why():
    for e in catalog.all_entries():
        if not e.trains:
            assert e.notes, f"{e.key}: trains=False needs a notes sentence"


def test_read_labels_match_kubeagent_shapes():
    """The gather writes every read label now, so check the labels it
    writes for each trainable entry's declared objects."""
    ok = ("events ", "describe node /", "describe pvc ", "log causes ")
    for e in catalog.trainable():
        _candidates, _result, reads = _single_row(e)
        assert reads, e.key
        for read in reads:
            assert read.label.startswith(ok), f"{e.key}: {read.label!r}"


def test_templates_resolve_with_sample_names():
    for e in catalog.trainable():
        for tpl in (e.evidence, e.log_cause, e.recommendation, e.answer.anchor,
                    e.answer.cause, e.answer.rationale):
            tpl.format(**FILL)
        for reason, message, count in e.events + e.contradiction_events:
            reason.format(**FILL)
            message.format(**FILL)
            if isinstance(count, str):
                count.format(**FILL)


def test_grounding_substrings_appear_in_corpus():
    load = corpus.load_corpus(sorted(DATA.glob("chaos-corpus-*.jsonl")))
    for e in catalog.all_entries():
        if not e.grounding:
            continue
        for slug in e.covered_slugs:
            rows = [r for r in load.rows if r.fault == slug and not r.skipped]
            assert rows, f"{e.key}: no corpus row for {slug}"
            joined = "\n".join(a for r in rows for a in r.assertions)
            for g in e.grounding:
                assert g in joined, f"{e.key}: grounding {g!r} not in corpus assertions for {slug}"


def test_log_cause_carries_no_prefix():
    """The renderer adds `log cause: ` once (`contract._finding_block`), so a
    value that already starts with it prints `log cause: log cause: …`."""
    for e in catalog.all_entries():
        assert not e.log_cause.startswith("log cause"), e.key


def test_restart_loop_evidence_quotes_the_container():
    """kubeagent prints `container %q, %d restarts, …`
    (internal/diagnose/restartloop.go:47 at v1.24.0)."""
    e = next(e for e in catalog.all_entries() if e.key == "restart-loop")
    assert e.evidence.format(**FILL).startswith('container "app", 14 restarts, ')


# The 17 trainable entries the rules decide in a single-workload row, in
# `trainable()` order: 16 decided by a node, 1 by a PVC.
JOB1_KEYS = (
    "memory-limit-oomkill", "networkpolicy-deny-all", "coredns-corefile-broken",
    "worker-containerd-stop", "crashloop-pod", "probe-failure", "container-start-error",
    "create-container-config-error", "init-crashloop", "init-config-error",
    "init-errimagepull", "init-imagepullbackoff", "init-oomkilled", "restart-loop",
    "volume-attach-error", "volume-mount-error", "pvc-unbound-unschedulable",
)


def _single_row(e):
    """Run one entry's declared objects, as declared, through the gather."""
    from kubeagent_verdict.dataset import cases, gather, render
    from kubeagent_verdict.dataset.names import Names

    bound = tuple(render.bind(obj, SAMPLE) for obj in e.objects)
    res = gather.gather([cases.gather_workload(e, Names(**SAMPLE), bound)])
    (candidates,), (result,) = res.candidates, res.results
    return candidates, result, res.reads


def test_job1_entries_are_the_17_the_rules_decide():
    assert tuple(e.key for e in catalog.job1_entries()) == JOB1_KEYS
    decided = tuple(e.key for e in catalog.trainable() if _single_row(e)[1].decided)
    assert decided == JOB1_KEYS
    left_out = {e.key for e in catalog.trainable()} - set(JOB1_KEYS)
    assert left_out == {"deployment-bad-image-tag", "node-cordon-diskfull",
                        "oversized-job-unschedulable"}


def test_the_cordoned_node_is_ruled_out():
    """IS-10: node-cordon-diskfull's pod is unscheduled, so no pod of the
    workload is on its node, and the rules rule the node out."""
    e = next(e for e in catalog.all_entries() if e.key == "node-cordon-diskfull")
    (obj,) = e.objects
    assert obj.placement == "off"
    candidates, result, _reads = _single_row(e)
    assert [(cand.cause, cand.verdict) for cand in candidates] == [
        ("node worker-2 (no kubelet lease)", "ruled_out")]
    assert not result.decided


def test_the_unbound_claim_entry():
    e = next(e for e in catalog.all_entries() if e.key == "pvc-unbound-unschedulable")
    # 2026-10-05 (Spec 4b-3): the node count is the {nodes} template field (was 3).
    message = ("0/{nodes} nodes are available: pod has unbound immediate PersistentVolumeClaims. "
               "preemption: 0/{nodes} nodes are available: {nodes} Preemption is not helpful for "
               "scheduling.")
    assert (e.covered_slugs, e.covered_kinds, e.trains) == ((), (), True)
    assert (e.workload_kind, e.status) == ("Deployment", "Degraded")
    assert (e.issue, e.reason, e.evidence) == (
        "Unschedulable", "No node can schedule this pod", message)
    # The pod's own event: kubeagent reads events by the pod's name, and the
    # claim's ProvisioningFailed event names the claim, not the pod.
    assert e.events == (("FailedScheduling", message, 5),)
    assert e.answer.cause == ("a claim the pod mounts is still waiting for its volume to be "
                              "provisioned")
    assert e.answer.keys == ("claim", "volume")
    assert e.answer.confidence == "high"
    assert e.contradiction_events == ()
    # The last entry of the catalog, so every other entry keeps its place.
    assert catalog.all_entries()[-1] is e
    assert catalog.trainable()[-1] is e


def test_the_unbound_claim_decides_confirmed_in_a_single_row():
    e = next(e for e in catalog.all_entries() if e.key == "pvc-unbound-unschedulable")
    candidates, result, reads = _single_row(e)
    assert [(cand.cause, cand.verdict, cand.fresh_read_outcome) for cand in candidates] == [
        ("PVC data-0 (MissingStorageClass)", "attributed", "confirmed")]
    assert (result.decided, result.cause, result.outcome) == (
        True, "PVC data-0 (MissingStorageClass)", "confirmed")
    assert [r.label for r in reads] == ["events shop/api-7f9c4d5b6-x2x9k",
                                         "describe pvc shop/data-0"]


def test_no_entry_names_a_pad_pvc():
    from kubeagent_verdict.dataset import names

    for e in catalog.all_entries():
        for obj in e.objects:
            assert obj.name.format(**FILL) not in names.PAD_PVCS, e.key
