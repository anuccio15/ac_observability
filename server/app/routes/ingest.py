"""Authenticated Pi ingestion endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from ..ingestion import IngestConflict, ingest_batch
from ..request_body import read_gzip_json
from ..schemas import IngestResponse, TelemetryBatch
from ..security import require_edge_token


router = APIRouter(prefix="/v1/telemetry", tags=["edge-ingestion"])


@router.post("/batches", response_model=IngestResponse)
async def receive_batch(
    request: Request,
    _authenticated: None = Depends(require_edge_token),
) -> IngestResponse:
    raw_payload = await read_gzip_json(request)
    try:
        batch = TelemetryBatch.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc
    if len(batch.samples) > request.app.state.settings.max_batch_samples:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="sample count exceeds configured limit",
        )
    try:
        result = await run_in_threadpool(
            ingest_batch,
            request.app.state.session_factory,
            batch,
        )
    except IngestConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return IngestResponse(
        batch_id=result.batch_id,
        accepted_samples=result.accepted_samples,
        duplicate=result.duplicate,
    )
