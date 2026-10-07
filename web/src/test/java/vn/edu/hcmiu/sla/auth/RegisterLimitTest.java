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

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.TestClock;

/** The register honeypot and per-IP limit (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.4). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class RegisterLimitTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    TestClock clock;

    @BeforeEach
    void now() {
        clock.set(NOW);
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    ResultActions register(String email, String ip, String website) throws Exception {
        return mvc.perform(post("/auth/register").with(csrf()).with(LoginLimitPageTest.from(ip))
                .param("email", email).param("displayName", "An")
                .param("password", "correct-horse-8").param("confirm", "correct-horse-8")
                .param("website", website));
    }

    @Test
    void aFilledHoneypotMakesNoAccount() throws Exception {
        register("an@example.com", "198.51.100.30", "https://spam.example")
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Please try again.")))
                .andExpect(content().string(containsString("value=\"an@example.com\"")));

        assertThat(users.findByEmail("an@example.com")).isEmpty();
    }

    @Test
    void theHoneypotIsHiddenFromKeyboardAndScreenReaders() throws Exception { // Review Focus
        String page = mvc.perform(get("/auth/register")).andReturn().getResponse().getContentAsString();

        assertThat(page).contains("<div class=\"trap\" aria-hidden=\"true\">")
                .containsPattern("<input id=\"website\"[^>]*tabindex=\"-1\"")
                .containsPattern("<input id=\"website\"[^>]*autocomplete=\"off\"");
    }

    @Test
    void thirtyNewAccountsFromOneNetworkInAnHourThenAWait() throws Exception {
        for (int i = 1; i <= 30; i++) {
            register("person" + i + "@example.com", "198.51.100.31", "").andExpect(redirectedUrl("/"));
        }

        register("person31@example.com", "198.51.100.31", "")
                .andExpect(status().isOk())
                .andExpect(content().string(containsString(
                        "Too many new accounts from this network. Try again in 60 minutes.")));
        assertThat(users.findByEmail("person31@example.com")).isEmpty();
        register("person31@example.com", "198.51.100.32", "").andExpect(redirectedUrl("/"));

        clock.set(NOW.plusHours(1));
        register("person32@example.com", "198.51.100.31", "").andExpect(redirectedUrl("/"));
    }

    @Test
    void refusedSignUpsDontCount() throws Exception {
        for (int i = 1; i <= 35; i++) {
            register("bot" + i + "@example.com", "198.51.100.33", "https://spam.example");
        }

        register("an@example.com", "198.51.100.33", "").andExpect(redirectedUrl("/"));
    }
}
