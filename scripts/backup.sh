#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

env_file="${AC_ENV_FILE:-.env}"
if [[ ! -f "$env_file" ]]; then
  echo "Missing environment file: $env_file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$env_file"
set +a

backup_dir="${AC_BACKUP_DIR:-$project_dir/backups}"
mkdir -p "$backup_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="$backup_dir/ac_metrics_${timestamp}.dump"

docker compose exec -T db pg_dump \
  --username "${POSTGRES_USER:-ac_metrics}" \
  --dbname "${POSTGRES_DB:-ac_metrics}" \
  --format custom \
  --no-owner > "$destination"

if [[ ! -s "$destination" ]]; then
  echo "Backup failed: output file is empty" >&2
  exit 1
fi

docker compose exec -T db pg_restore --list < "$destination" >/dev/null
echo "Backup written and verified: $destination"
