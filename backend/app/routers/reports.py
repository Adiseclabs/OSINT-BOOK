"""Report generation: HTML, JSON, PDF. Findings always carry their epistemic type; inferences are never worded as confirmed."""
import hashlib, json, io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from jinja2 import Environment, select_autoescape
from sqlalchemy.orm import Session
from .. import config
from ..db import get_db
from ..models import *  # noqa
from ..security import current_user, writer, case_access
from ..audit import next_ref, log
from ..crud import to_dict, ENT_BY_TYPE
from .core import provenance, case_dict, get_settings

r = APIRouter(prefix="/api/reports", tags=["reports"])
KIND_NOTE = {"FACT": "Directly observed and supported by linked evidence.", "OBSERVATION": "Observed by the analyst; not independently corroborated.",
             "INFERENCE": "Analyst inference - NOT confirmed.", "HYPOTHESIS": "Working hypothesis - NOT confirmed; requires further collection."}

def label_of(db, t, i):
    M = ENT_BY_TYPE.get(t); row = db.get(M, i) if M else None
    if not row: return i[:8]
    return getattr(row, "display_name", None) or getattr(row, "username", None) or getattr(row, "name", None) or getattr(row, "title", None) or getattr(row, "value", None) and "(identifier " + row.ref + ")" or row.ref

def admiralty(s): return {'High': 'A', 'Medium': 'C', 'Low': 'E'}.get(s.reliability, 'F') + (s.credibility or '6')

