# Runbook: training a release candidate

All commands run from the repo root, inside a venv installed from the
pinned lock file:

    pip install -r requirements.lock -e .

That buys the exact dependency versions the release was built and
evaluated against, not whatever `pyproject.toml`'s loose lower bounds
resolve to today. The full pipeline is CPU-only, and the training step
alone runs **upwards of 15 hours** on a workstation — run it under
`nohup` and watch `out/adapter-checkpoint/progress.json` (step 3;
**not** `train_log.json`, which does not exist until the run is over).

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

   **Before serving anything, check whether the control is already banked.**
   `evaluate` records each row's model output verbatim in `results.jsonl`
   precisely so a run can be re-scored without re-running inference, and it
   takes a `chat_fn` — so a previous run replays through the *current* scoring
   code by handing it the banked outputs in file order:

       rows = [...]                      # the test rows, same order as results
       banked = [json.loads(l) for l in open('out/eval-<prev>/results.jsonl')]
       it = iter(b['output'] for b in banked)
       res = evaluate(rows, lambda messages: next(it))

   That is a real control, not a shortcut: the generations are the old model's,
   and every metric is recomputed by today's code. It cost seconds where
   re-serving costs the ~2¼ hours below. It is valid only when the rows are the
   same rows — assert `len(banked) == len(rows)` and confirm the test bytes
   match, because `evaluate` walks rows positionally and a length-matched but
   reordered file would score silently wrong.

   The replay path does **not** apply when the scoring change needs something
   the banked run never produced. A decider added after a run was banked reads
   n/a on it rather than a number: `paired_contrast` needs a `pair_key` that
   older `results.jsonl` files do not carry, so it reports `n: 0` — and a
   decider needing rows the old run was never served (its twin slice, say)
   reports `unpaired`, not a score built from half-pairs. Re-scoring through
   `evaluate` regenerates both, which is why the replay goes through
   `evaluate` rather than reading `results.jsonl` fields directly.

   Then move the old model aside so nothing downstream picks it up:
   `mv dist/ dist-v<N>-superseded/`.

