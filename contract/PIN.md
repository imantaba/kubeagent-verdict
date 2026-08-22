# Contract pin

This directory pins the interface kubeagent-verdict trains against.

- **Pinned against:** kubeagent **v1.23.0** — `scan --investigate` local
  verdict mode, verdict contract **v1** (prose-versioned in kubeagent's
  `website/docs/features/diagnostics.md`).
- `system_prompt.txt` — the byte-exact `verdictSystemPrompt` constant from
  `internal/investigate/local.go`.
- `golden/user_message.txt` — the byte-exact output of kubeagent's
  `buildVerdictPrompt` for the inputs in `golden/input.json`, captured by a
  temporary build-tagged Go test run inside a kubeagent checkout (the test
  is not kept anywhere; the capture procedure is in the implementation plan,
  `docs/superpowers/plans/2026-08-22-kubeagent-verdict.md` in the kubeagent
  repo).
- `golden/input.json` — the structured mirror of that capture's inputs; the
  `next_step`/`command` strings are transcribed from the capture because
  they are kubeagent's deterministic suggestion output.
- `golden/answer.json` — a contract-valid answer for the fixture, used as a
  shape reference by tests.

## Re-pin procedure (when kubeagent changes the contract)

kubeagent's diagnostics.md prose contract is the tripwire: a new contract
version there means re-pinning here. Re-run the capture procedure against
the new kubeagent tag, re-extract `system_prompt.txt`, update
`contract.py`'s renderers until the golden test passes again, bump the
version named in this file, and retrain.
