from pathlib import Path

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import catalog, corpus

DATA = Path(__file__).resolve().parent.parent / "data" / "corpus"

SAMPLE = {
    "ns": "shop", "name": "api", "pod": "api-7f9c4d5b6-x2x9k", "container": "app",
    "init_container": "init-config", "image": "registry.example.com/shop/api:v1.2.3",
    "node": "worker-2", "pvc": "data-0", "restarts": 14,
}


def test_catalog_entry_objects_field_defaults_to_empty():
    e = catalog.CatalogEntry(key="t", covered_slugs=(), covered_kinds=(), trains=False)
    assert e.objects == ()


def test_entries_slugs_declare_their_objects():
    from kubeagent_verdict.dataset.objects import Fresh, Object

    expected = {
        "memory-limit-oomkill": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=Fresh(ready="False"), intent="decoy"),
        ),
        "deployment-bad-image-tag": (
            Object(kind="registry", name="registry.example.com", scan_reason="2",
                   placement="", fresh=Fresh(literal="dial tcp"), intent="decoy"),
        ),
        "node-cordon-diskfull": (
            Object(kind="node", name="{node}", scan_reason="no kubelet lease",
                   placement="on", fresh=Fresh(ready="True"), intent="decoy"),
        ),
        "networkpolicy-deny-all": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=Fresh(ready="False"), intent="decoy"),
        ),
        "coredns-corefile-broken": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=Fresh(ready="False"), intent="decoy"),
        ),
        "worker-containerd-stop": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=Fresh(ready="False"), intent="cause"),
            Object(kind="pvc", name="{pvc}", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0947"),
                   intent="decoy"),
        ),
        "oversized-job-unschedulable": (
            Object(kind="pvc", name="{pvc}", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0821"),
                   intent="decoy"),
        ),
        "crashloop-pod": (
            Object(kind="node", name="{node}", scan_reason="NotReady", placement="on",
                   fresh=Fresh(ready="False"), intent="decoy"),
        ),
    }
    by_key = {e.key: e.objects for e in catalog.all_entries()}
    for key, objects in expected.items():
        assert by_key[key] == objects, key


def test_entries_kinds_declare_their_objects():
    from kubeagent_verdict.dataset.objects import Fresh, Object

    node_decoy = Object(kind="node", name="{node}", scan_reason="NotReady",
                         placement="on", fresh=Fresh(ready="False"), intent="decoy")
    expected = {
        "probe-failure": (node_decoy,),
        "container-start-error": (node_decoy,),
        "create-container-config-error": (
            Object(kind="pvc", name="{pvc}", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0442"),
                   intent="decoy"),
        ),
        "init-crashloop": (node_decoy,),
        "init-config-error": (node_decoy,),
        "init-errimagepull": (node_decoy,),
        "init-imagepullbackoff": (node_decoy,),
        "init-oomkilled": (node_decoy,),
        "restart-loop": (node_decoy,),
        "volume-attach-error": (
            Object(kind="pvc", name="aux-0", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0821"),
                   intent="decoy"),
        ),
        "volume-mount-error": (
            Object(kind="pvc", name="aux-1", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0821"),
                   intent="decoy"),
        ),
    }
    by_key = {e.key: e.objects for e in catalog.all_entries()}
    for key, objects in expected.items():
        assert by_key[key] == objects, key


def test_19_entries_declare_an_object_and_9_declare_none():
    entries = catalog.all_entries()
    assert len(entries) == 28
    with_objects = {e.key for e in entries if e.objects}
    without_objects = {e.key for e in entries if not e.objects}
    assert len(with_objects) == 19
    assert len(without_objects) == 9
    assert with_objects.isdisjoint(without_objects)
    assert with_objects | without_objects == {e.key for e in entries}


def test_worker_containerd_stop_declares_its_cause_node_and_a_decoy_pvc():
    entry = next(e for e in catalog.all_entries() if e.key == "worker-containerd-stop")
    assert len(entry.objects) == 2
    assert {o.kind for o in entry.objects} == {"node", "pvc"}
    assert {o.intent for o in entry.objects} == {"cause", "decoy"}


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


def test_28_entries_unique_keys():
    entries = catalog.all_entries()
    assert len(entries) == 28
    assert len({e.key for e in entries}) == 28


def test_trainable_entries_are_complete():
    for e in catalog.trainable():
        assert e.issue and e.reason and e.evidence and e.recommendation, e.key
        assert e.winner_cause and e.winner_reason and e.rationale, e.key
        assert e.reads, e.key
        assert e.contradiction and e.own_cause and e.own_cause_keywords, e.key
        for cause, verdict, reason in e.losers:
            assert verdict in {"ruled_out", "outranked"}, e.key
            assert cause and reason, e.key


def test_own_cause_keywords_are_satisfied_by_their_own_cause():
    """The answer key must be able to score its own reference answer.

    `evals/score.py` grades the `own_cause` and `empty_candidates` slices with
    `all(k in cause for k in own_cause_keywords)`. A keyword the entry's own
    `own_cause` text does not contain makes that conjunction unsatisfiable: the
    ground truth itself scores zero, and so does every model, however good. A
    rate built from such a row measures the catalog, not the model.
    """
    broken = {}
    for e in catalog.trainable():
        cause = e.own_cause.format(**SAMPLE).lower()
        missing = [k for k in e.own_cause_keywords if k.lower() not in cause]
        if missing:
            broken[e.key] = (missing, cause)
    assert not broken, "keywords absent from their own expected cause: " + "; ".join(
        f"{k}: {m} not in {c!r}" for k, (m, c) in sorted(broken.items()))


def test_own_cause_keywords_are_discriminating():
    """Two keywords minimum, so the check cannot pass on one common word."""
    for e in catalog.trainable():
        assert len(e.own_cause_keywords) >= 2, e.key


def test_untrainable_entries_say_why():
    for e in catalog.all_entries():
        if not e.trains:
            assert e.notes, f"{e.key}: trains=False needs a notes sentence"


def test_read_labels_match_kubeagent_shapes():
    ok = ("events ", "describe node /", "describe pvc ", "log causes ")
    for e in catalog.trainable():
        for label, _content in e.reads:
            rendered = label.format(**SAMPLE)
            assert rendered.startswith(ok), f"{e.key}: {rendered!r}"


def test_templates_resolve_with_sample_names():
    for e in catalog.trainable():
        for tpl in (e.evidence, e.log_cause, e.recommendation, e.winner_cause,
                    e.winner_reason, e.rationale, e.contradiction, e.own_cause):
            tpl.format(**SAMPLE)
        for cause, _v, reason in e.losers:
            cause.format(**SAMPLE)
            reason.format(**SAMPLE)
        for label, content in e.reads:
            label.format(**SAMPLE)
            content.format(**SAMPLE)


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
    assert e.evidence.format(**SAMPLE).startswith('container "app", 14 restarts, ')
