from datetime import datetime

import pytest
from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse, SchoolBbMaterial, SchoolChange
from tests.helpers import api, blackboard_payload, full_payload, make_device, make_user


@pytest.fixture
def key(app):
    return make_device(app, make_user(app))


def sync(app, key, blackboard_part):
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "manual"}).get_json()["run_id"]
    payload = full_payload()
    payload["blackboard"] = blackboard_part
    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["status"]


def rows(app, model):
    with app.app_context():
        return db.session.execute(select(model).order_by(model.id)).scalars().all()


def test_the_blackboard_section_is_saved_with_times_in_utc(app, key):
    assert sync(app, key, {"status": "ok", "data": blackboard_payload()}) == "success"

    [course] = rows(app, SchoolBbCourse)
    assert (course.bb_id, course.course_code, course.name) == ("_101_1", "IT093IU", "Web Application Development")
    [assignment] = rows(app, SchoolBbAssignment)
    assert (assignment.course_id, assignment.due_at, assignment.score, assignment.status) == (
        course.id, datetime(2026, 10, 2, 16, 59), 8.5, "graded")
    assert len(rows(app, SchoolBbAnnouncement)) == 1
    assert rows(app, SchoolBbMaterial)[0].path == "Week 5"


def test_a_new_blackboard_sync_replaces_the_old_rows(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})
    data = blackboard_payload()
    data["courses"][0]["announcements"] = []

    sync(app, key, {"status": "ok", "data": data})

    assert rows(app, SchoolBbAnnouncement) == []
    assert len(rows(app, SchoolBbCourse)) == 1


def test_a_failed_blackboard_part_keeps_the_old_rows(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})

    status = sync(app, key, {"status": "failed", "error_code": "source_changed", "error_message": "Unexpected"})

    assert status == "partial"
    assert len(rows(app, SchoolBbAnnouncement)) == 1


def test_blackboard_changes_reach_the_feed(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})
    data = blackboard_payload()
    data["courses"][0]["announcements"].append({
        "bb_id": "_502_1", "title": "Room change", "text": "Moved to A2.508.",
        "posted_at": "2026-09-29T02:00:00+00:00", "url": "https://blackboard.hcmiu.edu.vn/x"})

    sync(app, key, {"status": "ok", "data": data})

    summaries = [c.summary for c in rows(app, SchoolChange) if c.section == "blackboard"]
    assert summaries[0].startswith("Blackboard loaded: 1 course")
    assert summaries[-1] == "New announcement · Web Application Development: Room change"
