# Mail Time Reader (Stage 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The laptop agent reads every email's times with a new rule-based reader (sessions, Periods, deadlines and flags) and uploads what today's format holds. It ships as agent 0.5.0, together with the sorting fixes.

**Architecture:** Three new modules of pure functions in `agent/sla_agent/`:

- `mail_words.py` holds every word list, grouped by role, and the accent-aware matcher, which moves there from `mail_rules.py`.
- `mail_phrases.py` is step 1: the dates, times, ranges, windows and lengths in one sentence, with their positions.
- `mail_times.py` is step 0 (clean the text) and step 2 (decide what each phrase is). It returns a `Found`.

`mail_rules.sort_email` calls `read_times` once per email and maps the result to today's upload. The old finder (`sessions_in` and `register_by_in` in `class_changes.py`) is removed. The cases document the student checked becomes a JSON fixture, which an acceptance test and a scorecard read.

**Tech Stack:** Python 3.12 with the standard library only (`re`, `unicodedata`, `dataclasses`, `datetime`, `functools`), and pytest. `sla_contract` (pydantic) does not change.

**Spec:** [`docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md`](../specs/2026-10-07-mail-event-kinds-design.md), stage 1 (§4, §7, §8 and §9), with its test cases in [`2026-10-07-mail-event-kinds-cases.md`](../specs/2026-10-07-mail-event-kinds-cases.md). The rule names in the code's comments (D1, P4, S3 …) are those of the spec's §4.3.

## Global Constraints

- **Rules only.** "Still no email text leaves the laptop: only days, times, codes from fixed lists and yes/no flags" (§7.1). No AI service and no new dependency.
- **Failures:** "Reader failures log no email text, as today" (§7.4). When the reader fails on an email, the email is still sorted and uploaded, with no sessions and no `register_by`.
- **Stage 1 is agent only.** "Periods, the other deadlines and the flags are not sent. So stage 1 changes no website behaviour" (§4.4). Nothing in `contract/` or `web/` changes.
- **The upload (§4.4):** "sessions: the day, the start (the check-in when there is one, as A.1) and the end (none when the session ends the next day)"; "register_by: the latest register deadline's day".
- **Limits:** at most 10 sessions, 5 Periods and 5 deadlines. A heading line is read together with the next line only when it has no number and "at most 8 words" (§4.2).
- **Left as they are:** "The class-change reader `read_announcement` is untouched" (§4). The categories keep reading the whole email (§4.1).
- **Words:** every word list lives in `agent/sla_agent/mail_words.py`, "grouped by role and written as read" (§4).
- **Done:** "A stage is done when every case passes or is on the 'known misses' list in the cases document, which the student agrees to" (§8.3). The list is empty: all 127 cases pass.
- **Branch and version:** stage 1 "starts from the sorting fixes (branch `mail-rules-fixes`, 082ed22) and ships with them" (§9). Work on the branch `mail-event-kinds`. The version becomes **0.5.0**. Nothing is pushed, merged or released without the student's word.
- **Commands** run from the repository's folder (`School-Life-Assistant/School-Life-Assistant`): tests with `.venv/Scripts/python.exe -m pytest …` (the project's settings add `-q`), tools with `.venv/Scripts/python.exe -m agent.tools.…`.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and hold only the files the task lists. `docs/WA_Report_Group.docx` is not ours, and the worktrees `../security-hardening` and `../site-roles` belong to other work: leave all three alone.
- **Code style:** match the files around it. Docstrings say what a function gives, comments give a rule's reason, and names follow the spec (session, Period, deadline, arrival).

## Review Focus

1. **A reply whose own lines start with "Từ:"** ("Lịch họp nhóm: / Từ: 14h00 / Đến: 16h00 / Ngày: 05/10/2026") keeps those lines: "Từ: 14h00" is a time, not the start of a quoted email. Pinned in Task 5 by `test_a_replys_own_time_lines_are_not_a_quote`.
2. **Non-breaking and invisible spaces** read like plain spaces, so a range stays a range: Outlook can put a no-break space (U+00A0) on each side of the dash in "13:00 - 16:30", and pasted text can hold zero-width spaces (U+200B). Pinned in Task 3 by `test_a_start_and_an_end` (its U+00A0 case) and in Task 11 by `test_odd_texts_never_stop_an_email`.
3. **Odd texts never stop an email:** emoji, invisible characters, a line of 200,000 letters, impossible dates and times. The email is still sorted. Pinned in Task 11 by `test_odd_texts_never_stop_an_email`.
4. **A break inside an event** ("Nghỉ giải lao 09:30 - 09:45.") drops only its own line; the event around it stays whole. Pinned in Task 8 by `test_what_is_dropped`.
5. **A closing word never points into a range:** "Đăng ký tham gia Tuần lễ diễn ra từ 26/10 đến 30/10." gives no register deadline, because the range is the event. Pinned in Task 6 by `test_not_deadlines`.

## File Structure

```text
agent/sla_agent/mail_words.py       new   Task 1       every word list, by role; Words and Labels, the accent-aware matcher
agent/sla_agent/mail_phrases.py     new   Tasks 3–4    step 1: days_in, clocks_in, lengths_in, parts_of, ranges_in,
                                                       weekday_filter, relative_day
agent/sla_agent/mail_times.py       new   Tasks 5–9    step 0 (clean, _sentences) and step 2; read_times -> Found
agent/sla_agent/mail_rules.py       edit  Tasks 1, 11  the matcher moves out; times_of and upload_sessions; sort_email
                                                       uses the reader
agent/sla_agent/class_changes.py    edit  Task 11      the old session finder and registration-deadline reader go
agent/sla_agent/__init__.py         edit  Task 13      version 0.5.0
agent/tools/mail_times_cases.py     new   Task 2       the cases document -> agent/tests/fixtures/mail-times-cases.json
agent/tools/mail_times_score.py     new   Task 10      the scorecard, and as_case_fields(found)
agent/tools/anonymize_mail.py       edit  Task 12      each real sample also keeps `found`
agent/tests/                        new   test_mail_words.py, test_mail_times_cases_tool.py, test_mail_phrases.py,
                                          test_mail_times.py, test_mail_times_score.py, test_mail_times_cases.py
                                    edit  test_mail_rules.py, test_sessions.py, test_anonymize_mail.py,
                                          test_mail_samples.py
agent/tests/fixtures/               new   mail-times-cases.json (Task 2, written by the tool)
                                    edit  mail-samples.json (Task 11: samples 20, 23, 24; Task 12: `found`)
docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md     edit  Task 13  status
```

`mail_times.py` grows over Tasks 5–9. When Task 9 is done, its sections read, from the top:

```text
imports and constants
# ---- what the reader finds              FoundSession, FoundPeriod, FoundDeadline, Found
# ---- step 0: clean the text (§4.1)      _before_quote, clean, _sentences
# ---- step 1: one sentence's phrases …   _Sentence, _target, _moment, _within, _label
# ---- step 2: what each sentence takes … _drop, _arrivals, _kind, _deadlines, _links, _notices
# ---- step 2: Periods (§4.3, P)          _says_later, _periods
# ---- step 2: sessions (§4.3, S)         _day_source, _neighbour_days, _session_days, _sessions, _join,
                                          _check_ins, _link_times, _one_day_periods
# ---- what is kept, with its mode …      _Modes, _kept_deadlines, _kept_periods, _kept_sessions
# ---- flags (§2)                         _flag
# ---- the reader                         read_times
```

Each section line is `# ---- <title> ` followed by dashes up to 120 characters, as in the code below.

**How the tasks fit together.** Tasks 1–10 add the new reader beside the old finder, which keeps sorting emails until Task 11 switches `sort_email` over and removes it. Task 12 stores the reader's full results in the real samples, and the student checks them. Task 13 sets the version.

---

### Task 1: The word lists and the matcher (`mail_words.py`)

The sorting fixes made an accent-aware matcher inside `mail_rules.py`: words written without accents always count, words written with accents count only with their own. The time reader needs the same matcher and many more word lists, so both move to one module. The matcher also learns three things: `spans` (where each match is), several `unless_after` words, and "the longest phrase wins where several start".

**Files:**
- Create: `agent/sla_agent/mail_words.py`
- Modify: `agent/sla_agent/mail_rules.py` (the matcher moves out)
- Test: `agent/tests/test_mail_words.py`

**Interfaces:**
- Consumes: `class_changes.fold(text) -> str` (lower case, no accents).
- Produces:
  - `Words(words, unless_after=())`. `.spans(text) -> list[tuple[int, int]]` gives the matches in `text`, which must be NFC, as positions in it. `.search(text) -> bool` takes any text, `None` too. `.accents` maps each folded word to the accents it is written with. `unless_after` is one word or a tuple of words.
  - `Labels(codes: dict[str, str])`, whose `.spans(text) -> list[tuple[int, int, str]]` also gives each match's code.
  - `fold_in_place(text) -> str`: `fold` letter by letter, so it has the length of `text`.
  - The roles, each a `Words`: `REGISTRATION`, `OPENING`, `CLOSING_STRONG`, `CLOSING_SOFT`, `ONLY_IN_REGISTRATION`, `RIGHT_BEFORE`, `CONFIRM`, `DUE`, `ARRIVAL`, `DOORS`, `LINK`, `START`, `END`, `ANY_TIME`, `WITHIN`, `DETAILS_LATER`, `PLACE`, `EACH_DAY`, `EVENT`, `NOTICE`, `RESCHEDULE`, `PIVOT`, `CANCEL`, `NOT_AN_EVENT`, `SCORE`, `ONLINE`, `IN_PERSON`, `MEETING`, `NOT_A_MEETING`, `REGISTERED`, `TODAY`, `TOMORROW`, `DAY_AFTER_TOMORROW`, `THIS_WEEK`, `NEXT_WEEK`, `WEEKDAY_FILTER`, `OFFICE_HOURS`. `LABELS` and `WEEKDAYS` are `Labels`: `LABELS` gives the spec's label codes (§3.2, for example `round_1`, `final`), and `WEEKDAYS` gives 0–6, with Monday as 0.
  - `mail_rules` keeps all its names and imports `Words` from here.

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_mail_words.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_words.py`
Expected: FAIL while collecting: `ImportError: cannot import name 'mail_words' from 'sla_agent'`.

- [ ] **Step 3: Write `mail_words.py`**

Create `agent/sla_agent/mail_words.py`:

```python
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
```

- [ ] **Step 4: Move the matcher out of `mail_rules.py`**

The sorting rules work as before; they now use the shared matcher.

In `agent/sla_agent/mail_rules.py`, delete the matcher, which now lives in `mail_words.py`: `_fold_letter`, `_folded`, `_accents` and `class Words` (lines 73–119): from the line `@lru_cache(maxsize=None)` through the line `        return False`, and the blank lines after it.

In `agent/sla_agent/mail_rules.py`, replace:

```python
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime, timedelta, timezone
```

with:

```python
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
from sla_agent.class_changes import dates_in, fold, read_announcement, register_by_in, sessions_in
```

with:

```python
from sla_agent.class_changes import dates_in, fold, read_announcement, register_by_in, sessions_in
from sla_agent.mail_words import Words
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
# writes them (see Words).
```

with:

```python
# writes them (see mail_words.Words).
```

- [ ] **Step 5: Run the word tests and the sorting tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_words.py agent/tests/test_mail_rules.py agent/tests/test_mail_samples.py`
Expected: PASS (`135 passed`)

- [ ] **Step 6: Commit**

```bash
git add agent/sla_agent/mail_words.py agent/sla_agent/mail_rules.py agent/tests/test_mail_words.py
git commit -m "feat(agent): mail_words, every word the mail time reader looks for, by role; the accent-aware matcher moves there from mail_rules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The test cases as a fixture (`mail_times_cases.py`)

The 127 cases the student checked live in the cases document, written for people ("Thu 15/10 from 14:00 · check-in 13:45"). This tool turns them into `agent/tests/fixtures/mail-times-cases.json`, which Task 10's acceptance test and scorecard read. A test checks that the fixture matches the document, so the two cannot drift apart.

**Files:**
- Create: `agent/tools/mail_times_cases.py`, `agent/tests/fixtures/mail-times-cases.json` (written by the tool)
- Test: `agent/tests/test_mail_times_cases_tool.py`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-10-07-mail-event-kinds-cases.md`, committed with this plan.
- Produces:
  - `read(doc) -> list[dict]`, `session(line) -> dict`, `period(line) -> dict`, `deadline(text) -> dict`, and the paths `DOC` and `FIXTURE`.
  - The fixture `{"cases": [...]}`. Each case has `id` ("Mail 01" … "Mail 100", "C1" … "C27"), `arrived` (an ISO date), `subject`, `text`, `sessions`, `periods`, `deadlines`, `meeting` and `registered`.
  - A session has `day`, `start`, `end`, `end_is_approximate`, `ends_next_day`, `check_in`, `link_opens`, `mode`, `relative` and `label`. A Period has `first_day`, `last_day`, `mode`, `from_time`, `to_time`, `details_later` and `label`. A deadline has `kind`, `day`, `time` and `mode`.
  - Days are ISO dates, times are "HH:MM", and codes are the spec's (§3.2).

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_mail_times_cases_tool.py`:

````python
"""The tool that turns the checked cases document into agent/tests/fixtures/mail-times-cases.json (spec
2026-10-07-mail-event-kinds-design.md §8)."""

import json

import pytest

from agent.tools.mail_times_cases import DOC, FIXTURE, deadline, period, read, session

NO_DETAILS = dict(end=None, end_is_approximate=False, ends_next_day=False, check_in=None, link_opens=None, mode=None,
                  relative=None, label=None)


@pytest.mark.parametrize("line, expected", [
    ("Thu 15/10 from 14:00 · check-in 13:45", dict(NO_DETAILS, day="2026-10-15", start="14:00", check_in="13:45")),
    ("Thu 08/10 10:00–~11:00 · day from a relative word (this week)",
     dict(NO_DETAILS, day="2026-10-08", start="10:00", end="11:00", end_is_approximate=True, relative="this_week")),
    ("Thu 31/12 22:00 – Fri 01/01/2027 00:30 (ends the next day) · check-in 21:30",
     dict(NO_DETAILS, day="2026-12-31", start="22:00", end="00:30", ends_next_day=True, check_in="21:30")),
    ("Sun 18/10 from 09:30 · link opens 09:00 · online",
     dict(NO_DETAILS, day="2026-10-18", start="09:30", link_opens="09:00", mode="online")),
    ("Thu 03/12 09:00–12:00 · online · label Qualifying round",
     dict(NO_DETAILS, day="2026-12-03", start="09:00", end="12:00", mode="online", label="qualifying")),
])
def test_session_lines(line, expected):
    assert session(line) == expected


@pytest.mark.parametrize("line, expected", [
    ("Mon 26/10 → Fri 30/10 · all day", dict(first_day="2026-10-26", last_day="2026-10-30", mode="all_day")),
    ("Tue 20/10 · all day · label Round 1", dict(first_day="2026-10-20", last_day="2026-10-20", mode="all_day",
                                                 label="round_1")),
    ("Mon 02/11 → Thu 05/11 · 09:00–17:00 each day",
     dict(first_day="2026-11-02", last_day="2026-11-05", mode="daily_window", from_time="09:00", to_time="17:00")),
    ("Sat 28/11 09:00 → Sun 29/11 16:00",
     dict(first_day="2026-11-28", last_day="2026-11-29", mode="one_window", from_time="09:00", to_time="16:00")),
    ("Wed 18/11 · 09:00–16:00 · details later",
     dict(first_day="2026-11-18", last_day="2026-11-18", mode="one_window", from_time="09:00", to_time="16:00",
          details_later=True)),
])
def test_period_lines(line, expected):
    assert period(line) == dict(dict(from_time=None, to_time=None, details_later=False, label=None), **expected)


@pytest.mark.parametrize("text, expected", [
    ("registration opens Thu 08/10", dict(kind="opens", day="2026-10-08", time=None, mode=None)),
    ("register by 17:00 Mon 12/10", dict(kind="register", day="2026-10-12", time="17:00", mode=None)),
    ("confirm by 12:00 Wed 14/10", dict(kind="confirm", day="2026-10-14", time="12:00", mode=None)),
    ("due 23:59 Sun 25/10", dict(kind="due", day="2026-10-25", time="23:59", mode=None)),
    ("register by 12:00 Sat 03/10 (in person)", dict(kind="register", day="2026-10-03", time="12:00", mode="in_person")),
])
def test_deadlines(text, expected):
    assert deadline(text) == expected


DOCUMENT = """# Mail event kinds: test cases

## Group A: mails 01–50 (arrive Wed 07/10/2026; the student's key)

### Mail 01 · Hội thảo

```text
Hội thảo vào 14:00 ngày 15/10/2026.
Có mặt trước 13:45.
```

- **Session:** Thu 15/10 from 14:00 · check-in 13:45
- **Deadlines:** registration opens Thu 08/10 · register by 17:00 Mon 12/10 (online)
- **Flags:** meeting

## Group C: short cases (arrive Mon 28/09/2026; checked by the student)

### C01 · Lịch ca

```text
Ca 1: 8:00–10:00; Ca 2: 13:00–15:00 ngày 30/9
```

- **Sessions:**
  - Wed 30/09 08:00–10:00 · label Shift 1
  - Wed 30/09 13:00–15:00 · label Shift 2
- *Note:* two shifts.

### C02 · Nothing

```text
Hello.
```

- **Nothing.**
"""


def test_reading_a_document():
    one, two, three = read(DOCUMENT)

    assert one == dict(
        id="Mail 01", arrived="2026-10-07", subject="Hội thảo", text="Hội thảo vào 14:00 ngày 15/10/2026.\nCó mặt trước 13:45.",
        sessions=[dict(NO_DETAILS, day="2026-10-15", start="14:00", check_in="13:45")], periods=[],
        deadlines=[dict(kind="opens", day="2026-10-08", time=None, mode=None),
                   dict(kind="register", day="2026-10-12", time="17:00", mode="online")],
        meeting=True, registered=False)
    assert (two["id"], two["arrived"], [s["label"] for s in two["sessions"]]) == ("C01", "2026-09-28", ["shift_1", "shift_2"])
    assert (three["sessions"], three["periods"], three["deadlines"], three["meeting"]) == ([], [], [], False)


def test_a_line_it_does_not_understand_stops_it():
    with pytest.raises(ValueError):
        read(DOCUMENT.replace("- **Nothing.**", "- **Sesions:** Thu 15/10 from 14:00"))


def test_the_fixture_is_the_cases_document():
    if not DOC.exists():
        pytest.skip("the docs folder is not next to the agent")

    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == {"cases": read(DOC.read_text(encoding="utf-8"))}
````

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times_cases_tool.py`
Expected: FAIL while collecting: `ModuleNotFoundError: No module named 'agent.tools.mail_times_cases'`.

