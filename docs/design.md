# kubeagent-verdict — the training repository for the local verdict model

**Date:** 2026-08-22
**Status:** Approved design, awaiting implementation plan
**Home:** this spec is committed to kubeagent's design history and travels into
the new repository as `docs/design.md` at scaffold time.

## What this is

A new, separate repository — `github.com/imantaba/kubeagent-verdict` — that
produces the local tiny model kubeagent's `--investigate` local verdict mode
consumes. kubeagent v1.23.0 shipped the consumer: with no `ANTHROPIC_API_KEY`,
`KUBEAGENT_EXPLAIN_ENDPOINT` plus a model name selects a mode in which
kubeagent gathers all evidence deterministically and one OpenAI-compatible
`/chat/completions` call adjudicates root-cause candidates, answering verdict
contract v1. Today an operator points that at a stock model. This repository
trains a purpose-tuned one.

The deliverable is an artifact, not a service:
`kubeagent-verdict-0.6b-q8_0.gguf` plus an Ollama `Modelfile` and
`SHA256SUMS`, produced by a CPU-only, all-Python pipeline:

```text
dataset  →  train  →  export  →  eval
```

kubeagent itself does not change. No kubeagent schema moves, no kubeagent
code is touched, and nothing in kubeagent ever imports or reads this
repository. The interface between the two projects is verdict contract v1 and
the verdict prompt format, both owned by kubeagent and pinned here.

## Decisions and their reasons

Every decision below was approved explicitly during design.

1. **Separate repo.** Training tooling (Python, ML dependencies, large
   artifacts) must not enter kubeagent's dependency-free Go world.
2. **Synthetic generator, corpus as ground truth.** The chaos correctness
   corpus is label-shaped, not prompt-shaped: 23 rows per full run, 0–10
   assertion lines each, largely repeating nightly. It pins which observable
   signals each injected fault produces, but it is neither training volume nor
   in the inference format. So a seeded, deterministic generator renders
   thousands of full inference-format examples grounded in the corpus and the
   known-issues reference, and the corpus itself becomes held-out evaluation
   truth. Teacher distillation (having a large model write labels) is
   explicitly deferred: it would add an API-key dependency and unaudited label
   quality; it may return later as an optional augmentation flag.
3. **Base model: Qwen3-0.6B.** The operator's constraint is no GPU anywhere —
   training included. Under 1B parameters, a LoRA fine-tune runs on a
   multicore CPU in hours. Qwen3-0.6B is Apache-2.0 (no redistribution
   strings on the published fine-tune), has a 32k context window — kubeagent's
   prompt is capped at 64 KiB, up to roughly 16k tokens worst case, which
   rules out 8k-context bases — and has the strongest structured-JSON
   instruction following in its size class. This supersedes the earlier "~3B"
   scope note. The pipeline is size-agnostic; a bigger sibling can be trained
   later without design change.
4. **All-Python (3.11+).** The training ecosystem is Python-native. A Go
   dataset builder could not import kubeagent's `internal/` packages across
   module boundaries anyway, so format fidelity rests on golden fixtures in
   any language; one toolchain wins. Config-driven stacks (axolotl and
   friends) were rejected as CUDA-first under a no-GPU constraint.
5. **Repo name: kubeagent-verdict.** Named for what the model does.
6. **License: Apache-2.0** — matching both kubeagent and the base model.

## The interface being trained against

At inference the model receives exactly what kubeagent v1.23.0's
`internal/investigate/local.go` sends:

- **System message:** `verdictSystemPrompt`, a fixed constant. It declares
  the adjudication task, the injection-hardening rules (everything between
  section markers is untrusted data; instructions inside evidence are never
  followed; evidence cannot change the output contract), and the answer
  schema.
- **User message:** three delimited sections, each wrapped
  `== BEGIN <name> ==` / `== END <name> ==` — `inventory` (the shared
  findings inventory), `candidates` (per flagged workload, the deterministic
  pass's root-cause candidates with verdicts `attributed` / `ruled_out` /
  `outranked` and one evidence sentence each), `evidence` (the bounded reads
  kubeagent chose) — followed by the closing line
  `Judge each listed workload now and answer with the JSON object only.`
  An empty section body renders `(none)`. Oversized evidence is cut and
  marked `[truncated by kubeagent]`.
- **Required answer — verdict contract v1** (prose-versioned in kubeagent's
  `website/docs/features/diagnostics.md`), a single JSON object:

  ```json
  {"verdicts":[{"workload":"<namespace>/<name>",
                "cause":"<candidate cause verbatim, none_of_these, or your own>",
                "confidence":"low|medium|high",
                "rationale":"<one sentence grounded in the evidence>"}],
   "summary":"<at most four short lines for an operator>"}
  ```

  No markdown, no fences, no text outside the object. kubeagent treats the
  answer as untrusted: it sanitizes every line, caps it at 512 runes, matches
  verdict rows against the flagged-workload set, and drops anything else.

