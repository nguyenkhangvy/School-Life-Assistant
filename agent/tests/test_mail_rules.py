"""Sorting one email on the laptop (spec 2026-09-28-outlook-mailbox-design.md, section 5)."""

import logging
import unicodedata
from datetime import date, datetime, time, timezone

import pytest

from sla_agent import mail_rules
from sla_agent.mail_rules import Context, Email, categories, course_of, is_from_lecturer, name_handles, sort_email
from sla_agent.mail_times import Found, FoundDeadline, FoundPeriod, FoundSession

ARRIVED = datetime(2026, 9, 21, 1, 5, tzinfo=timezone.utc)  # Mon 21/09 08:05 in Vietnam
CONTEXT = Context(
    courses=(("IT093IU", "Web Application Development", "P.Q.Hùng"),
             ("MA026IU", "Probability, Statistic & Random Process", "N.T.Hà"),
             ("PH012IU", "Physics 4", "Đ.V.Long")),
    bb_courses=(("Web Application Development_S1_2026-27_G02", "IT093IU"),
                ("Physics 4_S1_2026-27_G01", "PH012IU")),
)


def email(subject="Hello", text="", address="someone@example.com", name="Someone", received_at=ARRIVED):
    return Email(key="a" * 64, entry_id="00AB", thread_id="T1", received_at=received_at, sender_name=name,
                 sender_address=address, subject=subject, text=text)


# ---- who is a lecturer (5.1) --------------------------------------------------


@pytest.mark.parametrize("address, name", [
    ("bb@hcmiu.edu.vn", "Tran Van An - tvan@hcmiu.edu.vn"),  # a Blackboard announcement
    ("pqhung@hcmiu.edu.vn", "Web teacher"),  # P.Q.Hùng on the timetable
    ("vmkhoa@hcmiu.edu.vn", "Vo Minh Khoa"),  # initials + given name
    ("pqhung@hcmiu.edu.vn", "Hung Quoc Pham"),  # the name written the other way round
    ("buithanhnga@mp.hcmiu.edu.vn", "BUI THANH NGA"),  # the whole name, on an IU sub-domain
], ids=["blackboard", "timetable", "initials", "other-order", "whole-name-subdomain"])
def test_lecturers(address, name):
    assert is_from_lecturer(email(address=address, name=name), CONTEXT)


@pytest.mark.parametrize("address, name", [
    ("bb@hcmiu.edu.vn", "bb@hcmiu.edu.vn"),  # a "Submission received" receipt
    ("oss@hcmiu.edu.vn", "P.CTSV [OSS]"),
    ("hoisinhvien@hcmiu.edu.vn", "Hoi Sinh Vien IU"),
    ("iuyouth@hcmiu.edu.vn", "ĐOÀN TRƯỜNG ĐH QUỐC TẾ - IUYOUTH"),
    ("noreply.cis@hcmiu.edu.vn", "Reset Password"),
    ("iuoss@hcmiu.edu.vn", "IUOSS"),  # one word is not a person's name
    ("ttmai@student.hcmiu.edu.vn", "Tran Thi Mai"),  # a student
    ("vmkhoa@gmail.com", "Vo Minh Khoa"),  # not an IU address
], ids=["receipt", "oss", "union", "youth", "reset", "one-word", "student", "gmail"])
def test_not_lecturers(address, name):
    assert not is_from_lecturer(email(address=address, name=name), CONTEXT)


def test_a_teams_notice_from_a_lecturers_address_is_not_lecturer_mail():
    notice = email("Bạn đã được thêm vào một nhóm trong Microsoft Teams", address="dhtai@hcmiu.edu.vn",
                   name="Do Huu Tai")

    assert not is_from_lecturer(notice, CONTEXT)
    assert categories(notice, False) == ["class", "system_notice"]


def test_name_handles():
    assert name_handles("Võ Minh Khoa") == {"vmkhoa", "vominhkhoa", "kmvo", "khoaminhvo"}
    assert name_handles("Đặng Văn Long") >= {"dvlong"}
    assert name_handles("IUOSS") == set()


# ---- categories (5.2, 5.3) ------------------------------------------------------


