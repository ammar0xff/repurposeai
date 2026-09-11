"""Remote STT via GitHub Actions, pull-through style.

Works even when the app runs on a machine the runner cannot reach (homie is
Tailscale-only; GitHub runners can only reach the internet). Rendezvous is a
private gist: this host pushes the wav + meta as gist files (audio is split
into "part.N" files when needed) and dispatches a `remote-transcribe`
repository event; the workflow (see .github/workflows/transcribe.yml)
downloads the parts via their raw_url, reassembles the audio, runs
faster-whisper on a GitHub runner, and uploads a transcript.json back to
the same gist. This provider polls the gist until the transcript appears,
then verifies the sha256.

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
# The gist REST API inlines every file's content into one response and
# truncates the AGGREGATE past ~1 MiB (observed: first file full, all later
# files empty) - a naive pull-through dumps the transcript silently. The
# runner therefore fetches audio via each file's `raw_url`, which serves the
# full stored bytes (per-file cap 10 MiB) regardless of inline truncation.
# Parts exist to keep individual files comfortably under that 10 MiB cap.
PART_RAW = 3 * 1024 * 1024  # 3 MiB per part -> ~4 MiB base64 on the wire
MAX_PARTS = 24  # ~72 MiB ceiling; keeps the runner's wall-clock sane
GIST_BYTES_LIMIT = 8 * 1024 * 1024  # practical audio cap (runner runtime)
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
            last = f"{e.__class__.__name__}: {e}"
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


def dispatch(parts: list[bytes], meta: dict, token: str, owner: str, repo: str) -> str:
    """Push audio parts + meta to a fresh private gist and dispatch a job."""
    if not parts or len(parts) > MAX_PARTS:
        raise MediaError(
            f"remote STT: audio needs {len(parts)} parts, over the "
            f"{MAX_PARTS}-part gist mailbox cap.")
    files: dict[str, dict[str, str]] = {}
    for i, part in enumerate(parts):
        files[f"part.{i}"] = {"content": base64.b64encode(part).decode()}
    files["meta.json"] = {"content": json.dumps(meta)}
    gist = _req("POST", f"{API}/gists", token, {
        "description": "repurposeai remote transcription mailbox",
        "public": False,
        "files": files,
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


def _get_bytes(url: str, token: str, tries: int = 3, timeout: int = 120) -> bytes:
    """Fetch a gist file's raw_url - the REST `content` field is truncated
    past the aggregate ~1 MiB inline cap, but raw_url serves the full stored
    bytes (per-file cap 10 MiB), regardless of `truncated` flags."""
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"token {token}",
                     "User-Agent": "repurposeai-remote-stt"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries - 1:
                raise MediaError(f"github raw {url} -> {e.code}") from e
            last = f"{e.code}"
        except (http.client.IncompleteRead, urllib.error.URLError,
                TimeoutError) as e:
            last = f"{e.__class__.__name__}: {e}"
        time.sleep(1 + attempt * 2)
    raise MediaError(f"github raw fetch failed: {last}")


def collect(gid: str, expected_sha: str, token: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Poll the gist for transcript.json; verify; delete the mailbox."""
    deadline = time.time() + timeout
    mine = None
    try:
        while time.time() < deadline:
            time.sleep(POLL_SECONDS)
            gist = _req("GET", f"{API}/gists/{gid}", token)
            info = gist.get("files", {}).get("transcript.json")
            if not info:
                continue  # runner still working
            raw = info.get("content") or ""
            if not raw or info.get("truncated") or not raw.lstrip().startswith("{"):
                # transcript.json easily exceeds the aggregate inline cap and
                # comes back truncated/empty; pull the authoritative bytes.
                if not info.get("raw_url"):
                    continue
                raw = _get_bytes(info["raw_url"], token).decode("utf-8", "replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue  # runner may be mid-upload; keep polling
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
        if len(audio) > GIST_BYTES_LIMIT:
            raise MediaError(
                f"remote STT: audio is {len(audio)//1024//1024} MiB, over the "
                f"{GIST_BYTES_LIMIT//1024//1024} MiB gist mailbox cap.")
        parts = [audio[i:i + PART_RAW] for i in range(0, len(audio), PART_RAW)]
        if len(parts) > MAX_PARTS:
            raise MediaError(
                f"remote STT: audio is {len(audio)//1024//1024} MiB, over the "
                f"{MAX_PARTS}-part gist mailbox cap.")
        sha = hashlib.sha256(audio).hexdigest()
        meta = {"sha256": sha, "model": model or "small",
                "language": language, "audio": audio_name, "parts": len(parts)}
        gid = dispatch(parts, meta, self.token, self.owner, self.repo)
        payload = collect(gid, sha, self.token)
        out: dict[str, Any] = {
            "engine": payload.get("engine", "github-actions/faster-whisper"),
            "language": payload.get("language", language),
            "duration": payload.get("duration", 0.0),
            "words": payload["words"],
            "segments": payload.get("segments", []),
        }
        return out