#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

dump_path="${1:-}"
if [[ -z "$dump_path" || ! -f "$dump_path" ]]; then
  echo "Usage: CONFIRM_RESTORE=ac_metrics $0 /path/to/backup.dump" >&2
  exit 1
fi
if [[ "${CONFIRM_RESTORE:-}" != "ac_metrics" ]]; then
  echo "Restore replaces the current database. Set CONFIRM_RESTORE=ac_metrics." >&2
  exit 1
fi
env_file="${AC_ENV_FILE:-.env}"
if [[ ! -f "$env_file" ]]; then
  echo "Missing environment file: $env_file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$env_file"
set +a

database="${POSTGRES_DB:-ac_metrics}"
user="${POSTGRES_USER:-ac_metrics}"

docker compose stop app
docker compose exec -T db pg_restore \
  --username "$user" \
  --dbname "$database" \
  --clean \
  --if-exists \
  --no-owner < "$dump_path"
docker compose run --rm migrate
docker compose up -d app

ready_url="http://127.0.0.1:${AC_PORT:-8080}/ready"
for _attempt in {1..30}; do
  if curl --fail --silent --show-error "$ready_url" >/dev/null; then
    echo "Restore completed and API is ready: $dump_path"
    exit 0
  fi
  sleep 2
done

echo "Restore completed, but API readiness timed out: $ready_url" >&2
docker compose logs --tail=50 app migrate >&2
exit 1
