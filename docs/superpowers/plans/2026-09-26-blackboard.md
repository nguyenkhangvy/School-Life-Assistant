# Blackboard in the School Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the student's Blackboard announcements, assignments with due dates, grades and new course materials into the School module, synced by the laptop agent next to EduSoft.

**Architecture:** The laptop agent logs in to Blackboard's normal login form (separate credentials in Windows Credential Manager, a Blackboard-only TLS setting), reads Blackboard's REST API with that session, keeps only this semester's courses (the courses registered on EduSoft), and uploads a new `blackboard` section in the shared data format. EduSoft and Blackboard pause and fail independently. The web app stores the section in four new tables, writes "What changed" lines, shows a status line per system, a Courses page, Overview boxes and orange deadlines in the calendar.

**Tech Stack:** Python 3.12, requests, beautifulsoup4, keyring, pydantic (agent and shared format); Flask, SQLAlchemy, Flask-Migrate, Jinja, FullCalendar 6.1.21 (web app); pytest, responses (tests). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-26-blackboard-design.md` (builds on `docs/superpowers/specs/2026-09-25-edusoft-first-phase1-design.md`).

## Global Constraints

- Blackboard host: only `https://blackboard.hcmiu.edu.vn`. Redirects elsewhere are refused; Microsoft/SAML sign-in or a CAPTCHA pauses Blackboard.
- Blackboard TLS setting, for that host only: cipher string `ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA:@SECLEVEL=2`, `minimum_version = TLSv1_2`, certificate and hostname checks on. RSA key exchange stays refused. All other hosts keep Python's defaults.
- Blackboard password stored only in keyring service `SchoolLifeAssistant-Blackboard` (username = Blackboard username) and registered with `sla_agent.log.protect`.
- Read-only: the only non-`GET` request to Blackboard is the login form `POST`. EduSoft's registration page (`default.aspx?page=dkmonhoc`) is only ever fetched with `GET`.
- User agent on every request: `SchoolLifeAssistant/0.1 (IU student project)`.
- Uploaded limits: announcement text ≤ 5,000 characters, feedback ≤ 1,000 characters, material folders at most 2 levels below the top.
- Every uploaded link starts with `https://blackboard.hcmiu.edu.vn/`.
- New error code for Blackboard format problems: `source_changed`. `edusoft_changed` stays for EduSoft.
- Times: timezone-aware in the shared format, naive UTC in the database, Vietnam time (UTC+7) on pages.
- Current courses: rows with status `Đã lưu vào CSDL` in EduSoft's "DANH SÁCH MÔN HỌC ĐÃ CHỌN"; fallback: current timetable course codes.
- Commands on this machine: `.venv/Scripts/python.exe -m pytest …` (Git Bash) from the project root. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An announcement or feedback full of HTML (scripts, iframes, styles, a 20,000-character body)** must become safe plain text within its limit and render escaped. Tests: Task 5 (`html_to_text`), Task 10 (escaped rendering).
2. **A course that hides grades or materials (HTTP 403/404 on one endpoint)** must give an empty list for that part, not fail the whole Blackboard sync. Tests: Task 1 (`api` returns `None`), Task 5 (`read_blackboard` with a refused endpoint).
3. **Columns without a due date and calculated total columns** must not crash; totals are left out, undated items still listed. Test: Task 5.
4. **EduSoft paused (or failing) while Blackboard works, and the other way round** must still upload the working system, using the last known registered-course list. Tests: Task 6.
5. **A deadline at 23:59 or 00:30 Vietnam time** must appear on the correct Vietnam day in the calendar and in "Due soon". Tests: Task 10.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `agent/sla_agent/guarded_http.py` (new) | One-site HTTP: redirect checks, https upgrade, network errors, CAPTCHA detection | 1 |
| `agent/sla_agent/edusoft_client.py` (modify) | Uses `guarded_http`; reads the registration page | 1, 4 |
| `agent/sla_agent/blackboard_client.py` (new) | Blackboard TLS setting, login, logout, REST calls with paging | 1 |
| `agent/sla_agent/errors.py` (modify) | `SourceChanged` | 1 |
| `agent/sla_agent/credentials.py`, `state.py`, `cli.py` (modify) | Blackboard login details, `setup --blackboard`, status, forget, run, fetch | 2, 6, 7 |
| `contract/sla_contract/schema.py` (modify) | `blackboard` section, `EDUSOFT_SECTIONS`, `source_changed` | 3 |
| `agent/sla_agent/parsers/registration.py` (new) | Registered courses from the registration page | 4 |
| `agent/sla_agent/parsers/blackboard.py` (new) | Pure readers: course choice, HTML→text, announcements, assignments, materials | 5 |
| `agent/sla_agent/blackboard_reader.py` (new) | Calls the API through a client and builds the `Blackboard` section | 5 |
| `agent/sla_agent/sync.py` (modify) | EduSoft and Blackboard synced and paused independently | 6 |
| `agent/tools/anonymize_blackboard.py`, `agent/tools/anonymize_registration.py` (new) | Turn saved real answers into anonymized test copies | 4, 7 |
| `app/school/models.py` (modify), `migrations/versions/*_blackboard_tables.py` (new) | Four Blackboard tables | 8 |
| `app/school/services/ingest.py`, `changes.py` (modify) | Save the section; "What changed" lines | 8 |
| `app/school/services/sync_status.py` (modify) | One status line per system; Blackboard wording | 9 |
| `app/school/services/schedule.py`, `app/school/routes.py`, templates, `app/static/js/timetable.js`, `app/static/css/style.css` (modify/new) | Courses pages, Overview boxes, deadlines in the calendar | 10 |

---

### Task 1: One-site HTTP helper and the Blackboard client

**Files:**
- Create: `agent/sla_agent/guarded_http.py`, `agent/sla_agent/blackboard_client.py`, `agent/tests/blackboard_fakes.py`, `agent/tests/test_blackboard_client.py`
- Modify: `agent/sla_agent/errors.py`, `agent/sla_agent/edusoft_client.py`

**Interfaces:**
- Produces: `guarded_http.guarded_request(session, method, url, host, data=None, site="EduSoft") -> requests.Response`; `guarded_http.asks_for_verification(soup) -> bool`; `errors.SourceChanged` (code `"source_changed"`); `blackboard_client.BASE_URL = "https://blackboard.hcmiu.edu.vn"`; `blackboard_tls_context() -> ssl.SSLContext`; `BlackboardTLS(HTTPAdapter)`; `BlackboardClient(session=None)` with `.user_id: str | None`, `.capture: dict | None`, `.login(username, password)`, `.api(path) -> dict | None`, `.api_all(path) -> list[dict]`, `.logout()`. `path` is relative to `/learn/api/public`, e.g. `"/v1/users/me"`.

- [ ] **Step 1: Write the fake Blackboard pages**

Create `agent/tests/blackboard_fakes.py` (mirrors the real login form checked on 2026-09-26):

```python
"""Hand-written Blackboard answers for tests. The login form copies the real one at
https://blackboard.hcmiu.edu.vn/webapps/login/ (checked 2026-09-26)."""

BB = "https://blackboard.hcmiu.edu.vn"
LOGIN_URL = f"{BB}/webapps/login/"
LOGOUT_URL = f"{BB}/webapps/login/?action=logout"
API = f"{BB}/learn/api/public"

LOGIN_FORM = """
<form action="/webapps/login/" method="POST" id="login-form" name="login">
  <input type="text" name="user_id" id="user_id" value="">
  <input type="password" name="password" id="password" value="">
  <input type="submit" value="Login" name="login" id="entry-login">
  <input type="hidden" name="action" value="login">
  <input type="hidden" name="new_loc" value="">
  <input type="hidden" name="blackboard.platform.security.NonceUtil.nonce" value="NONCE-123">
</form>"""

LOGIN_PAGE = f"<html><head><title>Blackboard Learn</title></head><body>{LOGIN_FORM}</body></html>"
LOGIN_FAILED = f"<html><body><div id='loginErrorMessage'>The username or password you typed is incorrect.</div>{LOGIN_FORM}</body></html>"
CAPTCHA_LOGIN_PAGE = LOGIN_PAGE.replace("</form>", '<div class="g-recaptcha"></div></form>')
HOME_PAGE = "<html><body><div id='globalNavPageNavArea'>My Institution</div></body></html>"
ME = {"id": "_77_1", "userName": "student", "studentId": "S1"}
```

- [ ] **Step 2: Write the failing tests**

Create `agent/tests/test_blackboard_client.py`:

```python
import ssl
from urllib.parse import parse_qs

import pytest
import responses

from agent.tests.blackboard_fakes import API, CAPTCHA_LOGIN_PAGE, HOME_PAGE, LOGIN_FAILED, LOGIN_PAGE, LOGIN_URL, ME
from sla_agent.blackboard_client import BlackboardClient, BlackboardTLS, blackboard_tls_context
from sla_agent.errors import BadCredentials, ExtraVerification, SessionExpired, SourceChanged


def test_the_tls_setting_allows_blackboards_dhe_sha1_suites_but_not_rsa_key_exchange():
    context = blackboard_tls_context()
    names = {cipher["name"] for cipher in context.get_ciphers()}

    assert "DHE-RSA-AES128-SHA" in names
    assert "AES128-SHA" not in names  # RSA key exchange: no forward secrecy
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_the_tls_setting_is_used_only_for_blackboard():
    client = BlackboardClient()

    assert isinstance(client.session.get_adapter("https://blackboard.hcmiu.edu.vn/webapps/login/"), BlackboardTLS)
    assert not isinstance(client.session.get_adapter("https://edusoftweb.hcmiu.edu.vn/"), BlackboardTLS)


def posts():
    return [call for call in responses.calls if call.request.method == "POST"]


@responses.activate
def test_login_sends_the_form_with_its_nonce_and_learns_who_is_logged_in():
    responses.get(LOGIN_URL, body=LOGIN_PAGE)
    responses.post(LOGIN_URL, body=HOME_PAGE)
    responses.get(f"{API}/v1/users/me", json=ME)
    client = BlackboardClient()

    client.login("student", "bb-s3cret")

    [call] = posts()
    form = {k: v[0] for k, v in parse_qs(call.request.body, keep_blank_values=True).items()}
    assert form == {
        "user_id": "student", "password": "bb-s3cret", "login": "Login", "action": "login", "new_loc": "",
        "blackboard.platform.security.NonceUtil.nonce": "NONCE-123",
    }
    assert client.user_id == "_77_1"
    assert all("SchoolLifeAssistant" in c.request.headers["User-Agent"] for c in responses.calls)


@responses.activate
def test_a_wrong_password_raises_bad_credentials_after_one_attempt():
    responses.get(LOGIN_URL, body=LOGIN_PAGE)
    responses.post(LOGIN_URL, body=LOGIN_FAILED)

    with pytest.raises(BadCredentials):
        BlackboardClient().login("student", "wrong")

    assert len(posts()) == 1
    assert not any("/learn/api/" in c.request.url for c in responses.calls)


@responses.activate
def test_a_captcha_stops_before_sending_the_password():
    responses.get(LOGIN_URL, body=CAPTCHA_LOGIN_PAGE)

    with pytest.raises(ExtraVerification):
        BlackboardClient().login("student", "bb-s3cret")

    assert posts() == []


@responses.activate
def test_a_redirect_to_microsoft_sign_in_pauses_instead_of_following():
    responses.get(LOGIN_URL, status=302, headers={"Location": "https://login.microsoftonline.com/x/saml2"})

    with pytest.raises(ExtraVerification):
        BlackboardClient().login("student", "bb-s3cret")


@responses.activate
def test_api_answers_401_as_session_expired_and_403_or_404_as_nothing():
    responses.get(f"{API}/v1/a", status=401, json={"status": 401})
    responses.get(f"{API}/v1/b", status=403, json={"status": 403})
    responses.get(f"{API}/v1/c", status=404, json={"status": 404})
    client = BlackboardClient()

    with pytest.raises(SessionExpired):
        client.api("/v1/a")
    assert client.api("/v1/b") is None
    assert client.api("/v1/c") is None


@responses.activate
def test_api_answers_that_are_not_json_mean_the_format_changed():
    responses.get(f"{API}/v1/a", body="<html>maintenance</html>")

    with pytest.raises(SourceChanged):
        BlackboardClient().api("/v1/a")


@responses.activate
def test_api_all_follows_paging_and_captures_every_answer():
    responses.get(f"{API}/v1/items?limit=2",
                  json={"results": [{"id": 1}, {"id": 2}], "paging": {"nextPage": "/learn/api/public/v1/items?limit=2&offset=2"}})
    responses.get(f"{API}/v1/items?limit=2&offset=2", json={"results": [{"id": 3}]})
    client = BlackboardClient()
    client.capture = {}

    assert [item["id"] for item in client.api_all("/v1/items?limit=2")] == [1, 2, 3]
    assert set(client.capture) == {"/v1/items?limit=2", "/v1/items?limit=2&offset=2"}


@responses.activate
def test_api_all_of_a_refused_list_is_empty():
    responses.get(f"{API}/v1/items", status=403, json={"status": 403})

    assert BlackboardClient().api_all("/v1/items") == []
```

- [ ] **Step 3: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_blackboard_client.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'sla_agent.blackboard_client'`.

- [ ] **Step 4: Add `SourceChanged`**

In `agent/sla_agent/errors.py`, after `class ParseError`, add:

```python
class SourceChanged(AgentError):
    """Blackboard's answers don't look the way the reader expects: its format probably changed."""

    code = "source_changed"
```

- [ ] **Step 5: Create the one-site HTTP helper**

Create `agent/sla_agent/guarded_http.py`:

```python
"""HTTP that only talks to one site: every redirect is checked, http becomes https,
network problems become NetworkError. Shared by the EduSoft and Blackboard clients."""

from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from sla_agent.errors import ExtraVerification, NetworkError, UnexpectedRedirect

TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5
MICROSOFT_HOSTS = ("login.microsoftonline.com", "login.live.com", "login.windows.net")
VERIFICATION_HINTS = ("captcha", "recaptcha", "otp", "maxacnhan", "xacthuc")


def safe_url(url, host, site):
    parts = urlsplit(url)
    if parts.hostname in MICROSOFT_HOSTS:
        raise ExtraVerification(f"{site} sent the login to Microsoft sign-in.")
    if parts.hostname != host:
        raise UnexpectedRedirect(f"{site} tried to redirect to {parts.hostname}; not followed.")
    # Same site over plain http: go over https instead, never send anything unencrypted.
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))


def guarded_request(session, method, url, host, data=None, site="EduSoft"):
    """One request to `host`, following redirects by hand so every hop is checked."""
    url = safe_url(url, host, site)
    for _ in range(MAX_REDIRECTS + 1):
        try:
            response = session.request(method, url, data=data, timeout=TIMEOUT_SECONDS, allow_redirects=False)
        except (requests.ConnectionError, requests.Timeout) as error:
            raise NetworkError(f"{site} couldn't be reached ({error.__class__.__name__}).") from None
        if response.status_code >= 500:
            raise NetworkError(f"{site} answered with HTTP {response.status_code}.")
        if response.is_redirect:
            url = safe_url(urljoin(url, response.headers["Location"]), host, site)
            method, data = "GET", None
            continue
        response.encoding = response.encoding or "utf-8"
        return response
    raise NetworkError(f"{site} redirected too many times.")


def asks_for_verification(soup):
    for tag in soup.find_all(["input", "img", "div", "iframe"]):
        text = " ".join(str(tag.get(attr, "")) for attr in ("name", "id", "src", "class")).lower()
        if any(hint in text for hint in VERIFICATION_HINTS):
            return True
    return False
