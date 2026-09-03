# Shared-origin scenario diversity — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the shared-origin training pool from 4 scenarios to 20, make the discriminating origin read vary inside each scenario, and require that discriminator to carry a word rather than only a number — so the next retrain cannot fit the shared-origin rule by memorising four scenario templates.

**Architecture:** Two optional fields on the frozen `Propagation` dataclass (`origin_variants`, `origin_state`), one ~4-line draw site in `cases._render_shared_origin`, sixteen new `Propagation` literals appended to `_TRAINING_SCENARIOS`, and one rewrite of `kube-proxy-degraded`'s discriminator. Everything else is tests. `CASE_MIX` is frozen, the exam is frozen and pinned by hash, and no model is trained.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), pytest, stdlib `random`/`dataclasses`. No new dependency.

**Spec:** [docs/superpowers/specs/2026-09-03-shared-origin-scenario-diversity-design.md](../specs/2026-09-03-shared-origin-scenario-diversity-design.md) (committed on this branch as `6661859`)

## Global Constraints

- **Branch:** `shared-origin-scenario-diversity`, off `main` @ `ee2980e`. Never implement on `main`.
- **Every commit** uses `git commit -s` (DCO). Identity is `imantaba <itn.taba@gmail.com>`.
- **No AI attribution anywhere** — no `Co-Authored-By: Claude` trailer, no "generated with" line, no mention of a model doing the work, in any commit message, code comment, doc line or changelog entry.
- **No secrets, credentials, private IPs, internal hostnames or kubeconfig paths in any tracked file.** The banned identifier shapes are already a test: a dotted quad, `https?://`, `kubeconfig` (any case), `/home/`, and `@`. New scenario prose must contain none of them.
- **Python is `.venv/bin/python` (3.12).** The system `python3` is 3.14 — never use it. Run tests with `.venv/bin/python -m pytest`.
- **NEVER run `kv-train`, `kv-export`, `chaos/run.sh`, or any test with `-update`.** This plan authorises **no training run**. A retrain is ~17.5 hours on a separate host and is a decision that happens after all five verification checks pass, not inside this plan.
- **`CASE_MIX` is frozen** (`src/kubeagent_verdict/dataset/generate.py:57`). `shared_origin` stays at 4 and `shared_origin_decoy` at 4. Do not touch it.
- **The exam is frozen.** `generate.test_set()` must stay 263 rows with sha256 `e8cbb549289ebaf07ba817dd3d32fdf70724c0ae80410eb47d2228a3b22b49de`, over `json.dumps([to_row(e) for e in test_set()], sort_keys=True, ensure_ascii=False)`. Task 1 pins it; if it ever moves, every banked scoreboard comparison is void and the change is wrong.
- **The eval six are not edited.** `propagation.all_scenarios()` keeps its current text and declares neither `origin_variants` nor `origin_state`.
- **`docs/model-card.md` is not touched** — it describes released weights and nothing is released here.
- **`contract/golden/` does not move** — `tests/test_golden.py` pins the prompt contract against real kubeagent bytes, not the generated dataset.
- **An invariant that could not fail the pool it lands on is not an invariant.** Constraint 13 fails `kube-proxy-degraded` on the day it lands; that is deliberate and is why Task 3 rewrites it.
- **A comment or doc line that promises something the code does not keep is a defect, not a deferrable minor.** Two remedies: close the gap, or narrow the claim.

---

## File Structure

| file | responsibility after this plan |
| --- | --- |
| `src/kubeagent_verdict/dataset/propagation.py` | the scenario tables — eval six unchanged, trainable pool grows 4 → 20, two new optional `Propagation` fields, module docstring records the authoring guidance that cannot be tested |
| `src/kubeagent_verdict/dataset/cases.py` | one new draw site in `_render_shared_origin` (~4 lines + comment); nothing else moves |
| `tests/test_shared_origin_training.py` | the trainable pool's invariants (constraints 4, 6, 8, 9, 10, 12, 13, 14, 15) and the exam-identity hash pin |
| `tests/test_shared_origin_training_pair.py` | the pair invariants, extended: a pair draws the same variant, and a scenario renders more than one |
| `tests/test_propagation.py` | the eval six declare no variants and no state |
| `docs/how-training-works.md` | what changed and why, in the existing voice |

---

## Task 1: Pin the exam by hash

Small and mechanical, and it goes first because it protects every task after it. The existing `test_the_eval_set_is_two_hundred_and_sixty_three_rows` guards the row *count* but not the contents — 263 rows of different text would pass it.

**Files:**
- Modify: `tests/test_shared_origin_training.py` (imports at line 40; new test in the `# --- the eval must not move` section, immediately after `test_the_eval_set_is_two_hundred_and_sixty_three_rows` at line 308)

**Interfaces:**
- Consumes: `generate.test_set()`, `generate.to_row(e)` — note `to_row` is a **module function**, not a method on `Example`.
- Produces: module constant `EVAL_SET_SHA256` in `tests/test_shared_origin_training.py`. No later task reads it.

- [ ] **Step 1: Write the failing test**

Add `import hashlib` and `import json` to the import block at the top of `tests/test_shared_origin_training.py` (it currently starts `import re`; keep stdlib imports alphabetical: `hashlib`, `json`, `re`).

Then add, directly after `test_the_eval_set_is_two_hundred_and_sixty_three_rows`:

```python
# Captured on `main` @ `ee2980e` and re-confirmed on this branch before any
# edit. The 263 rows are the exam in its current shape, and this hash is not a
# claim that every past number was measured against them: 0902 is the only
# banked run scored against exactly this set in one go; 0901 covered the same
# rows as two runs (253 plus the ten `shared_origin_decoy_probe` rows), which
# is why its paired join reported `unpaired`; and 0830 predates those ten rows
# entirely, covering only the other 253. What the hash buys is forward-looking
# -- every number measured from here on stays comparable -- so a change that
# moves it is wrong unless it means to retire the comparison. The row count
# above cannot see a rewrite that keeps the count.
EVAL_SET_SHA256 = "e8cbb549289ebaf07ba817dd3d32fdf70724c0ae80410eb47d2228a3b22b49de"


def test_the_eval_set_is_byte_identical_to_the_one_every_scoreboard_used():
    blob = json.dumps([generate.to_row(e) for e in generate.test_set()],
                      sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    assert digest == EVAL_SET_SHA256, (
        "the exam moved; every banked scoreboard comparison is now void")
```

- [ ] **Step 2: Run it and watch it pass, then prove it is not vacuous**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -k byte_identical -q`
Expected: PASS.

A test that passes on first write has to be shown to be able to fail. Temporarily change the last character of `EVAL_SET_SHA256` from `e` to `f`, re-run, confirm it FAILS with the message above, then change it back and re-run to confirm PASS. Do not commit the mutated constant.

- [ ] **Step 3: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (330 collected before this task, 331 after).

- [ ] **Step 4: Commit**

```bash
git add tests/test_shared_origin_training.py
git commit -s -m "test: pin the eval set by hash, not only by row count"
```

---

## Task 2: The two new fields and the variant draw

The mechanism, with no scenario using it yet. After this task the pool renders exactly as it does today, byte for byte, because no scenario declares variants.

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (the `Propagation` dataclass — add two fields after `healthy_origin_content`, before `shared_verdict`)
- Modify: `src/kubeagent_verdict/dataset/cases.py` (`_render_shared_origin`, the draw after line 526 and the assignment at line 538)
- Test: `tests/test_shared_origin_training.py`

**Interfaces:**
- Produces: `Propagation.origin_variants: tuple[tuple[str, str], ...] = ()` — each entry is `(broken content, healthy content)`. `Propagation.origin_state: tuple[str, str] = ("", "")` — `(broken token, healthy token)`. Tasks 3 and 5–8 populate both on every trainable scenario; Task 4 and Task 9 assert over them.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_shared_origin_training.py`, at the end of the scenario-rule block (after `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`):

