package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;

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
import org.springframework.web.servlet.mvc.support.RedirectAttributesModelMap;

import vn.edu.hcmiu.sla.auth.AppUser;

class LayoutTest {

    static final AppUser AN = new AppUser(1, "an@example.com", "An", "x");

    /** The real site, with whichever modules exist: nothing here depends on which ones (see NavigationTest). */
    @Nested
    @SpringBootTest
    @AutoConfigureMockMvc
    class Pages {

        @Autowired
        MockMvc mvc;

        @Test
        void theDashboardGreetsYouWithOneCardPerModule() throws Exception {
            String page = mvc.perform(get("/").with(user(AN)))
                    .andExpect(status().isOk())
                    .andExpect(content().string(containsString("Hi, An")))
                    .andExpect(content().string(containsString("href=\"/css/style.css\"")))
                    .andReturn().getResponse().getContentAsString();

            assertThat(page.split("class=\"card module-card", -1)).hasSize(4); // School, Groups, Friends
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

        @Test
        void aModuleThatRegistersItselfGetsALinkAndACard() throws Exception {
            mvc.perform(get("/").with(user(AN)))
                    .andExpect(content().string(containsString("<a href=\"/school\">School</a>")))
                    .andExpect(content().string(containsString("<a class=\"card module-card\" href=\"/school\">")));
        }
    }

    @Nested
    @SpringBootTest
    @AutoConfigureMockMvc
    @Import(WithACount.FriendsWithTwo.class)
    class WithACount {

        @TestConfiguration
        static class FriendsWithTwo {
            @Bean
            @Order(Ordered.HIGHEST_PRECEDENCE) // before the real Friends count, which would say 0
            NavModule friendsNav() {
                return new NavModule("Friends", "/social/friends");
            }

            @Bean
            @Order(Ordered.HIGHEST_PRECEDENCE)
            NavCount friendsCount() {
                return new NavCount("Friends", userId -> 2);
            }
        }

        @Autowired
        MockMvc mvc;

        @Test
        void aModulesCountComesAfterItsLabel() throws Exception {
            mvc.perform(get("/").with(user(AN)))
                    .andExpect(content().string(containsString("<a href=\"/social/friends\">Friends"
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