```

- [ ] **Step 6: Make the EduSoft client use it**

In `agent/sla_agent/edusoft_client.py`:
- Replace the import line `from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit` with `from urllib.parse import urlencode, urljoin` (keep `import requests`: `requests.Session()` is still used).
- Remove `UnexpectedRedirect` from the `sla_agent.errors` import (it is now raised inside `guarded_http`).
- Add `from sla_agent.guarded_http import asks_for_verification, guarded_request`.
- Delete the constants `TIMEOUT_SECONDS`, `MAX_REDIRECTS`, `VERIFICATION_HINTS`, `MICROSOFT_HOSTS` and the functions `_asks_for_verification` and the method `_safe_url`.
- Replace every call `_asks_for_verification(` with `asks_for_verification(`.
- Replace the whole `_request` method with:

```python
    def _request(self, method, url, data=None):
        """One request, following redirects by hand so every hop is checked."""
        return guarded_request(self.session, method, url, HOST, data=data, site="EduSoft")
```

- [ ] **Step 7: Create the Blackboard client**

Create `agent/sla_agent/blackboard_client.py`:

```python
"""Talks to IU's Blackboard: log in with the normal form, read the REST API with that
session, log out. Reads only; the login form is the only request that sends data."""

import logging
import ssl

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from sla_agent.edusoft_client import USER_AGENT
from sla_agent.errors import BadCredentials, ExtraVerification, NetworkError, SessionExpired, SourceChanged
from sla_agent.guarded_http import asks_for_verification, guarded_request

log = logging.getLogger(__name__)

HOST = "blackboard.hcmiu.edu.vn"
BASE_URL = f"https://{HOST}"
LOGIN_URL = f"{BASE_URL}/webapps/login/"
LOGOUT_URL = f"{BASE_URL}/webapps/login/?action=logout"
API = "/learn/api/public"
MAX_PAGES = 10
# IU's Blackboard only offers TLS 1.2 AES-CBC-SHA suites, which Python refuses by default.
# Allow the DHE ones (forward secrecy) for this host only; RSA key exchange stays refused.
CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA:@SECLEVEL=2"


def blackboard_tls_context():
    context = ssl.create_default_context()  # certificate and hostname checks stay on
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers(CIPHERS)
    return context


class BlackboardTLS(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = blackboard_tls_context()
        return super().init_poolmanager(*args, **kwargs)


def _login_form_shown(soup):
    return soup.find("input", attrs={"name": "user_id"}) is not None


class BlackboardClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.session.mount(f"{BASE_URL}/", BlackboardTLS())
        self.user_id = None
        self.capture = None  # a dict keeps every API answer by path (for `sla-agent fetch`)

    def _request(self, method, url, data=None):
        return guarded_request(self.session, method, url, HOST, data=data, site="Blackboard")

    def login(self, username, password):
        page = BeautifulSoup(self._request("GET", LOGIN_URL).text, "html.parser")
        if asks_for_verification(page):
            raise ExtraVerification("Blackboard's login page asks for extra verification.")
        form = page.find("form", attrs={"action": "/webapps/login/"})
        if form is None or not _login_form_shown(form):
            raise NetworkError("Blackboard's login page didn't load correctly.")
        fields = {tag["name"]: tag.get("value", "") for tag in form.find_all("input")
                  if tag.get("name") and tag.get("type") != "submit"}
        fields.update({"user_id": username, "password": password, "login": "Login"})

        # Submitted once. No retry: a retry could count as a second failed login.
        result = BeautifulSoup(self._request("POST", LOGIN_URL, data=fields).text, "html.parser")
        if asks_for_verification(result):
            raise ExtraVerification("Blackboard asked for extra verification after login.")
        if _login_form_shown(result):
            raise BadCredentials("Blackboard rejected the username or password.")
        me = self.api("/v1/users/me")
        if not isinstance(me, dict) or not me.get("id"):
            raise SourceChanged("Blackboard's API didn't say who is logged in.")
        self.user_id = me["id"]
        log.info("Logged in to Blackboard")

    def api(self, path):
        """One API answer as a dict, or None when Blackboard refuses this item (HTTP 403/404)."""
        response = self._request("GET", f"{BASE_URL}{API}{path}")
        if response.status_code == 401:
            raise SessionExpired("Blackboard ended the session.")
        if response.status_code in (403, 404):
            return None
        if response.status_code != 200:
            raise SourceChanged(f"Blackboard's API answered HTTP {response.status_code}.")
        try:
            body = response.json()
        except ValueError:
            raise SourceChanged("Blackboard's API didn't answer with JSON.") from None
        if self.capture is not None:
            self.capture[path] = body
        return body

    def api_all(self, path):
        """Every result of a list endpoint, following Blackboard's paging; [] when refused."""
        results, next_path = [], path
        for _ in range(MAX_PAGES):
            body = self.api(next_path)
            if body is None:
                return results
            if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                raise SourceChanged("A Blackboard list answer has an unexpected format.")
            results += body["results"]
            next_page = (body.get("paging") or {}).get("nextPage")
            if not next_page:
                return results
            next_path = next_page.removeprefix(API)
        return results

    def logout(self):
        try:
            self._request("GET", LOGOUT_URL)
        except Exception:  # logging out is best effort; the session expires anyway
            log.info("Blackboard logout didn't complete")
```

- [ ] **Step 8: Run all agent tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass (the existing EduSoft client tests prove the refactor kept its behaviour).

- [ ] **Step 9: Commit**

```bash
git add agent/sla_agent/guarded_http.py agent/sla_agent/blackboard_client.py agent/sla_agent/errors.py agent/sla_agent/edusoft_client.py agent/tests/blackboard_fakes.py agent/tests/test_blackboard_client.py
git commit -m "feat(agent): Blackboard client with a Blackboard-only TLS setting" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Blackboard login details, `setup --blackboard`, status and forget

**Files:**
- Modify: `agent/sla_agent/credentials.py`, `agent/sla_agent/state.py`, `agent/sla_agent/cli.py`, `agent/tests/fakes.py`, `agent/tests/test_cli.py`, `agent/tests/test_credentials_and_state.py`, `docs/superpowers/specs/2026-09-26-blackboard-design.md`

**Interfaces:**
- Consumes: `BlackboardClient.login/logout` (Task 1).
- Produces: `credentials.save_blackboard(username, password)`, `credentials.load_blackboard(username) -> str | None`, `credentials.forget(student_id, server_url, blackboard_username=None)`; `State.blackboard_username: str | None`, `State.blackboard_paused: str | None`, `State.registered_courses: list[list[str]] | None` (each `[code, group]`); `cli.make_blackboard()`; `cli.BLACKBOARD_PAUSE_MESSAGES` is defined in Task 6, so this task prints its own messages.

- [ ] **Step 1: Write the failing tests**

In `agent/tests/test_credentials_and_state.py` add:

```python
def test_blackboard_password_goes_to_its_own_keyring_entry(isolated_agent):
    credentials.save_blackboard("bbuser", "bb-s3cret")

    assert isolated_agent.entries == {("SchoolLifeAssistant-Blackboard", "bbuser"): "bb-s3cret"}
    assert credentials.load_blackboard("bbuser") == "bb-s3cret"


def test_forget_also_removes_the_blackboard_password(isolated_agent):
    credentials.save_blackboard("bbuser", "bb-s3cret")

    credentials.forget("ITITIU20001", "https://sla.example.com", "bbuser")

    assert isolated_agent.entries == {}


def test_blackboard_state_round_trips_and_old_state_files_still_load():
    state = State(server_url="https://sla.example.com", student_id="S", blackboard_username="bbuser",
                  blackboard_paused="bad_credentials", registered_courses=[["IT093IU", "02"]])
    save_state(state)
    assert load_state() == state

    (agent_home() / "state.json").write_text('{"server_url": "https://x.example", "paused": null}', encoding="utf-8")
    assert load_state() == State(server_url="https://x.example")
```

In `agent/tests/fakes.py` add:

```python
class FakeBlackboard:
    def __init__(self, login_error=None):
        self.login_error = login_error
        self.logins = []
        self.logouts = 0
        self.user_id = "_1_1"

    def login(self, username, password):
        self.logins.append((username, password))
        if self.login_error:
            raise self.login_error

    def logout(self):
        self.logouts += 1
```

In `agent/tests/test_cli.py`:
- Change the fakes import to `from agent.tests.fakes import FakeBlackboard, FakeEduSoft, FakeServer`.
- In `World.__init__` add `self.blackboard = FakeBlackboard()` and `monkeypatch.setattr(cli, "make_blackboard", lambda: self.blackboard)`.
- Replace `World.answer_setup` with:

```python
    def answer_setup(self, server=SERVER, key=KEY, student=STUDENT, password=PASSWORD,
                     bb_user="", bb_password=None):
        self.answers = [server, student, bb_user]
        self.secret_answers = [key, password] + ([bb_password] if bb_user else [])
```

- Add these tests:

```python
BB_USER, BB_PASSWORD = "bbuser", "bb-s3cret"


def test_setup_can_add_blackboard_after_edusoft(world, isolated_agent):
    world.answer_setup(bb_user=BB_USER, bb_password=BB_PASSWORD)

    assert cli.main(["setup", "--no-schedule"]) == 0

    assert world.blackboard.logins == [(BB_USER, BB_PASSWORD)]
    assert world.blackboard.logouts == 1
    assert credentials.load_blackboard(BB_USER) == BB_PASSWORD
    assert load_state().blackboard_username == BB_USER


def test_setup_blackboard_alone_needs_edusoft_setup_first(world, capsys):
    assert cli.main(["setup", "--blackboard"]) == 1
    assert "sla-agent setup" in capsys.readouterr().out


def test_setup_blackboard_alone_saves_only_blackboard_and_clears_its_pause(world, isolated_agent):
    configure()
    state = load_state()
    state.blackboard_paused = "bad_credentials"
    save_state(state)
    world.answers = [BB_USER]
    world.secret_answers = [BB_PASSWORD]

    assert cli.main(["setup", "--blackboard"]) == 0

    assert world.edusoft.logins == []
    assert credentials.load_blackboard(BB_USER) == BB_PASSWORD
    assert (load_state().blackboard_username, load_state().blackboard_paused) == (BB_USER, None)


def test_a_wrong_blackboard_password_saves_nothing(world, isolated_agent, capsys):
    configure()
    world.blackboard.login_error = BadCredentials("rejected")
    world.answers = [BB_USER]
    world.secret_answers = ["wrong"]

    assert cli.main(["setup", "--blackboard"]) == 1

    assert len(world.blackboard.logins) == 1
    assert ("SchoolLifeAssistant-Blackboard", BB_USER) not in isolated_agent.entries
    assert load_state().blackboard_username is None
    assert "Nothing was saved" in capsys.readouterr().out


def test_status_shows_blackboard(world, capsys):
    configure()
    state = load_state()
    state.blackboard_username, state.blackboard_paused = BB_USER, "bad_credentials"
    save_state(state)

    cli.main(["status"])

    out = capsys.readouterr().out
    assert "Blackboard" in out
    assert "sla-agent setup --blackboard" in out


def test_forget_removes_the_blackboard_password_too(world, isolated_agent):
    configure()
    credentials.save_blackboard(BB_USER, BB_PASSWORD)
    state = load_state()
    state.blackboard_username = BB_USER
    save_state(state)

    cli.main(["forget"])

    assert isolated_agent.entries == {}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_cli.py agent/tests/test_credentials_and_state.py -q`
Expected: failures (`AttributeError: ... has no attribute 'make_blackboard'`, `save_blackboard`, unknown `State` fields).

- [ ] **Step 3: Implement credentials and state**

In `agent/sla_agent/credentials.py` add `BLACKBOARD_SERVICE = "SchoolLifeAssistant-Blackboard"  # username = Blackboard username` below the other services, then add:

```python
def save_blackboard(username, password):
    protect(password)
    keyring.set_password(BLACKBOARD_SERVICE, username, password)


def load_blackboard(username):
    password = keyring.get_password(BLACKBOARD_SERVICE, username)
    protect(password)
    return password
```

and replace `forget` with:

```python
def forget(student_id, server_url, blackboard_username=None):
    for service, username in (
        (EDUSOFT_SERVICE, student_id),
        (DEVICE_KEY_SERVICE, server_url),
        (BLACKBOARD_SERVICE, blackboard_username),
    ):
        if username:
            try:
                keyring.delete_password(service, username)
            except PasswordDeleteError:
                pass
```

In `agent/sla_agent/state.py` add to `State` after `last_result`:

```python
    blackboard_username: str | None = None
    blackboard_paused: str | None = None  # error code that paused Blackboard sync
    registered_courses: list | None = None  # [[course code, group], ...] from EduSoft's registration page
```

- [ ] **Step 4: Implement the CLI changes**

In `agent/sla_agent/cli.py`:
- Add `from sla_agent.blackboard_client import BlackboardClient`.
- Add below `make_server`:

```python
def make_blackboard():
    return BlackboardClient()
```

- Add below `cmd_setup`'s helpers (before `cmd_setup`):

```python
def _setup_blackboard(state, username=None):
    """Ask for (or use) the Blackboard login, check it once, save it. Returns an exit code."""
    username = username or ask(f"Blackboard username [{state.blackboard_username or ''}]: ").strip() \
        or state.blackboard_username or ""
    password = ask_secret("Blackboard password (not shown): ")
    protect(password)
    if not (username and password):
        say("Blackboard username and password are both needed. Nothing was saved.")
        return 1
    say("Checking your Blackboard login (one attempt)...")
    blackboard = make_blackboard()
    try:
        blackboard.login(username, password)
    except BadCredentials:
        say("Blackboard rejected the username or password. Nothing was saved.")
        return 1
    except ExtraVerification:
        say("Blackboard asked for extra verification, so automatic Blackboard sync can't be used. Nothing was saved.")
        return 1
    except AgentError as error:
        say(f"Couldn't check your Blackboard login: {error} Nothing was saved; try again later.")
        return 1
    finally:
        blackboard.logout()
    if state.blackboard_username and state.blackboard_username != username:
        credentials.forget(None, None, state.blackboard_username)
    credentials.save_blackboard(username, password)
    state.blackboard_username, state.blackboard_paused = username, None
    save_state(state)
    say("Blackboard saved. Its password is in Windows Credential Manager too.")
    return 0
```

- At the start of `cmd_setup` (right after `state = load_state()`), add:

```python
    if args.blackboard:
        if not state.server_url or not state.student_id:
            say(NOT_SET_UP)
            return 1
        return _setup_blackboard(state)
```

- In `cmd_setup`, just before `if not args.no_schedule:`, add:

```python
    blackboard_user = ask(f"Blackboard username (press Enter to skip) [{state.blackboard_username or ''}]: ").strip()
    if blackboard_user and _setup_blackboard(state, blackboard_user) != 0:
        say("EduSoft is saved; set up Blackboard later with `sla-agent setup --blackboard`.")
```

- In `main`, after `setup.add_argument("--no-schedule", ...)`, add:

```python
    setup.add_argument("--blackboard", action="store_true", help="set or change only the Blackboard login")
```

- Replace `cmd_status` with:

```python
def cmd_status(args):
    state = load_state()
    if not state.server_url:
        say(NOT_SET_UP)
        return 1
    say(f"Web app:     {state.server_url}")
    say(f"Student ID:  {state.student_id}")
    if state.paused:
        say(f"EduSoft:     PAUSED. {PAUSE_MESSAGES.get(state.paused, '')}")
    else:
        say("EduSoft:     on")
    if not state.blackboard_username:
        say("Blackboard:  not set up (run `sla-agent setup --blackboard`)")
    elif state.blackboard_paused:
        say(f"Blackboard:  PAUSED ({state.blackboard_paused}). Run `sla-agent setup --blackboard`.")
    else:
        say("Blackboard:  on")
    if state.last_result:
        say(f"Last sync:   {state.last_result['status']} at {state.last_result['at']}: {state.last_result['message']}")
    else:
        say("Last sync:   never")
    return 0
```

- In `cmd_forget`, replace `credentials.forget(state.student_id, state.server_url)` with `credentials.forget(state.student_id, state.server_url, state.blackboard_username)`.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass.

- [ ] **Step 6: Record the pause fields in the spec**

In `docs/superpowers/specs/2026-09-26-blackboard-design.md`, section 5, replace the bullet that starts "Each system has its **own pause**" with:

```markdown
- Each system has its **own pause** in the agent's state: `paused` (EduSoft, as before) and `blackboard_paused`. Older state files load unchanged.
```

- [ ] **Step 7: Commit**

```bash
git add agent/sla_agent/credentials.py agent/sla_agent/state.py agent/sla_agent/cli.py agent/tests/fakes.py agent/tests/test_cli.py agent/tests/test_credentials_and_state.py docs/superpowers/specs/2026-09-26-blackboard-design.md
git commit -m "feat(agent): Blackboard login in setup, status and forget" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The `blackboard` section in the shared data format

**Files:**
- Modify: `contract/sla_contract/schema.py`, `agent/sla_agent/sync.py`, `agent/sla_agent/cli.py`, `tests/test_contract.py`, `docs/superpowers/specs/2026-09-26-blackboard-design.md`

**Interfaces:**
- Produces: `schema.EDUSOFT_SECTIONS = ("timetable", "exams", "tuition")`, `schema.SECTION_NAMES = EDUSOFT_SECTIONS + ("blackboard",)`, `ErrorCode` includes `"source_changed"`, models `BbAnnouncement(bb_id, title, text, posted_at, url)`, `BbAssignment(bb_id, name, due_at, points_possible, score, grade_text, status, feedback, url)` with `status: Literal["not_graded", "needs_grading", "graded", "exempt"]`, `BbMaterial(bb_id, title, kind, path, created_at, url)` with `kind: Literal["file", "folder", "link", "document", "other"]`, `BbCourse(bb_id, course_code, name, url, announcements, assignments, materials)`, `Blackboard(courses)`; `FinishRun.blackboard`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contract.py`:

```python
BB = "https://blackboard.hcmiu.edu.vn"


def blackboard_payload():
    return {
        "courses": [{
            "bb_id": "_101_1", "course_code": "IT093IU", "name": "Web Application Development",
            "url": f"{BB}/webapps/blackboard/execute/launcher?type=Course&id=_101_1&url=",
            "announcements": [{"bb_id": "_501_1", "title": "No class on Thursday", "text": "Class is cancelled.",
                               "posted_at": "2026-09-28T02:00:00+00:00", "url": f"{BB}/x"}],
            "assignments": [{"bb_id": "_701_1", "name": "Lab 3", "due_at": "2026-10-02T16:59:00+00:00",
                             "points_possible": 10, "score": 8.5, "grade_text": "8.5", "status": "graded",
                             "feedback": "Good work", "url": f"{BB}/x"}],
            "materials": [{"bb_id": "_902_1", "title": "Week 5 slides.pdf", "kind": "file", "path": "Week 5",
                           "created_at": "2026-09-28T01:00:00+00:00", "url": f"{BB}/x"}],
        }],
    }


def test_a_blackboard_section_is_accepted_next_to_edusoft():
    payload = full_payload()
    payload["blackboard"] = {"status": "ok", "data": blackboard_payload()}

    finish = FinishRun.model_validate(payload)

    assert list(finish.sections()) == ["timetable", "exams", "tuition", "blackboard"]
    assert finish.blackboard.data.courses[0].assignments[0].score == 8.5


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["courses"][0]["announcements"][0].update(url="https://evil.example/x"),
        lambda p: p["courses"][0]["announcements"][0].update(posted_at="2026-09-28T02:00:00"),
        lambda p: p["courses"][0]["assignments"][0].update(status="done"),
        lambda p: p["courses"][0]["materials"][0].update(kind="video"),
        lambda p: p["courses"][0].update(student_email="s@example.com"),
        lambda p: p["courses"][0]["announcements"][0].update(text="x" * 5001),
    ],
    ids=["link-to-another-site", "naive-time", "unknown-status", "unknown-kind", "extra-field", "text-too-long"],
)
def test_bad_blackboard_data_is_rejected(change):
    data = blackboard_payload()
    change(data)

    with pytest.raises(ValidationError):
        FinishRun.model_validate({"blackboard": {"status": "ok", "data": data}})


def test_a_failed_blackboard_part_can_say_its_format_changed():
    finish = FinishRun.model_validate({
        "timetable": full_payload()["timetable"],
        "blackboard": {"status": "failed", "error_code": "source_changed", "error_message": "Unexpected format"},
    })

    assert finish.overall_status() == "partial"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_contract.py -q`
Expected: failures (extra field `blackboard` rejected; `source_changed` not an allowed code).

- [ ] **Step 3: Implement the models**

In `contract/sla_contract/schema.py`:
- Add `"source_changed",  # Blackboard's answers are in an unexpected format` to `ErrorCode` after `"edusoft_changed"`.
- After the `Tuition` class, add:

```python
BbId = Annotated[str, Field(min_length=1, max_length=64)]
BbUrl = Annotated[str, Field(max_length=500, pattern=r"^https://blackboard\.hcmiu\.edu\.vn/")]


class BbAnnouncement(_Strict):
    bb_id: BbId
    title: Name
    text: Annotated[str, Field(max_length=5000)] = ""
    posted_at: AwareDatetime | None = None
    url: BbUrl


class BbAssignment(_Strict):
    bb_id: BbId
    name: Name
    due_at: AwareDatetime | None = None
    points_possible: Annotated[float, Field(ge=0)] | None = None
    score: float | None = None
    grade_text: Annotated[str, Field(max_length=50)] | None = None
    status: Literal["not_graded", "needs_grading", "graded", "exempt"]
    feedback: Annotated[str, Field(max_length=1000)] | None = None
    url: BbUrl


class BbMaterial(_Strict):
    bb_id: BbId
    title: Name
    kind: Literal["file", "folder", "link", "document", "other"]
    path: Annotated[str, Field(max_length=500)] = ""
    created_at: AwareDatetime | None = None
    url: BbUrl


class BbCourse(_Strict):
    bb_id: BbId
    course_code: Code | None = None
    name: Name
    url: BbUrl
    announcements: Annotated[list[BbAnnouncement], Field(max_length=300)] = []
    assignments: Annotated[list[BbAssignment], Field(max_length=300)] = []
    materials: Annotated[list[BbMaterial], Field(max_length=1000)] = []


class Blackboard(_Strict):
    courses: Annotated[list[BbCourse], Field(max_length=40)]
```

- Add `BlackboardResult = Annotated[SectionOk[Blackboard] | SectionFailed, Field(discriminator="status")]` next to the other `*Result` aliases.
- Replace `SECTION_NAMES = ("timetable", "exams", "tuition")` with:

```python
EDUSOFT_SECTIONS = ("timetable", "exams", "tuition")
SECTION_NAMES = EDUSOFT_SECTIONS + ("blackboard",)
```

- In `FinishRun`, add `blackboard: BlackboardResult | None = None` after `tuition`.

- [ ] **Step 4: Keep the agent reading only EduSoft sections from EduSoft**

- In `agent/sla_agent/sync.py`: change the import to `from sla_contract.schema import EDUSOFT_SECTIONS, FinishRun` and `for name in SECTION_NAMES}` to `for name in EDUSOFT_SECTIONS}`.
- In `agent/sla_agent/cli.py`: change the import to `from sla_contract.schema import EDUSOFT_SECTIONS, FinishRun` and `for section in SECTION_NAMES:` (in `cmd_fetch`) to `for section in EDUSOFT_SECTIONS:`. Then run `grep -n SECTION_NAMES agent/sla_agent/*.py`; expected: no output.

- [ ] **Step 5: Drop `graded_at` from the spec**

In `docs/superpowers/specs/2026-09-26-blackboard-design.md`, section 6, remove `graded_at (nullable), ` from the assignments line of the data-format tree and `, graded_at` from the `school_bb_assignments` table row (Blackboard's grade answer has no graded date).

- [ ] **Step 6: Run everything**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add contract/sla_contract/schema.py agent/sla_agent/sync.py agent/sla_agent/cli.py tests/test_contract.py docs/superpowers/specs/2026-09-26-blackboard-design.md
git commit -m "feat(contract): blackboard section in the shared data format" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: This semester's registered courses from EduSoft

**Files:**
- Create: `agent/sla_agent/parsers/registration.py`, `agent/tools/__init__.py` (empty), `agent/tools/anonymize_registration.py`, `agent/tests/fixtures/registration.html` (generated), `agent/tests/test_registration.py`
- Modify: `agent/sla_agent/edusoft_client.py`, `agent/sla_agent/cli.py` (fetch), `agent/tests/fakes.py`, `agent/tests/test_cli.py`

**Interfaces:**
- Produces: `parsers.registration.RegisteredCourse(code: str, group: str)` (NamedTuple); `parse_registered_courses(pages: {"registration": html}) -> list[RegisteredCourse]`; `EduSoftClient.read("registration") -> {"registration": html}` (GET only); `fetch --save-html` also writes `registration.html`.

- [ ] **Step 1: Create the anonymized test copy of the real registration page**

The real page was saved on 2026-09-26 at `%USERPROFILE%\Documents\edusoft-pages\registration.html`. Create `agent/tools/anonymize_registration.py`:

```python
"""Make an anonymized test copy of EduSoft's registration page.

Usage: python -m agent.tools.anonymize_registration SAVED_PAGE OUTPUT
Keeps the layout, course codes, names, groups and statuses. Removes the student
box, the greeting, view state, the advisor's message and every fee amount."""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def anonymize(html):
    soup = BeautifulSoup(html, "html.parser")
    personal = set()
    for tag in soup.find_all(id=re.compile(r"ucThongTinSV_lb")):
        text = tag.get_text(" ", strip=True)
        if text and len(text) > 2:
            personal.add(text)
        tag.string = "-"
    greeting = soup.find(id="Header1_Logout1_lblNguoiDung")
    if greeting:
        match = re.search(r"Chào bạn (.+?) \((\w+)\)", greeting.get_text(" ", strip=True))
        if match:
            personal.update(match.groups())
        greeting.string = "Chào bạn STUDENT (STUDENT)"
    for tag in soup.find_all("input", attrs={"name": "__VIEWSTATE"}):
        tag["value"] = "VIEWSTATE-REMOVED"
    for tag in soup.find_all(id=re.compile(r"(lblLoiNhan|txtLoiNhan|lblNoiDungLoiNhan)")):
        tag.string = ""
    for td in soup.find_all("td"):
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", td.get_text(strip=True)):
            td.string = "1,000,000"
    out = str(soup)
    for value in sorted(personal, key=len, reverse=True):
        out = out.replace(value, "STUDENT")
    return out, personal


if __name__ == "__main__":
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    result, personal = anonymize(source.read_text(encoding="utf-8"))
    target.write_text(result, encoding="utf-8")
    leaks = [v for v in personal if v in result]
    print(f"personal values removed: {len(personal)}, still present: {len(leaks)}")
```

Run:
```bash
.venv/Scripts/python.exe -m agent.tools.anonymize_registration "$USERPROFILE/Documents/edusoft-pages/registration.html" agent/tests/fixtures/registration.html
grep -oE '\b[A-Z]{6}[0-9]{5}\b' agent/tests/fixtures/registration.html | wc -l
```
Expected: `still present: 0` and `0` student-ID-shaped strings.

- [ ] **Step 2: Write the failing tests**

Create `agent/tests/test_registration.py`:

```python
from pathlib import Path

import pytest
import responses

from sla_agent.edusoft_client import EduSoftClient
from sla_agent.errors import ParseError
from sla_agent.parsers.registration import RegisteredCourse, parse_registered_courses

FIXTURE = (Path(__file__).parent / "fixtures" / "registration.html").read_text(encoding="utf-8")
REGISTRATION_URL = "https://edusoftweb.hcmiu.edu.vn/default.aspx?page=dkmonhoc"

# Hand-checked against the timetable copy: same 8 courses and groups.
EXPECTED = [
    RegisteredCourse("IT090IU", "01"), RegisteredCourse("IT007WE", "01"), RegisteredCourse("PH012IU", "01"),
    RegisteredCourse("IT093IU", "02"), RegisteredCourse("EN011IU", "03"), RegisteredCourse("IT120IU", "01"),
    RegisteredCourse("MA026IU", "02"), RegisteredCourse("IT013IU", "02"),
]


def test_reads_the_registered_courses_with_their_groups():
    assert parse_registered_courses({"registration": FIXTURE}) == EXPECTED


def test_rows_not_saved_to_the_database_are_left_out():
    page = FIXTURE.replace("Đã lưu vào CSDL", "Chưa lưu", 1)

    assert len(parse_registered_courses({"registration": page})) == 7


@pytest.mark.parametrize("old, new", [("lblDaChon", "lblRenamed"), (">Regis ID<", ">ID<")],
                         ids=["list-title-missing", "header-changed"])
def test_a_page_that_does_not_look_right_raises_parse_error(old, new):
    assert old in FIXTURE

    with pytest.raises(ParseError):
        parse_registered_courses({"registration": FIXTURE.replace(old, new)})


@responses.activate
def test_the_registration_page_is_only_ever_read_with_get():
    responses.get(REGISTRATION_URL, body=FIXTURE)

    pages = EduSoftClient().read("registration")

    assert pages == {"registration": FIXTURE}
    assert [c.request.method for c in responses.calls] == ["GET"]
```

- [ ] **Step 3: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_registration.py -q`
Expected: collection error `No module named 'sla_agent.parsers.registration'`.

Note: if `test_reads_the_registered_courses_with_their_groups` later fails only on the order of courses, compare with the order in the fixture's table and fix `EXPECTED` to that order (the order is EduSoft's, not a behaviour).

- [ ] **Step 4: Implement the reader and the client page**

Create `agent/sla_agent/parsers/registration.py`:

```python
"""Registered courses: EduSoft's "DANH SÁCH MÔN HỌC ĐÃ CHỌN" on the registration page.

Only rows saved to EduSoft's database ("Đã lưu vào CSDL") count as registered."""

import re
from typing import NamedTuple

from sla_agent.errors import ParseError
from sla_agent.parsers.common import soup, text

LIST_TITLE_ID = "ContentPlaceHolder1_ctl00_lblDaChon"
SAVED = "Đã lưu vào CSDL"
COURSE_CODE = re.compile(r"^[A-Z]{2}\d{3}[A-Z]{2}$")


class RegisteredCourse(NamedTuple):
    code: str
    group: str


def parse_registered_courses(pages):
    page = soup(pages["registration"])
    title = page.find(id=LIST_TITLE_ID)
    if title is None:
        raise ParseError("The registered-course list wasn't found on EduSoft's registration page.")

    header_cells = None
    for table in title.find_all_next("table"):
        cells = [text(cell) for cell in table.find_all(["td", "th"])]
        if "Regis ID" in cells and "Mã MH" in cells:
            header_cells = cells[cells.index("STT"):] if "STT" in cells else cells
            break
    if header_cells is None or not {"Mã MH", "NMH", "Trạng Thái môn học"} <= set(header_cells):
        raise ParseError("The registered-course list's columns have changed.")
    code_at, group_at, status_at = (header_cells.index(h) for h in ("Mã MH", "NMH", "Trạng Thái môn học"))

    courses = []
    for table in title.find_all_next("table", class_="body-table"):
        for row in table.find_all("tr"):
            values = [text(cell) for cell in row.find_all("td", recursive=False)]
            if len(values) <= status_at or not COURSE_CODE.match(values[code_at]):
                continue
            if SAVED in values[status_at]:
                courses.append(RegisteredCourse(values[code_at], values[group_at]))
        if courses:
            break
    return courses
```

In `agent/sla_agent/edusoft_client.py`: add `"registration": "dkmonhoc",  # read only, never submitted` to `PAGES`, and in `read()` before `raise KeyError(section)` add:

```python
        if section == "registration":
            return {"registration": self.get_page("registration")}  # GET only: never submit this form
```

In `agent/tests/fakes.py`, add `"registration": ("registration",)` to `FakeEduSoft.SECTION_PARTS`.

In `agent/sla_agent/cli.py` `cmd_fetch`, after the loop over `EDUSOFT_SECTIONS`, add:

```python
        files["registration.html"] = edusoft.read("registration")["registration"]
```

In `agent/tests/test_cli.py` `test_fetch_saves_the_pages_locally_with_a_privacy_warning`, add `"registration.html",` to the expected sorted list (between `"home.html"` and `"timetable-semester.html"`).

- [ ] **Step 5: Run the agent tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/sla_agent/parsers/registration.py agent/sla_agent/edusoft_client.py agent/sla_agent/cli.py agent/tools agent/tests/fixtures/registration.html agent/tests/test_registration.py agent/tests/fakes.py agent/tests/test_cli.py
git commit -m "feat(agent): read this semester's registered courses from EduSoft (GET only)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Blackboard readers

**Files:**
- Create: `agent/sla_agent/parsers/blackboard.py`, `agent/sla_agent/blackboard_reader.py`, `agent/tests/test_blackboard_readers.py`

**Interfaces:**
- Consumes: `BlackboardClient.api/api_all/user_id` (Task 1), `RegisteredCourse` (Task 4), contract models (Task 3).
- Produces: `parsers.blackboard.html_to_text(html, limit) -> str`, `select_current_courses(courses: list[dict], registered: list[RegisteredCourse]) -> list[tuple[dict, str]]`, `announcements_from(items, course_id) -> list[BbAnnouncement]`, `assignments_from(columns, grades, course_id) -> list[BbAssignment]`, `walk_contents(top_items, fetch_children, max_depth=2, max_folder_requests=15) -> list[tuple[dict, str]]`, `materials_from(tree, course_id) -> list[BbMaterial]`, `course_url(course_id) -> str`; `blackboard_reader.read_blackboard(client, registered) -> Blackboard`.

- [ ] **Step 1: Write the failing tests**

Create `agent/tests/test_blackboard_readers.py` (JSON shapes follow Blackboard Learn's public REST API):

```python
from datetime import datetime, timezone

import pytest

from sla_agent.blackboard_reader import read_blackboard
from sla_agent.errors import SourceChanged
from sla_agent.parsers.blackboard import (
    announcements_from,
    assignments_from,
    html_to_text,
    materials_from,
    select_current_courses,
    walk_contents,
)
from sla_agent.parsers.registration import RegisteredCourse

BB = "https://blackboard.hcmiu.edu.vn"


def course(bb_id, course_id, name, created="2026-08-20T03:00:00.000Z"):
    return {"id": bb_id, "courseId": course_id, "name": name, "created": created}


# ---- Which courses -------------------------------------------------------------

def test_courses_are_chosen_by_their_registered_code():
    courses = [course("_1_1", "IT093IU-2026-1-02", "Web Application Development"),
               course("_2_1", "IT013IU-2025-2-01", "Algorithms"),
               course("_3_1", "PH012IU-2026-1-01", "Physics 4")]

    chosen = select_current_courses(courses, [RegisteredCourse("IT093IU", "02"), RegisteredCourse("PH012IU", "01")])

    assert [(c["id"], code) for c, code in chosen] == [("_1_1", "IT093IU"), ("_3_1", "PH012IU")]


def test_a_code_inside_a_longer_code_does_not_match():
    courses = [course("_1_1", "XIT093IU2", "Something else")]

    assert select_current_courses(courses, [RegisteredCourse("IT093IU", "02")]) == []


def test_the_group_then_the_newest_course_breaks_a_tie():
    courses = [course("_1_1", "IT093IU-2025-1-01", "Web App (old)", created="2025-08-01T00:00:00.000Z"),
               course("_2_1", "IT093IU-2026-1-02", "Web App", created="2026-08-01T00:00:00.000Z"),
               course("_3_1", "IT093IU-2026-1-03", "Web App (other group)", created="2026-08-02T00:00:00.000Z")]

    [(chosen, _)] = select_current_courses(courses, [RegisteredCourse("IT093IU", "02")])

    assert chosen["id"] == "_2_1"


def test_the_digits_of_the_course_code_are_not_mistaken_for_the_group():
    courses = [course("_1_1", "IT093IU-2026-1-01", "Web App", created="2026-08-02T00:00:00.000Z"),
               course("_2_1", "IT093IU-2026-1-03", "Web App", created="2026-08-01T00:00:00.000Z")]

    [(chosen, _)] = select_current_courses(courses, [RegisteredCourse("IT093IU", "03")])

    assert chosen["id"] == "_2_1"  # "03" is in IT093IU too, but only _2_1 is group 03


# ---- Text --------------------------------------------------------------------------

def test_html_becomes_safe_plain_text_within_its_limit():
    html = ("<p>Class on <b>Thursday</b>&nbsp;is cancelled.</p><script>alert(1)</script>"
            "<style>p{}</style><iframe src='x'></iframe>" + "<p>more</p>" * 3000)

    result = html_to_text(html, 5000)

    assert result.startswith("Class on Thursday is cancelled.")
    assert "<" not in result and "alert" not in result and "p{}" not in result
    assert len(result) <= 5000
    assert result.endswith("…")


# ---- Announcements ---------------------------------------------------------------

def test_announcements_skip_drafts_and_use_the_posting_date():
    items = [
        {"id": "_501_1", "title": "No class on Thursday", "body": "<p>Cancelled.</p>", "draft": False,
         "availability": {"duration": {"type": "Restricted", "start": "2026-09-28T02:00:00.000Z"}},
         "created": "2026-09-27T10:00:00.000Z"},
        {"id": "_502_1", "title": "Draft", "body": "x", "draft": True, "created": "2026-09-27T10:00:00.000Z"},
        {"id": "_503_1", "title": "", "body": "Untitled", "created": "2026-09-26T10:00:00.000Z"},
    ]

    result = announcements_from(items, "_101_1")

    assert [(a.bb_id, a.title, a.text) for a in result] == [
        ("_501_1", "No class on Thursday", "Cancelled."), ("_503_1", "(no title)", "Untitled")]
    assert result[0].posted_at == datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    assert result[0].url.startswith(f"{BB}/")


# ---- Assignments and grades -------------------------------------------------------

COLUMNS = [
    {"id": "_701_1", "name": "Lab 3", "score": {"possible": 10.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Attempts", "due": "2026-10-02T16:59:00.000Z"}},
    {"id": "_702_1", "name": "Participation", "score": {"possible": 5.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Manual"}},
    {"id": "_703_1", "name": "Total", "score": {"possible": 100.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Calculated"}},
    {"id": "_704_1", "name": "Hidden", "availability": {"available": "No"}, "grading": {"type": "Manual"}},
    {"id": "_705_1", "name": "Quiz 1", "score": {"possible": 20.0}, "availability": {"available": "Yes"},
     "grading": {"type": "Attempts", "due": "2026-10-09T16:59:00.000Z"}},
]
GRADES = [
    {"columnId": "_701_1", "status": "Graded", "score": 8.5,
     "displayGrade": {"scaleType": "Score", "score": 8.5, "possible": 10.0, "text": "8.5"},
     "feedback": "<p>Good <b>work</b></p>", "exempt": False},
    {"columnId": "_705_1", "status": "NeedsGrading", "exempt": False},
]


def test_assignments_merge_due_dates_and_my_grades_and_leave_out_totals_and_hidden_items():
    result = {a.bb_id: a for a in assignments_from(COLUMNS, GRADES, "_101_1")}

    assert sorted(result) == ["_701_1", "_702_1", "_705_1"]
    lab = result["_701_1"]
    assert (lab.name, lab.due_at, lab.points_possible, lab.score, lab.status, lab.feedback) == (
        "Lab 3", datetime(2026, 10, 2, 16, 59, tzinfo=timezone.utc), 10.0, 8.5, "graded", "Good work")
    assert (result["_702_1"].due_at, result["_702_1"].status) == (None, "not_graded")
    assert result["_705_1"].status == "needs_grading"


# ---- Materials ---------------------------------------------------------------------

def item(bb_id, title, handler, has_children=False, available="Yes"):
    return {"id": bb_id, "title": title, "created": "2026-09-28T01:00:00.000Z", "hasChildren": has_children,
            "availability": {"available": available}, "contentHandler": {"id": handler}}


def test_materials_walk_folders_two_levels_deep_with_their_path():
    top = [item("_1", "Week 5", "resource/x-bb-folder", True), item("_2", "Syllabus", "resource/x-bb-file")]
    children = {
        "_1": [item("_3", "Slides", "resource/x-bb-folder", True), item("_4", "Reading", "resource/x-bb-document")],
        "_3": [item("_5", "Lecture 5.pdf", "resource/x-bb-file"), item("_6", "Extra", "resource/x-bb-folder", True)],
        "_6": [item("_7", "Too deep.pdf", "resource/x-bb-file")],
    }
    asked = []

    def fetch(folder_id):
        asked.append(folder_id)
        return children[folder_id]

    tree = walk_contents(top, fetch)
    materials = {m.title: m for m in materials_from(tree, "_101_1")}

    assert asked == ["_1", "_3"]  # "_6" is a third level down: not opened
    assert (materials["Lecture 5.pdf"].kind, materials["Lecture 5.pdf"].path) == ("file", "Week 5 / Slides")
    assert materials["Reading"].kind == "document"
    assert "Too deep.pdf" not in materials


def test_unavailable_materials_are_left_out():
    tree = walk_contents([item("_1", "Hidden.pdf", "resource/x-bb-file", available="No")], lambda _: [])

    assert materials_from(tree, "_101_1") == []


# ---- The whole section --------------------------------------------------------------

class FakeApi:
    """Answers like BlackboardClient.api_all; `refused` paths answer [] (HTTP 403)."""

    def __init__(self, answers, refused=()):
        self.answers, self.refused, self.user_id, self.asked = answers, set(refused), "_77_1", []

    def api_all(self, path):
        self.asked.append(path)
        if any(path.startswith(r) for r in self.refused):
            return []
        return self.answers.get(path.split("?")[0], [])


def section_answers():
    return {
        "/v1/users/_77_1/courses": [{"courseId": "_101_1", "course": course("_101_1", "IT093IU-2026-1-02", "Web Application Development")},
                                    {"courseId": "_102_1", "course": course("_102_1", "IT013IU-2025-2-01", "Algorithms")}],
        "/v1/courses/_101_1/announcements": [{"id": "_501_1", "title": "Hi", "body": "Welcome", "created": "2026-09-01T00:00:00.000Z"}],
        "/v2/courses/_101_1/gradebook/columns": COLUMNS,
        "/v2/courses/_101_1/gradebook/users/_77_1": GRADES,
        "/v1/courses/_101_1/contents": [item("_2", "Syllabus", "resource/x-bb-file")],
    }


def test_read_blackboard_builds_the_section_for_current_courses_only():
    api = FakeApi(section_answers())

    result = read_blackboard(api, [RegisteredCourse("IT093IU", "02")])

    [web] = result.courses
    assert (web.bb_id, web.course_code, web.name) == ("_101_1", "IT093IU", "Web Application Development")
    assert (len(web.announcements), len(web.assignments), len(web.materials)) == (1, 3, 1)
    assert not any("/_102_1/" in path for path in api.asked)


def test_a_course_that_hides_its_grades_still_syncs_the_rest():
    api = FakeApi(section_answers(), refused=["/v2/courses/_101_1/gradebook/users"])

    [web] = read_blackboard(api, [RegisteredCourse("IT093IU", "02")]).courses

    assert {a.status for a in web.assignments} == {"not_graded"}
    assert len(web.announcements) == 1


def test_answers_in_an_unexpected_shape_raise_source_changed():
    answers = section_answers()
    answers["/v1/courses/_101_1/announcements"] = [{"unexpected": True}]

    with pytest.raises(SourceChanged):
        read_blackboard(FakeApi(answers), [RegisteredCourse("IT093IU", "02")])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_blackboard_readers.py -q`
Expected: collection error `No module named 'sla_agent.blackboard_reader'`.

- [ ] **Step 3: Implement the pure readers**

Create `agent/sla_agent/parsers/blackboard.py`:

```python
"""Blackboard readers: Blackboard REST answers -> the shared data format. Pure functions."""

import re
from datetime import datetime
from urllib.parse import quote

from bs4 import BeautifulSoup
from pydantic import ValidationError
from sla_contract.schema import BbAnnouncement, BbAssignment, BbMaterial

from sla_agent.blackboard_client import BASE_URL
from sla_agent.errors import SourceChanged

ANNOUNCEMENT_LIMIT = 5000
FEEDBACK_LIMIT = 1000
KINDS = {
    "resource/x-bb-file": "file",
    "resource/x-bb-folder": "folder",
    "resource/x-bb-externallink": "link",
    "resource/x-bb-document": "document",
}
GRADE_STATUS = {"Graded": "graded", "NeedsGrading": "needs_grading"}


def html_to_text(html, limit):
    """Plain text: scripts, styles and embedded frames dropped, entities decoded, cut at `limit`."""
    page = BeautifulSoup(html or "", "html.parser")
    for tag in page(["script", "style", "iframe", "object", "embed", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", page.get_text(" ")).replace(" .", ".").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise SourceChanged(f"Blackboard sent an unreadable time {value!r}.") from None


def course_url(course_id):
    return f"{BASE_URL}/webapps/blackboard/execute/launcher?type=Course&id={quote(course_id)}&url="


def _mentions(text, code):
    return re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", text.upper()) is not None


def _describes(course):
    return f"{course.get('courseId', '')} {course.get('name', '')}".upper()


def _group_matches(course, course_code, group):
    if not group or not group.isdigit():
        return False
    # Leave the course code out: "IT093IU" must not count as group "03".
    text = _describes(course).replace(course_code, " ")
    return re.search(rf"(?<![0-9])0*{int(group)}(?![0-9])", text) is not None


def select_current_courses(courses, registered):
    """(course, code) for each registered course found on Blackboard. Ties: same group, then newest."""
    chosen = []
    for course_code, group in registered:
        candidates = [c for c in courses if _mentions(_describes(c), course_code)]
        if not candidates:
            continue
        same_group = [c for c in candidates if _group_matches(c, course_code, group)]
        pool = same_group or candidates
        pool.sort(key=lambda c: c.get("created") or "", reverse=True)
        chosen.append((pool[0], course_code))
    return chosen


def _model(model, **fields):
    try:
        return model(**fields)
    except ValidationError as error:
        raise SourceChanged(f"Blackboard data doesn't fit: {error.errors()[0]['msg']}") from None


def announcements_from(items, course_id):
    result = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise SourceChanged("An announcement has an unexpected format.")
        if item.get("draft"):
            continue
        start = ((item.get("availability") or {}).get("duration") or {}).get("start")
        result.append(_model(
            BbAnnouncement,
            bb_id=item["id"],
            title=(item.get("title") or "").strip()[:255] or "(no title)",
            text=html_to_text(item.get("body"), ANNOUNCEMENT_LIMIT),
            posted_at=parse_time(start or item.get("created")),
            url=course_url(course_id),
        ))
    return result


def assignments_from(columns, grades, course_id):
    by_column = {g.get("columnId"): g for g in grades if isinstance(g, dict)}
    result = []
    for column in columns:
        if not isinstance(column, dict) or "id" not in column:
            raise SourceChanged("A gradebook column has an unexpected format.")
        grading = column.get("grading") or {}
        if grading.get("type") == "Calculated" or (column.get("availability") or {}).get("available") == "No":
            continue
        grade = by_column.get(column["id"]) or {}
        if grade.get("exempt"):
            status = "exempt"
        else:
            status = GRADE_STATUS.get(grade.get("status"), "not_graded")
        display = grade.get("displayGrade") or {}
        score = grade.get("score", display.get("score")) if status == "graded" else None
        feedback = html_to_text(grade.get("feedback"), FEEDBACK_LIMIT) or None
        result.append(_model(
            BbAssignment,
            bb_id=column["id"],
            name=(column.get("name") or column.get("displayName") or "(no name)").strip()[:255],
            due_at=parse_time(grading.get("due")),
            points_possible=(column.get("score") or {}).get("possible"),
            score=score,
            grade_text=(display.get("text") or None) if status == "graded" else None,
            status=status,
            feedback=feedback,
            url=course_url(course_id),
        ))
    return result


def walk_contents(top_items, fetch_children, max_depth=2, max_folder_requests=15):
    """[(item, folder path)] for the top level and folders up to `max_depth` levels below it."""
    found, queue, requests_left = [], [(item, "", 0) for item in top_items], max_folder_requests
    while queue:
        item, path, depth = queue.pop(0)
        found.append((item, path))
        is_folder = (item.get("contentHandler") or {}).get("id") == "resource/x-bb-folder" or item.get("hasChildren")
        if is_folder and depth < max_depth and requests_left > 0:
            requests_left -= 1
            child_path = f"{path} / {item.get('title', '')}".strip(" /")
            queue += [(child, child_path, depth + 1) for child in fetch_children(item["id"])]
    return found


def materials_from(tree, course_id):
    result = []
    for item, path in tree:
        if not isinstance(item, dict) or "id" not in item:
            raise SourceChanged("A course item has an unexpected format.")
        if (item.get("availability") or {}).get("available") == "No":
            continue
        link = next((l.get("href") for l in item.get("links") or [] if (l.get("href") or "").startswith("/")), None)
        result.append(_model(
            BbMaterial,
            bb_id=item["id"],
            title=(item.get("title") or "(no title)").strip()[:255],
            kind=KINDS.get((item.get("contentHandler") or {}).get("id"), "other"),
            path=path[:500],
            created_at=parse_time(item.get("created")),
            url=f"{BASE_URL}{link}" if link else course_url(course_id),
        ))
    return result
```

- [ ] **Step 4: Implement the section reader**

Create `agent/sla_agent/blackboard_reader.py`:

```python
"""Read the Blackboard section through a logged-in client (BlackboardClient or a test double)."""

from sla_contract.schema import BbCourse, Blackboard

from sla_agent.parsers.blackboard import (
    announcements_from,
    assignments_from,
    course_url,
    materials_from,
    select_current_courses,
    walk_contents,
)


def read_blackboard(client, registered):
    me = client.user_id
    memberships = client.api_all(f"/v1/users/{me}/courses?limit=100&expand=course")
    courses = [m["course"] for m in memberships if isinstance(m, dict) and isinstance(m.get("course"), dict)]

    result = []
    for course, code in select_current_courses(courses, registered):
        cid = course["id"]
        announcements = client.api_all(f"/v1/courses/{cid}/announcements?limit=100")
        columns = client.api_all(f"/v2/courses/{cid}/gradebook/columns?limit=100")
        grades = client.api_all(f"/v2/courses/{cid}/gradebook/users/{me}?limit=100")
        top = client.api_all(f"/v1/courses/{cid}/contents?limit=100")
        tree = walk_contents(top, lambda item_id: client.api_all(f"/v1/courses/{cid}/contents/{item_id}/children?limit=100"))
        result.append(BbCourse(
            bb_id=cid,
            course_code=code,
            name=(course.get("name") or code)[:255],
            url=course_url(cid),
            announcements=announcements_from(announcements, cid),
            assignments=assignments_from(columns, grades, cid),
            materials=materials_from(tree, cid),
        ))
    return Blackboard(courses=result)
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/sla_agent/parsers/blackboard.py agent/sla_agent/blackboard_reader.py agent/tests/test_blackboard_readers.py
git commit -m "feat(agent): Blackboard readers for courses, announcements, assignments, grades and materials" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: EduSoft and Blackboard sync independently

**Files:**
- Modify: `agent/sla_agent/sync.py`, `agent/sla_agent/cli.py`, `agent/tests/test_sync.py`, `agent/tests/test_cli.py`

**Interfaces:**
- Consumes: `FakeBlackboard` (Task 2), `read_blackboard` (Task 5), `parse_registered_courses`, `RegisteredCourse` (Task 4), `EDUSOFT_SECTIONS` (Task 3).
- Produces: `run_sync(trigger, *, state, edusoft, server, parsers, password, now, blackboard=None, blackboard_password=None, read_blackboard=read_blackboard) -> Outcome`; `sync.BLACKBOARD_PAUSE_MESSAGES`; `sync.everything_paused(state) -> bool`.

- [ ] **Step 1: Update the existing sync tests for per-system failures**

In `agent/tests/test_sync.py`:
- In `test_a_wrong_password_pauses_after_exactly_one_login_attempt` replace `assert only_finish(server).error_code == "bad_credentials"` with:

```python
    result = only_finish(server)
    assert {name: part.error_code for name, part in result.sections().items()} == {
        "timetable": "bad_credentials", "exams": "bad_credentials", "tuition": "bad_credentials"}
```

- In `test_extra_verification_pauses_and_suggests_import` replace `assert only_finish(server).error_code == "extra_verification"` with `assert only_finish(server).timetable.error_code == "extra_verification"`.
- In `test_edusoft_unreachable_is_reported_but_does_not_pause` replace `assert only_finish(server).error_code == "network"` with `assert only_finish(server).timetable.error_code == "network"`.
- In `test_a_password_rejected_during_re_login_pauses_and_stops` replace `assert only_finish(server).error_code == "bad_credentials"` with `assert only_finish(server).timetable.error_code == "bad_credentials"`.
- Change the `sync()` helper to:

```python
def sync(state, edusoft, server=None, parsers=PARSERS, trigger="scheduled", blackboard=None, read=None):
    server = server or FakeServer()
    outcome = run_sync(trigger, state=state, edusoft=edusoft, server=server, parsers=parsers,
                       password=PASSWORD, now=NOW, blackboard=blackboard,
                       blackboard_password=BB_PASSWORD if blackboard else None,
                       read_blackboard=read or empty_blackboard)
    return outcome, server
```

and add above it:

```python
from sla_contract.schema import Blackboard

from agent.tests.fakes import FakeBlackboard

BB_PASSWORD = "bb-s3cret"


def empty_blackboard(client, registered):
    return Blackboard(courses=[])
```

- [ ] **Step 2: Write the new failing tests**

Append to `agent/tests/test_sync.py`:

```python
@pytest.fixture
def bb_state(state):
    state.blackboard_username = "bbuser"
    state.registered_courses = [["IT093IU", "02"]]
    return state


def test_blackboard_syncs_after_edusoft_and_logs_out(bb_state):
    blackboard = FakeBlackboard()
    seen = []

    def read(client, registered):
        seen.append(registered)
        return Blackboard(courses=[])

    outcome, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard, read=read)

    assert list(only_finish(server).sections()) == ["timetable", "exams", "tuition", "blackboard"]
    assert blackboard.logins == [("bbuser", BB_PASSWORD)]
    assert blackboard.logouts == 1
    assert outcome.status == "success"
    assert len(seen) == 1


def test_a_wrong_edusoft_password_still_syncs_blackboard_with_the_last_known_courses(bb_state):
    edusoft = FakeEduSoft(login_error=BadCredentials("rejected"))
    seen = []

    outcome, server = sync(bb_state, edusoft, blackboard=FakeBlackboard(),
                           read=lambda client, registered: seen.append(registered) or Blackboard(courses=[]))

    result = only_finish(server)
    assert result.timetable.error_code == "bad_credentials"
    assert result.blackboard.status == "ok"
    assert bb_state.paused == "bad_credentials"
    assert [tuple(r) for r in seen[0]] == [("IT093IU", "02")]


def test_a_wrong_blackboard_password_pauses_only_blackboard(bb_state):
    blackboard = FakeBlackboard(login_error=BadCredentials("rejected"))

    outcome, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard)

    result = only_finish(server)
    assert (result.timetable.status, result.blackboard.error_code) == ("ok", "bad_credentials")
    assert (bb_state.paused, bb_state.blackboard_paused) == (None, "bad_credentials")
    assert len(blackboard.logins) == 1
    assert "sla-agent setup --blackboard" in outcome.message


def test_a_paused_blackboard_is_not_contacted(bb_state):
    bb_state.blackboard_paused = "bad_credentials"
    blackboard = FakeBlackboard()

    sync(bb_state, FakeEduSoft(), blackboard=blackboard)

    assert blackboard.logins == []


def test_both_paused_contacts_nobody(bb_state):
    bb_state.paused, bb_state.blackboard_paused = "bad_credentials", "bad_credentials"
    edusoft, blackboard = FakeEduSoft(), FakeBlackboard()

    outcome, server = sync(bb_state, edusoft, blackboard=blackboard)

    assert (edusoft.logins, blackboard.logins, server.starts) == ([], [], [])
    assert outcome.status == "paused"


def test_an_expired_blackboard_session_logs_in_again_once(bb_state):
    blackboard = FakeBlackboard()
    calls = []

    def read(client, registered):
        calls.append(1)
        if len(calls) == 1:
            raise SessionExpired("expired")
        return Blackboard(courses=[])

    _, server = sync(bb_state, FakeEduSoft(), blackboard=blackboard, read=read)

    assert len(blackboard.logins) == 2
    assert only_finish(server).blackboard.status == "ok"


def test_blackboard_without_a_known_course_list_waits_for_edusoft(state):
    state.blackboard_username, state.paused = "bbuser", "bad_credentials"

    _, server = sync(state, FakeEduSoft(), blackboard=FakeBlackboard())

    result = only_finish(server)
    assert result.blackboard.status == "failed"
    assert "course list" in result.blackboard.error_message


def test_the_registered_course_list_is_remembered(bb_state):
    from pathlib import Path

    page = (Path(__file__).parent / "fixtures" / "registration.html").read_text(encoding="utf-8")
    bb_state.registered_courses = None
    edusoft = FakeEduSoft(pages={"registration": [{"registration": page}]})

    sync(bb_state, edusoft)

    assert ["IT093IU", "02"] in bb_state.registered_courses
    assert len(bb_state.registered_courses) == 8
```

In `agent/tests/test_cli.py` add (these use `configure()` and `World`):

```python
def test_run_syncs_blackboard_when_it_is_set_up(world, monkeypatch):
    from sla_contract.schema import Blackboard

    configure()
    credentials.save_blackboard(BB_USER, BB_PASSWORD)
    state = load_state()
    state.blackboard_username, state.registered_courses = BB_USER, [["IT093IU", "02"]]
    save_state(state)
    monkeypatch.setattr(cli, "read_blackboard", lambda client, registered: Blackboard(courses=[]))

    assert cli.main(["run"]) == 0

    assert world.blackboard.logins == [(BB_USER, BB_PASSWORD)]
    assert "blackboard" in world.server.finishes[0][1].sections()


def test_run_with_only_edusoft_paused_still_syncs_blackboard(world, monkeypatch):
    from sla_contract.schema import Blackboard

    configure(paused="bad_credentials")
    credentials.save_blackboard(BB_USER, BB_PASSWORD)
    state = load_state()
    state.blackboard_username, state.registered_courses = BB_USER, [["IT093IU", "02"]]
    save_state(state)
    monkeypatch.setattr(cli, "read_blackboard", lambda client, registered: Blackboard(courses=[]))

    cli.main(["run"])

    assert world.edusoft.logins == []
    assert world.blackboard.logins == [(BB_USER, BB_PASSWORD)]
```

- [ ] **Step 3: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_sync.py agent/tests/test_cli.py -q`
Expected: failures (`run_sync() got an unexpected keyword argument 'blackboard'`, `cli` has no `read_blackboard`).

- [ ] **Step 4: Rewrite the sync**

Replace `agent/sla_agent/sync.py` with:

```python
"""One sync: EduSoft (timetable, exams, tuition) then Blackboard, each on its own.

Stop-don't-retry rules: a rejected password or an extra-verification request pauses
that system only (no second login attempt). An expired session gets one re-login and
one retry. One system failing never stops the other from uploading.
"""

import logging
from dataclasses import dataclass

from sla_contract.schema import EDUSOFT_SECTIONS, FinishRun

from sla_agent.blackboard_reader import read_blackboard as default_read_blackboard
from sla_agent.errors import AgentError, BadCredentials, ExtraVerification, SessionExpired
from sla_agent.log import protect
from sla_agent.parsers.registration import RegisteredCourse, parse_registered_courses

log = logging.getLogger(__name__)

PAUSE_MESSAGES = {
    "bad_credentials": "EduSoft rejected your student ID or password. EduSoft sync is paused; "
                       "run `sla-agent setup` to enter them again.",
    "extra_verification": "EduSoft asked for extra verification (CAPTCHA or code). EduSoft sync is "
                          "paused; save the pages from your browser and use `sla-agent import`.",
}
BLACKBOARD_PAUSE_MESSAGES = {
    "bad_credentials": "Blackboard rejected your username or password. Blackboard sync is paused; "
                       "run `sla-agent setup --blackboard` to enter them again.",
    "extra_verification": "Blackboard asked for extra verification (CAPTCHA, code or Microsoft sign-in). "
                          "Blackboard sync is paused.",
}
PAUSING_ERRORS = (BadCredentials, ExtraVerification)
NO_COURSE_LIST = "Blackboard needs this semester's course list from EduSoft first; it will sync after EduSoft does."


@dataclass
class Outcome:
    status: str  # success / partial / failed / paused
    message: str


def _failed(error):
    return {"status": "failed", "error_code": error.code, "error_message": str(error)[:500] or error.code}


def _unexpected(what, error):
    log.exception("Unexpected problem reading %s", what)
    return {"status": "failed", "error_code": "unknown",
            "error_message": f"Unexpected problem reading {what}: {error.__class__.__name__}"}


def blackboard_ready(state):
    return bool(state.blackboard_username) and not state.blackboard_paused


def everything_paused(state):
    return bool(state.paused) and not blackboard_ready(state)


def _read_section(name, edusoft, parsers, student_id, password):
    """One EduSoft part's result. Pausing errors are raised to stop EduSoft."""
    try:
        try:
            pages = edusoft.read(name)
        except SessionExpired:
            log.info("EduSoft session expired while reading %s; logging in again once", name)
            edusoft.login(student_id, password)
            pages = edusoft.read(name)
        return {"status": "ok", "data": parsers[name](pages)}
    except PAUSING_ERRORS:
        raise
    except AgentError as error:
        log.warning("Couldn't read %s: %s", name, error)
        return _failed(error)
    except Exception as error:  # a parser bug must not leave the run unfinished
        return _unexpected(name, error)


def _remember_registered_courses(state, edusoft, sections):
    """This semester's courses for Blackboard: EduSoft's registration list, else the timetable's codes."""
    try:
        registered = parse_registered_courses(edusoft.read("registration"))
    except Exception as error:  # the registration page is optional; fall back to the timetable
        log.info("Registration list not read (%s); using the timetable's courses", error.__class__.__name__)
        timetable = sections.get("timetable", {})
        data = timetable.get("data") if timetable.get("status") == "ok" else None
        registered = [RegisteredCourse(c.course_code, c.group or "") for c in data.courses] if data else []
    if registered:
        state.registered_courses = [[r.code, r.group] for r in registered]


def _collect_edusoft(state, edusoft, parsers, password):
    try:
        edusoft.login(state.student_id, password)
        sections = {name: _read_section(name, edusoft, parsers, state.student_id, password)
                    for name in EDUSOFT_SECTIONS}
        _remember_registered_courses(state, edusoft, sections)
        return sections
    except PAUSING_ERRORS as error:
        log.warning("Pausing EduSoft sync: %s", error)
        state.paused = error.code
        return {name: _failed(error) for name in EDUSOFT_SECTIONS}
    except AgentError as error:
        log.warning("EduSoft sync failed: %s", error)
        return {name: _failed(error) for name in EDUSOFT_SECTIONS}
    except Exception as error:
        failure = _unexpected("EduSoft", error)
        return {name: failure for name in EDUSOFT_SECTIONS}


def _collect_blackboard(state, blackboard, password, read):
    registered = [RegisteredCourse(code, group) for code, group in state.registered_courses or []]
    if not registered:
        return {"status": "failed", "error_code": "unknown", "error_message": NO_COURSE_LIST}
    try:
        blackboard.login(state.blackboard_username, password)
        try:
            data = read(blackboard, registered)
        except SessionExpired:
            log.info("Blackboard session expired; logging in again once")
            blackboard.login(state.blackboard_username, password)
            data = read(blackboard, registered)
        return {"status": "ok", "data": data}
    except PAUSING_ERRORS as error:
        log.warning("Pausing Blackboard sync: %s", error)
        state.blackboard_paused = error.code
        return _failed(error)
    except AgentError as error:
        log.warning("Blackboard sync failed: %s", error)
        return _failed(error)
    except Exception as error:
        return _unexpected("Blackboard", error)
    finally:
        blackboard.logout()


def _message(state, result, used_edusoft, used_blackboard):
    notes = []
    if used_edusoft and state.paused:
        notes.append(PAUSE_MESSAGES.get(state.paused, "EduSoft sync is paused."))
    if used_blackboard and state.blackboard_paused:
        notes.append(BLACKBOARD_PAUSE_MESSAGES.get(state.blackboard_paused, "Blackboard sync is paused."))
    if notes:
        return " ".join(notes)
    failed = [name for name, part in result.sections().items() if part.status == "failed"]
    return "Sync finished." if not failed else f"Sync finished, but couldn't read: {', '.join(failed)}."


def _paused_message(state):
    messages = [PAUSE_MESSAGES.get(state.paused, "EduSoft sync is paused.")]
    if state.blackboard_username and state.blackboard_paused:
        messages.append(BLACKBOARD_PAUSE_MESSAGES.get(state.blackboard_paused, "Blackboard sync is paused."))
    return " ".join(messages)


def run_sync(trigger, *, state, edusoft, server, parsers, password, now,
             blackboard=None, blackboard_password=None, read_blackboard=default_read_blackboard):
    """Run one sync and update `state` (the caller saves it). Server errors are raised."""
    protect(password)
    protect(blackboard_password)
    use_edusoft = not state.paused
    use_blackboard = blackboard is not None and bool(blackboard_password) and blackboard_ready(state)
    if not use_edusoft and not use_blackboard:
        return Outcome("paused", _paused_message(state))

    run_id = server.start(trigger)
    state.last_attempt_at = now.isoformat()
    sections = {}
    if use_edusoft:
        sections.update(_collect_edusoft(state, edusoft, parsers, password))
    if use_blackboard:
        sections["blackboard"] = _collect_blackboard(state, blackboard, blackboard_password, read_blackboard)
    result = FinishRun.model_validate(sections)
    status = server.finish(run_id, result)

    message = _message(state, result, use_edusoft, use_blackboard)
    state.last_result = {"at": now.isoformat(), "status": status, "message": message}
    log.info("Sync %s (%s): %s", status, trigger, message)
    return Outcome(status, message)
```

- [ ] **Step 5: Pass Blackboard through the CLI**

In `agent/sla_agent/cli.py`:
- Change `from sla_agent.sync import PAUSE_MESSAGES, run_sync` to `from sla_agent.sync import PAUSE_MESSAGES, everything_paused, run_sync` and add `from sla_agent.blackboard_reader import read_blackboard`.
- Replace `_sync` with:

```python
def _blackboard_login(state):
    """(client, password) when Blackboard is set up, else (None, None)."""
    if not state.blackboard_username:
        return None, None
    password = credentials.load_blackboard(state.blackboard_username)
    return (make_blackboard(), password) if password else (None, None)


def _sync(trigger, state, password, server):
    blackboard, blackboard_password = _blackboard_login(state)
    try:
        outcome = run_sync(trigger, state=state, edusoft=make_edusoft(), server=server, parsers=PARSERS,
                           password=password, now=_now(), blackboard=blackboard,
                           blackboard_password=blackboard_password, read_blackboard=read_blackboard)
    except RunInProgress:
        say("A sync is already running.")
        return 0
    except DeviceKeyRejected as error:
        say(f"{error} Run `sla-agent setup` with a new key.")
        return 1
    except ServerError as error:
        log.warning("Web app problem: %s", error)
        say(f"Couldn't reach the web app: {error}")
        save_state(state)
        return 1
    save_state(state)
    say(outcome.message)
    return 0 if outcome.status in ("success", "partial") else 1
```

Note: `read_blackboard` is looked up on the `cli` module at call time (`read_blackboard=read_blackboard` inside the function body), so the test's `monkeypatch.setattr(cli, "read_blackboard", ...)` takes effect.

- In `cmd_run` replace `if state.paused:` / its log line with:

```python
    if everything_paused(state):
        log.info("Automatic sync is paused for every system; not syncing")
        return 0
```

- In `cmd_sync_now` replace `if state.paused:` and its two lines with:

```python
    if everything_paused(state):
        say(PAUSE_MESSAGES.get(state.paused, "Automatic sync is paused."))
        return 1
```

- [ ] **Step 6: Run the agent tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add agent/sla_agent/sync.py agent/sla_agent/cli.py agent/tests/test_sync.py agent/tests/test_cli.py
git commit -m "feat(agent): EduSoft and Blackboard sync and pause independently" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Real Blackboard samples (needs the student)

**Files:**
- Create: `agent/tools/anonymize_blackboard.py`, `agent/tests/fixtures/blackboard-raw.json` (generated), `agent/tests/test_blackboard_samples.py`
- Modify: `agent/sla_agent/cli.py` (fetch), `agent/tests/test_cli.py`, `docs/superpowers/specs/2026-09-26-blackboard-design.md`

**Interfaces:**
- Consumes: `BlackboardClient.capture` (Task 1), `read_blackboard` (Task 5), `parse_registered_courses` (Task 4).
- Produces: `fetch --save-html` writes `blackboard-raw.json` (every API answer by path) when Blackboard is set up.

- [ ] **Step 1: Write the failing fetch test**

Append to `agent/tests/test_cli.py`:

```python
def test_fetch_also_saves_blackboards_answers_when_set_up(world, tmp_path, monkeypatch):
    import json

    from sla_contract.schema import Blackboard

    configure()
    credentials.save_blackboard(BB_USER, BB_PASSWORD)
    state = load_state()
    state.blackboard_username, state.registered_courses = BB_USER, [["IT093IU", "02"]]
    save_state(state)

    def read(client, registered):
        client.capture["/v1/users/_1_1/courses?limit=100&expand=course"] = {"results": []}
        return Blackboard(courses=[])

    monkeypatch.setattr(cli, "read_blackboard", read)
    folder = tmp_path / "pages"

    assert cli.main(["fetch", "--save-html", str(folder)]) == 0

    saved = json.loads((folder / "blackboard-raw.json").read_text(encoding="utf-8"))
    assert saved == {"/v1/users/_1_1/courses?limit=100&expand=course": {"results": []}}
    assert world.blackboard.logouts == 1
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_cli.py -k blackboards_answers -q`
Expected: FAIL (`blackboard-raw.json` doesn't exist).

- [ ] **Step 3: Save Blackboard answers in fetch**

In `agent/sla_agent/cli.py` `cmd_fetch`, right before `folder.mkdir(parents=True, exist_ok=True)`, add:

```python
    blackboard, blackboard_password = _blackboard_login(state)
    if blackboard is not None and not state.blackboard_paused:
        registered = [RegisteredCourse(code, group) for code, group in state.registered_courses or []]
        blackboard.capture = {}
        try:
            blackboard.login(state.blackboard_username, blackboard_password)
            read_blackboard(blackboard, registered)
        except AgentError as error:
            say(f"Couldn't read Blackboard: {error}")
        finally:
            blackboard.logout()
        files["blackboard-raw.json"] = json.dumps(blackboard.capture, ensure_ascii=False, indent=1)
```

Add `import json` at the top and `from sla_agent.parsers.registration import RegisteredCourse`. In `FakeBlackboard.__init__` (agent/tests/fakes.py) add `self.capture = None`.

- [ ] **Step 4: Run the agent tests**

Run: `.venv/Scripts/python.exe -m pytest agent/tests -q`
Expected: all pass. Commit:

```bash
git add agent/sla_agent/cli.py agent/tests/fakes.py agent/tests/test_cli.py
git commit -m "feat(agent): fetch --save-html also saves Blackboard's answers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: The student sets up Blackboard and saves samples**

Ask the student to run, in the project terminal with `(.venv)`:

```powershell
sla-agent setup --blackboard
sla-agent fetch --save-html "$env:USERPROFILE\Documents\edusoft-pages"
```

Expected: "Blackboard saved…", then "Saved N pages…", and `Documents\edusoft-pages\blackboard-raw.json` exists.

- [ ] **Step 6: Create the anonymizer**

Create `agent/tools/anonymize_blackboard.py`:

```python
"""Make an anonymized test copy of Blackboard answers saved by `sla-agent fetch`.

Usage: python -m agent.tools.anonymize_blackboard SAVED_JSON OUTPUT_JSON
Keeps the structure, IDs of courses/items, course IDs and names, dates and content types.
Replaces the student's user record and ID, announcement titles and bodies, grades, feedback,
item titles and descriptions."""

import json
import re
import sys
from pathlib import Path

TEXT_KEYS = {"body": "Anonymized text.", "description": "Anonymized description.",
             "feedback": "<p>Anonymized feedback.</p>", "text": "8"}


def anonymize(raw):
    me = next((v.get("id") for k, v in raw.items() if k.startswith("/v1/users/me") and isinstance(v, dict)), None)
    counter = {"title": 0}

    def fake_title():
        counter["title"] += 1
        return f"Item {counter['title']}"

    def clean(value, key=None, parent_key=None):
        if isinstance(value, dict):
            return {k: clean(v, k, key) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v, key, parent_key) for v in value]
        if not isinstance(value, str):
            if key == "score" and isinstance(value, (int, float)) and parent_key != "score":
                return 8.0
            return value
        if me and me in value:
            value = value.replace(me, "_1_1")
        if key in TEXT_KEYS:
            return TEXT_KEYS[key]
        if key == "title":
            return fake_title()
        return value

    result = {}
    for path, body in raw.items():
        if path.startswith("/v1/users/me"):
            result["/v1/users/me"] = {"id": "_1_1"}
            continue
        result[path.replace(me, "_1_1") if me else path] = clean(body)
    return result, me


if __name__ == "__main__":
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    raw = json.loads(source.read_text(encoding="utf-8"))
    result, me = anonymize(raw)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    text = json.dumps(result, ensure_ascii=False)
    user = raw.get("/v1/users/me", {})
    personal = [v for v in (me, user.get("userName"), user.get("studentId"),
                            (user.get("contact") or {}).get("email"),
                            (user.get("name") or {}).get("given"), (user.get("name") or {}).get("family")) if v]
    leaks = sum(v in text for v in personal)
    emails = len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text))
    print(f"answers: {len(result)}, personal values still present: {leaks}, emails: {emails}")
```

Note: `fetch` captures `/v1/users/me` only if the client's `login` ran with `capture` set; Step 3 sets `capture` before `login`, so it is present.

Run:
```bash
.venv/Scripts/python.exe -m agent.tools.anonymize_blackboard "$USERPROFILE/Documents/edusoft-pages/blackboard-raw.json" agent/tests/fixtures/blackboard-raw.json
```
Expected: `personal values still present: 0, emails: 0`.

- [ ] **Step 7: Write the real-sample tests**

Create `agent/tests/test_blackboard_samples.py`:

```python
"""The Blackboard reader against anonymized copies of real answers (saved 2026-09-26)."""

import json
from pathlib import Path

from sla_agent.blackboard_client import BASE_URL
from sla_agent.blackboard_reader import read_blackboard
from sla_agent.parsers.registration import parse_registered_courses

FIXTURES = Path(__file__).parent / "fixtures"
RAW = json.loads((FIXTURES / "blackboard-raw.json").read_text(encoding="utf-8"))
REGISTERED = parse_registered_courses({"registration": (FIXTURES / "registration.html").read_text(encoding="utf-8")})


class Replay:
    """Serves saved answers like BlackboardClient.api_all, following saved paging."""

    user_id = "_1_1"

    def api_all(self, path):
        results, next_path = [], path
        while next_path in RAW:
            body = RAW[next_path]
            results += body.get("results", [])
            next_page = (body.get("paging") or {}).get("nextPage")
            next_path = next_page.removeprefix("/learn/api/public") if next_page else None
        return results


def test_every_registered_course_is_found_on_blackboard():
    section = read_blackboard(Replay(), REGISTERED)

    assert sorted(c.course_code for c in section.courses) == sorted(r.code for r in REGISTERED)


def test_the_real_answers_become_valid_safe_data():
    section = read_blackboard(Replay(), REGISTERED)

    for course in section.courses:
        items = course.announcements + course.assignments + course.materials
        assert all(item.url.startswith(f"{BASE_URL}/") for item in items)
        assert all("<" not in a.text for a in course.announcements)
        assert all(a.due_at is None or a.due_at.tzinfo is not None for a in course.assignments)
    assert sum(len(c.announcements) + len(c.assignments) + len(c.materials) for c in section.courses) > 0
```

- [ ] **Step 8: Run them**

Run: `.venv/Scripts/python.exe -m pytest agent/tests/test_blackboard_samples.py -q`
Expected: PASS.

If `test_every_registered_course_is_found_on_blackboard` fails: print the anonymized `courseId`/`name` pairs with
`.venv/Scripts/python.exe -c "import json; r=json.load(open('agent/tests/fixtures/blackboard-raw.json', encoding='utf-8')); print([(m['course']['courseId'], m['course']['name']) for k,v in r.items() if 'expand=course' in k for m in v['results']])"`
and adapt `_mentions`/`_describes` in `agent/sla_agent/parsers/blackboard.py` to where the code actually appears (then add a unit test in `test_blackboard_readers.py` with that exact format). Re-run until green.

- [ ] **Step 9: Record the observed course-ID format in the spec**

In `docs/superpowers/specs/2026-09-26-blackboard-design.md`, section 3, rule 2, replace "How the code appears in Blackboard's course ID or name is confirmed from the real samples in step B2." with one sentence describing the observed format, e.g. "On IU's Blackboard the code appears in the course ID, e.g. `<observed example with the student's details removed>`."

- [ ] **Step 10: Commit**

```bash
git add agent/tools/anonymize_blackboard.py agent/tests/fixtures/blackboard-raw.json agent/tests/test_blackboard_samples.py agent/sla_agent/parsers/blackboard.py agent/tests/test_blackboard_readers.py docs/superpowers/specs/2026-09-26-blackboard-design.md
git commit -m "test(agent): Blackboard reader against anonymized real answers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Server: Blackboard tables, saving and "What changed" lines

**Files:**
- Modify: `app/school/models.py`, `app/school/services/ingest.py`, `app/school/services/changes.py`, `tests/helpers.py`
- Create: `migrations/versions/<generated>_blackboard_tables.py`, `tests/test_school_blackboard_ingest.py`
- Test additions: `tests/test_school_changes.py`

**Interfaces:**
- Consumes: contract `Blackboard` section (Task 3).
- Produces: models `SchoolBbCourse(bb_id, course_code, name, url, announcements, assignments, materials)`, `SchoolBbAnnouncement(course_id, bb_id, title, text, posted_at, url)`, `SchoolBbAssignment(course_id, bb_id, name, due_at, points_possible, score, grade_text, status, feedback, url)`, `SchoolBbMaterial(course_id, bb_id, title, kind, path, created_at, url)`; `changes.BbItem`, `changes.blackboard_changes(old, new) -> list[Change]`; `tests.helpers.blackboard_payload()`.

- [ ] **Step 1: Move the sample payload into the shared test helpers**

Move `blackboard_payload()` and `BB` from `tests/test_contract.py` into `tests/helpers.py` (same code), and in `tests/test_contract.py` import them: `from tests.helpers import BB, blackboard_payload, full_payload`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_school_changes.py`:

```python
from app.school.services.changes import BbItem, blackboard_changes

DUE = datetime(2026, 10, 2, 16, 59)  # Fri 02/10 23:59 Vietnam


def bb(kind, bb_id, title, **extra):
    return BbItem(kind=kind, course="Web App", bb_id=bb_id, title=title, **extra)


def test_first_blackboard_sync_gives_one_summary_line():
    new = (["Web App"], [bb("announcement", "a1", "Hi"), bb("assignment", "x1", "Lab 3", due_at=DUE)])

    assert summaries(blackboard_changes(None, new)) == [
        ("added", "Blackboard loaded: 1 course, 1 announcement, 1 assignment, 0 materials")]


def test_no_blackboard_courses_means_no_line():
    assert blackboard_changes(None, ([], [])) == []


def test_new_announcement_assignment_and_material():
    old = (["Web App"], [])
    new = (["Web App"], [bb("announcement", "a1", "No class on Thursday"),
                         bb("assignment", "x1", "Lab 3", due_at=DUE),
                         bb("material", "m1", "Week 5 slides.pdf", material_kind="file"),
                         bb("material", "m2", "Week 5", material_kind="folder")])

    assert summaries(blackboard_changes(old, new)) == [
        ("added", "New announcement · Web App: No class on Thursday"),
        ("added", "New assignment · Web App: Lab 3, due Fri 02/10 23:59"),
        ("added", "New material · Web App: Week 5 slides.pdf"),
    ]


def test_a_moved_deadline_and_a_new_grade():
    before = bb("assignment", "x1", "Lab 3", due_at=DUE, status="not_graded", points_possible=10.0)
    after = before._replace(due_at=datetime(2026, 10, 5, 16, 59), status="graded", score=8.5)

    assert summaries(blackboard_changes((["Web App"], [before]), (["Web App"], [after]))) == [
        ("changed", "Due date changed · Web App, Lab 3: Fri 02/10 23:59 → Mon 05/10 23:59"),
        ("changed", "New grade · Web App, Lab 3: 8.5/10"),
    ]
```

Create `tests/test_school_blackboard_ingest.py`:

```python
from datetime import datetime

import pytest
from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse, SchoolBbMaterial, SchoolChange
from tests.helpers import api, blackboard_payload, full_payload, make_device, make_user


@pytest.fixture
def key(app):
    return make_device(app, make_user(app))


def sync(app, key, blackboard_part):
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "manual"}).get_json()["run_id"]
    payload = full_payload()
    payload["blackboard"] = blackboard_part
    response = api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["status"]


def rows(app, model):
    with app.app_context():
        return db.session.execute(select(model).order_by(model.id)).scalars().all()


def test_the_blackboard_section_is_saved_with_times_in_utc(app, key):
    assert sync(app, key, {"status": "ok", "data": blackboard_payload()}) == "success"

    [course] = rows(app, SchoolBbCourse)
    assert (course.bb_id, course.course_code, course.name) == ("_101_1", "IT093IU", "Web Application Development")
    [assignment] = rows(app, SchoolBbAssignment)
    assert (assignment.course_id, assignment.due_at, assignment.score, assignment.status) == (
        course.id, datetime(2026, 10, 2, 16, 59), 8.5, "graded")
    assert len(rows(app, SchoolBbAnnouncement)) == 1
    assert rows(app, SchoolBbMaterial)[0].path == "Week 5"


def test_a_new_blackboard_sync_replaces_the_old_rows(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})
    data = blackboard_payload()
    data["courses"][0]["announcements"] = []

    sync(app, key, {"status": "ok", "data": data})

    assert rows(app, SchoolBbAnnouncement) == []
    assert len(rows(app, SchoolBbCourse)) == 1


def test_a_failed_blackboard_part_keeps_the_old_rows(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})

    status = sync(app, key, {"status": "failed", "error_code": "source_changed", "error_message": "Unexpected"})

    assert status == "partial"
    assert len(rows(app, SchoolBbAnnouncement)) == 1


def test_blackboard_changes_reach_the_feed(app, key):
    sync(app, key, {"status": "ok", "data": blackboard_payload()})
    data = blackboard_payload()
    data["courses"][0]["announcements"].append({
        "bb_id": "_502_1", "title": "Room change", "text": "Moved to A2.508.",
        "posted_at": "2026-09-29T02:00:00+00:00", "url": "https://blackboard.hcmiu.edu.vn/x"})

    sync(app, key, {"status": "ok", "data": data})

    summaries = [c.summary for c in rows(app, SchoolChange) if c.section == "blackboard"]
    assert summaries[0].startswith("Blackboard loaded: 1 course")
    assert summaries[-1] == "New announcement · Web Application Development: Room change"
```

- [ ] **Step 3: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_changes.py tests/test_school_blackboard_ingest.py -q`
Expected: import errors (`BbItem`, `SchoolBbCourse` don't exist).

- [ ] **Step 4: Add the models**

Append to `app/school/models.py`:

```python
# ---- Blackboard --------------------------------------------------------------


def _bb_course_id():
    return mapped_column(ForeignKey("school_bb_courses.id", ondelete="CASCADE"), nullable=False, index=True)


class SchoolBbCourse(db.Model):
    __tablename__ = "school_bb_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    announcements: Mapped[list["SchoolBbAnnouncement"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    assignments: Mapped[list["SchoolBbAssignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    materials: Mapped[list["SchoolBbMaterial"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True)


class SchoolBbAnnouncement(db.Model):
    __tablename__ = "school_bb_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="announcements")


class SchoolBbAssignment(db.Model):
    __tablename__ = "school_bb_assignments"
    __table_args__ = (Index("ix_school_bb_assignments_user_due", "user_id", "due_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    points_possible: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    grade_text: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="assignments")


class SchoolBbMaterial(db.Model):
    __tablename__ = "school_bb_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = _user_id()
    course_id: Mapped[int] = _bb_course_id()
    bb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    course: Mapped[SchoolBbCourse] = relationship(back_populates="materials")
```

Add `Float` to the `from sqlalchemy import (...)` list at the top of the file.

- [ ] **Step 5: Generate the migration**

```bash
S="$TEMP/sla-gen.db"; rm -f "$S"
SECRET_KEY=dev-only DATABASE_URL="sqlite:///$S" .venv/Scripts/flask.exe db upgrade
SECRET_KEY=dev-only DATABASE_URL="sqlite:///$S" .venv/Scripts/flask.exe db migrate -m "blackboard tables"
```
Expected: "Detected added table" for the four `school_bb_*` tables and a new file in `migrations/versions/`.

- [ ] **Step 6: Add the "What changed" lines**

Append to `app/school/services/changes.py`:

```python
class BbItem(NamedTuple):
    kind: str  # announcement / assignment / material
    course: str
    bb_id: str
    title: str
    due_at: datetime | None = None  # naive UTC
    status: str | None = None
    score: float | None = None
    points_possible: float | None = None
    grade_text: str | None = None
    material_kind: str | None = None


def _number(value):
    return f"{value:g}"


def _grade(item):
    if item.score is not None and item.points_possible:
        return f"{_number(item.score)}/{_number(item.points_possible)}"
    if item.score is not None:
        return _number(item.score)
    return item.grade_text or "graded"


def blackboard_changes(old, new):
    """old/new: (course names, [BbItem]). old is None on the first Blackboard sync."""
    courses, items = new
    if old is None:
        if not courses:
            return []
        def count(kind):
            return sum(1 for i in items if i.kind == kind)
        return [Change("added", f"Blackboard loaded: {_count(len(courses), 'course')}, "
                                f"{_count(count('announcement'), 'announcement')}, "
                                f"{_count(count('assignment'), 'assignment')}, "
                                f"{_count(count('material'), 'material')}")]

    before = {(i.kind, i.bb_id): i for i in old[1]}
    changes = []
    for item in items:
        previous = before.get((item.kind, item.bb_id))
        if item.kind == "announcement" and previous is None:
            changes.append(Change("added", f"New announcement · {item.course}: {item.title}"))
        elif item.kind == "assignment" and previous is None:
            due = f", due {when(item.due_at)}" if item.due_at else ""
            changes.append(Change("added", f"New assignment · {item.course}: {item.title}{due}"))
        elif item.kind == "assignment":
            if item.due_at and previous.due_at and item.due_at != previous.due_at:
                changes.append(Change("changed", f"Due date changed · {item.course}, {item.title}: "
                                                 f"{when(previous.due_at)} → {when(item.due_at)}"))
            elif item.due_at and previous.due_at is None:
                changes.append(Change("changed", f"Due date set · {item.course}, {item.title}: {when(item.due_at)}"))
            if item.status == "graded" and (previous.status != "graded" or previous.score != item.score):
                changes.append(Change("changed", f"New grade · {item.course}, {item.title}: {_grade(item)}"))
        elif item.kind == "material" and previous is None and item.material_kind != "folder":
            changes.append(Change("added", f"New material · {item.course}: {item.title}"))
    return changes
```

- [ ] **Step 7: Save the section**

In `app/school/services/ingest.py`:
- Extend the models import with `SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse, SchoolBbMaterial` and the changes import with `BbItem, blackboard_changes`.
- Add before `SAVERS`:

```python
def _bb_items(courses):
    """[BbItem] from Blackboard rows or from the shared-format courses."""
    items = []
    for course in courses:
        for a in course.announcements:
            items.append(BbItem("announcement", course.name, a.bb_id, a.title))
        for a in course.assignments:
            due = a.due_at if a.due_at is None or a.due_at.tzinfo is None else to_utc(a.due_at)
            items.append(BbItem("assignment", course.name, a.bb_id, a.name, due_at=due, status=a.status,
                                score=a.score, points_possible=a.points_possible, grade_text=a.grade_text))
        for m in course.materials:
            items.append(BbItem("material", course.name, m.bb_id, m.title, material_kind=m.kind))
    return items


def _optional_utc(moment):
    return None if moment is None else to_utc(moment)


def _save_blackboard(user_id, blackboard, now):
    old_courses = db.session.execute(select(SchoolBbCourse).filter_by(user_id=user_id)).scalars().all()
    old = ([c.name for c in old_courses], _bb_items(old_courses)) if old_courses else None
    new = ([c.name for c in blackboard.courses], _bb_items(blackboard.courses))

    mine = select(SchoolBbCourse.id).filter_by(user_id=user_id)
    for model in (SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbMaterial):
        db.session.execute(delete(model).where(model.course_id.in_(mine)))
    db.session.execute(delete(SchoolBbCourse).filter_by(user_id=user_id))
    for course in blackboard.courses:
        row = SchoolBbCourse(user_id=user_id, bb_id=course.bb_id, course_code=course.course_code,
                             name=course.name, url=course.url)
        row.announcements = [SchoolBbAnnouncement(user_id=user_id, bb_id=a.bb_id, title=a.title, text=a.text,
                                                  posted_at=_optional_utc(a.posted_at), url=a.url)
                             for a in course.announcements]
        row.assignments = [SchoolBbAssignment(user_id=user_id, bb_id=a.bb_id, name=a.name,
                                              due_at=_optional_utc(a.due_at), points_possible=a.points_possible,
                                              score=a.score, grade_text=a.grade_text, status=a.status,
                                              feedback=a.feedback, url=a.url)
                           for a in course.assignments]
        row.materials = [SchoolBbMaterial(user_id=user_id, bb_id=m.bb_id, title=m.title, kind=m.kind, path=m.path,
                                          created_at=_optional_utc(m.created_at), url=m.url)
                         for m in course.materials]
        db.session.add(row)
    db.session.flush()
    return blackboard_changes(old, new)
```

- Add `"blackboard": _save_blackboard` to `SAVERS`.

- [ ] **Step 8: Run all tests**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (including `test_migrations`, which proves the migration matches the models).

- [ ] **Step 9: Commit**

```bash
git add app/school/models.py app/school/services/ingest.py app/school/services/changes.py migrations/versions tests/helpers.py tests/test_contract.py tests/test_school_changes.py tests/test_school_blackboard_ingest.py
git commit -m "feat(school): store Blackboard data and report what changed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Server: one status line per system

**Files:**
- Modify: `app/school/services/sync_status.py`, `app/school/routes.py` (index), `app/templates/school/_status_card.html`, `tests/test_school_sync_status.py`, `tests/test_school_pages.py`

**Interfaces:**
- Consumes: `RunInfo` (existing).
- Produces: `sync_status.SystemLine(name, state, text)`, `sync_status.system_lines(runs: list[RunInfo], now) -> list[SystemLine]`; `describe()` uses Blackboard wording when the failing part is `blackboard`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_school_sync_status.py`:

```python
from app.school.services.sync_status import system_lines

OK = {"status": "ok"}


def bad(code):
    return {"status": "failed", "error_code": code, "error_message": "x"}


def edu(**parts):
    return {"timetable": parts.get("timetable", OK), "exams": parts.get("exams", OK), "tuition": parts.get("tuition", OK)}


def test_one_line_per_system_from_the_latest_run_that_included_it():
    runs = [run("partial", sections={**edu(), "blackboard": bad("bad_credentials")})]

    lines = system_lines(runs, NOW)

    assert [(l.name, l.state) for l in lines] == [("EduSoft", "ok"), ("Blackboard", "paused")]
    assert lines[0].text == "synced at 14:05"
    assert "sla-agent setup --blackboard" in lines[1].text


def test_a_system_never_synced_has_no_line():
    assert [l.name for l in system_lines([run("success", sections=edu())], NOW)] == ["EduSoft"]


def test_a_part_failure_is_shown_as_partly_synced():
    [line] = system_lines([run("partial", sections=edu(tuition=bad("edusoft_changed")))], NOW)

    assert (line.state, line.text) == ("partial", "synced at 14:05, but couldn't read: tuition")


def test_blackboard_failure_headline_names_blackboard():
    result = status(latest=run("failed", sections={"blackboard": bad("bad_credentials")}))

    assert result.state == "paused"
    assert "Blackboard" in result.headline
    assert "sla-agent setup --blackboard" in result.detail
```

Append to `tests/test_school_pages.py`:

```python
def test_school_home_shows_a_line_per_system(app, browser):
    _, key = add_device(browser)
    client = app.test_client()
    run_id = api(client, "POST", "/runs", key, json={"trigger": "scheduled"}).get_json()["run_id"]
    from tests.helpers import full_payload
    payload = full_payload()
    payload["blackboard"] = {"status": "failed", "error_code": "bad_credentials", "error_message": "rejected"}
    api(client, "POST", f"/runs/{run_id}/finish", key, json=payload)

    page = browser.get("/school/").get_data(as_text=True)

    assert "EduSoft" in page and "Blackboard" in page
    assert "sla-agent setup --blackboard" in page
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_sync_status.py tests/test_school_pages.py -q`
Expected: `ImportError: cannot import name 'system_lines'`.

- [ ] **Step 3: Implement**

In `app/school/services/sync_status.py`:
- Add after `PROBLEMS`:

```python
BLACKBOARD_PROBLEMS = {
    "bad_credentials": ("paused", "Paused: Blackboard rejected your username or password",
                        "Run `sla-agent setup --blackboard` on your laptop to enter them again."),
    "extra_verification": ("paused", "Paused: Blackboard asked for extra verification",
                           "Automatic Blackboard sync can't pass a CAPTCHA, code or Microsoft sign-in."),
    "network": ("failed", "Sync failed: Blackboard couldn't be reached", RETRY),
    "session_expired": ("failed", "Sync failed: Blackboard ended the session", RETRY),
    "source_changed": ("failed", "Sync failed: Blackboard's data format has changed",
                       "sla-agent needs an update to read it."),
}
PART_NAMES["blackboard"] = "Blackboard"

SYSTEMS = (("EduSoft", ("timetable", "exams", "tuition")), ("Blackboard", ("blackboard",)))
PAUSE_HINTS = {
    ("EduSoft", "bad_credentials"): "paused: wrong student ID or password. Run `sla-agent setup`.",
    ("Blackboard", "bad_credentials"): "paused: wrong username or password. Run `sla-agent setup --blackboard`.",
    ("EduSoft", "extra_verification"): "paused: asked for extra verification (CAPTCHA or code).",
    ("Blackboard", "extra_verification"): "paused: asked for extra verification (CAPTCHA, code or Microsoft sign-in).",
}
FAILURE_HINTS = {
    "network": "couldn't be reached; it will be tried again automatically.",
    "session_expired": "ended the session; it will be tried again automatically.",
    "edusoft_changed": "its pages changed; sla-agent needs an update.",
    "source_changed": "its data format changed; sla-agent needs an update.",
}


class SystemLine(NamedTuple):
    name: str
    state: str  # ok / partial / failed / paused
    text: str


def system_lines(runs, now):
    """One line per system, from the newest finished run that included it (runs newest first)."""
    lines = []
    for name, parts in SYSTEMS:
        run = next((r for r in runs if r.status != "running" and any(p in (r.sections or {}) for p in parts)), None)
        if run is None:
            continue
        results = {p: r for p, r in run.sections.items() if p in parts}
        failed = [p for p, r in results.items() if r["status"] == "failed"]
        if not failed:
            lines.append(SystemLine(name, "ok", f"synced {_at(run.finished_at, now)}"))
            continue
        code = results[failed[0]].get("error_code")
        if (name, code) in PAUSE_HINTS:
            lines.append(SystemLine(name, "paused", PAUSE_HINTS[(name, code)]))
        elif len(failed) < len(results):
            names = ", ".join(PART_NAMES.get(p, p) for p in failed)
            lines.append(SystemLine(name, "partial", f"synced {_at(run.finished_at, now)}, but couldn't read: {names}"))
        else:
            lines.append(SystemLine(name, "failed", FAILURE_HINTS.get(code, "sync failed; it will be tried again automatically.")))
    return lines
```

- In `describe`, replace the block

```python
        if code is None:
            failed = _failed_parts(latest.sections)
            code = latest.sections[failed[0]]["error_code"] if failed else None
        return make(*PROBLEMS.get(code, UNKNOWN))
```

with

```python
        problems = PROBLEMS
        if code is None:
            failed = _failed_parts(latest.sections)
            code = latest.sections[failed[0]]["error_code"] if failed else None
            if failed and failed[0] == "blackboard":
                problems = BLACKBOARD_PROBLEMS
        return make(*problems.get(code, UNKNOWN))
```

In `app/school/routes.py` `index()`:
- Import `system_lines` next to `RunInfo, describe`, and `SchoolSyncRun` in the models import.
- Before `return render_template(...)`, add:

```python
    recent = db.session.execute(
        select(SchoolSyncRun).filter_by(user_id=current_user.id)
        .order_by(SchoolSyncRun.started_at.desc(), SchoolSyncRun.id.desc()).limit(10)
    ).scalars().all()
    lines = system_lines([RunInfo(r.status, r.started_at, r.finished_at, r.error_code, r.error_message, r.sections)
                          for r in recent], now)
```

and pass `system_lines=lines` to `render_template`.

In `app/templates/school/_status_card.html`, after the detail paragraph, add:

```html
  {% if system_lines %}
    <ul class="system-lines">
      {% for line in system_lines %}
        <li class="system-{{ line.state }}"><strong>{{ line.name }}:</strong> {{ line.text }}</li>
      {% endfor %}
    </ul>
  {% endif %}
```

Append to `app/static/css/style.css`:

```css
.system-lines { list-style: none; margin: 0 0 8px; padding: 0; }
.system-lines li { margin: 2px 0; }
.system-paused, .system-partial { color: #c77700; }
.system-failed { color: var(--error); }
```

- [ ] **Step 4: Run all tests**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/school/services/sync_status.py app/school/routes.py app/templates/school/_status_card.html app/static/css/style.css tests/test_school_sync_status.py tests/test_school_pages.py
git commit -m "feat(school): sync status line per system (EduSoft, Blackboard)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Pages: Courses, Overview boxes and deadlines in the calendar

**Files:**
- Modify: `app/school/services/schedule.py`, `app/school/routes.py`, `app/templates/school/_subnav.html`, `app/templates/school/index.html`, `app/templates/school/timetable.html`, `app/static/js/timetable.js`, `app/static/css/style.css`
- Create: `app/templates/school/courses.html`, `app/templates/school/course.html`, `tests/test_school_blackboard_pages.py`

**Interfaces:**
- Consumes: Blackboard models (Task 8).
- Produces: routes `school.courses` (`GET /school/courses`), `school.course` (`GET /school/courses/<int:course_id>`); `schedule.deadlines_between(user_id, start_utc, end_utc) -> list[SchoolBbAssignment]`; calendar feed entries with `"allDay": True`, `"classNames": ["event-due"]`, `extendedProps.kind == "due"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_school_blackboard_pages.py`:

```python
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from app.extensions import db
from app.school.models import SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse, SchoolBbMaterial
from tests.helpers import make_user, register

BB = "https://blackboard.hcmiu.edu.vn/x"


@pytest.fixture
def browser(app):
    client = app.test_client()
    register(client)  # user 1
    return client


def add_course(app, user_id, name="Web Application Development", assignments=(), announcements=(), materials=()):
    with app.app_context():
        course = SchoolBbCourse(user_id=user_id, bb_id=f"_{name[:3]}_1", course_code="IT093IU", name=name, url=BB)
        course.assignments = [SchoolBbAssignment(user_id=user_id, url=BB, **a) for a in assignments]
        course.announcements = [SchoolBbAnnouncement(user_id=user_id, url=BB, **a) for a in announcements]
        course.materials = [SchoolBbMaterial(user_id=user_id, url=BB, **m) for m in materials]
        db.session.add(course)
        db.session.commit()
        return course.id


def page(browser, url):
    response = browser.get(url)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_the_courses_page_lists_only_my_courses(app, browser):
    add_course(app, 1)
    add_course(app, make_user(app, email="binh@example.com"), name="Binh's Course")

    html = page(browser, "/school/courses")

    assert "Web Application Development" in html
    assert "Binh" not in html


def test_someone_elses_course_page_is_404(app, browser):
    other = add_course(app, make_user(app, email="binh@example.com"), name="Binh's Course")

    assert browser.get(f"/school/courses/{other}").status_code == 404


def test_the_course_page_shows_all_four_parts_with_escaped_text(app, browser):
    course_id = add_course(
        app, 1,
        announcements=[{"bb_id": "a1", "title": "Heads up", "text": "<script>alert(1)</script> No class Thursday",
                        "posted_at": datetime(2026, 9, 28, 2, 0)}],
        assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "graded",
                      "score": 8.5, "points_possible": 10.0, "feedback": "Good work"}],
        materials=[{"bb_id": "m1", "title": "Week 5 slides.pdf", "kind": "file", "path": "Week 5",
                    "created_at": datetime(2026, 9, 28, 1, 0)}],
    )

    html = page(browser, f"/school/courses/{course_id}")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    for text in ("Heads up", "Lab 3", "Fri 02/10 23:59", "8.5/10", "Good work", "Week 5 slides.pdf"):
        assert text in html
    links = BeautifulSoup(html, "html.parser").find_all("a", string=lambda s: s and "Open in Blackboard" in s)
    assert links and all(l["target"] == "_blank" and "noopener" in l["rel"] for l in links)


def test_a_deadline_at_2359_vietnam_time_is_in_the_calendar_on_that_day(app, browser):
    add_course(app, 1, assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59),
                                     "status": "not_graded"}])

    events = browser.get("/school/api/calendar", query_string={"start": "2026-09-28", "end": "2026-10-05"}).get_json()

    [due] = [e for e in events if e["extendedProps"]["kind"] == "due"]
    assert (due["start"], due["allDay"], due["classNames"]) == ("2026-10-02", True, ["event-due"])
    assert due["title"] == "Due 23:59: Lab 3 · Web Application Development"


