import os

from app.config import load_config

# Tests use a throwaway in-memory SQLite database by default.
# CI sets TEST_DATABASE_URL to a real MySQL database.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


def make_config(**overrides):
    config = load_config({"SECRET_KEY": "test-secret", "DATABASE_URL": TEST_DATABASE_URL})
    config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    config.update(overrides)
    return config


def register(client, email="an@example.com", display_name="An", password="correct-horse", confirm=None):
    return client.post(
        "/auth/register",
        data={
            "email": email,
            "display_name": display_name,
            "password": password,
            "confirm": password if confirm is None else confirm,
        },
    )


def login(client, email="an@example.com", password="correct-horse", next_url=None):
    query = {} if next_url is None else {"next": next_url}
    return client.post("/auth/login", query_string=query, data={"email": email, "password": password})


def logout(client):
    return client.post("/auth/logout")


def make_user(app, email="an@example.com", display_name="An"):
    from app.auth.models import User
    from app.extensions import db

    with app.app_context():
        user = User(email=email, display_name=display_name)
        user.set_password("correct-horse")
        db.session.add(user)
        db.session.commit()
        return user.id


def make_device(app, user_id, name="My laptop"):
    """Create a sync device the way the Devices page does; returns the raw key."""
    from app.extensions import db
    from app.school.services.devices import create_device

    with app.app_context():
        _, raw_key = create_device(user_id, name)
        db.session.commit()
        return raw_key


def api(client, method, path, key=None, json=None, **kwargs):
    headers = {} if key is None else {"Authorization": f"Bearer {key}"}
    return client.open(f"/api/school/sync{path}", method=method, headers=headers, json=json, **kwargs)


# A complete, valid upload from the agent. Times are Vietnam time (+07:00).
def full_payload():
    return {
        "schema_version": 1,
        "timetable": {
            "status": "ok",
            "data": {
                "term_code": "20261",
                "term_name": "Semester 1, 2026-2027",
                "courses": [
                    {
                        "course_code": "IT093IU",
                        "course_name": "Web Application Development",
                        "group": "01",
                        "credits": 4,
                        "lecturer": "Nguyen Van A",
                        "meetings": [
                            {
                                "start_at": "2026-09-29T08:00:00+07:00",
                                "end_at": "2026-09-29T10:30:00+07:00",
                                "room": "A2.307",
                            }
                        ],
                    }
                ],
            },
        },
        "exams": {
            "status": "ok",
            "data": {
                "term_code": "20261",
                "exams": [
                    {
                        "course_code": "IT093IU",
                        "course_name": "Web Application Development",
                        "exam_type": "final",
                        "start_at": "2026-12-12T08:00:00+07:00",
                        "duration_min": 90,
                        "room": "A1.101",
                    }
                ],
            },
        },
        "tuition": {
            "status": "ok",
            "data": {
                "term_code": "20261",
                "amount_due": 12500000,
                "amount_paid": 0,
                "balance": 12500000,
                "due_date": "2026-10-15",
                "status_text": "Chưa đóng",
            },
        },
    }


# A valid Blackboard section as the agent uploads it.
BB = "https://blackboard.hcmiu.edu.vn"


def blackboard_payload():
    return {
        "courses": [{
            "bb_id": "_101_1", "course_code": "IT093IU", "name": "Web Application Development",
            "url": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
            "announcements": [{"bb_id": "_501_1", "title": "No class on Thursday", "text": "Class is cancelled.",
                               "posted_at": "2026-09-28T02:00:00+00:00", "url": f"{BB}/x"}],
            "assignments": [{"bb_id": "_701_1", "name": "Lab 3", "due_at": "2026-10-02T16:59:00+00:00",
                             "points_possible": 10, "score": 8.5, "grade_text": "8.5", "status": "graded",
                             "feedback": "Good work", "url": f"{BB}/x"}],
            "materials": [{"bb_id": "_902_1", "title": "Week 5 slides.pdf", "kind": "file", "path": "Week 5",
                           "created_at": "2026-09-28T01:00:00+00:00", "url": f"{BB}/x"}],
        }],
    }
