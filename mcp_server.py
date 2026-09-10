#!/usr/bin/env python3
"""RepurposeAI MCP server: thin stdio wrapper over services/ (no business logic)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/repurposeai.db")

from app.config.settings import get_settings  # noqa: E402
from app.core.ids import new_id  # noqa: E402
from app.core.logging import setup  # noqa: E402
from app.models.db import get_session_factory, init_db  # noqa: E402
from app.services.pipeline import Pipeline  # noqa: E402
from app.storage.local import LocalFilesystemStorage  # noqa: E402

setup()
init_db()
_s = get_settings()
_DB = get_session_factory()()
_PIPE = Pipeline(_DB, LocalFilesystemStorage(_s.storage_path), _s)

TOOLS = [
    {"name": "create_project", "description": "Create a project.",
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": []}},
    {"name": "analyze_media", "description": "Ingest + FFprobe a source into a project.",
     "inputSchema": {"type": "object", "properties": {
        "project_id": {"type": "string"}, "source": {"type": "string"}}, "required": ["project_id", "source"]}},
    {"name": "transcribe_project", "description": "STT a project's source.",
     "inputSchema": {"type": "object", "properties": {
        "project_id": {"type": "string"}, "model": {"type": "string", "default": ""}}, "required": ["project_id"]}},
    {"name": "find_candidates", "description": "Scenes/silence/sentences/candidates + eligibility.",
     "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "rank_candidates", "description": "Score candidates (LLM structured, else heuristic).",
     "inputSchema": {"type": "object", "properties": {
        "project_id": {"type": "string"}, "n": {"type": "integer", "default": 5}}, "required": ["project_id"]}},
    {"name": "render_clip", "description": "Resolve + render top clips.",
     "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "get_campaign", "description": "Read a campaign brief with blockers.",
     "inputSchema": {"type": "object", "properties": {
        "campaign_id": {"type": "string"}}, "required": ["campaign_id"]}},
    {"name": "validate_project", "description": "FFprobe-validate all rendered clips.",
     "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
    {"name": "list_clips", "description": "List clips with status.",
     "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}},
]


def _proj(pid: str):
    from app.models.entities import Project
    p = _DB.query(Project).filter_by(id=pid).first()
    if not p:
        raise ValueError("project not found")
    return p


def _job(pid: str, params: dict):
    from app.models.entities import ProcessingJob
    j = ProcessingJob(id=new_id(), project_id=pid, status="running", params=params)
    _DB.add(j)
    _DB.commit()
    return j


def call(name: str, a: dict) -> str:
    from app.models.entities import Clip, Project
    if name == "create_project":
        p = Project(id=new_id(), title=a.get("title", "Untitled"))
        _DB.add(p)
        _DB.commit()
        return json.dumps({"project_id": p.id})
    if name == "analyze_media":
        p = _proj(a["project_id"])
        j = _job(p.id, {"source": a["source"]})
        key = _PIPE.ingest(j, p, a["source"])
        from app.media.analyze import analyze
        return json.dumps(analyze(_PIPE.storage.get_path(key), _s.ffprobe_path))
    if name == "transcribe_project":
        p = _proj(a["project_id"])
        j = _job(p.id, {})
        from app.models.entities import MediaAsset
        src = _DB.query(MediaAsset).filter_by(project_id=p.id, kind="source").first()
        tr = _PIPE.transcribe(j, p, src.storage_key, a.get("model", ""))
        return json.dumps({"engine": tr["engine"], "words": len(tr["words"])})
    if name == "find_candidates":
        p = _proj(a["project_id"])
        return json.dumps(_PIPE.segment(_job(p.id, {}), p))
    if name == "rank_candidates":
        p = _proj(a["project_id"])
        return json.dumps(_PIPE.rank(_job(p.id, {}), p, int(a.get("n", 5))))
    if name == "render_clip":
        p = _proj(a["project_id"])
        return json.dumps(_PIPE.resolve_render(_job(p.id, {}), p))
    if name == "get_campaign":
        from app.models.entities import Campaign
        from app.services.campaigns import blockers, p0_missing
        c = _DB.query(Campaign).filter_by(id=a["campaign_id"]).first()
        if not c:
            return json.dumps({"error": "campaign not found"})
        return json.dumps({"id": c.id, "name": c.name, "version": c.version,
                           "rules": c.rules, "verified": c.verified,
                           "p0_missing": p0_missing(c.rules or {}),
                           "blockers": blockers(c.rules or {}, c.verified)})
    if name == "validate_project":
        from app.validation.checks import validate_clip
        out = []
        for c in _DB.query(Clip).filter_by(project_id=a["project_id"]).all():
            out.append({"clip": c.id, **validate_clip(
                _PIPE.storage.get_path(c.storage_key),
                {"width": 1080, "height": 1920, "min_duration": 5,
                 "max_duration": 600, "need_audio": True, "need_captions": True})})
        ready = all(o["status"] == "READY" for o in out) if out else False
        return json.dumps({"status": "READY" if ready else "NOT READY", "clips": out})
    if name == "list_clips":
        rows = _DB.query(Clip).filter_by(project_id=a["project_id"]).all()
        return json.dumps([{"id": c.id, "start": c.start, "end": c.end,
                            "status": c.status} for c in rows])
    raise ValueError(f"unknown tool: {name}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, method = msg.get("id"), msg.get("method")

        def ok(result):
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
            sys.stdout.flush()

        def err(code, message):
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}) + "\n")
            sys.stdout.flush()

        try:
            if method == "initialize":
                ok({"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                    "serverInfo": {"name": "repurposeai", "version": "0.1.0"}})
            elif method == "notifications/initialized":
                pass
            elif method == "tools/list":
                ok({"tools": TOOLS})
            elif method == "tools/call":
                p = msg.get("params", {})
                ok({"content": [{"type": "text", "text": call(p["name"], p.get("arguments", {}))}]})
            else:
                err(-32601, f"unknown: {method}")
        except Exception as e:
            err(-32603, f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
