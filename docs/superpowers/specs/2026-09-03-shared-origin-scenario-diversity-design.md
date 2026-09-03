# Shared-origin scenario diversity — design

**Date:** 2026-09-03
**Branch:** `shared-origin-scenario-diversity` (off `main` @ `ee2980e`)
**Status:** approved, ready for an implementation plan

## Why this slice exists

The 0902 retrain is scored and refused. It meets four of the six release deciders
and fails two, and the paired shared-origin decider — the one this whole line of
work exists to move — reads **0.1 of 10** against a bar of **≥ 0.7**, inside the
band `docs/runbooks/train.md` defines as *no evidence of reading*.

That number is not a mystery any more. It was diagnosed this session with a 2×2
that separates the two variables the failure could turn on, and two ablations on
the evidence line itself. The findings are recorded in
`docs/how-training-works.md` under *Why it failed, measured rather than guessed*;
this section restates the parts that drive the design.

### It is the scenario, not the rendering

|                    | 4 **training** scenarios | 6 **unseen** eval scenarios |
| ------------------ | ------------------------ | --------------------------- |
| exam rendering     | **0.5 paired (8)**       | **0.1 paired (10)** ← release run |
| training rendering | —                        | **0.0833 paired (12)**      |

Holding the scenario set fixed and swapping the rendering moves the score from
0.1 to 0.083 — nothing. Holding the rendering fixed and swapping the scenario set
moves it from 0.1 to 0.5 — five-fold. The variable is which origins the model was
trained on.

### The in-distribution 0.5 is two read and two constant

A pair scores only when both halves are answered correctly, so a scenario that
emits a constant verdict scores **zero** pairs, not half. The 0.5 decomposes
cleanly:

| scenario | discriminating line (broken vs healthy) | result |
| --- | --- | --- |
| `shared-configmap-deleted` | `Error from server (NotFound): the ConfigMap app-settings does not exist` vs `Name: app-settings, 7 keys` | PASS, PASS |
| `shared-dependency-scaled-to-zero` | `Replicas: 0 … Pods: none` vs `Replicas: 4 … 4 Running` | PASS, PASS |
| `internal-ca-expired` | `notAfter: expired 2h ago` vs `notAfter: 288 days remaining` | FAIL, FAIL — answers "separate" on both halves |
| `kube-proxy-degraded` | `last Service route sync: 11m ago (peer nodes: 4s ago)` vs `3s ago (peer nodes: 4s ago)` | FAIL, FAIL — answers "shared" on both halves |

The two that pass are separated by a lexical state token. The two that fail are
separated by a quantity.

This matters more than it first looks. `shared_origin` and `shared_origin_decoy`
hold **equal shares** by design (`generate.py:57`, pinned by
`tests/test_shared_origin_training_pair.py`), so every scenario is taught under
both answers in equal number. A constant answer is therefore a *chance-level*
strategy in training and should not survive it. That two scenarios collapsed to
one anyway means the model did not find a usable feature in those reads at all.

### The two ablations

Run on the same model, on the four failing pairs only:

- **UNIT** — units made consistent, no lexical hint added (`notAfter: 0 days
  remaining`; `last Service route sync: 660s ago (peer nodes: 4s ago)`):
  **0 of 4.** Nothing moved. It is not a unit-conversion failure.
- **LEX** — the quantity replaced by a bald state token (`notAfter: expired` /
  `notAfter: valid`; `sync: stale` / `sync: current`): **1 of 4.** Only
  `internal-ca-expired`'s three-workload pair flipped. `kube-proxy-degraded`
  answers "shared" whatever that line says.

So on three of four failing pairs the discriminating line is not weakly read; it
is **not read at all**.

### Why the shortcut is cheap

Measured on the 0902 corpus: 440 shared-origin rows across train and val, 436
distinct assistant answers and 440 distinct user prompts — so nothing is
memorised verbatim. But `shared_origin` draws on **four** cause templates over
521 graded verdicts, three of them covering 74%; the scenario is legible from
roughly 39 of a prompt's 40 lines, and the deciding line is the fortieth. Four
scenarios at ~110 rows each makes "recognise the scenario, emit its usual
template" fit the training data nearly as well as the rule, for far less.

## What this slice changes

Three changes, one branch. Each is stated with what it is measured to fix and
what it is not.

### ① The trainable pool grows from 4 scenarios to 20

