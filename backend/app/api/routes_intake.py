"""
POST /intake — universal document upload.

Drop any file (PDF, FHIR JSON, text) → the system figures out which patient it
belongs to, creates a new chart if needed, extracts facts, and runs them through
the self-healing engine. No manual patient selection required.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.intake import pipeline
from app.memory.schema import ClinicalFact

router = APIRouter(tags=["intake"])


class IntakeResponse(BaseModel):
    patient_id: str
    patient_name: str
    doc_id: str
    facts: List[ClinicalFact]
    classification: str
    healed: bool = False
    reason: str = ""
    actions: List[str] = []
    created_patient: bool = False


@router.post("/intake", response_model=IntakeResponse)
async def intake(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
) -> IntakeResponse:
    """
    Universal intake: upload any clinical document.

    - If patient_id is provided, the document is attached to that patient.
    - If not, the system extracts patient identity from the document and
      auto-resolves to an existing chart or creates a new one.

    Supported formats: PDF (.pdf), FHIR Bundle (.json), free text (.txt/.md).
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(422, "Uploaded file is empty.")

    filename = file.filename or "uploaded.txt"

    try:
        result = await pipeline.run(
            raw_bytes=raw_bytes,
            filename=filename,
            patient_id_hint=patient_id or None,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Intake failed: {type(exc).__name__}: {exc}")

    return IntakeResponse(
        patient_id=result.patient_id,
        patient_name=result.patient_name,
        doc_id=result.doc_id,
        facts=result.facts,
        classification=result.classification,
        healed=result.healed,
        reason=result.reason,
        actions=result.actions,
        created_patient=result.created_patient,
    )


class BatchIntakeItem(BaseModel):
    filename: str
    ok: bool = True
    error: str = ""
    patient_id: str = ""
    patient_name: str = ""
    doc_id: str = ""
    facts: List[ClinicalFact] = []
    classification: str = "NEW"
    healed: bool = False
    reason: str = ""
    actions: List[str] = []
    created_patient: bool = False


class BatchIntakeResponse(BaseModel):
    items: List[BatchIntakeItem]


@router.post("/intake/batch", response_model=BatchIntakeResponse)
async def intake_batch(
    files: List[UploadFile] = File(...),
    patient_id: Optional[str] = Form(None),
) -> BatchIntakeResponse:
    """
    Multi-file drop, ingested as ONE batch: every file still runs its own
    extraction and per-fact reconciliation, but the expensive Cognee graph
    rebuild happens ONCE for the whole drop instead of once per file — cognify
    cost scales with the patient's total fact count, so doing it N times for
    an N-file drop was the real remaining slowness (see pipeline.run_batch).

    The first file to resolve a patient pins the rest to that same chart,
    exactly like the single-file /intake loop this replaces.
    """
    raw_files: List[tuple[bytes, str]] = []
    for f in files:
        raw = await f.read()
        if raw:
            raw_files.append((raw, f.filename or "uploaded.txt"))
    if not raw_files:
        raise HTTPException(422, "No non-empty files to ingest.")

    results = await pipeline.run_batch(raw_files, patient_id_hint=patient_id or None)
    return BatchIntakeResponse(items=[
        BatchIntakeItem(
            filename=r.filename, ok=r.ok, error=r.error,
            patient_id=r.patient_id, patient_name=r.patient_name, doc_id=r.doc_id,
            facts=r.facts, classification=r.classification, healed=r.healed,
            reason=r.reason, actions=r.actions, created_patient=r.created_patient,
        )
        for r in results
    ])
