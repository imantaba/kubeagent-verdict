# Faithful prompts (Spec 3) — design

**Date:** 2026-09-25
**Branch:** `spec-faithful-prompts` (cut off `main` @ `6e7f0ce`)
**Status:** approved in six sections; written up for review

## What this is

kubeagent-verdict trains a model on prompts that copy what kubeagent
v1.24.0 sends in local verdict mode. This spec makes two promises about
every generated row:

1. **The prompt is one kubeagent v1.24.0 could really send.**
2. **The gold answer follows from what that prompt shows.**

Today both promises break in many places. The biggest break is in `multi`
rows: 618 of 718 multi job-2 workloads have a gold answer that names a
cause the prompt never shows.

The fix has five parts:

1. One module, `gather.py`, copies kubeagent's evidence gathering. Every
   catalog case builder uses it. No builder types a read by hand.
2. Each case is rebuilt on top of the gather.
3. The catalog prints the text kubeagent's detectors really print.
4. A checker reads every generated row and names each line kubeagent could
   not have sent.
5. The exam grader stops paying for copied prompt lines and hedged
   answers.

kubeagent's source at tag `v1.24.0` (commit `15ec5649b`) is the oracle.
The kubeagent repo stays read-only.

This spec does **not** move a bar (`JOB1_BAR` 0.9, `JOB2_BAR` 0.7,
`JOB3_BAR` 0.9). It lands **before** the retrain. The exam changes, so the
scores after it are a new baseline.

## Why

All counts below were measured on `main` @ `6e7f0ce` over the seed-17,
size-800 sample (801 rows — see IS-20), unless a line says otherwise.

### Multi workloads answer causes the prompt never shows

A `multi` row puts 2 to 4 workloads in one prompt. The builder renders each
workload with `findings=()`, so no workload block has an `issue:` line.
The gold answer for a job-2 workload is its own cause, taken from that
missing finding.

- 718 multi job-2 workloads in the training build.
- **618 of those 718** have a gold cause with no support in the prompt.
- 0 of 105 sampled multi rows show any `issue:` line.

A model cannot learn to read a cause that is not there. It can only learn
to guess.

### 21 shapes kubeagent could never send

Each shape below is a thing a real kubeagent prompt cannot contain. "Fixed
by" names the design part that removes it. "Guard" names the checker rule
(Design 4) that stops it coming back.

| # | What is wrong | Measured | Fixed by | Guard |
|---|---|---|---|---|
| IS-1 | Multi workloads carry no finding line | 0 of 105 multi rows show one | Design 2 H | B2 |
| IS-2 | Multi gold cause not supported by the workload's own block | 618 of 718 workloads | Design 2 H, thin-evidence rule | ANS-2 |
| IS-3 | A `fresh read:` line follows a `ruled out` candidate | 28 of 801 rows (56 lines) | Design 1 `pair_candidates` | D1, D1-onefresh |
| IS-4 | Two `attributed` candidates in one block | 147 of 801 rows | Design 2 A, multi dedup | C4-order |
| IS-5 | A mounted PVC decoy is Pending on a pod already past scheduling | 5 entries | Design 3 P1 | catalog test |
| IS-6 | The PVC decoy's name (`aux-0`/`aux-1`) differs from the name the finding blames | 110 of 801 rows mention one | Design 3 P1 (the decoys go) | catalog test |
| IS-7 | Multi workloads out of report order | 0 of 105 (already fixed on `main`) | — | B1 |
| IS-8 | Registry count is typed in, not counted; some reads show an empty image | 12 of 801 rows show `image "":` | Design 1 (count and image come from the row) | TXT-IS8, C1-cause |
| IS-9 | Scheduler text lacks the preemption suffix; "had disk pressure" is invented | 164 lines in 24 rows | Design 3 K5 | TXT-IS9 |
| IS-10 | `node-cordon-diskfull`'s unscheduled pod sits "on" a node | 22 of 24 rows for that entry | Design 2 (placement off) | catalog test |
| IS-11 | Raw kubectl-table or probe text inside a finding line | 50 of 801 rows | Design 3 K3 | TXT-IS11 |
| IS-12 | Detector `reason`/`evidence` strings kubeagent does not print | 14 strings | Design 3 K3 | exact-string tests |
| IS-13 | `own_cause_keywords` not reliably on a line the prompt can show | 11 entries get a new pair | Design 3 keyword changes | ANS-2, exposure test |
| IS-14 | A restart count below the detector's threshold of 3 | 2 of 40 draw values (1 and 2), in two entries | restarts drawn from `randint(3, 40)` | TXT-IS14 |
| IS-15 | `restart-loop` says `90s ago`; Go prints `1m30s ago` | every `restart-loop` row | Design 3 K3 | TXT-IS15 |
| IS-16 | A node declares `Ready=False` with no kubelet reason or message | 13 node objects | Design 3 K2/K4 | E7, `read_text` raises |
| IS-17 | coredns's suggested command names the wrong container | 31 of 801 rows (267 of 267 in the 8,000-row corpus) | Design 2 J (`_suggestion`) | TXT-IS17 |
| IS-18 | A job-2 row with an empty evidence section | 0 of 801 (already fixed on `main`) | Design 1 makes the events read unconditional | E-min |
| IS-19 | One node plays two stories in one multi row | 25 of 105 multi rows | Design 2 H (one node table per row) | C4-dedup |
| IS-20 | `generate(17, 800)` returns 801 rows | every call | fix A (Testing) | length test |
| IS-21 | No `Cluster health (P1): DEGRADED` block | 415 of 801 rows show a node candidate; 0 show the block | Design 2 J (cluster-health block) | B5, B7 |

Three more measured defects have no IS number. The checker catches all
three:

- **C1-conf:** the `[confidence: …]` tag is wrong on 45 of 801 rows
  (attributed 11, injection 18, truncated 16). The builders feed
  `render.header_for` hand-made candidates instead of the rules' own.
- **C1-cause:** 154 of 801 rows show a `considered` cause kubeagent cannot
  build, such as "considered memory limit too low for the workload". That
  is all 48 attributed rows, all 80 injection rows, and 26 of 40
  truncated rows.
- **The golden file fails 7 checks:** 1 B1 and 6 C1-conf. Its capture
  hand-built the workload order and never called `confidence.Annotate`,
  so all 10 workloads show no confidence tag.

### The queued minors and notes

| Item | What it is | Decision |
|---|---|---|
| Minor #6 | A clear row's rationale contradicts its own prompt | **Node half fixed here:** K2/K4 make the node describe print the real four conditions and the real `Ready=False` text. **Probe half goes to Spec 4:** `probe-failure`'s fixed "no restart" rationale beside a nonzero restart count stays, per ruling R3 (rationale text is unchanged in this spec). |
| Minor #12 | Refused and registry reads render with an empty image | **Fixed here:** the gather takes the row's image (Design 1, step 4). Guard TXT-IS8. |
| Minor #13 | `volume-mount-error` answers "high" on an inference | **Spec 4**, per ruling R2 (`direct` is unchanged in this spec). |
| Minor #14 | The header's confidence and the gold confidence come from two different rules | **Spec 4**, per ruling R2. The header itself becomes correct here (C1-conf); the gold confidence stays `_confidence(e)`. |
| Note: coredns `-c` | The coredns suggested command names the wrong container | **Fixed here** (IS-17). |
| Note: 8,001 rows | `generate()` returns one row more than asked | **Fixed here** (IS-20, fix A). |
| Note: fresh reads on ruled-out multi candidates | A ruled-out candidate gets a fresh-read line | **Fixed here** (IS-3, `pair_candidates`). |

