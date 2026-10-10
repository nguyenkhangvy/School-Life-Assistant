"""The mail time reader: an email's sessions, Periods, deadlines and flags (spec 2026-10-07-mail-event-kinds-design.md
§4). The whole test set is in test_mail_times_cases.py; these tests pin each rule on its own."""

import unicodedata
from datetime import date, time

import pytest

from sla_agent.mail_times import LINK_MARK, _sentences, clean, read_times

# ---- step 0: cleaning (§4.1) -----------------------------------------------------------------------------------------

REPLY = "Ok em, mình dời sang 15h00 nhé.\n\n{quote}\nCả nhóm gặp thầy lúc 10h00 ngày 02/10/2026."


@pytest.mark.parametrize("quote", [
    "From: Đặng Văn Long\nSent: Monday, September 28, 2026 10:00 AM",
    "Từ: Đặng Văn Long\nĐã gửi: Thứ Hai, 28 tháng 9, 2026 10:00",
    "-----Original Message-----",
    "On Mon, Sep 28, 2026 at 10:00 AM Đặng Văn Long <dvlong@hcmiu.edu.vn> wrote:",
    "Vào Th 2, 28 thg 9, 2026 lúc 10:00 Đặng Văn Long <dvlong@hcmiu.edu.vn>\nđã viết:",
    "> Cả nhóm gặp thầy",
])
def test_a_reply_loses_its_quoted_part(quote):
    assert clean("RE: Họp nhóm", REPLY.format(quote=quote)).strip() == "Ok em, mình dời sang 15h00 nhé."


@pytest.mark.parametrize("subject", ["TL: Họp nhóm", "Trả lời: Họp nhóm", "Re: Re: Họp nhóm"])
def test_every_way_of_marking_a_reply(subject):
    text = REPLY.format(quote="From: Đặng Văn Long\nSent: Monday")

    assert "10h00" not in clean(subject, text)


@pytest.mark.parametrize("subject", ["FW: Họp nhóm", "Fwd: Họp nhóm", "Họp nhóm"])
def test_forwards_and_other_emails_keep_everything(subject):
    text = REPLY.format(quote="From: Đặng Văn Long\nSent: Monday")

    assert "10h00 ngày 02/10/2026" in clean(subject, text)


def test_a_replys_own_time_lines_are_not_a_quote():
    text = "Lịch họp nhóm:\nTừ: 14h00\nĐến: 16h00\nNgày: 05/10/2026"

    assert clean("RE: Lịch họp", text) == text


def test_the_signature_and_office_hours_are_cut():
    text = "Workshop ngày 05/10/2026.\nGiờ làm việc: 7h30 - 16h30\nHẹn gặp các bạn.\n--\nPhòng CTSV\nHotline 0283"

    assert clean("Workshop", text) == "Workshop ngày 05/10/2026.\nHẹn gặp các bạn."


def test_links_go_and_accents_typed_apart_are_joined():
    text = unicodedata.normalize("NFD", "Đăng ký: https://example.com/event-30-9-14h00 trước 30/9")

    assert clean("", text) == f"Đăng ký:  {LINK_MARK}  trước 30/9"  # the link's dates and times are gone


# ---- sentences and headings (§4.2) -----------------------------------------------------------------------------------


def test_a_registration_heading_is_read_with_the_line_after_it():
    assert _sentences("THỜI GIAN ĐĂNG KÝ\n\nTừ ngày 20/09 đến 22/09/2026. Lưu ý: hợp lệ theo từng đợt.") == [
        "THỜI GIAN ĐĂNG KÝ: Từ ngày 20/09 đến 22/09/2026.", "Lưu ý: hợp lệ theo từng đợt."]


@pytest.mark.parametrize("text", [
    "ĐỊA ĐIỂM\nHội trường A2",  # not about registration
    "Hạn đăng ký 05/10\nHội thảo lúc 14h",  # has a number: a sentence of its own
    "Thông tin đăng ký Lễ Bế mạc Hội thao Sinh viên như sau\nThời gian: 9g45",  # longer than a heading
])
def test_other_lines_stay_on_their_own(text):
    assert len(_sentences(text)) == 2


