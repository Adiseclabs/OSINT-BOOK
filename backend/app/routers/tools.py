"""Tool execution model: every run is recorded; results are structured data that can be attached to a case."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import *  # noqa
from ..osint import TOOLS, ToolError
from ..security import current_user, writer, case_access, visible_case_ids
from ..audit import next_ref, log
from .core import get_settings
from .evidence import store_bytes

r = APIRouter(prefix="/api/tools", tags=["tools"])

@r.get("")
def catalog(user=Depends(current_user)):
    cats = {}
    for tid, (name, cat, desc, inputs, _, _) in TOOLS.items():
        cats.setdefault(cat, []).append({"id": tid, "name": name, "description": desc, "inputs": inputs})
    return cats

def run_dict(db, run, result=None):
    d = {c.name: getattr(run, c.name) for c in run.__table__.columns}
    d["input"] = json.loads(d.pop("input_json"))
    res = result or db.query(ToolResult).filter_by(tool_run_id=run.id).first()
    d["result"] = {"id": res.id, "ref": res.ref, "summary": res.summary, "data": json.loads(res.data_json), "saved": res.saved,
                   "attached_case_id": res.attached_case_id, "evidence_id": res.evidence_id} if res else None
    return d

@r.post("/run", status_code=201)
def run(body: dict, db: Session = Depends(get_db), user=Depends(writer)):
    t = TOOLS.get(body.get("tool"))
    if not t: raise HTTPException(404, "Unknown tool")
    name, cat, _, inputs, fn, prefix = t
    vals = {k: str(v).strip() for k, v in (body.get("input") or {}).items() if k in {i["name"] for i in inputs} and v not in (None, "")}
    for i in inputs:
        if i["required"] and not vals.get(i["name"]): raise HTTPException(422, f"{i['label']} is required")
    case_id = body.get("case_id") or None
    if case_id: case_access(db, user, case_id, write=True)
    for k, v in vals.items():   # any referenced record must belong to a case the user can access
        pass
    run_ = ToolRun(ref=next_ref(db, "RUN", 5), tool=body["tool"], input_json=json.dumps(vals), case_id=case_id, user_id=user.id, username=user.username)
    db.add(run_); db.flush()
    ctx = {"db": db, "allow_private": get_settings(db)["allow_private_targets"] == "true", "user": user}
    # scope guard for record-referencing inputs
    for i in inputs:
        v = vals.get(i["name"])
        if v and i["type"] in ("account", "evidence", "case"):
            M = {"account": Account, "evidence": Evidence, "case": Case}[i["type"]]
            row = db.get(M, v)
            if not row: raise HTTPException(422, f"{i['label']}: record not found")
            case_access(db, user, row.id if M is Case else row.case_id)
    res = None
    try:
        summary, data = fn(vals, ctx)
        run_.status = "Completed"
        res = ToolResult(ref=next_ref(db, prefix, 5), tool_run_id=run_.id, summary=summary, data_json=json.dumps(data, default=str))
        db.add(res)
    except ToolError as e:
        run_.status, run_.error = "Failed", str(e)
    except Exception as e:  # never leak internals
        run_.status, run_.error = "Failed", f"Unexpected error ({e.__class__.__name__})"
    run_.finished_at = now()
    log(db, user, "TOOL_EXECUTED", "tool_run", run_.ref, case_id, tool=body["tool"], status=run_.status)
    db.commit()
    return run_dict(db, run_, res)

@r.get("/runs")
def runs(case_id: str | None = None, page: int = 1, size: int = 50, db: Session = Depends(get_db), user=Depends(current_user)):
    qs = db.query(ToolRun)
    if case_id: case_access(db, user, case_id); qs = qs.filter(ToolRun.case_id == case_id)
    elif user.role != "admin": qs = qs.filter((ToolRun.user_id == user.id) | ToolRun.case_id.in_(visible_case_ids(db, user)))
    total = qs.count()
    rows = qs.order_by(ToolRun.started_at.desc()).offset((page - 1) * size).limit(min(size, 200)).all()
    return {"total": total, "items": [run_dict(db, x) for x in rows]}

@r.post("/results/{rid}/attach")
def attach(rid: str, body: dict, db: Session = Depends(get_db), user=Depends(writer)):
    """Attach a result to a case. Optionally preserve it as hashed evidence (JSON export of the result)."""
    res = db.get(ToolResult, rid)
    if not res: raise HTTPException(404, "Result not found")
    run_ = db.get(ToolRun, res.tool_run_id)
    if run_.user_id != user.id and user.role != "admin": raise HTTPException(403, "Not your tool run")
    case = case_access(db, user, body.get("case_id", ""), write=True)
    res.attached_case_id, res.saved = case.id, True
    if body.get("as_evidence", True):
        payload = json.dumps({"tool_run": run_.ref, "result": res.ref, "tool": run_.tool, "input": json.loads(run_.input_json), "started": run_.started_at, "finished": run_.finished_at, "summary": res.summary, "data": json.loads(res.data_json)}, indent=2, default=str).encode()
        etype = "WHOIS output" if run_.tool == "whois_lookup" else "DNS output" if run_.tool in ("dns_lookup", "mx_records", "txt_records", "reverse_dns") else "Tool output"
        ev = store_bytes(db, user, case, payload, f"{res.ref}.json", etype, f"{res.ref}: {res.summary}", body.get("source_id"), run_.finished_at, f"Generated by {run_.ref}")
        res.evidence_id = ev.id
    log(db, user, "TOOL_RESULT_ATTACHED", "tool_result", res.ref, case.id, evidence=bool(res.evidence_id)); db.commit()
    return run_dict(db, run_, res)

@r.post("/results/{rid}/save")
def save(rid: str, db: Session = Depends(get_db), user=Depends(writer)):
    res = db.get(ToolResult, rid)
    if not res: raise HTTPException(404, "Result not found")
    res.saved = True; db.commit()
    return {"ok": True}
