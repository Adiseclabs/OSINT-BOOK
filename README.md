# OSINT BOOK
Open Source Intelligence Investigation & Case Management. Local-first: FastAPI + SQLAlchemy + SQLite, React + TypeScript + Tailwind. No Docker, no cloud, no paid APIs, no telemetry.

For authorized investigations using lawfully obtained, public information only. It has no features for credential collection, private-account access, location tracking or bypassing platform controls.

## Installation
Requirements: Python 3.10+, Node 18+.

    cd backend && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python -m app.cli init --demo     # creates DB, users, fictional sample case CASE-2026-0001
    cd ../frontend && npm install

`init` prints the generated `admin` and `analyst` passwords **once**. Use `python -m app.cli init` (no `--demo`) for an empty install, or set `OSINTBOOK_ADMIN_PASSWORD` first. Reset a password: `python -m app.cli passwd admin`.

## Running
    cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000     # API docs at /api/docs
    cd frontend && npm run dev                                           # http://127.0.0.1:5173

Or `./start.sh` (`./start.sh --init` on first run).

## Configuration
Environment: `OSINTBOOK_DATA` (data directory, default `./data`), `OSINTBOOK_MAX_UPLOAD_MB` (25), `OSINTBOOK_OLLAMA` (local model URL). Runtime settings (report banner, private-target tools, AI provider) are in Settings.

## Data layout
    data/osintbook.db                 SQLite metadata (WAL, foreign keys on)
    data/cases/CASE-2026-0001/{evidence,screenshots,documents,exports}/
    data/backups/                     backup archives

## Workflow and key behaviours
DISCOVER > COLLECT > PRESERVE > VERIFY > CORRELATE > ANALYZE > ASSESS > REPORT. The stage bar tracks the active case; tasks carry a stage.

- Findings are typed FACT / OBSERVATION / INFERENCE / HYPOTHESIS (solid / outlined / dashed / dotted). Reports never word inferences as confirmed and flag findings with no source or evidence as UNSUPPORTED.
- Relationships carry certainty (CONFIRMED / LIKELY / POSSIBLE) and a percentage; CONFIRMED requires a source or evidence. Graph line style encodes certainty.
- Evidence is SHA-256 hashed on import; file, hash and collection data are immutable. Verify re-hashes and records history. Delete overwrites the file and keeps a metadata tombstone.
- Every tool run is recorded (ID, input, time, status, investigator). Results are structured data that can be attached to a case, optionally preserved as hashed evidence.
- AI assistant: rule-based by default, optional local Ollama summaries. Suggestions are marked AI GENERATED and need analyst approval; approved findings enter as Draft.
- Username search only generates candidate URLs to review manually; it does not probe platforms.

## What's new in 1.1
- **Admiralty source grading** (reliability A-F x information credibility 1-6) on every source, shown in reports and a grid on the case Readiness tab.
- **TLP markings** (CLEAR, GREEN, AMBER, AMBER+STRICT, RED) on cases, shown in the UI header and every report.
- **Case templates**: impersonation, alias research, incident and due-diligence case types create a starter task list tied to the workflow stages.
- **Report readiness checklist**: authorization recorded, findings supported, hashes valid, evidence reviewed, sources graded, no pending AI suggestions, no open tasks.
- **Interactive link chart**: drag nodes, pan, zoom, filter entity types, click a node to focus its neighbours.
- **CSV import** for identifiers, accounts and sources (validated per row, 500-row limit, sensitive-data acknowledgement).
- Findings page, About page, keyboard shortcut help (`?`), bundled IBM Plex fonts (works offline), redesigned layout.
- Existing databases upgrade automatically on start (new columns are added; no data is changed).

## Backup / restore
Settings > Backup & restore (admin). Full backup = SQLite snapshot + all case files + config + SHA-256 manifest. Case backup = case rows (JSON) + files + manifest. Restore verifies the manifest and rejects unsafe paths; a full restore makes a safety copy first. "Verify only" checks integrity without restoring.

## Security notes
- Passwords: scrypt. Sessions: random bearer tokens (stored hashed), 12 h absolute / 60 min idle, kept in sessionStorage (no cookies, so no CSRF surface). Lockout after 5 failed logins.
- Parameterized queries via SQLAlchemy; field whitelists and enums on every write; React escapes output.
- Uploads: extension allow-list, magic-byte check, size limit, generated storage names, path-traversal guard, never executed. HTML/text previews are returned as plain text; images/PDF are served with `nosniff` and a sandbox CSP.
- URL tools block loopback/private targets (SSRF) and re-check every redirect.
- Audit log is append-only (DB triggers) and hash-chained; admins can verify the chain.
- Case-level access: admin, lead investigator, or listed member (read / write); viewers are read-only.
- Email/phone identifiers are masked by default; saving requires acknowledging a sensitive-data warning; reveals are logged.
- Limits: single-machine tool, not hardened for network exposure. Keep it on 127.0.0.1, use disk encryption, encrypt backups.

## Architecture
    backend/app/   models.py db.py security.py audit.py crud.py (validated CRUD for case entities)
                   osint.py netguard.py (tools, SSRF guard)  cli.py (init/seed)
                   routers/ core evidence tools search reports backup analysis
    frontend/src/  ctx.tsx lib.ts ui.tsx EntityPage.tsx pages/*

## Testing
    cd backend && pytest -q        # 13 tests: auth, validation, masking, evidence integrity, upload safety, audit chain, permissions, SSRF, reports, backup, AI approval
    cd frontend && npm run build   # type-check + production build

Network-dependent tools (WHOIS, CT, DNS, HTTP fetch) are not exercised by the tests.

## Known gaps
No encrypted backups, no IPv6 ASN lookup, no PDF preview of reports in-app (download only), the authorization check is a recorded note rather than an external approval workflow.

## Author
Designed and built by Aditya Bhosale.
