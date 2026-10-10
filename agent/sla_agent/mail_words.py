"""Every word the mail readers look for, by role and written as read (spec 2026-10-07-mail-event-kinds-design.md
§4.2), and Words, the matcher that finds them. Pure data and functions.

Words are compared without letter case. Written without accents they always count; written with accents, only with
their own, wherever the tone mark sits: "học bóng" is not "học bổng", but "hoá" is "hóa"."""

import re
import unicodedata
from functools import lru_cache

from sla_agent.class_changes import fold


@lru_cache(maxsize=None)
def _fold_letter(letter):
    return fold(letter)


@lru_cache(maxsize=16)
def _folded(text):
    """fold(text), and for each of its letters the place in `text` it comes from."""
    folded, places = [], []
    for place, letter in enumerate(text):
        for f in _fold_letter(letter):
            folded.append(f)
            places.append(place)
    return "".join(folded), places


def fold_in_place(text):
    """fold(text) letter by letter, so each position still points at the same letter of `text`."""
    return "".join(_fold_letter(letter)[:1] or " " for letter in text)


def _accents(word):
    """A word's accent marks in no order, so it doesn't matter where the tone mark sits: "hoá" and "hóa" give the
    same."""
    word = word.lower()
    marks = sorted(c for c in unicodedata.normalize("NFD", word) if unicodedata.combining(c))
    return "".join(marks) + "đ" * word.count("đ")


def _pattern(words):
    """Folded `words` as one alternation, longest first, so the longest phrase wins where several start."""
    folded = sorted({fold(word) for word in words}, key=len, reverse=True)
    return "|".join(r"\s+".join(re.escape(part) for part in word.split()) for word in folded)


class Words:
    """Words to look for, as whole words, in any letter case. Written without accents they always count; written with
    accents, only with their own, wherever the tone mark sits ("học bóng" is not "học bổng", "hoá" is "hóa").
    `unless_after`: words that cancel a match right before it ("không bắt buộc" is not "bắt buộc")."""

    def __init__(self, words, unless_after=()):
        self.accents = {}  # folded words -> the accents of each way they are written
        for word in words:
            self.accents.setdefault(fold(word), set()).add(tuple(_accents(part) for part in word.split()))
        self.pattern = re.compile(r"\b(?:" + _pattern(words) + r")\b")
        if isinstance(unless_after, str):
            unless_after = (unless_after,)
        self.unless_after = unless_after and re.compile(r"\b(?:" + _pattern(unless_after) + r")\s+$")

    def spans(self, text):
        """(start, end) of every match in `text`, which must be NFC, in order."""
        folded, places = _folded(text)
        found = []
        for match in self.pattern.finditer(folded):
            if self.unless_after and self.unless_after.search(folded, 0, match.start()):
                continue
            start, end = places[match.start()], places[match.end() - 1] + 1
            written = tuple(_accents(word) for word in text[start:end].split())
            if not any(written) or written in self.accents[" ".join(match.group().split())]:
                found.append((start, end))
        return found

    def search(self, text):
        return bool(self.spans(unicodedata.normalize("NFC", text or "")))


class Labels:
    """Words that name something from a fixed list: spans(text) gives (start, end, code)."""

    def __init__(self, codes):
        self.codes = {fold(word): code for word, code in codes.items()}
        self.words = Words(codes)

    def spans(self, text):
        return [(start, end, self.codes[" ".join(fold(text[start:end]).split())])
                for start, end in self.words.spans(text)]


# ---- registration and deadlines (§4.3, D) ----------------------------------------------------------------------------

# "Đã đăng ký" is something done (a notice), not registering.
REGISTRATION = Words(("đăng ký", "register", "registration", "sign up", "sign-up", "form", "biểu mẫu", "hồ sơ",
                      "đặt lịch", "ứng tuyển"), unless_after=("đã",))
