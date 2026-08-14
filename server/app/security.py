"""Authentication for edge-only ingestion endpoints."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status


def require_edge_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    expected = request.app.state.settings.edge_api_token.get_secret_value()
    scheme, separator, supplied = (authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(supplied)
        and secrets.compare_digest(supplied, expected)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid edge API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
