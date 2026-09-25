# School-Life-Assistant: Phase 1 design (EduSoft first)

**Date:** 2026-09-25
**Scope:** the shared app foundation, and the School module's EduSoft sync (timetable, exams, tuition)
**Owner:** Nguyen Khang Vy
**Status:** Approved by the School module owner, waiting for team review
**Replaces:** the earlier Outlook-first design (commit `6e4580e`), which has been dropped

---

## 1. Background

School-Life-Assistant is one web app for IU students. It's our group project for the Web Application Development course.

- **Team:** 3 people, one module each, all in the same app:
  - **School** (Vy): brings your EduSoft timetable, exams and tuition into one place, with a calendar.
  - **Expense** (teammate): expense management.
  - **Health** (teammate): health management.
- **Time:** about 12 weeks.
- **Course requirements:** login/register, create/edit/delete data, a public link.
- **Allowed tech:** Python, JavaScript, HTML, CSS, MySQL, GitHub.
- **Cost:** everything must be free.

**Why EduSoft first:** your class schedule, exam dates and tuition deadline all live in EduSoft Web. You have to log in and click through several pages to see them, and nothing warns you when something changes. Phase 1 syncs this data automatically and shows it on one calendar.

---

## 2. Scope

### In Phase 1

1. **Shared foundation** (used by all 3 modules): app skeleton, database setup, shared page layout, register/login/logout, and the rules for how each module plugs in (section 9).
2. **School module:**
   - A small **sync program on the laptop** (`sla-agent`). It logs in to EduSoft on a schedule and sends your timetable, exams and tuition to the web app.
   - Pages: School home, timetable, calendar, exams, tuition, sync status, devices.
   - **Personal events** you can create, edit and delete, with a **clash warning** when one overlaps a class or exam.
   - A **"What changed" feed**, for example "IT101 Tue 30/09: room A2.307 → LA1.605".
   - Installable on a phone (PWA) and published at a public link.

### Not in Phase 1

- Grades, EduSoft public announcements, Outlook email, Blackboard.
- The full "should I attend?" bot. The clash warning is its first building block.
- Any action on EduSoft other than reading (no course registration, nothing that changes data there).
- The Expense and Health features. This document only defines how those modules plug in.

---

## 3. Key constraints and what we found

The user's requirements for the sync:

- Enter the EduSoft credentials once and keep them in the device's secure storage, never in MySQL.
- Sync automatically on a schedule the user sets (6, 12 or 24 hours), without opening the app. "Sync now" must work at any time.
- Show a clear status: last synced, syncing, success, failed.
- Handle wrong credentials, expired sessions, network failures and EduSoft page changes.
- **Never bypass a CAPTCHA, a one-time code or any other security check.**
- Don't send credentials to any service that doesn't need them.
- The app only retrieves and organizes information. The user makes every decision.

What we checked on 2026-09-25:

- **EduSoft has no API.** The only way in is to log in and read the pages.
- **The login form** (`https://edusoftweb.hcmiu.edu.vn/default.aspx?page=dangnhap`) is a classic ASP.NET form:
  - Fields: `ctl00$ContentPlaceHolder1$ctl00$txtTaiKhoa` (student ID), `ctl00$ContentPlaceHolder1$ctl00$txtMatKhau` (password), and the submit button `ctl00$ContentPlaceHolder1$ctl00$btnDangNhap`.
  - Hidden fields: `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTTARGET`, `__EVENTARGUMENT`. Session cookie: `ASP.NET_SessionId`.
  - **There is no CAPTCHA and no one-time code.** A "Login with Microsoft 365" button also exists; we don't use it.
