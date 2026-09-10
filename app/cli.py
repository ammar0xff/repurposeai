"""repurpose CLI: every pipeline stage + doctor. --json for automation."""
import argparse
import json
import sys

from .config.settings import get_settings
from .core.logging import setup
from .models.db import get_session_factory, init_db
from .services.pipeline import Pipeline
from .storage.local import LocalFilesystemStorage


def _ctx():
    s = get_settings()
    db = get_session_factory()()
    return s, db, Pipeline(db, LocalFilesystemStorage(s.storage_path), s)


def _fmt(obj, as_json: bool):
    print(json.dumps(obj, indent=1, ensure_ascii=False) if as_json else
          "\n".join(f"{k}: {v}" for k, v in obj.items()) if isinstance(obj, dict) else obj)


def cmd_init(a):

    from .core.ids import new_id
    from .models.entities import Project
    _, db, _ = _ctx()
    init_db()
    p = Project(id=new_id(), title=a.title, description=a.description or "",
                config=json.loads(a.config or "{}"))
    db.add(p)
    db.commit()
    _fmt({"project_id": p.id, "title": p.title}, a.json)


def _project(db, pid: str):
    from .models.entities import Project
    p = db.query(Project).filter_by(id=pid).first()
    if not p:
        print(json.dumps({"error": "project not found"}))
        sys.exit(2)
    return p


def _job_for(db, pipe, pid: str, params: dict):
    from .core.ids import new_id
    from .models.entities import ProcessingJob
    j = ProcessingJob(id=new_id(), project_id=pid, status="running", params=params)
    db.add(j)
    db.commit()
    return j


