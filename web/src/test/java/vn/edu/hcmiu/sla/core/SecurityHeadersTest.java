package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

/**
 * The security headers on both filter chains (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 5). The
 * error page needs a real server: Spring Security writes the headers while the first request fails, and Tomcat keeps
 * them when it forwards to /error; MockMvc doesn't forward.
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@AutoConfigureMockMvc
class SecurityHeadersTest {

    static final String CSP = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; "
            + "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            + "base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*";

    static final Map<String, String> HEADERS = Map.of(
            "Content-Security-Policy", CSP,
            "Referrer-Policy", "same-origin",
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            "X-Content-Type-Options", "nosniff",
            "X-Frame-Options", "DENY");

    @Autowired
    MockMvc mvc;

    @Value("${local.server.port}")
    int port;

    static void hasTheHeaders(ResultActions result) {
        MockHttpServletResponse response = result.andReturn().getResponse();
        HEADERS.forEach((name, value) -> assertThat(response.getHeader(name)).as(name).isEqualTo(value));
    }

    @Test
    void aPageHasThem() throws Exception {
        hasTheHeaders(mvc.perform(get("/auth/login")));
    }

    @Test
    void theErrorPageHasThem() throws Exception {
        HttpRequest missing = HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/css/nope.css"))
                .header("Accept", "text/html").build();

        HttpResponse<String> page = HttpClient.newHttpClient().send(missing, HttpResponse.BodyHandlers.ofString());

        assertThat(page.statusCode()).isEqualTo(404);
        assertThat(page.body()).contains("Page not found"); // the site's error page, from Tomcat's forward to /error
        HEADERS.forEach((name, value) -> assertThat(page.headers().firstValue(name)).as(name).hasValue(value));
    }

    @Test
    void theLaptopsSyncApiHasThem() throws Exception {
        hasTheHeaders(mvc.perform(get("/api/school/sync/check"))); // its own filter chain; refused, but with headers
    }
}
