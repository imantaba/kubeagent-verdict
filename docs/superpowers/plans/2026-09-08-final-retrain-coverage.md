# Final retrain coverage — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the trainable shared-origin pool from 24 to 48 scenarios, give every scenario 3 or 4 victims, teach the exam's six real read layouts, raise the shared-origin halves to 12% of the build, and add a cousin probe, so that one final retrain can pass all six release deciders.

**Architecture:** Every change is data or tests. The scenario records live in one module (`propagation.py`), the renderer and the generator are untouched except for the case mix and one new probe generator, and every new rule is pinned by a test that fails before the data lands. The exam stays byte-identical; two hashes pin it.

**Tech Stack:** Python 3.12 in `.venv`, pytest, the existing `kubeagent_verdict.dataset` package. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-08-final-retrain-coverage-design.md` (commit `7e5ed18`). The spec is the authority. This plan is its argument.

## Global Constraints

- Work on branch `final-retrain-coverage`, cut off `main` at `f22c07c`. Never implement on `main`.
- Every commit is signed off: `git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "…"`. No AI attribution anywhere: no `Co-Authored-By` trailer, no "generated with" line, no model named in any file or message.
- A commit message never cites a path under `docs/testing/` and never cites a scenario record ID from a real cluster.
- No secret, credential, private IP, internal hostname, kubeconfig path or context name in any tracked file. The machine that trains is called "the training host", never by name. Scenario text also avoids the banned shapes a test enforces: dotted quads, `http://` or `https://`, the word `kubeconfig`, `/home/`, and `@`.
- Python is `.venv/bin/python`; pytest is `.venv/bin/python -m pytest`. There is no bare `python`.
- NEVER run `kv-train`, `kv-export`, `chaos/run.sh`, or any test with `-update`. This plan does not authorise a retrain. Spec Section 3 steps 5–11 are the operator's, on the training host, after this branch is finished.
- `CASE_MIX` moves exactly once, in Task 1, to attributed 10 / shared_origin 12 / shared_origin_decoy 12. No other percentage moves.
- The exam is frozen. `FROZEN_253_SHA256 = "9f5fb341f620306d1d003d1617da613139f7bccf03cec768bd78539df75abb96"` and `EVAL_SET_SHA256 = "9d59a8f881862bc9035605d206a2cc9269bf5b59300f8fb8af3a030aff04f1b9"` in `tests/test_shared_origin_training.py`. Two tests pin these. If either moves, stop: something touched the exam.
- `_SCENARIOS` in `propagation.py` (the six exam origins) is never edited. `_TRAINING_SCENARIOS` only grows by appending.
- Every doc line this plan writes is in simple voice: short sentences, everyday words, lead with the decision, numbers explained ("3 of 10 pairs").
- A comment, docstring or reason string that promises something the code does not keep is a defect to fix, not a Minor. Either close the gap or narrow the claim.
- The literal word `BROKEN` never appears in scenario text. The placeholders `cases._fmt` fills are exactly nine: `{ns}`, `{name}`, `{pod}`, `{container}`, `{init_container}`, `{image}`, `{node}`, `{pvc}`, `{restarts}`. Any other `{…}` crashes the renderer. A literal brace is written doubled: `{{maintenance: true}}`.
- No `SHARED_CLAIM_PHRASES` word in any `local_cause`, `local_reason`, `distractor_cause`, `distractor_reason`, or read text. The list (`cases.py:32`): "shared origin", "shared root cause", "common cause", "common root cause", "same underlying", "same root cause", "upstream", "cascading", "knock-on", "caused by the same".
- Every scenario has at most 4 victims (`tests/test_propagation.py`) and, after Task 2, at least 3. `pass_confidence` varies within a scenario. A node-scoped `shared_cause` contains `{node}`; a namespace-scoped one contains `{ns}`.
- All `local_cause` strings and all `shared_cause` / `distractor_cause` strings are unique across the whole 48-scenario pool.

## Rules every scenario record follows

These rules come from the tests that already exist. A new record that breaks one fails the suite. Read them before writing any Python.

- **R1 — state line first, then the layout.** `test_every_variant_first_line_is_literal_and_unique_within_its_scenario` collects the first line of every half of every variant and requires all of them to be unique inside the scenario. An exam layout starts with `Conditions:` or `Replicas:` or `provisioner:` or `podSelector:` or `<N> pods across`, and its healthy half starts the same way, so two halves would collide. So every exam-layout copy opens with a one-line state line carrying the token, then the exam layout line for line. Precedent: node-memory-pressure opens "Memory: reclaiming" then "Conditions:…"; storageclass-pool-retired opens "Pool status: retired" then "provisioner: …". The first line also must not contain `{`.
- **R2 — numbers agree with the shared_reason.** The variant's numbers match the scenario's `shared_reason`: clock-skew says 6m42s, kube-proxy says 11m, csi-node-driver says 4 restarts, pod-identity says 2 desired and 2 pods, egress-proxy says 3 desired and 3 pods, netpol-allowlist says tier=datastore and tier=data.
- **R3 — first lines are new.** The appended 2b variants use these first lines, none of which any existing variant uses: node-pid "PID condition on this node: exhausted/available"; kube-proxy "node view of kube-proxy: stale/fresh"; csi-node-driver "node view of the CSI plugin: crashed/healthy"; node-runtime "kubelet view of the runtime: restarting/stable"; clock-skew "clock state on this node: skewed/synced"; conntrack "node view of conntrack: full/clear"; pod-identity "webhook Deployment: down/serving"; scaled-to-zero "Deployment scale state: replicas to 0" and "Deployment scale state: 2 of 2 Running"; egress-proxy "proxy rollout state: restarting/steady"; storageclass "ssd-premium class: retired/online"; netpol-allowlist "policy match state: blocked/allowed".
- **R4 — tokens are case-sensitive substrings.** `test_every_trainable_scenario_names_its_state_in_words` requires the broken token in every broken half, the healthy token in every healthy half, and each token absent from the other half. node-kernel-deadlock uses 'hung'/'responsive', so its broken halves never say "unresponsive".
- **R5 — the other half's token is absent from the whole text.** csi-controller-oomkilled's broken half has no "Running". provisioner-credentials-rotated and cluster-maintenance-taint broken halves have no "none". scaled-to-zero's broken half has no "Running" and its healthy half has no "replicas to 0". node-corrupt-overlay's healthy half has no lowercase "corrupt" ("NoCorruptDockerOverlay2" is fine, case-sensitive). node-readonly-filesystem's token is "read-only", so "FilesystemIsNotReadOnly" is fine.
- **R6 — a victim read that carries the broken token needs a healthy swap.** `test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half` requires `healthy_read_content` without the token whenever `read[1]` contains it. The swap must support the local cause instead. Evidence that names the origin fact gets `healthy_evidence`. Prefer neutral reads.
- **R7 — no shared-claim phrase in a `local_cause`.** `test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim` checks that field and no other. This plan holds the same line by hand in every new record: no `local_reason`, distractor string or read uses a phrase from `cases.SHARED_CLAIM_PHRASES`, and the task reviewer greps for them. One existing record, `_T_SCALED_TO_ZERO`, already says "upstream" in its distractor cause and in a victim's log cause; it is not touched.
- **R8 — `{{maintenance: true}}` never on a first line** (the first-line test rejects `{`).
- **R9 — a third victim is a different workload kind** from the two that exist where the spec says so (cluster-autoscaler-at-capacity and cni-ip-pool-exhausted already have a Job, so their third is a StatefulSet or CronJob).
- **R10 — exactly 4 variants per new scenario** (8 unique first lines), `origin_variants[0] == (origin_read[1], healthy_origin_content)`, no two variants of one half are the same rendering with different numbers (`_canonical_rendering` replaces every `\d+[A-Za-z]*` with `N`, collapses whitespace, and sorts lines).
- **Victim conventions.** `status` is "Running" for ProbeFailure, "Pending" for Unschedulable, "ContainerCreating" for VolumeAttachError and VolumeMountError, "OOMKilled" for OOMKilled, else equal to `issue`. Reason templates: CrashLoopBackOff "container {container} has restarted {restarts} times"; Init:CrashLoopBackOff "init container {init_container} has restarted {restarts} times"; RestartLoop "container {container} has restarted {restarts} times and is Running again between attempts"; ProbeFailure "readiness probe on container {container} is failing"; ContainerStartError "container {container} could not be started"; Unschedulable "pod has an unbound PersistentVolumeClaim and cannot be scheduled" or "no node has room for the pod"; VolumeAttachError "volume {pvc} could not be attached to the pod's node"; VolumeMountError "volume {pvc} could not be mounted into the pod"; OOMKilled "container {container} was killed by the kernel out-of-memory handler"; CreateContainerConfigError "container {container} could not build its environment".

## File Structure

| File | Change | Owner task |
|---|---|---|
| `src/kubeagent_verdict/dataset/generate.py` | `CASE_MIX` 10/12/12, comment numbers, `shared_origin_cousin_probes` | 1, 11 |
| `tests/test_generate.py` | counts 100/120/120 | 1 |
| `tests/test_shared_origin_training.py` | `DRAWS`/`BIG`, band floor 0.52, `EXPECTED_POOL`, ≥3 victims, layout tests, docstring numbers | 1, 2, 4, 5–10 |
| `src/kubeagent_verdict/dataset/propagation.py` | 15 third victims, 11 variants + spelling fix, 24 new scenarios, docstring | 2–9, 10 |
| `tests/test_shared_origin_floor.py` | decoy-width test; `SIZE = 8000` | 2, 10 |
| `tests/test_contamination.py` | `SIZE = 8000` | 10 |
| `tests/test_evidence_overlap.py` | `SIZE = 8000`, `DECLARED` re-measured | 10 |
| `src/kubeagent_verdict/dataset/cli.py` | `--probe-cousins` | 11 |
| `tests/test_probe_cousins.py` | new | 11 |
| `docs/runbooks/train.md`, `README.md`, `docs/design.md`, `docs/how-training-works.md` | size 8000, 12%, forty-eight, new section | 12 |

**Why the tasks split the way they do.** Task 1 moves the mix first because every share number downstream depends on it. Tasks 2–3 give the existing pool its third victims so the ≥3-victims rule holds before any new scenario is judged by it. Task 4 does the exam-layout variants on existing scenarios so the layout floors in Task 9 count them. Tasks 5–9 add one group each, and the pool pin grows with each group so a reviewer sees an exact count. Task 10 re-measures every size-dependent number once, at the finished pool. Task 11 is the cousin probe. Task 12 is docs.

---

### Task 1: Move the case mix to 10 / 12 / 12 and restate the sampling constants

**Files:**
- Modify: `src/kubeagent_verdict/dataset/generate.py:45-70` (comment + `CASE_MIX`), `:118-147` (the multi-loop comment's numbers)
- Modify: `tests/test_generate.py:57-70`
- Modify: `tests/test_shared_origin_training.py:421-450` (shared-minority docstring), `:534-560` (band tests), `:695-700` (`BIG`), `:772-796` (variants docstring)
- Modify: `tests/test_shared_origin_training_pair.py:73-85` (`_pairs`)

**Interfaces:**
- Produces: `generate.CASE_MIX` with `("attributed", 10)`, `("shared_origin", 12)`, `("shared_origin_decoy", 12)`; `generate.counts_for(1000)["shared_origin"] == 120`; module constants `DRAWS = 33` and `BIG = 275 * len(propagation.trainable_scenarios())` in `tests/test_shared_origin_training.py` that Tasks 5–10 rely on staying pool-relative; `_pairs` in `tests/test_shared_origin_training_pair.py` pairs twins by emission order and checks the group, so no later task trips on a workload-set collision.

- [ ] **Step 1: Write the failing counts test**

In `tests/test_generate.py`, replace the body of `test_counts_for_follows_the_mix` so the expected dict reads:

```python
def test_counts_for_follows_the_mix():
    counts = generate.counts_for(1000)
    assert counts == {"attributed": 100, "none_of_these": 150, "own_cause": 100,
                      "multi": 110, "shared_origin": 120,
                      "shared_origin_decoy": 120, "truncated": 50,
                      "injection": 100, "empty_candidates": 50,
                      "wrong_attribution": 100}
    assert sum(generate.counts_for(997).values()) == 997
    for size in (10, 100, 997, 1000, 4232):
        c = generate.counts_for(size)
        assert c["shared_origin"] == c["shared_origin_decoy"], size
```

Keep whatever extra assertions the existing test carries after the loop.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_generate.py::test_counts_for_follows_the_mix -v`
Expected: FAIL — `attributed` is 180 and `shared_origin` is 80.

- [ ] **Step 3: Move the mix**

In `src/kubeagent_verdict/dataset/generate.py`, change `CASE_MIX` to:

```python
CASE_MIX = (("attributed", 10), ("none_of_these", 15), ("own_cause", 10),
            ("multi", 11), ("shared_origin", 12), ("shared_origin_decoy", 12),
            ("truncated", 5), ("injection", 10), ("empty_candidates", 5),
            ("wrong_attribution", 10))
```

The comment block above it (lines 45–66) tells the 4% → 8% history. Add one short paragraph at its end, in simple voice:

```python
# 2026-09-08: both halves move again, from 8% to 12%, and `attributed` gives
# up the 8 points (18% -> 10%). The 0907 model failed decider 5 with 15 of 24
# scenarios holding only two victims and no exam layout in training. The
# pool doubles to 48 scenarios in this slice; at 12% and size 8000 each half
# is 960 rows, 20 pairs per scenario, about 18 in train after the split.
# tests/test_shared_origin_floor.py still pins the floor at 12.
```

In the multi-loop comment (lines 118–147) the sentence "the paired core is exactly even (440/440 at the build size)" becomes "the paired core is exactly even (960/960 at the build size)". Leave every other number in that comment alone; Task 10 re-measures the "~0.57" figure at the finished pool.

- [ ] **Step 4: Run the counts test, then the generator suite**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_generate.py -v`
Expected: PASS for `test_counts_for_follows_the_mix`. `test_test_set_slice_counts_are_pinned` and `test_keyword_slice_exposure_is_pinned` still PASS (the exam does not depend on the mix).

- [ ] **Step 5: Restate `BIG` as pool-relative**

In `tests/test_shared_origin_training.py`, replace lines 695–700 (the `BIG = 13200` constant and its comment) with:

```python
DRAWS = 33  # shared_origin rows per scenario at BIG; see the note below.
BIG = 275 * len(propagation.trainable_scenarios())
# Each shared_origin half is BIG * 12 // 100 rows, and the generator deals
# them round-robin over the pool, so every scenario gets exactly DRAWS rows
# per half (275 * 12 // 100 == 33). The pool grows in this slice, and the
# constant grows with it: 6600 rows at twenty-four scenarios, 13200 at
# forty-eight. Why 33 and not 11: the variant-rendering check below is a
# sampling check. With 4 variants drawn uniformly, P(fewer than 3 distinct
# in n draws) = (6 * 2**n - 8) / 4**n, and a fifth variant only lowers
# it. At n=11 that is 0.3% per scenario and 7% across twenty-four -- a
# deterministic failure with correct data. At n=33 it is 7.0e-10 per
# scenario, 3.4e-8 across forty-eight.
```

Add, right after the `big_rows` fixture, a test that pins the arithmetic so a future mix change cannot silently break the promise:

```python
def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS shared_origin rows per scenario. Check it."""
    pool = len(propagation.trainable_scenarios())
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * pool
```

In `test_every_trainable_scenario_renders_at_least_three_origin_variants` (line 772), rewrite the docstring's last paragraph to:

```
    The bar is 3 of 4 rather than 4 of 4 because the draw is uniform and
    random: this is a sampling check, and its strength is a function of
    `DRAWS`. At 33 draws a correct pool trips it about once in thirty
    million runs across a pool of forty-eight. Lowering `BIG` is not a free
    speed-up -- at 11 draws it is about 7%, and the failure names a scenario
    whose data is fine.
```

- [ ] **Step 6: Move the band floor with the mix**

The mix change is what moves the kept-pile independent share. Spec 2d measured it at 0.551 (size 800) and 0.546 (size 8000) on the twenty-four pool at the new mix, against a band of 0.55–0.70. In `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (line 553) change the assertion to:

```python
    share = _independent_share(kept)
    assert 0.52 <= share <= 0.70, f"kept-pile independent share {share:.3f}"
```

and add one sentence to its docstring: "The floor moved from 0.55 to 0.52 on 2026-09-08 when the halves went to 12%: the kept pile then read 0.551 at this size and 0.546 at the build size, and 0.52 keeps three points of room below both." Task 10 restates the measured numbers at the forty-eight pool.

Update the three interim docstring numbers now so no docstring lies between tasks: in `test_the_shared_answer_stays_the_minority_among_multi_workload_rows` (line 421) change "0.34" to "0.373"; in `test_the_generator_emits_the_two_classes_near_evenly` change "0.595" to "0.568"; in `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` change "0.565" to "0.551". Leave the "64/64" wording — Task 10 re-measures it.

- [ ] **Step 7: Re-key the twin pairing, which the mix change breaks by chance**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training_pair.py -q`
Expected: FAIL inside `_pairs` with `workload sets collide`. Nothing is wrong with the data. `_pairs` keys each twin on the sorted workload set it names, and at size 800 two origins drew the same two workloads. That pairing was luck all along: the new mix moved the random draws, and the luck ran out. It also runs out for the forty-eight pool at every size tried (800, 2400, 8000).

In `tests/test_shared_origin_training_pair.py`, replace the whole `_pairs` function (lines 73–85) with:

```python
def _pairs(rows):
    """Twin rows, matched by emission order and checked by group.

    The emitter writes each pair as two consecutive rows from one salt, so
    the n-th `shared_origin` row and the n-th `shared_origin_decoy` row are
    twins. The group check is what makes that sound: twins carry one group
    string, which names the origin and its workloads. Matching on the
    workload set alone stopped being unique when the mix moved: two origins
    can draw the same two workloads by chance, and then a row loses its
    twin to a stranger.
    """
    shared = _by_case(rows, SHARED)
    decoy = _by_case(rows, DECOY)
    assert shared, "no shared_origin rows"
    assert len(shared) == len(decoy), "a row has no twin"
    for a, b in zip(shared, decoy):
        assert a.group == b.group, "rows out of step: not twins"
        assert _workloads(a) == _workloads(b), "twins name different workloads"
    return list(zip(shared, decoy))
```

`_workloads` stays; the loop still uses it. Every caller (`for shared, decoy in _pairs(rows)`) keeps working, because the return shape is the same list of two-row tuples.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training_pair.py -q`
Expected: PASS.

- [ ] **Step 8: Run the training-shape suite**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -v`
Expected: PASS, including the two exam-pin tests. The kept-pile share test passes at 0.551. If either hash test fails, stop and report — the exam moved.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests -q -x --ignore=tests/test_shared_origin_floor.py --ignore=tests/test_contamination.py --ignore=tests/test_evidence_overlap.py`
Expected: PASS. The three ignored files still say `SIZE = 5500`; they are re-pinned in Task 10 and must not be edited here. (Run them once anyway: `.venv/bin/python -m pytest tests/test_shared_origin_floor.py tests/test_contamination.py tests/test_evidence_overlap.py -q`. The floor test PASSES at 5500 and 8%→12% because more pairs land in train. The evidence-overlap `DECLARED` dict may FAIL because the trained digest set changed shape — that is expected and is Task 10's job. Record the observed diff in the report and move on.)

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/generate.py tests/test_generate.py tests/test_shared_origin_training.py tests/test_shared_origin_training_pair.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: raise the shared-origin halves to 12% and make BIG pool-relative"
```

### Task 2: Pin "at least three victims" and add the first six third victims

**Files:**
- Modify: `tests/test_shared_origin_training.py` (new test after `test_pass_confidence_varies_within_every_trainable_scenario`, line 219)
- Modify: `tests/test_shared_origin_floor.py` (new test after `test_the_two_halves_survive_the_split_together`, the last test in the file)
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — the `victims=(` tuples of `_T_KUBE_PROXY` (line 859), `_T_CSI_NODE_DRIVER` (1867), `_T_NODE_PID_PRESSURE` (1964), `_T_NODE_RUNTIME_RESTARTING` (2065), `_T_NODE_CLOCK_SKEW` (2167), `_T_NODE_CONNTRACK_FULL` (2263)

**Interfaces:**
- Consumes: `Victim` (propagation.py:136), the nine placeholders, the victim conventions in "Rules every scenario record follows".
- Produces: six scenarios with 3 victims; two tests Task 3 turns green: `test_every_trainable_scenario_has_at_least_three_victims` and `test_three_verdict_decoys_are_common_and_span_the_node_scenarios`.

- [ ] **Step 1: Write the two failing tests**

In `tests/test_shared_origin_training.py`:

```python
def test_every_trainable_scenario_has_at_least_three_victims():
    """The 0907 model failed decider 5 on three-victim decoy halves it had
    never seen: 15 of 24 trainable scenarios held two victims, so the
    generator could only ever render two. Three is the floor now."""
    thin = {p.key: len(p.victims) for p in propagation.trainable_scenarios()
            if len(p.victims) < 3}
    assert thin == {}, f"scenarios with fewer than three victims: {thin}"
```

In `tests/test_shared_origin_floor.py`, after `test_the_two_halves_survive_the_split_together`. It reads the module's `train` fixture, the kept train pile at the build size, because that pile is what the model reads:

```python
def test_three_verdict_decoys_are_common_and_span_the_node_scenarios(train):
    """The 0907 model wrote broken JSON on decoy halves with three verdicts.
    It had seen few: 80 of 397 kept decoy rows carried three or more, and
    every node-scoped one came from a single scenario. Two floors now: at
    least 40 of every 100 decoy rows carry three or more verdicts, and the
    node-scoped ones with three or more come from at least 5 scenarios.

    The generator cycles a pair's width over 2..len(victims), so a scenario
    with two victims can never render three. These floors hold only when
    nearly every scenario has a third victim."""
    radius = {p.key: p.blast_radius for p in prop.trainable_scenarios()}
    decoys = [e for e in train if e.case == DECOY]
    wide = [e for e in decoys if len(e.meta["expected"]) >= 3]
    share = len(wide) / len(decoys)
    node_keys = {e.meta["origin"] for e in wide
                 if radius[e.meta["origin"]] == "node"}
    assert share >= 0.40, (
        f"{len(wide)} of {len(decoys)} decoy rows carry three or more "
        f"verdicts, share {share:.3f}")
    assert len(node_keys) >= 5, (
        f"node-scoped three-verdict decoys come from {len(node_keys)} "
        f"scenario(s): {sorted(node_keys)}")
```

- [ ] **Step 2: Run both to verify they fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py::test_every_trainable_scenario_has_at_least_three_victims -v`
Expected: FAIL naming 15 scenarios.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_floor.py -k three_verdict -v`
Expected: FAIL, `80 of 397 decoy rows carry three or more verdicts, share 0.202`. The build is fast; the whole file runs in seconds.

- [ ] **Step 3: Append the six victims**

Each block goes in as the LAST element of the named scenario's `victims=(...)` tuple, after the existing last `Victim(...)`, with a trailing comma. Every placeholder used is one of the nine.

`_T_KUBE_PROXY` (tokens 'stale'/'fresh'; existing victims are a Deployment and a DaemonSet):

```python
        Victim(
            workload_kind="StatefulSet", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-service: dial tcp: connection timed out",
            local_cause="this StatefulSet's init container waits on a Service name "
                        "that was renamed in the last chart release",
            local_reason="the init container's own log names a Service that no "
                         "longer exists in {ns}",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: wait for a dependency Service timed out "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
```

`_T_CSI_NODE_DRIVER` (tokens 'crashed'/'healthy'; existing victims are a StatefulSet and a Deployment):

```python
        Victim(
            workload_kind="Job", status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume {pvc}: timed out "
                     "waiting for the external attacher",
            local_cause="this Job's own claim references a volume handle that was "
                        "deleted from the storage backend last week",
            local_reason="the backend lists no volume with the handle this Job's "
                         "PersistentVolume names",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  ("Status: Bound\nVolume: pv-{pvc}\nEvents: Warning  "
                   "FailedAttachVolume  attachdetach-controller  "
                   "AttachVolume.Attach failed for volume {pvc}: timed out "
                   "waiting for the external attacher")),
            pass_confidence="medium",
        ),
```

`_T_NODE_PID_PRESSURE` (tokens 'exhausted'/'available'; existing victims are a Deployment and a DaemonSet):

```python
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="worker pool start failed: cannot allocate thread",
            local_cause="this StatefulSet's own thread pool size was raised past "
                        "the container's pids limit in the last config change",
            local_reason="the container's own pids limit is lower than the thread "
                         "count its config now asks for",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: thread creation failed, cannot allocate "
                   "resources (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
```

`_T_NODE_RUNTIME_RESTARTING` (tokens 'restarting'/'stable'; existing victims are a Deployment and a DaemonSet):

```python
        Victim(
            workload_kind="Job", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: context deadline exceeded",
            local_cause="this Job's own container runs a start hook that blocks "
                        "for longer than the kubelet's start deadline",
            local_reason="the container's own postStart hook waits on a remote "
                         "call with no timeout, and the kubelet gives up on it",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed "
                   "to create containerd task: context deadline exceeded while "
                   "starting {container}")),
            pass_confidence="high",
        ),
```

`_T_NODE_CLOCK_SKEW` (tokens 'skewed'/'synced'; existing victims are a Deployment and a DaemonSet):

```python
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="token validation failed: token is not yet valid",
            local_cause="this Job's own init container checks a token that a "
                        "misconfigured issuer minted with a future not-before time",
            local_reason="the token's own not-before claim is ten minutes ahead, "
                         "set by the issuer's config, on every node it is checked",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: token rejected, not yet valid "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
```

`_T_NODE_CONNTRACK_FULL` (tokens 'full'/'clear'; existing victims are a Deployment and a StatefulSet):

```python
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="last state terminated with exit code 1",
            log_cause="outbound dial failed after 5 retries",
            local_cause="this agent's own connection pool opens a new socket per "
                        "sample and never closes the old ones",
            local_reason="the agent's own open socket count climbs to its file "
                         "descriptor limit right before each restart",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: outbound dial failed, too many open "
                   "connections (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
```

- [ ] **Step 4: Run the structural suites**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py::test_every_trainable_scenario_has_at_least_three_victims -v`
Expected: FAIL naming 9 scenarios (the Task 3 batch). The six edited here are no longer listed.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_floor.py -k three_verdict -v`
Expected: FAIL on the share line. The share is above 0.202 and still below 0.40, because six more scenarios can render three verdicts now and fifteen still cannot. The node assertion is not reached.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_propagation.py tests/test_shared_origin_training_pair.py tests/test_shared_origin_training.py -q --deselect tests/test_shared_origin_training.py::test_every_trainable_scenario_has_at_least_three_victims`
Expected: PASS. The local-cause uniqueness, shared-claim phrase, banned-shape, and victim-read tests all cover the new text.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_shared_origin_training.py tests/test_shared_origin_floor.py src/kubeagent_verdict/dataset/propagation.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: pin three victims per scenario and give six node scenarios a third"
```

### Task 3: Add the remaining nine third victims

**Files:**
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — the `victims=(` tuples of `_T_SECRET_KEY_RENAMED` (line 1271), `_T_AUTOSCALER_CAPACITY` (1372), `_T_BASE_IMAGE_TAG` (1581), `_T_PVC_MULTI_ATTACH` (1673), `_T_CNI_IP_POOL` (1762), `_T_LIMITRANGE_LOWERED` (2360), `_T_EGRESS_PROXY_DOWN` (2478), `_T_NS_PVC_FULL` (2572), `_T_MIGRATION_LOCK` (2671). Line numbers are from before Task 2; find each by its `key=` string.

**Interfaces:**
- Consumes: `Victim`, the conventions above, the test from Task 2.
- Produces: every one of the 24 existing scenarios has 3 or 4 victims; `test_every_trainable_scenario_has_at_least_three_victims` and `test_three_verdict_decoys_are_common_and_span_the_node_scenarios` are green.

- [ ] **Step 1: Confirm the test still fails and names exactly these nine**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py::test_every_trainable_scenario_has_at_least_three_victims -v`
Expected: FAIL listing shared-secret-key-renamed, cluster-autoscaler-at-capacity, shared-base-image-tag-moved, shared-pvc-multi-attach, cni-ip-pool-exhausted, namespace-limitrange-lowered, namespace-egress-proxy-down, namespace-shared-pvc-full, namespace-migration-lock-held.

- [ ] **Step 2: Append the nine victims**

Each block is the LAST element of the named scenario's `victims=(...)` tuple.

`_T_SECRET_KEY_RENAMED` (key `shared-secret-key-renamed`, tokens 'missing'/'intact'; existing victims are a Deployment and a StatefulSet):

```python
        Victim(
            workload_kind="Job", status="Init:CreateContainerConfigError",
            issue="Init:CreateContainerConfigError",
            reason="init container {init_container} could not build its environment",
            evidence="secret key not found for env var API_TOKEN",
            local_cause="this Job's own init container reads the key name from a "
                        "chart value that was set with a typo in its own values file",
            local_reason="the init container's own envFrom names the key with a "
                         "typo that appears in no other workload's manifest",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nInit Containers:\n  {init_container}: waiting, "
                   "CreateContainerConfigError\nEvents: Warning  Failed  kubelet  "
                   "Error: secret key not found for env var API_TOKEN")),
            pass_confidence="medium",
        ),
