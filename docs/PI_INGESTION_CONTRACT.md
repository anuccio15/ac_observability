# Raspberry Pi ingestion contract

## Endpoint

`POST /v1/telemetry/batches`

Headers:

```http
Authorization: Bearer <edge-token>
Content-Type: application/json
Content-Encoding: gzip
```

Current request shape:

```json
{
  "schema_version": 1,
  "collector_version": "1.1.0",
  "decoder_versions": [1],
  "batch_id": "sha256...",
  "created_at": "2026-08-13T21:08:46+00:00",
  "reason": "scheduled",
  "samples": [
    {
      "event_id": "sha256...",
      "device_id": "1C:C0:89:66:69:14",
      "captured_at": "2026-08-13T21:08:46+00:00",
      "received_at": "2026-08-13T21:08:46+00:00",
      "urgent": false,
      "urgent_reason": null,
      "decoder_version": 1,
      "metrics": {},
      "raw_frame_hex": "a5..."
    }
  ]
}
```

Successful response:

```json
{
  "batch_id": "sha256...",
  "accepted": true,
  "accepted_samples": 1,
  "duplicate": false
}
```

## Transaction and retry rules

1. Validate the complete request before changing state.
2. Decode `raw_frame_hex`, require exactly 167 bytes, and preserve those bytes.
3. Insert the batch and every event in one database transaction.
4. Enforce unique `batch_id` and `event_id` constraints.
5. A byte-for-byte equivalent duplicate is successful and returns
   `duplicate: true`.
6. A reused ID with conflicting immutable content returns HTTP 409.
7. Return a 2xx response only after commit and echo the exact `batch_id`.
8. Use explicit 4xx errors for invalid or unsupported payloads and 5xx errors
   for retryable server failures.

## Version policy

- `schema_version` describes the HTTP payload. Unknown versions are rejected.
- `collector_version` describes the Pi software and is stored verbatim.
- `decoder_version` is per sample; a batch may legitimately contain more than
  one after an upgrade.
- Unknown decoder versions are accepted because the raw frame is authoritative.
- Server decoders create separate versioned projections rather than overwriting
  the Pi-provided `metrics`.

## Backlog behavior

The Pi may deliver days or months of history after an outage. The API must not
assume events arrive in timestamp order, and its request limits must accept the
configured Pi batch size of 20,000 samples. Ingestion should stream/decompress
with explicit compressed and expanded-body limits to prevent resource abuse.

The Pi deletes nothing until acknowledgment, keeps acknowledged samples for
seven additional days, and retries failed pending batches with the same IDs.
