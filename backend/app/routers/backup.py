"""Backup / restore with an SHA-256 integrity manifest."""
import hashlib, io, json, shutil, sqlite3, tempfile, zipfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .. import config
from ..db import get_db, engine, Base
from ..models import *  # noqa
from ..security import admin, writer, case_access, current_user
from ..audit import log
from .core import get_settings

r = APIRouter(prefix="/api/backup", tags=["backup"])
T = Base.metadata.tables

def _sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def _fsha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

def _zip_dir(z: zipfile.ZipFile, root: Path, arc_prefix: str, manifest: dict, evmap: dict):
    for p in sorted(root.rglob("*")):
        if p.is_file():
            arc = f"{arc_prefix}/{p.relative_to(root).as_posix()}"
            z.write(p, arc); manifest[arc] = _fsha(p)

def _finish(z, manifest, kind, extra=None):
    m = {"app": "OSINT BOOK", "kind": kind, "created_at": now(), "files": manifest, **(extra or {})}
    z.writestr("manifest.json", json.dumps(m, indent=2))

@r.post("/database")
def backup_db(db: Session = Depends(get_db), user=Depends(admin)):
    """Full backup: consistent SQLite snapshot + all case files + configuration + integrity manifest."""
    name = f"full_{now().replace(':', '').replace('-', '')}.zip"; dest = config.EXPORTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "osintbook.db"
        src = sqlite3.connect(config.DB_PATH); dst = sqlite3.connect(snap); src.backup(dst); dst.close(); src.close()
        man = {}
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "osintbook.db"); man["osintbook.db"] = _fsha(snap)
            if config.CASES_DIR.exists(): _zip_dir(z, config.CASES_DIR, "cases", man, {})
            cfg = json.dumps(get_settings(db), indent=2).encode(); z.writestr("config.json", cfg); man["config.json"] = _sha(cfg)
            ev = {e.ref: e.sha256 for e in db.query(Evidence).filter(Evidence.deleted_at.is_(None))}
            _finish(z, man, "full", {"evidence_sha256": ev})
    log(db, user, "BACKUP_CREATED", "backup", name, None, kind="full"); db.commit()
    return {"name": name, "size": dest.stat().st_size, "sha256": _fsha(dest)}

@r.post("/case/{cid}")
def backup_case(cid: str, db: Session = Depends(get_db), user=Depends(writer)):
    case = case_access(db, user, cid)
    name = f"case_{case.ref}_{now().replace(':', '').replace('-', '')}.zip"; dest = config.EXPORTS_DIR / name
    dump = {}
    def rows(t, cond): return [dict(x._mapping) for x in db.execute(select(T[t]).where(cond))]
    for tname, t in T.items():
        if tname == "cases": dump[tname] = rows(tname, t.c.id == cid)
        elif "case_id" in t.c and tname not in ("case_members",): dump[tname] = rows(tname, t.c.case_id == cid)
    ev_ids = [e["id"] for e in dump["evidence"]]; f_ids = [f["id"] for f in dump["findings"]]; run_ids = [x["id"] for x in dump["tool_runs"]]
    dump["evidence_hashes"] = rows("evidence_hashes", T["evidence_hashes"].c.evidence_id.in_(ev_ids))
    dump["finding_links"] = rows("finding_links", T["finding_links"].c.finding_id.in_(f_ids))
    dump["tool_results"] = rows("tool_results", T["tool_results"].c.tool_run_id.in_(run_ids))
    dump["subject_tags"] = rows("subject_tags", T["subject_tags"].c.subject_id.in_([s["id"] for s in dump["subjects"]]))
    tag_ids = {x["tag_id"] for x in dump["case_tags"]} | {x["tag_id"] for x in dump["subject_tags"]}
    dump["tags"] = rows("tags", T["tags"].c.id.in_(tag_ids))
    blob = json.dumps(dump, default=str).encode(); man = {"case.json": _sha(blob)}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("case.json", blob)
        root = config.CASES_DIR / case.ref
        if root.exists(): _zip_dir(z, root, f"cases/{case.ref}", man, {})
        _finish(z, man, "case", {"case_ref": case.ref, "evidence_sha256": {e["ref"]: e["sha256"] for e in dump["evidence"] if not e["deleted_at"]}})
    log(db, user, "BACKUP_CREATED", "backup", name, cid, kind="case"); db.commit()
    return {"name": name, "size": dest.stat().st_size, "sha256": _fsha(dest)}

