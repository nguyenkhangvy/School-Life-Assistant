# Class Changes and To Submit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show online, cancelled and make-up classes announced on Blackboard in the timetable and on the Overview, and replace "Due soon" with a "To submit" box whose rows link straight to each assignment.

**Architecture:** A pure reader (`app/school/services/class_changes.py`) turns stored Blackboard announcements into dated class changes. `schedule.items_between` applies them to the EduSoft class meetings, so the calendar feed and the Overview show the same thing. The laptop agent builds each assignment's direct Blackboard link from the gradebook column's `contentId`; the Overview lists unsubmitted assignments with that link.

**Tech Stack:** Flask, Jinja, Flask-SQLAlchemy (SQLite in tests, MySQL locally), FullCalendar 6 (already loaded), pytest, BeautifulSoup (tests), the `sla-agent` package.

**Spec:** docs/superpowers/specs/2026-09-26-class-changes-and-to-submit-design.md

Work on a new branch `class-changes` created from `phase1-edusoft`.

## Global Constraints

- The site is always light: never add `prefers-color-scheme: dark` rules (the student's standing preference, 2026-09-26).
- The database stores naive UTC; pages show Vietnam time (UTC+7); the calendar feed sends Vietnam wall-clock times without an offset.
- Every query is filtered by the logged-in user.
- Links to Blackboard open in a new tab with `rel="noopener noreferrer"` and must start with `https://blackboard.hcmiu.edu.vn/`.
- Text from Blackboard is shown with Jinja autoescaping (no `|safe`) and inserted by JavaScript with `textContent`.
- Colours: purple `#6f42c1` with white text for online and make-up classes; cancelled classes grey and crossed out. Legend texts: "Online / make-up", "Cancelled".
- Nothing new is sent anywhere, and no new dependency is added.
- Run Python with `.venv/Scripts/python.exe`; read and write files as UTF-8.

## Review Focus

1. **Dates inside links** (Teams and Meet links are full of digits and dashes) must not create class changes. Test: Task 3 (`test_what_changes_nothing`, the link case).
2. **Vietnamese typed with combining accents** (NFD, e.g. copied from Word) must still match "trực tuyến". Test: Task 3 (`test_date_formats_and_vietnamese`, the NFD case).
3. **An announcement without a posting time, or one the reader can't handle,** must never break the calendar or the Overview. Tests: Task 3 (`test_announcements_without_a_course_code_or_time_are_skipped`, `test_an_unreadable_announcement_is_skipped`).
4. **A make-up whose end time is before its start** (a typo) must not create a negative-length class; it gets the usual length. Test: Task 4 (`test_a_make_up_class_ending_before_it_starts_uses_the_usual_length`).
5. **An announcement from a course that isn't in the EduSoft timetable** must not add a class or fail. Test: Task 4 (`test_a_make_up_for_a_course_not_in_the_timetable_is_ignored`).

---

## File Structure

- `agent/sla_agent/parsers/blackboard.py`: `content_url`, and `assignments_from` uses it (Task 1).
- `app/school/routes.py`: "To submit" query, ✓ on done deadlines (Task 2); calendar events for changed classes (Task 4).
- `app/templates/school/index.html`: the "To submit" box (Task 2).
- `app/school/services/class_changes.py` (new): reading announcements, pure (Task 3).
- `app/school/services/schedule.py`: `Item` gains `change`, `bb_course_id`, `all_day`; `items_between` applies changes (Task 4).
- `app/templates/school/_item.html`, `app/templates/school/timetable.html`, `app/static/js/timetable.js`, `app/static/css/style.css`: display (Tasks 2 and 4).
- Tests: `agent/tests/test_blackboard_readers.py`, `agent/tests/test_blackboard_samples.py` (Task 1), `tests/test_school_blackboard_pages.py` (Task 2), `tests/test_school_class_changes.py` (new, Task 3), `tests/test_school_class_change_pages.py` (new, Task 4).

---

### Task 1: Direct assignment links (laptop agent)

**Files:**
- Modify: `agent/sla_agent/parsers/blackboard.py`
- Test: `agent/tests/test_blackboard_readers.py`, `agent/tests/test_blackboard_samples.py`

**Interfaces:**
- Consumes: `course_url(course_id)`, `BASE_URL`, `assignments_from(columns, grades, course_id)` (existing).
- Produces: `content_url(course_id: str, content_id: str) -> str`; `BbAssignment.url` is the item's own page when the column has a valid `contentId`.

- [ ] **Step 1: Write the failing tests**

Append to `agent/tests/test_blackboard_readers.py` (it already defines `BB`, `COLUMNS`, `GRADES` and imports `assignments_from`):

```python
def test_an_assignment_links_to_its_own_page_when_blackboard_names_it():
    columns = [{**COLUMNS[0], "contentId": "_452089_1"}, COLUMNS[1], {**COLUMNS[4], "contentId": "javascript:alert(1)"}]

    urls = {a.bb_id: a.url for a in assignments_from(columns, GRADES, "_101_1")}

    assert urls == {
        "_701_1": f"{BB}/webapps/blackboard/execute/displayIndividualContent?course_id=_101_1&content_id=_452089_1",
        "_702_1": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
        "_705_1": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
    }
```

Append to `agent/tests/test_blackboard_samples.py` (it already imports `BASE_URL`, `read_blackboard`, and defines `Replay`, `REGISTERED`):

```python
def test_real_assignments_link_to_their_own_page():
    urls = {a.name: a.url for c in read_blackboard(Replay(), REGISTERED).courses for a in c.assignments}

    assert urls["Finding the problems and potential solutions"] == (
        f"{BASE_URL}/webapps/blackboard/execute/displayIndividualContent?course_id=_35337_1&content_id=_452089_1")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_blackboard_readers.py agent/tests/test_blackboard_samples.py -q`
Expected: 2 failures; the `_701_1` / real URL is the course launcher link, not `displayIndividualContent`.

- [ ] **Step 3: Implement**

In `agent/sla_agent/parsers/blackboard.py`, right after `course_url`, add:

```python
BB_ID = re.compile(r"_\d+_\d+")


def content_url(course_id, content_id):
    """Blackboard's own page for one item of a course, e.g. an assignment."""
    return (f"{BASE_URL}/webapps/blackboard/execute/displayIndividualContent"
            f"?course_id={quote(course_id)}&content_id={quote(content_id)}")


def _assignment_url(column, course_id):
    content_id = column.get("contentId")
    if isinstance(content_id, str) and BB_ID.fullmatch(content_id):
        return content_url(course_id, content_id)
    return course_url(course_id)
```

In `assignments_from`, replace `url=course_url(course_id),` with `url=_assignment_url(column, course_id),`.

- [ ] **Step 4: Run the agent tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/parsers/blackboard.py agent/tests/test_blackboard_readers.py agent/tests/test_blackboard_samples.py
git commit -m "feat(agent): assignments link to their own Blackboard page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: "To submit" on the Overview, ✓ on done deadlines

**Files:**
- Modify: `app/school/routes.py`, `app/templates/school/index.html`, `app/static/css/style.css`
- Test: `tests/test_school_blackboard_pages.py`

**Interfaces:**
- Consumes: `SchoolBbAssignment` (`status` is `not_graded` / `needs_grading` / `graded` / `exempt`; `url`; `course`).
- Produces: `index()` passes `to_submit` (list of `SchoolBbAssignment`) and `now` to `school/index.html`; `due_soon` is gone. Calendar deadline titles start with `"✓ "` when done.

- [ ] **Step 1: Write the failing tests**

In `tests/test_school_blackboard_pages.py`, replace the whole `test_overview_shows_due_soon_and_latest_announcements` function with:

```python
def test_overview_shows_the_3_latest_announcements(app, browser):
    add_course(app, 1, announcements=[{"bb_id": f"a{i}", "title": f"Note {i}", "text": "t",
                                       "posted_at": datetime(2026, 9, 20 + i, 2, 0)} for i in range(5)])

    html = page(browser, "/school/")

    assert "Note 4" in html and "Note 2" in html and "Note 1" not in html


def test_to_submit_lists_what_i_havent_submitted_with_a_link(app, browser, monkeypatch):
    add_course(app, 1, assignments=[
        {"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "not_graded"},
        {"bb_id": "x2", "name": "Final report", "due_at": datetime(2026, 11, 30, 16, 59), "status": "not_graded"},
        {"bb_id": "x3", "name": "Missed quiz", "due_at": datetime(2026, 9, 25, 16, 59), "status": "not_graded"},
        {"bb_id": "x4", "name": "Long gone", "due_at": datetime(2026, 9, 1, 16, 59), "status": "not_graded"},
        {"bb_id": "x5", "name": "Handed in", "due_at": datetime(2026, 10, 3, 16, 59), "status": "needs_grading"},
        {"bb_id": "x6", "name": "Marked", "due_at": datetime(2026, 10, 4, 16, 59), "status": "graded", "score": 9.0},
        {"bb_id": "x7", "name": "Excused", "due_at": datetime(2026, 10, 5, 16, 59), "status": "exempt"},
        {"bb_id": "x8", "name": "Attendance", "due_at": None, "status": "not_graded"},
    ])
    add_course(app, make_user(app, email="binh@example.com"), name="Binh's Course", assignments=[
        {"bb_id": "y1", "name": "Binh's lab", "due_at": datetime(2026, 10, 2, 16, 59), "status": "not_graded"}])
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 29, 0, 30))

    soup = BeautifulSoup(page(browser, "/school/"), "html.parser")
    rows = soup.find("h2", string="To submit").find_next("ul").find_all("li")

    assert [r.find(class_="item-title").get_text(strip=True) for r in rows] == ["Missed quiz", "Lab 3", "Final report"]
    assert "Overdue" in rows[0].get_text() and "Overdue" not in rows[1].get_text()
    links = [r.find("a", string=lambda s: s and "Open assignment" in s) for r in rows]
    assert all(l["href"] == BB and l["target"] == "_blank" and "noopener" in l["rel"] for l in links)


def test_to_submit_says_when_nothing_is_left(browser):
    assert "Nothing left to submit." in page(browser, "/school/")


def test_done_deadlines_get_a_check_mark_in_the_calendar(app, browser):
    add_course(app, 1, assignments=[
        {"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "needs_grading"},
        {"bb_id": "x2", "name": "Lab 4", "due_at": datetime(2026, 10, 3, 16, 59), "status": "not_graded"}])

    events = browser.get("/school/api/calendar", query_string={"start": "2026-09-28", "end": "2026-10-05"}).get_json()

    assert sorted(e["title"] for e in events if e["extendedProps"]["kind"] == "due") == [
        "Due 23:59: Lab 4 · Web Application Development", "✓ Due 23:59: Lab 3 · Web Application Development"]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_blackboard_pages.py -q`
Expected: the three new "To submit" / ✓ tests fail ("To submit" heading not found; no ✓); the announcements test passes.

- [ ] **Step 3: Implement the route changes**

In `app/school/routes.py`, below `bp = Blueprint(...)`, add:

```python
OVERDUE_DAYS = 7  # a missed assignment stays in "To submit" this long
DONE = ("needs_grading", "graded", "exempt")
```

In `index()`, replace the whole `due_soon = db.session.execute(...)` statement with:

```python
    to_submit = db.session.execute(
        select(SchoolBbAssignment).filter_by(user_id=current_user.id, status="not_graded")
        .where(SchoolBbAssignment.due_at >= now - timedelta(days=OVERDUE_DAYS))
        .order_by(SchoolBbAssignment.due_at)
    ).scalars().all()
```

and in its `render_template(...)` call replace `due_soon=due_soon,` with:

```python
        to_submit=to_submit,
        now=now,
```

In `calendar_feed()`, replace the deadline title line with:

```python
            "title": f"{'✓ ' if deadline.status in DONE else ''}Due {vn_clock(deadline.due_at)}: "
                     f"{deadline.name} · {deadline.course.name}",
```

- [ ] **Step 4: Implement the template and CSS**

In `app/templates/school/index.html`, replace everything from `<h2>Due soon</h2>` through the `{% endif %}` that closes that box (the one right after "Nothing due in the next 7 days.") with:

```html
      <h2>To submit</h2>
      {% if to_submit %}
        <ul class="items">
          {% for a in to_submit %}
            <li class="item item-due{% if a.due_at < now %} is-overdue{% endif %}">
              <span class="item-time">{{ a.due_at | vn_time }}{% if a.due_at < now %} <span class="badge badge-overdue">Overdue</span>{% endif %}</span>
              <span class="item-title">{{ a.name }}</span>
              <span class="item-meta">{{ a.course.name }} · <a href="{{ a.url }}" target="_blank" rel="noopener noreferrer">Open assignment ↗</a></span>
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="muted">Nothing left to submit.</p>
      {% endif %}
```

Append to `app/static/css/style.css`:

```css
/* School: To submit */
.item.is-overdue { border-left-color: var(--error); }
.badge-overdue { background: var(--error); color: #fff; }
```

- [ ] **Step 5: Run all tests**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/school/routes.py app/templates/school/index.html app/static/css/style.css tests/test_school_blackboard_pages.py
git commit -m "feat(school): To submit box with direct links; done deadlines get a check mark" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Reading class changes from announcements

**Files:**
- Create: `app/school/services/class_changes.py`, `tests/test_school_class_changes.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Announced(kind: str, day: date, start: time | None = None, end: time | None = None, room: str | None = None)` (NamedTuple); `kind` is `"online"` / `"cancelled"` / `"makeup"`.
  - `read_announcement(title: str, text: str, posted_at: datetime) -> list[Announced]` (`posted_at` naive UTC).
  - `ClassChange(code: str, bb_course_id: int, kind: str, day: date, start, end, room)` (NamedTuple).
  - `changes_from(announcements: iterable of (course_code, bb_course_id, title, text, posted_at)) -> dict[(str, date), ClassChange]`, the newest announcement winning.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_school_class_changes.py`:

```python
"""Reading class changes from Blackboard announcements. posted_at values are naive UTC."""

import unicodedata
from datetime import date, datetime, time

import pytest

from app.school.services import class_changes
from app.school.services.class_changes import Announced, ClassChange, changes_from, read_announcement

# Real announcements from September 2026, with Teams codes and links shortened.
PROBABILITY_ONLINE = (
    "ONLINE CLASS ON SEPTEMBER 24",
    "Dear all, The class on September 24 is online on MS TEAMS. Please use the following code to access the class.",
    datetime(2026, 9, 23, 16, 7),
)
WEB_ONLINE = (
    "Online Class Notification – Web Application – 22 September 2026",
    "Dear Students, Please be informed that our Web Application class will be conducted online via Microsoft "
    "Teams. Date: Tuesday, 22 September 2026 Time: From 8:00 AM Platform: Microsoft Teams Online Class Link: "
    "https://teams.microsoft.com/l/meetup-join/19%3ameeting_x%40thread.v2/0?context=%7b%22Tid%22%3a%2212-10%22",
    datetime(2026, 9, 15, 16, 0),
)
PHYSICS_ONLINE = (
    "Link học online sáng thứ Sáu, 18/9/2026, 8g00-9g40",
    "Link: Physics 4 Friday, September 18 Time zone: Asia/Ho_Chi_Minh Google Meet joining info "
    "Video call link: https://meet.google.com/abc-defg-hij",
    datetime(2026, 9, 17, 9, 30),
)
PROBABILITY_CANCEL = (
    "Cancel class on September 17",
    "The class this week on September 17 will be canceled. The makeup schedule will be announced later",
    datetime(2026, 9, 15, 2, 36),
)
LOGISTICS = (
    "Logistics Reminder",
    "Lecture attendance: You will attend the first five lectures with me in person in Room A1.603 , with our "
    "last in-person lecture on 10/10. Attendance will be taken during these sessions. Starting the week of "
    "12/10 , lectures will be taught online by Dr. Tuan Nguyen via MS Teams. Please register your group in "
    "SkillsGroupTerm1-26-27_Sat.xlsx , available on our MS Teams Channel.",
    datetime(2026, 9, 22, 3, 59),
)
POSTED = datetime(2026, 9, 20, 2, 0)  # Sun 20/09 09:00 in Vietnam


@pytest.mark.parametrize("announcement, expected", [
    (PROBABILITY_ONLINE, {Announced("online", date(2026, 9, 24))}),
    (WEB_ONLINE, {Announced("online", date(2026, 9, 22))}),
    (PHYSICS_ONLINE, {Announced("online", date(2026, 9, 18))}),
    (PROBABILITY_CANCEL, {Announced("cancelled", date(2026, 9, 17))}),
])
def test_the_real_announcements(announcement, expected):
    assert set(read_announcement(*announcement)) == expected


def test_only_a_sentence_with_a_change_word_counts():
    # "in-person ... on 10/10" has no change word. "Starting the week of 12/10 ... online" is read as the
    # single day 12/10; ranges are out of scope (and the course has no class that Monday).
    assert read_announcement(*LOGISTICS) == [Announced("online", date(2026, 10, 12))]


@pytest.mark.parametrize("title", [
    "Online class on Sept. 24",
    "Online class on 24th September",
    "Online class on September 24th, 2026",
    "Lớp học trực tuyến ngày 24 tháng 9 năm 2026",
    "The lecture on 24/09 is online",
    unicodedata.normalize("NFD", "Lớp học trực tuyến ngày 24/9"),
])
def test_date_formats_and_vietnamese(title):
    assert read_announcement(title, "", POSTED) == [Announced("online", date(2026, 9, 24))]


@pytest.mark.parametrize("title", ["Lớp nghỉ ngày 24/09", "Hủy buổi học 24-9-2026", "No class on Sep 24",
                                   "Class on 24/9 is cancelled"])
def test_cancel_words(title):
    assert read_announcement(title, "", POSTED) == [Announced("cancelled", date(2026, 9, 24))]


@pytest.mark.parametrize("title", [
    "Submit your report online by 24/9",  # no class word
    "The class on September 10 was online",  # before the posting day
    "Online class soon",  # no date
    "Online class from 10:30-11:45 in A2.401",  # times are not dates
    "Online class, see https://example.com/10-11/12",  # dates inside links are ignored
])
def test_what_changes_nothing(title):
    assert read_announcement(title, "", POSTED) == []


def test_a_date_without_a_year_is_placed_near_the_posting_date():
    posted = datetime(2026, 12, 28, 2, 0)

    assert read_announcement("Online class on January 5", "", posted) == [Announced("online", date(2027, 1, 5))]


def test_each_date_takes_the_nearest_change_word():
    title = "The class on 26/9 is cancelled; make-up class on 3/10 from 8:00 to 9:40 in A2.401."

    assert read_announcement(title, "", POSTED) == [
        Announced("cancelled", date(2026, 9, 26)),
        Announced("makeup", date(2026, 10, 3), time(8, 0), time(9, 40), "A2.401"),
    ]


@pytest.mark.parametrize("title, start, end, room", [
    ("Học bù ngày 3/10", None, None, None),
    ("Make-up class on 3/10, 8g00-9g40", time(8, 0), time(9, 40), None),
    ("Make up class on 3/10 at 13h15", time(13, 15), None, None),
    ("Makeup class online on 3/10, 1:15 PM", time(13, 15), None, "Online"),
    ("Make-up lecture on 3/10 from 8:00 AM to 9:40 AM, room R109", time(8, 0), time(9, 40), "R109"),
])
def test_make_up_classes(title, start, end, room):
    assert read_announcement(title, "", POSTED) == [Announced("makeup", date(2026, 10, 3), start, end, room)]


def row(title, posted, code="MA026IU", bb_course_id=5, text=""):
    return (code, bb_course_id, title, text, posted)


def test_the_newest_announcement_wins_for_a_course_and_date():
    rows = [row("Class on 24/9 is cancelled", datetime(2026, 9, 21)), row("Online class on 24/9", datetime(2026, 9, 20))]

    assert changes_from(rows) == {("MA026IU", date(2026, 9, 24)): ClassChange(
        "MA026IU", 5, "cancelled", date(2026, 9, 24), None, None, None)}


def test_announcements_without_a_course_code_or_time_are_skipped():
    assert changes_from([row("Online class on 24/9", None), row("Online class on 24/9", POSTED, code=None)]) == {}


def test_an_unreadable_announcement_is_skipped(monkeypatch):
    real = class_changes.read_announcement

    def read(title, text, posted_at):
        if title == "bad":
            raise ValueError("boom")
        return real(title, text, posted_at)

    monkeypatch.setattr(class_changes, "read_announcement", read)

    assert list(changes_from([row("bad", POSTED), row("Online class on 24/9", POSTED)])) == [("MA026IU", date(2026, 9, 24))]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_class_changes.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'app.school.services.class_changes'`.

- [ ] **Step 3: Implement**

Create `app/school/services/class_changes.py`:

```python
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
    r"(?P<makeup>make[\s-]?up|\bbù\b)"
    r"|(?P<cancelled>cancel\w*|no class|nghỉ|hủy|huỷ)"
    r"|(?P<online>online|trực tuyến)",
    re.IGNORECASE,
)
CLASS_WORDS = re.compile(r"class|lecture|session|lesson|lớp|buổi|\bhọc\b|tiết", re.IGNORECASE)

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
```

- [ ] **Step 4: Run them**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_class_changes.py -q`
Expected: 30 passed.

