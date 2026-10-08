"""Relationship graph data + optional local AI assistant (suggestions only; analyst approval required)."""
import json, re
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import config
from ..db import get_db
from ..models import *  # noqa
from ..osint import entity_extraction, timeline_builder, duplicate_detection, EMAIL_RE, _lev
from ..security import current_user, writer, case_access
from ..audit import next_ref, log
from ..crud import ENT_BY_TYPE, to_dict
from .core import get_settings

r = APIRouter(prefix="/api", tags=["analysis"])

def node_label(row) -> str:
    return getattr(row, "display_name", None) or getattr(row, "username", None) or getattr(row, "name", None) or getattr(row, "title", None) or (f"{row.ref}" if hasattr(row, "value") else row.ref)

@r.get("/graph")
def graph(case_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    case_access(db, user, case_id)
    rels = db.query(Relationship).filter_by(case_id=case_id).all()
    need = {(x.from_type, x.from_id) for x in rels} | {(x.to_type, x.to_id) for x in rels}
    need |= {("subject", s.id) for s in db.query(Subject).filter_by(case_id=case_id)}
    nodes = []
    for t, i in need:
        row = db.get(ENT_BY_TYPE[t], i) if t in ENT_BY_TYPE else None
        if row and row.case_id == case_id:
            lab = node_label(row)
            if t == "identifier" and (row.id_type in ("Email", "Phone") or row.sensitive):
                from ..crud import mask; lab = mask(row.value, row.id_type)
            elif t == "identifier": lab = row.value
            nodes.append({"id": f"{t}:{i}", "type": t, "ref": row.ref, "label": lab})
    ids = {n["id"] for n in nodes}
    edges = [{"id": x.id, "ref": x.ref, "from": f"{x.from_type}:{x.from_id}", "to": f"{x.to_type}:{x.to_id}", "type": x.rel_type, "certainty": x.certainty, "pct": x.confidence_pct, "reasoning": x.reasoning}
             for x in rels if f"{x.from_type}:{x.from_id}" in ids and f"{x.to_type}:{x.to_id}" in ids]
    return {"nodes": nodes, "edges": edges}

@r.get("/entities")
def entity_options(case_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    """All linkable entities in a case, for relationship pickers."""
    case_access(db, user, case_id); out = []
    for t, M in ENT_BY_TYPE.items():
        for row in db.query(M).filter_by(case_id=case_id):
            if t == "evidence" and row.deleted_at: continue
            lab = node_label(row)
            if t == "identifier":
                from ..crud import mask; lab = mask(row.value, row.id_type)
            out.append({"type": t, "id": row.id, "ref": row.ref, "label": lab})
    return out

# ---------------- AI assistant ----------------
LABEL = "AI GENERATED"

def _ollama(prompt: str, st: dict) -> str:
    try:
        resp = httpx.post(f"{config.OLLAMA_URL}/api/generate", json={"model": st["ai_model"], "prompt": prompt, "stream": False}, timeout=120)
        resp.raise_for_status(); return resp.json().get("response", "").strip()
    except Exception as e:
        raise HTTPException(502, f"Local model unavailable ({e.__class__.__name__}). Is Ollama running on {config.OLLAMA_URL}?")

def _add(db, user, case, kind, payload, origin="rules"):
    s = AISuggestion(case_id=case.id, ref=next_ref(db, "AI", 4), kind=kind, payload=json.dumps({**payload, "ai_generated": True, "label": LABEL}), origin=origin, created_by=user.id)
    db.add(s); return s

@r.post("/ai/analyze")
def analyze(body: dict, db: Session = Depends(get_db), user=Depends(writer)):
    case = case_access(db, user, body.get("case_id", ""), write=True)
    task, st, made = body.get("task"), get_settings(db), []
    ctx = {"db": db}
    if task == "summarize":
        srcs = db.query(Source).filter_by(case_id=case.id).all(); evs = db.query(Evidence).filter_by(case_id=case.id).filter(Evidence.deleted_at.is_(None)).all()
        facts = "\n".join([f"- {s.ref} {s.title} ({s.reliability} reliability, accessed {s.access_date})" for s in srcs] + [f"- {e.ref} {e.description}" for e in evs])
        if st["ai_provider"] == "ollama":
            txt = _ollama("You assist an OSINT analyst. Summarise ONLY the records below in neutral language. Do not accuse anyone or state identity as fact. Mark uncertainty.\n" + facts, st)
            origin = f"ollama:{st['ai_model']}"
        else:
            txt, origin = f"{len(srcs)} sources and {len(evs)} evidence items recorded.\n" + facts, "rules"
        made.append(_add(db, user, case, "summary", {"text": txt}, origin))
    elif task == "entities":
        text = "\n".join(f"{s.title} {s.url} {s.notes}" for s in db.query(Source).filter_by(case_id=case.id))
        text += "\n" + "\n".join(f"{n.title} {n.body}" for n in db.query(Note).filter_by(case_id=case.id))
        _, d = entity_extraction({"text": text or " "}, ctx)
        known = {x.value.lower() for x in db.query(Identifier).filter_by(case_id=case.id)} | {x.name.lower() for x in db.query(Domain).filter_by(case_id=case.id)}
        for dom in d["domains"]:
            if dom not in known: made.append(_add(db, user, case, "domain", {"name": dom, "reasoning": "Domain string appears in recorded sources/notes."}))
        if d["emails"]: made.append(_add(db, user, case, "summary", {"text": f"{len(d['emails'])} email address(es) appear in notes/sources. Review and record manually if relevant (sensitive data)."}))
    elif task == "duplicates":
        _, d = duplicate_detection({"case_id": case.id}, ctx)
        made.append(_add(db, user, case, "summary", {"text": f"{len(d['duplicates'])} duplicate group(s): " + "; ".join(f"{x['type']} {', '.join(x['records'])}" for x in d["duplicates"])}))
    elif task == "timeline":
        _, d = timeline_builder({"case_id": case.id}, ctx)
        have = {t.title for t in db.query(TimelineEvent).filter_by(case_id=case.id)}
        for e in d["events"]:
            if e["title"] not in have: made.append(_add(db, user, case, "timeline", {"event_date": e["event_date"], "title": e["title"], "event_type": e["event_type"], "reasoning": f"Derived from date recorded on {e['ref']}."}))
    elif task == "relationships":
        accs = db.query(Account).filter_by(case_id=case.id).all()
        have = {(x.from_id, x.to_id) for x in db.query(Relationship).filter_by(case_id=case.id)}
        for i, a in enumerate(accs):
            for b in accs[i + 1:]:
                if (a.id, b.id) in have or (b.id, a.id) in have: continue
                sim = a.username.lower() == b.username.lower() or 1 - _lev(a.username.lower(), b.username.lower()) / max(len(a.username), len(b.username)) >= .8
                if sim and a.platform != b.platform:
                    made.append(_add(db, user, case, "relationship", {"from_type": "account", "from_id": a.id, "to_type": "account", "to_id": b.id, "rel_type": "ASSOCIATED_WITH", "certainty": "POSSIBLE", "confidence_pct": 30,
                        "reasoning": f"Usernames '{a.username}' ({a.platform}) and '{b.username}' ({b.platform}) are identical/similar. Username reuse alone does not establish a common operator.", "labels": [a.ref, b.ref]}))
        for a in accs:
            if a.public_website:
                for dm in db.query(Domain).filter_by(case_id=case.id):
                    if dm.name.lower() in a.public_website.lower() and not any(x for x in have if a.id in x and dm.id in x):
                        made.append(_add(db, user, case, "relationship", {"from_type": "account", "from_id": a.id, "to_type": "domain", "to_id": dm.id, "rel_type": "LINKED_TO", "certainty": "LIKELY", "confidence_pct": 60,
                            "reasoning": f"Account {a.ref} lists a public website containing {dm.name}.", "labels": [a.ref, dm.ref]}))
    elif task == "findings":
        for s in db.query(AISuggestion).filter_by(case_id=case.id, kind="relationship", status="Pending"):
            p = json.loads(s.payload)
            made.append(_add(db, user, case, "finding", {"title": f"Possible link: {' / '.join(p.get('labels', []))}", "kind": "HYPOTHESIS", "confidence": "Low", "severity": "Informational", "description": p["reasoning"], "analyst_assessment": "Unreviewed AI-drafted hypothesis. Requires analyst verification against sources."}))
    else:
        raise HTTPException(422, "task: summarize | entities | duplicates | timeline | relationships | findings")
    log(db, user, "AI_SUGGESTIONS_GENERATED", "ai", task, case.id, count=len(made)); db.commit()
    return [_sdict(s) for s in made]

def _sdict(s): return {"id": s.id, "ref": s.ref, "kind": s.kind, "status": s.status, "origin": s.origin, "created_at": s.created_at, "payload": json.loads(s.payload)}

@r.get("/ai/suggestions")
def suggestions(case_id: str, status: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    case_access(db, user, case_id)
    q = db.query(AISuggestion).filter_by(case_id=case_id)
    if status: q = q.filter_by(status=status)
    return [_sdict(s) for s in q.order_by(AISuggestion.created_at.desc()).limit(200)]

@r.post("/ai/suggestions/{sid}/approve")
def approve(sid: str, body: dict | None = None, db: Session = Depends(get_db), user=Depends(writer)):
    """Analyst approval turns a suggestion into a record. Findings enter as Draft and stay marked ai_generated."""
    s = db.get(AISuggestion, sid)
    if not s: raise HTTPException(404, "Not found")
    case_access(db, user, s.case_id, write=True)
    if s.status != "Pending": raise HTTPException(409, f"Already {s.status}")
    p = json.loads(s.payload); cid = s.case_id; made = None
    if s.kind == "finding":
        made = Finding(case_id=cid, ref=next_ref(db, "F", 3), title=p["title"], description=p["description"], kind=p["kind"], confidence=p["confidence"], severity=p["severity"], analyst_assessment=p.get("analyst_assessment", ""), ai_generated=True, status="Draft", created_by=user.id)
    elif s.kind == "relationship":
        made = Relationship(case_id=cid, ref=next_ref(db, "REL", 4), **{k: p[k] for k in ("from_type", "from_id", "to_type", "to_id", "rel_type", "certainty", "confidence_pct", "reasoning")}, created_by=user.id)
    elif s.kind == "timeline":
        made = TimelineEvent(case_id=cid, ref=next_ref(db, "TL", 4), event_date=p["event_date"], title=p["title"], event_type=p["event_type"], description=p["reasoning"], created_by=user.id)
    elif s.kind == "domain":
        made = Domain(case_id=cid, ref=next_ref(db, "DOM", 4), name=p["name"], notes="Added from AI-suggested entity; " + p["reasoning"], created_by=user.id)
    s.status = "Approved"
    if made: db.add(made)
    log(db, user, "AI_SUGGESTION_APPROVED", "ai", s.ref, cid, created=made.ref if made else None); db.commit()
    return {"approved": s.ref, "created": made.ref if made else None}

@r.post("/ai/suggestions/{sid}/reject")
def reject(sid: str, db: Session = Depends(get_db), user=Depends(writer)):
    s = db.get(AISuggestion, sid)
    if not s: raise HTTPException(404, "Not found")
    case_access(db, user, s.case_id, write=True)
    s.status = "Rejected"; log(db, user, "AI_SUGGESTION_REJECTED", "ai", s.ref, s.case_id); db.commit()
    return {"rejected": s.ref}