def test_a_no_break_space_in_the_subject_is_a_space():
    found = read_times("Đăng ký từ\N{NO-BREAK SPACE}nay đến 20/10/2026", "Workshop lúc 14h00 ngày 25/10/2026.",
                       date(2026, 10, 7))

    assert (found.register_by, [(s.day, s.start) for s in found.sessions]) == (
        date(2026, 10, 20), [(date(2026, 10, 25), time(14, 0))])


def test_a_from_line_and_a_to_line_are_one_range():
    found = read_times("", "Lịch họp nhóm:\nTừ: 14h00\nĐến: 16h00\nNgày: 15/10/2026", date(2026, 10, 7))

    assert [(s.day, s.start, s.end) for s in found.sessions] == [(date(2026, 10, 15), time(14, 0), time(16, 0))]


@pytest.mark.parametrize("text, session", [
    ("Link đăng ký: https://forms.gle/AbCdEf123\nThời gian: 14h00 - 16h30 ngày 20/10/2026\nĐịa điểm: Hội trường A2",
     (date(2026, 10, 20), time(14, 0), time(16, 30))),
    ("Đăng ký tại: https://forms.gle/x\nWorkshop diễn ra từ 8h00 đến 11h30 ngày 24/10/2026.",
     (date(2026, 10, 24), time(8, 0), time(11, 30))),
])
def test_a_line_that_held_a_link_is_not_a_heading(text, session):
    found = read_times("", text, date(2026, 10, 7))

    assert [(s.day, s.start, s.end) for s in found.sessions] == [session]
    assert found.deadlines == ()


# ---- deadlines (§4.3, D) ---------------------------------------------------------------------------------------------

ARRIVED = date(2026, 9, 28)  # Mon, in Vietnam


def deadlines(text, subject="", arrived=ARRIVED):
    return [(d.kind, d.day.strftime("%d/%m"), d.at and d.at.strftime("%H:%M"))
            for d in read_times(subject, text, arrived).deadlines]


@pytest.mark.parametrize("text, expected", [
    ("Hạn đăng ký: 17/10/2026 lúc 23:59.", [("register", "17/10", "23:59")]),
    ("Form đăng ký sẽ đóng vào 23:59 ngày 16/10.", [("register", "16/10", "23:59")]),
    ("Ngày 15/10 đóng đăng ký.", [("register", "15/10", None)]),  # no date after the word: the one before it
    ("Vui lòng xác nhận tham dự trước 18:00 ngày 07/11.", [("confirm", "07/11", "18:00")]),
    ("Sinh viên phải nộp bài trước 23:59 ngày 25/10/2026.", [("due", "25/10", "23:59")]),
    ("Sinh viên hoàn thành học phí trước 17:00 ngày 05/12.", [("due", "05/12", "17:00")]),
    ("Sinh viên vui lòng hoàn thành hồ sơ trước 17:00 ngày 13/10/2026.", [("register", "13/10", "17:00")]),
    ("Vui lòng đăng ký trước ngày 30/10 để được xác nhận suất tham dự.", [("register", "30/10", None)]),
    ("Hạn chót: 30/9", [("due", "30/09", None)]),  # a strong word without a kind word is "due"
    ("Report due 30/9 at 5 PM", [("due", "30/09", "17:00")]),
    ("Please register by 5 PM, October 3.", [("register", "03/10", "17:00")]),
    ("Sinh viên có thể đăng ký học phần đến 16:00 ngày 10/12.", [("register", "10/12", "16:00")]),
    ("Form đăng ký mở đến 16:00 ngày 21/11.", [("register", "21/11", "16:00")]),
    ("Ngày 05/10/2026: hạn đăng ký 12h00, workshop 14h00 - 16h30.", [("register", "05/10", "12:00")]),
    ("Sinh viên đăng ký trước 12h00 để tham gia workshop lúc 14h00 ngày 05/10/2026.", [("register", "05/10", "12:00")]),
])
def test_closing_words(text, expected):
    assert deadlines(text) == expected


