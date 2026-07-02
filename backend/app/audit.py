"""
Real audit trail (CLINICAL_COPILOT_PLAN §7).

This is the one part of the identity/access layer that is NOT simulated: an
append-only SQLite log of every clinically-meaningful action — who (doctor),
when (ts), which patient, what action, the decision/outcome, and the evidence
(fact/document ids) behind it. It is the "real doctor system" credibility anchor
on otherwise synthetic data.

Append-only by construction: there is `log()` and there are read queries; there
is deliberately no update/delete API. A tamper would have to go around this
module, and the row order (autoincrement id + UTC ts) preserves sequence.

DB: C:\\cg\\audit.db (short Windows path, same root as the ledger).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

_DB_PATH = os.environ.get("AUDIT_DB", r"C:\cg\audit.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


class AuditEntry(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)  # autoincrement = order
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), index=True)
    doctor: str = Field(index=True)
    patient_id: Optional[str] = Field(default=None, index=True)
    action: str = Field(index=True)  # recall | order_check | ingest | forget | approve | resolve | access_denied
    decision: str = ""               # outcome/summary (e.g. "critical: penicillin allergy")
    evidence_ids: str = "[]"         # JSON list of fact/document ids behind the action


def init() -> None:
    SQLModel.metadata.create_all(_engine)


def log(
    doctor: str,
    action: str,
    patient_id: Optional[str] = None,
    decision: str = "",
    evidence_ids: Optional[List[str]] = None,
) -> None:
    """Append one audit row. Best-effort: auditing must never break the request it
    records, but a failure is surfaced to stderr rather than silently swallowed."""
    entry = AuditEntry(
        doctor=doctor or "unknown",
        patient_id=patient_id,
        action=action,
        decision=(decision or "")[:500],
        evidence_ids=json.dumps(evidence_ids or []),
    )
    try:
        with Session(_engine) as s:
            s.add(entry)
            s.commit()
    except Exception as exc:  # pragma: no cover - observability, not control flow
        import sys

        print(f"[audit] failed to log {action}: {exc}", file=sys.stderr)


def recent(patient_id: Optional[str] = None, limit: int = 100) -> List[dict]:
    """Read the log newest-first, optionally scoped to one patient."""
    with Session(_engine) as s:
        q = select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)  # type: ignore[attr-defined]
        if patient_id:
            q = (
                select(AuditEntry)
                .where(AuditEntry.patient_id == patient_id)
                .order_by(AuditEntry.id.desc())  # type: ignore[attr-defined]
                .limit(limit)
            )
        rows = s.exec(q).all()
    return [
        {
            "id": r.id,
            "ts": r.ts,
            "doctor": r.doctor,
            "patient_id": r.patient_id,
            "action": r.action,
            "decision": r.decision,
            "evidence_ids": json.loads(r.evidence_ids or "[]"),
        }
        for r in rows
    ]
