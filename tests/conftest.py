import pytest

from app import create_app
from app.extensions import db
from tests.helpers import make_config


@pytest.fixture
def app():
    # No app context stays open while tests make requests: Flask-Login caches
    # the logged-in user per app context, which would leak between browsers.
    app = create_app(make_config())
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
