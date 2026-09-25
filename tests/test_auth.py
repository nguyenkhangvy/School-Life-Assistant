import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.extensions import db
from tests.helpers import login, logout, register


def test_register_stores_only_a_password_hash_and_logs_the_user_in(app, client):
    response = register(client, email="an@example.com", password="correct-horse")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with app.app_context():
        user = db.session.execute(select(User)).scalar_one()
        assert user.email == "an@example.com"
        assert "correct-horse" not in user.password_hash
        assert user.check_password("correct-horse")
    assert client.get("/").status_code == 200


def test_dashboard_sends_anonymous_visitors_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login?next=%2F"


def test_login_with_correct_password_opens_the_dashboard(app):
    register(app.test_client())
    browser = app.test_client()

    response = login(browser, email="an@example.com", password="correct-horse")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert browser.get("/").status_code == 200


@pytest.mark.parametrize(
    "email, password",
    [
        ("an@example.com", "wrong-password"),
        ("nobody@example.com", "correct-horse"),
    ],
)
def test_failed_login_shows_one_generic_message_and_stays_logged_out(app, email, password):
    register(app.test_client())
    browser = app.test_client()

    response = login(browser, email=email, password=password)

    assert response.status_code == 200
    assert "Email or password is incorrect." in response.get_data(as_text=True)
    assert browser.get("/").status_code == 302


def test_email_is_stored_lowercase_so_login_ignores_case(app):
    register(app.test_client(), email="  An@Example.COM ")
    browser = app.test_client()

    response = login(browser, email="AN@example.com")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.execute(select(User.email)).scalar_one() == "an@example.com"


def test_register_rejects_an_email_that_is_already_used(app):
    register(app.test_client(), email="an@example.com")

    response = register(app.test_client(), email="AN@example.com")

    assert response.status_code == 200
    assert "already registered" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.execute(select(func.count(User.id))).scalar_one() == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"password": "seven77", "confirm": "seven77"},
        {"password": "correct-horse", "confirm": "correct-horsf"},
        {"email": "not-an-email"},
        {"display_name": "   "},
    ],
    ids=["password-too-short", "confirm-mismatch", "bad-email", "blank-name"],
)
def test_register_rejects_invalid_input_without_creating_a_user(app, fields):
    response = register(app.test_client(), **fields)

    assert response.status_code == 200
    with app.app_context():
        assert db.session.execute(select(func.count(User.id))).scalar_one() == 0


def test_login_returns_to_the_requested_page_on_this_site(app):
    register(app.test_client())

    response = login(app.test_client(), next_url="/school/")

    assert response.headers["Location"] == "/school/"


@pytest.mark.parametrize(
    "next_url",
    ["https://evil.example/", "//evil.example/", "/\\evil.example/", "javascript:alert(1)"],
)
def test_login_never_redirects_to_another_site(app, next_url):
    register(app.test_client())

    response = login(app.test_client(), next_url=next_url)

    assert response.headers["Location"] == "/"


def test_logout_ends_the_session(client):
    register(client)

    response = logout(client)

    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"
    assert client.get("/").status_code == 302


def test_logout_cannot_be_triggered_by_a_plain_link(client):
    register(client)

    assert client.get("/auth/logout").status_code == 405
    assert client.get("/").status_code == 200
