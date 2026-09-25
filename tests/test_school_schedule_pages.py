"""Timetable, exams, tuition and the School home page. Times in the database are
naive UTC; pages show Vietnam time (UTC+7)."""

from datetime import date, datetime

import pytest
from bs4 import BeautifulSoup

from app.extensions import db
from app.school.models import SchoolChange, SchoolClassMeeting, SchoolCourse, SchoolExam, SchoolSyncRun, SchoolTuition
from tests.helpers import login, make_user, register


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)  # user 1
    return client


def add_course(app, user_id, code, name, meetings, term="20261"):
    with app.app_context():
        course = SchoolCourse(user_id=user_id, term_code=term, course_code=code, course_name=name)
        course.meetings = [
            SchoolClassMeeting(user_id=user_id, start_at=start, end_at=end, room=room) for start, end, room in meetings
        ]
        db.session.add(course)
        db.session.commit()


def add_exam(app, user_id, code, name, start, room="A1.101", exam_type="final"):
    with app.app_context():
        db.session.add(SchoolExam(user_id=user_id, term_code="20261", course_code=code, course_name=name,
                                  exam_type=exam_type, start_at=start, room=room))
        db.session.commit()


def page(browser, url):
    response = browser.get(url)
    assert response.status_code == 200
    return response.get_data(as_text=True)


# Tue 29/09/2026 08:00-10:30 in Vietnam = 01:00-03:30 UTC
WEB_TUESDAY = (datetime(2026, 9, 29, 1, 0), datetime(2026, 9, 29, 3, 30), "A2.508")


@pytest.mark.parametrize("path", ["/school/timetable", "/school/exams", "/school/tuition"])
def test_schedule_pages_need_login(client, path):
    assert client.get(path).status_code == 302


FEED = "/school/api/calendar"
NEXT_WEEK = {"start": "2026-09-28T00:00:00Z", "end": "2026-10-05T00:00:00Z"}  # as FullCalendar sends them


def feed(browser, **params):
    response = browser.get(FEED, query_string=params)
    assert response.status_code == 200
    return response.get_json()


def test_the_calendar_feed_gives_classes_in_vietnam_time(app, browser):
    add_course(app, 1, "IT093IU", "Web Application Development", [WEB_TUESDAY])

    assert feed(browser, **NEXT_WEEK) == [{
        "title": "Web Application Development",
        "start": "2026-09-29T08:00:00",
        "end": "2026-09-29T10:30:00",
        "classNames": ["event-class"],
        "extendedProps": {"kind": "class", "code": "IT093IU", "room": "A2.508"},
    }]


def test_the_calendar_feed_has_only_my_classes(app, browser):
    other = make_user(app, email="binh@example.com")
    add_course(app, other, "BA001IU", "Binh's Business Course", [WEB_TUESDAY])

    assert feed(browser, **NEXT_WEEK) == []


def test_a_class_early_on_monday_in_vietnam_belongs_to_that_monday(app, browser):
    # Mon 05/10/2026 06:00 in Vietnam is still Sunday 04/10 23:00 in UTC.
    add_course(app, 1, "MA001IU", "Early Maths", [(datetime(2026, 10, 4, 23, 0), datetime(2026, 10, 5, 0, 30), "A1.1")])

    assert feed(browser, **NEXT_WEEK) == []
    [event] = feed(browser, start="2026-10-05T00:00:00Z", end="2026-10-12T00:00:00Z")
    assert event["start"] == "2026-10-05T06:00:00"


def test_exams_are_in_the_calendar_with_their_own_colour(app, browser):
    add_exam(app, 1, "IT093IU", "Web Application Development", datetime(2026, 9, 30, 1, 0))

    [event] = feed(browser, **NEXT_WEEK)

    assert (event["title"], event["start"], event["classNames"]) == (
        "Final exam: Web Application Development", "2026-09-30T08:00:00", ["event-exam"],
    )


@pytest.mark.parametrize(
    "params",
    [{}, {"start": "not-a-date", "end": "2026-10-05"}, {"start": "2026-10-05", "end": "2026-09-28"},
     {"start": "2026-01-01", "end": "2026-12-31"}],
    ids=["missing", "not-a-date", "end-before-start", "too-long"],
)
def test_the_calendar_feed_refuses_bad_ranges(browser, params):
    assert browser.get(FEED, query_string=params).status_code == 400


def test_the_calendar_feed_needs_login(client):
    assert client.get(FEED, query_string=NEXT_WEEK).status_code == 302


def test_the_timetable_page_loads_the_pinned_calendar_script(browser):
    html = page(browser, "/school/timetable")

    assert 'id="calendar"' in html
    assert 'data-feed="/school/api/calendar"' in html
    assert "fullcalendar@6.1.21/index.global.min.js" in html
    assert 'integrity="sha384-' in html


def test_the_exams_page_lists_upcoming_exams(app, browser):
    add_exam(app, 1, "IT093IU", "Web Application Development", datetime(2099, 12, 12, 1, 0), room="A1.309")

    html = page(browser, "/school/exams")

    assert "Web Application Development" in html
    assert "12/12/2099" in html
    assert "08:00" in html
    assert "A1.309" in html


def test_the_exams_page_says_when_nothing_is_published(browser):
    assert "No exams published yet" in page(browser, "/school/exams")


def test_the_tuition_page_shows_balance_and_due_date(app, browser):
    with app.app_context():
        db.session.add(SchoolTuition(user_id=1, term_code="20261", amount_due=12500000, amount_paid=0,
                                     balance=12500000, due_date=date(2026, 10, 15), status_text="Chưa đóng", items=[]))
        db.session.commit()

    html = page(browser, "/school/tuition")

    assert "12,500,000" in html
    assert "15/10/2026" in html


def test_the_tuition_page_links_to_the_iu_payment_site_in_a_new_tab(browser):
    link = BeautifulSoup(page(browser, "/school/tuition"), "html.parser").find(
        "a", href="https://iupay.hcmiu.edu.vn/search/dhqt")

    assert link is not None
    assert link["target"] == "_blank"
    assert {"noopener", "noreferrer"} <= set(link["rel"])


def test_the_tuition_page_says_when_nothing_is_synced(browser):
    assert "No tuition information yet" in page(browser, "/school/tuition")


def test_school_home_shows_todays_classes_and_what_changed(app, browser, monkeypatch):
    add_course(app, 1, "IT093IU", "Web Application Development", [WEB_TUESDAY])
    with app.app_context():
        run = SchoolSyncRun(user_id=1, trigger="manual", started_at=datetime(2026, 9, 28), status="success")
        db.session.add(run)
        db.session.flush()
        db.session.add(SchoolChange(user_id=1, sync_run_id=run.id, section="timetable", kind="changed",
                                    summary="IT093IU Web Application Development: room A2.307 → A2.508"))
        db.session.commit()
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 29, 0, 30))  # Tue 07:30 in Vietnam

    html = page(browser, "/school/")

    assert "Today" in html
    assert "08:00–10:30" in html
    assert "room A2.307 → A2.508" in html


def test_school_home_does_not_show_other_users_changes(app, browser):
    other = make_user(app, email="binh@example.com")
    with app.app_context():
        run = SchoolSyncRun(user_id=other, trigger="manual", started_at=datetime(2026, 9, 28), status="success")
        db.session.add(run)
        db.session.flush()
        db.session.add(SchoolChange(user_id=other, sync_run_id=run.id, section="exams", kind="added",
                                    summary="Binh's secret exam"))
        db.session.commit()

    assert "Binh" not in page(browser, "/school/")
