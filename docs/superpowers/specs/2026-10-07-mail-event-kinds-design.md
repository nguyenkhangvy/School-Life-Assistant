# School-Life-Assistant: mail event kinds — a smarter time reader, Periods and deadlines

**Date:** 2026-10-07
**Scope:** read the times in Vietnamese school mail far more reliably, still with rules on the laptop; give every time its kind (Session, Period or Deadline) with its check-in, link, mode and approximate end; let the student add Periods to the Timetable; show every deadline; let lecturers' class activities be joined; read Outlook meeting invitations
**Owner:** Nguyen Khang Vy
**Status:** Approved 2026-10-07; stage 1 being planned
**Builds on:** [Outlook mail in a Mailbox tab](2026-09-28-outlook-mailbox-design.md) ("Outlook §5") and [a compact Mailbox, auto-Done, and events you can join](2026-09-28-mailbox-events-design.md) with its addendum ("Events §3.2", "A.1"). Everything there stays the same unless this document says otherwise. The reader reuses the accent-aware word matching of the sorting fixes on the branch `mail-rules-fixes` (082ed22).
**Test cases:** [2026-10-07-mail-event-kinds-cases.md](2026-10-07-mail-event-kinds-cases.md)

---

## 1. Goal

The agent finds each email's times on the laptop and the website shows them (Events §3). On the student's 50 test mails, today's reader gets 18 right. It turns deadlines, arrival times, end times and "email sent at" times into extra events, misses "14 giờ 00" and words like "ngày mai", and cannot say "come any time between 02/11 and 05/11". The goal is to read the times of Vietnamese school mail far more reliably, still with rules on the laptop, and to give every time its proper kind, so the student can form their calendar with a click or two.

The core rule:

> A **Session** is a scheduled occurrence and can clash. A **Period** is an availability window and never clashes. **Deadline** times are information and never become event time by themselves.

### Decided with the student (2026-10-06 and 2026-10-07)

- **Rules only.** The email's text never leaves the laptop. Reading by an AI service, or by a model on the laptop, was declined.
- **A two-step reader** (approach B): find and label every time phrase, then decide the kinds with a rule table. The word lists are data, kept in one file.
- **Three kinds:** Session, Period and Deadline (§2).
- **Periods are added by the student** ("Add"). An added Period shows as a bar in the Timetable's All-day row, never blocks time or causes clash marks, and is hidden while its card is Done. After its last day it only shows in past weeks.
- **Registration deadlines stay off the Timetable**, as today: they are a tag on the Mailbox row.
- **Every deadline is kept**, with its time, its kind (registration opens, register, confirm, due) and its mode (online or in person), instead of only the latest date. In-person and online deadlines are shown side by side, and passed ones are struck out.
- **Check-in, arrival and link-opens times stay separate from the start.** Clash marks and the Timetable block start from the check-in.
- **Approximate ends** ("khoảng 1 tiếng", "dự kiến") are kept and shown as "~11:00".
- **Labels** such as "Round 1" come from the app's own word list, never from the email's text.
- **Lecturers' class activities** can be joined: a Class email with a meeting or class-activity word (họp, gặp, hẹn, tư vấn, phỏng vấn, thuyết trình, kiểm tra giữa kỳ …) shows its times with clash marks and Join….
- **Registered ✓:** an email that confirms the student is registered says so on its row.
- **The Past rule of 29/9 stays** (A.3): an Event whose registration has closed, with nothing joined, moves to Past. Now also nothing added, and not registered.
- **The test set** is the student's 100 test mails (the student's own answer key for 1–50; 51–100 drafted and then checked by the student) plus the 57 real samples.
- **Built in three stages** (§9). One-click fixes and the class-change additions get their own specs (§10).
- **Whole days have no times** (decided in the review of the stage 1 plan): a Period from 00:00 to 23:59 is all day, so real sample 26's weekly contest rounds are all-day Periods.

### Not in scope

- One-click fixes and learning from them (part 2: its own spec, after stage 2; §10)
- Room changes, school holidays and lecturer tests in the class-change reader (their own spec, after stage 1; §10)
- Reading by AI
- The venue, the organiser or any other text of the email (unchanged from Events §1)
- Deadlines on the Timetable, reminders and notifications (unchanged)

---

## 2. What an email can hold

```
Email
 ├─ deadlines  opens · register · confirm · due                    day, time?, mode?
 ├─ sessions   day · start · end? (approximate? ends next day?)
 │             check-in? · link opens? · mode? · relative day? · label?
 ├─ periods    first day · last day · all_day | daily_window | one_window
 │             from/to time? · details later? · label?
 └─ flags      meeting · registered
```

**Session.** A time the student must be there.

