"""Unit: campaign policy, blockers, validator (stdlib-only)."""
import sys

sys.path.insert(0, ".")

from app.services.campaigns import blockers, bounds, p0_missing, to_project_config
from app.validation.campaign import check_source, validate_job


def _rules(**kw):
    base = {"campaign": "t", "rate_per_1k": 1.5, "budget": "$1k",
            "sources": ["pack.mp4"], "duration": {"min": 15, "max": 60},
            "hashtags": ["@x"], "credit": {"required": True, "text": "@x"},
            "cap": "$100"}
    base.update(kw)
    return base


def test_p0_and_blockers():
    assert p0_missing(_rules()) == []
    assert blockers(_rules(), True) == []
    miss = p0_missing(_rules(rate_per_1k=None))
    assert "rate_per_1k" in miss
    blk = blockers(_rules(), False)
    assert any(b.startswith("unverified") for b in blk)
    assert bounds(_rules()) == (15.0, 60.0)


def test_project_config_mapping():
    cfg = to_project_config(_rules())
    assert cfg["min_duration"] == 15 and cfg["credit"] == "@x"
    assert cfg["hashtags"] == ["@x"]


def test_source_gate():
    ok, _ = check_source("/packs/pack.mp4", _rules())
    assert ok
    bad, label = check_source("/tmp/other.mp4", _rules())
    assert not bad and "pack.mp4" not in label or "want one of" in label


def test_validate_ready_and_not():
    rules = _rules()
    clip = {"file": "c.mp4", "duration": 20.0, "width": 1080, "height": 1920,
            "captioned": True, "candidate": 0, "title": "t", "caption": "hi @x"}
    job = {"source": "/packs/pack.mp4", "credit_used": "@x", "extra_tags": ["@x"]}
    v = validate_job([clip], rules, job)
    assert v["status"] == "READY", v
    v2 = validate_job([], rules, job)
    assert v2["status"] == "NOT READY"
    v3 = validate_job([dict(clip, width=720)], rules, job)
    assert v3["status"] == "NOT READY"
