# Runbook: training a release candidate

All commands run from the repo root, inside the venv. The full pipeline is
CPU-only and takes several hours on a workstation — run the training step
under `nohup` and watch `train_log.json`.

1. **Dataset** (seconds):

       kv-dataset --seed 17 --size 5500 --out out/dataset

   Check `out/dataset/manifest.json`: train+val ≤ 5500 (the shortfall is
   examples dropped for colliding with a corpus-test fixture's group),
   test > 0, every case present in `case_counts`.

2. **Train** (hours, CPU):

       nohup kv-train --dataset out/dataset --out out/adapter > out/train.out 2>&1 &

   Progress: `python -c "import json; print(len(json.load(open('out/adapter/train_log.json'))['losses']))"`
   once it exists; before that, `tail out/train.out`. A smoke run first is
   cheap and catches config errors: `kv-train --dataset out/dataset --out out/smoke-adapter --limit 32 --epochs 1`.

3. **Export** (~30 min: clone, convert, cmake build, quantize):

       kv-export --adapter out/adapter --workdir out/export --out dist/

   Produces `dist/kubeagent-verdict-0.6b-q8_0.gguf`, `dist/Modelfile`,
   `dist/SHA256SUMS`. The chain ends with a llama-cli load-verify; if that
   fails, nothing in `dist/` is trustworthy.

4. **Serve and eval**:

       out/export/llama.cpp/build/bin/llama-server -m dist/kubeagent-verdict-0.6b-q8_0.gguf --port 8080 &
       kv-eval --test out/dataset/test.jsonl --endpoint http://localhost:8080/v1 \
               --model kubeagent-verdict --out out/eval

   Baseline for comparison: convert the untuned base with the same chain
   (`convert_hf_to_gguf.py` on the raw `Qwen/Qwen3-0.6B` download, then
   `llama-quantize ... Q8_0`), serve it the same way, and run kv-eval into
   `out/eval-baseline`. The scoreboard delta is the release evidence.
