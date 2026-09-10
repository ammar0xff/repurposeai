"""Integration: API CRUD, auth, authz, jobs, review, export (needs backend deps)."""
import os
import sys

sys.path.insert(0, ".")

TEST_URL = "sqlite:////tmp/rpa_test.db"
for f in ("/tmp/rpa_test.db",):
    try:
        os.unlink(f)
    except OSError:
        pass

from fastapi.testclient import TestClient

from app.api.deps import db_session
from app.main import app
from app.models.db import get_session_factory, init_db

init_db(TEST_URL)


def _test_db():
    db = get_session_factory(TEST_URL)()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[db_session] = _test_db
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


import uuid as _uuid

def _authed():
    u = 'u' + _uuid.uuid4().hex[:8]
    r = client.post("/api/auth/setup", json={"username": u, "password": "longpassword1"})
    assert r.status_code in (201, 403), r.text
    r = client.post("/api/auth/login", json={"username": u, "password": "longpassword1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, u


def test_password_auth_flow():
    h, u = _authed()
    assert client.get("/api/projects").status_code == 401  # no token, users exist
    assert client.get("/api/projects", headers=h).status_code == 200
    r = client.post("/api/auth/change", json={"username": u, "old_password": "longpassword1",
                                               "new_password": "longpassword2"})
    assert r.status_code == 200
    assert client.get("/api/projects", headers=h).status_code == 401  # rotated
    h2 = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": u, "password": "longpassword2"}).json()["token"]}
    assert client.get("/api/projects", headers=h2).status_code == 200
    assert client.post("/api/auth/logout", headers=h2).status_code == 200
    assert client.get("/api/projects", headers=h2).status_code == 401


def test_cross_user_isolation():
    import uuid as _uuid2
    h = _authed()[0]
    pid = client.post("/api/projects", json={"title": "iso"}, headers=h).json()["id"]
    u2 = "u" + _uuid2.uuid4().hex[:8]
    client.post("/api/auth/setup", json={"username": u2, "password": "longpassword2"})
    h2 = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": u2, "password": "longpassword2"}).json()["token"]}
    assert client.get(f"/api/projects/{pid}", headers=h2).status_code in (403, 404)
    mine = client.get("/api/projects", headers=h2).json()
    items = mine["items"] if isinstance(mine, dict) else mine
    assert all(p["id"] != pid for p in items)
