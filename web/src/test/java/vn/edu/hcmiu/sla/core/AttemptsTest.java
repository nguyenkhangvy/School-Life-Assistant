package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.LocalDateTime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import vn.edu.hcmiu.sla.school.TestClock;

/** The in-memory limiter (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.1). */
class AttemptsTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);
    static final Duration FIFTEEN = Duration.ofMinutes(15);

    final TestClock clock = new TestClock();
    final Attempts attempts = new Attempts(clock);

    @BeforeEach
    void now() {
        clock.set(NOW);
    }

    void at(LocalDateTime time) {
        clock.set(time);
    }

    @Test
    void countsOnlyEventsWithinTheWindow() {
        attempts.add("k");
        at(NOW.plusMinutes(5));
        attempts.add("k");
        at(NOW.plusMinutes(10));
        attempts.add("k");

        assertThat(attempts.count("k", FIFTEEN)).isEqualTo(3);
        at(NOW.plusMinutes(15)); // the first one leaves now
        assertThat(attempts.count("k", FIFTEEN)).isEqualTo(2);
        at(NOW.plusMinutes(26));
        assertThat(attempts.count("k", FIFTEEN)).isZero();
    }

    @Test
    void keysAreCountedApartAndClearedOneByOne() {
        attempts.add("a");
        attempts.add("a");
        attempts.add("b");

        attempts.clear("a");

        assertThat(attempts.count("a", FIFTEEN)).isZero();
        assertThat(attempts.count("b", FIFTEEN)).isEqualTo(1);
        assertThat(attempts.count("never", FIFTEEN)).isZero();
    }

    @Test
    void waitForIsZeroBelowTheLimitAndCountsDownFromTheOldest() {
        attempts.add("k");
        at(NOW.plusMinutes(1));
        attempts.add("k");
        assertThat(attempts.waitFor("k", 3, FIFTEEN)).isZero();

        at(NOW.plusMinutes(2));
        attempts.add("k");
        at(NOW.plusMinutes(3));

        assertThat(attempts.waitFor("k", 3, FIFTEEN)).isEqualTo(Duration.ofMinutes(12)); // the oldest leaves at NOW+15
    }

    @Test
    void pastTheLimitTheWaitLastsUntilEnoughHaveLeft() { // Review Focus: two tries at the same moment
        attempts.add("k");
        at(NOW.plusMinutes(1));
        attempts.add("k");
        at(NOW.plusMinutes(2));
        attempts.add("k");
        attempts.add("k"); // 4 events, limit 3
        at(NOW.plusMinutes(3));

        assertThat(attempts.waitFor("k", 3, FIFTEEN)).isEqualTo(Duration.ofMinutes(13)); // NOW+1 must leave too
    }

    @Test
    void waitsArePutInWholeMinutesRoundedUp() {
        assertThat(Attempts.inMinutes(Duration.ofSeconds(1))).isEqualTo("1 minute");
        assertThat(Attempts.inMinutes(Duration.ofMinutes(1))).isEqualTo("1 minute");
        assertThat(Attempts.inMinutes(Duration.ofSeconds(61))).isEqualTo("2 minutes");
        assertThat(Attempts.inMinutes(Duration.ofMinutes(15))).isEqualTo("15 minutes");
        assertThat(Attempts.minutes(Duration.ofMillis(900_500))).isEqualTo(16);
    }

    @Test
    void aboveTenThousandKeysAnAddDropsTheStaleOnes() {
        for (int i = 0; i <= Attempts.SWEEP_ABOVE; i++) {
            attempts.add("old-" + i); // 10,001 keys, all at NOW
        }
        at(NOW.plusMinutes(30));
        attempts.add("fresh-1"); // a sweep runs, but nothing is an hour old yet
        assertThat(attempts.size()).isEqualTo(Attempts.SWEEP_ABOVE + 2);

        at(NOW.plusMinutes(61));
        attempts.add("fresh-2"); // now the old keys are

        assertThat(attempts.size()).isEqualTo(2); // fresh-1 and fresh-2
    }
}