# Only in a sentence with a registration word.
OPENING = Words(("mở đăng ký", "đăng ký từ", "mở từ", "form mở", "cổng mở", "bắt đầu nhận", "đăng ký bắt đầu",
                 "registration opens"))
# A deadline even without a kind word: then it is "due". ("Due to the rain" is not one: the reader checks.)
CLOSING_STRONG = Words(("hạn chót", "hạn cuối", "hạn đăng ký", "hạn nộp", "hạn xác nhận", "thời hạn", "deadline",
                        "due"))
# A deadline only with a kind word in its sentence. "kết thúc" and "đến" count only in a registration sentence;
# "trước" and "by" only right before a time or a date.
CLOSING_SOFT = Words(("đóng", "ngừng tiếp nhận", "mở đến", "đến hết", "trước", "by", "closes", "kết thúc", "đến"))
ONLY_IN_REGISTRATION = Words(("kết thúc", "đến"))
RIGHT_BEFORE = Words(("trước", "by"))
CONFIRM = Words(("xác nhận tham dự", "xác nhận tham gia", "xác nhận chỗ", "confirm attendance",
                 "confirm your attendance", "rsvp"))
DUE = Words(("nộp", "nộp bài", "báo cáo", "slide", "project", "đồ án", "bài tập", "bài kiểm tra", "học phí", "lệ phí",
             "thanh toán", "submit", "submission", "payment"), unless_after=("đã",))

# ---- the rest of an event (§4.3, S and P) ----------------------------------------------------------------------------

ARRIVAL = Words(("check-in", "check in", "checkin", "điểm danh", "có mặt", "đến trước", "vui lòng đến", "tập trung",
                 "đăng nhập", "vào khu vực", "đăng ký tại chỗ", "mở cửa từ", "be there by", "arrive by"))
DOORS = Words(("mở cửa",))  # with one time an arrival; with a time range open hours (any time)
LINK = Words(("link", "đường link", "đường dẫn"))
START = Words(("bắt đầu", "diễn ra", "tổ chức", "khởi hành", "starts", "begins"))
# An event's own time: "đăng ký tham gia workshop lúc 8h00 - 11h30" says when the workshop is, not a registration window.
AT = Words(("lúc", "vào lúc"))
END = Words(("kết thúc", "ends", "finishes"))
ANY_TIME = Words(("bất kỳ lúc nào", "bất kỳ thời điểm nào", "bất cứ lúc nào", "bất cứ thời điểm nào", "tùy nhu cầu",
                  "trong thời gian trên", "trong khung giờ trên", "trong khung giờ mở cửa", "không bắt buộc phải ở lại",
                  "không bắt buộc ở lại", "any time", "anytime"))
WITHIN = Words(("trong khoảng",))  # "diễn ra trong khoảng 09:00 đến 16:00": a span, not a session
DETAILS_LATER = Words(("thông báo sau", "sắp xếp riêng", "khung giờ riêng", "mỗi lượt", "đặt lịch", "gửi sau",
                       "email tiếp theo", "to be announced"))
PLACE = Words(("địa điểm", "địa chỉ", "venue", "location"))  # "Địa điểm: … thông báo sau" is about where, not when
EACH_DAY = Words(("mỗi ngày", "các buổi", "hằng ngày", "hàng ngày", "every day", "daily"))
EVENT = Words(("diễn ra", "tổ chức", "vòng", "lễ", "khai mạc", "bế mạc"))

# ---- what is not an event time (§4.3, N) -----------------------------------------------------------------------------

NOTICE = Words(("được gửi", "gửi lúc", "công bố", "tiếp nhận", "đã đăng ký", "đã xác nhận", "đã nộp", "sent at",
                "announced"))
