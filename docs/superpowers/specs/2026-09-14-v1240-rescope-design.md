# Re-scope to kubeagent v1.24.0's local verdict contract — design

**Date:** 2026-09-14
**Branch:** `rescope-v1.24.0` (off `main` @ `ecfd67b`)
**Status:** approved in chat in seven sections; written here for review

## The decision, up front

kubeagent v1.24.0 changed what the model is asked to do. Our exam still
grades the old job. This slice does three things. It re-renders the
frozen exam under the new prompt shape. It replaces the old deciders with
three job scores that match the new prompt. And it runs the 0908 model
through `kv-eval` once. No retrain. No export. If 0908 passes, we publish.
If it fails, the model card says the model adds nothing under v1.24.0,
and nothing ships.

Three words this document leans on:

- **0908** is the model: the last retrain, dated 09-08, served as a GGUF
  file (the single-file model format Ollama loads) from `out/models/`.
- **`kv-eval`** is this project's eval command. It sends every exam
  prompt to a model endpoint, scores the replies with `score.py`, and
  prints a scoreboard. It writes only under `out/`.
- A **decider** is one scoreboard number with a pass bar. The model
  passes only if every decider passes. Today there are six; after this
  slice there are five, plus the three job scores.

And one word used three ways, so here is which is which: an **exam row**
is one of the 263 prompts; a **workload** is one scored unit inside a
prompt (a prompt holds one, two or three); a **reply row** is the one line
the model writes for a workload.

The eval must be able to fail 0908, and a model that returns nothing must
score 0 on all three jobs. An eval change that could not fail the model it
replaced is not a fix.

## Why this slice exists

Since v1.24.0, kubeagent's local verdict mode re-checks each candidate
cause against a fresh read before it calls the model. A workload whose
cause the rules settled renders as a `[rule, confirmed]` or
`[rule, unverified]` row in the report. The model does not choose that
row's cause. What the model still does is three things:

1. **Rule rows.** Echo the decided cause word for word, and write a
   rationale that does not deny what the fresh read found.
2. **Undecided rows.** Name a cause the evidence supports, or say
   `none_of_these`.
3. **Summary.** At most 4 lines, and they must agree with kubeagent's own
   shared-cause lines: never "separate reasons" when two decided rows share
   one cause, never "shared" when none do.

The 0908 model failed all three in 3 of 3 live calls. On 12 rule-decided
rows it echoed the cause on 4. It named invented causes on undecided rows.
Its summaries disagreed with the shared lines.

Our eval cannot see any of this. Its exam prompts carry the v1.23.0
candidate shape. Their decoy candidates are prose: free text picked from
a pool, with no object behind them, so no fresh read could ever refute
them. There are no fresh-read lines and no decided line. And decider 5
(paired shared-origin) grades a judgement kubeagent's rules now make for
it. Decider 5 is obsolete, and the exam grades a prompt kubeagent no
longer sends.

## What does not change

