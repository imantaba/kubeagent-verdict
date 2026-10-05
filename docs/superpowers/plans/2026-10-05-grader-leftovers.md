# Grader Leftovers (Spec 4b-4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make six grader-only fixes in `score.py` (and the cleaning twin in `gold.py`) without moving one exam byte, hash pin or bar.

**Architecture:** Four code changes, one per task, each with its own failing tests first: the cleaning step folds odd hyphens and `_`; G3b never cuts past a word ending in `:`; one matcher, `_word_hits`, finds keys and must-not words (short words start a word, must-not words can see "not"); the decoy gate tests job 1 and compares cleaned text. A fifth task writes the docs.

**Tech Stack:** Python 3, pytest, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-05-grader-leftovers-design.md`

## Global Constraints

- Repo: `/home/ubuntu/git/kubeagent-verdict`, branch `spec4b4-grader-leftovers`. Never work on `main`.
- Every shell call starts with `cd /home/ubuntu/git/kubeagent-verdict &&` (the cwd resets each call).
- Test command (PYTEST): `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` — add a test path or `-k` to narrow it. Full suite needs a 600000 ms timeout. Baseline: 1,940 passed, 10 skipped.
- Ruff: `cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 .` must print `All checks passed!`.
- Commit only with `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "<msg>"`. Stage files by name. Never `git add -A` or `git add .`. Never commit `.gitignore` or `train-v2.log`. Never run `git config`. Never push.
- No AI attribution anywhere: no `Co-Authored-By` trailer, no "Generated with" line, in commits, code or docs.
- No exam, train or val byte changes. `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and `GRADED_VIEW_SHA256` do not move. No file under `data/`, `out/`, `contract/` (except `contract/PIN.md` in Task 5) or `dist/` changes.
- The bars never move: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9, FLOOR, BALANCE 0.10, CEILING 0.30, LABEL_CUE, 0.40/5, 0.12/0.30.
- Never run any test with `-update` or `--update`. A number that moves is re-pinned by hand with a dated comment: `2026-10-05 (Spec 4b-4): <why>; was <old>`.
- TDD: write the test, run it, see it fail for the stated reason, then write the code.
- `NEGATION_WINDOW` (24) and `NEGATORS` are reused as they are. `_word_bounded_signal` does not change.
- `SHORT_WORD_MAX = 3`.
- Never name the training host in a tracked file.
- Docs are in simple voice: short sentences, plain words, numbers explained ("30 of 197").

## Review Focus

These inputs are implied by the spec but no headline test covers them. Each one gets a test in the task that owns the code.

1. **A negator more than 24 characters back.** "no node is cordoned or under memory pressure" must still count `pressure` as a must-not hit. It is the limit the spec leaves open, so it is pinned as open (Task 3).
2. **A word that holds "not" but is not a negator.** "another init container …" must still count `init container`. `NEGATORS` uses `\b`, so "another" is not "not" (Task 3).
3. **A short key at the very start, after punctuation, or after `_`.** "tag: v2 …", "(tag) …" and "image_tag …" must all hit `tag`. `(?<!\w)` treats the text start and punctuation as a word start, and the fold turns `_` into a space (Task 3).
4. **A must-not word with a `-`, written with an odd hyphen.** `init-container` must hit "init‐container" (U+2010). That needs the fold (Task 1) and `re.escape` (Task 3) together (Task 3).
5. **A label that is not one of the first two words.** A line whose `:` is on word 4 still gets its 1- and 2-word cuts. Only a cut that removes a word ending in `:` is skipped (Task 2).

---

### Task 1: The cleaning step folds odd hyphens and `_`

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py:600-605` (`_norm_cause`)
- Modify: `src/kubeagent_verdict/dataset/gold.py:118-123` (`_norm_cause`, the twin)
- Test: `tests/test_score.py` (imports at lines 8-10; the "one cleaning step" section at line 596; `test_job2_guards_a_none_of_these_workload_too` at line 565)

**Interfaces:**
- Consumes: nothing new.
- Produces: `score._norm_cause(s) -> str` and `gold._norm_cause(s) -> str`, same signature, now folding U+2010..U+2015 to `-` and `_` to a space after NFKC. A module-level `_FOLD` table in each file. Tasks 3 and 4 rely on this fold.

- [ ] **Step 1: Add the import**

In `tests/test_score.py`, change line 9:

```python
from kubeagent_verdict.dataset import cases, catalog, generate
```

to:

```python
from kubeagent_verdict.dataset import cases, catalog, generate
from kubeagent_verdict.dataset import gold as dataset_gold
```

(The alias keeps clear of the many local variables named `gold` in this file.)

- [ ] **Step 2: Write the failing tests**

In `tests/test_score.py`, right after `test_norm_cause_folds_full_width_letters_first` (ends near line 603), add:

```python
@pytest.mark.parametrize("twin", [score, dataset_gold], ids=["score", "gold"])
def test_norm_cause_folds_unicode_hyphens_and_underscores(twin):
    """2026-10-05 (Spec 4b-4). NFKC keeps U+2010 to U+2015 as they are, and
    `_` is not a space. So "init‐container" and `init_container` used to
    slip past all three init-container must-not spellings. The cleaning
    step now folds those dashes to `-` and `_` to a space, after NFKC,
    because NFKC can make some of them (a full-width `＿` becomes `_`)."""
    for dash in map(chr, range(0x2010, 0x2016)):
        assert twin._norm_cause(f"Init{dash}Container") == "init-container", hex(ord(dash))
    assert twin._norm_cause("init_container") == "init container"
    assert twin._norm_cause("ＩＮＩＴ＿ＣＯＮＴＡＩＮＥＲ") == "init container"


