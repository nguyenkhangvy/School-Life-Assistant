"""Talks to EduSoft Web: log in, read pages. Reads only; never changes anything there.

Safety rules:
- only https://edusoftweb.hcmiu.edu.vn; redirects elsewhere are refused
- an honest user agent that names this app
- a CAPTCHA, one-time code or Microsoft sign-in stops the login (never bypassed)
- the login form is submitted once; a rejected password is never retried
"""

import logging
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from sla_agent.errors import (
    BadCredentials,
    ExtraVerification,
    NetworkError,
    ParseError,
    SessionExpired,
    UnexpectedRedirect,
)

log = logging.getLogger(__name__)

HOST = "edusoftweb.hcmiu.edu.vn"
BASE_URL = f"https://{HOST}/"
LOGIN_URL = f"{BASE_URL}default.aspx?page=dangnhap"
USER_AGENT = "SchoolLifeAssistant/0.1 (IU student project)"
TIMEOUT_SECONDS = 20
RETRY_WAITS = (5, 30)  # seconds to wait before the 2nd and 3rd try
MAX_REDIRECTS = 5

USERNAME_FIELD = "ctl00$ContentPlaceHolder1$ctl00$txtTaiKhoa"
PASSWORD_FIELD = "ctl00$ContentPlaceHolder1$ctl00$txtMatKhau"
SUBMIT_FIELD = "ctl00$ContentPlaceHolder1$ctl00$btnDangNhap"

# EduSoft page names (default.aspx?page=...), confirmed with real pages on 2026-09-25.
PAGES = {
    "home": "gioithieu",
    "timetable": "thoikhoabieu",
    "exams": "xemlichthi",  # final exams
    "midterm_exams": "xemlichthigk",
    "tuition": "xemhocphi",
}

# Form fields used to switch views (reading only; nothing is changed on EduSoft).
TIMETABLE_TERM_FIELD = "ctl00$ContentPlaceHolder1$ctl00$ddlChonNHHK"
TIMETABLE_VIEW_FIELD = "ctl00$ContentPlaceHolder1$ctl00$ddlLoai"
SEMESTER_VIEW = "1"  # "TKB học kỳ cá nhân": every course of the semester, not just this week
FINAL_EXAM_TERM_FIELD = "ctl00$ContentPlaceHolder1$ctl00$dropNHHK"

VERIFICATION_HINTS = ("captcha", "recaptcha", "otp", "maxacnhan", "xacthuc")
MICROSOFT_HOSTS = ("login.microsoftonline.com", "login.live.com", "login.windows.net")


def _has_login_form(soup):
    return soup.find("input", attrs={"name": USERNAME_FIELD}) is not None


def _asks_for_verification(soup):
    for tag in soup.find_all(["input", "img", "div", "iframe"]):
        text = " ".join(
            str(tag.get(attr, "")) for attr in ("name", "id", "src", "class")
        ).lower()
        if any(hint in text for hint in VERIFICATION_HINTS):
            return True
    return False


def _selected(html, field):
    """(selected value, all values) of a dropdown in the page."""
    select = BeautifulSoup(html, "html.parser").find("select", attrs={"name": field})
    if select is None:
        return None, []
    options = select.find_all("option")
    chosen = select.find("option", selected=True) or (options[0] if options else None)
    return (chosen.get("value") if chosen else None), [o.get("value") for o in options]


def _form_fields(html):
    """What a browser would send back: hidden fields and each dropdown's current choice."""
    form = BeautifulSoup(html, "html.parser").find("form")
    if form is None:
        raise ParseError("EduSoft's page has no form to switch views with.")
    fields = {tag["name"]: tag.get("value", "") for tag in form.find_all("input", attrs={"type": "hidden"})
              if tag.get("name")}
    for select in form.find_all("select"):
        if select.get("name"):
            chosen = select.find("option", selected=True) or select.find("option")
            fields[select["name"]] = chosen.get("value", "") if chosen else ""
    return fields


