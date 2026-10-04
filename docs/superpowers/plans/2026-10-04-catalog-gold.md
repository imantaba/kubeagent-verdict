# Catalog Gold (Spec 4b-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every named catalog gold rests on an anchor in the workload's own lines, says only facts the prompt shows, and carries the kit's confidence; rules-decided rows are high.

**Architecture:** Each trainable `CatalogEntry` gets an answer kit (`stories.Answer` plus a `none_phrase`), the same type the shared-origin stories use. One helper in `cases.py`, `_entry_gold`, applies the 4b-1 gold rule to an undecided catalog workload: it names the kit's cause only when the kit's anchor is in the workload's anchor lines, and otherwise answers `none_of_these`. The four builders that answer an entry's own cause call it. The old fields (`own_cause`, `own_cause_keywords`, `rationale`, `direct`) and `_confidence` are deleted.

**Tech Stack:** Python 3, pytest, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-04-catalog-gold-design.md` (approved, commit 7b1e831). Read it with this plan.

## Global Constraints

- Repo: `/home/ubuntu/git/kubeagent-verdict`, branch `spec4b2-catalog-gold`. The shell's cwd resets on every call: start each command with `cd /home/ubuntu/git/kubeagent-verdict &&`.
- PYTEST = `env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`. The full suite is 1912 passed at the branch base (about 77 s).
- Lint: `.venv/bin/ruff check --ignore EXE002 .` must print `All checks passed!`. Line length is 100.
- COMMIT = `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "..."`. No `Co-Authored-By` trailer and no AI attribution of any kind, anywhere.
- Stage files by name. Never `git add -A` or `git add .`. Never commit `.gitignore` or `train-v2.log`. Never run `git config`.
- Never run any test with `-update`. Re-pin by hand, with a dated comment `# 2026-10-04 (Spec 4b-2): …` that says what moved the pin and gives the old value.
- Bars never move: 0.9 / 0.7 / 0.9, FLOOR, BALANCE 0.10, CEILING 0.30, LABEL_CUE, 0.40 / 5, 0.12 / 0.30.
- Never touch existing `out/` folders (reading is fine). Never delete `out/dataset-1004` or `out/dataset-0929`. Never touch `.venv`.
- `/home/ubuntu/git/kubeagent` is read-only.
- Never name the training host in a tracked file.
- No prompt byte moves: every user message stays byte-identical to `out/dataset-1004`.
- TDD: write the failing test first, run it, see it fail, then implement.
- Docs (Task 6) are in simple voice: short sentences, plain words, numbers explained.
- **Red between tasks:** only hash pins and count pins may be red at the end of Tasks 1-4. Every report lists each red test with its old and its new value. Any other test a task breaks is fixed in that task. Task 5 makes the suite fully green.

## Plan rulings

These settle points the spec leaves open. Each is binding on the tasks.

1. **Build folder.** The spec says `out/dataset-MMDD`. `out/dataset-1004` already exists and must not be touched, so the build goes to `out/dataset-1004-4b2`.
2. **empty_candidates with no anchor.** The row shows no candidate list, so "the evidence rules out the listed causes" would be false. Its summary is `"{key} is failing, but its own lines do not show why.\nNo deterministic candidates were available."`. A gated single row that does show candidates uses today's ruled-out wording, as spec §2 says.
3. **Gate count.** The spec's table says 1 train row moves to `none_of_these`. The 8,000-row pool has 4 such rows, all coredns `multi` rows (pool indexes 2088, 2177, 2630, 2850). One of them lands in train. The test pins the 4 in the pool. Task 5 measures and records the train count.
4. **Anchor lines at build time.** Test 2's first two bullets ("the anchor is in `anchor_lines`", "every key is in `anchor_lines`") are enforced when a row is built: `_entry_gold` checks the anchor against the anchor lines and `gold.check_keys` raises on a key that is not in them. The anchors test re-checks the anchor and the keys against the own lines, and the gate unit test proves the excluded-line path.
5. **Recommendation names.** Test 2's last bullet (no drawn name in a recommendation the own lines don't print) is enforced statically: after the 7 rewrites no trainable recommendation holds `{node}`, `{pvc}`, `{image}` or `{pod}`, and a Task 1 test pins that.
6. **A fourth hash pin.** The spec names three hashes. `OTHER_FAMILIES_SHA256` (`tests/test_generate.py:1157`) hashes the 229 non-shared-origin exam rows and moves too. Task 5 re-pins it the same way. `_PROBE_DECOYS_SHA256` (`tests/test_cases.py:962`) hashes decoys only and must **not** move.
7. **Gold type.** `_entry_gold` returns `gold.RowGold`. Its none branch has `cause == ""`; a builder writes `c.NONE_OF_THESE` into the answer row.

## Review Focus

1. **A `ValueError` from `_entry_gold` inside a builder whose caller catches `ValueError` and draws again.** A reasonable person expects the build to stop, not to shift the random stream silently. The prompt-bytes test (Task 1) catches any shift; it must stay green after Tasks 2 and 3.
2. **A single-workload row whose anchor is missing.** It must not name a cause in its summary, and its meta must carry no keys and no must-not words. Task 2 tests it with a kit whose anchor is never printed.
3. **An empty-candidates row whose anchor is missing.** Its summary must not say the evidence "rules out the listed causes". Task 2 tests the exact wording.
4. **An anchor that sits only on a line naming a ruled-out or refuted cause.** The row must answer `none_of_these`. A key that sits only on such a line must fail the build. Task 2's gate test covers both.
5. **A `multi` row with a healthy-origin read first.** The extra read must not count as any workload's own line. Task 3's anchors test runs over every `multi` row, including those.

---

### Task 1: The answer kits

**Files:**
- Modify: `src/kubeagent_verdict/dataset/catalog.py` (dataclass fields, after `contradiction_events`)
- Modify: `src/kubeagent_verdict/dataset/entries_slugs.py` (imports; 7 trainable entries; 2 recommendations)
- Modify: `src/kubeagent_verdict/dataset/entries_kinds.py` (imports; 13 trainable entries; 5 recommendations)
- Create: `tests/test_catalog_gold.py`

