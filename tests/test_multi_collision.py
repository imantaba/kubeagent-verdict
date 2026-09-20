"""`cases.multi`'s prepended healthy-origin read (spec section 2) must
never contradict the row it heads: a node-story read naming a node that
some other object in the row already shows in a bad state, or a
registry-story read sitting next to a registry candidate of its own.

Unit tests build synthetic `Propagation`/`Object`/`Names` values directly,
one per rule branch (keep, rename, drop-all-three, registry-drop). The
build-level test spies on the real per-story decision functions during a
real `generate.generate(seed=17, size=8000)` run, so it exercises the
exact rotation and RNG stream `kv-dataset` runs, not a hand-picked replay.

Two ruled registry stories are in the trainable pool now (spec section 6's
pool merge), so the registry-drop branch is exercised for real during a
build, not only against the synthetic story the unit tests still use.
"""

from __future__ import annotations

from kubeagent_verdict.dataset import cases, generate
from kubeagent_verdict.dataset import objects as o
from kubeagent_verdict.dataset import propagation as prop
from kubeagent_verdict.dataset.names import Names

# --------------------------------------------------------------- fixtures


def _names(node: str = "worker-1") -> Names:
    return Names(ns="payments", name="notifier", pod="notifier-0-abc12",
                 container="app", init_container="init-config",
                 image="registry.example.com/payments/notifier:v1.0.0",
                 node=node, pvc="data-0", restarts=3)


def _node_story() -> prop.Propagation:
    return prop.Propagation(
        key="test-node-story", blast_radius="cluster", scope_field="node",
        origin="{node} is not Ready", shared_cause="the node is down",
        shared_reason="reason", distractor_cause="distractor",
        distractor_reason="distractor reason", rationale="rationale template",
        remedy="fix {node}", confidence="high",
        origin_read=("describe node {node}", "broken content for {node}"),
        healthy_origin_content="Conditions:\n  Ready  True  KubeletReady",
        victims=(),
    )


def _registry_story() -> prop.Propagation:
    return prop.Propagation(
        key="test-registry-story", blast_radius="cluster", scope_field=None,
        origin="the registry is unreachable", shared_cause="the registry is down",
        shared_reason="reason", distractor_cause="distractor",
        distractor_reason="distractor reason", rationale="rationale template",
        remedy="restore the registry", confidence="high",
        origin_read=("get_events (cluster-wide, reason=Failed)",
                     "12 pods report the same pull error"),
        healthy_origin_content="pods report unrelated pull errors",
        victims=(),
        origin_object=o.Object(kind="registry", name="registry.example.com",
                               scan_reason="3", placement="",
                               fresh=o.Fresh(how="read", literal="dial tcp"),
                               intent="cause"),
    )


def _node_object(name: str, *, ready: str = "True", how: str = "read") -> o.Object:
    return o.Object(kind="node", name=name, scan_reason="NotReady", placement="on",
                    fresh=o.Fresh(how=how, ready=ready,
                                  message="boom" if how == "read_failed" else ""),
                    intent="decoy")


def _registry_object() -> o.Object:
    return o.Object(kind="registry", name="registry.example.com", scan_reason="1",
                    placement="", fresh=o.Fresh(how="read", literal="manifest unknown"),
                    intent="decoy")


# ------------------------------------------------------------ unit tests


def test_is_node_story_true_when_the_label_names_a_node():
    assert cases._is_node_story(_node_story())


def test_is_node_story_false_for_a_cluster_wide_story():
    assert not cases._is_node_story(_registry_story())


def test_node_clashes_on_a_failed_read():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", how="read_failed"),))


def test_node_clashes_on_ready_false():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", ready="False"),))


def test_node_clashes_on_ready_unknown():
    assert cases._node_clashes("worker-1", (_node_object("worker-1", ready="Unknown"),))


def test_node_does_not_clash_on_ready_true():
    assert not cases._node_clashes("worker-1", (_node_object("worker-1", ready="True"),))


def test_node_does_not_clash_on_a_different_name():
    assert not cases._node_clashes("worker-1", (_node_object("worker-2", ready="False"),))


def test_healthy_origin_node_keeps_the_anchor_with_no_clash():
    assert cases._multi_healthy_origin_node("worker-1", ()) == "worker-1"


def test_healthy_origin_node_renames_to_the_first_free_worker_on_a_clash():
    all_objects = (_node_object("worker-1", ready="False"),)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-2"


def test_healthy_origin_node_skips_a_second_clashing_worker_too():
    all_objects = (_node_object("worker-1", how="read_failed"),
                   _node_object("worker-2", ready="Unknown"))
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-3"


def test_healthy_origin_node_drops_when_all_three_workers_clash():
    all_objects = tuple(_node_object(w, ready="False") for w in cases._WORKER_NAMES)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) is None


def test_healthy_origin_node_ignores_a_stale_lease_state():
    # A node the rules refuted or left on a stale lease still reads Ready
    # True -- section 2's own example of a non-clash.
    all_objects = (_node_object("worker-1", ready="True"),)
    assert cases._multi_healthy_origin_node("worker-1", all_objects) == "worker-1"


