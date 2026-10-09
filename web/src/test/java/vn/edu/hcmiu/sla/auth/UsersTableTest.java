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