```python
def test_a_scenario_with_variants_renders_more_than_one_of_them():
    """The mechanism, exercised on a scenario built for the test.

    Asserted here rather than only on the real pool because the real pool's
    scenarios are added in later commits, and a draw site that silently
    ignored `origin_variants` would otherwise land green.
    """
    import dataclasses
    import random

    from kubeagent_verdict.dataset import cases

    base = propagation.trainable_scenarios()[0]
    variants = tuple(
        (f"state: broken variant {i}\n{base.origin_read[1]}",
         f"state: healthy variant {i}\n{base.healthy_origin_content}")
        for i in range(4))
    p = dataclasses.replace(base, origin_variants=variants)

    seen = set()
    for salt in range(40):
        e = cases.shared_origin(p, random.Random(salt), victims=2)
        seen |= {i for i, (b, _h) in enumerate(variants)
                 if b.split("\n")[0] in e.user}
    assert len(seen) > 1, f"only variant(s) {seen} ever rendered"


def test_a_pair_built_from_one_salt_draws_the_same_variant():
    """`generate.py:156-159` spends one salt twice, so the twins replay one
    stream. The draw sits before the `healthy` branch precisely so both halves
    reach it in the same RNG state -- otherwise a pair could contrast variant
    2's broken blob against variant 0's healthy one, which is two changes at
    once and no longer isolates the origin's state.
    """
    import dataclasses
    import random

    from kubeagent_verdict.dataset import cases

    base = propagation.trainable_scenarios()[0]
    variants = tuple(
        (f"state: broken variant {i}\n{base.origin_read[1]}",
         f"state: healthy variant {i}\n{base.healthy_origin_content}")
        for i in range(4))
    p = dataclasses.replace(base, origin_variants=variants)

    for salt in range(40):
        one = cases.shared_origin(p, random.Random(salt), victims=2)
        other = cases.shared_origin_decoy(p, random.Random(salt), victims=2)
        drawn = [i for i, (b, _h) in enumerate(variants)
                 if b.split("\n")[0] in one.user]
        assert len(drawn) == 1, f"salt {salt}: {len(drawn)} broken variants matched"
        assert variants[drawn[0]][1].split("\n")[0] in other.user, (
            f"salt {salt}: the twin drew a different variant")


def test_a_scenario_without_variants_renders_exactly_what_it_did_before():
    """The eval six declare none and must consume the RNG identically."""
    import random

    from kubeagent_verdict.dataset import cases

    for p in propagation.all_scenarios():
        assert p.origin_variants == (), p.key
        e = cases.shared_origin_probe(p, random.Random(3))
        assert p.origin_read[1].split("\n")[0] in e.user, p.key
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -k "variant" -q`
Expected: FAIL — `dataclasses.replace` raises `TypeError: got an unexpected keyword argument 'origin_variants'`.

- [ ] **Step 3: Add the two fields**

In `src/kubeagent_verdict/dataset/propagation.py`, inside the frozen `Propagation` dataclass, immediately after `healthy_origin_content: str = ""` and before `shared_verdict: str = "outranked"`:

```python
    # The discriminating read, rendered several ways. Each entry is
    # (broken content, healthy content) and entry 0 must equal
    # (origin_read[1], healthy_origin_content) -- three call sites read those
    # two directly, and making the legacy pair one of the drawn variants is
    # what keeps them showing content the model has actually seen. Empty on
    # the eval six: the exam is frozen and must consume the same RNG.
    origin_variants: tuple[tuple[str, str], ...] = ()
    # (broken token, healthy token). A word, not only a number -- the two
    # scenarios that failed at eval were separated by a quantity and the two
    # that passed by a lexical state token. Enforced over the trainable pool
    # only; the eval six are asked, not taught.
    origin_state: tuple[str, str] = ("", "")
```

- [ ] **Step 4: Add the draw**

In `src/kubeagent_verdict/dataset/cases.py`, immediately after line 526 (`drawn, scope_value = _propagation_names(p, rng, count)`) and its two following comment lines about the pinned field, insert the draw. Place it **before** the `anchor = drawn[0]` block so it is the last RNG consumer that both halves reach identically:

```python
    # The discriminating read varies inside a scenario, so what separates the
    # two halves is the relation the contents stand for rather than two literal
    # strings the model can memorise. Drawn from the passed-in rng, before the
    # `healthy` branch: `generate.py:156-159` draws ONE salt and builds a
    # separate `random.Random(salt)` for each half, so both replay an identical
    # stream and both draw the SAME variant -- exactly the way they already
    # draw the same names. Only when the scenario declares variants; the eval
    # six declare none and must consume the RNG exactly as they did before.
    broken_origin, healthy_origin = p.origin_read[1], p.healthy_origin_content
    if p.origin_variants:
        broken_origin, healthy_origin = rng.choice(p.origin_variants)
```

Then change line 538 from

```python
    origin_content = p.healthy_origin_content if healthy else p.origin_read[1]
```

to

```python
    origin_content = healthy_origin if healthy else broken_origin
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -k "variant" -q`
Expected: PASS.

- [ ] **Step 6: Run the whole suite, including the exam hash**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. In particular `test_the_eval_set_is_byte_identical_to_the_one_every_scoreboard_used` (Task 1) and the whole of `tests/test_shared_origin_training_pair.py` must still pass — nothing declares variants yet, so nothing rendered may have changed.

- [ ] **Step 7: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py src/kubeagent_verdict/dataset/cases.py tests/test_shared_origin_training.py
git commit -s -m "feat(dataset): let a propagation scenario declare several renderings of its origin read"
```

---

## Task 3: Retrofit the four existing scenarios, and rewrite `kube-proxy-degraded`

The four scenarios in the pool today get `origin_variants` and `origin_state`, and constraints 12 and 13 land as tests. `kube-proxy-degraded`'s discriminator is `11m` versus `3s` — there is no state word to name, and that scenario answered "shared" on all four halves of both its pairs at eval. It is rewritten here.

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (`_T_CA`, `_T_KUBE_PROXY`, `_T_CONFIGMAP`, `_T_SCALED_TO_ZERO`)
- Test: `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `Propagation.origin_variants` and `Propagation.origin_state` from Task 2; the draw site in `cases._render_shared_origin`.
- Produces: four trainable scenarios each declaring exactly 4 variants and a state pair. Tasks 5–8 copy this shape; Task 9 measures over it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shared_origin_training.py`, in the scenario-rule block:

```python
def test_every_trainable_scenario_declares_at_least_four_origin_variants():
    """Four literal strings per scenario is a lookup; several renderings of one
    relation is not. Variant 0 must be the legacy pair because three call sites
    read `origin_read[1]` / `healthy_origin_content` without going through the
    draw -- `multi`'s healthy-origin read (cases.py:788-789), the banned-shape
    blob, and the healthy-read invariant -- and they must keep showing content
    the model has actually seen.
    """
    for p in propagation.trainable_scenarios():
        assert len(p.origin_variants) >= 4, f"{p.key}: {len(p.origin_variants)}"
        assert p.origin_variants[0] == (p.origin_read[1], p.healthy_origin_content), (
            f"{p.key}: variant 0 is not the legacy pair")


def test_every_variant_first_line_is_literal_and_unique_within_its_scenario():
    """Two tests and one measurement identify a rendered variant by its first
    line, so a first line carrying `{ns}` or repeated across variants would
    make them silently unable to tell variants apart.
    """
    for p in propagation.trainable_scenarios():
        firsts = []
        for broken, healthy in p.origin_variants:
            for content in (broken, healthy):
                first = content.split("\n")[0]
                assert "{" not in first, f"{p.key}: placeholder in {first!r}"
                assert first.strip(), f"{p.key}: empty first line"
                firsts.append(first)
        assert len(set(firsts)) == len(firsts), f"{p.key}: duplicate first line"


