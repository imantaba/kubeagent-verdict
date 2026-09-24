# Job-2 generator fix — design

**Date:** 2026-09-24
**Branch:** `spec-wrong-attribution-generator` (cut off `main` @ `d931109`)
**Status:** approved in five sections; written up for review

## What this is

Job 2 asks the model to judge a workload that kubeagent's rules could not
decide. The generator that builds job-2 rows has two faults:

1. It builds pairs of prompts that are **the same bytes with opposite
   answers**.
2. It builds prompts that **kubeagent could never send** — wrong header,
   reads kubeagent never makes, reads kubeagent always makes left out.

This spec fixes the job-2 builders so every prompt looks like one kubeagent
could send, and every answer follows from its own prompt. Then we retrain
and set a new baseline.

It does **not** move a bar. It does not tune anything toward a passing
number. A miss after the retrain is reported, not fixed by editing the
exam.

## Why

### Same prompt, opposite answer

The grader spec (`2026-09-23-exam-grader-fix-design.md`, "What this does
not fix") measured it:

- `none_of_these_case` and `wrong_attribution` build **byte-identical
  prompts for 27 of 28 catalogue entries**. One answers `none_of_these`.
  The other answers the workload's own cause.
- In training that pair is 1,315 of 6,377 rows (20.6%), split 689 to 626.
- The model picked the more frequent label and used it everywhere:
  `none_of_these` 18 of 19, `wrong_attribution` 0 of 19.
- It spilled over. `misattribution_probe` is a different case, and the
  model still answered `none_of_these` on 17 of its 19 rows.

No model can learn a rule from a coin flip. This part is the main defect.

### Prompts kubeagent could never send

Measured on 2026-09-24 against kubeagent v1.24.0 (the pinned contract):

- **The header is set by hand.** The builders print
  `[confidence: …]` from `_confidence(e)`, a per-entry flag. kubeagent
  prints it from the attributed candidate's cause. Over the 19 trainable
  entries, the two disagree for 4 entries in the refuted shape (table in
  section 1).
- **`misattribution_probe` has a header on 19 of 19 rows.** No candidate
  there is attributed, so kubeagent would print no header.
- **`multi` has no header on any block.** kubeagent would print one on
  every block: over `out/dataset-0923`, that is 2,127 of 2,127 blocks
  (95.4% high, 4.6% medium).
- **Ruled-out rows carry a describe read.** kubeagent never describes a
  ruled-out candidate. `misattribution_probe` shows one anyway.
- **The previous-log read is missing.** kubeagent reads the previous
  log of every crash-family container. No job-2 prompt has that read.
- **The `log cause:` line is doubled** for 3 entries. The prompt says
  `log cause: log cause: bad command or entrypoint`.
- **Rationales cite evidence the prompt does not hold.** Example: the
  coredns `wrong_attribution` exam row says "the previous log classifies
  as a configuration parse error". The prompt has no log read.

## What kubeagent sends

All paths are in the kubeagent repository at the pinned tag. kubeagent is
read-only for this work.

| Fact | Where |
|---|---|
| Header rule: cause starts `node ` → high, `PVC ` → high, `registry ` → medium, else no header | `internal/confidence/confidence.go:36-47` (`ForRootCause`) |
| The header prints for any non-empty value, `high` included | `internal/investigate/prime.go:58-64` (`writeTraceHeading`) |
| Rules decide: skip ruled-out candidates; first confirmed wins, else first unverified; all refuted → undecided, the model judges | `internal/hypothesis/hypothesis.go:62-82` (`Decide`) |
| Reads per workload, in order: events of the first finding's pod, a describe per node or PVC candidate that is **not ruled out**, then a previous-log read per crash-family finding | `internal/investigate/gather.go:44-157` (`gatherEvidence`) |
| Crash family is exactly `CrashLoopBackOff`, `ContainerStartError`, `OOMKilled` | `internal/investigate/gather.go:195-197` (`crashFamily`) |
| Log read label: `log causes <ns>/<pod> container <container>` (container not quoted) | `internal/investigate/gather.go:153` |
| Log read content, four arms | `internal/investigate/reader.go:473-487` (`logCauseResult`) |
| Cause strings `bad command or entrypoint` and `configuration parse/validation error` | `internal/logscan/logscan.go:32`, `:62` |
| RestartLoop evidence quotes the container: `container %q, %d restarts, …` | `internal/diagnose/restartloop.go:44` |
| Read budget: 8 | `internal/investigate/investigate.go:22` (`maxToolCalls`) |

The four arms of the log read, verbatim (`%q` quotes the container):

| When | Content |
|---|---|
| refused | `reading the previous log of <ns>/<pod> was refused: this identity lacks the pods/log get permission` |
| no previous instance | `no previous-instance log for <ns>/<pod> container "<c>" (nothing was refused; the container may not have restarted)` |
| log has no known pattern | `the previous log of <ns>/<pod> container "<c>" has no classifiable output` |
| log matches a pattern | `log cause: <cause>` |

The refused arm is not used by this spec.

### Two product shapes for an undecided workload

Measured over all 19 trainable entries:

| | **refuted** | **ruled out** |
|---|---|---|
| What happened | one candidate attributed; a fresh read refutes it | every candidate ruled out |
| Attributed candidates | exactly 1 (every entry) | 0 (every entry) |
| Header | by rule | none |
| `fresh read:` line | yes | none |
| Describe reads | yes (the attributed candidate is read) | none |
| Decided line | none | none |

`worker-containerd-stop` has 2 candidates in the refuted shape; one is
attributed. Neither shape is decided, so both are job 2.

## Design

### 1. One rule for the header

Add `render.header_for(candidates) -> str`:

- It is a port of `ForRootCause`, applied to the one attributed
  candidate's cause.
- No attributed candidate → `""` (no header).
- Two or more attributed candidates → `ValueError`. kubeagent's trace has
  at most one winner, so two is a generator bug.

It lives in `render.py` so `cases.py` and `render.render_workload` share
one copy.

What the rule changes against today's `_confidence(e)`, refuted shape:

| Entry | Today | By rule | Why |
|---|---|---|---|
| `deployment-bad-image-tag` | high | medium | registry cause |
| `networkpolicy-deny-all` | medium | high | node cause |
| `probe-failure` | medium | high | node cause |
| `restart-loop` | medium | high | node cause |

The other 15 entries keep their value.

`_workload` keeps its hand-passed `confidence=` parameter. The job-1 and
shared-origin builders still use it; they are out of scope.

### 2. One builder for undecided job-2 rows

Add one private builder:

```python
_undecided_example(e, n, rng, *, case, shape, evidence)
```

- `shape` is `"refuted"` or `"ruled_out"`.
- `evidence` is `"clear"` or `"thin"`.
- `case` names the example and its meta. It never changes the prompt.

What each shape renders:

| | refuted | ruled_out |
|---|---|---|
| Menu | `_refuted_menu` | `_ruled_out_menu` |
| Header | `header_for(menu)` | none (by the same rule) |
| `fresh read:` line | yes | none |
| Object reads | `object_reads(menu)` | none |
| Previous-log read | crash-family entries (section 3) | crash-family entries (section 3) |
| Decided line | none | none |

Rules for the builder:

- **No shuffle.** kubeagent prints candidates in trace order. The answer is
  never on the menu in these rows, so position gives nothing away.
- **Reads in product order:** object reads first, then the log read.
- **The prompt depends only on (entry, names, shape, evidence).** Never on
  `case`.
- **The invariant this buys:** the same prompt always has the same expected
  cause and the same expected confidence.

The case builders become thin wrappers:

| Case | Shape | Evidence | Gold answer |
|---|---|---|---|
| `wrong_attribution` | refuted | clear | own cause at `_confidence(e)` |
| `own_cause` | ruled_out | clear | own cause at `_confidence(e)` |
| `none_of_these` | both, alternating | thin | `none_of_these` at `low` |
| `misattribution_probe` (eval only) | ruled_out | clear | own cause at `_confidence(e)` |

`own_cause` and `misattribution_probe` now build the same prompt for the
same entry and names, with the same cause and confidence. Their
rationales differ, and rationales are not graded. That is allowed by the
invariant.

`evidence="thin"` is allowed only for the entries in `THIN_ENTRIES`, a
hard-coded tuple in `cases.py`:

```python
THIN_ENTRIES = ("crashloop-pod", "coredns-corefile-broken",
                "init-crashloop", "restart-loop")
```

Any other entry raises. In these four, the finding does not name the
cause by itself and nothing else in the prompt gives it away. A thin row of
any other entry would teach "abstain" on a prompt that holds the answer.
`volume-mount-error` is the one other entry that could qualify; it is
recorded as a future option, not added.

**A known consequence.** A ruled-out row for an entry outside the crash
family has an **empty evidence section**. kubeagent would still show the
per-workload events read there. That read is missing from every job-2
builder today; adding it is Spec 3.

### 3. The evidence: clear and thin

One helper builds the previous-log read, and only for crash-family
entries. It is a table keyed by entry, not a guess from the issue text:

| Entry | Issue | Clear row | Thin row |
|---|---|---|---|
| `crashloop-pod` | CrashLoopBackOff | `log cause: bad command or entrypoint` | no-classifiable-output line |
| `coredns-corefile-broken` | CrashLoopBackOff | `log cause: configuration parse/validation error` | no-classifiable-output line |
| `memory-limit-oomkill` | OOMKilled | no-classifiable-output line | — (not thin) |
| `container-start-error` | ContainerStartError | no-previous-instance line | — (not thin) |
| `worker-containerd-stop` | ContainerStartError | no-previous-instance line | — (not thin) |
| `init-crashloop` | Init:CrashLoopBackOff | no log read | no log read |
| `restart-loop` | RestartLoop | no log read | no log read |

- The label is `log causes <n.ns>/<n.pod> container <container>`, with
  `<container>` the finding's container. That is `coredns` for
  `coredns-corefile-broken`, whose finding pins it, and `n.container` for
  the other four.
- `init-crashloop` and `restart-loop` are not crash family in kubeagent, so
  they get no log read in either version.
- A test asserts the table's keys are exactly the trainable entries whose
  issue is crash family. A new crash-family entry fails the suite until it
  gets a row.

The finding's own `log cause:` line:

- **Clear row:** kept.
- **Thin row:** dropped (`_finding(..., with_log_cause=False)`). This is a
  real product shape: a scan run without `--logs`.

So every thin entry's clear and thin prompts differ:

| Entry | What separates clear from thin |
|---|---|
| `crashloop-pod` | the finding's `log cause:` line and the log read's content |
| `coredns-corefile-broken` | the log read's content (its finding has no `log cause:` line) |
| `init-crashloop` | the finding's `log cause:` line |
| `restart-loop` | the finding's `log cause:` line |

The neutral log lines appear in clear rows as well as thin ones
(`memory-limit-oomkill`, the two ContainerStartError entries). So a neutral
line is not, by itself, a sign to abstain.

**Two catalogue fixes.** They also move job-1 rows, and that is intended:

- Strip the doubled `log cause: ` prefix from the `log_cause` field of
  `crashloop-pod`, `init-crashloop` and `restart-loop`. The renderer adds
  the prefix once (`src/kubeagent_verdict/contract.py:229`).
- Quote the container in `restart-loop`'s evidence
  (`entries_kinds.py`, about line 329): `container "{container}", …`, as
  kubeagent prints it.

### 4. The answers

**Thin rows** answer `none_of_these` at `low`. The rationale is fixed, one
per shape:

| Shape | Rationale |
|---|---|
| refuted | `A fresh read refutes the attributed cause, and no read names another.` |
| ruled_out | `Every candidate was ruled out, and no read names a cause.` |

The summary stays as it is today:

```
{ns}/{name} is failing, but the evidence rules out the listed causes.
A closer look at the workload is needed.
```

**Clear rows** answer the entry's own cause at `_confidence(e)`. That
changes `own_cause` and `empty_candidates`, which answer a flat `medium`
today. Each case keeps its own rationale suffix:

| Case | Rationale |
|---|---|
| `wrong_attribution` | `e.rationale` + ` The deterministic pass attributed a different cause, but the evidence supports this one.` |
| `own_cause` | `e.rationale` + ` The candidate list shown did not include this cause.` |
| `misattribution_probe` | `e.rationale` |

### 5. The case mix

| Case | Now | New |
|---|---|---|
| `none_of_these` | 11 | 4 |
| `own_cause` | 10 | 13 |
| `wrong_attribution` | 10 | 14 |

The three cases keep their combined 31%. The mix still sums to 100.

At `--size 8000`, before training rows that share a group with an exam
row are dropped:

- `none_of_these`: 320 rows = 80 per thin entry = 40 per shape.
- `own_cause` 1,040 + `wrong_attribution` 1,120 = about 114 clear rows per
  entry.
- For a thin entry, per shape: about 55 clear ruled-out rows and about 59
  clear refuted rows, against 40 thin rows. Clear outnumbers thin in every
  cell. A test pins that.

Rotation for `none_of_these`: row `i` uses entry `THIN_ENTRIES[i % 4]`
and shape `("refuted", "ruled_out")[(i // 4) % 2]`. The other two cases
keep their rotation over all 19 trainable entries.

### 6. `multi` and the eval probes

**`multi`:**

- Every block gets its header by rule. `render_workload` sets it, and
  `multi` is its only caller.
- Answers do not change.
- Every crash-family workload gets the previous-log read, always the clear
  version.

**The read budget in `multi`.** Today each workload contributes its first
2 object reads, and the row is cut at 8. Measured at seed 17, size 8000
(1,041 `multi` rows, 3,160 workload blocks, 836 of them crash family):

- Appending the log read after the object reads and keeping 2 would lose
  it in **780 of 836** crash-family blocks. That silent loss is not
  acceptable.
- **Ruling:** a crash-family workload keeps its **first object read, then
  its log read**. Any other workload keeps its first 2 object reads, as
  today. Every workload still contributes at most 2 reads.
- **The cap:** a row can pass 8 reads only with a healthy origin read and 4
  workloads (125 rows). There, the cap drops object reads from the end. It
  never drops a log read or the origin read. A plain `[:8]` would have cut
  a log read in 33 rows.
- A test asserts every crash-family workload in `multi` and
  `multi_misattribution_probe` has its log read in the prompt, and that no
  row has more than 8 reads.

**The eval probes:**

- `multi_misattribution_probe`: the header follows the rule (8 of its 38
  values change) and log reads are added under the same slice rule. It
  has no origin read and at most 4 workloads, so it never passes 8 reads.
- `misattribution_probe`: per section 2. Its docstring is rewritten to say
  what it builds.
- `empty_candidates`: no header (it has no candidates), plus the clear log read
  and a gold confidence of `_confidence(e)`. Remove the dead `remaining`
  loop.
- `contradiction_probe`: unchanged. Only the catalogue prefix fix reaches
  it.

### 7. The exam and the grader

**The `none_of_these` slice.** It becomes 8 rows: 4 thin entries × 2
shapes.

- Each row draws its own names. The rng key adds the shape:
  `_entry_rng("held-out", "none_of_these", entry.key, shape)`. Every other
  case keeps its key, so its rows keep their names.
- `held_out_case_set` gets a guard: `none_of_these` only for
  `THIN_ENTRIES`, both shapes.

| Measure | Now | New |
|---|---|---|
| Exam rows | 263 | 252 |
| Job-2 workloads | 153 | 142 (needs 100 of 142 to reach 0.7) |
| Keyword-graded job-2 workloads | 134 | 134 |
| Job-1 workloads | 157 | 157 |

The provenance test becomes: "`none_of_these` covers exactly the 4 thin
entries, each in both shapes".

**The grader's diagnostics.** `evaluate` computes row-level `cause_acc`,
`conf_acc` and the overconfident count. It decides who is keyword-graded
with `_is_keyword_graded(meta)` and `KEYWORD_CASES = {"own_cause",
"empty_candidates"}` (`score.py:16`, `:433-445`). Every other case is
exact-matched, so a correct own-cause answer on `wrong_attribution` or
`misattribution_probe` counts as wrong there.

- Switch those diagnostics to job 2's own per-workload population,
  `_is_job2_keyword_graded`.
- Remove `KEYWORD_CASES`.
- `job2()` itself does not change. No bar moves.

## The pins that move

Every pin is re-written **by hand with a dated comment**. No test is ever
run with `-update`.

**Three hashes:**

| Pin | Where |
|---|---|
| `FROZEN_253_SHA256` | `tests/test_shared_origin_training.py:814` |
| `EVAL_SET_SHA256` | `tests/test_shared_origin_training.py:875` |
| `GRADED_VIEW_SHA256` | `tests/test_exam_graded_view.py:66` |

The frozen slice keeps its meaning: every exam row before the trailing 10
decoy rows. That is now 242 rows, not 253. Rename the constant so its name
drops "253", and assert the row count separately.

**Count pins:**

- `tests/test_generate.py`: lines 57-68, 248-273, 278-309, 311-367,
  431-463, 644-666, 668-679.
- `tests/test_probe_cousins.py`: 100-109.
- `tests/test_oracle.py`: 210-222.
- `tests/test_score.py`: 1336-1341, 1811, 1886, 2055-2057, 2189, 2264.
- `tests/test_evidence_overlap.py`: the declared `contradiction_probe`
  entry (19, 38).

Line numbers are as of `d931109`; the plan re-measures each one.

**Other files:**

- Re-point the prompt-stability test
  (`tests/test_exam_prompt_stability.py:36-55`) at the new bank,
  `out/dataset-<MMDD>`.
- Add a dated entry to `contract/PIN.md`.
- `docs/design.md`: the curriculum table changes in this branch.
- The model card, runbook and README numbers change after the retrain,
  not in this branch.

**One guard to re-check.** `tests/test_score.py` asserts the
paste-the-prompt bot scores **below** `JOB2_BAR`. Its job-2 score is
re-measured on the new exam. If it no longer holds, stop and report. Do
not move the bar.

## What this costs

- **A retrain.** About 33-36 hours on the training host, CPU recipe.
- **A new baseline.** The new exam is a different exam: 252 rows, 142
  job-2 workloads. No score on it compares directly with a score on the
  old one.
- **One extra live run.** The 0920 model runs once on the new exam
  before the retrain, so the new model has a same-exam reference.
  `kv-eval --replay` cannot do this: it refuses a row-count mismatch
  (`evals/cli.py:224-228`), and the old run has 263 rows.
- **Job-1 rows move too.** The catalogue prefix fix and the restart-loop
  quote change job-1 prompts for 3 entries.
- **Thin rows are few.** 320 of 8,000 rows teach "abstain". If the model
  now under-abstains, that is a finding to report, not a reason to raise
  the share in this branch.

## Out of scope

**Spec 3:**

- The per-workload events read in job 2. Its absence is what leaves some
  ruled-out rows with an empty evidence section.
- Job-1 double-attributed rows.
- The shared-origin mismatch.
- `multi`'s workload lines carry no finding at all (no `issue:` line), so
  its log reads sit under a workload with no crash finding shown.
- kubeagent's real read budget in `multi`: greedy in workload order, not 2
  per workload.
- `coredns-corefile-broken`'s suggested command names `n.container`
  (`-c app`) while its finding names `coredns`.

**Job-1 ceiling spec:**

- `contradiction_probe`'s gold answer, and its header, which disagrees with
  the rule on 4 of 19 rows.
- The job-1 ceiling of 0.879 against a 0.90 bar.

**Not touched here:** the shared-origin builders, job-1 events and log
reads, node condition lines, and the GPU.

## Testing

TDD throughout: failing test first, watch it fail, then implement.

1. **`header_for` table.** Node, PVC, registry, other, no attributed
   candidate, and two attributed candidates (raises).
2. **Header equals the rule** for every job-2 workload the generator
   builds, `multi` included.
3. **Thin rows.** No `log cause:` text anywhere in the prompt. Answer is
   `none_of_these` at `low`. `evidence="thin"` raises for any entry outside
   `THIN_ENTRIES`.
4. **Shapes.** The neutral log lines appear in clear rows too. Refuted rows
   have a header and a `fresh read:` line. Ruled-out rows have neither,
   and no object read.
5. **kubeagent's exact strings** — the label, the three content arms used,
   the two cause strings — pinned with a comment naming the source line.
6. **Balance.** For every thin entry and each shape, clear rows outnumber
   thin rows.
7. **Diagnostics population** equals job 2's keyword-graded population.
8. **The invariant.** No two generated rows share a prompt but differ in
   expected cause or confidence.
9. **Log-read table completeness.** Its keys are exactly the trainable
   crash-family entries.
10. **The multi budget.** Every crash-family workload keeps its log read;
    no row has more than 8 reads.

**Stale text fixed in this branch:**

Known so far (line numbers as of `d931109`; the plan re-checks every
test that calls a changed builder):

- `tests/test_cases.py:60-67`: `none_of_these` on `memory-limit-oomkill`,
  which is not a thin entry, so it now raises. Line 66 is also vacuous:
  `"exit code 1"` is inside `"exit code 137"`.
- `tests/test_cases.py:113-119`: `empty_candidates` pinned at `medium`.
- `tests/test_cases.py:175-181`: `none_of_these` on
  `worker-containerd-stop` at `medium`; it now raises.
- `tests/test_cases.py:184-194`, which says `own_cause` uses the refuted
  menu.
- The shuffle test's case list (`tests/test_cases.py:320-327`): drop
  `none_of_these_case`.
- `tests/test_evidence_overlap.py`: the comment on the declared
  `contradiction_probe` entry says it reuses `none_of_these_case`'s reads.
  After this change the refuted reads reach training through
  `wrong_attribution` and the thin `none_of_these` rows. Rewrite the
  comment to say so, and re-measure the count.
- The builders' docstrings (`wrong_attribution`, `misattribution_probe`,
  `multi_misattribution_probe`) and the `contradiction` field's comment at
  `catalog.py:43`, which still names the `none_of_these` case.