def test_a_deadline_just_after_midnight_belongs_to_the_next_vietnam_day(app, browser):
    # Sat 03/10 00:30 in Vietnam is still Fri 02/10 17:30 in UTC.
    add_course(app, 1, assignments=[{"bb_id": "x1", "name": "Quiz", "due_at": datetime(2026, 10, 2, 17, 30),
                                     "status": "not_graded"}])

    events = browser.get("/school/api/calendar", query_string={"start": "2026-09-28", "end": "2026-10-05"}).get_json()

    assert [e["start"] for e in events if e["extendedProps"]["kind"] == "due"] == ["2026-10-03"]


def test_overview_shows_due_soon_and_latest_announcements(app, browser, monkeypatch):
    add_course(app, 1,
               assignments=[{"bb_id": "x1", "name": "Lab 3", "due_at": datetime(2026, 10, 2, 16, 59), "status": "not_graded"},
                            {"bb_id": "x2", "name": "Far away", "due_at": datetime(2026, 11, 30, 16, 59), "status": "not_graded"}],
               announcements=[{"bb_id": f"a{i}", "title": f"Note {i}", "text": "t", "posted_at": datetime(2026, 9, 20 + i, 2, 0)}
                              for i in range(5)])
    monkeypatch.setattr("app.school.routes.utcnow", lambda: datetime(2026, 9, 29, 0, 30))

    html = page(browser, "/school/")

    assert "Due soon" in html and "Lab 3" in html and "Far away" not in html
    assert "Note 4" in html and "Note 2" in html and "Note 1" not in html  # the 3 newest
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_school_blackboard_pages.py -q`
Expected: failures (404 for `/school/courses`; no due events).

- [ ] **Step 3: Implement queries and routes**

In `app/school/services/schedule.py`, add `SchoolBbAssignment` to the existing `from app.school.models import ...` line, then append:

```python
def deadlines_between(user_id, start_utc, end_utc):
    """Blackboard deadlines in [start_utc, end_utc), soonest first."""
    return db.session.execute(
        select(SchoolBbAssignment).where(
            SchoolBbAssignment.user_id == user_id,
            SchoolBbAssignment.due_at >= start_utc,
            SchoolBbAssignment.due_at < end_utc,
        ).order_by(SchoolBbAssignment.due_at)
    ).scalars().all()
