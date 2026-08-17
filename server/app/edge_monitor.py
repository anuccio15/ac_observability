"""Read-only Pi health probing and durable state-transition tracking."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import EdgeStatus, EdgeStatusTransition


LOG = logging.getLogger(__name__)
EDGE_ID = "bosch-pi"


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def probe_pi(settings: Settings) -> dict[str, Any]:
    """Fetch the Pi's public health endpoint without changing collector state."""
    checked_at = datetime.now(timezone.utc)
    if not settings.pi_api_url:
        return {
            "state": "unknown",
            "checked_at": checked_at,
            "pi_reachable": False,
            "bluetooth_connected": None,
            "last_frame_at": None,
            "detail": {"reason": "Pi health URL is not configured"},
        }

    request = urllib.request.Request(
        f"{settings.pi_api_url.rstrip('/')}/health",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.pi_status_timeout_seconds
        ) as response:
            payload = json.loads(response.read())
        collector = payload.get("collector") or {}
        bluetooth_connected = bool(payload.get("bluetooth_connected"))
        last_frame_at = _datetime(collector.get("last_frame_at"))
        if not bluetooth_connected:
            state = "bosch_disconnected"
        elif last_frame_at is None or (
            checked_at - last_frame_at
        ).total_seconds() > settings.telemetry_stale_seconds:
            state = "telemetry_stale"
        else:
            state = "healthy"
        detail = {
            "collector_version": payload.get("collector_version"),
            "collector_started_at": collector.get("started_at"),
            "last_connected_at": collector.get("last_connected_at"),
            "last_disconnected_at": collector.get("last_disconnected_at"),
            "last_error": collector.get("last_error"),
            "reconnect_count": collector.get("reconnect_count"),
            "pending_samples": (payload.get("storage") or {}).get("pending_samples"),
            "storage_warning": payload.get("storage_warning"),
        }
        return {
            "state": state,
            "checked_at": checked_at,
            "pi_reachable": True,
            "bluetooth_connected": bluetooth_connected,
            "last_frame_at": last_frame_at,
            "detail": detail,
        }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "state": "pi_unreachable",
            "checked_at": checked_at,
            "pi_reachable": False,
            "bluetooth_connected": None,
            "last_frame_at": None,
            "detail": {"reason": f"{type(exc).__name__}: {exc}"},
        }


def record_status(
    session_factory: sessionmaker[Session], result: dict[str, Any]
) -> EdgeStatus:
    with session_factory() as session, session.begin():
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:edge_id, 0))"),
            {"edge_id": EDGE_ID},
        )
        current = session.get(EdgeStatus, EDGE_ID)
        previous_state = current.state if current else None
        if current is None:
            current = EdgeStatus(
                edge_id=EDGE_ID,
                state=result["state"],
                checked_at=result["checked_at"],
                state_since=result["checked_at"],
                pi_reachable=result["pi_reachable"],
                bluetooth_connected=result["bluetooth_connected"],
                last_frame_at=result["last_frame_at"],
                detail=result["detail"],
            )
            session.add(current)
        else:
            current.state = result["state"]
            current.checked_at = result["checked_at"]
            current.pi_reachable = result["pi_reachable"]
            current.bluetooth_connected = result["bluetooth_connected"]
            current.last_frame_at = result["last_frame_at"]
            current.detail = result["detail"]
            if previous_state != result["state"]:
                current.state_since = result["checked_at"]
        if previous_state != result["state"]:
            session.add(
                EdgeStatusTransition(
                    edge_id=EDGE_ID,
                    from_state=previous_state,
                    to_state=result["state"],
                    changed_at=result["checked_at"],
                    detail=result["detail"],
                )
            )
        session.flush()
        session.expunge(current)
        return current


def check_and_record(
    settings: Settings, session_factory: sessionmaker[Session]
) -> EdgeStatus:
    return record_status(session_factory, probe_pi(settings))


def status_payload(status: EdgeStatus | None) -> dict[str, Any]:
    if status is None:
        return {
            "edge_id": EDGE_ID,
            "state": "unknown",
            "checked_at": None,
            "state_since": None,
            "pi_reachable": None,
            "bluetooth_connected": None,
            "last_frame_at": None,
            "detail": {},
        }
    return {
        "edge_id": status.edge_id,
        "state": status.state,
        "checked_at": status.checked_at,
        "state_since": status.state_since,
        "pi_reachable": status.pi_reachable,
        "bluetooth_connected": status.bluetooth_connected,
        "last_frame_at": status.last_frame_at,
        "detail": status.detail,
    }


def current_status(session: Session) -> EdgeStatus | None:
    return session.scalar(select(EdgeStatus).where(EdgeStatus.edge_id == EDGE_ID))