- **start:** when the programme starts.
- **end:** optional. It is **approximate** when it comes from "khoảng", "dự kiến" or "about". It may be on the **next day** ("từ 22:00 ngày 31/12 đến 00:30 ngày 01/01").
- **check-in:** the time to be there by: check-in, điểm danh, có mặt (trước / lúc), đến trước, vui lòng đến, tập trung, đăng nhập (an online check-in), "phòng mở cửa từ 14h" (one time), vào khu vực từ, đăng ký tại chỗ. Never later than the start.
- **link opens:** when an online event's link becomes available ("Link Teams sẽ mở lúc 13:45"; "link sẽ được gửi trước 30 phút" is 30 minutes before the start). Never later than the start.
- **mode:** online or in person (§4.3, rule M).
- **relative day:** set when the day came from a word such as "ngày mai" (a code from §3.2).
- **label:** a code from §3.2, such as Round 1 or Shift 2.

**Period.** Something the student may attend or do at any time within a range.

- **all_day:** days only ("Tuần lễ diễn ra từ 26/10 đến 30/10"). A Period from 00:00 to 23:59 is all_day too, with no times: those are the edges of the day, not times the email sets ("từ 00g00 ngày 14/9 đến 23g59 ngày 20/9" is open all week).
- **daily_window:** the same hours each day ("mở cửa từ 09:00 đến 17:00 trong các ngày 02/11 đến 05/11").
- **one_window:** from a time on the first day to a time on the last day ("từ 09:00 ngày 28/11 đến 16:00 ngày 29/11"); on one day, simply from–to that day ("08:00 đến 16:00 ngày 14/11").
- **details later:** the email says the student's own time comes later ("sẽ được thông báo sau", "mỗi ứng viên sẽ có một khung giờ riêng").

**Deadline.** Information only, never event time. Each has a day, an optional time and an optional mode.

- **opens:** registration opens ("Mở đăng ký từ 05/10", "Form mở ngày 01/10", "Đăng ký từ 01/10", the start of a registration window).
- **register:** registration closes (đăng ký, form, hồ sơ, đặt lịch, ứng tuyển).
- **confirm:** confirming attendance or a place closes (xác nhận tham dự, xác nhận tham gia, xác nhận chỗ).
- **due:** something must be handed in or paid (nộp bài, báo cáo, slide, project, a bài kiểm tra to finish, học phí, thanh toán).

**Flags.**