@r.get("")
def list_backups(user=Depends(admin)):
    return [{"name": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime} for p in sorted(config.EXPORTS_DIR.glob("*.zip"), reverse=True)]

@r.get("/{name}/download")
def download(name: str, db: Session = Depends(get_db), user=Depends(current_user)):
    p = (config.EXPORTS_DIR / Path(name).name)
    if not p.exists(): raise HTTPException(404, "Not found")
    if name.startswith("full_") and user.role != "admin": raise HTTPException(403, "Administrator only")
    log(db, user, "BACKUP_DOWNLOADED", "backup", p.name, None); db.commit()
    return FileResponse(p, filename=p.name, media_type="application/zip")

def _open_verified(data: bytes, td: Path) -> dict:
    try: z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile: raise HTTPException(422, "Not a valid backup archive")
    if "manifest.json" not in z.namelist(): raise HTTPException(422, "Backup has no integrity manifest")
    man = json.loads(z.read("manifest.json"))
    total = 0
    for i in z.infolist():
        n = i.filename
        if n.startswith("/") or ".." in Path(n).parts or "\\" in n: raise HTTPException(422, f"Unsafe path in archive: {n}")
        total += i.file_size
        if total > 5 * 1024 ** 3: raise HTTPException(422, "Archive too large")
    bad = []
    for n, h in man["files"].items():
        try: ok = _sha(z.read(n)) == h
        except KeyError: ok = False
        if not ok: bad.append(n)
    if bad: raise HTTPException(422, {"error": "Integrity check failed - archive was modified or is corrupt", "files": bad[:20]})
    z.extractall(td); return man

@r.post("/verify")
async def verify_archive(file: UploadFile = File(...), user=Depends(current_user)):
    with tempfile.TemporaryDirectory() as td:
        man = _open_verified(await file.read(), Path(td))
    return {"valid": True, "kind": man["kind"], "created_at": man["created_at"], "files": len(man["files"])}

@r.post("/restore")
async def restore(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(admin)):
    """Restore a backup. Full: replaces the database and case files (a safety copy is made first). Case: adds the case if absent."""
    data = await file.read()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); man = _open_verified(data, td)
        if man["kind"] == "full":
            safety = config.EXPORTS_DIR / f"pre-restore_{now().replace(':', '').replace('-', '')}.db"
            c = sqlite3.connect(config.DB_PATH); d = sqlite3.connect(safety); c.backup(d); d.close(); c.close()
            db.close(); engine.dispose()
            for ext in ("-wal", "-shm"): Path(str(config.DB_PATH) + ext).unlink(missing_ok=True)
            shutil.copy2(td / "osintbook.db", config.DB_PATH)
            if (td / "cases").exists():
                shutil.rmtree(config.CASES_DIR, ignore_errors=True); shutil.copytree(td / "cases", config.CASES_DIR)
            # verify evidence hashes post-restore
            return {"restored": "full", "safety_copy": safety.name, "note": "Sign in again. Run Verify All on each case to re-check evidence hashes."}
        dump = json.loads((td / "case.json").read_text())
        ref = man["case_ref"]
        if db.query(Case).filter_by(ref=ref).first() or db.get(Case, dump["cases"][0]["id"]): raise HTTPException(409, f"{ref} already exists; restore skipped")
        for tname in [t.name for t in Base.metadata.sorted_tables]:
            rows = dump.get(tname)
            if not rows: continue
            if tname == "cases":
                for x in rows:
                    if not db.get(User, x["investigator_id"]): x["investigator_id"] = user.id
            if tname == "tasks":
                for x in rows:
                    if x["assignee_id"] and not db.get(User, x["assignee_id"]): x["assignee_id"] = None
            if tname == "tool_runs":
                for x in rows: x["user_id"] = x["user_id"] if db.get(User, x["user_id"] or "") else user.id
            db.execute(T[tname].insert().prefix_with("OR IGNORE"), rows)
        if (td / "cases" / ref).exists(): shutil.copytree(td / "cases" / ref, config.CASES_DIR / ref, dirs_exist_ok=True)
        log(db, user, "BACKUP_RESTORED", "case", ref, dump["cases"][0]["id"], kind="case"); db.commit()
        return {"restored": "case", "case_ref": ref}
