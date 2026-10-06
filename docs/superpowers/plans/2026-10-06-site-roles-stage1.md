# Site roles, stage 1 (roles and profile) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every account gets one role (Student, Auditor, Admin) that decides its menu and the pages it may open; deactivated accounts can't log in, sync or be seen by other students; everyone gets a Profile and a Password page; the first Admin comes from a `.env` setting.

**Architecture:** A `role` column and soft-delete columns on `users` (module 0, "Site"). The role reaches Spring Security as the account's one authority; one access list in `SecurityConfig` says which roles may open which addresses, and a test fails when a page is missing from it. `AccountCheck`, a filter in the security chain, re-reads the account on every page so role changes, deactivation and password changes reach open sessions on their next click. Refusals get an explained 403 page. School's laptop keys and Social's Friends only work with active Students.

**Tech Stack:** Java 17, Spring Boot 4.1.1 (Spring MVC, Thymeleaf, Spring Security 7.1, Spring Data JPA, Flyway), MySQL 8 (H2 2.4 in MySQL mode for tests), JUnit 5 + MockMvc. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-06-site-roles-design.md`. This plan builds §12 stage 1: §3.1, §4 (all of it), §5.1–§5.5, and the parts of §9 and §10 they need. The Users page (stage 2) and the audit log and statistics (stage 3) get their own plans.

## Global Constraints

- Site-wide tables (`users`) have no module prefix; their migrations are named `V<date>_0_<number>__<what>.sql` (module 0 is Site). Never edit a migration once it is on `main`.
- Roles are stored as `student`, `auditor`, `admin` (a CHECK refuses anything else) and reach Spring Security as `ROLE_STUDENT`, `ROLE_AUDITOR`, `ROLE_ADMIN`. Every account on the live site, and everyone who registers, is a Student.
- The access list, top to bottom: `/auth/login`, `/auth/register`, `/css/**`, `/js/**`, `/error` → anyone; `/school/**`, `/social/**` → Student; `/admin/users/**` → Admin; `/admin/audit-log/**`, `/admin/statistics/**` → Auditor, Admin; `/`, `/account/**`, `/auth/logout` → any logged-in role; anything else → any logged-in role (so a mistyped address still says "Page not found"). `/api/school/sync/**` keeps its own filter chain.
- Menus: Student: School · Groups · Friends. Auditor: Audit log · Statistics. Admin: Users · Audit log · Statistics. Then Profile · Log out for every role. A page not built yet shows "coming soon".
- **Staff never see a student's own data** (timetable, exams, tuition, mail, courses, events, friends, groups).
- An account is **active** when `deactivated_at IS NULL`; an **active Student** is an active account with role `student`. Only active Students sync a laptop, appear in Find people and friend lists, and count in the Friends number.
- Messages, exactly:
  - Login, right password, deactivated: "This account has been deactivated. Ask the site's admin to turn it back on."
  - Logged out because the password changed elsewhere: "Your password was changed. Log in again."
  - 403: "You can't open this page" then "Your account is a student account: it can open School, Groups and Friends." / "Your account is an Auditor account: it can open the Audit log and Statistics." / "Your account is an Admin account: it can open Users, the Audit log and Statistics."; on the Connect page: "Only student accounts can connect a laptop. Log out and log in with your student account."; a form without its security code: "This form expired" then "Go back, reload the page and try again."
  - Profile: "Saved your profile.", "Enter your current password to change your email.", "Current password is incorrect.", "This email is already registered.", and register's field messages.
  - Password: "Password changed.", "Current password is incorrect.", "Choose a password different from your current one.", "Passwords don't match.", "Field must be between 8 and 128 characters long."
- Times are stored in UTC (`LocalDateTime.now(clock)`), shown in Vietnam time (UTC+7): dates `dd/MM/yyyy`, times `dd/MM/yyyy HH:mm`.
- All user text with `th:text` or Thymeleaf-escaped attributes, never `th:utext`.
- Commits: `type(scope): message`, as the repository does (`feat(web): …`, `docs: …`), ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- **The same email typed in capitals or with spaces on the Profile page** (`"  AN@Example.com "`): it is the person's own email, so no password is asked and it is saved lower-case. → Task 6, `theSameEmailInCapitalsOrWithSpacesNeedsNoPassword`.
- **A display name with HTML or quotes** (`<b>"Vy"</b>`): shown as text on Profile and on the home page, never as markup. → Task 6, `aNameWithHtmlIsShownAsText`.
- **A form sent after the account was deactivated** (the person still has the page open): nothing is saved; they are logged out with the deactivated message. → Task 3, `aFormSentAfterDeactivationDoesNothing`.
- **`SITE_ADMIN_EMAIL` written with capitals or spaces** (`" Boss@Example.com "`): still finds the account. → Task 9, `withNoActiveAdminTheNamedAccountBecomesOne`.
- **A new password with spaces at the end** (`"new horse 123 "`): kept exactly as typed, like register does, so it works at the next login. → Task 6, `aNewPasswordIsSavedAndThisSessionStaysLoggedIn`.

---

## Before you start

- Work in the worktree `C:/IU_SCHOOL/IU project/School-Life-Assistant/site-roles`, branch `site-roles` (it holds the spec and this plan). Another session uses the main project folder: don't switch branches there.
- Run commands from `web/` in Git Bash (`./mvnw …`; in PowerShell use `.\mvnw.cmd …` and quote `-D` options: `"-Dtest=UsersTableTest"`).
- Baseline on 2026-10-06 (main 8610543): `./mvnw -B test` → 753 tests, 0 failures, 1 skipped (`accentsAreIgnoredOnMySql`, which runs only on MySQL). Check it still passes before Task 1.
- One test class: `./mvnw -q test -Dtest=UsersTableTest`. A class with nested classes: `-Dtest='LayoutTest*'`.
- After renaming or deleting a class or migration, run `./mvnw clean` first (README, "Everyday commands").
- **H2 quirk:** H2 2.4.240 breaks every CHECK that compares text once the connection that created it closes ("Check constraint invalid"). The site's tests keep that connection open (`spring.datasource.hikari.max-lifetime=0`); a test that migrates a database of its own must use one `SingleConnectionDataSource` for the migration and its inserts (as `MigrationTest.freshWithTwoAccounts` does).

## File map

| File | Responsibility |
|---|---|
| `web/src/main/resources/db/migration/V20261006_0_1__user_roles.sql` | role, soft delete, audit columns and last login on `users` |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/Role.java` | the three roles: database code, label, authority |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/User.java` (modify) | the new columns and the changes to them |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/AppUser.java` (modify) | role and active in the session; the role as authority |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java` | account changes: login time, profile, password |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java` | after a login: the time, then back to the page that asked |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountCheck.java` | re-reads the logged-in account on every page |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/Sessions.java` | logs a person in for this browser (register, password change) |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountController.java` | `/account` (Profile) and `/account/password` |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/ProfileForm.java`, `PasswordForm.java` | the two forms' fields and rules |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/FirstAdmin.java` | `SITE_ADMIN_EMAIL` at startup |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/UserRepository.java` (modify) | is there an active Admin |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java` (modify) | register: first login time; uses `Sessions` |
| `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java` (modify) | access list, login checks and handlers, `AccountCheck`, method security |
| `web/src/main/java/vn/edu/hcmiu/sla/core/Refusals.java` | why a page was refused, for `error.html` |
| `web/src/main/java/vn/edu/hcmiu/sla/core/Navigation.java` (modify) | a menu per role |
| `web/src/main/java/vn/edu/hcmiu/sla/school/sync/DeviceKeys.java` (modify) | keys work only for active Students |
| `web/src/main/java/vn/edu/hcmiu/sla/social/friends/PeopleSearch.java`, `Friends.java`, `social/model/SocialFriendshipRepository.java` (modify) | Friends only among active Students |
| `web/src/main/resources/templates/error.html`, `layout.html`, `auth/login.html` (modify); `auth/account.html`, `auth/password.html` (new) | pages |
| `deploy/server/compose.yaml`, `deploy/server/.env.example`, `.env.example`, `render.yaml` (modify) | `SITE_ADMIN_EMAIL` |
| tests: `auth/UsersTableTest`, `auth/AppUserTest`, `auth/LoginTest`, `auth/RegisterTest`, `auth/AccountCheckTest`, `auth/AccountPageTest`, `auth/FirstAdminTest`, `core/MigrationNamingTest`, `core/MigrationTest`, `core/AccessListTest`, `core/AccessTest`, `core/RefusedPageTest`, `core/MethodSecurityTest`, `core/NavigationTest`, `core/LayoutTest`, `school/sync/SyncApiTest`, `social/SocialTestData`, `social/friends/FriendsTest`, `social/pages/FriendsPageTest` | |
| `README.md` | roles, the first Admin, rules 1, 3 and 5 |

---

### Task 1: Roles and deactivation in the database and in the session

**Files:**
- Create: `web/src/main/resources/db/migration/V20261006_0_1__user_roles.sql`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/Role.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/User.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/AppUser.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/core/MigrationNamingTest.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/core/MigrationTest.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginTest.java:91`, `web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java:30`, `web/src/test/java/vn/edu/hcmiu/sla/core/NavigationTest.java:18` (the `AppUser` constructor)
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/UsersTableTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/auth/AppUserTest.java`

**Interfaces:**
- Produces: `enum Role { STUDENT, AUDITOR, ADMIN }` with `String code()` ("student"), `String label()` ("Student"), `String authority()` ("ROLE_STUDENT"), `static Role of(String code)` (throws `IllegalArgumentException` for an unknown code).
- Produces on `User`: getters `getRole()`, `getCreatedBy()`, `getUpdatedAt()`, `getUpdatedBy()`, `getDeactivatedAt()`, `getDeactivatedBy()`, `getLastLoginAt()`, `isMustChangePassword()`, `isActive()`, `isActiveStudent()`; changes `changeRole(Role role, Integer by, LocalDateTime now)`, `deactivate(Integer by, LocalDateTime now)`, `reactivate(Integer by, LocalDateTime now)`, `changeProfile(String displayName, String email, Integer by, LocalDateTime now)`, `changePassword(String passwordHash, Integer by, LocalDateTime now)`, `loggedIn(LocalDateTime now)`. `by` is the account that made the change; `null` means the site itself.
- Produces: `record AppUser(Integer id, String email, String displayName, String passwordHash, Role role, boolean active)`; `AppUser.of(User)`; `getAuthorities()` is the role's authority; `isEnabled()` is `active`.

- [ ] **Step 1: Write the failing tests**

In `MigrationNamingTest.java`, replace the class body's pattern, message and second test:

```java
/** Migrations are named V&lt;date&gt;_&lt;module&gt;_&lt;number&gt;__&lt;what&gt;.sql: module 0 is Site, 1 School, 2 Social. */
class MigrationNamingTest {

    static final Pattern NAME = Pattern.compile("V\\d{8}_[012]_\\d+__[a-z0-9_]+\\.sql");

    @Test
    void everyMigrationIsNamedByDateModuleAndNumber() throws Exception {
        Resource[] files = new PathMatchingResourcePatternResolver().getResources("classpath*:db/migration/*");

        assertThat(files).isNotEmpty();
        for (Resource file : files) {
            String name = file.getFilename();
            assertThat(name.equals("V1__baseline.sql") || NAME.matcher(name).matches())
                    .as("%s should be named like V20261001_1_1__new_table.sql "
                            + "(date, module: 0 Site, 1 School, 2 Social, then a number)", name)
                    .isTrue();
        }
    }

    @Test
    void theModulesAreSiteSchoolAndSocial() {
        assertThat(NAME.matcher("V20261006_0_1__user_roles.sql").matches()).isTrue();
        assertThat(NAME.matcher("V20261006_1_1__school_table.sql").matches()).isTrue();
        assertThat(NAME.matcher("V20261006_2_1__social_friendships.sql").matches()).isTrue();
        assertThat(NAME.matcher("V20261006_3_1__expense_table.sql").matches()).isFalse();
    }
}
```

In `MigrationTest.java`, add this test after `theBaselineLeavesKeyNamesToMysqlLikeAlembicDid`:

```java
    @Test
    void accountsMadeBeforeRolesBecomeActiveStudents() throws Exception {
        // The live site's accounts were made before module 0: each becomes an active Student, last changed when made.
        // One connection for everything, so H2 keeps the role CHECK (see freshWithTwoAccounts).
        SingleConnectionDataSource live = new SingleConnectionDataSource(
                "jdbc:h2:mem:live-" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE", "sa", "", true);
        try {
            ScriptUtils.executeSqlScript(live.getConnection(), new ClassPathResource("db/migration/V1__baseline.sql"));
            try (Statement sql = live.getConnection().createStatement()) {
                sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at)"
                        + " VALUES (1, 'an@example.com', 'An', 'x', '2026-09-01 08:00:00')");
            }

            migrate(live, "classpath:db/migration");

            try (Statement sql = live.getConnection().createStatement();
                 ResultSet row = sql.executeQuery("SELECT role, created_at, updated_at, updated_by, deactivated_at,"
                         + " last_login_at, must_change_password FROM users WHERE id = 1")) {
                assertThat(row.next()).isTrue();
                assertThat(row.getString("role")).isEqualTo("student");
                assertThat(row.getTimestamp("updated_at")).isEqualTo(row.getTimestamp("created_at"));
                assertThat(row.getObject("updated_by")).isNull();
                assertThat(row.getTimestamp("deactivated_at")).isNull();
                assertThat(row.getTimestamp("last_login_at")).isNull();
                assertThat(row.getBoolean("must_change_password")).isFalse();
            }
        } finally {
            live.destroy();
        }
    }
