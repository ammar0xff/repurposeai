"""Integration: API CRUD, auth, authz, jobs, review, export (needs backend deps)."""
import os
import sys

sys.path.insert(0, ".")

os.environ["DATABASE_URL"] = "sqlite:////tmp/rpa_test.db"
for f in ("/tmp/rpa_test.db",):
    try:
        os.unlink(f)
    except OSError:
        pass

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.db import init_db  # noqa: E402

init_db("sqlite:////tmp/rpa_test.db")
client = TestClient(app, raise_server_exceptions=False)


def test_projects_crud():
    r = client.post("/api/projects", json={"title": "T1"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get("/api/projects").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 200
    assert client.get("/api/projects/nope").status_code == 404
    assert client.delete(f"/api/projects/{pid}").status_code == 200


def test_auth_enforced_when_token_set(monkeypatch):
    from app.config.settings import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("AUTH_TOKEN", "secret123")
    get_settings.cache_clear()
    try:
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/projects",
                          headers={"Authorization": "Bearer secret123"}).status_code == 200
    finally:
        monkeypatch.delenv("AUTH_TOKEN")
        get_settings.cache_clear()


def test_system_endpoints():
    assert client.get("/api/system/health").json()["status"] == "ok"
    r = client.get("/api/system/readiness")
    assert "checks" in r.json()
    assert "llm" in client.get("/api/system/providers").json()


def test_openapi_present():
    assert client.get("/api/openapi.json").status_code == 200