def test_the_two_cleaning_steps_agree():
    """`gold._norm_cause` is a copy of `score._norm_cause`, so the dataset
    package never imports the grader. Nothing kept the two equal before
    2026-10-05 (Spec 4b-4). This test does: same input, same output."""
    samples = ["Init‑Container", "  Node Worker-2 under MEMORY pressure. ",
               "none_of_these", "ＩＮＩＴ＿ＣＯＮＴＡＩＮＥＲ", "a—b", "", "x.",
               "tab\there", "ＭＥＭＯＲＹ　Ｌｉｍｉｔ．"]
    for s in samples:
        assert score._norm_cause(s) == dataset_gold._norm_cause(s), repr(s)
```

- [ ] **Step 3: Run them and see the fold test fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k "folds_unicode_hyphens or two_cleaning_steps"`

Expected: 2 failed (`[score]` and `[gold]`: `'init‐container' == 'init-container'`), 1 passed. The agreement test passes today, because the twins are equal today. It is a pin, so it passes before and after.

- [ ] **Step 4: Change both cleaning steps**

In `src/kubeagent_verdict/evals/score.py`, replace the whole `_norm_cause` function (line 600) with:

```python
# U+2010 to U+2015 (hyphen, non-breaking hyphen, figure dash, en dash, em
# dash, horizontal bar) fold to "-", and "_" to a space (2026-10-05, Spec 4b-4).
_FOLD = str.maketrans({**{chr(c): "-" for c in range(0x2010, 0x2016)}, "_": " "})


def _norm_cause(s: str) -> str:
    """One cleaning step for every cause the grader reads: NFKC first, so a
    full-width letter, space or period folds to its plain form, then odd
    hyphens to "-" and "_" to a space (`_FOLD`), then lowercase, strip,
    trailing periods off, and runs of whitespace squeezed to one space."""
    folded = unicodedata.normalize("NFKC", str(s)).translate(_FOLD)
    return " ".join(folded.lower().strip().rstrip(".").split())
```

In `src/kubeagent_verdict/dataset/gold.py`, replace its `_norm_cause` (line 118) with the same block, word for word: the comment, `_FOLD`, and the function.

- [ ] **Step 5: Run the new tests and see them pass**

Run the Step 3 command. Expected: 3 passed.

- [ ] **Step 6: Run the cleaning and guard tests and see the one known failure**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py`

Expected: exactly 1 failure, `test_job2_guards_a_none_of_these_workload_too`. Why: `own_lines={score.NONE_OF_THESE}` is the raw `none_of_these`, but own lines are always cleaned text, and cleaned `none_of_these` is now `none of these`. And the decoy `none_of_these` cleans to 3 words now, so G2 no longer skips it.

- [ ] **Step 7: Re-pin that test by hand**

Replace the body of `test_job2_guards_a_none_of_these_workload_too` (line 565) with:

```python
def test_job2_guards_a_none_of_these_workload_too():
    """The guard runs before the exact `none_of_these` match as well. The
    own line here is made up: it is the one way to show that order, since
    any other guarded reply would miss the exact match anyway.

    2026-09-29 (Spec 4a): this test used a made-up decoy, `none_of_these`.
    That decoy is 1 word, and G2 now skips a decoy under 3 words, so the
    reply passes it. G3b matches a whole own line of any length, so a
    made-up own line shows the order instead.

    2026-10-05 (Spec 4b-4): the cleaning step folds `_` to a space. Own
    lines are cleaned text, so the made-up own line is the cleaned form
    now. And the made-up decoy cleans to `none of these`, 3 words, so G2
    tests it again and zeroes the reply. No exam decoy has a `_`: the gold
    reply and every bot pin are unchanged."""
    wm = {"job": 2, "decided": False, "expected_cause": score.NONE_OF_THESE}
    reply = {"cause": score.NONE_OF_THESE, "confidence": "medium", "rationale": "r"}
    assert score.job2(wm, reply, []) == 1.0
    # 2026-10-05 (Spec 4b-4): own lines are cleaned text; was {score.NONE_OF_THESE}
    assert score.job2(wm, reply, [],
                      own_lines={score._norm_cause(score.NONE_OF_THESE)}) == 0.0
    # 2026-10-05 (Spec 4b-4): the decoy cleans to 3 words, so G2 tests it; was 1.0
    assert score.job2(wm, reply, [], decoys=[score.NONE_OF_THESE]) == 0.0
```

- [ ] **Step 8: Run the full suite and ruff**

Run PYTEST (full, 600000 ms) and ruff.
Expected: 1,943 passed, 10 skipped, 0 failed. Ruff: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/evals/score.py src/kubeagent_verdict/dataset/gold.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "fix(score): the cleaning step folds odd hyphens and underscores (Spec 4b-4)"
```

---

### Task 2: G3b never cuts past a label

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py:345-360` (`_g3b`)
- Test: `tests/test_score.py` (`test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut` at line 504; a new section at the end of the file)

**Interfaces:**
- Consumes: Task 1's `_norm_cause`.
- Produces, used by Tasks 3 and 4 (all in `tests/test_score.py`, module level):
  - `_LOG_CAUSE = re.compile(r"log cause: (.+)$", re.M)`
  - `_gold_bot_with(rows: list[dict], change) -> chat_fn`: answers each row with its gold reply after calling `change(row, verdict)` on each verdict dict, in place.
  - `_count_changed(rows: list[dict], change) -> int`: how many gold verdicts `change` alters.
  - A section header `# --------------------------------------------------- exam probes (Spec 4b-4)` at the end of the file. Tasks 3 and 4 add their probes under it.

