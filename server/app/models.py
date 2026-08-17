"""SQLAlchemy persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    friendly_name: Mapped[str | None] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestBatch(Base):
    __tablename__ = "ingest_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    collector_version: Mapped[str] = mapped_column(String(32), nullable=False)
    decoder_versions: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    edge_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("sample_count > 0", name="ingest_batch_sample_count_positive"),
        Index("ingest_batches_device_received_idx", "device_id", "received_at"),
    )


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    first_batch_id: Mapped[str] = mapped_column(
        ForeignKey("ingest_batches.batch_id"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edge_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decoder_version: Mapped[int] = mapped_column(Integer, nullable=False)
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgent_reason: Mapped[str | None] = mapped_column(Text)
    edge_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_frame: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    raw_frame_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("octet_length(raw_frame) = 167", name="telemetry_raw_frame_167_bytes"),
        Index("telemetry_device_captured_idx", "device_id", "captured_at"),
        Index("telemetry_captured_brin_idx", "captured_at", postgresql_using="brin"),
        Index(
            "telemetry_urgent_captured_idx",
            "device_id",
            "captured_at",
            postgresql_where=urgent.is_(True),
        ),
    )


class BatchEvent(Base):
    __tablename__ = "batch_events"

    batch_id: Mapped[str] = mapped_column(
        ForeignKey("ingest_batches.batch_id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("telemetry_events.event_id"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="batch_events_batch_ordinal_key"),
    )


class MetricCatalogEntry(Base):
    __tablename__ = "metric_catalog"

    metric_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="number")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    introduced_decoder_version: Mapped[int] = mapped_column(Integer, nullable=False)


class DecodedProjection(Base):
    __tablename__ = "decoded_projections"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"), primary_key=True
    )
    decoder_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    decoded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decoder_build: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    decode_error: Mapped[str | None] = mapped_column(Text)


class EdgeStatus(Base):
    __tablename__ = "edge_status"

    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pi_reachable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    bluetooth_connected: Mapped[bool | None] = mapped_column(Boolean)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EdgeStatusTransition(Base):
    __tablename__ = "edge_status_transitions"

    transition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edge_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("edge_status_transitions_changed_idx", "edge_id", "changed_at"),
    )
