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
        String idBefore = here.getId();

        mvc.perform(post("/account/password").session(here).with(csrf()).param("currentPassword", "correct-horse-8")
                        .param("password", "new horse 123 ").param("confirm", "new horse 123 "))
                .andExpect(redirectedUrl("/account"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("message", "Password changed."))));

        assertThat(here.getId()).isNotEqualTo(idBefore); // a new session id, so a copied cookie stops working
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
