# Runbook: cutting a release

Releases are GitHub Releases carrying the GGUF, Modelfile, SHA256SUMS,
LICENSE, and the model card. Model weights never enter git history —
`*.gguf` is gitignored.

1. Preconditions: clean tree on `main`, `pytest -q` green, `ruff check .`
   clean, and a completed train.md run with both scoreboards recorded in
   `docs/model-card.md`'s `## Scoreboard` (the README carries a headline
   summary of the same run and must not disagree with it).
   train.md step 2 has you `mv dist/ dist-v<N>-superseded/`; that
   directory is gitignored, so it satisfies "clean tree" rather than
   violating it, and the several hundred megabytes it holds cannot be staged
   by accident. Confirm the same way you confirm everything else here — read
   `git status --short`, do not assume.
2. Bump `__version__` in `src/kubeagent_verdict/__init__.py` and the
   `version` in `pyproject.toml` (they must match). Commit with `-s`.
3. Read `docs/model-card.md` against the just-completed run: the "Known
   limitations" and "How to read the scoreboard" sections must still hold
   for this model, not just the one they were written against, and its
   `## Scoreboard` tables must be this run's, pasted in with the run
   directory they came from named beside them. The release notes are the
   model card and nothing else — do **not** `cat` a scoreboard file onto
   the end of them. An earlier version of this runbook did, and the two
   sources drifted the moment a run was re-scored: the card carried the
   corrected numbers while `out/eval/scoreboard.md` still held the
   pre-correction ones. One source, checked by eye against the run
   directory, or the release ships two answers.

   Tag and publish (the push and the release are outward-facing — the
   operator confirms first):

       git tag v<X.Y.Z>
       git push origin main v<X.Y.Z>
       gh release create v<X.Y.Z> dist/kubeagent-verdict-0.6b-q8_0.gguf \
           dist/Modelfile dist/SHA256SUMS LICENSE docs/model-card.md \
           --title "kubeagent-verdict v<X.Y.Z>" \
           --notes-file docs/model-card.md

4. Verify: `gh release view v<X.Y.Z>` shows all five assets, and
   `sha256sum -c SHA256SUMS` passes on a fresh download.