- [ ] **Step 5: Commit**

```bash
git add app/school/services/class_changes.py tests/test_school_class_changes.py
git commit -m "feat(school): read online, cancelled and make-up classes from announcements" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Changed classes in the calendar and on the Overview

**Files:**
- Modify: `app/school/services/schedule.py`, `app/school/routes.py`, `app/templates/school/_item.html`, `app/templates/school/timetable.html`, `app/static/js/timetable.js`, `app/static/css/style.css`
- Create: `tests/test_school_class_change_pages.py`

**Interfaces:**
- Consumes: `class_changes.changes_from(...)`, `ClassChange` (Task 3).
- Produces: `schedule.Item` gains `change: str | None = None`, `bb_course_id: int | None = None`, `all_day: bool = False`. `items_between(user_id, start_utc, end_utc)` keeps its signature and returns changed items. Calendar events of changed classes have `classNames` `["event-changed"]` or `["event-cancelled"]`, `extendedProps.change`, and `url` (the app's course page).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_school_class_change_pages.py`:

```python
"""Classes changed by Blackboard announcements, in the calendar feed and on the Overview.
Times in the database are naive UTC; Vietnam is UTC+7."""

from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbCourse, SchoolClassMeeting, SchoolCourse
from tests.helpers import make_user, register

BB = "https://blackboard.hcmiu.edu.vn/x"
PROBABILITY = "Probability, Statistic & Random Process"
# Thursdays 13:15-15:45 in Vietnam = 06:15-08:45 UTC
THU_24 = (datetime(2026, 9, 24, 6, 15), datetime(2026, 9, 24, 8, 45), "A2.407")
THU_01 = (datetime(2026, 10, 1, 6, 15), datetime(2026, 10, 1, 8, 45), "A2.407")
POSTED = datetime(2026, 9, 20, 2, 0)
WEEK = {"start": "2026-09-21", "end": "2026-09-28"}  # Mon 21/09 - Sun 27/09


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)  # user 1
    return client


def add_timetable(app, user_id, code, name, meetings):
    with app.app_context():
        course = SchoolCourse(user_id=user_id, term_code="20261", course_code=code, course_name=name)
        course.meetings = [SchoolClassMeeting(user_id=user_id, start_at=s, end_at=e, room=r) for s, e, r in meetings]
        db.session.add(course)
        db.session.commit()


def announce(app, user_id, code, title, text="", posted_at=POSTED):
    with app.app_context():
        course = SchoolBbCourse(user_id=user_id, bb_id=f"_{code}_1", course_code=code, name=f"{code} on Blackboard",
                                url=BB)
        course.announcements = [SchoolBbAnnouncement(user_id=user_id, bb_id="_1_1", title=title, text=text,
                                                     posted_at=posted_at, url=BB)]
        db.session.add(course)
        db.session.commit()
        return course.id


def classes(browser, **week):
    events = browser.get("/school/api/calendar", query_string=week or WEEK).get_json()
    return [e for e in events if e["extendedProps"]["kind"] == "class"]


def makeups(browser):
    return [e for e in classes(browser) if e["extendedProps"].get("change") == "makeup"]


def test_an_online_class_is_purple_and_links_to_the_announcement(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24, THU_01])
    course_id = announce(app, 1, "MA026IU", "ONLINE CLASS ON SEPTEMBER 24", posted_at=datetime(2026, 9, 23, 16, 7))

    [event] = classes(browser)

    assert event["title"] == f"Online: {PROBABILITY}"
    assert (event["classNames"], event["extendedProps"]["room"], event["extendedProps"]["change"]) == (
        ["event-changed"], "Online", "online")
    assert event["url"] == f"/school/courses/{course_id}"
    [next_week] = classes(browser, start="2026-09-28", end="2026-10-05")
    assert next_week["classNames"] == ["event-class"] and "url" not in next_week


def test_a_cancelled_class_stays_in_its_slot_greyed(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Cancel class on September 24")

    [event] = classes(browser)

    assert (event["title"], event["classNames"], event["start"]) == (
        f"Cancelled: {PROBABILITY}", ["event-cancelled"], "2026-09-24T13:15:00")
    assert event["extendedProps"]["room"] == "A2.407"


def test_a_make_up_class_with_a_time_is_added(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on Saturday 26/9 from 8:00 to 9:40 in A2.401")

    assert [(e["title"], e["start"], e["end"], e["extendedProps"]["room"]) for e in makeups(browser)] == [
        (f"Make-up: {PROBABILITY}", "2026-09-26T08:00:00", "2026-09-26T09:40:00", "A2.401")]
    assert len(classes(browser)) == 2  # the normal Thursday class is still there


def test_a_make_up_class_without_an_end_lasts_as_long_as_the_usual_class(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24, THU_01])
    announce(app, 1, "MA026IU", "Make-up class on 26/9 at 13h15")

    assert [(e["start"], e["end"]) for e in makeups(browser)] == [("2026-09-26T13:15:00", "2026-09-26T15:45:00")]


def test_a_make_up_class_ending_before_it_starts_uses_the_usual_length(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on 26/9 from 13:15 to 9:40")

    assert [(e["start"], e["end"]) for e in makeups(browser)] == [("2026-09-26T13:15:00", "2026-09-26T15:45:00")]


def test_a_make_up_class_without_a_time_is_an_all_day_note(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Học bù ngày 26/9")

    [note] = [e for e in classes(browser) if e.get("allDay")]

    assert (note["title"], note["start"], note["classNames"]) == (
        f"Make-up class: {PROBABILITY} (see announcement)", "2026-09-26", ["event-changed"])


def test_a_make_up_class_at_the_time_of_a_class_is_not_added_twice(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on 24/9 at 13:15")

    assert len(classes(browser)) == 1


def test_changes_need_a_class_of_that_course_on_that_day(app, browser):
    # The real "Logistics Reminder": "Starting the week of 12/10, lectures will be taught online" is read as
    # Mon 12/10, and this Saturday course has no class that day.
    sat_10 = (datetime(2026, 10, 10, 6, 15), datetime(2026, 10, 10, 8, 45), "A1.603")
    sat_17 = (datetime(2026, 10, 17, 6, 15), datetime(2026, 10, 17, 8, 45), "A1.603")
    add_timetable(app, 1, "IT007WE", "Skills for Communicating Information", [sat_10, sat_17])
    announce(app, 1, "IT007WE", "Logistics Reminder",
             "Our last in-person lecture is on 10/10. Starting the week of 12/10 , lectures will be taught "
             "online by Dr. Tuan Nguyen via MS Teams.", posted_at=datetime(2026, 9, 22, 3, 59))

    events = classes(browser, start="2026-10-05", end="2026-10-19")

    assert [e["classNames"] for e in events] == [["event-class"], ["event-class"]]


def test_a_make_up_for_a_course_not_in_the_timetable_is_ignored(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "EN011IU", "Make-up class on 26/9 at 8:00")

    assert len(classes(browser)) == 1


def test_another_users_announcements_never_change_my_classes(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, make_user(app, email="binh@example.com"), "MA026IU", "ONLINE CLASS ON SEPTEMBER 24")

    [event] = classes(browser)

    assert event["classNames"] == ["event-class"]


def test_the_overview_shows_todays_online_class(app, browser, monkeypatch):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    course_id = announce(app, 1, "MA026IU", "ONLINE CLASS ON SEPTEMBER 24", posted_at=datetime(2026, 9, 23, 16, 7))
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 24, 0, 30))  # Thu 07:30 in Vietnam

    soup = BeautifulSoup(browser.get("/school/").get_data(as_text=True), "html.parser")
    [item] = soup.select("li.item-changed")

    assert "Online" in item.select_one(".badge-changed").get_text()
    assert item.find("a", string=lambda s: s and "See announcement" in s)["href"] == f"/school/courses/{course_id}"


def test_the_timetable_legend_explains_the_new_colours(browser):
    html = browser.get("/school/timetable").get_data(as_text=True)

    assert "Online / make-up" in html and "Cancelled" in html
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_class_change_pages.py -q`
Expected: failures (no `change` in events, no purple item, no legend text); `test_a_make_up_for_a_course_not_in_the_timetable_is_ignored`, `test_a_make_up_class_at_the_time_of_a_class_is_not_added_twice`, `test_changes_need_a_class_of_that_course_on_that_day` and `test_another_users_announcements_never_change_my_classes` may already pass (they pin what must not happen).