- [ ] **Step 1: Write the failing unit test**

In `tests/test_score.py`, right after `test_job2_guard_g3b_crops_no_line_below_3_words` (ends near line 527), add:

```python
def test_job2_guard_g3b_never_cuts_past_a_label():
    """Model-card limit 13, closed 2026-10-05 (Spec 4b-4). Cut `log cause:`
    off `log cause: bad command or entrypoint` and what is left is the
    label's words. A right answer that uses them in a row held that cut
    line and scored 0. Now a cut that would remove a word ending in `:` is
    not made. The whole line, or the line with only `log` cut, still
    counts."""
    own = _normalized(["    log cause: bad command or entrypoint"])
    assert not score._job2_guarded(
        "the container exits because of a bad command or entrypoint", (), own)
    assert score._job2_guarded("cause: bad command or entrypoint", (), own)
    assert score._job2_guarded("log cause: bad command or entrypoint", (), own)

    # A `:` further in does not stop the cuts before it. Here it is on word
    # 4, so the 1- and 2-word cuts are both made.
    own = _normalized(["    considered node worker-1 (NotReady): attributed — pod api"])
    assert score._job2_guarded("see node worker-1 (notready): attributed — pod api", (), own)
    assert score._job2_guarded("see worker-1 (notready): attributed — pod api", (), own)
```

- [ ] **Step 2: Run it and see it fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k never_cuts_past_a_label`

Expected: FAIL on the first assert (the right answer is guarded today).

- [ ] **Step 3: Add the label rule to `_g3b`**

In `src/kubeagent_verdict/evals/score.py`, replace `_g3b` with:

```python
def _g3b(c: str, own_lines: Iterable[str]) -> bool:
    """Whether the cleaned cause `c` holds one of `own_lines`, whole or with
    its first 1 or 2 words cut. A cut is made only when at least 3 words are
    left, so a 3-word line is matched whole only. A cut is never made past
    a word that ends in `:`, a label (2026-10-05, Spec 4b-4): cutting
    `log cause:` off a line leaves the label's words, and a right answer
    may use them."""
    for line in own_lines:
        if not line:
            continue
        if line in c:
            return True
        words = line.split()
        for cut in (1, 2):
            if len(words) - cut < 3:
                break
            if any(w.endswith(":") for w in words[:cut]):
                break
            if " ".join(words[cut:]) in c:
                return True
    return False
```

- [ ] **Step 4: Run it and see it pass**

Run the Step 2 command. Expected: 1 passed.

- [ ] **Step 5: Run `test_score.py` and see the one known failure**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py`

Expected: exactly 1 failure, `test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut`. Its line, `issue: OOMKilled — …`, starts with the label `issue:`, so its cuts are no longer made. That is the new rule working.

- [ ] **Step 6: Rewrite that test on a line with no label**

Replace `test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut` with:

```python
def test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut():
    """G3b also zeroes a cause that holds an own line minus its first word,
    or minus its first 2 words. A 3-word cut is not made: the cause below
    that holds the line minus its first 3 words passes.

    2026-10-05 (Spec 4b-4): this test used the inventory line `issue:
    OOMKilled — …`. Its first word is a label, and G3b no longer cuts past
    a label, so the test uses the candidate line now. It has no `:` in its
    first 2 words."""
    own = _normalized(_GUARD_API_CANDIDATES)
    words = score._norm_cause(_GUARD_API_CANDIDATES[1]).split()
    assert score._job2_guarded("memory limit: " + " ".join(words[1:]), (), own)
    assert score._job2_guarded("memory limit: " + " ".join(words[2:]), (), own)
    assert not score._job2_guarded("memory limit: " + " ".join(words[3:]), (), own)
```

- [ ] **Step 7: Write the exam probe and its helpers**

At the very end of `tests/test_score.py`, add:

```python


# --------------------------------------------------- exam probes (Spec 4b-4)
#
# Each probe is the gold reply with one change, scored on the real exam.
# The change is something a right answer may say, or something a wrong one
# may say, so the score shows whether the grader tells them apart.

_LOG_CAUSE = re.compile(r"log cause: (.+)$", re.M)


def _gold_bot_with(rows: list[dict], change):
    """Answers each row with its gold reply, after `change(row, verdict)`
    has edited each verdict dict in place. It reads nothing."""
    by_prompt = {r["messages"][1]["content"]: r for r in rows}

    def chat_fn(messages: list[dict]) -> str:
        row = by_prompt[messages[1]["content"]]
        reply = json.loads(row["messages"][2]["content"])
        for verdict in reply["verdicts"]:
            change(row, verdict)
        return json.dumps(reply)

    return chat_fn


def _count_changed(rows: list[dict], change) -> int:
    """How many gold verdicts `change` alters. A probe that alters none
    proves nothing, so each probe pins this count too."""
    n = 0
    for row in rows:
        for verdict in json.loads(row["messages"][2]["content"])["verdicts"]:
            before = verdict["cause"]
            change(row, verdict)
            n += verdict["cause"] != before
    return n


def _add_log_cause_label(row: dict, verdict: dict) -> None:
    labels = _LOG_CAUSE.findall(row["messages"][1]["content"])
    wm = row["meta"]["workloads"].get(verdict["workload"]) or {}
    if wm.get("job") == 2 and labels and verdict["cause"] != NONE_OF_THESE:
        verdict["cause"] += " because of a " + labels[0].strip()


def test_a_right_answer_in_a_log_cause_labels_words_scores_on_the_exam():
    """Limit 13 on the exam. The probe adds " because of a <the prompt's
    first log-cause label>" to each named job-2 cause: 50 answers change,
    and every one is still right. Before 2026-10-05 (Spec 4b-4), G3b cut
    `log cause:` off the line and zeroed 30 of them: 167 of 197 = 0.8477.
    Now 197 of 197."""
    rows = _corpus_rows()
    assert _count_changed(rows, _add_log_cause_label) == 50
    board = score.scoreboard(score.evaluate(rows, _gold_bot_with(rows, _add_log_cause_label)))
    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 197}
```

