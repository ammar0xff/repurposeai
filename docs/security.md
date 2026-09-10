# Security

- Uploads: extension allowlist + MIME sniffing via FFprobe (never trust names),
  size caps (`MAX_UPLOAD_MB`, request limits), storage under random UUID names.
- Paths: `project_key()` + provider `_p()` reject `..` traversal.
- Subprocess: argument arrays only, no shell, timeouts everywhere, absolute
  `FFMPEG_PATH`/`FFPROBE_PATH` from config.
- Secrets: `.env` only (gitignored, `.env.example` documents keys). Never logged
  (structured logger has no secret fields; render commands truncated in records).
  API keys only ever travel as Bearer headers to the configured provider.
- AuthN/Z: optional `AUTH_TOKEN` bearer (set in shared deployments); every
  project/clip query is ownership-scoped (`user_id`), tested (403s).
- LLM: transcript treated as untrusted input; prompts instruct to ignore
  embedded instructions; model cannot execute, choose files, or render.
- Headers: nosniff, DENY framing, no-referrer. CORS allowlist from env.
- Deps: run `pip audit` / Dependabot before releases (CI runs on every push).
