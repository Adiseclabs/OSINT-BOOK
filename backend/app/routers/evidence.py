"""Evidence: safe upload, hashing, preview, download, verification, chain of custody."""
import hashlib, json, os, re, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .. import config
from ..db import get_db
from ..models import *  # noqa
from ..security import current_user, writer, case_access, visible_case_ids
from ..audit import next_ref, log
from ..crud import to_dict, clean, F

r = APIRouter(prefix="/api/evidence", tags=["evidence"])
TYPES = ["Screenshot", "PDF", "Image", "Text file", "HTML export", "Document", "WHOIS output", "DNS output", "Webpage capture", "Analyst note", "Tool output"]
PATCHABLE = {"description": F(max=3000), "notes": F(max=3000), "tags": F(max=300), "source_id": F("ref"),
             "evidence_type": F(enum=TYPES), "verification_status": F(enum=["Pending", "Verified", "Disputed"])}

def safe_name(n: str) -> str:
    n = os.path.basename(n.replace("\\", "/"))
    return re.sub(r"[^A-Za-z0-9._-]", "_", n)[:120] or "file"

def folder_for(etype: str) -> str:
    return "screenshots" if etype in ("Screenshot", "Image", "Webpage capture") else "documents" if etype in ("PDF", "Document") else "evidence"

def abs_path(rel: str) -> Path:
    p = (config.DATA_DIR / rel).resolve()
    if config.DATA_DIR not in p.parents:  # path traversal guard
        raise HTTPException(400, "Invalid storage path")
    return p

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def store_bytes(db, user, case: Case, data: bytes, filename: str, etype: str, description: str = "", source_id=None,
                collected_at=None, notes: str = "") -> Evidence:
    ref = next_ref(db, "EV", 4)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    folder = config.CASES_DIR / case.ref / folder_for(etype)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{ref}_{uuid.uuid4().hex[:8]}.{ext}"
    dest.write_bytes(data)
    os.chmod(dest, 0o640)  # never executable
    sha = hashlib.sha256(data).hexdigest()
    ev = Evidence(case_id=case.id, ref=ref, evidence_type=etype, description=description, original_filename=safe_name(filename),
                  storage_path=str(dest.relative_to(config.DATA_DIR)), mime=config.ALLOWED_EXT.get(ext, "other"), size=len(data),
                  sha256=sha, collected_at=collected_at or now(), source_id=source_id, collector=user.display_name,
                  integrity_status="VALID", last_verified=now(), notes=notes, created_by=user.id)
    db.add(ev); db.flush()
    db.add(EvidenceHash(evidence_id=ev.id, sha256=sha, kind="initial", result="VALID", by_user=user.username))
    log(db, user, "EVIDENCE_UPLOADED", "evidence", ref, case.id, sha256=sha, size=len(data), filename=ev.original_filename)
    return ev

@r.post("", status_code=201)
async def upload(case_id: str = Form(...), evidence_type: str = Form("Document"), description: str = Form(""),
                 source_id: str = Form(""), collected_at: str = Form(""), notes: str = Form(""),
                 file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(writer)):
    case = case_access(db, user, case_id, write=True)
    if evidence_type not in TYPES: raise HTTPException(422, "Unknown evidence type")
    name = safe_name(file.filename or "file")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in config.ALLOWED_EXT: raise HTTPException(415, f"File type .{ext} is not allowed")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES: raise HTTPException(413, f"File exceeds {config.MAX_UPLOAD_BYTES // 1048576} MB limit")
    if not data: raise HTTPException(422, "Empty file")
    magic = config.MAGIC.get(ext)
    if magic and not data.startswith(magic): raise HTTPException(415, "File content does not match its extension")
    if source_id:
        s = db.get(Source, source_id)
        if not s or s.case_id != case_id: raise HTTPException(422, "Source not found in this case")
    ev = store_bytes(db, user, case, data, name, evidence_type, description, source_id or None, collected_at or None, notes)
    db.commit()
    return to_dict(ev)

@r.get("")
def list_(case_id: str | None = None, q: str | None = None, evidence_type: str | None = None,
          integrity: str | None = None, verification: str | None = None, page: int = 1, size: int = 50,
          db: Session = Depends(get_db), user=Depends(current_user)):
    qs = db.query(Evidence)
    if case_id: case_access(db, user, case_id); qs = qs.filter(Evidence.case_id == case_id)
    else: qs = qs.filter(Evidence.case_id.in_(visible_case_ids(db, user)))
    if q: qs = qs.filter(or_(Evidence.ref.like(f"%{q}%"), Evidence.description.like(f"%{q}%"), Evidence.original_filename.like(f"%{q}%"), Evidence.sha256.like(f"{q}%"), Evidence.tags.like(f"%{q}%")))
    if evidence_type: qs = qs.filter(Evidence.evidence_type == evidence_type)
    if integrity: qs = qs.filter(Evidence.integrity_status == integrity)
    if verification: qs = qs.filter(Evidence.verification_status == verification)
    total = qs.count()
    rows = qs.order_by(Evidence.created_at.desc()).offset((page - 1) * size).limit(min(size, 200)).all()
    return {"total": total, "page": page, "size": size, "items": [to_dict(e) for e in rows]}

def _ev(db, user, eid, write=False) -> Evidence:
    ev = db.get(Evidence, eid)
    if not ev: raise HTTPException(404, "Evidence not found")
    case_access(db, user, ev.case_id, write=write)
    return ev

