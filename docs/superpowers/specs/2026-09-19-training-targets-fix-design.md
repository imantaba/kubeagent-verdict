# Training targets that agree with kubeagent's rules — design

**Date:** 2026-09-19
**Branch:** `fix-training-targets` (off `main` @ `abdc0be`)
**Status:** approved in chat (option A and rulings A–F); revised after an
adversarial spec review; written here for review

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
   held-out drop, and the shared answer stays a minority of multi-workload
   rows.
5. Oracle gates: before any training, the gold answers must score perfectly
   on our own scorer wherever a perfect score is possible.

Then we retrain once on the training host, with a check at step 400 of
about 796.

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
   15% leaves none below it (the lowest keeps 15 with the final mix).
   Section 6 has the numbers.
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

### Changed after the spec review

An adversarial review of the first draft confirmed 16 findings: 4
important, 12 minor. What they changed:

1. **`multi` rises from 11% to 13%.** The first draft's mix put the
   shared-answer ratio at exactly 0.4000 at the real build size. A test
   fails above 0.40, and `docs/design.md` already said the next raise must
   move `multi` up too. The two extra points come from `attributed` and
   `none_of_these`, the same cases the approved design took from. Section 6.
2. **The ruled registry stories get their own read label.** The first
   draft gave them `get_events (cluster-wide, reason=Failed)`, a label only
   the exam's registry story uses today. They now use
   `get_events (cluster-wide, type=Warning)`, and a new test keeps every
   exam-only label out of training. Section 4.
3. **Plain broken twins keep the shared cause on every row.** A reviewer
   asked us to name each victim's local cause instead. We kept the shared
   cause and wrote down why (section 3). The cost is now spelled out in
   section 12, and gate 7 reads two of these rows by hand.
4. **Gates 1 and 2 say how to compute them.** Gate 1 names the job-2
   population to average over; the obvious scoreboard number reads about
   0.42 on a correct dataset. Gate 2 gives today's job 1 next to the
   target. Section 10.
5. **The run says what to do when a step fails:** a byte mismatch between
   the two builds, and a crash mid-run. Section 11.
6. **Smaller fixes.** Two line citations, the model card's test hash
   (it is not recorded there yet), the clash counts in section 2, the rows
   `FROZEN_253_SHA256` covers, one missed test pin
   (`test_evidence_overlap.py`), three missed doc passages, and one new
   disclosed limit (empty `decoy_by_workload` on ruled rows).

## 1. The `multi` fix

`cases.multi` (`dataset/cases.py:1131-1203`) runs the real rules on each
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
keeps 41, renames 37 and drops 1. In `train.jsonl` (after the split and
the held-out drop), 22 of the 48 such rows clash. Each clash is a
forbidden read, a confirmed NotReady node, or both: one row draws three
node objects all named `worker-1`. A node that the rules refuted or left
on a stale lease shows Ready True too, so it does not clash.

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
  confidence and rationale. Plain broken twins are the main case; see
  below.
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

**Row causes in a `none` summary.** Both `none` summaries list row causes.
A cause holding a shared-claim phrase ("upstream", "cascading", …) would
make job 3 read the summary as a claim and fail it. Today no story's
`shared_cause` or victim `local_cause` holds one: 0 hits across all 54
stories (48 trainable, 6 exam), and none in `names.py` either. A test
keeps the story texts that way, the new stories included; the oracle gate
catches anything the names add.

**Plain broken twins keep the shared cause (a review finding, kept).** In
a plain broken twin every row names the story's `shared_cause`, while the
summary says the rules confirmed no one cause. A reviewer asked us to name
each victim's own `local_cause` instead. We keep the shared cause, for two
reasons:

1. The origin read in that row shows the origin broken. Each victim's
   local cause is then not the most probable cause, and the system prompt
   asks for the most probable one. Teaching the local cause would teach the
   model to ignore the origin read.
2. The rows and the summary say different things, and both are true. The
   rows say what the evidence shows. The summary says what the rules did:
   they cannot check a plain story's origin, so they confirmed nothing.
   That is the line job 3 grades: claim a shared cause only when the rules
   confirmed one.

The cost is written down in section 12, and gate 7 reads two of these
rows by hand.

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
| registry 1 | registry `mirror.invalid` | literal `no such host` | literal `manifest unknown` (refuted) | `get_events (cluster-wide, type=Warning)` |
| registry 2 | registry `registry.invalid` | literal `toomanyrequests` | literal `manifest unknown` (refuted) | `get_events (cluster-wide, type=Warning)` |

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
- **Read labels.** No new story uses an origin-read label that only exam
  stories use today. At `abdc0be` that set has four labels:
  `describe kube-system/coredns (Deployment)`,
  `get_related storageclass standard`,
  `get_events (cluster-wide, reason=Failed)` and
  `get_related networkpolicy {ns}/default-deny`. A static test pins the
  set as a literal and fails if any trainable story's origin-read label is
  in it. It is pinned, not computed: a computed set would shrink the moment
  a training story took a label, and pass. `describe node {node}` is not
  in the set, because seven training stories use it today. The registry
  stories' `type=Warning` qualifier appears nowhere in `src/` or `tests/`
  today, and four training stories already use other
  `get_events (cluster-wide, …)` labels.
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

**New case mix.** Eight points move. Four each come out of `attributed`
and `none_of_these`. Three each go to the two shared-origin cases, and two
go to `multi`:

| Case | Today | New |
|---|---|---|
| attributed | 10 | 6 |
| none_of_these | 15 | 11 |
| own_cause | 10 | 10 |
| multi | 11 | 13 |
| shared_origin | 12 | 15 |
| shared_origin_decoy | 12 | 15 |
| truncated | 5 | 5 |
| injection | 10 | 10 |
| empty_candidates | 5 | 5 |
| wrong_attribution | 10 | 10 |

**Why `multi` must rise too.** A test in `test_shared_origin_training.py`
(about line 500) counts the shared answer's share of multi-workload rows:
`shared_origin` ÷ (`shared_origin` + `multi` + `shared_origin_decoy`), in
train plus val after the held-out drop, at size 800. It fails above 0.40.
Raising only the shared-origin cases lands exactly on that cap at the real
build size: 1200 ÷ (1200 + 600 + 1200) = 0.4000. `docs/design.md` and the
test's own docstring already say the next raise must move `multi` up with
it. At 13%, `multi` brings the ratio back near today's (0.3839 against
0.3797 at size 8000).

Simulated at seed 17 (the floor columns count training rows after the
held-out drop, at size 8000; the ratio is at size 8000, then 800):

| Option | Lowest plain story | Plain stories below 12 | Ruled pairs in train | Kept rows | Steps | Ratio 8000 (800) |
|---|---|---|---|---|---|---|
| today, no ruled stories | 15 | 0 | 0 | 6353 | 794 | 0.3797 (0.3810) |
| 12%, one in three | 8 | 16 | 288 | 6351 | 792 | not measured |
| 12%, one in four | 10 | 1 | 218 | 6357 | 794 | not measured |
| 15%, one in five, `multi` 11 (first draft) | 13 | 0 | 213 | 6395 | 798 | 0.4000 (0.3974) |
| **15%, one in five, `multi` 13 (chosen)** | **15** | **0** | **213** | **6369** | **796** | **0.3839 (0.3822)** |
| 16%, one in four, `multi` 13 (fallback) | 15 | 0 | 294 | 6409 | 800 | 0.3904 (0.3926) |

The chosen mix is the first draft's with two points moved into `multi`,
one from each of `attributed` and `none_of_these`. The fallback is
attributed 5, none_of_these 10, `multi` 13 and 16% each.

At 15%: 1200 pairs. 240 are ruled (40 per story) and 960 plain (20 per
story). Of the 240 ruled pairs, 26 are unverified node pairs (13 per node
story). About 186 to 190 broken twins in train carry the `shared` label.

The simulation used stand-in groups for the ruled pairs. The real build is
re-measured, and two checks decide what ships:

- If any plain story falls below 12, switch to the fallback.
- If the ratio is above 0.395 at either size, move one more point from
  `none_of_these` to `multi` and measure again. Both measured mixes sit
  under that line (0.3839 and 0.3904 at the real size).

Either switch is named in the commit.

`test_counts_for_follows_the_mix` (`tests/test_generate.py:57`) at size
1000 moves to attributed 60, none_of_these 110, multi 130, shared_origin
150 and shared_origin_decoy 150.

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
- `test_generate.py:57`: the counts in section 6.
- The shared-answer ratio test in `test_shared_origin_training.py` (about
  lines 480-504): its docstring says the next raise must move `multi` up.
  This raise does, so the docstring says so, with the new measured ratio.
  The 0.40 cap stays.
- `test_evidence_overlap.py`: `DECLARED` pins eval-to-training evidence
  reuse counts at seed 17, size 8000. Its own docstring says a `CASE_MIX`
  change moves them. Re-measure, and re-pin by hand with a dated comment
  if they move.

**New tests:**

- The oracle tests (section 10). Job 2 is averaged only over the
  workloads gate 1 names, never read off `scoreboard()`.
- The coherence test (section 4).
- No trainable story uses an exam-only origin-read label (section 4).
- No story's `shared_cause` or `local_cause` holds a shared-claim phrase
  (section 3).
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
- `README.md:170-177`: the share, pool and build-size history ("the share
  went to 12% each, the pool … from 24 to 48") gains a dated step for this
  retrain: 15% each, 54 stories, `multi` at 13%.
- `docs/how-training-works.md:92`: the `shared_origin` row's "name the same
  cause on every one", and its share (12% to 15%).
- `docs/how-training-works.md:318`: "it is 12% now" becomes 15%.
- `docs/how-training-works.md:905-910`: the cousin probe writes 54 pairs
  and 108 rows, not 48 and 96 (the same move as `test_probe_cousins.py`).
- `docs/design.md:269-270` and `:284-296`: the two 12% rows, "risen to
  12%", "paid out of `attributed` both times" (this raise is paid out of
  `attributed` and `none_of_these`, and moves `multi` up too), and the
  shared-answer ratio ("about 38 of every 100", "a test fails above 40")
  are re-measured.
