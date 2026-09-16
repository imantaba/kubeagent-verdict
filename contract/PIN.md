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