- [ ] **Step 3: Write the tool**

Create `agent/tools/mail_times_cases.py`:

````python
"""The mail time reader's test cases (spec 2026-10-07-mail-event-kinds-design.md §8): reads them from the cases
document the student checked and writes them as agent/tests/fixtures/mail-times-cases.json.

Run from the repository's folder after changing the cases document:

    python -m agent.tools.mail_times_cases
"""

import json
import re
from datetime import date
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
DOC = AGENT.parent / "docs" / "superpowers" / "specs" / "2026-10-07-mail-event-kinds-cases.md"
FIXTURE = AGENT / "tests" / "fixtures" / "mail-times-cases.json"

GROUP = re.compile(r"^## Group .*\(arrive \w{3} (\d{2})/(\d{2})/(\d{4})")
CASE = re.compile(r"^### (Mail \d+|C\d+) · (.*)$")
DAY = r"\w{3} (\d{2})/(\d{2})(?:/(\d{4}))?"
CLOCK = r"(\d{2}:\d{2})"
LABELS = {f"Round {n}": f"round_{n}" for n in range(1, 6)} | {f"Shift {n}": f"shift_{n}" for n in range(1, 6)} | {
    "Preliminary round": "preliminary", "Qualifying round": "qualifying", "Semi-final": "semifinal",
    "Final": "final", "Opening": "opening", "Closing": "closing"}
RELATIVE = {"today": "today", "tomorrow": "tomorrow", "the day after tomorrow": "day_after_tomorrow",
            "this week": "this_week", "next week": "next_week", "a weekday alone": "weekday"}
MODES = {"online": "online", "in person": "in_person"}
KINDS = {"registration opens": "opens", "register by": "register", "confirm by": "confirm", "due": "due"}


def _day(d, m, y):
    """A day as the document writes it: the year is left out when it is 2026."""
    return date(int(y or 2026), int(m), int(d)).isoformat()


def session(written):
    """One "Session:" line of the document, as the reader's session fields."""
    head, *extras = written.split(" · ")
    if m := re.fullmatch(rf"{DAY} from {CLOCK}", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), None, False, False
    elif m := re.fullmatch(rf"{DAY} {CLOCK}–(~?){CLOCK}", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), m.group(6), bool(m.group(5)), False
    elif m := re.fullmatch(rf"{DAY} {CLOCK} – {DAY} {CLOCK} \(ends the next day\)", head):
        day, start, end, approximate, next_day = _day(*m.group(1, 2, 3)), m.group(4), m.group(8), False, True
    else:
        raise ValueError(f"not a session: {written}")
    found = dict(day=day, start=start, end=end, end_is_approximate=approximate, ends_next_day=next_day, check_in=None,
                 link_opens=None, mode=None, relative=None, label=None)
    for extra in extras:
        if m := re.fullmatch(rf"check-in {CLOCK}", extra):
            found["check_in"] = m.group(1)
        elif m := re.fullmatch(rf"link opens {CLOCK}", extra):
            found["link_opens"] = m.group(1)
        elif extra in MODES:
            found["mode"] = MODES[extra]
        elif m := re.fullmatch(r"day from a relative word \((.+)\)", extra):
            found["relative"] = RELATIVE[m.group(1)]
        elif extra.startswith("label "):
            found["label"] = LABELS[extra.removeprefix("label ")]
        else:
            raise ValueError(f"not a session detail: {extra}")
    return found


def period(written):
    """One "Period:" line of the document, as the reader's period fields."""
    pieces = written.split(" · ")
    found = dict(first_day=None, last_day=None, mode=None, from_time=None, to_time=None, details_later=False, label=None)
    if m := re.fullmatch(rf"{DAY} {CLOCK} → {DAY} {CLOCK}", pieces[0]):
        found.update(first_day=_day(*m.group(1, 2, 3)), last_day=_day(*m.group(5, 6, 7)), mode="one_window",
                     from_time=m.group(4), to_time=m.group(8))
        rest = pieces[1:]
    else:
        if m := re.fullmatch(rf"{DAY} → {DAY}", pieces[0]):
            first, last = _day(*m.group(1, 2, 3)), _day(*m.group(4, 5, 6))
        elif m := re.fullmatch(DAY, pieces[0]):
            first = last = _day(*m.group(1, 2, 3))
        else:
            raise ValueError(f"not a period: {written}")
        found.update(first_day=first, last_day=last)
        if len(pieces) > 1 and pieces[1] == "all day":
            found["mode"] = "all_day"
        elif len(pieces) > 1 and (m := re.fullmatch(rf"{CLOCK}–{CLOCK} each day", pieces[1])):
            found.update(mode="daily_window", from_time=m.group(1), to_time=m.group(2))
        elif len(pieces) > 1 and (m := re.fullmatch(rf"{CLOCK}–{CLOCK}", pieces[1])) and first == last:
            found.update(mode="one_window", from_time=m.group(1), to_time=m.group(2))
        else:
            raise ValueError(f"not a period: {written}")
        rest = pieces[2:]
    for extra in rest:
        if extra == "details later":
            found["details_later"] = True
        elif extra.startswith("label "):
            found["label"] = LABELS[extra.removeprefix("label ")]
        else:
            raise ValueError(f"not a period detail: {extra}")
    return found


def deadline(written):
    """One deadline of a "Deadlines:" line, as the reader's deadline fields."""
    m = re.fullmatch(rf"(registration opens|register by|confirm by|due) (?:{CLOCK} )?{DAY}(?: \((online|in person)\))?",
                     written)
    if not m:
        raise ValueError(f"not a deadline: {written}")
    return dict(kind=KINDS[m.group(1)], day=_day(*m.group(3, 4, 5)), time=m.group(2),
                mode=MODES[m.group(6)] if m.group(6) else None)


def read(doc):
    """[case] in the order of the document."""
    cases, arrived, case, lines, listing = [], None, None, iter(doc.splitlines()), None
    for line in lines:
        if m := GROUP.match(line):
            arrived = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        elif m := CASE.match(line):
            case = dict(id=m.group(1), arrived=arrived, subject=m.group(2), text=None, sessions=[], periods=[],
                        deadlines=[], meeting=False, registered=False)
            cases.append(case)
            listing = None
        elif case is None:
            continue
        elif line == "```text":
            body = []
            for line in lines:
                if line == "```":
                    break
                body.append(line)
            case["text"] = "\n".join(body)
        elif m := re.fullmatch(r"- \*\*(Session|Period):\*\* (.+)", line):
            case["sessions" if m.group(1) == "Session" else "periods"].append(
                (session if m.group(1) == "Session" else period)(m.group(2)))
        elif m := re.fullmatch(r"- \*\*(Sessions|Periods):\*\*", line):
            listing = m.group(1).lower()
        elif listing and (m := re.fullmatch(r"  - (.+)", line)):
            case[listing].append((session if listing == "sessions" else period)(m.group(1)))
        elif m := re.fullmatch(r"- \*\*Deadlines:\*\* (.+)", line):
            case["deadlines"] = [deadline(d) for d in m.group(1).split(" · ")]
        elif m := re.fullmatch(r"- \*\*Flags:\*\* (.+)", line):
            for flag in m.group(1).split(", "):
                case[flag] = True
        elif line.startswith("- ") and not line.startswith(("- *Note:*", "- **Nothing.**")):
            raise ValueError(f"{case['id']}: not understood: {line}")
    return cases


def main():
    cases = read(DOC.read_text(encoding="utf-8"))
    FIXTURE.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases written to {FIXTURE}")


if __name__ == "__main__":
    main()
````

- [ ] **Step 4: Write the fixture**

Run: `.venv/Scripts/python.exe -m agent.tools.mail_times_cases`
Expected: it prints `127 cases written to …\agent\tests\fixtures\mail-times-cases.json`.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times_cases_tool.py`
Expected: PASS (`18 passed`)

- [ ] **Step 6: Commit**

```bash
git add agent/tools/mail_times_cases.py agent/tests/test_mail_times_cases_tool.py agent/tests/fixtures/mail-times-cases.json
git commit -m "test(agent): the mail time reader's 127 checked cases, read from the cases document into a fixture

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Step 1, part 1: dates, times and lengths (`mail_phrases.py`)

Step 1 finds the phrases of one sentence, with their positions, and decides nothing. This task covers dates, times, time ranges and lengths, and cuts a sentence into parts at commas and semicolons.

**Files:**
- Create: `agent/sla_agent/mail_phrases.py`
- Test: `agent/tests/test_mail_phrases.py`

