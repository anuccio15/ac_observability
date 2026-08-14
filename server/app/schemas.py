"""Versioned HTTP schemas for the Pi ingestion contract."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DEVICE_ID_RE = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")


class TelemetrySample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    device_id: str = Field(max_length=64)
    captured_at: datetime
    received_at: datetime
    urgent: bool = False
    urgent_reason: str | None = Field(default=None, max_length=1024)
    decoder_version: int = Field(ge=1)
    metrics: dict[str, Any]
    raw_frame_hex: str

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        value = value.lower()
        if not SHA256_RE.fullmatch(value):
            raise ValueError("event_id must be a lowercase SHA-256 hex digest")
        return value

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        value = value.upper()
        if not DEVICE_ID_RE.fullmatch(value):
            raise ValueError("device_id must be a colon-separated Bluetooth address")
        return value

    @field_validator("captured_at", "received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone offset")
        return value

    @field_validator("raw_frame_hex")
    @classmethod
    def validate_raw_frame(cls, value: str) -> str:
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("raw_frame_hex must contain hexadecimal bytes") from exc
        if len(raw) != 167:
            raise ValueError(f"raw frame must be 167 bytes, received {len(raw)}")
        if raw[0] != 0xA5:
            raise ValueError("raw frame marker must be 0xa5")
        checksum = sum(raw[2:]) & 0xFF
        if raw[1] != checksum:
            raise ValueError(
                f"raw frame checksum mismatch: received 0x{raw[1]:02x}, calculated 0x{checksum:02x}"
            )
        return raw.hex()


class TelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    collector_version: str = Field(min_length=1, max_length=32)
    decoder_versions: list[int] = Field(min_length=1, max_length=32)
    batch_id: str
    created_at: datetime
    reason: str = Field(min_length=1, max_length=128)
    samples: list[TelemetrySample] = Field(min_length=1, max_length=20_000)

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, value: str) -> str:
        value = value.lower()
        if not SHA256_RE.fullmatch(value):
            raise ValueError("batch_id must be a lowercase SHA-256 hex digest")
        return value

    @field_validator("created_at")
    @classmethod
    def require_created_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_batch_invariants(self) -> "TelemetryBatch":
        event_ids = [sample.event_id for sample in self.samples]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("samples contain duplicate event_id values")
        device_ids = {sample.device_id for sample in self.samples}
        if len(device_ids) != 1:
            raise ValueError("a batch must contain exactly one device_id")
        actual_versions = sorted({sample.decoder_version for sample in self.samples})
        if self.decoder_versions != actual_versions:
            raise ValueError("decoder_versions must match the versions present in samples")
        calculated_batch_id = hashlib.sha256("\n".join(event_ids).encode()).hexdigest()
        if self.batch_id != calculated_batch_id:
            raise ValueError("batch_id does not match the ordered event_id digest")
        return self

    @property
    def device_id(self) -> str:
        return self.samples[0].device_id


class IngestResponse(BaseModel):
    batch_id: str
    accepted: Literal[True] = True
    accepted_samples: int
    duplicate: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