Sixteen new `Propagation` literals in `src/kubeagent_verdict/dataset/propagation.py`,
appended to `_TRAINING_SCENARIOS`.

`CASE_MIX` is **frozen** (`generate.py:57`). `shared_origin` stays at 4% and
`shared_origin_decoy` at 4%, so at seed 17 / size 5500 the same 220 + 220 rows
spread over 20 scenarios instead of 4: **11 + 11 rows per scenario, down from
55 + 55**. The rule is still presented 440 times; no single scenario is presented
often enough for the lookup to be the cheaper fit.

Freezing the mix is deliberate. Raising the shared-origin share would improve
per-scenario repetition but would move every other slice's row count, and the
retrain would then change two variables at once — the opposite of the discipline
that let the 0902 run rule out rendering.

`generate.py:143` already varies the rendered width per row
(`victims = 2 + (i // len(train_scen)) % (len(p.victims) - 1)`). At 20 scenarios
`i // 20` runs 0..10 across each scenario's 11 rows, so widths still cycle. No
change needed there.

### ② `origin_variants` — the discriminating read varies inside a scenario

Today `_render_shared_origin` (`src/kubeagent_verdict/dataset/cases.py:538`)
renders one literal broken blob and one literal healthy blob per scenario,
byte-identical across every row that scenario produces. A model can only learn
two literal strings per scenario from that; it cannot learn the relation the
strings stand for.

New optional field on `Propagation`:

```python
origin_variants: tuple[tuple[str, str], ...] = ()   # (broken content, healthy content)
```

**The legacy pair stays and becomes variant 0.** `origin_read[1]` and
`healthy_origin_content` remain populated on every scenario and must equal
`origin_variants[0]`. Two call sites read them without going through the draw
— `_render_shared_origin`'s fallback when a scenario declares no variants
(`cases.py:537`) and `multi`'s healthy-origin branch (`cases.py:800`) — and
making the legacy pair one of the drawn variants is what keeps those two
showing content the model has actually seen, with no edit to either. It is
asserted, not left to authoring care.

**The label does not move.** `origin_read[0]` stays a single string. That is the
seam almost every consumer keys on — `origin_read_label` in `Example.meta`,
`multi`'s negative-case pairing (`cases.py:788-806`), the decoy-probe label test
(`tests/test_shared_origin_decoy_probe.py:242-256`), the healthy-content map in
`tests/test_shared_origin_training.py:274-283`. Keeping it a single string is
what confines this change to one draw site.

**The pair stays a minimal contrast, by construction.** `generate.py:156-159`
draws **one salt and spends it twice**: `random.Random(salt)` is built separately
for each half, so both halves replay an identical RNG stream. The variant is
drawn from the passed-in `rng` immediately after `_propagation_names`
(`cases.py:526`), which both halves call identically and which is the last RNG
consumer before the `healthy` branch. Both twins therefore draw the *same*
variant, exactly the way they already draw the same names. No plumbing is needed
and `test_a_pair_reads_the_same_things_in_the_same_order` keeps passing.

**The exam does not move.** The draw happens **only when `origin_variants` is
non-empty**. The eval six declare none, so they consume the same RNG as today.
Separately and more strongly: the exam's rows are minted through
`_entry_rng("shared-origin", p.key)` (`generate.py:379`), a per-scenario keyed
generator with no dependence on the training generator's stream, so adding
trainable scenarios cannot perturb it even in principle. Both facts are
belt-and-braces for the same guarantee; the guarantee itself is pinned by hash
(see *Verification*).

### ③ `origin_state` — the discriminator must carry a word, not only a number

New field on `Propagation`:

```python
origin_state: tuple[str, str] = ("", "")   # (broken token, healthy token)
```

Enforced over the **trainable pool only** (see *What ③ deliberately does not
cover*):

- `origin_state[0]` appears in every variant's broken content and in **none** of
  that scenario's healthy contents;
- `origin_state[1]` appears in every variant's healthy content and in **none** of
  that scenario's broken contents;
- neither token is empty, and neither is purely numeric.

This **fails the pool as it stands today**, which is the point of writing it as a
test rather than as guidance. `kube-proxy-degraded`'s two contents differ only in
`11m` versus `3s` — there is no state word to name — and that scenario answered
"shared" on all four halves of both its pairs. It is rewritten as part of this
change.

