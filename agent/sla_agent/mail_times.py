"""The mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4): an email's sessions, Periods, deadlines and
flags, read on the laptop with rules. Step 0 cleans the text, step 1 (mail_phrases) finds each sentence's dates and
times, and step 2 decides what each of them is. Pure functions: the email's text never leaves this module.

The rule names in the comments (D1, P4, S3 …) are the spec's, §4.3."""

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta

from sla_agent import mail_phrases as phrases
from sla_agent import mail_words as words
from sla_agent.class_changes import SENTENCE_END, URL, fold

MAX_SESSIONS = 10
MAX_PERIODS = 5
MAX_DEADLINES = 5
MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own
# The edges of a day, not times an email sets: they never start a session, and a Period from one to the other is all
# day ("từ 00g00 ngày 21/9 đến 23g59 ngày 27/9" opens and closes a contest round).
DAY_EDGES = (time(0, 0), time(23, 59))

# Step 0 (§4.1): invisible characters go, and a no-break space is a space, so "13:00\u200b-\u200b16:30" stays a range.
INVISIBLE = str.maketrans({"\u200b": None, "\u200c": None, "\u200d": None, "\ufeff": None, "\u00ad": None,
                           "\u00a0": " "})
# A link is taken out of the text and this mark (a private-use character: no word, no number) stays in its place, so
# a line that held a link is never a heading: "Link đăng ký: <link>" is a whole line, not the title of the next one.
LINK_MARK = chr(0xE000)
# On folded text.
REPLY = re.compile(r"\s*(?:re|tl|tra loi)\s*:")
QUOTE_FROM = re.compile(r"\s*(?:from|tu)\s*:(?!\s*\d)")  # "Từ: 14h00" is a time, not a header
QUOTE_HEADER = re.compile(r"\s*(?:sent|date|to|da gui|gui|ngay|den)\s*:")
ORIGINAL = re.compile(r"\s*-{2,}\s*original message\s*-{2,}")
WROTE = re.compile(r"\s*(?:on|vao)\b.*\b(?:wrote|da viet)\s*:\s*$")
# A "Từ:" line with a "Đến:" line right after it is one range: "Từ: 14h00" then "Đến: 16h00".
FROM_LINE = re.compile(r"\s*(?:tu|from)\s*:")
TO_LINE = re.compile(r"\s*(?:den|to)\s*:")
# Step 2 (§4.3), on folded text.
DUE_TO = re.compile(r"\s+to\b")  # "due to the rain" is not a deadline
LINK_BEFORE = re.compile(r"\btruoc\s+(?:do\s+)?(\d{1,3})\s*phut\b")  # "gửi trước 30 phút": 30 minutes before
ESTIMATED_END = re.compile(r"\bdu kien\s*$")  # "dự kiến kết thúc lúc 20:30": an approximate end


