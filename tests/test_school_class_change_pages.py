"""Classes changed by Blackboard announcements, in the calendar feed and on the Overview.
Times in the database are naive UTC; Vietnam is UTC+7."""

from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbCourse, SchoolClassMeeting, SchoolCourse
from tests.helpers import make_user, register

BB = "https://blackboard.hcmiu.edu.vn/x"
PROBABILITY = "Probability, Statistic & Random Process"
# Thursdays 13:15-15:45 in Vietnam = 06:15-08:45 UTC
THU_24 = (datetime(2026, 9, 24, 6, 15), datetime(2026, 9, 24, 8, 45), "A2.407")
THU_01 = (datetime(2026, 10, 1, 6, 15), datetime(2026, 10, 1, 8, 45), "A2.407")
POSTED = datetime(2026, 9, 20, 2, 0)
WEEK = {"start": "2026-09-21", "end": "2026-09-28"}  # Mon 21/09 - Sun 27/09


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)  # user 1
    return client


def add_timetable(app, user_id, code, name, meetings):
    with app.app_context():
        course = SchoolCourse(user_id=user_id, term_code="20261", course_code=code, course_name=name)
        course.meetings = [SchoolClassMeeting(user_id=user_id, start_at=s, end_at=e, room=r) for s, e, r in meetings]
        db.session.add(course)
        db.session.commit()


def announce(app, user_id, code, title, text="", posted_at=POSTED):
    with app.app_context():
        course = SchoolBbCourse(user_id=user_id, bb_id=f"_{code}_1", course_code=code, name=f"{code} on Blackboard",
                                url=BB)
        course.announcements = [SchoolBbAnnouncement(user_id=user_id, bb_id="_1_1", title=title, text=text,
                                                     posted_at=posted_at, url=BB)]
        db.session.add(course)
        db.session.commit()
        return course.id


def classes(browser, **week):
    events = browser.get("/school/api/calendar", query_string=week or WEEK).get_json()
    return [e for e in events if e["extendedProps"]["kind"] == "class"]


def makeups(browser):
    return [e for e in classes(browser) if e["extendedProps"].get("change") == "makeup"]


def test_an_online_class_is_purple_and_links_to_the_announcement(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24, THU_01])
    course_id = announce(app, 1, "MA026IU", "ONLINE CLASS ON SEPTEMBER 24", posted_at=datetime(2026, 9, 23, 16, 7))

    [event] = classes(browser)

    assert event["title"] == f"Online: {PROBABILITY}"
    assert (event["classNames"], event["extendedProps"]["room"], event["extendedProps"]["change"]) == (
        ["event-changed"], "Online", "online")
    assert event["url"] == f"/school/courses/{course_id}"
    [next_week] = classes(browser, start="2026-09-28", end="2026-10-05")
    assert next_week["classNames"] == ["event-class"] and "url" not in next_week


def test_a_cancelled_class_stays_in_its_slot_greyed(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Cancel class on September 24")

    [event] = classes(browser)

    assert (event["title"], event["classNames"], event["start"]) == (
        f"Cancelled: {PROBABILITY}", ["event-cancelled"], "2026-09-24T13:15:00")
    assert event["extendedProps"]["room"] == "A2.407"


def test_a_make_up_class_with_a_time_is_added(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on Saturday 26/9 from 8:00 to 9:40 in A2.401")

    assert [(e["title"], e["start"], e["end"], e["extendedProps"]["room"]) for e in makeups(browser)] == [
        (f"Make-up: {PROBABILITY}", "2026-09-26T08:00:00", "2026-09-26T09:40:00", "A2.401")]
    assert len(classes(browser)) == 2  # the normal Thursday class is still there


def test_a_make_up_class_without_an_end_lasts_as_long_as_the_usual_class(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24, THU_01])
    announce(app, 1, "MA026IU", "Make-up class on 26/9 at 13h15")

    assert [(e["start"], e["end"]) for e in makeups(browser)] == [("2026-09-26T13:15:00", "2026-09-26T15:45:00")]


def test_a_make_up_class_ending_before_it_starts_uses_the_usual_length(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on 26/9 from 13:15 to 9:40")

    assert [(e["start"], e["end"]) for e in makeups(browser)] == [("2026-09-26T13:15:00", "2026-09-26T15:45:00")]


def test_a_make_up_class_without_a_time_is_an_all_day_note(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Học bù ngày 26/9")

    [note] = [e for e in classes(browser) if e.get("allDay")]

    assert (note["title"], note["start"], note["classNames"]) == (
        f"Make-up class: {PROBABILITY} (see announcement)", "2026-09-26", ["event-changed"])


def test_a_make_up_class_at_the_time_of_a_class_is_not_added_twice(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "MA026IU", "Make-up class on 24/9 at 13:15")

    assert len(classes(browser)) == 1


def test_changes_need_a_class_of_that_course_on_that_day(app, browser):
    # The real "Logistics Reminder": "Starting the week of 12/10, lectures will be taught online" is read as
    # Mon 12/10, and this Saturday course has no class that day.
    sat_10 = (datetime(2026, 10, 10, 6, 15), datetime(2026, 10, 10, 8, 45), "A1.603")
    sat_17 = (datetime(2026, 10, 17, 6, 15), datetime(2026, 10, 17, 8, 45), "A1.603")
    add_timetable(app, 1, "IT007WE", "Skills for Communicating Information", [sat_10, sat_17])
    announce(app, 1, "IT007WE", "Logistics Reminder",
             "Our last in-person lecture is on 10/10. Starting the week of 12/10 , lectures will be taught "
             "online by Dr. Tuan Nguyen via MS Teams.", posted_at=datetime(2026, 9, 22, 3, 59))

    events = classes(browser, start="2026-10-05", end="2026-10-19")

    assert [e["classNames"] for e in events] == [["event-class"], ["event-class"]]


def test_a_make_up_for_a_course_not_in_the_timetable_is_ignored(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, 1, "EN011IU", "Make-up class on 26/9 at 8:00")

    assert len(classes(browser)) == 1


def test_another_users_announcements_never_change_my_classes(app, browser):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    announce(app, make_user(app, email="binh@example.com"), "MA026IU", "ONLINE CLASS ON SEPTEMBER 24")

    [event] = classes(browser)

    assert event["classNames"] == ["event-class"]


def test_the_overview_shows_todays_online_class(app, browser, monkeypatch):
    add_timetable(app, 1, "MA026IU", PROBABILITY, [THU_24])
    course_id = announce(app, 1, "MA026IU", "ONLINE CLASS ON SEPTEMBER 24", posted_at=datetime(2026, 9, 23, 16, 7))
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 24, 0, 30))  # Thu 07:30 in Vietnam

    soup = BeautifulSoup(browser.get("/school/").get_data(as_text=True), "html.parser")
    [item] = soup.select("li.item-changed")

    assert "Online" in item.select_one(".badge-changed").get_text()
    assert item.find("a", string=lambda s: s and "See announcement" in s)["href"] == f"/school/courses/{course_id}"


def test_the_timetable_legend_explains_the_new_colours(browser):
    html = browser.get("/school/timetable").get_data(as_text=True)

    assert "Online / make-up" in html and "Cancelled" in html
