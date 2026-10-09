package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.server.PathContainer;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;
import org.springframework.web.util.pattern.PathPatternParser;

/**
 * Every address the site serves is in SecurityConfig's access list
 * (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.2), so a new module can't be left open to every role.
 */
@SpringBootTest
class AccessListTest {

    /** Served by SyncApiConfig's own filter chain, which checks the laptop's device key instead of a login. */
    static final String[] LAPTOP = {"/api/school/sync/**"};

    @Autowired
    @Qualifier("requestMappingHandlerMapping")
    RequestMappingHandlerMapping pages;

    /** Whether an address as mapped (/school/courses/{courseId}) falls in one of the lists. */
    static boolean listed(String mapping) {
        PathContainer path = PathContainer.parsePath(mapping.replaceAll("\\{[^}]*}", "1"));
        return Stream.of(SecurityConfig.ANYONE, SecurityConfig.STUDENTS, SecurityConfig.ADMINS, SecurityConfig.STAFF,
                        SecurityConfig.EVERY_ROLE, LAPTOP)
                .flatMap(Arrays::stream)
                .anyMatch(pattern -> PathPatternParser.defaultInstance.parse(pattern).matches(path));
    }

    @Test
    void everyPageIsInTheAccessList() {
        List<String> mappings = pages.getHandlerMethods().keySet().stream()
                .flatMap(info -> info.getPatternValues().stream()).distinct().sorted().toList();

        assertThat(mappings).contains("/", "/school", "/social/friends", "/error", "/api/school/sync/check");
        assertThat(mappings).allSatisfy(mapping -> assertThat(listed(mapping))
                .as("%s is in an access list in SecurityConfig", mapping).isTrue());
    }

    @Test
    void anAddressOutsideTheListsIsCaught() {
        assertThat(listed("/expense/items")).isFalse();
        assertThat(listed("/admin/other")).isFalse();
        assertThat(listed("/school/courses/{courseId}")).isTrue();
        assertThat(listed("/admin/users/{id}/edit")).isTrue();
    }
}