# ---- what the reader finds -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FoundSession:
    day: date
    start: time
    end: time | None = None
    end_is_approximate: bool = False
    ends_next_day: bool = False
    check_in: time | None = None
    link_opens: time | None = None
    mode: str | None = None
    relative: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class FoundPeriod:
    first_day: date
    last_day: date
    mode: str  # "all_day", "daily_window" or "one_window"
    from_time: time | None = None
    to_time: time | None = None
    details_later: bool = False
    label: str | None = None


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
    """The text the times are read from: each link replaced by LINK_MARK; a reply without its quoted part (a forward
    keeps everything); no signature (from a line "--" on) and no lines giving office hours."""
    text = URL.sub(f" {LINK_MARK} ", unicodedata.normalize("NFC", text or "").translate(INVISIBLE))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
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
    number or link in it ("THỜI GIAN ĐĂNG KÝ", then "Từ ngày 20/09 đến 22/09/2026."), is read together with the line
    after it, and so is a "Từ:" line with a "Đến:" line after it."""
    found = [s for s in SENTENCE_END.split(text) if s.strip()]
    merged, i = [], 0
    while i < len(found):
        line = found[i]
        heading = (i + 1 < len(found) and not re.search(r"\d", line) and LINK_MARK not in line
                   and len(line.split()) <= MAX_HEADING_WORDS
                   and (words.REGISTRATION.spans(line) or words.CLOSING_STRONG.spans(line)))
        if heading:
            merged.append(line.strip().rstrip(":") + ": " + found[i + 1].strip())
            i += 2
        elif i + 1 < len(found) and FROM_LINE.match(fold(line)) and TO_LINE.match(fold(found[i + 1])):
            merged.append(line.strip() + " " + found[i + 1].strip())
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
        return a <= b and b - a <= phrases.FILLER_MOST and phrases.FILLER.fullmatch(fold(self.text[a:b])) is not None

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
        gap = sentence.text[span[1]:after[0].start]
        if right_after and (len(gap) > phrases.FILLER_MOST or not phrases.FILLER.fullmatch(fold(gap))):
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


def _label(sentence, position):
    part = sentence.parts[sentence.part(position)]
    return next((code for start, _, code in words.LABELS.spans(sentence.text) if part[0] <= start < part[1]), None)


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


def _links(sentence):
    """S5: [(clock, None)] for "Link … mở lúc 13:45", [(None, minutes)] for "Link … gửi trước 30 phút"."""
    found = []
    folded = fold(sentence.text)
    for span in sentence.spans(words.LINK):
        before = LINK_BEFORE.search(folded, span[1])
        if before:
            found.append((None, int(before.group(1))))
            continue
        part = sentence.part(span[0])
        clock = next((c for c in sentence.free(sentence.clocks)
                      if c.finish is None and sentence.part(c.start) == part and c.start >= span[1]), None)
        if clock is not None:
            sentence.use(clock)
            found.append((clock, None))
    return found


def _notices(sentence):
    """N: a notice takes the dates and times after it in its part ("Email này được gửi lúc 09:15 ngày 07/10")."""
    closing = sentence.spans(words.CLOSING_SOFT) + sentence.spans(words.CLOSING_STRONG)
    for span in sentence.spans(words.NOTICE):
        if any(start <= span[0] < end for start, end in closing):
            continue
        part = sentence.part(span[0])
        taken = [x for x in sentence.free(sentence.days + sentence.clocks + sentence.ranges + sentence.windows)
                 if sentence.part(x.start) == part and x.start >= span[1]]
        if taken:
            sentence.use(*taken)
            sentence.skip = True


# ---- step 2: Periods (§4.3, P) ---------------------------------------------------------------------------------------


def _says_later(sentence):
    """P2: the sentence says the student's own time comes later. Not on a line about the place: "Địa điểm: Thông tin
    chi tiết sẽ thông báo sau" is about where, not when."""
    return bool(sentence.spans(words.DETAILS_LATER)) and not sentence.spans(words.PLACE)