```

`_T_AUTOSCALER_CAPACITY` (key `cluster-autoscaler-at-capacity`, tokens 'blocked'/'eligible'; existing victims are a Deployment and a Job, so this one is a StatefulSet — R9):

```python
        Victim(
            workload_kind="StatefulSet", status="Pending", issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 3 Insufficient cpu",
            local_cause="this StatefulSet's own CPU request was raised in its last "
                        "rollout to more cores than any node in the pool has",
            local_reason="the StatefulSet's own pod spec asks for 12 cores and the "
                         "largest node in the pool has 8",
            read=("get_events {ns}/{name}",
                  ("Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                   "available: 3 Insufficient cpu")),
            pass_confidence="high",
        ),
```

`_T_BASE_IMAGE_TAG` (key `shared-base-image-tag-moved`, tokens 'failing'/'passing'; existing victims are a Deployment and a DaemonSet):

```python
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="exec format error at init entrypoint",
            local_cause="this Job's own init image was built for a different CPU "
                        "architecture than the nodes run",
            local_reason="the init container's own image manifest lists only an "
                         "arm64 layer and every node is amd64",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init container exited at startup, exec "
                   "format error (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
```

`_T_PVC_MULTI_ATTACH` (key `shared-pvc-multi-attach`, tokens 'wedged'/'flowing'; existing victims are a StatefulSet and a Job):

```python
        Victim(
            workload_kind="Deployment", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container {container}: timed out preparing "
                     "volume {pvc}",
            local_cause="this Deployment's own start hook copies data into its "
                        "volume and the copy runs past the kubelet's start deadline",
            local_reason="the container's own postStart copy moves 40 GiB on every "
                         "start and the kubelet's start timeout is 2 minutes",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed "
                   "to start container {container}: timed out preparing volume "
                   "{pvc}")),
            pass_confidence="medium",
        ),
```

`_T_CNI_IP_POOL` (key `cni-ip-pool-exhausted`, tokens 'depleted'/'available'; existing victims are a Deployment and a Job, so this one is a StatefulSet — R9):

```python
        Victim(
            workload_kind="StatefulSet", status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox: IPAM returned no address for "
                     "this pod",
            local_cause="this StatefulSet's own pod annotation pins an address "
                        "from a range that was removed from the IPAM config",
            local_reason="the pod's own address annotation names a range the IPAM "
                         "config no longer lists",
            read=("describe {ns}/{pod} (Pod)",
                  ("Node: {node}\nEvents: Warning  FailedCreatePodSandBox  kubelet  "
                   "Failed to create pod sandbox: plugin type cni failed: IPAM "
                   "returned no address for this pod")),
            pass_confidence="medium",
        ),
```

`_T_LIMITRANGE_LOWERED` (key `namespace-limitrange-lowered`, tokens 'lowered'/'restored'; existing victims are a Deployment and a Job):

```python
        Victim(
            workload_kind="StatefulSet", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="heap reservation failed: cannot allocate memory",
            local_cause="this StatefulSet's own heap flag is set above the "
                        "container's memory limit, so its runtime refuses to start",
            local_reason="the container's own maximum heap flag is larger than its "
                         "memory limit, a mismatch inside its own manifest",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: heap reservation failed, cannot allocate "
                   "memory (3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
```

`_T_EGRESS_PROXY_DOWN` (key `namespace-egress-proxy-down`, tokens 'restarting'/'steady'; existing victims are a Deployment and a StatefulSet):

```python
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="seed download through the proxy failed",
            local_cause="this Job's own init container downloads its seed data "
                        "from a host that was decommissioned last month",
            local_reason="the init container's own download address names a host "
                         "that no longer resolves anywhere",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: init download through the proxy failed "
                   "(3 of 3 sampled restarts)")),
            pass_confidence="medium",
        ),
```

`_T_NS_PVC_FULL` (key `namespace-shared-pvc-full`, tokens 'full'/'free'; existing victims are a StatefulSet and a Deployment):

```python
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="last state terminated with exit code 1",
            log_cause="write to output path failed: no space left on device",
            local_cause="this agent's own scratch directory sits on a small tmpfs "
                        "mount that each rotation overflows",
            local_reason="the agent's own tmpfs mount is 64 MiB and its rotation "
                         "writes 80 MiB before deleting the old file",
            read=("get_log_causes {ns}/{pod}",
                  ("classified cause: write to its output path failed, no space "
                   "left on device (3 of 3 sampled restarts)")),
            pass_confidence="high",
        ),
```

`_T_MIGRATION_LOCK` (key `namespace-migration-lock-held`, tokens 'held'/'released'; existing victims are a Job and a Deployment):

```python
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this StatefulSet's own readiness endpoint stays not-ready "
                        "through a warm-up that outlasts its probe's failure threshold",
            local_reason="the container's own warm-up log shows 4 minutes of "
                         "loading and its probe gives up after 90 seconds",
            read=("get_events {ns}/{name}",
                  ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP "
                   "probe failed with statuscode: 503")),
            pass_confidence="medium",
        ),
```

- [ ] **Step 3: Run the two tests and the structural suites**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py::test_every_trainable_scenario_has_at_least_three_victims -v`
Expected: PASS.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_floor.py -v`
Expected: PASS, all three tests. The share is about 0.50: every scenario now cycles its pair width over 2 and 3 (or 2, 3 and 4), so about half of the decoy rows carry three or more verdicts, and the seven node scenarios all contribute.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_propagation.py tests/test_shared_origin_training_pair.py tests/test_shared_origin_training.py tests/test_generate.py -q`
Expected: PASS. In particular `test_no_two_trainable_scenarios_share_a_local_cause`, `test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim`, `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`, and `test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half` all pass over the new text.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/propagation.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: give the nine remaining two-victim scenarios a third victim"
```

### Task 4: Teach the exam's layouts on eleven existing scenarios, and fix `Taints:  none`

**Files:**
- Modify: `tests/test_shared_origin_training.py` (two new tests after `test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half`, line 230)
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — `origin_variants` of `_T_NODE_PID_PRESSURE`, `_T_KUBE_PROXY`, `_T_CSI_NODE_DRIVER`, `_T_NODE_RUNTIME_RESTARTING`, `_T_NODE_CLOCK_SKEW`, `_T_NODE_CONNTRACK_FULL`, `_T_POD_IDENTITY_WEBHOOK`, `_T_SCALED_TO_ZERO`, `_T_EGRESS_PROXY_DOWN`, `_T_STORAGECLASS_POOL_RETIRED`, `_T_NETPOL_EGRESS_ALLOWLIST`; and the two `Taints:  none` lines in `_T_NODE_MEMORY_PRESSURE` (lines 3150 and 3173 before Tasks 2–3 shifted them).

**Interfaces:**
- Consumes: R1, R2, R3, R4, R5 from the rules section.
- Produces: eleven scenarios each with a fifth variant that copies the exam's layout line for line; the per-layout floors Task 9 counts.

- [ ] **Step 1: Write the two failing tests**

```python
# The exam's six reads use real kubectl layouts. These markers, with the
# exam's own spacing, say "this half is laid out the way the exam is".
_EXAM_LAYOUT_MARKERS = {
    "node-pid-pressure": ("Conditions:\n", "Taints:  "),
    "kube-proxy-degraded": ("Conditions:\n", "Taints:  "),
    "csi-node-driver-crashed": ("Conditions:\n", "Taints:  "),
    "node-runtime-restarting": ("Conditions:\n", "Taints:  "),
    "node-clock-skew": ("Conditions:\n", "Taints:  "),
    "node-conntrack-full": ("Conditions:\n", "Taints:  "),
    "pod-identity-webhook-down": ("Replicas:  ", "Pods:      ", "Last log:  "),
    "shared-dependency-scaled-to-zero": ("Replicas:  ", "Pods:      ",
                                         "Last log:  "),
    "namespace-egress-proxy-down": ("Replicas:  ", "Pods:      ", "Last log:  "),
    "storageclass-pool-retired": ("provisioner: ",
                                  "PersistentVolumes bound in the last 20m: "),
    "networkpolicy-egress-allowlist-stale": ("podSelector: ", "policyTypes: ",
                                             "egress: ", "pods selected: "),
}


def test_the_eleven_named_scenarios_carry_an_exam_layout_variant():
    """The 0907 model read `describe node` in the exam and had never seen a
    `Conditions:` table with a `Taints:` line in training. Each scenario
    named here shares a read kind with one of the six exam origins, and
    must carry at least one variant laid out the way the exam is."""
    by_key = {p.key: p for p in propagation.trainable_scenarios()}
    missing = []
    for key, markers in _EXAM_LAYOUT_MARKERS.items():
        halves = [h for pair in by_key[key].origin_variants for h in pair]
        if not any(all(m in half for m in markers) for half in halves):
            missing.append(key)
    assert missing == [], f"scenarios without an exam-layout variant: {missing}"


def test_node_memory_pressure_spells_no_taint_the_way_kubectl_does():
    """kubectl prints `Taints:  <none>`. The record said `Taints:  none`."""
    p = {q.key: q for q in propagation.trainable_scenarios()}["node-memory-pressure"]
    assert "Taints:  <none>" in p.healthy_origin_content
    assert "Taints:  none" not in p.healthy_origin_content
    healthy_halves = "\n".join(h for _b, h in p.origin_variants)
    assert "Taints:  none" not in healthy_halves
    assert p.origin_variants[0][1] == p.healthy_origin_content
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k "exam_layout_variant or spells_no_taint" -v`
Expected: both FAIL. The first lists all eleven keys; the second fails on `Taints:  <none>`.

- [ ] **Step 3: Fix the spelling**

In `_T_NODE_MEMORY_PRESSURE`, change both occurrences of `"Taints:  none"` to `"Taints:  <none>"` — one inside `healthy_origin_content`, one inside `origin_variants[0][1]`. The two strings must stay byte-identical; `test_every_trainable_scenario_declares_at_least_four_origin_variants` checks `origin_variants[0] == (origin_read[1], healthy_origin_content)`.

- [ ] **Step 4: Append the six node-scoped variants**

Each tuple is appended as the LAST element of the named scenario's `origin_variants=(...)`. The first line is the state line (R1, R3); the rest copies the exam's `describe node {node}` layout: a `Conditions:` table with the exam's column spacing, then a `Taints:` line. The broken half never contains the healthy token and the healthy half never contains the broken token (R4, R5).

`_T_NODE_PID_PRESSURE` ('exhausted' / 'available'):

```python
        (("PID condition on this node: exhausted\n"
          "Conditions:\n"
          "  PIDPressure      True    KubeletHasInsufficientPID   process table exhausted\n"
          "  Ready            True    KubeletReady                kubelet is posting ready status\n"
          "Taints:  node.kubernetes.io/pid-pressure:NoSchedule"),
         ("PID condition on this node: available\n"
          "Conditions:\n"
          "  PIDPressure      False   KubeletHasSufficientPID     pids available\n"
          "  Ready            True    KubeletReady                kubelet is posting ready status\n"
          "Taints:  <none>")),
