# Training targets that agree with kubeagent's rules — design

**Date:** 2026-09-19
**Branch:** `fix-training-targets` (off `main` @ `abdc0be`)
**Status:** approved in chat (option A and rulings A–F); written here for review

## The decision, up front

We fix the training data before we train again. Today about one training
row in five teaches an answer that kubeagent v1.24.0's own rules
contradict. A retrain on that data would spend about 33 hours teaching the
wrong thing.

This slice does five things:

1. `multi` rows stop overwriting the rules' decided cause with a
   hand-written one.
2. `shared_origin` rows stop claiming a shared cause when the rules did
   not confirm one.
3. Six new training stories where the rules *do* confirm a shared cause.
   Today no training row carries the `shared` label at all.
4. A new case mix, so every story still has enough training rows after the
   held-out drop.
5. Oracle gates: before any training, the gold answers must score perfectly
   on our own scorer wherever a perfect score is possible.

Then we retrain once on the training host, with a check at step 400 of 798.

The exam changes on 14 of its 263 rows. What the scorer reads does not
change, and a pinned hash (the "graded view", section 9) proves it. So
0908's exam scores must replay exactly on the new exam.

The retrained model is a new baseline. Its numbers cannot be compared with
0908's training runs, only with 0908's exam scores.

## Words this document uses

- **Gold answer.** The assistant message in a row: what we teach in
  training, and what the exam's diagnostics compare against.
- **Rule row.** A workload the rules decided. Its prompt carries a
  `decided by rules:` line. Job 1 grades it: echo that cause word for
  word, and write a rationale that does not deny the fresh read.
- **Label.** A row's job-3 label: `shared`, `separate` or `none`. It comes
  from `rules.label(rules.shared(results))`. `shared` means two or more
  workloads have a *confirmed* result in the same group. Unverified results
  never count.
- **Pair, twin.** `shared_origin` and `shared_origin_decoy` rows are built
  in pairs from one salt. Both twins draw the same names, menus and read
  labels. Only read contents differ. The **broken twin** shows the origin
  broken; the **healthy twin** shows it healthy.
- **Plain story.** One of today's 48 trainable shared-origin stories. It
  has no `origin_object`, so the rules never decide anything in it.
- **Ruled story.** One of the six new stories. It sets `origin_object`: a
  node, a PVC or a registry, the three kinds the rules can check.
- **Oracle test.** Feed each row's own gold answer to `score.evaluate` as
  if a model wrote it. A correct dataset scores 1.0 wherever 1.0 is
  reachable.
- **0908.** The model from the last retrain. Our negative control.

## Why

Measured on today's built files (seed 17, size 8000; `train.jsonl` has
6353 rows, `val.jsonl` 718):

| What is wrong | How many |
|---|---|
| `multi` rule rows whose gold cause is a hand-written string, not the rules' cause | all of them: 996 of 996 in train, 121 of 121 in val |
| undecided `multi` rows whose gold cause is `winner_cause` instead of `own_cause` | 185 in train |
| `shared_origin` summaries that claim a shared cause while the label is `none` | all of them: 862 of 862 in train, 98 of 98 in val |
| training rows labelled `shared` | 0 |
| `multi` rows whose healthy node read clashes with another read of the same node | 38 of 79, before the held-out drop |

What each one costs:

- **The first two.** Scoring the gold answers as replies gives job 1 0.6125
  on train, where it should be 1.0. Job 2, counted only on rows it can
  grade by keyword, gives 0.9149: 185 failures, all from `multi`.
- **The third** teaches the habit the exam's decoy probe is there to
  catch: "a cluster-wide read at the top means claim one shared cause."
- **The fourth** means the model never sees a `shared` label in training.
  Job 3 still grades it on 5 exam rows.
- **The fifth** puts two facts side by side in one prompt. One read says
  `describe node worker-2` worked and showed Ready True. A candidate line
  says reading `worker-2` was forbidden.

For scale, here is 0908 on today's exam. Bars are 0.9, 0.7 and 0.9.