def _periods(sentences, i, details_later):
    """P1–P5 for sentence i: (its Periods, the sessions its ranges and windows give as [(FoundSession, position)])."""
    sentence = sentences[i]
    near = sentences[i:i + 2]
    any_time = any(s.spans(words.ANY_TIME) for s in near)
    later = any(_says_later(s) for s in near)
    open_hours = any(c.finish for c in sentence.free(sentence.clocks) for _, end in sentence.spans(words.DOORS)
                     if c.start >= end)
    period_words = any_time or later or open_hours
    periods, sessions = [], []

    def period(first, last, mode, position, begin=None, finish=None):
        if (begin, finish) == DAY_EDGES:  # whole days: all day, with no times (§2)
            mode, begin, finish = "all_day", None, None
        periods.append(FoundPeriod(first, last, mode, begin, finish, details_later, _label(sentence, position)))

    for window in sentence.free(sentence.windows):  # P4
        sentence.use(window)
        length = datetime.combine(window.last, window.finish) - datetime.combine(window.first, window.begin)
        if length > timedelta(hours=24) or period_words:
            period(window.first, window.last, "one_window", window.start, window.begin, window.finish)
        else:
            sessions.append((FoundSession(window.first, window.begin, window.finish,
                                          ends_next_day=window.last > window.first), window.start))
    hour_ranges = [c for c in sentence.free(sentence.clocks) if c.finish is not None]
    for day_range in sentence.free(sentence.ranges):
        sentence.use(day_range, *hour_ranges)
        if not hour_ranges:  # P1, P3
            period(day_range.first, day_range.last, "all_day", day_range.start)
            continue
        days = [day_range.first + timedelta(days=n) for n in range((day_range.last - day_range.first).days + 1)]
        if sentence.weekday is not None:
            days = [d for d in days if d.weekday() == sentence.weekday]
        each_day = sentence.spans(words.EACH_DAY) or sentence.weekday is not None
        for hours in hour_ranges:  # "8h00 - 11h30 & 13h00 - 16h00": one each
            if each_day and not period_words and len(days) * len(hour_ranges) <= MAX_SESSIONS:  # P5
                sessions += [(FoundSession(d, hours.begin, hours.finish), hours.start) for d in days]
            else:  # P1, P5
                period(day_range.first, day_range.last, "daily_window", day_range.start, hours.begin, hours.finish)
    if period_words or sentence.spans(words.WITHIN):  # P1, P2: one day's from–to
        for clock in sentence.free(sentence.clocks):
            day = clock.finish is not None and sentence.day_for(clock)
            if day:
                sentence.use(clock, *[d for d in sentence.days if d.day == day])
                period(day, day, "one_window", clock.start, clock.begin, clock.finish)
    return periods, sessions


# ---- step 2: sessions (§4.3, S) --------------------------------------------------------------------------------------


def _day_source(sentence):
    """The days a sentence gives the lines around it: its free dates, else the day a relative word gave it, else the
    first day of its range or window."""
    if sentence.skip:
        return []
    free = [d.day for d in sentence.free(sentence.days)]
    if free:
        return free
    if sentence.relative:
        return [sentence.relative[1]]
    return [x.first for x in sentence.windows + sentence.ranges][:1]


def _neighbour_days(sentences, i):
    """S1: the days of the nearest line above that has some, else of the nearest line below."""
    for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(sentences))):
        days = _day_source(sentences[j])
        if days:
            return days
    return []


def _session_days(sentences, i, arrived):
    """S1: ([day], relative code or None) for sentence i's times."""
    sentence = sentences[i]
    days = [d.day for d in sentence.free(sentence.days)] or _neighbour_days(sentences, i)
    if days:
        return days, None
    if any(s.days for s in sentences[:i + 1]):
        return [], None
    relative = phrases.relative_day(sentence.text, arrived)
    if relative is None:
        return [], None
    sentence.relative = relative
    return [relative[1]], relative[0]