An eval change that could not fail the model it replaced is not a fix; the same
standard applies to an invariant. This one fails something real on the day it
lands.

#### What ③ deliberately does not cover

**It is necessary and demonstrably not sufficient.** `internal-ca-expired`
already satisfies it — `expired` in the broken content, `remaining` in the
healthy one, neither in the other — and it still failed at eval. The LEX
ablation, which additionally removed the quantity, flipped one of its two pairs
and moved nothing else. So "a legible state token exists" is the half of the
condition that can be checked mechanically, and it is being checked; "the
discriminator is not buried in a numeric phrase" is authoring guidance and is
recorded in the module docstring **labelled as guidance**, because no honest test
expresses it.

**It is not enforced on the eval six.** Adding the field to `all_scenarios()`
would require editing them, and the exam is frozen this slice. `origin_state`
defaults to `("", "")` and the assertion runs over `trainable_scenarios()` only.
The eval six are asked, not taught; the constraint is about what training
presents.

## The sixteen new scenarios

The spec fixes each scenario's **identity and properties**. The prose — the exact
`shared_cause` wording, the victim reads, the variant contents — is written at
implementation time against the rules in *Authoring constraints* below, and the
tests are the gate. An implementer who hits a collision may rename a key; the
disjointness tests decide.

The *victim issue kinds* column is the set a scenario draws from, not its victim
count: every scenario still carries 2-4 victims, and two victims may share a
kind — `cluster-autoscaler-at-capacity` is the case where they all do, because
nothing else happens to a pod no node can take.

Radius budget: the four existing scenarios are cluster ×2, node ×1, namespace ×1.
The sixteen new ones are cluster ×7, node ×5, namespace ×4, giving a pool of
**9 cluster / 6 node / 5 namespace** — near the eval six's own spread, so blast
radius predicts nothing.

### Cluster-scoped (7 new)

| key | origin | victim issue kinds |
| --- | --- | --- |
| `image-pull-secret-expired` | the shared pull secret's credential is rejected by the registry | `ErrImagePull`, `ImagePullBackOff`, `Init:ErrImagePull` |
| `shared-secret-key-renamed` | a key was renamed in a Secret every workload references | `CreateContainerConfigError`, `CrashLoopBackOff` |
| `cluster-autoscaler-at-capacity` | the autoscaler is at its configured maximum, so no node can be added | `Unschedulable` |
| `sidecar-injector-broken` | the mutating injector is adding a sidecar that cannot start | `Init:CrashLoopBackOff`, `CrashLoopBackOff`, `ProbeFailure` |
| `shared-base-image-tag-moved` | a mutable base-image tag now resolves to a broken build | `CrashLoopBackOff`, `ContainerStartError` |
| `shared-pvc-multi-attach` | a ReadWriteOnce volume is attached to one node and every other pod waits | `VolumeAttachError`, `VolumeMountError` |
| `cni-ip-pool-exhausted` | the cluster CNI has no pod addresses left to allocate | `ContainerStartError`, `Unschedulable` |

### Node-scoped (5 new)

| key | origin | victim issue kinds |
| --- | --- | --- |
| `csi-node-driver-crashed` | the CSI node driver on `{node}` is down, so nothing mounts there | `VolumeMountError`, `CrashLoopBackOff` |
| `node-pid-pressure` | `{node}` has exhausted its process-ID limit | `ContainerStartError`, `RestartLoop` |
| `node-runtime-restarting` | the container runtime on `{node}` is flapping | `RestartLoop`, `ProbeFailure` |
| `node-clock-skew` | `{node}`'s clock is far enough ahead that issued credentials are rejected there | `CrashLoopBackOff`, `ProbeFailure` |
| `node-conntrack-full` | `{node}`'s connection-tracking table is full and new connections are dropped | `ProbeFailure`, `CrashLoopBackOff` |

### Namespace-scoped (4 new)

| key | origin | victim issue kinds |
| --- | --- | --- |
| `namespace-limitrange-lowered` | a LimitRange default in `{ns}` now sets a memory limit below what its pods use | `OOMKilled`, `Init:OOMKilled` |
| `namespace-egress-proxy-down` | the egress proxy Deployment in `{ns}` has no ready replicas | `ProbeFailure`, `CrashLoopBackOff` |
| `namespace-shared-pvc-full` | the shared PersistentVolumeClaim in `{ns}` is at capacity and writes fail | `CrashLoopBackOff`, `ProbeFailure` |
| `namespace-migration-lock-held` | a shared migration lock in `{ns}` is held, so every init container waits and times out | `Init:CrashLoopBackOff`, `CrashLoopBackOff` |

