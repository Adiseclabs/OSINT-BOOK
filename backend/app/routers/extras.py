"""Case templates, readiness analytics, CSV import, About."""
import csv, io, json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import config
from ..db import get_db
from ..models import *  # noqa
from ..security import current_user, writer, case_access
from ..audit import next_ref, log
from ..crud import ENTITIES, clean, SENSITIVE_TYPES

r = APIRouter(prefix="/api", tags=["extras"])

TEMPLATES = {
 "Corporate impersonation": [("DISCOVER", "Record the legitimate organization and its official domains"), ("COLLECT", "Collect DNS, WHOIS and certificate data for the suspect domain"), ("COLLECT", "Capture suspect website metadata and headers"),
    ("PRESERVE", "Preserve screenshots and page captures with source records"), ("VERIFY", "Compare branding, text and registration data against the legitimate organization"), ("CORRELATE", "Link suspect domain, accounts and hosting entities"),
    ("ASSESS", "Rate confidence and state what is and is not established"), ("REPORT", "Generate and review the report")],
 "Threat actor alias research": [("DISCOVER", "Record the known username and where it was seen"), ("COLLECT", "Search public sources for candidate profiles"), ("PRESERVE", "Preserve each candidate profile as evidence"),
    ("VERIFY", "Compare public attributes (bio, links, language, activity times)"), ("CORRELATE", "Record relationships with confidence and reasoning"), ("ASSESS", "Separate FACT from INFERENCE and HYPOTHESIS"), ("REPORT", "Generate and review the report")],
 "Security incident": [("DISCOVER", "Record affected domains and IP addresses"), ("COLLECT", "Collect public reports and advisories as sources"), ("PRESERVE", "Preserve copies of reports and technical output"),
    ("CORRELATE", "Correlate entities across reports"), ("ANALYZE", "Build the incident timeline"), ("ASSESS", "Draft findings with severity and confidence"), ("REPORT", "Export the report")],
 "Digital due diligence": [("DISCOVER", "Identify the organization, websites and public profiles"), ("COLLECT", "Collect public company information, documents and security disclosures"), ("PRESERVE", "Preserve documents and page captures"),
    ("VERIFY", "Cross-check claims between independent sources"), ("ANALYZE", "Build entity profile and timeline"), ("ASSESS", "Confidence assessment"), ("REPORT", "Generate and review the report")],
}

@r.get("/case-templates")
def templates(user=Depends(current_user)):
    return {k: [{"stage": s, "title": t} for s, t in v] for k, v in TEMPLATES.items()}