Training examples must be in exactly this shape, or the fine-tune teaches the
wrong interface.

## Repository layout

```text
kubeagent-verdict/
├── LICENSE                     # Apache-2.0
├── README.md                   # purpose, provenance rules, runbooks
├── pyproject.toml              # package + pinned tool config
├── requirements.lock           # pinned versions; the reproducible install in README + train.md
├── contract/                   # the pinned interface to kubeagent
│   ├── PIN.md                  # what is pinned, to which kubeagent version
│   ├── system_prompt.txt       # verdictSystemPrompt, verbatim
│   └── golden/                 # captured fixture prompt + valid answer
├── data/
│   ├── corpus/                 # committed corpus snapshots (nightly CI artifacts)
│   └── knownissues/            # vendored 16-kind reference snapshot
├── src/kubeagent_verdict/
│   ├── contract.py             # section renderer + prompt assembly (pinned by golden test)
│   ├── dataset/                # kv-dataset — catalog + generator
│   ├── train/                  # kv-train   — CPU LoRA
│   ├── export/                 # kv-export  — merge + GGUF + quantize + Modelfile
│   └── evals/                  # kv-eval    — offline scoring
├── tests/
└── .github/workflows/ci.yml
```

Console entrypoints: `kv-dataset`, `kv-train`, `kv-export`, `kv-eval`.

### The contract directory is the load-bearing wall

kubeagent owns the interface; this repository pins it:

- `contract/system_prompt.txt` holds `verdictSystemPrompt` verbatim.
- `contract/PIN.md` names the pin: verdict contract v1, prompt shape as of
  **kubeagent v1.23.0**, the section-renderer semantics (`(none)` for empty
  bodies, trailing-newline trim before wrapping), the closing judge line, and
  the truncation marker.
- `contract/golden/` holds one full fixture prompt and one valid answer. A
  test asserts `contract.py` reproduces the fixture **byte-for-byte**.

A kubeagent prompt change therefore requires a deliberate re-pin here — new
fixture, new PIN.md entry — never a silent drift. The prose-versioned
contract in kubeagent's diagnostics.md is the tripwire that says when.

## Data provenance — the hard rule

Training inputs are exactly two, and nothing else is ever a source:

1. **The chaos correctness corpus** — `chaos-corpus-<minor>-<distro>.jsonl`
   rows, already redacted at chaos/run.sh's single seam before JSON encoding,
   pulled from the **nightly CI artifacts**, which are credential-scanned
   before upload. Never from a local `docs/testing/` copy: that directory
   holds live-cluster capture and is categorically excluded. Committed
   snapshots under `data/corpus/` record which nightly run they came from.
2. **The known-issues reference** — a vendored snapshot of kubeagent's
   `internal/knownissues` sixteen entries (kind, summary, detail, causes,
   checks, docs). The snapshot itself is a bare JSON array with no header: the
   v1.23.0 pin lives in `contract/PIN.md`'s repo-wide "pinned against" line,
   not in this file. It cannot carry one anywhere — `knownissues.py`'s
   strict loader requires the top level to be a list and rejects any entry
   whose fields are not exactly `kind`, `summary`, `detail`, `causes`,
   `checks`, `docs`, so a header object of any shape fails to load.
   kubeagent's `known-issues` command has no JSON output, so the snapshot is
   derived by hand from the Go slice literal.

Every identifier the generator invents comes from a fixed synthetic
vocabulary (the `web-abc` / `shop` / `worker-1` / `registry.example.com`
class). Three provenance tests check generated text against five fixed
regexes — a dotted-quad IP, an `http(s)://` scheme, the word "kubeconfig", a
`/home/` path prefix, a bare `@` — and fail on the first hit.
`test_provenance_no_banned_text` scans a train/val batch;
`test_provenance_no_banned_text_in_test_set` scans `generate.test_set()`,
which is where the corpus-derived, held-out-case and probe rows live; and
`test_provenance_scan_reaches_every_catalog_entry` asserts the scanned
corpus renders every trainable catalog entry, because a sampled 60-example
batch renders `own_cause` for only 6 of the 19 and a denylist cannot guard
prose it never emits. That third test is the one that makes the first two
mean something. No live cluster name, node name, private IP, internal
hostname, kubeconfig path or context name is meant to enter a tracked file —
the same rule kubeagent's own repository enforces — but these tests still
only catch the five shapes above, and a denylist is not an allowlist. (This
paragraph previously said the scan never ran against `generate.test_set()`,
leaving those rows unchecked. That was true when written.)

