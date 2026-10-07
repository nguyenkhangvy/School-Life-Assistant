"""The mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4): an email's sessions, Periods, deadlines and
flags, read on the laptop with rules. Step 0 cleans the text, step 1 (mail_phrases) finds each sentence's dates and
times, and step 2 decides what each of them is. Pure functions: the email's text never leaves this module.

The rule names in the comments (D1, P4, S3 …) are the spec's, §4.3."""

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, time

from sla_agent import mail_phrases as phrases
from sla_agent import mail_words as words
from sla_agent.class_changes import SENTENCE_END, URL, fold

MAX_DEADLINES = 5
MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own

# Step 0 (§4.1), on folded text.
REPLY = re.compile(r"\s*(?:re|tl|tra loi)\s*:")
QUOTE_FROM = re.compile(r"\s*(?:from|tu)\s*:(?!\s*\d)")  # "Từ: 14h00" is a time, not a header
QUOTE_HEADER = re.compile(r"\s*(?:sent|date|to|da gui|gui|ngay|den)\s*:")
ORIGINAL = re.compile(r"\s*-{2,}\s*original message\s*-{2,}")
WROTE = re.compile(r"\s*(?:on|vao)\b.*\b(?:wrote|da viet)\s*:\s*$")
# Step 2 (§4.3), on folded text.
DUE_TO = re.compile(r"\s+to\b")  # "due to the rain" is not a deadline


# ---- what the reader finds -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FoundDeadline:
    kind: str  # "opens", "register", "confirm" or "due"
    day: date
    at: time | None = None
    mode: str | None = None


@dataclass(frozen=True)
class Found:
    sessions: tuple = ()
    periods: tuple = ()
    deadlines: tuple = ()
    meeting: bool = False
    registered: bool = False

    @property
    def register_by(self):
        """The latest register deadline's day (what servers before stage 2 read), or None."""
        return max((d.day for d in self.deadlines if d.kind == "register"), default=None)


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


# ---- step 1: one sentence's phrases, and what is used (§4.2) ---------------------------------------------------------


class _Sentence:
    """A sentence, what step 1 found in it, and which of those step 2 has used."""

    def __init__(self, text, arrived):
        self.text = text
        self.parts = phrases.parts_of(text)
        self.days = phrases.days_in(text, arrived)
        self.lengths = phrases.lengths_in(text)
        taken = [(d.start, d.end) for d in self.days] + [(n.start, n.end) for n in self.lengths]
        self.clocks = phrases.clocks_in(text, taken)
        self.ranges, self.windows = phrases.ranges_in(text, self.days, self.clocks, arrived)
        self.weekday = phrases.weekday_filter(text)
        self.used = set()  # id() of the dates, times, ranges and windows a rule has used
        self.skip = False  # gives no day to the lines around it: a deadline, notice or not-an-event line
        self.sessions = []  # (FoundSession, position) made from this sentence
        self.relative = None  # (code, day) when this sentence's sessions took their day from a relative word
        self._spans = {}

    def spans(self, role):
        if role not in self._spans:
            self._spans[role] = role.spans(self.text)
        return self._spans[role]

    def part(self, position):
        return next(i for i, (start, end) in enumerate(self.parts) if start <= position <= end)

    def free(self, items):
        return [x for x in items if id(x) not in self.used]

    def use(self, *items):
        """Marks `items` used, with the dates and times inside a range or window."""
        for item in items:
            self.used.add(id(item))
            for inner in self.days + self.clocks:
                if item.start <= inner.start and inner.end <= item.end:
                    self.used.add(id(inner))

    def next_to(self, clock, day):
        """Whether a time and a date sit together: "14:00 ngày 15/10", "17/10 lúc 23:59"."""
        a, b = (clock.end, day.start) if clock.start < day.start else (day.end, clock.start)
        return a <= b and phrases.FILLER.fullmatch(fold(self.text[a:b])) is not None

    def day_for(self, clock):
        """A day for `clock` from this sentence: the date next to it, else a free date in its part, else in the
        sentence; else None."""
        beside = [d for d in self.days if self.next_to(clock, d)]
        if beside:
            return beside[0].day
        free = self.free(self.days)
        in_part = [d for d in free if self.part(d.start) == self.part(clock.start)]
        return (in_part or free)[0].day if free else None