```

`_T_KUBE_PROXY` ('stale' / 'fresh'; 11m agrees with the shared_reason — R2):

```python
        (("node view of kube-proxy: stale\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "kube-proxy: Service routes stale (last sync 11m ago)"),
         ("node view of kube-proxy: fresh\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "kube-proxy: Service routes fresh (last sync 12s ago)")),
```

`_T_CSI_NODE_DRIVER` ('crashed' / 'healthy'; 4 restarts agrees with the shared_reason):

```python
        (("node view of the CSI plugin: crashed\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "CSI node plugin: crashed (CrashLoopBackOff, 4 restarts)"),
         ("node view of the CSI plugin: healthy\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "CSI node plugin: healthy (Running, 0 restarts)")),
```

`_T_NODE_RUNTIME_RESTARTING` ('restarting' / 'stable'):

```python
        (("kubelet view of the runtime: restarting\n"
          "Conditions:\n"
          "  Ready            False   KubeletNotReady   "
          "container runtime is restarting (PLEG is not healthy)\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  node.kubernetes.io/not-ready:NoSchedule"),
         ("kubelet view of the runtime: stable\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   container runtime is stable\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>")),
```

`_T_NODE_CLOCK_SKEW` ('skewed' / 'synced'; 6m42s agrees with the shared_reason):

```python
        (("clock state on this node: skewed\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "System clock: skewed by 6m42s against the cluster time source"),
         ("clock state on this node: synced\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "System clock: synced (offset 4ms)")),
```

`_T_NODE_CONNTRACK_FULL` ('full' / 'clear'):

```python
        (("node view of conntrack: full\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Conntrack: full (262144 of 262144 entries)"),
         ("node view of conntrack: clear\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Conntrack: clear (31200 of 262144 entries)")),
```

- [ ] **Step 5: Append the three Deployment-layout variants**

These copy the exam's `describe kube-system/coredns (Deployment)` layout: a `Replicas:` line with five counts, one `Pods:` row per pod with the exam's column spacing, and a `Last log:` line. Pod names are made-up hash suffixes; they are fixtures, not real identifiers.

`_T_POD_IDENTITY_WEBHOOK` ('down' / 'serving'; 2 desired, 0 available agrees with the shared_reason):

```python
        (("webhook Deployment: down\n"
          "Replicas:  2 desired | 2 updated | 2 total | 0 available | 2 unavailable\n"
          "Pods:      pod-identity-webhook-6c9d7f8b4-x2k9q   0/1  CrashLoopBackOff  6 restarts\n"
          "           pod-identity-webhook-6c9d7f8b4-m4v7t   0/1  CrashLoopBackOff  6 restarts\n"
          "Last log:  webhook down: listener failed to bind"),
         ("webhook Deployment: serving\n"
          "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
          "Pods:      pod-identity-webhook-6c9d7f8b4-x2k9q   1/1  Running  0 restarts\n"
          "           pod-identity-webhook-6c9d7f8b4-m4v7t   1/1  Running  0 restarts\n"
          "Last log:  serving admission requests, 0 errors")),
```

`_T_SCALED_TO_ZERO` ('replicas to 0' / 'Running'; the broken half must not contain "Running" anywhere, and the healthy half must not contain "replicas to 0"):

```python
        (("Deployment scale state: replicas to 0\n"
          "Replicas:  0 desired | 0 updated | 0 total | 0 available | 0 unavailable\n"
          "Pods:      <none>\n"
          "Last log:  deployment scaled replicas to 0 (manual)"),
         ("Deployment scale state: 2 of 2 Running\n"
          "Replicas:  2 desired | 2 updated | 2 total | 2 available | 0 unavailable\n"
          "Pods:      session-5b7c9d6f4-k3p8w   1/1  Running  0 restarts\n"
          "           session-5b7c9d6f4-r9x2n   1/1  Running  0 restarts\n"
          "Last log:  serving, 2 of 2 Running")),
```

`_T_EGRESS_PROXY_DOWN` ('restarting' / 'steady'; 3 desired, 0 available agrees with the shared_reason; "0 restarts" is fine because the token is "restarting"):

```python
        (("proxy rollout state: restarting\n"
          "Replicas:  3 desired | 3 updated | 3 total | 0 available | 3 unavailable\n"
          "Pods:      egress-proxy-7f4d8c9b5-a2k7m   0/1  CrashLoopBackOff  12 restarts\n"
          "           egress-proxy-7f4d8c9b5-q8w3r   0/1  CrashLoopBackOff  12 restarts\n"
          "           egress-proxy-7f4d8c9b5-z5n1t   0/1  CrashLoopBackOff  12 restarts\n"
          "Last log:  restarting: proxy config invalid"),
         ("proxy rollout state: steady\n"
          "Replicas:  3 desired | 3 updated | 3 total | 3 available | 0 unavailable\n"
          "Pods:      egress-proxy-7f4d8c9b5-a2k7m   1/1  Running  0 restarts\n"
          "           egress-proxy-7f4d8c9b5-q8w3r   1/1  Running  0 restarts\n"
          "           egress-proxy-7f4d8c9b5-z5n1t   1/1  Running  0 restarts\n"
          "Last log:  steady, 0 errors in 1h")),
```

- [ ] **Step 6: Append the StorageClass and NetworkPolicy variants**

`_T_STORAGECLASS_POOL_RETIRED` ('retired' / 'online'). This copies the exam's `get_related storageclass standard` layout. The line `PersistentVolumes bound in the last 20m:` is the marker Task 9's storage floor counts, and the existing four variants do not carry it. 0 bound agrees with the shared_reason.

```python
        (("ssd-premium class: retired\n"
          "provisioner: example.com/ssd-csi\n"
          "controller storage-system/ssd-csi-controller: 1/1 ready, Running\n"
          "pool ssd-tier-a status: retired\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("ssd-premium class: online\n"
          "provisioner: example.com/ssd-csi\n"
          "controller storage-system/ssd-csi-controller: 1/1 ready, Running\n"
          "pool ssd-tier-b status: online\n"
          "PersistentVolumes bound in the last 20m: 5")),
```

`_T_NETPOL_EGRESS_ALLOWLIST` ('blocked' / 'allowed'). This copies the exam's `get_related networkpolicy {ns}/default-deny` layout. "allow to" does not contain "allowed", so the broken half stays clean.

```python
        (("policy match state: blocked\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to tier=datastore tcp/5432 (datastore pods now carry tier=data)\n"
          "connections to datastore: blocked\n"
          "pods selected: 6 of 6"),
         ("policy match state: allowed\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to tier=data tcp/5432\n"
          "connections to datastore: allowed\n"
          "pods selected: 6 of 6")),
```

- [ ] **Step 7: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py -v`
Expected: all PASS, including the two new tests, `test_every_variant_first_line_is_literal_and_unique_within_its_scenario`, `test_every_trainable_scenario_names_its_state_in_words`, and `test_no_two_variants_are_the_same_rendering_with_different_numbers`. If the state-words test fails, the failing variant contains the other half's token; read R4 and R5 and remove the word rather than changing the token.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean. The project's ruff line length is 100 (`pyproject.toml`); if ruff reports E501 on a variant line, wrap the string with an extra `"..."` continuation and keep the text byte-identical.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: teach the exam's read layouts on eleven trainable scenarios"
```

---

### Task 5: Group A — six node-scoped scenarios in the exam's `describe node` layout

**Files:**
- Modify: `tests/test_shared_origin_training.py` — rename `test_the_trainable_pool_holds_twenty_four_scenarios` (line 717 before Tasks 2–4 shifted it) to `test_the_trainable_pool_holds_the_planned_count` with a module constant `EXPECTED_POOL = 30`, and widen `test_a_negative_multi_row_shows_the_component_healthy` (line 585 before the shifts) to one healthy first line per scenario under a shared label
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — six new `Propagation` records placed directly before `_TRAINING_SCENARIOS`, and six new names appended to the `_TRAINING_SCENARIOS` tuple

**Interfaces:**
- Consumes: `Propagation`, `Victim` (propagation.py lines 136–223); the rules section; `vocab.ISSUE_KINDS`.
- Produces: keys `node-network-unavailable`, `node-kernel-deadlock`, `node-readonly-filesystem`, `node-frequent-kubelet-restart`, `node-cordoned-draining`, `node-corrupt-overlay`; `EXPECTED_POOL` that Tasks 6–9 bump.

Why these six: the 0907 model read the exam's `describe node {node}` (node-not-ready and node-disk-pressure) and had seen a `Conditions:` table only on node-memory-pressure. After this task, thirteen trainable node scenarios carry it (node-memory-pressure, the six Task 4 touched, and these six), each with a different condition type, so the model learns to read the table rather than one memorised row.

- [ ] **Step 1: Rename the pool-pin test and make it fail**

Replace the test at line 717 (name `test_the_trainable_pool_holds_twenty_four_scenarios`) with:

```python
# The pool grows by group across Tasks 5–9. Twenty-four is what it held when
# the 0907 run failed deciders 1 and 5; forty-eight is the planned end.
EXPECTED_POOL = 30


def test_the_trainable_pool_holds_the_planned_count():
    """The pool is pinned so a scenario cannot fall out of the tuple unseen."""
    pool = propagation.trainable_scenarios()
    assert len(pool) == EXPECTED_POOL
    assert len({p.key for p in pool}) == EXPECTED_POOL
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k planned_count -v`
Expected: FAIL, `24 == 30`.

In the same file, replace `test_a_negative_multi_row_shows_the_component_healthy` (line 585 before Tasks 1–4 shifted it) with:

```python
def test_a_negative_multi_row_shows_the_component_healthy(rows):
    """Same label, opposite content — otherwise the label is still the answer.

    Several scenarios share one read label: every node scenario in the
    exam's layout heads `describe node {node}`. So the healthy first lines
    are collected per label, and a row must show one of them. A dict of one
    content per label kept only the last scenario registered and failed
    every other scenario's negative row.
    """
    healthy = {}
    for p in propagation.trainable_scenarios():
        first = p.healthy_origin_content.split("\n")[0]
        healthy.setdefault(p.origin_read[0], set()).add(first)
    broken = {p.origin_read[1].split("\n")[0]
              for p in propagation.trainable_scenarios()}
    seen = 0
    for e in _by_case(rows, "multi"):
        if "origin_read_label" not in e.meta:
            continue
        seen += 1
        assert e.meta["origin_healthy"] is True
        first_lines = healthy[e.meta["origin_read_label"]]
        assert any(line in e.user for line in first_lines), e.meta
        for b in broken:
            assert b not in e.user
    assert seen
```

Why here: this task is the first to add a second scenario under `describe node {node}` (kube-proxy-degraded already heads it), and `cases.multi` renders `healthy_origin_content` for a negative row, never a variant. The rewrite passes on the twenty-four pool too, so it goes in before the records.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k component_healthy -v`
Expected: PASS.

- [ ] **Step 2: Write the first three records**

Insert them directly above `_TRAINING_SCENARIOS = (`. Every record follows the `_T_NODE_PID_PRESSURE` style: 4-space indent inside `Propagation(`, 8 for `Victim(`, 12 for fields.

```python
_T_NODE_NETWORK_UNAVAILABLE = Propagation(
    key="node-network-unavailable",
    blast_radius="node",
    scope_field="node",
    origin="the node lost its route to the pod network, so no pod placed there can get "
           "a sandbox",
    shared_cause="node {node} has no route to the pod network, so no pod placed there "
                 "can get a sandbox",
    shared_reason="{node} reports NetworkUnavailable True with reason NoRouteCreated, "
                  "the network-unavailable taint is on the node, and every pod that "
                  "landed there in the last 9m is stuck creating its sandbox",
    distractor_cause="the CNI plugin binary was removed from these pods' images in the "
                     "last rebuild",
    distractor_reason="the CNI plugin is installed on the node, not in a workload "
                      "image, and the failing pods were built from unrelated images",
    rationale="the node has no route to the pod network, so the kubelet cannot give "
              "any pod on it a network sandbox; this workload is one of the pods "
              "placed there, and its own spec is unchanged",
    remedy="Restore the pod-network route on {node} (restart the network agent or "
           "re-run the route controller) and let the stuck pods retry; the flagged "
           "workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Pod network route on this node: missing\n"
         "Conditions:\n"
         "  NetworkUnavailable   True    NoRouteCreated   route to the pod network is "
         "missing\n"
         "  Ready                True    KubeletReady     kubelet is posting ready "
         "status\n"
         "Taints:  node.kubernetes.io/network-unavailable:NoSchedule"),
    ),
    healthy_origin_content=(
        "Pod network route on this node: installed\n"
        "Conditions:\n"
        "  NetworkUnavailable   False   RouteCreated     route to the pod network is "
        "installed\n"
        "  Ready                True    KubeletReady     kubelet is posting ready "
        "status\n"
        "Taints:  <none>"
    ),
    origin_state=("missing", "installed"),
    origin_variants=(
        (("Pod network route on this node: missing\n"
          "Conditions:\n"
          "  NetworkUnavailable   True    NoRouteCreated   route to the pod network is "
          "missing\n"
          "  Ready                True    KubeletReady     kubelet is posting ready "
          "status\n"
          "Taints:  node.kubernetes.io/network-unavailable:NoSchedule"),
         ("Pod network route on this node: installed\n"
          "Conditions:\n"
          "  NetworkUnavailable   False   RouteCreated     route to the pod network is "
          "installed\n"
          "  Ready                True    KubeletReady     kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("the route controller reports this node's pod-network route missing\n"
          "no sandbox has been created on the node for 9m\n"
          "the network-unavailable taint is set"),
         ("the route controller reports this node's pod-network route installed\n"
          "sandboxes are being created on the node normally\n"
          "no network-unavailable taint is set")),
        (("Warning  NetworkNotReady  kubelet  pod network route missing: cannot set up "
          "a sandbox on this node"),
         ("Normal  NetworkReady  kubelet  pod network route installed: sandboxes are "
          "being set up on this node")),
        (("route state: missing\n"
          "sandboxes created in the last 10m: 0 of 14 attempts\n"
          "kubelet has logged NetworkPluginNotReady for 9m"),
         ("route state: installed\n"
          "sandboxes created in the last 10m: 14 of 14 attempts\n"
          "kubelet has logged no network plugin error")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox: network plugin returned error: no "
                     "route to the pod network",
            local_cause="this Deployment's own pod spec asks for a host network it is "
                        "not allowed to use",
            local_reason="the pod spec sets hostNetwork true and the namespace's "
                         "pod security policy rejects it",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  FailedCreatePodSandBox  kubelet  "
                  "Failed to create pod sandbox: network plugin returned error"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 1 node(s) had untolerated taint "
                     "node.kubernetes.io/network-unavailable, 2 Insufficient memory",
            local_cause="this StatefulSet's own memory request was doubled in its last "
                        "rollout past what the two remaining nodes can offer",
            local_reason="the pod asks for 24Gi and the two schedulable nodes have "
                         "16Gi free each",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: 1 node(s) had an untolerated taint, 2 Insufficient memory"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dial tcp: connect: network is unreachable",
            local_cause="this agent's own readiness probe checks a port the last config "
                        "change moved",
            local_reason="the probe dials 9100 and the agent now listens on 9101",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: dial tcp: "
                  "connect: network is unreachable"),
            pass_confidence="high",
        ),
    ),
)

_T_NODE_KERNEL_DEADLOCK = Propagation(
    key="node-kernel-deadlock",
    blast_radius="node",
    scope_field="node",
    origin="the node's kernel has a deadlocked task, so every container operation on "
           "it hangs",
    shared_cause="the kernel on node {node} has a deadlocked task, so every container "
                 "operation on that node hangs",
    shared_reason="{node} reports KernelDeadlock True with a task hung for more than "
                  "120 seconds, and every container start, exec and probe on the node "
                  "has stalled since",
    distractor_cause="the container runtime on the node was upgraded to a build that "
                     "hangs on cgroup v2",
    distractor_reason="the runtime version on the node is unchanged since last month "
                      "and the same build runs fine on its peers",
    rationale="a hung kernel task on {node} is blocking every container operation the "
              "kubelet issues there; this workload is on that node, and its hang is "
              "the node's, not its own",
    remedy="Reboot {node} (or drain it and let the hung task clear) and let its pods "
           "reschedule; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Kernel task state on this node: hung\n"
         "Conditions:\n"
         "  KernelDeadlock   True    KernelHasDeadlock   a task has hung for more than "
         "120 seconds\n"
         "  Ready            True    KubeletReady        kubelet is posting ready "
         "status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Kernel task state on this node: responsive\n"
        "Conditions:\n"
        "  KernelDeadlock   False   KernelHasNoDeadlock   every task is responsive\n"
        "  Ready            True    KubeletReady          kubelet is posting ready "
        "status\n"
        "Taints:  <none>"
    ),
    origin_state=("hung", "responsive"),
    origin_variants=(
        (("Kernel task state on this node: hung\n"
          "Conditions:\n"
          "  KernelDeadlock   True    KernelHasDeadlock   a task has hung for more than "
          "120 seconds\n"
          "  Ready            True    KubeletReady        kubelet is posting ready "
          "status\n"
          "Taints:  <none>"),
         ("Kernel task state on this node: responsive\n"
          "Conditions:\n"
          "  KernelDeadlock   False   KernelHasNoDeadlock   every task is responsive\n"
          "  Ready            True    KubeletReady          kubelet is posting ready "
          "status\n"
          "Taints:  <none>")),
        (("the node problem detector reports a kernel task hung on this node\n"
          "container starts and execs on the node have stalled for 6m\n"
          "the kubelet is still posting ready status"),
         ("the node problem detector reports every kernel task responsive on this "
          "node\n"
          "container starts and execs on the node complete normally\n"
          "the kubelet is posting ready status")),
        (("Warning  KernelDeadlock  node-problem-detector  task hung for 120s: "
          "INFO: task containerd-shim:4821 blocked for more than 120 seconds"),
         ("Normal  KernelResponsive  node-problem-detector  every task responsive: no "
          "blocked task in the last 30m")),
        (("kernel watchdog: hung\n"
          "blocked tasks: 3\n"
          "oldest blocked task age: 6m14s"),
         ("kernel watchdog: responsive\n"
          "blocked tasks: 0\n"
          "oldest blocked task age: n/a")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: context deadline exceeded",
            local_cause="this Deployment's own entrypoint waits on a lock file that a "
                        "previous run left behind",
            local_reason="the container's start script blocks on a stale lock in its "
                         "own working directory",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: context deadline exceeded"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: command timed out after 5s",
            local_cause="this StatefulSet's own exec probe runs a query that no longer "
                        "finishes inside its 5s timeout",
            local_reason="the probe query scans a table that has grown past what the "
                         "timeout allows",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: command timed "
                  "out after 5s"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="Liveness probe failed: command timed out; container will be "
                     "restarted",
            local_cause="this agent's own liveness hook forks a helper that blocks on "
                        "a pipe nobody reads",
            local_reason="the hook's helper writes to a pipe with no reader and the "
                         "hook waits on it",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: liveness command timed out, killed by kubelet "
                  "(3 of 3 sampled restarts)"),
            log_cause="liveness command timed out, killed by kubelet",
            pass_confidence="high",
        ),
    ),
)

_T_NODE_READONLY_FILESYSTEM = Propagation(
    key="node-readonly-filesystem",
    blast_radius="node",
    scope_field="node",
    origin="the node's root filesystem remounted read-only after an I/O error, so no "
           "container there can write to disk",
    shared_cause="the root filesystem on node {node} is mounted read-only, so no "
                 "container there can write to disk",
    shared_reason="{node} reports ReadonlyFilesystem True after an I/O error, and "
                  "every container on the node that writes to its own filesystem has "
                  "failed since the remount 8m ago",
    distractor_cause="the workloads' own images were rebuilt with a read-only root "
                     "filesystem setting",
    distractor_reason="the pod specs declare no readOnlyRootFilesystem and the images "
                      "are unchanged since last week",
    rationale="the root filesystem on {node} is read-only, so every container write on "
              "the node fails; this workload writes on start and is one of them",
    remedy="Repair the disk behind {node}'s root filesystem and remount it writable "
           "(or replace the node) and let the pods reschedule; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Root filesystem on this node: read-only\n"
         "Conditions:\n"
         "  ReadonlyFilesystem   True    FilesystemIsReadOnly   root filesystem "
         "remounted read-only after an I/O error\n"
         "  Ready                True    KubeletReady           kubelet is posting "
         "ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Root filesystem on this node: writable\n"
        "Conditions:\n"
        "  ReadonlyFilesystem   False   FilesystemIsNotReadOnly   root filesystem is "
        "writable\n"
        "  Ready                True    KubeletReady              kubelet is posting "
        "ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("read-only", "writable"),
    origin_variants=(
        (("Root filesystem on this node: read-only\n"
          "Conditions:\n"
          "  ReadonlyFilesystem   True    FilesystemIsReadOnly   root filesystem "
          "remounted read-only after an I/O error\n"
          "  Ready                True    KubeletReady           kubelet is posting "
          "ready status\n"
          "Taints:  <none>"),
         ("Root filesystem on this node: writable\n"
          "Conditions:\n"
          "  ReadonlyFilesystem   False   FilesystemIsNotReadOnly   root filesystem is "
          "writable\n"
          "  Ready                True    KubeletReady              kubelet is posting "
          "ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports this node's root filesystem read-only\n"
          "the remount followed an I/O error 8m ago\n"
          "every container write on the node has failed since"),
         ("the node problem detector reports this node's root filesystem writable\n"
          "no I/O error has been logged on the node\n"
          "container writes on the node succeed")),
        (("Warning  FilesystemIsReadOnly  node-problem-detector  root filesystem "
          "remounted read-only: EXT4-fs error on sda1"),
         ("Normal  FilesystemIsWritable  node-problem-detector  root filesystem "
          "writable: no error on sda1 in the last 24h")),
        (("mount state of the root filesystem: read-only\n"
          "I/O errors on the root device in the last 1h: 37\n"
          "container writes failing on the node: all"),
         ("mount state of the root filesystem: writable\n"
          "I/O errors on the root device in the last 1h: 0\n"
          "container writes failing on the node: none")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="open /var/run/app.pid: input/output error",
            local_cause="this Deployment's own container writes its pid file to a path "
                        "its image marks immutable",
            local_reason="the image sets the pid directory immutable at build time and "
                         "the entrypoint still writes there",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: write to the container filesystem failed "
                  "(3 of 3 sampled restarts)"),
            log_cause="write to the container filesystem failed",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: mkdir /run/containerd: "
                     "input/output error",
            local_cause="this Job's own container image is corrupt in the registry "
                        "and fails to unpack",
            local_reason="the image manifest lists a layer whose digest does not "
                         "match its content",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: input/output error"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.SetUp failed for volume {pvc}: mkdir on the node's "
                     "kubelet directory: input/output error",
            local_cause="this StatefulSet's own claim asks for a filesystem type the "
                        "node's kernel cannot mount",
            local_reason="the claim's storage class sets fsType xfs and the node "
                         "image ships no xfs module",
            read=("describe {ns}/{pvc} (PersistentVolumeClaim)",
                  "Status: Bound\nVolume: pv-{pvc}\nEvents: Warning  FailedMount  "
                  "kubelet  MountVolume.SetUp failed for volume {pvc}"),
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 3: Write the last three records**

Insert them directly after `_T_NODE_READONLY_FILESYSTEM`. node-cordoned-draining is the second scenario (after node-network-unavailable) whose broken half carries a real taint; the other four keep `Taints:  <none>` on both halves because their fault is not a taint.

```python
_T_NODE_FREQUENT_KUBELET_RESTART = Propagation(
    key="node-frequent-kubelet-restart",
    blast_radius="node",
    scope_field="node",
    origin="the node's kubelet keeps restarting, so its pods keep losing probes and "
           "container starts",
    shared_cause="the kubelet on node {node} keeps restarting, so its pods keep losing "
                 "probes and container starts",
    shared_reason="{node} reports FrequentKubeletRestart True with 6 kubelet restarts "
                  "in 20 minutes, and every probe and container start on the node "
                  "has been interrupted at least once in that window",
    distractor_cause="the workloads' own probes were tightened in the last chart "
                     "release",
    distractor_reason="the probe settings are unchanged since last month and the same "
                      "settings pass on pods scheduled to other nodes",
    rationale="the kubelet on {node} is flapping, so every probe and container start "
              "it owns is cut short; this workload is on that node and its own "
              "spec is unchanged",
    remedy="Stop the kubelet restart loop on {node} (read its journal, fix the "
           "crashing config or reprovision the node); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Kubelet on this node: flapping\n"
         "Conditions:\n"
         "  FrequentKubeletRestart   True    FrequentKubeletRestart     kubelet is "
         "flapping: 6 restarts in 20 minutes\n"
         "  Ready                    True    KubeletReady               kubelet is "
         "posting ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Kubelet on this node: steady\n"
        "Conditions:\n"
        "  FrequentKubeletRestart   False   NoFrequentKubeletRestart   kubelet is "
        "steady: 0 restarts in 20 minutes\n"
        "  Ready                    True    KubeletReady               kubelet is "
        "posting ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("flapping", "steady"),
    origin_variants=(
        (("Kubelet on this node: flapping\n"
          "Conditions:\n"
          "  FrequentKubeletRestart   True    FrequentKubeletRestart     kubelet is "
          "flapping: 6 restarts in 20 minutes\n"
          "  Ready                    True    KubeletReady               kubelet is "
          "posting ready status\n"
          "Taints:  <none>"),
         ("Kubelet on this node: steady\n"
          "Conditions:\n"
          "  FrequentKubeletRestart   False   NoFrequentKubeletRestart   kubelet is "
          "steady: 0 restarts in 20 minutes\n"
          "  Ready                    True    KubeletReady               kubelet is "
          "posting ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports the kubelet on this node flapping\n"
          "the kubelet has restarted 6 times in the last 20m\n"
          "each restart cut every probe and container start on the node short"),
         ("the node problem detector reports the kubelet on this node steady\n"
          "the kubelet has not restarted in the last 20m\n"
          "probes and container starts on the node complete normally")),
        (("Warning  FrequentKubeletRestart  node-problem-detector  kubelet flapping: "
          "6 restarts in 20m, last exit status 1"),
         ("Normal  KubeletSteady  node-problem-detector  kubelet steady: 0 restarts in "
          "20m, uptime 31d")),
        (("kubelet service state: flapping\n"
          "restarts in the last 20m: 6\n"
          "seconds since the last kubelet start: 48"),
         ("kubelet service state: steady\n"
          "restarts in the last 20m: 0\n"
          "seconds since the last kubelet start: 2678400")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: probe interrupted by kubelet restart",
            local_cause="this Deployment's own readiness handler returns 503 until a "
                        "cache warm-up that takes longer than its probe allows",
            local_reason="the handler reports not-ready for 90s after start and the "
                         "probe fails it after 30s",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="container was killed: kubelet restarted mid-start",
            local_cause="this agent's own config reload handler exits the process "
                        "whenever its watched file is rewritten",
            local_reason="the config file is rewritten every few minutes by a sidecar "
                         "and each rewrite exits the agent",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: process exited on config reload "
                  "(3 of 3 sampled restarts)"),
            log_cause="process exited on config reload",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: kubelet connection reset during "
                     "container create",
            local_cause="this Job's own container command names a binary the image "
                        "does not ship",
            local_reason="the command runs a tool that was dropped from the image "
                         "in its last rebuild",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container {container}"),
            pass_confidence="high",
        ),
    ),
)

_T_NODE_CORDONED_DRAINING = Propagation(
    key="node-cordoned-draining",
    blast_radius="node",
    scope_field="node",
    origin="the node is cordoned and draining, so its pods are being evicted and "
           "nothing new lands there",
    shared_cause="node {node} is cordoned and draining, so its pods are being evicted "
                 "and nothing new lands there",
    shared_reason="{node} is marked unschedulable with the unschedulable taint, a "
                  "drain has been evicting its pods for 7m, and every pod that "
                  "needs that node is either evicted or waiting on it",
    distractor_cause="the cluster is out of capacity and the pending pods are waiting "
                     "on the autoscaler",
    distractor_reason="the other nodes have room and the autoscaler reports no "
                      "scale-up in progress",
    rationale="{node} is cordoned and being drained, so its pods are evicted and any "
              "pod pinned to it waits; this workload's trouble is the drain, not its "
              "own spec",
    remedy="Finish or cancel the drain of {node} and uncordon it when it is ready; "
           "the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Scheduling on this node: cordoned\n"
         "Unschedulable: true\n"
         "Conditions:\n"
         "  Ready            True    KubeletReady   kubelet is posting ready status\n"
         "  MemoryPressure   False   KubeletHasSufficientMemory\n"
         "  DiskPressure     False   KubeletHasNoDiskPressure\n"
         "Taints:  node.kubernetes.io/unschedulable:NoSchedule\n"
         "Events: Normal  NodeNotSchedulable  kubelet  this node is cordoned and "
         "draining"),
    ),
    healthy_origin_content=(
        "Scheduling on this node: accepting\n"
        "Unschedulable: false\n"
        "Conditions:\n"
        "  Ready            True    KubeletReady   kubelet is posting ready status\n"
        "  MemoryPressure   False   KubeletHasSufficientMemory\n"
        "  DiskPressure     False   KubeletHasNoDiskPressure\n"
        "Taints:  <none>\n"
        "Events: Normal  NodeSchedulable  kubelet  this node is accepting pods"
    ),
    origin_state=("cordoned", "accepting"),
    origin_variants=(
        (("Scheduling on this node: cordoned\n"
          "Unschedulable: true\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  node.kubernetes.io/unschedulable:NoSchedule\n"
          "Events: Normal  NodeNotSchedulable  kubelet  this node is cordoned and "
          "draining"),
         ("Scheduling on this node: accepting\n"
          "Unschedulable: false\n"
          "Conditions:\n"
          "  Ready            True    KubeletReady   kubelet is posting ready status\n"
          "  MemoryPressure   False   KubeletHasSufficientMemory\n"
          "  DiskPressure     False   KubeletHasNoDiskPressure\n"
          "Taints:  <none>\n"
          "Events: Normal  NodeSchedulable  kubelet  this node is accepting pods")),
        (("the node was cordoned 7m ago and a drain is evicting its pods\n"
          "12 pods have been evicted from it so far\n"
          "nothing new is being scheduled onto it"),
         ("the node is accepting pods and no drain is running\n"
          "0 pods have been evicted from it in the last hour\n"
          "new pods are scheduled onto it normally")),
        (("Normal  NodeNotSchedulable  kubelet  node cordoned: drain started by the "
          "maintenance controller"),
         ("Normal  NodeSchedulable  kubelet  node accepting pods: schedulable again per the "
          "maintenance controller")),
        (("drain status: cordoned\n"
          "pods evicted so far: 12 of 18\n"
          "time since cordon: 7m"),
         ("drain status: accepting pods\n"
          "pods evicted so far: 0 of 0\n"
          "time since cordon: n/a")),
    ),
    victims=(
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) "
                     "had volume node affinity conflict",
            local_cause="this StatefulSet's own volume is pinned to a zone none of "
                        "the schedulable nodes are in",
            local_reason="the claim's volume lives in one zone and the nodes with room "
                         "are all in the other",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: 1 node(s) were unschedulable, 2 node(s) had volume node "
                  "affinity conflict"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Deployment",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="pod evicted by drain; replacement started on another node and "
                     "was evicted again",
            local_cause="this Deployment's own pod disruption budget allows zero "
                        "disruptions, so every routine eviction is retried forever",
            local_reason="the budget sets maxUnavailable 0 with a single replica, so "
                         "no eviction can ever succeed cleanly",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: process received SIGTERM and exited "
                  "(3 of 3 sampled restarts)"),
            log_cause="process received SIGTERM and exited",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="wait-for-node: this pod's node affinity target is not "
                     "schedulable",
            local_cause="this Job's own init container waits for a node label that "
                        "the last node pool rollout renamed",
            local_reason="the init step polls for a node label that no node carries "
                         "since the rename",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: init wait for a node label timed out "
                  "(3 of 3 sampled restarts)"),
            log_cause="init wait for a node label timed out",
            pass_confidence="high",
        ),
    ),
)

_T_NODE_CORRUPT_OVERLAY = Propagation(
    key="node-corrupt-overlay",
    blast_radius="node",
    scope_field="node",
    origin="the node's container layer store is corrupt, so containers there cannot "
           "start from cached image layers",
    shared_cause="the container layer store on node {node} is corrupt, so containers "
                 "there cannot start from cached image layers",
    shared_reason="{node} reports CorruptDockerOverlay2 True with unreadable cached "
                  "layers, and every container start on the node that reuses a cached "
                  "layer has failed since 11m ago",
    distractor_cause="the registry served a broken image layer to every pull in the "
                     "last hour",
    distractor_reason="the same images start normally on the other nodes, which pulled "
                      "them from the same registry in the same hour",
    rationale="the layer store on {node} is corrupt, so any container that starts "
              "from a cached layer there fails; this workload's image is cached on "
              "that node and its own build is sound",
    remedy="Clear the corrupt layer store on {node} (wipe the overlay2 directory and "
           "restart the runtime, or replace the node); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe node {node}",
        ("Layer store on this node: corrupt\n"
         "Conditions:\n"
         "  CorruptDockerOverlay2   True    CorruptDockerOverlay2     overlay2 layer "
         "store is corrupt: cached layers unreadable\n"
         "  Ready                   True    KubeletReady              kubelet is "
         "posting ready status\n"
         "Taints:  <none>"),
    ),
    healthy_origin_content=(
        "Layer store on this node: intact\n"
        "Conditions:\n"
        "  CorruptDockerOverlay2   False   NoCorruptDockerOverlay2   overlay2 layer "
        "store is intact\n"
        "  Ready                   True    KubeletReady              kubelet is "
        "posting ready status\n"
        "Taints:  <none>"
    ),
    origin_state=("corrupt", "intact"),
    origin_variants=(
        (("Layer store on this node: corrupt\n"
          "Conditions:\n"
          "  CorruptDockerOverlay2   True    CorruptDockerOverlay2     overlay2 layer "
          "store is corrupt: cached layers unreadable\n"
          "  Ready                   True    KubeletReady              kubelet is "
          "posting ready status\n"
          "Taints:  <none>"),
         ("Layer store on this node: intact\n"
          "Conditions:\n"
          "  CorruptDockerOverlay2   False   NoCorruptDockerOverlay2   overlay2 layer "
          "store is intact\n"
          "  Ready                   True    KubeletReady              kubelet is "
          "posting ready status\n"
          "Taints:  <none>")),
        (("the node problem detector reports this node's overlay2 store corrupt\n"
          "cached image layers on the node are unreadable\n"
          "container starts that reuse a cached layer fail there"),
         ("the node problem detector reports this node's overlay2 store intact\n"
          "cached image layers on the node read normally\n"
          "container starts that reuse a cached layer succeed there")),
        (("Warning  CorruptDockerOverlay2  node-problem-detector  layer store corrupt: "
          "failed to read layer diff, input/output error"),
         ("Normal  OverlayHealthy  node-problem-detector  layer store intact: all "
          "cached layers verified")),
        (("overlay2 store state: corrupt\n"
          "unreadable cached layers: 41 of 212\n"
          "container starts failed on this node in the last 10m: 19"),
         ("overlay2 store state: intact\n"
          "unreadable cached layers: 0 of 212\n"
          "container starts failed on this node in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to create containerd task: failed to mount rootfs: "
                     "input/output error",
            local_cause="this Deployment's own image was pushed with a layer that "
                        "its build never finished writing",
            local_reason="the image's last layer is truncated in the registry and "
                         "fails to unpack anywhere",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "create containerd task: failed to mount rootfs"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="exec: unable to load shared library: input/output error",
            local_cause="this StatefulSet's own image links a library its final "
                        "build stage never copied in",
            local_reason="the entrypoint loads a library that is absent from the "
                         "image's final layer",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: shared library failed to load at start "
                  "(3 of 3 sampled restarts)"),
            log_cause="shared library failed to load at start",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="init: read /etc/app/schema.sql: input/output error",
            local_cause="this Job's own init container reads a seed file that its "
                        "image ships as an empty placeholder",
            local_reason="the seed file in the init image is zero bytes and the init "
                         "step fails to parse it",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: init read of a bundled file failed "
                  "(3 of 3 sampled restarts)"),
            log_cause="init read of a bundled file failed",
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 4: Append the six names to the pool tuple**

Change the last line of `_TRAINING_SCENARIOS` from
`_T_NETPOL_EGRESS_ALLOWLIST, _T_NODE_MEMORY_PRESSURE)` to:

```python
                       _T_NETPOL_EGRESS_ALLOWLIST, _T_NODE_MEMORY_PRESSURE,
                       _T_NODE_NETWORK_UNAVAILABLE, _T_NODE_KERNEL_DEADLOCK,
                       _T_NODE_READONLY_FILESYSTEM,
                       _T_NODE_FREQUENT_KUBELET_RESTART, _T_NODE_CORDONED_DRAINING,
                       _T_NODE_CORRUPT_OVERLAY)
```

- [ ] **Step 5: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py tests/test_shared_origin_training_pair.py -v`
Expected: all PASS; `test_the_trainable_pool_holds_the_planned_count` now sees 30. The pool-wide tests that matter here: `test_no_two_trainable_scenarios_share_a_local_cause`, `test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim`, `test_every_trainable_scenario_names_its_state_in_words`, `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`, and `test_every_trainable_scenario_is_taught_equally` (which now deals at `BIG = 275 * 30`). If a local_cause collides, reword the new one; never touch an existing record.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add six node-condition scenarios in the describe-node layout"
```

---

### Task 6: Group B — four cluster-scoped operator outages in the exam's Deployment layout

**Files:**
- Modify: `tests/test_shared_origin_training.py` — `EXPECTED_POOL = 30` → `34`, and move `test_the_emitter_offers_every_origin_read_under_both_answers` (line 481 before the shifts) to `big_rows`, with a small-build companion
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — four new records after `_T_NODE_CORRUPT_OVERLAY`, four names appended to `_TRAINING_SCENARIOS`

**Interfaces:**
- Consumes: `Propagation`, `Victim`; `EXPECTED_POOL` from Task 5.
- Produces: keys `external-secrets-operator-down`, `network-operator-down`, `cert-manager-down`, `metrics-server-down`.

Why these four: the exam's coredns-down read is `describe kube-system/coredns (Deployment)` with a `Replicas:` line, a `Pods:` table and a `Last log:` line. Only pod-identity-webhook-down shares that read kind today, and only after Task 4 does it carry the layout. These four are cluster operators whose outage reaches unrelated workloads through a different mechanism each: a missing Secret, a broken overlay, a lapsed certificate, a frozen autoscaler.

- [ ] **Step 1: Bump the pin and watch it fail**

Set `EXPECTED_POOL = 34`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k planned_count -v`
Expected: FAIL, `30 == 34`.

This task's pool size also breaks the emitter's rotation test, for a reason that is not a defect. Do the rewrite now, before the records, so Step 4 runs green.

The generator gives one `multi` row in three a healthy origin read, dealt round-robin over the pool (`generate.py` line 148). At `SIZE = 800` that is 30 negatives, which cover thirty scenarios and not thirty-four. The test's docstring already says the contract holds "as long as there is at least one per scenario"; at this size that stops being true, so the test moves to `big_rows`, where the negatives lap the pool many times over, and a companion keeps the small-build half of the claim. In `tests/test_shared_origin_training.py`, replace `test_the_emitter_offers_every_origin_read_under_both_answers` with:

```python
def test_the_emitter_offers_every_origin_read_under_both_answers(big_rows):
    """The emitter's half, checked before the cull, where it is the emitter's.

    Every trainable origin read must be offered under a shared answer AND
    under an independent one. The negatives rotate over the pool one `multi`
    row in three, so the rotation completes only when the build holds at
    least three `multi` rows per scenario. `SIZE` stopped holding that at
    thirty-one scenarios; `BIG` holds it many times over. Asserting it on
    the kept pile instead would be asserting the cull's behaviour under the
    emitter's name.
    """
    shared = _origin_labels(big_rows, "shared_origin")
    negatives = _origin_labels(big_rows, "multi")
    assert shared, "no shared_origin row carries an origin read"
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert shared == negatives


def test_the_small_build_offers_no_negative_the_shared_half_lacks(rows):
    """The small build's share of the same contract.

    Every negative label is one the shared half also offers, so no label
    appears under the independent answer alone. Coverage the other way
    needs more rows than `SIZE` holds and is checked at `BIG` above.
    """
    shared = _origin_labels(rows, "shared_origin")
    negatives = _origin_labels(rows, "multi")
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert negatives <= shared
```

The comment block above the test ends with "the second if the cull ever takes half a pair or the decoy stops being emitted." Add one line after it:

```python
# 2026-09-08: the emitter's half runs at BIG now; its docstring says why.
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k "offers_every_origin_read or no_negative_the_shared_half_lacks" -v`
Expected: both PASS at thirty scenarios. They pass again at Step 4 with thirty-four.

- [ ] **Step 2: Write the four records**

Insert them directly after `_T_NODE_CORRUPT_OVERLAY`. The cluster scope declares `scope_field=None` and no `{node}` or `{ns}` in `shared_cause`, as `_T_POD_IDENTITY_WEBHOOK` does.

```python
_T_EXTERNAL_SECRETS_DOWN = Propagation(
    key="external-secrets-operator-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the external-secrets operator is down, so the Secrets it syncs are no "
           "longer created and pods that mount them cannot start",
    shared_cause="the external-secrets operator is down, so the Secrets it syncs are "
                 "no longer created and pods that mount them cannot start",
    shared_reason="kube-system/external-secrets shows 0 of 1 replicas available with "
                  "its pod in CrashLoopBackOff after 7 restarts, its last log says "
                  "the secret store is unreachable, and every ExternalSecret it owns "
                  "has been SecretSyncedError since",
    distractor_cause="the workloads' own Secret names were changed in the last chart "
                     "release",
    distractor_reason="the Secret names in the pod specs match the ExternalSecret "
                      "targets exactly and neither has changed in weeks",
    rationale="the Secret this workload mounts is created by the external-secrets "
              "operator, and the operator has been down since its store became "
              "unreachable; the workload's own spec is unchanged",
    remedy="Restore the external-secrets operator (fix its store credentials or "
           "endpoint) and let it sync; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/external-secrets (Deployment)",
        ("Secret store from the operator's view: unreachable\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      external-secrets-5d8c7b9f6-t4k2p   0/1  CrashLoopBackOff  "
         "7 restarts\n"
         "Last log:  secret store unreachable: giving up after 5 attempts"),
    ),
    healthy_origin_content=(
        "Secret store from the operator's view: reconciled\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      external-secrets-5d8c7b9f6-t4k2p   1/1  Running  0 restarts\n"
        "Last log:  reconciled 42 ExternalSecrets, 0 errors"
    ),
    origin_state=("unreachable", "reconciled"),
    origin_variants=(
        (("Secret store from the operator's view: unreachable\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      external-secrets-5d8c7b9f6-t4k2p   0/1  CrashLoopBackOff  "
          "7 restarts\n"
          "Last log:  secret store unreachable: giving up after 5 attempts"),
         ("Secret store from the operator's view: reconciled\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      external-secrets-5d8c7b9f6-t4k2p   1/1  Running  0 restarts\n"
          "Last log:  reconciled 42 ExternalSecrets, 0 errors")),
        (("the external-secrets operator reports its store unreachable\n"
          "the operator pod has crashed 7 times in 12m\n"
          "42 ExternalSecrets are in SecretSyncedError"),
         ("the external-secrets operator reports every ExternalSecret reconciled\n"
          "the operator pod has been Running for 9d\n"
          "0 ExternalSecrets are in error")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "external-secrets (store unreachable)"),
         ("Normal  Started  kubelet  Started container external-secrets (store "
          "reconciled)")),
        (("operator status: unreachable store\n"
          "ExternalSecrets in error: 42 of 42\n"
          "last successful sync: 14m ago"),
         ("operator status: reconciled\n"
          "ExternalSecrets in error: 0 of 42\n"
          "last successful sync: 20s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="CreateContainerConfigError",
            issue="CreateContainerConfigError",
            reason="container {container} could not build its environment",
            evidence="secret \"{name}-credentials\" not found",
            local_cause="this Deployment's own pod spec references a Secret whose "
                        "name was misspelled in its last rollout",
            local_reason="the envFrom entry names a Secret one letter off from the "
                         "one that exists in the namespace",
            read=("get_events {ns}/{name}",
                  "Warning  Failed  kubelet  Error: secret \"{name}-credentials\" "
                  "not found"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CreateContainerConfigError",
            issue="Init:CreateContainerConfigError",
            reason="init container {init_container} could not build its environment",
            evidence="couldn't find key DB_PASSWORD in Secret {ns}/{name}-db",
            local_cause="this Job's own init container asks for a Secret key that its "
                        "chart renamed in the last release",
            local_reason="the init step reads DB_PASSWORD and the chart now writes "
                         "DATABASE_PASSWORD",
            read=("describe {ns}/{pod} (Pod)",
                  "Init Containers:\n  {init_container}: waiting, "
                  "CreateContainerConfigError\nEvents: Warning  Failed  kubelet  "
                  "Error: couldn't find key DB_PASSWORD in Secret"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="MountVolume.SetUp failed for volume \"tls\": secret "
                     "\"{name}-tls\" not found",
            local_cause="this StatefulSet's own TLS Secret was deleted by a cleanup "
                        "job that matched its label by mistake",
            local_reason="the cleanup job's selector matched the StatefulSet's Secret "
                         "label and removed it",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  FailedMount  kubelet  "
                  "MountVolume.SetUp failed for volume \"tls\": secret not found"),
            pass_confidence="high",
        ),
    ),
)

_T_NETWORK_OPERATOR_DOWN = Propagation(
    key="network-operator-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the network operator keeps being OOM-killed, so the pod overlay network "
           "is no longer reconciled",
    shared_cause="the network operator keeps being OOM-killed, so the pod overlay "
                 "network is no longer reconciled and pods on different nodes cannot "
                 "reach each other",
    shared_reason="kube-system/network-operator shows 0 of 1 replicas available with "
                  "its pod OOMKilled 5 times at its 512Mi limit, its last log says "
                  "the overlay reconcile halted, and cross-node pod traffic has been "
                  "failing since",
    distractor_cause="the workloads' own Services lost their endpoints in a rollout",
    distractor_reason="every Service involved lists its ready endpoints and the "
                      "endpoints answer from the same node; only cross-node calls "
                      "fail",
    rationale="cross-node pod traffic depends on the overlay the network operator "
              "reconciles, and the operator has been OOM-killed out of running; "
              "this workload's peers are on other nodes",
    remedy="Raise the network operator's memory limit (or fix the leak) so it stays "
           "Running and reconciles the overlay; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "describe kube-system/network-operator (Deployment)",
        ("Overlay reconcile from the operator's view: halted\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      network-operator-7b6d9c8f5-q2m8x   0/1  OOMKilled  5 restarts\n"
         "Last log:  overlay reconcile halted: killed at 512Mi"),
    ),
    healthy_origin_content=(
        "Overlay reconcile from the operator's view: idle\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      network-operator-7b6d9c8f5-q2m8x   1/1  Running  0 restarts\n"
        "Last log:  overlay reconcile idle: 3 nodes in sync"
    ),
    origin_state=("halted", "idle"),
    origin_variants=(
        (("Overlay reconcile from the operator's view: halted\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      network-operator-7b6d9c8f5-q2m8x   0/1  OOMKilled  5 restarts\n"
          "Last log:  overlay reconcile halted: killed at 512Mi"),
         ("Overlay reconcile from the operator's view: idle\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      network-operator-7b6d9c8f5-q2m8x   1/1  Running  0 restarts\n"
          "Last log:  overlay reconcile idle: 3 nodes in sync")),
        (("the network operator reports its overlay reconcile halted\n"
          "the operator pod was OOM-killed 5 times at its 512Mi limit\n"
          "cross-node pod traffic has failed for 15m"),
         ("the network operator reports its overlay reconcile idle\n"
          "the operator pod has been Running for 6d within its limit\n"
          "cross-node pod traffic flows normally")),
        (("Warning  OOMKilling  kubelet  Memory cgroup out of memory: killed process "
          "network-operator (overlay reconcile halted)"),
         ("Normal  Started  kubelet  Started container network-operator (overlay "
          "reconcile idle, 3 nodes in sync)")),
        (("overlay reconcile loop: halted\n"
          "nodes out of sync: 3 of 3\n"
          "operator OOM kills in the last hour: 5"),
         ("overlay reconcile loop: idle\n"
          "nodes out of sync: 0 of 3\n"
          "operator OOM kills in the last hour: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dependency check to a peer on another "
                     "node timed out",
            local_cause="this Deployment's own readiness check calls a peer address "
                        "that was retired in the last release",
            local_reason="the check dials a peer hostname that no Service publishes "
                         "any more",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: dependency "
                  "check timed out"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="cluster join failed: peer on another node unreachable after 30s",
            local_cause="this StatefulSet's own peer list still names a member that "
                        "was scaled away last week",
            local_reason="the join step waits on a member ordinal that no longer "
                         "exists",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: peer join timed out (3 of 3 sampled restarts)"),
            log_cause="peer join timed out",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="wait-for-db: dial tcp: i/o timeout reaching a pod on another "
                     "node",
            local_cause="this Job's own init container dials the database by a pod "
                        "IP it cached from a previous run",
            local_reason="the init step reads a stale address file instead of the "
                         "Service name",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: init wait for the database timed out "
                  "(3 of 3 sampled restarts)"),
            log_cause="init wait for the database timed out",
            pass_confidence="high",
        ),
    ),
)

_T_CERT_MANAGER_DOWN = Propagation(
    key="cert-manager-down",
    blast_radius="cluster",
    scope_field=None,
    origin="cert-manager is down, so certificates near expiry are not renewed and "
           "the workloads serving them fail their TLS checks once they lapse",
    shared_cause="cert-manager is down, so certificates near expiry are not renewed "
                 "and the workloads serving them fail their TLS checks once they "
                 "lapse",
    shared_reason="cert-manager/cert-manager shows 0 of 1 replicas available with its "
                  "pod in CrashLoopBackOff after 11 restarts, its last log says it "
                  "lost its leader lease, and 9 Certificates have passed their "
                  "renewal time without a new Secret",
    distractor_cause="the workloads' own TLS Secrets were overwritten by a manual "
                     "kubectl apply",
    distractor_reason="the TLS Secrets carry the same serial they had a month ago and "
                      "no manual write is in the audit log",
    rationale="the certificate this workload serves is renewed by cert-manager, and "
              "cert-manager has been down past the renewal window; the workload's "
              "own config is unchanged",
    remedy="Restore cert-manager (let it reacquire its leader lease) and let it renew "
           "the lapsed Certificates; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe cert-manager/cert-manager (Deployment)",
        ("Leader lease from the controller's view: lost\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      cert-manager-6f9b8d7c5-w7r3n   0/1  CrashLoopBackOff  "
         "11 restarts\n"
         "Last log:  lost leader lease, exiting"),
    ),
    healthy_origin_content=(
        "Leader lease from the controller's view: holding\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      cert-manager-6f9b8d7c5-w7r3n   1/1  Running  0 restarts\n"
        "Last log:  holding leader lease, 0 certificates pending"
    ),
    origin_state=("lost", "holding"),
    origin_variants=(
        (("Leader lease from the controller's view: lost\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      cert-manager-6f9b8d7c5-w7r3n   0/1  CrashLoopBackOff  "
          "11 restarts\n"
          "Last log:  lost leader lease, exiting"),
         ("Leader lease from the controller's view: holding\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      cert-manager-6f9b8d7c5-w7r3n   1/1  Running  0 restarts\n"
          "Last log:  holding leader lease, 0 certificates pending")),
        (("cert-manager reports its leader lease lost\n"
          "the controller pod has crashed 11 times in 40m\n"
          "9 Certificates are past their renewal time"),
         ("cert-manager reports it is holding its leader lease\n"
          "the controller pod has been Running for 12d\n"
          "0 Certificates are past their renewal time")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "cert-manager (leader lease lost)"),
         ("Normal  Started  kubelet  Started container cert-manager (holding leader "
          "lease)")),
        (("controller lease: lost\n"
          "Certificates past renewal: 9 of 31\n"
          "last renewal issued: 3h ago"),
         ("controller lease: holding\n"
          "Certificates past renewal: 0 of 31\n"
          "last renewal issued: 6m ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: tls: certificate has expired",
            local_cause="this Deployment's own probe pins a CA bundle that was "
                        "rotated out of the trust store last quarter",
            local_reason="the probe's CA file is a copy from before the routine "
                         "rotation and no longer validates anything",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: tls: "
                  "certificate has expired"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="tls: failed to load server certificate: certificate has expired",
            local_cause="this StatefulSet's own server certificate is self-signed "
                        "with a one-year validity nobody tracked",
            local_reason="the certificate was generated by hand a year ago and never "
                         "enrolled for renewal",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: server certificate expired "
                  "(3 of 3 sampled restarts)"),
            log_cause="server certificate expired",
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="metrics push failed: x509: certificate has expired or is not "
                     "yet valid",
            local_cause="this agent's own client certificate is issued by a private "
                        "CA outside the cluster with a lapsed intermediate",
            local_reason="the agent's certificate chains to an intermediate that "
                         "expired last night",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: client certificate rejected as expired "
                  "(3 of 3 sampled restarts)"),
            log_cause="client certificate rejected as expired",
            pass_confidence="high",
        ),
    ),
)