- [ ] **Step 3: Apply the changes in `schedule.py`**

Replace the top of `app/school/services/schedule.py` (docstring, imports, constants and `Item`) with:

```python
"""Classes and exams for a day or a week, with day boundaries in Vietnam time.

The database stores naive UTC, so a Vietnam day runs from 17:00 UTC the day
before to 17:00 UTC that day. Classes changed by a Blackboard announcement
(online, cancelled, make-up) are marked here, so every page shows them the same way.
"""

from collections import Counter
from datetime import datetime, time, timedelta
from typing import NamedTuple

from sqlalchemy import select

from app.extensions import db
from app.school.models import (
    SchoolBbAnnouncement,
    SchoolBbAssignment,
    SchoolBbCourse,
    SchoolClassMeeting,
    SchoolCourse,
    SchoolExam,
)
from app.school.services import class_changes

VIETNAM_OFFSET = timedelta(hours=7)
EXAM_LABELS = {"final": "Final exam", "midterm": "Midterm exam", "other": "Exam"}
DEFAULT_CLASS_LENGTH = timedelta(minutes=90)  # a make-up class of a course with no known classes


class Item(NamedTuple):
    kind: str  # "class" or "exam"
    start_at: datetime  # naive UTC
    end_at: datetime | None
    code: str
    title: str
    room: str | None
    label: str | None = None  # e.g. "Final exam"
    change: str | None = None  # "online" / "cancelled" / "makeup", from a Blackboard announcement
    bb_course_id: int | None = None  # the app's page for the course that announced the change
    all_day: bool = False  # a make-up class announced without a time
```

