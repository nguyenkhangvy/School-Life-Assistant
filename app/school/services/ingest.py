"""Save the result of a sync run.

Each part that arrived correctly replaces that user's rows for that term,
after comparing old and new rows for the "What changed" feed. A part that
failed keeps its old rows. The caller commits, so the whole finish is one
transaction.
"""

from datetime import timezone
from decimal import Decimal

from sqlalchemy import delete, select

from app.extensions import db
from app.school.models import (
    SchoolChange,
    SchoolClassMeeting,
    SchoolCourse,
    SchoolExam,
    SchoolTuition,
)
from app.school.services.changes import (
    ExamInfo,
    Meeting,
    TuitionInfo,
    exam_changes,
    timetable_changes,
    tuition_changes,
)


def to_utc(moment):
    """Aware datetime -> naive UTC, as stored in the database."""
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _save_timetable(user_id, timetable, now):
    term = {"user_id": user_id, "term_code": timetable.term_code}
    had_courses = db.session.execute(select(SchoolCourse.id).filter_by(**term).limit(1)).first() is not None
    old = None
    if had_courses:
        old = [
            Meeting(course.course_code, course.course_name, meeting.start_at, meeting.end_at, meeting.room)
            for meeting, course in db.session.execute(
                select(SchoolClassMeeting, SchoolCourse)
                .join(SchoolCourse)
                .where(SchoolCourse.user_id == user_id, SchoolCourse.term_code == timetable.term_code)
            )
        ]
    new = [
        Meeting(course.course_code, course.course_name, to_utc(m.start_at), to_utc(m.end_at), m.room)
        for course in timetable.courses
        for m in course.meetings
    ]

    term_courses = select(SchoolCourse.id).filter_by(**term)
    db.session.execute(delete(SchoolClassMeeting).where(SchoolClassMeeting.course_id.in_(term_courses)))
    db.session.execute(delete(SchoolCourse).filter_by(**term))
    for course in timetable.courses:
        row = SchoolCourse(
            **term,
            course_code=course.course_code,
            course_name=course.course_name,
            group_code=course.group,
            credits=None if course.credits is None else Decimal(str(course.credits)),
            lecturer=course.lecturer,
        )
        row.meetings = [
            SchoolClassMeeting(user_id=user_id, start_at=to_utc(m.start_at), end_at=to_utc(m.end_at), room=m.room)
            for m in course.meetings
        ]
        db.session.add(row)

    return timetable_changes(old, new, now)


def _save_exams(user_id, exams, now):
    term = {"user_id": user_id, "term_code": exams.term_code}
    old_rows = db.session.execute(select(SchoolExam).filter_by(**term)).scalars().all()
    old = [ExamInfo(e.course_code, e.course_name, e.exam_type, e.start_at, e.room) for e in old_rows] or None
    new = [ExamInfo(e.course_code, e.course_name, e.exam_type, to_utc(e.start_at), e.room) for e in exams.exams]

    db.session.execute(delete(SchoolExam).filter_by(**term))
    db.session.add_all(
        SchoolExam(
            **term,
            course_code=exam.course_code,
            course_name=exam.course_name,
            exam_type=exam.exam_type,
            start_at=to_utc(exam.start_at),
            duration_min=exam.duration_min,
            room=exam.room,
            notes=exam.notes,
        )
        for exam in exams.exams
    )
    return exam_changes(old, new, now)


def _save_tuition(user_id, tuition, now):
    term = {"user_id": user_id, "term_code": tuition.term_code}
    old_row = db.session.execute(select(SchoolTuition).filter_by(**term)).scalar_one_or_none()
    old = None if old_row is None else TuitionInfo(
        old_row.term_code, old_row.balance, old_row.due_date, old_row.status_text
    )
    new = TuitionInfo(tuition.term_code, tuition.balance, tuition.due_date, tuition.status_text)

    db.session.execute(delete(SchoolTuition).filter_by(**term))
    db.session.add(
        SchoolTuition(
            **term,
            amount_due=tuition.amount_due,
            amount_paid=tuition.amount_paid,
            balance=tuition.balance,
            due_date=tuition.due_date,
            status_text=tuition.status_text,
            items=[item.model_dump() for item in tuition.items],
        )
    )
    return tuition_changes(old, new)


SAVERS = {"timetable": _save_timetable, "exams": _save_exams, "tuition": _save_tuition}


def finish_run(run, payload, now):
    run.status = payload.overall_status()
    run.finished_at = now
    run.error_code = payload.error_code
    run.error_message = payload.error_message
    if payload.error_code is not None:
        return

    summary = {}
    for name, result in payload.sections().items():
        if result.status != "ok":
            summary[name] = {
                "status": "failed",
                "error_code": result.error_code,
                "error_message": result.error_message,
            }
            continue
        for change in SAVERS[name](run.user_id, result.data, now):
            db.session.add(
                SchoolChange(
                    user_id=run.user_id, sync_run_id=run.id, section=name, kind=change.kind, summary=change.summary
                )
            )
        summary[name] = {"status": "ok"}
    run.sections = summary
