# Mail event kinds: test cases

**Date:** 2026-10-07  
**For:** [the design](2026-10-07-mail-event-kinds-design.md), §8. These cases become `agent/tests/fixtures/mail-times-cases.json`.

Each case is a mail and what the reader should give for it. Days carry their weekday and are in Vietnam time. “from 14:00” is a session without an end, and “~” marks an approximate end. A case that should give nothing says so.

| Group | Mails | Arrive | Answers |
|---|---|---|---|
| A | 01–50 | Wed 07/10/2026 | the student's answer key (2026-10-07) |
| B | 51–100 | Mon 02/11/2026 | drafted by Claude, checked by the student (2026-10-07) |
| C | C01–C27 | Mon 28/09/2026 | short cases from the design discussion, checked by the student (2026-10-07) |

The arrival day is what “ngày mai”, “tuần này” and a weekday on its own count from.

**Known misses** (cases the student agrees the reader may get wrong): none yet.

**How group A differs from the student's key.** The answers keep the key's days and times. They add what the design's rules give beyond the key: online modes (02, 15, 30), labels (06, 34), the meeting and registered flags, and an approximate end where the mail says “khoảng” or “dự kiến” (09, 47, 49). The key's link_available is a link-opens time, its confirmation_deadline a confirm deadline, its submission deadline a due deadline, and its registered_at, registered_date and completed the registered flag. Notice times (25, 27, 33, 35, 36, 39) are not kept.

## Group A: mails 01–50 (arrive Wed 07/10/2026; the student's key)

### Mail 01 · Hội thảo Kỹ năng học tập hiệu quả

```text
Kính gửi sinh viên,
Phòng Công tác Sinh viên tổ chức hội thảo “Kỹ năng học tập hiệu quả” vào 14:00 ngày 15/10/2026 tại phòng A2.301.
Sinh viên vui lòng có mặt trước 13:45 để ổn định chỗ ngồi.
Việc đăng ký tham dự mở từ 08/10 đến 12/10.
```

- **Session:** Thu 15/10 from 14:00 · check-in 13:45
- **Deadlines:** registration opens Thu 08/10 · register by Mon 12/10

### Mail 02 · Workshop AI dành cho sinh viên

```text
Workshop sẽ được tổ chức vào 09:30 ngày 18/10/2026 trên Microsoft Teams.
Link tham gia sẽ được gửi trước 09:00 cùng ngày.
Hạn đăng ký: 17/10/2026 lúc 23:59.
```

- **Session:** Sun 18/10 from 09:30 · link opens 09:00 · online
- **Deadlines:** register by 23:59 Sat 17/10

### Mail 03 · Mời tham dự buổi chia sẻ nghề nghiệp

```text
Buổi chia sẻ diễn ra từ 08:30 đến 11:30 ngày 20/10/2026 tại A1.206.
Vui lòng đến trước 08:15.
Đăng ký trước 19/10.
```

- **Session:** Tue 20/10 08:30–11:30 · check-in 08:15
- **Deadlines:** register by Mon 19/10

### Mail 04 · Sinh hoạt câu lạc bộ tháng 10

```text
CLB sẽ gặp mặt vào 18h30 thứ Sáu, ngày 23/10 tại phòng B1.102.
Thành viên cần đăng ký trước 20/10.
```

- **Session:** Fri 23/10 from 18:30
- **Deadlines:** register by Tue 20/10
- **Flags:** meeting

### Mail 05 · Orientation cho sinh viên mới

```text
Chương trình bắt đầu lúc 8 giờ sáng ngày 24/10/2026.
Sinh viên được yêu cầu có mặt lúc 7 giờ 30 để điểm danh.
Form đăng ký đóng vào 22/10.
```

- **Session:** Sat 24/10 from 08:00 · check-in 07:30
- **Deadlines:** register by Thu 22/10

### Mail 06 · Đăng ký tham gia cuộc thi học thuật

```text
Thời gian đăng ký: 01/10 đến 10/10.
Vòng sơ loại diễn ra vào 15/10 lúc 13h30.
Thí sinh cần có mặt lúc 13h00.
```

- **Session:** Thu 15/10 from 13:30 · check-in 13:00 · label Preliminary round
- **Deadlines:** registration opens Thu 01/10 · register by Sat 10/10

### Mail 07 · Hội thảo Career Talk

```text
Mở đăng ký từ 05/10.
Hạn đăng ký là 12/10 lúc 17:00.
Hội thảo được tổ chức 19/10 từ 14:00 đến 16:00.
Vui lòng check-in từ 13:30.
```

- **Session:** Mon 19/10 14:00–16:00 · check-in 13:30
- **Deadlines:** registration opens Mon 05/10 · register by 17:00 Mon 12/10

### Mail 08 · Tham dự buổi hướng dẫn đăng ký môn học

```text
Sinh viên có thể đăng ký tham dự từ 09:00 ngày 07/10 đến 23:59 ngày 09/10.
Buổi hướng dẫn chính thức diễn ra vào 10/10 lúc 09:00.
```

- **Session:** Sat 10/10 from 09:00
- **Deadlines:** registration opens 09:00 Wed 07/10 · register by 23:59 Fri 09/10

### Mail 09 · Cuộc họp nhóm dự án

```text
Vui lòng đăng ký trước 18:00 ngày 11/10.
Cuộc họp bắt đầu lúc 19:00 ngày 12/10 và dự kiến kết thúc lúc 20:30.
```