- **meeting:** despite its name, this marks any **class activity that may need Join**, not only a meeting: the email sets a time for the student to meet or to take part in a class activity. It has a meeting word (họp, gặp, hẹn, meeting, buổi trao đổi, tư vấn, consultation) or a class-activity word (kiểm tra giữa kỳ / cuối kỳ, thi giữa kỳ / cuối kỳ, thuyết trình, phỏng vấn) that does not come right after "không", "không có" or "kỹ năng" ("Workshop kỹ năng thuyết trình" is a skill topic), and is not "gặp gỡ" (meeting people at an event) or the sign-off "hẹn gặp lại"; or it is an Outlook invitation (§5). An email that announces a class change is not a meeting: its classes already reach the Timetable (Blackboard's "Please join the meeting on time" for an online class). It matters only for Class emails, which it makes event-like when they have a session (§6.2).
- **registered:** the email confirms that the student is registered: "bạn/em đã đăng ký", "bạn/em đã xác nhận", "cảm ơn bạn/em đã đăng ký". A third-person sentence such as "Sinh viên đã đăng ký cần đến trước 07:15" does not count. The app has no other way to know.

---

## 3. The upload format

Still no email text: only days, times, codes from fixed lists and yes/no flags. `MailItem` (Python, and its Java twin) changes as below. Every new field is optional with an empty default, so an older agent's upload stays valid.

### 3.1 Fields

**`MailSession`** gains:

| Field | Type | Rule |
|---|---|---|
| `end_is_approximate` | bool, default false | needs an `end` |
| `ends_next_day` | bool, default false | needs an `end`, which is on the next day and may be earlier than the start. Without it the end must be after the start, as today |
| `check_in` | time, optional | not after `start` |
| `link_opens` | time, optional | not after `start` |
| `mode` | "online" or "in_person", optional | |
| `relative` | code from §3.2, optional | |
| `label` | code from §3.2, optional | |

**`MailPeriod`** (new; `MailItem.periods`, at most 5):

| Field | Type | Rule |
|---|---|---|
| `first_day`, `last_day` | date | the last day is not before the first |
| `mode` | "all_day", "daily_window" or "one_window" | |
| `from_time`, `to_time` | time, optional | none for all_day; both for the others. `to_time` is after `from_time` for a daily_window, and for a one_window on one day |
| `details_later` | bool, default false | |
| `label` | code from §3.2, optional | |

**`MailDeadline`** (new; `MailItem.deadlines`, at most 5): `kind` ("opens", "register", "confirm" or "due"), `day`, `time` (optional) and `mode` ("online" or "in_person", optional).

**`MailItem`** also gains `meeting` (bool, default false), `registered` (bool, default false) and `invitation` ("request" or "cancelled", optional; §5). `register_by` stays: it is the latest `register` deadline's day, for servers older than stage 2.

The upload is refused when it has an unknown code; an end not after the start without `ends_next_day`; `end_is_approximate` or `ends_next_day` without an end; a check-in or link-opens time after the start; a Period whose times don't match its mode or whose last day is before its first; or more than 10 sessions, 5 Periods or 5 deadlines.

### 3.2 Fixed lists

**Labels:**

| The reader finds | Code | The site shows |
|---|---|---|
| vòng 1 … vòng 5 | `round_1` … `round_5` | Round 1 … Round 5 |
| sơ loại, vòng sơ loại | `preliminary` | Preliminary round |
| vòng loại | `qualifying` | Qualifying round |
| bán kết | `semifinal` | Semi-final |
| chung kết, vòng chung kết | `final` | Final |
| khai mạc, lễ khai mạc | `opening` | Opening |
| bế mạc, lễ bế mạc | `closing` | Closing |
| ca 1 … ca 5 | `shift_1` … `shift_5` | Shift 1 … Shift 5 |

**Relative days.** The arrival day is the Vietnam day the email arrived.

| The reader finds | Code | Which day | The site shows |
|---|---|---|---|
| hôm nay, sáng / chiều / tối nay, today, tonight | `today` | the arrival day | today |
| ngày mai, or "mai" after sáng / chiều / tối / trưa or a time; tomorrow | `tomorrow` | the next day | tomorrow |
| ngày kia, ngày mốt | `day_after_tomorrow` | two days later | the day after tomorrow |
| thứ X tuần này, this Thursday | `this_week` | that weekday in the arrival day's week (Monday to Sunday) | this Thursday |
| thứ X tuần sau / tuần tới, next Thursday | `next_week` | that weekday in the following week | next Thursday |
| thứ X or a weekday name on its own | `weekday` | the first such weekday after the arrival day | Thursday |

"Mai" on its own is not a day: it is also a name ("Trần Thị Mai"). A relative day or weekday word is used only when there is no written date in its sentence or any line above it, because school mail writes "Thứ Ba, 29/9" with the date.

---

## 4. The reader (agent)

The reader lives in `agent/sla_agent/mail_times.py` (pure functions). Every word list lives in `agent/sla_agent/mail_words.py`, grouped by role and written as read. The words are matched with the accent-aware matcher of the sorting fixes: written without accents they always count, and written with accents only with their own accents. The reader replaces `sessions_in` and `register_by_in` (Events §3.2, A.1, A.2). The class-change reader `read_announcement` is untouched. `sort_email` calls the reader once per email; when it fails on an email, that email has no sessions, Periods or deadlines, and the log holds no email text, as today.

### 4.1 Step 0: clean the text

1. Unicode NFC; links are ignored, as today.
2. **Replies** (a subject starting with "RE:", "TL:" or "Trả lời:") are cut at their first quoted part: a "From:" or "Từ:" line followed within four lines by "Sent:", "Date:", "To:", "Đã gửi:", "Gửi:", "Ngày:" or "Đến:" ("Từ: 14h00" is a time, not a header); a "-----Original Message-----" line; an "On … wrote:" or "Vào … đã viết:" line; or a line starting with ">". **Forwards** ("FW:", "Fwd:", "CT:", "Chuyển tiếp:") keep everything, because the forwarded part is the content.
3. **Signatures:** everything from a line that is only "--" is cut, and lines starting with "Giờ làm việc", "Working hours" or "Office hours" are dropped.

The cleaned text is also what `dates` (Outlook §5.4) and the flags read. The categories (Outlook §5.2) keep reading the whole email.

### 4.2 Step 1: find and label

The text is split into sentences (lines and sentence ends, as today). A heading line about registration or a deadline, with no number in it and at most 8 words, is read together with the line after it: "THỜI GIAN ĐĂNG KÝ" then "Từ ngày 20/09 đến 22/09/2026.", or "Thời hạn thực hiện:" then the line saying what by when. Each sentence is split into **parts** at commas and semicolons. In each sentence the reader finds these phrases, and which part each is in:

| Phrase | Examples |
|---|---|
| times | 13:00, 13.00, 13h, 13h30, 13g, 8g30, 14 giờ, 14 giờ 30 (phút), 1:00 PM, 2:00 CH, 8:00 SA. Sáng / chiều / tối / trưa before or after the hour in the same sentence ("chiều thứ Sáu, bắt đầu lúc 3 giờ" is 15:00). A time zone after the time (GMT+7, UTC+8, ICT, EST, EDT, PST, PDT, CET, JST, KST, SGT) is converted to Vietnam time |
| time ranges | 13:00–16:00, từ 13:00 đến 16:00, 1h - 3h chiều |
| lengths | kéo dài 2 tiếng, thời lượng 3 tiếng, thời lượng: 1h30, trong 2 giờ, thời gian làm bài là 90 phút, chỉ có 15 phút, khoảng 2 giờ 30 phút. "15 phút, sau đó có 10 phút" adds up. After "khoảng" or "about" alone only tiếng, phút and hours count: "khoảng 2 giờ chiều" is a time. "Trong 15 phút" alone is not a length |
| dates | the formats of Events §3.2, plus two-digit years (05/10/26) |
| date ranges | từ 26/10 đến 30/10, 26/10 – 30/10, từ nay đến 20/09, trong khoảng 02/01 đến 10/01 |
| windows | từ 8h00 ngày 01/10 đến 17h00 ngày 05/10 |
| weekday filters | các ngày thứ Bảy |
| relative days | §3.2 |

Not times, as today: lengths, dotted dates, bare small hours and day edges (Events §3.2). New: a number after a score word (điểm, điểm trung bình, GPA, ĐTB, IELTS, TOEIC, band) is not a time.

Each part's **words** are labelled by role. The full lists live in `mail_words.py`; these words start them. When two phrases overlap, the longer one wins: "mở đến" is closing, not opening, and "đã nộp" is a notice, not due.

| Role | Words | Used by |
|---|---|---|
| registration | đăng ký, register, registration, sign up, form, hồ sơ, đặt lịch, ứng tuyển. Not "đã đăng ký" | D |
| opening | in a sentence with a registration word: mở đăng ký, đăng ký từ, mở từ, form mở, cổng mở, bắt đầu nhận, đăng ký bắt đầu | D3 |
| closing, strong | hạn chót, hạn cuối, hạn đăng ký, hạn nộp, hạn xác nhận, thời hạn, deadline, due (not "due to"). Bare "hạn" (Số lượng có hạn) does not count, as today | D1 |
| closing, soft | đóng, ngừng tiếp nhận, mở đến, đến hết; "trước" or "by" right before a time or date; in a registration sentence also "kết thúc" and "đến" | D1 |
| confirm | xác nhận tham dự, xác nhận tham gia, xác nhận chỗ | D1 |
| due | nộp, nộp bài, báo cáo, slide, project, bài kiểm tra … hoàn thành, học phí, thanh toán | D1 |
| arrival | check-in, điểm danh, có mặt, đến trước, vui lòng đến, tập trung, đăng nhập, mở cửa từ + one time, vào khu vực từ, đăng ký tại chỗ | S4 |
| link | link, đường link, link họp, link tham gia | S5 |
| start, end | bắt đầu, diễn ra, tổ chức, khởi hành; kết thúc | S2 |
| any time | bất kỳ lúc nào, bất kỳ thời điểm nào, bất cứ lúc nào, tùy nhu cầu, có thể đến … trong thời gian / khung giờ, không bắt buộc … ở lại, mở cửa từ X đến Y | P1 |
| any session | bất kỳ buổi nào (the student may pick any of the listed sessions) | stays Sessions |
| details later | thông báo sau, sắp xếp riêng, khung giờ riêng, mỗi lượt, đặt lịch, lịch cụ thể … gửi sau, email tiếp theo | P2 |
| notice | được gửi, gửi lúc, công bố, tiếp nhận, đã đăng ký … vào (lúc / ngày), đã xác nhận … vào, đã nộp, chứng nhận / chứng chỉ … gửi sau | N |
| reschedule | dời, hoãn, chuyển … sang, postponed to | N |
| cancel | hủy, huỷ, cancel, cancelled | N |
| not an event | nghỉ (a day off), chuyển từ phòng … sang (a room change), kỳ thi bắt đầu từ (no end) | N |
| event | diễn ra, tổ chức, vòng, lễ, khai mạc, bế mạc | P6 |
| online, in person | online, trực tuyến, Zoom, Google Meet, Teams, livestream, đăng nhập hệ thống; trực tiếp, offline, in person, tại hội trường, tại phòng, tại cơ sở | M |
| meeting, class activity, registered, labels | §2 and §3.2 | F, labels |

### 4.3 Step 2: decide

The rules run in this order, and each time or date is used once.

1. **Arrival phrases take their times first**, including their "trước" ("có mặt trước 13:45", "đến trước 07:15"), so that "trước" is not read as a deadline.
2. **Deadlines (D):**
   - **D1.** A closing word points at the time or date right after it in its part, or, when there is none after it, at the one before it ("Ngày 15/10 đóng đăng ký"). Its kind comes from the nearest confirm, due or registration word in its sentence ("đăng ký trước ngày 30/10 để được xác nhận suất tham dự" is register). With none of these words, a strong closing word still makes a `due` deadline ("Hạn chót: 30/9", "Thời hạn khảo sát: đến hết ngày 27/08"), and a soft one makes none: "Link tham gia sẽ được gửi trước 09:00" is a link time. A deadline's day is its own date, else the date in its sentence; a time with no date in its sentence is not a deadline.
   - **D2.** A registration window, meaning a registration word with a date range or window ("đăng ký từ 01/10 đến 05/10", "Thời gian đăng ký: 8h00 - 12h00 ngày 05/10", "Đăng ký bắt đầu 18/12 và kết thúc 22/12 lúc 23:59"), gives `opens` at its start and `register` at its end.
   - **D3.** An opening word gives `opens` at its date and time.
   - **D4.** Deadlines with the same kind, day and mode are kept once, with the time when one of them has it; at most 5, soonest first. `register_by` is the latest register deadline's day. Deadlines before the arrival day are kept, as A.2.
3. **Link times (S5)** are taken next, before notices, so "link sẽ được gửi trước 30 phút" is a link time.
4. **Dropped (N):** notices; the old time of a rescheduling (its new time stays: "dời từ 14h00 ngày 05/10 sang 15h00 ngày 06/10" gives 06/10 15:00); cancelled times; not-an-event parts (their dates stay in `dates`).
5. **Periods (P):**
   - **P1.** A range or window with an any-time word in its sentence or the next one ("… trong thời gian trên") is a Period: `daily_window` for a day range with hours, `one_window` for a window or one day's from–to, and `all_day` for a day range without hours. "Mở cửa từ X đến Y" is itself an any-time phrase. In P1 to P5, a day range "with hours" has a time range anywhere in its sentence ("từ ngày 01/10 đến ngày 05/10, từ 7h00 - 11h00 mỗi ngày"), and each of its time ranges gives its own Period or sessions ("8h00 - 11h30 & 13h00 - 16h00 (Từ nay đến 20/09)" gives two Periods).
   - **P2.** A range with a details-later word in its sentence or the next one is a Period in the same way, and so is a time range after "trong khoảng" ("Các buổi tư vấn diễn ra trong khoảng 09:00 đến 16:00 ngày 18/11"). When the email has a details-later word anywhere, its Periods are marked **details later**. A details-later word on a line about the place does not count: "Địa điểm: Thông tin chi tiết sẽ thông báo sau" is about where, not when.
   - **P3.** A day range without hours, outside registration, notice and not-an-event parts, is an `all_day` Period.
   - **P4.** A window longer than 24 hours is a `one_window` Period, or an `all_day` one when it runs from 00:00 to 23:59 (§2). A window of 24 hours or less that crosses midnight is a session that ends the next day ("từ 22:00 ngày 31/12/2026 đến 00:30 ngày 01/01/2027").
   - **P5.** A day range with hours and "mỗi ngày", "các buổi" or a weekday filter, but without an any-time word, gives one session per day (only the named weekdays) when that makes at most 10, and otherwise a `daily_window` Period. Without any of these words it is a `daily_window` Period.
6. **Sessions (S)**, from every time that is left:
   - **S1. Day.** The date of its part; else of its sentence; else the day of the nearest line above that has one, skipping deadline, notice and cut lines (a line whose day came from a relative or weekday word counts, and a line holding a range or window gives its first day); else the same from the nearest line below; else a relative day or weekday word in its sentence, but only when there is no written date in the sentence or any line above it; else the time is dropped. Several dates and times on one line pair as in Events §3.2 rules 2–4.
   - **S2. Start and end:** a time range; "bắt đầu X … kết thúc Y" in one sentence; or a sentence with only an end word and one time ("Hoạt động dự kiến kết thúc vào 11:30"), which ends the nearest session above.
   - **S3. Length:** a length in the session's sentence sets its end; so does a length in a following sentence that has no time of its own ("Họp khoảng 1 tiếng."), for the nearest session above. Lengths add up when joined by "sau đó". The end is approximate with "khoảng", "dự kiến" or "about", and so is an end written after "dự kiến kết thúc". A length after "mỗi lượt" sets no end.
   - **S4. Check-in:** an arrival time joins the earliest session of the same day that starts at or after it, as that session's `check_in`; the session keeps its start. With no later session that day, it becomes a session of its own, as A.1.
   - **S5. Link opens:** a link time joins a session the same way, as its `link_opens`. "Trước 30 phút" or "trước đó 30 phút" means 30 minutes before that session's start. A link time with no session is dropped.
   - **S6.** Times with a zone are converted to Vietnam time, and the day may change.
   - **S7.** As today: sessions on days before the arrival day are dropped, repeats are kept once, and at most 10 sessions are kept, soonest first.
7. **P6.** A day with no hour, whose part has an event word, is a one-day `all_day` Period when the email gives no session on that day ("Ngày 20/10 diễn ra vòng 1").
8. **M, mode.** When the email has online words, sessions and deadlines with online words in their part (else their sentence) are online. When it also has in-person words, those with in-person words are in person. When it has only online words, all of its sessions are online; a deadline takes a mode only from its own words. An email without online words gets no modes.
9. **Labels** come from the label words of the item's part. Periods whose last day is before the arrival day are dropped, and at most 5 Periods are kept, soonest first.
10. **F, flags:** `meeting` and `registered` as in §2, read from the subject and the cleaned text.

### 4.4 Stage 1: today's upload

Until the server knows the new fields (stage 2), the agent sends only what today's format holds:

- **sessions:** the day, the start (the check-in when there is one, as A.1) and the end (none when the session ends the next day)
- **register_by:** the latest register deadline's day

Periods, the other deadlines and the flags are not sent. So stage 1 changes no website behaviour; it only stops fake events and finds more real ones.

---

## 5. Outlook invitations (stage 3)

- The Outlook reader also reads meeting requests and cancellations from the Inbox (Outlook item classes 53 and 54). Replies to invitations are still skipped. Each one becomes an email as today, with its subject, sender, text and categories, plus `invitation` ("request" or "cancelled") and `meeting` set.
- **A request's times come from Outlook, not from its text.** The start and end of its appointment, read in UTC and then turned into Vietnam time, give one session. A recurring meeting gives its next occurrences, at most 10. A meeting longer than one day gives a `one_window` Period. The text is still read for deadlines, mode and check-in.
- **A cancellation has no sessions.**

---

## 6. The website (stage 2)

### 6.1 Tables (one migration)

- **`school_mail`:** add `meeting` BOOLEAN NOT NULL DEFAULT FALSE, `registered` BOOLEAN NOT NULL DEFAULT FALSE and `invitation` VARCHAR(10) NULL. `register_by` stays.
- **`school_mail_sessions`:** add `check_in` TIME NULL, `link_opens` TIME NULL, `end_is_approximate` BOOLEAN NOT NULL DEFAULT FALSE, `ends_next_day` BOOLEAN NOT NULL DEFAULT FALSE, `mode` VARCHAR(10) NULL, `relative_day` VARCHAR(20) NULL and `label` VARCHAR(20) NULL.
- **`school_mail_periods`** (new): `id`, `mail_id` (deleted with its email), `first_day`, `last_day`, `mode` VARCHAR(12), `from_time` TIME NULL, `to_time` TIME NULL, `details_later` BOOLEAN NOT NULL, `label` VARCHAR(20) NULL. Replaced with each sync, like sessions.
- **`school_mail_deadlines`** (new): `id`, `mail_id` (deleted with its email), `kind` VARCHAR(10), `day`, `time` TIME NULL, `mode` VARCHAR(10) NULL. Replaced with each sync.
- **`school_mail_joined`:** add `check_in` TIME NULL, `mode` VARCHAR(10) NULL, `end_is_approximate` BOOLEAN NOT NULL DEFAULT FALSE and `ends_next_day` BOOLEAN NOT NULL DEFAULT FALSE, so a joined copy keeps them.
- **`school_mail_added_periods`** (new): `id`, `user_id`, `mail_key` VARCHAR(64), `first_day`, `last_day`, `mode`, `from_time` NULL, `to_time` NULL, `details_later`, `label` NULL, `title` VARCHAR(500), `created_at`; unique (`user_id`, `mail_key`, `first_day`, `last_day`, `mode`). Not touched by a sync, like joined sessions, so an added Period survives when its email is gone.

### 6.2 Mailbox

- **Event-like** (Events §4.2): the categories include Event or School task, **or Class with `meeting` and at least one session** (a lecturer's email that has a time and a meeting word). The student's Move to… choice wins, as today.
- **Registration state** of a card, in Vietnam time, from all its emails' opens and register deadlines: *not open* before the earliest opening; *open*; *closed* after the last register deadline (at its time, or at the end of its day when it has none). For each kind and mode the latest deadline counts, so a reminder can extend it, as A.3. The tag reads:
  - not open: "Registration opens Thu 08/10", adding ", closes Mon 12/10" when known
  - open: "Register by 17:00 Mon 12/10". With modes, each mode's deadline: "In person 12:00 Sat 03/10 · Online 17:00 Mon 12/10", a passed one struck out
  - closed: "Registration closed", as A.3
- **"Confirm by …" and "Due …"** tags show while their time has not passed.
- **"Registered ✓"** tag. A registered card shows no registration tag and never goes Past because its registration closed.
- **Session line** (Events §4.2) adds "· check-in 13:30", "Online" or "In person", "· link from 09:00", "~" before an approximate end, "Thu 31/12 22:00 – Fri 01/01 00:30" for a session that ends the next day, "· from 'tomorrow'" for a relative day (§3.2), and the label.
- **Period line:** "Period · Mon 02/11 → Thu 05/11 · 09:00–17:00 each day", "Period · Mon 26/10 → Fri 30/10 · all day", "Period · Sat 28/11 09:00 → Sun 29/11 16:00", "Period · Sat 14/11 · 08:00–16:00", plus "· your own time comes later" and the label; then **Added ✓ · Remove** when added.
- **Actions:** Join… as today (event-like cards, or a card with something joined or added). A card with exactly one Period and no sessions also gets **Add** on its row.
- **Next date** (Events §4.4): the soonest of its sessions that haven't ended and its Periods that haven't ended (a running Period's next date is today); else its `dates`, as Outlook §6.3.
- **Past** (Events §4.4 and A.3): every session and Period has ended; or it is an Event card whose registration has closed, with nothing joined or added, that is not registered.
- **Invitations:** a card whose newest email is a cancelled invitation shows "Cancelled". Its found sessions are struck out and can't be joined; joined copies stay until the student leaves them.
- **Gone emails:** "Joined events whose email is gone" (Events §4.6) also lists added Periods whose email is gone, with **Leave**.

### 6.3 Join…, Add and Remove

- **Join…** (Events §4.6) also lists each Period with a tick box ("Add to my Timetable"), and the card's deadlines as text.
- **Save** replaces this email's added Periods that haven't ended with the ticked ones, as it does for sessions. **Leave** also removes this email's added Periods. **Add** adds a card's only Period from its row; **Remove** removes one added Period.
- A joined copy keeps the session's check-in, mode, approximate end and next-day end.
- Refused with a message, as Events §4.6: adding a Period that has already ended; more than 5 added Periods for one email.

### 6.4 Clashes

A session is busy from its check-in (or its start) to its end; without an end, until one hour after its start, as today. An approximate end counts as given, and an end on the next day runs past midnight. **Periods are never busy:** added Periods clash with nothing, and nothing clashes with them. Events §4.5 is otherwise unchanged.

### 6.5 Timetable, Overview and the calendar feed

- **Joined sessions** (Events §4.7) start at their check-in, and the title adds "check-in 13:30". One that ends the next day runs past midnight.
- **Added Periods** are all-day items from the first day to the last (`/school/api/calendar`, class `event-period`: light green with a dashed edge). The title is the label and the card's title, with the hours ("09:00–17:00 each day", "until 16:00 Sun"). They never show ⚠, and they are hidden while their card is Done. The legend gains "Period".
- **Overview's Today and Tomorrow** list the added Periods running that day.

### 6.6 Addresses

`GET` and `POST /school/mailbox/{key}/join` and `POST …/leave` as today; new `POST /school/mailbox/{key}/add-period` and `POST /school/mailbox/{key}/remove-period`. All need login and the CSRF token, and a key that isn't one of the user's cards gives 404 (`remove-period`, like `leave`, also takes the key of an email that is gone).

---

## 7. Security and privacy

1. **Still no email text leaves the laptop:** only days, times, codes from fixed lists and yes/no flags. Unknown codes are refused by the upload format on both sides.
2. Every query is filtered by the logged-in user, every POST needs the CSRF token, and another user's card gives 404.
3. Codes are shown through fixed text; titles and places are escaped by Thymeleaf, as today.
4. Reader failures log no email text, as today.
5. A test checks that no part of a test mail's body appears in its upload beyond what its subject already shows.

---

## 8. Testing

1. **The test set** is `agent/tests/fixtures/mail-times-cases.json`, made from the [cases document](2026-10-07-mail-event-kinds-cases.md): the student's 100 mails (1–50 arrive Wed 07/10/2026, with answers from the student's key; 51–100 arrive Mon 02/11/2026, with answers drafted and then checked by the student) and the 27 short cases from the design discussion. The 57 real samples (`mail-samples.json`) keep their checked results and gain the reader's full results; each sample whose results change is checked by the student. In stage 1, three change what they upload: samples 20 and 23 (civic education: registration closes 22/09, from their "THỜI GIAN ĐĂNG KÝ" heading) and 24 (beFood: its ordering hours become two daily Periods instead of two events on 20/09). The old session tests (`test_sessions.py`) keep their expectations, except where this design changes them on purpose: a length now gives the end ("kéo dài 2h"), and "8 giờ sáng" is read.
2. **A scorecard,** `agent/tools/mail_times_score.py`, prints how many cases are right for each part (sessions, check-in, end, deadlines, Periods, flags) and lists the wrong ones.
3. **A stage is done** when every case passes or is on the "known misses" list in the cases document, which the student agrees to.
4. **Agent:** step 0 (replies cut, forwards kept, signatures), step 1 (each time and date form, scores, time zones), step 2 (each rule of §4.3 on its own), the word lists (no word in two roles that contradict each other), the stage 1 upload (§4.4), privacy (§7.5), and a failure that gives no times and logs no text.
5. **Upload format:** a shared sample with every new field, read on both sides, and each refusal of §3.1.
6. **Website (stage 2):** the tags (opens; register; per mode, with passed ones struck out; closed at a time; confirm; due; registered); Past (A.3 with added and registered); Class with `meeting` is event-like; session and Period lines; Join with Periods; Add, Remove and Leave; Done hides added Periods on the Timetable; check-in blocks; clashes from check-in; Periods are never busy; cancelled invitations; the gone list; Overview; the calendar feed; another user's key gives 404; CSRF; on MySQL like the other tables.
7. **Invitations (stage 3):** fake Outlook items for a request, a recurring request, a request longer than a day, a cancellation, and a reply (skipped).

---

## 9. Build order

**Stage 1, the reader (agent only).** It starts from the sorting fixes (branch `mail-rules-fixes`, 082ed22) and ships with them.

1. `mail_words.py` with the word lists, matched by the accent-aware matcher.
2. Steps 0, 1 and 2 in `mail_times.py`, test by test.
3. The test set and the scorecard; the real samples' changed results checked by the student.
4. `sort_email` uses the reader, mapped to today's upload (§4.4).
5. An agent release, then a real-sync check on the student's laptop.

**Stage 2, the format and the website.**

1. The upload format, Python and Java.
2. The migration, and saving the new parts.
3. Mailbox (event-like, tags, lines, Past, Add, Remove) and Join….
4. Clashes, Timetable, Overview and the calendar feed.
5. The agent sends everything it finds.
6. The server update (the student runs `update.sh`), then the agent release, then a real-sync check.

**Stage 3, Outlook invitations (agent only):** the reader picks up requests and cancellations; an agent release; a real-sync check with a test invitation.

---

## 10. Later, in their own specs

- **Class changes** (after stage 1): room changes ("Buổi học ngày 04/12 lúc 13:00 sẽ chuyển từ phòng A1.201 sang A2.205") as a new class-change kind; school holidays from IU offices ("Trường nghỉ từ 24/12 đến 26/12") marking those days' classes "No class"; lecturer tests ("Bài kiểm tra giữa kỳ sẽ bắt đầu lúc 08:00 ngày 12/11/2026") as exam items. The Python reader, its Java twin and Blackboard announcements change together. Until then these mails give nothing wrong: mails 80 and 92 give nothing, and mail 54 is a class activity the student can join.
- **One-click fixes and learning** (part 2, after stage 2): "Not an event", "Make this a Period" or "a session", "Wrong time", "This is the deadline" or "not a deadline". Fixes are kept across syncs. With the student's agreement, the laptop saves the email, anonymized, with the corrected answer as a new test case.

---

## 11. Changes to earlier specs

- **Events §3.2** (finding sessions) is replaced by §4 here; its pairing rules stay and are extended.
- **A.1:** in stage 1 the check-in still moves the session's start in the upload; from stage 2 it is sent separately, and blocks and clashes still start there.
- **A.2:** `register_by` stays for older servers; from stage 2 the site uses the deadlines.
- **A.3:** kept, with "nothing added" and "not registered" added.
- **Events §4.2:** event-like also includes Class with `meeting`; the row gains the tags and lines of §6.2.
- **Events §4.4:** the next date and Past also count Periods.
- **Events §4.5:** busy from the check-in; Periods are never busy.
- **Outlook §5.4:** `dates` are read from the cleaned text.

---

## 12. Risks

- **Rules fitted to tidy test mails.** The 100 test mails are clean, one idea per sentence. Real mail counts for more: keep adding anonymized real samples, and list a known miss rather than bend the rules for one odd mail.
- **A wrong Period hides a real clash,** because Periods are never busy. The student still sees it on the row and can add a session by hand.
- **A misread deadline closes a card too early** and moves it to Past. Past is one click away, and Join… stays.
- **A relative day read wrong,** such as a "thứ Ba" that meant last week. It is shown as "from 'Tuesday'" so the student can check it.
- **A reply cut too much or too little.** Only reply subjects are cut; forwards are untouched.
- **An older agent with a newer server, or the reverse.** Every new field is optional, and the server is updated first.
