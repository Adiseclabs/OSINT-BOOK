import io, json, hashlib
from pathlib import Path
from app import config
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64

def mkcase(client, h, **kw):
    body = {"title": "T", "authorization_notes": "Authorized test", "status": "Active", **kw}
    r = client.post("/api/cases", json=body, headers=h); assert r.status_code == 201, r.text; return r.json()

def test_auth_required(client):
    assert client.get("/api/cases").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code == 401

def test_case_requires_authorization_note(client, admin):
    r = client.post("/api/cases", json={"title": "x"}, headers=admin); assert r.status_code == 422

def test_validation_and_crud(client, admin):
    c = mkcase(client, admin); cid = c["id"]
    assert c["ref"].startswith("CASE-2026-")
    r = client.post(f"/api/sources?case_id={cid}", json={"title": "S", "reliability": "Nope"}, headers=admin); assert r.status_code == 422
    r = client.post(f"/api/sources?case_id={cid}", json={"title": "S", "reliability": "High", "bogus": 1}, headers=admin); assert r.status_code == 422
    r = client.post(f"/api/sources?case_id={cid}", json={"title": "S", "reliability": "High", "access_date": "2026-10-07"}, headers=admin); assert r.status_code == 201
    s = r.json(); assert s["ref"].startswith("SRC-")
    # SQL-injection-like search string is treated as data
    r = client.get(f"/api/sources?case_id={cid}&q=' OR 1=1 --", headers=admin); assert r.json()["total"] == 0
    assert client.patch(f"/api/sources/{s['id']}", json={"title": "S2"}, headers=admin).json()["title"] == "S2"

def test_sensitive_identifier_masking(client, admin):
    cid = mkcase(client, admin)["id"]
    b = {"value": "alex.morgan@example.org", "id_type": "Email"}
    assert client.post(f"/api/identifiers?case_id={cid}", json=b, headers=admin).status_code == 422
    r = client.post(f"/api/identifiers?case_id={cid}", json={**b, "sensitive_ack": True}, headers=admin); assert r.status_code == 201
    assert r.json()["value"].startswith("al") and "*" in r.json()["value"]
    full = client.get(f"/api/identifiers/{r.json()['id']}?reveal=true", headers=admin).json()
    assert full["value"] == "alex.morgan@example.org"
    acts = [a["action"] for a in client.get(f"/api/audit?case_id={cid}", headers=admin).json()["items"]]
    assert "REVEALED" in acts

def test_evidence_integrity_and_upload_safety(client, admin):
    cid = mkcase(client, admin)["id"]
    up = lambda name, data, **kw: client.post("/api/evidence", data={"case_id": cid, "evidence_type": "Document", **kw}, files={"file": (name, io.BytesIO(data))}, headers=admin)
    assert up("evil.exe", b"MZ").status_code == 415
    assert up("fake.png", b"not a png").status_code == 415
    assert up("empty.txt", b"").status_code == 422
    r = up("../../etc/passwd.txt", b"hello evidence"); assert r.status_code == 201, r.text
    ev = r.json(); assert ev["sha256"] == hashlib.sha256(b"hello evidence").hexdigest()
    assert "/" not in ev["original_filename"] and ".." not in ev["storage_path"].replace("../", "x")
    assert client.post(f"/api/evidence/{ev['id']}/verify", headers=admin).json()["result"] == "VALID"
    (config.DATA_DIR / ev["storage_path"]).write_bytes(b"tampered")
    assert client.post(f"/api/evidence/{ev['id']}/verify", headers=admin).json()["result"] == "MISMATCH"
    assert client.get(f"/api/evidence/{ev['id']}", headers=admin).json()["integrity_status"] == "MISMATCH"
    assert client.patch(f"/api/evidence/{ev['id']}", json={"sha256": "x"}, headers=admin).status_code == 422  # hash immutable
    cust = [x["action"] for x in client.get(f"/api/evidence/{ev['id']}/custody", headers=admin).json()]
    assert {"EVIDENCE_UPLOADED", "EVIDENCE_HASH_VERIFIED", "VIEWED"} <= set(cust)
    r = client.get(f"/api/evidence/{ev['id']}/preview", headers=admin); assert "sandbox" in r.headers["content-security-policy"]
    assert client.delete(f"/api/evidence/{ev['id']}", headers=admin).status_code == 200
    assert not (config.DATA_DIR / ev["storage_path"]).exists()

