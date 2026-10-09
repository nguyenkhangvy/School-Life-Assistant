package vn.edu.hcmiu.sla.core;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.RequestDispatcher;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.UserRepository;

/**
 * The error page after a 403 (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.5). MockMvc doesn't follow
 * the server's error dispatch, so each test opens /error the way the server does: with the status, the address and
 * the reason Refusals put on the request.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RefusedPageTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    ResultActions errorPage(AppUser user, int status, String path, String reason) throws Exception {
        MockHttpServletRequestBuilder request = get("/error").accept(MediaType.TEXT_HTML)
                .requestAttr(RequestDispatcher.ERROR_STATUS_CODE, status)
                .requestAttr(RequestDispatcher.ERROR_REQUEST_URI, path);
        if (reason != null) {
            request.requestAttr(Refusals.REASON, reason);
        }
        return mvc.perform(user == null ? request : request.with(user(user)));
    }

    @Test
    void eachRoleIsToldWhatItsAccountOpens() throws Exception {
        errorPage(LayoutTest.account(users, Role.STUDENT), 403, "/admin/users", Refusals.ROLE)
                .andExpect(status().isForbidden())
                .andExpect(content().string(containsString("You can&#39;t open this page")))
                .andExpect(content().string(containsString(
                        "Your account is a student account: it can open School, Groups and Friends.")))
                .andExpect(content().string(not(containsString("id=\"log-out-to-switch\""))));
        errorPage(LayoutTest.account(users, Role.AUDITOR), 403, "/school", Refusals.ROLE)
                .andExpect(content().string(containsString(
                        "Your account is an Auditor account: it can open the Audit log and Statistics.")));
        errorPage(LayoutTest.account(users, Role.ADMIN), 403, "/school", Refusals.ROLE)
                .andExpect(content().string(containsString(
                        "Your account is an Admin account: it can open Users, the Audit log and Statistics.")));
    }

    @Test
    void aStaffAccountOnTheConnectPageIsToldToUseItsStudentAccount() throws Exception {
        errorPage(LayoutTest.account(users, Role.ADMIN), 403, "/school/devices/connect", Refusals.CONNECT)
                .andExpect(content().string(containsString(
                        "Only student accounts can connect a laptop. Log out and log in with your student account.")))
                .andExpect(content().string(containsString("id=\"log-out-to-switch\"")));
    }

    @Test
    void aFormWithoutItsSecurityCodeHasExpired() throws Exception {
        errorPage(null, 403, "/auth/login", Refusals.FORM)
                .andExpect(content().string(containsString("This form expired")))
                .andExpect(content().string(containsString("Go back, reload the page and try again.")));
    }

    @Test
    void pageNotFoundIsAsBefore() throws Exception {
        errorPage(LayoutTest.account(users, Role.STUDENT), 404, "/nope", null)
                .andExpect(status().isNotFound())
                .andExpect(content().string(containsString("Page not found")))
                .andExpect(content().string(not(containsString("You can&#39;t open this page"))));
    }
}
