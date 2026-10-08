"""Command line: python -m app.cli init [--demo] | passwd USER | verify"""
import io, json, os, secrets, sys
from .db import Base, engine, SessionLocal
from . import models  # noqa
from .models import *  # noqa
from .security import hash_password
from .audit import next_ref, log, verify_chain

def pw() -> str:
    return secrets.token_urlsafe(12) + "A1"

def ensure_users(db, demo: bool):
    out = {}
    if not db.query(User).filter_by(username="admin").first():
        p = os.environ.get("OSINTBOOK_ADMIN_PASSWORD") or pw()
        db.add(User(username="admin", display_name="Administrator", password_hash=hash_password(p), role="admin")); out["admin"] = p
    if demo and not db.query(User).filter_by(username="analyst").first():
        p = pw(); db.add(User(username="analyst", display_name="Sam Rivera (demo)", password_hash=hash_password(p), role="investigator")); out["analyst"] = p
    db.commit(); return out

def png_profile() -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (640, 360), (245, 246, 248)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 640, 40], fill=(40, 60, 90)); d.text((14, 14), "example.org / people / alexm   (FICTIONAL SAMPLE)", fill="white")
    d.ellipse([30, 70, 110, 150], fill=(180, 190, 205)); d.text((130, 80), "Alex Morgan  (@alexm)", fill=(20, 20, 20))
    d.text((130, 105), "Research engineer, Example Research Group", fill=(60, 60, 60)); d.text((130, 125), "Writes about open data. Site: example.org", fill=(60, 60, 60))
    d.text((30, 330), "Synthetic image generated for the OSINT BOOK demo case", fill=(120, 120, 120))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def seed(db, user):
    from .routers.evidence import store_bytes
    mk = lambda M, p, w=4, **kw: _mk(db, user, M, p, w, **kw)
    case = Case(ref="CASE-2026-0001", title="Public Identity Correlation Exercise", case_type="Online identity", priority="High", status="Active", stage="CORRELATE",
                description="Fictional exercise: assess whether a public username used on two platforms is associated with a named researcher. All data is synthetic.",
                objectives="Determine, using public sources only, whether '@alexm' accounts relate to Alex Morgan of Example Research Group, and rate the strength of each link.",
                scope="Public web pages and DNS records for example.org. No logins, no private data, no contact with the subject.",
                authorization_notes="Training exercise. Authorized by the course lead; no real persons are involved.", investigator_id=user.id, start_date="2026-09-01", target_date="2026-10-30")
    case.id = uid(); db.add(case); db.flush()
    cid = case.id; log(db, user, "CASE_CREATED", "case", case.ref, cid)
    subj = mk(Subject, "SUBJ", case_id=cid, display_name="Alex Morgan", aliases=json.dumps(["alexm", "A. Morgan"]), role="Subject of exercise", confidence="Medium", description="Fictional researcher listed on example.org staff page.")
    org = mk(Organization, "ORG", case_id=cid, name="Example Research Group", org_type="Research", website="https://example.org", description="Fictional organisation.")
    dom = mk(Domain, "DOM", case_id=cid, name="example.org", registrar="Example Registrar Inc.", registered_on="2019-04-12")
    S = [mk(Source, "SRC", case_id=cid, title=t, url=u, publisher=p, source_type=st, publication_date=pd, access_date=ad, reliability=rel, confidence=c, notes=n) for t, u, p, st, pd, ad, rel, c, n in [
        ("Example Research Group - Staff page", "https://example.org/people/alexm", "Example Research Group", "Web page", "2026-06-02", "2026-09-01", "High", "High", "Lists Alex Morgan with handle @alexm."),
        ("Code hosting profile 'alexm'", "https://code.example.net/alexm", "Example Code", "Social profile", None, "2026-09-03", "Medium", "Medium", "Bio links to example.org."),
        ("Forum profile 'alexm'", "https://forum.example.com/u/alexm", "Example Forum", "Social profile", None, "2026-09-05", "Low", "Low", "Short bio, no website. Joined 2021."),
        ("example.org WHOIS record", "whois://example.org", "Registry", "Domain record", "2026-09-04", "2026-09-04", "High", "High", "Registrant data redacted."),
        ("Conference programme 2026", "https://conf.example.org/2026/programme.pdf", "Example Conf", "Document", "2026-05-20", "2026-09-07", "Medium", "Medium", "Speaker 'A. Morgan' affiliated with Example Research Group.")]]
    for s in S: s.id = s.id
    acc1 = mk(Account, "ACC", case_id=cid, subject_id=subj.id, platform="Example Code", username="alexm", profile_url=S[1].url, display_name="Alex M.", bio="Open data tinkerer. https://example.org", public_website="https://example.org", first_observed="2026-09-03", last_observed="2026-09-09", status="Active", confidence="Medium")
    acc2 = mk(Account, "ACC", case_id=cid, platform="Example Forum", username="alexm", profile_url=S[2].url, display_name="alexm", bio="Open data, maps, coffee.", first_observed="2026-09-05", last_observed="2026-09-05", status="Active", confidence="Low")
    idu = mk(Identifier, "ID", case_id=cid, subject_id=subj.id, value="alexm", id_type="Username", source_id=S[0].id, observed_date="2026-09-01", confidence="High", notes="Handle shown on staff page.")
    mk(Identifier, "ID", case_id=cid, subject_id=subj.id, value="alex.morgan@example.org", id_type="Email", source_id=S[0].id, observed_date="2026-09-01", confidence="Medium", notes="Fictional public contact address.", sensitive=True)
    snaps = [("Screenshot", "staff_page.png", png_profile(), "Screenshot of staff page showing @alexm", S[0].id),
             ("Webpage capture", "code_profile.html", b"<html><body><h1>alexm</h1><p>Open data tinkerer. https://example.org</p></body></html>", "HTML capture of code-hosting profile (stored inert)", S[1].id),
             ("Text file", "forum_profile.txt", b"alexm - Joined 2021\nOpen data, maps, coffee.\n", "Text capture of forum profile", S[2].id),
             ("WHOIS output", "example.org.whois", b"Domain Name: EXAMPLE.ORG\nRegistrar: Example Registrar Inc.\nCreation Date: 2019-04-12T00:00:00Z\nRegistrant: REDACTED\n", "WHOIS output for example.org", S[3].id),
             ("DNS output", "example.org.dns", b"example.org. A 192.0.2.10\nexample.org. MX 10 mail.example.org.\nexample.org. TXT \"v=spf1 -all\"\n", "DNS records for example.org", S[3].id)]
    case_obj = db.get(Case, cid); E = []
    for et, fn, data, desc, sid in snaps:
        ev = store_bytes(db, user, case_obj, data, fn, et, desc, sid, f"2026-09-0{len(E) + 1}T10:00:00Z"); ev.verification_status = "Verified" if len(E) < 3 else "Pending"; E.append(ev)
    acc1.evidence_id = E[1].id; acc2.evidence_id = E[2].id
    T = [("2026-09-01", "Public staff page lists @alexm", "Discovery", S[0].id, E[0].id), ("2026-09-03", "Code-hosting profile 'alexm' found; bio links example.org", "Observation", S[1].id, E[1].id),
         ("2026-09-04", "WHOIS and DNS for example.org collected", "Capture", S[3].id, E[3].id), ("2026-09-05", "Forum profile 'alexm' found (no organisational link)", "Observation", S[2].id, E[2].id),
         ("2026-09-07", "Conference programme names 'A. Morgan' at Example Research Group", "Observation", S[4].id, None)]
    for d, t, et, sid, eid in T: mk(TimelineEvent, "TL", case_id=cid, event_date=d, title=t, event_type=et, subject_id=subj.id, source_id=sid, evidence_id=eid)
    R = [("subject", subj.id, "organization", org.id, "WORKS_FOR", "CONFIRMED", 90, "Staff page lists Alex Morgan at the group.", E[0].id, S[0].id),
         ("subject", subj.id, "account", acc1.id, "USES", "LIKELY", 70, "Bio links to example.org; handle matches staff page.", E[1].id, S[1].id),
         ("subject", subj.id, "account", acc2.id, "USES", "POSSIBLE", 30, "Only the username matches; no organisational indicators.", E[2].id, S[2].id),
         ("organization", org.id, "domain", dom.id, "OWNS", "LIKELY", 75, "Domain hosts the group's staff pages; registrant redacted.", E[3].id, S[3].id),
         ("account", acc1.id, "account", acc2.id, "ASSOCIATED_WITH", "POSSIBLE", 35, "Identical username on two platforms. Username reuse alone is weak.", None, None)]
    for ft, fi, tt, ti, rt, cert, pct, why, eid, sid in R: mk(Relationship, "REL", case_id=cid, from_type=ft, from_id=fi, to_type=tt, to_id=ti, rel_type=rt, certainty=cert, confidence_pct=pct, reasoning=why, evidence_id=eid, source_id=sid)
    F_ = [("Staff page lists handle @alexm for Alex Morgan", "FACT", "Medium", "High", "Approved", "The staff page on example.org displays the handle next to the name and role.", "Directly observed; screenshot preserved and hashed.", [("evidence", E[0]), ("source", S[0])]),
          ("Code-hosting profile 'alexm' likely belongs to the same individual", "INFERENCE", "Medium", "Medium", "Under Review", "The profile bio links to example.org and uses the same handle as the staff page.", "Two independent indicators (handle + link). No direct statement of ownership, so this is an inference.", [("evidence", E[1]), ("source", S[1])]),
          ("Forum profile 'alexm' may be operated by the same person", "HYPOTHESIS", "Low", "Low", "Draft", "Only the username matches; the forum profile has no organisational, linguistic or temporal overlap with the others.", "Insufficient to link. Collect additional distinguishing attributes before any conclusion.", [("evidence", E[2]), ("source", S[2])])]
    for t, k, sev, conf, stt, desc, assess, links in F_:
        f = mk(Finding, "F", 3, case_id=cid, title=t, kind=k, severity=sev, confidence=conf, status=stt, description=desc, analyst_assessment=assess, subject_id=subj.id)
        for ty, o in links: db.add(FindingLink(finding_id=f.id, target_type=ty, target_id=o.id))
    mk(Task, "TASK", case_id=cid, title="Check forum profile for additional distinguishing attributes", status="Open", priority="High", due_date="2026-10-12", stage="VERIFY")
    mk(Task, "TASK", case_id=cid, title="Verify conference programme PDF and preserve a copy", status="In Progress", priority="Medium", due_date="2026-10-14", stage="PRESERVE")
    mk(Note, "NOTE", case_id=cid, title="Analyst note: scoping", body="Exercise limited to public pages. Do not contact the subject. Treat username reuse as weak evidence.", subject_id=subj.id)
    db.commit()
    # second, lighter case for dashboard context
    c2 = Case(ref="CASE-2026-0002", title="Brand Impersonation Review", case_type="Corporate impersonation", priority="Medium", status="Under Review", stage="COLLECT",
              description="Fictional: look-alike domain suspected of imitating a brand.", authorization_notes="Training exercise; fictional brand.", investigator_id=user.id, start_date="2026-09-20")
    db.add(c2); db.flush(); log(db, user, "CASE_CREATED", "case", c2.ref, c2.id)
    mk(Domain, "DOM", case_id=c2.id, name="examp1e-brand.example", notes="Look-alike of fictional brand domain.")
    mk(Task, "TASK", case_id=c2.id, title="Collect DNS and certificate data for look-alike domain", status="Open", priority="Medium", due_date="2026-10-09", stage="COLLECT")
    db.commit()

def _mk(db, user, M, prefix, width, **kw):
    kw.setdefault("created_by", user.id)
    r = M(ref=next_ref(db, prefix, width), **kw); db.add(r); db.flush()
    log(db, user, "CREATED", M.__tablename__, r.ref, kw.get("case_id")); return r

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    Base.metadata.create_all(engine); db = SessionLocal()
    if cmd == "init":
        demo = "--demo" in sys.argv
        creds = ensure_users(db, demo)
        if demo and not db.query(Case).first():
            seed(db, db.query(User).filter_by(username="admin").first()); print("Sample case CASE-2026-0001 loaded (fictional data).")
        for u, p in creds.items(): print(f"  created user {u}  password: {p}   <- shown once, change it in Settings")
        print("Database ready.")
    elif cmd == "passwd":
        u = db.query(User).filter_by(username=sys.argv[2]).first()
        if not u: sys.exit("No such user")
        p = pw(); u.password_hash = hash_password(p); db.query(SessionRow).filter_by(user_id=u.id).delete(); db.commit(); print("New password:", p)
    elif cmd == "verify":
        print(verify_chain(db))
    else:
        print(__doc__)

if __name__ == "__main__": main()
