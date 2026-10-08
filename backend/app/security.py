import hashlib, hmac, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, SessionRow, Case, CaseMember, now
from . import config

def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"

def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False

def check_password_strength(pw: str):
    if len(pw) < 10 or pw.lower() == pw or not any(c.isdigit() for c in pw):
        raise HTTPException(422, "Password needs 10+ characters with upper-case, lower-case and a digit.")

def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()

def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_ABSOLUTE_HOURS)
    db.add(SessionRow(token_hash=_h(token), user_id=user.id, expires_at=_iso(exp)))
    db.commit()
    return token

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    s = db.get(SessionRow, _h(auth[7:].strip()))
    n = datetime.now(timezone.utc)
    if not s:
        raise HTTPException(401, "Session invalid")
    last = datetime.strptime(s.last_seen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if s.expires_at < _iso(n) or n - last > timedelta(minutes=config.SESSION_IDLE_MINUTES):
        db.delete(s); db.commit()
        raise HTTPException(401, "Session expired")
    s.last_seen = _iso(n)
    user = db.get(User, s.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account disabled")
    db.commit()
    request.state.user = user
    return user

def writer(user: User = Depends(current_user)) -> User:
    if user.role == "viewer":
        raise HTTPException(403, "Read-only account")
    return user

def admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator only")
    return user

def case_access(db: Session, user: User, case_id: str, write: bool = False) -> Case:
    """Case-level permission: admin, assigned investigator, or explicit member."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if user.role == "admin" or case.investigator_id == user.id:
        return case
    m = db.get(CaseMember, (case_id, user.id))
    if not m or (write and m.access != "write") or (write and user.role == "viewer"):
        raise HTTPException(403, "No access to this case")
    return case

def visible_case_ids(db: Session, user: User) -> list[str]:
    if user.role == "admin":
        return [c for (c,) in db.query(Case.id).all()]
    own = {c for (c,) in db.query(Case.id).filter(Case.investigator_id == user.id)}
    mem = {c for (c,) in db.query(CaseMember.case_id).filter(CaseMember.user_id == user.id)}
    return list(own | mem)
