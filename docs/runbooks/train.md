# Runbook: training a release candidate

All commands run from the repo root, inside a venv installed from the
pinned lock file:

    pip install -r requirements.lock -e .

That buys the exact dependency versions the release was built and
evaluated against, not whatever `pyproject.toml`'s loose lower bounds
resolve to today. The full pipeline is CPU-only, and the training step
alone runs **about 28 hours** at the size-8000 build below (the 0907 run,
the 7 September test run whose model this retrain replaces, took about 8
seconds per example pass, and 16 or 32 threads gave the same wall time,
so time scales with rows and nothing else) — run it under
`nohup` and watch `out/adapter-checkpoint/progress.json` (step 3;
**not** `train_log.json`, which does not exist until the run is over).

**2026-09-19 pre-run estimate for this retrain's build (not yet run).**
Budget about **33 hours**, not the 28 above. The 28 scales 0907's time
per example by rows. This estimate scales 0908's time by tokens, the
formula spec section 11 of
`docs/superpowers/specs/2026-09-19-training-targets-fix-design.md` uses.
0908, the most recent full run, took 31.8 hours for 12,577,240 training
tokens (both epochs). This build's train split is 6,579,981 tokens per
epoch with the real Qwen3-0.6B tokenizer, 13,159,962 across both epochs.
So the training step takes about 31.8h × (13,159,962 ÷ 12,577,240) ≈
**33h16m**. That is an estimate, not a measurement. `train_log.json`
records no duration, so once the run finishes, measure it the way the
17h42m figure below was measured — from process start to the adapter's
own mtime — and put that number here and everywhere else this runbook
quotes the estimate. The step count is exact, not estimated: the train
split is 6,377 rows, so at grad_accum 16 the run is 2 × ⌊6377 ÷ 16⌋ =
**796 optimizer steps**, and `train_log.json`'s `optimizer_steps`
confirms it when the run ends.

