# Testing

- `tests/unit/`: stdlib-only modules (sentences, candidates, resolver,
  scoring, captions, storage, media with tiny ffmpeg fixtures). Run anywhere.
- `tests/integration/`: API via TestClient with dependency-overridden test DB
  (no env cross-talk), pipeline E2E on synthetic video.
- CI (`ci.yml`): backend (ruff, mypy, pytest), frontend (tsc, build),
  `heavy-e2e` (narrated fixture, real whisper on a free runner, full API loop).
- Property invariants covered: start<end, bounds respected, word order,
  caption non-overlap, clips within source duration.
- Fixtures are generated (`testsrc`, `sine`, edge-tts narration in CI) so no
  binary media lives in the repo (except a 340KB test mp4 in whopclip history).