def test_every_trainable_scenario_names_its_state_in_words():
    """The 0.5 in-distribution score decomposes into two scenarios read and two
    constant. The two read are separated by a lexical state token; the two
    constant by a quantity, and the UNIT ablation showed making the units
    consistent moved nothing. So a discriminator that is only a number is a
    discriminator two of four scenarios demonstrably did not read.

    Necessary and demonstrably not sufficient: `internal-ca-expired` already
    satisfies this and still failed. The other half -- "the token is not buried
    in a numeric phrase" -- is authoring guidance in the module docstring,
    because no honest test expresses it.
    """
    for p in propagation.trainable_scenarios():
        broken_token, healthy_token = p.origin_state
        assert broken_token.strip(), f"{p.key}: no broken state token"
        assert healthy_token.strip(), f"{p.key}: no healthy state token"
        assert re.search(r"[A-Za-z]", broken_token), f"{p.key}: {broken_token!r}"
        assert re.search(r"[A-Za-z]", healthy_token), f"{p.key}: {healthy_token!r}"
        for broken, healthy in p.origin_variants:
            assert broken_token in broken, f"{p.key}: {broken_token!r} missing"
            assert healthy_token not in broken, f"{p.key}: {healthy_token!r} in a broken read"
            assert healthy_token in healthy, f"{p.key}: {healthy_token!r} missing"
            assert broken_token not in healthy, f"{p.key}: {broken_token!r} in a healthy read"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -k "origin_variants or first_line or state_in_words" -q`
Expected: all three FAIL — every scenario declares `origin_variants == ()` and `origin_state == ("", "")`.

- [ ] **Step 3: Rewrite `kube-proxy-degraded`'s discriminator**

In `_T_KUBE_PROXY`, replace `origin_read` and `healthy_origin_content` with contents that name the state:

```python
    origin_read=(
        "describe node {node}",
        ("Service route programming: stale\n"
         "last sync 11m ago (peers synced 4s ago)\n"
         "Conditions:\n"
         "  Ready   True   KubeletReady   kubelet is posting ready status\n"
         "kube-proxy pod on this node: 1/1 Running, 0 restarts"),
    ),
    healthy_origin_content=(
        "Service route programming: fresh\n"
        "last sync 3s ago (peers synced 4s ago)\n"
        "Conditions:\n"
        "  Ready   True   KubeletReady   kubelet is posting ready status\n"
        "kube-proxy pod on this node: 1/1 Running, 0 restarts"
    ),
```

The label `describe node {node}` does **not** change: it is the seam `origin_read_label` travels on, and `multi`'s negative case pairs on it.

- [ ] **Step 4: Add the variants and the state tuple to all four scenarios**

Add `origin_state=` and `origin_variants=` to each, directly after `healthy_origin_content=` and before `victims=`. Variant 0 repeats the legacy pair verbatim in every case — that is what the test asserts.

`_T_CA` — token pair `("expired", "remaining")`:

```python
    origin_state=("expired", "remaining"),
    origin_variants=(
        (("notAfter: expired 2h ago\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 14 across 6 namespaces"),
         ("notAfter: 288 days remaining\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 14 across 6 namespaces")),
        (("notAfter: expired 41m ago\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 9 across 4 namespaces"),
         ("notAfter: 112 days remaining\n"
          "issuer: cluster-internal-ca\n"
          "workloads mounting this bundle: 9 across 4 namespaces")),
        (("notAfter: expired 6d ago\n"
          "issuer: cluster-internal-ca\n"
          "served to: 23 workloads across 8 namespaces"),
         ("notAfter: 401 days remaining\n"
          "issuer: cluster-internal-ca\n"
          "served to: 23 workloads across 8 namespaces")),
        (("validity: expired\n"
          "bundle: cluster-internal-ca\n"
          "renewal: no successful renewal recorded\n"
          "mounted by: 6 workloads"),
         ("validity: 74 days remaining\n"
          "bundle: cluster-internal-ca\n"
          "renewal: last renewal completed\n"
          "mounted by: 6 workloads")),
    ),
```

`_T_KUBE_PROXY` — token pair `("stale", "fresh")`, variant 0 being the rewritten pair from Step 3:

```python
    origin_state=("stale", "fresh"),
    origin_variants=(
        (("Service route programming: stale\n"
          "last sync 11m ago (peers synced 4s ago)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kube-proxy pod on this node: 1/1 Running, 0 restarts"),
         ("Service route programming: fresh\n"
          "last sync 3s ago (peers synced 4s ago)\n"
          "Conditions:\n"
          "  Ready   True   KubeletReady   kubelet is posting ready status\n"
          "kube-proxy pod on this node: 1/1 Running, 0 restarts")),
        (("route table on this node: stale\n"
          "no route update applied for 14m while peers are within 5s\n"
          "kube-proxy pod on this node: 1/1 Running"),
         ("route table on this node: fresh\n"
          "last route update applied 2s ago, within 5s of peers\n"
          "kube-proxy pod on this node: 1/1 Running")),
        (("kube-proxy reports its Service route table stale\n"
          "last successful sync: 9m ago\n"
          "peer nodes applied their tables seconds ago"),
         ("kube-proxy reports its Service route table fresh\n"
          "last successful sync: 4s ago\n"
          "peer nodes applied their tables seconds ago")),
        (("Service route sync: stale\n"
          "endpoint changes queued and unapplied: 62\n"
          "kube-proxy has not logged a sync in 12m"),
         ("Service route sync: fresh\n"
          "endpoint changes queued and unapplied: 0\n"
          "kube-proxy logged its last sync 3s ago")),
    ),
