"""Step 1 of the mail time reader: what one sentence holds, and where (spec 2026-10-07-mail-event-kinds-design.md
§4.2)."""

from datetime import date, timedelta

import pytest

from sla_agent.mail_phrases import clocks_in, days_in, lengths_in, parts_of, ranges_in, relative_day, weekday_filter

ARRIVED = date(2026, 9, 28)  # Mon, in Vietnam


def days(sentence):
    return [d.day for d in days_in(sentence, ARRIVED)]


def clocks(sentence):
    taken = [(d.start, d.end) for d in days_in(sentence, ARRIVED)] + [(n.start, n.end) for n in lengths_in(sentence)]
    return [(c.begin.strftime("%H:%M"), c.finish and c.finish.strftime("%H:%M")) for c in clocks_in(sentence, taken)]


def lengths(sentence):
    return [(n.minutes, n.approximate) for n in lengths_in(sentence)]


# ---- dates -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("written, day", [
    ("29/09/2026", date(2026, 9, 29)), ("27/9", date(2026, 9, 27)), ("18-9-2026", date(2026, 9, 18)),
    ("ngày 18 tháng 9", date(2026, 9, 18)), ("September 24", date(2026, 9, 24)), ("24th September", date(2026, 9, 24)),
    ("01.10.2026", date(2026, 10, 1)), ("05/10/26", date(2026, 10, 5)),
    ("02/01", date(2027, 1, 2)),  # no year: the one closest to the day the email arrived
])
def test_each_way_of_writing_a_date(written, day):
    assert days(f"Hội thảo {written}.") == [day]


def test_dates_carry_where_they_are():
    sentence = "Từ 26/10 đến 30/10"

    first, last = days_in(sentence, ARRIVED)

    assert (sentence[first.start:first.end], sentence[last.start:last.end]) == ("26/10", "30/10")


# ---- times -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("written, start", [
    ("13:00", "13:00"), ("13.00", "13:00"), ("13h", "13:00"), ("13h30", "13:30"), ("13g", "13:00"), ("8g30", "08:30"),
    ("14 giờ", "14:00"), ("14 giờ 30", "14:30"), ("14 giờ 30 phút", "14:30"), ("1:00 PM", "13:00"), ("1 PM", "13:00"),
    ("12 PM", "12:00"), ("12:30 AM", "00:30"), ("2:00 CH", "14:00"), ("8:00 SA", "08:00"),
])
def test_each_way_of_writing_a_time(written, start):
    assert clocks(f"Workshop lúc {written} ngày 01/10/2026") == [(start, None)]


@pytest.mark.parametrize("sentence, expected", [
    ("Workshop lúc 2h chiều", [("14:00", None)]),
    ("Họp lúc 7h tối", [("19:00", None)]),
    ("Meeting vào chiều thứ Sáu, bắt đầu lúc 3 giờ", [("15:00", None)]),  # the only time of day in the sentence
    ("Ngày 03/10: sáng 8h00 - 10h00, chiều 13h30 - 15h00", [("08:00", "10:00"), ("13:30", "15:00")]),
    ("Gặp lúc 11h trưa", [("11:00", None)]),
    ("Gặp lúc 1h trưa", [("13:00", None)]),
])
def test_morning_and_afternoon_words(sentence, expected):
    assert clocks(sentence) == expected


@pytest.mark.parametrize("sentence, expected", [
    ("Chúng tôi trân trọng kính mời bạn tham dự hội thảo lúc 8h30", [("08:30", None)]),  # "tôi" is "I"
    ("Phòng CTSV thông báo tới các bạn về buổi workshop lúc 9h", [("09:00", None)]),  # "tới" is "to"
    ("Buổi họp lớp sắp tới vào 8h30", [("08:30", None)]),  # "sắp tới": coming
    ("Họp lớp vào thứ Hai tuần tới lúc 9h", [("09:00", None)]),  # "tuần tới": next week
    ("Hop luc 7h toi", [("19:00", None)]),  # written without accents, "toi" may still be "tối"
])
def test_words_that_only_look_like_a_time_of_day(sentence, expected):
    assert clocks(sentence) == expected


@pytest.mark.parametrize("written", ["13:00 - 16:30", "13h00 – 16h30", "từ 13h đến 16h30", "1:00 – 4:30 PM",
                                     "13:00 until 16:30", "13:00\u00a0-\u00a016:30"])
def test_a_start_and_an_end(written):
    assert clocks(f"Thời gian: {written}") == [("13:00", "16:30")]


def test_a_range_written_with_colons():
    assert clocks("Thời gian: Từ: 13h00 Đến: 16h30") == [("13:00", "16:30")]


def test_a_range_ending_in_the_afternoon_starts_in_it_too():
    assert clocks("Từ 1h - 3h chiều") == [("13:00", "15:00")]


def test_an_end_that_is_not_after_its_start_is_dropped():
    assert clocks("22h00 - 01h00") == [("22:00", None)]


@pytest.mark.parametrize("sentence", [
    "Giải nhất 15.000.000 VNĐ", "Hotline 028.3724.4270", "Workshop (2h)", "Phòng A2.301",
    "Điều kiện: điểm trung bình từ 7.50 trở lên", "Thông báo ngày 01.10.2026", "Thời lượng: 1h30",
])
def test_not_times(sentence):
    assert clocks(sentence) == []


@pytest.mark.parametrize("written, hours", [("9:00 AM EST", -5), ("10:00 (GMT+8)", 8), ("14:00 ICT", 7),
                                            ("8:00 UTC", 0)])
def test_a_written_time_zone(written, hours):
    [clock] = clocks_in(f"Webinar at {written}", [])

    assert clock.offset == timedelta(hours=hours)


