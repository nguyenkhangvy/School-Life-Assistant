# School-Life-Assistant: friends, groups and group events

**Date:** 2026-10-06
**Scope:** a new Social module. Students add friends by display name. Anyone can create a club or group, find groups, ask to join (a Leader or Sub-leader approves) or be invited by a friend. Leaders and Sub-leaders publish events, once or repeating; members answer Going or Not going, and an event they are going to shows on their School Timetable.
**Owner:** Nguyen Khang Vy
**Status:** Draft, waiting for review
**Builds on:** [Java website](2026-09-26-java-website-design.md) (modules, menu, rules for the Java code), [My events](2026-09-30-my-events-design.md) (repeat rules, the event form, conflict marks) and [Mailbox events](2026-09-28-mailbox-events-design.md) (the conflict mark on Join). Everything there stays the same unless this document says otherwise.

---

## 1. Goal

The course proposal promises friends, groups and group events: "In a group: Leader and Sub-leader publish events, Member accepts", with invite approval, a clash check per member, and accepting adds the event to the timetable. Today the site holds only each student's own data, so nothing is shared between students.

### Decided with the student (2026-10-06)

- **Groups are clubs and big groups:** every group is public and can be found; people ask to join and a Leader or Sub-leader approves. Groups can be large.
- **Friends exist to invite people into groups.** No other friend features (no seeing friends' timetables, no friend lists on group pages).
- **People are found by display name.** Results show the name only, never an email.
- **Any member can invite a friend.** Accepting an invite from a Leader or Sub-leader joins at once; accepting a plain member's invite waits for approval like a join request.
- **Group events repeat like My events** (once, every N days, every N weeks on chosen days, every N months). A member answers for the whole series.
- **The Leader's clash check shows counts only:** "45 free · 12 busy" for each session, never names or details. Each member sees their own clashes in full.
- **Course requirements included from the start:** search, filters, sorting and paging on Find groups; soft delete of groups and group events; audit columns and a History per group.
- **Approach A:** a separate Social module (package `social`, tables `social_…`, URLs `/social/…`, migration module 2). There is still **one Timetable**, School's: the Social module adds the group events a student is going to through a small interface, so School code never imports Social code.

### Not in scope

- Site roles (Student, Auditor, Admin) and admin pages; restoring a deleted group (the rows stay for an admin page later)
- Emails or other notifications; the menu counts and "Waiting for you" are the only ones
- Demo data (100+ rows) and test accounts: they come with a site-wide seed script, decided separately, because the live site has real students
- A JSON API, chat, group pictures, skipped days for group events
- The phone hamburger menu (a site-wide layout change, UI/UX)

---

## 2. How it fits together

```
Top menu: School · Groups (3) · Friends (2) · Log out
                │                  │
                │                  └─ /social/friends: find people, requests, your friends
                └─ /social/groups: Waiting for you + your groups
                     ├─ /social/groups/find: every group, search / filters / sort / paging
                     ├─ /social/groups/new
                     └─ /social/groups/{id}: details, events, your button
                          ├─ /members: members, requests, invites, Invite friends, roles
                          ├─ /history: every change (Leaders and Sub-leaders)
                          └─ /events/new, /events/{eventId}, /events/{eventId}/edit

School's Schedule.itemsBetween ── classes, exams, joined events, own events
     + TimetableSource beans ──── Social: the sessions of group events the student is Going to
     ├─ Timetable calendar, Overview Today / Tomorrow
     └─ conflict marks (My events' Check, Mailbox Join, ⚠ on the calendar)
```

---

## 3. The data

Six tables, all `social_…`, in three migrations, one per build stage (§10). Module 2 is Social: names are `V<date>_2_<number>__<what>.sql`. `MigrationNamingTest` accepts modules 1 and 2, and the README's rule 5 says so. The `users` table doesn't change.

### 3.1 Friendships (stage 1)

```sql
CREATE TABLE social_friendships (
    id INT NOT NULL AUTO_INCREMENT,
    user_low_id INT NOT NULL,          -- the smaller of the two user ids
    user_high_id INT NOT NULL,         -- the larger
    requested_by_id INT NOT NULL,      -- who sent the request: one of the two
    status VARCHAR(8) NOT NULL,        -- pending / accepted
    created_at DATETIME NOT NULL,      -- sent at (UTC)
    accepted_at DATETIME NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_social_friendships_pair UNIQUE (user_low_id, user_high_id),
    CONSTRAINT ck_social_friendships_status CHECK (status IN ('pending', 'accepted')),
    CONSTRAINT ck_social_friendships_accepted CHECK ((status = 'accepted') = (accepted_at IS NOT NULL)),
    CONSTRAINT fk_social_friendships_low FOREIGN KEY (user_low_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_friendships_high FOREIGN KEY (user_high_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_friendships_by FOREIGN KEY (requested_by_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_social_friendships_high ON social_friendships (user_high_id);
```

One row per pair, whichever way the request went. Declining, cancelling and removing delete the row.

MySQL refuses a CHECK on a column whose foreign key has an ON DELETE action, so "smaller id first" and "requested_by is one of the two" are kept by the entity's constructor, not by CHECKs.

### 3.2 Groups, members and history (stage 2)

```sql
CREATE TABLE social_groups (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(500) NULL,
    category VARCHAR(10) NOT NULL,     -- academic / sports / arts / volunteer / tech / culture / other
    place VARCHAR(100) NULL,           -- where it usually meets
    max_members INT NULL,              -- empty: no limit
    created_by INT NULL,
    created_at DATETIME NOT NULL,
    updated_by INT NULL,
    updated_at DATETIME NOT NULL,
    deleted_by INT NULL,
    deleted_at DATETIME NULL,          -- soft delete
    live_name VARCHAR(80) GENERATED ALWAYS AS (CASE WHEN deleted_at IS NULL THEN name END),
    PRIMARY KEY (id),
    CONSTRAINT uq_social_groups_live_name UNIQUE (live_name),
    CONSTRAINT ck_social_groups_category
        CHECK (category IN ('academic', 'sports', 'arts', 'volunteer', 'tech', 'culture', 'other')),
    CONSTRAINT ck_social_groups_max CHECK (max_members IS NULL OR max_members BETWEEN 2 AND 1000),
    CONSTRAINT fk_social_groups_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_social_groups_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_social_groups_deleted_by FOREIGN KEY (deleted_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_social_groups_category ON social_groups (category);
CREATE INDEX ix_social_groups_created_at ON social_groups (created_at);

CREATE TABLE social_group_members (
    id INT NOT NULL AUTO_INCREMENT,
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    status VARCHAR(9) NOT NULL,        -- invited / requested / member
    role VARCHAR(9) NOT NULL,          -- leader / subleader / member
    invited_by INT NULL,               -- who invited them, if they were invited
    created_at DATETIME NOT NULL,      -- asked or invited at
    joined_at DATETIME NULL,           -- became a member at
    PRIMARY KEY (id),
    CONSTRAINT uq_social_group_members UNIQUE (group_id, user_id),
    CONSTRAINT ck_social_group_members_status CHECK (status IN ('invited', 'requested', 'member')),
    CONSTRAINT ck_social_group_members_role CHECK (role IN ('leader', 'subleader', 'member')),
    CONSTRAINT ck_social_group_members_role_needs_member CHECK (status = 'member' OR role = 'member'),
    CONSTRAINT ck_social_group_members_joined CHECK ((status = 'member') = (joined_at IS NOT NULL)),
    CONSTRAINT fk_social_group_members_group FOREIGN KEY (group_id) REFERENCES social_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_group_members_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_group_members_invited_by FOREIGN KEY (invited_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_social_group_members_user_status ON social_group_members (user_id, status);
CREATE INDEX ix_social_group_members_group_status ON social_group_members (group_id, status);

CREATE TABLE social_group_history (
    id INT NOT NULL AUTO_INCREMENT,
    group_id INT NOT NULL,
    actor_id INT NULL,                 -- who did it
    subject_id INT NULL,               -- whom it was about
    action VARCHAR(20) NOT NULL,
    detail VARCHAR(200) NULL,          -- e.g. the new role, an event's title, "invited by An"
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_social_group_history_action CHECK (action IN ('created', 'edited', 'deleted', 'requested',
        'request_cancelled', 'approved', 'declined', 'invited', 'invite_cancelled', 'joined', 'invite_declined',
        'left', 'removed', 'role_changed', 'handed_over', 'event_published', 'event_edited', 'event_deleted')),
    CONSTRAINT fk_social_group_history_group FOREIGN KEY (group_id) REFERENCES social_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_group_history_actor FOREIGN KEY (actor_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_social_group_history_subject FOREIGN KEY (subject_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_social_group_history_group_created ON social_group_history (group_id, created_at);
```

- **One row per person per group:** a person is invited, waiting for approval, or a member; never two at once. Declining, cancelling, leaving and removal delete the row; History keeps a line about it.
- **Group names** are unique among groups that aren't deleted: the code checks first (ignoring case) and says "A group with this name already exists."; `live_name` (the name while the group is live, NULL once deleted) has a unique index as the database's backstop, so a deleted group's name can be used again.
- **One Leader per group** is kept by the code (§6), with the group's row locked while roles change.
- History's action list already holds stage 3's event actions, so stage 3 doesn't alter the CHECK.

### 3.3 Group events and answers (stage 3)

```sql
CREATE TABLE social_group_events (
    id INT NOT NULL AUTO_INCREMENT,
    group_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    place VARCHAR(100) NULL,
    notes VARCHAR(500) NULL,
    first_day DATE NOT NULL,
    last_day DATE NOT NULL,
    start_time TIME NOT NULL,          -- Vietnam wall-clock time
    end_time TIME NOT NULL,
    repeat_kind VARCHAR(6) NOT NULL,   -- once / days / weeks / months
    every_n INT NOT NULL,
    weekdays VARCHAR(20) NULL,         -- "weeks" only: ISO day numbers, e.g. "2,4"
    created_by INT NULL,
    created_at DATETIME NOT NULL,
    updated_by INT NULL,
    updated_at DATETIME NOT NULL,
    deleted_by INT NULL,
    deleted_at DATETIME NULL,          -- soft delete
    PRIMARY KEY (id),
    CONSTRAINT ck_social_group_events_time CHECK (end_time > start_time),
    CONSTRAINT ck_social_group_events_days CHECK (last_day >= first_day),
    CONSTRAINT ck_social_group_events_repeat CHECK (repeat_kind IN ('once', 'days', 'weeks', 'months')),
    CONSTRAINT ck_social_group_events_every CHECK (every_n BETWEEN 1 AND 99),
    CONSTRAINT fk_social_group_events_group FOREIGN KEY (group_id) REFERENCES social_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_group_events_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_social_group_events_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_social_group_events_deleted_by FOREIGN KEY (deleted_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_social_group_events_group_first ON social_group_events (group_id, first_day);

CREATE TABLE social_event_answers (
    id INT NOT NULL AUTO_INCREMENT,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    answer VARCHAR(9) NOT NULL,        -- going / not_going
    answered_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_social_event_answers UNIQUE (event_id, user_id),
    CONSTRAINT ck_social_event_answers_answer CHECK (answer IN ('going', 'not_going')),
    CONSTRAINT fk_social_event_answers_event FOREIGN KEY (event_id) REFERENCES social_group_events (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_event_answers_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_social_event_answers_user_answer ON social_event_answers (user_id, answer);

ALTER TABLE social_group_history ADD COLUMN event_id INT NULL;
ALTER TABLE social_group_history ADD CONSTRAINT fk_social_group_history_event
    FOREIGN KEY (event_id) REFERENCES social_group_events (id) ON DELETE SET NULL;
```

- No answer row means "not answered yet". The proposal's diagram called this table `event_invites`; it is named for what a row holds, an answer.
- The days an event happens on come from My events' `Occurrences` (same rule, same limits: at most 366 days from first to last, every 1–99). Group events have no skipped days.

### 3.4 What this adds for the course

Three junction tables (friendships: users ↔ users; group members: users ↔ groups; event answers: users ↔ group events), audit columns (created/updated/deleted by and at) on groups and group events, soft delete on both, and CHECK constraints for every fixed value and range.

---

## 4. The menu, Friends and Groups pages

### 4.1 Menu and dashboard

- `Navigation.MODULES` becomes School, Groups, Friends. The Social module registers two `NavModule`s: Groups → `/social/groups`, Friends → `/social/friends`. The dashboard shows a card for each.
- **Counts:** a module may also give a number per user (a small `NavCount` bean); the menu shows it after the label, "Groups 3", and nothing when it is 0.
  - Friends: friend requests sent to you.
  - Groups: your open invites + requests you can approve (groups where you are Leader or Sub-leader) + events waiting for your answer (§5.3).

### 4.2 Friends (`/social/friends`)

One page, four parts:

1. **Find people:** a search box (at least 2 letters, else "Type at least 2 letters."). Matches anywhere in the display name, ignoring case (and accents on MySQL, through its collation: "vy" finds "Vỹ"). Never lists yourself. 20 per page, sorted by name, "Showing 1–20 of 45 people". Each row: the name, "In 2 of your groups: Chess Club, Guitar Club" when you share groups, and one button by state: **Add friend**, **Cancel request** (you asked), **Accept** (they asked you), **Friends ✓**.
2. **Requests for you:** name, sent date, **Accept** · **Decline**.
3. **Requests you sent:** name, sent date, **Cancel**.
4. **Your friends:** name, shared groups, **Remove** (asks "Remove Binh from your friends?" first).

Empty states: "No requests." / "No friends yet. Find people above." Emails are never shown.

### 4.3 Groups

| Page | URL | Who | What it has |
|---|---|---|---|
| My groups | `/social/groups` | anyone logged in | **Waiting for you** (only when something waits): invites ("An invited you to Chess Club" · Accept · Decline); events to answer (§5.3); for Leaders and Sub-leaders "Chess Club: 3 requests to join → Review". Then **your groups**: name, your role, members, next event, by name. Then groups you asked to join, marked "Waiting for approval". Empty: "You're not in any group yet. Find groups or create one." |
| Find groups | `/social/groups/find` | anyone logged in | §7. Each row: name, category, members ("Full" at the limit), description, next event, and your button: Ask to join / Requested / Invited / Member. |
| New group | `/social/groups/new` | anyone logged in | Name, description, category, usual place, member limit. Saving makes you the Leader and opens the group. |
| A group | `/social/groups/{id}` | anyone logged in | Name, category, place, description, members (and limit), Leader's name, upcoming events (title, repeat, days, time, "23 going"). Your button: Ask to join / Cancel request / Accept · Decline / Leave. Members: link to Members. Leaders and Sub-leaders: New event, Edit, Requests (count), History. Leader: Delete. |
| Edit group | `/social/groups/{id}/edit` | Leader, Sub-leaders | The same form. |
| Members | `/social/groups/{id}/members` | members | Members (name, role, joined date; Leader first, then Sub-leaders, then by name), search by name, 20 per page. **Invite friends**: your friends who aren't a member, invited or waiting, each with Invite. Leaders and Sub-leaders also see **Requests** (name, asked date, "invited by An" when a member invited them, Approve · Decline) and **Open invites** (name, invited by, Cancel), and the role buttons (§6). |
| History | `/social/groups/{id}/history` | Leader, Sub-leaders | Newest first, 20 per page: "06/10 14:05 · Vy approved Binh's request", "Vy published "Weekly practice"". A deleted account shows as "Someone". |

**Group form checks** (shown under each field; the form keeps what was typed):
- Name: "Enter a name." / "At least 3 characters." / "At most 80 characters." / "A group with this name already exists."
- Description: "At most 500 characters." Place: "At most 100 characters."
- Category: "Choose a category." (Academic, Sports, Arts & music, Volunteering, Technology, Language & culture, Other)
- Member limit: empty, or "Enter a number from 2 to 1000." / "The limit can't be below the current 57 members."

Saving a new group adds History "created" and makes its creator the Leader (a member row with role leader); saving an edit adds "edited" (detail: what changed, e.g. "name, member limit") and shows "Saved "Chess Club".".

**Delete group** (Leader): asks "Delete Chess Club for all 57 members?", sets `deleted_at` and `deleted_by`, adds History "deleted", and goes to My groups with "Deleted "Chess Club".". A deleted group is 404 everywhere; its events leave every Timetable.

---

## 5. Group events

### 5.1 The event form

`/social/groups/{id}/events/new` and `/social/groups/{id}/events/{eventId}/edit`, for the Leader and Sub-leaders.

- The same fields, limits and messages as My events' form (My events §4.1); the Social module reuses its checks. Place starts as the group's usual place.
- One more rule: "The first day can't be before today." for a new event, and for an edited event whose first day changed. An edited event may keep a first day that has passed.

| Button | Does |
|---|---|
| **Check members' times** | Checks the form; with mistakes, shows them. Otherwise shows the form again with one line per session: "Tue 07/10 19:00–21:00 · 45 free · 12 busy" (or "· all 57 free"). Saves nothing. |
| **Publish** (new) / **Save** (edit) | Checks the form, saves, adds History "event_published" / "event_edited" (detail: the title), and goes to the group page: "Published "Weekly practice". 57 members can now answer." / "Saved "Weekly practice"." |
| **Delete** (edit only) | Asks "Delete this event for all members?", soft-deletes it, adds History "event_deleted", and goes to the group page: "Deleted "Weekly practice"." |

**Busy** (members' times): for each member (status member, Leader and Sub-leaders included), a session is busy when it overlaps anything on that member's Timetable (`Schedule.itemsBetween` over the event's days) other than this event's own sessions, by the rules of My events §5.1: cancelled classes and make-ups without a time don't count, an exam without a length lasts 90 minutes, back-to-back is not a clash. Only the counts are shown.

### 5.2 The event page

`/social/groups/{id}/events/{eventId}`, for anyone logged in (a deleted event or group is 404).

- **Everyone:** title, group, repeat in words ("Every week on Tue"), days ("07/10–15/12"), time, place, notes, and "23 going · 4 not going". Non-members: "Join the group to answer."
- **Members:** **Going** and **Not going** buttons, the current answer marked. Above them, each session from today on: "✓ No conflict" or "⚠ Conflict: IT093IU Web Application (17:15–19:45)" (+ N), against their own Timetable without this event, as Mailbox's Join shows it. Answering saves the answer with `answered_at` and returns with "You're going to "Weekly practice"." / "You're not going to "Weekly practice".". Answers lock after the last day: "This event has ended."
- **Changed after you answered:** when the event's `updated_at` is after your `answered_at`, the page says "Changed on 06/10, after you answered." Answering again (the same answer or the other) clears it.
- **Leaders and Sub-leaders** also see the names under Going and Not going, and "No answer: 30"; and an Edit link.

### 5.3 Waiting for you: events

An event waits for your answer when it isn't deleted, its group isn't deleted, you are a member, its last day is today or later, and you haven't answered it or it changed after you answered. My groups lists them ("Chess Club · Weekly practice · Every week on Tue, 19:00–21:00 · Answer →", or "· Changed · Answer again →"), and the Groups count includes them.

### 5.4 On the Timetable (the only one)

- School's `Schedule` takes any number of `TimetableSource` beans (a School interface: the extra items for a user in [startUtc, endUtc)) and adds their items in `itemsBetween`. The Social module's source gives one item per session of each event the user answered **going**, in a live group where they are still a member, the event not deleted; days come from `Occurrences`.
- New item kind `group` (a `Schedule.GROUP` constant in School): label the group's name, title the event's title, room its place, source the event page ("Open"), `eventId` the group event's id. The calendar shows "Chess Club: Weekly practice" with the class `event-group` (a colour of its own, `--group-color`); the legend gets "Group event"; Overview's Today and Tomorrow list them like own events.
- **Conflict marks:** `MyEventConflicts` marks items of kind `mine` and `group`. An item never clashes with its own event's other sessions, compared by **kind and id**, because an own event and a group event can share an id. A clashing group session gets "⚠ " and `event-conflict` on the calendar.
- My events' Check and Mailbox's Join already read `itemsBetween`, so they count group events as busy without change.
- A group event leaves your Timetable when you answer Not going, leave or are removed (your answers to the group's events are deleted), or when the event or group is deleted.

---

## 6. Rules

### 6.1 Who can do what

| | Leader | Sub-leader | Member | Not a member |
|---|---|---|---|---|
| See the group, its events and counts | ✓ | ✓ | ✓ | ✓ |
| Ask to join (not when full) | | | | ✓ |
| See members, answer events | ✓ | ✓ | ✓ | |
| Invite friends | ✓ | ✓ | ✓ (needs approval) | |
| Approve or decline requests, cancel invites, publish / edit / delete events, edit the group, see History | ✓ | ✓ | | |
| Remove a member | anyone but themselves | plain members only | | |
| Make Sub-leader, make Member, hand over Leader, delete the group | ✓ | | | |
| Leave | no: hand over or delete the group first | ✓ | ✓ | |

The inviter may also cancel their own open invite.

### 6.2 Joining

1. **Ask to join** → *requested* (History "requested"). Cancel request → row deleted ("request_cancelled").
2. A Leader or Sub-leader **approves** → *member*, `joined_at` set ("approved") or **declines** → row deleted ("declined").
3. A member **invites** a friend → *invited*, `invited_by` set ("invited"). Only friends (accepted friendship), only when the friend has no row in the group, and not while the group is full. The inviter or a Leader / Sub-leader can cancel it ("invite_cancelled").
4. The friend **accepts**: if the inviter is, at that moment, a member with role Leader or Sub-leader → *member* ("joined", detail "invited by An"); otherwise → *requested* ("requested", detail "invited by An"), and step 2 follows. **Declines** → row deleted ("invite_declined").
5. **Leave** / **remove** → row deleted and the person's answers to the group's events deleted ("left" / "removed").
6. **Roles** (Leader only): Make Sub-leader / Make Member ("role_changed", detail the new role); **Hand over** to a member or Sub-leader asks "Make Binh the Leader? You become a Sub-leader." → Binh is Leader, the old Leader is Sub-leader ("handed_over").

### 6.3 Full groups

While the number of members equals `max_members`: Ask to join and Invite are switched off ("Full"), and Approve and Accept refuse with "Chess Club is full (50 members)." Approve, Accept, role changes and Leave lock the group's row (`PESSIMISTIC_WRITE`) before counting, so two clicks at once can't pass the limit or leave two Leaders.

### 6.4 Friends

- You can't send a request to yourself, or to someone who already has a row with you. If they asked you, your button is Accept.
- Only the person asked can accept or decline; only the sender can cancel; either friend can remove.
- Removing a friend doesn't change groups or invites already sent.

---

## 7. Find groups

`GET /social/groups/find`: every field is a URL parameter, so a search can be bookmarked and the back button works.

- **Search** (`q`): split into words; every word must appear in the name or the description (case ignored; accents ignored on MySQL). Matching parts are highlighted with `<mark>`, built from escaped pieces (never raw HTML).
- **Filters:**
  1. Category: any or one of the seven.
  2. My status: any, not joined, member (any role), Leader or Sub-leader, requested, invited.
  3. Size (members): any, 1–10, 11–50, 51 or more.
  4. Space: any, has space (no limit or below it), full.
  5. Upcoming events: any, has upcoming events (an event not deleted whose last day is today or later), none. Added in stage 3.
  6. Created: any time, last 7 days, last 30 days.
- **Sort by** name, members, newest or category, **then by** a second of the same (default: name; ties last by id).
- **Page size** 10 / 20 / 50 / 100 (default 20; anything else counts as 20), numbered pages with Previous and Next, and "Showing 21–40 of 156 groups". Nothing found: "No groups match." with a "Clear all filters" link.
- Deleted groups never appear. Counting, filtering, sorting and paging happen in the database (a JPA query built from the filters, with member counts as a subquery); next events are worked out only for the rows on the page.

Members, Find people and History page 20 at a time with the same "Showing …" line.

---

## 8. Errors and security

- Every page needs login (as now). Every action checks the role on the server, not only by hiding buttons.
- **404:** an unknown or deleted group or event; a request, invite or member row that isn't in that group.
- **403:** an action the person's role doesn't allow, on a page that says why: "Only the group's Leader can do that." / "Only the group's Leader and Sub-leaders can do that." / "Only members can do that." (`error.html` today only explains 404.)
- **Out-of-date clicks** (the request was already handled, the invite cancelled, the friend request answered) go back with a message, not an error page: "Binh is no longer waiting.", "This invite was cancelled.", "That request was already answered."
- **Double clicks:** the unique keys (one friendship per pair, one row per group and person, one answer per event and person) catch the second click, which counts as already done.
- **Forms:** browser hints (`required`, `maxlength`, `min`/`max`) for quick feedback; the server checks everything; mistakes show under their field and the form keeps what was typed. Buttons that delete ask first (`confirm`, as Devices does).
- **CSRF** on every POST; all text with `th:text`; search highlights built from escaped pieces.
- **Privacy:** search shows display names only; emails never; members' list only to members; the Leader's check only counts; who answered what only to Leaders and Sub-leaders.

---

## 9. Testing

As the existing tests: JUnit 5, MockMvc, H2 in MySQL mode, and once on MySQL in GitHub's checks.

- **Unit (pure):** the joining steps (§6.2) including the inviter's role at accept time; Find groups' filters and sorting turned into a query (and the page size rule); highlight pieces (escaping, several words, accents left as typed); busy counting (a class, an exam without a length, a cancelled class not busy, back-to-back not busy, this event's own sessions not busy); `MyEventConflicts` with an own event and a group event sharing an id.
- **Pages (MockMvc), per stage:** every page and button; each role's allowed and refused actions (403); unknown and deleted ids (404); another student's request (404); POST without CSRF (403); out-of-date clicks' messages; full groups; hand over; the menu counts; Find groups with every filter, both sorts, each page size and the "Showing" line; Friends search (at least 2 letters, never yourself, button states, no email in the HTML).
- **Timetable:** a Going event appears in `itemsBetween`, the calendar feed (`event-group`, the link) and Overview; Not going, leaving, a deleted event and a deleted group don't; a clashing group session gets ⚠; My events' Check counts a group event.
- **Migrations:** the tables exist (`MigrationTest`); the CHECK constraints refuse bad values; a deleted group's name can be used again; `MigrationNamingTest` accepts module 2.
- **Timing:** Check members' times for a 100-member group with a weekly event over a semester finishes in a few seconds on H2 (the test prints the time; §11).

---

## 10. Build order

Three stages, each with its own plan, migration and merge into `main`:

1. **Friends:** module setup (package `social`, `SocialModule`, `Navigation.MODULES`, `NavCount` and the menu counts, dashboard cards, `MigrationNamingTest` and README rules 1 and 5), `social_friendships`, the Friends page. Only Friends registers its `NavModule`, so the menu shows Groups as "coming soon" (as it does for any module not built yet) until stage 2; the Friends page shows no shared groups until stage 2.
2. **Groups:** `social_groups`, `social_group_members`, `social_group_history`; My groups, Find groups (five filters), New / Edit / Delete, the group page, Members, History; joining, invites, roles, full groups, the 403 page.
3. **Group events:** `social_group_events`, `social_event_answers`, History's `event_id`; the event form with members' times, the event page and answers, Waiting for you's events, `TimetableSource` and the `group` kind in School (calendar, legend, Overview, conflict marks), the sixth filter.

---

## 11. Risks

- **Check members' times is slow for big groups:** about eight queries per member (one `itemsBetween`), so 100 members is about 800 queries, a few seconds on the online database. It runs only when the button is pressed. If it is too slow, a batched `itemsBetween` for many users can replace the per-member calls later.
- **The generated column for unique live names** must work on H2 and MySQL; the plan tries it first. If H2 refuses it, the code check alone stays and the database backstop is dropped (noted in the plan).
- **Accent-insensitive search** depends on MySQL's collation (`utf8mb4_0900_ai_ci`); H2 tests only check case. The MySQL run in GitHub's checks covers one accented search.
- **An own event and a group event with the same id** would hide each other's clashes if compared by id alone: every comparison uses kind and id (tested).
- **A deleted account** removes its memberships (cascade), so a group whose Leader's account is deleted has no Leader. No page deletes accounts today; the admin pages (later) must hand over first.
- **The menu grows to three modules** plus Log out; on a narrow phone it may wrap until the hamburger menu exists.
- **Real students on the live site** see each other's display names through Find people. That is the chosen design; emails stay hidden.
