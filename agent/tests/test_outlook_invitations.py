"""Outlook meeting requests and cancellations in the Inbox (spec 2026-10-07-mail-event-kinds-design.md §5), read
through a fake Outlook: a request's times come from Outlook, not from its text."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from agent.tests.outlook_fakes import (
    E_ABORT,
    NOT_FOUND,
    ComError,
    FakeAccount,
    FakeAppointment,
    FakeCancellation,
    FakeMail,
    FakeMeetingReply,
    FakeMeetingRequest,
    FakeOutlook,
    FakePattern,
    at,
)
from sla_agent.errors import OutlookBlocked
from sla_agent.mail_rules import Context
from sla_agent.outlook_reader import newest_received, read_outlook

ME = "ititiu99001@student.hcmiu.edu.vn"
SINCE = date(2026, 8, 1)
TODAY = date(2026, 9, 28)  # Mon, in Vietnam
CONTEXT = Context(courses=(("IT093IU", "Web Application Development", "P.Q.Hùng"),))
LECTURER = dict(address="pqhung@hcmiu.edu.vn", name="Pham Quoc Hung")


def vietnam(month, day, hour=0, minute=0):
    """A Vietnam wall time as aware UTC, as Outlook's StartUTC gives it."""
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc) - timedelta(hours=7)


def read(*items):
    return read_outlook(ME, SINCE, CONTEXT, open_outlook=lambda: FakeOutlook(FakeAccount(ME, items)),
                        sleep=lambda seconds: None, today=TODAY).emails


def sessions(email):
    return [(s.day.isoformat(), s.start.strftime("%H:%M"), s.end and s.end.strftime("%H:%M")) for s in email.sessions]


def test_a_requests_time_comes_from_outlook_not_its_text():
    request = FakeMeetingRequest("Họp nhóm đồ án", at(25), FakeAppointment(vietnam(10, 1, 9), vietnam(10, 1, 10)),
                                 "Nhắc lại: buổi trước họp lúc 14h00 ngày 05/10/2026.", **LECTURER)

    [email] = read(request)

    assert sessions(email) == [("2026-10-01", "09:00", "10:00")]
    assert (email.invitation, email.meeting, email.categories, email.from_lecturer) == (
        "request", True, ["class"], True)


def test_a_recurring_meeting_gives_its_next_occurrences():
    pattern = FakePattern(time(9, 0), {
        date(2026, 9, 22): FakeAppointment(vietnam(9, 22, 9), vietnam(9, 22, 10)),  # before today
        date(2026, 9, 29): FakeAppointment(vietnam(9, 29, 9), vietnam(9, 29, 10)),
        date(2026, 10, 6): FakeAppointment(vietnam(10, 6, 9), vietnam(10, 6, 10)),
        date(2026, 10, 13): FakeAppointment(vietnam(10, 14, 10), vietnam(10, 14, 11)),  # moved to Wed 10:00
        date(2026, 10, 27): FakeAppointment(vietnam(10, 27, 9), vietnam(10, 27, 10)),  # 20/10 was skipped
    })
    series = FakeAppointment(vietnam(9, 22, 9), vietnam(9, 22, 10), pattern=pattern)

    [email] = read(FakeMeetingRequest("Họp nhóm hằng tuần", at(20), series, **LECTURER))

    assert sessions(email) == [("2026-09-29", "09:00", "10:00"), ("2026-10-06", "09:00", "10:00"),
                               ("2026-10-14", "10:00", "11:00"), ("2026-10-27", "09:00", "10:00")]
    assert all(asked.time() == time(9, 0) for asked in pattern.asked)


def test_a_recurring_meeting_gives_at_most_ten():
    days = [TODAY + timedelta(days=n) for n in range(30)]
    pattern = FakePattern(time(18, 0), {day: FakeAppointment(vietnam(day.month, day.day, 18),
                                                             vietnam(day.month, day.day, 19)) for day in days})

    [email] = read(FakeMeetingRequest("Daily stand-up", at(27), FakeAppointment(vietnam(9, 28, 18),
                                                                                 vietnam(9, 28, 19), pattern=pattern)))

    assert [s.day for s in email.sessions] == days[:10]


