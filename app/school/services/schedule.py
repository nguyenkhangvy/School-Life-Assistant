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


def vietnam_date(moment_utc):
    return (moment_utc + VIETNAM_OFFSET).date()


def day_start_utc(day):
    """Midnight in Vietnam on `day`, as naive UTC."""
    return datetime.combine(day, time()) - VIETNAM_OFFSET


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
    """Mark announced online and cancelled classes, and add make-up classes in [start_utc, end_utc).

    No make-up is added on a day the course has a class: such a date names the original class, as in
    "the make-up for the class on 24/9"."""
    result = []
    for item in items:
        change = changes.get((item.code, vietnam_date(item.start_at), "class")) if item.kind == "class" else None
        if change is not None and change.kind in ("online", "cancelled"):
            item = item._replace(change=change.kind, bb_course_id=change.bb_course_id,
                                 room="Online" if change.kind == "online" else item.room)
        result.append(item)
    class_days = {(item.code, vietnam_date(item.start_at)) for item in items if item.kind == "class"}
    for change in changes.values():
        if change.kind != "makeup" or change.code not in courses or (change.code, change.day) in class_days:
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
        if start_utc <= start_at < end_utc:
            result.append(Item("class", start_at, end_at, change.code, name, change.room, **marks))
    return sorted(result, key=lambda item: (item.start_at, item.kind))


def items_between(user_id, start_utc, end_utc):
    classes = db.session.execute(
        select(SchoolClassMeeting, SchoolCourse)
        .join(SchoolCourse)
        .where(
            SchoolClassMeeting.user_id == user_id,
            SchoolClassMeeting.start_at >= start_utc,
            SchoolClassMeeting.start_at < end_utc,
        )
    ).all()
    exams = db.session.execute(
        select(SchoolExam).where(
            SchoolExam.user_id == user_id, SchoolExam.start_at >= start_utc, SchoolExam.start_at < end_utc
        )
    ).scalars().all()
    items = [Item("class", m.start_at, m.end_at, c.course_code, c.course_name, m.room) for m, c in classes]
    items += [
        Item("exam", e.start_at, e.start_at + timedelta(minutes=e.duration_min) if e.duration_min else None,
             e.course_code, e.course_name, e.room, EXAM_LABELS.get(e.exam_type, "Exam"))
        for e in exams
    ]
    return _with_changes(items, _announced_changes(user_id), _timetable_courses(user_id), start_utc, end_utc)


def items_on(user_id, day):
    return items_between(user_id, day_start_utc(day), day_start_utc(day + timedelta(days=1)))


def deadlines_between(user_id, start_utc, end_utc):
    """Blackboard deadlines in [start_utc, end_utc), soonest first."""
    return db.session.execute(
        select(SchoolBbAssignment).where(
            SchoolBbAssignment.user_id == user_id,
            SchoolBbAssignment.due_at >= start_utc,
            SchoolBbAssignment.due_at < end_utc,
        ).order_by(SchoolBbAssignment.due_at)
    ).scalars().all()
