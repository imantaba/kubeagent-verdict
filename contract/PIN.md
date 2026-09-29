# Contract pin

This directory pins the interface kubeagent-verdict trains against.

- **Pinned against:** kubeagent **v1.24.0** — `scan --investigate` local
  verdict mode, verdict contract **v1** (prose-versioned in kubeagent's
  `website/docs/features/diagnostics.md`), tag `v1.24.0`, commit
  `15ec5649bbd2d07558eae945b71430afc8f231fd`.
- `system_prompt.txt` — the byte-exact `verdictSystemPrompt` constant from
  `internal/investigate/local.go`.
- `golden/user_message.txt` — the byte-exact output of kubeagent's
  `buildVerdictPrompt` for the cluster in `tests/fixtures/gather_fixture.yaml`,
  captured by a build-tagged Go test run inside an unpacked `git archive` of
  kubeagent. The harness is `contract/capture/kv_capture_test.go.txt` in
  this repository. Its header holds the seven steps: copy it in as
  `internal/investigate/kv_capture_test.go`, run it, and copy the files it
  writes back.
- `golden/input.json` — the structured mirror of that capture's inputs,
  which the harness writes from the YAML fixture. The `next_step`/`command`
  strings are kubeagent's own suggestion output.
- `golden/answer.json` — a contract-valid answer for the fixture, used as a
  shape reference by tests.
- `tests/fixtures/rules_golden.json` — what `hypothesis.Decide` and
  `hypothesis.Shared` produced during capture: the ten scoped workloads'
  rule candidates and decisions, plus the shared-cause lines and the eight
  bounded reads. `dataset/rules.py`'s tests replay it and must match the
  captured decisions field for field.
- `tests/fixtures/gather_go/` and `tests/fixtures/gather_go_logs/` — the ten
  stage dumps of the same run, one folder per fixture. Their README gives
  the line format. `tests/test_gather_byte_equal.py` rebuilds each dump from
  the Python port and compares it byte for byte.

## Re-pin procedure (when kubeagent changes the contract)

kubeagent's diagnostics.md prose contract is the tripwire: a new contract
version there means re-pinning here. Run the seven steps in the header of
`contract/capture/kv_capture_test.go.txt` against the new kubeagent tag,
update `contract.py`'s renderers and the dataset port until the golden and
byte-equal tests pass again, bump the version named in this file, and
retrain.

## Port drift — kubeagent internals this pin also depends on

The prompt shape is not the only thing that can drift. A kubeagent change
to any of these needs the same re-pin, even when
`website/docs/features/diagnostics.md`'s version number does not move:

