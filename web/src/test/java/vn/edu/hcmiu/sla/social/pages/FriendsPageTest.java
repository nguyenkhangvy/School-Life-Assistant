package vn.edu.hcmiu.sla.social.pages;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.flash;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.IntStream;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.core.Flash;
import vn.edu.hcmiu.sla.school.TestClock;
import vn.edu.hcmiu.sla.social.SocialTestData;
import vn.edu.hcmiu.sla.social.model.SocialFriendshipRepository;

/** The Friends page and its buttons (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 4.1 and 4.2). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class FriendsPageTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 6, 7, 0); // Tue 06/10/2026 14:00 in Vietnam

    @Autowired
    MockMvc mvc;

    @Autowired
    EntityManager db;

    @Autowired
    TestClock clock;

    @Autowired
    SocialFriendshipRepository friendships;

    SocialTestData data;
    AppUser an;

    @BeforeEach
    void anAccount() {
        data = new SocialTestData(db);
        an = data.person("An");
        clock.set(NOW);
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    String page(String path) throws Exception {
        return mvc.perform(get(path).with(user(an))).andExpect(status().isOk()).andReturn().getResponse()
                .getContentAsString();
    }

    /** A button: POST with the security code, and name/value pairs ("q", "lan"). */
    ResultActions press(String path, String... params) throws Exception {
        MockHttpServletRequestBuilder request = post(path).with(user(an)).with(csrf());
        for (int i = 0; i < params.length; i += 2) {
            request.param(params[i], params[i + 1]);
        }
        return mvc.perform(request);
    }

    static List<Flash> message(String text) {
        return List.of(new Flash("message", text));
    }

    // ---- The page ----------------------------------------------------------------------

    @Test
    void theFriendsPageNeedsLogin() throws Exception {
        mvc.perform(get("/social/friends")).andExpect(redirectedUrl("/auth/login"));
    }

    @Test
    void theMenuLinksFriendsAndShowsGroupsAsComingSoon() throws Exception {
        assertThat(page("/social/friends"))
                .contains("<a href=\"/social/friends\">Friends</a>")
                .contains("<span class=\"nav-soon\" title=\"Coming soon\">Groups</span>");
        assertThat(page("/")).contains("<a class=\"card module-card\" href=\"/social/friends\">");
    }

    @Test
    void anEmptyPageSaysWhatToDo() throws Exception {
        assertThat(page("/social/friends"))
                .contains("No friends yet. Find people above.")
                .contains("No requests.")
                .doesNotContain("Showing");
    }

    @Test
    void aSearchNeedsTwoLetters() throws Exception {
        String html = mvc.perform(get("/social/friends").param("q", " L ").with(user(an))).andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(); // spaces don't count as letters

        assertThat(html).contains("Type at least 2 letters.").doesNotContain("Showing");
    }

    @Test
    void searchResultsShowNamesWithTheRightButtonButNeverEmails() throws Exception {
        AppUser asked = data.person("Lan Asked");
        AppUser asker = data.person("Lan Asker");
        AppUser friend = data.person("Lan Friend");
        AppUser stranger = data.person("Lan Stranger");
        data.request(an, asked, NOW);
        data.request(asker, an, NOW);
        data.friends(an, friend);

        String html = page("/social/friends?q=lan");

        assertThat(html)
                .contains("Showing 1–4 of 4 people")
                .contains("action=\"/social/friends/" + stranger.id() + "/add\"")
                .contains("action=\"/social/friends/" + asked.id() + "/cancel\"")
                .contains("action=\"/social/friends/" + asker.id() + "/accept\"")
                .contains("Friends ✓")
                .doesNotContain("@example.com");
    }

    @Test
    void nobodyFoundSaysSo() throws Exception {
        assertThat(page("/social/friends?q=zzqq")).contains("No one found for “zzqq”.");
    }

    @Test
    void longResultsArePaged() throws Exception {
        IntStream.rangeClosed(1, 25).forEach(n -> data.person(String.format("Lan %02d", n)));

        assertThat(page("/social/friends?q=lan"))
                .contains("Showing 1–20 of 25 people")
                .contains("Lan 20")
                .doesNotContain("Lan 21")
                .contains("href=\"/social/friends?q=lan&amp;page=2\"");
        assertThat(page("/social/friends?q=lan&page=2")).contains("Showing 21–25 of 25 people").contains("Lan 25");
        assertThat(page("/social/friends?q=lan&page=abc")).contains("Showing 1–20 of 25 people");
        assertThat(page("/social/friends?q=lan&page=7")).contains("Showing 21–25 of 25 people");
        assertThat(page("/social/friends?q=lan&page=2147483647")).contains("Showing 21–25 of 25 people");
    }

    @Test
    void requestsShowWhenTheyWereSent() throws Exception {
        data.request(data.person("Lan"), an, NOW.minusDays(1));
        data.request(an, data.person("Binh"), NOW);

        assertThat(page("/social/friends")).contains("Sent 05/10/2026").contains("Sent 06/10/2026");
    }

    @Test
    void requestsWaitingShowInTheMenu() throws Exception {
        data.request(data.person("Lan"), an, NOW);

        assertThat(page("/")).contains("<a href=\"/social/friends\" aria-label=\"Friends, 1 waiting for you\">Friends"
                + "<span class=\"nav-count\" title=\"1 waiting for you\">1</span></a>");
    }

    @Test
    void removingAsksFirstWithoutRunningTheName() throws Exception {
        AppUser odd = data.person("O'Brien <b>\"x\"</b>");
        data.friends(an, odd);

        String html = page("/social/friends");

        assertThat(html)
                .contains("data-confirm=\"Remove O")
                .contains("/js/confirm.js")
                .doesNotContain("onsubmit")
                .doesNotContain("<b>\"x\"</b>");
    }

    // ---- The buttons -------------------------------------------------------------------

    @Test
    void addingFromASearchReturnsToThatSearchWithAMessage() throws Exception {
        AppUser lanAnh = data.person("Lan Anh");

        press("/social/friends/" + lanAnh.id() + "/add", "q", " lan anh ", "page", "1")
                .andExpect(redirectedUrl("/social/friends?q=lan%20anh&page=1"))
                .andExpect(flash().attribute("flashes", message("Friend request sent to Lan Anh.")));
        assertThat(friendships.findBetween(an.id(), lanAnh.id())).isPresent();
    }

    @Test
    void aVietnameseSearchSurvivesTheRedirect() throws Exception {
        AppUser vy = data.person("Vỹ");

        press("/social/friends/" + vy.id() + "/add", "q", "Vỹ", "page", "2")
                .andExpect(redirectedUrl("/social/friends?q=V%E1%BB%B9&page=2"));
    }

    @Test
    void requestsForYouCanBeAcceptedOrDeclined() throws Exception {
        AppUser lan = data.person("Lan");
        AppUser binh = data.person("Binh");
        data.request(lan, an, NOW.minusDays(1));
        data.request(binh, an, NOW);

        press("/social/friends/" + lan.id() + "/accept")
                .andExpect(redirectedUrl("/social/friends"))
                .andExpect(flash().attribute("flashes", message("You and Lan are now friends.")));
        press("/social/friends/" + binh.id() + "/decline")
                .andExpect(flash().attribute("flashes", message("Declined Binh's request.")));

        assertThat(friendships.findBetween(an.id(), lan.id()).orElseThrow().isAccepted()).isTrue();
        assertThat(friendships.findBetween(an.id(), binh.id())).isEmpty();
    }

    @Test
    void yourRequestsCanBeCancelledAndFriendsRemoved() throws Exception {
        AppUser lan = data.person("Lan");
        AppUser binh = data.person("Binh");
        data.request(an, lan, NOW);
        data.friends(binh, an);

        press("/social/friends/" + lan.id() + "/cancel")
                .andExpect(flash().attribute("flashes", message("Cancelled your request to Lan.")));
        press("/social/friends/" + binh.id() + "/remove")
                .andExpect(flash().attribute("flashes", message("Removed Binh from your friends.")));

        assertThat(friendships.findAllOf(an.id())).isEmpty();
    }

    @Test
    void staleClicksSayWhatHappened() throws Exception {
        AppUser lan = data.person("Lan");

        press("/social/friends/" + lan.id() + "/accept")
                .andExpect(redirectedUrl("/social/friends"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("error", "That request is no longer waiting."))));
    }

    @Test
    void anUnknownPersonOrYourselfIs404() throws Exception {
        press("/social/friends/999999/add").andExpect(status().isNotFound());
        press("/social/friends/" + an.id() + "/add").andExpect(status().isNotFound());
        press("/social/friends/999999/remove").andExpect(status().isNotFound());
    }

    @Test
    void buttonsNeedTheSecurityCode() throws Exception {
        AppUser lan = data.person("Lan");

        mvc.perform(post("/social/friends/" + lan.id() + "/add").with(user(an))).andExpect(status().isForbidden());

        assertThat(friendships.findBetween(an.id(), lan.id())).isEmpty();
    }
}