**Interfaces:**
- Consumes: `stories.Answer(anchor, cause, keys, rationale, confidence="high", link=False)` (already in `src/kubeagent_verdict/dataset/stories.py:31`; its `__post_init__` checks keys and confidence).
- Produces: `CatalogEntry.answer: stories.Answer | None` and `CatalogEntry.none_phrase: str`. Task 2 and Task 3 read them. The old fields stay in this task.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_catalog_gold.py`:

```python
"""Spec 4b-2: the catalog's answer kits, and the gold they give.

Every named catalog gold rests on an anchor in the workload's own lines.
See docs/superpowers/specs/2026-10-04-catalog-gold-design.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kubeagent_verdict.dataset import catalog, generate, stories

ENTRIES = {e.key: e for e in catalog.all_entries()}

# The spec's kit table (§3): key -> (anchor, cause, keys, confidence).
# Written out here, not imported, so a change to a kit fails.
KITS = {
    "memory-limit-oomkill": (
        "issue: oomkilled", "container killed at its memory limit",
        ("memory", "limit"), "high"),
    "deployment-bad-image-tag": (
        '": not found', "the image tag does not exist in the registry",
        ("image", "registry"), "high"),
    "node-cordon-diskfull": (
        "were unschedulable",
        "one node is unschedulable (cordoned) and the others have taints the pod does not "
        "tolerate",
        ("unschedulable", "taint"), "high"),
    "networkpolicy-deny-all": (
        "network policy: pods selected by",
        "a default-deny network policy blocks the probe's traffic to the pod",
        ("network", "policy"), "medium"),
    "coredns-corefile-broken": (
        "log cause: configuration parse",
        "the Corefile has a syntax or plugin error that crashes CoreDNS on startup",
        ("coredns", "error"), "high"),
    "worker-containerd-stop": (
        "containerd task: context deadline exceeded",
        "containerd on the pod's node is not responding (context deadline exceeded)",
        ("containerd", "deadline"), "high"),
    "oversized-job-unschedulable": (
        "insufficient memory",
        "the pod's memory request is larger than any node can allocate",
        ("memory", "node"), "high"),
    "crashloop-pod": (
        "log cause: bad command or entrypoint",
        "the container's command or entrypoint is wrong and it exits immediately",
        ("entrypoint", "exit"), "high"),
    "probe-failure": (
        "http 500", "the application answers its readiness endpoint with errors",
        ("readiness", "endpoint"), "high"),
    "container-start-error": (
        "no such file or directory",
        "the container's entrypoint names a path that does not exist in the image",
        ("container", "image"), "high"),
    "create-container-config-error": (
        "couldn't find key",
        "the pod spec references a ConfigMap key that was never added or was renamed",
        ("configmap", "key"), "high"),
    "init-crashloop": (
        "log cause: cannot reach a dependency",
        "the init container cannot reach a dependency it waits for before the pod can start",
        ("init", "dependency"), "high"),
    "init-config-error": (
        "secret migration-creds not found",
        "a Secret the init container references does not exist",
        ("secret", "init"), "high"),
    "init-errimagepull": (
        '": not found', "the init container's image tag does not exist in the registry",
        ("init", "registry", "tag"), "high"),
    "init-imagepullbackoff": (
        "back-off pulling image",
        "the init container's image cannot be pulled, and the kubelet keeps backing off",
        ("init", "pull"), "high"),
    "init-oomkilled": (
        "init:oomkilled", "the init container is killed at its memory limit",
        ("memory", "init"), "high"),
    "restart-loop": (
        "log cause: application panic",
        "the container panics (a code bug) and keeps restarting",
        ("panic", "container"), "high"),
    "volume-attach-error": (
        "multi-attach error", "the volume is still attached to another node",
        ("attached", "node"), "high"),
    "volume-mount-error": (
        "issue: volumemounterror", "the pod's volume times out while mounting on its node",
        ("volume", "pod"), "high"),
    "pvc-unbound-unschedulable": (
        "unbound immediate persistentvolumeclaims",
        "a claim the pod mounts is still waiting for its volume to be provisioned",
        ("claim", "volume"), "high"),
}

# The spec's draft reasons, as templates ({image} is filled per row).
REASONS = {
    "memory-limit-oomkill":
        "Its finding says the container exceeded its memory limit and was killed, with "
        "exit code 137.",
    "deployment-bad-image-tag":
        'The pull of {image} fails with "not found", so the tag does not exist in the '
        "registry.",
    "node-cordon-diskfull":
        "The scheduler says 1 node was unschedulable and 2 had taints the pod does not "
        "tolerate, so no node can take it.",
    "networkpolicy-deny-all":
        "The readiness probe times out, and kubeagent names the default-deny network policy "
        "that selects its pods as a possible cause, so the policy likely blocks the probe.",
    "coredns-corefile-broken":
        "The coredns container keeps crashing, and its previous log classifies as a "
        "configuration parse or validation error, so CoreDNS cannot load its Corefile.",
    "worker-containerd-stop":
        'Starting the container fails with "failed to create containerd task: context '
        "deadline exceeded\", so containerd on the pod's node does not answer in time.",
    "oversized-job-unschedulable":
        "The scheduler rejects all 3 nodes for insufficient memory, so the pod's memory "
        "request is larger than any node can give.",
    "crashloop-pod":
        "The container keeps exiting after it starts, and its previous log classifies as a "
        "bad command or entrypoint.",
    "probe-failure":
        "The readiness probe fails with HTTP 500, so the application answers its health "
        "endpoint with an error.",
    "container-start-error":
        'The container cannot start: its entrypoint path gives "no such file or directory", '
        "so that path is not in the image.",
    "create-container-config-error":
        "The kubelet couldn't find the key the container needs in the ConfigMap it names, "
        "so the pod spec points at a key that is not there.",
    "init-crashloop":
        "The init container keeps crashing, and its previous log classifies as connection "
        "refused, so it cannot reach a dependency it waits for.",
    "init-config-error":
        "The init container cannot start because the Secret it references is not found.",
    "init-errimagepull":
        "The init container's image pull fails with \"not found\", so its tag does not "
        "exist in the registry.",
    "init-imagepullbackoff":
        "The kubelet keeps backing off pulling the init container's image, so the pod "
        "cannot start. Its own lines do not say why the pull fails.",
    "init-oomkilled":
        "The init container is OOMKilled with exit code 137, so it is killed at its own "
        "memory limit.",
    "restart-loop":
        "The container keeps exiting with an error, and its previous log classifies as an "
        "application panic.",
    "volume-attach-error":
        "Attaching fails with a multi-attach error: the volume is already attached to "
        "another node.",
    "volume-mount-error":
        "Mounting the pod's volume times out waiting for the condition, so the volume does "
        "not mount on its node.",
    "pvc-unbound-unschedulable":
        "The scheduler says the pod has unbound immediate PersistentVolumeClaims, so a "
        "claim it mounts has no volume yet.",
}

NONE_PHRASES = {
    "memory-limit-oomkill": "its container keeps being killed for memory",
    "deployment-bad-image-tag": "its image cannot be pulled",
    "node-cordon-diskfull": "its pod cannot be scheduled",
    "networkpolicy-deny-all": "its readiness probe fails",
    "coredns-corefile-broken": "its container keeps crashing",
    "worker-containerd-stop": "its container fails to start",
    "oversized-job-unschedulable": "its pod cannot be scheduled",
    "crashloop-pod": "its container keeps crashing",
    "probe-failure": "its readiness probe fails",
    "container-start-error": "its container fails to start",
    "create-container-config-error": "its container fails to start",
    "init-crashloop": "its init container keeps crashing",
    "init-config-error": "its init container fails to start",
    "init-errimagepull": "its init container's image cannot be pulled",
    "init-imagepullbackoff": "its init container's image cannot be pulled",
    "init-oomkilled": "its init container keeps being killed for memory",
    "restart-loop": "its container keeps restarting",
    "volume-attach-error": "its volume cannot attach",
    "volume-mount-error": "its volume cannot be mounted",
    "pvc-unbound-unschedulable": "its pod cannot be scheduled",
}

# The 7 recommendations the spec rewrites (§3). The other 13 stay.
RECOMMENDATIONS = {
    "node-cordon-diskfull": "uncordon the node, or check why the other nodes are tainted",
    "worker-containerd-stop": "check whether the container runtime on the pod's node is healthy",
    "init-imagepullbackoff": "check the init image's tag and the registry credentials",
    "init-oomkilled": "raise the init container's memory limit",
    "restart-loop": "check the previous log for the panic",
    "volume-mount-error": "check why the volume does not mount on the pod's node",
    "pvc-unbound-unschedulable": "check why the pod's claim has no bound volume yet",
}


# ------------------------------------------------------------ the kits


def test_every_trainable_entry_has_a_kit_and_no_other_entry_does():
    for e in catalog.all_entries():
        if e.trains:
            assert isinstance(e.answer, stories.Answer), e.key
            assert e.none_phrase, e.key
        else:
            assert e.answer is None and e.none_phrase == "", e.key
    assert set(KITS) == {e.key for e in catalog.trainable()}


def test_the_kits_are_the_spec_table():
    got = {e.key: (e.answer.anchor, e.answer.cause, e.answer.keys, e.answer.confidence)
           for e in catalog.trainable()}
    assert got == KITS


def test_the_kit_reasons_are_the_spec_drafts():
    assert {e.key: e.answer.rationale for e in catalog.trainable()} == REASONS


def test_the_none_phrases_are_the_spec_list():
    assert {e.key: e.none_phrase for e in catalog.trainable()} == NONE_PHRASES


def test_no_kit_links_and_no_anchor_or_cause_holds_a_placeholder():
    for e in catalog.trainable():
        a = e.answer
        assert a.link is False, e.key
        assert "{" not in a.anchor and "{" not in a.cause, e.key
        stories.validate_answer(a)


def test_no_kit_cause_or_key_holds_one_of_its_must_not_words():
    for e in catalog.trainable():
        for word in e.own_cause_must_not:
            assert word not in e.answer.cause.lower(), (e.key, word)
            assert word not in e.answer.keys, (e.key, word)


def test_the_seven_recommendations_are_rewritten():
    for key, text in RECOMMENDATIONS.items():
        assert ENTRIES[key].recommendation == text, key


def test_no_trainable_recommendation_names_a_drawn_name():
    for e in catalog.trainable():
        for placeholder in ("{node}", "{pvc}", "{image}", "{pod}"):
            assert placeholder not in e.recommendation, (e.key, placeholder)


# ------------------------------------------------------------ the prompts

DATASET_1004 = Path(__file__).resolve().parents[1] / "out" / "dataset-1004"


@pytest.fixture(scope="module")
def build_1004() -> dict[str, list]:
    """The out/dataset-1004 pipeline: generate(17, 8000), split, drop held-out."""
    ex = generate.generate(17, 8000)
    tr, va = generate.split(ex, 17)
    te = generate.test_set()
    return {"train": generate.drop_held_out(tr, te),
            "val": generate.drop_held_out(va, te), "test": te}


@pytest.mark.skipif(not DATASET_1004.is_dir(), reason="out/dataset-1004 is not on this machine")
@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_no_prompt_byte_moves_from_dataset_1004(build_1004, split):
    """Spec test 5. The gold changes; the prompts never do. A builder that
    raises and is drawn again would shift every later row, so this also
    guards the random stream."""
    path = DATASET_1004 / f"{split}.jsonl"
    old = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    new = [generate.to_row(e) for e in build_1004[split]]
    assert len(new) == len(old)
    for i, (a, b) in enumerate(zip(new, old)):
        assert a["messages"][:2] == b["messages"][:2], (split, i)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`
Expected: the kit tests FAIL with `AttributeError: 'CatalogEntry' object has no attribute 'answer'`, and the recommendation test FAILS on `node-cordon-diskfull`. The three prompt-bytes tests PASS: they are the guard for Tasks 2 and 3, green from the start.

- [ ] **Step 3: Add the kit fields**

In `src/kubeagent_verdict/dataset/catalog.py`, add the import next to the existing one:

```python
from kubeagent_verdict.dataset.objects import Object
from kubeagent_verdict.dataset.stories import Answer
```

and add these two fields to `CatalogEntry`, directly after `contradiction_events`:

```python
    # The answer kit (Spec 4b-2), on trainable entries only. An undecided
    # row names `answer.cause` only when the workload's own lines, minus
    # every line naming a ruled-out or refuted cause, hold `answer.anchor`.
    # Otherwise the row answers none_of_these, and its reason opens with
    # `none_phrase`: "<none_phrase>; none of its own lines says why."
    answer: Answer | None = None
    none_phrase: str = ""
```

- [ ] **Step 4: Write the 20 kits and the 7 recommendations**

In `entries_slugs.py` and `entries_kinds.py`, add `from kubeagent_verdict.dataset.stories import Answer` to the imports. On every trainable entry, add `answer=` and `none_phrase=` directly after the existing `own_cause_must_not=` line (or after `own_cause_keywords=` when the entry has no must-not line). Take every value verbatim from `KITS`, `REASONS` and `NONE_PHRASES` in Step 1. Leave out `confidence=` when it is `"high"` (the default). The first entry, in full:

```python
        own_cause_must_not=INIT_CONTAINER,
        answer=Answer(
            anchor="issue: oomkilled",
            cause="container killed at its memory limit",
            keys=("memory", "limit"),
            rationale="Its finding says the container exceeded its memory limit and was "
                      "killed, with exit code 137."),
        none_phrase="its container keeps being killed for memory",
```

`networkpolicy-deny-all` is the one kit with `confidence="medium"`. The two reasons that hold `{image}` or quotes keep them exactly as in `REASONS`.

Then replace these 7 `recommendation=` values with the `RECOMMENDATIONS` text (a two-line string becomes one line):
- `entries_slugs.py`: `node-cordon-diskfull` (:97), `worker-containerd-stop` (:223).
- `entries_kinds.py`: `init-imagepullbackoff` (:211), `init-oomkilled` (:240-241), `restart-loop` (:272), `volume-mount-error` (:338), `pvc-unbound-unschedulable` (:374-375).

Do not touch `own_cause`, `own_cause_keywords`, `rationale` or `direct`. They still drive the builders until Tasks 2 and 3.

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`
Expected: all PASS.

Then the full suite: `$PYTEST`. Expected: green except pins that read a recommendation through a built summary (a hash or a count pin). List any red test with its old and new value in the report.

Then lint: `.venv/bin/ruff check --ignore EXE002 .` → `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_slugs.py src/kubeagent_verdict/dataset/entries_kinds.py tests/test_catalog_gold.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(catalog): answer kits and plain recommendations for the 20 trainable entries"
```

---

### Task 2: The gate in the single-workload builders

**Files:**
- Modify: `src/kubeagent_verdict/dataset/gold.py` (`excluded_causes`, `anchor_lines`, ~:141-153)
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_job1_example` ~:327, near `_CLEAR_WORDING` ~:418, `_undecided_example` ~:429-486, `empty_candidates` ~:623-660)
- Modify: `tests/test_catalog_gold.py`
- Modify: `tests/test_cases.py`, `tests/test_score.py` (old-field reads this task breaks)

**Interfaces:**
- Consumes: `CatalogEntry.answer`, `CatalogEntry.none_phrase` (Task 1); `gold.RowGold(verdict, cause, confidence, keys, rationale, linked)`, `gold.check_keys(keys, *, anchors, own)`, `gold.own_lines(prompt, workloads) -> dict[str, frozenset[str]]`, `gold._norm_cause(s)`.
- Produces (Task 3 uses all of these):
  - `gold.excluded_from(candidates, result: rules.Result) -> list[str]`
  - `gold.drop_excluded(own: Iterable[str], excluded: Iterable[str]) -> list[str]`
  - `cases._entry_gold(e: CatalogEntry, n: Names, own: Sequence[str], excluded: Sequence[str]) -> gold.RowGold`
  - `cases._ruled_out_summary(key: str) -> str`
  - In `tests/test_catalog_gold.py`: `catalog_rows(examples, skip)` and the `examples` fixture, plus `MULTI_CASES`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_catalog_gold.py`. Add these imports at the top with the others: `import dataclasses`, `import random`, `import re`, and `from kubeagent_verdict import contract as c`, and extend the dataset import to `from kubeagent_verdict.dataset import cases, catalog, generate, gold, stories` and `from kubeagent_verdict.dataset import names as names_mod`.

```python
# ------------------------------------------------------------ the gold

# The probe's fact pattern (spec test 2): a number with an optional unit,
# or a CamelCase word. Compared lowercase against the own lines.
FACT = re.compile(r"\b(?:\d+(?:\.\d+)?[A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]+|[a-z]+[A-Z][A-Za-z]+)\b")
GATED = "; none of its own lines says why."
# Task 3 rebuilds these two on the gate and empties this set.
MULTI_CASES = {"multi", "multi_misattribution_probe"}


@pytest.fixture(scope="module")
def examples() -> list:
    """Every catalog case over three seeds, plus the exam. About 7 s."""
    rows = []
    for seed in (17, 18, 19):
        rows += generate.generate(seed, 8000)
    return rows + generate.test_set()


def catalog_rows(examples, skip=frozenset()):
    """(example, workload, entry, verdict, workload meta, own lines) for every
    catalog workload. A catalog group is `entry:ns/name`, joined by `+`."""
    for ex in examples:
        if ex.case.startswith("shared_origin") or ex.case in skip:
            continue
        entry_of = {wl: ENTRIES[key] for key, wl in
                    (part.split(":", 1) for part in ex.group.split("+"))}
        own = gold.own_lines(ex.user, list(entry_of))
        verdicts = {v["workload"]: v for v in json.loads(ex.assistant)["verdicts"]}
        for wl, e in entry_of.items():
            yield ex, wl, e, verdicts[wl], ex.meta["workloads"][wl], sorted(own[wl])


def _names() -> names_mod.Names:
    return names_mod.Names(
        ns="shop", name="web", pod="web-5d8f7c9b4-x2k9p", container="app",
        init_container="init-config", image="registry.example.com/shop/web:v1.2.3",
        node="worker-1", pvc="data-0", restarts=5)


def test_every_named_answer_rests_on_its_own_lines(examples):
    """Spec test 2: the cause is the kit's, and the anchor, every key and
    every fact in the reason are on the workload's own lines."""
    named = 0
    for ex, wl, e, v, wm, own in catalog_rows(examples, skip=MULTI_CASES):
        if wm["decided"] or v["cause"] == c.NONE_OF_THESE:
            continue
        named += 1
        a, text, where = e.answer, "\n".join(own), (ex.case, ex.group, wl)
        assert v["cause"] == cases._fmt(a.cause, _names()), where
        assert any(gold._norm_cause(a.anchor) in ln for ln in own), where
        assert all(any(k in ln for ln in own) for k in a.keys), where
        unshown = [t for t in FACT.findall(v["rationale"]) if t.lower() not in text]
        assert unshown == [], (*where, unshown)
    assert named > 1000