Below `day_start_utc`, add:

```python
def _announced_changes(user_id):
    rows = db.session.execute(
        select(SchoolBbCourse.course_code, SchoolBbCourse.id, SchoolBbAnnouncement.title,
               SchoolBbAnnouncement.text, SchoolBbAnnouncement.posted_at)
        .join(SchoolBbAnnouncement, SchoolBbAnnouncement.course_id == SchoolBbCourse.id)
        .where(SchoolBbCourse.user_id == user_id)
    ).all()
    return class_changes.changes_from(rows)


def _timetable_courses(user_id):
    """{course code: (course name, usual class length)}."""
    rows = db.session.execute(
        select(SchoolCourse.course_code, SchoolCourse.course_name, SchoolClassMeeting.start_at,
               SchoolClassMeeting.end_at)
        .outerjoin(SchoolClassMeeting, SchoolClassMeeting.course_id == SchoolCourse.id)
        .where(SchoolCourse.user_id == user_id)
    ).all()
    names, lengths = {}, {}
    for code, name, start_at, end_at in rows:
        names.setdefault(code, name)
        if start_at and end_at:
            lengths.setdefault(code, Counter())[end_at - start_at] += 1
    return {code: (name, lengths[code].most_common(1)[0][0] if code in lengths else DEFAULT_CLASS_LENGTH)
            for code, name in names.items()}


def _utc(day, clock):
    return datetime.combine(day, clock) - VIETNAM_OFFSET


def _with_changes(items, changes, courses, start_utc, end_utc):
    """Mark announced online and cancelled classes, and add make-up classes in [start_utc, end_utc)."""
    result = []
    for item in items:
        change = changes.get((item.code, vietnam_date(item.start_at))) if item.kind == "class" else None
        if change is not None and change.kind in ("online", "cancelled"):
            item = item._replace(change=change.kind, bb_course_id=change.bb_course_id,
                                 room="Online" if change.kind == "online" else item.room)
        result.append(item)
    for change in changes.values():
        if change.kind != "makeup" or change.code not in courses:
            continue
        name, usual = courses[change.code]
        marks = {"change": "makeup", "bb_course_id": change.bb_course_id}
        if change.start is None:
            day_start = day_start_utc(change.day)
            if start_utc <= day_start < end_utc:
                result.append(Item("class", day_start, None, change.code, name, change.room, all_day=True, **marks))
            continue
        start_at = _utc(change.day, change.start)
        end_at = _utc(change.day, change.end) if change.end and change.end > change.start else start_at + usual
        overlaps = any(i.kind == "class" and i.code == change.code and i.start_at < end_at
                       and (i.end_at or i.start_at) > start_at for i in result)
        if start_utc <= start_at < end_utc and not overlaps:
            result.append(Item("class", start_at, end_at, change.code, name, change.room, **marks))
    return sorted(result, key=lambda item: (item.start_at, item.kind))
```

