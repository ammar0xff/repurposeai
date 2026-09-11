#!/usr/bin/env bash
# Pull-based CD for homie (runs from a systemd user timer, see *.timer).
# GitHub-hosted runners can't SSH into homie (Tailscale-only), so homie polls
# origin/main itself and redeploys when the SHA changes.
# Only tracked files are replaced; untracked (.venv, data/, secrets) are kept.
set -euo pipefail

REPO="$HOME/repurposeai"
DB_URL="sqlite:///./data/rpa.db"
STATUS_FILE="$HOME/repurposeai-deploy-status"

# Surface any failure to the 5-min watchdog (~/repurposeai-health.status).
trap 'printf "fail %s %s\n" "$(date -Is)" "$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)" > "$STATUS_FILE"' ERR

cd "$REPO"
git fetch origin -q

if git diff --quiet HEAD origin/main; then
  exit 0
fi

echo "[deploy] $(date -Is) applying $(git rev-parse --short origin/main)"
rm -f "$STATUS_FILE"
git reset --hard -q origin/main
.venv/bin/pip install -q -e .
export DATABASE_URL="$DB_URL"
# Adopt a pre-existing DB that was born via init_db()/create_all: if it has
# tables but no alembic_version, stamp at head (schema == current model,
# verified) instead of replaying CREATE TABLE that would collide.
NEEDS_STAMP=$(
  .venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("data/rpa.db")
has = c.execute("select 1 from sqlite_master where type='table' and name='alembic_version'").fetchone()
tables = c.execute("select count(*) from sqlite_master where type='table' and name not like 'sqlite_%'").fetchone()[0]
print(1 if (not has and tables) else 0)
PY
)
if [ "${NEEDS_STAMP:-0}" = "1" ]; then
  echo "[deploy] adopting existing DB (stamp head)"
  .venv/bin/alembic stamp head
fi
.venv/bin/alembic upgrade head
systemctl --user restart repurposeai
SHA="$(git rev-parse --short HEAD)"
echo "[deploy] ok $(date -Is)"
printf 'ok %s %s\n' "$(date -Is)" "$SHA" > "$STATUS_FILE"