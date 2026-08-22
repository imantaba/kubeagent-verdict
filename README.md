# kubeagent-verdict

Training pipeline for the local verdict model consumed by
[kubeagent](https://github.com/imantaba/kubeagent) `scan --investigate`
(local verdict mode, kubeagent ≥ v1.23.0).

Pipeline: `kv-dataset` → `kv-train` → `kv-export` → `kv-eval`. CPU-only:
no GPU is needed to train, export, or evaluate.

## Data provenance (hard rule)

Training data derives from exactly two sources, both vendored under `data/`:

1. `data/corpus/` — the chaos correctness corpus, downloaded **only** from
   kubeagent's nightly `chaos-matrix` CI artifacts (redacted at the seam and
   credential-scanned before upload). Never from a local working copy.
2. `data/knownissues/` — a snapshot of kubeagent's curated 16-kind
   known-issues reference.

Everything else in a training example is synthetic, drawn from the allowlist
in `src/kubeagent_verdict/dataset/names.py`. No live cluster identifier may
appear in any tracked file.

## Contract

The prompt format and verdict contract v1 are kubeagent's, pinned
byte-for-byte under `contract/`. See `contract/PIN.md`.

## Developer certificate of origin

Commits are signed off (`git commit -s`).