| Job | 0908 | Rows scored |
|---|---|---|
| job 1: echo the decided cause | 0.1783 | 157 |
| job 2: name the cause on an undecided row | 0.2418 | 153 |
| job 3: label the summary | 0.7179 | 39 |

## What does not change

- kubeagent. It is read-only to this project.
- `score.py`, the three job bars and the five deciders.
- `contract/system_prompt.txt`, the prompt renderer and the captured
  goldens under `contract/golden/`.
- The training recipe: base model, LoRA settings, 2 epochs, batch 16,
  seed 17, size 8000, CPU on the training host.
- `split`, `drop_held_out` and every group string. The fix builds groups
  from the same keys and names as today.
- The 48 plain stories' text and every catalog entry's text.
- Confidence in every gold row. The v1.24.0 spec says confidence stays as
  the catalog declares it; job 1 does not read it.
- The training device stays the CPU. Moving to a GPU changes the
  weights, so it is a separate recipe change.

## Changed since the approved design

Six things differ from what was approved in chat. Four came out of
checking the design against code. Two were found while writing this.

1. **One pair in five, not one in three, and the share rises to 15%.**
   One ruled pair in three at today's 12% leaves 16 of the 48 plain stories
   below the floor of 12 kept pairs (the lowest keeps 8). One in five at
   15% leaves none below it (the lowest keeps 13). Section 6 has the
   numbers.
2. **The unverified twin is node-only.** Section 5 says why PVC and
   registry cannot have one.
3. **"The exam tests exactly this twice" was wrong.** Two of the exam's
   shared-origin stories (`coredns-down`, `node-disk-pressure`) reach a
   rules decision through per-victim decoy objects, not an origin object.
   Section 3 covers how those rows are handled.
4. **The graded view gains one flag per workload.** The first definition
   dropped each workload's `expected_cause` entirely. But job 2 switches
   on it: `none_of_these` means exact match, anything else means keyword
   match. So the view now keeps a boolean for that switch (section 9).
5. **New: `multi` drops a registry-story healthy read next to a registry
   candidate.** Found while writing. Section 2.
6. **New: a ruled registry story counts its own victims.** Found while
   writing. Exam row 252 says "3 workloads failing to pull" with 2
   workloads flagged. The new stories must not copy that. Section 4.

## 1. The `multi` fix

`cases.multi` (`dataset/cases.py:1131-1204`) runs the real rules on each
workload. Then it throws the answer away and writes the catalog entry's
hand-written `winner_cause` into the gold row, decided or not.

The fix, per workload:

- **Decided:** gold cause is `result.cause`. Rationale is
  `_rule_rationale(result)`.
- **Undecided:** gold cause is `_fmt(e.own_cause, n)`. Rationale stays
  `_fmt(e.rationale, n)`.

Everything else stays: confidence, the keyword rule
(`own_cause_keywords` is empty when the row is decided or the cause is
`none_of_these`), the summary, and the healthy-origin read (section 2).

`_rule_rationale` builds a rationale from the rules' own evidence
sentence, so it cannot disagree with the fresh read:

```python
_NOUN = {"node": "node", "pvc": "claim", "registry": "registry"}

def _rule_rationale(result: rules.Result) -> str:
    kind, name = result.cause.split(" ", 2)[:2]
    noun = _NOUN[kind.lower()]
    evidence = result.evidence[0].lower() + result.evidence[1:]
    if result.outcome == "confirmed":
        return (f"The fresh read of {noun} {name} confirms it: {evidence}, "
                f"so the {noun}'s own state is why the flagged workload is failing.")
    return (f"The fresh read of {noun} {name} did not clear the earlier finding: "
            f"{evidence}, so {name} stays the named cause rather than something "
            f"the read ruled out.")
```