@pytest.mark.parametrize("text", [
    "Link tham gia sẽ được gửi trước 09:00 ngày 18/10.",  # a soft word without a kind word
    "Sinh viên vui lòng có mặt trước 13:45 ngày 15/10.",  # an arrival takes its "trước" first
    "Due to the rain, the talk moves to 14h ngày 30/9.",
    "Số lượng có hạn, đăng ký tham gia ngày 30/9.",  # bare "hạn"
    "Đăng ký tham gia Tuần lễ diễn ra từ 26/10 đến 30/10.",  # an event word between: not a registration window
    "Khóa học mở từ 10/12 đến 20/12.",  # an opening word needs a registration word
])
def test_not_deadlines(text):
    assert deadlines(text) == []


@pytest.mark.parametrize("text, expected", [
    ("Việc đăng ký tham dự mở từ 08/10 đến 12/10.", [("opens", "08/10", None), ("register", "12/10", None)]),
    ("Sinh viên có thể đăng ký từ 08:00 ngày 20/11 đến 23:59 ngày 22/11.",
     [("opens", "20/11", "08:00"), ("register", "22/11", "23:59")]),
    ("Thời gian đăng ký: 8h00 - 12h00 ngày 05/10/2026.", [("opens", "05/10", "08:00"), ("register", "05/10", "12:00")]),
    ("THỜI GIAN ĐĂNG KÝ\nTừ ngày 20/09 đến 22/09/2026.", [("opens", "20/09", None), ("register", "22/09", None)]),
])
def test_registration_windows(text, expected):
    assert deadlines(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Mở đăng ký từ 05/10. Hạn đăng ký là 12/10 lúc 17:00.", [("opens", "05/10", None), ("register", "12/10", "17:00")]),
    ("Form mở ngày 01/10.\nForm đóng ngày 10/10.", [("opens", "01/10", None), ("register", "10/10", None)]),
    ("Cổng đăng ký mở từ 01/11/2026 và đóng vào 15/11/2026 lúc 17:00.",
     [("opens", "01/11", None), ("register", "15/11", "17:00")]),
    ("Đăng ký bắt đầu 18/12 và kết thúc 22/12 lúc 23:59.", [("opens", "18/12", None), ("register", "22/12", "23:59")]),
])
def test_opening_words(text, expected):
    assert deadlines(text) == expected


@pytest.mark.parametrize("text", [
    "Mời các bạn đăng ký tham gia workshop lúc 8h00 - 11h30 ngày 24/10/2026 tại phòng A2.301.",  # "lúc": the event's
    "Đăng ký tham gia workshop diễn ra từ 8h00 đến 11h30 ngày 24/10/2026.",  # the range's own "đến" closes nothing
])
def test_an_events_own_time_is_not_a_registration_window(text):
    found = read_times("", text, ARRIVED)

    assert [(s.day, s.start, s.end) for s in found.sessions] == [(date(2026, 10, 24), time(8, 0), time(11, 30))]
    assert found.deadlines == ()


def test_the_same_deadline_is_kept_once_with_its_time():
    text = "Sinh viên đăng ký lịch phỏng vấn từ 05/11 đến 09/11. Hệ thống sẽ đóng đăng ký lúc 23:59 ngày 09/11."

    assert deadlines(text) == [("opens", "05/11", None), ("register", "09/11", "23:59")]


def test_at_most_five_deadlines_soonest_first():
    text = " ".join(f"Hạn nộp bài {n}: {n + 10}/10." for n in range(7, 0, -1))

    assert deadlines(text) == [("due", f"{n + 10}/10", None) for n in range(1, 6)]