def test_html_evidence_is_never_rendered(client, admin):
    cid = mkcase(client, admin)["id"]
    r = client.post("/api/evidence", data={"case_id": cid, "evidence_type": "HTML export"}, files={"file": ("p.html", io.BytesIO(b"<script>alert(1)</script>"))}, headers=admin).json()
    p = client.get(f"/api/evidence/{r['id']}/preview", headers=admin)
    assert p.headers["content-type"].startswith("application/json") and p.json()["kind"] == "text"

def test_audit_is_append_only_and_chained(client, admin):
    from app.db import engine
    from sqlalchemy import text
    import sqlalchemy
    with engine.begin() as c:
        try: c.execute(text("DELETE FROM audit_logs")); assert False, "delete should be blocked"
        except sqlalchemy.exc.DatabaseError: pass
    assert client.get("/api/audit/verify", headers=admin).json()["valid"] is True

def test_permissions(client, admin, viewer, other):
    c = mkcase(client, admin); cid = c["id"]
    assert client.get(f"/api/cases/{cid}", headers=other).status_code == 403
    assert cid not in [x["id"] for x in client.get("/api/cases", headers=other).json()["items"]]
    users = {u["username"]: u["id"] for u in client.get("/api/users", headers=admin).json()}
    client.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": users["viewer1"], "access": "read"}]}, headers=admin)
    assert client.get(f"/api/cases/{cid}", headers=viewer).status_code == 200
    assert client.post(f"/api/sources?case_id={cid}", json={"title": "x"}, headers=viewer).status_code == 403

def test_findings_provenance_and_relationship_rules(client, admin):
    cid = mkcase(client, admin)["id"]
    src = client.post(f"/api/sources?case_id={cid}", json={"title": "Staff page", "url": "https://example.org/p", "reliability": "High"}, headers=admin).json()
    f = client.post(f"/api/findings?case_id={cid}", json={"title": "Claim", "kind": "INFERENCE", "confidence": "Medium"}, headers=admin).json()
    assert client.post(f"/api/findings/{f['id']}/links", json={"target_type": "source", "target_id": src["id"]}, headers=admin).status_code == 201
    pv = client.get(f"/api/findings/{f['id']}/provenance", headers=admin).json()
    assert pv["sources"][0]["ref"] == src["ref"] and pv["kind"] == "INFERENCE"
    s1 = client.post(f"/api/subjects?case_id={cid}", json={"display_name": "A"}, headers=admin).json()
    d = client.post(f"/api/domains?case_id={cid}", json={"name": "example.org"}, headers=admin).json()
    rel = {"from_type": "subject", "from_id": s1["id"], "to_type": "domain", "to_id": d["id"], "rel_type": "OWNS", "certainty": "CONFIRMED"}
    assert client.post(f"/api/relationships?case_id={cid}", json=rel, headers=admin).status_code == 422  # confirmed needs support
    assert client.post(f"/api/relationships?case_id={cid}", json={**rel, "certainty": "LIKELY", "confidence_pct": 70}, headers=admin).status_code == 201
    g = client.get(f"/api/graph?case_id={cid}", headers=admin).json(); assert len(g["edges"]) == 1

def test_tools_run_attach_and_ssrf(client, admin):
    cid = mkcase(client, admin)["id"]
    r = client.post("/api/tools/run", json={"tool": "entity_extraction", "case_id": cid, "input": {"text": "Contact a@example.org or visit https://example.org/x from 192.0.2.7 on 2026-09-01"}}, headers=admin)
    assert r.status_code == 201 and r.json()["status"] == "Completed", r.text
    res = r.json()["result"]; assert res["data"]["ips"] == ["192.0.2.7"] and res["ref"].startswith("ENT-")
    a = client.post(f"/api/tools/results/{res['id']}/attach", json={"case_id": cid, "as_evidence": True}, headers=admin).json()
    assert a["result"]["evidence_id"]
    ssrf = client.post("/api/tools/run", json={"tool": "http_headers", "input": {"url": "http://127.0.0.1:8000/api/health"}}, headers=admin).json()
    assert ssrf["status"] == "Failed" and "non-public" in ssrf["error"]
    assert client.post("/api/tools/run", json={"tool": "dns_lookup", "input": {"domain": "not a domain"}}, headers=admin).json()["status"] == "Failed"

