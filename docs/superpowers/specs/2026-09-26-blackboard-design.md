# School-Life-Assistant: Blackboard in the School module

**Date:** 2026-09-26
**Scope:** bring the student's Blackboard announcements, assignments and due dates, grades and new course materials into the School module
**Owner:** Nguyen Khang Vy
**Status:** Design approved in conversation, waiting for review of this document
**Builds on:** [EduSoft-first Phase 1 design](2026-09-25-edusoft-first-phase1-design.md). The laptop agent, safety rules and sync API described there stay the same unless this document says otherwise.

---

## 1. Goal

Lecturers at IU post announcements (e.g. "no class on Thursday", "class moves online"), assignments with deadlines, grades and course files on Blackboard (`https://blackboard.hcmiu.edu.vn`). Students have to open each course to see them. The School module should show all of it in one place, put deadlines on the calendar, and list what is new in the "What changed" feed.

IU also runs IULMS (Moodle, `lms.hcmiu.edu.vn`). The student's courses use Blackboard, so IULMS is out of scope.

### In scope

- Announcements of current-semester courses
- Assignments, tests and other graded items with their due dates
- The student's own grades and feedback for those items
- Course materials (files, folders, links), listed with links, never downloaded

### Not in scope

- Past semesters (the account lists 41 courses; only current ones are kept)
- Downloading files, submitting anything, posting, or changing anything on Blackboard
- AI summaries of announcements
- EduSoft's official final grades (a separate page, not part of this design)

---

## 2. What we found (checked 2026-09-26)