def build(db, case: Case, user, opts: dict) -> dict:
    cid = case.id; st = get_settings(db)
    def rows(M, order=None): 
        q = db.query(M).filter_by(case_id=cid); return q.order_by(order).all() if order is not None else q.all()
    subjects, findings = rows(Subject), [f for f in rows(Finding) if f.status != "Rejected" or opts.get("include_rejected")]
    evs = [e for e in rows(Evidence) if not e.deleted_at]
    fd = []
    for f in findings:
        p = provenance(db, f); d = to_dict(f)
        d["kind_note"] = KIND_NOTE.get(f.kind, ""); d["subject"] = db.get(Subject, f.subject_id).display_name if f.subject_id else ""
        d["sources"] = [{"ref": s.ref, "title": s.title, "url": s.url, "reliability": s.reliability, "admiralty": admiralty(s), "access_date": s.access_date} for s in p["sources"]]
        d["evidence"] = [{"ref": e.ref, "description": e.description, "sha256": e.sha256, "integrity": e.integrity_status} for e in p["evidence"]]
        d["unsupported"] = not (d["sources"] or d["evidence"])
        fd.append(d)
    rels = [{**to_dict(x), "from_label": label_of(db, x.from_type, x.from_id), "to_label": label_of(db, x.to_type, x.to_id)} for x in rows(Relationship)]
    ev_counts = {}
    for f in fd: ev_counts[f["confidence"]] = ev_counts.get(f["confidence"], 0) + 1
    limits = ["Findings are limited to publicly available information recorded in this case.", "Sources were accessed on the dates shown; content may have changed since.",
              "INFERENCE and HYPOTHESIS items are analytical judgements and are not confirmed facts."]
    if any(e.integrity_status != "VALID" for e in evs): limits.append("One or more evidence items failed or have not passed hash verification (see Evidence).")
    if any(x["unsupported"] for x in fd): limits.append("Some findings have no linked source or evidence and are marked UNSUPPORTED.")
    return {"classification": st["report_classification"], "organization": st["org_name"], "generated_at": now(), "generated_by": user.display_name,
            "case": case_dict(db, case), "subjects": [to_dict(s) for s in subjects], "findings": fd, "evidence": [to_dict(e) for e in evs],
            "sources": [{**to_dict(s), "admiralty": admiralty(s)} for s in rows(Source)], "timeline": [to_dict(t) for t in rows(TimelineEvent, TimelineEvent.event_date)],
            "relationships": rels, "confidence_summary": ev_counts, "limitations": limits,
            "methodology": "Analysts followed the workflow DISCOVER, COLLECT, PRESERVE, VERIFY, CORRELATE, ANALYZE, ASSESS, REPORT. Each artefact was hashed (SHA-256) on import and its provenance recorded; all actions are in a tamper-evident audit log.",
            "audit_events": db.query(AuditLog).filter_by(case_id=cid).count()}

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{{ d.case.ref }} - Investigation Report</title>
<style>body{font:14px/1.5 Georgia,serif;max-width:900px;margin:2em auto;color:#1a1d21;padding:0 1em}h1{font-size:22px}h2{font-size:17px;border-bottom:1px solid #999;padding-top:1em}
table{border-collapse:collapse;width:100%;font:12px system-ui}td,th{border:1px solid #bbb;padding:4px 6px;text-align:left;vertical-align:top}.m{font:11px ui-monospace,monospace;word-break:break-all}
.k{display:inline-block;padding:0 6px;border:1px solid #444;font:11px system-ui}.warn{color:#8a4b00}.banner{font:11px system-ui;text-align:center;border:1px solid #444;padding:3px}</style></head><body>
<div class="banner">{{ d.classification }} | TLP:{{ d.case.tlp }}</div><h1>{{ d.case.ref }} - {{ d.case.title }}</h1>
<p>Prepared by {{ d.generated_by }}{% if d.organization %}, {{ d.organization }}{% endif %} on {{ d.generated_at }}. Status: {{ d.case.status }}. Priority: {{ d.case.priority }}.</p>
<h2>1. Executive Summary</h2><p>{{ d.case.description or 'No summary recorded.' }}</p>
<p>{{ d.findings|length }} finding(s): {% for k,v in d.confidence_summary.items() %}{{ v }} at {{ k }} confidence{% if not loop.last %}, {% endif %}{% endfor %}. {{ d.findings|selectattr('kind','in',['INFERENCE','HYPOTHESIS'])|list|length }} are inferences or hypotheses and are not confirmed.</p>
<h2>2. Investigation Objective</h2><p>{{ d.case.objectives or '-' }}</p><h2>3. Scope</h2><p>{{ d.case.scope or '-' }}</p><p class="m">Authorization: {{ d.case.authorization_notes }}</p>
<h2>4. Methodology</h2><p>{{ d.methodology }}</p>
<h2>5. Subject Overview</h2><table><tr><th>ID</th><th>Name</th><th>Type</th><th>Role</th><th>Confidence</th></tr>{% for s in d.subjects %}<tr><td>{{ s.ref }}</td><td>{{ s.display_name }}</td><td>{{ s.subject_type }}</td><td>{{ s.role }}</td><td>{{ s.confidence }}</td></tr>{% endfor %}</table>
<h2>6. Key Findings</h2>{% for f in d.findings %}<h3>{{ f.ref }} - {{ f.title }}</h3><p><span class="k">{{ f.kind }}</span> <span class="k">Severity: {{ f.severity }}</span> <span class="k">Confidence: {{ f.confidence }}</span> <span class="k">{{ f.status }}</span>{% if f.ai_generated %} <span class="k">AI-ASSISTED, ANALYST-APPROVED</span>{% endif %}</p>
<p><i>{{ f.kind_note }}</i></p><p>{{ f.description }}</p>{% if f.analyst_assessment %}<p><b>Assessment:</b> {{ f.analyst_assessment }}</p>{% endif %}{% if f.recommendation %}<p><b>Recommendation:</b> {{ f.recommendation }}</p>{% endif %}
{% if f.unsupported %}<p class="warn"><b>UNSUPPORTED:</b> no linked source or evidence.</p>{% endif %}
<p>Sources: {% for s in f.sources %}{{ s.ref }} ({{ s.title }}, Admiralty {{ s.admiralty }}){% if not loop.last %}; {% endif %}{% else %}none{% endfor %}<br>Evidence: {% for e in f.evidence %}{{ e.ref }}{% if not loop.last %}, {% endif %}{% else %}none{% endfor %}</p>{% endfor %}
<h2>7. Evidence</h2><table><tr><th>ID</th><th>Description</th><th>Collected</th><th>SHA-256</th><th>Integrity</th></tr>{% for e in d.evidence %}<tr><td>{{ e.ref }}</td><td>{{ e.description }}<br>{{ e.original_filename }}</td><td>{{ e.collected_at }}</td><td class="m">{{ e.sha256 }}</td><td>{{ e.integrity_status }}</td></tr>{% endfor %}</table>
<h2>8. Source Analysis</h2><table><tr><th>ID</th><th>Title / URL</th><th>Publisher</th><th>Accessed</th><th>Admiralty</th></tr>{% for s in d.sources %}<tr><td>{{ s.ref }}</td><td>{{ s.title }}<br class="m">{{ s.url }}</td><td>{{ s.publisher }}</td><td>{{ s.access_date }}</td><td>{{ s.admiralty }}</td></tr>{% endfor %}</table>
<h2>9. Timeline</h2><table><tr><th>Date</th><th>Event</th><th>Type</th></tr>{% for t in d.timeline %}<tr><td>{{ t.event_date }}</td><td>{{ t.title }}</td><td>{{ t.event_type }}</td></tr>{% endfor %}</table>
<h2>10. Relationship Analysis</h2><table><tr><th>From</th><th>Relationship</th><th>To</th><th>Certainty</th><th>Reasoning</th></tr>{% for x in d.relationships %}<tr><td>{{ x.from_label }}</td><td>{{ x.rel_type }}</td><td>{{ x.to_label }}</td><td>{{ x.certainty }} ({{ x.confidence_pct }}%)</td><td>{{ x.reasoning }}</td></tr>{% endfor %}</table>
<h2>11. Confidence Assessment</h2><p>Confidence reflects the strength of linked evidence and source reliability, not certainty about identity. Only findings labelled CONFIRMED with FACT type should be read as established.</p>
<h2>12. Limitations</h2><ul>{% for l in d.limitations %}<li>{{ l }}</li>{% endfor %}</ul>
<h2>13. Analyst Conclusion</h2><p>{{ conclusion or 'The analyst has not entered a conclusion.' }}</p>
<h2>14. Appendix</h2><p>Audit events recorded for this case: {{ d.audit_events }}. Report integrity: see SHA-256 recorded in the Reports register.</p></body></html>"""

env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

def render_html(d, conclusion): return env.from_string(HTML).render(d=d, conclusion=conclusion).encode()

def render_pdf(d, conclusion) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as x
    ss = getSampleStyleSheet(); buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"{d['case']['ref']} report", leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    P = lambda t, s="BodyText": Paragraph(x(str(t or "")), ss[s])
    def tbl(head, rows, w):
        t = Table([[Paragraph(f"<b>{x(h)}</b>", ss["BodyText"]) for h in head]] + [[Paragraph(x(str(c or "")), ss["BodyText"]) for c in r] for r in rows], colWidths=w, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7)])); return t
    c = d["case"]; s = [P(d["classification"] + " | TLP:" + c["tlp"], "Italic"), P(f"{c['ref']} - {c['title']}", "Title"), P(f"Prepared by {d['generated_by']} on {d['generated_at']}. Status {c['status']}, priority {c['priority']}."),
         P("1. Executive Summary", "Heading2"), P(c["description"] or "No summary recorded."), P("2. Investigation Objective", "Heading2"), P(c["objectives"] or "-"),
         P("3. Scope", "Heading2"), P(c["scope"]), P("Authorization: " + c["authorization_notes"]), P("4. Methodology", "Heading2"), P(d["methodology"]),
         P("5. Subject Overview", "Heading2"), tbl(["ID", "Name", "Type", "Role", "Confidence"], [[a["ref"], a["display_name"], a["subject_type"], a["role"], a["confidence"]] for a in d["subjects"]], [50, 150, 70, 150, 70]),
         P("6. Key Findings", "Heading2")]
    for f in d["findings"]:
        s += [P(f"{f['ref']} - {f['title']}", "Heading3"), P(f"[{f['kind']}] Severity {f['severity']} | Confidence {f['confidence']} | {f['status']}" + (" | AI-ASSISTED, ANALYST-APPROVED" if f["ai_generated"] else "")),
              P(f["kind_note"], "Italic"), P(f["description"]), P("Assessment: " + f["analyst_assessment"]) if f["analyst_assessment"] else Spacer(1, 1),
              P("Sources: " + ("; ".join(f"{a['ref']} ({a['title']})" for a in f["sources"]) or "none") + " | Evidence: " + (", ".join(a["ref"] for a in f["evidence"]) or "none") + (" | UNSUPPORTED" if f["unsupported"] else ""))]
    s += [P("7. Evidence", "Heading2"), tbl(["ID", "Description", "Collected", "SHA-256", "Integrity"], [[e["ref"], e["description"], e["collected_at"], e["sha256"], e["integrity_status"]] for e in d["evidence"]], [40, 130, 70, 220, 55]),
          P("8. Source Analysis", "Heading2"), tbl(["ID", "Title / URL", "Accessed", "Reliability"], [[a["ref"], f"{a['title']} {a['url']}", a["access_date"], a["reliability"]] for a in d["sources"]], [40, 330, 70, 70]),
          P("9. Timeline", "Heading2"), tbl(["Date", "Event", "Type"], [[t["event_date"], t["title"], t["event_type"]] for t in d["timeline"]], [80, 360, 80]),
          P("10. Relationship Analysis", "Heading2"), tbl(["From", "Relationship", "To", "Certainty", "Reasoning"], [[a["from_label"], a["rel_type"], a["to_label"], f"{a['certainty']} {a['confidence_pct']}%", a["reasoning"]] for a in d["relationships"]], [80, 80, 80, 70, 210]),
          P("11. Confidence Assessment", "Heading2"), P("Confidence reflects evidence strength and source reliability, not certainty about identity."),
          P("12. Limitations", "Heading2")] + [P("- " + l) for l in d["limitations"]] + [P("13. Analyst Conclusion", "Heading2"), P(conclusion or "The analyst has not entered a conclusion."), P("14. Appendix", "Heading2"), P(f"Audit events for this case: {d['audit_events']}.")]
    doc.build(s); return buf.getvalue()

@r.post("", status_code=201)
def generate(body: dict, db: Session = Depends(get_db), user=Depends(writer)):
    case = case_access(db, user, body.get("case_id", ""), write=True)
    fmt = body.get("format", "html")
    if fmt not in ("html", "json", "pdf"): raise HTTPException(422, "format: html | json | pdf")
    conclusion = str(body.get("conclusion", ""))[:8000]
    d = build(db, case, user, body)
    ref = next_ref(db, "RPT", 4)
    data = render_html(d, conclusion) if fmt == "html" else render_pdf(d, conclusion) if fmt == "pdf" else json.dumps({**d, "conclusion": conclusion}, indent=2, default=str).encode()
    folder = config.CASES_DIR / case.ref / "exports"; folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{ref}_{case.ref}.{fmt}"; dest.write_bytes(data)
    rep = Report(case_id=case.id, ref=ref, title=body.get("title") or f"{case.ref} investigation report", fmt=fmt, path=str(dest.relative_to(config.DATA_DIR)),
                 sha256=hashlib.sha256(data).hexdigest(), options_json=json.dumps({"conclusion": conclusion}), created_by=user.id)
    db.add(rep); log(db, user, "REPORT_EXPORTED", "report", ref, case.id, format=fmt, sha256=rep.sha256); db.commit()
    return to_dict(rep)

@r.get("")
def list_reports(case_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    case_access(db, user, case_id)
    return [to_dict(x) for x in db.query(Report).filter_by(case_id=case_id).order_by(Report.created_at.desc())]

@r.get("/{rid}/download")
def download(rid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    rep = db.get(Report, rid)
    if not rep: raise HTTPException(404, "Report not found")
    case_access(db, user, rep.case_id)
    p = (config.DATA_DIR / rep.path).resolve()
    if config.DATA_DIR not in p.parents or not p.exists(): raise HTTPException(404, "File missing")
    log(db, user, "REPORT_DOWNLOADED", "report", rep.ref, rep.case_id); db.commit()
    mt = {"html": "text/html", "json": "application/json", "pdf": "application/pdf"}[rep.fmt]
    return FileResponse(p, media_type="application/octet-stream" if rep.fmt == "html" else mt, filename=p.name, headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'"})
