"""Integration: API CRUD, auth, authz, jobs, review, export (needs backend deps)."""
import os
import sys
import uuid as _uuid

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
    prov = client.get("/api/system/providers").json()
    assert "llm" in prov
    eng = prov["stt"]["engines"]
    assert set(eng) == {"auto", "local", "github"}
    assert all(isinstance(v, bool) for v in eng.values())


def test_system_settings_roundtrip():
    g = client.get("/api/system/settings")
    assert g.status_code == 200, g.text
    assert g.json()["stt_provider"] in ("auto", "local", "github")
    r = client.put("/api/system/settings", json={"stt_provider": "github"})
    assert r.status_code == 200, r.text
    assert r.json()["stt_provider"] == "github"
    assert r.json()["stt_override"] == "github"
    assert client.get("/api/system/settings").json()["stt_provider"] == "github"
    bad = client.put("/api/system/settings", json={"stt_provider": "nope"})
    assert bad.status_code == 422
    client.put("/api/system/settings", json={"stt_provider": "auto"})


def test_openapi_present():
    assert client.get("/api/openapi.json").status_code == 200


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


def test_campaigns_crud_and_gate():
    import uuid as _uuid3
    u3 = "u" + _uuid3.uuid4().hex[:8]
    client.post("/api/auth/setup", json={"username": u3, "password": "longpassword3"})
    hh = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": u3, "password": "longpassword3"}).json()["token"]}
    r = client.post("/api/campaigns", json={"name": "c1", "rules": {}, "verified": False}, headers=hh)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["ready"] is False and r.json()["blockers"]
    full = {"rate_per_1k": 1.5, "budget": "$1k", "sources": ["a.mp4"],
            "duration": {"min": 10, "max": 30}, "hashtags": ["@x"],
            "credit": {"required": True, "text": "@x"}, "cap": "$10"}
    r = client.put(f"/api/campaigns/{cid}", json={"name": "c1", "rules": full, "verified": True}, headers=hh)
    assert r.json()["ready"] is True, r.text
    assert client.get(f"/api/campaigns/{cid}", headers=hh).status_code == 200
    v = client.post("/api/campaigns/validate", json={"campaign_id": cid, "clips": [], "job": {}}, headers=hh).json()
    assert v["status"] == "NOT READY"  # no clips
    assert client.delete(f"/api/campaigns/{cid}", headers=hh).status_code == 200