@pytest.mark.parametrize("subject, text, address, expected", [
    ("[ M-Invoice ] TB: Xuất hóa đơn điện tử số 80652", "", "noreply@kiemtrahoadon.com.vn", ["money"]),
    ("[Thông báo] Chương trình học bổng của Tập đoàn Điện lực Việt Nam năm học 2026", "", "oss@hcmiu.edu.vn",
     ["money"]),
    ("Thông báo về việc đăng ký tạm trú và cập nhật thông tin cư trú", "", "oss@hcmiu.edu.vn", ["school_task"]),
    ("THÔNG BÁO: CHƯƠNG TRÌNH SINH HOẠT CÔNG DÂN GIỮA KHÓA (2026 - 2027)", "", "oss@hcmiu.edu.vn", ["school_task"]),
    ('V/v thực hiện "Khảo sát sự hài lòng của người học"', "SV tham gia đánh giá sẽ được cộng điểm rèn luyện.",
     "oss@hcmiu.edu.vn", ["school_task", "training_points"]),
    ('[THƯ MỜI] sinh viên tham gia WORKSHOP “TỪ GIẢNG ĐƯỜNG TỚI CÔNG SỞ"', "✨ Tích lũy điểm rèn luyện.",
     "oss@hcmiu.edu.vn", ["event", "training_points"]),
    ("[HSV] - Thư mời đăng ký tham gia Chương trình “Job hay ‘bẫy’?”",
     "Được công nhận hoạt động theo Quy chế sinh viên.", "hoisinhvien@hcmiu.edu.vn", ["event"]),
    ("[Thông báo] TIẾP NHẬN SINH VIÊN THAM GIA WORKSHOP: HỌC IELTS HIỆU QUẢ",
     "Nhận các phần quà và ưu đãi học tập hấp dẫn từ DOL English. Nhận điểm rèn luyện.", "oss@hcmiu.edu.vn",
     ["event", "training_points"]),
    ("[Thông báo] Mời sinh viên ủng hộ trường theo chương trình [IU x beFood] Bứt phá Vòng Chung Kết",
     "mang về giải thưởng học bổng 25.000.000 VNĐ. Nhập mã trường để áp dụng ưu đãi giảm 30%.", "oss@hcmiu.edu.vn",
     ["promotion"]),
    ("THÔNG TIN VỀ CUỘC THI TIẾNG ANH STAR AWARD", "Điểm rèn luyện chỉ được ghi nhận 01 lần.",
     "iuyouth@hcmiu.edu.vn", ["event", "training_points"]),
    ("Cảm ơn bạn đã điền vào biểu mẫu này: CHECK-OUT: GEMINI ACADEMY FOR STUDENTS | WORKSHOP 3", "",
     "forms-receipts-noreply@google.com", ["event"]),
    ("[Ticket: 12345] Trần Thị Mai – Yêu cầu mới được tạo", "", "oss@hcmiu.edu.vn", ["requests_account"]),
    ("Reset your password", "", "noreply.cis@hcmiu.edu.vn", ["requests_account"]),
    ("Your Teams meeting recording has expired and is now deleted", "", "no-reply@sharepointonline.com",
     ["system_notice"]),
    ("Submission received", "", "bb@hcmiu.edu.vn", ["class"]),
    ("Hello", "Nothing to see.", "friend@example.com", []),
    # Words written with other accents are other words; written without accents they still count.
    ("Lớp học bóng rổ miễn phí cho sinh viên", "", "clbbongro@hcmiu.edu.vn", []),
    ("Thử mới vị trà sữa – giảm giá 30%", "", "promo@shop.vn", ["promotion"]),
    ("Thong bao hoc phi hoc ky 1", "", "oss@hcmiu.edu.vn", ["money"]),
    ("Xuất hoá đơn điện tử số 123", "", "noreply@kiemtrahoadon.com.vn", ["money"]),
    (unicodedata.normalize("NFD", "Giảm giá 30% cho sinh viên"), "", "promo@shop.vn", ["promotion"]),
    # "không bắt buộc" is not required.
    ("Workshop kỹ năng mềm (không bắt buộc)", "", "oss@hcmiu.edu.vn", ["event"]),
    ("Khảo sát ý kiến sinh viên (không bắt buộc)", "", "oss@hcmiu.edu.vn", ["school_task"]),
    ("Sinh viên năm nhất bắt buộc tham gia buổi định hướng", "", "oss@hcmiu.edu.vn", ["school_task"]),
    # A reply to a ticket is still about the ticket.
    ("RE: FW: [Ticket: 4521] Lỗi đăng nhập", "", "oss@hcmiu.edu.vn", ["requests_account"]),
    # Only IU offices and staff give school tasks.
    ("Khảo sát nhận voucher 50k", "", "survey@brand.com", ["promotion"]),
    ("Nhờ các bạn làm khảo sát đồ án", "", "an.nv@student.hcmiu.edu.vn", []),
    ("Khảo sát về phòng thí nghiệm", "", "lab@mp.hcmiu.edu.vn", ["school_task"]),
], ids=["invoice", "scholarship", "residence", "civic-education", "survey", "workshop", "job-talk-no-points",
        "ielts-top-two", "befood-prize-is-not-money", "contest", "form-receipt", "ticket", "password", "sharepoint",
        "receipt", "nothing", "basketball-is-not-scholarship", "try-new-is-not-invitation", "no-accents",
        "tone-on-a", "accents-typed-apart", "not-required-event", "not-required-survey", "required", "ticket-reply", "brand-survey",
        "classmate-survey", "iu-subdomain-survey"])
