"""Remote STT via GitHub Actions, pull-through style.

Works even when the app runs on a machine the runner cannot reach (homie is
Tailscale-only; GitHub runners can only reach the internet). Rendezvous is a
private gist: this host pushes the wav + meta as gist files and dispatches a
`remote-transcribe` repository event; the workflow (see
.github/workflows/transcribe.yml) downloads the wav, runs faster-whisper on a
GitHub runner, and uploads a transcript.json back to the same gist. This
provider polls the gist until the transcript appears, then verifies the sha256.

Requires a classic PAT with `gist` + `repo` scopes (workflow cannot write
gists with the default GITHUB_TOKEN). Monolingual stdlib -> runs on homie,
Termux, runner, anywhere.

Output shape matches the STTProvider contract:
{engine, language, duration, words:[{w,start,end}], segments:[{text,start,end}]}
"""
import base64
import hashlib
import http.client
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from ..core.errors import MediaError
from .stt import STTProvider

API = "https://api.github.com"
# GitHub stops inlining gist file content beyond roughly 1 MiB (rest API
# returns `truncated: true` with empty content, silently breaking the runner).
# Keep every mailbox file comfortably under it.
GIST_INLINE_LIMIT = 1_000_000
GIST_BYTES_LIMIT = 8 * 1024 * 1024  # gist file cap is 10 MiB; stay clear
POLL_SECONDS = 15
TIMEOUT_SECONDS = 1800


def pick_stt(mode: str, local_ok: bool, remote_ok: bool) -> str:
    """Select local|remote|none from the requested mode + probe results."""
    if mode == "github":
        return "remote" if remote_ok else "none"
    if mode == "local":
        return "local" if local_ok else "none"
    if local_ok:
        return "local"
    return "remote" if remote_ok else "none"


def _req(method: str, url: str, token: str, body=None,
         tries: int = 4, timeout: int = 120) -> dict:
    """GitHub API request with retry+backoff for flaky legs (truncations,
    timeouts, 5xx). 4xx are surfaced immediately."""
    token = token.strip()
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "repurposeai-remote-stt",
                **({"Content-Type": "application/json"} if data else {}),
            })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries - 1:
                raise MediaError(f"github api {method} {url} -> {e.code}",
                                 details=e.read()[:500].decode("utf-8", "replace")) from e
            last = f"{e.code}"
        except (http.client.IncompleteRead, urllib.error.URLError,
                TimeoutError, json.JSONDecodeError) as e:
            last = e
        time.sleep(1 + attempt * 2)
    raise MediaError(f"github api {method} {url} failed: {last}")


def compact_audio(ffmpeg_path: str, wav_path: str) -> bytes | None:
    """Re-encode wav to 16k mono opus-in-ogg (~24kbps) so the mailbox stays
    under GitHub's 1 MiB inline cap even for multi-minute clips. Returns the
    ogg bytes, or None if compression is not possible."""
    out = f"{wav_path}.ogg"
    try:
        subprocess.run(
            [ffmpeg_path, "-y", "-v", "error", "-i", wav_path,
             "-vn", "-c:a", "libopus", "-b:a", "24k", "-ar", "16000", "-ac", "1",
             out],
            check=True, timeout=300,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with open(out, "rb") as f:
            data = f.read()
        return data if data else None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass


def dispatch(audio: bytes, meta: dict, token: str, owner: str, repo: str) -> str:
    """Push audio+meta to a fresh private gist and dispatch a transcribe job."""
    name = meta.get("audio", "audio.wav")
    b64 = base64.b64encode(audio).decode()
    # Enforce the *inlined-content* cap, not the storage cap: over it the API
    # creates the gist but the runner sees `truncated: true` / empty content.
    if len(b64) > GIST_INLINE_LIMIT:
        raise MediaError(
            f"remote STT: audio is {len(audio)//1024//1024} MiB ({len(b64)//1024//1024} "
            f"MiB base64), over GitHub's ~1 MiB gist inline limit; use a shorter "
            "clip or local STT.")
    if len(audio) > GIST_BYTES_LIMIT:
        raise MediaError(
            f"remote STT: audio is {len(audio)//1024//1024} MiB, over the "
            f"{GIST_BYTES_LIMIT//1024//1024} MiB gist mailbox limit.")
    gist = _req("POST", f"{API}/gists", token, {
        "description": "repurposeai remote transcription mailbox",
        "public": False,
        "files": {
            name: {"content": b64},
            "meta.json": {"content": json.dumps(meta)},
        },
    })
    gid = gist["id"]
    _req("POST", f"{API}/repos/{owner}/{repo}/dispatches", token, {
        "event_type": "remote-transcribe",
        "client_payload": {"gist_id": gid, "sha256": meta["sha256"],
                           "model": meta["model"]},
    })
    return gid


def _gist_file(gist: dict, name: str) -> str:
    files = gist.get("files", {})
    if name not in files:
        raise KeyError(name)
    return files[name]["content"]


def verify_result(payload: dict, expected_sha: str) -> None:
    """Raise MediaError unless payload sha matches (wrong gist / stale)."""
    if (payload.get("sha256") or "") != expected_sha:
        raise MediaError("remote STT: transcript sha mismatch (stale result).")
    if not isinstance(payload.get("words"), list) or not payload["words"]:
        raise MediaError("remote STT: transcript.json has no words.")


def collect(gid: str, expected_sha: str, token: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Poll the gist for transcript.json; verify; delete the mailbox."""
    deadline = time.time() + timeout
    mine = None
    try:
        while time.time() < deadline:
            time.sleep(POLL_SECONDS)
            gist = _req("GET", f"{API}/gists/{gid}", token)
            try:
                raw = _gist_file(gist, "transcript.json")
            except KeyError:
                continue  # runner still working
            payload = json.loads(raw)
            verify_result(payload, expected_sha)
            mine = payload
            break
        if mine is None:
            raise MediaError("remote STT timed out waiting for the runner.")
        return mine
    finally:
        try:
            _req("DELETE", f"{API}/gists/{gid}", token)
        except MediaError:
            pass  # mailbox cleanup is best-effort


class RemoteGitHubProvider(STTProvider):
    name = "github-actions"

    def __init__(self, token: str = "", owner: str = "", repo: str = "",
                 ffmpeg_path: str = ""):
        self.token, self.owner, self.repo = token, owner, repo
        self.ffmpeg_path = ffmpeg_path

    def available(self) -> bool:
        return bool(self.token and self.owner and self.repo)

    def transcribe(self, wav_path: str, model: str = "", language: str | None = None) -> dict:
        if not self.available():
            raise MediaError(
                "Remote (GitHub Actions) STT unavailable: set GITHUB_TOKEN, "
                "GITHUB_OWNER, GITHUB_REPO (PAT scopes: gist + repo).")
        with open(wav_path, "rb") as f:
            audio = f.read()
        audio_name = "audio.wav"
        if self.ffmpeg_path:
            ogg = compact_audio(self.ffmpeg_path, wav_path)
            if ogg and len(ogg) < len(audio):
                audio, audio_name = ogg, "audio.ogg"
        sha = hashlib.sha256(audio).hexdigest()
        meta = {"sha256": sha, "model": model or "small",
                "language": language, "audio": audio_name}
        gid = dispatch(audio, meta, self.token, self.owner, self.repo)
        payload = collect(gid, sha, self.token)
        out: dict[str, Any] = {
            "engine": payload.get("engine", "github-actions/faster-whisper"),
            "language": payload.get("language", language),
            "duration": payload.get("duration", 0.0),
            "words": payload["words"],
            "segments": payload.get("segments", []),
        }
        return out