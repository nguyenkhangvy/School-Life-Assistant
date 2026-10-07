package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.LocalDateTime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import vn.edu.hcmiu.sla.core.Attempts;
import vn.edu.hcmiu.sla.school.TestClock;

/** The two login rules (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.3). */
class LoginLimitsTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);
    static final String IP = "198.51.100.1";
    static final String OTHER_IP = "198.51.100.2";

    final TestClock clock = new TestClock();
    final LoginLimits limits = new LoginLimits(new Attempts(clock));

    @BeforeEach
    void now() {
        clock.set(NOW);
    }

    void failed(String email, int times) {
        for (int i = 0; i < times; i++) {
            limits.failed(email, IP);
        }
    }

    @Test
    void fiveWrongPasswordsForOneEmailFromOneIpMeanWaiting() {
        failed("an@example.com", 4);
        assertThat(limits.waitFor("an@example.com", IP)).isZero();

        failed("an@example.com", 1);

        assertThat(limits.waitFor("an@example.com", IP)).isEqualTo(Duration.ofMinutes(15));
        assertThat(limits.waitFor("an@example.com", OTHER_IP)).isZero(); // the owner at home
        assertThat(limits.waitFor("binh@example.com", IP)).isZero();
    }

    @Test
    void theBlockIgnoresCapitalsAndSpacesInTheEmail() { // Review Focus
        failed("an@example.com", 5);

        assertThat(limits.waitFor(" AN@Example.com ", IP)).isEqualTo(Duration.ofMinutes(15));
    }

    @Test
    void aHundredWrongPasswordsFromOneIpBlockEveryEmailFromIt() {
        for (int i = 0; i < 99; i++) {
            limits.failed("person" + i + "@example.com", IP);
        }
        assertThat(limits.waitFor("an@example.com", IP)).isZero();

        limits.failed("person99@example.com", IP);

        assertThat(limits.waitFor("an@example.com", IP)).isEqualTo(Duration.ofMinutes(15));
        assertThat(limits.waitFor("an@example.com", OTHER_IP)).isZero();
    }

    @Test
    void theRightPasswordClearsThePairButNotTheIpCount() {
        failed("an@example.com", 4);
        limits.succeeded("an@example.com", IP);
        failed("an@example.com", 4);
        assertThat(limits.waitFor("an@example.com", IP)).isZero(); // the pair started again at 0

        for (int i = 0; i < 92; i++) {
            limits.failed("person" + i + "@example.com", IP);
        }

        assertThat(limits.waitFor("binh@example.com", IP)).isEqualTo(Duration.ofMinutes(15)); // 8 + 92 = 100
    }

    @Test
    void theWaitEndsWhenTheWindowHasPassed() {
        failed("an@example.com", 5);

        clock.set(NOW.plusMinutes(14));
        assertThat(limits.waitFor("an@example.com", IP)).isEqualTo(Duration.ofMinutes(1));
        clock.set(NOW.plusMinutes(15));
        assertThat(limits.waitFor("an@example.com", IP)).isZero();
    }
}
