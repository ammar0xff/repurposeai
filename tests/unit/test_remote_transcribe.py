"""Unit tests for the GitHub-Actions remote STT provider (stdlib-only)."""
import pytest

from app.core.errors import MediaError
from app.providers.remote_transcribe import (
    RemoteGitHubProvider,
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