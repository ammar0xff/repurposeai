# RepurposeAI — local-first AI video repurposing

![ci](https://github.com/ammar0xff/repurposeai/actions/workflows/ci.yml/badge.svg)

Long video in, ranked captioned vertical clips out. No paid APIs required.

## Quickstart (local)

```bash
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --port 8000   # API + worker + OpenAPI at /api/docs
cd web && npm install && npm run build   # serves from / when dist/ exists
```

Or: `docker compose up` (see `docs/deployment.md`).

## CLI

```bash
python -m app.cli init "My project"
python -m app.cli ingest <project> video.mp4
python -m app.cli run <project> --source video.mp4 --params '{"clip_count":5}'
python -m app.cli doctor
```

## How it works

ingest → analyze (FFprobe) → transcribe (faster-whisper, word timestamps) →
scenes + silence → sentence-aware candidates → eligibility filter →
structured LLM scoring (heuristic fallback, same schema) → timestamp resolver
(word boundaries + padding) → 9:16 reframe (center/face/speaker) →
libass captions → H264 render → FFprobe validation → human review → export.

LLM scores candidates; it never controls the timeline. See `docs/pipeline.md`.

## API quick reference

```bash
# setup / login (first-time or shared deployment)
curl -X POST localhost:8000/api/auth/setup  -d '{"username":"you","password":"longpassword1"}'
TOKEN=$(curl -X POST localhost:8000/api/auth/login  -d '{"username":"you","password":"longpassword1"}' | jq -r .token)
A="Authorization: Bearer $TOKEN"

# lifecycle: upload → process → poll → export
PID=$(curl -H "$A" -X POST localhost:8000/api/projects -d '{"title":"X"}' | jq -r .id)
curl -H "$A" -F "file=@video.mp4" localhost:8000/api/projects/$PID/upload
JOB=$(curl -H "$A" -X POST localhost:8000/api/projects/$PID/process \
  -d '{"upload_key":"<from upload>","params":{"stt_provider":"github"}}' | jq -r .job_id)
curl -H "$A" localhost:8000/api/jobs/$JOB              # poll (or SSE: /jobs/$JOB/events)
curl -H "$A" localhost:8000/api/projects/$PID/clips    # rendered clips + validation

# retry a failed job; check live queue metrics
curl -H "$A" -X POST localhost:8000/api/jobs/$JOB/retry
curl -H "$A" localhost:8000/api/system/metrics
```

See [`docs/configuration.md`](docs/configuration.md) for all env vars and [`docs/ops.md`](docs/ops.md) for runbook / liveness details.

## Docs

`docs/`: architecture, development, deployment, configuration, pipeline,
providers, storage, troubleshooting, security, testing.