- [ ] **Step 8: Run the probe**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k "log_cause_labels_words or g3b"`

Expected: all pass. To see it fail first, run it once with the two `_g3b` lines from Step 3 commented out: job 2 reads `{'rate': 0.8477, 'n': 197}`. Put the lines back.

- [ ] **Step 9: Run the full suite and ruff**

Expected: 1,945 passed, 10 skipped, 0 failed. Ruff: `All checks passed!`. The three cut-paste bot tests and the hedge bot test pass unchanged.

- [ ] **Step 10: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/evals/score.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "fix(score): G3b never cuts past a label (Spec 4b-4, limit 13)"
```

---

### Task 3: One matcher for keys and must-not words

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py:363-370` (`_keywords_match`, plus the new `SHORT_WORD_MAX` and `_word_hits` right after it) and the `job2` docstring (line 373 onward)
- Test: `tests/test_score.py` (the "one cleaning step, must-not words" section, line 596; the comment in `test_keywords_match_needs_every_keyword_and_no_must_not_word`, line 624; the exam probes section from Task 2)

**Interfaces:**
- Consumes: Task 1's fold (the hyphen test below needs it); Task 2's `_gold_bot_with`, `_count_changed` and the exam probes section.
- Produces: `score.SHORT_WORD_MAX = 3`; `score._word_hits(text: str, word: str, *, negatable: bool) -> bool`. `_keywords_match(cause, keywords, must_not=())` keeps its signature.

- [ ] **Step 1: Write the failing unit tests**

In `tests/test_score.py`, right after `test_keywords_match_needs_every_keyword_and_no_must_not_word`, add:

```python
def test_a_must_not_word_after_a_negator_does_not_count():
    """Model-card limit 14, closed in part 2026-10-05 (Spec 4b-4). A right
    answer may name a must-not word to rule it out. A hit with a `NEGATORS`
    word or "n't" in the 24 characters before it does not count, the same
    window job 3 uses. A hit with no negator still zeroes the answer."""
    keys, must_not = ["memory", "limit"], ["init container", "cordon", "pressure"]

    def ok(cause):
        return score._keywords_match(cause, keys, must_not)

    assert ok("the main container, not an init container, is killed at its memory limit")
    assert ok("killed at its memory limit; it isn't the init container")
    assert ok("killed at its memory limit; the node is not cordoned")
    assert not ok("killed at its memory limit in the init container")
    assert not ok("the node is cordoned and short of memory limit")
    # "another" holds "not", but `NEGATORS` matches whole words only.
    assert not ok("another init container is killed at its memory limit")
    # Still open, and pinned so: "no" is more than 24 characters before
    # `pressure`, so the hit counts and a right answer scores 0.
    assert not ok("memory limit; no node is cordoned or under memory pressure")


def test_a_short_word_starts_a_word_and_a_long_one_is_a_substring():
    """2026-10-05 (Spec 4b-4). A key or must-not word of `SHORT_WORD_MAX`
    letters or fewer must start a word: nothing in \\w just before it. It
    may run on, so `tag` still hits "tags". A longer word is a substring,
    as before: `pull` hits "pulling", `cordon` hits "cordoned", and
    `pressure` hits "MemoryPressure", which is 0920's wrong answer on exam
    row 197 and must stay 0."""
    assert score.SHORT_WORD_MAX == 3
    # Keys.
    assert not score._keywords_match("bad image stage", ["image", "tag"])
    assert score._keywords_match("bad image tags", ["image", "tag"])
    assert score._keywords_match("bad image tag", ["image", "tag"])
    assert score._keywords_match("tag: v2 is missing from the image", ["image", "tag"])
    assert score._keywords_match("the image (tag) is wrong", ["image", "tag"])
    assert score._keywords_match("bad image_tag", ["image", "tag"])
    assert score._keywords_match("image pulling fails", ["pull"])
    # Must-not words.
    for cause in ("an outage", "a percentage", "a stage"):
        assert score._keywords_match(cause, [], ["tag"]), cause
    assert not score._keywords_match("wrong tag", [], ["tag"])
    assert not score._keywords_match("MemoryPressure on the node", [], ["pressure"])
    assert score._keywords_match("no MemoryPressure on the node", [], ["pressure"])
    # A must-not word with a "-" still hits an odd hyphen: the fold
    # (Task 1) makes it "-", and the word is escaped before the search.
    assert not score._keywords_match("init‐container killed", [], ["init-container"])
```

Also change the comment inside `test_keywords_match_needs_every_keyword_and_no_must_not_word`:

```python
    # A must-not word is a substring rule, like a keyword. "initial" does
    # not hold "init container".
