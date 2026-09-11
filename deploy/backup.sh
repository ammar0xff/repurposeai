#!/usr/bin/env bash
# Nightly backup of the production data (rpa.db + data/projects), rotation 14d.
# Runs via repurposeai-backup.timer (systemd user). Safe pause: sqlite .backup
# snapshots under a read lock, so no corrupt copy if the API is writing.
set -euo pipefail

REPO="$HOME/repurposeai"
ROOT="$HOME/backups/rpa"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="$ROOT/$TS"
KEEP=14

mkdir -p "$DEST"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$REPO/data/rpa.db" ".backup '$DEST/rpa.db'"
else
  # WAL-safe fallback via Python's online backup API (a plain `cp` would miss
  # committed data still sitting in -wal).
  "$REPO/.venv/bin/python" - "$REPO/data/rpa.db" "$DEST/rpa.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
sqlite3.connect(src).backup(sqlite3.connect(dst))
PY
fi

# Project assets (media, renders, exports) - best effort if dir missing.
if [ -d "$REPO/data/projects" ]; then
  tar -czf "$DEST/projects.tar.gz" -C "$REPO/data" projects
fi

printf '%s\trpa.db bytes=%s\tprojects.tar.gz=%s\n' \
  "$(date -Is)" \
  "$(stat -c%s "$DEST/rpa.db")" \
  "$(stat -c%s "$DEST/projects.tar.gz" 2>/dev/null || echo 0)" \
  > "$ROOT/latest.txt"

# Rotate: keep the newest KEEP snapshots.
ls -1d "$ROOT"/*/ 2>/dev/null | sort -V | head -n -"$KEEP" | xargs -r rm -rf

echo "[backup] ok $DEST"