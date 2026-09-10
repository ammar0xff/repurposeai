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
- No Docker daemon here: Dockerfiles shipped, build-verification marked KNOWN LIMITATION.
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