```

to:

```python
    # A must-not word longer than 3 letters is a substring rule, like a
    # key (2026-10-05, Spec 4b-4). "initial" does not hold "init container".
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k "after_a_negator or short_word_starts"`

Expected: 2 failed. The first on the "not an init container" assert; the second on `AttributeError: ... 'SHORT_WORD_MAX'`.

- [ ] **Step 3: Write `_word_hits` and use it**

In `src/kubeagent_verdict/evals/score.py`, replace `_keywords_match` with this block (function, constant, helper):

```python
def _keywords_match(cause: str, keywords: Iterable[str],
                    must_not: Iterable[str] = ()) -> bool:
    """The keyword rule, written once for `job2` and `cause_acc`: the cause,
    cleaned by `_norm_cause`, holds every keyword and no must-not word. Both
    lists are lowercased and found by `_word_hits`: a word of
    `SHORT_WORD_MAX` letters or fewer must start a word, a longer one may
    sit anywhere. A must-not word with a negator just before it does not
    count, so a right answer may rule one out (2026-10-05, Spec 4b-4)."""
    c = _norm_cause(cause)
    return (all(_word_hits(c, str(k).lower(), negatable=False) for k in keywords)
            and not any(_word_hits(c, str(m).lower(), negatable=True) for m in must_not))


# A key or must-not word this short must start a word. As a substring,
# `tag` hits "stage" and "outage" (2026-10-05, Spec 4b-4).
SHORT_WORD_MAX = 3


def _word_hits(text: str, word: str, *, negatable: bool) -> bool:
    """Whether `word` is found in the cleaned `text`. A word of
    `SHORT_WORD_MAX` letters or fewer counts only where it starts a word (no
    \\w just before it); it may run on, so `tag` hits "tags". A longer word
    counts anywhere, so `pressure` hits "memorypressure". When `negatable`,
    a hit with a `NEGATORS` word or "n't" in the `NEGATION_WINDOW`
    characters before it does not count, the same rule as
    `_word_bounded_signal`."""
    start = r"(?<!\w)" if len(word) <= SHORT_WORD_MAX else ""
    for m in re.finditer(start + re.escape(word), text):
        if negatable:
            window = text[max(0, m.start() - NEGATION_WINDOW):m.start()]
            if NEGATORS.search(window) or "n't" in window:
                continue
        return True
    return False
```

`NEGATION_WINDOW` and `NEGATORS` are defined further down the module (near line 463). That is fine: `_word_hits` reads them when it runs, not when it is defined.

In the `job2` docstring, replace:

```
    every one of `own_cause_keywords` and none of `own_cause_must_not`, both
    matched as lowercase substrings -- or, on a `none_of_these` workload,
```

with:

```
    every one of `own_cause_keywords` and none of `own_cause_must_not`, both
    found by `_keywords_match` -- or, on a `none_of_these` workload,
```

- [ ] **Step 4: Run them and see them pass**

Run the Step 2 command. Expected: 2 passed.

- [ ] **Step 5: Write the two exam probes**

At the end of `tests/test_score.py`, under the exam probes section, add:

```python
def _rule_out_the_must_not_word(row: dict, verdict: dict) -> None:
    wm = row["meta"]["workloads"].get(verdict["workload"]) or {}
    must_not = wm.get("own_cause_must_not") or []
    if "init container" in must_not:
        verdict["cause"] += ", not an init container"
    if "cordon" in must_not:
        verdict["cause"] += "; the node is not cordoned"


def test_a_right_answer_that_rules_out_a_must_not_word_scores_on_the_exam():
    """Limit 14 on the exam. The probe adds ", not an init container" or
    "; the node is not cordoned" to the gold cause of each workload with
    that must-not word: 51 answers change, and every one is still right.
    Before 2026-10-05 (Spec 4b-4) all 51 scored 0: 146 of 197 = 0.7411.
    Now 197 of 197."""
    rows = _corpus_rows()
    assert _count_changed(rows, _rule_out_the_must_not_word) == 51
    board = score.scoreboard(score.evaluate(rows, _gold_bot_with(rows, _rule_out_the_must_not_word)))
    assert board["jobs"]["job2"] == {"rate": 1.0, "n": 197}


def _swap_tag_for_stage(row: dict, verdict: dict) -> None:
    wm = row["meta"]["workloads"].get(verdict["workload"]) or {}
    keys = wm.get("own_cause_keywords") or []
    if "tag" in keys:
        verdict["cause"] = " ".join(k for k in keys if k != "tag") + " stage"


def test_a_wrong_answer_that_says_stage_for_tag_fails_on_the_exam():
    """The 3-letter kit keys on the exam. The probe answers each workload
    keyed on `tag` with its other keys plus "stage": 6 answers change, and
    every one is wrong. Before 2026-10-05 (Spec 4b-4), `tag` sat inside
    "stage" and all 6 passed: 197 of 197. Now 191 of 197 = 0.9695."""
    rows = _corpus_rows()
    assert _count_changed(rows, _swap_tag_for_stage) == 6
    board = score.scoreboard(score.evaluate(rows, _gold_bot_with(rows, _swap_tag_for_stage)))
    assert board["jobs"]["job2"] == {"rate": 0.9695, "n": 197}
```

- [ ] **Step 6: Run the probes**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k "rules_out_a_must_not or says_stage_for_tag"`

Expected: 2 passed. To see them fail first, run once with `_keywords_match`'s old body (`all(str(k).lower() in c for k in keywords) and not any(str(m).lower() in c for m in must_not)`): the first reads `{'rate': 0.7411, 'n': 197}`, the second `{'rate': 1.0, 'n': 197}`. Put the new body back.

