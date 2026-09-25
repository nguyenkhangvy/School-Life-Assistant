from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse, SchoolBbMaterial
from tests.helpers import make_user, register

BB = "https://blackboard.hcmiu.edu.vn/x"


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)  # user 1
    return client


def add_course(app, user_id, name="Web Application Development", assignments=(), announcements=(), materials=()):
    with app.app_context():
        course = SchoolBbCourse(user_id=user_id, bb_id=f"_{name[:3]}_1", course_code="IT093IU", name=name, url=BB)
        course.assignments = [SchoolBbAssignment(user_id=user_id, url=BB, **a) for a in assignments]
        course.announcements = [SchoolBbAnnouncement(user_id=user_id, url=BB, **a) for a in announcements]
        course.materials = [SchoolBbMaterial(user_id=user_id, url=BB, **m) for m in materials]
        db.session.add(course)
        db.session.commit()
        return course.id


def page(browser, url):
    response = browser.get(url)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_the_courses_page_lists_only_my_courses(app, browser):
    add_course(app, 1)
    add_course(app, make_user(app, email="binh@example.com"), name="Binh's Course")

    html = page(browser, "/school/courses")

    assert "Web Application Development" in html
    assert "Binh" not in html


def test_someone_elses_course_page_is_404(app, browser):
    other = add_course(app, make_user(app, email="binh@example.com"), name="Binh's Course")

    assert browser.get(f"/school/courses/{other}").status_code == 404


def test_the_course_page_shows_all_four_parts_with_escaped_text(app, browser):
    course_id = add_course(
        app, 1,
        announcements=[{"bb_id": "a1", "title": "Heads up", "text": "<script>alert(1)</script> No class Thursday",
                        "posted_at": datetime(2026, 9, 28, 2, 0)}],
        assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "graded",
                      "score": 8.5, "points_possible": 10.0, "feedback": "Good work"}],
        materials=[{"bb_id": "m1", "title": "Week 5 slides.pdf", "kind": "file", "path": "Week 5",
                    "created_at": datetime(2026, 9, 28, 1, 0)}],
    )

    html = page(browser, f"/school/courses/{course_id}")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    for text in ("Heads up", "Lab 3", "Fri 02/10 23:59", "8.5/10", "Good work", "Week 5 slides.pdf"):
        assert text in html
    links = BeautifulSoup(html, "html.parser").find_all("a", string=lambda s: s and "Open in Blackboard" in s)
    assert links and all(l["target"] == "_blank" and "noopener" in l["rel"] for l in links)


def test_a_deadline_at_2359_vietnam_time_is_in_the_calendar_on_that_day(app, browser):
    add_course(app, 1, assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59),
                                     "status": "not_graded"}])

    events = browser.get("/school/api/calendar", query_string={"start": "2026-09-28", "end": "2026-10-05"}).get_json()

    [due] = [e for e in events if e["extendedProps"]["kind"] == "due"]
    assert (due["start"], due["allDay"], due["classNames"]) == ("2026-10-02", True, ["event-due"])
    assert due["title"] == "Due 23:59: Lab 3 · Web Application Development"


def test_a_deadline_just_after_midnight_belongs_to_the_next_vietnam_day(app, browser):
    # Sat 03/10 00:30 in Vietnam is still Fri 02/10 17:30 in UTC.
    add_course(app, 1, assignments=[{"bb_id": "x1", "name": "Quiz", "due_at": datetime(2026, 10, 2, 17, 30),
                                     "status": "not_graded"}])

    events = browser.get("/school/api/calendar", query_string={"start": "2026-09-28", "end": "2026-10-05"}).get_json()

    assert [e["start"] for e in events if e["extendedProps"]["kind"] == "due"] == ["2026-10-03"]


def test_overview_shows_due_soon_and_latest_announcements(app, browser, monkeypatch):
    add_course(app, 1,
               assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "not_graded"},
                            {"bb_id": "x2", "name": "Far away", "due_at": datetime(2026, 11, 30, 16, 59), "status": "not_graded"}],
               announcements=[{"bb_id": f"a{i}", "title": f"Note {i}", "text": "t", "posted_at": datetime(2026, 9, 20 + i, 2, 0)}
                              for i in range(5)])
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 29, 0, 30))

    html = page(browser, "/school/")

    assert "Due soon" in html and "Lab 3" in html and "Far away" not in html
    assert "Note 4" in html and "Note 2" in html and "Note 1" not in html  # the 3 newest
