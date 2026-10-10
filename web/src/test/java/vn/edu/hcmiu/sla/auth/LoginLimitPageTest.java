package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;

import java.net.URI;
import java.time.LocalDateTime;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.TestClock;

/**
 * Login limits on the real login form (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.3). Each test
 * sends from an IP of its own, so tests never add to each other's counts.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class LoginLimitPageTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);
    static final String RIGHT = "correct-horse-8";
    static final String WRONG = "wrong-password";

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    TestClock clock;

    User an;

    @BeforeEach
    void anAccount() {
        clock.set(NOW);
        an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT,
                LocalDateTime.of(2026, 9, 1, 0, 0)));
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    static RequestPostProcessor from(String ip) {
        return request -> {
            request.setRemoteAddr(ip);
            return request;
        };
    }

    ResultActions logIn(String email, String password, String ip) throws Exception {
        return mvc.perform(post("/auth/login").with(csrf()).with(from(ip))
                .param("email", email).param("password", password));
    }

    void wrong(int times, String ip) throws Exception {
        for (int i = 0; i < times; i++) {
            logIn("an@example.com", WRONG, ip).andExpect(redirectedUrl("/auth/login?error"));
        }
    }

    @Test
    void fiveWrongPasswordsMakeEvenTheRightOneWait() throws Exception {
        wrong(5, "198.51.100.11");

        logIn("an@example.com", RIGHT, "198.51.100.11").andExpect(redirectedUrl("/auth/login?wait=15"));
        assertThat(an.getLastLoginAt()).isNull(); // the password wasn't even checked
        mvc.perform(get("/auth/login").param("wait", "15"))
                .andExpect(content().string(containsString("Too many wrong passwords. Try again in 15 minutes.")));

        clock.set(NOW.plusMinutes(15));
        logIn("an@example.com", RIGHT, "198.51.100.11").andExpect(redirectedUrl("/"));
    }

    @Test
    void theOwnerOnAnotherNetworkStillLogsIn() throws Exception {
        wrong(5, "198.51.100.12");

        logIn("an@example.com", RIGHT, "198.51.100.13").andExpect(redirectedUrl("/"));
    }

    @Test
    void anUnknownEmailIsCountedTheSameWay() throws Exception {
        for (int i = 0; i < 5; i++) {
            logIn("nobody@example.com", WRONG, "198.51.100.14").andExpect(redirectedUrl("/auth/login?error"));
        }

        logIn("nobody@example.com", WRONG, "198.51.100.14").andExpect(redirectedUrl("/auth/login?wait=15"));
    }

    @Test
    void triesWhileBlockedDontMakeTheWaitLonger() throws Exception {
        wrong(5, "198.51.100.15");

        clock.set(NOW.plusMinutes(10));
        for (int i = 0; i < 5; i++) {
            logIn("an@example.com", WRONG, "198.51.100.15").andExpect(redirectedUrl("/auth/login?wait=5"));
        }

        clock.set(NOW.plusMinutes(15));
        logIn("an@example.com", RIGHT, "198.51.100.15").andExpect(redirectedUrl("/"));
    }

    @Test
    void theDeactivatedAnswerIsNotCounted() throws Exception {
        an.deactivate(null, NOW);

        for (int i = 0; i < 6; i++) {
            logIn("an@example.com", RIGHT, "198.51.100.16").andExpect(redirectedUrl("/auth/login?deactivated"));
        }
    }

    @Test
    void aRightPasswordStartsThePairAgain() throws Exception {
        wrong(4, "198.51.100.17");
        logIn("an@example.com", RIGHT, "198.51.100.17").andExpect(redirectedUrl("/"));

        wrong(4, "198.51.100.17");
        logIn("an@example.com", RIGHT, "198.51.100.17").andExpect(redirectedUrl("/"));
    }

    @Test
    void visitorsInOneIpv6NetworkShareTheirLimit() throws Exception {
        for (int i = 1; i <= 5; i++) {
            logIn("an@example.com", WRONG, "2001:db8:1:2::" + i).andExpect(redirectedUrl("/auth/login?error"));
        }

        logIn("an@example.com", RIGHT, "2001:db8:1:2::99").andExpect(redirectedUrl("/auth/login?wait=15"));
    }

    @Test
    void aWaitInTheAddressIsOnlyShownWhenItIsAFewDigits() throws Exception { // Review Focus
        mvc.perform(get("/auth/login").param("wait", "1"))
                .andExpect(content().string(containsString("Too many wrong passwords. Try again in 1 minute.")));
        for (String typed : new String[] {"abc", "<b>x</b>", "999", "0"}) {
            mvc.perform(get("/auth/login").param("wait", typed))
                    .andExpect(content().string(not(containsString("Too many wrong passwords"))))
                    .andExpect(content().string(not(containsString("<b>x</b>"))));
        }
    }

    @Test
    void aLoginAddressWithAnEncodedLetterWaitsToo() throws Exception { // final review: /auth/log%69n is /auth/login
        wrong(5, "198.51.100.18");

        mvc.perform(post(URI.create("/auth/log%69n")).with(csrf()).with(from("198.51.100.18"))
                        .param("email", "an@example.com").param("password", RIGHT))
                .andExpect(redirectedUrl("/auth/login?wait=15"));
        assertThat(an.getLastLoginAt()).isNull();
    }
}