- [ ] **Step 7: Run the full suite and ruff**

Expected: 1,949 passed, 10 skipped, 0 failed. Ruff: `All checks passed!`. In particular `tests/test_answer_keys.py::test_0920s_wrong_memory_request_answers_score_0` passes unchanged: "MemoryPressure" still hits `pressure`.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/evals/score.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "fix(score): short keys start a word, must-not words see a negator (Spec 4b-4, limit 14)"
```

---

### Task 4: The decoy gate tests job 1 and compares cleaned text

**Files:**
- Modify: `src/kubeagent_verdict/evals/score.py:214-216` (comment), `:795-799` (comment), `:806-813` (the decoy loop)
- Test: `tests/test_score.py` (`test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload` at line 1474; `test_the_gold_reply_names_no_decoy_on_any_exam_row` at line 1499; the decoy tests near line 885; the exam probes section)

**Interfaces:**
- Consumes: Task 1's `_norm_cause`; Task 2's `_gold_bot_with`, `_count_changed` and the exam probes section; the existing helpers `_node_workload`, `_one_verdict`, `_decoy_row`, `_corpus_rows`, and `score._workload_decoys(meta, workload) -> list[str]`.
- Produces: no new names.

- [ ] **Step 1: Write the failing tests**

(a) Replace `test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload` (line 1474) with:

```python
def test_decoy_gate_tests_a_job1_workload_too():
    """2026-10-05 (Spec 4b-4): job-1 workloads count in `decoy_rate` again.

    This test was `..._is_none_when_the_only_decoy_sits_on_a_job1_workload`
    and pinned `named_decoy` None there. Spec 4a skipped job 1 because a
    decided workload's own cause could be listed as its decoy, so the right
    answer named its own "decoy". Since Spec 4b-3 no case does that
    (`tests/test_multi_decoys.py`). So a job-1 workload's decoy is tested:
    the right answer reads False, the decoy reads True."""
    wm = _node_workload(cause="node worker-1 (disk pressure)")
    gold = _one_verdict("shop/api", wm["decided_cause"])
    row = {"messages": [{"role": "system", "content": "sys"},
                        {"role": "user", "content": "user shop/api"},
                        {"role": "assistant", "content": gold}],
           "meta": {"case": "contradiction_probe", "label": "none",
                    "decoy_by_workload": {"shop/api": ["node worker-2 (NotReady)"]},
                    "workloads": {"shop/api": wm}}}

    right = score.evaluate([row], lambda _messages: gold)
    assert right[0]["named_decoy"] is False
    assert score.scoreboard(right)["overall"]["decoy_rate"] == {"rate": 0.0, "n": 1}

    wrong = score.evaluate([row], lambda _messages: _one_verdict("shop/api",
                                                                 "node worker-2 (NotReady)"))
    assert wrong[0]["named_decoy"] is True
    assert score.scoreboard(wrong)["overall"]["decoy_rate"] == {"rate": 1.0, "n": 1}
```

(b) Right after `test_decoy_rate_is_zero_when_the_model_reads_the_evidence` (near line 890), add:

```python
def test_decoy_rate_cleans_both_sides_before_it_compares():
    """2026-10-05 (Spec 4b-4). The decoy compare used the raw answer, so a
    decoy copied with capitals or a trailing period did not count as
    naming it. Both sides are cleaned by `_norm_cause` now. It is still an
    exact match: a hedge that holds the decoy is G2's job, not this one."""
    board = score.scoreboard(_decoy_row("Node Worker-2 under MEMORY pressure."))
    assert board["overall"]["decoy_rate"] == {"rate": 1.0, "n": 1}
    board = score.scoreboard(_decoy_row("memory limit too low, or node worker-2 under memory pressure"))
    assert board["overall"]["decoy_rate"] == {"rate": 0.0, "n": 1}
```

(c) At the end of `tests/test_score.py`, under the exam probes section, add:

```python
def _name_the_first_decoy_in_capitals(row: dict, verdict: dict) -> None:
    decoys = score._workload_decoys(row["meta"], verdict["workload"])
    if decoys:
        verdict["cause"] = decoys[0].upper() + "."


def test_a_decoy_named_in_capitals_counts_on_the_exam():
    """Every workload with a decoy answers with its first decoy, in
    capitals, plus a period: 200 answers on 174 rows. Before 2026-10-05
    (Spec 4b-4), the raw compare missed every one and only job-2 workloads
    were tested: {0.0, 121}. Now both sides are cleaned and job 1 counts:
    {1.0, 174}."""
    rows = _corpus_rows()
    assert _count_changed(rows, _name_the_first_decoy_in_capitals) == 200
    board = score.scoreboard(score.evaluate(
        rows, _gold_bot_with(rows, _name_the_first_decoy_in_capitals)))
    assert board["overall"]["decoy_rate"] == {"rate": 1.0, "n": 174}
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py -k "job1_workload_too or cleans_both_sides or decoy_named_in_capitals"`

Expected: 3 failed. `named_decoy` is None (not False) on the job-1 row; `{'rate': 0.0, 'n': 1}` on the capitals row; `{'rate': 0.0, 'n': 121}` on the exam.

- [ ] **Step 3: Change the decoy loop**

In `src/kubeagent_verdict/evals/score.py`, in the `named_decoy` loop (near line 806), delete these two lines:

```python
            if ((meta.get("workloads") or {}).get(workload) or {}).get("job") != 2:
                continue
```

and replace:

```python
                decoy_hits.append(str(got.get("cause", "")) in decoys)
