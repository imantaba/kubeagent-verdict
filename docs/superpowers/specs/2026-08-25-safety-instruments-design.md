# Safety instruments for the eval set — design

**Date:** 2026-08-25
**Branch:** `safety-instruments` (off `main` @ `7bc8ac8`)
**Status:** approved, ready for an implementation plan

## Why this slice exists

The shipped v0.1.0 weights were trained at `8bd9d28`, where **33 of 253** test rows
were contaminated — their workload identities also appeared in training data. That
number reproduces `docs/model-card.md:378-379` exactly and concentrates in two
slices: `multi_misattribution_probe` 19/19 and `contradiction_probe` 14/19.

Commit `baf173e` fixed the cause: `drop_held_out` now splits compound group keys on
`+` on **both** sides (`src/kubeagent_verdict/dataset/generate.py:114-134`). Measured
on today's tree, contamination is **0 of 253** across all twelve slices. That zero is
not vacuous — 913 raw rows (827 train + 86 val) still collide before `drop_held_out`
runs, so the filter is doing real work on every build.

**Nothing locks that in.** No test recomputes the intersection, no guard stops an
eval-only case from being added to the training mix, and no test pins a single slice
count. A regression could reintroduce contamination and the suite would stay green —
which is precisely how the original leak shipped.

Separately, the model's weakest measured axis has no counterweight. `v0.1.0` calls
10 of 10 correlated failures "independent" (`shared_origin_probe`, cause accuracy
0.4333). The obvious correction — teach it to see shared origins — has an obvious
failure mode: a model that answers "shared origin" everywhere scores perfectly on
`separate_reasons_rate` and is worse than what it replaced. Nothing currently
measures that direction.

This slice adds no model, no training run, and no weight change. It adds the
instruments that make the fix permanent and the over-correction visible.

## Scope

**In:** four contamination instruments, one new scored axis, one release-bar
amendment, and one baseline measurement against the already-shipped GGUF.

**Out, deliberately:**

- Retraining, or anything that writes `dist/`. The shipped weights are frozen for
  this slice.
- `contradiction_probe`'s structural confound. Its withdrawal has two independent
  causes; `baf173e` fixes only the identity overlap. The other — that its read text
  is verbatim `none_of_these_case`'s, and `none_of_these` is a fixed 15% of every
  curriculum via `CASE_MIX` (`generate.py:45`) — needs held-out catalog *entries*
  and a retrain. Instrument 3 below documents that confound; it does not close it.
- Whether `kv-train` is bit-reproducible. Determining it means running `kv-train`
  twice, which this slice does not do.

## Instrument 1 — the contamination lock

A regression test that recomputes the intersection the way
`docs/runbooks/train.md:160-166` prescribes and asserts **0, per slice**.

The definition must match `drop_held_out`'s own contract: union every train and val
group key **split on `+`**, union every test group key split the same way, intersect.
Reading either side unsplit re-derives the very blind spot `baf173e` fixed —
`tests/test_generate.py:112-114` records that this exact mistake once let the test
assert the buggy rule against itself and pass while 103 train rows leaked.

Two assertions, both required:

1. **Post-filter, per slice:** for each of the twelve test slices, zero of its rows
   share a group-key part with any surviving train or val row. Per slice, not a
   single total — a total hides which slice regressed.
2. **Pre-filter, non-zero:** before `drop_held_out` runs, the collision count is
   greater than zero. Without this the test passes vacuously the moment `generate()`
   stops producing collisions for an unrelated reason, and a vacuous green is the
   failure mode this whole slice exists to prevent. Assert `> 0`, not `== 913` — the
   exact figure is a function of seed and size, and pinning it would make the test
   fail on an innocent curriculum change.

`Example.group` is never serialized — `to_row()` writes only `ex.meta`, which has no
`group` key — so this test operates on in-process `Example` objects, never on
JSONL.

## Instrument 2 — the `ast` guard

A `go/parser`-style structural guard over `src/kubeagent_verdict/dataset/generate.py`,
using the standard library's `ast` module. Two halves, both required — a negative
guard alone passes trivially if the thing it forbids stops existing.

**Negative.** None of the five eval-only case builders may be reachable from the
training-construction path. The five are `positional_probe`, `misattribution_probe`,
`multi_misattribution_probe`, `contradiction_probe`, `shared_origin_probe`. The
guard asserts:

