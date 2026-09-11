"""FastAPI app: routers, errors, CORS, secure headers, static web UI, lifespan worker."""
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from .api import auth, campaigns, clips, jobs, projects, system
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


from .core.ratelimit import LIMITER

LIMITER.per_minute = int(os.environ.get("RATE_PER_MINUTE", "600"))


@app.middleware("http")
async def _ctx(request: Request, call_next):
    if request.url.path.startswith("/api/") and not LIMITER.allow(
            (request.client.host if request.client else "?") + request.url.path):
        return JSONResponse({"error": "rate_limited",
                             "message": "Too many requests. Slow down.",
                             "hint": "RATE_PER_MINUTE"}, status_code=429)
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


app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(clips.router)
app.include_router(system.router)


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .config.settings import get_settings as _gs
    from .models.db import init_db
    from .services.pipeline import Pipeline
    from .storage.local import LocalFilesystemStorage
    from .workers import set_worker
    from .workers.runner import Worker
    st = _gs()
    init_db()
    store = LocalFilesystemStorage(st.storage_path)
    w = Worker(lambda db: Pipeline(db, store, st),
               max_jobs=st.max_concurrent_jobs)
    set_worker(w)
    w.start()
    yield
    w.stop()


app.router.lifespan_context = lifespan


WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def web(path: str) -> Response:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    root = WEB_DIST.resolve()
    target = (root / path).resolve()
    if target != root and not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Bad request")
    if target.is_file():
        return FileResponse(target)
    if "." in Path(path).name:
        raise HTTPException(status_code=404, detail="Not Found")
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
