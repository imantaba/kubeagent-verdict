# Exam rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the nine exam-rebuild items together, build `out/dataset-1005-exam`, pass every gate, and re-pin the exam hashes once.

**Architecture:** Checker checks go first, since they move no row. Then three generator changes: the service line built by the `svchealth` port, the must-not words and key changes, and the scheduler sums. Next comes the full "is forbidden" text, then a pin test. One build task runs the gates, adds the "what moved" test and re-pins every red pin at once. A docs task closes the work.

**Tech Stack:** Python 3 (`src/kubeagent_verdict`), pytest, ruff. No Go change.

**Spec:** `docs/superpowers/specs/2026-10-05-exam-rebuild-design.md` (approved; item 9 added in 3b0dff2).

## Global Constraints

- The bars never move: 0.9 / 0.7 / 0.9 (`JOB2_BAR = 0.7`), FLOOR, BALANCE 0.10, CEILING 0.30, LABEL_CUE, 0.40/5, 0.12/0.30.
- `src/kubeagent_verdict/evals/score.py` does not change.
- These keep their bytes: `tests/fixtures/gather_go*/`, the four `tests/fixtures/gather_fixture*.yaml`, `tests/fixtures/rules_golden.json` and `contract/golden/`.
- The exam stays at 249 rows. The build is exactly `.venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-1005-exam`.
- Never run a test with `-update`. Never delete or change anything already in `out/`; reading it is fine.
- TDD: write the failing test, watch it fail, then implement.
- Every command starts with `cd /home/ubuntu/git/kubeagent-verdict &&` (the shell's cwd resets).
- PYTEST is `env -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` (allow 600000 ms for the full suite). The suite is 1,954 passed at the start.
- Ruff is `.venv/bin/ruff check --ignore EXE002 .` and must print `All checks passed!`.
- Commit only with `git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "..."`. Add files by name. Never `git add -A` or `git add .`. Never commit `.gitignore` or `train-v2.log`. Add no AI attribution of any kind: no `Co-Authored-By` trailer, no "Generated with" line.
- Never name the training host in a tracked file.
- Docs and test docstrings use simple voice: short sentences, plain words, numbers explained.
- `src/kubeagent_verdict/dataset/checker.py` imports only the standard library. A test enforces this, so the checker keeps its own copies of any helper it needs.
- **Allowed red between Tasks 2 and 6.** Only these may be red at the end of Tasks 2-6, and each task's report lists every red one with its old and new value:
  - hash pins: `FROZEN_SLICE_SHA256` (`tests/test_shared_origin_training.py:947`), `EVAL_SET_SHA256` (`:1101`), `GRADED_VIEW_SHA256` (`tests/test_exam_graded_view.py:237`) and `OTHER_FAMILIES_SHA256` (`tests/test_generate.py:1154`);
  - fixed-folder tests: `tests/test_exam_prompt_stability.py`, `test_no_prompt_byte_moves_from_dataset_1004` in `tests/test_catalog_gold.py`, and the `_needs_old` tests in `tests/test_multi_decoys.py`;
  - count pins: `tests/test_oracle.py`, the count asserts in `tests/test_answer_keys.py` (`checked == 7979`, the exam `counts == {...}`, `len(keys) == 34`, `story_keyed == 83`, `(total, non_empty) == (13946, 1085)`), the probe numbers in `tests/test_score.py` and `GATED_POOL` in `tests/test_catalog_gold.py`.
  
  Anything else red is a bug in the task. `_PROBE_DECOYS_SHA256` (`tests/test_cases.py:968`) must never go red. If it does, stop and report why.

## Review Focus

1. A story gold that holds one of its own must-not words must fail the build with a `ValueError`. It must not ship a gold the grader then marks wrong. Task 3 pins this.
2. IS-22's sum check must not false-fail on real scheduler text: a `(x3)` repeat suffix, a message wrapped in `(...)`, a message cut with `…`, the colon-less "for this pod" form, a count-less PVC clause, and a preemption tail. Task 4 pins each.
3. A service line on a row whose pod node is down must use the down-node form (`matching pods on down node <n> (NotReady)`), not `2 matching pods, 0 ready`. Task 2 pins this.
4. A PVC or registry `read_failed` ending with no namespace must raise. It must not print `in the namespace ""`. Task 5 pins this.
5. Rows must stay aligned with `out/dataset-1005`: the same counts per split and the same `case` at each index. Without that, the "what moved" test compares the wrong rows. Task 7 pins this.

---

### Task 1: The six tighter checker checks (item 7)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/checker.py` (`_b4` :876, `_b6` :918, `_b7` ~:998, `_f3` :1711-1737, `_txt_is15` :1836-1855, `_ans2` ~:2009-2035, plus a new `_FOLD`/`_norm_cause` copy)
- Test: `tests/test_checker.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `checker._norm_cause(s: str) -> str` and `checker._FOLD`, copies of `gold._norm_cause` and `gold._FOLD`. No rule is added or removed: `test_no_exemption_names_remain` still sees 51 rules.

Background: the golden user message (`contract/golden/user_message.txt`) has these lines: 2 `Cluster health (P1): DEGRADED — 2/4 nodes Ready.`, 3 `  node worker-1 NotReady: KubeletNotReady — container runtime is down`, 4 `  node worker-2 no kubelet lease`, 6 `  system kube-system/coredns 0/2 Degraded`, 46 `Service issues:`, 47 `  - shop/api (NoReadyEndpoints): service has 0 ready endpoints`. `_golden()` returns meta `None`, so ANS-2 never runs on it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_checker.py`. Add `gold` to the existing `from kubeagent_verdict.dataset import ...` line.

```python
# ------------------------------------------------ exam rebuild, item 7

def _golden_with(old: str, new: str) -> checker.Report:
    system, user, assistant, meta = _golden()
    assert old in user
    return checker.check(system, user.replace(old, new, 1), assistant, meta)


_SVC = "  - shop/api (NoReadyEndpoints): service has 0 ready endpoints\n"


@pytest.mark.parametrize("extra, fires", [
    ("  - zz/api (ClusterIP): no ready endpoints\n", False),
    ("  - aa/api (ClusterIP): no ready endpoints\n", True),            # out of order
    (_SVC, True),                                                       # duplicate key
    ("  - shop/api (LoadBalancer): no external address\n", False),      # NoExternalAddress after NoEndpoints
])
def test_b6_service_lines_sort_by_namespace_name_problem(extra, fires):
    rep = _golden_with(_SVC, _SVC + extra)
    assert ("B6" in _fired(rep)) is fires, _where(rep)


def test_b6_no_external_address_before_no_endpoints_fails():
    rep = _golden_with(_SVC, "  - shop/api (LoadBalancer): no external address\n" + _SVC)
    assert "B6" in _fired(rep), _where(rep)


_W1 = "  node worker-1 NotReady: KubeletNotReady — container runtime is down\n"


@pytest.mark.parametrize("tail, fires", [
    ("x " * 70, True),        # a 140-rune message with spaces
    ("y" * 121, False),       # 120 runes plus the cut mark fits
    ("y" * 122, True),
])
def test_f3_a_message_only_not_ready_line_is_cut_at_120_runes(tail, fires):
    rep = _golden_with(_W1, f"  node worker-1 NotReady: {tail.rstrip()}\n")
    assert ("F3" in _fired(rep)) is fires, _where(rep)


def test_f3_a_reason_keeps_the_512_cap():
    rep = _golden_with(_W1, "  node worker-1 NotReady: K" + "a" * 199 + "\n")
    assert "F3" not in _fired(rep), _where(rep)


@pytest.mark.parametrize("age, fires", [("0s", True), ("39s", True), ("40s", False),
                                        ("1m5s", False)])
def test_is15_a_lease_age_under_40s_fails(age, fires):
    """clusterhealth.go:137-144: a lease is stale only past 40s, so a
    younger age is never printed."""
    _s, user, _a, _m = _golden()
    assert _WORKER_2 in user
    fired, inspected = _is15(user.replace(
        _WORKER_2, f"  node worker-2 kubelet not heartbeating (lease {age} stale)\n", 1))
    assert inspected and fired is fires
```

`_WORKER_2` and `_is15` already exist (`tests/test_checker.py:407-417`). The line form is the one `test_is15_reads_a_lease_age_in_go_duration_form` uses.

```python
def test_b7_extra_system_lines_at_the_gather_cap(monkeypatch):
    system, user, assistant, meta = _golden()
    entries = len(checker._context(system, user, assistant, meta).p.entries)
    sys_line = "  system kube-system/coredns 0/2 Degraded\n"

    def run(extra: str, patch: bool) -> bool:
        if patch:
            monkeypatch.setattr(checker, "MAX_GATHER_WORKLOADS", entries)
        else:
            monkeypatch.setattr(checker, "MAX_GATHER_WORKLOADS", 10)
        rep = checker.check(system, user.replace(sys_line, sys_line + extra, 1), assistant, meta)
        return "B7" in _fired(rep)

    assert not run("  system kube-system/metrics-server 0/1 CrashLoopBackOff\n", True)
    assert run(sys_line, True)                                  # a rendered entry again
    assert run("  system kube-system/metrics-server\n", True)  # not a system line
    assert run("  system kube-system/metrics-server 0/1 CrashLoopBackOff\n", False)
```

For B4, find a built row with a policy line. Break it so the workload has a non-ProbeFailure finding:

```python
def test_b4_policy_line_needs_only_probe_failures(exam_rows):
    for row in exam_rows:
        system, user, assistant, meta = _parts(row)
        if "    network policy: pods selected by" not in user:
            continue
        x = checker._context(system, user, assistant, meta)
        e = next(e for e in x.p.entries
                 if any(checker._sub_kind(s.text) == "N" for s in e.subs)
                 and not any(checker._sub_kind(s.text) == "M" for s in e.subs))
        probe = next(s.text for s in e.subs
                     if s.text.startswith(checker._ISSUE_PREFIX + "ProbeFailure"))
        broken = user.replace(probe, probe.replace("ProbeFailure", "RestartLoop", 1), 1)
        assert "B4" not in _fired(checker.check(system, user, assistant, meta))
        assert "B4" in _fired(checker.check(system, broken, assistant, meta))
        return
    pytest.fail("no exam row carries a network-policy line")
```

For ANS-2: a key that sits only in a ruled-out candidate line passed before and must fail now.

```python
def test_ans2_does_not_count_a_ruled_out_candidate_line(exam_rows):
    for row in exam_rows:
        system, user, assistant, meta = _parts(row)
        x = checker._context(system, user, assistant, meta)
        for name, wm in meta["workloads"].items():
            b = x.block(name)
            if not wm["own_cause_keywords"] or b is None:
                continue
            for cd in b.cands:
                if cd.verdict != "ruled out" or user.lower().count(cd.cause.lower()) != 1:
                    continue
                m = copy.deepcopy(meta)
                m["workloads"][name]["own_cause_keywords"] = [cd.cause.lower()]
                assert "ANS-2" in _fired(checker.check(system, user, assistant, m))
                return
    pytest.fail("no exam row has a ruled-out candidate whose cause is unique in the prompt")
```

`copy` is already imported. A cand item's `fresh` list holds the fresh-read items under it (`checker.py:405-415`). Add a COPIES entry next to the others:

```python
    "_FOLD": (checker._FOLD, gold._FOLD),
```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_checker.py -k "b6_ or f3_a or is15_a_lease or b7_extra or b4_policy or ans2_does or copies"`
Expected: FAIL. The out-of-order and duplicate B6 cases, the 140-rune and 122-rune F3 cases, IS-15 at 0s and 39s, the B7 extra lines, B4, ANS-2, and the COPIES entry (`checker._FOLD` does not exist yet). The cases marked "passes" already pass.

- [ ] **Step 3: Implement**

In `checker.py`:

`_b4`: after the existing order check, add the netpol gate (`netpolicy.go:28-42`). An entry with a policy line ("N") and no "more findings" line ("M") may have only ProbeFailure findings:

```python
        if "N" in seq and "M" not in seq:
            kinds = [ln.text[len(_ISSUE_PREFIX):].split(" ", 1)[0]
                     for ln in e.subs if ln.text.startswith(_ISSUE_PREFIX)]
            if any(k != "ProbeFailure" for k in kinds):
                out.append((f"inventory line {e.line.no}", e.line.text))
```

Keep one violation per entry: if the order check already appended this entry, skip the second append.

`_b6`: keep the format and cap checks. Then add the order and uniqueness check (`svchealth.go:33-75`):

```python
    keys = []
    for ln in x.p.services:
        m = _SERVICE_LINE.match(ln.text)
        if m is None:
            continue
        ns, name, _typ, detail = m.groups()
        keys.append(((ns, name, "NoExternalAddress" if detail == "no external address"
                      else "NoEndpoints"), ln))
    for (prev, _), (key, ln) in zip(keys, keys[1:]):
        if key <= prev:
            out.append((f"user line {ln.no}", ln.text))
```

`_SERVICE_LINE` is `^  - (\S+)/(\S+) \((\S+)\): (.+)$`, so its four groups are namespace, name, type and detail. The rule checks order, not wording. The golden's `NoReadyEndpoints` line must still pass.

`_b7`: at 10 or more entries, today only the prefix is compared. Add: every line in `got_sys[len(want_sys):]` must match `_HEALTH_SYSTEM`; the extra names must be unique; and none may name a kube-system entry that is already rendered (`{e.name for e in x.p.entries if e.ns == "kube-system"}`). The checker cannot see a workload past the 10th. "Unique, well-formed and not a rendered one" is the closest check to the spec's "a matching flagged kube-system workload past the first 10".

`_f3`, the NotReady branch. Replace the `else:` arm:

```python
            elif not re.match(r"^[A-Z][A-Za-z0-9]*$", text):
                over = _runes_over(text, NOT_READY_MESSAGE_RUNES + 1)   # clusterhealth.go:206
            else:
                over = _runes_over(text)
```

`_txt_is15`: a lease token must also parse to at least 40 seconds (`clusterhealth.go:137-144`):

```python
_LEASE_MIN_NS = 40 * 10**9
...
            ns = _parse_duration(tok)
            if ns is None or ns < _LEASE_MIN_NS:
                bad.append(...)        # the same append the existing _duration_ok failure uses
```

Detector ages and rollout ages keep `_duration_ok` alone.

`_ans2`: add the copies near the other copied constants:

```python
# Copied from gold.py (the checker imports only the standard library);
# tests/test_checker.py COPIES pins the copy.
_FOLD = str.maketrans({**{chr(c): "-" for c in range(0x2010, 0x2016)}, "_": " "})


def _norm_cause(s: str) -> str:
    folded = unicodedata.normalize("NFKC", str(s)).translate(_FOLD)
    return " ".join(folded.lower().strip().rstrip(".").split())
```

Add `import unicodedata`. In `_ans2`, build `excluded` from the block, then drop every part that names one, as `gold.drop_excluded` does:

```python
        excluded = []
        if b is not None:
            parts += [b.heading.text] + [it.line.text for it in b.items]
            excluded = [_norm_cause(cd.cause) for cd in b.cands
                        if cd.verdict == "ruled out"
                        or any(f.outcome == "refuted" for f in cd.fresh)]
        for r in x.group_of(name) or []:
            parts += [r.label] + r.content.split("\n")
        kept = [p for p in parts if not any(e and e in _norm_cause(p) for e in excluded)]
```

The containment check then runs on `"\n".join(kept).lower()`. Update the docstrings of all six rules to name the Go line they follow.

- [ ] **Step 4: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_checker.py`
Expected: PASS. This includes `test_the_exam_pool_passes` and the manifest test that requires 0 violations. A built row that now fails is a real finding: stop and report it. Do not loosen the check.

Then run the full suite and ruff. Both must be fully green. This task moves no row, so no pin may go red.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/checker.py tests/test_checker.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "checker: six checks closer to kubeagent's Go output (exam rebuild item 7)"
```

---

### Task 2: The probe-failure service line, built by the port (item 9)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/catalog.py:72`, `src/kubeagent_verdict/dataset/entries_kinds.py:39`, `src/kubeagent_verdict/dataset/cases.py:226-230` and its callers at :322, :491 and :682, and `src/kubeagent_verdict/dataset/render.py` (`cluster_health` :280-335, `__all__` :25)
- Test: `tests/test_service_lines.py` (new); `tests/test_cluster_health.py`

**Interfaces:**
- Consumes: `health.Service`, `health.EndpointSlice`, `health.Pod`, `health.service_issues`, `health.annotate_endpoint_cause`, `health.DownNode`, `health.assess` (all exist).
- Produces:
  - `render.down_nodes(workloads: tuple[c.Workload, ...], reads: tuple[c.EvidenceRead, ...]) -> tuple[health.DownNode, ...]`;
  - `CatalogEntry.service_type: str | None = None`, which replaces `service_issue`;
  - `cases._service_issues(e: CatalogEntry, n: Names, down: tuple[health.DownNode, ...]) -> tuple[c.ServiceIssue, ...]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_service_lines.py`:

```python
"""Every service line in a build is one kubeagent's svchealth can print
(exam rebuild, item 9). The type in the brackets is the Service type. The
detail is one of svchealth's forms. The contract golden and the Go
fixtures are not built rows, so they keep their old line."""

from __future__ import annotations

import re

import pytest

from kubeagent_verdict.dataset import cases, catalog, generate, health

_LINE = re.compile(r"^  - (\S+)/(\S+) \(([^)]*)\): (.*)$")
_TYPES = ("ClusterIP", "NodePort", "LoadBalancer")
_DETAIL = re.compile(
    r"^(no external address|no ready endpoints"
    r"|no ready endpoints — declared via kubeagent\.io/expected-empty"
    r"|no ready endpoints \(backs (CronJob|Job) — expected between runs\)"
    r"|no ready endpoints \(backs DaemonSet — 0 desired\)"
    r"|no ready endpoints \(backs (Deployment|StatefulSet) — scaled to 0\)"
    r"|no ready endpoints — (the selector matches no pods"
    r"|matching pods on down node \S+ \(.+\)|matching pods on \d+ down nodes"
    r"|\d+ matching pods?, 0 ready))$")


def _service_lines(user: str) -> list[str]:
    lines = user.split("\n")
    if "Service issues:" not in lines:
        return []
    out = []
    for ln in lines[lines.index("Service issues:") + 1:]:
        if not ln.startswith("  - "):
            break
        out.append(ln)
    return out


@pytest.fixture(scope="module")
def built_rows() -> list[dict]:
    return [generate.to_row(ex) for ex in generate.generate(17, 8000)] + \
           [generate.to_row(ex) for ex in generate.test_set()]


def test_every_built_service_line_is_one_svchealth_prints(built_rows):
    seen = 0
    for row in built_rows:
        for ln in _service_lines(row["messages"][1]["content"]):
            seen += 1
            m = _LINE.match(ln)
            assert m, ln
            _ns, _name, typ, detail = m.groups()
            assert typ in _TYPES, ln
            assert _DETAIL.match(detail), ln
            if detail == "no external address":
                assert typ == "LoadBalancer", ln
    assert seen > 0


def test_the_probe_failure_entry_names_a_service_type():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    assert e.service_type == "ClusterIP"


def _names():
    return Names(ns="shop", name="api", pod="api-7d9", container="api",
                 init_container="init", image="shop/api:1.0", node="worker-1",
                 pvc="data", restarts=5)


def test_a_service_on_a_live_node_says_2_matching_pods_0_ready():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    (issue,) = cases._service_issues(e, _names(), ())
    assert (issue.type, issue.detail) == ("ClusterIP", "no ready endpoints — 2 matching pods, 0 ready")


def test_a_service_on_a_down_node_names_the_node():
    [e] = [e for e in catalog.all_entries() if e.service_type is not None]
    (issue,) = cases._service_issues(e, _names(), (health.DownNode("worker-1", "NotReady"),))
    assert issue.detail == "no ready endpoints — matching pods on down node worker-1 (NotReady)"
```

Add `from kubeagent_verdict.dataset.names import Names` to the imports (`Names` lives in `names.py:40`; its fields are ns, name, pod, container, init_container, image, node, pvc, restarts, and nodes=3).

Then add one test to `tests/test_cluster_health.py`, next to the test at :135 that it mirrors. It uses that file's own `_wl` and `_node` helpers:

```python
def test_down_nodes_names_the_node_the_block_prints_not_ready():
    """Exam rebuild, item 9: the service line's endpoint cause reads the
    same down nodes the cluster-health block judged."""
    workloads = (_wl(candidates=(_node("worker-2"),)),)
    assert render.cluster_health(workloads, ()).node_issues[0].startswith("worker-2 ")
    assert render.down_nodes(workloads, ()) == (health.DownNode("worker-2", "NotReady"),)
```

`health.assess` builds a NotReady node's `DownNode` with the reason `"NotReady"` (`health.py:176`).

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_service_lines.py tests/test_cluster_health.py`
Expected: FAIL. The wording test fails on lines like `(NoReadyEndpoints): service has 0 ready endpoints`, `service_type` does not exist, and neither does `down_nodes`.

- [ ] **Step 3: Implement**

`catalog.py:72`: replace the field.

```python
    service_type: str | None = None   # a Service fronts the workload; svchealth prints its line
```

`entries_kinds.py:39`: `service_type="ClusterIP",`.

`render.py`: move the body of `cluster_health` into `_assess(workloads, reads)`, which returns `health.assess(nodes, workloads)`'s pair. Then:

```python
def cluster_health(workloads, reads):
    """(docstring unchanged)"""
    return _assess(workloads, reads)[0]


def down_nodes(workloads: tuple[c.Workload, ...],
               reads: tuple[c.EvidenceRead, ...]) -> tuple[health.DownNode, ...]:
    """The nodes `cluster_health` judges down, from the same `health.assess`
    call: what svchealth's endpoint cause sees (AnnotateEndpointCause)."""
    return _assess(workloads, reads)[1]
```

Add `"down_nodes"` to `__all__`.

`cases.py:226`:

```python
def _service_issues(e: CatalogEntry, n: Names,
                    down: tuple[health.DownNode, ...]) -> tuple[c.ServiceIssue, ...]:
    """The entry's Service, through the svchealth port: one Service selecting
    app=<name>, one EndpointSlice with 2 not-ready addresses, and the
    workload's 2 not-ready pods on its node (the workload is 0/2 ready)."""
    if e.service_type is None:
        return ()
    sel = (("app", n.name),)
    svc = health.Service(n.ns, n.name, type=e.service_type, selector=sel)
    sl = health.EndpointSlice(n.ns, n.name, ready=("false", "false"))
    pods = (health.Pod(n.ns, n.pod, n.node, labels=sel),
            health.Pod(n.ns, f"{n.pod}-b", n.node, labels=sel))
    issues = health.annotate_endpoint_cause(
        health.service_issues((svc,), (sl,), ()), (svc,), pods, down)
    return tuple(i.contract() for i in issues)
```

Import `health` if `cases.py` does not already. At each caller (:322, :491, :682), pass the row's down nodes from the same workloads and reads the user message uses:

```python
    user = _user_message(None, "", _service_issues(e, n, render.down_nodes((w,), res.reads)),
                         (w,), res.reads, key=e.key)
```

At :682 the reads variable is `reads`, not `res.reads`.

Grep the tests for `service_issue=` and `.service_issue`, and move each one to `service_type`.

- [ ] **Step 4: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_service_lines.py tests/test_cluster_health.py tests/test_render.py tests/test_checker.py tests/test_cases.py`
Expected: PASS.

Then run the full suite. Only the allowed-red pins may fail. List each one with its old and new value. Run ruff.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_kinds.py src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/render.py tests/test_service_lines.py tests/test_cluster_health.py <any test file you moved to service_type> && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "dataset: build the probe-failure service line with the svchealth port (exam rebuild item 9)"
```

---

### Task 3: Must-not words and key changes (items 2, 3, 4, 5)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/catalog.py` (add `REGISTRY_FAULT` next to `INIT_CONTAINER` ~:93), `src/kubeagent_verdict/dataset/entries_slugs.py` (`deployment-bad-image-tag` :43-76, `networkpolicy-deny-all` :131-160), `src/kubeagent_verdict/dataset/stories.py` (`Answer` :31-56, the coredns healthy readiness answer :243-246, the disk-pressure ContainerStartError keys :1077-1090), `src/kubeagent_verdict/dataset/gold.py` (`RowGold` :132, `_row_gold` ~:185-208) and `src/kubeagent_verdict/dataset/cases.py:816`
- Test: `tests/test_answer_keys.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces:
  - `catalog.REGISTRY_FAULT: tuple[str, ...]`;
  - `stories.Answer.must_not: tuple[str, ...] = ()`;
  - `gold.RowGold.must_not: tuple[str, ...] = ()`, the last field, with a default;
  - shared-origin row meta `own_cause_must_not == list(rg.must_not)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_answer_keys.py`:

Grow `CHANGED` from seven entries to eight. Change `deployment-bad-image-tag` and add `networkpolicy-deny-all`:

```python
# Written out here, not imported, so a change to the constant fails.
REGISTRY_FAULT = ("unreachable", "refused", "timed out", "timeout", "unauthorized",
                  "authentication", "rate limit", "dial tcp", "no such host")

    # 2026-10-05 (exam rebuild, item 4): was INIT alone.
    "deployment-bad-image-tag": (("image", "registry"), (*INIT, *REGISTRY_FAULT)),
    # 2026-10-05 (exam rebuild, item 3): a liveness answer is not this readiness cause.
    "networkpolicy-deny-all": (("network", "policy"), ("liveness",)),
```

Rename `test_the_seven_changed_entries_carry_the_spec_table` to `test_the_changed_entries_carry_the_spec_table`, and add a dated rename note to its docstring. Add:

```python
def test_registry_fault_is_the_spec_tuple():
    assert catalog.REGISTRY_FAULT == REGISTRY_FAULT


def test_a_registry_fault_answer_scores_0_on_the_bad_tag_workloads(exam_rows):
    """The new probe (spec, "Numbers to record"). Before item 4 these
    answers passed the key ("image", "registry")."""
    hit = 0
    for row in exam_rows:
        for name, wm in row["meta"]["workloads"].items():
            if wm["expected_cause"] != "the image tag does not exist in the registry":
                continue
            kw, must_not = wm["own_cause_keywords"], wm["own_cause_must_not"]
            for cause in ("the image registry is unreachable",
                          "pulling the image from the registry timed out",
                          "the registry returned unauthorized for the image"):
                assert score.job2(wm, {"cause": cause}, kw, workload=name,
                                  own_cause_must_not=must_not) == 0.0
            assert score.job2(wm, {"cause": "the registry is not unreachable; the image tag is wrong"},
                              kw, workload=name, own_cause_must_not=must_not) == 1.0
            hit += 1
    assert hit > 0
```

Before writing the last assert, read how `score._keywords_match` handles a negated must-not word (the 4b-4 must-not window). If "is not unreachable" does not clear it the way the spec says, report this rather than change the sentence.

Split `test_the_exam_has_34_keys_and_exactly_the_3_weak_pairs` in two, so the key count (a count pin, re-pinned in Task 7 if it moves) and the pairs (this task's target) fail apart:

```python
def _exam_keys(exam_rows):
    keys = set()
    for row in exam_rows:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    return keys


def test_the_exam_has_34_keys(exam_rows):
    """(keep the old docstring's history) 2026-10-05 (exam rebuild): split from
    the weak-pairs test."""
    assert len(_exam_keys(exam_rows)) == 34


def test_the_exam_has_exactly_the_1_weak_pair(exam_rows):
    """(keep the history) 2026-10-05 (exam rebuild): 1 pair, was 3."""
    keys = _exam_keys(exam_rows)
    pairs = sorted({(cause_a, kw_a, cause_b, kw_b)
                    for cause_a, kw_a, must_not_a in keys
                    for cause_b, kw_b, _ in keys
                    if cause_b != cause_a
                    and score._keywords_match(cause_b, kw_a, must_not_a)})
    assert pairs == WEAK_PAIRS
```

Replace `WEAK_PAIRS` and its comment block with this. Keep the old dated comment lines above it, then add:

```python
# 2026-10-05 (exam rebuild, items 3 and 5): 1 pair, was 3. The liveness
# victim's gold now trips the catalog key's must-not word "liveness", and the
# coredns readiness key's must-not word "containerd" refuses the corefile
# entry's gold. The pair left is the same cause in two wordings: both golds
# say a default-deny NetworkPolicy is behind a failing readiness probe, so
# passing it is right.
WEAK_PAIRS = [
    ("a default-deny network policy blocks the probe's traffic to the pod", ('network', 'policy'),
     'its pods are selected by the NetworkPolicy default-deny, a possible cause of its failing readiness probe', ('readiness', 'policy')),
]
```

Then pin the shared-origin must-not field:

```python
def test_a_story_answer_refuses_a_must_not_word_in_its_own_cause():
    with pytest.raises(ValueError, match="must-not"):
        stories.Answer(anchor="x", cause="containerd is slow", keys=("slow",),
                       rationale="r", must_not=("containerd",))


def test_a_story_must_not_word_is_lowercase_and_not_empty():
    for bad in (("",), ("Containerd",)):
        with pytest.raises(ValueError):
            stories.Answer(anchor="x", cause="the probe is slow", keys=("slow",),
                           rationale="r", must_not=bad)


def _answers(cause: str) -> list[stories.Answer]:
    """Every story Answer with this cause, found by text, so a reorder of
    the story list cannot point a test at the wrong answer."""
    out = []
    for st in stories.by_key().values():
        for v in st.victims:
            out += [a for a in (v.broken, v.healthy) if a is not None and a.cause == cause]
    return out


def test_the_coredns_readiness_answer_refuses_containerd():
    """Item 5: this key ("deadline", "exceeded") passed the corefile entry's
    gold, which names containerd."""
    got = _answers("its readiness probe exceeded its deadline on a slow dependency")
    assert got and {a.must_not for a in got} == {("containerd",)}


def test_the_disk_pressure_cse_keys_name_the_origin():
    """Item 2: ("containerd", "task") named no origin."""
    got = _answers("its container cannot start because containerd failed to create its "
                   "task, with no space left on the device")
    assert got and {a.keys for a in got} == {("space", "containerd")}
```

The two cause strings are copied from `stories.py:243-246` (the coredns story's Deployment victim, `healthy`) and `:1077-1090` (the disk-pressure ContainerStartError victim, `broken`).

Replace the shared-origin branch of `test_every_pool_workload_carries_its_entrys_must_not_list`. Today it expects `[]`. Now a keyed shared-origin workload carries `INIT_CONTAINER` unless its own lines show an init-container status:

```python
            if shared_origin_row:
                own = gold.own_lines(row["messages"][1]["content"], [name])[name]
                init_victim = any("Init:" in ln for ln in own)
                got = wm["own_cause_must_not"]
                if not kw:
                    assert got == [], (row["meta"]["case"], name)
                elif init_victim:
                    assert not set(INIT) & set(got), (row["meta"]["case"], name)
                else:
                    assert got[-len(INIT):] == list(INIT), (row["meta"]["case"], name)
                story_keyed += bool(want)
                non_empty += bool(got)
                continue
```

Import `gold` and `stories`. Keep the `story_keyed == 83` and `(total, non_empty)` asserts. They are count pins, allowed red until Task 7.

Add a gold-side test:

```python
def test_a_story_gold_holding_its_own_must_not_word_fails_the_build():
    """Review Focus 1: a gold that names one of its own must-not words is
    refused at build time, not shipped for the grader to mark wrong.
    Answer.__post_init__ cannot see this: gold adds INIT_CONTAINER later,
    for every victim that is not an init victim."""
    word = catalog.INIT_CONTAINER[0]

    def poison(a):
        return None if a is None else dataclasses.replace(a, cause=f"{a.cause} ({word})")

    st = stories.by_key()["coredns-down"]
    victims = tuple(v if v.status.startswith("Init:") or v.issue.startswith("Init:")
                    else dataclasses.replace(v, broken=poison(v.broken), healthy=poison(v.healthy))
                    for v in st.victims)
    st = dataclasses.replace(st, victims=victims)
    raised = 0
    for seed in range(10):
        try:
            cases.shared_origin(st, random.Random(seed))
        except ValueError as err:
            assert "must-not" in str(err), err
            raised += 1
    assert raised > 0
```

Seeds 0-9 cover both worlds, and a row the rules decide uses no Answer, so the test needs only one named row among them. Import `dataclasses`, `random`, `cases` and `stories` in `tests/test_answer_keys.py`. `coredns-down` has 3 victims, and `catalog.INIT_CONTAINER[0]` is `"init container"`.

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_answer_keys.py`
Expected: FAIL on the changed entries, `REGISTRY_FAULT`, the registry probe, the weak pair, the Answer validation, the coredns and disk-pressure lookups, the shared-origin must-not branch, and the poisoned-gold test.

- [ ] **Step 3: Implement**

`catalog.py`, next to `INIT_CONTAINER`:

```python
# Words that name a registry fault rather than a missing tag (exam rebuild,
# item 4). G2 skips the bad-tag entry's 2-word decoy, so these do its job.
REGISTRY_FAULT = ("unreachable", "refused", "timed out", "timeout", "unauthorized",
                  "authentication", "rate limit", "dial tcp", "no such host")
```

`entries_slugs.py`:
- `deployment-bad-image-tag`: `own_cause_must_not=INIT_CONTAINER + REGISTRY_FAULT`;
- `networkpolicy-deny-all`: `own_cause_must_not=("liveness",)`.

`stories.py`, `Answer`: add `must_not: tuple[str, ...] = ()` after `link`. In `__post_init__`:

```python
        for w in self.must_not:
            if not w or w != w.lower() or w.strip() != w:
                raise ValueError(f"{self.cause!r}: must-not word {w!r} is not lowercase and trimmed")
            if w in self.cause.lower():
                raise ValueError(f"{self.cause!r}: must-not word {w!r} is inside the cause")
```

Then:
- the coredns healthy readiness answer (:243-246) gains `must_not=("containerd",)`;
- the disk-pressure ContainerStartError answer's keys become `("space", "containerd")` (:1077-1090). Check that both words are in its cause; `__post_init__` checks this too.

`gold.py`: import `catalog`. `RowGold` gains `must_not: tuple[str, ...] = ()` as its last field. In `_row_gold`'s named branch:

```python
            cause = so._sub(answer.cause, row.names, built.draw)
            init = t.status.startswith("Init:") or t.issue.startswith("Init:")
            must_not = answer.must_not + (() if init else catalog.INIT_CONTAINER)
            hit = [w for w in must_not if w in cause.lower()]
            if hit:
                raise ValueError(f"{row.key}: gold {cause!r} holds its own must-not word {hit[0]!r}")
            return RowGold("named", cause, answer.confidence, answer.keys, answer.rationale,
                           answer.link and built.world_name == "broken", must_not)
```

If `gold` importing `catalog` makes an import cycle, copy nothing. Report it instead. Check first with `.venv/bin/python -c "import kubeagent_verdict.dataset.gold"`.

`cases.py:816`: `own_cause_must_not=list(rg.must_not)`.

- [ ] **Step 4: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_answer_keys.py tests/test_stories.py tests/test_cases.py`
Expected: PASS, except the count pins named in Global Constraints. The new tests and `test_every_pool_gold_passes_its_own_key_with_must_not` must pass. If `checked` moves, that assert is a count pin.

Then run the full suite. List each red pin with its old and new value. Run ruff.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/catalog.py src/kubeagent_verdict/dataset/entries_slugs.py src/kubeagent_verdict/dataset/stories.py src/kubeagent_verdict/dataset/gold.py src/kubeagent_verdict/dataset/cases.py tests/test_answer_keys.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "dataset: must-not words for stories, registry faults and the weak pairs (exam rebuild items 2-5)"
```

---

### Task 4: IS-22's sum half and the scheduler texts (item 1)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/checker.py` (`_txt_is22` ~:1890-1920), `src/kubeagent_verdict/dataset/shared_origin.py` (`_sub` :110), and `src/kubeagent_verdict/dataset/stories.py` (network-unavailable :788-809, cordoned-draining :913-934, disk-pressure :1058-1090, the Job victim :1163-1166)
- Test: `tests/test_checker.py`

**Interfaces:**
- Consumes: Task 3's `Answer` (unchanged shape here).
- Produces: `checker._sched_sum_ok(text: str) -> bool`, and an `{other_nodes}` slot in `shared_origin._sub`, filled as `str(len(d.nodes) - 1)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_checker.py`:

```python
# ------------------------------------------------ exam rebuild, item 1

@pytest.mark.parametrize("text, ok", [
    ("0/3 nodes are available: 1 node(s) had untolerated taint {x: y}, 2 Insufficient cpu.", True),
    ("0/4 nodes are available: 1 node(s) had untolerated taint {x: y}, 2 Insufficient cpu.", False),
    ("0/3 nodes are available: 1 node(s) were unschedulable, 2 Insufficient memory. (x4)", True),
    ("(0/3 nodes are available: 3 Insufficient cpu.)", True),
    ("0/5 nodes are available: 1 node(s) were unschedulable, 2 node(s) had volume…", True),
    ("0/3 nodes are available for this pod", True),
    ("0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims.", True),
    ("0/3 nodes are available: 1 node(s) were unschedulable, pod has unbound immediate "
     "PersistentVolumeClaims.", False),
    ("0/3 nodes are available: 3 Insufficient cpu. preemption: 0/3 nodes are available: "
     "3 No preemption victims found for incoming pod.", True),
    ("0/3 nodes are available: 3 Insufficient cpu. preemption: 0/3 nodes are available: "
     "2 No preemption victims found for incoming pod.", False),
])
def test_sched_sum_ok(text, ok):
    assert checker._sched_sum_ok(text) is ok


def test_every_story_scheduler_line_sums_to_its_node_count():
    """The whole story set, both worlds, seeds 0-5 (spec item 1: "the whole
    4b-1 story set is swept")."""
    bad = []
    for st in stories.by_key().values():
        for world in ("broken", "healthy"):
            for seed in range(6):
                d = so.draw(st, random.Random(seed), width=len(st.victims))
                b = so.build(st, d, world=world)
                bad += [(st.key, world, seed, ln) for ln in b.user.split("\n")
                        if "nodes are available" in ln and not checker._sched_sum_ok(ln)]
    assert bad == []
```

Import `shared_origin as so` and `stories` if they are not imported. The signatures are `so.draw(story, rng, *, width)` and `so.build(story, d, *, world)`, and the result's `.user` is the prompt. All 47 stories build in both worlds at c23dab3.

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_checker.py -k "sched_sum or story_scheduler"`
Expected: FAIL. `_sched_sum_ok` does not exist. Once it does, the sweep fails on the disk-pressure lines at 4 and 5 nodes, the cordoned "2 node(s)" lines, and the colon-ful "no node fits this pod" line.

- [ ] **Step 3: Implement the rule**

In `checker.py`:

```python
_SCHED_PART = re.compile(r"\b0/(\d+) nodes are available: (.*)$")
_SCHED_COUNT = re.compile(r"^(\d+) ")
_SCHED_TIMES = re.compile(r"\s*\(x\d+\)$")


def _sched_sum_ok(text: str) -> bool:
    """IS-22's sum half: in "0/N nodes are available: <reasons>", the reason
    counts add up to N. Each " preemption: " part is checked alone. A part
    whose clauses carry no count (the PVC PreFilter message) is skipped, a
    part cut with "…" is skipped, and a part with some counts and not others
    fails. Real Kubernetes can give one node two reasons and over-count; the
    builder never writes that, so the sum must equal N."""
    for part in text.split(" preemption: "):
        m = _SCHED_PART.search(part)
        if not m:
            continue
        reasons = _SCHED_TIMES.sub("", m.group(2)).rstrip()
        if reasons.endswith("…"):
            continue
        clauses = [c.strip() for c in reasons.rstrip(").").split(",")]
        counts = [_SCHED_COUNT.match(c) for c in clauses]
        if not any(counts):
            continue
        if not all(counts) or sum(int(c.group(1)) for c in counts) != int(m.group(1)):
            return False
    return True
```

In `_txt_is22`, run `_sched_sum_ok` on every line the rule already scans (`x.p.inv` and `_content_lines(r)` of reads). This includes rows with no cluster-health header: today the function returns early there, so move the header check below the sum check. A line that already failed the total check is not appended twice. Keep the inspected count's meaning: lines that hold "nodes are available". Update the docstring.

- [ ] **Step 4: Fix the texts**

`shared_origin._sub` gains `"other_nodes": str(len(d.nodes) - 1)` next to `"nodes"`.

In `stories.py` (read each block first; the line numbers are from c23dab3):
- **network-unavailable (:788-809):** in both worlds' events, ", and the other nodes have insufficient memory" → ", {other_nodes} Insufficient memory". The healthy anchor "the other nodes have insufficient memory" → "Insufficient memory". The cause and rationale stay unless they quote the old words; if they do, they follow.
- **cordoned-draining (:913-934):** the broken evidence gains ", {other_nodes} node(s) had volume node affinity conflict" so it sums. Events "2 node(s) had volume node affinity conflict" → "{other_nodes} node(s) ...". Healthy evidence, events and anchor "3 node(s) had ..." → "{nodes} node(s) had ...". An anchor not run through `_sub` drops the count: "node(s) had volume node affinity conflict".
- **disk-pressure (:1058-1090):** "2 Insufficient cpu." → "{other_nodes} Insufficient cpu." in both worlds.
- **Job victim (:1163-1166):** events "no node fits this pod" → "{nodes} Insufficient cpu.". The evidence "0/{nodes} nodes are available for this pod" stays.

Then search the rest of `stories.py` for "nodes are available" and any hard-coded "<digit> node(s)" or "<digit> Insufficient". Fix any other line the sweep finds the same way.

- [ ] **Step 5: Run the tests**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_checker.py tests/test_stories.py tests/test_shared_origin_pipeline.py`
Expected: PASS. Then run the full suite: only the allowed-red pins may fail, so list them. A story-text test that pins an old sentence moves to the new one with a dated comment. Run ruff.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/checker.py src/kubeagent_verdict/dataset/shared_origin.py src/kubeagent_verdict/dataset/stories.py tests/test_checker.py <story-text tests you moved> && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "dataset: scheduler reasons sum to the node count; IS-22 checks it (exam rebuild item 1)"
```

---

### Task 5: B6, the full "is forbidden" text (item 6)

**Files:**
- Modify: `src/kubeagent_verdict/dataset/objects.py:152-160`, `src/kubeagent_verdict/dataset/render.py` (`draw_ending` :91, `deciding_ending` :116), `src/kubeagent_verdict/dataset/cases.py` (:295, :627, :999) and `src/kubeagent_verdict/dataset/shared_origin.py:21`
- Test: `tests/test_objects.py:103-108`, `tests/test_render.py` (:53, :73, :76), `tests/test_rule_rationale.py` (:71, :84), `tests/test_cases.py:509`, `tests/test_shared_origin_pipeline.py:52`, `tests/test_ruled_scenarios.py:449`, `tests/test_catalog_text.py:268`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `objects.unverify(obj: Object, how: str, *, namespace: str = "") -> Object`;
  - `render.draw_ending(obj, rng, *, namespace: str = "")`;
  - `render.deciding_ending(obj, rng, *, namespace: str = "")`;
  - `objects.SERVICE_ACCOUNT = "system:serviceaccount:kubeagent:kubeagent"`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_objects.py`, replace the short-text asserts at :103-108:

```python
_SA = "system:serviceaccount:kubeagent:kubeagent"


def test_read_failed_prints_the_api_servers_full_text():
    """Exam rebuild, item 6: kubeagent prints `read failed: ` + redact.Error(err),
    and redact.Error changes only URL errors, so the API server's text arrives
    whole. The user is kubeagent's own service account."""
    assert o.unverify(_NODE, "read_failed").fresh.message == (
        f'nodes "{_NODE.name}" is forbidden: User "{_SA}" cannot get resource "nodes" '
        'in API group "" at the cluster scope')
    assert o.unverify(_PVC, "read_failed", namespace="shop").fresh.message == (
        f'persistentvolumeclaims "{_PVC.name}" is forbidden: User "{_SA}" cannot get resource '
        '"persistentvolumeclaims" in API group "" in the namespace "shop"')
    assert o.unverify(_REGISTRY, "read_failed", namespace="shop").fresh.message == (
        f'events is forbidden: User "{_SA}" cannot list resource "events" in API group "" '
        'in the namespace "shop"')


@pytest.mark.parametrize("obj", [_PVC, _REGISTRY])
def test_a_namespaced_read_failed_needs_its_namespace(obj):
    """Review Focus 4: never `in the namespace ""`."""
    with pytest.raises(ValueError, match="namespace"):
        o.unverify(obj, "read_failed")


def test_the_origin_events_text_names_the_service_account():
    from kubeagent_verdict.dataset import shared_origin as so
    assert f'User "{_SA}"' in so.ORIGIN_EVENTS_FORBIDDEN
```

Use the module's real names for the node, PVC and registry fixtures. `_NODE`, `_PVC` and `_REGISTRY` stand in for whatever `tests/test_objects.py` already defines.

Move the other listed tests to the long text and the `namespace=` kwarg:
- `test_render.py:53, 73, 76`: `draw_ending` on a PVC passes `namespace=`. The seed sequences are unchanged, because `namespace` draws nothing.
- `test_rule_rationale.py:71, 84`: pass `namespace=`.
- `test_cases.py:509`: the menu's PVC message has the long form with `n.ns`.
- `test_shared_origin_pipeline.py:52`, `test_ruled_scenarios.py:449`, `test_catalog_text.py:268`: the long text.

`test_rules.py` and `test_checker.py` build their own messages and stay. The Go fixtures stay byte for byte.

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_objects.py tests/test_render.py tests/test_rule_rationale.py tests/test_cases.py tests/test_shared_origin_pipeline.py tests/test_ruled_scenarios.py tests/test_catalog_text.py`
Expected: FAIL on the new texts and on the `namespace=` kwarg (TypeError).

- [ ] **Step 3: Implement**

`objects.py`:

```python
# kubeagent's own identity: the deploy/rbac-*.yaml manifests create this account.
SERVICE_ACCOUNT = "system:serviceaccount:kubeagent:kubeagent"


def unverify(obj: Object, how: str, *, namespace: str = "") -> Object:
    """An ending the rules cannot settle: the object stays decided but unverified.

    A failed read prints the API server's whole refusal, as kubeagent does
    (`read failed: ` + redact.Error(err), internal/investigate/gather.go).
    A claim and an event list are namespaced, so they need `namespace`."""
    if how == "read_failed":
        if obj.kind in ("pvc", "registry") and not namespace:
            raise ValueError(f"{obj.kind} {obj.name}: a failed read needs its namespace")
        user = f'User "{SERVICE_ACCOUNT}"'
        message = {
            "node": (f'nodes "{obj.name}" is forbidden: {user} cannot get resource "nodes" '
                     'in API group "" at the cluster scope'),
            "pvc": (f'persistentvolumeclaims "{obj.name}" is forbidden: {user} cannot get '
                    f'resource "persistentvolumeclaims" in API group "" in the namespace "{namespace}"'),
            "registry": (f'events is forbidden: {user} cannot list resource "events" '
                         f'in API group "" in the namespace "{namespace}"'),
        }[obj.kind]
        return replace(obj, fresh=Fresh(how="read_failed", message=message))
    ...  # the rest unchanged
```

`render.py`: `draw_ending(obj, rng, *, namespace="")` and `deciding_ending(obj, rng, *, namespace="")` pass `namespace=namespace` to `unverify`. No rng draw changes.

`cases.py`:
- :295: `deciding_ending(obj, rng, namespace=n.ns)`;
- :627: `unverify(bind(obj, names), endings[obj.kind], namespace=n.ns)`;
- :999: `render.draw_ending(render.bind(obj, names_dict), rng, namespace=n.ns)`.

`shared_origin.py:21`:

```python
ORIGIN_EVENTS_FORBIDDEN = (f'events is forbidden: User "{objects.SERVICE_ACCOUNT}" cannot list '
                           'resource "events" in API group "" in the namespace "kube-system"')
```

Check that `shared_origin` already imports `objects`. `:226` is a node, so it needs no namespace.

- [ ] **Step 4: Run the tests**

Run the Step 2 command. Expected: PASS. Then run the full suite: only the allowed-red pins may fail, so list them. Then `git diff --stat c23dab3 -- tests/fixtures contract` must print nothing. Run ruff.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add src/kubeagent_verdict/dataset/objects.py src/kubeagent_verdict/dataset/render.py src/kubeagent_verdict/dataset/cases.py src/kubeagent_verdict/dataset/shared_origin.py tests/test_objects.py tests/test_render.py tests/test_rule_rationale.py tests/test_cases.py tests/test_shared_origin_pipeline.py tests/test_ruled_scenarios.py tests/test_catalog_text.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "dataset: a refused read prints the API server's full text (exam rebuild item 6)"
```

---

### Task 6: image-pull-secret-expired is graded as unverified (item 8)

**Files:**
- Test: `tests/test_shared_origin_training.py` (append)

**Interfaces:**
- Consumes: `cases.shared_origin(story, rng, victims=None, unverified=False)`, and `score.OVERCLAIM_WORDS` with `score._word_bounded_signal`.
- Produces: nothing.

This is a pin test. The behavior is already right, so the test passes at once. The spec accepts that, and the report must say so.

- [ ] **Step 1: Write the test**

```python
def test_image_pull_secret_expired_pull_victims_are_unverified():
    """Exam rebuild, item 8. Every victim with a registry candidate is job 1,
    outcome unverified; its gold is the decided cause, and its rationale
    claims no more than that. The exam has no row from this story, so this
    pins the training rows only."""
    st = stories.by_key()["image-pull-secret-expired"]
    seen = 0
    for seed in range(20):
        ex = cases.shared_origin(st, random.Random(seed))
        x = checker._context(ex.system, ex.user, ex.assistant, ex.meta)
        golds = {v["workload"]: v for v in json.loads(ex.assistant)["verdicts"]}
        for name, wm in ex.meta["workloads"].items():
            b = x.block(name)
            if b is None or not any("registry" in cd.cause for cd in b.cands):
                continue
            seen += 1
            assert (wm["job"], wm["decided_outcome"]) == (1, "unverified"), name
            assert golds[name]["cause"] == wm["decided_cause"], name
            assert not score._word_bounded_signal(golds[name]["rationale"],
                                                  score.OVERCLAIM_WORDS), name
    assert seen > 0
```

`Example` has `system`, `user`, `assistant` and `meta`. The assistant text is JSON with a `verdicts` list of `{workload, cause, confidence, rationale}`. Add `import random` and `from kubeagent_verdict.dataset import cases, checker` and `from kubeagent_verdict.evals import score`; the module already imports `json` and `stories`. The local is `golds`, because the module imports `gold`.

- [ ] **Step 2: Run it**

Run: `cd /home/ubuntu/git/kubeagent-verdict && <PYTEST> tests/test_shared_origin_training.py -k image_pull_secret_expired`
Expected: PASS at once. If it fails, the generator does not do what the spec says: stop and report. Do not change the generator in this task.

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_shared_origin_training.py && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "test: pin image-pull-secret-expired's pull victims as unverified (exam rebuild item 8)"
```

---

### Task 7: Build, gates, the "what moved" test and the one re-pin

**Files:**
- Create: `tests/test_exam_rebuild_moves.py`
- Modify: `tests/test_exam_prompt_stability.py` (`BANK`), `tests/test_catalog_gold.py` (remove `test_no_prompt_byte_moves_from_dataset_1004`; `GATED_POOL`), `tests/test_multi_decoys.py` (remove the `_needs_old` tests), `tests/test_answer_keys.py` (count pins; the new pool-pair test), `tests/test_shared_origin_training.py` (:947, :1101), `tests/test_exam_graded_view.py:237`, `tests/test_generate.py:1154` (if it moved), `tests/test_oracle.py` and `tests/test_score.py`
- Scratch (not committed): `<scratchpad>/gates.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `out/dataset-1005-exam/{train,val,test}.jsonl` (untracked) and a green suite.

- [ ] **Step 1: Build**

Run: `cd /home/ubuntu/git/kubeagent-verdict && env -u ALL_PROXY -u all_proxy .venv/bin/kv-dataset --seed 17 --size 8000 --out out/dataset-1005-exam`
Expected: it writes three files. `wc -l out/dataset-1005-exam/*.jsonl` shows test = 249. If the folder already exists, stop and ask. Never overwrite anything in `out/`.

- [ ] **Step 2: Write the "what moved" test**

This test checks Tasks 1-6 as a whole, so it passes as soon as it is written. If it fails, a task moved a row or a line it should not have: stop and report which.

Create `tests/test_exam_rebuild_moves.py`:

```python
"""What the exam rebuild moved (2026-10-05). It compares an in-process
build with out/dataset-1005, the last build before the rebuild. Rows stay
aligned: the same counts and the same case at every index. Every changed
prompt line is one of three kinds: a refused-read line (item 6), a
scheduler line (item 1) or a service line (item 9). Skips when the old
folder is not on this machine."""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from kubeagent_verdict.dataset import generate

OLD = pathlib.Path(__file__).resolve().parents[1] / "out" / "dataset-1005"
_SERVICE = re.compile(r"^  - \S+/\S+ \(")

pytestmark = pytest.mark.skipif(not (OLD / "test.jsonl").exists(),
                                reason="out/dataset-1005 is not on this machine")


def _old(split: str) -> list[dict]:
    return [json.loads(ln) for ln in (OLD / f"{split}.jsonl").read_text().splitlines()]


def _allowed(line: str) -> bool:
    return ("is forbidden" in line or "nodes are available" in line
            or "FailedScheduling" in line or _SERVICE.match(line) is not None)


@pytest.fixture(scope="module")
def new() -> dict[str, list[dict]]:
    """The build kv-dataset writes for --seed 17 --size 8000, in process
    (the same calls as dataset/cli.py:58-65)."""
    examples = generate.generate(seed=17, size=8000)
    train, val = generate.split(examples, seed=17)
    test = generate.test_set()
    return {"train": [generate.to_row(e) for e in generate.drop_held_out(train, test)],
            "val": [generate.to_row(e) for e in generate.drop_held_out(val, test)],
            "test": [generate.to_row(e) for e in test]}
```

Then add:

```python
@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_rows_stay_aligned(new, split):
    old = _old(split)
    assert len(new[split]) == len(old)
    assert [r["meta"]["case"] for r in new[split]] == [r["meta"]["case"] for r in old]


@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_every_changed_prompt_line_is_one_of_the_three_kinds(new, split):
    bad = []
    for i, (a, b) in enumerate(zip(_old(split), new[split])):
        old_lines = a["messages"][1]["content"].split("\n")
        new_lines = b["messages"][1]["content"].split("\n")
        if len(old_lines) != len(new_lines):
            bad.append((i, "line count"))
            continue
        bad += [(i, n) for o, n in zip(old_lines, new_lines) if o != n and not _allowed(n)]
    assert bad == []
```

The cordoned-draining evidence line gains a clause, but it is still a scheduler line, so this test allows it. If a story's prompt gains or loses a line, the test reports `line count`. That is a finding: report it.

Run the test. Expected: PASS, because it builds in process. A row's `meta` in the folder is a JSON object with a `case` key, so `r["meta"]["case"]` works on both sides.

- [ ] **Step 3: Run the gates**

Write `<scratchpad>/gates.py` (not committed). On `out/dataset-1005-exam` it prints, for each split:
- the row counts;
- checker violations by rule: `checker.check(system, user, assistant, meta)` on every row, which must be 0;
- the gold bot, `score.scoreboard(score.evaluate(rows, chat_fn))` with `chat_fn` returning each row's own assistant text, where `board["jobs"]["job1"|"job2"|"job3"]` must all be 1.0 and `board["overall"]["decoy_rate"]` must be 0.0;
- the `none_of_these` share of train workloads, which must be under 0.30.

It also runs the same numbers on `out/dataset-1005`. The before numbers include the IS-22 sum violations with the new rule. The script also prints the exam job counts and how many prompts and golds moved per split. Run it, and put its whole output in the task report. Every gate must hold before Step 4.

- [ ] **Step 4: Point the fixed-folder tests at the new build**

- `tests/test_exam_prompt_stability.py`: `BANK` reads `out/dataset-1005-exam/test.jsonl`, with a dated comment and the old path.
- `tests/test_catalog_gold.py`: remove `test_no_prompt_byte_moves_from_dataset_1004`.
- `tests/test_multi_decoys.py`: remove the `_needs_old` tests and the `_needs_old` helper if nothing else uses it.

Leave a dated comment at each spot: `# 2026-10-05 (exam rebuild): replaced by tests/test_exam_rebuild_moves.py.`

- [ ] **Step 5: Add the pool pair count**

In `tests/test_answer_keys.py`, add:

```python
def test_the_pool_weak_pair_count_does_not_grow(pool_rows, exam_rows):
    """Spec item 5: most pool pairs are benign (the same cause in other
    words, init vs main container, two NetworkPolicy names), so they are not
    swept. This pins their number so it cannot grow unnoticed. 178 before
    the rebuild (208 keys)."""
    keys = set()
    for row in pool_rows + exam_rows:
        for wm in row["meta"]["workloads"].values():
            kw = wm["own_cause_keywords"]
            if wm["job"] == 2 and score._is_job2_keyword_graded(wm, kw):
                keys.add((wm["expected_cause"], tuple(kw), tuple(wm["own_cause_must_not"])))
    pairs = {(a, ka, b) for a, ka, ma in keys for b, _, _ in keys
             if a != b and score._keywords_match(b, ka, ma)}
    assert (len(keys), len(pairs)) == (KEYS, PAIRS)
```

Run it once with the pin set to `(0, 0)`, then write the two numbers it reports in place of `KEYS` and `PAIRS`. Add a comment: `# 2026-10-05 (exam rebuild): measured on this build; was (208, 178) on main.` If the before numbers on main are not (208, 178), write the measured ones and say so in the report.

- [ ] **Step 6: Re-pin, once**

Run the full suite. For every allowed-red pin that fails, write the new value from the failure message. Each gets a comment `# 2026-10-05 (exam rebuild): was <old value>.` The pins:
- `FROZEN_SLICE_SHA256` and `EVAL_SET_SHA256` (`tests/test_shared_origin_training.py`), `GRADED_VIEW_SHA256` (`tests/test_exam_graded_view.py`), and `OTHER_FAMILIES_SHA256` (`tests/test_generate.py`) if it moved;
- the count pins in `test_oracle`, `test_answer_keys`, `test_score` and `GATED_POOL`.

`_PROBE_DECOYS_SHA256` must not move. If it does, stop and report why. Never use `-update`. A failing test that is not on the allowed-red list is a bug: report it and do not re-pin it.

- [ ] **Step 7: Run everything**

Run: the full suite (0 failed, 0 skipped on this machine), ruff, and `git diff --stat c23dab3 -- tests/fixtures contract src/kubeagent_verdict/evals/score.py`, which must print nothing.

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add tests/test_exam_rebuild_moves.py tests/test_exam_prompt_stability.py tests/test_catalog_gold.py tests/test_multi_decoys.py tests/test_answer_keys.py tests/test_shared_origin_training.py tests/test_exam_graded_view.py tests/test_oracle.py tests/test_score.py <tests/test_generate.py if moved> && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "test: re-pin the exam after the rebuild; add the what-moved test"
```

---

### Task 8: Docs

**Files:**
- Modify: `PIN.md`, `docs/model-card.md`

**Interfaces:**
- Consumes: Task 7's gates output and re-pin values (from its report).
- Produces: nothing.

- [ ] **Step 1: PIN.md**

Add a new entry, `### 2026-10-05 — Exam rebuild`, in the style of the 4b-4 entry above it. It says:
- the build folder (`out/dataset-1005-exam`) and the command;
- the three new hashes;
- each hand re-pin with its old and new value;
- every number from the spec's "Numbers to record", before and after:
  - prompt rows moved and gold rows moved (train, val, exam);
  - IS-22 sum violations (before with the new rule; after 0);
  - exam job counts;
  - `WEAK_PAIRS` (3 to 1) and the pool pair count;
  - the 4b-4 bots and probes on job 2;
  - the new registry-fault probe;
- a "Left" list: B4's fourth arm (needs a new Go capture), and the benign pool pairs.

For the bots and probes, re-run the 4b-4 bot and probe tests on the new exam and record what they print. If a test pins one of those numbers, Task 7 re-pinned it, so take the new value from there.

In the 4b-4 entry's "Left for the exam rebuild" list, add one dated line: `2026-10-05: done in "Exam rebuild" below, except B4's fourth arm.`

- [ ] **Step 2: docs/model-card.md**

- Add a dated note on each limit whose numbers moved.
- Update the decoy-rate bullet if its n moved.
- In the two 0920 sections, add one line: they scored the exam as it was before the 2026-10-05 rebuild.

Write in simple voice: short sentences, plain words, numbers explained ("1 of 34 keys").

- [ ] **Step 3: Check and commit**

Run ruff and the full suite once more; both must stay green. Then:

```bash
cd /home/ubuntu/git/kubeagent-verdict && git add PIN.md docs/model-card.md && git -c user.name=imantaba -c user.email=itn.taba@gmail.com -c core.fileMode=false commit -s -m "docs: PIN.md and model card for the exam rebuild"
```
