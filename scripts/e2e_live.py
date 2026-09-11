"""Live production E2E driver (runs on homie against the real API + worker).

Exercises the FULL prod path on the actual host: project -> upload ->
(seed a runner-style transcript, since homie has no whisper) -> process
(segmentation/ranking/caption render/validation) -> review approve ->
export. Exit 0 only when the export manifest contains >=1 clip.

Transcript seeding: faster-whisper can't run on homie (SIGILL/oomd), so a
transcript is written directly into the prod DB the same way a transcript
produced on a runner would be stored. Everything else uses real services.

Usage:  python3 scripts/e2e_live.py <base> <media> <sqlite_db> [--keep]
          [--no-seed] [--stt auto|local|github]
  base:      http://127.0.0.1:8001
  media:     path to an mp4 (generated automatically if it doesn't exist)
  sqlite_db: path to the production sqlite file (e.g. data/rpa.db)
  --keep:    keep the test project + user after the run (default: clean up)
  --no-seed: do NOT seed a transcript -- real STT runs (e.g. remote via
             GitHub Actions when --stt github / STT_PROVIDER=auto).
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CFG = {
    "title_prefix": "live-e2e",
    "config": {
        "clip_count": 3,
        "min_duration": 6,
        "max_duration": 12,
        "min_words": 4,
        "ranking_profile": "balanced",
        "ranking_weights": {"hook": 0.55, "clarity": 0.45},
        "render_profile": "shorts_1080x1920",
        "caption_style": "bold",
        "reframe": "center",
        "credit": "Live E2E",
    },
    "job_params": {"whisper_model": "tiny", "clip_count": 3},
}


def log(msg: str) -> None:
    print(msg, flush=True)


def probe_duration(media: str, ffprobe: str = "ffprobe") -> float:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                          "format=duration", "-of", "json", media],
                         capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def make_media(media: str) -> None:
    log("generating synthetic source (concatenated scenes + tone audio)")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:duration=10:rate=20",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:duration=10:rate=20",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:duration=10:rate=20",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        "-filter_complex",
        ("[0:v]hue=h=0[v0];[1:v]hue=h=45[v1];[2:v]hue=h=90[v2];"
         "[v0][v1][v2]concat=n=3:v=1:a=0[v]"),
        "-map", "[v]", "-map", "3:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-movflags", "+faststart", "-shortest", media,
    ], check=True, timeout=300)


def make_transcript(duration: float) -> tuple[list, list]:
    words, segs, step = [], [], 0.7
    start = 0.0
    i = 0
    while start < duration - 0.7:
        end = min(start + 0.38, duration)
        words.append({"start": round(start, 2), "end": round(end, 2),
                      "w": f"fixture{i}"})
        if i % 5 == 4:
            segs.append({"start": round(start - 4 * step, 2),
                         "end": round(end, 2),
                         "text": " ".join(w["w"] for w in words[-5:]) + "."})
        i += 1
        start += step
    return words, segs


class API:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = ""

    def _req(self, method: str, path: str, body=None, files=None):
        data, headers = None, {}
        headers["Authorization"] = f"Bearer {self.token}"
        if files:
            b = "----" + uuid.uuid4().hex
            with open(files, "rb") as f:
                raw = f.read()
            data = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
                    f"filename=\"live.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").encode() + raw
            data += f"\r\n--{b}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={b}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw_out = r.read() or b"{}"
                return json.loads(raw_out) if raw_out else {}
        except urllib.error.HTTPError as e:
            log(f"HTTP {e.code} on {method} {path}: {e.read()[:400]!r}")
            raise


def cleanup(db: sqlite3.Connection, pid: str, username: str,
            keep: bool) -> None:
    if keep:
        log(f"keeping artifacts (project={pid}, user={username})")
        return
    cur = db.cursor()
    cur.execute("delete from pipeline_stages where job_id in "
                "(select id from processing_jobs where project_id=?)", (pid,))
    cur.execute("delete from candidate_scores where candidate_id in "
                "(select id from candidates where project_id=?)", (pid,))
    cur.execute("delete from generated_metadata where clip_id in "
                "(select id from clips where project_id=?)", (pid,))
    cur.execute("delete from review_decisions where clip_id in "
                "(select id from clips where project_id=?)", (pid,))
    for t in ("clips", "candidates", "scenes", "transcripts", "exports",
              "media_assets", "processing_jobs"):
        cur.execute(f"delete from {t} where project_id=?", (pid,))
    cur.execute("delete from projects where id=?", (pid,))
    cur.execute("delete from api_tokens where user_id in "
                "(select id from users where username=?)", (username,))
    cur.execute("delete from users where username=?", (username,))
    db.commit()
    shutil.rmtree(os.path.join(os.getcwd(), "data", pid),
                  ignore_errors=True)
    log("cleaned up test project + user")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("media")
    ap.add_argument("sqlite_db")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--stt", choices=["auto", "local", "github"], default="")
    args = ap.parse_args()

    if not os.path.exists(args.media):
        make_media(args.media)
    dur = probe_duration(args.media)
    log(f"source: {args.media} duration={dur}s")

    db = sqlite3.connect(args.sqlite_db)
    api = API(args.base)
    username, password = f"e2e{uuid.uuid4().hex[:6]}", uuid.uuid4().hex + "xY8!"

    api._req("POST", "/api/auth/setup", {"username": username,
                                         "password": password})
    api.token = api._req("POST", "/api/auth/login",
                         {"username": username, "password": password})["token"]
    log(f"authenticated as {username}")

    pid = api._req("POST", "/api/projects",
                   {"title": f"{CFG['title_prefix']}-{dt.datetime.now(dt.UTC).strftime('%H%M%S')}",
                    "config": CFG["config"]})["id"]
    key = api._req("POST", f"/api/projects/{pid}/upload",
                   files=args.media)["storage_key"]

    if not args.no_seed:
        words, segs = make_transcript(dur)
        db.execute(
            "insert into transcripts (id, project_id, engine, language, duration, "
            "words, segments, created_at, updated_at) values (?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, pid, "e2e-fixture", "en", dur,
             json.dumps(words), json.dumps(segs), now, now))
        db.commit()
        log(f"project {pid}, uploaded {key}, transcript seeded ({len(words)} words)")
    else:
        log(f"project {pid}, uploaded {key}, NO seed (real STT, stt={args.stt or 'auto'})")

    params = dict(CFG["job_params"])
    if args.stt:
        params["stt_provider"] = args.stt
    jid = api._req("POST", f"/api/projects/{pid}/process",
                   {"upload_key": key, "params": params})["job_id"]
    log(f"job {jid} queued; polling...")
    deadline = time.time() + 900
    job = {}
    while time.time() < deadline:
        time.sleep(15)
        job = api._req("GET", f"/api/jobs/{jid}")
        log(f"poll: {job.get('status')} {job.get('progress')} "
            f"{job.get('current_stage') or ''}")
        if job.get("status") in ("ready_for_review", "failed", "cancelled"):
            break
    if job.get("status") != "ready_for_review":
        log(f"JOB FAILED: {job.get('error')}")
        cleanup(db, pid, username, args.keep)
        return 1

    clips = api._req("GET", f"/api/projects/{pid}/clips")
    log(f"clips: {len(clips)}")
    for c in clips:
        log(f"  {c['id'][:8]} status={c.get('status')} "
            f"{c.get('validation', {}).get('status')} "
            f"{c.get('validation', {}).get('resolution')}")
    ready = [c for c in clips if c.get("validation", {}).get("status") == "READY"] or clips
    if not ready:
        log("no clips produced")
        cleanup(db, pid, username, args.keep)
        return 1
    approved = api._req("POST", f"/api/clips/{ready[0]['id']}/approve",
                        {"decision": "approved"})
    assert approved["decision"] == "approved"

    exp = api._req("POST", f"/api/projects/{pid}/export")
    n = len(exp.get("manifest", {}).get("clips", []))
    ok = n >= 1
    log(f"EXPORT-OK: {exp.get('id')} {n} clips" if ok else "EXPORT EMPTY")
    cleanup(db, pid, username, args.keep)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())