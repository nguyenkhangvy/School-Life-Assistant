from datetime import date, datetime

from app.school.services.changes import (
    ExamInfo,
    Meeting,
    TuitionInfo,
    exam_changes,
    timetable_changes,
    tuition_changes,
)

# Times are naive UTC, as stored. 01:00 UTC is 08:00 in Vietnam.
NOW = datetime(2026, 9, 28, 0, 0)  # Mon 28/09 07:00 Vietnam time


def web(start, room="A2.307", end=None):
    return Meeting("IT093IU", "Web Application Development", start, end or start.replace(hour=start.hour + 2), room)


TUE = datetime(2026, 9, 29, 1, 0)  # Tue 29/09 08:00 VN
THU = datetime(2026, 10, 1, 1, 0)  # Thu 01/10 08:00 VN
SAT = datetime(2026, 10, 3, 1, 0)  # Sat 03/10 08:00 VN
LAST_WEEK = datetime(2026, 9, 22, 1, 0)


def summaries(changes):
    return [(c.kind, c.summary) for c in changes]


# ---- Timetable ---------------------------------------------------------------


def test_first_timetable_sync_gives_one_summary_line():
    changes = timetable_changes(None, [web(LAST_WEEK), web(TUE), web(THU)], NOW)

    assert summaries(changes) == [("added", "Timetable loaded: 1 course, 2 upcoming classes")]


def test_no_changes_means_no_lines():
    assert timetable_changes([web(TUE), web(THU)], [web(TUE), web(THU)], NOW) == []


def test_a_room_change_is_reported_in_vietnam_time():
    changes = timetable_changes([web(TUE)], [web(TUE, room="LA1.605")], NOW)

    assert summaries(changes) == [
        ("changed", "IT093IU Web Application Development: room A2.307 → LA1.605 on Tue 29/09 08:00")
    ]


def test_the_same_room_change_for_several_classes_is_one_line():
    changes = timetable_changes([web(TUE), web(THU)], [web(TUE, room="LA1.605"), web(THU, room="LA1.605")], NOW)

    assert summaries(changes) == [
        ("changed", "IT093IU Web Application Development: room A2.307 → LA1.605 on Tue 29/09 08:00, Thu 01/10 08:00")
    ]


def test_cancelled_and_extra_classes():
    changes = timetable_changes([web(TUE), web(THU)], [web(THU), web(SAT, room="A1.101")], NOW)

    assert summaries(changes) == [
        ("removed", "IT093IU Web Application Development: class cancelled on Tue 29/09 08:00"),
        ("added", "IT093IU Web Application Development: new class on Sat 03/10 08:00 (A1.101)"),
    ]


def test_past_classes_disappearing_from_edusoft_are_not_reported():
    assert timetable_changes([web(LAST_WEEK), web(TUE)], [web(TUE)], NOW) == []


def test_long_date_lists_are_shortened():
    weeks = [datetime(2026, 10, day, 1, 0) for day in (1, 8, 15, 22, 29)]

    changes = timetable_changes([web(d) for d in weeks], [], NOW)

    assert summaries(changes) == [
        ("removed", "IT093IU Web Application Development: 5 classes cancelled on "
                    "Thu 01/10 08:00, Thu 08/10 08:00, Thu 15/10 08:00 and 2 more")
    ]


# ---- Exams -------------------------------------------------------------------

FINAL = ExamInfo("IT093IU", "Web Application Development", "final", datetime(2026, 12, 12, 1, 0), "A1.101")


def test_first_exam_sync_gives_one_summary_line():
    assert summaries(exam_changes(None, [FINAL], NOW)) == [("added", "Exam schedule loaded: 1 exam")]


def test_a_new_exam():
    assert summaries(exam_changes([], [FINAL], NOW)) == [
        ("added", "New final exam: IT093IU Web Application Development, Sat 12/12 08:00 (A1.101)")
    ]


def test_a_moved_exam():
    moved = FINAL._replace(start_at=datetime(2026, 12, 14, 6, 0))

    assert summaries(exam_changes([FINAL], [moved], NOW)) == [
        ("changed", "IT093IU Web Application Development final exam moved: Sat 12/12 08:00 → Mon 14/12 13:00")
    ]


def test_an_exam_room_change():
    assert summaries(exam_changes([FINAL], [FINAL._replace(room="A1.202")], NOW)) == [
        ("changed", "IT093IU Web Application Development final exam room: A1.101 → A1.202")
    ]


def test_a_removed_exam():
    assert summaries(exam_changes([FINAL], [], NOW)) == [
        ("removed", "Final exam removed: IT093IU Web Application Development")
    ]


# ---- Tuition -----------------------------------------------------------------

UNPAID = TuitionInfo("20261", 12500000, date(2026, 10, 15), "Chưa đóng")


def test_first_tuition_sync():
    assert summaries(tuition_changes(None, UNPAID)) == [
        ("added", "Tuition 20261: balance 12,500,000 VND, due 15/10/2026")
    ]


def test_tuition_paid():
    paid = UNPAID._replace(balance=0, status_text="Đã đóng")

    assert summaries(tuition_changes(UNPAID, paid)) == [
        ("changed", "Tuition 20261: balance 12,500,000 → 0 VND"),
        ("changed", "Tuition 20261: status Chưa đóng → Đã đóng"),
    ]


def test_tuition_due_date_moved():
    assert summaries(tuition_changes(UNPAID, UNPAID._replace(due_date=date(2026, 10, 20)))) == [
        ("changed", "Tuition 20261: due date 15/10/2026 → 20/10/2026")
    ]


def test_unchanged_tuition_gives_no_lines():
    assert tuition_changes(UNPAID, UNPAID) == []


def test_an_empty_exam_schedule_is_not_announced_again_and_again():
    assert exam_changes(None, [], NOW) == []


def test_an_empty_timetable_is_not_announced_again_and_again():
    assert timetable_changes(None, [], NOW) == []
