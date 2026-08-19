from __future__ import annotations

from app.dashboard_auth import (
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect", encoded)
    assert "$" not in encoded


def test_signed_session_rejects_tampering_and_expiration() -> None:
    secret = "a-session-secret-that-is-longer-than-thirty-two-characters"
    token = create_session_token("admin", secret, 60, now=1_000)
    assert read_session_token(token, secret, "admin", now=1_059) is not None
    assert read_session_token(token, secret, "admin", now=1_060) is None
    assert read_session_token(f"{token}x", secret, "admin", now=1_001) is None
    assert read_session_token(token, secret, "someone-else", now=1_001) is None
