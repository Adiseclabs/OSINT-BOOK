"""Auth, users, cases, finding links, tags, audit log, settings, dashboard."""
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import *  # noqa
from .. import config
from ..security import (hash_password, verify_password, check_password_strength, create_session, current_user,
                        writer, admin, case_access, visible_case_ids, _h)
from ..audit import next_ref, log, verify_chain
from ..crud import clean, F, to_dict, CONF4, ENT_BY_TYPE

r = APIRouter(prefix="/api")

# ---------- auth ----------
@r.post("/auth/login")
def login(body: dict, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == str(body.get("username", "")).lower()).first()
    n = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if u and u.locked_until and u.locked_until > n:
        raise HTTPException(429, "Account temporarily locked after repeated failures. Try again in a few minutes.")
    if not u or not u.active or not verify_password(str(body.get("password", "")), u.password_hash):
        if u:
            u.failed_attempts += 1
            if u.failed_attempts >= config.LOGIN_MAX_FAILURES:
                u.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=config.LOGIN_LOCK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
                u.failed_attempts = 0
        log(db, u, "LOGIN_FAILED", "user", str(body.get("username", ""))[:64]); db.commit()
        raise HTTPException(401, "Invalid username or password")
    u.failed_attempts, u.locked_until, u.last_login = 0, None, now()
    token = create_session(db, u)
    log(db, u, "LOGIN", "user", u.username); db.commit()
    return {"token": token, "user": {"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role}}

@r.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = db.get(SessionRow, _h(request.headers["authorization"][7:].strip()))
    if s: db.delete(s)
    log(db, user, "LOGOUT", "user", user.username); db.commit()
    return {"ok": True}

@r.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}

@r.post("/auth/password")
def change_pw(body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(str(body.get("current", "")), user.password_hash):
        raise HTTPException(403, "Current password is incorrect")
    check_password_strength(str(body.get("new", "")))
    user.password_hash = hash_password(body["new"])
    db.query(SessionRow).filter(SessionRow.user_id == user.id).delete()
    log(db, user, "PASSWORD_CHANGED", "user", user.username); db.commit()
    return {"ok": True}

@r.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role, "active": u.active}
            for u in db.query(User).order_by(User.username)]

@r.post("/users", status_code=201)
def add_user(body: dict, db: Session = Depends(get_db), user: User = Depends(admin)):
    uname = str(body.get("username", "")).strip().lower()
    if not uname.isalnum() and not uname.replace("_", "").replace(".", "").isalnum():
        raise HTTPException(422, "Username: letters, digits, . and _ only")
    if db.query(User).filter_by(username=uname).first(): raise HTTPException(409, "Username exists")
    if body.get("role") not in ("admin", "investigator", "viewer"): raise HTTPException(422, "Invalid role")
    check_password_strength(str(body.get("password", "")))
    u = User(username=uname, display_name=str(body.get("display_name") or uname)[:100],
             password_hash=hash_password(body["password"]), role=body["role"])
    db.add(u); log(db, user, "USER_CREATED", "user", uname, role=u.role); db.commit()
    return {"id": u.id}

# ---------- settings ----------
DEFAULT_SETTINGS = {"mask_sensitive": "true", "allow_private_targets": "false", "ai_provider": "none",
                    "ai_model": "llama3.1", "org_name": "", "report_classification": "CONFIDENTIAL - INVESTIGATION WORK PRODUCT"}

def get_settings(db) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update({x.key: x.value for x in db.query(Setting)})
    return s

@r.get("/settings")
def settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_settings(db)

@r.put("/settings")
def put_settings(body: dict, db: Session = Depends(get_db), user: User = Depends(admin)):
    changed = {}
    for k, v in body.items():
        if k not in DEFAULT_SETTINGS: raise HTTPException(422, f"Unknown setting {k}")
        if k == "ai_provider" and v not in ("none", "ollama"): raise HTTPException(422, "ai_provider: none | ollama")
        v = str(v).lower() if v in (True, False) else str(v)[:200]
        row = db.get(Setting, k)
        if row: row.value = v
        else: db.add(Setting(key=k, value=v))
        changed[k] = v
    log(db, user, "SETTINGS_CHANGED", "settings", "", None, changes=changed); db.commit()
    return get_settings(db)

