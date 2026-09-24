# Contract pin

This directory pins the interface kubeagent-verdict trains against.

- **Pinned against:** kubeagent **v1.24.0** — `scan --investigate` local
  verdict mode, verdict contract **v1** (prose-versioned in kubeagent's
  `website/docs/features/diagnostics.md`), tag `v1.24.0`, commit
  `15ec5649bbd2d07558eae945b71430afc8f231fd`.
- `system_prompt.txt` — the byte-exact `verdictSystemPrompt` constant from
  `internal/investigate/local.go`.
- `golden/user_message.txt` — the byte-exact output of kubeagent's
  `buildVerdictPrompt` for the inputs in `golden/input.json`, captured by a
  temporary build-tagged Go test run inside a kubeagent checkout. The
  capture procedure is `contract/capture/kv_capture_test.go.txt` in this
  repository — copy it into a kubeagent checkout as
  `internal/investigate/local_capture_test.go`, run it there, and copy the
  files it writes back.
- `golden/input.json` — the structured mirror of that capture's inputs; the
  `next_step`/`command` strings are transcribed from the capture because
  they are kubeagent's deterministic suggestion output.
- `golden/answer.json` — a contract-valid answer for the fixture, used as a
  shape reference by tests.
- `tests/fixtures/rules_golden.json` — the fixture `hypothesis.Decide` and
  `hypothesis.Shared` ran against during capture: twelve workloads' rule
  candidates and decisions, plus the shared-cause lines and the eight
  bounded reads. `dataset/rules.py`'s tests replay it and must match the
  captured decisions field for field.

## Re-pin procedure (when kubeagent changes the contract)

kubeagent's diagnostics.md prose contract is the tripwire: a new contract
version there means re-pinning here. Copy
`contract/capture/kv_capture_test.go.txt` into a kubeagent checkout as
`internal/investigate/local_capture_test.go`, run it against the new
kubeagent tag, re-extract `system_prompt.txt`, update `contract.py`'s
renderers until the golden test passes again, bump the version named in
this file, and retrain.

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

## Capture record (v1.24.0 re-scope)

- Captured from kubeagent tag `v1.24.0`, commit `15ec5649bbd2d07558eae945b71430afc8f231fd`.
- Test: `contract/capture/kv_capture_test.go.txt`. The five steps are in its header.
- Files: `tests/fixtures/rules_golden.json` (the rules pin). The prompt golden and the system prompt land in `contract/golden/` and `contract/system_prompt.txt` as the code that renders them lands.
- The worktree was removed after the capture. kubeagent was not changed.

## Dataset pin moves

The exam's two hashes live in `tests/test_shared_origin_training.py`:
`FROZEN_SLICE_SHA256` over every row before the ten
`shared_origin_decoy_probe` rows (242 rows) and `EVAL_SET_SHA256` over all
252. Until 2026-09-24 the first was `FROZEN_253_SHA256`, over 253 rows of
263. They are pinned so a change to the generators cannot move the exam
without someone saying why. This is where the why is recorded.

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
  undecided row, and the reads decide the answer. `FROZEN_253_SHA256` is
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