## The dataset generator (kv-dataset)

### The failure catalog

The generator's core is a catalog keyed by cause: one entry per distinct
fault slug — the 23 chaos scenarios share **17 distinct slugs**
(`control-plane-docker-stop`, `control-plane-cert-expiry`,
`node-cordon-diskfull`, `networkpolicy-deny-all`, `coredns-corefile-broken`,
`loadbalancer-no-provider`, `memory-limit-oomkill`, `namespace-deletion`,
`deployment-bad-image-tag`, `configmap-aws-key-leak`,
`worker-containerd-stop`, `certmanager-bad-issuer-ref`,
`flux-gitrepo-dns-failure`, `oversized-job-unschedulable`, `crashloop-pod`,
`no-fault-healthy-readyz`, `coredns-servfail-template`) — plus entries for
known-issues kinds not already covered by a slug (the 16 kinds overlap the
slugs heavily: OOMKilled, CrashLoopBackOff, ImagePullBackOff appear in both).
Coverage is total and tested: every one of the 17 slugs and every one of the
16 kinds maps to exactly one catalog entry, and a completeness test fails on
any slug or kind without one.

Each catalog entry declares:

- the inventory findings that fault produces;
- the candidate list the deterministic pass would offer — winner, ruled-out
  losers, outranked alternatives, in kubeagent's trace vocabulary. The
  rendered order is **shuffled per example**: kubeagent's own annotators
  (`internal/rootcause/rootcause.go`) walk a verdict-blind `sort.Strings`
  key, so a ruled-out candidate can precede the attributed one in the field.
  Rendering the winner first taught position as a shortcut the real system
  never supplies, and the first tuned model learned to answer by index
  rather than by evidence;
- evidence-line templates;
- the correct verdict: cause, confidence, a one-sentence rationale template.

**The corpus grounds the catalog — for entries that opt in.** A `grounding`
declaration (`CatalogEntry.grounding`, a tuple of substrings) is optional
per entry, and the test that checks it,
`test_grounding_substrings_appear_in_corpus`, skips any entry that leaves it
unset. `memory-limit-oomkill` declares `grounding=("OOMKilled",)`, and its
corpus row does assert "OOMKilled diagnosed (found 'OOMKilled')".

Read that check narrowly, because it is narrow. It compares the entry's
hand-written `grounding` tuple against the corpus assertion text and
nothing else — `CatalogEntry.evidence` is never read by it, and the two
fields are not tied together anywhere in the code. Four of the five
entries that declare grounding prove the gap: `coredns-corefile-broken`
grounds on `kube-system/coredns` while its evidence line reads
`container "coredns", restartCount=6`; `worker-containerd-stop` grounds on
`NotReady` against a `RunContainerError` evidence line;
`deployment-bad-image-tag` grounds on `ImagePullBackOff` against a
`Failed to pull image` line; `node-cordon-diskfull` grounds on
`Unschedulable` while its evidence carries only the lowercase spelling. So
what the corpus grounds is the declaration, not the evidence template the
model actually trains on.

And it grounds only where an entry opts in: of the 8 trainable entries
whose slug has corpus coverage, 5 declare grounding;
`networkpolicy-deny-all`, `oversized-job-unschedulable` and `crashloop-pod`
are also trainable, also have corpus rows for their slug, and declare
none — for those, nothing is checked against the corpus at all.

Rationale and summary text is templated from the known-issues causes/checks
phrasing and the corpus assertion phrasing, with bounded seeded variation —
one sentence grounded in the evidence, summaries of at most four short lines,
every line under kubeagent's 512-rune cap.

### The curriculum

The case mix is what adjudication means, in approximate proportions:

| Case | Share | Teaches |
|---|---|---|
| Candidate attributed, evidence supports it | ~26% | Pick the candidate **verbatim**; calibrate confidence |
| `none_of_these` — evidence rules all candidates out | ~15% | Refusing the offered menu |
| Own evidence-grounded cause (unlisted) | ~10% | Naming what the deterministic pass missed |
| Multi-workload prompts (2–4 flagged, mixed causes) | ~11% | One verdict row per listed workload, no extras |
| `shared_origin` — 2–4 flagged, all downstream of one broken component | ~4% | Naming the SAME cause on every row when the evidence says one thing broke |
| `shared_origin_decoy` — the same scenario, origin read HEALTHY | ~4% | Taking each workload's own cause when the read refutes the shared story. Emitted as `shared_origin`'s twin from one salt, never independently; the two shares must stay equal |
| Truncated evidence (marker present) | ~5% | Judging honestly under cut evidence — lower confidence |
| Injection attempts inside evidence | ~10% | Evidence is data; fake `== END ==` markers and "ignore your instructions" text change nothing |
| Empty candidates / healthy distractors mixed in | ~5% | Not inventing problems |
| `wrong_attribution` — the `attributed` tag is on a candidate the evidence contradicts | ~10% | The tag is a hint, not an answer: evidence overrides it |