@r.get("/cases/{cid}/analytics")
def analytics(cid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    case_access(db, user, cid)
    q = lambda M: db.query(M).filter_by(case_id=cid)
    findings, sources, evs = q(Finding).all(), q(Source).all(), q(Evidence).filter(Evidence.deleted_at.is_(None)).all()
    linked = {(l.finding_id) for l in db.query(FindingLink).join(Finding, Finding.id == FindingLink.finding_id).filter(Finding.case_id == cid)}
    by = lambda rows, k: {x: sum(1 for r_ in rows if getattr(r_, k) == x) for x in sorted({getattr(r_, k) for r_ in rows})}
    rel = {"High": "A", "Medium": "C", "Low": "E"}
    grid: dict = {}
    for s in sources:
        key = f"{rel.get(s.reliability, 'F')}{s.credibility or '6'}"; grid[key] = grid.get(key, 0) + 1
    subjects, idents, accounts = q(Subject).all(), q(Identifier).all(), q(Account).all()
    rels = q(Relationship).all(); tasks = q(Task).all()
    checks = [
      ("Authorization recorded", bool(db.get(Case, cid).authorization_notes.strip()), "Add legal/authorization notes to the case."),
      ("Every finding has a source or evidence", all(f.id in linked for f in findings) and bool(findings), f"{sum(1 for f in findings if f.id not in linked)} finding(s) are unsupported."),
      ("All evidence hashes verified VALID", bool(evs) and all(e.integrity_status == "VALID" for e in evs), f"{sum(1 for e in evs if e.integrity_status != 'VALID')} item(s) not VALID. Run Verify all."),
      ("No evidence pending review", all(e.verification_status != "Pending" for e in evs) and bool(evs), f"{sum(1 for e in evs if e.verification_status == 'Pending')} item(s) pending review."),
      ("Every source has a reliability grade", all(s.reliability != "Unknown" for s in sources) and bool(sources), f"{sum(1 for s in sources if s.reliability == 'Unknown')} source(s) ungraded."),
      ("Accounts linked to evidence", all(a.evidence_id for a in accounts), f"{sum(1 for a in accounts if not a.evidence_id)} account(s) have no evidence reference."),
      ("No unreviewed AI suggestions", not q(AISuggestion).filter_by(status="Pending").count(), "AI suggestions await analyst review."),
      ("Confirmed relationships are supported", all((x.evidence_id or x.source_id) for x in rels if x.certainty == "CONFIRMED"), "A CONFIRMED relationship lacks support."),
      ("No open tasks before reporting", all(t.status == "Done" for t in tasks) and bool(tasks), f"{sum(1 for t in tasks if t.status != 'Done')} task(s) not done.")]
    return {"findings_by_kind": by(findings, "kind"), "findings_by_confidence": by(findings, "confidence"), "findings_by_severity": by(findings, "severity"), "evidence_by_type": by(evs, "evidence_type"),
            "admiralty_grid": grid, "tasks": by(tasks, "status"), "checks": [{"name": n, "ok": ok, "hint": "" if ok else h} for n, ok, h in checks],
            "totals": {"subjects": len(subjects), "identifiers": len(idents), "accounts": len(accounts), "relationships": len(rels), "evidence": len(evs), "sources": len(sources), "findings": len(findings)}}

IMPORTABLE = {"identifiers": ["id_type", "value", "observed_date", "confidence", "notes"], "accounts": ["platform", "username", "profile_url", "display_name", "bio", "public_website", "status", "first_observed", "last_observed"],
              "sources": ["title", "url", "source_type", "publisher", "author", "publication_date", "access_date", "reliability", "credibility", "notes"], "domains": ["name", "registrar", "registered_on", "notes"]}

@r.post("/import/{kind}")
async def import_csv(kind: str, case_id: str = Form(...), acknowledge_sensitive: bool = Form(False), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(writer)):
    """Bulk-import public records from CSV. Each row goes through the same validation as manual entry; bad rows are reported, good rows saved."""
    if kind not in IMPORTABLE: raise HTTPException(404, "Unsupported import")
    case_access(db, user, case_id, write=True)
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000: raise HTTPException(413, "CSV larger than 2 MB")
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError: raise HTTPException(422, "CSV must be UTF-8")
    rd = csv.DictReader(io.StringIO(text))
    if not rd.fieldnames or not set(rd.fieldnames) & set(IMPORTABLE[kind]): raise HTTPException(422, f"Expected columns: {', '.join(IMPORTABLE[kind])}")
    cfg = ENTITIES[kind]; M = cfg["model"]; ok, errors = 0, []
    for n, row in enumerate(rd, start=2):
        if n > 502: errors.append({"row": n, "error": "Row limit (500) reached"}); break
        body = {k: v for k, v in row.items() if k in IMPORTABLE[kind] and v not in (None, "")}
        try:
            data = clean(cfg["fields"], body, partial=False)
            if kind == "identifiers" and data.get("id_type") in SENSITIVE_TYPES and not acknowledge_sensitive:
                raise ValueError("sensitive identifier - tick the acknowledgement to import")
            db.add(M(case_id=case_id, ref=next_ref(db, cfg["prefix"], cfg.get("width", 4)), created_by=user.id, **data)); ok += 1
        except Exception as e:
            msg = e.detail["errors"] if hasattr(e, "detail") and isinstance(e.detail, dict) else str(e)
            errors.append({"row": n, "error": msg})
    log(db, user, "CSV_IMPORTED", kind, file.filename or "", case_id, imported=ok, rejected=len(errors)); db.commit()
    return {"imported": ok, "rejected": len(errors), "errors": errors[:50]}

@r.get("/about")
def about(db: Session = Depends(get_db), user=Depends(current_user)):
    size = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    return {"name": "OSINT BOOK", "version": "1.1.0", "author": "Aditya Bhosale", "db_size": size, "cases": db.query(Case).count(), "evidence": db.query(Evidence).count(), "audit_records": db.query(AuditLog).count(), "data_dir": str(config.DATA_DIR)}
