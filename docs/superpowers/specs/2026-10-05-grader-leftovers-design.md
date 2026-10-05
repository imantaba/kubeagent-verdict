# Grader leftovers (Spec 4b-4) — design

**Date:** 2026-10-05
**Branch:** `spec4b4-grader-leftovers` (cut off `main` @ `38345e1`)
**Status:** approved in chat 2026-10-05; written for review

## What this is

Spec 4b is four specs. 4b-1 (the shared-origin family), 4b-2 (catalog
gold) and 4b-3 (`multi` rows and decoys) are merged. This is 4b-4:
**the grader leftovers.**

PIN.md's "Left for 4b-4" list has about 15 items. Six of them change only
the grader. The rest change exam rows: their prompts, their gold or their
keys. Any exam change moves all three hash pins, and the exam rebuild after
4b-4 moves them anyway. So 4b-4 takes **only the six grader items**, and
the rest move to the exam rebuild's list (see "Left for the exam rebuild").

The six:

1. **The decoy gate covers job 1.** `named_decoy` tests decided workloads
   too.
2. **The decoy compare is cleaned.** `named_decoy` cleans both sides with
   `_norm_cause` before it compares.
3. **G3b never cuts past a label** (model-card limit 13).
4. **Must-not words can see "not", and short ones start at a word**
   (model-card limit 14).
5. **The cleaning step folds hyphens and underscores.**
6. **Kit keys of 3 letters start at a word.** This is the grader's answer
   to "the guard for 4+-letter kit keys".

No prompt, gold answer, key, decoy list or system message changes. The
checker does not change. The bars do not move: `JOB1_BAR` 0.9, `JOB2_BAR`
0.7, `JOB3_BAR` 0.9.

## Why

Measured on `out/dataset-1005` and the exam the tests read
(`_corpus_rows()`: 249 rows, 197 job-2 workloads). Every "probe answer"
below is the gold reply with one change, scored by `score.evaluate`.

### 1. The decoy gate skips job 1

Spec 4a made `named_decoy` test job-2 workloads only. Its reason: a
decided workload's right answer could be the same text as its decoy.
4b-3 made that false. No case lists a workload's own gold as its decoy, and
`tests/test_multi_decoys.py` pins it. The skip has no reason left.

With the skip, `decoy_rate` measures 121 exam rows. Without it, 174: 53
rows gain a decoy score. The gold reply names a decoy on 0 of 121 rows
today and 0 of 174 after.

### 2. The decoy compare is raw

`named_decoy` asks whether the raw answer is exactly one of the decoys
(`score.py:813`). G2 and the keyword rule both clean first. So a decoy
copied with a capital letter or a trailing period does not count as naming
it. A probe that answers every workload with its first decoy in capitals
plus a period: `decoy_rate` 0.0 today (with the gate widened, so the
change is this item alone), 1.0 after.

### 3. G3b cuts a label off a line (limit 13)

Some own lines read `log cause: bad command or entrypoint`. G3b cuts 1 or 2
words off the front of each own line, so it can cut `log cause:` and leave
the label's words, `bad command or entrypoint`. A right answer that uses
those words in a row holds the cut line and scores 0.

On the exam, 50 job-2 workloads have a `log cause:` line in their prompt.
The probe answer is the gold cause plus " because of a <the prompt's first
log-cause label>". Job 2 scores it 167 of 197 today: 30 right answers are
zeroed. After: 197 of 197.

### 4. A must-not word is a substring and cannot see "not" (limit 14)

Must-not words are matched anywhere in the cleaned answer. So `tag` hits
`stage`, and a right answer that names a must-not word to rule it out
scores 0. The probe answer is the gold cause plus ", not an init
container" (for keys with that must-not) or "; the node is not cordoned"
(for `cordon`). Job 2 scores it 146 of 197 today: 51 right answers are
zeroed. After: 197 of 197.

The exam's must-not words: `init container`, `init-container`,
`initcontainer` (42 workloads each), `cordon` and `pressure` (9 each),
`tag` (6), `provision` (6).

Whole-word matching was considered and turned down. `cordon` must still
hit "cordoned" and `provision` must still hit "provisioned": those are the
wrong answers the words exist to catch.

Start-of-word matching for every must-not word was approved in chat, then
turned down while planning. It lets 0920's wrong answer on exam row 197,
"the pod's node has a MemoryPressure condition", pass: `pressure` sits
inside "memorypressure", not at its start. `tests/test_answer_keys.py`
pins that answer at 0.

So a must-not word follows the same length rule as a key (§6): 3 letters
or fewer must start at a word, longer is a substring as today. On the
exam that changes only `tag`. Every number in this spec was measured with
this rule.