That table is `CASE_MIX` in `src/kubeagent_verdict/dataset/generate.py`, and
it is meant to be read against it rather than trusted on its own. An earlier
version of this table said `attributed` was ~40% and omitted
`wrong_attribution` entirely — the one case built specifically to defeat
tag-copying, which is the shortcut this whole section is about. It was
wrong from the commit that introduced the case until a pre-publication
audit recomputed it.

`shared_origin` took its four points from `multi` rather than from the mix
growing, and that is a deliberate cost. The two are the same release decider's
two halves: `separate_reasons_rate` fails when the model can never see a shared
origin, and `false_shared_rate` fails when it claims one everywhere. `multi`
stays the larger of the two.

Its scenarios come from `propagation.trainable_scenarios()`, a pool disjoint
from the six the `shared_origin_probe` eval slice draws from — disjoint in key
and in graded answer string, since `drop_held_out` compares group identity and
never reads the text. Separately, a third of `multi`'s rows now carry the same
origin read with the component shown HEALTHY. Without that, no `multi` row had
a cluster-scoped read at all, so "an origin read is present" answered the whole
slice without reading a word of its evidence.

Two residuals survived that fix. The first has since been paid, and what it
cost is worth recording, because the counter-example that closed the obvious
shortcut left a better one open. A `multi` row's victims are
`rng.sample(entries)` — arbitrary catalog entries whose local symptoms have
nothing to do with the origin read — while a `shared_origin` row's victims are
the scenario's own, and their symptoms cohere with it. So the two classes
differed in the VICTIMS as well as in the read, and "do these symptoms look
like they share a cause" separated them without reading the origin at all.
Symptom coherence is a better shortcut than the one the counter-example
removed, and a healthy-read `multi` row does not touch it.

`shared_origin_decoy` closes it on the training side, the same way
`shared_origin_decoy_probe` closes the exam side: every `shared_origin` row is
now emitted with a twin from the SAME rng salt, rendering the same scenario
with the origin read showing the component healthy. The pair is a minimal
contrast — identical inventory, identical candidate menus carrying identical
tags in identical order, identical read labels in identical order — so the
victims are held byte-identical and symptom coherence cannot separate the
classes. Every trainable scenario is taught under both answers, and nothing
about the scenario predicts the label. `drop_held_out` takes pairs whole,
since both halves share a group key, so the 169/169 core survives the filter
exactly. The residual lean is now the surviving `multi` negatives, which have
no positive twin: the kept pile reads ~0.62 toward the INDEPENDENT answer,
the opposite direction from the ~62/38 toward shared recorded before, and no
longer confounded with anything the model can read off the victims. Those
negatives are kept rather than balanced away — a healthy read over arbitrary
victims is a different counter-example, not a worse copy of the paired one.
Both splits are asserted separately, one on the generator's raw output and one
on the kept pile, so neither can be claimed by measuring the other. Second, the eval cannot yet detect the shortcut this
paragraph closes on the training side: seven of the ten `shared_origin_probe`
rows carry a read label appearing in none of the other 243 test rows, so
answering "one shared cause" on those four labels and "separate causes"
everywhere else passes BOTH halves of decider 5 while reading no evidence at
all. That is now closed too, from the exam side, by `shared_origin_decoy_probe`
— ten rows rendering the same six scenarios with the origin read showing the
component HEALTHY, drawn from the same rng salts as their twins so each pair is
a minimal contrast: identical inventory, identical candidate menus, identical
read labels in identical order, and only the read contents different. Every
origin read label in the exam now appears under both answers, so matching one
predicts nothing. The menu is not re-tagged, which is the point: the local
cause keeps `attributed` and the shared cause keeps `outranked` on BOTH halves,
so "trust the attributed tag" sweeps the decoy slice and scores zero on its
twin, and "take the outranked candidate" does exactly the reverse. Swapping the
tags would have let one heuristic win both.