_T_METRICS_SERVER_DOWN = Propagation(
    key="metrics-server-down",
    blast_radius="cluster",
    scope_field=None,
    origin="metrics-server is down, so every autoscaler is frozen at its last size",
    shared_cause="metrics-server is down, so every autoscaler is frozen at its last "
                 "size and overloaded pods are not scaled out",
    shared_reason="kube-system/metrics-server shows 0 of 1 replicas available with "
                  "its pod in CrashLoopBackOff after 8 restarts, its last log says "
                  "node metric scrapes time out, and every HorizontalPodAutoscaler "
                  "reports FailedGetResourceMetric",
    distractor_cause="the workloads' own autoscalers were deleted in the last chart "
                     "release",
    distractor_reason="every HorizontalPodAutoscaler is present and its target "
                      "reference is unchanged; each one reports it cannot read "
                      "metrics",
    rationale="this workload is overloaded because its autoscaler cannot read "
              "metrics, and it cannot read them because metrics-server is down; "
              "the same is true of every autoscaled workload",
    remedy="Restore kube-system/metrics-server (fix its kubelet scrape timeout) and "
           "let the autoscalers resume; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "describe kube-system/metrics-server (Deployment)",
        ("Node metrics from the server's view: unable to fetch\n"
         "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
         "Pods:      metrics-server-8c7d6b9f4-h5n2k   0/1  CrashLoopBackOff  "
         "8 restarts\n"
         "Last log:  unable to fetch node metrics: scrape timeout"),
    ),
    healthy_origin_content=(
        "Node metrics from the server's view: scraped\n"
        "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
        "Pods:      metrics-server-8c7d6b9f4-h5n2k   1/1  Running  0 restarts\n"
        "Last log:  scraped 3 nodes, 41 pods"
    ),
    origin_state=("unable", "scraped"),
    origin_variants=(
        (("Node metrics from the server's view: unable to fetch\n"
          "Replicas:  1 desired | 1 updated | 1 total | 0 available | 1 unavailable\n"
          "Pods:      metrics-server-8c7d6b9f4-h5n2k   0/1  CrashLoopBackOff  "
          "8 restarts\n"
          "Last log:  unable to fetch node metrics: scrape timeout"),
         ("Node metrics from the server's view: scraped\n"
          "Replicas:  1 desired | 1 updated | 1 total | 1 available | 0 unavailable\n"
          "Pods:      metrics-server-8c7d6b9f4-h5n2k   1/1  Running  0 restarts\n"
          "Last log:  scraped 3 nodes, 41 pods")),
        (("metrics-server reports it is unable to fetch node metrics\n"
          "the server pod has crashed 8 times in 25m\n"
          "every HorizontalPodAutoscaler reports FailedGetResourceMetric"),
         ("metrics-server reports it scraped every node\n"
          "the server pod has been Running for 20d\n"
          "every HorizontalPodAutoscaler reads its metrics normally")),
        (("Warning  FailedGetResourceMetric  horizontal-pod-autoscaler  unable to "
          "fetch metrics from resource metrics API"),
         ("Normal  SuccessfulRescale  horizontal-pod-autoscaler  metrics scraped, "
          "New size: 4; reason: cpu resource utilization above target")),
        (("metrics API: unable to serve\n"
          "autoscalers frozen: 17 of 17\n"
          "last successful scrape: 25m ago"),
         ("metrics API: scraped and serving\n"
          "autoscalers frozen: 0 of 17\n"
          "last successful scrape: 15s ago")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503 "
                     "(overloaded, queue depth 4000)",
            local_cause="this Deployment's own request queue is unbounded and a "
                        "single slow client can fill it",
            local_reason="the queue has no cap and one client is holding 4000 "
                         "requests open",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="OOMKilled",
            issue="OOMKilled",
            reason="container {container} was killed by the kernel out-of-memory "
                   "handler",
            evidence="container exceeded its memory limit under load that would have "
                     "been spread across more replicas",
            local_cause="this StatefulSet's own in-memory index doubles on every "
                        "compaction and never releases the old copy",
            local_reason="the index keeps both copies after compaction and grows "
                         "until the kernel kills it",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: memory limit exceeded under load "
                  "(3 of 3 sampled restarts)"),
            log_cause="memory limit exceeded under load",
            pass_confidence="high",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="RestartLoop",
            issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="scrape target overloaded: collector restarted after 30s of "
                     "backpressure",
            local_cause="this agent's own scrape interval was set to one second in "
                        "its last config push",
            local_reason="the agent scrapes every target every second and restarts "
                         "when its buffer fills",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: collector restarted under backpressure "
                  "(3 of 3 sampled restarts)"),
            log_cause="collector restarted under backpressure",
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 3: Append the four names to the pool tuple**

After `_T_NODE_CORRUPT_OVERLAY` in `_TRAINING_SCENARIOS`, before the closing `)`:

```python
                       _T_NODE_CORRUPT_OVERLAY, _T_EXTERNAL_SECRETS_DOWN,
                       _T_NETWORK_OPERATOR_DOWN, _T_CERT_MANAGER_DOWN,
                       _T_METRICS_SERVER_DOWN)
```

- [ ] **Step 4: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py tests/test_shared_origin_training_pair.py -v`
Expected: all PASS with the pool at 34. metrics-server-down's tokens are 'unable' / 'scraped': check that no healthy half says "unable" and no broken half says "scraped" (the broken halves say "scrape timeout" and "unable to fetch", never "scraped").

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add four cluster-operator scenarios in the describe-deployment layout"
```

---

### Task 7: Group C — four cluster-wide event scenarios in the exam's events layout

**Files:**
- Modify: `tests/test_shared_origin_training.py` — `EXPECTED_POOL = 34` → `38`
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — four new records after `_T_METRICS_SERVER_DOWN`, four names appended to `_TRAINING_SCENARIOS`

**Interfaces:**
- Consumes: `Propagation`, `Victim`; `EXPECTED_POOL` from Task 6.
- Produces: keys `shared-nfs-server-down`, `cluster-maintenance-taint`, `shared-gateway-refusing`, `runtime-class-removed`.

Why these four: the exam's registry-unreachable read is `get_events (cluster-wide, reason=Failed)`. Its broken half counts pods and namespaces and ends with `distinct <things> in the failing set: 1`. Its healthy half says the failing pods have nothing in common and ends with `one per failing pod`. No trainable scenario uses this read kind today. These four teach the same shape with four different event reasons.

Two token traps live in this group:
- cluster-maintenance-taint's tokens are `maintenance` / `none`. The word `none` must not appear anywhere in a broken half, so every broken half ends `distinct taints in the failing set: 1`, never `none`. The literal `{{maintenance: true}}` renders as `{maintenance: true}` and sits on line 3, never on line 1 (R8).
- runtime-class-removed's broken token is `no runtime`. The healthy halves say `name no handler in common`, never "no runtime handler".

- [ ] **Step 1: Bump the pin and watch it fail**

Set `EXPECTED_POOL = 38`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k planned_count -v`
Expected: FAIL, `34 == 38`.

- [ ] **Step 2: Write the four records**

Insert them directly after `_T_METRICS_SERVER_DOWN`.

```python
_T_SHARED_NFS_SERVER_DOWN = Propagation(
    key="shared-nfs-server-down",
    blast_radius="cluster",
    scope_field=None,
    origin="the shared NFS server is down, so every pod that mounts a volume from "
           "it is stuck at mount",
    shared_cause="the shared NFS server is down, so every pod that mounts a volume "
                 "from it is stuck at mount",
    shared_reason="9 pods across 4 namespaces report the same FailedMount error, "
                  "mount.nfs timed out, and every one of them names the same NFS "
                  "server; that server has answered no mount in 20m",
    distractor_cause="the workloads' own volume specs were rewritten to the wrong "
                     "export path in the last chart release",
    distractor_reason="the export paths in the failing pods' specs match what the "
                      "server published last week, and the error is a timeout, not "
                      "a missing export",
    rationale="this workload's volume is served by the shared NFS server, and that "
              "server has stopped answering mounts for every pod that uses it; the "
              "workload's own volume spec is unchanged",
    remedy="Bring the shared NFS server back (or fail over to its replica) and let "
           "the kubelets retry their mounts; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedMount)",
        ("NFS mount failures across the cluster: timed out against one server\n"
         "9 pods across 4 namespaces report the same error:\n"
         "  MountVolume.SetUp failed: mount.nfs: Connection timed out\n"
         "distinct NFS servers in the failing set: 1"),
    ),
    healthy_origin_content=(
        "NFS mount failures across the cluster: one per failing pod, no server in "
        "common\n"
        "pods reporting a mount error name no NFS server in common, and\n"
        "no two of them fail the same way: wrong fs type, permission denied,\n"
        "no such export\n"
        "distinct NFS servers in the failing set: one per failing pod"
    ),
    origin_state=("timed out", "one per failing pod"),
    origin_variants=(
        (("NFS mount failures across the cluster: timed out against one server\n"
          "9 pods across 4 namespaces report the same error:\n"
          "  MountVolume.SetUp failed: mount.nfs: Connection timed out\n"
          "distinct NFS servers in the failing set: 1"),
         ("NFS mount failures across the cluster: one per failing pod, no server in "
          "common\n"
          "pods reporting a mount error name no NFS server in common, and\n"
          "no two of them fail the same way: wrong fs type, permission denied,\n"
          "no such export\n"
          "distinct NFS servers in the failing set: one per failing pod")),
        (("every FailedMount event in the last 20m names the same NFS server\n"
          "each of the 9 mounts timed out after 30s\n"
          "the server has answered no mount request since the failures began"),
         ("the FailedMount events in the last 20m name a different server each: "
          "one per failing pod\n"
          "each mount fails for its own reason: a wrong fs type, a denied "
          "permission, a missing export\n"
          "every named server answers mount requests")),
        (("Warning  FailedMount  kubelet  MountVolume.SetUp failed: mount.nfs: "
          "Connection timed out (same server for 9 of 9 failing pods)"),
         ("Warning  FailedMount  kubelet  MountVolume.SetUp failed: mount.nfs: no "
          "such export (servers named: one per failing pod)")),
        (("NFS server in common across failing mounts: 1\n"
          "mount outcome for every pod that uses it: timed out\n"
          "failing pods: 9 in 4 namespaces"),
         ("NFS server in common across failing mounts: 0, one per failing pod\n"
          "mount outcome: a different error for each pod\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.SetUp failed for volume \"{pvc}\": mount.nfs: "
                     "mount failed",
            local_cause="this Deployment's own volume names an NFS export path that "
                        "was renamed on the server last week",
            local_reason="the pod spec still mounts the old export path and the "
                         "server now publishes it under a new name",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.SetUp failed for volume "
                  "\"{pvc}\": mount.nfs: mount failed"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the NFS CSI "
                     "node plugin reported the attach as failed",
            local_cause="this StatefulSet's own volume attachment is pinned to a "
                        "node that was rebuilt without the NFS client package",
            local_reason="the attachment names a node whose image lost the NFS "
                         "client in the last rebuild",
            read=("get_events {ns}/{name}",
                  "Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="DaemonSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: mount source for the agent's "
                     "shared volume is not ready",
            local_cause="this agent's own hostPath mount points at a directory the "
                        "node image no longer ships",
            local_reason="the DaemonSet mounts a host directory that the last node "
                         "image dropped",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container \"{container}\": mount source not ready"),
            pass_confidence="high",
        ),
    ),
)