```

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/UsersTableTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.LocalDateTime;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

/** Roles, deactivation and who changed an account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 3.1). */
@SpringBootTest
@Transactional
class UsersTableTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);
    static final LocalDateTime OCT_6 = LocalDateTime.of(2026, 10, 6, 7, 0);

    @Autowired
    EntityManager db;

    @Autowired
    UserRepository users;

    @Autowired
    JdbcTemplate jdbc;

    User saved(String email) {
        User user = users.save(new User(email, "An", "x", SEPT_1));
        db.flush();
        return user;
    }

    /** The account as the database has it now. */
    User reloaded(User user) {
        db.flush();
        db.clear();
        return users.findById(user.getId()).orElseThrow();
    }

    @Test
    void aNewAccountIsAnActiveStudentChangedWhenItWasMade() {
        User an = reloaded(saved("an@example.com"));

        assertThat(an.getRole()).isEqualTo(Role.STUDENT);
        assertThat(an.isActive()).isTrue();
        assertThat(an.isActiveStudent()).isTrue();
        assertThat(an.getUpdatedAt()).isEqualTo(SEPT_1);
        assertThat(an.getCreatedBy()).isNull();
        assertThat(an.getUpdatedBy()).isNull();
        assertThat(an.getDeactivatedAt()).isNull();
        assertThat(an.getLastLoginAt()).isNull();
        assertThat(an.isMustChangePassword()).isFalse();
    }

    @Test
    void aRoleChangeKeepsWhoAndWhen() {
        User admin = saved("admin@example.com");
        User an = saved("an@example.com");

        an.changeRole(Role.AUDITOR, admin.getId(), OCT_6);
        an = reloaded(an);

        assertThat(an.getRole()).isEqualTo(Role.AUDITOR);
        assertThat(an.isActive()).isTrue();
        assertThat(an.isActiveStudent()).isFalse();
        assertThat(an.getUpdatedBy()).isEqualTo(admin.getId());
        assertThat(an.getUpdatedAt()).isEqualTo(OCT_6);
    }

    @Test
    void deactivatingKeepsWhoAndWhenAndReactivatingClearsThem() {
        User admin = saved("admin@example.com");
        User an = saved("an@example.com");

        an.deactivate(admin.getId(), OCT_6);
        an = reloaded(an);
        assertThat(an.isActive()).isFalse();
        assertThat(an.isActiveStudent()).isFalse();
        assertThat(an.getDeactivatedAt()).isEqualTo(OCT_6);
        assertThat(an.getDeactivatedBy()).isEqualTo(admin.getId());

        an.reactivate(admin.getId(), OCT_6.plusHours(1));
        an = reloaded(an);
        assertThat(an.isActive()).isTrue();
        assertThat(an.isActiveStudent()).isTrue();
        assertThat(an.getDeactivatedAt()).isNull();
        assertThat(an.getDeactivatedBy()).isNull();
        assertThat(an.getUpdatedAt()).isEqualTo(OCT_6.plusHours(1));
    }

    @Test
    void aLoginIsNotAChange() {
        User an = saved("an@example.com");

        an.loggedIn(OCT_6);
        an = reloaded(an);

        assertThat(an.getLastLoginAt()).isEqualTo(OCT_6);
        assertThat(an.getUpdatedAt()).isEqualTo(SEPT_1);
    }

    @Test
    void aProfileOrPasswordChangeKeepsWhoAndWhen() {
        User an = saved("an@example.com");
        jdbc.update("UPDATE users SET must_change_password = TRUE WHERE id = ?", an.getId());
        an = reloaded(an);
        assertThat(an.isMustChangePassword()).isTrue();

        an.changeProfile("An Nguyen", "an.nguyen@example.com", an.getId(), OCT_6);
        an.changePassword("y", an.getId(), OCT_6.plusHours(1));
        an = reloaded(an);

        assertThat(an.getDisplayName()).isEqualTo("An Nguyen");
        assertThat(an.getEmail()).isEqualTo("an.nguyen@example.com");
        assertThat(an.getPasswordHash()).isEqualTo("y");
        assertThat(an.isMustChangePassword()).isFalse(); // a password they chose themselves
        assertThat(an.getUpdatedBy()).isEqualTo(an.getId());
        assertThat(an.getUpdatedAt()).isEqualTo(OCT_6.plusHours(1));
    }

    /** On whichever database the tests run: H2 here, MySQL in GitHub's second run. */
    @Test
    void theTableRefusesAnUnknownRole() {
        User an = saved("an@example.com");

        assertThatThrownBy(() -> jdbc.update("UPDATE users SET role = 'boss' WHERE id = ?", an.getId()))
                .isInstanceOf(DataAccessException.class)
                .hasMessageContaining("ck_users_role");
    }

    @Test
    void deletingAnAdminLeavesTheAccountsTheyChanged() {
        User admin = saved("admin@example.com");
        User an = saved("an@example.com");
        an.changeRole(Role.AUDITOR, admin.getId(), OCT_6);
        an.deactivate(admin.getId(), OCT_6);
        db.flush();

        jdbc.update("DELETE FROM users WHERE id = ?", admin.getId());
        db.clear();
        User again = users.findById(an.getId()).orElseThrow();

        assertThat(again.getUpdatedBy()).isNull();
        assertThat(again.getDeactivatedBy()).isNull();
        assertThat(again.getDeactivatedAt()).isEqualTo(OCT_6);
        assertThat(again.getRole()).isEqualTo(Role.AUDITOR);
    }
}
```

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/AppUserTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.LocalDateTime;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.GrantedAuthority;

/** The role in the session (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.2). */
class AppUserTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);

    @Test
    void rolesAreStoredByTheirCodeAndShownByTheirLabel() {
        assertThat(Role.of("student")).isEqualTo(Role.STUDENT);
        assertThat(Role.of("auditor")).isEqualTo(Role.AUDITOR);
        assertThat(Role.of("admin")).isEqualTo(Role.ADMIN);
        assertThat(Role.ADMIN.code()).isEqualTo("admin");
        assertThat(Role.AUDITOR.label()).isEqualTo("Auditor");
        assertThatThrownBy(() -> Role.of("boss")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void theRoleIsTheAccountsOneAuthority() {
        for (Role role : Role.values()) {
            AppUser user = new AppUser(1, "an@example.com", "An", "x", role, true);

            assertThat(user.getAuthorities()).extracting(GrantedAuthority::getAuthority)
                    .containsExactly("ROLE_" + role.name());
        }
    }

    @Test
    void aDeactivatedAccountIsNotEnabled() {
        assertThat(new AppUser(1, "an@example.com", "An", "x", Role.STUDENT, true).isEnabled()).isTrue();
        assertThat(new AppUser(1, "an@example.com", "An", "x", Role.STUDENT, false).isEnabled()).isFalse();
    }

    @Test
    void ofCopiesTheAccount() {
        User user = new User("an@example.com", "An", "x", SEPT_1);
        user.changeRole(Role.AUDITOR, null, SEPT_1);
        user.deactivate(null, SEPT_1);

        AppUser of = AppUser.of(user);

        assertThat(of.email()).isEqualTo("an@example.com");
        assertThat(of.displayName()).isEqualTo("An");
        assertThat(of.passwordHash()).isEqualTo("x");
        assertThat(of.role()).isEqualTo(Role.AUDITOR);
        assertThat(of.active()).isFalse();
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='MigrationNamingTest,UsersTableTest,AppUserTest'`
Expected: FAIL: compilation errors (`Role` doesn't exist, `User` has no `changeRole`).

- [ ] **Step 3: Write the migration**

Create `web/src/main/resources/db/migration/V20261006_0_1__user_roles.sql`:

```sql
-- Site roles and soft delete (docs/superpowers/specs/2026-10-06-site-roles-design.md, 3.1). Module 0 is Site: tables
-- every module shares. Every account so far becomes an active Student, last changed when it was made. MySQL refuses a
-- CHECK on a column whose foreign key has an ON DELETE action, so only role has one: "deactivated_by is set when
-- deactivated_at is" is kept by User.
ALTER TABLE users ADD COLUMN role VARCHAR(7) NOT NULL DEFAULT 'student';
ALTER TABLE users ADD COLUMN created_by INT NULL;
ALTER TABLE users ADD COLUMN updated_at DATETIME NULL;
ALTER TABLE users ADD COLUMN updated_by INT NULL;
ALTER TABLE users ADD COLUMN deactivated_at DATETIME NULL;
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

(Every statement was tried on H2 2.4.240 in MySQL mode while writing this plan; MySQL 8 accepts the same syntax.)

- [ ] **Step 4: Write `Role`**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/Role.java`:

```java
package vn.edu.hcmiu.sla.auth;

/**
 * An account's role, one per account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.1): Students use
 * School, Groups and Friends; Auditors read the audit log and statistics; Admins manage accounts. users.role keeps the
 * code ("student"); Spring Security sees the authority (ROLE_STUDENT), so hasRole("STUDENT") matches it.
 */
public enum Role {
    STUDENT("student", "Student"),
    AUDITOR("auditor", "Auditor"),
    ADMIN("admin", "Admin");

    private final String code;
    private final String label;

    Role(String code, String label) {
        this.code = code;
        this.label = label;
    }

    /** As stored in users.role. */
    public String code() {
        return code;
    }

    /** As pages show it: "Student". */
    public String label() {
        return label;
    }

    public String authority() {
        return "ROLE_" + name();
    }

    public static Role of(String code) {
        for (Role role : values()) {
            if (role.code.equals(code)) {
                return role;
            }
        }
        throw new IllegalArgumentException("Not a role: " + code);
    }
}
```

- [ ] **Step 5: Add the columns to `User`**

Replace `web/src/main/java/vn/edu/hcmiu/sla/auth/User.java` with:

```java
package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * An account. Shared by every module: their tables point at users.id. Its role, whether it is active and who last
 * changed it: docs/superpowers/specs/2026-10-06-site-roles-design.md, 3.1. In the changes below, by is the account that
 * made the change; null means the site itself (the first Admin, from SITE_ADMIN_EMAIL).
 */
@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, unique = true, length = 255)
    private String email;

    @Column(name = "display_name", nullable = false, length = 100)
    private String displayName;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt; // UTC

    @Column(nullable = false, length = 7)
    private String role = Role.STUDENT.code();

    @Column(name = "created_by")
    private Integer createdBy; // the Admin who made the account; null = registered themselves

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt; // UTC

    @Column(name = "updated_by")
    private Integer updatedBy; // who made the last change; null = the site, or none since

    @Column(name = "deactivated_at")
    private LocalDateTime deactivatedAt; // UTC; null = active

    @Column(name = "deactivated_by")
    private Integer deactivatedBy;

    @Column(name = "last_login_at")
    private LocalDateTime lastLoginAt; // UTC

    @Column(name = "must_change_password", nullable = false)
    private boolean mustChangePassword;

    protected User() {
    }

    /** An active Student, as register makes one. */
    public User(String email, String displayName, String passwordHash, LocalDateTime createdAt) {
        this.email = email;
        this.displayName = displayName;
        this.passwordHash = passwordHash;
        this.createdAt = createdAt;
        this.updatedAt = createdAt;
    }

    public Integer getId() {
        return id;
    }

    public String getEmail() {
        return email;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public Role getRole() {
        return Role.of(role);
    }

    public Integer getCreatedBy() {
        return createdBy;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public Integer getUpdatedBy() {
        return updatedBy;
    }

    public LocalDateTime getDeactivatedAt() {
        return deactivatedAt;
    }

    public Integer getDeactivatedBy() {
        return deactivatedBy;
    }

    public LocalDateTime getLastLoginAt() {
        return lastLoginAt;
    }

    public boolean isMustChangePassword() {
        return mustChangePassword;
    }

    /** Not deactivated. */
    public boolean isActive() {
        return deactivatedAt == null;
    }

    /** Allowed to sync a laptop and seen by other students (spec 4.6 and 5.2). */
    public boolean isActiveStudent() {
        return isActive() && getRole() == Role.STUDENT;
    }

    public void changeRole(Role newRole, Integer by, LocalDateTime now) {
        role = newRole.code();
        changed(by, now);
    }

    public void deactivate(Integer by, LocalDateTime now) {
        deactivatedAt = now;
        deactivatedBy = by;
        changed(by, now);
    }

    public void reactivate(Integer by, LocalDateTime now) {
        deactivatedAt = null;
        deactivatedBy = null;
        changed(by, now);
    }

    public void changeProfile(String newDisplayName, String newEmail, Integer by, LocalDateTime now) {
        displayName = newDisplayName;
        email = newEmail;
        changed(by, now);
    }

    /** A password the person chose themselves, so they no longer have to change it. */
    public void changePassword(String newPasswordHash, Integer by, LocalDateTime now) {
        passwordHash = newPasswordHash;
        mustChangePassword = false;
        changed(by, now);
    }

    /** A login isn't a change to the account: updated_at stays. */
    public void loggedIn(LocalDateTime now) {
        lastLoginAt = now;
    }

    private void changed(Integer by, LocalDateTime now) {
        updatedAt = now;
        updatedBy = by;
    }
}
```

- [ ] **Step 6: Put the role into `AppUser`**

Replace `web/src/main/java/vn/edu/hcmiu/sla/auth/AppUser.java` with:

```java
package vn.edu.hcmiu.sla.auth;

import java.util.Collection;
import java.util.List;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

/**
 * The logged-in user as Spring Security keeps it. Controllers get it with
 * {@code @AuthenticationPrincipal AppUser user} and filter every query by {@code user.id()}. Its role is its one
 * authority (ROLE_STUDENT, ROLE_AUDITOR or ROLE_ADMIN).
 */
public record AppUser(Integer id, String email, String displayName, String passwordHash, Role role, boolean active)
        implements UserDetails {

    public static AppUser of(User user) {
        return new AppUser(user.getId(), user.getEmail(), user.getDisplayName(), user.getPasswordHash(), user.getRole(),
                user.isActive());
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority(role.authority()));
    }

    /** False once deactivated: login then refuses the account, but only after the right password (SecurityConfig). */
    @Override
    public boolean isEnabled() {
        return active;
    }

    @Override
    public String getPassword() {
        return passwordHash;
    }

    @Override
    public String getUsername() {
        return email;
    }

    /** For templates: {@code ${#authentication.principal.displayName}}. */
    public String getDisplayName() {
        return displayName;
    }
}
```

- [ ] **Step 7: Fix the tests that build an `AppUser` by hand, and the raw inserts**

- `LoginTest.java` line 91: `AppUser an = new AppUser(1, "an@example.com", "An", "x", Role.STUDENT, true);`
- `LayoutTest.java` line 30: `static final AppUser AN = new AppUser(1, "an@example.com", "An", "x", Role.STUDENT, true);` and add `import vn.edu.hcmiu.sla.auth.Role;`
- `NavigationTest.java` line 18: `static final AppUser AN = new AppUser(7, "an@example.com", "An", "x", Role.STUDENT, true);` and add `import vn.edu.hcmiu.sla.auth.Role;`

In `MigrationTest.java`, `updated_at` is now required, and H2 breaks the role CHECK on a database whose creating connection closed:

1. In `freshWithTwoAccounts()`, make the two inserts:
   ```java
            sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at)"
                    + " VALUES (1, 'an@example.com', 'An', 'x', '2026-10-06 08:00:00', '2026-10-06 08:00:00')");
            sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at)"
                    + " VALUES (2, 'binh@example.com', 'Binh', 'x', '2026-10-06 08:00:00', '2026-10-06 08:00:00')");
   ```
2. Replace `aMailSettingsRowWithoutAutoDoneHasItOn` with:
   ```java
    @Test
    void aMailSettingsRowWithoutAutoDoneHasItOn() throws Exception {
        // No row means auto-Done is on; a row written without the column means the same.
        SingleConnectionDataSource fresh = freshWithTwoAccounts();
        try (Statement sql = fresh.getConnection().createStatement()) {
            sql.execute("INSERT INTO school_mail_settings (user_id) VALUES (1)");
            try (ResultSet row = sql.executeQuery("SELECT auto_done FROM school_mail_settings WHERE user_id = 1")) {
                assertThat(row.next()).isTrue();
                assertThat(row.getBoolean("auto_done")).isTrue();
            }
        } finally {
            fresh.destroy();
        }
    }
   ```
   `freshWithTwoAccounts` is declared further down the class; Java doesn't mind. Keep the `DriverManagerDataSource` import: `pythonMadeDatabase` still uses it.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='MigrationNamingTest,MigrationTest,UsersTableTest,AppUserTest,LoginTest,NavigationTest,LayoutTest*'`
Expected: PASS.

Then the whole suite: `./mvnw -B test`
Expected: 753 + 12 = 765 tests, 0 failures, 1 skipped.

- [ ] **Step 9: Commit**

