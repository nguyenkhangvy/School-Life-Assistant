# School-Life-Assistant: site roles (Student, Auditor, Admin)

**Date:** 2026-10-06
**Scope:** every account gets one role. Students keep School, Groups and Friends. Auditors read the audit log and statistics. Admins manage accounts. Also new: Profile and password change, deactivating accounts (soft delete), the Users page, the audit log and the Statistics page.
**Owner:** Nguyen Khang Vy
**Status:** Approved 2026-10-06. Stage 1 (roles and profile): docs/superpowers/plans/2026-10-06-site-roles-stage1.md. Stages 2 and 3 get their own plans.
**Builds on:** [Java website](2026-09-26-java-website-design.md) (modules, menu, rules for the Java code), [Friends and groups](2026-10-06-friends-and-groups-design.md) (paging, "Sort by … then by", Find people) and [Connect button](2026-10-04-connect-button-design.md) (the Connect page and the laptop's trade-in). Everything there stays the same unless this document says otherwise.

---

## 1. Goal

The course spec (`final_project_description_v3.pdf`, §2.1) asks for at least 3 roles with different permissions, role-based access where different users see different features and data, profile management (view, edit, change password) and an admin dashboard (create, deactivate, change roles). It also asks for soft delete, an audit trail, logging of important events, and search, filters and paging. The proposal (2026-10-05) promises Student (own data, friends, groups), Auditor (read-only: audit log, statistics) and Admin (users, roles), with search and paging on users and the audit log, login and change logging, and a test account per role.

Today the `users` table has no role, and every account sees the same pages.

### Decided with the student (2026-10-06)

- **Separate roles:** one role per account. Staff accounts (Auditor, Admin) have no School, Groups or Friends. The student keeps their own Student account and uses a separate account as Admin.
- **The audit log records accounts and data changes:** logins, account changes, Admin actions, and every change a student makes in School and Social. Not page views, not syncs.
- **Approach A:** a `role` column; all access rules in one list; Admin actions check the role a second time; every page load re-reads the account. Not a roles-and-permissions table (approach B), not checks inside each page (C).
- **Three stages:** 1 Roles and profile, 2 the Users page, 3 Audit log and statistics.
- **Auditors see shortened emails** (`v•••@gmail.com`), Admins full ones.
- **Audit lines name the record, never its content:** "Created an event · event #57", not the event's title.
- **The first Admin** comes from a `.env` setting, `SITE_ADMIN_EMAIL`.
- **Admin-set passwords** are made up by the site, shown once, and must be replaced at the next login.

### Not in scope

- Login rate limiting, CSP and other security headers, the JSON API (`/api/v1`) and its docs
- Sending emails: no "forgot password" email (an Admin sets a temporary password instead), no email verification
- Demo data and the test accounts themselves: made by hand on the Users page or by the site-wide seed script, decided separately
- Logging in as another user; editing what a role may do; deleting accounts for good
- Exporting or cleaning up the audit log; a chart library
- Group roles (Leader, Sub-leader, Member), which are Social's stage 2
- The phone hamburger menu

---

## 2. How it fits together

```
Browser ─▶ Caddy ─▶ the site
  every page:  AccountCheck ─ re-reads the account: deactivated → logged out; new role, name or password → session follows
               access list  ─ which roles may open which addresses; otherwise the 403 page
                 Student            /school/**, /social/**                  (as now)
                 Admin              /admin/users/**                          (stage 2)
                 Auditor, Admin     /admin/audit-log/**, /admin/statistics/** (stage 3)
                 any logged-in role /, /account/**, /auth/logout

Laptop ─▶ /api/school/sync/** ─▶ DeviceKeys: the key's owner must be an active Student

auth, admin, School, Social ─▶ AuditLog.record(…) ─▶ audit_log             (stage 3)
School, Social ─▶ AccountColumn, StatisticsSource beans ─▶ the admin pages  (they never read module tables)
```

| Package | What it gets |
|---|---|
| `auth` | `Role`; `User`'s new columns; the role in `AppUser`; the login checks; `AccountCheck`; `FirstAdmin`; the Profile and Password pages (`/account`) |
| `core` | the access list (`SecurityConfig`); the 403 page; the menu per role (`Navigation`); `AuditLog` and its actions; the `AccountColumn`, `StatisticsSource` and `HomeLine` interfaces |
| `admin` (new) | the Users, Audit log and Statistics pages (`/admin/…`) |
| `main` | the home page per role |
| `school`, `social` | the active-Student rules (laptops, Friends); audit calls; their numbers for Statistics; School's laptop count |

**Module 0 is "Site":** site-wide tables (`users`, `audit_log`) have no prefix, and their migrations are named `V<date>_0_<number>__<what>.sql`. `MigrationNamingTest` accepts 0, 1 and 2. README rule 1 adds the site-wide pages (`/account`, `/admin`) and tables; rule 3 says the admin pages read every account but only account fields; rule 5 lists module 0.

---

## 3. The data

### 3.1 users (stage 1)

```sql
ALTER TABLE users ADD COLUMN role VARCHAR(7) NOT NULL DEFAULT 'student';
ALTER TABLE users ADD COLUMN created_by INT NULL;          -- the Admin who made it; NULL = registered themselves
ALTER TABLE users ADD COLUMN updated_at DATETIME NULL;     -- NOT NULL below, once filled in
ALTER TABLE users ADD COLUMN updated_by INT NULL;          -- who made the last change; NULL = the site, or none since
ALTER TABLE users ADD COLUMN deactivated_at DATETIME NULL; -- soft delete; NULL = active
ALTER TABLE users ADD COLUMN deactivated_by INT NULL;
ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL;
ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET updated_at = created_at;
ALTER TABLE users MODIFY updated_at DATETIME NOT NULL;
ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('student', 'auditor', 'admin'));
ALTER TABLE users ADD CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL;
ALTER TABLE users ADD CONSTRAINT fk_users_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL;
ALTER TABLE users ADD CONSTRAINT fk_users_deactivated_by
    FOREIGN KEY (deactivated_by) REFERENCES users (id) ON DELETE SET NULL;
CREATE INDEX ix_users_role ON users (role);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE INDEX ix_users_last_login_at ON users (last_login_at);
```

- Every account on the live site becomes a Student; nothing else changes for them.
- **Active** means `deactivated_at IS NULL`. An **active Student** is an active account with role `student`.
- `updated_at` / `updated_by` change with the name, email, role, password or status.
- Only `role` has a CHECK: MySQL refuses a CHECK on a column whose foreign key has an ON DELETE action, so "deactivated_by is set when deactivated_at is" stays in the code.
- No page deletes accounts. If a row is ever deleted by hand, the `…_by` columns pointing at it become NULL.

### 3.2 audit_log (stage 3)

```sql
CREATE TABLE audit_log (
    id BIGINT NOT NULL AUTO_INCREMENT,
    created_at DATETIME NOT NULL,       -- UTC
    actor_id INT NULL,                  -- who did it; NULL for a failed login (nobody is logged in) or the site itself
    actor_email VARCHAR(255) NULL,      -- their email then; for a failed login, what was typed (only if it has an @)
    actor_role VARCHAR(7) NULL,         -- their role then
    action VARCHAR(40) NOT NULL,        -- e.g. account.login, admin.role_changed, school.event_deleted (§7.1)
    result VARCHAR(7) NOT NULL,         -- ok / failed / refused
    target_type VARCHAR(10) NULL,       -- user / laptop / event / mail / friendship
    target_id VARCHAR(64) NULL,         -- the record's id; text, because a mail's key is text
    detail VARCHAR(200) NULL,           -- e.g. "Student → Auditor", "name, email", "wrong password"
    ip VARCHAR(45) NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_audit_log_result CHECK (result IN ('ok', 'failed', 'refused')),
    CONSTRAINT ck_audit_log_role CHECK (actor_role IS NULL OR actor_role IN ('student', 'auditor', 'admin')),
    CONSTRAINT ck_audit_log_target
        CHECK (target_type IS NULL OR target_type IN ('user', 'laptop', 'event', 'mail', 'friendship')),
    CONSTRAINT fk_audit_log_actor FOREIGN KEY (actor_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);
CREATE INDEX ix_audit_log_actor_created ON audit_log (actor_id, created_at);
CREATE INDEX ix_audit_log_action_created ON audit_log (action, created_at);
```

- **Lines are only added.** No page edits or deletes one, not even an Admin's.
- `actor_email` and `actor_role` copy what was true at that moment, on purpose: the line must still say who did it after that person changes their email or role. This is the one place the design isn't normalized, and the report says why.
- `action` has no CHECK: the list grows with each module (Groups stages add theirs), and the code keeps it as one Java enum.

### 3.3 School's index (stage 3)

```sql
CREATE INDEX ix_school_sync_runs_started_at ON school_sync_runs (started_at);
```

A module 1 migration, so Statistics can count the last 24 hours of syncs across all students quickly.

### 3.4 What this adds for the course

Three roles with different features and data; profile management; an admin dashboard that creates, edits, deactivates and changes roles; soft delete and audit columns on `users`; an append-only audit trail of logins, data changes and refused pages (time, user, action, result); CHECK constraints on roles, results and record kinds; search, six filters, sort with "then by", page sizes and "Showing …" counts on Users and the Audit log.

---

## 4. Roles and access (stage 1)

### 4.1 What each role sees

| | Student | Auditor | Admin |
|---|---|---|---|
| Menu | School · Groups · Friends | Audit log · Statistics | Users · Audit log · Statistics |
| Home page | the module cards, as now | a card per page | a card per page |
| School and Social pages | ✓ | 403 | 403 |
| Laptop sync | ✓ | key refused | key refused |
| Users | 403 | 403 | ✓ |
| Audit log, Statistics | 403 | ✓ read-only | ✓ read-only |
| Profile, Password, Log out | ✓ | ✓ | ✓ |

- **Staff never see a student's own data:** no timetable, exams, tuition, mail, courses, events, friends or groups. They see only account details (name, email, role, status, dates, number of laptops) and totals.
- **Auditors see shortened emails:** the first character, `•••`, then the domain (`v•••@gmail.com`). Admins see them in full.
- Registering always makes a Student. Staff accounts are made by an Admin (§6.2), or by an Admin changing a Student's role.

### 4.2 The access list

One list in `SecurityConfig`, read top to bottom:

| Addresses | Who |
|---|---|
| `/auth/login`, `/auth/register`, `/css/**`, `/js/**`, `/error` | anyone |
| `/school/**`, `/social/**` | Student |
| `/admin/users/**` | Admin |
| `/admin/audit-log/**`, `/admin/statistics/**` | Auditor, Admin |
| `/`, `/account/**`, `/auth/logout` | any logged-in role |
| `/api/school/sync/**` | the laptop: its own filter chain, as now (§4.6) |
| anything else | any logged-in role, so a mistyped address still says "Page not found" |

- **A test keeps the list complete:** it walks every address the site maps and fails if one falls through to "anything else". A new module therefore can't be left open to every role by mistake.
- **The second check:** the Users actions (stage 2) carry `@PreAuthorize("hasRole('ADMIN')")`, and the audit log and statistics readers `hasAnyRole('AUDITOR', 'ADMIN')`, with method security switched on.
- Roles reach Spring Security as `ROLE_STUDENT`, `ROLE_AUDITOR` and `ROLE_ADMIN`, from `AppUser`, which now carries the role.

### 4.3 Menu and home page

- `Navigation` keeps one fixed list per role: Student: School, Groups, Friends. Auditor: Audit log, Statistics. Admin: Users, Audit log, Statistics. A page not built yet shows "coming soon", as now; in stage 1 that is all three staff pages.
- The admin package registers its pages as `NavModule`s (Users → `/admin/users`, Audit log → `/admin/audit-log`, Statistics → `/admin/statistics`) as it builds them.
- **Profile · Log out** sit at the right of the menu for every role.
- **Home page:** Students see the module cards, as now. Staff see a card per menu page, each with one line from a small `HomeLine` bean next to its `NavModule` (like `NavCount`):
  - Users (stage 2): "156 users · 3 deactivated · 5 new this week"
  - Audit log (stage 3): "42 lines today · 3 failed logins"
  - Statistics (stage 3): "156 users · 12 laptops synced today"

### 4.4 Every page load re-reads the account

`AccountCheck` runs on every page after the session is loaded and before the access list, with one lookup by id. It doesn't run for the sync API (no session) or for static files.

| The account now | What happens |
|---|---|
| deactivated | session ended; login page with "This account has been deactivated. Ask the site's admin to turn it back on." |
| gone (deleted by hand) | session ended; the plain login page |
| a different password than at login | session ended; login page with "Your password was changed. Log in again." |
| a different role, name or email | the session's account is updated, so the menu and the access list follow at once |
| the same | nothing |

The page where someone changes their own password stores the new password in their session, so that session stays logged in.

### 4.5 The 403 page

`error.html` explains 403 as well as 404:

- **Not allowed:** "You can't open this page." Then, by role: "Your account is a student account: it can open School, Groups and Friends." / "Your account is an Auditor account: it can open the Audit log and Statistics." / "Your account is an Admin account: it can open Users, the Audit log and Statistics." Then "Back to the start page".
- **The Connect page** (`/school/devices/connect`) for a staff account: "Only student accounts can connect a laptop. Log out and log in with your student account.", with a Log out button.
- **A missing or expired security code (CSRF):** "This form expired. Go back, reload the page and try again."
- Groups (Social's stage 2) adds its own reasons to the same page, such as "Only the group's Leader can do that."

### 4.6 The laptop

- `DeviceKeys.checkIn` accepts a key only when its owner is an active Student. Otherwise the laptop gets the same 401 `invalid_device_key` as for a cancelled key and shows its usual message.
- The key isn't cancelled: when the account is an active Student again, the laptop syncs again without reconnecting.
- A connect code traded in after its account was deactivated gives a key that is refused the first time it's used.
- No agent change, no new laptop release.

---

## 5. Accounts (stage 1; temporary passwords in stage 2)

### 5.1 Logging in

- Wrong password or unknown email: "Email or password is incorrect.", as now.
- Right password, deactivated account: "This account has been deactivated. Ask the site's admin to turn it back on." Spring Security normally checks the account's status *before* the password; the login provider moves that check after it, so the login page never shows which emails have accounts.
- A successful login sets `last_login_at`. Registering counts as the first login.

### 5.2 Accounts that aren't active Students, as other students see them

A deactivated account, or one with a staff role:

- doesn't appear in Find people, friend lists, "Requests for you", "Requests you sent" or the Friends count;
- is "not found" (404) for every friend button, like an unknown person.

Its rows stay, and everything comes back when it is an active Student again. Groups (Social's stage 2) applies the same rule to its members, Leaders and invites, in its own plan.

### 5.3 The first Admin

- **The setting:** `SITE_ADMIN_EMAIL` in `.env`. On the server, `deploy/server/compose.yaml` passes it to the site (`SITE_ADMIN_EMAIL: ${SITE_ADMIN_EMAIL:-}`).
- **At startup, after the migrations:** if the site has no active Admin and the setting names an existing account, that account becomes an active Admin, and the log says "Made admin@… an Admin (SITE_ADMIN_EMAIL)". From stage 3 an audit line records it too, done by "the site".
- An empty setting does nothing. An unknown email logs a warning. If an active Admin already exists, the setting does nothing, so it can never undo an Admin's decisions. It also serves as the way back if every Admin is ever lost.
- **On the live site:** register the admin account the usual way, add the setting to `deploy/server/.env`, run `update.sh`. The README lists these steps. Because roles are separate, this is a new account, not the student's own.

### 5.4 Profile (`/account`, every role)

Shows the display name, email, role, member since and last login (Vietnam time). The form:

| Field | Rules and messages |
|---|---|
| Display name | as register: "This field is required." / "Field cannot be longer than 100 characters." |
| Email | as register: "Invalid email address." / "Field cannot be longer than 255 characters." / "This email is already registered." |
| Current password | only when the email changes: "Enter your current password to change your email." / "Current password is incorrect." |

Saving sets `updated_at` and `updated_by` and returns with "Saved your profile."; the session shows the new name at once.

### 5.5 Password (`/account/password`, every role)

| Field | Rules and messages |
|---|---|
| Current password | "Current password is incorrect." |
| New password | as register: "Field must be between 8 and 128 characters long."; "Choose a password different from your current one." |
| Confirm | "Passwords don't match." |

Saving stores the new hash (scrypt, as now), clears `must_change_password`, sets `updated_at` and `updated_by`, gives the session a new id and returns with "Password changed." Other sessions of the account are logged out on their next click (§4.4).

### 5.6 Temporary passwords (stage 2)

- **Made by the site:** 12 random characters from letters and digits without look-alikes (no 0, O, 1, l, I), shown in three groups of four, e.g. `K7mq-p2Xz-9wRt`.
- **Shown once,** in the message on the user's page. That page is sent with `Cache-Control: no-store`, as the Devices page does for a new key.
- **Sets `must_change_password`.** After login, every page leads to `/account/password` with "Choose your own password to continue." until it's done. Log out, the Password page, the error page and static files still work.

---

## 6. The Users page (stage 2, Admin only)

### 6.1 The list (`/admin/users`)

Every field is a URL parameter, so a search can be bookmarked and the back button works.

- **Search** (`q`): split into words; every word must appear in the name or the email (case ignored; accents ignored on MySQL, through its collation).
- **Filters:**
  1. Role: any, Student, Auditor, Admin.
  2. Status: any, active, deactivated.
  3. Registered from (a date, Vietnam time; that whole day included).
  4. Registered to (that whole day included).
  5. Last login: any, in the last 7 days, in the last 30 days, more than 30 days ago, never.
  6. Added by: any, registered themselves, made by an admin.
- **Sort by** name (A–Z), email (A–Z), role (Admin, Auditor, Student), registered (newest first) or last login (latest first, "never" last), **then by** a second of the same. Default: registered, then name; ties last by id.
- **Page size** 10 / 20 / 50 / 100 (default 20; anything else counts as 20), numbered pages with Previous and Next, and "Showing 21–40 of 156 users". Nothing found: "No users match." with a "Clear all filters" link.
- **Columns:** Name (links to the user's page), Email, Role, Status ("Active", or "Deactivated 05/10"), Registered, Last login ("Never"), Laptops (devices whose key isn't cancelled).
- Filtering, sorting, counting and paging happen in the database: one JPA query built from the filters. The Laptops column comes from School's `AccountColumn` bean, asked only about the rows on the page.
- A **New user** button.

### 6.2 New user (`/admin/users/new`)

- **Fields:** email and display name (the register rules and messages, including "This email is already registered."), and role (default Student).
- **Saving** creates the account with a temporary password (§5.6), `created_by` the Admin, and opens the user's page: "Account created. Temporary password: K7mq-p2Xz-9wRt. Give it to An; it works until they choose their own."

### 6.3 A user's page (`/admin/users/{id}`)

- **Details:** name, email, role, status ("Deactivated on 05/10 by Admin"), registered (date, and "by Admin" or "registered themselves"), last changed (date and by whom), last login, laptops, and "Must choose a new password" while that is set.
- **Recent activity** (stage 3): the last 20 lines by them or about their account (§7.1), and a "See all" link to the Audit log with "Only An".
- An unknown id is 404.

| Button | Does | Then |
|---|---|---|
| Edit (`/admin/users/{id}/edit`) | name and email, Profile's rules, no password needed | "Saved An's account." |
| Change role | a role list and a button | "An is now an Auditor." |
| Deactivate | asks "Deactivate An? They can't log in until an admin turns the account back on." | "Deactivated An." |
| Reactivate | | "Reactivated An." |
| Set a temporary password | asks "Set a temporary password for An? They'll be logged out everywhere." | the password, once (§5.6) |

### 6.4 Rules

- **Not on yourself:** your own user's page shows the details, no buttons, and "This is you. Use Profile to change your name, email or password." The server also refuses: "You can't change your own role." / "You can't deactivate your own account."
- **At least one active Admin:** you can't act on yourself, so the Admin acting always remains. Changing an Admin's role or deactivating an Admin also locks the active Admins' rows (`PESSIMISTIC_WRITE`) and refuses if no other active Admin would remain ("The site needs at least one active Admin."). That only happens when two Admins act on each other at the same moment.
- **Out-of-date clicks** return with a message, not an error page: "An is already deactivated." / "An is already active." / "An is already an Auditor."
- **A Student moved to a staff role** keeps their School and Social data, hidden. Their laptops are refused (§4.6), and other students no longer see them (§5.2). Making them a Student again brings it all back.
- An Admin can't see a student's own data and can't log in as anyone else.

---

## 7. The audit log (stage 3)

### 7.1 What is written

One line per action that changed something. A button that changes nothing (pressed twice, or from an out-of-date page) writes no line.

| Area | Action (code → plain words on the page) | Record |
|---|---|---|
| Accounts | `account.login` Logged in · `account.login_failed` Login failed (detail: wrong password / unknown email / deactivated) · `account.logout` Logged out · `account.registered` Registered · `account.profile_changed` Changed their profile (detail: name, email) · `account.password_changed` Changed their password · `account.refused` Page refused (detail: the address, without its query) | none; a failed login: the account it tried (user), if the email has one |
| Admin | `admin.user_created` Created an account (detail: the role) · `admin.user_edited` Edited an account (detail: name, email) · `admin.role_changed` Changed a role (detail: "Student → Auditor") · `admin.user_deactivated` Deactivated an account · `admin.user_reactivated` Reactivated an account · `admin.temporary_password` Set a temporary password · `admin.made_admin` Made Admin by SITE_ADMIN_EMAIL (no actor) | user |
| School | `school.laptop_added` Added a laptop · `school.laptop_connected` Connected a laptop · `school.laptop_renamed` Renamed a laptop · `school.laptop_removed` Removed a laptop | laptop |
| School | `school.event_created` Created an event · `school.event_edited` Edited an event · `school.event_deleted` Deleted an event · `school.event_day_skipped` Skipped a day · `school.event_skip_undone` Undid a skipped day | event |
| School | `school.mail_moved` Changed a mail's categories · `school.mail_joined` Joined a mail's event · `school.mail_left` Left a mail's event · `school.mail_done` Marked a mail done · `school.mail_undone` Marked a mail not done · `school.mail_automatic` Put a mail back to automatic · `school.mail_settings` Changed mailbox settings (detail: auto-Done on / off) | mail (the last one: none) |
| Social | `social.friend_requested` Sent a friend request · `social.friend_accepted` Accepted a friend request · `social.friend_declined` Declined a friend request · `social.friend_cancelled` Cancelled a friend request · `social.friend_removed` Removed a friend | friendship (the row's id, never the other student, so staff can't tell who is friends with whom) |

- **Not logged:** opening pages; opening a mail (`/opened` only marks it read); Sync now; the laptop's syncs, whose results show on the Devices page.
- **The detail never holds a student's content:** no titles, subjects, places, notes, device names or other people's names. Only account facts (a role, which fields changed) and failure reasons.
- `school.laptop_connected` is the Connect trade-in, which has no session: its actor is the account the connect code belongs to.
- **A failed login** has no actor (nobody proved who they are): Who shows the typed email, and the record is the account it tried, if any.
- **Lines about a person** are the ones they did and the ones whose record is their account (an Admin's actions on it, failed logins on it). The "One person" filter and a user's Recent activity show both.

### 7.2 Writing a line

- `AuditLog.record(action, result, target, detail)` in `core` takes the actor (id, email, role) from the logged-in account and the IP from the request. It joins the caller's transaction, so a change that rolls back leaves no line and a change that happened always has one.
- Logins and failed logins come from Spring Security's authentication events, logouts from the logout handler, refused pages from the 403 handler. Those lines are written in a transaction of their own. An expired form (CSRF) writes no line.
- **The IP** is `request.getRemoteAddr()`. On the server this is the visitor's address: Caddy sets `X-Forwarded-For`, dropping one sent by the visitor (its default since Caddy 2.5; the plan checks it), and `SERVER_FORWARD_HEADERS_STRATEGY=framework` (already in `compose.yaml`) makes the site read it. Only Caddy can reach the site.
- **A failed login's typed email** is kept only if it contains "@", cut to 255 characters. People sometimes type their password into the email box.

### 7.3 The page (`/admin/audit-log`, Auditor and Admin, read-only)

Every field is a URL parameter, as on Users.

- **Search** (`q`): split into words; every word must appear in who (the line's email or the account's current name) or in the detail.
- **Filters:**
  1. Area and action: one list grouped by area (Accounts, Admin, School, Social); picking an area means all its actions.
  2. Result: any, ok, failed, refused.
  3. Role (of the person, then): any, Student, Auditor, Admin, none.
  4. From (a date, Vietnam time; that whole day included).
  5. To (that whole day included).
  6. One person (`user=88`): lines by them or about their account (§7.1), set by the "See all" link on a user's page and shown as "Only An ×".
- **Sort by** time (newest first), who (A–Z by name, lines without an account last), action or result, **then by** a second of the same. Default: time; ties last by id, newest first.
- **Paging** as on Users: 10 / 20 / 50 / 100 (default 20), "Showing 1–20 of 3,412 lines"; nothing found: "No lines match." with "Clear all filters".
- **Columns:** Time (Vietnam time, 06/10/2026 14:05:09), Who (name and email; for a failed login, the typed email; "The site" for `admin.made_admin`), Role, Action (plain words), Result, Record ("user #88", "laptop #12", "event #57", "mail 3f2a…", "friendship #31"), Detail, IP.
- **Admins** see full emails, and user records link to the user's page. **Auditors** see shortened emails (§4.1) and no links.
- Filtering, sorting, counting and paging happen in the database.

---

## 8. Statistics (stage 3, Auditor and Admin, read-only)

Totals only: no names, no student's own data.

| Group | Numbers |
|---|---|
| Accounts | users by role; active and deactivated; new accounts per week (Monday to Sunday, Vietnam time) for the last 8 weeks |
| Logins (from the audit log) | per day for the last 14 days: logins and failed logins; pages refused per day |
| School | laptops connected (keys not cancelled, owner an active Student); laptops seen in the last 24 hours; syncs started in the last 24 hours by result (success, partial, failed) |
| Social | friendships; friend requests waiting (Groups stages add groups and events) |

- **Each module supplies its own group** through a `StatisticsSource` bean (in `core`, like `NavCount`): a title, named numbers and per-day rows. The page shows the site's groups first, then the modules' in menu order. The admin package never reads School's or Social's tables.
- **Per-day rows** are table rows with the number and an HTML `<meter>` bar scaled to the table's largest number. No chart library, no inline styles or scripts, so a strict CSP later still works.
- Numbers are counted when the page opens; nothing is stored.

---

## 9. Errors and security

- **Every rule is checked on the server.** Hiding a button is never the only protection.
- **404:** an unknown user id on the admin pages; a friend button on someone who isn't an active Student.
- **403:** §4.5. Every POST needs its security code (CSRF), as now.
- **Forms** use browser hints (`required`, `maxlength`, `type="email"`) for quick feedback; the server checks everything; mistakes show under their field and the form keeps what was typed (passwords excepted). Deactivate and Set a temporary password ask first (`confirm.js`, as Devices does).
- **Out-of-date clicks** go back with a message (§6.4).
- **Passwords**, temporary ones included, are stored only as scrypt hashes, as now. A temporary password is made with `SecureRandom` and shown once.
- **Login** never shows which emails have accounts (§5.1). The login page and the audit log keep the reasons apart: the person sees one message for a wrong password or an unknown email; the Auditor sees which it was.
- **Sessions:** a new session id after login and after a password change; role changes, deactivation and password changes reach other sessions on their next click (§4.4).

---

## 10. Testing

As the existing tests: JUnit 5, MockMvc, H2 in MySQL mode, and once on MySQL in GitHub's checks.

- **Access:** each role (and no login) against each area: allowed, 403, or the login page. The access-list test (§4.2) walks every mapped address.
- **Menu and home page** for each role; "coming soon" for staff pages not built yet.
- **Deactivation:** login refused after the right password, the usual message after a wrong one; a logged-in session ends on its next click; the laptop's key is refused; the account vanishes from Find people, friend lists, requests and the Friends count; reactivating brings it all back.
- **Role changes:** take effect on the next click; a staff account's laptop is refused; the Connect page's message for staff.
- **First Admin:** with no active Admin the named account is promoted; with one, nothing happens; an unknown email logs a warning; an empty setting does nothing.
- **Profile and Password:** every field rule; a taken email; the current password needed for an email change; a wrong current password; the same password again; other sessions logged out, this one kept.
- **Users page:** search; every filter; every sort and "then by"; each page size and the "Showing" line; New user and its temporary password (shown once, `no-store`, forced change); Edit; Change role; Deactivate and Reactivate; the rules about yourself; two Admins acting on each other at the same moment (a race test, like `FriendsRaceTest`); out-of-date clicks; `@PreAuthorize` refusing a non-Admin call to the service.
- **Audit log:** every action in §7.1 writes exactly one line with the right actor, action, result, record and detail; a change that rolls back writes none; a button that changes nothing writes none; no title or name from a student's data appears in any detail; a failed login's typed text without "@" isn't kept; Auditors see shortened emails and no links, Admins full emails and links; every filter, sort and page size.
- **Statistics:** each number against known test data; no name or email on the page.
- **Migrations:** the new columns and table exist (`MigrationTest`); the CHECKs refuse a bad role, result or record kind on whichever database runs the tests; `MigrationNamingTest` accepts module 0.

---

## 11. Risks

- **The course requires a test account per role on the live site.** The test Admin can see real students' emails and deactivate them. Its password goes only in the report, is strong, and is changed after grading. Demo data stays a separate decision.
- **Groups (Social's stage 2)** must handle accounts that aren't active Students, such as a group Leader who is deactivated or made an Auditor. Its plan covers that (§5.2).
- **The audit log is never cleaned up.** At today's use (a few hundred lines a day) that is fine for years.
- **A Student moved to staff** sees "rejected this device key" on their laptop; the message mentions the Devices page, which is a little misleading, but it avoids a new laptop release.
- **One extra lookup per page** (§4.4), by primary key. Fine at this size.
- **H2 and MySQL differ** on `ALTER TABLE … MODIFY` and on CHECKs (H2 2.4.240 loses a CHECK's IN list once its connection closes; the test settings already keep connections open). The plan tries the migration on both first.
- **Existing tests** log in with accounts that the account check now re-reads from the database: test accounts must be saved rows (most already are). The plan updates the rest.

---

## 12. Build order

Three stages, each with its own plan and merge into `main`:

1. **Roles and profile:** the `users` migration (module 0); `Role` and the role in `AppUser`; the login provider's checks (§5.1) and `last_login_at`; `AccountCheck`; the access list, its test and method security; the menu and home page per role, with Profile in the menu; the 403 page (roles, Connect, expired forms); the active-Student rules for laptops and Friends; `SITE_ADMIN_EMAIL` (and `compose.yaml`, README); the Profile and Password pages; `MigrationNamingTest` and README rules 1, 3 and 5.
2. **The Users page:** the list (search, filters, sort, paging); New user; a user's page; Edit, Change role, Deactivate / Reactivate, Set a temporary password; temporary passwords and the forced change (§5.6); School's `AccountColumn` (laptops); `HomeLine` and the Users card's line.
3. **Audit log and statistics:** the `audit_log` migration (module 0) and School's index (module 1); `AuditLog` and every action in §7.1, including login, logout and refused-page events; the Audit log page; Recent activity on a user's page; `StatisticsSource` and the Statistics page, with School's and Social's groups; the Audit log and Statistics cards' lines.
