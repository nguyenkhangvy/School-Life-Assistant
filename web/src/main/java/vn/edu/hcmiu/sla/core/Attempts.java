package vn.edu.hcmiu.sla.core;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

/**
 * Counts events per key within a time window, in memory (docs/superpowers/specs/2026-10-07-security-hardening-design.md,
 * 3.1): wrong passwords, new accounts, failed Connect trade-ins. The site runs as one server, so memory is exact; a
 * restart clears every count. A key keeps only events younger than an hour, the longest window; above 10,000 keys, an
 * add first drops every key whose newest event is older than that.
 */
@Component
public class Attempts {

    static final Duration KEPT = Duration.ofHours(1);
    static final int SWEEP_ABOVE = 10_000;

    private final Clock clock;
    private final Map<String, List<Instant>> events = new ConcurrentHashMap<>();

    public Attempts(Clock clock) {
        this.clock = clock;
    }

    /** One event for this key, now. */
    public void add(String key) {
        Instant now = clock.instant();
        if (events.size() > SWEEP_ABOVE) {
            Instant stale = now.minus(KEPT);
            events.values().removeIf(times -> !times.get(times.size() - 1).isAfter(stale));
        }
        events.compute(key, (name, old) -> {
            List<Instant> kept = new ArrayList<>(since(old, now.minus(KEPT)));
            kept.add(now);
            return List.copyOf(kept);
        });
    }

    /** The events for this key within the window that ends now. */
    public int count(String key, Duration window) {
        return since(events.get(key), clock.instant().minus(window)).size();
    }

    /** How long until fewer than limit events for this key are within the window; zero when they already are. */
    public Duration waitFor(String key, int limit, Duration window) {
        Instant now = clock.instant();
        List<Instant> recent = since(events.get(key), now.minus(window));
        if (recent.size() < limit) {
            return Duration.ZERO;
        }
        Duration wait = Duration.between(now, recent.get(recent.size() - limit).plus(window));
        return wait.isNegative() ? Duration.ZERO : wait;
    }

    public void clear(String key) {
        events.remove(key);
    }

    /** How many keys are held: what the sweep keeps small. */
    int size() {
        return events.size();
    }

    /** A wait in whole minutes, rounded up, at least 1. */
    public static long minutes(Duration wait) {
        return Math.max(1, (wait.toMillis() + 59_999) / 60_000);
    }

    /** "1 minute", "12 minutes": a wait as pages say it. */
    public static String inMinutes(Duration wait) {
        long minutes = minutes(wait);
        return minutes == 1 ? "1 minute" : minutes + " minutes";
    }

    /** The times after the given moment, oldest first. */
    private static List<Instant> since(List<Instant> times, Instant after) {
        return times == null ? List.of() : times.stream().filter(time -> time.isAfter(after)).toList();
    }
}