### What Spec 2 deferred

The job-2 generator spec (`2026-09-24-job2-generator-fix-design.md`)
deferred six items to this spec.

| Deferred item | Decision |
|---|---|
| The per-workload events read | Design 1: always the first read of every workload. |
| Rows with two `attributed` candidates | IS-4: Design 2 A and the multi dedup. |
| The shared-origin mismatch | Spec 4. |
| Multi workloads with no finding line | IS-1: Design 2 H. |
| Multi's workload-fair read budget | Design 1: kubeagent's budget is greedy, not fair. The first workloads can spend it all. |
| The coredns command | IS-17: Design 2 J. |

Spec 2 also said "job-1 events and log reads are not touched" and "node
condition lines are not touched". Both statements end here: job-1 reads go
through the gather (Design 1), and K2 renders real node conditions
(Design 3).

## What kubeagent sends

Every fact here is from kubeagent at tag `v1.24.0`. Paths are under
`internal/`.

| Fact | Where |
|---|---|
| The prompt has three sections in this order: inventory, candidates, evidence. Each sits between `== BEGIN x ==` and `== END x ==`. | `investigate/local.go:73-105` |
| An empty section prints `(none)`. | `investigate/local.go:57-60` |
| The prompt closes with "Judge each listed workload now and answer with the JSON object only." | `investigate/local.go` (`buildVerdictPrompt`) |
| The system prompt is fixed text. | `investigate/local.go:34-45` |
| The whole prompt is capped at 64 KiB. Only the evidence is cut, ending in `[truncated by kubeagent]`. | `investigate/local.go:28, 84-103` |
| The inventory is `explain.BuildInventoryPrompt` with the `--explain` closing line trimmed. | `investigate/local.go:74-76`, `explain/explain.go:176-230` |
| When the cluster verdict is Degraded, the inventory **starts** with `Cluster health (P1): DEGRADED — R/T nodes Ready.`, then `  node <issue>` lines, then `  system <issue>` lines, then a blank line. | `explain/explain.go:178-186` |
| The verdict is Degraded when there is any node issue or any system issue. | `clusterhealth/clusterhealth.go:60-108` |
| A workload line is `- ns/name (Kind): R/D ready, status S, N restarts`. | `explain/explain.go:205-206` |
| At most 3 finding blocks per workload. Identical blocks collapse to `(×N)`. Extra blocks of one kind print `    … and N more of the same kind`. | `explain/explain.go:238, 252-282` |
| A finding block is `    issue: <Issue> — <Reason> (<Evidence>)`, an optional `      log cause:` line, an optional `      container resources:` line, and always `      suggested fix (deterministic, pre-reviewed — do not substitute): <NextStep> \| run: <Command>`. | `explain/explain.go:295-311` |
| `network policy:` and `recent change:` lines come after the findings. | `explain/explain.go:208-217` |
| At most 10 `Service issues:` lines. | `investigate/local.go:27, 49-54`, `explain/explain.go:220-224` |
| A candidates heading is `- ns/name (Kind):`, with ` [confidence: X]` before the colon when one candidate is attributed. | `investigate/prime.go:58-121` |
| X comes from the attributed cause: `node ` or `PVC ` → high, `registry ` → medium, anything else → no tag. | `confidence/confidence.go:36-47` |
| A candidate line is `    considered <cause>: <verdict> — <reason>`. The verdict is `attributed`, `ruled out` or `outranked`. | `investigate/prime.go:58-121` |
| A cause has one of 5 shapes: `node X (r)`, `registry unknown`, `registry H`, `registry H (N workloads failing to pull)`, `PVC X (r)`. | `rootcause/rootcause.go:44, 108, 113, 128, 132, 210` |
| A fresh line is `      fresh read: <outcome> — <evidence>`. The outcome is `confirmed`, `refuted` or `unverified`. | `investigate/prime.go:85-99` |
| Fresh lines pair with candidates by position. A ruled-out candidate gets no fresh line, and the cursor does not move past it. | `investigate/prime.go:92-94` |
| At most 8 candidates, then `    [truncated by kubeagent]`. | `investigate/prime.go:38, 86-90` |
| A decided workload ends with `    decided by rules: <cause> — <outcome>`. | `investigate/prime.go:102` |
| Decide skips ruled-out candidates. The first confirmed one wins; else the first unverified one; if all are refuted, the workload is undecided. | `hypothesis/hypothesis.go:62-82` |
| Registry outcomes come from the pull events: connection beats auth beats image. | `hypothesis/decide.go:172-230` |
| Evidence is gathered per workload, in report order: the events read first, then describes, then logs. | `investigate/gather.go:57-157` |
| The gather covers at most 10 workloads. | `investigate/gather.go:24, 28-43` |
| The read budget is 8, shared by all workloads. | `investigate/investigate.go:22` |
| A read is `== label ==\n<content>\n\n`, each content capped at 4096 bytes. | `investigate/gather.go:163-174` |
| Labels: `events <ns>/<name>`, `describe node /<name>`, `describe pvc <ns>/<name>`, `log causes <ns>/<pod> container <c>`. | `investigate/gather.go:90, 132, 153` |
| Crash family (gets a log read): `CrashLoopBackOff`, `ContainerStartError`, `OOMKilled`. | `investigate/gather.go:193-197` |
| An events read is `no events for ns/name`, or `events for ns/name:` plus `  <Reason>: <Message> (xN)` lines. | `investigate/reader.go:312-322` |
| A node describe is `node <name>: unschedulable=<bool>`, then `  condition T=S (R): M` lines, then `  taint k=v:e` lines. | `investigate/reader.go:238-248` |
| A PVC describe is `pvc ns/name: phase=P storageClass=C volume=V`. | `investigate/reader.go:250-257` |
| A failed read's content is `read failed: <reduced error>`. | `investigate/gather.go:85, 117, 126` |
| A log read has 5 possible bodies: refused, other error, no previous instance, no classifiable output, or `log cause: <cause>`. | `investigate/reader.go:473-487` |
| A classified cause is one of 10 fixed strings. | `logscan/logscan.go:30-69, 126` |
| API text is cleaned as `redact.Addresses(safetext.Line(s))`. | `investigate/reader.go:88-90` |
| A model-written line is capped at 512 runes. | `investigate/local.go:113, 436, 463-474` |

## Design

### 1. One gather for every row

A new module, `src/kubeagent_verdict/dataset/gather.py`, copies
kubeagent's `gatherEvidence` and the fresh-line pairing in
`writeWorkloadCandidates`. Every catalog case builder calls it. The
shared-origin builders in `propagation.py` belong to Spec 4 and keep their
own reads.

**What it takes in.**

