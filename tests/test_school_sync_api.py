import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.school.models import SchoolSyncDevice, SchoolSyncRun
from app.timeutil import utcnow
from tests.helpers import api, full_payload, make_config, make_device, make_user


@pytest.fixture
def key(app):
    return make_device(app, make_user(app))


def _device(app):
    with app.app_context():
        return db.session.execute(select(SchoolSyncDevice)).scalar_one()


def _runs(app):
    with app.app_context():
        return db.session.execute(select(SchoolSyncRun).order_by(SchoolSyncRun.id)).scalars().all()


# ---- Device keys -------------------------------------------------------------


def test_device_key_is_stored_only_as_its_sha256_hash(app, key):
    device = _device(app)

    assert device.token_hash == hashlib.sha256(key.encode()).hexdigest()
    assert key not in (device.name, device.token_hash)


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer not-a-real-key", "Basic dXNlcjpwYXNz", "Bearer "],
    ids=["missing", "wrong-key", "wrong-scheme", "empty-key"],
)
def test_requests_without_a_valid_device_key_get_401(app, key, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}

    response = app.test_client().get("/api/school/sync/check", headers=headers)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid_device_key"}


def test_a_cancelled_device_key_gets_401(app, key):
    with app.app_context():
        device = db.session.execute(select(SchoolSyncDevice)).scalar_one()
        device.revoked_at = utcnow()
        db.session.commit()

    assert api(app.test_client(), "GET", "/check", key).status_code == 401


# ---- Check -------------------------------------------------------------------


def test_first_check_says_due_and_records_the_check_in(app, key):
    response = api(app.test_client(), "GET", "/check", key)

    assert response.status_code == 200
    assert response.get_json() == {"due": True, "reason": "never", "interval_hours": 12}
    assert _device(app).last_seen_at is not None


# ---- Start -------------------------------------------------------------------


def test_start_creates_a_running_run_and_check_then_says_running(app, key):
    client = app.test_client()

    response = api(client, "POST", "/runs", key, json={"trigger": "scheduled"})

    assert response.status_code == 201
    [run] = _runs(app)
    assert response.get_json() == {"run_id": run.id}
    assert (run.status, run.trigger, run.device_id) == ("running", "scheduled", _device(app).id)
    assert api(client, "GET", "/check", key).get_json()["reason"] == "running"


def test_a_second_start_while_one_is_running_gets_409(app, key):
    client = app.test_client()
    api(client, "POST", "/runs", key, json={"trigger": "scheduled"})

    response = api(client, "POST", "/runs", key, json={"trigger": "manual"})

    assert response.status_code == 409
    assert len(_runs(app)) == 1


def test_start_closes_a_stuck_run_as_timed_out(app, key):
    client = app.test_client()
    api(client, "POST", "/runs", key, json={"trigger": "scheduled"})
    with app.app_context():
        stuck = db.session.execute(select(SchoolSyncRun)).scalar_one()
        stuck.started_at = utcnow() - timedelta(minutes=20)
        db.session.commit()

    response = api(client, "POST", "/runs", key, json={"trigger": "manual"})

    assert response.status_code == 201
    old, new = _runs(app)
    assert (old.status, old.error_code, old.finished_at is not None) == ("failed", "timeout", True)
    assert new.status == "running"


def test_start_rejects_an_unknown_trigger(app, key):
    response = api(app.test_client(), "POST", "/runs", key, json={"trigger": "whenever"})

    assert response.status_code == 422
    assert _runs(app) == []


# ---- Finish ------------------------------------------------------------------


def _start(client, key):
    return api(client, "POST", "/runs", key, json={"trigger": "scheduled"}).get_json()["run_id"]


def test_finish_marks_the_run_with_its_overall_status(app, key):
    client = app.test_client()
    run_id = _start(client, key)

    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=full_payload())

    assert response.status_code == 200
    assert response.get_json() == {"status": "success"}
    [run] = _runs(app)
    assert run.status == "success"
    assert run.finished_at is not None


def test_an_invalid_upload_gets_422_and_leaves_the_run_running(app, key):
    client = app.test_client()
    run_id = _start(client, key)
    payload = full_payload()
    payload["timetable"]["data"]["student_id"] = "ITITIU20001"

    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"] == "invalid_payload"
    assert "ITITIU20001" not in response.get_data(as_text=True)
    assert _runs(app)[0].status == "running"


def test_a_device_cannot_finish_another_users_run(app, key):
    client = app.test_client()
    run_id = _start(client, key)
    other_key = make_device(app, make_user(app, email="binh@example.com"))

    response = api(client, "POST", f"/runs/{run_id}/finish", other_key, json=full_payload())

    assert response.status_code == 404
    assert _runs(app)[0].status == "running"


def test_a_finished_run_cannot_be_finished_again(app, key):
    client = app.test_client()
    run_id = _start(client, key)
    api(client, "POST", f"/runs/{run_id}/finish", key, json=full_payload())

    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=full_payload())

    assert response.status_code == 409


def test_an_oversized_upload_gets_413(app, key):
    client = app.test_client()
    run_id = _start(client, key)
    payload = full_payload()
    payload["tuition"]["data"]["status_text"] = "x" * 1_100_000

    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)

    assert response.status_code == 413


def test_the_api_works_with_csrf_protection_switched_on():
    app = create_app(make_config(WTF_CSRF_ENABLED=True))
    with app.app_context():
        db.create_all()
    key = make_device(app, make_user(app))

    response = api(app.test_client(), "POST", "/runs", key, json={"trigger": "manual"})

    assert response.status_code == 201
    with app.app_context():
        db.drop_all()
