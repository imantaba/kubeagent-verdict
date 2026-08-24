# Chaos correctness corpus snapshots

Source: kubeagent's nightly `chaos-matrix` workflow artifacts, downloaded
with `gh run download` — run id `32548862821`, dated `2026-08-22`, artifacts
`chaos-report-kind-v1.32`, `chaos-report-kind-v1.33`,
`chaos-report-kind-v1.34`, `chaos-report-k3s-v1.34`.

Rows were redacted at the harness seam (`redact_nodes` runs BEFORE JSON
encoding) and the workflow credential-scans the corpus before uploading it.
`redact_nodes` did not catch every string, though, and it missed one in
**all four** tracked files. The three kind files
(`chaos-corpus-v1.32-kind.jsonl`, `-v1.33-kind.jsonl`, `-v1.34-kind.jsonl`)
each carry two unredacted occurrences of
`kubeagent-chaos-v1-<minor>-worker`. The k3s file
(`chaos-corpus-v1.34-k3s.jsonl`, the `3. diskfull` row) carries one
occurrence of `k3d-kubeagent-chaos-k3s-v1-34-agent-0` — k3d's own name for
the agent node of that same disposable cluster, a different spelling for
the same kind of thing. Both are the chaos harness's deterministic name for
a node it creates and tears down inside one CI run; neither identifies
anything reachable or any real cluster, so the rows were left
byte-identical to what the harness emitted rather than hand-edited
afterward — rewriting them would break their provenance against the CI run
named above.

An earlier version of this paragraph said the miss was confined to three
files and named the k3s file as the clean one. That was wrong, and wrong in
the reassuring direction: anyone auditing this corpus by grepping for the
documented `-worker` pattern would have found the k3s file clean and
concluded redaction had held there. It had not. The accurate statement is
that **no** tracked corpus file is free of a harness-owned node name.

These snapshots are the ONLY corpus source for this repository: they are
never copied from a kubeagent working tree, whose `docs/testing/` holds
live-cluster output.

One JSON object per line: `scenario`, `fault` (a slug from the closed
17-entry vocabulary in `src/kubeagent_verdict/vocab.py`), `k8s`, `distro`,
`rc` (the scenario's machine verdict, 0 = no assertion failed), `assertions`
(verbatim assertion lines), `skipped`, `skip_reason`.
