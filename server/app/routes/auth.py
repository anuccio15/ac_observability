"""Dashboard login, logout, and session endpoints."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..dashboard_auth import create_session_token, read_session_token, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["dashboard-auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


def _settings(request: Request):
    return request.app.state.settings


def _current_username(request: Request) -> str | None:
    settings = _settings(request)
    session = read_session_token(
        request.cookies.get(settings.dashboard_cookie_name),
        settings.dashboard_session_secret.get_secret_value(),
        settings.dashboard_username,
    )
    return session.username if session else None


@router.get("/session")
def session(request: Request) -> dict:
    username = _current_username(request)
    return {"authenticated": username is not None, "username": username}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    settings = _settings(request)
    password_valid = verify_password(
        payload.password,
        settings.dashboard_password_hash.get_secret_value(),
    )
    username_valid = secrets.compare_digest(payload.username, settings.dashboard_username)
    if not (password_valid and username_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    token = create_session_token(
        settings.dashboard_username,
        settings.dashboard_session_secret.get_secret_value(),
        settings.dashboard_session_ttl_seconds,
    )
    response.set_cookie(
        key=settings.dashboard_cookie_name,
        value=token,
        max_age=settings.dashboard_session_ttl_seconds,
        httponly=True,
        secure=settings.dashboard_cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "username": settings.dashboard_username}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    settings = _settings(request)
    response.delete_cookie(
        key=settings.dashboard_cookie_name,
        path="/",
        secure=settings.dashboard_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return {"authenticated": False, "username": None}
