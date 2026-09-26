"""Class changes announced on Blackboard: online, cancelled and make-up classes. Pure functions.

A sentence that mentions a class, a change word and a date makes a change; each date takes the
nearest cancel or make-up word, or an online word when the sentence has neither. The rules are in
docs/superpowers/specs/2026-09-26-class-changes-and-to-submit-design.md, section 2."""

import logging
import re
import unicodedata
from datetime import date, time, timedelta
from typing import NamedTuple

log = logging.getLogger(__name__)

VIETNAM_OFFSET = timedelta(hours=7)

CHANGE_WORDS = re.compile(
    r"(?P<makeup>\bmake[\s-]?up\b|\bbù\b)"
    r"|(?P<cancelled>\bcancel(?:s|ed|led|ing|ling|lations?)?\b|\bno class(?:es)?\b|\bnghỉ\b|\bhủy\b|\bhuỷ\b)"
    r"|(?P<online>\bonline\b|\btrực tuyến\b)",
    re.IGNORECASE,
)
CLASS_WORDS = re.compile(r"\b(?:class(?:es)?|lectures?|sessions?|lessons?|lớp|buổi|học|tiết)\b", re.IGNORECASE)

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}
MONTH = "|".join(sorted(MONTH_NAMES, key=len, reverse=True))
ORDINAL = r"(?:st|nd|rd|th)?"
YEAR = r"(?:,?\s+(?P<year>\d{4}))?"
DATE_FORMATS = [
    re.compile(rf"\b(?P<month>{MONTH})\b\.?\s+(?P<day>\d{{1,2}}){ORDINAL}(?!\d){YEAR}", re.IGNORECASE),
    re.compile(rf"(?<!\d)(?P<day>\d{{1,2}}){ORDINAL}\s+(?:of\s+)?(?P<month>{MONTH})\b\.?{YEAR}", re.IGNORECASE),
    re.compile(r"(?<![\w/.:])(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{4}))?(?![\d/])"),
    re.compile(r"ngày\s+(?P<day>\d{1,2})\s+tháng\s+(?P<month>\d{1,2})(?:\s+năm\s+(?P<year>\d{4}))?", re.IGNORECASE),
]
TIME = re.compile(
    r"(?<![\w/.:])(?P<hour>\d{1,2})(?:[:hg](?P<minute>\d{2})?|(?=\s*[ap]\.?m\b))(?:\s*(?P<ampm>[ap])\.?m\.?)?(?!\w)",
    re.IGNORECASE,
)
RANGE_JOIN = re.compile(r"\s*(?:-|–|to|đến)\s*", re.IGNORECASE)
ROOM = re.compile(r"(?<![\w.])(?:[A-Z]{1,2}\d\.\d{3}|R\d{3})(?!\w|\.\w)")
URL = re.compile(r"https?://\S+")
ABBREVIATIONS = ("jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
                 "dr", "mr", "ms", "mrs")
SENTENCE_END = re.compile(
    r"(?<=[.!?])" + "".join(rf"(?<!\b{a}\.)" for a in ABBREVIATIONS) + r"(?<![ap]\.m\.)\s+|\n+",
    re.IGNORECASE,
)


class Announced(NamedTuple):
    kind: str  # "online" / "cancelled" / "makeup"
    day: date  # in Vietnam
    start: time | None = None  # make-up only
    end: time | None = None
    room: str | None = None


class ClassChange(NamedTuple):
    code: str  # course code, e.g. "MA026IU"
    bb_course_id: int  # the app's page for the Blackboard course that posted it
    kind: str
    day: date
    start: time | None
    end: time | None
    room: str | None


def _date(match, posted_day):
    month = match.group("month")
    month = MONTH_NAMES[month.lower()] if month.isalpha() else int(month)
    day, year = int(match.group("day")), match.group("year")
    try:
        if year:
            return date(int(year), month, day)
        candidates = [date(posted_day.year + k, month, day) for k in (-1, 0, 1)]
    except ValueError:
        return None
    return min(candidates, key=lambda d: abs(d - posted_day))


def _dates(sentence, posted_day):
    """[(position, date)] in `sentence`, from the posting day on."""
    found, taken = [], []
    for pattern in DATE_FORMATS:
        for match in pattern.finditer(sentence):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            taken.append(match.span())
            day = _date(match, posted_day)
            if day is not None and day >= posted_day:
                found.append((match.start(), day))
    return found


def _time(match):
    hour, minute = int(match.group("hour")), int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").lower()
    if ampm == "p" and hour < 12:
        hour += 12
    if ampm == "a" and hour == 12:
        hour = 0
    return time(hour, minute) if hour < 24 and minute < 60 else None


def _times(sentence):
    """(start, end) of the first time in `sentence`; end only for a range like 8:00-9:40."""
    matches = list(TIME.finditer(sentence))
    if not matches:
        return None, None
    end = None
    if len(matches) > 1 and RANGE_JOIN.fullmatch(sentence[matches[0].end():matches[1].start()]):
        end = _time(matches[1])
    return _time(matches[0]), end


def read_announcement(title, text, posted_at):
    """The class changes one announcement makes. posted_at: naive UTC."""
    posted_day = (posted_at + VIETNAM_OFFSET).date()
    found = []
    for sentence in [title or ""] + SENTENCE_END.split(text or ""):
        sentence = URL.sub(" ", unicodedata.normalize("NFC", sentence))
        words = [(m.start(), m.lastgroup) for m in CHANGE_WORDS.finditer(sentence)]
        if not words or not CLASS_WORDS.search(sentence):
            continue
        # Online words decide only when there is no cancel or make-up word: "make-up class online on 3/10"
        # is an online make-up class.
        deciding = [word for word in words if word[1] != "online"] or words
        for position, day in _dates(sentence, posted_day):
            kind = min(deciding, key=lambda word: abs(word[0] - position))[1]
            if kind != "makeup":
                found.append(Announced(kind, day))
                continue
            start, end = _times(sentence)
            room = ROOM.search(sentence)
            online = any(k == "online" for _, k in words)
            found.append(Announced("makeup", day, start, end, "Online" if online else room and room.group(0)))
    return found


def changes_from(announcements):
    """{(course code, Vietnam date): ClassChange}; the newest announcement wins.

    announcements: (course code, app course id, title, text, posted_at) tuples."""
    changes = {}
    dated = [a for a in announcements if a[0] and a[4] is not None]
    for code, bb_course_id, title, text, posted_at in sorted(dated, key=lambda a: a[4]):
        try:
            announced = read_announcement(title, text, posted_at)
        except Exception:  # one unreadable announcement must never break a page
            log.exception("Couldn't read an announcement for class changes")
            continue
        for a in announced:
            changes[(code, a.day)] = ClassChange(code, bb_course_id, *a)
    return changes