**Interfaces:**
- Consumes: `class_changes.MAIL_DATE_FORMATS`, `MONTH_NAMES` and `fold`; `mail_words.SCORE` (a number after a score word is not a time).
- Produces:
  - Frozen dataclasses: `Day(start, end, day)`, `Clock(start, end, begin, finish=None, offset=None)` and `Length(start, end, minutes, approximate, slot, adds)`. `start` and `end` are positions in the sentence.
  - `days_in(sentence, arrived) -> list[Day]`, in order. A date without a year takes the year closest to `arrived`.
  - `lengths_in(sentence) -> list[Length]`.
  - `clocks_in(sentence, taken) -> list[Clock]`: the times outside the `(start, end)` spans in `taken` (the caller passes the sentence's dates and lengths). A time range is one `Clock` with a `finish`. `offset` is a written time zone's offset from UTC; the caller turns the time into Vietnam time.
  - `parts_of(sentence) -> list[tuple[int, int]]`: the parts between commas and semicolons.
  - The constants `VIETNAM` (7 hours) and `JOIN`, which Task 4 uses too.

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_mail_phrases.py`:

```python
"""Step 1 of the mail time reader: what one sentence holds, and where (spec 2026-10-07-mail-event-kinds-design.md
§4.2)."""

from datetime import date, timedelta

import pytest

from sla_agent.mail_phrases import clocks_in, days_in, lengths_in, parts_of

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


@pytest.mark.parametrize("written", ["13:00 - 16:30", "13h00 – 16h30", "từ 13h đến 16h30", "1:00 – 4:30 PM",
                                     "13:00 until 16:30", "13:00\u00a0-\u00a016:30"])
def test_a_start_and_an_end(written):
    assert clocks(f"Thời gian: {written}") == [("13:00", "16:30")]


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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_phrases.py`
Expected: FAIL while collecting: `ModuleNotFoundError: No module named 'sla_agent.mail_phrases'`.

- [ ] **Step 3: Write `mail_phrases.py`**

Create `agent/sla_agent/mail_phrases.py`:

```python
"""Step 1 of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4.2): the dates, times, ranges,
windows and lengths one sentence holds, and where they are. Pure functions."""

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

from sla_agent import mail_words as words
from sla_agent.class_changes import MAIL_DATE_FORMATS, MONTH_NAMES, fold

# A date with a two-digit year: "05/10/26".
SHORT_YEAR = re.compile(r"(?<![\w/.:])(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<short>\d{2})(?![\d/])")
DATE_FORMATS = [SHORT_YEAR] + MAIL_DATE_FORMATS
# A time: 13:00, 13.00, 13h, 13h30, 13g, 8g30, 14 giờ, 14 giờ 30 (phút), 1 PM, 1:30 pm, 2:00 CH, 8:00 SA. "01.10"
# followed by ".2026" is a date, and "15.000.000" money.
TIME = re.compile(
    r"(?<![\w/.:,])(?P<hour>\d{1,2})"
    r"(?:\s*gi[ờo](?:\s*(?P<gminute>\d{1,2})(?:\s*ph[úu]t)?)?(?!\w)"
    r"|(?:[:.](?=\d{2})|[hg])(?P<minute>\d{2})?"
    r"|(?=\s*(?:[ap]\.?m\b|(?-i:SA|CH)\b)))"
    r"(?:\s*(?P<ampm>[ap])\.?m\.?|\s*(?P<vn>(?-i:SA|CH))\b)?"
    r"(?!\w|\.\d)",
    re.IGNORECASE,
)
# A time zone written right after a time: "9:00 AM EST", "10:00 (GMT+8)".
ZONE = re.compile(r"\s*\(?\s*(?:(?P<named>ICT|EST|EDT|PST|PDT|CET|CEST|JST|KST|SGT)\b|(?:GMT|UTC)\s*(?P<sign>[+\-−])?"
                  r"\s*(?P<hours>\d{1,2})?(?::?(?P<minutes>\d{2}))?)\s*\)?")
ZONE_HOURS = {"ICT": 7, "EST": -5, "EDT": -4, "PST": -8, "PDT": -7, "CET": 1, "CEST": 2, "JST": 9, "KST": 9, "SGT": 8}
VIETNAM = timedelta(hours=7)
# On folded text: what joins the two ends of a range.
JOIN = re.compile(r"\s*,?\s*(?:den|toi|-|–|—|to|until|till)\s+(?:het\s+)?(?:ngay\s+)?$|\s*[-–—]\s*$")
# On folded text, right after a time: the time of day ("2h chiều" is 14:00).
TIME_OF_DAY_AFTER = re.compile(r"\s*(sang|chieu|toi|trua)\b")
TIME_OF_DAY = re.compile(r"\b(sang|chieu|toi|trua)\b")
EARLIEST_BARE_HOUR = 6  # a bare hour under this, without minutes or AM/PM, is a length: "(2h)"
# A length: a lead word, then hours and/or minutes, on folded text. After a weak lead ("khoảng", "about") only units
# that can't be a time of day count: "khoảng 1 tiếng" is a length, "khoảng 2 giờ chiều" a time. "Trong" leads only
# hours: "trong 15 phút đầu" is not an event's length.
LENGTH = re.compile(
    r"(?:(?P<lead>\b(?:keo dai|thoi luong(?: du kien)?|trong vong|trong|du kien|thoi gian lam bai|thoi gian trinh bay|"
    r"chi co|sau do co|sau do|duration|lasting|lasts|for)\b)|(?P<weak>\b(?:khoang|about|around|approximately)\b))"
    r"(?:\s*(?:la|:))?(?:\s*(?:khoang|about|around|approximately))?\s*"
    r"(?:(?P<hours>\d{1,2})(?:[.,](?P<half>5))?\s*(?P<unit>gio\b|tieng\b|hours?\b|h(?=\d|\b))"
    r"(?:\s*(?P<more>\d{1,2})\s*(?:phut\b|p\b|minutes?\b)?)?"
    r"|(?P<minutes>\d{1,3})\s*(?:phut|minutes?)\b)")
APPROXIMATE = re.compile(r"\b(?:khoang|du kien|about|around|approximately)\b")
SLOT = re.compile(r"\bmoi\s+luot\b")


@dataclass(frozen=True)
class Day:
    start: int
    end: int
    day: date


@dataclass(frozen=True)
class Clock:
    """A time, or a time range when `finish` is given. `offset`: the written time zone's offset from UTC."""
    start: int
    end: int
    begin: time
    finish: time | None = None
    offset: timedelta | None = None


@dataclass(frozen=True)
class Length:
    start: int
    end: int
    minutes: int
    approximate: bool
    slot: bool  # "mỗi lượt … 30 phút": each booking slot's length, not the event's
    adds: bool  # "sau đó có 10 phút": adds to the length before it


def _year_guess(day, month, arrived):
    """The date with the year closest to the arrival day, or None when there is no such date."""
    try:
        candidates = [date(arrived.year + k, month, day) for k in (-1, 0, 1)]
    except ValueError:
        return None
    return min(candidates, key=lambda d: abs(d - arrived))


def days_in(sentence, arrived):
    """[Day] in `sentence`, in order. A date without a year takes the year closest to `arrived`."""
    found, taken = [], []
    for pattern in DATE_FORMATS:
        for match in pattern.finditer(sentence):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            taken.append(match.span())
            month = match.group("month")
            month = MONTH_NAMES[month.lower()] if month.isalpha() else int(month)
            day = int(match.group("day"))
            groups = match.groupdict()
            try:
                if groups.get("short"):
                    value = date(2000 + int(groups["short"]), month, day)
                elif groups.get("year"):
                    value = date(int(groups["year"]), month, day)
                else:
                    value = _year_guess(day, month, arrived)
            except ValueError:
                value = None
            if value is not None:
                found.append(Day(match.start(), match.end(), value))
    return sorted(found, key=lambda d: d.start)


def lengths_in(sentence):
    """[Length] in `sentence`, in order."""
    folded = words.fold_in_place(sentence)
    found = []
    for match in LENGTH.finditer(folded):
        if match.group("weak") and match.group("unit") in ("gio", "h"):
            continue
        if match.group("lead") == "trong" and match.group("minutes"):
            continue
        if match.group("minutes"):
            minutes = int(match.group("minutes"))
        else:
            minutes = int(match.group("hours")) * 60 + (30 if match.group("half") else 0) + int(match.group("more") or 0)
        before = folded[max(0, match.start() - 40):match.start()]
        found.append(Length(match.start(), match.end(), minutes,
                            approximate=bool(APPROXIMATE.search(match.group(0))),
                            slot=bool(SLOT.search(before)),
                            adds=(match.group("lead") or "").startswith("sau do")))
    return found


def _ampm(sentence, match, folded):
    """"a" / "p" for this time: its own AM/PM or SA/CH; else a time-of-day word right after it ("2h chiều"), else the
    nearest one before it in its part, else the only kind the sentence has; else None. "Trưa" is noon: only
    1h–3h trưa are afternoon."""
    if match.group("ampm"):
        return match.group("ampm").lower()
    if match.group("vn"):
        return "a" if match.group("vn") == "SA" else "p"
    hour = int(match.group("hour"))
    word = TIME_OF_DAY_AFTER.match(folded, match.end())
    if not word:
        part_start = max(folded.rfind(",", 0, match.start()), folded.rfind(";", 0, match.start())) + 1
        before = list(TIME_OF_DAY.finditer(folded, part_start, match.start()))
        word = before[-1] if before else None
    if not word:
        kinds = {w.group(1) for w in TIME_OF_DAY.finditer(folded)}
        word = TIME_OF_DAY.search(folded) if len(kinds) == 1 else None
    if not word:
        return None
    if word.group(1) == "trua":
        return "p" if hour <= 3 else None
    return "a" if word.group(1) == "sang" else "p"


def _clock_value(match, ampm):
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or match.group("gminute") or 0)
    if ampm == "p" and hour < 12:
        hour += 12
    if ampm == "a" and hour == 12:
        hour = 0
    return time(hour, minute) if hour < 24 and minute < 60 else None


def _zone(sentence, end):
    """(offset, end) of a time zone written at `end`, else (None, end)."""
    match = ZONE.match(sentence, end)
    if not match:
        return None, end
    if match.group("named"):
        return timedelta(hours=ZONE_HOURS[match.group("named")]), match.end()
    sign = -1 if match.group("sign") in ("-", "−") else 1
    return sign * timedelta(hours=int(match.group("hours") or 0), minutes=int(match.group("minutes") or 0)), match.end()


def clocks_in(sentence, taken):
    """[Clock] in `sentence` outside the spans in `taken` (its dates and lengths), in order. Two times joined by
    "-", "đến", "to" … make one range; a range's end that isn't after its start is dropped. A bare small hour
    ("(2h)") is a length, not a time; a dotted number after a score word ("điểm trung bình từ 7.50") is a score."""
    folded = words.fold_in_place(sentence)
    scores = words.SCORE.spans(sentence)
    singles = []
    for match in TIME.finditer(sentence):
        if any(match.start() < end and start < match.end() for start, end in taken):
            continue
        if "." in match.group(0) and any(end <= match.start() for _, end in scores):
            continue
        ampm = _ampm(sentence, match, folded)
        if (match.group("minute") is None and match.group("gminute") is None and ampm is None
                and "gi" not in match.group(0).lower() and int(match.group("hour")) < EARLIEST_BARE_HOUR):
            continue
        value = _clock_value(match, ampm)
        if value is None:
            continue
        offset, end = _zone(sentence, match.end())
        singles.append((match, ampm, value, offset, end))
    found, i = [], 0
    while i < len(singles):
        first, first_ampm, begin, offset, end = singles[i]
        finish = None
        i += 1
        if i < len(singles) and JOIN.match(fold(sentence[end:singles[i][0].start()]) + " "):
            second, second_ampm, finish, offset2, end = singles[i]
            offset = offset or offset2
            i += 1
            if not first_ampm and second_ampm:
                shifted = _clock_value(first, second_ampm)
                if shifted and shifted < finish:
                    begin = shifted
            if finish <= begin:
                finish = None
        found.append(Clock(first.start(), end, begin, finish, offset))
    return found


def parts_of(sentence):
    """(start, end) of the sentence's parts: it is cut at commas and semicolons."""
    cuts = [i for i, c in enumerate(sentence) if c in ",;"]
    starts, ends = [0] + [c + 1 for c in cuts], cuts + [len(sentence)]
    return list(zip(starts, ends))
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_phrases.py`
Expected: PASS (`64 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_phrases.py agent/tests/test_mail_phrases.py
git commit -m "feat(agent): mail_phrases, step 1 of the time reader: the dates, times and lengths of a sentence, and its parts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Step 1, part 2: ranges, windows, weekdays and relative days

**Files:**
- Modify: `agent/sla_agent/mail_phrases.py`
- Test: `agent/tests/test_mail_phrases.py`

**Interfaces:**
- Consumes: Task 3's `days_in`, `clocks_in`, `JOIN`, `Day` and `Clock`; `mail_words.WEEKDAYS`, `WEEKDAY_FILTER`, `TODAY`, `TOMORROW`, `DAY_AFTER_TOMORROW`, `THIS_WEEK` and `NEXT_WEEK`.
- Produces:
  - Frozen dataclasses `DayRange(start, end, first, last)` and `Window(start, end, first, begin, last, finish)`.
  - `ranges_in(sentence, days, clocks, arrived) -> tuple[list[DayRange], list[Window]]`. A window is a time and a date joined to a time and a date ("từ 8h00 ngày 01/10 đến 17h00 ngày 05/10"); windows are found first. A day range is two dates joined by "đến", "–" and the like, or "từ nay đến <date>" (from `arrived`).
  - `weekday_filter(sentence) -> int | None`: the weekday (Monday is 0) named after "các ngày", "các", "mỗi" or "every".
  - `relative_day(sentence, arrived) -> tuple[str, date] | None`. The codes are `today`, `tomorrow`, `day_after_tomorrow`, `this_week`, `next_week`, and `weekday` (a weekday alone: the next one after `arrived`).
  - The patterns `FILLER` (what may sit between a time and its date) and `FROM_NOW`, both on folded text.

- [ ] **Step 1: Write the failing tests**

In `agent/tests/test_mail_phrases.py`, replace:

```python
from sla_agent.mail_phrases import clocks_in, days_in, lengths_in, parts_of
```

with:

```python
from sla_agent.mail_phrases import clocks_in, days_in, lengths_in, parts_of, ranges_in, relative_day, weekday_filter
```

Add to the end of `agent/tests/test_mail_phrases.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_phrases.py`
Expected: FAIL while collecting: `ImportError: cannot import name 'ranges_in' from 'sla_agent.mail_phrases'`.

- [ ] **Step 3: Add the ranges, windows, weekday filter and relative days**

In `agent/sla_agent/mail_phrases.py`, replace:

```python
# On folded text: what joins the two ends of a range.
JOIN = re.compile(r"\s*,?\s*(?:den|toi|-|–|—|to|until|till)\s+(?:het\s+)?(?:ngay\s+)?$|\s*[-–—]\s*$")
```

with:

```python
# On folded text: what joins the two ends of a range, and what may sit between a time and its date.
JOIN = re.compile(r"\s*,?\s*(?:den|toi|-|–|—|to|until|till)\s+(?:het\s+)?(?:ngay\s+)?$|\s*[-–—]\s*$")
FILLER = re.compile(r"\s*[,(]?\s*(?:(?:ngay|vao|luc|vao luc|on|at|cung ngay)\s*)*[,)]?\s*$")
FROM_NOW = re.compile(r"\btu\s+nay\s+(?:den|toi)\s+(?:het\s+)?(?:ngay\s+)?$")
```

In `agent/sla_agent/mail_phrases.py`, add with two blank lines between, right after the line `    offset: timedelta | None = None`:

```python
@dataclass(frozen=True)
class DayRange:
    start: int
    end: int
    first: date
    last: date


@dataclass(frozen=True)
class Window:
    """From a time on one day to a time on another."""
    start: int
    end: int
    first: date
    begin: time
    last: date
    finish: time
```

In `agent/sla_agent/mail_phrases.py`, add with two blank lines between, right before the line `def parts_of(sentence):`:

```python
def _between(sentence, a, b):
    return fold(sentence[a:b])


def ranges_in(sentence, days, clocks, arrived):
    """(DayRange list, Window list): two dates joined by "đến", "–" …, "từ nay đến <date>", and a time and date joined
    to a time and date ("từ 8h00 ngày 01/10 đến 17h00 ngày 05/10")."""
    def next_to(clock, day):
        a, b = (clock.end, day.start) if clock.start < day.start else (day.end, clock.start)
        return FILLER.fullmatch(_between(sentence, a, b)) is not None

    windows, day_ranges, used = [], [], set()
    for i in range(len(days) - 1):
        d1, d2 = days[i], days[i + 1]
        c1 = next((c for c in clocks if c.finish is None and next_to(c, d1)), None)
        c2 = next((c for c in clocks if c.finish is None and next_to(c, d2) and c is not c1), None)
        if c1 and c2:
            left_end, right_start = max(c1.end, d1.end), min(c2.start, d2.start)
            if left_end <= right_start and JOIN.match(_between(sentence, left_end, right_start) + " "):
                windows.append(Window(min(c1.start, d1.start), max(c2.end, d2.end), d1.day, c1.begin, d2.day, c2.begin))
                used.update((i, i + 1))
                continue
    for i in range(len(days) - 1):
        if i in used or i + 1 in used:
            continue
        d1, d2 = days[i], days[i + 1]
        if JOIN.match(_between(sentence, d1.end, d2.start) + " ") and d1.day <= d2.day:
            day_ranges.append(DayRange(d1.start, d2.end, d1.day, d2.day))
            used.update((i, i + 1))
    for i, d in enumerate(days):
        if i not in used and FROM_NOW.search(fold(sentence[:d.start])):
            day_ranges.append(DayRange(fold(sentence[:d.start]).rfind("tu nay"), d.end, arrived, d.day))
    return sorted(day_ranges, key=lambda r: r.start), windows
```

Add to the end of `agent/sla_agent/mail_phrases.py`:

```python
def weekday_filter(sentence):
    """The weekday (0 = Monday) named after "các ngày", "các", "mỗi" or "every", else None: "các ngày thứ Bảy"."""
    filters = words.WEEKDAY_FILTER.spans(sentence)
    for start, _, day in words.WEEKDAYS.spans(sentence):
        if any(end <= start and FILLER.fullmatch(fold(sentence[end:start])) for _, end in filters):
            return day
    return None


def relative_day(sentence, arrived):
    """(code, day) of the day a relative word names in `sentence` (spec §3.2), else None."""
    if words.TODAY.spans(sentence):
        return "today", arrived
    if words.TOMORROW.spans(sentence):
        return "tomorrow", arrived + timedelta(days=1)
    if words.DAY_AFTER_TOMORROW.spans(sentence):
        return "day_after_tomorrow", arrived + timedelta(days=2)
    named = words.WEEKDAYS.spans(sentence)
    if not named:
        return None
    weekday = named[0][2]
    monday = arrived - timedelta(days=arrived.weekday())
    if words.NEXT_WEEK.spans(sentence):
        return "next_week", monday + timedelta(days=7 + weekday)
    if words.THIS_WEEK.spans(sentence):
        return "this_week", monday + timedelta(days=weekday)
    return "weekday", arrived + timedelta(days=(weekday - arrived.weekday() - 1) % 7 + 1)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_phrases.py`
