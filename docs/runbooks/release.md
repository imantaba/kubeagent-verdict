# Runbook: cutting a release

Releases are GitHub Releases carrying the GGUF, Modelfile, and SHA256SUMS.
Model weights never enter git history — `*.gguf` is gitignored.

1. Preconditions: clean tree on `main`, `pytest -q` green, `ruff check .`
   clean, and a completed train.md run with both scoreboards recorded in
   the README.
2. Bump `__version__` in `src/kubeagent_verdict/__init__.py` and the
   `version` in `pyproject.toml` (they must match). Commit with `-s`.
3. Tag and publish (the push and the release are outward-facing — the
   operator confirms first):

       git tag v<X.Y.Z>
       git push origin main v<X.Y.Z>
       gh release create v<X.Y.Z> dist/kubeagent-verdict-0.6b-q8_0.gguf \
           dist/Modelfile dist/SHA256SUMS \
           --title "kubeagent-verdict v<X.Y.Z>" \
           --notes "$(cat out/eval/scoreboard.md)"

4. Verify: `gh release view v<X.Y.Z>` shows all three assets, and
   `sha256sum -c SHA256SUMS` passes on a fresh download.
