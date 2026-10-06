package vn.edu.hcmiu.sla.core;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;

/** Each role opens only its own pages (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.1 and 4.2). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class AccessTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    AppUser account(Role role) {
        return LayoutTest.account(users, role);
    }

    /** 404: allowed, but the page comes in stage 2 (Users) or 3 (Audit log, Statistics). */
    @ParameterizedTest(name = "{0} opens {1}: {2}")
    @CsvSource({
        "STUDENT, /,                  200",
        "STUDENT, /school,            200",
        "STUDENT, /social/friends,    200",
        "STUDENT, /admin/users,       403",
        "STUDENT, /admin/audit-log,   403",
        "STUDENT, /admin/statistics,  403",
        "AUDITOR, /,                  200",
        "AUDITOR, /school,            403",
        "AUDITOR, /school/timetable,  403",
        "AUDITOR, /social/friends,    403",
        "AUDITOR, /admin/users,       403",
        "AUDITOR, /admin/audit-log,   404",
        "AUDITOR, /admin/statistics,  404",
        "ADMIN,   /,                  200",
        "ADMIN,   /school,            403",
        "ADMIN,   /social/friends,    403",
        "ADMIN,   /admin/users,       404",
        "ADMIN,   /admin/audit-log,   404",
        "ADMIN,   /admin/statistics,  404"})
    void eachRoleOpensOnlyItsOwnPages(Role role, String path, int expected) throws Exception {
        mvc.perform(get(path).with(user(account(role)))).andExpect(status().is(expected));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/", "/school", "/social/friends", "/admin/users", "/admin/audit-log", "/admin/statistics"})
    void withoutLoginEveryPageAsksForIt(String path) throws Exception {
        mvc.perform(get(path)).andExpect(redirectedUrl("/auth/login"));
    }

    @Test
    void aMistypedAddressIsNotFoundForEveryRole() throws Exception {
        for (Role role : Role.values()) {
            mvc.perform(get("/no-such-page").with(user(account(role)))).andExpect(status().isNotFound());
        }
    }

    @Test
    void aRefusalSaysWhy() throws Exception {
        mvc.perform(get("/school").with(user(account(Role.AUDITOR))))
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.ROLE));
        mvc.perform(get("/school/devices/connect").with(user(account(Role.ADMIN))))
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.CONNECT));
        mvc.perform(post("/social/friends/1/add").with(user(account(Role.STUDENT)))) // no security code
                .andExpect(status().isForbidden())
                .andExpect(request().attribute(Refusals.REASON, Refusals.FORM));
    }

    @Test
    void aNewRoleAppliesOnTheNextClick() throws Exception {
        User user = users.save(new User("an-" + UUID.randomUUID() + "@example.com", "An", "x", LayoutTest.SEPT_1));
        AppUser before = AppUser.of(user);
        user.changeRole(Role.AUDITOR, null, LocalDateTime.of(2026, 10, 6, 7, 0));

        mvc.perform(get("/school").with(user(before))).andExpect(status().isForbidden());
    }
}
