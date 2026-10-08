```
CASE FILE ............ OSINT BOOK
CLASSIFICATION ....... local workstation, your machine only
STAGE ................ DISCOVER > COLLECT > PRESERVE > VERIFY > CORRELATE > ANALYZE > ASSESS > REPORT
STATUS ............... v1.1, working, honest about its gaps (see the end)
ANALYST .............. Aditya Bhosale
```

# OSINT BOOK

**Open Source Intelligence Investigation & Case Management.**

Most OSINT work dies in a folder of screenshots named `final_final_2.png`. Three weeks later nobody can say where a claim came from, whether the file was ever touched, or whether "probably the same person" was an observation or a hunch someone typed in confidently.

OSINT BOOK is a notebook that refuses to let that happen. It runs on your laptop, stores everything in one SQLite file plus a folder, and makes you say three things about every piece of information: **where it came from, whether it has changed since, and how sure you actually are.**

No cloud. No account. No telemetry. No paid APIs.

---

## The house rules

These are not features. They are constraints the whole app is built around.

**1. A claim without a source is flagged, not hidden.**
Every finding links to the sources and evidence behind it. If it links to nothing, it is marked `UNSUPPORTED` in the app and in the report.

**2. Say how sure you are, in the shape of the thing.**
Findings are one of four types, and they look different on purpose:

| Type | Meaning | Looks like |
|---|---|---|
| `FACT` | Directly shown by preserved evidence | solid |
| `OBSERVATION` | You saw it; nobody corroborated it | outlined |
| `INFERENCE` | A judgement drawn from facts | dashed |
| `HYPOTHESIS` | A working guess | dotted |

Relationships follow the same idea. A `CONFIRMED` link is a solid line, `LIKELY` is dashed, `POSSIBLE` is dotted, so an uncertain connection never looks like a settled one. And a `CONFIRMED` relationship cannot be saved without a source or evidence behind it.

**3. Evidence is hashed the moment it arrives, and then it is frozen.**
SHA-256 on import. The file, its hash and its collection time cannot be edited. Re-verify any time and the result goes into a history. Delete a file and it is overwritten, but a tombstone with the original hash stays so the chain of custody still reads true.

**4. The log cannot be edited, including by you.**
Audit records are append-only (the database itself rejects `UPDATE` and `DELETE`) and hash-chained, so an admin can prove the log was not rewritten.

**5. The machine suggests. The analyst decides.**
The assistant can propose entities, timeline events and relationships. Every suggestion is stamped `AI GENERATED`, sits in a queue, and becomes a real record only when you approve it. Approved findings enter as `Draft`.

---

## What it will not do

Built deliberately without: credential or password collection, private-account access, location tracking, doxxing helpers, anything that bypasses a platform's controls. The username tool only *generates candidate URLs* for you to open and judge yourself. It never probes the platforms.

Email and phone identifiers are masked by default, saving one asks you to confirm a lawful basis, and every reveal is logged. A case cannot be created without recording who authorized it.

---

## Run it

You need Python 3.10+ and Node 18+.

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.cli init --demo
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Second terminal:

```powershell
cd frontend
npm install
npm run dev
```