Expected: PASS (`84 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_phrases.py agent/tests/test_mail_phrases.py
git commit -m "feat(agent): mail_phrases reads date ranges, windows, weekday filters and relative days

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Step 0: clean the text (`mail_times.py`)

**Files:**
- Create: `agent/sla_agent/mail_times.py`
- Test: `agent/tests/test_mail_times.py`

**Interfaces:**
- Consumes: `mail_words.OFFICE_HOURS`, `REGISTRATION` and `CLOSING_STRONG`; `class_changes.SENTENCE_END`, `URL` and `fold`.
- Produces:
  - `clean(subject, text) -> str`: NFC, with links removed. A reply loses its quoted part, and a forward keeps everything. The signature (from a line "--" on) and lines giving office hours go.
  - `_sentences(text) -> list[str]`: the sentences, split as in Events §3.2. A heading line about registration or a deadline, with no number and at most `MAX_HEADING_WORDS` (8) words, is joined to the next line as "HEADING: next line".
  - Tasks 6–9 add to this file; the map under **File Structure** shows where.

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_mail_times.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: FAIL while collecting: `ModuleNotFoundError: No module named 'sla_agent.mail_times'`.

- [ ] **Step 3: Write `mail_times.py` with step 0**

Create `agent/sla_agent/mail_times.py`:

```python
"""The mail time reader (spec 2026-10-07-mail-event-kinds-design.md §4): an email's sessions, Periods, deadlines and
flags, read on the laptop with rules. Step 0 cleans the text, step 1 (mail_phrases) finds each sentence's dates and
times, and step 2 decides what each of them is. Pure functions: the email's text never leaves this module.

The rule names in the comments (D1, P4, S3 …) are the spec's, §4.3."""

import re
import unicodedata

from sla_agent import mail_words as words
from sla_agent.class_changes import SENTENCE_END, URL, fold

MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own

# Step 0 (§4.1), on folded text.
REPLY = re.compile(r"\s*(?:re|tl|tra loi)\s*:")
QUOTE_FROM = re.compile(r"\s*(?:from|tu)\s*:(?!\s*\d)")  # "Từ: 14h00" is a time, not a header
QUOTE_HEADER = re.compile(r"\s*(?:sent|date|to|da gui|gui|ngay|den)\s*:")
ORIGINAL = re.compile(r"\s*-{2,}\s*original message\s*-{2,}")
WROTE = re.compile(r"\s*(?:on|vao)\b.*\b(?:wrote|da viet)\s*:\s*$")


# ---- step 0: clean the text (§4.1) -----------------------------------------------------------------------------------


def _before_quote(lines):
    """A reply's own lines: everything before its first quoted part."""
    for i, line in enumerate(lines):
        folded = fold(line)
        if ORIGINAL.match(folded) or folded.lstrip().startswith(">"):
            return lines[:i]
        if WROTE.match(folded) or (i + 1 < len(lines) and re.match(r"\s*(?:on|vao)\b", folded)
                                   and WROTE.match(folded + " " + fold(lines[i + 1]))):
            return lines[:i]
        if QUOTE_FROM.match(folded) and any(QUOTE_HEADER.match(fold(below)) for below in lines[i + 1:i + 5]):
            return lines[:i]
    return lines


def clean(subject, text):
    """The text the times are read from: links removed; a reply without its quoted part (a forward keeps everything);
    no signature (from a line "--" on) and no lines giving office hours."""
    text = URL.sub(" ", unicodedata.normalize("NFC", text or "")).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if REPLY.match(fold(subject or "")):
        lines = _before_quote(lines)
    kept = []
    for line in lines:
        if line.strip() == "--":
            break
        hours = words.OFFICE_HOURS.spans(line)
        if hours and hours[0][0] == len(line) - len(line.lstrip()):
            continue
        kept.append(line)
    return "\n".join(kept)


def _sentences(text):
    """The sentences of `text`, split as in Events §3.2. A heading line about registration or a deadline, with no
    number in it ("THỜI GIAN ĐĂNG KÝ", then "Từ ngày 20/09 đến 22/09/2026."), is read together with the line after it."""
    found = [s for s in SENTENCE_END.split(text) if s.strip()]
    merged, i = [], 0
    while i < len(found):
        line = found[i]
        heading = (i + 1 < len(found) and not re.search(r"\d", line) and len(line.split()) <= MAX_HEADING_WORDS
                   and (words.REGISTRATION.spans(line) or words.CLOSING_STRONG.spans(line)))
        if heading:
            merged.append(line.strip().rstrip(":") + ": " + found[i + 1].strip())
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: PASS (`19 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_times.py agent/tests/test_mail_times.py
git commit -m "feat(agent): mail_times step 0: replies lose their quoted part, signatures and office hours go, registration headings join their line

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Step 2: deadlines

This task adds what the reader returns (`Found`), the per-sentence bookkeeping that every later rule uses (`_Sentence`), the first rules of step 2 (arrivals, then deadlines D1–D4), and modes for deadlines (rule M). `read_times` returns only deadlines for now.

**Files:**
- Modify: `agent/sla_agent/mail_times.py`
- Test: `agent/tests/test_mail_times.py`

**Interfaces:**
- Consumes: `mail_phrases` (Tasks 3–4); the `mail_words` roles; `clean` and `_sentences` (Task 5).
- Produces:
  - `FoundDeadline(kind, day, at=None, mode=None)`: `kind` is "opens", "register", "confirm" or "due"; `at` is a `time`; `mode` is "online", "in_person" or `None`.
  - `Found(sessions=(), periods=(), deadlines=(), meeting=False, registered=False)`, frozen, with the property `register_by`: the latest register deadline's day, or `None`.
  - `read_times(subject, text, arrived) -> Found`, where `arrived` is the Vietnam date the email arrived.
  - For Tasks 7–9:
    - `_Sentence(text, arrived)`: one sentence, what step 1 found in it (`.days`, `.clocks`, `.lengths`, `.ranges`, `.windows`, `.parts`, `.weekday`) and what step 2 has done with it (`.used`, `.skip`, `.sessions`, `.relative`). Its methods are `.spans(role)`, `.part(position)`, `.free(items)`, `.use(*items)`, `.next_to(clock, day)` and `.day_for(clock)`.
    - `_target(sentence, span, right_after=False)`, `_moment(sentence, item)` and `_within(span, spans)`.
    - `_Modes(online, in_person)` with `.of(sentence, position, whole_email)`, and `_kept_deadlines(deadlines, heading, modes)`.

- [ ] **Step 1: Write the failing tests**

In `agent/tests/test_mail_times.py`, replace:

```python
import unicodedata

import pytest

from sla_agent.mail_times import _sentences, clean
```

with:

```python
import unicodedata
from datetime import date

import pytest

from sla_agent.mail_times import _sentences, clean, read_times
```

Add to the end of `agent/tests/test_mail_times.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: FAIL while collecting: `ImportError: cannot import name 'read_times' from 'sla_agent.mail_times'`.

- [ ] **Step 3: Add the deadlines**

In `agent/sla_agent/mail_times.py`, replace:

```python
import re
import unicodedata

from sla_agent import mail_words as words
```

with:

```python
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, time

from sla_agent import mail_phrases as phrases
from sla_agent import mail_words as words
```

In `agent/sla_agent/mail_times.py`, add right before the line `MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own`:

```python
MAX_DEADLINES = 5
```

In `agent/sla_agent/mail_times.py`, add right after the line `WROTE = re.compile(r"\s*(?:on|vao)\b.*\b(?:wrote|da viet)\s*:\s*$")`:

```python
# Step 2 (§4.3), on folded text.
DUE_TO = re.compile(r"\s+to\b")  # "due to the rain" is not a deadline
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- step 0: clean the text (§4.1) -----------------------------------------------------------------------------------`:

```python
# ---- what the reader finds -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FoundDeadline:
    kind: str  # "opens", "register", "confirm" or "due"
    day: date
    at: time | None = None
    mode: str | None = None


@dataclass(frozen=True)
class Found:
    sessions: tuple = ()
    periods: tuple = ()
    deadlines: tuple = ()
    meeting: bool = False
    registered: bool = False

    @property
    def register_by(self):
        """The latest register deadline's day (what servers before stage 2 read), or None."""
        return max((d.day for d in self.deadlines if d.kind == "register"), default=None)
```

Add to the end of `agent/sla_agent/mail_times.py`:

```python
# ---- step 1: one sentence's phrases, and what is used (§4.2) ---------------------------------------------------------


class _Sentence:
    """A sentence, what step 1 found in it, and which of those step 2 has used."""

    def __init__(self, text, arrived):
        self.text = text
        self.parts = phrases.parts_of(text)
        self.days = phrases.days_in(text, arrived)
        self.lengths = phrases.lengths_in(text)
        taken = [(d.start, d.end) for d in self.days] + [(n.start, n.end) for n in self.lengths]
        self.clocks = phrases.clocks_in(text, taken)
        self.ranges, self.windows = phrases.ranges_in(text, self.days, self.clocks, arrived)
        self.weekday = phrases.weekday_filter(text)
        self.used = set()  # id() of the dates, times, ranges and windows a rule has used
        self.skip = False  # gives no day to the lines around it: a deadline, notice or not-an-event line
        self.sessions = []  # (FoundSession, position) made from this sentence
        self.relative = None  # (code, day) when this sentence's sessions took their day from a relative word
        self._spans = {}

    def spans(self, role):
        if role not in self._spans:
            self._spans[role] = role.spans(self.text)
        return self._spans[role]

    def part(self, position):
        return next(i for i, (start, end) in enumerate(self.parts) if start <= position <= end)

    def free(self, items):
        return [x for x in items if id(x) not in self.used]

    def use(self, *items):
        """Marks `items` used, with the dates and times inside a range or window."""
        for item in items:
            self.used.add(id(item))
            for inner in self.days + self.clocks:
                if item.start <= inner.start and inner.end <= item.end:
                    self.used.add(id(inner))

    def next_to(self, clock, day):
        """Whether a time and a date sit together: "14:00 ngày 15/10", "17/10 lúc 23:59"."""
        a, b = (clock.end, day.start) if clock.start < day.start else (day.end, clock.start)
        return a <= b and phrases.FILLER.fullmatch(fold(self.text[a:b])) is not None

    def day_for(self, clock):
        """A day for `clock` from this sentence: the date next to it, else a free date in its part, else in the
        sentence; else None."""
        beside = [d for d in self.days if self.next_to(clock, d)]
        if beside:
            return beside[0].day
        free = self.free(self.days)
        in_part = [d for d in free if self.part(d.start) == self.part(clock.start)]
        return (in_part or free)[0].day if free else None


def _target(sentence, span, right_after=False):
    """The free date or single time a word at `span` points at: the first after it in its part (only right after it
    when `right_after`), else the last before it in its part; None when there is none. Never one inside a date range
    or window: those are registration windows (D2) or Periods (P)."""
    part = sentence.part(span[0])
    spans = [(x.start, x.end) for x in sentence.free(sentence.ranges + sentence.windows)]
    items = [x for x in sentence.free(sentence.days + [c for c in sentence.clocks if c.finish is None])
             if sentence.part(x.start) == part and not any(a <= x.start and x.end <= b for a, b in spans)]
    after = sorted((x for x in items if x.start >= span[1]), key=lambda x: x.start)
    if after:
        if right_after and not phrases.FILLER.fullmatch(fold(sentence.text[span[1]:after[0].start])):
            return None
        return after[0]
    before = [x for x in items if x.end <= span[0]]
    return None if right_after or not before else max(before, key=lambda x: x.start)


def _moment(sentence, item):
    """(day, time, items) a word points at: a date with the time next to it, or a time with the date next to it;
    a time alone borrows its part's or sentence's date (which stays free)."""
    if isinstance(item, phrases.Day):
        beside = [c for c in sentence.free(sentence.clocks) if c.finish is None and sentence.next_to(c, item)]
        return item.day, beside[0].begin if beside else None, [item] + beside[:1]
    beside = [d for d in sentence.free(sentence.days) if sentence.next_to(item, d)]
    if beside:
        return beside[0].day, item.begin, [item, beside[0]]
    return sentence.day_for(item), item.begin, [item]


def _within(span, spans):
    return any(start <= span[0] and span[1] <= end and (start, end) != span for start, end in spans)


# ---- step 2: what each sentence takes, in order (§4.3, steps 1–4) ----------------------------------------------------


def _drop(sentence):
    """N: a not-an-event or cancelled sentence gives nothing; a rescheduling keeps only what follows "sang"."""
    if sentence.spans(words.NOT_AN_EVENT) or sentence.spans(words.CANCEL):
        sentence.use(*sentence.days, *sentence.clocks, *sentence.ranges, *sentence.windows)
        sentence.skip = True
        return
    for start, end in sentence.spans(words.RESCHEDULE):
        pivot = next((p for p in sentence.spans(words.PIVOT) if p[0] >= end), None)
        if pivot:
            sentence.use(*[x for x in sentence.days + sentence.clocks + sentence.ranges + sentence.windows
                           if start <= x.start and x.end <= pivot[0]])


def _arrivals(sentence):
    """Arrival words take their times first ("có mặt trước 13:45"), so their "trước" is never read as a deadline.
    "Mở cửa từ" counts only with one time: with a range it gives open hours."""
    found = []
    for span in sentence.spans(words.ARRIVAL):
        part = sentence.part(span[0])
        clock = next((c for c in sentence.free(sentence.clocks) if sentence.part(c.start) == part and c.start >= span[1]),
                     None)
        if clock is None or (fold(sentence.text[span[0]:span[1]]).startswith("mo cua") and clock.finish is not None):
            continue
        sentence.use(clock)
        found.append(clock)
    return found


def _kind(sentence, span, strong):
    """D1: the nearest confirm, due or registration word in the sentence gives the kind; a strong deadline word
    without one is "due"; a soft one without one is no deadline (None)."""
    kinds = [(abs(start - span[0]), rank, kind)
             for rank, (kind, role) in enumerate((("confirm", words.CONFIRM), ("due", words.DUE),
                                                  ("register", words.REGISTRATION)))
             for start, _ in sentence.spans(role)]
    return min(kinds)[2] if kinds else ("due" if strong else None)


def _deadlines(sentence):
    """D: [(FoundDeadline, position)]: the sentence's deadlines; they use the dates and times they take."""
    found = []

    def add(kind, position, day, at, items):
        if day is not None:
            found.append((FoundDeadline(kind, day, at), position))
            sentence.use(*items)

    registration = sentence.spans(words.REGISTRATION)
    starts = sentence.spans(words.START) + sentence.spans(words.EVENT)
    # D2: a registration word, then in its part a date range, a window, or a time range with a date, with no event
    # word between them.
    for reg in registration:
        part = sentence.part(reg[0])
        for item in sentence.free(sentence.windows + sentence.ranges + [c for c in sentence.clocks if c.finish]):
            if sentence.part(item.start) != part or item.start < reg[1]:
                continue
            if any(reg[1] <= start < item.start for start, _ in starts):
                continue
            if isinstance(item, phrases.Window):
                add("opens", reg[0], item.first, item.begin, [item])
                add("register", reg[0], item.last, item.finish, [item])
            elif isinstance(item, phrases.DayRange):
                add("opens", reg[0], item.first, None, [item])
                add("register", reg[0], item.last, None, [item])
            else:
                day = sentence.day_for(item)
                add("opens", reg[0], day, item.begin, [item])
                add("register", reg[0], day, item.finish, [item])
    # D3: an opening word, in a registration sentence.
    if registration:
        for span in sentence.spans(words.OPENING):
            target = _target(sentence, span)
            if target is not None:
                add("opens", span[0], *_moment(sentence, target))
    # D1: closing words. "Due to the rain" is not a deadline.
    strong = [s for s in sentence.spans(words.CLOSING_STRONG)
              if not (fold(sentence.text[s[0]:s[1]]) == "due" and DUE_TO.match(fold(sentence.text[s[1]:])))]
    soft = [s for s in sentence.spans(words.CLOSING_SOFT) if not _within(s, strong)]
    only_in_registration = sentence.spans(words.ONLY_IN_REGISTRATION)
    right_after = sentence.spans(words.RIGHT_BEFORE)
    for span in sorted(set(strong + soft)):
        if span not in strong and span in only_in_registration and not registration:
            continue
        kind = _kind(sentence, span, span in strong)
        target = kind and _target(sentence, span, right_after=span in right_after)
        if target is not None:
            add(kind, span[0], *_moment(sentence, target))
    if found and not sentence.free(sentence.days):
        sentence.skip = True
    return found


# ---- what is kept, with its mode (§4.3, D4, M, S7) -------------------------------------------------------------------


@dataclass(frozen=True)
class _Modes:
    """M: whether an email has online and in-person words, and the mode they give one of its items."""

    online: bool
    in_person: bool

    def of(self, sentence, position, whole_email):
        """The mode of an item at `position` in `sentence`: from the words of its part, else of its sentence; else, with
        `whole_email` (for sessions), online when the email has only online words."""
        part = sentence.parts[sentence.part(position)]
        for start, end in (part, (0, len(sentence.text))):
            if any(start <= s < end for s, _ in sentence.spans(words.ONLINE)):
                return "online"
            if self.online and any(start <= s < end for s, _ in sentence.spans(words.IN_PERSON)):
                return "in_person"
        return "online" if whole_email and self.online and not self.in_person else None


def _kept_deadlines(deadlines, heading, modes):
    """D4 and M: [(sentence, FoundDeadline, position)] as kept: each with its mode, once (with its time when a copy has
    it), at most MAX_DEADLINES, soonest first. Deadlines before the day the email arrived stay, as A.2."""
    unique = {}
    for sentence, deadline, position in deadlines:
        if sentence is not heading:
            deadline = replace(deadline, mode=modes.of(sentence, position, whole_email=False))
        key = (deadline.kind, deadline.day, deadline.mode)
        if key not in unique or (unique[key].at is None and deadline.at is not None):
            unique[key] = deadline
    return tuple(sorted(unique.values(), key=lambda d: (d.day, d.at or time(0)))[:MAX_DEADLINES])


# ---- the reader ------------------------------------------------------------------------------------------------------


def read_times(subject, text, arrived):
    """Found: what one email that arrived on `arrived` (a Vietnam date) holds."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    heading = _Sentence(unicodedata.normalize("NFC", subject or ""), arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    for sentence in sentences:
        _drop(sentence)
        _arrivals(sentence)
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
    return Found(deadlines=_kept_deadlines(deadlines, heading, modes))
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: PASS (`53 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_times.py agent/tests/test_mail_times.py
git commit -m "feat(agent): the time reader finds deadlines: register, opens, confirm and due, each with its day, time and mode

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Step 2: Periods

This task adds the Periods (P1–P5). First it adds two rules that must take their times before the Periods do: link times (S5; Task 8 joins them to their sessions) and notices (N). Each sentence's Periods are made before any session, so a time that a Period uses never becomes a session too. A Period from 00:00 to 23:59 is all day, with no times (spec §2): those are the edges of the day, not times the email sets.

**Files:**
- Modify: `agent/sla_agent/mail_times.py`
- Test: `agent/tests/test_mail_times.py`

**Interfaces:**
- Consumes: Task 6's `_Sentence`, `_target`, `_moment`, `_within`, `_Modes` and `_kept_deadlines`.
- Produces:
  - `FoundPeriod(first_day, last_day, mode, from_time=None, to_time=None, details_later=False, label=None)`: `mode` is "all_day", "daily_window" or "one_window".
  - `FoundSession(day, start, end=None, end_is_approximate=False, ends_next_day=False, check_in=None, link_opens=None, mode=None, relative=None, label=None)`, defined now and filled in Task 8.
  - `read_times` returns Periods (soonest first, at most 5) and deadlines.
  - `DAY_EDGES` (00:00 and 23:59): a Period between them is all day, and in Task 8 they never start a session.
  - For Task 8: `_label(sentence, position)`, `_links(sentence)`, `_notices(sentence)`, `_says_later(sentence)`, and `_periods(sentences, i, details_later) -> (Periods, the days and times P5 hands on as sessions)`.

- [ ] **Step 1: Write the failing tests**

Add to the end of `agent/tests/test_mail_times.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: FAIL with `12 failed`, all in `test_periods`: the reader finds no Periods yet.

- [ ] **Step 3: Add the Periods**

In `agent/sla_agent/mail_times.py`, replace:

```python
from datetime import date, time
```

with:

```python
from datetime import date, datetime, time, timedelta
```

In `agent/sla_agent/mail_times.py`, add right before the line `MAX_DEADLINES = 5`:

```python
MAX_SESSIONS = 10
MAX_PERIODS = 5
```

In `agent/sla_agent/mail_times.py`, add right after the line `MAX_HEADING_WORDS = 8  # a heading line longer than this is a sentence of its own`:

```python
# The edges of a day, not times an email sets: they never start a session, and a Period from one to the other is all
# day ("từ 00g00 ngày 21/9 đến 23g59 ngày 27/9" opens and closes a contest round).
DAY_EDGES = (time(0, 0), time(23, 59))
```

In `agent/sla_agent/mail_times.py`, add right after the line `DUE_TO = re.compile(r"\s+to\b")  # "due to the rain" is not a deadline`:

```python
LINK_BEFORE = re.compile(r"\btruoc\s+(?:do\s+)?(\d{1,3})\s*phut\b")  # "gửi trước 30 phút": 30 minutes before
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right after the line `# ---- what the reader finds -------------------------------------------------------------------------------------------`:

```python
@dataclass(frozen=True)
class FoundSession:
    day: date
    start: time
    end: time | None = None
    end_is_approximate: bool = False
    ends_next_day: bool = False
    check_in: time | None = None
    link_opens: time | None = None
    mode: str | None = None
    relative: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class FoundPeriod:
    first_day: date
    last_day: date
    mode: str  # "all_day", "daily_window" or "one_window"
    from_time: time | None = None
    to_time: time | None = None
    details_later: bool = False
    label: str | None = None
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- step 2: what each sentence takes, in order (§4.3, steps 1–4) ----------------------------------------------------`:

```python
def _label(sentence, position):
    part = sentence.parts[sentence.part(position)]
    return next((code for start, _, code in words.LABELS.spans(sentence.text) if part[0] <= start < part[1]), None)
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- what is kept, with its mode (§4.3, D4, M, S7) -------------------------------------------------------------------`:

```python
def _links(sentence):
    """S5: [(clock, None)] for "Link … mở lúc 13:45", [(None, minutes)] for "Link … gửi trước 30 phút"."""
    found = []
    folded = fold(sentence.text)
    for span in sentence.spans(words.LINK):
        before = LINK_BEFORE.search(folded, span[1])
        if before:
            found.append((None, int(before.group(1))))
            continue
        part = sentence.part(span[0])
        clock = next((c for c in sentence.free(sentence.clocks)
                      if c.finish is None and sentence.part(c.start) == part and c.start >= span[1]), None)
        if clock is not None:
            sentence.use(clock)
            found.append((clock, None))
    return found


def _notices(sentence):
    """N: a notice takes the dates and times after it in its part ("Email này được gửi lúc 09:15 ngày 07/10")."""
    closing = sentence.spans(words.CLOSING_SOFT) + sentence.spans(words.CLOSING_STRONG)
    for span in sentence.spans(words.NOTICE):
        if any(start <= span[0] < end for start, end in closing):
            continue
        part = sentence.part(span[0])
        taken = [x for x in sentence.free(sentence.days + sentence.clocks + sentence.ranges + sentence.windows)
                 if sentence.part(x.start) == part and x.start >= span[1]]
        if taken:
            sentence.use(*taken)
            sentence.skip = True


# ---- step 2: Periods (§4.3, P) ---------------------------------------------------------------------------------------


def _says_later(sentence):
    """P2: the sentence says the student's own time comes later. Not on a line about the place: "Địa điểm: Thông tin
    chi tiết sẽ thông báo sau" is about where, not when."""
    return bool(sentence.spans(words.DETAILS_LATER)) and not sentence.spans(words.PLACE)


def _periods(sentences, i, details_later):
    """P1–P5 for sentence i: (its Periods, the sessions its ranges and windows give as [(FoundSession, position)])."""
    sentence = sentences[i]
    near = sentences[i:i + 2]
    any_time = any(s.spans(words.ANY_TIME) for s in near)
    later = any(_says_later(s) for s in near)
    open_hours = any(c.finish for c in sentence.free(sentence.clocks) for _, end in sentence.spans(words.DOORS)
                     if c.start >= end)
    period_words = any_time or later or open_hours
    periods, sessions = [], []

    def period(first, last, mode, position, begin=None, finish=None):
        if (begin, finish) == DAY_EDGES:  # whole days: all day, with no times (§2)
            mode, begin, finish = "all_day", None, None
        periods.append(FoundPeriod(first, last, mode, begin, finish, details_later, _label(sentence, position)))

    for window in sentence.free(sentence.windows):  # P4
        sentence.use(window)
        length = datetime.combine(window.last, window.finish) - datetime.combine(window.first, window.begin)
        if length > timedelta(hours=24) or period_words:
            period(window.first, window.last, "one_window", window.start, window.begin, window.finish)
        else:
            sessions.append((FoundSession(window.first, window.begin, window.finish,
                                          ends_next_day=window.last > window.first), window.start))
    hour_ranges = [c for c in sentence.free(sentence.clocks) if c.finish is not None]
    for day_range in sentence.free(sentence.ranges):
        sentence.use(day_range, *hour_ranges)
        if not hour_ranges:  # P1, P3
            period(day_range.first, day_range.last, "all_day", day_range.start)
            continue
        days = [day_range.first + timedelta(days=n) for n in range((day_range.last - day_range.first).days + 1)]
        if sentence.weekday is not None:
            days = [d for d in days if d.weekday() == sentence.weekday]
        each_day = sentence.spans(words.EACH_DAY) or sentence.weekday is not None
        for hours in hour_ranges:  # "8h00 - 11h30 & 13h00 - 16h00": one each
            if each_day and not period_words and len(days) * len(hour_ranges) <= MAX_SESSIONS:  # P5
                sessions += [(FoundSession(d, hours.begin, hours.finish), hours.start) for d in days]
            else:  # P1, P5
                period(day_range.first, day_range.last, "daily_window", day_range.start, hours.begin, hours.finish)
    if period_words or sentence.spans(words.WITHIN):  # P1, P2: one day's from–to
        for clock in sentence.free(sentence.clocks):
            day = clock.finish is not None and sentence.day_for(clock)
            if day:
                sentence.use(clock, *[d for d in sentence.days if d.day == day])
                period(day, day, "one_window", clock.start, clock.begin, clock.finish)
    return periods, sessions
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- the reader ------------------------------------------------------------------------------------------------------`:

```python
def _kept_periods(periods, arrived):
    """The Periods that haven't ended by `arrived`, each once, at most MAX_PERIODS, soonest first."""
    return tuple(sorted({p for p in periods if p.last_day >= arrived},
                        key=lambda p: (p.first_day, p.last_day, p.from_time or time(0)))[:MAX_PERIODS])
```

In `agent/sla_agent/mail_times.py`, replace `read_times` (from the line `def read_times(subject, text, arrived):` to the end of the file) with:

```python
def read_times(subject, text, arrived):
    """Found: what one email that arrived on `arrived` (a Vietnam date) holds."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    heading = _Sentence(unicodedata.normalize("NFC", subject or ""), arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))
    details_later = any(_says_later(s) for s in sentences)

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    for sentence in sentences:
        _drop(sentence)
        _arrivals(sentence)
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
        _links(sentence)
        _notices(sentence)
    periods = []
    for i in range(len(sentences)):
        periods += _periods(sentences, i, details_later)[0]
    return Found(periods=_kept_periods(periods, arrived), deadlines=_kept_deadlines(deadlines, heading, modes))
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: PASS (`72 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_times.py agent/tests/test_mail_times.py
git commit -m "feat(agent): the time reader finds Periods: day ranges, open hours and windows you can come to at any time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Step 2: sessions

This task adds the sessions (S1–S7): each one's day, end, check-in and link time; one-day Periods (P6); and modes and labels for sessions.

**Files:**
- Modify: `agent/sla_agent/mail_times.py`
- Test: `agent/tests/test_mail_times.py`

**Interfaces:**
- Consumes: Tasks 6–7.
- Produces: `read_times` returns sessions too: soonest first, at most `MAX_SESSIONS` (10, added in Task 7), none before the arrival day. Each `FoundSession` keeps its own start, with `check_in` and `link_opens` beside it; Task 11 turns them into today's upload.

- [ ] **Step 1: Write the failing tests**

In `agent/tests/test_mail_times.py`, replace:

```python
from datetime import date
```

with:

```python
from datetime import date, time
```

Add to the end of `agent/tests/test_mail_times.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: FAIL with `32 failed` in the new session tests (`test_the_day_of_a_time`, `test_the_end_of_a_session`, `test_check_in_and_link_times` and the others): the reader finds no sessions yet.

- [ ] **Step 3: Add the sessions**

In `agent/sla_agent/mail_times.py`, add right after the line `LINK_BEFORE = re.compile(r"\btruoc\s+(?:do\s+)?(\d{1,3})\s*phut\b")  # "gửi trước 30 phút": 30 minutes before`:

```python
ESTIMATED_END = re.compile(r"\bdu kien\s*$")  # "dự kiến kết thúc lúc 20:30": an approximate end
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- what is kept, with its mode (§4.3, D4, M, S7) -------------------------------------------------------------------`:

```python
# ---- step 2: sessions (§4.3, S) --------------------------------------------------------------------------------------


def _day_source(sentence):
    """The days a sentence gives the lines around it: its free dates, else the day a relative word gave it, else the
    first day of its range or window."""
    if sentence.skip:
        return []
    free = [d.day for d in sentence.free(sentence.days)]
    if free:
        return free
    if sentence.relative:
        return [sentence.relative[1]]
    return [x.first for x in sentence.windows + sentence.ranges][:1]


def _neighbour_days(sentences, i):
    """S1: the days of the nearest line above that has some, else of the nearest line below."""
    for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(sentences))):
        days = _day_source(sentences[j])
        if days:
            return days
    return []


def _session_days(sentences, i, arrived):
    """S1: ([day], relative code or None) for sentence i's times."""
    sentence = sentences[i]
    days = [d.day for d in sentence.free(sentence.days)] or _neighbour_days(sentences, i)
    if days:
        return days, None
    if any(s.days for s in sentences[:i + 1]):
        return [], None
    relative = phrases.relative_day(sentence.text, arrived)
    if relative is None:
        return [], None
    sentence.relative = relative
    return [relative[1]], relative[0]


def _sessions(sentences, i, arrived, given):
    """S1–S3 for sentence i: sessions from its free times, with those P4 and P5 gave."""
    sentence = sentences[i]
    clocks = sentence.free(sentence.clocks)
    approximate = set()
    # S2: "bắt đầu X … kết thúc Y" is one session; a sentence with only an end ends the nearest session above.
    for start, end in sentence.spans(words.END):
        after = [c for c in clocks if c.start >= end and c.finish is None]
        before = [c for c in clocks if c.end <= start and c.finish is None]
        if not after:
            continue
        estimated = bool(ESTIMATED_END.search(fold(sentence.text[:start])))
        if before:
            first, last = before[-1], after[0]
            joined = replace(first, finish=last.begin) if last.begin > first.begin else first
            clocks = [joined if c is first else c for c in clocks if c is not last]
            sentence.use(last)
            if estimated:
                approximate.add(id(joined))
        elif len(clocks) == 1 and not sentence.free(sentence.days):
            above = next((s for s in reversed(sentences[:i]) if s.sessions), None)
            if above:
                session, position = above.sessions[-1]
                above.sessions[-1] = (replace(session, end=after[0].begin, end_is_approximate=estimated), position)
            sentence.use(after[0])
            clocks = []
    found = list(given)
    clocks = [c for c in clocks if c.begin not in DAY_EDGES]
    days, relative = _session_days(sentences, i, arrived) if clocks else ([], None)
    pairs = zip(days, clocks) if len(days) == len(clocks) else [(d, c) for d in days for c in clocks]
    for day, clock in pairs:
        start, end = clock.begin, clock.finish
        if clock.offset is not None:  # S6
            moved = datetime.combine(day, start) - clock.offset + phrases.VIETNAM
            day, start = moved.date(), moved.time()
            end = end and (datetime.combine(day, end) - clock.offset + phrases.VIETNAM).time()
        found.append((FoundSession(day, start, end, id(clock) in approximate, relative=relative), clock.start))
    sentence.sessions = found
    # S3: a length ends the sessions of its sentence, or else of the nearest sentence above with sessions.
    lengths = [n for n in sentence.lengths if not n.slot]
    if not lengths:
        return
    minutes = next((n.minutes for n in lengths if not n.adds), 0) + sum(n.minutes for n in lengths if n.adds)
    holder = sentence if found else next((s for s in reversed(sentences[:i]) if s.sessions), None)
    if holder is None or not minutes:
        return
    for k, (session, position) in enumerate(holder.sessions):
        end = datetime.combine(session.day, session.start) + timedelta(minutes=minutes)
        if session.end is None and end.date() == session.day:
            holder.sessions[k] = (replace(session, end=end.time(),
                                          end_is_approximate=any(n.approximate for n in lengths)), position)


def _join(sessions, day, at, field):
    """S4, S5: sets `field` to `at` on the earliest session of `day` that starts at or after `at` and has none yet.
    Whether one was found."""
    later = [k for k, (s, _, _) in enumerate(sessions) if s.day == day and s.start >= at and getattr(s, field) is None]
    if not later:
        return False
    k = min(later, key=lambda k: sessions[k][0].start)
    session, i, position = sessions[k]
    sessions[k] = (replace(session, **{field: at}), i, position)
    return True


def _check_ins(sentences, arrivals, sessions, arrived):
    """S4: each arrival time [(sentence index, clock)] joins the earliest session of its day that starts at or after
    it, as its check-in; with no such session it is a session of its own (A.1)."""
    for i, clock in arrivals:
        day = sentences[i].day_for(clock) or next(iter(_neighbour_days(sentences, i)), None)
        if day is None and not any(s.days for s in sentences[:i + 1]):
            relative = phrases.relative_day(sentences[i].text, arrived)
            day = relative and relative[1]
        if day is not None and not _join(sessions, day, clock.begin, "check_in"):
            sessions.append((FoundSession(day, clock.begin, clock.finish), i, clock.start))


def _link_times(sentences, links, sessions):
    """S5: each link time [(sentence index, clock, minutes)] joins a session like an arrival time; "trước 30 phút"
    (minutes) counts back from the start of the nearest session above."""
    for i, clock, minutes in links:
        if clock is not None:
            day = sentences[i].day_for(clock) or next(iter(_neighbour_days(sentences, i)), None)
            if day is not None:
                _join(sessions, day, clock.begin, "link_opens")
            continue
        above = [k for k, (_, j, _) in enumerate(sessions) if j <= i]
        if above:
            session, j, position = sessions[above[-1]]
            at = datetime.combine(session.day, session.start) - timedelta(minutes=minutes)
            if at.date() == session.day and session.link_opens is None:
                sessions[above[-1]] = (replace(session, link_opens=at.time()), j, position)


def _one_day_periods(sentences, sessions, details_later):
    """P6: each day with no hour, with an event word in its part and no session that day, as a one-day Period."""
    periods, busy = [], {s.day for s, _, _ in sessions}
    for sentence in sentences:
        events = [sentence.part(start) for start, _ in sentence.spans(words.EVENT)]
        for day in sentence.free(sentence.days):
            if day.day not in busy and sentence.part(day.start) in events:
                periods.append(FoundPeriod(day.day, day.day, "all_day", details_later=details_later,
                                           label=_label(sentence, day.start)))
                busy.add(day.day)
    return periods
```

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- the reader ------------------------------------------------------------------------------------------------------`:

```python
def _kept_sessions(sentences, sessions, arrived, modes):
    """M, labels and S7: [(FoundSession, sentence index, position)] as kept: each with its mode and label, a check-in
    that isn't before the start left out; none before `arrived`; a repeated day and start once, with the end found;
    at most MAX_SESSIONS, soonest first."""
    kept = {}
    for session, i, position in sessions:
        if session.day < arrived:
            continue
        sentence = sentences[i]
        session = replace(session, mode=modes.of(sentence, position, whole_email=True),
                          label=session.label or _label(sentence, position),
                          check_in=session.check_in if session.check_in and session.check_in < session.start else None)
        key = (session.day, session.start)
        if key not in kept:
            kept[key] = session
        elif kept[key].end is None and session.end is not None:
            kept[key] = replace(kept[key], end=session.end, end_is_approximate=session.end_is_approximate)
    return tuple(sorted(kept.values(), key=lambda s: (s.day, s.start))[:MAX_SESSIONS])
```

In `agent/sla_agent/mail_times.py`, replace `read_times` (from the line `def read_times(subject, text, arrived):` to the end of the file) with:

```python
def read_times(subject, text, arrived):
    """Found: what one email that arrived on `arrived` (a Vietnam date) holds."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    heading = _Sentence(unicodedata.normalize("NFC", subject or ""), arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))
    details_later = any(_says_later(s) for s in sentences)

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    arrivals, links = [], []
    for i, sentence in enumerate(sentences):
        _drop(sentence)
        arrivals += [(i, clock) for clock in _arrivals(sentence)]
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
        links += [(i, clock, minutes) for clock, minutes in _links(sentence)]
        _notices(sentence)
    periods, given = [], []
    for i in range(len(sentences)):
        found, made = _periods(sentences, i, details_later)
        periods += found
        given.append(made)
    for i in range(len(sentences)):
        _sessions(sentences, i, arrived, given[i])
    sessions = [(s, i, p) for i, sentence in enumerate(sentences) for s, p in sentence.sessions]
    _check_ins(sentences, arrivals, sessions, arrived)
    _link_times(sentences, links, sessions)
    periods += _one_day_periods(sentences, sessions, details_later)
    return Found(
        sessions=_kept_sessions(sentences, sessions, arrived, modes),
        periods=_kept_periods(periods, arrived),
        deadlines=_kept_deadlines(deadlines, heading, modes),
    )
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: PASS (`107 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_times.py agent/tests/test_mail_times.py
git commit -m "feat(agent): the time reader finds sessions with their end, check-in, link time, mode, relative day and label

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The meeting and registered flags

`meeting` marks any class activity that may need Join, not only a meeting (spec §2). `registered` marks an email saying that you have registered or confirmed. Both are read from the subject and the cleaned text.

**Files:**
- Modify: `agent/sla_agent/mail_times.py`
- Test: `agent/tests/test_mail_times.py`

**Interfaces:**
- Consumes: `mail_words.MEETING`, `NOT_A_MEETING` and `REGISTERED`.
- Produces: the final `read_times(subject, text, arrived) -> Found`, with every field filled.

- [ ] **Step 1: Write the failing tests**

Add to the end of `agent/tests/test_mail_times.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py`
Expected: FAIL with `6 failed` in `test_the_meeting_flag` and `test_the_registered_flag`: no flag is set yet.

- [ ] **Step 3: Add the flags**

In `agent/sla_agent/mail_times.py`, add with two blank lines between, right before the line `# ---- the reader ------------------------------------------------------------------------------------------------------`:

```python
# ---- flags (§2) ------------------------------------------------------------------------------------------------------


def _flag(text, role, unless=None):
    """Whether `text` (NFC) has a word of `role` that is not inside a word of `unless`."""
    spans = role.spans(text)
    if unless is not None:
        spans = [s for s in spans if not any(a <= s[0] and s[1] <= b for a, b in unless.spans(text))]
    return bool(spans)
```

In `agent/sla_agent/mail_times.py`, replace `read_times` (from the line `def read_times(subject, text, arrived):` to the end of the file) with:

```python
def read_times(subject, text, arrived):
    """Found: the sessions, Periods, deadlines and flags of one email that arrived on `arrived` (a Vietnam date)."""
    sentences = [_Sentence(s, arrived) for s in _sentences(clean(subject, text))]
    subject = unicodedata.normalize("NFC", subject or "")
    heading = _Sentence(subject, arrived)
    modes = _Modes(any(s.spans(words.ONLINE) for s in sentences), any(s.spans(words.IN_PERSON) for s in sentences))
    details_later = any(_says_later(s) for s in sentences)

    deadlines = [(heading, d, p) for d, p in _deadlines(heading)]  # the subject gives deadlines only
    arrivals, links = [], []
    for i, sentence in enumerate(sentences):
        _drop(sentence)
        arrivals += [(i, clock) for clock in _arrivals(sentence)]
        deadlines += [(sentence, d, p) for d, p in _deadlines(sentence)]
        links += [(i, clock, minutes) for clock, minutes in _links(sentence)]
        _notices(sentence)
    periods, given = [], []
    for i in range(len(sentences)):
        found, made = _periods(sentences, i, details_later)
        periods += found
        given.append(made)
    for i in range(len(sentences)):
        _sessions(sentences, i, arrived, given[i])
    sessions = [(s, i, p) for i, sentence in enumerate(sentences) for s, p in sentence.sessions]
    _check_ins(sentences, arrivals, sessions, arrived)
    _link_times(sentences, links, sessions)
    periods += _one_day_periods(sentences, sessions, details_later)
    texts = [subject] + [s.text for s in sentences]
    return Found(
        sessions=_kept_sessions(sentences, sessions, arrived, modes),
        periods=_kept_periods(periods, arrived),
        deadlines=_kept_deadlines(deadlines, heading, modes),
        meeting=any(_flag(t, words.MEETING, words.NOT_A_MEETING) for t in texts),
        registered=any(_flag(t, words.REGISTERED) for t in texts),
    )
```

- [ ] **Step 4: Run the reader's tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times.py agent/tests/test_mail_words.py agent/tests/test_mail_phrases.py`
Expected: PASS (`221 passed`)

- [ ] **Step 5: Commit**

```bash
git add agent/sla_agent/mail_times.py agent/tests/test_mail_times.py
git commit -m "feat(agent): the time reader sets the meeting and registered flags

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The scorecard and the whole test set

**Files:**
- Create: `agent/tools/mail_times_score.py`
- Test: `agent/tests/test_mail_times_score.py`, `agent/tests/test_mail_times_cases.py`

**Interfaces:**
- Consumes: `read_times` (Task 9); the fixture (Task 2).
- Produces:
  - `as_case_fields(found) -> dict`: a `Found` written in the case format of Task 2. Tasks 11 and 12 use it.
  - `score(cases) -> (dict[part, (right, all)], list[(case id, [wrong parts])])`.
  - `PARTS`: "sessions", "ends", "check-ins and links", "modes, relative days, labels", "periods", "deadlines" and "flags".
  - `KNOWN_MISSES` in `test_mail_times_cases.py`, which is empty.

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_mail_times_score.py`:

```python
"""The scorecard of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §8.2)."""

from agent.tools.mail_times_score import PARTS, score

SESSION = dict(day="2026-10-15", start="14:00", end=None, end_is_approximate=False, ends_next_day=False,
               check_in="13:45", link_opens=None, mode=None, relative=None, label=None)
CASE = dict(id="Mail 01", arrived="2026-10-07", subject="Hội thảo",
            text="Hội thảo lúc 14:00 ngày 15/10/2026.\nCó mặt trước 13:45.\nHạn đăng ký: 12/10.",
            sessions=[SESSION], periods=[], deadlines=[dict(kind="register", day="2026-10-12", time=None, mode=None)],
            meeting=False, registered=False)


def test_a_right_case_counts_in_every_part():
    totals, wrong = score([CASE])

    assert totals == {part: (1, 1) for part in PARTS}
    assert wrong == []


def test_a_wrong_part_is_named():
    totals, wrong = score([dict(CASE, sessions=[dict(SESSION, check_in="13:30")])])

    assert totals["check-ins and links"] == (0, 1)
    assert totals["sessions"] == totals["deadlines"] == (1, 1)
    assert wrong == [("Mail 01", ["check-ins and links"])]
```

Create `agent/tests/test_mail_times_cases.py`:

```python
"""The whole test set of the mail time reader (spec 2026-10-07-mail-event-kinds-design.md §8.1): the student's test
mails and the short cases of the design discussion, each with the result the student checked. They come from
docs/superpowers/specs/2026-10-07-mail-event-kinds-cases.md, made into fixtures/mail-times-cases.json by
agent/tools/mail_times_cases.py."""

import json
from datetime import date
from pathlib import Path

import pytest

from agent.tools.mail_times_score import as_case_fields
from sla_agent.mail_times import read_times

CASES = json.loads((Path(__file__).parent / "fixtures" / "mail-times-cases.json").read_text(encoding="utf-8"))["cases"]
FIELDS = ("sessions", "periods", "deadlines", "meeting", "registered")
# Ids of cases the student agreed the reader may get wrong; the cases document lists them too.
KNOWN_MISSES = set()


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_each_case_reads_as_the_student_checked(case):
    if case["id"] in KNOWN_MISSES:
        pytest.xfail("a known miss the student agreed to")

    found = read_times(case["subject"], case["text"], date.fromisoformat(case["arrived"]))

    assert as_case_fields(found) == {field: case[field] for field in FIELDS}
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times_score.py agent/tests/test_mail_times_cases.py`
Expected: FAIL while collecting: `ModuleNotFoundError: No module named 'agent.tools.mail_times_score'`.

- [ ] **Step 3: Write the scorecard**

Create `agent/tools/mail_times_score.py`:

```python
"""The scorecard of the mail time reader on its test set (spec 2026-10-07-mail-event-kinds-design.md §8.2): for each
part, how many cases are right, and which cases are wrong. Run from the repository's folder:

    python -m agent.tools.mail_times_score
"""

import json
from datetime import date
from pathlib import Path

from sla_agent.mail_times import read_times

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mail-times-cases.json"
# Each part compares these fields of every session, or a whole list or flag.
SESSION_PARTS = {
    "sessions": ("day", "start"),
    "ends": ("day", "start", "end", "end_is_approximate", "ends_next_day"),
    "check-ins and links": ("day", "start", "check_in", "link_opens"),
    "modes, relative days, labels": ("day", "start", "mode", "relative", "label"),
}
PARTS = tuple(SESSION_PARTS) + ("periods", "deadlines", "flags")


def _hm(clock):
    return clock.strftime("%H:%M") if clock else None


def as_case_fields(found):
    """A Found written as the cases write it (agent/tools/mail_times_cases.py)."""
    return dict(
        sessions=[dict(day=s.day.isoformat(), start=_hm(s.start), end=_hm(s.end), end_is_approximate=s.end_is_approximate,
                       ends_next_day=s.ends_next_day, check_in=_hm(s.check_in), link_opens=_hm(s.link_opens),
                       mode=s.mode, relative=s.relative, label=s.label) for s in found.sessions],
        periods=[dict(first_day=p.first_day.isoformat(), last_day=p.last_day.isoformat(), mode=p.mode,
                      from_time=_hm(p.from_time), to_time=_hm(p.to_time), details_later=p.details_later, label=p.label)
                 for p in found.periods],
        deadlines=[dict(kind=d.kind, day=d.day.isoformat(), time=_hm(d.at), mode=d.mode) for d in found.deadlines],
        meeting=found.meeting,
        registered=found.registered,
    )


def _part(fields, part):
    if part in SESSION_PARTS:
        return [{key: s[key] for key in SESSION_PARTS[part]} for s in fields["sessions"]]
    if part == "flags":
        return fields["meeting"], fields["registered"]
    return fields[part]


def score(cases):
    """({part: (right, all)}, [(case id, [wrong parts])]) of the reader on `cases`."""
    right, wrong = dict.fromkeys(PARTS, 0), []
    for case in cases:
        found = as_case_fields(read_times(case["subject"], case["text"], date.fromisoformat(case["arrived"])))
        parts = [part for part in PARTS if _part(found, part) != _part(case, part)]
        for part in PARTS:
            right[part] += part not in parts
        if parts:
            wrong.append((case["id"], parts))
    return {part: (n, len(cases)) for part, n in right.items()}, wrong


def main():
    totals, wrong = score(json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"])
    for part, (n, total) in totals.items():
        print(f"{part:<30} {n:>3}/{total}")
    for case_id, parts in wrong:
        print(f"wrong: {case_id}: {', '.join(parts)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests: every one of the 127 cases passes**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_mail_times_score.py agent/tests/test_mail_times_cases.py`
Expected: PASS (`129 passed`)

- [ ] **Step 5: Print the scorecard**

Run: `.venv/Scripts/python.exe -m agent.tools.mail_times_score`
Expected: every part is `127/127` and no line starts with `wrong:`.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/mail_times_score.py agent/tests/test_mail_times_score.py agent/tests/test_mail_times_cases.py
git commit -m "test(agent): the time reader's scorecard, and every checked case as a test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: `sort_email` uses the reader; the old finder goes

From here the agent uploads what the new reader finds, mapped to today's format (§4.4). Every expectation of the old session tests stays, except the two this design changes on purpose: a length now gives the end ("kéo dài 2h" ends at 16:00), and "8 giờ sáng" is read. Three real samples change what they upload (spec §8.1):

- Samples 20 and 23 (civic education) gain `register_by` 2026-09-22, from their heading "THỜI GIAN ĐĂNG KÝ".
- Sample 24 (beFood) loses its two sessions on 20/09: its ordering hours are two daily Periods.

**Files:**
- Modify: `agent/sla_agent/mail_rules.py`, `agent/sla_agent/class_changes.py`, `agent/tests/fixtures/mail-samples.json`
- Test: `agent/tests/test_sessions.py`, `agent/tests/test_mail_rules.py`, `agent/tests/test_mail_times_cases.py`

**Interfaces:**
- Consumes: `read_times`, `Found`, `clean` and `MAX_SESSIONS` (`mail_times`); `as_case_fields` (Task 10).
- Produces:
  - `mail_rules.times_of(email, arrived) -> Found`: an empty `Found` when the reader fails, logging only the error's class name.
  - `mail_rules.upload_sessions(found) -> list[MailSession]`: the start is the check-in when there is one; there is no end when the session ends the next day; a repeated day and start is kept once; sorted.
  - `sort_email` sets `dates` from the cleaned text, `sessions` from `upload_sessions`, and `register_by` from `Found.register_by`.
  - `class_changes` no longer has `Session`, `sessions_in`, `register_by_in`, `MAX_SESSIONS` or `DAY_EDGES`.

- [ ] **Step 1: Write the failing tests**

The old session tests now read through the new reader and today's upload.

In `agent/tests/test_sessions.py`, replace:

```python
"""The times an event takes place, found in an email's subject and text on the laptop (spec
2026-09-28-mailbox-events-design.md, section 3.2). Only days and times ever leave the laptop."""
```

with:

```python
"""The times an event takes place, as stage 1 uploads them (spec 2026-10-07-mail-event-kinds-design.md §4.4): read by
the mail time reader, with a check-in moving the start (mailbox-events addendum A.1). These are the expectations the
first reader had (mailbox-events 3.2); the new design changes two on purpose: a length now gives the end ("kéo dài
2h"), and "8 giờ sáng" is read. Only days and times ever leave the laptop."""
```

In `agent/tests/test_sessions.py`, replace:

```python
from sla_agent.class_changes import MAX_SESSIONS, Session, register_by_in, sessions_in
```

with:

```python
from sla_agent.mail_rules import upload_sessions
from sla_agent.mail_times import MAX_SESSIONS, read_times
```

In `agent/tests/test_sessions.py`, replace:

```python
def found(text):
    return [(s.day.strftime("%d/%m"), s.start.strftime("%H:%M"), s.end and s.end.strftime("%H:%M"))
            for s in sessions_in(text, ARRIVED)]
```

with:

```python
def found(text, arrived=ARRIVED):
    return [(s.day.strftime("%d/%m"), s.start.strftime("%H:%M"), s.end and s.end.strftime("%H:%M"))
            for s in upload_sessions(read_times("", text, arrived))]


def register_by(text, arrived=ARRIVED):
    return read_times("", text, arrived).register_by
```

In `agent/tests/test_sessions.py`, replace:

```python
@pytest.mark.parametrize("text", [
    "Thời gian: 14h00 ngày 30/9, kéo dài 2h",
    "Workshop 14h ngày 30/9 (2h)",
    "Ngày 30/9 lúc 14h. Thời lượng: 1h30",
    "Ngày 30/9 lúc 14h, mỗi buổi trong vòng 2h",
    "Talk on 30/9 at 14h, lasting 2h",
])
def test_a_length_is_not_a_time(text):
    assert found(text) == [("30/09", "14:00", None)]
```

with:

```python
@pytest.mark.parametrize("text, end", [
    ("Thời gian: 14h00 ngày 30/9, kéo dài 2h", "16:00"),  # changed on purpose: a length gives the end
    ("Workshop 14h ngày 30/9 (2h)", None),
    ("Ngày 30/9 lúc 14h. Thời lượng: 1h30", "15:30"),
    ("Ngày 30/9 lúc 14h, mỗi buổi trong vòng 2h", "16:00"),
    ("Talk on 30/9 at 14h, lasting 2h", "16:00"),
])
def test_a_length_is_not_a_time(text, end):
    assert found(text) == [("30/09", "14:00", end)]
```

In `agent/tests/test_sessions.py`, replace:

```python
    ("2h chiều", "14:00"), ("2h30 chiều", "14:30"), ("7h tối", "19:00"), ("8 giờ sáng", None), ("8h sáng", "08:00"),
    ("5h sáng", "05:00"), ("1h trưa", "13:00"), ("11h trưa", "11:00"), ("12h trưa", "12:00"), ("14h chiều", "14:00"),
])
def test_a_time_of_day_word_after_the_hour(written, start):
    assert found(f"Ngày 30/9 lúc {written}") == ([("30/09", start, None)] if start else [])
