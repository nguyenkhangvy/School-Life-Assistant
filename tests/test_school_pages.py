import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolSyncDevice, SchoolSyncRun
from tests.helpers import api, login, make_device, make_user, register

KEY_PATTERN = re.compile(r"sla_[A-Za-z0-9_\-]{40,}")


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)
    return client


def add_device(browser, name="My laptop"):
    response = browser.post("/school/devices", data={"name": name})
    match = KEY_PATTERN.search(response.get_data(as_text=True))
    return response, match.group(0) if match else None


def devices(app):
    with app.app_context():
        return db.session.execute(select(SchoolSyncDevice).order_by(SchoolSyncDevice.id)).scalars().all()


@pytest.mark.parametrize("path", ["/school/", "/school/devices"])
def test_school_pages_need_login(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


def test_a_new_device_key_is_shown_once_and_works(app, browser):
    response, key = add_device(browser)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert key is not None
    assert api(app.test_client(), "GET", "/check", key).status_code == 200
    assert key not in browser.get("/school/devices").get_data(as_text=True)


def test_a_device_needs_a_name(app, browser):
    response, key = add_device(browser, name="   ")

    assert key is None
    assert devices(app) == []


def test_cancelling_a_device_stops_its_key(app, browser):
    _, key = add_device(browser)
    device_id = devices(app)[0].id

    response = browser.post(f"/school/devices/{device_id}/revoke")

    assert response.status_code == 302
    assert devices(app)[0].revoked_at is not None
    assert api(app.test_client(), "GET", "/check", key).status_code == 401


def test_a_cancelled_device_disappears_from_the_list(app, browser):
    add_device(browser, name="Old laptop")
    add_device(browser, name="New laptop")
    old_id = devices(app)[0].id

    browser.post(f"/school/devices/{old_id}/revoke")
    browser.get("/school/devices")  # shows (and clears) the "can no longer sync" message
    page = browser.get("/school/devices").get_data(as_text=True)

    assert "Old laptop" not in page
    assert "New laptop" in page


def test_renaming_a_device(app, browser):
    add_device(browser)
    device_id = devices(app)[0].id

    browser.post(f"/school/devices/{device_id}/rename", data={"name": "Dorm laptop"})

    assert devices(app)[0].name == "Dorm laptop"


@pytest.mark.parametrize("action, data", [("revoke", {}), ("rename", {"name": "Mine now"})])
def test_nobody_can_change_another_users_device(app, browser, action, data):
    other_key = make_device(app, make_user(app, email="binh@example.com"), name="Binh's laptop")
    other_id = devices(app)[0].id

    response = browser.post(f"/school/devices/{other_id}/{action}", data=data)

    assert response.status_code == 404
    assert (devices(app)[0].name, devices(app)[0].revoked_at) == ("Binh's laptop", None)
    assert api(app.test_client(), "GET", "/check", other_key).status_code == 200


def test_the_devices_page_lists_only_my_devices(app, browser):
    make_device(app, make_user(app, email="binh@example.com"), name="Binh's laptop")
    add_device(browser, name="An's laptop")

    page = browser.get("/school/devices").get_data(as_text=True)

    assert "An&#39;s laptop" in page
    assert "Binh" not in page


def test_sync_now_makes_the_next_check_due(app, browser):
    _, key = add_device(browser)
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "scheduled"}).get_json()["run_id"]
    api(client, "POST", f"/runs/{run_id}/finish", key,
        json={"error_code": "network", "error_message": "EduSoft timed out"})
    with app.app_context():
        # Pretend the failed run was 10 minutes ago, past the 5-minute gap.
        run = db.session.get(SchoolSyncRun, run_id)
        run.started_at -= timedelta(minutes=10)
        db.session.commit()

    response = browser.post("/school/sync-now")

    assert response.status_code == 302
    assert api(client, "GET", "/check", key).get_json()["reason"] == "requested"
    assert "waiting for your laptop" in browser.get("/school/").get_data(as_text=True)


def test_school_home_shows_the_setup_hint_before_any_device(browser):
    page = browser.get("/school/").get_data(as_text=True)

    assert "Devices page" in page


def test_another_user_logging_in_sees_their_own_status(app, browser):
    add_device(browser)
    make_user(app, email="binh@example.com")
    other = app.test_client()
    login(other, email="binh@example.com")

    assert "Not set up yet" in other.get("/school/").get_data(as_text=True)


def test_school_home_shows_a_line_per_system(app, browser):
    _, key = add_device(browser)
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "scheduled"}).get_json()["run_id"]
    from tests.helpers import full_payload
    payload = full_payload()
    payload["blackboard"] = {"status": "failed", "error_code": "bad_credentials", "error_message": "rejected"}
    api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)

    page = browser.get("/school/").get_data(as_text=True)

    assert "EduSoft" in page and "Blackboard" in page
    assert "sla-agent setup --blackboard" in page