**Linux / macOS**

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli init --demo
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd ../frontend && npm install && npm run dev
```

Open **http://127.0.0.1:5173**.

`init` prints the `admin` and `analyst` passwords **once**. Copy them. Lost one: `python -m app.cli passwd admin`. Want an empty install: leave off `--demo`. API docs live at `/api/docs`.

> **Upgrading an older database?** Just start the server once. New columns are added automatically and no data is touched.

---

## Take the tour: the sample case

`--demo` loads **CASE-2026-0001, "Public Identity Correlation Exercise"**. Everything in it is fictional. It is built to show the part most tools skip: *how weak evidence should look.*

The question: does the username `alexm` on two platforms belong to Alex Morgan of Example Research Group?

Open it and look at three things.

1. **Relationships.** `Alex Morgan WORKS_FOR Example Research Group` is a solid line, because a staff page proves it. `Alex Morgan USES alexm` on the forum is dotted at 30%. The only link is a shared username, and the case says so in its own reasoning.
2. **Findings.** One `FACT`, one `INFERENCE`, one `HYPOTHESIS`. The third one is the honest answer: *insufficient to link.*
3. **Readiness tab.** Nine checks before you are allowed to feel finished. The sample case fails two on purpose (evidence pending review, tasks still open).

Then generate a report. The inference is never worded as confirmed, and every finding cites its sources with an Admiralty grade.

---

## How a case moves

```
DISCOVER   record what you are looking at, and your authority to look
COLLECT    run tools, find sources, write them down
PRESERVE   hash it, store it, never touch it again
VERIFY     check the hashes; check the claims against independent sources
CORRELATE  draw relationships, with confidence and reasoning
ANALYZE    build the timeline, find the gaps
ASSESS     grade each finding; separate fact from judgement
REPORT     HTML, PDF or JSON, with the limits stated
```

The stage bar sits under the header for the active case. Tasks carry a stage. Four case types (corporate impersonation, alias research, security incident, due diligence) start with a ready-made task list so you begin from a method rather than a blank page.

---

## What is inside

| Area | What it does |
|---|---|
| **Cases** | Authorization, scope, objectives, TLP marking, per-case access (admin, lead, read or write members) |
| **Subjects, identifiers, accounts, domains, organizations** | The things you are investigating, each with source, date and confidence |
| **Sources** | Reliability **A to F** and information credibility **1 to 6** (the Admiralty system), shown as a grid per case |
| **Evidence** | Upload, preview as inert text, download, verify, tag, link to findings, full custody trail |
| **Timeline** | Events linked back to subject, source, evidence and finding |
| **Relationships** | Link chart you can drag, pan, zoom, filter by type, and click to focus a node's neighbours |
| **Findings** | The four types above, with a provenance panel showing the claim, its sources and each file's hash |
| **OSINT tools** | 25 passive tools in five groups. Every run is recorded; every result is structured data you can attach to a case, optionally preserved as hashed evidence |
| **Reports** | Fourteen sections, TLP banner, limitations written for you, export to HTML, PDF, JSON |
| **Backup** | Full or per-case, with a SHA-256 manifest that restore checks before touching anything |
| **CSV import** | Identifiers, accounts, sources; validated row by row |
| **Search** | `Ctrl K` across everything, exact matching |

Keyboard: `Ctrl K` search, `Alt 1-9` jump between sections, `?` for the full list.

The tools: DNS, WHOIS, IP and ASN, MX, TXT, reverse DNS, certificate transparency, URL metadata, HTTP headers, robots.txt, sitemap, page metadata, technology hints, username candidates, public email domain check, profile comparison, PDF and image metadata, hashing, file type, entity extraction, relationship extraction, timeline builder, duplicate detection, evidence correlation.

---

## Where things live

```
data/
  osintbook.db                      all structured records
  cases/CASE-2026-0001/
    evidence/  screenshots/  documents/  exports/
  backups/                          archives with integrity manifests
```

Set `OSINTBOOK_DATA` to move it. `OSINTBOOK_MAX_UPLOAD_MB` (default 25) caps uploads. `OSINTBOOK_OLLAMA` points at a local model if you want AI summaries. Everything else is in **Settings**.

> **Never commit `data/`.** It holds your evidence and your database. The `.gitignore` already excludes it. Keep it that way.

---

## Security, plainly

- Passwords are scrypt-hashed. Sessions are random tokens stored hashed, expire after 60 idle minutes (12 hours hard), and five bad logins lock the account briefly.
- Every write is whitelisted and type-checked; all SQL is parameterized.
- Uploads must match an allowed extension *and* its magic bytes, get generated storage names, and are never executed. HTML evidence is shown as text, never rendered.
- URL tools refuse loopback and private addresses, and re-check every redirect hop. Turn that off only for an authorized internal assessment.
- Case permissions are enforced on the server, not just hidden in the UI.

---

## The map

```
backend/app/
  models.py  db.py  security.py  audit.py
  crud.py            validated, audited CRUD shared by case entities
  osint.py           the tools          netguard.py   outbound request guard
  cli.py             init, seed, passwd, verify
  routers/           core  evidence  tools  search  reports  backup  analysis  extras
frontend/src/
  ctx.tsx  lib.ts  ui.tsx  EntityPage.tsx   shell, API client, shared parts
  pages/                                    one file per screen
```

FastAPI, SQLAlchemy and SQLite on one side; React, TypeScript and Tailwind on the other. Fonts are IBM Plex, bundled, so it works offline.

---

## Tests

```bash
cd backend && pytest -q        # 14 tests
cd frontend && npm run build   # type-check and production build
```

The backend suite covers login lockout, validation, identifier masking, evidence tamper detection, hostile uploads, audit immutability, case permissions, the SSRF guard, all three report formats, backup round-trips and tamper rejection, and the AI approval gate.

---

## Things I know are weak

Better you read this here than discover it mid-investigation.

- The tools that need the internet (WHOIS, certificate transparency, DNS, HTTP) are **not covered by automated tests**.
- There are **no automated frontend tests** yet. The UI was checked by hand and by screenshot.
- Backups are **not encrypted**. Put them on an encrypted disk.
- ASN lookup is **IPv4 only**.
- It is a **single-machine tool**. Do not expose it to a network.
- Authorization is a recorded note, not an approval workflow.
- It has seen one analyst's testing, not a team's real caseload.

## Next

Encrypted backups, frontend tests, richer graph editing, saved searches, evidence redaction, a proper release build.

---

Not affiliated with any government or law-enforcement agency. For authorized work on lawfully obtained public information. What it produces is analyst work product, not a legal finding.

**Designed and built by Aditya Bhosale.**

*Licence: not chosen yet. Add one before accepting contributions.*