def _sessions(sentences, i, arrived, given):
    """S1–S3 for sentence i: sessions from its free times, with those P4 and P5 gave."""
    sentence = sentences[i]
    clocks = sentence.free(sentence.clocks)
    approximate = set()
    # S2: "bắt đầu X … kết thúc Y" is one session; a sentence with only an end ends the nearest session above.
    for start, end in sentence.spans(words.END):
        after = [c for c in clocks if c.start >= end and c.finish is None]
        before = [c for c in clocks if c.end <= start and c.finish is None]
        if not after:
            continue
        estimated = bool(ESTIMATED_END.search(fold(sentence.text[:start])))
        if before:
            first, last = before[-1], after[0]
            joined = replace(first, finish=last.begin) if last.begin > first.begin else first
            clocks = [joined if c is first else c for c in clocks if c is not last]
            sentence.use(last)
            if estimated:
                approximate.add(id(joined))
        elif len(clocks) == 1 and not sentence.free(sentence.days):
            above = next((s for s in reversed(sentences[:i]) if s.sessions), None)
            if above:
                session, position = above.sessions[-1]
                above.sessions[-1] = (replace(session, end=after[0].begin, end_is_approximate=estimated), position)
            sentence.use(after[0])
            clocks = []
    found = list(given)
    clocks = [c for c in clocks if c.begin not in DAY_EDGES]
    days, relative = _session_days(sentences, i, arrived) if clocks else ([], None)
    pairs = zip(days, clocks) if len(days) == len(clocks) else [(d, c) for d in days for c in clocks]
    for day, clock in pairs:
        start, end = clock.begin, clock.finish
        if clock.offset is not None:  # S6
            moved = datetime.combine(day, start) - clock.offset + phrases.VIETNAM
            day, start = moved.date(), moved.time()
            end = end and (datetime.combine(day, end) - clock.offset + phrases.VIETNAM).time()
        found.append((FoundSession(day, start, end, id(clock) in approximate, ends_next_day=bool(end and end <= start),
                                   relative=relative), clock.start))
    sentence.sessions = found
    # S3: a length ends the sessions of its sentence, or else of the nearest sentence above with sessions.
    lengths = [n for n in sentence.lengths if not n.slot]
    if not lengths:
        return
    minutes = next((n.minutes for n in lengths if not n.adds), 0) + sum(n.minutes for n in lengths if n.adds)
    holder = sentence if found else next((s for s in reversed(sentences[:i]) if s.sessions), None)
    if holder is None or not minutes:
        return
    for k, (session, position) in enumerate(holder.sessions):
        end = datetime.combine(session.day, session.start) + timedelta(minutes=minutes)
        if session.end is None and end.date() == session.day:
            holder.sessions[k] = (replace(session, end=end.time(),
                                          end_is_approximate=any(n.approximate for n in lengths)), position)


def _join(sessions, day, at, field):
    """S4, S5: sets `field` to `at` on the earliest session of `day` that starts at or after `at` and has none yet.
    Whether one was found."""
    later = [k for k, (s, _, _) in enumerate(sessions) if s.day == day and s.start >= at and getattr(s, field) is None]
    if not later:
        return False
    k = min(later, key=lambda k: sessions[k][0].start)
    session, i, position = sessions[k]
    sessions[k] = (replace(session, **{field: at}), i, position)
    return True


def _check_ins(sentences, arrivals, sessions, arrived):
    """S4: each arrival time [(sentence index, clock)] joins the earliest session of its day that starts at or after
    it, as its check-in; with no such session it is a session of its own (A.1)."""
    for i, clock in arrivals:
        day = sentences[i].day_for(clock) or next(iter(_neighbour_days(sentences, i)), None)
        if day is None and not any(s.days for s in sentences[:i + 1]):
            relative = phrases.relative_day(sentences[i].text, arrived)
            day = relative and relative[1]
        if day is not None and not _join(sessions, day, clock.begin, "check_in"):
            sessions.append((FoundSession(day, clock.begin, clock.finish), i, clock.start))


def _link_times(sentences, links, sessions):
    """S5: each link time [(sentence index, clock, minutes)] joins a session like an arrival time; "trước 30 phút"
    (minutes) counts back from the start of the nearest session above."""
    for i, clock, minutes in links:
        if clock is not None:
            day = sentences[i].day_for(clock) or next(iter(_neighbour_days(sentences, i)), None)
            if day is not None:
                _join(sessions, day, clock.begin, "link_opens")
            continue
        above = [k for k, (_, j, _) in enumerate(sessions) if j <= i]
        if above:
            session, j, position = sessions[above[-1]]
            at = datetime.combine(session.day, session.start) - timedelta(minutes=minutes)
            if at.date() == session.day and session.link_opens is None:
                sessions[above[-1]] = (replace(session, link_opens=at.time()), j, position)


