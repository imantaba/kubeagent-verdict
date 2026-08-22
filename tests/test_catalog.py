from pathlib import Path

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import catalog, corpus

DATA = Path(__file__).resolve().parent.parent / "data" / "corpus"

SAMPLE = {
    "ns": "shop", "name": "api", "pod": "api-7f9c4d5b6-x2x9k", "container": "app",
    "init_container": "init-config", "image": "registry.example.com/shop/api:v1.2.3",
    "node": "worker-2", "pvc": "data-0", "restarts": 14,
}


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
        assert e.issue and e.reason and e.evidence and e.next_step and e.command, e.key
        assert e.winner_cause and e.winner_reason and e.rationale, e.key
        assert e.reads, e.key
        assert e.contradiction and e.own_cause and e.own_cause_keywords, e.key
        for cause, verdict, reason in e.losers:
            assert verdict in {"ruled_out", "outranked"}, e.key
            assert cause and reason, e.key


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
        for tpl in (e.evidence, e.log_cause, e.next_step, e.command, e.winner_cause,
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
