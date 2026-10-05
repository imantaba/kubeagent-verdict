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

## Capture record (v1.24.0, cluster and registry capture)

- Captured from kubeagent tag `v1.24.0`, commit `15ec5649bbd2d07558eae945b71430afc8f231fd`.
  Go: `go1.26.4 linux/amd64`.
- The capture ran from a `git archive v1.24.0` copy in a scratch folder; the
  kubeagent checkout was not touched.
- Harness: `contract/capture/kv_capture_test.go.txt`. It now has four modes,
  each with its own fixture env var: main (`KV_FIXTURE`), logs
  (`KV_FIXTURE_LOGS`), cluster (`KV_FIXTURE_CLUSTER`) and registry
  (`KV_FIXTURE_REGISTRY`). One `go test -count=1 -tags goldencapture -run
  TestCaptureVerdictGolden ./internal/investigate` run writes all four dump
  folders. The cluster mode also runs three pure scan steps in `scan.go`'s
  order: `svchealth.Assess`, `svchealth.AnnotateEndpointCause` and
  `netpolicy.Annotate` (before `rootcause.Annotate`).
- New fixtures: `tests/fixtures/gather_fixture_cluster.yaml` (16 nodes, 19
  workloads, 13 services) and `tests/fixtures/gather_fixture_registry.yaml`
  (3 nodes, 6 Deployments that fail to pull).
- New dumps: `tests/fixtures/gather_go_cluster/` and
  `tests/fixtures/gather_go_registry/`, 11 files each, plus a README.
- The 22 old dumps (`gather_go/` and `gather_go_logs/`) and the four golden
  files came out of this run byte for byte as they were. Nothing under
  `contract/golden/` moved.
- The Python tests check the registry dumps byte for byte. The cluster dumps
  are checked only for dump 0 until the Python cluster-health code exists.
- The harness gates its logs check on `len(logRead) > 0`, because the cluster
  and registry fixtures read no logs.
- Built rows reach the registry no-pull sentence 0 times. The capture proves
  its bytes; reaching it needs a victim whose events have aged out.
- **What the cluster capture does not pin.**
  - Services s11 to s13 are cut by the prompt's 10-issue cap. They are the
    "backs DaemonSet", "backs Deployment" and "backs StatefulSet" wordings
    (s11, s12, s13). The names are ordered so the five wordings of
    `AnnotateEndpointCause` print first: s01 one down node, s02 "2 down
    nodes", s03 "1 matching pod, 0 ready", s04 "3 matching pods, 0 ready",
    s05 "the selector matches no pods". The harness checks all ten printed
    service lines and that none of s11 to s13 prints. The three cut
    "backs ..." wordings have no byte check.
  - n15's node attribution is the 12th of 12 candidates for each workload,
    and the prompt keeps 8. The line "decided by rules: node n15 (NotReady)"
    still shows.
  - No node describe beyond n15 happens. The 8 reads go to events reads before
    ks-ds and ks-e are reached.
- sha256 of the fixtures:

  | File | sha256 |
  |---|---|
  | `gather_fixture_cluster.yaml` | `c060cfe9d1d2bd74c2629d1024768b9949c6c71d7026da73d4f4d6c1766dae37` |
  | `gather_fixture_registry.yaml` | `48811313b35ad24e27dc4e670a321fe6018a35b447c1a6baf61f9415ff308b05` |

