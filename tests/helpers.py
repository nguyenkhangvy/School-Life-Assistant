import os

from app.config import load_config

# Tests use a throwaway in-memory SQLite database by default.
# CI sets TEST_DATABASE_URL to a real MySQL database.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


def make_config(**overrides):
    config = load_config({"SECRET_KEY": "test-secret", "DATABASE_URL": TEST_DATABASE_URL})
    config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    config.update(overrides)
    return config


def register(client, email="an@example.com", display_name="An", password="correct-horse", confirm=None):
    return client.post(
        "/auth/register",
        data={
            "email": email,
            "display_name": display_name,
            "password": password,
            "confirm": password if confirm is None else confirm,
        },
    )


def login(client, email="an@example.com", password="correct-horse", next_url=None):
    query = {} if next_url is None else {"next": next_url}
    return client.post("/auth/login", query_string=query, data={"email": email, "password": password})


def logout(client):
    return client.post("/auth/logout")
