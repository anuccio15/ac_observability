#!/usr/bin/env python3
"""Interactively configure the single dashboard account in a local .env file."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "server"))

from app.dashboard_auth import hash_password  # noqa: E402


def update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(values)
    updated: list[str] = []
    for line in lines:
        key, separator, _value = line.partition("=")
        if separator and key in remaining:
            updated.append(f"{key}={remaining.pop(key)}")
        else:
            updated.append(line)
    if remaining and updated and updated[-1]:
        updated.append("")
    updated.extend(f"{key}={value}" for key, value in remaining.items())

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as temporary:
            temporary.write("\n".join(updated) + "\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--username", default="admin")
    parser.add_argument(
        "--secure-cookie",
        action="store_true",
        help="mark the login cookie HTTPS-only (enable after the public HTTPS hostname works)",
    )
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        raise SystemExit("Username must not be empty")
    password = getpass.getpass(f"Password for {username}: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not password:
        raise SystemExit("Password must not be empty")

    update_env(
        args.env_file,
        {
            "AC_DASHBOARD_USERNAME": username,
            "AC_DASHBOARD_PASSWORD_HASH": hash_password(password),
            "AC_DASHBOARD_SESSION_SECRET": secrets.token_urlsafe(48),
            "AC_DASHBOARD_SESSION_TTL_SECONDS": str(7 * 24 * 60 * 60),
            "AC_DASHBOARD_COOKIE_SECURE": "true" if args.secure_cookie else "false",
        },
    )
    print(f"Configured dashboard account '{username}' in {args.env_file}")
    print("The plaintext password was not stored.")


if __name__ == "__main__":
    main()
