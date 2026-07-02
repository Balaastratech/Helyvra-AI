"""
Identity, access & audit surface (CLINICAL_COPILOT_PLAN §7).

  GET  /doctors                       -> login picker roster (simulated)
  GET  /patients/resolve?query=&doctor_id=
                                      -> resolve a name/MRN to ONE patient, or a
                                         disambiguation list when it's ambiguous
                                         (the "no confirmation = no answer" safety
                                         story, made visible). Scoped to the
                                         doctor's access list when a doctor is given.
  GET  /audit?patient_id=             -> read the real append-only audit trail.

The resolver never silently picks a patient when more than one matches — it
returns the candidates for explicit selection (§3.4). Every resolve is audited.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app import audit, auth
from app.memory import records

router = APIRouter(tags=["access"])


class Doctor(BaseModel):
    doctor_id: str
    name: str
    specialty: str = ""
    role: str = "doctor"


class PatientMatch(BaseModel):
    patient_id: str
    name: str
    mrn: str
    dob: str = ""
    sex: str = ""
    age: Optional[int] = None
    last_visit: Optional[str] = None
    summary: str = ""


class ResolveResponse(BaseModel):
    query: str
    resolved: Optional[PatientMatch] = None  # set only when exactly one match
    candidates: List[PatientMatch] = []      # >1 match -> disambiguation list


class AuditResponse(BaseModel):
    entries: List[dict]


def _age(dob: str) -> Optional[int]:
    try:
        d = date.fromisoformat(dob)
    except (ValueError, TypeError):
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def _last_visit(patient_id: str) -> Optional[str]:
    docs = records.list_documents(patient_id)
    if not docs:
        return None
    return max(str(d["date"]) for d in docs)


def _match(p: dict) -> PatientMatch:
    return PatientMatch(
        patient_id=p["patient_id"], name=p.get("name", ""), mrn=p.get("mrn", ""),
        dob=p.get("dob", ""), sex=p.get("sex", ""), age=_age(p.get("dob", "")),
        last_visit=_last_visit(p["patient_id"]), summary=p.get("summary", ""),
    )


@router.get("/doctors", response_model=List[Doctor])
def doctors() -> List[Doctor]:
    return [Doctor(**d) for d in auth.list_doctors()]


@router.get("/patients/resolve", response_model=ResolveResponse)
def resolve(
    query: str = Query(..., min_length=1),
    doctor_id: Optional[str] = Query(None),
) -> ResolveResponse:
    """Match a free-text query (name / MRN) to the patients this doctor may see."""
    q = query.strip().lower()
    pool = records.list_patients()
    if doctor_id:  # hard access scoping — never resolve outside the doctor's list
        allowed = set(auth.allowed_patients(doctor_id))
        pool = [p for p in pool if p["patient_id"] in allowed]

    matches = [
        p for p in pool
        if q in p.get("name", "").lower()
        or q in p.get("mrn", "").lower()
        or q == p.get("patient_id", "").lower()
    ]

    audit.log(
        doctor_id or "unknown", "resolve",
        decision=f"query '{query}' -> {len(matches)} match(es)",
        evidence_ids=[p["patient_id"] for p in matches],
    )

    resolved = _match(matches[0]) if len(matches) == 1 else None
    candidates = [_match(p) for p in matches] if len(matches) != 1 else []
    return ResolveResponse(query=query, resolved=resolved, candidates=candidates)


@router.get("/audit", response_model=AuditResponse)
def read_audit(
    patient_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
) -> AuditResponse:
    """Read the real, append-only audit trail (newest first)."""
    return AuditResponse(entries=audit.recent(patient_id=patient_id, limit=limit))