It was hand-checked against every confirmed and unverified branch of
`_check_node`, `_check_pvc` and `_check_registry`, against job 1's denial
phrases, its node "is ready" check and its overclaim words. The
unverified wording uses no overclaim word; "confirms" appears only in the
confirmed branch, and job 1 runs the overclaim check only on unverified
rows. It was then measured on real rows: every decided `multi` workload
passes job 1 with it. The branches only the new stories reach (PVC
confirmed, registry confirmed) are measured by the oracle gate
(section 10).

One authoring rule keeps it that way: a failed-read message
(`objects.unverify`) contains no denial phrase and no overclaim word.
A test checks every message.

Measured with this exact code patched in: job 1 on decided `multi` rows
goes to 996 of 996 in train and 121 of 121 in val. Keyword-graded job 2 goes from
0.9149 to 1.0 on train.

## 2. The `multi` healthy-origin read

One `multi` row in three starts with a shared-origin story's read, showing
the origin healthy. It teaches that a cluster-wide read at the top does
not by itself mean a shared cause.

The read is formatted with the first workload's names. So for a node story
it names the first workload's node. That node is often also a rules object
in the same row, and sometimes with a clashing state.

**Node rule.** Keep the node name unless the row holds a node object with
that name whose fresh read failed, or whose Ready condition is not
`True`. If it does, use the first node in `worker-1`, `worker-2`,
`worker-3` that has no such object. If all three clash, drop the healthy
read for that row.

Measured over today's rows: 79 have a node-story healthy read. The rule
keeps 41, renames 37 and drops 1. In the kept training rows, every clash
is one of the two kinds above: a forbidden read (20 rows) or a confirmed
NotReady node (3 rows). A node that the rules refuted or left on a stale
lease shows Ready True too, so it does not clash.

**Registry rule (new).** The two ruled registry stories' healthy read is a
cluster-wide events read. If the row holds any registry object, drop the
healthy read. Otherwise the prompt would show a cluster-wide read with no
auth error next to a pod whose events show one.

**PVC stories need no rule.** Their read names a storage class that no
`multi` object uses (section 4).

**Rotation (ruling B).** The rotation already walks
`train_scen[(i // 3) % len(train_scen)]`. With 54 stories it covers all
54, the six ruled ones included. Its comment's "960/960" and "~0.55" are
re-measured.

Tests: no rendered `multi` row has a healthy node read naming a node that
a failed read or a confirmed candidate also names. No row has a
registry-story healthy read and a registry candidate together.

`multi` adds only the read. It never adds a rules object for the story.

## 3. The `_render_shared_origin` fix

`_render_shared_origin` (`dataset/cases.py:757-905`) builds both twins. It
has the same flaw as `multi`, plus a second one:

- The gold cause is `decoy if healthy else shared_cause`, even when the
  rules decided the row.
- The summary follows `healthy`, not the label the rules computed a few
  lines later. So every broken twin says "N workloads share one upstream
  cause", even when the label is `none`.

The fix:

- **Decided rows** get `result.cause` and `_rule_rationale(result)`.
- **Other rows** keep `decoy if healthy else shared_cause`, with today's
  confidence and rationale.
- **The summary follows the label:**

| Label | Summary |
|---|---|
| `shared` | Today's three lines, unchanged: "{count} workloads share one upstream cause: {origin}." / "Root cause: {shared_cause}." / the remedy. |
| `none`, healthy twin, every row cause different | "{count} workloads are failing for separate reasons.", then one line per row (first three). |
| any other `none` | "{count} workloads are failing, and kubeagent's rules did not confirm one cause on two or more of them.", then one line per row (first three). No remedy. |
| `separate` | Raise `ValueError`. |

Why `separate` raises: every victim in a story binds the *same* origin
object, so any confirmed results share one group. `separate` needs two
different confirmed groups, which this function cannot produce. A test
forces the branch with a monkeypatched `rules.label` and checks the error.
This settles the second critic finding: the branch exists and is tested,
but no row can reach it.

**The critic's first finding is overruled.** Two exam stories,
`coredns-down` and `node-disk-pressure`, reach a rules decision through a
per-victim decoy node, not through an origin object. The critic asked us
to keep the hand-written cause on those rows. We give them the rules'
cause, like every other rule row, for three reasons:

