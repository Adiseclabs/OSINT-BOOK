from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from . import config
from .db import Base, engine
from . import models  # noqa
from .crud import routers as entity_routers
from .routers import core, evidence, tools, search, reports, backup, analysis, extras

Base.metadata.create_all(engine)

def migrate():
    """Additive migration: add columns introduced after a database was first created."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    with engine.begin() as c:
        for t in Base.metadata.sorted_tables:
            have = {x["name"] for x in insp.get_columns(t.name)}
            for col in t.columns:
                if col.name not in have:
                    d = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                    ddl = f'ALTER TABLE {t.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}'
                    if d is not None: ddl += " DEFAULT '" + str(d).replace("'", "''") + "'"
                    c.execute(text(ddl))
migrate()
app = FastAPI(title="OSINT BOOK", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse({"detail": "Internal error. See server log."}, status_code=500)

for rt in (core.r, evidence.r, tools.r, search.r, reports.r, backup.r, analysis.r, extras.r, *entity_routers):
    app.include_router(rt)

@app.get("/api/health")
def health(): return {"ok": True}
