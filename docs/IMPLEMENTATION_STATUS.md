# Implementation status

## Completed in server v0.1.0

- Portable Python 3.13 application image and PostgreSQL 16 Compose deployment
- Separate one-shot migration service with readiness ordering
- FastAPI liveness, database readiness, OpenAPI, and metric catalog endpoints
- Bearer-token authentication isolated to the Pi ingestion role
- Bounded streaming of gzip bodies and bounded decompression
- Strict upload schema, timezone, Bluetooth address, SHA-256 ID, 167-byte frame,
  frame marker, and Bosch checksum validation
- Transactional idempotent ingestion with per-device advisory locking
- Immutable raw frame, Pi metrics, decoder version, and content digests
- Correct duplicate acknowledgment and HTTP 409 conflict behavior
- Independent batch/event membership for overlapping retries
- Initial 25-entry confirmed/candidate/derived metric catalog
- Alembic migration and isolated PostgreSQL integration-test profile
- Non-root, read-only application container with bounded logs
- Verified custom-format PostgreSQL backup and guarded restore scripts
- Synology/GCP portability boundary documented

## Completed in server v0.2.0

- Device inventory and latest-sample APIs
- Automatically bucketed multi-metric time-series API
- Windowed summary aggregates and data freshness metadata
- On-demand operating-segment detection with duration and compressor statistics
- Read-only urgent/fault event feed
- Responsive React and Apache ECharts dashboard served by the application image
- Desktop and 390-pixel mobile visual QA with no browser console errors
- Secure Pi-to-Synology configuration with three-hour scheduled delivery,
  immediate urgent delivery, and one-minute durable retry
- First live Pi backfill acknowledged with 341 samples and zero remaining backlog

## Verification record

- 12 local unit/API tests passed for v0.1.0.
- 18 tests pass against an isolated PostgreSQL 16 container in v0.2.0.
- Production Compose smoke test completed `db → migrate → app` successfully.
- `/health` and `/ready` returned healthy/ready with migration `0001_initial`.
- A real-format captured Bosch frame was accepted once and returned
  `duplicate: true` on retry; PostgreSQL retained one batch and one event.
- Backup was created, validated with `pg_restore --list`, restored, and retained
  one batch, one event, and all 25 metric definitions.
- All disposable containers, test databases, volumes, and smoke credentials were
  removed after verification.

## Next implementation slice

1. Port decoder v1 to create immutable server-side projections.
2. Add persisted minute/hour/day rollups after real query volume requires them.
3. Add cycle and fault materialization when on-demand range queries become costly.
4. Add optional dashboard authentication before exposing it outside the LAN.
5. Add Synology reverse-proxy TLS and automated logical backup scheduling.