In `items_between`, replace the final `return sorted(items, key=lambda item: (item.start_at, item.kind))` with:

```python
    return _with_changes(items, _announced_changes(user_id), _timetable_courses(user_id), start_utc, end_utc)
```

(`deadlines_between` and `items_on` stay as they are.)

- [ ] **Step 4: Calendar events for changed classes**

In `app/school/routes.py`, replace the whole `_calendar_event` function with:

```python
CHANGE_TITLES = {"online": "Online", "makeup": "Make-up", "cancelled": "Cancelled"}


def _calendar_event(item):
    title = f"{item.label}: {item.title}" if item.label else item.title
    css = f"event-{item.kind}"
    if item.change:
        title = f"{CHANGE_TITLES[item.change]}: {title}"
        css = "event-cancelled" if item.change == "cancelled" else "event-changed"
    event = {
        "title": f"Make-up class: {item.title} (see announcement)" if item.all_day else title,
        "start": _wall_clock(item.start_at),
        "classNames": [css],
        "extendedProps": {"kind": item.kind, "code": item.code, "room": item.room},
    }
    if item.all_day:
        event["start"] = schedule.vietnam_date(item.start_at).isoformat()
        event["allDay"] = True
    elif item.end_at:
        event["end"] = _wall_clock(item.end_at)
    if item.change:
        event["extendedProps"]["change"] = item.change
    if item.bb_course_id:
        event["url"] = url_for("school.course", course_id=item.bb_course_id)
    return event
```

