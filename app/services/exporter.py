"""Export: organized bundle + manifest.json (+ portable archive support)."""
import io
import json
import zipfile

from ..core.ids import new_id
from ..models.entities import Clip, Export, GeneratedMetadata, Transcript
from ..storage.base import project_key

PIPELINE_VERSION = "repurposeai/0.1"


def build_export(db, storage, project) -> Export:
    clips = db.query(Clip).filter_by(project_id=project.id).all()
    tr = db.query(Transcript).filter_by(project_id=project.id).first()
    items, files = [], {}
    for i, c in enumerate(sorted(clips, key=lambda x: x.start), 1):
        md = db.query(GeneratedMetadata).filter_by(clip_id=c.id).first()
        name = f"clip-{i:03d}.mp4"
        try:
            files[name] = storage.get(c.storage_key)
        except Exception:
            continue
        items.append({"id": c.id, "file": name, "start": c.start, "end": c.end,
                      "score": 0, "validation": c.validation,
                      "title": (md.titles[md.chosen_title] if md and md.titles else ""),
                      "hashtags": md.hashtags if md else []})
    manifest = {"project_id": project.id, "title": project.title,
                "pipeline_version": PIPELINE_VERSION,
                "config": project.config or {}, "clips": items}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(f"exports/{project.title}/{name}", data)
        z.writestr(f"exports/{project.title}/manifest.json",
                   json.dumps(manifest, indent=1))
        z.writestr(f"exports/{project.title}/metadata.json",
                   json.dumps([{"clip": c["id"], "title": c["title"],
                                "hashtags": c["hashtags"]} for c in items], indent=1))
        if tr:
            z.writestr(f"exports/{project.title}/transcript.json",
                       json.dumps({"words": tr.words, "engine": tr.engine}))
    key = project_key(project.id, "exports", f"export-{new_id()}.zip")
    storage.put(key, buf.getvalue())
    exp = Export(id=new_id(), project_id=project.id, storage_key=key, manifest=manifest)
    db.add(exp)
    db.commit()
    return exp


def project_archive(db, storage, project, include_media: bool = True) -> str:
    """Portable project archive for import/export (metadata + optional media)."""
    from ..models.entities import Candidate, MediaAsset, ReviewDecision
    data = {
        "project": {"title": project.title, "description": project.description,
                    "language": project.language, "config": project.config},
        "candidates": [{"start": c.start, "end": c.end, "text": c.text,
                        "score": c.score} for c in
                       db.query(Candidate).filter_by(project_id=project.id).all()],
        "decisions": [{"clip_id": d.clip_id, "decision": d.decision, "note": d.note}
                      for d in db.query(ReviewDecision).join(
                          Clip, ReviewDecision.clip_id == Clip.id).filter(
                              Clip.project_id == project.id).all()],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(data, indent=1))
        if include_media:
            for a in db.query(MediaAsset).filter_by(project_id=project.id, kind="source").all():
                try:
                    z.writestr(f"media/{a.id}", storage.get(a.storage_key))
                except Exception:
                    continue
    key = project_key(project.id, "exports", f"project-{new_id()}.rpa.zip")
    storage.put(key, buf.getvalue())
    return key