```bash
git add web/src/main/resources/db/migration/V20261006_0_1__user_roles.sql web/src/main/java/vn/edu/hcmiu/sla/auth/Role.java web/src/main/java/vn/edu/hcmiu/sla/auth/User.java web/src/main/java/vn/edu/hcmiu/sla/auth/AppUser.java web/src/test/java/vn/edu/hcmiu/sla/auth/UsersTableTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/AppUserTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/LoginTest.java web/src/test/java/vn/edu/hcmiu/sla/core/MigrationNamingTest.java web/src/test/java/vn/edu/hcmiu/sla/core/MigrationTest.java web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java web/src/test/java/vn/edu/hcmiu/sla/core/NavigationTest.java
git commit -F - <<'EOF'
feat(web): every account has a role (Student, Auditor or Admin) and can be deactivated, in module 0's first migration

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Login refuses a deactivated account after the password, and notes when each login happens

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java:73-74` (register)
- Modify: `web/src/main/resources/templates/auth/login.html`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterTest.java`

**Interfaces:**
- Consumes: `User.loggedIn`, `User.deactivate`, `User.reactivate`, `AppUser.isEnabled()` (Task 1).
- Produces: `@Service Accounts` with `void loggedIn(Integer userId, LocalDateTime now)`. Task 6 adds to it.
- Produces: `@Component LoggedIn extends SavedRequestAwareAuthenticationSuccessHandler` (the login form's success handler).
- Produces: login redirects to `/auth/login?deactivated` for the right password of a deactivated account; `/auth/login?error` for everything else that fails.

- [ ] **Step 1: Write the failing tests**

In `LoginTest.java`, add `@Import(TestClock.Config.class)` under `@Transactional`, these fields and imports, and the tests:

```java
import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.AfterEach;
import org.springframework.context.annotation.Import;

import vn.edu.hcmiu.sla.school.TestClock;
```

```java
    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 6, 7, 0);

    @Autowired
    TestClock clock;

    @AfterEach
    void realTime() {
        clock.reset();
    }

    @Test
    void aLoginNotesItsTime() throws Exception {
        User an = savedUser("an@example.com", WerkzeugPasswordEncoderTest.SCRYPT);
        clock.set(NOW);

        mvc.perform(post("/auth/login").with(csrf()).param("email", "an@example.com").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/"));

        assertThat(an.getLastLoginAt()).isEqualTo(NOW);
        assertThat(an.getUpdatedAt()).isEqualTo(LocalDateTime.of(2026, 9, 1, 0, 0)); // a login isn't a change
    }

    @Test
    void aDeactivatedAccountIsToldSoButOnlyWithTheRightPassword() throws Exception {
        User an = savedUser("an@example.com", WerkzeugPasswordEncoderTest.SCRYPT);
        an.deactivate(null, NOW);

        mvc.perform(post("/auth/login").with(csrf())
                        .param("email", " AN@example.com ").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/auth/login?deactivated"));
        mvc.perform(post("/auth/login").with(csrf()).param("email", "an@example.com").param("password", "wrong-password"))
                .andExpect(redirectedUrl("/auth/login?error")); // a wrong password never learns the account is there
        mvc.perform(get("/auth/login").param("deactivated", ""))
                .andExpect(content().string(containsString(
                        "This account has been deactivated. Ask the site's admin to turn it back on.")));
        assertThat(an.getLastLoginAt()).isNull();
    }

    @Test
    void anUnknownEmailGetsTheSameAnswerAsAWrongPassword() throws Exception {
        mvc.perform(post("/auth/login").with(csrf())
                        .param("email", "nobody@example.com").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/auth/login?error"));
    }

    @Test
    void aReactivatedAccountLogsInAgain() throws Exception {
        User an = savedUser("an@example.com", WerkzeugPasswordEncoderTest.SCRYPT);
        an.deactivate(null, NOW);
        an.reactivate(null, NOW);

        mvc.perform(post("/auth/login").with(csrf()).param("email", "an@example.com").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/"));
    }
```

In `RegisterTest.java`, add:

```java
    @Test
    void registeringMakesAStudentAndCountsAsTheFirstLogin() throws Exception {
        mvc.perform(register("an@example.com", "An", "correct-horse-8", "correct-horse-8"))
                .andExpect(redirectedUrl("/"));

        User user = users.findByEmail("an@example.com").orElseThrow();
        assertThat(user.getRole()).isEqualTo(Role.STUDENT);
        assertThat(user.getCreatedBy()).isNull();
        assertThat(user.getLastLoginAt()).isEqualTo(user.getCreatedAt());
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='LoginTest,RegisterTest'`
Expected: FAIL: `aLoginNotesItsTime` (last login is null), `aDeactivatedAccountIsToldSoButOnlyWithTheRightPassword` (redirects to `/auth/login?error` for the right password too: Spring Security checks the account before the password), `registeringMakesAStudentAndCountsAsTheFirstLogin` (last login is null).

- [ ] **Step 3: Write `Accounts` and `LoggedIn`**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Changes to the logged-in person's own account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5). */
@Service
public class Accounts {

    private final UserRepository users;

    public Accounts(UserRepository users) {
        this.users = users;
    }

    /** users.last_login_at, for the Users page (stage 2) and Profile. */
    @Transactional
    public void loggedIn(Integer userId, LocalDateTime now) {
        users.findById(userId).ifPresent(user -> user.loggedIn(now));
    }
}
```

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.time.Clock;
import java.time.LocalDateTime;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.core.Authentication;
import org.springframework.security.web.authentication.SavedRequestAwareAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

/**
 * After a login: notes its time, then goes back to the page that asked for login, else home, as Spring Security's own
 * handler does.
 */
@Component
public class LoggedIn extends SavedRequestAwareAuthenticationSuccessHandler {

    private final Accounts accounts;
    private final Clock clock;

    public LoggedIn(Accounts accounts, Clock clock) {
        this.accounts = accounts;
        this.clock = clock;
        setDefaultTargetUrl("/");
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
            Authentication authentication) throws IOException, ServletException {
        if (authentication.getPrincipal() instanceof AppUser user) {
            accounts.loggedIn(user.id(), LocalDateTime.now(clock));
        }
        super.onAuthenticationSuccess(request, response, authentication);
    }
}
```

- [ ] **Step 4: Check deactivation after the password, and use the two handlers**

Replace `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java` with:

```java
package vn.edu.hcmiu.sla.core;

import java.util.Map;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.security.web.authentication.ExceptionMappingAuthenticationFailureHandler;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;

import vn.edu.hcmiu.sla.auth.AppUserDetailsService;
import vn.edu.hcmiu.sla.auth.LoggedIn;
import vn.edu.hcmiu.sla.auth.WerkzeugPasswordEncoder;

/** Every page needs login except login, register and static files. Every form carries a CSRF token. */
@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn) throws Exception {
        http
                .authorizeHttpRequests(pages -> pages
                        .requestMatchers("/auth/login", "/auth/register", "/css/**", "/js/**", "/error").permitAll()
                        .anyRequest().authenticated())
                .formLogin(login -> login
                        .loginPage("/auth/login")
                        .usernameParameter("email")
                        .passwordParameter("password")
                        .successHandler(loggedIn) // back to the page that asked for login, else home
                        .failureHandler(loginFailed())
                        .permitAll())
                .logout(logout -> logout
                        .logoutUrl("/auth/logout")
                        .logoutSuccessUrl("/auth/login"));
        return http.build();
    }

    /** A wrong password or an unknown email: ?error. The right password for a deactivated account: ?deactivated. */
    static AuthenticationFailureHandler loginFailed() {
        ExceptionMappingAuthenticationFailureHandler failed = new ExceptionMappingAuthenticationFailureHandler();
        failed.setDefaultFailureUrl("/auth/login?error");
        failed.setExceptionMappings(Map.of(DisabledException.class.getName(), "/auth/login?deactivated"));
        return failed;
    }

    /**
     * Checks the email and password. Spring Security normally refuses a disabled account before it looks at the
     * password, which would tell anyone which emails have accounts; here only the right password learns that the
     * account is deactivated (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.1). The site's only
     * AuthenticationProvider, so Spring Security uses it for every login.
     */
    @Bean
    DaoAuthenticationProvider passwordLogin(AppUserDetailsService accounts, PasswordEncoder passwords) {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(accounts);
        provider.setPasswordEncoder(passwords);
        provider.setPreAuthenticationChecks(account -> {
        });
        provider.setPostAuthenticationChecks(account -> {
            if (!account.isEnabled()) {
                throw new DisabledException("This account has been deactivated");
            }
        });
        return provider;
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new WerkzeugPasswordEncoder();
    }

    /** Where a login is kept between requests; the register page uses it to log the new account in. */
    @Bean
    SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }
}
```

- [ ] **Step 5: Register counts as the first login; the login page says "deactivated"**

In `AuthController.register`, replace

```java
        User user = users.save(new User(form.getEmail(), form.getDisplayName(),
                passwords.encode(form.getPassword()), LocalDateTime.now(ZoneOffset.UTC)));
```

with

```java
        LocalDateTime now = LocalDateTime.now(ZoneOffset.UTC);
        User account = new User(form.getEmail(), form.getDisplayName(), passwords.encode(form.getPassword()), now);
        account.loggedIn(now); // registering logs the new account in: its first login
        User user = users.save(account);
```

In `templates/auth/login.html`, after the `param.error` line add:

```html
    <p th:if="${param.deactivated}" class="flash flash-error">This account has been deactivated. Ask the site's admin to turn it back on.</p>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='LoginTest,RegisterTest'`
Expected: PASS (`afterLoginYouGoBackToThePageYouAskedFor` still redirects to `http://localhost/school/timetable?continue`: `LoggedIn` is the same handler Spring Security used).

Then `./mvnw -B test`. Expected: 770 tests, 0 failures, 1 skipped.

- [ ] **Step 7: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java web/src/main/resources/templates/auth/login.html web/src/test/java/vn/edu/hcmiu/sla/auth/LoginTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterTest.java
git commit -F - <<'EOF'
feat(web): a deactivated account is told so at login, but only after the right password; each login notes its time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Every page re-reads the logged-in account

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountCheck.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java` (the `pages` chain)
- Modify: `web/src/main/resources/templates/auth/login.html`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java` (saved accounts)
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/AccountCheckTest.java`

**Interfaces:**
- Consumes: `User.isActive()`, `AppUser.of(User)`, `UserRepository.findById` (Task 1).
- Produces: `class AccountCheck extends OncePerRequestFilter`, `new AccountCheck(UserRepository users, SecurityContextRepository logins)`, placed before Spring Security's `AuthorizationFilter`. Logged-out redirects: `/auth/login?deactivated`, `/auth/login?changed`, `/auth/login` (account gone).
- Produces: `LayoutTest.account(UserRepository users, Role role)`: a saved account named An, for page tests in `core`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/AccountCheckTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.social.model.SocialFriendshipRepository;

/**
 * An Admin's change reaches a session that is already open on its next click
 * (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.4). Each test logs in with the real login form, so the
 * session is the browser's.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AccountCheckTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    SocialFriendshipRepository friendships;

    User an;

    @BeforeEach
    void anAccount() {
        an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));
    }

    MockHttpSession logIn() throws Exception {
        MockHttpSession session = new MockHttpSession();
        mvc.perform(post("/auth/login").session(session).with(csrf())
                        .param("email", "an@example.com").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/"));
        return session;
    }

    @Test
    void anUnchangedAccountStaysLoggedIn() throws Exception {
        MockHttpSession session = logIn();

        mvc.perform(get("/").session(session)).andExpect(status().isOk());
        mvc.perform(get("/").session(session)).andExpect(status().isOk());
    }

    @Test
    void aDeactivatedAccountIsLoggedOutOnItsNextClick() throws Exception {
        MockHttpSession session = logIn();
        an.deactivate(null, SEPT_1);

        mvc.perform(get("/").session(session)).andExpect(redirectedUrl("/auth/login?deactivated"));

        assertThat(session.isInvalid()).isTrue();
    }

    @Test
    void aFormSentAfterDeactivationDoesNothing() throws Exception { // Review Focus
        User lan = users.save(new User("lan@example.com", "Lan", "x", SEPT_1));
        MockHttpSession session = logIn();
        an.deactivate(null, SEPT_1);

        mvc.perform(post("/social/friends/" + lan.getId() + "/add").session(session).with(csrf()))
                .andExpect(redirectedUrl("/auth/login?deactivated"));

        assertThat(friendships.findBetween(an.getId(), lan.getId())).isEmpty();
    }

    @Test
    void anAccountDeletedByHandIsLoggedOut() throws Exception {
        MockHttpSession session = logIn();
        users.delete(an);
        users.flush();

        mvc.perform(get("/").session(session)).andExpect(redirectedUrl("/auth/login"));
    }

    @Test
    void aPasswordChangedElsewhereLogsThisSessionOut() throws Exception {
        MockHttpSession session = logIn();
        an.changePassword(WerkzeugPasswordEncoderTest.SCRYPT_VIETNAMESE, an.getId(), SEPT_1);

        mvc.perform(get("/").session(session)).andExpect(redirectedUrl("/auth/login?changed"));
        mvc.perform(get("/auth/login").param("changed", ""))
                .andExpect(content().string(containsString("Your password was changed. Log in again.")));
    }

    @Test
    void aNewNameOrRoleIsPutIntoTheSession() throws Exception {
        MockHttpSession session = logIn();
        an.changeProfile("An Nguyen", "an@example.com", an.getId(), SEPT_1);
        an.changeRole(Role.AUDITOR, null, SEPT_1);

        mvc.perform(get("/").session(session))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Hi, An Nguyen")));

        SecurityContext saved = (SecurityContext) session.getAttribute(
                HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY);
        AppUser now = (AppUser) saved.getAuthentication().getPrincipal();
        assertThat(now.displayName()).isEqualTo("An Nguyen");
        assertThat(now.role()).isEqualTo(Role.AUDITOR);
        assertThat(saved.getAuthentication().getAuthorities()).extracting(GrantedAuthority::getAuthority)
                .containsExactly("ROLE_AUDITOR");
    }

    @Test
    void cssAndJavaScriptDontLookTheAccountUp() throws Exception {
        MockHttpSession session = logIn();
        an.deactivate(null, SEPT_1);

        mvc.perform(get("/css/style.css").session(session)).andExpect(status().isOk());
        mvc.perform(get("/").session(session)).andExpect(redirectedUrl("/auth/login?deactivated"));
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest=AccountCheckTest`
Expected: FAIL in every test but `anUnchangedAccountStaysLoggedIn` (no redirect happens; the session still shows "Hi, An").

- [ ] **Step 3: Write `AccountCheck`**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountCheck.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.util.Optional;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Re-reads the logged-in account on every page (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.4), so a
 * change reaches a session that is already open on its next click: a deactivated or deleted account, or one whose
 * password changed somewhere else, is logged out; a new role, name or email goes into the session, so the menu and the
 * access list follow at once. One lookup by id. Static files are skipped, and so is the error page (OncePerRequestFilter
 * leaves out error dispatches). SecurityConfig places it before the access list; it is not a bean, so it runs only
 * there.
 */
public class AccountCheck extends OncePerRequestFilter {

    private final UserRepository users;
    private final SecurityContextRepository logins;
    private final SecurityContextLogoutHandler logout = new SecurityContextLogoutHandler();

    public AccountCheck(UserRepository users, SecurityContextRepository logins) {
        this.users = users;
        this.logins = logins;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return path.startsWith("/css/") || path.startsWith("/js/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Authentication login = SecurityContextHolder.getContext().getAuthentication();
        if (login != null && login.getPrincipal() instanceof AppUser user) {
            Optional<User> account = users.findById(user.id());
            String ended = account.isEmpty() ? ""
                    : !account.get().isActive() ? "?deactivated"
                    : !account.get().getPasswordHash().equals(user.passwordHash()) ? "?changed"
                    : null;
            if (ended != null) {
                logout.logout(request, response, login);
                response.sendRedirect(request.getContextPath() + "/auth/login" + ended);
                return;
            }
            AppUser now = AppUser.of(account.get());
            if (!now.equals(user)) {
                SecurityContext context = SecurityContextHolder.createEmptyContext();
                context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(now, null,
                        now.getAuthorities()));
                SecurityContextHolder.setContext(context);
                logins.saveContext(context, request, response);
            }
        }
        chain.doFilter(request, response);
    }
}
```

- [ ] **Step 4: Put it into the chain; the login page says "changed"**

In `SecurityConfig.java`:
- add imports `org.springframework.security.web.access.intercept.AuthorizationFilter`, `vn.edu.hcmiu.sla.auth.AccountCheck` and `vn.edu.hcmiu.sla.auth.UserRepository`;
- change the method's signature to `SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn, UserRepository users, SecurityContextRepository logins) throws Exception`;
- after the `.authorizeHttpRequests(…)` call, add:
  ```java
                .addFilterBefore(new AccountCheck(users, logins), AuthorizationFilter.class)
  ```

In `templates/auth/login.html`, after the `param.deactivated` line add:

```html
    <p th:if="${param.changed}" class="flash">Your password was changed. Log in again.</p>
```

- [ ] **Step 5: `LayoutTest` logs in with saved accounts**

`LayoutTest` logs in as an `AppUser` that isn't in the database; every page now looks the account up and logs it out. Replace `LayoutTest.java` with:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.support.RedirectAttributesModelMap;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;

class LayoutTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);

    /** A saved account named An: every page re-reads the logged-in account (AccountCheck), so it must be a real row. */
    static AppUser account(UserRepository users, Role role) {
        User user = users.save(new User("layout-" + UUID.randomUUID() + "@example.com", "An", "x", SEPT_1));
        user.changeRole(role, null, SEPT_1);
        return AppUser.of(user);
    }

    /** The real site, with whichever modules exist: nothing here depends on which ones (see NavigationTest). */
    @Nested
    @SpringBootTest
    @AutoConfigureMockMvc
    @Transactional
    class Pages {

        @Autowired
        MockMvc mvc;

        @Autowired
        UserRepository users;

        @Test
        void theDashboardGreetsYouWithOneCardPerModule() throws Exception {
            String page = mvc.perform(get("/").with(user(account(users, Role.STUDENT))))
                    .andExpect(status().isOk())
                    .andExpect(content().string(containsString("Hi, An")))
                    .andExpect(content().string(containsString("href=\"/css/style.css\"")))
                    .andReturn().getResponse().getContentAsString();

            assertThat(page.split("class=\"card module-card", -1)).hasSize(4); // School, Groups, Friends
        }

        @Test
        void theMenuIsHiddenUntilYouLogIn() throws Exception {
            mvc.perform(get("/auth/login"))
                    .andExpect(content().string(not(containsString("Log out"))));
        }

        @Test
        void oneTimeMessagesAppearAtTheTop() throws Exception {
            mvc.perform(get("/auth/login").flashAttr("flashes", List.of(new Flash("error", "Something broke."))))
                    .andExpect(content().string(containsString("<p class=\"flash flash-error\">Something broke.</p>")));
        }
    }

    @Nested
    @SpringBootTest
    @AutoConfigureMockMvc
    @Transactional
    @Import(WithSchool.SchoolNav.class)
    class WithSchool {

        @TestConfiguration
        static class SchoolNav {
            @Bean
            NavModule schoolNav() {
                return new NavModule("School", "/school");
            }
        }

        @Autowired
        MockMvc mvc;

        @Autowired
        UserRepository users;

        @Test
        void aModuleThatRegistersItselfGetsALinkAndACard() throws Exception {
            mvc.perform(get("/").with(user(account(users, Role.STUDENT))))
                    .andExpect(content().string(containsString("<a href=\"/school\">School</a>")))
                    .andExpect(content().string(containsString("<a class=\"card module-card\" href=\"/school\">")));
        }
    }

    @Nested
    @SpringBootTest
    @AutoConfigureMockMvc
    @Transactional
    @Import(WithACount.FriendsWithTwo.class)
    class WithACount {

        @TestConfiguration
        static class FriendsWithTwo {
            @Bean
            @Order(Ordered.HIGHEST_PRECEDENCE) // before the real Friends count, which would say 0; names differ from SocialModule's beans
            NavModule testFriendsMenu() {
                return new NavModule("Friends", "/social/friends");
            }

            @Bean
            @Order(Ordered.HIGHEST_PRECEDENCE)
            NavCount twoFriendRequestsWaiting() {
                return new NavCount("Friends", userId -> 2);
            }
        }

        @Autowired
        MockMvc mvc;

        @Autowired
        UserRepository users;

        @Test
        void aModulesCountComesAfterItsLabel() throws Exception {
            mvc.perform(get("/").with(user(account(users, Role.STUDENT))))
                    .andExpect(content().string(containsString("<a href=\"/social/friends\" aria-label=\"Friends, 2 waiting for you\">Friends"
                            + "<span class=\"nav-count\" title=\"2 waiting for you\">2</span></a>")));
        }
    }

    @Test
    void flashHelpersCollectMessagesForTheNextPage() {
        RedirectAttributesModelMap redirect = new RedirectAttributesModelMap();

        Flash.success(redirect, "Device renamed.");
        Flash.error(redirect, "A device name is required.");

        assertThat(redirect.getFlashAttributes().get("flashes")).isEqualTo(List.of(
                new Flash("message", "Device renamed."), new Flash("error", "A device name is required.")));
    }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='AccountCheckTest,LayoutTest*,LoginTest,RegisterTest'`
Expected: PASS. (`LoginTest.logOutNeedsAFormWithItsSecurityCode` still uses an `AppUser` that isn't saved; it passes because the security-code check and the logout both run before `AccountCheck`.)

Then `./mvnw -B test`. Expected: 777 tests, 0 failures, 1 skipped. If a test elsewhere now redirects to `/auth/login`, it logs in as an `AppUser` that isn't a saved row: save the account first, as `LayoutTest.account` does.

- [ ] **Step 7: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/AccountCheck.java web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/resources/templates/auth/login.html web/src/test/java/vn/edu/hcmiu/sla/auth/AccountCheckTest.java web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java
git commit -F - <<'EOF'
feat(web): every page re-reads the account, so deactivation, a new role or a changed password applies at the next click

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 4: The access list, method security and the 403 page that says why

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/core/Refusals.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java`
- Modify: `web/src/main/resources/templates/error.html`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/core/AccessListTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/core/AccessTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/core/RefusedPageTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/core/MethodSecurityTest.java`

**Interfaces:**
- Consumes: `Role`, `AppUser.role()`, `LayoutTest.account(UserRepository, Role)` (Tasks 1 and 3).
- Produces: `SecurityConfig.ANYONE`, `STUDENTS`, `ADMINS`, `STAFF`, `EVERY_ROLE` (package-private `String[]`), applied in that order; `@EnableMethodSecurity`, so stage 2's `@PreAuthorize` works.
- Produces: `@ControllerAdvice public class Refusals implements AccessDeniedHandler`; request attribute `Refusals.REASON` (`"sla.refusal"`) with `Refusals.ROLE`, `CONNECT` or `FORM`; model attribute `refusal` (`Refusals.Refusal(String title, String text, boolean offerLogOut)`, null on other pages).

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/core/AccessListTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.server.PathContainer;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;
import org.springframework.web.util.pattern.PathPatternParser;

/**
 * Every address the site serves is in SecurityConfig's access list
 * (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.2), so a new module can't be left open to every role.
 */
@SpringBootTest
class AccessListTest {

    /** Served by SyncApiConfig's own filter chain, which checks the laptop's device key instead of a login. */
    static final String[] LAPTOP = {"/api/school/sync/**"};

    @Autowired
    @Qualifier("requestMappingHandlerMapping")
    RequestMappingHandlerMapping pages;

    /** Whether an address as mapped (/school/courses/{courseId}) falls in one of the lists. */
    static boolean listed(String mapping) {
        PathContainer path = PathContainer.parsePath(mapping.replaceAll("\\{[^}]*}", "1"));
        return Stream.of(SecurityConfig.ANYONE, SecurityConfig.STUDENTS, SecurityConfig.ADMINS, SecurityConfig.STAFF,
                        SecurityConfig.EVERY_ROLE, LAPTOP)
                .flatMap(Arrays::stream)
                .anyMatch(pattern -> PathPatternParser.defaultInstance.parse(pattern).matches(path));
    }

    @Test
    void everyPageIsInTheAccessList() {
        List<String> mappings = pages.getHandlerMethods().keySet().stream()
                .flatMap(info -> info.getPatternValues().stream()).distinct().sorted().toList();

        assertThat(mappings).contains("/", "/school", "/social/friends", "/error", "/api/school/sync/check");
        assertThat(mappings).allSatisfy(mapping -> assertThat(listed(mapping))
                .as("%s is in an access list in SecurityConfig", mapping).isTrue());
    }

    @Test
    void anAddressOutsideTheListsIsCaught() {
        assertThat(listed("/expense/items")).isFalse();
        assertThat(listed("/admin/other")).isFalse();
        assertThat(listed("/school/courses/{courseId}")).isTrue();
        assertThat(listed("/admin/users/{id}/edit")).isTrue();
    }
}
```

Create `web/src/test/java/vn/edu/hcmiu/sla/core/AccessTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;

/** Each role opens only its own pages (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.1 and 4.2). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AccessTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    AppUser account(Role role) {
        return LayoutTest.account(users, role);
    }

    /** 404: allowed, but the page comes in stage 2 (Users) or 3 (Audit log, Statistics). */
    @ParameterizedTest(name = "{0} opens {1}: {2}")
    @CsvSource({
        "STUDENT, /,                  200",
        "STUDENT, /school,            200",
        "STUDENT, /social/friends,    200",
        "STUDENT, /admin/users,       403",
        "STUDENT, /admin/audit-log,   403",
        "STUDENT, /admin/statistics,  403",
        "AUDITOR, /,                  200",
        "AUDITOR, /school,            403",
        "AUDITOR, /school/timetable,  403",
        "AUDITOR, /social/friends,    403",
        "AUDITOR, /admin/users,       403",
        "AUDITOR, /admin/audit-log,   404",
        "AUDITOR, /admin/statistics,  404",
        "ADMIN,   /,                  200",
        "ADMIN,   /school,            403",
        "ADMIN,   /social/friends,    403",
        "ADMIN,   /admin/users,       404",
        "ADMIN,   /admin/audit-log,   404",
        "ADMIN,   /admin/statistics,  404"})
    void eachRoleOpensOnlyItsOwnPages(Role role, String path, int expected) throws Exception {
        mvc.perform(get(path).with(user(account(role)))).andExpect(status().is(expected));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/", "/school", "/social/friends", "/admin/users", "/admin/audit-log", "/admin/statistics"})
    void withoutLoginEveryPageAsksForIt(String path) throws Exception {
        mvc.perform(get(path)).andExpect(redirectedUrl("/auth/login"));
    }

    @Test
    void aMistypedAddressIsNotFoundForEveryRole() throws Exception {
        for (Role role : Role.values()) {
            mvc.perform(get("/no-such-page").with(user(account(role)))).andExpect(status().isNotFound());
        }
    }

    @Test
    void aRefusalSaysWhy() throws Exception {
        mvc.perform(get("/school").with(user(account(Role.AUDITOR))))
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.ROLE));
        mvc.perform(get("/school/devices/connect").with(user(account(Role.ADMIN))))
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.CONNECT));
        mvc.perform(post("/social/friends/1/add").with(user(account(Role.STUDENT)))) // no security code
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.FORM));
    }

    @Test
    void aNewRoleAppliesOnTheNextClick() throws Exception {
        User user = users.save(new User("an-" + UUID.randomUUID() + "@example.com", "An", "x", LayoutTest.SEPT_1));
        AppUser before = AppUser.of(user);
        user.changeRole(Role.AUDITOR, null, LocalDateTime.of(2026, 10, 6, 7, 0));

        mvc.perform(get("/school").with(user(before))).andExpect(status().isForbidden());
    }
}
```

Create `web/src/test/java/vn/edu/hcmiu/sla/core/RefusedPageTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.RequestDispatcher;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.UserRepository;

