"""Standalone connectivity check for the remote-STT (GitHub Actions) path.

Creates (or reuses) a private gist holding speech audio + meta.json, dispatches
a `remote-transcribe` event, polls until transcript.json lands, and verifies
the sha256 + word count. Typical runtime ~3-6 min (fresh runner installs
faster-whisper). No homie required.

Usage:
    python3 scripts/verify_remote_stt.py <github_token> [gist_id]
    # with gist_id: re-check an existing mailbox (audio fetched from it)
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

API = "https://api.github.com"
GIST_CAP = 8 * 1024 * 1024
URL = "https://github.com/openai/whisper/raw/main/tests/jfk.flac"


def _req(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "repurposeai-verify",
            **({"Content-Type": "application/json"} if data else {}),
        })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"{}")


def make_audio() -> bytes:
    wav = "/tmp/jfk.wav"
    if not os.path.exists(wav):
        src = "/tmp/jfk.flac"
        if not os.path.exists(src):
            subprocess.run(
                ["curl", "-sSL", "-o", src, URL], check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-ar", "16000", "-ac", "1", wav], check=True)
    return open(wav, "rb").read()


def main() -> int:
    token = sys.argv[1].strip()
    if len(sys.argv) > 2:
        gid = sys.argv[2]
    else:
        audio = make_audio()
        if len(audio) > GIST_CAP:
            print("FAIL audio too large", len(audio)); return 1
        gist = _req("POST", f"{API}/gists", token, {
            "description": "repurposeai connectivity check",
            "public": False,
            "files": {"audio.wav": {"content": base64.b64encode(audio).decode()},
                      "meta.json": {"content": json.dumps({"model": "tiny",
                                                           "language": None})}}})
        gid = gist["id"]
        print("created gist", gid, "audio bytes", len(audio), flush=True)

    files = _req("GET", f"{API}/gists/{gid}", token)["files"]
    audio = base64.b64decode(files["audio.wav"]["content"])
    sha = hashlib.sha256(audio).hexdigest()
    print("mailbox audio bytes", len(audio), "sha", sha[:12], flush=True)

    _req("POST", f"{API}/repos/ammar0xff/repurposeai/dispatches", token,
         {"event_type": "remote-transcribe",
          "client_payload": {"gist_id": gid}})
    print("dispatched; polling for transcript.json...", flush=True)

    deadline = time.time() + 900
    while time.time() < deadline:
        time.sleep(20)
        files = _req("GET", f"{API}/gists/{gid}", token)["files"]
        if "transcript.json" not in files:
            continue
        payload = json.loads(files["transcript.json"]["content"])
        if payload.get("sha256") != sha:
            print("FAIL sha mismatch", payload.get("sha256"), sha) 
            try:
                _req("DELETE", f"{API}/gists/{gid}", token)
            except urllib.error.HTTPError:
                pass
            return 1
        words = payload.get("words", [])
        print(f"PASS engine={payload.get('engine')} words={len(words)} "
              f"duration={payload.get('duration')} language="
              f"{payload.get('language')}", flush=True)
        try:
            _req("DELETE", f"{API}/gists/{gid}", token)
        except urllib.error.HTTPError:
            pass
        return 0
    print("FAIL timed out waiting for transcript.json", flush=True)
    try:
        _req("DELETE", f"{API}/gists/{gid}", token)
    except urllib.error.HTTPError:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())