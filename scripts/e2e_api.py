"""End-to-end API driver: project -> upload -> process -> poll -> clips ->
approve -> export. Usage: python3 scripts/e2e_api.py <base> <media> [config_json].
Exit 0 only when export manifest has >=1 clip."""
import json
import sys
import time
import urllib.request

BASE, MEDIA = sys.argv[1], sys.argv[2]
CFG = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}


def call(method, path, body=None, files=None):
    data, headers = None, {}
    if files:
        import uuid
        b = "----" + uuid.uuid4().hex
        with open(MEDIA, "rb") as _f:
            raw = _f.read()
        data = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"demo.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").encode() + raw + f"\r\n--{b}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={b}"}
    elif body is not None:
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read() or b"{}")


pid = call("POST", "/api/projects", {"title": "e2e", "config": CFG})["id"]
print("project:", pid, flush=True)
key = call("POST", f"/api/projects/{pid}/upload", files=True)["storage_key"]
print("uploaded:", key, flush=True)
jid = call("POST", f"/api/projects/{pid}/process",
           {"upload_key": key, "params": {"whisper_model": "tiny"}})["job_id"]
print("job:", jid, flush=True)
for _ in range(60):
    j = call("GET", f"/api/jobs/{jid}")
    print("poll:", j["status"], j["progress"], j.get("current_stage"), flush=True)
    if j["status"] in ("ready_for_review", "failed", "cancelled"):
        break
    time.sleep(15)
assert j["status"] == "ready_for_review", f"job failed: {j.get('error')}"
clips = call("GET", f"/api/projects/{pid}/clips")
print("clips:", len(clips), flush=True)
assert clips, "no clips rendered"
first = call("POST", f"/api/clips/{clips[0]['id']}/approve", {"decision": "approved"})
assert first["decision"] == "approved"
exp = call("POST", f"/api/projects/{pid}/export")
assert len(exp["manifest"].get("clips", [])) >= 1, "empty export"
print("EXPORT-OK:", exp["id"], len(exp["manifest"]["clips"]), "clips", flush=True)
