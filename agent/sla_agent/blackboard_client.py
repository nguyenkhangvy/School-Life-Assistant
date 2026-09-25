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
