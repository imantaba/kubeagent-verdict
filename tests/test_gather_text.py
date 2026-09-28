"""Port tests for dataset/gather.py's text layer, and for the older ports it
stands on.

The text layer is kubeagent's line cleaner, its `sanitize`, its events
format and its crash family. The older ports are `contract.redact_addresses`,
`contract.cap_content`, `rules.read_text`'s PVC line and the log-read bodies
in `cases.LOG_READS`.

Every vector is copied from a kubeagent Go test at v1.24.0 and cites it as
`file:line` under kubeagent's `internal/`. Where Go has no test for the
exact shape, the expected text is built from Go's format string, and the
comment cites that line instead.
"""
from __future__ import annotations

import pytest

from kubeagent_verdict import contract as c
from kubeagent_verdict import vocab
from kubeagent_verdict.dataset import cases, catalog, gather, rules
from kubeagent_verdict.dataset import objects as o


def _go(raw: bytes) -> str:
    """The str form of a Go string literal whose bytes are not all UTF-8.

    A Python str cannot hold such bytes. Decoding with surrogateescape keeps
    each one as a lone surrogate, which is the form safetext_line takes.
    """
    return raw.decode("utf-8", "surrogateescape")


# Named, as in Go: a combining mark written inline sits on top of whatever
# comes before it (safetext/safetext_test.go:12-21).
ACUTE = "\u0301"      # Mn, combining acute accent
CEDILLA = "\u0327"    # Mn, combining cedilla
VOWEL_AA = "\u093e"   # Mc, Devanagari vowel sign AA (spacing)
ENCLOSE = "\u20dd"    # Me, combining enclosing circle
DEVA_KA = "\u0915"    # Devanagari KA, the base for VOWEL_AA
ZWJ = "\u200d"        # Cf, dropped before the mark rules run
CIRCUMFL = "\u0302"   # Mn, combining circumflex
DOT_BELOW = "\u0323"  # Mn, combining dot below
# "tiếng Việt" fully decomposed: two marks on each accented vowel.
VIET = "tie" + CIRCUMFL + ACUTE + "ng Vie" + DOT_BELOW + CIRCUMFL + "t"


def test_safetext_bounds_are_kubeagents():
    # safetext/safetext.go:28 and :40
    assert gather.MAX_LINE == 512
    assert gather.MAX_COMBINING == 4


# safetext/safetext_test.go:9, every case, in Go's order.
@pytest.mark.parametrize(("raw", "want"), [
    pytest.param('Error: ImagePullBackOff pulling "registry.example/app:1.2"',
                 'Error: ImagePullBackOff pulling "registry.example/app:1.2"', id="clean"),
    pytest.param("", "", id="empty"),
    pytest.param("\x1b[2J\x1b[Hgotcha", "[2J[Hgotcha", id="ansi-escape"),
    pytest.param("\x1b]0;pwned\x07rest", "]0;pwnedrest", id="osc-title"),
    pytest.param("a\x00b", "ab", id="nul"),
    pytest.param("real\rfake", "real fake", id="carriage-return"),
    pytest.param("line1\nline2", "line1 line2", id="newline"),
    pytest.param("a\tb", "a b", id="tab"),
    pytest.param("before\u202eafter", "beforeafter", id="rtl-override"),
    pytest.param("a\u200db", "ab", id="zero-width-joiner"),
    pytest.param("a\u2028b\u2029c", "a b c", id="line-separators"),
    pytest.param(_go(b"bad\xffbyte"), "bad\ufffdbyte", id="invalid-utf8"),
    pytest.param("  padded\n", "padded", id="trimmed"),
    pytest.param("caf\u00e9 \u2014 na\u00efve \u2713", "caf\u00e9 \u2014 na\u00efve \u2713",
                 id="non-ascii"),
    pytest.param(VIET, VIET, id="decomposed-diacritics"),
    pytest.param(ACUTE + "abc", "abc", id="mark-with-no-base"),
    pytest.param("a" + ACUTE * 20 + "b", "a" + ACUTE * 4 + "b", id="mark-stack-capped"),
    pytest.param("a" + ACUTE * 9 + "b" + CEDILLA * 9, "a" + ACUTE * 4 + "b" + CEDILLA * 4,
                 id="cap-per-base"),
    pytest.param(DEVA_KA + VOWEL_AA * 9, DEVA_KA + VOWEL_AA * 4, id="spacing-mark"),
    pytest.param("a" + ENCLOSE * 9, "a" + ENCLOSE * 4, id="enclosing-mark"),
    pytest.param("a" + ZWJ + ACUTE * 9, "a" + ACUTE * 4, id="dropped-format-keeps-base"),
    pytest.param("a\n" + ACUTE + "b", "a b", id="newline-resets-base"),
])
def test_safetext_line(raw, want):
    assert gather.safetext_line(raw) == want