1. `contract/system_prompt.txt` line 6 tells the model to return a
   decided cause verbatim. kubeagent's `ruleRow` prints the rules' cause
   whatever the model says.
2. Those rows are exam-only. No training row is built from them.
3. Job 1 already grades them against the rules' cause, and all 16 of them
   fail job 1 with today's gold answer. The fix makes the gold answer agree
   with what is graded.

The rationale for those rows now comes from `_rule_rationale`, so it talks
about the node, not about CoreDNS. The disclosed limits (section 12) say
this.

## 4. Six ruled stories

Pool: 54 stories, the 48 plain ones plus 6 ruled ones. A ruled story sets
`origin_object`, so the rules check the origin itself. Victims in a ruled
story carry no per-victim objects (`v.objects` is empty).

| Story | Origin object | Broken fresh read | Healthy fresh read | Origin read label |
|---|---|---|---|---|
| node 1 | node, scan reason `NotReady` | Ready `False` | Ready `True` (refuted) | `describe node {node}` |
| node 2 | node, scan reason `NotReady` | Ready `Unknown` | Ready `True` (refuted) | `describe node {node}` |
| PVC 1 | PVC, `ProvisionerNotResponding`, mounted | phase `Pending` | phase `Bound` (refuted) | `get_related storageclass {sc}` |
| PVC 2 | PVC, `MissingStorageClass`, mounted | phase `Pending` | phase `Bound` (refuted) | `get_related storageclass {sc}` |
| registry 1 | registry `mirror.invalid` | literal `no such host` | literal `manifest unknown` (refuted) | `get_events (cluster-wide, reason=Failed)` |
| registry 2 | registry `registry.invalid` | literal `toomanyrequests` | literal `manifest unknown` (refuted) | `get_events (cluster-wide, reason=Failed)` |

Rules each story relies on (from `dataset/rules.py`):

- Node: Ready `False` or `Unknown` confirms. Ready `True` refutes. The
  group is `node/{name}`, the same for every victim on that node.
- PVC: `Pending` confirms, `Bound` refutes. With either reason above and a
  plain class, the group is `storageclass/{sc}/{reason}`. So victims with
  different claims still share one group.
- Registry: a connection literal confirms, an image literal refutes. The
  group is `registry/{name}`.

Authoring rules:

- **Storage classes.** Each PVC story uses a new plain class that no
  other code uses. The classes already taken are `fast-ssd`, `standard`,
  `ssd-premium`, `block-ssd`, `archive-hdd`, `encrypted-ssd`, `bulk-nvme`
  and `replicated-ssd`.
- **Registry hosts.** `mirror.invalid` and `registry.invalid`, unused in
  `src/` today. Victim images are rewritten to the story's host at render
  time, with no random draw. For `registry.example.com` this is a no-op, so
  the exam does not move.
- **Registry count.** A ruled registry story's scan reason is the number
  of victims the row renders, filled in at render time. A literal scan
  reason, like the exam's `"3"`, is left alone.
- **Registry victims** use issues from `REGISTRY_ISSUES`, so the rules
  consider the registry for them.
- **Origin reads.** At least four variants per story, each with a
  different first line. Free-form text, like the plain stories.
- **Healthy PVC and registry content** names no `{pvc}`, `{pod}`,
  `{image}` or `{name}`. Registry content also carries no counts and names
  no workload. That keeps it true in any row it lands in.
- **Phrases.** `origin`, `shared_cause` and `remedy` contain no
  independence phrase and no negated shared-claim phrase. Otherwise job 3
  would fail the `shared` summary built from them.
- **Leaks.** The new classes and hosts are never a catalog object's value.
  A static test checks this.
- **Existing tests.** The stories pass today's eval-disjointness and
  authoring-floor tests.

**Coherence.** A rendered row must not contradict itself. A test reads
every rendered ruled row and checks:

- Node: a broken variant's origin read shows `Ready` with the same value
  as the fresh read. A healthy variant shows `Ready True`. No ruled node
  content mentions a lease or a heartbeat time.