def test_confidence_follows_the_gold(examples):
    """Spec test 4: rules-decided rows are high, named rows carry the kit's
    confidence, none_of_these rows are low, and meta agrees."""
    for ex, wl, e, v, wm, _own in catalog_rows(examples, skip=MULTI_CASES):
        if wm["decided"]:
            want = "high"
        elif v["cause"] == c.NONE_OF_THESE:
            want = "low"
        else:
            want = e.answer.confidence
        assert v["confidence"] == want, (ex.case, ex.group, wl)
        if "expected_confidence" in ex.meta:
            first = json.loads(ex.assistant)["verdicts"][0]
            assert ex.meta["expected_confidence"] == first["confidence"], (ex.case, ex.group)


def _probe_own_lines(examples) -> list[str]:
    ex = next(x for x in examples
              if x.case == "own_cause" and x.group.startswith("probe-failure:"))
    wl = ex.group.split(":", 1)[1]
    return sorted(gold.own_lines(ex.user, [wl])[wl])


def test_the_gate_names_the_cause_only_on_its_anchor(examples):
    """Spec test 3, the hand-cut case: real own lines of a probe-failure row."""
    e, n = ENTRIES["probe-failure"], _names()
    own = _probe_own_lines(examples)
    named = cases._entry_gold(e, n, own, [])
    assert named == gold.RowGold("named", e.answer.cause, "high", ("readiness", "endpoint"),
                                 e.answer.rationale, False)
    none = gold.RowGold("none_of_these", "", "low", (),
                        "its readiness probe fails" + GATED, False)
    cut = [ln for ln in own if "http 500" not in ln]
    assert cases._entry_gold(e, n, cut, []) == none
    assert cases._entry_gold(e, n, own, ["http 500"]) == none


