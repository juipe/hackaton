"""Password hashing, session tokens and opaque token helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings
from app.utils.time import utcnow

_password_hash = PasswordHash((BcryptHasher(),))

#: bcrypt silently ignores anything past 72 bytes and modern bindings raise instead,
#: so longer inputs are folded down to a fixed-length digest first. Applied by both
#: :func:`hash_password` and :func:`verify_password` so the two always agree.
_BCRYPT_MAX_BYTES = 72

_JWT_ALGORITHM = "HS256"


def _prepare_password(raw: str) -> str:
    encoded = raw.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return raw
    return base64.b64encode(hashlib.sha256(encoded).digest()).decode("ascii")


def hash_password(raw: str) -> str:
    return _password_hash.hash(_prepare_password(raw))


def verify_password(raw: str, hashed: str) -> bool:
    if not raw or not hashed:
        return False
    try:
        return _password_hash.verify(_prepare_password(raw), hashed)
    except Exception:
        # A malformed or unknown hash must read as "wrong password", never a 500.
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = utcnow()
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id carried by a valid token, or ``None``."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
        return uuid.UUID(str(payload["sub"]))
    except Exception:
        return None


def generate_invite_token() -> str:
    """Opaque, unguessable invite token. Carries no internal identifiers."""
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    """Only the hash is ever persisted, so a database leak cannot replay invites."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return secrets.compare_digest(left, right)


__all__ = [
    "create_access_token",
    "decode_access_token",
    "generate_csrf_token",
    "generate_invite_token",
    "hash_invite_token",
    "hash_password",
    "tokens_match",
    "verify_password",
]