/**
 * The error page after a 403 (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.5). MockMvc doesn't follow
 * the server's error dispatch, so each test opens /error the way the server does: with the status, the address and
 * the reason Refusals put on the request.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RefusedPageTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    ResultActions errorPage(AppUser user, int status, String path, String reason) throws Exception {
        MockHttpServletRequestBuilder request = get("/error").accept(MediaType.TEXT_HTML)
                .requestAttr(RequestDispatcher.ERROR_STATUS_CODE, status)
                .requestAttr(RequestDispatcher.ERROR_REQUEST_URI, path);
        if (reason != null) {
            request.requestAttr(Refusals.REASON, reason);
        }
        return mvc.perform(user == null ? request : request.with(user(user)));
    }

    @Test
    void eachRoleIsToldWhatItsAccountOpens() throws Exception {
        errorPage(LayoutTest.account(users, Role.STUDENT), 403, "/admin/users", Refusals.ROLE)
                .andExpect(status().isForbidden())
                .andExpect(content().string(containsString("You can&#39;t open this page")))
                .andExpect(content().string(containsString(
                        "Your account is a student account: it can open School, Groups and Friends.")))
                .andExpect(content().string(not(containsString("id=\"log-out-to-switch\""))));
        errorPage(LayoutTest.account(users, Role.AUDITOR), 403, "/school", Refusals.ROLE)
                .andExpect(content().string(containsString(
                        "Your account is an Auditor account: it can open the Audit log and Statistics.")));
        errorPage(LayoutTest.account(users, Role.ADMIN), 403, "/school", Refusals.ROLE)
                .andExpect(content().string(containsString(
                        "Your account is an Admin account: it can open Users, the Audit log and Statistics.")));
    }

    @Test
    void aStaffAccountOnTheConnectPageIsToldToUseItsStudentAccount() throws Exception {
        errorPage(LayoutTest.account(users, Role.ADMIN), 403, "/school/devices/connect", Refusals.CONNECT)
                .andExpect(content().string(containsString(
                        "Only student accounts can connect a laptop. Log out and log in with your student account.")))
                .andExpect(content().string(containsString("id=\"log-out-to-switch\"")));
    }

    @Test
    void aFormWithoutItsSecurityCodeHasExpired() throws Exception {
        errorPage(null, 403, "/auth/login", Refusals.FORM)
                .andExpect(content().string(containsString("This form expired")))
                .andExpect(content().string(containsString("Go back, reload the page and try again.")));
    }

    @Test
    void pageNotFoundIsAsBefore() throws Exception {
        errorPage(LayoutTest.account(users, Role.STUDENT), 404, "/nope", null)
                .andExpect(status().isNotFound())
                .andExpect(content().string(containsString("Page not found")))
                .andExpect(content().string(not(containsString("You can&#39;t open this page"))));
    }
}
```

Create `web/src/test/java/vn/edu/hcmiu/sla/core/MethodSecurityTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;

/** The second check: @PreAuthorize on an action refuses the wrong role (spec 4.2), as stage 2's Users actions will. */
@SpringBootTest
@Import(MethodSecurityTest.AdminOnlyConfig.class)
class MethodSecurityTest {

