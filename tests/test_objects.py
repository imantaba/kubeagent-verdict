import pytest

from kubeagent_verdict.dataset import objects as o


def node(**kw):
    base = {"kind": "node", "name": "{node}", "scan_reason": "NotReady",
            "placement": "on", "fresh": o.Fresh(ready="False")}
    base.update(kw)
    return o.Object(**base)


def pvc(**kw):
    base = {"kind": "pvc", "name": "{pvc}", "scan_reason": "ProvisioningFailed",
            "placement": "mounted",
            "fresh": o.Fresh(phase="Pending", storage_class="fast-ssd", volume="")}
    base.update(kw)
    return o.Object(**base)


def registry(**kw):
    base = {"kind": "registry", "name": "registry.example.com", "scan_reason": "2",
            "placement": "", "fresh": o.Fresh(literal="connection refused")}
    base.update(kw)
    return o.Object(**base)


def test_literal_tables_are_the_ones_decide_go_ships():
    assert o.CONNECTION_LITERALS[0] == "dial tcp"
    assert o.CONNECTION_LITERALS[-1] == "429 too many requests"
    assert len(o.CONNECTION_LITERALS) == 13
    assert o.AUTH_LITERALS == ("pull access denied", "no basic auth credentials",
                               "unauthorized", "denied")
    assert o.IMAGE_LITERALS == ("manifest unknown", "not found", "name unknown",
                                "repository does not exist", "invalid reference format")
    assert o.PULL_LITERALS == o.CONNECTION_LITERALS + o.AUTH_LITERALS + o.IMAGE_LITERALS


def test_valid_objects_construct():
    node()
    pvc()
    registry()
    node(fresh=o.Fresh(how="not_read"))
    node(fresh=o.Fresh(how="read_failed", message='nodes "{node}" is forbidden'))
    registry(fresh=o.Fresh(literal=""))


@pytest.mark.parametrize("bad, text", [
    ({"kind": "service"}, "object service/{node}: kind"),
    ({"scan_reason": "Broken"}, "object node/{node}: scan_reason"),
    ({"placement": "mounted"}, "object node/{node}: placement"),
    ({"fresh": o.Fresh(ready="Maybe")}, "object node/{node}: ready"),
    ({"fresh": o.Fresh(how="read_failed")}, "object node/{node}: read_failed needs a message"),
    ({"fresh": o.Fresh(how="later")}, "object node/{node}: how"),
    ({"intent": "joke"}, "object node/{node}: intent"),
    ({"fresh": o.Fresh(ready="True", wrong_pod=True)}, "object node/{node}: wrong_pod"),
])
def test_bad_node_values_name_the_object(bad, text):
    with pytest.raises(ValueError) as err:
        node(**bad)
    assert text in str(err.value)


@pytest.mark.parametrize("bad, text", [
    ({"scan_reason": "NotReady"}, "object pvc/{pvc}: scan_reason"),
    ({"placement": "on"}, "object pvc/{pvc}: placement"),
    ({"fresh": o.Fresh(phase="")}, "object pvc/{pvc}: phase"),
])
def test_bad_pvc_values_name_the_object(bad, text):
    with pytest.raises(ValueError) as err:
        pvc(**bad)
    assert text in str(err.value)


@pytest.mark.parametrize("bad, text", [
    ({"scan_reason": "two"}, "object registry/registry.example.com: scan_reason"),
    ({"placement": "on"}, "object registry/registry.example.com: placement"),
    ({"fresh": o.Fresh(literal="kaboom")}, "object registry/registry.example.com: literal"),
])
def test_bad_registry_values_name_the_object(bad, text):
    with pytest.raises(ValueError) as err:
        registry(**bad)
    assert text in str(err.value)


def test_registry_scan_reason_accepts_the_count_template():
    """A ruled registry story fills `scan_reason` in at render time (spec
    section 4, "Registry count"): the literal template string `"{count}"`
    must construct, alongside the digit strings every other registry
    object already uses."""
    registry(scan_reason="{count}")


def test_refute_gives_each_kind_its_healthy_ending():
    n = o.refute(node(scan_reason="no kubelet lease", fresh=o.Fresh(how="read_failed", message="x")))
    assert (n.scan_reason, n.fresh.how, n.fresh.ready, n.fresh.message) == ("NotReady", "read", "True", "")
    p = o.refute(pvc(fresh=o.Fresh(phase="Pending", storage_class="fast-ssd", volume="pv-0821")))
    assert (p.fresh.phase, p.fresh.volume, p.fresh.storage_class) == ("Bound", "pv-0821", "fast-ssd")
    r = o.refute(registry(fresh=o.Fresh(literal="unauthorized", wrong_pod=True)))
    assert (r.fresh.literal, r.fresh.wrong_pod) == ("manifest unknown", False)


def test_unverify_read_failed_carries_the_name_template():
    assert o.unverify(node(), "read_failed").fresh == o.Fresh(
        how="read_failed", message='nodes "{node}" is forbidden')
    assert o.unverify(pvc(), "read_failed").fresh.message == \
        'persistentvolumeclaims "{pvc}" is forbidden'
    assert o.unverify(registry(), "read_failed").fresh.message == "events is forbidden"


def test_unverify_kind_specific_endings():
    n = o.unverify(node(), "lease")
    assert (n.scan_reason, n.fresh.ready) == ("no kubelet lease", "True")
    assert o.unverify(registry(), "auth").fresh.literal == "unauthorized"
    assert o.unverify(registry(), "no_event").fresh.literal == ""


@pytest.mark.parametrize("obj, how", [
    (node(), "auth"), (pvc(), "lease"), (registry(), "lease"), (node(), "nope"),
])
def test_unverify_rejects_the_wrong_combination(obj, how):
    with pytest.raises(ValueError) as err:
        o.unverify(obj, how)
    assert f"cannot unverify a {obj.kind} by {how!r}" in str(err.value)


def test_drop_removes_one_object_and_keeps_order():
    a, b, c = node(), pvc(), registry()
    assert o.drop((a, b, c), b) == (a, c)


def test_check_objects_rejects_duplicates_and_names_the_entry():
    with pytest.raises(ValueError) as err:
        o.check_objects("crashloop-pod", (node(), node()))
    assert str(err.value) == "entry crashloop-pod: object node/{node} is declared twice"
    o.check_objects("crashloop-pod", (node(), pvc(), registry()))


def test_check_objects_wraps_a_bad_object_with_the_entry_key():
    bad = o.Object.__new__(o.Object)
    object.__setattr__(bad, "kind", "node")
    object.__setattr__(bad, "name", "{node}")
    object.__setattr__(bad, "scan_reason", "Broken")
    object.__setattr__(bad, "placement", "on")
    object.__setattr__(bad, "fresh", o.Fresh(ready="True"))
    object.__setattr__(bad, "intent", "decoy")
    with pytest.raises(ValueError) as err:
        o.check_objects("crashloop-pod", (bad,))
    assert str(err.value).startswith("entry crashloop-pod: object node/{node}: scan_reason")