# Rule 1 is strings.ToValidUTF8(s, "\ufffd") (safetext/safetext.go:70),
# which writes one U+FFFD for each RUN of bad bytes. No Go test has a run,
# so these vectors are built from that function's documented behavior.
@pytest.mark.parametrize(("raw", "want"), [
    pytest.param(_go(b"a\xff\xfeb"), "a\ufffdb", id="run-is-one"),
    pytest.param(_go(b"a\xe2\x80b"), "a\ufffdb", id="cut-character-is-one"),
    pytest.param(_go(b"a\xff") + "\ufffd" + _go(b"\xffb"), "a\ufffd\ufffd\ufffdb",
                 id="real-replacement-ends-a-run"),
])
def test_safetext_line_folds_a_run_of_bad_bytes(raw, want):
    assert gather.safetext_line(raw) == want


def test_safetext_line_takes_str_only():
    """A caller holding bytes decodes them first, as `_go` does."""
    with pytest.raises(TypeError):
        gather.safetext_line(b"bad\xffbyte")


def test_safetext_line_truncates_to_max_line_runes():
    # safetext/safetext_test.go:62
    got = gather.safetext_line("x" * (512 + 200))
    assert len(got) == 512
    assert got.endswith("…")


def test_safetext_line_truncates_on_rune_boundaries():
    # safetext/safetext_test.go:72. A str is never cut inside a character, so
    # what is left to check is that it encodes and holds exactly 512 runes.
    got = gather.safetext_line("\u00e9" * (512 + 200))
    got.encode("utf-8")
    assert len(got) == 512


def test_safetext_line_cut_does_not_decorate_the_ellipsis():
    # safetext/safetext_test.go:84. One leading rune, then base/mark pairs,
    # put a mark right at the cut. The mark goes, so a base ends the text.
    got = gather.safetext_line("x" + ("a" + ACUTE) * 512)
    assert got.endswith("a…")
    assert len(got) <= 512


# safetext/safetext_test.go:97
@pytest.mark.parametrize("raw", [
    "clean",
    "a\x1b[1mb",
    "x" * (512 + 10),
    _go(b"bad\xffbyte"),
    "a" + ACUTE * 60 + "b",
    ACUTE * 5 + "no base",
    ("a" + ACUTE * 9) * 80,
])
def test_safetext_line_is_idempotent(raw):
    once = gather.safetext_line(raw)
    assert gather.safetext_line(once) == once


def test_sanitize_truncates_to_max_line():
    # investigate/reader_test.go:173
    got = gather._sanitize("a" * (512 + 50))
    assert len(got) == 512
    assert got.endswith("…")


def test_sanitize_drops_format_characters():
    # investigate/reader_test.go:187
    assert gather._sanitize("before\u202eafter") == "beforeafter"


def test_sanitize_cleans_before_it_redacts():
    # investigate/reader_test.go:207. U+202E splits the address. Cleaning
    # first joins it back, so the redaction finds it; the other order does not.
    raw = "connecting to 10.96.\u202e0.10 failed"
    got = gather._sanitize(raw)
    assert "<redacted>" in got
    assert "10.96.0.10" not in got
    assert "10.96.0.10" in gather.safetext_line(c.redact_addresses(raw))


