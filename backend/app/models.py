import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, Index, UniqueConstraint, event, DDL
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def uid() -> str:
    return str(uuid.uuid4())

S = String
def col(t=S, **kw):
    return mapped_column(t, **kw)

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = col(primary_key=True, default=uid)
    username: Mapped[str] = col(unique=True)
    display_name: Mapped[str] = col()
    password_hash: Mapped[str] = col()
    role: Mapped[str] = col(default="investigator")  # admin | investigator | viewer
    active: Mapped[bool] = col(Boolean, default=True)
    failed_attempts: Mapped[int] = col(Integer, default=0)
    locked_until: Mapped[str | None] = col(nullable=True)
    last_login: Mapped[str | None] = col(nullable=True)
    created_at: Mapped[str] = col(default=now)

class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = col(primary_key=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[str] = col(default=now)
    expires_at: Mapped[str] = col()
    last_seen: Mapped[str] = col(default=now)

class Counter(Base):
    __tablename__ = "counters"
    prefix: Mapped[str] = col(primary_key=True)
    n: Mapped[int] = col(Integer, default=0)

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = col(primary_key=True)
    value: Mapped[str] = col(Text)

class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = col(primary_key=True, default=uid)
    name: Mapped[str] = col(unique=True)

class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = col(primary_key=True, default=uid)
    ref: Mapped[str] = col(unique=True)
    title: Mapped[str] = col()
    description: Mapped[str] = col(Text, default="")
    case_type: Mapped[str] = col(default="General")
    priority: Mapped[str] = col(default="Medium")
    status: Mapped[str] = col(default="Draft")
    investigator_id: Mapped[str | None] = col(ForeignKey("users.id"), nullable=True)
    objectives: Mapped[str] = col(Text, default="")
    scope: Mapped[str] = col(Text, default="")
    authorization_notes: Mapped[str] = col(Text, default="")
    start_date: Mapped[str | None] = col(nullable=True)
    target_date: Mapped[str | None] = col(nullable=True)
    stage: Mapped[str] = col(default="DISCOVER")
    tlp: Mapped[str] = col(default="AMBER")
    created_at: Mapped[str] = col(default=now)
    updated_at: Mapped[str] = col(default=now, onupdate=now)
    __table_args__ = (Index("ix_cases_updated", "updated_at"), Index("ix_cases_status", "status"))

class CaseMember(Base):
    __tablename__ = "case_members"
    case_id: Mapped[str] = col(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = col(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    access: Mapped[str] = col(default="read")  # read | write

class CaseTag(Base):
    __tablename__ = "case_tags"
    case_id: Mapped[str] = col(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = col(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class SubjectTag(Base):
    __tablename__ = "subject_tags"
    subject_id: Mapped[str] = col(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = col(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class CaseEntity:
    """Mixin: every case-scoped record has uuid id, human ref, case, timestamps."""
    id: Mapped[str] = col(primary_key=True, default=uid)
    ref: Mapped[str] = col(unique=True)
    case_id: Mapped[str] = col(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = col(nullable=True)
    created_at: Mapped[str] = col(default=now, index=True)
    updated_at: Mapped[str] = col(default=now, onupdate=now, index=True)

class Subject(CaseEntity, Base):
    __tablename__ = "subjects"
    display_name: Mapped[str] = col()
    subject_type: Mapped[str] = col(default="Person")
    aliases: Mapped[str] = col(Text, default="[]")
    role: Mapped[str] = col(default="")
    description: Mapped[str] = col(Text, default="")
    confidence: Mapped[str] = col(default="Low")

class Identifier(CaseEntity, Base):
    __tablename__ = "identifiers"
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    value: Mapped[str] = col()
    id_type: Mapped[str] = col()
    source_id: Mapped[str | None] = col(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    observed_date: Mapped[str | None] = col(nullable=True)
    confidence: Mapped[str] = col(default="Medium")
    notes: Mapped[str] = col(Text, default="")
    sensitive: Mapped[bool] = col(Boolean, default=False)

class Account(CaseEntity, Base):
    __tablename__ = "accounts"
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    platform: Mapped[str] = col()
    username: Mapped[str] = col()
    profile_url: Mapped[str] = col(default="")
    display_name: Mapped[str] = col(default="")
    bio: Mapped[str] = col(Text, default="")
    public_website: Mapped[str] = col(default="")
    metadata_json: Mapped[str] = col(Text, default="{}")
    first_observed: Mapped[str | None] = col(nullable=True)
    last_observed: Mapped[str | None] = col(nullable=True)
    status: Mapped[str] = col(default="Unknown")
    evidence_id: Mapped[str | None] = col(ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True)
    confidence: Mapped[str] = col(default="Medium")

class Organization(CaseEntity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = col()
    org_type: Mapped[str] = col(default="")
    jurisdiction: Mapped[str] = col(default="")
    website: Mapped[str] = col(default="")
    description: Mapped[str] = col(Text, default="")

class Domain(CaseEntity, Base):
    __tablename__ = "domains"
    name: Mapped[str] = col()
    registrar: Mapped[str] = col(default="")
    registered_on: Mapped[str | None] = col(nullable=True)
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[str | None] = col(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str] = col(Text, default="")

class Source(CaseEntity, Base):
    __tablename__ = "sources"
    source_type: Mapped[str] = col(default="Web page")
    url: Mapped[str] = col(default="")
    title: Mapped[str] = col()
    publisher: Mapped[str] = col(default="")
    author: Mapped[str] = col(default="")
    publication_date: Mapped[str | None] = col(nullable=True)
    access_date: Mapped[str | None] = col(nullable=True)
    archived_url: Mapped[str] = col(default="")
    reliability: Mapped[str] = col(default="Unknown")
    confidence: Mapped[str] = col(default="Medium")
    notes: Mapped[str] = col(Text, default="")
    tags: Mapped[str] = col(default="")
    credibility: Mapped[str] = col(default="6")  # Admiralty information credibility 1-6 (6 = cannot be judged)

class Evidence(CaseEntity, Base):
    __tablename__ = "evidence"
    evidence_type: Mapped[str] = col(default="Document")
    description: Mapped[str] = col(Text, default="")
    original_filename: Mapped[str] = col(default="")
    storage_path: Mapped[str] = col(default="")  # relative to DATA_DIR
    mime: Mapped[str] = col(default="")
    size: Mapped[int] = col(Integer, default=0)
    sha256: Mapped[str] = col(default="")
    collected_at: Mapped[str] = col(default=now)
    source_id: Mapped[str | None] = col(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    collector: Mapped[str] = col(default="")
    integrity_status: Mapped[str] = col(default="VALID")  # VALID | MISMATCH | MISSING | DELETED | UNVERIFIED
    last_verified: Mapped[str | None] = col(nullable=True)
    notes: Mapped[str] = col(Text, default="")
    tags: Mapped[str] = col(default="")
    verification_status: Mapped[str] = col(default="Pending")  # Pending | Verified | Disputed
    deleted_at: Mapped[str | None] = col(nullable=True)

class EvidenceHash(Base):
    __tablename__ = "evidence_hashes"
    id: Mapped[str] = col(primary_key=True, default=uid)
    evidence_id: Mapped[str] = col(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    sha256: Mapped[str] = col()
    kind: Mapped[str] = col(default="initial")  # initial | verify
    result: Mapped[str] = col(default="VALID")
    computed_at: Mapped[str] = col(default=now)
    by_user: Mapped[str] = col(default="")

class Finding(CaseEntity, Base):
    __tablename__ = "findings"
    title: Mapped[str] = col()
    description: Mapped[str] = col(Text, default="")
    kind: Mapped[str] = col(default="OBSERVATION")  # FACT | OBSERVATION | INFERENCE | HYPOTHESIS
    severity: Mapped[str] = col(default="Informational")
    confidence: Mapped[str] = col(default="Low")
    status: Mapped[str] = col(default="Draft")  # Draft | Under Review | Approved | Rejected
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_assessment: Mapped[str] = col(Text, default="")
    recommendation: Mapped[str] = col(Text, default="")
    ai_generated: Mapped[bool] = col(Boolean, default=False)

class FindingLink(Base):
    __tablename__ = "finding_links"
    id: Mapped[str] = col(primary_key=True, default=uid)
    finding_id: Mapped[str] = col(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = col()  # evidence | source
    target_id: Mapped[str] = col(index=True)
    __table_args__ = (UniqueConstraint("finding_id", "target_type", "target_id"),)

class TimelineEvent(CaseEntity, Base):
    __tablename__ = "timeline_events"
    event_date: Mapped[str] = col(index=True)
    title: Mapped[str] = col()
    description: Mapped[str] = col(Text, default="")
    event_type: Mapped[str] = col(default="Observation")
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_id: Mapped[str | None] = col(ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[str | None] = col(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    finding_id: Mapped[str | None] = col(ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)

class Relationship(CaseEntity, Base):
    __tablename__ = "relationships"
    from_type: Mapped[str] = col()
    from_id: Mapped[str] = col(index=True)
    to_type: Mapped[str] = col()
    to_id: Mapped[str] = col(index=True)
    rel_type: Mapped[str] = col()
    certainty: Mapped[str] = col(default="POSSIBLE")  # CONFIRMED | LIKELY | POSSIBLE
    confidence_pct: Mapped[int] = col(Integer, default=30)
    reasoning: Mapped[str] = col(Text, default="")
    evidence_id: Mapped[str | None] = col(ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[str | None] = col(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)

class ToolRun(Base):
    __tablename__ = "tool_runs"
    id: Mapped[str] = col(primary_key=True, default=uid)
    ref: Mapped[str] = col(unique=True)
    tool: Mapped[str] = col()
    input_json: Mapped[str] = col(Text, default="{}")
    started_at: Mapped[str] = col(default=now, index=True)
    finished_at: Mapped[str | None] = col(nullable=True)
    status: Mapped[str] = col(default="Running")
    error: Mapped[str] = col(Text, default="")
    case_id: Mapped[str | None] = col(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[str | None] = col(nullable=True)
    username: Mapped[str] = col(default="")

class ToolResult(Base):
    __tablename__ = "tool_results"
    id: Mapped[str] = col(primary_key=True, default=uid)
    ref: Mapped[str] = col(unique=True)
    tool_run_id: Mapped[str] = col(ForeignKey("tool_runs.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = col(default="")
    data_json: Mapped[str] = col(Text, default="{}")
    saved: Mapped[bool] = col(Boolean, default=False)
    attached_case_id: Mapped[str | None] = col(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    evidence_id: Mapped[str | None] = col(nullable=True)
    created_at: Mapped[str] = col(default=now)

class Note(CaseEntity, Base):
    __tablename__ = "notes"
    title: Mapped[str] = col()
    body: Mapped[str] = col(Text, default="")
    subject_id: Mapped[str | None] = col(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)

class Task(CaseEntity, Base):
    __tablename__ = "tasks"
    title: Mapped[str] = col()
    description: Mapped[str] = col(Text, default="")
    status: Mapped[str] = col(default="Open")  # Open | In Progress | Blocked | Done
    priority: Mapped[str] = col(default="Medium")
    due_date: Mapped[str | None] = col(nullable=True)
    stage: Mapped[str] = col(default="COLLECT")
    assignee_id: Mapped[str | None] = col(ForeignKey("users.id"), nullable=True)

class Report(CaseEntity, Base):
    __tablename__ = "reports"
    title: Mapped[str] = col()
    fmt: Mapped[str] = col(default="html")
    path: Mapped[str] = col(default="")
    sha256: Mapped[str] = col(default="")
    options_json: Mapped[str] = col(Text, default="{}")

class AISuggestion(CaseEntity, Base):
    __tablename__ = "ai_suggestions"
    kind: Mapped[str] = col()  # finding | relationship | timeline | entity | summary
    payload: Mapped[str] = col(Text, default="{}")
    origin: Mapped[str] = col(default="rules")  # rules | ollama:<model>
    status: Mapped[str] = col(default="Pending")  # Pending | Approved | Rejected

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = col(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = col(default=now, index=True)
    user_id: Mapped[str | None] = col(nullable=True)
    username: Mapped[str] = col(default="system")
    action: Mapped[str] = col(index=True)
    entity_type: Mapped[str] = col(default="")
    entity_ref: Mapped[str] = col(default="", index=True)
    case_id: Mapped[str | None] = col(nullable=True, index=True)
    detail: Mapped[str] = col(Text, default="{}")
    prev_hash: Mapped[str] = col(default="")
    hash: Mapped[str] = col(default="")

# Audit records are append-only: block UPDATE/DELETE at the database level.
for _op in ("UPDATE", "DELETE"):
    event.listen(AuditLog.__table__, "after_create", DDL(
        f"CREATE TRIGGER IF NOT EXISTS audit_no_{_op.lower()} BEFORE {_op} ON audit_logs "
        f"BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;"))

# Full-text style search is done with LIKE over indexed columns (exact substring matching preserved).