- **Session:** Mon 12/10 19:00–~20:30
- **Deadlines:** register by 18:00 Sun 11/10
- **Flags:** meeting
- *Note:* the end is approximate because it comes after “dự kiến kết thúc” (rule S3); the key gives 20:30 without saying so.

### Mail 10 · Tham dự lễ trao giải

```text
Ban tổ chức yêu cầu sinh viên xác nhận tham dự trước 15/10.
Lễ trao giải diễn ra lúc 09:45 ngày 17/10/2026.
Check-in từ 09:00.
```

- **Session:** Sat 17/10 from 09:45 · check-in 09:00
- **Deadlines:** confirm by Thu 15/10

### Mail 11 · Workshop cuối tuần

```text
Workshop diễn ra lúc 2h chiều Chủ nhật 18/10.
Địa điểm: A2.307.
```

- **Session:** Sun 18/10 from 14:00

### Mail 12 · Buổi tư vấn học tập

```text
Hẹn gặp sinh viên vào 10h30 sáng ngày 21 tháng 10.
```

- **Session:** Wed 21/10 from 10:30
- **Flags:** meeting

### Mail 13 · Training kỹ năng mềm

```text
Chương trình bắt đầu vào 8h15 ngày 22/10 và kết thúc lúc 11h45.
```

- **Session:** Thu 22/10 08:15–11:45

### Mail 14 · Talkshow

```text
Talkshow bắt đầu lúc 14 giờ 30 phút, thứ Tư ngày 28/10/2026.
```

- **Session:** Wed 28/10 from 14:30

### Mail 15 · Họp trực tuyến

```text
Chúng ta sẽ họp vào 20:00 tối nay trên Teams.
```

- **Session:** Wed 07/10 from 20:00 · online · day from a relative word (today)
- **Flags:** meeting

### Mail 16 · Nhắc hạn đăng ký học bổng

```text
Sinh viên vui lòng hoàn thành hồ sơ trước 17:00 ngày 13/10/2026.
Sau thời gian trên, hệ thống sẽ ngừng tiếp nhận hồ sơ.
```

- **Deadlines:** register by 17:00 Tue 13/10

### Mail 17 · Hạn đăng ký workshop

```text
Form đăng ký sẽ đóng vào 23:59 ngày 16/10.
```

- **Deadlines:** register by 23:59 Fri 16/10

### Mail 18 · Nhắc nộp bài

```text
Sinh viên phải nộp bài trước 23:59 ngày 25/10/2026.
```

- **Deadlines:** due 23:59 Sun 25/10

### Mail 19 · Đăng ký tham gia chương trình

```text
Vui lòng đăng ký trước ngày 30/10 để được xác nhận suất tham dự.
```

- **Deadlines:** register by Fri 30/10

### Mail 20 · Thông báo thời hạn xác nhận

```text
Hạn cuối để xác nhận tham dự là 12:00 ngày 14/10.
```

- **Deadlines:** confirm by 12:00 Wed 14/10

### Mail 21 · Tuần lễ định hướng sinh viên

```text
Tuần lễ diễn ra từ 26/10 đến 30/10/2026.
```

- **Period:** Mon 26/10 → Fri 30/10 · all day

### Mail 22 · Khóa học kỹ năng

```text
Khóa học kéo dài từ 01/11 đến 15/11.
```

- **Period:** Sun 01/11 → Sun 15/11 · all day

### Mail 23 · Triển lãm sinh viên

```text
Triển lãm mở cửa từ 09:00 đến 17:00 trong các ngày 02/11 đến 05/11.
```

- **Period:** Mon 02/11 → Thu 05/11 · 09:00–17:00 each day
- *Note:* the key's “02/11 09:00 to 05/11 17:00, any time” is open 09:00–17:00 on each of those days.

### Mail 24 · Chương trình tình nguyện

```text
Chương trình bắt đầu 07:30 ngày 08/11 và kết thúc 16:30 cùng ngày.
```

- **Session:** Sun 08/11 07:30–16:30

### Mail 25 · Thông báo hội thảo

```text
Email này được gửi lúc 09:15 ngày 07/10/2026.
Hội thảo sẽ diễn ra vào 14:00 ngày 20/10/2026.
Hạn đăng ký là 18/10.
```

- **Session:** Tue 20/10 from 14:00
- **Deadlines:** register by Sun 18/10
- *Note:* “Email này được gửi lúc 09:15” is a notice.

### Mail 26 · Nhắc lại lịch phỏng vấn

```text
Bạn đã đăng ký phỏng vấn vào 10/10.
Buổi phỏng vấn chính thức diễn ra lúc 09:00 ngày 12/10.
```

- **Session:** Mon 12/10 from 09:00
- **Flags:** meeting, registered

### Mail 27 · Xác nhận đăng ký

```text
Bạn đã đăng ký vào lúc 15:32 ngày 06/10.
Thời gian tham gia chương trình: 08:00 ngày 15/10.
```

- **Session:** Thu 15/10 from 08:00
- **Flags:** registered
- *Note:* the registration time 15:32 06/10 is a notice and is not kept.

### Mail 28 · Deadline không ảnh hưởng đến lịch tham dự

```text
Deadline đăng ký là 20/10.
Tuy nhiên, sự kiện sẽ diễn ra vào 25/10 lúc 15:00.
```

- **Session:** Sun 25/10 from 15:00
- **Deadlines:** register by Tue 20/10

### Mail 29 · Thời gian đăng ký và thời gian tham gia

