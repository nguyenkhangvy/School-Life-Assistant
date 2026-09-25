import pytest
from sqlalchemy import func, select

from app import create_app
from app.auth.models import User
from app.config import load_config
from app.extensions import db
from tests.helpers import TEST_DATABASE_URL, make_config, register


def test_missing_settings_stop_the_app_with_their_names():
    with pytest.raises(RuntimeError) as error:
        load_config({"SECRET_KEY": "x"})

    assert "DATABASE_URL" in str(error.value)
    assert "SECRET_KEY" not in str(error.value)


def test_a_database_password_with_a_raw_at_sign_stops_the_app_with_a_hint():
    with pytest.raises(RuntimeError) as error:
        load_config({"SECRET_KEY": "x", "DATABASE_URL": "mysql+pymysql://sla_app:abc@123@localhost:3306/school_life"})

    assert "%40" in str(error.value)
    assert "abc@123" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    ["mysql+pymysql://sla_app:abc%40123@localhost:3306/school_life?charset=utf8mb4", "sqlite://", "sqlite:///a.db"],
)
def test_valid_database_addresses_are_accepted(url):
    assert load_config({"SECRET_KEY": "x", "DATABASE_URL": url})["SQLALCHEMY_DATABASE_URI"] == url


def test_forms_reject_posts_without_a_csrf_token():
    app = create_app(make_config(WTF_CSRF_ENABLED=True))
    with app.app_context():
        db.create_all()

    response = register(app.test_client())

    assert response.status_code == 400
    with app.app_context():
        assert db.session.execute(select(func.count(User.id))).scalar_one() == 0
        db.drop_all()


def _session_cookie_after_register(environ_extra):
    config = load_config({"SECRET_KEY": "test-secret", "DATABASE_URL": TEST_DATABASE_URL, **environ_extra})
    config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    app = create_app(config)
    with app.app_context():
        db.create_all()
    response = register(app.test_client())
    with app.app_context():
        db.drop_all()
    return next(h for h in response.headers.getlist("Set-Cookie") if h.startswith("session="))


def test_session_cookie_is_httponly_samesite_and_secure_by_default():
    cookie = _session_cookie_after_register({})

    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" in cookie


def test_secure_cookie_can_be_turned_off_for_local_http():
    cookie = _session_cookie_after_register({"SESSION_COOKIE_SECURE": "false"})

    assert "Secure" not in cookie
