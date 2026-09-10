"""Structured logging: request_id/job_id/project_id/stage on every record."""
import json
import logging
import sys
import time
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_job_id: ContextVar[str] = ContextVar("job_id", default="-")
_project_id: ContextVar[str] = ContextVar("project_id", default="-")
_stage: ContextVar[str] = ContextVar("stage", default="-")


def set_ctx(*, request_id=None, job_id=None, project_id=None, stage=None):
    if request_id is not None:
        _request_id.set(request_id)
    if job_id is not None:
        _job_id.set(job_id)
    if project_id is not None:
        _project_id.set(project_id)
    if stage is not None:
        _stage.set(stage)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": _request_id.get(), "job_id": _job_id.get(),
            "project_id": _project_id.get(), "stage": _stage.get(),
        })


def setup(level: str = "INFO") -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("repurposeai")
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False
    return root


log = logging.getLogger("repurposeai")