```text
Bạn có thể đăng ký từ 01/10 đến 05/10.
Sau khi đăng ký, vui lòng tham gia buổi workshop vào 10/10 lúc 09:30.
```

- **Session:** Sat 10/10 from 09:30
- **Deadlines:** registration opens Thu 01/10 · register by Mon 05/10

### Mail 30 · Hướng dẫn trước sự kiện

```text
Vui lòng hoàn thành đăng ký trước 12/10.
Link Teams sẽ mở lúc 13:45 ngày 15/10.
Chương trình chính thức bắt đầu lúc 14:00 ngày 15/10.
```

- **Session:** Thu 15/10 from 14:00 · link opens 13:45 · online
- **Deadlines:** register by Mon 12/10

### Mail 31 · Workshop nghiên cứu khoa học

```text
Workshop diễn ra trong 2 giờ, bắt đầu lúc 08:30 ngày 16/10.
```

- **Session:** Fri 16/10 08:30–10:30

### Mail 32 · Hướng dẫn check-in

```text
Vui lòng đến trước 08:00 ngày 18/10.
Chương trình bắt đầu lúc 08:30.
```

- **Session:** Sun 18/10 from 08:30 · check-in 08:00

### Mail 33 · Sau khi kết thúc chương trình

```text
Chứng nhận sẽ được gửi sau ngày 25/10.
Buổi lễ diễn ra vào 25/10 lúc 09:00.
```

- **Session:** Sun 25/10 from 09:00

### Mail 34 · Lịch chương trình tháng 10

```text
Ngày 10/10 mở đăng ký.
Ngày 15/10 đóng đăng ký.
Ngày 20/10 diễn ra vòng 1.
Ngày 25/10 diễn ra vòng 2.
```

- **Periods:**
  - Tue 20/10 · all day · label Round 1
  - Sun 25/10 · all day · label Round 2
- **Deadlines:** registration opens Sat 10/10 · register by Thu 15/10

### Mail 35 · Lịch phỏng vấn tuyển thành viên

```text
Đăng ký từ 01/10.
Hạn đăng ký 08/10.
Danh sách được công bố 10/10.
Phỏng vấn diễn ra 12/10 từ 14:00 đến 17:00.
```

- **Session:** Mon 12/10 14:00–17:00
- **Deadlines:** registration opens Thu 01/10 · register by Thu 08/10
- **Flags:** meeting

### Mail 36 · Hồ sơ đã được tiếp nhận

```text
Hồ sơ của bạn đã được tiếp nhận thành công.
Thời gian tiếp nhận: 06/10/2026 lúc 10:35.
```

- **Nothing.**

### Mail 37 · Thông báo hệ thống

```text
Hệ thống sẽ bảo trì trong 2 giờ vào ban đêm.
```

- **Nothing.**

### Mail 38 · Cảm ơn bạn đã đăng ký

```text
Cảm ơn bạn đã đăng ký tham gia chương trình.
Thông tin chi tiết về thời gian tham dự sẽ được gửi sau.
```

- **Flags:** registered

### Mail 39 · Kết quả đăng ký

```text
Bạn đã đăng ký thành công vào ngày 05/10/2026.
```

- **Flags:** registered

### Mail 40 · Thông tin chung

```text
Sinh viên nên hoàn thành thủ tục càng sớm càng tốt.
Chương trình dự kiến diễn ra vào cuối tháng.
```

- **Nothing.**

### Mail 41 · Hội thảo ngày 20/10

```text
Hạn đăng ký: 18/10.
Vui lòng có mặt lúc 13:30.
Hội thảo chính thức bắt đầu lúc 14:00 ngày 20/10 và kết thúc lúc 16:00.
```

- **Session:** Tue 20/10 14:00–16:00 · check-in 13:30
- **Deadlines:** register by Sun 18/10

### Mail 42 · Đăng ký trước, tham gia sau

```text
Form mở ngày 01/10.
Form đóng ngày 10/10.
Những sinh viên đăng ký thành công sẽ tham gia chương trình vào 15/10 lúc 08:00.
```

- **Session:** Thu 15/10 from 08:00
- **Deadlines:** registration opens Thu 01/10 · register by Sat 10/10

### Mail 43 · Chương trình bắt đầu lúc 9h

```text
Check-in từ 08:30.
Đăng ký trước 05/10.
Chương trình bắt đầu lúc 09:00 ngày 07/10.
```

- **Session:** Wed 07/10 from 09:00 · check-in 08:30
- **Deadlines:** register by Mon 05/10

### Mail 44 · Hạn nộp và buổi thuyết trình

```text
Hạn nộp slide: 20/10 lúc 23:59.
Buổi thuyết trình: 22/10 lúc 13:30.
Sinh viên cần có mặt trước 13:15.
```

- **Session:** Thu 22/10 from 13:30 · check-in 13:15
- **Deadlines:** due 23:59 Tue 20/10
- **Flags:** meeting

### Mail 45 · Đăng ký tham dự lễ tốt nghiệp

```text
Sinh viên đăng ký từ 01/11 đến 05/11.
Lễ tốt nghiệp được tổ chức vào 15/11/2026 lúc 08:00.
Sinh viên phải có mặt lúc 07:15.
```

- **Session:** Sun 15/11 from 08:00 · check-in 07:15
- **Deadlines:** registration opens Sun 01/11 · register by Thu 05/11

### Mail 46 · Mai gặp nhau nhé

```text
Nhớ nhé, 2 giờ chiều mai mình gặp ở A1.205 để trao đổi về project. Đừng đến trễ.
```

