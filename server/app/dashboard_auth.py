"""Single-user dashboard authentication using signed, HTTP-only sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, iterations: int = PASSWORD_ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    # Colons keep the value safe in Docker Compose .env files, where dollar
    # signs would otherwise be interpreted as variable substitutions.
    return f"{PASSWORD_SCHEME}:{iterations}:{_encode(salt)}:{_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = encoded.split(":", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_raw)
        if not 100_000 <= iterations <= 2_000_000:
            return False
        expected = _decode(digest_raw)
        supplied = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _decode(salt_raw), iterations
        )
        return hmac.compare_digest(supplied, expected)
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class DashboardSession:
    username: str
    expires_at: int


def create_session_token(
    username: str,
    secret: str,
    ttl_seconds: int,
    *,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = _encode(
        json.dumps(
            {"sub": username, "exp": issued_at + ttl_seconds},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    signature = _encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_session_token(
    token: str | None,
    secret: str,
    expected_username: str,
    *,
    now: int | None = None,
) -> DashboardSession | None:
    if not token:
        return None
    try:
        payload, supplied_signature = token.split(".", 1)
        expected_signature = _encode(
            hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        decoded = json.loads(_decode(payload))
        username = decoded["sub"]
        expires_at = int(decoded["exp"])
        current_time = int(time.time() if now is None else now)
        if not hmac.compare_digest(str(username), expected_username):
            return None
        if expires_at <= current_time:
            return None
        return DashboardSession(username=expected_username, expires_at=expires_at)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
