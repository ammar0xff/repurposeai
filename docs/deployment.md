# Deployment

## Local: `docker compose up`

Builds backend (API+worker), frontend (nginx), named volume `rpa-data`.
Healthchecks on `/api/system/health` and `/`.

## Single Linux server

1. `cp .env.example .env.prod`, set `AUTH_TOKEN`, `CORS_ORIGINS`, model config.
2. Reverse proxy (Caddy/nginx) terminating HTTPS in front of `:80` (frontend)
   which proxies `/api/` to backend `:8000`.
3. Run backend + worker via compose or systemd (`deploy/` has unit examples).
4. Persistent volumes for `./data` (SQLite file, media, clips). Back up the
   folder nightly (SQLite: `sqlite3 data/repurposeai.db .backup`).

## GPU server (optional)

Use an NVIDIA base image variant, set `WHISPER_DEVICE=cuda`,
`WHISPER_COMPUTE_TYPE=float16`. Nothing else changes; the pipeline
auto-selects the device from config.

## Production compose

`docker-compose.prod.yml` adds Postgres 16 (set `DB_PASSWORD`, point
`DATABASE_URL` at it, run `alembic upgrade head` once against it).

## Continuous deployment (optional)

`.github/workflows/cd.yml` syncs `main` to homie on every push and restarts
the service. It runs only when these repo secrets exist (otherwise skipped):

- `HOMIE_HOST`, `HOMIE_USER`, `HOMIE_SSH_KEY` (ed25519, no passphrase)

The job runs migrations, reinstalls the package, and health-checks
`/api/system/health` before finishing.