RESCHEDULE = Words(("dời", "hoãn", "chuyển", "lùi", "postponed", "rescheduled"))
PIVOT = Words(("sang", "to"))  # the new time of a rescheduling comes after it
CANCEL = Words(("hủy", "cancel", "cancelled", "canceled"))
NOT_AN_EVENT = Words(("nghỉ", "chuyển từ phòng", "đổi phòng", "kỳ thi bắt đầu từ"))
SCORE = Words(("điểm trung bình", "điểm tích lũy", "điểm rèn luyện", "điểm học tập", "thang điểm", "ĐTB", "GPA", "CPA",
               "IELTS", "TOEIC", "TOEFL", "band"))

# ---- online or in person (§4.3, M) -----------------------------------------------------------------------------------

ONLINE = Words(("online", "trực tuyến", "zoom", "google meet", "teams", "livestream", "đăng nhập hệ thống"))
IN_PERSON = Words(("trực tiếp", "offline", "in person", "tại hội trường", "tại phòng", "tại cơ sở"))

# ---- flags (§2) ------------------------------------------------------------------------------------------------------

MEETING = Words(("họp", "cuộc họp", "gặp", "gặp mặt", "hẹn", "meeting", "buổi trao đổi", "tư vấn", "consultation",
                 "kiểm tra giữa kỳ", "kiểm tra cuối kỳ", "thi giữa kỳ", "thi cuối kỳ", "thuyết trình", "phỏng vấn"),
                unless_after=("không", "không có", "không có buổi", "kỹ năng"))
NOT_A_MEETING = Words(("gặp gỡ", "hẹn gặp lại"))  # meeting people at an event; a "see you again" sign-off
REGISTERED = Words(("bạn đã đăng ký", "em đã đăng ký", "bạn đã xác nhận", "em đã xác nhận", "cảm ơn bạn đã đăng ký",
                    "cảm ơn em đã đăng ký", "you have registered", "you are registered"))

# ---- times of day (§4.2) ---------------------------------------------------------------------------------------------

# Morning ("a") or afternoon ("p") for a time: "2h chiều" is 14:00. Matched with their accents, so "tôi" (I) and
# "tới" (to, next) are not "tối". "Trưa" is noon: only 1h–3h trưa are afternoon.
TIME_OF_DAY = Labels({"sáng": "a", "chiều": "p", "tối": "p", "trưa": "noon"})

# ---- labels and relative days (§3.2) ---------------------------------------------------------------------------------

LABELS = Labels({**{f"vòng {n}": f"round_{n}" for n in range(1, 6)}, **{f"ca {n}": f"shift_{n}" for n in range(1, 6)},
                 "sơ loại": "preliminary", "vòng sơ loại": "preliminary", "vòng loại": "qualifying",
                 "bán kết": "semifinal", "chung kết": "final", "vòng chung kết": "final", "khai mạc": "opening",
                 "lễ khai mạc": "opening", "bế mạc": "closing", "lễ bế mạc": "closing"})
TODAY = Words(("hôm nay", "sáng nay", "trưa nay", "chiều nay", "tối nay", "today", "tonight"))
TOMORROW = Words(("ngày mai", "sáng mai", "trưa mai", "chiều mai", "tối mai", "tomorrow"))
DAY_AFTER_TOMORROW = Words(("ngày kia", "ngày mốt"))
WEEKDAYS = Labels({**{f"thứ {name}": day for day, name in enumerate(("hai", "ba", "tư", "năm", "sáu", "bảy"))},
                   **{f"thứ {day + 2}": day for day in range(6)}, "chủ nhật": 6,
                   **{name: day for day, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday",
                                                            "saturday", "sunday"))}})
THIS_WEEK = Words(("tuần này", "this"))
NEXT_WEEK = Words(("tuần sau", "tuần tới", "next"))
WEEKDAY_FILTER = Words(("các ngày", "các", "mỗi", "every"))  # right before a weekday: "các ngày thứ Bảy"

# ---- cleaning (§4.1) -------------------------------------------------------------------------------------------------

OFFICE_HOURS = Words(("giờ làm việc", "working hours", "office hours"))
