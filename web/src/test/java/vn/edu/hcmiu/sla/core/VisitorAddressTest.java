package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;

/**
 * Whose address the limits count, on a real server as behind Caddy (docs/superpowers/specs/2026-10-07-security-hardening-design.md,
 * 3.2): the X-Forwarded-For that Caddy writes, never a Forwarded header the visitor sent, which Caddy passes on as it
 * is. The Connect trade-in shows it: 20 wrong codes from one address, then 429 for that address only. The same
 * annotations as SecurityHeadersTest, so both share one server.
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@AutoConfigureMockMvc
class VisitorAddressTest {

    @Value("${local.server.port}")
    int port;

    /** A trade-in of a code that doesn't exist (400 invalid_code), sent through "Caddy" for the given visitor. */
    int tradeIn(String visitor, String forwarded) throws Exception {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/school/sync/connect"))
                .header("Content-Type", "application/json")
                .header("X-Forwarded-For", visitor)
                .POST(HttpRequest.BodyPublishers.ofString(
                        "{\"code\": \"" + "A".repeat(43) + "\", \"verifier\": \"" + "A".repeat(43) + "\"}"));
        if (forwarded != null) {
            request.header("Forwarded", forwarded);
        }
        return HttpClient.newHttpClient().send(request.build(), HttpResponse.BodyHandlers.discarding()).statusCode();
    }

    @Test
    void theLimitsCountCaddysAddressForTheVisitorNotOneTheyClaim() throws Exception { // final review
        for (int i = 0; i < 20; i++) {
            assertThat(tradeIn("203.0.113.80", "for=198.51.100.200")).isEqualTo(400);
        }

        assertThat(tradeIn("203.0.113.80", null)).isEqualTo(429);
        assertThat(tradeIn("198.51.100.200", null)).isEqualTo(400); // the address they claimed wasn't counted
        assertThat(tradeIn("203.0.113.81", null)).isEqualTo(400); // and neither was the server's own
    }
}