- No such name appears as a case string in `CASE_MIX` (`generate.py:45-47`).
- No `cases.<name>` call for any of the five appears inside the body of `generate()`
  — today the construction loop's calls are at `generate.py:76-100`, and every one
  of them is a non-probe builder.

**Positive.** Every name in `HELD_OUT_CASES` (`generate.py:54-55`) must be built by
`held_out_case_set()`. This is the half that catches a case silently dropping out of
the test set: a name removed from the held-out builder while staying in the tuple
produces a smaller test set and no failure anywhere else.

The guard refuses shapes it cannot read rather than skipping them. If `CASE_MIX`
stops being a tuple of literal pairs, or `generate()`'s calls stop being plain
`cases.<attr>(...)` calls, the guard fails by name — widening it is then a
deliberate edit, not an accident. This mirrors the refusal discipline in
kubeagent's `internal/diagnose/knownissues_test.go`, which exists for the same
reason: a best-effort guard that silently skips an unfamiliar shape is not a guard.

## Instrument 3 — the duplication guard

Contamination has a second shape that group keys cannot see: two rows with different
identities and byte-identical evidence text. That is `contradiction_probe`'s
structural confound, and today it is prose in a docstring.

**Method: declared allowlist over exact hashes.** For every rendered example, extract
the evidence block from `ex.user` — the substring between `== BEGIN evidence ==` and
`== END evidence ==`, the markers `contract.section()` writes (`contract.py:154-157`)
— and take its SHA-256. Build the hash set of all train and val rows. For each
eval-only slice, fail on any row whose evidence hash is in that set **unless** the
`(slice, reason)` pair is in a declared allowlist.

Exact hashing, not similarity. There is no repo precedent for a similarity metric
(zero hits for `difflib`, `SequenceMatcher`, `levenshtein`, `jaccard`, `cosine`,
`embedding`), and a similarity threshold is a number nobody can defend. Exact
matching needs no threshold, is a set lookup, and stays stdlib-only.

The allowlist is the deliverable, not the check. Each entry names why the sharing
exists and what it costs:

| Slice | Why it shares | What it costs |
| --- | --- | --- |
| `positional_probe` | reuses `attributed`'s reads by design; the candidate menu is the only perturbation | none — the perturbation is the whole measurement |
| `misattribution_probe` | same | none — same reason |
| `contradiction_probe` | reuses `none_of_these_case`'s read text, and `none_of_these` is a fixed 15% of every curriculum | **this is why the slice cannot catch an entry-lookup table.** Negative control v4 measured the known-broken first tune at 1.0 cause / 0.0 decoy here |

The third row is the point: it converts `cases.py:282-300`'s prose retraction into a
machine-checked fact. An undeclared new overlap fails the suite, and closing
`contradiction_probe`'s confound will show up as an allowlist entry that can be
deleted.

`shared_origin_probe` and `multi_misattribution_probe` get no entry. If either ever
starts sharing evidence text with training data, that is a defect and the guard
should say so.

## Instrument 4 — pin the denominators

`generate.py:244-245` currently reads:

```python
if (first.ns, first.name) == (second.ns, second.name):
    continue  # a name collision would merge the two answer rows
```

A name collision silently drops a `multi_misattribution_probe` row, and **no test
pins any slice count** — the literals `253` and `== 19` appear nowhere in `tests/`.
`multi_misattribution_probe` could go from 19 rows to 18 with the suite green, which
would quietly turn the release bar set below into "≤1 of 18".

Two changes:

1. **Pin every slice count.** One test asserting the full table, measured on today's
   tree:

   | slice | rows | | slice | rows |
   | --- | --- | --- | --- | --- |
   | `attributed` | 53 | | `none_of_these` | 19 |
   | `contradiction_probe` | 19 | | `own_cause` | 19 |
   | `empty_candidates` | 19 | | `positional_probe` | 19 |
   | `injection` | 19 | | `shared_origin_probe` | 10 |
   | `misattribution_probe` | 19 | | `truncated` | 19 |
   | `multi_misattribution_probe` | 19 | | `wrong_attribution` | 19 |

   Total **253**.

2. **Make the collision loud.** Move the distinctness check into
   `cases.multi_misattribution_probe` as a `raise` — every caller gets it, including
   any future one — and delete the caller's `continue` so the raise propagates.
   Today the two seeded draws never collide (19 entries produce 19 rows), so this is
   a no-op on the current tree and a named failure on any tree where it matters.

