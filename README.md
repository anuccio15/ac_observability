# AC Metrics

Self-contained telemetry ingestion, storage, analysis, and visualization for the
Bosch IDS Premium Connected edge collector.

The Phase 1 ingestion foundation is implemented. The Docker Compose application runs locally
and later on a Synology NAS without depending on hosted databases or proprietary
cloud services. The same application image can run on GCP with its
`AC_DATABASE_URL` pointed at Cloud SQL for PostgreSQL.

## Chosen architecture

- **API and background jobs:** Python 3.13 with FastAPI
- **Database:** PostgreSQL 16 using a Docker-managed persistent volume
- **Web application:** React, TypeScript, Vite, and Apache ECharts
- **Packaging:** one multi-stage application image plus PostgreSQL, orchestrated
  by Docker Compose
- **Reverse proxy/TLS:** Synology DSM reverse proxy in production; direct local
  port binding during development
- **Source of truth:** immutable raw Bosch frames plus versioned interpretations

PostgreSQL is preferred over server-side SQLite because the five-second stream
produces about 6.3 million events per device per year, while chart queries,
backfills, and ingestion may run concurrently. No PostgreSQL extensions are
required, keeping the deployment portable across Synology models.

## Design documents

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Pi ingestion contract](docs/PI_INGESTION_CONTRACT.md)
- [Product and dashboard design](docs/PRODUCT_DESIGN.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Synology deployment](docs/SYNOLOGY_DEPLOYMENT.md)

## Repository shape

```text
ac_metrics/
├── compose.yaml
├── .env.example
├── Dockerfile
├── server/
│   ├── app/
│   ├── migrations/
│   └── tests/
├── docs/
└── scripts/
```

The durable ingestion path and browser dashboard are implemented. Raw frames and
the Pi's decoded metrics remain authoritative; future decoder improvements can
add versioned server-side projections without rewriting either source.

## Dashboard and read APIs

The production container serves the authenticated AC Observatory dashboard at `/`. It refreshes
hourly and on manual sync, and provides responsive compressor, thermal, refrigerant,
pressure, electrical, cycle, connectivity-alert, daily-summary, and urgent-event
views. Read-only data endpoints include:

```text
GET /api/v1/devices
GET /api/v1/telemetry/latest
GET /api/v1/telemetry/series
GET /api/v1/summary
GET /api/v1/cycles
GET /api/v1/faults
GET /api/v1/daily-summaries
GET /api/v1/edge/status
POST /api/v1/edge/status/check
POST /api/v1/edge/sync
GET /api/v1/metrics/catalog
```

Time-series requests accept a device, comma-separated numeric metrics, timezone-
aware start/end values, and a maximum point count. The server selects a bucket
size automatically so long ranges remain chartable without discarding raw events.

## Core invariants

1. An event is acknowledged only after its entire batch commits successfully.
2. `batch_id` and `event_id` are idempotency keys; retries never duplicate data.
3. The raw 167-byte Bosch frame is immutable and retained independently of any
   decoded representation.
4. Decoder changes create a new projection; they never rewrite the original Pi
   interpretation.
5. The server may be offline for days. The Pi remains the durable edge buffer.
6. The first release is read-only toward HVAC equipment; the server has no
   Bluetooth or control path.

## Development quick start

```bash
cp .env.example .env
# Replace the database password and edge token, then configure the dashboard login.
python3 scripts/configure_dashboard_auth.py
docker compose config
docker compose up -d --build
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

## Synology start and operations

The current Synology deployment is cloned at `~/projects/ac_observability`. Its
user profile defines `docker-compose` as the verified Compose v2 binary and adds
the required `sudo`, so run these commands **without** putting another `sudo` in
front of them.

SSH to the NAS and start or rebuild the application:

```bash
ssh alexnuccio@192.168.0.117
cd ~/projects/ac_observability
python3 scripts/configure_dashboard_auth.py
docker-compose up -d --build
```

The authentication setup prompts for the `admin` password twice, writes only a
PBKDF2 password hash plus a random session-signing secret to the uncommitted
`.env`, and never prints or stores the plaintext password. Run it again whenever
the password should change. Existing browser sessions are invalidated because a
new signing secret is generated. Login sessions last seven days by default.

Set `AC_DASHBOARD_COOKIE_SECURE=true` after the HTTPS reverse proxy hostname is
working. Leave it false only while accessing the dashboard directly over local
HTTP. Health/readiness probes and the Pi's bearer-token ingestion endpoint remain
independent of the dashboard login.

If the alias was added during the current SSH session, load it once with
`. ~/.profile`. New SSH sessions load it automatically.

Check container and API health:

```bash
docker-compose ps
curl --fail http://127.0.0.1:8081/health
curl --fail http://127.0.0.1:8081/ready
```

This NAS uses port `8081` because its existing nginx service occupies `8080`.
The published port is controlled by `AC_PORT` in `.env`. Configure
`AC_PI_API_URL` and `AC_PI_API_TOKEN` to enable the dashboard's manual sync
button. It asks the Pi to use its normal acknowledged batch uploader, and only
then refreshes the charts and paginated tables.

The server performs a read-only Pi health check once per hour and whenever the
dashboard loads or manually syncs. It distinguishes Pi unreachable, Bosch
Bluetooth disconnected, stale telemetry, healthy, and not-yet-checked states.
Only state changes are retained in the alert history. Because the Synology may
sleep, the dashboard always displays the last check time; a sleeping NAS cannot
detect an outage until it wakes. `AC_PI_STATUS_INTERVAL_SECONDS` controls the
schedule and defaults to 3600 seconds.

Daily summaries are calculated deterministically from stored telemetry using the
browser's local timezone. They report cooling runtime, cycles, temperature,
compressor demand, telemetry coverage/gaps, prior-day changes, and a seven-day
runtime baseline. Electrical consumption is presented as a visibly labeled
candidate estimate while the raw-field mappings await EasyAir confirmation.

Decoder-v2 candidate analysis also exposes outdoor-unit watts, total input
current, power factor, fan current/stage, and EEV opening directly from immutable
raw frames. Historical energy tables integrate watts only across contiguous
observations, so collector outages are excluded instead of being counted as zero
usage. These figures cover the outdoor unit, not the indoor blower or auxiliary
heat, and remain visibly marked as candidates pending EasyAir confirmation.

View recent logs or follow them live:

```bash
docker-compose logs --tail=100 app db migrate
docker-compose logs --follow app
```

Restart or stop the application:

```bash
docker-compose restart
docker-compose down
```

`docker-compose down` removes the containers and network but preserves the
PostgreSQL named volume. Do not add `--volumes` unless intentionally deleting the
database. To deploy updates:

```bash
git pull --ff-only
docker-compose up -d --build
```

Run isolated PostgreSQL integration tests with:

```bash
docker compose --profile test run --rm test
docker compose --profile test down
```

Create a verified PostgreSQL custom-format backup with `./scripts/backup.sh`.
Restores require an explicit confirmation variable; see the script before use.

## Portability boundary

Application code depends only on PostgreSQL and environment variables. A future
GCP deployment can use the same image with Cloud Run or GKE plus Cloud SQL. DSM
reverse-proxy settings, local Compose volumes, and Wake-on-LAN remain deployment
concerns and do not enter the ingestion or query layers.