```python
@dataclass(frozen=True)
class GatherFinding:
    issue: str
    pod: str                  # "ns/name"
    container: str = ""
    log_read: str | None = None   # the declared log-read body

@dataclass(frozen=True)
class GatherWorkload:
    namespace: str
    name: str
    pod: str
    issue: str
    objects: tuple            # the entry's node/PVC/registry objects
    events: tuple[tuple[str, str, int], ...]   # (reason, message, count)
    findings: tuple[GatherFinding, ...]

@dataclass(frozen=True)
class GatherResult:
    reads: tuple[c.EvidenceRead, ...]
    candidates: tuple[tuple[c.Candidate, ...], ...]   # per workload
    results: tuple[rules.Result, ...]                 # per workload

def gather(workloads: Sequence[GatherWorkload]) -> GatherResult: ...
```

**What it does, in order.**

1. **Candidates.** Call `rules.attribute` (`rules.py:100-191`, unchanged)
   for each workload.
2. **Reads, greedy, budget 8.** Walk the workloads in report order, at most
   `MAX_GATHER_WORKLOADS` (10). Use `contract.MAX_TOOL_CALLS` (8) as the
   budget. Check the budget before every single read. For each workload:
   1. **The events read, always first.** Its pod is the first finding's pod
      part (kubeagent's `podPart`), else the workload name.
   2. **Describes.** Each candidate that is not ruled out and not a
      registry, in candidate order, over the whole list (the 8-candidate
      display cap does not limit reads). Key each object `kind/ns/name`
      (empty ns for a node). A key read by an earlier workload is not read
      again. Content comes from `rules.read_text` (`rules.py:381-422`).
   3. **Logs.** One read per crash-family finding with a container. Dedup
      on `ns/pod/container`. Content is the finding's declared `log_read`.

   When the budget is spent, no read happens anywhere after that point.
   A workload the budget never reached is **starved**.
3. **Starved objects.** An object the walk never reached gets
   `Fresh(how="not_read")` on every occurrence of its key, in every
   workload (`dataclasses.replace`). Its fresh text is "not re-read: the
   read budget was spent first". That outcome is **unverified**. So Decide
   can still pick it: a starved workload with a live candidate is
   **decided, and becomes job 1**. A starved workload whose candidates are
   all ruled out stays job 2, with no reads of its own.
4. **Registry candidates.** Their outcome comes from the workload's events
   text, not from a separate field:
   - A port of `classifyPullEvents` sets `fresh.literal`, using the
     `CONNECTION`/`AUTH`/`IMAGE_LITERALS` lists in `objects.py:25-36`.
     Connection beats auth beats image.
   - A port of `pullPod`/`checkRegistry` sets `wrong_pod`.
   - `fresh.how` follows the events read: `not_read` if it was never made,
     `read_failed` if it failed, `read` otherwise.
   - The registry count is **counted**: the number of flagged workloads in
     the row that fail to pull from that host. It is never typed in.
   - The gather takes the image from the row (minor #12).
5. **Decide.** Call `rules.decide` (`rules.py:293-319`, unchanged) over what
   was actually read.
6. **Pair fresh lines.** `pair_candidates(candidates, result)` copies
   kubeagent's cursor. A ruled-out candidate gets no fresh line and the
   cursor stays put. Every other candidate takes the next decision in order.
   This fixes IS-3.

**Text cleaning.**

- `safetext_line` ports `safetext.Line`: at most 512 runes; at most 4
  combining marks in a run; invalid UTF-8 becomes U+FFFD; `\t \n \v \f \r`,
  U+2028 and U+2029 become a space; other control and format (Cf)
  characters are dropped; the result is trimmed. A cut line ends in `…`,
  and a combining mark left dangling at the cut is dropped.
- `_sanitize(s)` is `contract.redact_addresses(safetext_line(s))`
  (`contract.py:148-149`), the same order as kubeagent.
- `cap_content` (`contract.py:158-178`) runs inside `render_evidence`
  (`contract.py:181-187`).
- A `CRASH_FAMILY` constant names the three crash-family issues.
- There is no `redact.Error` port. A failed read's text is written in the
  catalog as the finished string.

**What it removes.**

- `render.py`: `apply_budget` (`:91-126`), `registry_events_read`
  (`:129-157`), `object_reads` (`:160-183`), and the inline
  `decisions = {d.candidate: d …}` pairing (`:240-254`).
- `cases.py`: `_multi_reads`/`_cap_reads` (`:181-214`),
  `_to_contract_candidates` (`:283-300`), and the fake `Result` in
  `_winner_example` (`:319-357`).

**What stays.** `rules.attribute`, `rules.decide`, `render.header_for`,
and `contract.render_candidates` (`contract.py:190-214`).

### 2. Each case, rebuilt on the gather

**The job-1 set.** A new function, `catalog.job1_entries()`, returns the
17 entries the rules can decide in a single-workload row: 16 decided by a
node and 1 decided by a PVC (`pvc-unbound-unschedulable`). Three trainable
entries are outside it:

- `deployment-bad-image-tag`: its registry count is counted from the row,
  so in a single row it is always 1, and kubeagent rules it out.
- `node-cordon-diskfull`: its pod is unscheduled, so its node placement is
  "off" and the node is ruled out.
- `oversized-job-unschedulable`: same reason, placement "off".

These builders use `job1_entries()`: attributed, injection and truncated
(the rotations at `generate.py:140, 259, 262`, which today use
`catalog.trainable()` from `:130`), the positional-probe guard in
`probe_sets` (`generate.py:400-407`), and the contradiction-probe loop
(`generate.py:450-454`, replacing its `entry.contradiction` gate).

These keep all 20 entries: `own_cause_case` (`:148`), `wrong_attribution`
(`:266`), `empty_candidates` (`:264`), `misattribution_probe` and
`multi_misattribution_probe` (`:418-428`). `none_of_these` keeps
`THIN_ENTRIES` (`cases.py:421`: crashloop-pod, coredns-corefile-broken,
init-crashloop, restart-loop).

**A. attributed** (`cases.py:360-368`, job 1)

- The winner is the entry's cause-intent object, or else its only object.
- A new `deciding_ending(kind)` draws the winner's ending:
  node → {declared-if-confirming, lease, read_failed};
  PVC → {declared, read_failed}. Other objects keep decoy endings.
  `render.ENDINGS` and `draw_ending` do not change.
- In half the rows (a coin from the row's rng), add one ruled-out PVC:
  `aux-0` (`PAD_PVCS[0]`), unmounted, never read. Its position comes from
  the rules' own order.
- The row must be decided (`decided=True`). Gold cause is `result.cause`,
  rationale is `_rule_rationale(result)`, confidence is `_confidence(e)`.
  `decoy_by_workload` holds the other candidates.

**B. injection** (`cases.py:578-589`, job 1)

- A, plus one events line `  <Reason>: <payload> (x1)`. Reason is one of
  `Unhealthy`, `Killing`, `FailedSync`. None of these trips the pull-event
  test.
- The payload comes from `INJECTION_PAYLOADS` (`cases.py:371-377`) and
  passes through `_sanitize`. `meta` keeps the raw payload.

**C. positional_probe** (`cases.py:592-607`, eval, job 1)

- The winner is placed last.
- Node entries: a refuted `worker-1` comes first (placement on, scan
  NotReady, fresh Ready True). If the row's own node is `worker-1`, the
  decoy is `worker-2`.
- The PVC entry: a refuted `aux-0` comes first (mounted, scan Pending,
  fresh Bound).
- There is no registry branch.
- Decide passes over the refuted first candidate and picks the winner.
  Gold is `result.cause`. `meta._row_decoy` is the refuted candidate's
  cause.

**D. truncated** (`cases.py:543-575`, job 1)

- This case tests the **8-candidate display cap**, not the 8-read budget.
- Padding is `PAD_PVCS` `aux-0` … `aux-8`, all ruled out (unmounted), so
  none is read. The names stay as they are.
- Every pad sorts before every entry PVC name. So the PVC-decided entry's
  cause lands past the cap. The 16 node-decided entries show their cause
  first, because node candidates come before PVC candidates.
- Gold as A. The flat "low" confidence and the "treat with caution"
  summary go.

**E. undecided job-2 rows** (`_undecided_example`, `cases.py:439-496`, and
its wrappers `:499-540`: wrong_attribution, own_cause,
misattribution_probe, none_of_these)

- Menus and gold do not change.
- Reads come from the gather: events, then describes, then the log.
- The thin-row leak test checks that **all** keywords are present, not any
  one.

**F. contradiction_probe** (`cases.py:623-709`, eval, job 1)

- It runs over the 17 job-1 entries.
- The menu, `_contradiction_menu` (`cases.py:610-620`), does not change:
  node lease, PVC read_failed, registry auth.
- Gold follows the rules: `result.cause`, `_rule_rationale(result)`,
  `_confidence(e)`. The 19 hand-typed `none_of_these` answers go.
- The contradiction lines move into the read they belong to. Event lines
  come from the entry's `contradiction_events` and go into the events read.
  `worker-containerd-stop` needs none: its lease ending already renders a
  describe with `Ready=True`.

**G. empty_candidates** (`cases.py:712-743`, job 2)

- Reads are the events read plus the log read (crash family only).
- `node-cordon-diskfull` and `worker-containerd-stop` lose their describe
  read: with no candidate, there is nothing to describe.

**H. multi** (`cases.py:1464-1552`)

- Workloads sort by (namespace, name, kind), kubeagent's report order.
- Each workload renders through `_workload`/`_finding`, so its block has
  its real finding lines (IS-1).
- One greedy gather covers all workloads. It replaces the per-workload
  hand-built reads.
- **One object, one state.** `_multi_objects` (`:1380-1402`) builds one node
  table per row and dedups it: a node has one scan reason in a row. Own
  node names are distinct within a row, and own (namespace, PVC) pairs are
  distinct. `NODES` grows to `worker-1` … `worker-5` (IS-19).
- The healthy-origin read (helpers at `:1405-1461`) stays first. It is
  Spec 4's, and the checker exempts it (Design 4).
- The origin label is stored filled in. `cases.py:1550` takes
  `healthy_read[0]` (`:1498`). Today 19 of 35 rows store an unfilled
  template such as `describe node {node}`.
- **Thin evidence.** A starved workload whose candidates are all ruled out
  has no reads. It answers its own cause only when its own block holds
  every one of its keywords. Otherwise its gold is `none_of_these` at low confidence.

**I. multi_misattribution_probe** (`cases.py:746-824`)

- The prefix rule is dropped.
- The builder raises if a constituent workload is starved.

**J. Cross-cutting**

- **coredns command.** `_suggestion` uses the entry's real container name,
  so coredns's command reads `-c coredns`, as kubeagent's remediation text
  does (`remediation/remediation.go:21, 25, 44`). This fixes IS-17.
- **Image.** The gather always takes the row's image (minor #12).
- **Event tuples.** Entries whose reads were kubectl-table text now declare
  events as `(reason, message, count)` tuples. The `formatEvents` port
  renders them.
- **`_row_decoy`** (`cases.py:217-230`) keeps its role.
- **The cluster-health block** (IS-21). A new pure function renders it:
  - The block appears **if and only if** the row has a node candidate or a
    flagged `kube-system` workload.
  - `T = max(3, distinct named nodes + 1)`. `R = T −` the nodes whose scan
    reason is NotReady.
  - Node issues, in node-name order:
    `<name> NotReady: KubeletNotReady — container runtime is down` or
    `<name> no kubelet lease`.
  - System issues: `kube-system/<name> R/D <status>`.
  - The scheduler world is not fully covered. A scheduler message can
    count a cordoned or tainted node that this block does not list. That
    residual goes to Spec 4.

### 3. Catalog text kubeagent really prints

After this spec the catalog has 29 entries, 20 of them trainable (one new
entry).

**K3. 14 detector-string fixes.** Each string is copied from the detector
that prints it (paths under kubeagent `internal/diagnose/`).

| Entry | Fixed text | Source |
|---|---|---|
| memory-limit-oomkill | reason `Container exceeded its memory limit and was killed`; evidence `container "{container}", exitCode=137` | `oomkilled.go:22-24` |
| deployment-bad-image-tag | reason `Bad image reference or registry authentication`; evidence `container "{container}": Failed to pull image "{image}": not found` | `imagepull.go:19-20` |
| create-container-config-error | the container name is quoted | `configerror.go:26` |
| probe-failure | reason `the readiness probe keeps failing — the pod is kept out of Service endpoints`; evidence `container "{container}": readiness probe failed — HTTP 500` | `probefailure.go:346, 363-372` |
| networkpolicy-deny-all | evidence `container "{container}": readiness probe failed — timed out` | `probefailure.go:363-372` |
| init-errimagepull | evidence gains the position: `init container "{init_container}" (1/2): Failed to pull image "{image}": not found` | `initcontainer.go` |
| init-imagepullbackoff | evidence gains the position: `init container "{init_container}" (1/2): Back-off pulling image "{image}"` | `initcontainer.go` |
| init-config-error | evidence `init container "{init_container}" (1/2): secret migration-creds not found` | `initcontainer.go:70-71` |
| volume-mount-error | evidence `Unable to attach or mount volumes: unmounted volumes=[data], unattached volumes=[], failed to process volumes=[]: timed out waiting for the condition` | kubelet volume manager text |
| restart-loop | evidence `container "{container}", {restarts} restarts, last exit 1 (Error), 1m30s ago` (today `90s ago`) | `restartloop.go` |
| crashloop-pod | evidence `container "{container}", restartCount={restarts}, last exit 1 (Error), 3m0s ago` | `crashloop.go:44-56` |
| coredns-corefile-broken | evidence `container "coredns", restartCount=6, last exit 1 (Error), 42s ago` | `crashloop.go:44-56` |
| node-cordon-diskfull | the disk-pressure message is `kubelet has disk pressure` | kubelet `setters.go:717-718` |
| scheduler strings | per K5 below | K5 |

The ages are fixed values, not draws. kubeagent prints them with Go's
`time.Duration.String()`, which writes 90 seconds as `1m30s` and 3
minutes as `3m0s`. `90s` and `3m` are not forms it prints.

**Restarts.** `crashloop-pod` and `restart-loop` draw their restart count
from `randint(3, 40)`. The detector fires only at 3 or more
(`restartloop.go:15, 35-37`). This fixes IS-14.

**K2. The node describe prints all four conditions**, in kubelet order,
with kubelet's real reasons and messages:

| Condition | Reason | Message |
|---|---|---|
| MemoryPressure=False | `KubeletHasSufficientMemory` | `kubelet has sufficient memory available` |
| DiskPressure=False | `KubeletHasNoDiskPressure` | `kubelet has no disk pressure` |
| DiskPressure=True | `KubeletHasDiskPressure` | `kubelet has disk pressure` |
| PIDPressure=False | `KubeletHasSufficientPID` | `kubelet has sufficient PID available` |
| Ready=True | `KubeletReady` | `kubelet is posting ready status` |
| Ready=False | `KubeletNotReady` | `container runtime is down` (K4) |

**K4. One constant for `Ready=False`.** Every node object that declares
`ready="False"` uses one shared constant: `ready_reason="KubeletNotReady"`,
`ready_message="container runtime is down"` (kubelet `runtime.go:129`, a
fixed real string). That is 13 objects today (the 12 node entries other
than `node-cordon-diskfull`, plus `worker-containerd-stop`); the P1 swap
below adds 4 more. `read_text`
raises if a node declares `ready="False"` without this text. This fixes
IS-16.

**K5. Scheduler strings.** The default scheduler profile always adds a
preemption suffix. Here the suffix is always
` preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling.`

| Entry | Message (before the suffix) | Events count |
|---|---|---|
| oversized-job-unschedulable | `0/3 nodes are available: 3 Insufficient memory.` | `(x5)` |
| node-cordon-diskfull | `0/3 nodes are available: 1 node(s) were unschedulable, 2 node(s) had untolerated taint(s).` | `(x6)` |
| pvc-unbound-unschedulable (new) | `0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims.` | — |

This fixes IS-9.

**P1. PVC decoys that cannot happen (option A).** A pod with a finding
such as a config error or a mount error is past scheduling. Its claims are
Bound: PreBind blocks Bind until they bind, and Bound never goes back. So a
mounted, Pending PVC decoy on that pod is impossible.

- `create-container-config-error`, `volume-attach-error`,
  `volume-mount-error`: the PVC decoy becomes a node decoy `{node}` (scan
  NotReady, placement on, `Ready=False` with the K4 text, intent decoy).
- `worker-containerd-stop`: the PVC decoy is removed.
- `oversized-job-unschedulable`: its decoy becomes a node (scan NotReady,
  placement off, `Ready=False` with the K4 text).
- **New entry `pvc-unbound-unschedulable`:** a Deployment, Pending,
  Unschedulable. `covered_slugs=()`, `covered_kinds=()`. Reason
  `No node can schedule this pod`.
  - Its object is the PVC `{pvc}`: intent cause, scan
    `MissingStorageClass`, mounted, fresh Pending, storage class
    `fast-ssd`.
  - Its events tuple holds the `ProvisioningFailed` event with message
    `storageclass.storage.k8s.io "fast-ssd" not found`.
  - `own_cause`: "a claim the pod mounts is still waiting for its volume to
    be provisioned". Keywords `("claim", "volume")`.
- The comment at `names.py:22-25` is updated.

This fixes IS-5 and IS-6.

**Fields deleted from `CatalogEntry`** (`catalog.py:37-40, 43`):
`contradiction`, `winner_cause`, `winner_reason`, `losers`, `reads`. The
16 entries that had a `contradiction` get `contradiction_events` instead.

**Keyword changes.** 11 entries change their `own_cause_keywords`. Each new
pair is on a line the prompt can show.

| Entry | New keywords |
|---|---|
| deployment-bad-image-tag | `image`, `registry` |
| node-cordon-diskfull | `node`, `pod` |
| networkpolicy-deny-all | `network`, `policy` |
| coredns-corefile-broken | `coredns`, `error` |
| worker-containerd-stop | `containerd`, `deadline` |
| oversized-job-unschedulable | `memory`, `node` |
| probe-failure | `readiness`, `endpoint` |
| container-start-error | `container`, `image` |
| restart-loop | `panic`, `container` |
| volume-attach-error | `attached`, `node` |
| volume-mount-error | `volume`, `pod` |

`crashloop-pod` keeps `("entrypoint", "exit")`. Seven more entries keep
their pairs, and the new entry uses `("claim", "volume")`.

**Other text.**

- `worker-containerd-stop`'s `own_cause` becomes "containerd on the pod's
  node is not responding (context deadline exceeded)".
- `direct`, `rationale` and every other `own_cause` stay as they are
  (rulings R2 and R3).

### 4. The checker

A new module, `src/kubeagent_verdict/dataset/checker.py`, with tests in
`tests/test_checker.py`. It is an **independent text parser**: it reads
the rendered prompt and answer, and nothing else. It never rebuilds a row
from the row's own data.

Two other designs were rejected:

- Rebuilding each row with the generator's own code and comparing. It
  would share the generator's mistakes.
- A checker limited to the K3 strings and the ports. It misses order,
  pairing and header defects.

It has one function per rule. A violation carries the rule id, where it
is, and a quote.

**The rules.**

| Group | Rule | What it checks |
|---|---|---|
| Frame | A1 | The three sections, in order |
| | A2 | The closing sentence |
| | A3 | The 64 KiB cap; only the evidence is ever cut |
| | A4 | The system prompt, word for word |
| | A5 | `(none)` for an empty section |
| | A6 | The inventory has `BuildInventoryPrompt`'s shape |
| Inventory | B1 | Workloads sorted by (ns, name, kind), at most 10 |
| | B2 | Workload-line and finding-line shapes; at most 3 finding blocks |
| | B3 | The `(×N)` collapse |
| | B4 | `network policy:` and `recent change:` after the findings |
| | B5 | The cluster-health block's format |
| | B6 | At most 10 service issues |
| | B7 | The cluster-health block appears if and only if there is a node candidate or a flagged `kube-system` workload, with exactly the lines Design 2 J names |
| Candidates | C1 | Heading shape and order |
| | C1-conf | The confidence tag is there if and only if `ForRootCause` of the attributed cause gives one, and it matches |
| | C1-cause | A cause has one of kubeagent's 5 shapes |
| | C2-vocab | The verdict is one of the 3 words |
| | C2-reason | The reason text is one kubeagent writes for that verdict |
| | C3 | At most 8 candidates, then the truncation line |
| | C4-order | At most one attributed candidate per block |
| | C4-dedup | No object twice in a block; one scan reason per node per row |
| | C5/D4 | The decided line appears if and only if the workload is decided; its outcome is `confirmed` or `unverified` |
| Fresh read | D1 | Never after a ruled-out candidate |
| | D1-onefresh | Exactly one per non-ruled-out candidate, in order |
| | D2-vocab | The outcome is one of the 3 words |
| | D3 | A confirmed or refuted fresh line names an object whose read is in the evidence section |
| Evidence | E1 | At most 8 reads |
| | E2-order | Per workload: events, then describes, then logs |
| | E3 | Each read at most 4096 bytes |
| | E4 | The label has one of the 4 shapes |
| | E5 | No label repeats |
| | E6 | The events format |
| | E7 | The node describe format |
| | E8 | The PVC describe format |
| | E9 | A log read is one of the 5 bodies; a cause is one of the 10 strings |
| | E10 | A failed read reads `read failed:` |
| | E-min | Every scoped workload has at least one read. A starved workload is exempt. |
| Text | F1 | No control characters; no long runs of combining marks |
| | F2 | No raw IP address and no `host:port` |
| | F3 | Every line of API text and every gold answer line is at most 512 runes |
| | TXT-IS8 | No `image "":` |
| | TXT-IS9 | A line with `nodes are available:` also has ` preemption: 0/`; no `had disk pressure` |
| | TXT-IS11 | No `dial tcp`, `i/o timeout` or `Get "` outside an events read |
| | TXT-IS14 | Restart counts are 3 or more |
| | TXT-IS15 | No `90s ago` and no `3m ago`; every age is a form Go's `Duration.String()` prints |
| | TXT-IS17 | coredns's command has `-c coredns` |
| Answer | ANS-1 | The answer's workloads equal `meta.workloads`. A job-1 gold cause equals the decided cause. No gold cause is a ruled-out or refuted cause. |
| | ANS-2 | Every `own_cause` keyword is in that workload's own block |

**Exemptions.** Both lists are pinned by a test.

- **The 4 shared-origin cases** skip the evidence rules: `shared_origin`,
  `shared_origin_decoy`, `shared_origin_probe`,
  `shared_origin_decoy_probe`. Spec 4 removes this exemption.
- **The multi healthy-origin read** is exempt only at read index 0, and only
  when its label equals the filled `meta.origin_read_label` exactly (plain
  string equality). 35 of 105 multi rows have one. It still counts toward
  the 8 reads.

**Where it runs.**

- At generate time, as a per-case count. It is a report only. It never
  blocks a write and never draws a random number.
- In pytest, over the golden file (0 violations), a seed set
  (seed 17, size 800, about 0.17 s), and the exam pool (about 8,253 rows,
  about 1.7 s).

**Byte-exact ports** are limited to the K3 strings and the ports under test
(Testing). The checker does not port every detector.

### 5. The exam and the grader

**The exam changes.** The counts below are estimates from the approved
design. The plan re-measures each one after regenerating. **If a measured
value differs, the plan stops and reports.**

| Case | Today | After |
|---|---|---|
| attributed | 53 | 22 |
| own_cause | 19 | 51 |
| truncated | 19 | 17 |
| injection | 19 | 17 |
| empty_candidates | 19 | 20 |
| wrong_attribution | 19 | 20 |
| positional_probe | 19 | 17 |
| misattribution_probe | 19 | 20 |
| multi_misattribution_probe | 19 | 20 |
| contradiction_probe | 19 | 17 |
| shared_origin_probe | 10 | 10 |
| shared_origin_decoy_probe | 10 | 10 |
| none_of_these | 8 | 8 |
| **Total** | **252** | **249** |

| Population | Today | After |
|---|---|---|
| job 1 workloads | 157 | 118 |
| job 2 workloads | 142 | 179 |
| job 3 prompts | 39 | 40 |
| job 3 labels (shared / separate / none) | 5 / 0 / 34 | 5 / 0 / 35 |
| keyword-graded job-2 workloads | 134 | 171 |
| frozen slice rows | 242 | 239 |

- **31 corpus rows move to `own_cause`.** They come from entries no rule
  can decide: `deployment-bad-image-tag` 24, `node-cordon-diskfull` 4,
  `oversized-job-unschedulable` 3. They now show kubeagent's real shape:
  every candidate ruled out, gold is the workload's own cause.
- **`none_of_these` gold falls from 27 to 8** across the exam: the 19
  hand-typed answers in `contradiction_probe` go (Design 2 F).
- **Keyword grounding:** 40 of 40 keyword instances are on a line the
  prompt can show.

**The grader guard (option A: G2 plus G3b).** Once the prompt shows each
workload's real finding, a bot that pastes the prompt back can earn job-2
keywords. Two checks stop that. Each zeroes one workload.

- **G2:** zero the workload if its normalized raw cause contains any decoy
  cause. The decoys are the workload's `decoy_by_workload` plus the row's
  `decoy_causes`/`decoy_cause`.
- **G3b:** zero the workload if its raw cause contains any full printed line
  of its own block: its inventory lines, its candidate block, and the
  evidence reads matched to it.

Both checks run on the **raw** reply, **before** the 512-rune cap and
before keyword matching. Capping first was measured to let the paste bot
reach 0.007. Normalization is `_norm_cause` (`evals/score.py:409-410`). One
helper serves both `job2()` (`evals/score.py:194-214`) and the
`cause_hits` count in `evaluate()` (`evals/score.py:525-532`).

The gold answer must pass every guard. A test asserts the gold answer
passes both guards on every exam row.

**Measured bots** (job-2 score):

| Bot | No guard | Guarded |
|---|---|---|
| paste the prompt | 0.5352 | 0 |
| echo | 0.5282 | 0 |
| name the decoy | 0 | 0 |
| hedge (real cause plus the decoy) | 0.9437 | 0.2183 |
| gold | 1.0 | 1.0 |

G3b stops pasting. G2 stops hedging: naming the real cause and a decoy
together.

**Thin rows.** A test checks that every `none_of_these` thin row hides at
least one keyword. All 4 `THIN_ENTRIES` pass today.

**Bars do not move.** Known gap: `node-cordon-diskfull`'s keywords
`("node", "pod")` are generic. Spec 4 owns them.

## The pins that move

Every pin is re-written **by hand, with a dated comment**. No test runs
with `-update`. A value marked "measured" comes from the regenerated data.

| Pin | Location | Before → after |
|---|---|---|
| Catalog counts | `tests/test_catalog.py:106, 147` | 28 → 29 entries; 19 → 20 trainable. The test names carry the counts and are renamed in the same edit. |
| `worker-containerd-stop` test | `tests/test_catalog.py:117` | Rewritten: the entry has no PVC decoy. |
| PVC pins | `tests/test_catalog.py:52-99` | Follow the P1 swap. |
| Exam rows | `tests/test_shared_origin_training.py:777` | 252 → 249 |
| Per-case `Counter` | `tests/test_generate.py:288-326` | The Design 5 table |
| Populations | `tests/test_generate.py:449-482, 639-660` | job1 157 → 118; job2 142 → 179; job3 prompts 39 → 40; job3 labels {5, 0, 34} → {5, 0, 35}; `decided_total` 157 → 118 |
| Keyword exposure | `tests/test_generate.py:329-386` | Becomes 100% of keyword-graded job-2 workloads, measured |
| Footnote | `tests/test_score.py:1420-1445` | "76 of 134" → "X of 171", X measured |
| Always-`none_of_these` bot | `tests/test_score.py:2040-2056` | 0.0563 → about 0.045 (8 of 179), measured |
| Paste bot | `tests/test_score.py:2058-2118` | 0.535 unguarded → guarded, measured. **STOP if it reaches 0.7.** |
| Hedge bot | `tests/test_score.py` | New pinned test |
| `DECLARED` | `tests/test_evidence_overlap.py` | positional and contradiction 19 → 17; misattribution and multi_misattribution 19 → 20; the two shared-origin probes unchanged |
| Job-1 misses | `tests/test_oracle.py:252` | 19 misses → 0 ("job 1 is perfect") |
| Job 3 oracle | `tests/test_oracle.py` | n 39 → 40; labels {5, 0, 34} → {5, 0, 35} |
| Job 2 oracle | `tests/test_oracle.py` | n 142 → 179; rate stays 1.0 |
| Exam hashes | `FROZEN_SLICE_SHA256` (`test_shared_origin_training.py:871`), `EVAL_SET_SHA256` (`:938`), `GRADED_VIEW_SHA256` (`test_exam_graded_view.py:78`) | All three measured |
| Frozen length | `tests/test_shared_origin_training.py:947-955` | 242 → 239 |
| Multi job-1 curriculum | `tests/test_oracle.py:228-250` | 1226/1226 train, 132/132 val today. It measures the training build, not the exam, so it gets its own re-measure. |
| PAD_PVCS | `tests/test_names.py:28-31` | Gains the sort test (Testing) |
| `contract/PIN.md` | — | New dated entry recording the regenerated counts, the three hashes, and the grader guard; `JOB2_BAR` stays 0.7 |
| `docs/design.md:652` | — | "19 trainable entries" → "20" |
| Shared-origin keyword pairs | `propagation.py` | Unaffected |

## What this costs

- **Code.** `gather.py` is about 300 lines plus tests. Every case builder
  changes how it gets its reads. The catalog changes K3, K2/K4, K5, P1
  and 11 keyword pairs, and loses five fields.
- **Tests.** Port tests, the byte-equal gather test, the checker's own
  tests, and the rewrites the field deletion forces (Testing). The checker
  adds about 2 seconds to each full run.
- **The golden re-capture.** One run on the training host, which has Go.
  This workstation does not.
- **Regeneration.** Almost every row's text changes, so every count and
  hash in the pins table is re-measured.
- **Live runs.** Two live runs of the 0920 checkpoint, about 2 h 20 min
  each; one retrain, about 32 hours on the CPU recipe; one untuned-baseline
  run, about 2 h 20 min. See "Run order".

## Out of scope

**Spec 4** owns:

- Rewriting the shared-origin stories, and removing the shared-origin
  checker exemption and the healthy-origin read exemption.
- The shared-origin mismatch Spec 2 deferred.
- The strings at `propagation.py:505` and `:526`.
- The `propagation.py` text near line 3440 that says `WaitForFirstConsumer`
  while it shows the Immediate-mode scheduler message.
- `node-cordon-diskfull`'s `own_cause`, which says "the pod's node" for a
  pod with no node, and its generic keywords `("node", "pod")`.
- Rulings R2 and R3: `direct`, `rationale` and `own_cause` text. This
  includes minor #13, minor #14, and the probe half of minor #6.
- The scheduler-world residual of the cluster-health block (Design 2 J).

**Measured later, not designed here:** the job-1 ceiling (0.879 against the
0.90 bar). Only a retrained model can answer it.

**Unrelated:** the training host's GPU. That is a separate project.

## Testing

The tests prove four things:

1. The Python ports match kubeagent.
2. The checker catches every impossible prompt.
3. Every decision in this spec has a test that fails without it.
4. Every number that moves is re-pinned by hand.

### Port tests

Each port gets vectors copied from kubeagent's own Go test. Where Go has no
test for the exact shape, the expected output is built from Go's format
string, with a `file:line` comment. All paths are under kubeagent
`internal/` at `v1.24.0`.

| Port | Vectors from |
|---|---|
| `safetext.Line` | `safetext/safetext_test.go:9, 62, 72, 84, 97` |
| `redact.Addresses` | `redact/redact_test.go:66, 94` |
| `capContent` | `investigate/gather_test.go:167, 187` |
| `formatEvents` | `investigate/reader_test.go:974` |
| `describeNode` (all four conditions) | `investigate/reader_test.go:361`, plus the format string at `reader.go:242-244` |
| `describePVC` | the format string at `investigate/reader.go:255-256` |
| log-read bodies and the 10 causes | `logscan/logscan_test.go:9, 43, 72, 98, 132, 167` |
| `renderCandidates` and the cursor | `investigate/prime_test.go:89, 148, 174, 188` |
| `BuildInventoryPrompt` with the Degraded block | `explain/explain_test.go:110` |
| `clusterhealth.Assess` | `clusterhealth/clusterhealth_test.go` (27 tests) |
| `ForRootCause` | `confidence/confidence_test.go:27` |
| `classifyPullEvents` | `hypothesis/hypothesis_test.go:311` (22 literals: 13 connection, 4 auth, 5 image) and `:350` (precedence) |

### The byte-equal gather test

`gather.py` decides read order, the budget, and which candidate gets which
fresh line. It is the riskiest port, so it is checked byte for byte
against the real kubeagent code.

- **The fixture.** One YAML file in `tests/fixtures/` describes about 12
  workloads: namespace, pod, findings and crashed container, objects and
  their endings, events as `(reason, message, count)`, and log text for
  crashed containers. The golden re-capture uses the same file.
- **The Go side** (training host only). A harness loads the YAML, builds
  `inventory.Workload`s and a fake clientset, and runs the real kubeagent
  functions. It writes 10 dumps:

  | # | Stage |
  |---|---|
  | 1 | Workload order (`flaggedScope`, `Prioritize`) |
  | 2 | Events reads |
  | 3 | The candidate walk: read, skipped as ruled out, or deduped |
  | 4 | Node describes |
  | 5 | PVC describes |
  | 6 | Log reads |
  | 7 | The read trail |
  | 8 | The evidence bundle |
  | 9 | `Decide` per workload |
  | 10 | Shared-cause lines and the full prompt |

- **The Python side.** A pytest loads the same YAML, runs `gather.py` and
  the renderers, and compares each dump and the prompt byte for byte with
  the committed Go dumps. It needs no Go and runs on every `pytest`.

### The golden re-capture

The capture file `contract/capture/kv_capture_test.go.txt` hand-builds
four things the real pipeline computes. It is fixed first:

1. Load the shared YAML instead of the hand-typed workloads and reads.
2. Build a fake clientset from it and call `inventory.Prioritize` for the
   order.
3. Call `clusterhealth.Assess` instead of a hand-built cluster value.
4. Call the package-private `gatherEvidence` directly (the file is in
   `package investigate`).
5. Call `confidence.Annotate` after the three `rootcause.Annotate*` calls,
   as `scan.go:815-818` does.

**Steps.**

1. On this workstation: `git archive v1.24.0 | gzip` in the kubeagent repo.
   Check the file count against `git ls-tree -r v1.24.0 --name-only | wc -l`.
   No worktree, no branch.
2. Copy the archive, the YAML and the capture file to a scratch folder on
   the training host.
3. Unpack it. Copy the capture file in as
   `internal/investigate/kv_capture_test.go`.
4. Run `go test` there, with three stand-ins for a real API server:
   - the reads that need a real `RESTClient` are switched off (the fake
     clientset has none);
   - the log read goes through an `httptest` server that serves the
     fixture's log text, because the fake clientset's `GetLogs` always
     returns `fake logs`;
   - a `PrependReactor` filters events by `involvedObject.Name`, plus a
     self-check that two workloads' event reads differ.
5. Copy back `contract/golden/{input.json,user_message.txt,answer.json}`,
   `contract/system_prompt.txt`, `tests/fixtures/rules_golden.json`, and
   the capture record in `contract/PIN.md`.
6. Check that the fixture still exercises every rule path in
   `rules_golden.json`: each attribution rule and each Decide outcome
   appears at least once. Keep today's refused reads: node `worker-7`, PVC
   `aux-1`, and the events of `img/seven`.
7. Remove the scratch folder and the local archive. `git status --short`
   in the kubeagent repo must print nothing.

**Fallback (option 2),** only if the training host cannot build Go: the
golden file stays a formatter reference, with a pinned list of the
pipeline-order rules switched off for it. The byte-equal gather test then
loses its Go side. This is strictly worse and needs a new approval.

### Checker controls

- **The golden passes** every rule, with no exemption beyond the two pinned
  lists.
- **One broken copy per rule.** For every rule id, a broken copy of a
  passing prompt is caught **by that id**. This includes B7 and
  D1-onefresh.
- **No dead rules.** Every rule inspects at least one line somewhere in
  the generated set, so no rule is dead code.
- **Every commit** runs the checker over the golden file, the seed set and
  the exam, with 0 violations expected.
- **Exemption pins.** One test pins the exact 4 shared-origin names. One
  test pins the healthy-origin rule. One test asserts no stored read label
  contains `{`.

### Rewrites forced by the deleted fields

These must change in the same commit that deletes the fields:

- `tests/test_catalog.py`: the functions at `:153`, `:195`, `:203`.
- `tests/test_cases.py`: the functions at `:280`, `:301`, `:422`.
- `tests/test_generate.py`: the functions at `:170`, `:191`, `:388`.
- `generate.py:451`, the `entry.contradiction` gate in `probe_sets`,
  or the module fails to import.

The `probe_sets` guard and its docstring (`generate.py:375-395`) are
rewritten to use `job1_entries()`.

### IS-20, fix A

`generate(seed, size)` appends the `worker-containerd-stop` self-paired
multi row outside the counted loop (`generate.py:190-203`). Fix A makes
that row take one of the multi slots `CASE_MIX` already counts. New test:
`len(generate(seed, size)) == size`.

### The TDD map

Each decision, the test that proves it, and what that test shows on
`main` today.

| Decision | Test | On `main` today |
|---|---|---|
| Gather order and budget (D1) | New `gather.py` test: events, describes, logs per workload; 8 reads in total | No gather module |
| Starved candidate → unverified → job 1 (D1) | New gather test whose workloads need more than 8 reads | Multi reads are hand-built per workload |
| Registry outcome from events text (D1) | New test where the events text decides the registry outcome | The outcome is a hand-set field |
| Registry count counted (D1) | New test: the printed count equals the pull-failing workloads in scope | The count is typed in |
| Image threading (D1, minor #12) | New test: every registry and refused read carries the row's image | 12 of 801 rows show `image "":` |
| `pair_candidates` (D1, IS-3) | Port of `prime_test.go:148, 174, 188` | 28 of 801 rows break it |
| `safetext_line` port (D1) | Port of `safetext_test.go` vectors | No port |
| `job1_entries()` (D2) | New catalog test: exactly the 17 names | No such function |
| Attributed distractor `aux-0` (D2 A) | New distribution test over attributed rows | Not built |
| Positional decoys (D2 C) | New test: node branch uses `worker-1` or `worker-2`, PVC branch uses `aux-0` | Not pinned |
| Pads sort first (D2 D) | `max(PAD_PVCS) < min(PVCS)`, and no entry names a pad | No sort test |
| Contradiction gold follows the rules (D2 F) | `tests/test_oracle.py:252` becomes 0 misses | Fails: 19 misses |
| `contradiction_events` go into the events read (D2 F) | New test per entry | Lines are typed into a separate read |
| Multi finding lines (D2 H, IS-1) | New test: every multi workload block has an `issue:` line | 0 of 105 rows |
| Multi report order (D2 H, IS-7) | B1 broken copy | Already sorted; guard only |
| One node table per row (D2 H, IS-19) | New test: two workloads sharing a node show one scan reason | 25 of 105 rows |
| Filled origin label (D2 H) | New test: no label contains `{` | 19 of 35 rows |
| Thin evidence gold (D2 H) | New test: a starved workload missing a keyword answers `none_of_these` at low confidence | Not enforced |
| Multi probe raises on a starved constituent (D2 I) | New test | No check |
| coredns `-c coredns` (D2 J, IS-17) | TXT-IS17 over generated rows | 31 of 801 rows |
| Cluster-health block (D2 J, IS-21) | New test for the block function, plus B7 | 0 of 801 rows show it |
| K3 strings (D3) | One exact-string test per entry | 14 entries differ |
| Restarts at least 3 (D3, IS-14) | TXT-IS14 plus a draw test | Draws start at 1 |
| K2 and K4 (D3, IS-16) | New test: the describe has four conditions; `read_text` raises on bare `Ready=False` | No shared constant |
| K5 scheduler strings (D3, IS-9) | One exact-string test per entry | No suffix |
| P1 swap and the new entry (D3) | `tests/test_catalog.py:117` rewritten; new entry tests | 5 impossible PVC decoys |
| Keyword grounding (D3) | Exposure test per changed entry | 11 entries not grounded |
| The checker (D4) | `tests/test_checker.py`: golden, broken copies, no dead rules | No checker |
| C1-cause (D4) | Broken copy with a made-up cause | 154 of 801 rows |
| C1-conf (D4) | Broken copy with a wrong tag | 45 of 801 rows |
| Exemption pins (D4) | The two pin tests | No pins |
| G2 and G3b (D5) | Paste, echo and hedge bot tests; gold passes every guard | Paste bot 0.5352, hedge 0.9437 |
| Corpus reroute (D5) | New test: the 31 rows carry no decided line | Built as decided rows |
| Thin-row provenance (D5) | New test: every thin row hides at least one keyword | Passes today; pinned |
| IS-20 fix A | `len(generate(seed, size)) == size` | Returns `size + 1` |

## Run order

`kv-eval --replay` cannot help here: it re-scores old replies to old
prompts, and this spec changes the prompts.

1. **Merge this spec.** Regenerate the exam and the training build. Run
   the suite, the checker and the oracle tests. Re-pin by hand with a dated
   `contract/PIN.md` entry, including the multi curriculum pin's own
   re-measure. Run the 0920 checkpoint live against the new exam (about
   2 h 20 min, with `--endpoint`). This shows how much of 0920's job-2
   score came from copying the prompt.
2. **Do Spec 4.** Regenerate, re-pin, and run 0920 live again. This
   separates Spec 4's effect from this one's.
3. **Retrain once** (about 32 hours, CPU recipe), only after both specs
   land. Retraining between them would mix two effects into one number.
4. **Run the untuned baseline once** on the final exam (about 2 h 20 min).
   Its exported model already exists, so there is no export step.

Steps 1, 2 and 4 are diagnostic. Each is recorded in `docs/model-card.md`
as a dated checkpoint. None of them gates anything.

## Success criteria

- Every generated row outside the pinned exemptions passes every checker
  rule: the golden file, the seed set and the exam pool, 0 violations.
- The golden file is re-captured through kubeagent's real pipeline, and the
  byte-equal gather test passes.
- Every rule has a broken copy caught by its own id, and no rule is dead.
- 0 of the 618 unsupported multi job-2 labels remain: every multi job-2
  gold cause is supported by its own block, or is `none_of_these` under
  the thin-evidence rule.
- The exam matches the Design 5 tables, or the plan stops and reports.
- Keyword exposure is 100% on every keyword-graded job-2 workload,
  measured.
- The guarded paste bot stays under `JOB2_BAR`, measured. The gold answer
  passes every guard on every exam row.
- `len(generate(seed, size)) == size`.
- `pytest` and `ruff` pass on every commit.
- No pin moves without a dated comment. No test runs with `-update`.
- No bar moves: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9.