def test_categories(subject, text, address, expected):
    assert categories(email(subject, text, address, name=address), False) == expected


def test_a_lecturers_email_is_class_first():
    assert categories(email("Thư mời workshop", "điểm rèn luyện"), True) == ["class", "event"]


# ---- dates (5.4) -------------------------------------------------------------------


def test_dates_come_from_the_subject_and_text_from_the_day_it_arrived():
    item = sort_email(email("Workshop ngày 29/09/2026", "Hạn đăng ký: 20/9. Check-in 13:00, 29/9."), CONTEXT)

    assert item.dates == [date(2026, 9, 29)]


# ---- class changes (5.5) -------------------------------------------------------------


def test_a_blackboard_copy_names_its_course_and_title():
    item = sort_email(email("Web Application Development_S1_2026-27_G02: Online class on 22/9", "",
                            "bb@hcmiu.edu.vn", "Tran Van An - tvan@hcmiu.edu.vn"), CONTEXT)

    assert (item.from_lecturer, item.blackboard_title) == (True, "Online class on 22/9")
    assert [(c.course_code, c.kind, c.day) for c in item.class_changes] == [("IT093IU", "online", date(2026, 9, 22))]


def test_an_email_naming_one_course_changes_that_course():
    item = sort_email(email("Physics 4: make-up class", "Make-up class on 3/10 from 1:15 to 3:45 PM in A2.401",
                            "vmkhoa@hcmiu.edu.vn", "Vo Minh Khoa"), CONTEXT)

    [change] = item.class_changes
    assert (change.course_code, change.kind, change.start, change.end, change.room) == (
        "PH012IU", "makeup", time(13, 15), time(15, 45), "A2.401")


def test_a_timetable_lecturer_changes_their_own_course():
    item = sort_email(email("Class cancelled", "No class on 24/9.", "pqhung@hcmiu.edu.vn", "Hung Quoc Pham"), CONTEXT)

    assert [(c.course_code, c.kind) for c in item.class_changes] == [("IT093IU", "cancelled")]


@pytest.mark.parametrize("subject, text, address, name", [
    ("Online class on 24/9", "", "oss@hcmiu.edu.vn", "P.CTSV [OSS]"),  # not a lecturer
    ("Online class on 24/9", "", "vmkhoa@hcmiu.edu.vn", "Vo Minh Khoa"),  # no course named, not on the timetable
    ("IT093IU and MA026IU: no class on 24/9", "", "vmkhoa@hcmiu.edu.vn", "Vo Minh Khoa"),  # two courses
], ids=["not-a-lecturer", "no-course", "two-courses"])
def test_no_class_change_without_a_lecturer_and_one_course(subject, text, address, name):
    assert sort_email(email(subject, text, address, name), CONTEXT).class_changes == []


def test_course_of_prefers_the_blackboard_course_name():
    copy = email("Physics 4_S1_2026-27_G01: Web Application Development notes", "", "bb@hcmiu.edu.vn",
                 "Đặng Văn Long - dvlong@hcmiu.edu.vn")

    assert course_of(copy, CONTEXT) == "PH012IU"


# ---- the whole email ------------------------------------------------------------------


