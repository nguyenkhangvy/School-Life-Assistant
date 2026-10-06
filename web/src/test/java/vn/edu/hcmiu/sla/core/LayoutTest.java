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
