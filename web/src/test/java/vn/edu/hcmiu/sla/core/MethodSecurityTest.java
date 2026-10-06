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
