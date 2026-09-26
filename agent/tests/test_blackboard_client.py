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


# After the password is sent, only a login that didn't work is checked for a verification step:
# the home page shows lecturers' announcements and images, whose names can contain "otp".

@responses.activate
def test_a_home_page_with_otp_in_an_image_name_is_not_taken_for_verification():
    responses.get(LOGIN_URL, body=LOGIN_PAGE)
    responses.post(LOGIN_URL, body=HOME_PAGE.replace("</body>", '<img src="/bbcswebdav/footprint.png"></body>'))
    responses.get(f"{API}/v1/users/me", json=ME)
    client = BlackboardClient()

    client.login("student", "bb-s3cret")

    assert client.user_id == "_77_1"


@responses.activate
def test_a_code_step_after_the_password_pauses():
    responses.get(LOGIN_URL, body=LOGIN_PAGE)
    responses.post(LOGIN_URL, body="<html><body><input name='otp' type='text'></body></html>")
    responses.get(f"{API}/v1/users/me", status=401)

    with pytest.raises(ExtraVerification):
        BlackboardClient().login("student", "bb-s3cret")


@responses.activate
def test_a_rejection_page_without_the_login_form_counts_as_a_wrong_password():
    # "Session expired" would be retried at the next sync; a wrong password must not be.
    responses.get(LOGIN_URL, body=LOGIN_PAGE)
    responses.post(LOGIN_URL, body="<html><body>Access denied.</body></html>")
    responses.get(f"{API}/v1/users/me", status=401)

    with pytest.raises(BadCredentials):
        BlackboardClient().login("student", "wrong")

    assert len(posts()) == 1
