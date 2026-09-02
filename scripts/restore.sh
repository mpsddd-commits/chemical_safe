#!/usr/bin/env bash
# ID-9 - restore a dump produced by backup.sh.
set -euo pipefail

CONTAINER="${CONTAINER:-safeenv-postgres}"
DB_USER="${POSTGRES_USER:-safeenv}"
DB_NAME="${POSTGRES_DB:-safeenv}"

if [ $# -ne 1 ]; then
  echo "usage: $0 ./backups/safeenv-YYYYmmdd-HHMMSS.dump" >&2
  exit 64
fi

DUMP="$1"
[ -f "$DUMP" ] || { echo "error: no such file: $DUMP" >&2; exit 66; }

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "error: $CONTAINER is not running. Start the stack first." >&2
  exit 1
fi

echo "This OVERWRITES the current contents of '$DB_NAME'."
read -r -p "Continue? [y/N] " reply
case "$reply" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "aborted"; exit 0 ;;
esac

echo "restoring $DUMP ..."
docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < "$DUMP"
echo "done."
echo "run 'docker compose exec app python -m app.cli stats' to verify."
