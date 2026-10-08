import hashlib, json
from sqlalchemy.orm import Session
from .models import AuditLog, Counter, User, now

def next_ref(db: Session, prefix: str, width: int = 4, year: bool = False) -> str:
    key = f"{prefix}-{now()[:4]}" if year else prefix
    c = db.get(Counter, key)
    if not c:
        c = Counter(prefix=key, n=0); db.add(c)
    c.n = (c.n or 0) + 1
    db.flush()
    return f"{key}-{c.n:0{width}d}"

def log(db: Session, user: User | None, action: str, entity_type: str = "", entity_ref: str = "",
        case_id: str | None = None, **detail):
    """Append a hash-chained audit record (tamper-evident)."""
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev = last.hash if last else "GENESIS"
    ts = now()
    d = json.dumps(detail, sort_keys=True, default=str)
    uname = user.username if user else "system"
    h = hashlib.sha256("|".join([prev, ts, uname, action, entity_type, entity_ref, d]).encode()).hexdigest()
    db.add(AuditLog(ts=ts, user_id=user.id if user else None, username=uname, action=action,
                    entity_type=entity_type, entity_ref=entity_ref, case_id=case_id, detail=d,
                    prev_hash=prev, hash=h))

def verify_chain(db: Session) -> dict:
    prev, n = "GENESIS", 0
    for r in db.query(AuditLog).order_by(AuditLog.id):
        h = hashlib.sha256("|".join([prev, r.ts, r.username, r.action, r.entity_type, r.entity_ref, r.detail]).encode()).hexdigest()
        if r.prev_hash != prev or r.hash != h:
            return {"valid": False, "broken_at": r.id, "checked": n}
        prev, n = r.hash, n + 1
    return {"valid": True, "checked": n}