def test_the_subject_gives_deadlines_too():
    assert deadlines("Xem chi tiết bên dưới.", subject="Hạn đăng ký: 05/10") == [("register", "05/10", None)]


def test_register_by_is_the_latest_register_deadline_even_a_past_one():
    found = read_times("", "Hạn chót đăng ký: 24/9. Gia hạn: hạn đăng ký đến 27/9. Hạn nộp bài: 30/9.", ARRIVED)

    assert found.register_by == date(2026, 9, 27)
    assert read_times("", "Hạn nộp bài: 30/9", ARRIVED).register_by is None


def test_a_deadline_takes_a_mode_only_from_its_own_words():
    both = ("Sinh viên tham gia trực tiếp đăng ký trước 12h00 ngày 03/10. "
            "Tham gia online qua Zoom đăng ký trước 17h00 ngày 05/10.")
    online_event = "Workshop lúc 09:30 ngày 18/10/2026 trên Microsoft Teams.\nHạn đăng ký: 17/10/2026 lúc 23:59."

    assert [(d.day, d.mode) for d in read_times("", both, ARRIVED).deadlines] == [
        (date(2026, 10, 3), "in_person"), (date(2026, 10, 5), "online")]
    assert [d.mode for d in read_times("", online_event, ARRIVED).deadlines] == [None]


# ---- Periods (§4.3, P) -----------------------------------------------------------------------------------------------


def periods(text, arrived=ARRIVED):
    return [(p.mode, p.first_day.strftime("%d/%m"), p.last_day.strftime("%d/%m"),
             p.from_time and p.from_time.strftime("%H:%M"), p.to_time and p.to_time.strftime("%H:%M"), p.details_later,
             p.label) for p in read_times("", text, arrived).periods]


@pytest.mark.parametrize("text, expected", [
    ("Tuần lễ diễn ra từ 26/10 đến 30/10/2026.", [("all_day", "26/10", "30/10", None, None, False, None)]),
    ("Triển lãm mở cửa từ 09:00 đến 17:00 trong các ngày 02/11 đến 05/11.",
     [("daily_window", "02/11", "05/11", "09:00", "17:00", False, None)]),
    ("Ngày hội mở cửa từ 08:00 đến 16:00 ngày 14/11/2026.\nSinh viên có thể đến bất kỳ thời điểm nào trong thời gian trên.",
     [("one_window", "14/11", "14/11", "08:00", "16:00", False, None)]),
    ("Chương trình diễn ra từ 09:00 ngày 28/11 đến 16:00 ngày 29/11.",
     [("one_window", "28/11", "29/11", "09:00", "16:00", False, None)]),
    ("Vòng 1 diễn ra từ 8h00 ngày 01/10/2026 đến 17h00 ngày 05/10/2026.",
     [("one_window", "01/10", "05/10", "08:00", "17:00", False, "round_1")]),
    ("Các buổi tư vấn diễn ra trong khoảng 09:00 đến 16:00 ngày 18/11.\nSinh viên cần đặt lịch trước 15/11.",
     [("one_window", "18/11", "18/11", "09:00", "16:00", True, None)]),
    ("Ngày hội thể thao diễn ra từ 07:00 đến 17:00 ngày 06/12.\nCác trận đấu của bạn sẽ được thông báo sau.",
     [("one_window", "06/12", "06/12", "07:00", "17:00", True, None)]),
    ("Hội thao từ 01/10 đến 05/10, 7h00 - 11h00.", [("daily_window", "01/10", "05/10", "07:00", "11:00", False, None)]),
    ("Thời gian: 8h00 - 11h30 & 13h00 - 16h00 (Từ nay đến 30/09).",
     [("daily_window", "28/09", "30/09", "08:00", "11:30", False, None),
      ("daily_window", "28/09", "30/09", "13:00", "16:00", False, None)]),
    # 00:00 to 23:59 are the edges of the day, not times the email sets: the Period is all day (§2)
    ("Vòng 1 diễn ra từ 00g00 ngày 05/10 đến 23g59 ngày 11/10/2026.",
     [("all_day", "05/10", "11/10", None, None, False, "round_1")]),
    ("Thư viện phục vụ từ 00:00 đến 23:59 trong các ngày 05/10 đến 09/10.",
     [("all_day", "05/10", "09/10", None, None, False, None)]),
    ("Phòng tự học mở từ 00:00 đến 23:59 ngày 06/10, sinh viên có thể đến bất kỳ lúc nào.",
     [("all_day", "06/10", "06/10", None, None, False, None)]),
], ids=["days", "open-hours", "any-time-next-line", "over-a-day", "round", "within-and-booked", "later", "no-each-day",
        "two-hour-ranges", "whole-days-window", "whole-days-each-day", "whole-day"])