1. **Dataset** (seconds):

       kv-dataset --seed 17 --size 8000 --out out/dataset

   Check `out/dataset/manifest.json`: train+val ≤ 8000 (the shortfall is
   examples dropped for colliding with a corpus-test fixture's group),
   test > 0, every case present in `case_counts`.

   A probe set built with `kv-dataset --probe-cousins` (see
   `docs/how-training-works.md`) carries no job-2 answer keys; score it
   with `kv-eval --no-job2`, or job 2 refuses the run instead of reading
   `n/a`.

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
   **2026-09-19 estimate:** the exam is 263 rows now, not 243. At the same
   ~1.8 rows/minute that is about 146 minutes, **~2½ hours**. It is scaled
   from the 149-row measurement above, not timed afresh: the 2026-09-19
   fix replayed 0908's banked outputs instead of re-serving (see below),
   so it produced no new timing.
   Note the endpoint: `kv-eval`
   defaults to Ollama's `http://localhost:11434/v1`, so a llama-server run
   without `--endpoint` silently scores whatever Ollama is serving.

   **Before serving anything, check whether the control is already banked.**
   `evaluate` records each row's model output verbatim in `results.jsonl`
   precisely so a run can be re-scored without re-running inference, and it
   takes a `chat_fn` — so a previous run replays through the *current* scoring
   code by handing it the banked outputs in file order:

   `kv-eval --test <rows> --replay out/eval-<prev> --out <dir>` does this
   with both alignment guards and carries the prior run's model and
   endpoint; it still cannot prove the prompts match, so compare `messages`
   first.

       rows = [...]                      # the test rows, same order as results
       banked = [json.loads(l) for l in open('out/eval-<prev>/results.jsonl')]
       it = iter(b['output'] for b in banked)
       res = evaluate(rows, lambda messages: next(it))

   That is a real control, not a shortcut: the generations are the old model's,
   and every metric is recomputed by today's code. It cost seconds where
   re-serving costs the ~2¼ hours above (~2½ hours at today's 263-row exam,
   2026-09-19 estimate). It is valid only when the rows are the
   same rows — assert `len(banked) == len(rows)` and confirm the test bytes
   match, because `evaluate` walks rows positionally and a length-matched but
   reordered file would score silently wrong.

   The replay path does **not** apply when the scoring change needs
   something the banked run never produced. A job bar or decider added
   after a run was banked reads `n/a` on it rather than a number: job 3
   needs each row's meta to carry a `label`, and a run banked against
   the exam shape before this rescope has no label to give it, so it
   reports `n: 0` rather than a score built from a partial population.
   Re-scoring through `evaluate` regenerates the row from the current
   test set, which is why the replay goes through `evaluate` rather
   than reading `results.jsonl` fields directly.

   Then move the old model aside so nothing downstream picks it up:
   `mv dist/ dist-v<N>-superseded/`.

3. **Train** (~33 hours at this build, a pre-run estimate; CPU):

       nohup kv-train --dataset out/dataset --out out/adapter > out/train.out 2>&1 &

   **The older 4,292-example build took about 17½ hours.** That is
   measured, not estimated: one run has been timed end to end at
   **17h42m** — 4,292 examples, two epochs, 536 optimizer steps, just
   under two minutes per step. Two
   earlier versions of this line under-budgeted, first at "several hours"
   and then at "upwards of 15 hours" offered as a floor because no
   completed run had both a start and an end on record. One does now, and
   the floor was low by nearly three hours. The attempt that stopped at
   12h19m in a power loss was roughly 70% through, not a run that was
   failing.

   That 17h42m run and 0908 (31.8 hours, spec section 11) are both older,
   smaller builds. **2026-09-19 pre-run estimate for this retrain's
   build:** about **33h16m**, by the token-ratio formula in the box near
   the top of this runbook. It is an estimate, not a measurement: nothing
   has been trained on this build yet. Measure the real duration the way
   the 17h42m was measured, and put it here in place of the estimate.

   A smoke run first is cheap and catches config errors:
   `kv-train --dataset out/dataset --out out/smoke-adapter --limit 32 --epochs 1`.

   **Progress is two questions, and they have different answers.**

   *How far along is it?* — `cat out/adapter-checkpoint/progress.json`:
   optimizer steps done, which epoch, how far into it, and both totals to
   read them against. It is written at every checkpoint.

   *Is it still moving?* — a CPU-time delta, below. Do not use
   `progress.json` for this. At the pinned recipe the run is ~536 optimizer
   steps on the older build measured above; this retrain's build is
   **796 optimizer steps** (2 × ⌊6,377 ÷ 16⌋, exact — spec section 11 says
   "about 796"), so at the default interval the file is rewritten about 32
   times across the whole run — tens of minutes apart on this hardware. An
   mtime that has not moved for a few minutes means nothing.

   Neither question is answered by the two things this runbook used to
   offer, and they were wrong in the same way. `train_log.json` cannot be
   watched "once it exists", because `run_training` creates its output
   directory *after* the epoch loop (`out_dir.mkdir` at train.py:213, loop
   at :181) — it exists only when the run is already over. And
   `out/train.out` stops growing the moment the weight load finishes and
   then stays byte-identical for the whole run, so tailing it after the
   first minute tells you nothing.

   What does distinguish working from hung is a CPU-time delta:

       ssh host 'a=$(ps -o times= -p PID); sleep 15; b=$(ps -o times= -p PID); echo $((b-a))'

   A healthy run on this box returns ~200 CPU-seconds per 15 wall-seconds,
   i.e. ~14 cores busy. `ps -o pcpu=` reads the other way and is worth a
   glance too: it is a *lifetime* average, so a process that quietly stopped
   working shows a falling one, while a healthy run holds steady — this run
   sat at 1335–1336% across eight hours.

   **The figure is measured now.** 4292 rows x 2 epochs at grad_accum 16 is
   536 optimizer steps — exactly what the finished run did — and it took
   **17h42m** on this hardware, just under two minutes per step, measured
   from process start to the adapter's own mtime. This paragraph used to say
   there was no trustworthy figure to quote and to record the real one the
   first time a run was watched end to end; that is what happened. The two
   older runs still offer only loose upper bounds — 17h and 24h between
   dataset-written and adapter-written, both including idle time before
   launch — so they stay bounds rather than durations, and the measurement
   above does not come from them. The 17h42m measurement is history now
   too: it is the 4,292-example build, not this one. **This retrain's build
   is 6,377 train rows and 796 optimizer steps, and its own duration is not
   measured yet.** The box near the top of this runbook carries the
   2026-09-19 pre-run estimate (~33h16m) and says what replaces it.

   **Set `HF_HUB_OFFLINE=1`.** `kv-train` contacts the Hugging Face Hub for the
   base model even when it is already in `~/.cache/huggingface`, and a hub
   round trip that fails takes the run with it —
   `httpx.RemoteProtocolError: Server disconnected without sending a response`,
   raised before a single optimizer step. The weights were on disk the whole
   time. Offline mode reads the cache and never dials out, which removes a
   network dependency the training step does not otherwise have:

       nohup env HF_HUB_OFFLINE=1 kv-train --dataset out/dataset --out out/adapter > out/train.out 2>&1 &

   Two notes on running it over ssh. `nohup` is what lets the run survive the
   ssh session ending, so a dropped connection costs nothing — but the shell
   that launches it may be killed before `echo $! > out/train.pid` runs, which
   leaves an empty pidfile beside a healthy process. Recover the real pid with
   `ps -eo pid,cmd | grep "[k]v-train"` and write it back.

   **A run that dies can now be resumed**, so host stability costs minutes
   rather than a day:

       nohup env HF_HUB_OFFLINE=1 kv-train --dataset out/dataset --out out/adapter --resume > out/train.out 2>&1 &

   It restarts from the last checkpoint, redoing at most `--checkpoint-every`
   optimizer steps of work (25 by default; `0` disables checkpointing). A
   resumed run is **bit-for-bit identical** to one that was never
   interrupted, which `tests/test_train_checkpoint.py` asserts as an
   equality rather than by inspection: every piece of state resume carries
   — the optimizer moments, the torch RNG that LoRA dropout draws from, the
   Python RNG that orders each epoch, the position within the epoch — moves
   the weights if it is dropped, and moving the weights fails that test.

   Two things it refuses rather than guesses at:

   - **A checkpoint from a different recipe or dataset**, rejected by
     fingerprint. This is the one failure here with no downstream detector:
     it finishes, writes an adapter, and reports a clean run, having trained
     something no scoreboard can tell apart from the model you meant.
   - **`--resume` with no checkpoint present**, which is an error and not a
     silent fresh start. The usual cause is `--out` naming the wrong
     directory. A run that died *before* its first checkpoint genuinely has
     nothing to resume — start it normally.

   The checkpoint sits at `out/adapter-checkpoint/`, a sibling of `--out`
   and deliberately never inside it, so `out/adapter/` existing still means
   exactly one thing: the run finished. A completed run deletes its own
   checkpoint, so a stale one cannot be resumed into.

   This paragraph used to say the opposite — that `kv-train` had no
   checkpointing, that a run dying at 99% produced nothing at all, not a
   partial adapter and not a resumable state. That was true when it was
   written, and it was written because a run reached 12h19m and was lost
   whole to a hard power loss with `out/adapter/` never created. That run is
   why the rest of this section exists; it is no longer what a power loss
   costs.

   Tell a power loss from a crash before assuming either. A crash inside
   `kv-train` appends a traceback to `out/train.out`, because stdout and
   stderr are redirected there. A power loss appends nothing, and leaves its
   evidence in the system log instead:

       journalctl --list-boots | tail -3          # a new boot you did not ask for
       journalctl -b -1 --no-pager | tail -20     # previous boot ends mid-stride,
                                                  # with no shutdown sequence
       journalctl -b 0 --no-pager | grep -iE "recovering journal|Dirty bit"

   `Dirty bit is set. Fs was not properly unmounted and some data may be
   corrupt` is the confirmation, and it is also an instruction: **re-verify
   the dataset before relaunching**, and re-verify it even when resuming.
   `--resume` fingerprints the recipe and the encoded rows, so it refuses a
   dataset that changed — but a corrupted file that still parses is a
   different dataset, and being refused tells you nothing about which of the
   two is the corrupt one. Compare all four files against the machine they
   were generated on:

       sha256sum out/dataset/{train,val,test}.jsonl out/dataset/manifest.json

   And when polling that pid from another machine, **an ssh failure is not
   evidence the process ended**. `! ssh host "kill -0 $PID"` cannot distinguish
   exit 1 (pid gone) from exit 255 (could not connect), so one unreachable
   moment reports a healthy two-hour-old run as finished. Poll for an explicit
   token instead — `ssh host "kill -0 $PID && echo ALIVE || echo GONE"` — and
   treat anything that is neither `ALIVE` nor `GONE` as "ask again".

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
   `seed`, `size`, `test_rows`, a SHA-256 over `out/dataset/manifest.json`,
   and a second SHA-256 over the `--test` file's own bytes. Every other field
   of `run` is a property of the serving side, a basename, or a row count two
   same-sized test sets share — so before this block a retrain that overwrote
   `out/dataset/test.jsonl` in place produced two scoreboards making
   byte-identical claims about what they scored. **Compare the two `dataset`
   blocks before comparing any number across them.**

   `test_sha256` is the one that decides whether a comparison is a comparison:
   it is the hash of the file the rows were read from, so two runs agreeing on
   it were judged against the same test set. `manifest_sha256` answers a
   different question. `kv-dataset` builds `test.jsonl` from
   `generate.test_set()`, which takes neither a seed nor a size, so a
   `--seed 17` run and a `--seed 42` run write the same 263 test rows and two
   different manifests. A differing `manifest_sha256` beside a matching
   `test_sha256` therefore means **same rows, different dataset config** —
   often exactly the comparison you want, not a reason to discard it. A
   differing `test_sha256` is the disqualifying one. A `null` block means the
   `--test` file had no manifest beside it, or had one that could not be read
   or parsed — the three are indistinguishable here — which is fine for a
   hand-made set and leaves a release argument with nothing to check *in the
   run directory*.

   That is weaker than "disqualifying", which is what this paragraph used to
   say, and the correction is worth writing down because the stronger claim
   would have thrown away two usable runs. Every run recorded before `e9262fd`
   stores `dataset: null`, including the v0.1.0 baseline and the
   negative-control re-score. Both were qualified afterwards without the hash:
   `score.evaluate` walks the test rows in file order and appends one result
   per row, so `results.jsonl` line *i* is `test.jsonl` line *i*, and each old
   run's per-row identity can be reconstructed from what it *did* store and
   compared position for position against the test file scored today. The
   control matched all 253 positions; the baseline's 243 are exactly those
   253 minus the ten `shared_origin_probe` rows added afterwards, with zero
   positional mismatches.

   Those counts are the file as it stood when that check was run. `test.jsonl`
   has since grown to **263** rows, by appending the ten
   `shared_origin_decoy_probe` rows and nothing else: the first 253 lines are
   byte-identical, so the check re-runs unchanged against the file's prefix and
   both older runs stay qualified. That is the only reason an append is
   tolerated at all — `test_set()` builds the exam by concatenation, never by
   interleaving, and `tests/test_generate.py` pins both the per-slice counts and
   the order. A change that renumbers an existing row invalidates every banked
   scoreboard and is a different decision from this one.

   That check is not a weaker substitute for the hash — it is stronger. The
   hash is computed after scoring (`cli.py` reads the file, runs the whole
   eval, then hashes), so it describes the file at the end of the run rather
   than the bytes that were scored. The positional check describes what was
   actually scored. Read the rule as: a `null` block means the cheap check is
   unavailable and the run needs the expensive one, not that the run is
   unusable.

   Read both hashes, not one. `kv-dataset` writes the test file and the
   manifest as two separate writes and nothing afterwards ties them together,
   so a hand-edited `test.jsonl` beside an untouched manifest matches on
   `manifest_sha256` and differs on `test_sha256` — that pair means the rows
   were scored against a file the manifest no longer describes. Then check one
   number across the two blocks: `dataset.test_rows` is what the generator
   wrote, `run.rows_available` is what the eval read, and they must be equal
   on an unlimited run. They are computed by different code from different
   files, so a mismatch is the cheapest available signal that the two are no
   longer the same set of rows. `test_sha256: null` inside an otherwise
   populated block means the file could not be re-read after scoring — treat
   it as no answer, not a pass.

6. **Read the scoreboard against the bar.** Beating the untuned baseline on
   every metric is necessary and nowhere near sufficient — the first tuned
   model scored 1.0 on contract validity, cause accuracy and confidence
   simultaneously by reading the `attributed` tag and nothing else. A
   release needs three job bars and five more things:

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
     as `Length gap (helps - misleads): <n> -- <verdict>`, where the verdict
     is `met (bar: <= 0.15)`, a `MISSED (bar: <= 0.15)` sentence, or a
     `not measured` sentence naming which of the two abstentions fired; and
     stored as `length_gap` / `length_gap_ok` in `scoreboard.json`.
     Apart, the model is counting words: the winning cause is the longer
     phrase in 15 of 19 catalog entries, so a word counter beats the decoy
     rate for free without reading anything. A wide gap invalidates the
     decoy rate.

     Two properties of the gate matter more than the number. It is
     **signed**, not `abs()`: the failure it exists to catch is asymmetric —
     high on `helps`, low on `misleads` — so a model that scores *better* on
     the harder slice passes rather than failing for being good. And it
     **abstains** when `length helps` is below 0.5, reporting `not measured`
     with `length_gap_ok: null`. The floor bounds that one rate; `length
     misleads` may read anything beside it. A model failing the slice a word
     counter would ace has not shown enough for the difference to certify
     anything — the untuned baseline is the motivating case, reading 0.0 and
     0.0 for a gap of 0.00 that an unconditioned threshold passes exactly as
     it passes v0.1.0's 1.0 and 1.0. An abstention is not a pass — write
     **not measured** in the release notes, the same rule as `overconfidence
     rate` below.

     What the sign leaves open, so you read the number knowing it: the
     **mirror** shortcut, always answering the shorter candidate. It is as
     evidence-free as word counting, and no negative gap can ever read
     `MISSED` however extreme. In its pure form it scores ~0.0 on `helps`, so
     the floor catches it and it reads `not measured` — refused, but by the
     floor and not by the sign. Its partial form — around 0.5 on `helps`
     against 1.0 on `misleads`, gap −0.5 — **passes this decider**, and no
     other codified decider catches it: overall cause accuracy carries no
     numeric bar, only "beats the untuned baseline", and that baseline is
     0.0576. Read `cause when length helps` off the printed table by eye — a
     model sitting near 0.5 there has not earned the pass this bar just gave
     it.

     The gate is computed on the **overall** block only. Re-measured for the
     v1.24.0 rescope, the overall `misleads` denominator is now 1 row (56
     helps against 1 misleads: `wrong_attribution` 19/0, `positional_probe`
     18/1, `misattribution_probe` 19/0). At a denominator of 1 there is no
     fraction of a row to tune 0.15 against — the misleads rate can only
     read 0.0 or 1.0 — so 0.15 is kept as the meaning "the two slices must
     agree" rather than as a number calibrated to this population. Judge
     a case by its two rates, never by arithmetic on them against this bar;
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
   - **Job 1 — echo the decided cause.** Mean ≥ 0.9. kubeagent's own
     rules now decide some rows before the model ever answers; on a
     decided row the model's only job is to repeat the decided cause and
     give a rationale that does not deny it. A model that copies the
     decided line and pads a filler rationale can score close to 1.0
     here — the model card says so plainly. This bar measures
     contract-following. Job 2 is where skill shows.

   - **Job 2 — name the cause on undecided rows.** Mean ≥ 0.7. The
     expected answer is the story's own cause, or `none_of_these` when
     the menu holds nothing right. This is the old cause-accuracy work,
     carried over onto the rows the rules leave open.

   - **Job 3 — say whether it is one cause or several.** Mean ≥ 0.9 over
     the 39 prompts with two or more flagged workloads, and it decides
     the release on its own. One bar reads the summary's own claim
     against a `shared` / `separate` / `none` label, so a model cannot
     pass by always giving the same answer — the same guard the two old
     shared-origin rates existed for, now read as a single number
     instead of a pair.

   - **Is the answer the prompt's own `suggested fix` line handed back?**
     `suggestion echo` must be **0**, over every row the model answered — 263
     today when it answered them all, 253 for a run scored against the exam as
     it stood before the `shared_origin_decoy_probe` append. What that
     denominator does and does not prove is below. Every
     finding in a scan prompt carries a `suggested fix (deterministic,
     pre-reviewed — do not substitute): <text> | run: <cmd>` line, and that
     text is a *symptom* restated generically by `internal/remediation.For`,
     never a diagnosis. Returning it is the cheapest wrong answer available:
     it is fluent, it is on-topic, and it is already in the context window.
     The bar is zero rather than a tolerance because on this corpus a correct
     answer is never a suggestion string — measured, 0 of 263 rows have a
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
     a pass only when **`tests/test_dataset_suggestions.py` is green** — that
     test renders `generate.test_set()` in full, so it covers the appended
     rows without amendment, and it is what makes the prompt vocabulary
     kubeagent's. Without it the number is decoration.

     That test is the whole guard, not half of one. This rule used to ask for
     a full row count as well, and a full row count would not have caught the
     bug it was written for: when the two vocabularies were disjoint, `n` read
     253 of 253 — the entire exam of the day — and the reading was still
     empty. A count of rows cannot see whether the strings in them mean
     anything. Only the test can.

     Read `n` anyway, but read it as a different question: how much of the
     exam the scorer could judge. A row leaves this rate when the prompt
     offered no suggestion line to echo, or when the scorer got no verdict
     out of the reply. Today every one of the 263 prompts carries a
     suggestion line, so in practice a missing row is one the scorer could
     not read — and `contract` already charges the model for it, over all
     263 rows. 0908 is the worked example: echo reads `0.0 (262)` because one
     reply was not valid JSON, so no cause came off it. Note what that row is
     not. It is not a truncated reply and not a refusal: it is a complete
     answer that names a cause for both flagged workloads, with one extra `}`
     two thirds of the way in. A single stray character costs the whole row,
     here and on every other rate that reads a cause. `contract` reads 0.9696
     over 263 with 8 failures, that row among them. So one or two missing
     rows is still a pass; the model has already paid for them on the decider
     that counts them. A large gap is not a pass — it says most of the exam
     never produced a readable answer, and a 0 over the remainder is a
     statement about a handful of rows.

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