- PVC: a victim read that names its claim shows `Pending` in the broken
  twin and `Bound` in the healthy twin. The storage-class read names no
  claim.
- Registry: the broken origin read contains the fresh literal and the
  host. Broken victim reads quote the same connection literal. Healthy
  victim reads show only image-level errors, and healthy local causes are
  image-level (no auth literal).
- The unverified twin (section 5) is exempt from the origin-state checks.

## 5. The unverified twin (node only)

Every rule row in training today is `confirmed` or comes from `multi`.
No shared-origin row teaches "the rules could not check the origin". So
one node pair in three gets an unverified broken twin.

In that twin the origin object goes through
`objects.unverify(obj, "read_failed")`. The origin read's content is
exactly `read failed: nodes "{node}" is forbidden`. Every victim becomes a
rule row with outcome `unverified`. Unverified results do not count toward
`shared`, so the label is `none`. The summary is the "any other `none`"
line from section 3. The rows use the unverified rationale.

Why not PVC: the origin object's name is `{pvc}`, so each victim gets its
own claim, and a failed read names one claim. But the story shows a single
storage-class read, not one read per claim. There is no clean place in the
prompt to show three different failed claim reads.

Why not registry: every unverified ending contradicts the broken victim
reads. Those reads are pull events that quote a connection error. A failed
read says `events is forbidden`, yet the prompt shows events. An auth
ending or a missing event says the opposite of what the events show.

## 6. Selection and the case mix

The loop in `generate.generate` picks one story per pair. One pair in five
comes from the ruled pool:

```python
plain = [p for p in train_scen if p.origin_object is None]      # 48
ruled = [p for p in train_scen if p.origin_object is not None]  # 6
for i in range(counts["shared_origin"]):
    if i % 5 == 4:
        j = i // 5
        p = ruled[j % 6]
        t = j // 6
        victims = 2 + (t // 3) % (len(p.victims) - 1)
        unverified = p.origin_object.kind == "node" and t % 3 == 2
    else:
        k = i - (i + 1) // 5
        p = plain[k % 48]
        victims = 2 + (k // 48) % (len(p.victims) - 1)
        unverified = False
    salt = rng.getrandbits(64)
    # both twins from random.Random(salt), as today
```

Plain pairs walk the same story and victim sequence as today. Their salts
differ, because the ruled pairs now draw salts between them.

**New case mix.** Three points each move from `attributed` and
`none_of_these` to the two shared-origin cases:

| Case | Today | New |
|---|---|---|
| attributed | 10 | 7 |
| none_of_these | 15 | 12 |
| own_cause | 10 | 10 |
| multi | 11 | 11 |
| shared_origin | 12 | 15 |
| shared_origin_decoy | 12 | 15 |
| truncated | 5 | 5 |
| injection | 10 | 10 |
| empty_candidates | 5 | 5 |
| wrong_attribution | 10 | 10 |

Simulated at seed 17, size 8000 (numbers are training rows after the
held-out drop):

| Option | Lowest plain story | Plain stories below 12 | Ruled pairs in train | Kept rows | Steps |
|---|---|---|---|---|---|
| today, no ruled stories | 15 | 0 | 0 | 6353 | 794 |
| 12%, one in three | 8 | 16 | 288 | 6351 | 792 |
| 12%, one in four | 10 | 1 | 218 | 6357 | 794 |
| **15%, one in five (chosen)** | **13** | **0** | **213** | **6395** | **798** |
| 16%, one in four (fallback) | 15 | 0 | 294 | 6468 | 808 |

At 15%: 1200 pairs. 240 are ruled (40 per story) and 960 plain (20 per
story). Of the 240 ruled pairs, 26 are unverified node pairs (13 per node
story). About 186 to 190 broken twins in train carry the `shared` label.

The simulation used stand-in groups for the ruled pairs. The real build is
re-measured. If any plain story falls below 12, we switch to the fallback
(16%, one in four, attributed 6, none_of_these 11) and say so in the
commit.

