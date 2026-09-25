"""Device keys: how the laptop agent proves which user it syncs for.

The raw key is shown to the user once. The database keeps only its SHA-256
hash, so a leaked database can't be used to upload data.
"""

import hashlib
import secrets

from sqlalchemy import select

from app.extensions import db
from app.school.models import SchoolSyncDevice

KEY_PREFIX = "sla_"


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_device(user_id, name):
    """Add a device (caller commits). Returns (device, raw_key)."""
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    device = SchoolSyncDevice(user_id=user_id, name=name, token_hash=hash_key(raw_key))
    db.session.add(device)
    db.session.flush()
    return device, raw_key


def authenticate(raw_key):
    """The active device for this key, or None."""
    if not raw_key:
        return None
    return db.session.execute(
        select(SchoolSyncDevice).filter_by(token_hash=hash_key(raw_key), revoked_at=None)
    ).scalar_one_or_none()