_T_CLUSTER_MAINTENANCE_TAINT = Propagation(
    key="cluster-maintenance-taint",
    blast_radius="cluster",
    scope_field=None,
    origin="every node carries a maintenance taint no workload tolerates, so no new "
           "pod can be scheduled anywhere",
    shared_cause="every node carries a maintenance taint no workload tolerates, so "
                 "no new pod can be scheduled anywhere",
    shared_reason="12 pods across 5 namespaces report the same FailedScheduling "
                  "error, 0/3 nodes available because all 3 carry an untolerated "
                  "maintenance taint, and no pending pod has tolerated it",
    distractor_cause="the workloads' own tolerations were dropped in the last chart "
                     "release",
    distractor_reason="the pending pods never carried a toleration for this taint, "
                      "because the taint did not exist before the maintenance "
                      "window opened",
    rationale="this workload cannot be scheduled because every node carries the "
              "maintenance taint, and no pod in the cluster can be scheduled for "
              "the same reason; the workload's own spec is unchanged",
    remedy="Remove the maintenance taint from the nodes once the window closes (or "
           "untaint one node now); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedScheduling)",
        ("Untolerated taint across the cluster: maintenance, on every node\n"
         "12 pods across 5 namespaces report the same error:\n"
         "  0/3 nodes are available: 3 node(s) had untolerated taint "
         "{{maintenance: true}}\n"
         "distinct taints in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Untolerated taint across the cluster: none\n"
        "pods reporting a scheduling failure name no taint in common, and\n"
        "no two of them fail the same way: insufficient cpu, node affinity "
        "mismatch,\n"
        "unbound claim\n"
        "distinct taints in the failing set: none"
    ),
    origin_state=("maintenance", "none"),
    origin_variants=(
        (("Untolerated taint across the cluster: maintenance, on every node\n"
          "12 pods across 5 namespaces report the same error:\n"
          "  0/3 nodes are available: 3 node(s) had untolerated taint "
          "{{maintenance: true}}\n"
          "distinct taints in the failing set: 1"),
         ("Untolerated taint across the cluster: none\n"
          "pods reporting a scheduling failure name no taint in common, and\n"
          "no two of them fail the same way: insufficient cpu, node affinity "
          "mismatch,\n"
          "unbound claim\n"
          "distinct taints in the failing set: none")),
        (("every FailedScheduling event in the last 20m names the maintenance "
          "taint\n"
          "all 3 nodes carry it and no pending pod tolerates it\n"
          "pods pending on it: 12 in 5 namespaces"),
         ("the FailedScheduling events in the last 20m name a taint in common: "
          "none\n"
          "each pending pod waits for its own reason: cpu, affinity, a claim\n"
          "pods pending: 3 in 3 namespaces")),
        (("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "3 node(s) had an untolerated maintenance taint (12 of 12 pending pods)"),
         ("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "1 Insufficient cpu, 2 node(s) didn't match affinity (shared taint: "
          "none)")),
        (("taint shared by every pending pod: maintenance\n"
          "nodes carrying it: 3 of 3\n"
          "pending pods that tolerate it: 0 of 12"),
         ("taint shared by every pending pod: none\n"
          "nodes carrying an untolerated taint: 0 of 3\n"
          "pending pods: 3, each for its own reason")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this Deployment's own required node affinity names an "
                        "instance type the pool no longer has",
            local_reason="the affinity rule asks for a node label no node in the "
                         "pool carries since the last resize",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: no node fits this pod"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this StatefulSet's own pod anti-affinity forbids two "
                        "replicas per node and it now asks for more replicas than "
                        "there are nodes",
            local_reason="the anti-affinity rule leaves no node for the fourth "
                         "replica of a three-node cluster",
            read=("describe {ns}/{pod} (Pod)",
                  "Status: Pending\nEvents: Warning  FailedScheduling  "
                  "default-scheduler  0/3 nodes are available: no node fits this "
                  "pod"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="0/3 nodes are available for this pod",
            local_cause="this Job's own resource request asks for a GPU that no node "
                        "in the cluster has",
            local_reason="the pod requests one GPU and the cluster has no GPU node",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: no node fits this pod"),
            pass_confidence="high",
        ),
    ),
)

_T_SHARED_GATEWAY_REFUSING = Propagation(
    key="shared-gateway-refusing",
    blast_radius="cluster",
    scope_field=None,
    origin="the shared API gateway refuses connections, so every pod whose readiness "
           "check calls through it fails its probe",
    shared_cause="the shared API gateway refuses connections, so every pod whose "
                 "readiness check calls through it fails its probe",
    shared_reason="14 pods across 6 namespaces report the same Unhealthy error, "
                  "readiness probe failed because the API gateway refused the "
                  "connection, and every one of them names the same gateway",
    distractor_cause="the workloads' own readiness probes were pointed at the wrong "
                     "path in the last rollout",
    distractor_reason="the probe paths are unchanged and answer when called "
                      "directly; only the hop through the gateway fails",
    rationale="this workload's readiness check calls through the shared API "
              "gateway, and the gateway is refusing every connection; the "
              "workload's own probe is unchanged",
    remedy="Restore the shared API gateway (restart it or roll back its last "
           "config) and let the probes pass; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=Unhealthy)",
        ("Gateway named by failing readiness probes: one, and it refused every "
         "call\n"
         "14 pods across 6 namespaces report the same error:\n"
         "  Readiness probe failed: API gateway: connection refused\n"
         "distinct gateways in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Gateway named by failing readiness probes: one per failing pod\n"
        "pods reporting a readiness failure name no gateway in common, and\n"
        "no two of them fail the same way: HTTP 500, timeout, missing path\n"
        "distinct gateways in the failing set: one per failing pod"
    ),
    origin_state=("refused", "one per failing pod"),
    origin_variants=(
        (("Gateway named by failing readiness probes: one, and it refused every "
          "call\n"
          "14 pods across 6 namespaces report the same error:\n"
          "  Readiness probe failed: API gateway: connection refused\n"
          "distinct gateways in the failing set: 1"),
         ("Gateway named by failing readiness probes: one per failing pod\n"
          "pods reporting a readiness failure name no gateway in common, and\n"
          "no two of them fail the same way: HTTP 500, timeout, missing path\n"
          "distinct gateways in the failing set: one per failing pod")),
        (("every Unhealthy event in the last 20m names the same API gateway\n"
          "the gateway refused all 14 probe calls\n"
          "the gateway's own listener has accepted nothing since"),
         ("the Unhealthy events in the last 20m name a different gateway each: "
          "one per failing pod\n"
          "each probe fails for its own reason: a 500, a timeout, a missing path\n"
          "every named gateway accepts connections")),
        (("Warning  Unhealthy  kubelet  Readiness probe failed: API gateway: "
          "connection refused (same gateway for 14 of 14 failing pods)"),
         ("Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed "
          "with statuscode: 500 (gateways named: one per failing pod)")),
        (("API gateway in common across failing probes: 1\n"
          "outcome of every probe call through it: refused\n"
          "failing pods: 14 in 6 namespaces"),
         ("API gateway in common across failing probes: 0, one per failing pod\n"
          "outcome: a different error for each pod\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: 503",
            local_cause="this Deployment's own readiness path was renamed in its "
                        "last image and the probe still calls the old one",
            local_reason="the probe asks for a path the new image answers with 404 "
                         "and the handler reports that as not ready",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Running",
            issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: dependency check did not pass",
            local_cause="this StatefulSet's own readiness check calls a sidecar that "
                        "its last rollout removed from the pod",
            local_reason="the check dials a sidecar port that nothing in the pod "
                         "listens on any more",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nReady: False\nEvents: Warning  Unhealthy  kubelet  "
                  "Readiness probe failed: dependency check did not pass"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="first outbound call failed on start, exiting",
            local_cause="this Job's own container exits on its first failed outbound call "
                        "because its retry budget is set to zero",
            local_reason="the retry count is 0, so one failed call ends the process",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: first outbound call failed on start "
                  "(3 of 3 sampled restarts)"),
            log_cause="first outbound call failed on start",
            pass_confidence="high",
        ),
    ),
)

_T_RUNTIME_CLASS_REMOVED = Propagation(
    key="runtime-class-removed",
    blast_radius="cluster",
    scope_field=None,
    origin="the sandboxed RuntimeClass handler was removed from the nodes, so every "
           "pod that asks for it fails to create its sandbox",
    shared_cause="the sandboxed RuntimeClass handler was removed from the nodes, so "
                 "every pod that asks for it fails to create its sandbox",
    shared_reason="8 pods across 4 namespaces report the same FailedCreatePodSandBox "
                  "error, no runtime for the sandboxed handler is configured, and "
                  "every one of them asks for that one handler",
    distractor_cause="the workloads' own pod specs gained a runtimeClassName in the "
                     "last chart release",
    distractor_reason="the failing pods have asked for the sandboxed class for "
                      "months and ran fine until the node runtime config changed",
    rationale="this workload asks for the sandboxed RuntimeClass, and the nodes no "
              "longer have a handler for it; every pod that asks for the same "
              "class fails the same way and the workload's own spec is unchanged",
    remedy="Restore the sandboxed handler in the container runtime config on every "
           "node (or roll back the runtime config change); the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_events (cluster-wide, reason=FailedCreatePodSandBox)",
        ("Sandbox handler across the cluster: no runtime for the sandboxed class\n"
         "8 pods across 4 namespaces report the same error:\n"
         "  Failed to create pod sandbox: no runtime for \"sandboxed\" is "
         "configured\n"
         "distinct runtime handlers in the failing set: 1"),
    ),
    healthy_origin_content=(
        "Sandbox handler across the cluster: one per failing pod\n"
        "pods reporting a sandbox failure name no handler in common, and\n"
        "no two of them fail the same way: cgroup limit, seccomp profile "
        "missing,\n"
        "hostPort in use\n"
        "distinct runtime handlers in the failing set: one per failing pod"
    ),
    origin_state=("no runtime", "one per failing pod"),
    origin_variants=(
        (("Sandbox handler across the cluster: no runtime for the sandboxed class\n"
          "8 pods across 4 namespaces report the same error:\n"
          "  Failed to create pod sandbox: no runtime for \"sandboxed\" is "
          "configured\n"
          "distinct runtime handlers in the failing set: 1"),
         ("Sandbox handler across the cluster: one per failing pod\n"
          "pods reporting a sandbox failure name no handler in common, and\n"
          "no two of them fail the same way: cgroup limit, seccomp profile "
          "missing,\n"
          "hostPort in use\n"
          "distinct runtime handlers in the failing set: one per failing pod")),
        (("every FailedCreatePodSandBox event in the last 20m names the sandboxed "
          "handler\n"
          "the nodes report no runtime configured for it since the last runtime "
          "config push\n"
          "pods failing on it: 8 in 4 namespaces"),
         ("the FailedCreatePodSandBox events in the last 20m name a handler in "
          "common: none, one per failing pod\n"
          "each sandbox fails for its own reason: a cgroup limit, a missing "
          "seccomp profile, a busy hostPort\n"
          "every handler the nodes list is configured")),
        (("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
          "no runtime for \"sandboxed\" is configured (8 of 8 failing pods)"),
         ("Warning  FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
          "hostPort 8080 already in use (handlers named: one per failing pod)")),
        (("runtime handler in common across failing sandboxes: 1, sandboxed\n"
          "handler state on the nodes: no runtime configured\n"
          "failing pods: 8 in 4 namespaces"),
         ("runtime handler in common across failing sandboxes: 0, one per failing "
          "pod\n"
          "handler state on the nodes: every listed handler configured\n"
          "failing pods: 3 in 3 namespaces")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this Deployment's own pod spec asks for a seccomp profile "
                        "the node image never shipped",
            local_reason="the securityContext names a localhost seccomp profile "
                         "that no node has on disk",
            read=("get_events {ns}/{name}",
                  "Warning  FailedCreatePodSandBox  kubelet  Failed to create pod "
                  "sandbox: sandbox creation failed"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this StatefulSet's own container requests a hostPort that "
                        "another pod on every node already holds",
            local_reason="the hostPort it asks for is taken on each node by a "
                         "DaemonSet that arrived last week",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nRuntimeClassName: sandboxed\nEvents: Warning  "
                  "FailedCreatePodSandBox  kubelet  Failed to create pod sandbox: "
                  "sandbox creation failed"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="Failed to create pod sandbox for pod {pod}",
            local_cause="this Job's own pod spec sets a cgroup parent that does not "
                        "exist on the nodes",
            local_reason="the pod asks for a cgroup parent path the nodes' cgroup "
                         "tree does not contain",
            read=("get_events {ns}/{name}",
                  "Warning  FailedCreatePodSandBox  kubelet  Failed to create pod "
                  "sandbox: sandbox creation failed"),
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 3: Append the four names to the pool tuple**

After `_T_METRICS_SERVER_DOWN` in `_TRAINING_SCENARIOS`:

```python
                       _T_METRICS_SERVER_DOWN, _T_SHARED_NFS_SERVER_DOWN,
                       _T_CLUSTER_MAINTENANCE_TAINT, _T_SHARED_GATEWAY_REFUSING,
                       _T_RUNTIME_CLASS_REMOVED)
```

- [ ] **Step 4: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py tests/test_shared_origin_training_pair.py -v`
Expected: all PASS with the pool at 38. If `test_every_trainable_scenario_names_its_state_in_words` fails on cluster-maintenance-taint, a broken half contains the letters `none` somewhere (search each broken half for that substring; `node` and `nodes` do not contain it). If it fails on runtime-class-removed, a healthy half says "no runtime" (it must say "no handler").

Run the rendering check for the brace literal:

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
from kubeagent_verdict.dataset import generate
rows = generate.generate(seed=17, size=800)
hits = [r for r in rows if "maintenance: true" in r.user]
assert hits, "no maintenance-taint row rendered at size 800"
bad = [r for r in hits if "{{maintenance" in r.user or "}}" in r.user]
assert not bad, "the brace literal rendered twice"
print("ok", len(hits), "rows carry the taint literal, rendered once")
EOF
```

Expected: `ok N rows carry the taint literal, rendered once` with N ≥ 1. `generate.generate` returns `Example` objects; `.user` is the rendered prompt text (see `to_row` in `src/kubeagent_verdict/dataset/generate.py`).

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add four cluster-wide event scenarios in the exam's events layout"
```

---

### Task 8: Group D — five StorageClass scenarios in the exam's storageclass layout

**Files:**
- Modify: `tests/test_shared_origin_training.py` — `EXPECTED_POOL = 38` → `43`
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — five new records after `_T_RUNTIME_CLASS_REMOVED`, five names appended to `_TRAINING_SCENARIOS`

**Interfaces:**
- Consumes: `Propagation`, `Victim`; `EXPECTED_POOL` from Task 7.
- Produces: keys `csi-controller-oomkilled`, `csi-controller-unschedulable`, `provisioner-credentials-rotated`, `storage-backend-full`, `csi-driver-version-mismatch`.

Why these five: storage-provisioner-down is 0 of 7 on every model to date. Its read is `get_related storageclass standard`, with a `provisioner:` line, a `controller <ns>/<name>: <n>/<n> ready, <state>` line and `PersistentVolumes bound in the last 20m: <n>`. Only storageclass-retired shares the read kind, and only after Task 4 does it carry the layout. These five put five different faults behind the same four-line read: a crashing controller, an unplaceable controller, a healthy controller with a refusing backend, a full backend, and a version split.

One deliberate change from the spec's count line: csi-driver-version-mismatch stalls staging, not binding, and its victims are mount and attach errors. Its count line therefore reads `PersistentVolumes bound in the last 20m: 5, staged on a node: 0` on the broken half (the spec wrote 0). The phrase `bound in the last` stays, so Task 9's per-layout floor still counts it.

Two token traps: csi-controller-oomkilled's healthy token is `Running`, so its broken halves never say "Running" anywhere; provisioner-credentials-rotated's healthy token is `none`, so its broken halves never contain those four letters (its controller line says `1/1 ready, Running` on both halves).

Every Unschedulable victim read in this group says `unbound PersistentVolumeClaim` and never names the controller state.

- [ ] **Step 1: Bump the pin and watch it fail**

Set `EXPECTED_POOL = 43`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k planned_count -v`
Expected: FAIL, `38 == 43`.

- [ ] **Step 2: Write the first three records**

Insert them directly after `_T_RUNTIME_CLASS_REMOVED`.

```python
_T_CSI_CONTROLLER_OOMKILLED = Propagation(
    key="csi-controller-oomkilled",
    blast_radius="cluster",
    scope_field=None,
    origin="the block-ssd CSI controller is OOM-killed on every start, so no claim "
           "on that class gets a volume",
    shared_cause="the block-ssd CSI controller is OOM-killed on every start, so no "
                 "claim on that class gets a volume",
    shared_reason="storage-system/block-ssd-csi-controller shows 0 of 2 ready with "
                  "both pods OOMKilled, its last restart 40s ago with exit 137, and "
                  "0 PersistentVolumes have bound on block-ssd in the last 20m",
    distractor_cause="the workloads' own claims were recreated with the wrong access "
                     "mode in the last chart release",
    distractor_reason="the claims ask for the same access mode they always did and "
                      "the class supports it; the provisioner has simply not "
                      "answered any of them",
    rationale="this workload's claim is on the block-ssd class, and that class's "
              "controller is OOM-killed before it can provision anything; the "
              "workload's own claim is unchanged",
    remedy="Raise the block-ssd CSI controller's memory limit (or fix its leak) so "
           "it stays up and provisions; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass block-ssd",
        ("block-ssd controller state: OOMKilled on every start\n"
         "provisioner: example.com/block-ssd-csi\n"
         "controller storage-system/block-ssd-csi-controller: 0/2 ready, OOMKilled\n"
         "last restart: 40s ago, exit 137\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "block-ssd controller state: Running\n"
        "provisioner: example.com/block-ssd-csi\n"
        "controller storage-system/block-ssd-csi-controller: 2/2 ready, Running\n"
        "last restart: none in 7d\n"
        "PersistentVolumes bound in the last 20m: 5"
    ),
    origin_state=("OOMKilled", "Running"),
    origin_variants=(
        (("block-ssd controller state: OOMKilled on every start\n"
          "provisioner: example.com/block-ssd-csi\n"
          "controller storage-system/block-ssd-csi-controller: 0/2 ready, "
          "OOMKilled\n"
          "last restart: 40s ago, exit 137\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("block-ssd controller state: Running\n"
          "provisioner: example.com/block-ssd-csi\n"
          "controller storage-system/block-ssd-csi-controller: 2/2 ready, Running\n"
          "last restart: none in 7d\n"
          "PersistentVolumes bound in the last 20m: 5")),
        (("the block-ssd CSI controller is OOMKilled at its 256Mi limit on every "
          "start\n"
          "both controller pods have exit 137 in their last termination\n"
          "no block-ssd claim has bound in 20m"),
         ("the block-ssd CSI controller has been Running within its limit for 7d\n"
          "both controller pods report 0 restarts\n"
          "5 block-ssd claims bound in the last 20m")),
        (("Warning  BackOff  kubelet  Back-off restarting failed container "
          "block-ssd-csi-controller (OOMKilled, exit 137)"),
         ("Normal  Started  kubelet  Started container block-ssd-csi-controller "
          "(Running, 2 of 2 ready)")),
        (("class block-ssd provisioner health: OOMKilled\n"
          "controller pods ready: 0 of 2\n"
          "claims waiting on this class: 5, bound in 20m: 0"),
         ("class block-ssd provisioner health: Running\n"
          "controller pods ready: 2 of 2\n"
          "claims waiting on this class: 0, bound in 20m: 5")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim asks for a storage class name "
                        "with a typo, so no provisioner picks it up",
            local_reason="the claim names a class one letter off from any class in "
                         "the cluster",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this StatefulSet's own volumeClaimTemplate asks for 10 TiB, "
                        "more than the class's per-volume cap",
            local_reason="the template requests a size the class will never "
                         "provision",
            read=("describe {ns}/{pod} (Pod)",
                  "Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.MountDevice failed for volume \"{pvc}\": the "
                     "controller has not published the volume",
            local_cause="this Job's own pod mounts the same claim twice with "
                        "conflicting mount options",
            local_reason="two volumeMounts name the same claim, one read-only and "
                         "one read-write, and the second mount fails",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.MountDevice failed for volume "
                  "\"{pvc}\": mount failed"),
            pass_confidence="high",
        ),
    ),
)

_T_CSI_CONTROLLER_UNSCHEDULABLE = Propagation(
    key="csi-controller-unschedulable",
    blast_radius="cluster",
    scope_field=None,
    origin="the archive-hdd CSI controller cannot be scheduled, so claims on that "
           "class are never provisioned",
    shared_cause="the archive-hdd CSI controller cannot be scheduled, so claims on "
                 "that class are never provisioned",
    shared_reason="storage-system/archive-hdd-csi-controller shows 0 of 1 ready and "
                  "Pending because its node selector storage-tier=archive matches "
                  "no node, and 0 PersistentVolumes have bound on archive-hdd in "
                  "the last 20m",
    distractor_cause="the workloads' own claim templates were switched to a class "
                     "name with a typo in the last chart release",
    distractor_reason="the claims name archive-hdd exactly and the class exists; "
                      "its controller has no node to run on",
    rationale="this workload's claim is on the archive-hdd class, and that class's "
              "controller is Pending with no node matching its selector, so "
              "nothing on the class is provisioned; the workload's own claim is "
              "unchanged",
    remedy="Label a node storage-tier=archive (or fix the controller's node "
           "selector) so the archive-hdd controller can run; the flagged workloads "
           "need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass archive-hdd",
        ("archive-hdd controller placement: its node selector matches no node\n"
         "provisioner: example.com/archive-hdd-csi\n"
         "controller storage-system/archive-hdd-csi-controller: 0/1 ready, Pending "
         "(node selector matches no node)\n"
         "node selector: storage-tier=archive\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "archive-hdd controller placement: Running on its archive node\n"
        "provisioner: example.com/archive-hdd-csi\n"
        "controller storage-system/archive-hdd-csi-controller: 1/1 ready, Running\n"
        "node selector: storage-tier=archive (1 node)\n"
        "PersistentVolumes bound in the last 20m: 3"
    ),
    origin_state=("matches no node", "Running"),
    origin_variants=(
        (("archive-hdd controller placement: its node selector matches no node\n"
          "provisioner: example.com/archive-hdd-csi\n"
          "controller storage-system/archive-hdd-csi-controller: 0/1 ready, "
          "Pending (node selector matches no node)\n"
          "node selector: storage-tier=archive\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("archive-hdd controller placement: Running on its archive node\n"
          "provisioner: example.com/archive-hdd-csi\n"
          "controller storage-system/archive-hdd-csi-controller: 1/1 ready, "
          "Running\n"
          "node selector: storage-tier=archive (1 node)\n"
          "PersistentVolumes bound in the last 20m: 3")),
        (("the archive-hdd CSI controller is Pending because its node selector "
          "matches no node\n"
          "the label storage-tier=archive is on 0 of 3 nodes since the last node "
          "pool rollout\n"
          "no archive-hdd claim has bound in 20m"),
         ("the archive-hdd CSI controller is Running on the node labelled "
          "storage-tier=archive\n"
          "the label is on 1 of 3 nodes\n"
          "3 archive-hdd claims bound in the last 20m")),
        (("Warning  FailedScheduling  default-scheduler  0/3 nodes are available: "
          "3 node(s) didn't match Pod's node affinity/selector "
          "(archive-hdd-csi-controller: selector matches no node)"),
         ("Normal  Scheduled  default-scheduler  Successfully assigned "
          "storage-system/archive-hdd-csi-controller to the archive node "
          "(Running)")),
        (("class archive-hdd provisioner placement: matches no node\n"
          "controller pods ready: 0 of 1\n"
          "claims waiting on this class: 3, bound in 20m: 0"),
         ("class archive-hdd provisioner placement: Running, 1 node matched\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 0, bound in 20m: 3")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim pins a volume by name that "
                        "another claim already holds",
            local_reason="the claim's volumeName points at a PersistentVolume bound "
                         "to a different claim",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Job's own claim asks for ReadWriteMany on a class that "
                        "only offers ReadWriteOnce",
            local_reason="the claim's access mode is one the class cannot provide",
            read=("describe {ns}/{pod} (Pod)",
                  "Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="init step waited 120s for its data volume and gave up",
            local_cause="this StatefulSet's own init container polls a volume path "
                        "that its last chart release renamed, so it never sees the "
                        "disk that is mounted",
            local_reason="the init step waits on a path the chart no longer mounts "
                         "the disk at",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: init step gave up waiting for its data volume "
                  "(3 of 3 sampled restarts)"),
            log_cause="init step gave up waiting for its data volume",
            pass_confidence="high",
        ),
    ),
)

_T_PROVISIONER_CREDENTIALS_ROTATED = Propagation(
    key="provisioner-credentials-rotated",
    blast_radius="cluster",
    scope_field=None,
    origin="the encrypted-ssd provisioner's backend credentials were rotated, so the "
           "backend refuses every new volume request",
    shared_cause="the encrypted-ssd provisioner's backend credentials were rotated, "
                 "so the backend refuses every new volume request",
    shared_reason="storage-system/encrypted-ssd-csi-controller is 1 of 1 ready, but "
                  "its last provision error says the backend refused credentials "
                  "(401), and 0 PersistentVolumes have bound on encrypted-ssd in "
                  "the last 20m",
    distractor_cause="the workloads' own service accounts lost the storage role in "
                     "the last RBAC change",
    distractor_reason="claims need no service account role to bind, and the refusal "
                      "comes from the storage backend, not the API server",
    rationale="this workload's claim is on the encrypted-ssd class, and that "
              "class's backend refuses the provisioner's credentials, so no claim "
              "on it binds; the workload's own claim is unchanged",
    remedy="Update the encrypted-ssd provisioner's backend secret with the rotated "
           "credentials and restart it; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass encrypted-ssd",
        ("encrypted-ssd backend provision errors: refused credentials on every "
         "call\n"
         "provisioner: example.com/encrypted-ssd-csi\n"
         "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
         "Running\n"
         "last provision error: backend refused credentials (401)\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "encrypted-ssd backend provision errors: none\n"
        "provisioner: example.com/encrypted-ssd-csi\n"
        "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
        "Running\n"
        "last provision error: none\n"
        "PersistentVolumes bound in the last 20m: 6"
    ),
    origin_state=("refused credentials", "none"),
    origin_variants=(
        (("encrypted-ssd backend provision errors: refused credentials on every "
          "call\n"
          "provisioner: example.com/encrypted-ssd-csi\n"
          "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "last provision error: backend refused credentials (401)\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("encrypted-ssd backend provision errors: none\n"
          "provisioner: example.com/encrypted-ssd-csi\n"
          "controller storage-system/encrypted-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "last provision error: none\n"
          "PersistentVolumes bound in the last 20m: 6")),
        (("the encrypted-ssd controller is up but its backend has refused "
          "credentials on all 6 provision calls in 20m\n"
          "the backend rotated its access credentials overnight and the provisioner still "
          "holds the old ones\n"
          "no encrypted-ssd claim has bound since"),
         ("the encrypted-ssd controller is up and its backend accepted all 6 "
          "provision calls in 20m\n"
          "provision errors in that window: none\n"
          "6 encrypted-ssd claims bound in the last 20m")),
        (("Warning  ProvisioningFailed  example.com/encrypted-ssd-csi  failed to "
          "provision volume: backend refused credentials (401)"),
         ("Normal  ProvisioningSucceeded  example.com/encrypted-ssd-csi  "
          "Successfully provisioned volume (errors in 20m: none)")),
        (("class encrypted-ssd backend auth: refused credentials\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 6, bound in 20m: 0"),
         ("class encrypted-ssd backend auth: accepted, errors none\n"
          "controller pods ready: 1 of 1\n"
          "claims waiting on this class: 0, bound in 20m: 6")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim was created in the wrong "
                        "namespace by its chart, so the pod never finds it",
            local_reason="the chart rendered the claim into a different namespace "
                         "than the Deployment",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this StatefulSet's own claim template sets a selector that "
                        "no PersistentVolume label matches",
            local_reason="the template's selector asks for a volume label nothing "
                         "in the cluster carries",
            read=("describe {ns}/{pod} (Pod)",
                  "Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the backend "
                     "did not complete the attach",
            local_cause="this Job's own claim is bound to a volume still attached to "
                        "a node that was deleted without detaching",
            local_reason="the volume's attachment record names a node that no "
                         "longer exists",
            read=("get_events {ns}/{name}",
                  "Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed"),
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 3: Write the last two records**

Insert them directly after `_T_PROVISIONER_CREDENTIALS_ROTATED`.

```python
_T_STORAGE_BACKEND_FULL = Propagation(
    key="storage-backend-full",
    blast_radius="cluster",
    scope_field=None,
    origin="the bulk-nvme storage backend is out of space, so the provisioner cannot "
           "carve a new volume for any claim on that class",
    shared_cause="the bulk-nvme storage backend is out of space, so the provisioner "
                 "cannot carve a new volume for any claim on that class",
    shared_reason="storage-system/bulk-nvme-csi-controller is 1 of 1 ready, but the "
                  "backend reports out of space with 0 GiB free of 4 TiB, and 0 "
                  "PersistentVolumes have bound on bulk-nvme in the last 20m",
    distractor_cause="the workloads' own claims ask for more space than their "
                     "namespace quota allows",
    distractor_reason="every namespace involved has quota to spare, and the claims "
                      "were admitted; the backend has no space to fill them",
    rationale="this workload's claim is on the bulk-nvme class, and that class's "
              "backend has no free space to provision from; the workload's own "
              "claim is unchanged",
    remedy="Free or add capacity on the bulk-nvme backend (delete released volumes "
           "or extend the pool); the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related storageclass bulk-nvme",
        ("bulk-nvme backend: out of space\n"
         "provisioner: example.com/bulk-nvme-csi\n"
         "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
         "backend capacity: out of space (0 GiB free of 4 TiB)\n"
         "PersistentVolumes bound in the last 20m: 0"),
    ),
    healthy_origin_content=(
        "bulk-nvme backend: space remaining\n"
        "provisioner: example.com/bulk-nvme-csi\n"
        "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
        "backend capacity: space remaining 1.9 TiB of 4 TiB\n"
        "PersistentVolumes bound in the last 20m: 4"
    ),
    origin_state=("out of space", "space remaining"),
    origin_variants=(
        (("bulk-nvme backend: out of space\n"
          "provisioner: example.com/bulk-nvme-csi\n"
          "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
          "backend capacity: out of space (0 GiB free of 4 TiB)\n"
          "PersistentVolumes bound in the last 20m: 0"),
         ("bulk-nvme backend: space remaining\n"
          "provisioner: example.com/bulk-nvme-csi\n"
          "controller storage-system/bulk-nvme-csi-controller: 1/1 ready, Running\n"
          "backend capacity: space remaining 1.9 TiB of 4 TiB\n"
          "PersistentVolumes bound in the last 20m: 4")),
        (("the bulk-nvme backend is out of space: 0 GiB free of 4 TiB\n"
          "the controller is up and every provision call fails on capacity\n"
          "no bulk-nvme claim has bound in 20m"),
         ("the bulk-nvme backend has space remaining: 1.9 TiB free of 4 TiB\n"
          "the controller is up and every provision call in 20m succeeded\n"
          "4 bulk-nvme claims bound in the last 20m")),
        (("Warning  ProvisioningFailed  example.com/bulk-nvme-csi  failed to "
          "provision volume: backend out of space (0 GiB free)"),
         ("Normal  ProvisioningSucceeded  example.com/bulk-nvme-csi  Successfully "
          "provisioned volume (space remaining 1.9 TiB)")),
        (("class bulk-nvme backend capacity: out of space\n"
          "free: 0 GiB of 4 TiB\n"
          "claims waiting on this class: 4, bound in 20m: 0"),
         ("class bulk-nvme backend capacity: space remaining\n"
          "free: 1.9 TiB of 4 TiB\n"
          "claims waiting on this class: 0, bound in 20m: 4")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Deployment's own claim asks for a size below the "
                        "class's minimum, which the provisioner rejects",
            local_reason="the claim requests 100Mi and the class provisions nothing "
                         "under 1Gi",
            read=("get_events {ns}/{name}",
                  "Warning  FailedScheduling  default-scheduler  0/3 nodes are "
                  "available: pod has unbound immediate PersistentVolumeClaims"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="Job",
            status="Pending",
            issue="Unschedulable",
            reason="no node has room for the pod",
            evidence="pod has unbound immediate PersistentVolumeClaims",
            local_cause="this Job's own claim names a snapshot as its data source "
                        "that was pruned by the retention policy",
            local_reason="the claim's dataSource points at a VolumeSnapshot that no "
                         "longer exists",
            read=("describe {ns}/{pod} (Pod)",
                  "Status: Pending\nVolumes: {pvc} (PersistentVolumeClaim, "
                  "unbound)\nEvents: Warning  FailedScheduling  default-scheduler  "
                  "0/3 nodes are available: pod has unbound immediate "
                  "PersistentVolumeClaims"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the backend "
                     "could not allocate the attach",
            local_cause="this StatefulSet's own volume was resized past the "
                        "backend's per-volume cap and the failed resize left it "
                        "detached",
            local_reason="the claim's last resize was refused by the backend and "
                         "the volume has not reattached since",
            read=("get_events {ns}/{name}",
                  "Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed"),
            pass_confidence="high",
        ),
    ),
)

_T_CSI_DRIVER_VERSION_MISMATCH = Propagation(
    key="csi-driver-version-mismatch",
    blast_radius="cluster",
    scope_field=None,
    origin="the replicated-ssd CSI controller was upgraded ahead of its node "
           "plugins, so volumes it provisions cannot be staged on any node",
    shared_cause="the replicated-ssd CSI controller was upgraded ahead of its node "
                 "plugins, so volumes it provisions cannot be staged on any node",
    shared_reason="storage-system/replicated-ssd-csi-controller is 1 of 1 ready at "
                  "driver API v2 while every node plugin is still at v1, and of the "
                  "5 PersistentVolumes bound on replicated-ssd in the last 20m, 0 "
                  "have been staged on any node",
    distractor_cause="the workloads' own pods were moved to nodes without the CSI "
                     "node plugin in the last node pool rollout",
    distractor_reason="every node runs the replicated-ssd node plugin and reports "
                      "it healthy; the plugin is a version the controller no longer "
                      "speaks to",
    rationale="this workload's volume is on the replicated-ssd class, and that "
              "class's controller provisions volumes its older node plugins cannot "
              "stage; the workload's own volume spec is unchanged",
    remedy="Roll the replicated-ssd node plugin DaemonSet to the controller's "
           "version (or roll the controller back); the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related storageclass replicated-ssd",
        ("replicated-ssd driver versions: mismatch between controller and node "
         "plugins\n"
         "provisioner: example.com/replicated-ssd-csi\n"
         "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
         "Running\n"
         "driver API: controller v2, node plugins v1 (mismatch)\n"
         "PersistentVolumes bound in the last 20m: 5, staged on a node: 0"),
    ),
    healthy_origin_content=(
        "replicated-ssd driver versions: in step\n"
        "provisioner: example.com/replicated-ssd-csi\n"
        "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
        "Running\n"
        "driver API: controller v2, node plugins v2, in step\n"
        "PersistentVolumes bound in the last 20m: 5, staged on a node: 5"
    ),
    origin_state=("mismatch", "in step"),
    origin_variants=(
        (("replicated-ssd driver versions: mismatch between controller and node "
          "plugins\n"
          "provisioner: example.com/replicated-ssd-csi\n"
          "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "driver API: controller v2, node plugins v1 (mismatch)\n"
          "PersistentVolumes bound in the last 20m: 5, staged on a node: 0"),
         ("replicated-ssd driver versions: in step\n"
          "provisioner: example.com/replicated-ssd-csi\n"
          "controller storage-system/replicated-ssd-csi-controller: 1/1 ready, "
          "Running\n"
          "driver API: controller v2, node plugins v2, in step\n"
          "PersistentVolumes bound in the last 20m: 5, staged on a node: 5")),
        (("the replicated-ssd controller speaks driver API v2 and every node "
          "plugin still speaks v1: a mismatch\n"
          "the controller was upgraded 25m ago and the node plugin DaemonSet was "
          "not\n"
          "5 volumes bound since then, 0 staged on any node"),
         ("the replicated-ssd controller and every node plugin speak driver API "
          "v2, in step\n"
          "both were upgraded together 3d ago\n"
          "5 volumes bound in 20m, all 5 staged")),
        (("Warning  FailedMount  kubelet  MountVolume.MountDevice failed: node "
          "plugin v1 cannot stage a v2 volume (driver version mismatch)"),
         ("Normal  SuccessfulMountVolume  kubelet  MapVolume.MapPodDevice "
          "succeeded (driver versions in step, v2/v2)")),
        (("class replicated-ssd driver API: mismatch\n"
          "controller: v2, node plugins: v1 on 3 of 3 nodes\n"
          "volumes bound in 20m: 5, staged: 0"),
         ("class replicated-ssd driver API: in step\n"
          "controller: v2, node plugins: v2 on 3 of 3 nodes\n"
          "volumes bound in 20m: 5, staged: 5")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment",
            status="ContainerCreating",
            issue="VolumeMountError",
            reason="volume {pvc} could not be mounted into the pod",
            evidence="MountVolume.MountDevice failed for volume \"{pvc}\": the node "
                     "plugin could not stage the volume",
            local_cause="this Deployment's own volume mount asks for a mount option "
                        "the driver does not support",
            local_reason="the claim's mountOptions carry a flag the driver rejects "
                         "at stage",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nStatus: ContainerCreating\nEvents: Warning  "
                  "FailedMount  kubelet  MountVolume.MountDevice failed for volume "
                  "\"{pvc}\": stage failed"),
            pass_confidence="high",
        ),
        Victim(
            workload_kind="StatefulSet",
            status="ContainerCreating",
            issue="VolumeAttachError",
            reason="volume {pvc} could not be attached to the pod's node",
            evidence="AttachVolume.Attach failed for volume \"{pvc}\": the node "
                     "plugin did not acknowledge the attach",
            local_cause="this StatefulSet's own volume was left attached to a node "
                        "that was removed from the cluster before its pod moved",
            local_reason="the volume's attachment still names the removed node and "
                         "the new node cannot take it",
            read=("get_events {ns}/{name}",
                  "Warning  FailedAttachVolume  attachdetach-controller  "
                  "AttachVolume.Attach failed for volume \"{pvc}\": attach failed"),
            pass_confidence="medium",
        ),
        Victim(
            workload_kind="Job",
            status="ContainerStartError",
            issue="ContainerStartError",
            reason="container {container} could not be started",
            evidence="failed to start container: the data volume was not staged "
                     "before the container's start deadline",
            local_cause="this Job's own container entrypoint runs a filesystem check "
                        "that fails on the volume's unclean journal",
            local_reason="the entrypoint's fsck refuses the volume and exits before "
                         "the main process starts",
            read=("describe {ns}/{pod} (Pod)",
                  "Node: {node}\nEvents: Warning  Failed  kubelet  Error: failed to "
                  "start container \"{container}\": data volume not ready"),
            pass_confidence="high",
        ),
    ),
)
```

- [ ] **Step 4: Append the five names to the pool tuple**

After `_T_RUNTIME_CLASS_REMOVED` in `_TRAINING_SCENARIOS`:

```python
                       _T_RUNTIME_CLASS_REMOVED, _T_CSI_CONTROLLER_OOMKILLED,
                       _T_CSI_CONTROLLER_UNSCHEDULABLE,
                       _T_PROVISIONER_CREDENTIALS_ROTATED, _T_STORAGE_BACKEND_FULL,
                       _T_CSI_DRIVER_VERSION_MISMATCH)
```

- [ ] **Step 5: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py tests/test_shared_origin_training_pair.py -v`
Expected: all PASS with the pool at 43. If `test_every_trainable_scenario_names_its_state_in_words` fails on csi-controller-oomkilled, a broken half says "Running"; on provisioner-credentials-rotated, a broken half contains the letters `none`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add five StorageClass scenarios in the exam's storageclass layout"
```

---

### Task 9: Pin the per-layout floors, then Group E — five NetworkPolicy scenarios in the exam's networkpolicy layout

**Files:**
- Modify: `tests/test_shared_origin_training.py` — new constant `EXAM_LAYOUT_FLOORS`, new helper `_teaches_layout`, new test `test_every_exam_layout_has_a_trained_floor`; `EXPECTED_POOL = 43` → `48`
- Modify: `src/kubeagent_verdict/dataset/propagation.py` — five new records after `_T_CSI_DRIVER_VERSION_MISMATCH`, five names appended to `_TRAINING_SCENARIOS`

**Interfaces:**
- Consumes: `Propagation`, `Victim`; `propagation.trainable_scenarios()`; `EXPECTED_POOL` from Task 8; the layouts Tasks 4–8 added.
- Produces: keys `networkpolicy-dns-egress-missing`, `networkpolicy-namespace-label-drifted`, `networkpolicy-port-mismatch`, `networkpolicy-allow-selector-typo`, `networkpolicy-ingress-deny-all`; the test name `test_every_exam_layout_has_a_trained_floor`, which Task 12's docs cite and `## Done when` requires.

Why the floors first: the pool count says how many scenarios there are, not what shape their reads take. The 0907 model failed on five exam layouts it had seen once or never. The floors pin each layout's count so a later edit that drops a layout fails a test, not an exam. Written before Group E, the test fails on exactly one line (NetworkPolicy, 1 of 6), which proves it can fail.

How a scenario counts: it counts once for a layout when its read label starts the way the exam's does and any half of any of its origin variants carries the layout's marker text. The Deployment floor uses `startswith("describe ")` plus `endswith("(Deployment)")`, because cert-manager's label starts `describe cert-manager/` and the exam's starts `describe kube-system/`. Both are the same layout.

The floors are the spec's. After this task the measured counts are higher on two layouts:

| layout | marker | floor | after this task |
|---|---|---|---|
| node | `Conditions:` and `Taints:` in one half, label starts `describe node ` | 13 | 13 |
| deployment | `Replicas:` in a half, label `describe …(Deployment)` | 4 | 7 |
| events | label starts `get_events (cluster-wide, reason=` | 4 | 4 |
| storageclass | `bound in the last` in a half, label starts `get_related storageclass` | 6 | 6 |
| networkpolicy | `podSelector:` in a half, label starts `get_related networkpolicy` | 6 | 6 |

Why these five scenarios: networkpolicy-deny-all is the exam's only NetworkPolicy read and training had one cousin. These five keep the exam's four-line layout and vary the fault: no DNS rule, a namespace label that drifted, a port that moved, a selector typo, and a deny-all on ingress instead of egress. Every victim carries `network_policies=("<policy>",)` so the rendered pod shows the policy the way the exam's victims do. Every `shared_cause` names `{ns}`; no variant text carries a placeholder.

- [ ] **Step 1: Write the floors test**

Add to `tests/test_shared_origin_training.py`, directly after `test_the_trainable_pool_holds_the_planned_count`:

```python
# One marker per exam read layout, and the fewest trainable scenarios that
# must teach it. A scenario counts once per layout when its read label
# starts the way the exam's does and any half of any of its origin
# variants carries the marker text. The floors are the spec's; the
# measured counts after the coverage branch are node 13, deployment 7,
# events 4, storageclass 6, networkpolicy 6.
EXAM_LAYOUT_FLOORS = {
    "node": 13,
    "deployment": 4,
    "events": 4,
    "storageclass": 6,
    "networkpolicy": 6,
}


def _teaches_layout(p, layout: str) -> bool:
    label = p.origin_read[0]
    halves = [p.origin_read[1], p.healthy_origin_content]
    for broken, healthy in p.origin_variants:
        halves.extend((broken, healthy))
    if layout == "node":
        return (label.startswith("describe node ")
                and any("Conditions:" in h and "Taints:" in h for h in halves))
    if layout == "deployment":
        return (label.startswith("describe ") and label.endswith("(Deployment)")
                and any("Replicas:" in h for h in halves))
    if layout == "events":
        return label.startswith("get_events (cluster-wide, reason=")
    if layout == "storageclass":
        return (label.startswith("get_related storageclass")
                and any("bound in the last" in h for h in halves))
    if layout == "networkpolicy":
        return (label.startswith("get_related networkpolicy")
                and any("podSelector:" in h for h in halves))
    raise ValueError(layout)


def test_every_exam_layout_has_a_trained_floor():
    """The 0907 model read five exam layouts it had seen once or never in
    training. Each layout now has a floor: the fewest trainable scenarios
    that carry the exam's read shape. A drop below a floor is a regression
    the pool count cannot see, because it counts scenarios, not shapes."""
    short = {}
    for layout, floor in EXAM_LAYOUT_FLOORS.items():
        keys = sorted(p.key for p in propagation.trainable_scenarios()
                      if _teaches_layout(p, layout))
        if len(keys) < floor:
            short[layout] = (len(keys), floor, keys)
    assert not short, f"layouts under their floor (count, floor, keys): {short}"
```

- [ ] **Step 2: Run it and watch it fail on NetworkPolicy only**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k trained_floor -v`
Expected: FAIL, and the message names exactly one layout: `{'networkpolicy': (1, 6, ['networkpolicy-egress-allowlist-stale'])}`. If node, deployment, events or storageclass also appear, a Task 4–8 variant lost its marker; fix that scenario, not the floor.

- [ ] **Step 3: Bump the pin**

Set `EXPECTED_POOL = 48`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py -k planned_count -v`
Expected: FAIL, `43 == 48`.

- [ ] **Step 4: Write the first three records**

Insert them directly after `_T_CSI_DRIVER_VERSION_MISMATCH`.

```python
_T_NETPOL_DNS_EGRESS_MISSING = Propagation(
    key="networkpolicy-dns-egress-missing",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's egress policy has no DNS rule, so every pod's name "
           "lookups are dropped",
    shared_cause="the egress policy in {ns} allows no DNS traffic, so every pod "
                 "there fails to resolve any name",
    shared_reason="{ns}/egress-to-app selects every pod in the namespace with "
                  "policyTypes Egress and one rule, to app=backend on tcp/8080; "
                  "it has no rule to kube-system on udp/53, so DNS is not "
                  "allowed for any of the 6 selected pods",
    distractor_cause="the workloads' own DNS settings were changed to a "
                     "nameserver outside the cluster in the last chart release",
    distractor_reason="every pod still uses the cluster DNS service address from "
                      "its dnsPolicy ClusterFirst; the queries leave the pod and "
                      "are dropped at the policy",
    rationale="the workload cannot resolve any name because the egress policy "
              "that selects it has no DNS rule, and that is true of every pod "
              "in {ns} right now",
    remedy="Add an egress rule to {ns}/egress-to-app allowing udp/53 to "
           "kube-system; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-app",
        ("DNS egress allowed: no\n"
         "podSelector: empty (selects every pod in the namespace)\n"
         "policyTypes: Egress\n"
         "egress: allow to app=backend tcp/8080\n"
         "DNS udp/53 allowed: no\n"
         "pods selected: 6 of 6"),
    ),
    healthy_origin_content=(
        "DNS egress allowed: yes\n"
        "podSelector: empty (selects every pod in the namespace)\n"
        "policyTypes: Egress\n"
        "egress: allow to app=backend tcp/8080\n"
        "egress: allow to kube-system udp/53\n"
        "DNS udp/53 allowed: yes\n"
        "pods selected: 6 of 6"
    ),
    origin_state=("allowed: no", "allowed: yes"),
    origin_variants=(
        (("DNS egress allowed: no\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=backend tcp/8080\n"
          "DNS udp/53 allowed: no\n"
          "pods selected: 6 of 6"),
         ("DNS egress allowed: yes\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=backend tcp/8080\n"
          "egress: allow to kube-system udp/53\n"
          "DNS udp/53 allowed: yes\n"
          "pods selected: 6 of 6")),
        (("the namespace egress policy selects all 6 pods and lists one rule, to "
          "the backend on tcp/8080\n"
          "DNS to kube-system udp/53 allowed: no\n"
          "name lookups from every selected pod time out"),
         ("the namespace egress policy selects all 6 pods and lists two rules, "
          "to the backend and to kube-system udp/53\n"
          "DNS to kube-system udp/53 allowed: yes\n"
          "name lookups from every selected pod answer in under 5ms")),
        (("Warning  PolicyDrop  network-plugin  DNS query to kube-system udp/53 "
          "dropped by egress-to-app (DNS allowed: no)"),
         ("Normal  PolicyAllow  network-plugin  DNS query to kube-system udp/53 "
          "passed egress-to-app (DNS allowed: yes)")),
        (("egress-to-app DNS rule: missing, allowed: no\n"
          "selected pods: 6 of 6\n"
          "dropped udp/53 packets in the last 10m: 2410"),
         ("egress-to-app DNS rule: present, allowed: yes\n"
          "selected pods: 6 of 6\n"
          "dropped udp/53 packets in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="name resolution failed on start",
            local_cause="this Deployment's own pod spec sets dnsPolicy None with an "
                        "empty nameserver list, so it has nowhere to send a query",
            local_reason="the pod's own dnsConfig lists no nameserver at all",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: name resolution failed on start (3 of 3 "
                  "sampled restarts)"),
            pass_confidence="high",
            network_policies=("egress-to-app",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: peer lookup failed",
            local_cause="this StatefulSet's own readiness check resolves a hostname "
                        "with a typo that no zone serves",
            local_reason="the probe's own peer hostname is misspelled in the "
                         "StatefulSet's config",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: peer lookup failed"),
            pass_confidence="medium",
            network_policies=("egress-to-app",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-backend could not resolve the backend name",
            local_cause="this Job's own init container looks up a search domain "
                        "that its chart dropped from the pod's dnsConfig",
            local_reason="the init step queries a short name whose search domain "
                         "the pod no longer carries",
            read=("get_events {ns}/{name}",
                  "Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-backend could not resolve "
                  "the backend name"),
            pass_confidence="high",
            network_policies=("egress-to-app",),
        ),
    ),
)

_T_NETPOL_NAMESPACE_LABEL_DRIFTED = Propagation(
    key="networkpolicy-namespace-label-drifted",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's broker egress policy names the messaging namespace by a "
           "label that was renamed, so no pod can reach the broker",
    shared_cause="the egress policy in {ns} names the messaging namespace by a "
                 "label that was renamed, so no pod there can reach the message "
                 "broker",
    shared_reason="{ns}/egress-to-messaging selects app=orders pods, 3 of 6, with "
                  "one Egress rule to namespaceSelector team=messaging on "
                  "tcp/5672; that selector matches 0 namespaces since the "
                  "messaging namespace was relabelled, so broker traffic from "
                  "every selected pod is dropped",
    distractor_cause="the message broker has stopped accepting connections from "
                     "every namespace",
    distractor_reason="the broker's own readiness passes and a pod in another "
                      "namespace publishes to it without error",
    rationale="the workload cannot reach the broker because the egress policy "
              "that selects it matches no namespace any more, and that is true "
              "of every selected pod in {ns} right now",
    remedy="Update the namespaceSelector in {ns}/egress-to-messaging to the "
           "messaging namespace's current label; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-messaging",
        ("Broker namespace match: no namespace carries the rule's label\n"
         "podSelector: app=orders\n"
         "policyTypes: Egress\n"
         "egress: allow to namespaceSelector team=messaging tcp/5672\n"
         "namespaces matched: 0 (matches no namespace; label renamed)\n"
         "pods selected: 3 of 6"),
    ),
    healthy_origin_content=(
        "Broker namespace match: the messaging namespace\n"
        "podSelector: app=orders\n"
        "policyTypes: Egress\n"
        "egress: allow to namespaceSelector team=messaging tcp/5672\n"
        "namespaces matched: 1 (the messaging namespace)\n"
        "pods selected: 3 of 6"
    ),
    origin_state=("no namespace", "messaging namespace"),
    origin_variants=(
        (("Broker namespace match: no namespace carries the rule's label\n"
          "podSelector: app=orders\n"
          "policyTypes: Egress\n"
          "egress: allow to namespaceSelector team=messaging tcp/5672\n"
          "namespaces matched: 0 (matches no namespace; label renamed)\n"
          "pods selected: 3 of 6"),
         ("Broker namespace match: the messaging namespace\n"
          "podSelector: app=orders\n"
          "policyTypes: Egress\n"
          "egress: allow to namespaceSelector team=messaging tcp/5672\n"
          "namespaces matched: 1 (the messaging namespace)\n"
          "pods selected: 3 of 6")),
        (("the broker egress rule's namespaceSelector matches no namespace\n"
          "the label team=messaging was renamed to owner=messaging 40m ago\n"
          "broker connections from the 3 selected pods: all dropped"),
         ("the broker egress rule's namespaceSelector matches the messaging "
          "namespace\n"
          "the label team=messaging is present on it\n"
          "broker connections from the 3 selected pods: all open")),
        (("Warning  PolicyDrop  network-plugin  egress to tcp/5672 dropped by "
          "egress-to-messaging: namespaceSelector matches no namespace"),
         ("Normal  PolicyAllow  network-plugin  egress to tcp/5672 passed "
          "egress-to-messaging: namespaceSelector matches the messaging namespace")),
        (("egress-to-messaging target: no namespace matched\n"
          "selected pods: 3 of 6\n"
          "dropped tcp/5672 connections in the last 10m: 96"),
         ("egress-to-messaging target: the messaging namespace, 1 matched\n"
          "selected pods: 3 of 6\n"
          "dropped tcp/5672 connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="broker connection timed out during startup",
            local_cause="this Deployment's own broker setting names a virtual host "
                        "that was deleted from the broker last week",
            local_reason="the connection setting's vhost no longer exists on the "
                         "broker",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: connection to the broker timed out before the "
                  "first publish (3 of 3 sampled restarts)"),
            pass_confidence="high",
            network_policies=("egress-to-messaging",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-broker gave up after 120s",
            local_cause="this Job's own init container waits on a broker queue that "
                        "was renamed in the last release",
            local_reason="the init step polls a queue name the broker no longer "
                         "declares",
            read=("get_events {ns}/{name}",
                  "Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-broker gave up after 120s"),
            pass_confidence="medium",
            network_policies=("egress-to-messaging",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: broker check timed out",
            local_cause="this StatefulSet's own readiness check publishes a test "
                        "message with credentials the broker revoked",
            local_reason="the probe's own broker login was revoked in the broker's "
                         "last user cleanup",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: broker check timed out"),
            pass_confidence="high",
            network_policies=("egress-to-messaging",),
        ),
    ),
)

_T_NETPOL_PORT_MISMATCH = Propagation(
    key="networkpolicy-port-mismatch",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's cache egress policy opens the cache's old port, so "
           "every connection to its new port is dropped",
    shared_cause="the egress policy in {ns} opens the cache's old port, so every "
                 "connection to its new port is dropped",
    shared_reason="{ns}/egress-to-cache selects role=worker pods, 5 of 6, with one "
                  "Egress rule to app=cache on tcp/6379, while the cache now "
                  "listens on tcp/6380; the port does not match, so every "
                  "connection from the selected pods is dropped",
    distractor_cause="the workloads' own cache client settings still name the "
                     "cache's old port",
    distractor_reason="the clients dial tcp/6380, the port the cache now listens "
                      "on; it is the policy that still says tcp/6379",
    rationale="the workload cannot reach the cache because the egress policy that "
              "selects it opens a port the cache no longer listens on, and that "
              "is true of every selected pod in {ns} right now",
    remedy="Change the cache rule in {ns}/egress-to-cache from tcp/6379 to "
           "tcp/6380; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/egress-to-cache",
        ("Cache port match: no\n"
         "podSelector: role=worker\n"
         "policyTypes: Egress\n"
         "egress: allow to app=cache tcp/6379\n"
         "cache listening port: 6380\n"
         "port match: no\n"
         "pods selected: 5 of 6"),
    ),
    healthy_origin_content=(
        "Cache port match: yes\n"
        "podSelector: role=worker\n"
        "policyTypes: Egress\n"
        "egress: allow to app=cache tcp/6380\n"
        "cache listening port: 6380\n"
        "port match: yes\n"
        "pods selected: 5 of 6"
    ),
    origin_state=("port match: no", "port match: yes"),
    origin_variants=(
        (("Cache port match: no\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to app=cache tcp/6379\n"
          "cache listening port: 6380\n"
          "port match: no\n"
          "pods selected: 5 of 6"),
         ("Cache port match: yes\n"
          "podSelector: role=worker\n"
          "policyTypes: Egress\n"
          "egress: allow to app=cache tcp/6380\n"
          "cache listening port: 6380\n"
          "port match: yes\n"
          "pods selected: 5 of 6")),
        (("the cache egress rule opens tcp/6379 and the cache listens on "
          "tcp/6380, port match: no\n"
          "the cache moved ports in its last rollout and the policy was not "
          "updated\n"
          "cache connections from the 5 selected pods: all dropped"),
         ("the cache egress rule opens tcp/6380 and the cache listens on "
          "tcp/6380, port match: yes\n"
          "the policy was updated with the cache's last rollout\n"
          "cache connections from the 5 selected pods: all open")),
        (("Warning  PolicyDrop  network-plugin  egress to app=cache tcp/6380 "
          "dropped by egress-to-cache (rule opens tcp/6379, port match: no)"),
         ("Normal  PolicyAllow  network-plugin  egress to app=cache tcp/6380 "
          "passed egress-to-cache (rule opens tcp/6380, port match: yes)")),
        (("egress-to-cache rule port: 6379, cache port: 6380, port match: no\n"
          "selected pods: 5 of 6\n"
          "dropped cache connections in the last 10m: 3120"),
         ("egress-to-cache rule port: 6380, cache port: 6380, port match: yes\n"
          "selected pods: 5 of 6\n"
          "dropped cache connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="cache connection timed out during startup",
            local_cause="this Deployment's own cache client pins a protocol version "
                        "the cache stopped serving in its last upgrade",
            local_reason="the client's own protocol setting is one the cache no "
                         "longer answers",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: connection to the cache timed out before the "
                  "first command (3 of 3 sampled restarts)"),
            pass_confidence="high",
            network_policies=("egress-to-cache",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: cache check timed out",
            local_cause="this StatefulSet's own readiness check pings the cache with "
                        "an auth token that expired",
            local_reason="the probe's own cache token passed its expiry last night",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: cache check timed out"),
            pass_confidence="medium",
            network_policies=("egress-to-cache",),
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="cache write-behind queue overflowed, exiting to flush",
            log_cause="cache write-behind queue overflowed",
            local_cause="this agent's own cache connection pool is sized larger than "
                        "the cache's per-client connection cap",
            local_reason="the agent's own pool opens more connections than the cache "
                         "admits and the extras stall its queue",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: cache write-behind queue overflowed (3 of 3 "
                  "sampled restarts)"),
            pass_confidence="high",
            network_policies=("egress-to-cache",),
        ),
    ),
)
```

- [ ] **Step 5: Write the last two records**

Insert them directly after `_T_NETPOL_PORT_MISMATCH`.

```python
_T_NETPOL_ALLOW_SELECTOR_TYPO = Propagation(
    key="networkpolicy-allow-selector-typo",
    blast_radius="namespace",
    scope_field="ns",
    origin="the namespace's frontend allow policy has a typo in its pod selector, "
           "so it selects nothing and the default-deny blocks every frontend pod",
    shared_cause="the {ns} frontend allow policy has a typo in its pod selector, "
                 "so it selects nothing and the namespace's default-deny blocks "
                 "every frontend pod's egress",
    shared_reason="{ns}/allow-frontend-egress carries podSelector role=fronted, "
                  "which selects 0 of 6 pods, while the pods carry role=frontend; "
                  "its one Egress rule to app=api on tcp/443 applies to nobody, "
                  "and the namespace's default-deny egress applies to all 6",
    distractor_cause="the workloads' own images lost their CA bundle in the last "
                     "rebuild",
    distractor_reason="the API's certificate verifies from a pod in another "
                      "namespace running the same image; the connection from "
                      "{ns} never leaves the pod",
    rationale="the workload cannot reach the API because the policy meant to allow "
              "it selects no pod, so the default-deny applies, and that is true "
              "of every frontend pod in {ns} right now",
    remedy="Fix the podSelector in {ns}/allow-frontend-egress from role=fronted "
           "to role=frontend; the flagged workloads need no change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/allow-frontend-egress",
        ("Frontend selector: selects no pod\n"
         "podSelector: role=fronted (selects no pod)\n"
         "policyTypes: Egress\n"
         "egress: allow to app=api tcp/443\n"
         "pods selected: 0 of 6\n"
         "baseline: default-deny egress applies to the 6 unselected pods"),
    ),
    healthy_origin_content=(
        "Frontend selector: every frontend pod\n"
        "podSelector: role=frontend (selects every frontend pod)\n"
        "policyTypes: Egress\n"
        "egress: allow to app=api tcp/443\n"
        "pods selected: 6 of 6\n"
        "baseline: default-deny egress applies to 0 unselected pods"
    ),
    origin_state=("selects no pod", "every frontend pod"),
    origin_variants=(
        (("Frontend selector: selects no pod\n"
          "podSelector: role=fronted (selects no pod)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=api tcp/443\n"
          "pods selected: 0 of 6\n"
          "baseline: default-deny egress applies to the 6 unselected pods"),
         ("Frontend selector: every frontend pod\n"
          "podSelector: role=frontend (selects every frontend pod)\n"
          "policyTypes: Egress\n"
          "egress: allow to app=api tcp/443\n"
          "pods selected: 6 of 6\n"
          "baseline: default-deny egress applies to 0 unselected pods")),
        (("the frontend allow policy's selector says role=fronted and selects no "
          "pod\n"
          "the 6 frontend pods carry role=frontend\n"
          "with nothing selected, the namespace default-deny drops their egress"),
         ("the frontend allow policy's selector says role=frontend and selects "
          "every frontend pod\n"
          "all 6 frontend pods carry role=frontend\n"
          "their egress to the API passes the allow rule")),
        (("Warning  PolicyDrop  network-plugin  egress to app=api tcp/443 dropped "
          "by default-deny: allow-frontend-egress selects no pod (role=fronted)"),
         ("Normal  PolicyAllow  network-plugin  egress to app=api tcp/443 passed "
          "allow-frontend-egress: selector matches every frontend pod")),
        (("allow-frontend-egress selector: role=fronted, selects no pod\n"
          "frontend pods under default-deny: 6 of 6\n"
          "dropped tcp/443 connections in the last 10m: 870"),
         ("allow-frontend-egress selector: role=frontend, every frontend pod\n"
          "frontend pods under default-deny: 0 of 6\n"
          "dropped tcp/443 connections in the last 10m: 0")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="API connection timed out during startup",
            local_cause="this Deployment's own API client pins a TLS version the "
                        "API stopped accepting last month",
            local_reason="the client's own TLS floor is one the API no longer "
                         "negotiates",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: connection to the API timed out before the "
                  "first request (3 of 3 sampled restarts)"),
            pass_confidence="high",
            network_policies=("allow-frontend-egress",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: API check timed out",
            local_cause="this StatefulSet's own readiness check sends the API a "
                        "token from a service account that was deleted",
            local_reason="the probe's own service account no longer exists, so its "
                         "token is rejected",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: API check timed out"),
            pass_confidence="medium",
            network_policies=("allow-frontend-egress",),
        ),
        Victim(
            workload_kind="Job", status="Init:CrashLoopBackOff",
            issue="Init:CrashLoopBackOff",
            reason="init container {init_container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="wait-for-api gave up after 120s",
            local_cause="this Job's own init container calls the API through a proxy "
                        "setting that names a proxy nobody runs any more",
            local_reason="the init step's own proxy variable points at a host that "
                         "was decommissioned",
            read=("get_events {ns}/{name}",
                  "Warning  BackOff  kubelet  back-off restarting failed init "
                  "container {init_container}: wait-for-api gave up after 120s"),
            pass_confidence="high",
            network_policies=("allow-frontend-egress",),
        ),
    ),
)

_T_NETPOL_INGRESS_DENY_ALL = Propagation(
    key="networkpolicy-ingress-deny-all",
    blast_radius="namespace",
    scope_field="ns",
    origin="a deny-all ingress policy selects every pod in the namespace, so no "
           "inbound connection reaches any of them",
    shared_cause="a deny-all ingress policy in {ns} blocks every inbound "
                 "connection, so pods there that need their peers or their "
                 "callers cannot become ready",
    shared_reason="{ns}/deny-all-ingress selects every pod in the namespace, 6 of "
                  "6, with policyTypes Ingress and an empty ingress list, so all "
                  "ingress is denied to every pod",
    distractor_cause="the workloads' own readiness ports were changed in the last "
                     "chart release",
    distractor_reason="the probe ports match the containers' listening ports; the "
                      "probes fail because nothing inbound reaches the pods",
    rationale="the workload cannot take any inbound connection because a deny-all "
              "ingress policy selects it, and that is true of every pod in {ns} "
              "right now",
    remedy="Narrow or delete {ns}/deny-all-ingress and add allow rules for the "
           "peers and callers each pod needs; the flagged workloads need no "
           "change.",
    confidence="high",
    origin_read=(
        "get_related networkpolicy {ns}/deny-all-ingress",
        ("Ingress into this namespace: all ingress denied\n"
         "podSelector: empty (selects every pod in the namespace)\n"
         "policyTypes: Ingress\n"
         "ingress: [] (no rules — all ingress denied)\n"
         "pods selected: 6 of 6"),
    ),
    healthy_origin_content=(
        "Ingress into this namespace: allow from the scheduler, on one pod\n"
        "podSelector: app=legacy-batch\n"
        "policyTypes: Ingress\n"
        "ingress: allow from podSelector app=scheduler\n"
        "pods selected: 1 of 6"
    ),
    origin_state=("all ingress denied", "allow from"),
    origin_variants=(
        (("Ingress into this namespace: all ingress denied\n"
          "podSelector: empty (selects every pod in the namespace)\n"
          "policyTypes: Ingress\n"
          "ingress: [] (no rules — all ingress denied)\n"
          "pods selected: 6 of 6"),
         ("Ingress into this namespace: allow from the scheduler, on one pod\n"
          "podSelector: app=legacy-batch\n"
          "policyTypes: Ingress\n"
          "ingress: allow from podSelector app=scheduler\n"
          "pods selected: 1 of 6")),
        (("the ingress policy selects all 6 pods and lists no rule, so all "
          "ingress denied\n"
          "peer and caller connections into every pod are dropped\n"
          "the policy was applied 30m ago by a cluster-wide hardening job"),
         ("the ingress policy selects 1 of 6 pods and lists one rule, allow from "
          "the scheduler\n"
          "peer and caller connections into the other 5 pods are untouched\n"
          "the policy has not changed in 30d")),
        (("Warning  PolicyDrop  network-plugin  ingress to every pod dropped by "
          "deny-all-ingress: no rules, all ingress denied"),
         ("Normal  PolicyAllow  network-plugin  ingress to app=legacy-batch passed "
          "deny-all-ingress: allow from app=scheduler")),
        (("deny-all-ingress scope: 6 of 6 pods, all ingress denied\n"
          "inbound connections dropped in the last 10m: 4280\n"
          "pods with a passing readiness probe: 0 of 6"),
         ("deny-all-ingress scope: 1 of 6 pods, allow from app=scheduler\n"
          "inbound connections dropped in the last 10m: 0\n"
          "pods with a passing readiness probe: 6 of 6")),
    ),
    victims=(
        Victim(
            workload_kind="Deployment", status="CrashLoopBackOff",
            issue="CrashLoopBackOff",
            reason="container {container} has restarted {restarts} times",
            evidence="last state terminated with exit code 1",
            log_cause="cluster join got no reply from any peer",
            local_cause="this Deployment's own cluster-join step expects a reply on a "
                        "port its container never opens",
            local_reason="the join step's own reply port is not in the container's "
                         "listen list",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: cluster join got no reply from any peer (3 of "
                  "3 sampled restarts)"),
            pass_confidence="high",
            network_policies=("deny-all-ingress",),
        ),
        Victim(
            workload_kind="StatefulSet", status="Running", issue="ProbeFailure",
            reason="readiness probe on container {container} is failing",
            evidence="Readiness probe failed: HTTP probe failed with statuscode: "
                     "503, body: peer handshake did not complete",
            local_cause="this StatefulSet's own readiness check waits on a quorum "
                        "vote its own config sets one member too high",
            local_reason="the quorum size in the StatefulSet's config is one more "
                         "than its replica count",
            read=("get_events {ns}/{name}",
                  "Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe "
                  "failed with statuscode: 503, body: peer handshake did not "
                  "complete"),
            pass_confidence="medium",
            network_policies=("deny-all-ingress",),
        ),
        Victim(
            workload_kind="DaemonSet", status="RestartLoop", issue="RestartLoop",
            reason="container {container} has restarted {restarts} times and is "
                   "Running again between attempts",
            evidence="watchdog: no scrape received in 60s, restarting",
            log_cause="watchdog saw no scrape in 60s",
            local_cause="this agent's own watchdog restarts it whenever its metrics "
                        "endpoint goes 60s without a scrape, and the scrape "
                        "interval is 90s",
            local_reason="the agent's own watchdog window is shorter than the "
                         "scrape interval it is configured with",
            read=("get_log_causes {ns}/{pod}",
                  "classified cause: watchdog saw no scrape in 60s (3 of 3 sampled "
                  "restarts)"),
            pass_confidence="high",
            network_policies=("deny-all-ingress",),
        ),
    ),
)
```

- [ ] **Step 6: Append the five names to the pool tuple**

After `_T_CSI_DRIVER_VERSION_MISMATCH` in `_TRAINING_SCENARIOS`:

```python
                       _T_CSI_DRIVER_VERSION_MISMATCH, _T_NETPOL_DNS_EGRESS_MISSING,
                       _T_NETPOL_NAMESPACE_LABEL_DRIFTED, _T_NETPOL_PORT_MISMATCH,
                       _T_NETPOL_ALLOW_SELECTOR_TYPO, _T_NETPOL_INGRESS_DENY_ALL)
```

- [ ] **Step 7: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_training.py tests/test_propagation.py tests/test_shared_origin_training_pair.py -v`
Expected: all PASS. The pool pin reads 48. The floors test passes with every layout at or above its floor. If `test_every_trainable_scenario_names_its_state_in_words` fails on networkpolicy-namespace-label-drifted, a broken half contains the twelve characters `messaging namespace` (the state line must say "the rule's label", not the namespace's name); on networkpolicy-ingress-deny-all, a broken half contains `allow from`.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests -q`
Expected: all PASS. This is the first full run after the pool doubled, so a floor test at size 5500 (`tests/test_shared_origin_floor.py`) may fail on a per-origin train count below 12. If it does, record the failing origins and their counts in the commit message body and move on: Task 10 raises the build size to 8000 and re-measures every floor.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict
git add src/kubeagent_verdict/dataset/propagation.py tests/test_shared_origin_training.py
git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add five NetworkPolicy scenarios and pin the per-layout floors"
```

---
### Task 10: Move the build size to 8000 and re-measure every size-pinned number

**Files:**
- Modify: `tests/test_shared_origin_floor.py:1-23` (module docstring and `SIZE`)
- Modify: `tests/test_contamination.py:24-27` (comment and `SIZE`), `:59` (the "913")
- Modify: `tests/test_evidence_overlap.py:26-31` (module docstring "16/19"), `:41-43` (`SIZE`), `:58-103` (`DECLARED`), `:150-154` (row-count comment), `:180` ("5500-row corpus")
- Modify: `tests/test_shared_origin_training.py` docstrings of `test_the_shared_answer_stays_the_minority_among_multi_workload_rows` (line 421), `test_the_generator_emits_the_two_classes_near_evenly` (line 534), `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (line 553)
- Modify: `src/kubeagent_verdict/dataset/generate.py:136-137` (the "~0.57" sentence in the multi-loop comment)
- Modify: `src/kubeagent_verdict/dataset/propagation.py:26,76,82` (module docstring)
- Scratch, never tracked: `out/measure-pool.py` (`out/` is in `.gitignore`)

**Interfaces:**
- Consumes: the 48-scenario pool from Task 9; `DRAWS`/`BIG` from Task 1; `generate.counts_for`, `generate.split`, `generate.drop_held_out`, `generate.test_set`.
- Produces: `SEED, SIZE = 17, 8000` in all three size-pinned files; a `DECLARED` dict measured at that size; every docstring number stated at the finished pool. Task 12 copies the size into the docs.

**Why this task exists.** Three test files pin the build recipe by size. The spec moves the recipe to seed 17, size 8000, so that 48 scenarios at 12 percent still give each one about 20 pairs. Every number those files and their neighbours state was measured at 5500 on 24 scenarios. A docstring that states a stale number is a defect, so this task re-measures all of them once, at the finished pool, and writes them down with a reason. Two rows must not move: `shared_origin_probe` and `shared_origin_decoy_probe` stay `(0, 34)`. Their rows come from the six exam scenarios, which never enter training. A nonzero there means a trainable scenario's read is byte-identical to an exam read after masking. That is a data defect to fix in `propagation.py`, never a number to re-declare.

- [ ] **Step 1: Move the three `SIZE` constants**

In `tests/test_shared_origin_floor.py` line 22:

```python
SEED, SIZE = 17, 8000  # the runbook's build recipe
```

In `tests/test_contamination.py` lines 24–27:

```python
# The release configuration, from docs/runbooks/train.md. Contamination is a
# function of seed and size, so a number measured at any other configuration
# says nothing about what ships.
SEED, SIZE = 17, 8000
```

In `tests/test_evidence_overlap.py` lines 41–43:

```python
# The release configuration. These counts are deterministic at exactly this
# seed and size and mean nothing at any other.
SEED, SIZE = 17, 8000
```

- [ ] **Step 2: Run the three files to see what moved**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_shared_origin_floor.py tests/test_contamination.py -v`
Expected: PASS, all five tests. The floor test passes because 8000 × 12 ÷ 100 = 960 rows per half, 20 per scenario before the split, and the split leaves each scenario well above 12. The decoy-width test passes at about 0.50. If the floor test FAILS, stop and report the scenarios it names: the size was chosen so it cannot, and a failure means a scenario is missing from the round-robin.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_evidence_overlap.py -v`
Expected: `test_eval_only_evidence_reuse_matches_the_declared_allowlist` FAILS with an assertion diff between `measured` and `DECLARED`. Copy the `measured` dict out of the failure message; Step 4 uses it. The other tests in the file PASS.

- [ ] **Step 3: Write and run the measurement script**

Write this file to `out/measure-pool.py`. It imports only `generate` and `propagation` and restates the two ratios the training-shape tests compute, so its numbers are the tests' numbers.

```python
"""Print every number the size-pinned tests and docstrings state.

Not tracked. Run it once after the pool is complete and copy the numbers
into the docstrings named in the plan.
"""
from collections import Counter

from kubeagent_verdict.dataset import generate, propagation

SEED = 17
DECLARED_CASES = ("positional_probe", "misattribution_probe",
                  "multi_misattribution_probe", "contradiction_probe",
                  "shared_origin_probe", "shared_origin_decoy_probe")


def by_case(rows, case):
    return [e for e in rows if e.case == case]


def independent_share(rows):
    """Same arithmetic as tests/test_shared_origin_training.py::_independent_share."""
    shared = len(by_case(rows, "shared_origin"))
    independent = (len(by_case(rows, "shared_origin_decoy"))
                   + len([e for e in by_case(rows, "multi")
                          if "origin_read_label" in e.meta]))
    return independent / (shared + independent)


def shared_minority(rows):
    """Same arithmetic as test_the_shared_answer_stays_the_minority_among_multi_workload_rows."""
    shared = len(by_case(rows, "shared_origin"))
    separate = (len(by_case(rows, "multi"))
                + len(by_case(rows, "shared_origin_decoy")))
    return shared / (shared + separate)


def report(size):
    pool = propagation.trainable_scenarios()
    rows = generate.generate(seed=SEED, size=size)
    test = generate.test_set()
    train, val = generate.split(rows, seed=SEED)
    kept_train = generate.drop_held_out(train, test)
    kept_val = generate.drop_held_out(val, test)
    kept = kept_train + kept_val
    counts = generate.counts_for(size)
    held = {part for e in test for part in e.group.split("+")}
    dropped = sum(1 for e in train + val
                  if any(part in held for part in e.group.split("+")))
    per_origin = Counter(e.meta["origin"] for e in kept_train
                         if e.case == "shared_origin")
    decoys = [e for e in kept_train if e.case == "shared_origin_decoy"]
    widths = Counter(len(e.meta["expected"]) for e in decoys)
    wide = sum(n for w, n in widths.items() if w >= 3)
    multi_with_read = [e for e in by_case(kept, "multi")
                       if "origin_read_label" in e.meta]
    print(f"size {size} on {len(pool)} scenarios")
    print(f"  emitted {len(rows)}; train {len(train)}, val {len(val)}; "
          f"kept train {len(kept_train)}, kept val {len(kept_val)}, "
          f"kept {len(kept)}; test {len(test)}")
    print(f"  drop_held_out removes {dropped} rows")
    print(f"  test rows in the six DECLARED slices: "
          f"{sum(1 for e in test if e.case in DECLARED_CASES)}")
    print(f"  counts_for: shared_origin {counts['shared_origin']}, "
          f"shared_origin_decoy {counts['shared_origin_decoy']}, "
          f"multi {counts['multi']}, attributed {counts['attributed']}")
    print(f"  emitted independent share {independent_share(rows):.3f}")
    print(f"  kept independent share {independent_share(kept):.3f}")
    print(f"  kept shared-minority share {shared_minority(kept):.3f}")
    print(f"  kept multi rows with an origin read: {len(multi_with_read)}")
    print(f"  shared_origin rows per scenario in kept train: "
          f"min {min(per_origin[p.key] for p in pool)}, "
          f"max {max(per_origin[p.key] for p in pool)}")
    print(f"  decoy verdict widths in kept train: {dict(sorted(widths.items()))}; "
          f"three or more: {wide} of {len(decoys)} ({wide / len(decoys):.3f})")


for size in (800, 8000):
    report(size)
```

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python out/measure-pool.py`
Expected: two blocks, one per size, in under 10 seconds. Paste both blocks into the task report. Sanity bounds, measured on the 24-scenario pool at the new mix: kept shared-minority share about 0.373 at 800 and 0.385 at 8000; emitted independent share about 0.568 and 0.566; kept independent share about 0.551 and 0.546. The pool size does not change these ratios much, because they are ratios between case counts and `counts_for` fixes the case counts. A value more than 0.02 away from those is a signal that something else moved: stop and report before editing any docstring. `counts_for` at 800 must print `shared_origin 96, shared_origin_decoy 96`.

- [ ] **Step 4: Re-declare `DECLARED` with a reason per row that moved**

In `tests/test_evidence_overlap.py`, compare the `measured` dict from Step 2 with `DECLARED`.

Rules:
- `shared_origin_probe` and `shared_origin_decoy_probe` stay `(0, 34)`. If either measured nonzero, do NOT change the number. Find the colliding read with this snippet (run it from the repo root; it reuses the test module's own helpers):

```python
from tests import test_evidence_overlap as t
from kubeagent_verdict.dataset import generate

exs = generate.generate(seed=t.SEED, size=t.SIZE)
train, val = generate.split(exs, seed=t.SEED)
test = generate.test_set()
kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
trained = {}
for ex in kept:
    for read in t._reads(ex):
        key = t._digest(t._mask(read, ex))
        trained.setdefault(key, (ex.case, ex.meta.get("origin"), read.splitlines()[0]))
for ex in test:
    if ex.case in ("shared_origin_probe", "shared_origin_decoy_probe"):
        for read in t._reads(ex):
            hit = trained.get(t._digest(t._mask(read, ex)))
            if hit:
                print(ex.case, ex.meta["origin"], "|", read.splitlines()[0], "| trained by", hit)
```

  The output names the training row's case and origin and the first line of the read. Fix the data: in `propagation.py`, change that trainable scenario's victim `read` (or `healthy_read_content`, or the origin variant) so it is no longer the exam's text byte for byte after masking. A different first line, a different number, or a different second line is enough. Then re-run the test. Record the fix in the commit body as a data defect found by the allowlist.
- `positional_probe`, `misattribution_probe`, `multi_misattribution_probe`: these reuse `attributed` reads by design, so a count that moves only says the random draws moved. A bigger corpus can only reuse more, so expect each to go up or stay. Write the new pair and add one sentence to its comment, for example: `# 23/25 at size 5500; 25/25 at 8000, because the larger attributed pile draws every template the probe uses.` Use the number you measured, not this example.
- `contradiction_probe`: this row is the instrument. It read 17/19 at 4 percent, 16/19 at 8 percent. Write the measured pair and extend the existing comment with two sentences in the same style: what moved (the mix to 12 percent, the size to 8000, or both) and why (the `none_of_these` rows draw differently). If it measures 0/19, the confound has closed by accident, and the comment says the entry must then be deleted. That is very unlikely at a larger size; if it happens, stop and report rather than deleting.

Then update the module docstring lines 26–31, which say "16/19 becomes 0/19": replace "16/19" with the measured `contradiction_probe` count.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_evidence_overlap.py -v`
Expected: PASS.

- [ ] **Step 5: Restate the row-count comment and the "5500-row" docstring**

In `tests/test_evidence_overlap.py` lines 150–154, the comment reads "measured over every row the guard can reach, 4787 kept + 263 test = 5050 … the allowlist test below actually calls `_reads` on 4883 of them". Replace the three numbers with the script's: `kept` for 4787, `kept + 263` for 5050, and `kept + (test rows in the six DECLARED slices)` for 4883. Keep every other word.

In the docstring at line 180, replace "the whole 5500-row corpus" with "the whole 8000-row corpus".

- [ ] **Step 6: Restate the contamination docstring**

In `tests/test_contamination.py` line 59, replace "never as the measured 913" with "never as the measured N", where N is the script's `drop_held_out removes N rows` at size 8000. Keep the rest of the sentence.

- [ ] **Step 7: Restate the floor test's module docstring**

In `tests/test_shared_origin_floor.py`, keep the first three paragraphs as history and append this paragraph before the closing `"""`, filling the two numbers from the script's size-8000 block:

```
On 2026-09-08 the recipe moved to size 8000, both halves to 12 percent, and
the pool to forty-eight scenarios. That is 960 rows per half, 20 pairs per
scenario before the split. The smallest scenario keeps MIN pairs in train
and the largest MAX. The floor stays at 12: the extra room is the point,
because the split still takes groups by hash, not by count.
```

Write the real numbers in place of MIN and MAX.

- [ ] **Step 8: Restate the training-shape docstrings at the finished pool**

In `tests/test_shared_origin_training.py`:

In `test_the_shared_answer_stays_the_minority_among_multi_workload_rows` (line 421), the docstring sentence that Task 1 changed to "0.373" now reads "the shared answer is 0.373 of the multi-workload rows at 8/8, and the cap of 0.40 leaves room for one more raise but fails as soon as `multi` falls below a fifth of `shared_origin`." Rewrite it to: "the shared answer is S of the multi-workload rows at 12/12 (B at the build size), and the cap of 0.40 leaves no room for another raise: the next one must move `multi` up with it." S is the script's kept shared-minority share at 800 and B the one at 8000.

In `test_the_generator_emits_the_two_classes_near_evenly` (line 534): replace "0.595" (Task 1 made it "0.568") with the script's emitted independent share at 800, and "64/64 at this module's SIZE" with "96/96 at this module's SIZE".

In `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (line 553): the sentence "0.565 toward the independent answer" (Task 1 made it "0.551") takes the script's kept independent share at 800. Task 1's added sentence ("The floor moved from 0.55 to 0.52 … 0.551 at this size and 0.546 at the build size …") takes the script's two kept independent shares in the same two places. Leave the historical "0.619" sentence alone.

Leave `_independent_share`'s docstring alone: its "0.386", "0.619" and "169 rows" describe the day the decoy twin was added, and history does not move.

- [ ] **Step 9: Restate the generator comment and the propagation docstring**

In `src/kubeagent_verdict/dataset/generate.py`, the multi-loop comment sentence "and the kept pile reads ~0.57 toward the INDEPENDENT answer" takes the script's kept independent share at 8000, rounded to two places, in the form "~0.55". Use the measured value.

In `src/kubeagent_verdict/dataset/propagation.py`:
- line 26: "Each scenario is one ORIGIN and two to four VICTIMS." → "Each scenario is one ORIGIN and three or four VICTIMS."
- line 76: "2-4 victims with kinds from `vocab.ISSUE_KINDS`" → "3-4 victims with kinds from `vocab.ISSUE_KINDS`"
- line 82: "twenty-four scenarios taught in equal shares" → "forty-eight scenarios taught in equal shares"

`tests/test_propagation.py::test_scenarios_have_two_to_four_victims` keeps its name and its `2 <= len(p.victims) <= 4` bound. It states the renderer's bound, which is still 2 to 4; the three-victim rule is the training pool's and lives in `tests/test_shared_origin_training.py`.

- [ ] **Step 10: Run everything**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests -q`
Expected: all PASS. This is the first full run at the finished pool and the build size, and nothing is ignored.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check src tests`
Expected: clean.

Run: `cd /home/ubuntu/git/kubeagent-verdict && git status --short`
Expected: only the six tracked files above are modified. `out/measure-pool.py` does not appear (it is ignored). If it appears, do not add it.

- [ ] **Step 11: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_shared_origin_floor.py tests/test_contamination.py tests/test_evidence_overlap.py tests/test_shared_origin_training.py src/kubeagent_verdict/dataset/generate.py src/kubeagent_verdict/dataset/propagation.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "tests: move the build size to 8000 and re-measure every size-pinned number"
```

If Step 4 fixed a colliding read, say so in the commit body: which scenario, which read, and that the allowlist found it.

---

### Task 11: The cousin probe — one fresh twin pair per trainable scenario

**Files:**
- Modify: `src/kubeagent_verdict/dataset/generate.py` (new function `shared_origin_cousin_probes` right after `shared_origin_wide_probes`, before `test_set`)
- Modify: `src/kubeagent_verdict/dataset/cli.py` (new `--probe-cousins FILE` mode beside `--probe-wide`)
- Create: `tests/test_probe_cousins.py`

**Interfaces:**
- Consumes: the 48-scenario pool; `cases.shared_origin_probe(p, rng, victims=None)` and `cases.shared_origin_decoy_probe(p, rng, victims=None)`; `_entry_rng(*parts)`; `generate.write_jsonl`; `evals.score.paired_contrast`.
- Produces: `generate.shared_origin_cousin_probes(pairs_per_origin: int = 1) -> list[Example]` returning 96 rows (48 adjacent twin pairs) over the trainable pool only; `kv-dataset --probe-cousins FILE`. Task 12 documents the command. Spec Section 3 step 10 runs the file through kv-eval on the training host.

**What this probe is.** The wide probe asks the exam's six held-out origins five times each. The cousin probe asks the other question: on the 48 scenarios the model studied, does it read the origin at all? One fresh pair per scenario, full width, so every decoy half carries three or four verdicts, which is the shape that broke the 0907 model's JSON. It is in-distribution by design: a low score here means the recipe did not take, not that coverage is missing. It goes to its own file, never into `test_set()`, and it decides nothing.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_probe_cousins.py`:

```python
"""The cousin probe: one fresh twin pair per trainable scenario.

The wide probe (tests/test_probe_wide.py) asks the six held-out origins
five times each. This probe asks the 48 trained scenarios once each: 48
pairs, 96 rows, every pair at full width, so every decoy half carries three
or four verdicts. It is in-distribution on purpose. A model that reads the
origin on the scenarios it studied and still fails the exam has a coverage
problem; one that fails here has a recipe problem. It is written to its
own file, scored on its own, and decides nothing. The frozen exam does not
move.
"""

from kubeagent_verdict.dataset import generate, propagation


def _pair_key(ex) -> str:
    return "|".join(sorted(ex.meta["expected"]))


def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {p.key for p in propagation.trainable_scenarios()}
    assert len(trainable) == 48
    assert len(rows) == len(trainable) * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == trainable
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 1, origin
        assert case_list.count("shared_origin_decoy_probe") == 1, origin


def test_cousin_probe_uses_only_trainable_origins():
    # The mirror of the wide probe's leak guard. This probe is the
    # in-distribution check, so a held-out origin here would score the exam
    # twice and tell us nothing new.
    held_out = {p.key for p in propagation.all_scenarios()}
    for ex in generate.shared_origin_cousin_probes():
        assert ex.meta["origin"] not in held_out


def test_cousin_rows_are_adjacent_twins_with_unique_pair_keys():
    rows = generate.shared_origin_cousin_probes()
    seen: set[str] = set()
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        key = _pair_key(probe)
        # Same workloads on both halves — that is what makes them one pair.
        assert key == _pair_key(decoy)
        # A repeated key would merge two pairs in the paired scoring.
        assert key not in seen
        seen.add(key)
        # The discriminating read must differ, or the pair asks nothing.
        assert probe.user != decoy.user
        # Probe half: every victim shares ONE cause. Decoy half: none of the
        # victims' correct causes is that shared cause.
        shared = set(probe.meta["expected"].values())
        assert len(shared) == 1
        assert shared.isdisjoint(set(decoy.meta["expected"].values()))


def test_every_cousin_decoy_carries_three_or_more_verdicts():
    # Full width on purpose: three-verdict decoy halves are the shape the
    # 0907 model broke its JSON on, and every trainable scenario now has at
    # least three victims, so every cousin decoy can carry three.
    for ex in generate.shared_origin_cousin_probes():
        if ex.case == "shared_origin_decoy_probe":
            assert len(ex.meta["expected"]) >= 3, ex.meta["origin"]


def test_cousin_probe_fails_a_constant_answer_model():
    # The standing rule: an eval change that could not fail the model it
    # replaced is not a fix. A model that answers every row the same way
    # must score zero pairs.
    from kubeagent_verdict.evals.score import paired_contrast

    rows = generate.shared_origin_cousin_probes()
    for verdict in ("shared", "separate"):
        results = [{"pair_key": _pair_key(ex), "case": ex.case,
                    "shared_verdict": verdict} for ex in rows]
        board = paired_contrast(results)
        assert board["both_correct"]["rate"] == 0.0
        assert board["both_correct"]["n"] == len(rows) // 2
        assert board["unpaired"] == 0
        assert board["ambiguous"] == 0


def test_cousin_probe_is_deterministic():
    a = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    b = [generate.to_row(ex) for ex in generate.shared_origin_cousin_probes()]
    assert a == b


def test_cousin_probe_is_not_in_the_exam():
    # Its own file, never the frozen exam: no cousin row shares an origin
    # with any exam row, and the exam's row count does not move.
    exam = generate.test_set()
    assert len(exam) == 263
    exam_origins = {ex.meta.get("origin") for ex in exam
                    if ex.case in ("shared_origin_probe",
                                   "shared_origin_decoy_probe")}
    cousin_origins = {ex.meta["origin"]
                      for ex in generate.shared_origin_cousin_probes()}
    assert exam_origins.isdisjoint(cousin_origins)


def test_cli_probe_cousins_writes_only_the_standalone_file(tmp_path, monkeypatch):
    import json

    from kubeagent_verdict.dataset import cli

    out = tmp_path / "probe-cousins.jsonl"
    monkeypatch.setattr("sys.argv", ["kv-dataset", "--probe-cousins", str(out)])
    cli.main()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 96
    first = json.loads(lines[0])
    assert first["meta"]["case"] == "shared_origin_probe"
    # Standalone means standalone: no train/val/test/manifest beside it.
    assert [p.name for p in tmp_path.iterdir()] == ["probe-cousins.jsonl"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_probe_cousins.py -v`
Expected: every test FAILS or ERRORS with `AttributeError: module 'kubeagent_verdict.dataset.generate' has no attribute 'shared_origin_cousin_probes'`; the CLI test fails with an argparse error on the unknown flag.

- [ ] **Step 3: Write the generator**

In `src/kubeagent_verdict/dataset/generate.py`, directly after `shared_origin_wide_probes` and before `test_set`:

```python
def shared_origin_cousin_probes(pairs_per_origin: int = 1) -> list[Example]:
    """EVAL-ONLY, DIAGNOSTIC-ONLY: one fresh twin pair per TRAINABLE origin.

    The wide probe asks the six held-out origins five times each. This one
    asks the other question: on the scenarios the model studied, does it
    read the origin at all? One pair per trainable scenario, at full width,
    so every decoy half carries three or four verdicts, which is the shape
    the 0907 model broke its JSON on.

    It is in-distribution on purpose. A model that scores well here and
    fails the exam has a coverage gap; one that fails here has a recipe
    problem. It goes to its own file, never into `test_set()`, and its
    numbers gate no release. Fresh salts keep every pair distinct from the
    training rows' draws; the SAME salt on both halves keeps each pair a
    minimal contrast. A repeated pair key would silently merge two pairs in
    the paired scoring, so a collision raises instead of shrinking the set.
    """
    from kubeagent_verdict.dataset import cases, propagation

    out: list[Example] = []
    seen: dict[str, str] = {}
    for p in propagation.trainable_scenarios():
        for i in range(pairs_per_origin):
            probe = cases.shared_origin_probe(
                p, _entry_rng("shared-origin-cousin", p.key, str(i)),
                victims=None)
            decoy = cases.shared_origin_decoy_probe(
                p, _entry_rng("shared-origin-cousin", p.key, str(i)),
                victims=None)
            key = "|".join(sorted(probe.meta["expected"]))
            if key in seen:
                raise ValueError(
                    f"cousin-probe pair key collision: {seen[key]} and "
                    f"{p.key}#{i} both drew {key!r}; a collision would "
                    "merge two pairs in the paired scoring")
            seen[key] = f"{p.key}#{i}"
            out.append(probe)
            out.append(decoy)
    return out
```

If the collision error fires on the real pool, two scenarios drew the same workload names for all their victims from their own salts. Do not catch it and do not change a scenario. Report it; the fix is a different salt label (for example `"shared-origin-cousin-2"`), and that is a ruling for the controller to record.

- [ ] **Step 4: Add the CLI mode**

In `src/kubeagent_verdict/dataset/cli.py`:

Extend the module docstring so the second paragraph reads:

```python
"""kv-dataset: render the training dataset. Task 8 adds split/test/manifest.

`--probe-wide FILE` and `--probe-cousins FILE` are separate modes: each
writes only its standalone diagnostic file (deterministic, never part of the
exam) and exits. Neither needs a seed and neither touches any other file.
The wide probe asks the six held-out origins five times each; the cousin
probe asks each trainable scenario once.
"""
```

After the `--probe-wide` argument add:

```python
    p.add_argument(
        "--probe-cousins", type=Path, metavar="FILE",
        help="write the cousin probe (one twin pair per trainable "
             "scenario, full width; diagnostic only, gates no release) to "
             "FILE and exit; --seed/--size/--out are not used")
```

After the `if args.probe_wide is not None:` block add:

```python
    if args.probe_cousins is not None:
        rows = generate.shared_origin_cousin_probes()
        args.probe_cousins.parent.mkdir(parents=True, exist_ok=True)
        generate.write_jsonl(args.probe_cousins, rows)
        print(f"wrote {len(rows)} rows ({len(rows) // 2} twin pairs) "
              f"to {args.probe_cousins}")
        return
```

Change the error line to:

```python
        p.error("--seed, --size and --out are required "
                "(unless --probe-wide or --probe-cousins)")
```

- [ ] **Step 5: Run the new tests, then the neighbours**

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests/test_probe_cousins.py tests/test_probe_wide.py tests/test_generate.py -v`
Expected: all PASS. The wide-probe tests still pass; the `--probe-wide` mode is unchanged.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/kv-dataset --probe-cousins out/probe-cousins.jsonl`
Expected: `wrote 96 rows (48 twin pairs) to out/probe-cousins.jsonl`. The file is under `out/`, which git ignores. Do not add it.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests -q && .venv/bin/ruff check src tests`
Expected: all PASS; ruff clean.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/generate.py src/kubeagent_verdict/dataset/cli.py tests/test_probe_cousins.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "dataset: add the cousin probe, one twin pair per trainable scenario"
```

---

### Task 12: Docs — the recipe lines, the new shares, and what the 0907 run taught us

**Files:**
- Modify: `docs/runbooks/train.md` (lines 10–11, 17, 19; one new paragraph after line 482)
- Modify: `README.md` (lines 28, 65–69, 165–170)
- Modify: `docs/design.md` (lines 256, 260–261, 279–285, 401–402)
- Modify: `docs/how-training-works.md` (lines 84, 92–93, 318, 405–408, the table at 410–416, 419–420, 730, 797; one new section before line 835)
- Leave alone: `docs/model-card.md`. Its size-5500 line (393) describes an older tree and is still true of that tree.

Line numbers are from the tree at the branch point. Tasks 1–11 do not touch these four files, so they hold; still, find each line with `grep -n` before editing it.

**Interfaces:**
- Consumes: the 48-scenario pool (Task 9), the size-8000 recipe (Task 10), the `--probe-cousins` flag (Task 11).
- Produces: nothing code reads. The runbook is what the operator follows on the training host for spec Section 3 steps 5–11. That work is not in this plan and this task does not start it.

**Voice.** Every line this task writes is simple voice: short sentences, everyday words, numbers explained ("3 of 10 pairs"). History lines stay. A sentence that says what 4 percent gave, or what 7 percent was tried at, was true when it was written and still is. Only lines that state the current recipe change.

- [ ] **Step 1: Collect the numbers**

Run this script from the repo root and keep its output open. Every number below that appears as `<name>` is replaced by the number this script printed on that line. Nothing else in this task is measured by hand.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
from kubeagent_verdict.dataset import generate

SEED, SIZE = 17, 8000
rows = generate.generate(seed=SEED, size=SIZE)
train, val = generate.split(rows, seed=SEED)
test = generate.test_set()
ktrain = generate.drop_held_out(train, test)
kval = generate.drop_held_out(val, test)
kept = ktrain + kval

print("kept_train", len(ktrain))
print("kept_val", len(kval))
print("shared_pairs_generated", sum(e.case == "shared_origin" for e in rows))
per: dict[str, int] = {}
for e in ktrain:
    if e.case == "shared_origin":
        per[e.meta["origin"]] = per.get(e.meta["origin"], 0) + 1
print("fewest_pairs_in_train", min(per.values()), "most", max(per.values()))

shared = sum(e.case == "shared_origin" for e in kept)
decoy = sum(e.case == "shared_origin_decoy" for e in kept)
multi_all = sum(e.case == "multi" for e in kept)
multi_origin = sum(e.case == "multi" and bool(e.meta.get("origin_healthy")) for e in kept)
separate = decoy + multi_origin
print("origin_read_shared", shared, "origin_read_separate", separate,
      "split", f"{round(100 * shared / (shared + separate))} / "
               f"{round(100 * separate / (shared + separate))}")
print("shared_minority", f"{shared / (shared + multi_all + decoy):.2f}")

before = sum(len(e.meta["expected"]) for e in train + val if e.case == "multi")
after = sum(len(e.meta["expected"]) for e in kept if e.case == "multi")
print("multi_workloads_after_drop", after, "multi_workloads_before_drop", before)
EOF
```

Expected: eight lines. `shared_pairs_generated` is 960 (12 of every 100 rows at size 8000). `fewest_pairs_in_train` is at least 12, the floor Task 10 re-pinned. `shared_minority` is under 0.40. If any of those three does not hold, stop: Task 10 was not finished, and this task does not paper over it.

- [ ] **Step 2: The runbook**

In `docs/runbooks/train.md`:

Lines 10–11. Replace

```
alone runs **about 17½ hours** on a workstation — run it under
```

with

```
alone runs **about 28 hours** at the size-8000 build below (the 0907 run
took about 8 seconds per example pass, and 16 or 32 threads gave the same
wall time, so time scales with rows and nothing else) — run it under
```

Line 17. Replace `kv-dataset --seed 17 --size 5500 --out out/dataset` with `kv-dataset --seed 17 --size 8000 --out out/dataset`.

Line 19. Replace `train+val ≤ 5500` with `train+val ≤ 8000`.

After line 482, which ends `only thing a release argument may cite.`, add this paragraph inside the same list item, indented the same way as the wide-probe paragraph above it:

```
     The cousin probe asks the other question. The wide probe asks the six
     held-out origins five times each; the cousin probe asks every trained
     scenario once. `kv-dataset --probe-cousins out/probe-cousins.jsonl`
     writes one twin pair per trainable scenario (48 pairs, 96 rows) to its
     own file, every decoy half at full width, and
     `kv-eval --test out/probe-cousins.jsonl --endpoint <url>` scores it.
     It is in-distribution on purpose. A model that scores well here and
     fails the exam has a coverage gap; a model that fails here did not
     learn to read the origin at all, and the next look is at the recipe.
     Like the wide probe, it is a diagnostic and not a decider. Report
     both beside the six deciders; neither one changes the verdict.
```

- [ ] **Step 3: The README**

In `README.md`:

Line 28. Replace `kv-dataset --seed 17 --size 5500 --out out/dataset` with `kv-dataset --seed 17 --size 8000 --out out/dataset`.

Lines 65–69. Replace

```
Dataset: `kv-dataset --seed 17 --size 5500`, derived from the chaos
corpus snapshot in `data/corpus/` — kubeagent `chaos-matrix` run id
`32548862821`, dated 2026-08-22. **The shipped weights were trained on a
dataset generated at commit `8bd9d28`, before three generator fixes
landed**, so re-running that command on this tree produces a different,
corrected dataset (4155/432/253 against the 4312/451/205 the weights saw).
```

with

```
Dataset: `kv-dataset --seed 17 --size 8000` on this tree, derived from the
chaos corpus snapshot in `data/corpus/` — kubeagent `chaos-matrix` run id
`32548862821`, dated 2026-08-22. **The shipped weights were trained at size
5500 on a dataset generated at commit `8bd9d28`, before three generator
fixes landed**, so re-running that older size-5500 command on this tree
produces a different, corrected dataset (4155/432/253 against the
4312/451/205 the weights saw). The build size for the next model is 8000.
```

Lines 165–170. The paragraph ends with `Every number on this page still comes from a model that never saw the shape.` Insert, before that last sentence:

```
Since then the share went to 12% each, the pool of trained scenarios went
from 24 to 48, and the build size went from 5500 to 8000, all for the final
retrain.
```

- [ ] **Step 4: The design doc**

In `docs/design.md`:

Line 256. In the `Candidate attributed` row, replace `~18%` with `~10%`.

Lines 260–261. In the `shared_origin` row and the `shared_origin_decoy` row, replace `~8%` with `~12%`.

Lines 279–285. Replace

```
share has since doubled to 8%, paid out of `attributed`, so that every
trainable scenario keeps at least 12 pairs in train after the validation
split; a test pins that floor at the build recipe (seed 17, size 5500). The
shared answer stays the minority answer to a multi-workload question: in the
pile the model reads it is about one in three of the `multi`,
`shared_origin` and `shared_origin_decoy` rows together, and a test fails
above 0.40.
```

with

```
share has since doubled to 8% and then risen to 12%, paid out of
`attributed` both times, so that every trainable scenario keeps at least 12
pairs in train after the validation split; a test pins that floor at the
build recipe (seed 17, size 8000). The shared answer stays the minority
answer to a multi-workload question: in the pile the model reads it is
about <shared_minority> of the `multi`, `shared_origin` and
`shared_origin_decoy` rows together, and a test fails above 0.40.
```

Lines 401–402. Replace

```
  swaps a tag — so across all 1,600 constituent workloads it contributes to
  train and val at `--seed 17 --size 5500` (2,478 before `drop_held_out`),
```

with

```
  swaps a tag — so across all <multi_workloads_after_drop> constituent
  workloads it contributes to train and val at `--seed 17 --size 8000`
  (<multi_workloads_before_drop> before `drop_held_out`),
```

Write the two numbers with a thousands comma, the way the line already does.

- [ ] **Step 5: The training doc**

In `docs/how-training-works.md`:

Line 84. In the `attributed` row, replace `18%` with `10%`.

Lines 92–93. In the `shared_origin` and `shared_origin_decoy` rows, replace `8%` with `12%`.

Line 318. Replace `(it is 8% now; Change 4 below` with `(it is 12% now; Change 4 below says how it reached 8%, and the last section of Part 3 says why it went on to 12%. Change 4`. Read the whole sentence afterwards and make sure it still says one thing.

Lines 405–408. After the sentence ending `7% was tried first and left one scenario at 11.` add:

```
Both halves are 12% since the final retrain's data landed, the build size
is 8000, and the floor test now pins 12 pairs at that recipe (seed 17, size
8000). The last section of Part 3 says why.
```

The table at lines 410–416. Add a third column:

```
| | 4% build | 8% build | 12% build |
|---|---|---|---|
| `shared_origin` pairs, as generated | 220 | 440 | 960 |
| fewest pairs one scenario keeps in train | 5 | 14 | <fewest_pairs_in_train> |
| training questions | 4,282 | 4,314 | <kept_train> |
| validation | 436 | 473 | <kept_val> |
| **exam (test.jsonl)** | **263** | **263 — byte-identical** | **263 — byte-identical** |
```

Lines 419–420. Replace

```
now holds 440 shared against 573 separate, 43 / 57. The numbers in the rest
```

with

```
held 440 shared against 573 separate, 43 / 57, at the 8% build; at the 12%
build it holds <origin_read_shared> shared against <origin_read_separate>
separate, <split>. The numbers in the rest
```

Line 730. Replace `(the section after this one takes it to twenty-four)` with `(the sections after this one take it to twenty-four, then to forty-eight)`.

Line 797. Replace `The pool is now twenty-four.` with `The pool was twenty-four after this change. The next section takes it to forty-eight.`

Before the `---` that precedes `## Small glossary` (line 833), after the paragraph `This page does not authorise that retrain. It records what the textbook now holds and why.`, add this section:

```
### What the 0907 run taught us

The retrain on the twenty-four-scenario textbook ran on the seventh of
September, so this page calls it 0907. It sat the exam and was refused.
Two deciders failed.

| Decider | Bar | 0907 result |
|---|---|---|
| 1. Every answer is valid JSON | 263 of 263 | **262 of 263** |
| 5a. False "shared" on the multi-workload probe | at most 1 of 19 | **2 of 19** |
| 5c. Pairs where both halves are right | at least 7 of 10 | **4 of 9** |

The other deciders were met. Beside the exam, the wide probe scored 19 of
30 pairs and the cousin probe scored 30 of 30. So the model read the origin
on the scenarios it had studied, and missed on the ones it had not.

The broken answer was on a node-disk-pressure decoy half with three
victims. Every cause in it was right. The shape was wrong: the model wrote
the second and third verdicts inside the first one and then wrote a second
summary. Across the exam and the wide probe, 4 of the 6 three-verdict node
decoy answers were broken the same way.

We measured why instead of guessing. Four things stood out.

- **Three-verdict decoys were rare in training.** 15 of the 24 trained
  scenarios had only 2 victims, and so did 6 of the 7 node-scoped ones. A
  node decoy with three verdicts could come from one scenario only, about 8
  rows in all. The training pile held 317 decoy rows with 2 verdicts, 74
  with 3, and 6 with 4.
- **The exam's reads use real kubectl layouts the training never showed.**
  The exam's node reads are a `Conditions:` table with `Taints:` under it.
  Its Deployment reads have a `Replicas:` line, a `Pods:` table and a
  `Last log:` line. Its registry read is a cluster-wide events summary. Its
  StorageClass read names the controller's readiness and the volumes bound
  in the last 20 minutes. The trained cousins used one-line labels instead,
  such as "Process table: exhausted".
- **The StorageClass read with a crashed controller scored 0 of 7 on all
  three models.** The trained cousin said the controller was running and
  the pool was retired. The exam says the controller is in CrashLoopBackOff
  and nothing has bound in 20 minutes. The model had never seen a crashed
  controller.
- **Capacity is not the limit.** The training loss over the last 50 steps
  averaged 0.0005. The model memorised the textbook. What it lacked was
  shapes, not room.

One more thing, about time rather than data: 16 threads and 32 threads took
the same wall time. Time scales with rows, about 8 seconds per example
pass.

What this change does about it:

- **Forty-eight scenarios, not twenty-four.** Twenty-four new ones, in five
  groups that copy the exam's five read layouts: node `Conditions:` tables,
  Deployment describes, cluster-wide events, StorageClass reads with a
  crashed or missing controller, and NetworkPolicy reads. Every kind of
  failure in the catalog still appears somewhere in the pool.
- **Every scenario has at least three victims.** Fifteen scenarios got a
  third one, so a decoy with three verdicts can now come from any scenario.
  A test fails if fewer than 40 of every 100 decoy rows carry three or more
  verdicts, or if the node-scoped ones come from fewer than 5 scenarios.
- **Eleven existing scenarios got an exam-layout variant**, so the older
  cousins also show the real layouts some of the time.
- **The shares moved to 12% each**, paid out of `attributed` again, and the
  textbook grew from 5,500 to 8,000 questions so that every scenario still
  keeps at least 12 pairs in train.
- **A cousin probe.** `kv-dataset --probe-cousins` writes one fresh pair per
  trained scenario, 48 pairs and 96 rows, every decoy half at full width.
  It asks whether the model reads the origin on what it studied. It decides
  nothing.

The exam did not move: 263 questions, the same checksum.

What the final retrain will tell us:

- **All six deciders pass:** the model ships. The wide and cousin probes are
  reported beside it, and a poor probe score does not stop it.
- **Decider 1 fails again on a three-verdict decoy:** the data now shows
  that shape often, so the fault is in the recipe, not in coverage. The
  next look is at the training, not the textbook.
- **Decider 5c fails and the wide probe is low on one group:** that group's
  layout still needs work, and the wide probe names the origin.
- **Decider 5c fails and the cousin probe is low:** the model does not read
  the origin even on scenarios it studied. That points at the recipe.
- **Decider 5c fails and both probes are high:** the exam's six origins are
  harder than their cousins. Read the pair-level rows before deciding
  anything.

This page does not authorise that retrain either. It records what the
textbook now holds and why.
```

- [ ] **Step 6: Check the docs**

Run: `cd /home/ubuntu/git/kubeagent-verdict && grep -n '5500' README.md docs/runbooks/train.md docs/design.md docs/how-training-works.md`
Expected: only history lines: the README sentence about the shipped weights, the runbook's negative-control paragraph if it names the size, `docs/how-training-works.md` line 408 (the 8% recipe as it was), and the new sentences that say "from 5500 to 8000" or "size 5500 on". No build command and no floor-test line may still say 5500.

Run: `cd /home/ubuntu/git/kubeagent-verdict && grep -n '<[a-z_]*>' README.md docs/design.md docs/how-training-works.md docs/runbooks/train.md | grep -v '<url>\|<PLACEHOLDER>\|<date>\|<ctx>\|<path>'`
Expected: no output. Every `<name>` from Step 1 was replaced by its number.

Run: `cd /home/ubuntu/git/kubeagent-verdict && grep -n 'twenty-four\|forty-eight' docs/how-training-works.md`
Expected: lines 730, 797 and the new section, all naming forty-eight as the current pool.

Run: `cd /home/ubuntu/git/kubeagent-verdict && git diff --stat`
Expected: exactly four files: `README.md`, `docs/design.md`, `docs/how-training-works.md`, `docs/runbooks/train.md`. `docs/model-card.md` is not in the list.

Read the new section once more, out loud if it helps. Every sentence is short. Every number says what it counts. No sentence promises a result the run has not produced.

Run: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python -m pytest tests -q`
Expected: all PASS. Docs do not move tests, but this is the last task, and the suite is the branch's exit check.

- [ ] **Step 7: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add README.md docs/runbooks/train.md docs/design.md docs/how-training-works.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com commit -s -m "docs: describe the final retrain's data and the 0907 lessons"
```

---

## Done when

- Twelve tasks are committed on `final-retrain-coverage`, every commit signed off by `imantaba <itn.taba@gmail.com>`, with no AI attribution anywhere.
- `.venv/bin/python -m pytest tests -q` passes and `.venv/bin/ruff check src tests` is clean at the branch tip.
- `propagation.trainable_scenarios()` returns 48 scenarios; every one has at least three victims and at least four origin variants (the eleven Task 4 touches carry five; the twenty-four new scenarios carry exactly four); the `test_propagation.py` structural suite and the pool tests pass.
- `test_every_exam_layout_has_a_trained_floor` passes: node 13, deployment 4, events 4, storageclass 6, networkpolicy 6 or more scenarios per exam layout.
- `generate.test_set()` is still 263 rows with the checksum the contamination test pins. Not one exam byte moved.
- At `--seed 17 --size 8000`: every trainable scenario keeps at least 12 shared-origin pairs in train; at least 40 of every 100 kept decoy rows carry three or more verdicts, and the node-scoped ones come from at least 5 scenarios; the shared answer is under 0.40 of the multi-workload rows; the evidence-overlap declaration matches what is measured.
- `kv-dataset --probe-wide` still writes 60 rows; `kv-dataset --probe-cousins` writes 96 rows, 48 twin pairs, no pair-key collision.
- The four docs from Task 12 say 8000, 10 / 12 / 12 and forty-eight where they state the recipe; `docs/model-card.md` is untouched.
- The whole-branch review on the most capable model leaves no Critical or Important finding open.
- Nothing trained, nothing exported, nothing written under `dist/`, nothing run on the training host, and the chaos harness untouched. This plan ends at the finishing menu.

## Not in this plan

- **Spec Section 3, steps 5–11.** They belong to the operator, on the training host, after the finishing menu: build the dataset at `--seed 17 --size 8000` and report the manifest counts; run the floor test there; encode every train row with the training tokenizer at 4096 and report that 0 rows would be dropped (if not, the fix is in the data, never in the length); report both and **wait for the user to say go**; then one retrain with the 0907 recipe into a dated adapter directory that refuses to overwrite; export to a dated `dist-retrain-<date>/`, never `dist/`; the exam, the wide probe and the cousin probe through `kv-eval` with an explicit endpoint; and the six-decider report in simple voice. No subagent runs `kv-train`, `kv-export` or the chaos harness. No task in this plan starts any of it.
- **Rejected in the spec:** a larger base model; only six close cousins; grounding the rationale on the read; a GPU run; any change to the exam, the wide probe, the deciders or a schema; any new dependency.
- **Parked from earlier work, and still parked:** the ruff pre-commit hook; a `--rescore` mode for the contamination check; the wording at `cases.py` line 520; a medium-confidence trained scenario; the training host's old backup and smoke directories; the wide probe's ambiguous row 4; the two differing wide-probe copies. None of them is touched here.