def _one_day_periods(sentences, sessions, details_later):
    """P6: each day with no hour, with an event word in its part and no session that day, as a one-day Period."""
    periods, busy = [], {s.day for s, _, _ in sessions}
    for sentence in sentences:
        events = [sentence.part(start) for start, _ in sentence.spans(words.EVENT)]
        for day in sentence.free(sentence.days):
            if day.day not in busy and sentence.part(day.start) in events:
                periods.append(FoundPeriod(day.day, day.day, "all_day", details_later=details_later,
                                           label=_label(sentence, day.start)))
                busy.add(day.day)
    return periods


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


def _kept_periods(periods, arrived):
    """The Periods that haven't ended by `arrived`, each once, at most MAX_PERIODS, soonest first."""
    return tuple(sorted({p for p in periods if p.last_day >= arrived},
                        key=lambda p: (p.first_day, p.last_day, p.from_time or time(0)))[:MAX_PERIODS])


def _kept_sessions(sentences, sessions, arrived, modes):
    """M, labels and S7: [(FoundSession, sentence index, position)] as kept: each with its mode and label, a check-in
    that isn't before the start left out; none before `arrived`; a repeated day and start once, with the end found;
    at most MAX_SESSIONS, soonest first."""
    kept = {}
    for session, i, position in sessions:
        if session.day < arrived:
            continue
        sentence = sentences[i]
        session = replace(session, mode=modes.of(sentence, position, whole_email=True),
                          label=session.label or _label(sentence, position),
                          check_in=session.check_in if session.check_in and session.check_in < session.start else None)
        key = (session.day, session.start)
        if key not in kept:
            kept[key] = session
        elif kept[key].end is None and session.end is not None:
            kept[key] = replace(kept[key], end=session.end, end_is_approximate=session.end_is_approximate)
    return tuple(sorted(kept.values(), key=lambda s: (s.day, s.start))[:MAX_SESSIONS])


# ---- flags (§2) ------------------------------------------------------------------------------------------------------


def _flag(text, role, unless=None):
    """Whether `text` (NFC) has a word of `role` that is not inside a word of `unless`."""
    spans = role.spans(text)
    if unless is not None:
        spans = [s for s in spans if not any(a <= s[0] and s[1] <= b for a, b in unless.spans(text))]
    return bool(spans)


# ---- the reader ------------------------------------------------------------------------------------------------------


def read_times(subject, text, arrived):
    """Found: the sessions, Periods, deadlines and flags of one email that arrived on `arrived` (a Vietnam date)."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    subject = unicodedata.normalize("NFC", subject or "")
    heading = _Sentence(subject, arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))
    details_later = any(_says_later(s) for s in sentences)

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    arrivals, links = [], []
    for i, sentence in enumerate(sentences):
        _drop(sentence)
        arrivals += [(i, clock) for clock in _arrivals(sentence)]
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
        links += [(i, clock, minutes) for clock, minutes in _links(sentence)]
        _notices(sentence)
    periods, given = [], []
    for i in range(len(sentences)):
        found, made = _periods(sentences, i, details_later)
        periods += found
        given.append(made)
    for i in range(len(sentences)):
        _sessions(sentences, i, arrived, given[i])
    sessions = [(s, i, p) for i, sentence in enumerate(sentences) for s, p in sentence.sessions]
    _check_ins(sentences, arrivals, sessions, arrived)
    _link_times(sentences, links, sessions)
    periods += _one_day_periods(sentences, sessions, details_later)
    texts = [subject] + [s.text for s in sentences]
    return Found(
        sessions=_kept_sessions(sentences, sessions, arrived, modes),
        periods=_kept_periods(periods, arrived),
        deadlines=_kept_deadlines(deadlines, heading, modes),
        meeting=any(_flag(t, words.MEETING, words.NOT_A_MEETING) for t in texts),
        registered=any(_flag(t, words.REGISTERED) for t in texts),
    )
