"""Remote transcription step for the transcribe.yml workflow.

Written so the workflow YAML stays simple: this script is invoked by the
`remote-transcribe` event (or manual workflow_dispatch with a gist_id input)
after the gist id is resolved into the GID env var. It:

  1. fetches the audio parts + meta.json from the private gist mailbox,
  2. reassembles them into the original wav/ogg,
  3. runs faster-whisper with word timestamps,
  4. PATCHes transcript.json back to the same gist.

Stdlib only. Runs on the ubuntu-latest runner (actionlint/py3.12).
"""
import base64
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
GID = os.environ["GID"]
TOKEN = os.environ["GH_TOKEN"].strip()


def _req(method, url, tries=4, timeout=120):
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": f"token {TOKEN}",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries - 1:
                raise
            last = e.code
        except (http.client.IncompleteRead, urllib.error.URLError,
                TimeoutError, json.JSONDecodeError) as e:
            last = e
        time.sleep(1 + attempt * 2)
    raise RuntimeError(f"gist request failed after {tries} tries: {last}")


def main() -> int:
    gist = _req("GET", f"{API}/gists/{GID}")
    files = gist["files"]
    if not files.get("meta.json", {}).get("content"):
        raise RuntimeError(
            "gist meta.json is empty/truncated (clip too long for the mailbox?)")
    meta = json.loads(files["meta.json"]["content"])
    audio_name = meta.get("audio", "audio.wav")
    nparts = int(meta.get("parts") or 0)
    if nparts:
        payload = []
        for i in range(nparts):
            name = f"part.{i}"
            if not files.get(name, {}).get("content"):
                raise RuntimeError(
                    f"gist {name} is empty/truncated (mailbox?)")
            payload.append(base64.b64decode(files[name]["content"]))
        audio = b"".join(payload)
    else:
        if not files.get(audio_name, {}).get("content"):
            raise RuntimeError(
                f"gist {audio_name} is empty/truncated (clip too long for the mailbox?)")
        audio = base64.b64decode(files[audio_name]["content"])
    open(audio_name, "wb").write(audio)

    from faster_whisper import WhisperModel  # type: ignore

    model = meta.get("model", "small")
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, info = m.transcribe(
        audio_name, word_timestamps=True, language=meta.get("language"))
    words, segments = [], []
    for s in segs:
        segments.append({"text": s.text.strip(),
                         "start": round(s.start, 2), "end": round(s.end, 2)})
        for w in (s.words or []):
            if w.word.strip():
                words.append({"w": w.word.strip(),
                              "start": round(w.start, 2), "end": round(w.end, 2)})
    payload = {"engine": f"github-actions/faster-whisper/{model}",
               "language": getattr(info, "language", None),
               "duration": round(words[-1]["end"], 2) if words else 0.0,
               "words": words, "segments": segments,
               "sha256": hashlib.sha256(audio).hexdigest()}
    json.dump(payload, open("transcript.json", "w"))
    print("words:", len(words), "duration:", payload["duration"])

    body = {"files": {"transcript.json": {"content": open("transcript.json").read()}}}
    req = urllib.request.Request(
        f"{API}/gists/{GID}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={"Authorization": f"token {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        print("gist updated:", r.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())