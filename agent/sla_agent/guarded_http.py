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