# redact/redact_test.go:66, against the existing port.
@pytest.mark.parametrize(("raw", "want"), [
    ("cannot reach a dependency (10.96.14.203:80) — connection refused",
     "cannot reach a dependency (<redacted>) — connection refused"),
    ("cannot reach a dependency (192.0.2.7) — connection refused",
     "cannot reach a dependency (<redacted>) — connection refused"),
    ("cannot reach a dependency ([fd00::1]:5432) — connection refused",
     "cannot reach a dependency (<redacted>) — connection refused"),
    ("cannot reach a dependency (db.chaos.svc.cluster.local:5432) — connection refused",
     "cannot reach a dependency (<redacted>) — connection refused"),
    ("tried 10.0.0.1:80 then 10.0.0.2:80", "tried <redacted> then <redacted>"),
])
def test_redact_addresses_redacts_what_a_log_can_carry(raw, want):
    assert c.redact_addresses(raw) == want


# redact/redact_test.go:94, against the existing port.
@pytest.mark.parametrize("prose", [
    "application panic (code bug)",
    "DNS resolution failed (name lookup)",
    "ran out of memory in-process",
    "cannot reach a dependency — connection refused",
    "0/2 ready, status CrashLoopBackOff, 5 restarts",
    "permission denied — check securityContext / file permissions",
    "back-off 5m0s restarting failed container",
])
def test_redact_addresses_leaves_ordinary_prose_alone(prose):
    assert c.redact_addresses(prose) == prose


def test_format_events_bytes():
    # investigate/reader_test.go:974
    assert gather.format_events("shop", "web-abc", ()) == "no events for shop/web-abc"
    events = (("BackOff", "Back-off restarting failed container", 4),)
    assert gather.format_events("shop", "web-abc", events) == (
        "events for shop/web-abc:\n  BackOff: Back-off restarting failed container (x4)\n")
    hostile = (("Failed", "pull\x1b[31m failed", 1),)
    assert "\x1b" not in gather.format_events("shop", "web-abc", hostile)


def test_format_events_prints_the_count_as_is():
    # investigate/reader.go:319, "  %s: %s (x%d)\n": 0 and 1 have no special
    # form, and the events keep their order.
    events = (("Scheduled", "assigned shop/web-abc to worker-1", 0),
              ("Pulled", "image already present", 1))
    assert gather.format_events("shop", "web-abc", events) == (
        "events for shop/web-abc:\n"
        "  Scheduled: assigned shop/web-abc to worker-1 (x0)\n"
        "  Pulled: image already present (x1)\n")


def test_format_events_redacts_reason_and_message():
    # investigate/reader_test.go:395
    events = (("FailedMount at 10.96.0.40:2049",
               "unable to mount volume from 10.96.0.41:2049", 1),)
    got = gather.format_events("shop", "web-abc", events)
    assert "10.96.0.40:2049" not in got
    assert "10.96.0.41:2049" not in got
    assert got.count("<redacted>") == 2


def test_cap_content_cuts_at_line_boundary_with_marker():
    # investigate/gather_test.go:167, against the existing port. The two
    # constants are investigate/gather.go:23 and :25.
    assert c.MAX_READ_BYTES == 4096
    assert c.TRUNCATION_MARKER == "[truncated by kubeagent]"
    long = ("a" * 99 + "\n") * 60
    got = c.cap_content(long)
    assert len(got.encode()) <= c.MAX_READ_BYTES + len(c.TRUNCATION_MARKER) + 1
    assert got.endswith("\n" + c.TRUNCATION_MARKER)
    for line in got.removesuffix("\n" + c.TRUNCATION_MARKER).split("\n"):
        assert len(line) == 99
    assert c.cap_content("one line\n") == "one line\n"


def test_one_events_read_is_capped_at_four_kib():
    # investigate/gather_test.go:187: 200 events on one pod make one read far
    # over the cap. The label is investigate/gather.go:90.
    events = tuple(("BackOff", "x" * 40, 1) for _ in range(200))
    read = c.EvidenceRead(label="events shop/web",
                          content=gather.format_events("shop", "web", events))
    bundle = c.render_evidence((read,))
    assert c.TRUNCATION_MARKER in bundle
    assert len(bundle.encode()) <= c.MAX_READ_BYTES + 1024