    @TestConfiguration
    static class AdminOnlyConfig {
        @Bean
        AdminOnly adminOnly() {
            return new AdminOnly();
        }
    }

    public static class AdminOnly {
        @PreAuthorize("hasRole('ADMIN')")
        public String secret() {
            return "for Admins";
        }
    }

    @Autowired
    AdminOnly adminOnly;

    @AfterEach
    void logOut() {
        SecurityContextHolder.clearContext();
    }

    static void logInAs(Role role) {
        AppUser user = new AppUser(1, "a@example.com", "A", "x", role, true);
        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(user, null, user.getAuthorities()));
    }

    @Test
    void anActionForAdminsRefusesEveryoneElse() {
        logInAs(Role.STUDENT);
        assertThatThrownBy(adminOnly::secret).isInstanceOf(AccessDeniedException.class);
        logInAs(Role.AUDITOR);
        assertThatThrownBy(adminOnly::secret).isInstanceOf(AccessDeniedException.class);

        logInAs(Role.ADMIN);
        assertThat(adminOnly.secret()).isEqualTo("for Admins");
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='AccessListTest,AccessTest,RefusedPageTest,MethodSecurityTest'`
Expected: FAIL: compilation errors (`SecurityConfig.ANYONE` and `Refusals` don't exist).

- [ ] **Step 3: Write `Refusals`**

Create `web/src/main/java/vn/edu/hcmiu/sla/core/Refusals.java`:

```java
package vn.edu.hcmiu.sla.core;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.csrf.CsrfException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ModelAttribute;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;

/**
 * Why a page was refused (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.5). Spring Security calls
 * {@link #handle} for a role the access list doesn't allow and for a form without its security code (CSRF): the reason
 * goes on the request, then the server shows the error page (403), which explains it through the "refusal" model
 * attribute.
 */
@ControllerAdvice
public class Refusals implements AccessDeniedHandler {

    public static final String REASON = "sla.refusal";
    public static final String ROLE = "role";
    public static final String CONNECT = "connect";
    public static final String FORM = "form";

    static final String CONNECT_PAGE = "/school/devices/connect";
    static final String CANT_OPEN = "You can't open this page";

    /** What the 403 page says; offerLogOut adds a Log out button. */
    public record Refusal(String title, String text, boolean offerLogOut) {
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, AccessDeniedException denied)
            throws IOException {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        request.setAttribute(REASON, denied instanceof CsrfException ? FORM
                : path.equals(CONNECT_PAGE) || path.startsWith(CONNECT_PAGE + "/") ? CONNECT
                : ROLE);
        response.sendError(HttpServletResponse.SC_FORBIDDEN);
    }

    /** null on every page but a refused one. */
    @ModelAttribute("refusal")
    public Refusal refusal(HttpServletRequest request, @AuthenticationPrincipal AppUser user) {
        Object reason = request.getAttribute(REASON);
        if (reason == null) {
            return null;
        }
        if (FORM.equals(reason)) {
            return new Refusal("This form expired", "Go back, reload the page and try again.", false);
        }
        if (CONNECT.equals(reason)) {
            return new Refusal(CANT_OPEN,
                    "Only student accounts can connect a laptop. Log out and log in with your student account.", true);
        }
        return new Refusal(CANT_OPEN, user == null ? null : canOpen(user.role()), false);
    }

    static String canOpen(Role role) {
        return switch (role) {
            case STUDENT -> "Your account is a student account: it can open School, Groups and Friends.";
            case AUDITOR -> "Your account is an Auditor account: it can open the Audit log and Statistics.";
            case ADMIN -> "Your account is an Admin account: it can open Users, the Audit log and Statistics.";
        };
    }
}
```

- [ ] **Step 4: The access list, method security and the refusals handler in `SecurityConfig`**

In `SecurityConfig.java`:
- add imports `org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity` and `vn.edu.hcmiu.sla.auth.Role`;
- replace the class comment and declaration line with:
  ```java
  /**
   * Who may open what (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.2): the lists below, read top to
   * bottom; AccessListTest checks that every page is in one. Every form carries a CSRF token. Method security is on, so
   * an action can check the role a second time with @PreAuthorize.
   */
  @Configuration
  @EnableMethodSecurity
  public class SecurityConfig {

      static final String[] ANYONE = {"/auth/login", "/auth/register", "/css/**", "/js/**", "/error"};
      static final String[] STUDENTS = {"/school/**", "/social/**"};
      static final String[] ADMINS = {"/admin/users/**"};
      static final String[] STAFF = {"/admin/audit-log/**", "/admin/statistics/**"};
      static final String[] EVERY_ROLE = {"/", "/account/**", "/auth/logout"};
  ```
- change `pages(…)`'s signature to `SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn, Refusals refusals, UserRepository users, SecurityContextRepository logins) throws Exception`;
- replace its `.authorizeHttpRequests(…)` call with:
  ```java
                .authorizeHttpRequests(pages -> pages
                        .requestMatchers(ANYONE).permitAll()
                        .requestMatchers(STUDENTS).hasRole(Role.STUDENT.name())
                        .requestMatchers(ADMINS).hasRole(Role.ADMIN.name())
                        .requestMatchers(STAFF).hasAnyRole(Role.AUDITOR.name(), Role.ADMIN.name())
                        .requestMatchers(EVERY_ROLE).authenticated()
                        .anyRequest().authenticated()) // a mistyped address: "Page not found", for any role
  ```
- after the `.addFilterBefore(…)` line, add:
  ```java
                .exceptionHandling(refused -> refused.accessDeniedHandler(refusals))
  ```

`exceptionHandling`'s handler is also the one the security-code (CSRF) check uses.

- [ ] **Step 5: The error page explains 403**

Replace `web/src/main/resources/templates/error.html` with:

```html
<!doctype html>
<html xmlns:th="http://www.thymeleaf.org" th:replace="~{layout :: page(~{::title}, ~{::main})}">
<head>
  <title>Something went wrong · School-Life-Assistant</title>
</head>
<body>
<main>
  <section class="card narrow">
    <th:block th:if="${status == 404}">
      <h1>Page not found</h1>
      <p>That page doesn't exist, or it isn't yours.</p>
    </th:block>
    <th:block th:if="${status == 403}">
      <h1 th:if="${refusal != null}" th:text="${refusal.title}">You can't open this page</h1>
      <h1 th:unless="${refusal != null}">You can't open this page</h1>
      <p th:if="${refusal != null and refusal.text != null}" th:text="${refusal.text}">Your account is a student account: it can open School, Groups and Friends.</p>
      <form th:if="${refusal != null and refusal.offerLogOut}" id="log-out-to-switch" method="post" th:action="@{/auth/logout}">
        <button type="submit" class="button">Log out</button>
      </form>
    </th:block>
    <th:block th:unless="${status == 404 or status == 403}">
      <h1>Something went wrong</h1>
      <p>Please go back and try again.</p>
    </th:block>
    <p><a th:href="@{/}">Back to the start page</a></p>
  </section>
</main>
</body>
</html>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='AccessListTest,AccessTest,RefusedPageTest,MethodSecurityTest,LoginTest,RegisterTest'`
Expected: PASS. If `everyPageIsInTheAccessList` names an address, add its prefix to the right list (that is the test doing its job), not to the test.

Then `./mvnw -B test`. Expected: 812 tests, 0 failures, 1 skipped.

- [ ] **Step 7: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/core/Refusals.java web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/resources/templates/error.html web/src/test/java/vn/edu/hcmiu/sla/core/AccessListTest.java web/src/test/java/vn/edu/hcmiu/sla/core/AccessTest.java web/src/test/java/vn/edu/hcmiu/sla/core/RefusedPageTest.java web/src/test/java/vn/edu/hcmiu/sla/core/MethodSecurityTest.java
git commit -F - <<'EOF'
feat(web): one access list says which roles open which pages, and a refused page says why

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 5: A menu and home page per role

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/Navigation.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/core/NavigationTest.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java`

**Interfaces:**
- Consumes: `AppUser.role()` (Task 1); `LayoutTest.account` (Task 3).
- Produces: `Navigation.MODULES` becomes `Map<Role, List<String>>`; `navItems(null)` is an empty list. The home page (`main/index.html`) already shows one card per menu item, so staff get their own cards with no template change.

- [ ] **Step 1: Write the failing tests**

Replace `NavigationTest.java` with:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.transaction.CannotCreateTransactionException;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.core.Navigation.NavItem;

class NavigationTest {

    static final AppUser AN = account(Role.STUDENT);
    static final NavModule FRIENDS = new NavModule("Friends", "/social/friends");

    static AppUser account(Role role) {
        return new AppUser(7, "an@example.com", "An", "x", role, true);
    }

    @Test
    void everyModuleIsListedAndComingSoonUntilItRegisters() {
        assertThat(new Navigation(List.of(), List.of()).navItems(AN))
                .extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("School", null), tuple("Groups", null), tuple("Friends", null));
    }

    @Test
    void eachRoleHasItsOwnMenu() {
        Navigation navigation = new Navigation(List.of(), List.of());

        assertThat(navigation.navItems(account(Role.AUDITOR))).extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("Audit log", null), tuple("Statistics", null));
        assertThat(navigation.navItems(account(Role.ADMIN))).extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("Users", null), tuple("Audit log", null), tuple("Statistics", null));
    }

    @Test
    void staffMenusLeaveOutTheStudentModulesEvenOnceTheyExist() {
        Navigation navigation = new Navigation(List.of(new NavModule("School", "/school"), FRIENDS,
                new NavModule("Users", "/admin/users")), List.of());

        assertThat(navigation.navItems(account(Role.ADMIN))).extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("Users", "/admin/users"), tuple("Audit log", null), tuple("Statistics", null));
        assertThat(navigation.navItems(AN)).extracting(NavItem::label).containsExactly("School", "Groups", "Friends");
    }

    @Test
    void aRegisteredModuleGetsItsLink() {
        assertThat(new Navigation(List.of(new NavModule("School", "/school")), List.of()).navItems(AN))
                .extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("School", "/school"), tuple("Groups", null), tuple("Friends", null));
    }

    @Test
    void aModulesCountIsTheLoggedInStudents() {
        Navigation navigation = new Navigation(List.of(FRIENDS),
                List.of(new NavCount("Friends", userId -> userId == 7 ? 2 : 5)));

        assertThat(navigation.navItems(AN)).extracting(NavItem::count).containsExactly(0, 0, 2);
    }

    @Test
    void loggedOutThereIsNoMenu() {
        assertThat(new Navigation(List.of(FRIENDS), List.of(new NavCount("Friends", userId -> 2))).navItems(null))
                .isEmpty();
    }

    @Test
    void nothingIsCountedForAModuleNotBuiltYet() {
        assertThat(new Navigation(List.of(), List.of(new NavCount("Friends", userId -> 2))).navItems(AN))
                .extracting(NavItem::count).containsExactly(0, 0, 0);
    }

    @Test
    void aCountThatCantBeReadShowsNothingSoThePageStillOpens() {
        Navigation navigation = new Navigation(List.of(FRIENDS), List.of(new NavCount("Friends", userId -> {
            throw new DataAccessResourceFailureException("The database is down");
        })));

        assertThat(navigation.navItems(AN).get(2).count()).isZero(); // e.g. the error page, while the database is down

        Navigation noConnection = new Navigation(List.of(FRIENDS), List.of(new NavCount("Friends", userId -> {
            throw new CannotCreateTransactionException("No connection"); // what @Transactional gives when it is down
        })));
        assertThat(noConnection.navItems(AN).get(2).count()).isZero();
    }

    @Test
    void aCountIsWorkedOutOnlyWhenThePageShowsIt() {
        AtomicInteger asked = new AtomicInteger();
        Navigation navigation = new Navigation(List.of(FRIENDS),
                List.of(new NavCount("Friends", userId -> asked.incrementAndGet())));

        List<NavItem> items = navigation.navItems(AN);
        assertThat(asked).hasValue(0); // an API call that shows no menu costs nothing

        items.get(2).count();
        assertThat(asked).hasValue(1);
    }
}
```

In `LayoutTest.Pages`, add:

```java
        @Test
        void staffSeeTheirOwnPagesComingSoonAndNoStudentModules() throws Exception {
            String auditor = mvc.perform(get("/").with(user(account(users, Role.AUDITOR))))
                    .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
            assertThat(auditor)
                    .contains("<span class=\"nav-soon\" title=\"Coming soon\">Audit log</span>")
                    .contains("<span class=\"nav-soon\" title=\"Coming soon\">Statistics</span>")
                    .doesNotContain(">School<").doesNotContain(">Friends<");
            assertThat(auditor.split("class=\"card module-card", -1)).hasSize(3); // Audit log, Statistics

            String admin = mvc.perform(get("/").with(user(account(users, Role.ADMIN))))
                    .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
            assertThat(admin).contains("<span class=\"nav-soon\" title=\"Coming soon\">Users</span>");
            assertThat(admin.split("class=\"card module-card", -1)).hasSize(4); // Users, Audit log, Statistics
        }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='NavigationTest,LayoutTest*'`
Expected: FAIL in `eachRoleHasItsOwnMenu`, `staffMenusLeaveOutTheStudentModulesEvenOnceTheyExist`, `loggedOutThereIsNoMenu` and `staffSeeTheirOwnPagesComingSoonAndNoStudentModules` (everyone gets School · Groups · Friends).

- [ ] **Step 3: One menu per role**

In `Navigation.java`:
- add `import vn.edu.hcmiu.sla.auth.Role;`;
- change the class comment to "Gives every page the menu: the logged-in role's modules in a fixed order, with a link for each one that exists, and its count.";
- replace `static final List<String> MODULES = List.of("School", "Groups", "Friends");` with:
  ```java
      /** Each role's menu (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.3). */
      static final Map<Role, List<String>> MODULES = Map.of(
              Role.STUDENT, List.of("School", "Groups", "Friends"),
              Role.AUDITOR, List.of("Audit log", "Statistics"),
              Role.ADMIN, List.of("Users", "Audit log", "Statistics"));
  ```
- replace the `navItems` method with:
  ```java
      /** user is null on the login and register pages, which show no menu. */
      @ModelAttribute("navItems")
      public List<NavItem> navItems(@AuthenticationPrincipal AppUser user) {
          if (user == null) {
              return List.of();
          }
          return MODULES.get(user.role()).stream().map(label -> {
              String path = paths.get(label);
              NavCount count = counts.get(label);
              IntSupplier counter = path == null || count == null ? null : () -> count.of(user.id());
              return new NavItem(label, path, counter);
          }).toList();
      }
  ```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='NavigationTest,LayoutTest*,FriendsPageTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 816 tests, 0 failures, 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/core/Navigation.java web/src/test/java/vn/edu/hcmiu/sla/core/NavigationTest.java web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java
git commit -F - <<'EOF'
feat(web): each role gets its own menu and home cards; staff pages show as coming soon

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 6: Profile and Password pages

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/Sessions.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/ProfileForm.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/PasswordForm.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountController.java`
- Create: `web/src/main/resources/templates/auth/account.html`, `web/src/main/resources/templates/auth/password.html`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java`
- Modify: `web/src/main/resources/templates/layout.html`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/AccountPageTest.java`; `LayoutTest.java`

