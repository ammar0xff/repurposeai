"""Unit tests for the GitHub-Actions remote STT provider (stdlib-only)."""
import base64
import http.client
import json
import shutil
import subprocess
from unittest import mock

import pytest

from app.core.errors import MediaError
from app.providers.remote_transcribe import (
    RemoteGitHubProvider,
    _gist_file,
    _req,
    compact_audio,
    dispatch,
    pick_stt,
    verify_result,
)


def test_pick_stt_forces_remote_only_when_configured():
    assert pick_stt("github", local_ok=False, remote_ok=True) == "remote"
    assert pick_stt("github", local_ok=True, remote_ok=True) == "remote"
    assert pick_stt("github", local_ok=True, remote_ok=False) == "none"


def test_pick_stt_auto_prefers_local_then_remotes():
    assert pick_stt("auto", local_ok=True, remote_ok=False) == "local"
    assert pick_stt("auto", local_ok=False, remote_ok=True) == "remote"
    assert pick_stt("auto", local_ok=True, remote_ok=True) == "local"


def test_pick_stt_local_never_uses_remote():
    assert pick_stt("local", local_ok=True, remote_ok=True) == "local"
    assert pick_stt("local", local_ok=False, remote_ok=True) == "none"


def test_available_requires_all_three_credentials():
    p = RemoteGitHubProvider("ghp_x", "ammar0xff", "repurposeai")
    assert p.available()
    for k in ("token", "owner", "repo"):
        kw = {"token": "ghp_x", "owner": "ammar0xff", "repo": "repurposeai"}
        kw[k] = ""
        assert not RemoteGitHubProvider(**kw).available()


def test_verify_result_accepts_matching_payload():
    payload = {"sha256": "abc", "words": [{"w": "hi", "start": 0.0, "end": 0.4}]}
    verify_result(payload, "abc")


@pytest.mark.parametrize("kw", [{"sha256": "nope"},
                                {"words": []},
                                {"words": None}])
def test_verify_result_rejects_bad_payloads(kw):
    payload = {"sha256": "abc", "words": [{"w": "hi", "start": 0.0, "end": 0.4}]}
    payload.update(kw)
    with pytest.raises(MediaError):
        verify_result(payload, "abc")


def test_transcribe_without_creds_raises_clear_error():
    p = RemoteGitHubProvider("", "", "")
    with pytest.raises(MediaError, match="GITHUB_TOKEN"):
        p.transcribe("/tmp/whatever.wav")


class _Ctx:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self, *a):
        return self.data


def _resp(payload: dict):
    return _Ctx(payload)


def test_req_retries_on_incomplete_read_and_result_ok():
    with mock.patch("app.providers.remote_transcribe.time.sleep"), \
            mock.patch("app.providers.remote_transcribe.urllib.request.urlopen") as uo:
        uo.side_effect = [
            http.client.IncompleteRead(b"123", 100),
            _resp({"ok": True}),
        ]
        assert _req("GET", "https://api.github.com/x", "ghp_ tkn") == {"ok": True}
        assert uo.call_count == 2


def test_req_gives_up_after_tries_and_raises_mediarerror():
    with mock.patch("app.providers.remote_transcribe.time.sleep"), \
            mock.patch("app.providers.remote_transcribe.urllib.request.urlopen") as uo:
        uo.side_effect = http.client.IncompleteRead(b"", 100)
        with pytest.raises(MediaError, match="(?i)incomplete"):
            _req("GET", "https://api.github.com/x", "ghp_ tkn", tries=3)
        assert uo.call_count == 3


def test_gist_file_returns_plain_json_content():
    # JSON files on the gist are plain text (only audio.wav is base64);
    # parsing must not base64-decode them, even for awkward lengths (1 mod 4).
    content = json.dumps({"model": "tiny", "x": 9})
    assert len(content) % 4 == 1
    gist = {"files": {"transcript.json": {"content": content}}}
    assert _gist_file(gist, "transcript.json") == content
    assert json.loads(_gist_file(gist, "transcript.json"))["model"] == "tiny"


def test_dispatch_writes_audio_parts_and_plain_meta():
    gist = {"id": "g1"}
    calls = []

    def fake_req(method, url, token, body=None, **kw):
        calls.append((method, url, body))
        return gist

    with mock.patch("app.providers.remote_transcribe._req", side_effect=fake_req):
        meta = {"sha256": "abc", "model": "tiny", "language": None,
                "audio": "audio.ogg", "parts": 2}
        gid = dispatch([b"PCM-a", b"PCM-b"], meta, "ghp_x", "ammar0xff", "repurposeai")

    assert gid == "g1"
    _post_method, post_url, post = calls[0]
    assert post_url.endswith("/gists")
    files = post["files"]
    assert files["part.0"]["content"] == base64.b64encode(b"PCM-a").decode()
    assert files["part.1"]["content"] == base64.b64encode(b"PCM-b").decode()
    assert json.loads(files["meta.json"]["content"])["parts"] == 2
    _el, url, dispatch_body = calls[1]
    assert url.endswith("/dispatches")
    assert dispatch_body["client_payload"]["gist_id"] == "g1"


def test_dispatch_rejects_audio_over_part_cap():
    with mock.patch("app.providers.remote_transcribe._req") as req:
        with pytest.raises(MediaError, match="part"):
            dispatch([b"\x00"] * 25,
                     {"sha256": "abc", "model": "tiny", "parts": 25},
                     "ghp_x", "o", "r")
        req.assert_not_called()


def _sine_wav(path, seconds=1.0, rate=16000):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ar", str(rate), "-ac", "1", path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg required to generate fixtures")
def test_compact_audio_shrinks_and_produces_ogg():
    wav = "/tmp/rpa-compact-test.wav"
    _sine_wav(wav, seconds=60)
    with open(wav, "rb") as f:
        raw = f.read()
    ogg = compact_audio("ffmpeg", wav)
    assert ogg is not None
    assert ogg.startswith(b"OggS")
    assert len(ogg) < len(raw)  # 60s of 16k/16-bit wav is ~1.9 MiB
    import os
    os.unlink(wav)


@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg required to generate fixtures")
def test_provider_compresses_before_dispatch_when_ffmpeg_configured():
    wav = "/tmp/rpa-provider-compress.wav"
    _sine_wav(wav, seconds=60)
    p = RemoteGitHubProvider("ghp_x", "ammar0xff", "repurposeai", "ffmpeg")
    seen = {}

    def fake_dispatch(parts, meta, token, owner, repo):
        seen.update(parts=parts, meta=meta)
        return "g1"

    def fake_collect(gid, sha, token):
        return {"engine": "x", "language": None, "duration": 1.0,
                "words": [{"w": "hi", "start": 0, "end": 1}], "segments": []}

    with mock.patch("app.providers.remote_transcribe.dispatch",
                    side_effect=fake_dispatch), \
            mock.patch("app.providers.remote_transcribe.collect",
                       side_effect=fake_collect):
        out = p.transcribe(wav, model="tiny")

    assert seen["parts"][0].startswith(b"OggS")
    assert len(seen["parts"]) == 1  # 60s 16k wav compresses below one part
    assert seen["meta"]["audio"] == "audio.ogg"
    assert seen["meta"]["parts"] == 1
    assert seen["meta"]["sha256"] == __import__("hashlib").sha256(seen["parts"][0]).hexdigest()
    assert out["engine"] == "x"
    import os
    os.unlink(wav)