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
import json
import time
from typing import Any
import urllib.error
import urllib.request

from ..core.errors import MediaError
from .stt import STTProvider

API = "https://api.github.com"
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


def _req(method: str, url: str, token: str, body=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "repurposeai-remote-stt",
            **({"Content-Type": "application/json"} if data else {}),
        })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise MediaError(f"github api {method} {url} -> {e.code}",
                         details=e.read()[:500].decode("utf-8", "replace")) from e


def dispatch(audio: bytes, meta: dict, token: str, owner: str, repo: str) -> str:
    """Push audio+meta to a fresh private gist and dispatch a transcribe job."""
    if len(audio) > GIST_BYTES_LIMIT:
        raise MediaError(
            f"remote STT: wav is {len(audio)//1024//1024} MiB, over the "
            f"{GIST_BYTES_LIMIT//1024//1024} MiB gist mailbox limit; use a "
            "shorter clip or local STT.")
    gist = _req("POST", f"{API}/gists", token, {
        "description": "repurposeai remote transcription mailbox",
        "public": False,
        "files": {
            "audio.wav": {"content": base64.b64encode(audio).decode()},
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
    return base64.b64decode(files[name]["content"]).decode("utf-8")


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
            try:
                gist = _req("GET", f"{API}/gists/{gid}", token)
            except MediaError as e:
                raise
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

    def __init__(self, token: str = "", owner: str = "", repo: str = ""):
        self.token, self.owner, self.repo = token, owner, repo

    def available(self) -> bool:
        return bool(self.token and self.owner and self.repo)

    def transcribe(self, wav_path: str, model: str = "", language: str | None = None) -> dict:
        if not self.available():
            raise MediaError(
                "Remote (GitHub Actions) STT unavailable: set GITHUB_TOKEN, "
                "GITHUB_OWNER, GITHUB_REPO (PAT scopes: gist + repo).")
        audio = open(wav_path, "rb").read()
        sha = hashlib.sha256(audio).hexdigest()
        gid = dispatch(audio, {"sha256": sha, "model": model or "small",
                               "language": language}, self.token, self.owner, self.repo)
        payload = collect(gid, sha, self.token)
        out: dict[str, Any] = {
            "engine": payload.get("engine", "github-actions/faster-whisper"),
            "language": payload.get("language", language),
            "duration": payload.get("duration", 0.0),
            "words": payload["words"],
            "segments": payload.get("segments", []),
        }
        return out