```

In `app/school/routes.py`:
- Extend the models import with `SchoolBbAnnouncement, SchoolBbAssignment, SchoolBbCourse`.
- Add a filter:

```python
@bp.app_template_filter("score")
def score(value):
    return f"{value:g}"
```

- In `calendar_feed()`, replace the final `return jsonify(...)` with:

```python
    events = [_calendar_event(item) for item in items]
    for deadline in schedule.deadlines_between(current_user.id, schedule.day_start_utc(start), schedule.day_start_utc(end)):
        events.append({
            "title": f"Due {vn_clock(deadline.due_at)}: {deadline.name} · {deadline.course.name}",
            "start": schedule.vietnam_date(deadline.due_at).isoformat(),
            "allDay": True,
            "classNames": ["event-due"],
            "extendedProps": {"kind": "due", "code": deadline.course.course_code, "room": None},
        })
    return jsonify(events)
```

- In `index()`, before `return render_template(...)`, add:

```python
    due_soon = db.session.execute(
        select(SchoolBbAssignment).filter_by(user_id=current_user.id)
        .where(SchoolBbAssignment.due_at >= now, SchoolBbAssignment.due_at < now + timedelta(days=7))
        .order_by(SchoolBbAssignment.due_at)
    ).scalars().all()
    latest_announcements = db.session.execute(
        select(SchoolBbAnnouncement).filter_by(user_id=current_user.id)
        .order_by(SchoolBbAnnouncement.posted_at.desc(), SchoolBbAnnouncement.id.desc()).limit(3)
    ).scalars().all()
