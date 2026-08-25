"""Structural guards over the generator, read with `ast`.

An eval-only probe that leaks into the training mix destroys the slice it
belongs to -- silently, because the row still renders and still scores. A
runtime check cannot see this: by the time generate() has run, a probe row
in the training set looks exactly like any other row.

Two halves, both required. A negative guard alone passes trivially if the
thing it forbids stops existing.

This guard REFUSES shapes it cannot read rather than skipping them. If
CASE_MIX stops being a tuple of literal pairs, or generate()'s calls stop
being plain `cases.<attr>(...)` calls, it fails by name -- widening it is
then a deliberate edit, not an accident. A best-effort guard that silently
skips an unfamiliar shape is not a guard.
"""

import ast
from pathlib import Path

from kubeagent_verdict.dataset import generate

GENERATE_PY = (Path(__file__).resolve().parents[1]
               / "src" / "kubeagent_verdict" / "dataset" / "generate.py")

# The five builders that exist to make a shortcut visible. A shortcut the
# training data rewards is not a shortcut the eval can detect.
EVAL_ONLY = frozenset({"positional_probe", "misattribution_probe",
                       "multi_misattribution_probe", "contradiction_probe",
                       "shared_origin_probe"})


def _module() -> ast.Module:
    return ast.parse(GENERATE_PY.read_text(encoding="utf-8"))


def _module_assign(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(
        f"{name} is no longer a module-level assignment in generate.py. "
        f"This guard refuses shapes it cannot read; widen it deliberately.")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(
        f"generate.py no longer defines a function named {name}. "
        f"This guard refuses shapes it cannot read; widen it deliberately.")


def _literal_case_names(value: ast.expr, what: str) -> list[str]:
    """The case-name strings out of CASE_MIX, refusing any other shape."""
    assert isinstance(value, ast.Tuple), (
        f"{what} is no longer a literal tuple ({type(value).__name__}). "
        f"A computed value cannot be read statically; this guard refuses it "
        f"rather than skipping it.")
    names = []
    for elt in value.elts:
        assert isinstance(elt, ast.Tuple) and len(elt.elts) == 2, (
            f"{what} entry is no longer a 2-tuple literal; refused.")
        head = elt.elts[0]
        assert isinstance(head, ast.Constant) and isinstance(head.value, str), (
            f"{what} entry's case name is no longer a string literal; refused.")
        names.append(head.value)
    return names


def test_case_mix_names_no_eval_only_case():
    names = _literal_case_names(_module_assign(_module(), "CASE_MIX"), "CASE_MIX")
    leaked = EVAL_ONLY & set(names)
    assert not leaked, f"eval-only cases in the training mix: {sorted(leaked)}"


def test_generate_calls_no_eval_only_builder():
    """generate() builds train/val. None of the five may be reachable from it."""
    fn = _function(_module(), "generate")
    called = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        assert not isinstance(func, ast.Subscript), (
            "generate() dispatches a call through a subscript, which cannot be "
            "read statically; refused rather than skipped.")
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "cases"):
            called.add(func.attr)
    leaked = EVAL_ONLY & called
    assert not leaked, f"generate() builds eval-only cases: {sorted(leaked)}"


def test_every_held_out_case_is_built():
    """The positive half.

    A name removed from held_out_case_set() while staying in HELD_OUT_CASES
    produces a smaller test set and no failure anywhere else.
    """
    tree = _module()
    value = _module_assign(tree, "HELD_OUT_CASES")
    assert isinstance(value, ast.Tuple), (
        "HELD_OUT_CASES is no longer a literal tuple; refused.")
    declared = []
    for elt in value.elts:
        assert isinstance(elt, ast.Constant) and isinstance(elt.value, str), (
            "HELD_OUT_CASES entry is no longer a string literal; refused.")
        declared.append(elt.value)

    fn = _function(tree, "held_out_case_set")
    handled = {node.value for node in ast.walk(fn)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    missing = [case for case in declared if case not in handled]
    assert not missing, f"declared in HELD_OUT_CASES but never built: {missing}"


def test_held_out_cases_all_reach_the_test_set():
    """The positive half again, behaviourally.

    The static check above reads names; this one checks rows actually arrive.
    Together they catch both a name that stops being built and a builder that
    stops producing.
    """
    present = {ex.case for ex in generate.test_set()}
    missing = set(generate.HELD_OUT_CASES) - present
    assert not missing, f"held-out cases absent from the test set: {sorted(missing)}"