- [ ] **Step 5: Overview items, legend, calendar label and CSS**

Replace the whole of `app/templates/school/_item.html` with:

```html
{% macro schedule_item(item) %}
  {% set labels = {"online": "Online", "makeup": "Make-up", "cancelled": "Cancelled"} %}
  {% set look = "cancelled" if item.change == "cancelled" else "changed" %}
  <li class="item item-{{ item.kind }}{% if item.change %} item-{{ look }}{% endif %}">
    <span class="item-time">
      {%- if item.all_day %}All day{% else %}{{ item.start_at | vn_clock }}{% if item.end_at %}–{{ item.end_at | vn_clock }}{% endif %}{% endif -%}
    </span>
    <span class="item-title">
      {% if item.change %}<span class="badge badge-{{ look }}">{{ labels[item.change] }}</span> {% endif %}
      {% if item.label %}<strong>{{ item.label }}:</strong> {% endif %}{{ item.title }}
    </span>
    <span class="item-meta">
      {{ item.code }}
      {% if item.room and item.change != "online" %}
        · {% if item.room.upper().startswith("ONLINE") %}<span class="badge">Online</span>{% else %}{{ item.room }}{% endif %}
      {% endif %}
      {% if item.bb_course_id %}
        · <a href="{{ url_for('school.course', course_id=item.bb_course_id) }}">See announcement</a>
      {% endif %}
    </span>
  </li>
{% endmacro %}
```