# ---------- cases ----------
CASE_F = {
    "title": F(req=True, max=300), "description": F(max=6000),
    "case_type": F(enum=["General", "Corporate impersonation", "Threat actor alias research", "Security incident", "Digital due diligence", "Academic", "Online identity"]),
    "priority": F(enum=["Low", "Medium", "High", "Critical"]),
    "status": F(enum=["Draft", "Active", "Under Review", "Suspended", "Closed", "Archived"]),
    "objectives": F(max=6000), "scope": F(max=6000), "authorization_notes": F(max=6000),
    "start_date": F("date"), "target_date": F("date"), "investigator_id": F("ref"),
    "stage": F(enum=["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"]),
    "tags": F("list"),
    "tlp": F(enum=["CLEAR", "GREEN", "AMBER", "AMBER+STRICT", "RED"]),
}

def case_dict(db, c: Case) -> dict:
    d = to_dict(c)
    d["tags"] = [t.name for t in db.query(Tag).join(CaseTag, CaseTag.tag_id == Tag.id).filter(CaseTag.case_id == c.id)]
    inv = db.get(User, c.investigator_id) if c.investigator_id else None
    d["investigator"] = inv.display_name if inv else ""
    return d

def set_tags(db, c: Case, names: list[str]):
    db.query(CaseTag).filter_by(case_id=c.id).delete()
    for n in {x.strip().lower() for x in names if x.strip()}:
        t = db.query(Tag).filter_by(name=n).first() or Tag(name=n)
        db.add(t); db.flush(); db.add(CaseTag(case_id=c.id, tag_id=t.id))

