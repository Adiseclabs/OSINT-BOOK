"""Generic, validated, audited CRUD for case-scoped entities."""
import json, re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .db import get_db
from .models import *  # noqa
from .security import current_user, writer, case_access, visible_case_ids
from .audit import next_ref, log

CONF = ["Low", "Medium", "High"]
CONF4 = ["Low", "Medium", "High", "Confirmed"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?Z?)?$")

# field spec: name -> (kind, required, enum/maxlen)
def F(kind="str", req=False, enum=None, max=2000):
    return dict(kind=kind, req=req, enum=enum, max=max)

ENTITIES = {
    "subjects": dict(model=Subject, prefix="SUBJ", search=["display_name", "role", "description", "aliases"], fields={
        "display_name": F(req=True, max=200), "subject_type": F(enum=["Person", "Organization", "Group", "Unknown"]),
        "aliases": F("list"), "role": F(max=200), "description": F(max=5000), "confidence": F(enum=CONF4)}),
    "identifiers": dict(model=Identifier, prefix="ID", search=["value", "notes"], fields={
        "subject_id": F("ref"), "value": F(req=True, max=500),
        "id_type": F(req=True, enum=["Username", "Email", "Phone", "Website", "Domain", "Profile URL", "Organization", "IP address", "Other"]),
        "source_id": F("ref"), "observed_date": F("date"), "confidence": F(enum=CONF4), "notes": F(max=3000),
        "sensitive": F("bool")}),
    "accounts": dict(model=Account, prefix="ACC", search=["username", "platform", "display_name", "bio", "profile_url"], fields={
        "subject_id": F("ref"), "platform": F(req=True, max=100), "username": F(req=True, max=200),
        "profile_url": F(max=1000), "display_name": F(max=200), "bio": F(max=3000), "public_website": F(max=1000),
        "metadata_json": F("json"), "first_observed": F("date"), "last_observed": F("date"),
        "status": F(enum=["Active", "Inactive", "Unknown", "Deleted", "Suspended"]),
        "evidence_id": F("ref"), "confidence": F(enum=CONF4)}),
    "organizations": dict(model=Organization, prefix="ORG", search=["name", "description"], fields={
        "name": F(req=True, max=300), "org_type": F(max=100), "jurisdiction": F(max=100),
        "website": F(max=500), "description": F(max=3000)}),
    "domains": dict(model=Domain, prefix="DOM", search=["name", "registrar", "notes"], fields={
        "name": F(req=True, max=253), "registrar": F(max=200), "registered_on": F("date"),
        "subject_id": F("ref"), "source_id": F("ref"), "notes": F(max=3000)}),
    "sources": dict(model=Source, prefix="SRC", search=["title", "url", "publisher", "author", "notes"], fields={
        "source_type": F(enum=["Web page", "Social profile", "News article", "Public record", "Document", "Domain record", "Security disclosure", "Other"]),
        "url": F(max=2000), "title": F(req=True, max=500), "publisher": F(max=300), "author": F(max=300),
        "publication_date": F("date"), "access_date": F("date"), "archived_url": F(max=2000),
        "reliability": F(enum=["High", "Medium", "Low", "Unknown"]), "confidence": F(enum=CONF4),
        "notes": F(max=3000), "tags": F(max=300), "credibility": F(enum=["1", "2", "3", "4", "5", "6"])}),
    "findings": dict(model=Finding, prefix="F", width=3, search=["title", "description", "analyst_assessment"], fields={
        "title": F(req=True, max=300), "description": F(max=6000),
        "kind": F(req=True, enum=["FACT", "OBSERVATION", "INFERENCE", "HYPOTHESIS"]),
        "severity": F(enum=["Informational", "Low", "Medium", "High", "Critical"]), "confidence": F(enum=CONF4),
        "status": F(enum=["Draft", "Under Review", "Approved", "Rejected"]), "subject_id": F("ref"),
        "analyst_assessment": F(max=6000), "recommendation": F(max=4000)}),
    "timeline": dict(model=TimelineEvent, prefix="TL", search=["title", "description"], fields={
        "event_date": F("date", req=True), "title": F(req=True, max=300), "description": F(max=3000),
        "event_type": F(enum=["Discovery", "Observation", "Change", "Capture", "Registration", "Incident", "Contact", "Other"]),
        "subject_id": F("ref"), "evidence_id": F("ref"), "source_id": F("ref"), "finding_id": F("ref")}),
    "relationships": dict(model=Relationship, prefix="REL", search=["rel_type", "reasoning"], fields={
        "from_type": F(req=True, enum=["subject", "identifier", "account", "organization", "domain", "evidence", "source"]),
        "from_id": F(req=True, max=64),
        "to_type": F(req=True, enum=["subject", "identifier", "account", "organization", "domain", "evidence", "source"]),
        "to_id": F(req=True, max=64),
        "rel_type": F(req=True, enum=["USES", "OWNS", "MENTIONS", "ASSOCIATED_WITH", "WORKS_FOR", "LINKED_TO", "OBSERVED_ON", "REFERENCES"]),
        "certainty": F(enum=["CONFIRMED", "LIKELY", "POSSIBLE"]), "confidence_pct": F("int"),
        "reasoning": F(max=3000), "evidence_id": F("ref"), "source_id": F("ref")}),
    "notes": dict(model=Note, prefix="NOTE", search=["title", "body"], fields={
        "title": F(req=True, max=300), "body": F(max=20000), "subject_id": F("ref")}),
    "tasks": dict(model=Task, prefix="TASK", search=["title", "description"], fields={
        "title": F(req=True, max=300), "description": F(max=3000),
        "status": F(enum=["Open", "In Progress", "Blocked", "Done"]), "priority": F(enum=["Low", "Medium", "High", "Critical"]),
        "due_date": F("date"), "stage": F(enum=["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"]),
        "assignee_id": F("ref")}),
}
FILTERS = ("status", "kind", "severity", "confidence", "event_type", "source_type", "reliability", "priority", "stage", "id_type", "platform")
ENT_BY_TYPE = {"subject": Subject, "identifier": Identifier, "account": Account, "organization": Organization,
               "domain": Domain, "evidence": Evidence, "source": Source}

