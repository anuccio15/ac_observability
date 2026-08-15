"""Server-side control plane for the trusted LAN edge collector."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/api/v1/edge", tags=["edge"])


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
