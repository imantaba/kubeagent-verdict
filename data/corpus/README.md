# Chaos correctness corpus snapshots

Source: kubeagent's nightly `chaos-matrix` workflow artifacts, downloaded
with `gh run download` — run id `32548862821`, dated `2026-08-22`, artifacts
`chaos-report-kind-v1.32`, `chaos-report-kind-v1.33`,
`chaos-report-kind-v1.34`, `chaos-report-k3s-v1.34`.

Rows were redacted at the harness seam (`redact_nodes` runs BEFORE JSON
encoding) and the workflow credential-scans the corpus before uploading it.
These snapshots are the ONLY corpus source for this repository: they are
never copied from a kubeagent working tree, whose `docs/testing/` holds
live-cluster output.

One JSON object per line: `scenario`, `fault` (a slug from the closed
17-entry vocabulary in `src/kubeagent_verdict/vocab.py`), `k8s`, `distro`,
`rc` (the scenario's machine verdict, 0 = no assertion failed), `assertions`
(verbatim assertion lines), `skipped`, `skip_reason`.
