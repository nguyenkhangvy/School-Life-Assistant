from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.extensions import db
from app.school.models import (
    SchoolChange,
    SchoolClassMeeting,
    SchoolCourse,
    SchoolExam,
    SchoolSyncRun,
    SchoolTuition,
)
from tests.helpers import api, full_payload, make_device, make_user


@pytest.fixture
def key(app):
    return make_device(app, make_user(app))


def sync(app, key, payload):
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "manual"}).get_json()["run_id"]
    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["status"]


def rows(app, model, **filters):
    with app.app_context():
        return db.session.execute(select(model).filter_by(**filters).order_by(model.id)).scalars().all()


def payload_with_course(
    code, name, term="20261", start="2026-10-06T08:00:00+07:00", end="2026-10-06T10:30:00+07:00", room="A2.307"
):
    payload = full_payload()
    payload["timetable"]["data"]["term_code"] = term
    payload["timetable"]["data"]["courses"] = [
        {"course_code": code, "course_name": name, "meetings": [{"start_at": start, "end_at": end, "room": room}]}
    ]
    return payload


def failed(message="Table not found"):
    return {"status": "failed", "error_code": "edusoft_changed", "error_message": message}


def test_a_successful_sync_saves_every_part_with_times_in_utc(app, key):
    assert sync(app, key, full_payload()) == "success"

    [course] = rows(app, SchoolCourse)
    assert (course.term_code, course.course_code, course.group_code, float(course.credits), course.lecturer) == (
        "20261", "IT093IU", "01", 4.0, "Nguyen Van A",
    )
    [meeting] = rows(app, SchoolClassMeeting)
    assert (meeting.course_id, meeting.start_at, meeting.end_at, meeting.room) == (
        course.id, datetime(2026, 9, 29, 1, 0), datetime(2026, 9, 29, 3, 30), "A2.307",
    )
    [exam] = rows(app, SchoolExam)
    assert (exam.exam_type, exam.start_at, exam.duration_min, exam.room) == (
        "final", datetime(2026, 12, 12, 1, 0), 90, "A1.101",
    )
    [tuition] = rows(app, SchoolTuition)
    assert (tuition.amount_due, tuition.amount_paid, tuition.balance, tuition.due_date, tuition.status_text) == (
        12500000, 0, 12500000, date(2026, 10, 15), "Chưa đóng",
    )


def test_a_new_sync_replaces_that_terms_timetable(app, key):
    sync(app, key, payload_with_course("IT001IU", "Old course"))

    sync(app, key, payload_with_course("IT002IU", "New course"))

    assert [c.course_code for c in rows(app, SchoolCourse)] == ["IT002IU"]
    [meeting] = rows(app, SchoolClassMeeting)
    assert meeting.course_id == rows(app, SchoolCourse)[0].id


def test_a_failed_part_keeps_its_old_data_and_records_why(app, key):
    sync(app, key, full_payload())
    payload = payload_with_course("IT002IU", "New course")
    payload["tuition"] = failed("Tuition table not found")

    assert sync(app, key, payload) == "partial"

    [tuition] = rows(app, SchoolTuition)
    assert tuition.balance == 12500000
    assert [c.course_code for c in rows(app, SchoolCourse)] == ["IT002IU"]
    last_run = rows(app, SchoolSyncRun)[-1]
    assert last_run.sections["tuition"] == {
        "status": "failed", "error_code": "edusoft_changed", "error_message": "Tuition table not found",
    }
    assert last_run.sections["timetable"]["status"] == "ok"


def test_other_terms_and_other_users_are_untouched(app, key):
    sync(app, key, payload_with_course("IT001IU", "Last term course", term="20253"))
    other_key = make_device(app, make_user(app, email="binh@example.com"))
    sync(app, other_key, payload_with_course("BA001IU", "Binh's course"))

    sync(app, key, payload_with_course("IT002IU", "This term course"))

    assert sorted(c.course_code for c in rows(app, SchoolCourse)) == ["BA001IU", "IT001IU", "IT002IU"]


def test_a_whole_run_error_changes_no_data(app, key):
    sync(app, key, full_payload())

    status = sync(app, key, {"error_code": "bad_credentials", "error_message": "EduSoft rejected the password"})

    assert status == "failed"
    assert len(rows(app, SchoolCourse)) == 1
    assert len(rows(app, SchoolTuition)) == 1
    last_run = rows(app, SchoolSyncRun)[-1]
    assert (last_run.error_code, last_run.sections) == ("bad_credentials", None)


# ---- "What changed" feed ------------------------------------------------------


def test_each_sync_records_what_changed(app, key):
    # 2099 keeps these classes "upcoming" whenever the tests run.
    future = {"start": "2099-10-06T08:00:00+07:00", "end": "2099-10-06T10:30:00+07:00"}
    sync(app, key, payload_with_course("IT001IU", "Web", **future))
    first_run_changes = [(c.section, c.kind) for c in rows(app, SchoolChange)]

    sync(app, key, payload_with_course("IT001IU", "Web", room="LA1.605", **future))

    assert first_run_changes == [("timetable", "added"), ("exams", "added"), ("tuition", "added")]
    last_run = rows(app, SchoolSyncRun)[-1]
    [change] = rows(app, SchoolChange, sync_run_id=last_run.id)
    assert (change.section, change.kind) == ("timetable", "changed")
    assert "IT001IU Web: room A2.307 → LA1.605" in change.summary


def test_a_failed_part_records_no_changes(app, key):
    sync(app, key, full_payload())
    payload = full_payload()
    payload["tuition"] = failed()

    sync(app, key, payload)

    last_run = rows(app, SchoolSyncRun)[-1]
    assert rows(app, SchoolChange, sync_run_id=last_run.id) == []