def test_periods(text, expected):
    assert periods(text) == expected


@pytest.mark.parametrize("text", [
    "Sinh viên đăng ký từ 01/11 đến 05/11.",  # a registration window (D2)
    "Trường nghỉ từ 24/12 đến 26/12.",  # not an event
    "Thời gian tiếp nhận: từ 01/10 đến 05/10.",  # a notice
    "Hội thao diễn ra từ 01/10 đến 03/10, từ 7h00 - 11h00 mỗi ngày.",  # each day: sessions (P5)
    "Sự kiện diễn ra từ 22:00 ngày 31/12/2026 đến 00:30 ngày 01/01/2027.",  # a night: one session (P4)
    "Tuần 3: Từ 00g00 ngày 14/9 đến 23g59 ngày 20/9/2026.",  # over before the email arrived
    "Thời gian: 14g00 - 17g00, ngày 11/10/2026.\nĐịa điểm: Thông tin chi tiết sẽ thông báo sau.",  # later is about where
])
def test_not_periods(text):
    assert periods(text) == []


# ---- sessions (§4.3, S) ----------------------------------------------------------------------------------------------


def sessions(text, arrived=ARRIVED):
    return [(s.day.strftime("%d/%m"), s.start.strftime("%H:%M"),
             s.end and ("~" if s.end_is_approximate else "") + s.end.strftime("%H:%M"),
             s.check_in and s.check_in.strftime("%H:%M"), s.link_opens and s.link_opens.strftime("%H:%M"))
            for s in read_times("", text, arrived).sessions]


@pytest.mark.parametrize("text, expected", [
    ("Ngày: 01/10/2026\nThời gian: 13h00 – 16h00", [("01/10", "13:00", "16:00", None, None)]),  # the line above
    ("Thời gian: 14h00 – 16h30\nNgày: 05/10/2026", [("05/10", "14:00", "16:30", None, None)]),  # the line below
    ("Hạn đăng ký: 05/10.\nVui lòng có mặt lúc 13:30.\nHội thảo bắt đầu lúc 14:00 ngày 20/10 và kết thúc lúc 16:00.",
     [("20/10", "14:00", "16:00", "13:30", None)]),  # a deadline line gives no day
    ("Ngày 29/09 và 01/10, 13:00–14:00", [("29/09", "13:00", "14:00", None, None), ("01/10", "13:00", "14:00", None, None)]),
    ("29/9 lúc 8h, 30/9 lúc 14h", [("29/09", "08:00", None, None, None), ("30/09", "14:00", None, None, None)]),
    ("Thời gian: 14h", []),  # no day anywhere
], ids=["above", "below", "deadline-line", "two-days-one-time", "pairs", "no-day"])
def test_the_day_of_a_time(text, expected):
    assert sessions(text) == expected


WEDNESDAY = date(2026, 10, 7)


def test_a_relative_day_only_without_a_written_date():
    [tonight] = read_times("", "Chúng ta sẽ họp vào 20:00 tối nay.", WEDNESDAY).sessions
    [dated] = read_times("", "Workshop ngày 12/10/2026.\nHọp lúc 9h sáng thứ Ba.", WEDNESDAY).sessions

    assert (tonight.day, tonight.relative) == (date(2026, 10, 7), "today")
    assert (dated.day, dated.relative) == (date(2026, 10, 12), None)