- **Session:** Thu 08/10 from 14:00 · day from a relative word (tomorrow)
- **Flags:** meeting

### Mail 47 · Họp nhóm tuần này

```text
Mình chốt lịch 10h sáng thứ Năm tuần này nhé. Họp khoảng 1 tiếng.
```

- **Session:** Thu 08/10 10:00–~11:00 · day from a relative word (this week)
- **Flags:** meeting

### Mail 48 · Nhắc lịch

```text
Nhắc bạn là 8h sáng ngày kia có buổi họp với nhóm.
```

- **Session:** Fri 09/10 from 08:00 · day from a relative word (the day after tomorrow)
- **Flags:** meeting

### Mail 49 · Lịch tuần sau

```text
Workshop tuần sau tổ chức vào thứ Ba lúc 14h, kéo dài khoảng 90 phút.
```

- **Session:** Tue 13/10 14:00–~15:30 · day from a relative word (next week)

### Mail 50 · Đừng quên buổi meeting

```text
Meeting vào chiều thứ Sáu, bắt đầu lúc 3 giờ.
Link sẽ được gửi trước đó 30 phút.
```

- **Session:** Fri 09/10 from 15:00 · link opens 14:30 · day from a relative word (a weekday alone)
- **Flags:** meeting

## Group B: mails 51–100 (arrive Mon 02/11/2026; drafted by Claude, checked by the student)

### Mail 51 · Workshop Git và GitHub

```text
Workshop Git và GitHub sẽ được tổ chức vào 09:00 ngày 08/11/2026 tại phòng A2.302.
Sinh viên vui lòng đăng ký trước 23:59 ngày 05/11.
Có mặt tại phòng trước 08:45.
```

- **Session:** Sun 08/11 from 09:00 · check-in 08:45
- **Deadlines:** register by 23:59 Thu 05/11

### Mail 52 · Đăng ký chương trình trao đổi sinh viên

```text
Cổng đăng ký mở từ 01/11/2026 và đóng vào 15/11/2026 lúc 17:00.
Danh sách sinh viên được chọn sẽ được công bố vào 20/11.
Buổi hướng dẫn dành cho sinh viên được chọn diễn ra vào 22/11 lúc 14:00.
```

- **Session:** Sun 22/11 from 14:00
- **Deadlines:** registration opens Sun 01/11 · register by 17:00 Sun 15/11

### Mail 53 · Seminar về trí tuệ nhân tạo

```text
Seminar diễn ra vào thứ Hai, ngày 09/11, từ 13:30 đến 15:30.
Người tham dự có thể check-in từ 13:00.
```

- **Session:** Mon 09/11 13:30–15:30 · check-in 13:00

### Mail 54 · Nhắc lịch kiểm tra giữa kỳ

```text
Bài kiểm tra giữa kỳ sẽ bắt đầu lúc 08:00 ngày 12/11/2026.
Sinh viên phải có mặt tại phòng thi trước 07:45.
Thời gian làm bài là 90 phút.
```

- **Session:** Thu 12/11 08:00–09:30 · check-in 07:45
- **Flags:** meeting

### Mail 55 · Hạn xác nhận tham gia

```text
Vui lòng xác nhận tham dự trước 18:00 ngày 07/11.
Chương trình sẽ được tổ chức vào 10/11 lúc 15:00.
```

- **Session:** Tue 10/11 from 15:00
- **Deadlines:** confirm by 18:00 Sat 07/11

### Mail 56 · Ngày hội việc làm

```text
Ngày hội việc làm mở cửa từ 08:00 đến 16:00 ngày 14/11/2026.
Sinh viên có thể đến bất kỳ thời điểm nào trong thời gian trên.
```

- **Period:** Sat 14/11 · 08:00–16:00

### Mail 57 · Đăng ký phỏng vấn học bổng

```text
Sinh viên đăng ký lịch phỏng vấn từ 05/11 đến 09/11.
Hệ thống sẽ đóng đăng ký lúc 23:59 ngày 09/11.
Lịch phỏng vấn của bạn là 14:30 ngày 11/11.
```

- **Session:** Wed 11/11 from 14:30
- **Deadlines:** registration opens Thu 05/11 · register by 23:59 Mon 09/11
- **Flags:** meeting

### Mail 58 · Buổi họp lớp

```text
Lớp sẽ họp vào 18h thứ Tư tuần này.
Cuộc họp dự kiến kéo dài khoảng 90 phút.
```

- **Session:** Wed 04/11 18:00–~19:30 · day from a relative word (this week)
- **Flags:** meeting

### Mail 59 · Chương trình hiến máu

```text
Chương trình diễn ra vào 07:30 ngày 16/11.
Sinh viên đã đăng ký cần đến trước 07:15 để làm thủ tục.
Form đăng ký đóng vào 12/11.
```

- **Session:** Mon 16/11 from 07:30 · check-in 07:15
- **Deadlines:** register by Thu 12/11
- *Note:* “Sinh viên đã đăng ký” is third person, so not registered; its “trước 07:15” is an arrival, not a deadline.

### Mail 60 · Triển lãm đồ án sinh viên

```text
Triển lãm mở cửa trong ba ngày, từ 10/11 đến 12/11, mỗi ngày từ 09:00 đến 17:00.
Bạn có thể tham quan vào bất kỳ thời điểm nào trong khung giờ mở cửa.
```

- **Period:** Tue 10/11 → Thu 12/11 · 09:00–17:00 each day

### Mail 61 · Hướng dẫn sử dụng phòng lab

