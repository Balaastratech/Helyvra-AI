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
