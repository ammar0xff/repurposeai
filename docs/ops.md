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

## API operations (health, jobs, metrics)

Auth: Bearer token from `AUTH_TOKEN` or `POST /api/auth/login`; without either the
API is open (dev mode). All paths under `/api`.

```
curl -fsS http://127.0.0.1:8001/api/system/health        # liveness (no auth)
curl -fsS http://127.0.0.1:8001/api/system/readiness     # db/storage/ffmpeg/stt/llm probe
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/system/metrics
curl -fsS -H "Authorization: Bearer $TOKEN" -X POST http://127.0.0.1:8001/api/jobs/$JID/retry
```

- `metrics` → queue depth by status, running jobs with heartbeat age, stale running
  ids (vs `WORKER_STALE_TIMEOUT`), recent failures, disk free, DB size. The ops
  dashboard.
- `jobs/{id}/retry` → a terminal failed/cancelled job back to `queued`, resuming
  from the interrupted stage (done stages are skipped; source key is re-resolved
  from the project if missing). Returns 409 while a job is still active, 404 unknown.

State machine: `queued → running → ready_for_review | failed | cancelled`.

## Worker liveness (heartbeats)

Every stage transition and long-running loop (`receive`, `resolve_render`)
touches `ProcessingJob.last_heartbeat`. The dispatcher loop (3s) reaps any
`running` job whose heartbeat is older than `WORKER_STALE_TIMEOUT` (default 1800s;
ingest download alone can legitimately run ~1800s, so keep it >= that) and marks it
`failed` with `JobInterrupted: worker lost contact (no heartbeat >Ns)`. Jobs that
failed midway never get stuck `running`; retry resumes them. Verify with
`system/metrics` → `stale_running` should be empty.

## Database facts

- Production DB: `~/repurposeai/data/rpa.db`, alembic at 0006
  (0001 initial, 0002 profiles, 0003 … , 0004 campaigns, 0005 reconcile,
  0006 job heartbeat). `ProcessingJob.last_heartbeat` lives on 0006.
- SQLite runs in WAL mode (`journal_mode=WAL`, `synchronous=NORMAL`,
  `busy_timeout=10000`, `foreign_keys=ON`) — set by the app on every connection,
  not by the `sqlite3` CLI default.
- `data/repurposeai.db` is a legacy phantom from the old `alembic.ini` path —
  it no longer exists; do not recreate it.
- `candidate_scores.profile` exists in DB and model (0005 reconciliation).

## Remote STT via GitHub Actions (optional)

Homie cannot run faster-whisper (SIGILL/oomd), so transcription can be farmed
out to a GitHub runner even though homie is Tailscale-only:

1. Create a classic PAT with `gist` + `repo` scopes.
2. Put it on homie: `~/repurposeai/.env` →
   `GITHUB_TOKEN=…`, `GITHUB_OWNER=ammar0xff`, `GITHUB_REPO=repurposeai`
   (`STT_PROVIDER=auto` enables remote fallback when local STT is absent;
   `github` forces remote only).
3. Mirror the same PAT as the GH repo secret `REMOTE_STT_PAT`
   (`gh secret set REMOTE_STT_PAT` — the workflow token cannot write gists).
4. Trigger remotely: run a job with `params.stt_provider=github`, or
   `rpa transcribe <project> --stt auto|github`.

Mechanics: provider pushes the extracted 16k wav to a private gist, dispatches
`remote-transcribe`, polls for `transcript.json`, sha256-verifies it, deletes
the mailbox, then the pipeline resumes locally. Limit: wav <= 8 MiB.

## Deploy key / auth facts

- Homie pulls via read-only GitHub deploy key `~/.ssh/id_repurposeai_cd`
  (GitHub id: 162924505); origin = `git@github.com:ammar0xff/repurposeai.git`.
- Runtime config = systemd `Environment=` (DATABASE_URL, PORT); a `~/.env` may
  add optional STT env (unit env still wins via pydantic precedence).
- Tailscale-only: GitHub-hosted runners cannot reach homie; do not reintroduce
  GitHub-action SSH deploys.