@pytest.mark.parametrize("text, expected", [
    ("Cuộc họp bắt đầu lúc 19:00 ngày 12/10 và dự kiến kết thúc lúc 20:30.", [("12/10", "19:00", "~20:30", None, None)]),
    ("Hoạt động bắt đầu lúc 06:30 ngày 07/10.\nHoạt động dự kiến kết thúc vào 11:30.",
     [("07/10", "06:30", "~11:30", None, None)]),
    ("Workshop diễn ra trong 2 giờ, bắt đầu lúc 08:30 ngày 16/10.", [("16/10", "08:30", "10:30", None, None)]),
    ("Họp lúc 10h ngày 08/10. Họp khoảng 1 tiếng.", [("08/10", "10:00", "~11:00", None, None)]),
    ("Thuyết trình vào 10:30 ngày 23/12. Thời gian trình bày là 15 phút, sau đó có 10 phút hỏi đáp.",
     [("23/12", "10:30", "10:55", None, None)]),
    ("Tư vấn lúc 09:00 ngày 18/10. Mỗi lượt tư vấn kéo dài khoảng 30 phút.", [("18/10", "09:00", None, None, None)]),
], ids=["start-and-end", "end-alone", "length-before", "length-after", "lengths-add-up", "slot-length"])
def test_the_end_of_a_session(text, expected):
    assert sessions(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Hội thảo lúc 14:00 ngày 15/10. Có mặt trước 13:45.", [("15/10", "14:00", None, "13:45", None)]),
    ("Check in: 13:00 - 13:45, ngày 29/09/2026", [("29/09", "13:00", "13:45", None, None)]),  # no later session
    ("Workshop lúc 09:30 ngày 18/10 trên Teams. Link tham gia sẽ được gửi trước 09:00 cùng ngày.",
     [("18/10", "09:30", None, None, "09:00")]),
    ("Meeting lúc 15:00 ngày 09/10. Link sẽ được gửi trước đó 30 phút.", [("09/10", "15:00", None, None, "14:30")]),
], ids=["check-in", "check-in-alone", "link-time", "link-before"])
def test_check_in_and_link_times(text, expected):
    assert sessions(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("The webinar starts at 9:00 AM EST on October 5, 2026.", [("05/10", "21:00", None, None, None)]),
    ("The talk starts at 8:00 PM PST on October 5, 2026.", [("06/10", "11:00", None, None, None)]),
])
def test_a_written_time_zone_becomes_vietnam_time(text, expected):
    assert sessions(text) == expected


def test_past_days_repeats_and_at_most_ten_soonest_first():
    days = ", ".join(f"{d}/10" for d in range(12, 0, -1))

    assert sessions("ngày 20/9 lúc 14h và ngày 30/9 lúc 14h") == [("30/09", "14:00", None, None, None)]
    assert sessions("Workshop 30/9 lúc 14h\nThời gian: 14h00 – 16h00 ngày 30/9") == [("30/09", "14:00", "16:00", None, None)]
    assert [s[0] for s in sessions(f"Các buổi: {days}, lúc 18h")] == [f"{d:02d}/10" for d in range(1, 11)]


def test_a_night_session_ends_the_next_day():
    [night] = read_times("", "Sự kiện diễn ra từ 22:00 ngày 31/12/2026 đến 00:30 ngày 01/01/2027.", ARRIVED).sessions

    assert (night.day, night.start, night.end, night.ends_next_day) == (date(2026, 12, 31), time(22), time(0, 30), True)