# investigate/reader.go:255-256 and gather.go:132, Go's format strings as
# written. Python's % prints a str as Go's %s does.
_DESCRIBE_PVC = "pvc %s/%s: phase=%s storageClass=%s volume=%s\n"
_DESCRIBE_LABEL = "describe %s %s/%s"


@pytest.mark.parametrize(("phase", "storage_class", "volume"), [
    ("Bound", "fast-ssd", "pv-0442"),
    # A nil storageClassName prints as "" (reader.go:251-254), and so does an
    # unset volumeName.
    ("Pending", "", ""),
])
def test_read_text_pvc_is_describe_pvc(phase, storage_class, volume):
    pvc = o.Object(kind="pvc", name="web-data", scan_reason="ProvisioningFailed",
                   placement="mounted",
                   fresh=o.Fresh(how="read", phase=phase, storage_class=storage_class,
                                 volume=volume))
    label, content = rules.read_text(pvc, ns="shop", pod="web-abc")
    assert label == _DESCRIBE_LABEL % ("pvc", "shop", "web-data")
    assert content == _DESCRIBE_PVC % ("shop", "web-data", phase, storage_class, volume)


def test_crash_family_is_kubeagents():
    # investigate/gather.go:195-197
    assert gather.CRASH_FAMILY == ("CrashLoopBackOff", "ContainerStartError", "OOMKilled")
    assert set(gather.CRASH_FAMILY) <= vocab.ISSUE_KINDS


# The ten causes internal/logscan can return, keyed by the signature that
# returns each, from TestClassify (logscan/logscan_test.go:9). The empty key
# is the fallback, which has no signature. The other logscan tests
# (logscan_test.go:43, 72, 98, 132, 167) name no cause or signature outside
# this table.
LOGSCAN_CAUSES = {
    "panic": "application panic (code bug)",
    "entrypoint": "bad command or entrypoint",
    "conn-refused": "cannot reach a dependency — connection refused",
    "dns": "DNS resolution failed (name lookup)",
    "oom-inproc": "ran out of memory in-process",
    "config": "configuration parse/validation error",
    "addr-in-use": "port already in use",
    "auth": "authentication/authorization failure to a dependency",
    "perm-denied": "permission denied — check securityContext / file permissions",
    "": "last output before exit (no signature in the last 25 lines)",
}

# investigate/reader.go:480 and :484, Go's format strings as written. `%q` of
# a DNS-1123 container name only adds the double quotes.
_GO_NO_PREVIOUS = ("no previous-instance log for %s/%s container %q "
                   "(nothing was refused; the container may not have restarted)")
_GO_NO_CLASSIFIABLE = "the previous log of %s/%s container %q has no classifiable output"


def _go_sprintf(fmt: str, ns: str, pod: str, container: str) -> str:
    return fmt.replace("%q", '"%s"') % (ns, pod, container)


@pytest.mark.parametrize("cause", list(LOGSCAN_CAUSES.values()))
def test_no_logscan_cause_holds_an_address(cause):
    """reader.go:486 redacts the cause before it sends it. None of the ten
    holds an address, so the body is "log cause: " plus the cause."""
    assert c.redact_addresses(cause) == cause


@pytest.mark.parametrize("body", [
    pytest.param(body, id=f"{key}-{arm}")
    for key, pair in cases.LOG_READS.items()
    for arm, body in zip(("clear", "thin"), pair)
    if body is not None
])
def test_log_read_body_is_one_kubeagent_can_send(body):
    """Each body is an arm of `logCauseResult` (reader.go:473-487): a
    classified cause, or one of the two texts for no cause."""
    if body.startswith("log cause: "):
        assert body.removeprefix("log cause: ") in LOGSCAN_CAUSES.values()
        return
    got = body.format(ns="shop", pod="web-abc", container="app")
    assert got in (_go_sprintf(_GO_NO_PREVIOUS, "shop", "web-abc", "app"),
                   _go_sprintf(_GO_NO_CLASSIFIABLE, "shop", "web-abc", "app"))


def test_catalog_log_causes_are_logscan_causes():
    """A finding's `log cause:` line is a logscan cause too."""
    for e in catalog.all_entries():
        if e.log_cause:
            assert e.log_cause in LOGSCAN_CAUSES.values(), e.key