class EduSoftClient:
    def __init__(self, session=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.current_term = None  # e.g. "20261", learned from the timetable page

    # ---- HTTP with safety checks ------------------------------------------

    def _safe_url(self, url):
        parts = urlsplit(url)
        if parts.hostname in MICROSOFT_HOSTS:
            raise ExtraVerification("EduSoft sent the login to Microsoft sign-in.")
        if parts.hostname != HOST:
            raise UnexpectedRedirect(f"EduSoft tried to redirect to {parts.hostname}; not followed.")
        # Same site over plain http: go over https instead, never send anything unencrypted.
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))

    def _request(self, method, url, data=None):
        """One request, following redirects by hand so every hop is checked."""
        url = self._safe_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            try:
                response = self.session.request(
                    method, url, data=data, timeout=TIMEOUT_SECONDS, allow_redirects=False
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                raise NetworkError(f"EduSoft couldn't be reached ({error.__class__.__name__}).") from None
            if response.status_code >= 500:
                raise NetworkError(f"EduSoft answered with HTTP {response.status_code}.")
            if response.is_redirect:
                url = self._safe_url(urljoin(url, response.headers["Location"]))
                method, data = "GET", None
                continue
            response.encoding = response.encoding or "utf-8"
            return response
        raise NetworkError("EduSoft redirected too many times.")

    def _get_with_retries(self, url):
        for wait in (*RETRY_WAITS, None):
            try:
                return self._request("GET", url)
            except NetworkError:
                if wait is None:
                    raise
                log.info("EduSoft not reachable, trying again in %s s", wait)
                self.sleep(wait)

    # ---- Public API --------------------------------------------------------

    def login(self, student_id, password):
        login_page = BeautifulSoup(self._get_with_retries(LOGIN_URL).text, "html.parser")
        if _asks_for_verification(login_page):
            raise ExtraVerification("EduSoft's login page asks for extra verification.")
        form = login_page.find("form")
        if form is None or not _has_login_form(login_page):
            raise NetworkError("EduSoft's login page didn't load correctly.")

        # Send every hidden field, empty ones too, exactly like a browser does.
        fields = {
            tag["name"]: tag.get("value", "")
            for tag in form.find_all("input", attrs={"type": "hidden"})
            if tag.get("name")
        }
        submit = login_page.find("input", attrs={"name": SUBMIT_FIELD})
        fields.update({
            USERNAME_FIELD: student_id,
            PASSWORD_FIELD: password,
            SUBMIT_FIELD: submit.get("value", "") if submit else "",
        })
        action = urljoin(LOGIN_URL, form.get("action") or LOGIN_URL)

        # Submitted once. No retry here: a retry could count as a second failed login.
        result = BeautifulSoup(self._request("POST", action, data=fields).text, "html.parser")
        if _asks_for_verification(result):
            raise ExtraVerification("EduSoft asked for extra verification after login.")
        if _has_login_form(result):
            raise BadCredentials("EduSoft rejected the student ID or password.")
        log.info("Logged in to EduSoft")

    def _page_url(self, name):
        return f"{BASE_URL}default.aspx?page={PAGES[name]}"

    @staticmethod
    def _logged_in(html):
        if _has_login_form(BeautifulSoup(html, "html.parser")):
            raise SessionExpired("EduSoft showed the login form instead of the page.")
        return html

    def get_page(self, name):
        return self._logged_in(self._get_with_retries(self._page_url(name)).text)

    def switch_view(self, name, html, field, value):
        """Send the page's form back with one dropdown changed, as choosing it in a browser does."""
        fields = _form_fields(html)
        fields.update({field: value, "__EVENTTARGET": field, "__EVENTARGUMENT": ""})
        return self._logged_in(self._request("POST", self._page_url(name), data=fields).text)

    def read(self, section):
        """All pages one section needs, for its reader in sla_agent.parsers."""
        if section == "timetable":
            weekly = self.get_page("timetable")
            self.current_term = _selected(weekly, TIMETABLE_TERM_FIELD)[0]
            semester = self.switch_view("timetable", weekly, TIMETABLE_VIEW_FIELD, SEMESTER_VIEW)
            return {"weekly": weekly, "semester": semester}
        if section == "exams":
            if self.current_term is None:
                self.current_term = _selected(self.get_page("timetable"), TIMETABLE_TERM_FIELD)[0]
            final = self.get_page("exams")
            shown, listed = _selected(final, FINAL_EXAM_TERM_FIELD)
            if shown != self.current_term and self.current_term in listed:
                final = self.switch_view("exams", final, FINAL_EXAM_TERM_FIELD, self.current_term)
            return {"term": self.current_term, "final": final, "midterm": self.get_page("midterm_exams")}
        if section == "tuition":
            return {"tuition": self.get_page("tuition")}
        raise KeyError(section)
