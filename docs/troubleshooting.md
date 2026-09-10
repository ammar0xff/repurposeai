# Troubleshooting

- `STT provider unavailable`: install `.[stt]`; on old CPUs native wheels can
  SIGILL (see readiness) — use runner-class hardware for transcription.
- Job stuck `queued`: worker not running (API lifespan starts it; daemon via
  `python -m app.workers.daemon`). Check `/api/jobs`.
- Job `failed` at transcribe on 2GB boxes: expected (OOM). Transcribe elsewhere,
  or scale the box; rank/render need little RAM.
- Upload 422: extension allowlist (`mp4,mkv,mov,webm,mp3,wav,m4a,avi`) or size cap.
- 401s: `AUTH_TOKEN` set but client missing `Authorization: Bearer`.
- SQLite `database is locked`: single-writer workload is fine; move to Postgres
  for concurrent writers.
- Runner yt-dlp YouTube 403/bot-check: use direct mp4/asset URLs on runners.
