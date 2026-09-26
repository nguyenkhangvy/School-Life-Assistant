"""Reading class changes from Blackboard announcements. posted_at values are naive UTC."""

import unicodedata
from datetime import date, datetime, time

import pytest

from app.school.services import class_changes
from app.school.services.class_changes import Announced, ClassChange, changes_from, read_announcement

# Real announcements from September 2026, with Teams codes and links shortened.
PROBABILITY_ONLINE = (
    "ONLINE CLASS ON SEPTEMBER 24",
    "Dear all, The class on September 24 is online on MS TEAMS. Please use the following code to access the class.",
    datetime(2026, 9, 23, 16, 7),
)
WEB_ONLINE = (
    "Online Class Notification – Web Application – 22 September 2026",
    "Dear Students, Please be informed that our Web Application class will be conducted online via Microsoft "
    "Teams. Date: Tuesday, 22 September 2026 Time: From 8:00 AM Platform: Microsoft Teams Online Class Link: "
    "https://teams.microsoft.com/l/meetup-join/19%3ameeting_x%40thread.v2/0?context=%7b%22Tid%22%3a%2212-10%22",
    datetime(2026, 9, 15, 16, 0),
)
PHYSICS_ONLINE = (
    "Link học online sáng thứ Sáu, 18/9/2026, 8g00-9g40",
    "Link: Physics 4 Friday, September 18 Time zone: Asia/Ho_Chi_Minh Google Meet joining info "
    "Video call link: https://meet.google.com/abc-defg-hij",
    datetime(2026, 9, 17, 9, 30),
)
PROBABILITY_CANCEL = (
    "Cancel class on September 17",
    "The class this week on September 17 will be canceled. The makeup schedule will be announced later",
    datetime(2026, 9, 15, 2, 36),
)
LOGISTICS = (
    "Logistics Reminder",
    "Lecture attendance: You will attend the first five lectures with me in person in Room A1.603 , with our "
    "last in-person lecture on 10/10. Attendance will be taken during these sessions. Starting the week of "
    "12/10 , lectures will be taught online by Dr. Tuan Nguyen via MS Teams. Please register your group in "
    "SkillsGroupTerm1-26-27_Sat.xlsx , available on our MS Teams Channel.",
    datetime(2026, 9, 22, 3, 59),
)
POSTED = datetime(2026, 9, 20, 2, 0)  # Sun 20/09 09:00 in Vietnam


@pytest.mark.parametrize("announcement, expected", [
    (PROBABILITY_ONLINE, {Announced("online", date(2026, 9, 24))}),
    (WEB_ONLINE, {Announced("online", date(2026, 9, 22))}),
    (PHYSICS_ONLINE, {Announced("online", date(2026, 9, 18))}),
    (PROBABILITY_CANCEL, {Announced("cancelled", date(2026, 9, 17))}),
])
def test_the_real_announcements(announcement, expected):
    assert set(read_announcement(*announcement)) == expected


def test_only_a_sentence_with_a_change_word_counts():
    # "in-person ... on 10/10" has no change word. "Starting the week of 12/10 ... online" is read as the
    # single day 12/10; ranges are out of scope (and the course has no class that Monday).
    assert read_announcement(*LOGISTICS) == [Announced("online", date(2026, 10, 12))]


@pytest.mark.parametrize("title", [
    "Online class on Sept. 24",
    "Online class on 24th September",
    "Online class on September 24th, 2026",
    "Lớp học trực tuyến ngày 24 tháng 9 năm 2026",
    "The lecture on 24/09 is online",
    unicodedata.normalize("NFD", "Lớp học trực tuyến ngày 24/9"),
])
def test_date_formats_and_vietnamese(title):
    assert read_announcement(title, "", POSTED) == [Announced("online", date(2026, 9, 24))]


@pytest.mark.parametrize("title", ["Lớp nghỉ ngày 24/09", "Hủy buổi học 24-9-2026", "No class on Sep 24",
                                   "Class on 24/9 is cancelled", "Nghỉ học ngày 24/9"])
def test_cancel_words(title):
    assert read_announcement(title, "", POSTED) == [Announced("cancelled", date(2026, 9, 24))]


@pytest.mark.parametrize("title, kind", [
    ("Classes on 24/9 are cancelled", "cancelled"),
    ("Class cancellation on 24/9", "cancelled"),
    ("We are cancelling the lecture on 24/9", "cancelled"),
    ("Lectures on 24/9 will be online", "online"),
])
def test_plurals_and_word_forms(title, kind):
    assert read_announcement(title, "", POSTED) == [Announced(kind, date(2026, 9, 24))]


@pytest.mark.parametrize("title", [
    "Submit your report online by 24/9",  # no class word
    "The class on September 10 was online",  # before the posting day
    "Online class soon",  # no date
    "Online class from 10:30-11:45 in A2.401",  # times are not dates
    "Online class, see https://example.com/10-11/12",  # dates inside links are ignored
    "Tell your classmates to submit online by 24/9",  # "classmates" is not a class word
    "The classroom booking system goes online on 24/9",  # nor is "classroom"
    "Nộp bài trực tuyến trước ngày 24/9 cho môn học",  # a deadline, not a class
])
def test_what_changes_nothing(title):
    assert read_announcement(title, "", POSTED) == []


