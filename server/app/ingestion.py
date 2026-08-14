"""Transactional and idempotent persistence for Pi telemetry batches."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from .models import BatchEvent, Device, IngestBatch, TelemetryEvent
from .schemas import TelemetryBatch, TelemetrySample


class IngestConflict(ValueError):
    """An idempotency key was reused for different immutable content."""


@dataclass(frozen=True)
class IngestResult:
    batch_id: str
    accepted_samples: int
    duplicate: bool


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def batch_digest(batch: TelemetryBatch) -> str:
    return _canonical_digest(batch.model_dump(mode="json"))


def sample_digest(sample: TelemetrySample) -> str:
    return _canonical_digest(sample.model_dump(mode="json"))


def ingest_batch(
    session_factory: sessionmaker[Session],
    batch: TelemetryBatch,
) -> IngestResult:
    content_digest = batch_digest(batch)
    with session_factory() as session, session.begin():
        # The Pi is a single logical writer. Serializing by device removes races
        # between a retry and a newly formed overlapping batch without blocking
        # ingestion from other future devices.
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:device_id, 0))"),
            {"device_id": batch.device_id},
        )
        existing_batch = session.get(IngestBatch, batch.batch_id)
        if existing_batch is not None:
            if existing_batch.content_digest != content_digest:
                raise IngestConflict("batch_id already exists with different content")
            return IngestResult(batch.batch_id, existing_batch.sample_count, True)

        event_digests = {sample.event_id: sample_digest(sample) for sample in batch.samples}
        existing_events = session.execute(
            select(TelemetryEvent.event_id, TelemetryEvent.event_digest).where(
                TelemetryEvent.event_id.in_(event_digests)
            )
        ).all()
        for event_id, stored_digest in existing_events:
            if event_digests[event_id] != stored_digest:
                raise IngestConflict(
                    f"event_id {event_id} already exists with different content"
                )

        first_seen = min(sample.captured_at for sample in batch.samples)
        last_seen = max(sample.captured_at for sample in batch.samples)
        device_insert = insert(Device).values(
            device_id=batch.device_id,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
        )
        session.execute(
            device_insert.on_conflict_do_update(
                index_elements=[Device.device_id],
                set_={
                    "first_seen_at": func.least(Device.first_seen_at, first_seen),
                    "last_seen_at": func.greatest(Device.last_seen_at, last_seen),
                },
            )
        )
        session.add(
            IngestBatch(
                batch_id=batch.batch_id,
                device_id=batch.device_id,
                schema_version=batch.schema_version,
                collector_version=batch.collector_version,
                decoder_versions=batch.decoder_versions,
                reason=batch.reason,
                edge_created_at=batch.created_at,
                sample_count=len(batch.samples),
                content_digest=content_digest,
            )
        )
        session.flush()

        existing_ids = {event_id for event_id, _ in existing_events}
        new_events = []
        for sample in batch.samples:
            if sample.event_id in existing_ids:
                continue
            raw = bytes.fromhex(sample.raw_frame_hex)
            new_events.append(
                {
                    "event_id": sample.event_id,
                    "event_digest": event_digests[sample.event_id],
                    "device_id": sample.device_id,
                    "first_batch_id": batch.batch_id,
                    "captured_at": sample.captured_at,
                    "edge_received_at": sample.received_at,
                    "decoder_version": sample.decoder_version,
                    "urgent": sample.urgent,
                    "urgent_reason": sample.urgent_reason,
                    "edge_metrics": sample.metrics,
                    "raw_frame": raw,
                    "raw_frame_digest": hashlib.sha256(raw).hexdigest(),
                }
            )
        if new_events:
            session.execute(insert(TelemetryEvent), new_events)
        session.execute(
            insert(BatchEvent),
            [
                {
                    "batch_id": batch.batch_id,
                    "event_id": sample.event_id,
                    "ordinal": ordinal,
                }
                for ordinal, sample in enumerate(batch.samples)
            ],
        )
    return IngestResult(batch.batch_id, len(batch.samples), False)