@pytest.mark.parametrize("text, days", [
    ("Hội thao diễn ra từ 01/10 đến 03/10, từ 7h00 - 11h00 mỗi ngày.", ["01/10", "02/10", "03/10"]),
    ("Lớp vào các ngày thứ Bảy từ 03/10 đến 24/10/2026, 8h00 - 11h00.", ["03/10", "10/10", "17/10", "24/10"]),
])
def test_each_day_of_a_range(text, days):
    assert [s[0] for s in sessions(text)] == days


def test_a_dated_event_with_no_hour_is_a_one_day_period():
    found = read_times("", "Ngày 15/10 đóng đăng ký.\nNgày 20/10 diễn ra vòng 1.", ARRIVED)

    assert found.sessions == ()
    assert [(p.mode, p.first_day, p.label) for p in found.periods] == [("all_day", date(2026, 10, 20), "round_1")]


@pytest.mark.parametrize("text, expected", [
    ("Email này được gửi lúc 09:15 ngày 07/10/2026.\nHội thảo sẽ diễn ra vào 14:00 ngày 20/10/2026.",
     [("20/10", "14:00", None, None, None)]),
    ("Workshop dời từ 14h00 ngày 05/10/2026 sang 15h00 ngày 06/10/2026.", [("06/10", "15:00", None, None, None)]),
    ("Hủy buổi workshop 14h00 ngày 05/10/2026 do thời tiết xấu.", []),
    ("Buổi học ngày 04/12 lúc 13:00 sẽ chuyển từ phòng A1.201 sang A2.205.", []),
    ("Workshop ngày 05/10/2026: 08:00 - 11:30.\nNghỉ giải lao 09:30 - 09:45.", [("05/10", "08:00", "11:30", None, None)]),
], ids=["notice", "rescheduled", "cancelled", "room-change", "a-break-drops-only-its-line"])
def test_what_is_dropped(text, expected):
    assert sessions(text, arrived=date(2026, 9, 28)) == expected


@pytest.mark.parametrize("text, expected", [
    ("Workshop diễn ra lúc 14:00 ngày 15/10/2026, nếu không tham gia được vui lòng hủy đăng ký.",
     [("15/10", "14:00", None, None, None)]),  # cancelling one's registration cancels no time
    ("Workshop diễn ra từ 08:00 - 11:30 ngày 15/10/2026, nghỉ giải lao lúc 09:30.",
     [("15/10", "08:00", "11:30", None, None)]),  # the break drops only its own part
])
def test_a_drop_word_drops_only_its_part(text, expected):
    assert sessions(text, arrived=date(2026, 9, 28)) == expected


@pytest.mark.parametrize("text, expected", [
    ("Sinh viên đăng nhập hệ thống và nộp bài trước 23:59 ngày 20/10/2026.", [("due", "20/10", "23:59")]),
    ("Sinh viên đăng nhập vào hệ thống để đăng ký học phần từ 8h00 ngày 12/10/2026 đến 17h00 ngày 16/10/2026.",
     [("opens", "12/10", "08:00"), ("register", "16/10", "17:00")]),
])
def test_an_arrival_word_stops_at_a_deadline_or_registration_word(text, expected):
    assert (sessions(text), deadlines(text)) == ([], expected)


def test_the_edges_of_a_day_never_start_a_session():
    assert sessions("Sinh viên đăng nhập hệ thống từ 00:00 ngày 15/10/2026.") == []
    whole_day = "Vòng loại diễn ra từ 00g00 ngày 15/10/2026 đến 23g59 ngày 15/10/2026."
    assert sessions(whole_day) == []
    assert periods(whole_day) == [("all_day", "15/10", "15/10", None, None, False, "qualifying")]


@pytest.mark.parametrize("text, modes", [
    ("Workshop lúc 09:30 ngày 18/10/2026 trên Microsoft Teams.", ["online"]),
    ("Link Teams sẽ mở lúc 13:45 ngày 15/10.\nChương trình bắt đầu lúc 14:00 ngày 15/10.", ["online"]),
    ("Hội thảo lúc 14:00 ngày 15/10/2026 tại phòng A2.301.", [None]),  # no online words: no modes at all
    ("Sáng 17/10: 08:00–11:30 trực tiếp tại hội trường. Tối 17/10: 19:00–21:00 online qua Zoom.", ["in_person", "online"]),
], ids=["online-in-its-part", "only-online-words-in-the-email", "no-online-words", "both"])
def test_session_modes(text, modes):
    assert [s.mode for s in read_times("", text, ARRIVED).sessions] == modes


