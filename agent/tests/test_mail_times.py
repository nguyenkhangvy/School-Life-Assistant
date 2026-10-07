"""The mail time reader: an email's sessions, Periods, deadlines and flags (spec 2026-10-07-mail-event-kinds-design.md
§4). The whole test set is in test_mail_times_cases.py; these tests pin each rule on its own."""

import unicodedata

import pytest

from sla_agent.mail_times import _sentences, clean

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