- EduSoft blocks requests whose user agent is `curl`. A request that honestly names our app (`SchoolLifeAssistant/0.1 (IU student project)`) is accepted, so we never pretend to be a browser.
- An older student project, [TP-O/edusoft](https://github.com/TP-O/edusoft) (MIT license, archived 2022), read the schedule, exams, tuition and transcript from IU's EduSoft. That confirms these pages can be read after login.
- **What a web app in the browser can't do:**
  - read the operating system's password store (Windows Credential Manager, the iPhone Keychain),
  - call EduSoft from the page, because EduSoft is a different site, and
  - run on a schedule while it's closed.

**Conclusion:** keeping the password on the device *and* syncing automatically both require a small program running on the laptop. That is the core of this design.

---

## 4. Architecture

```
YOUR LAPTOP                                   CLOUD (free)
┌─────────────────────────────┐               ┌──────────────────────────────┐
│ Windows Task Scheduler      │               │ Web app (Flask on Render)    │
│  every 15 min + at logon    │               │  - login/register (shared)   │
│        ▼                    │  HTTPS +      │  - School pages              │
│ sla-agent (Python)          │  device key   │  - Sync API (device key only)│
│  1. "is a sync due?" ───────┼──────────────►│        ▼                     │
│  2. log in + read 3 pages   │               │ MySQL (Aiven): academic data │
│     from EduSoft (HTTPS)    │               │  + sync history. No passwords│
│  3. parse → clean JSON ─────┼──────────────►└──────────────────────────────┘
│ Windows Credential Manager: │                   ▲
│  EduSoft password,          │                   │ phone / laptop browser (PWA)
│  device key                 │
└─────────────────────────────┘
```

**How one sync works:**

1. Every 15 minutes, and when you log in to Windows, Task Scheduler starts `sla-agent run`.
2. The agent asks the web app whether a sync is due: `GET /api/school/sync/check`. The answer is "yes" if your interval (6/12/24 h) has passed or you pressed **Sync now** on any device.
3. If it's due, the agent tells the web app it's starting (`POST /api/school/sync/runs`). The web app now shows **Syncing…**.
4. The agent logs in to EduSoft once and reads the timetable, exam and tuition pages.
5. It turns each page into clean data **on the laptop**. Only the needed fields are kept.
6. It sends the result for each part (success + data, or failure + reason) with `POST /api/school/sync/runs/<id>/finish`.
7. The web app saves each part that succeeded, records what changed, and shows **Synced at 14:05** (or the failure reason).

If the laptop was off, the next sync happens at the next Windows logon. `sla-agent sync-now` syncs right away.

**Tech stack:**

| Part | Choice | Why |
|---|---|---|
| Web app | Python 3.12 + Flask | The team knows Python; Flask is simple |
| Pages | Jinja templates (built on the server) + CSS + a little JavaScript | One shared layout for all 3 modules |
| Calendar | FullCalendar (JavaScript, from a CDN) | Month/week views without writing date-grid code |
| Database | MySQL 8, through Flask-SQLAlchemy + PyMySQL | Course requirement |
| Table changes | Flask-Migrate | Everyone gets the same tables from code |
| Login | Flask-Login + Werkzeug password hashing | Standard and safe |
| Forms | Flask-WTF | Protection against fake form submissions (CSRF) |
| Data format check | pydantic | The web app and the agent share one format definition |
| Laptop agent | `requests`, `beautifulsoup4`, `keyring` | HTTP, reading HTML, Windows Credential Manager |
| Tests | pytest, `responses` (fake HTTP) | Standard Python testing |
| Hosting | Render (free web service) + Aiven (free MySQL, 1 GB) | Public HTTPS link at no cost |
| Automation | GitHub Actions | Runs the tests on every pull request |

---

## 5. Security rules

These rules must hold in the code and be checked by tests.

1. **The EduSoft password:**
   - It's typed once in `sla-agent setup`, without being shown on screen (`getpass`).
   - It's checked with one real login before it's saved. A wrong password is never saved.
   - It's stored **only** in Windows Credential Manager, through the `keyring` library (service name `SchoolLifeAssistant-EduSoft`).
   - It's never written to files, logs, command lines, environment variables, MySQL, or our server. A logging filter scrubs it from all log output.
   - It is only ever sent to `https://edusoftweb.hcmiu.edu.vn`.
2. **Talking to EduSoft:**
   - The agent only connects to `https://edusoftweb.hcmiu.edu.vn`. It refuses redirects to any other site or to plain `http`.
   - It uses the honest user agent and a timeout on every request.
   - One sync is about 4 requests. Scheduled syncs are at least 1 hour apart and manual syncs at least 5 minutes apart.
3. **The device key** (how the agent proves who it is to the web app):
   - It's created on the Devices page with `secrets.token_urlsafe(32)` and shown **once**.
   - The web app stores only its SHA-256 hash. A database leak therefore can't be used to send fake data.
   - The laptop stores it in Windows Credential Manager.
   - It only works on `/api/school/sync/*` and only for its owner. It can be cancelled at any time; a cancelled key gets `401`.
4. **Data minimization:**
   - The agent sends only the parsed fields defined in the shared format (section 7).
   - Raw EduSoft pages never leave the laptop. The only exception is `sla-agent fetch --save-html`, which saves them to the laptop's own disk for building tests.
5. **Stop instead of retrying:**
   - If EduSoft rejects the password, automatic sync **pauses** with no second attempt, so the EduSoft account can't be locked.
   - If a CAPTCHA, a one-time code or a redirect to Microsoft login appears, sync **pauses** with a message. Nothing is bypassed. The fallback is `sla-agent import <file>`: you save the page from your own browser and the agent reads it.
6. **Web app:**
   - Passwords are stored only as Werkzeug hashes.
   - Every form has CSRF protection. The JSON sync API uses the device key instead.
   - Session cookies are HttpOnly, Secure (on the public site) and SameSite=Lax.
   - Every query is filtered by `current_user.id`. Another user's row returns `404`.
   - Jinja escapes all text. JavaScript uses `textContent` (never `innerHTML`) for text that came from EduSoft.

---

## 6. Error handling

| Situation | How it's detected | What happens |
|---|---|---|
| Wrong student ID or password | After login, EduSoft shows the login form and its error message again | Pause locally. The run ends `failed / bad_credentials`. The web app shows "Paused: run `sla-agent setup`" |
| Session expired during a sync | A page redirects to `dangnhap` or shows the login form | Log in again once and retry that page once. Otherwise `failed / session_expired` |
| Network problem, timeout, server error, EduSoft maintenance page | Exceptions, status codes, maintenance text | Retry twice (after 5 s, then 30 s). Then `failed / network`. The next check tries again |
| EduSoft changed a page layout | The parser can't find the expected table or column headers | Only that part fails (`edusoft_changed`). The other parts are saved. The run is `partial` and names the part |
| CAPTCHA, one-time code or Microsoft sign-in appears | Unexpected inputs or a redirect on the login page | Pause `extra_verification`. Suggest `sla-agent import` |
| Our web app can't be reached | Connection error | Logged on the laptop. The next check tries again |
| Device key cancelled | `401` from the web app | Stop. Local status says "run `sla-agent setup`" |
| Sync stuck | A run has been `running` for more than 15 minutes | The web app shows it as failed (timed out) |
| Laptop hasn't checked in | `last_seen_at` is older than 2 × the interval | The web app warns "your laptop hasn't checked in since …" |

**Status messages shown to the user:** Never synced · Requested, waiting for your laptop · Syncing… · Synced at 14:05 · Partly synced (the tuition page couldn't be read) · Failed: *reason + what to do* · Paused: *reason + what to do* · Your laptop hasn't checked in since *time*.

---

## 7. Data

All times are stored in **UTC** and shown in **Vietnam time** (Asia/Ho_Chi_Minh, UTC+7). Every School table has a `user_id` linked to `users.id`.

| Table | Columns |
|---|---|
| `users` (shared) | id, email (unique), display_name, password_hash, created_at |
| `school_courses` | term_code, course_code, course_name, group, credits, lecturer |
| `school_class_meetings` | course_id, start_at, end_at, room. **One row per real class session.** EduSoft's week pattern is turned into actual dates, using IU's period-time table (to be confirmed with real pages) |
| `school_exams` | term_code, course_code, course_name, exam_type, start_at, duration_min, room, notes |
| `school_tuition` | term_code, amount_due, amount_paid, balance, due_date (nullable), status_text, items (JSON) |
| `school_events` | title, start_at, end_at, all_day, location, notes. The user's **personal events** |
| `school_sync_devices` | name, token_hash (unique), created_at, last_seen_at, revoked_at |
| `school_sync_settings` | user_id (primary key), interval_hours (6/12/24), sync_requested_at |
| `school_sync_runs` | device_id, trigger (scheduled/manual/import), started_at, finished_at, status (running/success/partial/failed), error_code, error_message, sections (JSON) |
| `school_changes` | sync_run_id, section, kind (added/removed/changed), summary, created_at, seen_at |

**Saving a sync:**

- The timetable, exams and tuition are handled as three separate parts.
- A part that arrived correctly replaces that user's rows for that term in **one transaction**.
- A part that failed keeps its old rows.
- Before replacing, the old and new rows are compared, and every difference becomes a row in `school_changes` for the "What changed" feed.

**The shared data format** lives in `contract/sla_contract/schema.py` (pydantic models). The web app uses it to check every upload; wrong data gets `422`. The agent uses it to build uploads. Because both sides import the same file, they can't disagree about the format.

---

## 8. Pages and API

| URL | Page | What it does |
|---|---|---|
| `/school/` | School home | Sync status card with **Sync now**, today's and tomorrow's classes, next exams, tuition balance and due date, unseen changes |
| `/school/timetable?week=` | Timetable | Week grid, previous/next week |
| `/school/calendar` | Calendar | FullCalendar; classes, exams, tuition deadline and personal events in different colors. Data from `/school/api/calendar?start=&end=` |
| `/school/exams` | Exams | List by date; past exams greyed out |
| `/school/tuition` | Tuition | Per term: due, paid, balance, deadline |
| `/school/events/new`, `/school/events/<id>/edit`, `/school/events/<id>/delete` | Personal events | Create, edit, delete (POST with a confirm step). **Clash warning** when the event overlaps a class or exam. It's only a warning; the user decides |
| `/school/changes` | What changed | The changes feed; mark as seen |
| `/school/sync` | Sync | Detailed status (refreshes every 10 s while a sync is requested or running), last 20 runs, interval setting |
| `/school/devices` | Devices | Add (key shown once), rename, cancel |

**Sync API** (JSON, device key in the `Authorization: Bearer` header, used only by the agent):

| Method and URL | Purpose |
|---|---|
| `GET /api/school/sync/check` | Is a sync due? Also records that the laptop checked in |
| `POST /api/school/sync/runs` | "I'm starting a sync" → returns a run id |
| `POST /api/school/sync/runs/<id>/finish` | The result for each part: data, or error code and message |

**How this meets the course requirements:**

- **Create:** personal events, devices.
- **Read:** every page above.
- **Update:** personal events, device name, sync interval, marking changes as seen.
- **Delete:** personal events; cancelling a device.

**Phone app (PWA):** `manifest.json` plus a service worker that caches only CSS, JS and icons. Pages and data always come fresh from the server.

---

## 9. Shared foundation: rules for all modules

### Folder structure

```
School-Life-Assistant/
├── app/                      # the web app
│   ├── __init__.py           # create_app(): builds the app, registers modules
│   ├── config.py             # settings read from environment variables
│   ├── extensions.py         # db, migrate, login_manager, csrf
│   ├── auth/                 # register / login / logout (shared)
│   ├── main/                 # home page / dashboard
│   ├── school/               # Vy's module
│   ├── expense/              # teammate's module
│   ├── health/               # teammate's module
│   ├── templates/            # base.html + one folder per module
│   └── static/               # css, js, icons, manifest.json, service-worker.js
├── contract/                 # shared sync data format (web app + agent)
├── agent/                    # the laptop sync program (sla-agent)
├── migrations/               # database version history (shared)
├── tests/
├── docs/
├── .github/workflows/        # CI: runs the tests on every pull request
├── .env.example              # list of settings, no real secrets
├── requirements.txt
└── wsgi.py
```

### How a module plugs in

Each module is a **Flask Blueprint** in its own folder.

1. **URLs** start with the module name: `/school/...`, `/expense/...`, `/health/...`.
2. **Table names** start with the module name: `school_...`, `expense_...`, `health_...`.
3. **Every table** holding user data has a `user_id` column linked to `users.id`.
4. **Every page** uses `@login_required` and shows only the current user's rows (always filter by `current_user.id`).
5. **Every template** extends `base.html`.
6. **Every form** uses Flask-WTF, so CSRF protection is on.
7. **The menu** in `base.html` has one link per module. Each person adds their own.

### Team rules

- Never commit `.env` or any secret. Real settings go in `.env` locally and in the hosting dashboard online.
- Work on a branch, open a pull request, and have a teammate review it before merging to `main`.
- **Database changes:** pull `main` first, then run `flask db migrate`. If two migrations clash ("multiple heads"), run `flask db merge heads` and commit the result.

---

## 10. The laptop agent (`sla-agent`)

| Command | What it does |
|---|---|
| `sla-agent setup` | Asks for the web app address, the device key, your student ID and your password. Checks the login once, saves the secrets in Windows Credential Manager, and creates the scheduled task (every 15 min + at logon) |
| `sla-agent run` | What the scheduled task calls: asks the web app whether a sync is due, and syncs if it is |
| `sla-agent sync-now` | Syncs immediately |
| `sla-agent status` | Shows the last local result and whether sync is paused |
| `sla-agent import <file>` | Reads a page you saved from your own browser and uploads it (fallback if automatic login stops working) |
| `sla-agent fetch --save-html` | Saves your EduSoft pages **on the laptop only**, used to build the parser tests |
| `sla-agent forget` | Deletes the saved secrets and the scheduled task |

- Local files live in `%LOCALAPPDATA%\SchoolLifeAssistant\`: the state file, and a rotating log with secrets scrubbed.
- The parsers (`parsers/timetable.py`, `exams.py`, `tuition.py`) are written against **real, anonymized EduSoft pages**. The School owner saves them with `--save-html` and removes their name, student ID and date of birth. IU's class period times (when period 1 starts, and so on) are confirmed at the same time.

---

## 11. Build order

Each step ends with passing tests and a hands-on check.

| Step | Work | Done when |
|---|---|---|
| 0 | This document | The team has reviewed it |
| 1 | **Foundation:** Flask app, MySQL, migrations, `base.html`, register/login/logout, CI, module rules | You can register, log in and see the dashboard. **Teammates can start** |
| 2 | **Server side of syncing:** School tables, shared data format, Devices page, sync API, saving parts, changes feed logic, status logic | Tests with fake uploads pass; the Devices page works |
| 3 | **Agent core:** Credential Manager storage, safe EduSoft client, login and detection of wrong password / expired session / CAPTCHA, uploader, commands, scheduled task, log scrubbing | Tests with fake EduSoft pages pass |
| 4 | **Real pages:** save and anonymize the real EduSoft pages, confirm period times, write the three parsers | First real sync into a local web app |
| 5 | **Pages:** School home, timetable, calendar, exams, tuition, personal events + clash warning, changes feed, sync page | Every page works on a laptop and a phone screen |
| 6 | **Deploy + PWA:** Render + Aiven, settings, public link, manifest and service worker, `docs/agent-setup.md` | Real end-to-end check from a phone |

---

## 12. Testing

**Automated** (pytest, run by GitHub Actions on every pull request):

- Register, login, logout, wrong password.
- One user can never see or change another user's data (`404`).
- An unknown or cancelled device key gets `401`. The database stores only the key's hash.
- An upload in the wrong format gets `422`.
- Saving replaces only the parts that succeeded. The changes feed produces the expected summaries.
- The clash check finds overlaps and ignores events that only touch at the edges (one ends at 10:00, the next starts at 10:00).
- Sync scheduling: interval, "Sync now" requests, minimum gaps.
- Agent:
  - A wrong password pauses sync after **exactly one** login attempt.
  - An expired session causes one re-login.
  - A CAPTCHA page pauses sync.
  - A redirect to another site is refused.
- **The password never appears in logs:** a test captures all log output during a fake sync and fails if the password string shows up anywhere.
- Parser tests against the anonymized real pages.

EduSoft and the web app are replaced by fake responses in the agent tests. Real calls are checked by hand.

**Manual checks:**

- After `sla-agent setup`, the password appears in Windows Credential Manager ("Generic credentials") and nowhere in MySQL.
- After `sla-agent sync-now`, the web status goes Syncing → Synced, and the timetable, exams and tuition match EduSoft.
- Pressing **Sync now** on the phone gets picked up by the laptop within 15 minutes.
- With a 6-hour interval, no sync happens before it's due.
- After cancelling the device, the next run reports the cancelled key.
- A wrong password in setup is rejected and nothing is stored.
- The public link works on a phone and installs as an app.

---

## 13. Risks

| Risk | How we handle it |
|---|---|
| EduSoft changes a page layout | Parts fail separately and old data stays; the status names the broken part; parser tests make the fix quick |
| IU adds a CAPTCHA or one-time code | Sync pauses, nothing is bypassed, `sla-agent import` still works |
| Sync only runs while the laptop is on | Fine for data that changes a few times a semester; the web app shows the last check-in time |
| Too many automated requests to IU | About 4 requests per sync, honest user agent, at least 1 hour between scheduled syncs |
| Render free plan: sleeps after 15 min idle, 750 hours/month | The agent's 15-minute check keeps it awake while the laptop is on; one web service stays within 750 hours |
| Aiven free MySQL switches off after long inactivity | Regular syncs keep it active; Aiven emails before switching it off |
| Two teammates change the database at the same time | Team rules in section 9 (pull first, `flask db merge heads`) |
