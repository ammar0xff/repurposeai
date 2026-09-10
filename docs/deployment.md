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
## Continuous deployment (homie)

GitHub-hosted runners can't SSH into homie (Tailscale-only IP), so homie runs
**pull-based CD**: a systemd user timer polls every minute and redeploys when
`origin/main`'s SHA changes.

Installation (one-time, on homie):
```bash
mkdir -p ~/.config/systemd/user
cp deploy/repurposeai-cd.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now repurposeai-cd.timer
```

`deploy/pull_deploy.sh` then: fetches `origin/main` (via GitHub deploy key, see
below), `git reset --hard` (tracked files only; `.venv`, `data/`, secrets kept),
`pip install -e .`, `alembic upgrade head` against `data/rpa.db`, and restarts
the service. The timer needs the repo clone's `origin` set to the SSH remote:

```bash
git remote set-url origin git@github.com:ammar0xff/repurposeai.git
# + a read-only GitHub deploy key installed at ~/.ssh/id_repurposeai_cd
#   with ~/.ssh/config: Host github.com → IdentityFile ~/.ssh/id_repurposeai_cd
```
