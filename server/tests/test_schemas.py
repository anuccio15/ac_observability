from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import TelemetryBatch
from .helpers import RAW_FRAME_HEX, make_batch, make_sample


def test_accepts_current_pi_contract() -> None:
    batch = TelemetryBatch.model_validate(make_batch())
    assert batch.schema_version == 1
    assert batch.device_id == "1C:C0:89:66:69:14"
    assert len(bytes.fromhex(batch.samples[0].raw_frame_hex)) == 167


def test_rejects_raw_frame_checksum_failure() -> None:
    payload = make_batch()
    damaged = bytearray.fromhex(RAW_FRAME_HEX)
    damaged[-1] ^= 1
    payload["samples"][0]["raw_frame_hex"] = damaged.hex()
    with pytest.raises(ValidationError, match="checksum mismatch"):
        TelemetryBatch.model_validate(payload)


def test_rejects_batch_id_that_does_not_match_ordered_events() -> None:
    payload = make_batch()
    payload["batch_id"] = "0" * 64
    with pytest.raises(ValidationError, match="batch_id does not match"):
        TelemetryBatch.model_validate(payload)


def test_rejects_duplicate_events() -> None:
    sample = make_sample()
    payload = make_batch([sample, sample])
    with pytest.raises(ValidationError, match="duplicate event_id"):
        TelemetryBatch.model_validate(payload)


def test_rejects_naive_timestamps() -> None:
    payload = make_batch()
    payload["samples"][0]["captured_at"] = "2026-08-13T21:08:46"
    with pytest.raises(ValidationError, match="timezone"):
        TelemetryBatch.model_validate(payload)
