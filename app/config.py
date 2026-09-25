import os

REQUIRED_SETTINGS = ("SECRET_KEY", "DATABASE_URL")


def load_config(environ=os.environ):
    """Build the Flask settings from environment variables (or a .env file)."""
    missing = [name for name in REQUIRED_SETTINGS if not environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing settings: {', '.join(missing)}. Copy .env.example to .env and fill them in."
        )

    return {
        "SECRET_KEY": environ["SECRET_KEY"],
        "SQLALCHEMY_DATABASE_URI": environ["DATABASE_URL"],
        # Check connections before use and renew them before free MySQL hosts drop idle ones.
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True, "pool_recycle": 280},
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        # HTTPS-only cookies unless explicitly turned off for http://localhost.
        "SESSION_COOKIE_SECURE": environ.get("SESSION_COOKIE_SECURE", "true").lower() != "false",
    }