- **kubeagent.** Not one file. The golden (a prompt kubeagent itself
  wrote, kept as the byte-for-byte answer key) and the rules fixture (a
  file of inputs and the strings kubeagent's rules produce for them) are
  captured in a throwaway worktree — a second checkout of kubeagent in a
  temporary directory — that is removed afterwards. `go.mod` is untouched.
- **The exam's identities.** 263 rows (253 frozen plus 10 decoy rows), the
  same 13 case types with the same counts, the same seeds (the fixed
  random-number starts that make every generated row come out the same
  each run), the same scenario names and `Example.group` keys. No row
  moves, so the contamination test stays valid as it is.
- **The model.** 0908 was the last retrain. It is not retrained and not
  re-exported. It sits the new exam through `kv-eval` only.
- **The five deciders that survive.** Contract validity, decoy rate, length
  gap, overconfidence, suggestion echo — same meaning, same bars.
- **The training set's use.** It is re-rendered by the same code path so
  the generator has one shape, but no training runs on it.
- **Training host rules.** Nothing runs on the training host in this slice.

## Global constraints

These rules bind every task on this branch. The plan copies them word
for word, and every reviewer checks against them.

- **kubeagent is not changed.** Not one file, and `go.mod` stays as it
  is. The golden and the fixture are captured in a throwaway worktree
  that is removed afterwards.
- **No training, no export.** `kv-train` and `kv-export` are not run.
  Nothing writes under `dist/`. 0908 sits the exam through `kv-eval`
  only, and `kv-eval` writes only under `out/`.
- **Nothing runs on the training host.**
- **`kv-eval` is always given `--endpoint`.** The run has no
  `ANTHROPIC_API_KEY` in the shell, and no key value is ever printed.
- **Every commit is `git commit -s`** under the repository's own git
  identity, the one every commit on `main` already carries. No AI
  attribution anywhere: not in commits, code, docs or the model card.
- **Never `git add -A`.** Name each file.
- **A commit message never cites a path under `docs/testing/`.**
- **No pin moves by a test flag.** The golden and the fixture are copied
  once from the section 7 capture. After that they change only by the
  re-pin steps in `PIN.md`.
- **No real identifier in any tracked file.** No real cluster, host,
  node, namespace, address, kubeconfig path or context name. Fixtures use
  `worker-1`, `worker-2`, `registry.invalid`, `<ADDRESS>` and the names
  in `names.py`.
- **Simple voice in every doc line.** Short sentences, everyday words,
  the decision first, numbers explained.
- **TDD.** The failing test first, then the code. `pytest` and `ruff`
  pass on every commit, from the project's `.venv`.
- **The promise rule.** A comment, doc line or reason string that
  promises what the code does not keep is a defect. Close the gap or
  narrow the claim. Retraction is not deletion.
- **The eval must be able to fail 0908.** A "returns nothing" bot reads 0
  on all three jobs.

**Build order.** The plan sequences the work like this, because each
step pins the next: (1) `dataset/objects.py`; (2) the section 7 capture
in the throwaway worktree, which produces the golden and the fixture in
that shape; (3) `dataset/rules.py` against the fixture; (4) `contract.py`
and the system prompt against the golden; (5) `dataset/cases.py`;
(6) `evals/score.py`; (7) the smoke set; (8) the docs; (9) the run.

## Approach chosen

Three options were weighed in chat.

| Option | Cost | What you learn | Downside |
|---|---|---|---|
| **1. Faithful re-render** (chosen) | Port kubeagent's three rule tables; graft one real object per story; re-render | Whether 0908 does the three jobs on the prompt kubeagent actually sends | The stories were written without objects; grafting one takes judgement per entry |
| 2. Hand-written new exam | Write 263 new prompts by hand | The same, on prompts we chose | Identities move; the contamination test and every banked score are void |
| 3. Score the live pairs only | Use the 3 real calls | Almost nothing; 3 prompts cannot fail a model with confidence | No pass bar is meaningful at n = 3 |

Option 1's first premise — that the stories already imply their objects
— failed on inspection. 9 of 28 catalog entries never flag a workload at
all, and most of the rest name a fault kubeagent's rules do not check. The fix
chosen was **graft one object per story** (section 3), then **mix three
fresh-state endings on decoy nodes** so job 1 has enough rows to grade
(option A in chat).

The frozen exam is re-rendered. The three real live prompt/reply pairs
become a tracked, redacted smoke set that prints but decides nothing. The
golden is re-captured from kubeagent v1.24.0.

## Section 1 — the pipeline

```
declare  →  derive  →  render  →  exam rows  →  kv-eval  →  score.py
objects     rules       prompt      + meta        replay      jobs 1–3
```

- **Declare.** Each catalog entry and each propagation scenario declares
  the objects its story contains: kind, name, the reason the scan gave, and
  the state a fresh read finds.
- **Derive.** A pure Python port of kubeagent's three rule tables turns the
  declared objects into candidates, fresh-read outcomes, a decided line,
  and the shared-cause label. The port is pinned byte-for-byte to
  v1.24.0 by a golden fixture kubeagent itself produced.
- **Render.** The v1.24.0 prompt: the candidate block with fresh-read
  lines and the decided line, the v1.24.0 system prompt.
- **Exam rows.** Same 263 identities and seeds. Each row's meta now carries
  per workload: `job` (1 or 2), `decided`, `decided_cause`,
  `decided_outcome`, `decided_evidence`, `expected_cause`; per prompt: the
  job-3 `label` (`shared`, `separate`, `none`) and `decoy_by_workload`.
- **Replay.** `kv-eval` sends `messages[0]` and `messages[1]` exactly as
  today.
- **Score.** `score.py` reads only meta and the reply. It never re-derives
  anything.

**The job is derived, never declared.** A row is job 1 because the rules
decided it, not because someone wrote `job: 1`. That keeps the exam honest
if the rules change: re-pin the port and the jobs follow.

## Section 2 — components

### `dataset/objects.py` (new)

A frozen `Object`:

| Field | Values |
|---|---|
| `kind` | `node`, `pvc`, `registry` |
| `name` | node name, PVC name, or registry host |
| `scan_reason` | node: `NotReady`, `no kubelet lease`, `kubelet not heartbeating`; pvc: one of kubeagent's six (`ProvisioningFailed`, `FailedBinding`, `MissingStorageClass`, `NoMatchingPV`, `PVSelectorMismatch`, `ProvisionerNotResponding`); registry: the count of workloads failing to pull |
| `placement` | node: `on` or `off` (a pod of this workload is or is not scheduled on it); pvc: `mounted` or `unmounted`; registry: unused |
| `fresh` | per kind — node: Ready `True` / `False` / `Unknown` / `missing`, or a failed-read message, or `not_read`; pvc: phase `Bound` / `Pending` / `Lost` / other, plus the storage class and volume the read prints, or a failed read; registry: the pull-event literal (from kubeagent's three closed lists) or `none`, and whether the events read hit the wrong pod |
| `intent` | `cause` or `decoy` — documentation only; the scorer never reads it |

Three pure transforms return a new object or tuple:

- `refute(obj)` — the refuted ending for its kind: node Ready `True` with
  the `NotReady` reason; pvc phase `Bound`; registry an image-error literal.
- `unverify(obj, how)` — an unverified ending: node `lease` (reason
  `no kubelet lease`, Ready `True`) or `read_failed`; pvc `read_failed`;
  registry `auth` (an auth literal) or `no_event`.
- `drop(obj)` — the object is removed from the declaration.

Any value outside the tables above is a `ValueError` at build time, naming
the entry and the object.

### Declarations

- `CatalogEntry.objects: tuple[Object, ...] = ()`.
- `Propagation.origin_object` with two fresh states, broken and healthy.
- `Victim.on_origin: bool` and `Victim.objects`.

### `dataset/rules.py` (new, pure)

- `attribute(objects, pod, ns) → candidates`, in kubeagent's order: node,
  then pvc, then registry. Every candidate gets one of kubeagent's three
  scan verdicts: `attributed`, `ruled_out` or `outranked`; there is no
  fourth. A node whose placement is `off` is
  `ruled out — no pod of this workload is scheduled on it`. The first
  `on` node is `attributed — pod <pod> is scheduled on it`; any later one
  is `outranked — <first cause> is the stronger cause`. A PVC that is not
  mounted is `ruled out — not mounted by this workload's pods`; the first
  mounted one is attributed with `pod <pod> mounts it`. A registry
  candidate needs two or more workloads failing to pull from the host;
  fewer is ruled out with `only workload failing to pull from this host;
  threshold is 2`.
- `decide(candidates) → Result`, kubeagent's `hypothesis.Decide`: walk the
  non-ruled-out candidates in order; the first confirmed wins; else the
  first unverified; else undecided. An unverified decision **is** a
  decision. The per-kind outcomes and their exact evidence strings are
  pinned by the fixture (section 7); the branches are listed in section 6.
- `shared(results) → lines`, kubeagent's `hypothesis.Shared`: count rows
  that are decided **and** confirmed. Fewer than 2 → no lines. Two or
  more in one group → one `<n> workloads share one upstream cause: <text>`
  line per group, capped at 4. Two or more and no group shared → the
  one line `no shared cause among the <n> workloads confirmed by rules`.
  The group key and its text follow kubeagent's `group()`:
  - a node groups on `node/<name>`; the text is its cause;
  - a registry groups on `registry/<host>`; the text is its cause;
  - a PVC whose scan reason is `ProvisionerNotResponding` or
    `MissingStorageClass`, and whose read shows a storage class made
    only of `a-z`, `0-9`, `.` and `-`, groups on
    `storageclass/<class>/<reason>`; the text is
    `storage class <class> (<reason>)`;
  - every other PVC groups on `pvc/<ns>/<name>`; the text is its cause.

  The storage-class group is what makes `storage-provisioner-down`'s
  three PVCs one group. The strings are pinned by the fixture.
- `label(lines) → shared | separate | none`: the job-3 label an exam row
  carries in meta. A "share one upstream cause" line → `shared`; the "no
  shared cause" line → `separate`; no lines → `none`.
- `read_text(obj) → (label, content)`: the read kubeagent's gather would
  have made for this object, in the gather's exact format. A node read is
  `node <name>: unschedulable=<bool>` then one `condition` line per
  condition and one `taint` line per taint. A PVC read is
  `pvc <ns>/<name>: phase=<phase> storageClass=<class> volume=<volume>`.
  A failed read is `read failed: <message>`.

### `contract.py` and `contract/system_prompt.txt`

- `Candidate` gains `fresh_read_outcome` and `fresh_read_evidence`
  (empty on a ruled-out candidate).
- `Workload` gains `decided`, `decided_cause`, `decided_outcome`.
- `render_candidates` prints, per workload, the heading
  `- <ns>/<name> (<Kind>) [confidence: <c>]:`, then per candidate
  `    considered <cause>: <verdict> — <reason>` with `_` rendered as a
  space, then after each non-ruled-out candidate
  `      fresh read: <outcome> — <evidence>`, at most 8 candidates followed
  by `    [truncated by kubeagent]`, and on a decided workload
  `    decided by rules: <cause> — <outcome>`. The decided line may name a
  candidate past the cap; that is what kubeagent does.
- The system prompt becomes v1.24.0's. The inserted paragraph is:

  > A workload marked "decided by rules" has its cause fixed by
  > kubeagent's own fresh read: return that cause verbatim and use the
  > rationale to explain it. A candidate marked refuted is not supported;
  > a workload whose every candidate is refuted is yours to name.

  `contract.SYSTEM_PROMPT` and the file stay equal; the existing test
  pins that.

### `dataset/cases.py`

Every builder becomes a transform on the entry's declared objects. The
`_candidates()` helper and the prose decoy pool go.

| Case type | Transform |
|---|---|
| `attributed`, `injection`, `truncated` | objects as declared; `truncated` adds 9 unmounted PVC decoys named from a new tuple `PAD_PVCS` in `names.py` (`aux-0` … `aux-8`; never drawn by the rng, so no identity moves) so the list runs past the 8-cap and the marker prints. kubeagent sorts PVC candidates by name and prints nodes first, so a decided PVC or registry lands past the cap and the decided line names a candidate the model cannot see; a decided node stays in the shown eight |
| `none_of_these` | `refute(cause)`, plus the contradiction read; expected `none_of_these` |
| `own_cause`, `empty_candidates` | `drop(cause)`; the fixed sentence for every row becomes "the candidate list shown did not include this cause" |
| `wrong_attribution` | `drop(cause)`; the decoy is attributed at scan and refuted at read; expected: the own cause |
| `positional_probe` | a decoy of an earlier kind prints first |
| `misattribution_probe` | decoy placement `off`, so it is ruled out |
| `contradiction_probe` | the decoy is left **unverified** (`unverify`, node `lease` where the decoy is a node; otherwise the kind's own unverified ending) and the events read points hard at the own cause — the main job-1 trap |
| `shared_origin_probe` (broken half) | two or more victims confirmed on one object |
| `shared_origin_decoy_probe` (healthy half) | the origin's healthy state: 0 confirmed |
| `multi`, `multi_misattribution_probe` | per workload, as above |

The table names 14 builders. `multi` is training-only and never in the
exam; the exam's 13 case types are the other 13, with the counts
`tests/test_generate.py` pins today.

`cause` in this table means the entry's cause object. Only one entry has
one: `worker-containerd-stop`. The other 18 producing entries declare a
decoy object only (the 17 in section 3's decoy table, plus
`node-cordon-diskfull` with its lease-lapse node), so on them the
transforms read like this:

- `none_of_these`: the decoy is refuted at read, and the single
  contradiction read replaces the entry's reads. The own cause is not
  derivable from the prompt, so the expected cause is `none_of_these`.
- `own_cause`: the decoy is shown and refuted; the own cause is absent
  from the menu. The rationale carries the fixed sentence "the candidate
  list shown did not include this cause". Expected: the own cause.
- `empty_candidates`: every object dropped, so the menu is empty.
  Expected: the own cause.
- `wrong_attribution`: the decoy is attributed at scan and refuted at
  read. Expected: the own cause.

On `worker-containerd-stop`, `refute(cause)` refutes its node object and
`drop(cause)` models a refused nodes list; its decoy PVC stays as
declared.

Confidence stays as the catalog declares it; the graft check already
corrected the one entry (`probe-failure`) where it disagreed with
kubeagent's prefix rule.

### Five facts about kubeagent's checker that bind these builders

1. `Annotate` puts **every** declared down node on **every** workload in
   the prompt, ruled out where the workload's pod is not on it. So a
   declaration is per prompt, placement is per workload, and a
   multi-workload prompt shows the other workload's node as a ruled-out
   line. A test pins this (section 6).
2. A PVC's verdict comes from its declared phase, never from prose.
3. `Init:ImagePullBackOff` and `Init:ErrImagePull` never get a registry
   candidate: the registry pass keys on the exact issue string.
4. `worker-containerd-stop`'s `contradiction_probe` cannot flip the node
   read. That would refute the node and send the row to job 2. So its
   contradiction lives in the events read, and the node read stays
   broken.
5. The `losers` text on `networkpolicy-deny-all` and
   `coredns-corefile-broken` is stale; it is a doc-only fix.

### `evals/score.py`

`job1`, `job2`, `job3` (section 4), the `decoy_by_workload` gate, and the
removal of decider 5.

### Golden, fixture, smoke

Re-captured from kubeagent v1.24.0 in a throwaway worktree (section 7).
The smoke set lives in a new tracked `contract/smoke/`.

## Section 3 — the graft table

Every entry and scenario gets one declaration. Names, seeds, row counts
and identities do not move. Where the story supports a real cause, it
gets one (job 1). Otherwise it gets a decoy the fresh read refutes or
leaves unverified — always one of kubeagent's own shapes.

### Catalog entry with a real cause (1)

| Key | Cause object | Decoy object |
|---|---|---|
| `worker-containerd-stop` | node, `NotReady` at scan, Ready `False` at fresh read → confirmed | PVC `ProvisioningFailed`, outranked at scan; `Bound` at read → refuted on the "menu is wrong" types, drawn per row from the PVC endings on the option-A types |

Its `own_cause` and `empty_candidates` rows `drop(cause)`: that models a
refused nodes list, a real blind spot. Both rows are job 2.

### Catalog entries with a decoy only (17)

| Key | Decoy object |
|---|---|
| `memory-limit-oomkill` | node, `NotReady` |
| `deployment-bad-image-tag` | registry, 2 or more workloads failing to pull |
| `networkpolicy-deny-all` (catalog) | node, `NotReady` |
| `coredns-corefile-broken` | node, `NotReady` |
| `oversized-job-unschedulable` | PVC, class `fast-ssd`, volume `pv-0821` |
| `crashloop-pod` | node, `NotReady` |
| `probe-failure` | node, `NotReady` |
| `container-start-error` | node, `NotReady` |
| `create-container-config-error` | PVC, class `fast-ssd`, volume `pv-0442` |
| `init-crashloop` | node, `NotReady` |
| `init-config-error` | node, `NotReady` |
| `init-errimagepull` | node, `NotReady` (a registry candidate is impossible: fact 3) |
| `init-imagepullbackoff` | node, `NotReady` (same) |
| `init-oomkilled` | node, `NotReady` |
| `restart-loop` | node, `NotReady` |
| `volume-attach-error` | PVC, class `fast-ssd`, volume `pv-0821` |
| `volume-mount-error` | PVC, same shape (a node decoy would contradict the entry's own "the node is fine" prose) |

### Catalog entries with nothing (10)

Nine never flag a workload, so they produce 0 exam rows and get no
object: `control-plane-docker-stop`, `control-plane-cert-expiry`,
`loadbalancer-no-provider`, `namespace-deletion`,
`configmap-aws-key-leak`, `certmanager-bad-issuer-ref`,
`flux-gitrepo-dns-failure`, `no-fault-healthy-readyz`,
`coredns-servfail-template`.

`node-cordon-diskfull` flags a workload (15 exam rows: 13 of its own and
2 workloads inside `multi_misattribution_probe` prompts), but its fault —
cordon plus `DiskPressure` — is not one of kubeagent's three node reasons.
It gets a lease-lapse node: reason `no kubelet lease`, Ready `True` at
read → decided, unverified. A full disk does make the kubelet's lease
lapse, so the story holds.

### Propagation scenarios (6)

| Key | Objects | Job 3 label (broken / healthy) |
|---|---|---|
| `coredns-down` | node ×3, one per victim (own `on`, others `off`), all refuted | none / none |
| `node-not-ready` | node ×1 shared; `NotReady` → confirmed when broken, Ready `True` → refuted when healthy | shared / none |
| `storage-provisioner-down` | PVC ×3, scan reason `ProvisionerNotResponding`, one class `standard`, so the three form one storage-class group; `Pending` when broken, `Bound` when healthy | shared / none |
| `registry-unreachable` | registry ×1 on all 3 victims (after the rewrite below); connection literal when broken, image literal when healthy | shared / none |
| `node-disk-pressure` | node ×1; victim 1 `off` (ruled out), victims 2 and 3 `on` and refuted | none / none |
| `networkpolicy-deny-all` (propagation) | node ×2, one per victim, refuted | none / none |

Two rewrites the table needs, both accepted in chat:

- `node-not-ready` victim 1: five fields move from a Pending shape to a
  `RunContainerError` shape, because a Pending pod cannot sit on the
  shared node.
- `registry-unreachable` victim 3: issue changes from
  `Init:ImagePullBackOff` to `ImagePullBackOff`, so all three victims can
  get the registry candidate and the prose count "3 workloads" stays true.

### Option A — three endings on decoy nodes

With every decoy refuted, job 1 had 10 rows, all from one entry. That is
too few to grade, and a bot that never echoes anything would lose almost
nothing. So on the "here is the menu, answer it" case types —
`attributed`, `injection`, `truncated`, `positional_probe`,
`multi_misattribution_probe` — and on the scenario decoys, each decoy
node's fresh state is drawn per row from the row's own seed:

| Ending | Declared | Fresh-read line | Decided? |
|---|---|---|---|
| refuted | reason `NotReady`, Ready `True` | `refuted — Ready condition is True now` | no |
| unverified, lease | reason `no kubelet lease`, Ready `True` | `unverified — Ready condition is True, but the kubelet lease was not re-read` | yes, unverified |
| unverified, read failed | describe read failed | `unverified — fresh read failed: <message>` | yes, unverified |

PVC and registry decoys get their kind's own endings by the same draw:
PVC `Bound` (refuted) or read failed (unverified); registry image literal
(refuted), auth literal or no event (unverified).

The "menu is wrong" types — `none_of_these`, `own_cause`,
`empty_candidates`, `wrong_attribution`, `misattribution_probe` — keep
their designed endings. `contradiction_probe` is always unverified (the
job-1 trap on all 19 entries).

**Stated plainly, for the model card:** on an unverified decoy row the
rules fix a node the story says is not the cause. That is v1.24.0's own
`[rule, unverified]` behaviour, not our invention. The exam grades
whether the model follows the contract, not whether the contract found
the truth.

### Population after the graft

Roughly, over the 263 rows: job 1 about 70 workload answers across 19
entries; job 2 about 210; job 3 exactly 39 prompts (19
`multi_misattribution_probe`, 10 `shared_origin_probe`, 10
`shared_origin_decoy_probe`) labelled 5 `shared`, 0 `separate`, 34
`none`. The 10 shared-origin probes come from the 6 scenarios as today:
one full-width prompt per scenario, plus one two-victim prompt for each
of the 4 scenarios with 3 or more victims (`coredns-down`,
`storage-provisioner-down`, `registry-unreachable`,
`node-disk-pressure`). The decoy probes mirror the same 10 draws with
the same seeds. The `none` set includes prompts with two or three
decided-unverified rows, which catches "two decided rows, so say shared".
The plan pins the exact numbers after the first render.

**The `separate` label stays at 0 in the exam.** It is pinned three
ways: a rules unit test (two confirmed rows on different objects produce
the "no shared cause" line), a scorer unit test (a `separate` row is
scored as section 4 says), and one training-only prompt: a `multi` prompt of two
`worker-containerd-stop` draws in different namespaces on different
nodes, both confirmed, label `separate`. Rewriting `coredns-down` to
carry two real objects was rejected: it would move a frozen identity.

## Section 4 — scoring and pass bars

The scorer is three row-level functions over meta and the reply.

### Job 1 — rule rows

**Bar: mean ≥ 0.9.** One score per decided workload. It is 1 only if all
four conditions hold:

1. the reply has a row for that workload;
2. its `cause` equals `decided_cause` byte for byte;
3. its `rationale` is non-blank after the same cap and clean-up
   kubeagent applies — 512 runes (Go's word for one Unicode character),
   control characters stripped, trimmed
   — mirroring the third gate in kubeagent's `ruleRow`
   (`internal/investigate/local.go:448`), so a rationale kubeagent would
   render as "no answer" earns nothing;
4. no denial phrase fires.

The denial table is closed and small. Matching is case-insensitive on
word boundaries, and negation-aware: a hit with "not", "no" or "never"
within 24 characters before it is not a denial — the rule
`_shared_claim_signal` already uses.

| Kind | Phrases (fire on every outcome) |
|---|---|
| node | "rather than the node", "not the node", "node is fine", "node is healthy", "healthy node" |
| registry | "rather than the registry", "not the registry", "registry is reachable" |
| pvc | "rather than the claim", "not the claim", "claim is fine", "is bound" |

One evidence-keyed rule, forced by option A: "is ready" is a node denial
unless the row's `decided_evidence` itself says "Ready condition is True"
(the lease rows), where it is agreement. A read-failed row's evidence
says "fresh read failed: …", so "is ready" stays a denial there.

On unverified rows only, the overclaim words also fire: "verified",
"confirm", "confirms", "confirmed" — word-bounded, so "unverified" does
not self-collide, and negation-aware.

Missing row or missing reply = 0.

**Known ceiling, stated in the model card.** The decided cause is printed
in the prompt. A regex plus a filler rationale scores near 1.0 on job 1.
Job 1 measures contract-following; job 2 carries the diagnostic weight. A
high job 1 alone is not evidence of skill. Real LLMs still failed 8 of 12
live rows.

### Job 2 — undecided rows

**Bar: mean ≥ 0.7.** One score per undecided workload. The expected
answer is the story's own cause or `none_of_these`.

- Under v1.24.0 the menu carries only kind-shaped candidates, so the own
  cause is never in it. Every undecided row whose `expected_cause` is
  the story's own cause is graded the way `own_cause` is today, whatever
  its case type: `own_cause`, `empty_candidates`, `wrong_attribution`,
  and any row whose decoy was refuted at read (an `attributed` row with
  the refuted ending, for one). The rule: all of the entry's
  `own_cause_keywords` appear in the reply's cause, matched as substrings
  after lowercasing both sides.
- `none_of_these` scores 1 only on rows whose meta says
  `expected_cause = none_of_these` (the `none_of_these` case, 19 rows).
  On any other undecided row it scores 0. An always-`none_of_these` bot
  lands near 0.1.
- A wrong named cause = 0. Missing row or reply = 0.

`keyword_derivable_n` keeps printing, now over all job-2 rows, so a reader can see how many answers were copyable from the
finding text.

### Job 3 — summary

**Bar: mean ≥ 0.9, gating.** Population: every prompt with two or more
flagged workloads — the 39 above. Label from meta.

| Label | Scores 1 when the summary … |
|---|---|
| `shared` | claims a shared cause and does not deny one |
| `separate` | denies a shared cause and does not claim one |
| `none` | is non-blank and does not claim one |

Both signals or neither → 0, not excluded. Blank or missing → 0. This is
the fix to the old `false_shared` pattern, which dropped ambiguous rows
from the denominator. The reading reuses `_shared_claim_signal`,
`SHARED_CLAIM_PHRASES`, `INDEPENDENCE_PHRASES`, `NEGATORS` and
`NEGATION_WINDOW`.

The bar gates because 39 prompts clears the "20 or more" rule. The
per-label counts print beside it. A "never say shared" bot scores 34 of
39 = 0.87 and fails; "always shared" fails harder.

### The five deciders

| Decider | Change |
|---|---|
| Contract validity | none; 263 of 263 |
| Decoy rate | the per-row `answered` gate (`score.py:348-354`) becomes per decoy-bearing workload via `decoy_by_workload`; 39 of 115 decoy rows could dodge the gate before |
| Length gap | re-measured on the new kind-shaped strings; `LENGTH_GAP_TOLERANCE` and `LENGTH_GAP_FLOOR` re-derived, and the decider must read above the floor — it is not dropped |
| Overconfidence | none; `own_cause` and `empty_candidates` survive |
| Suggestion echo | none; the finding block's suggestion line is separate from the candidate menu |

Decider 5 goes: `paired_contrast`, `_shared_verdict`, the
`paired_shared_origin` block, the `separate_reasons_rate` and
`false_shared_rate` columns. `cause_accuracy` stays as a column and
decides nothing.

### Baseline pins

- A reply of `""` on every row → job 1, job 2 and job 3 each read `0.0`
  with their full `n`, never `None`.
- The regex echo bot → job 1 near 1.0, job 2 at 0.
- The "never say shared" bot → job 3 = 34 of 39.

### What passes

All three job bars and all five deciders. Anything less is a fail, and a
fail is reported as a fail.

## Section 5 — errors, pins and docs

### Errors in the generator

A declaration the rules cannot read is a build error, never a silent
drop. `rules.py` raises `ValueError` naming the entry key and the object
when the kind, a node's scan reason, a PVC's reason or phase, or a
registry literal is outside the closed tables. A prompt with more than 8
reads is a build error. `generate` stops at the first error and writes
nothing, so a half-rendered exam cannot land.

### Errors in the eval run

| What | Handling |
|---|---|
| Empty, unparseable, or workload-less reply | 0 on every job (section 4) |
| Transport error — refused connection, timeout, HTTP 5xx | `kv-eval` aborts with the error and no scoreboard, as today (`evals/client.py` wraps nothing); a partial scoreboard could be read as a pass |
| Row meta missing `job`, `decided_cause` or `label` | `KeyError` at load, before any model call: the exam and the scorer disagree |

### Port drift

`dataset/rules.py` is pinned to kubeagent v1.24.0 by
`tests/fixtures/rules_golden.json`: declared inputs and the strings
kubeagent's own `Decide` and `Shared` produced for them. If that test
fails, kubeagent changed its rules and the port is stale.
`contract/PIN.md` gets the re-pin procedure (section 7) and a trigger
list: a change to `verdictSystemPrompt`, `renderCandidates`,
`hypothesis.Decide`, `hypothesis.Shared`, `maxCandidatesPerWorkload`, or
any of the gather's three read formats means a re-pin.

### Pins that move once, on this branch

- `contract/golden/user_message.txt` and `input.json` — re-captured from
  v1.24.0.
- `contract/system_prompt.txt` and `contract.SYSTEM_PROMPT` together.
- `FROZEN_253_SHA256` and `EVAL_SET_SHA256` in
  `tests/test_shared_origin_training.py` — re-pinned to the re-rendered
  exam, then frozen again.
- `tests/test_generate.py`'s 13 case counts do **not** change; that test
  is the proof no identity moved. The contamination test is untouched.

### Code that goes

`paired_contrast`, `_shared_verdict`, the two decider-5 constants and the
`paired_shared_origin` block in `score.py`; the decider-5 asserts in
`tests/test_paired_contrast.py`, `tests/test_probe_wide.py` and
`tests/test_probe_cousins.py`; `_candidates()` and the prose decoy pool
in `cases.py`; five comment lines in `cases.py` and `generate.py` that
describe the old shape.

### Docs that change (simple voice, every line)

| File | Change |
|---|---|
| `README.md` | one line under the scoreboard naming the three jobs; a forward pointer in the historical section, whose numbers stay |
| `contract/PIN.md` | the v1.24.0 tag and commit, the re-pin procedure, the trigger list |
| `docs/design.md` | six lines: what the rules decide, what the model still does |
| `docs/how-training-works.md` | one line on the re-render; decider item 5 removed and the rest renumbered; the 13-slice table gains a job column |
| `docs/runbooks/train.md` | "Six things" becomes "Five things"; the old decider bullet is replaced with the job 1 / 2 / 3 bars |
| `docs/model-card.md` | untouched now; after the run it gains one dated section (below) |
| `entries_slugs.py` | the stale `losers` text on `networkpolicy-deny-all` and `coredns-corefile-broken`, corrected to what the rules say |
| `contract/smoke/README.md` | new (section 7) |

The model-card section is written after the run. It carries the three
job scores, pass or fail in its first line, and these four limits:

1. Job 1 has a regex ceiling: a bot that copies the decided line scores
   about 1.0.
2. On option-A rows the rules fix a node the story says is not the
   cause, and the exam grades the echo, not the story.
3. The `separate` label is 0 in the exam. Only a scorer test and one
   training-only prompt pin it.
4. 0908 was trained on the v1.23.0 prompt shape. It never saw a
   fresh-read or decided line in training.

**The promise rule.** Any comment, doc line or reason string that still
promises the old candidate menu, the prose decoys or decider 5 is either
updated or narrowed on this branch. The whole-branch review greps for
`paired`, `decider 5`, `five deciders`, `six things` and `contrast`.

## Section 6 — testing

Every task is TDD: failing test first. No test needs a model or a
network; `evaluate` takes `chat_fn`, so tests pass fake bots.

### New test files

- `tests/test_rules.py` — the port against the fixture: every input must
  produce byte-for-byte the strings kubeagent produced. Plus one test per
  branch:
  - node: Ready `False` → confirmed "Ready condition is False now";
    `Unknown` → confirmed "Ready condition is Unknown now"; missing →
    confirmed "the node has no Ready condition"; `True` with scan reason
    `no kubelet lease` or `kubelet not heartbeating` (kubeagent treats
    both as a heartbeat reason) → unverified "Ready condition is True,
    but the kubelet lease
    was not re-read"; `True` otherwise → refuted "Ready condition is True
    now"; read failed → unverified "fresh read failed: <message>"; never
    read → unverified "not re-read: the read budget was spent first";
  - pvc: `Bound` → refuted "phase is Bound now"; `Pending` → confirmed
    "phase is still Pending"; `Lost` → confirmed "phase is Lost"; other →
    unverified "phase is not one kubeagent expects";
  - registry: connection literal → confirmed; auth literal → unverified;
    image literal → refuted; no event → unverified; wrong pod →
    unverified;
  - `shared()`: fewer than 2 confirmed → `none`; 2 on one node →
    `shared`; 2 confirmed on different keys → `separate`; 3 PVCs with
    `ProvisionerNotResponding` on one class → one `storage class` line;
    the same 3 with `ProvisioningFailed` → `separate`; groups sorted by
    count then key.
- `tests/test_objects.py` — `refute`, `unverify` and `drop` are pure and
  the input is frozen; a bad kind, reason, phase or literal raises
  `ValueError` naming the entry and object.
- `tests/test_smoke.py` — the 3 pairs parse, carry none of the banned
  shapes, and their scores print without gating.

### Existing test files that change

- `tests/test_score.py` — job 1: each of the four conditions alone flips
  the score
  (wrong echo, blank rationale after cap, kind denial, negated denial
  passes, "is ready" passes only on rows whose evidence says Ready is
  True, overclaim fails only on unverified rows, missing row). Job 2:
  exact match, keyword match on `own_cause`, `none_of_these` only on
  marked rows, the always-`none_of_these` bot near 0.1. Job 3: all three
  labels against all five summary shapes (claim, deny, both, neither,
  blank). The three baseline bots. The `decoy_by_workload` gate: a reply
  that answers only the non-decoy workloads counts as unanswered for the
  decoy rate.
- `tests/test_generate.py` — the 13 case counts stay. New asserts: every
  row carries the meta keys; every prompt has at most 8 reads and fits
  64 KiB; every declared down node appears on every workload of its
  prompt (fact 1); the job counts, pinned as exact numbers the plan fills
  in after the first render (job 3: 39 prompts, 5 / 0 / 34).
- `tests/test_contract.py` — `render_candidates`: fresh-read line only
  after non-ruled-out candidates, the decided line, the 8-cap plus
  marker, a decided line past the cap. System prompt equals the file.
- `tests/test_golden.py` — byte-equal to the re-captured file.
- `tests/test_shared_origin_training.py` — the two hashes re-pinned; the
  one training-only `separate` prompt asserted present.
- `tests/test_paired_contrast.py`, `tests/test_probe_wide.py`,
  `tests/test_probe_cousins.py` — decider-5 asserts removed; the decoy
  checks they also carry stay.
- Length gap — the constants asserted against the new strings, and the
  decider must read above the floor.

### Branch-level checks

`pytest` green, `ruff` clean, the promise grep from section 5, and the
secret grep over every new file. CI runs the same suite and does not
change.

## Section 7 — the smoke set and the golden re-capture

### Golden re-capture

Done once, on this branch, in a throwaway worktree:

1. In the kubeagent checkout: `git worktree add <scratchpad>/ka-v1.24.0
   v1.24.0`.
2. Copy the capture test into `internal/investigate/` of that worktree
   only.
3. `go test ./internal/investigate -run TestKVCapture` writes three files
   into the scratchpad: `user_message.txt` (the prompt kubeagent renders
   for the golden input), `input.json` (that input in kubeagent-verdict's
   shape), and `rules_golden.json` (declared inputs covering every branch
   in section 6, with the strings `hypothesis.Decide` and `Shared`
   produced — including the edge cases: an outranked node "not re-read:
   the read budget was spent first", a decided line past the 8-cap, and
   a storage-class group).
4. Copy the three files into `contract/golden/` and `tests/fixtures/`;
   record the tag and commit hash in `PIN.md`.
5. Remove the worktree. kubeagent is not touched: no commit, no file on
   `main`, `go.mod` unchanged.

The capture test never lands in kubeagent. It lives in kubeagent-verdict
as `contract/capture/kv_capture_test.go.txt` with the five steps above in
its header, so a re-pin is a copy, not a rewrite.

### Smoke set

Three real prompt/reply pairs from the live run — calls 02, 03 and 04
(05 was a deliberate 404 test and is excluded). They go to a new tracked
`contract/smoke/`: `02-request.json`, `02-response.json`, the same for
03 and 04, and a short README. The run's `meta.json` and
`request-headers.txt` stay gitignored; they name the endpoint.

Redaction before anything is tracked:

| Was | Becomes |
|---|---|
| the two kind node names (the live run's kind cluster was called `kubeagent-live`, so its nodes carry that prefix) | `worker-1`, `worker-2` |
| the container bridge address and any pod IP | `<ADDRESS>` |
| the three `.invalid` URLs | unchanged (reserved test domain) |
| the five hashed pod names | unchanged |

`tests/test_smoke.py` greps the six files for dotted quads, any
`scheme://host` other than the three `.invalid` hosts, `kubeconfig`,
`/home/`, `@` and the old cluster name `kubeagent-live`, and fails on any
hit.

What the smoke set does: the scorer reads each prompt's
`decided by rules:` lines to find its rule rows (the kind is the cause's
first word — kubeagent's causes start `node `, `PVC ` or `registry ` —
and the outcome is the word after the dash) and scores the real reply the same way it
scores an exam row. `kv-eval` prints the three per-pair scores under a
`smoke (not gated)` heading. Today's numbers: 12 rule rows, echoed on 4.
This shows the scorer reads kubeagent's real output the same way it
reads a generated prompt; the golden shows the generated prompt has that
shape. Nothing in the smoke set moves a pass bar.

The README says, in five lines: where the pairs came from (a kubeagent
v1.24.0 run against a throwaway kind cluster with injected faults), what
was redacted, that the model was 0908, and that the set decides nothing.

## The run

After the branch is green and reviewed:

1. Start Ollama, record its PID under `out/`. No `ANTHROPIC_API_KEY` in
   the shell. The 0908 GGUF lives under gitignored `out/models/`.
2. `kv-eval --endpoint http://localhost:11434/v1 --model <0908 tag>`,
   output under `out/`.
3. Read the scoreboard: three jobs, five deciders, the smoke lines.
4. Write the model-card section (section 5). Pass or fail, in the first
   line.

**Pass:** all three bars and all five deciders. Then, after the project
owner says yes, publish kubeagent-verdict.

**Fail:** the model card says the model adds nothing under v1.24.0. No
version bump, no tag, no release. The eval, the port, the golden and the
smoke set still land: they are the project's contract with v1.24.0
whatever the model does.

## Risks, stated plainly

- **The graft is judgement.** Each of the 19 producing entries got an
  object a person chose. The checker refuted three drafts before the
  table settled. A wrong choice shows up as a row the rules decide in a
  way the story contradicts; the reads-≤8 test and the fixture catch the
  mechanical kind, not the narrative kind.
- **Job 1 can be gamed by a regex.** Stated in the model card, pinned by
  the echo-bot test. Job 2 is where skill shows.
- **0908 was trained on the v1.23.0 shape.** It has never seen a
  fresh-read line or a decided line. A fail is the likely outcome; the
  eval exists to say so with numbers.
- **`separate` is 0 in the exam.** The path is pinned only by a unit
  test and one training-only prompt. An exam row would need a moved
  identity, which we refuse.
- **The port can drift.** The fixture test catches it; the PIN procedure
  says what to do.

## Rejected and out of scope

- Rewriting `coredns-down` to carry two real objects, for a `separate`
  exam row — moves an identity.
- A retrain on the re-rendered training set — 0908 was the last retrain.
- Any change to kubeagent — a capture test in a throwaway worktree is the
  whole of the contact.
- Running the chaos harness — nothing here needs a cluster.
