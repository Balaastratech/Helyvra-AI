"""
Fact ledger — app-side authoritative status store (SQLModel over SQLite).

This is the rock-solid backbone of the demo: every `ClinicalFact` and its
lifecycle (active / superseded / contested, valid_from/to, supersession chain,
reason) lives here deterministically. Cognee still does the semantic + temporal
heavy lifting, but the ledger is what drives the heal visualization, the
time-scrubber, and `/why` in later phases.

DB location: C:\\cg\\ledger.db (short Windows path, same root as Cognee storage).
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.memory.schema import ClinicalFact

# --- DB engine (short Windows path) ---------------------------------------
_DB_PATH = os.environ.get("LEDGER_DB", r"C:\cg\ledger.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


class FactRecord(SQLModel, table=True):
    """SQLModel table row. Mirrors `ClinicalFact` 1:1."""

    __tablename__ = "facts"

    id: str = Field(primary_key=True)
    patient_id: str = Field(index=True)
    subject: str = Field(index=True)
    predicate: str
    value: str
    valid_from: date
    valid_to: Optional[date] = None
    source: str = "unknown"
    status: str = "active"
    superseded_by: Optional[str] = None
    confidence: float = 1.0
    reason: Optional[str] = None
    raw_text: str = ""
    cognee_data_id: Optional[str] = None
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    resource_type: Optional[str] = None
    page: Optional[int] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    ontology_valid: Optional[bool] = None

    @classmethod
    def from_fact(cls, f: ClinicalFact) -> "FactRecord":
        # `label` is a computed field on ClinicalFact (not a column) — drop any
        # keys that aren't real FactRecord columns.
        data = {k: v for k, v in f.model_dump().items() if k in cls.model_fields}
        return cls(**data)

    def to_fact(self) -> ClinicalFact:
        data = self.model_dump()
        if data.get("attributes") is None:  # NULL on rows created before this column
            data["attributes"] = {}
        return ClinicalFact(**data)


# --- lifecycle ------------------------------------------------------------
def init() -> None:
    """Create tables if missing, then add any newly-introduced columns."""
    SQLModel.metadata.create_all(_engine)
    _migrate()


def _migrate() -> None:
    """
    Lightweight additive migration: SQLModel.create_all never ALTERs an existing
    table, so when new ClinicalFact columns are added we patch the live `facts`
    table here (SQLite ADD COLUMN, nullable) instead of forcing a DB wipe.
    """
    with _engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(facts)")}
        coltypes = {
            "source_document": "TEXT", "document_title": "TEXT", "cognee_data_id": "TEXT",
            "resource_type": "TEXT", "page": "INTEGER", "attributes": "JSON",
            "ontology_valid": "BOOLEAN",
        }
        for name, sqltype in coltypes.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE facts ADD COLUMN {name} {sqltype}")
        conn.commit()


def reset() -> None:
    """Wipe ALL facts (fresh demo). Keeps schema."""
    init()
    with Session(_engine) as s:
        s.exec(sa_delete(FactRecord))
        s.commit()


# --- CRUD -----------------------------------------------------------------
def add(fact: ClinicalFact) -> ClinicalFact:
    """Insert a brand-new fact."""
    with Session(_engine) as s:
        s.add(FactRecord.from_fact(fact))
        s.commit()
    return fact


def upsert(*facts: ClinicalFact) -> None:
    """Insert-or-update one or more facts (used by reconcile nodes)."""
    with Session(_engine) as s:
        for f in facts:
            existing = s.get(FactRecord, f.id)
            if existing is None:
                s.add(FactRecord.from_fact(f))
            else:
                for k, v in f.model_dump().items():
                    if k in FactRecord.model_fields:  # skip computed `label`
                        setattr(existing, k, v)
                s.add(existing)
        s.commit()


def get(fact_id: str) -> Optional[ClinicalFact]:
    with Session(_engine) as s:
        row = s.get(FactRecord, fact_id)
        return row.to_fact() if row else None


# --- queries --------------------------------------------------------------
def query_active(patient_id: str, subject: str) -> List[ClinicalFact]:
    """Active facts for a patient scoped to one subject (the judge candidate set)."""
    with Session(_engine) as s:
        rows = s.exec(
            select(FactRecord)
            .where(FactRecord.patient_id == patient_id)
            .where(FactRecord.subject == subject)
            .where(FactRecord.status == "active")
            .order_by(FactRecord.valid_from)
        ).all()
        return [r.to_fact() for r in rows]


def query_all(patient_id: str, subject: str) -> List[ClinicalFact]:
    """ALL facts (any status) for a patient+subject, oldest first. Used by answer synthesis."""
    with Session(_engine) as s:
        rows = s.exec(
            select(FactRecord)
            .where(FactRecord.patient_id == patient_id)
            .where(FactRecord.subject == subject)
            .order_by(FactRecord.valid_from)
        ).all()
        return [r.to_fact() for r in rows]


def all(patient_id: str) -> List[ClinicalFact]:
    """Every fact (any status) for a patient, oldest first."""
    with Session(_engine) as s:
        rows = s.exec(
            select(FactRecord)
            .where(FactRecord.patient_id == patient_id)
            .order_by(FactRecord.valid_from)
        ).all()
        return [r.to_fact() for r in rows]


def snapshot(patient_id: str, as_of: date) -> List[ClinicalFact]:
    """
    What was true at a point in time (the time-scrubber query):
    facts whose validity window contains `as_of`.
    """
    out: List[ClinicalFact] = []
    with Session(_engine) as s:
        rows = s.exec(
            select(FactRecord).where(FactRecord.patient_id == patient_id)
        ).all()
        for r in rows:
            if r.status == "retracted":
                continue  # entered-in-error facts were never "true at" any date
            if r.valid_from <= as_of and (r.valid_to is None or as_of < r.valid_to):
                out.append(r.to_fact())
    out.sort(key=lambda f: f.valid_from)
    return out


def chain(fact_id: str) -> List[ClinicalFact]:
    """Follow the `superseded_by` links from `fact_id` forward to current truth."""
    out: List[ClinicalFact] = []
    cur = get(fact_id)
    seen = set()
    while cur and cur.id not in seen:
        out.append(cur)
        seen.add(cur.id)
        cur = get(cur.superseded_by) if cur.superseded_by else None
    return out


def retract(fact_id: str, reason: str):
    """
    Retract a fact that was ENTERED IN ERROR (never true).

    Marks it `status="retracted"` (kept for audit, excluded from current truth and
    snapshots) and, if it had superseded an older fact, restores that older fact to
    active (the supersession was based on a bogus fact). Returns
    `(retracted: ClinicalFact|None, restored: ClinicalFact|None)`.
    """
    fact = get(fact_id)
    if fact is None:
        return None, None

    restored: Optional[ClinicalFact] = None
    # If this fact superseded an older one, that older fact becomes current again.
    with Session(_engine) as s:
        prior = s.exec(
            select(FactRecord).where(FactRecord.superseded_by == fact_id)
        ).first()
        if prior is not None:
            prior.status = "active"
            prior.valid_to = None
            prior.superseded_by = None
            prior.reason = f"restored: superseding fact retracted ({reason})"
            s.add(prior)
            s.commit()
            restored = prior.to_fact()

    fact.status = "retracted"
    fact.reason = reason
    upsert(fact)
    return fact, restored