@pytest.mark.parametrize("title, expected", [
    ("No class on Thursday 24/9 (8-10)", [Announced("cancelled", date(2026, 9, 24))]),
    ("The class on Thursday 24/9 will be online, 8-10am", [Announced("online", date(2026, 9, 24))]),
    ("Học bù ngày 3/10, tiết 10-12", [Announced("makeup", date(2026, 10, 3))]),
])
def test_hour_and_period_ranges_are_not_dates(title, expected):
    assert read_announcement(title, "", POSTED) == expected


def test_paragraphs_from_blackboard_stay_separate_sentences():
    from sla_agent.parsers.blackboard import html_to_text

    html = ("<p>our class on 24/9 will be online via MS Teams</p>"
            "<p>Reminder: Homework 2 is due in class on 1/10</p>")

    assert read_announcement("Notice", html_to_text(html, 5000), POSTED) == [Announced("online", date(2026, 9, 24))]


def test_a_date_without_a_year_is_placed_near_the_posting_date():
    posted = datetime(2026, 12, 28, 2, 0)

    assert read_announcement("Online class on January 5", "", posted) == [Announced("online", date(2027, 1, 5))]


def test_each_date_takes_the_nearest_change_word():
    title = "The class on 26/9 is cancelled; make-up class on 3/10 from 8:00 to 9:40 in A2.401."

    assert read_announcement(title, "", POSTED) == [
        Announced("cancelled", date(2026, 9, 26)),
        Announced("makeup", date(2026, 10, 3), time(8, 0), time(9, 40), "A2.401"),
    ]


@pytest.mark.parametrize("title, start, end, room", [
    ("Học bù ngày 3/10", None, None, None),
    ("Make-up class on 3/10, 8g00-9g40", time(8, 0), time(9, 40), None),
    ("Make up class on 3/10 at 13h15", time(13, 15), None, None),
    ("Makeup class online on 3/10, 1:15 PM", time(13, 15), None, "Online"),
    ("Make-up lecture on 3/10 from 8:00 AM to 9:40 AM, room R109", time(8, 0), time(9, 40), "R109"),
    ("Make-up class at 8:00 on 3/10", time(8, 0), None, None),
    ("Make-up class on 3/10 from 1:15 to 3:45 PM", time(13, 15), time(15, 45), None),
    ("Make-up class on 3/10, 1:15-3:45pm", time(13, 15), time(15, 45), None),
    ("Make-up class on 3/10 from 11:00 to 1:00 PM", time(11, 0), time(13, 0), None),
    ("Thầy dạy bù ngày 3/10", None, None, None),
])
def test_make_up_classes(title, start, end, room):
    assert read_announcement(title, "", POSTED) == [Announced("makeup", date(2026, 10, 3), start, end, room)]


def test_a_make_up_takes_the_time_and_room_next_to_its_own_date():
    title = "Class on Thursday 24/9 13:15-15:45 cancelled, make-up class on Saturday 3/10 8:00-9:40 room A2.401"

    assert read_announcement(title, "", POSTED) == [
        Announced("cancelled", date(2026, 9, 24)),
        Announced("makeup", date(2026, 10, 3), time(8, 0), time(9, 40), "A2.401"),
    ]


def test_two_make_ups_in_one_sentence_keep_their_own_times():
    title = "Make-up class on 1/10 at 8:00 and make-up class on 3/10 at 14:00 in R109"

    assert read_announcement(title, "", POSTED) == [
        Announced("makeup", date(2026, 10, 1), time(8, 0), None, None),
        Announced("makeup", date(2026, 10, 3), time(14, 0), None, "R109"),
    ]


def row(title, posted, code="MA026IU", bb_course_id=5, text=""):
    return (code, bb_course_id, title, text, posted)


def test_the_newest_announcement_wins_for_a_course_and_date():
    rows = [row("Class on 24/9 is cancelled", datetime(2026, 9, 21)), row("Online class on 24/9", datetime(2026, 9, 20))]

    assert changes_from(rows) == {("MA026IU", date(2026, 9, 24), "class"): ClassChange(
        "MA026IU", 5, "cancelled", date(2026, 9, 24), None, None, None)}


def test_a_later_make_up_notice_keeps_the_cancellation_of_the_same_day():
    rows = [row("Cancel class on September 24", datetime(2026, 9, 15)),
            row("The make-up for the class on September 24 will be on 3/10 at 8:00", datetime(2026, 9, 16))]

    changes = changes_from(rows)

    assert changes[("MA026IU", date(2026, 9, 24), "class")].kind == "cancelled"
    assert changes[("MA026IU", date(2026, 10, 3), "makeup")].start == time(8, 0)


def test_announcements_without_a_course_code_or_time_are_skipped():
    assert changes_from([row("Online class on 24/9", None), row("Online class on 24/9", POSTED, code=None)]) == {}


def test_an_unreadable_announcement_is_skipped(monkeypatch):
    real = class_changes.read_announcement

    def read(title, text, posted_at):
        if title == "bad":
            raise ValueError("boom")
        return real(title, text, posted_at)

    monkeypatch.setattr(class_changes, "read_announcement", read)

    assert list(changes_from([row("bad", POSTED), row("Online class on 24/9", POSTED)])) == [("MA026IU", date(2026, 9, 24), "class")]
