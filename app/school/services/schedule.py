"""Classes and exams for a day or a week, with day boundaries in Vietnam time.

The database stores naive UTC, so a Vietnam day runs from 17:00 UTC the day
before to 17:00 UTC that day.
"""

from datetime import datetime, time, timedelta
from typing import NamedTuple

from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolClassMeeting, SchoolCourse, SchoolExam

VIETNAM_OFFSET = timedelta(hours=7)
EXAM_LABELS = {"final": "Final exam", "midterm": "Midterm exam", "other": "Exam"}


class Item(NamedTuple):
    kind: str  # "class" or "exam"
    start_at: datetime  # naive UTC
    end_at: datetime | None
    code: str
    title: str
    room: str | None
    label: str | None = None  # e.g. "Final exam"


def vietnam_date(moment_utc):
    return (moment_utc + VIETNAM_OFFSET).date()


def day_start_utc(day):
    """Midnight in Vietnam on `day`, as naive UTC."""
    return datetime.combine(day, time()) - VIETNAM_OFFSET


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
    return sorted(items, key=lambda item: (item.start_at, item.kind))


def items_on(user_id, day):
    return items_between(user_id, day_start_utc(day), day_start_utc(day + timedelta(days=1)))
