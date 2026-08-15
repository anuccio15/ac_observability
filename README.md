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

The browser dashboard and decoded telemetry query APIs are the next phase; the
durable, authenticated Pi ingestion path is ready first so data collection can
begin without waiting for the visualization layer.

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
# Replace both example passwords/tokens in .env.
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
docker-compose up -d --build
```

If the alias was added during the current SSH session, load it once with
`. ~/.profile`. New SSH sessions load it automatically.

Check container and API health:

```bash
docker-compose ps
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/ready
```

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
