"""The text layer of kubeagent's evidence gather.

kubeagent cleans every free-text field it reads from the cluster before a
model sees it, and it writes a pod's events in one fixed shape. This module
ports those pieces from kubeagent v1.24.0, byte for byte:

- `safetext_line` is `safetext.Line` (internal/safetext/safetext.go:69-107).
- `_sanitize` is the investigate package's `sanitize`: clean first, then
  redact addresses (internal/investigate/reader.go:88-90).
- `format_events` is `formatEvents` (internal/investigate/reader.go:312-322).
- `CRASH_FAMILY` names the issues whose previous log kubeagent reads.

The character rules lean on Unicode tables: Python's `unicodedata` here,
Go's `unicode` there. Python 3.12 and Go 1.26 both ship Unicode 15.0.0, so
the two agree on every character. Pure: no I/O, no state.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from kubeagent_verdict import contract as c

# The rune budget for one cleaned line, the ellipsis included
# (internal/safetext/safetext.go:28).
MAX_LINE = 512
# How many combining marks one base character may carry
# (internal/safetext/safetext.go:40).
MAX_COMBINING = 4

# The issues that mean a container crashed, so kubeagent reads and
# classifies its previous log (`crashFamily`,
# internal/investigate/gather.go:195-197).
CRASH_FAMILY = ("CrashLoopBackOff", "ContainerStartError", "OOMKilled")

# The whitespace controls and line separators that become a space
# (internal/safetext/safetext.go:79).
_FOLD = frozenset("\t\n\v\f\r\u2028\u2029")
# A run of lone surrogates. A str cannot hold bytes that are not UTF-8;
# decoding with errors="surrogateescape" keeps each one as a lone surrogate.
_SURROGATES = re.compile(r"[\ud800-\udfff]+")


def safetext_line(s: str) -> str:
    """Return `s` fit to print, as kubeagent's `safetext.Line` does.

    Four rules, in Go's order:

    1. Bytes that are not UTF-8 become U+FFFD, one for each run. Here they
       arrive as lone surrogates.
    2. Tab, newline, carriage return, vertical tab, form feed, U+2028 and
       U+2029 become a space. Every other control (Cc) and format (Cf)
       character is dropped.
    3. A combining mark (category M) is kept only while its base character
       carries fewer than MAX_COMBINING of them. A space is not a base, and
       a character dropped by rule 2 does not break the link to the base.
    4. The result is trimmed. Past MAX_LINE runes it is cut to one rune
       short, marks left at the cut go too, and "…" ends it.

    Idempotent: safetext_line(safetext_line(s)) == safetext_line(s).
    """
    # Rule 1 (safetext.go:70): strings.ToValidUTF8 writes one U+FFFD for
    # each run of bad bytes.
    s = _SURROGATES.sub("\ufffd", s)
    out = []
    base = False  # a base character is there for a mark to sit on
    marks = 0     # marks already on it
    for ch in s:
        # Rule 2 (safetext.go:78-84).
        if ch in _FOLD:
            ch = " "
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf"):
            continue  # dropped, and the base it interrupts outlives it
        # Rule 3 (safetext.go:85-94).
        if ch == " ":
            base, marks = False, 0
        elif cat[0] == "M":
            if not base or marks == MAX_COMBINING:
                continue
            marks += 1
        else:
            base, marks = True, 0
        out.append(ch)
    # Rule 4 (safetext.go:98-105). str.strip() also trims U+001C-U+001F,
    # which Go's TrimSpace does not, but rule 2 has already dropped them.
    s = "".join(out).strip()
    if len(s) > MAX_LINE:
        cut = s[:MAX_LINE - 1]
        while cut and unicodedata.category(cut[-1])[0] == "M":
            cut = cut[:-1]
        return cut + "…"
    return s


def _sanitize(s: str) -> str:
    """Clean one free-text field read from the cluster, such as an event's
    reason or message.

    Clean first, then redact, as kubeagent's `sanitize` does
    (internal/investigate/reader.go:88-90). A format character can sit
    inside an address and split it. Cleaning first joins the address back
    together, so the redaction still finds it.
    """
    return c.redact_addresses(safetext_line(s))


def format_events(namespace: str, name: str,
                  events: Sequence[tuple[str, str, int]]) -> str:
    """The events read's content, as kubeagent's `formatEvents` writes it
    (internal/investigate/reader.go:312-322).

    `events` holds (reason, message, count) tuples in the order kubeagent
    listed them. The reason and message are cleaned. The namespace and name
    are not: the API server already checks them. The count prints as it
    is, so 0 and 1 have no special form. With no events the content is one
    line with no newline at its end.
    """
    if not events:
        return f"no events for {namespace}/{name}"
    lines = [f"events for {namespace}/{name}:\n"]
    for reason, message, count in events:
        lines.append(f"  {_sanitize(reason)}: {_sanitize(message)} (x{count})\n")
    return "".join(lines)