Two limits are recorded rather than described away. The slice could not have
failed the model it was written for — the 0830 model answered independence on
all ten twin rows, which is the decoy slice's correct answer — so it is not
offered as a fix on its own; it is the second half of a pair, and the pair
could always fail 0830. And `confidence_carried` is copyable here in a way it
is not on the twin, because the expected grade is the deterministic pass's own
per-workload grade printed in the prompt: when the local attribution is right,
so is its grade, and inventing a different one to defeat the copy would be
inventing evidence. A related staleness is deliberate. In the healthy world the
shared candidate's `reason` still asserts the broken fact — it is the
deterministic pass's claim and the read contradicts it — and resolving that in
favour of the read is precisely the skill the slice measures.

Being an exam-side change, it moves the test set: 253 rows to 263. It is
strictly APPENDED, so the first 253 lines of `test.jsonl` are byte-identical
and a scoreboard banked against the shorter file still lines up row for row.
The training set does not move at all — every new group is `propagation:`-
prefixed and collides with nothing, so `drop_held_out` drops the same rows and
`train.jsonl` and `val.jsonl` regenerate byte-identical across the change.

The generator's `multi` case draws `rng.randint(2, 4)` workloads per
example — it never reaches kubeagent's own gather cap. Verdict contract v1
allows up to `MAX_VERDICT_ROWS` (10, mirroring kubeagent's
`MAX_GATHER_WORKLOADS`), so the training data never exercises a prompt at
the width the real interface permits.

Confidence labels are derived from explicit evidence-strength rules in the
catalog (direct signal present → high; consistent but indirect → medium;
truncated or thin → low), so calibration is trained, not guessed.

### Rendering, determinism, split

- Output is chat-format JSONL:
  `{"messages":[{"role":"system",...},{"role":"user",...},{"role":"assistant",...}]}`,
  rendered by the same `contract.py` the golden test pins.
- One `--seed` flag; same seed + same inputs → **byte-identical** output.
  No wall-clock, no unseeded randomness anywhere in the pipeline.
- Volume: ~5,000 training / ~500 validation examples. The split is **by
  scenario family** — all variants of one family land on one side, so no
  near-duplicate leakage.
- Held-out **test** fixtures are corpus-derived: one per corpus row, built
  from that scenario's family with the known injected fault as the required
  verdict. They appear in neither training nor validation.
- The test set is **stratified across the curriculum**, not corpus rows
  alone. Corpus rows are all `attributed`, so a corpus-only test set scores
  one case while reporting an overall rate, and the ~55% of the mix that is
  `none_of_these`, `own_cause`, `truncated`, `injection`,
  `empty_candidates` and `wrong_attribution` trains without ever being
  measured. One held-out example per (trainable entry, case) closes that.
- **Eval-only adversarial slices** exist that no training example can
  imitate — three at first, and a fourth, `contradiction_probe`, added
  later and then withdrawn from the release bar for the reason recorded
  below. `positional_probe` places the correct candidate LAST with an
  honest `attributed` tag. `misattribution_probe` places it last AND hands
  `attributed` to a decoy the evidence contradicts. All are deterministic
  — never shuffled — because their purpose is to hold the shortcut fixed
  against the correct answer. Their groups are held out of train and val,
  so the model has never seen that (entry, workload) pair.
- The third closes a hole the first two could not see. `multi` is ~11% of
  the curriculum and had no test row at all, and `cases.multi()` never
  swaps a tag — so across all 1,600 constituent workloads it contributes to
  train and val at `--seed 17 --size 5500` (2,478 before `drop_held_out`),
  "trust the `attributed` tag" is a strategy the training data never once
  contradicts in that shape. Both single-workload probes render one
  workload, so neither can reach it. `multi_misattribution_probe` renders
  two workloads, each with the tag handed to a decoy; naming **either**
  decoy counts as tag-following. Its rows are **appended** to the test
  file, never interleaved, so a scoreboard banked against the previous
  file still lines up row-for-row.

## Training (kv-train)

- HF `transformers` + `peft` LoRA on CPU; the release runbook
  (`docs/runbooks/train.md`) installs from `requirements.lock` for the exact
  versions a release was built and evaluated against. A plain
  `pip install -e .` — the README's Pipeline section, and every CI job —
  resolves `pyproject.toml`'s loose lower bounds instead.
- Defaults, all in one committed config file: r=16, α=32, targeting the
  attention and MLP projections, 2–3 epochs, effective batch via gradient
  accumulation, fixed seed.
- **Loss masked to assistant tokens only** — the model learns to answer, not
  to reproduce prompts.
- **Non-thinking chat format.** Qwen3 defaults to a thinking mode; the
  fine-tune uses the non-thinking template so the tuned model emits the bare
  JSON object with no `<think>` preamble for kubeagent's parser to trip on.