```text
Buổi hướng dẫn bắt đầu lúc 14h ngày 17/11.
Vui lòng hoàn thành đăng ký trước 16/11.
```

- **Session:** Tue 17/11 from 14:00
- **Deadlines:** register by Mon 16/11

### Mail 62 · Hạn nộp báo cáo nhóm

```text
Báo cáo nhóm phải được nộp trước 23:59 ngày 19/11.
Buổi thuyết trình sẽ diễn ra vào 21/11 từ 08:30 đến 11:00.
```

- **Session:** Sat 21/11 08:30–11:00
- **Deadlines:** due 23:59 Thu 19/11
- **Flags:** meeting

### Mail 63 · Buổi tư vấn CV

```text
Các buổi tư vấn diễn ra trong khoảng 09:00 đến 16:00 ngày 18/11.
Sinh viên cần đặt lịch trước 15/11.
Mỗi lượt tư vấn kéo dài khoảng 30 phút.
```

- **Period:** Wed 18/11 · 09:00–16:00 · details later
- **Deadlines:** register by Sun 15/11
- **Flags:** meeting
- *Note:* 09:00–16:00 is the booking window, not a clash. Each student books one 30-minute slot inside it; that slot becomes a session only once the student has booked it (added by hand on the Join page).

### Mail 64 · Thông báo tuyển cộng tác viên

```text
Hạn đăng ký ứng tuyển là 10/11/2026.
Ứng viên được chọn sẽ tham gia buổi phỏng vấn vào 13/11 lúc 09:00.
```

- **Session:** Fri 13/11 from 09:00
- **Deadlines:** register by Tue 10/11
- **Flags:** meeting

### Mail 65 · Họp dự án

```text
Nhóm chúng ta họp vào 15:00 chiều mai.
Nhớ đọc tài liệu trước cuộc họp.
```

- **Session:** Tue 03/11 from 15:00 · day from a relative word (tomorrow)
- **Flags:** meeting

### Mail 66 · Chương trình định hướng nghề nghiệp

```text
Chương trình bắt đầu lúc 08:30 ngày 23/11 và kết thúc lúc 12:00.
Sinh viên đăng ký trước 20/11.
```

- **Session:** Mon 23/11 08:30–12:00
- **Deadlines:** register by Fri 20/11

### Mail 67 · Đăng ký tham quan doanh nghiệp

```text
Form đăng ký mở đến 16:00 ngày 21/11.
Chuyến tham quan diễn ra vào 25/11, tập trung tại trường lúc 07:00.
Xe khởi hành lúc 07:30.
```

- **Session:** Wed 25/11 from 07:30 · check-in 07:00
- **Deadlines:** register by 16:00 Sat 21/11
- *Note:* the bus leaves at 07:30 (the start) and students gather at 07:00 (the check-in). “Form đăng ký mở đến” closes registration.

### Mail 68 · Lịch thi cuối kỳ

```text
Kỳ thi bắt đầu từ 01/12/2026.
Lịch thi cụ thể của từng môn sẽ được công bố vào 20/11.
```

- **Flags:** meeting
- *Note:* exam season with no time: only the flag (“thi cuối kỳ”). The meeting flag marks a class activity that may need Join, not only a meeting (design §2).

### Mail 69 · Workshop kỹ năng thuyết trình

```text
Workshop diễn ra vào 24/11 lúc 13:00.
Thời lượng dự kiến là 3 tiếng.
```

- **Session:** Tue 24/11 13:00–~16:00

### Mail 70 · Thông báo đăng ký hoạt động ngoại khóa

```text
Sinh viên có thể đăng ký từ 08:00 ngày 20/11 đến 23:59 ngày 22/11.
Hoạt động diễn ra vào 27/11 lúc 08:00.
```

- **Session:** Fri 27/11 from 08:00
- **Deadlines:** registration opens 08:00 Fri 20/11 · register by 23:59 Sun 22/11

### Mail 71 · Lịch gặp cố vấn học tập

```text
Bạn có lịch gặp cố vấn vào 10h sáng ngày 26/11.
Vui lòng đến đúng giờ vì mỗi sinh viên chỉ có 15 phút.
```

- **Session:** Thu 26/11 10:00–10:15
- **Flags:** meeting

### Mail 72 · Chương trình giao lưu quốc tế

```text
Chương trình diễn ra từ 09:00 ngày 28/11 đến 16:00 ngày 29/11.
Sinh viên có thể tham gia một hoặc nhiều phiên tùy nhu cầu.
```

- **Period:** Sat 28/11 09:00 → Sun 29/11 16:00

### Mail 73 · Đăng ký cuộc thi lập trình

```text
Hạn đăng ký là 30/11 lúc 23:59.
Vòng loại online bắt đầu lúc 09:00 ngày 03/12 và kết thúc lúc 12:00.
```

- **Session:** Thu 03/12 09:00–12:00 · online · label Qualifying round
- **Deadlines:** register by 23:59 Mon 30/11

### Mail 74 · Buổi hướng dẫn đồ án

```text
Buổi hướng dẫn sẽ diễn ra sáng thứ Sáu tuần sau lúc 09:30.
Thời lượng khoảng 2 giờ.
```

- **Session:** Fri 13/11 09:30–~11:30 · day from a relative word (next week)

### Mail 75 · Nhắc hạn đóng phí

```text
Sinh viên hoàn thành học phí trước 17:00 ngày 05/12.
Đây là email nhắc hạn thanh toán, không có buổi gặp trực tiếp.
```

