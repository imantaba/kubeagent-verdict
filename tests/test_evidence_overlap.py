"""The duplication guard: evidence text shared between eval and training.

Group keys cannot see this shape of contamination -- two rows with different
identities and byte-identical evidence. That is contradiction_probe's
structural confound, and until now it was prose in a docstring
(cases.py:282-300). This makes it a machine-checked fact.

Two design decisions, both forced by measurement rather than assumed:

PER-READ, NOT PER-BLOCK. Whole-block raw hashing finds 2 of 86 rows, because
_fmt substitutes each row's freshly drawn namespace, name, pod and image, so
two rows from the same template are never byte-identical. A multi row's
BLOCK matches only on a coincidental entry pair; its individual READS are
plain attributed reads and are reused wholesale.

IDENTITY-MASKED, NOT RAW. Masking the row's own ns and name, then collapsing
the derived pod form, is what takes positional_probe from 6/25 to 23/25.
Without the pod mask the guard still fires, but detects only reads that
happen not to mention a pod -- a signal shaped by which template mentions
which field, not by what is shared.

Exact hashing after masking, never similarity. There is no repo precedent
for a similarity metric and a similarity threshold is a number nobody can
defend. Masked-exact needs no threshold and is a set lookup.

The counts below are PINNED, not bounded. A pinned count detects sharing
disappearing as well as appearing -- so when contradiction_probe's confound
is closed, 17/19 becomes 0/19, this fails, and the entry gets deleted
deliberately rather than remembered. Same discipline as a golden file: a
curriculum change that moves these fails the test and the new numbers get
re-declared on purpose.
"""

import hashlib
import re

import pytest

from kubeagent_verdict.dataset import generate

# The release configuration. These counts are deterministic at exactly this
# seed and size and mean nothing at any other.
SEED, SIZE = 17, 5500

# contract.section() writes "== BEGIN <name> ==\n<body>\n== END <name> ==\n\n";
# render_evidence() writes one "== <label> ==\n<content>\n\n" per read inside it.
BEGIN = "== BEGIN evidence ==\n"
END = "\n== END evidence =="
READ_DELIM = re.compile(r"(?m)^== .* ==$\n")

# names.draw() derives the pod from the workload name as <name>-<suffix>, so
# after the name is masked the pod reads <NAME>-<suffix>. Collapsing it is
# load-bearing: without it positional_probe reads 6/25 instead of 23/25.
POD = re.compile(r"<NAME>-[a-z0-9]{3,}(?:-[a-z0-9]{3,})?")

# slice -> (reads reused from train/val, total reads). Every entry is a
# measured fact with a reason; see the module docstring and the design spec.
DECLARED = {
    # Reuses attributed's reads by design -- the candidate menu is the only
    # perturbation, which IS the whole measurement. Costs nothing.
    "positional_probe": (23, 25),
    "misattribution_probe": (24, 25),
    # Same, in the multi shape: _reads(e, n)[:2] per constituent.
    "multi_misattribution_probe": (47, 50),
    # THIS ROW IS THE POINT OF THE INSTRUMENT. It reuses none_of_these_case's
    # read text verbatim, and none_of_these is a fixed 15% of every curriculum
    # via CASE_MIX -- which is why this slice cannot catch a model reciting an
    # entry-lookup table. Negative control v4 measured the known-broken first
    # tune at 1.0 cause / 0.0 decoy here. When that confound is closed this
    # becomes 0/19 and this entry must be deleted, not updated.
    "contradiction_probe": (17, 19),
    # THIS ROW IS THE POINT OF THE ALLOWLIST. Its rows come from
    # dataset.propagation, not the catalog, so it shares nothing -- which is
    # what shows the guard discriminates rather than rubber-stamping.
    "shared_origin_probe": (0, 34),
}


def _reads(ex) -> list[str]:
    """Split a rendered evidence block into its individual reads."""
    user = ex.user
    start = user.find(BEGIN)
    end = user.find(END, start)
    assert start >= 0 and end > start, (
        f"a {ex.case} row has no delimited evidence block; the guard refuses "
        f"to score a shape it cannot read")
    body = user[start + len(BEGIN):end]
    assert body.strip() != "(none)", (
        f"a {ex.case} row rendered an empty evidence block; the guard refuses "
        f"to score it rather than hashing the literal '(none)', which would "
        f"make every such row collide with every other regardless of content")
    return [part for part in READ_DELIM.split(body) if part.strip()]


