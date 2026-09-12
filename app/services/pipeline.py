"""Pipeline service: stage-by-stage orchestration over pure functions.
Callable from API, CLI, worker, MCP. Idempotent per stage (skip when done
unless force=True). Persist checkpoints after every stage (resumability)."""
from pathlib import Path

from ..core.errors import MediaError
from ..core.ids import new_id
from ..core.logging import log, set_ctx
from ..media.analyze import analyze
from ..media.signals import scene_cuts, silence
from ..models.entities import (
    Candidate,
    CandidateScore,
    Clip,
    MediaAsset,
    PipelineStage,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
)
from ..pipelines.candidates import eligible, generate
from ..pipelines.sentences import to_sentences  # noqa: F401 (public step)
from ..providers.llm import get_llm_provider
from ..providers.remote_transcribe import RemoteGitHubProvider, pick_stt
from ..providers.stt import FasterWhisperProvider
from ..ranking.resolve import resolve
from ..ranking.service import rank as rank_service
from ..rendering.renderer import PROFILES, Renderer
from ..storage.base import StorageProvider, project_key
from ..validation.checks import validate_clip

STAGES = ["ingest", "analyze", "transcribe", "segment", "rank",
          "resolve", "render", "validate"]


def _utc():
    import datetime as _dt
    return _dt.datetime.now(_dt.UTC)


_STOP: dict[str, bool] = {}  # process-wide cancel flags (worker + API share them)