# ---- lengths ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("sentence, expected", [
    ("Workshop kéo dài 2 tiếng", [(120, False)]),
    ("Thời lượng: 1h30", [(90, False)]),
    ("Workshop diễn ra trong 2 giờ", [(120, False)]),
    ("Thời gian làm bài là 90 phút", [(90, False)]),
    ("Mỗi sinh viên chỉ có 15 phút", [(15, False)]),
    ("Kéo dài khoảng 2 giờ 30 phút", [(150, True)]),
    ("Họp khoảng 1 tiếng", [(60, True)]),
    ("Thời lượng dự kiến là 3 tiếng", [(180, True)]),
    ("Talk lasting 2h", [(120, False)]),
])
def test_lengths(sentence, expected):
    assert lengths(sentence) == expected


@pytest.mark.parametrize("sentence", ["Họp khoảng 2 giờ chiều", "Trong 15 phút đầu", "Có mặt trước 15 phút"])
def test_not_lengths(sentence):
    assert lengths(sentence) == []


@pytest.mark.parametrize("sentence, start", [
    ("Thời gian dự kiến: 14h00 ngày 20/10/2026", "14:00"),
    ("Workshop bắt đầu lúc 9h00, sau đó 13h30 tiếp tục phần thảo luận", "13:30"),
])
def test_a_time_after_du_kien_or_sau_do_is_a_time(sentence, start):
    assert lengths(sentence) == []
    assert start in [begin for begin, _ in clocks(sentence)]


def test_lengths_that_add_up_and_slot_lengths():
    presented = lengths_in("Thời gian trình bày là 15 phút, sau đó có 10 phút hỏi đáp")
    slot = lengths_in("Mỗi lượt tư vấn kéo dài khoảng 30 phút")

    assert [(n.minutes, n.adds) for n in presented] == [(15, False), (10, True)]
    assert [n.slot for n in slot] == [True]


# ---- parts -----------------------------------------------------------------------------------------------------------


def test_a_sentence_is_cut_into_parts_at_commas_and_semicolons():
    sentence = "Ngày 05/10: hạn 12h00, workshop 14h00; check-in 13h00"

    assert [sentence[a:b] for a, b in parts_of(sentence)] == ["Ngày 05/10: hạn 12h00", " workshop 14h00",
                                                              " check-in 13h00"]


# ---- ranges and windows ------------------------------------------------------------------------------------------------


def ranges(sentence, arrived=ARRIVED):
    found = days_in(sentence, arrived)
    taken = [(d.start, d.end) for d in found]
    day_ranges, windows = ranges_in(sentence, found, clocks_in(sentence, taken), arrived)
    return ([(r.first, r.last) for r in day_ranges],
            [(w.first, w.begin.strftime("%H:%M"), w.last, w.finish.strftime("%H:%M")) for w in windows])


@pytest.mark.parametrize("sentence", ["Tuần lễ diễn ra từ 26/10 đến 30/10/2026", "Thời gian: 26/10 – 30/10",
                                      "Từ ngày 26/10 đến ngày 30/10", "Trong khoảng 26/10 đến 30/10"])
def test_a_date_range(sentence):
    assert ranges(sentence) == ([(date(2026, 10, 26), date(2026, 10, 30))], [])


def test_from_now_until_a_date():
    assert ranges("Thời gian: 8h00 - 11h30 (Từ nay đến 30/09)") == ([(ARRIVED, date(2026, 9, 30))], [])


@pytest.mark.parametrize("sentence", ["Vòng 1 từ 8h00 ngày 01/10/2026 đến 17h00 ngày 05/10/2026",
                                      "Từ 01/10 lúc 8h00 đến 05/10 lúc 17h00"])
def test_a_window_from_a_time_on_one_day_to_a_time_on_another(sentence):
    assert ranges(sentence) == ([], [(date(2026, 10, 1), "08:00", date(2026, 10, 5), "17:00")])


@pytest.mark.parametrize("sentence", ["Ngày 29/09 và 01/10, 13:00–14:00", "Từ 30/10 đến 26/10"])
def test_not_ranges(sentence):
    assert ranges(sentence) == ([], [])


# ---- weekdays and relative days --------------------------------------------------------------------------------------


@pytest.mark.parametrize("sentence, weekday", [
    ("Lớp vào các ngày thứ Bảy từ 03/10 đến 24/10", 5), ("Sinh hoạt mỗi thứ Hai", 0), ("Thời gian: Thứ Ba, 29/9", None),
])
def test_a_weekday_filter(sentence, weekday):
    assert weekday_filter(sentence) == weekday


WEDNESDAY = date(2026, 10, 7)


@pytest.mark.parametrize("sentence, expected", [
    ("Họp vào 20:00 tối nay", ("today", date(2026, 10, 7))),
    ("2 giờ chiều mai mình gặp", ("tomorrow", date(2026, 10, 8))),
    ("8h sáng ngày kia có buổi họp", ("day_after_tomorrow", date(2026, 10, 9))),
    ("10h sáng thứ Năm tuần này", ("this_week", date(2026, 10, 8))),
    ("Workshop tuần sau tổ chức vào thứ Ba lúc 14h", ("next_week", date(2026, 10, 13))),
    ("Meeting vào chiều thứ Sáu", ("weekday", date(2026, 10, 9))),
    ("Họp vào thứ Tư", ("weekday", date(2026, 10, 14))),  # the next one after the day it arrived
    ("[Ticket] Trần Thị Mai – Yêu cầu mới", None),  # "Mai" alone is a name, not tomorrow
])
def test_relative_days(sentence, expected):
    assert relative_day(sentence, WEDNESDAY) == expected