def test_sessions_are_found_in_every_email_whatever_its_categories():
    item = sort_email(email("Họp lớp", "Họp lớp ngày 30/09/2026, 14h00 - 15h30."), CONTEXT)

    assert item.categories == []
    assert [(s.day, s.start, s.end) for s in item.sessions] == [(date(2026, 9, 30), time(14, 0), time(15, 30))]


def test_sessions_come_from_the_text_never_the_subject():
    with_check_in = email("[THƯ MỜI] Workshop 29/9 lúc 14h",
                          "Thời gian: 14:00 - 16:30, ngày 29/09/2026\nCheck in: 13:00 - 13:45, ngày 29/09/2026")
    subject_only = email("Link học online sáng thứ Sáu, 18/9/2026, 8g00-9g40", "Friday, September 18")

    assert [(s.day, s.start, s.end, s.check_in) for s in sort_email(with_check_in, CONTEXT).sessions] == [
        (date(2026, 9, 29), time(14, 0), time(16, 30), time(13, 0))]
    assert sort_email(subject_only, CONTEXT).sessions == []


def test_an_email_the_time_reader_fails_on_keeps_its_sorting_and_logs_no_text(monkeypatch, caplog):
    def broken(subject, text, arrived):
        raise ValueError(text)

    monkeypatch.setattr(mail_rules, "read_times", broken)

    with caplog.at_level(logging.WARNING):
        item = sort_email(email("Workshop ngày 30/9", "Bí mật riêng tư 12345, 14h00. Hạn đăng ký 25/9."), CONTEXT)

    assert (item.sorted, item.sessions, item.register_by, item.categories) == (True, [], None, ["event"])
    assert "Bí mật" not in caplog.text and "12345" not in caplog.text


# ---- what the upload holds (spec 2026-10-07-mail-event-kinds-design.md §3, from stage 2) ---------------------------


def test_everything_the_reader_finds_is_uploaded(monkeypatch):
    found = Found(
        sessions=(FoundSession(date(2026, 10, 20), time(13, 30), time(15, 30), end_is_approximate=True,
                               check_in=time(13, 0), mode="in_person", label="round_1"),
                  FoundSession(date(2026, 12, 31), time(22, 0), time(0, 30), ends_next_day=True,
                               link_opens=time(21, 45), mode="online", relative="tomorrow")),
        periods=(FoundPeriod(date(2026, 11, 2), date(2026, 11, 5), "daily_window", time(9), time(17), label="opening"),
                 FoundPeriod(date(2026, 10, 26), date(2026, 10, 30), "all_day", details_later=True)),
        deadlines=(FoundDeadline("opens", date(2026, 10, 8), time(8)),
                   FoundDeadline("register", date(2026, 10, 12), time(17), "online")),
        meeting=True, registered=True)
    monkeypatch.setattr(mail_rules, "read_times", lambda subject, text, arrived: found)

    item = sort_email(email("[THƯ MỜI] Cuộc thi", "…"), CONTEXT)

    assert [s.model_dump(mode="json", exclude_defaults=True) for s in item.sessions] == [
        {"day": "2026-10-20", "start": "13:30:00", "end": "15:30:00", "end_is_approximate": True,
         "check_in": "13:00:00", "mode": "in_person", "label": "round_1"},
        {"day": "2026-12-31", "start": "22:00:00", "end": "00:30:00", "ends_next_day": True, "link_opens": "21:45:00",
         "mode": "online", "relative": "tomorrow"}]
    assert [p.model_dump(mode="json", exclude_defaults=True) for p in item.periods] == [
        {"first_day": "2026-11-02", "last_day": "2026-11-05", "mode": "daily_window", "from_time": "09:00:00",
         "to_time": "17:00:00", "label": "opening"},
        {"first_day": "2026-10-26", "last_day": "2026-10-30", "mode": "all_day", "details_later": True}]
    assert [d.model_dump(mode="json", exclude_defaults=True) for d in item.deadlines] == [
        {"kind": "opens", "day": "2026-10-08", "time": "08:00:00"},
        {"kind": "register", "day": "2026-10-12", "time": "17:00:00", "mode": "online"}]
    assert (item.register_by, item.meeting, item.registered, item.invitation) == (date(2026, 10, 12), True, True, None)