```

with:

```python
    ("2h chiều", "14:00"), ("2h30 chiều", "14:30"), ("7h tối", "19:00"), ("8 giờ sáng", "08:00"), ("8h sáng", "08:00"),
    ("5h sáng", "05:00"), ("1h trưa", "13:00"), ("11h trưa", "11:00"), ("12h trưa", "12:00"), ("14h chiều", "14:00"),
])
def test_a_time_of_day_word_after_the_hour(written, start):
    assert found(f"Ngày 30/9 lúc {written}") == [("30/09", start, None)]
```

In `agent/tests/test_sessions.py`, replace:

```python
    sessions = sessions_in(f"Các buổi: {days}, lúc 18h", ARRIVED)

    assert len(sessions) == MAX_SESSIONS
    assert sessions[0] == Session(date(2026, 10, 1), time(18, 0))
    assert sessions == sorted(sessions)
```

with:

```python
    sessions = upload_sessions(read_times("", f"Các buổi: {days}, lúc 18h", ARRIVED))

    assert len(sessions) == MAX_SESSIONS
    assert (sessions[0].day, sessions[0].start) == (date(2026, 10, 1), time(18, 0))
    assert sessions == sorted(sessions, key=lambda s: (s.day, s.start))
```

In `agent/tests/test_sessions.py`, replace:

```python
    assert sessions_in("", ARRIVED) == []
    assert sessions_in(None, ARRIVED) == []