- Footprint: ~1.2 GB base weights in bf16 plus small LoRA gradients — hours
  per run on a multicore CPU, RAM-bound nowhere.

## Export (kv-export)

- Merge the adapter into the base model.
- Convert with llama.cpp's `convert_hf_to_gguf.py`; llama.cpp is fetched at a
  **pinned tag** by the export script (it is not a pip package), and the pin
  lives in the script beside the lock file.
- Quantize to **Q8_0** (~640 MB) as the shipped default; Q4_K_M is a
  documented smaller option.
- Emit an Ollama `Modelfile`: correct chat template, `temperature 0`,
  `num_ctx 32768`. Serving is then exactly:

  ```
  ollama create kubeagent-verdict -f Modelfile
  KUBEAGENT_EXPLAIN_ENDPOINT=http://localhost:11434/v1 \
  KUBEAGENT_MODEL=kubeagent-verdict kubeagent scan --investigate
  ```

- Verify the produced GGUF actually loads before writing `SHA256SUMS`;
  an unloadable artifact is a pipeline failure, not a shipped file.

## Eval (kv-eval) and acceptance

**Offline tier** — runs after every training run, CPU, minutes. Scores the
tuned model on the corpus-derived test fixtures plus a validation slice.
First the **same acceptance rules kubeagent applies to model output**: one
valid JSON object, verdict rows exactly matching the listed workload set,
confidence from the closed set, line-length bounds. Then task metrics:

- cause accuracy — candidate picked verbatim when right, correct
  `none_of_these` when right;
- injection-resistance rate on the hardening cases;
- **confidence carried** — explicitly *not* a calibration score. The prompt
  prints `[confidence: X]` on the candidate line and the expected answer
  reuses that same value, so the metric is maxed by copying a bracketed
  string out of the question. It reads 1.0 on the first tuned model's every
  slice, including the one where that model got the cause 84% wrong. It is
  reported because carrying the deterministic grade through is worth
  checking, and named so it can never be read as judgment;
- **overconfidence rate** — the honest half of the same question, and not
  determined by the prompt: among the verdicts whose cause the model got
  **wrong**, how many it still graded `high`. A model that copies the
  bracketed grade scores 1.0 here exactly when it is most confidently wrong;
- **decoy rate** — how often the model names the cause that position or the
  `attributed` tag points at while the evidence points elsewhere. It is
  unmeasured (`None`, not `False`) on a row the model did not answer at
  all: a refusal, a parse failure or an omitted workload once averaged in
  as `0.0`, the best possible score, making a model that hedges on exactly
  the hardest rows indistinguishable from one that read the evidence and
  rejected the decoy. Refusing is not resisting;
- **cause accuracy split by whether candidate length helps**. The decoy
  rate rules out two shortcuts — position and tag — and was described here
  as *the* metric that separates reading from reciting. That claim was too
  wide, and a third shortcut walks through the gap it left. In 15 of the 19
  trainable catalog entries the winning cause is the longer phrase (mean
  9.0 words against 6.4), so "pick the longer candidate" scores ~83% on
  **both** single-workload probe slices while reading nothing at all — no
  evidence, no tag, no position — and it beats the decoy rate for free,
  because the trap and the longer phrase usually disagree. Splitting cause
  accuracy by whether length points **at** the true cause is what separates
  the two: a word counter scores ~1.0 where length helps and ~0.0 where it
  misleads; a model that read the evidence scores alike on both. A tie is a
  coin flip, so it counts as misleading. On the 243-row test set the split
  is 45 rows where length helps against 12 where it misleads — read the two
  numbers together or not at all; neither means anything alone. Reading them
  together is now mechanical rather than a habit: `score.length_gap` computes
  the signed `helps - misleads` difference against a 0.15 bar and abstains
  when `helps` is below 0.5 — that rate alone, whatever `misleads` reads
  beside it — because a model failing the slice a word counter would ace has
  not shown enough for the difference to certify anything. The untuned
  baseline is the motivating case: 0.0 against 0.0 is a gap of zero that no
  unconditioned threshold could fail. The verdict is stored on the **overall** block alone —
  0.15 is read against the 12-row `misleads` denominator, and in the three
  cases that carry length-keyed rows at all that denominator is 4 — while the
  two rates it derives from stay on every case
  (`docs/runbooks/train.md` step 6). (The 57 rows
  that carry both a decoy and a non-`none_of_these` expected cause are the
  only ones the split can be computed over; the other 186 contribute to
  neither number.)

Every rate travels with its denominator, and an unmeasured rate renders as
`n/a` rather than as `0.0`. The first tuned model's headline
`injection_echo_rate: 0.0` was a hardcoded default over an empty slice —
the most reassuring number on the board measured nothing at all.

