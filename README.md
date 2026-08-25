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

    # reproducible instead: pip install -r requirements.lock -e .
    # buys the exact dependency versions the shipped model was trained and
    # evaluated against, not whatever pyproject.toml's loose lower bounds
    # resolve to today

    kv-dataset --seed 17 --size 5500 --out out/dataset
    kv-train   --dataset out/dataset --out out/adapter
    kv-export  --adapter out/adapter --workdir out/export --out dist/
    kv-eval    --test out/dataset/test.jsonl --model kubeagent-verdict --out out/eval

Runbooks with timings and verification steps: `docs/runbooks/`.

## Data provenance (hard rule)

Training data comes ONLY from synthetic generation (the catalog +
allowlisted fictional names) and from the redacted chaos-corpus artifacts
kubeagent's nightly CI publishes. No real, live cluster identifier — node
name, namespace, hostname, IP, kubeconfig path or context — may appear in
any tracked file. `data/corpus/README.md` records the exact CI run each
snapshot came from. Provenance tests guard this, but read them narrowly:
they are a denylist of five known leak shapes — a dotted-quad IP, an
`http(s)://` scheme, the word "kubeconfig", a `/home/` path prefix, a bare
`@` — not a scan for every token outside the fictional vocabulary. They
run over a generated train/val batch *and* over `generate.test_set()`, and
a third test asserts the scanned corpus renders every trainable catalog
entry, since a denylist cannot guard prose it never emits. One carve-out:
**all four** corpus files still carry
the chaos harness's own deterministic name for the disposable node of the
cluster it creates and tears down inside one CI run —
`kubeagent-chaos-v1-<minor>-worker` in the three kind files,
`k3d-kubeagent-chaos-k3s-v1-34-agent-0` in the k3s one. Neither is a live
identifier: they name no reachable node and no real cluster. See
`data/corpus/README.md` for why those rows were kept byte-identical rather
than scrubbed — and for the correction, since this repo previously
documented the k3s file as the clean one.

## Scoreboard

v0.1.0, over the 243-row corpus-derived test set at temperature 0, with
the untuned Qwen3-0.6B base as the floor. The full per-slice tables are in
`docs/model-card.md`.

| | released model | untuned base |
|---|---|---|
| contract validity | **1.0** (243) | 0.5514 (243) |
| cause accuracy | **0.9959** (243) | 0.0576 (243) |
| decoy rate, `positional_probe` | **0.0** (19) | 0.0 (19) |
| decoy rate, `misattribution_probe` | **0.0** (19) | 0.0 (19) |
| decoy rate, `wrong_attribution` | **0.0** (19) | 0.0 (19) |
| `length helps` / `length misleads` | **1.0 / 1.0** (45 / 12) | 0.0 / 0.0 (45 / 12) |
| injection echo | **0.0** (19) | 0.0 (19) |
| overconfidence on wrong causes | **not measured** (n=0 on clean slices) | 0.6069 (145) |

Do not read any of it without `docs/model-card.md`'s "How to read the
scoreboard" and "Known limitations". In short, and each argued there:

- The base model's `0.0`s in the right-hand column are **not** decoy
  resistance. It reads `0.0` there because it almost never names a valid
  candidate at all — a model that answers nothing scores perfectly on
  every metric conditioned on having answered.
- `cause accuracy` is a **closed-set selection score**: the released model
  reproduces the reference cause string verbatim on 224 of 224 rows that
  have one. It measures which of nineteen memorised catalog phrases it
  picked, not free-text accuracy.
- Every trainable catalog entry appears in train, val and test, so no
  slice here separates a model that reads the evidence from one that
  recites per-entry answers.
- Two slices — `multi_misattribution_probe` (19/19) and
  `contradiction_probe` (14/19) — share workload identities with the
  training data and are withdrawn from the bar.
- Overconfidence is unmeasured, not passed: the model got two causes wrong
  in 243 rows and both sit in a withdrawn slice.
- These numbers come from a **corrected answer key**. Eight of nineteen
  catalog entries carried keywords absent from their own reference answer,
  which capped two slices at 0.5789 for every model. Commit `70460e9`
  fixes it and negative-controls the fix; the runs were re-scored by
  replaying their recorded outputs, not re-run.

## License

Apache-2.0. Contributions require DCO sign-off (`git commit -s`).

The shipped GGUF (`dist/kubeagent-verdict-0.6b-q8_0.gguf`) merges a LoRA
adapter into the base model, so it is a derivative of that base model too,
not only of this repo's training code. The base is `Qwen/Qwen3-0.6B`
(`train/config.py`'s pinned `base`, downloaded via
`transformers.AutoModelForCausalLM.from_pretrained` in `train.py` and
`export.py`); `docs/design.md`'s design record states it is Apache-2.0.
This repo does not vendor or re-attest that license — consult the base
model's own Hugging Face repository (`Qwen/Qwen3-0.6B`) for its current
terms.