```

with:

```python
    assert found("") == []
    assert found(None) == []
```

In `agent/tests/test_sessions.py`, add with two blank lines between, right before the line `# ---- the registration deadline (addendum A.2) ---------------------------------------------------------------------`:

```python
def test_a_session_that_ends_the_next_day_is_uploaded_without_its_end():
    assert found("Sự kiện diễn ra từ 22:00 ngày 31/12/2026 đến 00:30 ngày 01/01/2027.") == [("31/12", "22:00", None)]
```

In `agent/tests/test_sessions.py`, replace:

```python
    assert register_by_in(CLOSING, date(2026, 9, 20)) == date(2026, 9, 22)
    assert sessions_in(CLOSING, date(2026, 9, 20)) == [Session(date(2026, 9, 30), time(9, 45))]
```

with:

```python
    assert register_by(CLOSING, date(2026, 9, 20)) == date(2026, 9, 22)
    assert found(CLOSING, date(2026, 9, 20)) == [("30/09", "09:45", None)]
```

In `agent/tests/test_sessions.py`, replace:

```python
    assert register_by_in(text, ARRIVED) == deadline
```

with:

```python
    assert register_by(text) == deadline
```

In `agent/tests/test_sessions.py`, replace:

```python
    assert register_by_in(text, ARRIVED) is None
```