- **Blackboard Learn 3900.x.** The login page (`/webapps/login/`) is a normal form: `user_id`, `password`, a hidden one-time value (`blackboard.platform.security.NonceUtil.nonce`), `action`, `new_loc`. No CAPTCHA and no Microsoft sign-in button.
- **The student's Blackboard username and password are different from EduSoft's.**
- **Blackboard's REST API is on** (`/learn/api/public/v1/system/version` → 3900.0.0) and **accepts a normal logged-in session.** A one-time check with the student's own login returned HTTP 200 for:
  - `GET /learn/api/public/v1/users/me`
  - `GET /learn/api/public/v1/users/{id}/courses` (41 courses, all semesters)
  - `GET /learn/api/public/v1/courses/{id}/announcements`
  - `GET /learn/api/public/v2/courses/{id}/gradebook/columns` (graded items with due dates)
  - `GET /learn/api/public/v2/courses/{id}/gradebook/users/{userId}` (the student's grades)
  - `GET /learn/api/public/v1/courses/{id}/contents` (course materials)
  - `GET /learn/api/public/v1/calendars/items`
- **Encryption:** the server only offers TLS 1.2 with AES-CBC-SHA cipher suites (no AES-GCM, no ECDHE). Python refuses SHA-1 suites by default, so plain `requests` fails with a handshake error. The certificate itself is fine (Sectigo, `*.hcmiu.edu.vn`, 2048-bit RSA, SHA-256, valid until January 2027).

---

## 3. How it works

The same laptop agent (`sla-agent`), on the same schedule, syncs EduSoft first and then Blackboard:

1. Log in through Blackboard's login form with the **Blackboard** username and password from Windows Credential Manager.
2. Read, for each **current-semester** course: announcements, gradebook columns with due dates, the student's grades, and course materials (top level plus up to 2 folder levels).
3. Turn everything into the shared data format on the laptop: only the needed fields, announcement HTML turned into plain text.
4. Log out, then upload to the web app together with the EduSoft result.

About 40 to 60 requests per sync for 8 courses. With a sync every 6 to 12 hours this is a light load.

**Which courses are "current"** (decided by the student on 2026-09-26): the courses registered this semester, as listed on EduSoft.

1. Each sync, the agent opens EduSoft's course registration page (`default.aspx?page=dkmonhoc`) and reads the table under **"DANH SÁCH MÔN HỌC ĐÃ CHỌN"** (columns STT, Regis ID, Mã MH, Tên môn học, NMH, TTH, STC, STCHP, Học Phí, Miễn Giảm, Phải Đóng, Trạng Thái môn học). Rows with status **"Đã lưu vào CSDL"** are the registered courses; their `Mã MH` (e.g. `IT093IU`) and `NMH` (group, e.g. `02`) are kept.
2. A Blackboard course is current when its course code is on that list. How the code appears in Blackboard's course ID or name is confirmed from the real samples in step B2.
3. If several Blackboard courses share a code (e.g. a course taken again), the one whose group matches `NMH` wins; if that still ties, the most recently created one.
4. If the registration page can't be read (e.g. EduSoft is overloaded during registration week), the agent uses the course codes of the current EduSoft timetable instead; they are the same courses.

**The registration page is where students register and cancel courses. The agent only ever sends a `GET` for it and never submits its form or presses any of its buttons.** (Checked 2026-09-26, outside the registration period: the page says "ngoài thời gian đăng ký" and lists the 8 registered courses, matching the timetable.)

---

## 4. Security rules

All rules of the Phase 1 design apply. In addition:

1. **Separate login.** The Blackboard password is stored only in Windows Credential Manager under the service `SchoolLifeAssistant-Blackboard` (username = the Blackboard username). It is scrubbed from all logs like the EduSoft password.
2. **Read-only.** The only request that sends data is the login form. Everything else is `GET`. Logging out at the end is a `GET` to `/webapps/login/?action=logout`.
3. **Only `https://blackboard.hcmiu.edu.vn`.** Redirects to other sites are refused; a redirect to a Microsoft or SAML sign-in page, or a CAPTCHA, pauses Blackboard (never bypassed).
4. **Blackboard-only encryption setting.** For this host only, the agent allows these cipher suites, in this order: `ECDHE+AESGCM`, `ECDHE+CHACHA20`, `DHE+AESGCM`, `DHE-RSA-AES256-SHA`, `DHE-RSA-AES128-SHA`, at OpenSSL security level 2, TLS 1.2 or newer. Certificate and hostname checks stay on. RSA key exchange (no forward secrecy) stays refused. All other hosts, EduSoft included, keep Python's default settings.
5. **Safe text.** Announcement bodies and feedback are converted from HTML to plain text on the laptop (scripts and styles dropped, entities decoded) and shown with Jinja's autoescaping. Links shown in the app must start with `https://blackboard.hcmiu.edu.vn/`.
6. **Data minimization.** Uploaded: course name and code, announcement title, text (up to 5,000 characters) and dates, item names, due dates, scores, grade status, feedback (up to 1,000 characters), material titles, types, folder paths and dates, and Blackboard links. Not uploaded: other students' data, file contents, Blackboard internal user records.

---

## 5. EduSoft and Blackboard sync independently

Today a wrong EduSoft password ends the whole run. After this change:

- Each system has its **own pause** in the agent's state: `paused = {"edusoft": code or null, "blackboard": code or null}` (older state files with a single value are read as the EduSoft pause).
- A login failure of one system becomes **failed sections** for that system (not a whole-run error), so the other system still syncs and uploads.
- Setup: `sla-agent setup` asks for the Blackboard username and password after the EduSoft ones (Enter skips them). `sla-agent setup --blackboard` sets or changes only the Blackboard login. Running either clears that system's pause.
- The status card on the website shows one line per system, e.g. "EduSoft: synced 14:05 · Blackboard: paused, wrong password (run `sla-agent setup --blackboard`)".

---

## 6. Data

### Shared data format (`contract/sla_contract/schema.py`)

A new section `blackboard` in `FinishRun`, next to `timetable`, `exams` and `tuition`:

```
Blackboard
└── courses[]: bb_id, course_code (nullable), name, url
    ├── announcements[]: bb_id, title, text, posted_at, url
    ├── assignments[]:   bb_id, name, due_at (nullable), points_possible (nullable),
    │                    score (nullable), grade_text (nullable), status, feedback (nullable),
    │                    graded_at (nullable), url
    └── materials[]:     bb_id, title, kind (file/folder/link/document/other), path, created_at (nullable), url
```

Times are timezone-aware like the rest of the format. Unknown fields are rejected, as today.

### Tables

| Table | Columns (every table also has `id` and `user_id`) |
|---|---|
| `school_bb_courses` | bb_id, course_code, name, url |
| `school_bb_announcements` | course_id, bb_id, title, text, posted_at, url |
| `school_bb_assignments` | course_id, bb_id, name, due_at, points_possible, score, grade_text, status, feedback, graded_at, url |
| `school_bb_materials` | course_id, bb_id, title, kind, path, created_at, url |

A successful `blackboard` section replaces the user's Blackboard rows in one transaction. A failed section keeps the old rows.

### "What changed" lines

Compared by `bb_id` before replacing:

- New announcement: "New announcement · Web Application Development: No class on Thursday 01/10"
- New assignment: "New assignment · OOAD: Lab 3, due Fri 02/10 23:59"
- Due date changed: "Due date changed · Algorithms, Homework 2: 05/10 → 08/10"
- New grade: "New grade · Physics 4, Lab report 1: 8.5/10"
- New material: "New material · Web Application Development: Week 5 slides.pdf"
- The first Blackboard sync writes one summary line per kind instead (e.g. "Blackboard loaded: 8 courses, 12 announcements, 20 assignments"), and nothing when a list is empty.

---

## 7. What the student sees

- **School menu:** Overview · Timetable · **Courses** · Exams · Tuition · Devices.
- **Overview:** new boxes **Due soon** (assignments due in the next 7 days) and **Latest announcements** (3 newest, with an excerpt).
- **Timetable calendar:** deadlines in **orange**, in the strip at the top of each day ("Due 23:59: Lab 3"), because most deadlines fall outside the 07:00 to 19:00 grid. The calendar feed adds them as all-day entries.
- **Courses page:** the current courses. Each course page has four parts:
  - **Announcements:** newest first, full plain text, date.
  - **Assignments:** due date, graded or not, score, overdue marker.
  - **Grades:** score out of maximum and feedback text.
  - **Materials:** newest first with folder path and date.
- Every item has an **Open in Blackboard ↗** link (new tab, `rel="noopener noreferrer"`).
- Every page is login-protected and shows only the logged-in user's rows; another user's course returns 404.

---

## 8. Error handling

| Situation | What happens |
|---|---|
| Wrong Blackboard username or password | Blackboard pauses after exactly one attempt; EduSoft continues; status says "run `sla-agent setup --blackboard`" |
| CAPTCHA, one-time code, Microsoft/SAML sign-in | Blackboard pauses; nothing is bypassed |
| Session expired (HTTP 401 from the API or the login page shown) | Log in again once and retry once; otherwise the section fails with `session_expired` |
| A course refuses one request (HTTP 403 or 404, e.g. grades hidden) | That list is empty for that course; the rest continues |
| Response not in the expected format | The `blackboard` section fails with the new error code `source_changed`; old data kept |
| Connection or encryption problem | `network`; tried again at the next sync |

`source_changed` is added to the shared format's error codes for Blackboard; `edusoft_changed` stays for EduSoft.

---

## 9. Testing

- **Readers** are tested against anonymized copies of real Blackboard JSON saved with `sla-agent fetch --save-html` (names, IDs, texts, scores and links replaced; checked for leaks like the EduSoft copies).
- **Automated tests:**
  - The Blackboard encryption setting: SHA-1 DHE suites allowed, RSA key exchange refused, certificate verification on, and the setting is used only for the Blackboard host.
  - Login: form fields including the nonce; one attempt on a wrong password; re-login once after a 401.
  - Independent pauses: an EduSoft login failure still uploads Blackboard, and the other way round; old single-value state files still load.
  - HTML to text: scripts, styles and tags removed, entities decoded, length limits.
  - Current-course rule: registered list read from an anonymized copy of the registration page (only "Đã lưu vào CSDL" rows), matching by code, the group tie-break, and the timetable fallback. The registration page is only ever fetched with `GET`.
  - Due dates in Vietnam time, "What changed" lines, calendar feed entries, page ownership (404), links limited to the Blackboard host.
- **Manual:** `sla-agent setup --blackboard`, `sla-agent sync-now`, then check the Courses pages, Overview boxes and calendar in Edge on laptop and phone widths.

---

## 10. Build order

| Step | Work | Done when |
|---|---|---|
| B1 | Agent: Blackboard client (encryption setting, login, logout, session expiry), credentials, `setup --blackboard`, pause per system | Tests with fake Blackboard answers pass |
| B2 | Student runs `sla-agent setup --blackboard`; save real samples on the laptop (Blackboard JSON and the registration page), anonymize them, write the readers and the current-course rule | Reader tests pass against the anonymized copies |
| B3 | Server: data format, tables and migration, saving, "What changed" lines, status per system | Tests with fake uploads pass |
| B4 | Pages: Courses and course pages, Overview boxes, deadlines in the calendar | Page tests pass; Edge screenshots look right |
| B5 | Real sync end to end, docs (README, agent setup) | The student sees their real Blackboard data |

---

## 11. Risks

| Risk | How we handle it |
|---|---|
| IU changes Blackboard's encryption or login page | Failures are reported per system; the encryption setting is one small, tested piece |
| IU moves courses to IULMS | Out of scope now; the per-source design lets a Moodle reader be added later |
| Many requests per sync | Only current courses, folders at most 2 levels deep, sync at most every 6 hours |
| Announcements contain formatting or scripts | Converted to plain text on the laptop and escaped again on the page |
| Schedule: this adds 2 to 3 weeks | Personal events, the sync-interval setting and deployment (step 6) move later but still fit the 12 weeks |
