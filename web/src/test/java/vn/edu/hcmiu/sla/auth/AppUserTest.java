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