Chosen so that across the full pool all **16** `vocab.ISSUE_KINDS` are exercised.
The existing ten scenarios cover twelve; `Init:CrashLoopBackOff`,
`Init:ErrImagePull`, `Init:OOMKilled` and `OOMKilled` are the four this set adds.
That is asserted by test.

Two propagation families stay deliberately absent, unchanged from the module
docstring's existing note: a blocking admission webhook and an exhausted
ResourceQuota. Both stop the pod being created, so they surface as `FailedCreate`
on the workload — a kind `vocab.ISSUE_KINDS` does not admit. `sidecar-injector-broken`
is not a counter-example to that: its pod *is* created and its injected sidecar
then fails, which is an ordinary pod-level kind. `namespace-limitrange-lowered`
is likewise not `ResourceQuota` — a LimitRange sets a low limit on a pod that
was admitted, and the pod then OOMKills.

### Semantic adjacency, stated rather than hidden

Three of the sixteen sit near an eval scenario in mechanism:
`image-pull-secret-expired` near `registry-unreachable`,
`csi-node-driver-crashed` near `storage-provisioner-down`, and
`node-pid-pressure` near `node-disk-pressure`. The disjointness tests are on the
key and on the graded answer string, not on semantics, so these pass — and a
training pool that teaches a family in order to be tested on a held-out member is
the intended shape, not a leak.

It still weakens the strongest reading of a pass. The commitment this slice makes
instead: the exam already scores **per pair**, so when the next run is read, the
six eval scenarios are reported split into those with a near neighbour in
training and those without. "It generalised to adjacent origins only" is a
finding that must be visible in the write-up, not one that has to be dug for.

## Authoring constraints

Every trainable scenario, existing and new, must satisfy all of the following.
Those marked **(new)** are invariants this slice adds.

| # | constraint | enforced by |
| --- | --- | --- |
| 1 | key matches `^[a-z0-9]+(-[a-z0-9]+)*$` | `test_trainable_scenarios_obey_every_rule_the_eval_table_obeys` |
| 2 | key disjoint from every eval key | `test_no_trainable_origin_is_an_eval_origin` |
| 3 | `shared_cause` / `distractor_cause` disjoint from every eval one | `test_no_trainable_scenario_reuses_an_eval_answer_string` |
| 4 | `shared_cause` / `distractor_cause` unique **across the trainable pool** | **(new)** |
| 5 | `local_cause` unique within the scenario | existing |
| 6 | `local_cause` unique **across the trainable pool** | **(new)** |
| 7 | 2–4 victims, each `issue` in `vocab.ISSUE_KINDS` | existing |
| 8 | `pass_confidence` varies within the scenario | **(new)** — currently guidance in the docstring only |
| 9 | `blast_radius` and `scope_field` mutually consistent | **(new)** |
| 10 | `healthy_read_content` set on any victim whose own read asserts the origin is broken | **(new)**, best-effort — see below |
| 11 | `healthy_origin_content` non-empty | existing |
| 12 | ≥ 4 `origin_variants`, and `origin_variants[0]` equals `(origin_read[1], healthy_origin_content)` | **(new)** |
| 13 | `origin_state` obeys ③ | **(new)** |
| 14 | no banned identifier shape anywhere in the scenario's text | existing, extended to cover `origin_variants` |
| 15 | the pool exercises all 16 `vocab.ISSUE_KINDS` | **(new)** |

Constraint 8 is currently only asserted for the eval six's *purpose* in prose. It
becomes a test here because with sixteen new scenarios written by different
hands, "vary the confidence" as guidance will not hold, and a scenario whose
victims all carry one grade reopens the confidence-copy shortcut the module
docstring says is closed.

Constraint 10 cannot be fully mechanised — deciding whether a victim's read
"asserts the origin is broken" is a judgment about English. What **is**
mechanised: if a scenario declares `origin_state`, no victim read may contain the
broken token unless that victim also declares a `healthy_read_content` that does
not. That catches the specific failure the constraint exists to prevent — a decoy
row showing a healthy origin next to victim evidence contradicting it — for the
cases where the token is the give-away. The residual is authoring judgment and is
labelled as such.

