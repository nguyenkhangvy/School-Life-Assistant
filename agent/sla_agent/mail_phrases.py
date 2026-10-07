"""Step 1 of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4.2): the dates, times, ranges,
windows and lengths one sentence holds, and where they are. Pure functions."""

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

from sla_agent import mail_words as words
from sla_agent.class_changes import MAIL_DATE_FORMATS, MONTH_NAMES, fold

# A date with a two-digit year: "05/10/26".
SHORT_YEAR = re.compile(r"(?<![\w/.:])(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<short>\d{2})(?![\d/])")
DATE_FORMATS = [SHORT_YEAR] + MAIL_DATE_FORMATS
# A time: 13:00, 13.00, 13h, 13h30, 13g, 8g30, 14 giờ, 14 giờ 30 (phút), 1 PM, 1:30 pm, 2:00 CH, 8:00 SA. "01.10"
# followed by ".2026" is a date, and "15.000.000" money.
TIME = re.compile(
    r"(?<![\w/.:,])(?P<hour>\d{1,2})"
    r"(?:\s*gi[ờo](?:\s*(?P<gminute>\d{1,2})(?:\s*ph[úu]t)?)?(?!\w)"
    r"|(?:[:.](?=\d{2})|[hg])(?P<minute>\d{2})?"
    r"|(?=\s*(?:[ap]\.?m\b|(?-i:SA|CH)\b)))"
    r"(?:\s*(?P<ampm>[ap])\.?m\.?|\s*(?P<vn>(?-i:SA|CH))\b)?"
    r"(?!\w|\.\d)",
    re.IGNORECASE,
)
# A time zone written right after a time: "9:00 AM EST", "10:00 (GMT+8)".
ZONE = re.compile(r"\s*\(?\s*(?:(?P<named>ICT|EST|EDT|PST|PDT|CET|CEST|JST|KST|SGT)\b|(?:GMT|UTC)\s*(?P<sign>[+\-−])?"
                  r"\s*(?P<hours>\d{1,2})?(?::?(?P<minutes>\d{2}))?)\s*\)?")
ZONE_HOURS = {"ICT": 7, "EST": -5, "EDT": -4, "PST": -8, "PDT": -7, "CET": 1, "CEST": 2, "JST": 9, "KST": 9, "SGT": 8}
VIETNAM = timedelta(hours=7)
# On folded text: what joins the two ends of a range.
JOIN = re.compile(r"\s*,?\s*(?:den|toi|-|–|—|to|until|till)\s+(?:het\s+)?(?:ngay\s+)?$|\s*[-–—]\s*$")
# On folded text, right after a time: the time of day ("2h chiều" is 14:00).
TIME_OF_DAY_AFTER = re.compile(r"\s*(sang|chieu|toi|trua)\b")
TIME_OF_DAY = re.compile(r"\b(sang|chieu|toi|trua)\b")
EARLIEST_BARE_HOUR = 6  # a bare hour under this, without minutes or AM/PM, is a length: "(2h)"
# A length: a lead word, then hours and/or minutes, on folded text. After a weak lead ("khoảng", "about") only units
# that can't be a time of day count: "khoảng 1 tiếng" is a length, "khoảng 2 giờ chiều" a time. "Trong" leads only
# hours: "trong 15 phút đầu" is not an event's length.
LENGTH = re.compile(
    r"(?:(?P<lead>\b(?:keo dai|thoi luong(?: du kien)?|trong vong|trong|du kien|thoi gian lam bai|thoi gian trinh bay|"
    r"chi co|sau do co|sau do|duration|lasting|lasts|for)\b)|(?P<weak>\b(?:khoang|about|around|approximately)\b))"
    r"(?:\s*(?:la|:))?(?:\s*(?:khoang|about|around|approximately))?\s*"
    r"(?:(?P<hours>\d{1,2})(?:[.,](?P<half>5))?\s*(?P<unit>gio\b|tieng\b|hours?\b|h(?=\d|\b))"
    r"(?:\s*(?P<more>\d{1,2})\s*(?:phut\b|p\b|minutes?\b)?)?"
    r"|(?P<minutes>\d{1,3})\s*(?:phut|minutes?)\b)")
APPROXIMATE = re.compile(r"\b(?:khoang|du kien|about|around|approximately)\b")
SLOT = re.compile(r"\bmoi\s+luot\b")


@dataclass(frozen=True)
class Day:
    start: int
    end: int
    day: date


@dataclass(frozen=True)
class Clock:
    """A time, or a time range when `finish` is given. `offset`: the written time zone's offset from UTC."""
    start: int
    end: int
    begin: time
    finish: time | None = None
    offset: timedelta | None = None


@dataclass(frozen=True)
class Length:
    start: int
    end: int
    minutes: int
    approximate: bool
    slot: bool  # "mỗi lượt … 30 phút": each booking slot's length, not the event's
    adds: bool  # "sau đó có 10 phút": adds to the length before it


def _year_guess(day, month, arrived):
    """The date with the year closest to the arrival day, or None when there is no such date."""
    try:
        candidates = [date(arrived.year + k, month, day) for k in (-1, 0, 1)]
    except ValueError:
        return None
    return min(candidates, key=lambda d: abs(d - arrived))