### 5. The cleaning step leaves hyphens and underscores

NFKC keeps a non-ASCII hyphen (U+2010 to U+2015) as it is, and `_` is not a
space. So "init‐container" (U+2010) and `init_container` slip past all
three init-container spellings. The cleaning step has a twin in `gold.py`.
No test keeps the two equal today; 4b-4 adds one. Measured with both changed: 0 of 8,000 pool
rows and 0 of 249 exam rows change by a byte.

### 6. Three kit keys are 3 letters

4b-2 loosened the key rule in `stories.py` from 4+ letters to 3+. Three
catalog keys are 3 letters: `tag` (init-errimagepull), `pod`
(volume-mount-error) and `key` (create-container-config-error). As
substrings they hit inside longer words: `tag` in "stage". Rows that carry
one: 413 train (131 + 137 + 145), 38 val (21 + 7 + 10) and 18 exam (6
each).

The probe answer replaces the gold cause with its keys, swapping `tag` for
`stage`. Today job 2 scores it 197 of 197: 6 wrong answers pass. After, 191
of 197: those 6 fail.

Re-keying those three entries would also close it, but it changes keys on
18 exam rows, which moves the pins. So this is the grader's fix, and the
4+-letter guard is not restored. A key of 3 letters or fewer must start at
a word boundary. It may run on: `tag` still hits "tags", `pod` still hits
"pods". Longer keys stay substrings, so `pull` still hits "pulling".

## What stays the same

- Every exam, train and val byte. The three hash pins and every dataset
  test.
- The checker and its 51 rules.
- The gold reply scores 1.0 on job 1, job 2 and job 3.
- The hedge bot scores job 2 0.4162 of 197. The three cut-paste bots score
  job 2 0.0 of 197. (Measured with rules 3 to 6 in place.)
- The 24-character negation window and the `NEGATORS` list. They are
  reused as they are.

## Design

All of it is in `src/kubeagent_verdict/evals/score.py`, plus the cleaning
twin in `src/kubeagent_verdict/dataset/gold.py`.

### 1 and 2. The decoy loop

In the `named_decoy` loop:

- Remove the test that skips a workload whose `job` is not 2.
- Compare `_norm_cause(answer)` with the set of `_norm_cause(decoy)`, exact
  match. It stays exact, not a substring test: G2 is the substring test,
  and it zeroes the score. `named_decoy` is a diagnostic and asks "did it
  name the decoy", nothing more.

Update the comments at `score.py:216` and `score.py:795-807`, which say job
1 is skipped and left for 4b-4.

### 3. G3b

In `_g3b`, a cut of N words is skipped when any of the first N words ends
in `:`. The whole line is still matched. So `log cause: bad command or
entrypoint` can be matched whole, or with `log` cut, but never with `log
cause:` cut.

Measured: the three cut-paste bots still score 0 of 197.

### 4 and 6. One matcher for keys and must-not words

A new constant, `SHORT_WORD_MAX = 3`, and a new helper,
`_word_hits(text, word, *, negatable)`:
- A word of `SHORT_WORD_MAX` letters or fewer is found only where it starts
  a word: no letter, digit or `_` just before it (`(?<!\w)` + the escaped
  word, nothing at the end). A longer word is found anywhere, as today.
- When `negatable` is true, a hit with a `NEGATORS` word or an "n't" in the
  24 characters before it does not count, the same as
  `_word_bounded_signal`.
- It returns whether any hit counts.

`_keywords_match` then reads:
- A key: `_word_hits(c, key, negatable=False)`. A key is never negatable:
  "not a tag" holding the key is not the grader's concern, and G3b and
  must-not words cover wrong answers.
- A must-not word: `_word_hits(c, word, negatable=True)`.

`job2` and `cause_acc` both call `_keywords_match`, so both get the rule.
The docstrings of `_keywords_match` and `job2` say how it works now.

`_word_bounded_signal` is not changed. It keeps its `\b` at both ends,
which job 3 needs ("verified" must not hit "unverified").

### 5. Cleaning

`_norm_cause` in both `score.py` and `gold.py` first maps U+2010 to U+2015
to `-` and `_` to a space, then does what it does today. The order: NFKC,
the map, lowercase, strip, trailing periods, squeeze spaces. NFKC goes
first because it can produce some of these characters.

## Tests

TDD: each test is written first and seen to fail.

New tests, in `tests/test_score.py` unless named:

- **Decoy gate, job 1.** A one-row case whose job-1 workload names its
  decoy: `named_decoy` True, `decoy_rate` {1.0, 1}. Today it is None.
- **Decoy compare.** The decoy copied as "Registry Down." counts.
- **G3b label.** An own line `log cause: bad command or entrypoint`; the
  answer "the container exits because of a bad command or entrypoint" is
  not guarded. A paste of `cause: bad command or entrypoint` still is.