def test_resolve_keeps_the_anchor_node_with_no_clash():
    story = _node_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, ())
    assert result == ("describe node worker-1", "Conditions:\n  Ready  True  KubeletReady")


def test_resolve_renames_on_a_clash():
    story = _node_story()
    h = _names(node="worker-1")
    all_objects = (_node_object("worker-1", ready="False"),)
    result = cases._resolve_multi_healthy_origin(story, h, all_objects)
    assert result == ("describe node worker-2", "Conditions:\n  Ready  True  KubeletReady")


def test_resolve_drops_the_read_when_all_three_workers_clash():
    story = _node_story()
    h = _names(node="worker-1")
    all_objects = tuple(_node_object(w, ready="False") for w in cases._WORKER_NAMES)
    assert cases._resolve_multi_healthy_origin(story, h, all_objects) is None


def test_resolve_keeps_a_non_node_story_regardless_of_node_objects():
    story = _registry_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, (_node_object("worker-1", ready="False"),))
    assert result == ("get_events (cluster-wide, reason=Failed)",
                      "pods report unrelated pull errors")


def test_resolve_drops_a_registry_story_read_when_the_row_holds_a_registry_object():
    story = _registry_story()
    h = _names(node="worker-1")
    assert cases._resolve_multi_healthy_origin(story, h, (_registry_object(),)) is None


def test_resolve_keeps_a_registry_story_read_with_no_registry_object_in_the_row():
    story = _registry_story()
    h = _names(node="worker-1")
    result = cases._resolve_multi_healthy_origin(story, h, (_node_object("worker-1"),))
    assert result is not None


# --------------------------------------------------------- build-level tests


def test_a_real_registry_healthy_origin_read_is_dropped_next_to_its_own_candidate(monkeypatch):
    """The registry branch of `_resolve_multi_healthy_origin` (spec section 2)
    used to be exercised only synthetically: no story in the trainable pool
    set a registry `origin_object`, so a build never reached the
    registry-drop branch. `trainable_scenarios()` now includes the two ruled
    registry stories (spec section 6's pool merge), so it does. This spies
    on the real per-row decision during the exact `kv-dataset --seed 17
    --size 8000` build: a registry-story healthy origin is kept only when no
    victim in that row carries a registry candidate of its own, and dropped
    (the function returns `None`) whenever one does -- against the real
    rotation and RNG stream, not a hand-picked replay.
    """
    calls: list[tuple[bool, bool]] = []  # (row has a registry candidate, kept)
    original = cases._resolve_multi_healthy_origin

    def spy(healthy_origin, h, all_objects):
        result = original(healthy_origin, h, all_objects)
        if (healthy_origin.origin_object is not None
                and healthy_origin.origin_object.kind == "registry"):
            has_candidate = any(obj.kind == "registry" for obj in all_objects)
            calls.append((has_candidate, result is not None))
        return result

    monkeypatch.setattr(cases, "_resolve_multi_healthy_origin", spy)
    generate.generate(seed=17, size=8000)

    assert calls, "the rotation must reach at least one registry story"
    for has_candidate, kept in calls:
        assert kept != has_candidate, (has_candidate, kept)

    dropped = sum(1 for _, kept in calls if not kept)
    # Measured over this exact build (seed 17, size 8000): 12 multi rows draw
    # a registry-story healthy origin; the rule drops 2 of them and keeps 10.
    assert (len(calls), dropped) == (12, 2)


def test_no_real_healthy_node_read_names_a_clashing_node(monkeypatch):
    """Spies on the real per-story node decision during the exact
    `kv-dataset --seed 17 --size 8000` build, so this exercises the real
    rotation and RNG stream. A kept or renamed read's chosen name never
    clashes with the row it heads; a dropped read really did have all
    three worker names clashing. Also counts keep/rename/drop for the
    measured footnote.
    """
    calls: list[tuple[str, tuple, str | None]] = []
    original = cases._multi_healthy_origin_node

    def spy(h_node, all_objects):
        result = original(h_node, all_objects)
        calls.append((h_node, all_objects, result))
        return result

    monkeypatch.setattr(cases, "_multi_healthy_origin_node", spy)
    generate.generate(seed=17, size=8000)

    assert calls, "the rotation must reach at least one node story"

    kept = renamed = dropped = 0
    for h_node, all_objects, result in calls:
        if result is None:
            dropped += 1
            assert cases._node_clashes(h_node, all_objects)
            for w in cases._WORKER_NAMES:
                assert cases._node_clashes(w, all_objects)
            continue
        assert not cases._node_clashes(result, all_objects)
        if result == h_node:
            kept += 1
        else:
            renamed += 1

    # Re-measured 2026-09-19 over this exact build (seed 17, size 8000)
    # after the mix and pool changes in spec section 6: 96 multi rows draw a
    # node-story healthy origin; the rule keeps 59, renames 35 and drops 2.
    assert (len(calls), kept, renamed, dropped) == (96, 59, 35, 2)
