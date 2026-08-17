"""Server-side control plane for the trusted LAN edge collector."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..edge_monitor import check_and_record, current_status, status_payload
from ..models import EdgeStatusTransition


router = APIRouter(prefix="/api/v1/edge", tags=["edge"])


@router.get("/status")
def get_edge_status(
    history_limit: int = Query(12, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    transitions = session.scalars(
        select(EdgeStatusTransition)
        .order_by(EdgeStatusTransition.changed_at.desc())
        .limit(history_limit)
    )
    return {
        "current": status_payload(current_status(session)),
        "transitions": [
            {
                "id": item.transition_id,
                "from_state": item.from_state,
                "to_state": item.to_state,
                "changed_at": item.changed_at,
                "detail": item.detail,
            }
            for item in transitions
        ],
    }


@router.post("/status/check")
async def check_edge_status(request: Request) -> dict[str, Any]:
    status = await run_in_threadpool(
        check_and_record,
        request.app.state.settings,
        request.app.state.session_factory,
    )
    return {"current": status_payload(status)}


@router.post("/sync")
def sync_edge(request: Request) -> dict[str, Any]:
    """Ask the Pi to upload its durable backlog and return after acknowledgement."""
    settings = request.app.state.settings
    if not settings.pi_api_url or not settings.pi_api_token:
        raise HTTPException(status_code=503, detail="Pi synchronization is not configured")
    url = f"{settings.pi_api_url.rstrip('/')}/api/v1/flush"
    edge_request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.pi_api_token.get_secret_value()}",
        },
    )
    try:
        with urllib.request.urlopen(
            edge_request, timeout=settings.pi_sync_timeout_seconds
        ) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Pi synchronization returned HTTP {exc.code}",
        ) from exc
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Pi synchronization failed") from exc
    return {"status": "complete", "edge": payload}
