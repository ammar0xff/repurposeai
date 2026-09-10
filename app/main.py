"""FastAPI app: routers, errors, CORS, secure headers, static web UI, lifespan worker."""
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import clips, jobs, projects, system
from .config.settings import get_settings
from .core.errors import RepurposeError
from .core.ids import new_id
from .core.logging import set_ctx, setup

setup()
app = FastAPI(title="RepurposeAI", version="0.1.0",
              docs_url="/api/docs", openapi_url="/api/openapi.json")
s = get_settings()
app.add_middleware(
    CORSMiddleware, allow_origins=s.cors_list(), allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def _ctx(request: Request, call_next):
    set_ctx(request_id=new_id())
    t0 = time.time()
    try:
        resp = await call_next(request)
    except RepurposeError as e:
        return JSONResponse({"error": e.code, "message": e.message, "hint": e.hint},
                            status_code=e.status)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Request-ID"] = new_id()
    resp.headers["X-Elapsed"] = f"{(time.time() - t0) * 1000:.0f}ms"
    return resp


@app.exception_handler(RepurposeError)
async def _domain_err(_: Request, e: RepurposeError):
    return JSONResponse({"error": e.code, "message": e.message, "hint": e.hint},
                        status_code=e.status)


app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(clips.router)
app.include_router(system.router)


@app.on_event("startup")
def _startup():
    from .config.settings import get_settings as _gs
    from .models.db import init_db
    from .storage.local import LocalFilesystemStorage
    from .workers import set_worker
    from .workers.runner import Worker
    from .services.pipeline import Pipeline
    st = _gs()
    init_db()
    LocalFilesystemStorage(st.storage_path)
    w = Worker(lambda db: Pipeline(db, LocalFilesystemStorage(st.storage_path), st),
               max_jobs=st.max_concurrent_jobs)
    set_worker(w)
    w.start()


try:
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="web")
except RuntimeError:
    pass  # frontend not built yet; API-only mode
