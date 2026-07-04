"""
POST /intake — universal document upload.

Drop any file (PDF, FHIR JSON, text) → the system figures out which patient it
belongs to, creates a new chart if needed, extracts facts, and runs them through
the self-healing engine. No manual patient selection required.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.intake import pipeline, upload_hashes
from app.memory import records
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
    # Dedup: set when the exact same file was already uploaded (and force=False).
    # No extraction/engine run happened; `duplicate_of` points at the prior doc.
    duplicate: bool = False
    duplicate_of: Optional[dict] = None


def _dup_info(hit: dict) -> dict:
    """Shape the stored hash record into the {doc_id, patient_id, patient_name,
    uploaded_at} the UI shows in its 'already uploaded' confirm."""
    p = records.get_patient(hit.get("patient_id", ""))
    return {
        "doc_id": hit.get("doc_id", ""),
        "patient_id": hit.get("patient_id", ""),
        "patient_name": p["name"] if p else hit.get("patient_id", ""),
        "uploaded_at": hit.get("uploaded_at", ""),
    }


def _duplicate_hit(file_hash: str, force: bool) -> Optional[dict]:
    """A prior upload of this exact file whose patient still exists, unless the
    caller explicitly asked to re-process (force)."""
    if force:
        return None
    hit = upload_hashes.lookup(file_hash)
    if hit and records.get_patient(hit.get("patient_id", "")):
        return hit
    return None


@router.post("/intake", response_model=IntakeResponse)
async def intake(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    force: bool = Form(False),
) -> IntakeResponse:
    """
    Universal intake: upload any clinical document.

    - If patient_id is provided, the document is attached to that patient.
    - If not, the system extracts patient identity from the document and
      auto-resolves to an existing chart or creates a new one.

    Re-uploading the exact same file returns `duplicate: true` (no extraction,
    no engine run) unless `force=true`.

    Supported formats: PDF, FHIR JSON, CSV, text, and images (jpg/png/webp/heic).
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(422, "Uploaded file is empty.")

    filename = file.filename or "uploaded.txt"
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    hit = _duplicate_hit(file_hash, force)
    if hit:
        info = _dup_info(hit)
        return IntakeResponse(
            patient_id=info["patient_id"], patient_name=info["patient_name"],
            doc_id=info["doc_id"], facts=[], classification="DUPLICATE",
            duplicate=True, duplicate_of=info,
        )

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

    upload_hashes.record(file_hash, result.doc_id, result.patient_id, filename)

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
    duplicate: bool = False
    duplicate_of: Optional[dict] = None


class BatchIntakeResponse(BaseModel):
    items: List[BatchIntakeItem]


@router.post("/intake/batch", response_model=BatchIntakeResponse)
async def intake_batch(
    files: List[UploadFile] = File(...),
    patient_id: Optional[str] = Form(None),
    force: bool = Form(False),
) -> BatchIntakeResponse:
    """
    Multi-file drop, ingested as ONE batch: every file still runs its own
    extraction and per-fact reconciliation, but the expensive Cognee graph
    rebuild happens ONCE for the whole drop instead of once per file — cognify
    cost scales with the patient's total fact count, so doing it N times for
    an N-file drop was the real remaining slowness (see pipeline.run_batch).

    The first file to resolve a patient pins the rest to that same chart,
    exactly like the single-file /intake loop this replaces.

    Files whose exact bytes were already uploaded are reported as
    `duplicate: true` and skipped (no extraction/engine run) unless force=true.
    """
    raw_files: List[tuple[bytes, str]] = []
    for f in files:
        raw = await f.read()
        if raw:
            raw_files.append((raw, f.filename or "uploaded.txt"))
    if not raw_files:
        raise HTTPException(422, "No non-empty files to ingest.")

    # Split the drop into already-seen duplicates (skipped) and files to run.
    items: List[BatchIntakeItem] = []
    to_process: List[tuple[bytes, str]] = []
    to_process_hashes: List[str] = []  # parallel to to_process
    for raw, fn in raw_files:
        file_hash = hashlib.sha256(raw).hexdigest()
        hit = _duplicate_hit(file_hash, force)
        if hit:
            info = _dup_info(hit)
            items.append(BatchIntakeItem(
                filename=fn, ok=True, duplicate=True, duplicate_of=info,
                patient_id=info["patient_id"], patient_name=info["patient_name"],
                doc_id=info["doc_id"], classification="DUPLICATE",
            ))
        else:
            to_process.append((raw, fn))
            to_process_hashes.append(file_hash)

    if to_process:
        results = await pipeline.run_batch(to_process, patient_id_hint=patient_id or None)
        for file_hash, r in zip(to_process_hashes, results):
            if r.ok and r.doc_id:
                upload_hashes.record(file_hash, r.doc_id, r.patient_id, r.filename)
            items.append(BatchIntakeItem(
                filename=r.filename, ok=r.ok, error=r.error,
                patient_id=r.patient_id, patient_name=r.patient_name, doc_id=r.doc_id,
                facts=r.facts, classification=r.classification, healed=r.healed,
                reason=r.reason, actions=r.actions, created_patient=r.created_patient,
            ))

    return BatchIntakeResponse(items=items)