with:

```python
    assert register_by(text) is None
```

In `agent/tests/test_mail_rules.py`, replace:

```python
def test_an_email_the_session_finder_fails_on_keeps_its_sorting_and_logs_no_text(monkeypatch, caplog):
    def broken(text, from_day):
        raise ValueError(text)

    monkeypatch.setattr(mail_rules, "sessions_in", broken)

    with caplog.at_level(logging.WARNING):
        item = sort_email(email("Workshop ngày 30/9", "Bí mật riêng tư 12345, 14h00."), CONTEXT)

    assert (item.sorted, item.sessions, item.categories) == (True, [], ["event"])
    assert "Bí mật" not in caplog.text and "12345" not in caplog.text
```

with:

```python
def test_an_email_the_time_reader_fails_on_keeps_its_sorting_and_logs_no_text(monkeypatch, caplog):
    def broken(subject, text, arrived):
        raise ValueError(text)

    monkeypatch.setattr(mail_rules, "read_times", broken)

    with caplog.at_level(logging.WARNING):
        item = sort_email(email("Workshop ngày 30/9", "Bí mật riêng tư 12345, 14h00. Hạn đăng ký 25/9."), CONTEXT)

    assert (item.sorted, item.sessions, item.register_by, item.categories) == (True, [], None, ["event"])
    assert "Bí mật" not in caplog.text and "12345" not in caplog.text
```

In `agent/tests/test_mail_rules.py`, replace:

```python
def test_an_email_the_deadline_reader_fails_on_keeps_its_sorting_and_logs_no_text(monkeypatch, caplog):
    def broken(text, from_day):
        raise ValueError(text)

    monkeypatch.setattr(mail_rules, "register_by_in", broken)

    with caplog.at_level(logging.WARNING):
        item = sort_email(email("Workshop ngày 30/9", "Bí mật riêng tư 12345. Hạn đăng ký 25/9."), CONTEXT)

    assert (item.sorted, item.register_by, item.categories) == (True, None, ["event"])
    assert "Bí mật" not in caplog.text and "12345" not in caplog.text
```

with:

```python
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
```

In `agent/tests/test_mail_times_cases.py`, replace:

```python
agent/tools/mail_times_cases.py."""
```

with:

```python
agent/tools/mail_times_cases.py. Each case also checks that its text never reaches its upload (§7.5)."""
```

In `agent/tests/test_mail_times_cases.py`, replace:

```python
import json
from datetime import date
from pathlib import Path

import pytest

from agent.tools.mail_times_score import as_case_fields
from sla_agent.mail_times import read_times
```

with:

```python
import json
import re
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from agent.tools.mail_times_score import as_case_fields
from sla_agent.class_changes import fold
from sla_agent.mail_rules import Context, Email, sort_email
from sla_agent.mail_times import read_times
```

Add to the end of `agent/tests/test_mail_times_cases.py`:

```python
def _strings(value, leave_out=("subject", "categories")):
    """Every string inside an upload, but its subject (already shown) and its categories (codes)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, inner in value.items():
            if key not in leave_out:
                yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings(inner)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_no_part_of_a_mails_text_reaches_its_upload(case):
    email = Email(key="0" * 64, entry_id="00AB", thread_id=None,
                  received_at=datetime.combine(date.fromisoformat(case["arrived"]), time(2), tzinfo=timezone.utc),
                  sender_name="Someone", sender_address="someone@example.com", subject=case["subject"], text=case["text"])

    upload = " ".join(fold(s) for s in _strings(sort_email(email, Context()).model_dump(mode="json")))

    words = set(re.findall(r"[^\W\d_]{5,}", fold(case["text"]))) - set(re.findall(r"\w+", fold(case["subject"])))
    assert words & set(re.findall(r"[^\W\d_]{5,}", upload)) == set()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_sessions.py agent/tests/test_mail_rules.py agent/tests/test_mail_times_cases.py`
Expected: FAIL while collecting: `ImportError: cannot import name 'upload_sessions' from 'sla_agent.mail_rules'`.

- [ ] **Step 3: `sort_email` uses the reader**

In `agent/sla_agent/mail_rules.py`, replace:

```python
"""Sorting one email on the laptop: who sent it, its categories, its dates, and the class changes it
announces. Pure functions. The rules are in docs/superpowers/specs/2026-09-28-outlook-mailbox-design.md,
section 5.
```

with:

```python
"""Sorting one email on the laptop: who sent it, its categories, its dates, its times, and the class changes it
announces. Pure functions. The rules are in docs/superpowers/specs/2026-09-28-outlook-mailbox-design.md,
section 5; the times are read by mail_times (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md).
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
from sla_agent.class_changes import dates_in, fold, read_announcement, register_by_in, sessions_in
from sla_agent.mail_words import Words
```

with:

```python
from sla_agent.class_changes import dates_in, fold, read_announcement
from sla_agent.mail_times import Found, clean, read_times
from sla_agent.mail_words import Words
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
def sessions_of(email, arrived):
    """The times the email's event or school task takes place (mailbox-events 3.2), found in every email so they
    are ready when the student moves one to Event. Only the text is read: a time in the subject is often a summary
    that repeats (or rounds) the text's. [] when the finder fails on it."""
    try:
        return [MailSession(day=s.day, start=s.start, end=s.end) for s in sessions_in(email.text, arrived)]
    except Exception as error:  # the message could quote the email
        log.warning("Couldn't read the times in an email (%s); it is uploaded without them",
                    error.__class__.__name__)
        return []


def register_by_of(email, arrived):
    """The email's registration deadline (mailbox-events addendum A.2), found in every email; None when there is
    none or the reader fails on it."""
    try:
        return register_by_in(email.subject + "\n" + email.text, arrived)
    except Exception as error:  # the message could quote the email
        log.warning("Couldn't read the registration deadline in an email (%s); it is uploaded without one",
                    error.__class__.__name__)
        return None
```

with:

```python
def times_of(email, arrived):
    """The email's sessions, Periods, deadlines and flags (mail_times), read in every email so they are ready when
    the student moves one to Event. An empty Found when the reader fails on it."""
    try:
        return read_times(email.subject, email.text, arrived)
    except Exception as error:  # the message could quote the email
        log.warning("Couldn't read the times in an email (%s); it is uploaded without them",
                    error.__class__.__name__)
        return Found()


def upload_sessions(found):
    """The sessions as today's upload holds them (spec 2026-10-07-mail-event-kinds-design.md §4.4): a check-in moves
    the start (mailbox-events addendum A.1), and an end on the next day is left out."""
    kept = {}
    for session in found.sessions:
        start = session.check_in or session.start
        end = None if session.ends_next_day else session.end
        kept.setdefault((session.day, start), MailSession(day=session.day, start=start, end=end))
    return [kept[key] for key in sorted(kept)]
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
        code = course_of(email, context) if lecturer else None
```

with:

```python
        code = course_of(email, context) if lecturer else None
        found = times_of(email, arrived)
```

In `agent/sla_agent/mail_rules.py`, replace:

```python
            dates=dates_in(email.subject + "\n" + email.text, arrived)[:MAX_DATES],
            sessions=sessions_of(email, arrived),
            register_by=register_by_of(email, arrived),
```

with:

```python
            dates=dates_in(email.subject + "\n" + clean(email.subject, email.text), arrived)[:MAX_DATES],
            sessions=upload_sessions(found),
            register_by=found.register_by,
```

- [ ] **Step 4: Remove the old finder from `class_changes.py`**

Delete from the bottom up, so each deletion's line numbers are those of the file as it is now.

In `agent/sla_agent/class_changes.py`, delete the old session finder and deadline reader: `_ampm`, `_is_length`, `_session_times`, `_is_check_in`, `sessions_in` and `register_by_in` (lines 218–322): from the line `def _ampm(sentence, match):` to the end of the file, and the blank lines after it.

