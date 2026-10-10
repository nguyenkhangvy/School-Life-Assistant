package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

/** Argon2id passwords, old scrypt ones upgraded at login (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 4). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class PasswordHashTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);
    static final String ARGON2ID = "{argon2}$argon2id$v=19$m=19456,t=2,p=1$";

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    PasswordEncoder passwords;

    ResultActions logIn(MockHttpSession session, String email, String password) throws Exception {
        return mvc.perform(post("/auth/login").session(session).with(csrf())
                .with(LoginLimitPageTest.from("192.0.2.40")).param("email", email).param("password", password));
    }

    @Test
    void newPasswordsAreArgon2id() {
        String hash = passwords.encode("correct-horse-8");

        assertThat(hash).startsWith(ARGON2ID).hasSizeLessThan(255);
        assertThat(passwords.matches("correct-horse-8", hash)).isTrue();
        assertThat(passwords.matches("correct-horse-9", hash)).isFalse();
    }

    @Test
    void oldScryptHashesStillMatch() {
        assertThat(passwords.matches("correct-horse-8", WerkzeugPasswordEncoderTest.SCRYPT)).isTrue();
        assertThat(passwords.matches("mật khẩu 123", WerkzeugPasswordEncoderTest.SCRYPT_VIETNAMESE)).isTrue();
        assertThat(passwords.matches("wrong-password", WerkzeugPasswordEncoderTest.SCRYPT)).isFalse();
    }

    @Test
    void aPlaceholderHashFailsWithoutAnError() throws Exception {
        assertThat(passwords.matches("x", "x")).isFalse();
        users.save(new User("an@example.com", "An", "x", SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "x").andExpect(redirectedUrl("/auth/login?error"));
    }

    @Test
    void anOldAccountIsUpgradedAtLoginAndStaysLoggedIn() throws Exception {
        User an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));
        MockHttpSession session = new MockHttpSession();

        logIn(session, "an@example.com", "correct-horse-8").andExpect(redirectedUrl("/"));

        assertThat(an.getPasswordHash()).startsWith(ARGON2ID);
        assertThat(passwords.matches("correct-horse-8", an.getPasswordHash())).isTrue();
        assertThat(an.getUpdatedAt()).isEqualTo(SEPT_1); // nobody changed anything
        assertThat(an.getUpdatedBy()).isNull();
        mvc.perform(get("/").session(session)).andExpect(status().isOk()); // not logged out as "password changed"
    }

    @Test
    void aWrongPasswordLeavesAnOldHashAlone() throws Exception {
        User an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "wrong-password").andExpect(redirectedUrl("/auth/login?error"));

        assertThat(an.getPasswordHash()).isEqualTo(WerkzeugPasswordEncoderTest.SCRYPT);
    }

    @Test
    void anArgon2idAccountIsNotHashedAgain() throws Exception {
        String hash = passwords.encode("correct-horse-8");
        User an = users.save(new User("an@example.com", "An", hash, SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "correct-horse-8").andExpect(redirectedUrl("/"));

        assertThat(an.getPasswordHash()).isEqualTo(hash);
    }
}