```

and pass `due_soon=due_soon, latest_announcements=latest_announcements` to `render_template`.

- Add the pages:

```python
@bp.get("/courses")
@login_required
def courses():
    rows = db.session.execute(
        select(SchoolBbCourse).filter_by(user_id=current_user.id).order_by(SchoolBbCourse.name)
    ).scalars().all()
    return render_template("school/courses.html", courses=rows)


@bp.get("/courses/<int:course_id>")
@login_required
def course(course_id):
    row = db.first_or_404(select(SchoolBbCourse).filter_by(id=course_id, user_id=current_user.id))
    far_future = datetime.max
    return render_template(
        "school/course.html",
        course=row,
        announcements=sorted(row.announcements, key=lambda a: a.posted_at or datetime.min, reverse=True),
        assignments=sorted(row.assignments, key=lambda a: a.due_at or far_future),
        materials=sorted(row.materials, key=lambda m: m.created_at or datetime.min, reverse=True),
        now=utcnow(),
    )
```

Add `datetime` to the `from datetime import date, timedelta` import.

- [ ] **Step 4: Implement the templates**

Replace the `school_pages` list in `app/templates/school/_subnav.html` with:

```html
{% set school_pages = [
  ("school.index", "Overview"),
  ("school.timetable", "Timetable"),
  ("school.courses", "Courses"),
  ("school.exams", "Exams"),
  ("school.tuition", "Tuition"),
  ("school.devices", "Devices"),
] %}
```

Create `app/templates/school/courses.html`:

```html
{% extends "base.html" %}
{% block title %}Courses · School-Life-Assistant{% endblock %}
{% block content %}
  <h1>Courses</h1>
  {% include "school/_subnav.html" %}
  {% if courses %}
    <div class="module-grid">
      {% for course in courses %}
        <a class="card module-card" href="{{ url_for('school.course', course_id=course.id) }}">
          <h2>{{ course.name }}</h2>
          <p class="muted">{{ course.course_code or "" }} · {{ course.announcements | length }} announcements ·
             {{ course.assignments | length }} assignments</p>
        </a>
      {% endfor %}
    </div>
  {% else %}
    <section class="card"><p>No Blackboard courses yet. Set up Blackboard on your laptop with
      <code>sla-agent setup --blackboard</code>; your courses appear after the next sync.</p></section>
  {% endif %}
{% endblock %}
```

Create `app/templates/school/course.html`:

```html
{% extends "base.html" %}
{% block title %}{{ course.name }} · School-Life-Assistant{% endblock %}
{% macro bb_link(url) %}<a href="{{ url }}" target="_blank" rel="noopener noreferrer">Open in Blackboard ↗</a>{% endmacro %}
{% block content %}
  <h1>{{ course.name }}</h1>
  {% include "school/_subnav.html" %}
  <p>{{ bb_link(course.url) }}</p>

  <section class="card">
    <h2>Announcements</h2>
    {% for a in announcements %}
      <article class="bb-item">
        <h3>{{ a.title }}</h3>
        <p class="muted">{{ a.posted_at | vn_time if a.posted_at else "" }}</p>
        <p class="bb-text">{{ a.text }}</p>
        <p>{{ bb_link(a.url) }}</p>
      </article>
    {% else %}
      <p class="muted">No announcements.</p>
    {% endfor %}
  </section>

  <section class="card">
    <h2>Assignments &amp; grades</h2>
    {% for a in assignments %}
      <article class="bb-item{% if a.due_at and a.due_at < now and a.status == 'not_graded' %} is-overdue{% endif %}">
        <h3>{{ a.name }}</h3>
        <p>
          {% if a.due_at %}Due {{ a.due_at | vn_time }}{% if a.due_at < now and a.status == 'not_graded' %} <span class="badge badge-warning">Overdue</span>{% endif %}{% else %}No due date{% endif %}
          · {% if a.status == "graded" %}Grade: <strong>{% if a.score is not none and a.points_possible %}{{ a.score | score }}/{{ a.points_possible | score }}{% elif a.score is not none %}{{ a.score | score }}{% else %}{{ a.grade_text or "graded" }}{% endif %}</strong>
            {% elif a.status == "needs_grading" %}Submitted, waiting for a grade
            {% elif a.status == "exempt" %}Exempt
            {% else %}Not graded yet{% endif %}
        </p>
        {% if a.feedback %}<p class="bb-text muted">Feedback: {{ a.feedback }}</p>{% endif %}
        <p>{{ bb_link(a.url) }}</p>
      </article>
    {% else %}
      <p class="muted">No assignments.</p>
    {% endfor %}
  </section>

  <section class="card">
    <h2>Materials</h2>
    {% if materials %}
      <ul class="bb-materials">
        {% for m in materials %}
          <li>
            <strong>{{ m.title }}</strong>
            <span class="muted">{{ m.kind }}{% if m.path %} · {{ m.path }}{% endif %}{% if m.created_at %} · added {{ m.created_at | vn_date }}{% endif %}</span>
            · {{ bb_link(m.url) }}
          </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="muted">No materials.</p>
    {% endif %}
  </section>
{% endblock %}
```

In `app/templates/school/index.html`, inside the second `<section class="card">` (before `<h2>Next exam</h2>`), add:

```html
      <h2>Due soon</h2>
      {% if due_soon %}
        <ul class="items">
          {% for a in due_soon %}
            <li class="item item-due">
              <span class="item-time">{{ a.due_at | vn_time }}</span>
              <span class="item-title">{{ a.name }}</span>
              <span class="item-meta">{{ a.course.name }}</span>
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="muted">Nothing due in the next 7 days.</p>
      {% endif %}

      <h2>Latest announcements</h2>
      {% if latest_announcements %}
        <ul class="changes">
          {% for a in latest_announcements %}
            <li><a href="{{ url_for('school.course', course_id=a.course_id) }}">{{ a.course.name }}</a>: {{ a.title }}
                <span class="muted">{{ a.text[:120] }}{% if a.text | length > 120 %}…{% endif %}</span></li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="muted">No announcements yet.</p>
      {% endif %}