`test_counts_for_follows_the_mix` at size 1000 moves to attributed 70,
none_of_these 120, shared_origin 150 and shared_origin_decoy 150.

## 7. Test moves

**Rulings from chat:**

- **A, equal shares.** Within each pool every story gets an equal share.
  `BIG` is `275 * len(trainable_scenarios())` today, which is 13200. With
  54 stories that formula gives 14850, so `BIG` becomes the fixed value
  13200: 1980 pairs, of which 396 are ruled (66 per story) and 1584 plain
  (33 per story). So `DRAWS = 33` still holds for plain stories, and its
  comment's sampling math stands.
- **C, label-aware rewrites.** Tests that assume one cause on every row,
  or one summary per twin, check per label instead:
  - `test_shared_origin_training.py:698`
  - `test_propagation.py:191-211` and `:226-261`
  - `test_probe_cousins.py`: 48 becomes 54, 96 becomes 108, and the twin
    assertion reads the label.
  - `test_probe_wide.py`: storage-provisioner-down's victims now carry
    per-victim PVC causes on rule rows.
- **E and F, re-measure.** Bands, dominance counts and layout floors are
  re-measured on the new build, not guessed. Ruled stories add node,
  storage-class and events layouts, so the measured counts in
  `EXAM_LAYOUT_FLOORS`' comment move. Today's floors are node 13,
  deployment 4, events 4, storageclass 6 and networkpolicy 6.

**Other moves:**

- `test_shared_origin_training.py`: lines 89-108, 113-128, 475, 538, 556,
  569, 606, 625, 660, 693, 733, 776, 820-842, 856 (`EXPECTED_POOL` 48 to
  54), 870, 917, 950, 962 and 988.
- `test_cases.py:404-425` pins the `multi` bug as a contract; it now pins
  the rules' cause on decided rows and `own_cause` on undecided ones.
- `test_shared_origin_floor.py`: `FLOOR = 12` stays. Its docstring moves.
- `test_healthy_evidence.py:31` and `:196`.
- `test_shared_origin_training_pair.py:143` still holds; it is checked,
  not moved.

**New tests:**

- The oracle tests (section 10).
- The coherence test (section 4).
- The graded-view pin (section 9).
- A shared label only comes from an origin object: every `shared` row is
  a ruled story's broken twin or one of the exam's three origin-object
  stories.
- The `multi` collision tests (section 2).
- The `separate` branch raises (section 3).
- Failed-read messages hold no denial or overclaim word (section 1).
- Ruled registry rows name their own victim count (section 4).

No test is run with `-update`. Every re-pin is made by hand, with a dated
comment.

## 8. Doc moves

- `README.md:125-127`: "the correct answer names the same shared cause on
  every row" becomes the label-driven rule.
- `docs/how-training-works.md:92`: the `shared_origin` row's "name the same
  cause on every one", and its share (12% to 15%).
- `docs/design.md:269-270` and `:284-296`: the two 12% rows, "risen to
  12%", and the shared-answer ratio ("about 38 of every 100", "a test
  fails above 40") are re-measured.
- `docs/runbooks/train.md`: line 11 ("about 28 hours"), lines 39 and 65
  ("~2¼ hours"), and lines 83, 87-88 and 133 ("17½ hours", "17h42m",
  "4,292 examples") get this run's measured numbers.
- `docs/model-card.md`: the 0908 v1.24.0 section records the test hash
  `c2d22b6e…`. It gains a dated re-pin entry saying the exam moved on 14
  rows and the graded view did not.
- `contract/PIN.md` "Dataset pin moves": a new dated entry, in the same
  style as the two before it.
- The `propagation.py` module docstring (lines 60-125) and the comment on
  `origin_object`.
- `generate.py`: a dated comment on the `CASE_MIX` change, and the
  rotation comment (section 2).
- The `_render_shared_origin` docstring cites `generate.py:156-159`; the
  loop is at 176-196 today and moves again. Cite the function, not lines.

