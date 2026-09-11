#!/usr/bin/env bash
# Watchdog: probes the API health endpoint every 5 min and surfaces CD failures.
# Does NOT alert on its own - it keeps a human-readable status file that an
# operator (or future notify/ntfy/webhook hook) can check.
#   ~/repurposeai-health.status   OK|DOWN + timestamp (+ last deploy status)
#   ~/repurposeai-errors.log      append-only failure lines since rotation
set -euo pipefail

STATUS_FILE="$HOME/repurposeai-health.status"
ERROR_LOG="$HOME/repurposeai-errors.log"
DEPLOY_STATUS="$HOME/repurposeai-deploy-status"

NOW="$(date -Is)"
UP=1
if ! curl -fsS -m 10 http://127.0.0.1:8001/api/system/health >/dev/null 2>&1; then
  UP=0
fi

# Last deploy result (written by pull_deploy.sh). Absent = never deployed yet.
DEPLOY="$(cat "$DEPLOY_STATUS" 2>/dev/null || echo "no deploy yet")"

if [ "$UP" = "1" ]; then
  printf 'OK %s | %s\n' "$NOW" "$DEPLOY" > "$STATUS_FILE"
else
  printf 'DOWN %s | %s\n' "$NOW" "$DEPLOY" > "$STATUS_FILE"
  printf '%s API health DOWN (app restart pending?)\n' "$NOW" >> "$ERROR_LOG"
fi