import json
import re

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import generate

BANNED = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),  # any dotted-quad IP
    re.compile(r"https?://"),
    re.compile(r"kubeconfig", re.IGNORECASE),
    re.compile(r"/home/"),
    re.compile(r"@"),
)


def test_generate_is_deterministic():
    a = generate.generate(seed=17, size=40)
    b = generate.generate(seed=17, size=40)
    assert [generate.to_row(x) for x in a] == [generate.to_row(y) for y in b]
    assert a != generate.generate(seed=18, size=40)


def test_provenance_no_banned_text():
    for ex in generate.generate(seed=17, size=60):
        blob = ex.user + "\n" + ex.assistant
        for pat in BANNED:
            assert not pat.search(blob), f"{ex.meta}: {pat.pattern}"


def test_every_example_is_contract_valid():
    for ex in generate.generate(seed=17, size=60):
        assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
        assert ex.system == c.SYSTEM_PROMPT
        doc = json.loads(ex.assistant)
        assert set(doc) == {"verdicts", "summary"}
        assert 1 <= len(doc["verdicts"]) <= c.MAX_VERDICT_ROWS
        for row in doc["verdicts"]:
            assert row["confidence"] in c.CONFIDENCE_VALUES
            assert re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", row["workload"])
            assert row["workload"] in ex.user
        lines = [ln for ln in doc["summary"].split("\n") if ln.strip()]
        assert 1 <= len(lines) <= c.MAX_SUMMARY_LINES


def test_to_row_schema():
    (ex,) = generate.generate(seed=17, size=1)
    row = generate.to_row(ex)
    assert set(row) == {"messages", "meta"}
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]


def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 400, "none_of_these": 150, "own_cause": 100,
                      "multi": 150, "truncated": 50, "injection": 100,
                      "empty_candidates": 50}
    assert sum(generate.counts_for(997).values()) == 997  # remainder lands on attributed


def test_case_mix_present_in_generated_set():
    exs = generate.generate(seed=17, size=200)
    seen = {ex.case for ex in exs}
    assert seen == {"attributed", "none_of_these", "own_cause", "multi",
                    "truncated", "injection", "empty_candidates"}


def test_split_never_straddles_a_group():
    exs = generate.generate(seed=17, size=300)
    train, val = generate.split(exs, seed=17)
    train_groups = {ex.group for ex in train}
    val_groups = {ex.group for ex in val}
    assert not (train_groups & val_groups)
    frac = len(val) / (len(train) + len(val))
    assert 0.04 <= frac <= 0.20


def test_corpus_test_set_derives_from_committed_rows():
    exs = generate.corpus_test_set()
    assert exs, "no corpus-derived test examples"
    for ex in exs:
        assert ex.meta["source"]["fault"]
        assert ex.meta["source"]["distro"] in {"kind", "k3s"}


def test_drop_held_out_removes_colliding_groups():
    exs = generate.generate(seed=17, size=60)
    fake_test = [exs[0]]  # pretend the first example's group is a test fixture
    kept = generate.drop_held_out(exs, fake_test)
    assert exs[0].group not in {ex.group for ex in kept}
    assert len(kept) < len(exs)