3. **Train** (15+ hours, CPU):

       nohup kv-train --dataset out/dataset --out out/adapter > out/train.out 2>&1 &

   **Budget upwards of 15 hours.** That is a floor, not an estimate, and
   the honest reason is that no run here has been timed end to end: no
   completed run has both a start and an end on record. What *is* measured
   is two consecutive attempts that never finished — one stopped at 12h19m
   when the box lost power, and the next was still running at 15h15m, by
   direct `ps` reading, when the host became unreachable. An earlier version
   of this line said "several hours"; that is wrong by at least a factor of
   three, and under-budgeting is what makes a healthy run look hung.

   A smoke run first is cheap and catches config errors:
   `kv-train --dataset out/dataset --out out/smoke-adapter --limit 32 --epochs 1`.

   **Progress is two questions, and they have different answers.**

   *How far along is it?* — `cat out/adapter-checkpoint/progress.json`:
   optimizer steps done, which epoch, how far into it, and both totals to
   read them against. It is written at every checkpoint.

   *Is it still moving?* — a CPU-time delta, below. Do not use
   `progress.json` for this. At the pinned recipe the run is ~536 optimizer
   steps, so at the default interval the file is rewritten about 21 times
   across the whole run — tens of minutes apart on this hardware. An mtime
   that has not moved for a few minutes means nothing.

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

   **Budget hours, and do not guess.** 4292 rows x 2 epochs at grad_accum 16
   is ~536 optimizer steps, and that had not finished at 8h on this hardware.
   The two previous full runs left only loose upper bounds — 17h and 24h
   between dataset-written and adapter-written — and both include idle time
   between generating the dataset and launching, so neither is a duration.
   There is no trustworthy figure to quote yet; record the real one the first
   time a run is watched end to end.

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

     The gate is computed on the **overall** block only. The two rates appear
     on every case, but 0.15 is calibrated against the overall 12-row
     `misleads` denominator where one row is 0.083; in the three cases that
     carry length-keyed rows at all that denominator is 4, where one flipped
     row is 0.25 and clears the bar on its own. Judge
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
   - **Does it distinguish shared origins from coincidence?** Read
     `separate reasons` and `false shared` **together, or not at all.**
     Alone, either is trivially gamed: a model that always answers
     "independent" scores 0 on `false_shared_rate`, and a model that always
     answers "shared origin" scores 0 on `separate_reasons_rate`. The second
     is the obvious failure mode of the obvious correction to the first, and
     nothing measured it until now. **`false_shared_rate` must be ≤ 1 of
     19** on `multi_misattribution_probe` **and ≤ 1 of 10 on
     `shared_origin_decoy_probe`**; both counts are pinned by
     `tests/test_generate.py`. The second slice is the one that matters. It is
     `shared_origin_probe` rendered from the same ten scenarios and the same
     seeds with the cluster-wide read *healthy*: identical workloads, identical
     candidate menus in identical order, identical evidence labels, and the
     correct answer is separate causes. Nothing that keys on a label, a
     position, or a tag can pass both halves of the pair, which is what the
     pair is for. Read the halves on their own slices — a scoreboard that
     reports `false shared` only on 19 rows is a run against the pre-append
     253-row exam, and decider 5 is then measured on the weaker denominator it
     had before. Check the ambiguous count printed
     under the table beside it: a large one means the phrase sets need
     narrowing, not that the model changed, and it shrinks the denominator
     the ratio above is read against.

     One limit, so it is not read as more than it is: the decoy slice **could
     not have failed the 0830 model**, which answered "separate reasons" to
     every shared-origin question and would score 1.0 on it. It is a trap for a
     model corrected toward "shared", not evidence about one that was never
     tempted. Its `confidence carried` is weak for a second reason — a decoy
     row's correct confidences are the ones already printed in the prompt.

     The **pair does not share that limit**, and it is the number to read
     first. `paired shared-origin (both halves right)` scores a pair 1.0 only
     when the probe half claims a shared origin *and* its twin denies one, so
     every habit that answers both halves the same way scores 0.0 on it
     whichever answer it picks — the 0830 model scores **0.0**. **The bar is
     ≥ 0.7 of 10.** Read anything at or below 0.3 as *no evidence of reading*:
     answering each row independently by coin flip lands a pair 0.25 of the
     time, so a score in that band is what chance produces and is not a
     partial pass.

     Read the two rates above as **marginals of this one**, and distrust them
     when they disagree with it. The 0901 model scored `separate reasons` 0.5
     and `false shared` 0.4 — two middling numbers that read as partial skill
     and cleared this decider's pre-registered bar in its letter — while
     scoring **0.1** paired: nine of its ten pairs answered both worlds
     identically, so the verdict was a function of which scenario it was
     looking at rather than of what the reads said. Neither marginal can see
     that, because a per-scenario constant landing right half the time is
     arithmetically indistinguishable from half-skill until the halves are
     joined. That is the whole reason this number exists.

     `the answer changed with the evidence` is printed beside it and is a
     **diagnostic, not credit**: a model that flips with the evidence and gets
     the direction wrong every time reads 1.0 there and 0.0 on the score. It
     bounds the score from above, so the gap between them is "changed, but
     backwards". Both read **n/a** on a run against the frozen 253-row exam,
     which carries the probe half and no twin — ten half-pairs are not a
     score, and a decider that printed a number there would be reporting one
     it could not have measured.

     There is a second way to get that n/a, and it looks like diligence.
     `paired_contrast` builds its pairs from **one** `results` list, so the
     two halves must be scored in the **same run**. Scoring the frozen 253
     and the ten decoy rows as two `kv-eval` invocations — the obvious way
     to read the halves "separately" — puts each twin in a different results
     file, and every pair reports `unpaired`. Score
     `out/dataset/test.jsonl` whole, all 263 rows, exactly as step 2 writes
     it: the scoreboard already prints one row per slice, so the halves are
     still read separately, and the pair is still joined. `unpaired: 10`
     under the table is the tell that this happened.

   - **Is the answer the prompt's own `suggested fix` line handed back?**
     `suggestion echo` must be **0 of 263** — the whole test set, or 0 of 253
     for a run scored against the exam as it stood before the
     `shared_origin_decoy_probe` append. Every
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
     a pass only when **`n` is the full row count of the exam that was scored
     (263 today, 253 before the append) and
     `tests/test_dataset_suggestions.py` is green** — that test renders
     `generate.test_set()` in full, so it covers the appended rows without
     amendment, and it is what makes the prompt vocabulary kubeagent's.
     Without it the number is decoration.

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
