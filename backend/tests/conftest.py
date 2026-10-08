import os, tempfile, sys
from pathlib import Path
_td = tempfile.mkdtemp(prefix="obtest_")
os.environ["OSINTBOOK_DATA"] = _td
os.environ["OSINTBOOK_ADMIN_PASSWORD"] = "AdminPass12345"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import cli
from app.db import SessionLocal
from app.security import hash_password
from app.models import User

@pytest.fixture(scope="session")
def client():
    db = SessionLocal(); cli.ensure_users(db, False)
    for n, role in (("viewer1", "viewer"), ("other", "investigator")):
        db.add(User(username=n, display_name=n, password_hash=hash_password("UserPass12345"), role=role))
    db.commit(); db.close()
    return TestClient(app)

def login(client, u, p):
    r = client.post("/api/auth/login", json={"username": u, "password": p}); assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}

@pytest.fixture(scope="session")
def admin(client): return login(client, "admin", "AdminPass12345")
@pytest.fixture(scope="session")
def viewer(client): return login(client, "viewer1", "UserPass12345")
@pytest.fixture(scope="session")
def other(client): return login(client, "other", "UserPass12345")
