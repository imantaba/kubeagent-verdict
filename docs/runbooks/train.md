# Runbook: training a release candidate

All commands run from the repo root, inside a venv installed from the
pinned lock file:

    pip install -r requirements.lock -e .

That buys the exact dependency versions the release was built and
evaluated against, not whatever `pyproject.toml`'s loose lower bounds
resolve to today. The full pipeline is CPU-only and takes several hours
on a workstation — run the training step under `nohup` and watch
`train_log.json`.

1. **Dataset** (seconds):

       kv-dataset --seed 17 --size 5500 --out out/dataset

   Check `out/dataset/manifest.json`: train+val ≤ 5500 (the shortfall is
   examples dropped for colliding with a corpus-test fixture's group),
   test > 0, every case present in `case_counts`.

2. **Negative control** — only when the dataset or the eval changed, and
   then it is not optional. An eval change that could not fail the model it
   replaced is not a fix. Serve the *previous* model, still on disk, and run
   the *corrected* eval against it:

       out/export/llama.cpp/build/bin/llama-server \
           -m dist/kubeagent-verdict-0.6b-q8_0.gguf --port 8080 -t 4 -c 4096 -n 2048 &
       kv-eval --test out/dataset/test.jsonl --endpoint http://127.0.0.1:8080/v1 \
               --model dist/kubeagent-verdict-0.6b-q8_0.gguf \
               --out out/eval-negative-control

   It must **fail** that model on the adversarial slices. If it passes, the
   eval did not close the hole and there is nothing to retrain for yet.
   Budget **~2¼ hours** for the current 243 rows at this size. That is
   measured, not estimated: a `llama-server -t 4` run on a workstation CPU
   completed 149 rows in 81.4 minutes, or ~1.8 rows/minute, so 243 rows take
   roughly 133 minutes. An earlier version of this line said "~30 minutes for
   224 rows" and was wrong on both counts — badly enough to make a healthy
   run look hung, which matters because `kv-eval` prints nothing to stdout
   until it finishes. To watch progress, count `launch_slot_` lines in the
   llama-server log; do **not** count `print_timing` lines, which are
   incremental snapshots emitted several times within a single generation.
   Note the endpoint: `kv-eval`
   defaults to Ollama's `http://localhost:11434/v1`, so a llama-server run
   without `--endpoint` silently scores whatever Ollama is serving.

   Then move the old model aside so nothing downstream picks it up:
   `mv dist/ dist-v<N>-superseded/`.

3. **Train** (hours, CPU):

       nohup kv-train --dataset out/dataset --out out/adapter > out/train.out 2>&1 &

   Progress: `python -c "import json; print(len(json.load(open('out/adapter/train_log.json'))['losses']))"`
   once it exists; before that, `tail out/train.out`. A smoke run first is
   cheap and catches config errors: `kv-train --dataset out/dataset --out out/smoke-adapter --limit 32 --epochs 1`.

4. **Export** (~30 min: clone, convert, cmake build, quantize):

       kv-export --adapter out/adapter --workdir out/export --out dist/

   Produces `dist/kubeagent-verdict-0.6b-q8_0.gguf`, `dist/Modelfile`,
   `dist/SHA256SUMS`. The chain ends with a llama-cli load-verify; if that
   fails, nothing in `dist/` is trustworthy.

   This is the one step where the venv must be **activated**, not merely
   used. `kv-export` shells out to `git` and `cmake` by bare name, and
   `cmake` is pip-provided — it exists at `.venv/bin/cmake` and nowhere
   else on a machine that never installed the system package. Running
   `.venv/bin/kv-export` by absolute path, which is enough for every other
   entry point here, leaves `.venv/bin` off `PATH` and the export dies on
   `FileNotFoundError: 'cmake'`. It dies *late*: the merge and the f16
   conversion both succeed first, so several minutes and a 1.2 GB
   intermediate are spent before the failure appears. `source
   .venv/bin/activate`, or prepend `.venv/bin` to `PATH`.

5. **Serve and eval**:

       out/export/llama.cpp/build/bin/llama-server \
           -m dist/kubeagent-verdict-0.6b-q8_0.gguf --port 8080 -t 4 -c 4096 -n 2048 &
       kv-eval --test out/dataset/test.jsonl --endpoint http://127.0.0.1:8080/v1 \
               --model dist/kubeagent-verdict-0.6b-q8_0.gguf --out out/eval

   Baseline for comparison: convert the untuned base with the same chain
   (`convert_hf_to_gguf.py` on the raw `Qwen/Qwen3-0.6B` download, then
   `llama-quantize ... Q8_0`), serve it the same way, and run kv-eval into
   `out/eval-baseline`. The scoreboard delta is the release evidence.

   `--limit` exists for a smoke read, not for a release. It reports which
   cases it dropped entirely; a scoreboard covering three of ten cases looks
   exactly like one covering all ten, so never bank a limited run.

   **Read `scoreboard.json`'s `run` block before you read any number in it.**
   It names the model basename, the endpoint, the test file and
   `rows_scored`/`rows_available`, with `limited: true` when those differ.
   Two scoreboards are otherwise distinguishable only by directory name,
   which is exactly the wrong thing to trust when the failure mode is
   forgetting `--endpoint` and scoring Ollama instead. The model is reduced
   to its basename and the endpoint drops any userinfo, so neither field can
   carry a home directory or a credential into a file you might paste.

   Its `dataset` sub-block says **which** test set those rows came from:
   `seed`, `size`, `test_rows`, and a SHA-256 over `out/dataset/manifest.json`.
   Every other field of `run` is a property of the serving side, and
   `test_file` is a basename — so before this block a retrain that overwrote
   `out/dataset/test.jsonl` in place produced two scoreboards making
   byte-identical claims about what they scored. **Compare the two `dataset`
   blocks before comparing any number across them.** Differing hashes mean
   two different test sets and the comparison is not a comparison; a `null`
   block means the `--test` file had no manifest beside it, which is fine for
   a hand-made set and disqualifying for a release argument.

6. **Read the scoreboard against the bar.** Beating the untuned baseline on
   every metric is necessary and nowhere near sufficient — the first tuned
   model scored 1.0 on contract validity, cause accuracy and confidence
   simultaneously by reading the `attributed` tag and nothing else. Six
   things decide a release:

   - contract validity 1.0;
   - **decoy rate low on all three adversarial slices** —
     `positional_probe`, `misattribution_probe`, `multi_misattribution_probe`
     — plus `wrong_attribution`. It rules out answering by position or by
     tag. It reads `n/a` on slices that carry no decoy; that is correct, not
     a gap. **A slice whose identities are in the training data does not
     count toward this bullet** — check that before reading it, with the
     intersection described under "contamination" below;
   - **`length_gap` ≤ 0.15, and not at the floor.** The gap is
     `length helps` minus `length misleads`, printed under the overall table
     as `Length gap (helps - misleads): <n> -- met | MISSED | not measured`
     and stored as `length_gap` / `length_gap_ok` in `scoreboard.json`.
     Apart, the model is counting words: the winning cause is the longer
     phrase in 15 of 19 catalog entries, so a word counter beats the decoy
     rate for free without reading anything. A wide gap invalidates the
     decoy rate.

     Two properties of the gate matter more than the number. It is
     **signed**, not `abs()`: the failure it exists to catch is asymmetric —
     high on `helps`, low on `misleads` — so a model that scores *better* on
     the harder slice passes rather than failing for being good. And it
     **abstains** when `length helps` is below 0.5, reporting `not measured`
     with `length_gap_ok: null`. A gap between two floor rates certifies
     nothing: the untuned baseline reads 0.0 and 0.0, gap 0.00, which an
     unconditioned threshold passes exactly as it passes v0.1.0's 1.0 and
     1.0. An abstention is not a pass — write **not measured** in the release
     notes, the same rule as `overconfidence rate` below;
   - `overconfidence rate` — of the causes it got wrong, how many it still
     graded `high`. `confidence carried` is extraction and cannot fail.
     **This one can go blind.** It is conditioned on errors, so a model that
     stops making them leaves it with no denominator: for v0.1.0 the tuned
     model got two causes wrong in 243 rows and both were inside a slice
     withdrawn as contaminated, leaving `n = 0` everywhere it counted. Check
     the denominator before reading the rate, and if it is zero on every
     uncontaminated slice, write **not measured** in the release notes.
     Do not borrow the number from a withdrawn slice to fill the gap, and do
     not read a small `n` as a pass — v0.1.0's earlier `0.1111 (18)` was
     called a pass and the 18 was manufactured by an answer-key bug (16 rows
     no answer could satisfy; see `docs/model-card.md`);
   - **Does it distinguish shared origins from coincidence?** Read
     `separate reasons` and `false shared` **together, or not at all.**
     Alone, either is trivially gamed: a model that always answers
     "independent" scores 0 on `false_shared_rate`, and a model that always
     answers "shared origin" scores 0 on `separate_reasons_rate`. The second
     is the obvious failure mode of the obvious correction to the first, and
     nothing measured it until now. **`false_shared_rate` must be ≤ 1 of
     19** — the whole `multi_misattribution_probe` slice, whose count is
     pinned by `tests/test_generate.py`. Check the ambiguous count printed
     under the table beside it: a large one means the phrase sets need
     narrowing, not that the model changed, and it shrinks the denominator
     the ratio above is read against.

   - **Is the answer the prompt's own `suggested fix` line handed back?**
     `suggestion echo` must be **0 of 253** — the whole test set. Every
     finding in a scan prompt carries a `suggested fix (deterministic,
     pre-reviewed — do not substitute): <text> | run: <cmd>` line, and that
     text is a *symptom* restated generically by `internal/remediation.For`,
     never a diagnosis. Returning it is the cheapest wrong answer available:
     it is fluent, it is on-topic, and it is already in the context window.
     The bar is zero rather than a tolerance because on this corpus a correct
     answer is never a suggestion string — measured, 0 of 253 rows have a
     stored winner cause that matches one — so every echo is a wrong answer
     and costs cause accuracy too. Read the two together; alone this rate
     only names the *mechanism* behind a cause miss, and a model can miss for
     other reasons at 0.0 echo.

     **This one can go vacuous, and it silently was.** The rate is `None`
     when nothing was measured, but a *populated* 0 can still mean nothing:
     the metric compares what the model said against the strings the prompt
     offered, so it can only fire if those strings are the ones kubeagent
     actually emits. Until `fc07804` they were not — the
     catalog authored its own, more helpful, wording per entry, and the two
     vocabularies were **disjoint**: 253 of 253 test prompts carried zero
     strings `internal/remediation.For` can produce. Re-scoring v0.1.0's
     recorded outputs against its own prompts returns `0.0 (253)`, which
     looks like a clean pass and is not a measurement at all. So a 0 here is
     a pass only when **`n` is 253 and `tests/test_dataset_suggestions.py`
     is green** — that test is what makes the prompt vocabulary kubeagent's,
     and without it the number is decoration.

     Note where the failure was actually seen: **live, not on the eval.**
     v0.1.0 scores 0.0 on the synthetic set and still handed back
     kubeagent's suggestion, clipped at the em dash, on live chaos
     scenarios — because at serve time the line finally carried strings the
     model had never been trained against. This decider is therefore a
     floor, not the detector. It fails a model that parrots on prompts it
     has seen; a model that only parrots on unfamiliar wording still needs
     a live run to catch.

   **What this bar does NOT decide, and a decider that was withdrawn.** An
   earlier bullet used to stand first here: cause accuracy on `none_of_these`,
   `own_cause` and `empty_candidates` substantially above zero, on the
   grounds that only those slices require an answer other than the entry's
   stored winner cause, so only they can catch a model reciting a
   memorised entry-to-cause lookup table. It was withdrawn because it does
   not do that. Scored against the known-broken first tune — a model that
   follows the `attributed` tag 79% of the time on `misattribution_probe` —
   `none_of_these` read 1.0. It clears the bar it was supposed to fail.
   (The same experiment read 0.5789 on `own_cause` and `empty_candidates`
   and this runbook used to cite those two as well. Withdrawn: 0.5789 was
   the pre-`70460e9` answer key's ceiling, 11/19, not a property of that
   model — see `docs/model-card.md`. The broken tune cannot be re-scored,
   since it ran against a 205-row test set, so its real score on those two
   slices is unknown.) A fourth slice built to replace it,
   `contradiction_probe`, was measured the same way (negative control v4)
   and read 1.0 cause / 0.0 decoy, because it reuses the read text of
   `none_of_these`, which is 15% of the curriculum — a trained trigger, not
   a reasoning test.

   Every trainable catalog entry appears in train, val and test, so **no
   slice in this eval separates a model that reads the evidence from one
   that recites per-entry answers.** Do not read this scoreboard as evidence
   of entry-level generalisation. Fixing it means holding whole catalog
   entries out of train and retraining; see `docs/design.md`.

   **Contamination — check this before reading the decoy bullet.** Train and
   eval must come from the same commit. When they do not — a long run started
   before a generator fix landed, which happened for v0.1.0 — the newer test
   rows were never excluded from the older training data, and their slices
   are uninterpretable rather than merely noisy. Measure it, do not estimate
   it: regenerate the training commit's `train`+`val` in a `git worktree`,
   union each example's `group` split on `+`, and intersect against this
   tree's `generate.test_set()` groups, counting per case. Report any slice
   with a non-zero count as contaminated and withdraw it from the bar for
   that release. For v0.1.0 that was `multi_misattribution_probe` (19 of 19)
   and `contradiction_probe` (14 of 19); every other slice was 0. `kv-eval`
   does not compute this yet — it should, so the number cannot rot in a doc.

   Then the live tier: `docs/runbooks/live-eval.md`.
