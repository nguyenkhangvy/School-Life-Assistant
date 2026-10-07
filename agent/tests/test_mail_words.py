"""The word lists of the mail readers and the matcher that finds them (spec 2026-10-07-mail-event-kinds-design.md
§4.2)."""

import unicodedata

import pytest

from sla_agent import mail_words as words
from sla_agent.mail_words import Labels, Words, fold_in_place


def found(role, text):
    return [text[start:end] for start, end in role.spans(text)]


@pytest.mark.parametrize("text, expected", [
    ("Hạn chót đăng ký: 05/10", ["đăng ký"]),
    ("HAN DANG KY 05/10", ["DANG KY"]),  # written without accents: always counts
    ("Đăng Ký trước 12/10", ["Đăng Ký"]),  # any letter case
    ("Đăng kí trước 12/10", []),  # "kí" is not "ký": other accents, another word
    ("Bạn đã đăng ký thành công", []),  # "đã đăng ký" is done, not registering
])
def test_registration_words(text, expected):
    assert found(words.REGISTRATION, text) == expected


def test_the_tone_mark_may_sit_on_either_vowel():
    assert found(Words(("hóa đơn",)), "Xuất hoá đơn số 12") == ["hoá đơn"]


def test_spans_point_into_the_text_as_written():
    text = "Ngày 05/10: hạn đăng ký 12h00"

    [(start, end)] = words.CLOSING_STRONG.spans(text)

    assert text[start:end] == "hạn đăng ký"


def test_the_longest_phrase_wins_where_several_start():
    assert found(words.CLOSING_SOFT, "Form đăng ký mở đến 16:00 ngày 21/11") == ["mở đến"]


def test_words_right_after_unless_after_do_not_count():
    meeting = Words(("gặp", "thuyết trình"), unless_after=("không", "không có buổi"))

    assert found(meeting, "không có buổi gặp trực tiếp") == []
    assert found(meeting, "Không gặp được") == []
    assert found(meeting, "Nhóm gặp nhau lúc 9h") == ["gặp"]


def test_search_takes_any_text():
    assert words.MEETING.search(unicodedata.normalize("NFD", "Họp nhóm"))
    assert not words.MEETING.search(None)


def test_labels_give_their_codes():
    assert words.LABELS.spans("Vòng sơ loại diễn ra") == [(0, 12, "preliminary")]
    assert [code for _, _, code in Labels({"ca 1": "shift_1", "ca 2": "shift_2"}).spans("Ca 1: 8:00; Ca 2: 13:00")] == [
        "shift_1", "shift_2"]


def test_folding_in_place_keeps_every_position():
    text = "Đăng ký 14 giờ, ngày 05/10 🎉"

    folded = fold_in_place(text)

    assert len(folded) == len(text)
    assert folded.startswith("dang ky 14 gio")


@pytest.mark.parametrize("one, other", [
    (words.OPENING, words.CLOSING_STRONG), (words.OPENING, words.CLOSING_SOFT), (words.ONLINE, words.IN_PERSON),
    (words.MEETING, words.NOT_A_MEETING), (words.REGISTRATION, words.NOTICE), (words.ANY_TIME, words.DETAILS_LATER),
])
def test_no_word_is_in_two_roles_that_contradict_each_other(one, other):
    assert set(one.accents) & set(other.accents) == set()