- `verdictSystemPrompt` (the system message constant);
- `renderCandidates` (the candidates section's renderer);
- `hypothesis.Decide` (which candidates get decided, and how);
- `hypothesis.Shared` (the shared-cause lines above the model's summary);
- `maxCandidatesPerWorkload` (how many candidates a workload's section can
  carry);
- the gather's three read formats — `reader.go`'s node, PVC and event
  blocks — since a reformatted read is a reformatted prompt even when
  nothing else changes.

Watch kubeagent's own CHANGELOG for these names, not just the prose
contract version.

## Capture record (v1.24.0, gather capture)

- Captured from kubeagent tag `v1.24.0`, commit `15ec5649bbd2d07558eae945b71430afc8f231fd`.
- Harness: `contract/capture/kv_capture_test.go.txt`. It runs kubeagent's own
  pipeline over two YAML fixtures, in `scan.go`'s order: `clusterhealth.Assess`,
  `inventory.Prioritize`, the three `rootcause` annotators, `confidence.Annotate`,
  then `flaggedScope`, `gatherEvidence`, `Decide`, `Shared` and
  `buildVerdictPrompt`. The seven steps are in its header:
  1. note kubeagent's `git status --short`, `git archive v1.24.0` into a
     scratch folder, and count the tag's files with `git ls-tree`;
  2. copy the two fixtures and the harness into the scratch folder;
  3. unpack the archive, check the file count matches (748 both times), and
     copy the harness in as `internal/investigate/kv_capture_test.go`;
  4. run `go test -count=1 -tags goldencapture -run TestCaptureVerdictGolden
     ./internal/investigate` with `KV_FIXTURE`, `KV_FIXTURE_LOGS` and
     `KV_GOLDEN_DIR` set;
  5. copy the goldens and both dump folders back, and record the tag and
     commit here;
  6. check the fixture still reaches every rule path the old
     `rules_golden.json` did, and still refuses the reads of node worker-7,
     PVC aux-1 and img/seven's events;
  7. remove the scratch folder and check `git status --short` prints what
     step 1 printed.
- Files: `contract/golden/input.json`, `contract/golden/user_message.txt`,
  `contract/system_prompt.txt` (unchanged, byte for byte),
  `tests/fixtures/rules_golden.json`, and the dumps in
  `tests/fixtures/gather_go/` and `tests/fixtures/gather_go_logs/`.
- kubeagent's `git status --short` printed ` M .gitignore` before and after.
  kubeagent was not changed, and the scratch folder was removed.
- **Why there are two fixtures.** The gather stops after 8 reads. The main
  fixture spends all 8 on the reads rule-path coverage needs, before it
  reaches a crashed container, so its log dump holds no log read.
  `gather_fixture_logs.yaml` is a small healthy cluster where 5 of the 8
  reads are log reads. It writes dumps only, no golden file.
- **What changed, and why.** The first capture hand-built its workload
  order and never called `confidence.Annotate`, so the old golden showed
  no `[confidence: …]` tag on any of its 10 workloads, and its order was
  not the one `Prioritize` gives. The new golden has both. The fixture
  changed too, so the scoped roster changed: 10 of 12 flagged workloads
  are in scope (web/shop and web/worker are not). Two more shapes moved
  with it: the cluster line now reads
  `worker-1 NotReady: KubeletNotReady — container runtime is down`, and a
  crash finding with a container gets a `-c <container>` suggestion.
  `golden/answer.json` was edited by hand to the new roster.

## Dataset pin moves

The exam's two hashes live in `tests/test_shared_origin_training.py`:
`FROZEN_SLICE_SHA256` over every row before the ten
`shared_origin_decoy_probe` rows (239 rows) and `EVAL_SET_SHA256` over all
249. Until 2026-09-26 they were over 242 and 252 rows. Until 2026-09-24 the
first was `FROZEN_253_SHA256`, over 253 rows of 263. A third pin,
`GRADED_VIEW_SHA256` in `tests/test_exam_graded_view.py`, hashes the part
of each row the grader reads. They are pinned so a change to the
generators cannot move the exam without someone saying why. This is where
the why is recorded.

- **2026-09-16 — the missing `decided by rules:` line.** Both hashes moved.
  Not one of the 263 prompts carried that line, though job 1 grades the
  model on echoing it. The renderer in `contract.py` was right; the
  generators in `dataset/cases.py` built every workload without setting
  `decided`, so the renderer had nothing to print. The line now renders on
  all 157 rule-decided workloads and on no undecided one. The same commit
  restored the `decoy_cause` key in every decoy row's meta — the decoy-rate
  and length-gap readings both read it, and both were reading an empty
  slice — and re-labelled the ten `shared_origin_decoy_probe` rows from
  `none` to `separate`. Every job-1 and decoy number measured before this
  is retired. The captured goldens under `contract/golden/` did not move:
  they were always right, and `test_user_message_matches_kubeagent_bytes`
  passed untouched across the fix.

- **2026-09-16 — revert the `separate` relabel.** `EVAL_SET_SHA256` moved
  again; `FROZEN_253_SHA256` did not, because the ten affected rows
  (254-263) sit outside the frozen slice. The job-3 label is derived, not
  declared: the design spec (`:247-250`) says a row is `shared` only when
  its rendered lines carry the "share one upstream cause" line, `separate`
  only when they carry the "no shared cause" line, and `none` when they
  carry neither. The ten `shared_origin_decoy_probe` rows carry neither
  keying line, so the value the rules produce is `none`. The previous
  entry's relabel to `separate` overrode that derived value by hand and
  was never derived from anything the rules said; it also contradicted the
  spec's own flat pin that `separate` stays at 0 in the exam (`:473`,
  `:845`). The override is removed; `**r.meta`'s derived label stands
  again. Every job-3 number measured against the `separate` re-pin above
  is retired.

- **2026-09-19 — `_render_shared_origin`'s decided-row fix.** Both hashes
  moved again. A decided victim's row cause and rationale used to render
  the row's formatted `shared_cause` sentence even when the rules had
  already decided that victim on its own local evidence; they now render
  the rules' own answer (`result.cause`, `_rule_rationale(result)`)
  instead, and a `none`-labeled row's summary no longer claims a shared
  cause it did not find — it now says kubeagent's rules did not confirm
  one cause on two or more workloads. The footprint was measured by
  building the exam at the pre-fix commit and at the fixed one and diffing
  every row: exactly 14 of the 263 rows change, byte for byte, and nothing
  else does — the ten `shared_origin_probe` rows (244-253, inside the
  frozen slice, which is why `FROZEN_253_SHA256` moved) plus 4 of the ten
  `shared_origin_decoy_probe` rows (254-263, outside it — the two origins
  whose victims decide the same way regardless of `healthy`; the other six
  decoy rows, whose healthy world decides nothing, do not move). Each of
  the 14 changed rows differs only in the assistant message and, inside
  `meta`, only `expected`/`expected_cause`. The exam's own job 3, oracle-
  read, stays at 1.0 after the fix (5 of 5 `shared`-labeled rows, 34 of 34
  `none`-labeled rows), and the graded-view pin (`tests/
  test_exam_graded_view.py`) passes unchanged, so this re-pin is the two
  hashes only — no other frozen artifact moved.

- **2026-09-23 — answer keys for the shared-origin job-2 workloads.** Both
  hashes moved, and so did the graded-view pin (`tests/
  test_exam_graded_view.py`). Every undecided workload in the two
  shared-origin slices carried `own_cause_keywords: []`, so job 2 scored it
  0.0 whatever the model replied — 20 of the exam's 153 job-2 workloads.
  Each now carries a curated two-word pair: the victim's own pair in the
  healthy world, the scenario's shared pair in the broken one. The 22 pairs
  (16 victims, 6 shared causes) live in `dataset/propagation.py`. A decided
  workload still carries `[]`, because job 1 grades it by echo. The
  footprint was measured by diffing the exam before and after: 11 of the
  263 rows change, and in each only `meta` does — rows 248, 249 and 253
  inside the frozen slice (4 workloads, which is why `FROZEN_253_SHA256`
  moved) and rows 255-259 and 261-263 outside it (16 workloads). Not one
  `messages` byte moved; `tests/test_exam_prompt_stability.py` pins that
  against the banked exam. The grader now refuses a job-2 workload that
  names a cause but carries no keywords, instead of scoring it zero. The
  paste-the-prompt bot rises from 0.366 to 0.497, because all 20 print
  their answer on their own menu. A job-2 number measured before this was
  scored by a grader that zeroed those 20 workloads for every reply, so it
  does not compare with one measured after.

- **2026-09-24 — the job-2 generator fix.** Both hashes moved, and so did
  the graded-view pin (`tests/test_exam_graded_view.py`). Before the fix,
  `none_of_these` and `wrong_attribution` built the same prompt for 27 of
  28 catalogue entries and gave it two different answers, so the model
  could not learn to override a wrong tag. Now one builder makes every
  undecided row, and the prompt decides the answer. `FROZEN_253_SHA256` is
  renamed `FROZEN_SLICE_SHA256`: the `none_of_these` slice falls from 19
  rows to 8, so the exam falls from 263 rows to 252 and the frozen slice
  from 253 to 242. The frozen slice still means every row before the ten
  `shared_origin_decoy_probe` rows, and a test pins its length. This time
  rendered bytes move, not only `meta`, so the new exam is a new baseline:
  no number on it compares with one from before. The banked exam the
  prompt-stability test reads is now `out/dataset-0924/test.jsonl`. The
  footprint, in commit order, measured by diffing the exam before and
  after each change:
  - The catalogue stopped doubling the `log cause: ` prefix and quotes the
    container in `restart-loop`'s evidence. 41 rows change, in the user
    message only.
  - One builder makes every undecided row. All 19 `own_cause` rows change
    their user message, and 16 of them their gold answer and meta. All 19
    `misattribution_probe` rows change their user message. 9 of 19
    `wrong_attribution` rows change their user message. The held-out rows
    interleave by entry, so every row after the first changed entry
    shifts.
  - A multi-workload row keeps its crash-family log reads, and
    `multi_misattribution_probe` prints the header kubeagent's confidence
    rule gives. 13 of its 19 rows change their user message only.
  - `empty_candidates` answers at the entry's own confidence and keeps its
    log read. 16 of its 19 rows change their gold answer and meta, and 5
    of those 16 also change their user message.

  No other row moves. The paste-the-prompt bot scores 76/142 = 0.5352 on
  job 2, up from 76/153 = 0.4967: the exam lost 11 `none_of_these`
  workloads, none of them keyword-graded. It still scores below
  `JOB2_BAR` (0.7), which does not move. The full per-change footprint is
  in the comment above `FROZEN_SLICE_SHA256` in
  `tests/test_shared_origin_training.py`.

- **2026-09-26 — faithful prompts.** All three hashes moved:
  `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and `GRADED_VIEW_SHA256`. The
  exam falls from 252 rows to 249, and the frozen slice from 242 to 239.
  Rendered bytes moved on all 249 rows, so the new exam is a new baseline:
  no number on it compares with one from before. Every scoreboard number
  banked before this change is retired. The banked exam the
  prompt-stability test reads is now `out/dataset-0926/test.jsonl` (built
  with `--seed 17 --size 8000`: 6,457 train rows, 721 val rows, 249 test
  rows). (2026-09-28: `out/dataset-0928` replaced `out/dataset-0926` that
  day, with the same three counts; see the 2026-09-28 entry. The counts
  below were measured again on `out/dataset-0928` and on the code of that
  day, and none moved: the job 1 / 2 / 3 populations, the bot table, the
  35 of 104 seed `multi` rows with a healthy-origin read, the multi
  curriculum, the thin-row rule and the `node-cordon-diskfull` rows.)

  Why. The old generators typed many prompt lines by hand, and some of
  those lines were ones kubeagent never sends. Now every row gets its reads
  the way kubeagent's gather gets them: the same order and the same budget
  of 8 reads. Each case is built on a shape kubeagent can really produce.
  The catalog prints the detector and kubelet text kubeagent prints. The
  rules decide every winner, so no hand-typed winner is left.

  Per case, old count → new count: `attributed` 53 → 22, `own_cause`
  19 → 51, `truncated` 19 → 17, `injection` 19 → 17, `empty_candidates`
  19 → 20, `wrong_attribution` 19 → 20, `positional_probe` 19 → 17,
  `misattribution_probe` 19 → 20, `multi_misattribution_probe` 19 → 20,
  `contradiction_probe` 19 → 17. `none_of_these` (8),
  `shared_origin_probe` (10) and `shared_origin_decoy_probe` (10) keep
  their counts. This matches the spec's table.

  What is graded, measured on the file:
  - Job 1: 157 → 120 workloads. The spec predicted 118.
  - Job 2: 142 → 177 workloads. The spec predicted 179. 169 of the 177
    are keyword-graded (134 before; the spec predicted 171), and all 169
    print every keyword somewhere in the prompt.
  - Job 3: 39 → 40 rows. The labels shared / separate / none go from
    5 / 0 / 34 to 5 / 0 / 35.
  - The spec's counts were 2 off because the node list grew from three
    workers to five, which moved the draws. The `networkpolicy-deny-all`
    victims in `shared_origin_probe` and its decoy probe are now decided
    by the rules on their nodes (4 more job-1 workloads). The
    `node-disk-pressure` pair lost 2 decided victims (2 fewer).
  - The always-`none_of_these` bot scores 8 of 177 = 0.0452 on job 2.

  The footprint, in commit order, measured by building the exam before and
  after each change and matching rows by content:
  - Port kubeagent's text cleaning and event format. 0 rows move.
  - Port kubeagent's evidence gather. 0 rows move.
  - The grader guard (below). 0 rows move; it changes the grader only.
  - Show the cluster-health block kubeagent sends. 150 of the 252 rows
    gain the block in their user message, all inside the frozen slice.
    Nothing else moves.
  - Use the detector and kubelet text kubeagent really prints. 222 of the
    242 frozen rows move: 218 change their user message, 89 their meta and
    6 their gold answer. The decoy probe rows do not move.
  - Check the gather byte for byte against kubeagent. 0 rows move.
  - Build the undecided rows on the gather. 71 rows change their user
    message: `own_cause`, `wrong_attribution` and `misattribution_probe`
    19 each, `none_of_these` 8, `empty_candidates` 6.
  - Build the job-1 rows on the gather. The exam goes from 252 rows to
    251. 137 rows stay byte for byte (127 frozen rows and the 10 decoy
    probe rows). 31 rows the rules do not decide move from `attributed` to
    `own_cause`.
  - Decide the `contradiction_probe` rows by the rules. The exam goes from
    251 rows to 249. The 19 old rows go and 17 new ones come; the other
    232 rows do not move. The new rows name no decoy.
  - Build the `multi` rows on the gather, with five workers in the node
    list. 156 rows move: 152 of the 239 frozen rows and 4 of the 10 decoy
    probe rows.
  - Check every prompt against what kubeagent can send. The checker's
    coredns fix moves 16 rows, one line each (the workload line's restart
    count). The training build moves too: train 6,415 → 6,457 rows, val
    749 → 721.
  - Mask the pod in the suggested fix line as kubeagent does. All 249
    rows move, only in their fix lines: 297 commands (273 in the frozen
    slice, 24 in the decoy probe rows).

  No system message moved in any of them. The full per-change footprint is
  in the comment above `FROZEN_SLICE_SHA256` in
  `tests/test_shared_origin_training.py`.

  The grader guard. Job 2 now zeroes a workload's answer in two cases,
  before it looks for keywords. G2: the answer names one of the row's
  decoy causes. G3b: the answer contains a whole line of the workload's
  own block (its inventory line, its candidate block or its matched
  reads). Both run on the model's raw reply, before the 512-rune cap and
  before keyword matching. A guard that ran after the cap let a paste bot
  slip through, because the cap cut off every line pasted after rune 512.
  The guard matters more now than when it landed: the catalog prints
  kubeagent's own text, and that text names the cause, so 169 of the 177
  job-2 answers are on screen. The keywords no longer hold a paste bot
  down. The guard holds a verbatim paste to 0. (2026-09-28, final review:
  this said "The guard does", which was too strong. A near-copy is a known
  gap: the same own lines with the first word of each line cut score 147
  of 177 = 0.8305 with the guard on, over the 0.7 bar. See the 2026-09-28
  entry.) Job 2, unguarded → guarded:

  | Bot | Spec (old exam) | Measured, old exam (142) | Measured, new exam (177) |
  |---|---|---|---|
  | paste the prompt | 0.5352 → 0 | 0.5352 → 0 | 0.9548 → 0 |
  | echo | 0.5282 (75 of 142) → 0 | 0.5211 (74 of 142) → 0 | 0.9548 → 0 |
  | name the decoy | 0 → 0 | 0 → 0 | 0 → 0 |
  | hedge | 0.9437 → 0.2183 | 0.9437 → 0.2183 | 0.9548 → 0.1808 (32 of 177) |
  | gold | 1.0 → 1.0 | 1.0 → 1.0 | 1.0 → 1.0 |

  "Old exam" is the exam as it was when the guard landed. The spec does
  not say exactly what its echo bot echoes; the test's echo bot scored 74
  of 142, one short of the spec's 75. The gold reply passes every guard on
  every exam row (the guard zeroes 0 of 177), and a test pins that.
  `JOB2_BAR` stays 0.7.

  The checker (`dataset/checker.py`) reads every row the build writes and
  counts the places where it differs from a prompt kubeagent v1.24.0 can
  send. The manifest gains a ninth key, `checker_violations`: per case, how
  many places differ. It is a report and never blocks a write. On this
  build it is 0 for all 16 cases.
  - It has 49 rules: the spec's table plus `TXT-POD`. (2026-09-28: 50
    since `B8` landed; see the next entry.)
  - The four shared-origin cases skip 19 of them until Spec 4 rewrites
    `propagation.py`: the 12 evidence rules and 7 rules that fail on text
    `propagation.py` types itself. The spec named only the 12 evidence
    rules. A test fails if one of the 7 stops firing there.
  - A `multi` row's healthy-origin read skips 7 rules. 35 of the 104
    `multi` rows of `generate(17, 800)` have that read (the spec said 35
    of 105).
  - It is slower than the spec guessed: 0.64 s for the 800-row seed set
    and 6.58 s for the exam pool, against about 0.17 s and 1.7 s.
  - Measured at the branch base, its counts matched the spec for IS-1, 3,
    8, 15, 17 and 21. The others differed, each for a known reason:
    IS-2 (213 rows of 246, spec 618 of 718: the seed set, not the training
    build), IS-4 (168, spec 147: the rule also checks candidate order),
    IS-9 (73 lines in 47 rows, spec 164 lines in 24: 115 of the spec's
    lines sit in shared-origin rows, which skip the rule), IS-11 (24, spec
    50: 18 are in exempt rows, and the rule checks only the three literals
    in the inventory), IS-16 (31, spec 13 objects: E7 accepts a header
    with no conditions, and D3 catches them) and IS-19 (50 rows, spec 25
    of 105: the rule covers both duplicate shapes).
  - It found two bugs. `coredns-corefile-broken` could draw as
    few as 1 restart, but its finding says `restartCount=6` and kubeagent sums a
    workload's restarts, so it now draws at least 6. And the golden
    answer gave `img/solo` the cause `registry mirror.invalid`. Only one
    workload fails to pull from that registry, below kubeagent's threshold
    of two, so the answer is now `none_of_these`, at `low` as before.
  - `TXT-POD` fired on every row before the fix-line change (800 of 800
    seed rows, 8,249 of 8,249 exam-pool rows) and on none after. The fix
    line now names `<pod>`, as kubeagent's prompt does. A finding on the
    workload object itself (RolloutStuck) keeps the workload's name, but
    no catalog entry emits that shape, so only the Go test vector and the
    checker's own test cover it. 28 exam fix commands
    (`shared_origin_probe` 14, `shared_origin_decoy_probe` 14) now name
    no pod for their workload, and that pod name appeared nowhere else in
    the prompt. That matches kubeagent.
  - One shape has no rule yet: `deployment-bad-image-tag` rows in
    `empty_candidates` (2 in the seed set, 1 in the exam, 20 in the
    8,000-row pool).

  The `multi` rows, measured on the new training build:
  - A `multi` block now prints each workload's finding lines, and its reads
    come from one gather over the whole row.
  - The oracle's multi curriculum is 1,207 job-1 workloads in train and
    163 in val. Before this change it was 1,226 and 132. (2026-09-28:
    this said "The spec predicted 1,226 and 132", but those were the
    counts before the change, not a prediction. Measured again on
    `out/dataset-0928`: still 1,207 and 163.)
  - The thin-row rule (`_thin_multi`) fires 0 times (ruling 75): every
    starved undecided workload in both builds still shows its keywords.
    Unit tests reach both sides. (2026-09-28: this said "The spec
    expected it to fire on some rows", but the spec gives no count.
    Measured again: 0 times in 1,134 checks on the 8,000-row pool and 0
    in 116 on the 800-row seed set. The exam has no `multi` rows, so the
    rule never runs there. The pool has 14 starved undecided workloads
    and the seed set 1; the bank has 11, 10 in train and 1 in val. All of
    them show their keywords.)
  - Job-2 labels in `multi` rows that name a cause their prompt does not
    show: 618 before, 0 now.
  - `generate(seed, size)` returns exactly `size` rows. It used to return
    `size + 1`.

  Left for Spec 4 (known, not fixed here):
  - `node-cordon-diskfull`'s own cause, rationale and keywords
    (`"node"`, `"pod"`) still claim disk pressure, which no line of the
    workload's own block shows. 10 exam rows carry that gold, and 213
    train and 13 val rows.
  - `coredns-corefile-broken` lives in the drawn namespace, not
    `kube-system`; its restart count is pinned; and it is the one named
    exception to the thin-row test.
  - Some event wording is not the kubelet's (`memory-limit-oomkill`
    among others).
  - `propagation.py` types its own candidate, describe and scheduler
    text, and 13 healthy-origin `describe node …` reads in
    `generate(17, 800)` are hand-typed (6 of them with a suffix such as
    ` (CSI status)`).
  - 14 shared-origin exam victims carry the gold `node worker-N
    (NotReady)`, which no line of theirs names.
  - `volume-mount-error`'s P1 decoy.
  - No node carries the `node.kubernetes.io/not-ready` taint.
  - A flagged `kube-system` workload outside the first 10 gets a system
    line in Go but not here.
  - A `not_read` object's fresh value is typed by hand and is not checked
    against Go.
  - The candidate-cap marker is no longer in the golden; only a unit test
    covers it.

  The golden re-capture is recorded under "Capture record" above.

- **2026-09-28 — final review fixes.** All three hashes moved again:
  `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and `GRADED_VIEW_SHA256`. The
  exam is still 249 rows and the frozen slice still 239. Only user
  messages moved. No gold answer, system message, `meta` field or decoy
  moved, so the graded populations stay the same: job 1 120 workloads,
  job 2 177 (169 keyword-graded), job 3 40 rows. 20 of the 249 rows show
  new bytes, so a score on this exam compares with one on the 2026-09-26
  exam only over the other 229 rows. The banked exam the
  prompt-stability test reads is now `out/dataset-0928/test.jsonl`. It
  was built with the same command as `out/dataset-0926` (`--seed 17
  --size 8000`), and it has the same counts: 6,457 train rows, 721 val
  rows, 249 test rows. `out/dataset-0926` stays on disk, unused.

  Why. A final review found rows that leave out lines kubeagent prints.
  kubeagent's root-cause pass lists on every workload of a row every node
  the row names as down, and rules it out where no pod of that workload
  runs (`internal/rootcause/rootcause.go`, `Annotate`, lines 24-56). It
  does the same for claims: every workload lists every broken PVC another
  workload of its namespace names (`AnnotatePVC`, lines 177-222).
  - The `multi_misattribution_probe` rows listed each workload's own node
    only. Now each workload also lists the other workloads' nodes, ruled
    out, and their claims in its own namespace, ruled out.
  - The `multi` rows left out a same-namespace workload's claim. Now they
    list it, ruled out.

  The probe's decoys are still built from each workload's own candidates
  only, so the grader counts the same decoys as before.

  The footprint, measured by diffing each file against `out/dataset-0926`:
  - Exam: 20 of 249 rows moved, all 20 `multi_misattribution_probe` rows.
    Each changed its user message only: 36 lines added and 0 removed, all
    of the form `considered node worker-N (NotReady): ruled out — no pod
    of this workload is scheduled on it`. No other case moved, the ten
    `shared_origin_decoy_probe` rows included.
  - Train: 12 of 6,457 rows moved, all `multi`, one ruled-out PVC line
    each.
  - Val: 1 of 721 rows moved, a `multi` row, one ruled-out PVC line.
  - The 8,000-row pool moved 22 `multi` rows. The split drops 9 of them.

  The hashes, old → new:

  | Pin | Old | New |
  |---|---|---|
  | `FROZEN_SLICE_SHA256` | `9d548bee64a9519a3ca080fcde14846b4f0beb0fac4381c582002b3828dbdde6` | `48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69` |
  | `EVAL_SET_SHA256` | `85388c7e17b60d0c4dc6dfc3448b0ff82226e028ecebf6443f20d00082163b5f` | `b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653` |
  | `GRADED_VIEW_SHA256` | `3118c0dac18db802c5db5574e4fc5be8420fd7651a144bf6ff498701f3c8af4c` | `396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108` |

  The bank, `out/dataset-0928`, by sha256:
  - `test.jsonl`: `9396e347a2336f4ea08fb0ef5283fbceb37c496f1199096d1cd23bf4e8cea48e`
  - `train.jsonl`: `e384aee64d7d06d7c59a4f577a09f425feefdff9cbf038c21333ec378aa0f915`
  - `val.jsonl`: `2138d992b25bb003d3a4277879c14b4aea1fb90add59994d4a1523059fe94d83`

  The checker gained a 50th rule, `B8`, which catches this gap. On a row
  with two or more workload blocks, every block must list every down node
  the row names, and every PVC another block of its namespace names. A
  block cut at the candidate cap is exempt. Places it flags:

  | Set | Before the fixes | After |
  |---|---|---|
  | exam (249 rows) | 20 rows, 36 places (missing node lines) | 0 |
  | 8,000-row pool | 22 rows, 22 places (missing PVC lines) | 0 |
  | 800-row seed set | 3 rows, 3 places (missing PVC lines) | 0 |

  The manifest's `checker_violations` stay 0 for all 16 cases. The pod
  slot rule `TXT-POD` also got stricter. It found nothing new: 0 on the
  exam, the pool and the seed set. Two more changes moved 0 rows: the
  ruled-out menu lost a registry count nothing read, and a test now pins
  the Unicode tables the text port matches (15.0.0, the version Go 1.26
  and Python 3.12 share).

  The grader: one fix, two known gaps pinned, and no bar moved (0.9 /
  0.7 / 0.9).
  - The fix. G3b reads a workload's own block, and that block includes
    the evidence reads that belong to it. A read used to go to a workload
    by name prefix, so `describe pvc web/cache-0` went to `web/cache`
    although it sat in `web/indexer`'s gather group. Now a read goes to
    the gather group it sits in. Each group opens with an `events
    <ns>/<pod>` read. On the exam no own-block line moved (4,004 before
    and after). In the 8,000-row pool 1 row moved: 2 lines went from
    `web/cache` to `web/indexer` (172,051 lines before and after). The
    job-2 bot table did not move: paste 0, echo 0, name the decoy 0,
    hedge 0.1808 (32 of 177), always-`none_of_these` 0.0452 (8 of 177).
  - The gold net. The gold answer passes the guard on every exam job-2
    workload (0 of 177 zeroed). A new test checks the 8,000-row training
    pool too: 0 of its 9,426 job-2 golds are zeroed.
  - Gap 1, a near-copy. The guard holds a verbatim paste to 0. A bot that
    pastes each job-2 workload's own inventory entry and own reads, with
    the first word of each line cut, keeps no whole line, so G3b never
    fires. It scores 147 of 177 = 0.8305 with the guard on and with it
    off, over the 0.7 bar.
  - Gap 2, the registry host. A right bad-image-tag answer that adds the
    host ("… in the registry registry.example.com") contains the decoy
    `registry registry.example.com`, so G2 zeroes it. 30 of the 177 job-2
    workloads have that gold answer, and 29 of them carry the decoy. The
    gold reply with the host added scores 148 of 177 = 0.8362. Plan
    ruling 37 accepted this decoy because the gold answer passes.

  Tests pin both gaps, and the model card lists them as known limits 11
  and 12. Closing either one changes the grader, so it needs a change to
  the spec. (2026-09-29: Spec 4a closed gap 1 for cut pastes, and closed
  gap 2. See the next entry.)

  Left for Spec 4 (known, not fixed here; 2026-09-29: split into "Done
  in 4a" and "Left for 4b" in the next entry):
  - B4: three arms the generator reaches have no Go capture to check
    them byte for byte (the candidate-cap line, a registry auth sentence
    and the no-pull-event sentence). Covering them needs a new capture.
  - B6: a refused read's message is shorter than the API server's real
    text.
  - C9: the guard's text cleaning has no NFKC step, so a look-alike
    character (say, a full-width letter) can slip a copy past it.
  - D4: `multi`'s decoy list is keyed on each object's intent, not on
    what the prompt shows, so it can hold a decided workload's own gold.
    No grader reads it today.
  - A node's state at scan time: a cordon and a pressure condition.
  - A stronger G3b.
  - A narrower G2.

- **2026-09-29 — Spec 4a, the grader guard and weak keywords.** All three
  hashes moved: `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and
  `GRADED_VIEW_SHA256`. Only `meta` moved. No message moved: all 7,427
  rows show the model the same bytes as `out/dataset-0928`. The exam is
  still 249 rows and the frozen slice still 239. The graded populations
  stay the same: job 1 120 workloads, job 2 177 (169 keyword-graded),
  job 3 40 rows. A model's replies to the 0928 exam are its replies to
  this one, so they can be re-scored with no model call. The model card
  records 0920's replay.

  The planned `meta` changes:
  - Every workload carries a new key, `own_cause_must_not`: words that
    zero an answer that holds them. It is non-empty on the job-2
    workloads of five catalog entries and empty everywhere else.
  - The two init bad-tag entries' `own_cause_keywords` gain `init`. The
    row-level `expected_own_keywords` on those entries' `own_cause` rows
    move the same way.

  The seven entries whose keys changed:

  | Entry | Required (was) | Required (now) | Must not |
  |---|---|---|---|
  | `memory-limit-oomkill` | memory, limit | same | init container |
  | `deployment-bad-image-tag` | image, registry | same | init container |
  | `container-start-error` | container, image | same | init container, tag |
  | `init-errimagepull` | tag, registry | init, registry, tag | — |
  | `init-imagepullbackoff` | registry, tag | init, tag, registry | — |
  | `oversized-job-unschedulable` | memory, node | same | cordon, pressure |
  | `volume-mount-error` | volume, pod | same | provision |

  "Init container" is three must-not words: `init container`,
  `init-container` and `initcontainer`. Never bare `init`, which
  "initial" and "initialize" would trip.

  The gate. Before the re-pin, a script compared `out/dataset-0929` with
  `out/dataset-0928` row by row. With the planned changes taken out, 0
  rows differ, in messages or in `meta`. What it counted:

  | Split | Rows | Workloads | With must-not words | Init keys moved | Row-level keys moved |
  |---|---|---|---|---|---|
  | train | 6,457 | 10,991 | 778 | 271 | 115 |
  | val | 721 | 1,225 | 85 | 33 | 14 |
  | test | 249 | 297 | 57 | 12 | 4 |

  The hashes, old → new:

  | Pin | Old | New |
  |---|---|---|
  | `FROZEN_SLICE_SHA256` | `48787d98334850d255a1e70b7a1bf3aeaa09cf4c43892b302cced99d04ff4d69` | `f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a` |
  | `EVAL_SET_SHA256` | `b8f75125a48d846388a852b1f88996630ae46c6ce853b86748d122fd7bbb5653` | `a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2` |
  | `GRADED_VIEW_SHA256` | `396844d5b57420ea983c36e75976ef69f9b616938fc8430be776a4b6d137a108` | `efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4` |

  The bank, `out/dataset-0929`, built with the same command (`--seed 17
  --size 8000`), by sha256:
  - `test.jsonl`: `dd3834efe5b986ec2591ccdf1b0be3e86dec1dd5d235b2a8ae17b219c5dcb2f5`
  - `train.jsonl`: `6b8da804eaf2de616979d4296c2950f6522d0e0f0369c350770b36340182042f`
  - `val.jsonl`: `e0e79322e3a533f19c5ea6f670ce160ce65a54196b131835a3b0aac7454b649b`

  `out/dataset-0928` stays on disk. The prompt-stability test still reads
  its exam: that test reads messages only, and no message moved.

  The grader: four changes, and no bar moved (0.9 / 0.7 / 0.9).
  - One cleaning step. `_norm_cause` applies NFKC first, so a full-width
    letter reads as the plain one. The guard, the keyword match and the
    must-not match all go through it. `none_of_these` is still an exact
    match.
  - G3b crops. It also zeroes an answer that holds an own line with its
    first 1 or 2 words cut, as long as 3 words are left. Gap 1 of the
    previous entry is closed for cut pastes.
  - G2 skips a decoy under 3 words. On the exam that is only `registry
    registry.example.com`. Gap 2 of the previous entry is closed.
  - `decoy_rate` counts job-2 workloads only. A decided workload's right
    answer can be the same text as a decoy, and it no longer counts as
    naming one. The gold reply and 0920 both read 0 of 128 rows.

  Job 2, the bots, before → after:

  | Bot | Before | After |
  |---|---|---|
  | own lines, first word cut | 0.8305 (147 of 177) | 0 |
  | own lines, first 2 words cut | 0.8305 (147 of 177) | 0 |
  | own lines, first 2 words swapped | 0.8644 (153 of 177) | 0 |
  | hedge | 0.1808 (32 of 177) | 0.3446 (61 of 177) |
  | gold | 1.0 | 1.0 |
  | gold with the registry host | 0.8362 (148 of 177) | 1.0 |

  Weak keywords: 34 pairs of exam keys where one story's gold answer
  passes another story's key, now 21. A test pins the 21 exactly.

  Done in 4a, from the previous entry's list:
  - C9: the NFKC step.
  - A stronger G3b, for cut pastes. A clause lifted out of the middle of
    a line still passes; model-card limit 11 says why it must.
  - A narrower G2.

  Left for 4b, from the same list:
  - B4: three arms with no Go capture.
  - B6: a refused read's message is shorter than the API server's real
    text.
  - D4: `multi`'s decoy list is keyed on each object's intent.
  - A node's state at scan time: a cordon and a pressure condition.

  Found by the final review, also left for 4b:
  - G3b zeroes a right answer written in a `log cause:` label's words,
    on 24 of the 177 exam job-2 workloads. Model-card limit 13.
  - A must-not word is a plain substring, and it cannot see "not".
    Model-card limit 14.
  - G2 now skips `registry registry.example.com`, so a wrong answer that
    says that registry is unreachable passes the bad-image-tag key on
    all 29 bad-image-tag workloads that carry that decoy. The key has no
    must-not word for a registry fault.
  - NFKC leaves a non-ASCII hyphen (U+2010 to U+2015) as it is, and
    `init_container` is not one of the three spellings. An init-container
    answer written either way passes the main-container keys.
  - `named_decoy` still compares the raw answer with each decoy, exact
    match. It skips the cleaning step, so a decoy copied with a capital
    letter or a trailing period does not count as naming it.

  Every item on the 2026-09-26 entry's "Left for Spec 4" list is still
  open too. The spec's "Left for 4b" list, in
  `docs/superpowers/specs/2026-09-29-grader-guard-design.md`, adds what
  was found while writing 4a, the 21 weak pairs among them. It does not
  repeat the items above or the 2026-09-26 list. 4b starts from all
  three lists.