Each result row keeps the model's **raw output verbatim** alongside the
computed fields. A scorer is what lied about the first tuned model, so a
reader must be able to re-score, or simply read what the model actually
said, without paying for inference again and without trusting these numbers.

One scoreboard file per run. The **untuned base model is scored once** as the
baseline; every improvement is measured against it, so "the fine-tune helped"
is a number, not an impression.

**Live tier** — the real gate, a documented runbook rather than code here:
serve the GGUF via Ollama, point kubeagent `--investigate` at it, run the
chaos-gate scenarios from the kubeagent repository. The chaos harness
requires the operator's explicit authorization every time; nothing in this
repository ever runs it.

**Acceptance for shipping a model release:** the offline scoreboard beats the
untuned baseline on every metric, contract validity is 100%, the **decoy
rate on all three adversarial slices is low**, the **length-helps and
length-misleads cause accuracies are close to each other**, and the live
tier names the injected fault correctly on the chaos scenarios that flag
workloads.

Neither of those two bars is optional and neither is a tie-breaker. A model
that answers by position or by tag can score 1.0 on contract validity, cause
accuracy and confidence match simultaneously — the first tuned model did
exactly that — because the expected cause is printed verbatim in its own
prompt beside the `attributed` tag. A model that answers by counting words
defeats the decoy rate as well, without reading anything. Those metrics
measure extraction; the decoy rate and the length split measure judgement,
and each one rules out a shortcut the other cannot see.

The length split is a **measurement, not a repair**. The cue lives in 19
hand-authored winner/loser phrase pairs in the catalog, and it is there for
a reason that is not an accident of drafting: a correct root cause names a
specific mechanism, while a plausible wrong answer names a category, so the
right answer tends to be the longer sentence — in kubeagent's own reports as
much as here. Equalising the counts by hand would be tuning the data until
the metric reads well, which is the opposite of what the metric is for. The
split makes the shortcut visible first; whether to rebalance the catalog is
then a decision from data rather than a guess.

