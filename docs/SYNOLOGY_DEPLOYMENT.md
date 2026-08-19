# Synology deployment

This service is designed for DSM 7 with Container Manager. It uses standard
multi-architecture Python and PostgreSQL images, so the same repository works on
supported Intel/AMD and ARM64 Synology models. Confirm that the NAS model supports
Container Manager before deployment.

## 1. Prepare persistent storage

Create administrator-only directories on a persistent shared volume. Replace
`volume1` if the NAS uses a different volume name.

```bash
mkdir -p /volume1/docker/ac_metrics/postgres
mkdir -p /volume1/docker/ac_metrics/backups
```

Do not put the PostgreSQL directory in Synology Drive, a bidirectional sync task,
or any filesystem-level backup job while PostgreSQL is running. Use the included
logical backup script for consistent database backups.

## 2. Copy and configure the application

Copy this repository to `/volume1/docker/ac_metrics/app`, then create `.env` from
the example. Generate independent secrets rather than reusing a DSM password.

```bash
cd /volume1/docker/ac_metrics/app
cp .env.example .env
python3 scripts/configure_dashboard_auth.py
openssl rand -hex 32
openssl rand -hex 32
```

Set the generated values in `.env` and enable the persistent bind mount:

```dotenv
POSTGRES_DB=ac_metrics
POSTGRES_USER=ac_metrics
POSTGRES_PASSWORD=<first-generated-secret>
AC_DATABASE_URL=postgresql+psycopg://ac_metrics:<first-generated-secret>@db:5432/ac_metrics
AC_EDGE_API_TOKEN=<second-generated-secret>
AC_POSTGRES_DATA_PATH=/volume1/docker/ac_metrics/postgres
AC_PORT=8080
```

If the database password contains URL-reserved punctuation it must be URL encoded
inside `AC_DATABASE_URL`. Hex output from the command above needs no encoding.
Keep `.env` private and supply the same `AC_EDGE_API_TOKEN` to the Pi collector.
The authentication configurator stores only a PBKDF2 password hash and a random
session-signing secret. After HTTPS is active, set
`AC_DASHBOARD_COOKIE_SECURE=true` and rebuild the app container.

## 3. Validate and start

From an SSH session on the NAS:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/ready
```

`migrate` should exit successfully after applying the database schema. `app` and
`db` should remain healthy. The API listens on NAS port 8080 unless `AC_PORT` is
changed. Do not expose that port directly to the public internet.

## 4. Connect the Pi

Configure the Pi's upstream endpoint as:

```text
http://<nas-lan-address>:<AC_PORT>/v1/telemetry/batches
```

Use the same edge token stored in `.env`. The server accepts gzip-compressed JSON
and acknowledges a batch only after its transaction commits. Both batch and event
identifiers are idempotent, so retrying after a network failure is safe.

## 5. Back up and restore

Run a logical backup from the repository directory:

```bash
AC_BACKUP_DIR=/volume1/docker/ac_metrics/backups ./scripts/backup.sh
```

Schedule that command in DSM Task Scheduler and send the backup directory to the
NAS's normal backup destination. Test restoration periodically against a disposable
database. Restoration is intentionally guarded:

```bash
AC_CONFIRM_RESTORE=yes ./scripts/restore.sh /absolute/path/to/backup.dump
```

The restore script replaces the contents of the configured database. Stop the Pi
uploader and take a fresh backup before restoring production.

## Operational notes

- Container Manager and PostgreSQL background activity can prevent disk hibernation.
  Prefer normal NAS power management over stopping the database each hour.
- Docker log rotation is capped in `compose.yaml`; PostgreSQL data is not capped.
  Add DSM free-space alerts and monitor database growth.
- A Synology reverse proxy can later provide TLS and a friendly hostname for the
  dashboard. Keep ingestion LAN-only unless a secure remote path is deliberately
  configured.
- Before upgrades, run a backup, pull or copy the new source, rebuild, and use
  `docker compose up -d`. Alembic migrations run before the application starts.

## GCP lift-and-shift

The application has no DSM-specific code. Build the same production image, point
`AC_DATABASE_URL` at Cloud SQL for PostgreSQL, provide `AC_EDGE_API_TOKEN` through
Secret Manager, and run the image on Cloud Run or GKE. Replace the Compose migration
container with a one-shot deployment job. Raw frames, idempotency behavior, schema
migrations, and Pi request format remain unchanged.