```

In `app/templates/school/timetable.html`, add after the Exam legend item: `<span class="legend-item legend-due">Deadline</span>`.

In `app/static/js/timetable.js`, change `allDaySlot: false,` to:

```javascript
    allDaySlot: true,
    allDayText: "Due",
```

Append to `app/static/css/style.css`:

```css
/* School: Blackboard */
:root { --due-color: #c77700; }
@media (prefers-color-scheme: dark) { :root { --due-color: #e0a040; } }
.legend-due::before { background: var(--due-color); }
.fc .event-due { background: var(--due-color); border-color: var(--due-color); color: #fff; }
.fc .fc-list-event.event-due { background: transparent; color: var(--text); }
.fc .fc-list-event.event-due .fc-list-event-dot { border-color: var(--due-color); }
.item-due { border-left-color: var(--due-color); }
.bb-item { padding: 10px 0; border-top: 1px solid var(--border); }
.bb-item:first-of-type { border-top: 0; }
.bb-item h3 { margin: 0 0 4px; font-size: 1rem; }
.bb-item p { margin: 4px 0; }
.bb-text { white-space: pre-line; }
.bb-item.is-overdue h3 { color: var(--error); }
.badge-warning { background: var(--due-color); }
.bb-materials { margin: 0; padding-left: 18px; }
.bb-materials li { margin-bottom: 6px; }
```

- [ ] **Step 5: Run all tests**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/school/services/schedule.py app/school/routes.py app/templates/school app/static/js/timetable.js app/static/css/style.css tests/test_school_blackboard_pages.py
git commit -m "feat(school): Courses pages, Due soon and announcements on Overview, deadlines in the calendar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: End to end, browser check and docs

**Files:**
- Modify: `README.md`, `docs/superpowers/specs/2026-09-26-blackboard-design.md`

- [ ] **Step 1: Real sync**

With the student's `flask run --debug` window running on port 5000, run `.venv/Scripts/sla-agent.exe sync-now`.
Expected: "Sync finished." Then check the database:

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
from dotenv import dotenv_values; from sqlalchemy import create_engine, text
with create_engine(dotenv_values('.env')['DATABASE_URL']).connect() as c:
    print(c.execute(text('SELECT status, sections FROM school_sync_runs ORDER BY id DESC LIMIT 1')).one())
    for t in ('school_bb_courses','school_bb_announcements','school_bb_assignments','school_bb_materials'):
        print(t, c.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar())"
```
Expected: status `success`, `blackboard: ok`, 8 courses and non-zero counts where the student's courses have items.

- [ ] **Step 2: Browser check**

Seed a scratch SQLite database with the anonymized fixtures (the same approach as the calendar check: `create_app` with `DATABASE_URL=sqlite:///<scratch>`, `finish_run` with `read_blackboard(Replay(), REGISTERED)` from `agent/tests/test_blackboard_samples.py`), run `flask run --port 5059`, and use the scratch Playwright environment with Edge to screenshot `/school/`, `/school/courses`, one course page and `/school/timetable` at 1400×1000 and 390×844. Look at every screenshot; the only allowed console error is the missing `/favicon.ico`.

- [ ] **Step 3: Docs**

In `README.md`, under "Everyday commands", add a row:

```markdown
| Set up or change the Blackboard login | `sla-agent setup --blackboard` |
```

In `docs/superpowers/specs/2026-09-26-blackboard-design.md`, change the status line to `**Status:** Built (see docs/superpowers/plans/2026-09-26-blackboard.md)`.

- [ ] **Step 4: Full verification and commit**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

```bash
git add README.md docs/superpowers/specs/2026-09-26-blackboard-design.md
git commit -m "docs: Blackboard setup and spec status" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