def _target(sentence, span, right_after=False):
    """The free date or single time a word at `span` points at: the first after it in its part (only right after it
    when `right_after`), else the last before it in its part; None when there is none. Never one inside a date range
    or window: those are registration windows (D2) or Periods (P)."""
    part = sentence.part(span[0])
    spans = [(x.start, x.end) for x in sentence.free(sentence.ranges + sentence.windows)]
    items = [x for x in sentence.free(sentence.days + [c for c in sentence.clocks if c.finish is None])
             if sentence.part(x.start) == part and not any(a <= x.start and x.end <= b for a, b in spans)]
    after = sorted((x for x in items if x.start >= span[1]), key=lambda x: x.start)
    if after:
        if right_after and not phrases.FILLER.fullmatch(fold(sentence.text[span[1]:after[0].start])):
            return None
        return after[0]
    before = [x for x in items if x.end <= span[0]]
    return None if right_after or not before else max(before, key=lambda x: x.start)


def _moment(sentence, item):
    """(day, time, items) a word points at: a date with the time next to it, or a time with the date next to it;
    a time alone borrows its part's or sentence's date (which stays free)."""
    if isinstance(item, phrases.Day):
        beside = [c for c in sentence.free(sentence.clocks) if c.finish is None and sentence.next_to(c, item)]
        return item.day, beside[0].begin if beside else None, [item] + beside[:1]
    beside = [d for d in sentence.free(sentence.days) if sentence.next_to(item, d)]
    if beside:
        return beside[0].day, item.begin, [item, beside[0]]
    return sentence.day_for(item), item.begin, [item]


def _within(span, spans):
    return any(start <= span[0] and span[1] <= end and (start, end) != span for start, end in spans)


# ---- step 2: what each sentence takes, in order (§4.3, steps 1–4) ----------------------------------------------------


def _drop(sentence):
    """N: a not-an-event or cancelled sentence gives nothing; a rescheduling keeps only what follows "sang"."""
    if sentence.spans(words.NOT_AN_EVENT) or sentence.spans(words.CANCEL):
        sentence.use(*sentence.days, *sentence.clocks, *sentence.ranges, *sentence.windows)
        sentence.skip = True
        return
    for start, end in sentence.spans(words.RESCHEDULE):
        pivot = next((p for p in sentence.spans(words.PIVOT) if p[0] >= end), None)
        if pivot:
            sentence.use(*[x for x in sentence.days + sentence.clocks + sentence.ranges + sentence.windows
                           if start <= x.start and x.end <= pivot[0]])


def _arrivals(sentence):
    """Arrival words take their times first ("có mặt trước 13:45"), so their "trước" is never read as a deadline.
    "Mở cửa từ" counts only with one time: with a range it gives open hours."""
    found = []
    for span in sentence.spans(words.ARRIVAL):
        part = sentence.part(span[0])
        clock = next((c for c in sentence.free(sentence.clocks) if sentence.part(c.start) == part and c.start >= span[1]),
                     None)
        if clock is None or (fold(sentence.text[span[0]:span[1]]).startswith("mo cua") and clock.finish is not None):
            continue
        sentence.use(clock)
        found.append(clock)
    return found


def _kind(sentence, span, strong):
    """D1: the nearest confirm, due or registration word in the sentence gives the kind; a strong deadline word
    without one is "due"; a soft one without one is no deadline (None)."""
    kinds = [(abs(start - span[0]), rank, kind)
             for rank, (kind, role) in enumerate((("confirm", words.CONFIRM), ("due", words.DUE),
                                                  ("register", words.REGISTRATION)))
             for start, _ in sentence.spans(role)]
    return min(kinds)[2] if kinds else ("due" if strong else None)


