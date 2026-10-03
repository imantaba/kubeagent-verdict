# Shared-Origin Rewrite (Spec 4b-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the shared-origin family (4 cases, 2,420 of 7,427 rows in
out/dataset-0929) on kubeagent's real pipeline, so every row passes all 50
checker rules with no exemption and every gold says only what its prompt shows.

**Architecture:** Two new Go captures (CLUSTER and REGISTRY), made by the
existing harness in new modes, pin a new pure `dataset/health.py` (the cluster
health block, service issues, network-policy lines) byte for byte. A new
`dataset/stories.py` holds 47 stories as world objects (a broken world and a
healthy world each). A new `dataset/shared_origin.py` runs one world through
`_report_order` → one `gather.gather()` → the rules over every candidate →
`c.build_user_message`, and a new `dataset/gold.py` takes the gold from anchors
in each workload's own lines. cases.py's four builders delegate to it, the
checker loses its exemption and gets a B7 rewrite, and generate.py keeps its
loop with new sizes.

**Tech Stack:** Python 3 (pytest, ruff, PyYAML); Go (the capture harness, run
from a `git archive` copy of kubeagent v1.24.0); YAML fixtures; sha256 pins.

**Spec:** `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md`

## Global Constraints

- Bars: `JOB1_BAR` 0.9, `JOB2_BAR` 0.7, `JOB3_BAR` 0.9. They never move.
- No change to `src/kubeagent_verdict/evals/score.py` or `src/kubeagent_verdict/contract.py`, and no new must-not word.
- The checker rule count stays 50.
- One `salt` per shared-origin pair, drawn from the main stream.
- The train/val split stays a hash of the group.
- The exam's 229 other-family rows stay byte-identical, and the exam stays 249 rows.
- No 0920 replay.
- The kubeagent repo (/home/ubuntu/git/kubeagent) is read-only; its status stays ` M .gitignore`. Captures run only from a `git archive v1.24.0` copy in scratch.
- `multi` keeps `origin_read_label` (244 rows) and its prompt bytes do not change.
- The ruled share stays 1 pair in 5 (`i % 5 == 4`).
- The 22 old capture dumps (`tests/fixtures/gather_go/`, `tests/fixtures/gather_go_logs/`) stay byte-identical.
- Never run any test with `-update` or `--update`. TDD: write the failing test, watch it fail, then implement.
- Python tests: `env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider <paths>` (written `PYTEST <paths>` below).
- Lint: `.venv/bin/ruff check --ignore EXE002 .` prints `All checks passed!` before every commit.
- Commit: `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "<msg>"` (written `COMMIT "<msg>"` below). Add files by name. Never `git add -A` or `git add .`. Never commit `.gitignore` or `train-v2.log`. No AI attribution in any commit, file or doc.
- Never touch existing `out/` contents (reading is fine), `.venv`, or any kind cluster. Never name the training host in a tracked file.
- Docs are written in simple voice: short sentences, plain words, numbers explained.
- Run every command from `/home/ubuntu/git/kubeagent-verdict` (prefix `cd /home/ubuntu/git/kubeagent-verdict &&`; the shell's working directory resets).

## Rulings

Each ruling settles a choice the spec leaves open. Implementers follow them;
the controller records any new ones in the SDD ledger.

1. **`propagation.py` stays unchanged.** `multi` still uses it for its
   origin text. Cost if wrong: a dead-code cleanup later; no row changes.
2. **Stories live in a new `dataset/stories.py`**, as frozen dataclasses
   `VictimText`, `World` and `Story` (fields below in Task 3). `trainable()`
   returns 41 stories (the 35 P first in key order, then the 6 R in today's
   ruled order); `exam()` returns the 6 exam stories in `all_scenarios` order.
   Cost if wrong: moving data into another module; no behavior change.
3. **A new pure `dataset/health.py`** holds the Python port of kubeagent's
   clusterhealth, svchealth and netpolicy pieces: `Condition`, `Node`,
   `DownNode`, `assess`, `go_duration`, `Service`, `EndpointSlice`,
   `Backend`, `service_issues`, `annotate_endpoint_cause`,
   `selecting_policies` and `CONDITION_TYPES`. It imports only `contract`,
   `gather.safetext_line` and the standard library (no cycle: `gather`
   imports `contract`, `objects` and `rules`, never `render` or `health`).
   Cost if wrong: one more module; the byte tests pin its output either way.
4. **`health.assess` is the spec §3 function** `cluster_health(nodes, leases,
   now, threshold, workloads)`. Leases are a field of `Node` and "now" is
   implied by `lease_age_ms`. `render.cluster_health(workloads, reads)` stays
   as `multi`'s wrapper with the same signature and the same bytes
   (T = max(3, named+1), the (name, kind) sort, the ValueError), rebuilt on
   `health.assess` with synthetic nodes. Cost if wrong: a rename.
5. **Staleness is judged on raw milliseconds before rounding:** a lease is
   stale when `lease_age_ms > threshold_ms`; only the printed age is rounded
   by `go_duration`. 40,000 ms gives no line; 40,400 ms gives "40s". Cost if
   wrong: the CLUSTER byte test fails in Task 2, where it is cheap to fix.
6. **The new pipeline builds its prompt with
   `c.build_user_message(health_block, None, "", service_issues, workloads,
   reads)` and then `render.check_prompt_size(user,
   entry_or_scenario_key=group)`.** It never calls `cases._user_message`,
   which derives the health block from candidates. Cost if wrong: a health
   block that disagrees with the world; the pipeline tests catch it.
7. **`gold.own_lines` is an exact port of score.py `_own_blocks`**, with an
   equality test over every built row. The dataset never imports
   `evals.score` outside tests. Cost if wrong: a key the grader cannot see;
   the equality test catches it.
8. **Row meta.** Keeps: `case`, `origin`, `blast_radius`, `scope_value`,
   `expected`, `label`, `workloads`, `decoy_by_workload`, and
   `shared_claim_phrases` on the decoy probe; `decoy_causes` is `[]`.
   Drops: `origin_read_label`, `distractor_cause`, `wrong_summary_phrase`,
   `expected_confidence`. Cost if wrong: a later spec re-adds a field; the
   grader reads only kept fields.
9. **A PVC candidate exists only when its PVC is flagged.** The healthy world
   has no origin candidate. Cost if wrong: a healthy world that names the
   origin and so leaks the answer; the worlds-differ test catches it.
10. **Node count.** T is drawn in `[max(3, named+1), 5]`. The node list is
    `sorted(set(victim nodes) | {origin node})`, padded from `names.NODES`
    (worker-1 … worker-5) in order until it holds T names. Cost if wrong: a
    header total the B7 rewrite rejects; Task 7's mutations catch it.
11. **Rng discipline.** Every draw for a pair happens before any branch on
    the world, so the two twins draw the same values. Cost if wrong: twins
    that differ in more than the world; the twin test catches it.
12. **Decoys come from world objects only.** The new pipeline makes no
    `render.draw_ending` decoys. `decoy_by_workload[w]` is the causes of
    the candidates the rules ruled out or refuted for `w` — the same set
    `gold.anchor_lines` excludes, so a gold never names a decoy. This is
    stricter than `multi`'s "not the workload's own" (cases.py:753): on a
    broken world the origin candidate is the answer, never a decoy. Cost if wrong: fewer decoy rows; the three-verdict floor
    test (`tests/test_shared_origin_floor.py:72`) catches it.
13. **A down node gives every flagged workload a candidate**, ruled out when
    the workload's pod is not on that node. Cost if wrong: fewer
    three-verdict rows; same floor test.
14. **The fresh node describe** uses `rules._node_conditions` from the Fresh
    fields (`ready`, `ready_reason`, `ready_message`, `unschedulable`,
    `disk_pressure`, `taints`). Memory and PID pressure show only in the
    health block. Only down nodes become candidates. Cost if wrong: a
    describe kubeagent would not print; the CLUSTER capture pins the format.
15. **Story data.** The plan gives full code for 3 pilots (node-not-ready,
    coredns-down, networkpolicy-deny-all). The other 44 stories get a value
    table plus an authoring procedure, guarded by tests that run over every
    story. Cost if wrong: an implementer's wording choice in a victim text;
    the guard tests bound it.
16. **`_HEALTH_SYSTEM`** becomes
    `^  system kube-system/(\S+) (?:(\d+)/(\d+) )?(.+)$`; the optional
    count group is tried first because the regex engine tries it greedily.
    Cost if wrong: a system line with counts parsed as a status; Task 7's
    test catches it.
17. **"Both fixtures stay within the 8-read budget"** (spec §5) is read as:
    the gather's trail never holds more than 8 reads, which the harness
    already asserts. A step the budget skips is allowed and shows in
    07-trail.txt. Cost if wrong: one fixture trimmed to fewer workloads.
18. **Gold lives in a new `dataset/gold.py`** (own lines, anchors, gold,
    confidence, label, summaries), separate from the pipeline in
    `dataset/shared_origin.py`. Cost if wrong: a merge of two modules.
19. **Gold is per world.** Each `VictimText` carries a `broken` answer and an
    optional `healthy` answer (`stories.Answer`: anchor, cause, keys,
    confidence, rationale, link). In the broken world the anchor must sit in
    an event, a finding's evidence, a candidate line or a describe line; a
    log-cause label never carries `link=True`. In the healthy world a victim
    is named only when its own healthy lines show its own cause; otherwise
    it is `none_of_these`, and it never names the origin. An origin row is
    named only when its own lines show why (likely named: coredns via the
    config-parse log label, csi-controller-unschedulable via
    FailedScheduling, network-operator and csi-controller-oomkilled via
    OOMKilled; `none_of_these`: cert-manager, external-secrets,
    metrics-server, pod-identity-webhook, csi-node-driver-crashed,
    namespace-egress-proxy). Expected label split over the 38 P stories: 13
    flip to "shared" (exam: coredns-down, networkpolicy-deny-all), 11 have
    exactly one linked victim (exam: node-disk-pressure), 14 have none.
    Estimates over 135 cells per world: broken named 40 / none 70 / decided
    25; healthy named 46 / none 86 / decided 3; the exam's 32 victim cells
    9 named / 13 none / 10 decided. These are estimates, not test bars.
    Cost if wrong: a gold that says more than its prompt; the pool check
    and the cross-world key test catch it.
20. **`shown_origin` is the tail of the "shared" summary's first line.**
    A "shared" summary starts "N workloads share one upstream cause:
    <shown_origin>." with the story's `shown_origin` formatted by
    `shared_origin._sub` (Task 4's `gold_for`).
    Cost if wrong: job 3 still grades the label, so only the summary's
    wording changes.
21. **N in the summary.** A "shared" summary's N is the larger of the
    linked victims and the rules-confirmed rows. A "none" summary's N is
    every row, the origin row included. The gold tests and the pool check
    enforce both. Cost if wrong: a count one off in a summary line; job 3
    does not grade N.
22. **Which pool each builder uses.** `multi`'s `healthy_origin` keeps
    `propagation.trainable_scenarios()` (Ruling 1). The shared-origin loop
    and the cousin probe use `stories.trainable()`. The exam and the wide
    probe use `stories.exam()`. The exam keeps today's shape: 6 full rows,
    plus a `victims=2` row for each of the 4 exam stories with 3+ victims,
    so 10 broken and 10 healthy. Cost if wrong: the exam size moves off
    249, which `test_the_eval_set_is_two_hundred_and_forty_nine_rows`
    catches.
23. **Every down origin node carries the NotReady text**
    (`objects.NOT_READY_REASON` / `NOT_READY_MESSAGE`). The 3 R node
    stories are confirmed by the rules in the broken world, and
    unconfirmed in the unverified twin. Cost if wrong: a node story with
    no confirming read, which the "R stories confirm in broken only" test
    catches.
24. **A victim's `c.Finding.log_cause` stays "".** The log-cause label
    reaches the prompt only through the gather's log read, as in
    kubeagent. Cost if wrong: the label printed twice; checker rule E-family
    would flag it.
25. **The rules' "separate" maps to "none".** The family never carries
    the label "separate"; `gold.label_for` returns "shared" or "none" only.
    Cost if wrong: job 3's "separate" bucket gets family rows; the label
    tests catch it.
26. **Import direction.** `shared_origin.py` and `gold.py` never import
    `cases` or `generate`. `cases` wraps them into `Example`; the builder
    names and keyword arguments are kept, and `p` becomes a
    `stories.Story`. `draw`/`build` replaces the spec's single
    `build(story, rng, …)`, so that both twins share one draw by
    construction. Cost if wrong: an import cycle, caught at import time.
27. **Test pickers skip the family by case prefix.** A test in another
    file that picks "some row" from `generate.generate` (test_checker.py's
    pickers, `_source`) skips every case that starts with
    `shared_origin` through one helper, `_family(case) -> bool`. Cost if
    wrong: a picker lands on a family row and pins its bytes; the next
    family change breaks an unrelated test.
28. **Who owns which mix test.** Task 8 owns
    `tests/test_shared_origin_floor.py` (rewritten whole) and the
    whole-family checks appended to `tests/test_shared_origin_pool.py`.
    Task 9 does not touch either file. Cost if wrong: two tasks edit one
    file and the second undoes the first.
29. **Where balance and ceiling are measured:** over the train split at
    the runbook recipe (seed 17, size 8000), after `generate.split` and
    `generate.drop_held_out`, because that is the pile the model reads.
    Balance compares the `none_of_these` share of verdicts in
    `shared_origin` rows (broken world) with the share in
    `shared_origin_decoy` rows (healthy world). The ceiling counts every
    verdict of every case in that split. Cost if wrong: a share measured
    on a pile the model never reads; the bars do not move either way.
30. **The decided rationale is `render.rule_rationale`.** Task 4 moves
    `cases._rule_rationale` and `_NOUN` to render.py, body unchanged, and
    leaves `cases._rule_rationale = render.rule_rationale` so every old
    caller keeps working. `gold.py` may import `render`, never `cases`
    (Ruling 26). Cost if wrong: two copies of one sentence that drift.
31. **The unverified twin.** Its rows are decided with outcome
    "unverified" (job 1, `rules.decide` at rules.py:325-330), its label is
    "none" (`rules.shared` counts confirmed results only), and
    `shared_origin.build` raises `ValueError` when `unverified=True` and
    the world has no down node. The healthy twin never takes
    `unverified`. Cost if wrong: an unverified row graded as job 2, or a
    "could not check" world with nothing to check.
32. **Pair identity is `Example.group`.** The broken world may add an
    origin row, so the two halves' workload sets can differ (H1). The
    group joins the victims only and is the same in both worlds.
    `_shared_origin_twin_pairs`, the cousin and wide probe tests, and the
    training-pair tests all pair on it. Cost if wrong: pairs that never
    match, so the paired checks pass on nothing.
33. **Summary lines are joined with "\n"** (H6). "N workloads are failing
    for separate reasons." is said only in a healthy world where every row
    is named or decided and no two causes are equal (the spec's "named"
    at its summary rule means named or decided). Every other "none"
    summary says the rules did not confirm one cause on two or more.
    Cost if wrong: job 3 still passes ("none" needs only no claim), but a
    summary claims more than its rows show.
34. **`shared_origin.build` is a second checked prompt funnel.**
    `tests/test_cases.py`'s prompt-size test walks
    `_FUNNELS = {("cases.py", "_user_message"), ("shared_origin.py", "build")}`
    and requires each to call `render.check_prompt_size`. Cost if wrong: a
    family prompt over the byte cap reaches a training row.
35. **Twins need only differ.** Old tests asserted that both halves of a
    pair carry the same origin read label. That label is gone. The new
    rule (spec §4 "Worlds differ"): the two prompts differ in at least one
    printed line. Read labels may differ between worlds (H5). Cost if
    wrong: a pair test that fails on correct rows.
36. **Twin scoring in the decoy probe** filters the twin's verdicts to
    the decoy row's own workloads before it scores, because the broken
    twin may carry an origin row the decoy has not (H1). Cost if wrong: a
    paired score that counts a workload one half never asked about.
37. **WEAK_PAIRS** (`tests/test_answer_keys.py:241`): the family's
    entries are regenerated from the new golds by the test's own
    procedure. If the total count grows, the task report says so with the
    new pairs; the list is never extended silently and no bar moves.
    Cost if wrong: a weak pair hidden inside the regenerated list.
38. **"No rule passes by looking at nothing" is pinned from the first
    build** (spec Tests §2). Task 8 runs `checker.check_row` over every
    family row, sums `Report.inspected` per rule, and pins the two lists
    as literals. The must-inspect set has 30 rules: the spec's nine
    (ANS-2, D3, E6, E7, E8, E9, B5, B7, TXT-IS15) plus the 23 rules that
    inspect at least one item of the old family today (A1–A6, ANS-1,
    ANS-2, B2, B3, B4, B7, B8, C1, C2-vocab, C3, C4-order, D1, F1, F2,
    F3, TXT-IS8, TXT-POD; measured 2026-10-03 over the 2420 family rows
    of `generate(17, 8000) + test_set()`, 0 violations). The spec's
    "the 10 rules that fire today" is read as these 23: no rule fires on
    the old family, and 23 read it, so the superset drops no rule the
    old family exercised. If a must-inspect rule inspects nothing, the
    task stops with DONE_WITH_CONCERNS; it never moves the rule to the
    other list. Cost if wrong: a rule that passes the family by reading
    none of it, or (the other way) a pin stricter than the spec asked,
    which costs one DONE_WITH_CONCERNS report.
39. **The cross-world key check lives in the pool file** (Task 8): a
    victim's named keys must fail its other world's gold cause and every
    decoy cause in its own row, matched with `score._keywords_match`.
    Cost if wrong: a gold the model can pass by naming the other world's
    cause.
40. **The Task 7 header test keeps its :1140 assert** unchanged:
    `{"multi", "multi_misattribution_probe", "wrong_attribution"} <= set(checked)`.
    The family's R rows are job 1, and whether a P row shows a candidate
    depends on its story, so the family is not required there. Cost if
    wrong: a header test that fails on a story with no candidate.
41. **Tests may call two underscore helpers**: `gold._summary` and
    `score._keywords_match` (Task 9 part C). The old tests called
    `cases._shared_origin_summary` and `cases._rule_rationale` the same
    way, and Task 4's own tests call `score._own_blocks` and
    `gold._summary`. No production name changes for a test. Cost if
    wrong: two tests to edit if a helper is renamed.
42. **A story fact a test needs is checked before the test is written**
    (Task 9 part C, Steps C2 and C9). If no healthy world earns "N
    workloads are failing for separate reasons." (Ruling 33), or no kept
    family row earns it, the implementer stops with DONE_WITH_CONCERNS.
    That is a question about the stories, not about the test, so no test
    is left red and none is loosened. Cost if wrong: one stop.
43. **A pin the plan cannot state is measured, never guessed** (Task 9
    parts B and C). `EXAM_KEYWORDED`, `DENYING_ROWS` and
    `EXAM_PROBE_LABELS` ship with a starting value, and Step C9 writes the
    measured value under checks taken from plan facts: every R probe is
    "shared"; `coredns-down` is "shared" at full width and "none" at
    width 2; `networkpolicy-deny-all` is "shared" at full width; both
    labels appear; every decoy probe is "none". The two `DECLARED` entries
    in `tests/test_evidence_overlap.py` are written the same way by Step
    B6. A failed check stops the task; the pin is never moved to pass it.
    Cost if wrong: a pin that records what the build did, bounded by
    those checks.
44. **A broken "none" summary has 3 or 4 lines** (Task 9 part C, Step
    C6): the header plus one line per row, at most 3 (Ruling 33). Every
    build has 2 or more rows, because `draw` refuses a width below 2.
    Step C2 prints every gold summary's line count, so a one-row build
    would show there first. Cost if wrong: one bound to loosen.
45. **`DECLARED` in `tests/test_evidence_overlap.py` belongs to Task 9
    part B.** Step B6 rewrites its two family entries and the comment
    above them; no other part edits that dict. Cost if wrong: two parts
    editing one literal, and a merge conflict inside the task.
46. **The origin read no longer has to come first** (Task 9 part B). The
    real gather orders its reads per workload, so
    `test_the_origin_is_read_once_not_once_per_victim` asserts that the
    origin is read once, and no longer that it leads. This check is lost
    on purpose: it is the gather's behaviour, and the gather is
    kubeagent's. Cost if wrong: an origin read placed late in a prompt,
    with no test to notice.
47. **Task 9 works from Task 7's failure list.** Before Task 9 starts,
    the controller compares the tests Task 7's report names as broken
    with the tests Task 9's four parts rewrite, delete or re-pin. A test
    on Task 7's list that no part covers is added, under the deletion
    rule, to the part that owns its file; a test outside every part's
    files goes to part D. Cost if wrong: a red test after Task 9 that no
    step names.
48. **Task 11's documentation choices.** (a) Its scripts live in
    `/tmp/kv-task11`, outside the repo, and are never committed: they
    feed one another and are too long for one heredoc, and a folder in
    the repo would show in Task 12's tree checks. (b) The 4a
    `named_decoy` raw-answer item is not added to the 4b-4 list: the
    spec's lists (:732-760) do not name it, and adding it widens scope.
    (c) One dated note follows the long "twin" passage in
    `docs/how-training-works.md`, beyond the spec's line anchors. It
    says only what the change already implies. (d) The weak-pair count
    is read from the regenerated `WEAK_PAIRS`, not checked against a
    printed number: the list is the source. (e) The "14 victims" note
    cites the spec's 20 (:69, :639); the old gold is gone and cannot be
    counted again. (f) A doc says "byte for byte the same" only when
    Task 11's Step 5 measures it true. Cost if wrong: a docs paragraph
    to edit.
49. **Task 9 part D's choices.** (a) Its measured numbers and edit
    scripts live in `/tmp/kv-t9d/`, outside the repo, and are never
    committed, for the reason in Ruling 48(a). (b) A `WEAK_PAIRS` list
    that grows past 21 does not stop the commit: the report names each
    new pair and the list is regenerated, never trimmed (Ruling 37). The
    weak pairs are Spec 4b-4's. (c) `grade_job2=False` stays in
    `tests/test_oracle.py::_gold_results`: the pools are still measured
    by `_job2_gate` and `_job2_keyword_only`, so the measurement path
    does not change. (d) Step D1 stops on any failing name outside its
    34, unless the dispatch added that name under Ruling 47. (e) The pool
    check "8000 = 5600 + 2400" is a hard stop, because the spec's mix
    (:495) keeps the family at 15% of 8,000. (f) The one rewrite is the
    helper `_name_the_decoy_bot`: its fallback was `none_of_these`, which
    is now a right answer for some workloads, so it becomes
    `(no decoy offered)`. Cost if wrong: (b) a longer weak list reaching
    4b-4; the rest, one step to redo.
50. **Task 9 part A's choices.** (a) Every trainable R story keeps
    propagation's three victims. Task 5's table says 3, and the PVC
    stories' ContainerCreating victim is re-authored as Pending, because
    an unbound claim never reaches a mount. A third victim that fails
    `test_r_stories_confirm_in_broken_only` is a stop, never a drop.
    (b) `test_no_two_trainable_scenarios_share_a_local_cause` is deleted:
    `local_cause` was an entry in the made-up menu. (c)
    `test_every_exam_layout_has_a_trained_floor` and
    `test_every_held_out_read_kind_has_a_trained_cousin` are kept, with
    `EXAM_LAYOUT_FLOORS` and `_teaches_layout`: they read only the
    `propagation` pool, which `multi` still trains on. Cost if wrong:
    (a) one story re-authored in Task 5; (b) and (c) one test to restore
    or delete.

## Review Focus

1. **A message-only NotReady whose 120-rune cut lands next to a non-ASCII
   rune** must be cut by runes, not bytes, and end with "…". Test:
   `test_notready_message_cut_counts_runes` in Task 2.
2. **A Ready node with a stale lease** prints a lease line but still counts
   as Ready in the header's R/T. Test:
   `test_stale_lease_node_still_counts_ready` in Task 2.
3. **A Job or CronJob system status with spaces** ("BackoffLimitExceeded
   (3 of 3 failed)" style) must render with no counts and parse whole under
   the new `_HEALTH_SYSTEM`. Tests: `test_job_system_line_has_no_counts` in
   Task 2 and `test_health_system_status_may_hold_spaces` in Task 7.
4. **A refused read on the origin row** (its events or log read fails) must
   not flip a P broken world's label to "none": the label counts victims'
   own anchors, not the origin's. Test:
   `test_refused_origin_read_keeps_shared_label` in Task 4.
5. **The 8-read budget leaving a victim's anchor unread** must give that
   victim `none_of_these` and drop it from N, and the label must follow N
   (2+ → "shared", else "none"). Test:
   `test_budget_cut_victim_falls_back_to_none_of_these` in Task 4.

## File Map

Create:
- `tests/fixtures/gather_fixture_cluster.yaml` — the CLUSTER fixture (n01–n16; n16 carries the three detector conditions and prints no line).
- `tests/fixtures/gather_fixture_registry.yaml` — the REGISTRY fixture.
- `tests/fixtures/gather_go_cluster/` and `tests/fixtures/gather_go_registry/` — the eleven Go dumps (00–10) per fixture, written by the harness.
- `src/kubeagent_verdict/dataset/health.py` — the pure health/service/netpol port.
- `src/kubeagent_verdict/dataset/stories.py` — 47 stories as data.
- `src/kubeagent_verdict/dataset/shared_origin.py` — one world through the real pipeline.
- `src/kubeagent_verdict/dataset/gold.py` — own lines, anchors, gold, label, summaries.
- `tests/test_health.py`, `tests/test_stories.py`, `tests/test_shared_origin_pipeline.py`, `tests/test_shared_origin_gold.py`.
- `tests/test_shared_origin_pool.py` — every family gold scored by the real grader (Task 7), and the whole-family checks (Task 8).

Modify:
- `contract/capture/kv_capture_test.go.txt` — a mode replaces `golden bool`; new optional fixture fields; cluster and registry wiring.
- `tests/test_gather_byte_equal.py` — 4 folders, the folder guard, the old-dump hashes, and the CLUSTER run path.
- `src/kubeagent_verdict/dataset/render.py:239-346` — `cluster_health` rebuilt on `health.assess` (Task 2); `_NOUN` and `rule_rationale` appended (Task 4).
- `src/kubeagent_verdict/dataset/cases.py` — `_NOUN` and `_rule_rationale` (:55-75) become one alias line (Task 4); the 4 builders delegate; `_render_shared_origin` (:920-1123), its helpers (`_propagation_names`, `_victim_finding`, `_shared_origin_row`, `_shared_origin_summary`, `_SharedOrigin`) and the `origin_read_label` writes (:1152, :1190) go (Task 7).
- `src/kubeagent_verdict/dataset/checker.py` — :17-31 docstring, :179-196 exemption sets, :232 `_HEALTH_SYSTEM`, :956-1035 `_b7`, :2049-2063 skip.
- `src/kubeagent_verdict/dataset/generate.py` — :20-21 import, :99 comment, :110-115 comment, :134 import, :246-283 the loop, :514-576 the exam probes, :579-661 `_shared_origin_twin_pairs` and the wide and cousin probes.
- `tests/test_cases.py` (the prompt-size funnel test, Task 3), `tests/test_checker.py` and `tests/test_generate.py` (Task 7, including the `OTHER_FAMILIES_SHA256` guard on the 229 other exam rows).
- `tests/test_shared_origin_floor.py` (rewritten whole) and `tests/test_shared_origin_training.py:1236-1290, :1391-1476` (Task 8).
- The old family tests (Task 9): `tests/test_shared_origin_training.py` (the rest), `test_propagation.py`, `test_healthy_evidence.py`, `test_evidence_overlap.py`, `test_ruled_scenarios.py`, `test_probe_cousins.py`, `test_probe_wide.py`, `test_shared_origin_keywords.py`, `test_shared_origin_decided.py`, `test_shared_origin_training_pair.py`, `test_shared_origin_decoy_probe.py`, `test_score.py`, `test_oracle.py`, `test_answer_keys.py`, `test_generate.py`.
- The hash pins and the banked exam (Task 10): `tests/test_shared_origin_training.py:1036, :1177`, `tests/test_exam_graded_view.py` (docstring and :215), `tests/test_exam_prompt_stability.py` (docstring and `BANK` :52).
- The docs (Task 11): `contract/PIN.md`, `docs/model-card.md`, `docs/how-training-works.md`, `docs/design.md`, `README.md`. `docs/runbooks/train.md` is checked and not edited.

Build (Task 10, never committed; `out/` is gitignored):
- `out/dataset-<MMDD>`, named for the build day. No existing `out/` folder is touched.

Task 12 creates and modifies nothing: it runs the Done-when checks and reports them.

---

### Task 1: Capture harness modes, the CLUSTER and REGISTRY fixtures, and the capture record

**Files:**
- Modify: `contract/capture/kv_capture_test.go.txt` — run doc :1-60; types :113-242; `kvScanNode` :278-292; `TestCaptureVerdictGolden` :750-768; `kvCapture` :774 onward (lease loop :818-850, service issues :810-813, `clusterhealth.Assess` :1033, `wantCuts` :1168-1173, `golden` branches :1230, :1489-1509).
- Create: `tests/fixtures/gather_fixture_cluster.yaml`, `tests/fixtures/gather_fixture_registry.yaml`.
- Create (by the capture, copied back): `tests/fixtures/gather_go_cluster/00-fixture.json` … `10-prompt.txt`, `tests/fixtures/gather_go_registry/00-fixture.json` … `10-prompt.txt`, and a `README.md` in each folder (one paragraph: which fixture, which mode; the format is `tests/fixtures/gather_go/README.md`'s).
- Modify: `tests/test_gather_byte_equal.py:52-60` (folders), `:98-130` (`load_fixture` keys), `:466-491` (parametrization, guard).
- Modify: `contract/PIN.md` (new section "Capture record (v1.24.0, cluster and registry capture)").

**Interfaces:**
- Consumes: nothing from this plan.
- Produces:
  - Fixture YAML keys (all optional; old fixtures do not use them):
    - `nodes[i].conditions`: list of `{type, status, reason, message}`. When set, these are the node's scan-time conditions, in the order given, and `scan_reason` no longer builds them: it holds the reason kubeagent's `DownNodes` must give the node (`NotReady`, `no kubelet lease`, `kubelet not heartbeating`), or `""` for a node that is not down. The harness's "the scan saw the nodes the fixture says it saw" self-check then checks it, in every mode.
    - `nodes[i].unschedulable`: bool (cordoned).
    - `nodes[i].lease`: `""` (old behavior, from `scan_reason`), `"renewed"`, `"missing"` or `"no_renew"`; `nodes[i].lease_age_ms`: int, used with `"renewed"`.
    - `workloads[i].pods[j].labels`: map; `workloads[i].pods[j].ready`: bool.
    - `services`: list of `{namespace, name, type, selector, annotations, lb_ingress}`.
    - `endpoint_slices`: list of `{namespace, service, ready}`; `ready` is a list of `"true"`, `"false"` or `"unset"`, one per address.
    - `backends`: list of `{namespace, name, kind, labels, desired}`.
    - `network_policies`: list of `{namespace, name, pod_selector}`.
  - In mode `cluster`, `service_issues` must be empty: the harness computes them. In every other mode `services`, `endpoint_slices`, `backends` and `network_policies` must be empty.
  - Python constants in `tests/test_gather_byte_equal.py`: `MAIN`, `LOGS`, `CLUSTER = ("gather_fixture_cluster.yaml", "gather_go_cluster")`, `REGISTRY = ("gather_fixture_registry.yaml", "gather_go_registry")`, and `FOLDERS = (MAIN, LOGS, CLUSTER, REGISTRY)`.

- [ ] **Step 1: Write the failing Python tests (loader + folder guard)**

In `tests/test_gather_byte_equal.py`, after `LOGS = …` add:

```python
CLUSTER = ("gather_fixture_cluster.yaml", "gather_go_cluster")
REGISTRY = ("gather_fixture_registry.yaml", "gather_go_registry")
FOLDERS = (MAIN, LOGS, CLUSTER, REGISTRY)
```

Change the dump-0 test's parametrization to `FOLDERS`, add REGISTRY to the byte test (CLUSTER joins it in Task 2, once `health.py` exists), and add the guard:

```python
@pytest.mark.parametrize("fixture, folder", FOLDERS)
def test_dump0_is_the_fixture_as_python_loads_it(fixture, folder):
    got = load_fixture((FIXTURES / fixture).read_text(encoding="utf-8"))
    want = json.loads((FIXTURES / folder / "00-fixture.json").read_text(encoding="utf-8"))
    assert got == want


@pytest.mark.parametrize("dump", DUMPS)
@pytest.mark.parametrize("fixture, folder", [MAIN, LOGS, REGISTRY])
def test_the_dump_matches_kubeagent_byte_for_byte(fixture, folder, dump):
    ...  # body unchanged


def test_every_capture_folder_is_checked():
    """A gather_go* folder no test reads would be a capture nobody checks."""
    on_disk = {p.name for p in FIXTURES.iterdir() if p.is_dir() and p.name.startswith("gather_go")}
    assert on_disk == {folder for _, folder in FOLDERS}


def test_the_old_dumps_are_unchanged():
    """The 22 old dump files are the v1.24.0 main and logs captures. The new
    modes must not move a byte of them."""
    want = {  # sha256 of each file, taken from git before Task 1 (fill from Step 2)
    }
    got = {f"{folder}/{name}": hashlib.sha256((FIXTURES / folder / name).read_bytes()).hexdigest()
           for _, folder in (MAIN, LOGS) for name in ("00-fixture.json", *DUMPS)}
    assert got == want
```

Add `import hashlib` at the top.

- [ ] **Step 2: Pin the old dumps' hashes before anything changes**

Run: `cd /home/ubuntu/git/kubeagent-verdict && for d in gather_go gather_go_logs; do for f in 00-fixture.json 01-order.txt 02-events.txt 03-candidates.txt 04-nodes.txt 05-pvcs.txt 06-logs.txt 07-trail.txt 08-bundle.txt 09-decide.txt 10-prompt.txt; do printf '        "%s/%s": "%s",\n' $d $f $(git show HEAD:tests/fixtures/$d/$f | sha256sum | cut -d' ' -f1); done; done`

Paste the 22 printed lines into `want` in `test_the_old_dumps_are_unchanged`.

- [ ] **Step 3: Extend `load_fixture` for the new optional keys**

In `load_fixture` (:98), accept the new keys and refuse anything else. Node keys: required `name`, `scan_reason`, `fresh`; optional `conditions`, `unschedulable`, `lease`, `lease_age_ms`. Pod keys: required `name`, `node`, `claims`; optional `labels`, `ready`. Top-level optional: `services`, `endpoint_slices`, `backends`, `network_policies`, each a list of mappings with exactly the keys in Interfaces. A condition's `type` must be one of the seven types kubeagent's fixtures use: the kubelet's `MemoryPressure`, `DiskPressure`, `PIDPressure`, `Ready`, and the node-problem-detector's `NetworkUnavailable`, `ReadonlyFilesystem`, `CorruptDockerOverlay2` (Task 2's `health.CONDITION_TYPES` holds the same seven); `lease` one of `""`, `renewed`, `missing`, `no_renew`. Use the existing `_keys(where, value, required, optional)` helper for every mapping, as the current loader does for `fresh`.

- [ ] **Step 4: Run the tests to see them fail**

Run: `PYTEST tests/test_gather_byte_equal.py`
Expected: FAIL — `test_every_capture_folder_is_checked` (folders missing) and the dump-0/byte tests for CLUSTER and REGISTRY (`FileNotFoundError`). `test_the_old_dumps_are_unchanged` PASSES.

- [ ] **Step 5: Add the mode to the harness**

In `kv_capture_test.go.txt`, add after the imports:

```go
// kvMode says which fixture a capture runs and what it checks.
type kvMode string

const (
	kvModeMain     kvMode = "main"     // writes the golden files and gather_go/
	kvModeLogs     kvMode = "logs"     // gather_go_logs/: every log-loop action
	kvModeCluster  kvMode = "cluster"  // gather_go_cluster/: health, services, netpols
	kvModeRegistry kvMode = "registry" // gather_go_registry/: every registry outcome
)
```

Replace the `golden bool` parameter of `kvCapture` with `mode kvMode`, and every `if golden` with `if mode == kvModeMain`. `TestCaptureVerdictGolden` becomes:

```go
func TestCaptureVerdictGolden(t *testing.T) {
	dir := os.Getenv("KV_GOLDEN_DIR")
	if dir == "" {
		t.Skip("KV_GOLDEN_DIR not set")
	}
	runs := []struct {
		env, want, dump string
		mode            kvMode
	}{
		{"KV_FIXTURE", "tests/fixtures/gather_fixture.yaml", "gather_go", kvModeMain},
		{"KV_FIXTURE_LOGS", "tests/fixtures/gather_fixture_logs.yaml", "gather_go_logs", kvModeLogs},
		{"KV_FIXTURE_CLUSTER", "tests/fixtures/gather_fixture_cluster.yaml", "gather_go_cluster", kvModeCluster},
		{"KV_FIXTURE_REGISTRY", "tests/fixtures/gather_fixture_registry.yaml", "gather_go_registry", kvModeRegistry},
	}
	for _, r := range runs {
		path := os.Getenv(r.env)
		if path == "" {
			t.Fatalf("%s must name %s", r.env, r.want)
		}
		r := r
		// The main run writes the golden files; the others only their dumps.
		if !t.Run(string(r.mode), func(t *testing.T) { kvCapture(t, path, dir, r.dump, r.mode) }) {
			return
		}
	}
}
```

`wantCuts` becomes `map[kvMode]int{kvModeMain: 0, kvModeLogs: 1, kvModeCluster: 0, kvModeRegistry: 0}[mode]`. The logs self-checks after `return` run only for `kvModeLogs`; add `kvCheckCluster(t, prompt, d4)` and `kvCheckRegistry(t, d9)` branches (Step 7).

- [ ] **Step 6: Add the optional fields and the cluster wiring**

New types (json tags are the YAML keys in Interfaces):

```go
type kvCondition struct {
	Type    string `json:"type"`
	Status  string `json:"status"`
	Reason  string `json:"reason"`
	Message string `json:"message"`
}

type kvService struct {
	Namespace   string            `json:"namespace"`
	Name        string            `json:"name"`
	Type        string            `json:"type"`
	Selector    map[string]string `json:"selector"`
	Annotations map[string]string `json:"annotations"`
	LBIngress   bool              `json:"lb_ingress"`
}

type kvSlice struct {
	Namespace string   `json:"namespace"`
	Service   string   `json:"service"`
	Ready     []string `json:"ready"` // "true", "false" or "unset", one per address
}

type kvBackend struct {
	Namespace string            `json:"namespace"`
	Name      string            `json:"name"`
	Kind      string            `json:"kind"`
	Labels    map[string]string `json:"labels"`
	Desired   int32             `json:"desired"`
}

type kvNetpol struct {
	Namespace   string            `json:"namespace"`
	Name        string            `json:"name"`
	PodSelector map[string]string `json:"pod_selector"`
}
```

Add to `kvFixture`: `Services []kvService `json:"services"``, `EndpointSlices []kvSlice `json:"endpoint_slices"``, `Backends []kvBackend `json:"backends"``, `NetworkPolicies []kvNetpol `json:"network_policies"``. Add to `kvNode`: `Conditions []kvCondition `json:"conditions"``, `Unschedulable bool `json:"unschedulable"``, `Lease string `json:"lease"``, `LeaseAgeMs int64 `json:"lease_age_ms"``. Add to `kvPod`: `Labels map[string]string `json:"labels"``, `Ready bool `json:"ready"``.

`kvScanNode`: when `len(n.Conditions) > 0`, build `node.Status.Conditions` from them in order with `kvCond(corev1.NodeConditionType(c.Type), c.Status, c.Reason, c.Message)` and ignore `n.ScanReason` here (it is only the expected `DownNodes` reason, see Interfaces); set `node.Spec.Unschedulable = n.Unschedulable`. Otherwise keep today's code.

Two existing self-checks after the scan (:1052-1083):
- "The scan saw the nodes the fixture says it saw" stays as it is, in every mode. It now also checks the CLUSTER fixture's `scan_reason` column against `health.DownNodes`.
- "The node list is the named nodes plus healthy unnamed ones, T = max(3, named+1)" runs only when no fixture node has `conditions`. It is the old fixtures' rule; the CLUSTER fixture has 16 real nodes. Wrap both of its `t.Fatalf` checks in `if !kvHasConditions(nodes) { … }`, with

```go
// kvHasConditions reports whether a fixture spells out node conditions,
// so its node count is the cluster's own, not max(3, named+1).
func kvHasConditions(nodes []kvNode) bool {
	for _, n := range nodes {
		if len(n.Conditions) > 0 {
			return true
		}
	}
	return false
}
```

The lease loop (:836-842) becomes:

```go
		switch n.Lease {
		case "":
			if n.ScanReason == "" { // today's rule, unchanged for the old fixtures
				leases = append(leases, kvLease(n.Name, kvNow.Add(-10*time.Second)))
			}
		case "renewed":
			leases = append(leases, kvLease(n.Name, kvNow.Add(-time.Duration(n.LeaseAgeMs)*time.Millisecond)))
		case "no_renew":
			leases = append(leases, coordinationv1.Lease{ObjectMeta: metav1.ObjectMeta{Namespace: "kube-node-lease", Name: n.Name}})
		case "missing":
		default:
			t.Fatalf("node %s: lease %q is not renewed, no_renew or missing", n.Name, n.Lease)
		}
```

with

```go
func kvLease(name string, renewed time.Time) coordinationv1.Lease {
	renew := metav1.NewMicroTime(renewed)
	return coordinationv1.Lease{
		ObjectMeta: metav1.ObjectMeta{Namespace: "kube-node-lease", Name: name},
		Spec:       coordinationv1.LeaseSpec{RenewTime: &renew},
	}
}
```

Service issues: in mode `cluster`, fail if `fx.ServiceIssues` is non-empty; build `corev1.Service`, `discoveryv1.EndpointSlice` (label `kubernetes.io/service-name: <service>`, one endpoint per `ready` entry with `Conditions.Ready` nil for `"unset"`), and the backends, then call `svchealth.Assess` and, after `clusterhealth.Assess` has the down nodes, `svchealth.AnnotateEndpointCause`, exactly as `internal/scan/scan.go` calls them in the archive copy (open scan.go and copy the call shape; do not guess argument order). The pods passed to `AnnotateEndpointCause` are every fixture pod, with `Labels`, `Spec.NodeName = pod.node` and a `Ready` condition from `ready`. In mode `cluster`, also call `netpolicy.Annotate` on `wl` with the fixture's network policies and pods, in the place scan.go calls it. In every other mode, fail if any of the four new top-level lists is non-empty.

- [ ] **Step 7: Add each new mode's self-checks**

```go
// kvCheckCluster fails unless the prompt shows every line the CLUSTER
// fixture exists to capture.
func kvCheckCluster(t *testing.T, prompt string) {
	t.Helper()
	for _, s := range []string{
		"Cluster health (P1): DEGRADED — 11/16 nodes Ready.",
		"  node n01 NotReady: KubeletNotReady — ", "…\n",
		"  node n02 NotReady: NodeStatusUnknown — Kubelet stopped posting node status.",
		"  node n03 NotReady: PLEG is not healthy",
		"  node n04 NotReady\n",
		"  node n05 no kubelet lease", "  node n06 no kubelet lease",
		"(lease 40s stale)", "(lease 43s stale)", "(lease 1m35s stale)",
		"(lease 1h0m0s stale)", "(lease 1h1m40s stale)",
		"  node n13 MemoryPressure\n  node n13 PIDPressure\n",
		"  node n14 SchedulingDisabled",
		"  node n15 DiskPressure\n  node n15 NotReady: KubeletNotReady — container runtime is down\n  node n15 SchedulingDisabled\n",
		"  system kube-system/ks-cron Last run failed",
		"network policy: pods selected by allow-web, deny-web",
	} {
		if !strings.Contains(prompt, s) {
			t.Errorf("cluster prompt is missing %q", s)
		}
	}
	for _, s := range []string{"  node n12 ", "  node n16 ", "other-ns-policy"} {
		if strings.Contains(prompt, s) {
			t.Errorf("cluster prompt shows %q, which must not print", s)
		}
	}
	if got := strings.Count(prompt, "\n  system kube-system/"); got < 11 {
		t.Errorf("%d system lines, want every flagged kube-system workload (at least 11)", got)
	}
}

// kvCheckRegistry fails unless the decide dump holds every registry outcome.
func kvCheckRegistry(t *testing.T, decide string) {
	t.Helper()
	for _, s := range []string{
		"only workload failing to pull from this host; threshold is 2",
		"workloads failing to pull from this host clear the threshold of 2",
	} {
		if !strings.Contains(decide, s) {
			t.Errorf("registry decide dump is missing %q", s)
		}
	}
}
```

After writing the eleven dumps, call `kvCheckCluster(t, prompt)` in mode `cluster` and `kvCheckRegistry(t, d9.b.String())` in mode `registry`. Also update the run doc (:1-60): the `go test` line gains `KV_FIXTURE_CLUSTER=… KV_FIXTURE_REGISTRY=…`, and the copy-back step copies `out/gather_go_cluster/*` and `out/gather_go_registry/*` to `tests/fixtures/`.

- [ ] **Step 8: Write the CLUSTER fixture**

Copy the header comment's style, `kubeagent`, `summary`, `platform_line: ""`, `service_issues: []` and `pvcs: []` from `tests/fixtures/gather_fixture_logs.yaml`; every workload carries the same keys the logs fixture's workloads carry (`pod`, `pods`, `findings`, `events`, `events_failed`, `decoy_events`, `restarts`). `tests/fixtures/gather_fixture_cluster.yaml` holds 16 nodes, n01–n16, every one with explicit `conditions` (listed in the order Memory, Disk, PID, Ready unless the row says otherwise; Go prints pressure lines in the order the conditions are listed) and `scan_reason` set to the `DownNodes` reason column:

| Node | Conditions (True unless noted) | Cordoned | Lease | `scan_reason` | Expected line(s) |
|---|---|---|---|---|---|
| n01 | Ready False, reason KubeletNotReady, message of 130 runes with `é` as rune 115 | no | renewed 10,000 | NotReady | `NotReady: KubeletNotReady — <120 runes>…` |
| n02 | Ready Unknown, reason NodeStatusUnknown, message "Kubelet stopped posting node status." | no | renewed 10,000 | NotReady | `NotReady: NodeStatusUnknown — Kubelet stopped posting node status.` |
| n03 | Ready False, no reason, message "PLEG is not healthy: pleg was last seen active 3m0s ago" | no | renewed 10,000 | NotReady | `NotReady: PLEG is not healthy: …` |
| n04 | no Ready condition (pressure conditions False) | no | renewed 10,000 | NotReady | `NotReady` |
| n05 | Ready True | no | missing | no kubelet lease | `no kubelet lease` |
| n06 | Ready True | no | no_renew | no kubelet lease | `no kubelet lease` |
| n07 | Ready True | no | renewed 40,400 | kubelet not heartbeating | `kubelet not heartbeating (lease 40s stale)` |
| n08 | Ready True | no | renewed 42,500 | kubelet not heartbeating | `… (lease 43s stale)` |
| n09 | Ready True | no | renewed 95,000 | kubelet not heartbeating | `… (lease 1m35s stale)` |
| n10 | Ready True | no | renewed 3,600,000 | kubelet not heartbeating | `… (lease 1h0m0s stale)` |
| n11 | Ready True | no | renewed 3,700,000 | kubelet not heartbeating | `… (lease 1h1m40s stale)` |
| n12 | Ready True | no | renewed 40,000 | `""` | none |
| n13 | MemoryPressure True, PIDPressure True, Ready True | no | renewed 10,000 | `""` | `MemoryPressure`, `PIDPressure` |
| n14 | Ready True | yes | renewed 10,000 | `""` | `SchedulingDisabled` |
| n15 | DiskPressure True, Ready False (KubeletNotReady, "container runtime is down") | yes | renewed 10,000 | NotReady | `DiskPressure`, `NotReady: …`, `SchedulingDisabled` |
| n16 | NetworkUnavailable True (reason NoRouteCreated), ReadonlyFilesystem True (reason FilesystemIsReadOnly), CorruptDockerOverlay2 True, Ready True | no | renewed 10,000 | `""` | none: Go ignores the three detector types |

Down nodes are n01–n04, n15 (NotReady) and n05–n11 (lease): 12, more than the 8-candidate cap. Every node's `fresh` is `how: read` with the same Ready values as its conditions.

Workloads (namespace, name, kind, ready/desired, status, findings, pods → node). Every flagged workload has the same report priority, so the scope is the first 10 in namespace order. The two `app` workloads must sort before `kube-system` to stay in scope, and three kube-system workloads fall past the 10 — their system lines must still print (PIN.md `:424-425`):
- `app/web` Deployment 0/2, two pods labeled `app: web` on n16, one ProbeFailure finding each (the netpol target).
- `app/cart` Deployment 0/1, pod on n15 (the pod past the cap: n15 sorts after n01–n11, so its candidate is cut), finding CrashLoopBackOff.
- kube-system: `ks-deploy` Deployment 0/2 Running CrashLoopBackOff on n16; `ks-sts` StatefulSet 0/1 Pending Unschedulable; `ks-ds` DaemonSet 3/4 Running; `ks-job` Job status "Failed"; `ks-cron` CronJob status "Last run failed"; plus `ks-a` … `ks-f` Deployments 0/1 CrashLoopBackOff on n16 — 11 flagged kube-system workloads.
- `network_policies`: `app/allow-web` and `app/deny-web`, both `pod_selector: {app: web}`; `other/other-ns-policy`, same selector.
- 13 services, one per detail wording (every one in namespace `svc`, names `s01`–`s13` so the sort is the table order; the prompt keeps the first 10):

| Service | Setup | Expected detail |
|---|---|---|
| s01 | LoadBalancer, `lb_ingress: false`, selector matched by 1 ready pod and a 1-address ready slice | `no external address` |
| s02 | ClusterIP, selector matches 1 ready pod, slice with 0 ready addresses | `no ready endpoints` |
| s03 | annotation `kubeagent.io/expected-empty: "true"`, no matching pods | `no ready endpoints — declared via kubeagent.io/expected-empty` |
| s04 | selector matches a CronJob backend | `no ready endpoints (backs CronJob — expected between runs)` |
| s05 | selector matches a Job backend | `no ready endpoints (backs Job — expected between runs)` |
| s06 | selector matches a DaemonSet backend, desired 0 | `no ready endpoints (backs DaemonSet — 0 desired)` |
| s07 | selector matches a Deployment backend, desired 0 | `no ready endpoints (backs Deployment — scaled to 0)` |
| s08 | selector matches a StatefulSet backend, desired 0 | `no ready endpoints (backs StatefulSet — scaled to 0)` |
| s09 | selector matches no pod and no backend | `no ready endpoints — the selector matches no pods` |
| s10 | 1 not-ready pod on n01 | `no ready endpoints — matching pods on down node n01 (NotReady)` |
| s11 | 2 not-ready pods, on n02 and n05 | `no ready endpoints — matching pods on 2 down nodes` |
| s12 | 1 not-ready pod on n16 | `no ready endpoints — 1 matching pod, 0 ready` |
| s13 | 3 not-ready pods on n16 | `no ready endpoints — 3 matching pods, 0 ready` |

The `svc` pods belong to `svc/backing-*` workloads with `ready == desired` so they are not flagged and do not enter the scope. The "Expected detail" column is a prediction: the Go run decides the bytes, and any difference is recorded in the PIN.md capture record, not "fixed" in Python.

- [ ] **Step 9: Write the REGISTRY fixture**

`tests/fixtures/gather_fixture_registry.yaml`: the same top-level `kubeagent`, `summary`, `platform_line: ""`, `service_issues: []` and `pvcs: []` as the logs fixture; three nodes, `w1`–`w3`, all `scan_reason: ""` (no down node, no health block). Six Deployments in namespace `pull`, each 0/1 with one ImagePullBackOff finding:

| Workload | Image | Events on its pod | Outcome the rules give |
|---|---|---|---|
| p-conn | `reg.example.com/a:1` | `Failed` / `Failed to pull image "reg.example.com/a:1": …` holding a literal from `o.CONNECTION_LITERALS` | connection error |
| p-auth | `reg.example.com/b:1` | same shape, a literal from `o.AUTH_LITERALS` | auth error |
| p-image | `reg.example.com/c:1` | same shape, a literal from `o.IMAGE_LITERALS` | image error |
| p-nopull | `reg.example.com/d:1` | only a `BackOff` event, no pull failure | no pull event |
| p-notread | `reg.example.com/e:1` | events present, but the workload's finding names a second pod (`pods` lists two; the events read covers the first) | pulling pod not read |
| solo | `other.example.com/f:1` | a connection-error pull event | `only workload failing to pull from this host; threshold is 2` |

Print the three literal lists first: `PYTHONPATH=src .venv/bin/python -c "from kubeagent_verdict.dataset import objects as o; print(o.CONNECTION_LITERALS, o.AUTH_LITERALS, o.IMAGE_LITERALS)"`, and copy one literal from each into the messages.

- [ ] **Step 10: Run the capture from a `git archive` copy**

Follow the run doc at the top of the harness, with the two new env vars:

```bash
SCRATCH=$(mktemp -d /tmp/claude-1000/kv-capture.XXXX)
git -C /home/ubuntu/git/kubeagent archive v1.24.0 | gzip > "$SCRATCH/ka.tar.gz"
mkdir "$SCRATCH/ka" && tar -xzf "$SCRATCH/ka.tar.gz" -C "$SCRATCH/ka"
cp contract/capture/kv_capture_test.go.txt "$SCRATCH/ka/internal/investigate/kv_capture_test.go"
cd "$SCRATCH/ka" && PATH=$PATH:/usr/local/go/bin \
  KV_FIXTURE=/home/ubuntu/git/kubeagent-verdict/tests/fixtures/gather_fixture.yaml \
  KV_FIXTURE_LOGS=/home/ubuntu/git/kubeagent-verdict/tests/fixtures/gather_fixture_logs.yaml \
  KV_FIXTURE_CLUSTER=/home/ubuntu/git/kubeagent-verdict/tests/fixtures/gather_fixture_cluster.yaml \
  KV_FIXTURE_REGISTRY=/home/ubuntu/git/kubeagent-verdict/tests/fixtures/gather_fixture_registry.yaml \
  KV_GOLDEN_DIR="$SCRATCH/out" go test -count=1 -tags goldencapture -run TestCaptureVerdictGolden ./internal/investigate -v
```

Expected: PASS for all four subtests. Copy back only the two new folders: `cp -r "$SCRATCH/out/gather_go_cluster" "$SCRATCH/out/gather_go_registry" /home/ubuntu/git/kubeagent-verdict/tests/fixtures/`. Do not copy the main golden files or the old folders: `git status` must show no change under `contract/golden/`, `tests/fixtures/gather_go/` or `tests/fixtures/gather_go_logs/`. Then `rm -rf "$SCRATCH"` and check `git -C /home/ubuntu/git/kubeagent status --short` still prints only ` M .gitignore`.

If a self-check in Step 7 fails, fix the fixture (not the expected string) unless the Go output shows the expected string was wrong; in that case fix the string and say why in the report.

- [ ] **Step 11: Run the Python tests**

Run: `PYTEST tests/test_gather_byte_equal.py`
Expected: PASS, including `test_the_old_dumps_are_unchanged`, dump 0 for all four folders, the folder guard, and REGISTRY's ten byte tests.

- [ ] **Step 12: Write the capture record in PIN.md**

Add a section `## Capture record (v1.24.0, cluster and registry capture)` after the last capture record, holding:
- the full kubeagent commit (`git -C /home/ubuntu/git/kubeagent rev-parse 'v1.24.0^{commit}'`, which starts `15ec5649bbd2`);
- the Go version (`/usr/local/go/bin/go version`);
- the sha256 of both fixture files and of every file in both new dump folders (`sha256sum tests/fixtures/gather_fixture_cluster.yaml tests/fixtures/gather_fixture_registry.yaml tests/fixtures/gather_go_cluster/* tests/fixtures/gather_go_registry/*`);
- one line: "The capture ran from a `git archive v1.24.0` copy in a scratch folder; the kubeagent checkout was not touched."
- one line: "Built rows reach the registry no-pull sentence 0 times. The capture proves its bytes; reaching it needs a victim whose events have aged out."

- [ ] **Step 13: Lint and commit**

```bash
.venv/bin/ruff check --ignore EXE002 .
git add contract/capture/kv_capture_test.go.txt tests/fixtures/gather_fixture_cluster.yaml \
  tests/fixtures/gather_fixture_registry.yaml tests/fixtures/gather_go_cluster tests/fixtures/gather_go_registry \
  tests/test_gather_byte_equal.py contract/PIN.md
COMMIT "test(capture): cluster and registry capture modes, fixtures and dumps"
```

---

### Task 2: `dataset/health.py` — cluster health, service issues and network policies, pinned by the CLUSTER capture

**Files:**
- Create: `src/kubeagent_verdict/dataset/health.py`
- Create: `tests/test_health.py`
- Modify: `src/kubeagent_verdict/dataset/render.py:231-346` — `cluster_health` rebuilt on `health.assess`; `_trim_line`, `_not_ready_issue`, `_flagged` become aliases.
- Modify: `tests/test_gather_byte_equal.py` — `Run` gains `cluster`; `run()` gains the CLUSTER path; `dump_prompt` reads `r.cluster`; the byte test runs over `FOLDERS`.

**Interfaces:**
- Consumes: `gather.safetext_line(s) -> str`; `c.ClusterHealth(degraded, nodes_ready, nodes_total, node_issues, system_issues)`; `c.ServiceIssue(namespace, name, type, detail)`; `c.Workload` (fields `namespace`, `name`, `kind`, `ready`, `desired`, `status`, `findings`); Task 1's CLUSTER fixture and its 11 dumps in `tests/fixtures/gather_go_cluster/`.
- Produces (`kubeagent_verdict.dataset.health`):
  - `KUBELET_TYPES = ("MemoryPressure", "DiskPressure", "PIDPressure", "Ready")`, `DETECTOR_TYPES = ("NetworkUnavailable", "ReadonlyFilesystem", "CorruptDockerOverlay2")`, `CONDITION_TYPES = KUBELET_TYPES + DETECTOR_TYPES`
  - `SYSTEM_NAMESPACE = "kube-system"`, `NO_LEASE = "no kubelet lease"`, `NOT_HEARTBEATING = "kubelet not heartbeating"`, `THRESHOLD_MS = 40_000`, `LEASES = ("renewed", "missing", "no_renew")`
  - `Condition(type: str, status: str, reason: str = "", message: str = "")` — frozen; `ValueError` on a type outside `CONDITION_TYPES` or a status outside `("True", "False", "Unknown")`
  - `READY = Condition("Ready", "True")`
  - `Node(name: str, conditions: tuple[Condition, ...] = (), unschedulable: bool = False, lease: str = "renewed", lease_age_ms: int = 10_000)` — frozen; `ValueError` on a lease outside `LEASES`
  - `DownNode(name: str, reason: str)` — frozen
  - `flagged(w: c.Workload) -> bool`, `trim_line(s: str, limit: int) -> str`, `not_ready_issue(reason: str, message: str) -> str`, `go_duration(ms: int) -> str`
  - `assess(nodes: Sequence[Node], workloads: Sequence[c.Workload], *, threshold_ms: int = THRESHOLD_MS) -> tuple[c.ClusterHealth | None, tuple[DownNode, ...]]`
  - `Service(namespace: str, name: str, type: str = "ClusterIP", selector: tuple[tuple[str, str], ...] = (), annotations: tuple[tuple[str, str], ...] = (), lb_ingress: bool = False)`
  - `EndpointSlice(namespace: str, service: str, ready: tuple[str, ...] = ())` — each entry `"true"`, `"false"` or `"unset"`
  - `Backend(namespace: str, kind: str, labels: tuple[tuple[str, str], ...], desired: int)`
  - `Pod(namespace: str, name: str, node: str, labels: tuple[tuple[str, str], ...] = (), ready: bool = False)`
  - `SvcIssue(namespace: str, name: str, type: str, problem: str, detail: str, expected: bool = False)` with `.contract() -> c.ServiceIssue`
  - `service_issues(services, slices, backends) -> tuple[SvcIssue, ...]`
  - `annotate_endpoint_cause(issues, services, pods, down: Sequence[DownNode]) -> tuple[SvcIssue, ...]`
  - `NetworkPolicy(namespace: str, name: str, pod_selector: tuple[tuple[str, str], ...] = ())`
  - `selecting_policies(namespace: str, pods: Sequence[Pod], policies: Sequence[NetworkPolicy]) -> tuple[str, ...]`
  - `network_policies_for(w: c.Workload, pods: Sequence[Pod], policies: Sequence[NetworkPolicy]) -> tuple[str, ...]`
- `render.cluster_health(workloads, reads)` keeps its signature and its bytes. `render._SYSTEM_NAMESPACE`, `render._MIN_NODES`, `render._NO_LEASE`, `render._NODE_CAUSE`, `render._DESCRIBE_NODE`, `render._trim_line`, `render._not_ready_issue` and `render._flagged` stay importable: `checker.py:951`, `tests/test_checker.py:733`, `:786`, `tests/test_cluster_health.py:85-133`, `tests/test_gather_byte_equal.py:184` and `tests/test_catalog_text.py:193-201` use them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health.py`:

```python
"""The pure port of kubeagent's cluster health, service health and
network-policy pieces (v1.24.0). The CLUSTER capture pins the same code
byte for byte (tests/test_gather_byte_equal.py); these tests name each rule."""

from __future__ import annotations

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import health as h


def _wl(name, *, ns="kube-system", kind="Deployment", ready=0, desired=2,
        status="CrashLoopBackOff", findings=()):
    return c.Workload(ns, name, kind, ready, desired, status, 0, findings)


def _f(issue="CrashLoopBackOff"):
    return c.Finding(issue, "r", "e", "n", "cmd")


def _down(reason="KubeletNotReady", message="container runtime is down"):
    return h.Condition("Ready", "False", reason, message)


@pytest.mark.parametrize("ms, want", [
    (0, "0s"), (499, "0s"), (500, "1s"), (40_400, "40s"), (42_500, "43s"),
    (59_500, "1m0s"), (95_000, "1m35s"), (3_600_000, "1h0m0s"),
    (3_700_000, "1h1m40s"), (90_061_000, "25h1m1s"),
])
def test_go_duration_is_round_to_the_second_then_string(ms, want):
    assert h.go_duration(ms) == want


def test_notready_message_cut_counts_runes():
    msg = "a" * 114 + "é" + "b" * 15  # 130 runes, 131 bytes
    got = h.not_ready_issue("KubeletNotReady", msg)
    assert got == "NotReady: KubeletNotReady — " + "a" * 114 + "é" + "b" * 5 + "…"


@pytest.mark.parametrize("reason, message, want", [
    ("KubeletNotReady", "runtime down", "NotReady: KubeletNotReady — runtime down"),
    ("KubeletNotReady", "", "NotReady: KubeletNotReady"),
    ("", "PLEG is not healthy", "NotReady: PLEG is not healthy"),
    ("", "", "NotReady"),
])
def test_not_ready_issue_forms(reason, message, want):
    assert h.not_ready_issue(reason, message) == want


def test_an_unknown_condition_type_fails_at_load():
    with pytest.raises(ValueError, match="FrequentKubeletRestart"):
        h.Condition("FrequentKubeletRestart", "True")


def test_an_unknown_lease_fails_at_load():
    with pytest.raises(ValueError, match="stale"):
        h.Node("a", (h.READY,), lease="stale")


def test_issue_order_is_pressure_then_notready_then_cordon():
    n = h.Node("a", (h.Condition("MemoryPressure", "True"), h.Condition("DiskPressure", "True"),
                     _down()), unschedulable=True)
    got, down = h.assess([n, h.Node("b", (h.READY,)), h.Node("c", (h.READY,))], [])
    assert got.node_issues == ("a MemoryPressure", "a DiskPressure",
                               "a NotReady: KubeletNotReady — container runtime is down",
                               "a SchedulingDisabled")
    assert down == (h.DownNode("a", "NotReady"),)
    assert (got.nodes_ready, got.nodes_total) == (2, 3)


def test_the_lease_line_comes_after_the_cordon():
    n = h.Node("a", (h.READY,), unschedulable=True, lease_age_ms=41_000)
    got, _ = h.assess([n], [])
    assert got.node_issues == ("a SchedulingDisabled",
                               "a kubelet not heartbeating (lease 41s stale)")


def test_stale_lease_node_still_counts_ready():
    nodes = [h.Node("a", (h.READY,), lease_age_ms=50_000), h.Node("b", (h.READY,)),
             h.Node("c", (h.READY,))]
    got, down = h.assess(nodes, [])
    assert (got.degraded, got.nodes_ready, got.nodes_total) == (True, 3, 3)
    assert got.node_issues == ("a kubelet not heartbeating (lease 50s stale)",)
    assert down == (h.DownNode("a", "kubelet not heartbeating"),)


def test_staleness_is_judged_on_raw_milliseconds():
    at, over = h.Node("a", (h.READY,), lease_age_ms=40_000), h.Node("a", (h.READY,), lease_age_ms=40_001)
    assert h.assess([at], []) == (None, ())
    assert h.assess([over], [])[0].node_issues == ("a kubelet not heartbeating (lease 40s stale)",)
    assert h.assess([h.Node("a", (h.READY,), lease_age_ms=3_600_000)], [], threshold_ms=0) == (None, ())


@pytest.mark.parametrize("lease", ["missing", "no_renew"])
def test_a_missing_or_unrenewed_lease_prints_no_kubelet_lease(lease):
    got, down = h.assess([h.Node("a", (h.READY,), lease=lease)], [])
    assert got.node_issues == ("a no kubelet lease",)
    assert down == (h.DownNode("a", "no kubelet lease"),)
    assert got.nodes_ready == 1


def test_a_not_ready_node_is_not_lease_checked():
    got, down = h.assess([h.Node("a", (_down(),), lease="missing")], [])
    assert got.node_issues == ("a NotReady: KubeletNotReady — container runtime is down",)
    assert down == (h.DownNode("a", "NotReady"),)


def test_no_ready_condition_is_not_ready():
    got, _ = h.assess([h.Node("a", (h.Condition("DiskPressure", "False"),))], [])
    assert got.node_issues == ("a NotReady",)


def test_the_last_ready_condition_wins():
    got, _ = h.assess([h.Node("a", (_down(), h.READY))], [])
    assert got is None


def test_detector_conditions_print_nothing():
    n = h.Node("a", (h.Condition("NetworkUnavailable", "True", "NoRouteCreated"),
                     h.Condition("ReadonlyFilesystem", "True", "FilesystemIsReadOnly"),
                     h.Condition("CorruptDockerOverlay2", "True"), h.READY))
    assert h.assess([n], []) == (None, ())


def test_node_lines_are_in_name_order():
    nodes = [h.Node("b", (_down(),)), h.Node("a", (_down(),))]
    got, down = h.assess(nodes, [])
    assert [i.split()[0] for i in got.node_issues] == ["a", "b"]
    assert [d.name for d in down] == ["a", "b"]


def test_job_system_line_has_no_counts():
    cron = _wl("nightly", kind="CronJob", ready=0, desired=1,
               status="BackoffLimitExceeded (3 of 3 failed)")
    dns = _wl("coredns", ready=0, desired=2, findings=(_f(),))
    calm = _wl("kube-proxy", kind="DaemonSet", ready=3, desired=3, status="Running")
    other = _wl("api", ns="shop", findings=(_f(),))
    got, _ = h.assess([h.Node("a", (h.READY,))], [cron, dns, calm, other])
    assert got.system_issues == ("kube-system/coredns 0/2 CrashLoopBackOff",
                                 "kube-system/nightly BackoffLimitExceeded (3 of 3 failed)")
    assert got.node_issues == ()


def test_a_healthy_cluster_has_no_block():
    assert h.assess([h.Node(x, (h.READY,)) for x in "abc"], [_wl("x", ns="shop")]) == (None, ())


def test_condition_text_passes_safetext_first():
    got, _ = h.assess([h.Node("a", (_down("KubeletNotReady", "runtime\ndown\x07"),))], [])
    assert got.node_issues == ("a NotReady: KubeletNotReady — runtime down",)


# --- Service issues (svchealth.Assess, AnnotateEndpointCause).

_SEL = (("app", "x"),)


def _svc(name="s", **kw):
    return h.Service("svc", name, selector=kw.pop("selector", _SEL), **kw)


def _details(services, slices=(), backends=(), pods=(), down=()):
    issues = h.service_issues(services, slices, backends)
    return [i.detail for i in h.annotate_endpoint_cause(issues, services, pods, down)]


def test_a_load_balancer_with_no_ingress_has_no_external_address():
    s = _svc(type="LoadBalancer")
    pod = h.Pod("svc", "p", "w1", _SEL, True)
    assert _details([s], [h.EndpointSlice("svc", "s", ("true",))], pods=[pod]) == ["no external address"]


def test_an_empty_selector_gets_no_endpoint_check():
    assert _details([_svc(selector=())]) == []


def test_external_name_is_skipped():
    assert _details([_svc(type="ExternalName")]) == []


def test_unset_ready_counts_as_ready():
    pod = h.Pod("svc", "p", "w1", _SEL, False)
    assert _details([_svc()], [h.EndpointSlice("svc", "s", ("unset",))], pods=[pod]) == []


def test_a_slice_for_another_service_does_not_count():
    pod = h.Pod("svc", "p", "w1", _SEL, True)
    assert _details([_svc()], [h.EndpointSlice("svc", "other", ("true",))], pods=[pod]) == \
        ["no ready endpoints"]


def test_expected_empty_annotation():
    s = _svc(annotations=(("kubeagent.io/expected-empty", "TRUE"),))
    assert _details([s]) == ["no ready endpoints — declared via kubeagent.io/expected-empty"]


@pytest.mark.parametrize("kind, desired, want", [
    ("CronJob", 1, "no ready endpoints (backs CronJob — expected between runs)"),
    ("Job", 1, "no ready endpoints (backs Job — expected between runs)"),
    ("DaemonSet", 0, "no ready endpoints (backs DaemonSet — 0 desired)"),
    ("Deployment", 0, "no ready endpoints (backs Deployment — scaled to 0)"),
    ("StatefulSet", 0, "no ready endpoints (backs StatefulSet — scaled to 0)"),
])
def test_a_backing_workload_explains_the_empty_service(kind, desired, want):
    assert _details([_svc()], backends=[h.Backend("svc", kind, _SEL, desired)]) == [want]


def test_a_live_backend_makes_the_service_unexpected():
    backends = [h.Backend("svc", "CronJob", _SEL, 1), h.Backend("svc", "Deployment", _SEL, 2)]
    assert _details([_svc()], backends=backends) == ["no ready endpoints — the selector matches no pods"]


def test_the_backing_kind_is_the_first_in_go_order():
    backends = [h.Backend("svc", "Deployment", _SEL, 0), h.Backend("svc", "Job", _SEL, 1)]
    assert _details([_svc()], backends=backends) == \
        ["no ready endpoints (backs Job — expected between runs)"]


@pytest.mark.parametrize("pods, down, want", [
    ((), (), "no ready endpoints — the selector matches no pods"),
    ((("p1", "w1", False),), (h.DownNode("w1", "NotReady"),),
     "no ready endpoints — matching pods on down node w1 (NotReady)"),
    ((("p1", "w1", False), ("p2", "w1", False)), (h.DownNode("w1", "no kubelet lease"),),
     "no ready endpoints — matching pods on down node w1 (no kubelet lease)"),
    ((("p1", "w1", False), ("p2", "w2", False)),
     (h.DownNode("w1", "NotReady"), h.DownNode("w2", "NotReady")),
     "no ready endpoints — matching pods on 2 down nodes"),
    ((("p1", "w3", False),), (), "no ready endpoints — 1 matching pod, 0 ready"),
    ((("p1", "w3", False), ("p2", "w3", False), ("p3", "", False)), (),
     "no ready endpoints — 3 matching pods, 0 ready"),
    ((("p1", "w3", True),), (), "no ready endpoints"),
])
def test_the_endpoint_cause(pods, down, want):
    hp = [h.Pod("svc", n, node, _SEL, ready) for n, node, ready in pods]
    assert _details([_svc()], pods=hp, down=down) == [want]


def test_pods_in_another_namespace_do_not_match():
    pod = h.Pod("other", "p", "w1", _SEL, False)
    assert _details([_svc()], pods=[pod]) == ["no ready endpoints — the selector matches no pods"]


def test_service_issues_sort_by_namespace_name_problem():
    lb = _svc("a", type="LoadBalancer")
    got = h.service_issues([_svc("b"), lb], (), ())
    assert [(i.name, i.problem) for i in got] == [("a", "NoEndpoints"), ("a", "NoExternalAddress"),
                                                 ("b", "NoEndpoints")]
    assert got[0].contract() == c.ServiceIssue("svc", "a", "LoadBalancer", "no ready endpoints")


# --- Network policies (netpolicy.Annotate).

_POD = h.Pod("app", "web-1", "w1", (("app", "web"), ("tier", "fe")))


def test_selecting_policies_sorted_and_deduped():
    pols = [h.NetworkPolicy("app", "deny-web", (("app", "web"),)),
            h.NetworkPolicy("app", "allow-web", (("app", "web"),)),
            h.NetworkPolicy("app", "other", (("app", "db"),)),
            h.NetworkPolicy("elsewhere", "far", (("app", "web"),))]
    assert h.selecting_policies("app", [_POD, _POD], pols) == ("allow-web", "deny-web")


def test_an_empty_pod_selector_selects_every_pod():
    assert h.selecting_policies("app", [_POD], [h.NetworkPolicy("app", "all")]) == ("all",)


def test_policies_print_only_when_every_finding_is_a_probe_failure():
    pols = [h.NetworkPolicy("app", "deny-web", (("app", "web"),))]
    probe = _wl("web", ns="app", findings=(_f("ProbeFailure"),))
    mixed = _wl("web", ns="app", findings=(_f("ProbeFailure"), _f()))
    bare = _wl("web", ns="app", ready=0, desired=2)
    calm = _wl("web", ns="app", ready=2, desired=2, status="Running")
    assert h.network_policies_for(probe, [_POD], pols) == ("deny-web",)
    assert h.network_policies_for(mixed, [_POD], pols) == ()
    assert h.network_policies_for(bare, [_POD], pols) == ("deny-web",)
    assert h.network_policies_for(calm, [_POD], pols) == ()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PYTEST tests/test_health.py`
Expected: FAIL — `ImportError: cannot import name 'health'`.

- [ ] **Step 3: Write `dataset/health.py`**

```python
"""A pure port of kubeagent's cluster health, service health and
network-policy pieces, at v1.24.0:

- internal/clusterhealth/clusterhealth.go (`Assess`, `nodeHealth`,
  `staleHeartbeat`, `notReadyIssue`, `trimLine`);
- internal/svchealth/svchealth.go (`Assess`, `ReadyEndpoints`,
  `classifyBacking`, `AnnotateEndpointCause`);
- internal/netpolicy/netpolicy.go (`Annotate`, `selectingPolicies`).

It reads no cluster and draws no random number. The CLUSTER capture
(tests/fixtures/gather_go_cluster/) pins every line it makes, byte for
byte, through tests/test_gather_byte_equal.py.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset.gather import safetext_line

# Kubelet conditions, and the node-problem-detector conditions the stories
# use. kubeagent reads only the first four; the other three it ignores, so
# they print no health line (clusterhealth.go nodeHealth).
KUBELET_TYPES = ("MemoryPressure", "DiskPressure", "PIDPressure", "Ready")
DETECTOR_TYPES = ("NetworkUnavailable", "ReadonlyFilesystem", "CorruptDockerOverlay2")
CONDITION_TYPES = KUBELET_TYPES + DETECTOR_TYPES
_PRESSURE = ("MemoryPressure", "DiskPressure", "PIDPressure")
_STATUSES = ("True", "False", "Unknown")
SYSTEM_NAMESPACE = "kube-system"
NO_LEASE = "no kubelet lease"
NOT_HEARTBEATING = "kubelet not heartbeating"
THRESHOLD_MS = 40_000  # the scan's lease threshold; the harness's kvThreshold
LEASES = ("renewed", "missing", "no_renew")
_NOT_READY_RUNES = 120


@dataclasses.dataclass(frozen=True)
class Condition:
    """One node condition, as the scan lists it."""

    type: str
    status: str
    reason: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if self.type not in CONDITION_TYPES:
            raise ValueError(f"condition type {self.type!r} is not one of {CONDITION_TYPES}")
        if self.status not in _STATUSES:
            raise ValueError(f"condition status {self.status!r} is not one of {_STATUSES}")


READY = Condition("Ready", "True")


@dataclasses.dataclass(frozen=True)
class Node:
    """One node at scan time. `lease` is "renewed" (renewed `lease_age_ms`
    before the scan), "missing" (no lease object) or "no_renew" (a lease
    with no renew time)."""

    name: str
    conditions: tuple[Condition, ...] = ()
    unschedulable: bool = False
    lease: str = "renewed"
    lease_age_ms: int = 10_000

    def __post_init__(self) -> None:
        if self.lease not in LEASES:
            raise ValueError(f"node {self.name}: lease {self.lease!r} is not one of {LEASES}")


@dataclasses.dataclass(frozen=True)
class DownNode:
    """`clusterhealth.DownNode`: a node the root-cause pass may blame."""

    name: str
    reason: str


def flagged(w: c.Workload) -> bool:
    """A port of `Workload.Flagged` (inventory/inventory.go:102-104)."""
    return len(w.findings) > 0 or w.ready < w.desired or w.status == "Failed"


def trim_line(s: str, limit: int) -> str:
    """A port of `trimLine` (clusterhealth.go:218-229): the first line,
    stripped, cut to `limit` runes plus an ellipsis when it is longer.
    A Python str counts code points, which are Go's runes."""
    i = s.find("\n")
    if i >= 0:
        s = s[:i]
    s = s.strip()
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def not_ready_issue(reason: str, message: str) -> str:
    """A port of `notReadyIssue` (clusterhealth.go:197-216)."""
    s = "NotReady"
    m = trim_line(message, _NOT_READY_RUNES)
    if reason and m:
        s += ": " + reason + " — " + m
    elif reason:
        s += ": " + reason
    elif m:
        s += ": " + m
    return s


def go_duration(ms: int) -> str:
    """Go's `time.Duration.Round(time.Second).String()` for a non-negative
    count of milliseconds: half a second rounds up, then h/m/s."""
    s = (ms + 500) // 1000
    if s == 0:
        return "0s"
    hours, rem = divmod(s, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes}m{sec}s"
    if minutes:
        return f"{minutes}m{sec}s"
    return f"{sec}s"


def _node_health(n: Node) -> tuple[bool, list[str]]:
    """A port of `nodeHealth`: the last Ready condition decides; pressure
    conditions that are True print in the order listed; then NotReady,
    then SchedulingDisabled. Other condition types are ignored."""
    ready, reason, message, issues = False, "", "", []
    for cond in n.conditions:
        if cond.type == "Ready":
            ready = cond.status == "True"
            reason, message = safetext_line(cond.reason), safetext_line(cond.message)
        elif cond.type in _PRESSURE and cond.status == "True":
            issues.append(cond.type)
    if not ready:
        issues.append(not_ready_issue(reason, message))
    if n.unschedulable:
        issues.append("SchedulingDisabled")
    return ready, issues


def _stale(n: Node, threshold_ms: int) -> tuple[str, str] | None:
    """A port of `staleHeartbeat`: (issue, down reason), or None. Stale
    means older than the threshold, judged on raw milliseconds; only the
    printed age is rounded."""
    if n.lease in ("missing", "no_renew"):
        return NO_LEASE, NO_LEASE
    if n.lease_age_ms > threshold_ms:
        return (f"{NOT_HEARTBEATING} (lease {go_duration(n.lease_age_ms)} stale)",
                NOT_HEARTBEATING)
    return None


def assess(nodes: Sequence[Node], workloads: Sequence[c.Workload], *,
           threshold_ms: int = THRESHOLD_MS) -> tuple[c.ClusterHealth | None, tuple[DownNode, ...]]:
    """A port of `clusterhealth.Assess`: the health block and the down nodes.

    Nodes are judged in name order, the order the API server lists them.
    A Ready node counts toward R even when its lease is stale; only a Ready
    node is lease-checked, and `threshold_ms` 0 turns the check off. The
    system lines are every flagged kube-system workload in `workloads`
    (all of them, not only the scoped ones), sorted by namespace, name and
    kind as the scan sorts them before `Assess`; a Job or CronJob prints
    no counts. With no node line and no system line the cluster is
    Healthy and kubeagent prints no block, so the first value is None.
    """
    ready_count, node_issues, down = 0, [], []
    for n in sorted(nodes, key=lambda n: n.name):
        ready, issues = _node_health(n)
        if not ready:
            down.append(DownNode(n.name, "NotReady"))
        else:
            ready_count += 1
            stale = _stale(n, threshold_ms) if threshold_ms > 0 else None
            if stale is not None:
                issues.append(stale[0])
                down.append(DownNode(n.name, stale[1]))
        node_issues += [f"{n.name} {iss}" for iss in issues]
    system = []
    for w in sorted(workloads, key=lambda w: (w.namespace, w.name, w.kind)):
        if w.namespace != SYSTEM_NAMESPACE or not flagged(w):
            continue
        if w.kind in ("Job", "CronJob"):
            system.append(f"{w.namespace}/{w.name} {w.status}")
        else:
            system.append(f"{w.namespace}/{w.name} {w.ready}/{w.desired} {w.status}")
    if not node_issues and not system:
        return None, tuple(down)
    return (c.ClusterHealth(degraded=True, nodes_ready=ready_count, nodes_total=len(nodes),
                            node_issues=tuple(node_issues), system_issues=tuple(system)),
            tuple(down))


# --- Service issues (svchealth.go).

EXPECTED_EMPTY = "kubeagent.io/expected-empty"
_BACKING_ORDER = ("CronJob", "Job", "DaemonSet", "Deployment", "StatefulSet")
_EPHEMERAL = ("Job", "CronJob")
_BACKING_DETAIL = {
    "CronJob": "no ready endpoints (backs CronJob — expected between runs)",
    "Job": "no ready endpoints (backs Job — expected between runs)",
    "DaemonSet": "no ready endpoints (backs DaemonSet — 0 desired)",
    "Deployment": "no ready endpoints (backs Deployment — scaled to 0)",
    "StatefulSet": "no ready endpoints (backs StatefulSet — scaled to 0)",
}
_NO_ENDPOINTS = "no ready endpoints"


@dataclasses.dataclass(frozen=True)
class Service:
    namespace: str
    name: str
    type: str = "ClusterIP"
    selector: tuple[tuple[str, str], ...] = ()
    annotations: tuple[tuple[str, str], ...] = ()
    lb_ingress: bool = False


@dataclasses.dataclass(frozen=True)
class EndpointSlice:
    """One slice for `service`: one address per `ready` entry, each "true",
    "false" or "unset" (a nil Ready condition, which counts as ready)."""

    namespace: str
    service: str
    ready: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Backend:
    """A workload a service may front: its pod-template labels and its
    desired count. A Job or CronJob is ephemeral."""

    namespace: str
    kind: str
    labels: tuple[tuple[str, str], ...]
    desired: int


@dataclasses.dataclass(frozen=True)
class Pod:
    namespace: str
    name: str
    node: str
    labels: tuple[tuple[str, str], ...] = ()
    ready: bool = False


@dataclasses.dataclass(frozen=True)
class SvcIssue:
    """`svchealth.Issue`. `.contract()` is the line the prompt prints;
    an expected issue prints too."""

    namespace: str
    name: str
    type: str
    problem: str
    detail: str
    expected: bool = False

    def contract(self) -> c.ServiceIssue:
        return c.ServiceIssue(self.namespace, self.name, self.type, self.detail)


def _selector_matches(selector: tuple[tuple[str, str], ...],
                      labels: tuple[tuple[str, str], ...]) -> bool:
    """svchealth's `selectorMatches`: an empty selector matches nothing."""
    if not selector:
        return False
    have = dict(labels)
    return all(have.get(k) == v for k, v in selector)


def _ready_endpoints(s: Service, slices: Sequence[EndpointSlice]) -> int:
    return sum(1 for sl in slices if sl.namespace == s.namespace and sl.service == s.name
               for r in sl.ready if r in ("true", "unset"))


def _backing(s: Service, backends: Sequence[Backend]) -> str | None:
    """`classifyBacking`: the backing kind when every matching backend is
    ephemeral or scaled to zero, else None."""
    matches = [b for b in backends
               if b.namespace == s.namespace and _selector_matches(s.selector, b.labels)]
    if not matches or any(b.kind not in _EPHEMERAL and b.desired > 0 for b in matches):
        return None
    return min(matches, key=lambda b: _BACKING_ORDER.index(b.kind)).kind


def service_issues(services: Sequence[Service], slices: Sequence[EndpointSlice],
                   backends: Sequence[Backend]) -> tuple[SvcIssue, ...]:
    """A port of `svchealth.Assess`, sorted by namespace, name and problem."""
    out = []
    for s in services:
        if s.type == "ExternalName":
            continue
        if s.type == "LoadBalancer" and not s.lb_ingress:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoExternalAddress",
                                "no external address"))
        if not s.selector or _ready_endpoints(s, slices) > 0:
            continue
        kind = _backing(s, backends)
        if kind is not None:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints",
                                _BACKING_DETAIL[kind], expected=True))
        elif dict(s.annotations).get(EXPECTED_EMPTY, "").lower() == "true":
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints",
                                f"{_NO_ENDPOINTS} — declared via {EXPECTED_EMPTY}", expected=True))
        else:
            out.append(SvcIssue(s.namespace, s.name, s.type, "NoEndpoints", _NO_ENDPOINTS))
    return tuple(sorted(out, key=lambda i: (i.namespace, i.name, i.problem)))


def _endpoint_cause(s: Service, pods: Sequence[Pod], down: dict[str, str]) -> str:
    matching = [p for p in pods
                if p.namespace == s.namespace and _selector_matches(s.selector, p.labels)]
    if not matching:
        return "the selector matches no pods"
    seen, hits = set(), []
    for p in matching:
        if not p.node or p.node in seen:
            continue
        if p.node in down:
            seen.add(p.node)
            hits.append(f"{p.node} ({down[p.node]})")
    if len(hits) == 1:
        return "matching pods on down node " + hits[0]
    if hits:
        return f"matching pods on {len(hits)} down nodes"
    if not any(p.ready for p in matching):
        return f"{len(matching)} matching {'pod' if len(matching) == 1 else 'pods'}, 0 ready"
    return ""


def annotate_endpoint_cause(issues: Sequence[SvcIssue], services: Sequence[Service],
                            pods: Sequence[Pod], down: Sequence[DownNode]) -> tuple[SvcIssue, ...]:
    """A port of `AnnotateEndpointCause`: an unexpected NoEndpoints issue
    gets "no ready endpoints — <cause>" when the pods say why."""
    by_key = {(s.namespace, s.name): s for s in services}
    down_reason = {d.name: d.reason for d in down}
    out = []
    for i in issues:
        s = by_key.get((i.namespace, i.name))
        if i.problem == "NoEndpoints" and not i.expected and s is not None:
            cause = _endpoint_cause(s, pods, down_reason)
            if cause:
                i = dataclasses.replace(i, detail=f"{_NO_ENDPOINTS} — {cause}")
        out.append(i)
    return tuple(out)


# --- Network policies (netpolicy.go).

@dataclasses.dataclass(frozen=True)
class NetworkPolicy:
    """A policy's pod selector as match labels; empty selects every pod."""

    namespace: str
    name: str
    pod_selector: tuple[tuple[str, str], ...] = ()


def selecting_policies(namespace: str, pods: Sequence[Pod],
                       policies: Sequence[NetworkPolicy]) -> tuple[str, ...]:
    """A port of `selectingPolicies`: the sorted, deduped names of the
    policies in `namespace` whose selector matches any of `pods`."""
    names = set()
    for pol in policies:
        if pol.namespace != namespace:
            continue
        for p in pods:
            have = dict(p.labels)
            if all(have.get(k) == v for k, v in pol.pod_selector):
                names.add(pol.name)
                break
    return tuple(sorted(names))


def network_policies_for(w: c.Workload, pods: Sequence[Pod],
                         policies: Sequence[NetworkPolicy]) -> tuple[str, ...]:
    """A port of `netpolicy.Annotate` for one workload and its own pods:
    the selecting policies when the workload is flagged and every finding
    is a ProbeFailure (none at all counts), else ()."""
    if not flagged(w) or not all(f.issue == "ProbeFailure" for f in w.findings):
        return ()
    return selecting_policies(w.namespace, pods, policies)
```

- [ ] **Step 4: Run the health tests**

Run: `PYTEST tests/test_health.py`
Expected: PASS.

- [ ] **Step 5: Rebuild `render.cluster_health` on `health.assess`**

In `render.py`, add `from kubeagent_verdict.dataset import health` to the imports. Replace `_trim_line`, `_not_ready_issue` and `_flagged` (:248-282) with aliases, keeping the module constants above them:

```python
# Kept for the callers that import these names from render (the checker's
# docs, tests/test_checker.py, tests/test_cluster_health.py and
# tests/test_gather_byte_equal.py). The code lives in health.py.
_trim_line = health.trim_line
_not_ready_issue = health.not_ready_issue
_flagged = health.flagged
```

Replace the body of `cluster_health` (keep its docstring, and add one sentence to it: "It builds synthetic nodes from the candidates and hands them to `health.assess`, the port the CLUSTER capture pins."):

```python
    reasons: dict[str, set[str]] = {}
    for w in workloads:
        for cand in w.candidates:
            m = _NODE_CAUSE.match(cand.cause)
            if m:
                reasons.setdefault(m.group(1), set()).add(m.group(2))
    named = set(reasons) | {r.label[len(_DESCRIBE_NODE):] for r in reads
                            if r.label.startswith(_DESCRIBE_NODE)}
    nodes = []
    for name in sorted(named):
        rs = reasons.get(name, set())
        unknown = rs - {"NotReady", _NO_LEASE}
        if unknown:
            raise ValueError(f"node {name}: no cluster-health text for reason "
                             f"{min(unknown)!r}")
        if "NotReady" in rs:
            nodes.append(health.Node(name, (health.Condition(
                "Ready", "False", o.NOT_READY_REASON, o.NOT_READY_MESSAGE),)))
        elif rs:
            nodes.append(health.Node(name, (health.READY,), lease="missing"))
        else:
            nodes.append(health.Node(name, (health.READY,)))
    total = max(_MIN_NODES, len(named) + 1)
    # Healthy nodes the prompt never names. They print nothing; only the
    # count T sees them. The leading space keeps them off any real name.
    nodes += [health.Node(f" healthy-{i}", (health.READY,)) for i in range(total - len(nodes))]
    block, _down = health.assess(nodes, workloads)
    return block
```

The old function returned `None` only when there was no node reason and no system line; `health.assess` does the same. A node named only by a describe label is Ready with a fresh lease, so it prints nothing, as before.

- [ ] **Step 6: Run the render-side tests**

Run: `PYTEST tests/test_cluster_health.py tests/test_catalog_text.py tests/test_checker.py tests/test_render.py tests/test_multi_collision.py tests/test_gather_byte_equal.py`
Expected: PASS. Any failure here means a byte moved; fix `cluster_health`, not a test.

- [ ] **Step 7: Add the CLUSTER run path to the byte test**

In `tests/test_gather_byte_equal.py`, import `health` (`from kubeagent_verdict.dataset import cases, gather, health, render, rules`), add `cluster: c.ClusterHealth | None` to `Run` after `workloads`, and add these helpers above `run()`:

```python
def _cluster_mode(doc: dict) -> bool:
    """The CLUSTER fixture spells out node conditions. The Python port then
    computes the health block, the service issues and the network-policy
    lines from the fixture's objects, the way kubeagent's scan does."""
    return any("conditions" in n for n in doc["nodes"])


def _labels(d: dict | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((d or {}).items()))


def _health_nodes(doc: dict) -> tuple[health.Node, ...]:
    return tuple(health.Node(n["name"], tuple(health.Condition(**x) for x in n["conditions"]),
                             unschedulable=n.get("unschedulable", False), lease=n["lease"],
                             lease_age_ms=n.get("lease_age_ms", 0))
                 for n in doc["nodes"])


def _health_pods(w: dict) -> tuple[health.Pod, ...]:
    return tuple(health.Pod(w["namespace"], p["name"], p["node"], _labels(p.get("labels")),
                            p.get("ready", False)) for p in w["pods"])


def _cluster_services(doc: dict, down: tuple[health.DownNode, ...]) -> tuple[c.ServiceIssue, ...]:
    services = tuple(health.Service(s["namespace"], s["name"], s["type"], _labels(s["selector"]),
                                    _labels(s["annotations"]), s["lb_ingress"])
                     for s in doc.get("services", []))
    slices = tuple(health.EndpointSlice(s["namespace"], s["service"], tuple(s["ready"]))
                   for s in doc.get("endpoint_slices", []))
    backends = tuple(health.Backend(b["namespace"], b["kind"], _labels(b["labels"]), b["desired"])
                     for b in doc.get("backends", []))
    pods = tuple(p for w in doc["workloads"] for p in _health_pods(w))
    issues = health.service_issues(services, slices, backends)
    return tuple(i.contract() for i in health.annotate_endpoint_cause(issues, services, pods, down))
```

In `run()`, after the `workloads` loop and `summary`, replace the `services = …` and `prompt = …` lines with:

```python
    if _cluster_mode(doc):
        cluster, down = health.assess(_health_nodes(doc),
                                      [_prompt_workload(w) for w in doc["workloads"]])
        assert [(d.name, d.reason) for d in down] == \
            [(n["name"], n["scan_reason"]) for n in doc["nodes"] if n["scan_reason"]]
        policies = tuple(health.NetworkPolicy(p["namespace"], p["name"], _labels(p["pod_selector"]))
                         for p in doc.get("network_policies", []))
        workloads = [dataclasses.replace(pw, network_policies=health.network_policies_for(
                         pw, _health_pods(w), policies))
                     for pw, (_, w) in zip(workloads, shown)]
        services = _cluster_services(doc, down)
        prompt = c.build_user_message(cluster, summary, doc["platform_line"], services,
                                      tuple(workloads), result.reads)
        render.check_prompt_size(prompt, entry_or_scenario_key=fixture)
    else:
        cluster = render.cluster_health(tuple(workloads), result.reads)
        services = tuple(c.ServiceIssue(**x) for x in doc["service_issues"])
        prompt = cases._user_message(summary, doc["platform_line"], services, tuple(workloads),
                                     result.reads, key=fixture)
```

and pass `cluster` into `Run(...)` after `tuple(workloads)`. `zip(workloads, shown)` pairs each scoped workload with its fixture dict; `workloads` is in `shown` order and never longer. In `dump_prompt`, replace `health = render.cluster_health(r.workloads, r.result.reads)` with `health = r.cluster` (rename the local to `block` so it does not shadow the module). Change the byte test's parametrization to `FOLDERS`.

- [ ] **Step 8: Run the byte test, then everything that renders**

Run: `PYTEST tests/test_gather_byte_equal.py`
Expected: PASS for all four folders (44 dump tests), the folder guard and the old-dump hashes.

If a CLUSTER dump differs, read the diff against the Go dump. The Go dump is right: fix `health.py` (never the dump), then add a `tests/test_health.py` case that names the rule you fixed.

Run: `PYTEST tests/`
Expected: PASS (the whole suite; nothing outside these files moved).

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/ruff check --ignore EXE002 .
git add src/kubeagent_verdict/dataset/health.py tests/test_health.py \
  src/kubeagent_verdict/dataset/render.py tests/test_gather_byte_equal.py
COMMIT "feat(dataset): health port (cluster health, service issues, network policies) pinned by the cluster capture"
```

---

### Task 3: `dataset/stories.py` and `dataset/shared_origin.py` — stories as worlds, one real pipeline, three pilots

**Files:**
- Create: `src/kubeagent_verdict/dataset/stories.py`
- Create: `src/kubeagent_verdict/dataset/shared_origin.py`
- Modify: `tests/test_cases.py:1254-1300` (the prompt-size funnel test learns a second funnel, Ruling 34)
- Test: `tests/test_stories.py`, `tests/test_shared_origin_pipeline.py`

**Interfaces:**
- Consumes (Task 2): `health.Condition`, `health.READY`, `health.Node`, `health.DownNode`, `health.assess`, `health.Service`, `health.EndpointSlice`, `health.Backend`, `health.Pod`, `health.service_issues`, `health.annotate_endpoint_cause`, `health.NetworkPolicy`, `health.network_policies_for`.
- Consumes (existing): `gather.GatherFinding(issue, pod, container="", log_read=None, image="")`, `gather.GatherWorkload(namespace, name, pod, issue, objects=(), events=(), findings=(), events_failed="")`, `gather.gather(workloads, *, budget) -> GatherResult(reads, candidates, results, candidate_steps, finding_steps)`, `gather.CRASH_FAMILY`; `objects.Object`, `objects.NODE_NOT_READY`, `objects.unverify(obj, "read_failed")`; `rules.attribute(objects, *, ns, pod, issue)`; `render.header_for(candidates)`, `render.check_prompt_size(prompt, *, entry_or_scenario_key)`; `c.Workload`, `c.Finding`, `c.build_user_message(cluster, summary, platform_line, service_issues, workloads, reads)`; `names.draw(rng)`, `names.pod_name(rng, name)`, `names.NAMESPACES`, `names.NODES`; `remediation.suggest_for(issue, *, ns, pod, container="", kind="", workload)`; `checker.LOG_CAUSES`, `checker.LOG_CAUSE_PREFIX`, `checker.LOG_NO_PREVIOUS`, `checker.LOG_NO_CLASSIFIABLE`.
- Produces:
  - `stories.Answer(anchor: str, cause: str, keys: tuple[str, ...], rationale: str, confidence: str = "high", link: bool = False)`
  - `stories.VictimText(workload_kind, status, issue, reason, evidence, events=(), log="", broken: Answer | None = None, healthy: Answer | None = None, events_healthy=None, evidence_healthy=None, log_healthy=None, on_origin=False, pulls=False, none_phrase="")`
  - `stories.OriginRow(namespace, name, kind, status, issue, reason, evidence, container, ready=0, desired=2, events=(), log="", answer: Answer | None = None, none_phrase="")`
  - `stories.ServiceSpec(namespace, name, selector, ready: tuple[str, ...], backend: tuple[str, int] | None = None)`
  - `stories.World(conditions=(health.READY,), unschedulable=False, lease="renewed", lease_age_ms=10_000, origin_row: OriginRow | None = None, pvc_reason="", pvc_phase="", pvc_class="", pull_literal="", services=(), policies=())`
  - `stories.Story(key, cls, blast_radius, scope_field, origin_kind, victims, broken, healthy, shown_origin, shown_cause, shown_remedy)`
  - `stories.by_key() -> dict[str, Story]`, `stories.trainable() -> tuple[Story, ...]`, `stories.exam() -> tuple[Story, ...]`, `stories.EXAM_KEYS`, `stories.RULED_ORDER`, `stories.NO_PREVIOUS`, `stories.NO_CLASSIFIABLE`
  - `shared_origin.Draw(scope_value, victims: tuple[Names, ...], origin: Names | None, nodes: tuple[str, ...], width: int)`
  - `shared_origin.draw(story, rng, *, width) -> Draw` — every rng call for a pair
  - `shared_origin.Row(key, role, index, names, workload: c.Workload, text, result: rules.Result, candidates: tuple[c.Candidate, ...], trace)`
  - `shared_origin.Built(story, world_name, draw, group, user, rows: tuple[Row, ...], health: c.ClusterHealth | None, service_issues, gathered, unverified)`
  - `shared_origin.build(story, d: Draw, *, world: str, unverified: bool = False) -> Built` — no rng; `world` is "broken" or "healthy"

The spec's `build(story, rng, *, world, victims)` is split into `draw` then
`build`, so the twins share one `Draw` by construction (Ruling 11).

- [ ] **Step 1: Write the failing story tests**

Create `tests/test_stories.py`:

```python
import pytest

from kubeagent_verdict.dataset import stories as s
from kubeagent_verdict.dataset.checker import LOG_CAUSES


def test_answer_keys_are_checked():
    with pytest.raises(ValueError, match="key"):
        s.Answer(anchor="x", cause="its probe fails", keys=("Probe",), rationale="r")
    with pytest.raises(ValueError, match="key"):
        s.Answer(anchor="x", cause="its probe fails", keys=("dns",), rationale="r")
    with pytest.raises(ValueError, match="inside"):
        s.Answer(anchor="x", cause="its probe fails", keys=("timeout",), rationale="r")
    with pytest.raises(ValueError, match="1 to 3"):
        s.Answer(anchor="x", cause="a b c d", keys=(), rationale="r")
    with pytest.raises(ValueError, match="rationale"):
        s.Answer(anchor="x", cause="its probe fails", keys=("probe",), rationale="")


def test_log_label_never_links():
    a = s.Answer(anchor="log cause: port already in use", cause="its port is already in use",
                 keys=("port",), rationale="r", link=True)
    with pytest.raises(ValueError, match="log"):
        s.validate_answer(a)


def test_pilots_are_present_and_valid():
    by = s.by_key()
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        st = by[key]
        assert st.cls in s.CLASSES and st.scope_field in s.SCOPES
        assert st.origin_kind in s.ORIGIN_KINDS
        assert len(st.victims) >= 2
        for v in st.victims:
            for log in (v.log, v.log_healthy):
                assert log in (None, "", s.NO_PREVIOUS, s.NO_CLASSIFIABLE) or log in LOG_CAUSES


def test_exam_order_and_trainable_disjoint():
    exam = [st.key for st in s.exam()]
    assert exam == [k for k in s.EXAM_KEYS if k in s.by_key()]
    assert not {st.key for st in s.trainable()} & set(s.EXAM_KEYS)
```

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/test_stories.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'kubeagent_verdict.dataset.stories'`.

- [ ] **Step 3: Write `stories.py`**

```python
"""The shared-origin stories as data (Spec 4b-1 §4).

A story is one upstream fault seen from 2 or more victims. Each story has
two worlds: `broken` (the fault is real) and `healthy` (it is not). Victim
texts hold the victim's own lines; `{node}`, `{ns}`, `{name}`, `{pod}`,
`{pvc}` and `{scope}` are filled by `shared_origin.build`. Gold comes from
`Answer` anchors found in a victim's own lines (dataset/gold.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kubeagent_verdict.dataset import health
from kubeagent_verdict.dataset.checker import LOG_CAUSES

NO_PREVIOUS = "<no previous>"
NO_CLASSIFIABLE = "<no classifiable>"
CLASSES = ("P", "R")
SCOPES = ("node", "ns", "")
ORIGIN_KINDS = ("node", "pvc", "registry", "workload", "other")
CONFIDENCES = ("high", "medium")
EXAM_KEYS = ("coredns-down", "node-not-ready", "storage-provisioner-down",
             "registry-unreachable", "node-disk-pressure", "networkpolicy-deny-all")
RULED_ORDER = ("node-kubelet-halted", "node-kubelet-unresponsive",
               "pvc-provisioner-not-responding", "pvc-storageclass-missing",
               "registry-mirror-unreachable", "registry-rate-limited")
_KEY = re.compile(r"^[a-z]{4,}$")


@dataclass(frozen=True)
class Answer:
    anchor: str
    cause: str
    keys: tuple[str, ...]
    rationale: str
    confidence: str = "high"
    link: bool = False

    def __post_init__(self) -> None:
        if not 1 <= len(self.keys) <= 3:
            raise ValueError(f"{self.cause!r}: 1 to 3 keys, got {len(self.keys)}")
        for k in self.keys:
            if not _KEY.match(k):
                raise ValueError(f"{self.cause!r}: key {k!r} is not 4+ lowercase letters")
            if k not in self.cause.lower():
                raise ValueError(f"{self.cause!r}: key {k!r} is not inside the cause")
        if "{" in "".join(self.keys):
            raise ValueError(f"{self.cause!r}: a key may not hold a placeholder")
        if not self.rationale.strip():
            raise ValueError(f"{self.cause!r}: the rationale is empty")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"{self.cause!r}: confidence {self.confidence!r}")


def validate_answer(a: Answer) -> None:
    """Checks that need the story: a log label never links (Ruling 19)."""
    if a.link and a.anchor.startswith("log cause: "):
        raise ValueError(f"{a.cause!r}: a log-cause label never carries link=True")


@dataclass(frozen=True)
class VictimText:
    workload_kind: str
    status: str
    issue: str
    reason: str
    evidence: str
    events: tuple[tuple[str, str, int], ...] = ()
    log: str = ""
    broken: Answer | None = None
    healthy: Answer | None = None
    events_healthy: tuple[tuple[str, str, int], ...] | None = None
    evidence_healthy: str | None = None
    log_healthy: str | None = None
    on_origin: bool = False
    pulls: bool = False
    none_phrase: str = ""


@dataclass(frozen=True)
class OriginRow:
    namespace: str
    name: str
    kind: str
    status: str
    issue: str
    reason: str
    evidence: str
    container: str
    ready: int = 0
    desired: int = 2
    events: tuple[tuple[str, str, int], ...] = ()
    log: str = ""
    answer: Answer | None = None
    none_phrase: str = ""


@dataclass(frozen=True)
class ServiceSpec:
    namespace: str
    name: str
    selector: tuple[tuple[str, str], ...]
    ready: tuple[str, ...]
    backend: tuple[str, int] | None = None


@dataclass(frozen=True)
class World:
    conditions: tuple[health.Condition, ...] = (health.READY,)
    unschedulable: bool = False
    lease: str = "renewed"
    lease_age_ms: int = 10_000
    origin_row: OriginRow | None = None
    pvc_reason: str = ""
    pvc_phase: str = ""
    pvc_class: str = ""
    pull_literal: str = ""
    services: tuple[ServiceSpec, ...] = ()
    policies: tuple[health.NetworkPolicy, ...] = ()


@dataclass(frozen=True)
class Story:
    key: str
    cls: str
    blast_radius: str
    scope_field: str
    origin_kind: str
    victims: tuple[VictimText, ...]
    broken: World
    healthy: World
    shown_origin: str
    shown_cause: str
    shown_remedy: str


_NOT_READY = health.Condition("Ready", "False", "KubeletNotReady", "container runtime is down")

_STORIES: tuple[Story, ...] = (
    Story(
        key="node-not-ready", cls="R", blast_radius="node", scope_field="node",
        origin_kind="node",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff",
                issue="ContainerStartError", reason="RunContainerError",
                evidence="container {name} failed to start (RunContainerError)",
                events=(("Failed", "Error: RunContainerError: failed to create containerd "
                         "task: context deadline exceeded", 3),),
                log=NO_PREVIOUS, on_origin=True,
                none_phrase="its container fails to start"),
            VictimText(
                workload_kind="StatefulSet", status="ContainerCreating",
                issue="VolumeAttachError", reason="FailedAttachVolume",
                evidence="volume pvc-{pvc} cannot attach",
                events=(("FailedAttachVolume", 'Multi-Attach error for volume "pvc-{pvc}" '
                         "Volume is already exclusively attached to one node and can't be "
                         "attached to another", 4),),
                on_origin=True, none_phrase="its volume cannot attach"),
        ),
        broken=World(conditions=(_NOT_READY,)),
        healthy=World(),
        shown_origin="node {node} is NotReady",
        shown_cause="node {node} reports Ready False: container runtime is down",
        shown_remedy="Recover or drain {node}; the flagged workloads need no change.",
    ),
    Story(
        key="coredns-down", cls="P", blast_radius="cluster", scope_field="",
        origin_kind="workload",
        victims=(
            VictimText(
                workload_kind="Deployment", status="CrashLoopBackOff",
                issue="CrashLoopBackOff", reason="Error",
                evidence="container {name} exited with code 1",
                log="DNS resolution failed (name lookup)",
                broken=Answer(anchor="log cause: DNS resolution failed (name lookup)",
                              cause="its container crashes because DNS name resolution "
                                    "fails on lookup",
                              keys=("resolution", "lookup"),
                              rationale="its log read names a DNS lookup failure"),
                log_healthy="cannot reach a dependency — connection refused",
                healthy=Answer(anchor="log cause: cannot reach a dependency — connection refused",
                               cause="its container crashes because a dependency refuses "
                                     "connections",
                               keys=("refuses", "connections"),
                               rationale="its log read names a refused connection"),
                none_phrase="its container keeps crashing"),
            VictimText(
                workload_kind="Deployment", status="Running",
                issue="ProbeFailure", reason="Unhealthy",
                evidence="readiness probe failing",
                events=(("Unhealthy", "Readiness probe failed: Get \"http://10.0.0.1:8080/ready\": "
                         "lookup sessions.auth.svc.cluster.local: server misbehaving", 6),),
                broken=Answer(anchor="lookup sessions.auth.svc.cluster.local: server misbehaving",
                              cause="its readiness probe fails because DNS lookups are "
                                    "misbehaving",
                              keys=("lookups", "misbehaving"), confidence="medium",
                              rationale="its probe event shows a failed DNS lookup", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: Get "
                                 "\"http://10.0.0.1:8080/ready\": context deadline exceeded "
                                 "after 1s", 6),),
                healthy=Answer(anchor="context deadline exceeded after 1s",
                               cause="its readiness probe hits a timeout on a slow dependency",
                               keys=("timeout", "dependency"), confidence="medium",
                               rationale="its probe event shows a deadline exceeded"),
                none_phrase="its readiness probe fails"),
            VictimText(
                workload_kind="StatefulSet", status="Running",
                issue="ProbeFailure", reason="Unhealthy",
                evidence="readiness probe failing",
                events=(("Unhealthy", "Readiness probe failed: lookup "
                         "{name}-0.{name}.{ns}.svc.cluster.local: server misbehaving", 5),),
                broken=Answer(anchor="svc.cluster.local: server misbehaving",
                              cause="its readiness probe fails because DNS lookups are "
                                    "misbehaving",
                              keys=("lookups", "misbehaving"), confidence="medium",
                              rationale="its probe event shows a failed DNS lookup", link=True),
                events_healthy=(("Unhealthy", "Readiness probe failed: HTTP probe failed "
                                 "with statuscode: 503", 5),),
                healthy=Answer(anchor="HTTP probe failed with statuscode: 503",
                               cause="its readiness probe gets a 503 status code",
                               keys=("status", "code"), confidence="medium",
                               rationale="its probe event shows a 503 answer"),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(
            origin_row=OriginRow(
                namespace="kube-system", name="coredns", kind="Deployment",
                status="CrashLoopBackOff", issue="CrashLoopBackOff", reason="Error",
                evidence="container coredns exited with code 1", container="coredns",
                events=(("BackOff", "Back-off restarting failed container coredns in pod "
                         "{pod}", 9),),
                log="configuration parse/validation error",
                answer=Answer(anchor="log cause: configuration parse/validation error",
                              cause="CoreDNS keeps crashing because its configuration fails "
                                    "to parse",
                              keys=("configuration", "parse"),
                              rationale="its log read names a configuration parse error")),
            services=(ServiceSpec("kube-system", "kube-dns", (("k8s-app", "kube-dns"),),
                                  ready=("false", "false"), backend=("Deployment", 2)),),
        ),
        healthy=World(),
        shown_origin="CoreDNS is down",
        shown_cause="CoreDNS keeps crashing on a configuration parse error, so the kube-dns "
                    "service has no ready endpoints",
        shown_remedy="Fix the CoreDNS configuration; the flagged workloads need no change.",
    ),
    Story(
        key="networkpolicy-deny-all", cls="P", blast_radius="namespace", scope_field="ns",
        origin_kind="other",
        victims=(
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="liveness probe failing",
                events=(("Unhealthy", "Liveness probe failed: dependency check timed out", 7),),
                broken=Answer(anchor="default-deny",
                              cause="the NetworkPolicy default-deny selects its pods and "
                                    "blocks its traffic, so its liveness probe fails",
                              keys=("policy", "deny"),
                              rationale="its network policy line names default-deny",
                              link=True),
                none_phrase="its liveness probe fails"),
            VictimText(
                workload_kind="Deployment", status="Running", issue="ProbeFailure",
                reason="Unhealthy", evidence="readiness probe failing",
                events=(("Unhealthy", "Readiness probe failed: upstream check timed out", 5),),
                broken=Answer(anchor="default-deny",
                              cause="the NetworkPolicy default-deny selects its pods and "
                                    "blocks its traffic, so its readiness probe fails",
                              keys=("policy", "deny"),
                              rationale="its network policy line names default-deny",
                              link=True),
                none_phrase="its readiness probe fails"),
        ),
        broken=World(policies=(health.NetworkPolicy("{scope}", "default-deny", ()),)),
        healthy=World(),
        shown_origin="the NetworkPolicy default-deny in {scope}",
        shown_cause="the NetworkPolicy default-deny in {scope} selects every pod and blocks "
                    "their traffic",
        shown_remedy="Allow the needed traffic in {scope} or remove default-deny; the "
                     "flagged workloads need no change.",
    ),
)


def by_key() -> dict[str, Story]:
    return {st.key: st for st in _STORIES}


def exam() -> tuple[Story, ...]:
    by = by_key()
    return tuple(by[k] for k in EXAM_KEYS if k in by)


def trainable() -> tuple[Story, ...]:
    rest = [st for st in _STORIES if st.key not in EXAM_KEYS]
    p = sorted((st for st in rest if st.cls == "P"), key=lambda st: st.key)
    r = sorted((st for st in rest if st.cls == "R"),
               key=lambda st: RULED_ORDER.index(st.key) if st.key in RULED_ORDER else 99)
    return tuple(p + r)
```

Note: `health.NetworkPolicy(namespace, name, pod_selector)` carries `"{scope}"`
here; `build` formats it. An empty `pod_selector` selects every pod in the
namespace, as in kubeagent.

- [ ] **Step 4: Run the story tests**

Run: `PYTEST tests/test_stories.py`
Expected: PASS (4 tests).

- [ ] **Step 5: Write the failing pipeline tests**

Create `tests/test_shared_origin_pipeline.py`:

```python
import random

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict.dataset import rules, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.dataset.checker import LOG_CAUSE_PREFIX, LOG_CAUSES


def _twins(key, seed=7, width=None, unverified=False):
    # The healthy twin has no down node, so it never takes `unverified` (Ruling 31).
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(seed), width=width or len(st.victims))
    return (so.build(st, d, world="broken", unverified=unverified),
            so.build(st, d, world="healthy"))


@pytest.mark.parametrize("key", ["node-not-ready", "coredns-down", "networkpolicy-deny-all"])
def test_twins_share_names_and_differ_in_a_line(key):
    b, h = _twins(key)
    assert [r.key for r in b.rows if r.role == "victim"] == \
           [r.key for r in h.rows if r.role == "victim"]
    assert b.group == h.group
    assert set(b.user.splitlines()) != set(h.user.splitlines())


def test_rows_are_in_report_order():
    b, _ = _twins("coredns-down")
    keys = [(r.workload.namespace, r.workload.name, r.workload.kind) for r in b.rows]
    assert keys == sorted(keys)


def test_down_node_is_confirmed_on_both_victims():
    b, h = _twins("node-not-ready")
    assert all(r.result.decided for r in b.rows)
    assert not any(r.result.decided for r in h.rows)
    assert b.health is not None and "NotReady" in b.user
    # The printed line carries both halves (contract.py:212), never a bare "— ".
    for r in b.rows:
        assert r.workload.decided_outcome == r.result.outcome != ""
        assert f"decided by rules: {r.result.cause} — {r.result.outcome}\n" in b.user


def test_unverified_twin_shows_the_refused_node_read():
    # A refused read still decides: rules.decide returns outcome "unverified"
    # (rules.py:325-330), which is job 1 but never counts toward rules.shared.
    b = _twins("node-not-ready", unverified=True)[0]
    node = b.draw.scope_value
    assert f'nodes "{node}" is forbidden' in b.user
    assert all(r.result.decided and r.result.outcome == "unverified" for r in b.rows)
    assert all(r.workload.decided_outcome == "unverified" for r in b.rows)
    assert b.user.count(" — unverified\n") == len(b.rows)
    assert rules.shared(tuple(r.result for r in b.rows)) == ()


def test_unverified_needs_a_down_node():
    st = stories.by_key()["coredns-down"]
    d = so.draw(st, random.Random(7), width=len(st.victims))
    with pytest.raises(ValueError, match="unverified"):
        so.build(st, d, world="broken", unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        so.build(st, d, world="healthy", unverified=True)


def test_health_header_counts_the_down_node():
    b, h = _twins("node-not-ready")
    total = len(b.draw.nodes)
    assert 3 <= total <= 5
    assert f"{total - 1}/{total} nodes Ready" in b.user
    assert b.health.nodes_total == total and b.health.nodes_ready == total - 1
    assert h.health is None or not h.health.degraded


def test_netpol_line_only_in_the_broken_world():
    b, h = _twins("networkpolicy-deny-all")
    assert "default-deny" in b.user and "default-deny" not in h.user


def test_log_reads_print_a_known_label():
    b, h = _twins("coredns-down")
    for built in (b, h):
        for line in built.user.splitlines():
            if LOG_CAUSE_PREFIX in line:
                assert line.split(LOG_CAUSE_PREFIX, 1)[1].strip() in LOG_CAUSES


def test_origin_row_only_in_the_broken_world():
    b, h = _twins("coredns-down")
    assert [r.key for r in b.rows if r.role == "origin"] == ["kube-system/coredns"]
    assert not [r for r in h.rows if r.role == "origin"]
    assert "kube-system/kube-dns" in b.user and "kube-system/kube-dns" not in h.user


def test_width_two_drops_the_third_victim():
    b, _ = _twins("coredns-down", width=2)
    assert len([r for r in b.rows if r.role == "victim"]) == 2


def test_prompt_fits_and_has_at_most_ten_workloads():
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        for built in _twins(key):
            assert len(built.rows) <= c.MAX_GATHER_WORKLOADS
            assert len(built.gathered.reads) <= c.MAX_TOOL_CALLS
```

Then teach the funnel test in `tests/test_cases.py` about the second funnel.
`shared_origin.build` calls `c.build_user_message` itself, because it passes
the real `cluster` from `health.assess` rather than the one
`render.cluster_health` would rebuild. Without this edit the existing test
`test_every_build_user_message_call_goes_through_the_checked_funnel` fails
on `shared_origin.py`. Replace `_build_user_message_calls_outside_the_funnel`
(test_cases.py:1254-1275) with this, and add the new test right after
`test_every_build_user_message_call_goes_through_the_checked_funnel`:

```python
# The two functions allowed to call `build_user_message`. Each must also call
# `render.check_prompt_size`, which `test_each_funnel_checks_the_prompt_size`
# pins, so a third call site cannot slip past the byte cap (Ruling 34).
_FUNNELS = {("cases.py", "_user_message"), ("shared_origin.py", "build")}


def _build_user_message_calls_outside_the_funnel() -> list[str]:
    """Every call to `build_user_message` found by parsing every module under
    `src/kubeagent_verdict/dataset/`, except the calls inside the two funnels
    in `_FUNNELS`: `cases._user_message` and `shared_origin.build`. Returns
    "path:lineno" strings for whatever is left; an empty list means every call
    site in the package goes through a funnel (and so through
    `render.check_prompt_size`).
    """
    dataset_dir = pathlib.Path(cases.__file__).parent
    findings: list[str] = []
    for path in sorted(dataset_dir.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        funnel_call_ids: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (path.name, node.name) in _FUNNELS:
                funnel_call_ids |= {id(sub) for sub in ast.walk(node)
                                    if _is_build_user_message_call(sub)}
        for node in ast.walk(tree):
            if _is_build_user_message_call(node) and id(node) not in funnel_call_ids:
                findings.append(f"{path.name}:{node.lineno}")
    return findings


def test_each_funnel_checks_the_prompt_size():
    dataset_dir = pathlib.Path(cases.__file__).parent
    for fname, func in sorted(_FUNNELS):
        tree = ast.parse((dataset_dir / fname).read_text())
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == func)
        calls = {s.func.attr if isinstance(s.func, ast.Attribute) else getattr(s.func, "id", "")
                 for s in ast.walk(fn) if isinstance(s, ast.Call)}
        assert "check_prompt_size" in calls, (fname, func)
```

In the docstring of
`test_every_build_user_message_call_goes_through_the_checked_funnel`, change
"routes through `cases._user_message`, the one funnel that pairs the two" to
"routes through one of the two funnels in `_FUNNELS` (`cases._user_message`
and `shared_origin.build`), each of which pairs the two", and change "outside
that one funnel function" to "outside those two funnel functions". In its
assert message, change "to route through cases._user_message (the shared
funnel)" to "to route through a funnel in _FUNNELS".

- [ ] **Step 6: Run them to see them fail**

Run: `PYTEST tests/test_shared_origin_pipeline.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'kubeagent_verdict.dataset.shared_origin'`.

Run: `PYTEST tests/test_cases.py -k funnel`
Expected: FAIL in `test_each_funnel_checks_the_prompt_size` with `FileNotFoundError` naming `shared_origin.py`.

- [ ] **Step 7: Write `shared_origin.py`**

```python
"""One shared-origin world through kubeagent's real pipeline (Spec 4b-1 §5).

`draw` makes every rng call for a pair; `build` runs one world with no rng:
report order → one gather → the rules over every candidate → the prompt.
This module never imports `cases` or `generate` (Ruling 26).
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import NamedTuple

from kubeagent_verdict import contract as c
from kubeagent_verdict import remediation as rem
from kubeagent_verdict.dataset import gather, health, objects, render, rules, stories
from kubeagent_verdict.dataset import names as names_mod
from kubeagent_verdict.dataset.checker import (LOG_CAUSE_PREFIX, LOG_NO_CLASSIFIABLE,
                                               LOG_NO_PREVIOUS)
from kubeagent_verdict.dataset.names import Names

ORIGIN_EVENTS_FORBIDDEN = ('events is forbidden: User "kubeagent" cannot list '
                           'resource "events" in API group "" in the namespace "kube-system"')


class Draw(NamedTuple):
    scope_value: str
    victims: tuple[Names, ...]
    origin: Names | None
    nodes: tuple[str, ...]
    width: int


class Row(NamedTuple):
    key: str
    role: str
    index: int
    names: Names
    workload: c.Workload
    text: stories.VictimText | stories.OriginRow
    result: rules.Result
    candidates: tuple[c.Candidate, ...]
    trace: tuple


class Built(NamedTuple):
    story: stories.Story
    world_name: str
    draw: Draw
    group: str
    user: str
    rows: tuple[Row, ...]
    health: c.ClusterHealth | None
    service_issues: tuple[c.ServiceIssue, ...]
    gathered: gather.GatherResult
    unverified: bool


def _draw_in(rng: random.Random, ns: str | None) -> Names:
    n = names_mod.draw(rng)
    ns = ns or n.ns
    tag = n.image.rsplit(":", 1)[-1]
    return replace(n, ns=ns, pod=names_mod.pod_name(rng, n.name),
                   image=f"registry.example.com/{ns}/{n.name}:{tag}")


def draw(story: stories.Story, rng: random.Random, *, width: int) -> Draw:
    """Every rng call for a pair, before any branch on the world (Ruling 11)."""
    if not 2 <= width <= len(story.victims):
        raise ValueError(f"{story.key}: width {width} outside 2..{len(story.victims)}")
    if story.scope_field == "ns":
        scope = rng.choice(names_mod.NAMESPACES)
    elif story.scope_field == "node":
        scope = rng.choice(names_mod.NODES)
    else:
        scope = ""
    victims: list[Names] = []
    seen: set[tuple[str, str]] = set()
    for _ in story.victims[:width]:
        while True:
            n = _draw_in(rng, scope if story.scope_field == "ns" else None)
            if story.scope_field == "node":
                n = replace(n, node=scope)
            if (n.ns, n.name) not in seen:
                break
        seen.add((n.ns, n.name))
        victims.append(n)
    row = story.broken.origin_row or story.healthy.origin_row
    origin = None
    if row is not None:
        o = names_mod.draw(rng)
        origin = replace(o, ns=row.namespace, name=row.name, container=row.container,
                         pod=names_mod.pod_name(rng, row.name))
    named = {n.node for n in victims} | ({origin.node} if origin else set())
    total = rng.randint(max(3, len(named) + 1), 5)
    nodes = sorted(named)
    for extra in names_mod.NODES:
        if len(nodes) >= total:
            break
        if extra not in nodes:
            nodes.append(extra)
    return Draw(scope, tuple(victims), origin, tuple(sorted(nodes)), width)


def _sub(text: str, n: Names | None, d: Draw) -> str:
    return text.format_map({
        "scope": d.scope_value, "node": n.node if n else d.scope_value,
        "ns": n.ns if n else d.scope_value, "name": n.name if n else "",
        "pod": n.pod if n else "", "pvc": n.pvc if n else ""})


def _kind(t) -> str:
    return t.kind if isinstance(t, stories.OriginRow) else t.workload_kind


def _container(t, n: Names) -> str:
    return n.init_container if t.status.startswith("Init:") else n.container


def _log_body(value: str) -> str:
    if value == stories.NO_PREVIOUS:
        return LOG_NO_PREVIOUS
    if value == stories.NO_CLASSIFIABLE:
        return LOG_NO_CLASSIFIABLE
    return LOG_CAUSE_PREFIX + value


def _pick(t, field: str, healthy: bool):
    alt = getattr(t, field + "_healthy", None)
    return alt if healthy and alt is not None else getattr(t, field)


def build(story: stories.Story, d: Draw, *, world: str, unverified: bool = False,
          budget: int = c.MAX_TOOL_CALLS, origin_events_failed: str = "") -> Built:
    if world not in ("broken", "healthy"):
        raise ValueError(f"world {world!r}")
    healthy = world == "healthy"
    w = story.healthy if healthy else story.broken
    entries = [("victim", i, n, v) for i, (v, n) in enumerate(zip(story.victims, d.victims))]
    if w.origin_row is not None:
        entries.append(("origin", -1, d.origin, w.origin_row))
    entries.sort(key=lambda e: (e[2].ns, e[2].name, _kind(e[3])))   # _report_order's key

    def finding(t, n: Names) -> c.Finding:
        s = rem.suggest_for(t.issue, ns=n.ns, pod=n.pod, container=_container(t, n),
                            kind=_kind(t), workload=n.name)
        return c.Finding(issue=t.issue, reason=t.reason,
                         evidence=_sub(_pick(t, "evidence", healthy), n, d),
                         next_step=s.next_step, command=s.command)

    def bare(t, n: Names) -> c.Workload:
        ready = t.ready if isinstance(t, stories.OriginRow) else 0
        desired = t.desired if isinstance(t, stories.OriginRow) else 1
        return c.Workload(namespace=n.ns, name=n.name, kind=_kind(t), ready=ready,
                          desired=desired, status=t.status, restarts=n.restarts,
                          findings=(finding(t, n),))

    origin_node = d.scope_value if story.origin_kind == "node" else ""
    nodes = tuple(
        health.Node(name, conditions=w.conditions, unschedulable=w.unschedulable,
                    lease=w.lease, lease_age_ms=w.lease_age_ms) if name == origin_node
        else health.Node(name, conditions=(health.READY,))
        for name in d.nodes)
    cluster, down = health.assess(nodes, [bare(t, n) for _, _, n, t in entries])
    if unverified and not down:
        raise ValueError(f"{story.key}: unverified needs a down node to refuse")

    pods = tuple(health.Pod(n.ns, n.pod, n.node, labels=(("app", n.name),))
                 for _, _, n, _ in entries)
    svcs, slices, backends, svc_pods = [], [], [], list(pods)
    for spec in w.services:
        svcs.append(health.Service(spec.namespace, spec.name, selector=spec.selector))
        slices.append(health.EndpointSlice(spec.namespace, spec.name, ready=spec.ready))
        if spec.backend is not None:
            backends.append(health.Backend(spec.namespace, spec.backend[0], spec.selector,
                                           spec.backend[1]))
        svc_pods += [health.Pod(spec.namespace, f"{spec.name}-{i}", d.nodes[0],
                                labels=spec.selector, ready=r == "true")
                     for i, r in enumerate(spec.ready)]
    issues = health.annotate_endpoint_cause(
        health.service_issues(tuple(svcs), tuple(slices), tuple(backends)),
        tuple(svcs), tuple(svc_pods), down)
    policies = tuple(replace(p, namespace=_sub(p.namespace, None, d)) for p in w.policies)

    gws, objs = [], []
    for role, _, n, t in entries:
        ob = []
        for dn in down:
            o = objects.Object(kind="node", name=dn.name, scan_reason=dn.reason,
                               placement="on" if n.node == dn.name else "off",
                               fresh=objects.NODE_NOT_READY, intent="cause")
            ob.append(objects.unverify(o, "read_failed") if unverified else o)
        objs.append(tuple(ob))
        container = _container(t, n)
        log = _pick(t, "log", healthy)
        reads_log = t.issue in gather.CRASH_FAMILY
        f = gather.GatherFinding(issue=t.issue, pod=f"{n.ns}/{n.pod}", container=container,
                                 log_read=_log_body(log) if reads_log else None,
                                 image=n.image if getattr(t, "pulls", False) else "")
        events = tuple((r, _sub(m, n, d), k) for r, m, k in _pick(t, "events", healthy))
        gws.append(gather.GatherWorkload(
            namespace=n.ns, name=n.name, pod=n.pod, issue=t.issue, objects=tuple(ob),
            events=events, findings=(f,),
            events_failed=origin_events_failed if role == "origin" else ""))
    gathered = gather.gather(gws, budget=budget)

    rows, workloads = [], []
    for i, (role, idx, n, t) in enumerate(entries):
        candidates = gathered.candidates[i]
        result = gathered.results[i]
        base = bare(t, n)
        wl = replace(base, candidates=candidates, confidence=render.header_for(candidates),
                     decided=result.decided, decided_cause=result.cause if result.decided else "",
                     decided_outcome=result.outcome if result.decided else "",
                     network_policies=health.network_policies_for(base, pods, policies))
        workloads.append(wl)
        trace = rules.attribute(objs[i], ns=n.ns, pod=n.pod, issue=t.issue)
        rows.append(Row(f"{n.ns}/{n.name}", role, idx, n, wl, t, result, candidates, trace))

    issues_c = tuple(i.contract() for i in issues)
    user = c.build_user_message(cluster, None, "", issues_c, tuple(workloads), gathered.reads)
    group = "+".join(f"propagation:{story.key}:{n.ns}/{n.name}" for n in d.victims)
    render.check_prompt_size(user, entry_or_scenario_key=group)
    return Built(story, world, d, group, user, tuple(rows), cluster, issues_c, gathered,
                 unverified)
```

`gathered.candidates[i]` and `gathered.results[i]` are workload i's shown
candidates and `rules.Result`, in input order. If the field shapes differ
(a dict keyed by "ns/name"), index by `f"{n.ns}/{n.name}"` instead; the
tests do not change.

- [ ] **Step 8: Run the pipeline tests**

Run: `PYTEST tests/test_stories.py tests/test_shared_origin_pipeline.py`
Expected: PASS (17 tests: 4 in test_stories.py, 13 in the pipeline file, where the twins test runs once per pilot).

Run: `PYTEST tests/test_cases.py -k funnel`
Expected: PASS (2 tests).

- [ ] **Step 9: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add src/kubeagent_verdict/dataset/stories.py src/kubeagent_verdict/dataset/shared_origin.py \
       tests/test_stories.py tests/test_shared_origin_pipeline.py tests/test_cases.py \
  && COMMIT "feat(dataset): stories as worlds and one real shared-origin pipeline (3 pilots)"
```

---

### Task 4: `dataset/gold.py` — gold from anchors in each workload's own lines

**Files:**
- Create: `src/kubeagent_verdict/dataset/gold.py`
- Modify: `src/kubeagent_verdict/dataset/render.py` (append `_NOUN` and `rule_rationale`; add `"rule_rationale"` to `__all__`)
- Modify: `src/kubeagent_verdict/dataset/cases.py:55-75` (`_NOUN` and `_rule_rationale` become one alias line, Ruling 30)
- Test: `tests/test_shared_origin_gold.py`

**Interfaces:**
- Consumes (Task 3): `shared_origin.draw`, `shared_origin.build(story, d, *, world, unverified=False, budget=c.MAX_TOOL_CALLS, origin_events_failed="") -> Built`, `shared_origin.ORIGIN_EVENTS_FORBIDDEN`, `shared_origin._sub`, `Row`, `stories.Answer`, `stories.by_key`.
- Consumes (existing): `rules.shared(results) -> tuple[str, ...]`, `rules.label(lines) -> "none" | "separate" | "shared"`, `rules.Result.decisions` (`Decision(candidate, outcome, evidence)`); score.py `_SECTION_MARK` :219, `_READ_LABEL` :220, `_GATHER_GROUP_LABEL` :223, `_read_owner` :226-249, `_own_blocks` :251 to its end, `_norm_cause` :600-605.
- Produces:
  - `gold.own_lines(user: str, workloads: Iterable[str]) -> dict[str, frozenset[str]]` — the verbatim port of `score._own_blocks`, same signature and return value. Every workload gets a key. Every line in it is already cleaned by `_norm_cause` (NFKC, lowercase, trailing periods off, spaces squeezed), so a caller cleans an anchor with `gold._norm_cause` before looking for it.
  - `gold._norm_cause(s: str) -> str` — the verbatim port of score.py's.
  - `gold.anchor_lines(own: Iterable[str], row: shared_origin.Row) -> list[str]`
  - `gold.check_keys(keys, *, anchors: list[str], own: list[str]) -> None`
  - `gold.RowGold(verdict: str, cause: str, confidence: str, keys: tuple[str, ...], rationale: str, linked: bool)` — `verdict` is "decided", "named" or "none_of_these"
  - `gold.label_for(rule_lines: tuple[str, ...], *, linked: int, cls: str, world: str) -> str` — "shared" or "none"
  - `gold.Gold(rows: dict[str, RowGold], label: str, n: int, summary: str)`
  - `gold.gold_for(built: shared_origin.Built) -> Gold`
  - `gold._summary(built, rows: dict[str, RowGold], label: str, n: int) -> str` — 1 to 4 lines joined with "\n" (Ruling 33)
  - `render.rule_rationale(result: rules.Result) -> str` — moved from `cases._rule_rationale`, body unchanged; `cases._rule_rationale` stays as an alias

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shared_origin_gold.py`:

```python
import random

import pytest

from kubeagent_verdict.dataset import cases, gold, render, rules, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score

PILOTS = ("node-not-ready", "coredns-down", "networkpolicy-deny-all")


def _built(key, world, width=None, **kw):
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(11), width=width or len(st.victims))
    return so.build(st, d, world=world, **kw)


@pytest.mark.parametrize("key", PILOTS)
@pytest.mark.parametrize("world", ["broken", "healthy"])
def test_own_lines_equal_the_graders(key, world):
    b = _built(key, world)
    keys = [r.key for r in b.rows]
    assert gold.own_lines(b.user, keys) == score._own_blocks(b.user, keys)


def test_decided_rows_take_the_rules_cause():
    b = _built("node-not-ready", "broken")
    g = gold.gold_for(b)
    for r in b.rows:
        rg = g.rows[r.key]
        assert rg.verdict == "decided" and rg.confidence == "high"
        assert rg.cause == r.result.cause
        assert rg.rationale == render.rule_rationale(r.result)
    assert g.label == "shared"


def test_rule_rationale_moved_to_render():
    assert cases._rule_rationale is render.rule_rationale


def test_decided_gold_passes_job1():
    for kw in ({}, {"unverified": True}):
        b = _built("node-not-ready", "broken", **kw)
        g = gold.gold_for(b)
        for r in b.rows:
            rg = g.rows[r.key]
            wm = {"decided_cause": r.result.cause, "decided_outcome": r.result.outcome,
                  "decided_evidence": r.result.evidence}
            assert score.job1(wm, {"cause": rg.cause, "rationale": rg.rationale}) == 1.0


def test_unverified_twin_is_decided_and_labelled_none():
    # Ruling 31: a refused node read decides every row (job 1) but confirms
    # nothing, so rules.shared is () and the label is "none".
    g = gold.gold_for(_built("node-not-ready", "broken", unverified=True))
    assert g.label == "none"
    assert all(rg.verdict == "decided" for rg in g.rows.values())
    assert g.summary.startswith(f"{g.n} workloads are failing, and kubeagent's rules did not ")


def test_named_needs_its_anchor_and_none_otherwise():
    g = gold.gold_for(_built("coredns-down", "broken"))
    verdicts = sorted(rg.verdict for rg in g.rows.values())
    assert verdicts.count("named") == 4          # 3 victims + the coredns origin row
    h = gold.gold_for(_built("node-not-ready", "healthy"))
    for rg in h.rows.values():
        assert rg.verdict == "none_of_these" and rg.confidence == "low" and rg.keys == ()
        assert rg.rationale.endswith("; none of its own lines says why.")


def test_labels_per_world_and_width():
    assert gold.gold_for(_built("coredns-down", "broken")).label == "shared"
    assert gold.gold_for(_built("coredns-down", "broken", width=2)).label == "none"
    assert gold.gold_for(_built("coredns-down", "healthy")).label == "none"
    assert gold.gold_for(_built("networkpolicy-deny-all", "broken")).label == "shared"
    assert gold.gold_for(_built("networkpolicy-deny-all", "healthy")).label == "none"


def test_rules_separate_maps_to_none():
    lines = ("no shared cause among the 2 workloads confirmed by rules",)
    assert rules.label(lines) == "separate"
    assert gold.label_for(lines, linked=0, cls="R", world="broken") == "none"


def test_cross_world_keys_do_not_overlap():
    for key in PILOTS:
        b = gold.gold_for(_built(key, "broken"))
        h = gold.gold_for(_built(key, "healthy"))
        for k in set(b.rows) & set(h.rows):
            assert not set(b.rows[k].keys) & set(h.rows[k].keys), k


def test_planted_key_in_an_excluded_line_is_refused():
    with pytest.raises(ValueError, match="only in excluded lines"):
        gold.check_keys(("deny",), anchors=["probe failed"], own=["probe failed", "policy deny"])


def test_summaries():
    g = gold.gold_for(_built("networkpolicy-deny-all", "broken"))
    assert g.summary.startswith("2 workloads share one upstream cause: the NetworkPolicy ")
    assert "Root cause: " in g.summary
    h = gold.gold_for(_built("networkpolicy-deny-all", "healthy"))
    assert h.summary.startswith("2 workloads are failing, and kubeagent's rules did not "
                                "confirm one cause on two or more of them.\n")
    assert h.summary.count(": its own lines do not show why.") == 2


def test_summary_is_one_to_four_lines():
    for key in PILOTS:
        for world in ("broken", "healthy"):
            lines = gold.gold_for(_built(key, world)).summary.split("\n")
            assert 1 <= len(lines) <= 4 and all(ln.strip() for ln in lines), (key, world)


def test_separate_reasons_only_when_every_healthy_row_has_its_own_cause():
    b = _built("coredns-down", "healthy")
    rows = {r.key: gold.RowGold("named", f"cause {i}", "high", ("x",), "r", False)
            for i, r in enumerate(b.rows)}
    n = len(rows)
    assert gold._summary(b, rows, "none", n).startswith(
        f"{n} workloads are failing for separate reasons.\n")
    same = {k: g._replace(cause="cause 0") for k, g in rows.items()}
    assert "separate reasons" not in gold._summary(b, same, "none", n)
    first = next(iter(rows))
    unnamed = {**rows, first: gold.RowGold("none_of_these", "", "low", (), "r", False)}
    assert "separate reasons" not in gold._summary(b, unnamed, "none", n)
    bb = _built("coredns-down", "broken", width=2)
    rows_b = {r.key: gold.RowGold("named", f"cause {i}", "high", ("x",), "r", False)
              for i, r in enumerate(bb.rows)}
    assert "separate reasons" not in gold._summary(bb, rows_b, "none", len(rows_b))


def test_refused_origin_read_keeps_shared_label():
    b = _built("coredns-down", "broken", origin_events_failed=so.ORIGIN_EVENTS_FORBIDDEN)
    assert "forbidden" in b.user
    assert gold.gold_for(b).label == "shared"


def test_budget_cut_victim_falls_back_to_none_of_these():
    cut_seen = False
    for budget in range(1, 9):
        b = _built("coredns-down", "broken", budget=budget)
        g = gold.gold_for(b)
        own = gold.own_lines(b.user, [r.key for r in b.rows])
        linked = 0
        for row in b.rows:
            if row.role != "victim" or row.text.broken is None:
                continue
            anchor = gold._norm_cause(so._sub(row.text.broken.anchor, row.names, b.draw))
            seen = any(anchor in line for line in gold.anchor_lines(own[row.key], row))
            if not seen:
                cut_seen = True
                assert g.rows[row.key].verdict == "none_of_these"
            elif row.text.broken.link:
                linked += 1
        confirmed = sum(1 for r in b.rows if g.rows[r.key].verdict == "decided")
        assert g.n == (max(linked, confirmed) if g.label == "shared" else len(b.rows))
        assert g.label == ("shared" if linked >= 2 else "none")
    assert cut_seen, "no budget in 1..8 cut a victim's anchor; the test proves nothing"
```

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/test_shared_origin_gold.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'kubeagent_verdict.dataset.gold'`.

- [ ] **Step 3: Move the rule rationale, then write `gold.py`**

Move `_NOUN` and `_rule_rationale` from `cases.py:55-75` to the end of
`render.py`. Keep `_NOUN` as it is. Rename the function to `rule_rationale`
and keep its body and docstring unchanged. render.py already imports `rules`.
Add `"rule_rationale"` to render's `__all__`, in sorted order. In cases.py, replace
the two definitions with one line, so every current caller keeps working
(cases.py :349, :853, :1550; test_cases.py :121, :562;
test_rule_rationale.py :108; test_shared_origin_decided.py :65, :77):

```python
_rule_rationale = render.rule_rationale
```

Then copy, verbatim and in order, from `src/kubeagent_verdict/evals/score.py`:
`_SECTION_MARK` (:219), `_READ_LABEL` (:220), `_GATHER_GROUP_LABEL` (:223),
`_read_owner` (:226-249), `_own_blocks` (:251 to the end of that function)
and `_norm_cause` (:600-605), plus any module constant they read. Rename
`_own_blocks` to `own_lines`; keep every other name. Do not import
`evals.score` (Ruling 7). Then add:

```python
"""Gold for a shared-origin row (Spec 4b-1 §6), from anchors in own lines."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import NamedTuple

from kubeagent_verdict.dataset import render, rules
from kubeagent_verdict.dataset import shared_origin as so

# ... the verbatim port from score.py goes here (own_lines, _norm_cause, ...) ...

_EXCLUDED = ("ruled_out", "refuted")


class RowGold(NamedTuple):
    verdict: str
    cause: str
    confidence: str
    keys: tuple[str, ...]
    rationale: str
    linked: bool


class Gold(NamedTuple):
    rows: dict[str, RowGold]
    label: str
    n: int
    summary: str


def anchor_lines(own: Iterable[str], row: so.Row) -> list[str]:
    """A row's own lines minus every line that names a ruled-out or refuted
    candidate's cause: a gold may not lean on a cause the rules threw out."""
    dropped = [_norm_cause(shown.cause) for d, shown in zip(row.result.decisions, row.candidates)
               if d.outcome in _EXCLUDED]
    return [ln for ln in own if not any(x and x in _norm_cause(ln) for x in dropped)]


def check_keys(keys: tuple[str, ...], *, anchors: list[str], own: list[str]) -> None:
    for k in keys:
        if any(k in ln.lower() for ln in anchors):
            continue
        if any(k in ln.lower() for ln in own):
            raise ValueError(f"key {k!r} sits only in excluded lines")


def label_for(rule_lines: tuple[str, ...], *, linked: int, cls: str, world: str) -> str:
    if rules.label(rule_lines) == "shared":
        return "shared"
    if cls == "P" and world == "broken" and linked >= 2:
        return "shared"
    return "none"                                   # "separate" maps here (Ruling 25)


def _row_gold(row: so.Row, own: list[str], built: so.Built) -> RowGold:
    t = row.text
    if row.result.decided:                          # confirmed or unverified: job 1
        return RowGold("decided", row.result.cause, "high", (),
                       render.rule_rationale(row.result), False)
    if row.role == "origin":
        answer = t.answer
    else:
        answer = t.healthy if built.world_name == "healthy" else t.broken
    if answer is not None:
        anchor = _norm_cause(so._sub(answer.anchor, row.names, built.draw))
        anchors = anchor_lines(own, row)
        if any(anchor in ln for ln in anchors):
            check_keys(answer.keys, anchors=anchors, own=own)
            return RowGold("named", so._sub(answer.cause, row.names, built.draw),
                           answer.confidence, answer.keys, answer.rationale,
                           answer.link and built.world_name == "broken")
    return RowGold("none_of_these", "", "low", (),
                   f"{t.none_phrase}; none of its own lines says why.", False)


def gold_for(built: so.Built) -> Gold:
    blocks = own_lines(built.user, [r.key for r in built.rows])
    rows = {r.key: _row_gold(r, sorted(blocks[r.key]), built) for r in built.rows}
    rule_lines = rules.shared(tuple(r.result for r in built.rows))
    linked = sum(1 for r in built.rows if r.role == "victim" and rows[r.key].linked)
    label = label_for(rule_lines, linked=linked, cls=built.story.cls, world=built.world_name)
    if label == "shared":
        confirmed = sum(1 for r in built.rows
                        if rows[r.key].verdict == "decided" and r.result.outcome == "confirmed")
        n = max(linked, confirmed)
    else:
        n = len(built.rows)
    return Gold(rows, label, n, _summary(built, rows, label, n))


def _summary(built: so.Built, rows: dict[str, RowGold], label: str, n: int) -> str:
    """1 to 4 lines, joined with "\\n" (Ruling 33). "Failing for separate
    reasons" is said only in a healthy world where every row has its own,
    different cause, named or rule-decided; anywhere else it would claim more
    than the rows show."""
    st, d = built.story, built.draw
    if label == "shared":
        return "\n".join((
            f"{n} workloads share one upstream cause: {so._sub(st.shown_origin, None, d)}.",
            f"Root cause: {so._sub(st.shown_cause, None, d)}.",
            so._sub(st.shown_remedy, None, d)))
    separate = (built.world_name == "healthy"
                and all(g.verdict != "none_of_these" for g in rows.values())
                and len({g.cause for g in rows.values()}) == len(rows))
    lines = [f"{n} workloads are failing for separate reasons." if separate else
             f"{n} workloads are failing, and kubeagent's rules did not confirm one "
             "cause on two or more of them."]
    for r in built.rows[:3]:
        g = rows[r.key]
        lines.append(f"{r.key}: {g.cause}." if g.cause else
                     f"{r.key}: its own lines do not show why.")
    return "\n".join(lines)
```

`shown_origin`, `shown_cause` and `shown_remedy` are formatted with no
victim, so `{node}` and `{ns}` take the scope value.

- [ ] **Step 4: Run the gold tests**

Run: `PYTEST tests/test_shared_origin_gold.py`
Expected: PASS (20 tests: the own-lines test runs 6 times, 3 pilots × 2
worlds).

Run: `PYTEST tests/test_cases.py tests/test_rule_rationale.py tests/test_shared_origin_decided.py`
Expected: PASS (the `_rule_rationale` alias keeps every old caller working). If `test_budget_cut_victim_falls_back_to_none_of_these` fails only
on its last assert (`cut_seen`), no budget from 1 to 8 cut a victim's
anchor. Do not weaken or delete that assert. Stop and report
DONE_WITH_CONCERNS with the read labels the gather made at budget 1, so
the controller can rule on another story or width for this test.

- [ ] **Step 5: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add src/kubeagent_verdict/dataset/gold.py src/kubeagent_verdict/dataset/render.py \
       src/kubeagent_verdict/dataset/cases.py tests/test_shared_origin_gold.py \
  && COMMIT "feat(dataset): shared-origin gold from anchors in own lines"
```

---

### Task 5: The R stories, the PVC and registry branches, and the story guard tests

**Files:**
- Modify: `src/kubeagent_verdict/dataset/stories.py` (append 8 stories to `_STORIES`; add `DROPPED`)
- Modify: `src/kubeagent_verdict/dataset/shared_origin.py` (`build`'s per-entry loop: the PVC and registry objects)
- Test: `tests/test_stories.py` (guard tests over every story), `tests/test_shared_origin_pipeline.py`

**Interfaces:**
- Consumes (Tasks 3–4): `stories.*`, `shared_origin.draw/build`, `gold.gold_for`, `gold.own_lines`, `gold.anchor_lines`.
- Consumes (existing): `objects.Fresh(phase=, storage_class=, literal=)`, `objects.validate` (objects.py:92 — the authority on which fields each kind needs), `gather._registry_host(image)`, `propagation.all_scenarios()` / `trainable_scenarios()` (the source texts).
- Produces: `stories.DROPPED: tuple[str, ...]` (13 keys); 8 R stories; `build` emits a `pvc` object per victim when `World.pvc_reason` is set and a `registry` object per pulling victim when `World.pull_literal` is set.

**Authoring procedure (Ruling 15).** For each story: (1) start from the
`propagation.py` scenario with the same key — copy each victim's workload
kind, status, issue, reason, evidence and events into a `VictimText`, and
turn its origin text into `World` fields. A healthy-world line never names
the broken origin's effect (a taint, a condition or an object only the
broken world has). Where a victim's broken line does, give it
`evidence_healthy` / `events_healthy` / `log_healthy`: the scenario's own
`healthy_evidence` or `healthy_read_content` when it has one that still
shows the victim failing, otherwise a new line; (2) build both worlds with seed 0
at full width and read the prompt; (3) give a victim a `broken` answer only
when its own lines name its own cause, with `link=True` only when that line
names the origin's effect; (4) give a `healthy` answer only when its healthy
lines show a different own cause, with keys that share nothing with the
broken keys; (5) write a `none_phrase` for every victim; (6) run the guard
tests.

| key | scope | origin | broken world | healthy world | victims |
|---|---|---|---|---|---|
| node-kubelet-halted | node | node | `conditions=(_NOT_READY,)` | `World()` | 3, all of propagation's, `on_origin=True` |
| node-kubelet-unresponsive | node | node | `conditions=(_NOT_READY,)`, `lease="stale"`, `lease_age_ms=95_000` | `World()` | 3, all of propagation's, `on_origin=True` |
| pvc-provisioner-not-responding | ns | pvc | `pvc_reason="ProvisionerNotResponding"`, `pvc_phase="Pending"`, `pvc_class="standard"` | `World()` | 3 Pending, FailedScheduling "unbound immediate PersistentVolumeClaims" (the third, a ContainerCreating Deployment in propagation, is re-authored as Pending: an unbound claim never reaches a mount) |
| pvc-storageclass-missing | ns | pvc | `pvc_reason="MissingStorageClass"`, `pvc_phase="Pending"`, `pvc_class="fast-ssd"` | `World()` | 3, as above |
| registry-mirror-unreachable | ns | registry | `pull_literal="dial tcp: lookup registry.example.com: i/o timeout"` | `World()` | 3, all of propagation's (ImagePullBackOff or ErrImagePull), `pulls=True`, events "Failed to pull image …" |
| registry-rate-limited | ns | registry | `pull_literal="429 Too Many Requests: toomanyrequests: rate limit exceeded"` | `World()` | 3, as above |
| storage-provisioner-down (exam) | ns | pvc | `pvc_reason="ProvisionerNotResponding"`, `pvc_phase="Pending"`, `pvc_class="standard"` | `World()` | 3 |
| registry-unreachable (exam) | ns | registry | `pull_literal="dial tcp 10.0.0.9:443: connect: connection refused"` | `World()` | 3, `pulls=True` |

Each of the six trainable R stories keeps three victims (Ruling 50):
Task 8's floors and Task 9's three-victim test need a third. If
`test_r_stories_confirm_in_broken_only` fails on a third victim, stop and
report DONE_WITH_CONCERNS with the story and the victim. Never drop the
victim to pass.

Every down origin node carries the `NODE_NOT_READY` describe (Ruling 23),
so all three node R stories are confirmed in the broken world. In the
healthy world of an R story no victim may name the origin; a victim is
named only from its own healthy lines.

`shown_*` for R stories: node → as node-not-ready; pvc →
`"storage class {…} cannot provision"`, `"the provisioner for storage class
<class> is not responding"` (or "does not exist"), `"Fix the provisioner
for <class>; the flagged workloads need no change."`; registry →
`"registry registry.example.com is unreachable"` (or "rate limits pulls"),
the literal, `"Restore access to registry.example.com; the flagged
workloads need no change."`.

`DROPPED` = the 12 X stories (cluster-autoscaler-at-capacity,
internal-ca-expired, kube-proxy-degraded, namespace-migration-lock-held,
namespace-shared-pvc-full, node-clock-skew, node-conntrack-full,
node-frequent-kubelet-restart, node-kernel-deadlock,
shared-base-image-tag-moved, shared-gateway-refusing,
sidecar-injector-broken) plus runtime-class-removed.

- [ ] **Step 1: Write the failing guard tests**

Append to `tests/test_stories.py`:

```python
import random

from kubeagent_verdict.dataset import gold
from kubeagent_verdict.dataset import shared_origin as so


def _both(st, seed=0):
    d = so.draw(st, random.Random(seed), width=len(st.victims))
    return so.build(st, d, world="broken"), so.build(st, d, world="healthy")


def _all():
    return tuple(s.by_key().values())


def test_no_dropped_story_is_kept():
    assert not set(s.DROPPED) & set(s.by_key())
    assert len(s.DROPPED) == 13


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_worlds_differ_in_a_printed_line(st):
    b, h = _both(st)
    assert set(b.user.splitlines()) != set(h.user.splitlines())


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_every_answer_anchor_shows_in_its_world(st):
    b, h = _both(st)
    for built, pick in ((b, "broken"), (h, "healthy")):
        own = gold.own_lines(built.user, [r.key for r in built.rows])
        for row in built.rows:
            a = row.text.answer if row.role == "origin" else getattr(row.text, pick)
            if a is None or row.result.decided:
                continue
            s.validate_answer(a)
            anchor = gold._norm_cause(so._sub(a.anchor, row.names, built.draw))
            assert any(anchor in ln for ln in gold.anchor_lines(own[row.key], row)), \
                (st.key, pick, row.key, anchor)


@pytest.mark.parametrize("st", _all(), ids=lambda st: st.key)
def test_cross_world_keys_share_nothing(st):
    for v in st.victims:
        if v.broken and v.healthy:
            assert not set(v.broken.keys) & set(v.healthy.keys), st.key


@pytest.mark.parametrize("st", [x for x in _all() if x.cls == "R"], ids=lambda st: st.key)
def test_r_stories_confirm_in_broken_only(st):
    b, h = _both(st)
    assert gold.gold_for(b).label == "shared"
    assert all(r.result.decided for r in b.rows if r.role == "victim")
    assert not any(r.result.decided for r in h.rows)
    assert gold.gold_for(h).label == "none"
```

Append to `tests/test_shared_origin_pipeline.py`:

```python
def test_pvc_candidate_only_when_the_claim_is_flagged():
    b, h = _twins("storage-provisioner-down")
    assert any(cd.kind == "pvc" for r in b.rows for cd in r.trace)
    assert not any(cd.kind == "pvc" for r in h.rows for cd in r.trace)


def test_registry_candidate_reads_the_pull_literal():
    b, _ = _twins("registry-unreachable")
    assert "connection refused" in b.user
    assert all(r.result.decided for r in b.rows if r.role == "victim")
```

(`Candidate.kind` is the object kind the rules attribute; if the field is
named otherwise in rules.py, use that name — the assertion is "a pvc
candidate exists".)

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/test_stories.py tests/test_shared_origin_pipeline.py`
Expected: FAIL — `AttributeError: module ... has no attribute 'DROPPED'` and `KeyError: 'storage-provisioner-down'`.

- [ ] **Step 3: Add the PVC and registry branches to `build`**

In `shared_origin.build`, inside the per-entry loop, right after the
down-node loop and before `objs.append(tuple(ob))`:

```python
        if w.pvc_reason and role == "victim":
            ob.append(objects.Object(
                kind="pvc", name=n.pvc, scan_reason=w.pvc_reason, placement="mounted",
                fresh=objects.Fresh(phase=w.pvc_phase, storage_class=w.pvc_class),
                intent="cause"))
        if w.pull_literal and getattr(t, "pulls", False):
            ob.append(objects.Object(
                kind="registry", name=gather._registry_host(n.image), scan_reason="{count}",
                placement="", fresh=objects.Fresh(literal=w.pull_literal), intent="cause"))
```

These values are the ones `objects.validate` accepts (objects.py:115-127).
A PVC's placement is `"mounted"` (`PVC_PLACEMENTS`), because the victim's
own pods mount its claim; `rules.attribute` rules out any other placement
(rules.py:151). A registry has no placement (`""`), and its `scan_reason`
is the `"{count}"` template: `gather.gather` writes the real count of
pulling workloads in the row over it (`gather._registry_counts`,
gather.py:539-543), so the printed cause reads `registry <host> (<N>
workloads failing to pull)` with `<N>` the pullers the row shows.

- [ ] **Step 4: Add `DROPPED` and the 8 R stories** following the table and
the authoring procedure. Keep the victim texts' issue strings exactly as in
`propagation.py`.

- [ ] **Step 5: Run the tests**

Run: `PYTEST tests/test_stories.py tests/test_shared_origin_pipeline.py tests/test_shared_origin_gold.py`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add src/kubeagent_verdict/dataset/stories.py src/kubeagent_verdict/dataset/shared_origin.py \
       tests/test_stories.py tests/test_shared_origin_pipeline.py \
  && COMMIT "feat(dataset): the R stories with PVC and registry candidates"
```

---

### Task 6: The P stories (two batches), the named edits, and the count tests

**Files:**
- Modify: `src/kubeagent_verdict/dataset/stories.py`
- Test: `tests/test_stories.py`

**Interfaces:**
- Consumes: Tasks 3–5 (the authoring procedure and guard tests in Task 5).
- Produces: all 47 stories; `trainable()` returns 41 (35 P by key, then the 6 R in `RULED_ORDER`); `exam()` returns 6.

Batch A (19, node-scoped and origin-row stories): node-pid-pressure,
node-runtime-restarting, node-memory-pressure, node-network-unavailable,
node-readonly-filesystem, node-cordoned-draining, node-corrupt-overlay,
node-disk-pressure (exam), cluster-maintenance-taint,
cni-ip-pool-exhausted, csi-node-driver-crashed, namespace-egress-proxy-down,
pod-identity-webhook-down, external-secrets-operator-down,
network-operator-down, cert-manager-down, metrics-server-down,
csi-controller-oomkilled, csi-controller-unschedulable.

Batch B (17): shared-configmap-deleted, shared-dependency-scaled-to-zero,
image-pull-secret-expired, shared-secret-key-renamed,
shared-pvc-multi-attach, namespace-limitrange-lowered,
storageclass-pool-retired, shared-nfs-server-down,
provisioner-credentials-rotated, storage-backend-full,
csi-driver-version-mismatch, networkpolicy-egress-allowlist-stale,
networkpolicy-dns-egress-missing, networkpolicy-namespace-label-drifted,
networkpolicy-port-mismatch, networkpolicy-allow-selector-typo,
networkpolicy-ingress-deny-all.

Named edits (spec §4):
- node-pid-pressure: the broken world carries `health.Condition("PIDPressure", "True", "KubeletHasInsufficientPID", "")` beside Ready.
- The 6 networkpolicy stories, shared-pvc-multi-attach and csi-driver-version-mismatch: at least one victim gets `events_healthy`, `evidence_healthy` or `log_healthy`, so the healthy world shows that victim's own cause (about 24 new victim texts in all).
- NetworkUnavailable, ReadonlyFilesystem, CorruptDockerOverlay2 and runtime restarts print no health line: their worlds differ through the victims' own lines.
- node-network-unavailable and node-disk-pressure: the Pending victim's broken `evidence` and events keep the `node.kubernetes.io/network-unavailable` (or `node.kubernetes.io/disk-pressure`) taint text; its `evidence_healthy` and `events_healthy` carry propagation.py's `healthy_evidence` / `healthy_read_content` over, so the healthy world names `dedicated=gpu` and never the condition's taint. Task 9 Part B's healthy-evidence tests read these lines.
- Origin rows (Ruling 19): named — csi-controller-unschedulable via its FailedScheduling event, network-operator and csi-controller-oomkilled via OOMKilled (cause "…was killed at its memory limit", keys `("memory", "limit")`, high); `none_of_these` — cert-manager, external-secrets, metrics-server, pod-identity-webhook, csi-node-driver-crashed, namespace-egress-proxy (its origin is `none_of_these` by rule).
- shared-dependency-scaled-to-zero: its linked answers are `confidence="medium"`, keys `("session", "endpoint")`.
- image-pull-secret-expired, storageclass-pool-retired, provisioner-credentials-rotated, storage-backend-full, csi-controller-oomkilled, csi-controller-unschedulable stay P: the rules leave them unconfirmed (auth errors are Unverified; ProvisioningFailed groups per claim; no PVC candidate reaches the victims).

- [ ] **Step 1: Write the failing count and edit tests**

Append to `tests/test_stories.py`:

```python
def test_counts():
    by = s.by_key()
    assert len(by) == 47
    assert sum(st.cls == "P" for st in by.values()) == 38
    tr = s.trainable()
    assert len(tr) == 41
    assert [st.cls for st in tr] == ["P"] * 35 + ["R"] * 6
    assert [st.key for st in tr[35:]] == list(s.RULED_ORDER)
    assert [st.key for st in s.exam()] == list(s.EXAM_KEYS)


def test_named_edits():
    by = s.by_key()
    assert any(cd.type == "PIDPressure" and cd.status == "True"
               for cd in by["node-pid-pressure"].broken.conditions)
    assert by["networkpolicy-deny-all"].healthy.policies == ()
    for key in ("networkpolicy-egress-allowlist-stale", "networkpolicy-dns-egress-missing",
                "networkpolicy-namespace-label-drifted", "networkpolicy-port-mismatch",
                "networkpolicy-allow-selector-typo", "networkpolicy-ingress-deny-all",
                "shared-pvc-multi-attach", "csi-driver-version-mismatch"):
        assert any(v.events_healthy is not None or v.evidence_healthy is not None
                   or v.log_healthy is not None for v in by[key].victims), key


def test_p_labels_are_mixed():
    labels = []
    for st in s.trainable():
        if st.cls != "P":
            continue
        b, _ = _both(st)
        labels.append(gold.gold_for(b).label)
    assert labels.count("shared") >= 5 and labels.count("none") >= 5, labels
```

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/test_stories.py`
Expected: FAIL in `test_counts` (`assert 11 == 47`).

- [ ] **Step 3: Write batch A** with the authoring procedure, then run
`PYTEST tests/test_stories.py -k "not counts and not mixed"`. Expected: PASS.

- [ ] **Step 4: Write batch B** the same way.

- [ ] **Step 5: Run the story, pipeline and gold tests**

Run: `PYTEST tests/test_stories.py tests/test_shared_origin_pipeline.py tests/test_shared_origin_gold.py`
Expected: PASS. Record in the task report each story's broken label at
full width (Ruling 19 expects about 13 "shared" among the 38 P).

- [ ] **Step 6: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add src/kubeagent_verdict/dataset/stories.py tests/test_stories.py \
  && COMMIT "feat(dataset): the 38 P stories as worlds with the named edits"
```

---

### Task 7: The checker (exemption gone, B7, `_HEALTH_SYSTEM`), the cases builders, and generate's switch to stories

**Files:**
- Modify: `src/kubeagent_verdict/dataset/checker.py` — docstring :17-31; delete `EXEMPT_CASES`, `EVIDENCE_RULES`, `PROPAGATION_TEXT_RULES` :179-196; `_HEALTH_SYSTEM` :232; `_b7` :956-1035; delete the skip in `check()` :2049-2063.
- Modify: `src/kubeagent_verdict/dataset/cases.py` — `shared_origin` :1126, `shared_origin_decoy` :1156 (and the two probe builders beside them); delete `_render_shared_origin` :920-1123 and the `origin_read_label` writes :1152, :1190.
- Modify: `src/kubeagent_verdict/dataset/generate.py` — the `TYPE_CHECKING` import :20-21; the `CASE_MIX` comment (after :99); the `HELD_OUT_CASES` comment :110-115; the import :134; the shared-origin loop :246-283 (the 2026-09-19 comment :229-245 stays); the probe comments :514-528; `shared_origin_probes` and `shared_origin_decoy_probes` :532-576; `_shared_origin_twin_pairs` :579-605; the wide and cousin probes :609-661.
- Modify: `tests/test_checker.py` — imports :27; docstring :9; `_source` :281-286; the crash-fix picker :318-319; the exemption block :571-625; the meta-none picker :663-665; the `COPIES` entry :768-769.
- Modify: `tests/test_generate.py` — `_HEADER_EXEMPT` :1102-1105; the skip at :1127 (the assert at :1140 stays as it is); `import hashlib`; append the `OTHER_FAMILIES_SHA256` guard and `test_the_other_families_exam_rows_did_not_move`.
- Test: `tests/test_checker.py`, `tests/test_generate.py`, `tests/test_shared_origin_pool.py` (new)

Why `generate.py` and the two old test files move in this task: the
builders' first argument becomes a `stories.Story`, and the checker loses
`EXEMPT_CASES`. Without the generate switch, `generate.generate` hands
`Propagation` objects to the new builders and fails. Without the test
edits, `tests/test_checker.py` fails at import (`COPIES` reads
`checker.EXEMPT_CASES` when the module loads), and `tests/test_generate.py`
skips a set of cases the checker no longer has.

**Interfaces:**
- Consumes: `shared_origin.draw/build`, `gold.gold_for`, `stories.Story`, `stories.by_key()`, `stories.trainable()`, `stories.exam()`, `stories.EXAM_KEYS`; `health.Condition`; `cases._answer(rows, summary)`, `render.workload_meta`, `render.prompt_meta`; `checker.check(system, user, assistant, meta) -> Report`; `score.evaluate(rows, chat_fn, *, grade_job2=True)`.
- Produces:
  - `cases.shared_origin(p: stories.Story, rng, victims=None, unverified=False) -> Example`; `cases.shared_origin_decoy(p: stories.Story, rng, victims=None) -> Example`; `cases._shared_origin_example(case: str, built: shared_origin.Built, **extra) -> Example`; `cases.shared_origin_probe(p: stories.Story, rng, victims=None) -> Example` and `cases.shared_origin_decoy_probe(p: stories.Story, rng, victims=None) -> Example` keep their names. Row meta per Ruling 8; `meta["expected"]` is `{workload: answer cause}` as today.
  - `generate._shared_origin_twin_pairs(origins: Sequence[Story], pairs_per_origin: int, salt: str, width_of: Callable[[Story, int], int | None], error_prefix: str) -> list[Example]`.
  - The family's pools (Ruling 22): the training loop and `shared_origin_cousin_probes` walk `stories.trainable()`; `shared_origin_probes`, `shared_origin_decoy_probes` and `shared_origin_wide_probes` walk `stories.exam()`. `multi` keeps `propagation.trainable_scenarios()` (generate.py:152).
  - `tests/test_shared_origin_pool.py:full_marks_misses(examples) -> list[str]`. Task 8 appends its whole-family test to the same file and calls it there (tests cannot import each other here: there is no `__init__.py` or `conftest.py`).

- [ ] **Step 1: Write the failing tests and drop the old exemption pins**

In `tests/test_checker.py`:

Replace the import at :27 with these two lines, and add
`from dataclasses import replace` after `from collections import Counter`
(:21):

```python
from kubeagent_verdict.dataset import (cases, checker, gather, generate, health, objects, render,
                                       rules, stories)
```

In the module docstring, replace the line
`- the exemptions stay exactly as ruled;` (:9) with
`- no case is exempt: the shared-origin family is checked by every rule;`.

Replace `_source` (:281-286) with `_family` and the new `_source`:

```python
# `_source` and two other pickers keep skipping the shared-origin family so
# each broken copy keeps the source row it had before Spec 4b-1 (the other
# families' rows are byte-identical). The family's own rows are checked by
# test_shared_origin_row_passes_every_rule and the manifest test.
def _family(row: dict) -> bool:
    return row["meta"]["case"].startswith("shared_origin")


def _source(pick, seed_rows) -> tuple:
    if pick is None:
        return _golden()
    row = next(r for r in seed_rows if not _family(r) and pick(r))
    return _parts(row)
```

In `test_a_crash_findings_logs_command_names_its_own_container`, replace
its picker (:318-319) with:

```python
    row = next(r for r in seed_rows
               if not _family(r) and _CRASH_FIX.search(r["messages"][1]["content"]))
```

In `test_meta_none_skips_only_ans1s_meta_clause_and_ans2`, replace its
picker (:663-665) with:

```python
    row = next(r for r in seed_rows
               if not _family(r)
               and not r["meta"].get("origin_read_label") and _has_own_keywords(r))
```

Replace :571-625 — from the line
`# --- the exemptions ---…` through the end of
`test_each_propagation_text_rule_still_fires_with_the_exemption_off` — with
the block below. It deletes the three pin tests and the old "still fires
with the exemption off" test, and keeps `_SKIPS_THE_HEALTHY_READ` and
`test_a_healthy_read_is_not_flagged_by_the_rules_that_exempt_it` unchanged
under a new heading:

```python
# --- no exemptions (Spec 4b-1) --------------------------------------------

# The 19 rules the shared-origin family skipped until Spec 4b-1 (the old
# EVIDENCE_RULES and PROPAGATION_TEXT_RULES). The family's rows now pass them.
_ONCE_EXEMPT = frozenset({"E1", "E2-order", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10",
                          "E-min", "D3", "B1", "C1-conf", "C1-cause", "C5/D4", "D1-onefresh",
                          "TXT-IS9", "TXT-IS11"})


def test_each_once_exempt_rule_still_fires_on_its_own_bad_row(seed_rows):
    """Each rule still fires on a bad row built for it (its BROKEN copy), and
    a bad row whose meta names a shared-origin case fails the same way: no
    case name turns a rule off."""
    assert _ONCE_EXEMPT <= set(BROKEN)
    for rule in sorted(_ONCE_EXEMPT):
        pick, brk = BROKEN[rule]
        system, user, assistant, meta = brk(*_source(pick, seed_rows))
        assert rule in _fired(checker.check(system, user, assistant, meta)), rule
        if meta is not None:
            for case in ("shared_origin", "shared_origin_decoy", "shared_origin_probe",
                         "shared_origin_decoy_probe"):
                fired = _fired(checker.check(system, user, assistant, {**meta, "case": case}))
                assert rule in fired, (rule, case)


# --- the healthy-origin read (multi) ----------------------------------------

# The evidence rules that walk the gathered reads (`_Ctx.gathered`), which
# leave out a healthy-origin read at index 0. The checker keeps no list of
# them: until 2026-09-28 it had one, HEALTHY_READ_EXEMPT, that no code read.
_SKIPS_THE_HEALTHY_READ = frozenset({"E2-order", "E4", "E6", "E7", "E8", "E9", "E10"})


def test_a_healthy_read_is_not_flagged_by_the_rules_that_exempt_it(seed_rows):
    """Recognised by its label at index 0, the read passes every rule. Drop
    the label from meta and the same read is one of the gathered reads, and
    the rules that walk those fail it: it is no workload's events read."""
    system, user, assistant, meta = _parts(_healthy_row(seed_rows))
    assert _where(checker.check(system, user, assistant, meta)) == []
    bare = {k: v for k, v in meta.items() if k != "origin_read_label"}
    fired = _fired(checker.check(system, user, assistant, bare))
    assert fired
    assert fired <= _SKIPS_THE_HEALTHY_READ
```

Delete the `"EXEMPT_CASES (test_generate)"` entry of `COPIES` (:768-769):
`_HEADER_EXEMPT` leaves `tests/test_generate.py` below, and the entry
reads `checker.EXEMPT_CASES` when the module loads.

Append to `tests/test_checker.py`:

```python
# --- the shared-origin family (Spec 4b-1) ---------------------------------

def _so_row(key="node-not-ready", seed=1):
    return cases.shared_origin(stories.by_key()[key], random.Random(seed))


def _rule_fails(ex, user, rule):
    rep = checker.check(ex.system, user, ex.assistant, ex.meta)
    return [v for v in rep.violations if v.rule == rule]


def test_shared_origin_row_passes_every_rule():
    for key in ("node-not-ready", "coredns-down", "networkpolicy-deny-all"):
        ex = _so_row(key)
        rep = checker.check(ex.system, ex.user, ex.assistant, ex.meta)
        assert not rep.violations, (key, rep.violations)


def test_no_exemption_names_remain():
    for name in ("EXEMPT_CASES", "EVIDENCE_RULES", "PROPAGATION_TEXT_RULES"):
        assert not hasattr(checker, name)
    assert len(checker.RULES) == 50


def test_health_system_status_may_hold_spaces():
    for text in ("  system kube-system/backup Last run failed",
                 "  system kube-system/metrics-server 0/0 Scaled Down",
                 "  system kube-system/nightly BackoffLimitExceeded (3 of 3 failed)"):
        m = checker._HEALTH_SYSTEM.match(text)
        assert m, text
    m = checker._HEALTH_SYSTEM.match("  system kube-system/coredns 0/2 CrashLoopBackOff")
    assert m.group(2, 3, 4) == ("0", "2", "CrashLoopBackOff")


def _swap_first_two_node_lines(user, node):
    lines = user.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith(f"  node {node} ")]
    assert len(idx) >= 2
    lines[idx[0]], lines[idx[1]] = lines[idx[1]], lines[idx[0]]
    return "\n".join(lines) + "\n"


def test_b7_mutations():
    st = stories.by_key()["node-not-ready"]
    # The broken node gets a second line: PIDPressure prints before NotReady.
    pid = replace(st, broken=replace(st.broken, conditions=(
        health.Condition("PIDPressure", "True", "", ""), *st.broken.conditions)))
    ex = cases.shared_origin(pid, random.Random(1))
    node = ex.meta["scope_value"]
    assert not _rule_fails(ex, ex.user, "B7")
    # wrong order inside a node
    assert _rule_fails(ex, _swap_first_two_node_lines(ex.user, node), "B7")
    # a down line with no candidate
    extra = ex.user.replace(f"  node {node} NotReady",
                            f"  node worker-9 NotReady\n  node {node} NotReady", 1)
    assert _rule_fails(ex, extra, "B7")
    # a header total below the named nodes
    low = re.sub(r"— (\d+)/(\d+) nodes Ready", "— 0/1 nodes Ready", ex.user, count=1)
    assert _rule_fails(ex, low, "B7")
    # a header with no lines
    bare = "\n".join(ln for ln in ex.user.splitlines()
                     if not ln.startswith(("  node ", "  system "))) + "\n"
    assert _rule_fails(ex, bare, "B7")
```

In `tests/test_generate.py`, delete the comment and `_HEADER_EXEMPT`
(:1102-1105), in the same commit as the `COPIES` entry above. In
`test_every_job2_header_follows_kubeagents_rule`, replace only the skip
(:1127) with:

```python
        if "== BEGIN candidates ==" not in ex.user:
```

Keep the last assert (:1140) exactly as it is:
`{"multi", "multi_misattribution_probe", "wrong_attribution"} <= set(checked)`.
Do not add `"shared_origin"` to it. Family rows that have a job-2 workload
with a candidate are held to the header rule whenever they occur. The
family's R rows are rules-decided (job 1), whether confirmed or unverified
(Ruling 31), so they are not job 2. Whether a P row shows a candidate
depends on its story, so the test does not require the family to appear.

Also in `tests/test_generate.py`, add `import hashlib` to the imports
(between `import collections` and `import json`), and append this guard at
the end of the file. It pins the 229 exam rows outside the family. It
passes before this task and must still pass after it: the rewrite moves
only the 20 family rows (spec "Done when": "229 rows byte-identical").

```python
# 2026-10-03 (Spec 4b-1): measured on main @ ff6527e. The rewrite moves
# only the 20 shared-origin exam rows; the other 229 must not move.
OTHER_FAMILIES_SHA256 = "09de3501feceaab8ec014e7ccc5d187c3d88af50deef63dd030ef9cbaa87895a"


def test_the_other_families_exam_rows_did_not_move():
    other = [e for e in generate.test_set() if not e.case.startswith("shared_origin")]
    assert len(other) == 229
    blob = json.dumps([generate.to_row(e) for e in other], sort_keys=True, ensure_ascii=False)
    assert hashlib.sha256(blob.encode("utf-8")).hexdigest() == OTHER_FAMILIES_SHA256
```

If this test ever fails, a row outside the family moved. Do not re-pin
it: stop and report BLOCKED with the first differing row's `case` and
`group`.

Create `tests/test_shared_origin_pool.py` — the pool check: every built
row, answered with its own gold, gets full marks from the real grader with
job-2 grading on. It feeds `score.evaluate` the way
`tests/test_oracle.py:_gold_results` (:40-62) does: rows from
`generate.to_row`, and a `chat_fn` that returns each row's own gold in
order. Task 8 runs the same check over every family row of the build.

```python
import random

import pytest

from kubeagent_verdict.dataset import cases, generate, stories
from kubeagent_verdict.evals import score


def full_marks_misses(examples) -> list[str]:
    """Every row whose own gold, read back as the model's reply, loses a
    mark: contract, a decoy named, or any job-1, job-2 or job-3 score
    below 1.0. G2 and G3b gate the job-2 scores, so they are covered."""
    rows = [generate.to_row(e) for e in examples]
    gold = iter(r["messages"][2]["content"] for r in rows)
    results = score.evaluate(rows, lambda _messages: next(gold), grade_job2=True)
    misses = []
    for e, r in zip(examples, results):
        bad = [name for name, ok in (
            ("contract", r["contract_ok"]),
            ("decoy", not r["named_decoy"]),
            ("job1", all(s == 1.0 for s in r["job1_scores"])),
            ("job2", all(s == 1.0 for s in r["job2_scores"])),
            ("job3", r["job3"] in (None, 1.0))) if not ok]
        if bad:
            misses.append(f"{e.case} {e.group}: {bad}")
    return misses


@pytest.mark.parametrize("key", ["node-not-ready", "coredns-down", "networkpolicy-deny-all"])
def test_gold_scores_full_marks(key):
    st = stories.by_key()[key]
    exs = [cases.shared_origin(st, random.Random(3)),
           cases.shared_origin_decoy(st, random.Random(3))]
    assert full_marks_misses(exs) == []


def test_a_wrong_answer_loses_marks():
    """The check can fail: the healthy twin's gold, sent as the broken
    twin's reply, must lose a mark."""
    st = stories.by_key()["node-not-ready"]
    broken = cases.shared_origin(st, random.Random(3))
    healthy = cases.shared_origin_decoy(st, random.Random(3))
    row = generate.to_row(broken)
    [r] = score.evaluate([row], lambda _m: healthy.assistant, grade_job2=True)
    assert not (all(s == 1.0 for s in r["job1_scores"] + r["job2_scores"])
                and r["job3"] in (None, 1.0))


def test_generate_builds_the_family_from_stories():
    """Training draws only trainable stories, the exam only the six exam
    stories, and no family row carries an origin read label."""
    by = stories.by_key()
    train = [e for e in generate.generate(17, 200) if e.case.startswith("shared_origin")]
    exam = [e for e in generate.test_set() if e.case.startswith("shared_origin")]
    assert train and len(exam) == 20
    for e in train + exam:
        assert e.meta["origin"] in by
        assert "origin_read_label" not in e.meta
    assert {e.meta["origin"] for e in exam} == {st.key for st in stories.exam()}
    assert not {e.meta["origin"] for e in train} & set(stories.EXAM_KEYS)
```

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/test_checker.py tests/test_shared_origin_pool.py tests/test_generate.py::test_every_job2_header_follows_kubeagents_rule tests/test_generate.py::test_the_other_families_exam_rows_did_not_move`
Expected: FAIL —
- the four `_so_row`/`test_b7_mutations`/pool builder tests: `cases.shared_origin` still takes a `Propagation` (an AttributeError such as `origin_object`);
- `test_no_exemption_names_remain`: `EXEMPT_CASES` still exists;
- `test_health_system_status_may_hold_spaces`: no match on "Last run failed";
- `test_each_once_exempt_rule_still_fires_on_its_own_bad_row`: the copy relabelled `shared_origin` is skipped by the old exemption;
- `test_generate_builds_the_family_from_stories`: old rows carry `origin_read_label`;
- `test_every_job2_header_follows_kubeagents_rule`: it may fail on the old rows' hand-passed headers; note what it says.

Every other test in `tests/test_checker.py` must still PASS, and
`test_the_other_families_exam_rows_did_not_move` PASSES (it is a guard,
not a red test).

- [ ] **Step 3: Rewrite the cases builders**

Replace `shared_origin` and `shared_origin_decoy` in cases.py, and delete
`_render_shared_origin` (:920-1123) and both `origin_read_label` writes:

```python
def _shared_origin_example(case: str, built: so.Built, **extra) -> Example:
    """One family row from a built world: gold from `gold.gold_for`, meta per
    Ruling 8, decoys per Ruling 12. `extra` adds case-specific meta keys."""
    g = gold.gold_for(built)
    answer_rows, metas, decoys = [], {}, {}
    for row in built.rows:
        rg = g.rows[row.key]
        cause = rg.cause if rg.verdict != "none_of_these" else "none_of_these"
        answer_rows.append({"workload": row.key, "cause": cause,
                            "confidence": rg.confidence, "rationale": rg.rationale})
        metas[row.key] = render.workload_meta(row.result, expected_cause=cause,
                                              own_cause_keywords=list(rg.keys),
                                              own_cause_must_not=[])
        decoys[row.key] = [shown.cause for d, shown in zip(row.result.decisions, row.candidates)
                           if d.outcome in ("ruled_out", "refuted")]
    meta = render.prompt_meta(metas, label=g.label, decoy_by_workload=decoys)
    st, d = built.story, built.draw
    meta.update(case=case, origin=st.key, blast_radius=st.blast_radius,
                scope_value=d.scope_value,
                expected={r["workload"]: r["cause"] for r in answer_rows},
                decoy_causes=[], **extra)
    return Example(case=case, group=built.group, system=c.SYSTEM_PROMPT, user=built.user,
                   assistant=_answer(answer_rows, g.summary), meta=meta)


def shared_origin(p: stories.Story, rng: random.Random, victims: int | None = None,
                  unverified: bool = False) -> Example:
    d = so.draw(p, rng, width=victims or len(p.victims))
    return _shared_origin_example("shared_origin",
                                  so.build(p, d, world="broken", unverified=unverified))


def shared_origin_decoy(p: stories.Story, rng: random.Random,
                        victims: int | None = None) -> Example:
    d = so.draw(p, rng, width=victims or len(p.victims))
    return _shared_origin_example("shared_origin_decoy", so.build(p, d, world="healthy"))


def shared_origin_probe(p: stories.Story, rng: random.Random,
                        victims: int | None = None) -> Example:
    d = so.draw(p, rng, width=victims or len(p.victims))
    return _shared_origin_example("shared_origin_probe", so.build(p, d, world="broken"))


def shared_origin_decoy_probe(p: stories.Story, rng: random.Random,
                              victims: int | None = None) -> Example:
    d = so.draw(p, rng, width=victims or len(p.victims))
    return _shared_origin_example("shared_origin_decoy_probe", so.build(p, d, world="healthy"),
                                  shared_claim_phrases=list(SHARED_CLAIM_PHRASES))
```

Keep each builder's docstring, edited to drop the sentences about the
made-up menu, the distractor, the origin-read label and the "separate
reasons" summary; say instead that the row comes from `stories` through
the real pipeline and that its answers are named, decided or
`none_of_these`. `meta["expected"]` keeps today's shape (workload →
answer cause): the cause-spread test and the old family tests read it.
Twins are paired on `Example.group` (Ruling 32), not on it.
The row dicts carry the same four keys `multi` passes `_answer`
(cases.py:747-748). Import `gold`, `shared_origin as so` and `stories`
at the top of cases.py. If `prop` (propagation) is then used only by
`multi`, keep the import.

Also delete the old builder's helpers. Only `_render_shared_origin` calls
them, so once it is gone they have no caller in `src/`:
`_propagation_names` (:789), `_victim_finding` (:818), `_shared_origin_row`
(:828), `_shared_origin_summary` (:859-895) and `_SharedOrigin` (:898).
Before deleting each one, run `grep -n "<name>" src/kubeagent_verdict/dataset/*.py`.
If it shows a caller outside the deleted code, keep that helper and say so
in the report. Keep `_is_node_story` (:1435), because `multi` uses it at :1482.
Keep the `_rule_rationale` alias from Task 4.
Tests that call these helpers (test_propagation.py :520-:637,
test_shared_origin_decided.py :54-:165) fail from here on. Task 9 rewrites
or deletes them.

- [ ] **Step 4: Switch generate.py to stories**

Replace the `TYPE_CHECKING` import (:20-21):

```python
if TYPE_CHECKING:
    from kubeagent_verdict.dataset.stories import Story
```

After the last line of the comment above `CASE_MIX` (:99,
"…(test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape).")
add:

```python
# 2026-10-03 (Spec 4b-1): the shared-origin halves keep 15% each, but their
# rows now come from `stories` through kubeagent's real pipeline. The twins
# no longer differ in an origin read: they are the broken and the healthy
# world of one story, and they differ in at least one printed line.
```

Replace the `shared_origin` paragraph of the `HELD_OUT_CASES` comment
(:110-115) with:

```python
# `shared_origin` is excluded for a second reason on top of `multi`'s: its
# examples come from `stories.trainable()`, and `held_out_case_set` mints its
# rows from the TRAINING pool. Listing it here would put trainable origins
# into the test set -- the leak the split exists to prevent, arriving by the
# other door. The eval's shared-origin rows come from `probe_sets` and draw
# only from `stories.exam()`.
```

Change the import in `generate` (:134) to
`    from kubeagent_verdict.dataset import cases, catalog, propagation, stories`.
Keep `train_scen = propagation.trainable_scenarios()` (:152): `multi`
still uses it.

Replace the loop from `    plain = tuple(p for p in train_scen if p.origin_object is None)`
(:246) through the decoy append (:283) with the block below. The
2026-09-19 comment above it (:229-245) stays as history.

```python
    # 2026-10-03 (Spec 4b-1): the pools are `stories.trainable()`, 35 plain
    # stories then 6 ruled ones (`cls == "R"`), about 27 pairs per plain story
    # and 40 per ruled story at size 8000.
    pool = stories.trainable()
    plain = tuple(st for st in pool if st.cls == "P")
    ruled = tuple(st for st in pool if st.cls == "R")
    for i in range(counts["shared_origin"]):
        if i % 5 == 4:
            j = i // 5
            p = ruled[j % len(ruled)]
            t = j // len(ruled)
            # Vary the width the way `probe_sets` does: a row that always
            # renders every victim teaches the count, not the reasoning.
            victims = 2 + (t // 3) % (len(p.victims) - 1)
            unverified = p.origin_kind == "node" and t % 3 == 2
        else:
            k = i - (i + 1) // 5
            p = plain[k % len(plain)]
            victims = 2 + (k // len(plain)) % (len(p.victims) - 1)
            unverified = False
        # ONE salt, drawn once and spent twice. Two `random.Random` objects
        # built from the same seed replay the same stream, so the twins make
        # the same draws (`shared_origin.draw` draws everything before it
        # branches on the world). Only the world differs -- broken or healthy --
        # and with it at least one printed line and the answer: the pair is a
        # minimal contrast in the curriculum, the same instrument the exam uses.
        #
        # `unverified` never applies to the decoy twin: the healthy world has
        # no origin candidate, so there is no "could not check" world for it.
        #
        # This loop emits both halves, so it runs `counts["shared_origin"]`
        # times and not once per row. `counts["shared_origin_decoy"]` is spent
        # here too, by the twin; the two entries hold equal shares, so the
        # budget still sums to `size`.
        salt = rng.getrandbits(64)
        out.append(cases.shared_origin(p, random.Random(salt), victims=victims,
                                       unverified=unverified))
        out.append(cases.shared_origin_decoy(p, random.Random(salt), victims=victims))
```

The loop draws exactly one `rng.getrandbits(64)` per pair, as before, so
the main stream and every non-family row stay byte-identical.

Replace the probe comment (:514-517) with:

```python
    # These rows come from `dataset.stories` (`dataset.propagation` until
    # 2026-10-03), not from the catalog, so they share no group namespace with
    # any training row: every group is still prefixed `propagation:`,
    # `drop_held_out` drops nothing, and no training example is lost to the
    # slice.
```

Insert directly above `    out.extend(shared_origin_decoy_probes())`
(:529), after the comment that ends "…the training set does not move.":

```python
    # 2026-10-03 (Spec 4b-1): no family row carries an origin read label any
    # more. Each twin pair is the broken and the healthy world of one story.
```

Replace `shared_origin_probes` and `shared_origin_decoy_probes`
(:532-576) with:

```python
def shared_origin_probes() -> list[Example]:
    """EVAL-ONLY: one row per exam story, plus narrower subsets.

    Full-width rows come first and subset rows after, so dropping the subsets
    later would leave the first six at their original indices. A subset exists
    only where a story has a victim to spare: it renders the same origin at
    two workloads instead of three or four, which is what tells a two-workload
    failure apart from a genuinely wide one when the scoreboard is read by
    victim count.
    """
    from kubeagent_verdict.dataset import cases, stories

    out: list[Example] = []
    for p in stories.exam():
        out.append(cases.shared_origin_probe(p, _entry_rng("shared-origin", p.key)))
    for p in stories.exam():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
    return out


def shared_origin_decoy_probes() -> list[Example]:
    """EVAL-ONLY: `shared_origin_probes` in each story's healthy world.

    Same stories, same order, same widths — and the SAME two rng salts, which
    is what makes each row a minimal contrast with its twin rather than a
    second question about the same cluster. Identical salts give identical
    draws; only the world differs (healthy instead of broken), and with it at
    least one printed line and the answer.
    """
    from kubeagent_verdict.dataset import cases, stories

    out: list[Example] = []
    for p in stories.exam():
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin", p.key)))
    for p in stories.exam():
        if len(p.victims) < 3:
            continue
        out.append(cases.shared_origin_decoy_probe(
            p, _entry_rng("shared-origin-pair", p.key), victims=2))
    return out
```

Replace `_shared_origin_twin_pairs` (:579-605) whole. The pair key moves
from the expected workloads to `Example.group` (Ruling 32): the broken
world adds an origin row for some stories (coredns-down's
`kube-system/coredns`), so the twins' expected workloads can differ, but
their group names only the victims and is the same in both worlds.

```python
def _shared_origin_twin_pairs(origins: Sequence[Story], pairs_per_origin: int,
                              salt: str, width_of: Callable[[Story, int], int | None],
                              error_prefix: str) -> list[Example]:
    """Build twin pairs (a probe row and its decoy) over a list of stories.

    Both halves of a pair use the same salted rng, so they draw the same
    values and differ only in the world (broken or healthy). `width_of(p, i)`
    picks the victim count for pair `i` of story `p`; returning `None`
    means the full victim set. A pair is keyed on its group, which names
    the victims and is the same in both worlds. A repeated group would merge
    two pairs in the paired scoring, so it raises instead.
    """
    from kubeagent_verdict.dataset import cases

    out: list[Example] = []
    seen: dict[str, str] = {}
    for p in origins:
        for i in range(pairs_per_origin):
            width = width_of(p, i)
            probe = cases.shared_origin_probe(
                p, _entry_rng(salt, p.key, str(i)), victims=width)
            decoy = cases.shared_origin_decoy_probe(
                p, _entry_rng(salt, p.key, str(i)), victims=width)
            assert probe.group == decoy.group, (probe.group, decoy.group)
            key = probe.group
            if key in seen:
                raise ValueError(
                    f"{error_prefix} pair key collision: {seen[key]} and "
                    f"{p.key}#{i} both drew {key!r}; a collision would "
                    "merge two pairs in the paired scoring")
            seen[key] = f"{p.key}#{i}"
            out.append(probe)
            out.append(decoy)
    return out
```

In the docstrings of `shared_origin_wide_probes` (:629) and
`shared_origin_cousin_probes` (:655), "pair key" now means the group:
change "A repeated pair key" to "A repeated group" wherever it appears.

In `shared_origin_wide_probes` (:609-637), replace
"(same names, same menus, same read labels -- only the read contents and
the answer differ)" with "(same draws -- only the world, at least one
printed line and the answer differ)", "where the scenario has a victim to
spare" with "where the story has a victim to spare", and the body with:

```python
    from kubeagent_verdict.dataset import stories

    return _shared_origin_twin_pairs(
        stories.exam(), pairs_per_origin, "shared-origin-wide",
        lambda p, i: 2 if i % 2 == 1 and len(p.victims) >= 3 else None,
        "wide-probe")
```

In `shared_origin_cousin_probes` (:640-661), replace "One pair per
trainable scenario, at full width, so every decoy half carries three or
four verdicts, which is the shape the 0907 model broke its JSON on." with
"One pair per trainable story, at full width (every victim the story
has). Every trainable story has three or more victims (Ruling 50), so
every decoy half carries three or more verdicts, the shape the 0907
model broke its JSON on.",
and the body with:

```python
    from kubeagent_verdict.dataset import stories

    return _shared_origin_twin_pairs(
        stories.trainable(), pairs_per_origin,
        "shared-origin-cousin", lambda p, i: None, "cousin-probe")
```

After this step `grep -n "propagation" src/kubeagent_verdict/dataset/generate.py`
shows only the import, `train_scen` (:152), the `multi` code that uses it,
and the history comments.

- [ ] **Step 5: Change the checker**

Delete `EXEMPT_CASES`, `EVIDENCE_RULES`, `PROPAGATION_TEXT_RULES`
(:179-196) and the skip in `check()` (:2049-2063). In the docstring
(:17-31) replace the exemption paragraph with: "Every case, shared-origin
included, is checked by all 50 rules." Set

```python
_HEALTH_SYSTEM = re.compile(r"^  system kube-system/(\S+) (?:(\d+)/(\d+) )?(.+)$")
```

Replace `_b7` with:

```python
# Inside one node: pressure, NotReady, SchedulingDisabled, lease
# (clusterhealth/clusterhealth.go:60-110).
_NODE_LINE_ORDER = ("MemoryPressure", "DiskPressure", "PIDPressure", "NotReady",
                    "SchedulingDisabled", "no kubelet lease", "kubelet not heartbeating",
                    "expected but absent from the cluster")


def _node_rank(issue: str) -> int:
    return next(i for i, p in enumerate(_NODE_LINE_ORDER) if issue.startswith(p))


def _b7(x: _Ctx) -> tuple[int, _Finding]:
    """The cluster-health block, as kubeagent prints it: several lines per
    node in a fixed order, a down line only with its candidate, a header
    total at least the nodes it names, never header-only."""
    blocks = x.p.blocks
    truncated = any(b.truncated for b in blocks)
    nodes: dict[str, set[str]] = {}
    for b in blocks:
        for cd in b.cands:
            s = _shape(cd.cause)
            if s and s[0] == "node":
                nodes.setdefault(s[1], set()).add(s[2])
    system = [e for e in x.p.entries if e.ns == SYSTEM_NAMESPACE]
    h = x.p.health
    lines = [(ln, _HEALTH_NODE.match(ln.text)) for ln in h[1:]]
    node_lines = [(ln, m) for ln, m in lines if m]
    where = f"inventory line {h[0].no}" if h else "inventory"
    if (nodes or system) and not h:
        return 1, [(where, "no cluster-health block")]
    if not h:
        return 1, []
    out = []
    if len(h) == 1:
        out.append((where, "a cluster-health header with no lines"))
    keys = [(m.group(1), _node_rank(m.group(2))) for _, m in node_lines]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        out.append((where, "node lines are not in name order, then pressure, NotReady, "
                           "SchedulingDisabled, lease"))
    down = [(ln, m) for ln, m in node_lines if m.group(2).startswith(_DOWN_ISSUES)]
    for ln, m in down:
        if m.group(1) not in nodes and not truncated:
            out.append((f"inventory line {ln.no}", ln.text))
    by_name = {m.group(1): m.group(2) for _, m in down}
    for name, reasons in sorted(nodes.items()):
        want = ("NotReady" if "NotReady" in reasons else
                "no kubelet lease" if "no kubelet lease" in reasons else "kubelet not heartbeating")
        got = by_name.get(name, "")
        if not (got.startswith(want) and (want != "NotReady" or got == want
                                          or got.startswith("NotReady: "))):
            out.append((where, f"node {name} ({want}): {got or 'no line'}"))
    named = {m.group(1) for _, m in node_lines}
    head = _HEALTH_HEADER.match(h[0].text)
    if head and int(head.group(2)) < len(named):
        out.append((where, f"at least {len(named)} nodes expected: {h[0].text}"))
    want_sys = []
    for e in system:
        if not e.match:
            continue
        ready, desired, status = e.match.group(4), e.match.group(5), e.match.group(6)
        if e.kind in ("Job", "CronJob"):
            want_sys.append(f"  system {e.ns}/{e.name} {status}")
        else:
            want_sys.append(f"  system {e.ns}/{e.name} {ready}/{desired} {status}")
    got_sys = [ln.text for ln, m in lines if not m]
    ok = (got_sys[:len(want_sys)] == want_sys if len(x.p.entries) >= MAX_GATHER_WORKLOADS
          else got_sys == want_sys)
    if not ok:
        out.append((where, f"system lines {got_sys} expected {want_sys}"))
    return len(h), out
```

`_DOWN_ISSUES` is defined after `_b7` today; move it above `_b7`.
`_B7_MIN_NODES` loses its last reader: delete it and its comment.

- [ ] **Step 6: Run the checker, generate and pool tests**

Run: `PYTEST tests/test_checker.py tests/test_generate.py tests/test_shared_origin_pool.py tests/test_stories.py tests/test_shared_origin_gold.py tests/test_shared_origin_pipeline.py`
Expected:
- every test in `tests/test_checker.py` PASSES, including
  `test_the_exam_pool_passes` and `test_the_manifest_reports_the_checkers_counts`,
  which now run the 50 rules over real family rows and must report 0
  violations, and the old B5 and B7 mutation tests with their old
  messages (if one fails only on message text, keep the old text in the
  new `_b7`);
- `tests/test_shared_origin_pool.py`, `tests/test_stories.py`,
  `tests/test_shared_origin_gold.py`, `tests/test_shared_origin_pipeline.py`,
  `test_every_job2_header_follows_kubeagents_rule` and
  `test_the_other_families_exam_rows_did_not_move` PASS (if the guard
  fails, a non-family exam row moved: stop and report BLOCKED);
- other `tests/test_generate.py` tests that pin the old family (origin
  read labels, origin variants, the `propagation` pools) may FAIL. Task 9
  rewrites them. List each failing test in the task report; every
  `tests/test_generate.py` test that does not touch the family must PASS.

Then run: `PYTEST tests/test_multi_collision.py tests/test_cases.py`
Expected: PASS. `multi` and every other case are untouched, so a failure
here is a regression in this task, not old family pins.

Then run the whole suite once: `PYTEST`
Expected: failures only in the files Task 9 lists (the old family pins),
in the three hash pins Task 10 re-pins (`FROZEN_SLICE_SHA256`,
`EVAL_SET_SHA256`, `GRADED_VIEW_SHA256`, four tests), and in
`tests/test_exam_prompt_stability.py::test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam`,
whose bank Task 10 re-points. Write the failing test names,
grouped by file, into the task report. Task 9 works from that list.

If a rule fires on a family row, the row is wrong, not the rule. Fix the
module that printed the line (`shared_origin.py` or `gold.py`), add a
test for that case to `tests/test_shared_origin_pipeline.py` or
`tests/test_shared_origin_gold.py`, and never edit a rule other than
`_b7` and `_HEALTH_SYSTEM`. If the fix is not clear, stop and report
BLOCKED with the rule, the row's group and the line.

- [ ] **Step 7: Lint and commit**

If Step 6 changed `shared_origin.py`, `gold.py` or their tests, add those
files by name to the `git add` below as well.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add src/kubeagent_verdict/dataset/checker.py src/kubeagent_verdict/dataset/cases.py \
       src/kubeagent_verdict/dataset/generate.py tests/test_checker.py tests/test_generate.py \
       tests/test_shared_origin_pool.py \
  && COMMIT "feat(checker): no shared-origin exemption, B7 for real health blocks; family built from stories"
```

---

### Task 8: The mix — BIG, the training-mix tests, the floor rewrite, and the whole-family checks

**Files:**
- Modify: `tests/test_shared_origin_training.py` — imports :47-48; the constants :1236-1255; `test_big_deals_exactly_draws_rows_per_scenario` :1263-1271; `test_the_trainable_pool_exercises_every_issue_kind` :1274-1280; `EXPECTED_POOL` and its test :1287-1294; `test_every_trainable_scenario_is_taught_equally` :1391-1416; delete `test_every_trainable_scenario_renders_at_least_three_origin_variants` :1419-1442; `test_no_shared_origin_cause_dominates_the_curriculum` :1445-1475.
- Rewrite: `tests/test_shared_origin_floor.py` (whole file).
- Modify: `tests/test_shared_origin_pool.py` (made in Task 7) — imports at the top; append the whole-family checks.
- No production code. Task 9 never touches the floor or pool files (Ruling 28).

Line numbers are from main @ ff6527e. Find each test by its name.

**Interfaces:**
- Consumes: `stories.trainable() -> tuple[Story, ...]` (35 P, then 6 R), `stories.by_key()`, `Story.key`, `.cls`, `.blast_radius`, `.victims` (each `VictimText` has `.issue`); `generate.generate`, `split`, `drop_held_out`, `test_set`, `counts_for`, `to_row`, `shared_origin_probes`, `shared_origin_decoy_probes`, `shared_origin_wide_probes`, `shared_origin_cousin_probes`; `checker.check_row(row) -> Report` (`.inspected: dict[str, int]`), `checker.RULES`, `checker.LOG_CAUSES`, `checker.LOG_CAUSE_PREFIX`; `gold.own_lines(user, workloads)`; `score._own_blocks`, `score._keywords_match(cause, keywords, must_not)`; `full_marks_misses(examples)` (Task 7, same file); `contract.NONE_OF_THESE`.
- Row facts it relies on: `Example.group` is the same in both twins (Ruling 32); the training loop and `_shared_origin_twin_pairs` append the broken half then its healthy twin; `split` and `drop_held_out` move a whole group at once; `shared_origin_probes()` and `shared_origin_decoy_probes()` walk the same stories in the same order. Meta per Ruling 8: `meta["workloads"][w]` has `job`, `decided_outcome`, `own_cause_keywords`; `meta["expected"]`, `meta["label"]`, `meta["decoy_by_workload"]`, `meta["origin"]`.
- Produces: nothing later tasks call. Task 11 copies the numbers this task's report prints into `contract/PIN.md`.

- [ ] **Step 1: Run the old mix tests to see them fail**

Run: `PYTEST tests/test_shared_origin_floor.py "tests/test_shared_origin_training.py::test_every_trainable_scenario_is_taught_equally" "tests/test_shared_origin_training.py::test_every_trainable_scenario_renders_at_least_three_origin_variants"`
Expected: FAIL. After Task 7 the family draws from `stories.trainable()` (41 keys), so the floor test finds 0 rows for the 13 dropped keys, the equal-shares test sees 41 keys where it expects 54, and the variants test raises `KeyError` or `AttributeError` (stories have no `origin_variants`).

- [ ] **Step 2: Edit the training-mix tests**

In `tests/test_shared_origin_training.py`, replace the two imports (:47-48) with:

```python
from kubeagent_verdict import contract, vocab
from kubeagent_verdict.dataset import generate, propagation, stories
```

Replace the two constant lines (:1236-1237) with the lines below, and
keep the 2026-09-19 comment under them as history. Then change
`BIG = 13200` (:1255) to `BIG = 14000`.

```python
DRAWS = 48  # plain-story shared_origin rows per story at BIG; see below.
RULED_DRAWS = 70  # ruled-story shared_origin rows per story at BIG.
# 2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, 35 plain
# stories (`cls == "P"`) then 6 ruled ones (`cls == "R"`). 15% of 14000 is
# 2100 pairs: four in five go to the plain stories (1680 = 35 x 48) and one
# in five to the ruled ones (420 = 6 x 70). Origin variants are gone, so the
# sampling argument below no longer applies: the two numbers now pin only
# the equal shares inside each pool. The comment below is history.
```

Replace `test_big_deals_exactly_draws_rows_per_scenario` (:1263-1271) with:

```python
def test_big_deals_exactly_draws_rows_per_scenario():
    """`BIG` promises DRAWS plain-story rows and RULED_DRAWS ruled-story
    rows per story, not one uniform rate over the whole pool (spec
    section 7 ruling A: "within each pool every story gets an equal share",
    checked per pool, not across them). Re-measured 2026-09-19, Task 9.
    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, split on
    `Story.cls`."""
    pool = stories.trainable()
    plain = sum(1 for st in pool if st.cls == "P")
    ruled = sum(1 for st in pool if st.cls == "R")
    assert (plain, ruled) == (35, 6)
    assert generate.counts_for(BIG)["shared_origin"] == DRAWS * plain + RULED_DRAWS * ruled
```

Replace `test_the_trainable_pool_exercises_every_issue_kind` (:1274-1280) with:

```python
def test_the_trainable_pool_exercises_every_issue_kind():
    """A kind absent from the curriculum is a kind the shared-origin rule was
    never taught over -- and `vocab.ISSUE_KINDS` is what the eval draws from.

    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`. Measured
    before the named edits, the 41 kept stories' victims cover all 16 kinds;
    three of them (Init:ErrImagePull, Init:ImagePullBackOff, Init:OOMKilled)
    rest on one victim each.
    """
    seen = {v.issue for st in stories.trainable() for v in st.victims}
    missing = sorted(set(vocab.ISSUE_KINDS) - seen)
    assert not missing, f"no trainable story exercises: {missing}"
```

Replace `EXPECTED_POOL = 54` and its test (:1287-1294) with the lines
below. The four comment lines above `EXPECTED_POOL` (:1283-1286) stay.

```python
# On 2026-10-03 (Spec 4b-1) the family moved to `stories.trainable()`: the
# 12 X stories and runtime-class-removed left it, 54 to 41 (35 plain, then 6
# ruled). `multi` keeps `propagation.trainable_scenarios()`, still 54.
EXPECTED_POOL = 41


def test_the_trainable_pool_holds_the_planned_count():
    """The pool is pinned so a story cannot fall out of the tuple unseen."""
    pool = stories.trainable()
    assert len(pool) == EXPECTED_POOL
    assert len({st.key for st in pool}) == EXPECTED_POOL
    assert [st.cls for st in pool] == ["P"] * 35 + ["R"] * 6
    assert len(propagation.trainable_scenarios()) == 54
```

In `test_every_trainable_scenario_is_taught_equally` (:1391-1416), add
this paragraph at the end of the docstring:

```text
    2026-10-03 (Spec 4b-1): the pool is `stories.trainable()`, split on
    `Story.cls`, and the shares are pinned exactly: DRAWS for every plain
    story and RULED_DRAWS for every ruled one.
```

and replace its body with:

```python
    pool = stories.trainable()
    plain_keys = {st.key for st in pool if st.cls == "P"}
    ruled_keys = {st.key for st in pool if st.cls == "R"}
    for case in ("shared_origin", "shared_origin_decoy"):
        counts = Counter(e.meta["origin"] for e in big_rows if e.case == case)
        assert set(counts) == plain_keys | ruled_keys, (
            f"{case}: {sorted((plain_keys | ruled_keys) ^ set(counts))}")
        plain_shares = {v for k, v in counts.items() if k in plain_keys}
        ruled_shares = {v for k, v in counts.items() if k in ruled_keys}
        assert plain_shares == {DRAWS}, f"{case}: plain shares {dict(counts)}"
        assert ruled_shares == {RULED_DRAWS}, f"{case}: ruled shares {dict(counts)}"
```

Delete `test_every_trainable_scenario_renders_at_least_three_origin_variants`
(:1419-1442) and the two blank lines after it. Stories have no origin
variants; this is a deletion the spec allows (the invented origin read).

In `test_no_shared_origin_cause_dominates_the_curriculum` (:1445-1475),
add this paragraph at the end of the docstring. Step 5 prints the three
numbers; write them where the sentence says:

```text
    Re-measured 2026-10-03 (Spec 4b-1: 41 stories, `BIG` = 14000).
    `none_of_these` is left out of the count: it is the answer "nothing in
    this workload's own lines says why", not a cause a model can name by
    rote, and the ceiling test in test_shared_origin_floor.py bounds it on
    its own. Measured: <the distinct count Step 5 prints> distinct causes,
    top one <top1>, top three <top3>. The bar stays 0.12 and 0.30.
```

and replace its `causes = Counter(...)` statement with:

```python
    causes = Counter(cause
                     for e in big_rows if e.case == "shared_origin"
                     for cause in e.meta["expected"].values()
                     if cause != contract.NONE_OF_THESE)
```

The three `<…>` marks above are filled in Step 5 with the printed values;
none may stay in the file.

- [ ] **Step 3: Rewrite `tests/test_shared_origin_floor.py`**

Replace the whole file with:

```python
"""Every trainable story keeps enough shared-origin pairs in TRAIN, and the
pile the model reads is balanced.

The 0906 retrain built the data at the runbook's recipe (seed 17, size 5500)
with `shared_origin` at 4% of the mix. That gave each trainable scenario
about 9 pairs before the split. The validation split takes groups by hash,
not by count, so some scenarios lost 4 of their 9 pairs to validation and
reached the optimizer with 5. The model that came out of it learned "shared
by default" on the scenarios it saw least.

This test pins a floor at the build recipe itself, after the split and after
`drop_held_out`, because that is the pile the model reads. The floor is 12
rows of each half per scenario. A share that looks generous as emitted is
not the number that matters; the surviving count is.

On 2026-09-08 the recipe moved to size 8000, both halves to 12 percent, and
the pool to forty-eight scenarios. That is 960 rows per half, 20 pairs per
scenario before the split. The smallest scenario keeps 13 pairs in train
and the largest 20. The floor stays at 12: the extra room is the point,
because the split still takes groups by hash, not by count.

Re-measured 2026-09-19 (Task 9: pool merge to fifty-four scenarios and both
halves to 15 percent, spec section 6). That is 1200 rows per half before
the split, 20 pairs per plain scenario and 40 per ruled scenario -- the
selection loop gives ruled stories roughly twice the plain per-story rate
by design (spec section 7 ruling A), not evenly across all fifty-four. The
smallest scenario keeps 15 pairs in train (a plain story) and the largest
39 (a ruled story). The floor stays at 12: it was set once, against the
smallest surviving count, and every scenario -- plain or ruled -- still
clears it with room to spare.

2026-10-03 (Spec 4b-1): the family is built from `stories.trainable()`, 41
stories (35 plain, then 6 ruled), and each workload's answer is a named
cause, a rules-decided cause or `none_of_these`. At size 8000 that is 1200
pairs before the split: 27 or 28 per plain story and 40 per ruled story.
The floor stays 12. Four checks join it, all on the same pile (Ruling 29):

- balance: the `none_of_these` share of verdicts in the broken half and in
  the healthy half differ by at most 10 points, so the world, not the
  case, tells the model when to answer `none_of_these`;
- ceiling: `none_of_these` is at most 30% of every verdict in train, so a
  model cannot score by saying it everywhere;
- the label cue: at least 5 plain stories end "shared" and at least 5 end
  "none" by majority of their broken rows, so the story does not give the
  label away;
- twins differ: no kept pair prints the same set of lines in both worlds.

If one of these misses, the fix is in the stories, never in the bar.
"""
import json
from collections import Counter

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import generate, stories

SEED, SIZE = 17, 8000  # the runbook's build recipe
FLOOR = 12
BALANCE = 0.10  # most the two worlds' none_of_these shares may differ
CEILING = 0.30  # most of all train verdicts that may be none_of_these
LABEL_CUE = 5  # fewest plain stories that must end each way

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"


@pytest.fixture(scope="module")
def train():
    rows = generate.generate(seed=SEED, size=SIZE)
    train, _val = generate.split(rows, seed=SEED)
    return generate.drop_held_out(train, generate.test_set())


def _per_origin(rows, case):
    return Counter(e.meta["origin"] for e in rows if e.case == case)


def _none_share(rows) -> tuple[int, int]:
    """(`none_of_these` verdicts, all verdicts) over `rows`."""
    verdicts = [v for e in rows for v in json.loads(e.assistant)["verdicts"]]
    return sum(v["cause"] == contract.NONE_OF_THESE for v in verdicts), len(verdicts)


def _majority(labels) -> str | None:
    """The label most rows carry. A tie counts for neither side."""
    top = Counter(labels).most_common()
    if not top or (len(top) > 1 and top[0][1] == top[1][1]):
        return None
    return top[0][0]


def _pairs(rows):
    """The kept twins, in order. The training loop appends each broken half
    and its healthy twin back to back, and `split` and `drop_held_out` move
    a whole group at once, so adjacent family rows are twins."""
    fam = [e for e in rows if e.case in (SHARED, DECOY)]
    assert len(fam) % 2 == 0, len(fam)
    out = list(zip(fam[::2], fam[1::2]))
    for a, b in out:
        assert (a.case, b.case) == (SHARED, DECOY), (a.case, b.case)
        assert a.group == b.group, (a.group, b.group)
    return out


def test_every_trainable_story_keeps_the_floor_in_train(train):
    keys = [st.key for st in stories.trainable()]
    shared = _per_origin(train, SHARED)
    decoy = _per_origin(train, DECOY)
    short = {k: (shared[k], decoy[k]) for k in keys
             if shared[k] < FLOOR or decoy[k] < FLOOR}
    assert short == {}, (
        f"stories below {FLOOR} probe/decoy rows in train "
        f"(shared, decoy): {short}")


def test_the_two_halves_survive_the_split_together(train):
    """The pair shares a group key, so the split can never take one half."""
    assert _per_origin(train, SHARED) == _per_origin(train, DECOY)


def test_three_verdict_decoys_are_common_and_span_the_node_stories(train):
    """The 0907 model wrote broken JSON on decoy halves with three verdicts.
    It had seen few: 80 of 397 kept decoy rows carried three or more, and
    every node-scoped one came from a single scenario. Two floors now: at
    least 40 of every 100 decoy rows carry three or more verdicts, and the
    node-scoped ones with three or more come from at least 5 stories.

    The generator cycles a pair's width over 2..len(victims), so a story
    with two victims can never render three. These floors hold only when
    nearly every story has a third victim. 2026-10-03: the radius comes
    from `Story.blast_radius`."""
    radius = {st.key: st.blast_radius for st in stories.trainable()}
    decoys = [e for e in train if e.case == DECOY]
    wide = [e for e in decoys if len(e.meta["expected"]) >= 3]
    share = len(wide) / len(decoys)
    node_keys = {e.meta["origin"] for e in wide
                 if radius[e.meta["origin"]] == "node"}
    assert share >= 0.40, (
        f"{len(wide)} of {len(decoys)} decoy rows carry three or more "
        f"verdicts, share {share:.3f}")
    assert len(node_keys) >= 5, (
        f"node-scoped three-verdict decoys come from {len(node_keys)} "
        f"story(s): {sorted(node_keys)}")


def test_none_of_these_is_balanced_across_the_worlds(train):
    """If the healthy half said `none_of_these` far more often than the
    broken half, the case name would be the cue, not the workload's lines."""
    b_none, b_all = _none_share([e for e in train if e.case == SHARED])
    h_none, h_all = _none_share([e for e in train if e.case == DECOY])
    gap = abs(b_none / b_all - h_none / h_all)
    assert gap <= BALANCE, (
        f"broken {b_none}/{b_all}, healthy {h_none}/{h_all}, gap {gap:.3f}")


def test_none_of_these_stays_under_the_ceiling(train):
    """Every verdict of every case in train, not only the family's."""
    n, total = _none_share(train)
    assert n / total <= CEILING, (
        f"{n} of {total} train verdicts are none_of_these ({n / total:.3f})")


def test_the_story_does_not_give_the_label_away(train):
    """A plain story's label depends on what its victims print, so some
    stories must end "shared" and some "none" by majority."""
    plain = [st.key for st in stories.trainable() if st.cls == "P"]
    ends = Counter(
        _majority([e.meta["label"] for e in train
                   if e.case == SHARED and e.meta["origin"] == k])
        for k in plain)
    assert ends["shared"] >= LABEL_CUE and ends["none"] >= LABEL_CUE, dict(ends)


def test_kept_twins_print_different_lines(train):
    """Spec section 4, "Worlds differ": the two prompts differ in at least
    one printed line (Ruling 35)."""
    same = [a.group for a, b in _pairs(train)
            if set(a.user.splitlines()) == set(b.user.splitlines())]
    assert same == [], f"{len(same)} kept pairs print the same lines: {same[:10]}"
```

- [ ] **Step 4: Append the whole-family checks to `tests/test_shared_origin_pool.py`**

Replace the import block at the top of the file (Task 7 wrote it) with:

```python
import json
import random
import re
from collections import Counter

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, checker, generate, gold, stories
from kubeagent_verdict.evals import score
```

Append to the end of the file:

```python
# ---- Whole-family checks (Task 8): every family row the build and the
# probe sets make, at the runbook recipe.

BROKEN = ("shared_origin", "shared_origin_probe")
HEALTHY = ("shared_origin_decoy", "shared_origin_decoy_probe")
_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")


@pytest.fixture(scope="module")
def pairs():
    """Every family pair as (broken, healthy). The training loop and
    `_shared_origin_twin_pairs` append the broken half then its twin, and
    `split` and `drop_held_out` move a whole group at once, so adjacent
    family rows are twins. The exam's two probe lists walk the same stories
    in the same order, so they zip."""
    rows = generate.generate(17, 8000)
    train, val = generate.split(rows, seed=17)
    test = generate.test_set()
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    alternating = ([e for e in kept if e.case.startswith("shared_origin")]
                   + generate.shared_origin_wide_probes()
                   + generate.shared_origin_cousin_probes())
    assert len(alternating) % 2 == 0, len(alternating)
    out = (list(zip(alternating[::2], alternating[1::2]))
           + list(zip(generate.shared_origin_probes(),
                      generate.shared_origin_decoy_probes())))
    for a, b in out:
        assert a.case in BROKEN and b.case in HEALTHY, (a.case, b.case)
        assert a.group == b.group, (a.group, b.group)
    return out


@pytest.fixture(scope="module")
def family(pairs):
    return [e for pair in pairs for e in pair]


def test_every_family_gold_scores_full_marks(family):
    misses = full_marks_misses(family)
    assert misses == [], f"{len(misses)} rows lose a mark: {misses[:20]}"


def test_own_lines_equal_the_graders_on_every_row(family):
    """Ruling 7: the dataset's copy of the grader's own-lines rule agrees
    with the grader on every family row, not only on the pilots."""
    bad = []
    for e in family:
        ws = list(e.meta["workloads"])
        if gold.own_lines(e.user, ws) != score._own_blocks(e.user, ws):
            bad.append(f"{e.case} {e.group}")
    assert bad == [], f"{len(bad)} rows: {bad[:20]}"


def test_every_log_cause_is_one_kubeagent_prints(family):
    """A log read's body says `log cause: <one of logscan's ten causes>`."""
    bad = set()
    for e in family:
        for ln in e.user.splitlines():
            s = ln.strip()
            if (s.startswith(checker.LOG_CAUSE_PREFIX)
                    and s[len(checker.LOG_CAUSE_PREFIX):] not in checker.LOG_CAUSES):
                bad.add(s)
    assert not bad, sorted(bad)[:20]


def test_one_verdict_per_workload(family):
    """Every workload gets exactly one answer, and the answer is the one
    the meta expects."""
    for e in family:
        verdicts = json.loads(e.assistant)["verdicts"]
        names = [v["workload"] for v in verdicts]
        where = (e.case, e.group)
        assert len(names) == len(set(names)), (where, names)
        assert set(names) == set(e.meta["workloads"]) == set(e.meta["expected"]), where
        assert {v["workload"]: v["cause"] for v in verdicts} == e.meta["expected"], where


def test_label_and_summary_agree(family):
    """The label is "shared" or "none", the summary's first line claims a
    shared cause exactly when the label is "shared", and a healthy world is
    always "none"."""
    for e in family:
        label = e.meta["label"]
        first = json.loads(e.assistant)["summary"].split("\n")[0]
        where = (e.case, e.group, first)
        assert label in ("shared", "none"), (where, label)
        assert bool(_SHARED_HEAD.match(first)) == (label == "shared"), where
        if e.case in HEALTHY:
            assert label == "none", where


def test_each_answer_kind_carries_its_confidence_and_keys(family):
    """`none_of_these` is low with no keys; a decided workload (job 1) is
    high with no keys; a named job-2 workload has keys to grade on."""
    for e in family:
        for v in json.loads(e.assistant)["verdicts"]:
            wm = e.meta["workloads"][v["workload"]]
            where = (e.case, e.group, v["workload"], v["cause"])
            if v["cause"] == contract.NONE_OF_THESE:
                assert v["confidence"] == "low", where
                assert wm["own_cause_keywords"] == [], where
            elif wm["job"] == 1:
                assert v["confidence"] == "high", where
                assert wm["own_cause_keywords"] == [], where
            else:
                assert wm["job"] == 2 and wm["own_cause_keywords"], where


def test_ruled_broken_worlds_are_shared_unless_a_check_was_unverified(family):
    """Ruling 31: rules confirm the shared cause in a ruled story's broken
    world, except in the unverified twin, whose label is "none"."""
    by = stories.by_key()
    for e in family:
        if e.case not in BROKEN or by[e.meta["origin"]].cls != "R":
            continue
        unverified = any(wm["decided_outcome"] == "unverified"
                         for wm in e.meta["workloads"].values())
        assert e.meta["label"] == ("none" if unverified else "shared"), (e.case, e.group)


def test_named_keys_fail_the_other_world_and_every_decoy(pairs):
    """Ruling 39: a workload's keys must not also match its other world's
    answer or any decoy its own row shows. Otherwise a model scores by
    naming the wrong thing."""
    bad = []
    for a, b in pairs:
        for row, other in ((a, b), (b, a)):
            for w, wm in row.meta["workloads"].items():
                keys = wm["own_cause_keywords"]
                if not keys:
                    continue
                own = row.meta["expected"][w]
                assert score._keywords_match(own, keys, []), (row.case, row.group, w, keys)
                rivals = list(row.meta["decoy_by_workload"][w])
                theirs = other.meta["expected"].get(w)
                if theirs is not None and theirs != contract.NONE_OF_THESE:
                    rivals.append(theirs)
                bad += [f"{row.case} {row.group} {w}: {keys} match {cause!r}"
                        for cause in rivals if score._keywords_match(cause, keys, [])]
    assert bad == [], f"{len(bad)}: {bad[:20]}"


# Ruling 38. The spec's nine, plus the 23 rules that read at least one item
# of the old family (2026-10-03, 2420 rows of generate(17, 8000) +
# test_set(), 0 violations).
MUST_INSPECT = frozenset({
    "ANS-2", "D3", "E6", "E7", "E8", "E9", "B5", "B7", "TXT-IS15",
    "A1", "A2", "A3", "A4", "A5", "A6", "ANS-1", "B2", "B3", "B4", "B8",
    "C1", "C2-vocab", "C3", "C4-order", "D1", "F1", "F2", "F3", "TXT-IS8",
    "TXT-POD",
})
# Pinned from the first build (Task 8 Step 5). A rule moves between these
# two lists only with a dated comment saying why.
INSPECTS = frozenset({
    "A1", "A2", "A3", "A4", "A5", "A6", "ANS-1", "ANS-2", "B2", "B3", "B4",
    "B5", "B7", "B8", "C1", "C2-vocab", "C3", "C4-order", "D1", "D3", "E6",
    "E7", "E8", "E9", "F1", "F2", "F3", "TXT-IS15", "TXT-IS8", "TXT-POD",
})
INSPECTS_NONE = frozenset({
    "B1", "B6", "C1-cause", "C1-conf", "C2-reason", "C4-dedup", "C5/D4",
    "D1-onefresh", "D2-vocab", "E-min", "E1", "E10", "E2-order", "E3", "E4",
    "E5", "TXT-IS11", "TXT-IS14", "TXT-IS17", "TXT-IS9",
})


def test_no_rule_passes_by_looking_at_nothing(family):
    """Spec Tests section 2: every one of the 50 rules is on exactly one
    list, the "inspects" list is what the family really exercises, and the
    must-inspect rules are on it."""
    seen = Counter()
    for e in family:
        for rule, n in checker.check_row(generate.to_row(e)).inspected.items():
            seen[rule] += n
    assert INSPECTS | INSPECTS_NONE == set(checker.RULES)
    assert not INSPECTS & INSPECTS_NONE
    measured = {r for r in checker.RULES if seen[r] > 0}
    assert measured == INSPECTS, (
        f"now inspect: {sorted(measured - INSPECTS)}; "
        f"now inspect nothing: {sorted(INSPECTS - measured)}")
    assert MUST_INSPECT <= INSPECTS, sorted(MUST_INSPECT - INSPECTS)
```

The starting `INSPECTS` is `MUST_INSPECT` (30 rules) and `INSPECTS_NONE`
is the other 20. Step 5 replaces them with what the build measures.

- [ ] **Step 5: Measure, then fill in the pins**

Run:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
import json
from collections import Counter
from kubeagent_verdict import contract
from kubeagent_verdict.dataset import checker, generate, stories

pool = stories.trainable()
rows = generate.generate(17, 8000)
train, val = generate.split(rows, seed=17)
test = generate.test_set()
kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
fam = ([e for e in kept if e.case.startswith("shared_origin")]
       + generate.shared_origin_wide_probes() + generate.shared_origin_cousin_probes()
       + generate.shared_origin_probes() + generate.shared_origin_decoy_probes())
seen = Counter()
for e in fam:
    for k, n in checker.check_row(generate.to_row(e)).inspected.items():
        seen[k] += n
print("family rows", len(fam))
print("INSPECTS", sorted(r for r in checker.RULES if seen[r] > 0))
print("INSPECTS_NONE", sorted(r for r in checker.RULES if seen[r] == 0))

big = generate.generate(17, 14000)
causes = Counter(c for e in big if e.case == "shared_origin"
                 for c in e.meta["expected"].values() if c != contract.NONE_OF_THESE)
tot = sum(causes.values())
top = causes.most_common(3)
print("cause spread: distinct", len(causes), "top1", round(top[0][1] / tot, 4),
      "top3", round(sum(n for _c, n in top) / tot, 4), top)

tr = generate.drop_held_out(train, test)
per = Counter(e.meta["origin"] for e in tr if e.case == "shared_origin")
print("floor: min", min(per[st.key] for st in pool), "max", max(per[st.key] for st in pool))
def share(rs):
    vs = [v for e in rs for v in json.loads(e.assistant)["verdicts"]]
    return sum(v["cause"] == contract.NONE_OF_THESE for v in vs), len(vs)
b, h = share([e for e in tr if e.case == "shared_origin"]), share([e for e in tr if e.case == "shared_origin_decoy"])
print("balance: broken", b, "healthy", h, "gap", round(abs(b[0] / b[1] - h[0] / h[1]), 4))
print("ceiling:", share(tr), round(share(tr)[0] / share(tr)[1], 4))
ends = Counter()
for st in pool:
    if st.cls == "P":
        c = Counter(e.meta["label"] for e in tr if e.case == "shared_origin" and e.meta["origin"] == st.key)
        m = c.most_common()
        ends[None if len(m) > 1 and m[0][1] == m[1][1] else m[0][0]] += 1
print("label cue:", dict(ends))
decoys = [e for e in tr if e.case == "shared_origin_decoy"]
wide = [e for e in decoys if len(e.meta["expected"]) >= 3]
radius = {st.key: st.blast_radius for st in pool}
print("three-verdict:", len(wide), len(decoys), round(len(wide) / len(decoys), 4),
      sorted({e.meta["origin"] for e in wide if radius[e.meta["origin"]] == "node"}))
EOF
```

Expected: it prints each line. Then:
1. If any rule in `MUST_INSPECT` is on the printed `INSPECTS_NONE` line, stop. Commit nothing. Report DONE_WITH_CONCERNS with the rule names (Ruling 38).
2. Otherwise set the `INSPECTS` and `INSPECTS_NONE` literals in `tests/test_shared_origin_pool.py` to the two printed lists, sorted, in the same style.
3. Write the printed distinct count, top one and top three into the cause-spread docstring sentence from Step 2, in place of the three `<…>` marks.
4. Copy every printed line into the task report. Task 11 puts the floor, balance, ceiling, label cue and three-verdict numbers into `contract/PIN.md`.

- [ ] **Step 6: Run the mix tests**

Run: `PYTEST tests/test_shared_origin_floor.py tests/test_shared_origin_pool.py "tests/test_shared_origin_training.py::test_big_deals_exactly_draws_rows_per_scenario" "tests/test_shared_origin_training.py::test_the_trainable_pool_exercises_every_issue_kind" "tests/test_shared_origin_training.py::test_the_trainable_pool_holds_the_planned_count" "tests/test_shared_origin_training.py::test_every_trainable_scenario_is_taught_equally" "tests/test_shared_origin_training.py::test_no_shared_origin_cause_dominates_the_curriculum"`
Expected: PASS.

The bars are 0.9, 0.7 and 0.9 for the exam, and FLOOR, BALANCE, CEILING,
LABEL_CUE, the three-verdict 0.40 and 5, the cause spread's 0.12 and
0.30, and full issue-kind coverage here. None of them moves. If one of
these tests fails, the data is wrong, not the bar: commit nothing, and
report DONE_WITH_CONCERNS with the test name, the numbers Step 5 printed
and the stories involved. The controller rules on a story fix (Tasks 5
and 6 own the story data).

If `test_every_family_gold_scores_full_marks`, `test_own_lines_equal_the_graders_on_every_row`,
`test_every_log_cause_is_one_kubeagent_prints`, `test_one_verdict_per_workload`,
`test_label_and_summary_agree`, `test_each_answer_kind_carries_its_confidence_and_keys`,
`test_ruled_broken_worlds_are_shared_unless_a_check_was_unverified` or
`test_named_keys_fail_the_other_world_and_every_decoy` fails, a row is
wrong. Fix the module that made it (`shared_origin.py`, `gold.py` or the
story data in `stories.py`), add a test that pins that case to
`tests/test_shared_origin_pipeline.py`, `tests/test_shared_origin_gold.py`
or `tests/test_stories.py`, and rerun. If the fix is not clear, stop and
report BLOCKED with the test, the row's case and group, and the line.

Then run: `PYTEST tests/test_stories.py tests/test_shared_origin_gold.py tests/test_shared_origin_pipeline.py tests/test_checker.py`
Expected: PASS.

- [ ] **Step 7: Lint and commit**

If Step 6 changed `shared_origin.py`, `gold.py`, `stories.py` or their
tests, add those files by name to the `git add` below as well.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_shared_origin_training.py tests/test_shared_origin_floor.py \
       tests/test_shared_origin_pool.py \
  && COMMIT "test(mix): BIG 14000, the 4b-1 mix tests, and whole-family gold checks"
```

---

### Task 9: The old family tests, rewritten against the new rows

Tasks 2 to 8 replaced the family's code. The old tests still read what is
gone: the made-up candidate menus, the 12 X stories and the invented
origin read. This task moves them to the new rows, in four parts. Each
part has its own files, its own steps and its own commit. No source file
changes, and no bar moves.

The deletion rule (spec, Tests): a test is deleted only if it checks
something the new rows no longer have — the made-up candidate menu, the
12 X stories, or the invented origin read (origin variants and
`origin_read_label` on this family included). Everything else is kept or
rewritten against the new rows. A test about `multi` or another family
that only touches propagation in passing stays.

Run the parts in order, A to D, then Part E's one check. Each part's
first step runs its own files and says which failures to expect. Before
Part A, the controller has compared Task 7's failure list with the four
parts (Ruling 47); the dispatch names any test added to a part.

Two sets of tests are not this task's, and no step here edits them:

- What Task 8 owns: `tests/test_shared_origin_floor.py`,
  `tests/test_shared_origin_pool.py`, and the imports, constants and
  tests Task 8 names in `tests/test_shared_origin_training.py`.
- Task 10's five. They read the old exam bytes and stay red until Task 10
  re-pins them:
  - `tests/test_exam_graded_view.py::test_graded_view_is_pinned`
  - `tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload`
  - `tests/test_exam_prompt_stability.py::test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam`
  - `tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used`
  - `tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used`

**Files:**
- Part A — Modify: `tests/test_shared_origin_training.py` (every test but Task 8's and Task 10's two hash tests).
- Part B — Modify: `tests/test_propagation.py`, `tests/test_healthy_evidence.py`, `tests/test_ruled_scenarios.py`, `tests/test_evidence_overlap.py` (two `DECLARED` entries and the comment above them; Ruling 45).
- Part C — Modify: `tests/test_probe_cousins.py`, `tests/test_probe_wide.py`, `tests/test_shared_origin_keywords.py`, `tests/test_shared_origin_decided.py`, `tests/test_shared_origin_training_pair.py`, `tests/test_shared_origin_decoy_probe.py`.
- Part D — Modify: `tests/test_score.py`, `tests/test_oracle.py`, `tests/test_answer_keys.py` (the counts and the regenerated `WEAK_PAIRS`, Ruling 37), `tests/test_generate.py` (not the tests Task 7 changed).
- No production code.

**Interfaces:**
- Consumes (Task 3): `stories.Answer`, `stories.VictimText`, `stories.World`, `stories.Story` (`key`, `cls`, `blast_radius`, `scope_field`, `origin_kind`, `victims`, `broken`, `healthy`, `shown_origin`, `shown_cause`, `shown_remedy`); `stories.by_key()`, `stories.trainable()` (41: 35 P by key, then 6 R in `RULED_ORDER`), `stories.exam()` (6), `EXAM_KEYS`, `RULED_ORDER`, `DROPPED`; `shared_origin.draw(story, rng, *, width) -> Draw` (raises `ValueError` outside `2..len(victims)`), `shared_origin.build(story, d, *, world, unverified=False, budget=c.MAX_TOOL_CALLS, origin_events_failed="") -> Built`.
- Consumes (Task 4): `gold.own_lines(user, workloads)`, `gold.RowGold(verdict, cause, confidence, keys, rationale, linked)`, `gold.Gold(rows, label, n, summary)`, `gold.gold_for(built)`, `gold.label_for(rule_lines, *, linked, cls, world)`, `gold._summary(built, rows, label, n)` (Ruling 41).
- Consumes (Task 7): `cases.shared_origin(p, rng, victims=None, unverified=False)`, `cases.shared_origin_decoy`, `cases.shared_origin_probe`, `cases.shared_origin_decoy_probe`; `generate._shared_origin_twin_pairs`; `render.rule_rationale(result)`; the row meta of Ruling 8 (no `origin_read_label`, `distractor_cause`, `wrong_summary_phrase` or `expected_confidence` on this family); twins paired on `Example.group` (Ruling 32); Task 7's report list of the tests it broke.
- Consumes (existing): `score._keywords_match` (Ruling 41), `generate.generate(seed, size)`, `generate.test_set()`, `generate.to_row(e)`.
- Produces: a suite where exactly Task 10's five tests fail (Part E checks it); the re-pinned exam job counts in `tests/test_oracle.py` (Task 10's measure must print the same "now" numbers, and its Step 6 runs `tests/test_oracle.py`); the regenerated `WEAK_PAIRS` in `tests/test_answer_keys.py` (Task 11 reads its length); `EXAM_PROBE_LABELS`, `EXAM_KEYWORDED` and `DENYING_ROWS`, measured (Ruling 43).

#### Part A: tests/test_shared_origin_training.py (the rest)

**Files:**
- Modify: `tests/test_shared_origin_training.py`
- No production code. Task 8 owns some tests in this file and Task 10 owns the two hash tests. Part A touches neither.

Task 7 rebuilt the four shared-origin builders from `stories.Story`. This file
still tests the old rows: the made-up candidate menu, the origin variants and
the invented origin read. This part moves the rest of the file to the new
rows. "The rest" means everything Task 8 and Task 10 do not own. Find each
test by its name; line numbers are from main @ ff6527e and move after Tasks 2
to 8.

The file has 51 tests on main. Task 8 deletes one of them and rewrites five
more, which leaves 50 when this part starts. Here is where the 51 go:

| | Count | Where |
|---|---|---|
| Task 8 owns | 6 | `test_big_deals_exactly_draws_rows_per_scenario`, `test_the_trainable_pool_exercises_every_issue_kind`, `test_the_trainable_pool_holds_the_planned_count`, `test_every_trainable_scenario_is_taught_equally`, `test_every_trainable_scenario_renders_at_least_three_origin_variants` (Task 8 deletes it), `test_no_shared_origin_cause_dominates_the_curriculum` |
| Task 10 owns | 2 | `test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used`, `test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used` |
| Kept as they are | 14 | one of them (:475) gets new numbers in its docstring |
| Rewritten (full code below) | 14 | 12 with new code, 2 with a new docstring only. 7 keep their name; 7 get a new name |
| Deleted | 13 | Step A8 |
| Moved to the `multi` block | 2 | Steps A8 and A9 |
| New | 6 | 1 in Step A4, 3 in Step A6 for the dropped keys, 2 in Step A6 for whole pairs |
| Re-pinned | 0 | this part moves no pin and no bar |

After this part the file has 43 tests: 36 from this part, 2 from Task 10 and 5
from Task 8.

**The deletion rule.** A test is deleted only if it checks something the new
rows no longer have: the made-up candidate menu, the 12 X stories, or the
invented origin read (origin variants, or `origin_read_label` on this
family). Everything else is kept or rewritten. Every deletion below says what
the test checked. A test about `multi` that only touches propagation in
passing stays. Three tests are handled under Ruling 50:
`test_no_two_trainable_scenarios_share_a_local_cause` is deleted, because its
`local_cause` was an entry in the made-up menu; and
`test_every_exam_layout_has_a_trained_floor` and
`test_every_held_out_read_kind_has_a_trained_cousin` are kept, because they
read the `propagation` pool, which `multi` still trains on.

**What happens to each old test.**

*Rewrite (14).* Full code is in Steps A4, A5 and A7. The first eight rows of
the table read `stories` instead of the 54 `propagation` scenarios. The next
four read rows and keys. The last two change a docstring only.

| Old test | New test | Step |
|---|---|---|
| `test_a_trainable_scenario_pool_exists` (:85) | `test_both_trainable_pools_exist` | A4 |
| `test_no_trainable_origin_is_an_eval_origin` (:89) | same name | A4 |
| `test_no_trainable_scenario_reuses_an_eval_answer_string` (:96) | `test_no_trainable_story_reuses_an_eval_answer_string` | A4 |
| `test_trainable_scenarios_obey_every_rule_the_eval_table_obeys` (:117) | `test_trainable_stories_obey_every_rule_the_eval_table_obeys` | A4 |
| `_SCOPE_FOR_RADIUS` (:186) and `test_blast_radius_and_scope_field_agree` (:189) | same names | A4 |
| `test_no_two_trainable_scenarios_share_an_answer_string` (:199) | `test_no_two_trainable_stories_share_an_origin_answer_string` | A4 |
| `test_every_trainable_scenario_has_at_least_three_victims` (:230) | `test_every_trainable_story_has_at_least_three_victims` | A4 |
| `test_no_trainable_scenario_text_carries_a_banned_identifier_shape` (:353) | `test_no_trainable_story_text_carries_a_banned_identifier_shape`, plus one new control | A4 |
| `test_every_generated_shared_origin_row_names_a_trainable_origin` (:469) | same name | A5 |
| `test_every_shared_origin_row_names_one_cause_for_every_workload` (:756) | `test_a_shared_ruled_row_decides_every_workload` | A5 |
| `test_no_eval_row_comes_from_the_trainable_pool` (:1211) | same name | A5 |
| `test_the_probe_still_draws_only_held_out_origins` (:1219) | same name | A5 |
| `test_the_generator_emits_the_two_classes_near_evenly` (:648) | same name, docstring only | A7 |
| `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (:670) | same name, docstring only | A7 |

*Delete (13).* Each one checks the made-up menu or the invented origin
read. All 13 go in Step A8.

1. `test_every_trainable_scenario_declares_at_least_four_origin_variants` (:131). It counts the origin variants of each scenario. The family draws no variant now.
2. `test_every_variant_first_line_is_literal_and_unique_within_its_scenario` (:145). It reads the first line of each origin variant.
3. `test_every_trainable_scenario_names_its_state_in_words` (:161). It checks the invented origin state token inside each variant.
4. `test_no_two_trainable_scenarios_share_a_local_cause` (:209). A victim's `local_cause` was an entry in the made-up menu. A victim's own cause is read off its own lines now, and two stories may fail a pod the same way. (Ruling 50.)
5. `test_pass_confidence_varies_within_every_trainable_scenario` (:219). It checked the per-victim confidence of the old menu, so the model could not copy one grade. Confidence is never graded, and the gold side is pinned by Task 8's `test_each_answer_kind_carries_its_confidence_and_keys`.
6. `test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half` (:239). It looked for the invented `origin_state` token in a victim read. A healthy world is its own set of lines now, and Part B's `tests/test_healthy_evidence.py` checks those lines.
7. `test_the_eleven_named_scenarios_carry_an_exam_layout_variant` (:283). It checks that eleven scenarios carry a variant laid out like the old exam's origin read. The exam has no such read now.
8. `test_no_two_variants_are_the_same_rendering_with_different_numbers` (:323). It compares origin variants.
9. `test_a_scenario_with_variants_renders_more_than_one_of_them` (:379). It draws a variant through `cases.shared_origin`, which takes a `Story` now.
10. `test_a_pair_built_from_one_salt_draws_the_same_variant` (:406). Same: a variant draw. The new pair is checked in `tests/test_shared_origin_training_pair.py` (Part C).
11. `test_a_scenario_without_variants_renders_exactly_what_it_did_before` (:435). It checks that a probe built from a `Propagation` prints the first line of `origin_read[1]`. The builders take a `Story` now, and a probe prints real lines.
12. `test_the_small_build_offers_no_negative_the_shared_half_lacks` (:598). It compares `origin_read_label` between the family and `multi`. The family has no label.
13. `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers` (:611). It counts `origin_read_label` on the family. Step A6 adds the new check of the thing it protected: whole pairs.

These helpers die with them (listed again in the audit below): `_EXAM_LAYOUT_MARKERS`
(:264), `_QUANTITY` (:307), `_canonical_rendering` (:310), `_origin_labels`
(:550) and `_PVC_SCOPED_ORIGINS` (:749).

*Move to the `multi` block (2).* These check `multi`, which keeps the
54-scenario pool and `origin_read_label`. They stay in the file, in a block
beside `_template`. Step A8 deletes the old copy, Step A9 writes the new one.
- `test_the_emitter_offers_every_origin_read_under_both_answers` (:580) becomes `test_the_multi_negatives_offer_every_origin_read_template`. The shared side is gone with the family's label; the negatives are compared to the pool itself.
- `test_node_memory_pressure_spells_no_taint_the_way_kubectl_does` (:297) keeps its name. Its two variant asserts go; the two asserts about `healthy_origin_content` stay, because `multi`'s negative rows print that text.

*Keep (14).* No code. Each one depends on neither a dropped meta key nor
the 54-scenario pool as the family's source:
- `test_every_trainable_scenario_carries_a_healthy_origin_read` (:111). It reads `healthy_origin_content` of the `propagation` pool, which is `multi`'s raw material.
- `test_the_case_mix_names_shared_origin_and_still_sums_to_one_hundred` (:449). It reads `generate.CASE_MIX`.
- `test_shared_origin_is_not_a_held_out_case` (:455). It reads `generate.HELD_OUT_CASES`.
- `test_generate_emits_shared_origin_rows` (:465). It only asks that `rows` holds a `shared_origin` row.
- `test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows` (:475). It counts rows by case. Step A2 measures that the counts did not move, and Step A7 updates the numbers in its docstring.
- `test_a_negative_multi_row_shows_the_component_healthy` (:711) and `test_a_negative_multi_row_still_says_separate_reasons` (:739). They read `multi` rows only, so they keep the pool and the label on purpose.
- `test_a_shared_origin_training_row_never_says_separate_reasons` (:744). Ruling 33: only a healthy world says it, and a `shared_origin` row is the broken world. It reads the summary, not a dropped key.
- `test_the_eval_set_is_two_hundred_and_forty_nine_rows` (:785). The exam is still 229 other rows plus the 20 rebuilt ones.
- `test_the_frozen_slice_is_every_row_before_the_decoy_probe` (:1186). It pins the 239-row length and the position of the decoy probes, not any content.
- `test_training_still_contaminates_nothing` (:1227). It compares groups, which are victims only (Ruling 32).
- `test_every_exam_layout_has_a_trained_floor` (:1344) and `test_every_held_out_read_kind_has_a_trained_cousin` (:1358). They read only the `propagation` pool, which `multi` still trains on, so they still guard what they guarded (Ruling 50). `EXAM_LAYOUT_FLOORS` and `_teaches_layout` stay with them.
- `test_one_training_only_separate_prompt_exists_at_the_frozen_seed` (:1478). It reads a `multi` row. `split` hashes each group alone, so a `multi` row's side and order cannot move when the family changes.

**Helpers, fixtures and constants.**

| Name | Verdict |
|---|---|
| `SIZE`, `SEED` (:50-:51) | stay |
| `rows` fixture (:54) | stays |
| `kept` fixture (:59) | stays; its docstring says where `shared_origin` rows come from, and Step A3 updates that sentence |
| `_by_case` (:79) | stays; the new helpers use it |
| `_SCOPE_FOR_RADIUS` (:186) | changes: the cluster entry is `""`, not `None` (Step A4) |
| `_template` (:529) | stays; a dated note says only `multi` rows reach it (Step A7) |
| `_independent_share` (:633) | stays; it already counts the family by case. Docstring only (Step A7) |
| `EXAM_LAYOUT_FLOORS` (:1313), `_teaches_layout` (:1322) | stay; the two kept layout tests use them |
| `_EXAM_LAYOUT_MARKERS`, `_QUANTITY`, `_canonical_rendering`, `_origin_labels`, `_PVC_SCOPED_ORIGINS` | go (Step A8). Each was used only by tests that go. `_PVC_SCOPED_ORIGINS` is replaced by `Story.origin_kind == "pvc"` |
| `FAMILY_CASES`, `_DROPPED_META_KEYS`, `_BANNED`, `_origin_answers`, `_authored_origin_text`, `_strings`, `_banned_shapes`, `_dropped_keys`, `_rows_carrying_dropped_keys`, `family_piles` | new, Step A3 |
| `_unpaired_groups` | new, Step A6 |
| `_multi_templates` | new, Step A9 |
| `DRAWS`, `RULED_DRAWS`, `BIG`, `big_rows`, `EXPECTED_POOL` | Task 8's. Not touched |
| `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256`, `_digest` | Task 10's. Not touched |

The module docstring is replaced in Step A3. It keeps the story of how the
file began and adds what changed on 2026-10-03.

**Interfaces:**
- Consumes (Tasks 2 to 8): `stories.trainable()`, `stories.exam()`, `stories.by_key()`, `stories.CLASSES`, `stories.SCOPES`, `stories.ORIGIN_KINDS`; `Story.key`, `.cls`, `.blast_radius`, `.scope_field`, `.origin_kind`, `.victims`, `.broken`, `.healthy`, `.shown_cause`; `World.origin_row`, `.pull_literal`; `OriginRow.answer`; `VictimText.issue`, `.broken`, `.healthy`, `.evidence`; `Answer.cause`, `.link`; `generate.generate`, `.split`, `.drop_held_out`, `.test_set`, `.shared_origin_wide_probes`, `.shared_origin_cousin_probes`, `.CASE_MIX`, `.HELD_OUT_CASES`; the import line Task 8 writes, `from kubeagent_verdict import contract, vocab` and `from kubeagent_verdict.dataset import generate, propagation, stories`; the Task 8 names `big_rows`, `BIG`.
- Consumes (unchanged): `propagation.trainable_scenarios()`, `propagation.all_scenarios()`, `propagation.BLAST_RADII`, `propagation.SEPARATE_REASONS`, `Propagation.origin_read`, `.healthy_origin_content`, `.key`; `vocab.ISSUE_KINDS`.
- Row facts it relies on: the meta keys of Ruling 8 (per workload `job`, `decided`, `decided_cause`, `decided_outcome`, `decided_evidence`, `expected_cause`, `own_cause_keywords`, `own_cause_must_not`; per row `workloads`, `label`, `case`, `origin`, `expected`); a family row has no `origin_read_label`, `distractor_cause`, `wrong_summary_phrase` or `expected_confidence`; `multi` rows still have `origin_read_label`; `Example.group` is the victims only and is the same in both twins (Ruling 32); a family label is `shared` or `none` only; "failing for separate reasons" is said only by a healthy world (Ruling 33); the family counts are unchanged (120 and 120 at `SIZE` 800), and so is the exam (249 rows, 239 in the frozen slice).
- Produces: nothing later tasks call.

**Dates.** Every dated comment this part adds says `2026-10-03`. If the day
you carry this part out is not 2026-10-03, write that day instead, in every
one of them, as you go. Step A11 lists them so you can check.

- [ ] **Step A1: Run the old file to see it fail**

Run: `PYTEST tests/test_shared_origin_training.py`
Expected: FAIL. About 9 of the 50 tests fail and about 41 pass. This count is
reasoned from reading the code of Tasks 3, 7 and 8, not measured, and it can
differ by a few. Task 7's report lists the tests it breaks (Ruling 47); put
that list beside this one. The failures come in four groups:
- Three variant builder tests: `test_a_scenario_with_variants_renders_more_than_one_of_them` (:379), `test_a_pair_built_from_one_salt_draws_the_same_variant` (:406) and `test_a_scenario_without_variants_renders_exactly_what_it_did_before` (:435). They call `cases.shared_origin` or `cases.shared_origin_probe` with a `propagation` scenario. The builders take a `Story` now.
- Three read-label tests: `test_the_emitter_offers_every_origin_read_under_both_answers` (:580), `test_the_small_build_offers_no_negative_the_shared_half_lacks` (:598) and `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers` (:611). They collect `origin_read_label` from family rows. The family has none, so the set they build for it is empty and one of their asserts on that set fails.
- `test_every_shared_origin_row_names_one_cause_for_every_workload` (:756). A plain story's broken world is labelled `shared` now, and the workloads of a plain story are not decided.
- The two hash tests that Task 10 owns (:1201, :1206). They fail until Task 10 re-pins them.

Every other old test passes, because `propagation.py` does not change and most
of them read it.

Check: every test listed under "Keep" in the intro must be among the passing
ones. If one of them fails, stop. That is a break from an earlier task, not an
old pin. Report BLOCKED with the test name and the error. Do the same for any
failure that is neither in the four groups above nor in Task 7's list.

- [ ] **Step A2: MEASURE the numbers the docstrings quote**

Four docstrings in this file quote how big the family is in the training
pile: `test_the_generator_emits_the_two_classes_near_evenly` (0.5636),
`test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (0.5385 and
0.5461), `test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows`
(0.3810, 0.3836, and "214 of 3,128"), and `_independent_share`. The family is
rebuilt, so "these did not move" has to be measured, not assumed.

Task 7 keeps the family's row counts: 120 `shared_origin` rows and 120
`shared_origin_decoy` rows at `SIZE` 800, and 1,200 and 1,200 at size 8,000.
`multi` is built first, and `split` hashes each group alone, so a `multi`
row's side and order cannot move either. The script below checks all of that
against what main @ ff6527e measured. It also measures one number that does
move: how many rows of the multi-workload pile now carry the label `shared`.
A plain story's broken row is `shared` too now, whenever two or more of its
victims are linked to the origin. Before, only a ruled row was.

What main measured (the script holds these as `WAS`):

| Pile | `shared_origin` | `shared_origin_decoy` | `multi` with a read label | independent share | family share |
|---|---|---|---|---|---|
| size 800, all rows | 120 | 120 | 35 | 0.5636 | 0.3488 |
| size 800, kept | 120 | 120 | 20 | 0.5385 | 0.3810 |
| size 8000, all rows | 1,200 | 1,200 | 345 | 0.5628 | 0.3488 |
| size 8000, kept | 1,200 | 1,200 | 244 | 0.5461 | 0.3824 |

The multi-workload pile (kept `multi` + `shared_origin` + `shared_origin_decoy`)
was 315 rows at size 800 and 3,138 at size 8000. Its `multi` rows were 73
`none` and 2 `separate` at size 800, and 725 and 13 at size 8000.

The script writes no file. It checks that:
- there are 41 trainable and 6 exam stories;
- every number in the table is the same as before;
- the pile sizes and the `multi` labels are the same as before;
- every family row is labelled `shared` or `none`, and every healthy twin is `none`.

Run from the repo root:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
from collections import Counter

from kubeagent_verdict.dataset import generate, stories

SEED = 17
# Measured on main @ ff6527e, before Spec 4b-1:
# (shared_origin rows, shared_origin_decoy rows, multi rows with a read label,
#  independent share, case-family share among multi-workload rows)
WAS = {
    (800, "rows"): (120, 120, 35, 0.5636, 0.3488),
    (800, "kept"): (120, 120, 20, 0.5385, 0.3810),
    (8000, "rows"): (1200, 1200, 345, 0.5628, 0.3488),
    (8000, "kept"): (1200, 1200, 244, 0.5461, 0.3824),
}
# multi rows in the kept pile, by label, measured the same way
WAS_MULTI = {800: {"none": 73, "separate": 2}, 8000: {"none": 725, "separate": 13}}
# multi + shared_origin + shared_origin_decoy rows in the kept pile
WAS_PILE = {800: 315, 8000: 3138}
failures = []


def by_case(pile, case):
    return [e for e in pile if e.case == case]


def numbers(pile):
    shared = len(by_case(pile, "shared_origin"))
    decoy = len(by_case(pile, "shared_origin_decoy"))
    labelled = len([e for e in by_case(pile, "multi") if "origin_read_label" in e.meta])
    independent = round((decoy + labelled) / (shared + decoy + labelled), 4)
    separate = len(by_case(pile, "multi")) + decoy
    return shared, decoy, labelled, independent, round(shared / (shared + separate), 4)


def check(ok, what):
    print(("ok      " if ok else "FAILED  ") + what)
    if not ok:
        failures.append(what)


check((len(stories.trainable()), len(stories.exam())) == (41, 6),
      f"41 trainable and 6 exam stories, got {(len(stories.trainable()), len(stories.exam()))}")
test = generate.test_set()
for size in (800, 8000):
    rows = generate.generate(seed=SEED, size=size)
    train, val = generate.split(rows, seed=SEED)
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    for name, pile in (("rows", rows), ("kept", kept)):
        got = numbers(pile)
        print(size, name, "now", got, "was", WAS[(size, name)])
        check(got == WAS[(size, name)], f"{size} {name}: the case counts and shares did not move")
    pile = [e for e in kept if e.case in ("multi", "shared_origin", "shared_origin_decoy")]
    labels = Counter(e.meta["label"] for e in pile)
    multi = Counter(e.meta["label"] for e in by_case(kept, "multi"))
    family = Counter(e.meta["label"] for e in pile if e.case != "multi")
    decoy = Counter(e.meta["label"] for e in by_case(kept, "shared_origin_decoy"))
    print(size, "answer level: pile", len(pile), "labels", dict(labels))
    check(len(pile) == WAS_PILE[size], f"{size}: the multi-workload pile is still {WAS_PILE[size]}, got {len(pile)}")
    check(dict(multi) == WAS_MULTI[size], f"{size}: the multi rows keep their labels {WAS_MULTI[size]}, got {dict(multi)}")
    check(set(family) <= {"shared", "none"}, f"{size}: a family row is 'shared' or 'none', got {sorted(family)}")
    check(set(decoy) == {"none"}, f"{size}: every healthy twin is 'none', got {dict(decoy)}")
    shared = labels["shared"]
    print(f"WRITE size {size}: {shared} of {len(pile):,} ({round(100 * shared / len(pile))} of every 100)")
print("CHECK FAILED" if failures else "CHECK PASSED")
raise SystemExit(1 if failures else 0)
EOF
```

It prints one `ok` or `FAILED` line for each check, and then two lines of this form:

```text
WRITE size 800: <S> of 315 (<P> of every 100)
WRITE size 8000: <S> of 3,138 (<P> of every 100)
```

`<S>` is the number before ` of ` and `<P>` is the number in the brackets.
Write all four numbers down. Step A7 puts them in one docstring, and none of
the `<...>` marks may stay in the file.

CHECK: the last line is `CHECK PASSED` and the exit code is 0. If any line
says `FAILED`, the script ends with `CHECK FAILED`. Then stop, commit
nothing, and report DONE_WITH_CONCERNS with the whole printout. Do not edit a
number, a bar or a pin to make the check pass, and do not use `-update`. A
count that moved means the family's row counts changed in Task 7 or Task 8,
which this part cannot fix.

Part A moves no pin. The docstring numbers are the only thing this step feeds.

Run: `PYTEST tests/test_shared_origin_training.py::test_generate_emits_shared_origin_rows`
Expected: PASS. It only confirms that the file still loads before it is edited.

- [ ] **Step A3: Add the import, the new docstring and the helpers**

Four edits at the top of `tests/test_shared_origin_training.py`.

1. Add `import dataclasses` above `import hashlib`. The stdlib block then reads:

```python
import dataclasses
import hashlib
import json
import re
from collections import Counter
```

Leave the two `kubeagent_verdict` import lines as Task 8 wrote them.

2. Replace the whole module docstring (:1-:38, from `"""Teaching shared-origin
reasoning without teaching the test.` to its closing `"""`) with the text
below. It keeps the history of how the file began and adds what changed:

```python
"""Teaching shared-origin reasoning without teaching the test.

This file guards the rows the model trains on. It asks two questions. Does
training leak the exam? And does the training pile hand the model a cue, so
it can score without reading the evidence?

How it began (kept as history)
------------------------------

`propagation.py` shipped its six scenarios as EVAL-ONLY and said why: the
measurement had to exist and had to fail before any attempt was made to teach
the correction. It has now failed — on all ten `shared_origin_probe` rows the
0830 model answered "N workloads are failing for separate reasons" and picked
a different local decoy for every workload. The same docstring named the
condition a correction has to meet:

    once these scenarios are ever trained on, a pass stops meaning that, and
    the slice needs held-out origins the way `contradiction_probe` needed
    held-out entries.

So training gets its OWN origins and the six eval scenarios stay eval-only —
the catalog's 19-trainable / 9-held-out split, applied to propagation. The
eval set does not move, which is what keeps the 0830 scoreboard comparable.

That closes the obvious shortcut. This module was written mostly for the
second, which is not obvious: `multi` builds its reads per constituent
(`_reads(e, n)[:2]`), so a cluster-scoped read at the head of the list used to
appear in shared-origin rows and NOWHERE else. Train the positive case alone
and "an origin read is present" separates the two classes perfectly — the
model would pass the probe on the prompt's shape without reading a word of the
evidence, and every rate on the slice would improve for a reason that is not
the skill. The counterweight was a negative case: `multi` rows carrying the
SAME origin read label with content showing the component HEALTHY, where
"separate reasons" is still the right answer. Same shape, both answers, so
only the evidence separates them.

Two residuals were asserted rather than claimed away. The counterweight was
lighter than the generator made it look: `drop_held_out` removes about a
third of the `multi` counter-examples and none of the `shared_origin` rows,
so the emitted ~48/52 reached the optimizer as ~62/38 (the band is now held
by `test_the_trained_pile_is_not_one_sided_among_origin_read_rows`). And the
exam could not detect this shortcut even then — seven of the ten
`shared_origin_probe` rows carried a read label that appeared in none of the
other 243, so label-matching alone cleared job 3 and the decoy rate. The
second residual is gone: the family has no read label now (see below).

What changed on 2026-10-03 (Spec 4b-1)
--------------------------------------

The shared-origin family is rebuilt from `stories.py`: real lines, run
through kubeagent's own pipeline. Three things follow for this file.

1. The family's training pool is the 41 stories in `stories.trainable()`.
   The 54 made-up scenarios in `propagation.py` are no longer its pool.
2. The made-up candidate menu, the 12 X stories and the invented origin read
   are gone from the family. So are the tests that checked them: the origin
   variants, their states, their exam layouts, the read-layout floors and
   cousins, and `origin_read_label` on this family.
3. A family row's meta no longer carries `origin_read_label`,
   `distractor_cause`, `wrong_summary_phrase` or `expected_confidence`.
   `test_no_family_row_meta_carries_a_dropped_key` checks that on the train
   pile, the exam, the wide probes and the cousin probes.

`multi` was not rebuilt. It still draws from the 54 scenarios in
`propagation.py`, which Spec 4b-1 does not change, and it is now the only
case that carries `origin_read_label`. So the checks that only `multi` can
answer stay in this file, in the block that holds `_template`. The family's
side of the same shortcut is checked in `tests/test_shared_origin_floor.py`
and `tests/test_shared_origin_pool.py`. Spec 4b-3 owns `multi`.
"""
```

3. Insert these helpers directly below `_by_case` (:79) and above the banner
comment line that ends `the held-out origin split`. Two blank lines before and
after:

```python
FAMILY_CASES = ("shared_origin", "shared_origin_decoy",
                "shared_origin_probe", "shared_origin_decoy_probe")

# 2026-10-03 (Spec 4b-1): the four meta keys the made-up menu and the invented
# origin read needed. The family does not carry them. `multi` still carries
# `origin_read_label`, and nothing below looks at `multi`.
_DROPPED_META_KEYS = ("origin_read_label", "distractor_cause",
                      "wrong_summary_phrase", "expected_confidence")

_BANNED = (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"https?://"),
           re.compile(r"kubeconfig", re.IGNORECASE), re.compile(r"/home/"),
           re.compile(r"@"))


def _origin_answers(story):
    """Every answer that names the origin: each world's origin row answer, and
    each victim answer that links to the origin."""
    out = []
    for world in (story.broken, story.healthy):
        row = world.origin_row
        if row is not None and row.answer is not None:
            out.append(row.answer)
    for v in story.victims:
        out += [a for a in (v.broken, v.healthy) if a is not None and a.link]
    return out


def _authored_origin_text(story):
    """The strings a story authors for the origin, which the exam grades.

    Only a plain (P) story writes them: its `shown_cause`, and the cause of
    each answer that names the origin. A ruled (R) story's cause is the
    rules' wording, decided by code and not chosen by the model, and the
    ruled stories may repeat it on purpose: the trainable node stories read
    like the exam story `node-not-ready`. So a ruled story authors nothing
    here.
    """
    if story.cls == "R":
        return set()
    text = {a.cause for a in _origin_answers(story)}
    text.add(story.shown_cause)
    return text


def _strings(obj):
    """Every string inside a story, however deep it sits."""
    if isinstance(obj, str):
        yield obj
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _strings(getattr(obj, f.name))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, (tuple, list, set, frozenset)):
        for item in obj:
            yield from _strings(item)


def _banned_shapes(story):
    blob = "\n".join(_strings(story))
    return [pat.pattern for pat in _BANNED if pat.search(blob)]


def _dropped_keys(node, path="meta"):
    """Where a dropped key sits in a meta value, however deep."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key in _DROPPED_META_KEYS:
                found.append(here)
            found += _dropped_keys(value, here)
    elif isinstance(node, (list, tuple)):
        for i, value in enumerate(node):
            found += _dropped_keys(value, f"{path}[{i}]")
    return found


def _rows_carrying_dropped_keys(piles):
    return [(name, e.case, e.group, path)
            for name, pile in piles.items() for e in pile
            for path in _dropped_keys(e.meta)]


@pytest.fixture(scope="module")
def family_piles(rows):
    """The four piles a family row can sit in."""
    exam = generate.test_set()
    return {"train": [e for e in rows if e.case in FAMILY_CASES],
            "exam": [e for e in exam if e.case in FAMILY_CASES],
            "wide": generate.shared_origin_wide_probes(),
            "cousin": generate.shared_origin_cousin_probes()}
```

4. In the docstring of the `kept` fixture (:59), replace

```text
    group; a `shared_origin` row is built from the train-only propagation
    pool the exam never touches. So `multi` loses about a third of its
    origin-read rows here and `shared_origin` loses none.
```

with

```text
    group; a `shared_origin` row is built from a train-only story the exam
    never touches (before 2026-10-03 (Spec 4b-1) it was built from the
    train-only propagation pool). So `multi` loses about a third of its
    origin-read rows here and `shared_origin` loses none.
```

Run: `PYTEST tests/test_shared_origin_training.py::test_generate_emits_shared_origin_rows tests/test_shared_origin_training.py::test_the_case_mix_names_shared_origin_and_still_sums_to_one_hundred`
Expected: PASS, 2 passed. The helpers are not used by any test yet.

- [ ] **Step A4: Rewrite the story-shape tests**

These eight tests read `stories` instead of the 54 `propagation` scenarios.
They pass on the first run, because they check data, not a new behaviour. A
failing one points at a story, not at the test: stop, and report BLOCKED
with the story key it prints. The scenario tables in `propagation.py` are
still checked by Part B's kept tests in `tests/test_propagation.py`
(`test_every_scenario_has_a_closed_blast_radius`,
`test_scenario_keys_are_unique_and_slug_shaped`,
`test_every_victim_issue_is_in_the_closed_kind_vocabulary`,
`test_scenarios_have_two_to_four_victims`, `test_scoped_scenarios_declare_the_field_they_pin`
and `test_no_scenario_text_carries_a_banned_identifier_shape`).

Replace `test_a_trainable_scenario_pool_exists` (:85) with:

```python
def test_both_trainable_pools_exist():
    """`stories` feeds the shared-origin family. `propagation` still feeds `multi`."""
    assert stories.trainable()
    assert propagation.trainable_scenarios()
```

Replace `test_no_trainable_origin_is_an_eval_origin` (:89) with:

```python
def test_no_trainable_origin_is_an_eval_origin():
    """The whole point. A shared key would make the probe a memory test.

    2026-10-03 (Spec 4b-1): the family's two pools are `stories.exam()` and
    `stories.trainable()`; `multi` still draws from the trainable
    `propagation` scenarios. All three must stay clear of the six held-out
    keys, and the six must still be the same six in both modules.
    """
    held = {st.key for st in stories.exam()}
    assert held == {p.key for p in propagation.all_scenarios()}
    assert {st.key for st in stories.trainable()} & held == set()
    assert {p.key for p in propagation.trainable_scenarios()} & held == set()
```

Replace `test_no_trainable_scenario_reuses_an_eval_answer_string` (:96) with:

```python
def test_no_trainable_story_reuses_an_eval_answer_string():
    """Disjoint keys are not enough — the probe grades the cause STRING.

    Two stories could carry different keys and the same cause string, and
    then the model has seen the graded answer verbatim while `drop_held_out`
    reports a clean split, because it keys on group identity and never looks
    at the text.

    2026-10-03 (Spec 4b-1): the strings compared are the ones a story writes
    for its origin (`_authored_origin_text`). A victim's answer to its OWN
    cause is left out on purpose: it is read off that victim's own lines, and
    two stories may fail a pod the same way. A ruled story's cause is the
    rules' wording, which the stories share on purpose.
    """
    held = set()
    for st in stories.exam():
        held |= _authored_origin_text(st)
    assert held, "the exam stories author no origin text, so this check is empty"
    for st in stories.trainable():
        assert not (_authored_origin_text(st) & held), st.key
```

Replace `test_trainable_scenarios_obey_every_rule_the_eval_table_obeys` (:117) with:

```python
def test_trainable_stories_obey_every_rule_the_eval_table_obeys():
    """The shape rules, on the 41 stories.

    2026-10-03 (Spec 4b-1): the old checks on `shared_verdict`, `confidence`,
    `pass_confidence` and a duplicate `local_cause` have no analog. A story
    has no verdict to forbid, a confidence is a closed pair checked when an
    `Answer` is built, and a victim's own cause is read off its own lines, not
    chosen from a menu.
    """
    for st in stories.trainable():
        assert st.cls in stories.CLASSES, st.key
        assert st.blast_radius in propagation.BLAST_RADII, st.key
        assert st.scope_field in stories.SCOPES, st.key
        assert st.origin_kind in stories.ORIGIN_KINDS, st.key
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", st.key), st.key
        assert 2 <= len(st.victims) <= 4, st.key
        for v in st.victims:
            assert v.issue in vocab.ISSUE_KINDS, f"{st.key}: {v.issue}"
```

Replace `_SCOPE_FOR_RADIUS` and `test_blast_radius_and_scope_field_agree`
(:186-:196) with:

```python
_SCOPE_FOR_RADIUS = {"cluster": "", "node": "node", "namespace": "ns"}


def test_blast_radius_and_scope_field_agree():
    """A node-scoped origin is only coherent if every victim is on that node.
    `shared_origin.draw` pins the field named by `scope_field`, so a radius
    that disagrees with it asserts a blast radius its own inventory
    contradicts.

    2026-10-03 (Spec 4b-1): a story names "no scope" with the empty string,
    not `None`, so the cluster entry above changed from `None` to `""`.
    """
    for st in stories.trainable():
        assert st.scope_field == _SCOPE_FOR_RADIUS[st.blast_radius], st.key
```

Replace `test_no_two_trainable_scenarios_share_an_answer_string` (:199) with:

```python
def test_no_two_trainable_stories_share_an_origin_answer_string():
    """A cause string reused across stories is a lookup key spanning both."""
    owner = {}
    for st in stories.trainable():
        for value in sorted(_authored_origin_text(st)):
            assert owner.setdefault(value, st.key) == st.key, (
                f"{st.key} repeats an origin answer string of {owner[value]}: {value!r}")
```

Replace `test_every_trainable_scenario_has_at_least_three_victims` (:230) with:

```python
def test_every_trainable_story_has_at_least_three_victims():
    """The 0907 model failed decider 5 on three-victim decoy halves it had
    never seen: 15 of 24 trainable scenarios held two victims, so the
    generator could only ever render two. Three is the floor now."""
    thin = {st.key: len(st.victims) for st in stories.trainable()
            if len(st.victims) < 3}
    assert thin == {}, f"stories with fewer than three victims: {thin}"
```

Replace `test_no_trainable_scenario_text_carries_a_banned_identifier_shape`
(:353) with the test below and its control. The old test looped over the
scenarios' victims and a list of fields. `_strings` walks every dataclass
field instead, so a field added later is covered the day it is added. The
control plants an address and a URL and shows the check sees both:

```python
def test_no_trainable_story_text_carries_a_banned_identifier_shape():
    """Every string in a story, however deep, is checked. `_strings` walks the
    dataclasses, so a new field is covered the day it is added."""
    for st in stories.trainable():
        assert _banned_shapes(st) == [], st.key


def test_the_banned_shape_check_sees_a_planted_address():
    """Not vacuous: the same check reports a pattern planted in a victim line
    and one planted in a world."""
    st = stories.trainable()[0]
    victim = dataclasses.replace(st.victims[0], evidence="dial tcp 10.1.2.3:443 refused")
    planted_ip = dataclasses.replace(st, victims=(victim,) + st.victims[1:])
    assert _banned_shapes(planted_ip) == [_BANNED[0].pattern]
    world = dataclasses.replace(st.broken, pull_literal="GET https://registry.example.com/v2/")
    planted_url = dataclasses.replace(st, broken=world)
    assert _banned_shapes(planted_url) == [_BANNED[1].pattern]
```

Run: `PYTEST tests/test_shared_origin_training.py::test_both_trainable_pools_exist tests/test_shared_origin_training.py::test_no_trainable_origin_is_an_eval_origin tests/test_shared_origin_training.py::test_no_trainable_story_reuses_an_eval_answer_string tests/test_shared_origin_training.py::test_trainable_stories_obey_every_rule_the_eval_table_obeys tests/test_shared_origin_training.py::test_blast_radius_and_scope_field_agree tests/test_shared_origin_training.py::test_no_two_trainable_stories_share_an_origin_answer_string tests/test_shared_origin_training.py::test_every_trainable_story_has_at_least_three_victims tests/test_shared_origin_training.py::test_no_trainable_story_text_carries_a_banned_identifier_shape tests/test_shared_origin_training.py::test_the_banned_shape_check_sees_a_planted_address`
Expected: PASS, 9 passed. The file now has 51 tests.

- [ ] **Step A5: Rewrite the row tests**

These four read generated rows or the exam. Replace each by name.

Replace `test_every_generated_shared_origin_row_names_a_trainable_origin` (:469).
It used to check only the broken half. A twin carries the same `origin`, so
it checks both:

```python
def test_every_generated_shared_origin_row_names_a_trainable_origin(rows):
    train = {st.key for st in stories.trainable()}
    for case in ("shared_origin", "shared_origin_decoy"):
        pile = _by_case(rows, case)
        assert pile, case
        for e in pile:
            assert e.meta["origin"] in train, e.meta["origin"]
```

Replace `test_every_shared_origin_row_names_one_cause_for_every_workload`
(:756). The old test used `_PVC_SCOPED_ORIGINS` (:749); Step A8 deletes that
constant. The new one narrows the claim to ruled stories and reads the PVC
exemption off the story's own `origin_kind`:

```python
def test_a_shared_ruled_row_decides_every_workload(rows):
    """A ruled story is decided end to end, and its label says so.

    Spec section 3, ruling C asked this of every `shared`-labelled row: every
    workload decided, one cause for the origin, except a PVC-scoped origin
    (`rules.py`'s group-key storage-class fallback), which can decide several
    victims to several PVC causes and still be one `shared` group. The
    exemption became a live path on 2026-09-19, when the two ruled PVC stories
    joined the trainable pool.

    2026-10-03 (Spec 4b-1): a plain story's broken-world row is `shared` too
    now, whenever two or more of its victims are linked to the origin
    (`gold.label_for`), and a plain story is not decided: the model names the
    cause from the evidence. So the claim is narrowed to the ruled stories
    (`cls == "R"`). The PVC exemption used to be a named set of keys. It is the
    story's own `origin_kind` now, so no key list can drift.
    """
    by_key = stories.by_key()
    seen = 0
    for e in _by_case(rows, "shared_origin"):
        st = by_key[e.meta["origin"]]
        if st.cls != "R" or e.meta["label"] != "shared":
            continue
        seen += 1
        assert all(w["decided"] for w in e.meta["workloads"].values()), st.key
        if st.origin_kind != "pvc":
            assert len(set(e.meta["expected"].values())) == 1, st.key
    assert seen, "no ruled shared_origin row reached the label shared"
```

Replace `test_no_eval_row_comes_from_the_trainable_pool` (:1211):

```python
def test_no_eval_row_comes_from_the_trainable_pool():
    train = {p.key for p in propagation.trainable_scenarios()}
    train |= {st.key for st in stories.trainable()}
    for e in generate.test_set():
        assert e.meta.get("origin") not in train
        for part in e.group.split("+"):
            assert not any(f"propagation:{k}:" in part for k in train), part
```

Replace `test_the_probe_still_draws_only_held_out_origins` (:1219). It used to
check one probe case. It checks both now:

```python
def test_the_probe_still_draws_only_held_out_origins():
    held = {st.key for st in stories.exam()}
    exam = generate.test_set()
    for case in ("shared_origin_probe", "shared_origin_decoy_probe"):
        probes = [e for e in exam if e.case == case]
        assert len(probes) == 10, case
        for e in probes:
            assert e.meta["origin"] in held, (case, e.meta["origin"])
```

Run: `PYTEST tests/test_shared_origin_training.py::test_every_generated_shared_origin_row_names_a_trainable_origin tests/test_shared_origin_training.py::test_a_shared_ruled_row_decides_every_workload tests/test_shared_origin_training.py::test_no_eval_row_comes_from_the_trainable_pool tests/test_shared_origin_training.py::test_the_probe_still_draws_only_held_out_origins`
Expected: PASS, 4 passed. If `test_a_shared_ruled_row_decides_every_workload`
fails on `assert seen`, no ruled `shared_origin` row reached the label
`shared`. Stop and report BLOCKED. That is a story or a Task 7 problem.

- [ ] **Step A6: Add the new tests**

Two groups. Insert both between `test_every_generated_shared_origin_row_names_a_trainable_origin`
and `test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows`.

The first group is the dropped-key check. A family row's meta must not carry
`origin_read_label`, `distractor_cause`, `wrong_summary_phrase` or
`expected_confidence`, in any of the four piles a family row can sit in: the
training rows, the exam, the wide probes and the cousin probes. The key can
sit inside the per-workload meta too, so the check looks at every depth. The
check passes at once, because Task 7 already dropped the keys. The two
control tests plant each key and show the check can fail:

```python
def test_no_family_row_meta_carries_a_dropped_key(family_piles):
    """2026-10-03 (Spec 4b-1): the family's meta lost `origin_read_label`,
    `distractor_cause`, `wrong_summary_phrase` and `expected_confidence`.
    Each had a reader in the old scorer or the old tests; a key that comes
    back would be read by nothing, or by the wrong thing. The check covers
    all four piles a family row can sit in, and looks inside the nested
    per-workload meta as well.
    """
    cases = set()
    for name, pile in family_piles.items():
        assert pile, f"the {name} pile is empty"
        cases |= {e.case for e in pile}
    assert cases == set(FAMILY_CASES), sorted(cases ^ set(FAMILY_CASES))
    assert _rows_carrying_dropped_keys(family_piles) == []


def test_the_dropped_key_check_sees_a_planted_key(family_piles):
    """Not vacuous: each dropped key, planted in the first row of each pile,
    is reported with its pile, case, group and path."""
    for pile, examples in family_piles.items():
        for key in _DROPPED_META_KEYS:
            planted = dataclasses.replace(examples[0], meta={"label": "none", key: "x"})
            assert _rows_carrying_dropped_keys({pile: [planted]}) == [
                (pile, planted.case, planted.group, f"meta.{key}")], (pile, key)


def test_the_dropped_key_check_sees_a_key_nested_under_a_workload(family_piles):
    """The per-workload meta is where `distractor_cause` used to sit."""
    example = family_piles["train"][0]
    planted = dataclasses.replace(example, meta={
        "workloads": {"ns/w": {"job": 1, "distractor_cause": "x"}}})
    assert _rows_carrying_dropped_keys({"train": [planted]}) == [
        ("train", planted.case, planted.group, "meta.workloads.ns/w.distractor_cause")]
```

The second group checks that the cull takes a pair whole. It replaces the
protection `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers`
gave, which counted a label the family does not have. The pair is a
`shared_origin` row and a `shared_origin_decoy` row with the same
`Example.group` (Ruling 32). `split` and `drop_held_out` work on the group,
so they take both or neither. The control cuts one twin out and shows the
group is reported:

```python
def _unpaired_groups(pile):
    """The groups where the broken half and the healthy half do not match one
    for one. A pair is a `shared_origin` row and a `shared_origin_decoy` row
    with the same `Example.group` (Ruling 32)."""
    broken = Counter(e.group for e in _by_case(pile, "shared_origin"))
    healthy = Counter(e.group for e in _by_case(pile, "shared_origin_decoy"))
    return sorted((broken - healthy) + (healthy - broken))


def test_the_cull_takes_every_family_pair_whole(kept):
    """What the model reads holds both halves of every pair, or neither.

    `split` and `drop_held_out` work on the group, and both halves of a pair
    share one, so the cull takes a pair whole. Nothing else in the suite
    checks that it still does. The twin is the counter-example that keeps
    "a story is broken" from being a cue: a pile with the broken half and no
    healthy half teaches the cue back.

    2026-10-03 (Spec 4b-1): this replaces
    `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers`.
    That test counted origin read labels, and the family has none now. The
    thing it protected, whole pairs, is still true of the new rows, so it is
    checked directly.
    """
    assert _by_case(kept, "shared_origin"), "the filter took every shared_origin row"
    assert _unpaired_groups(kept) == []


def test_the_pair_check_sees_half_a_pair(kept):
    """Not vacuous: take one healthy twin out and its group is reported."""
    twin = _by_case(kept, "shared_origin_decoy")[0]
    cut = [e for e in kept if e is not twin]
    assert _unpaired_groups(cut) == [twin.group]
```

Run: `PYTEST tests/test_shared_origin_training.py::test_no_family_row_meta_carries_a_dropped_key tests/test_shared_origin_training.py::test_the_dropped_key_check_sees_a_planted_key tests/test_shared_origin_training.py::test_the_dropped_key_check_sees_a_key_nested_under_a_workload tests/test_shared_origin_training.py::test_the_cull_takes_every_family_pair_whole tests/test_shared_origin_training.py::test_the_pair_check_sees_half_a_pair`
Expected: PASS, 5 passed. The file now has 56 tests. If
`test_no_family_row_meta_carries_a_dropped_key` fails, its message names the
pile, case, group and path of the key. That row is wrong in Task 7's
builders. Stop and report BLOCKED with the message. Do not delete the key
from the check.

- [ ] **Step A7: Update the docstrings that quote numbers or sources**

Five docstring edits. Replace each old text with its new text. In every pair
the old text is unique in the file.

1. `_template` (:529). Old:

```text
    or slash in it, and exactly one template may match.
    """
```

New:

```text
    or slash in it, and exactly one template may match.

    2026-10-03 (Spec 4b-1): only `multi` rows carry a label now, so only
    `multi` rows reach this function.
    """
```

2. `_independent_share` (:633). Old:

```text
    blind to the 169 rows the change was about.
    """
```

New:

```text
    blind to the 169 rows the change was about.

    2026-10-03 (Spec 4b-1): the family's rows carry no read label now, so the
    family is counted by case: every `shared_origin` row on one side and every
    `shared_origin_decoy` row on the other. `multi` is still counted by its
    label, because only its negatives carry the read. The counts did not
    move: 120 + 120 + 35 at this module's SIZE, which is 0.5636.
    """
```

3. `test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows`
(:475). Old (the last paragraph of its docstring):

```text
    That case-family share is not the share of multi-workload rows whose
    graded answer actually claims a shared origin. That answer-level share
    is about 7 of every 100 -- 214 of 3,128 at build size 8000 (214 of
    3,126 before the 2026-09-24 case-mix change), counted on the same kept
    pile the numbers above come from -- and this test does not measure it
    and does not guard it.
    """
```

New. The new text adds a measured paragraph before it and changes the
numbers in it. Write the four numbers from Step A2's `WRITE` lines where
`<S800>`, `<P800>`, `<S8000>` and `<P8000>` stand: `<S800>` and `<P800>`
from the size 800 line, `<S8000>` and `<P8000>` from the size 8000 line.
Write each `<S...>` exactly as the script printed it, with its comma if it
has one. Leave `315` and `3,138` as they are; the check above proved the pile
did not move:

```text
    Re-measured 2026-10-03 (Spec 4b-1) -- 0.3810 at this module's size,
    0.3824 at the build size. This spec did not move either one: the case
    counts are the same. Main read 0.3810 and 0.3824 before the change, so
    the 0.3836 written above was already out of date.

    That case-family share is not the share of multi-workload rows whose
    graded answer actually claims a shared origin. That answer-level share
    used to be about 7 of every 100 -- 22 of 315 at this module's size and
    214 of 3,138 at build size 8000 (the 3,128 written here before was out
    of date), counted on the same kept pile the numbers above come from.
    Re-measured 2026-10-03 (Spec 4b-1): a plain-story `shared_origin` row
    now has a `shared` label whenever two or more of its victims are linked
    to the origin, not only a ruled row, so it is <S800> of 315
    (<P800> of every 100) at this module's size and <S8000> of 3,138
    (<P8000> of every 100) at build size 8000. This test still does not
    measure it and does not guard it.
    """
```

4. `test_the_generator_emits_the_two_classes_near_evenly` (:648). Old:

```text
    actually sits and still fails both degenerate ends.
    """
    assert 0.55 <= _independent_share(rows) <= 0.75
```

New:

```text
    actually sits and still fails both degenerate ends.

    2026-10-03 (Spec 4b-1): unchanged at 0.5636. The family is built from
    stories now, but a pair is still one `shared_origin` row and one
    `shared_origin_decoy` twin from the same salt, so the paired half is
    still 120/120 at this module's SIZE, and `multi` was not touched, so its
    35 negatives are the same 35.
    """
    assert 0.55 <= _independent_share(rows) <= 0.75
```

5. `test_the_trained_pile_is_not_one_sided_among_origin_read_rows` (:670). Old:

```text
    negatives; 0.52 still keeps room below both.
    """
    share = _independent_share(kept)
```

New:

```text
    negatives; 0.52 still keeps room below both.

    Re-measured 2026-10-03 (Spec 4b-1) -- 0.5385 at this size, 0.5461 at the
    build size. Both are unchanged, because the rewrite moved no case count,
    so the floor keeps 0.0185 and 0.0261 of room. The family has no read
    label now, so "origin read rows" means the family's two cases, counted
    by case, plus the `multi` rows that carry a label (see
    `_independent_share`).
    """
    share = _independent_share(kept)
```

Check that no mark is left. This prints nothing:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -nE '<(S|P)(800|8000)>' tests/test_shared_origin_training.py
```

Run: `PYTEST tests/test_shared_origin_training.py::test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows tests/test_shared_origin_training.py::test_the_generator_emits_the_two_classes_near_evenly tests/test_shared_origin_training.py::test_the_trained_pile_is_not_one_sided_among_origin_read_rows`
Expected: PASS, 3 passed. No code changed; no bar moved (0.40, 0.55 to 0.75
and 0.52 to 0.70 are as they were).

- [ ] **Step A8: Delete the tests and helpers the new rows no longer need**

This deletes 20 top-level items: the 13 tests listed under "Delete" in the
intro, the 2 tests that move (Step A9 writes them back), and the 7 helpers.
The script finds each by name, removes its whole span plus the comment block
right above it, and never touches a `# ----` banner. It stops without
writing if a name is missing, so run it once. Run from the repo root:

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import ast
import pathlib

PATH = pathlib.Path("tests/test_shared_origin_training.py")

# 13 deleted tests, 2 tests that move to the `multi` block (Step A9 writes
# them back), and the helpers that only those tests used.
DOOMED = (
    # deleted tests
    "test_every_trainable_scenario_declares_at_least_four_origin_variants",
    "test_every_variant_first_line_is_literal_and_unique_within_its_scenario",
    "test_every_trainable_scenario_names_its_state_in_words",
    "test_no_two_trainable_scenarios_share_a_local_cause",
    "test_pass_confidence_varies_within_every_trainable_scenario",
    "test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half",
    "test_the_eleven_named_scenarios_carry_an_exam_layout_variant",
    "test_no_two_variants_are_the_same_rendering_with_different_numbers",
    "test_a_scenario_with_variants_renders_more_than_one_of_them",
    "test_a_pair_built_from_one_salt_draws_the_same_variant",
    "test_a_scenario_without_variants_renders_exactly_what_it_did_before",
    "test_the_small_build_offers_no_negative_the_shared_half_lacks",
    "test_the_cull_never_leaves_an_origin_read_under_only_shared_answers",
    # moved to the multi block
    "test_node_memory_pressure_spells_no_taint_the_way_kubectl_does",
    "test_the_emitter_offers_every_origin_read_under_both_answers",
    # helpers only the tests above used
    "_EXAM_LAYOUT_MARKERS", "_QUANTITY", "_canonical_rendering",
    "_origin_labels", "_PVC_SCOPED_ORIGINS",
)

lines = PATH.read_text().split("\n")
tree = ast.parse("\n".join(lines))


def name_of(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def is_comment(i):  # i is a 0-based line index
    return lines[i].lstrip().startswith("#")


spans, found = [], []
for node in tree.body:
    name = name_of(node)
    if name not in DOOMED:
        continue
    found.append(name)
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
    top = start
    # Take the comment block that sits right above the node, with at most one
    # blank line between. A banner line (`# -----`) is never taken.
    j = top - 1
    if j >= 0 and not lines[j].strip():
        j -= 1
    if j >= 0 and is_comment(j) and not lines[j].startswith("# ---"):
        while j >= 0 and is_comment(j):
            j -= 1
        top = j + 1
    end = node.end_lineno  # 1-based inclusive, so also the 0-based exclusive end
    while end < len(lines) and not lines[end].strip():
        end += 1
    spans.append((top, end, name))

missing = sorted(set(DOOMED) - set(found))
assert not missing, f"not in the file (already deleted, or renamed?): {missing}"
for top, end, name in sorted(spans, reverse=True):
    print(f"delete :{top + 1}-{end} {name}")
    del lines[top:end]
PATH.write_text("\n".join(lines))
print(f"{len(spans)} top-level items deleted")
EOF
```

It prints `delete :<first>-<last> <name>` for each item, then
`20 top-level items deleted`. If it stops with `not in the file`, a name was
already removed or renamed by an earlier task. Do not edit the list; report
BLOCKED with the names.

Check the count:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -c '^def test_' tests/test_shared_origin_training.py
```

Expected: `41`.

Run: `PYTEST tests/test_shared_origin_training.py --collect-only`
Expected: 41 tests collected and no import error. A deleted helper that
something still reads would show up in Step A11, not here.

- [ ] **Step A9: Write the `multi` block**

Insert this block after the last line of `_template` (`    return hits.pop()`)
and before `def _independent_share`, with two blank lines before it and two
after it. It holds the two tests that moved. It goes in after Step A8
because `test_node_memory_pressure_spells_no_taint_the_way_kubectl_does`
keeps its name, and A8 would have deleted it. A comment at the top says where
the deleted tests went. `_multi_templates` is the one new helper:

```python
# 2026-10-03 (Spec 4b-1): a comment stood here that argued about the family's
# origin read label under both answers. The family has no label now, so the
# argument went with its tests,
# `test_the_small_build_offers_no_negative_the_shared_half_lacks` and
# `test_the_cull_never_leaves_an_origin_read_under_only_shared_answers`.
# What is left is the half only `multi` can answer: does the build offer every
# origin read as a negative at all? The old text is in git, at main @ ff6527e.

def _multi_templates(rows):
    """The origin read templates `multi` rows carry. The family carries none."""
    return {_template(e.meta["origin_read_label"])
            for e in _by_case(rows, "multi") if "origin_read_label" in e.meta}


def test_the_multi_negatives_offer_every_origin_read_template(big_rows):
    """The emitter's half, checked before the cull, where it is the emitter's.

    Every trainable origin read template must be offered by a `multi` row,
    under an independent answer. The negatives rotate over the pool one
    `multi` row in three, so the rotation completes only when the build holds
    at least three `multi` rows per scenario. `SIZE` stopped holding that at
    thirty-one scenarios; `BIG` holds it many times over. Asserting it on the
    kept pile instead would be asserting the cull's behaviour under the
    emitter's name.

    2026-10-03 (Spec 4b-1): this was `test_the_emitter_offers_every_origin_read_under_both_answers`,
    which compared the shared half to the negatives. The family has no
    origin read label now, so only the negatives side is left, and it is
    compared to the pool itself: the set of templates the 54 `propagation`
    scenarios declare.
    """
    pool = {p.origin_read[0] for p in propagation.trainable_scenarios()}
    negatives = _multi_templates(big_rows)
    assert negatives, "no multi row carries an origin read — the cue is alive"
    assert negatives == pool, sorted(negatives ^ pool)


def test_node_memory_pressure_spells_no_taint_the_way_kubectl_does():
    """kubectl prints `Taints:  <none>`. The record said `Taints:  none`.

    2026-10-03 (Spec 4b-1): moved here from the origin-variant group. Its
    variant checks went with the variants. What stays is the healthy read
    that `multi`'s negative rows render.
    """
    p = {q.key: q for q in propagation.trainable_scenarios()}["node-memory-pressure"]
    assert "Taints:  <none>" in p.healthy_origin_content
    assert "Taints:  none" not in p.healthy_origin_content
```

Run: `PYTEST tests/test_shared_origin_training.py::test_the_multi_negatives_offer_every_origin_read_template tests/test_shared_origin_training.py::test_node_memory_pressure_spells_no_taint_the_way_kubectl_does`
Expected: PASS, 2 passed. The file now has 43 tests.

- [ ] **Step A10: Check the names**

This confirms every rewritten, new and moved test is in the file, every
deleted name is gone, and no top-level name is defined twice. A name defined
twice would hide a test, because the second `def` wins. Run from the repo
root:

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import ast
import collections
import pathlib

PATH = pathlib.Path("tests/test_shared_origin_training.py")

# The 36 tests this part leaves in the file: 14 kept, 14 rewritten, 6 new,
# 2 moved to the `multi` block.
PRESENT_TESTS = (
    # kept (14)
    "test_every_trainable_scenario_carries_a_healthy_origin_read",
    "test_the_case_mix_names_shared_origin_and_still_sums_to_one_hundred",
    "test_shared_origin_is_not_a_held_out_case",
    "test_generate_emits_shared_origin_rows",
    "test_the_shared_origin_case_family_stays_the_minority_among_multi_workload_rows",
    "test_a_negative_multi_row_shows_the_component_healthy",
    "test_a_negative_multi_row_still_says_separate_reasons",
    "test_a_shared_origin_training_row_never_says_separate_reasons",
    "test_the_eval_set_is_two_hundred_and_forty_nine_rows",
    "test_the_frozen_slice_is_every_row_before_the_decoy_probe",
    "test_training_still_contaminates_nothing",
    "test_one_training_only_separate_prompt_exists_at_the_frozen_seed",
    "test_every_exam_layout_has_a_trained_floor",
    "test_every_held_out_read_kind_has_a_trained_cousin",
    # rewritten (14)
    "test_both_trainable_pools_exist",
    "test_no_trainable_origin_is_an_eval_origin",
    "test_no_trainable_story_reuses_an_eval_answer_string",
    "test_trainable_stories_obey_every_rule_the_eval_table_obeys",
    "test_blast_radius_and_scope_field_agree",
    "test_no_two_trainable_stories_share_an_origin_answer_string",
    "test_every_trainable_story_has_at_least_three_victims",
    "test_no_trainable_story_text_carries_a_banned_identifier_shape",
    "test_every_generated_shared_origin_row_names_a_trainable_origin",
    "test_a_shared_ruled_row_decides_every_workload",
    "test_no_eval_row_comes_from_the_trainable_pool",
    "test_the_probe_still_draws_only_held_out_origins",
    "test_the_generator_emits_the_two_classes_near_evenly",
    "test_the_trained_pile_is_not_one_sided_among_origin_read_rows",
    # new (6)
    "test_the_banned_shape_check_sees_a_planted_address",
    "test_no_family_row_meta_carries_a_dropped_key",
    "test_the_dropped_key_check_sees_a_planted_key",
    "test_the_dropped_key_check_sees_a_key_nested_under_a_workload",
    "test_the_cull_takes_every_family_pair_whole",
    "test_the_pair_check_sees_half_a_pair",
    # moved to the multi block (2)
    "test_the_multi_negatives_offer_every_origin_read_template",
    "test_node_memory_pressure_spells_no_taint_the_way_kubectl_does",
)

# Helpers this part adds (or, for _SCOPE_FOR_RADIUS, changes).
PRESENT_HELPERS = (
    "FAMILY_CASES", "_DROPPED_META_KEYS", "_BANNED", "_origin_answers",
    "_authored_origin_text", "_strings", "_banned_shapes", "_dropped_keys",
    "_rows_carrying_dropped_keys", "family_piles", "_unpaired_groups",
    "_multi_templates", "_SCOPE_FOR_RADIUS",
)

ABSENT = (
    # deleted tests (13)
    "test_every_trainable_scenario_declares_at_least_four_origin_variants",
    "test_every_variant_first_line_is_literal_and_unique_within_its_scenario",
    "test_every_trainable_scenario_names_its_state_in_words",
    "test_no_two_trainable_scenarios_share_a_local_cause",
    "test_pass_confidence_varies_within_every_trainable_scenario",
    "test_a_victim_read_never_asserts_a_broken_origin_on_the_healthy_half",
    "test_the_eleven_named_scenarios_carry_an_exam_layout_variant",
    "test_no_two_variants_are_the_same_rendering_with_different_numbers",
    "test_a_scenario_with_variants_renders_more_than_one_of_them",
    "test_a_pair_built_from_one_salt_draws_the_same_variant",
    "test_a_scenario_without_variants_renders_exactly_what_it_did_before",
    "test_the_small_build_offers_no_negative_the_shared_half_lacks",
    "test_the_cull_never_leaves_an_origin_read_under_only_shared_answers",
    # the old name of the test that moved and changed (1)
    "test_the_emitter_offers_every_origin_read_under_both_answers",
    # the old names of the seven renamed tests
    "test_a_trainable_scenario_pool_exists",
    "test_no_trainable_scenario_reuses_an_eval_answer_string",
    "test_trainable_scenarios_obey_every_rule_the_eval_table_obeys",
    "test_no_two_trainable_scenarios_share_an_answer_string",
    "test_every_trainable_scenario_has_at_least_three_victims",
    "test_no_trainable_scenario_text_carries_a_banned_identifier_shape",
    "test_every_shared_origin_row_names_one_cause_for_every_workload",
    # helpers only the deleted tests used (5)
    "_EXAM_LAYOUT_MARKERS", "_QUANTITY", "_canonical_rendering", "_origin_labels",
    "_PVC_SCOPED_ORIGINS",
)

tree = ast.parse(PATH.read_text())
defined = collections.Counter()
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        defined[node.name] += 1
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                defined[target.id] += 1

missing = [n for n in PRESENT_TESTS + PRESENT_HELPERS if defined[n] == 0]
left = [n for n in ABSENT if defined[n] > 0]
twice = sorted(n for n, k in defined.items() if k > 1)
assert not missing, f"missing from the file: {missing}"
assert not left, f"should be gone but still defined: {left}"
assert not twice, f"defined more than once, so the first one is hidden: {twice}"
count = sum(1 for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
print("names ok")
print(f"{count} tests")
EOF
```

Expected: it prints `names ok` and then `43 tests`. The 43 are 36 from this
part, 2 from Task 10 and 5 from Task 8. If the number differs and the
assert on this part's names passed, the difference is in Task 8's tests;
look at Task 8's report, not at this part.

- [ ] **Step A11: Run the whole file**

First list the dates this part wrote:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff -U0 -- tests/test_shared_origin_training.py | grep '^+' | grep 'Spec 4b-1' | grep -o '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' | sort | uniq -c
```

Task 8 is already committed, so this diff holds only this part's edits.
Expected: one line, with the day you carried this part out. Any other date,
or a second line, is a mistake; fix it.

Run: `PYTEST tests/test_shared_origin_training.py`
Expected: 41 passed and 2 failed. The two failures are exactly
`test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used`
and `test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used`.
They fail because the 20 family exam rows are rebuilt on real lines. Task 10
re-pins `FROZEN_SLICE_SHA256` and `EVAL_SET_SHA256`; do not touch them here
and do not use `-update`. Any other failure is a mistake in this part or a
break from an earlier task. Read its message, fix it if the test or helper is
yours, and report BLOCKED if it is a story or a builder.

- [ ] **Step A12: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_shared_origin_training.py \
  && COMMIT "test(shared-origin): rewrite the training-file tests against stories and real rows"
```

Expected: `ruff` prints `All checks passed!` and the commit is made. Do not add `.gitignore`,
`train-v2.log` or the plan file. The commit message has no author trailer and no tool credit.

#### Part B: propagation, healthy evidence, evidence overlap, ruled scenarios

**Files:**
- Modify: `tests/test_propagation.py`
- Modify: `tests/test_healthy_evidence.py`
- Modify: `tests/test_evidence_overlap.py` — two `DECLARED` entries and the comment above them; no test code changes.
- Modify: `tests/test_ruled_scenarios.py`
- No production code. Tasks 7 and 8 edit none of these four files.

Task 7 rebuilt the four shared-origin builders from `stories.Story` and
deleted the old `cases._render_shared_origin` and its helpers. These four
files still test the old rows. This part moves them to the new rows. Find
each test by its name; line numbers are from main @ ff6527e.

What happens to the 77 tests in the three files that change code:

| | Count | Where |
|---|---|---|
| Kept as they are | 36 | 18 in `test_propagation.py`, 2 in `test_healthy_evidence.py`, 16 in `test_ruled_scenarios.py` |
| Rewritten (full code below) | 34 | 16 in `test_propagation.py`, 7 in `test_healthy_evidence.py`, 11 in `test_ruled_scenarios.py`. 23 keep their name; 11 get a new name. |
| Deleted | 7 | 3 in `test_propagation.py`, 4 in `test_ruled_scenarios.py` |
| New | 2 | 1 in `test_healthy_evidence.py`, 1 in `test_ruled_scenarios.py` |

`test_evidence_overlap.py` keeps all 4 of its tests. One measured pin in it
is re-measured and re-pinned (Step B6).

**The deletion rule.** A test is deleted only if it checks the made-up
candidate menu, the 12 X stories, or the invented origin read (origin
variants, or `origin_read_label` on this family). Everything else is kept
or rewritten. The 7 deletions each name what they checked. A test that
looked old but still checks something the new rows have was rewritten, and
the Notes at the end say which.

**Interfaces:**
- Consumes (Tasks 2 to 7): `stories.exam()`, `stories.by_key()`, `stories.trainable()`, `stories.RULED_ORDER`; `Story.key`, `.cls`, `.blast_radius`, `.scope_field`, `.origin_kind`, `.victims`, `.broken`, `.healthy`; `World.conditions`, `.origin_row`, `.pvc_class`; `VictimText.evidence`, `.events`, `.evidence_healthy`, `.events_healthy`; `shared_origin.draw(story, rng, *, width)`, `shared_origin.build(story, d, *, world, unverified=False)` and `shared_origin._sub(text, names, draw)`; `Built.user`, `.rows`, `.draw`, `.gathered.reads`, `.group`; `Row.key`, `.role`, `.index`, `.names`, `.result`, `.candidates`; `cases.shared_origin`, `cases.shared_origin_decoy`, `cases.shared_origin_probe`, `cases.shared_origin_decoy_probe`; `generate._entry_rng`, `generate.to_row`, `generate.generate`, `generate.split`, `generate.drop_held_out`, `generate.test_set`.
- Consumes (unchanged): `propagation.trainable_scenarios()`, `all_scenarios()`, `ruled_scenarios()`, `SEPARATE_REASONS`; `objects.CONNECTION_LITERALS`; `score.job1`; the `contract` constants `SYSTEM_PROMPT`, `CLOSING_INSTRUCTION`, `MAX_PROMPT_BYTES`, `MAX_SUMMARY_LINES`, `MAX_VERDICT_ROWS`, `CONFIDENCE_VALUES`.
- Row facts it relies on: the meta keys of Ruling 8 (`workloads` with `job`, `decided`, `decided_cause`, `decided_outcome`, `decided_evidence`, `expected_cause`, `own_cause_keywords`, `own_cause_must_not`; `decoy_by_workload`; `decoy_causes == []`; `shared_claim_phrases` on the decoy probe only); `Example.group` is `"+".join(f"propagation:{key}:{ns}/{name}")` over the drawn victims and is the same in both twins (Ruling 32); the unverified twin raises `ValueError` for a story with no down node (Ruling 31); "failing for separate reasons" is said only by a healthy world (Ruling 33).
- Produces: nothing later tasks call.

- [ ] **Step B1: Run the three old files to see them fail**

Run: `PYTEST tests/test_propagation.py tests/test_healthy_evidence.py tests/test_ruled_scenarios.py`
Expected: FAIL. In the draft's sandbox it was 68 failed and 46 passed; the exact count can differ by a few. The failures come in three groups:
- `test_propagation.py`: most of the builder tests (:184-:377) and the tests from :512 to the end. They call `cases._render_shared_origin`, which Task 7 deleted, or look for the made-up menu. `test_registry_example_com_host_is_a_no_op_rewrite` fails too on the real tree, because `cases._propagation_names` is gone; the draft's sandbox still had that helper, so it passed there.
- `test_healthy_evidence.py`: the 7 tests that build a row from a `Propagation` object. The builders now take a `Story`.
- `test_ruled_scenarios.py`: the rendered-row tests (:318-:367) and the unverified-twin tests (:384-:473).

Check: every test that Steps B2 to B5 list under "Keep" must be among the passing ones. If one of them fails, stop. That is a break from an earlier task, not an old pin. Report BLOCKED with the test name and the error.

- [ ] **Step B2: Rewrite the builder tests in `tests/test_propagation.py`**

Keep these 18 tests. They read `propagation.py`'s own tables, which `multi`
still draws and which this spec does not change:
`test_victim_and_propagation_gain_the_declaration_fields` (:26),
`test_every_scenario_has_a_closed_blast_radius` (:44),
`test_scenario_keys_are_unique_and_slug_shaped` (:50),
`test_every_victim_issue_is_in_the_closed_kind_vocabulary` (:58),
`test_every_victim_verdict_label_is_a_real_verdict` (:72),
`test_no_scenario_hands_the_shared_cause_the_attributed_tag` (:78),
`test_scenarios_have_two_to_four_victims` (:90),
`test_each_victim_carries_its_own_local_decoy` (:95),
`test_the_pass_confidence_varies_inside_at_least_one_scenario` (:110),
`test_blast_radii_are_all_exercised` (:123),
`test_scoped_scenarios_declare_the_field_they_pin` (:128),
`test_a_pinned_scope_field_appears_in_the_shared_cause` (:136),
`test_no_scenario_text_carries_a_banned_identifier_shape` (:147),
`test_the_eval_six_declare_no_variants_and_no_state` (:380),
`test_the_shared_scenarios_declare_an_origin_object` (:394),
`test_the_six_scenarios_declare_what_the_graft_table_says` (:422),
`test_every_scenario_object_passes_check_declaration` (:470),
`test_victim_decoy_objects_declare_their_contents` (:480).

Replace the imports (:17-:23) with:

```python
import json
import random
from dataclasses import replace

from kubeagent_verdict import contract as c
from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, generate, objects, propagation, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.dataset.objects import Fresh, Object
```

Replace the banner comment and `_first` (:178-:182) with these three
helpers. `_probe` builds a probe row from a story, `_built` builds one world
of a story, and `_candidate_blocks` splits the printed candidate section into
one block per workload:

```python
# ---------------------------------------------------------------- the builder
#
# Spec 4b-1: the shared-origin family is built from `stories.Story` through
# the real pipeline, so the tests below read the rows a story produces and
# the lines a model sees. `propagation` is still the source of `multi`'s
# scenarios, which is why the data tests above stay.


def _probe(st, **kw):
    return cases.shared_origin_probe(st, generate._entry_rng("t", st.key), **kw)


def _built(st, world, width=None, seed=7):
    d = so.draw(st, random.Random(seed), width=width or len(st.victims))
    return so.build(st, d, world=world)


def _candidate_blocks(user):
    """The candidate section, split into one block of lines per workload."""
    menu = user.split("== BEGIN candidates ==")[1].split("== END candidates ==")[0]
    blocks, key = {}, None
    for line in menu.split("\n"):
        if line.startswith("- "):
            key = line[2:].split(" (")[0]
            blocks[key] = []
        elif key is not None:
            blocks[key].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}
```

Replace `test_builder_renders_one_verdict_row_per_victim` (:184-:190) with:

```python
def test_builder_renders_one_verdict_row_per_victim():
    """One verdict per flagged workload: the victims, plus the origin's own
    row when the broken world has one (`coredns-down` lists kube-system/coredns)."""
    for st in stories.exam():
        rows = json.loads(_probe(st).assistant)["verdicts"]
        extra = 1 if st.broken.origin_row is not None else 0
        assert len(rows) == len(st.victims) + extra, st.key
        assert len({r["workload"] for r in rows}) == len(rows), st.key
```

Replace `test_every_row_names_the_same_shared_cause` (:193-:227) with:

```python
def test_every_row_names_the_same_shared_cause():
    """The whole point, on a ruled exam story: the rules confirmed one cause
    group on every victim.

    A node story and a registry story bind one name, so the cause string is
    identical on every victim. A PVC story binds one claim per victim, so the
    strings differ and every one names a PVC. The plain exam stories make no
    such promise: their victims are named from their own lines, and the label
    follows the gold rule (two or more linked victims). The exam must still
    hold both labels, or this check proves nothing about either.
    """
    saw_shared = saw_none = False
    for st in stories.exam():
        ex = _probe(st)
        saw_shared |= ex.meta["label"] == "shared"
        saw_none |= ex.meta["label"] == "none"
        if st.cls != "R":
            continue
        verdicts = json.loads(ex.assistant)["verdicts"]
        assert ex.meta["label"] == "shared", st.key
        for v in verdicts:
            meta = ex.meta["workloads"][v["workload"]]
            assert meta["decided"] and meta["decided_outcome"] == "confirmed", st.key
        causes = {v["cause"] for v in verdicts}
        if st.origin_kind == "pvc":
            assert len(causes) >= 2, st.key
            assert all(cause.startswith("PVC ") for cause in causes), st.key
        else:
            assert len(causes) == 1, st.key
    assert saw_shared and saw_none, "both labels must be exercised"
```

Replace `test_the_summary_never_says_the_workloads_fail_for_separate_reasons` (:230-:236) with:

```python
def test_the_summary_never_says_the_workloads_fail_for_separate_reasons():
    """A broken world never calls its workloads separate: the rules either
    confirmed one cause ("share one upstream cause") or did not confirm it
    ("did not confirm one cause"). The phrase belongs to a healthy world only
    (Ruling 33), so only the broken probe is checked here."""
    for st in stories.exam():
        summary = json.loads(_probe(st).assistant)["summary"]
        assert propagation.SEPARATE_REASONS not in summary, st.key
        lines = [ln for ln in summary.split("\n") if ln.strip()]
        assert len(lines) <= c.MAX_SUMMARY_LINES, st.key
```

Replace `test_the_shared_cause_is_a_candidate_line_on_every_workload` (:280-:299) with:

```python
def test_the_shared_cause_is_a_candidate_line_on_every_workload():
    """The rules' cause is a candidate line on every workload it decides.

    The contract tells the model it may answer with "a candidate cause
    verbatim". When the rules confirm a cause, that cause is printed as a
    `considered` line in the workload's own block, so the right answer is
    inside the model's vocabulary and a wrong answer is a judgement failure,
    never a phrasing one. Read off the built rows and the printed section,
    not off a menu the test invented.
    """
    for st in stories.exam():
        if st.cls != "R":
            continue
        b = _built(st, "broken")
        blocks = _candidate_blocks(b.user)
        for row in b.rows:
            assert row.result.decided, (st.key, row.key)
            assert row.result.cause in {cd.cause for cd in row.candidates}, (st.key, row.key)
            assert f"considered {row.result.cause}: " in blocks[row.key], (st.key, row.key)
```

Replace `test_the_origin_evidence_is_read_once_and_leads` (:302-:318) with this test, under its new name:

```python
def test_the_origin_is_read_once_not_once_per_victim():
    """One shared cause means one read of the origin, not N copies of it.

    Restating the origin under every victim would make "the same sentence
    appears N times" a countable shortcut. The gather reads each node or
    claim once across the row, and prints each read once. (The old test also
    asked that the origin read come first. The real gather orders reads per
    workload, events then describe then log, so that half no longer holds and
    is not asserted.)
    """
    for st in stories.exam():
        b = _built(st, "broken")
        labels = [r.label for r in b.gathered.reads]
        assert len(set(labels)) == len(labels), st.key
        evidence = b.user.split("== BEGIN evidence ==")[1].split("== END evidence ==")[0]
        for label in labels:
            assert evidence.count(f"== {label} ==") == 1, (st.key, label)
        if st.cls == "R" and st.origin_kind == "node":
            node = [lb for lb in labels if lb.startswith("describe node ")]
            assert node == [f"describe node /{b.draw.scope_value}"], st.key
```

Replace `test_meta_carries_every_local_decoy_so_the_scorer_can_see_tag_following` (:321-:330) with this test, under its new name:

```python
def test_meta_names_the_story_and_has_no_made_up_decoys():
    for st in stories.exam():
        ex = _probe(st)
        assert ex.meta["case"] == "shared_origin_probe", st.key
        assert ex.meta["origin"] == st.key
        assert ex.meta["blast_radius"] == st.blast_radius
        assert ex.meta["decoy_causes"] == [], st.key
        assert set(ex.meta["decoy_by_workload"]) == set(ex.meta["workloads"]), st.key
        for decoys in ex.meta["decoy_by_workload"].values():
            for decoy in decoys:
                assert decoy in ex.user, (st.key, decoy)
```

Replace `test_meta_names_the_memorised_summary_phrase_to_score_against` (:333-:337) with this test, under its new name:

```python
def test_meta_drops_the_keys_the_made_up_menu_needed():
    """`origin_read_label`, `distractor_cause`, `wrong_summary_phrase` and
    `expected_confidence` described the invented origin read, the invented
    distractor and the old per-story confidence. The new rows have none of
    them (Ruling 8), on any of the four cases."""
    st = stories.by_key()["node-not-ready"]
    for build in (cases.shared_origin, cases.shared_origin_decoy,
                  cases.shared_origin_probe, cases.shared_origin_decoy_probe):
        meta = build(st, random.Random(3)).meta
        for gone in ("origin_read_label", "distractor_cause", "wrong_summary_phrase",
                     "expected_confidence"):
            assert gone not in meta, (build.__name__, gone)
```

Replace `test_the_prompt_is_contract_valid` (:340-:352) with:

```python
def test_the_prompt_is_contract_valid():
    for st in stories.exam():
        ex = _probe(st)
        assert ex.system == c.SYSTEM_PROMPT
        assert ex.user.endswith(c.CLOSING_INSTRUCTION)
        assert len(ex.user.encode("utf-8")) <= c.MAX_PROMPT_BYTES
        doc = json.loads(ex.assistant)
        assert set(doc) == {"verdicts", "summary"}
        assert 1 <= len(doc["verdicts"]) <= c.MAX_VERDICT_ROWS
        for row in doc["verdicts"]:
            assert row["confidence"] in c.CONFIDENCE_VALUES
            assert row["workload"] in ex.user
```

Replace `test_a_pinned_scope_is_the_same_for_every_victim` (:355-:362) with:

```python
def test_a_pinned_scope_is_the_same_for_every_victim():
    for st in stories.exam():
        if not st.scope_field:
            continue
        b = _built(st, "broken")
        scope = b.draw.scope_value
        assert scope, st.key
        pinned = [n.node if st.scope_field == "node" else n.ns for n in b.draw.victims]
        assert pinned == [scope] * len(pinned), st.key
        ex = _probe(st)
        assert ex.meta["scope_value"], st.key
        if st.cls == "R" and st.origin_kind == "node":
            causes = {v["cause"] for v in json.loads(ex.assistant)["verdicts"]}
            assert all(ex.meta["scope_value"] in cause for cause in causes), st.key
```

Replace `test_the_builder_is_deterministic` (:365-:370) with:

```python
def test_the_builder_is_deterministic():
    for st in stories.exam():
        a = _probe(st)
        b = _probe(st)
        assert generate.to_row(a) == generate.to_row(b), st.key
```

Replace `test_a_subset_row_renders_fewer_victims_from_the_same_scenario` (:373-:377) with:

```python
def test_a_subset_row_renders_fewer_victims_from_the_same_scenario():
    st = next(s for s in stories.exam() if len(s.victims) >= 3)
    ex = _probe(st, victims=2)
    extra = 1 if st.broken.origin_row is not None else 0
    assert len(json.loads(ex.assistant)["verdicts"]) == 2 + extra
    assert ex.group.count("propagation:") == 2
```

Replace `test_shared_origin_meta_is_derived_from_the_object_not_declared` (:512-:535) with this test, under its new name:

```python
def test_shared_origin_meta_is_derived_from_the_rules_not_declared():
    """R21: job/decided_* meta for a shared-origin victim comes from the rules
    pass over the built world, not from a hand-set 'job: 1' literal."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin(st, random.Random(7), victims=2)
    b = _built(st, "broken", width=2)

    metas = ex.meta["workloads"]
    assert len(metas) == 2
    for row in b.rows:
        meta = metas[row.key]
        assert set(meta) == {
            "job", "decided", "decided_cause", "decided_outcome",
            "decided_evidence", "expected_cause", "own_cause_keywords",
            "own_cause_must_not"}
        # Shared-origin keys come from stories, not from a catalog entry,
        # so there are no must-not words.
        assert meta["own_cause_must_not"] == []
        assert meta["job"] == 1
        assert meta["decided"] is True
        assert meta["decided_outcome"] == "confirmed"
        assert meta["decided_cause"] == row.result.cause
        assert meta["decided_evidence"] == row.result.evidence
    assert ex.meta["label"] in ("shared", "none")
    assert set(ex.meta["decoy_by_workload"]) == set(metas)
```

Replace `test_shared_origin_decoy_meta_is_not_decided_when_healthy` (:538-:548) with:

```python
def test_shared_origin_decoy_meta_is_not_decided_when_healthy():
    """The healthy world has the origin fixed; no victim is confirmed on it,
    so the rules decide none of them and every workload is graded on job 2."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_decoy(st, random.Random(7), victims=2)

    assert len(ex.meta["workloads"]) == 2
    for meta in ex.meta["workloads"].values():
        assert meta["decided"] is False
        assert meta["job"] == 2
    assert ex.meta["label"] == "none"
```

Replace `test_registry_unreachable_shared_read_agrees_with_the_declared_object` (:551-:571) with this test, under its new name:

```python
def test_registry_unreachable_shared_read_agrees_with_the_decision():
    """The registry-events consistency rule: the rules decide a registry from
    the pulling pod's own events, so the broken world must print a connection
    error there and the healthy world must not."""
    st = stories.by_key()["registry-unreachable"]
    broken = _built(st, "broken", width=2)
    healthy = _built(st, "healthy", width=2)

    for row in broken.rows:
        assert row.result.decided, row.key
        assert row.result.outcome == "confirmed", row.key
    assert not any(row.result.decided for row in healthy.rows)

    def pull_events(built):
        return [r.content.lower() for r in built.gathered.reads if r.label.startswith("events ")]

    for text in pull_events(broken):
        assert any(lit in text for lit in objects.CONNECTION_LITERALS), text
    for text in pull_events(healthy):
        assert not any(lit in text for lit in objects.CONNECTION_LITERALS), text
```

Replace `test_registry_count_template_fills_in_the_rendered_victim_count` (:574-:595) with:

```python
def test_registry_count_template_fills_in_the_rendered_victim_count():
    """A registry cause counts the workloads the row renders (spec section 4,
    "Registry count"): 2 victims say 2 and 3 victims say 3. This is the fix
    for the bug the exam's row 252 disclosed, where a count fixed in the data
    stayed "3" on a row that showed only 2 victims, so the rules pass's own
    cause line claimed more workloads than the row showed.

    Victim images always pull from `registry.example.com`, so that is the host
    the cause names, and no other host is printed.
    """
    st = stories.by_key()["registry-unreachable"]
    assert len(st.victims) >= 3

    two = cases.shared_origin(st, random.Random(1), victims=2)
    assert "registry registry.example.com (2 workloads failing to pull)" in two.user
    assert "(3 workloads failing to pull)" not in two.user

    three = cases.shared_origin(st, random.Random(1), victims=3)
    assert "registry registry.example.com (3 workloads failing to pull)" in three.user
    assert "(2 workloads failing to pull)" not in three.user

    for row in _built(st, "broken", width=3).rows:
        assert row.names.image.startswith("registry.example.com/"), row.key
```

Replace `test_shared_origin_wrappers_merge_the_new_meta_without_losing_existing_keys` (:635-:664) with:

```python
def test_shared_origin_wrappers_merge_the_new_meta_without_losing_existing_keys():
    """The four thin wrappers share one meta builder: each keeps the keys it
    writes today and gains 'workloads', 'label' and 'decoy_by_workload'. The
    four keys the made-up menu needed are gone (Ruling 8)."""
    st = stories.by_key()["node-not-ready"]
    common = ("workloads", "label", "decoy_by_workload", "case", "origin", "blast_radius",
              "scope_value", "expected", "decoy_causes")

    for build in (cases.shared_origin, cases.shared_origin_decoy,
                  cases.shared_origin_probe, cases.shared_origin_decoy_probe):
        meta = build(st, random.Random(3)).meta
        for key in common:
            assert key in meta, (build.__name__, key)
        assert meta["decoy_causes"] == [], build.__name__

    probe = cases.shared_origin_decoy_probe(st, random.Random(3))
    phrases = probe.meta["shared_claim_phrases"]
    assert phrases and all(isinstance(p, str) and p for p in phrases)
    for build in (cases.shared_origin, cases.shared_origin_decoy, cases.shared_origin_probe):
        assert "shared_claim_phrases" not in build(st, random.Random(3)).meta, build.__name__
```

Do not run the file yet. Two old tests that Step B3 deletes are still in it.

- [ ] **Step B3: Delete the made-up-menu tests from `tests/test_propagation.py`**

Delete these three tests and the helper `_menu_blocks`, with the two blank
lines after each. After Step B2 nothing calls `_menu_blocks`, because the
rewritten candidate test uses `_candidate_blocks`:

- `_menu_blocks` (:239-:248): it split the made-up menu into blocks. The new `_candidate_blocks` splits the real candidate section instead.
- `test_the_decoy_leads_every_candidate_menu_and_the_answer_trails` (:251-:277): it checks the order of the made-up three-candidate menu (decoy first, distractor second, shared cause last). The new rows print the real candidates the gather produced, in the order the rules gave them, so there is no invented order to test.
- `test_registry_origin_rewrites_victim_images_to_the_declared_host` (:598-:612): it checks that the old builder rewrote victim images to the invented origin object's host. The new rows take the image from the story's own lines. The host check lives on in `test_registry_count_template_fills_in_the_rendered_victim_count` (image starts with `registry.example.com/`) and in `test_ruled_registry_row_names_its_own_rendered_victim_count` (Step B5).
- `test_registry_example_com_host_is_a_no_op_rewrite` (:615-:632): it checks that the rewrite above leaves the exam's host alone, through `cases._propagation_names`, which Task 7 deletes. With no rewrite there is nothing to leave alone.

Then:

Run: `PYTEST tests/test_propagation.py`
Expected: PASS. In the draft's sandbox that was 34 passed (18 kept, 16 rewritten). If a rewritten test fails on the real stories, do not loosen it. Read Questions 1 and 2 at the end of this part, then stop and report the test name and the story key.

- [ ] **Step B4: Rewrite `tests/test_healthy_evidence.py`**

Nothing in this file is deleted. Seven of its tests checked the old twin
mechanics (the inventory fixed, only the reads swapped, the `_before_reads`
split); the new rows still have twins, so each is rewritten against the new
mechanics under a new name.

Keep these two tests and the three helpers above the second one. They read
`propagation.py`'s own table, which `multi` still draws:
`test_the_one_victim_whose_evidence_names_the_origin_has_a_healthy_twin` (:71),
`test_a_victim_whose_evidence_names_a_fault_token_declares_healthy_evidence` (:187),
and `_tokens`, `_looks_like_a_label`, `_fault_tokens` (:147-:184).

Replace the module docstring, the imports, the constants and the helpers
(:1-:68, down to the end of `_pair`) with the block below. This drops the old
helpers `_before_reads`, `_reads` and `_without_decided`. The new `_entry`
reads one workload's inventory entry and `_read` reads one evidence read:

```python
"""A healthy-world finding must not say the origin is broken.

A twin pair is one story built twice from one draw: the broken world, and the
healthy world, which is the broken world with the origin fixed plus any
victim-side edits the story declares. The victim-side edits matter. Where a
victim's own finding names a fact of the origin, a healthy twin that reuses
the text carries a finding that says the origin is broken, a cluster block
that says it is fine, and a label that says "none". The node-disk-pressure
decoy did exactly that -- `untolerated taint node.kubernetes.io/disk-pressure`
in the prompt of a world whose node has no disk pressure -- and the model
believed the finding. `VictimText.evidence_healthy` and `events_healthy` are
the fix: the same finding in the world where the origin is fine, printed only
by the healthy half.

Spec 4b-1: these tests read the rows a story builds through the real pipeline.
Two tests still read `propagation.py`'s own data, which does not change and
which `multi` still draws: the first one, and the fault-token sweep further down.
"""

import random
import re

from kubeagent_verdict.dataset import cases, stories
from kubeagent_verdict.dataset import propagation as prop
from kubeagent_verdict.dataset import shared_origin as so

TAINT = "node.kubernetes.io/disk-pressure"
NETWORK_TAINT = "node.kubernetes.io/network-unavailable"
HEALTHY_TAINT = "dedicated=gpu"
EVIDENCE_MARK = "== BEGIN evidence =="
DECIDED_PREFIX = "    decided by rules: "
_UNTOLERATED = re.compile(r"untolerated taint ([^\s,)]+)")

# A maximal run of these characters, at least 6 long, is a "token" for the
# fault-token sweep further down.
_TOKEN_RE = re.compile(r"[A-Za-z0-9._/=-]{6,}")


def _scenario(key: str) -> prop.Propagation:
    return next(p for p in (*prop.trainable_scenarios(), *prop.all_scenarios())
                if p.key == key)


def _decided(user: str) -> list[str]:
    return [line for line in user.splitlines() if line.startswith(DECIDED_PREFIX)]


def _pair(st: stories.Story) -> tuple[cases.Example, cases.Example]:
    """The broken probe and its healthy twin, from one seed and so one draw."""
    return (cases.shared_origin_probe(st, random.Random(7)),
            cases.shared_origin_decoy_probe(st, random.Random(7)))


def _built(st: stories.Story, world: str) -> so.Built:
    d = so.draw(st, random.Random(7), width=len(st.victims))
    return so.build(st, d, world=world)


def _entry(user: str, key: str) -> str:
    """One workload's inventory entry: its `- ns/name (` line and the indented
    lines under it. The entry ends at the next `- ` line or at any line that
    does not start with a space."""
    inventory = user.split("== BEGIN inventory ==")[1].split("== END inventory ==")[0]
    kept, inside = [], False
    for line in inventory.split("\n"):
        if line.startswith("- "):
            inside = line.startswith(f"- {key} (")
        elif not line.startswith(" "):
            inside = False
        if inside:
            kept.append(line)
    return "\n".join(kept)


def _read(user: str, label: str) -> str:
    """One evidence read: the text under its `== label ==` line, up to the next
    `== ` line. Empty when the prompt prints no such read."""
    evidence = user.split(EVIDENCE_MARK)[1].split("== END evidence ==")[0]
    parts = evidence.split(f"== {label} ==\n")
    return parts[1].split("\n== ")[0] if len(parts) > 1 else ""


def _victim_row(built: so.Built, index: int) -> so.Row:
    return next(r for r in built.rows if r.role == "victim" and r.index == index)
```

Replace the five tests from `test_the_disk_pressure_decoy_inventory_no_longer_names_the_taint`
(:78) to the end of `test_the_broken_half_never_renders_the_healthy_evidence`
(:144) with the block below. The old names map to the new ones like this:

| Old test | New test |
|---|---|
| `test_the_disk_pressure_decoy_inventory_no_longer_names_the_taint` (:78) | `test_the_disk_pressure_healthy_world_never_prints_the_taint` |
| `test_the_healthy_finding_and_the_healthy_read_name_the_same_taint` (:84) | `test_the_healthy_finding_and_the_healthy_events_name_the_same_taint` |
| `test_the_halves_differ_only_in_the_reads_the_evidence_and_the_decided_line` (:91) | `test_the_halves_differ_in_at_least_one_printed_line` (Ruling 35) |
| `test_the_decided_line_is_the_rule_engine_re_reading_the_origin` (:110) | same name, rewritten |
| `test_the_broken_half_never_renders_the_healthy_evidence` (:139) | `test_the_broken_half_never_renders_the_healthy_text` |

```python
def test_the_disk_pressure_healthy_world_never_prints_the_taint():
    """The first leak, on the new rows: the broken world names the taint, and
    the healthy world, whose node has no pressure, names it nowhere -- not in
    the finding line and not in the scheduler's event."""
    probe, decoy = _pair(stories.by_key()["node-disk-pressure"])
    assert TAINT in probe.user
    assert TAINT not in decoy.user


def test_the_healthy_finding_and_the_healthy_events_name_the_same_taint():
    """The two places a prompt names the untolerated taint agree, in each world.

    The broken world names the disk-pressure taint in the finding and in the
    pod's events. The healthy world names an operator's own taint in both. A
    finding that names one taint above events that name another would be two
    stories in one prompt.
    """
    st = stories.by_key()["node-disk-pressure"]
    for world, taint in (("broken", TAINT), ("healthy", HEALTHY_TAINT)):
        built = _built(st, world)
        seen = 0
        for row in built.rows:
            finding = _UNTOLERATED.findall(_entry(built.user, row.key))
            if not finding:
                continue
            events = _UNTOLERATED.findall(
                _read(built.user, f"events {row.names.ns}/{row.names.pod}"))
            assert finding == events == [taint], (world, row.key, finding, events)
            seen += 1
        assert seen, f"no {world} victim names an untolerated taint"


def test_the_halves_differ_in_at_least_one_printed_line():
    """The pair-mechanics promise, machine-checked for every story (Ruling 35).

    The two halves need not differ only in their reads, and the rule engine's
    decided line is one of the lines that may differ. They must differ in at
    least one printed line, or the pair teaches nothing. They must also stay
    one pair: the same draw, so the same victims, named by the same group.
    """
    for st in stories.by_key().values():
        probe, decoy = _pair(st)
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), st.key
        assert probe.group == decoy.group, st.key
        for part in probe.group.split("+"):
            victim = part.split(":", 2)[2]
            assert victim in probe.meta["workloads"], (st.key, victim)
            assert victim in decoy.meta["workloads"], (st.key, victim)
        assert "shared_claim_phrases" in decoy.meta, st.key
        assert "shared_claim_phrases" not in probe.meta, st.key


def test_the_decided_line_is_the_rule_engine_re_reading_the_origin():
    """The one thing the pair cannot hold fixed, stated rather than hidden.

    The rules re-check each candidate against the gather's fresh reads and
    the prompt prints what they decided. On the three ruled exam stories
    (node-not-ready, storage-provisioner-down, registry-unreachable) the
    fresh read of the origin is what decides every victim, so the broken half
    prints one decided line per victim and the healthy half prints none. The
    line is the rule engine's reading of the reads, so a model separating the
    halves on it is separating them on the evidence. The three plain exam
    stories give the rules no node, claim or registry to confirm, so neither
    half decides anything.
    """
    ruled = 0
    for st in stories.exam():
        probe, decoy = _pair(st)
        if st.cls == "P":
            assert _decided(probe.user) == [], st.key
            assert _decided(decoy.user) == [], st.key
            continue
        ruled += 1
        metas = probe.meta["workloads"].values()
        assert all(m["decided"] for m in metas), st.key
        want = sorted(f"{DECIDED_PREFIX}{m['decided_cause']} — {m['decided_outcome']}"
                      for m in metas)
        assert sorted(_decided(probe.user)) == want, st.key
        assert _decided(decoy.user) == [], st.key
        assert not any(m["decided"] for m in decoy.meta["workloads"].values()), st.key
    assert ruled == 3, ruled


def test_the_broken_half_never_renders_the_healthy_text():
    """A victim's healthy finding and healthy events are printed by the
    healthy half and never by the broken half.

    Swept over every story. A healthy finding is printed verbatim in the
    victim's inventory entry, so it is looked for there. A healthy event is
    run through kubeagent's redaction before it is printed (an address
    becomes `<redacted>`), so the event is compared as the printed read: the
    two halves must print different events for that pod. A healthy text that
    equals the broken one is skipped, because it cannot tell the halves apart.
    """
    checked = set()
    for st in stories.by_key().values():
        broken, healthy = _built(st, "broken"), _built(st, "healthy")
        for i, v in enumerate(st.victims[:broken.draw.width]):
            row = _victim_row(broken, i)
            if v.evidence_healthy is not None and v.evidence_healthy != v.evidence:
                text = so._sub(v.evidence_healthy, row.names, broken.draw)
                assert text in _entry(healthy.user, row.key), (st.key, row.key, text)
                assert text not in _entry(broken.user, row.key), (st.key, row.key, text)
                checked.add(st.key)
            if v.events_healthy is not None and v.events_healthy != v.events:
                label = f"events {row.names.ns}/{row.names.pod}"
                assert _read(healthy.user, label), (st.key, label)
                assert _read(healthy.user, label) != _read(broken.user, label), (st.key, label)
                checked.add(st.key)
    assert {"coredns-down", "node-disk-pressure", "node-network-unavailable"} <= checked, checked
```

Replace the last two tests (:211-:219) with the block below. It holds the two
network-unavailable tests, rewritten (`test_the_network_unavailable_decoy_inventory_no_longer_names_the_taint`
becomes `test_the_network_unavailable_healthy_world_never_prints_the_taint`),
and one new test with its two helpers. The new test sweeps every story: a
healthy prompt must not name a node condition that only the broken world has.
It is the general form of the two leaks this file was written for.

```python
def test_the_network_unavailable_healthy_world_never_prints_the_taint():
    """NetworkUnavailable prints no health line (kubeagent never checks it),
    so the victim's own finding is the only place the two worlds can differ."""
    probe, decoy = _pair(stories.by_key()["node-network-unavailable"])
    assert NETWORK_TAINT in probe.user
    assert NETWORK_TAINT not in decoy.user


def test_the_network_unavailable_healthy_finding_names_a_different_taint():
    st = stories.by_key()["node-network-unavailable"]
    _, decoy = _pair(st)
    built = _built(st, "healthy")
    assert any(HEALTHY_TAINT in _entry(decoy.user, row.key) for row in built.rows)


def _squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _broken_only_words(st: stories.Story) -> list[str]:
    """The names of the node conditions only the broken world carries: a
    pressure condition by its type, a Ready that is False as "NotReady"."""
    return [("NotReady" if cd.type == "Ready" else cd.type)
            for cd in st.broken.conditions if cd not in st.healthy.conditions]


def test_a_healthy_world_never_names_a_node_condition_only_the_broken_world_has():
    """A healthy prompt must not assert a fact only the broken origin has.

    Swept over every story whose broken world carries a node condition the
    healthy world does not (DiskPressure, PIDPressure, NotReady, ...). The
    condition's name, with case and punctuation removed, may appear nowhere
    in the healthy prompt. That also catches the taint spelling of the same
    fact (`node.kubernetes.io/disk-pressure` squashes to a string holding
    `diskpressure`), which is how both known leaks, node-disk-pressure and
    node-network-unavailable, got into a healthy inventory.
    """
    checked = set()
    for st in stories.by_key().values():
        words = _broken_only_words(st)
        if not words:
            continue
        healthy = _squash(_built(st, "healthy").user)
        for word in words:
            assert _squash(word) not in healthy, (st.key, word)
        checked.add(st.key)
    assert {"node-not-ready", "node-pid-pressure", "node-disk-pressure"} <= checked, checked
```

Run: `PYTEST tests/test_healthy_evidence.py`
Expected: PASS. In the draft's sandbox that was 10 passed (2 kept, 7 rewritten, 1 new). If the new sweep or the fault-token tests fail on the real stories, do not loosen them. Read Questions 1 and 4 at the end of this part, then stop and report the test name, the story key and the line it printed.

- [ ] **Step B5: Rewrite and prune `tests/test_ruled_scenarios.py`**

Keep these 16 tests, with the constants and helpers above them (`RULED`,
`PLAIN`, `EVAL`, `NODE_KEYS`, `PVC_STORAGE_CLASSES`, `REGISTRY_KEYS`,
`_EXAM_ONLY_LABELS`, `_INDEPENDENCE_PHRASES`, `_IPV4`, `_URL`, `_victim_blob`,
`_scenario_blob`, `_WORKLOAD_KINDS`, `_COUNT_PHRASE`). They read
`propagation.ruled_scenarios()`, which `multi` still draws:
`test_a_ruled_scenario_pool_exists_with_six_stories` (:86),
`test_ruled_scenario_keys_are_disjoint_from_eval_and_trainable` (:90),
`test_no_ruled_scenario_reuses_an_eval_or_trainable_answer_string` (:97),
`test_no_ruled_scenario_shares_a_local_cause_with_trainable` (:115),
`test_every_ruled_scenario_obeys_the_authoring_floor` (:125),
`test_blast_radius_and_scope_field_agree_for_every_ruled_scenario` (:140),
`test_every_ruled_scenario_has_at_least_three_victims` (:146),
`test_pass_confidence_varies_within_every_ruled_scenario` (:151),
`test_every_ruled_scenario_carries_a_healthy_origin_read` (:157),
`test_no_ruled_scenario_text_carries_a_banned_identifier_shape` (:199),
`test_no_ruled_scenario_phrase_leaks_a_shared_or_independence_claim` (:210),
`test_ruled_origin_read_label_is_never_an_exam_only_label` (:222),
`test_ruled_node_stories_never_mention_a_lease_or_heartbeat` (:231),
`test_ruled_pvc_storage_classes_are_new_and_plain` (:240),
`test_ruled_registry_hosts_are_new_and_scan_reason_is_the_count_template` (:267),
`test_ruled_registry_content_carries_no_count_and_names_no_workload` (:293).

Replace the module docstring (:1-:19) with:

```python
"""The six ruled stories (spec section 4): origins where the DETERMINISTIC
rules pass itself decides the shared cause, not just a scenario author's
say-so. `propagation.trainable_scenarios()` now returns the 48 plain
stories plus these six (spec section 6's pool merge), so every check below
that means "disjoint from the plain pool" filters `trainable_scenarios()`
down to `PLAIN` first rather than comparing against the merged pool --
comparing the six ruled stories against a pool that now contains them
would always pass, vacuously. It still has to clear the same authoring
floor and the same eval-disjointness rules the plain pool already clears,
which is why several checks below mirror a named test in
`test_shared_origin_training.py` rather than inventing a new shape.

Two groups of tests live here. The table tests read `propagation.py`'s
`ruled_scenarios()` directly: that data is unchanged and `multi` still
draws it. The rendered-row tests (the last section) build the same six
keys from `stories.py` through the real pipeline. A ruled story's BROKEN
world puts a real object behind every victim (a NotReady node, a Pending
claim, a registry whose pulls fail), so the rules pass confirms each one
against the same group key and the label is "shared"; the HEALTHY world
has no such object, no victim is decided, and the label is "none". That is
asserted directly, by building both worlds, rather than trusted from the
story's shape.
"""
```

Replace the imports (:21-:29) with:

```python
import json
import random
import re

import pytest

from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, propagation, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score
```

Delete these four tests (:162-:196) and the blank lines after them. Each
checks the invented origin read, which no longer exists in the new rows:

- `test_every_ruled_scenario_declares_at_least_four_origin_variants` (:162): the origin variants were the invented read's alternative wordings. The new rows have one origin read, the real one from the gather. Nothing in `src/` reads `origin_variants` any more.
- `test_every_ruled_variant_first_line_is_literal_and_unique_within_its_scenario` (:168): the same variants, checked for their first lines.
- `test_every_ruled_scenario_names_its_state_in_words` (:180): it checks that each variant names the origin's state (`origin_state`) in broken and healthy words. The state now comes from the real lines; the rendered-row test below checks that the broken prompt shows `NotReady`, the storage class or the registry cause line and the healthy prompt does not.
- `test_a_ruled_victim_read_never_asserts_a_broken_origin_on_the_healthy_half` (:190): it checks `healthy_read_content` on the invented read. The healthy half of the new rows is checked directly in `test_ruled_scenario_coherence_across_victim_counts_and_salts`, and for every story in `test_a_healthy_world_never_names_a_node_condition_only_the_broken_world_has` (Step B4).

Replace everything from the banner `# --- rendered rows` (:316) to the end of
the file (:473) with the block below. It holds 12 tests: 10 rewritten under
their old name, 1 rewritten under a new name
(`test_unverified_node_twin_matches_the_healthy_twins_names_menus_and_labels`
becomes `test_unverified_node_twin_matches_the_healthy_twins_names_and_labels`;
the menu is gone), and 1 new test,
`test_the_ruled_stories_are_the_six_ruled_scenarios`, which ties
`stories.RULED_ORDER` to the same six keys the table tests above read. The
parametrized tests now run once per story and row width (2 up to all of the
story's victims). `PVC_KEYS` and `NOT_NODE_KEYS` move up into this block.

```python
# ----------------------------------------------------------- rendered rows

# The rendered-row tests below build each ruled story through the real
# pipeline (`so.draw` then `so.build`) and read the prompt it prints.
# `propagation.ruled_scenarios()` above and `stories.RULED_ORDER` here must
# name the same six keys, or the two halves of this file would be checking
# different things.

DECIDED = "    decided by rules: "
REGISTRY_HOST = "registry.example.com"


def _story(key):
    return stories.by_key()[key]


def _widths(st):
    """Every row width the story can render: 2 up to all of its victims."""
    return range(2, len(st.victims) + 1)


def _built(st, world, width, salt=7, unverified=False):
    d = so.draw(st, random.Random(salt), width=width)
    return so.build(st, d, world=world, unverified=unverified)


def _summary(ex):
    return json.loads(ex.assistant)["summary"]


RULED_ROWS = [(key, w) for key in stories.RULED_ORDER for w in _widths(_story(key))]
RULED_IDS = [f"{key}-{w}" for key, w in RULED_ROWS]
NODE_ROWS = [(key, w) for key, w in RULED_ROWS if key in NODE_KEYS]
NODE_IDS = [f"{key}-{w}" for key, w in NODE_ROWS]

PVC_KEYS = set(PVC_STORAGE_CLASSES)
NOT_NODE_KEYS = PVC_KEYS | REGISTRY_KEYS


def test_the_ruled_stories_are_the_six_ruled_scenarios():
    """The table tests read `propagation.ruled_scenarios()`; the rendered-row
    tests read `stories.RULED_ORDER`. Both must name the same six keys."""
    assert set(stories.RULED_ORDER) == {p.key for p in RULED}
    assert len(stories.RULED_ORDER) == 6
    assert set(stories.RULED_ORDER) == NODE_KEYS | PVC_KEYS | REGISTRY_KEYS


@pytest.mark.parametrize("key,victims", RULED_ROWS, ids=RULED_IDS)
def test_ruled_scenario_renders_shared_on_broken_and_none_on_healthy(key, victims):
    st = _story(key)
    for salt in (1, 2, 3, 4, 5):
        broken = cases.shared_origin(st, random.Random(salt), victims=victims)
        healthy = cases.shared_origin_decoy(st, random.Random(salt), victims=victims)
        assert broken.meta["label"] == "shared", (key, victims, salt)
        assert healthy.meta["label"] == "none", (key, victims, salt)


@pytest.mark.parametrize("key", stories.RULED_ORDER)
def test_ruled_scenario_coherence_across_victim_counts_and_salts(key):
    """Spec section 4, 'Coherence', checked on the BUILT prompt: in the
    broken world every victim is decided by the rules and the prompt shows
    the origin's own state (a NotReady node, the claim's storage class, the
    registry cause line); in the healthy world no victim is decided and none
    of that state is printed."""
    st = _story(key)
    for victims in _widths(st):
        for salt in (1, 2, 3):
            broken = _built(st, "broken", victims, salt)
            healthy = _built(st, "healthy", victims, salt)
            where = (key, victims, salt)
            assert all(r.result.decided for r in broken.rows), where
            assert not any(r.result.decided for r in healthy.rows), where
            assert broken.user.count(DECIDED) == victims, where
            assert DECIDED not in healthy.user, where
            if key in NODE_KEYS:
                assert "NotReady" in broken.user, where
                assert "NotReady" not in healthy.user, where
            if key in PVC_KEYS:
                mark = f"storageClass={st.broken.pvc_class}"
                assert mark in broken.user, where
                assert mark not in healthy.user, where
            if key in REGISTRY_KEYS:
                assert f"{DECIDED}registry {REGISTRY_HOST} (" in broken.user, where


@pytest.mark.parametrize("key", sorted(REGISTRY_KEYS))
def test_ruled_registry_row_names_its_own_rendered_victim_count(key):
    """The Task 6 fix (spec section 4, 'Registry count'), applied to the real
    ruled registry stories: the rules pass's own cause line names however
    many victims THIS row draws, never a fixed digit."""
    st = _story(key)
    for victims in _widths(st):
        b = _built(st, "broken", victims)
        cause = f"registry {REGISTRY_HOST} ({victims} workloads failing to pull)"
        assert b.user.count(f"{DECIDED}{cause} — confirmed") == victims, (key, victims)


# --------------------------------------------------- the unverified twin

# Spec section 5: one node pair in three gets an unverified broken twin
# instead of the confirmed one. `shared_origin(..., unverified=True)` is
# only ever the BROKEN half -- there is no unverified decoy variant --
# so every check below compares it against the healthy twin's names and
# label only where the two are expected to agree, and reads its own
# prompt, verdicts and meta everywhere else. (A refused read cannot be
# unverified when there is no down node to refuse, hence the ValueError
# guards: Ruling 31.)


@pytest.mark.parametrize("key", sorted(NOT_NODE_KEYS))
def test_unverified_true_raises_for_a_ruled_pvc_or_registry_story(key):
    st = _story(key)
    with pytest.raises(ValueError, match="unverified"):
        _built(st, "broken", 2, salt=1, unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(st, random.Random(1), victims=2, unverified=True)


def test_unverified_true_raises_for_a_plain_trainable_story():
    plain = next(st for st in stories.trainable() if st.cls == "P")
    with pytest.raises(ValueError, match="unverified"):
        _built(plain, "broken", 2, salt=1, unverified=True)
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(plain, random.Random(1), victims=2, unverified=True)


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_labels_none_with_the_did_not_confirm_summary(key, victims):
    st = _story(key)
    for salt in (1, 2, 3, 4, 5):
        ex = cases.shared_origin(st, random.Random(salt), victims=victims, unverified=True)
        assert ex.meta["label"] == "none", (key, victims, salt)
        assert _summary(ex).startswith(
            f"{victims} workloads are failing, and kubeagent's rules did "
            "not confirm one cause on two or more of them."), (key, victims, salt)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_origin_read_says_read_failed_is_forbidden(key):
    st = _story(key)
    b = _built(st, "broken", 2, salt=1, unverified=True)
    node = b.draw.scope_value
    assert node, key
    assert f'read failed: nodes "{node}" is forbidden' in b.user


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_every_row_decided_unverified_with_rules_cause(key, victims):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(2), victims=victims, unverified=True)
    rows = json.loads(ex.assistant)["verdicts"]
    assert len(rows) == victims
    for row in rows:
        assert row["cause"].startswith("node ") and row["cause"].endswith("(NotReady)"), row
        assert "did not clear the earlier finding" in row["rationale"], row
        assert "is forbidden" in row["rationale"], row


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_workloads_meta_marks_decided_outcome_unverified(key):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(3), victims=2, unverified=True)
    assert ex.meta["workloads"], key
    for wm in ex.meta["workloads"].values():
        assert wm["decided"] is True, key
        assert wm["decided_outcome"] == "unverified", key
        assert wm["job"] == 1, key


@pytest.mark.parametrize("key,victims", NODE_ROWS, ids=NODE_IDS)
def test_unverified_node_twin_job1_accepts_every_row(key, victims):
    st = _story(key)
    ex = cases.shared_origin(st, random.Random(4), victims=victims, unverified=True)
    verdicts = {row["workload"]: row for row in json.loads(ex.assistant)["verdicts"]}
    assert set(verdicts) == set(ex.meta["workloads"])
    for wkey, wm in ex.meta["workloads"].items():
        assert score.job1(wm, verdicts[wkey]) == 1.0, (key, victims, wkey)


@pytest.mark.parametrize("key", sorted(NODE_KEYS))
def test_unverified_node_twin_matches_the_healthy_twins_names_and_labels(key):
    """`so.draw` makes every rng call before it looks at the world (Ruling
    11), so at the same salt the unverified twin and the healthy twin share
    a pair name, an origin node and the same workloads in the same order.
    Both are labelled "none". What each prompt prints, and what each
    verdict says, is allowed to differ and is not compared here."""
    st = _story(key)
    for victims in _widths(st):
        for salt in (1, 2, 3):
            unverified = cases.shared_origin(
                st, random.Random(salt), victims=victims, unverified=True)
            healthy = cases.shared_origin_decoy(st, random.Random(salt), victims=victims)
            where = (key, victims, salt)
            assert unverified.group == healthy.group, where
            assert unverified.meta["origin"] == healthy.meta["origin"] == key, where
            assert unverified.meta["scope_value"] == healthy.meta["scope_value"], where
            assert list(unverified.meta["workloads"]) == list(healthy.meta["workloads"]), where
            assert list(unverified.meta["expected"]) == list(healthy.meta["expected"]), where
            assert unverified.meta["label"] == healthy.meta["label"] == "none", where
```

Run: `PYTEST tests/test_ruled_scenarios.py`
Expected: PASS. In the draft's sandbox that was 55 passed; the number depends on how many victims each real ruled story has, so it is not a pin. If a rewritten test fails on the real stories, do not loosen it. Read Questions 1 to 3 at the end of this part, then stop and report the test name, the story key and the printed line.

- [ ] **Step B6: MEASURE the evidence-overlap numbers and re-pin the two family entries**

`tests/test_evidence_overlap.py` hashes every evidence read in the 249 exam
rows (masking names) and counts how many also appear in the kept training
rows. It pins that count per case in `DECLARED`. Two entries are about the
shared-origin family: `shared_origin_probe` is `(3, 34)` and
`shared_origin_decoy_probe` is `(2, 34)` today. The first number is how many
reads match training, the second is how many reads the slice has. The 10 + 10
family rows are rebuilt from real lines, so both numbers can change. The 229
other exam rows are pinned byte-identical elsewhere, and their four entries
must not move.

The test code does not change. This step measures, checks, and writes the two
entries plus the comment beside them. It also rewrites the history line near
the end of the module comment (`# still holds: 0 of 7164 kept rows and 0 of
249 test rows.`) with the new row counts.

What it checks before it writes anything:
- the exam is 249 rows, 10 of them `shared_origin_probe` and 10 `shared_origin_decoy_probe`;
- neither family slice is empty;
- the four other `DECLARED` entries, as measured, equal what the file declares;
- no kept or exam row has an empty evidence block (the history line says "0");
- no exam story is also a training story (`stories.EXAM_KEYS` and `stories.trainable()` do not overlap).

If any check fails, the script prints `CHECK FAILED` and the reasons and
exits without touching the file. Then stop, commit nothing, and report
DONE_WITH_CONCERNS with the printed numbers. Do not move a pin to make a
check pass. Do not use `-update`.

Run from the repo root:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
import datetime
import sys

sys.path.insert(0, "tests")
import test_evidence_overlap as t
from kubeagent_verdict.dataset import generate, stories

TARGET = "tests/test_evidence_overlap.py"
FAMILY = ("shared_origin_probe", "shared_origin_decoy_probe")

exs = generate.generate(seed=t.SEED, size=t.SIZE)
train, val = generate.split(exs, seed=t.SEED)
test = generate.test_set()
kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
trained = {t._digest(t._mask(r, ex)) for ex in kept for r in t._reads(ex)}

measured, hit_reads = {}, {}
for case in t.DECLARED:
    pairs = [(ex, r) for ex in test if ex.case == case for r in t._reads(ex)]
    hits = [(ex, r) for ex, r in pairs if t._digest(t._mask(r, ex)) in trained]
    measured[case] = (len(hits), len(pairs))
    hit_reads[case] = hits

print("test rows", len(test), "| kept training rows", len(kept))
print("exam rows:", {c: sum(1 for ex in test if ex.case == c) for c in FAMILY})
print("case".ljust(34), "declared".ljust(10), "measured")
for case, want in t.DECLARED.items():
    got = measured[case]
    note = "" if got == want else ("   <- family, moves" if case in FAMILY else "   <- MOVED")
    print(case.ljust(34), str(want).ljust(10), got, note)
for case in FAMILY:
    print(f"reads of {case} that a kept training row also prints:")
    for ex, r in hit_reads[case]:
        print("   ", repr(r.strip().splitlines()[0][:90]))

empty_kept = sum(1 for ex in kept if t._reads(ex) == [])
empty_test = sum(1 for ex in test if t._reads(ex) == [])
print("rows with an empty evidence block: kept", empty_kept, "| test", empty_test)

problems = []
leaked = sorted(set(stories.EXAM_KEYS) & {s.key for s in stories.trainable()})
if leaked:
    problems.append(f"an exam story is also a training story: {leaked}")
if len(test) != 249:
    problems.append(f"the exam is {len(test)} rows, not 249")
for case in FAMILY:
    n = sum(1 for ex in test if ex.case == case)
    if n != 10:
        problems.append(f"{case}: {n} exam rows, not 10")
    if measured[case][1] == 0:
        problems.append(f"{case}: no reads, the slice is missing")
for case, want in t.DECLARED.items():
    if case not in FAMILY and measured[case] != want:
        problems.append(f"{case} moved: declared {want}, measured {measured[case]}")
if empty_kept or empty_test:
    problems.append("an empty evidence block appeared; the history comment cannot say 0")
if problems:
    print("CHECK FAILED:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("CHECKS PASSED: 249 exam rows, 10 + 10 family rows, the other slices unchanged")

today = datetime.date.today().isoformat()
(p_hit, p_tot), (d_hit, d_tot) = measured[FAMILY[0]], measured[FAMILY[1]]
was_p, was_d = t.DECLARED[FAMILY[0]], t.DECLARED[FAMILY[1]]
new_block = f'''    # These rows are built from `stories.Story` objects, not from the catalog. An exam
    # story is never trained on (`stories.EXAM_KEYS` is held out of the training pool), so
    # a hit here is a read whose masked text a kept training row also prints: shared
    # wording, never a shared scenario.
    # {today} (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was {was_p}.
    "shared_origin_probe": ({p_hit}, {p_tot}),
    # Its healthy-origin twin, declared rather than left out on purpose: an undeclared
    # slice is not measured at all, so the guard's coverage would silently lag the exam.
    # {today} (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was {was_d}.
    "shared_origin_decoy_probe": ({d_hit}, {d_tot}),
'''
history_old = ("# still holds: 0 of 7164 kept rows and 0 of 249 test rows. "
               "Such a row would\n")
history_new = (
    "# still holds: 0 of 7164 kept rows and 0 of 249 test rows. The shared-origin\n"
    f"# family moved to real lines on {today} (Spec 4b-1), and it still holds: 0 of\n"
    f"# {len(kept)} kept rows and 0 of {len(test)} test rows. Such a row would\n")

src = open(TARGET).read()
first = "    # THIS ROW WAS THE POINT OF THE ALLOWLIST at 0/34"
last = '    "shared_origin_decoy_probe": (2, 34),\n'
assert src.count(first) == 1 and src.count(last) == 1 and src.count(history_old) == 1, \
    "a marker is missing or repeated; edit by hand"
a = src.index(first)
b = src.index(last) + len(last)
assert a < b
src = src[:a] + new_block + src[b:]
src = src.replace(history_old, history_new)
open(TARGET, "w").write(src)
print(f"wrote {TARGET}")
print(new_block)
EOF
```

It prints, in order: the row counts, a table of declared against measured for
all six entries (the two family rows are marked `<- family, moves` when they
differ), the first line of every family read that a kept training row also
prints, the check result, and finally the exact block it wrote. The block it
writes is:

```text
    # These rows are built from `stories.Story` objects, not from the catalog. An exam
    # story is never trained on (`stories.EXAM_KEYS` is held out of the training pool), so
    # a hit here is a read whose masked text a kept training row also prints: shared
    # wording, never a shared scenario.
    # <YYYY-MM-DD, the day this step runs> (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was (3, 34).
    "shared_origin_probe": (<hits>, <reads>),
    # Its healthy-origin twin, declared rather than left out on purpose: an undeclared
    # slice is not measured at all, so the guard's coverage would silently lag the exam.
    # <YYYY-MM-DD, the day this step runs> (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was (2, 34).
    "shared_origin_decoy_probe": (<hits>, <reads>),
```

It replaces the old comment that started `# THIS ROW WAS THE POINT OF THE
ALLOWLIST at 0/34` (the history of the 2026-09-19 pool merge, now stale
because those rows no longer exist). Read the printed reads before you go on.
A hit must be generic wording (an event such as `Normal Started kubelet`),
never a read that names an exam story's own cause. If one does, stop and
report it.

Run: `PYTEST tests/test_evidence_overlap.py`
Expected: PASS. All four tests pass and the allowlist test now agrees with the measured numbers. The three helper tests did not change.

- [ ] **Step B7: Run the four files together**

Run: `PYTEST tests/test_propagation.py tests/test_healthy_evidence.py tests/test_evidence_overlap.py tests/test_ruled_scenarios.py`
Expected: PASS. Nothing in these files needs a fresh `-update`, and none is allowed. The other old family files are other parts' work; do not touch them here.

- [ ] **Step B8: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_propagation.py tests/test_healthy_evidence.py \
       tests/test_evidence_overlap.py tests/test_ruled_scenarios.py \
  && COMMIT "test(shared-origin): rewrite the propagation, healthy-evidence, overlap and ruled tests"
```

#### Part C: the probes, the pairs, the decoy probe, keywords and decided rows

**Files:** Modify `tests/test_probe_cousins.py`, `tests/test_probe_wide.py`, `tests/test_shared_origin_keywords.py`, `tests/test_shared_origin_decided.py`, `tests/test_shared_origin_training_pair.py`, `tests/test_shared_origin_decoy_probe.py`.

What this part does, in plain words. Six old test files were written for the made-up
candidate menu and the invented origin read. After Task 7 they check things that no
longer exist. This part makes each of them check the new rows: real story worlds, a
`broken` and a `healthy` twin per story, and a gold answer that comes from the rules or
from a named anchor.

Rules this part follows:

- A test is deleted only if it checks the made-up menu, the 12 X stories, or the invented
  origin read (`origin_read_label`, `healthy_origin_content`). Everything else is
  rewritten or kept.
- A pair of twin rows is matched on `Example.group` (Ruling 32). The group names the
  victims only. The broken world can add an origin row that the healthy world does not
  have, so two twins can have different workload sets. They never have different victims.
- Two twins only have to differ in at least one printed line (Ruling 35). Nothing here
  asks for the same order of reads or the same menu.
- Labels are `shared` or `none` (Ruling 25). A test that needs "shared" picks a story and a
  width that earn it. It never assumes a label from the story's class alone.
- No bar and no test threshold moves. A pin is never edited to make a failing check pass.
  If a check in Step C2 or C9 fails, the implementer stops, commits nothing, and reports
  DONE_WITH_CONCERNS with the numbers.
- Task 8 owns `tests/test_shared_origin_floor.py`, `tests/test_shared_origin_pool.py` and
  parts of `tests/test_shared_origin_training.py`. This part does not open them. Test files
  cannot import each other (`tests/` has no `__init__.py`), so where a test here needs to
  score a reply it does so inline.
- The commit has no author trailer and no tool credit. Do not add one.

How the counts move, so the numbers below are not a surprise:

| What | Old | New | Why |
|---|---|---|---|
| Cousin probe pairs / rows | 54 / 108 | 41 / 82 | It draws from `stories.trainable()` (35 P, then 6 ruled R). |
| Wide probe rows | 60 | 60 | 6 exam stories x 5 pairs x 2. Unchanged. |
| Exam rows | 249 | 249 | Unchanged. Task 10 owns the hash pins. |
| Exam probe rows per half | 10 | 10 | 6 full width, then 4 width-2 rows for the exam stories with 3 or more victims. |

- [ ] **Step C1: Run the six old files against the new tree and record how they fail**

Do not edit anything. This step is only a record. It shows which old checks the new rows
broke, so the task report can say which tests were rewritten for a real reason.

Run: `PYTEST tests/test_probe_cousins.py tests/test_probe_wide.py tests/test_shared_origin_keywords.py tests/test_shared_origin_decided.py tests/test_shared_origin_training_pair.py tests/test_shared_origin_decoy_probe.py`

Expected: FAIL. Write down the exact failing test names. The predictions, from reading
the old code against the new modules, are:

- `test_probe_cousins.py`: `test_cousin_probe_counts_and_balance` (:21, 54 against 41),
  `test_cli_probe_cousins_writes_only_the_standalone_file` (:126, 108 against 82). The
  twin test (:45) and the 3-verdict test (:86) most likely fail too: `_pair_key` compares
  the sorted `expected` workloads, and the broken world can add an origin row; and a ruled
  story can have two victims.
- `test_probe_wide.py`: `test_wide_probe_counts_and_balance` (:19) passes only if the held-out
  set is still the six exam stories. The twin test (:40) most likely fails on `_pair_key`.
- `test_shared_origin_keywords.py`: all three pass. They read `propagation` data, which
  does not change. They are rewritten anyway, because they no longer check the rows the
  exam serves.
- `test_shared_origin_decided.py`: about 13 of 14 fail, mostly with `AttributeError`
  (`cases._shared_origin_row` and `cases._shared_origin_summary` are gone). Only
  `test_no_story_shared_cause_or_local_cause_holds_a_shared_claim_phrase` (:171) passes.
- `test_shared_origin_training_pair.py`: the story-count test (:138), the same-workloads
  test (:148), the answer-flip test (:180) and the denial test (:273) fail.
- `test_shared_origin_decoy_probe.py`: the menu test (:119), the distinct-causes test
  (:184), the separate-reasons test (:194), the `decoy_causes` test (:200), the tag test
  (:259) and both teeth tests (:317, :380) fail.

A test that passes here and is not in the prediction list is fine. A test that fails with
an error that is not in the prediction list (for example an `ImportError` from a module
Task 7 should have built) means an earlier task is not done. Stop and report
DONE_WITH_CONCERNS.

- [ ] **Step C2: Check the facts the new tests lean on, before writing them**

The new tests assume a handful of facts about the new rows. This script checks every one of
them on the real tree. Nothing is written. If it prints any `BAD` line, stop: do not write
the tests, do not loosen a check, commit nothing, and report DONE_WITH_CONCERNS with the
printed lines.

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
import json
import random
import re

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, generate, gold, stories
from kubeagent_verdict.dataset import shared_origin as so
from kubeagent_verdict.evals import score
from kubeagent_verdict.evals.score import INDEPENDENCE_PHRASES

bad = []


def need(ok, what):
    if not ok:
        bad.append(what)


def victim_keys(ex):
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


NONE = contract.NONE_OF_THESE
by_key = stories.by_key()
need(len(by_key) == 47, f"by_key has {len(by_key)}, expected 47")
need(len(stories.trainable()) == 41, f"trainable has {len(stories.trainable())}, expected 41")
need(len(stories.exam()) == 6, f"exam has {len(stories.exam())}, expected 6")

# 1. Every story, both worlds, width 2 and full width.
capped = 0
seen_gold = set()
for st in by_key.values():
    for w in sorted({2, len(st.victims)}):
        d = so.draw(st, random.Random(5), width=w)
        bb = so.build(st, d, world="broken")
        hb = so.build(st, d, world="healthy")
        bg, hg = gold.gold_for(bb), gold.gold_for(hb)
        tag = f"{st.key} w{w}"
        need(hg.label == "none", f"{tag}: healthy label is {hg.label}")
        for b, g in ((bb, bg), (hb, hg)):
            lines = g.summary.split("\n")
            need(1 <= len(lines) <= 4, f"{tag}: summary has {len(lines)} lines")
            need(score.job3(g.label, g.summary) == 1.0, f"{tag}: gold summary fails job3")
        confirmed = sum(1 for r in bb.rows if r.result.outcome == "confirmed")
        linked = sum(1 for r in bb.rows if r.role == "victim" and bg.rows[r.key].linked)
        if bg.label == "shared":
            seen_gold.add("broken-shared")
            need(confirmed >= 2 or (st.cls == "P" and linked >= 2), f"{tag}: shared not earned")
        else:
            seen_gold.add("broken-none")
            need(st.cls != "P" or linked < 2, f"{tag}: P story is none with linked={linked}")
        if st.cls == "R":
            need(bg.label == "shared", f"{tag}: R story is not shared when broken")
            need(all(r.result.decided and r.result.outcome == "confirmed"
                     for r in bb.rows if r.role == "victim"), f"{tag}: R victim not confirmed")
            need(not any(r.result.decided for r in hb.rows), f"{tag}: R row decided when healthy")
        if len(bb.rows) >= 4:
            capped += 1
            lines = gold._summary(bb, bg.rows, "none", len(bb.rows)).split("\n")
            need(len(lines) == 4 and
                 [ln.split(":")[0] for ln in lines[1:]] == [r.key for r in bb.rows[:3]],
                 f"{tag}: the cap of three rows does not hold")
need(seen_gold == {"broken-shared", "broken-none"}, f"labels seen {sorted(seen_gold)}")
need(capped > 0, "no build has 4 or more rows, so the cap check has nothing to look at")

# 2. No answer holds a shared-claim phrase.
for st in by_key.values():
    answers = [a for v in st.victims for a in (v.broken, v.healthy) if a is not None]
    answers += [wd.origin_row.answer for wd in (st.broken, st.healthy)
                if wd.origin_row is not None and wd.origin_row.answer is not None]
    for a in answers:
        low = a.cause.lower()
        for ph in cases.SHARED_CLAIM_PHRASES:
            need(ph not in low, f"{st.key}: answer {a.cause!r} holds {ph!r}")

# 3. The unverified twin.
st = by_key["node-not-ready"]
ub = so.build(st, so.draw(st, random.Random(11), width=len(st.victims)),
              world="broken", unverified=True)
need(all(r.result.outcome == "unverified" for r in ub.rows if r.role == "victim"),
     "node-not-ready unverified: a victim is not 'unverified'")
need(gold.gold_for(ub).label == "none", "node-not-ready unverified: label is not none")
try:
    cases.shared_origin(by_key["registry-unreachable"], random.Random(11), unverified=True)
    need(False, "registry-unreachable with unverified=True did not raise")
except ValueError as e:
    need("unverified" in str(e), f"registry-unreachable ValueError says {e}")

# 4. Pairs: the exam probes, the cousin probe and the wide probe.
cousin = generate.shared_origin_cousin_probes()
wide = generate.shared_origin_wide_probes()
need(len(cousin) == 82, f"cousin rows {len(cousin)}, expected 82")
need(len(wide) == 60, f"wide rows {len(wide)}, expected 60")
probes = generate.shared_origin_probes()
decoys = generate.shared_origin_decoy_probes()
need(len(probes) == len(decoys) == 10, f"exam probes {len(probes)}/{len(decoys)}, expected 10/10")
pairs = (list(zip(probes, decoys)) + list(zip(cousin[0::2], cousin[1::2]))
         + list(zip(wide[0::2], wide[1::2])))
shared_pairs = 0
r_shared_wide = 0
for p, d in pairs:
    tag = f"{p.meta['origin']} {p.group}"
    s = by_key[p.meta["origin"]]
    vk = victim_keys(p)
    need(p.group == d.group, f"{tag}: twins have different groups")
    need(vk <= set(p.meta["expected"]) and vk <= set(d.meta["expected"]),
         f"{tag}: a victim has no verdict")
    need(set(d.meta["expected"]) <= set(p.meta["expected"]),
         f"{tag}: the decoy flags a workload the probe does not")
    need(set(p.user.splitlines()) != set(d.user.splitlines()), f"{tag}: twins print the same lines")
    need(d.meta["label"] == "none", f"{tag}: decoy label is {d.meta['label']}")
    named = [c for c in d.meta["expected"].values() if c != NONE]
    need(len(named) == len(set(named)), f"{tag}: decoy named causes repeat")
    pat = re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(s.shown_cause)))
    need(not any(pat.fullmatch(c) for c in named), f"{tag}: a decoy cause is the shared cause")
    need(d.meta["decoy_causes"] == [], f"{tag}: decoy_causes is not []")
    need(set(d.meta["decoy_by_workload"]) <= set(d.meta["expected"]), f"{tag}: decoy_by_workload key")
    if s.cls == "R":
        need(p.meta["label"] == "shared", f"{tag}: R probe is not shared")
        need(all(p.meta["workloads"][w]["job"] == 1 for w in vk), f"{tag}: R victim not job 1")
        need({p.meta["expected"][w] for w in vk}.isdisjoint(set(d.meta["expected"].values())),
             f"{tag}: R victim cause appears in the decoy")
    if p.meta["label"] == "shared":
        shared_pairs += 1
        common = set(p.meta["expected"]) & set(d.meta["expected"])
        need(any(p.meta["expected"][w] != d.meta["expected"][w] for w in common),
             f"{tag}: no common workload flips")
for p, d in zip(wide[0::2], wide[1::2]):
    if by_key[p.meta["origin"]].cls == "R" and p.meta["label"] == "shared":
        r_shared_wide += 1
need(r_shared_wide >= 15, f"wide R probes that are shared: {r_shared_wide}, expected 15 or more")
need(shared_pairs > 0, "no pair is labelled shared")
ruled_shared = sum(1 for p, _d in zip(cousin[0::2], cousin[1::2])
                   if by_key[p.meta["origin"]].cls == "R" and p.meta["label"] == "shared")
need(ruled_shared >= len(stories.RULED_ORDER), f"cousin R shared {ruled_shared}, expected 6 or more")

# 5. Keywords: siblings and twins.
def keyed(ex):
    for w, m in ex.meta["workloads"].items():
        if m["job"] == 2 and m["expected_cause"] != NONE:
            yield w, m["expected_cause"], m["own_cause_keywords"]

sib = twin = 0
for ex in probes + decoys:
    k = list(keyed(ex))
    for w, cause, keys in k:
        need(1 <= len(keys) <= 3, f"{ex.group} {w}: {len(keys)} keywords")
        need(all(re.fullmatch(r"[a-z]{4,}", x) and x in cause.lower() for x in keys),
             f"{ex.group} {w}: a keyword is not inside its cause")
        need(score._keywords_match(cause, keys), f"{ex.group} {w}: keywords miss their own cause")
        for w2, cause2, _ in k:
            if w2 != w and cause2 != cause:
                sib += 1
                need(not score._keywords_match(cause2, keys), f"{ex.group} {w} matches {w2}")
for p, d in zip(probes, decoys):
    for a, b in ((p, d), (d, p)):
        for w, cause, keys in keyed(a):
            other = b.meta["expected"].get(w)
            if other is not None and other != cause:
                twin += 1
                need(not score._keywords_match(other, keys), f"{a.group} {w} matches its twin")
need(sib > 0 and twin > 0, f"discrimination looked at {sib} sibling and {twin} twin pairs")

# 6. The healthy summary header is earned in some decoys and not in others.
earned = unearned = 0
for _tag, ex in [("c", e) for e in cousin if e.case == "shared_origin_decoy_probe"] + \
        [("e", e) for e in decoys]:
    causes = list(ex.meta["expected"].values())
    head = json.loads(ex.assistant)["summary"].split("\n")[0]
    if NONE not in causes and len(set(causes)) == len(causes):
        earned += 1
        need(head == f"{len(causes)} workloads are failing for separate reasons.",
             f"{ex.group}: earned header missing: {head}")
    else:
        unearned += 1
        need(head == (f"{len(causes)} workloads are failing, and kubeagent's rules did not "
                      "confirm one cause on two or more of them."),
             f"{ex.group}: unearned header wrong: {head}")
need(earned > 0 and unearned > 0, f"earned {earned}, unearned {unearned}: both must be above 0")

# 7. node-not-ready's decided cause.
st = by_key["node-not-ready"]
ex = cases.shared_origin_probe(st, generate._entry_rng("t", st.key))
causes = {v["cause"] for v in json.loads(ex.assistant)["verdicts"]}
need(len(causes) == 1, f"node-not-ready has {len(causes)} causes")
only = next(iter(causes))
need(only.startswith("node "), f"node-not-ready cause is {only!r}")
need(ex.meta["scope_value"] in only, "scope_value is not in the cause")
d7 = so.draw(st, generate._entry_rng("t", st.key), width=len(st.victims))
need(only != so._sub(st.shown_cause, None, d7), "the rule cause equals the story's shown cause")

# 8. The training pair: size 800, seed 17.
rows17 = generate.generate(seed=17, size=800)
sh = [e for e in rows17 if e.case == "shared_origin"]
dc = [e for e in rows17 if e.case == "shared_origin_decoy"]
need(sh and len(sh) == len(dc), f"training halves {len(sh)}/{len(dc)}")
need(all(a.group == b.group and a.meta["origin"] == b.meta["origin"] for a, b in zip(sh, dc)),
     "training twins are out of step")
need({e.meta["origin"] for e in sh} == {st.key for st in stories.trainable()},
     "training origins are not the trainable stories")
train, val = generate.split(rows17, seed=17)
test = generate.test_set()
kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
head_sep = re.compile(r"^\d+ workloads are failing for separate reasons\.")
fam = [e for e in kept if e.case in ("shared_origin", "shared_origin_decoy")]
earned_ids = {id(e) for e in fam if head_sep.match(json.loads(e.assistant)["summary"])}
deny_ids = {id(e) for e in fam
            if any(p in str(json.loads(e.assistant)["summary"]).lower() for p in INDEPENDENCE_PHRASES)}
need(earned_ids and deny_ids == earned_ids,
     f"family rows that deny {len(deny_ids)} against earned headers {len(earned_ids)}")
for e in fam:
    if e.meta["label"] == "none":
        for v in json.loads(e.assistant)["verdicts"]:
            low = v["cause"].lower()
            for ph in cases.SHARED_CLAIM_PHRASES:
                need(ph not in low, f"{e.group}: none-labelled cause {v['cause']!r} holds {ph!r}")

print("pairs checked:", len(pairs), "| shared pairs:", shared_pairs, "| capped builds:", capped)
print("earned headers:", earned, "| unearned:", unearned)
print("training family rows kept:", len(fam), "| earned among them:", len(earned_ids))
for line in bad[:40]:
    print("BAD", line)
print("violations:", len(bad))
raise SystemExit(1 if bad else 0)
EOF
```

Expected: exit 0, `violations: 0`, and every count above 0. If it exits 1, stop (see the top of
this step).

- [ ] **Step C3: Rewrite `tests/test_probe_cousins.py`**

The file keeps four tests as they are: `test_cousin_probe_is_deterministic` (:95),
`test_cousin_probe_is_not_in_the_exam` (:101), `test_cli_probe_cousins_writes_only_the_standalone_file`
(:126, edited in this step) and `test_cli_rejects_both_probe_flags_together` (:143).
Everything above `def test_cousin_probe_is_deterministic():` is replaced.

REWRITE (4 tests): `test_cousin_probe_counts_and_balance` (:21),
`test_cousin_probe_uses_only_trainable_origins` (:36),
`test_cousin_rows_are_adjacent_twins_with_unique_pair_keys` (:45, renamed
`test_cousin_rows_are_adjacent_twins_with_unique_groups`),
`test_every_cousin_decoy_carries_three_or_more_verdicts` (:86, renamed
`test_every_cousin_decoy_carries_a_verdict_for_every_victim`).

KEEP: `test_cousin_probe_is_deterministic` (:95), `test_cousin_probe_is_not_in_the_exam` (:101),
`test_cli_rejects_both_probe_flags_together` (:143).

RE-PIN: `test_cli_probe_cousins_writes_only_the_standalone_file` (:126), 108 to 82.

Open `tests/test_probe_cousins.py`. Delete everything from line 1 down to, and not
including, the line `def test_cousin_probe_is_deterministic():`. Put this block at the top:

```python
"""The cousin probe: one fresh twin pair per trainable story.

The wide probe (tests/test_probe_wide.py) asks the six held-out stories five
times each. This probe asks each trained story once: 41 stories, so 41 pairs
and 82 rows. (It was 54 pairs and 108 rows on the old made-up menu.) Every
pair is at full width.

A pair is one story told in two worlds. In the broken world the origin is
broken. In the healthy world it is not. Both halves carry the same
`Example.group`, and their printed lines differ. The probe is in-distribution
on purpose. A model that reads the origin on the stories it studied and still
fails the exam has a coverage problem. One that fails here has a recipe
problem. It is written to its own file, scored on its own, and decides
nothing. The frozen exam does not move.
"""

from kubeagent_verdict.dataset import generate, stories


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group.

    A group is `propagation:<story>:<ns>/<name>` for each victim, joined by
    `+`. It names victims only, and it is the same in both worlds. The broken
    world can add an origin row to `expected`. The group never lists it.
    """
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def test_cousin_probe_counts_and_balance():
    rows = generate.shared_origin_cousin_probes()
    trainable = {st.key for st in stories.trainable()}
    # 2026-10-03 (Spec 4b-1): the probe draws from stories.trainable(), 41 stories
    # (35 plain, 6 ruled), one pair each; was 54 stories and 108 rows.
    assert len(trainable) == 41
    assert len(rows) == len(trainable) * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == trainable
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 1, origin
        assert case_list.count("shared_origin_decoy_probe") == 1, origin


def test_cousin_probe_uses_only_trainable_origins():
    # The mirror of the wide probe's leak guard. This probe is the
    # in-distribution check, so an exam story or a dropped story here would
    # score the exam twice and tell us nothing new.
    kept_out = set(stories.EXAM_KEYS) | set(stories.DROPPED)
    for ex in generate.shared_origin_cousin_probes():
        assert ex.meta["origin"] not in kept_out, ex.meta["origin"]


def test_cousin_rows_are_adjacent_twins_with_unique_groups():
    """Twins are matched on `Example.group`, not on the workload set.

    The broken world can add an origin row that the healthy world lacks, so
    the two halves may flag different workloads. They never name different
    victims. Two things are checked per pair. The halves print different lines
    (otherwise the pair asks nothing). And on a `shared` probe at least one
    workload both halves flag gets a different cause, so the answer really
    flips with the read.

    A ruled (R) story is checked harder. Its probe is `shared`, every victim
    is decided by the rules (job 1), and the victims' causes appear nowhere
    in the decoy's answer. A plain (P) story is `shared` only when two or
    more victims are linked, so a P pair may be `none` on both halves. Only
    the decoy half is always `none`.
    """
    rows = generate.shared_origin_cousin_probes()
    by_key = stories.by_key()
    seen: set[str] = set()
    saw_shared = 0
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        origin = probe.meta["origin"]
        assert origin == decoy.meta["origin"]
        assert probe.group == decoy.group, origin
        # A repeated group would merge two pairs in the paired scoring.
        assert probe.group not in seen, origin
        seen.add(probe.group)
        victims = _victim_keys(probe)
        assert victims <= set(probe.meta["expected"]), origin
        assert victims <= set(decoy.meta["expected"]), origin
        # The reads must differ, or the pair asks nothing.
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), origin
        assert decoy.meta["label"] == "none", origin
        if by_key[origin].cls == "R":
            assert probe.meta["label"] == "shared", origin
            for w in victims:
                assert probe.meta["workloads"][w]["job"] == 1, (origin, w)
            probe_causes = {probe.meta["expected"][w] for w in victims}
            assert probe_causes.isdisjoint(set(decoy.meta["expected"].values())), origin
        if probe.meta["label"] == "shared":
            saw_shared += 1
            common = set(probe.meta["expected"]) & set(decoy.meta["expected"])
            assert any(probe.meta["expected"][w] != decoy.meta["expected"][w]
                       for w in common), origin
    # The six ruled stories are always shared. If fewer than six pairs are,
    # the ruled stories have fallen out of `stories.trainable()`.
    assert saw_shared >= len(stories.RULED_ORDER), saw_shared


def test_every_cousin_decoy_carries_a_verdict_for_every_victim():
    # Full width on purpose. A ruled story can have only two victims, so the
    # old claim "three or more verdicts everywhere" is gone. What still holds
    # is that every drawn victim gets its own verdict, and that some decoys are
    # wide enough to carry three (the shape the 0907 model broke its JSON on).
    by_key = stories.by_key()
    wide = 0
    for ex in generate.shared_origin_cousin_probes():
        if ex.case != "shared_origin_decoy_probe":
            continue
        story = by_key[ex.meta["origin"]]
        assert len(_victim_keys(ex)) == len(story.victims), story.key
        assert len(ex.meta["expected"]) >= len(story.victims), story.key
        if len(ex.meta["expected"]) >= 3:
            wide += 1
    assert wide > 0


```

Then, in the same file, replace the two lines in `test_cli_probe_cousins_writes_only_the_standalone_file`

```python
    # Re-measured 2026-09-19 (Task 9's pool merge, spec section 6): 96 to 108.
    assert len(lines) == 108
```

with

```python
    # 2026-10-03 (Spec 4b-1): the cousin probe draws from stories.trainable(),
    # 41 stories, one pair each; was 108.
    assert len(lines) == 82
```

Check the file shape:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -n '^def test_\|^def _' tests/test_probe_cousins.py
```

Expected: exactly `_victim_keys`, `test_cousin_probe_counts_and_balance`,
`test_cousin_probe_uses_only_trainable_origins`, `test_cousin_rows_are_adjacent_twins_with_unique_groups`,
`test_every_cousin_decoy_carries_a_verdict_for_every_victim`, `test_cousin_probe_is_deterministic`,
`test_cousin_probe_is_not_in_the_exam`, `test_cli_probe_cousins_writes_only_the_standalone_file`,
`test_cli_rejects_both_probe_flags_together`.

Run: `PYTEST tests/test_probe_cousins.py`
Expected: PASS (8 tests).

- [ ] **Step C4: Rewrite `tests/test_probe_wide.py`**

REWRITE (3 tests): `test_wide_probe_counts_and_balance` (:19),
`test_wide_probe_uses_no_trainable_origin` (:32),
`test_wide_rows_are_adjacent_twins_with_unique_pair_keys` (:40, renamed
`test_wide_rows_are_adjacent_twins_with_unique_groups`).

NEW (1 test): `test_wide_probe_widths_follow_the_story`. The wide probe is the only place the
exam stories are drawn at both widths five times each. A broken width rule would not show up
anywhere else.

KEEP: `test_wide_probe_is_deterministic` (:78), `test_cli_probe_wide_writes_only_the_standalone_file`
(:84, still asserts 60).

Open `tests/test_probe_wide.py`. Delete everything from line 1 down to, and not including,
the line `def test_wide_probe_is_deterministic():`. Put this block at the top:

```python
"""The widened shared-origin probe: a diagnostic file, not a release decider.

The frozen exam asks the shared-origin question with ten twin pairs spread over
six stories. That is enough to score a model, but not enough to diagnose one:
"it always fails on CoreDNS" resting on two pairs could be a coin landing badly
twice. The wide probe mints five twin pairs per exam story (30 pairs, 60 rows)
so a per-story verdict rests on five observations. Odd-numbered draws of a
story with three or more victims are narrowed to two, so each story is seen at
more than one width. It is written to its own file and scored on its own. The
frozen 249-row exam does not move.

Twins are matched on `Example.group`. The group names the victims, and it is
the same in both worlds. The broken world can add an origin row that the
healthy world lacks, so the two halves may flag different workloads.
"""

from kubeagent_verdict.dataset import generate, stories


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def test_wide_probe_counts_and_balance():
    rows = generate.shared_origin_wide_probes()
    exam_keys = {st.key for st in stories.exam()}
    assert len(exam_keys) == 6
    assert len(rows) == len(exam_keys) * 5 * 2
    per: dict[str, list[str]] = {}
    for ex in rows:
        per.setdefault(ex.meta["origin"], []).append(ex.case)
    assert set(per) == exam_keys
    for origin, case_list in per.items():
        assert case_list.count("shared_origin_probe") == 5, origin
        assert case_list.count("shared_origin_decoy_probe") == 5, origin


def test_wide_probe_uses_no_trainable_origin():
    # The leak guard: a trainable story in the probe would score the model on
    # stories it memorised during training. A dropped story would be a story
    # no part of the pipeline builds any more.
    barred = {st.key for st in stories.trainable()} | set(stories.DROPPED)
    for ex in generate.shared_origin_wide_probes():
        assert ex.meta["origin"] not in barred, ex.meta["origin"]


def test_wide_rows_are_adjacent_twins_with_unique_groups():
    """Twins are matched on `Example.group`, and the halves must print
    different lines (Ruling 35).

    A ruled (R) exam story is `shared` on its probe half at every width: the
    rules confirm one cause on its victims. Every victim is job 1, and the
    victims' causes appear nowhere in the decoy's answer. There are three R
    exam stories (node-not-ready, storage-provisioner-down,
    registry-unreachable) and five probes of each, so at least fifteen probes
    are `shared`. A plain (P) story is `shared` only when two or more victims
    are linked, so a P pair may be `none` on both halves. The decoy half is
    always `none`.
    """
    rows = generate.shared_origin_wide_probes()
    by_key = stories.by_key()
    seen: set[str] = set()
    shared_n = 0
    assert len(rows) % 2 == 0
    for probe, decoy in zip(rows[0::2], rows[1::2]):
        assert probe.case == "shared_origin_probe"
        assert decoy.case == "shared_origin_decoy_probe"
        origin = probe.meta["origin"]
        assert origin == decoy.meta["origin"]
        assert probe.group == decoy.group, origin
        # A repeated group would merge two pairs in the paired scoring.
        assert probe.group not in seen, origin
        seen.add(probe.group)
        victims = _victim_keys(probe)
        assert victims <= set(probe.meta["expected"]), origin
        assert victims <= set(decoy.meta["expected"]), origin
        assert set(probe.user.splitlines()) != set(decoy.user.splitlines()), origin
        assert decoy.meta["label"] == "none", origin
        if by_key[origin].cls == "R":
            assert probe.meta["label"] == "shared", origin
            for w in victims:
                assert probe.meta["workloads"][w]["job"] == 1, (origin, w)
            probe_causes = {probe.meta["expected"][w] for w in victims}
            assert probe_causes.isdisjoint(set(decoy.meta["expected"].values())), origin
        if probe.meta["label"] == "shared":
            shared_n += 1
            common = set(probe.meta["expected"]) & set(decoy.meta["expected"])
            assert any(probe.meta["expected"][w] != decoy.meta["expected"][w]
                       for w in common), origin
    r_exam = [st for st in stories.exam() if st.cls == "R"]
    assert len(r_exam) == 3
    assert shared_n >= 5 * len(r_exam), shared_n


def test_wide_probe_widths_follow_the_story():
    """Draw i of a story is narrowed to two victims when i is odd and the story
    has three or more. Every other draw is full width."""
    rows = generate.shared_origin_wide_probes()
    probes = rows[0::2]
    order = [st for st in stories.exam() for _ in range(5)]
    assert [ex.meta["origin"] for ex in probes] == [st.key for st in order]
    for flat, (st, ex) in enumerate(zip(order, probes)):
        i = flat % 5
        want = 2 if i % 2 == 1 and len(st.victims) >= 3 else len(st.victims)
        assert len(_victim_keys(ex)) == want, (st.key, i)


```

Check the file shape:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -n '^def test_\|^def _' tests/test_probe_wide.py
```

Expected: `_victim_keys`, then `test_wide_probe_counts_and_balance`, `test_wide_probe_uses_no_trainable_origin`,
`test_wide_rows_are_adjacent_twins_with_unique_groups`, `test_wide_probe_widths_follow_the_story`,
`test_wide_probe_is_deterministic`, `test_cli_probe_wide_writes_only_the_standalone_file`.

Run: `PYTEST tests/test_probe_wide.py`
Expected: PASS (6 tests).

- [ ] **Step C5: Rewrite `tests/test_shared_origin_keywords.py`**

All three old tests read `propagation` data. That data does not change, so they pass today,
but they no longer check what the exam serves. The exam's 20 shared-origin rows now carry
keywords from the rows' own gold (`gold.RowGold.keys`, 1 to 3 words, each inside its cause).
The three tests keep their three properties and move to those rows.

REWRITE (3 tests):
- `test_every_eval_scenario_and_victim_carries_a_keyword_pair` (:26), now
  `test_every_named_job2_workload_carries_one_to_three_keywords`. A keyword set is no longer
  a pair, and a rules-decided or `none_of_these` workload has none.
- `test_every_eval_keyword_appears_in_its_own_cause` (:33), now
  `test_every_exam_keyword_appears_in_its_own_cause`. It also checks the grader accepts the
  gold cause with its own keywords.
- `test_every_eval_keyword_pair_discriminates_on_its_own_menu` (:46), now
  `test_every_exam_keyword_set_discriminates`. There is no menu any more. The two legs are
  the siblings in the same row and the same workload in the other world.

NEW (1 test): `test_the_exam_keyword_count_is_pinned`. Its number is only known after the
rows are built. It ships with a starting literal and Step C9 measures it.

Replace the whole file with:

```python
"""The exam's job-2 grading keywords, on the rebuilt shared-origin rows.

Job 2 grades a named cause by keywords. Three properties, and the second and
third are the ones that matter:

- COVERAGE: every named job-2 workload in the 20 shared-origin exam rows has
  one to three keywords. Every other workload (decided by the rules, or
  `none_of_these`) has none. A named workload with no keywords could score
  0.0 whatever the model answered. That is a defect in the data, not a
  failure of the model.
- SELF-CONTAINMENT: each keyword is a lowercase word of four letters or more
  and sits inside its own cause. A typo here would make the workload
  unanswerable.
- DISCRIMINATION: a keyword set must not match any other cause the same row
  asks about. Two legs. The sibling leg: a workload's keywords do not match
  a different cause on another workload in the same row. The twin leg: they do
  not match the same workload's answer in the other world, including
  `none_of_these`. A set that cannot tell the two worlds apart grades both
  worlds the same.
"""
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import generate
from kubeagent_verdict.evals import score

# 2026-10-03 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 18.
EXAM_KEYWORDED = 12


@pytest.fixture(scope="module")
def probes():
    return generate.shared_origin_probes()


@pytest.fixture(scope="module")
def decoys():
    return generate.shared_origin_decoy_probes()


def _keyed(ex):
    """Yield (workload, cause, keywords) for each named job-2 workload."""
    for workload, m in ex.meta["workloads"].items():
        cause = m["expected_cause"]
        if m["job"] == 2 and cause != contract.NONE_OF_THESE:
            yield workload, cause, m["own_cause_keywords"]


def test_every_named_job2_workload_carries_one_to_three_keywords(probes, decoys):
    named = 0
    for ex in probes + decoys:
        for workload, m in ex.meta["workloads"].items():
            keys = m["own_cause_keywords"]
            if m["job"] == 2 and m["expected_cause"] != contract.NONE_OF_THESE:
                named += 1
                assert 1 <= len(keys) <= 3, (ex.group, workload, keys)
            else:
                assert keys == [], (ex.group, workload, keys)
    assert named > 0


def test_every_exam_keyword_appears_in_its_own_cause(probes, decoys):
    checked = 0
    for ex in probes + decoys:
        for workload, cause, keys in _keyed(ex):
            checked += 1
            for k in keys:
                assert re.fullmatch(r"[a-z]{4,}", k), (ex.group, workload, k)
                assert k in cause.lower(), (ex.group, workload, k, cause)
            assert score._keywords_match(cause, keys), (ex.group, workload)
    assert checked > 0


def test_every_exam_keyword_set_discriminates(probes, decoys):
    siblings = 0
    for ex in probes + decoys:
        named = list(_keyed(ex))
        for workload, cause, keys in named:
            for other, other_cause, _ in named:
                if other == workload or other_cause == cause:
                    continue
                siblings += 1
                assert not score._keywords_match(other_cause, keys), (
                    ex.group, workload, other)
    assert siblings > 0

    twins = 0
    for probe, decoy in zip(probes, decoys):
        for here, there in ((probe, decoy), (decoy, probe)):
            for workload, cause, keys in _keyed(here):
                other_cause = there.meta["expected"].get(workload)
                if other_cause is None or other_cause == cause:
                    continue
                twins += 1
                assert not score._keywords_match(other_cause, keys), (
                    here.group, workload, other_cause)
    assert twins > 0


def test_the_exam_keyword_count_is_pinned(probes, decoys):
    keyed = sum(len(list(_keyed(ex))) for ex in probes + decoys)
    # The pin guards the story data. A story edit that adds or drops a named
    # job-2 workload on the exam moves this number on purpose.
    assert keyed == EXAM_KEYWORDED
```

Run: `PYTEST tests/test_shared_origin_keywords.py`
Expected: 3 PASS. `test_the_exam_keyword_count_is_pinned` FAILS with `assert N == 12`. The 12 is
a starting value. Step C9 measures N and writes it in. Do not touch the 12 before then.

- [ ] **Step C6: Rewrite `tests/test_shared_origin_decided.py`**

The old file unit-tested two helpers that no longer exist (`cases._shared_origin_row` and
`cases._shared_origin_summary`), with hand-made `rules.Result` values. Its build-level tests
walked `propagation`. The new file tests the same ideas on real rows:

- A row the rules decide gets the rules' cause and rationale (job 1).
- A row they do not decide is named from its own lines or `none_of_these` (job 2).
- The summary follows the label: three lines when shared, a header and up to three row
  lines when not.

REWRITE (11 tests). Old name, then new name:
- `test_decided_confirmed_row_gets_the_rules_cause_and_rationale` (:57) and
  `test_decided_unverified_row_also_gets_the_rules_cause_and_rationale` (:69) become
  `test_a_confirmed_row_gets_the_rules_cause_and_rationale` and
  `test_an_unverified_row_is_decided_and_the_label_is_none`.
- `test_shared_label_keeps_todays_three_lines` (:113) becomes `test_a_shared_summary_is_three_lines`.
- `test_none_label_healthy_twin_all_different_says_separate_reasons` (:122) and
  `test_none_label_healthy_twin_with_a_repeated_cause_uses_the_other_branch` (:142) fold into
  `test_a_healthy_summary_says_separate_reasons_only_when_the_rows_earn_it`.
- `test_none_label_broken_says_rules_did_not_confirm_one_cause` (:131) becomes
  `test_a_broken_none_summary_says_the_rules_did_not_confirm_one_cause`.
- `test_separate_label_raises` (:153) becomes `test_the_family_never_carries_the_label_separate`.
- `test_summary_lines_cap_at_three_rows` (:160) becomes `test_a_summary_lists_at_most_three_rows`.
- `test_no_story_shared_cause_or_local_cause_holds_a_shared_claim_phrase` (:171) becomes
  `test_no_story_answer_holds_a_shared_claim_phrase`. The old test also checked `shared_cause`.
  That string now lives in the shared summary only, next to the claim it belongs to, so the
  check moves to the answers a `none` summary can print.
- `test_a_shared_label_only_comes_from_an_origin_object` (:185) becomes `test_a_shared_label_is_earned`.
- `test_exactly_three_of_six_shared_origin_probe_stories_are_shared` (:210) becomes
  `test_the_exam_probe_labels_are_pinned`.
- `test_a_decided_shared_origin_probe_workload_carries_the_rules_cause` (:231) keeps its name.

DELETE (2 tests):
- `test_undecided_broken_row_keeps_the_shared_cause` (:81). It checks the made-up fallback of the
  deleted `_shared_origin_row`: an undecided broken row took the story's shared cause. The new
  rows have no such fallback. An undecided row is `named` (it needs its anchor line) or
  `none_of_these`. Task 4's `test_named_needs_its_anchor_and_none_otherwise` covers that, and
  `test_the_job_split_follows_the_rules_decision` below covers the meta side.
- `test_undecided_healthy_row_keeps_the_decoy_cause` (:93). Same reason, for the decoy cause.

NEW (2 tests): `test_every_r_story_is_shared_in_the_broken_world_at_every_width` (Task 5 covers
full width only) and `test_the_job_split_follows_the_rules_decision`.

Replace the whole file with:

```python
"""The shared-origin family's decided rows and its label-driven summary.

A row the rules decide (job 1) takes its cause and rationale from the rules.
A row they do not decide (job 2) is `named` from its own lines, or it is
`none_of_these`. The label is `shared` or `none`. Nothing in this family is
ever labelled `separate`.

The summary follows the label. A `shared` row gets three lines: the count and
the origin, the root cause, and the remedy. A `none` row gets a header and then
one line per row, at most three. The header says "failing for separate
reasons" only in a healthy world where every row has its own, different cause
(a named cause or a rules-decided one). Anywhere else it says the rules did not
confirm one cause, because anything stronger would claim more than the rows show.
"""

from __future__ import annotations

import json
import random
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, generate, gold, render, stories
from kubeagent_verdict.dataset import shared_origin as so

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")
_ROW_LINE = re.compile(r"^[^\s:]+/[^\s:]+: ")


def _verdicts(ex) -> dict[str, dict]:
    return {v["workload"]: v for v in json.loads(ex.assistant)["verdicts"]}


def _summary(ex) -> str:
    return json.loads(ex.assistant)["summary"]


def _built(key, world, width=None, **kw):
    st = stories.by_key()[key]
    d = so.draw(st, random.Random(11), width=width or len(st.victims))
    return so.build(st, d, world=world, **kw)


def _answers(st):
    """Every `Answer` a story can print: victims in both worlds, then origin rows."""
    for v in st.victims:
        for a in (v.broken, v.healthy):
            if a is not None:
                yield a
    for w in (st.broken, st.healthy):
        if w.origin_row is not None and w.origin_row.answer is not None:
            yield w.origin_row.answer


@pytest.fixture(scope="module")
def fam():
    """The exam probes, the exam decoy probes and the cousin probes."""
    rows = (generate.shared_origin_probes()
            + generate.shared_origin_decoy_probes()
            + generate.shared_origin_cousin_probes())
    narrow = sum(1 for st in stories.exam() if len(st.victims) >= 3)
    assert len(rows) == 2 * (len(stories.EXAM_KEYS) + narrow) + 2 * len(stories.trainable())
    return rows


# ------------------------------------------------------- decided rows


def test_a_confirmed_row_gets_the_rules_cause_and_rationale():
    b = _built("node-not-ready", "broken")
    g = gold.gold_for(b)
    victims = [r for r in b.rows if r.role == "victim"]
    assert victims
    for row in victims:
        res = row.result
        assert res.decided and res.outcome == "confirmed", row.key
        rg = g.rows[row.key]
        assert rg.verdict == "decided", row.key
        assert rg.cause == res.cause, row.key
        assert rg.rationale == render.rule_rationale(res), row.key
        assert rg.keys == (), row.key

    # The same draw, rendered as an example: the reply and the meta agree.
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_probe(st, random.Random(11))
    verdicts = _verdicts(ex)
    assert {r.key for r in victims} <= set(verdicts)
    for row in victims:
        assert verdicts[row.key]["cause"] == row.result.cause
        assert verdicts[row.key]["rationale"] == render.rule_rationale(row.result)
        m = ex.meta["workloads"][row.key]
        assert m["job"] == 1 and m["decided"], row.key
        assert m["decided_cause"] == row.result.cause, row.key
        assert m["decided_outcome"] == "confirmed", row.key
        assert m["own_cause_keywords"] == [], row.key


def test_an_unverified_row_is_decided_and_the_label_is_none():
    """A refused node read still decides (job 1, outcome "unverified"), but it
    confirms nothing, so the rules do not call the cause shared (Ruling 31)."""
    st = stories.by_key()["node-not-ready"]
    b = _built("node-not-ready", "broken", unverified=True)
    victims = [r for r in b.rows if r.role == "victim"]
    assert victims
    assert all(r.result.decided and r.result.outcome == "unverified" for r in victims)
    g = gold.gold_for(b)
    assert g.label == "none"
    header = (f"{len(b.rows)} workloads are failing, and kubeagent's rules did not "
              "confirm one cause on two or more of them.")
    assert g.summary.split("\n")[0] == header

    ex = cases.shared_origin(st, random.Random(11), unverified=True)
    assert ex.meta["label"] == "none"
    for row in victims:
        m = ex.meta["workloads"][row.key]
        assert m["job"] == 1 and m["decided_outcome"] == "unverified", row.key
    assert _summary(ex).split("\n")[0] == header

    # A story with no down node has nothing to refuse, so it cannot be unverified.
    with pytest.raises(ValueError, match="unverified"):
        cases.shared_origin(stories.by_key()["registry-unreachable"],
                            random.Random(11), unverified=True)


# ---------------------------------------------------------- summaries


def test_a_shared_summary_is_three_lines(fam):
    seen = 0
    for ex in fam:
        if ex.meta["label"] != "shared":
            continue
        seen += 1
        lines = _summary(ex).split("\n")
        assert len(lines) == 3, (ex.case, ex.group)
        assert _SHARED_HEAD.match(lines[0]), lines[0]
        assert lines[1].startswith("Root cause: "), lines[1]
        n = int(lines[0].split(" ", 1)[0])
        assert 2 <= n <= len(ex.meta["expected"]), (ex.group, n)
        assert lines[2].strip(), (ex.group, "empty remedy line")
    assert seen > 0


def test_a_healthy_summary_says_separate_reasons_only_when_the_rows_earn_it(fam):
    """Earned means: no row is `none_of_these`, and no two rows share a cause."""
    earned = unearned = 0
    for ex in fam:
        if ex.case != "shared_origin_decoy_probe":
            continue
        causes = list(ex.meta["expected"].values())
        n = len(causes)
        head = _summary(ex).split("\n")[0]
        if contract.NONE_OF_THESE not in causes and len(set(causes)) == n:
            earned += 1
            assert head == f"{n} workloads are failing for separate reasons.", ex.group
        else:
            unearned += 1
            assert head == (f"{n} workloads are failing, and kubeagent's rules did not "
                            "confirm one cause on two or more of them."), ex.group
    assert earned > 0 and unearned > 0, (earned, unearned)


def test_a_broken_none_summary_says_the_rules_did_not_confirm_one_cause(fam):
    seen = 0
    for ex in fam:
        if ex.case != "shared_origin_probe" or ex.meta["label"] != "none":
            continue
        seen += 1
        n = len(ex.meta["expected"])
        lines = _summary(ex).split("\n")
        assert lines[0] == (f"{n} workloads are failing, and kubeagent's rules did not "
                            "confirm one cause on two or more of them."), ex.group
        assert 3 <= len(lines) <= 4, (ex.group, len(lines))
        # Header, then one line per row. There is no remedy line on a `none` row.
        for ln in lines[1:]:
            assert _ROW_LINE.match(ln), (ex.group, ln)
    assert seen > 0


def test_the_family_never_carries_the_label_separate(fam):
    # Ruling 25: the rules' "separate" maps to "none". The word survives only
    # in a summary header, and only when a healthy world earns it.
    assert {ex.meta["label"] for ex in fam} == {"shared", "none"}


def test_a_summary_lists_at_most_three_rows(fam):
    for ex in fam:
        if ex.meta["label"] == "shared":
            continue
        n = len(ex.meta["expected"])
        assert len(_summary(ex).split("\n")) == 1 + min(3, n), ex.group

    # The loop above only reaches a fourth row if some example has one. Force
    # it: build every story in both worlds, and cap the ones with four rows.
    capped = 0
    for st in stories.by_key().values():
        for world in ("broken", "healthy"):
            b = _built(st.key, world)
            if len(b.rows) < 4:
                continue
            capped += 1
            g = gold.gold_for(b)
            lines = gold._summary(b, g.rows, "none", len(b.rows)).split("\n")
            assert len(lines) == 4, (st.key, world)
            assert [ln.split(":")[0] for ln in lines[1:]] == [r.key for r in b.rows[:3]]
    assert capped > 0


def test_no_story_answer_holds_a_shared_claim_phrase():
    """A cause with a shared-claim phrase would make job 3 read a `none` row's
    per-workload line as a claim and fail it. The shared summary is exempt: it
    carries the claim on purpose, and it is built from the story's shown text,
    not from an answer."""
    checked = 0
    for st in stories.by_key().values():
        for a in _answers(st):
            checked += 1
            low = a.cause.lower()
            for ph in cases.SHARED_CLAIM_PHRASES:
                assert ph not in low, (st.key, ph, a.cause)
    assert checked > 0


# ------------------------------------------------------------ labels


def test_a_shared_label_is_earned():
    """`shared` needs two confirmed rows, or (for a plain story) two linked
    victims. A healthy world is never `shared`. Every story at its narrowest
    and widest width, so the width rule is exercised too."""
    seen: set[str] = set()
    for st in stories.by_key().values():
        for width in sorted({2, len(st.victims)}):
            for world in ("broken", "healthy"):
                d = so.draw(st, random.Random(5), width=width)
                b = so.build(st, d, world=world)
                g = gold.gold_for(b)
                confirmed = sum(1 for r in b.rows if r.result.outcome == "confirmed")
                linked = sum(1 for r in b.rows
                             if r.role == "victim" and g.rows[r.key].linked)
                tag = (st.key, width, world)
                if world == "healthy":
                    assert g.label == "none", tag
                    seen.add("healthy-none")
                elif g.label == "shared":
                    assert confirmed >= 2 or (st.cls == "P" and linked >= 2), tag
                    seen.add("broken-shared")
                else:
                    if st.cls == "P":
                        assert linked < 2, tag
                    seen.add("broken-none")
    assert seen == {"healthy-none", "broken-shared", "broken-none"}


def test_every_r_story_is_shared_in_the_broken_world_at_every_width():
    """Task 5 checks full width. This checks the narrow width as well, because
    the wide probe and the training loop draw ruled stories at width 2."""
    checked = 0
    for st in stories.by_key().values():
        if st.cls != "R":
            continue
        for width in sorted({2, len(st.victims)}):
            d = so.draw(st, random.Random(5), width=width)
            broken = so.build(st, d, world="broken")
            healthy = so.build(st, d, world="healthy")
            tag = (st.key, width)
            assert gold.gold_for(broken).label == "shared", tag
            for r in broken.rows:
                if r.role == "victim":
                    assert r.result.decided and r.result.outcome == "confirmed", (tag, r.key)
            assert gold.gold_for(healthy).label == "none", tag
            assert not any(r.result.decided for r in healthy.rows), tag
            checked += 1
    assert checked >= sum(1 for st in stories.by_key().values() if st.cls == "R")


# 2026-10-03 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
# was ['none', 'shared', 'shared', 'shared', 'none', 'none', 'none', 'shared', 'shared', 'none'].
EXAM_PROBE_LABELS = ["shared", "shared", "shared", "shared", "none",
                     "shared", "none", "shared", "shared", "none"]


def test_the_exam_probe_labels_are_pinned():
    """Six full-width probes in exam order, then the width-2 probes of the four
    exam stories with three or more victims. Pinned so a story edit that moves
    a label is a deliberate edit here, not a silent drift."""
    probes = generate.shared_origin_probes()
    decoys = generate.shared_origin_decoy_probes()
    full = [st.key for st in stories.exam()]
    narrow = [st.key for st in stories.exam() if len(st.victims) >= 3]
    assert [e.meta["origin"] for e in probes] == full + narrow
    assert [e.meta["label"] for e in probes] == EXAM_PROBE_LABELS
    assert {e.meta["label"] for e in decoys} == {"none"}
    by_key = stories.by_key()
    for e in probes:
        if by_key[e.meta["origin"]].cls == "R":
            assert e.meta["label"] == "shared", e.group


def test_a_decided_shared_origin_probe_workload_carries_the_rules_cause():
    """`node-not-ready`'s victims share one node, so every one decides against
    it and gets the identical rules' cause."""
    st = stories.by_key()["node-not-ready"]
    ex = cases.shared_origin_probe(st, generate._entry_rng("t", st.key))
    causes = {v["cause"] for v in json.loads(ex.assistant)["verdicts"]}
    assert len(causes) == 1
    only = causes.pop()
    assert only.startswith("node ")
    assert ex.meta["scope_value"] in only
    d = so.draw(st, generate._entry_rng("t", st.key), width=len(st.victims))
    # The rules' own terse cause, not the story's shown sentence.
    assert only != so._sub(st.shown_cause, None, d)


# ------------------------------------------------------------ the job split


def test_the_job_split_follows_the_rules_decision(fam):
    decided = undecided = 0
    for ex in fam:
        expected = ex.meta["expected"]
        for name, m in ex.meta["workloads"].items():
            if m["decided"]:
                decided += 1
                assert m["job"] == 1, (ex.group, name)
                assert m["own_cause_keywords"] == [], (ex.group, name)
                assert m["decided_cause"] == expected[name], (ex.group, name)
                assert m["decided_outcome"] in ("confirmed", "unverified"), (ex.group, name)
            else:
                undecided += 1
                assert m["job"] == 2, (ex.group, name)
    assert decided > 0 and undecided > 0, (decided, undecided)
```

Run: `PYTEST tests/test_shared_origin_decided.py`
Expected: 13 PASS, or 12 PASS and 1 FAIL. The one test allowed to fail is
`test_the_exam_probe_labels_are_pinned`, and only on its `EXAM_PROBE_LABELS` line: that literal is a
starting value worked out from the plan, and Step C9 measures the real list and writes it in. If the
test fails on the origin order or on the ruled-story assert instead, stop: that is a real defect. Report
DONE_WITH_CONCERNS with the failure.

- [ ] **Step C7: Rewrite `tests/test_shared_origin_training_pair.py`**

This file has three parts and this step touches two: the header (old :1-94) and the tests from
`test_every_trainable_scenario_is_taught_under_both_answers` (:138) to the end of the file. The
five tests in between stay as they are.

KEEP (5 tests): `test_the_case_mix_names_the_decoy_and_still_sums_to_one_hundred` (:96),
`test_the_two_halves_get_the_same_share` (:102), `test_the_decoy_is_not_a_held_out_case` (:112),
`test_the_generator_emits_the_halves_in_equal_number` (:123),
`test_the_optimizer_never_reads_a_one_sided_pair` (:128).

REWRITE (6 tests, plus the `_pairs` helper):
- `_pairs` (:73). It no longer asserts equal workload sets. Twins share a group and an origin.
- `test_every_trainable_scenario_is_taught_under_both_answers` (:138), now
  `test_every_trainable_story_is_taught_under_both_answers`.
- `test_a_pair_shows_the_same_workloads_with_the_same_menus` (:148), now
  `test_a_pair_shows_the_same_victims`. There is no menu, so the claim is about victims.
- `test_a_pair_does_not_read_the_same_things` (:159) keeps its name.
- `test_the_answer_flips_with_the_read` (:180) keeps its name.
- `test_no_trainable_local_cause_speaks_the_language_of_a_shared_claim` (:215), now
  `test_no_none_labelled_training_cause_speaks_the_language_of_a_shared_claim`. It reads the
  rendered verdict causes in the kept pile, which is the thing the model sees. Task 6's
  per-story answer check is `test_no_story_answer_holds_a_shared_claim_phrase` in
  `tests/test_shared_origin_decided.py`.
- `test_no_trainable_answer_both_denies_sharing_and_speaks_its_language` (:273) keeps its name,
  and `_denying_rows` (:261) is kept as it is. The old claim "every decoy row denies" is no longer
  true, because a healthy world only says "separate reasons" when it earns it. The new claim is
  that the family rows that deny are exactly the decoys whose header says so.

DELETE (2 tests):
- `test_a_pair_reads_the_same_things_in_the_same_order` (:154). It checks the order of the invented
  read labels (`_read_labels`). The new rows print real lines, not labelled reads, and Ruling 35
  asks only that twins differ.
- `test_the_decoy_half_shows_the_component_healthy` (:196). It checks the invented BROKEN line of
  the origin read against the pvc-scoped origins (`_PVC_SCOPED_ORIGINS`). The healthy world is now
  a `World` of its own, and Task 5 pins that the two worlds differ in a printed line.

Also dropped with these: the helpers `_workloads`, `_menu`, `_read_labels` and the constant
`_PVC_SCOPED_ORIGINS`.

Step one. Open `tests/test_shared_origin_training_pair.py`. Delete everything from line 1 down to,
and not including, the line `# ------------------------------------------------------- the mix pairs it up`.
Put this block at the top:

```python
"""The curriculum's minimal contrast: the same story told both ways.

Every `shared_origin` row has a twin, `shared_origin_decoy`, drawn from the
same salt. The twin names the same victims and prints the same story. Only the
world differs. In the broken world the origin is broken. In the healthy world
it is not. The right answer flips with the world.

This is what the 0901 model got wrong. It answered the exam's ten twin pairs
the same way in both worlds on nine of them. Its verdict was a function of
which story it was looking at, not of what the reads said. The fix is to teach
every trainable story under BOTH answers, so nothing about the story predicts
the label. The read does, and only the read.

What this does not claim. It cannot make the model read. It removes a shortcut
that made not reading enough. Whether that shortcut was the cause is a question
for the paired score on the next run, not for this file.
"""

import json
import re

import pytest

from kubeagent_verdict.dataset import cases, generate, stories
from kubeagent_verdict.evals.score import INDEPENDENCE_PHRASES

SIZE = 800
SEED = 17

SHARED = "shared_origin"
DECOY = "shared_origin_decoy"

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")
_SEPARATE_HEAD = re.compile(r"^\d+ workloads are failing for separate reasons\.")


@pytest.fixture(scope="module")
def rows():
    return generate.generate(seed=SEED, size=SIZE)


@pytest.fixture(scope="module")
def kept(rows):
    train, val = generate.split(rows, seed=SEED)
    test = generate.test_set()
    return generate.drop_held_out(train, test) + generate.drop_held_out(val, test)


def _by_case(rows, case):
    return [e for e in rows if e.case == case]


def _victim_keys(example) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in example.group.split("+")}


def _summary(example) -> str:
    return json.loads(example.assistant)["summary"]


def _pairs(rows):
    """Twin rows, matched by emission order and checked by group.

    The emitter writes each pair as two consecutive rows from one salt, so the
    n-th `shared_origin` row and the n-th `shared_origin_decoy` row are twins.
    The group check is what makes that sound: twins carry one group string, and
    it names the story and its victims. The workload sets are not compared. The
    broken world can add an origin row that the healthy world lacks.
    """
    shared = _by_case(rows, SHARED)
    decoy = _by_case(rows, DECOY)
    assert shared, "no shared_origin rows"
    assert len(shared) == len(decoy), "a row has no twin"
    for a, b in zip(shared, decoy):
        assert a.group == b.group, "rows out of step: not twins"
        assert a.meta["origin"] == b.meta["origin"], "twins name different stories"
    return list(zip(shared, decoy))


```

Step two. In the same file, delete everything from the line
`def test_every_trainable_scenario_is_taught_under_both_answers(rows):` to the end of the file
(that is also the section comment above it, `# ------------------------------------ every row is a pair`
stays, because it heads the generator-equality test). Append this block at the end:

```python
def test_every_trainable_story_is_taught_under_both_answers(rows):
    """The claim the whole change rests on: the story does not predict the label."""
    shared = {e.meta["origin"] for e in _by_case(rows, SHARED)}
    decoy = {e.meta["origin"] for e in _by_case(rows, DECOY)}
    assert shared == decoy
    assert shared == {st.key for st in stories.trainable()}


# ------------------------------------------- only the world differs, and it does

def test_a_pair_shows_the_same_victims(rows):
    for shared, decoy in _pairs(rows):
        victims = _victim_keys(shared)
        assert victims == _victim_keys(decoy)
        assert victims <= set(shared.meta["expected"]), shared.group
        assert victims <= set(decoy.meta["expected"]), shared.group


def test_a_pair_does_not_read_the_same_things(rows):
    for shared, decoy in _pairs(rows):
        assert set(shared.user.splitlines()) != set(decoy.user.splitlines()), shared.group


def test_the_answer_flips_with_the_read(rows):
    """The decoy is always `none` and never claims sharing. The broken half
    claims sharing exactly when its label is `shared`, and then its answer
    differs from the decoy's on at least one workload both halves flag."""
    flipped = 0
    for shared, decoy in _pairs(rows):
        decoy_head = _summary(decoy).split("\n")[0]
        assert decoy.meta["label"] == "none", decoy.group
        assert not _SHARED_HEAD.match(decoy_head), decoy.group
        shared_head = _summary(shared).split("\n")[0]
        claims = bool(_SHARED_HEAD.match(shared_head))
        assert claims == (shared.meta["label"] == "shared"), shared.group
        if shared.meta["label"] != "shared":
            continue
        common = set(shared.meta["expected"]) & set(decoy.meta["expected"])
        assert any(shared.meta["expected"][w] != decoy.meta["expected"][w]
                   for w in common), shared.group
        assert _summary(shared) != _summary(decoy), shared.group
        flipped += 1
    assert flipped > 0


def test_no_none_labelled_training_cause_speaks_the_language_of_a_shared_claim(kept):
    """A `none` row's verdicts may not use the words that assert sharing.

    The decoy half teaches "these have SEPARATE causes" by naming each
    workload's own. If one of those causes is worded with a shared-claim
    phrase, the row teaches the grader's positive signal as part of a negative
    answer. job3 reads the summary, which carries the per-workload lines, so it
    would score a correct answer as a shared claim.

    This reads the rendered verdict causes of every kept family row whose
    label is `none`. A `shared` row is exempt, because its summary makes the
    claim on purpose. The per-story version of this check (all 47 stories, both
    worlds, origin rows included) is in tests/test_shared_origin_decided.py.
    """
    checked = 0
    offenders = []
    for e in kept:
        if e.case not in (SHARED, DECOY) or e.meta["label"] != "none":
            continue
        for v in json.loads(e.assistant)["verdicts"]:
            checked += 1
            low = v["cause"].lower()
            offenders += [(e.meta["origin"], e.case, p, v["cause"])
                          for p in cases.SHARED_CLAIM_PHRASES if p in low]
    assert checked > 0
    assert offenders == [], (
        "a none-labelled training cause carries shared-claim language: "
        + "; ".join(f"{o} ({c}) says {p!r} in {t!r}" for o, c, p, t in offenders[:5]))


def _denying_rows(kept):
    """Training rows whose rendered answer denies a shared origin."""
    out = []
    for e in kept:
        summary = str(json.loads(e.assistant).get("summary", "")).lower()
        if any(p in summary for p in INDEPENDENCE_PHRASES):
            out.append((e, summary))
    return out


# 2026-10-03 (Spec 4b-1): the shared-origin rows were rebuilt on real lines; was every
# decoy row, because the old decoy summary always said "separate reasons".
DENYING_ROWS = 40


def test_no_trainable_answer_both_denies_sharing_and_speaks_its_language(kept):
    """A summary that both claims sharing and denies it scores 0 on every label.

    The old guard said every decoy row denies. That is no longer true. A
    healthy world says "failing for separate reasons" only when every row has
    its own, different cause. Otherwise it says the rules did not confirm one
    cause, and that header is not a denial. So the guard is now an equality:
    the family rows that deny are exactly the family rows whose header says
    "separate reasons". An equality cannot be lowered to make a red test
    green. It can only be deleted.
    """
    denying = _denying_rows(kept)
    family_denying = {id(e) for e, _ in denying if e.case in (SHARED, DECOY)}
    earned = {id(e) for e in kept
              if e.case in (SHARED, DECOY) and _SEPARATE_HEAD.match(_summary(e))}
    # A denominator, asserted rather than assumed. An empty set would make the
    # equality pass while measuring nothing.
    assert earned, "no kept family row earned the 'separate reasons' header"
    assert family_denying == earned, (
        f"{len(family_denying)} family rows deny, {len(earned)} earn the header")
    assert len(earned) == DENYING_ROWS

    offenders = [
        (e.case, e.group, [p for p in cases.SHARED_CLAIM_PHRASES if p in summary], summary)
        for e, summary in denying
        if any(p in summary for p in cases.SHARED_CLAIM_PHRASES)
    ]
    assert offenders == [], (
        f"{len(offenders)} of {len(denying)} denying answers also speak "
        "shared-claim language, so the grader reads them as ambiguous: "
        + "; ".join(f"{c} ({g}) says {p}" for c, g, p, _ in offenders[:5]))
```

Check the file shape:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -n '^def test_\|^def _\|^[A-Z_]* = ' tests/test_shared_origin_training_pair.py
```

Expected, in order: `SIZE`, `SEED`, `SHARED`, `DECOY`, `_SHARED_HEAD`, `_SEPARATE_HEAD`, `_by_case`,
`_victim_keys`, `_summary`, `_pairs`, then the five kept tests, then the six rewritten tests with
`_denying_rows` and `DENYING_ROWS` before the last one. There must be no `_workloads`, `_menu`,
`_read_labels` or `_PVC_SCOPED_ORIGINS`.

Run: `PYTEST tests/test_shared_origin_training_pair.py`
Expected: 10 PASS and 1 FAIL. The failing test is
`test_no_trainable_answer_both_denies_sharing_and_speaks_its_language`, with `assert N == 40`. The 40 is
a starting value. Step C9 measures N and writes it in. If the failure is on the equality line above it
instead, or on `assert earned`, stop: that is a real defect (a family row denies without earning the
header, or no row earns it). Report DONE_WITH_CONCERNS with the printed counts.

- [ ] **Step C8: Rewrite `tests/test_shared_origin_decoy_probe.py`**

The decoy probe is the counter-example half of the exam: the same story, the origin healthy. The
old file leaned hard on the made-up menu, the read labels and the tag heuristics. All of those are
gone. What still holds is the idea: a pair is a real contrast, the decoy's right answer makes no
shared claim, and a model that copies the twin's answer must fail.

REWRITE (8 tests):
- `test_the_slice_mirrors_the_probe_row_for_row` (:108) keeps its name. The lists are now built from
  `stories.exam()`.
- `test_the_pair_reads_the_same_things_in_the_same_order` (:153), now
  `test_the_pair_shows_the_same_victims_and_the_lines_differ`. The same order is no longer asked
  (Ruling 35). The same group and the same victims are.
- `test_the_correct_answer_is_each_workload_s_own_local_cause` (:184), now
  `test_the_correct_answer_is_each_workload_s_own_cause`.
- `test_the_summary_says_separate_reasons` (:194), now `test_the_summary_makes_no_shared_claim`. The
  header says "separate reasons" only when it is earned, so the test checks what matters: no claim.
- `test_the_shared_cause_is_the_decoy_the_scorer_watches` (:200), now
  `test_the_slice_sets_no_row_level_decoy`. `decoy_causes` is `[]` (Ruling 8).
- `test_the_slice_carries_shared_claim_phrases_and_no_wrong_summary_phrase` (:222) keeps its name and
  gains the three other dropped meta keys.
- `test_a_model_that_always_claims_a_shared_origin_fails_this_slice` (:317), now
  `test_a_model_that_copies_the_twin_s_answer_fails_this_slice`. The twin's reply is filtered to the
  decoy's own workloads first (Ruling 36).
- `test_a_model_that_reads_the_evidence_passes_this_slice` (:380) keeps its name.

DELETE (5 tests, and the helpers they use):
- `test_every_eval_scenario_declares_a_healthy_origin_read` (:114). It checks `healthy_origin_content`,
  the invented origin read. A story's healthy world is a `World` now.
- `test_the_pair_shows_the_same_workloads_with_the_same_menus` (:119). It checks the candidate menu.
- `test_no_decoy_prompt_carries_a_BROKEN_line_of_the_origin_read` (:162). It checks the invented
  BROKEN line of the origin read. The two worlds are separate objects now, so no line can leak from one
  into the other, and `test_the_pair_shows_the_same_victims_and_the_lines_differ` checks they differ.
- `test_no_tag_heuristic_wins_both_shared_origin_slices` (:259, parametrized) and its helper
  `_menu_pick`. It checks the menu tags (`attributed`, `outranked`). There are no tags.
- `test_every_origin_read_label_in_the_exam_carries_both_answers` (:295). It reads
  `origin_read[0]`, the label of the invented read. The label is gone, and Ruling 35 asks only that
  twins differ in a printed line.
- The helpers `_sections`, `SECTION` and `LABEL` go with them. Nothing left uses them.

KEEP (1 test): `test_the_slice_drops_no_training_row` (:410), with its banner.

Open `tests/test_shared_origin_decoy_probe.py`. Delete everything from line 1 down to, and not
including, the banner line `# ------------------------------------------- the training set must not move`.
Put this block at the top. Keep the banner and the kept test below it exactly as they are.

```python
"""The counter-example half of the shared-origin exam.

A shared-origin pair is one story told in two worlds. In `shared_origin_probe`
the origin is broken. In `shared_origin_decoy_probe` the same story is told
with the origin healthy. The two rows draw the same names from the same seed,
so they are a minimal contrast: the same victims, the same story. What the
reads say about the origin is what differs.

The right answer flips with the read. In the broken world the rules may
confirm one cause on two or more workloads, and the summary says so. In the
healthy world the rules confirm nothing, so each workload answers with its own
cause, or with `none_of_these` when its own lines do not show why.

These tests check three things.

* The pair is a real contrast: one group, the same victims, different lines.
* The decoy's right answer makes no shared claim.
* The scorer has teeth. A model that copies the twin's answer fails job 3 on
  every pair whose probe is labelled `shared`. A model that reads the
  evidence passes everything.

What this slice does not do. A model that always answers "separate reasons"
would pass these rows. The pair catches it, because the probe half expects a
shared claim. This file is the second half of a pair, not a fix on its own.
"""

import json
import re

import pytest

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import cases, generate, stories
from kubeagent_verdict.evals import score

CASE = "shared_origin_decoy_probe"

_SHARED_HEAD = re.compile(r"^\d+ workloads share one upstream cause: ")


@pytest.fixture(scope="module")
def exam():
    return generate.test_set()


@pytest.fixture(scope="module")
def decoys(exam):
    rows = [e for e in exam if e.case == CASE]
    # Without this, every loop below passes over an empty list and the slice
    # could be unwired from `probe_sets` with a green suite.
    assert rows, f"{CASE} is not in the exam"
    return rows


@pytest.fixture(scope="module")
def probes(exam):
    return [e for e in exam if e.case == "shared_origin_probe"]


def _victim_keys(ex) -> set[str]:
    """The victims a twin names, read off its group (`+`-joined segments)."""
    return {seg.split(":", 2)[2] for seg in ex.group.split("+")}


def _template_pattern(template: str):
    """A regex for a story's cause template, each `{name}` slot matching any text."""
    return re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(template)))


def _twin_reply(decoy, probe) -> str:
    """The probe's own answer, cut down to the decoy's workloads.

    The broken world can flag an origin row that the healthy world does not
    (Ruling 36). A model that copied the probe's answer would also name that
    row, which the decoy does not ask about. Cutting the reply to the
    decoy's workloads keeps the contract check about the answer's content.
    """
    flagged = set(decoy.meta["expected"])
    doc = json.loads(probe.assistant)
    return json.dumps({"verdicts": [v for v in doc["verdicts"] if v["workload"] in flagged],
                       "summary": doc["summary"]}, ensure_ascii=False)


# --------------------------------------------------------------- the slice

def test_the_slice_mirrors_the_probe_row_for_row(decoys, probes):
    """Same stories, same widths, same order: one counter-example each."""
    want = ([st.key for st in stories.exam()]
            + [st.key for st in stories.exam() if len(st.victims) >= 3])
    assert len(decoys) == len(probes) == len(want) == 10
    assert [e.meta["origin"] for e in decoys] == want
    assert [e.meta["origin"] for e in probes] == want


def test_the_pair_shows_the_same_victims_and_the_lines_differ(decoys, probes):
    """The claim that makes the pair a contrast rather than two questions.

    The twins share a group, so they name the same victims. Their printed
    lines must differ, or the pair asks nothing and a model cannot tell the
    two worlds apart by reading.
    """
    for d, p in zip(decoys, probes):
        assert d.group == p.group, d.meta["origin"]
        victims = _victim_keys(d)
        assert victims <= set(d.meta["expected"]), d.meta["origin"]
        assert victims <= set(p.meta["expected"]), d.meta["origin"]
        assert set(d.user.splitlines()) != set(p.user.splitlines()), d.meta["origin"]


def test_the_correct_answer_is_each_workload_s_own_cause(decoys):
    """No named cause repeats inside a row, and none is the story's shared cause.

    `none_of_these` may repeat: it is an answer, not a cause. At least one
    decoy must name two or more causes, or the test above proves nothing about
    distinctness.
    """
    patterns = {st.key: _template_pattern(st.shown_cause) for st in stories.exam()}
    multi = 0
    for e in decoys:
        named = [c for c in e.meta["expected"].values() if c != contract.NONE_OF_THESE]
        assert len(named) == len(set(named)), e.group
        for cause in named:
            assert not patterns[e.meta["origin"]].fullmatch(cause), (e.group, cause)
        if len(named) >= 2:
            multi += 1
    assert multi > 0


def test_the_summary_makes_no_shared_claim(decoys):
    for e in decoys:
        summary = json.loads(e.assistant)["summary"]
        assert e.meta["label"] == "none", e.group
        assert not _SHARED_HEAD.match(summary), e.group
        assert score.job3("none", summary) == 1.0, e.group
        low = summary.lower()
        for ph in cases.SHARED_CLAIM_PHRASES:
            assert ph not in low, (e.group, ph)


def test_the_slice_sets_no_row_level_decoy(decoys):
    """Ruling 8: `decoy_causes` is `[]`. A story has no scripted wrong cause
    any more. What the scorer watches is `decoy_by_workload`, the causes the
    rules ruled out or refuted for that workload."""
    for e in decoys:
        assert e.meta["decoy_causes"] == [], e.group
        assert set(e.meta["decoy_by_workload"]) <= set(e.meta["expected"]), e.group


def test_the_slice_carries_shared_claim_phrases_and_no_wrong_summary_phrase(decoys):
    for e in decoys:
        assert e.meta["shared_claim_phrases"] == list(cases.SHARED_CLAIM_PHRASES), e.group
        for gone in ("wrong_summary_phrase", "origin_read_label",
                     "distractor_cause", "expected_confidence"):
            assert gone not in e.meta, (e.group, gone)


# ------------------------------------------------------------ the teeth

def test_a_model_that_copies_the_twin_s_answer_fails_this_slice(decoys, probes):
    """The failure mode a shared-origin correction can plausibly introduce.

    The fake answer is the TWIN row's own assistant message, cut down to the
    decoy's workloads. Same salt means same victim names, so the twin's answer
    is exactly what a model that had learned "a story with an origin means one
    shared cause" would emit here.

    job3 grades the summary against THIS row's own `none` label. So it tracks
    what the twin's summary claims, not which story it is. A `shared`-labelled
    twin writes "N workloads share one upstream cause", which is false here, so
    job3 reads 0.0. A `none`-labelled twin already writes the honest "rules did
    not confirm one cause" header, so job3 reads 1.0. Both kinds must occur, or
    the test would only prove one of them.
    """
    reply = {d.user: _twin_reply(d, t) for d, t in zip(decoys, probes)}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: reply[m[1]["content"]])
    seen = set()
    for d, t, r in zip(decoys, probes, results):
        assert r["contract_ok"], (d.group, r["contract_reasons"])
        want = 0.0 if t.meta["label"] == "shared" else 1.0
        assert r["job3"] == want, d.group
        seen.add(t.meta["label"])
    assert seen == {"shared", "none"}


def test_a_model_that_reads_the_evidence_passes_this_slice(decoys):
    """Non-vacuity: the assertions above are about the ANSWER, not the shape.

    The fake answer is each decoy row's own gold. It must pass the contract and
    score full marks on cause, confidence and job 3, and it must never name a
    decoy cause. (`named_decoy` is None where no job-2 workload has a listed
    decoy, and False where one does and the reply avoids it.)
    """
    by_prompt = {e.user: e.assistant for e in decoys}
    results = score.evaluate([generate.to_row(e) for e in decoys],
                             lambda m: by_prompt[m[1]["content"]], grade_job2=True)
    for e, r in zip(decoys, results):
        assert r["contract_ok"], (e.group, r["contract_reasons"])
        assert r["cause_acc"] == 1.0, e.group
        assert r["conf_acc"] == 1.0, e.group
        assert r["job3"] == 1.0, e.group
        assert r["named_decoy"] in (False, None), e.group


```

Check the file shape:

```bash
cd /home/ubuntu/git/kubeagent-verdict && grep -n '^def test_\|^def _\|^CASE\|^# ---' tests/test_shared_origin_decoy_probe.py
```

Expected: `CASE`, `_victim_keys`, `_template_pattern`, `_twin_reply`, the three section comments, the
eight rewritten tests, then the banner `# ----- the training set must not move` and
`test_the_slice_drops_no_training_row` last. There must be no `_sections`, `_menu_pick`, `SECTION` or `LABEL`.

Run: `PYTEST tests/test_shared_origin_decoy_probe.py`
Expected: PASS (9 tests).

- [ ] **Step C9: Measure, then fill in the pins**

Three values cannot be known until the new rows exist. All three ship with a starting value.
`EXAM_PROBE_LABELS` is checked only on the labels the plan states (a ruled story is `shared` at every
width; `coredns-down` is `shared` at full width and `none` at width 2; `networkpolicy-deny-all` is
`shared` at full width; the probes hold both labels). The rest of the list (`node-disk-pressure` and the
width-2 row of a plain story other than `coredns-down`) depends on how Task 6 wrote the victim texts, so
it is measured, not guessed. Run:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
import json
import re

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import generate, stories
from kubeagent_verdict.evals.score import INDEPENDENCE_PHRASES

NONE = contract.NONE_OF_THESE
failed = []


def check(ok, what):
    print("CHECK", "ok  " if ok else "FAIL", what)
    if not ok:
        failed.append(what)


probes = generate.shared_origin_probes()
decoys = generate.shared_origin_decoy_probes()

# 1. The keyword count, counted two ways.
keyed = 0
job2_named = 0
for ex in probes + decoys:
    for w, m in ex.meta["workloads"].items():
        if m["job"] == 2 and m["expected_cause"] != NONE:
            keyed += 1
            if not 1 <= len(m["own_cause_keywords"]) <= 3:
                failed.append(f"{ex.group} {w}: keywords {m['own_cause_keywords']}")
    for v in json.loads(ex.assistant)["verdicts"]:
        if v["cause"] != NONE and not ex.meta["workloads"][v["workload"]]["decided"]:
            job2_named += 1
print("EXAM_KEYWORDED measured:", keyed)
check(keyed > 0, "at least one named job-2 workload on the exam")
check(keyed == job2_named, f"keyed {keyed} equals named undecided verdicts {job2_named}")

# 2. The ten probe labels.
labels = [ex.meta["label"] for ex in probes]
print("EXAM_PROBE_LABELS measured:", labels)
by_key = stories.by_key()
full = [st.key for st in stories.exam()]
narrow = [st.key for st in stories.exam() if len(st.victims) >= 3]
origins = [ex.meta["origin"] for ex in probes]
check(origins == full + narrow, "six full-width probes in exam order, then the width-2 probes")
for ex in probes:
    if by_key[ex.meta["origin"]].cls == "R":
        check(ex.meta["label"] == "shared", f"ruled probe {ex.group} is shared")
check(labels[full.index("coredns-down")] == "shared", "coredns-down full width is shared")
check(labels[len(full) + narrow.index("coredns-down")] == "none", "coredns-down width 2 is none")
check(labels[full.index("networkpolicy-deny-all")] == "shared",
      "networkpolicy-deny-all full width is shared")
check(set(labels) == {"shared", "none"}, "the probes hold both labels")
check({ex.meta["label"] for ex in decoys} == {"none"}, "every exam decoy is none")

# 3. The denying family rows in the kept pile.
rows = generate.generate(seed=17, size=800)
train, val = generate.split(rows, seed=17)
test = generate.test_set()
kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
head = re.compile(r"^\d+ workloads are failing for separate reasons\.")
fam = [e for e in kept if e.case in ("shared_origin", "shared_origin_decoy")]
earned = {id(e) for e in fam if head.match(json.loads(e.assistant)["summary"])}
deny = {id(e) for e in fam
        if any(p in str(json.loads(e.assistant)["summary"]).lower() for p in INDEPENDENCE_PHRASES)}
print("DENYING_ROWS measured:", len(earned), "| family rows kept:", len(fam))
check(len(earned) > 0, "at least one kept family row earns the 'separate reasons' header")
check(deny == earned, f"family rows that deny ({len(deny)}) are the rows that earn ({len(earned)})")

# 4. The probe row counts.
check(len(generate.shared_origin_cousin_probes()) == 82, "cousin probe has 82 rows")
check(len(generate.shared_origin_wide_probes()) == 60, "wide probe has 60 rows")
check(len(generate.test_set()) == 249, "the exam has 249 rows")

print("failed checks:", len(failed))
raise SystemExit(1 if failed else 0)
EOF
```

Expected: exit 0, `failed checks: 0`. If a CHECK fails, stop. Commit nothing. Do not edit a pin to
make it pass. Report DONE_WITH_CONCERNS with the whole printout. A `FAIL` on a label line means the
real rows disagree with the Task 4 and Task 5 facts, which is the controller's call.

When it passes, make exactly three edits with the Edit tool, using the printed values.

1. In `tests/test_shared_origin_keywords.py`, the line `EXAM_KEYWORDED = 12` becomes
   `EXAM_KEYWORDED = <the number printed after "EXAM_KEYWORDED measured:">`. Leave the dated comment
   above it as it is. It already reads
   `# 2026-10-03 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 18.`
2. In `tests/test_shared_origin_training_pair.py`, the line `DENYING_ROWS = 40` becomes
   `DENYING_ROWS = <the number printed after "DENYING_ROWS measured:">`. Leave the dated comment above
   it as it is. It already reads
   `# 2026-10-03 (Spec 4b-1): the shared-origin rows were rebuilt on real lines; was every decoy row, because the old decoy summary always said "separate reasons".`
   The comment is wrapped over two lines in the file. Keep it that way.
3. In `tests/test_shared_origin_decided.py`, the `EXAM_PROBE_LABELS = [...]` list becomes the list
   printed after `EXAM_PROBE_LABELS measured:`, wrapped five to a line as it is now. Leave the dated
   comment above it as it is.

If the day this step runs is not 2026-10-03, change the date in all three comments to that day.

- [ ] **Step C10: Run the six files**

Run: `PYTEST tests/test_probe_cousins.py tests/test_probe_wide.py tests/test_shared_origin_keywords.py tests/test_shared_origin_decided.py tests/test_shared_origin_training_pair.py tests/test_shared_origin_decoy_probe.py`
Expected: PASS, 51 tests (cousins 8, wide 6, keywords 4, decided 13, training pair 11, decoy probe 9).
If the count differs, a function was lost in a splice. Run the `grep` check from Steps C3, C4, C7 and C8.

Then run the whole suite once, to see that nothing outside these six files leans on what changed:

Run: `PYTEST tests`
Expected: report only, never a reason to edit. No failure may be in the six files above. Elsewhere
the only failures allowed are Task 10's five, named at the top of this task, and failures in Part D's
four files (`tests/test_score.py`, `tests/test_oracle.py`, `tests/test_answer_keys.py`,
`tests/test_generate.py`), which Part D re-pins next. Write any other failure by name into the task
report and do not fix it here. It belongs to the part that owns the file (Ruling 47).

- [ ] **Step C11: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_probe_cousins.py tests/test_probe_wide.py tests/test_shared_origin_keywords.py tests/test_shared_origin_decided.py tests/test_shared_origin_training_pair.py tests/test_shared_origin_decoy_probe.py \
  && COMMIT "test(shared-origin): rewrite the probe, pair, decoy-probe, keyword and decided tests"
```

Expected: `ruff` prints `All checks passed!` and the commit is made. Do not add `.gitignore`,
`train-v2.log` or the plan file. The commit message has no author trailer and no tool credit.

#### Part D: the exam and pool numbers that move

**Files:**
- Modify: `tests/test_score.py` — rewrite the `_name_the_decoy_bot` helper (:3091); re-pin 16 tests (:1499-:3534); one helper docstring (`_never_say_shared_bot` :2455).
- Modify: `tests/test_oracle.py` — re-pin 10 tests (:131-:514); one helper docstring (`_gold_results` :39).
- Modify: `tests/test_answer_keys.py` — re-pin 5 tests (:95-:260); the `WEAK_PAIRS` list (:189) when the pairs change.
- Modify: `tests/test_generate.py` — re-pin 3 tests (:401, :605, :836). Task 7 already edited this file (`_HEADER_EXEMPT`, the skip rule, `import hashlib`, `OTHER_FAMILIES_SHA256` and `test_the_other_families_exam_rows_did_not_move`). This part leaves all of that alone.
- Not touched here: `tests/test_shared_origin_floor.py`, `tests/test_shared_origin_pool.py` and the listed tests in `tests/test_shared_origin_training.py` (Task 8 owns them, Ruling 28); the three hash pins and the banked-exam test (Task 10).
- Scratch, never committed: `/tmp/kv-t9d/` (the measured numbers and the edit scripts).
- No production code.

Line numbers are from main @ ff6527e. Find each test by its name.

**Interfaces:**
- Consumes (all built by Tasks 2-8): `generate.test_set()`, `generate.generate(17, 8000)`, `generate.split`, `generate.drop_held_out`, `generate.to_row`; `score.evaluate`, `score.scoreboard`, `score._workload_decoys`, `score._keyword_exposure`, `score._is_job2_keyword_graded`, `score._job2_guarded`; the helpers the four test files already define (`_own_keyword_bot`, `_rewrite_keyword_answer_keys`, `_unguarded_job2_scores`, `_gold_results`, `_job2_gate`, `_job2_keyword_only`, `_decided_lines`).
- Row facts it relies on: a rebuilt family row is labelled `shared` or `none`, never `separate` (Ruling 25); every named job-2 workload on it carries `own_cause_keywords` in `meta["workloads"][w]`, and `meta["decoy_causes"]` is `[]` (Ruling 8); `decoy_by_workload[w]` holds the causes the rules ruled out or refuted for `w` (Ruling 12).
- Produces: the re-pinned exam job counts in `tests/test_oracle.py` (Task 10's measure must print the same "now" numbers, and its Step 6 runs `tests/test_oracle.py` to prove it); the regenerated `WEAK_PAIRS` in `tests/test_answer_keys.py` (Task 11 reads `len(WEAK_PAIRS)` itself). Task 11 copies nothing from this part's report.

**What moves, in plain words.** The exam has 249 rows. 229 of them are other families and do not change; Task 7 pins that with `OTHER_FAMILIES_SHA256`. 20 are shared-origin family rows (10 `shared_origin_probe`, 10 `shared_origin_decoy_probe`). Task 7 rebuilt those 20 on real lines. The training pool (8,000 rows) splits the same way: 5,600 other rows and 2,400 family rows, and the train and val files are cut from it.

Many tests pin a count over the whole exam or the whole pool. Such a count is `a` from the other rows plus `b` from the family rows. Only `b` can move. So every pin gets the same treatment: measure it once (Step D3), check that the `a` part is the number it was, and write the new total next to a dated comment.

Three jobs, explained once. **Job 1:** the rules decide the workload, and the right answer is the rules' cause. **Job 2:** the model names the cause, or says `none_of_these`. **Job 3:** a row-level label, `shared` or `none`. The rebuilt rows never use `separate` (Ruling 25); `multi` rows keep it.

**Rules for every step in this part**

- No bar moves: 0.9, 0.7, 0.9, and every test threshold and tolerance (`abs=0.005` stays). Never run a test with `-update`.
- A pin changes only to the number Step D3 measured. A pin never changes to make a check pass.
- Every changed pin gets a dated comment on the line above it, in this form. The date is the day Step D3 runs. Old comments stay.

  ```python
  # <YYYY-MM-DD, the day D3 ran> (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines; was 169.
  assert counted == <new number>
  ```

  Pool pins say "the shared-origin rows of the training pool were rebuilt on real lines" in place of "the 20 shared-origin exam rows".
- If a CHECK fails or a step says stop: stop, commit nothing, and report DONE_WITH_CONCERNS with the numbers.

**The steps**

| Step | What it does |
|---|---|
| D1 | Run the four files. Only the 34 tests this part re-pins may fail. |
| D2 | Rewrite the `_name_the_decoy_bot` helper (the one rewrite). |
| D3 | MEASURE. One script prints all 71 numbers and runs every check. |
| D4 | Write the small edit helper. |
| D5-D8 | One edit script per file: score, generate, oracle, answer keys. |
| D9 | Check the diff. |
| D10 | Run the four files green; run the whole suite once, report only. |
| D11 | Lint and commit. |

##### What happens to each test

There are 265 test functions in the four files. Every one is in exactly one row of this table. (Pytest runs 274 cases on today's tree, because nine of the functions take parameters. This part counts functions.)

| File | Tests | RE-PIN | KEEP | DELETE |
|---|---|---|---|---|
| `tests/test_score.py` | 198 | 16 | 182 | 0 |
| `tests/test_oracle.py` | 11 | 10 | 1 | 0 |
| `tests/test_answer_keys.py` | 11 | 5 | 6 | 0 |
| `tests/test_generate.py` | 45 | 3 | 42 | 0 |
| **Total** | **265** | **34** | **231** | **0** |

**REWRITE (1 helper, no test).** `_name_the_decoy_bot` (:3091), in Step D2. Its fallback for a workload with no decoy was `none_of_these`. A rebuilt shared-origin workload can expect `none_of_these` and carry no decoy, so the old bot would score a point it should not. The new bot answers `(no decoy offered)` there, which is never right. Step D5 also adds a count to its test, so a 0 score only counts when decoys were on offer.

**DELETE (0).** The deletion rule allows deleting only a test about the made-up candidate menu, the 12 X stories or the invented origin read. None of the 265 is one. `origin_read_label` is read in `tests/test_generate.py` by exactly two tests, `test_a_multi_row_reads_each_object_once_within_the_budget` (:1051) and `test_a_multi_rows_origin_label_is_the_read_it_prints` (:1062). Both walk `multi` rows only (the `multi_rows` fixture), and `multi` is untouched. The menu, X-story and origin-variant tests live in other files, under other parts of this plan.

**RE-PIN (34).** Listed by file in Steps D5-D8, each with the pins it reads and what changes. Three of them also get a new name if the numbers in the old name move (see the tables). Also changed: the docstrings of the helpers `_never_say_shared_bot` and `_gold_results`, and the `WEAK_PAIRS` list when the pairs change.

**KEEP (231).** Nothing changes in these. The ones that read generated family rows, or pin a number the family could move, are named here with the reason. They must PASS in Step D1 and Step D10. The rest are in the appendix at the end.

`tests/test_generate.py`, 30 tests that read generated rows and pin no count the family moves:

- They check a rule the new rows also keep (determinism, contract, provenance, row schema):
  `test_generate_is_deterministic` (:21), `test_provenance_no_banned_text` (:28), `test_every_example_is_contract_valid` (:35), `test_to_row_schema` (:50), `test_provenance_no_banned_text_in_test_set` (:277), `test_provenance_scan_reaches_every_catalog_entry` (:293).
- They check how rows are grouped and split. `test_probe_rows_never_enter_train_or_val` bans `shared_origin_probe` but not `shared_origin_decoy_probe`; it stays as it is:
  `test_case_mix_present_in_generated_set` (:71), `test_split_never_straddles_a_group` (:83), `test_drop_held_out_removes_colliding_groups` (:131), `test_probe_rows_never_enter_train_or_val` (:148), `test_drop_held_out_splits_compound_test_groups` (:165).
- They check the exam is built from the committed rows and rotates over the right entries:
  `test_corpus_test_set_derives_from_committed_rows` (:93), `test_corpus_rows_the_rules_do_not_decide_take_their_own_cause` (:101), `test_job1_cases_rotate_over_the_entries_the_rules_decide` (:120), `test_test_set_is_not_all_one_case` (:139), `test_test_set_is_deterministic` (:179).
- They pin case counts or decoys. D3 measures the same numbers and checks them:
  `test_every_probe_row_carries_a_decoy_that_is_not_the_answer` (:184) reads only `positional_probe` and `misattribution_probe`; `test_test_set_slice_counts_are_pinned` (:341) pins 10 `shared_origin_probe`, 10 `shared_origin_decoy_probe` and 249 in all; `test_every_decoy_probe_row_names_its_decoy_cause` (:866) pins row-level decoys on `wrong_attribution` 20, `positional_probe` 17 and `misattribution_probe` 20, and the family names none; `test_the_length_gap_decider_has_rows_in_both_slices` (:897) pins 57 rows with a length verdict, and none is a family row.
- They check generate's size, errors and `multi`:
  `test_generate_stops_at_first_error_and_writes_nothing` (:549), `test_generate_appends_one_training_only_separate_multi_row` (:568), `test_generate_builds_exactly_size_rows` (:591), `test_every_declared_down_node_appears_ruled_out_on_every_other_workload` (:664), which walks `multi` rows, `test_every_crash_family_workload_in_a_multi_row_keeps_its_log_read` (:971).
- They check prompt text:
  `test_registry_fresh_read_literal_is_a_substring_of_the_events_read` (:736), `test_no_pull_event_line_has_no_events_for_in_it` (:772), `test_one_prompt_has_one_answer` (:915), `test_clear_rows_outnumber_thin_rows_for_every_thin_entry_and_shape` (:940), `test_every_job2_header_follows_kubeagents_rule` (:1120).

`tests/test_score.py`:

- `test_echo_the_decided_cause_bot_clears_job1_and_scores_zero_on_job2` (:2446) uses the generated exam but asserts rates only (1.0 and 0.0). D3 checks the same rates.
- `test_the_gold_answer_passes_the_grader_guard_on_every_exam_job2_workload` (:3245) asserts zero refusals and no literal count. D3 checks it too.
- `test_evaluate_does_not_guard_a_job1_workload` (:1311), `test_decoy_gate_unions_the_workload_list_with_the_row_level_pair` (:1400) and `test_decoy_gate_is_none_when_the_only_decoy_sits_on_a_job1_workload` (:1474) build their rows by hand. They pass whatever the generator does. Their docstrings describe the old `decoy_by_workload` shape as history, and stay as written.

`tests/test_oracle.py`: `test_oracle_multi_job1_matches_the_spec_measurement` (:374) pins `multi` job-1 numbers for train and val (1207 of 1207 and 163 of 163). `multi` is not a family case; D3 checks both numbers did not move.

`tests/test_answer_keys.py`, all six kept tests:

- `test_init_container_is_the_three_spellings_and_never_bare_init` (:61), `test_the_seven_changed_entries_carry_the_spec_table` (:65), `test_every_other_entry_has_no_must_not_words` (:71), `test_each_init_spelling_trips_the_main_container_memory_key` (:77), `test_initial_and_initialize_do_not_trip_it` (:87): catalog-only, no generated rows.
- `test_0920s_wrong_memory_request_answers_score_0` (:167): reads exam rows 197 and 198, the two 0920 memory-request workloads. D3 checks they are still those rows.

Tasks 2 to 8 are done, so the rebuilt rows are live. The old numbers count the old rows, so some pins now fail. Only the 34 tests this part re-pins may fail. A failure anywhere else is a surprise and stops this part.

- [ ] **Step D1: Run the four files, then compare every failure with the list**

Run:

```bash
mkdir -p /tmp/kv-t9d && cd /home/ubuntu/git/kubeagent-verdict \
  && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -rfE --tb=no \
       tests/test_score.py tests/test_oracle.py tests/test_answer_keys.py tests/test_generate.py \
       > /tmp/kv-t9d/d1.out 2>&1; tail -1 /tmp/kv-t9d/d1.out
```

Then compare. These are the old names of the 34 (three of them may be renamed in Step D5 and Step D8):

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import sys

MAY_FAIL = {
    "tests/test_score.py": [
        "test_the_gold_reply_names_no_decoy_on_any_exam_row",
        "test_the_footnote_counts_the_corpus_job2_keyword_population",
        "test_empty_reply_bot_scores_zero_on_every_job_with_full_n",
        "test_never_say_shared_bot_scores_35_of_40_on_job3",
        "test_a_regex_copier_scores_the_job1_ceiling_the_model_card_states",
        "test_always_none_of_these_bot_scores_well_under_the_job2_bar",
        "test_the_grader_guard_zeroes_a_bot_that_pastes_the_prompt",
        "test_the_grader_guard_zeroes_a_bot_that_echoes_its_own_entries",
        "test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut",
        "test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2",
        "test_a_bot_that_names_the_decoy_scores_zero_on_job2_with_or_without_the_guard",
        "test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy",
        "test_the_gold_answer_passes_the_grader_guard_on_every_training_pool_job2_workload",
        "test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row",
        "test_the_exposed_workloads_trace_back_to_twenty_catalog_entries",
        "test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest",
    ],
    "tests/test_oracle.py": [
        "test_oracle_job1_is_perfect_on_train",
        "test_oracle_job1_is_perfect_on_val",
        "test_oracle_job2_gate_is_perfect_on_train",
        "test_oracle_job2_gate_is_perfect_on_val",
        "test_oracle_job2_keyword_only_matches_the_spec_measurement",
        "test_oracle_job3_is_perfect_on_train",
        "test_oracle_job3_is_perfect_on_val",
        "test_exam_oracle_job1_is_perfect",
        "test_exam_oracle_job3_is_perfect",
        "test_exam_oracle_job2_is_perfect",
    ],
    "tests/test_answer_keys.py": [
        "test_every_pool_workload_carries_its_entrys_must_not_list",
        "test_every_pool_gold_passes_its_own_key_with_must_not",
        "test_only_exam_job2_workloads_carry_must_not_words",
        "test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs",
        "test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads",
    ],
    "tests/test_generate.py": [
        "test_the_job2_keyword_exposure_is_pinned_per_case",
        "test_job_population_counts_match_the_pinned_exam_shape",
        "test_every_job1_workload_prints_its_decided_line_and_no_job2_one_does",
    ],
}
lines = open("/tmp/kv-t9d/d1.out").read().strip().splitlines()
print(lines[-1] if lines else "no output at all")
if not lines or not ("passed" in lines[-1] or "failed" in lines[-1]):
    sys.exit("D1: pytest did not finish, read /tmp/kv-t9d/d1.out")
failed, outside = [], []
for line in lines:
    if not line.startswith(("FAILED ", "ERROR ")):
        continue
    path, _, name = line.split()[1].partition("::")
    name = name.split("[")[0]
    failed.append((path, name))
    if name not in MAY_FAIL.get(path, ()):
        outside.append((path, name))
print("D1: failed", len(failed), "- outside the list of 34:", len(outside))
for path, name in outside:
    print("  OUTSIDE", path, name)
sys.exit(1 if outside else 0)
EOF
```

Expected: exit 0 and `D1: failed N - outside the list of 34: 0`, with N anywhere from 0 to 34. A test in the 34 that passes is fine: its number did not move, and Step D3 will say so. The run counts 274 cases (265 functions) plus the ones Task 7 added to `tests/test_generate.py`. Do not stop on the total; stop on a name.

The controller has already compared Task 7's failure list with this part (Ruling 47). If the dispatch names a test it added to this part, put that name in `MAY_FAIL` under its file before you run the check; the dispatch says how to fix it. Any other `OUTSIDE` line: stop, commit nothing, and report DONE_WITH_CONCERNS with the name and the failure text. Never add a name the dispatch did not give.

- [ ] **Step D2: Replace `_name_the_decoy_bot` (:3091) with the version below**

The block below holds the whole new helper (the `BOT` text) and replaces the old one whole. It must run before Step D3, because D3 measures with this bot.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import ast
from pathlib import Path

path = Path("tests/test_score.py")
src = path.read_text()
tree = ast.parse(src)
lines = src.split("\n")


def span(name):
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            start = min([n.lineno] + [d.lineno for d in n.decorator_list])
            return start - 1, n.end_lineno
    raise SystemExit(f"no function {name}")


BOT = '''_NO_DECOY_TO_NAME = "(no decoy offered)"


def _name_the_decoy_bot(rows: list[dict]):
    """Answers every flagged workload with its first decoy: its own
    `decoy_by_workload` entries first, then the row's decoys. A workload
    with no decoy at all gets `_NO_DECOY_TO_NAME`, a reply that is never
    right. It must not get `none_of_these`: a rebuilt shared-origin
    workload can expect `none_of_these` and carry no decoy, and the old
    fallback would have scored it. It walks into the trap every time it
    is offered one."""
    by_prompt = {r["messages"][1]["content"]: r for r in rows}

    def chat_fn(messages: list[dict]) -> str:
        meta = by_prompt[messages[1]["content"]]["meta"]
        row_decoys = meta.get("decoy_causes") or [meta.get("decoy_cause")]
        verdicts = []
        for name in meta["workloads"]:
            decoys = [d for d in [*(meta.get("decoy_by_workload") or {}).get(name, []),
                                  *row_decoys] if d]
            verdicts.append({"workload": name,
                             "cause": decoys[0] if decoys else _NO_DECOY_TO_NAME,
                             "confidence": "high",
                             "rationale": "the candidate the prompt offers"})
        return json.dumps({"verdicts": verdicts,
                           "summary": "see the verdicts above for details"})

    return chat_fn'''
s, e = span("_name_the_decoy_bot")
old = "\n".join(lines[s:e])
assert old.count("decoys[0] if decoys else NONE_OF_THESE") == 1, "the old bot is not the one this step replaces"
lines[s:e] = BOT.split("\n")
out = "\n".join(lines)
ast.parse(out)
path.write_text(out)
print("replaced _name_the_decoy_bot in tests/test_score.py")
EOF
```

The script refuses to run (and writes nothing) if the old body does not hold `decoys[0] if decoys else NONE_OF_THESE` exactly once.

Run: `PYTEST tests/test_score.py -k test_a_bot_that_names_the_decoy`
Expected: PASS, or FAIL on one of the two lines that hold the old job-2 count: `assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}` or `assert (sum(unguarded), len(unguarded)) == (0, 177)`. In both, the rate must read `0.0` and the first number of the pair `0`; only the `n` differs, because the exam's job-2 count moved. That is fine: Step D5 re-pins it. If the rate is not `0.0` or the first number is not `0`, the bot scored a point; stop, commit nothing and report DONE_WITH_CONCERNS with the numbers. If the failure is anything else, stop the same way.

- [ ] **Step D3: Run the master script, then read its output**

This is the only step that measures. One script prints every number this part pins, once, each with a label such as `exam.job2_n`. Every later step quotes those labels, so no number is copied by hand.

For each number the script prints one `PIN` line: the label, the new value, the value before Spec 4b-1, and the family part. A `MOVED` mark means the new value differs from the old one. It also writes `/tmp/kv-t9d/pins.json`, which the edit scripts read, and the date the comments carry.

Every pin that has a part from the other rows gets an automatic `SAME` check: that part, measured now, must equal what it was before. The 229 other exam rows and the 5,600 other pool rows did not change, so it must.

Run:

```bash
mkdir -p /tmp/kv-t9d && cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF' > /tmp/kv-t9d/d3.out 2>&1
import collections
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import textwrap
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
DATE = datetime.date.today().isoformat()          # the day this step runs
OUT = Path(os.environ.get("PINS_OUT", "/tmp/kv-t9d/pins.json"))

# What each pin read before Spec 4b-1 (all rows), and what the 229 exam rows (or the
# 5,600 pool rows) that are not in the shared-origin family read. The second table is
# the SAME check: the non-family part must come out equal to it.
WAS = {
    'exam.job1_n': '120',
    'exam.job2_n': '177',
    'exam.job3_n': '40',
    'exam.job3_shared': '5',
    'exam.job3_none': '35',
    'exam.job2_none_of_these': '8',
    'exam.decoy_rate_n': '128',
    'exam.decoy_offered_n': '157',
    'exam.keyword_graded_n': '169',
    'exam.keyword_derivable_n': '169',
    'exam.counted_kw_job2': '169',
    'exam.all_job2_rows': '144',
    'exam.must_not_job2_plain': '120',
    'exam.must_not_job2_with': '57',
    'exam.always_none_rate': '0.0452',
    'exam.bot.paste.unguarded': '(169, 177)',
    'exam.bot.paste.rate4': '0.9548',
    'exam.bot.echo.unguarded': '(169, 177)',
    'exam.bot.echo.rate4': '0.9548',
    'exam.bot.trim.first_word.wins': '147',
    'exam.bot.trim.first_2_words.wins': '147',
    'exam.bot.trim.first_2_swapped.wins': '153',
    'exam.bot.name_the_decoy.unguarded': '(0, 177)',
    'exam.bot.hedge.board': '{"rate": 0.3446, "n": 177}',
    'exam.bot.hedge.unguarded': '(169, 177)',
    'exam.bot.hedge.rate4': '0.9548',
    'exam.g2.pair': '(30, 0)',
    'exam.trace.fully': '(20, 151)',
    'exam.trace.partly': '(0, 0)',
    'exam.trace.total': '151',
    'exam.trace.not_catalog': '18',
    'exam.retire.level': '169',
    'exam.retire.job2_after': '0.0452',
    'exam.retire.acc_before': '0.5877',
    'exam.retire.acc_after': '0.0321',
    'exam.retire.overconf_before': '105',
    'exam.retire.overconf_after': '241',
    'exam.exposure.other_cases': "{'empty_candidates': 20, 'misattribution_probe': 20, 'multi_misattribution_probe': 40, 'own_cause': 51, 'wrong_attribution': 20}",
    'exam.exposure.graded.probe': '3',
    'exam.exposure.derivable.probe': '3',
    'exam.exposure.graded.decoy': '15',
    'exam.exposure.derivable.decoy': '15',
    'exam.exposure.graded_sum': '169',
    'exam.exposure.derivable_sum': '169',
    'exam.oracle.job1': '(120, 120.0)',
    'exam.weak.keys': '33',
    'exam.weak.pairs_n': '21',
    'exam.weak.non_family_pairs_digest': "'73766aa2f16b0827'",
    'exam.weak.list': "'9400a0203f60ea47'",
    'exam.old_init_keys.board': '{"rate": 0.9322, "n": 177}',
    'exam.old_init_keys.lost': '12',
    'pool.workloads': '13677',
    'pool.job2_workloads': '9426',
    'pool.job2_keyword_graded': '3694',
    'pool.must_not_non_empty': '1084',
    'train.job1_n': '3074',
    'train.job2_gate_n': '3017',
    'train.job2_keyword_only_n': '2766',
    'train.job3.shared': '{"rate": 1.0, "n": 194}',
    'train.job3.separate': '{"rate": 1.0, "n": 13}',
    'train.job3.none': '{"rate": 1.0, "n": 2623}',
    'train.job3_n': '2830',
    'train.multi_job1': '(1207.0, 1207)',
    'val.job1_n': '387',
    'val.job2_gate_n': '326',
    'val.job2_keyword_only_n': '298',
    'val.job3.shared': '{"rate": 1.0, "n": 20}',
    'val.job3.separate': '{"rate": None, "n": 0}',
    'val.job3.none': '{"rate": 1.0, "n": 288}',
    'val.job3_n': '308',
    'val.multi_job1': '(163.0, 163)',
}
OTHER = {
    'exam.job1_n': '90',
    'exam.job2_n': '159',
    'exam.job3_n': '20',
    'exam.job3_shared': '0',
    'exam.job3_none': '20',
    'exam.job2_none_of_these': '8',
    'exam.decoy_rate_n': '119',
    'exam.decoy_offered_n': '139',
    'exam.keyword_graded_n': '151',
    'exam.keyword_derivable_n': '151',
    'exam.counted_kw_job2': '151',
    'exam.all_job2_rows': '139',
    'exam.must_not_job2_plain': '102',
    'exam.must_not_job2_with': '57',
    'exam.always_none_rate': '0.0503',
    'exam.bot.paste.unguarded': '(151, 159)',
    'exam.bot.paste.rate4': '0.9497',
    'exam.bot.echo.unguarded': '(151, 159)',
    'exam.bot.echo.rate4': '0.9497',
    'exam.bot.trim.first_word.wins': '145',
    'exam.bot.trim.first_2_words.wins': '145',
    'exam.bot.trim.first_2_swapped.wins': '151',
    'exam.bot.name_the_decoy.unguarded': '(0, 159)',
    'exam.bot.hedge.board': '{"rate": 0.3082, "n": 159}',
    'exam.bot.hedge.unguarded': '(151, 159)',
    'exam.bot.hedge.rate4': '0.9497',
    'exam.g2.pair': '(30, 0)',
    'exam.trace.fully': '(20, 151)',
    'exam.trace.partly': '(0, 0)',
    'exam.trace.total': '151',
    'exam.trace.not_catalog': '0',
    'exam.retire.level': '151',
    'exam.retire.job2_after': '0.0503',
    'exam.retire.acc_before': '0.607',
    'exam.retire.acc_after': '0.0349',
    'exam.retire.overconf_before': '90',
    'exam.retire.overconf_after': '221',
    'exam.exposure.other_cases': "{'empty_candidates': 20, 'misattribution_probe': 20, 'multi_misattribution_probe': 40, 'own_cause': 51, 'wrong_attribution': 20}",
    'exam.weak.keys': '20',
    'exam.weak.pairs_n': '4',
    'exam.weak.non_family_pairs_digest': "'73766aa2f16b0827'",
    'exam.old_init_keys.lost': '12',
    'pool.workloads': '7671',
    'pool.job2_workloads': '4014',
    'pool.job2_keyword_graded': '3694',
    'pool.must_not_non_empty': '1084',
    'train.job1_n': '2534',
    'train.job2_gate_n': '3017',
    'train.job2_keyword_only_n': '2766',
    'train.job3.shared': '{"rate": None, "n": 0}',
    'train.job3.separate': '{"rate": 1.0, "n": 13}',
    'train.job3.none': '{"rate": 1.0, "n": 639}',
    'train.job3_n': '652',
    'train.multi_job1': '(1207.0, 1207)',
    'val.job1_n': '333',
    'val.job2_gate_n': '326',
    'val.job2_keyword_only_n': '298',
    'val.job3.shared': '{"rate": None, "n": 0}',
    'val.job3.separate': '{"rate": None, "n": 0}',
    'val.job3.none': '{"rate": 1.0, "n": 86}',
    'val.job3_n': '86',
    'val.multi_job1': '(163.0, 163)',
    'DIGEST.pool_other': 'dcfd9a036c4156bac40e',
    'DIGEST.train_other': 'bad0a4d99d60dc1fff8e',
    'DIGEST.val_other': 'd5c222fcab79cf51fd47',
}


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


from kubeagent_verdict.dataset import catalog, generate  # noqa: E402
from kubeagent_verdict.evals import score  # noqa: E402

ts = load("t_score", "tests/test_score.py")
to = load("t_oracle", "tests/test_oracle.py")
tg = load("t_generate", "tests/test_generate.py")
ta = load("t_answer_keys", "tests/test_answer_keys.py")

PINS, FAILED = {}, []


def fam_row(row):
    return row["meta"]["case"].startswith("shared_origin")


def fam_ex(ex):
    return ex.case.startswith("shared_origin")


def check(name, ok, detail=""):
    print(f"{'CHECK ok  ' if ok else 'CHECK FAIL'} {name} {detail}")
    if not ok:
        FAILED.append(name)


def lit(v):
    """Python source for a value. A {"rate", "n"} board keeps double quotes."""
    if isinstance(v, dict) and set(v) == {"rate", "n"}:
        return '{"rate": %r, "n": %r}' % (v["rate"], v["n"])
    return repr(v)


def pin(label, allv, other=None, fam=None, same=True):
    """Record one pinned number. `other` is the part from rows outside the family;
    it must equal what it read before (SAME) unless `same` is False."""
    PINS[label] = {"v": lit(allv), "was": WAS.get(label, "?")}
    moved = "" if lit(allv) == WAS.get(label) else "  MOVED"
    print(f"PIN   {label:40s} = {lit(allv):24s} was {WAS.get(label, '?'):22s} family {lit(fam)}{moved}")
    if other is not None and same:
        check(f"SAME  {label} (non-family part)", lit(other) == OTHER.get(label),
              f"got {lit(other)} want {OTHER.get(label)}")


def three(rows, fn, is_fam=fam_row):
    o = [r for r in rows if not is_fam(r)]
    f = [r for r in rows if is_fam(r)]
    return fn(rows), fn(o), fn(f)


def tri(label, rows, fn, is_fam=fam_row, same=True):
    a, o, f = three(rows, fn, is_fam)
    pin(label, a, o, f, same)
    return a, o, f


def wls(rows, job=None):
    for r in rows:
        for wm in r["meta"]["workloads"].values():
            if job is None or wm.get("job") == job:
                yield wm


def digest(rows):
    """Order-independent: sha256 over the sorted per-row hashes."""
    per = sorted(hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                 for r in rows)
    return hashlib.sha256("".join(per).encode()).hexdigest()[:20]


def board(rows, bot=None):
    return score.scoreboard(score.evaluate(rows, bot(rows) if bot else (lambda m: "")))


# ------------------------------------------------------------------ the exam
exam_ex = generate.test_set()
exam = [generate.to_row(e) for e in exam_ex]

print("== the exam: 249 rows, 229 outside the family and 20 inside ==")
a, o, f = three(exam, len)
check("exam rows are 249 = 229 + 20", (a, o, f) == (249, 229, 20), f"got {(a, o, f)}")
cc = collections.Counter(e.case for e in exam_ex if fam_ex(e))
check("family exam cases are 10 + 10", dict(cc) == {"shared_origin_probe": 10, "shared_origin_decoy_probe": 10},
      f"got {dict(cc)}")
OTHER_FAMILIES_SHA256 = "09de3501feceaab8ec014e7ccc5d187c3d88af50deef63dd030ef9cbaa87895a"  # Task 7's literal
blob = json.dumps([generate.to_row(e) for e in exam_ex if not fam_ex(e)], sort_keys=True, ensure_ascii=False)
check("the 229 non-family exam rows are byte-stable (Task 7's digest)",
      hashlib.sha256(blob.encode("utf-8")).hexdigest() == OTHER_FAMILIES_SHA256)

tri("exam.job1_n", exam, lambda rs: sum(1 for _ in wls(rs, 1)))
tri("exam.job2_n", exam, lambda rs: sum(1 for _ in wls(rs, 2)))
tri("exam.job3_n", exam, lambda rs: sum(1 for r in rs if len(r["meta"]["workloads"]) >= 2))
for lab in ("shared", "none"):
    tri(f"exam.job3_{lab}", exam, lambda rs, lab=lab: sum(
        1 for r in rs if len(r["meta"]["workloads"]) >= 2 and r["meta"]["label"] == lab))
sep = sum(1 for r in exam if len(r["meta"]["workloads"]) >= 2 and r["meta"]["label"] == "separate")
check("no exam row is labelled separate (Ruling 25)", sep == 0, f"got {sep}")
tri("exam.job2_none_of_these", exam, lambda rs: sum(
    1 for wm in wls(rs, 2) if wm["expected_cause"] == score.NONE_OF_THESE))
unkeyed = sum(1 for wm in wls(exam, 2) if wm["expected_cause"] != score.NONE_OF_THESE
              and not wm["own_cause_keywords"])
check("no exam job-2 workload is named without keys", unkeyed == 0, f"got {unkeyed}")
J1, J2 = PINS["exam.job1_n"]["v"], PINS["exam.job2_n"]["v"]

# the decided line
dl_miss = 0
for ex in exam_ex:
    lines = tg._decided_lines(ex.user)
    for key, wm in ex.meta["workloads"].items():
        if wm["job"] == 1:
            dl_miss += not (key in lines and lines[key] == (wm["decided_cause"], wm["decided_outcome"]))
        else:
            dl_miss += key in lines
check("every job-1 exam workload prints its decided line, no job-2 one does", dl_miss == 0, f"misses {dl_miss}")


def gold_board(rs):
    replies = {r["messages"][1]["content"]: r["messages"][2]["content"] for r in rs}
    return score.scoreboard(score.evaluate(rs, lambda m: replies[m[1]["content"]]))


tri("exam.decoy_rate_n", exam, lambda rs: gold_board(rs)["overall"]["decoy_rate"]["n"])
check("the gold reply names no decoy", gold_board(exam)["overall"]["decoy_rate"]["rate"] == 0.0)
tri("exam.decoy_offered_n", exam, lambda rs: sum(
    1 for r in rs for name, wm in r["meta"]["workloads"].items()
    if wm.get("job") == 2 and score._workload_decoys(r["meta"], name)))
tri("exam.keyword_graded_n", exam, lambda rs: board(rs)["overall"]["keyword_graded_n"])
tri("exam.keyword_derivable_n", exam, lambda rs: board(rs)["overall"]["keyword_derivable_n"])
tri("exam.counted_kw_job2", exam, lambda rs: sum(
    1 for wm in wls(rs, 2) if wm.get("expected_cause") != score.NONE_OF_THESE and wm.get("own_cause_keywords")))
tri("exam.all_job2_rows", exam, lambda rs: sum(
    1 for r in rs if r["meta"]["workloads"] and all(w.get("job") == 2 for w in r["meta"]["workloads"].values())))
tri("exam.must_not_job2_plain", exam, lambda rs: sum(1 for wm in wls(rs, 2) if not wm["own_cause_must_not"]))
tri("exam.must_not_job2_with", exam, lambda rs: sum(1 for wm in wls(rs, 2) if wm["own_cause_must_not"]))
check("no exam job-1 workload carries a must-not word", not any(wm["own_cause_must_not"] for wm in wls(exam, 1)))
bad_rows = [r["meta"]["case"] for r, res in zip(exam, score.evaluate(exam, ts._own_keyword_bot(exam)))
            if r["meta"]["workloads"] and all(w.get("job") == 2 for w in r["meta"]["workloads"].values())
            and abs(res["cause_acc"] - sum(res["job2_scores"]) / len(res["job2_scores"])) > 1e-9]
check("cause_acc and the job-2 mean agree on every all-job-2 exam row (the own-keyword bot)",
      bad_rows == [], f"disagree on {bad_rows}")

print("== bots on the exam ==")
nb = board(exam, ts._never_say_shared_bot)["jobs"]["job3"]
check("never-say-shared bot agrees with the label counts",
      (nb["n"], nb["by_label"]["shared"]["n"], nb["by_label"]["none"]["n"], nb["by_label"]["separate"]["n"]) ==
      (eval(PINS["exam.job3_n"]["v"]), eval(PINS["exam.job3_shared"]["v"]),
       eval(PINS["exam.job3_none"]["v"]), 0), f"got {nb}")
check("the exam has a shared row (the bot's shared rate reads 0.0, not None)",
      nb["by_label"]["shared"]["rate"] == 0.0 and nb["by_label"]["none"]["rate"] == 1.0, f"got {nb}")
tri("exam.always_none_rate", exam, lambda rs: board(rs, ts._always_none_of_these_bot)["jobs"]["job2"]["rate"])
ab = board(exam, ts._always_none_of_these_bot)["jobs"]["job2"]
check("always-none rate is none_of_these workloads over job-2 workloads",
      ab["rate"] == round(eval(PINS["exam.job2_none_of_these"]["v"]) / eval(J2), 4), f"got {ab}")
cb = board(exam, ts._regex_copier_bot)["jobs"]
check("regex copier clears every exam job-1 workload and no job-2 one",
      cb["job1"] == {"rate": 1.0, "n": eval(J1)} and cb["job2"] == {"rate": 0.0, "n": eval(J2)}, f"got {cb}")
eb = board(exam, ts._echo_the_decided_cause_bot)["jobs"]
check("echo-the-decided-cause bot clears the job-1 bar and scores 0 on job 2",
      eb["job1"]["rate"] >= score.JOB1_BAR and eb["job2"]["rate"] == 0.0, f"got {eb}")


def guarded(rs, bot):
    return score.scoreboard(score.evaluate(rs, bot(rs)))["jobs"]["job2"]


def unguarded(rs, bot):
    u = ts._unguarded_job2_scores(rs, bot(rs))
    total = round(sum(u), 4)
    return (int(total) if total == int(total) else total, len(u))


def trimmed(trim):
    return lambda rs: ts._trimmed_paste_bot(rs, trim)


for tag, bot in (("paste", ts._paste_the_prompt_bot), ("echo", ts._echo_the_own_entries_bot)):
    tri(f"exam.bot.{tag}.unguarded", exam, lambda rs, bot=bot: unguarded(rs, bot))
    tri(f"exam.bot.{tag}.rate4", exam, lambda rs, bot=bot: round(
        unguarded(rs, bot)[0] / unguarded(rs, bot)[1], 4) if unguarded(rs, bot)[1] else None)
    check(f"the guard zeroes the {tag} bot on every exam row", guarded(exam, bot)["rate"] == 0.0)
for tag, trim in (("first_word", ts._first_word_cut), ("first_2_words", ts._first_2_words_cut),
                  ("first_2_swapped", ts._first_2_words_swapped)):
    tri(f"exam.bot.trim.{tag}.wins", exam, lambda rs, trim=trim: unguarded(rs, trimmed(trim))[0])
    u = unguarded(exam, trimmed(trim))
    check(f"trimmed paste ({tag}) still clears the job-2 bar without the guard",
          u[0] / u[1] >= score.JOB2_BAR, f"got {u}")
    check(f"the guard zeroes trimmed paste ({tag})", guarded(exam, trimmed(trim))["rate"] == 0.0)
tri("exam.bot.name_the_decoy.unguarded", exam, lambda rs: unguarded(rs, ts._name_the_decoy_bot))
check("the guard and no guard both score the name-the-decoy bot 0",
      guarded(exam, ts._name_the_decoy_bot)["rate"] == 0.0
      and unguarded(exam, ts._name_the_decoy_bot)[0] == 0.0)
tri("exam.bot.hedge.board", exam, lambda rs: guarded(rs, ts._hedge_bot))
tri("exam.bot.hedge.unguarded", exam, lambda rs: unguarded(rs, ts._hedge_bot))
tri("exam.bot.hedge.rate4", exam, lambda rs: round(
    unguarded(rs, ts._hedge_bot)[0] / unguarded(rs, ts._hedge_bot)[1], 4) if unguarded(rs, ts._hedge_bot)[1] else None)
check("the hedge bot stays under the job-2 bar with the guard",
      guarded(exam, ts._hedge_bot)["rate"] < score.JOB2_BAR)


def g2(rs):
    bad = zeroed = 0
    for row in rs:
        own = score._own_blocks(row["messages"][1]["content"], row["meta"]["workloads"])
        gold = {v["workload"]: v["cause"] for v in json.loads(row["messages"][2]["content"])["verdicts"]}
        for name, wm in row["meta"]["workloads"].items():
            if wm.get("job") == 2 and gold[name] == ts._BAD_TAG_GOLD:
                bad += 1
                zeroed += score._job2_guarded(ts._BAD_TAG_GOLD + " registry.example.com",
                                              score._workload_decoys(row["meta"], name), own[name])
    return bad, zeroed


tri("exam.g2.pair", exam, g2)
replies = {r["messages"][1]["content"]: json.loads(r["messages"][2]["content"]) for r in exam}


def g2_bot(messages):
    reply = json.loads(json.dumps(replies[messages[1]["content"]]))
    for v in reply["verdicts"]:
        if v["cause"] == ts._BAD_TAG_GOLD:
            v["cause"] = ts._BAD_TAG_GOLD + " registry.example.com"
    return json.dumps(reply)


g2b = score.scoreboard(score.evaluate(exam, g2_bot))["jobs"]["job2"]
check("a right bad-tag answer that names the registry host still scores 1.0", g2b["rate"] == 1.0, f"got {g2b}")

print("== the 20-entry trace and the four retired numbers ==")
declaring = {}
for entry in catalog.all_entries():
    if entry.own_cause_keywords:
        declaring.setdefault(tuple(entry.own_cause_keywords), []).append(entry.key)


def trace(rs):
    exposed, hidden = collections.Counter(), collections.Counter()
    for row in rs:
        prompt = row["messages"][1]["content"].lower()
        for wm in row["meta"]["workloads"].values():
            if not (isinstance(wm, dict) and wm.get("job") == 2):
                continue
            kws = tuple(wm.get("own_cause_keywords") or ())
            if not kws or kws not in declaring:
                continue
            (exposed if all(k.lower() in prompt for k in kws) else hidden)[kws] += 1
    fully, partly, nf, npartly = set(), set(), 0, 0
    for kws, n in exposed.items():
        if hidden.get(kws):
            partly.update(declaring[kws])
            npartly += n
        else:
            fully.update(declaring[kws])
            nf += n
    return (len(fully), nf), (len(partly), npartly), nf + npartly


tri("exam.trace.fully", exam, lambda rs: trace(rs)[0])
tri("exam.trace.partly", exam, lambda rs: trace(rs)[1])
tri("exam.trace.total", exam, lambda rs: trace(rs)[2])
check("no family workload traces to a catalog entry", trace([r for r in exam if fam_row(r)]) == ((0, 0), (0, 0), 0))
tri("exam.trace.not_catalog", exam, lambda rs: board(rs)["overall"]["keyword_derivable_n"] - trace(rs)[2])


def retire(rs):
    bot = ts._own_keyword_bot(rs)
    rewritten, level = ts._rewrite_keyword_answer_keys(rs, "nonexistentkeywordtoken")
    before = score.scoreboard(score.evaluate(rs, bot))
    after = score.scoreboard(score.evaluate(rewritten, bot))
    ob, oa = before["overall"], after["overall"]
    moved = sorted(c for c in before["by_case"] if before["by_case"][c] != after["by_case"][c])
    return {
        "level": level, "derivable_before": ob["keyword_derivable_n"], "derivable_after": oa["keyword_derivable_n"],
        "graded_after": oa["keyword_graded_n"], "job2_before": before["jobs"]["job2"]["rate"],
        "job2_after": after["jobs"]["job2"]["rate"], "acc_before": ob["cause_accuracy"]["rate"],
        "acc_after": oa["cause_accuracy"]["rate"], "oc_before": ob["overconfidence_rate"]["n"],
        "oc_after": oa["overconfidence_rate"]["n"], "lh_before": ob["cause_when_length_helps"],
        "lh_after": oa["cause_when_length_helps"], "gap_before": ob["length_gap"], "gap_after": oa["length_gap"],
        "moved": moved, "job1_same": before["jobs"]["job1"] == after["jobs"]["job1"],
        "job3_same": before["jobs"]["job3"] == after["jobs"]["job3"],
        "rest_same": all(ob[k] == oa[k] for k in ("cause_when_length_misleads", "contract_rate", "decoy_rate",
                                                 "suggestion_echo_rate", "injection_echo_rate",
                                                 "confidence_carried")) and ob["n"] == oa["n"],
    }


R = three(exam, retire)
for label, key in (("exam.retire.level", "level"), ("exam.retire.job2_after", "job2_after"),
                   ("exam.retire.acc_before", "acc_before"), ("exam.retire.acc_after", "acc_after"),
                   ("exam.retire.overconf_before", "oc_before"), ("exam.retire.overconf_after", "oc_after")):
    pin(label, R[0][key], R[1][key], R[2][key])
check("the retired job-2 rate equals the always-none rate (both are the none_of_these share)",
      PINS["exam.retire.job2_after"]["v"] == PINS["exam.always_none_rate"]["v"],
      f"got {PINS['exam.retire.job2_after']['v']} vs {PINS['exam.always_none_rate']['v']}")
check("the non-family cases that move are the five that moved before",
      set(R[1]["moved"]) == {"own_cause", "empty_candidates", "wrong_attribution", "misattribution_probe",
                             "multi_misattribution_probe"}, f"got {R[1]['moved']}")
check("the seven cases that move are the same seven (the test's set stays as it is)",
      set(R[0]["moved"]) == {"own_cause", "empty_candidates", "wrong_attribution", "misattribution_probe",
                             "multi_misattribution_probe", "shared_origin_probe", "shared_origin_decoy_probe"},
      f"got {R[0]['moved']}")
check("the own-keyword bot clears job 2 before the rewrite", R[0]["job2_before"] == 1.0)
check("the derivable count is 0 after the rewrite and the graded count is unchanged",
      R[0]["derivable_after"] == 0 and R[0]["graded_after"] == R[0]["level"] == eval(PINS["exam.keyword_graded_n"]["v"]))
check("the length figures do not move (the family has no length verdicts)",
      (R[0]["lh_before"], R[0]["lh_after"], R[0]["gap_before"], R[0]["gap_after"]) ==
      ({"rate": 0.8333, "n": 48}, {"rate": 0.0, "n": 48}, 0.8333, 0.0), f"got {R[0]['lh_before']} {R[0]['lh_after']}")
check("jobs 1 and 3 and the other overall fields do not move",
      R[0]["job1_same"] and R[0]["job3_same"] and R[0]["rest_same"])

print("== keyword exposure per case ==")
graded, derivable = collections.Counter(), collections.Counter()
for ex, row in zip(exam_ex, exam):
    d, m = score._keyword_exposure(row["meta"], row["messages"][1]["content"])
    if m:
        graded[ex.case] += m
        derivable[ex.case] += d
non_fam = {k: v for k, v in graded.items() if not k.startswith("shared_origin")}
pin("exam.exposure.other_cases", dict(sorted(non_fam.items())), dict(sorted(non_fam.items())))
for case, tag in (("shared_origin_probe", "probe"), ("shared_origin_decoy_probe", "decoy")):
    pin(f"exam.exposure.graded.{tag}", graded.get(case, 0))
    pin(f"exam.exposure.derivable.{tag}", derivable.get(case, 0))
    check(f"{case} has keyword-graded workloads (the pinned dict can name it)", graded.get(case, 0) > 0)
    check(f"every graded {case} workload is derivable", derivable.get(case, 0) == graded.get(case, 0))
pin("exam.exposure.graded_sum", sum(graded.values()))
pin("exam.exposure.derivable_sum", sum(derivable.values()))

print("== the length gap and the decoy cause ==")
res_all = score.evaluate(exam, lambda m: "")
lh = [(fam_row(r), x["length_helps"]) for r, x in zip(exam, res_all) if x["length_helps"] is not None]
check("57 exam rows carry a length verdict and none is a family row",
      (len(lh), sum(1 for f_, _ in lh if f_)) == (57, 0), f"got {(len(lh), sum(1 for f_, _ in lh if f_))}")
named = collections.Counter(e.case for e in exam_ex if e.meta.get("decoy_cause"))
check("no family row names a row-level decoy cause",
      not any(k.startswith("shared_origin") for k in named), f"got {dict(named)}")

print("== the oracle read of the exam ==")
exam_res = to._gold_results(exam_ex)
scores1 = [s for r in exam_res for s in r["job1_scores"]]
misses = [e.case for e, r in zip(exam_ex, exam_res) if sum(r["job1_scores"]) < len(r["job1_scores"])]
pin("exam.oracle.job1", (len(scores1), float(sum(scores1))))
check("the exam oracle misses no job-1 row", misses == [] and sum(scores1) == len(scores1), f"misses {misses}")
ob = score.scoreboard(list(exam_res))["jobs"]
check("the exam oracle reads 1.0 on jobs 2 and 3",
      ob["job2"] == {"rate": 1.0, "n": eval(J2)} and ob["job3"]["rate"] == 1.0, f"got {ob['job2']} {ob['job3']}")
check("the exam oracle job-3 counts agree with the label counts",
      (ob["job3"]["n"], ob["job3"]["by_label"]["shared"]["n"], ob["job3"]["by_label"]["none"]["n"]) ==
      (eval(PINS["exam.job3_n"]["v"]), eval(PINS["exam.job3_shared"]["v"]), eval(PINS["exam.job3_none"]["v"])))

print("== the answer keys on the exam ==")
hold = []
for i, name in ((197, "billing/frontend"), (198, "batch/notifier")):
    wm = exam[i]["meta"]["workloads"].get(name, {})
    hold.append(exam[i]["meta"]["case"] == "multi_misattribution_probe"
                and wm.get("expected_cause") == ta.MEMORY_REQUEST
                and wm.get("own_cause_must_not") == ["cordon", "pressure"])
check("exam rows 197 and 198 are still the two 0920 memory-request workloads", all(hold), f"got {hold}")


def exam_keys(rs):
    keys = set()
    for row in rs:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    return keys


def weak_pairs(keys):
    return sorted({(ca, kwa, cb, kwb) for ca, kwa, mna in keys for cb, kwb, _ in keys
                   if cb != ca and score._keywords_match(cb, kwa, mna)})


keys_all, keys_other = exam_keys(exam), exam_keys([r for r in exam if not fam_row(r)])
fam_only = keys_all - keys_other
pairs_all = weak_pairs(keys_all)
pairs_other = [p for p in pairs_all if not any((p[0], p[1]) == (k[0], k[1]) or (p[2], p[3]) == (k[0], k[1])
                                               for k in fam_only)]
pin("exam.weak.keys", len(keys_all), len(keys_other), len(fam_only))
pin("exam.weak.pairs_n", len(pairs_all), len(pairs_other), len(pairs_all) - len(pairs_other))
pin("exam.weak.non_family_pairs_digest", hashlib.sha256(json.dumps(pairs_other).encode()).hexdigest()[:16],
    hashlib.sha256(json.dumps(pairs_other).encode()).hexdigest()[:16])
old_pairs = [tuple(p) for p in ta.WEAK_PAIRS]
new_pairs = [p for p in pairs_all if p not in old_pairs]
print(f"WEAK  {len(pairs_all)} pairs now, {len(old_pairs)} in the file, {len(new_pairs)} not in the file today")
for p in new_pairs:
    print("WEAK  new:", p)


def weak_literal(pairs):
    """The header comment and the WEAK_PAIRS list, one pair per two lines, grouped by the key
    that accepts the other answers."""
    def text(cause):
        return "MEMORY_REQUEST" if cause == ta.MEMORY_REQUEST else repr(cause)
    out = ["# Every ordered pair of exam answer keys (A, B), with different gold",
           "# sentences, where B's gold passes A's key: (A's cause, A's keywords, B's",
           f"# cause, B's keywords). All {len(pairs)} are left for Spec 4b-4 (the Spec 4b-1 design,",
           "# \"Left for 4b-2, 4b-3 and 4b-4\"). 4b-4 must shrink this list. A change that grows",
           "# it fails here.",
           "WEAK_PAIRS = ["]
    last = None
    for ca, kwa, cb, kwb in pairs:
        if (ca, kwa) != last:
            out.extend(textwrap.wrap(f"The key {kwa} of {ca!r} also passes these other answers:",
                                     width=96, initial_indent="    # ", subsequent_indent="    # ",
                                     break_long_words=False, break_on_hyphens=False))
            last = (ca, kwa)
        out.append(f"    ({text(ca)}, {kwa!r},")
        out.append(f"     {text(cb)}, {kwb!r}),")
    out.append("]")
    return "\n".join(out) + "\n"


pin("exam.weak.list", hashlib.sha256(json.dumps(pairs_all).encode()).hexdigest()[:16])
print("WEAK  the list in the file " + ("is unchanged" if [list(p) for p in old_pairs] == [list(p) for p in pairs_all]
                                       else "must be replaced"))


OUT.parent.mkdir(parents=True, exist_ok=True)
(OUT.parent / "weak_pairs.txt").write_text(weak_literal(pairs_all))

old_init = {("init", "registry", "tag"): ["tag", "registry"], ("init", "tag", "registry"): ["registry", "tag"]}
by_prompt = {r["messages"][1]["content"]: r for r in exam}


def old_init_bot(messages):
    row = by_prompt[messages[1]["content"]]
    verdicts = []
    for name, wm in row["meta"]["workloads"].items():
        kws = old_init.get(tuple(wm["own_cause_keywords"]), wm["own_cause_keywords"])
        verdicts.append({"workload": name, "cause": " ".join(kws) if kws else "none_of_these",
                         "confidence": "high", "rationale": "answers with its own expected keywords"})
    return json.dumps({"verdicts": verdicts, "summary": "see the verdicts above for details"})


oi = score.evaluate(exam, old_init_bot)
oib = score.scoreboard(oi)["jobs"]["job2"]
pin("exam.old_init_keys.board", oib)
lost = eval(J2) - round(sum(sum(r["job2_scores"]) for r in oi))
init_n = sum(1 for r in exam for wm in r["meta"]["workloads"].values()
             if wm["job"] == 2 and tuple(wm["own_cause_keywords"]) in old_init)
init_other = sum(1 for r in exam if not fam_row(r) for wm in r["meta"]["workloads"].values()
                 if wm["job"] == 2 and tuple(wm["own_cause_keywords"]) in old_init)
pin("exam.old_init_keys.lost", lost, init_other, lost - init_other)
check("the workloads the old init keys lose are exactly the workloads on the two init keys",
      lost == init_n, f"lost {lost}, on the two keys {init_n}")

# ------------------------------------------------------------------- the pool
print("== the 8,000-row training pool (seed 17) ==")
pool_ex = generate.generate(17, 8000)
pool = [generate.to_row(e) for e in pool_ex]
a, o, f = three(pool, len)
check("the pool is 8000 rows = 5600 + 2400", (a, o, f) == (8000, 5600, 2400), f"got {(a, o, f)}")
tri("pool.workloads", pool, lambda rs: sum(1 for _ in wls(rs)))
tri("pool.job2_workloads", pool, lambda rs: sum(1 for _ in wls(rs, 2)))
tri("pool.job2_keyword_graded", pool, lambda rs: sum(
    1 for wm in wls(rs, 2) if score._is_job2_keyword_graded(wm, wm["own_cause_keywords"])))
tri("pool.must_not_non_empty", pool, lambda rs: sum(1 for wm in wls(rs) if wm["own_cause_must_not"]))
by_kw = {}
for e in catalog.all_entries():
    if e.own_cause_keywords:
        by_kw.setdefault(e.own_cause_keywords, set()).add(e.own_cause_must_not)
conflicts = [(r["meta"]["case"], tuple(wm["own_cause_keywords"])) for r in pool for wm in r["meta"]["workloads"].values()
             if wm["own_cause_must_not"] != (list(next(iter(by_kw[tuple(wm["own_cause_keywords"])])))
                                             if tuple(wm["own_cause_keywords"]) in by_kw else [])]
check("every pool workload's must-not list is its catalog entry's list or []", conflicts == [],
      f"first {conflicts[:3]}")
zeroed = checked = 0
for row in pool:
    meta = row["meta"]
    own = score._own_blocks(row["messages"][1]["content"], meta["workloads"])
    gold = {v["workload"]: v["cause"] for v in json.loads(row["messages"][2]["content"])["verdicts"]}
    for name, wm in meta["workloads"].items():
        if wm.get("job") == 2:
            checked += 1
            zeroed += bool(score._job2_guarded(gold[name], score._workload_decoys(meta, name), own[name]))
            if score._is_job2_keyword_graded(wm, wm["own_cause_keywords"]):
                zeroed += not score._keywords_match(gold[name], wm["own_cause_keywords"], wm["own_cause_must_not"])
check("the guard and the key accept the gold of every pool job-2 workload", zeroed == 0, f"refused {zeroed}")
check("non-family pool rows are byte-stable", digest([r for r in pool if not fam_row(r)]) == OTHER.get("DIGEST.pool_other"))

train0, val0 = generate.split(pool_ex, seed=17)
train = generate.drop_held_out(train0, exam_ex)
val = generate.drop_held_out(val0, exam_ex)
check("non-family train rows are byte-stable",
      digest([generate.to_row(e) for e in train if not fam_ex(e)]) == OTHER.get("DIGEST.train_other"))
check("non-family val rows are byte-stable",
      digest([generate.to_row(e) for e in val if not fam_ex(e)]) == OTHER.get("DIGEST.val_other"))
print(f"INFO  train {len(train)} rows ({sum(fam_ex(e) for e in train)} family), "
      f"val {len(val)} rows ({sum(fam_ex(e) for e in val)} family)")


def split3(exs, fn):
    return fn(exs), fn([e for e in exs if not fam_ex(e)]), fn([e for e in exs if fam_ex(e)])


def rn(b):
    return {"rate": b["rate"], "n": b["n"]}


for name, exs in (("train", train), ("val", val)):
    res = lambda es: to._gold_results(es, grade_job2=False)  # noqa: E731
    a, o, f = split3(exs, lambda es: score.scoreboard(res(es))["jobs"]["job1"]["n"])
    pin(f"{name}.job1_n", a, o, f)
    check(f"{name} oracle job 1 reads 1.0", score.scoreboard(res(exs))["jobs"]["job1"]["rate"] == 1.0)
    a, o, f = split3(exs, lambda es: to._job2_gate(es)["n"])
    pin(f"{name}.job2_gate_n", a, o, f)
    check(f"{name} oracle job-2 gate reads 1.0", to._job2_gate(exs)["rate"] == 1.0)
    a, o, f = split3(exs, lambda es: to._job2_keyword_only(es)["n"])
    pin(f"{name}.job2_keyword_only_n", a, o, f)
    check(f"{name} oracle job-2 keyword-only reads 1.0", to._job2_keyword_only(exs)["rate"] == 1.0)
    j3 = score.scoreboard(res(exs))["jobs"]["job3"]
    for lab in ("shared", "separate", "none"):
        pin(f"{name}.job3.{lab}", rn(j3["by_label"][lab]),
            rn(score.scoreboard(res([e for e in exs if not fam_ex(e)]))["jobs"]["job3"]["by_label"][lab]),
            rn(score.scoreboard(res([e for e in exs if fam_ex(e)]))["jobs"]["job3"]["by_label"][lab]))
    fam_j3 = score.scoreboard(res([e for e in exs if fam_ex(e)]))["jobs"]["job3"]["by_label"]
    check(f"no shared-origin {name} row is labelled separate (Ruling 25)", fam_j3["separate"]["n"] == 0,
          f"got {fam_j3['separate']['n']}")
    pin(f"{name}.job3_n", j3["n"], score.scoreboard(res([e for e in exs if not fam_ex(e)]))["jobs"]["job3"]["n"],
        score.scoreboard(res([e for e in exs if fam_ex(e)]))["jobs"]["job3"]["n"])
    check(f"{name} oracle job 3 reads 1.0 on every label it has",
          j3["rate"] == 1.0 and all(v["rate"] in (1.0, None) for v in j3["by_label"].values()))
    results = res(exs)
    mj = [x for r in results if r["case"] == "multi" for x in r["job1_scores"]]
    pin(f"{name}.multi_job1", (float(sum(mj)), len(mj)), (float(sum(mj)), len(mj)))
    un = sum(1 for e in exs for wm in generate.to_row(e)["meta"]["workloads"].values()
             if wm["job"] == 2 and wm["expected_cause"] != score.NONE_OF_THESE and not wm["own_cause_keywords"])
    check(f"{name} has no named job-2 workload without keys", un == 0, f"got {un}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"date": DATE, "pins": PINS}, indent=1))
print()
print(f"wrote {OUT} ({len(PINS)} pins, date {DATE})")
print("CHECKS FAILED:", len(FAILED), FAILED if FAILED else "")
sys.exit(1 if FAILED else 0)
EOF
echo "master exit code: $?"
```

Then:

```bash
grep -E '^(INFO|WEAK|CHECK FAIL|CHECKS FAILED|wrote)' /tmp/kv-t9d/d3.out
grep -c '^PIN ' /tmp/kv-t9d/d3.out
grep '^PIN .*MOVED' /tmp/kv-t9d/d3.out
```

Expected: `master exit code: 0`; no `CHECK FAIL` line; `CHECKS FAILED: 0`; `wrote /tmp/kv-t9d/pins.json (71 pins, date <today>)`; the count prints `71`. The `MOVED` lines are the numbers the next steps change. The `WEAK` lines say how many weak pairs there are now, how many the file lists, and (if the list must be replaced) `WEAK  new:` lines naming the pairs that were not there before.

The script takes under a minute. It exits 1 on a tree that has not had Task 7, by design: it measures what Task 7 builds.

**CHECK.** The structural checks, besides the automatic `SAME` ones:

1. The exam has 249 rows: 229 other and 20 family (10 + 10). Task 7's digest holds on the 229.
2. No exam row and no shared-origin train or val row is labelled `separate` (Ruling 25). The `multi` rows keep that label (13 in the train pool), so the train and val pools as a whole still hold it.
3. No named job-2 workload on the exam, train or val is without keys.
4. Every job-1 exam workload prints its decided line, no job-2 one does, and no job-1 workload carries a must-not word.
5. The gold reply names no decoy, and cause accuracy and job 2 agree on every all-job-2 row.
6. The bots behave as the tests say. Never-say-shared agrees with the label counts, and the exam has a `shared` row. The always-none rate equals the share of `none_of_these` workloads. The regex copier and the echo-the-decided-cause bot clear job 1 and score 0 on job 2. The guard zeroes the paste, echo and trimmed-paste bots, while the trimmed pastes clear the bar unguarded. Name-the-decoy scores 0 both ways. The hedge bot stays under the bar guarded. A right bad-tag answer naming the registry host still scores 1.0 (G2).
7. The key rewrite retires the numbers it retired before: the retired job-2 rate equals the always-none rate; the non-family cases that move are the same five, and the cases that move are the same seven; the own-keyword bot clears job 2 before the rewrite; derivable is 0 after it and graded is unchanged; the length figures and the other overall fields do not move.
8. Both family cases have keyword-graded workloads, and every graded one is derivable.
9. 57 exam rows carry a length verdict and none is a family row; no family row names a row-level decoy.
10. The exam oracle misses no job-1 row, reads 1.0 on jobs 2 and 3, and its job-3 counts agree with the labels. Rows 197 and 198 are still the 0920 memory-request workloads.
11. The workloads the old init keys lose are exactly the ones on the two init keys.
12. The pool is 8,000 rows = 5,600 + 2,400. Every pool must-not list is its catalog entry's list or empty. The guard and the key accept the gold of every pool job-2 workload. The non-family pool, train and val rows are byte-stable (digests).
13. The train and val oracles read 1.0 on each job.

On any `CHECK FAIL`: stop, commit nothing, and report DONE_WITH_CONCERNS with the `CHECK FAIL` lines and the `PIN` lines around them. A failed `SAME` check means a row outside the 20 moved: report it, never re-pin it.

- [ ] **Step D4: Create `/tmp/kv-t9d/apply_pins.py`**

**The 71 numbers.** "Today" is the tree before Spec 4b-1: the total, then the part from the other rows and the part from the family rows. Only the family part can move.

| Label | What it counts | Today: all = other + family |
|---|---|---|
| `exam.job1_n` | job-1 workloads on the exam | 120 = 90 + 30 |
| `exam.job2_n` | job-2 workloads on the exam | 177 = 159 + 18 |
| `exam.job3_n` | exam rows with two or more workloads (the job-3 rows) | 40 = 20 + 20 |
| `exam.job3_shared` | job-3 rows labelled `shared` | 5 = 0 + 5 |
| `exam.job3_none` | job-3 rows labelled `none` | 35 = 20 + 15 |
| `exam.job2_none_of_these` | job-2 workloads whose right answer is `none_of_these` | 8 = 8 + 0 |
| `exam.decoy_rate_n` | workloads the decoy-rate figure counts, read off the gold reply | 128 = 119 + 9 |
| `exam.decoy_offered_n` | job-2 workloads that are offered at least one decoy | 157 = 139 + 18 |
| `exam.keyword_graded_n` | job-2 workloads graded by their answer keys (`keyword_graded_n`) | 169 = 151 + 18 |
| `exam.keyword_derivable_n` | of those, the ones whose key words the prompt shows (`keyword_derivable_n`) | 169 = 151 + 18 |
| `exam.counted_kw_job2` | named job-2 workloads that carry key words, counted straight from the rows | 169 = 151 + 18 |
| `exam.all_job2_rows` | rows where every workload is job 2 | 144 = 139 + 5 |
| `exam.must_not_job2_plain` | job-2 workloads with no must-not word | 120 = 102 + 18 |
| `exam.must_not_job2_with` | job-2 workloads with a must-not word | 57 = 57 + 0 |
| `exam.always_none_rate` | job-2 rate of the bot that always says `none_of_these` | 0.0452 over 177 (other 0.0503 over 159; family 0.0 over 18) |
| `exam.bot.paste.unguarded` | paste-the-prompt bot: (job-2 points won, job-2 workloads), no guard | (169, 177) = other (151, 159) + family (18, 18) |
| `exam.bot.paste.rate4` | that win rate, to 4 places | 0.9548 (other 0.9497; family 1.0) |
| `exam.bot.echo.unguarded` | echo-its-own-entries bot: (points won, job-2 workloads), no guard | (169, 177) = other (151, 159) + family (18, 18) |
| `exam.bot.echo.rate4` | that win rate, to 4 places | 0.9548 (other 0.9497; family 1.0) |
| `exam.bot.trim.first_word.wins` | workloads the paste bot with its first word cut still wins, no guard | 147 = 145 + 2 |
| `exam.bot.trim.first_2_words.wins` | same, first two words cut | 147 = 145 + 2 |
| `exam.bot.trim.first_2_swapped.wins` | same, first two words swapped | 153 = 151 + 2 |
| `exam.bot.name_the_decoy.unguarded` | name-the-decoy bot: (points won, job-2 workloads), no guard | (0, 177) = other (0, 159) + family (0, 18) |
| `exam.bot.hedge.board` | hedge bot: the guarded job-2 `{rate, n}` | n 177 = 159 + 18; rate 0.3446 (other 0.3082; family 0.6667) |
| `exam.bot.hedge.unguarded` | hedge bot: (points won, job-2 workloads), no guard | (169, 177) = other (151, 159) + family (18, 18) |
| `exam.bot.hedge.rate4` | that win rate, to 4 places | 0.9548 (other 0.9497; family 1.0) |
| `exam.g2.pair` | (job-2 workloads with the bad-tag gold cause, how many the guard zeroes once the registry host is added) | (30, 0) = other (30, 0) + family (0, 0) |
| `exam.trace.fully` | (catalog entries whose keys every prompt shows, workloads on them) | (20, 151) = other (20, 151) + family (0, 0) |
| `exam.trace.partly` | (catalog entries whose keys only some prompts show, workloads on them) | (0, 0) = other (0, 0) + family (0, 0) |
| `exam.trace.total` | workloads that trace to a catalog entry | 151 = 151 + 0 |
| `exam.trace.not_catalog` | derivable workloads that trace to no catalog entry | 18 = 0 + 18 |
| `exam.retire.level` | workloads still graded after every key is rewritten to a word no reply has | 169 = 151 + 18 |
| `exam.retire.job2_after` | job-2 rate of the own-keyword bot after that rewrite | 0.0452 (other 0.0503; family 0.0) |
| `exam.retire.acc_before` | cause accuracy of that bot before the rewrite | 0.5877 (other 0.607; family 0.3667) |
| `exam.retire.acc_after` | cause accuracy of that bot after the rewrite | 0.0321 (other 0.0349; family 0.0) |
| `exam.retire.overconf_before` | overconfident answers before the rewrite | 105 = 90 + 15 |
| `exam.retire.overconf_after` | overconfident answers after the rewrite | 241 = 221 + 20 |
| `exam.exposure.other_cases` | key-graded workloads in each of the five non-family cases (a guard) | own_cause 51, empty_candidates 20, wrong_attribution 20, misattribution_probe 20, multi_misattribution_probe 40; no family part |
| `exam.exposure.graded.probe` | key-graded workloads in the 10 `shared_origin_probe` rows | 3 (family only) |
| `exam.exposure.derivable.probe` | of those, derivable | 3 (family only) |
| `exam.exposure.graded.decoy` | key-graded workloads in the 10 `shared_origin_decoy_probe` rows | 15 (family only) |
| `exam.exposure.derivable.decoy` | of those, derivable | 15 (family only) |
| `exam.exposure.graded_sum` | key-graded workloads over all seven cases | 169 = 151 (the five other cases) + 18 |
| `exam.exposure.derivable_sum` | derivable workloads over all seven cases | 169 = 151 (the five other cases) + 18 |
| `exam.oracle.job1` | (job-1 workloads, points) the gold-reply oracle scores on the exam | (120, 120.0): 120 = 90 + 30 workloads, every one right |
| `exam.weak.keys` | distinct job-2 answer keys on the exam | 33 = 20 + 13 |
| `exam.weak.pairs_n` | ordered pairs of keys where B's gold passes A's key | 21 = 4 + 17 |
| `exam.weak.non_family_pairs_digest` | fingerprint of the pairs that involve no family key (a guard) | '73766aa2f16b0827' (the 4 other pairs) |
| `exam.weak.list` | fingerprint of the full pair list (decides whether D8 replaces `WEAK_PAIRS`) | '9400a0203f60ea47' (the 21 pairs in the file) |
| `exam.old_init_keys.board` | job-2 `{rate, n}` of a reply built from the old `init` keys | n 177 = 159 + 18; rate 0.9322 |
| `exam.old_init_keys.lost` | job-2 workloads that reply loses | 12 = 12 + 0 |
| `pool.workloads` | workloads in the 8,000-row pool (seed 17) | 13677 = 7671 + 6006 |
| `pool.job2_workloads` | job-2 workloads in the pool | 9426 = 4014 + 5412 |
| `pool.job2_keyword_graded` | key-graded job-2 workloads in the pool | 3694 = 3694 + 0 |
| `pool.must_not_non_empty` | pool workloads with a must-not word | 1084 = 1084 + 0 |
| `train.job1_n` | job-1 workloads in train | 3074 = 2534 + 540 |
| `train.job2_gate_n` | job-2 workloads the gate oracle checks in train | 3017 = 3017 + 0 |
| `train.job2_keyword_only_n` | job-2 workloads the keyword-only oracle checks in train | 2766 = 2766 + 0 |
| `train.job3.shared` | train `shared` rows, `{rate, n}` | n 194 = 0 + 194; rate 1.0 |
| `train.job3.separate` | train `separate` rows, `{rate, n}` | n 13 = 13 + 0; rate 1.0 |
| `train.job3.none` | train `none` rows, `{rate, n}` | n 2623 = 639 + 1984; rate 1.0 |
| `train.job3_n` | train job-3 rows | 2830 = 652 + 2178 |
| `train.multi_job1` | (points, workloads) for `multi` job 1 in train (a guard) | (1207.0, 1207); no family part |
| `val.job1_n` | job-1 workloads in val | 387 = 333 + 54 |
| `val.job2_gate_n` | job-2 workloads the gate oracle checks in val | 326 = 326 + 0 |
| `val.job2_keyword_only_n` | job-2 workloads the keyword-only oracle checks in val (a guard) | 298 = 298 + 0 |
| `val.job3.shared` | val `shared` rows, `{rate, n}` | n 20 = 0 + 20; rate 1.0 |
| `val.job3.separate` | val `separate` rows, `{rate, n}` | n 0 = 0 + 0; rate None |
| `val.job3.none` | val `none` rows, `{rate, n}` | n 288 = 86 + 202; rate 1.0 |
| `val.job3_n` | val job-3 rows | 308 = 86 + 222 |
| `val.multi_job1` | (points, workloads) for `multi` job 1 in val (a guard) | (163.0, 163); no family part |

Six of these edit nothing on their own. They are guards, or they decide a later step: `exam.exposure.other_cases` (the five non-family cases of the per-case exposure test), `exam.weak.non_family_pairs_digest`, `train.multi_job1` and `val.multi_job1` (the `multi` numbers a kept oracle test pins), `val.job2_keyword_only_n`, and `exam.weak.list` (it only decides whether Step D8 replaces `WEAK_PAIRS`). The other 65 each feed one or more of the 34 tests; the tables in Steps D5-D8 name them.

The edit scripts in D5-D8 share one helper. It reads `/tmp/kv-t9d/pins.json`, fills in `@@label@@` (the new number) and `@@was:label@@` (the old one), puts the dated comment above each changed line, and writes each file once at the end. A pin whose number did not move is skipped, and the skip is printed. If an old text is missing or a label has no pin, it stops with a message and writes nothing.

```bash
mkdir -p /tmp/kv-t9d && cat > /tmp/kv-t9d/apply_pins.py <<'EOF'
"""Applies the Spec 4b-1 re-pins to one test file.

The measured numbers come from the master step (PINS_IN, default /tmp/kv-t9d/pins.json). A
file step opens a file, lists its edits, and saves once at the end, so a step that fails part
way leaves the file as it was.

    from apply_pins import Edit
    ed = Edit("tests/test_score.py")
    ed.E("test_x", old, new, was="@@was:exam.job2_n@@")    # one dated comment above the line
    ed.doc("test_x", "text", labels=["exam.job2_n"])       # one dated paragraph in the docstring
    ed.rename("test_x_177", "test_x_@@exam.job2_n@@")      # last edit for that function
    ed.save()

Placeholders in `new`, `was`, `text` and a rename template:
    @@label@@       the number measured now (the master step prints and stores it)
    @@was:label@@   the number the test pinned before
A tuple pin also gives label.0, label.1, ... and a {"rate", "n"} pin gives label.rate, label.n.

An edit whose new text equals its old text is skipped: that pin did not move. `old` must still
occur exactly once inside the function, skipped or not, so a typo in `old` is always caught.
"""
import ast
import json
import os
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(os.environ.get("APPLY_ROOT", Path.cwd()))
_data = json.loads(Path(os.environ.get("PINS_IN", "/tmp/kv-t9d/pins.json")).read_text())
DATE = _data["date"]
KINDS = {
    "exam": "the 20 shared-origin exam rows were rebuilt on real lines",
    "pool": "the shared-origin rows of the training pool were rebuilt on real lines",
}
PINS = {}
for _label, _p in _data["pins"].items():
    PINS[_label] = dict(_p)
    try:
        _v, _w = ast.literal_eval(_p["v"]), ast.literal_eval(_p["was"])
    except (ValueError, SyntaxError):
        continue
    if isinstance(_v, (tuple, list)) and isinstance(_w, (tuple, list)) and len(_v) == len(_w):
        for _i, (_a, _b) in enumerate(zip(_v, _w)):
            PINS[f"{_label}.{_i}"] = {"v": repr(_a), "was": repr(_b)}
    if isinstance(_v, dict) and isinstance(_w, dict) and set(_v) == set(_w):
        for _k in _v:
            PINS[f"{_label}.{_k}"] = {"v": repr(_v[_k]), "was": repr(_w[_k])}

_SUB = re.compile(r"@@(was:)?([A-Za-z0-9_.]+)@@")


def sub(text):
    def one(m):
        if m.group(2) not in PINS:
            raise SystemExit(f"no pin called {m.group(2)!r} in the master's output")
        return PINS[m.group(2)]["was" if m.group(1) else "v"]
    return _SUB.sub(one, text)


def moved(labels):
    return any(PINS[label]["v"] != PINS[label]["was"] for label in labels)


class Edit:
    def __init__(self, rel):
        self.rel, self.path = rel, ROOT / rel
        self.src = self.path.read_text()
        self.alias, self.applied, self.skipped = {}, [], []

    def _span(self, func):
        func = self.alias.get(func, func)
        for n in ast.parse(self.src).body:
            if isinstance(n, ast.FunctionDef) and n.name == func:
                first = min([n.lineno] + [d.lineno for d in n.decorator_list])
                return n, first - 1, n.end_lineno
        raise SystemExit(f"{self.rel}: no top-level function {func}")

    def _check(self):
        try:
            ast.parse(self.src)
        except SyntaxError as err:
            raise SystemExit(f"{self.rel}: the edit left a syntax error: {err}")

    def E(self, func, old, new, was=None, kind="exam", note=None):
        node, s, e = self._span(func)
        lines = self.src.split("\n")
        body = "\n".join(lines[s:e])
        if body.count(old) != 1:
            raise SystemExit(f"{self.rel}::{func}: the old text occurs {body.count(old)} times, "
                             f"want 1:\n{old}")
        new_text = sub(new)
        if new_text == old:
            self.skipped.append(func)
            return
        at = body.index(old)
        first_line = body.count("\n", 0, at)
        head = lines[s + first_line]
        indent = head[: len(head) - len(head.lstrip())]
        new_body = (body[:at] + new_text + body[at + len(old):]).split("\n")
        text = note or (f"{KINDS[kind]}; was {sub(was)}." if was is not None else None)
        if text is not None:
            note_lines = textwrap.fill(f"{DATE} (Spec 4b-1): {text}", width=100,
                                       initial_indent=indent + "# ", subsequent_indent=indent + "# ",
                                       break_long_words=False, break_on_hyphens=False).split("\n")
            new_body[first_line:first_line] = note_lines
        lines[s:e] = new_body
        self.src = "\n".join(lines)
        self._check()
        self.applied.append(func)

    def doc(self, func, text, labels=(), kind="exam", lead=True):
        if labels and not moved(labels):
            self.skipped.append(func + " (docstring)")
            return
        node, s, e = self._span(func)
        ds = node.body[0]
        if not (isinstance(ds, ast.Expr) and isinstance(ds.value, ast.Constant)
                and isinstance(ds.value.value, str)):
            raise SystemExit(f"{self.rel}::{func} has no docstring")
        indent = " " * ds.col_offset
        para = f"{DATE} (Spec 4b-1): " + (f"{KINDS[kind]}. " if lead else "") + sub(text)
        para_lines = textwrap.fill(para, width=100, initial_indent=indent, subsequent_indent=indent,
                                   break_long_words=False, break_on_hyphens=False).split("\n")
        lines = self.src.split("\n")
        last = lines[ds.end_lineno - 1]
        if last.strip() == '"""':
            lines[ds.end_lineno - 1:ds.end_lineno - 1] = ["", *para_lines]
        else:
            assert last.endswith('"""'), (func, last)
            lines[ds.end_lineno - 1] = last[:-3].rstrip()
            para_lines[-1] += '"""'
            lines[ds.end_lineno:ds.end_lineno] = ["", *para_lines]
        self.src = "\n".join(lines)
        self._check()
        self.applied.append(func + " (docstring)")

    def rename(self, func, template, why=None):
        new = sub(template)
        if new == func:
            self.skipped.append(func + " (name)")
            return
        if not new.isidentifier():
            raise SystemExit(f"{new!r} is not a function name")
        node, s, e = self._span(func)
        lines = self.src.split("\n")
        head = lines[node.lineno - 1]
        assert head.startswith(f"def {func}("), head
        lines[node.lineno - 1] = head.replace(f"def {func}(", f"def {new}(", 1)
        self.src = "\n".join(lines)
        self._check()
        self.alias[func] = new
        text = why or f"Renamed from `{func}`: the numbers in its name moved."
        ds = node.body[0]
        if isinstance(ds, ast.Expr) and isinstance(ds.value, ast.Constant) \
                and isinstance(ds.value.value, str):
            self.doc(new, text, lead=False)
        else:
            node, s, e = self._span(new)
            lines = self.src.split("\n")
            note = textwrap.fill(f"{DATE} (Spec 4b-1): {text}", width=100, initial_indent="# ",
                                 subsequent_indent="# ", break_long_words=False,
                                 break_on_hyphens=False).split("\n")
            lines[s:s] = note
            self.src = "\n".join(lines)
            self._check()
        self.applied.append(func + " (name)")

    def replace_region(self, start_marker, end_marker, new_text, note):
        """Swap the text from the line holding start_marker up to and including the line holding
        end_marker for new_text, and put a dated comment above it."""
        lines = self.src.split("\n")
        a = [i for i, ln in enumerate(lines) if ln.startswith(start_marker)]
        if len(a) != 1:
            raise SystemExit(f"{self.rel}: start marker {start_marker!r} found {len(a)} times")
        b = [i for i, ln in enumerate(lines) if i > a[0] and ln.startswith(end_marker)]
        if not b:
            raise SystemExit(f"{self.rel}: end marker {end_marker!r} not found")
        note_lines = textwrap.fill(f"{DATE} (Spec 4b-1): {sub(note)}", width=100, initial_indent="# ",
                                   subsequent_indent="# ", break_long_words=False,
                                   break_on_hyphens=False).split("\n")
        lines[a[0]:b[0] + 1] = [*note_lines, *new_text.rstrip("\n").split("\n")]
        self.src = "\n".join(lines)
        self._check()
        self.applied.append(f"region {start_marker!r}")

    def save(self):
        compile(self.src, str(self.path), "exec")
        if "@@" in self.src:
            raise SystemExit(f"{self.rel}: a placeholder is still in the text")
        self.path.write_text(self.src)
        print(f"{self.rel}: {len(self.applied)} edits applied, {len(self.skipped)} skipped "
              f"because their number did not move")
        for what in self.applied:
            print("  applied", what)
        for what in self.skipped:
            print("  skipped", what)
EOF
```

Run:

```bash
cd /tmp/kv-t9d && /home/ubuntu/git/kubeagent-verdict/.venv/bin/python -c "
import apply_pins
print(len(apply_pins._data['pins']), 'pins,', len(apply_pins.PINS), 'names, date', apply_pins.DATE)"
```

Expected: `71 pins, 112 names, date <the day D3 ran>`. The 112 names are the 71 pins plus the parts of the tuple and `{rate, n}` pins (`exam.g2.pair.0`, `train.job3.shared.n` and so on).

- [ ] **Step D5: Run the score edit script**

Each edit script below is run once. If one must be run again, first restore its file with `git checkout -- <file>` and redo D2 (for `tests/test_score.py`) and the step. Do not patch a script to make it pass: a `SystemExit` message means the plan and the file disagree, so stop and report.

Sixteen tests, each in the table. The two bold ones are edited even when no number moves: the name-the-decoy test gets its new `offered` count, and the trace test gets its updated comments and docstring.

| Test (today's line) | Pins it reads | What changes |
|---|---|---|
| `test_the_gold_reply_names_no_decoy_on_any_exam_row` (:1499) | `exam.decoy_rate_n` | The `n` of the decoy rate in the assert; a docstring paragraph. |
| `test_the_footnote_counts_the_corpus_job2_keyword_population` (:1916) | `exam.keyword_graded_n`, `exam.keyword_derivable_n`, `exam.counted_kw_job2` | Three counts (graded, derivable, counted); a docstring paragraph. |
| `test_empty_reply_bot_scores_zero_on_every_job_with_full_n` (:2367) | `exam.job1_n`, `exam.job2_n` | The job-1 and job-2 workload counts. |
| `test_never_say_shared_bot_scores_35_of_40_on_job3` (:2481) | `exam.job3_n`, `exam.job3_none`, `exam.job3_shared` | Four job-3 numbers (n, the none/n rate, shared n, none n); the helper docstring (`_never_say_shared_bot`); renamed if the two numbers in the name move. |
| `test_a_regex_copier_scores_the_job1_ceiling_the_model_card_states` (:2545) | `exam.job1_n`, `exam.job2_n` | The job-1 and job-2 `n` in the board. |
| `test_always_none_of_these_bot_scores_well_under_the_job2_bar` (:2600) | `exam.job2_n`, `exam.always_none_rate`, `exam.job2_none_of_these` | The rate in the `approx`; a docstring paragraph. The tolerance does not move. |
| `test_the_grader_guard_zeroes_a_bot_that_pastes_the_prompt` (:2711) | `exam.keyword_graded_n`, `exam.keyword_derivable_n`, `exam.job2_n`, `exam.bot.paste.unguarded`, `exam.bot.paste.rate4` | Derivable, graded and job-2 counts; the unguarded pair; the 4-place rate; a docstring paragraph. |
| `test_the_grader_guard_zeroes_a_bot_that_echoes_its_own_entries` (:2878) | `exam.job2_n`, `exam.bot.echo.unguarded`, `exam.bot.echo.rate4` | The job-2 `n`; the unguarded pair; the 4-place rate; a docstring paragraph. |
| `test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut` (:3009) | `exam.job2_n`, `exam.bot.trim.first_2_words.wins`, `exam.bot.trim.first_word.wins`, `exam.bot.trim.first_2_swapped.wins` | The three win counts in the table; the job-2 `n` twice; a docstring paragraph. |
| `test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2` (:3039) | `exam.job2_n`, `exam.g2.pair` | The (bad-tag, zeroed) pair; the job-2 `n`; a docstring paragraph. |
| `test_a_bot_that_names_the_decoy_scores_zero_on_job2_with_or_without_the_guard` (:3115) | `exam.job2_n`, `exam.decoy_offered_n`, `exam.bot.name_the_decoy.unguarded` | **Edited even if no number moves.** The `(0, n)` pair and the board `n`; a NEW count of workloads that were offered a decoy, with a comment saying why; a docstring paragraph. The bot it runs is the one Step D2 rewrote. |
| `test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy` (:3167) | `exam.job2_n`, `exam.bot.hedge.board`, `exam.bot.hedge.unguarded`, `exam.bot.hedge.rate4` | The guarded board; the unguarded pair; the 4-place rate; a docstring paragraph. |
| `test_the_gold_answer_passes_the_grader_guard_on_every_training_pool_job2_workload` (:3277) | `pool.job2_workloads` | The `checked` count (pool job-2 workloads); a docstring paragraph. |
| `test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row` (:3332) | `exam.all_job2_rows` | The `checked` count (rows where every workload is job 2); a docstring paragraph. |
| `test_the_exposed_workloads_trace_back_to_twenty_catalog_entries` (:3413) | `exam.keyword_derivable_n`, `exam.trace.fully`, `exam.trace.partly`, `exam.trace.total`, `exam.trace.not_catalog` | **Edited even if no number moves.** The `continue` comment (no longer `propagation.py`: the keys come from `stories.py`); the fully, partly and total counts; the scoreboard comment; the derivable count; a docstring paragraph. |
| `test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest` (:3534) | `exam.keyword_graded_n`, `exam.keyword_derivable_n`, `exam.retire.level`, `exam.retire.job2_after`, `exam.retire.acc_before`, `exam.retire.acc_after`, `exam.retire.overconf_before`, `exam.retire.overconf_after` | Eight numbers: level, derivable, graded, the retired job-2 rate, cause accuracy before and after, overconfidence before and after; a docstring paragraph. The set of seven cases and the length figures stay. |

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import sys

sys.path.insert(0, "/tmp/kv-t9d")
from apply_pins import DATE, Edit  # noqa: E402

ed = Edit("tests/test_score.py")

# --- the decoy rate -------------------------------------------------------------------------
F = "test_the_gold_reply_names_no_decoy_on_any_exam_row"
ed.E(F, '"decoy_rate"] == {"rate": 0.0, "n": 128}',
     '"decoy_rate"] == {"rate": 0.0, "n": @@exam.decoy_rate_n@@}',
     was="@@was:exam.decoy_rate_n@@")
ed.doc(F, "The exam now has @@exam.decoy_rate_n@@ job-2 workloads that carry a decoy, was "
          "@@was:exam.decoy_rate_n@@. The gold reply still names none of them.",
       labels=["exam.decoy_rate_n"])

# --- the footnote ---------------------------------------------------------------------------
F = "test_the_footnote_counts_the_corpus_job2_keyword_population"
ed.E(F, 'assert board["overall"]["keyword_graded_n"] == 169',
     'assert board["overall"]["keyword_graded_n"] == @@exam.keyword_graded_n@@',
     was="@@was:exam.keyword_graded_n@@")
ed.E(F, 'assert board["overall"]["keyword_derivable_n"] == 169',
     'assert board["overall"]["keyword_derivable_n"] == @@exam.keyword_derivable_n@@',
     was="@@was:exam.keyword_derivable_n@@")
ed.E(F, "assert counted == 169", "assert counted == @@exam.counted_kw_job2@@",
     was="@@was:exam.counted_kw_job2@@")
ed.doc(F, "@@was:exam.keyword_derivable_n@@ of @@was:exam.keyword_graded_n@@ becomes "
          "@@exam.keyword_derivable_n@@ of @@exam.keyword_graded_n@@. The new shared-origin "
          "workloads carry the keys of their story's answer, and every key sits in a line "
          "of the workload's own prompt, so the two counts agree.",
       labels=["exam.keyword_graded_n", "exam.keyword_derivable_n", "exam.counted_kw_job2"])

# --- the empty-reply bot --------------------------------------------------------------------
F = "test_empty_reply_bot_scores_zero_on_every_job_with_full_n"
ed.E(F, "assert expected_job1_n == 120", "assert expected_job1_n == @@exam.job1_n@@",
     was="@@was:exam.job1_n@@")
ed.E(F, "assert expected_job2_n == 177", "assert expected_job2_n == @@exam.job2_n@@",
     was="@@was:exam.job2_n@@")

# --- the never-say-shared bot ---------------------------------------------------------------
F = "test_never_say_shared_bot_scores_35_of_40_on_job3"
ed.E(F, 'assert board["jobs"]["job3"]["n"] == 40',
     'assert board["jobs"]["job3"]["n"] == @@exam.job3_n@@', was="@@was:exam.job3_n@@")
ed.E(F, 'assert board["jobs"]["job3"]["rate"] == round(35 / 40, 4)',
     'assert board["jobs"]["job3"]["rate"] == round(@@exam.job3_none@@ / @@exam.job3_n@@, 4)',
     was="@@was:exam.job3_none@@ / @@was:exam.job3_n@@")
ed.E(F, 'assert board["jobs"]["job3"]["by_label"]["shared"]["n"] == 5',
     'assert board["jobs"]["job3"]["by_label"]["shared"]["n"] == @@exam.job3_shared@@',
     was="@@was:exam.job3_shared@@")
ed.E(F, 'assert board["jobs"]["job3"]["by_label"]["none"]["n"] == 35',
     'assert board["jobs"]["job3"]["by_label"]["none"]["n"] == @@exam.job3_none@@',
     was="@@was:exam.job3_none@@")
ed.doc("_never_say_shared_bot",
       "The exam is now @@exam.job3_shared@@ shared / 0 separate / @@exam.job3_none@@ none of "
       "@@exam.job3_n@@, so this bot's job3 rate is @@exam.job3_none@@/@@exam.job3_n@@. "
       "Was @@was:exam.job3_shared@@ shared / 0 separate / @@was:exam.job3_none@@ none of "
       "@@was:exam.job3_n@@.",
       labels=["exam.job3_n", "exam.job3_shared", "exam.job3_none"])
# The name carries the numbers, so it moves with them. Last edit for this function.
ed.rename(F, "test_never_say_shared_bot_scores_@@exam.job3_none@@_of_@@exam.job3_n@@_on_job3",
          why="Renamed from `test_never_say_shared_bot_scores_35_of_40_on_job3`: the numbers in "
              "its name moved.")

# --- the regex copier -----------------------------------------------------------------------
F = "test_a_regex_copier_scores_the_job1_ceiling_the_model_card_states"
ed.E(F, 'assert board["jobs"]["job1"] == {"rate": 1.0, "n": 120}',
     'assert board["jobs"]["job1"] == {"rate": 1.0, "n": @@exam.job1_n@@}',
     was="@@was:exam.job1_n@@")
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 0.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")

# --- the always-none bot --------------------------------------------------------------------
F = "test_always_none_of_these_bot_scores_well_under_the_job2_bar"
ed.E(F, 'pytest.approx(0.0452, abs=0.005)', 'pytest.approx(@@exam.always_none_rate@@, abs=0.005)',
     was="@@was:exam.always_none_rate@@")
ed.doc(F, "Job 2 counts @@exam.job2_n@@ workloads and @@exam.job2_none_of_these@@ of them expect "
          "`none_of_these`, so this bot scores @@exam.job2_none_of_these@@/@@exam.job2_n@@ = "
          "@@exam.always_none_rate@@. The tolerance and the bar do not move.",
       labels=["exam.job2_n", "exam.job2_none_of_these", "exam.always_none_rate"])

# --- the paste bot --------------------------------------------------------------------------
F = "test_the_grader_guard_zeroes_a_bot_that_pastes_the_prompt"
ed.E(F, 'assert board["overall"]["keyword_derivable_n"] == 169',
     'assert board["overall"]["keyword_derivable_n"] == @@exam.keyword_derivable_n@@',
     was="@@was:exam.keyword_derivable_n@@")
ed.E(F, 'assert board["overall"]["keyword_graded_n"] == 169',
     'assert board["overall"]["keyword_graded_n"] == @@exam.keyword_graded_n@@',
     was="@@was:exam.keyword_graded_n@@")
ed.E(F, 'assert board["jobs"]["job2"]["n"] == 177',
     'assert board["jobs"]["job2"]["n"] == @@exam.job2_n@@', was="@@was:exam.job2_n@@")
ed.E(F, "assert (sum(unguarded), len(unguarded)) == (169, 177)",
     "assert (sum(unguarded), len(unguarded)) == @@exam.bot.paste.unguarded@@",
     was="@@was:exam.bot.paste.unguarded@@")
ed.E(F, "assert round(sum(unguarded) / len(unguarded), 4) == 0.9548",
     "assert round(sum(unguarded) / len(unguarded), 4) == @@exam.bot.paste.rate4@@",
     was="@@was:exam.bot.paste.rate4@@")
ed.doc(F, "Job 2 counts @@exam.job2_n@@ workloads and @@exam.keyword_graded_n@@ of them are "
          "graded and exposed. With no guard this bot scores "
          "@@exam.bot.paste.unguarded.0@@/@@exam.bot.paste.unguarded.1@@ = "
          "@@exam.bot.paste.rate4@@. The guarded rate is still 0.0.",
       labels=["exam.job2_n", "exam.keyword_graded_n", "exam.bot.paste.unguarded",
               "exam.bot.paste.rate4"])

# --- the echo bot ---------------------------------------------------------------------------
F = "test_the_grader_guard_zeroes_a_bot_that_echoes_its_own_entries"
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 0.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")
ed.E(F, "assert (sum(unguarded), len(unguarded)) == (169, 177)",
     "assert (sum(unguarded), len(unguarded)) == @@exam.bot.echo.unguarded@@",
     was="@@was:exam.bot.echo.unguarded@@")
ed.E(F, "assert round(sum(unguarded) / len(unguarded), 4) == 0.9548",
     "assert round(sum(unguarded) / len(unguarded), 4) == @@exam.bot.echo.rate4@@",
     was="@@was:exam.bot.echo.rate4@@")
ed.doc(F, "The echo wins @@exam.bot.echo.unguarded.0@@ of the @@exam.bot.echo.unguarded.1@@ "
          "job-2 workloads unguarded: @@exam.bot.echo.rate4@@. Guarded it is still 0.0.",
       labels=["exam.bot.echo.unguarded", "exam.bot.echo.rate4"])

# --- the trimmed paste bots -----------------------------------------------------------------
F = "test_the_grader_guard_zeroes_a_paste_with_the_first_words_cut"
ed.E(F, "    (_first_word_cut, 147),\n    (_first_2_words_cut, 147),\n"
        "    (_first_2_words_swapped, 153),",
     "    (_first_word_cut, @@exam.bot.trim.first_word.wins@@),\n"
     "    (_first_2_words_cut, @@exam.bot.trim.first_2_words.wins@@),\n"
     "    (_first_2_words_swapped, @@exam.bot.trim.first_2_swapped.wins@@),",
     was="@@was:exam.bot.trim.first_word.wins@@, @@was:exam.bot.trim.first_2_words.wins@@ and "
         "@@was:exam.bot.trim.first_2_swapped.wins@@")
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 0.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")
ed.E(F, "assert (sum(unguarded), len(unguarded)) == (unguarded_wins, 177)",
     "assert (sum(unguarded), len(unguarded)) == (unguarded_wins, @@exam.job2_n@@)",
     was="@@was:exam.job2_n@@")
ed.doc(F, "Unguarded the three bots win @@exam.bot.trim.first_word.wins@@, "
          "@@exam.bot.trim.first_2_words.wins@@ and @@exam.bot.trim.first_2_swapped.wins@@ of "
          "@@exam.job2_n@@. The guard zeroes all of them: 0 of @@exam.job2_n@@.",
       labels=["exam.bot.trim.first_word.wins", "exam.bot.trim.first_2_words.wins",
               "exam.bot.trim.first_2_swapped.wins", "exam.job2_n"])

# --- the registry host (G2) -----------------------------------------------------------------
F = "test_a_right_bad_tag_answer_that_names_the_registry_host_passes_g2"
ed.E(F, "assert (bad_tag, zeroed) == (30, 0)",
     "assert (bad_tag, zeroed) == @@exam.g2.pair@@", was="@@was:exam.g2.pair@@")
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 1.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 1.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")
ed.doc(F, "@@exam.g2.pair.0@@ of the @@exam.job2_n@@ job-2 workloads have the gold bad-tag "
          "cause, and G2 zeroes @@exam.g2.pair.1@@ of them when the host is added. The gold "
          "reply with the host added scores @@exam.job2_n@@ of @@exam.job2_n@@.",
       labels=["exam.g2.pair", "exam.job2_n"])

# --- the name-the-decoy bot (its fallback was rewritten in step D2) -------------------------
F = "test_a_bot_that_names_the_decoy_scores_zero_on_job2_with_or_without_the_guard"
T = "assert (sum(unguarded), len(unguarded)) == (0, 177)"
ed.E(F, T,
     T + "\n"
     f"    # {DATE} (Spec 4b-1): the bot's fallback is `(no decoy offered)` now, never\n"
     "    # `none_of_these`, so 0.0 only means something if decoys were on offer. Count them.\n"
     "    offered = sum(1 for r in rows for name, wm in r[\"meta\"][\"workloads\"].items()\n"
     "                  if wm.get(\"job\") == 2 and score._workload_decoys(r[\"meta\"], name))\n"
     "    assert offered == @@exam.decoy_offered_n@@")
ed.E(F, T, "assert (sum(unguarded), len(unguarded)) == @@exam.bot.name_the_decoy.unguarded@@",
     was="@@was:exam.bot.name_the_decoy.unguarded@@")
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 0.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")
ed.doc(F, "Job 2 counts @@exam.job2_n@@, the bot is offered a decoy on "
          "@@exam.decoy_offered_n@@ of those workloads, and the rate is still 0.0 both ways. "
          "A workload with no decoy gets `(no decoy offered)`, which is never right; it used "
          "to get `none_of_these`, which a rebuilt workload can expect.")

# --- the hedge bot --------------------------------------------------------------------------
F = "test_the_grader_guard_zeroes_a_hedge_between_the_cause_and_a_decoy"
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.3446, "n": 177}',
     'assert board["jobs"]["job2"] == @@exam.bot.hedge.board@@',
     was="@@was:exam.bot.hedge.board@@")
ed.E(F, "assert (sum(unguarded), len(unguarded)) == (169, 177)",
     "assert (sum(unguarded), len(unguarded)) == @@exam.bot.hedge.unguarded@@",
     was="@@was:exam.bot.hedge.unguarded@@")
ed.E(F, "assert round(sum(unguarded) / len(unguarded), 4) == 0.9548",
     "assert round(sum(unguarded) / len(unguarded), 4) == @@exam.bot.hedge.rate4@@",
     was="@@was:exam.bot.hedge.rate4@@")
ed.doc(F, "Job 2 counts @@exam.job2_n@@. Unguarded the hedge wins "
          "@@exam.bot.hedge.unguarded.0@@ of them, @@exam.bot.hedge.rate4@@. Guarded it reads "
          "@@exam.bot.hedge.board.rate@@, still under the job-2 bar.",
       labels=["exam.job2_n", "exam.bot.hedge.board", "exam.bot.hedge.unguarded",
               "exam.bot.hedge.rate4"])

# --- the training pool's gold guard ---------------------------------------------------------
F = "test_the_gold_answer_passes_the_grader_guard_on_every_training_pool_job2_workload"
ed.E(F, "assert checked == 9426", "assert checked == @@pool.job2_workloads@@",
     kind="pool", was="@@was:pool.job2_workloads@@")
ed.doc(F, "The pool now holds @@pool.job2_workloads@@ job-2 golds (was "
          "@@was:pool.job2_workloads@@), and the guard zeroes none of them.",
       kind="pool", labels=["pool.job2_workloads"])

# --- cause accuracy against job 2 -----------------------------------------------------------
F = "test_cause_accuracy_and_job2_agree_on_every_all_job2_exam_row"
ed.E(F, "assert checked == 144", "assert checked == @@exam.all_job2_rows@@",
     was="@@was:exam.all_job2_rows@@")
ed.doc(F, "@@exam.all_job2_rows@@ rows are checked now (was @@was:exam.all_job2_rows@@).",
       labels=["exam.all_job2_rows"])

# --- the trace to catalog entries -----------------------------------------------------------
F = "test_the_exposed_workloads_trace_back_to_twenty_catalog_entries"
ed.E(F, "continue  # not a catalog entry -- an eval-only (propagation.py) pair",
     "continue  # not a catalog entry -- a shared-origin story's key (stories.py)",
     note="the shared-origin workloads' keys come from the stories now, not from "
          "`propagation.py`. No catalog count moves.")
ed.E(F, "assert (len(fully), n_fully) == (20, 151)",
     "assert (len(fully), n_fully) == @@exam.trace.fully@@", was="@@was:exam.trace.fully@@")
ed.E(F, "assert (len(partly), n_partly) == (0, 0)",
     "assert (len(partly), n_partly) == @@exam.trace.partly@@", was="@@was:exam.trace.partly@@")
ed.E(F, "assert n_fully + n_partly == 151", "assert n_fully + n_partly == @@exam.trace.total@@",
     was="@@was:exam.trace.total@@")
ed.E(F, "    # The scoreboard's total is bigger now: the catalog's 151 plus the 18\n"
        "    # eval-origin workloads this test deliberately does not count above.",
     "    # The scoreboard's total is bigger now: the catalog's @@exam.trace.total@@ plus the\n"
     "    # @@exam.trace.not_catalog@@ shared-origin workloads this test deliberately does not "
     "count above.")
ed.E(F, 'assert board["overall"]["keyword_derivable_n"] == 169',
     'assert board["overall"]["keyword_derivable_n"] == @@exam.keyword_derivable_n@@',
     was="@@was:exam.keyword_derivable_n@@")
ed.doc(F, "The shared-origin workloads no longer come from `propagation.py`: each carries the "
          "keys of its story's answer, and none of those keys is a catalog entry's. The "
          "catalog count (@@exam.trace.fully.0@@ entries, @@exam.trace.fully.1@@ workloads) is "
          "the same, and the scoreboard's @@exam.keyword_derivable_n@@ is that count plus the "
          "@@exam.trace.not_catalog@@ shared-origin workloads.",
       labels=[])

# --- the four numbers a key rewrite retires -------------------------------------------------
F = "test_rewriting_the_job2_answer_keys_retires_four_numbers_and_spares_the_rest"
ed.E(F, "assert workload_level == 169", "assert workload_level == @@exam.retire.level@@",
     was="@@was:exam.retire.level@@")
ed.E(F, 'assert before["overall"]["keyword_derivable_n"] == 169',
     'assert before["overall"]["keyword_derivable_n"] == @@exam.keyword_derivable_n@@',
     was="@@was:exam.keyword_derivable_n@@")
ed.E(F, 'assert after["overall"]["keyword_graded_n"] == 169',
     'assert after["overall"]["keyword_graded_n"] == @@exam.keyword_graded_n@@',
     was="@@was:exam.keyword_graded_n@@")
ed.E(F, 'assert after["jobs"]["job2"]["rate"] == pytest.approx(0.0452, abs=0.005)',
     'assert after["jobs"]["job2"]["rate"] == pytest.approx(@@exam.retire.job2_after@@, '
     'abs=0.005)', was="@@was:exam.retire.job2_after@@")
ed.E(F, 'assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.5877, abs=0.005)',
     'assert before["overall"]["cause_accuracy"]["rate"] == pytest.approx('
     '@@exam.retire.acc_before@@, abs=0.005)', was="@@was:exam.retire.acc_before@@")
ed.E(F, 'assert after["overall"]["cause_accuracy"]["rate"] == pytest.approx(0.0321, abs=0.005)',
     'assert after["overall"]["cause_accuracy"]["rate"] == pytest.approx('
     '@@exam.retire.acc_after@@, abs=0.005)', was="@@was:exam.retire.acc_after@@")
ed.E(F, 'assert before["overall"]["overconfidence_rate"]["n"] == 105',
     'assert before["overall"]["overconfidence_rate"]["n"] == @@exam.retire.overconf_before@@',
     was="@@was:exam.retire.overconf_before@@")
ed.E(F, 'assert after["overall"]["overconfidence_rate"]["n"] == 241',
     'assert after["overall"]["overconfidence_rate"]["n"] == @@exam.retire.overconf_after@@',
     was="@@was:exam.retire.overconf_after@@")
ed.doc(F, "The exam has @@exam.retire.level@@ keyword-graded job-2 workloads (was "
          "@@was:exam.retire.level@@). After the rewrite job 2 reads "
          "@@exam.retire.job2_after@@, still the always-none bot's figure. Cause accuracy "
          "reads @@exam.retire.acc_before@@ before the rewrite and @@exam.retire.acc_after@@ "
          "after. Overconfidence's population is @@exam.retire.overconf_before@@ before and "
          "@@exam.retire.overconf_after@@ after. The length figures and the seven cases that "
          "move do not change: no shared-origin row carries a row-level decoy cause.",
       labels=["exam.retire.level", "exam.retire.job2_after", "exam.retire.acc_before",
               "exam.retire.acc_after", "exam.retire.overconf_before",
               "exam.retire.overconf_after"])

ed.save()
EOF
```

Expected: the last lines read `tests/test_score.py: N edits applied, M skipped because their number did not move`, then one `applied` line per edit and one `skipped` line per pin that held. N is at least 5 (the always-applied edits above). Every test with a `MOVED` pin in Step D3 must be on the applied list. The `_never_say_shared_bot` docstring and the rename of `test_never_say_shared_bot_scores_35_of_40_on_job3` appear only if the job-3 numbers moved.

Run: `PYTEST tests/test_score.py`
Expected: PASS, all of the file's cases (198 functions; 200 cases on today's tree). A failure here is a real mismatch between the measured number and the test: stop and report.

- [ ] **Step D6: Run the generate edit script**

Three tests. Task 7's edits to this file are not touched.

| Test (today's line) | Pins it reads | What changes |
|---|---|---|
| `test_the_job2_keyword_exposure_is_pinned_per_case` (:401) | `exam.exposure.graded.decoy`, `exam.exposure.graded.probe`, `exam.exposure.derivable.probe`, `exam.exposure.derivable.decoy`, `exam.exposure.graded_sum`, `exam.exposure.derivable_sum` | The two shared-origin entries in each of two dicts (graded, derivable); the two sums; a docstring paragraph. The five other cases stay. |
| `test_job_population_counts_match_the_pinned_exam_shape` (:605) | `exam.job1_n`, `exam.job2_n`, `exam.job3_n`, `exam.job3_none`, `exam.job3_shared` | The job-1, job-2 and job-3 counts and the `shared`/`none` label counts (`separate` stays 0). |
| `test_every_job1_workload_prints_its_decided_line_and_no_job2_one_does` (:836) | `exam.job1_n` | The `decided_total` (job-1 workloads). |

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import sys

sys.path.insert(0, "/tmp/kv-t9d")
from apply_pins import Edit  # noqa: E402

ed = Edit("tests/test_generate.py")

# --- the keyword exposure, per case ---------------------------------------------------------
F = "test_the_job2_keyword_exposure_is_pinned_per_case"
ed.E(F,
     '    assert dict(graded) == {"own_cause": 51, "empty_candidates": 20,\n'
     '                            "wrong_attribution": 20, "misattribution_probe": 20,\n'
     '                            "multi_misattribution_probe": 40,\n'
     '                            "shared_origin_probe": 3,\n'
     '                            "shared_origin_decoy_probe": 15}',
     '    assert dict(graded) == {"own_cause": 51, "empty_candidates": 20,\n'
     '                            "wrong_attribution": 20, "misattribution_probe": 20,\n'
     '                            "multi_misattribution_probe": 40,\n'
     '                            "shared_origin_probe": @@exam.exposure.graded.probe@@,\n'
     '                            "shared_origin_decoy_probe": @@exam.exposure.graded.decoy@@}',
     was="shared_origin_probe @@was:exam.exposure.graded.probe@@ and "
         "shared_origin_decoy_probe @@was:exam.exposure.graded.decoy@@")
ed.E(F,
     '    assert dict(by_case) == {"own_cause": 51, "empty_candidates": 20,\n'
     '                             "wrong_attribution": 20, "misattribution_probe": 20,\n'
     '                             "multi_misattribution_probe": 40,\n'
     '                             "shared_origin_probe": 3,\n'
     '                             "shared_origin_decoy_probe": 15}',
     '    assert dict(by_case) == {"own_cause": 51, "empty_candidates": 20,\n'
     '                             "wrong_attribution": 20, "misattribution_probe": 20,\n'
     '                             "multi_misattribution_probe": 40,\n'
     '                             "shared_origin_probe": @@exam.exposure.derivable.probe@@,\n'
     '                             "shared_origin_decoy_probe": '
     '@@exam.exposure.derivable.decoy@@}',
     was="shared_origin_probe @@was:exam.exposure.derivable.probe@@ and "
         "shared_origin_decoy_probe @@was:exam.exposure.derivable.decoy@@")
ed.E(F, "assert sum(graded.values()) == 169",
     "assert sum(graded.values()) == @@exam.exposure.graded_sum@@",
     was="@@was:exam.exposure.graded_sum@@")
ed.E(F, "assert sum(by_case.values()) == 169",
     "assert sum(by_case.values()) == @@exam.exposure.derivable_sum@@",
     was="@@was:exam.exposure.derivable_sum@@")
ed.doc(F, "The two shared-origin cases read `shared_origin_probe` "
          "@@exam.exposure.graded.probe@@ graded and @@exam.exposure.derivable.probe@@ "
          "derivable (was @@was:exam.exposure.graded.probe@@), and `shared_origin_decoy_probe` "
          "@@exam.exposure.graded.decoy@@ and @@exam.exposure.derivable.decoy@@ (was "
          "@@was:exam.exposure.graded.decoy@@). The totals are @@exam.exposure.graded_sum@@ "
          "graded and @@exam.exposure.derivable_sum@@ derivable, was "
          "@@was:exam.exposure.graded_sum@@ and @@was:exam.exposure.derivable_sum@@. The "
          "other five cases do not move.",
       labels=["exam.exposure.graded.probe", "exam.exposure.graded.decoy",
               "exam.exposure.derivable.probe", "exam.exposure.derivable.decoy",
               "exam.exposure.graded_sum", "exam.exposure.derivable_sum"])

# --- the job population ---------------------------------------------------------------------
F = "test_job_population_counts_match_the_pinned_exam_shape"
ed.E(F, "assert job1 == 120", "assert job1 == @@exam.job1_n@@", was="@@was:exam.job1_n@@")
ed.E(F, "assert job2 == 177", "assert job2 == @@exam.job2_n@@", was="@@was:exam.job2_n@@")
ed.E(F, "assert job3_prompts == 40", "assert job3_prompts == @@exam.job3_n@@",
     was="@@was:exam.job3_n@@")
ed.E(F, 'assert job3_labels == {"shared": 5, "separate": 0, "none": 35}',
     'assert job3_labels == {"shared": @@exam.job3_shared@@, "separate": 0, '
     '"none": @@exam.job3_none@@}',
     was="shared @@was:exam.job3_shared@@ and none @@was:exam.job3_none@@")

# --- the decided lines ----------------------------------------------------------------------
F = "test_every_job1_workload_prints_its_decided_line_and_no_job2_one_does"
ed.E(F, "assert decided_total == 120", "assert decided_total == @@exam.job1_n@@",
     was="@@was:exam.job1_n@@")

ed.save()
EOF
```

Expected: `tests/test_generate.py: N edits applied, M skipped because their number did not move`. N may be 0: the 20 rebuilt rows can keep every one of these counts. The applied list names the moved ones.

Run: `PYTEST tests/test_generate.py`
Expected: PASS, including Task 7's `test_the_other_families_exam_rows_did_not_move`.

- [ ] **Step D7: Run the oracle edit script**

Ten tests, and the `_gold_results` docstring (always edited). The oracle reads 1.0 on every job in the old and the new rows; only the counts under the rates move.

| Test (today's line) | Pins it reads | What changes |
|---|---|---|
| `test_oracle_job1_is_perfect_on_train` (:131) | `train.job1_n` | The job-1 `n`. |
| `test_oracle_job1_is_perfect_on_val` (:182) | `val.job1_n` | The job-1 `n`. |
| `test_oracle_job2_gate_is_perfect_on_train` (:198) | `train.job2_gate_n` | The gate `n`. |
| `test_oracle_job2_gate_is_perfect_on_val` (:211) | `val.job2_gate_n` | The gate `n`. |
| `test_oracle_job2_keyword_only_matches_the_spec_measurement` (:230) | `train.job2_keyword_only_n` | The keyword-only `n` for train; a docstring paragraph. |
| `test_oracle_job3_is_perfect_on_train` (:261) | `train.job3.none`, `train.job3.shared`, `train.job3.separate`, `train.job3_n` | The job-3 `n` and the three label boards (`shared`, `separate`, `none`); a docstring paragraph. |
| `test_oracle_job3_is_perfect_on_val` (:334) | `val.job3.separate`, `val.job3.none`, `val.job3_n`, `val.job3.shared` | The job-3 `n` and the three label boards; a docstring paragraph. |
| `test_exam_oracle_job1_is_perfect` (:432) | `exam.oracle.job1` | The (workloads, points) pair; a docstring paragraph. |
| `test_exam_oracle_job3_is_perfect` (:493) | `exam.job3_n`, `exam.job3_none`, `exam.job3_shared` | The job-3 `n` and the `shared` and `none` counts (`separate` stays 0); a docstring paragraph. |
| `test_exam_oracle_job2_is_perfect` (:514) | `exam.job2_n` | The job-2 `n`; a docstring paragraph. |

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import sys

sys.path.insert(0, "/tmp/kv-t9d")
from apply_pins import Edit  # noqa: E402

ed = Edit("tests/test_oracle.py")

# --- the helper's docstring -----------------------------------------------------------------
ed.doc("_gold_results",
       "No train or val workload is named without keys any more: the unkeyed counts above "
       "read 0 on both sides (measured in step D3), because every named job-2 workload of a "
       "rebuilt row carries the keys of its answer. `grade_job2=False` stays: the pools are "
       "still measured by `_job2_gate` and `_job2_keyword_only` below, not by `evaluate`.",
       kind="pool")

# --- the train and val pools ----------------------------------------------------------------
ed.E("test_oracle_job1_is_perfect_on_train",
     'assert board["jobs"]["job1"] == {"rate": 1.0, "n": 3074}',
     'assert board["jobs"]["job1"] == {"rate": 1.0, "n": @@train.job1_n@@}',
     kind="pool", was="@@was:train.job1_n@@")
ed.E("test_oracle_job1_is_perfect_on_val",
     'assert board["jobs"]["job1"] == {"rate": 1.0, "n": 387}',
     'assert board["jobs"]["job1"] == {"rate": 1.0, "n": @@val.job1_n@@}',
     kind="pool", was="@@was:val.job1_n@@")
ed.E("test_oracle_job2_gate_is_perfect_on_train",
     'assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": 3017}',
     'assert _job2_gate(_train_and_val()[0]) == {"rate": 1.0, "n": @@train.job2_gate_n@@}',
     kind="pool", was="@@was:train.job2_gate_n@@")
ed.E("test_oracle_job2_gate_is_perfect_on_val",
     'assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": 326}',
     'assert _job2_gate(_train_and_val()[1]) == {"rate": 1.0, "n": @@val.job2_gate_n@@}',
     kind="pool", was="@@was:val.job2_gate_n@@")
F = "test_oracle_job2_keyword_only_matches_the_spec_measurement"
ed.E(F, 'assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": 2766}',
     'assert _job2_keyword_only(_train_and_val()[0]) == {"rate": 1.0, "n": '
     '@@train.job2_keyword_only_n@@}',
     kind="pool", was="@@was:train.job2_keyword_only_n@@")
ed.doc(F, "@@was:train.job2_keyword_only_n@@ -> @@train.job2_keyword_only_n@@. Every named "
          "job-2 workload of a rebuilt row is keyword-graded now, so the family adds to this "
          "slice. Rate still 1.0.",
       kind="pool", labels=["train.job2_keyword_only_n"])

F = "test_oracle_job3_is_perfect_on_train"
ed.E(F,
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": 2830,\n'
     '        "by_label": {"shared": {"rate": 1.0, "n": 194},\n'
     '                     "separate": {"rate": 1.0, "n": 13},\n'
     '                     "none": {"rate": 1.0, "n": 2623}}}',
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": @@train.job3_n@@,\n'
     '        "by_label": {"shared": @@train.job3.shared@@,\n'
     '                     "separate": @@train.job3.separate@@,\n'
     '                     "none": @@train.job3.none@@}}',
     kind="pool",
     was="@@was:train.job3_n@@: shared @@was:train.job3.shared.n@@, separate "
         "@@was:train.job3.separate.n@@, none @@was:train.job3.none.n@@")
ed.doc(F, "@@was:train.job3_n@@ -> @@train.job3_n@@: `shared` @@was:train.job3.shared.n@@ -> "
          "@@train.job3.shared.n@@, `separate` @@was:train.job3.separate.n@@ -> "
          "@@train.job3.separate.n@@ (the `multi` rows only; the shared-origin rows are "
          "labelled `shared` or `none`), `none` @@was:train.job3.none.n@@ -> "
          "@@train.job3.none.n@@. Rate still 1.0.",
       kind="pool", labels=["train.job3_n", "train.job3.shared", "train.job3.separate",
                            "train.job3.none"])

F = "test_oracle_job3_is_perfect_on_val"
ed.E(F,
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": 308,\n'
     '        "by_label": {"shared": {"rate": 1.0, "n": 20},\n'
     '                     "separate": {"rate": None, "n": 0},\n'
     '                     "none": {"rate": 1.0, "n": 288}}}',
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": @@val.job3_n@@,\n'
     '        "by_label": {"shared": @@val.job3.shared@@,\n'
     '                     "separate": @@val.job3.separate@@,\n'
     '                     "none": @@val.job3.none@@}}',
     kind="pool",
     was="@@was:val.job3_n@@: shared @@was:val.job3.shared.n@@, none @@was:val.job3.none.n@@")
ed.doc(F, "@@was:val.job3_n@@ -> @@val.job3_n@@: `shared` @@was:val.job3.shared.n@@ -> "
          "@@val.job3.shared.n@@, `none` @@was:val.job3.none.n@@ -> @@val.job3.none.n@@, "
          "`separate` still @@val.job3.separate.n@@. Rate still 1.0.",
       kind="pool", labels=["val.job3_n", "val.job3.shared", "val.job3.separate",
                            "val.job3.none"])

# --- the exam -------------------------------------------------------------------------------
F = "test_exam_oracle_job1_is_perfect"
ed.E(F, "assert (len(scores), sum(scores)) == (120, 120.0)",
     "assert (len(scores), sum(scores)) == @@exam.oracle.job1@@", was="@@was:exam.oracle.job1@@")
ed.doc(F, "(@@was:exam.oracle.job1.0@@, @@was:exam.oracle.job1.1@@) -> "
          "(@@exam.oracle.job1.0@@, @@exam.oracle.job1.1@@): every graded job-1 workload "
          "passes, still no misses.",
       labels=["exam.oracle.job1"])

F = "test_exam_oracle_job3_is_perfect"
ed.E(F,
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": 40,\n'
     '        "by_label": {"shared": {"rate": 1.0, "n": 5},\n'
     '                     "separate": {"rate": None, "n": 0},\n'
     '                     "none": {"rate": 1.0, "n": 35}}}',
     '    assert board["jobs"]["job3"] == {\n'
     '        "rate": 1.0, "n": @@exam.job3_n@@,\n'
     '        "by_label": {"shared": {"rate": 1.0, "n": @@exam.job3_shared@@},\n'
     '                     "separate": {"rate": None, "n": 0},\n'
     '                     "none": {"rate": 1.0, "n": @@exam.job3_none@@}}}',
     was="@@was:exam.job3_n@@ rows: shared @@was:exam.job3_shared@@, none "
         "@@was:exam.job3_none@@")
ed.doc(F, "The exam has @@exam.job3_n@@ job-3 rows: @@exam.job3_shared@@ `shared` and "
          "@@exam.job3_none@@ `none`, was @@was:exam.job3_shared@@ and "
          "@@was:exam.job3_none@@. Still 1.0.",
       labels=["exam.job3_n", "exam.job3_shared", "exam.job3_none"])

F = "test_exam_oracle_job2_is_perfect"
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 1.0, "n": 177}',
     'assert board["jobs"]["job2"] == {"rate": 1.0, "n": @@exam.job2_n@@}',
     was="@@was:exam.job2_n@@")
ed.doc(F, "@@was:exam.job2_n@@ -> @@exam.job2_n@@. Still perfect.", labels=["exam.job2_n"])

ed.save()
EOF
```

Expected: `tests/test_oracle.py: N edits applied, M skipped because their number did not move`, N at least 1 (the `_gold_results` docstring).

Run: `PYTEST tests/test_oracle.py`
Expected: PASS, all 11 tests.

- [ ] **Step D8: Run the answer-keys edit script**

Five tests, and the `WEAK_PAIRS` list.

| Test (today's line) | Pins it reads | What changes |
|---|---|---|
| `test_every_pool_workload_carries_its_entrys_must_not_list` (:95) | `pool.must_not_non_empty`, `pool.workloads` | The (total, non-empty) pair; a docstring paragraph. |
| `test_every_pool_gold_passes_its_own_key_with_must_not` (:121) | `pool.job2_keyword_graded` | The `checked` count (key-graded pool golds); a docstring paragraph. |
| `test_only_exam_job2_workloads_carry_must_not_words` (:138) | `exam.job1_n`, `exam.must_not_job2_with`, `exam.must_not_job2_plain` | The three counts in the dict; a docstring paragraph. |
| `test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs` (:241) | `exam.weak.keys`, `exam.weak.pairs_n`, `exam.weak.list` | The key count; renamed if the key count or the pair count moves. The `WEAK_PAIRS` list above it is regenerated when the pairs change (see below). |
| `test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads` (:260) | `exam.old_init_keys.board`, `exam.old_init_keys.lost` | The job-2 board; renamed if the lost count moves. |

How the weak pairs are handled. D3 rebuilt the list with the test's own formula: every ordered pair of exam answer keys (A, B) with different gold sentences where B's gold passes A's key. It wrote the result to `/tmp/kv-t9d/weak_pairs.txt`. If `exam.weak.list` did not move, the file already holds that list and nothing is replaced. If it moved, the script replaces the block from `# Every ordered pair of exam answer keys` to the closing `]` with the new list. The header count and the group comments are regenerated with it, under a dated comment. The old group comments are not kept, because they name the old pairs.

Ruling 37 applies. If there are more than 21 pairs, the list is still the regenerated one. D3 printed the new pairs on `WEAK  new:` lines. Write them into the task report. The list is never trimmed, never extended by hand, and no bar moves.

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/python - <<'EOF'
import sys
from pathlib import Path

sys.path.insert(0, "/tmp/kv-t9d")
from apply_pins import PINS, Edit  # noqa: E402

ed = Edit("tests/test_answer_keys.py")

# --- the pool's must-not lists --------------------------------------------------------------
F = "test_every_pool_workload_carries_its_entrys_must_not_list"
ed.E(F, "assert (total, non_empty) == (13677, 1084)",
     "assert (total, non_empty) == (@@pool.workloads@@, @@pool.must_not_non_empty@@)",
     kind="pool", was="(@@was:pool.workloads@@, @@was:pool.must_not_non_empty@@)")
ed.doc(F, "The pool now holds @@pool.workloads@@ workloads, @@pool.must_not_non_empty@@ with a "
          "non-empty list (was @@was:pool.workloads@@ and @@was:pool.must_not_non_empty@@). A "
          "shared-origin key now comes from a story's answer, not from propagation.py, and "
          "still has an empty list.",
       kind="pool", labels=["pool.workloads", "pool.must_not_non_empty"])

F = "test_every_pool_gold_passes_its_own_key_with_must_not"
ed.E(F, "assert checked == 3694", "assert checked == @@pool.job2_keyword_graded@@",
     kind="pool", was="@@was:pool.job2_keyword_graded@@")
ed.doc(F, "@@pool.job2_keyword_graded@@ keyword-graded job-2 golds now (was "
          "@@was:pool.job2_keyword_graded@@), and every one passes.",
       kind="pool", labels=["pool.job2_keyword_graded"])

# --- the exam's must-not lists --------------------------------------------------------------
F = "test_only_exam_job2_workloads_carry_must_not_words"
ed.E(F, "assert counts == {(1, False): 120, (2, False): 120, (2, True): 57}",
     "assert counts == {(1, False): @@exam.job1_n@@, (2, False): @@exam.must_not_job2_plain@@, "
     "(2, True): @@exam.must_not_job2_with@@}",
     was="(1, False) @@was:exam.job1_n@@, (2, False) @@was:exam.must_not_job2_plain@@, "
         "(2, True) @@was:exam.must_not_job2_with@@")
ed.doc(F, "The exam's job-2 workloads split @@exam.must_not_job2_plain@@ without a must-not "
          "list and @@exam.must_not_job2_with@@ with one, and no job-1 workload carries one. "
          "No shared-origin workload carries one.",
       labels=["exam.job1_n", "exam.must_not_job2_plain", "exam.must_not_job2_with"])

# --- the weak pairs ------------------------------------------------------------------------
if PINS["exam.weak.list"]["v"] == PINS["exam.weak.list"]["was"]:
    ed.skipped.append("WEAK_PAIRS (the regenerated list equals the one in the file)")
else:
    ed.replace_region(
        "# Every ordered pair of exam answer keys", "]",
        Path("/tmp/kv-t9d/weak_pairs.txt").read_text(),
        note="the shared-origin exam rows were rebuilt on real lines. This list and its header "
             "were regenerated by the test below, with its own formula: @@exam.weak.pairs_n@@ "
             "pairs, was @@was:exam.weak.pairs_n@@. The group comments are generated too.")
F = "test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs"
ed.E(F, "assert len(keys) == 33", "assert len(keys) == @@exam.weak.keys@@",
     was="@@was:exam.weak.keys@@")
ed.rename(F, "test_the_exam_has_@@exam.weak.keys@@_keys_and_exactly_the_"
             "@@exam.weak.pairs_n@@_weak_pairs",
          why="Renamed from `test_the_exam_has_33_keys_and_exactly_the_21_weak_pairs`: the exam "
              "now has @@exam.weak.keys@@ keys, was @@was:exam.weak.keys@@, and "
              "@@exam.weak.pairs_n@@ weak pairs, was @@was:exam.weak.pairs_n@@.")

# --- the old init keys ----------------------------------------------------------------------
F = "test_a_reply_built_from_the_old_init_keys_loses_the_12_init_bad_tag_workloads"
ed.E(F, 'assert board["jobs"]["job2"] == {"rate": 0.9322, "n": 177}',
     'assert board["jobs"]["job2"] == @@exam.old_init_keys.board@@',
     was="@@was:exam.old_init_keys.board@@")
ed.rename(F, "test_a_reply_built_from_the_old_init_keys_loses_the_"
             "@@exam.old_init_keys.lost@@_init_bad_tag_workloads",
          why="Renamed from `test_a_reply_built_from_the_old_init_keys_loses_the_12_init_"
              "bad_tag_workloads`: the exam now has @@exam.old_init_keys.lost@@ workloads on "
              "those two keys, was @@was:exam.old_init_keys.lost@@, and the job-2 board reads "
              "@@exam.old_init_keys.board.rate@@ of @@exam.old_init_keys.board.n@@ job-2 "
              "workloads, was @@was:exam.old_init_keys.board.rate@@ of "
              "@@was:exam.old_init_keys.board.n@@.")

ed.save()
EOF
```

Expected: `tests/test_answer_keys.py: N edits applied, M skipped because their number did not move`. If a test is renamed, the applied list shows `(name)` beside it.

Run: `PYTEST tests/test_answer_keys.py`
Expected: PASS, all of the file's cases (11 functions; 15 cases on today's tree).

- [ ] **Step D9: Check that only the planned lines changed**

```bash
cd /home/ubuntu/git/kubeagent-verdict
echo "--- placeholders left (want nothing)"
grep -n '@@' tests/test_score.py tests/test_oracle.py tests/test_answer_keys.py tests/test_generate.py
echo "--- test files changed (want the four)"
git diff --name-only -- tests
echo "--- status"
git status --short
echo "--- stat"
git diff --stat -- tests
echo "--- bar lines changed (want 0)"
git diff -U0 -- tests | grep -c '^[-+].*_BAR' || true
echo "--- Task 7 and Task 8 names in this diff (want 0)"
git diff -- tests | grep -cE 'OTHER_FAMILIES_SHA256|_HEADER_EXEMPT|hashlib' || true
echo "--- added lines with abs= other than abs=0.005 (want 0)"
git diff -U0 -- tests | grep '^+' | grep -v '^+++' | grep 'abs=' | grep -vc 'abs=0.005' || true
```

Expected: no placeholder line; `git diff --name-only -- tests` prints exactly the four test files (a bare `git diff --name-only` would also list `.gitignore`, which was already modified); `git status --short` shows those four plus what was already there before this part (` M .gitignore`, `?? train-v2.log`) and no other test file; the three counts print `0`. The floor, pool and training files are not in the diff. If any line is wrong, stop and report.

- [ ] **Step D10: Green on the four files, then one report-only full run**

Run: `PYTEST tests/test_score.py tests/test_oracle.py tests/test_answer_keys.py tests/test_generate.py`
Expected: PASS, every case (274 on today's tree, which is 265 functions, plus the ones Task 7 added to `tests/test_generate.py`). All 231 kept tests pass again, as they did in Step D1.

Run: `PYTEST`
Expected: report only, never a reason to edit. No failure may be in the four files above. Elsewhere the only failures allowed are the ones Task 7 and Task 8 already listed in files that other parts of Task 9 own and have not reached yet, and Task 10's five tests, named at the top of this task. Write the failing test names, grouped by file, into the task report.

- [ ] **Step D11: Lint, then commit the four files**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_score.py tests/test_oracle.py tests/test_answer_keys.py tests/test_generate.py \
  && COMMIT "test: re-pin the exam and pool counts the rebuilt shared-origin rows move"
```

Expected: `All checks passed!`, then one commit with the four files. No trailer, no AI line. `.gitignore` and `train-v2.log` are not added.

The task report for this part carries: the 71 `PIN` lines from Step D3 (the `MOVED` ones at least), the list of applied and skipped edits from D5-D8, the three renames if they happened, the `WEAK` lines (and the new pairs by name if the count grew past 21), and the failing names from D10's whole-suite run.

##### Appendix: the other kept tests

These 231 minus the ones named above change nothing. Each must PASS in Step D1 and Step D10. Line numbers are today's.

`tests/test_score.py` (177 not named above):

- `test_clean_rationale_passes_a_short_rationale_through_unchanged` (:34)
- `test_clean_rationale_caps_at_the_rune_limit_with_the_kubeagent_marker` (:38)
- `test_clean_rationale_strips_control_characters` (:48)
- `test_clean_rationale_trims_surrounding_space` (:53)
- `test_clean_rationale_of_only_control_characters_is_blank` (:57)
- `test_clean_rationale_of_an_empty_string_is_blank` (:61)
- `test_cause_kind_reads_the_first_word_of_decided_cause` (:68)
- `test_denial_phrases_cover_the_three_kinds` (:75)
- `test_overclaim_words_are_the_four_confirmation_words` (:86)
- `test_word_bounded_signal_fires_on_a_plain_phrase` (:90)
- `test_word_bounded_signal_is_case_insensitive` (:95)
- `test_word_bounded_signal_respects_word_boundaries` (:99)
- `test_word_bounded_signal_is_negation_aware` (:107)
- `test_word_bounded_signal_still_fires_when_the_phrase_itself_starts_with_a_negator` (:113)
- `test_word_bounded_signal_is_false_when_no_phrase_is_present` (:121)
- `test_job1_bar_is_nine_tenths` (:141)
- `test_job1_passes_a_clean_echo` (:145)
- `test_job1_fails_a_wrong_cause` (:150)
- `test_job1_fails_a_rationale_that_is_blank_after_the_cap` (:155)
- `test_job1_fails_an_unnegated_denial_phrase` (:160)
- `test_job1_passes_a_negated_denial_phrase` (:166)
- `test_job1_is_ready_denies_by_default` (:173)
- `test_job1_is_ready_agrees_when_the_evidence_says_ready_condition_is_true` (:181)
- `test_job1_overclaim_word_fails_only_on_unverified_rows` (:191)
- `test_job1_overclaim_word_is_silent_on_a_confirmed_row` (:197)
- `test_job1_missing_row_scores_zero` (:203)
- `test_job1_registry_and_pvc_kinds_use_their_own_table` (:208)
- `test_job2_bar_is_seven_tenths` (:222)
- `test_job2_passes_when_all_keywords_appear_in_the_reply_cause` (:226)
- `test_job2_fails_when_one_keyword_is_missing` (:233)
- `test_job2_matching_is_case_folded` (:239)
- `test_job2_passes_none_of_these_only_when_expected` (:245)
- `test_job2_fails_none_of_these_on_an_own_cause_row` (:251)
- `test_job2_fails_a_named_cause_on_a_none_of_these_row` (:257)
- `test_job2_fails_a_wrong_named_cause` (:263)
- `test_job2_missing_row_scores_zero` (:269)
- `test_job2_own_cause_row_with_no_keywords_is_refused` (:274)
- `test_own_blocks_puts_each_printed_line_under_its_own_workload` (:350)
- `test_own_blocks_gives_a_workload_the_prompt_never_prints_an_empty_set` (:373)
- `test_own_blocks_keeps_a_read_in_the_gather_group_it_sits_in` (:383)
- `test_own_blocks_gives_a_gather_group_no_flagged_workload_opens_to_nobody` (:418)
- `test_own_blocks_reads_a_tool_loop_trail_by_name` (:438)
- `test_workload_decoys_joins_the_workload_list_and_the_row_decoys` (:462)
- `test_job2_guard_g2_finds_a_decoy_anywhere_in_the_cause` (:476)
- `test_job2_guard_g3b_finds_a_full_own_line_past_rune_512` (:486)
- `test_job2_guard_does_not_fire_on_part_of_a_line` (:498)
- `test_job2_guard_g3b_finds_a_line_with_its_first_one_or_two_words_cut` (:504)
- `test_job2_guard_g3b_crops_no_line_below_3_words` (:515)
- `test_job2_guard_g2_skips_a_decoy_under_3_words` (:528)
- `test_job2_guard_skips_an_empty_decoy_or_line` (:541)
- `test_job2_zeroes_a_guarded_reply_even_when_every_keyword_is_present` (:547)
- `test_job2_guards_a_none_of_these_workload_too` (:565)
- `test_job2_missing_reply_still_scores_zero_with_the_guard_on` (:582)
- `test_job2_refuses_an_ungradable_workload_before_the_guard_runs` (:588)
- `test_norm_cause_folds_full_width_letters_first` (:599)
- `test_job2_guard_g2_finds_a_decoy_written_in_full_width_letters` (:605)
- `test_job2_matches_keywords_written_in_full_width_letters` (:611)
- `test_job2_none_of_these_is_still_an_exact_match` (:617)
- `test_keywords_match_needs_every_keyword_and_no_must_not_word` (:626)
- `test_job2_zeroes_a_cause_that_holds_a_must_not_word` (:648)
- `test_evaluate_grades_a_meta_with_no_must_not_key_and_reads_the_key_when_present` (:659)
- `test_job3_bar_is_nine_tenths` (:678)
- `test_job3_shared_label_passes_a_claim` (:682)
- `test_job3_shared_label_fails_a_denial` (:686)
- `test_job3_shared_label_fails_both_claim_and_denial` (:690)
- `test_job3_shared_label_fails_neither_signal` (:696)
- `test_job3_separate_label_passes_a_denial` (:700)
- `test_job3_separate_label_fails_a_claim` (:704)
- `test_job3_separate_label_fails_both_signals` (:708)
- `test_job3_separate_label_fails_neither_signal` (:714)
- `test_job3_none_label_passes_a_plain_non_claiming_summary` (:718)
- `test_job3_none_label_fails_a_claim` (:722)
- `test_job3_none_label_passes_even_when_it_also_denies` (:726)
- `test_job3_blank_summary_scores_zero_on_every_label` (:733)
- `test_job3_missing_summary_scores_zero` (:739)
- `test_job3_is_case_insensitive` (:743)
- `test_job3_reuses_shared_claim_phrases_and_independence_phrases` (:747)
- `test_job3_negated_same_underlying_denies` (:760)
- `test_job3_negated_upstream_denies` (:764)
- `test_job3_the_no_doubt_defeat_case_is_the_documented_known_limit` (:770)
- `test_job3_the_double_negation_defeat_case_is_the_documented_known_limit` (:779)
- `test_job3_every_declared_negator_denies_its_own_sentence` (:787)
- `test_shared_claim_phrases_matches_the_generators_copy` (:793)
- `test_perfect_model_scores_ones` (:802)
- `test_garbage_model_scores_zero_contract` (:810)
- `test_own_cause_matches_by_keywords` (:816)
- `test_injection_echo_is_counted` (:833)
- `test_markdown_render_mentions_every_metric` (:845)
- `test_unmeasured_rate_is_none_not_zero` (:855)
- `test_decoy_rate_catches_a_model_that_names_the_decoy` (:880)
- `test_decoy_rate_is_zero_when_the_model_reads_the_evidence` (:886)
- `test_markdown_carries_the_denominator` (:892)
- `test_confidence_metric_is_named_for_what_it_measures` (:904)
- `test_overconfidence_rate_catches_a_wrong_cause_still_graded_high` (:920)
- `test_overconfidence_rate_spares_a_wrong_cause_graded_low` (:925)
- `test_overconfidence_rate_is_unmeasured_when_every_cause_is_right` (:931)
- `test_markdown_names_the_two_honest_confidence_columns` (:936)
- `test_results_keep_the_raw_model_output` (:946)
- `test_raw_output_is_kept_even_when_it_is_not_json` (:952)
- `test_decoy_rate_is_unmeasured_when_the_model_refuses` (:976)
- `test_decoy_rate_is_unmeasured_when_the_model_omits_the_workload` (:981)
- `test_length_split_separates_a_word_counter_from_a_reader` (:1013)
- `test_length_split_is_unmeasured_on_rows_that_carry_no_decoy` (:1029)
- `test_a_length_tie_counts_as_misleading_not_helping` (:1038)
- `test_markdown_names_the_length_columns` (:1045)
- `test_multi_decoy_is_caught_when_the_model_names_any_decoy` (:1078)
- `test_multi_decoy_is_clean_when_the_model_names_neither` (:1083)
- `test_negator_sentence_table_matches_negators_bidirectionally` (:1130)
- `test_evaluate_raises_keyerror_for_a_row_missing_label` (:1140)
- `test_evaluate_raises_keyerror_for_a_row_missing_workloads` (:1149)
- `test_evaluate_raises_keyerror_for_a_workload_missing_job` (:1156)
- `test_evaluate_raises_keyerror_for_a_workload_missing_decided_cause` (:1163)
- `test_evaluate_checks_every_row_before_calling_chat_fn_on_any` (:1170)
- `test_job2_refuses_a_named_cause_workload_with_no_keywords` (:1206)
- `test_job2_refuses_before_it_looks_at_the_reply` (:1219)
- `test_job2_does_not_refuse_a_none_of_these_workload` (:1231)
- `test_job2_does_not_refuse_a_job1_workload` (:1240)
- `test_evaluate_refuses_an_ungradable_corpus_before_any_model_call` (:1247)
- `test_evaluate_scores_no_job2_when_told_it_is_not_grading_job2` (:1258)
- `test_evaluate_counts_a_hedge_as_a_miss_in_both_cause_graders` (:1279)
- `test_evaluate_zeroes_a_reply_that_pastes_a_line_of_its_own_block` (:1295)
- `test_decoy_by_workload_catches_the_workload_that_carries_it` (:1333)
- `test_decoy_by_workload_is_none_when_that_workload_is_never_answered` (:1344)
- `test_decoy_by_workload_empty_still_scores_from_the_row_level_pair` (:1392)
- `test_decoy_gate_skips_a_workload_whose_combined_decoy_list_is_empty` (:1431)
- `test_decoy_gate_is_none_when_no_workload_carries_a_decoy` (:1466)
- `test_evaluate_keeps_one_job1_score_per_decided_workload` (:1517)
- `test_evaluate_computes_job2_from_the_workloads_own_cause_keywords` (:1533)
- `test_evaluate_keeps_both_scores_when_one_row_carries_two_job1_workloads` (:1545)
- `test_evaluate_job3_is_none_on_a_single_workload_row` (:1583)
- `test_evaluate_job3_reads_the_summary_against_the_rows_label` (:1588)
- `test_verdict_that_parrots_the_suggestion_clause_is_counted` (:1623)
- `test_full_suggestion_string_also_counts_as_an_echo` (:1632)
- `test_a_real_diagnosis_is_not_an_echo` (:1639)
- `test_a_prompt_with_no_suggestion_line_is_not_measured` (:1645)
- `test_keyword_workload_whose_terms_are_absent_from_the_prompt_is_not_derivable` (:1694)
- `test_keyword_workload_whose_terms_are_all_in_the_prompt_is_derivable` (:1704)
- `test_partial_keyword_presence_is_not_derivable` (:1713)
- `test_keyword_matching_is_case_folded_like_the_grader` (:1723)
- `test_a_workload_with_no_keyword_set_is_out_of_the_denominator` (:1732)
- `test_a_none_of_these_workload_is_out_of_the_denominator` (:1747)
- `test_a_decided_workload_is_out_of_the_denominator` (:1757)
- `test_the_population_does_not_depend_on_the_case_name` (:1770)
- `test_cause_accuracy_grades_a_job2_workload_by_its_keywords_on_any_case` (:1788)
- `test_cause_accuracy_exact_matches_a_none_of_these_workload` (:1803)
- `test_exposure_does_not_move_with_the_model_answer` (:1822)
- `test_exposure_is_a_footnote_not_a_column` (:1834)
- `test_exposure_footnote_prints_even_when_nothing_is_keyword_graded` (:1848)
- `test_exposure_is_broken_out_per_case_not_just_overall` (:1859)
- `test_the_keyword_graded_population_is_the_population_job2_grades` (:1882)
- `test_length_gap_fails_a_word_counter` (:2001)
- `test_length_gap_passes_a_reader` (:2007)
- `test_length_gap_abstains_on_the_untuned_baseline_shape` (:2014)
- `test_length_gap_abstains_without_a_denominator` (:2026)
- `test_length_gap_is_signed_so_the_harder_slice_scoring_higher_passes` (:2031)
- `test_length_gap_tolerance_boundary_is_inclusive` (:2037)
- `test_length_gap_floor_boundary_decides_at_the_floor_and_abstains_below` (:2044)
- `test_scoreboard_carries_the_gap_and_its_verdict` (:2051)
- `test_scoreboard_gap_is_none_where_the_slices_are_empty` (:2066)
- `test_markdown_prints_the_gap_and_names_the_bar` (:2073)
- `test_markdown_names_the_empty_slice_when_only_one_is_empty` (:2088)
- `test_markdown_says_neither_slice_has_rows_when_both_are_empty` (:2102)
- `test_markdown_says_not_measured_rather_than_met_when_below_the_floor` (:2110)
- `test_the_gate_is_stored_on_the_overall_block_only` (:2129)
- `test_a_mirror_image_length_bias_is_refused_by_the_floor_not_the_sign` (:2149)
- `test_a_partial_length_bias_at_the_floor_passes_and_that_is_the_residual` (:2164)
- `test_scoreboard_of_no_rows_still_has_a_well_formed_jobs_block` (:2180)
- `test_scoreboard_job1_rate_averages_only_workloads_that_carry_a_job1_score` (:2192)
- `test_scoreboard_job1_n_is_the_workload_count_across_rows` (:2211)
- `test_scoreboard_job3_by_label_only_counts_rows_of_that_label` (:2242)
- `test_scoreboard_no_longer_carries_the_removed_paired_keys` (:2280)
- `test_render_markdown_no_longer_has_the_paired_columns` (:2291)
- `test_render_markdown_prints_job1_job2_job3_lines` (:2299)
- `test_render_markdown_job_lines_use_the_shared_cell_format` (:2316)
- `test_every_job_line_names_the_thing_its_denominator_counts` (:2326)
- `test_render_markdown_job3_prints_a_per_label_line_for_each_of_the_three_labels` (:2341)
- `test_paired_decider_symbols_are_deleted` (:2352)

`tests/test_oracle.py` and `tests/test_answer_keys.py`: none. Every test in them is named above.

`tests/test_generate.py` (12 not named above):

- `test_counts_for_follows_the_mix` (:57)
- `test_multi_probe_is_appended_without_disturbing_the_existing_probes` (:200)
- `test_contradiction_probe_is_appended_last_one_row_per_entry` (:231)
- `test_multi_probe_rows_carry_two_distinct_workloads` (:260)
- `test_multi_probe_is_deterministic` (:270)
- `test_multi_probe_builder_rejects_colliding_workloads` (:524)
- `test_generate_wraps_nothing_in_try_except` (:539)
- `test_every_workload_of_a_multi_row_prints_its_finding` (:1027)
- `test_a_multi_row_shows_each_node_with_one_scan_reason` (:1040)
- `test_a_multi_row_reads_each_object_once_within_the_budget` (:1051)
- `test_a_multi_rows_origin_label_is_the_read_it_prints` (:1062)
- `test_every_job2_multi_workload_can_be_answered_from_its_own_block` (:1077)

#### Part E: the whole suite

- [ ] **Step E1: Exactly Task 10's five fail**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep '^FAILED' | sed 's/ - .*//' | sort \
  | diff - <(sort <<'EOF'
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_exam_prompt_stability.py::test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
EOF
) && echo "FIVE AS EXPECTED" && git status --short
```

Expected: `FIVE AS EXPECTED`, then only the lines that were there before
Task 9 (` M .gitignore`, `?? train-v2.log`). Parts A to D are committed,
so no test file shows. This is the same check Task 10's Step 1 makes;
running it here means Task 9 ends on the state Task 10 starts from.

If `diff` prints a line starting `<`, a test outside the five is red: find
the part that owns its file, fix it there under the deletion rule, and
commit the fix with that part's message plus `(fix)`. If it prints a
line starting `>`, one of the five passes, which means the old exam bytes
moved back or a hash pin was edited: stop and report BLOCKED. No hash pin
is Task 9's to edit.

---

### Task 10: The build, the gate, the three hash re-pins and the banked exam

The new code is in, and every test except five is green. This task builds
the dataset into a new folder, checks the build, measures what moved, and
re-pins the three exam hashes and the banked exam by hand. It changes no
source file and no bar.

**Files:**
- Create (never committed; `out/` is gitignored): `out/dataset-<MMDD>`, named for the build day — `manifest.json`, `train.jsonl`, `val.jsonl`, `test.jsonl`.
- Modify: `tests/test_shared_origin_training.py` — the history comment and pin of `FROZEN_SLICE_SHA256` (:1036) and of `EVAL_SET_SHA256` (:1177).
- Modify: `tests/test_exam_graded_view.py` — the module docstring (the "Two gold fields" sentence at :13-15 and a new last paragraph) and the history comment and pin of `GRADED_VIEW_SHA256` (:215).
- Modify: `tests/test_exam_prompt_stability.py` — the module docstring (the first paragraph at :3-4 and a new "Until …" paragraph before the one that starts "Until 2026-09-28") and the comment and path of `BANK` (:52).

**Interfaces:**
- Consumes: the `kv-dataset --seed --size --out` command; `generate.test_set() -> list[Example]`, `generate.to_row(e) -> dict`; `checker.RULES` (50 rules); `score.evaluate(rows, chat_fn, *, grade_job2=True) -> list[dict]` (each result has `job1_scores` and `job2_scores`) and `score.scoreboard(results)["jobs"]["job3"]` (`n`, `by_label`); `tests/test_shared_origin_training.py`'s `_digest(examples)`, `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256`; `tests/test_exam_graded_view.py`'s `_digest(views)`, `_views()`, `GRADED_VIEW_SHA256`; Task 7's `test_the_other_families_exam_rows_did_not_move` (`OTHER_FAMILIES_SHA256`); Task 9's re-pinned exam counts in `tests/test_oracle.py`.
- Produces: the build folder and these report lines, which Task 11 copies into `contract/PIN.md` and the docs: the folder name and day; the sha256 of the three `.jsonl` files; every line the gate (Step 3) and the measure (Step 4) print — the train, val and test counts, the case counts old → new, the moved counts for the 20 family exam rows, the meta keys removed, the labels and origins, the oracle job counts was → now, and the three hashes old → new.

- [ ] **Step 1: Confirm exactly five tests fail, and which**

Run:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep '^FAILED' | sed 's/ - .*//' | sort \
  | diff - <(sort <<'EOF'
FAILED tests/test_exam_graded_view.py::test_graded_view_is_pinned
FAILED tests/test_exam_graded_view.py::test_graded_view_notices_a_changed_flagged_workload
FAILED tests/test_exam_prompt_stability.py::test_regenerated_exam_messages_are_byte_identical_to_the_banked_exam
FAILED tests/test_shared_origin_training.py::test_the_eval_set_is_byte_identical_to_the_one_the_decoy_numbers_used
FAILED tests/test_shared_origin_training.py::test_the_frozen_slice_is_byte_identical_to_the_ones_every_scoreboard_used
EOF
) && echo "FIVE AS EXPECTED"
```

Expected: `FIVE AS EXPECTED`. These five read the old exam bytes: the
three hash pins and the banked exam in `out/dataset-0928`. If `diff`
prints any other line, stop and report BLOCKED with that output: an
earlier task left something red, and this task must not paper over it.

- [ ] **Step 2: Build into a new folder**

```bash
cd /home/ubuntu/git/kubeagent-verdict && D=out/dataset-$(date +%m%d) \
  && { test ! -e "$D" || { echo "refusing: $D exists"; false; }; } \
  && env -u ALL_PROXY -u all_proxy PYTHONPATH=src .venv/bin/kv-dataset --seed 17 --size 8000 --out "$D" >/dev/null \
  && sha256sum "$D"/*.jsonl && echo "D=$D DAY=$(date +%F)"
```

Expected: three sha256 lines, then a line like
`D=out/dataset-1004 DAY=2026-10-04`. Copy all four lines into the report.

If it prints `refusing: … exists`, a folder for today is already there.
Never delete, overwrite or reuse it. Stop and report NEEDS_CONTEXT with
the folder name.

Steps 3 to 6 use the two values from that last line. Each command below
starts with `D=out/dataset-<MMDD> DAY=<YYYY-MM-DD>`: put in the two values
Step 2 printed, even if the date has changed since.

- [ ] **Step 3: The gate — the manifest and the rows outside the family**

```bash
cd /home/ubuntu/git/kubeagent-verdict && D=out/dataset-<MMDD> DAY=<YYYY-MM-DD> \
  && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - "$D" <<'EOF'
import json
import pathlib
import sys

from kubeagent_verdict.dataset import checker

d = pathlib.Path(sys.argv[1])
assert d.name.startswith("dataset-") and d.name != "dataset-0929", d
m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
old = json.loads(pathlib.Path("out/dataset-0929/manifest.json").read_text(encoding="utf-8"))
family = {"shared_origin", "shared_origin_decoy"}
probes = {"shared_origin_probe", "shared_origin_decoy_probe"}
assert len(checker.RULES) == 50, len(checker.RULES)
assert (m["seed"], m["size"]) == (17, 8000), (m["seed"], m["size"])
assert sorted(m) == sorted(old), sorted(set(m) ^ set(old))
bad = {k: v for k, v in m["checker_violations"].items() if v}
assert not bad, f"checker violations: {bad}"
assert sorted(m["checker_violations"]) == sorted(old["checker_violations"])
assert m["test"] == 249, m["test"]
tc, otc = m["test_case_counts"], old["test_case_counts"]
assert {k: tc[k] for k in probes} == {k: 10 for k in probes}, tc
assert {k: v for k, v in tc.items() if k not in probes} == {
    k: v for k, v in otc.items() if k not in probes}, "a non-family exam case count moved"
assert m["train"] + m["val"] <= 8000, (m["train"], m["val"])
n = sum(1 for ln in (d / "test.jsonl").read_text(encoding="utf-8").splitlines() if ln)
assert n == 249, n
cc, occ = m["case_counts"], old["case_counts"]
assert (cc["shared_origin"], cc["shared_origin_decoy"]) == (1200, 1200), cc
assert {k: v for k, v in cc.items() if k not in family} == {
    k: v for k, v in occ.items() if k not in family}, "a non-family case count moved"


def others(folder, name):
    lines = (folder / name).read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln and json.loads(ln)["meta"]["case"] not in family]


for name in ("train.jsonl", "val.jsonl"):
    a, b = others(pathlib.Path("out/dataset-0929"), name), others(d, name)
    assert a == b, f"{name}: a non-family row moved ({len(a)} rows before, {len(b)} now)"
    print(f"{name}: {len(b)} non-family rows, byte-identical to dataset-0929")
print("train", old["train"], "->", m["train"], "| val", old["val"], "->", m["val"],
      "| test", old["test"], "->", m["test"])
for k in sorted(cc):
    print(f"case {k}: {occ[k]} -> {cc[k]}")
print("corpus files", m["corpus_files"])
print("GATE OK")
EOF
```

It checks:
- the checker has 50 rules, and every case in the manifest has 0 checker violations;
- seed 17 and size 8000, and the manifest has the same keys as dataset-0929's;
- the exam is 249 rows, with 10 `shared_origin_probe` and 10 `shared_origin_decoy_probe`, and every other exam case count is unchanged;
- the family has 1,200 `shared_origin` and 1,200 `shared_origin_decoy` rows (spec §7: 1,200 pairs at size 8000), and every other case count is unchanged;
- every train and val row outside the family is byte-identical to dataset-0929's, in the same order. (On the tree before this plan, `kv-dataset --seed 17 --size 8000` rebuilds dataset-0929 byte for byte, checked 2026-10-03. So any change here comes from this plan.)

Expected: the per-file lines, the counts, and `GATE OK` last. If an
assert fires, stop. Commit nothing, keep the folder, and report
DONE_WITH_CONCERNS with the assert's message and everything printed
before it.

- [ ] **Step 4: Measure what moved on the exam**

First, the 229 other-family exam rows, byte for byte:

```bash
cd /home/ubuntu/git/kubeagent-verdict && D=out/dataset-<MMDD> DAY=<YYYY-MM-DD> \
  && cmp <(head -n 229 out/dataset-0929/test.jsonl) <(head -n 229 "$D/test.jsonl") && echo "229 SAME"
```

Expected: `229 SAME`. If `cmp` prints a difference, stop, commit nothing,
and report DONE_WITH_CONCERNS with its output.

Then the measure:

```bash
cd /home/ubuntu/git/kubeagent-verdict && D=out/dataset-<MMDD> DAY=<YYYY-MM-DD> \
  && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - "$D" "$DAY" <<'EOF'
import json
import pathlib
import sys
from collections import Counter

from kubeagent_verdict.dataset import generate
from kubeagent_verdict.evals import score

sys.path.insert(0, "tests")
import test_exam_graded_view as g
import test_shared_origin_training as t

d = pathlib.Path(sys.argv[1])
assert d.name.startswith("dataset-") and d.name != "dataset-0929", d
day = sys.argv[2]


def load(p):
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln]


def flagged(r):
    return [v["workload"] for v in json.loads(r["messages"][2]["content"])["verdicts"]]


old = load(pathlib.Path("out/dataset-0929/test.jsonl"))
bank = load(pathlib.Path("out/dataset-0928/test.jsonl"))
new = load(d / "test.jsonl")
exam = generate.test_set()
gen = [json.loads(json.dumps(generate.to_row(e), ensure_ascii=False)) for e in exam]
assert len(old) == len(bank) == len(new) == 249
assert new == gen, "test.jsonl is not generate.test_set()"
assert [r["messages"] for r in old] == [r["messages"] for r in bank], "0928 and 0929 messages differ"
assert new[:229] == old[:229], "a row outside the family moved"
assert [r["meta"]["case"] for r in new[229:]] == (
    ["shared_origin_probe"] * 10 + ["shared_origin_decoy_probe"] * 10)
ec = sum("expected_cause" in r["meta"] for r in new)
econf = sum("expected_confidence" in r["meta"] for r in new)
print("expected_cause rows", ec, "expected_confidence rows", econf)
assert (ec, econf) == (209, 209), "Ruling 8: the family rows carry neither"


def moved(a, b):
    return {
        "system": sum(x["messages"][0] != y["messages"][0] for x, y in zip(a, b)),
        "user": sum(x["messages"][1] != y["messages"][1] for x, y in zip(a, b)),
        "gold": sum(x["messages"][2] != y["messages"][2] for x, y in zip(a, b)),
        "flagged": sum(flagged(x) != flagged(y) for x, y in zip(a, b)),
        "meta": sum(x["meta"] != y["meta"] for x, y in zip(a, b)),
    }


probe, decoy = moved(old[229:239], new[229:239]), moved(old[239:], new[239:])
fam = {k: probe[k] + decoy[k] for k in probe}
print("moved, shared_origin_probe (10 rows):", probe)
print("moved, shared_origin_decoy_probe (10 rows):", decoy)
ok_top = set().union(*(r["meta"] for r in old[229:]))
nk_top = set().union(*(r["meta"] for r in new[229:]))
ok_w = set().union(*(w for r in old[229:] for w in r["meta"]["workloads"].values()))
nk_w = set().union(*(w for r in new[229:] for w in r["meta"]["workloads"].values()))
print("row meta keys removed", sorted(ok_top - nk_top), "added", sorted(nk_top - ok_top))
print("workload meta keys removed", sorted(ok_w - nk_w), "added", sorted(nk_w - ok_w))
print("labels was", dict(Counter(r["meta"]["label"] for r in old[229:])),
      "now", dict(Counter(r["meta"]["label"] for r in new[229:])))
print("origins was", sorted({r["meta"]["origin"] for r in old[229:]}),
      "now", sorted({r["meta"]["origin"] for r in new[229:]}))
print("family workloads was", sum(len(flagged(r)) for r in old[229:]),
      "now", sum(len(flagged(r)) for r in new[229:]))


def jobs(rows):
    gold = iter(r["messages"][2]["content"] for r in rows)
    res = score.evaluate(rows, lambda _m: next(gold), grade_job2=True)
    j1 = [s for r in res for s in r["job1_scores"]]
    j2 = [s for r in res for s in r["job2_scores"]]
    fam1 = [s for r in res[229:] for s in r["job1_scores"]]
    fam2 = [s for r in res[229:] for s in r["job2_scores"]]
    j3 = score.scoreboard(res)["jobs"]["job3"]
    return {"job1": (len(j1), sum(j1)), "job2": (len(j2), sum(j2)),
            "family job1": len(fam1), "family job2": len(fam2),
            "job3": (j3["n"], {k: v["n"] for k, v in j3["by_label"].items()})}


print("exam jobs, oracle-read, was", jobs(old))
print("exam jobs, oracle-read, now", jobs(new))

frozen_new = t._digest(exam[:-10])
eval_new = t._digest(exam)
graded_new = g._digest(g._views())
print("FROZEN_SLICE_SHA256", t.FROZEN_SLICE_SHA256, "->", frozen_new)
print("EVAL_SET_SHA256", t.EVAL_SET_SHA256, "->", eval_new)
print("GRADED_VIEW_SHA256", g.GRADED_VIEW_SHA256, "->", graded_new)
assert frozen_new != t.FROZEN_SLICE_SHA256, "the frozen slice did not move"
assert eval_new != t.EVAL_SET_SHA256, "the eval set did not move"
assert graded_new != g.GRADED_VIEW_SHA256, "the graded view did not move"

removed = ", ".join(f"`{k}`" for k in sorted(ok_top - nk_top)) or "no key"
sysline = ("No system message moves." if fam["system"] == 0
           else f"{fam['system']} system messages move.")
print(f"""
===== tests/test_shared_origin_training.py, before `FROZEN_SLICE_SHA256 =` =====
#
# {day} (Spec 4b-1): the shared-origin family is rebuilt on kubeagent's
# real pipeline (2026-10-03-shared-origin-rewrite-design.md). The slice
# stays at 239 rows. Its 10 `shared_origin_probe` rows move: {probe['user']} user
# messages, {probe['gold']} gold answers and {probe['meta']} metas; their meta drops
# {removed}. The other 229 rows do not move
# (`OTHER_FAMILIES_SHA256` in tests/test_generate.py). Every number banked
# against the old bytes is retired.
# {t.FROZEN_SLICE_SHA256} ->
# {frozen_new}
FROZEN_SLICE_SHA256 = "{frozen_new}"

===== tests/test_shared_origin_training.py, before `EVAL_SET_SHA256 =` =====
#
# {day} (Spec 4b-1): the shared-origin rows are rebuilt on kubeagent's
# real pipeline, which moved `FROZEN_SLICE_SHA256` above. The ten
# `shared_origin_decoy_probe` rows move too: {decoy['user']} user messages,
# {decoy['gold']} gold answers and {decoy['meta']} metas.
# {t.EVAL_SET_SHA256} ->
# {eval_new}
EVAL_SET_SHA256 = "{eval_new}"

===== tests/test_exam_graded_view.py, before `GRADED_VIEW_SHA256 =` =====
# {day} (Spec 4b-1): the 20 shared-origin rows are rebuilt on kubeagent's
# real pipeline; {fam['user']} user messages and {fam['flagged']} flagged lists move, and
# no other row moves
# {g.GRADED_VIEW_SHA256} ->
# {graded_new}
GRADED_VIEW_SHA256 = "{graded_new}"

===== tests/test_exam_graded_view.py, the docstring's last paragraph (append) =====
Re-pinned on {day} for Spec 4b-1
(2026-10-03-shared-origin-rewrite-design.md). The 20 shared-origin exam
rows -- 10 `shared_origin_probe` and 10 `shared_origin_decoy_probe` --
are rebuilt on kubeagent's real pipeline: real report order, the gather,
the rules over every candidate, and gold taken from each victim's own
lines. {fam['user']} of their 20 user messages and {fam['gold']} of their 20 gold answers
change, and the `flagged` list moves on {fam['flagged']} of them. Their meta drops
{removed}. The other 229 rows are byte for byte the old
ones (`OTHER_FAMILIES_SHA256` in `tests/test_generate.py`). {sysline}

===== tests/test_exam_graded_view.py, the docstring's "Two gold fields" sentence =====
replace the two lines
single-workload row mirrors them: `expected_cause` on 209 of the 249
rows and `expected_confidence` on 219 (211 and 221 of 251 before the
with the four lines
single-workload row mirrors them: `expected_cause` on {ec} of the 249
rows and `expected_confidence` on {econf} (209 and 219 until {day},
when the 10 `shared_origin_probe` rows stopped carrying
`expected_confidence`; 211 and 221 of 251 before the

===== tests/test_exam_prompt_stability.py, the docstring's first paragraph =====
replace the two lines
`out/dataset-0928/test.jsonl` is the exam the faithful prompts
(2026-09-25-faithful-prompts-design.md) bank: 249 rows, and a new
with the two lines
`out/{d.name}/test.jsonl` is the exam Spec 4b-1
(2026-10-03-shared-origin-rewrite-design.md) banks: 249 rows, and a new

===== tests/test_exam_prompt_stability.py, BANK and its comment =====
# {day} (Spec 4b-1): the 20 shared-origin exam rows are rebuilt on real
# lines; re-pointed, dataset-0928 -> {d.name}
BANK = Path(__file__).resolve().parents[1] / "out" / "{d.name}" / "test.jsonl"

===== tests/test_exam_prompt_stability.py, the paragraph before "Until 2026-09-28" =====
Until {day} it pointed at `out/dataset-0928/test.jsonl`. Spec 4b-1
(2026-10-03-shared-origin-rewrite-design.md) rebuilds the 20
shared-origin exam rows on kubeagent's real pipeline: {fam['user']} of their user
messages and {fam['gold']} of their gold answers move, so that bank no longer
matches this generator. The other 229 rows' messages are the ones it
banked.
""")
EOF
```

It checks, and stops at the first that fails:
- the new `test.jsonl` is `generate.test_set()`, row for row;
- dataset-0928 and dataset-0929 have the same messages, so the bank the stability test reads today matches dataset-0929's prompts;
- the first 229 rows equal dataset-0929's, and the last 20 are 10 `shared_origin_probe` then 10 `shared_origin_decoy_probe`;
- `expected_cause` sits on 209 rows and `expected_confidence` on 209 (Ruling 8: the family's rows carry neither; the 10 probe rows carried `expected_confidence` until now, 219 in all);
- each of the three hashes moved.

Then it prints, for the report: the moved counts for the 20 family rows
(system, user, gold, `flagged`, meta), the meta keys removed and added,
the labels and origins was → now, the family's workload count, the
oracle's job counts on the exam was → now (job 1, job 2, the family's
share of each, and job 3 by label), and the three hashes old → new.
Last, it prints eight paste-ready blocks for Step 5, each under a
`=====` header that names the file and the place.

Expected: every check passes and every line prints. The numbers are what
they are: no pin and no bar moves to fit them. If a check fails, stop.
Commit nothing, keep the folder, and report DONE_WITH_CONCERNS with the
message and every line printed before it.

Note two things the spec predicts for the job counts (spec "The build
and the re-pin" §3): job 1 and job 2 on the exam move, because the
family's victims become named, decided or `none_of_these`, and some
origins get a row. Today they are 120 and 177. Task 9 already re-pinned
`tests/test_oracle.py` to the new counts; the "now" line here must match
those pins, and Step 6 runs `tests/test_oracle.py` to prove it.

- [ ] **Step 5: Paste the printed blocks**

Each block from Step 4 goes in exactly one place. Copy it as printed.

1. `tests/test_shared_origin_training.py`, block "before `FROZEN_SLICE_SHA256 =`": replace the line `FROZEN_SLICE_SHA256 = "f3d05a3d…"` with the whole block. The old history comment above it stays; the block's first line, `#`, separates the new entry from it, as the other entries are separated.
2. Same file, block "before `EVAL_SET_SHA256 =`": replace the line `EVAL_SET_SHA256 = "a5304170…"` with the whole block, the same way.
3. `tests/test_exam_graded_view.py`, block "before `GRADED_VIEW_SHA256 =`": replace the line `GRADED_VIEW_SHA256 = "efed5140…"` with the whole block. This file's history entries have no `#` separator line, and the block has none.
4. Same file, block "the docstring's last paragraph (append)": add it as the module docstring's last paragraph — after the paragraph that starts "Re-pinned again on 2026-09-26, when the suggested fix line", with one blank line between, and before the closing `"""`.
5. Same file, block "the docstring's "Two gold fields" sentence": replace the two lines it names with the four lines it gives.
6. `tests/test_exam_prompt_stability.py`, block "the docstring's first paragraph": replace the two lines it names with the two lines it gives.
7. Same file, block "the paragraph before "Until 2026-09-28"": insert it as a new paragraph directly before the paragraph that starts "Until 2026-09-28 it pointed at", with one blank line after it.
8. Same file, block "BANK and its comment": replace the line `BANK = Path(__file__)…"dataset-0928"…` with the block. The 2026-09-26 and 2026-09-28 comments above it stay.

Then check that only those places changed:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff --stat -- tests/ && git diff -- tests/ | grep '^-[^-]'
```

Expected: three files changed, and exactly seven removed lines: the
three old pin lines, the old `BANK` line, the line
``rows and `expected_confidence` on 219 (211 and 221 of 251 before the``
(block 5's first line is unchanged, so git keeps it), and the two old
lines block 6 replaces. Any other removed line is a paste in the wrong
place: fix it before going on.

- [ ] **Step 6: Run the re-pinned tests, then the whole suite**

Run: `PYTEST -rs tests/test_shared_origin_training.py tests/test_exam_graded_view.py tests/test_exam_prompt_stability.py tests/test_generate.py::test_the_other_families_exam_rows_did_not_move tests/test_oracle.py`
Expected: PASS, and no `SKIPPED` line for `tests/test_exam_prompt_stability.py` (a skip means `BANK` points at a folder that does not exist).

Run: `PYTEST`
Expected: PASS, every test. If anything fails, stop. Commit nothing, and
report DONE_WITH_CONCERNS with the failures.

- [ ] **Step 7: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add tests/test_shared_origin_training.py tests/test_exam_graded_view.py \
       tests/test_exam_prompt_stability.py \
  && COMMIT "test: re-pin the frozen slice, eval set and graded view, and re-point the banked exam, for the rebuilt shared-origin rows"
```

The build folder is not committed. The report carries every line Steps
2, 3 and 4 printed, so Task 11 can quote them.

---

### Task 11: The docs — PIN.md, the model card, and four short edits

The build is done and the three pins have moved. This task writes it
down. It edits five documents and changes nothing else: no source file,
no test, no bar.

The docs carry many numbers: pairs per story, answer shares, hashes, job
counts. A number typed by hand can be wrong, so none is. A script
(`measure.py`) reads the new bank and the old bank (`out/dataset-0929`),
checks them against what Tasks 8 and 10 reported, and writes every number
to `facts.json`. A second script (`apply_edits.py`) fills those numbers
into the edits and writes the docs. If a check fails, the task stops and
nothing is written.

The title's "four short edits" are `docs/how-training-works.md`,
`docs/design.md`, `README.md` and one re-check of `docs/runbooks/train.md`.
The re-check edits nothing.

The old text stays. An older item is closed by a dated note placed after
it, never by deleting it. The only old lines this task rewrites are the
ones the spec names: model-card limit 6, two rows of a table in
`how-training-works.md`, one row of a second table in it, and two rows of
`design.md`.

**Files:**
- Create (never committed; in `/tmp/kv-task11`, outside the repo): `reported.json`, `facts.json`, `measure.log`, and the scripts and edit lists the steps write there: `measure_core.py`, `measure.py`, `apply_edits.py`, `edits_pin.txt`, `edits_card.txt`, `edits_guides.txt`.
- Modify: `contract/PIN.md` — a dated note after each of five older items (:420-421, :424-425, :428-429, B4 at :537-539 and :647, a node's state at :547 and :651; seven notes in all), and a new entry at the end of the file, "Dataset pin moves".
- Modify: `docs/model-card.md` — a note under each of the two 0920 headings (:798, :864); a dated note on limits 1 to 5 (:941-974) and 7 to 9 (:1010-1037); limit 6 (:975-992) rewritten; a new limit 15 after limit 14 (:1124-1125).
- Modify: `docs/how-training-works.md` — the `shared_origin` and `shared_origin_decoy` rows of the case table (:92-93); the `shared_origin_decoy_probe` row of the exam table (:213); a dated note after :390.
- Modify: `docs/design.md` — the two table rows at :280-281; a dated paragraph after :413.
- Modify: `README.md` — a dated note after the twin paragraph (:154-156).
- Check only: `docs/runbooks/train.md` — the exam is still 249 rows there (:77, :103, :525-530). No edit.
- Not touched: old specs and plans, anything under `out/`, `src/kubeagent_verdict/evals/score.py`, `src/kubeagent_verdict/contract.py`, and every test.
- Line numbers above are from the start of the branch. Earlier tasks may have moved them (Task 1's capture record sits above the PIN.md items). The edits match text, never a line number.

**Interfaces:**
- Consumes (Task 8, Step 5 report): the five lines `floor: min N max N`, `balance: broken (..) healthy (..) gap X`, `ceiling: (n, d) share`, `label cue: {...}` and `three-verdict: wide decoys ratio [...]`. Step 2 copies the numbers into `reported.json`. Step 5 counts each one again from the new `train.jsonl` and stops if it differs.
- Consumes (Task 9, part D): the regenerated `WEAK_PAIRS` in `tests/test_answer_keys.py`. Step 5 reads `len(WEAK_PAIRS)` itself, so no number is copied.
- Consumes (Task 10 report): Step 2's last line `D=out/dataset-<MMDD> DAY=<YYYY-MM-DD>` and its three sha256 lines; Step 3's gate lines (the train, val and test counts and the case counts); Step 4's lines (the moved counts for the 20 family rows, the meta keys removed, the labels and origins was → now, the family's workload count, the oracle job counts was → now, the three hashes old → new). Step 2 copies the folder, the day, the three sha256s, the three new hashes and the job 1 and job 2 counts into `reported.json`. Step 5 counts the rest again and checks it against those.
- Consumes (Task 1): the PIN.md section `## Capture record (v1.24.0, cluster and registry capture)`, and its sentence that built rows reach the registry no-pull sentence 0 times. Step 1 checks the section is there. Step 5 checks the sentence is true of the new bank.
- Consumes: `out/dataset-0929` (the old bank, on disk) and `out/dataset-<MMDD>` (the new one); `generate.test_set()`, `generate.to_row(e)`, `generate.shared_origin_cousin_probes()`; `stories.trainable()` with `Story.key` and `.cls`; `propagation.trainable_scenarios()`; `score.evaluate(rows, chat_fn, *, grade_job2=True)` and `score.scoreboard(results)`; `tests/test_shared_origin_training.py` (`_digest`, `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256`); `tests/test_exam_graded_view.py` (`_digest`, `_views`, `GRADED_VIEW_SHA256`).
- Produces: five edited docs, committed. Nothing else leaves this task. The report carries `measure.log`, so a reader can see every number the docs now hold.

- [ ] **Step 1: Preflight — read only**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'EOF'
import pathlib
import subprocess


def git(*a):
    return subprocess.run(("git",) + a, capture_output=True, text=True, check=True).stdout


assert git("branch", "--show-current").strip() == "spec4b1-shared-origin", "wrong branch"
allowed = {"M .gitignore", "?? train-v2.log", "?? docs/superpowers/plans/2026-10-03-shared-origin-rewrite.md"}
odd = [ln for ln in git("status", "--short").splitlines() if ln.strip() not in allowed]
assert not odd, f"the tree is not clean: {odd}"
assert "re-pin the frozen slice" in git("log", "--oneline", "-15"), "Task 10's commit is not on this branch"
pin = pathlib.Path("contract/PIN.md").read_text(encoding="utf-8")
assert "## Capture record (v1.24.0, cluster and registry capture)" in pin, "Task 1's capture record is missing"
assert "15ec5649bbd2d07558eae945b71430afc8f231fd" in pin, "the full kubeagent commit is not in PIN.md"
for p in ("out/dataset-0929/train.jsonl", "out/dataset-0929/val.jsonl", "out/dataset-0929/test.jsonl", "data/corpus"):
    assert pathlib.Path(p).exists(), f"missing: {p}"
print("preflight ok")
EOF
mkdir -p /tmp/kv-task11 && ls -d /tmp/kv-task11
```

Expected: `preflight ok`, then `/tmp/kv-task11`. If an assertion fails, stop.
A wrong branch, a dirty tree or a missing Task 10 commit means an earlier
task is not finished: report BLOCKED with the message. A missing capture
record or hash means Task 1 left its PIN.md section out: report BLOCKED
and name it. This task does not write that section; it only points to it.

- [ ] **Step 2: Copy the Task 8 and Task 10 numbers into `reported.json`**

Fill each `<<…>>` mark with the number or text it names, and remove the
`<<` and `>>`. Numbers stay bare; text stays in its quotes. Task 8's
numbers come from its Step 5 report lines. Task 10's come from its Step 2
and Step 4 report lines. If a number is missing from either report, stop
and report NEEDS_CONTEXT. Do not work one out by hand.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/reported.json" <<'KV_EOF'
{
 "t8": {
  "floor_min": <<T8: the number after "floor: min">>,
  "floor_max": <<T8: the number after "max" on the same "floor:" line>>,
  "balance_gap": <<T8: the number after "gap" on the "balance:" line, as printed, for example 0.0123>>,
  "ceiling": <<T8: the last number on the "ceiling:" line, as printed, for example 0.1873>>,
  "cue_shared": <<T8: the count printed under 'shared' in the "label cue:" dict; 0 if the key is absent>>,
  "cue_none": <<T8: the count printed under 'none' in the "label cue:" dict; 0 if the key is absent>>,
  "wide": <<T8: the first number on the "three-verdict:" line>>,
  "wide_of": <<T8: the second number on the "three-verdict:" line>>
 },
 "t10": {
  "folder": "<<T10: the folder name in Step 2's last line, for example dataset-1004>>",
  "day": "<<build day>>",
  "sha": {
   "train": "<<T10: the sha256 Step 2 printed for train.jsonl>>",
   "val": "<<T10: the sha256 Step 2 printed for val.jsonl>>",
   "test": "<<T10: the sha256 Step 2 printed for test.jsonl>>"
  },
  "pins": {
   "FROZEN_SLICE_SHA256": "<<T10: the NEW hash in Step 4's FROZEN_SLICE_SHA256 old -> new line>>",
   "EVAL_SET_SHA256": "<<T10: the NEW hash in Step 4's EVAL_SET_SHA256 old -> new line>>",
   "GRADED_VIEW_SHA256": "<<T10: the NEW hash in Step 4's GRADED_VIEW_SHA256 old -> new line>>"
  },
  "jobs": {
   "job1": <<T10: the "now" workload count for job 1 in Step 4's oracle line>>,
   "job2": <<T10: the "now" workload count for job 2 in Step 4's oracle line>>
  }
 }
}
KV_EOF
.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["t10"]["folder"], d["t10"]["day"])' "$S/reported.json" \
  && { ! grep -n '<<\|>>' "$S/reported.json"; }
```

Expected: one line, the folder and the day (for example
`dataset-1004 2026-10-04`), and nothing after it. A traceback means a
mark is still there or a quote is missing: fix the file and run the check
again. The `<<build day>>` mark is the `DAY` value from Task 10's Step 2
line. Every dated note in the docs uses that day.

- [ ] **Step 3: Write `measure_core.py`**

The helpers. They are pure: they read rows and count, and they import
nothing from `kubeagent_verdict`. There is one counter for each model-card
limit this task re-measures: what a prompt shows against what a rationale
says (limits 1, 2, 4 and 9), how a prompt prints a claim (limit 3), how
many decided workloads use the template (limit 5), how a node's heading is
spelled (limit 8), and how many rows carry a decoy (limit 7). The same
counter runs on `out/dataset-0929` and on the new bank, so every
was-against-now pair in the docs compares like with like. The mix counters
give limits 6 and 15. The last helper runs the oracle: it scores the gold
reply as if the model had sent it.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/measure_core.py" <<'KV_EOF'
"""Task 11: the counts the docs quote.  Pure functions: no printing, no writes."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FAMILY = {"shared_origin", "shared_origin_decoy"}
EXAM_FAMILY = {"shared_origin_probe", "shared_origin_decoy_probe"}
SPLITS = ("train", "val", "test")
NONE_OF_THESE = "none_of_these"


def load(bank, split):
    text = (Path(bank) / f"{split}.jsonl").read_text(encoding="utf-8")
    return [json.loads(ln) for ln in text.splitlines() if ln]


def user(r):
    return r["messages"][1]["content"]


def verdicts(r):
    return json.loads(r["messages"][2]["content"])["verdicts"]


def is_family(r):
    return r["meta"]["case"] in FAMILY | EXAM_FAMILY


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Each detector returns (seen, bad) for ONE row: seen is True when the row has
# something the detector can judge, bad is True when what it judges is wrong.
# A detector that sees nothing in a whole split proves nothing, and the caller
# refuses to read "0 bad" from "0 seen".

# --- limit 1: a rationale's Ready word against the Ready word the prompt shows
def ready(r):
    shown = set(re.findall(r"^\s*Ready\s+(True|False|Unknown)\b", user(r), re.M))
    shown |= set(re.findall(r"Ready=(True|False|Unknown)", user(r)))
    seen = bad = False
    for v in verdicts(r):
        m = re.search(r"ready condition is (True|False|Unknown)", v["rationale"], re.I)
        if m and shown:
            seen = True
            bad = bad or m.group(1) not in shown
    return seen, bad


# --- limit 2: one node named under two different reasons in one row
NODE_CAUSE = re.compile(r"\bnode (\S+?)(?: \(([^)]+)\)| ((?:\S+ ){0,3}\S+))")


def node_reasons(r):
    texts = [v["cause"] for v in verdicts(r)]
    for line in user(r).splitlines():
        line = line.strip()
        if line.startswith("considered node ") or line.startswith("decided by rules: node "):
            texts.append(line.split("decided by rules: ")[-1].replace("considered ", "", 1))
    out = {}
    for t in texts:
        m = NODE_CAUSE.match(t.strip().replace("decided by rules: ", ""))
        if m:
            out.setdefault(m.group(1), set()).add((m.group(2) or m.group(3) or "").rstrip(":,"))
    bad = False
    for reasons in out.values():
        kept = []
        for reason in sorted(reasons, key=len):
            if not any(k in reason for k in kept):
                kept.append(reason)
        bad = bad or len(kept) > 1
    return bool(out), bad


# --- limit 4: "N workloads" in a cause against the number of workloads flagged
def counts(r):
    n = len(r["meta"]["workloads"])
    said = [int(m) for v in verdicts(r) for m in re.findall(r"\b(\d+) workloads?\b", v["cause"])]
    return bool(said), any(x != n for x in said)


# --- limits 5 and 9: the rule-rationale template
TEMPLATE = re.compile(
    r"^The fresh read of (node|claim|registry) \S+ (?:confirms it:|did not clear the earlier finding:) .*"
    r"(?:so the (?:node|claim|registry)'s own state is why the flagged workload is failing\.|"
    r"stays the named cause rather than something the read ruled out\.)$", re.S)
QUOTED = re.compile(
    r"^The fresh read of \S+ \S+ (?:confirms it:|did not clear the earlier finding:) (.*?), so ")


def decided(r):
    by = {v["workload"]: v for v in verdicts(r)}
    for w, wm in r["meta"]["workloads"].items():
        if wm.get("job") == 1 and w in by:
            yield by[w]


def template_rows(r):
    """(template rationales on decided workloads, of those the ones that quote a read the prompt never shows)."""
    lines = [ln.lower() for ln in user(r).splitlines() if "fresh read:" in ln]
    tpl = bad = 0
    for v in decided(r):
        if TEMPLATE.match(v["rationale"]):
            tpl += 1
            m = QUOTED.match(v["rationale"])
            if m and not any(m.group(1).lower() in ln for ln in lines):
                bad += 1
    return tpl, bad


# --- limit 8: how a node's describe heading is spelled
SLASH = re.compile(r"(?m)^== describe node /[\w.-]+ ==$")
PLAIN = re.compile(r"(?m)^== describe node [\w.-]+ ==$")

# --- limit 3: a claim's phase as the prompt prints it
CLAIM = re.compile(r"(?m)^== describe (\S+) \(PersistentVolumeClaim\) ==\n(?:.*\n)*?Status: (\w+)")
CLAIM_GO = re.compile(r"(?m)^== describe pvc (\S+) ==\npvc \S+: phase=(\w+)")


def unverified(r):
    return any(w["decided_outcome"] == "unverified" for w in r["meta"]["workloads"].values())


def share(rs):
    vs = [v for r in rs for v in verdicts(r)]
    return sum(v["cause"] == NONE_OF_THESE for v in vs), len(vs)


def split_stats(rows):
    """Every count the model card quotes about one split of one bank."""
    fam = [r for r in rows if is_family(r)]
    m = {"rows": len(rows), "fam": len(fam)}
    for name, fn in (("l1", ready), ("l2", node_reasons), ("l4", counts)):
        res = [fn(r) for r in fam]
        m[f"{name}_seen"] = sum(s for s, _b in res)
        m[f"{name}_bad"] = sum(b for _s, b in res)
    m["l3_claim_rows"] = m["l3_two"] = 0
    phases = Counter()
    for r in fam:
        per = {}
        for rx in (CLAIM, CLAIM_GO):
            for mt in rx.finditer(user(r)):
                per.setdefault(mt.group(1), set()).add(mt.group(2))
        m["l3_claim_rows"] += bool(per)
        for ph in per.values():
            phases.update(ph)
            m["l3_two"] += len(ph) > 1
    m["l3_phases"] = ", ".join(f"{k} {v}" for k, v in sorted(phases.items())) or "none"
    m["l5_all_total"] = sum(1 for r in rows for _ in decided(r))
    m["l5_all_tpl"] = sum(template_rows(r)[0] for r in rows)
    m["l5_fam_total"] = sum(1 for r in fam for _ in decided(r))
    m["l9_seen"] = sum(template_rows(r)[0] for r in fam)
    m["l9_bad"] = sum(template_rows(r)[1] for r in fam)
    m["l5_fam_tpl"] = m["l9_seen"]
    slash = plain = both = 0
    for r in fam:
        a, b = bool(SLASH.search(user(r))), bool(PLAIN.search(user(r)))
        slash += a and not b
        plain += b and not a
        both += a and b
    m["l8_slash"], m["l8_plain"], m["l8_both"] = slash, plain, both
    m["l7_decoy"] = sum(1 for r in fam if any(r["meta"]["decoy_by_workload"].values()))
    m["none_all"], m["verd_all"] = share(rows)
    return m


def mix_stats(rows, cls):
    """Floor, balance, ceiling, label cue and three-verdict for ONE split (train), as spec 7 defines them.
    `cls` maps a story key to "P" or "R"."""
    broken = [r for r in rows if r["meta"]["case"] == "shared_origin"]
    healthy = [r for r in rows if r["meta"]["case"] == "shared_origin_decoy"]
    pairs = Counter(r["meta"]["origin"] for r in broken)
    m = {"stories": len(pairs), "floor_min": min(pairs.values()), "floor_max": max(pairs.values())}
    for c in ("P", "R"):
        per = {k: n for k, n in pairs.items() if cls[k] == c}
        sel = [r for r in broken if cls[r["meta"]["origin"]] == c]
        ok = [r for r in sel if not unverified(r)]
        lab = Counter(r["meta"]["label"] for r in ok)
        m[f"{c}_stories"], m[f"{c}_pairs"] = len(per), sum(per.values())
        m[f"{c}_low"], m[f"{c}_high"] = min(per.values()), max(per.values())
        m[f"{c}_checked"], m[f"{c}_shared"], m[f"{c}_none"] = len(ok), lab["shared"], lab["none"]
    un = [r for r in broken if unverified(r)]
    m["unverified"] = len(un)
    m["unverified_none"] = sum(r["meta"]["label"] == "none" for r in un)
    m["healthy"] = len(healthy)
    m["healthy_none"] = sum(r["meta"]["label"] == "none" for r in healthy)
    m["share_broken"], m["share_healthy"] = share(broken), share(healthy)
    m["share_bank"] = share(rows)
    ends = Counter()
    for key, c in cls.items():
        if c != "P" or key not in pairs:
            continue
        lab = Counter(r["meta"]["label"] for r in broken if r["meta"]["origin"] == key)
        top = lab.most_common()
        ends["tie" if len(top) > 1 and top[0][1] == top[1][1] else top[0][0]] += 1
    m["cue_shared"], m["cue_none"], m["cue_tie"] = ends["shared"], ends["none"], ends["tie"]
    wide = [r for r in healthy if len(r["meta"]["expected"]) >= 3]
    m["wide"], m["wide_of"] = len(wide), len(healthy)
    return m


def jobs(rows, score):
    """The oracle's job counts when the model's reply is the gold reply (Task 10 prints the same)."""
    gold = iter(r["messages"][2]["content"] for r in rows)
    res = score.evaluate(rows, lambda _m: next(gold), grade_job2=True)
    j1 = [s for r in res for s in r["job1_scores"]]
    j2 = [s for r in res for s in r["job2_scores"]]
    fam1 = [s for r in res[229:] for s in r["job1_scores"]]
    fam2 = [s for r in res[229:] for s in r["job2_scores"]]
    j3 = score.scoreboard(res)["jobs"]["job3"]
    return {"job1": (len(j1), sum(j1)), "job2": (len(j2), sum(j2)),
            "fam_job1": len(fam1), "fam_job2": len(fam2),
            "job3": (j3["n"], {k: v["n"] for k, v in sorted(j3["by_label"].items())})}


NO_PULL = "no pull event names the failure; events may have aged out"
AUTH = "that can be one image or the whole host"


def count_text(rows, needle):
    """How many rows show `needle` in the prompt (family rows only)."""
    return sum(needle in user(r) for r in rows if is_family(r))


def flagged(r):
    return [v["workload"] for v in verdicts(r)]


def moved(a, b):
    return {
        "system": sum(x["messages"][0] != y["messages"][0] for x, y in zip(a, b)),
        "user": sum(x["messages"][1] != y["messages"][1] for x, y in zip(a, b)),
        "gold": sum(x["messages"][2] != y["messages"][2] for x, y in zip(a, b)),
        "flagged": sum(flagged(x) != flagged(y) for x, y in zip(a, b)),
        "meta": sum(x["meta"] != y["meta"] for x, y in zip(a, b)),
    }


def status(old_bad, new_bad, new_seen):
    """closed / narrowed / unchanged / clean / worse / blind: the word a note opens with."""
    if new_seen == 0:
        return "blind"
    if new_bad > old_bad:
        return "worse"
    if new_bad == 0:
        return "closed" if old_bad else "clean"
    return "narrowed" if new_bad < old_bad else "unchanged"
KV_EOF
wc -l "$S/measure_core.py"
```

Expected: `250 /tmp/kv-task11/measure_core.py`.

- [ ] **Step 4: Write `measure.py`**

The measure and the checks. It reads `reported.json`, builds every fact,
stops on any check that fails, and writes `facts.json`. Each check is a
bar or a number someone else already reported. It never moves one.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/measure.py" <<'KV_EOF'
"""Task 11, Step 4: measure the new bank against dataset-0929, check it, and write facts.json.

usage: measure.py <scratch folder>
The bank folder and the build day come from <scratch folder>/reported.json (Task 10's Step 2 line).
"""
import json
import pathlib
import re
import sys
from collections import Counter

S = pathlib.Path(sys.argv[1])
rep = json.loads((S / "reported.json").read_text(encoding="utf-8"))
t8, t10 = rep["t8"], rep["t10"]
assert re.fullmatch(r"dataset-\d{4}", t10["folder"]), f"folder is not dataset-<MMDD>: {t10['folder']!r}"
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", t10["day"]), f"day is not <YYYY-MM-DD>: {t10['day']!r}"
D = pathlib.Path("out") / t10["folder"]
DAY = t10["day"]
sys.path.insert(0, str(S))
sys.path.insert(0, "tests")

import measure_core as mc  # noqa: E402
import test_answer_keys as ak  # noqa: E402
import test_exam_graded_view as g  # noqa: E402
import test_shared_origin_training as t  # noqa: E402

from kubeagent_verdict.dataset import generate, propagation, stories  # noqa: E402
from kubeagent_verdict.evals import score  # noqa: E402

OLD = pathlib.Path("out/dataset-0929")
# PIN.md, the 2026-09-29 entry: the pins and the bank this build replaces.
OLD_PINS = {
    "FROZEN_SLICE_SHA256": "f3d05a3da5946e8bdcfd56db7538ba9bbae57fa05f5fd232167c56aa8086897a",
    "EVAL_SET_SHA256": "a53041702ffcd794e4077df2c8d7e2dbfd8800192e56ba6b324cbb8e242f06e2",
    "GRADED_VIEW_SHA256": "efed51405ad4822633b1a29a541c6972f57c8e3aa34258d9b1aba5e9d8d9caa4",
}
OLD_BANK = {
    "test": "dd3834efe5b986ec2591ccdf1b0be3e86dec1dd5d235b2a8ae17b219c5dcb2f5",
    "train": "6b8da804eaf2de616979d4296c2950f6522d0e0f0369c350770b36340182042f",
    "val": "e0e79322e3a533f19c5ea6f670ce160ce65a54196b131835a3b0aac7454b649b",
}
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


assert D.name != "dataset-0929" and D.is_dir(), D
for split, want in OLD_BANK.items():
    assert mc.sha256(OLD / f"{split}.jsonl") == want, f"dataset-0929/{split}.jsonl is not the bank PIN.md records"
pin_text = pathlib.Path("contract/PIN.md").read_text(encoding="utf-8")
for name, old in OLD_PINS.items():
    assert old in pin_text, f"{name}: the old value is not in PIN.md"

old_rows = {s: mc.load(OLD, s) for s in mc.SPLITS}
new_rows = {s: mc.load(D, s) for s in mc.SPLITS}
old_stats = {s: mc.split_stats(old_rows[s]) for s in mc.SPLITS}
new_stats = {s: mc.split_stats(new_rows[s]) for s in mc.SPLITS}
cls_old = {p.key: ("R" if p.origin_object is not None else "P") for p in propagation.trainable_scenarios()}
cls_new = {s.key: s.cls for s in stories.trainable()}
old_mix = mc.mix_stats(old_rows["train"], cls_old)
new_mix = mc.mix_stats(new_rows["train"], cls_new)
new_val_mix = mc.mix_stats(new_rows["val"], cls_new)

F = {"DAY": DAY, "D": D.name}


def n(x):
    return f"{x:,}"


def pc(a, b):
    return f"{100 * a / b:.1f}%"


def trio(stats, bad, seen):
    return (f"{n(stats['train'][bad])} of {n(stats['train'][seen])} in train, "
            f"{n(stats['val'][bad])} of {n(stats['val'][seen])} in val and "
            f"{n(stats['test'][bad])} of {n(stats['test'][seen])} in the exam")


def total(stats, key):
    return sum(stats[s][key] for s in mc.SPLITS)


TEXT = {"closed": "Closed for this family.", "clean": "Not found in either build.",
        "narrowed": "Narrower.", "unchanged": "Not closed by this build."}
for lim, bad, seen in (("l1", "l1_bad", "l1_seen"), ("l2", "l2_bad", "l2_seen"),
                       ("l4", "l4_bad", "l4_seen"), ("l9", "l9_bad", "l9_seen")):
    word = mc.status(total(old_stats, bad), total(new_stats, bad), total(new_stats, seen))
    check(word not in ("worse", "blind"), f"limit {lim[1:]}: {word} "
          f"(bad {total(old_stats, bad)} -> {total(new_stats, bad)}, new rows judged {total(new_stats, seen)})")
    F[f"{lim}_status"] = TEXT.get(word, word)
    F[f"{lim}_now"] = trio(new_stats, bad, seen)
    F[f"{lim}_was"] = trio(old_stats, bad, seen)
# limit 8: how a family row spells a node's describe heading
seen8 = sum(new_stats[s]["l8_slash"] + new_stats[s]["l8_plain"] + new_stats[s]["l8_both"] for s in mc.SPLITS)
check(seen8 > 0, "limit 8: no family row prints a node heading, so nothing was judged")
check(total(new_stats, "l8_both") <= total(old_stats, "l8_both"),
      f"limit 8: {total(new_stats, 'l8_both')} rows print both forms, was {total(old_stats, 'l8_both')}")
F["l8_status"] = (
    "Closed for this family. Its rows print one form only: kubeagent's, with the slash."
    if total(new_stats, "l8_plain") == 0 and total(new_stats, "l8_both") == 0 and total(new_stats, "l8_slash") > 0
    else "Not closed. Some family rows still print the story form, without the slash.")


def forms(stats):
    return "; ".join(
        f"{label}: {n(stats['train'][k])} in train, {n(stats['val'][k])} in val, {n(stats['test'][k])} in the exam"
        for label, k in (("kubeagent's form with the slash only", "l8_slash"),
                         ("the story form only", "l8_plain"), ("both forms", "l8_both")))


F["l8_now"], F["l8_was"] = forms(new_stats), forms(old_stats)


def phases(stats):
    return (f"{n(stats['train']['l3_claim_rows'])} train rows, {n(stats['val']['l3_claim_rows'])} val rows and "
            f"{n(stats['test']['l3_claim_rows'])} exam rows show a claim; "
            f"{total(stats, 'l3_two')} of them show one claim with two phases; phases shown in train: "
            f"{stats['train']['l3_phases']}")


F["l3_now"], F["l3_was"] = phases(new_stats), phases(old_stats)


def tpl(stats):
    s = stats
    return (f"{n(s['train']['l5_fam_tpl'])} of {n(s['train']['l5_fam_total'])} decided family workloads in train, "
            f"{n(s['val']['l5_fam_tpl'])} of {n(s['val']['l5_fam_total'])} in val and "
            f"{n(s['test']['l5_fam_tpl'])} of {n(s['test']['l5_fam_total'])} in the exam; across every case, "
            f"{n(s['train']['l5_all_tpl'])} of {n(s['train']['l5_all_total'])} decided workloads in train")


F["l5_now"], F["l5_was"] = tpl(new_stats), tpl(old_stats)

cousin = [generate.to_row(e) for e in generate.shared_origin_cousin_probes()]
cousin_decoy = sum(1 for r in cousin if any(r["meta"]["decoy_by_workload"].values()))
F["cousin_rows"], F["cousin_pairs"], F["cousin_decoy"] = n(len(cousin)), n(len(cousin) // 2), n(cousin_decoy)


def decoys(stats):
    return (f"{n(stats['train']['l7_decoy'])} of {n(stats['train']['fam'])} family rows in train, "
            f"{n(stats['val']['l7_decoy'])} of {n(stats['val']['fam'])} in val and "
            f"{n(stats['test']['l7_decoy'])} of {n(stats['test']['fam'])} in the exam")


F["l7_now"], F["l7_was"] = decoys(new_stats), decoys(old_stats)

# limit 6 and limit 15: the labels and the none_of_these share
for key in ("P_stories", "P_pairs", "P_low", "P_high", "P_checked", "P_shared", "P_none",
            "R_stories", "R_pairs", "R_low", "R_high", "R_checked", "R_shared", "R_none",
            "unverified", "unverified_none", "healthy", "healthy_none", "cue_shared", "cue_none", "cue_tie",
            "wide", "wide_of", "floor_min", "floor_max"):
    F[f"m_{key}"] = n(new_mix[key])
    F[f"v_{key}"] = n(new_val_mix[key])
F["v_P_pairs"], F["v_R_pairs"] = n(new_val_mix["P_pairs"]), n(new_val_mix["R_pairs"])
F["v_P_shared"], F["v_R_shared"] = n(new_val_mix["P_shared"]), n(new_val_mix["R_shared"])
F["v_unverified"] = n(new_val_mix["unverified"])
(bn, bd), (hn, hd), (cn, cd) = new_mix["share_broken"], new_mix["share_healthy"], new_mix["share_bank"]
F["m_share_broken"] = f"{n(bn)} of {n(bd)} = {pc(bn, bd)}"
F["m_share_healthy"] = f"{n(hn)} of {n(hd)} = {pc(hn, hd)}"
F["m_share_bank"] = f"{n(cn)} of {n(cd)} = {pc(cn, cd)}"
F["m_share_bank_pct"] = pc(cn, cd)
F["m_gap_points"] = f"{abs(100 * bn / bd - 100 * hn / hd):.1f}"
on, od = old_mix["share_bank"]
F["o_share_bank"] = f"{n(on)} of {n(od)} = {pc(on, od)}"
F["wide_pct"] = pc(new_mix["wide"], new_mix["wide_of"])
F["v_share_val"] = pc(*new_val_mix["share_bank"])

# the checks that tie this step to Tasks 8 and 10
check(new_mix["floor_min"] >= 12, f"floor: min {new_mix['floor_min']} pairs per story in train, bar is 12")
check(abs(bn / bd - hn / hd) <= 0.10, f"balance: broken {bn / bd:.4f}, healthy {hn / hd:.4f}")
check(cn / cd <= 0.30, f"ceiling: {cn / cd:.4f}")
check(new_mix["cue_shared"] >= 5 and new_mix["cue_none"] >= 5,
      f"label cue: {new_mix['cue_shared']} P stories end shared, {new_mix['cue_none']} end none")
check(new_mix["floor_min"] == t8["floor_min"] and new_mix["floor_max"] == t8["floor_max"],
      f"floor differs from Task 8's report: {new_mix['floor_min']}/{new_mix['floor_max']}")
check(round(abs(bn / bd - hn / hd), 4) == t8["balance_gap"], f"balance gap differs from Task 8's report {t8['balance_gap']}")
check(round(cn / cd, 4) == t8["ceiling"], f"ceiling differs from Task 8's report {t8['ceiling']}")
check((new_mix["cue_shared"], new_mix["cue_none"]) == (t8["cue_shared"], t8["cue_none"]),
      "label cue differs from Task 8's report")
check((new_mix["wide"], new_mix["wide_of"]) == (t8["wide"], t8["wide_of"]),
      f"three-verdict differs from Task 8's report: {new_mix['wide']} of {new_mix['wide_of']}")

# the registry sentences: Task 1's capture record says built rows reach the no-pull one 0 times
F["reg_nopull"] = n(sum(mc.count_text(new_rows[s], mc.NO_PULL) for s in mc.SPLITS))
F["reg_auth"] = n(sum(mc.count_text(new_rows[s], mc.AUTH) for s in mc.SPLITS))
check(F["reg_nopull"] == "0",
      f"Task 1's capture record says built rows reach the registry no-pull sentence 0 times; {F['reg_nopull']} family rows do")
F["weak_pairs"] = str(len(ak.WEAK_PAIRS))

# the manifest, the sha256s, the three pins
man, oman = (json.loads((p / "manifest.json").read_text(encoding="utf-8")) for p in (D, OLD))
for s in mc.SPLITS:
    F[f"{s}_old"], F[f"{s}_new"] = n(oman[s]), n(man[s])
    check(len(new_rows[s]) == man[s], f"{s}.jsonl has {len(new_rows[s])} rows, the manifest says {man[s]}")
    F[f"sha_{s}"] = mc.sha256(D / f"{s}.jsonl")
    check(F[f"sha_{s}"] == t10["sha"][s], f"{s}.jsonl sha256 differs from Task 10's report")
check(man["case_counts"]["shared_origin"] == man["case_counts"]["shared_origin_decoy"] == 1200,
      "the family is not 1,200 pairs at --size 8000: "
      f"{man['case_counts']['shared_origin']} and {man['case_counts']['shared_origin_decoy']}")
F["family_cases"] = (f"{n(man['case_counts']['shared_origin'])} `shared_origin` and "
                     f"{n(man['case_counts']['shared_origin_decoy'])} `shared_origin_decoy`")
# rows outside the family (train and val): are they the rows of dataset-0929? Compared as a
# multiset of whole rows, so a change of order alone is not counted as a change.
FAMILY = {"shared_origin", "shared_origin_decoy"}


def differ(rows_a, rows_b):
    """How many rows of rows_a are not in rows_b (as whole rows)."""
    a = Counter(json.dumps(r, sort_keys=True) for r in rows_a)
    b = Counter(json.dumps(r, sort_keys=True) for r in rows_b)
    return sum((a - b).values())


outside = {}
for kind, pick in (("outside", lambda r: r["meta"]["case"] not in FAMILY),
                   ("multi", lambda r: r["meta"]["case"] == "multi")):
    outside[kind] = {s: (differ([r for r in new_rows[s] if pick(r)], [r for r in old_rows[s] if pick(r)]),
                         len([r for r in new_rows[s] if pick(r)]),
                         len([r for r in old_rows[s] if pick(r)])) for s in ("train", "val")}
OUT_OK = all(d == 0 and nn == oo for d, nn, oo in outside["outside"].values())
MULTI_OK = all(d == 0 and nn == oo for d, nn, oo in outside["multi"].values())
F["outside_status"] = (
    "Every train and val row outside the family is byte for byte the same as in `out/dataset-0929`."
    if OUT_OK else
    "Outside the family, " + " and ".join(
        f"{n(d)} of {n(nn)} {s} rows are not in `out/dataset-0929`"
        for s, (d, nn, oo) in outside["outside"].items()) + ", byte for byte.")
F["multi_status"] = (
    "`multi` is not changed by 4b-1. Every `multi` row is byte for byte the one in `out/dataset-0929`, "
    "so what the text above says about `multi` rows still holds. Spec 4b-3 owns `multi`."
    if MULTI_OK else
    "`multi` is not meant to change in 4b-1, but " + " and ".join(
        f"{n(d)} of {n(nn)} {s} `multi` rows are not in `out/dataset-0929`"
        for s, (d, nn, oo) in outside["multi"].items()) +
    ", byte for byte, so read the text above against the new bank. Spec 4b-3 owns `multi`.")
print("outside the family, rows not in dataset-0929:", outside["outside"])
print("multi, rows not in dataset-0929:", outside["multi"])
exam = generate.test_set()
now_pins = {"FROZEN_SLICE_SHA256": t.FROZEN_SLICE_SHA256, "EVAL_SET_SHA256": t.EVAL_SET_SHA256,
            "GRADED_VIEW_SHA256": g.GRADED_VIEW_SHA256}
calc_pins = {"FROZEN_SLICE_SHA256": t._digest(exam[:-10]), "EVAL_SET_SHA256": t._digest(exam),
             "GRADED_VIEW_SHA256": g._digest(g._views())}
for name in OLD_PINS:
    check(now_pins[name] == calc_pins[name], f"{name}: the test file's pin is not what the generator gives")
    check(now_pins[name] != OLD_PINS[name], f"{name}: did not move")
    check(now_pins[name] == t10["pins"][name], f"{name}: differs from Task 10's report")
    F[f"{name}_old"], F[f"{name}_new"] = OLD_PINS[name], now_pins[name]

# the 20 family exam rows, old against new
o_t, n_t = old_rows["test"], new_rows["test"]
check(len(o_t) == len(n_t) == 249 and o_t[:229] == n_t[:229], "the 229 other-family exam rows moved")
check(all(r["meta"]["case"] in mc.EXAM_FAMILY for r in o_t[229:] + n_t[229:]) and
      not any(r["meta"]["case"] in mc.EXAM_FAMILY for r in n_t[:229]),
      "the 20 shared-origin exam rows are not the last 20 rows")
fam_moved = mc.moved(o_t[229:], n_t[229:])
for k, v in fam_moved.items():
    F[f"moved_{k}"] = str(v)
top_o = set().union(*(r["meta"] for r in o_t[229:]))
top_n = set().union(*(r["meta"] for r in n_t[229:]))
F["meta_removed"] = ", ".join(f"`{k}`" for k in sorted(top_o - top_n)) or "no key"
F["meta_added"] = ", ".join(f"`{k}`" for k in sorted(top_n - top_o)) or "no key"
for key, short in (("expected_cause", "ec"), ("expected_confidence", "ecf")):
    F[f"{short}_was"] = n(sum(1 for r in o_t if key in r["meta"]))
    F[f"{short}_now"] = n(sum(1 for r in n_t if key in r["meta"]))
check(len({r["meta"]["origin"] for r in n_t[229:]}) == 6,
      "the README, how-training-works.md and the card say the 20 exam rows come from 6 stories; "
      f"the new rows name {len({r['meta']['origin'] for r in n_t[229:]})} origins")
F["labels_was"] = ", ".join(f"{k} {v}" for k, v in sorted(Counter(r["meta"]["label"] for r in o_t[229:]).items()))
F["labels_now"] = ", ".join(f"{k} {v}" for k, v in sorted(Counter(r["meta"]["label"] for r in n_t[229:]).items()))
F["origins_now"] = ", ".join(f"`{k}`" for k in sorted({r["meta"]["origin"] for r in n_t[229:]}))
F["origins_was"] = ", ".join(f"`{k}`" for k in sorted({r["meta"]["origin"] for r in o_t[229:]}))
jo, jn = mc.jobs(o_t, score), mc.jobs(n_t, score)
F["job1_was"], F["job1_now"] = f"{jo['job1'][0]}", f"{jn['job1'][0]}"
F["job2_was"], F["job2_now"] = f"{jo['job2'][0]}", f"{jn['job2'][0]}"
F["famjob1_was"], F["famjob1_now"] = f"{jo['fam_job1']}", f"{jn['fam_job1']}"
F["famjob2_was"], F["famjob2_now"] = f"{jo['fam_job2']}", f"{jn['fam_job2']}"
F["job3_was"] = f"{jo['job3'][0]} rows ({', '.join(f'{k} {v}' for k, v in jo['job3'][1].items())})"
F["job3_now"] = f"{jn['job3'][0]} rows ({', '.join(f'{k} {v}' for k, v in jn['job3'][1].items())})"
check(jn["job1"][0] == jn["job1"][1] and jn["job2"][0] == jn["job2"][1],
      f"the gold reply does not score full marks on the new exam: {jn['job1']}, {jn['job2']}")
check(t10["jobs"] == {"job1": jn["job1"][0], "job2": jn["job2"][0]}, "job counts differ from Task 10's report")

for k in sorted(F):
    print(f"{k} = {F[k]}")
(S / "facts.json").write_text(json.dumps(F, indent=1, sort_keys=True), encoding="utf-8")
if fails:
    print("\nCHECK FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit("stop: commit nothing, keep facts.json, report DONE_WITH_CONCERNS with this output")
print("\nMEASURE OK:", len(F), "facts")
KV_EOF
wc -l "$S/measure.py"
```

Expected: `296 /tmp/kv-task11/measure.py`.

- [ ] **Step 5: MEASURE — every number the docs will hold**

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && rm -f "$S/facts.json" "$S/measure.log" \
  && { env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
       .venv/bin/python "$S/measure.py" "$S" > "$S/measure.log" 2>&1; echo "exit=$?"; cat "$S/measure.log"; }
```

Expected: `exit=0`, then one `name = value` line for each fact, sorted, and
last `MEASURE OK: <N> facts`. The checks that must pass:

- the mix bars on the new `train.jsonl`: at least 12 pairs for every story; the broken and the healthy `none_of_these` share within 10 points; `none_of_these` at most 30% of train verdicts; at least 5 plain stories ending "shared" and at least 5 ending "none";
- Task 8's five numbers, counted again here, are the ones in `reported.json`;
- the bank has 1,200 pairs of the family at `--seed 17 --size 8000` (1,200 `shared_origin` and 1,200 `shared_origin_decoy` rows);
- the registry no-pull sentence appears in 0 rows, as the capture record says;
- each file's row count matches the manifest, and each sha256 matches Task 10's report;
- the three pins moved, match what the generator gives, and match Task 10's report;
- the first 229 exam rows are unchanged, and the last 20 are exactly the family's, from 6 origins;
- the gold reply scores full marks on the new exam, and the job 1 and job 2 counts match Task 10's report.

It also prints two lines that say whether the rows outside the family, and
the `multi` rows, are the same as in `out/dataset-0929`. These are not
checks. Task 10 already gates that. The docs say whichever is true.

The old values it compares against are the ones PIN.md's 2026-09-29 entry
records. It asserts they are still there.

If `CHECK FAILED` appears, or `exit` is not 0: stop. Commit nothing, keep
`facts.json` and `measure.log`, and report DONE_WITH_CONCERNS with the
whole log. The numbers are what they are: no pin, no bar and no check
moves to fit them. If you get a traceback instead of `CHECK FAILED`, an
input is wrong. Fix `reported.json` if the slip was yours. If it was not,
report BLOCKED with the traceback.

- [ ] **Step 6: Write `apply_edits.py`**

The editor. It reads `facts.json` and one or more edit lists. Each edit
is one of three kinds: add text after a block (the block stays), rewrite
a block, or add text at the end of a file. Every block must be found
exactly once. If any one is not, nothing is written for any file. A
paragraph that takes a number in is re-wrapped to 76 columns, because the
number changes its line length; every other line is left as it is.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/apply_edits.py" <<'KV_EOF'
"""Task 11: apply the doc edits.  usage: apply_edits.py <facts.json> [--check] <edits file>...

An edits file is a list of edits, each in one of three shapes:

    @@@ FILE <path>                  (sets the file for the edits below it)

    @@@ AFTER                        add text right after a block; the block is
    <the block, exactly once>        untouched, so old text always stays
    @@@ ADD
    <the text to add>
    @@@ END

    @@@ FIND                         rewrite: the block becomes the new text
    <the block, exactly once>
    @@@ WITH
    <the new text>
    @@@ END

    @@@ APPEND                       add text at the end of the file
    <the text>
    @@@ END

`{{key}}` in ADD, WITH and APPEND text is replaced from facts.json; a key that is not
there is an error. A paragraph (or one list item) that took a fact in is re-wrapped to 76 columns,
because the fact changes its line lengths; a table row, or a paragraph that holds a
sha256, is left alone, and so is every paragraph that took no fact.
With --check nothing is written.  Every edit must find its block
exactly once, or nothing is written at all.
"""
import json
import pathlib
import re
import sys
import textwrap
from collections import Counter

args = sys.argv[1:]
check_only = "--check" in args
args = [a for a in args if a != "--check"]
facts = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
edit_files = args[1:]
KEY = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


WIDTH = 76
NEW_UNIT = re.compile(r"\s*(- |\d+\. |\|)")
MARKER = re.compile(r"(\s*)(- |\d+\. )?")
HASH = re.compile(r"[0-9a-f]{40,}")
wrapped = 0


def units(text):
    """Cut text into paragraphs: a blank line, a list item or a table row starts a new one."""
    out = []
    for ln in text.split("\n"):
        if not out or ln.strip() == "" or out[-1][0].strip() == "" or NEW_UNIT.match(ln):
            out.append([ln])
        else:
            out[-1].append(ln)
    return out


def rewrap(lines):
    first = MARKER.match(lines[0]).group(0)
    rest = re.match(r"\s*", lines[1]).group(0) if len(lines) > 1 else " " * len(first)
    body = " ".join([lines[0][len(first):].strip()] + [x.strip() for x in lines[1:]])
    return textwrap.fill(body, width=WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def fill(text, where):
    global wrapped

    def sub(m):
        if m.group(1) not in facts:
            raise SystemExit(f"{where}: no fact called {m.group(1)!r} in facts.json")
        return str(facts[m.group(1)])

    out = []
    for unit in units(text):
        raw = "\n".join(unit)
        done = KEY.sub(sub, raw)
        if done != raw and not HASH.search(done) and not done.lstrip().startswith("|"):
            done = rewrap(done.split("\n"))
            wrapped += 1
        out.append(done)
    return "\n".join(out)


def parse(path):
    edits, target, i = [], None, 0
    lines = pathlib.Path(path).read_text(encoding="utf-8").split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("@@@ FILE "):
            target = ln[len("@@@ FILE "):].strip()
            i += 1
            continue
        if ln in ("@@@ AFTER", "@@@ FIND", "@@@ APPEND"):
            kind, i = ln[4:], i + 1
            first, second = [], []
            cur, mid = first, {"AFTER": "@@@ ADD", "FIND": "@@@ WITH", "APPEND": None}[kind]
            if kind == "APPEND":
                cur = second
            while lines[i] != "@@@ END":
                if lines[i] == mid:
                    cur = second
                else:
                    cur.append(lines[i])
                i += 1
            where = f"{path}:{i + 1}"
            assert target, f"{where}: an edit before any @@@ FILE line"
            assert kind == "APPEND" or mid and cur is second, f"{where}: {kind} block has no {mid} line"
            edits.append((target, kind, "\n".join(first), "\n".join(second), where))
            i += 1
            continue
        assert ln.strip() == "" or ln.startswith("#"), f"{path}:{i + 1}: stray line {ln!r}"
        i += 1
    return edits


texts = {}
removed = Counter()
done = 0
for path in edit_files:
    for target, kind, first, second, where in parse(path):
        if target not in texts:
            texts[target] = pathlib.Path(target).read_text(encoding="utf-8")
        text = texts[target]
        second = fill(second, where)
        if kind == "APPEND":
            texts[target] = text.rstrip("\n") + "\n\n" + second.strip("\n") + "\n"
        else:
            n = text.count(first)
            if n != 1:
                raise SystemExit(f"{where}: the block was found {n} times in {target}, not once:\n{first}")
            at = text.index(first) + len(first)
            if kind == "AFTER":
                if text[at:at + 1] not in ("\n", ""):
                    raise SystemExit(f"{where}: the block does not end at the end of a line:\n{first}")
                texts[target] = text[:at] + "\n" + second + text[at:]
            else:
                texts[target] = text.replace(first, second)
                gone = Counter(first.split("\n")) - Counter(second.split("\n"))
                removed[target] += sum(gone.values())
        done += 1

print(f"{done} edits found their block exactly once")
print(f"{wrapped} paragraphs that took a fact in were re-wrapped to {WIDTH} columns")
for target in sorted(texts):
    print(f"  {target}: {removed[target]} old lines rewritten (every other old line stays)")
if check_only:
    print("--check: nothing written")
else:
    for target, text in texts.items():
        pathlib.Path(target).write_text(text, encoding="utf-8")
    print("written")
KV_EOF
wc -l "$S/apply_edits.py"
```

Expected: `157 /tmp/kv-task11/apply_edits.py`.

- [ ] **Step 7: Write the PIN.md edits**

Seven short notes and one new entry. The notes close five older items in
place: the victims whose gold names a node their lines never show, the
`kube-system` line past the first 10 workloads, the candidate-cap marker,
B4 (twice: at its first mention and at its pointer in the Left-for list)
and a node's state at scan time (twice, the same way). The note on B4
also corrects it: the old wording was one arm short. The new entry
follows the shape of the 2026-09-29 entry: what moved, why, the hashes,
the bank, what moved on the exam, the mix numbers, what is closed, and
what is left.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/edits_pin.txt" <<'KV_EOF'
# contract/PIN.md: five older items close in place (the old text stays), then a new entry at the end.
@@@ FILE contract/PIN.md

@@@ AFTER
  - 14 shared-origin exam victims carry the gold `node worker-N
    (NotReady)`, which no line of theirs names.
@@@ ADD
    ({{DAY}}, Spec 4b-1: closed. The count was 14. Spec 4b-1 counted
    again and found 20. A victim's gold now names a cause only when that
    cause's anchor is in the victim's own lines. If it is not, the gold is
    `none_of_these`. The pool check scores every family gold with the real
    grader and wants full marks on every row.)
@@@ END

@@@ AFTER
  - A flagged `kube-system` workload outside the first 10 gets a system
    line in Go but not here.
@@@ ADD
    ({{DAY}}, Spec 4b-1: closed. `render.cluster_health` is rebuilt on
    `health.assess`, the port that the cluster capture pins. The cluster
    fixture flags 13 workloads, 11 of them in `kube-system`, so 3
    `kube-system` workloads fall past the first 10. Their system lines
    print, and `tests/test_gather_byte_equal.py` holds the lines equal to
    Go's.)
@@@ END

@@@ AFTER
  - The candidate-cap marker is no longer in the golden; only a unit test
    covers it.
@@@ ADD
    ({{DAY}}, Spec 4b-1: closed. The cluster fixture has 12 down nodes
    against Go's cap of 8 candidates per workload, so the cap is in the new
    Go capture, `tests/fixtures/gather_go_cluster`. The byte test holds
    our bytes equal to it.)
@@@ END

@@@ AFTER
  - B4: three arms the generator reaches have no Go capture to check
    them byte for byte (the candidate-cap line, a registry auth sentence
    and the no-pull-event sentence). Covering them needs a new capture.
@@@ ADD
    ({{DAY}}, Spec 4b-1: the three arms are closed. The cluster and
    registry captures, from kubeagent v1.24.0, cover the candidate-cap
    line, the registry auth sentence and the no-pull-event sentence, and
    `tests/test_gather_byte_equal.py` checks each one byte for byte. The
    wording above was one arm short. A fourth arm, the shared-cause cap,
    has no capture. It moves to 4b-4.)
@@@ END

@@@ AFTER
  - B4: three arms with no Go capture.
@@@ ADD
    ({{DAY}}, Spec 4b-1: three arms closed, and a fourth found. See the
    longer B4 note above. The fourth arm, the shared-cause cap, moves to
    4b-4.)
@@@ END

@@@ AFTER
    No grader reads it today.
  - A node's state at scan time: a cordon and a pressure condition.
@@@ ADD
    ({{DAY}}, Spec 4b-1: closed. A node read now prints `unschedulable=`
    and every condition. The cluster lines carry a node's pressure,
    NotReady, cordon and lease state, in that order. Each story sets all
    of it, once per world.)
@@@ END

@@@ AFTER
  - D4: `multi`'s decoy list is keyed on each object's intent.
  - A node's state at scan time: a cordon and a pressure condition.
@@@ ADD
    ({{DAY}}, Spec 4b-1: closed. See the note under the same item in the
    2026-09-26 entry.)
@@@ END

@@@ APPEND
- **{{DAY}} — Spec 4b-1, the shared-origin rewrite.** All three hashes
  moved: `FROZEN_SLICE_SHA256`, `EVAL_SET_SHA256` and
  `GRADED_VIEW_SHA256`. The exam is still 249 rows and the frozen slice
  still 239. 229 exam rows, from the other families, are byte for byte
  the old ones (`OTHER_FAMILIES_SHA256` in `tests/test_generate.py`). The
  20 shared-origin exam rows are rebuilt: 10 `shared_origin_probe` and 10
  `shared_origin_decoy_probe`. Of those 20 rows, {{moved_user}} user
  messages, {{moved_gold}} gold answers, {{moved_flagged}} flagged lists
  and {{moved_meta}} metas moved. {{moved_system}} system messages moved.

  Why. Until now this family showed the model text the generator made up:
  a candidate menu and an origin read typed by hand. Now each row runs
  kubeagent's own steps: the report order, the gather, the rules over
  every candidate, and the render. The design is in
  `docs/superpowers/specs/2026-10-03-shared-origin-rewrite-design.md`.
  One line each on what changed:
  - Real rows. There are 47 stories, each in two worlds, one broken and
    one healthy. 41 are trainable (35 plain, 6 ruled) and 6 are
    exam-only. 13 stories are gone: 12 whose only origin line was the
    hand-typed read (the spec's X stories), and `runtime-class-removed`,
    whose two worlds print the same lines. The trainable pool was 54 (48
    plain, 6 ruled).
  - The exemption is gone. The checker used to skip this family for some
    rules (`EXEMPT_CASES`, `EVIDENCE_RULES` and `PROPAGATION_TEXT_RULES`).
    All 50 rules now run on it, and the build's manifest shows 0
    violations.
  - The gold rules. A victim's gold names a cause only when the cause's
    anchor is in that victim's own lines. If it is not, the gold is
    `none_of_these`. The label is "shared" when the rules confirm one
    cause on 2 or more workloads, or when 2 or more victims in a broken
    world show link anchors in their own lines. Otherwise it is "none".
  - B7, the checker's rule for the cluster-health block, is rewritten. A
    node can have several lines, in the order pressure, NotReady, cordon,
    lease, and a candidate is needed only for the down lines. The
    checker's `_HEALTH_SYSTEM` pattern is fixed in the same change.

  The hashes, old → new:

  | Pin | Old | New |
  |---|---|---|
  | `FROZEN_SLICE_SHA256` | `{{FROZEN_SLICE_SHA256_old}}` | `{{FROZEN_SLICE_SHA256_new}}` |
  | `EVAL_SET_SHA256` | `{{EVAL_SET_SHA256_old}}` | `{{EVAL_SET_SHA256_new}}` |
  | `GRADED_VIEW_SHA256` | `{{GRADED_VIEW_SHA256_old}}` | `{{GRADED_VIEW_SHA256_new}}` |

  The bank, `out/{{D}}`, built with the same command (`--seed 17
  --size 8000`), by sha256:
  - `test.jsonl`: `{{sha_test}}`
  - `train.jsonl`: `{{sha_train}}`
  - `val.jsonl`: `{{sha_val}}`

  Rows: train {{train_old}} → {{train_new}}, val {{val_old}} →
  {{val_new}}, test {{test_old}} → {{test_new}}. The bank holds
  {{family_cases}} rows, which is 1,200 pairs. {{outside_status}}
  `out/dataset-0929` and `out/dataset-0928` stay on disk. The
  prompt-stability test now reads `out/{{D}}/test.jsonl`.

  What moved on the 20 exam rows:
  - Their `meta` drops {{meta_removed}} and adds {{meta_added}}. The
    exam carries `expected_cause` on {{ec_now}} rows (was {{ec_was}}) and
    `expected_confidence` on {{ecf_now}} rows (was {{ecf_was}}).
  - Labels, was {{labels_was}}; now {{labels_now}}.
  - Origins, was {{origins_was}}; now {{origins_now}}.
  - The oracle's job counts, with the gold reply as the model's reply
    (every one is full marks): job 1 {{job1_was}} → {{job1_now}}
    workloads, job 2 {{job2_was}} → {{job2_now}} workloads, job 3
    {{job3_was}} → {{job3_now}}. The 20 family rows hold {{famjob1_now}}
    of the job-1 workloads (was {{famjob1_was}}) and {{famjob2_now}} of
    the job-2 workloads (was {{famjob2_was}}).
  - No bar moved: 0.9, 0.7 and 0.9.

  The mix, counted on the new `train.jsonl`. These are the numbers the
  mix tests passed with:
  - Pairs per story: {{m_floor_min}} to {{m_floor_max}}. The bar is at
    least 12.
  - `none_of_these` in broken rows: {{m_share_broken}}. In healthy rows:
    {{m_share_healthy}}. The gap is {{m_gap_points}} points. The bar is
    within 10.
  - `none_of_these` in all train answers: {{m_share_bank}}. The bar is at
    most 30%. In `out/dataset-0929` it was {{o_share_bank}}.
  - Label cue: {{m_cue_shared}} plain stories end mostly "shared" and
    {{m_cue_none}} end mostly "none" ({{m_cue_tie}} tied). The bar is at
    least 5 each.
  - Three-verdict: {{m_wide}} of {{m_wide_of}} healthy rows = {{wide_pct}}
    carry 3 or more verdicts. The bar is at least 40 of every 100.

  Five older items close in place, each with a dated note and the old
  text kept: the victims whose gold names a node their lines never show,
  the `kube-system` line past the first 10 workloads, the candidate-cap
  marker, B4, and a node's state at scan time. B4's wording is corrected:
  it has a fourth arm.

  The capture is recorded under "Capture record (v1.24.0, cluster and
  registry capture)" above. In the new bank, {{reg_nopull}} family rows
  show the registry no-pull sentence and {{reg_auth}} show the registry
  auth sentence. The capture proves the bytes of both.

  The model card: limits 1 to 5 and 7 to 9 have a dated note with the new
  numbers, limit 6 is rewritten, and limit 15 is new. The two 0920
  sections say they scored the exam's shared-origin rows as they were
  before {{DAY}}. 0920 has not been run on the new exam.

  Left for 4b-2, 4b-3 and 4b-4:
  - 4b-2: gold that says more than its prompt, in the other families. The
    gold rule above, applied to them.
  - 4b-3: `multi` rows and decoys.
    - the container-name clash, 96 of 738 `multi` rows;
    - `multi`'s `healthy_origin` and its `origin_read_label` path;
    - D4.
  - 4b-4: grader leftovers.
    - model-card limits 13 and 14;
    - hyphen and underscore folding in the cleaning step;
    - the weak pairs: 21 on the 2026-09-29 exam, {{weak_pairs}} on this
      one;
    - image-pull-secret-expired graded as unverified;
    - B6;
    - the G2 registry skip;
    - must-not words for this family;
    - B4's fourth arm, the shared-cause cap;
    - tighter checker checks that real output does not need: service-line
      wording and sort order, the network-policy gate, a message-only
      NotReady line over 120 runes, lease ages from 0s to 39s, an extra
      system line at 10 rows, and ANS-2 counting ruled-out lines.

  The order after 4b-1: 4b-2, 4b-3 and 4b-4, then the exam rebuild and
  re-pin, then 0920 live, then the one retrain (about 32 hours on the
  training host), then the untuned baseline.
@@@ END
KV_EOF
wc -l "$S/edits_pin.txt"
```

Expected: `203 /tmp/kv-task11/edits_pin.txt`.

- [ ] **Step 8: Write the model-card edits**

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/edits_card.txt" <<'KV_EOF'
# docs/model-card.md: a dated note on limits 1 to 5 and 7 to 9, limit 6 rewritten, limit 15 new, a note under both 0920 headings.
# Limit 10 is not in this family and limits 11 to 14 are the grader's: no edit.
@@@ FILE docs/model-card.md

@@@ AFTER
### 0920 against the Spec 3 exam (2026-09-28)
@@@ ADD

({{DAY}}, Spec 4b-1: this section scored the exam's shared-origin rows as
they were before {{DAY}}. Spec 4b-1 rebuilt those 20 rows, and {{moved_user}}
of the 20 user messages moved. The other 229 rows are byte for byte the
same. Nothing was re-scored. 0920 has not been run on the rebuilt exam, so
no number here compares with it.)
@@@ END

@@@ AFTER
### 0920 re-scored under the 4a grader (2026-09-29)
@@@ ADD

({{DAY}}, Spec 4b-1: this section scored the exam's shared-origin rows as
they were before {{DAY}}. Spec 4b-1 rebuilt those 20 rows, and {{moved_user}}
of the 20 user messages moved. The other 229 rows are byte for byte the
same. Nothing was re-scored. 0920 has not been run on the rebuilt exam, so
no number here compares with it.)
@@@ END

@@@ AFTER
   same fault, worded two different ways — a model that expects the two
   words to match will not find them matching here.
@@@ ADD

   ({{DAY}}, Spec 4b-1: {{l1_status}} The family's rows are now built by
   running kubeagent's own steps, so the node read in a prompt is the one
   kubeagent prints. Of the family rows whose rationale states a Ready
   condition, these state a word the prompt does not show: {{l1_now}}.
   Counted the same way on `out/dataset-0929`: {{l1_was}}.)
@@@ END

@@@ AFTER
   "NotReady" and "no kubelet lease" — in the same row, and neither reason
   is what the row's own evidence shows for that node (disk pressure).
@@@ ADD

   ({{DAY}}, Spec 4b-1: {{l2_status}} Of the family rows that name a
   node, these name one node under two different reasons: {{l2_now}}.
   Counted the same way on `out/dataset-0929`: {{l2_was}}.)
@@@ END

@@@ AFTER
   prompt; the mismatch is a fact about the code, not something a model
   can read.
@@@ ADD

   ({{DAY}}, Spec 4b-1: re-measured. The prompt now prints a claim as
   kubeagent reads it. Now: {{l3_now}}. Before, on `out/dataset-0929`:
   {{l3_was}}.)
@@@ END

@@@ AFTER
   workloads, so the count written into the text and the count of rows a
   model is asked to judge do not match.
@@@ ADD

   ({{DAY}}, Spec 4b-1: {{l4_status}} The exam row named above is one of
   the 20 rows that were rebuilt. Of the family rows whose cause says "N
   workloads", these say an N that is not the number of workloads flagged:
   {{l4_now}}. Counted the same way on `out/dataset-0929`: {{l4_was}}.)
@@@ END

@@@ AFTER
   reasoning behind it — job 1, which grades whether the model repeats the
   decided cause, cannot tell the two apart.
@@@ ADD

   ({{DAY}}, Spec 4b-1: re-measured. `_rule_rationale` moved to
   `render.rule_rationale`, and the old name stays as an alias. The
   template now covers {{l5_now}}. Before, on `out/dataset-0929`:
   {{l5_was}}. These two are counted by one rule on both builds. The
   numbers in the text above were counted another way, so read the two
   against each other and not against that text.)
@@@ END

@@@ FIND
6. **Plain broken twins always deny a shared cause, even though both rows
   name the same origin.** A plain story's two twin rows both point at the
   same real cause, but the rules cannot check a plain story's origin, so
   the summary on both rows says the rules did not confirm one cause. A
   model could learn "never call a cause shared" from this pattern alone.
   The ruled broken twins teach the other side, because the rules can check
   a ruled story's origin: in this build 192 of them land in train and 22
   in val, all carrying the `shared` label. This build has 960 plain pairs
   and 240 ruled pairs (1,200 in all), and every one of the 48 plain
   stories keeps at least 15 of its 20 pairs in train. Three stories tie
   for the lowest, at 15 (`sidecar-injector-broken`, `node-corrupt-overlay`
   and `cluster-maintenance-taint`), and the highest is 20. A further 26 of the 240
   ruled pairs, drawn only from the two node-kind ruled stories, are
   deliberately rendered "unverified" instead of confirmed (25 land in
   train, 1 in val): the origin read is made to fail, so the rules cannot
   confirm or deny it, and the label is `none`, not `shared`. That is a
   third pattern, not a second copy of "plain" — it teaches "the rules
   could not check" as its own answer.
@@@ WITH
6. **A broken twin is labelled "shared" only when the prompt shows why.**
   (Rewritten {{DAY}}, Spec 4b-1. The limit used to say that plain broken
   twins always deny a shared cause. That is no longer true.) A story is
   one of two kinds. A ruled story is one the rules can check: its origin
   is a node, a claim or a registry, a fresh read confirms it, and 2 or
   more victims share it. A plain story is every other kind: the rules
   never group 2 or more of its victims. A broken world is labelled
   "shared" in two cases. The rules confirm one cause on 2 or more
   workloads. Or 2 or more victims show the origin's link in their own
   lines. Every other row is labelled "none". That covers every healthy
   world, and every "unverified" twin, where the origin read fails and the
   rules can neither confirm nor deny.
   In train, {{m_P_stories}} plain stories give {{m_P_pairs}} pairs, and
   {{m_R_stories}} ruled stories give {{m_R_pairs}} pairs. Of the plain
   pairs, {{m_P_shared}} are labelled "shared" and {{m_P_none}} "none". Of
   the ruled pairs that are not "unverified", {{m_R_shared}} are "shared"
   and {{m_R_none}} are "none". A further {{m_unverified}} ruled pairs are
   "unverified", and {{m_unverified_none}} of those carry the label
   "none". In val, {{v_P_shared}} plain pairs and {{v_R_shared}} ruled
   pairs are labelled "shared". Every story keeps at least 12 pairs in
   train, a bar a test holds. The lowest story has {{m_floor_min}} and the
   highest has {{m_floor_max}}.
   The risk is a cue. If a story's name decided its label, a model could
   learn the name and skip the evidence. A test checks that {{m_cue_shared}}
   plain stories end mostly "shared" and {{m_cue_none}} end mostly "none"
   ({{m_cue_tie}} tied), at least 5 each, so the label comes from the
   prompt and not from the story.
   For the record, the old limit counted 960 plain pairs and 240 ruled
   pairs, 192 ruled train rows and 22 in val labelled "shared", and 26
   unverified pairs (25 in train, 1 in val), over 48 plain stories.
@@@ END

@@@ AFTER
   `networkpolicy-deny-all` — do declare decoy objects and do carry a
   decoy rate there.)
@@@ ADD

   ({{DAY}}, Spec 4b-1: re-measured. The code and the story counts named
   above describe the build before {{DAY}}. Family rows that carry a decoy
   rate now: {{l7_now}}. Before, on `out/dataset-0929`: {{l7_was}}. The
   `--probe-cousins` rows that carry one: {{cousin_decoy}} of
   {{cousin_rows}} rows ({{cousin_pairs}} pairs).)
@@@ END

@@@ AFTER
   exam's node-story rows print only the story form. A model that expects
   one fixed format will see both.
@@@ ADD

   ({{DAY}}, Spec 4b-1: the family rows only. {{l8_status}} Family rows by
   form, now: {{l8_now}}. Before, on `out/dataset-0929`: {{l8_was}}.
   {{multi_status}})
@@@ END

@@@ AFTER
   something the prompt does print (`Unknown` against `False`); this is
   the general case, and the bigger fact.
@@@ ADD

   ({{DAY}}, Spec 4b-1: {{l9_status}} The family's candidate list now
   prints kubeagent's own `fresh read:` line, and the rationale quotes it.
   Of the family's rule rows that use the template, these quote a read the
   prompt never shows: {{l9_now}}. Counted the same way on
   `out/dataset-0929`: {{l9_was}}.)
@@@ END

@@@ AFTER
    purpose, and kept bare `init` off the list because `initial` would
    trip it. Spec 4b owns the rest.
@@@ ADD
15. **`none_of_these` is {{m_share_bank_pct}} of the train answers.** (Added {{DAY}}, Spec
    4b-1.) A victim's gold names a cause only when its anchor is in that
    victim's own lines. Where it is not, the gold is `none_of_these`. In
    train that is {{m_share_bank}} of all verdicts. In `out/dataset-0929` it was
    {{o_share_bank}}. In broken worlds it is {{m_share_broken}}. In healthy
    worlds it is {{m_share_healthy}}. Tests hold the mix. The balance test
    wants the broken and the healthy share within 10 points, so the answer
    does not tell a model which world it is in. The gap is {{m_gap_points}}
    points. The ceiling test wants the answer at most 30% of all train
    verdicts. The three-verdict test wants at least 40 of every 100
    healthy rows to carry 3 or more verdicts, so a healthy row is not
    always a short one. It is {{m_wide}} of {{m_wide_of}} = {{wide_pct}}.
    The risk is one these tests cannot see. A model that over-learns
    `none_of_these` will say it when the evidence is there. We will see
    that only after the retrain.
@@@ END
KV_EOF
wc -l "$S/edits_card.txt"
```

Expected: `188 /tmp/kv-task11/edits_card.txt`.

What it does:
- Under both 0920 headings: a note that the section scored the exam's shared-origin rows as they were before the build day. 0920 has not been run on the rebuilt exam, so no number there compares with a new one.
- Limits 1, 2, 3, 4, 5, 7, 8 and 9: a dated note with the new number, and the same count on `out/dataset-0929`. Each says whether the build closed the limit for this family.
- Limit 6: rewritten, 18 old lines. The old limit said that plain broken twins always deny a shared cause. That is no longer true, so the new limit says when a broken twin is labelled "shared", and gives the counts. It keeps the old counts in a last paragraph, for the record.
- Limit 15, new: `none_of_these` is now a common answer. The limit gives its share of train, in broken worlds and in healthy worlds, and the three tests that hold it. It does not predict what the retrain will do with it.
- Limit 10 is not in this family, and limits 11 to 14 belong to the grader. None of them is edited.

- [ ] **Step 9: Write the guide edits**

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && cat > "$S/edits_guides.txt" <<'KV_EOF'
# The three guides and the README. Old history stays: the passages that say "same candidate menus" are dated notes of earlier designs.

@@@ FILE docs/how-training-works.md

@@@ FIND
| `shared_origin` | 15% | Several broken workloads, all downstream of one thing — name that thing on every one (in the rules' own words where the rules checked it), and call it one shared cause only when the rules confirm it |
| `shared_origin_decoy` | 15% | The *same* question with the one thing shown **healthy** — so the answer is separate reasons after all |
@@@ WITH
| `shared_origin` | 15% | Several broken workloads, all downstream of one thing. Name that thing on a workload only when that workload's own lines show it, and answer `none_of_these` when they do not. Call it one shared cause only when the rules confirm it, or when two or more workloads' own lines show the link |
| `shared_origin_decoy` | 15% | The *same* story with the one thing shown **healthy**. Each workload's answer is its own cause when its lines show one, and `none_of_these` when they do not |
@@@ END

@@@ FIND
| `shared_origin_decoy_probe` | 10 | The mirror of the row above, from the *same* ten scenarios: same workloads, same candidate menus, same order. Only the reads differ — here the cluster-wide thing is **healthy**, so the answer really is separate causes. A model that learned "say shared" scores zero. | 1 or 2, plus 3 |
@@@ WITH
| `shared_origin_decoy_probe` | 10 | The mirror of the row above, from the *same* six stories: the same fault, with the cluster-wide thing **healthy**. The lines differ, because each world is built from kubeagent's own steps. Each workload's answer is its own cause, or `none_of_these`. A model that learned "say shared" scores zero. | 1 or 2, plus 3 |
@@@ END

@@@ AFTER
survives it exactly: **169 against 169.**
@@@ ADD

*Update, {{DAY}} (Spec 4b-1).* The twins are no longer line-for-line copies.
Each world is now built by running kubeagent's own steps on a story, so the
lines change with the fault. A broken world shows the fault in the victims'
own lines. A healthy world shows the same story with the one thing healthy.
Each workload's answer is its own cause when its lines show one, and
`none_of_these` when they do not. Every question is still asked in both
worlds. The text above describes the first design, and it stays as history.
@@@ END

@@@ FILE docs/design.md

@@@ FIND
Naming the story's cause on every row the rules do not decide and the rules' own cause on every row they do; calling it shared only when the rules confirm it |
@@@ WITH
Naming the story's cause on a row only when that row's own lines show it, and `none_of_these` otherwise; the rules' own cause on every row they decide; calling it shared only when the rules confirm it or 2 or more victims' own lines show the link |
@@@ END

@@@ FIND
`shared_origin_decoy` — the same scenario, origin read HEALTHY | ~15% | Taking each workload's own cause when the read refutes the shared story.
@@@ WITH
`shared_origin_decoy` — the same story, origin HEALTHY | ~15% | Taking each workload's own cause when its lines show one, and `none_of_these` when they do not.
@@@ END

@@@ AFTER
`train.jsonl` and `val.jsonl` regenerate byte-identical across the change.
@@@ ADD

({{DAY}}, Spec 4b-1.) The shared-origin family no longer uses an invented
origin read. Each prompt is now built by running kubeagent's own steps on a
story: the report order, the gather, the rules over every candidate, and
the render. There are 47 stories, each in two worlds, one broken and one
healthy. 41 are trainable, where the old pool had 54, and 6 are
exam-only. The paragraphs above describe the earlier design, and they stay
as history. `multi` still draws from `propagation.trainable_scenarios()`;
Spec 4b-3 owns it. The counts and the hashes are in `contract/PIN.md`.
@@@ END

@@@ FILE README.md

@@@ AFTER
The twin is not evidence about the models below: a model that answers
"separate causes" to everything scores 1.0 on it, which is exactly what these
two did.
@@@ ADD

({{DAY}}, Spec 4b-1: the twin paragraph above describes the rows as they
were. The twin is no longer a copy of the broken rows with the reads
swapped. Each world is now built from kubeagent's own steps, so the lines
differ as the faults differ. The exam keeps its 20 shared-origin rows, from
6 stories. The scores below were taken on the rows as they were before
{{DAY}}.)
@@@ END
KV_EOF
wc -l "$S/edits_guides.txt"
```

Expected: `74 /tmp/kv-task11/edits_guides.txt`.

What it does:
- `docs/how-training-works.md`: the two case-table rows and the decoy exam row say what the family is now. A dated note follows the long "twin" passage at :390. The passages that say "same candidate menus" stay as they are. They describe the first design, and the note says so.
- `docs/design.md`: the same two rows, and a dated paragraph after :413 that names the new design in four lines.
- `README.md`: one dated note after the twin paragraph. It says the paragraph above describes the rows as they were, and that the scores below were taken on the old rows.

- [ ] **Step 10: Dry run, then apply**

First a dry run. It changes no file.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 && grep -q '^MEASURE OK' "$S/measure.log" \
  && .venv/bin/python "$S/apply_edits.py" "$S/facts.json" --check "$S/edits_pin.txt" "$S/edits_card.txt" "$S/edits_guides.txt"
```

Expected:

```
27 edits found their block exactly once
37 paragraphs that took a fact in were re-wrapped to 76 columns
  README.md: 0 old lines rewritten (every other old line stays)
  contract/PIN.md: 0 old lines rewritten (every other old line stays)
  docs/design.md: 2 old lines rewritten (every other old line stays)
  docs/how-training-works.md: 3 old lines rewritten (every other old line stays)
  docs/model-card.md: 18 old lines rewritten (every other old line stays)
--check: nothing written
```

If it prints anything else, stop. A "found 0 times" message means a doc
moved since this plan was written, or an earlier task edited the same
place: report NEEDS_CONTEXT with the message. A "no fact called" message
means an edit asks for a number `measure.py` did not make: report BLOCKED.
Do not edit an edit list to make it pass.

Then apply it. Run this once. A second run fails on its first rewritten
block and writes nothing.

```bash
cd /home/ubuntu/git/kubeagent-verdict && S=/tmp/kv-task11 \
  && .venv/bin/python "$S/apply_edits.py" "$S/facts.json" "$S/edits_pin.txt" "$S/edits_card.txt" "$S/edits_guides.txt"
```

Expected: the same lines, ending `written`.

- [ ] **Step 11: The training host is not named**

The dispatch gives `HOST`, the training host's ssh alias. This plan never
writes it. The second pattern is the alias up to its first dash, the short
name people also use.

```bash
cd /home/ubuntu/git/kubeagent-verdict && : "${HOST:?set HOST to the alias the dispatch gave}" && \
  git grep -n -i -F -e "$HOST" -e "${HOST%%-*}" ; echo "exit=$?"
```

Expected: no line before `exit=1`. If `HOST` is unset the command stops at
once with "set HOST…"; an empty pattern would match every line. The docs
say "the training host" and nothing more. If `git grep` prints a line,
stop, commit nothing, and report DONE_WITH_CONCERNS with the file and the
line number (never the matched text itself). Do not edit it away here. A
hit means an earlier task or a measured fact leaked the name, and the
controller needs to know which.

- [ ] **Step 12: Check the diff**

```bash
cd /home/ubuntu/git/kubeagent-verdict && F="contract/PIN.md docs/model-card.md docs/how-training-works.md docs/design.md README.md" \
  && echo "--- deletions per file" && git diff --numstat -- $F | awk '{print $2, $3}' \
  && echo "--- whitespace" && git diff --check -- $F && echo "(clean)" \
  && echo "--- marks left" && { ! grep -n '{{\|<<\|@@@' $F; } && echo "(none)" \
  && echo "--- untouched" && git diff --stat -- docs/runbooks src/kubeagent_verdict/evals/score.py src/kubeagent_verdict/contract.py tests out && echo "(nothing)" \
  && echo "--- status" && git status --short \
  && echo "--- in place" \
  && grep -c 'Spec 4b-1, the shared-origin rewrite' contract/PIN.md \
  && grep -c '^15\. \*\*`none_of_these` is ' docs/model-card.md \
  && grep -c '^6\. \*\*A broken twin is labelled "shared" only when the prompt shows why' docs/model-card.md \
  && grep -c '15ec5649bbd2d07558eae945b71430afc8f231fd' contract/PIN.md \
  && echo "--- runbook" && grep -c '249' docs/runbooks/train.md \
  && wc -l < "out/$(.venv/bin/python -c 'import json; print(json.load(open("/tmp/kv-task11/reported.json"))["t10"]["folder"])')/test.jsonl"
```

Expected, in order:

```
--- deletions per file
0 README.md
0 contract/PIN.md
2 docs/design.md
3 docs/how-training-works.md
18 docs/model-card.md
--- whitespace
(clean)
--- marks left
(none)
--- untouched
(nothing)
--- status
 M README.md
 M contract/PIN.md
 M docs/design.md
 M docs/how-training-works.md
 M docs/model-card.md
(the same three lines Step 1 allowed may follow: .gitignore, train-v2.log and the plan file)
--- in place
1
1
1
<one or more>
--- runbook
<one or more>
249
```

The deletion counts are fixed by the edit lists, so they must be exactly
these. The insertion counts depend on the numbers and are not checked. The
status lines for the three allowed files are the same ones Step 1 saw. Any
other file in `git status` is a stray write: stop and report BLOCKED. The
last two lines say `docs/runbooks/train.md` still counts the exam as 249
rows and the new `test.jsonl` has 249 rows. If the runbook does not say
249, stop and report NEEDS_CONTEXT: the runbook is the one doc this task
checks and does not edit.

Read the new text once, in the diff, before the commit:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff -- contract/PIN.md | sed -n '1,400p'
```

Expected: a plain reader could follow it. The `Why` bullets, the hashes
table, the bank block and the Left-for lists are all there; every number
is a digit string, not a mark; no line names the training host.

- [ ] **Step 13: Run the whole suite**

Run: `PYTEST`
Expected: PASS, every test. These are docs, but a test may read them. If
anything fails, stop. Commit nothing, and report DONE_WITH_CONCERNS with
the failures.

- [ ] **Step 14: Lint and commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git add contract/PIN.md docs/model-card.md docs/how-training-works.md docs/design.md README.md \
  && COMMIT "docs: the shared-origin rewrite (Spec 4b-1) in PIN.md, the model card and the guides"
```

Expected: ruff passes, and one commit with five files. Nothing under
`/tmp/kv-task11` is committed. The report carries `measure.log` in full,
the dry-run output of Step 10, and the Step 12 output.

---

### Task 12: Final checks — the Done-when table

This task changes nothing. It runs every check in the spec's "Done when"
table against the finished branch and Task 10's build, and writes the
table, with the measured value in each row, into the task report. A miss
is reported, never fixed here: no bar, pin or test moves in this task.

**Files:**
- None created or modified. The build folder `out/dataset-<MMDD>` from
  Task 10 is read only.

**Interfaces:**
- Consumes: Task 10's folder name and day (its report line
  `D=out/dataset-<MMDD> DAY=<YYYY-MM-DD>`) and its report lines for the
  exam job counts and the three hashes; Task 1's
  `tests/test_gather_byte_equal.py`; Task 4's
  `tests/test_shared_origin_gold.py`; Task 6's `tests/test_stories.py`;
  Task 7's `tests/test_checker.py`, `tests/test_generate.py` and
  `tests/test_shared_origin_pool.py`; Task 8's
  `tests/test_shared_origin_floor.py` and `tests/test_shared_origin_pool.py`;
  Task 9's `tests/test_oracle.py`; `stories.trainable()`; `checker.RULES`;
  `score.evaluate(rows, chat_fn, *, grade_job2=True) -> list[dict]` (each
  result has `contract_ok`, `named_decoy`, `job1_scores`, `job2_scores`
  and `job3`); `contract.NONE_OF_THESE`.
- Produces: the filled Done-when table in the task report. The finishing
  step quotes it.
- The controller gives the training host's ssh alias in the dispatch as
  `HOST`. It is never written into a file.

- [ ] **Step 1: The full suite is green**

Run: `PYTEST`

Expected: every test passes, `0 failed`. The prompt-stability test runs
(it reads Task 10's bank, which is on disk), so the summary shows no
`skipped` for `tests/test_exam_prompt_stability.py`. Check that with:

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest -q -p no:cacheprovider -rs tests/test_exam_prompt_stability.py
```

Expected: PASS, and no `SKIPPED` line. Write the full run's last line
(`<N> passed`) in the report. The Python suite has no update flag
(`grep -n -e '--update' tests/conftest.py` prints nothing), so every pin
that moved on this branch moved by hand, in Task 9 or Task 10. The Go
golden files live in the kubeagent repo, and Step 3 shows it unchanged.

- [ ] **Step 2: The bars and the grader did not move**

Run:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git diff --stat main -- src/kubeagent_verdict/evals/score.py src/kubeagent_verdict/contract.py \
  && echo "--- bars" && grep -n 'JOB[123]_BAR *=' src/kubeagent_verdict/evals/score.py \
  && echo "--- bar tests" && git diff main -- tests/test_score.py | grep -n 'BAR' ; echo "done"
```

Expected: no `git diff --stat` output; the three bar lines read
`JOB1_BAR = 0.9`, `JOB2_BAR = 0.7` and `JOB3_BAR = 0.9`; no line under
`--- bar tests`; then `done`.

- [ ] **Step 3: Lint, the kubeagent repo, and the working tree**

Run:

```bash
cd /home/ubuntu/git/kubeagent-verdict && .venv/bin/ruff check --ignore EXE002 . \
  && git -C /home/ubuntu/git/kubeagent status --short \
  && echo "--- verdict tree" && git status --short
```

Expected: `All checks passed!`; the kubeagent repo prints only
` M .gitignore`; the verdict tree prints only ` M .gitignore` and
`?? train-v2.log`. The build folder does not show, because `out/` is
ignored.

- [ ] **Step 4: No tracked file and no commit names the training host, and no commit credits an assistant**

Run, with `HOST` set to the alias the dispatch gave:

```bash
cd /home/ubuntu/git/kubeagent-verdict && : "${HOST:?set HOST to the alias the dispatch gave}" && \
  git grep -n -i -F -e "$HOST" -e "${HOST%%-*}" ; \
  git log --format=%B main..HEAD | grep -n -i -F -e "$HOST" -e "${HOST%%-*}" ; \
  git log --format=%B main..HEAD | grep -n -i -E 'co-authored-by|generated with' ; echo "done"
```

Expected: only `done`. If `HOST` is unset the command stops at once
with "set HOST…"; an empty pattern would match every line. A match is a leak: stop, commit nothing, and report
DONE_WITH_CONCERNS with the file and line (never the matched text itself
in a file).

- [ ] **Step 5: Run the Done-when tests by name**

```bash
cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_gather_byte_equal.py \
  tests/test_generate.py::test_the_other_families_exam_rows_did_not_move \
  tests/test_checker.py::test_shared_origin_row_passes_every_rule \
  tests/test_shared_origin_gold.py::test_labels_per_world_and_width \
  tests/test_stories.py::test_p_labels_are_mixed \
  tests/test_shared_origin_pool.py \
  tests/test_shared_origin_floor.py \
  tests/test_oracle.py \
  tests/test_multi_collision.py tests/test_render.py tests/test_cluster_health.py \
  && ls -d tests/fixtures/gather_go*/ | wc -l \
  && git diff --stat main -- tests/fixtures/gather_go/ tests/fixtures/gather_go_logs/ ; echo "done"
```

Expected: PASS; then `4` (the four capture folders); then no diff output
(the 22 old dumps did not move); then `done`. The byte test runs over all
four folders, and `test_every_capture_folder_is_checked` is the folder
guard. `test_shared_origin_pool.py` holds Task 7's
`test_gold_scores_full_marks` and Task 8's
`test_every_family_gold_scores_full_marks`,
`test_ruled_broken_worlds_are_shared_unless_a_check_was_unverified`,
`test_label_and_summary_agree` and
`test_no_rule_passes_by_looking_at_nothing`. `test_shared_origin_floor.py`
holds the floor (12), balance (0.10), ceiling (0.30), label-cue (5) and
kept-twins tests.

- [ ] **Step 6: Measure the build**

Use the folder from Task 10's report.

```bash
cd /home/ubuntu/git/kubeagent-verdict && D=out/dataset-<MMDD> && env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - "$D" <<'EOF'
import json
import pathlib
import sys
from collections import Counter

from kubeagent_verdict import contract
from kubeagent_verdict.dataset import checker, stories
from kubeagent_verdict.evals import score

d = pathlib.Path(sys.argv[1])
SHARED, DECOY = "shared_origin", "shared_origin_decoy"


def load(name):
    lines = (d / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(ln) for ln in lines if ln]


def case(r):
    return r["meta"]["case"]


def verdicts(r):
    return json.loads(r["messages"][2]["content"])["verdicts"]


def none_share(rows):
    vs = [v for r in rows for v in verdicts(r)]
    return sum(v["cause"] == contract.NONE_OF_THESE for v in vs), len(vs)


def majority(labels):
    top = Counter(labels).most_common()
    if not top or (len(top) > 1 and top[0][1] == top[1][1]):
        return None
    return top[0][0]


train, val, test = load("train.jsonl"), load("val.jsonl"), load("test.jsonl")
man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
print(f"checker: {len(checker.RULES)} rules, "
      f"{sum(man['checker_violations'].values())} violations over {len(man['checker_violations'])} cases")
print(f"exam rows: {len(test)}")
base = pathlib.Path("out/dataset-0929")
for name, rows in (("train.jsonl", train), ("val.jsonl", val)):
    was = [r for r in (json.loads(ln) for ln in (base / name).read_text(encoding="utf-8").splitlines() if ln)
           if not case(r).startswith("shared_origin")]
    now = [r for r in rows if not case(r).startswith("shared_origin")]
    multi = sum(case(r) == "multi" for r in now)
    print(f"{name}: non-family rows equal dataset-0929's: {was == now} ({len(now)} rows, {multi} multi)")
was_test = [json.loads(ln) for ln in (base / "test.jsonl").read_text(encoding="utf-8").splitlines() if ln]
print(f"exam rows 1-229 equal dataset-0929's: {was_test[:229] == test[:229]}")
pool = stories.trainable()

per = Counter(r["meta"]["origin"] for r in train if case(r) == SHARED)
low = min(pool, key=lambda st: per[st.key])
print(f"pairs per story in train: fewest {per[low.key]} ({low.key}), "
      f"{len(pool)} stories, {sum(per.values())} pairs")

plain = [st.key for st in pool if st.cls == "P"]
ends = Counter(majority([r["meta"]["label"] for r in train
                         if case(r) == SHARED and r["meta"]["origin"] == k]) for k in plain)
print(f"plain stories by majority label: shared {ends['shared']}, none {ends['none']}, "
      f"tie {ends[None]}, of {len(plain)}")

bn, ba = none_share([r for r in train if case(r) == SHARED])
hn, ha = none_share([r for r in train if case(r) == DECOY])
print(f"none_of_these share: broken {bn}/{ba} = {bn / ba:.4f}, healthy {hn}/{ha} = "
      f"{hn / ha:.4f}, gap {abs(bn / ba - hn / ha) * 100:.1f} points")

n, t = none_share(train)
print(f"none_of_these share over all train verdicts: {n}/{t} = {n / t:.4f}")

fam = [r for r in train if case(r) in (SHARED, DECOY)]
pairs = list(zip(fam[::2], fam[1::2]))
assert all((case(a), case(b)) == (SHARED, DECOY) for a, b in pairs), "twins are not adjacent"
assert all(a["meta"]["origin"] == b["meta"]["origin"] for a, b in pairs), "twins differ in origin"
same = sum(set(a["messages"][1]["content"].splitlines())
           == set(b["messages"][1]["content"].splitlines()) for a, b in pairs)
print(f"kept pairs whose worlds print the same lines: {same} of {len(pairs)}")

labels = Counter((case(r), r["meta"]["label"]) for r in train + val + test
                 if case(r).startswith("shared_origin"))
print("labels by case:", dict(sorted(labels.items())))
healthy_shared = sum(case(r) == DECOY and r["meta"]["label"] == "shared" for r in train + val + test)
print(f"healthy-world rows labelled shared: {healthy_shared}")

rows = [r for r in train + val + test if case(r).startswith("shared_origin")]
gold = iter(r["messages"][2]["content"] for r in rows)
res = score.evaluate(rows, lambda _m: next(gold), grade_job2=True)
miss = [case(r) for r, x in zip(rows, res) if not (
    x["contract_ok"] and not x["named_decoy"]
    and all(s == 1.0 for s in x["job1_scores"])
    and all(s == 1.0 for s in x["job2_scores"])
    and x["job3"] in (None, 1.0))]
print(f"family rows read back as their own gold: {len(rows)}, short of full marks: {len(miss)}")
EOF
```

Expected, line by line:

- `checker: 50 rules, 0 violations over <K> cases`, where `<K>` is the
  number of keys under `checker_violations` in the manifest.
- `exam rows: 249`.
- `train.jsonl: non-family rows equal dataset-0929's: True (…)` and the
  same for `val.jsonl`. The second number in the brackets is the `multi`
  row count; it is the same as in `out/dataset-0929`, and so are those
  rows' bytes.
- `exam rows 1-229 equal dataset-0929's: True`.
- `pairs per story in train: fewest <F> (…)` with `<F>` at least 12, over
  41 stories.
- `plain stories by majority label: shared <S>, none <N>, …` with `<S>`
  and `<N>` each at least 5.
- `none_of_these share: …, gap <G> points` with `<G>` at most 10.0.
- `none_of_these share over all train verdicts: … = <R>` with `<R>` at
  most 0.30 (the spec expects about 0.26).
- `kept pairs whose worlds print the same lines: 0 of …`.
- `labels by case:` shows only `shared` and `none`.
- `healthy-world rows labelled shared: 0`.
- `family rows read back as their own gold: …, short of full marks: 0`.

The script stops with an `AssertionError` if a broken row and its healthy
twin are not next to each other in train, or have different origins. That
is a build fault: report BLOCKED with the message.

- [ ] **Step 7: Fill in the Done-when table**

Copy this table into the report and fill the last column from the step
named in it.

| Check | Target | Where it is checked | Measured |
|---|---|---|---|
| Capture folders, byte-equal | 4 of 4, plus the folder guard | Step 5: `test_gather_byte_equal.py` and the `4` | |
| Old dump files | 22 unchanged | Step 5: `test_the_old_dumps_are_unchanged` and the empty diff | |
| `multi` bytes after the switch | unchanged | Step 6: the two "non-family rows equal" lines; Step 5: `test_multi_collision.py`, `test_render.py`, `test_cluster_health.py` | |
| Exam rows from other families | 229 byte-identical | Step 6: "exam rows 1-229"; Step 5: `test_the_other_families_exam_rows_did_not_move` | |
| Exam size | 249 rows | Step 6: "exam rows" | |
| Checker manifest on the new build | 0 failures, 50 rules | Step 6: "checker"; Step 5: `test_shared_origin_row_passes_every_rule`, `test_no_rule_passes_by_looking_at_nothing` | |
| Pool check (every gold, real grader, job-2 on) | full marks on every row | Step 6: "short of full marks"; Step 5: `test_gold_scores_full_marks`, `test_every_family_gold_scores_full_marks` | |
| Label | "shared" only in a confirmed or 2+-linked broken world | Step 6: "labels by case" and "healthy-world rows labelled shared"; Step 5: `test_labels_per_world_and_width`, `test_ruled_broken_worlds_are_shared_unless_a_check_was_unverified`, `test_label_and_summary_agree` | |
| Kept pairs whose worlds print the same lines | 0 | Step 6: "kept pairs"; Step 5: `test_kept_twins_print_different_lines` | |
| Trainable P stories ending "shared" / "none" | at least 5 each | Step 6: "plain stories"; Step 5: `test_the_story_does_not_give_the_label_away`, `test_p_labels_are_mixed` | |
| Pairs per story in train | at least 12 | Step 6: "pairs per story"; Step 5: `test_every_trainable_story_keeps_the_floor_in_train` | |
| Broken vs healthy `none_of_these` share | within 10 points | Step 6: "gap"; Step 5: `test_none_of_these_is_balanced_across_the_worlds` | |
| Whole-bank `none_of_these` share | at most 30% (expect about 26%) | Step 6: "over all train verdicts"; Step 5: `test_none_of_these_stays_under_the_ceiling` | |
| New exam job-1 and job-2 counts | measured and recorded | Task 10 Step 4's oracle line (was → now); Step 5: `tests/test_oracle.py` | |
| Bars | unchanged | Step 2 | |
| Full test suite | green, no `-update` | Step 1 | |

Every row must meet its target. If one does not, stop: commit nothing,
move no bar, pin or threshold, and report DONE_WITH_CONCERNS with the
table, the row that missed, and the line the step printed. The controller
rules on the fix; the story data belongs to Tasks 5 and 6.

- [ ] **Step 8: Write the report**

The report holds the table from Step 7, the full suite's last line from
Step 1, and every line Step 6 printed. This task makes no commit: Step 3
showed a tree with nothing to add.