- sha256 of the dumps (`sha256sum` format). `05-pvcs.txt` is empty in both
  folders, and `04-nodes.txt` is empty in the registry folder
  (`e3b0c442…`).

      558971d5f110a8127ad1aa5898249777341d5edc7ff60d991adb6f34e6a80e21  gather_go_cluster/00-fixture.json
      72ae75b4b3ee69db15d16bab957445a7fda52f15c247a4fb284d38ba4acbabe2  gather_go_cluster/01-order.txt
      0dab56fb3d2835692df3988817f7e50224979e4c0c27fa70daf47c5cbb649106  gather_go_cluster/02-events.txt
      877956fd80b0dcecd3f3f0737a7f2aa179d1595b4b6c5d5ed7b50640ad69f5f0  gather_go_cluster/03-candidates.txt
      66bc3439671a6efc8c9e6422101daf0d754cb44a43d11d3ad44b9c32c40c943f  gather_go_cluster/04-nodes.txt
      e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  gather_go_cluster/05-pvcs.txt
      34a2db7f46ce5d662f86998706a5eb158a8386f6857d6ac92f4b89d0579c998d  gather_go_cluster/06-logs.txt
      884f6dc71e7caaf660760e730ad83f3a30977a7a4ac7436aac017be67bca4322  gather_go_cluster/07-trail.txt
      e49370ca72bc319e0cd13862361edcf101c628f194ba784ea1dd16ca0d6ac63c  gather_go_cluster/08-bundle.txt
      ec5591ac409d83531f81ade0139c0c7903eb2be9532c5d859a2454877e6ea992  gather_go_cluster/09-decide.txt
      1ed0774fb5a8af4bb00a7c9065229a1c2a767228ea20ea7209d5e7f8af4dfbde  gather_go_cluster/10-prompt.txt
      0ce4aa595c3eaf0ad3b3226a9928bc9534e2593ab1082e8db1fbfb323c209582  gather_go_registry/00-fixture.json
      6201f610bf496c64f84f910df9ef8e3a766b74b29d0aeed0a94db502ecbe8934  gather_go_registry/01-order.txt
      cc4115ae678b7b02bee1f18ee054462ea9d61462f8aa929d6fe77f5eb715d130  gather_go_registry/02-events.txt
      17ffd057f40091e7bf97aa65f61567eefb491a462c9894a909ef7540d94c5a5a  gather_go_registry/03-candidates.txt
      e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  gather_go_registry/04-nodes.txt
      e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  gather_go_registry/05-pvcs.txt
      760caac51cc68b2a56aea7c908eb63b0b2f1853920d00d81a9e78a09f70970c1  gather_go_registry/06-logs.txt
      dd3fc774ce3bb7abd0938aed62abe0a14363940a3e5e3d94f2ef5ed18da8c131  gather_go_registry/07-trail.txt
      221bc8acb55538ba1a655de31062753f04fb0c3d7a665c139e916c0aac46a2ba  gather_go_registry/08-bundle.txt
      747c808f00e5acc6247225cafa1f75bb8fbfa7d76db2ede15ab37485085a2b21  gather_go_registry/09-decide.txt
      43d50c0b60ccce1ebdcdd9ec3b48e3c37c41af40ea3126f60104afb8d7edfeca  gather_go_registry/10-prompt.txt

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

- **2026-10-05 — Spec 4b-3, `multi` rows and decoys.** No exam hash moved.
  `test.jsonl` is byte for byte the 4b-2 one. From this date `multi` shows
  only reads kubeagent's own gather makes, and the checker has no
  exemption for a hand-made read (the `origin_read_label` path is gone).
  Details are in the last entry of this section.
