"""The duplication guard: evidence text shared between eval and training.

Group keys cannot see this shape of contamination -- two rows with different
identities and byte-identical evidence. That was contradiction_probe's
structural confound, first written as prose in a docstring. This makes it
a machine-checked fact.

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
disappearing as well as appearing -- a count that falls fails this as loudly
as one that rises, and the new number gets re-declared deliberately rather
than remembered. Same discipline as a golden file: a
curriculum change that moves these fails the test and the new numbers get
re-declared on purpose.
"""

import hashlib
import re

import pytest

from kubeagent_verdict.dataset import generate

# The release configuration. These counts are deterministic at exactly this
# seed and size and mean nothing at any other.
SEED, SIZE = 17, 8000

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
    # 2026-09-26 (faithful prompts): (20, 20) -> (18, 19). One read went:
    # `worker-containerd-stop` lost its PVC decoy (a mounted, Pending claim
    # cannot sit on a pod past scheduling), so its row renders one read, not
    # two. One read stopped matching by chance: the
    # `deployment-bad-image-tag` exam row lives in namespace `auth`, so the
    # mask turns "unauthorized" into "un<NS>orized". A kept training row in
    # `auth` used to render the same read; the rng stream moved and none
    # does now. Every other read is still reused, including the node
    # describes, which now print kubeagent's four conditions.
    # 2026-09-26 (faithful prompts): (18, 19) -> (55, 56). The slice is built
    # on the gather now, for the 17 entries the rules decide: 17 rows, each
    # reading its pod's events, the refuted decoy's describe and the
    # winner's read (a describe, a failed read, or nothing for a lease
    # ending), plus the log read for the crash family. These are the reads
    # an `attributed` row of the same entry makes, and the node decoy's
    # describe is the healthy describe most training rows render, so 55 are
    # reused. The miss is the claim decoy's describe, `pvc <ns>/aux-0:
    # phase=Bound storageClass=standard`: no training row mounts `aux-0`,
    # so none reads it.
    # 2026-09-26 (faithful prompts): (55, 56) -> (54, 56). The slice builds
    # the same reads. The node list grew from three workers to five, which
    # moved every later training draw, and one events read stopped matching
    # by chance: an `init-crashloop` row's BackOff line for container
    # `init-migrate` at (x5). No kept training row draws that container with
    # that count now. The `aux-0` miss stays. 55 - 1 = 54.
    # 2026-09-26 (faithful prompts): (54, 56) -> (55, 56). The slice builds
    # the same reads. coredns-corefile-broken now draws its restarts from 6,
    # which moved every later training draw, and the `init-crashloop`
    # BackOff read for `init-migrate` at (x5) matches a kept training row
    # again by chance. The `aux-0` miss stays. 54 + 1 = 55.
    "positional_probe": (55, 56),
    # Since 2026-09-24 this probe builds `own_cause`'s ruled-out prompt: no
    # object reads, and one log read on each of the five crash-family
    # entries. All five are reused, from `own_cause` and `wrong_attribution`
    # training rows, by design: the probe asks the same question those rows
    # train. The other fourteen rows render no reads. It read (14, 20) when
    # its menu still carried describe reads.
    # 2026-09-26 (faithful prompts): every row reads its pod's events first,
    # as kubeagent does for every workload it scopes, so each of the 19 rows
    # gains one read. 18 are reused: the events text is one template per
    # entry, and the mask blanks the row's ns, name and pod. The miss is
    # `deployment-bad-image-tag`'s: its pull events print the drawn image,
    # whose tag the mask does not blank. The five log reads are still
    # reused. (5, 5) -> (23, 24)
    # 2026-09-26 (faithful prompts): (23, 24) -> (23, 25). The new entry
    # `pvc-unbound-unschedulable` adds one row and its events read, which is
    # reused. Three matches moved by chance, as the job-1 rows now rotate
    # over 17 entries and every later training draw moved: the
    # `init-crashloop` and `restart-loop` events reads each matched one
    # `none_of_these` training row that drew the same container and restart
    # count, and no kept row does now; `deployment-bad-image-tag`'s pull
    # events, the old miss, now match a training row that drew the same tag.
    # 23 + 1 - 2 + 1 = 23.
    # 2026-09-26 (faithful prompts): (23, 25) -> (24, 25). The slice builds
    # the same reads; the five-worker node list moved every training draw,
    # and three matches moved by chance. The two old misses, an
    # `init-crashloop` and a `restart-loop` events read, now each match a
    # kept training row. `deployment-bad-image-tag`'s pull events miss
    # again: they print the drawn tag (`v2.8.4`), which the mask does not
    # blank, and no kept row drew it. 23 + 2 - 1 = 24.
    # 2026-09-26 (faithful prompts): (24, 25) -> (23, 25). The slice builds
    # the same reads. coredns-corefile-broken now draws its restarts from 6,
    # which moved every later training draw, and one match went by chance:
    # the `restart-loop` events read, a BackOff line for container `main` at
    # (x6), matches no kept training row now. The
    # `deployment-bad-image-tag` miss stays. 24 - 1 = 23.
    "misattribution_probe": (23, 25),
    # Same, in the multi shape. Since 2026-09-24 a crash-family constituent
    # reads its first object read and then its clear log read, the read
    # kubeagent makes for every crash-family workload; any other constituent
    # reads its first two object reads, as before. That adds 10 log reads and
    # drops 2 second object reads. All 10 log reads are reused: the clear log
    # read is one template per entry, and crash-family training rows render
    # it too. The one miss is the same events read as before. It read
    # (39, 40) when every constituent took its first two object reads.
    # 2026-09-26 (faithful prompts): (47, 48) -> (47, 50). The new entry
    # joins the pairing at the end, so the pair that wrapped round,
    # `volume-mount-error` with `memory-limit-oomkill` (3 reads, all hits),
    # became two pairs with `pvc-unbound-unschedulable` (2 and 3 reads, 4
    # hits). The miss is the new entry's refuted describe, `pvc <ns>/data-0:
    # phase=Bound storageClass=fast-ssd`, which no kept row renders under
    # that row's mask. The other pull events read of
    # `deployment-bad-image-tag` stopped matching: only that entry's
    # `attributed` and `truncated` training rows rendered it, and the rules
    # do not decide that entry, so neither case trains it now.
    # 47 - 3 - 1 + 4 = 47.
    # 2026-09-26 (faithful prompts): (47, 50) -> (80, 84). The slice is built
    # on the gather now: one gather over the whole row, which reads each
    # workload's pod events (40 reads, not 2), the describes of its refuted
    # menu (34, not 38), and the log read of each crash-family workload
    # (10). 80 are reused: the events text is one template per entry, and
    # the healthy node describe is the one most training rows render. The
    # 4 misses: `deployment-bad-image-tag`'s pull events print the drawn tag,
    # which the mask does not blank; a `restart-loop` workload in namespace
    # `web` whose container is also `web`, so the mask turns the container
    # into `<NS>` and no kept row matches that line at (x5); and two refuted
    # `pvc-unbound-unschedulable` claim describes (`pvc <ns>/data-0:
    # phase=Bound storageClass=fast-ssd`), which no kept row renders under
    # that row's mask. One of the two sits in namespace `data`, so the mask
    # also turns its `data-0` into `<NS>-0`. 84 - 4 = 80.
    "multi_misattribution_probe": (80, 84),
    # THIS ROW WAS THE POINT OF THE INSTRUMENT. It was written to catch this
    # slice reusing none_of_these_case's read text, which is why the slice
    # cannot catch a model reciting an entry-lookup table. Negative control v4
    # measured the known-broken first tune at 1.0 cause / 0.0 decoy here.
    # Re-measured 2026-09-24, per read: all 19 hits are the generic describe
    # reads ("node worker-2: unschedulable=false", a PVC's phase line) that
    # most refuted-menu training rows also render, and none of the 19
    # contradiction lines is reused. That was already so before
    # `none_of_these` moved to thin evidence, which left the count at 19.
    # It read 17/19 while `attributed` held 26% of the mix. Raising the two
    # shared-origin halves from 4% to 8% took the budget out of `attributed`,
    # which moved every later random draw, and one `none_of_these` training
    # row that used to draw the same node name as an exam read
    # (unschedulable=false on the same worker) now draws another. That is
    # one read falling out by chance, not the confound closing: 16 of 19
    # are still reused verbatim.
    # The mix rose again after that, from 8% to 12% on both shared-origin
    # halves, and the pool has since grown to forty-eight scenarios;
    # together they shifted another `none_of_these` draw and this row now
    # reads 17/19. The build size moving to 8000, this task's own change,
    # does not touch it: it already read 17/19 at size 5500 with the same
    # mix and pool, so the size is not what moved this row.
    # 2026-09-26 (faithful prompts): (19, 38) -> (20, 37). One read went:
    # `worker-containerd-stop` lost its PVC decoy, and with it the
    # "persistentvolumeclaims ... is forbidden" read, which was a hit. Two
    # contradiction lines are reused now, where none was before. A node
    # describe now prints kubeagent's four conditions with the kubelet's
    # stock messages, so the healthy describe that contradicts
    # `worker-containerd-stop`'s and `node-cordon-diskfull`'s scan finding
    # is byte for byte the ordinary healthy describe most training rows
    # render. That is the confound this row watches, measured, not closed:
    # the contradiction now lives only in the scan finding beside the read.
    # 19 - 1 + 2 = 20.
    # 2026-09-26 (faithful prompts): (20, 37) -> (24, 39). The slice is built
    # on the gather now, for the 17 entries the rules decide: 17 rows, not
    # 19. Each row reads its pod's events, with the entry's contradiction
    # events after its own; the describe of the one object it names, which
    # ends on its lease (16 nodes) or on a failed read (the claim); and the
    # log read for the five crash-family entries. 17 + 17 + 5 = 39. All 17
    # describes are hits: the healthy node describe is the one most
    # training rows render, and the failed claim read is too. All 5 log
    # reads are hits. Of the 17 events reads, the 2 with no contradiction
    # events (`worker-containerd-stop`, `pvc-unbound-unschedulable`) are
    # hits, and the 15 that carry a contradiction line are the 15 misses:
    # no training row prints those lines. 17 + 5 + 2 = 24.
    "contradiction_probe": (24, 39),
    # These rows are built from `stories.Story` objects, not from the catalog. An exam
    # story is never trained on (`stories.EXAM_KEYS` is held out of the training pool), so
    # a hit here is a read whose masked text a kept training row also prints: shared
    # wording, never a shared scenario.
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was (3, 34).
    "shared_origin_probe": (19, 40),
    # Its healthy-origin twin, declared rather than left out on purpose: an undeclared
    # slice is not measured at all, so the guard's coverage would silently lag the exam.
    # 2026-10-04 (Spec 4b-1): the 20 shared-origin exam rows were rebuilt on real lines;
    # was (2, 34).
    "shared_origin_decoy_probe": (13, 30),
}


