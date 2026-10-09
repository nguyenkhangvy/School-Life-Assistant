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
