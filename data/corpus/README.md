# Chaos correctness corpus snapshots

Source: kubeagent's nightly `chaos-matrix` workflow artifacts, downloaded
with `gh run download` — run id `32548862821`, dated `2026-08-22`, artifacts
`chaos-report-kind-v1.32`, `chaos-report-kind-v1.33`,
`chaos-report-kind-v1.34`, `chaos-report-k3s-v1.34`.

Rows were redacted at the harness seam (`redact_nodes` runs BEFORE JSON
encoding) and the workflow credential-scans the corpus before uploading it.
`redact_nodes` did not catch every string, though: three of the four
tracked files (`chaos-corpus-v1.32-kind.jsonl`, `-v1.33-kind.jsonl`,
`-v1.34-kind.jsonl` — not the k3s file) each carry two unredacted
occurrences of `kubeagent-chaos-v1-<minor>-worker`, the chaos harness's own
deterministic name for the disposable kind node it creates and tears down
for that CI run. That name identifies nothing reachable and no real
cluster, so the rows were left byte-identical to what the harness emitted
rather than hand-edited afterward — rewriting them would break their
provenance against the CI run named above.
These snapshots are the ONLY corpus source for this repository: they are
never copied from a kubeagent working tree, whose `docs/testing/` holds
live-cluster output.

One JSON object per line: `scenario`, `fault` (a slug from the closed
17-entry vocabulary in `src/kubeagent_verdict/vocab.py`), `k8s`, `distro`,
`rc` (the scenario's machine verdict, 0 = no assertion failed), `assertions`
(verbatim assertion lines), `skipped`, `skip_reason`.
