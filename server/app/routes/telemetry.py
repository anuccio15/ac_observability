"""Read-only telemetry APIs consumed by the dashboard."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Device, MetricCatalogEntry, TelemetryEvent


router = APIRouter(prefix="/api/v1", tags=["telemetry"])

DEFAULT_SERIES_METRICS = (
    "compressor_set_hz",
    "outdoor_ambient_t4_f",
    "outdoor_coil_t3_f",
    "compressor_discharge_t5_f",
    "compressor_suction_th_f",
    "compressor_ipm_temp_f",
    "target_evaporating_temp_tes_f",
    "evaporating_temp_te_f",
    "target_condensing_temp_tcs_f",
    "condensing_temp_tc_f",
    "target_discharge_superheat_f",
    "compressor_discharge_superheat_f",
    "evaporating_pressure_pe_psig",
    "condensing_pressure_pc_psig",
    "candidate_ac_input_voltage_v",
    "candidate_compressor_current_a",
)
SUMMARY_METRICS = (
    "compressor_set_hz",
    "outdoor_ambient_t4_f",
    "compressor_discharge_t5_f",
    "compressor_ipm_temp_f",
    "evaporating_pressure_pe_psig",
    "condensing_pressure_pc_psig",
    "candidate_ac_input_voltage_v",
    "candidate_compressor_current_a",
)


def _utc(value: datetime | None, default: datetime) -> datetime:
    value = value or default
    if value.tzinfo is None:
        raise HTTPException(status_code=422, detail="timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _range(
    start: datetime | None,
    end: datetime | None,
    *,
    default_hours: int = 24,
    maximum_days: int = 366,
) -> tuple[datetime, datetime]:
    range_end = _utc(end, datetime.now(timezone.utc))
    range_start = _utc(start, range_end - timedelta(hours=default_hours))
    if range_start >= range_end:
        raise HTTPException(status_code=422, detail="start must be before end")
    if range_end - range_start > timedelta(days=maximum_days):
        raise HTTPException(
            status_code=422,
            detail=f"requested range exceeds {maximum_days} days",
        )
    return range_start, range_end


def _device(session: Session, device_id: str | None) -> Device:
    if device_id:
        device = session.get(Device, device_id)
    else:
        device = session.scalar(select(Device).order_by(Device.last_seen_at.desc()).limit(1))
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    return device


def _event_payload(event: TelemetryEvent | None) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "event_id": event.event_id,
        "device_id": event.device_id,
        "captured_at": event.captured_at,
        "server_received_at": event.server_received_at,
        "decoder_version": event.decoder_version,
        "urgent": event.urgent,
        "urgent_reason": event.urgent_reason,
        "metrics": event.edge_metrics,
    }


@router.get("/devices")
def devices(session: Session = Depends(get_session)) -> dict[str, Any]:
    results = []
    for device in session.scalars(select(Device).order_by(Device.last_seen_at.desc())):
        event_count = session.scalar(
            select(func.count()).select_from(TelemetryEvent).where(
                TelemetryEvent.device_id == device.device_id
            )
        )
        urgent_count = session.scalar(
            select(func.count()).select_from(TelemetryEvent).where(
                TelemetryEvent.device_id == device.device_id,
                TelemetryEvent.urgent.is_(True),
            )
        )
        latest = session.scalar(
            select(TelemetryEvent)
            .where(TelemetryEvent.device_id == device.device_id)
            .order_by(TelemetryEvent.captured_at.desc())
            .limit(1)
        )
        results.append(
            {
                "device_id": device.device_id,
                "friendly_name": device.friendly_name,
                "timezone": device.timezone,
                "first_seen_at": device.first_seen_at,
                "last_seen_at": device.last_seen_at,
                "event_count": event_count or 0,
                "urgent_count": urgent_count or 0,
                "latest": _event_payload(latest),
            }
        )
    return {"devices": results}


@router.get("/telemetry/latest")
def latest_telemetry(
    device_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    device = _device(session, device_id)
    event = session.scalar(
        select(TelemetryEvent)
        .where(TelemetryEvent.device_id == device.device_id)
        .order_by(TelemetryEvent.captured_at.desc())
        .limit(1)
    )
    return {"sample": _event_payload(event)}


@router.get("/telemetry/series")
def telemetry_series(
    device_id: str | None = None,
    metrics: str = ",".join(DEFAULT_SERIES_METRICS),
    start: datetime | None = None,
    end: datetime | None = None,
    max_points: int = Query(1200, ge=50, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    device = _device(session, device_id)
    range_start, range_end = _range(start, end)
    requested = list(dict.fromkeys(key.strip() for key in metrics.split(",") if key.strip()))
    if not requested or len(requested) > 20:
        raise HTTPException(status_code=422, detail="request between 1 and 20 metrics")
    catalog = {
        entry.metric_key: entry
        for entry in session.scalars(
            select(MetricCatalogEntry).where(MetricCatalogEntry.metric_key.in_(requested))
        )
    }
    invalid = [key for key in requested if key not in catalog or catalog[key].value_type != "number"]
    if invalid:
        raise HTTPException(status_code=422, detail={"invalid_numeric_metrics": invalid})

    bucket_seconds = max(
        5,
        math.ceil((range_end - range_start).total_seconds() / max_points),
    )
    query = text(
        """
        SELECT
            to_timestamp(
                floor(extract(epoch FROM captured_at) / :bucket_seconds) * :bucket_seconds
            ) AS bucket,
            avg((edge_metrics ->> :metric_key)::double precision) AS average,
            min((edge_metrics ->> :metric_key)::double precision) AS minimum,
            max((edge_metrics ->> :metric_key)::double precision) AS maximum,
            count(*) AS sample_count
        FROM telemetry_events
        WHERE device_id = :device_id
          AND captured_at >= :range_start
          AND captured_at <= :range_end
          AND jsonb_typeof(edge_metrics -> :metric_key) = 'number'
        GROUP BY bucket
        ORDER BY bucket
        """
    )
    series: dict[str, Any] = {}
    for key in requested:
        rows = session.execute(
            query,
            {
                "bucket_seconds": bucket_seconds,
                "metric_key": key,
                "device_id": device.device_id,
                "range_start": range_start,
                "range_end": range_end,
            },
        )
        entry = catalog[key]
        series[key] = {
            "label": entry.label,
            "unit": entry.unit,
            "category": entry.category,
            "confidence": entry.confidence,
            "points": [
                {
                    "timestamp": row.bucket,
                    "value": float(row.average),
                    "minimum": float(row.minimum),
                    "maximum": float(row.maximum),
                    "sample_count": row.sample_count,
                }
                for row in rows
            ],
        }
    return {
        "device_id": device.device_id,
        "start": range_start,
        "end": range_end,
        "bucket_seconds": bucket_seconds,
        "series": series,
    }


@router.get("/summary")
def telemetry_summary(
    device_id: str | None = None,
    hours: int = Query(24, ge=1, le=24 * 31),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    device = _device(session, device_id)
    range_end = datetime.now(timezone.utc)
    range_start = range_end - timedelta(hours=hours)
    latest = session.scalar(
        select(TelemetryEvent)
        .where(TelemetryEvent.device_id == device.device_id)
        .order_by(TelemetryEvent.captured_at.desc())
        .limit(1)
    )
    counts = session.execute(
        select(
            func.count(TelemetryEvent.event_id),
            func.count(TelemetryEvent.event_id).filter(TelemetryEvent.urgent.is_(True)),
            func.min(TelemetryEvent.captured_at),
            func.max(TelemetryEvent.captured_at),
        ).where(
            TelemetryEvent.device_id == device.device_id,
            TelemetryEvent.captured_at >= range_start,
            TelemetryEvent.captured_at <= range_end,
        )
    ).one()
    aggregate_query = text(
        """
        SELECT
            avg((edge_metrics ->> :metric_key)::double precision) AS average,
            min((edge_metrics ->> :metric_key)::double precision) AS minimum,
            max((edge_metrics ->> :metric_key)::double precision) AS maximum
        FROM telemetry_events
        WHERE device_id = :device_id
          AND captured_at >= :range_start
          AND captured_at <= :range_end
          AND jsonb_typeof(edge_metrics -> :metric_key) = 'number'
        """
    )
    aggregates: dict[str, Any] = {}
    for key in SUMMARY_METRICS:
        row = session.execute(
            aggregate_query,
            {
                "metric_key": key,
                "device_id": device.device_id,
                "range_start": range_start,
                "range_end": range_end,
            },
        ).one()
        if row.average is not None:
            aggregates[key] = {
                "average": float(row.average),
                "minimum": float(row.minimum),
                "maximum": float(row.maximum),
            }
    return {
        "device_id": device.device_id,
        "window_hours": hours,
        "start": range_start,
        "end": range_end,
        "event_count": counts[0],
        "urgent_count": counts[1],
        "first_sample_at": counts[2],
        "last_sample_at": counts[3],
        "latest": _event_payload(latest),
        "aggregates": aggregates,
    }


@router.get("/cycles")
def cycles(
    device_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    device = _device(session, device_id)
    range_start, range_end = _range(start, end, default_hours=24 * 7, maximum_days=31)
    rows = session.execute(
        text(
            """
            WITH ordered AS (
                SELECT
                    captured_at,
                    edge_metrics ->> 'mode' AS mode,
                    CASE WHEN jsonb_typeof(edge_metrics -> 'compressor_set_hz') = 'number'
                        THEN (edge_metrics ->> 'compressor_set_hz')::double precision
                    END AS compressor_hz,
                    lag(captured_at) OVER (ORDER BY captured_at) AS previous_at,
                    lag(edge_metrics ->> 'mode') OVER (ORDER BY captured_at) AS previous_mode
                FROM telemetry_events
                WHERE device_id = :device_id
                  AND captured_at >= :range_start
                  AND captured_at <= :range_end
            ), marked AS (
                SELECT *, CASE
                    WHEN previous_at IS NULL
                      OR mode IS DISTINCT FROM previous_mode
                      OR captured_at - previous_at > interval '5 minutes'
                    THEN 1 ELSE 0 END AS new_cycle
                FROM ordered
            ), grouped AS (
                SELECT *, sum(new_cycle) OVER (ORDER BY captured_at) AS cycle_group
                FROM marked
            )
            SELECT
                mode,
                min(captured_at) AS started_at,
                max(captured_at) AS ended_at,
                extract(epoch FROM max(captured_at) - min(captured_at)) AS duration_seconds,
                count(*) AS sample_count,
                avg(compressor_hz) AS average_compressor_hz,
                max(compressor_hz) AS maximum_compressor_hz,
                count(*) OVER () AS total_count
            FROM grouped
            WHERE mode IS NOT NULL
            GROUP BY cycle_group, mode
            ORDER BY started_at DESC
            LIMIT :page_size OFFSET :offset
            """
        ),
        {
            "device_id": device.device_id,
            "range_start": range_start,
            "range_end": range_end,
            "page_size": page_size,
            "offset": (page - 1) * page_size,
        },
    ).all()
    total = int(rows[0].total_count) if rows else 0
    return {
        "device_id": device.device_id,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "cycles": [
            {
                "mode": row.mode,
                "started_at": row.started_at,
                "ended_at": row.ended_at,
                "duration_seconds": float(row.duration_seconds),
                "sample_count": row.sample_count,
                "average_compressor_hz": (
                    float(row.average_compressor_hz)
                    if row.average_compressor_hz is not None
                    else None
                ),
                "maximum_compressor_hz": (
                    float(row.maximum_compressor_hz)
                    if row.maximum_compressor_hz is not None
                    else None
                ),
            }
            for row in rows
        ],
    }


@router.get("/faults")
def faults(
    device_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    device = _device(session, device_id)
    condition = (
        TelemetryEvent.device_id == device.device_id,
        TelemetryEvent.urgent.is_(True),
    )
    total = session.scalar(
        select(func.count()).select_from(TelemetryEvent).where(*condition)
    ) or 0
    events = session.scalars(
        select(TelemetryEvent)
        .where(*condition)
        .order_by(TelemetryEvent.captured_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return {
        "device_id": device.device_id,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "faults": [_event_payload(event) for event in events],
    }