def days_in(sentence, arrived):
    """[Day] in `sentence`, in order. A date without a year takes the year closest to `arrived`."""
    found, taken = [], []
    for pattern in DATE_FORMATS:
        for match in pattern.finditer(sentence):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            taken.append(match.span())
            month = match.group("month")
            month = MONTH_NAMES[month.lower()] if month.isalpha() else int(month)
            day = int(match.group("day"))
            groups = match.groupdict()
            try:
                if groups.get("short"):
                    value = date(2000 + int(groups["short"]), month, day)
                elif groups.get("year"):
                    value = date(int(groups["year"]), month, day)
                else:
                    value = _year_guess(day, month, arrived)
            except ValueError:
                value = None
            if value is not None:
                found.append(Day(match.start(), match.end(), value))
    return sorted(found, key=lambda d: d.start)


def lengths_in(sentence):
    """[Length] in `sentence`, in order."""
    folded = words.fold_in_place(sentence)
    found = []
    for match in LENGTH.finditer(folded):
        if match.group("weak") and match.group("unit") in ("gio", "h"):
            continue
        if match.group("lead") == "trong" and match.group("minutes"):
            continue
        if match.group("minutes"):
            minutes = int(match.group("minutes"))
        else:
            minutes = int(match.group("hours")) * 60 + (30 if match.group("half") else 0) + int(match.group("more") or 0)
        before = folded[max(0, match.start() - 40):match.start()]
        found.append(Length(match.start(), match.end(), minutes,
                            approximate=bool(APPROXIMATE.search(match.group(0))),
                            slot=bool(SLOT.search(before)),
                            adds=(match.group("lead") or "").startswith("sau do")))
    return found


def _ampm(sentence, match, folded):
    """"a" / "p" for this time: its own AM/PM or SA/CH; else a time-of-day word right after it ("2h chiều"), else the
    nearest one before it in its part, else the only kind the sentence has; else None. "Trưa" is noon: only
    1h–3h trưa are afternoon."""
    if match.group("ampm"):
        return match.group("ampm").lower()
    if match.group("vn"):
        return "a" if match.group("vn") == "SA" else "p"
    hour = int(match.group("hour"))
    word = TIME_OF_DAY_AFTER.match(folded, match.end())
    if not word:
        part_start = max(folded.rfind(",", 0, match.start()), folded.rfind(";", 0, match.start())) + 1
        before = list(TIME_OF_DAY.finditer(folded, part_start, match.start()))
        word = before[-1] if before else None
    if not word:
        kinds = {w.group(1) for w in TIME_OF_DAY.finditer(folded)}
        word = TIME_OF_DAY.search(folded) if len(kinds) == 1 else None
    if not word:
        return None
    if word.group(1) == "trua":
        return "p" if hour <= 3 else None
    return "a" if word.group(1) == "sang" else "p"


def _clock_value(match, ampm):
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or match.group("gminute") or 0)
    if ampm == "p" and hour < 12:
        hour += 12
    if ampm == "a" and hour == 12:
        hour = 0
    return time(hour, minute) if hour < 24 and minute < 60 else None


def _zone(sentence, end):
    """(offset, end) of a time zone written at `end`, else (None, end)."""
    match = ZONE.match(sentence, end)
    if not match:
        return None, end
    if match.group("named"):
        return timedelta(hours=ZONE_HOURS[match.group("named")]), match.end()
    sign = -1 if match.group("sign") in ("-", "−") else 1
    return sign * timedelta(hours=int(match.group("hours") or 0), minutes=int(match.group("minutes") or 0)), match.end()


def clocks_in(sentence, taken):
    """[Clock] in `sentence` outside the spans in `taken` (its dates and lengths), in order. Two times joined by
    "-", "đến", "to" … make one range; a range's end that isn't after its start is dropped. A bare small hour
    ("(2h)") is a length, not a time; a dotted number after a score word ("điểm trung bình từ 7.50") is a score."""
    folded = words.fold_in_place(sentence)
    scores = words.SCORE.spans(sentence)
    singles = []
    for match in TIME.finditer(sentence):
        if any(match.start() < end and start < match.end() for start, end in taken):
            continue
        if "." in match.group(0) and any(end <= match.start() for _, end in scores):
            continue
        ampm = _ampm(sentence, match, folded)
        if (match.group("minute") is None and match.group("gminute") is None and ampm is None
                and "gi" not in match.group(0).lower() and int(match.group("hour")) < EARLIEST_BARE_HOUR):
            continue
        value = _clock_value(match, ampm)
        if value is None:
            continue
        offset, end = _zone(sentence, match.end())
        singles.append((match, ampm, value, offset, end))
    found, i = [], 0
    while i < len(singles):
        first, first_ampm, begin, offset, end = singles[i]
        finish = None
        i += 1
        if i < len(singles) and JOIN.match(fold(sentence[end:singles[i][0].start()]) + " "):
            second, second_ampm, finish, offset2, end = singles[i]
            offset = offset or offset2
            i += 1
            if not first_ampm and second_ampm:
                shifted = _clock_value(first, second_ampm)
                if shifted and shifted < finish:
                    begin = shifted
            if finish <= begin:
                finish = None
        found.append(Clock(first.start(), end, begin, finish, offset))
    return found


def parts_of(sentence):
    """(start, end) of the sentence's parts: it is cut at commas and semicolons."""
    cuts = [i for i, c in enumerate(sentence) if c in ",;"]
    starts, ends = [0] + [c + 1 for c in cuts], cuts + [len(sentence)]
    return list(zip(starts, ends))
