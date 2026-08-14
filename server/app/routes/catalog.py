"""Read-only metric definition API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import MetricCatalogEntry


router = APIRouter(prefix="/api/v1", tags=["metrics"])


@router.get("/metrics/catalog")
def metric_catalog(session: Session = Depends(get_session)) -> dict:
    entries = session.execute(
        select(MetricCatalogEntry).order_by(MetricCatalogEntry.display_order)
    ).scalars()
    return {
        "metrics": [
            {
                "key": entry.metric_key,
                "label": entry.label,
                "description": entry.description,
                "unit": entry.unit,
                "category": entry.category,
                "confidence": entry.confidence,
                "value_type": entry.value_type,
                "display_order": entry.display_order,
                "introduced_decoder_version": entry.introduced_decoder_version,
            }
            for entry in entries
        ]
    }
