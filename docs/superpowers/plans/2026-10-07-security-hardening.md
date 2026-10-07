# Security hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit wrong passwords, new accounts and failed laptop Connect trade-ins; refuse bots with a honeypot; hash new passwords with Argon2id and upgrade old ones at login; send Content-Security-Policy, Referrer-Policy and Permissions-Policy headers; and let Dependabot propose dependency updates.

**Architecture:** One in-memory limiter (`core.Attempts`, keyed sliding windows on the site's `Clock`) and the visitor's address (`core.ClientAddress`, IPv6 grouped by /64) serve three users: login (a filter in front of Spring Security's login plus counting in the login handlers), register (honeypot and per-IP limit in `AuthController`) and the sync API's Connect trade-in. The `PasswordEncoder` bean becomes a `DelegatingPasswordEncoder` (Argon2id for new hashes, the existing Werkzeug scrypt checker for old ones), and the login provider re-hashes old hashes through `Accounts.rehash`. One static method in `SecurityConfig` adds the three headers to both filter chains.

**Tech Stack:** Java 17, Spring Boot 4.1.1 (Spring MVC, Thymeleaf 3.1, Spring Security 7.1.1, Spring Data JPA, Flyway), MySQL 8 (H2 2.4 in MySQL mode for tests), JUnit 5 + MockMvc, BouncyCastle 1.86 (already a dependency; Argon2 uses it). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-07-security-hardening-design.md` (all of it). It builds on `docs/superpowers/specs/2026-10-06-site-roles-design.md`, whose stage 1 this branch starts from.

## Global Constraints

- No new dependencies. No database migration.
- **Limits** (§3), keys `login-pair:<email>|<ip>`, `login-ip:<ip>`, `register-ip:<ip>`, `connect-ip:<ip>`:
  - 5 wrong passwords per email + IP in 15 minutes
  - 100 wrong passwords per IP in 15 minutes
  - 30 new accounts per IP per hour
  - 20 failed Connect trade-ins (`invalid_code`) per IP in 15 minutes
  - a key keeps events younger than 1 hour; above 10,000 keys, an add first drops every key whose newest event is older than 1 hour
- **IPv6** addresses are grouped by their first 64 bits (`2001:db8:1:2::/64`); an IPv4-mapped address counts as the IPv4 address.
- **Messages, exactly:**
  - "Too many wrong passwords. Try again in N minutes." ("1 minute" for 1)
  - "Please try again."
  - "Too many new accounts from this network. Try again in N minutes."
  - 429 `{"error": "too_many_attempts"}`
  - the log line "Login limit reached for <ip> (one email from one IP)" / "(one IP, any emails)", never with the email
- **Argon2id:** `new Argon2PasswordEncoder(16, 32, 1, 19456, 2)` under the id `argon2` (`{argon2}$argon2id$v=19$m=19456,t=2,p=1$…`). Hashes without a `{…}` prefix are checked by `WerkzeugPasswordEncoder`. Re-hashing at login never changes `updated_at` or `updated_by`.
- **Headers, exactly:**
  - `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*`
  - `Referrer-Policy: same-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()`
  - both filter chains (pages and `/api/school/sync/**`)
- **No inline JavaScript or `style=` in templates.** Scripts are files in `static/js/`.
- Times come from the site's `Clock` (`TestClock` in tests); stored times are UTC.
- All user text with `th:text` or Thymeleaf-escaped attributes, never `th:utext`.
- Commits: `type(scope): message`, as the repository does, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- **Two tries at the same moment push a count past its limit:** the wait lasts until enough old tries have left the window, never zero or negative. → Task 1, `pastTheLimitTheWaitLastsUntilEnoughHaveLeft`.
- **An IPv4 visitor reported as an IPv4-mapped IPv6 address** (`::ffff:203.0.113.7`, as some proxies write it): counted as the same IPv4 address, not as a separate visitor. → Task 1, `anIpv4AddressWrittenAsIpv6CountsAsTheIpv4Address`.
- **The same email typed in capitals or with spaces** after 5 wrong tries in lower case: still the same email + IP pair, still blocked. → Task 2, `theBlockIgnoresCapitalsAndSpacesInTheEmail`.
- **A `?wait=` value typed into the address** (`abc`, `<b>x</b>`, `999`, `0`): no message, never markup. → Task 2, `aWaitInTheAddressIsOnlyShownWhenItIsAFewDigits`.
- **A keyboard or screen-reader user on register:** never lands in the hidden field (`tabindex="-1"`, `aria-hidden`, `autocomplete="off"`). → Task 3, `theHoneypotIsHiddenFromKeyboardAndScreenReaders`.

---

## Before you start

- Work in the worktree `C:/IU_SCHOOL/IU project/School-Life-Assistant/security-hardening`, branch `security-hardening`, made from `site-roles` (a7a0b66). It holds the spec and this plan. Other sessions use the main project folder and the `site-roles` worktree; don't switch branches there.
- Run commands from `web/` in Git Bash (`./mvnw …`; in PowerShell use `.\mvnw.cmd …` and quote `-D` options).
- Baseline (site-roles a7a0b66; the spec commit adds no code): `./mvnw -B test` → 843 tests, 0 failures, 1 skipped (`accentsAreIgnoredOnMySql`, MySQL only). Check it before Task 1.
- One test class: `./mvnw -q test -Dtest=AttemptsTest`. After renaming or deleting a class, `./mvnw clean` first.
- **Limits are shared within a test context.** `Attempts` is one bean, and test classes with the same configuration share it. Every limit test therefore sends from an IP of its own (`request.setRemoteAddr(...)`, the helper `from(ip)` below), so tests never add to each other's counts.

## File map

| File | Responsibility |
|---|---|
| `web/src/main/java/vn/edu/hcmiu/sla/core/Attempts.java` | the in-memory limiter |
| `web/src/main/java/vn/edu/hcmiu/sla/core/ClientAddress.java` | the visitor's address; IPv6 grouped by /64 |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimits.java` | the two login rules |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimitFilter.java` | refuses a login before the password check while a rule says wait |
| `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java` (modify) | the filter, counting on failure, Argon2id encoder, re-hashing, headers on the pages chain |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java` (modify) | clears the pair; puts the account as saved into the session |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java`, `RegisterForm.java` (modify) | the login wait message; the register honeypot and limit |
| `web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java`, `Sessions.java`, `User.java` (modify) | `rehash`, `loggedIn` returning the account, `refresh` |
| `web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncApiController.java`, `SyncApiConfig.java` (modify) | the Connect trade-in limit; headers on the sync chain |
| `web/src/main/resources/templates/auth/login.html`, `auth/register.html`, `school/devices.html` (modify) | messages, honeypot, scripts as files |
| `web/src/main/resources/static/js/devices.js` (new), `static/css/style.css` (modify) | Copy key; the `.trap` class |
| `.github/dependabot.yml` (new) | weekly update pull requests |
| `README.md` (modify) | the Security section, rule 6, the default-branch note |
| tests: `core/AttemptsTest`, `core/ClientAddressTest`, `auth/LoginLimitsTest`, `auth/LoginLimitPageTest`, `auth/RegisterLimitTest`, `auth/PasswordHashTest`, `auth/RegisterTest`, `auth/AccountPageTest`, `school/sync/ConnectApiTest`, `core/SecurityHeadersTest`, `core/TemplatesFollowTheCspTest`, `school/pages/DevicesPageTest` | |

---

### Task 1: The limiter and the visitor's address

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/core/Attempts.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/core/ClientAddress.java`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/core/AttemptsTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/core/ClientAddressTest.java`

**Interfaces:**
- Produces: `@Component Attempts(Clock clock)` with `void add(String key)`, `int count(String key, Duration window)`, `Duration waitFor(String key, int limit, Duration window)` (zero when under the limit), `void clear(String key)`, package-private `int size()`, `static long minutes(Duration wait)` (rounded up, at least 1) and `static String inMinutes(Duration wait)` ("1 minute", "12 minutes").
- Produces: `final class ClientAddress` with `static String of(HttpServletRequest request)` and package-private `static String of(String address)`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/core/AttemptsTest.java`:

```java
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
```

Create `web/src/test/java/vn/edu/hcmiu/sla/core/ClientAddressTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

/** The visitor's address for limits (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.2). */
class ClientAddressTest {

    @Test
    void anIpv4AddressIsKeptAsItIs() {
        assertThat(ClientAddress.of("203.0.113.7")).isEqualTo("203.0.113.7");
    }

    @Test
    void ipv6IsGroupedByItsFirst64Bits() {
        assertThat(ClientAddress.of("2001:db8:1:2:aaaa:bbbb:cccc:dddd")).isEqualTo("2001:db8:1:2::/64");
        assertThat(ClientAddress.of("2001:0db8:0001:0002::1")).isEqualTo("2001:db8:1:2::/64");
        assertThat(ClientAddress.of("2001:db8:1:3::1")).isEqualTo("2001:db8:1:3::/64");
        assertThat(ClientAddress.of("::1")).isEqualTo("0:0:0:0::/64");
    }

    @Test
    void anIpv4AddressWrittenAsIpv6CountsAsTheIpv4Address() { // Review Focus
        assertThat(ClientAddress.of("::ffff:203.0.113.7")).isEqualTo("203.0.113.7");
    }

    @Test
    void theRequestsRemoteAddressIsUsed() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("2001:db8:1:2::5");

        assertThat(ClientAddress.of(request)).isEqualTo("2001:db8:1:2::/64");
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='AttemptsTest,ClientAddressTest'`
Expected: FAIL: compilation errors (`Attempts` and `ClientAddress` don't exist).

- [ ] **Step 3: Write `Attempts`**

Create `web/src/main/java/vn/edu/hcmiu/sla/core/Attempts.java`:

```java
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
```

- [ ] **Step 4: Write `ClientAddress`**

Create `web/src/main/java/vn/edu/hcmiu/sla/core/ClientAddress.java`:

```java
package vn.edu.hcmiu.sla.core;

import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.UnknownHostException;

import jakarta.servlet.http.HttpServletRequest;

/**
 * The visitor's address for limits (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.2). On the server,
 * request.getRemoteAddr() is the visitor's: Caddy sets X-Forwarded-For, the site reads it
 * (SERVER_FORWARD_HEADERS_STRATEGY=framework), and only Caddy can reach the site. IPv4 is kept as it is; IPv6 is
 * grouped by its first 64 bits, so one device can't get round a limit by changing its IPv6 address.
 */
public final class ClientAddress {

    private ClientAddress() {
    }

    public static String of(HttpServletRequest request) {
        return of(request.getRemoteAddr());
    }

    static String of(String address) {
        if (address == null || !address.contains(":")) {
            return String.valueOf(address);
        }
        try {
            InetAddress parsed = InetAddress.getByName(address); // an IPv6 literal: parsed, never looked up
            if (!(parsed instanceof Inet6Address)) {
                return parsed.getHostAddress(); // ::ffff:203.0.113.7 is an IPv4 address
            }
            byte[] bytes = parsed.getAddress();
            return String.format("%x:%x:%x:%x::/64", word(bytes, 0), word(bytes, 2), word(bytes, 4), word(bytes, 6));
        } catch (UnknownHostException notAnAddress) {
            return address;
        }
    }

    private static int word(byte[] bytes, int at) {
        return ((bytes[at] & 0xff) << 8) | (bytes[at + 1] & 0xff);
    }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='AttemptsTest,ClientAddressTest'`
Expected: PASS (10 tests).

Then `./mvnw -B test`. Expected: 853 tests, 0 failures, 1 skipped.

- [ ] **Step 6: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/core/Attempts.java web/src/main/java/vn/edu/hcmiu/sla/core/ClientAddress.java web/src/test/java/vn/edu/hcmiu/sla/core/AttemptsTest.java web/src/test/java/vn/edu/hcmiu/sla/core/ClientAddressTest.java
git commit -F - <<'EOF'
feat(web): an in-memory limiter that counts tries per key and visitor, with IPv6 grouped by its /64

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Login limits

**Files:**
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimits.java`
- Create: `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimitFilter.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java` (the `login` GET)
- Modify: `web/src/main/resources/templates/auth/login.html`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitsTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitPageTest.java`

**Interfaces:**
- Consumes: `Attempts`, `ClientAddress` (Task 1); `AppUserDetailsService.normalizeEmail` (exists).
- Produces: `@Component LoginLimits(Attempts attempts)` with `Duration waitFor(String email, String ip)`, `void failed(String email, String ip)`, `void succeeded(String email, String ip)`; constants `PER_PAIR = 5`, `PER_IP = 100`, `WINDOW = 15 minutes`.
- Produces: `class LoginLimitFilter extends OncePerRequestFilter`, `new LoginLimitFilter(LoginLimits limits)`, placed before `UsernamePasswordAuthenticationFilter`; a blocked login goes to `/auth/login?wait=<minutes>`.
- Produces: `SecurityConfig.loginFailed(LoginLimits limits)`; `LoggedIn(Accounts accounts, LoginLimits limits, Clock clock)`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitsTest.java`:

```java
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
```

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitPageTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;

import java.time.LocalDateTime;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.TestClock;

/**
 * Login limits on the real login form (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.3). Each test
 * sends from an IP of its own, so tests never add to each other's counts.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class LoginLimitPageTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);
    static final String RIGHT = "correct-horse-8";
    static final String WRONG = "wrong-password";

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    TestClock clock;

    User an;

    @BeforeEach
    void anAccount() {
        clock.set(NOW);
        an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT,
                LocalDateTime.of(2026, 9, 1, 0, 0)));
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    static RequestPostProcessor from(String ip) {
        return request -> {
            request.setRemoteAddr(ip);
            return request;
        };
    }

    ResultActions logIn(String email, String password, String ip) throws Exception {
        return mvc.perform(post("/auth/login").with(csrf()).with(from(ip))
                .param("email", email).param("password", password));
    }

    void wrong(int times, String ip) throws Exception {
        for (int i = 0; i < times; i++) {
            logIn("an@example.com", WRONG, ip).andExpect(redirectedUrl("/auth/login?error"));
        }
    }

    @Test
    void fiveWrongPasswordsMakeEvenTheRightOneWait() throws Exception {
        wrong(5, "198.51.100.11");

        logIn("an@example.com", RIGHT, "198.51.100.11").andExpect(redirectedUrl("/auth/login?wait=15"));
        assertThat(an.getLastLoginAt()).isNull(); // the password wasn't even checked
        mvc.perform(get("/auth/login").param("wait", "15"))
                .andExpect(content().string(containsString("Too many wrong passwords. Try again in 15 minutes.")));

        clock.set(NOW.plusMinutes(15));
        logIn("an@example.com", RIGHT, "198.51.100.11").andExpect(redirectedUrl("/"));
    }

    @Test
    void theOwnerOnAnotherNetworkStillLogsIn() throws Exception {
        wrong(5, "198.51.100.12");

        logIn("an@example.com", RIGHT, "198.51.100.13").andExpect(redirectedUrl("/"));
    }

    @Test
    void anUnknownEmailIsCountedTheSameWay() throws Exception {
        for (int i = 0; i < 5; i++) {
            logIn("nobody@example.com", WRONG, "198.51.100.14").andExpect(redirectedUrl("/auth/login?error"));
        }

        logIn("nobody@example.com", WRONG, "198.51.100.14").andExpect(redirectedUrl("/auth/login?wait=15"));
    }

    @Test
    void triesWhileBlockedDontMakeTheWaitLonger() throws Exception {
        wrong(5, "198.51.100.15");

        clock.set(NOW.plusMinutes(10));
        for (int i = 0; i < 5; i++) {
            logIn("an@example.com", WRONG, "198.51.100.15").andExpect(redirectedUrl("/auth/login?wait=5"));
        }

        clock.set(NOW.plusMinutes(15));
        logIn("an@example.com", RIGHT, "198.51.100.15").andExpect(redirectedUrl("/"));
    }

    @Test
    void theDeactivatedAnswerIsNotCounted() throws Exception {
        an.deactivate(null, NOW);

        for (int i = 0; i < 6; i++) {
            logIn("an@example.com", RIGHT, "198.51.100.16").andExpect(redirectedUrl("/auth/login?deactivated"));
        }
    }

    @Test
    void aRightPasswordStartsThePairAgain() throws Exception {
        wrong(4, "198.51.100.17");
        logIn("an@example.com", RIGHT, "198.51.100.17").andExpect(redirectedUrl("/"));

        wrong(4, "198.51.100.17");
        logIn("an@example.com", RIGHT, "198.51.100.17").andExpect(redirectedUrl("/"));
    }

    @Test
    void visitorsInOneIpv6NetworkShareTheirLimit() throws Exception {
        for (int i = 1; i <= 5; i++) {
            logIn("an@example.com", WRONG, "2001:db8:1:2::" + i).andExpect(redirectedUrl("/auth/login?error"));
        }

        logIn("an@example.com", RIGHT, "2001:db8:1:2::99").andExpect(redirectedUrl("/auth/login?wait=15"));
    }

    @Test
    void aWaitInTheAddressIsOnlyShownWhenItIsAFewDigits() throws Exception { // Review Focus
        mvc.perform(get("/auth/login").param("wait", "1"))
                .andExpect(content().string(containsString("Too many wrong passwords. Try again in 1 minute.")));
        for (String typed : new String[] {"abc", "<b>x</b>", "999", "0"}) {
            mvc.perform(get("/auth/login").param("wait", typed))
                    .andExpect(content().string(not(containsString("Too many wrong passwords"))))
                    .andExpect(content().string(not(containsString("<b>x</b>"))));
        }
    }
}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='LoginLimitsTest,LoginLimitPageTest'`
Expected: FAIL: compilation error (`LoginLimits` doesn't exist).

- [ ] **Step 3: Write `LoginLimits` and `LoginLimitFilter`**

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimits.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.time.Duration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import vn.edu.hcmiu.sla.core.Attempts;

/**
 * The two login rules (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.3): 5 wrong passwords for one
 * email from one IP, or 100 from one IP for any emails, within 15 minutes, and the password isn't checked until the
 * count drops. An unknown email counts like a wrong password, so the limits never show which emails have accounts.
 */
@Component
public class LoginLimits {

    static final int PER_PAIR = 5;
    static final int PER_IP = 100;
    static final Duration WINDOW = Duration.ofMinutes(15);

    private static final Logger LOG = LoggerFactory.getLogger(LoginLimits.class);

    private final Attempts attempts;

    public LoginLimits(Attempts attempts) {
        this.attempts = attempts;
    }

    /** How long this email from this IP must wait before its password is checked; zero: check it now. */
    public Duration waitFor(String email, String ip) {
        Duration pair = attempts.waitFor(pairKey(email, ip), PER_PAIR, WINDOW);
        Duration all = attempts.waitFor(ipKey(ip), PER_IP, WINDOW);
        return pair.compareTo(all) >= 0 ? pair : all;
    }

    /** A wrong password or an unknown email. */
    public void failed(String email, String ip) {
        attempts.add(pairKey(email, ip));
        attempts.add(ipKey(ip));
        if (attempts.count(pairKey(email, ip), WINDOW) == PER_PAIR) {
            LOG.warn("Login limit reached for {} (one email from one IP)", ip);
        }
        if (attempts.count(ipKey(ip), WINDOW) == PER_IP) {
            LOG.warn("Login limit reached for {} (one IP, any emails)", ip);
        }
    }

    /** The right password: this email from this IP starts again. */
    public void succeeded(String email, String ip) {
        attempts.clear(pairKey(email, ip));
    }

    private static String pairKey(String email, String ip) {
        return "login-pair:" + AppUserDetailsService.normalizeEmail(email) + "|" + ip;
    }

    private static String ipKey(String ip) {
        return "login-ip:" + ip;
    }
}
```

Create `web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimitFilter.java`:

```java
package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.time.Duration;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.filter.OncePerRequestFilter;

import vn.edu.hcmiu.sla.core.Attempts;
import vn.edu.hcmiu.sla.core.ClientAddress;

/**
 * Runs in front of Spring Security's login (POST /auth/login): while LoginLimits says to wait, the password isn't
 * checked and the browser goes back to the login page with the minutes to wait. Not a bean, so it runs only in the
 * pages' filter chain (SecurityConfig).
 */
public class LoginLimitFilter extends OncePerRequestFilter {

    private final LoginLimits limits;

    public LoginLimitFilter(LoginLimits limits) {
        this.limits = limits;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return !("POST".equals(request.getMethod()) && path.equals("/auth/login"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Duration wait = limits.waitFor(request.getParameter("email"), ClientAddress.of(request));
        if (wait.isZero()) {
            chain.doFilter(request, response);
            return;
        }
        response.sendRedirect(request.getContextPath() + "/auth/login?wait=" + Attempts.minutes(wait));
    }
}
```

- [ ] **Step 4: Count in the login handlers, add the filter**

In `SecurityConfig.java`:
- add imports `org.springframework.security.authentication.BadCredentialsException`, `org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter`, `vn.edu.hcmiu.sla.auth.LoginLimitFilter` and `vn.edu.hcmiu.sla.auth.LoginLimits`;
- change `pages(…)`'s signature to `SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn, Refusals refusals, UserRepository users, SecurityContextRepository logins, LoginLimits limits) throws Exception`;
- after the `.addFilterBefore(new AccountCheck(users, logins), AuthorizationFilter.class)` line, add:
  ```java
                .addFilterBefore(new LoginLimitFilter(limits), UsernamePasswordAuthenticationFilter.class)
  ```
- in `formLogin`, replace `.failureHandler(loginFailed())` with `.failureHandler(loginFailed(limits))`;
- replace the `loginFailed()` method (and its comment) with:
  ```java
      /**
       * A wrong password or an unknown email: counted (LoginLimits), then ?error. The right password for a deactivated
       * account: ?deactivated, not counted (it isn't a guess).
       */
      static AuthenticationFailureHandler loginFailed(LoginLimits limits) {
          ExceptionMappingAuthenticationFailureHandler pages = new ExceptionMappingAuthenticationFailureHandler();
          pages.setDefaultFailureUrl("/auth/login?error");
          pages.setExceptionMappings(Map.of(DisabledException.class.getName(), "/auth/login?deactivated"));
          return (request, response, failure) -> {
              if (failure instanceof BadCredentialsException) {
                  limits.failed(request.getParameter("email"), ClientAddress.of(request));
              }
              pages.onAuthenticationFailure(request, response, failure);
          };
      }
  ```

`ClientAddress` is in `core`, the same package as `SecurityConfig`: no import needed.

In `LoggedIn.java`:
- add import `vn.edu.hcmiu.sla.core.ClientAddress`;
- add the field `private final LoginLimits limits;` and make the constructor:
  ```java
      public LoggedIn(Accounts accounts, LoginLimits limits, Clock clock) {
          this.accounts = accounts;
          this.limits = limits;
          this.clock = clock;
          setDefaultTargetUrl("/");
      }
  ```
- in `onAuthenticationSuccess`, inside the `if`, before `accounts.loggedIn(…)`, add:
  ```java
              limits.succeeded(user.email(), ClientAddress.of(request));
  ```
- change the class comment's first sentence to "After a login: this email from this IP starts its count again (LoginLimits), the login's time is noted, then the browser goes back to the page that asked for login, else home, as Spring Security's own handler does."

- [ ] **Step 5: The wait message**

In `AuthController.java`, add imports `java.time.Duration`, `org.springframework.web.bind.annotation.RequestParam` and `vn.edu.hcmiu.sla.core.Attempts`, and replace the `login()` method with:

```java
    /** ?wait=N comes from LoginLimitFilter; anything but 1 or 2 digits from 1 up shows no message. */
    @GetMapping("/login")
    String login(@RequestParam(required = false) String wait, Model model) {
        if (wait != null && wait.matches("[0-9]{1,2}") && Integer.parseInt(wait) > 0) {
            model.addAttribute("tooMany", "Too many wrong passwords. Try again in "
                    + Attempts.inMinutes(Duration.ofMinutes(Integer.parseInt(wait))) + ".");
        }
        return "auth/login";
    }
```

In `templates/auth/login.html`, after the `param.changed` line add:

```html
    <p th:if="${tooMany}" class="flash flash-error" th:text="${tooMany}">Too many wrong passwords. Try again in 15 minutes.</p>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='LoginLimitsTest,LoginLimitPageTest,LoginTest,RegisterTest,AccountCheckTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 866 tests, 0 failures, 1 skipped.

- [ ] **Step 7: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimits.java web/src/main/java/vn/edu/hcmiu/sla/auth/LoginLimitFilter.java web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java web/src/main/resources/templates/auth/login.html web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitsTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/LoginLimitPageTest.java
git commit -F - <<'EOF'
feat(web): 5 wrong passwords for one email from one network, or 100 from one network, mean a wait before the next try

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 3: The register honeypot and limit, and the Connect trade-in limit

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/RegisterForm.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java` (register)
- Modify: `web/src/main/resources/templates/auth/register.html`
- Modify: `web/src/main/resources/static/css/style.css`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncApiController.java`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterLimitTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/school/sync/ConnectApiTest.java`

**Interfaces:**
- Consumes: `Attempts`, `ClientAddress` (Task 1).
- Produces: `RegisterForm.getWebsite()` / `setWebsite(String)`; `AuthController.NEW_ACCOUNTS_PER_IP = 30`, `NEW_ACCOUNTS_WINDOW = 1 hour`; `SyncApiController.FAILED_TRADE_INS_PER_IP = 20`, `TRADE_IN_WINDOW = 15 minutes`. Both controllers take an `Attempts` in their constructors.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterLimitTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.TestClock;

/** The register honeypot and per-IP limit (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.4). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class RegisterLimitTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 7, 1, 0);

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    TestClock clock;

    @BeforeEach
    void now() {
        clock.set(NOW);
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    ResultActions register(String email, String ip, String website) throws Exception {
        return mvc.perform(post("/auth/register").with(csrf()).with(LoginLimitPageTest.from(ip))
                .param("email", email).param("displayName", "An")
                .param("password", "correct-horse-8").param("confirm", "correct-horse-8")
                .param("website", website));
    }

    @Test
    void aFilledHoneypotMakesNoAccount() throws Exception {
        register("an@example.com", "198.51.100.30", "https://spam.example")
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Please try again.")))
                .andExpect(content().string(containsString("value=\"an@example.com\"")));

        assertThat(users.findByEmail("an@example.com")).isEmpty();
    }

    @Test
    void theHoneypotIsHiddenFromKeyboardAndScreenReaders() throws Exception { // Review Focus
        String page = mvc.perform(get("/auth/register")).andReturn().getResponse().getContentAsString();

        assertThat(page).contains("<div class=\"trap\" aria-hidden=\"true\">")
                .containsPattern("<input id=\"website\"[^>]*tabindex=\"-1\"")
                .containsPattern("<input id=\"website\"[^>]*autocomplete=\"off\"");
    }

    @Test
    void thirtyNewAccountsFromOneNetworkInAnHourThenAWait() throws Exception {
        for (int i = 1; i <= 30; i++) {
            register("person" + i + "@example.com", "198.51.100.31", "").andExpect(redirectedUrl("/"));
        }

        register("person31@example.com", "198.51.100.31", "")
                .andExpect(status().isOk())
                .andExpect(content().string(containsString(
                        "Too many new accounts from this network. Try again in 60 minutes.")));
        assertThat(users.findByEmail("person31@example.com")).isEmpty();
        register("person31@example.com", "198.51.100.32", "").andExpect(redirectedUrl("/"));

        clock.set(NOW.plusHours(1));
        register("person32@example.com", "198.51.100.31", "").andExpect(redirectedUrl("/"));
    }

    @Test
    void refusedSignUpsDontCount() throws Exception {
        for (int i = 1; i <= 35; i++) {
            register("bot" + i + "@example.com", "198.51.100.33", "https://spam.example");
        }

        register("an@example.com", "198.51.100.33", "").andExpect(redirectedUrl("/"));
    }
}
```

In `ConnectApiTest.java`, add the import `org.springframework.test.web.servlet.request.RequestPostProcessor` and, after the `trade` helper:

```java
    ResultActions tradeFrom(String ip, String code, String verifier) throws Exception {
        RequestPostProcessor from = request -> {
            request.setRemoteAddr(ip);
            return request;
        };
        return mvc.perform(post("/api/school/sync/connect").with(from).contentType(MediaType.APPLICATION_JSON)
                .content(bytes(Map.of("code", code, "verifier", verifier))));
    }

    // ---- Limits (security hardening spec, 3.5) --------------------------------

    @Test
    void twentyFailedTradeInsFromOneNetworkThenEvenAGoodCodeWaits() throws Exception {
        for (int i = 0; i < 20; i++) {
            tradeFrom("203.0.113.9", "A".repeat(43), VERIFIER).andExpect(status().isBadRequest());
        }

        tradeFrom("203.0.113.9", code(), VERIFIER)
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.error").value("too_many_attempts"));
        assertThat(devices.count()).isZero();
        tradeFrom("203.0.113.10", code(), VERIFIER).andExpect(status().isOk());
    }

    @Test
    void aMalformedBodyIsNotCounted() throws Exception {
        for (int i = 0; i < 25; i++) {
            tradeFrom("203.0.113.11", "short", VERIFIER).andExpect(status().is(422));
        }

        tradeFrom("203.0.113.11", code(), VERIFIER).andExpect(status().isOk());
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='RegisterLimitTest,ConnectApiTest'`
Expected: FAIL in `aFilledHoneypotMakesNoAccount` (the account is made), `theHoneypotIsHiddenFromKeyboardAndScreenReaders` (no such field), `thirtyNewAccountsFromOneNetworkInAnHourThenAWait` (the 31st is made) and `twentyFailedTradeInsFromOneNetworkThenEvenAGoodCodeWaits` (200, not 429). `refusedSignUpsDontCount` and `aMalformedBodyIsNotCounted` may already pass.

- [ ] **Step 3: The honeypot field and the register checks**

In `RegisterForm.java`, add after the `confirm` field and its accessors:

```java
    /** The honeypot (spec 3.4 of security hardening): hidden from people, so only a bot fills it in. */
    private String website = "";

    public String getWebsite() {
        return website;
    }

    public void setWebsite(String website) {
        this.website = website == null ? "" : website;
    }
```

In `AuthController.java`:
- add imports `vn.edu.hcmiu.sla.core.ClientAddress` (`Attempts` and `Duration` came in Task 2);
- add the constants and field, and take `Attempts` in the constructor:
  ```java
      static final int NEW_ACCOUNTS_PER_IP = 30;
      static final Duration NEW_ACCOUNTS_WINDOW = Duration.ofHours(1);

      private final Attempts attempts;
  ```
  with `this.attempts = attempts;` in the constructor, which becomes `public AuthController(UserRepository users, PasswordEncoder passwords, Sessions sessions, Attempts attempts)`;
- at the start of `register(…)`'s body, add:
  ```java
          String network = "register-ip:" + ClientAddress.of(request);
          if (!form.getWebsite().isEmpty()) { // the honeypot: people never see it
              errors.reject("trap", "Please try again.");
              return "auth/register";
          }
          Duration wait = attempts.waitFor(network, NEW_ACCOUNTS_PER_IP, NEW_ACCOUNTS_WINDOW);
          if (!wait.isZero()) {
              errors.reject("tooMany",
                      "Too many new accounts from this network. Try again in " + Attempts.inMinutes(wait) + ".");
              return "auth/register";
          }
  ```
- right after `User user = users.save(account);`, add `attempts.add(network); // only accounts actually made count`.

In `templates/auth/register.html`:
- right after the `<form …>` line, add:
  ```html
      <p class="flash flash-error" th:each="error : ${#fields.globalErrors()}" th:text="${error}">Please try again.</p>
  ```
- right before the `<button type="submit" class="button">Create account</button>` line, add:
  ```html
      <div class="trap" aria-hidden="true">
        <label for="website">Leave this empty</label>
        <input id="website" type="text" th:field="*{website}" tabindex="-1" autocomplete="off">
      </div>
  ```

At the end of `static/css/style.css`, add:

```css
/* The register page's honeypot (security hardening spec, 3.4): off-screen, so only a bot fills it in. */
.trap { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
```

- [ ] **Step 4: The Connect trade-in limit**

In `SyncApiController.java`:
- add imports `java.time.Duration`, `vn.edu.hcmiu.sla.core.Attempts` and `vn.edu.hcmiu.sla.core.ClientAddress`;
- add the constants and field, and take `Attempts` in the constructor (add the parameter at the end and assign it):
  ```java
      static final int FAILED_TRADE_INS_PER_IP = 20;
      static final Duration TRADE_IN_WINDOW = Duration.ofMinutes(15);

      private final Attempts attempts;
  ```
- replace the `connect` method with:
  ```java
      /**
       * Connect's trade-in: the one-time code from the Connect page and the app's verifier, for a new device key and the
       * account's email. No device key is needed here (SyncApiConfig); anything wrong with the code is 400 invalid_code.
       * After 20 of those from one network within 15 minutes, 429 too_many_attempts without looking at the code
       * (security hardening spec, 3.5). A malformed body (422) isn't counted: it can't be a guess.
       */
      @PostMapping("/connect")
      ResponseEntity<Map<String, Object>> connect(HttpServletRequest request) throws IOException {
          String network = "connect-ip:" + ClientAddress.of(request);
          if (attempts.count(network, TRADE_IN_WINDOW) >= FAILED_TRADE_INS_PER_IP) {
              return error(HttpStatus.TOO_MANY_REQUESTS, "too_many_attempts");
          }
          ConnectRequest body = json.read(json.body(request), ConnectRequest.class);
          Optional<ConnectCodes.Pending> pending = connectCodes.redeem(body.code(), body.verifier());
          if (pending.isEmpty()) {
              attempts.add(network);
              return error(HttpStatus.BAD_REQUEST, "invalid_code");
          }
          String key = deviceKeys.create(pending.get().userId(), pending.get().name(), now()).rawKey();
          return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                  .body(Map.of("key", key, "email", pending.get().email()));
      }
  ```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='RegisterLimitTest,RegisterTest,ConnectApiTest,SyncApiTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 872 tests, 0 failures, 1 skipped.

- [ ] **Step 6: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/auth/RegisterForm.java web/src/main/java/vn/edu/hcmiu/sla/auth/AuthController.java web/src/main/resources/templates/auth/register.html web/src/main/resources/static/css/style.css web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncApiController.java web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterLimitTest.java web/src/test/java/vn/edu/hcmiu/sla/school/sync/ConnectApiTest.java
git commit -F - <<'EOF'
feat(web): register refuses bots with a hidden field and allows 30 new accounts per network per hour; Connect trade-ins are limited too

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Argon2id passwords, upgraded at login

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java` (`passwordEncoder`, `passwordLogin`)
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/auth/User.java`, `Accounts.java`, `Sessions.java`, `LoggedIn.java`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/auth/PasswordHashTest.java`; `RegisterTest.java` (one assertion); `AccountPageTest.java` (one assertion)

**Interfaces:**
- Consumes: `LoggedIn(Accounts, LoginLimits, Clock)` (Task 2).
- Produces: the `PasswordEncoder` bean is a `DelegatingPasswordEncoder`; `User.rehash(String newPasswordHash)`; `UserDetails Accounts.rehash(UserDetails account, String newHash)`; `Optional<User> Accounts.loggedIn(Integer userId, LocalDateTime now)` (was `void`); `Sessions.refresh(AppUser user, HttpServletRequest request, HttpServletResponse response)`; `LoggedIn(Accounts accounts, LoginLimits limits, Sessions sessions, Clock clock)`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/auth/PasswordHashTest.java`:

```java
package vn.edu.hcmiu.sla.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDateTime;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.annotation.Transactional;

/** Argon2id passwords, old scrypt ones upgraded at login (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 4). */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class PasswordHashTest {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);
    static final String ARGON2ID = "{argon2}$argon2id$v=19$m=19456,t=2,p=1$";

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    PasswordEncoder passwords;

    ResultActions logIn(MockHttpSession session, String email, String password) throws Exception {
        return mvc.perform(post("/auth/login").session(session).with(csrf())
                .with(LoginLimitPageTest.from("192.0.2.40")).param("email", email).param("password", password));
    }

    @Test
    void newPasswordsAreArgon2id() {
        String hash = passwords.encode("correct-horse-8");

        assertThat(hash).startsWith(ARGON2ID).hasSizeLessThan(255);
        assertThat(passwords.matches("correct-horse-8", hash)).isTrue();
        assertThat(passwords.matches("correct-horse-9", hash)).isFalse();
    }

    @Test
    void oldScryptHashesStillMatch() {
        assertThat(passwords.matches("correct-horse-8", WerkzeugPasswordEncoderTest.SCRYPT)).isTrue();
        assertThat(passwords.matches("mật khẩu 123", WerkzeugPasswordEncoderTest.SCRYPT_VIETNAMESE)).isTrue();
        assertThat(passwords.matches("wrong-password", WerkzeugPasswordEncoderTest.SCRYPT)).isFalse();
    }

    @Test
    void aPlaceholderHashFailsWithoutAnError() throws Exception {
        assertThat(passwords.matches("x", "x")).isFalse();
        users.save(new User("an@example.com", "An", "x", SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "x").andExpect(redirectedUrl("/auth/login?error"));
    }

    @Test
    void anOldAccountIsUpgradedAtLoginAndStaysLoggedIn() throws Exception {
        User an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));
        MockHttpSession session = new MockHttpSession();

        logIn(session, "an@example.com", "correct-horse-8").andExpect(redirectedUrl("/"));

        assertThat(an.getPasswordHash()).startsWith(ARGON2ID);
        assertThat(passwords.matches("correct-horse-8", an.getPasswordHash())).isTrue();
        assertThat(an.getUpdatedAt()).isEqualTo(SEPT_1); // nobody changed anything
        assertThat(an.getUpdatedBy()).isNull();
        mvc.perform(get("/").session(session)).andExpect(status().isOk()); // not logged out as "password changed"
    }

    @Test
    void aWrongPasswordLeavesAnOldHashAlone() throws Exception {
        User an = users.save(new User("an@example.com", "An", WerkzeugPasswordEncoderTest.SCRYPT, SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "wrong-password").andExpect(redirectedUrl("/auth/login?error"));

        assertThat(an.getPasswordHash()).isEqualTo(WerkzeugPasswordEncoderTest.SCRYPT);
    }

    @Test
    void anArgon2idAccountIsNotHashedAgain() throws Exception {
        String hash = passwords.encode("correct-horse-8");
        User an = users.save(new User("an@example.com", "An", hash, SEPT_1));

        logIn(new MockHttpSession(), "an@example.com", "correct-horse-8").andExpect(redirectedUrl("/"));

        assertThat(an.getPasswordHash()).isEqualTo(hash);
    }
}
```

In `RegisterTest.java`, in `registeringLogsYouInAndSavesAWerkzeugStylePassword`, rename the test to `registeringLogsYouInAndSavesAnArgon2idPassword` and replace `assertThat(user.getPasswordHash()).startsWith("scrypt:32768:8:1$");` with:

```java
        assertThat(user.getPasswordHash()).startsWith("{argon2}$argon2id$v=19$m=19456,t=2,p=1$");
```

In `AccountPageTest.java`, in `aNewPasswordIsSavedAndThisSessionStaysLoggedIn`, after the `passwords.matches("new horse 123 ", …)` line add:

```java
        assertThat(an.getPasswordHash()).startsWith("{argon2}$argon2id$");
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='PasswordHashTest,RegisterTest,AccountPageTest'`
Expected: FAIL: `newPasswordsAreArgon2id`, `anOldAccountIsUpgradedAtLoginAndStaysLoggedIn`, `anArgon2idAccountIsNotHashedAgain` (hashes are still scrypt), `registeringLogsYouInAndSavesAnArgon2idPassword` and `aNewPasswordIsSavedAndThisSessionStaysLoggedIn`.

- [ ] **Step 3: The encoder and the re-hash hook**

In `SecurityConfig.java`:
- add imports `org.springframework.security.crypto.argon2.Argon2PasswordEncoder`, `org.springframework.security.crypto.password.DelegatingPasswordEncoder` and `vn.edu.hcmiu.sla.auth.Accounts`;
- replace the `passwordEncoder()` method with:
  ```java
      /**
       * New hashes are Argon2id with OWASP's settings (security hardening spec, 4): {argon2}$argon2id$…. A hash with no
       * {id} prefix is the old scrypt (Werkzeug) format, which WerkzeugPasswordEncoder still checks; the login provider
       * re-hashes it at the next login (Accounts.rehash).
       */
      @Bean
      PasswordEncoder passwordEncoder() {
          DelegatingPasswordEncoder passwords = new DelegatingPasswordEncoder("argon2",
                  Map.of("argon2", new Argon2PasswordEncoder(16, 32, 1, 19456, 2)));
          passwords.setDefaultPasswordEncoderForMatches(new WerkzeugPasswordEncoder());
          return passwords;
      }
  ```
- replace the `passwordLogin(…)` method's signature and body with:
  ```java
      @Bean
      DaoAuthenticationProvider passwordLogin(AppUserDetailsService users, PasswordEncoder passwords, Accounts accounts) {
          DaoAuthenticationProvider provider = new DaoAuthenticationProvider(users);
          provider.setPasswordEncoder(passwords);
          provider.setUserDetailsPasswordService(accounts::rehash); // an old hash becomes Argon2id at login
          provider.setPreAuthenticationChecks(account -> {
          });
          provider.setPostAuthenticationChecks(account -> {
              if (!account.isEnabled()) {
                  throw new DisabledException("This account has been deactivated");
              }
          });
          return provider;
      }
  ```
  and add to its comment: "Spring re-hashes an old password at login through Accounts.rehash."

- [ ] **Step 4: Re-hash without a change; keep the session**

In `User.java`, after `changePassword(…)` add:

```java
    /** The same password hashed anew, with a stronger algorithm: not a change by anyone, so updated_at stays. */
    public void rehash(String newPasswordHash) {
        passwordHash = newPasswordHash;
    }
```

In `Accounts.java`:
- add imports `java.util.Optional` and `org.springframework.security.core.userdetails.UserDetails`;
- replace `loggedIn(…)` with:
  ```java
      /** users.last_login_at, for the Users page (stage 2) and Profile; the account as now saved. */
      @Transactional
      public Optional<User> loggedIn(Integer userId, LocalDateTime now) {
          Optional<User> user = users.findById(userId);
          user.ifPresent(account -> account.loggedIn(now));
          return user;
      }
  ```
- add:
  ```java
      /**
       * Spring calls this at login when the stored hash is an older kind than Argon2id (security hardening spec, 4): the
       * same password, hashed anew. Not a change by anyone, so updated_at stays.
       */
      @Transactional
      public UserDetails rehash(UserDetails account, String newHash) {
          User user = users.findById(((AppUser) account).id()).orElseThrow();
          user.rehash(newHash);
          return AppUser.of(user);
      }
  ```

In `Sessions.java`, replace the `logIn` method with these two:

```java
    public void logIn(AppUser user, HttpServletRequest request, HttpServletResponse response) {
        if (request.getSession(false) != null) {
            request.changeSessionId(); // a new session id after login
        }
        refresh(user, request, response);
    }

    /**
     * Puts the account as now saved into this browser's session, keeping its session id: after a login whose password
     * was just re-hashed (security hardening spec, 4), so AccountCheck doesn't take the new hash for a changed password.
     */
    public void refresh(AppUser user, HttpServletRequest request, HttpServletResponse response) {
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(user, null, user.getAuthorities()));
        SecurityContextHolder.setContext(context);
        logins.saveContext(context, request, response);
    }
```

In `LoggedIn.java`:
- add the field `private final Sessions sessions;`; the constructor becomes `public LoggedIn(Accounts accounts, LoginLimits limits, Sessions sessions, Clock clock)` and assigns it;
- replace the line `accounts.loggedIn(user.id(), LocalDateTime.now(clock));` with:
  ```java
              // The account as now saved: Spring may have just re-hashed its password (Accounts.rehash), and the session
              // must hold the new hash, or AccountCheck would log this session out on its next click.
              accounts.loggedIn(user.id(), LocalDateTime.now(clock))
                      .ifPresent(saved -> sessions.refresh(AppUser.of(saved), request, response));
  ```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='PasswordHashTest,RegisterTest,AccountPageTest,LoginTest,AccountCheckTest,LoginLimitPageTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 878 tests, 0 failures, 1 skipped. Hashing is now slower (Argon2id is about 50–100 ms each), so the suite takes a little longer.

- [ ] **Step 6: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/java/vn/edu/hcmiu/sla/auth/User.java web/src/main/java/vn/edu/hcmiu/sla/auth/Accounts.java web/src/main/java/vn/edu/hcmiu/sla/auth/Sessions.java web/src/main/java/vn/edu/hcmiu/sla/auth/LoggedIn.java web/src/test/java/vn/edu/hcmiu/sla/auth/PasswordHashTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/RegisterTest.java web/src/test/java/vn/edu/hcmiu/sla/auth/AccountPageTest.java
git commit -F - <<'EOF'
feat(web): new passwords are hashed with Argon2id; old scrypt ones still work and are re-hashed at the next login

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 5: Security headers, and no inline code

**Files:**
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java`
- Modify: `web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncApiConfig.java`
- Create: `web/src/main/resources/static/js/devices.js`
- Modify: `web/src/main/resources/templates/school/devices.html`
- Test: `web/src/test/java/vn/edu/hcmiu/sla/core/SecurityHeadersTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/core/TemplatesFollowTheCspTest.java`, `web/src/test/java/vn/edu/hcmiu/sla/school/pages/DevicesPageTest.java`

**Interfaces:**
- Produces: `public static void SecurityConfig.securityHeaders(HttpSecurity http)`, used by both filter chains; constants `CONTENT_SECURITY_POLICY` and `PERMISSIONS_POLICY`.

- [ ] **Step 1: Write the failing tests**

Create `web/src/test/java/vn/edu/hcmiu/sla/core/SecurityHeadersTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;

import jakarta.servlet.RequestDispatcher;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

/** The security headers on both filter chains (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 5). */
@SpringBootTest
@AutoConfigureMockMvc
class SecurityHeadersTest {

    static final String CSP = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; "
            + "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            + "base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*";

    @Autowired
    MockMvc mvc;

    static void hasTheHeaders(ResultActions result) throws Exception {
        result.andExpect(header().string("Content-Security-Policy", CSP))
                .andExpect(header().string("Referrer-Policy", "same-origin"))
                .andExpect(header().string("Permissions-Policy",
                        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"))
                .andExpect(header().string("X-Content-Type-Options", "nosniff"))
                .andExpect(header().string("X-Frame-Options", "DENY"));
    }

    @Test
    void aPageHasThem() throws Exception {
        hasTheHeaders(mvc.perform(get("/auth/login")));
    }

    @Test
    void theErrorPageHasThem() throws Exception {
        hasTheHeaders(mvc.perform(get("/error").accept(MediaType.TEXT_HTML)
                .requestAttr(RequestDispatcher.ERROR_STATUS_CODE, 404)
                .requestAttr(RequestDispatcher.ERROR_REQUEST_URI, "/nope")));
    }

    @Test
    void theLaptopsSyncApiHasThem() throws Exception {
        hasTheHeaders(mvc.perform(get("/api/school/sync/check"))); // its own filter chain; refused, but with headers
    }
}
```

Create `web/src/test/java/vn/edu/hcmiu/sla/core/TemplatesFollowTheCspTest.java`:

```java
package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * The site's Content-Security-Policy refuses inline scripts, inline event handlers and style attributes (security
 * hardening spec, 5), and a browser does so silently, on the live site only. So no template may contain them: scripts
 * are files in static/js.
 */
class TemplatesFollowTheCspTest {

    @Test
    void noTemplateHasInlineCodeTheCspWouldRefuse() throws Exception {
        Resource[] templates = new PathMatchingResourcePatternResolver().getResources("classpath*:templates/**/*.html");

        assertThat(templates).isNotEmpty();
        for (Resource template : templates) {
            String html = template.getContentAsString(StandardCharsets.UTF_8);
            String name = template.getFilename();
            assertThat(html).as("%s: a <script> without src", name).doesNotContainPattern("<script(?![^>]*\\bsrc\\s*=)[^>]*>");
            assertThat(html).as("%s: an on…= event handler", name).doesNotContainPattern("\\s(th:)?on[a-z]+\\s*=");
            assertThat(html).as("%s: a style= attribute", name).doesNotContainPattern("\\s(th:)?style\\s*=");
        }
    }
}
```

In `DevicesPageTest.java`, add:

```java
    @Test
    void theDevicesPageRunsNoInlineCode() throws Exception { // security hardening spec, 5
        deviceKeys.create(an.id(), "My laptop", LocalDateTime.of(2026, 9, 1, 0, 0));

        assertThat(devicesPage())
                .contains("<script src=\"/js/devices.js\" defer></script>")
                .contains("<script src=\"/js/confirm.js\" defer></script>")
                .contains("data-confirm=\"Cancel this device? It will stop syncing immediately.\"")
                .doesNotContain("onsubmit");
    }
```

- [ ] **Step 2: Run them to verify they fail**

Run: `./mvnw -q test -Dtest='SecurityHeadersTest,TemplatesFollowTheCspTest,DevicesPageTest'`
Expected: FAIL: the three header tests (no Content-Security-Policy header), `noTemplateHasInlineCodeTheCspWouldRefuse` (`school/devices.html`: a `<script>` without src, then `onsubmit`), and `theDevicesPageRunsNoInlineCode`.

- [ ] **Step 3: Move Devices' code into files**

Create `web/src/main/resources/static/js/devices.js`:

```js
// Devices: Copy puts the new device key (shown once) on the clipboard. A file of its own: the site's
// Content-Security-Policy refuses inline scripts (security hardening spec, 5).
(function () {
  var button = document.getElementById("copy-key");
  if (!button) {
    return;
  }
  button.addEventListener("click", function () {
    var key = document.getElementById("new-key").textContent;
    navigator.clipboard.writeText(key).then(function () {
      button.textContent = "Copied";
    });
  });
})();
```

In `templates/school/devices.html`:
- delete the inline `<script>` block (the 7 lines from `<script>` to `</script>` after the key card);
- on the Cancel device form, replace `onsubmit="return confirm('Cancel this device? It will stop syncing immediately.');"` with `data-confirm="Cancel this device? It will stop syncing immediately."`;
- right before `</main>`, add:
  ```html
    <script th:src="@{/js/devices.js}" defer></script>
    <script th:src="@{/js/confirm.js}" defer></script>
  ```

- [ ] **Step 4: The headers on both chains**

In `SecurityConfig.java`:
- add the import `org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter.ReferrerPolicy`;
- after the `EVERY_ROLE` constant, add:
  ```java
      /** The Content-Security-Policy (security hardening spec, 5). */
      static final String CONTENT_SECURITY_POLICY = "default-src 'self'; "
              + "script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; "
              + "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; "
              + "base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*";
      static final String PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()";
  ```
- in `pages(…)`, right before `return http.build();`, add `securityHeaders(http);`;
- add the method:
  ```java
      /**
       * What both filter chains add (security hardening spec, 5): Content-Security-Policy, Referrer-Policy and
       * Permissions-Policy, on top of Spring Security's HSTS, nosniff, X-Frame-Options and no-store. Scripts come only
       * from the site and FullCalendar's folder on jsDelivr; form-action allows the redirect to the laptop app on this
       * computer that ends the Connect page; FullCalendar adds its own <style>, hence 'unsafe-inline' for styles only.
       */
      public static void securityHeaders(HttpSecurity http) throws Exception {
          http.headers(headers -> headers
                  .contentSecurityPolicy(csp -> csp.policyDirectives(CONTENT_SECURITY_POLICY))
                  .referrerPolicy(referrer -> referrer.policy(ReferrerPolicy.SAME_ORIGIN))
                  .permissionsPolicyHeader(permissions -> permissions.policy(PERMISSIONS_POLICY)));
      }
  ```

In `SyncApiConfig.java`, add the import `vn.edu.hcmiu.sla.core.SecurityConfig`, and in `syncApi(…)`, right before `return http.build();`, add `SecurityConfig.securityHeaders(http);`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./mvnw -q test -Dtest='SecurityHeadersTest,TemplatesFollowTheCspTest,DevicesPageTest,SyncApiTest,ConnectApiTest'`
Expected: PASS.

Then `./mvnw -B test`. Expected: 883 tests, 0 failures, 1 skipped.

- [ ] **Step 6: Commit**

```bash
git add web/src/main/java/vn/edu/hcmiu/sla/core/SecurityConfig.java web/src/main/java/vn/edu/hcmiu/sla/school/sync/SyncApiConfig.java web/src/main/resources/static/js/devices.js web/src/main/resources/templates/school/devices.html web/src/test/java/vn/edu/hcmiu/sla/core/SecurityHeadersTest.java web/src/test/java/vn/edu/hcmiu/sla/core/TemplatesFollowTheCspTest.java web/src/test/java/vn/edu/hcmiu/sla/school/pages/DevicesPageTest.java
git commit -F - <<'EOF'
feat(web): every response carries a Content-Security-Policy, Referrer-Policy and Permissions-Policy; Devices' scripts move to a file

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 6: Dependabot, the README, and a look in the browser

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-07-security-hardening-design.md` (status line)

- [ ] **Step 1: Dependabot**

Create `.github/dependabot.yml`:

```yaml
# Weekly update pull requests against main, the default branch (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 6).
# Dependabot's security alerts are switched on in GitHub's settings (README, "Security").
version: 2
updates:
  - package-ecosystem: maven
    directory: /web
    schedule:
      interval: weekly
  - package-ecosystem: pip
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: pip
    directory: /agent
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: docker
    directory: /web
    schedule:
      interval: weekly
  - package-ecosystem: docker-compose
    directory: /deploy/server
    schedule:
      interval: weekly
```

- [ ] **Step 2: The README**

1. In "Always on: AWS Lightsail", step 5, delete the sentence "(`--branch main`: GitHub's default branch for this repository isn't `main`.)". The default branch is `main` now; the `--branch main` in the clone command stays and does no harm.
2. After the "Accounts and roles" section (before its `---`), add:
   ```markdown
   ## Security

   What the site does by itself ([design](docs/superpowers/specs/2026-10-07-security-hardening-design.md)):

   - **Login limits:** after 5 wrong passwords for one email from one network within 15 minutes, or 100 from one network for any emails, the password isn't checked until the wait ends ("Too many wrong passwords. Try again in N minutes."). An unknown email counts like a wrong password.
   - **Bots:** a hidden "Leave this empty" field on register; at most 30 new accounts per network per hour and 20 failed laptop Connect trade-ins per network in 15 minutes. The counts live in memory, so a restart clears them.
   - **Passwords:** Argon2id. Older (scrypt) passwords keep working and are re-hashed at their next login.
   - **Headers:** Content-Security-Policy (scripts only from the site and FullCalendar's folder on jsDelivr, never inline), Referrer-Policy and Permissions-Policy, plus HSTS, nosniff and X-Frame-Options.
   - **Dependencies:** Dependabot opens weekly update pull requests (`.github/dependabot.yml`).

   **Settings only the owner can change:**

   1. GitHub → Settings → Code security: turn on **Dependabot alerts** and **Dependabot security updates**.
   2. Aiven console → the service → allowed IP addresses: only the server's static IP, `13.228.157.213`. Add your own IP while you need direct access.
   3. Aiven console → users: a user for the site with rights on `defaultdb` only (it still creates and changes tables, through Flyway). Put it in `deploy/server/.env` as `DATABASE_URL`, run `update.sh`, and keep `avnadmin` for yourself.
   ```
3. In "Rules for the Java code", add after rule 5:
   ```markdown
   6. JavaScript lives in files in `web/src/main/resources/static/js/`, never in a template (`<script>` without `src`, `onclick=`, `style=`): the Content-Security-Policy refuses inline code, and `TemplatesFollowTheCspTest` fails on it.
   ```

- [ ] **Step 3: Mark the spec approved**

In the spec, replace `**Status:** Draft, waiting for review. One plan.` with:

```markdown
**Status:** Approved 2026-10-07. Plan: docs/superpowers/plans/2026-10-07-security-hardening.md.
```

(Skip this step if the spec already says it.)

- [ ] **Step 4: Run everything**

Run: `./mvnw -B test`
Expected: 883 tests, 0 failures, 1 skipped (`accentsAreIgnoredOnMySql`).

- [ ] **Step 5: Commit**

```bash
git add .github/dependabot.yml README.md docs/superpowers/specs/2026-10-07-security-hardening-design.md
git commit -F - <<'EOF'
docs: Dependabot proposes weekly updates; the README explains what the site guards against and the owner's settings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 6: A look in the browser (the student)**

The site needs a real database. Don't use the laptop's usual one (`school_life`): other branches share it, and a migration they don't have would stop them starting (Flyway: "applied migration not resolved locally"). A separate database avoids that:

1. In a MySQL prompt as root: `CREATE DATABASE school_life_hardening CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON school_life_hardening.* TO 'sla_app'@'localhost';`
2. Copy the laptop's `.env` into the worktree root and change the database name at the end of `DATABASE_URL` to `school_life_hardening`.
3. From `web/`: `./mvnw spring-boot:run`, then open http://localhost:5000 (Chrome, with DevTools' Console open), at 1400 px and 390 px wide.

Check:
- **Register:** no extra field shows, and Tab skips from Confirm password straight to Create account. Make two accounts.
- **Login limits:** 5 wrong passwords for one account, then the right one: "Too many wrong passwords. Try again in 15 minutes."
- **The timetable** (School → Timetable): the calendar draws.
- **Devices:** add a device by name, then Copy shows "Copied". Cancel device asks first.
- **The Console** shows no "Content-Security-Policy" errors on any of these pages.
- **After the merge, on the live site:** the laptop app's Connect button still goes all the way through (Accounts → Change → Connect). That's the `form-action` check, which needs the real laptop app.

Stop the site with Ctrl+C. Delete the copied `.env` (it's gitignored).

- [ ] **Step 7: Hand back**

Report the test totals (Java: 843 → the new total, 0 failures). Pushing, the pull request (it needs a teammate's approving review, the lecturer's condition), merging and `update.sh` are not part of this plan: ask the student first. GitHub's MySQL job must pass before the merge. After the merge, the student does the README's three "Settings only the owner can change".