Constraint 14 is a genuine extension, not a restatement:
`test_no_trainable_scenario_text_carries_a_banned_identifier_shape` builds its
blob from `origin_read[1]` and `healthy_origin_content` and would not see a
banned shape that appears only inside a variant.

## Files touched

| file | change |
| --- | --- |
| `src/kubeagent_verdict/dataset/propagation.py` | two new `Propagation` fields; sixteen new literals; `kube-proxy-degraded` rewritten to satisfy ③; `origin_variants` added to all four existing trainable scenarios; module docstring updated |
| `src/kubeagent_verdict/dataset/cases.py` | the variant draw in `_render_shared_origin`, ~4 lines, plus its comment |
| `tests/test_shared_origin_training.py` | constraints 4, 6, 8, 9, 10, 12, 13, 15; constraint 14 extended; and the exam-identity hash pin, beside the existing `test_the_eval_set_is_two_hundred_and_sixty_three_rows` under *the eval must not move* |
| `tests/test_propagation.py` | the eval six declare no variants and no `origin_state` |
| `tests/test_shared_origin_training_pair.py` | untouched: a regression gate only. The two pair-variant invariants are written into `tests/test_shared_origin_training.py` instead |
| `docs/how-training-works.md` | what changed and why, in the existing voice |
| `docs/model-card.md` | untouched — it describes released weights, and nothing is released here |

`contract/golden/` does **not** move: `tests/test_golden.py` pins the prompt
contract against real kubeagent bytes, not the generated dataset.

## Verification

All of it runs before a retrain is even requested. A retrain is ~17.5 hours on
the training host and is not authorised by this document.

1. **Suite green** — the 330 existing tests plus the new invariants.
2. **The exam has not moved.** `generate.test_set()` is 263 rows with sha256
   `e8cbb549289ebaf07ba817dd3d32fdf70724c0ae80410eb47d2228a3b22b49de`, over
   `json.dumps([to_row(e) for e in test_set()], sort_keys=True, ensure_ascii=False)`.
   Captured on `main` @ `ee2980e` and re-confirmed on this branch before any
   edit. It is pinned beside the existing row-count assertion
   (`tests/test_shared_origin_training.py:308`), which already guards the
   count but not the contents — 263 rows of different text would pass it. If
   the hash moves, the comparison to 0830 / 0901 / 0902 is void and the change
   is wrong.
3. **The dataset rebuilds as designed** at seed 17 / size 5500: 20 distinct
   origins present in the emitted rows, 11 `shared_origin` and 11
   `shared_origin_decoy` per scenario, contamination still 0 of 263.
4. **The diagnosis statistic has flattened.** Re-run the corpus measurement
   that found the shortcut — the distribution of graded shared-origin causes
   over the emitted `shared_origin` rows. It reads "three templates cover 74%"
   today. The bar: **no single cause template above 12%, and the top three
   together below 30%.** Twenty scenarios weighted by victim count put the
   uniform value near 5%, so those numbers leave real headroom while still
   failing anything close to today's shape. This is the check that says the
   change did what it was designed to do rather than merely compiling.
5. **Variants are rendered, not merely declared.** Count distinct origin-read
   contents per scenario in the rows generated at seed 17 / size 5500:
   **at least 3 distinct broken contents per trainable scenario.** A scenario
   draws 11 times from 4-plus variants, so 4 of 4 would be a coin-flip
   assertion; 3 is deterministic at a fixed seed and still fails a field that
   renders one variant. A test that counts declarations rather than renders
   would notice neither.

Only after all five does the question of authorising a retrain arise.

## What this slice does not claim

- **It does not claim the model will pass.** Diversity attacks the 0.1 → 0.5 gap,
  which is generalisation, and that gap is measured. ③ attacks the 0.5 cap, and
  its evidence is one ablation flipping one pair — a hypothesis with support, not
  a measurement. A next run landing between 0.5 and 0.7 reads as "diversity
  worked, legibility partly worked", not as "close enough".
- **It does not change the exam**, so it cannot make the score move by making the
  question easier. That is the reason for check 2, and for pinning a hash rather
  than asserting an intention.
- **It does not touch `CASE_MIX`**, so any regression on another slice in the next
  run is not attributable to a curriculum rebalance.
- **It ships no model and authorises no training run.** The 0902 weights remain
  refused, `dist-v2-superseded/` still holds the only released artifact, and
  nothing here is published.