def clean(spec: dict, data: dict, partial: bool) -> dict:
    out, errs = {}, {}
    for k in data:
        if k not in spec:
            errs[k] = "unknown field"
    for k, s in spec.items():
        if k not in data:
            if s["req"] and not partial:
                errs[k] = "required"
            continue
        v, kind = data[k], s["kind"]
        if v in (None, "") and kind not in ("bool",):
            if s["req"]:
                errs[k] = "required"
            else:
                out[k] = None if kind in ("date", "ref", "int") else ("[]" if kind == "list" else ("{}" if kind == "json" else ""))
            continue
        try:
            if kind == "str":
                v = str(v).strip()
                if len(v) > s["max"]: raise ValueError(f"max {s['max']} characters")
                if s["enum"] and v not in s["enum"]: raise ValueError("must be one of " + ", ".join(s["enum"]))
            elif kind == "date":
                v = str(v).strip()
                if not DATE.match(v): raise ValueError("use YYYY-MM-DD or YYYY-MM-DDTHH:MM")
                datetime.fromisoformat(v.replace("Z", "")[:19].replace(" ", "T"))
            elif kind == "bool": v = bool(v)
            elif kind == "int":
                v = int(v)
                if not 0 <= v <= 100: raise ValueError("0-100")
            elif kind == "ref": v = str(v)[:64]
            elif kind == "list":
                if isinstance(v, str): v = [x.strip() for x in v.split(",") if x.strip()]
                if not isinstance(v, list) or len(v) > 50: raise ValueError("list of up to 50 items")
                v = json.dumps([str(x)[:200] for x in v])
            elif kind == "json":
                v = json.dumps(v if isinstance(v, dict) else json.loads(v))[:20000]
        except (ValueError, TypeError) as e:
            errs[k] = str(e)
            continue
        out[k] = v
    if errs:
        raise HTTPException(422, {"errors": errs})
    return out

SENSITIVE_TYPES = {"Email", "Phone"}

def mask(value: str, id_type: str) -> str:
    if id_type == "Email" and "@" in value:
        u, d = value.split("@", 1)
        return u[:2] + "*" * max(2, len(u) - 2) + "@" + d
    if id_type == "Phone":
        return "*" * max(0, len(value) - 3) + value[-3:]
    return value

def to_dict(row, reveal=False) -> dict:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for k in ("aliases",):
        if k in d: d[k] = json.loads(d[k] or "[]")
    if "metadata_json" in d: d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
    if isinstance(row, Identifier):
        d["masked"] = not reveal and (row.id_type in SENSITIVE_TYPES or row.sensitive)
        if d["masked"]: d["value"] = mask(row.value, row.id_type)
    return d

def _fk_ok(db, case_id, data):
    """Referenced records must belong to the same case."""
    lookup = {"subject_id": Subject, "source_id": Source, "evidence_id": Evidence, "finding_id": Finding}
    for k, m in lookup.items():
        if data.get(k):
            r = db.get(m, data[k])
            if not r or r.case_id != case_id:
                raise HTTPException(422, {"errors": {k: "not found in this case"}})

def make_router(name: str, cfg: dict) -> APIRouter:
    r = APIRouter(prefix=f"/api/{name}", tags=[name])
    M, spec = cfg["model"], cfg["fields"]

    @r.get("")
    def list_(request: Request, case_id: str | None = None, q: str | None = None, subject_id: str | None = None,
              page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
              db: Session = Depends(get_db), user=Depends(current_user)):
        qs = db.query(M)
        if case_id:
            case_access(db, user, case_id); qs = qs.filter(M.case_id == case_id)
        else:
            qs = qs.filter(M.case_id.in_(visible_case_ids(db, user)))
        if subject_id and hasattr(M, "subject_id"): qs = qs.filter(M.subject_id == subject_id)
        for k in FILTERS:
            v = request.query_params.get(k)
            if v and hasattr(M, k):
                qs = qs.filter(getattr(M, k) == v)
        if q:
            qs = qs.filter(or_(*[getattr(M, c).like(f"%{q}%") for c in cfg["search"]]))
        total = qs.count()
        order = M.event_date if name == "timeline" else M.created_at.desc()
        rows = qs.order_by(order).offset((page - 1) * size).limit(size).all()
        return {"total": total, "page": page, "size": size, "items": [to_dict(x) for x in rows]}

    @r.post("", status_code=201)
    def create(body: dict, case_id: str, db: Session = Depends(get_db), user=Depends(writer)):
        case_access(db, user, case_id, write=True)
        ack = bool(body.pop("sensitive_ack", False))
        data = clean(spec, body, partial=False)
        _fk_ok(db, case_id, data)
        if M is Identifier and (data.get("id_type") in SENSITIVE_TYPES or data.get("sensitive")) and not ack:
            raise HTTPException(422, {"errors": {"sensitive_ack": "Acknowledge the sensitive-data warning before saving."}})
        if M is Relationship:
            data.setdefault("certainty", "POSSIBLE")
            if data["certainty"] == "CONFIRMED" and not (data.get("evidence_id") or data.get("source_id")):
                raise HTTPException(422, {"errors": {"certainty": "A confirmed relationship needs linked evidence or a source."}})
        row = M(case_id=case_id, ref=next_ref(db, cfg["prefix"], cfg.get("width", 4)), created_by=user.id, **data)
        db.add(row); db.flush()
        log(db, user, "CREATED", name, row.ref, case_id, **({"sensitive_ack": True} if ack else {}))
        db.commit()
        return to_dict(row)

    @r.get("/{rid}")
    def get(rid: str, reveal: bool = False, db: Session = Depends(get_db), user=Depends(current_user)):
        row = db.get(M, rid)
        if not row: raise HTTPException(404, "Not found")
        case_access(db, user, row.case_id)
        if reveal and isinstance(row, Identifier):
            log(db, user, "REVEALED", name, row.ref, row.case_id); db.commit()
        out = to_dict(row, reveal)
        if M is Finding:
            out["links"] = [{"type": l.target_type, "id": l.target_id} for l in db.query(FindingLink).filter_by(finding_id=row.id)]
        return out

    @r.patch("/{rid}")
    def update(rid: str, body: dict, db: Session = Depends(get_db), user=Depends(writer)):
        row = db.get(M, rid)
        if not row: raise HTTPException(404, "Not found")
        case_access(db, user, row.case_id, write=True)
        data = clean(spec, body, partial=True)
        _fk_ok(db, row.case_id, data)
        changes = {k: [getattr(row, k), v] for k, v in data.items() if getattr(row, k) != v}
        if M is Identifier: changes = {k: ["(masked)", "(masked)"] if k == "value" else v for k, v in changes.items()}
        for k, v in data.items(): setattr(row, k, v)
        log(db, user, "MODIFIED", name, row.ref, row.case_id, changes=changes)
        db.commit()
        return to_dict(row)

    @r.delete("/{rid}")
    def delete(rid: str, db: Session = Depends(get_db), user=Depends(writer)):
        row = db.get(M, rid)
        if not row: raise HTTPException(404, "Not found")
        case_access(db, user, row.case_id, write=True)
        ref, cid = row.ref, row.case_id
        db.delete(row); log(db, user, "DELETED", name, ref, cid); db.commit()
        return {"deleted": ref}
    return r

routers = [make_router(n, c) for n, c in ENTITIES.items()]
