# Architecture

## Layers (dependencies point inward)

```
web/ (React) -> REST/SSE -> app/api/ -> app/services/ -> app/{pipelines,ranking,rendering,captions,media,validation}
                                              |                    ^
                                              v                    | pure stdlib
                                    app/workers/ (DB queue)        |
                                              |              app/providers/ (ABCs)
                                              v                    |
                                    app/models/ (SQLAlchemy)  app/storage/
```

Rules: pipeline services never import FastAPI, SQLAlchemy, or providers'
concrete classes (provider ABCs only). The same `Pipeline` object runs from
API worker threads, CLI, MCP server, and tests.

## Key decisions

- **SQLite default, Postgres via `DATABASE_URL`.** Alembic migrations are explicit
  files; `init_db()` (create_all) exists for dev/tests only.
- **DB-backed job queue**, no Redis required. `Worker` dispatcher thread claims
  `queued` jobs up to `MAX_CONCURRENT_JOBS`. Cancel = shared flag + status.
- **Idempotent stages**: each stage checkpoints; resume skips `done` stages;
  per-clip renders skip existing clips. `--force` re-runs.
- **LLM scores candidates, never timelines.** Structured JSON validated
  (Pydantic when installed, manual fallback), retry, then heuristic fallback
  with identical schema. Fallbacks are labeled (`source` field, UI note).
- **Heavy ML is optional.** STT/face/scene libs are lazy imports behind
  availability probes (subprocess probe for SIGILL-prone wheels). The app
  boots and serves review/exports without them.