@r.get("/cases")
def list_cases(q: str | None = None, status: str | None = None, priority: str | None = None,
               page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    qs = db.query(Case).filter(Case.id.in_(visible_case_ids(db, user)))
    if q: qs = qs.filter(or_(Case.title.like(f"%{q}%"), Case.ref.like(f"%{q}%"), Case.description.like(f"%{q}%")))
    if status: qs = qs.filter(Case.status == status)
    if priority: qs = qs.filter(Case.priority == priority)
    total = qs.count()
    rows = qs.order_by(Case.updated_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "page": page, "size": size, "items": [case_dict(db, c) for c in rows]}

@r.post("/cases", status_code=201)
def create_case(body: dict, db: Session = Depends(get_db), user: User = Depends(writer)):
    tags = body.pop("tags", [])
    template = body.pop("template", None)
    data = clean(CASE_F, {**body, "tags": tags}, partial=False)
    tags = json.loads(data.pop("tags", "[]"))
    if not (data.get("authorization_notes") or "").strip():
        raise HTTPException(422, {"errors": {"authorization_notes": "Record the legal basis / authorization for this investigation."}})
    c = Case(ref=next_ref(db, "CASE", 4, year=True), investigator_id=data.pop("investigator_id", None) or user.id, **data)
    db.add(c); db.flush(); set_tags(db, c, tags)
    log(db, user, "CASE_CREATED", "case", c.ref, c.id)
    from .extras import TEMPLATES
    for t in TEMPLATES.get(template or data.get("case_type"), []):
        db.add(Task(case_id=c.id, ref=next_ref(db, "TASK", 4), title=t[1], stage=t[0], priority="Medium", created_by=user.id))
    db.commit()
    return case_dict(db, c)

@r.get("/cases/{cid}")
def get_case(cid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = case_access(db, user, cid)
    d = case_dict(db, c)
    from ..crud import ENTITIES
    d["counts"] = {n: db.query(cfg["model"]).filter_by(case_id=cid).count() for n, cfg in ENTITIES.items()}
    d["counts"]["evidence"] = db.query(Evidence).filter_by(case_id=cid).filter(Evidence.deleted_at.is_(None)).count()
    d["members"] = [{"user_id": m.user_id, "access": m.access} for m in db.query(CaseMember).filter_by(case_id=cid)]
    return d

@r.patch("/cases/{cid}")
def patch_case(cid: str, body: dict, db: Session = Depends(get_db), user: User = Depends(writer)):
    c = case_access(db, user, cid, write=True)
    data = clean(CASE_F, body, partial=True)
    tags = json.loads(data.pop("tags")) if "tags" in data else None
    changes = {k: [getattr(c, k), v] for k, v in data.items() if getattr(c, k) != v}
    for k, v in data.items(): setattr(c, k, v)
    if tags is not None: set_tags(db, c, tags); changes["tags"] = tags
    c.updated_at = now()
    log(db, user, "CASE_MODIFIED", "case", c.ref, c.id, changes=changes); db.commit()
    return case_dict(db, c)

@r.put("/cases/{cid}/members")
def members(cid: str, body: dict, db: Session = Depends(get_db), user: User = Depends(writer)):
    c = case_access(db, user, cid, write=True)
    if user.role != "admin" and c.investigator_id != user.id: raise HTTPException(403, "Only the lead investigator or an admin can change access")
    db.query(CaseMember).filter_by(case_id=cid).delete()
    for m in body.get("members", []):
        if m.get("access") not in ("read", "write") or not db.get(User, m.get("user_id")): raise HTTPException(422, "Invalid member")
        db.add(CaseMember(case_id=cid, user_id=m["user_id"], access=m["access"]))
    log(db, user, "CASE_ACCESS_CHANGED", "case", c.ref, cid, members=body.get("members", [])); db.commit()
    return {"ok": True}

@r.get("/cases/{cid}/activity")
def activity(cid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    case_access(db, user, cid)
    rows = db.query(AuditLog).filter_by(case_id=cid).order_by(AuditLog.id.desc()).limit(200).all()
    return [{"id": a.id, "ts": a.ts, "user": a.username, "action": a.action, "entity_type": a.entity_type, "entity_ref": a.entity_ref} for a in rows]

# ---------- finding links (provenance) ----------
@r.post("/findings/{fid}/links", status_code=201)
def link(fid: str, body: dict, db: Session = Depends(get_db), user: User = Depends(writer)):
    f = db.get(Finding, fid)
    if not f: raise HTTPException(404, "Finding not found")
    case_access(db, user, f.case_id, write=True)
    t = body.get("target_type")
    M = {"evidence": Evidence, "source": Source}.get(t)
    tgt = db.get(M, body.get("target_id")) if M else None
    if not tgt or tgt.case_id != f.case_id: raise HTTPException(422, "Target must be evidence or a source in the same case")
    if db.query(FindingLink).filter_by(finding_id=fid, target_type=t, target_id=tgt.id).first(): raise HTTPException(409, "Already linked")
    db.add(FindingLink(finding_id=fid, target_type=t, target_id=tgt.id))
    log(db, user, "LINKED", t, tgt.ref, f.case_id, finding=f.ref); db.commit()
    return {"ok": True}

@r.delete("/findings/{fid}/links/{t}/{tid}")
def unlink(fid: str, t: str, tid: str, db: Session = Depends(get_db), user: User = Depends(writer)):
    f = db.get(Finding, fid)
    if not f: raise HTTPException(404, "Finding not found")
    case_access(db, user, f.case_id, write=True)
    db.query(FindingLink).filter_by(finding_id=fid, target_type=t, target_id=tid).delete()
    log(db, user, "UNLINKED", t, tid, f.case_id, finding=f.ref); db.commit()
    return {"ok": True}

def provenance(db, f: Finding) -> dict:
    ev = [e for e in (db.get(Evidence, l.target_id) for l in db.query(FindingLink).filter_by(finding_id=f.id, target_type="evidence")) if e]
    sr = [s for s in (db.get(Source, l.target_id) for l in db.query(FindingLink).filter_by(finding_id=f.id, target_type="source")) if s]
    return {"evidence": ev, "sources": sr}

@r.get("/findings/{fid}/provenance")
def prov(fid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    f = db.get(Finding, fid)
    if not f: raise HTTPException(404, "Finding not found")
    case_access(db, user, f.case_id)
    p = provenance(db, f)
    return {"finding": f.ref, "claim": f.title, "kind": f.kind, "confidence": f.confidence,
            "sources": [{"id": s.id, "ref": s.ref, "url": s.url, "title": s.title, "reliability": s.reliability, "access_date": s.access_date} for s in p["sources"]],
            "evidence": [{"id": e.id, "ref": e.ref, "description": e.description, "sha256": e.sha256, "integrity": e.integrity_status} for e in p["evidence"]]}

# ---------- audit log ----------
@r.get("/audit")
def audit(case_id: str | None = None, action: str | None = None, q: str | None = None,
          page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=500),
          db: Session = Depends(get_db), user: User = Depends(current_user)):
    qs = db.query(AuditLog)
    vis = visible_case_ids(db, user)
    if case_id:
        case_access(db, user, case_id); qs = qs.filter(AuditLog.case_id == case_id)
    elif user.role != "admin":
        qs = qs.filter(or_(AuditLog.case_id.in_(vis), AuditLog.user_id == user.id))
    if action: qs = qs.filter(AuditLog.action == action)
    if q: qs = qs.filter(or_(AuditLog.entity_ref.like(f"%{q}%"), AuditLog.username.like(f"%{q}%")))
    total = qs.count()
    rows = qs.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "items": [{"id": a.id, "ts": a.ts, "user": a.username, "action": a.action, "entity_type": a.entity_type,
                                       "entity_ref": a.entity_ref, "case_id": a.case_id, "detail": json.loads(a.detail), "hash": a.hash[:12]} for a in rows]}

@r.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db), user: User = Depends(admin)):
    return verify_chain(db)