@pytest.mark.parametrize("text, labels", [
    ("Ca 1: 8:00–10:00; Ca 2: 13:00–15:00 ngày 30/9", ["shift_1", "shift_2"]),
    ("Vòng sơ loại diễn ra vào 15/10 lúc 13h30.", ["preliminary"]),
])
def test_session_labels(text, labels):
    assert [s.label for s in read_times("", text, ARRIVED).sessions] == labels


# ---- flags (§2) ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("subject, text, meeting", [
    ("Họp nhóm", "", True),  # the subject counts
    ("", "Thầy hẹn cả nhóm họp lúc 9h.", True),
    ("", "Bài kiểm tra giữa kỳ sẽ bắt đầu lúc 08:00 ngày 12/11.", True),
    ("", "Đây là email nhắc hạn thanh toán, không có buổi gặp trực tiếp.", False),
    ("Workshop kỹ năng thuyết trình", "Workshop diễn ra vào 24/11 lúc 13:00.", False),
    ("", "Gặp gỡ các builder Web3.", False),
    ("", "Xin cảm ơn và hẹn gặp lại bạn.", False),
], ids=["subject", "meeting-word", "class-activity", "not-after-khong-co", "a-skill", "gap-go", "sign-off"])
def test_the_meeting_flag(subject, text, meeting):
    assert read_times(subject, text, ARRIVED).meeting is meeting


@pytest.mark.parametrize("text, registered", [
    ("Bạn đã đăng ký thành công vào ngày 05/10/2026.", True),
    ("Cảm ơn bạn đã đăng ký tham gia chương trình.", True),
    ("Bạn đã xác nhận tham gia hội thảo.", True),
    ("Sinh viên đã đăng ký cần đến trước 07:15.", False),  # not "you"
    ("Những sinh viên đăng ký thành công sẽ tham gia vào 15/10.", False),
])
def test_the_registered_flag(text, registered):
    assert read_times("", text, ARRIVED).registered is registered


# ---- review fixes ------------------------------------------------------------------------------------------------------


def test_a_line_full_of_dates_and_times_is_read_quickly():
    import time as clock
    text = "14h ngày 05/10/2026, " * 600 + "\n" + "từ 8h ngày 1/10 đến 9h ngày 2/10, " * 300
    began = clock.perf_counter()
    read_times("", text, ARRIVED)
    assert clock.perf_counter() - began < 10


@pytest.mark.parametrize("text", [
    "Chương trình từ 17h00 ngày 05/11/2026 đến 16h00 ngày 05/11/2026.",
    "Chương trình từ 17h ngày 06/11/2026 đến 8h ngày 05/11/2026.",
])
def test_a_window_that_ends_before_it_starts_is_no_session(text):
    assert all(s.end is None or s.end > s.start for s in read_times("", text, ARRIVED).sessions)


def test_a_time_zone_that_moves_the_end_past_midnight_ends_the_next_day():
    [session] = read_times("", "The talk is at 8:00 AM - 10:00 AM PST on October 5, 2026.", ARRIVED).sessions
    assert (session.day, session.start, session.end, session.ends_next_day) == (
        date(2026, 10, 5), time(23, 0), time(1, 0), True)


@pytest.mark.parametrize("space", ["​", "﻿", "​ "])
def test_invisible_spaces_keep_a_range_whole(space):
    [session] = read_times("", f"Thời gian: 13:00{space}-{space}16:30 ngày 15/10/2026", ARRIVED).sessions
    assert (session.start, session.end) == (time(13, 0), time(16, 30))