- **Deadlines:** due 17:00 Sat 05/12
- *Note:* “không có buổi gặp trực tiếp” does not set the meeting flag.

### Mail 76 · Xác nhận tham gia hội thảo

```text
Bạn đã xác nhận tham gia hội thảo vào ngày 30/11.
Hội thảo sẽ bắt đầu lúc 14:00 ngày 02/12.
```

- **Session:** Wed 02/12 from 14:00
- **Flags:** registered

### Mail 77 · Lịch hoạt động câu lạc bộ

```text
Tháng này CLB có các buổi:
05/12 lúc 18:00
12/12 lúc 18:00
19/12 lúc 18:00
Thành viên có thể tham gia bất kỳ buổi nào.
```

- **Sessions:**
  - Sat 05/12 from 18:00
  - Sat 12/12 from 18:00
  - Sat 19/12 from 18:00
- *Note:* “bất kỳ buổi nào” means pick any of the listed sessions, so they stay sessions.

### Mail 78 · Ngày hội thể thao

```text
Ngày hội thể thao diễn ra từ 07:00 đến 17:00 ngày 06/12.
Các trận đấu của bạn được sắp xếp riêng và sẽ được thông báo sau.
```

- **Period:** Sun 06/12 · 07:00–17:00 · details later

### Mail 79 · Đăng ký workshop

```text
Đăng ký trước 01/12.
Workshop bắt đầu 02/12 lúc 09:00 và kéo dài khoảng 2 giờ 30 phút.
```

- **Session:** Wed 02/12 09:00–~11:30
- **Deadlines:** register by Tue 01/12

### Mail 80 · Thông báo phòng học thay đổi

```text
Buổi học ngày 04/12 lúc 13:00 sẽ chuyển từ phòng A1.201 sang A2.205.
```

- **Nothing.**
- *Note:* a room change for a class: left to the class-change spec (design §10).

### Mail 81 · Lịch phỏng vấn tuyển thành viên

```text
Bạn được mời phỏng vấn vào 09:15 ngày 08/12.
Vui lòng đăng nhập hệ thống trước 09:00.
```

- **Session:** Tue 08/12 from 09:15 · check-in 09:00 · online
- **Flags:** meeting

### Mail 82 · Hạn đăng ký học phần

```text
Sinh viên có thể đăng ký học phần đến 16:00 ngày 10/12.
Sau thời điểm này, hệ thống sẽ đóng chức năng đăng ký.
```

- **Deadlines:** register by 16:00 Thu 10/12

### Mail 83 · Buổi chia sẻ kinh nghiệm thực tập

```text
Buổi chia sẻ bắt đầu lúc 14h30 thứ Ba ngày 15/12.
Phòng sẽ mở cửa từ 14h.
```

- **Session:** Tue 15/12 from 14:30 · check-in 14:00

### Mail 84 · Chương trình cuối năm

```text
Chương trình bắt đầu lúc 19:00 ngày 18/12.
Vui lòng check-in từ 18:15.
Đăng ký trước 15/12.
```

- **Session:** Fri 18/12 from 19:00 · check-in 18:15
- **Deadlines:** register by Tue 15/12

### Mail 85 · Khóa đào tạo trực tuyến

```text
Khóa học mở từ 10/12 đến 20/12.
Sinh viên có thể xem bài giảng bất cứ lúc nào trong khoảng thời gian này.
Bài kiểm tra cuối khóa phải hoàn thành trước 23:59 ngày 20/12.
```

- **Period:** Thu 10/12 → Sun 20/12 · all day
- **Deadlines:** due 23:59 Sun 20/12

### Mail 86 · Họp nhóm ngày mai

```text
Nhóm mình gặp nhau lúc 9h sáng mai tại thư viện.
Cuộc họp dự kiến khoảng 45 phút.
```

- **Session:** Tue 03/11 09:00–~09:45 · day from a relative word (tomorrow)
- **Flags:** meeting

### Mail 87 · Chương trình trao đổi học thuật

```text
Hạn đăng ký chương trình là 15/12.
Phỏng vấn diễn ra từ 08:00 đến 12:00 ngày 17/12.
Mỗi ứng viên sẽ có một khung giờ riêng.
```

- **Period:** Thu 17/12 · 08:00–12:00 · details later
- **Deadlines:** register by Tue 15/12
- **Flags:** meeting

### Mail 88 · Hoạt động tình nguyện cuối tuần

```text
Hoạt động bắt đầu lúc 06:30 sáng thứ Bảy.
Sinh viên tập trung tại cổng trường lúc 06:00.
Hoạt động dự kiến kết thúc vào 11:30.
```

- **Session:** Sat 07/11 06:30–~11:30 · check-in 06:00 · day from a relative word (a weekday alone)

### Mail 89 · Thông báo kết quả học bổng

```text
Kết quả sẽ được công bố vào 20/12.
Danh sách phỏng vấn đã được công bố vào 15/12.
```

- **Flags:** meeting
- *Note:* both dates are announcements; only the flag (“phỏng vấn”). The meeting flag marks a class activity that may need Join, not only a meeting (design §2).

### Mail 90 · Buổi gặp mặt sinh viên

```text
Buổi gặp mặt diễn ra chiều ngày 21/12, từ 14:00 đến 17:00.
Bạn có thể tham dự bất kỳ lúc nào trong khung giờ trên.
```

- **Period:** Mon 21/12 · 14:00–17:00
- **Flags:** meeting

### Mail 91 · Nhắc hạn xác nhận chỗ