# ---------- dashboard ----------
@r.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    vis = visible_case_ids(db, user)
    def cs(M): return db.query(M).filter(M.case_id.in_(vis))
    active = db.query(Case).filter(Case.id.in_(vis), Case.status.in_(["Active", "Under Review", "Draft"])).order_by(Case.updated_at.desc()).limit(8).all()
    last = {c.id: db.query(AuditLog.ts).filter_by(case_id=c.id).order_by(AuditLog.id.desc()).first() for c in active}
    ev = cs(Evidence).filter(Evidence.deleted_at.is_(None))
    integ = {k: ev.filter(Evidence.integrity_status == k).count() for k in ("VALID", "MISMATCH", "MISSING", "UNVERIFIED")}
    # unresolved relationships: possible-only links; unverified claims: non-fact findings not yet approved
    return {
        "active_cases": [{**case_dict(db, c), "last_activity": last[c.id][0] if last[c.id] else c.updated_at} for c in active],
        "open_tasks": [to_dict(t) for t in cs(Task).filter(Task.status != "Done").order_by(Task.due_date).limit(8)],
        "recent_evidence": [to_dict(e) for e in ev.order_by(Evidence.created_at.desc()).limit(6)],
        "pending_verification": [to_dict(e) for e in ev.filter(Evidence.verification_status == "Pending").order_by(Evidence.created_at).limit(8)],
        "priority_findings": [to_dict(f) for f in cs(Finding).filter(Finding.severity.in_(["High", "Critical"]), Finding.status != "Rejected").limit(6)],
        "recent_sources": [to_dict(s) for s in cs(Source).order_by(Source.created_at.desc()).limit(6)],
        "sources_today": cs(Source).filter(Source.created_at >= now()[:10]).count(),
        "unresolved_relationships": [to_dict(x) for x in cs(Relationship).filter(Relationship.certainty != "CONFIRMED").limit(6)],
        "unverified_claims": [to_dict(f) for f in cs(Finding).filter(Finding.kind.in_(["INFERENCE", "HYPOTHESIS"]), Finding.status != "Approved").limit(6)],
        "integrity": integ,
        "ai_pending": cs(AISuggestion).filter(AISuggestion.status == "Pending").count(),
    }
