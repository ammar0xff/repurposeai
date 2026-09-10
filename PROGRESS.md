# RepurposeAI — build progress (living file)

Goal: production-grade, local-first AI video repurposing platform (spec: 79 sections).
Strategy: vertical slices, reuse proven whopclip core (ported, not rewritten).

## Environment reality (Termux, 2026-09-10)
- Python 3.14, Node 24, ffmpeg 8.1, pytest present. No Docker (ship config, cannot build here).
- Heavy ML (whisper large, mediapipe) stays optional; CPU-first; GPU optional.
- GitHub runner (free 16GB) remains the heavy-STT option via existing clip workflow.

## Slice tracker
- [ ] S0 scaffold: repo, pyproject, Makefile, .env.example, CI, docs skeleton
- [ ] S1 backend core: config, logging, storage abstraction, DB models + Alembic, auth
- [ ] S2 API: projects/jobs/clips/review/exports/system + OpenAPI + tests
- [ ] S3 pipeline services: ingest, analyze, STT, scenes/silence, sentences, candidates, eligibility
- [ ] S4 ranking: provider abstraction (OpenAI-compat/Ollama/local), profiles, structured JSON, resolver
- [ ] S5 render: reframe strategies, captions engine, renderer, render profiles, metadata variants
- [ ] S6 jobs: stages, progress (SSE+poll), cancel, resume, validation, review decisions, export manifest
- [ ] S7 CLI: init/ingest/analyze/transcribe/candidates/rank/render/validate/run/export/doctor (+--json)
- [ ] S8 MCP thin server
- [ ] S9 frontend: React+TS+Vite+Tailwind (Overview/Projects/Jobs/Review/Exports/Settings/System), build verified
- [ ] S10 Dockerfiles + compose + prod compose + deployment docs
- [ ] S11 docs/ (10 files), security doc, final engineering report
- [ ] S12 FINAL VERIFICATION (§79 checklist)

## Decisions log
- Reuse whopclip pipeline logic by porting into services/ (proven on real runs).
- SQLite default, Postgres via DATABASE_URL. No Redis required (DB-backed queue).
- Docker images build green in CI (backend + frontend, 2026-09-10). No daemon on Termux/homie; run images on real hardware.
- No paid APIs anywhere; heuristic fallbacks visible in UI/metadata ("AI unavailable" labeling).

## Known limitations
- Docker images not build-tested (no daemon on this machine).
- Large-model STT/face run on runner-class hardware, not on 2GB boxes.

## Toolchain decision (2026-09-10)
- pydantic-core has NO cp314 android/aarch64 wheel → pip tries a Rust source build.
  Same root cause as ctranslate2/mediapipe. FastAPI/Pydantic/SQLAlchemy stack
  therefore installs on HOMIE (Ubuntu x86_64, wheels OK), not on Termux.
- Rule: pure pipeline logic modules must import NOTHING beyond stdlib (+numpy-free),
  so their unit tests run on Termux. Pydantic/SQLAlchemy live only at API/DB boundary.
- Frontend builds on Termux (node 24 works). Docker images cannot build here (no daemon).

## 2026-09-10 — S0/S3-core progress
- Scaffold + config + storage + providers + media + sentences/candidates/resolver/
  heuristic/captions/reframe/renderer/validation/ranking-service written.
- 10 unit tests PASS on Termux (stdlib-only modules).
- Rule confirmed: pipeline modules stay stdlib-only; pydantic/sqlalchemy/fastapi at boundary.

## 2026-09-10 — S4-S9 progress
- Ranking service (LLM structured + Pydantic-or-manual validation + retry + heuristic),
  reframe strategies, renderer (arg arrays, tracked), validation reports, exporter/manifest.
- API (projects/jobs/clips/review/exports/system+SSE+OpenAPI), auth abstraction, worker
  (DB queue, cancel, resume), CLI (13 commands), MCP thin server, Alembic 0001.
- Frontend React+TS+Vite+Tailwind (7 pages, keyboard review, axes bars) BUILDS on Termux.
- E2E found + fixed: worker session ownership, preuploaded ingest, sqlite mkdir, test isolation.
- 19/19 pytest green on homie. ruff 0, mypy 0 (49 files).
- Homie CPU cannot run PyAV/ctranslate2 wheels (SIGILL) + oomd kills whisper:
  STT availability uses a subprocess probe (never crashes the server); heavy STT
  belongs on runners (GitHub Actions, free 16GB).

## Sync discipline (learned 2026-09-10)
- Termux is source of truth. Push to GitHub; transfer Termux->homie via tar
  of CHANGED files only. Never full-tree pull homie->Termux (it once reverted
  a local fix). `git diff` on homie is for inspection only.

## FINAL ENGINEERING REPORT (2026-09-10)

### Architecture
Layered, inward dependencies: web -> REST/SSE -> api -> services -> pure
pipeline libs; providers/ behind ABCs; DB-backed worker, no Redis required.
Same Pipeline object serves API, CLI, MCP, tests.