def test_a_key_only_on_an_excluded_line_fails_the_build():
    e = dataclasses.replace(ENTRIES["probe-failure"], answer=stories.Answer(
        anchor="http 500", cause="the readiness endpoint fails",
        keys=("readiness", "endpoint"), rationale="x."))
    own = ["probe says http 500", "readiness endpoint is down"]
    with pytest.raises(ValueError, match="sits only in excluded lines"):
        cases._entry_gold(e, _names(), own, ["readiness endpoint is down"])
    with pytest.raises(ValueError, match="sits in no own line"):
        cases._entry_gold(e, _names(), own[:1], [])


def test_an_entry_with_no_kit_cannot_answer():
    e = next(x for x in catalog.all_entries() if not x.trains)
    with pytest.raises(ValueError, match="has no answer kit"):
        cases._entry_gold(e, _names(), [], [])


def _unprinted(key: str) -> catalog.CatalogEntry:
    """`key`'s entry with an anchor no prompt ever prints."""
    e = ENTRIES[key]
    return dataclasses.replace(e, answer=dataclasses.replace(
        e.answer, anchor="this line is never printed"))


@pytest.mark.parametrize("case", ["own_cause", "wrong_attribution", "misattribution_probe"])
def test_a_single_row_with_no_anchor_names_nothing(case):
    e, n = _unprinted("probe-failure"), _names()
    shape = "refuted" if case == "wrong_attribution" else "ruled_out"
    ex = cases._undecided_example(e, n, case=case, shape=shape, evidence="clear")
    doc = json.loads(ex.assistant)
    (row,) = doc["verdicts"]
    assert (row["cause"], row["confidence"], row["rationale"]) == (
        c.NONE_OF_THESE, "low", "its readiness probe fails" + GATED)
    assert doc["summary"] == cases._ruled_out_summary("shop/web")
    wm = ex.meta["workloads"]["shop/web"]
    assert (wm["own_cause_keywords"], wm["own_cause_must_not"]) == ([], [])
    assert ex.meta["expected_cause"] == c.NONE_OF_THESE


def test_an_empty_candidates_row_with_no_anchor_does_not_claim_a_list():
    ex = cases.empty_candidates(_unprinted("probe-failure"), _names())
    doc = json.loads(ex.assistant)
    (row,) = doc["verdicts"]
    assert (row["cause"], row["confidence"]) == (c.NONE_OF_THESE, "low")
    assert doc["summary"] == ("shop/web is failing, but its own lines do not show why.\n"
                              "No deterministic candidates were available.")
    assert ex.meta["expected_own_keywords"] == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`
Expected: FAIL. `test_every_named_answer_rests_on_its_own_lines` fails on the first changed cause or unshown fact; `test_confidence_follows_the_gold` fails on a rules-decided `medium` row; the gate tests fail with `AttributeError: module 'kubeagent_verdict.dataset.cases' has no attribute '_entry_gold'`.

- [ ] **Step 3: Split the excluded-cause helpers in gold.py**

Replace `excluded_causes` and `anchor_lines` in `src/kubeagent_verdict/dataset/gold.py` with:

```python
def excluded_from(candidates: Iterable, result: rules.Result) -> list[str]:
    """Causes the rules threw out: every candidate ruled out at attribution,
    plus every candidate refuted by its fresh read."""
    ruled_out = [cand.cause for cand in candidates if cand.verdict == "ruled_out"]
    refuted = [d.candidate for d in result.decisions if d.outcome == "refuted"]
    return ruled_out + refuted


def excluded_causes(row: so.Row) -> list[str]:
    return excluded_from(row.candidates, row.result)


def drop_excluded(own: Iterable[str], excluded: Iterable[str]) -> list[str]:
    """`own` minus every line that names an excluded cause: a gold may not
    lean on a cause the rules threw out."""
    dropped = [_norm_cause(x) for x in excluded]
    return [ln for ln in own if not any(x and x in _norm_cause(ln) for x in dropped)]


def anchor_lines(own: Iterable[str], row: so.Row) -> list[str]:
    return drop_excluded(own, excluded_causes(row))
```

This is a pure refactor for the shared-origin rows: their bytes must not move.

- [ ] **Step 4: Add `_entry_gold` and `_ruled_out_summary` to cases.py**

Directly after `_MENUS = {...}` (~:426), add:

```python
_GATED_NONE = "; none of its own lines says why."


def _entry_gold(e: CatalogEntry, n: Names, own: Sequence[str],
                excluded: Sequence[str]) -> gold.RowGold:
    """The gold for one undecided catalog workload (Spec 4b-2 §2).

    It names the kit's cause only when the kit's anchor is in the
    workload's anchor lines: its own lines minus every line that names an
    excluded (ruled-out or refuted) cause. Otherwise the answer is
    none_of_these, at low confidence, with no keys. A named answer whose
    key sits in no anchor line raises ValueError, so a kit that leans on
    a hidden word fails the build instead of teaching it.
    """
    a = e.answer
    if a is None:
        raise ValueError(f"{e.key} has no answer kit")
    own = list(own)
    anchors = gold.drop_excluded(own, excluded)
    anchor = gold._norm_cause(_fmt(a.anchor, n))
    if any(anchor in ln for ln in anchors):
        gold.check_keys(a.keys, anchors=anchors, own=own)
        return gold.RowGold("named", _fmt(a.cause, n), a.confidence, a.keys,
                            _fmt(a.rationale, n), False)
    return gold.RowGold("none_of_these", "", "low", (), f"{e.none_phrase}{_GATED_NONE}", False)


def _ruled_out_summary(key: str) -> str:
    """The summary of an undecided single row that names no cause."""
    return (f"{key} is failing, but the evidence rules out the listed causes.\n"
            "A closer look at the workload is needed.")
```

- [ ] **Step 5: Rules-decided single rows are high**

In `_job1_example`, replace `cause, conf = result.cause, _confidence(e)` with:

```python
    cause, conf = result.cause, "high"
```

- [ ] **Step 6: Gate `_undecided_example`**

Replace the block from `if thin:` to the line `summary = f"{key} is failing: {cause}.\n{last}"` with:

```python
    if thin:
        cause, conf, keywords, must_not = c.NONE_OF_THESE, "low", [], []
        rationale = _THIN_RATIONALE[shape]
        summary = _ruled_out_summary(key)
    else:
        own = sorted(gold.own_lines(user, [key])[key])
        g = _entry_gold(e, n, own, gold.excluded_from(candidates, result))
        if g.verdict == "named":
            cause, conf, keywords = g.cause, g.confidence, list(g.keys)
            must_not = list(e.own_cause_must_not)
            suffix, last = _CLEAR_WORDING[case]
            rationale = g.rationale + suffix
            last = last or f"{_fmt(e.recommendation, n).capitalize()}."
            summary = f"{key} is failing: {cause}.\n{last}"
        else:
            cause, conf, keywords, must_not = c.NONE_OF_THESE, "low", [], []
            rationale = g.rationale
            summary = _ruled_out_summary(key)