**Interfaces:**
- Consumes: `User.changeProfile`, `User.changePassword`, `Role.label()` (Task 1); `AccountCheck`'s `?changed` (Task 3); `/account/**` in `EVERY_ROLE` (Task 4).
- Produces: `@Component Sessions` with `void logIn(AppUser user, HttpServletRequest request, HttpServletResponse response)`.
- Produces on `Accounts`: `void changeProfile(Integer userId, String displayName, String email, LocalDateTime now)`, `User changePassword(Integer userId, String password, LocalDateTime now)`.
- Produces: `GET/POST /account`, `GET/POST /account/password`; "Profile" in every role's menu, before Log out.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/AccountPageTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.flash;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;
import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.core.Flash;
import vn.edu.hcmiu.sla.school.TestClock;

/** Profile and Password (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.4 and 5.5). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class AccountPageTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0); // 01/09/2026 07:00 in Vietnam
    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 6, 7, 5);   // 06/10/2026 14:05 in Vietnam

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    PasswordEncoder passwords;

    @Autowired
    TestClock clock;

    User an;

    @BeforeEach
    void anAccount() {
        an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));
        clock.set(NOW);
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    AppUser me() {
        return AppUser.of(an);
    }

    String page(String path) throws Exception {
        return mvc.perform(get(path).with(user(me()))).andExpect(status().isOk()).andReturn().getResponse()
                .getContentAsString();
    }

    MockHttpServletRequestBuilder saveProfile(String name, String email, String currentPassword) {
        return post("/account").with(user(me())).with(csrf())
                .param("displayName", name).param("email", email).param("currentPassword", currentPassword);
    }

    MockHttpServletRequestBuilder changePassword(String current, String password, String confirm) {
        return post("/account/password").with(user(me())).with(csrf())
                .param("currentPassword", current).param("password", password).param("confirm", confirm);
    }

    /** Logs in with the real login form: the returned session is a browser's. */
    MockHttpSession logIn() throws Exception {
        MockHttpSession session = new MockHttpSession();
        mvc.perform(post("/auth/login").session(session).with(csrf())
                        .param("email", "an@example.com").param("password", "correct-horse-8"))
                .andExpect(redirectedUrl("/"));
        return session;
    }

    // ---- Profile ---------------------------------------------------------------------

    @Test
    void theProfileShowsTheAccountInVietnamTime() throws Exception {
        an.loggedIn(NOW);

        assertThat(page("/account"))
                .contains("value=\"An\"")
                .contains("value=\"an@example.com\"")
                .contains("<dd>Student</dd>")
                .contains("<dd>01/09/2026</dd>")
                .contains("<dd>06/10/2026 14:05</dd>")
                .contains("href=\"/account/password\"");
    }

    @Test
    void anAccountThatNeverLoggedInSaysNever() throws Exception {
        assertThat(page("/account")).contains("<dd>Never</dd>");
    }

    @Test
    void everyRoleHasAProfile() throws Exception {
        for (Role role : Role.values()) {
            an.changeRole(role, null, NOW);

            assertThat(page("/account")).contains("<dd>" + role.label() + "</dd>");
        }
    }

    @Test
    void aNewNameIsSavedWithWhoAndWhen() throws Exception {
        mvc.perform(saveProfile("An Nguyen", "an@example.com", ""))
                .andExpect(redirectedUrl("/account"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("message", "Saved your profile."))));

        assertThat(an.getDisplayName()).isEqualTo("An Nguyen");
        assertThat(an.getUpdatedBy()).isEqualTo(an.getId());
        assertThat(an.getUpdatedAt()).isEqualTo(NOW);
    }

    @Test
    void theSameEmailInCapitalsOrWithSpacesNeedsNoPassword() throws Exception { // Review Focus
        mvc.perform(saveProfile("An", "  AN@Example.com ", "")).andExpect(redirectedUrl("/account"));

        assertThat(an.getEmail()).isEqualTo("an@example.com");
    }

    @Test
    void aNewEmailNeedsTheCurrentPassword() throws Exception {
        mvc.perform(saveProfile("An", "an.nguyen@example.com", ""))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Enter your current password to change your email.")));
        mvc.perform(saveProfile("An", "an.nguyen@example.com", "wrong-password"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Current password is incorrect.")));
        assertThat(an.getEmail()).isEqualTo("an@example.com");

        mvc.perform(saveProfile("An", "an.nguyen@example.com", "correct-horse-8")).andExpect(redirectedUrl("/account"));

        assertThat(an.getEmail()).isEqualTo("an.nguyen@example.com");
    }

    @Test
    void anEmailSomeoneElseHasIsRefused() throws Exception {
        users.save(new User("binh@example.com", "Binh", "x", SEPT_1));

        mvc.perform(saveProfile("An", "BINH@example.com", "correct-horse-8"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("This email is already registered.")));

        assertThat(an.getEmail()).isEqualTo("an@example.com");
    }

    @Test
    void theProfileChecksItsFieldsAndKeepsWhatWasTyped() throws Exception {
        mvc.perform(saveProfile("  ", "not-an-email", ""))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("This field is required.")))
                .andExpect(content().string(containsString("Invalid email address.")))
                .andExpect(content().string(containsString("value=\"not-an-email\"")));
        mvc.perform(saveProfile("n".repeat(101), "an@example.com", ""))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Field cannot be longer than 100 characters.")));

        assertThat(an.getDisplayName()).isEqualTo("An");
        assertThat(an.getEmail()).isEqualTo("an@example.com");
    }

    @Test
    void aNameWithHtmlIsShownAsText() throws Exception { // Review Focus
        mvc.perform(saveProfile("<b>\"Vy\"</b>", "an@example.com", "")).andExpect(redirectedUrl("/account"));

        assertThat(page("/account")).contains("value=\"&lt;b&gt;&quot;Vy&quot;&lt;/b&gt;\"")
                .doesNotContain("<b>\"Vy\"</b>");
        assertThat(page("/")).contains("Hi, &lt;b&gt;&quot;Vy&quot;&lt;/b&gt;");
    }

    @Test
    void theProfileFormNeedsItsSecurityCode() throws Exception {
        mvc.perform(post("/account").with(user(me())).param("displayName", "X").param("email", "an@example.com"))
                .andExpect(status().isForbidden());

        assertThat(an.getDisplayName()).isEqualTo("An");
    }

    @Test
    void theAccountPagesNeedLogin() throws Exception {
        mvc.perform(get("/account")).andExpect(redirectedUrl("/auth/login"));
        mvc.perform(get("/account/password")).andExpect(redirectedUrl("/auth/login"));
    }

    // ---- Password --------------------------------------------------------------------

    @Test
    void aNewPasswordIsSavedAndThisSessionStaysLoggedIn() throws Exception { // Review Focus: kept as typed
        MockHttpSession here = logIn();
        MockHttpSession elsewhere = logIn();

        mvc.perform(post("/account/password").session(here).with(csrf()).param("currentPassword", "correct-horse-8")
                        .param("password", "new horse 123 ").param("confirm", "new horse 123 "))
                .andExpect(redirectedUrl("/account"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("message", "Password changed."))));

        assertThat(passwords.matches("new horse 123 ", an.getPasswordHash())).isTrue();
        assertThat(an.getUpdatedAt()).isEqualTo(NOW);
        mvc.perform(get("/").session(here)).andExpect(status().isOk());
        mvc.perform(get("/").session(elsewhere)).andExpect(redirectedUrl("/auth/login?changed"));
    }

    @Test
    void thePasswordFormChecksEveryField() throws Exception {
        mvc.perform(changePassword("wrong-password", "new-horse-123", "new-horse-123"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Current password is incorrect.")));
        mvc.perform(changePassword("correct-horse-8", "short", "short"))
                .andExpect(content().string(containsString("Field must be between 8 and 128 characters long.")));
        mvc.perform(changePassword("correct-horse-8", "new-horse-123", "new-horse-321"))
                .andExpect(content().string(containsString("Passwords don&#39;t match.")));
        mvc.perform(changePassword("correct-horse-8", "correct-horse-8", "correct-horse-8"))
                .andExpect(content().string(containsString("Choose a password different from your current one.")));

        assertThat(an.getPasswordHash()).isEqualTo(WerkzeugPasswordEncoderTest.SCRYPT);
    }
}
```

In `LayoutTest.Pages`, add:

```java
        @Test
        void theMenuEndsWithProfileAndLogOutForEveryRole() throws Exception {
            for (Role role : Role.values()) {
                mvc.perform(get("/").with(user(account(users, role))))
                        .andExpect(content().string(containsString("<a href=\"/account\">Profile</a>")))
                        .andExpect(content().string(containsString("Log out")));
            }
        }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='AccountPageTest,LayoutTest*'`
Expected: FAIL: `/account` is 404, and the menu has no Profile link (`theAccountPagesNeedLogin` and `theProfileFormNeedsItsSecurityCode` may already pass).

- [ ] **Step 3: `Sessions`, and `AuthController` uses it**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/Sessions.java`:

```java
package vn.edu.hcmiu.sla.auth;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Component;

/**
 * Logs a person in for this browser, as the login form does: a new session id, then the account saved in the session.
 * Register uses it for a new account; Password uses it so the session that changed the password stays logged in
 * (AccountCheck logs out the others).
 */
@Component
public class Sessions {

    private final SecurityContextRepository logins;

    public Sessions(SecurityContextRepository logins) {
        this.logins = logins;
    }

    public void logIn(AppUser user, HttpServletRequest request, HttpServletResponse response) {
        if (request.getSession(false) != null) {
            request.changeSessionId(); // a new session id after login
        }
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(user, null, user.getAuthorities()));
        SecurityContextHolder.setContext(context);
        logins.saveContext(context, request, response);
    }
}
```

In `AuthController.java`:
- replace the field `private final SecurityContextRepository logins;` with `private final Sessions sessions;`, and the constructor with:
  ```java
      public AuthController(UserRepository users, PasswordEncoder passwords, Sessions sessions) {
          this.users = users;
          this.passwords = passwords;
          this.sessions = sessions;
      }
  ```
- in `register`, replace `logIn(AppUser.of(user), request, response);` with `sessions.logIn(AppUser.of(user), request, response);`;
- delete the private `logIn` method, and the imports it alone used: `UsernamePasswordAuthenticationToken`, `SecurityContext`, `SecurityContextHolder`, `SecurityContextRepository`.

- [ ] **Step 4: The two forms**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/ProfileForm.java`:

```java
package vn.edu.hcmiu.sla.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import vn.edu.hcmiu.sla.core.Text;

/** The Profile page's fields (spec 5.4): the name and email with register's rules and messages. */
public class ProfileForm {

    @NotBlank(message = RegisterForm.REQUIRED)
    @Size(max = 100, message = "Field cannot be longer than 100 characters.")
    private String displayName = "";

    @NotBlank(message = RegisterForm.REQUIRED)
    @Email(regexp = "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", message = "Invalid email address.")
    @Size(max = 255, message = "Field cannot be longer than 255 characters.")
    private String email = "";

    /** Needed only when the email changes. */
    private String currentPassword = "";

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName == null ? "" : Text.strip(displayName);
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = AppUserDetailsService.normalizeEmail(email);
    }

    public String getCurrentPassword() {
        return currentPassword;
    }

    public void setCurrentPassword(String currentPassword) {
        this.currentPassword = currentPassword == null ? "" : currentPassword;
    }
}
```

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/PasswordForm.java`:

```java
package vn.edu.hcmiu.sla.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** The Password page's fields (spec 5.5). Passwords are kept exactly as typed, as on register. */
public class PasswordForm {

    private String currentPassword = "";

    @Size(min = 8, max = 128, message = "Field must be between 8 and 128 characters long.")
    private String password = "";

    @NotBlank(message = RegisterForm.REQUIRED)
    private String confirm = "";

    public String getCurrentPassword() {
        return currentPassword;
    }

    public void setCurrentPassword(String currentPassword) {
        this.currentPassword = currentPassword == null ? "" : currentPassword;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password == null ? "" : password;
    }

    public String getConfirm() {
        return confirm;
    }

    public void setConfirm(String confirm) {
        this.confirm = confirm == null ? "" : confirm;
    }
}
```

- [ ] **Step 5: `Accounts` saves them**

In `Accounts.java`, add the import `org.springframework.security.crypto.password.PasswordEncoder`, a `passwords` field, and these methods; the constructor becomes `public Accounts(UserRepository users, PasswordEncoder passwords)`:

```java
    /** A new display name and email, both already checked by the Profile page (spec 5.4). */
    @Transactional
    public void changeProfile(Integer userId, String displayName, String email, LocalDateTime now) {
        users.findById(userId).orElseThrow().changeProfile(displayName, email, userId, now);
    }

    /** A new password the person chose themselves (spec 5.5); the account as saved. */
    @Transactional
    public User changePassword(Integer userId, String password, LocalDateTime now) {
        User user = users.findById(userId).orElseThrow();
        user.changePassword(passwords.encode(password), userId, now);
        return user;
    }
```

- [ ] **Step 6: The controller**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/AccountController.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import vn.edu.hcmiu.sla.core.Flash;

/** Profile and Password, for every role (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.4 and 5.5). */
@Controller
@RequestMapping("/account")
public class AccountController {

    private static final ZoneOffset VIETNAM = ZoneOffset.ofHours(7); // as School's VietnamTime, which auth can't use
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final DateTimeFormatter DATE_TIME = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm");

    private final UserRepository users;
    private final Accounts accounts;
    private final PasswordEncoder passwords;
    private final Sessions sessions;
    private final Clock clock;

    public AccountController(UserRepository users, Accounts accounts, PasswordEncoder passwords, Sessions sessions,
            Clock clock) {
        this.users = users;
        this.accounts = accounts;
        this.passwords = passwords;
        this.sessions = sessions;
        this.clock = clock;
    }

    static String vietnam(LocalDateTime utc, DateTimeFormatter format) {
        return utc.atOffset(ZoneOffset.UTC).withOffsetSameInstant(VIETNAM).format(format);
    }

    /** Every page has just re-read the account (AccountCheck), so it is there. */
    private User account(AppUser user) {
        return users.findById(user.id()).orElseThrow();
    }