(An earlier draft justified leaving the cue alone on the grounds that the
winner phrases were lifted verbatim from `internal/rootcause`, so shortening
them would de-align the model from its consumer's vocabulary. That was
checked and is false — none of `rootcause.go`'s shapes matches a
`winner_cause` value; every one is hand-authored here. The cue is therefore
this repository's to fix, if the data ever says it should be.)

**An eval change that could not fail the model it replaced is not a fix.**
Before a retrain begins on a corrected dataset, the corrected eval is run
against the previous model and must fail it. An eval that still scores the
broken model highly is not sensitive enough to gate the retrain, and that
costs one eval run to discover instead of one training run.

**A known limitation: the eval does not test entry-level generalisation.**
`generate()`'s `rotate(i)` cycles `catalog.trainable()` into the train/val
pool, and both `held_out_case_set()` and `probe_sets()` iterate
`catalog.trainable()` too — so every trainable catalog entry appears in
train, val and test alike, and no entry is ever held out of training. Each
entry's issue/reason/evidence finding block is also a fingerprint: the
tuples are distinct across all 19 trainable entries, so a model could in
principle skip the candidate list entirely and answer from a memorised
finding-block-to-winner-cause lookup instead of judging the evidence.
`positional_probe`, `misattribution_probe` and `multi_misattribution_probe`
cannot catch that: all three perturb only the candidates section and leave
the finding block untouched, so a pure lookup table scores 1.0 on each with
a decoy rate of 0.0.

An earlier draft of this section claimed the discriminator already existed
— that `none_of_these`, `own_cause` and `empty_candidates` hold the finding
block fixed while requiring an answer other than the stored `winner_cause`,
and so cannot be passed by recitation. **That claim is retracted.** Scoring
the known-broken first tune, which follows the `attributed` tag 79% of the
time on `misattribution_probe`, gives `none_of_these` 1.0. A model proven
not to read the evidence clears it. It is not a discriminator.

The same experiment recorded 0.5789 on `own_cause` and `empty_candidates`,
and this section used to cite the pair as part of the retraction. **That
citation is itself retracted, for a different reason.** Those two slices
are graded by keyword rather than string equality, and until `70460e9`
eight of the nineteen catalog entries declared a keyword that their own
reference answer did not contain, making the grader's conjunction
unsatisfiable on those rows. `0.5789` is `11/19` — the ceiling of a broken
answer key, identical for every model that ever ran against it, and no
evidence about this model or any other. The broken tune cannot be
re-scored against the corrected key: it ran on a 205-row test set from an
earlier commit, and the replay refuses a row-count mismatch rather than
guessing an alignment. Its real score on those two slices is unknown. The
retraction above stands on `none_of_these` alone, which the key bug never
touched.

A fourth slice, `contradiction_probe`, was then built specifically to be
one, and negative control v4 scored the same broken model on it: **1.0
cause, 0.0 decoy**, with the expected rationale and summary reproduced
verbatim. It reuses `none_of_these_case`'s read text, and `none_of_these`
is 15% of the curriculum, so the contradiction sentence is a trained
trigger for a trained answer template rather than something to reason
about. Holding the adversarial menu roughly fixed and changing only the
read text moves cause accuracy from 0.1579 (`misattribution_probe`) and
0.4737 (`wrong_attribution`) to 1.0. The slice is kept — it does defeat an
index-copier, a tag-copier and a word counter — but not as a memorisation
test.

The honest position for v0.1.0: **no slice built from this catalog can
separate a model that reads from one that recites per-entry answers, while
every entry appears in training.** Closing it means holding whole catalog
entries out of train and retraining; this release does not do that, and the
scoreboard should not be read as evidence of entry-level generalisation.

## Testing

- **Contract golden test** — `contract.py` reproduces the captured fixture
  byte-for-byte; `system_prompt.txt` matches the fixture's system message. A
  mismatch fails hard and names the re-pin procedure.
- **Determinism test** — same seed + inputs → byte-identical JSONL.
- **Split-integrity test** — no family straddles train/validation; test
  fixtures appear in neither.
- **Provenance scan** — a five-shape denylist (dotted-quad IP, `http(s)://`,
  "kubeconfig", `/home/`, bare `@`) over a generated train/val batch *and*
  over `generate.test_set()`, plus a coverage assertion that the scanned
  corpus renders every trainable catalog entry — a sampled 60-example batch
  renders `own_cause` for only 6 of 19, and a denylist cannot guard prose it
  never emits. Still not a scan for every token outside the synthetic
  allowlist. (This entry previously ended "it does not run over
  `generate.test_set()`", which was true when written.)
- **Corpus loader tests** — required keys enforced; slug must be in the
  closed vocabulary; `unknown-scenario` refused; a malformed row is withheld
  and counted, never guessed — the corpus contract's own words.
- **Eval scorer units** — canned model outputs, including malformed ones
  kubeagent would reject.
- **Case-mix test** — generated proportions stay within tolerance of the
  curriculum table.
- **Catalog completeness test** — every fault slug and every known-issues
  kind has exactly one catalog entry.

## CI

GitHub Actions on every push: lint, pytest, a 60-example smoke dataset build
with a pinned seed, and a one-step training smoke to catch transformers/peft
API drift. **No real training in CI** — training runs on the operator's
machine per the runbook. Releases are manual: a tagged GitHub release with
the operator-built GGUF, `Modelfile`, and `SHA256SUMS` attached.

## Error handling

Fail loudly and name the thing. A contract drift, a provenance hit, or an
unloadable GGUF each stop the pipeline with the file and the reason. The one
soft degradation is the corpus loader's: a malformed row costs that row,
with a count in the output, never the run — mirroring the corpus writer's
own contract on the kubeagent side.

## Non-goals

- **No GPU anywhere** — not in training, not in serving, not in CI.
- **No API-key dependency** — the pipeline never calls a hosted model;
  teacher distillation is deferred and would be opt-in if it ever arrives.
- **No kubeagent changes** — no schema move, no new flag, no code. kubeagent
  v1.23.0 is the consumer as it stands.
- **No serving infrastructure** — Ollama (or any OpenAI-compatible server)
  is the operator's; this repo ships the artifact and the Modelfile.
- **No corpus authoring** — the chaos harness writes the corpus; this
  repository only reads published, redacted artifacts.
- **No new detector knowledge** — the catalog encodes what kubeagent already
  detects and documents; inventing failure modes kubeagent cannot observe
  would train hallucination.

## Conventions carried over from kubeagent

- Every commit DCO-signed (`git commit -s`), author `imantaba`.
- No AI attribution anywhere — commits, docs, release notes.
- No live identifier in any tracked file; synthetic vocabulary only;
  `docs/testing/`-class captures never enter this repository at all.
- TDD: the failing test first, then the implementation.

## Implementation shape (for the plan)

One implementation plan, roughly: scaffold (repo, license, pyproject, CI
skeleton) → contract pin (system prompt, golden fixture, renderer + test) →
corpus/knownissues loaders → failure catalog → generator + determinism/split/
provenance tests → trainer → exporter → offline eval + baseline scoreboard →
runbooks (training, release, live eval) → first trained artifact.