No commit message cites a path under `docs/testing/`.

## 9. The exam: what moves and how it is pinned

`multi` never appears in the exam. `_render_shared_origin` does, through
the two probe cases. So the exam changes on 14 rows:

- `shared_origin_probe` (rows 244-253): all 10 rows. Summaries follow the
  label; decided rows carry the rules' cause.
- `shared_origin_decoy_probe` (rows 254-263): 4 rows, where a decided
  workload's cause changes.

Only the gold answer changes on those rows, plus the meta that mirrors it
(`meta["expected"]` and each workload's `expected_cause`). The prompts do
not change. Every other exam row must stay byte-identical. If any other
case changes, that is a failure, not a re-pin.

Both pins move. `FROZEN_253_SHA256` covers rows 1-253, which include rows
244-252. `EVAL_SET_SHA256` covers all 263. Both are re-pinned by hand in
`tests/test_shared_origin_training.py`, with a dated entry in the history
comment at lines 721-748.

**The graded view.** A new pinned hash over exactly what the scorer reads.
It proves the 14 changed rows changed nothing that is scored:

```python
NONE = "none_of_these"

def view(row):
    meta = dict(row["meta"])
    meta.pop("expected", None)
    ws = {}
    for k, w in meta["workloads"].items():
        d = {f: v for f, v in w.items() if f != "expected_cause"}
        d["expects_none_of_these"] = w.get("expected_cause") == NONE
        ws[k] = d
    meta["workloads"] = ws
    gold = json.loads(row["messages"][2]["content"])
    return {"messages": row["messages"][:2], "meta": meta,
            "flagged": [v["workload"] for v in gold["verdicts"]]}

rows = [generate.to_row(e) for e in generate.test_set()]
blob = json.dumps([view(r) for r in rows], sort_keys=True, ensure_ascii=False)
```

Its sha256 at `abdc0be` is
`cac6361b0bab69956d386a9d77193b82c14957014430f95bfbbd45008ae309d2`. The
test pins that value before the fix and must pass unchanged after it.

Every other top-level meta key stays in the view. On the probe rows those
are `blast_radius`, `case`, `decoy_by_workload`, `decoy_causes`,
`distractor_cause`, `expected_confidence`, `label`, `origin`,
`scope_value` and `wrong_summary_phrase`. The fix must not change any of
them; the pin is how we know it did not.

**Negative control.** Replay 0908's recorded replies (`out/eval/0908/`,
263 rows, one `output` string each, in exam order) through
`score.evaluate` on the new exam.

- **Must reproduce exactly:** job 1 0.1783, job 2 0.2418, job 3 0.7179
  (shared 1.0 on 5, none 0.6765 on 34), contract validity 0.9696, decoy
  rate 0.0988, suggestion echo 0.0.
- **May move, reported:** cause accuracy, confidence carried and
  overconfidence (0.1717 today). They compare replies with the gold cause,
  and 14 gold rows changed.
- 0908 must still miss all three job bars.

## 10. Gates before any training

All of these pass before the dataset goes to the training host:

1. **Oracle, train and val.** Gold-as-reply scores job 1 = 1.0 and job 3 =
   1.0. Job 2 = 1.0 on rows it grades by keyword.
2. **Oracle, exam.** Job 1 = 0.879 (138 of 157). The 19 misses are all
   `contradiction_probe`, which this slice does not touch. Job 3 is
   measured and expected to be 1.0 (today 34 of 39; the 5 misses are the
   `none` rows with the shared template).
3. **Length.** Every row fits in 4096 tokens with the real Qwen tokenizer.
   No row is dropped for length.
4. **Tests.** The full suite and ruff pass, including every new test in
   section 7.
5. **Exam footprint.** Exactly the 14 rows above change. The graded view
   hash does not.
6. **Negative control.** The 0908 replay in section 9.
7. **Hand read.** A person reads a sample: two rows per ruled story (both
   twins), two unverified node twins, five fixed `multi` rows and all 14
   changed exam rows.

