# School-Life-Assistant: security hardening (limits, bots, Argon2id, headers, dependency scanning)

**Date:** 2026-10-07
**Scope:** limits on wrong passwords, new accounts and the laptop's Connect trade-in; a honeypot on register; Argon2id password hashes, with old ones upgraded at login; Content-Security-Policy, Referrer-Policy and Permissions-Policy headers; Dependabot.
**Owner:** Nguyen Khang Vy
**Status:** Approved 2026-10-07. Plan: docs/superpowers/plans/2026-10-07-security-hardening.md.
**Builds on:** [Site roles](2026-10-06-site-roles-design.md) (SecurityConfig, AccountCheck, LoggedIn, Accounts, Sessions; this branch starts from `site-roles`), [Connect button](2026-10-04-connect-button-design.md) (the Connect page's redirect to the laptop, the trade-in) and [Java website](2026-09-26-java-website-design.md). Everything there stays the same unless this document says otherwise.

---

## 1. Goal

On 2026-10-07 the site was checked against a 20-item "before you launch" security list: 13 items done, 4 partial, 3 missing. This document builds what the site can fix itself:

| Checklist item | Today | After |
|---|---|---|
| 11 Hash passwords | scrypt; the course spec names BCrypt or Argon2 | Argon2id for every new hash; old ones upgraded at login |
| 12 Login limits | unlimited guesses | email + IP pair and per-IP limits |
| 13 Block bots | nothing | honeypot and a per-IP limit on register; a limit on the Connect trade-in |
| 18 Security headers | HSTS, nosniff, X-Frame-Options, no-store | plus Content-Security-Policy, Referrer-Policy, Permissions-Policy |
| 20 Scan dependencies | Dependabot alerts off, no config | `dependabot.yml`; the student turns alerts on |

The course spec lists "Rate Limiting: Prevent brute force attacks on login", "XSS Prevention: Escape output, Content Security Policy headers" and "Password Security: BCrypt or Argon2" as non-negotiable.

### Decided with the student (2026-10-07)

- **Login limits block the email + IP pair,** plus a higher cap per IP. A stranger can't lock a classmate out by typing their email, because the owner on another network still gets in.
- **The numbers allow for campus Wi-Fi,** where many students share one public IP: 5 wrong passwords per email + IP in 15 minutes; 100 per IP in 15 minutes; 30 new accounts per IP per hour; 20 failed Connect trade-ins per IP in 15 minutes. IPv6 addresses are grouped by their /64.
- **Bots:** a honeypot and the per-IP limits. No CAPTCHA.
- **Argon2id** with OWASP's settings for new hashes. Old scrypt hashes keep working and are upgraded at the next login.
- **Approach A:** an in-memory limiter in the site, which runs as one server. Not a database table, not Caddy.
- **Headers** as in §5. **Dependabot** for Maven, pip, GitHub Actions, Docker and Docker Compose.

### Not in scope

- A CAPTCHA (Turnstile): later, only if fake accounts actually appear
- Locking accounts; limits that survive a restart or work across several servers
- Audit lines for blocked logins (site roles stage 3 adds the audit log)
- Encrypting backups; the Aiven and GitHub settings, which the student changes (§7)
- The laptop app: no change, no new release

---

## 2. How it fits together

```
POST /auth/login ─▶ LoginLimitFilter ── over a limit ─▶ /auth/login?wait=N   (password not checked)
                        │ under
                        ▼
                    passwordLogin (Spring's DaoAuthenticationProvider)
                        ├─ wrong password / unknown email ─▶ loginFailed: count pair + IP ─▶ ?error
                        ├─ right password, deactivated ─────▶ ?deactivated (not counted)
                        └─ right password ─▶ old hash? re-hash as Argon2id (Accounts.rehash)
                                              ─▶ LoggedIn: clear the pair, last login, session ← account as saved

POST /auth/register ─▶ honeypot filled? ─▶ IP over 30/hour? ─▶ field checks ─▶ account (Argon2id), counted
POST /api/school/sync/connect ─▶ IP over 20 failures? 429 ─▶ trade-in; invalid_code counted

Every response (both filter chains) ─▶ CSP, Referrer-Policy, Permissions-Policy, plus HSTS, nosniff, X-Frame-Options
```

| Package | What it gets |
|---|---|
| `core` | `Attempts` (the limiter), `ClientAddress` (the visitor's IP, IPv6 grouped by /64), the header settings |
| `auth` | `LoginLimits` (the two login rules), `LoginLimitFilter`, counting in the login handlers, the register honeypot and limit, the Argon2id encoder, `Accounts.rehash`, `LoggedIn` putting the account as saved into the session |
| `school.sync` | the Connect trade-in limit |
| templates, static | the wait message on login; the honeypot field; `js/devices.js`; `data-confirm` on Cancel device |
| `.github` | `dependabot.yml` |

---

## 3. Limits

### 3.1 The limiter

`Attempts` (`core`) counts events per key within a time window, using the site's `Clock`:

- `add(key)` records one event now; `count(key, window)` is the number within the window; `clear(key)` forgets the key; `waitFor(key, limit, window)` is how long until the count drops below the limit (zero when it already is).
- **Keys:** `login-pair:<email>|<ip>`, `login-ip:<ip>`, `register-ip:<ip>`, `connect-ip:<ip>`.
- **Memory:** a key keeps only events younger than an hour, the longest window. A key with none left is removed. When the map holds more than 10,000 keys, the next `add` first drops every key whose newest event is older than an hour.
- Safe when many requests arrive at once (a concurrent map, one lock per key).

### 3.2 The visitor's address

`ClientAddress.of(request)` is `request.getRemoteAddr()`. On the server that is the visitor's address: Caddy sets `X-Forwarded-For`, `SERVER_FORWARD_HEADERS_STRATEGY=framework` makes the site read it, and only Caddy can reach the site. An IPv4 address is kept as it is. An IPv6 address becomes its first 64 bits (`2001:db8:1:2::/64`), so one device can't get around a limit by changing its IPv6 address.

### 3.3 Login

| Rule | Limit | Key |
|---|---|---|
| One email from one IP | 5 wrong passwords in 15 minutes | the email as login reads it (trimmed, lower-case) + IP |
| One IP, any emails | 100 wrong passwords in 15 minutes | IP |

- **Before the password is checked:** `LoginLimitFilter` runs in front of Spring Security's login, for `POST /auth/login` only. If either rule has reached its limit, the password isn't checked and the browser goes to `/auth/login?wait=N`. N is the minutes until the blocking rule's count drops below its limit (`waitFor`), rounded up, at least 1; if both rules block, the longer wait. Two tries at the same moment can push a count past its limit; the wait then lasts until enough old tries have left the window.
- **The login page:** "Too many wrong passwords. Try again in N minutes." ("1 minute" for N = 1.)
- **Counted** (both keys): a wrong password or an unknown email, which Spring reports alike (`BadCredentialsException`). **Not counted:** the right password on a deactivated account; a blocked try.
- **A successful login** clears the pair, not the IP count.
- **The app log** gets one line when a key reaches its limit: "Login limit reached for 203.0.113.7 (one email from one IP)". It never includes the email.

### 3.4 Register

Checked in this order, before the usual field checks:

1. **Honeypot:** an extra text field `website`, labelled "Leave this empty", inside a wrapper moved off-screen by CSS (class `trap`), with `aria-hidden="true"` on the wrapper and `tabindex="-1"` and `autocomplete="off"` on the field. If it's filled in, no account is made and the form comes back with "Please try again." (the typed name and email kept, the passwords empty).
2. **IP limit:** 30 accounts created from one IP within an hour. At the limit, no account is made: "Too many new accounts from this network. Try again in N minutes."

Only accounts actually created count toward the limit.

### 3.5 The laptop's Connect trade-in

`POST /api/school/sync/connect` needs no login (the laptop app calls it). After 20 failed trade-ins from one IP within 15 minutes, it answers 429 `{"error": "too_many_attempts"}` without looking at the code. A failed trade-in is today's 400 `invalid_code` (unknown, expired or used code, or a wrong verifier). A malformed body (422) isn't counted: it can't be a guess. The laptop app shows its usual "The web app answered HTTP 429" text, so it needs no change.

---

## 4. Argon2id passwords

- **The encoder:** the `PasswordEncoder` bean becomes Spring's `DelegatingPasswordEncoder`, with `argon2` as the id for new hashes: `new Argon2PasswordEncoder(16, 32, 1, 19456, 2)` (salt 16 bytes, hash 32 bytes, 1 thread, 19 MiB, 2 passes: OWASP's settings). A hash without a `{…}` prefix is the old scrypt (Werkzeug) format, and `WerkzeugPasswordEncoder` checks it (`setDefaultPasswordEncoderForMatches`). New hashes look like `{argon2}$argon2id$v=19$m=19456,t=2,p=1$…`, about 100 characters (the column holds 255).
- **New hashes everywhere:** register, Password, and stage 2's temporary passwords. `WerkzeugPasswordEncoder` stays, for checking old hashes.
- **Upgrade at login:** the `passwordLogin` provider gets a `UserDetailsPasswordService`, `Accounts.rehash`. When someone logs in with the right password and a hash that isn't Argon2id, Spring re-hashes the typed password and calls it. It saves the new hash with `User.rehash(hash)`, which leaves `updated_at` and `updated_by` alone, because nobody changed anything.
- **The session:** Spring keeps the account as it was before the upgrade in the session. `LoggedIn` therefore puts the account as now saved into the session (`Sessions.refresh`, with no second session id; Spring gave a new one at login). Otherwise `AccountCheck` would see a different hash on the next click and log the person out with "Your password was changed."
- **Accounts that never log in** keep scrypt, which is still secure.
- **Cost:** about 19 MiB and 50–100 ms per hash, only at login and when a password is set.

---

## 5. Security headers

Every response of both filter chains (pages and the sync API) gets:

**Content-Security-Policy:**

```
default-src 'self'; script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*
```

- **Scripts:** the site's own files and FullCalendar's folder on jsDelivr, which `timetable.html` already pins with an integrity hash. Inline scripts are refused.
- **`form-action … http://127.0.0.1:*`:** the Connect page's form ends with a redirect to the laptop app on the same computer (`http://127.0.0.1:<port>/callback`). Browsers check that redirect against `form-action`, so without this the laptop could never connect.
- **`style-src 'unsafe-inline'`:** FullCalendar adds its own `<style>` element. Only styles get this exception.

**Referrer-Policy:** `same-origin`: links out (Outlook, IUPay, GitHub) don't say which page they came from.

**Permissions-Policy:** `camera=(), microphone=(), geolocation=(), payment=(), usb=()`. The site uses none of these. Copy key's clipboard access isn't affected.

**Unchanged:** HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Cache-Control: no-store`.

**Code that must move:** the Copy key script in `school/devices.html` becomes `static/js/devices.js`. The Cancel device form's `onsubmit="return confirm('Cancel this device? It will stop syncing immediately.')"` becomes `data-confirm` with the same question, which `confirm.js` already handles (as on Friends).

---

## 6. Dependency scanning

`.github/dependabot.yml` opens weekly update pull requests against `main`, the repository's default branch:

| Ecosystem | Directory | What it watches |
|---|---|---|
| `maven` | `/web` | Spring Boot, BouncyCastle, the other Java libraries |
| `pip` | `/` | the root `pyproject.toml` and `requirements-dev.txt` |
| `pip` | `/agent` | the laptop app's `pyproject.toml` |
| `github-actions` | `/` | the workflows' actions |
| `docker` | `/web` | the Dockerfile's Java images |
| `docker-compose` | `/deploy/server` | the Caddy image |

The README also loses its out-of-date note that the default branch isn't `main`.

---

## 7. Steps only the student can do

1. **GitHub** → Settings → Code security: turn on **Dependabot alerts** and **Dependabot security updates**.
2. **Aiven console**, allowed IP addresses: only the server's static IP `13.228.157.213`. Add the laptop's IP when direct access is needed.
3. **Aiven console**, users: create a user for the site with rights on `defaultdb` only. It still needs to create and change tables, for Flyway. Put it in `deploy/server/.env` as `DATABASE_URL`, run `update.sh`, and keep `avnadmin` for yourself.

The README gets a short **Security** section: what the site protects (limits, honeypot, hashes, headers, scanning) and these three steps.

---

## 8. Errors and security

- **No hints about accounts:** an unknown email counts and blocks exactly like a wrong password, and a blocked try never checks the password. The wait message is the same whether or not the email has an account.
- **The IP comes from Caddy only** (§3.2). A visitor can't choose their own address by sending an `X-Forwarded-For` header.
- **Messages use `th:text`.** The honeypot field and its wrapper carry no user text.
- **Restarts:** the counts live in memory and a restart, which happens only on deploy, clears them.

---

## 9. Testing

As the existing tests: JUnit 5, MockMvc, H2 in MySQL mode, and once on MySQL in GitHub's checks. Limit tests use the test clock, and each test gets its own fake IP (MockMvc's `remoteAddr`) so tests don't share counts.

- **Limiter (unit):** counting within a window; old events leaving it; `waitFor` at, below and past the limit; the wait message's minutes rounded up, at least 1; clearing; the sweep above 10,000 keys; IPv4 kept, IPv6 grouped by /64.
- **Login:**
  - the 5th wrong password for one email + IP blocks the 6th try, even with the right password, until the window passes
  - an unknown email counts like a wrong password
  - another email from the same IP is still allowed until 100
  - the same email from another IP is allowed
  - a right password clears the pair but not the IP count
  - a blocked try doesn't extend the block
  - the deactivated message isn't counted
  - the wait message shows the right minutes
- **Register:** the honeypot refuses and makes no account; 30 accounts from one IP within an hour, then the message; field checks still work.
- **Connect trade-in:** 20 `invalid_code` answers, then 429 `too_many_attempts` even for a good code; a malformed body isn't counted.
- **Argon2id:**
  - a new account's hash starts with `{argon2}$argon2id$`
  - Password stores Argon2id
  - an old scrypt account logs in, its stored hash becomes Argon2id with `updated_at` unchanged, and the next click still works
  - a wrong password on an old account changes nothing
  - a placeholder hash (`"x"`) fails without an error
- **Headers:** a page, the error page and a sync API response carry the three headers with exactly the values in §5.
- **Guard:** no template contains inline `<script>` code, `on…=` attributes or `style=` attributes.
- **Devices:** the page loads `js/devices.js`, and Cancel has `data-confirm`.
- **By hand, in the browser:**
  - the timetable calendar draws
  - Copy key works
  - Cancel asks first
  - the laptop's Connect button goes all the way through
  - the browser console shows no CSP errors

---

## 10. Risks

- **Campus Wi-Fi shares one IP.** The numbers leave room, and the log line shows if blocks happen in real use.
- **The CSP could block something the tests don't cover.** The by-hand look goes through every script, and the console names any block.
- **Argon2 memory:** 19 MiB per hash; dozens at once still fit in the 1 GB container.
- **Upgrade at login:** if putting the account into the session failed, the person would be logged out on their next click. A test covers it.
- **Stage 2 (Users page)** must hash temporary passwords through the same `PasswordEncoder` bean, which this document makes Argon2id.

---

## 11. Build order

One plan, six tasks, each with its tests:

1. `Attempts` and `ClientAddress` (`core`).
2. Login limits: `LoginLimits`, `LoginLimitFilter`, counting in the login handlers, the wait message.
3. The register honeypot and limit; the Connect trade-in limit.
4. Argon2id, the upgrade at login (`Accounts.rehash`, `User.rehash`), and `LoggedIn` putting the account as saved into the session.
5. Security headers on both chains; `js/devices.js`; `data-confirm` on Cancel device; the guard test.
6. `dependabot.yml`, the README's Security section and default-branch fix, and the by-hand look.
