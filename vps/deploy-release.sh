#!/usr/bin/env bash

set -Eeuo pipefail

readonly RELEASE_ARCHIVE="/tmp/estadia20-release.tgz"
readonly APP_DIR="/opt/estadia20"
readonly NEXT_DIR="/opt/estadia20.next"
readonly PREVIOUS_DIR="/opt/estadia20.previous"
readonly SERVICE_NAME="estadia20.service"
readonly LOCAL_HEALTH_URL="http://127.0.0.1:3011/api/health"
readonly MAX_ARCHIVE_BYTES=$((50 * 1024 * 1024))

if [[ "$#" -ne 1 || "$1" != "$RELEASE_ARCHIVE" ]]; then
  echo "Usage: $0 $RELEASE_ARCHIVE" >&2
  exit 64
fi

if [[ ! -f "$RELEASE_ARCHIVE" || -L "$RELEASE_ARCHIVE" ]]; then
  echo "Release archive is missing or invalid." >&2
  exit 66
fi

archive_size="$(stat -c '%s' "$RELEASE_ARCHIVE")"
if (( archive_size <= 0 || archive_size > MAX_ARCHIVE_BYTES )); then
  echo "Release archive size is outside the allowed range." >&2
  exit 65
fi

exec 9>"/run/lock/estadia20-deploy.lock"
if ! flock -n 9; then
  echo "Another roomies20 deployment is running." >&2
  exit 75
fi

if ! python3 - "$RELEASE_ARCHIVE" <<'PY'
import pathlib
import sys
import tarfile

archive_path = sys.argv[1]
allowed_roots = {"public", "server.py"}

with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    if not members:
        raise SystemExit("Release archive is empty.")

    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Unsafe archive path: {member.name}")
        if not path.parts or path.parts[0] not in allowed_roots:
            raise SystemExit(f"Unexpected archive entry: {member.name}")
        if member.issym() or member.islnk() or member.isdev():
            raise SystemExit(f"Unsupported archive entry: {member.name}")
PY
then
  unlink "$RELEASE_ARCHIVE"
  exit 65
fi

previous_saved=0

rollback() {
  status="$?"
  trap - ERR

  echo "Deployment failed; restoring the previous release." >&2
  if (( previous_saved == 1 )) && [[ -d "$PREVIOUS_DIR" ]]; then
    systemctl stop "$SERVICE_NAME" || true
    rm -rf -- "$APP_DIR"
    mv -- "$PREVIOUS_DIR" "$APP_DIR"
    systemctl start "$SERVICE_NAME" || true
  fi

  rm -rf -- "$NEXT_DIR"
  rm -f -- "$RELEASE_ARCHIVE"
  exit "$status"
}

trap rollback ERR

rm -rf -- "$NEXT_DIR" "$PREVIOUS_DIR"
install -d -m 0755 "$NEXT_DIR"
tar -xzf "$RELEASE_ARCHIVE" -C "$NEXT_DIR" --no-same-owner --no-same-permissions

test -f "$NEXT_DIR/server.py"
test -f "$NEXT_DIR/public/index.html"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile "$NEXT_DIR/server.py"

chown -R root:root "$NEXT_DIR"
find "$NEXT_DIR" -type d -exec chmod 0755 {} +
find "$NEXT_DIR" -type f -exec chmod 0644 {} +

mv -- "$APP_DIR" "$PREVIOUS_DIR"
previous_saved=1
mv -- "$NEXT_DIR" "$APP_DIR"

systemctl restart "$SERVICE_NAME"

healthy=0
for _attempt in {1..20}; do
  if curl -fs "$LOCAL_HEALTH_URL" >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done

if (( healthy != 1 )); then
  false
fi

previous_saved=0
rm -rf -- "$PREVIOUS_DIR"
rm -f -- "$RELEASE_ARCHIVE"
trap - ERR

echo "roomies20 deployment completed successfully."