- `docs/runbooks/train.md`: line 11 ("about 28 hours"), lines 39 and 65
  ("~2¼ hours"), and lines 83, 87-88 and 133 ("17½ hours", "17h42m",
  "4,292 examples") get this run's measured numbers.
- `docs/model-card.md`: the 0908 v1.24.0 section gains the test hash
  `c2d22b6e…`. Today that hash is recorded only in
  `out/eval/0908/scoreboard.json` (`test_sha256`). The section also gains a
  dated re-pin entry saying the exam moved on 14 rows and the graded view
  did not.
- `contract/PIN.md` "Dataset pin moves": a new dated entry, in the same
  style as the two before it.
- The `propagation.py` module docstring (lines 1-123) and the comment on
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

Both pins move. `FROZEN_253_SHA256` covers rows 1-253, which include all
ten `shared_origin_probe` rows (244-253). `EVAL_SET_SHA256` covers all
263. Both are re-pinned by hand in
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
   1.0, read off `score.scoreboard`. Job 2 = 1.0 on every job-2 workload it
   can grade: those where
   `score._is_job2_keyword_graded(wm, wm["own_cause_keywords"])` is true,
   and those whose `expected_cause` is `none_of_these` (exact match). The
   test averages `score.job2` over exactly those workloads.
   - Do not read job 2 off `scoreboard()`. Its job-2 rate averages every
     job-2 workload, and 4312 of the 7433 in today's train (58%, all
     shared-origin) carry no keywords, so job 2 scores them 0 whatever the
     reply says (out of scope). On a correct dataset that rate reads about
     0.42.
   - Do not use `_is_keyword_graded` either. It feeds a diagnostic
     footnote, not a score.
   - Today, on the keyword-graded workloads: 0.9149 (1990 of 2175 in
     train).
2. **Oracle, exam.** Job 1 = 0.879 (138 of 157); today it is 0.7006 (110
   of 157). The 19 misses are all `contradiction_probe`, which this slice
   does not touch. Job 3 is measured and expected to be 1.0 (today 34 of
   39; the 5 misses are the `none` rows with the shared template).
3. **Length.** Every row fits in 4096 tokens with the real Qwen tokenizer.
   No row is dropped for length.
4. **Tests.** The full suite and ruff pass, including every new test in
   section 7.
5. **Exam footprint.** Exactly the 14 rows above change. The graded view
   hash does not.
6. **Negative control.** The 0908 replay in section 9.
7. **Hand read.** A person reads a sample: two rows per ruled story (both
   twins), two unverified node twins, two plain broken twins, five fixed
   `multi` rows and all 14 changed exam rows.

## 11. The run

1. **Update the host.** The training host's checkout is 63 commits behind `main`.
   Pull, reinstall, and use a fresh `--out`.
2. **Build on both machines.** Run `.venv/bin/kv-dataset --seed 17 --size
   8000` on the workstation and on the training host. The four files (train, val,
   test, manifest) must match byte for byte. If they do not, stop. Diff
   the two manifests, look for a version or config drift between the
   checkouts, and do not train until they match.
3. **Smoke run.** `--limit 32 --epochs 1` on the training host. It must finish
   and write a checkpoint.
4. **Full run.** About 796 steps; the real build sets the count. Launch
   with `nohup env HF_HUB_OFFLINE=1 kv-train --dataset … --out … > …
   2>&1 &`. Time estimate: 0908 took 31.8 hours for 12,577,240 training
   tokens, so this run takes 31.8 hours × (new tokens ÷ 12,577,240). That
   is about 32 to 34 hours. Check it is alive by the change in CPU time
   (`ps -o times=`). If the run dies, follow `docs/runbooks/train.md`'s
   resume section: it covers `--resume` and how to tell a crash from a
   power loss.
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
  cannot check a plain story's origin. But the pairing may read oddly, and
  it has a training cost. 960 plain pairs are built, and at least 15 of
  each story's 20 land in train. Each broken twin pairs a per-row cause
  with a summary that will not call it shared. A model could learn "never
  call a cause shared". The ruled broken twins (about 186 to 190 in train,
  with the `shared` label) teach the other side. §3 gives the reason for
  the choice; gate 7 reads two of these rows by hand.
- **No decoy rate on ruled stories.** Ruled-story rows, both twins, carry
  an empty `decoy_by_workload` for every victim (`dataset/cases.py:877-878`,
  unchanged by this slice). Today that covers 3 exam-only stories. After
  this slice it also covers about 240 ruled pairs, so the decoy-rate
  diagnostic sees none of them.
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

**Take `multi`'s two points from `wrong_attribution` (mix E).** Keep
`attributed` at 7, and set `wrong_attribution` to 9 and `none_of_these`
to 11.

- Cost: one more case moves.
- What you learn: slightly more job-1 rows (2585 workloads against 2519)
  and a plain-story floor of 16 instead of 15.
- Downside: fewer job-2 keyword workloads (2169 against 2286) while job 2
  is also failing. And it moves a case the approved design did not touch.

**Recommendation:** the full slice as written. It is the only option where
every gold answer agrees with the rules the model will run under.