@r.get("/{eid}")
def get(eid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    ev = _ev(db, user, eid)
    log(db, user, "VIEWED", "evidence", ev.ref, ev.case_id); db.commit()
    d = to_dict(ev)
    d["hash_history"] = [{"sha256": h.sha256, "kind": h.kind, "result": h.result, "at": h.computed_at, "by": h.by_user}
                         for h in db.query(EvidenceHash).filter_by(evidence_id=ev.id).order_by(EvidenceHash.computed_at.desc())]
    d["linked_findings"] = [{"id": f.id, "ref": f.ref, "title": f.title} for f in
                            (db.get(Finding, l.finding_id) for l in db.query(FindingLink).filter_by(target_type="evidence", target_id=ev.id)) if f]
    return d

@r.patch("/{eid}")
def patch(eid: str, body: dict, db: Session = Depends(get_db), user=Depends(writer)):
    """Only descriptive metadata can change; file, hash and collection data are immutable. Every edit is logged."""
    ev = _ev(db, user, eid, True)
    data = clean(PATCHABLE, body, partial=True)
    changes = {k: [getattr(ev, k), v] for k, v in data.items() if getattr(ev, k) != v}
    for k, v in data.items(): setattr(ev, k, v)
    log(db, user, "EVIDENCE_METADATA_MODIFIED", "evidence", ev.ref, ev.case_id, changes=changes); db.commit()
    return to_dict(ev)

@r.post("/{eid}/verify")
def verify(eid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    ev = _ev(db, user, eid)
    if ev.deleted_at: raise HTTPException(409, "Evidence was deleted")
    p = abs_path(ev.storage_path)
    if not p.exists(): res, calc = "MISSING", ""
    else:
        calc = sha256_file(p); res = "VALID" if calc == ev.sha256 else "MISMATCH"
    ev.integrity_status, ev.last_verified = res, now()
    db.add(EvidenceHash(evidence_id=ev.id, sha256=calc, kind="verify", result=res, by_user=user.username))
    log(db, user, "EVIDENCE_HASH_VERIFIED", "evidence", ev.ref, ev.case_id, result=res); db.commit()
    return {"ref": ev.ref, "result": res, "expected": ev.sha256, "computed": calc}

@r.post("/verify-all")
def verify_all(case_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    case_access(db, user, case_id)
    out = []
    for ev in db.query(Evidence).filter_by(case_id=case_id).filter(Evidence.deleted_at.is_(None)):
        p = abs_path(ev.storage_path)
        calc = sha256_file(p) if p.exists() else ""
        res = "MISSING" if not calc else ("VALID" if calc == ev.sha256 else "MISMATCH")
        ev.integrity_status, ev.last_verified = res, now()
        db.add(EvidenceHash(evidence_id=ev.id, sha256=calc, kind="verify", result=res, by_user=user.username))
        out.append({"ref": ev.ref, "result": res})
    log(db, user, "EVIDENCE_HASH_VERIFIED_BULK", "case", case_id, case_id, count=len(out)); db.commit()
    return out

HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'", "Cache-Control": "no-store"}

@r.get("/{eid}/preview")
def preview(eid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    """Images/PDF are served inertly; every text-like format (incl. HTML) is returned as escaped plain text, never rendered."""
    ev = _ev(db, user, eid)
    p = abs_path(ev.storage_path)
    if ev.deleted_at or not p.exists(): raise HTTPException(404, "File not available")
    ext = p.suffix.lower().lstrip(".")
    kind = config.ALLOWED_EXT.get(ext)
    log(db, user, "PREVIEWED", "evidence", ev.ref, ev.case_id); db.commit()
    if kind == "text":
        return JSONResponse({"kind": "text", "text": p.read_bytes()[:200_000].decode("utf-8", "replace"), "truncated": p.stat().st_size > 200_000}, headers=HEADERS)
    if kind in ("image", "pdf"):
        mt = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf"}[ext]
        return FileResponse(p, media_type=mt, headers={**HEADERS, "Content-Disposition": "inline"})
    return JSONResponse({"kind": "none", "text": "No inline preview for this file type. Download it to inspect."}, headers=HEADERS)

@r.get("/{eid}/download")
def download(eid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    ev = _ev(db, user, eid)
    p = abs_path(ev.storage_path)
    if ev.deleted_at or not p.exists(): raise HTTPException(404, "File not available")
    log(db, user, "EVIDENCE_EXPORTED", "evidence", ev.ref, ev.case_id, sha256=ev.sha256); db.commit()
    return FileResponse(p, media_type="application/octet-stream", filename=ev.original_filename, headers=HEADERS)

@r.get("/{eid}/custody")
def custody(eid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    ev = _ev(db, user, eid)
    rows = db.query(AuditLog).filter(AuditLog.entity_ref == ev.ref).order_by(AuditLog.id).all()
    linked = db.query(AuditLog).filter(AuditLog.detail.like(f'%"{ev.ref}"%')).all()
    merged = sorted({a.id: a for a in rows + linked}.values(), key=lambda x: x.id)
    return [{"ts": a.ts, "user": a.username, "action": a.action, "detail": json.loads(a.detail)} for a in merged]

@r.delete("/{eid}")
def delete(eid: str, db: Session = Depends(get_db), user=Depends(writer)):
    """Secure deletion: file is overwritten then removed. The metadata record is kept as a tombstone for custody."""
    ev = _ev(db, user, eid, True)
    if ev.deleted_at: raise HTTPException(409, "Already deleted")
    p = abs_path(ev.storage_path)
    if p.exists():
        with open(p, "r+b") as f:
            f.write(b"\x00" * p.stat().st_size); f.flush(); os.fsync(f.fileno())
        p.unlink()
    ev.deleted_at, ev.integrity_status = now(), "DELETED"
    log(db, user, "EVIDENCE_DELETED", "evidence", ev.ref, ev.case_id, sha256=ev.sha256); db.commit()
    return {"deleted": ev.ref}