In `agent/sla_agent/class_changes.py`, delete `class Session` (lines 121–124): from the line `class Session(NamedTuple):` through the line `    end: time | None = None`, and the blank lines after it.

In `agent/sla_agent/class_changes.py`, delete `_words` and the patterns built from it: `DEADLINE`, `TIME_OF_DAY`, `LENGTH_BEFORE`, `CHECK_IN`, `REGISTER` (lines 98–110): from the line `def _words(words):` through the line `REGISTER = re.compile(r"\b(?:dang\s+ky|register|registration|sign\s*-?\s*up)\b")`, and the blank lines after it.

In `agent/sla_agent/class_changes.py`, delete the session constants: `SESSION_TIME`, `SESSION_JOIN`, `DEADLINE_WORDS`, `LENGTH_WORDS`, `EARLIEST_BARE_HOUR`, `DAY_EDGES`, `MAX_SESSIONS` (lines 70–89): from the line `# Sessions (mailbox-events 3.2): a time is a start alone, or a start and an end joined by one of these. "01.10"` through the line `MAX_SESSIONS = 10`, and the blank lines after it.

In `agent/sla_agent/class_changes.py`, replace:

```python
"""Class changes announced by lecturers: online, cancelled and make-up classes; the dates in a text; and the
times an event takes place (sessions). Pure functions.
```

with:

```python
"""Class changes announced by lecturers: online, cancelled and make-up classes; and the dates in a text. Pure
functions. (An email's own times are read by mail_times, docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md.)
```

In `agent/sla_agent/class_changes.py`, replace:

```python
suites check every example in it.

Sessions follow docs/superpowers/specs/2026-09-28-mailbox-events-design.md, section 3.2, and its addendum of
2026-09-29 (check-in times, the registration deadline)."""
```

with:

```python
suites check every example in it."""
```

- [ ] **Step 5: Samples 20, 23 and 24 upload what the reader gives**

Save this script outside the repository, as `fix_samples.py` in your scratch folder, and run it from the repository's folder with `.venv/Scripts/python.exe <scratch folder>/fix_samples.py`. It prints `samples 20, 23 and 24 changed`.

```python
"""Samples 20, 23 and 24 upload what the new reader gives (spec 2026-10-07-mail-event-kinds-design.md §8.1). Run once,
from the repository's folder."""
import json
from pathlib import Path

PATH = Path("agent/tests/fixtures/mail-samples.json")
samples = json.loads(PATH.read_text(encoding="utf-8"))
emails = samples["emails"]
assert [emails[n]["expected"]["register_by"] for n in (20, 23)] == [None, None]
assert len(emails[24]["expected"]["sessions"]) == 2
for n in (20, 23):  # civic education: the heading "THỜI GIAN ĐĂNG KÝ", then "Từ ngày 20/09 đến 22/09/2026."
    emails[n]["expected"]["register_by"] = "2026-09-22"
emails[24]["expected"]["sessions"] = []  # beFood: its ordering hours are two daily Periods, not two events on 20/09
PATH.write_text(json.dumps(samples, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("samples 20, 23 and 24 changed")
```

- [ ] **Step 6: Run all the agent's tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests`
Expected: PASS (`1298 passed`)

- [ ] **Step 7: Commit**

```bash
git add agent/sla_agent/mail_rules.py agent/sla_agent/class_changes.py agent/tests/test_sessions.py agent/tests/test_mail_rules.py agent/tests/test_mail_times_cases.py agent/tests/fixtures/mail-samples.json
git commit -m "feat(agent): sort_email reads each email's times with the new reader and uploads them as today; the old session finder goes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The real samples keep everything the reader finds

Each real sample keeps its checked upload and gains `found`, the reader's full result. A test then holds the reader to it (spec §8.1).

**Files:**
- Modify: `agent/tools/anonymize_mail.py`, `agent/tests/fixtures/mail-samples.json`
- Test: `agent/tests/test_anonymize_mail.py`, `agent/tests/test_mail_samples.py`

**Interfaces:**
- Consumes: `as_case_fields` (Task 10), `read_times` (Task 9) and `mail_rules.VIETNAM_OFFSET`.
- Produces: every sample in `mail-samples.json` has `expected.found` in the case format. `anonymize_mail.sample(email, context)` writes it for new samples.

- [ ] **Step 1: Write the failing tests**

In `agent/tests/test_anonymize_mail.py`, replace:

```python
from agent.tools.anonymize_mail import PLACEHOLDER_TEXT, anonymize
```

with:

```python
from agent.tools.anonymize_mail import PLACEHOLDER_TEXT, anonymize, sample
```

Add to the end of `agent/tests/test_anonymize_mail.py`:

```python
def test_a_sample_keeps_everything_the_time_reader_finds():
    workshop = Email(key="9" * 64, entry_id="00AB", thread_id=None, received_at=ARRIVED, sender_name="P.CTSV [OSS]",
                     sender_address="oss@hcmiu.edu.vn", subject="Hội thảo",
                     text="Hội thảo lúc 14:00 ngày 30/09/2026. Có mặt trước 13:45. Hạn đăng ký: 25/9.")

    found = sample(workshop, Context())["expected"]["found"]

    assert found["sessions"] == [dict(day="2026-09-30", start="14:00", end=None, end_is_approximate=False,
                                      ends_next_day=False, check_in="13:45", link_opens=None, mode=None, relative=None,
                                      label=None)]
    assert found["deadlines"] == [dict(kind="register", day="2026-09-25", time=None, mode=None)]
```

In `agent/tests/test_mail_samples.py`, replace:

```python
made by agent/tools/anonymize_mail.py. Each `expected` result, sessions included, was checked by the student."""

import json
from datetime import datetime
```

with:

```python
made by agent/tools/anonymize_mail.py. Each `expected` result, sessions included, was checked by the student; so
was `found`, everything the mail time reader finds (spec 2026-10-07-mail-event-kinds-design.md §8.1)."""

import json
from datetime import datetime, timedelta, timezone
```

In `agent/tests/test_mail_samples.py`, replace:

```python
from sla_agent.mail_rules import Context, Email, sort_email
```

with:

```python
from agent.tools.mail_times_score import as_case_fields
from sla_agent.mail_rules import Context, Email, sort_email
from sla_agent.mail_times import read_times
```

In `agent/tests/test_mail_samples.py`, replace:

```python
    } == sample["expected"]
```

with:

```python
    } == {key: value for key, value in sample["expected"].items() if key != "found"}
```

Add to the end of `agent/tests/test_mail_samples.py`:

```python
@pytest.mark.parametrize("sample", SAMPLES["emails"],
                         ids=[f"{n:02d} {s['subject'][:40]}" for n, s in enumerate(SAMPLES["emails"])])
def test_each_email_reads_as_the_student_checked(sample):
    arrived = (datetime.fromisoformat(sample["received_at"]).astimezone(timezone.utc) + timedelta(hours=7)).date()

    found = read_times(sample["subject"], sample["text"], arrived)

    assert as_case_fields(found) == sample["expected"]["found"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_anonymize_mail.py agent/tests/test_mail_samples.py`
Expected: FAIL with `58 failed`, each a `KeyError: 'found'`: `test_a_sample_keeps_everything_the_time_reader_finds` and the 57 `test_each_email_reads_as_the_student_checked`.

- [ ] **Step 3: The anonymizer keeps `found`**

In `agent/tools/anonymize_mail.py`, replace:

```python
(docs/superpowers/specs/2026-09-28-mailbox-events-design.md, 3.2); the student checks them before the file is
```

with:

```python
(docs/superpowers/specs/2026-09-28-mailbox-events-design.md, 3.2), and `found` everything the mail time reader
finds (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md); the student checks them before the file is
```

In `agent/tools/anonymize_mail.py`, replace:

```python
from sla_agent.mail_rules import (
```

with:

```python
from sla_agent.mail_rules import (
    VIETNAM_OFFSET,
```

In `agent/tools/anonymize_mail.py`, replace:

```python
from sla_agent.outlook_reader import inbox_of, open_outlook, read_emails, semester_start
from sla_agent.state import load_state
```

with:

```python
from sla_agent.mail_times import read_times
from sla_agent.outlook_reader import inbox_of, open_outlook, read_emails, semester_start
from sla_agent.state import load_state

from agent.tools.mail_times_score import as_case_fields
```

In `agent/tools/anonymize_mail.py`, replace:

```python
    item = sort_email(email, context)
```

with:

```python
    item = sort_email(email, context)
    arrived = (email.received_at.astimezone(timezone.utc) + VIETNAM_OFFSET).date()
```

In `agent/tools/anonymize_mail.py`, replace:

```python
            "class_changes": [c.model_dump(mode="json", exclude_none=True) for c in item.class_changes],
```

with:

```python
            "class_changes": [c.model_dump(mode="json", exclude_none=True) for c in item.class_changes],
            "found": as_case_fields(read_times(email.subject, email.text, arrived)),
```

- [ ] **Step 4: Add `found` to every sample**

Save this script outside the repository, as `add_found.py` in your scratch folder, and run it from the repository's folder with `.venv/Scripts/python.exe <scratch folder>/add_found.py`. It prints `57 samples now keep what the reader finds`.

```python
"""Adds `found`, everything the mail time reader finds, to each real sample's expected result. Run once, from the
repository's folder."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))  # agent.tools is found from the repository's folder

from agent.tools.mail_times_score import as_case_fields  # noqa: E402
from sla_agent.mail_times import read_times  # noqa: E402

PATH = Path("agent/tests/fixtures/mail-samples.json")
samples = json.loads(PATH.read_text(encoding="utf-8"))
for sample in samples["emails"]:
    arrived = (datetime.fromisoformat(sample["received_at"]).astimezone(timezone.utc) + timedelta(hours=7)).date()
    sample["expected"]["found"] = as_case_fields(read_times(sample["subject"], sample["text"], arrived))
PATH.write_text(json.dumps(samples, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(f"{len(samples['emails'])} samples now keep what the reader finds")
```

- [ ] **Step 5: The student checks what is new**

`found` holds what the upload already had (checked before) and new information. Each row below is the new information in one real sample, written as in the cases document. Samples not listed gain nothing new. The meeting flag only matters on a Class email with at least one session (spec §6.2). So on the Microsoft notices (04, 28, 32) and the Event emails (03, 19, 36, 44) it changes nothing, and only sample 27, an online class, becomes something to join.

| # | Subject | What is new |
|---|---|---|
| 03 | [THÔNG BÁO] TIẾP NHẬN ĐĂNG KÝ THAM GIA WORKSHOP BEAN TO BOLD | Session: Tue 29/09 14:00–16:30 · check-in 13:00<br>Flags: meeting |
| 04 | Your Teams meeting recording has expired and is now deleted | Flags: meeting |
| 05 | Thông báo về việc đăng ký tạm trú và cập nhật thông tin cư trú | Deadlines: due Sat 03/10 |
| 19 | [Thông báo] Thư Mời Tham Gia Workshop Nha Khoa Học Đường 2026: “Hiểu Đ… | Flags: meeting |
| 20 | THÔNG BÁO: CHƯƠNG TRÌNH SINH HOẠT CÔNG DÂN GIỮA KHÓA (2026 - 2027) | Deadlines: registration opens Sun 20/09 · register by Tue 22/09 |
| 23 | THÔNG BÁO: CHƯƠNG TRÌNH SINH HOẠT CÔNG DÂN GIỮA KHÓA (2026 - 2027) | Deadlines: registration opens Sun 20/09 · register by Tue 22/09 |
| 24 | [Thông báo] Mời sinh viên ủng hộ trường theo chương trình [IU x beFood… | Period: Mon 14/09 → Sun 20/09 · all day · label Final<br>Period: Thu 17/09 → Sun 20/09 · 08:00–11:30 each day<br>Period: Thu 17/09 → Sun 20/09 · 13:00–16:00 each day |
| 26 | THÔNG TIN VỀ CUỘC THI TIẾNG ANH STAR AWARD - VÒNG THI TRẮC NGHIỆM STAR… | Period: Fri 04/09 → Mon 05/10 · all day<br>Period: Mon 14/09 → Sun 20/09 · all day<br>Period: Mon 21/09 → Sun 27/09 · all day<br>Period: Mon 28/09 → Mon 05/10 · all day |
| 27 | Web Application Development_S1_2026-27_G02: Online Class Notification … | Session: Tue 22/09 from 08:00 · online<br>Flags: meeting |
| 28 | Your Teams meeting recording has expired and is now deleted | Flags: meeting |
| 32 | Your Teams meeting recording has expired and is now deleted | Flags: meeting |
| 36 | [HSV] - Thư mời đăng ký tham gia Talkshow về “ An toàn tình dục & Sức … | Flags: meeting |
| 44 | [HSV] - Thư mời đăng ký tham gia các chương trình của Tuần lễ Chào đón… | Period: Mon 07/09 → Sat 12/09 · all day<br>Flags: meeting |
| 48 | [UHub Network x GOOGLE] Thư thông báo theo dõi tình trạng đăng ký tham… | Session: Mon 31/08 from 19:30 · online |
| 49 | V/v thực hiện "Khảo sát sự hài lòng của người học với trải nghiệm học … | Period: Thu 13/08 → Wed 26/08 · all day |
| 51 | [UHub Network x GOOGLE] Thư thông báo theo dõi tình trạng đăng ký tham… | Session: Tue 25/08 from 19:30 · online |
| 54 | [HSV] - Khảo sát "Doanh nghiệp yêu thích 2026 - Enterprise of Choice" | Deadlines: due Thu 27/08 |

Commit only once the student agrees with every row. If the student marks a row wrong, stop and fix that first:

1. Add the email to the cases document as a new case, with the right answer.
2. Rebuild the fixture (Task 2, Step 4).
3. Fix the reader, test first.
4. Run Step 4's script again.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_anonymize_mail.py agent/tests/test_mail_samples.py`
Expected: PASS (`120 passed`)

- [ ] **Step 7: Commit**

```bash
git add agent/tools/anonymize_mail.py agent/tests/test_anonymize_mail.py agent/tests/test_mail_samples.py agent/tests/fixtures/mail-samples.json
git commit -m "test(agent): each real sample keeps everything the time reader finds, checked by the student

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Version 0.5.0

**Files:**
- Modify: `agent/sla_agent/__init__.py`, `docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md`

- [ ] **Step 1: Set the version and the spec's status**

In `agent/sla_agent/__init__.py`, replace:

```python
__version__ = "0.4.2"
```

with:

```python
__version__ = "0.5.0"
```

In `docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md`, replace:

```markdown
**Status:** Approved 2026-10-07; stage 1 being planned
```

with:

```markdown
**Status:** Approved 2026-10-07; stage 1 built (agent 0.5.0)
```

- [ ] **Step 2: Run every test of the project**

Run: `.venv/Scripts/python.exe -m pytest`
Expected: PASS (`1465 passed`)

- [ ] **Step 3: Print the scorecard**

Run: `.venv/Scripts/python.exe -m agent.tools.mail_times_score`
Expected: every part is `127/127` and no line starts with `wrong:`.

- [ ] **Step 4: Commit**

```bash
git add agent/sla_agent/__init__.py docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md
git commit -m "chore(agent): version 0.5.0; stage 1 of the mail event kinds spec is built

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Hand over to the student**

Report the branch, its commits since 082ed22 and the test count. Each of these next steps is the student's decision:

1. **PR** from `mail-event-kinds` to `main`, with the sorting fixes inside. A teammate reviews and approves it before the merge (the lecturer's condition).
2. **Push** to the three repositories.
3. **Release:** push the tag `v0.5.0`, then the release workflow builds the `.exe`.
4. **A real-sync check** on the laptop. The agent looks for updates only every 24 hours.

Stage 2 (the upload format and the website) gets its own plan.
