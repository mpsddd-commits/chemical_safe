#!/usr/bin/env bash
# ID-9 - PostgreSQL dump.
#
# The initial index takes up to eight hours (NFR-4), so losing safeenv_pgdata is
# expensive even though every document could in principle be re-collected.
# Run this before `docker compose down -v`.
set -euo pipefail

STACK="${STACK:-safeenv}"
CONTAINER="${CONTAINER:-safeenv-postgres}"
OUT_DIR="${OUT_DIR:-./backups}"
DB_USER="${POSTGRES_USER:-safeenv}"
DB_NAME="${POSTGRES_DB:-safeenv}"

mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$OUT_DIR/${STACK}-${STAMP}.dump"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "error: $CONTAINER is not running. Start the stack first." >&2
  exit 1
fi

echo "dumping $DB_NAME from $CONTAINER ..."
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$TARGET"

SIZE="$(du -h "$TARGET" | cut -f1)"
echo "done: $TARGET ($SIZE)"
echo
echo "note: retained originals under ./data/originals are NOT included."
echo "      They are already on the host filesystem; back them up separately"
echo "      if this machine is not itself backed up."
