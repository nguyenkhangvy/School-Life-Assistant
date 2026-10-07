"""The mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4): an email's sessions, Periods, deadlines and
flags, read on the laptop with rules. Step 0 cleans the text, step 1 (mail_phrases) finds each sentence's dates and
times, and step 2 decides what each of them is. Pure functions: the email's text never leaves this module.

The rule names in the comments (D1, P4, S3 …) are the spec's, §4.3."""

import re
import unicodedata

from sla_agent import mail_words as words
from sla_agent.class_changes import SENTENCE_END, URL, fold

MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own

# Step 0 (§4.1), on folded text.
REPLY = re.compile(r"\s*(?:re|tl|tra loi)\s*:")
QUOTE_FROM = re.compile(r"\s*(?:from|tu)\s*:(?!\s*\d)")  # "Từ: 14h00" is a time, not a header
QUOTE_HEADER = re.compile(r"\s*(?:sent|date|to|da gui|gui|ngay|den)\s*:")
ORIGINAL = re.compile(r"\s*-{2,}\s*original message\s*-{2,}")
WROTE = re.compile(r"\s*(?:on|vao)\b.*\b(?:wrote|da viet)\s*:\s*$")


# ---- step 0: clean the text (§4.1) -----------------------------------------------------------------------------------


def _before_quote(lines):
    """A reply's own lines: everything before its first quoted part."""
    for i, line in enumerate(lines):
        folded = fold(line)
        if ORIGINAL.match(folded) or folded.lstrip().startswith(">"):
            return lines[:i]
        if WROTE.match(folded) or (i + 1 < len(lines) and re.match(r"\s*(?:on|vao)\b", folded)
                                   and WROTE.match(folded + " " + fold(lines[i + 1]))):
            return lines[:i]
        if QUOTE_FROM.match(folded) and any(QUOTE_HEADER.match(fold(below)) for below in lines[i + 1:i + 5]):
            return lines[:i]
    return lines


def clean(subject, text):
    """The text the times are read from: links removed; a reply without its quoted part (a forward keeps everything);
    no signature (from a line "--" on) and no lines giving office hours."""
    text = URL.sub(" ", unicodedata.normalize("NFC", text or "")).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if REPLY.match(fold(subject or "")):
        lines = _before_quote(lines)
    kept = []
    for line in lines:
        if line.strip() == "--":
            break
        hours = words.OFFICE_HOURS.spans(line)
        if hours and hours[0][0] == len(line) - len(line.lstrip()):
            continue
        kept.append(line)
    return "\n".join(kept)


def _sentences(text):
    """The sentences of `text`, split as in Events §3.2. A heading line about registration or a deadline, with no
    number in it ("THỜI GIAN ĐĂNG KÝ", then "Từ ngày 20/09 đến 22/09/2026."), is read together with the line after it."""
    found = [s for s in SENTENCE_END.split(text) if s.strip()]
    merged, i = [], 0
    while i < len(found):
        line = found[i]
        heading = (i + 1 < len(found) and not re.search(r"\d", line) and len(line.split()) <= MAX_HEADING_WORDS
                   and (words.REGISTRATION.spans(line) or words.CLOSING_STRONG.spans(line)))
        if heading:
            merged.append(line.strip().rstrip(":") + ": " + found[i + 1].strip())
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged
