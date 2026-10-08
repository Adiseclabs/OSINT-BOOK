"""Global search across case content. Exact substring matching on every indexed text column."""
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import *  # noqa
from ..security import current_user, visible_case_ids

r = APIRouter(prefix="/api/search", tags=["search"])
GROUPS = [("case", Case, ["ref", "title", "description"], "title"), ("subject", Subject, ["ref", "display_name", "aliases", "description"], "display_name"),
          ("identifier", Identifier, ["ref", "notes"], "ref"), ("account", Account, ["ref", "username", "display_name", "bio", "profile_url"], "username"),
          ("evidence", Evidence, ["ref", "description", "original_filename", "tags", "notes"], "description"), ("source", Source, ["ref", "title", "url", "publisher", "notes"], "title"),
          ("finding", Finding, ["ref", "title", "description", "analyst_assessment"], "title"), ("timeline", TimelineEvent, ["ref", "title", "description"], "title"),
          ("note", Note, ["ref", "title", "body"], "title"), ("domain", Domain, ["ref", "name", "notes"], "name"), ("organization", Organization, ["ref", "name", "description"], "name")]
DATEF = {"case": "created_at", "timeline": "event_date"}

@r.get("")
def search(q: str = Query(..., min_length=2, max_length=200), case_id: str | None = None, date_from: str | None = None, date_to: str | None = None,
           subject_id: str | None = None, confidence: str | None = None, severity: str | None = None, evidence_type: str | None = None,
           source_type: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    vis = visible_case_ids(db, user)
    if case_id and case_id not in vis: return {"query": q, "groups": []}
    out = []
    for kind, M, cols, label in GROUPS:
        qs = db.query(M)
        if kind == "case": qs = qs.filter(Case.id.in_([case_id] if case_id else vis))
        else: qs = qs.filter(M.case_id.in_([case_id] if case_id else vis))
        if kind == "identifier": qs = qs.filter(or_(*[getattr(M, c).like(f"%{q}%") for c in cols]) | (M.value == q))  # masked values: exact match only
        else: qs = qs.filter(or_(*[getattr(M, c).like(f"%{q}%") for c in cols]))
        if subject_id and hasattr(M, "subject_id"): qs = qs.filter(M.subject_id == subject_id)
        if confidence and hasattr(M, "confidence"): qs = qs.filter(M.confidence == confidence)
        if severity and hasattr(M, "severity"): qs = qs.filter(M.severity == severity)
        if evidence_type and kind != "evidence": pass
        elif evidence_type: qs = qs.filter(M.evidence_type == evidence_type)
        if source_type:
            if kind == "source": qs = qs.filter(M.source_type == source_type)
            else: continue
        df = DATEF.get(kind, "created_at")
        if date_from: qs = qs.filter(getattr(M, df) >= date_from)
        if date_to: qs = qs.filter(getattr(M, df) <= date_to + "~")
        rows = qs.limit(15).all()
        if rows:
            out.append({"kind": kind, "items": [{"id": x.id, "ref": x.ref, "label": (getattr(x, label) if kind != "identifier" else x.ref), "case_id": x.id if kind == "case" else x.case_id} for x in rows]})
    return {"query": q, "groups": out}
