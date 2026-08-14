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

## Verification record

- 12 local unit/API tests passed.
- 16 tests passed against an isolated PostgreSQL 16 container.
- Production Compose smoke test completed `db → migrate → app` successfully.
- `/health` and `/ready` returned healthy/ready with migration `0001_initial`.
- A real-format captured Bosch frame was accepted once and returned
  `duplicate: true` on retry; PostgreSQL retained one batch and one event.
- Backup was created, validated with `pg_restore --list`, restored, and retained
  one batch, one event, and all 25 metric definitions.
- All disposable containers, test databases, volumes, and smoke credentials were
  removed after verification.

## Next implementation slice

1. Add device, latest-sample, event pagination, and time-series query APIs.
2. Port decoder v1 to create immutable server-side projections.
3. Add minute/hour/day rollups and automatic chart resolution.
4. Scaffold the React dashboard against those query APIs.
5. Add DSM deployment configuration only after the Synology CPU architecture,
   volume paths, hostname, and TLS/reverse-proxy choices are confirmed.