Either change alone would catch a lost row; together the failure is legible ("names
collided") rather than mysterious ("18 != 19").

**Two zero-cost hardenings ride along here:**

- Add `"shared_origin_probe"` to the banned set at `tests/test_generate.py:109-110`.
  It is the only eval-only slice missing from that set, for no reason other than
  that it was added after the set was written.
- The distinctness assertion at `tests/test_generate.py:194-201` already checks
  this at test level; once the builder raises, that test asserts the builder's own
  guarantee rather than a property of the output.

## The new axis — `false_shared_rate`

`separate_reasons_rate` (`score.py:188-190`, n=10 on `shared_origin_probe`) measures
the model wrongly claiming independence where a shared origin is true. It has no
mirror, so a model that answers "shared origin" everywhere scores perfectly on it.

`false_shared_rate` is that mirror: the rate at which the model claims a shared
origin on `multi_misattribution_probe` (n=19), the one slice where independence is
the *correct* answer.

**Detection.** Read the model's `summary` field only — the same narrow claim
`separate_reasons_rate` makes, for the same reason: the phrase is a summary artifact,
and the claim is exactly "the model wrote shared-origin language", nothing broader.
Resolve three ways:

| summary contains | verdict |
| --- | --- |
| a shared-claim phrase, no independence phrase | **1.0** — false shared claim |
| an independence phrase, no shared-claim phrase | **0.0** — correct |
| both, or neither | **`None`** — ambiguous, counted separately |

The third row is the honesty gate. A summary reading "these are **not** caused by a
shared origin" contains shared-origin language and is correct; scoring it 1.0 would
manufacture a failure. `None` rather than `False` follows `score.py:63-71`'s
established rule — a case the metric cannot read must never average in as the best
possible score.

**The ambiguous count is reported as its own number**, alongside the rate. The
interim phrase sets are deliberately over-inclusive, so some rows will land there;
seeing how many is how the sets get narrowed later. A metric whose imprecision is
invisible is exactly the kind of instrument this repo keeps having to retract.

**Where the phrases live.** One new meta field, `shared_claim_phrases: list[str]`, on
`multi_misattribution_probe` rows — the error side, travelling with the row exactly
as `wrong_summary_phrase` does (`cases.py:517`), so `score.py` keys off the field's
presence rather than special-casing a slice name. The independence side is a fixed
property of the correct answer, not of a row, so it lives as a module constant in
`score.py` beside `KEYWORD_CASES` and `HIGHEST_CONFIDENCE`. This keeps `score.py`'s
existing boundary intact: it imports from `contract` and `evals.contract_check` and
never from `dataset`, and it should stay that way.

Both sets are matched case-insensitively as substrings, as `wrong_summary_phrase`
already is (`score.py:130-131`).

**Wiring.** `evaluate()` emits two per-row fields:

- `false_shared` — `1.0`, `0.0`, or `None`. `None` on an ambiguous row (both phrase
  kinds present, or neither), and `None` on an unanswered row, following
  `wrong_summary`'s existing treatment at `score.py:127-131`.
- `shared_ambiguous` — `True` only when the row was answered and could not be
  resolved. An unanswered row is `False` here: it is unmeasured, not ambiguous, and
  conflating the two would make a broken model look like a vague phrase set.

`aggregate()` reduces `false_shared` through the existing `_rate()` helper, filtering
`is not None` exactly as `separate_reasons_rate` does at `score.py:188-190` — `_rate()`
returns `{"rate": None, "n": 0}` on empty, so the rate always travels with its
denominator, and the denominator shrinking below 19 is itself the signal that the
phrase sets are too loose. `shared_ambiguous` sums to a plain integer count.

`COLUMNS` (`score.py:206-212`) gains one entry, for `false_shared_rate`. The
ambiguous count is not a column — it is a diagnostic for reading the rate, not a
score — and is reported in the aggregate dict and in `render_markdown`'s prose.

## The release bar

`docs/runbooks/train.md:104-133` names four things that decide a release. None of
them names `separate_reasons_rate`, so a regression on it ships green today. Add a
fifth:

> **Does it distinguish shared origins from coincidence?** Read
> `separate_reasons_rate` and `false_shared_rate` **together, or not at all.**
> Alone, either is trivially gamed: a model that always answers "independent"
> scores 0 on `false_shared_rate`, and a model that always answers "shared origin"
> scores 0 on `separate_reasons_rate`. **`false_shared_rate` must be ≤ 1 of 19.**
> Check the ambiguous count beside it — a large one means the phrase sets need
> narrowing, not that the model changed.

This follows the shape of the existing "length helps / length misleads" bullet,
which already establishes the read-these-together discipline for a metric pair.

## The baseline measurement

Run `kv-eval` against the shipped v0.1.0 GGUF on `llama-server` at temperature 0 and
commit the measured numbers, so the ≤1/19 bar is a measurement rather than a guess.

The expected shape, stated in advance so the run can contradict it: v0.1.0 emits
separate-reasons language on this slice, so `false_shared_rate` should be at or near
0/19 — while `separate_reasons_rate` is 1.0, because the same habit that makes it
safe here makes it wrong on all ten `shared_origin_probe` rows. A baseline that reads
"0.0 and 1.0" is not a contradiction; it is the pair demonstrating on the first run
why neither number means anything alone.

If the measured `false_shared_rate` exceeds 1/19, the bar is wrong and gets revised
against the measurement — with the revision written down. A bar quietly relaxed to
fit the number it was meant to constrain is not a bar.

## Testing

Ordinary failing-first TDD does not apply to instruments 1 through 4, and pretending
otherwise would be the exact self-deception this slice exists to prevent. They are
guards over a tree that is already correct: contamination is already 0, the eval-only
builders are already absent from the training mix, and the slice counts are already
what they should be. Written against today's tree, every one of them passes on the
first run. **A guard that has only ever been observed passing is not known to be a
guard.**

So each of the four carries a **demonstrated failure**, recorded in its commit
message: perturb the thing it guards, observe the named failure, revert the
perturbation, confirm green. Concretely —

| Instrument | Perturbation | Expected failure |
| --- | --- | --- |
| 1, contamination lock | revert `drop_held_out` to the unsplit comparison | non-zero in `multi_misattribution_probe` and `contradiction_probe` |
| 1, non-vacuity half | stub the pre-filter collision count to 0 | the `> 0` assertion |
| 2, negative | add `("positional_probe", 5)` to `CASE_MIX` | the eval-only-name assertion |
| 2, positive | drop a name from `held_out_case_set()` | the `HELD_OUT_CASES` coverage assertion |
| 2, refusal | rewrite `CASE_MIX` as a computed value | refused by name, not silently skipped |
| 3 | give `multi_misattribution_probe` a read verbatim from `attributed` | undeclared-overlap failure |
| 4, counts | drop one `with_losers` entry | `18 != 19` on the pinned table |
| 4, raise | force both draws to the same name | the builder's `ValueError`, not a silent skip |

The perturbations are throwaway and never committed; only the observation is.

`false_shared_rate` is the one piece that *is* ordinary TDD — it does not exist yet,
so its tests fail first for the ordinary reason. It gets unit coverage for all three
resolutions (shared-only, independence-only, both-present), a fourth for neither-present,
and a fifth asserting `None` on an unanswered row, all driven by synthetic `summary`
strings and mirroring the existing `wrong_summary` tests.

Standing rule for the whole slice: **an eval change that could not fail the model it
replaced is not a fix.** The table above is how that rule is discharged here.

## Sequencing

1. Instrument 4 (pins and hardenings) — smallest, and it fixes the denominator every
   later number depends on.
2. Instrument 1 (contamination lock).
3. Instrument 2 (`ast` guard).
4. Instrument 3 (duplication guard and allowlist).
5. `false_shared_rate` — meta field, scoring, columns, tests.
6. The `train.md` release bar.
7. The v0.1.0 baseline run, as its own commit, so the instruments are reviewed
   separately from the measurement they enable.

## Constraints

- Branch `safety-instruments` off `main`; never commit to `main` directly.
- Every commit `git commit -s` (DCO), identity `imantaba <itn.taba@gmail.com>`. No
  AI attribution of any kind, anywhere.
- Python is `.venv/bin/python` (3.12). The system `python3` is 3.14 and must not be
  used. The eval CLI is the console script `.venv/bin/kv-eval`; `python -m
  kubeagent_verdict.evals.cli` is a silent no-op.
- Stdlib only. `pyproject.toml` declares `dependencies = []` and this slice adds
  none — `ast` and `hashlib` are both standard library.
- `ruff` line length 100, target py311.
- Never run `kv-train`, `kv-export`, or anything that writes `dist/`.
- No live identifiers, secrets, private IPs, or internal hostnames in any tracked
  file.