- `docs/design.md`.

## Run order

1. Write the plan, then build it subagent-driven.
2. Regenerate: `kv-dataset --seed 17 --size 8000`.
3. Re-pin by hand, with dated comments. Add the `PIN.md` entry.
4. Run the 0920 model on the new exam, live, with `--endpoint`.
5. Merge, push, and pull on the training host.
6. Retrain (about 33-36 hours).
7. Export, quantize, serve locally, and run `kv-eval --endpoint`.
8. Write the new baseline and the model-card sections, including the 0920
   section that is still missing.

If a measured value differs from the plan at any step, stop and report.

## Success criteria

- No two rows share a prompt with different expected answers.
- Every job-2 header equals kubeagent's rule.
- No job-2 prompt holds a read kubeagent would not make, other than the
  gaps listed under Spec 3.
- Every crash-family workload's log read survives the read cap.
- The suite passes; no bar moved; no test ran with `-update`.
- The retrained model is scored on the new exam, with the 0920 model's
  score on the same exam beside it.

**What to watch first in the new scores:**

- The own-cause rate on the refuted-shape slices: `wrong_attribution`
  (0 of 19 on the old exam) and `multi_misattribution_probe`.
- The own-cause rate on `misattribution_probe` (answered `none_of_these` on
  17 of 19 on the old exam).
- `none_of_these` answers on clear rows. Any is a regression.

Bars never move. A miss is reported, not tuned.