## 11. The run

1. **Update the host.** The training host's checkout is 63 commits behind `main`.
   Pull, reinstall, and use a fresh `--out`.
2. **Build on both machines.** Run `.venv/bin/kv-dataset --seed 17 --size
   8000` on the workstation and on the training host. The four files (train, val,
   test, manifest) must match byte for byte.
3. **Smoke run.** `--limit 32 --epochs 1` on the training host. It must finish
   and write a checkpoint.
4. **Full run.** 798 steps. Launch with `nohup env HF_HUB_OFFLINE=1
   kv-train --dataset … --out … > … 2>&1 &`. Time estimate: 0908 took
   31.8 hours for 12,577,240 training tokens, so this run takes 31.8 hours
   × (new tokens ÷ 12,577,240). That is about 32 to 34 hours. Check it is
   alive by the change in CPU time (`ps -o times=`).
5. **Step 400.** When `progress.json` shows 400 optimizer steps, copy the
   checkpoint directory aside with `cp -a`. Export it on the workstation to
   `dist-retrain-<date>-step400/`, serve it with Ollama and run `kv-eval
   --endpoint … --test <ds>/val.jsonl --limit 150` (150 rows, 214
   workloads, about 33 minutes). Stop the run only if job 1 or job 3 is
   below 0.5. Anything else, keep going.
6. **Final.** Export to `dist-retrain-<date>/`, never `dist/`. Run the full
   exam (263 rows, about 44 minutes), the wide probe (60 rows) and the
   cousin probe (108 rows), all with `--endpoint`.
7. **Record.** The model card gets a new section. The result is a new
   baseline; it is not a faster route to 0908's numbers.

## 12. Disclosed limits

These stay true after this slice. Each will be written in the model card.

- **Exam `node-not-ready`.** Its gold rationale says Ready is False; its
  origin read shows `Unknown`.
- **Exam decoy-node rows** (`coredns-down`, `node-disk-pressure`). The rule
  rationale talks about the decoy node, while the rest of the row is about
  CoreDNS or disk pressure. Rows 248 and 258 (`node-disk-pressure`) also
  show one node under two scan reasons.
- **Exam storage story.** Healthy victim reads say `Pending` while the
  fresh read says `Bound`.
- **Exam row 252.** "3 workloads failing to pull" with 2 workloads
  flagged.
- **One fixed rationale template.** Every rule row's rationale follows
  `_rule_rationale`. A model could learn the template instead of the
  reasoning. Job 1 cannot see the difference.
- **Plain broken twins.** Every row names the same origin cause, while the
  summary says the rules confirmed no one cause. Both are true: the rules
  cannot check a plain story's origin. But the pairing may read oddly.
- **Two read formats for one node.** A `multi` row can show a node both in
  kubeagent's gather format (`describe node /worker-2`) and in the
  story's `describe node worker-2` format. The exam's node story does the
  same.

## Out of scope

- **Job 2's keyword gap on shared-origin rows.** Their undecided rows carry
  no keywords, so job 2 scores 0 on them whatever the reply says.
- **`contradiction_probe`.** Its 19 job-1 rows fail with the gold answer
  too. That is a separate question.
- **The GPU.** Moving device changes the weights and breaks comparison
  with every earlier run. It is its own project.

## Options not taken

**Keep the exam byte-frozen.** Fix `_render_shared_origin` for training
only, and keep a copy of the old behavior for the two probes.

- Cost: one duplicated function.
- What you learn: nothing new; 0908's recorded hash keeps matching.
- Downside: the probes would keep gold answers that contradict what the
  same code just computed. That breaks the promise rule. The graded-view
  hash already proves the scored part did not move.

**Fix only `multi`.**

- Cost: about half the work.
- What you learn: whether job 1 improves on its own.
- Downside: 862 wrong summaries stay in training, and there are still 0
  `shared` rows. Job 3 would stay untrained on the label it grades.

**Recommendation:** the full slice as written. It is the only option where
every gold answer agrees with the rules the model will run under.