    private static String profilePage(User account, Model model) {
        model.addAttribute("role", account.getRole().label());
        model.addAttribute("memberSince", vietnam(account.getCreatedAt(), DATE));
        model.addAttribute("lastLogin",
                account.getLastLoginAt() == null ? "Never" : vietnam(account.getLastLoginAt(), DATE_TIME));
        return "auth/account";
    }

    @GetMapping
    String profile(@AuthenticationPrincipal AppUser user, Model model) {
        User account = account(user);
        ProfileForm form = new ProfileForm();
        form.setDisplayName(account.getDisplayName());
        form.setEmail(account.getEmail());
        model.addAttribute("form", form);
        return profilePage(account, model);
    }

    @PostMapping
    String saveProfile(@AuthenticationPrincipal AppUser user, @Valid @ModelAttribute("form") ProfileForm form,
            BindingResult errors, Model model, RedirectAttributes redirect) {
        User account = account(user);
        boolean newEmail = !form.getEmail().equals(account.getEmail());
        if (newEmail && !errors.hasFieldErrors("email") && users.existsByEmail(form.getEmail())) {
            errors.rejectValue("email", "taken", "This email is already registered.");
        }
        if (newEmail && form.getCurrentPassword().isEmpty()) {
            errors.rejectValue("currentPassword", "required", "Enter your current password to change your email.");
        } else if (newEmail && !passwords.matches(form.getCurrentPassword(), account.getPasswordHash())) {
            errors.rejectValue("currentPassword", "wrong", "Current password is incorrect.");
        }
        if (errors.hasErrors()) {
            return profilePage(account, model);
        }
        accounts.changeProfile(user.id(), form.getDisplayName(), form.getEmail(), LocalDateTime.now(clock));
        Flash.success(redirect, "Saved your profile.");
        return "redirect:/account";
    }

    @GetMapping("/password")
    String passwordPage(Model model) {
        model.addAttribute("form", new PasswordForm());
        return "auth/password";
    }

    @PostMapping("/password")
    String changePassword(@AuthenticationPrincipal AppUser user, @Valid @ModelAttribute("form") PasswordForm form,
            BindingResult errors, HttpServletRequest request, HttpServletResponse response,
            RedirectAttributes redirect) {
        User account = account(user);
        if (!passwords.matches(form.getCurrentPassword(), account.getPasswordHash())) {
            errors.rejectValue("currentPassword", "wrong", "Current password is incorrect.");
        } else if (!errors.hasFieldErrors("password") && passwords.matches(form.getPassword(), account.getPasswordHash())) {
            errors.rejectValue("password", "same", "Choose a password different from your current one.");
        }
        if (!form.getConfirm().isEmpty() && !form.getConfirm().equals(form.getPassword())) {
            errors.rejectValue("confirm", "mismatch", "Passwords don't match.");
        }
        if (errors.hasErrors()) {
            return "auth/password";
        }
        User changed = accounts.changePassword(user.id(), form.getPassword(), LocalDateTime.now(clock));
        sessions.logIn(AppUser.of(changed), request, response); // this session goes on; AccountCheck ends the others
        Flash.success(redirect, "Password changed.");
        return "redirect:/account";
    }
}
```

- [ ] **Step 7: The pages, and Profile in the menu**

Create `web/src/main/resources/templates/auth/account.html`:

```html
<!doctype html>
<html xmlns:th="http://www.thymeleaf.org" th:replace="~{layout :: page(~{::title}, ~{::main})}">
<head>
  <title>Profile · School-Life-Assistant</title>
</head>
<body>
<main>
  <section class="card narrow">
    <h1>Profile</h1>
    <dl class="facts">
      <dt>Role</dt>
      <dd th:text="${role}">Student</dd>
      <dt>Member since</dt>
      <dd th:text="${memberSince}">01/09/2026</dd>
      <dt>Last login</dt>
      <dd th:text="${lastLogin}">06/10/2026 14:05</dd>
    </dl>
  </section>
  <section class="card narrow">
    <h2>Name and email</h2>
    <form method="post" th:action="@{/account}" th:object="${form}" novalidate>
      <div class="field">
        <label for="displayName">Display name</label>
        <input id="displayName" type="text" th:field="*{displayName}" maxlength="100" autocomplete="nickname">
        <p class="field-error" th:each="error : ${#fields.errors('displayName')}" th:text="${error}">This field is required.</p>
      </div>
      <div class="field">
        <label for="email">Email</label>
        <input id="email" type="email" th:field="*{email}" maxlength="255" autocomplete="email">
        <p class="field-error" th:each="error : ${#fields.errors('email')}" th:text="${error}">Invalid email address.</p>
      </div>
      <div class="field">
        <label for="currentPassword">Current password <span class="muted">(only to change your email)</span></label>
        <input id="currentPassword" type="password" th:field="*{currentPassword}" autocomplete="current-password">
        <p class="field-error" th:each="error : ${#fields.errors('currentPassword')}" th:text="${error}">Current password is incorrect.</p>
      </div>
      <button type="submit" class="button">Save</button>
    </form>
    <p><a th:href="@{/account/password}">Change your password</a></p>
  </section>
</main>
</body>
</html>
```

Create `web/src/main/resources/templates/auth/password.html`:

```html
<!doctype html>
<html xmlns:th="http://www.thymeleaf.org" th:replace="~{layout :: page(~{::title}, ~{::main})}">
<head>
  <title>Change password · School-Life-Assistant</title>
</head>
<body>
<main>
  <section class="card narrow">
    <h1>Change password</h1>
    <form method="post" th:action="@{/account/password}" th:object="${form}" novalidate>
      <div class="field">
        <label for="currentPassword">Current password</label>
        <input id="currentPassword" type="password" th:field="*{currentPassword}" autocomplete="current-password">
        <p class="field-error" th:each="error : ${#fields.errors('currentPassword')}" th:text="${error}">Current password is incorrect.</p>
      </div>
      <div class="field">
        <label for="password">New password</label>
        <input id="password" type="password" th:field="*{password}" maxlength="128" autocomplete="new-password">
        <p class="field-error" th:each="error : ${#fields.errors('password')}" th:text="${error}">Too short.</p>
      </div>
      <div class="field">
        <label for="confirm">Confirm new password</label>
        <input id="confirm" type="password" th:field="*{confirm}" maxlength="128" autocomplete="new-password">
        <p class="field-error" th:each="error : ${#fields.errors('confirm')}" th:text="${error}">Passwords don't match.</p>
      </div>
      <button type="submit" class="button">Change password</button>
    </form>
    <p><a th:href="@{/account}">Back to Profile</a></p>
  </section>
</main>
</body>
</html>
```

In `templates/layout.html`, right before `<form method="post" th:action="@{/auth/logout}" class="inline">`, add:

```html
      <a th:href="@{/account}">Profile</a>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='AccountPageTest,LayoutTest*,RegisterTest,LoginTest,AccountCheckTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 830 tests, 0 failures, 1 skipped.

- [ ] **Step 9: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/Sessions.java web/src/main/java/vn/edu/hcmiu/sla/auth/ProfileForm.java web/src/main/java/vn/edu/hcmiu/sla/auth/PasswordForm.java web/src/main/java/vn/edu/hcmiu/sla/auth/AccountController.java web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java web/src/main/resources/templates/auth/account.html web/src/main/resources/templates/auth/password.html web/src/main/resources/templates/layout.html web/src/test/java/vn/edu/hcmiu/sla/auth/AccountPageTest.java web/src/test/java/vn/edu/hcmiu/sla/core/LayoutTest.java
git commit -F - <<'EOF'
feat(web): Profile and Password pages for every role; a new password logs out your other sessions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 7: A laptop syncs only for an active Student

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/school/sync/DeviceKeys.java`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/school/sync/SyncApiTest.java`

**Interfaces:**
- Consumes: `User.isActiveStudent()` (Task 1).
- Produces: `DeviceKeys(SchoolSyncDeviceRepository devices, UserRepository users)`; `authenticate` (and so `checkIn`) is empty while the key's owner isn't an active Student. Keys are never cancelled by this.

- [ ] **Step 1: Write the failing tests**

In `SyncApiTest.java`, add the import `vn.edu.hcmiu.sla.auth.Role` and, after `aCancelledDeviceKeyGets401`:

```java
    // ---- Accounts that aren't active Students (site roles spec, 4.6) ----------

    static final LocalDateTime OCT_6 = LocalDateTime.of(2026, 10, 6, 7, 0);

    User owner() {
        return users.findByEmail("an@example.com").orElseThrow();
    }

    @Test
    void aDeactivatedAccountsLaptopGets401UntilTheAccountIsBack() throws Exception {
        owner().deactivate(null, OCT_6);

        check(key).andExpect(status().isUnauthorized())
                .andExpect(content().json("{\"error\": \"invalid_device_key\"}", JsonCompareMode.STRICT));
        assertThat(theDevice().getRevokedAt()).isNull(); // not cancelled

        owner().reactivate(null, OCT_6);
        check(key).andExpect(status().isOk());
    }

    @Test
    void aStaffAccountsLaptopGets401() throws Exception {
        owner().changeRole(Role.AUDITOR, null, OCT_6);
        check(key).andExpect(status().isUnauthorized());

        owner().changeRole(Role.STUDENT, null, OCT_6);
        check(key).andExpect(status().isOk());
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest=SyncApiTest`
Expected: FAIL in both new tests (the key still answers 200).

- [ ] **Step 3: Check the owner**

In `DeviceKeys.java`:
- add imports `vn.edu.hcmiu.sla.auth.User` and `vn.edu.hcmiu.sla.auth.UserRepository`;
- add the field `private final UserRepository users;` and make the constructor:
  ```java
      public DeviceKeys(SchoolSyncDeviceRepository devices, UserRepository users) {
          this.devices = devices;
          this.users = users;
      }
  ```
- replace `authenticate` with:
  ```java
      /**
       * The active device for this key, or empty; empty too while its owner isn't an active Student (deactivated, or a
       * staff role: spec 2026-10-06-site-roles-design.md, 4.6). The key isn't cancelled, so it works again once the
       * owner is an active Student.
       */
      @Transactional(readOnly = true)
      public Optional<SchoolSyncDevice> authenticate(String rawKey) {
          if (rawKey == null || rawKey.isEmpty()) {
              return Optional.empty();
          }
          return devices.findByTokenHashAndRevokedAtIsNull(hashKey(rawKey))
                  .filter(device -> users.findById(device.getUserId()).filter(User::isActiveStudent).isPresent());
      }
  ```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='SyncApiTest,ConnectApiTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 832 tests, 0 failures, 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/school/sync/DeviceKeys.java web/src/test/java/vn/edu/hcmiu/sla/school/sync/SyncApiTest.java
git commit -F - <<'EOF'
feat(web): a laptop stops syncing while its account is deactivated or not a Student, and starts again when it is

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 8: Friends only among active Students

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/social/friends/PeopleSearch.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/social/friends/Friends.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/social/model/SocialFriendshipRepository.java`
- Modify: `web/src/test/java/vn/edu/hcmiu/sla/social/SocialTestData.java`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/social/friends/FriendsTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/social/pages/FriendsPageTest.java`

**Interfaces:**
- Consumes: `User.isActiveStudent()`, `User.deactivate`, `User.reactivate`, `User.changeRole` (Task 1).
- Produces: `SocialTestData.deactivate(AppUser)`, `reactivate(AppUser)`, `giveRole(AppUser, Role)`. Find people, the three lists, the Friends count and the five buttons leave out (buttons: 404) anyone who isn't an active Student. Their rows stay.

- [ ] **Step 1: Write the failing tests**

In `SocialTestData.java`, add the import `vn.edu.hcmiu.sla.auth.Role` and:

```java
    /** That account deactivated, as an Admin would do it (site roles spec, 5.2). */
    public void deactivate(AppUser person) {
        db.find(User.class, person.id()).deactivate(null, SEPT_1);
        db.flush();
    }

    public void reactivate(AppUser person) {
        db.find(User.class, person.id()).reactivate(null, SEPT_1);
        db.flush();
    }

    /** That account given another role. */
    public void giveRole(AppUser person, Role role) {
        db.find(User.class, person.id()).changeRole(role, null, SEPT_1);
        db.flush();
    }
```

In `FriendsTest.java`, add the import `vn.edu.hcmiu.sla.auth.Role` and:

```java
    // ---- Accounts that aren't active Students (site roles spec, 5.2) --------------------

    @Test
    void findPeopleLeavesOutDeactivatedAndStaffAccounts() {
        data.person("Trang Le");
        data.deactivate(data.person("Trang Off"));
        data.giveRole(data.person("Trang Staff"), Role.AUDITOR);

        Page<PersonRow> found = friends.search(an.id(), "trang", 1);

        assertThat(names(found)).containsExactly("Trang Le");
        assertThat(found.getTotalElements()).isEqualTo(1);
    }

    @Test
    void theirRequestsAndFriendshipsAreHiddenUntilTheyAreBack() {
        AppUser lan = data.person("Lan");
        AppUser binh = data.person("Binh");
        AppUser cuong = data.person("Cuong");
        data.request(lan, an, NOW); // waiting for An
        data.request(an, binh, NOW); // An sent it
        data.friends(an, cuong);
        data.deactivate(lan);
        data.deactivate(binh);
        data.giveRole(cuong, Role.ADMIN);

        assertThat(friends.requestsFor(an.id())).isEmpty();
        assertThat(friends.requestsSentBy(an.id())).isEmpty();
        assertThat(friends.friendsOf(an.id())).isEmpty();
        assertThat(friends.countRequestsFor(an.id())).isZero();

        data.reactivate(lan);
        data.reactivate(binh);
        data.giveRole(cuong, Role.STUDENT);

        assertThat(friends.requestsFor(an.id())).extracting(Request::name).containsExactly("Lan");
        assertThat(friends.requestsSentBy(an.id())).extracting(Request::name).containsExactly("Binh");
        assertThat(friends.friendsOf(an.id())).extracting(Friend::name).containsExactly("Cuong");
        assertThat(friends.countRequestsFor(an.id())).isEqualTo(1);
    }

    @Test
    void everyButtonOnThemIsNotFoundAndTheirRowsStay() {
        AppUser lan = data.person("Lan");
        data.request(lan, an, NOW);
        data.deactivate(lan);

        assertThat(friends.add(an.id(), lan.id(), NOW)).isEmpty();
        assertThat(friends.accept(an.id(), lan.id(), NOW)).isEmpty();
        assertThat(friends.decline(an.id(), lan.id(), NOW)).isEmpty();
        assertThat(friends.cancel(an.id(), lan.id(), NOW)).isEmpty();
        assertThat(friends.remove(an.id(), lan.id(), NOW)).isEmpty();
        assertThat(friendships.findBetween(an.id(), lan.id())).isPresent(); // there again when Lan is back
    }
```

In `FriendsPageTest.java`, add the import `static org.springframework.test.web.servlet.result.MockMvcResultMatchers.model;` and:

```java
    @Test
    void someoneDeactivatedIsNotFoundAndNotCounted() throws Exception {
        AppUser lan = data.person("Lan");
        data.request(lan, an, NOW);
        data.deactivate(lan);

        mvc.perform(get("/social/friends").with(user(an)))
                .andExpect(model().attribute("forYou", List.of()));
        assertThat(page("/social/friends")).doesNotContain("nav-count");
        press("/social/friends/" + lan.id() + "/accept").andExpect(status().isNotFound());
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='FriendsTest,FriendsPageTest'`
Expected: FAIL in the four new tests (deactivated and staff accounts are still found, listed, counted, and their buttons work).