class Pipeline:
    def __init__(self, db, storage: StorageProvider, settings):
        self.db, self.storage, self.s = db, storage, settings

    # ----- stage bookkeeping -----
    def _heartbeat(self, job: ProcessingJob):
        job.last_heartbeat = _utc()
        # no commit here: callers commit with their own mutation

    def _stage(self, job: ProcessingJob, name: str) -> PipelineStage:
        st = self.db.query(PipelineStage).filter_by(job_id=job.id, name=name).first()
        if not st:
            st = PipelineStage(id=new_id(), job_id=job.id, name=name)
            self.db.add(st)
            self.db.commit()
        return st

    def _begin(self, job: ProcessingJob, name: str) -> PipelineStage:
        st = self._stage(job, name)
        st.status, st.started_at, st.error = "running", _utc(), ""
        job.current_stage, job.status = name, "running"
        self._heartbeat(job)
        self.db.commit()
        set_ctx(stage=name)
        log.info("stage begin: %s", name)
        return st

    def _done(self, job: ProcessingJob, st: PipelineStage, progress: int):
        st.status, st.completed_at, st.progress = "done", _utc(), 100
        job.progress = progress
        self._heartbeat(job)
        self.db.commit()
        log.info("stage done: %s", st.name)

    def _fail(self, job: ProcessingJob, st: PipelineStage, e: Exception):
        st.status, st.error, st.completed_at = "failed", f"{type(e).__name__}: {e}", _utc()
        job.status, job.error = "failed", f"{type(e).__name__}: {e}"
        self._heartbeat(job)
        self.db.commit()
        log.error("stage failed: %s: %s", st.name, e)

    @staticmethod
    def cancel(job_id: str):
        _STOP[job_id] = True

    def _cancelled(self, job: ProcessingJob) -> bool:
        if _STOP.pop(job.id, False):
            job.status = "cancelled"
            self.db.commit()
            log.warning("job cancelled: %s", job.id)
            return True
        return False

    # ----- stages -----
    def ingest(self, job: ProcessingJob, project: Project, source: str,
               upload_bytes: bytes | None = None, filename: str = "") -> str:
        st = self._begin(job, "ingest")
        try:
            if (job.params or {}).get("preuploaded") and self.storage.exists(source):
                key = source
                log.info("ingest: using pre-uploaded key %s", key)
            elif upload_bytes is not None:
                safe = "".join(c for c in filename if c.isalnum() or c in "._-")[-80:] or "upload"
                key = project_key(project.id, "source", safe)
                self.storage.put(key, upload_bytes)
            elif source.startswith(("http://", "https://")):
                key = self._download(source, project)
            else:
                key = project_key(project.id, "source", _safe_name(source))
                self.storage.put_file(key, source)
            a = MediaAsset(id=new_id(), project_id=project.id, kind="source",
                           storage_key=key, size=0, meta={})
            self.db.add(a)
            self.db.commit()
            self._done(job, st, 8)
            return key
        except Exception as e:
            self._fail(job, st, e)
            raise

    def _download(self, url: str, project: Project) -> str:
        import urllib.request
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1][:80] or "remote"
        key = project_key(project.id, "source", _safe_name(name))
        dest = self.storage._p(key) if hasattr(self.storage, "_p") else None
        if "wetransfer.com" in url or url.startswith("https://we.tl/"):
            return self._wetransfer(url, project)
        try:
            import subprocess
            tmp = f"/tmp/rpa-dl-{new_id()}"
            subprocess.run(["yt-dlp", "-f", "mp4/best[height<=1080]/best", "--no-playlist",
                            "-o", tmp, url], check=True, timeout=1800)
            self.storage.put_file(key, tmp)
            import os
            os.unlink(tmp)
            return key
        except FileNotFoundError:
            req = urllib.request.Request(url, headers={"User-Agent": "repurposeai/0.1"})
            with urllib.request.urlopen(req, timeout=300) as r, open(str(dest), "wb") as f:
                f.write(r.read())
            return key

    def _wetransfer(self, url: str, project: Project) -> str:
        import subprocess
        import sys
        vend = str(__import__("pathlib").Path(__file__).parent.parent.parent
                   / "vendor" / "transferwee.py")
        tmp = f"/tmp/rpa-wt-{new_id()}.mp4"
        subprocess.run([sys.executable, vend, "download", "-o", tmp, url],
                       check=True, timeout=1800)
        key = project_key(project.id, "source", f"wetransfer-{new_id()}.mp4")
        self.storage.put_file(key, tmp)
        import os
        os.unlink(tmp)
        return key

    def analyze(self, job: ProcessingJob, project: Project, storage_key: str) -> dict:
        st = self._begin(job, "analyze")
        try:
            info = analyze(self.storage.get_path(storage_key), self.s.ffprobe_path)
            project.duration = info["duration"]
            project.status = "analyzed"
            self.db.commit()
            self._done(job, st, 15)
            return info
        except Exception as e:
            self._fail(job, st, e)
            raise

    def _stt_override(self) -> str:
        from ..models.entities import SystemSetting
        row = self.db.query(SystemSetting).filter_by(key="stt_provider").first()
        if row and row.value in ("auto", "local", "github"):
            return row.value
        return ""

    def transcribe(self, job: ProcessingJob, project: Project, storage_key: str,
                   model: str = "", force: bool = False,
                   stt_provider: str = "") -> dict:
        st = self._begin(job, "transcribe")
        try:
            if not force:
                old = self.db.query(Transcript).filter_by(project_id=project.id).first()
                if old:
                    self._done(job, st, 35)
                    return {"words": old.words, "duration": old.duration,
                            "engine": old.engine, "cached": True}
            import subprocess
            wav = f"/tmp/rpa-{new_id()}.wav"
            subprocess.run([self.s.ffmpeg_path, "-y", "-v", "error", "-i",
                            self.storage.get_path(storage_key),
                            "-vn", "-ar", "16000", "-ac", "1", wav],
                           check=True, timeout=600)
            mode = stt_provider or self._stt_override() or self.s.stt_provider
            prov = FasterWhisperProvider(model or self.s.whisper_model,
                                         self.s.whisper_device, self.s.whisper_compute_type)
            remote = RemoteGitHubProvider(self.s.github_token, self.s.github_owner,
                                          self.s.github_repo, self.s.ffmpeg_path)
            choice = pick_stt(mode, prov.available(), remote.available())
            if choice == "local":
                tr = prov.transcribe(wav, model or self.s.whisper_model)
            elif choice == "remote":
                tr = remote.transcribe(wav, model or self.s.whisper_model)
            else:
                if mode == "github":
                    raise MediaError(
                        "Remote (GitHub Actions) STT unavailable: set "
                        "GITHUB_TOKEN/GITHUB_OWNER/GITHUB_REPO.")
                raise MediaError("STT provider unavailable (faster-whisper not installed).")
            import os
            os.unlink(wav)
            row = Transcript(id=new_id(), project_id=project.id, engine=tr["engine"],
                             language=tr.get("language"), duration=tr["duration"],
                             words=tr["words"], segments=tr.get("segments", []))
            self.db.add(row)
            self.db.commit()
            self._done(job, st, 35)
            return tr
        except Exception as e:
            self._fail(job, st, e)
            raise

    def segment(self, job: ProcessingJob, project: Project) -> dict:
        """Scenes + silence + sentences + candidates + eligibility. One checkpoint."""
        st = self._begin(job, "segment")
        try:
            tr = self.db.query(Transcript).filter_by(project_id=project.id).first()
            if not tr:
                raise MediaError("No transcript. Run transcribe first.")
            src = self._src_path(project)
            cuts, eng = scene_cuts(src)
            sil = silence(src)
            for i in range(len(cuts) - 1):
                self.db.add(Scene(id=new_id(), project_id=project.id,
                                  start=cuts[i], end=cuts[i + 1], engine=eng))
            cfg = (project.config or {})
            cands = generate(tr.words, tr.duration, sil, cuts,
                             float(cfg.get("min_duration", 15)),
                             float(cfg.get("max_duration", 60)))
            ok = eligible(cands, {
                "min_duration": cfg.get("min_duration", 15),
                "max_duration": cfg.get("max_duration", 60),
                "min_words": cfg.get("min_words", 8),
                "require_sentence_complete": cfg.get("require_sentence_complete", False),
                "blacklisted_phrases": cfg.get("blacklisted_phrases", []),
                "required_topics": cfg.get("required_topics", []),
                "excluded_topics": cfg.get("excluded_topics", []),
            })
            for c in ok:
                self.db.add(Candidate(id=new_id(), project_id=project.id, job_id=job.id,
                                      start=c["start"], end=c["end"], text=c["text"],
                                      hook_text=c["hook_text"], features=c["features"]))
            self.db.commit()
            self._done(job, st, 50)
            return {"cuts": len(cuts), "silence": len(sil), "candidates": len(cands),
                    "eligible": len(ok), "engine": eng}
        except Exception as e:
            self._fail(job, st, e)
            raise

    def rank(self, job: ProcessingJob, project: Project, n: int = 5) -> dict:
        st = self._begin(job, "rank")
        try:
            cfg = project.config or {}
            rows = self.db.query(Candidate).filter_by(
                project_id=project.id, job_id=job.id).all()
            tr = self.db.query(Transcript).filter_by(project_id=project.id).first()
            cands = [{"id": i, "start": r.start, "end": r.end, "text": r.text,
                      "hook_text": r.hook_text} for i, r in enumerate(rows)]
            provider = get_llm_provider(cfg.get("ai_provider") or self.s.llm_provider)
            moms, via = rank_service(
                cands, tr.words if tr else [], tr.duration if tr else 0, n,
                provider, cfg.get("ai_model", self.s.llm_model),
                cfg.get("ranking_profile", "balanced"),
                cfg.get("ranking_weights"))
            for m in moms:
                r = rows[m["candidate"]]
                r.score = m["score"]
                self.db.add(CandidateScore(candidate_id=r.id, source=m.get("source", via),
                                           model=m.get("model", ""),
                                           prompt_version=m.get("prompt_version", ""),
                                           axes=m.get("axes", {}), overall=m["score"] / 10,
                                           reason=m.get("reason", ""),
                                           profile=m.get("profile", cfg.get("ranking_profile", "balanced"))))
            self.db.commit()
            self._done(job, st, 65)
            return {"ranked": len(moms), "via": via}
        except Exception as e:
            self._fail(job, st, e)
            raise

    def resolve_render(self, job: ProcessingJob, project: Project) -> dict:
        """Resolve timestamps + render + validate + metadata. Resumable per clip."""
        cfg = project.config or {}
        profile = cfg.get("render_profile", "shorts_1080x1920")
        reframe = cfg.get("reframe", "smart")
        style = cfg.get("caption_style", "bold")
        tr = self.db.query(Transcript).filter_by(project_id=project.id).first()
        words = tr.words if tr else []
        rows = self.db.query(Candidate).filter_by(
            project_id=project.id, job_id=job.id).order_by(Candidate.score.desc()).all()
        n = int(cfg.get("clip_count", 5))
        rdr = Renderer(self.s.ffmpeg_path)
        done = 0
        for r in rows[:n]:
            if self._cancelled(job):
                return {"rendered": done, "cancelled": True}
            self._heartbeat(job)  # render can run minutes; keep liveness fresh
            exists = self.db.query(Clip).filter_by(candidate_id=r.id).first()
            if exists:  # idempotent resume
                done += 1
                continue
            st = self._begin(job, f"render:{r.id[:8]}")
            try:
                rs, re = resolve(r.start, r.end, words, tr.duration if tr else 0,
                                 max_len=float(cfg.get("max_duration", 60)))
                key = project_key(project.id, "clips", f"{r.id}.mp4")
                import os
                tmp = f"/tmp/rpa-clip-{r.id}.mp4"
                rdr.render(self._src_path(project), rs, re, words, tmp,
                                  profile, reframe, style, cfg.get("credit", ""))
                self.storage.put_file(key, tmp)
                # captions validation needs the .ass sidecar beside the clip
                ass_tmp = Path(tmp).with_suffix(".ass")
                if ass_tmp.exists():
                    self.storage.put_file(f"{Path(key).with_suffix('.ass')}", str(ass_tmp))
                vrep = validate_clip(self.storage.get_path(key), {
                    "width": PROFILES[profile]["w"], "height": PROFILES[profile]["h"],
                    "min_duration": cfg.get("min_duration", 15),
                    "max_duration": cfg.get("max_duration", 60),
                    "need_audio": True, "need_captions": True})
                clip = Clip(id=new_id(), project_id=project.id, job_id=job.id,
                            candidate_id=r.id, start=rs, end=re, storage_key=key,
                            status="rendered" if vrep["status"] == "READY" else "failed",
                            render_profile=profile, validation=vrep)
                self.db.add(clip)
                try:
                    from ..models.entities import GeneratedMetadata as _GM
                    from ..providers.llm import get_llm_provider as _gllm
                    from .metadata import generate as _genmd
                    md = _genmd(r.text, _gllm(cfg.get("ai_provider") or self.s.llm_provider),
                                cfg.get("ai_model", self.s.llm_model),
                                cfg.get("hashtags", []))
                    self.db.add(_GM(id=new_id(), clip_id=clip.id, titles=md["titles"],
                                    description=md["description"], caption=md["caption"],
                                    hashtags=md["hashtags"], keywords=md["keywords"]))
                except Exception as e:  # noqa: BLE001 - metadata must never break renders
                    log.warning("metadata generation skipped: %s", e)
                os.unlink(tmp)
                self._done(job, st, 65 + int(30 * (done + 1) / max(n, 1)))
                done += 1
            except Exception as e:  # noqa: BLE001 - per-clip guard: record, continue batch
                self._fail(job, st, e)
                continue
        return {"rendered": done}

    def run(self, job_id: str, force: bool = False) -> dict:
        """Full pipeline with per-stage resume. Returns summary."""
        from ..models.entities import ProcessingJob as PJ
        job = self.db.query(PJ).filter_by(id=job_id).first()
        if not job:
            raise ValueError("unknown job")
        project = self.db.query(Project).filter_by(id=job.project_id).first()
        set_ctx(job_id=job.id, project_id=project.id)
        job.status, job.error = "running", ""
        self._heartbeat(job)
        self.db.commit()
        params = job.params or {}
        try:
            self._campaign_for(job, project, params)  # merges rules, enforces gate
            done_stages = {s.name for s in job.stages if s.status == "done"} if not force else set()
            src_key = params.get("storage_key", "")
            if "ingest" not in done_stages:
                src_key = self.ingest(job, project, params.get("source", ""),
                                      filename=params.get("filename", ""))
                params["storage_key"] = src_key
                job.params = params
                self.db.commit()
            else:
                # Resume-safe: params may predate the storage_key field; fall back
                # to the project's registered source asset.
                src_key = params.get("storage_key") or self._src_key_for(project)
            if self._cancelled(job):
                return {"job": job.id, "cancelled": True}
            if "analyze" not in done_stages:
                self.analyze(job, project, src_key)
            if "transcribe" not in done_stages:
                self.transcribe(job, project, src_key, params.get("whisper_model", ""), force,
                                params.get("stt_provider", ""))
            if "segment" not in done_stages:
                self.segment(job, project)
            # rank+resolve+render
            if "rank" not in done_stages:
                self.rank(job, project, int(params.get("clip_count", 5)))
            res = self.resolve_render(job, project)
            if res.get("cancelled"):
                return {"job": job.id, "cancelled": True}
            job.status, job.progress = "ready_for_review", 100
            self.db.commit()
            log.info("job ready_for_review: %s", job.id)
            return {"job": job.id, "status": job.status, **res}
        except Exception as e:  # noqa: BLE001 - top-level guard: mark failed, never crash worker
            if job.status != "failed":
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"
                self.db.commit()
            return {"job": job.id, "status": "failed", "error": str(e)}

    def _campaign_for(self, job: ProcessingJob, project: Project, params: dict):
        """Apply campaign policy: merge rules into config, enforce strict gate.
        Returns the Campaign or None. Refuses production runs with blockers."""
        cid = params.get("campaign_id", "")
        if not cid:
            return None
        from ..models.entities import Campaign
        from .campaigns import blockers, to_project_config
        camp = self.db.query(Campaign).filter_by(id=cid).first()
        if not camp:
            raise ValueError("unknown campaign")
        blk = blockers(camp.rules or {}, camp.verified)
        if blk and not params.get("no_strict"):
            raise ValueError(f"campaign blocked: {blk}")
        cfg = dict(project.config or {})
        cfg.update(to_project_config(camp.rules or {}))
        project.config = cfg
        job.params = {**params, "campaign_name": camp.name,
                      "credit_used": cfg.get("credit", ""),
                      "extra_tags": cfg.get("hashtags", [])}
        self.db.commit()
        log.info("campaign %s applied (strict=%s)", camp.name, not params.get("no_strict"))
        return camp

    def _src_path(self, project: Project) -> str:
        a = self.db.query(MediaAsset).filter_by(
            project_id=project.id, kind="source").order_by(
                MediaAsset.created_at.desc()).first()
        if not a:
            raise MediaError("No source asset. Ingest first.")
        return self.storage.get_path(a.storage_key)

    def _src_key_for(self, project: Project) -> str:
        a = self.db.query(MediaAsset).filter_by(
            project_id=project.id, kind="source").order_by(
                MediaAsset.created_at.desc()).first()
        if not a:
            raise MediaError("No source asset. Ingest first.")
        return a.storage_key


def _safe_name(name: str) -> str:
    base = (name.rsplit("/", 1)[-1] or "file").strip()
    safe = "".join(c for c in base if c.isalnum() or c in "._-")[-100:]
    return safe or "file"