```

Update the docstring's second sentence to: "Thin evidence is the `none_of_these` case and only it; clear evidence answers the kit's cause when the workload's own lines show its anchor (`_entry_gold`), and none_of_these when they do not." The thin summary's bytes do not change: `_ruled_out_summary` is the same two lines.

- [ ] **Step 7: Gate `empty_candidates`**

Replace the body from `cause = _fmt(e.own_cause, n)` to the line before `meta.update(prompt_meta(...))` with:

```python
    key = f"{n.ns}/{n.name}"
    own = sorted(gold.own_lines(user, [key])[key])
    g = _entry_gold(e, n, own, [])
    if g.verdict == "named":
        cause, conf, keywords = g.cause, g.confidence, list(g.keys)
        must_not = list(e.own_cause_must_not)
        rationale = g.rationale + " The candidate list shown did not include this cause."
        first = f"{key} is failing: {cause}."
    else:
        cause, conf, keywords, must_not = c.NONE_OF_THESE, "low", [], []
        rationale = g.rationale
        first = f"{key} is failing, but its own lines do not show why."
    rows = [{"workload": key, "cause": cause, "confidence": conf, "rationale": rationale}]
    summary = f"{first}\nNo deterministic candidates were available."
    wm = workload_meta(result, expected_cause=cause, own_cause_keywords=keywords,
                       own_cause_must_not=must_not)
    meta = {"case": "empty_candidates", "entry": e.key, "expected_cause": cause,
            "expected_confidence": conf, "expected_own_keywords": keywords}
```

Keep the rest (`meta.update(prompt_meta(...))` and the `return`, which may use `key`). Rewrite the docstring's first paragraph to: "The row answers the kit's cause when its own lines show the anchor, and none_of_these when they do not (Spec 4b-2). There is no candidate list, so nothing is excluded."

After this step, `grep -n "_confidence(" src/kubeagent_verdict/dataset/cases.py` shows only the definition, `multi_misattribution_probe` and `multi`. Task 3 removes those.

- [ ] **Step 8: Run the new tests to see them pass**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`
Expected: all PASS, including the three prompt-bytes tests.

- [ ] **Step 9: Rewrite the old tests this task breaks**

Each rewrite gets a dated comment `# 2026-10-04 (Spec 4b-2): …` saying what changed. In `tests/test_cases.py`:

- :37 the comment `# direct=True entry with full evidence` → `# a rules-decided row is high`.
- :44-47 rename `test_attributed_indirect_entry_gets_medium` to `test_attributed_rows_are_high_for_every_entry`; it now asserts `"high"`. Docstring or comment: probe-failure was `medium` until Spec 4b-2.
- :253-258 `test_truncated_answers_at_the_entrys_confidence_with_no_caution`: rename to `test_truncated_answers_high_with_no_caution`; assert `row["confidence"] == ex.meta["expected_confidence"] == "high"` (drop the `!= "low"` line, now implied).
- :268 comment `# a direct entry; was a flat "medium"` → `# the kit's confidence`.
- :276 `cases._fmt(e.own_cause, n)` → `cases._fmt(e.answer.cause, n)`.
- :291-292 `cases._confidence(e)` → `e.answer.confidence` (both lines); the docstring says "the kit's own confidence".
- :410-412 `cases._fmt(e.own_cause, n)` → `cases._fmt(e.answer.cause, n)`; `cases._confidence(e)` → `e.answer.confidence`; `list(e.own_cause_keywords)` → `list(e.answer.keys)`.
- :431 and :714 `cases._fmt(e.own_cause, n)` → `cases._fmt(e.answer.cause, n)`.
- :1538-1540 the three comments `# a node cause; the entry says medium` → `# a node cause; the kit says high` for probe-failure and restart-loop, and `# a node cause; the kit says medium` for networkpolicy-deny-all. The test's assertions do not change.
- :1638-1645 `test_a_clear_row_answers_the_own_cause_at_the_entrys_confidence`: rename to `test_a_clear_row_answers_the_kits_cause_at_the_kits_confidence`; assert `row["cause"] == cases._fmt(e.answer.cause, n) == ex.meta["expected_cause"]` and `row["confidence"] == e.answer.confidence == ex.meta["expected_confidence"]`.
- :1661-1663 `cases._fmt(e.rationale, n)` → `cases._fmt(e.answer.rationale, n)`; `cases._fmt(e.own_cause, n)` → `cases._fmt(e.answer.cause, n)`.

In `tests/test_score.py` (~:3585), the `declaring` loop reads the catalog's keys. It must read the kits, because the exam's meta now carries them:

```python
    for entry in catalog.all_entries():
        if entry.answer:
            declaring.setdefault(tuple(entry.answer.keys), []).append(entry.key)
```

with a dated comment. The test's counts (151 catalog workloads, 175) may move; that is a count pin and Task 5 re-pins it.

- [ ] **Step 10: Run the full suite and lint**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST` and `.venv/bin/ruff check --ignore EXE002 .`
Expected: green except hash and count pins. The red ones expected: `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256`, `GRADED_VIEW_SHA256`, `OTHER_FAMILIES_SHA256`, and counts in `tests/test_answer_keys.py` and `tests/test_score.py`. `_PROBE_DECOYS_SHA256` must stay green. Any other red test is fixed in this task. List every red pin with old and new value in the report.

- [ ] **Step 11: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/gold.py src/kubeagent_verdict/dataset/cases.py tests/test_catalog_gold.py tests/test_cases.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(cases): single-workload catalog gold rests on an anchor in its own lines"
```

---

### Task 3: The gate in the multi builders, and the old fields go

**Files:**
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_confidence` ~:267, `multi_misattribution_probe` ~:667-751, `_thin_multi` ~:890-905, `multi` ~:1011-1115)
- Modify: `src/kubeagent_verdict/dataset/catalog.py` (module docstring :5-8; fields `rationale`, `direct`, `own_cause`, `own_cause_keywords`)
- Modify: `src/kubeagent_verdict/dataset/entries_slugs.py`, `src/kubeagent_verdict/dataset/entries_kinds.py` (delete the four old kwargs on every entry)
- Modify: `tests/test_catalog_gold.py`, `tests/test_cases.py`, `tests/test_catalog.py`, `tests/test_catalog_text.py`, `tests/test_stories.py`, `tests/test_answer_keys.py`

**Interfaces:**
- Consumes (Task 2): `cases._entry_gold(e, n, own, excluded) -> gold.RowGold`, `gold.excluded_from(candidates, result)`, `gold.own_lines(prompt, workloads)`; in the test file, `catalog_rows`, `examples`, `MULTI_CASES`, `GATED`, `_names`, `_unprinted`.
- Produces: a `CatalogEntry` with no `rationale`, `direct`, `own_cause` or `own_cause_keywords`; no `cases._confidence`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_catalog_gold.py`, change `MULTI_CASES` to an empty set and its comment to `# Empty since Task 3: every case is on the gate.` — or delete it and its two `skip=MULTI_CASES` uses. Delete it; `catalog_rows` keeps its `skip` parameter for the grader test. Then append:

