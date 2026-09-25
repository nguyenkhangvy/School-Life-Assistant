from datetime import datetime, timezone


def utcnow():
    """Current time in UTC, without tzinfo, as stored in MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