- **Must-not "not".** The answer "the main container, not an init
  container, is killed at its memory limit" passes. "killed in the init
  container" still fails. "the node is cordoned" still fails on `cordon`.
- **Must-not start.** `tag` does not hit "stage" or "outage". `pressure`
  still hits "MemoryPressure"; "no MemoryPressure" does not count.
- **Short key start.** `tag` does not pass "stage"; it passes "tags".
- **Cleaning.** `init_container` and "init‐container" (U+2010) fold to
  the plain spelling, in both twins. A new twin test gives both the
  same strings and expects the same answers.
- **Exam probes.** The three probe answers above, on `_corpus_rows()`,
  pinned at their after-numbers: label 197 of 197, "not" 197 of 197,
  "stage" 191 of 197. A fourth probe pins the capital-decoy bot's
  `decoy_rate` at {1.0, 174}.

Tests that change:

- The two tests near `tests/test_score.py:1475` and `:1500` pin "job 2
  only" for `decoy_rate`. They are rewritten to pin job 1 counting, with a
  dated "2026-10-05 (Spec 4b-4)" note saying what they were.
- Any test that pins a `decoy_rate` count or a `named_decoy` value that
  moves is re-pinned by hand with a dated comment and the reason. Same for
  `cause_accuracy` and any other grader number. No `-update`.

Tests that must not change: every dataset, hash, checker and bar test, the
gold-reply tests, the hedge bot test (0.4162 of 197) and the cut-paste bot
test (0.0 of 197).

## Docs

- `docs/model-card.md`:
  - limit 13: a dated note that it is closed, with the 167 → 197 number;
  - limit 14: a dated note that the "not" and `stage` cases are closed,
    with the 146 → 197 number. Still open: a "no" more than 24 characters
    back, as in "no node is cordoned or under memory pressure";
  - the "decoy rate counts job-2 workloads only" bullet (line 901): a
    dated note that job 1 counts again, and why it is safe now.
- `contract/PIN.md`: a new entry "2026-10-05 — Spec 4b-4". It says no pin
  moved, lists the six changes with their numbers and any hand re-pins, and
  ends with the "Left for the exam rebuild" list below. The 4b-1 entry's
  left-for list gets a dated pointer to it.
- `docs/design.md`: only where it describes a rule that changes.

## Left for the exam rebuild

These were on 4b-4's list and change exam rows, so they move with the
rebuild and its one re-pin:

- IS-22's sum half: the reasons in "0/N nodes are available: ..." add up to
  N. It fails on 4b-1 stories, exam rows included (PIN.md, 4b-3 entry).
- node-disk-pressure's ContainerStartError keys: ("containerd", "task") to
  ("space", "containerd").
- The weak pairs: 3 left (PIN.md, 4b-2 entry).
- The G2 registry skip: the bad-image-tag key has no must-not word for a
  registry fault.
- Must-not words for the shared-origin family.
- B6: a refused read's short "is forbidden" text.
- The tighter checker checks (service-line wording and sort order, the
  network-policy gate, a message-only NotReady line over 120 runes, lease
  ages 0s to 39s, an extra system line at 10 rows, ANS-2 counting
  ruled-out lines). They move no row, but they belong with the build.
- B4's fourth arm, the shared-cause cap. It needs a new Go capture.
- image-pull-secret-expired graded as unverified.

## Run order

1. This spec.
2. The plan.
3. The build, task by task, with TDD.
4. The docs.
5. The final review.
6. Merge, if you choose.

## Done when

| Check | Target |
|---|---|
| Exam, train and val bytes | 0 changed |
| Hash pins and checker | unchanged, 0 violations |
| Gold reply | job 1, job 2 and job 3 all 1.0 |
| Hedge bot, job 2 | 0.4162 of 197 |
| Cut-paste bots, job 2 | 0.0 of 197 each |
| Label probe, job 2 | 197 of 197 (was 167) |
| "not" probe, job 2 | 197 of 197 (was 146) |
| "stage" probe, job 2 | 191 of 197 (was 197) |
| Capital-decoy bot, `decoy_rate` | {1.0, 174} (was {0.0, 121}) |
| Gold reply, `decoy_rate` | {0.0, 174} |
| Bars | unchanged |
| Full suite and ruff | green, no `-update` |

## Out of scope

- Any prompt, gold, key, decoy list or checker change. That is the exam
  rebuild.
- A 0920 replay or live run. 0920 has not run on the exam 4b-1 rebuilt;
  its live run comes after the rebuild.
- Training, and anything under `dist/`.
- Moving a bar.