```python
def test_the_old_fields_are_gone():
    fields = {f.name for f in dataclasses.fields(catalog.CatalogEntry)}
    assert not fields & {"direct", "own_cause", "own_cause_keywords", "rationale"}
    assert not hasattr(cases, "_confidence")


# The pool's gated rows: generate(17, 8000) index and workload. All four are
# coredns `multi` rows whose read budget ran out before the coredns log read,
# so no own line shows the configuration parse error (Plan ruling 3).
GATED_POOL = {(2088, "web/scheduler"), (2177, "web/scheduler"), (2630, "media/worker"),
              (2850, "edge/gateway")}


def test_the_gate_fires_on_exactly_the_four_coredns_multi_rows():
    """Spec test 3, the real coredns multi shape."""
    pool, found = generate.generate(17, 8000), set()
    for i, ex in enumerate(pool):
        if ex.case.startswith("shared_origin"):
            continue
        for v in json.loads(ex.assistant)["verdicts"]:
            if v["rationale"].endswith(GATED):
                found.add((i, v["workload"]))
                assert ex.case == "multi" and ex.group.count("coredns-corefile-broken") == 1
                assert (v["cause"], v["confidence"], v["rationale"]) == (
                    c.NONE_OF_THESE, "low", "its container keeps crashing" + GATED)
                assert ex.meta["workloads"][v["workload"]]["own_cause_keywords"] == []
    assert found == GATED_POOL
    assert not [ex for ex in generate.test_set()
                if any(v["rationale"].endswith(GATED)
                       for v in json.loads(ex.assistant)["verdicts"])]


def test_a_multi_workload_with_no_anchor_names_nothing():
    """`_starved_row`'s shape: shop/gateway gets no read, its keys show on
    its finding line, so `_thin_multi` passes it on and the gate decides."""
    from test_cases import _crash_pairs, _names as row_names
    e = _unprinted("node-cordon-diskfull")
    ex = cases.multi([*_crash_pairs(), (e, row_names("shop", "gateway", "worker-4"))],
                     random.Random(26))
    v = next(r for r in json.loads(ex.assistant)["verdicts"] if r["workload"] == "shop/gateway")
    assert (v["cause"], v["confidence"], v["rationale"]) == (
        c.NONE_OF_THESE, "low", "its pod cannot be scheduled" + GATED)
    wm = ex.meta["workloads"]["shop/gateway"]
    assert (wm["expected_cause"], wm["own_cause_keywords"], wm["own_cause_must_not"]) == (
        c.NONE_OF_THESE, [], [])
```