def _deadlines(sentence):
    """D: [(FoundDeadline, position)]: the sentence's deadlines; they use the dates and times they take."""
    found = []

    def add(kind, position, day, at, items):
        if day is not None:
            found.append((FoundDeadline(kind, day, at), position))
            sentence.use(*items)

    registration = sentence.spans(words.REGISTRATION)
    starts = sentence.spans(words.START) + sentence.spans(words.EVENT)
    # D2: a registration word, then in its part a date range, a window, or a time range with a date, with no event
    # word between them.
    for reg in registration:
        part = sentence.part(reg[0])
        for item in sentence.free(sentence.windows + sentence.ranges + [c for c in sentence.clocks if c.finish]):
            if sentence.part(item.start) != part or item.start < reg[1]:
                continue
            if any(reg[1] <= start < item.start for start, _ in starts):
                continue
            if isinstance(item, phrases.Window):
                add("opens", reg[0], item.first, item.begin, [item])
                add("register", reg[0], item.last, item.finish, [item])
            elif isinstance(item, phrases.DayRange):
                add("opens", reg[0], item.first, None, [item])
                add("register", reg[0], item.last, None, [item])
            else:
                day = sentence.day_for(item)
                add("opens", reg[0], day, item.begin, [item])
                add("register", reg[0], day, item.finish, [item])
    # D3: an opening word, in a registration sentence.
    if registration:
        for span in sentence.spans(words.OPENING):
            target = _target(sentence, span)
            if target is not None:
                add("opens", span[0], *_moment(sentence, target))
    # D1: closing words. "Due to the rain" is not a deadline.
    strong = [s for s in sentence.spans(words.CLOSING_STRONG)
              if not (fold(sentence.text[s[0]:s[1]]) == "due" and DUE_TO.match(fold(sentence.text[s[1]:])))]
    soft = [s for s in sentence.spans(words.CLOSING_SOFT) if not _within(s, strong)]
    only_in_registration = sentence.spans(words.ONLY_IN_REGISTRATION)
    right_after = sentence.spans(words.RIGHT_BEFORE)
    for span in sorted(set(strong + soft)):
        if span not in strong and span in only_in_registration and not registration:
            continue
        kind = _kind(sentence, span, span in strong)
        target = kind and _target(sentence, span, right_after=span in right_after)
        if target is not None:
            add(kind, span[0], *_moment(sentence, target))
    if found and not sentence.free(sentence.days):
        sentence.skip = True
    return found


# ---- what is kept, with its mode (§4.3, D4, M, S7) -------------------------------------------------------------------


@dataclass(frozen=True)
class _Modes:
    """M: whether an email has online and in-person words, and the mode they give one of its items."""

    online: bool
    in_person: bool

    def of(self, sentence, position, whole_email):
        """The mode of an item at `position` in `sentence`: from the words of its part, else of its sentence; else, with
        `whole_email` (for sessions), online when the email has only online words."""
        part = sentence.parts[sentence.part(position)]
        for start, end in (part, (0, len(sentence.text))):
            if any(start <= s < end for s, _ in sentence.spans(words.ONLINE)):
                return "online"
            if self.online and any(start <= s < end for s, _ in sentence.spans(words.IN_PERSON)):
                return "in_person"
        return "online" if whole_email and self.online and not self.in_person else None


def _kept_deadlines(deadlines, heading, modes):
    """D4 and M: [(sentence, FoundDeadline, position)] as kept: each with its mode, once (with its time when a copy has
    it), at most MAX_DEADLINES, soonest first. Deadlines before the day the email arrived stay, as A.2."""
    unique = {}
    for sentence, deadline, position in deadlines:
        if sentence is not heading:
            deadline = replace(deadline, mode=modes.of(sentence, position, whole_email=False))
        key = (deadline.kind, deadline.day, deadline.mode)
        if key not in unique or (unique[key].at is None and deadline.at is not None):
            unique[key] = deadline
    return tuple(sorted(unique.values(), key=lambda d: (d.day, d.at or time(0)))[:MAX_DEADLINES])


# ---- the reader ------------------------------------------------------------------------------------------------------


def read_times(subject, text, arrived):
    """Found: what one email that arrived on `arrived` (a Vietnam date) holds."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    heading = _Sentence(unicodedata.normalize("NFC", subject or ""), arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    for sentence in sentences:
        _drop(sentence)
        _arrivals(sentence)
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
    return Found(deadlines=_kept_deadlines(deadlines, heading, modes))