- [ ] **Step 3: Leave them out**

In `PeopleSearch.java`, replace the class comment's first sentence and the `MATCHING` line:

```java
/**
 * Accounts found by display name for Find people (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md,
 * 4.2): never the one searching, only active Students (site roles spec, 5.2), sorted by name. pattern comes from
 * {@link Friends#containsPattern}, with '!' as LIKE's escape character. On MySQL the column's collation also ignores
 * accents.
 */
public interface PeopleSearch extends Repository<User, Integer> {

    String MATCHING = "from User u where u.id <> :userId and u.role = 'student' and u.deactivatedAt is null"
            + " and lower(u.displayName) like :pattern escape '!'";
```

In `SocialFriendshipRepository.java`, replace `countRequestsFor` with:

```java
    /** Requests sent to this student that they haven't answered, from active Students only (site roles spec, 5.2). */
    @Query("select count(f) from SocialFriendship f, User u where u.id = f.requestedById and f.status = 'pending'"
            + " and f.requestedById <> :userId and (f.userLowId = :userId or f.userHighId = :userId)"
            + " and u.role = 'student' and u.deactivatedAt is null")
    long countRequestsFor(Integer userId);
```

In `Friends.java`:
- replace the class comment's last sentence with: "Every button is safe to press twice or from an out-of-date page: it does what still makes sense and says what happened. Someone who isn't an active Student (deactivated, or a staff role) is left out of every list and is "not found" for every button; their rows stay, for when they are back (site roles spec, 5.2)."
- in `requests(…)`, replace its `return` line with:
  ```java
          return rows.stream().filter(row -> names.containsKey(row.other(userId)))
                  .map(row -> new Request(row.other(userId), names.get(row.other(userId)), row.getCreatedAt()))
                  .toList();
  ```
- in `friendsOf(…)`, replace `return ids.stream().map(id -> new Friend(id, names.get(id)))` with `return ids.stream().filter(names::containsKey).map(id -> new Friend(id, names.get(id)))`;
- replace `names(…)` with:
  ```java
      /** The display names of those who are active Students; the others are left out. */
      private Map<Integer, String> names(Collection<Integer> ids) {
          return users.findAllById(ids).stream().filter(User::isActiveStudent)
                  .collect(Collectors.toMap(User::getId, User::getDisplayName));
      }
  ```
- replace `nameOf(…)` with:
  ```java
      /** The other person's display name; empty for an unknown id, the student themselves, or not an active Student. */
      private Optional<String> nameOf(Integer userId, Integer otherId) {
          return otherId.equals(userId) ? Optional.empty()
                  : users.findById(otherId).filter(User::isActiveStudent).map(User::getDisplayName);
      }
  ```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='FriendsTest,FriendsPageTest,FriendsRaceTest,SocialTablesTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 836 tests, 0 failures, 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/social/friends/PeopleSearch.java web/src/main/java/vn/edu/hcmiu/sla/social/friends/Friends.java web/src/main/java/vn/edu/hcmiu/sla/social/model/SocialFriendshipRepository.java web/src/test/java/vn/edu/hcmiu/sla/social/SocialTestData.java web/src/test/java/vn/edu/hcmiu/sla/social/friends/FriendsTest.java web/src/test/java/vn/edu/hcmiu/sla/social/pages/FriendsPageTest.java
git commit -F - <<'EOF'
feat(web): Friends leaves out deactivated and staff accounts until they are active Students again

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 9: The first Admin from `SITE_ADMIN_EMAIL`, the settings files and the README

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/FirstAdmin.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/UserRepository.java`
- Modify: `deploy/server/compose.yaml`, `deploy/server/.env.example`, `.env.example`, `render.yaml`
- Modify: `README.md`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/FirstAdminTest.java`

**Interfaces:**
- Consumes: `User.changeRole`, `User.reactivate`, `User.isActive` (Task 1); `AppUserDetailsService.normalizeEmail` (exists).
- Produces: `UserRepository.existsByRoleAndDeactivatedAtIsNull(String role)`; `FirstAdmin implements ApplicationRunner` with `Outcome promote()` (`NO_SETTING`, `ADMIN_EXISTS`, `NO_ACCOUNT`, `MADE_ADMIN`), constructor `FirstAdmin(UserRepository users, Clock clock, String email)`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/FirstAdminTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.LocalDateTime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.FirstAdmin.Outcome;

/** The first Admin, from SITE_ADMIN_EMAIL (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.3). */
@SpringBootTest
@Transactional
class FirstAdminTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);

    @Autowired
    UserRepository users;

    @Autowired
    JdbcTemplate jdbc;

    @Autowired
    Clock clock;

    @Autowired
    ApplicationContext context;

    @BeforeEach
    void noActiveAdminYet() {
        // Accounts other test classes left behind may include an Admin; this test's transaction undoes the change.
        jdbc.update("UPDATE users SET role = 'student' WHERE role = 'admin'");
    }

    User saved(String email) {
        return users.save(new User(email, "Boss", "x", SEPT_1));
    }

    FirstAdmin setting(String email) {
        return new FirstAdmin(users, clock, email);
    }

    @Test
    void withNoActiveAdminTheNamedAccountBecomesOne() { // Review Focus: capitals and spaces
        User boss = saved("boss@example.com");

        assertThat(setting(" Boss@Example.com ").promote()).isEqualTo(Outcome.MADE_ADMIN);

        assertThat(boss.getRole()).isEqualTo(Role.ADMIN);
        assertThat(boss.isActive()).isTrue();
        assertThat(boss.getUpdatedBy()).isNull(); // the site did it
        assertThat(users.existsByRoleAndDeactivatedAtIsNull("admin")).isTrue();
    }

    @Test
    void aDeactivatedAccountNamedIsTurnedBackOn() {
        User boss = saved("boss@example.com");
        boss.deactivate(null, SEPT_1);

        assertThat(setting("boss@example.com").promote()).isEqualTo(Outcome.MADE_ADMIN);

        assertThat(boss.isActive()).isTrue();
        assertThat(boss.getRole()).isEqualTo(Role.ADMIN);
    }

    @Test
    void anActiveAdminMeansTheSettingDoesNothing() {
        saved("admin@example.com").changeRole(Role.ADMIN, null, SEPT_1);
        User boss = saved("boss@example.com");

        assertThat(setting("boss@example.com").promote()).isEqualTo(Outcome.ADMIN_EXISTS);

        assertThat(boss.getRole()).isEqualTo(Role.STUDENT);
    }

    @Test
    void aDeactivatedAdminDoesntCount() {
        User old = saved("admin@example.com");
        old.changeRole(Role.ADMIN, null, SEPT_1);
        old.deactivate(null, SEPT_1);
        User boss = saved("boss@example.com");

        assertThat(setting("boss@example.com").promote()).isEqualTo(Outcome.MADE_ADMIN);

        assertThat(boss.getRole()).isEqualTo(Role.ADMIN);
    }

    @Test
    void noSettingOrAnUnknownEmailChangesNothing() {
        assertThat(setting("").promote()).isEqualTo(Outcome.NO_SETTING);
        assertThat(setting("   ").promote()).isEqualTo(Outcome.NO_SETTING);
        assertThat(setting("nobody@example.com").promote()).isEqualTo(Outcome.NO_ACCOUNT);

        assertThat(users.existsByRoleAndDeactivatedAtIsNull("admin")).isFalse();
    }

    @Test
    void theSiteRunsItEachTimeItStarts() {
        assertThat(context.getBean(FirstAdmin.class)).isInstanceOf(ApplicationRunner.class);
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest=FirstAdminTest`
Expected: FAIL: compilation errors (`FirstAdmin` doesn't exist).

- [ ] **Step 3: Write `FirstAdmin`**

In `UserRepository.java`, add:

```java
    /** Is there an active account with this role ("admin")? */
    boolean existsByRoleAndDeactivatedAtIsNull(String role);
```

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/FirstAdmin.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * The first Admin (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.3). Each time the site starts, after the
 * migrations: if it has no active Admin, the account named by SITE_ADMIN_EMAIL (.env) becomes one. Once an Admin
 * exists the setting does nothing, so it never undoes an Admin's decisions; it is also the way back if every Admin is
 * ever lost.
 */
@Component
class FirstAdmin implements ApplicationRunner {

    /** What a start did with the setting. */
    enum Outcome { NO_SETTING, ADMIN_EXISTS, NO_ACCOUNT, MADE_ADMIN }

    private static final Logger LOG = LoggerFactory.getLogger(FirstAdmin.class);

    private final UserRepository users;
    private final Clock clock;
    private final String email;

    FirstAdmin(UserRepository users, Clock clock, @Value("${SITE_ADMIN_EMAIL:}") String email) {
        this.users = users;
        this.clock = clock;
        this.email = email;
    }

    @Override
    public void run(ApplicationArguments args) {
        promote();
    }

    Outcome promote() {
        String wanted = AppUserDetailsService.normalizeEmail(email);
        if (wanted.isEmpty()) {
            return Outcome.NO_SETTING;
        }
        if (users.existsByRoleAndDeactivatedAtIsNull(Role.ADMIN.code())) {
            return Outcome.ADMIN_EXISTS;
        }
        Optional<User> account = users.findByEmail(wanted);
        if (account.isEmpty()) {
            LOG.warn("SITE_ADMIN_EMAIL names no account: {}. Register it on the site, then restart.", wanted);
            return Outcome.NO_ACCOUNT;
        }
        User admin = account.get();
        LocalDateTime now = LocalDateTime.now(clock);
        if (!admin.isActive()) {
            admin.reactivate(null, now);
        }
        admin.changeRole(Role.ADMIN, null, now);
        users.save(admin);
        LOG.info("Made {} an Admin (SITE_ADMIN_EMAIL)", wanted);
        return Outcome.MADE_ADMIN;
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest=FirstAdminTest`
Expected: PASS (6 tests).

- [ ] **Step 5: The settings files**

In `deploy/server/compose.yaml`, under `web:` → `environment:`, after the `SERVER_FORWARD_HEADERS_STRATEGY` line add:

```yaml
      # The first Admin: this account becomes one while the site has no active Admin (README, "Accounts and roles").
      SITE_ADMIN_EMAIL: ${SITE_ADMIN_EMAIL:-}
```

At the end of `deploy/server/.env.example`, add:

```
# The first Admin (README, "Accounts and roles"): register that account on the site, write its email here, then run
# update.sh. Once the site has an active Admin this does nothing; it can stay empty.
SITE_ADMIN_EMAIL=
```

At the end of the root `.env.example`, add:

```
# The first Admin on your laptop (README, "Accounts and roles"): register that account, write its email here and
# restart the site. Once the site has an active Admin this does nothing; it can stay empty.
SITE_ADMIN_EMAIL=
```

In `render.yaml`, at the end of `envVars:`, add:

```yaml
      # The first Admin (README, "Accounts and roles"); it can stay empty.
      - key: SITE_ADMIN_EMAIL
        sync: false
```

- [ ] **Step 6: The README**

1. After the `- **Friends** (Vy): …` line in the intro, add:
   ```markdown
   - **Accounts and roles**: every account is a Student, an Auditor or an Admin, and has a Profile and a Password page ([design](docs/superpowers/specs/2026-10-06-site-roles-design.md)).
   ```
2. Before `## Rules for the Java code`, add this section (and the `---` line after it, as the other sections have):
   ```markdown
   ## Accounts and roles

   Every account has one role. Everyone who registers is a Student.

   | Role | Sees |
   |---|---|
   | Student | School, Groups, Friends |
   | Auditor | Audit log and Statistics, read-only (coming soon) |
   | Admin | Users, Audit log and Statistics (coming soon) |

   Every role has **Profile** (name and email) and **Change password**. Which role may open which address is one list at the top of `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java`; `AccessListTest` fails when a page's address isn't in it. A deactivated account can't log in, its laptop stops syncing and other students don't see it; its data stays.

   **The first Admin.** Staff accounts have no School, so the Admin is an account of its own, not your student account:

   1. Register the admin account on the site, as anyone does.
   2. Write its email in the settings: `SITE_ADMIN_EMAIL=admin@example.com` in `.env` on your laptop, or in `deploy/server/.env` on the server.
   3. Restart the site (on the server: `bash ~/School-Life-Assistant/deploy/server/update.sh`). While the site has no active Admin, that account becomes one; once it has one, the setting does nothing.
   ```
3. Rule 1 becomes:
   ```markdown
   1. URLs start with the module name (`/school/...`, `/social/...`), tables with the module name (`school_...`, `social_...`). Site-wide pages (`/account`, and `/admin` for staff) and tables (`users`) have no module name.
   ```
4. In rule 3, at the end of the paragraph that starts "Social rows are shared between students", add: "Friends also leaves out anyone who isn't an active Student (deactivated, or a staff role): they aren't found, as an unknown person isn't."
5. In rule 5, replace "with module 1 for School and 2 for Social:" with "with module 0 for site-wide tables (Site), 1 for School and 2 for Social:".

- [ ] **Step 7: Run everything**

Run: `./mvnw -B test`
Expected: 842 tests, 0 failures, 1 skipped (`accentsAreIgnoredOnMySql`).

- [ ] **Step 8: Look at it in the browser**

Start the site (`./mvnw spring-boot:run` from `web/`, with the laptop's `.env`) and check by hand at 1400 px and 390 px wide:
- register a new account for staff use; put its email in `.env` as `SITE_ADMIN_EMAIL`, restart: the log says "Made … an Admin (SITE_ADMIN_EMAIL)", and that account's menu reads Users · Audit log · Statistics (grey, coming soon) · Profile · Log out, with three cards;
- your student account still reads School · Groups · Friends · Profile · Log out;
- as the Admin, type `/school` in the address bar: "You can't open this page" and the Admin sentence;
- Profile: change the name (the home page greets the new name), try a new email without the password (the message), change the password, then log in again with it;
- deactivate the student account by hand in MySQL (`UPDATE users SET deactivated_at = UTC_TIMESTAMP() WHERE email = '…';`): its open tab is logged out at the next click with the deactivated message; logging in with the right password shows it, a wrong one shows "Email or password is incorrect."; then `UPDATE users SET deactivated_at = NULL WHERE email = '…';`.

Stop the site with Ctrl+C.

- [ ] **Step 9: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/FirstAdmin.java web/src/main/java/vn/edu/hcmiu/sla/auth/UserRepository.java web/src/test/java/vn/edu/hcmiu/sla/auth/FirstAdminTest.java deploy/server/compose.yaml deploy/server/.env.example .env.example render.yaml README.md
git commit -F - <<'EOF'
feat(web): SITE_ADMIN_EMAIL makes the first Admin; the README explains roles and module 0

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 10: Hand back**

Report the test totals (Java: baseline 753 → the new total, 0 failures). Merging into `main`, pushing to the three repositories and `update.sh` on the server are not part of this plan: ask the student first. GitHub's MySQL job must pass before the merge: it is the only run that applies the role CHECK and the new migration on MySQL. After the merge, the live site's first Admin needs the README's three steps.