(`tests/` is on `sys.path` under pytest's default import mode, so `from test_cases import …` works; it imports only the named helpers, so no test is collected twice.)

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`
Expected: FAIL. The anchors and confidence tests now see multi rows with old causes, old reasons and `medium` decided rows; `test_the_old_fields_are_gone` fails on the field set; the pool test finds no gated row; the starved test sees the kit's cause.

- [ ] **Step 3: Gate `multi_misattribution_probe`**

Replace its body from `workloads, rows = [], []` to the line before `lines = [...]` with: build every workload first, then the user message, then the gold.

```python
    workloads = []
    decoy_by_workload: dict[str, list[str]] = {}
    for (e, n), others, candidates, result in zip(pairs, foreign, res.candidates,
                                                   res.results):
        key = f"{n.ns}/{n.name}"
        if _starved(n, res.reads):
            raise ValueError(f"multi_misattribution_probe: the read budget never reached {key}")
        workloads.append(_workload(e, n, candidates, render.header_for(candidates),
                                   result=result))
        not_own = {f"{_CAUSE_WORD[obj.kind]} {obj.name}" for obj in others}
        decoy_by_workload[key] = [cand.cause for cand in candidates
                                  if cand.cause.split(" (", 1)[0] not in not_own]
    group = "+".join(f"{e.key}:{n.ns}/{n.name}" for e, n in pairs)
    user = _user_message(None, "", (), tuple(workloads), res.reads, key=group)
    keys = [f"{n.ns}/{n.name}" for _e, n in pairs]
    own = gold.own_lines(user, keys)
    rows = []
    workloads_meta: dict[str, dict] = {}
    for (e, n), key, candidates, result in zip(pairs, keys, res.candidates, res.results):
        g = _entry_gold(e, n, sorted(own[key]), gold.excluded_from(candidates, result))
        cause = g.cause or c.NONE_OF_THESE
        rows.append({"workload": key, "cause": cause, "confidence": g.confidence,
                     "rationale": g.rationale})
        workloads_meta[key] = workload_meta(
            result, expected_cause=cause, own_cause_keywords=list(g.keys),
            own_cause_must_not=list(e.own_cause_must_not) if g.verdict == "named" else [])
```

Delete the old `group = ...` and `user = ...` lines that followed the loop. In the docstring, replace "and the answer keeps the entry's own confidence" with "and each answer is the kit's, through the gate (`_entry_gold`)".

- [ ] **Step 4: Switch `_thin_multi` to the kit's keys**

In `_thin_multi`, replace `e.own_cause_keywords` with `e.answer.keys`.

- [ ] **Step 5: Gate `multi`**

Replace its body from `workloads, rows = [], []` to the line `user = _user_message(None, "", (), tuple(workloads), tuple(reads), key=group)` with:

```python
    workloads = []
    decoy_by_workload: dict[str, list[str]] = {}
    for (e, n), objects, candidates in zip(pairs, combined_objects, res.candidates):
        workloads.append(_workload(e, n, candidates, render.header_for(candidates),
                                   result=res.results[len(workloads)]))
        trace = rules.attribute(objects, ns=n.ns, pod=n.pod, issue=e.issue)
        # decoy_by_workload holds the decoy's cause STRING, as the prompt
        # prints it, never the raw kind/name identifier.
        decoy_by_workload[f"{n.ns}/{n.name}"] = [
            shown.cause for raw, shown in zip(trace, candidates) if raw.obj.intent == "decoy"]
    group = "+".join(f"{e.key}:{n.ns}/{n.name}" for e, n in pairs)
    reads = res.reads
    if healthy_read is not None:
        reads = (c.EvidenceRead(label=healthy_read[0], content=healthy_read[1]), *reads)
    user = _user_message(None, "", (), tuple(workloads), tuple(reads), key=group)
    keys = [f"{n.ns}/{n.name}" for _e, n in pairs]
    own = gold.own_lines(user, keys)
    rows = []
    workloads_meta: dict[str, dict] = {}
    for (e, n), key, w, candidates, result in zip(pairs, keys, workloads, res.candidates,
                                                  res.results):
        if result.decided:
            expected_cause, conf, keywords = result.cause, "high", []
            rationale = _rule_rationale(result)
        elif _thin_multi(e, n, w, result, res.reads):
            expected_cause, conf, keywords = c.NONE_OF_THESE, "low", []
            rationale = _THIN_RATIONALE["ruled_out"]
        else:
            g = _entry_gold(e, n, sorted(own[key]), gold.excluded_from(candidates, result))
            expected_cause, conf, keywords = g.cause or c.NONE_OF_THESE, g.confidence, list(g.keys)
            rationale = g.rationale
        rows.append({"workload": key, "cause": expected_cause, "confidence": conf,
                     "rationale": rationale})
        graded = not (result.decided or expected_cause == c.NONE_OF_THESE)
        workloads_meta[key] = render.workload_meta(
            result, expected_cause=expected_cause,
            own_cause_keywords=keywords if graded else [],
            own_cause_must_not=list(e.own_cause_must_not) if graded else [])
```

Then delete the now-duplicated `group = ...`, `reads = res.reads`, `if healthy_read ...` and `user = ...` lines that came after the `label`/`extra_meta` lines; keep `label`, `extra_meta`, its comment block, `lines` and the `return` unchanged. (If the first loop's `res.results[len(workloads)]` reads awkwardly to you, zip `res.results` in as a fourth item instead; the behaviour is the same.)

Rewrite the docstring's gold list:

```
    The gold, per workload:
    - The rules decide it: their cause, at high confidence, and a rationale
      from their evidence.
    - They do not, the gather never reached it, and its own lines miss a
      key of its kit: none_of_these, at low confidence (see `_thin_multi`).
    - Otherwise the gate (`_entry_gold`): the kit's cause when its own
      lines show the kit's anchor, none_of_these when they do not.
```

- [ ] **Step 6: Delete `_confidence` and the old fields**

- Delete `_confidence` from `cases.py`.
- Delete the `rationale`, `direct`, `own_cause` and `own_cause_keywords` fields from `CatalogEntry`.
- Delete those four kwargs from every entry in `entries_slugs.py` and `entries_kinds.py` (multi-line strings included).
- Rewrite `catalog.py`'s module docstring sentences "The cause an entry does write is its own_cause, the answer when the rules leave the workload undecided." as "The cause an entry does write is its answer kit's (`answer`), named when the rules leave the workload undecided and its own lines show the kit's anchor."

Check: `grep -rn "own_cause\b\|own_cause_keywords\|\.direct\b\|_confidence(" src/` shows only meta keys (`"own_cause_keywords"` strings, `own_cause_keywords=` kwargs of `workload_meta`) and the case name `own_cause`. No `e.own_cause…`, `e.rationale` or `e.direct` read remains in `src/`.

- [ ] **Step 7: Rewrite every remaining old-field test**

Each with a dated comment `# 2026-10-04 (Spec 4b-2): …`.

`tests/test_cases.py`:
- :869 `cases._fmt(e1.own_cause, n1)` / `e2` → `cases._fmt(e1.answer.cause, n1)` / `e2.answer.cause`.
- :1123-1133 `test_a_starved_workload_whose_block_names_its_cause_answers_it`: docstring → "node-cordon-diskfull's keys, "unschedulable" and "taint", are both on its finding line, so its own block names its cause with no read." Assertions:
  ```python
      assert (row["cause"], row["confidence"]) == (e.answer.cause, e.answer.confidence)
      assert row["rationale"] == cases._fmt(e.answer.rationale, n)
      wm = ex.meta["workloads"]["shop/gateway"]
      assert (wm["job"], wm["own_cause_keywords"]) == (2, list(e.answer.keys))
  ```
- :1136-1150 `test_a_starved_workload_whose_block_lacks_a_keyword_answers_none_of_these`: build the entry with
  ```python
      e0 = _entry("node-cordon-diskfull")
      e = dataclasses.replace(e0, answer=stories.Answer(
          anchor=e0.answer.anchor, cause="the node reports disk pressure",
          keys=("disk", "pressure"), rationale="x."))
  ```
  (import `stories` from `kubeagent_verdict.dataset` if the file does not yet). The assertions stay.
- :1815 `e.own_cause_keywords` → `e.answer.keys`.

`tests/test_catalog.py`:
- :167-169 in `test_trainable_entries_are_complete`: drop `assert e.rationale, e.key`; replace `assert e.own_cause and e.own_cause_keywords, e.key` with `assert e.answer and e.none_phrase, e.key`.
- :220-243 rename `test_own_cause_keywords_are_satisfied_by_their_own_cause` to `test_kit_keys_are_satisfied_by_their_own_cause`; read `e.answer.cause` and `e.answer.keys`; docstring: `stories.Answer` checks this at import too, this keeps the grader's view. `test_own_cause_keywords_are_discriminating` → `test_kit_keys_are_discriminating` over `e.answer.keys`.
- :262-264 `for tpl in (e.evidence, e.log_cause, e.recommendation, e.rationale, e.own_cause)` → `(e.evidence, e.log_cause, e.recommendation, e.answer.anchor, e.answer.cause, e.answer.rationale)`.
- :353-358: `assert e.answer.cause == ("a claim the pod mounts is still waiting for its volume to be provisioned")`, `assert e.answer.keys == ("claim", "volume")`, `assert e.answer.confidence == "high"` (replaces `e.direct is True`).

`tests/test_catalog_text.py`:
- :580-603 `KEYWORDS`: `"node-cordon-diskfull": ("unschedulable", "taint")`; the test asserts `e.answer.keys == KEYWORDS[key]`.
- :606-608 `test_worker_containerd_stop_names_containerd_in_its_own_cause` asserts `_entry("worker-containerd-stop").answer.cause == (…same string…)`.

`tests/test_stories.py:184`: `own = {tuple(e.answer.keys) for e in catalog.all_entries() if e.answer}`.

`tests/test_answer_keys.py`:
- `CHANGED["init-imagepullbackoff"]` → `(("init", "pull"), ())`, with a dated comment (was `("init", "tag", "registry")`).
- :65-67 and every other `e.own_cause_keywords` in the file → `e.answer.keys`; the module docstring gets one dated line saying the keys now live on the kit.

- [ ] **Step 8: Run the tests and the suite**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py`, then `$PYTEST`, then `.venv/bin/ruff check --ignore EXE002 .`
Expected: `test_catalog_gold.py` all PASS, including the prompt-bytes tests. The full suite is green except the hash and count pins listed in Task 2 Step 10 (values may have moved again). `_PROBE_DECOYS_SHA256` stays green. Report every red pin with old and new value.

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_slugs.py src/kubeagent_verdict/dataset/entries_kinds.py tests/test_catalog_gold.py tests/test_cases.py tests/test_catalog.py tests/test_catalog_text.py tests/test_stories.py tests/test_answer_keys.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "feat(cases): multi catalog gold on the gate; drop own_cause, rationale and direct"
```

---

### Task 4: The real grader gives every catalog gold full marks

**Files:**
- Modify: `tests/test_catalog_gold.py`

**Interfaces:**
- Consumes: `full_marks_misses(examples) -> list[str]` in `tests/test_shared_origin_pool.py:14` (reads each row's own gold back as the model's reply through `score.evaluate(..., grade_job2=True)` and lists every row that loses a mark: contract, decoy, job 1, job 2, job 3; G2 and G3b gate job 2, so they are covered).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Write the test**

Append to `tests/test_catalog_gold.py`:

```python
def test_the_real_grader_gives_every_catalog_gold_full_marks():
    """Spec test 6: every built catalog gold, read back as the reply, keeps
    full marks under the real grader (G2 and G3b included), and job 2
    scores it 1.0 against its own keys and must-not words."""
    from test_shared_origin_pool import full_marks_misses
    rows = [ex for ex in generate.generate(17, 8000) + generate.test_set()
            if not ex.case.startswith("shared_origin")]
    assert len(rows) > 5000
    assert full_marks_misses(rows) == []


def test_the_grader_check_can_fail():
    """The same check, fed a probe-failure gold whose cause is another
    entry's, must lose a mark: the test above is not vacuous."""
    from test_shared_origin_pool import full_marks_misses
    ex = next(x for x in generate.test_set() if x.case == "own_cause"
              and x.group.startswith("probe-failure:"))
    doc = json.loads(ex.assistant)
    doc["verdicts"][0]["cause"] = ENTRIES["init-oomkilled"].answer.cause
    bad = dataclasses.replace(ex, assistant=json.dumps(doc))
    assert full_marks_misses([bad]) != []
```

(`Example` is a frozen dataclass in `src/kubeagent_verdict/dataset/generate.py`, so `dataclasses.replace` works on it.)

- [ ] **Step 2: Run them**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST tests/test_catalog_gold.py -k grader`
Expected: both PASS (Tasks 2 and 3 built the gold to pass; this is the independent check). If the first fails, the listed rows name the case and group; that is a real defect in Task 2 or 3 code, not in this test. Report it as BLOCKED with the miss list; do not loosen the test.

- [ ] **Step 3: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . && git add tests/test_catalog_gold.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "test(catalog): the real grader gives every catalog gold full marks"
```

---

### Task 5: Build, gates, and the hand re-pin

**Files:**
- Create (not committed): `out/dataset-1004-4b2/` (the build)
- Create (not committed): a scratch probe script in the session scratchpad or `/tmp`
- Modify: `tests/test_shared_origin_training.py` (:1008 `FROZEN_SLICE_SHA256`, :1156 `EVAL_SET_SHA256`)
- Modify: `tests/test_exam_graded_view.py` (:232 `GRADED_VIEW_SHA256`)
- Modify: `tests/test_generate.py` (:1157 `OTHER_FAMILIES_SHA256`)
- Modify: `tests/test_answer_keys.py` (:139, :161, `WEAK_PAIRS` :225, the key-count test :255, the init-keys bot :278-303)
- Modify: `tests/test_score.py` (the catalog-workload counts in the test around :3560-3620)
- Modify: any other count pin the earlier task reports listed as red

**Interfaces:**
- Consumes: Tasks 1-4 as committed.
- Produces: the measured numbers Task 6 quotes, written into the task report.

- [ ] **Step 1: Build**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src .venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-1004-4b2
```

Expected: `out/dataset-1004-4b2/` holds `train.jsonl`, `val.jsonl`, `test.jsonl`, `manifest.json`. Row counts: train 6439, val 739, test 249 (the same as `out/dataset-1004`). If the folder already exists, stop and report; never overwrite.

- [ ] **Step 2: The gates**

a. Checker: every value under `manifest.json`'s `"checker_violations"` is 0.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -c "import json; v=json.load(open('out/dataset-1004-4b2/manifest.json'))['checker_violations']; print(v); assert not any(v.values())"
```

b. The `none_of_these` ceiling: `tests/test_shared_origin_floor.py::test_none_of_these_stays_under_the_ceiling` passes (CEILING 0.30, never moved). Record its share.

c. Unshown facts: save this as a scratch script (not in the repo) and run it with `PYTHONPATH=src .venv/bin/python <script>`:

```python
import json, re
from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import gold

FACT = re.compile(r"\b(?:\d+(?:\.\d+)?[A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]+|[a-z]+[A-Z][A-Za-z]+)\b")


def unshown_rows(path):
    bad = 0
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        wls = row["meta"]["workloads"]
        own = gold.own_lines(row["messages"][1]["content"], list(wls))
        hit = False
        for v in json.loads(row["messages"][2]["content"])["verdicts"]:
            wm = wls.get(v["workload"])
            if not isinstance(wm, dict) or wm.get("decided") or v["cause"] == c.NONE_OF_THESE:
                continue
            text = "\n".join(own[v["workload"]])
            hit |= any(t.lower() not in text for t in FACT.findall(v["rationale"]))
        bad += hit
    return bad


for folder in ("out/dataset-1004", "out/dataset-1004-4b2"):
    print(folder, {s: unshown_rows(f"{folder}/{s}.jsonl") for s in ("train", "val", "test")})
```

Expected: `out/dataset-1004-4b2` shows 0 for train, val and test. `out/dataset-1004` shows the before numbers (the spec quotes 714 train and 32 exam). Record both.

If any gate fails, stop and report BLOCKED with the numbers. Do not change a bar.

- [ ] **Step 3: Measure what moved**

Compare the two builds row by row (same order, same prompts) with a scratch script, and record:
- per split: verdicts whose cause changed; verdicts moved to `none_of_these`; `medium` → `high` moves, split into rules-decided rows and named rows; rows whose reason changed;
- the exam's job counts: `Counter(wm["job"] for row in test for wm in row["meta"]["workloads"].values() if isinstance(wm, dict))`, before and after.

These go in the report verbatim; Task 6 quotes them.

- [ ] **Step 4: Re-pin the hashes by hand**

Run the four hash tests, read each new digest from its failure, and replace the constant. Each gets a dated comment in the style already above it:

```python
# 2026-10-04 (Spec 4b-2): the catalog gold rests on anchors in own lines.
# Exam answers and meta move (reasons, causes, confidence, two entries'
# keys); no prompt byte moves (tests/test_catalog_gold.py).
# <old digest> ->
# <new digest>
```

- `FROZEN_SLICE_SHA256` (`tests/test_shared_origin_training.py:1008`)
- `EVAL_SET_SHA256` (`tests/test_shared_origin_training.py:1156`)
- `GRADED_VIEW_SHA256` (`tests/test_exam_graded_view.py:232`)
- `OTHER_FAMILIES_SHA256` (`tests/test_generate.py:1157`): its comment says "the other 229 must not move"; add that 4b-2 moves their answers and meta, not their prompts (Plan ruling 6).

`_PROBE_DECOYS_SHA256` must be green without a change. If it is red, stop and report BLOCKED.

- [ ] **Step 5: Re-pin the counts by hand**

`tests/test_answer_keys.py`:
- :139 `(total, non_empty) == (13946, 1084)` → the measured pair, with a dated comment giving the old pair.
- :161 `checked == 7976` → the measured count (expected 7972: the 4 gated coredns rows lose their keys); update the docstring's count line too.
- `WEAK_PAIRS` and `test_the_exam_has_34_keys_and_exactly_the_9_weak_pairs`: measure the key set and the pairs exactly as the test computes them. The pair count must be **fewer than 9**; if it is 9 or more, stop and report BLOCKED. Replace `WEAK_PAIRS` with the measured list (same tuple shape, a `#` comment above each group as now), rename the test to `test_the_exam_has_<K>_keys_and_exactly_the_<P>_weak_pairs` with the measured numbers, add a dated docstring line naming the old name, and update the comment above `WEAK_PAIRS` ("All <P> are left for Spec 4b-4 … A change that grows it fails here.").
- The init-keys bot (:278-303): the old-answer map becomes
  ```python
      old = {("init", "registry", "tag"): ["tag", "registry"],
             ("init", "pull"): ["registry", "tag"]}
  ```
  with a dated comment: init-imagepullbackoff's key is now `init`, `pull`; its old answer is still "registry tag", which lacks both. Measure the exam workloads on those two keys; if it is not 12, rename the test to the measured number. Re-pin `board["jobs"]["job2"]` to the measured `{"rate": …, "n": …}` with the old value in the comment.

`tests/test_score.py`: re-pin the catalog-workload counts in the test whose docstring speaks of 151 catalog workloads and the scoreboard's 175, with a dated docstring line explaining the move (two entries' keys changed; the gate moved no exam row).