def test_a_meeting_longer_than_a_day_is_a_period():
    [email] = read(FakeMeetingRequest("Trại hè khoa học", at(25),
                                      FakeAppointment(vietnam(10, 10, 8), vietnam(10, 12, 17))))

    assert email.sessions == []
    assert [(p.first_day, p.last_day, p.mode, p.from_time, p.to_time) for p in email.periods] == [
        (date(2026, 10, 10), date(2026, 10, 12), "one_window", time(8, 0), time(17, 0))]


def test_an_all_day_meeting_is_an_all_day_period():
    [email] = read(FakeMeetingRequest("Ngày hội CLB", at(25),
                                      FakeAppointment(vietnam(10, 5), vietnam(10, 7), all_day=True)))

    assert [(p.first_day, p.last_day, p.mode, p.from_time) for p in email.periods] == [
        (date(2026, 10, 5), date(2026, 10, 6), "all_day", None)]


def test_a_meeting_that_ends_after_midnight_ends_the_next_day():
    start = vietnam(12, 31, 22)

    [email] = read(FakeMeetingRequest("Countdown", at(25), FakeAppointment(start, start + timedelta(hours=2, minutes=30))))

    assert [(s.end, s.ends_next_day) for s in email.sessions] == [(time(0, 30), True)]


def test_a_cancellation_has_no_sessions():
    cancelled = FakeCancellation("Đã hủy: Họp nhóm đồ án", at(26), "Cuộc họp lúc 9h00 ngày 01/10/2026 đã bị hủy.",
                                 thread="T7", **LECTURER)

    [email] = read(cancelled)

    assert (email.invitation, email.meeting, email.sessions, email.periods) == ("cancelled", True, [], [])
    assert email.thread_id == "T7"


def test_replies_to_invitations_are_still_skipped():
    emails = read(FakeMeetingReply("Đã chấp nhận: Họp nhóm đồ án", at(27)), FakeMail("Hello", at(26)))

    assert [e.subject for e in emails] == ["Hello"]


def test_the_text_still_gives_the_check_in_and_mode():
    request = FakeMeetingRequest(
        "Workshop kỹ năng", at(25), FakeAppointment(vietnam(10, 5, 14), vietnam(10, 5, 16)),
        "Thời gian: 14h00 - 16h00 ngày 05/10/2026, check-in lúc 13h30, họp online qua Teams.\nHạn đăng ký: 03/10/2026.")

    [email] = read(request)

    assert [(s.start, s.check_in, s.mode) for s in email.sessions] == [(time(14, 0), time(13, 30), "online")]
    assert [(d.kind, d.day) for d in email.deadlines] == [("register", date(2026, 10, 3))]


def test_a_teams_meeting_is_online():
    request = FakeMeetingRequest("Họp nhóm", at(25), FakeAppointment(vietnam(10, 1, 9), vietnam(10, 1, 10),
                                                                     location="Microsoft Teams Meeting"))

    assert [s.mode for s in read(request)[0].sessions] == ["online"]


def test_the_location_never_leaves_the_laptop():
    request = FakeMeetingRequest("Họp nhóm", at(25), FakeAppointment(vietnam(10, 1, 9), vietnam(10, 1, 10),
                                                                     location="UNIQUE-ROOM-5c1d"))

    [email] = read(request)

    assert "UNIQUE-ROOM-5c1d" not in email.model_dump_json()


def test_when_outlook_cant_give_the_appointment_the_text_gives_the_times():
    request = FakeMeetingRequest("Họp nhóm", at(25), ComError(NOT_FOUND), "Họp lúc 9h00 ngày 01/10/2026.")

    [email] = read(request)

    assert sessions(email) == [("2026-10-01", "09:00", None)]
    assert email.invitation == "request"


def test_outlook_refusing_the_appointment_blocks_the_read():
    request = FakeMeetingRequest("Họp nhóm", at(25), ComError(E_ABORT))

    with pytest.raises(OutlookBlocked):
        read(request)


def test_the_quick_check_counts_a_meeting_request_as_new_mail():
    outlook = FakeOutlook(FakeAccount(ME, [
        FakeMail("Old", at(20)),
        FakeMeetingRequest("Họp nhóm", at(29), FakeAppointment(vietnam(10, 1, 9), vietnam(10, 1, 10))),
        FakeMeetingReply("Đã chấp nhận", at(30)),
    ]))

    assert newest_received(ME, running=lambda: outlook) == at(29)
