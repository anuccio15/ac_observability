from __future__ import annotations

import gzip
import hashlib
import json


EDGE_TOKEN = "test-edge-token-that-is-at-least-32-characters"
DEVICE_ID = "1C:C0:89:66:69:14"
RAW_FRAME_HEX = (
    "a5b10200000056005e005d00730056006b00d000f6002c004e006b0059002d00"
    "0300ff00ff00ff00ff00ff00ff00000009001900050000000000000082017801"
    "ed007801040400000001000000ff0002002500c0c0c0c0c0c0bfbfbfbfbfbfbf"
    "bfbfbfbfbfbfbfbfbfbfbf0000000b00ff000000ff7f0000c0c0bfc0bfbfbfbf"
    "bfbfbfbf05001700ff00ff0000000200ff00ff7fff7f00000000000000000000"
    "00000000000000"
)


def make_sample(
    captured_at: str = "2026-08-13T21:08:46+00:00",
    *,
    compressor_hz: int = 0,
) -> dict:
    event_id = hashlib.sha256(
        f"{DEVICE_ID}|{captured_at}|{RAW_FRAME_HEX}".encode()
    ).hexdigest()
    return {
        "event_id": event_id,
        "device_id": DEVICE_ID,
        "captured_at": captured_at,
        "received_at": captured_at,
        "urgent": False,
        "urgent_reason": None,
        "decoder_version": 1,
        "metrics": {
            "mode_code": 2,
            "mode": "cooling",
            "compressor_set_hz": compressor_hz,
            "outdoor_ambient_t4_f": 94,
        },
        "raw_frame_hex": RAW_FRAME_HEX,
    }


def make_batch(samples: list[dict] | None = None) -> dict:
    samples = samples or [make_sample()]
    event_ids = [sample["event_id"] for sample in samples]
    return {
        "schema_version": 1,
        "collector_version": "1.1.0",
        "decoder_versions": sorted({sample["decoder_version"] for sample in samples}),
        "batch_id": hashlib.sha256("\n".join(event_ids).encode()).hexdigest(),
        "created_at": samples[0]["captured_at"],
        "reason": "scheduled",
        "samples": samples,
    }


def gzip_json(payload: dict) -> bytes:
    return gzip.compress(json.dumps(payload, separators=(",", ":")).encode())


def edge_headers(token: str = EDGE_TOKEN) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
    }
