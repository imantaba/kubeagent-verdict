# Runbook: training a release candidate

All commands run from the repo root, inside the venv. The full pipeline is
CPU-only and takes several hours on a workstation — run the training step
under `nohup` and watch `train_log.json`.

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
   Budget ~30 minutes for 224 rows at this size. Note the endpoint: `kv-eval`
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

6. **Read the scoreboard against the bar.** Beating the untuned baseline on
   every metric is necessary and nowhere near sufficient — the first tuned
   model scored 1.0 on contract validity, cause accuracy and confidence
   simultaneously by reading the `attributed` tag and nothing else. Four
   things decide a release:

   - contract validity 1.0;
   - **decoy rate low on all three adversarial slices** —
     `positional_probe`, `misattribution_probe`, `multi_misattribution_probe`
     — plus `wrong_attribution`. It rules out answering by position or by
     tag. It reads `n/a` on slices that carry no decoy; that is correct, not
     a gap;
   - **`length helps` and `length misleads` close together.** Apart, the
     model is counting words: the winning cause is the longer phrase in 15
     of 19 catalog entries, so a word counter beats the decoy rate for free
     without reading anything. A wide gap invalidates the decoy rate;
   - `overconfidence rate` — of the causes it got wrong, how many it still
     graded `high`. `confidence carried` is extraction and cannot fail.

   Then the live tier: `docs/runbooks/live-eval.md`.