Any other count pin an earlier report listed as red: re-pin it the same way, with the old value in the comment, and say in the report why it moved.

- [ ] **Step 6: Full suite and lint**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST` and `.venv/bin/ruff check --ignore EXE002 .`
Expected: every test passes (1912 at the base, plus the new ones); `All checks passed!`. No `-update` anywhere.

- [ ] **Step 7: Commit**

Stage only the test files you changed, by name:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_shared_origin_training.py tests/test_exam_graded_view.py tests/test_generate.py tests/test_answer_keys.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "test: re-pin the exam hashes and key counts for the catalog gold"
```

The report carries: the build path and row counts, the checker result, the `none_of_these` share, the unshown-fact counts before and after, the Step 3 measurements, every pin's old and new value, the weak-pair count and list, and the suite total.

---

### Task 6: Docs

**Files:**
- Modify: `contract/PIN.md` (a new dated 4b-2 entry; a line under "Dataset pin moves" :182; the "Left for Spec 4" node-cordon-diskfull line :483-486)
- Modify: `docs/model-card.md` (known limit 10 at :1128; the weak-keywords paragraph :928-934)
- Modify: `docs/how-training-works.md` (one line)
- Modify: `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md` (the "Left for 4b-2, 4b-3 and 4b-4" list, :732-736)

**Interfaces:**
- Consumes: Task 5's report numbers (the controller passes them in the dispatch). Never invent a number; every number comes from that report.
- Produces: nothing for code.

All text in simple voice: short sentences, plain words, numbers explained ("4 of 8,000 rows"). Never name the training host.

- [ ] **Step 1: `contract/PIN.md`**

Add a dated `2026-10-04 (Spec 4b-2)` entry in the same place and style as the 4b-1 entry. It says, each as a short bullet:
- the gold rule as it now applies to the catalog: an undecided workload names its entry's cause only when its own lines, minus lines naming a ruled-out or refuted cause, hold the kit's anchor; otherwise `none_of_these`, low, no keys, and the reason "<none phrase>; none of its own lines says why.";
- the gate fires on the measured train count (4 rows in the 8,000-row pool, all coredns `multi` rows whose read budget ran out before the log read) and on 0 exam rows;
- confidence: rules-decided rows are high; probe-failure and restart-loop named rows go to high; networkpolicy-deny-all stays medium; with the measured counts;
- the 8 changed causes (node-cordon-diskfull, networkpolicy-deny-all, init-config-error, init-imagepullbackoff, init-oomkilled, restart-loop, volume-attach-error, volume-mount-error) and the 7 changed recommendations;
- the measured counts from Task 5: unshown facts before and after, checker 0, `none_of_these` share, weak pairs 9 → P, exam job counts;
- the build folder `out/dataset-1004-4b2` and why it is not `out/dataset-1004`.

Under "Dataset pin moves" add one line with the four hashes, old → new. Mark the "Left for Spec 4" `node-cordon-diskfull` bullet closed: append "Closed 2026-10-04 by Spec 4b-2: its answer now names the cordoned node and the taints its own finding line prints."

- [ ] **Step 2: `docs/model-card.md`**

- Known limit 10 ("One story's answer names disk pressure its prompt never shows."): add a dated "Closed 2026-10-04 (Spec 4b-2)" note with the new cause and keys and the measured counts.
- The weak-keywords paragraph (:928-934): add a dated sentence that 4b-1 took the pinned pairs to 9 and 4b-2 to P (the measured number), because node-cordon-diskfull's key is now `unschedulable`, `taint`. Leave the history sentences as they are.

- [ ] **Step 3: `docs/how-training-works.md`**

Add one line where the doc describes the gold (near the case table, :92 area): "Every named gold, in every family, rests on an anchor in the workload's own lines. If the anchor is not there, the gold is `none_of_these`."

- [ ] **Step 4: The 4b-1 spec's "Left for" list**

Under `**4b-2: gold that says more than its prompt, in the other families.**` add: "Done 2026-10-04: see `docs/superpowers/specs/2026-10-04-catalog-gold-design.md`."

- [ ] **Step 5: Check and commit**

Run: `cd /home/ubuntu/git/kubeagent-verdict && $PYTEST -q tests/test_docs*.py 2>/dev/null; $PYTEST` (doc tests, if any, must pass) and `.venv/bin/ruff check --ignore EXE002 .`

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add contract/PIN.md docs/model-card.md docs/how-training-works.md docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "docs: record the catalog gold (Spec 4b-2)"
```