In `app/templates/school/timetable.html`, after `<span class="legend-item legend-due">Deadline</span>`, add:

```html
    <span class="legend-item legend-changed">Online / make-up</span>
    <span class="legend-item legend-cancelled">Cancelled</span>
```

In `app/static/js/timetable.js`, change `allDayText: "Due",` to `allDayText: "All day",`.

Append to `app/static/css/style.css`:

```css
/* School: classes changed by an announcement */
:root { --changed-color: #6f42c1; --cancelled-color: #c9ced6; }
.legend-changed::before { background: var(--changed-color); }
.legend-cancelled::before { background: var(--cancelled-color); }
.fc .event-changed { background: var(--changed-color); border-color: var(--changed-color); color: #fff; }
.fc .event-cancelled { background: #eef0f3; border-color: var(--cancelled-color); color: var(--muted); }
.fc .event-cancelled .event-title { text-decoration: line-through; }
.fc .fc-list-event.event-changed, .fc .fc-list-event.event-cancelled { background: transparent; color: var(--text); }
.fc .fc-list-event.event-changed .fc-list-event-dot { border-color: var(--changed-color); }
.fc .fc-list-event.event-cancelled .fc-list-event-dot { border-color: var(--cancelled-color); }
.fc .fc-list-event.event-cancelled .event-title { color: var(--muted); }
.item-changed { border-left-color: var(--changed-color); }
.item-cancelled { border-left-color: var(--cancelled-color); color: var(--muted); }
.item-cancelled .item-title { text-decoration: line-through; }
.badge-changed { background: var(--changed-color); color: #fff; }
.badge-cancelled { background: var(--cancelled-color); color: var(--text); }
```

