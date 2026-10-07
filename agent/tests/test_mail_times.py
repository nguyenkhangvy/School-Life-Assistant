"""The mail time reader: an email's sessions, Periods, deadlines and flags (spec 2026-10-07-mail-event-kinds-design.md
§4). The whole test set is in test_mail_times_cases.py; these tests pin each rule on its own."""

import unicodedata
from datetime import date

import pytest

from sla_agent.mail_times import _sentences, clean, read_times

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

    assert clean("", text) == "Đăng ký:   trước 30/9"


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
