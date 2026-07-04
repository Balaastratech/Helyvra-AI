"""
Patients + documents: the real-application surface.

Flow the UI drives:
  GET /patients                       -> pick a chart (name + MRN)
  GET /patients/{id}/documents        -> the records inbox (ingested? which fact?)
  GET /documents/{doc_id}             -> read the source file
  POST /ingest_document {patient,doc} -> push the document's assertion through the
                                         self-healing engine; the fact links back
                                         to the source file (source_document).
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.dto import (
    CreatePatientRequest,
    DocumentDetail,
    DocumentSummary,
    DocumentsResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    Patient,
    PatientsResponse,
)
from app.checks import engine as checks_engine
from app.checks.cards import Card
from app.engine import extract, service
from app.memory import cognee_client, ledger, records
from app.memory.schema import ClinicalFact
from datetime import date as _date
from pydantic import BaseModel

router = APIRouter(tags=["patients"])


@router.get("/patients", response_model=PatientsResponse)
def patients() -> PatientsResponse:
    return PatientsResponse(patients=[Patient(**p) for p in records.list_patients()])


@router.post("/patients", response_model=Patient)
def create_patient(req: CreatePatientRequest) -> Patient:
    """Create a new chart so a user can bring their own patient + records."""
    if not req.name.strip():
        raise HTTPException(422, "patient name is required.")
    return Patient(**records.add_patient(req.name, req.dob, req.sex, req.mrn))


# --- pre-visit brief (CLINICAL_COPILOT_PLAN §6 / UX §3.5) ------------------
class BriefItem(BaseModel):
    fact_id: str
    label: str
    value: str
    date: str
    status: str
    resource_type: Optional[str] = None
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    page: Optional[int] = None
    attributes: dict = {}


class BriefResponse(BaseModel):
    patient: Patient
    age: Optional[int] = None
    fact_count: int = 0
    allergy_badge: Optional[str] = None   # active allergy substance(s) for the red chip
    risk_badge: bool = False              # any warning/critical open-check card
    groups: dict = {}                     # resource_type -> [BriefItem]
    cards: List[Card] = []                # Top not-to-miss cards (severity-capped)


_GROUP_ORDER = [
    ("Condition", "conditions"), ("Medication", "medications"),
    ("Allergy", "allergies"), ("LabResult", "labs"),
    ("FamilyHistory", "family"), ("Lifestyle", "lifestyle"),
    ("Vital", "vitals"), ("Procedure", "procedures"),
]


def _age_from(dob: str) -> Optional[int]:
    try:
        d = _date.fromisoformat(dob)
    except (ValueError, TypeError):
        return None
    t = _date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def _brief_item(f: ClinicalFact) -> BriefItem:
    return BriefItem(
        fact_id=f.id, label=f.label, value=f.value,
        date=f.valid_from.isoformat(), status=f.status,
        resource_type=f.resource_type, source_document=f.source_document,
        document_title=f.document_title, page=f.page, attributes=f.attributes or {},
    )


@router.get("/patients/{patient_id}/brief", response_model=BriefResponse)
def brief(patient_id: str) -> BriefResponse:
    """The pre-visit brief: a grouped chart summary + the Top not-to-miss cards
    from the check engine. Empty groups + no cards is the honest state before any
    record is uploaded."""
    patient = records.get_patient(patient_id)
    if patient is None:
        raise HTTPException(404, f"unknown patient: {patient_id}")

    facts = [f for f in ledger.all(patient_id) if f.status != "retracted"]
    groups: dict = {key: [] for _, key in _GROUP_ORDER}
    for f in facts:
        rt = f.resource_type or "Note"
        key = next((k for r, k in _GROUP_ORDER if r == rt), None)
        if key:
            groups[key].append(_brief_item(f).model_dump())

    active_allergies = [
        f.attributes.get("substance") or f.value
        for f in facts
        if f.resource_type == "Allergy" and f.status == "active"
        and f.predicate.strip().lower() != "cleared"
    ]
    cards = checks_engine.run_open_checks(patient_id)
    risk = any(c.indicator in ("warning", "critical") for c in cards)

    return BriefResponse(
        patient=Patient(**patient),
        age=_age_from(patient.get("dob", "")),
        fact_count=len(facts),
        allergy_badge=", ".join(sorted(set(a for a in active_allergies if a))) or None,
        risk_badge=risk,
        groups=groups,
        cards=cards,
    )


@router.get("/patients/{patient_id}/documents", response_model=DocumentsResponse)
def documents(patient_id: str) -> DocumentsResponse:
    if records.get_patient(patient_id) is None:
        raise HTTPException(404, f"unknown patient: {patient_id}")
    ingested = records.ingested_doc_ids(ledger.all(patient_id))
    out = [
        DocumentSummary(
            doc_id=d["doc_id"],
            date=d["date"],
            type=d["type"],
            author=d["author"],
            title=d["title"],
            entered_in_error=bool(d.get("entered_in_error")),
            ingested=d["doc_id"] in ingested,
            fact_id=ingested.get(d["doc_id"]),
        )
        for d in records.list_documents(patient_id)
    ]
    return DocumentsResponse(patient_id=patient_id, documents=out)


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def document(doc_id: str) -> DocumentDetail:
    d = records.get_document(doc_id)
    if d is None:
        raise HTTPException(404, f"unknown document: {doc_id}")
    ingested = records.ingested_doc_ids(ledger.all(d["patient_id"]))
    return DocumentDetail(
        patient_id=d["patient_id"],
        doc_id=d["doc_id"],
        date=d["date"],
        type=d["type"],
        author=d["author"],
        title=d["title"],
        text=d.get("text", ""),
        entered_in_error=bool(d.get("entered_in_error")),
        ingested=d["doc_id"] in ingested,
        fact_id=ingested.get(d["doc_id"]),
    )


@router.post("/ingest_document", response_model=IngestDocumentResponse)
async def ingest_document(req: IngestDocumentRequest) -> IngestDocumentResponse:
    doc = records.get_document(req.doc_id)
    if doc is None or doc["patient_id"] != req.patient_id:
        raise HTTPException(404, f"document not found for patient: {req.doc_id}")

    # Idempotent: if already ingested, return the existing fact(s).
    already = records.ingested_doc_ids(ledger.all(req.patient_id))
    if req.doc_id in already:
        existing = [f for f in ledger.all(req.patient_id) if f.source_document == req.doc_id]
        return IngestDocumentResponse(
            doc_id=req.doc_id, facts=existing, classification="ALREADY",
            reason="Document already in memory.",
        )

    built: list[ClinicalFact] = records.facts_from_document(req.patient_id, doc)
    if not built:
        raise HTTPException(422, "document asserts nothing to ingest.")
    return await _run_ingest(req.patient_id, doc)


# --- shared ingestion + upload --------------------------------------------
async def _run_ingest(
    patient_id: str, doc: dict, cognify_after: bool = True,
) -> IngestDocumentResponse:
    """Push a document's assertion(s) through the self-healing engine.

    Facts run through run_facts() (perf: ONE Cognee graph build for the whole
    document, not one per fact — each fact still gets its own full
    recall->judge->reconcile->ledger-write, so reconciliation is unaffected).

    `cognify_after=False` (set by a multi-file batch caller — see
    pipeline.run_batch) skips even that one per-document rebuild, deferring
    it to the caller so an N-file drop pays the growing cognify cost once,
    not N times.
    """
    built = records.facts_from_document(patient_id, doc)
    states = await service.run_facts(
        patient_id, built, cognee_sync=True, cognify_after=cognify_after,
    )

    classification, reason, actions, final = "NEW", "", [], []
    healed = False
    for fact, state in zip(built, states):
        cls = state.get("classification", "NEW")
        classification = cls
        reason = state.get("reason", "") or reason
        actions += list(state.get("actions") or [])
        if cls in ("SUPERSEDES", "CONTRADICTS"):
            healed = True
        final.append(ledger.get(fact.id) or fact)

    if not healed:
        # Naive villain only ever sees documents with NO corrections in them. A
        # fact's raw_text is the WHOLE source document (shared across every
        # fact extracted from it), so gating per-fact would leak a correction
        # into naive via any co-extracted NEW fact from the same document —
        # withhold the entire document instead.
        for fact in built:
            await cognee_client.add_naive(fact)
        if cognify_after:
            await cognee_client.cognify_naive(patient_id)

    return IngestDocumentResponse(
        doc_id=doc["doc_id"], facts=final, classification=classification,
        healed=healed, reason=reason, actions=actions,
    )


@router.post("/upload", response_model=IngestDocumentResponse)
async def upload(patient_id: str = Form(...), file: UploadFile = File(...)) -> IngestDocumentResponse:
    """
    Upload a real clinical record (.txt / .md / .json), extract the fact (Vertex
    for free text; structured if the file is JSON with `asserts`), store the file,
    and ingest it. The resulting fact links back to the uploaded document.
    """
    if records.get_patient(patient_id) is None:
        raise HTTPException(404, f"unknown patient: {patient_id}")

    raw = (await file.read()).decode("utf-8", errors="replace").strip()
    if not raw:
        raise HTTPException(422, "uploaded file is empty.")

    filename = file.filename or "uploaded.txt"
    doc_id = f"UP-{patient_id}-{uuid.uuid4().hex[:8]}"

    # Structured JSON upload (has asserts) -> use directly; else extract via LLM.
    asserts: list[dict] = []
    doc_date = date.today().isoformat()
    author = "uploaded"
    if filename.lower().endswith(".json"):
        try:
            payload = json.loads(raw)
            asserts = payload.get("asserts", [])
            doc_date = payload.get("date", doc_date)
            author = payload.get("author", author)
        except Exception:
            raise HTTPException(422, "invalid JSON document.")
    if not asserts:
        try:
            f = extract.extract_fact(patient_id, raw)
        except Exception as exc:
            raise HTTPException(422, f"could not extract a clinical fact: {exc}")
        asserts = [{"subject": f.subject, "predicate": f.predicate, "value": f.value}]
        doc_date = f.valid_from.isoformat()
        author = f.source

    doc = {
        "doc_id": doc_id,
        "date": doc_date,
        "type": "Uploaded record",
        "author": author,
        "title": filename,
        "text": raw,
        "uploaded": True,
        "asserts": asserts,
    }
    records.save_upload(patient_id, doc)
    return await _run_ingest(patient_id, {**doc, "patient_id": patient_id})
