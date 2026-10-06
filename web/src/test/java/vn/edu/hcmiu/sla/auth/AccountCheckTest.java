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
