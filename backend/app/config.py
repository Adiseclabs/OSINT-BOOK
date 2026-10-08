import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("OSINTBOOK_DATA", BASE.parent / "data")).resolve()
DB_PATH = DATA_DIR / "osintbook.db"
CASES_DIR = DATA_DIR / "cases"
EXPORTS_DIR = DATA_DIR / "backups"
MAX_UPLOAD_BYTES = int(os.environ.get("OSINTBOOK_MAX_UPLOAD_MB", "25")) * 1024 * 1024
SESSION_ABSOLUTE_HOURS = 12
SESSION_IDLE_MINUTES = 60
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 5
ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
ALLOWED_EXT = {
    "png": "image", "jpg": "image", "jpeg": "image", "gif": "image", "webp": "image",
    "pdf": "pdf", "txt": "text", "md": "text", "log": "text", "json": "text", "csv": "text",
    "xml": "text", "html": "text", "htm": "text", "whois": "text", "dns": "text",
    "docx": "office", "xlsx": "office", "pptx": "office",
}
MAGIC = {  # extension -> required leading bytes
    "png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff", "gif": b"GIF8",
    "webp": b"RIFF", "pdf": b"%PDF", "docx": b"PK", "xlsx": b"PK", "pptx": b"PK",
}
OLLAMA_URL = os.environ.get("OSINTBOOK_OLLAMA", "http://127.0.0.1:11434")

def ensure_dirs():
    for d in (DATA_DIR, CASES_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