def test_what_the_format_cant_hold_is_left_out_and_never_the_email(monkeypatch):
    found = Found(
        sessions=(FoundSession(date(2026, 10, 20), time(13, 30), time(13, 0), end_is_approximate=True,
                               check_in=time(14, 0), link_opens=time(13, 45)),),
        periods=(FoundPeriod(date(2026, 11, 2), date(2026, 11, 5), "daily_window", time(17), time(9)),
                 FoundPeriod(date(2026, 11, 2), date(2026, 11, 5), "all_day")))
    monkeypatch.setattr(mail_rules, "read_times", lambda subject, text, arrived: found)

    item = sort_email(email("[THƯ MỜI] Cuộc thi", "…"), CONTEXT)

    assert item.sorted
    assert [s.model_dump(mode="json", exclude_defaults=True) for s in item.sessions] == [
        {"day": "2026-10-20", "start": "13:30:00"}]
    assert [p.mode for p in item.periods] == ["all_day"]


def test_a_check_in_is_sent_apart_from_the_start():
    item = sort_email(email("[THƯ MỜI] Workshop", "Ngày 29/9/2026: check-in 13h00, chương trình 14h00 - 16h30."),
                      CONTEXT)

    assert [(s.start, s.end, s.check_in) for s in item.sessions] == [(time(14, 0), time(16, 30), time(13, 0))]


def test_a_lecturers_meeting_is_flagged_but_a_class_change_is_not():
    meeting = sort_email(email("Họp nhóm đồ án", "Cả nhóm gặp thầy lúc 10h00 ngày 02/10/2026 tại phòng A1.309.",
                               "vmkhoa@hcmiu.edu.vn", "Vo Minh Khoa"), CONTEXT)
    online = sort_email(email("Web Application Development_S1_2026-27_G02: Online class on 22/9",
                              "Our class on 22/9 will be online on MS Teams. Please join the meeting on time.",
                              "bb@hcmiu.edu.vn", "Tran Van An - tvan@hcmiu.edu.vn"), CONTEXT)

    assert (meeting.categories, meeting.meeting) == (["class"], True)
    assert [c.kind for c in online.class_changes] == ["online"]
    assert online.meeting is False


def test_the_registration_deadline_is_found_in_every_email():
    item = sort_email(email("Họp lớp", "Hạn đăng ký: 23h59 ngày 25/9/2026."), CONTEXT)

    assert (item.categories, item.register_by) == ([], date(2026, 9, 25))


def test_a_replys_quoted_part_gives_no_dates_and_no_sessions():
    reply = email("RE: Họp nhóm", "Ok em, gặp thầy ngày 05/10/2026 lúc 15h00 nhé.\n\nFrom: Đặng Văn Long\n"
                                  "Sent: Monday\nCả nhóm gặp thầy lúc 10h00 ngày 02/10/2026.")

    item = sort_email(reply, CONTEXT)

    assert item.dates == [date(2026, 10, 5)]
    assert [(s.day, s.start) for s in item.sessions] == [(date(2026, 10, 5), time(15, 0))]


@pytest.mark.parametrize("text", [
    "🎉" * 5000,
    "\u200b14:00\u200b ngày\u00a005/10/2026 \x00",
    "Thời gian: " + "x" * 200_000 + " 14h ngày 05/10",
    "Từ ngày 32/13/2026 đến 99/99, 25:61 - 13h",
], ids=["emoji", "invisible-characters", "a-very-long-line", "impossible-dates-and-times"])
def test_odd_texts_never_stop_an_email(text):
    item = sort_email(email("Thông báo", text), CONTEXT)

    assert item.sorted


def test_the_text_never_leaves_in_the_result():
    item = sort_email(email("Workshop", "UNIQUE-TEXT-7f3a only the laptop may read this"), CONTEXT)

    assert "UNIQUE-TEXT-7f3a" not in item.model_dump_json()


def test_an_email_the_rules_fail_on_is_uploaded_unsorted(monkeypatch, caplog):
    def broken(*args):
        raise ValueError("SECRET-SUBJECT-TEXT")

    monkeypatch.setattr(mail_rules, "categories", broken)
    caplog.set_level(logging.WARNING)

    item = sort_email(email("Tạm trú"), CONTEXT)

    assert (item.sorted, item.categories, item.subject) == (False, [], "Tạm trú")
    assert "SECRET-SUBJECT-TEXT" not in caplog.text
