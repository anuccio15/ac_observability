# Implementation plan

## Phase 1: ingestion foundation

- Scaffold Compose, FastAPI, PostgreSQL, migrations, configuration, and tests.
- Implement health/readiness and transactional idempotent batch ingestion.
- Seed the metric catalog from the Pi decoder definitions.
- Add fixtures from the captured Pi frames and prove duplicate/conflict behavior.
- Provide backup and restore scripts before using the database as the only server
  copy.

Exit condition: the Pi can flush a copied test backlog repeatedly without loss
or duplication, and acknowledged IDs match exactly.

## Phase 2: query and projection layer

- Port the versioned Bosch decoder into a shared server module.
- Store immutable edge metrics and raw frames plus decoder projections.
- Add device, event, metric catalog, and series APIs.
- Implement resolution selection and initial 1-minute/hourly rollups.
- Add re-decode jobs that are restart-safe and idempotent.

Exit condition: captured samples and synthetic long-range data return correct,
bounded chart series and can be re-decoded without mutating originals.

## Phase 3: web application

- Build the overview, performance charts, event explorer, and collector status.
- Add responsive/PWA behavior, UTC-to-device-timezone handling, loading/error
  states, and accessible chart alternatives.
- Export selected ranges to CSV/JSON.

Exit condition: desktop and phone layouts answer the five primary product
questions using both real samples and gap/failure fixtures.

## Phase 4: deployment and operations

- Build multi-architecture images and production Compose configuration.
- Configure DSM reverse proxy, TLS, secrets, volumes, and restart policies.
- Benchmark ingestion of at least a 20,000-sample batch and a simulated year.
- Test backup restore, duplicate delivery, power interruption, and disk pressure.
- Measure whether PostgreSQL/Container Manager prevents the desired Synology
  hibernation and choose an evidence-based power policy.

Exit condition: a clean Synology deployment can ingest the Pi backlog, survive
restart, restore from backup, and serve bounded chart queries.

## Deferred until supported by data

- Confirmed Bosch fault-word mapping
- Automated anomaly detection
- Native mobile application
- Multi-home/multi-user authorization
- Automated NAS shutdown after ingestion
- Sending commands to HVAC equipment