```text
Vui lòng xác nhận chỗ trước 12:00 ngày 19/12.
Sự kiện diễn ra vào 22/12 lúc 09:00.
```

- **Session:** Tue 22/12 from 09:00
- **Deadlines:** confirm by 12:00 Sat 19/12

### Mail 92 · Lịch nghỉ lễ

```text
Trường nghỉ từ 24/12 đến 26/12.
Các lớp học sẽ trở lại bình thường vào 27/12.
```

- **Nothing.**
- *Note:* a school holiday: left to the class-change spec (design §10).

### Mail 93 · Buổi thuyết trình đồ án

```text
Nhóm của bạn thuyết trình vào 10:30 ngày 23/12.
Thời gian trình bày là 15 phút, sau đó có 10 phút hỏi đáp.
```

- **Session:** Wed 23/12 10:30–10:55
- **Flags:** meeting
- *Note:* 15 minutes of presenting, then 10 of questions: 25 minutes.

### Mail 94 · Đăng ký chương trình mùa đông

```text
Đăng ký bắt đầu 18/12 và kết thúc 22/12 lúc 23:59.
Chương trình bắt đầu 26/12 lúc 08:00.
```

- **Session:** Sat 26/12 from 08:00
- **Deadlines:** registration opens Fri 18/12 · register by 23:59 Tue 22/12

### Mail 95 · Hướng dẫn nhận chứng chỉ

```text
Chứng chỉ sẽ được phát từ 09:00 đến 11:30 ngày 28/12 tại phòng A1.101.
Sinh viên có thể đến nhận trong thời gian trên.
```

- **Period:** Mon 28/12 · 09:00–11:30

### Mail 96 · Nhắc lịch họp online

```text
Cuộc họp online diễn ra lúc 20h tối thứ Hai.
Link họp sẽ được gửi trước 30 phút.
```

- **Session:** Mon 09/11 from 20:00 · link opens 19:30 · online · day from a relative word (a weekday alone)
- **Flags:** meeting

### Mail 97 · Thông báo deadline project

```text
Deadline project là 23:59 ngày 29/12.
Không có buổi thuyết trình trong thông báo này.
```

- **Deadlines:** due 23:59 Tue 29/12
- *Note:* “Không có buổi thuyết trình” does not set the meeting flag.

### Mail 98 · Sự kiện chào năm mới

```text
Sự kiện diễn ra từ 22:00 ngày 31/12/2026 đến 00:30 ngày 01/01/2027.
Khách có thể vào khu vực sự kiện từ 21:30.
```

- **Session:** Thu 31/12 22:00 – Fri 01/01/2027 00:30 (ends the next day) · check-in 21:30

### Mail 99 · Đăng ký tham dự hội nghị

```text
Đăng ký mở đến 25/12.
Hội nghị diễn ra vào 05/01/2027 từ 08:00 đến 17:00.
Người tham dự không bắt buộc phải ở lại cả ngày.
```

- **Period:** Tue 05/01/2027 · 08:00–17:00
- **Deadlines:** register by Fri 25/12

### Mail 100 · Thông báo cuối kỳ

```text
Các hoạt động cuối kỳ sẽ diễn ra trong khoảng 02/01 đến 10/01/2027.
Lịch cụ thể của từng hoạt động sẽ được gửi trong email tiếp theo.
Không có thời gian cụ thể cho từng hoạt động trong email này.
```

- **Period:** Sat 02/01/2027 → Sun 10/01/2027 · all day · details later

## Group C: short cases from the design discussion (arrive Mon 28/09/2026; checked by the student)

### C01 · Thông báo

```text
Hạn đăng ký: 05/10/2026. Sự kiện diễn ra lúc 14h00 ngày 12/10/2026.
```

- **Session:** Mon 12/10 from 14:00
- **Deadlines:** register by Mon 05/10

### C02 · Thông báo

```text
Cổng đăng ký mở từ 8h00 ngày 01/10/2026 đến 17h00 ngày 10/10/2026.
Chương trình diễn ra 14h00 - 16h30 ngày 15/10/2026.
```

- **Session:** Thu 15/10 14:00–16:30
- **Deadlines:** registration opens 08:00 Thu 01/10 · register by 17:00 Sat 10/10

### C03 · Thông báo

```text
Sinh viên đăng ký tại link bên dưới trước 17h00 ngày 30/09/2026.
Workshop diễn ra lúc 14h00 ngày 05/10/2026.
```

- **Session:** Mon 05/10 from 14:00
- **Deadlines:** register by 17:00 Wed 30/09

### C04 · Webinar

```text
Please register by 5 PM, October 3.
The talk starts at 2 PM on October 10.
```

- **Session:** Sat 10/10 from 14:00
- **Deadlines:** register by 17:00 Sat 03/10

### C05 · Thông báo

```text
Ngày tổ chức: 15/10/2026
Thời gian đăng ký: từ 01/10 đến 10/10/2026
Thời gian: 14h00 – 16h00
```

- **Session:** Thu 15/10 14:00–16:00
- **Deadlines:** registration opens Thu 01/10 · register by Sat 10/10

### C06 · Cuộc thi

```text
Vòng 1 diễn ra từ 8h00 ngày 01/10/2026 đến 17h00 ngày 05/10/2026.
```

- **Period:** Thu 01/10 08:00 → Mon 05/10 17:00 · label Round 1

### C07 · Hội thao

```text
Hội thao diễn ra từ ngày 01/10 đến ngày 05/10/2026, từ 7h00 - 11h00 mỗi ngày.
```