```

with:

```python
                decoy_hits.append(_norm_cause(got.get("cause", ""))
                                  in {_norm_cause(d) for d in decoys})
```

Replace the comment just above the loop (near line 795):

```python
        # Only job-2 workloads are tested (2026-09-29, Spec 4a). The 4a
        # reason (a decided workload's own cause in its decoy list) stopped
        # holding at 4b-1, and 4b-3 pins it false; testing job 1 is left for
        # 4b-4. A row with no job-2 workload that
        # carries a decoy has nothing to test, and `named_decoy` is None.
```

with:

```python
        # Job-1 and job-2 workloads are both tested (2026-10-05, Spec 4b-4).
        # Spec 4a tested job 2 only: a decided workload's own cause could sit
        # in its decoy list. 4b-3 pins that no case does that. Both sides are
        # cleaned by `_norm_cause` before the exact compare, so a decoy copied
        # with capitals or a trailing period counts. A row with no workload
        # that carries a decoy has nothing to test, and `named_decoy` is None.
```

And replace the comment near line 214:

```python
# No case lists a workload's own gold as its decoy (pinned by
# tests/test_multi_decoys.py since Spec 4b-3). Job 1 is still skipped:
# widening the decoy gate to job 1 is a grader change, left for 4b-4.
```

with:

```python
# No case lists a workload's own gold as its decoy (pinned by
# tests/test_multi_decoys.py since Spec 4b-3). So the decoy gate tests
# job-1 workloads too (2026-10-05, Spec 4b-4).
```

- [ ] **Step 4: Run them and see them pass**

Run the Step 2 command. Expected: 3 passed.

- [ ] **Step 5: Run `test_score.py` and see the one known failure**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_score.py`

Expected: exactly 1 failure, `test_the_gold_reply_names_no_decoy_on_any_exam_row`: `{'rate': 0.0, 'n': 174}` != `{'rate': 0.0, 'n': 121}`. 53 rows gain a decoy score from their job-1 workloads, and the gold reply names none.

- [ ] **Step 6: Re-pin it by hand**

In `test_the_gold_reply_names_no_decoy_on_any_exam_row`, add this paragraph at the end of the docstring:

```
    2026-10-05 (Spec 4b-4): job-1 workloads are tested too. 174 exam rows
    carry a decoy on a job-1 or job-2 workload, was 121. The gold reply
    still names none of them.
```

and replace the last two lines:

```python
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 128.
    assert score.scoreboard(results)["overall"]["decoy_rate"] == {"rate": 0.0, "n": 121}
```

with:

```python
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 128.
    # 2026-10-05 (Spec 4b-4): job-1 workloads are tested too; was 121.
    assert score.scoreboard(results)["overall"]["decoy_rate"] == {"rate": 0.0, "n": 174}
```

- [ ] **Step 7: Run the full suite and ruff**

Expected: 1,951 passed, 10 skipped, 0 failed. Ruff: `All checks passed!`. If any other test pins a `decoy_rate` or `named_decoy` that moved, re-pin it by hand the same way (dated comment, old value, reason) and say so in the report. On the scratch run, none did.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/evals/score.py tests/test_score.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "fix(score): the decoy gate tests job 1 and compares cleaned text (Spec 4b-4)"
```

---

### Task 5: The docs

**Files:**
- Modify: `docs/model-card.md` (the bullet at line 900; limit 13 at line 1208; limit 14 at line 1221)
- Modify: `contract/PIN.md` (the 4b-1 entry's "Still open for 4b-4" lines near line 925; a new entry at the end of the file)

**Interfaces:**
- Consumes: the numbers Tasks 1-4 pinned. Copy them; do not re-measure.
- Produces: nothing code reads.

- [ ] **Step 1: Model card, the decoy-rate bullet**

In `docs/model-card.md`, at the end of the bullet that starts `- **The decoy rate counts job-2 workloads only.**` (line 900, ends "… 0 of 128 now."), add on new lines, indented 2 spaces like the bullet:

```
  (2026-10-05, Spec 4b-4: job-1 workloads count again. The reason for the
  skip is gone: since Spec 4b-3 no case lists a workload's own cause as
  its decoy, and a test pins it. On the exam 174 rows now carry a decoy,
  was 121. The gold reply names a decoy on 0 of 174. 0920 has not been
  run on this exam, so its number is not re-measured.)
```

- [ ] **Step 2: Model card, limit 13**

At the end of limit 13 (ends "One idea: never cut past a word that ends in `:`."), add on new lines, indented 4 spaces like the item:

```
    (2026-10-05, Spec 4b-4: closed. G3b never cuts past a word that ends
    in `:`. The whole line, or the line with words before the label cut,
    still counts. On the exam, 50 job-2 workloads carry a `log cause:`
    line. A probe that adds the label's words to each right answer scored
    167 of 197 before and 197 of 197 now. The three cut-paste bots still
    score 0 of 197.)