- **2026-10-04 — Spec 4b-2, the catalog gold.** Four hashes moved, old to
  new (details are in the last entry of this section):
  - `FROZEN_SLICE_SHA256`: `d7d609f9e63cb0d52c74a92f33242b8967dc46e4670924be0d15288d29ef941b`
    to `660f2b55fbc08426122381285d40a628f8a2a666f2756348086e71acf773f8b3`.
  - `EVAL_SET_SHA256`: `0a9b308a210157c3147cdc8c5b39471cbb50522f27bd792e39fded423f525a0d`
    to `94b384623a66bbee21520275c0282973ade7b089c3e8cdab94447398c218661e`.
  - `GRADED_VIEW_SHA256`: `b6335d8386c815c77c2bda8b0f3dd4310969f88680a1a9b2cb41d375a54c08a5`
    to `a1a3c8d4ebf62cec64bf2d0f98d2187592911725e90025269afeb8e97ade03e9`.
  - `OTHER_FAMILIES_SHA256` (`tests/test_generate.py`): `09de3501feceaab8ec014e7ccc5d187c3d88af50deef63dd030ef9cbaa87895a`
    to `745ac86ddcd0850427510bf7034c1bfe879dc4f739e4a275fe0a43de6bbc054a`.

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
    Closed 2026-10-04 by Spec 4b-2: its answer now names the cordoned node
    and the taints its own finding line prints.
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
    (2026-10-04, Spec 4b-1: closed. The count was 14. Spec 4b-1 counted
    again and found 20. A victim's gold now names a cause only when that
    cause's anchor is in the victim's own lines. If it is not, the gold is
    `none_of_these`. The pool check scores every family gold with the real
    grader and wants full marks on every row.)
  - `volume-mount-error`'s P1 decoy.
  - No node carries the `node.kubernetes.io/not-ready` taint.
  - A flagged `kube-system` workload outside the first 10 gets a system
    line in Go but not here.
    (2026-10-04, Spec 4b-1: closed. `render.cluster_health` is rebuilt on
    `health.assess`, the port that the cluster capture pins. The cluster
    fixture flags 13 workloads, 11 of them in `kube-system`, so 3
    `kube-system` workloads fall past the first 10. Their system lines
    print, and `tests/test_gather_byte_equal.py` holds the lines equal to
    Go's.)
  - A `not_read` object's fresh value is typed by hand and is not checked
    against Go.
  - The candidate-cap marker is no longer in the golden; only a unit test
    covers it.
    (2026-10-04, Spec 4b-1: closed. The cluster fixture has 12 down nodes
    against Go's cap of 8 candidates per workload, so the cap is in the new
    Go capture, `tests/fixtures/gather_go_cluster`. The byte test holds our
    bytes equal to it.)

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
    (2026-10-04, Spec 4b-1: the three arms are closed. The cluster and
    registry captures, from kubeagent v1.24.0, cover the candidate-cap line,
    the registry auth sentence and the no-pull-event sentence, and
    `tests/test_gather_byte_equal.py` checks each one byte for byte. The
    wording above was one arm short. A fourth arm, the shared-cause cap, has
    no capture. It moves to 4b-4.)
  - B6: a refused read's message is shorter than the API server's real
    text.
  - C9: the guard's text cleaning has no NFKC step, so a look-alike
    character (say, a full-width letter) can slip a copy past it.
  - D4: `multi`'s decoy list is keyed on each object's intent, not on
    what the prompt shows, so it can hold a decided workload's own gold.
    No grader reads it today. (2026-10-05, Spec 4b-3: done. Every `multi`
    decoy list is `gold.excluded_from(...)`, and
    `tests/test_multi_decoys.py` checks that no workload in any case lists
    its own gold. Widening the decoy gate to job 1 is left for 4b-4.)
  - A node's state at scan time: a cordon and a pressure condition.
    (2026-10-04, Spec 4b-1: closed. A node read now prints `unschedulable=`
    and every condition. The cluster lines carry a node's pressure,
    NotReady, cordon and lease state, in that order. Each story sets all of
    it, once per world.)
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
    (2026-10-04, Spec 4b-1: three arms closed, and a fourth found. See the
    longer B4 note above. The fourth arm, the shared-cause cap, moves to
    4b-4.)
  - B6: a refused read's message is shorter than the API server's real
    text.
  - D4: `multi`'s decoy list is keyed on each object's intent.
    (2026-10-05, Spec 4b-3: done. Every `multi` decoy list is
    `gold.excluded_from(...)`, and `tests/test_multi_decoys.py` checks that
    no workload in any case lists its own gold. Widening the decoy gate to
    job 1 is left for 4b-4.)
  - A node's state at scan time: a cordon and a pressure condition.
    (2026-10-04, Spec 4b-1: closed. See the note under the same item in the
    2026-09-26 entry.)

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

- **2026-10-04 — Spec 4b-1, the shared-origin rewrite.** All three hashes
  moved: `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and `GRADED_VIEW_SHA256`.
  The exam is still 249 rows and the frozen slice still 239. 229 exam rows,
  from the other families, are byte for byte the old ones
  (`OTHER_FAMILIES_SHA256` in `tests/test_generate.py`). The 20
  shared-origin exam rows are rebuilt: 10 `shared_origin_probe` and 10
  `shared_origin_decoy_probe`. Of those 20 rows, 20 user messages, 20 gold
  answers, 20 flagged lists and 20 metas moved. 0 system messages moved.

  Why. Until now this family showed the model text the generator made up:
  a candidate menu and an origin read typed by hand. Now each row runs
  kubeagent's own steps: the report order, the gather, the rules over
  every candidate, and the render. The design is in
  `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md`.
  One line each on what changed:
  - Real rows. There are 47 stories, each in two worlds, one broken and
    one healthy. 41 are trainable (35 plain, 6 ruled) and 6 are
    exam-only. 13 stories are gone: 12 whose only origin line was the
    hand-typed read (the spec's X stories), and `runtime-class-removed`,
    whose two worlds print the same lines. The trainable pool was 54 (48
    plain, 6 ruled).
  - The exemption is gone. The checker used to skip this family for some
    rules (`EXEMPT_CASES`, `EVIDENCE_RULES` and `PROPAGATION_TEXT_RULES`).
    All 50 rules now run on it, and the build's manifest shows 0
    violations.
  - The gold rules. A victim's gold names a cause only when the cause's
    anchor is in that victim's own lines. If it is not, the gold is
    `none_of_these`. The label is "shared" when the rules confirm one
    cause on 2 or more workloads, or when 2 or more victims in a broken
    world show link anchors in their own lines. Otherwise it is "none".
  - B7, the checker's rule for the cluster-health block, is rewritten. A
    node can have several lines, in the order pressure, NotReady, cordon,
    lease, and a candidate is needed only for the down lines. The
    checker's `_HEALTH_SYSTEM` pattern is fixed in the same change.

  The hashes, old → new:

  | Pin | Old | New |
  |---|---|---|
  | `FROZEN_SLICE_SHA256` | `f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a` | `d7d609f9e63cb0d52c74a92f33242b8967dc46e4670924be0d15288d29ef941b` |
  | `EVAL_SET_SHA256` | `a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2` | `0a9b308a210157c3147cdc8c5b39471cbb50522f27bd792e39fded423f525a0d` |
  | `GRADED_VIEW_SHA256` | `efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4` | `b6335d8386c815c77c2bda8b0f3dd4310969f88680a1a9b2cb41d375a54c08a5` |

  The bank, `out/dataset-1004`, built with the same command (`--seed 17
  --size 8000`), by sha256:
  - `test.jsonl`: `01e7732e09553c227b4c13458ee04fed3146b0dd28346319711553d6a6fd71d0`
  - `train.jsonl`: `30ac872a0f1a14025b71bbe8aaf7e36812e6216afe3686056d56a553b73e2a64`
  - `val.jsonl`: `fd94f367e1f7f1f52607e23e405357c993427424e6e281123de766c5d2087643`

  Rows: train 6,457 → 6,439, val 721 → 739, test 249 → 249. The bank holds
  1,200 `shared_origin` and 1,200 `shared_origin_decoy` rows, which is 1,200
  pairs. Every train and val row outside the family is byte for byte the
  same as in `out/dataset-0929`. `out/dataset-0929` and `out/dataset-0928`
  stay on disk. The prompt-stability test now reads
  `out/dataset-1004/test.jsonl`.

  What moved on the 20 exam rows:
  - Their `meta` drops `distractor_cause`, `expected_confidence`,
    `wrong_summary_phrase` and adds no key. The exam carries
    `expected_cause` on 209 rows (was 209) and `expected_confidence` on 209
    rows (was 219).
  - Labels, was none 15, shared 5; now none 13, shared 7.
  - Origins: unchanged. The 20 rows come from the same six stories,
    `coredns-down`, `networkpolicy-deny-all`, `node-disk-pressure`,
    `node-not-ready`, `registry-unreachable` and
    `storage-provisioner-down`.
  - The oracle's job counts, with the gold reply as the model's reply (every
    one is full marks): job 1 120 → 102 workloads, job 2 177 → 197
    workloads, job 3 40 rows (none 35, separate 0, shared 5) → 40 rows (none
    33, separate 0, shared 7). The 20 family rows hold 12 of the job-1
    workloads (was 30) and 38 of the job-2 workloads (was 18).
  - No bar moved: 0.9, 0.7 and 0.9.
  - The evidence-overlap pins moved: `shared_origin_probe` 3 → 19 of 40,
    and `shared_origin_decoy_probe` 2 → 13 of 30. The real gather prints
    the same line shapes in both worlds, and training rows print them too.

  The mix, counted on the new `train.jsonl`. These are the numbers the
  mix tests passed with:
  - Pairs per story: 20 to 39. The bar is at least 12.
  - `none_of_these` in broken rows: 533 of 2,931 = 18.2%. In healthy rows:
    677 of 2,710 = 25.0%. The gap is 6.8 points. The bar is within 10.
  - `none_of_these` in all train answers: 1,461 of 11,192 = 13.1%. The bar
    is at most 30%. In `out/dataset-0929` it was 251 of 10,991 = 2.3%.
  - Label cue: 20 plain stories end mostly "shared" and 14 end mostly "none"
    (1 tied). The bar is at least 5 each.
  - Three-verdict: 532 of 1,080 healthy rows = 49.3% carry 3 or more
    verdicts. The bar is at least 40 of every 100.

  Five older items close in place, each with a dated note and the old
  text kept: the victims whose gold names a node their lines never show,
  the `kube-system` line past the first 10 workloads, the candidate-cap
  marker, B4, and a node's state at scan time. B4's wording is corrected:
  it has a fourth arm.

  The capture is recorded under "Capture record (v1.24.0, cluster and
  registry capture)" above. In the new bank, 0 family rows show the registry
  no-pull sentence and 28 show the registry auth sentence. The capture
  proves the bytes of both.

  The model card: limits 1 to 5 and 7 to 9 have a dated note with the new
  numbers, limit 6 is rewritten, and limit 15 is new. The two 0920 sections
  say they scored the exam's shared-origin rows as they were before
  2026-10-04. 0920 has not been run on the new exam.

  Left for 4b-2, 4b-3 and 4b-4:
  - 4b-2: gold that says more than its prompt, in the other families. The
    gold rule above, applied to them.
  - 4b-3: `multi` rows and decoys. Done 2026-10-05, see the 2026-10-05
    entry below.
    - the container-name clash, 96 of 738 `multi` rows: closed, no change.
      kubeagent's gather does the same
      (`internal/investigate/gather.go:146`). See §6 of
      `docs/superpowers/specs/2026-10-05-multi-decoys-design.md`;
    - `multi`'s `healthy_origin` and its `origin_read_label` path: removed;
    - D4: done.
    Still open for 4b-4: the guard for 4+-letter kit keys, widening the
    decoy gate to job 1, and the sum half of IS-22. That half fails on
    4b-1 stories, exam rows included, so it waits for the exam rebuild.
    (2026-10-05: 4b-4 took only the grader items. The rest moved to the
    exam rebuild. See the "2026-10-05 — Spec 4b-4" entry below.)
  - 4b-4: grader leftovers.
    - model-card limits 13 and 14;
    - hyphen and underscore folding in the cleaning step;
    - the weak pairs: 21 on the 2026-09-29 exam, 9 on this one;
    - image-pull-secret-expired graded as unverified;
    - B6;
    - the G2 registry skip;
    - must-not words for this family;
    - node-disk-pressure's ContainerStartError keys ("containerd",
      "task") name no origin; re-key it to ("space", "containerd") with the
      exam rebuild;
    - B4's fourth arm, the shared-cause cap;
    - tighter checker checks that real output does not need: service-line
      wording and sort order, the network-policy gate, a message-only
      NotReady line over 120 runes, lease ages from 0s to 39s, an extra
      system line at 10 rows, and ANS-2 counting ruled-out lines.

  The order after 4b-1: 4b-2, 4b-3 and 4b-4, then the exam rebuild and
  re-pin, then 0920 live, then the one retrain (about 32 hours on the
  training host), then the untuned baseline.

- **2026-10-04 (Spec 4b-2) — the catalog gold.** The four hashes above
  moved. The prompts did not: 0 rows in any split differ from
  `out/dataset-1004` in the system or user message. Only the gold answers
  (cause, reason, confidence, keys) moved. The exam is still 249 rows.

  The rule. A catalog entry's answer is now a kit: an anchor, a cause,
  keys, a reason and a confidence.
  - An undecided workload names its entry's cause only when its own lines
    hold the kit's anchor. Its own lines are all its lines, minus any line
    that names a ruled-out or refuted cause.
  - If the anchor is not there, the gold is `none_of_these`, confidence
    low, no keys, and the reason is "<none phrase>; none of its own lines
    says why."
  - The rule runs wherever an entry's own cause is written: `own_cause`,
    `wrong_attribution`, `misattribution_probe`, `empty_candidates`,
    `multi_misattribution_probe` and `multi`.

  The gate fires on 4 rows in the 8,000-row pool. All 4 are coredns `multi`
  rows whose read budget ran out before the log read. 1 of the 4 lands in
  train, 0 in val and 0 on the exam. So it fires on 1 train row and on 0
  exam rows. It is there so a later case or budget change cannot quietly
  bring overclaiming back.

  Confidence. Rules-decided rows are now high. The probe-failure and
  restart-loop named rows go to high. `networkpolicy-deny-all` stays
  medium. Counted against `out/dataset-1004`, medium to high:
  - rules-decided verdicts: 441 in train, 60 in val, 15 on the exam. They
    sit in 416, 58 and 15 rows, because one row can hold more than one;
  - named verdicts: 258 in train, 34 in val, 12 on the exam. Here each row
    holds one, so these are also 258, 34 and 12 rows.

  The 8 changed causes (the new text is in the kit in
  `src/kubeagent_verdict/dataset/entries_*.py`):
  - `node-cordon-diskfull`: "one node is unschedulable (cordoned) and the
    others have taints the pod does not tolerate". It no longer claims
    disk pressure.
  - `networkpolicy-deny-all`: "a default-deny network policy blocks the
    probe's traffic to the pod".
  - `init-config-error`: "a Secret the init container references does not
    exist".
  - `init-imagepullbackoff`: "the init container's image cannot be pulled,
    and the kubelet keeps backing off".
  - `init-oomkilled`: "the init container is killed at its memory limit".
  - `restart-loop`: "the container panics (a code bug) and keeps
    restarting".
  - `volume-attach-error`: "the volume is still attached to another node".
  - `volume-mount-error`: "the pod's volume times out while mounting on its
    node".

  The 7 changed recommendations. Each now names no object the workload's
  own lines do not print: `node-cordon-diskfull`, `init-imagepullbackoff`,
  `init-oomkilled`, `restart-loop`, `volume-mount-error`,
  `worker-containerd-stop` and `pvc-unbound-unschedulable`. The other 13
  stay.

  What moved, counted against `out/dataset-1004` (train / val / exam):
  - Cause changed: 1,158 / 92 / 52 verdicts. Counted as rows: 1,118 /
    89 / 47 rows.
  - Reason changed: 2,766 / 298 / 151 verdicts. Counted as rows: 2,531 /
    271 / 131 rows.
  - Moved to `none_of_these`: 1 / 0 / 0 rows.
  - Unshown facts, counted as verdicts (cause and reason both checked,
    shared-origin rows left out): train 714 of 5,300 named verdicts before,
    0 of 5,299 after; exam 32 of 241 before, 0 of 241 after. Counted as
    rows, reason only: 553 / 52 / 26 rows before and 0 / 0 / 0 after.
  - `none_of_these` share of all verdicts: train 1,462 of 11,192 = 13.06%
    (the ceiling is 30%), val 140 of 1,293 = 10.83%, exam 22 of 299 =
    7.36%.
  - The checker: 0 violations of every kind in the manifest.
  - Weak pairs: 9 to 3. The key count stays 34. The 3 left are two for the
    default-deny network policy key. The golds it clashes with are the
    liveness and readiness victim golds of the shared default-deny story,
    not the catalog `probe-failure` entry. The third is one for
    "deadline", "exceeded" against the containerd gold.
    `node-cordon-diskfull`'s key is now "unschedulable", "taint".
  - Exam job counts, before and after: job 1 102 workloads, job 2 197
    workloads. They are the same.
  - The init-keys hedge bot: its map now follows the new keys. Its job-2
    rate stays 0.9391 on 197 workloads.

  The build folder is `out/dataset-1004-4b2`: train 6,439, val 739, test
  249 rows. It is not `out/dataset-1004` because that folder holds the 4b-1
  build, and the 4b-1 numbers above were counted on it. Keeping both lets
  the before and after counts be re-run. The prompt-stability test now
  reads `out/dataset-1004-4b2/test.jsonl`.

### 2026-10-05 — Spec 4b-3: multi rows and decoys

No exam hash moved. `test.jsonl` is byte for byte the one in
`out/dataset-1004-4b2`, so `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and
`GRADED_VIEW_SHA256` stay as they were. The design is in
`docs/superpowers/specs/2026-10-05-multi-decoys-design.md`.

The build folder is `out/dataset-1005` (`--seed 17 --size 8000`): train
6,439, val 739, test 249 rows. The exam has no `multi` rows, which is why
it did not move.

What changed in `multi`:
- No healthy-origin read. `multi` shows only reads kubeagent's gather
  makes. The checker has no exemption for a hand-made read.
- A decoy list is `gold.excluded_from(...)`: the causes the prompt rules
  out, never a workload's own gold.
- The summary says "separate reasons" only when the rows show it, and it
  names every workload.
- A scheduler node count agrees with the cluster header. The node-cordon
  answer sentence had a hard-coded node count too ("2 had taints"). It is
  now `{other_nodes}`, so a rebuilt `multi` row's answer agrees with its
  prompt.

What moved, against `out/dataset-1004-4b2` (train / val / exam):
- `multi` prompts: 315 / 40 / 0 rows moved, 355 in all.
- `multi` answers: 279 / 27 / 0 rows moved, 306 in all. 200 / 18 / 0 rows
  moved in both. So 218 rows moved in both.
- 652 train and 86 val `multi` rows in all (738). Rows that are not
  `multi`: 0 prompts moved in any split.
- 77 shared-origin rows from 4b-1 (66 train, 11 val, 0 exam) have an answer
  that moved. They are the rows with 4 or more workloads. The summary now
  names every workload, where it used to name only some.

Measured, before and after:
- Node count mismatches (a scheduler line whose node count differs from the
  header): 172 `multi` rows before (159 train, 13 val), 0 after.
- Own-gold decoys (D4): 0 after, over 11,192 train, 1,293 val and 299 exam
  workloads checked. The counts show the 0 is not an empty pass.
- `none_of_these` verdicts in `multi` rows: train 1 of 1,924 before, 2 of
  1,924 after. Val 0 of 246 both times. That is 2 of 2,170 train and val
  verdicts, far under the 30% ceiling.
- `multi` row labels: train 639 `none`, 13 `separate`, the same before and
  after. Val 86 `none`, the same.
- The checker has 51 rules and 0 violations of every kind (16 case keys).
  The new one is IS-22 (a scheduler node count matches the header). It
  inspected 2,266 counts: 2,026 train, 160 val, 80 exam. Only its first
  half is built. Its sum half fails on 4b-1 stories, so it waits for the
  exam rebuild.

No re-pin was needed for the final build. Removing the healthy-origin read
moved these pins. Each is a hand re-pin, dated 2026-10-05 (Spec 4b-3) in a
comment. The guarded rates stayed 1.0 and no exam pin moved.
- `GATED_POOL` in `test_catalog_gold`: 4 rows to 6. It added (2488,
  payments/gateway) and (2851, payments/ingest). Why: the old healthy read
  used up a budget slot, so a stale "unverified" node answer survived. Now
  the 8th read refutes the node and the row gates to `none_of_these`.
- `test_oracle`: job 1 n 3151 to 3145; job 2 gate n 8041 to 8047;
  keyword-only n 6579 to 6584; multi job 1 (1207, 1207) to (1201, 1201).
- `test_answer_keys`: (13946, 1084) to (13946, 1085); checked 7972 to 7979.
- `test_score`: checked 9618 to 9627.

Test changes:
- The two share tests in `test_shared_origin_training` now assert `== 0.5`.
- `test_catalog_gold`'s dataset-1004 byte test skips `multi` rows.
- `tests/test_multi_collision.py` is deleted, with the healthy-origin read.
- `test_shared_origin_pool`'s `INSPECTS` list gained TXT-IS22.
- New: `tests/test_multi_decoys.py`.

Container-name clash: closed, no change. 96 of 738 `multi` rows have it,
and kubeagent does the same (`internal/investigate/gather.go:146`). See §6
of the spec.

Full suite: 1,940 passed. Ruff: clean.

### 2026-10-05 — Spec 4b-4: grader leftovers

No pin moved. No exam, train or val byte changed. `FROZEN_SLICE_SHA256`,
`EVAL_SET_SHA256` and `GRADED_VIEW_SHA256` stay as they were. Only the
grader changed: `src/kubeagent_verdict/evals/score.py`, and the cleaning
twin in `src/kubeagent_verdict/dataset/gold.py`. The design is in
`docs/superpowers/specs/2026-10-05-grader-leftovers-design.md`.

The six changes, with what each one moves on the exam (249 rows, 197
job-2 workloads). A "probe" is the gold reply with one change.
1. The decoy gate tests job 1. `decoy_rate` counts 174 rows, was 121.
   The gold reply names a decoy on 0 of 174.
2. The decoy compare cleans both sides with `_norm_cause`. A probe that
   names each first decoy in capitals plus a period: `decoy_rate`
   {0.0, 121} before, {1.0, 174} after.
3. G3b never cuts past a word that ends in `:` (model-card limit 13). A
   probe that adds a `log cause:` label's words to 50 right answers: job 2
   167 of 197 before, 197 of 197 after.
4. A must-not word with a negator in the 24 characters before it does not
   count (model-card limit 14). A probe that rules out the must-not word
   in 51 right answers: job 2 146 of 197 before, 197 of 197 after.
5. The cleaning step folds U+2010 to U+2015 to `-` and `_` to a space,
   after NFKC, in both twins. A new test keeps the twins equal.
6. A key or must-not word of 3 letters or fewer must start a word
   (`SHORT_WORD_MAX = 3`). This is the grader's answer to the 4+-letter
   kit-key guard. A probe that writes "stage" for `tag` on 6 workloads:
   job 2 197 of 197 before (6 wrong answers passed), 191 of 197 after.

What did not move: the gold reply scores 1.0 on job 1 (102), job 2 (197)
and job 3 (40). The hedge bot scores job 2 0.4162 of 197. The three
cut-paste bots score job 2 0.0 of 197. The bars did not move.

Still open in the grader: a negator more than 24 characters back, as in
"no node is cordoned or under memory pressure", still scores 0. And the
negation check does not see a curly apostrophe: "isn’t" (U+2019) is not
read as "n't", so a must-not word right after it still counts. Both are
written down in model-card limit 14. No code changed for them.

Hand re-pins, each dated 2026-10-05 (Spec 4b-4) in a comment:
- `test_the_gold_reply_names_no_decoy_on_any_exam_row`: `decoy_rate` n
  121 to 174.
- `test_job2_guards_a_none_of_these_workload_too`: the made-up own line
  is the cleaned `none of these` now. The made-up decoy `none_of_these`
  cleans to 3 words, so G2 tests it: 1.0 to 0.0. No exam decoy has a `_`.

Test changes:
- `test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload`
  is now `test_decoy_gate_tests_a_job1_workload_too`.
- `test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut`
  uses a candidate line now. Its old line starts with the label `issue:`.
- New in `tests/test_score.py`: the fold test (both twins), the twin
  test, the G3b label test, the negator test, the short-word test, the
  cleaned-compare test, and four exam probes.

Left for the exam rebuild. These were on 4b-4's list, but each changes
exam rows, so they move with the rebuild and its one re-pin:
- IS-22's sum half: the reasons in "0/N nodes are available: ..." add up
  to N. It fails on 4b-1 stories, exam rows included.
- node-disk-pressure's ContainerStartError keys: ("containerd", "task")
  to ("space", "containerd").
- The weak pairs: 3 left (see the 4b-2 entry).
- The G2 registry skip: the bad-image-tag key has no must-not word for a
  registry fault.
- Must-not words for the shared-origin family.
- B6: a refused read's short "is forbidden" text.
- The tighter checker checks: service-line wording and sort order, the
  network-policy gate, a message-only NotReady line over 120 runes, lease
  ages 0s to 39s, an extra system line at 10 rows, and ANS-2 counting
  ruled-out lines. They move no row, but they belong with the build.
- B4's fourth arm, the shared-cause cap. It needs a new Go capture.
- image-pull-secret-expired graded as unverified.

Full suite: 1,951 passed. Ruff: clean.
