# kubeagent-verdict

Training pipeline for the tiny local model behind kubeagent's
`--investigate` local verdict mode: a LoRA fine-tune of Qwen3-0.6B that
answers verdict contract v1, exported to Q8_0 GGUF for CPU-only serving
via Ollama or llama-server. kubeagent itself does not change here — this
repo produces the model that mode consumes.

## The contract

The model answers kubeagent's verdict contract v1 — a bare JSON object,
one verdict row per flagged workload plus a short summary. The contract
and every prompt bound are pinned byte-for-byte against kubeagent v1.23.0
in `contract/PIN.md`; the golden fixture in `contract/golden/` is a
captured kubeagent prompt, and `src/kubeagent_verdict/contract.py` renders
it byte-identically (tested).

## Pipeline

    pip install -e ".[dev]"            # light: dataset + evals, stdlib-only
    pip install -e ".[train,export]" --extra-index-url https://download.pytorch.org/whl/cpu

    kv-dataset --seed 17 --size 5500 --out out/dataset
    kv-train   --dataset out/dataset --out out/adapter
    kv-export  --adapter out/adapter --workdir out/export --out dist/
    kv-eval    --test out/dataset/test.jsonl --model kubeagent-verdict --out out/eval

Runbooks with timings and verification steps: `docs/runbooks/`.

## Data provenance (hard rule)

Training data comes ONLY from synthetic generation (the catalog +
allowlisted fictional names) and from the redacted chaos-corpus artifacts
kubeagent's nightly CI publishes. No live cluster identifier — node name,
namespace, hostname, IP, kubeconfig path or context — may appear in any
tracked file. `data/corpus/README.md` records the exact CI run each
snapshot came from; a provenance test bans identifier-shaped text from
every generated example.

## Scoreboard

(Recorded by the release process — see docs/runbooks/train.md step 4.)

## License

Apache-2.0. Contributions require DCO sign-off (`git commit -s`).
