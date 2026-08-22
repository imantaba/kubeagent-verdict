import random
import re

from kubeagent_verdict.dataset import names


def test_draw_is_deterministic_per_seed():
    a = names.draw(random.Random(7))
    b = names.draw(random.Random(7))
    assert a == b
    assert a != names.draw(random.Random(8))


def test_drawn_values_come_from_the_allowlist():
    n = names.draw(random.Random(3))
    assert n.ns in names.NAMESPACES
    assert n.name in names.NAMES
    assert n.container in names.CONTAINERS
    assert n.init_container in names.INIT_CONTAINERS
    assert n.node in names.NODES
    assert n.pvc in names.PVCS
    assert re.fullmatch(rf"{n.name}-[0-9a-f]{{9}}-[a-z0-9]{{5}}", n.pod)
    assert re.fullmatch(r"registry\.example\.com/[a-z]+/[a-z]+:v\d\.\d\.\d", n.image)
    assert 1 <= n.restarts <= 40
