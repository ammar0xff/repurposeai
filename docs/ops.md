# Operations runbook (homie)

Homie is the single production box: Ubuntu VM on Tailscale
(`ammar@100.112.4.10`), systemd user units, no Docker daemon.
Everything the box does is declared here; nothing hand-rolled.

## Services and timers

```
systemctl --user list-timers          # all three below
```

| Unit                | Cadence | What it does                                    |
| ------------------- | ------- | ----------------------------------------------- |
| `repurposeai-cd`    | 1 min   | pull-based CD: fetch origin/main, deploy, alembic, restart |
| `repurposeai-watch` | 5 min   | health probe + CD-status surfacing (status file)|
| `repurposeai-backup`| 03:00   | nightly snapshot of data/ (14-day rotation)     |

## Status files (surfaced, not pushed anywhere yet)

| File | Meaning |
| ---- | ------- |
| `~/repurposeai-health.status` | `OK/DOWN <ts> \| <last deploy>` written by watch.sh |
| `~/repurposeai-deploy-status` | `ok <ts> <sha>` (deploy succeeded) or `fail <ts> <sha>` (CD failed) |
| `~/repurposeai-errors.log`    | append-only failure lines since last rotation |
| `~/backups/rpa/latest.txt`    | last backup manifest (db bytes + projects.tar.gz bytes) |

```sh
# one-line health check from Termux:
ssh homie "cat ~/repurposeai-health.status"

# inspect a failed deploy:
ssh homie "journalctl --user -u repurposeai-cd.service -r -n 30"
```

An operator alerting channel (ntfy / webhook / email) is deliberately **not**
shipped; the hooks are the two files above. Wire `watch.sh` when a channel
matters.

## Backups and restore

Backups land in `~/backups/rpa/<YYYYmmdd-HHMMSS>/`:
- `rpa.db` — consistent copy via `sqlite3 .backup` (safe while API writes).
- `projects.tar.gz` — all project media / renders / exports under `data/projects`.
- Rotation keeps the newest 14 snapshots.

Restore (drill, don't wing it in an incident):
```sh
ssh homie "systemctl --user stop repurposeai"
ssh homie "cp ~/repurposeai/data/rpa.db ~/repurposeai/data/rpa.db.corrupt-$(date +%s)"
ssh homie "cp ~/backups/rpa/<SNAPSHOT>/rpa.db ~/repurposeai/data/rpa.db"
ssh homie "tar -xzf ~/backups/rpa/<SNAPSHOT>/projects.tar.gz -C ~/repurposeai/data"
ssh homie "systemctl --user start repurposeai"
ssh homie "curl -fsS http://127.0.0.1:8001/api/system/health"
```

## Incident response

1. Read the status files first (fast, no SSH debugging needed):
   `~/repurposeai-health.status`, `~/repurposeai-deploy-status`, `~/repurposeai-errors.log`.
2. `DOWN` + `fail` deployment → `journalctl --user -u repurposeai-cd.service -r -n 40`
   (common cause: alembic rejected a migration or pip install broke).
3. `DOWN` but the last deploy was `ok` → app crash:
   `journalctl --user -u repurposeai -r -n 40`, then
   `systemctl --user restart repurposeai` and re-check the health status.
4. Alembic stuck / half-applied → do NOT hand-fix the DB; restore the
   last good backup and retry the deploy after fixing the migration.
5. DB full / disk pressure → `du -sh ~/backups ~/repurposeai/data`; older
   snapshots rotate automatically at 14.

## Database facts

- Production DB: `~/repurposeai/data/rpa.db`, alembic at 0005
  (0001 initial, 0002 profiles, 0003 … , 0004 campaigns, 0005 reconcile).
- `data/repurposeai.db` is a legacy phantom from the old `alembic.ini` path —
  it no longer exists; do not recreate it.
- `candidate_scores.profile` exists in DB and model (0005 reconciliation).

## Deploy key / auth facts

- Homie pulls via read-only GitHub deploy key `~/.ssh/id_repurposeai_cd`
  (GitHub id: 162924505); origin = `git@github.com:ammar0xff/repurposeai.git`.
- No `.env` on homie; runtime config is passed as systemd `Environment=`.
- Tailscale-only: GitHub-hosted runners cannot reach homie; do not reintroduce
  GitHub-action SSH deploys.