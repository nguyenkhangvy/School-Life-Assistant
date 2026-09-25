"""Timetable reader: EduSoft's whole-semester view ("TKB học kỳ cá nhân") -> dated classes.

Each course row can hold several schedule lines (e.g. a lecture on Tuesday and a
lab on Saturday). Each schedule column keeps one value per line: first the rows
of a small inner table, then a div. The weeks column also carries a code like
'-23456789-1234567': one character per week of the semester, a digit (the last
digit of the week number) when the class meets that week, '-' or ' ' when not.
"""

import re
from datetime import timedelta

from sla_contract.schema import ClassMeeting, Course, Timetable

from sla_agent.errors import ParseError
from sla_agent.parsers.common import parse_day, selected_option, soup, text, vietnam_time
from sla_agent.parsers.periods import class_hours

TERM_FIELD = "ctl00$ContentPlaceHolder1$ctl00$ddlChonNHHK"
WEEK_FIELD = "ctl00$ContentPlaceHolder1$ctl00$ddlTuan"
HEADERS = ("Mã MH", "Tên MH", "NMH", "STC", "Thứ", "Tiết BD", "ST", "Phòng", "Tuần")
WEEKDAYS = {"hai": 0, "ba": 1, "tư": 2, "năm": 3, "sáu": 4, "bảy": 5, "cn": 6, "chủ nhật": 6}
WEEK_OPTION = re.compile(r"Tuần\s*0*1\s*\[Từ\s*(\d{2}/\d{2}/\d{4})")
WEEK_ONE_NOTE = re.compile(r"tuần 1\)?\s*bắt đầu từ ngày\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
NOTE_ID = "ContentPlaceHolder1_ctl00_lblNote"
WEEKS_CODE = re.compile(r"ddrivetiptuan\('([^']*)'\)")
COURSE_AND_GROUP = re.compile(r"^\s*(\S+)\s+nhóm\s+(\S+)")

# Columns of a course row in the semester view.
CODE, NAME, GROUP, CREDITS = 0, 1, 2, 3
WEEKDAY, FIRST_PERIOD, PERIOD_COUNT, ROOM, WEEKS = 8, 9, 10, 11, 13


def _leaves(cell):
    """The per-line pieces of a schedule cell, in page order."""
    return [el for el in cell.find_all(["td", "div"]) if not el.find(["td", "div", "table"])]


def _week_one_monday(*pages):
    """From the note "(tuần 1) bắt đầu từ ngày 31/08/2026", or the weekly view's week list."""
    for page in pages:
        if page is None:
            continue
        match = WEEK_ONE_NOTE.search(text(page.find(id=NOTE_ID)))
        if match:
            return parse_day(match.group(1))
        select = page.find("select", attrs={"name": WEEK_FIELD})
        for option in select.find_all("option") if select else []:
            match = WEEK_OPTION.search(option.get("value", "") + " " + text(option))
            if match:
                return parse_day(match.group(1))
    raise ParseError("Couldn't find when week 1 of the semester starts.")


def _weeks(code):
    weeks = []
    for number, char in enumerate(code, start=1):
        if char.isdigit():
            if char != str(number % 10):
                raise ParseError(f"Week code {code!r} doesn't line up with week numbers.")
            weeks.append(number)
        elif char not in "- ":
            raise ParseError(f"Unexpected character in week code {code!r}.")
    return weeks


def _weekday(value):
    key = value.strip().lower().removeprefix("thứ").strip()
    if key not in WEEKDAYS:
        raise ParseError(f"Unknown weekday {value!r}.")
    return WEEKDAYS[key]


def _number(value, what):
    try:
        return int(value)
    except ValueError:
        raise ParseError(f"Couldn't read the {what} {value!r}.") from None


def _lecturers(weekly):
    """(course code, group) -> lecturer name, from the weekly view's class boxes."""
    names = {}
    if weekly is None:
        return names
    for box in weekly.find_all(attrs={"onmouseover": re.compile(r"^ddrivetip\(")}):
        details = re.findall(r"'([^']*)'", box["onmouseover"])
        if len(details) >= 9:
            match = COURSE_AND_GROUP.match(details[2])
            if match and details[8].strip():
                names[match.groups()] = details[8].strip()
    return names


def _meetings(cells, week_one):
    days, firsts, counts, rooms = (_leaves(cells[i]) for i in (WEEKDAY, FIRST_PERIOD, PERIOD_COUNT, ROOM))
    weeks = _leaves(cells[WEEKS])
    if not len(days) == len(firsts) == len(counts) == len(rooms) == len(weeks):
        raise ParseError("A course's schedule columns don't have the same number of lines.")

    meetings = []
    for day, first, count, room, week_cell in zip(days, firsts, counts, rooms, weeks):
        if not text(day) and not text(first):
            continue  # a course with no scheduled classes
        code = WEEKS_CODE.search(week_cell.get("onmouseover", ""))
        if not code:
            raise ParseError("A schedule line has no week code.")
        offset = _weekday(text(day))
        start, end = class_hours(_number(text(first), "first period"), _number(text(count), "number of periods"))
        for week in _weeks(code.group(1)):
            date = week_one + timedelta(weeks=week - 1, days=offset)
            meetings.append(ClassMeeting(
                start_at=vietnam_time(date, start), end_at=vietnam_time(date, end), room=text(room) or None,
            ))
    return sorted(meetings, key=lambda m: m.start_at)


def parse_timetable(pages):
    """pages: {"semester": html of the whole-semester view, "weekly": html of the weekly view (optional)}."""
    page = soup(pages["semester"])

    term_select = page.find("select", attrs={"name": TERM_FIELD})
    term = selected_option(term_select) if term_select else None
    if term is None or not term.get("value"):
        raise ParseError("Couldn't find which semester the timetable is for.")

    grid = page.find("div", class_="grid-roll2")
    if grid is None:
        raise ParseError("The semester timetable table wasn't found.")
    if not any(all(h in list(t.stripped_strings) for h in HEADERS) for t in page.find_all("table")):
        raise ParseError("The semester timetable's column headers have changed.")

    weekly = soup(pages["weekly"]) if pages.get("weekly") else None
    week_one = _week_one_monday(page, weekly)
    lecturers = _lecturers(weekly)

    courses = []
    for row in grid.find_all("table", class_="body-table", recursive=False):
        first_row = row.find("tr")
        cells = first_row.find_all("td", recursive=False) if first_row else []
        if len(cells) <= WEEKS:
            raise ParseError(f"A course row has {len(cells)} columns instead of at least {WEEKS + 1}.")
        code, group = text(cells[CODE]), text(cells[GROUP])
        credits = text(cells[CREDITS])
        courses.append(Course(
            course_code=code,
            course_name=text(cells[NAME]),
            group=group or None,
            credits=float(credits) if credits else None,
            lecturer=lecturers.get((code, group)),
            meetings=_meetings(cells, week_one),
        ))
    return Timetable(term_code=term["value"], term_name=text(term) or None, courses=courses)