def test_reports_and_backup_roundtrip(client, admin):
    c = mkcase(client, admin); cid = c["id"]
    client.post(f"/api/findings?case_id={cid}", json={"title": "Unlinked hypothesis", "kind": "HYPOTHESIS"}, headers=admin)
    for fmt in ("html", "json", "pdf"):
        rep = client.post("/api/reports", json={"case_id": cid, "format": fmt, "conclusion": "Done"}, headers=admin); assert rep.status_code == 201, rep.text
        dl = client.get(f"/api/reports/{rep.json()['id']}/download", headers=admin); assert dl.status_code == 200 and len(dl.content) > 100
        if fmt == "html": assert b"UNSUPPORTED" in dl.content and b"HYPOTHESIS" in dl.content and b"not confirmed" in dl.content.lower()
        if fmt == "pdf": assert dl.content.startswith(b"%PDF")
    b = client.post(f"/api/backup/case/{cid}", headers=admin).json()
    z = client.get(f"/api/backup/{b['name']}/download", headers=admin).content
    assert client.post("/api/backup/verify", files={"file": ("b.zip", io.BytesIO(z))}, headers=admin).json()["valid"]
    import zipfile; zin = zipfile.ZipFile(io.BytesIO(z)); out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zo:
        for n in zin.namelist(): zo.writestr(n, zin.read(n) + (b"x" if n == "case.json" else b""))
    assert client.post("/api/backup/verify", files={"file": ("b.zip", io.BytesIO(out.getvalue()))}, headers=admin).status_code == 422
    assert client.post("/api/backup/restore", files={"file": ("b.zip", io.BytesIO(z))}, headers=admin).status_code == 409  # exists
    full = client.post("/api/backup/database", headers=admin).json(); assert full["size"] > 0

def test_ai_suggestions_require_approval(client, admin):
    cid = mkcase(client, admin)["id"]
    for plat in ("A", "B"):
        client.post(f"/api/accounts?case_id={cid}", json={"platform": plat, "username": "alexm"}, headers=admin)
    s = client.post("/api/ai/analyze", json={"case_id": cid, "task": "relationships"}, headers=admin).json()
    assert len(s) == 1 and s[0]["payload"]["label"] == "AI GENERATED" and s[0]["status"] == "Pending"
    assert client.get(f"/api/relationships?case_id={cid}", headers=admin).json()["total"] == 0   # nothing official yet
    assert client.post(f"/api/ai/suggestions/{s[0]['id']}/approve", headers=admin).status_code == 200
    rel = client.get(f"/api/relationships?case_id={cid}", headers=admin).json()["items"][0]; assert rel["certainty"] == "POSSIBLE"
    f = client.post("/api/ai/analyze", json={"case_id": cid, "task": "summarize"}, headers=admin).json(); assert f[0]["kind"] == "summary"

def test_lockout(client):
    for _ in range(5): client.post("/api/auth/login", json={"username": "other", "password": "bad"})
    assert client.post("/api/auth/login", json={"username": "other", "password": "UserPass12345"}).status_code == 429

def test_templates_analytics_import(client, admin):
    c = mkcase(client, admin, case_type="Corporate impersonation", tlp="GREEN"); cid = c["id"]
    assert c["tlp"] == "GREEN"
    assert client.get(f"/api/tasks?case_id={cid}", headers=admin).json()["total"] >= 6   # template tasks
    csvb = b"platform,username,status\nGitHub,alexm,Active\nX,,Active\n"
    r = client.post("/api/import/accounts", data={"case_id": cid}, files={"file": ("a.csv", io.BytesIO(csvb))}, headers=admin).json()
    assert r["imported"] == 1 and r["rejected"] == 1
    e = b"id_type,value\nEmail,a@example.org\n"
    assert client.post("/api/import/identifiers", data={"case_id": cid}, files={"file": ("i.csv", io.BytesIO(e))}, headers=admin).json()["imported"] == 0
    a = client.get(f"/api/cases/{cid}/analytics", headers=admin).json()
    assert any(not x["ok"] for x in a["checks"]) and a["totals"]["accounts"] == 1
    assert client.get("/api/about", headers=admin).json()["author"] == "Aditya Bhosale"