def _mask(text: str, ex) -> str:
    """Blank the row's own identity so two rows from one template collide.

    A catalog group is `entry.key:ns/name`; a shared_origin_probe group is
    `propagation:<scenario>:ns/name`. rsplit takes the last field in both.

    This is a TEXTUAL replace, not a field-aware one, and is deliberately
    broader than "the row's own ns and name": the draw pools overlap, so a
    row in namespace `web` also blanks a container named `web`, and a row
    named `cache` blanks it inside the PVC `cache-0`. No direction is
    claimed for that imprecision: each row is masked with its OWN identity,
    so the mask is a different function per row and the effect on a given
    comparison is not predictable in general. What holds is narrower: the
    counts below were measured against exactly this behaviour, so they
    include whatever collisions it causes, and any drift still fails loudly.
    """
    for part in ex.group.split("+"):
        if ":" not in part or "/" not in part:
            continue
        ns, _, name = part.rsplit(":", 1)[1].partition("/")
        if ns:
            text = text.replace(ns, "<NS>")
        if name:
            text = text.replace(name, "<NAME>")
    return POD.sub("<POD>", text)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fake(user: str) -> generate.Example:
    """The smallest Example `_reads` will look at: it reads .user and .case."""
    return generate.Example(case="fake_probe", group="fake:ns/name",
                            system="", user=user, assistant="", meta={})


# `_reads` carries two refusals, and BOTH are unreachable on today's tree --
# measured over every row the guard can reach, 4587 kept + 253 test = 4840,
# all of which render a delimited, non-empty evidence block. That is the
# superset: the allowlist test below actually calls `_reads` on 4673 of them,
# because it reads only the five DECLARED slices out of the test set.
# Unreachable is exactly why they need tests: deleting
# either assert changes no other test's outcome, so without these two the
# guards are the vacuous shape this whole branch exists to prevent. They
# assert the REFUSAL, not a value, because a refusal is the entire
# behaviour: hashing an undelimited row would silently score zero reads, and
# hashing the literal "(none)" would make every empty row collide with every
# other one regardless of content -- a 100% reuse count that means nothing.
def test_reads_refuses_a_row_with_no_delimited_evidence_block():
    with pytest.raises(AssertionError, match="no delimited evidence block"):
        _reads(_fake("a user turn that never opens an evidence section"))


def test_reads_refuses_an_empty_evidence_block_rather_than_hashing_none():
    with pytest.raises(AssertionError, match="empty evidence block"):
        _reads(_fake(f"{BEGIN}(none){END}"))


def test_reads_splits_a_well_formed_block_into_its_reads():
    """The positive control: the two refusals above reject bad input, not all
    input. Measured -- replacing `_reads`' body with an unconditional raise
    naming both refusal phrases passes BOTH tests above; this one fails.

    The allowlist test below catches that perturbation too, so this is not
    the only net. It is the cheap, local one: it fails in milliseconds and
    names `_reads`, where the allowlist test fails only after generating the
    whole 5500-row corpus and splitting it, and then names a count. It also
    pins the split's exact shape -- the trailing blank line belongs to the
    read before it -- which the allowlist test only sees through a hash."""
    body = "== pod ==\nfirst read\n\n== events ==\nsecond read\n"
    assert _reads(_fake(f"{BEGIN}{body}{END}")) == [
        "first read\n\n", "second read\n"]


def test_eval_only_evidence_reuse_matches_the_declared_allowlist():
    exs = generate.generate(seed=SEED, size=SIZE)
    train, val = generate.split(exs, seed=SEED)
    test = generate.test_set()
    # What actually TRAINS -- post-filter, not the raw split.
    kept = generate.drop_held_out(train, test) + generate.drop_held_out(val, test)
    trained = {_digest(_mask(read, ex)) for ex in kept for read in _reads(ex)}

    measured = {}
    for case in DECLARED:
        pairs = [(ex, read) for ex in test if ex.case == case
                 for read in _reads(ex)]
        assert pairs, f"{case} produced no reads; the slice is missing"
        hits = sum(1 for ex, read in pairs if _digest(_mask(read, ex)) in trained)
        measured[case] = (hits, len(pairs))

    assert measured == DECLARED, (
        "declared evidence reuse moved. This is a golden-file-shaped failure: "
        "re-measure, understand WHY it moved, and re-declare on purpose. "
        "A count going DOWN is as meaningful as one going up.")