- **Sessions:**
  - Thu 01/10 07:00–11:00
  - Fri 02/10 07:00–11:00
  - Sat 03/10 07:00–11:00
  - Sun 04/10 07:00–11:00
  - Mon 05/10 07:00–11:00

### C08 · Họp nhóm

```text
Thầy hẹn cả nhóm họp lúc 9h sáng thứ Ba tuần sau tại phòng A2.401.
```

- **Session:** Tue 06/10 from 09:00 · day from a relative word (next week)
- **Flags:** meeting

### C09 · RE: Họp nhóm

```text
Ok em, mình dời sang 15h00 nhé.

From: Đặng Văn Long
Sent: 28/09/2026
Cả nhóm gặp thầy lúc 10h00 ngày 02/10/2026.
```

- **Flags:** meeting
- *Note:* a reply: the quoted part is cut, and the new time 15h00 has no day, so no session.

### C10 · Workshop

```text
Ngày 05/10/2026: hạn đăng ký 12h00, workshop 14h00 - 16h30.
```

- **Session:** Mon 05/10 14:00–16:30
- **Deadlines:** register by 12:00 Mon 05/10

### C11 · Workshop

```text
Sinh viên đăng ký trước 12h00 để tham gia workshop lúc 14h00 ngày 05/10/2026.
```

- **Session:** Mon 05/10 from 14:00
- **Deadlines:** register by 12:00 Mon 05/10

### C12 · Workshop

```text
Thời gian đăng ký: 8h00 - 12h00 ngày 05/10/2026; Thời gian tổ chức: 14h00 - 16h00 ngày 05/10/2026.
```

- **Session:** Mon 05/10 14:00–16:00
- **Deadlines:** registration opens 08:00 Mon 05/10 · register by 12:00 Mon 05/10

### C13 · Workshop

```text
Đăng ký tại chỗ lúc 13h30, chương trình bắt đầu 14h00 ngày 05/10/2026.
```

- **Session:** Mon 05/10 from 14:00 · check-in 13:30

### C14 · Thông báo

```text
Chương trình diễn ra vào lúc 14 giờ 00 ngày 05/10/2026.
```

- **Session:** Mon 05/10 from 14:00

### C15 · Thông báo

```text
Thời gian: 8 giờ 30 phút, ngày 05/10/2026.
```

- **Session:** Mon 05/10 from 08:30

### C16 · Thông báo

```text
Thời gian: 14h00 – 16h30
Ngày: 05/10/2026
```

- **Session:** Mon 05/10 14:00–16:30

### C17 · Học bổng

```text
Ngày 28/9/2026, Phòng CTSV thông báo học bổng.
Điều kiện: điểm trung bình từ 7.50 trở lên.
```

- **Nothing.**
- *Note:* 7.50 is a score, not a time.

### C18 · Workshop

```text
Workshop dời từ 14h00 ngày 05/10/2026 sang 15h00 ngày 06/10/2026.
```

- **Session:** Tue 06/10 from 15:00

### C19 · Workshop

```text
Hủy buổi workshop 14h00 ngày 05/10/2026 do thời tiết xấu.
```

- **Nothing.**

### C20 · Webinar

```text
The webinar starts at 9:00 AM EST on October 5, 2026.
```

- **Session:** Mon 05/10 from 21:00
- *Note:* EST is UTC−5, so 9:00 AM EST is 21:00 in Vietnam.

### C21 · Lịch họp

```text
Thời gian: 05/10/2026 2:00 CH - 3:00 CH
```

- **Session:** Mon 05/10 14:00–15:00
- **Flags:** meeting
- *Note:* the subject “Lịch họp” sets the meeting flag (corrected while planning: the first draft left it out).

### C22 · Lớp kỹ năng

```text
Lớp kỹ năng vào các ngày thứ Bảy từ 03/10 đến 24/10/2026, 8h00 - 11h00.
```

- **Sessions:**
  - Sat 03/10 08:00–11:00
  - Sat 10/10 08:00–11:00
  - Sat 17/10 08:00–11:00
  - Sat 24/10 08:00–11:00

### C23 · Workshop

```text
Workshop bắt đầu 14h00 ngày 05/10/2026, kéo dài 2 tiếng.
```

- **Session:** Mon 05/10 14:00–16:00

### C24 · Thông báo

```text
Thời gian: 14h00 ngày 05/10/26.
```

- **Session:** Mon 05/10 from 14:00

### C25 · Workshop

```text
Workshop diễn ra ngày 05/10/2026 tại hội trường A2.

--
Phòng Công tác Sinh viên
Giờ làm việc: 7h30 - 16h30, Thứ Hai đến Thứ Sáu
```

- **Period:** Mon 05/10 · all day
- *Note:* the signature is cut, so the office hours give nothing; the workshop has a day but no hour (rule P6).

### C26 · Ngày hội việc làm

```text
Sinh viên tham gia trực tiếp đăng ký trước 12h00 ngày 03/10. Tham gia online qua Zoom đăng ký trước 17h00 ngày 05/10.
```

- **Deadlines:** register by 12:00 Sat 03/10 (in person) · register by 17:00 Mon 05/10 (online)

### C27 · Lịch ca

```text
Ca 1: 8:00–10:00; Ca 2: 13:00–15:00 ngày 30/9
```

- **Sessions:**
  - Wed 30/09 08:00–10:00 · label Shift 1
  - Wed 30/09 13:00–15:00 · label Shift 2