```

- [ ] **Step 3: Model card, limit 14**

At the end of limit 14 (ends "Spec 4b owns the rest."), add on new lines, indented 4 spaces:

```
    (2026-10-05, Spec 4b-4: mostly closed. A must-not word with "not",
    "no", "n't" or another negator in the 24 characters before it no
    longer counts. A probe that adds ", not an init container" or "; the
    node is not cordoned" to each right answer scored 146 of 197 before
    and 197 of 197 now. A key or must-not word of 3 letters or fewer must
    start a word, so `tag` no longer hits "stage", "outage" or
    "percentage". A probe that writes "stage" for `tag` scored 197 of 197
    before (6 wrong answers passed) and 191 of 197 now. Longer words stay
    substrings on purpose: `cordon` must hit "cordoned", and `pressure`
    must hit "MemoryPressure", 0920's wrong answer on exam row 197. Still
    open: a negator more than 24 characters back, as in "no node is
    cordoned or under memory pressure". That answer still scores 0.)
```

- [ ] **Step 4: PIN.md, the pointer in the 4b-1 entry**

In `contract/PIN.md`, right after these lines in the 4b-1 entry (near line 925):

```
    Still open for 4b-4: the guard for 4+-letter kit keys, widening the
    decoy gate to job 1, and the sum half of IS-22. That half fails on
    4b-1 stories, exam rows included, so it waits for the exam rebuild.
```

add, at the same indent:

```
    (2026-10-05: 4b-4 took only the grader items. The rest moved to the
    exam rebuild. See the "2026-10-05 — Spec 4b-4" entry below.)
```

- [ ] **Step 5: PIN.md, the new entry**

At the end of `contract/PIN.md` (after "Full suite: 1,940 passed. Ruff: clean."), add:

```markdown

### 2026-10-05 — Spec 4b-4: grader leftovers

No pin moved. No exam, train or val byte changed. `FROZEN_SLICE_SHA256`,
`EVAL_SET_SHA256` and `GRADED_VIEW_SHA256` stay as they were. Only the
grader changed: `src/kubeagent_verdict/evals/score.py`, and the cleaning
twin in `src/kubeagent_verdict/dataset/gold.py`. The design is in
`docs/superpowers/specs/2026-10-05-grader-leftovers-design.md`.

The six changes, with what each one moves on the exam (249 rows, 197
job-2 workloads). A "probe" is the gold reply with one change.
1. The decoy gate tests job 1. `decoy_rate` counts 174 rows, was 121.
   The gold reply names a decoy on 0 of 174.
2. The decoy compare cleans both sides with `_norm_cause`. A probe that
   names each first decoy in capitals plus a period: `decoy_rate`
   {0.0, 121} before, {1.0, 174} after.
3. G3b never cuts past a word that ends in `:` (model-card limit 13). A
   probe that adds a `log cause:` label's words to 50 right answers: job 2
   167 of 197 before, 197 of 197 after.
4. A must-not word with a negator in the 24 characters before it does not
   count (model-card limit 14). A probe that rules out the must-not word
   in 51 right answers: job 2 146 of 197 before, 197 of 197 after.
5. The cleaning step folds U+2010 to U+2015 to `-` and `_` to a space,
   after NFKC, in both twins. A new test keeps the twins equal.
6. A key or must-not word of 3 letters or fewer must start a word
   (`SHORT_WORD_MAX = 3`). This is the grader's answer to the 4+-letter
   kit-key guard. A probe that writes "stage" for `tag` on 6 workloads:
   job 2 197 of 197 before (6 wrong answers passed), 191 of 197 after.

What did not move: the gold reply scores 1.0 on job 1 (102), job 2 (197)
and job 3 (40). The hedge bot scores job 2 0.4162 of 197. The three
cut-paste bots score job 2 0.0 of 197. The bars did not move.

Hand re-pins, each dated 2026-10-05 (Spec 4b-4) in a comment:
- `test_the_gold_reply_names_no_decoy_on_any_exam_row`: `decoy_rate` n
  121 to 174.
- `test_job2_guards_a_none_of_these_workload_too`: the made-up own line
  is the cleaned `none of these` now. The made-up decoy `none_of_these`
  cleans to 3 words, so G2 tests it: 1.0 to 0.0. No exam decoy has a `_`.

Test changes:
- `test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload`
  is now `test_decoy_gate_tests_a_job1_workload_too`.
- `test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut`
  uses a candidate line now. Its old line starts with the label `issue:`.
- New in `tests/test_score.py`: the fold test (both twins), the twin
  test, the G3b label test, the negator test, the short-word test, the
  cleaned-compare test, and four exam probes.

Left for the exam rebuild. These were on 4b-4's list, but each changes
exam rows, so they move with the rebuild and its one re-pin:
- IS-22's sum half: the reasons in "0/N nodes are available: ..." add up
  to N. It fails on 4b-1 stories, exam rows included.
- node-disk-pressure's ContainerStartError keys: ("containerd", "task")
  to ("space", "containerd").
- The weak pairs: 3 left (see the 4b-2 entry).
- The G2 registry skip: the bad-image-tag key has no must-not word for a
  registry fault.
- Must-not words for the shared-origin family.
- B6: a refused read's short "is forbidden" text.
- The tighter checker checks: service-line wording and sort order, the
  network-policy gate, a message-only NotReady line over 120 runes, lease
  ages 0s to 39s, an extra system line at 10 rows, and ANS-2 counting
  ruled-out lines. They move no row, but they belong with the build.
- B4's fourth arm, the shared-cause cap. It needs a new Go capture.
- image-pull-secret-expired graded as unverified.

Full suite: 1,951 passed. Ruff: clean.
```

- [ ] **Step 6: Check nothing else moved**

Run: `cd /home/ubuntu/git/kubeagent-verdict && git diff --stat main -- data contract out dist | cat`
Expected: only `contract/PIN.md` listed.

Run the full suite and ruff. Expected: 1,951 passed, 10 skipped, 0 failed. `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add docs/model-card.md contract/PIN.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "docs: record Spec 4b-4 grader leftovers in the model card and PIN.md"
```