def cmd_ingest(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    j = _job_for(db, pipe, p.id, {"source": a.source})
    key = pipe.ingest(j, p, a.source)
    _fmt({"storage_key": key}, a.json)


def cmd_analyze(a):
    s, db, pipe = _ctx()
    p = _project(db, a.project)
    from .models.entities import MediaAsset
    src = db.query(MediaAsset).filter_by(project_id=p.id, kind="source").first()
    from .media.analyze import analyze
    info = analyze(pipe.storage.get_path(src.storage_key), s.ffprobe_path)
    p.duration = info["duration"]
    db.commit()
    _fmt(info, a.json)


def cmd_transcribe(a):
    s, db, pipe = _ctx()
    p = _project(db, a.project)
    from .models.entities import MediaAsset
    src = db.query(MediaAsset).filter_by(project_id=p.id, kind="source").first()
    j = _job_for(db, pipe, p.id, {})
    tr = pipe.transcribe(j, p, src.storage_key, a.model or s.whisper_model, a.force)
    _fmt({"engine": tr["engine"], "words": len(tr["words"]), "duration": tr["duration"]}, a.json)


def cmd_candidates(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    j = _job_for(db, pipe, p.id, {})
    out = pipe.segment(j, p)
    _fmt(out, a.json)


def cmd_rank(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    j = _job_for(db, pipe, p.id, {})
    _fmt(pipe.rank(j, p, a.n), a.json)


def cmd_render(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    j = _job_for(db, pipe, p.id, {})
    _fmt(pipe.resolve_render(j, p), a.json)


def cmd_validate(a):
    from .models.entities import Clip
    from .validation.checks import validate_clip
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    reps = []
    for c in db.query(Clip).filter_by(project_id=p.id).all():
        reps.append({"clip": c.id, **validate_clip(
            pipe.storage.get_path(c.storage_key),
            {"width": 1080, "height": 1920, "min_duration": 5, "max_duration": 600,
             "need_audio": True, "need_captions": True})})
    _fmt({"clips": reps}, a.json)


def cmd_run(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    from .core.ids import new_id
    from .models.entities import ProcessingJob
    params = {"source": a.source} if a.source else {}
    params.update(json.loads(a.params or "{}"))
    j = ProcessingJob(id=new_id(), project_id=p.id, status="queued", params=params)
    db.add(j)
    db.commit()
    _fmt(pipe.run(j.id, a.force), a.json)


def cmd_export(a):
    _, db, pipe = _ctx()
    p = _project(db, a.project)
    from .services.exporter import build_export
    e = build_export(db, pipe.storage, p)
    _fmt({"id": e.id, "storage_key": e.storage_key,
          "clips": len(e.manifest.get("clips", []))}, a.json)


def cmd_doctor(a):
    import shutil
    checks = {}
    checks["python"] = {"status": "PASS",
                        "detail": f"{sys.version_info.major}.{sys.version_info.minor}"}
    for b in ("ffmpeg", "ffprobe"):
        ok = shutil.which(getattr(get_settings(), f"{b}_path", b)) is not None
        checks[b] = {"status": "PASS" if ok else "FAIL"}
    try:
        init_db()
        checks["database"] = {"status": "PASS"}
    except Exception as e:  # noqa: BLE001 - doctor reports all failures, never raises
        checks["database"] = {"status": "FAIL", "detail": str(e)[:120]}
    try:
        LocalFilesystemStorage(get_settings().storage_path).list("")
        checks["storage"] = {"status": "PASS"}
    except Exception as e:  # noqa: BLE001 - doctor reports all failures, never raises
        checks["storage"] = {"status": "FAIL", "detail": str(e)[:120]}
    try:
        import faster_whisper  # noqa
        checks["stt"] = {"status": "PASS", "detail": "faster-whisper installed"}
    except ImportError:
        checks["stt"] = {"status": "WARN", "detail": "heuristic/STT unavailable"}
    llm = get_settings().llm_provider
    checks["llm"] = {"status": "PASS" if llm == "heuristic" else "WARN",
                     "detail": f"provider={llm}"}
    import shutil as _sh
    free = _sh.disk_usage(get_settings().storage_path).free // 10**9
    checks["disk"] = {"status": "PASS" if free > 1 else "WARN", "detail": f"{free}GB free"}
    checks["worker"] = {"status": "PASS", "detail": "db-backed queue"}
    _fmt(checks, a.json)
    if any(c["status"] == "FAIL" for c in checks.values()):
        sys.exit(1)


def cmd_campaign(a):
    from .models.entities import Campaign
    from .services.campaigns import blockers, create_from_dict, p0_missing
    _, db, _ = _ctx()
    if a.action == "create":
        with open(a.rules) as _f:
            rules = json.loads(_f.read())
        c = create_from_dict(db, "local", a.name, rules, a.verified)
        _fmt({"id": c.id, "blockers": blockers(c.rules or {}, c.verified)}, a.json)
    elif a.action == "check":
        c = db.query(Campaign).filter_by(id=a.campaign_id).first()
        if not c:
            print(json.dumps({"error": "campaign not found"}))
            sys.exit(2)
        _fmt({"blockers": blockers(c.rules or {}, c.verified), "p0_missing": p0_missing(c.rules or {})}, a.json)
    elif a.action == "validate":
        from .validation.campaign import validate_job
        c = db.query(Campaign).filter_by(id=a.campaign_id).first()
        if not c:
            print(json.dumps({"error": "campaign not found"}))
            sys.exit(2)
        if a.clips:
            with open(a.clips) as _f:
                clips = json.loads(_f.read())
        else:
            clips = []
        job = json.loads(a.job or "{}")
        v = validate_job(clips, c.rules or {}, job)
        _fmt(v, a.json)
        if v["status"] != "READY" and not a.json:
            print("NOT READY")
    else:
        rows = db.query(Campaign).all()
        _fmt([{"id": c.id, "name": c.name, "verified": c.verified} for c in rows], a.json)


def main(argv=None):
    setup()
    ap = argparse.ArgumentParser(prog="repurpose")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("title", nargs="?", default="Untitled")
    p.add_argument("--description", default=""); p.add_argument("--config", default="{}")
    p = sub.add_parser("ingest"); p.add_argument("project"); p.add_argument("source")
    p = sub.add_parser("analyze"); p.add_argument("project")
    p = sub.add_parser("transcribe"); p.add_argument("project")
    p.add_argument("--model", default=""); p.add_argument("--force", action="store_true")
    p = sub.add_parser("candidates"); p.add_argument("project")
    p = sub.add_parser("rank"); p.add_argument("project"); p.add_argument("--n", type=int, default=5)
    p = sub.add_parser("render"); p.add_argument("project")
    p = sub.add_parser("validate"); p.add_argument("project")
    p = sub.add_parser("run"); p.add_argument("project")
    p.add_argument("--source", default=""); p.add_argument("--params", default="{}")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("export"); p.add_argument("project")
    p = sub.add_parser("campaign")
    p.add_argument("action", choices=["list", "create", "check", "validate"])
    p.add_argument("--name", default=""); p.add_argument("--rules", default="")
    p.add_argument("--campaign-id", default=""); p.add_argument("--verified", action="store_true")
    p.add_argument("--clips", default=""); p.add_argument("--job", default="{}")
    sub.add_parser("doctor")
    a = ap.parse_args(argv)
    {"init": cmd_init, "campaign": cmd_campaign, "ingest": cmd_ingest, "analyze": cmd_analyze,
     "transcribe": cmd_transcribe, "candidates": cmd_candidates, "rank": cmd_rank,
     "render": cmd_render, "validate": cmd_validate, "run": cmd_run,
     "export": cmd_export, "doctor": cmd_doctor}[a.cmd](a)


if __name__ == "__main__":
    main()