```

`_T_CONFIGMAP` — token pair `("NotFound", "keys")`. Note the case: the victim reads say `configmap "app-settings" not found`, which does **not** contain `NotFound`. Do not lower-case the token.

```python
    origin_state=("NotFound", "keys"),
    origin_variants=(
        (("Error from server (NotFound): the ConfigMap app-settings does not exist\n"
          "namespace {ns}: Active\n"
          "pods in {ns} referencing it: 6 of 6"),
         ("Name: app-settings, 7 keys\n"
          "namespace {ns}: Active\n"
          "pods in {ns} referencing it: 6 of 6")),
        (("app-settings: NotFound\n"
          "namespace {ns}: Active\n"
          "workloads in {ns} mounting it: 4 of 4"),
         ("app-settings: present, 5 keys\n"
          "namespace {ns}: Active\n"
          "workloads in {ns} mounting it: 4 of 4")),
        (("the shared app-settings ConfigMap: NotFound\n"
          "last seen in the namespace event log 12m ago\n"
          "pods in {ns} referencing it: 9 of 9"),
         ("the shared app-settings ConfigMap: 11 keys\n"
          "last written 12m ago\n"
          "pods in {ns} referencing it: 9 of 9")),
        (("the ConfigMap every flagged workload mounts resolves NotFound\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "mounted by every workload flagged here"),
         ("the ConfigMap every flagged workload mounts resolves with 6 keys\n"
          "namespace {ns}: Active, no deletion timestamp\n"
          "mounted by every workload flagged here")),
    ),
```

`_T_SCALED_TO_ZERO` — token pair `("replicas to 0", "Running")`. Note the healthy legacy content already says `Last scale event: none in the last 24h`, so `none` cannot be the broken token.

```python
    origin_state=("replicas to 0", "Running"),
    origin_variants=(
        (("Replicas:  0 desired | 0 updated | 0 total | 0 available\n"
          "Pods:      none\n"
          "Last scale event: 34m ago, 4 replicas to 0"),
         ("Replicas:  4 desired | 4 updated | 4 total | 4 available\n"
          "Pods:      4 Running, 0 restarts\n"
          "Last scale event: none in the last 24h")),
        (("Last scale event: 2h ago, 6 replicas to 0\n"
          "Replicas:  0 desired | 0 updated | 0 total | 0 available\n"
          "Pods:      none"),
         ("Last scale event: none in the last 7d\n"
          "Replicas:  6 desired | 6 updated | 6 total | 6 available\n"
          "Pods:      6 Running, 0 restarts")),
        (("desired replicas: 0, available: 0\n"
          "scale history: 11m ago, 3 replicas to 0\n"
          "no pod has been scheduled for this Deployment since"),
         ("desired replicas: 3, available: 3\n"
          "scale history: unchanged for 9d\n"
          "3 pods Running for this Deployment")),
        (("the session Deployment was scaled from 5 replicas to 0\n"
          "current pods: 0\n"
          "no endpoint is registered for its Service"),
         ("the session Deployment holds 5 replicas\n"
          "current pods: 5 Running\n"
          "5 endpoints are registered for its Service")),
    ),
```

- [ ] **Step 5: Add the two `healthy_read_content` swaps constraint 10 exists for**

Two victim reads assert a broken origin and would otherwise render unchanged next to a *healthy* origin read on the decoy half. Task 4 mechanises the token half of this; these two are the judgment half, applied now.

In `_T_CA`'s third victim (the `StatefulSet`, whose read is `classified cause: peer certificate rejected as expired`), add after `read=(...)`:

```python
            healthy_read_content=("classified cause: peer certificate rejected as "
                                  "untrusted (3 of 3 sampled restarts)"),
```

In `_T_CONFIGMAP`'s first victim (the `Deployment`) and third victim (the `StatefulSet`), both of whose reads name `configmap "app-settings" not found` — the same ConfigMap the healthy origin read shows present — add respectively:

```python
            healthy_read_content=("Events: Warning  Failed  kubelet  Error: couldn't "
                                  "find key api-timeout in ConfigMap {ns}/checkout-settings"),
```

```python
            healthy_read_content=("Warning  Failed  kubelet  Error: configmap "
                                  "\"{name}-revision-settings\" not found"),
```

Each is consistent with that victim's own `local_cause` — "the key {container} reads was removed from its own ConfigMap" and "the StatefulSet was rolled to a revision that mounts a new ConfigMap" — which is the point: on the decoy half each workload fails for its own reason and the shared ConfigMap is fine.

- [ ] **Step 6: Correct the stale claim on `healthy_read_content`**

`Victim.healthy_read_content`'s comment in `propagation.py` says:

```
    # Only `shared_origin_decoy_probe` renders this, and it needs one wherever
```

That was true when the probe was the only case rendering a healthy origin. `shared_origin_decoy` renders it too -- `cases.py:555` sits inside `_render_shared_origin`, which both reach through the `healthy=True` branch -- and Step 5 above has just added three of them to trainable scenarios, which the comment says does not happen. A doc line that promises something the code does not keep is a defect to fix, not a deferrable minor. Narrow the claim:

```
    # Rendered by BOTH healthy-origin cases -- `shared_origin_decoy` (training)
    # and `shared_origin_decoy_probe` (eval) -- and needed wherever
```

Leave the rest of the comment, including the count of eval victims needing none, unchanged: that sentence is scoped to the eval sixteen and is still true.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -q`
Expected: PASS, including the three new tests.

- [ ] **Step 8: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Watch three in particular:
- `test_the_eval_set_is_byte_identical_to_the_one_every_scoreboard_used` — the exam must not have moved.
- `tests/test_shared_origin_training_pair.py` in full — the pair invariants must survive a rendering that now varies.
- `test_a_negative_multi_row_shows_the_component_healthy` — it keys on `origin_read[0]` and the legacy contents, both of which still exist.

If `test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim` or `test_no_trainable_answer_both_denies_sharing_and_speaks_its_language` fails on the new `healthy_read_content` strings, the fix is to reword the string, not to relax the test.

- [ ] **Step 9: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git commit -s -m "feat(dataset): vary the origin read in the four existing trainable scenarios

kube-proxy-degraded's discriminator was 11m versus 3s -- a quantity, which
the eval measured that scenario never reading. It now names its state."
```

---

## Task 4: The remaining pool invariants, and freeze the eval six

Constraints 4, 6, 8, 9, 10 and the constraint-14 extension. All six pass on the pool as it stands — they were checked against it before this plan was written — so they land green here and then gate the sixteen scenarios Tasks 5–8 add.

**Files:**
- Modify: `tests/test_shared_origin_training.py`
- Modify: `tests/test_propagation.py`

**Interfaces:**
- Consumes: `Propagation.origin_variants`, `Propagation.origin_state`, `Victim.healthy_read_content`.
- Produces: nothing later tasks import.

- [ ] **Step 1: Write the tests**

Add to `tests/test_shared_origin_training.py`, in the scenario-rule block:

```python
_SCOPE_FOR_RADIUS = {"cluster": None, "node": "node", "namespace": "ns"}


def test_blast_radius_and_scope_field_agree():
    """A node-scoped origin is only coherent if every victim is on that node.
    `_propagation_names` pins the field named by `scope_field`, so a radius
    that disagrees with it asserts a blast radius its own inventory
    contradicts.
    """
    for p in propagation.trainable_scenarios():
        assert p.scope_field == _SCOPE_FOR_RADIUS[p.blast_radius], p.key


def test_no_two_trainable_scenarios_share_an_answer_string():
    """A cause string reused across scenarios is a lookup key spanning both."""
    seen = {}
    for p in propagation.trainable_scenarios():
        for field, value in (("shared_cause", p.shared_cause),
                             ("distractor_cause", p.distractor_cause)):
            assert value not in seen, f"{p.key}.{field} repeats {seen[value]}"
            seen[value] = f"{p.key}.{field}"


def test_no_two_trainable_scenarios_share_a_local_cause():
    """Same reason, on the decoy half's answers."""
    seen = {}
    for p in propagation.trainable_scenarios():
        for v in p.victims:
            assert v.local_cause not in seen, (
                f"{p.key}: local_cause repeats {seen[v.local_cause]}")
            seen[v.local_cause] = p.key


def test_pass_confidence_varies_within_every_trainable_scenario():
    """Guidance in the module docstring until now. With sixteen new scenarios
    written at once, "vary the confidence" as guidance will not hold, and a
    scenario whose victims all carry one grade reopens the confidence-copy
    shortcut the docstring says is closed.
    """
    for p in propagation.trainable_scenarios():
        grades = {v.pass_confidence for v in p.victims}
        assert len(grades) > 1, f"{p.key}: every victim carries {grades}"


def test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half():
    """The mechanised half of constraint 10.

    On the decoy half the origin read shows the component healthy. A victim
    read that still carries the scenario's broken state token contradicts it
    in the same prompt, and the row teaches nothing except that the evidence
    disagrees with itself. Deciding whether a read "asserts the origin is
    broken" is a judgment about English and is not mechanised; the token is
    the case where it is mechanical, and it is checked.
    """
    for p in propagation.trainable_scenarios():
        broken_token = p.origin_state[0]
        if not broken_token:
            continue
        for v in p.victims:
            if broken_token not in v.read[1]:
                continue
            assert v.healthy_read_content, (
                f"{p.key}: a victim read carries {broken_token!r} with no healthy swap")
            assert broken_token not in v.healthy_read_content, (
                f"{p.key}: the healthy swap still carries {broken_token!r}")
```

Then extend the banned-shape test's blob. In `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`, change the list being joined so it also covers the variants and the state tokens — a banned shape appearing only inside a variant is invisible to the blob as it stands:

```python
        blob = "\n".join([p.origin, p.shared_cause, p.shared_reason,
                          p.distractor_cause, p.distractor_reason, p.rationale,
                          p.remedy, p.origin_read[0], p.origin_read[1],
                          p.healthy_origin_content,
                          p.origin_state[0], p.origin_state[1]]
                         + [f"{b}\n{h}" for b, h in p.origin_variants]
                         + [f"{v.reason}\n{v.evidence}\n{v.log_cause}\n"
                            f"{v.local_cause}\n{v.local_reason}\n"
                            f"{v.read[0]}\n{v.read[1]}\n{v.healthy_read_content}"
                            for v in p.victims])
```

Note it also picks up `healthy_read_content`, which the blob did not see either.

Add to `tests/test_propagation.py`:

```python
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
```

- [ ] **Step 2: Run them**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py -q`
Expected: PASS. These invariants were verified against the current pool before this plan was written; a failure here means Task 3 introduced a collision — most likely a duplicated `local_cause` or a `healthy_read_content` that still carries the broken token. Fix the scenario, not the test.

- [ ] **Step 3: Prove the new tests are not vacuous**

For each of the five new tests in `tests/test_shared_origin_training.py`, temporarily break one scenario so that test fails, confirm the failure names the scenario, and revert. Suggested mutations: set `_T_KUBE_PROXY`'s `scope_field` to `None`; copy `_T_CA`'s `shared_cause` onto `_T_CONFIGMAP`; copy one `local_cause` across two scenarios; set every `pass_confidence` in `_T_KUBE_PROXY` to `"high"`; delete the `healthy_read_content` added to `_T_CA`'s third victim. Revert every mutation before committing and re-run.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_shared_origin_training.py tests/test_propagation.py
git commit -s -m "test: gate the trainable pool on the invariants the new scenarios must meet"
```

---

## A note on Tasks 5–8

The spec settles what these four tasks contain, and it is worth repeating here so a reviewer does not read the next four tasks as under-specified:

> The prose — the exact origin read, the victim evidence, the decoy causes — is written at implementation time against the rules in *Authoring constraints* below, and the tests are the gate.

Sixteen scenarios is roughly 1100 lines of literal. Pasting them into the plan would make the plan the implementation, and would fix at planning time prose that has to be written against the file it lands in. So each of Tasks 5–8 carries: the four scenarios' **fixed** properties (key, blast radius, scope field, victim issue kinds — all from the spec's tables, none negotiable), the **complete** fifteen-constraint checklist, and the tests that gate it. The shape to transcribe is `_T_CA` in `propagation.py` itself, in the same file being edited — not another task in this plan.

Each task adds its four scenarios to `_TRAINING_SCENARIOS` and runs the whole suite. The invariants from Tasks 3 and 4 are already in place, so a scenario that violates one fails on the spot rather than at the end.

---

## Task 5: Four cluster-radius scenarios

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (four new `Propagation` literals before `_TRAINING_SCENARIOS`, and four new names appended to that tuple)

**Interfaces:**
- Consumes: `Propagation`, `Victim`, `origin_variants`, `origin_state` — all defined in Task 2 and already used by the four scenarios in the file.
- Produces: `_T_IMAGE_PULL_SECRET`, `_T_SECRET_KEY_RENAMED`, `_T_AUTOSCALER_CAPACITY`, `_T_SIDECAR_INJECTOR`, appended to `_TRAINING_SCENARIOS` in that order.

**The four scenarios (fixed by the spec — do not renegotiate):**

| key | radius | scope_field | victim issue kinds |
| --- | --- | --- | --- |
| `image-pull-secret-expired` | cluster | `None` | `ErrImagePull`, `ImagePullBackOff`, `Init:ErrImagePull`, `Init:ImagePullBackOff` |
| `shared-secret-key-renamed` | cluster | `None` | `CreateContainerConfigError`, `CrashLoopBackOff` |
| `cluster-autoscaler-at-capacity` | cluster | `None` | `Unschedulable`, `Unschedulable` |
| `sidecar-injector-broken` | cluster | `None` | `Init:CrashLoopBackOff`, `CrashLoopBackOff`, `ProbeFailure` |

The origin in each case: a registry pull secret whose token expired; a shared Secret whose key was renamed by a platform change; the cluster autoscaler unable to add a node; a mutating webhook injecting a sidecar that cannot start.

**One deliberate deviation from the spec's table.** The spec gives `image-pull-secret-expired` three victims, `ErrImagePull` / `ImagePullBackOff` / `Init:ErrImagePull`. That table and constraint 15 were written independently, and they do not agree: measured against the pool as it stands, `Init:ImagePullBackOff` is the one kind in `vocab.ISSUE_KINDS` that no existing scenario and no other of the sixteen new ones carries, so constraint 15 would fail at Task 9 with the spec's table taken literally. A fourth victim -- an init container stuck in `Init:ImagePullBackOff` behind the same expired pull secret -- is the natural home for it, stays inside constraint 7's 2-4 range, and is the smaller change. The alternative, narrowing constraint 15 to fifteen kinds, would weaken the only pool-level coverage check the slice has.

- [ ] **Step 1: Read the shape**

Read `_T_CA` in `src/kubeagent_verdict/dataset/propagation.py` end to end, including its `origin_state` and `origin_variants` (added in Task 3). It is the shape every new scenario copies: a `Propagation` with `key`, `origin`, `blast_radius`, `scope_field`, `shared_cause`, `shared_reason`, `distractor_cause`, `distractor_reason`, `rationale`, `remedy`, `confidence`, `origin_read`, `healthy_origin_content`, `origin_state`, `origin_variants`, `victims`. Read the module docstring too — it carries the authoring rules that are guidance rather than tests.

- [ ] **Step 2: Write the four scenarios**

Each one must satisfy all fifteen constraints. Nine of them are tests that already run; six are authoring judgment. The full list:

1. `key` matches `^[a-z0-9]+(-[a-z0-9]+)*$`. **(tested)**
2. `key` is not one of the six in `all_scenarios()`. **(tested)**
3. `shared_cause` and `distractor_cause` appear in no eval scenario. **(tested)**
4. `shared_cause` and `distractor_cause` are unique across the whole trainable pool. **(tested)**
5. Every `local_cause` within the scenario is distinct. **(tested)**
6. Every `local_cause` is distinct across the whole trainable pool. **(tested)**
7. 2–4 victims, each `issue` in `vocab.ISSUE_KINDS` — use the kinds in the table above verbatim. **(tested)**
8. `pass_confidence` is not the same on every victim. **(tested)**
9. `scope_field` agrees with `blast_radius` — `cluster` → `None`. **(tested)**
10. A victim read that asserts the origin is broken declares a `healthy_read_content` that does not. The token half is tested; the English half is judgment — read each victim's read against the *healthy* origin content and ask whether the two could be true at once. **(half tested)**
11. `healthy_origin_content` is non-empty. **(tested)**
12. At least 4 `origin_variants`, and `origin_variants[0] == (origin_read[1], healthy_origin_content)`. Every variant's first line is literal (no `{...}`) and distinct within the scenario. **(tested)**
13. `origin_state` is a `(broken, healthy)` word pair; each token carries a letter; the broken token appears in every broken variant and in no healthy one, and vice versa. **(tested)**
14. No dotted-quad IP, no `https?://`, no `kubeconfig`, no `/home/`, no `@` in any field. **(tested)**
15. Contributes toward the pool exercising all sixteen `vocab.ISSUE_KINDS` — asserted in Task 9, which is why the kinds in the table are fixed.

Beyond the list, the authoring judgment that no test expresses:

- **The state token must not be buried in a numeric phrase.** `expired` in `notAfter: expired 2h ago` is read; `stale` in `last sync 11m ago` would not have been there at all. Put the word where it stands on its own.
- **The decoy causes must be plausible.** A decoy the model can dismiss on plausibility teaches it to dismiss decoys, not to read the origin.
- **`log_cause` renders on both halves** — it is part of the `Finding`, not the read (`cases.py:461`). Write each `local_cause` so it is compatible with its victim's `log_cause`, the way `_T_CA`'s are.
- **The scenario must not name a real cluster.** Namespaces, node names and workload names come from `names.py` via `{ns}`, `{node}` and `{name}`; do not hard-code one.

- [ ] **Step 3: Append them to `_TRAINING_SCENARIOS`**

```python
_TRAINING_SCENARIOS = (_T_CA, _T_KUBE_PROXY, _T_CONFIGMAP, _T_SCALED_TO_ZERO,
                       _T_IMAGE_PULL_SECRET, _T_SECRET_KEY_RENAMED,
                       _T_AUTOSCALER_CAPACITY, _T_SIDECAR_INJECTOR)
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. The invariants from Tasks 3 and 4 now run over eight scenarios. A failure names the scenario and the constraint — fix the scenario. Do not relax a test to accommodate prose; the prose is the negotiable half.

Watch in particular: `test_the_eval_set_is_byte_identical_to_the_one_every_scoreboard_used` (nothing here may touch the exam), `test_no_eval_row_comes_from_the_trainable_pool`, and the whole of `tests/test_shared_origin_training_pair.py`.

- [ ] **Step 5: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py
git commit -s -m "feat(dataset): four cluster-radius shared-origin training scenarios"
```

---

## Task 6: Three more cluster-radius scenarios, and the first node-radius one

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py`

**Interfaces:**
- Consumes: `Propagation`, `Victim`, `origin_variants`, `origin_state`.
- Produces: `_T_BASE_IMAGE_TAG`, `_T_PVC_MULTI_ATTACH`, `_T_CNI_IP_POOL`, `_T_CSI_NODE_DRIVER`, appended to `_TRAINING_SCENARIOS`.

**The four scenarios (fixed by the spec — do not renegotiate):**

| key | radius | scope_field | victim issue kinds |
| --- | --- | --- | --- |
| `shared-base-image-tag-moved` | cluster | `None` | `CrashLoopBackOff`, `ContainerStartError` |
| `shared-pvc-multi-attach` | cluster | `None` | `VolumeAttachError`, `VolumeMountError` |
| `cni-ip-pool-exhausted` | cluster | `None` | `ContainerStartError`, `Unschedulable` |
| `csi-node-driver-crashed` | node | `"node"` | `VolumeMountError`, `CrashLoopBackOff` |

The origin in each case: a shared base image tag repointed to a broken build; a ReadWriteOnce PVC attached to a node that will not release it; the CNI's address pool exhausted; the CSI node driver DaemonSet pod crashed on one node.

`csi-node-driver-crashed` is the first node-radius scenario added here, so `scope_field` is `"node"` and the origin read is keyed on `{node}` — see `_T_KUBE_PROXY` for the shape.

- [ ] **Step 1: Read the shape**

Read `_T_CA` (cluster radius) and `_T_KUBE_PROXY` (node radius) in `src/kubeagent_verdict/dataset/propagation.py` end to end, including their `origin_state` and `origin_variants`. Read the module docstring for the authoring rules that are guidance rather than tests.

- [ ] **Step 2: Write the four scenarios**

All fifteen constraints apply. Nine are tests that already run; six are authoring judgment:

1. `key` matches `^[a-z0-9]+(-[a-z0-9]+)*$`. **(tested)**
2. `key` is not one of the six in `all_scenarios()`. **(tested)**
3. `shared_cause` and `distractor_cause` appear in no eval scenario. **(tested)**
4. `shared_cause` and `distractor_cause` are unique across the whole trainable pool. **(tested)**
5. Every `local_cause` within the scenario is distinct. **(tested)**
6. Every `local_cause` is distinct across the whole trainable pool. **(tested)**
7. 2–4 victims, each `issue` in `vocab.ISSUE_KINDS` — use the kinds in the table above verbatim. **(tested)**
8. `pass_confidence` is not the same on every victim. **(tested)**
9. `scope_field` agrees with `blast_radius` — `cluster` → `None`, `node` → `"node"`. **(tested)**
10. A victim read that asserts the origin is broken declares a `healthy_read_content` that does not. The token half is tested; the English half is judgment. **(half tested)**
11. `healthy_origin_content` is non-empty. **(tested)**
12. At least 4 `origin_variants`, and `origin_variants[0] == (origin_read[1], healthy_origin_content)`. Every variant's first line is literal (no `{...}`) and distinct within the scenario. **(tested)**
13. `origin_state` is a `(broken, healthy)` word pair; each token carries a letter; the broken token appears in every broken variant and in no healthy one, and vice versa. **(tested)**
14. No dotted-quad IP, no `https?://`, no `kubeconfig`, no `/home/`, no `@` in any field. **(tested)**
15. Contributes toward the pool exercising all sixteen `vocab.ISSUE_KINDS` — asserted in Task 9.

The authoring judgment no test expresses:

- **The state token must not be buried in a numeric phrase.** Put the word where it stands on its own.
- **The decoy causes must be plausible.**
- **`log_cause` renders on both halves** (`cases.py:461`) — write each `local_cause` compatible with its victim's `log_cause`.
- **Do not hard-code a namespace, node or workload name.** Use `{ns}`, `{node}`, `{name}`.
- **`cni-ip-pool-exhausted` must not write a dotted quad.** Constraint 14 bans one, and an address-pool scenario is the obvious place to reach for one. Say "the pool has 0 of 512 addresses free", never a CIDR.

- [ ] **Step 3: Append them to `_TRAINING_SCENARIOS`**

Add `_T_BASE_IMAGE_TAG`, `_T_PVC_MULTI_ATTACH`, `_T_CNI_IP_POOL`, `_T_CSI_NODE_DRIVER` after the four names Task 5 added, keeping the tuple one name per position and formatted as it already is.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, now over twelve scenarios. A failure names the scenario and the constraint — fix the scenario, never the test.

- [ ] **Step 5: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py
git commit -s -m "feat(dataset): image, storage and network shared-origin training scenarios"
```

---

## Task 7: Four node-radius scenarios

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py`

**Interfaces:**
- Consumes: `Propagation`, `Victim`, `origin_variants`, `origin_state`.
- Produces: `_T_NODE_PID_PRESSURE`, `_T_NODE_RUNTIME_RESTARTING`, `_T_NODE_CLOCK_SKEW`, `_T_NODE_CONNTRACK_FULL`, appended to `_TRAINING_SCENARIOS`.

**The four scenarios (fixed by the spec — do not renegotiate):**

| key | radius | scope_field | victim issue kinds |
| --- | --- | --- | --- |
| `node-pid-pressure` | node | `"node"` | `ContainerStartError`, `RestartLoop` |
| `node-runtime-restarting` | node | `"node"` | `RestartLoop`, `ProbeFailure` |
| `node-clock-skew` | node | `"node"` | `CrashLoopBackOff`, `ProbeFailure` |
| `node-conntrack-full` | node | `"node"` | `ProbeFailure`, `CrashLoopBackOff` |

The origin in each case: the node at its PID limit; the container runtime restarting under the workloads; the node's clock far enough off that token validation fails; the node's conntrack table full so new connections are dropped.

All four are node-scoped, so every origin read is keyed on `{node}` and `_propagation_names` pins every victim to that one node. `_T_KUBE_PROXY` is the shape.

- [ ] **Step 1: Read the shape**

Read `_T_KUBE_PROXY` in `src/kubeagent_verdict/dataset/propagation.py` end to end — it is the node-radius scenario, including the `origin_state` and `origin_variants` Task 3 gave it and the comment on its first victim explaining why that `local_cause` is worded the way it is. Read the module docstring for the authoring rules that are guidance rather than tests.

- [ ] **Step 2: Write the four scenarios**

All fifteen constraints apply. Nine are tests that already run; six are authoring judgment:

1. `key` matches `^[a-z0-9]+(-[a-z0-9]+)*$`. **(tested)**
2. `key` is not one of the six in `all_scenarios()`. **(tested)**
3. `shared_cause` and `distractor_cause` appear in no eval scenario. **(tested)**
4. `shared_cause` and `distractor_cause` are unique across the whole trainable pool. **(tested)**
5. Every `local_cause` within the scenario is distinct. **(tested)**
6. Every `local_cause` is distinct across the whole trainable pool. **(tested)**
7. 2–4 victims, each `issue` in `vocab.ISSUE_KINDS` — use the kinds in the table above verbatim. **(tested)**
8. `pass_confidence` is not the same on every victim. **(tested)**
9. `scope_field` agrees with `blast_radius` — `node` → `"node"` on all four. **(tested)**
10. A victim read that asserts the origin is broken declares a `healthy_read_content` that does not. The token half is tested; the English half is judgment. **(half tested)**
11. `healthy_origin_content` is non-empty. **(tested)**
12. At least 4 `origin_variants`, and `origin_variants[0] == (origin_read[1], healthy_origin_content)`. Every variant's first line is literal (no `{...}`) and distinct within the scenario. **(tested)**
13. `origin_state` is a `(broken, healthy)` word pair; each token carries a letter; the broken token appears in every broken variant and in no healthy one, and vice versa. **(tested)**
14. No dotted-quad IP, no `https?://`, no `kubeconfig`, no `/home/`, no `@` in any field. **(tested)**
15. Contributes toward the pool exercising all sixteen `vocab.ISSUE_KINDS` — asserted in Task 9.

The authoring judgment no test expresses:

- **The state token must not be buried in a numeric phrase.** This task is where that rule is hardest and most load-bearing: all four origins are naturally quantities — a PID count, a restart count, a clock offset, a conntrack table's fill. `kube-proxy-degraded` was rewritten in Task 3 for exactly this reason, and it is the worked example. Every one of these four must name its state in a word (`at the PID limit`, `restarting`, `skewed`, `full`) beside whatever number it also shows.
- **Four node scenarios must not become four spellings of one scenario.** They share a radius and a scope field; they must not share a cause shape. If two of them read as "the node is out of something", change one.
- **The decoy causes must be plausible.**
- **`log_cause` renders on both halves** (`cases.py:461`) — write each `local_cause` compatible with its victim's `log_cause`.
- **Do not hard-code a node or namespace name.** Use `{node}`, `{ns}`, `{name}`.

- [ ] **Step 3: Append them to `_TRAINING_SCENARIOS`**

Add `_T_NODE_PID_PRESSURE`, `_T_NODE_RUNTIME_RESTARTING`, `_T_NODE_CLOCK_SKEW`, `_T_NODE_CONNTRACK_FULL` after the names Task 6 added.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, now over sixteen scenarios. A failure names the scenario and the constraint — fix the scenario, never the test.

- [ ] **Step 5: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py
git commit -s -m "feat(dataset): four node-radius shared-origin training scenarios"
```

---

## Task 8: Four namespace-radius scenarios

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py`

**Interfaces:**
- Consumes: `Propagation`, `Victim`, `origin_variants`, `origin_state`.
- Produces: `_T_LIMITRANGE_LOWERED`, `_T_EGRESS_PROXY_DOWN`, `_T_NS_PVC_FULL`, `_T_MIGRATION_LOCK`, appended to `_TRAINING_SCENARIOS`. After this task the tuple holds twenty scenarios and the pool is complete.

**The four scenarios (fixed by the spec — do not renegotiate):**

| key | radius | scope_field | victim issue kinds |
| --- | --- | --- | --- |
| `namespace-limitrange-lowered` | namespace | `"ns"` | `OOMKilled`, `Init:OOMKilled` |
| `namespace-egress-proxy-down` | namespace | `"ns"` | `ProbeFailure`, `CrashLoopBackOff` |
| `namespace-shared-pvc-full` | namespace | `"ns"` | `CrashLoopBackOff`, `ProbeFailure` |
| `namespace-migration-lock-held` | namespace | `"ns"` | `Init:CrashLoopBackOff`, `CrashLoopBackOff` |

The origin in each case: a `LimitRange` whose default memory limit was lowered under the namespace's workloads; the namespace's egress proxy Deployment down; a shared PVC in the namespace at 100% used; a schema-migration advisory lock held by a dead pod.

`namespace-limitrange-lowered` carries `OOMKilled` and `Init:OOMKilled`, which no other scenario in the pool carries -- `Init:CrashLoopBackOff` also appears on `sidecar-injector-broken` in Task 5, but those two do not. They are the last two kinds the pool is missing, which is why Task 9's coverage assertion comes after this task and not before it.

- [ ] **Step 1: Read the shape**

Read `_T_CONFIGMAP` in `src/kubeagent_verdict/dataset/propagation.py` end to end — it is the namespace-radius scenario, including the `origin_state`, `origin_variants` and the two `healthy_read_content` swaps Task 3 gave it. Read the module docstring for the authoring rules that are guidance rather than tests.

- [ ] **Step 2: Write the four scenarios**

All fifteen constraints apply. Nine are tests that already run; six are authoring judgment:

1. `key` matches `^[a-z0-9]+(-[a-z0-9]+)*$`. **(tested)**
2. `key` is not one of the six in `all_scenarios()`. **(tested)**
3. `shared_cause` and `distractor_cause` appear in no eval scenario. **(tested)**
4. `shared_cause` and `distractor_cause` are unique across the whole trainable pool. **(tested)**
5. Every `local_cause` within the scenario is distinct. **(tested)**
6. Every `local_cause` is distinct across the whole trainable pool. **(tested)**
7. 2–4 victims, each `issue` in `vocab.ISSUE_KINDS` — use the kinds in the table above verbatim. **(tested)**
8. `pass_confidence` is not the same on every victim. **(tested)**
9. `scope_field` agrees with `blast_radius` — `namespace` → `"ns"` on all four. **(tested)**
10. A victim read that asserts the origin is broken declares a `healthy_read_content` that does not. The token half is tested; the English half is judgment. `_T_CONFIGMAP`'s two swaps are the worked example: a victim naming the shared component by name, next to a healthy origin read showing that component fine, contradicts itself. **(half tested)**
11. `healthy_origin_content` is non-empty. **(tested)**
12. At least 4 `origin_variants`, and `origin_variants[0] == (origin_read[1], healthy_origin_content)`. Every variant's first line is literal (no `{...}`) and distinct within the scenario. **(tested)**
13. `origin_state` is a `(broken, healthy)` word pair; each token carries a letter; the broken token appears in every broken variant and in no healthy one, and vice versa. **(tested)**
14. No dotted-quad IP, no `https?://`, no `kubeconfig`, no `/home/`, no `@` in any field. **(tested)**
15. Contributes toward the pool exercising all sixteen `vocab.ISSUE_KINDS` — asserted in Task 9. These four carry the last missing kinds, so a typo in `OOMKilled`, `Init:OOMKilled` or `Init:CrashLoopBackOff` fails that assertion rather than passing quietly.

The authoring judgment no test expresses:

- **The state token must not be buried in a numeric phrase.** `namespace-shared-pvc-full` is the trap here — "100%" is a quantity; "full" is the word.
- **`namespace-egress-proxy-down` must not write a URL or a proxy address.** Constraint 14 bans `https?://`, and a proxy scenario is the obvious place to reach for one. Name the Deployment, not an endpoint.
- **The decoy causes must be plausible.**
- **`log_cause` renders on both halves** (`cases.py:461`) — write each `local_cause` compatible with its victim's `log_cause`.
- **Do not hard-code a namespace or workload name.** Use `{ns}`, `{name}`.

- [ ] **Step 3: Append them to `_TRAINING_SCENARIOS`**

Add `_T_LIMITRANGE_LOWERED`, `_T_EGRESS_PROXY_DOWN`, `_T_NS_PVC_FULL`, `_T_MIGRATION_LOCK` after the names Task 7 added. The tuple now holds twenty names.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, now over twenty scenarios.

- [ ] **Step 5: Sanity-check the radius pool**

Run: `.venv/bin/python -c "from collections import Counter; from kubeagent_verdict.dataset import propagation as p; print(Counter(s.blast_radius for s in p.trainable_scenarios()))"`
Expected: `Counter({'cluster': 9, 'node': 6, 'namespace': 5})` — the spec's target. If it differs, a scenario carries the wrong `blast_radius`; fix it.

- [ ] **Step 6: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py
git commit -s -m "feat(dataset): four namespace-radius shared-origin training scenarios"
```

---

## Task 9: What the pool teaches, measured

The per-scenario invariants cannot see the curriculum. This task asserts the properties that only exist across the whole pool: every issue kind is exercised, every scenario is taught equally, every scenario renders more than one origin read, and no cause template dominates.

**Files:**
- Modify: `tests/test_shared_origin_training.py`

**Interfaces:**
- Consumes: `propagation.trainable_scenarios()`, `generate.generate(seed, size)`, `Example.case`, `Example.meta["origin"]`, `Example.meta["expected"]`.
- Produces: nothing later tasks read.

The generator was measured before this plan was written: `generate.generate(seed=17, size=5500)` takes **0.3 seconds** and yields 220 `shared_origin` rows. It is a plain module-scoped fixture and carries **no `slow` marker**.

- [ ] **Step 1: Write the tests**

Add to `tests/test_shared_origin_training.py`. Add `from collections import Counter` to the imports.

```python
BIG = 5500  # 0.3s to generate; 11 rows of each half per scenario at 20 scenarios


@pytest.fixture(scope="module")
def big_rows():
    return generate.generate(seed=SEED, size=BIG)


def test_the_trainable_pool_exercises_every_issue_kind():
    """A kind absent from the curriculum is a kind the shared-origin rule was
    never taught over -- and `vocab.ISSUE_KINDS` is what the eval draws from.
    """
    seen = {v.issue for p in propagation.trainable_scenarios() for v in p.victims}
    missing = sorted(set(vocab.ISSUE_KINDS) - seen)
    assert not missing, f"no trainable scenario exercises: {missing}"


def test_the_trainable_pool_holds_twenty_scenarios():
    """Four scenarios is what the pool held when it scored 0.5 in-distribution
    and 0.1 out. The count is asserted so shrinking it back is a deliberate
    edit rather than a merge artefact.
    """
    assert len(propagation.trainable_scenarios()) == 20


def test_every_trainable_scenario_is_taught_equally(big_rows):
    """Equal shares are what make a constant answer chance-level: a scenario
    the curriculum shows twice as often is one the model can afford to answer
    by name.
    """
    keys = {p.key for p in propagation.trainable_scenarios()}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == keys, f"{case}: {sorted(keys ^ set(counts))}"
        assert len(set(counts.values())) == 1, f"{case}: uneven shares {dict(counts)}"


def test_every_trainable_scenario_renders_at_least_three_origin_variants(big_rows):
    """Declaring four variants is not the same as rendering them. If the draw
    were keyed on something constant per scenario, every row would carry
    variant 0 and the whole mechanism would be inert while its own unit test
    still passed.
    """
    by_key = {p.key: p for p in propagation.trainable_scenarios()}
    seen = {k: set() for k in by_key}
    for e in big_rows:
        if e.case != "shared_origin":
            continue
        p = by_key[e.meta["origin"]]
        for i, (broken, _healthy) in enumerate(p.origin_variants):
            if broken.split("\n")[0] in e.user:
                seen[p.key].add(i)
    thin = {k: sorted(v) for k, v in seen.items() if len(v) < 3}
    assert not thin, f"scenarios rendering fewer than 3 variants: {thin}"


def test_no_shared_origin_cause_dominates_the_curriculum(big_rows):
    """The flattening the slice exists for.

    Measured on the four-scenario pool before this slice: 15 distinct causes,
    top one 0.263 and top three 0.633. A model that answers the single most
    common cause on every shared-origin row was right a quarter of the time.
    The bar is 0.12 and 0.30 -- both of which the old pool failed by a wide
    margin, which is what makes this check non-vacuous.
    """
    causes = Counter(cause
                     for e in big_rows if e.case == "shared_origin"
                     for cause in e.meta["expected"].values())
    total = sum(causes.values())
    top = causes.most_common(3)
    assert top[0][1] / total <= 0.12, (
        f"{top[0][0]!r} is {top[0][1] / total:.3f} of all shared-origin causes")
    assert sum(n for _c, n in top) / total < 0.30, (
        f"top three are {sum(n for _c, n in top) / total:.3f} of all causes")
```

- [ ] **Step 2: Run them**

Run: `.venv/bin/python -m pytest tests/test_shared_origin_training.py -q`
Expected: PASS.

If `test_the_trainable_pool_exercises_every_issue_kind` fails, it names the missing kinds. The fix is to change one victim's `issue` in one of the sixteen new scenarios to a kind that genuinely fits its story — never to relax the assertion, and never to bolt a kind onto a scenario where it makes no sense.

If `test_every_trainable_scenario_is_taught_equally` fails with uneven shares, check `BIG`: `generate` divides the `shared_origin` allocation across scenarios, and a size that is not a clean multiple of 20 leaves a remainder. Adjust `BIG` upward to the next size that divides evenly; do not weaken the assertion to `max - min <= 1`.

If `test_no_shared_origin_cause_dominates_the_curriculum` fails, the pool is still too concentrated — most likely two scenarios sharing a cause shape, or one scenario contributing more distinct causes than its neighbours. Report the numbers and the offending causes rather than moving the bar.

- [ ] **Step 3: Confirm the exam still has not moved**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including `test_the_eval_set_is_byte_identical_to_the_one_every_scoreboard_used`, `test_no_eval_row_comes_from_the_trainable_pool`, `test_the_probe_still_draws_only_held_out_origins` and `test_training_still_contaminates_nothing`. Those four together are the whole of the containment argument: twenty trainable scenarios, none of them reachable from the 263-row exam.

- [ ] **Step 4: Commit**

```bash
git add tests/test_shared_origin_training.py
git commit -s -m "test: assert what the shared-origin curriculum teaches, across the pool"
```

---

## Task 10: Write down what a test cannot hold

Six of the fifteen constraints are authoring judgment, and the module docstring is where the next person authoring a scenario meets them. It must say which half is which — a docstring that presents all fifteen as rules promises enforcement the file does not have, and that is a defect under this repo's own standard.

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` (module docstring only)
- Modify: `docs/how-training-works.md`

**Interfaces:**
- Consumes: nothing. Produces: nothing.

- [ ] **Step 1: Extend the module docstring**

Append to the module docstring of `src/kubeagent_verdict/dataset/propagation.py`, after its existing text:

```
Authoring a trainable scenario
------------------------------

Nine of the rules below are enforced by `tests/test_shared_origin_training.py`
and will fail the suite. Six are judgment and will not -- they are written here
because a test cannot hold them, not because they matter less.

Enforced: the key's shape and its disjointness from the eval six; both cause
strings unique across the pool; every `local_cause` unique within the scenario
and across the pool; 2-4 victims with kinds from `vocab.ISSUE_KINDS`;
`pass_confidence` varying within the scenario; `scope_field` agreeing with
`blast_radius`; a non-empty `healthy_origin_content`; at least four
`origin_variants` whose first entry is the legacy pair and whose first lines
are literal and distinct; an `origin_state` word pair present in every variant
of its own half and absent from the other; no banned identifier shape anywhere;
and, across the pool, all sixteen issue kinds with no cause template over 12%.

Judgment, and unenforced:

- Put the state word where it stands on its own. `notAfter: expired 2h ago`
  is read; a bare `11m ago` was measured not to be. The enforced rule only
  says a word is present somewhere.
- Write decoy causes a reader would have to check. A decoy dismissible on
  plausibility teaches the model to dismiss decoys, not to read the origin.
- A victim read must be able to be true beside the *healthy* origin content.
  The enforced half catches the case where the state token itself appears;
  naming the shared component in other words is invisible to it, and
  `_T_CONFIGMAP`'s two `healthy_read_content` swaps are what that looks like.
- `log_cause` renders on both halves -- it belongs to the Finding, not the
  read (`cases.py:461`). Each `local_cause` must be compatible with it.
- Scenarios sharing a blast radius must not share a cause shape. Four
  node-scoped scenarios that all read "the node is out of something" are one
  scenario spelled four ways.
- Never hard-code a namespace, node or workload name. `{ns}`, `{node}` and
  `{name}` are substituted from `names.py`.
```

- [ ] **Step 2: Update `docs/how-training-works.md`**

Read the file first and match its voice — it explains the training process in plain language and deliberately never names the training host. Add a short section describing what changed: the shared-origin curriculum grew from four scenarios to twenty; the discriminating read now varies within each scenario so the answer depends on what the read says rather than on which of four strings it is; and the exam did not move, so the numbers stay comparable.

State plainly what this does **not** claim: it is a change to what the model is taught, measured only by what the curriculum contains. Whether it moves the shared-origin score is a question a retrain answers, and no retrain has run.

- [ ] **Step 3: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. A docstring edit cannot break a test, but the run confirms the tree is clean before the branch is finished.

- [ ] **Step 4: Commit**

```bash
git add src/kubeagent_verdict/dataset/propagation.py docs/how-training-works.md
git commit -s -m "docs: record which shared-origin authoring rules are enforced and which are not"
```

---

## After the plan

The branch is then ready for `superpowers:finishing-a-development-branch`.

Five verification checks come from the spec, and Tasks 1–10 land four of them as tests: the exam is byte-identical (Task 1), every scenario renders more than one variant (Task 9), no cause template dominates (Task 9), and contamination is still 0 of 263 (the existing `test_training_still_contaminates_nothing`, re-run in Task 9 Step 3). The fifth — whether any of this moves the shared-origin score — is a retrain, which **this plan does not authorize and no task performs**. It is a separate decision, on a separate host, after these checks are green.

One spec commitment survives this plan without a task, deliberately. The spec notes that three of the sixteen new scenarios sit semantically next to an eval scenario — `image-pull-secret-expired` next to `registry-unreachable`, `csi-node-driver-crashed` next to `storage-provisioner-down`, `node-pid-pressure` next to `node-disk-pressure` — and commits to reporting any future shared-origin score split into the eval scenarios that have a near training neighbour and those that do not. That is a reporting obligation on whoever reads the next scoreboard. It cannot be a task here because there is no scoreboard to split: no retrain has run.
