#!/usr/bin/env bash
# Pull-based CD for homie (runs from a systemd user timer, see *.timer).
# GitHub-hosted runners can't SSH into homie (Tailscale-only), so homie polls
# origin/main itself and redeploys when the SHA changes.
# Only tracked files are replaced; untracked (.venv, data/, secrets) are kept.
set -euo pipefail

REPO="$HOME/repurposeai"
DB_URL="sqlite:///./data/rpa.db"

cd "$REPO"
git fetch origin -q

if git diff --quiet HEAD origin/main; then
  exit 0
fi

echo "[deploy] $(date -Is) applying $(git rev-parse --short origin/main)"
git reset --hard -q origin/main
.venv/bin/pip install -q -e .
export DATABASE_URL="$DB_URL"
.venv/bin/alembic upgrade head
systemctl --user restart repurposeai
echo "[deploy] ok $(date -Is)"