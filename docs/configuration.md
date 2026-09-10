# Configuration

All settings in `app/config/settings.py`, env-driven, validated at startup.
See `.env.example` for the full list.

| Key | Default | Notes |
|---|---|---|
| `DATABASE_URL` | sqlite `./data/repurposeai.db` | Postgres URL for prod |
| `STORAGE_PATH` / `STORAGE_BACKEND` | `./data` / `local` | `s3` needs boto3 + bucket env |
| `FFMPEG_PATH` / `FFPROBE_PATH` | `ffmpeg` / `ffprobe` | Never assumed; validated by doctor |
| `WHISPER_MODEL` / `_DEVICE` / `_COMPUTE_TYPE` | `small` / `cpu` / `int8` | `tiny` for smoke tests |
| `LLM_PROVIDER` | `heuristic` | `openai_compat`, `ollama`, `local` |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | empty | Only transcript text is sent |
| `MAX_UPLOAD_MB` / `MAX_CONCURRENT_JOBS` | 2048 / 2 | Tune to hardware |
| `AUTH_TOKEN` | empty (open) | Set in any shared deployment |
| `CORS_ORIGINS` | localhost dev ports | Lock down in prod |