### Implemented features
Projects CRUD + upload/download ingest, FFprobe analysis (cached), whisper STT
(word timestamps), scenes (PySceneDetect/ffmpeg) + silence, sentence-aware
candidates, eligibility profiles, structured 6-axis LLM ranking (Pydantic or
manual validation, retry, heuristic fallback, identical schema), resolver
(word boundaries + padding + sentence pull-up), reframe strategies
(center/face/speaker/smart/manual + chain), 5 caption styles (libass),
tracked H264 rendering, 5 render profiles, metadata variants, FFprobe
validation reports, keyboard review with persisted decisions, rerender without
re-STT, export bundles + manifest + portable archives, MCP thin server,
13-command CLI, React UI (7 pages), Docker + prod compose, 10 docs, CI.

### AI providers
LLM: OpenAI-compatible / Ollama / local-reserved / heuristic, selectable via
LLM_PROVIDER; only transcript text sent; bearer server-side. STT:
faster-whisper (tiny..large, int8 CPU default, CUDA-ready). No paid APIs.

### Pipeline
ingest->analyze->transcribe->segment->rank->resolve/render->validate, staged
checkpoints, idempotent resume, cancel flags, per-clip skip-on-exists.

### Database
17 tables, UUID hex PKs, timestamps, FKs, indexes (project/job/status/score/
created), Alembic 0001 with downgrade.

### API / security / testing / deployment
REST + SSE + OpenAPI; bearer-token auth abstraction; ownership-scoped queries;
arg-array subprocess; traversal-proof storage; secrets only in .env (audit
clean 2026-09-10). Tests: 19 green (14 unit anywhere + 5 integration), CI:
ruff+mypy+pytest+tsc+vite build+heavy STT E2E narrated fixture on free runner.

### Known limitations
- No Docker daemon on build machine: images not build-tested.
- 2GB homie: no local whisper/face (SIGILL+oomd); STT belongs on runners;
  API+panel+review run fine there (systemd, linger on).
- YouTube bot-checks runners: use direct mp4/asset URLs.
- S3Storage needs boto3 + bucket env (untested live).

### Performance
Lazy ML imports, cached analysis/transcript, single FFprobe per asset,
bounded workers, temp cleanup, int8 CPU default.

### Extension points
New LLM/STT/vision provider (subclass ABC), ranking profiles (config),
caption styles + render profiles (dicts), storage backend (interface),
prompt versions (prompts/ + stored version per result).

## Gap audit vs 79-section spec (2026-09-10) — 7 items open
1. §18 ranking profiles (balanced/viral/educational/emotional/storytelling/podcast+custom).
2. §25 metadata AI variants (3 titles/description/caption/hashtags/keywords, heuristic fallback).
3. §70 project IMPORT (export exists); §32 pagination on list endpoints.
4. §37 rate limiting; §38 production password auth (token-only today).
5. §78 frontend tests (vitest) + CI step.
6. §79 Docker build verify — BLOCKED here (no daemon); documented limitation.
7. Docs already cover the rest; OpenAPI auto-generated.

## Gap closure (2026-09-10, all verified)
1. Ranking profiles: 6 presets + custom merge/renormalize, persisted per score.
2. Metadata variants: LLM 3-titles + description/caption/hashtags/keywords,
   heuristic fallback, stored per clip, choosable in review.
3. Project import endpoint + archive; pagination on projects/jobs.
4. Rate limiting (token bucket, 429s) + password auth (scrypt, tokens, rotation
   on change, logout revocation, cross-user isolation tested).
5. Vitest (5 green) + CI test step. CI fully green.
6. Homie live: API+UI :8001 (systemd), auth enforced, paginated, UI 200.

## Merge: whopclip campaigns -> RepurposeAI (2026-09-10)
- New `campaigns` table (migration 0004) + policy service (P0, blockers,
  bounds, project-config mapping, stdlib-pure).
- Pipeline applies campaign rules per job; strict gate refuses blocked
  production runs (dry-run bypass explicit, never submittable).
- Campaign validator (technical READY vs submission-ready) as service +
  API + CLI + panel-equivalent UI.
- WeTransfer ingest vendored (transferwee, BSD attributed).
- API: campaigns CRUD, blockers, validate, per-campaign clips.
- MCP: get_campaign. CLI: campaign list/create/check/validate.
- UI: Campaigns list + detail (policy, blockers, brief editor, verify
  toggle, gated generate), nav entry.
- whopclip retired 2026-09-11: campaign engine fully merged (migration 0004,
  policies, CLI/UI/MCP); old repo frozen on GitHub (`ammar0xff/whopclip`),
  homie panel stopped & removed, local copies deleted.
- Verified: ruff 0, mypy 0, 26 pytest green, UI 200, API authed flow live.

## Continuous deployment (homie)

- GitHub runners can't reach homie (Tailscale-only), so CD is PULL-based:
  systemd user timer `repurposeai-cd.timer` (1 min) runs
  `deploy/pull_deploy.sh` -> fetch/reset origin/main, pip install, alembic,
  restart. Fetch/auth uses read-only GitHub deploy key at `~/.ssh/id_repurposeai_cd`.
- Fix: homie DB was born via `init_db()` (create_all) so it had tables but no
  `alembic_version`; script now stamps head to adopt such DBs before upgrading.
- Setup (one-time): copy deploy/repurposeai-cd.{service,timer}, enable timer,
  origin remote -> SSH, deploy key installed.