- [ ] **Step 6: Run all tests**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (the existing calendar tests keep their exact event dictionaries: unchanged classes get no `change` or `url`).

- [ ] **Step 7: Commit**

```bash
git add app/school/services/schedule.py app/school/routes.py app/templates/school/_item.html app/templates/school/timetable.html app/static/js/timetable.js app/static/css/style.css tests/test_school_class_change_pages.py
git commit -m "feat(school): online, cancelled and make-up classes in the timetable and on the Overview" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Browser check, real sync, spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-09-26-class-changes-and-to-submit-design.md`

- [ ] **Step 1: Browser check**

Seed a scratch SQLite database the same way as the Blackboard check (`create_app` with `DATABASE_URL=sqlite:///<scratch>/cc.db`, `finish_run` with the timetable, exams, tuition and `read_blackboard(Replay(), REGISTERED)` samples). Then add these announcements to the matching Blackboard courses (same `course_code`), with `posted_at` as given (naive UTC):

| course_code | title | posted_at |
|---|---|---|
| MA026IU | ONLINE CLASS ON SEPTEMBER 24 | 2026-09-23 16:07 |
| MA026IU | Cancel class on September 17 | 2026-09-15 02:36 |
| PH012IU | Make-up class on Saturday 26/9 from 8:00 to 9:40 in A2.401 | 2026-09-20 02:00 |
| IT093IU | Học bù ngày 27/9 | 2026-09-20 02:00 |

Run `flask run --port 5059` on it and use the scratch Playwright environment with Edge to screenshot `/school/` (today's real date), `/school/timetable` for the weeks of 14/09 and 21/09, the list view at 390×844, and one course page. Take them at 1400×1000 and 390×844, with the device in dark and in light mode. Look at every screenshot: Thu 24/09 Probability purple "Online:"; Thu 17/09 grey and crossed out; Sat 26/09 purple make-up 08:00–09:40; Sun 27/09 an all-day purple note; the legend; "To submit" with "Open assignment ↗". The only allowed console error is the missing `/favicon.ico`. Measure that no page is wider than the screen (`document.documentElement.scrollWidth`).

- [ ] **Step 2: Real sync**

Start the site on port 5000 (`flask run`), run `.venv/Scripts/sla-agent.exe sync-now` (expected: "Sync finished."), then check:

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
from dotenv import dotenv_values; from sqlalchemy import create_engine, text
with create_engine(dotenv_values('.env')['DATABASE_URL']).connect() as c:
    print(list(c.execute(text('SELECT name, status, url FROM school_bb_assignments ORDER BY due_at'))))"
```

Expected: assignments linked to Blackboard items have `displayIndividualContent?course_id=…&content_id=…` URLs. Then, in an app context for the student's user, print `schedule.items_between(user_id, schedule.day_start_utc(date(2026, 9, 14)), schedule.day_start_utc(date(2026, 9, 28)))` and check: Probability 17/09 `cancelled`, 24/09 `online`; Physics 18/09 `online`; Web Application Development 22/09 `online`. Stop the site afterwards.

- [ ] **Step 3: Spec status, full tests, commit**

In the spec, change the status line to `**Status:** Built (see docs/superpowers/plans/2026-09-26-class-changes-and-to-submit.md)`.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

```bash
git add docs/superpowers/specs/2026-09-26-class-changes-and-to-submit-design.md
git commit -m "docs: class changes and To submit built" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