def _reads(ex) -> list[str]:
    """Split a rendered evidence block into its individual reads.

    An empty block, rendered "(none)", has no reads. It is never hashed:
    the literal "(none)" would make every empty row collide with every
    other one regardless of content.
    """
    user = ex.user
    start = user.find(BEGIN)
    end = user.find(END, start)
    assert start >= 0 and end > start, (
        f"a {ex.case} row has no delimited evidence block; the guard refuses "
        f"to score a shape it cannot read")
    body = user[start + len(BEGIN):end]
    if body.strip() == "(none)":
        return []
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


# `_reads` refuses one shape and is unreachable on today's tree: every row
# the guard can reach renders a delimited evidence block. Unreachable is why
# it needs a test: deleting the assert changes no other test's outcome. It
# asserts the REFUSAL, not a value, because hashing an undelimited row would
# silently score zero reads.
#
# An EMPTY block renders "(none)". From 2026-09-24 a ruled-out row outside
# the crash family rendered one: no object read and no log read. Since
# 2026-09-26 every undecided row reads its pod's events first, as kubeagent
# does, so none is empty. Measured at SEED/SIZE: 0 of 7107 kept rows and 0
# of 252 test rows, down from 746 and 30. Job-1 rows read through the gather
# too since later on 2026-09-26, and it still holds: 0 of 7148 kept rows and
# 0 of 251 test rows. The contradiction rows moved to the gather on
# 2026-09-26 too, and it still holds: 0 of 7151 kept rows and 0 of 249 test
# rows. The `multi` rows moved to the gather on 2026-09-26 as well, and it
# still holds: 0 of 7164 kept rows and 0 of 249 test rows. The shared-origin
# family moved to real lines on 2026-10-04 (Spec 4b-1), and it still holds: 0 of
# 7178 kept rows and 0 of 249 test rows. Such a row would
# have no reads, so
# it would add nothing to the trained set and nothing to a slice's count.
# The `assert pairs` in the allowlist test still fails a slice that goes
# wholly empty.
def test_reads_refuses_a_row_with_no_delimited_evidence_block():
    with pytest.raises(AssertionError, match="no delimited evidence block"):
        _reads(_fake("a user turn that never opens an evidence section"))


def test_reads_gives_no_reads_for_an_empty_evidence_block_rather_than_hashing_none():
    assert _reads(_fake(f"{BEGIN}(none){END}")) == []


def test_reads_splits_a_well_formed_block_into_its_reads():
    """The positive control: the two refusals above reject bad input, not all
    input. Measured -- replacing `_reads`' body with an unconditional raise
    naming both refusal phrases passes BOTH tests above; this one fails.

    The allowlist test below catches that perturbation too, so this is not
    the only net. It is the cheap, local one: it fails in milliseconds and
    names `_reads`, where the allowlist test fails only after generating the
    whole 8000-row corpus and splitting it, and then names a count. It also
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
