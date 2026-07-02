"""
API data contracts (Phase 2).

Request/response Pydantic models mirroring the exact contracts in docs/phase-2.md.
`ClinicalFact` (memory/schema.py) is reused directly wherever a fact is returned,
so the API surface and the engine share one fact shape.
"""

from __future__ import annotations

import datetime
from datetime import date
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from app.memory.schema import ClinicalFact

Mode = Literal["total_recall", "naive"]


# --- /seed ----------------------------------------------------------------
class SeedRequest(BaseModel):
    patient_id: str = "P001"


class HeldBack(BaseModel):
    label: str
    text: str


class SeedResponse(BaseModel):
    patient_id: str
    seeded: List[ClinicalFact]
    held_back: List[HeldBack]


# --- /ingest --------------------------------------------------------------
class IngestRequest(BaseModel):
    patient_id: str = "P001"
    text: str = ""
    structured: Optional[dict] = None


class IngestResponse(BaseModel):
    fact: ClinicalFact
    classification: str
    target_fact_id: Optional[str] = None
    reason: str = ""
    healed: bool = False
    actions: List[str] = Field(default_factory=list)


# --- /reset ---------------------------------------------------------------
class ResetRequest(BaseModel):
    patient_id: str = "P001"


class ResetResponse(BaseModel):
    ok: bool = True
    patient_id: str


# --- /forget (entered-in-error retraction) --------------------------------
class ForgetRequest(BaseModel):
    patient_id: str = "P001"
    fact_id: str
    reason: str = "entered in error"


class ForgetResponse(BaseModel):
    fact: ClinicalFact                       # the retracted fact (audit kept)
    restored: Optional[ClinicalFact] = None  # prior fact made active again, if any
    forgotten: bool = False                  # whether Cognee dropped the assertion
    cognee: dict = Field(default_factory=dict)  # Cognee deletion summary


# --- /ask -----------------------------------------------------------------
class AskRequest(BaseModel):
    patient_id: str = "P001"
    question: str
    mode: Mode = "total_recall"
    as_of: Optional[date] = None


class AskResponse(BaseModel):
    answer: str
    mode: Mode
    search_type: str
    raw: Any = None


# --- /graph (ledger fact-timeline) ----------------------------------------
class GraphNode(BaseModel):
    id: str
    label: str
    subject: str
    value: str
    status: str               # active | superseded (computed at as_of)
    valid_from: date
    valid_to: Optional[date] = None
    source: str = "unknown"
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    # visualization layer (additive)
    category: str = "Other"          # FHIR resource_type -> swimlane (Allergy/Medication/...)
    confidence: float = 1.0
    ontology_valid: Optional[bool] = None
    kind: Literal["fact", "relative", "risk"] = "fact"


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["SUPERSEDED_BY", "SAME_SUBJECT", "RELATED_TO", "RISK"]
    label: str = ""


class GraphResponse(BaseModel):
    as_of: date
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# --- /graph/cognee (raw Cognee KG) ----------------------------------------
class CogneeGraphResponse(BaseModel):
    nodes: List[dict]
    edges: List[dict]


# --- /why -----------------------------------------------------------------
class WhyResponse(BaseModel):
    fact: ClinicalFact
    superseded_by: Optional[ClinicalFact] = None
    reason: str = ""
    source: str = ""
    # Field name `date` would shadow the `date` type in this class namespace, so
    # qualify it as `datetime.date` to keep the annotation correct.
    date: Optional[datetime.date] = None
    chain: List[ClinicalFact] = Field(default_factory=list)


# --- /health --------------------------------------------------------------
class HealthResponse(BaseModel):
    ok: bool
    cognee: str
    ledger: str


# --- /patients ------------------------------------------------------------
class Patient(BaseModel):
    patient_id: str
    mrn: str
    name: str
    dob: str
    sex: str = ""
    summary: str = ""


class PatientsResponse(BaseModel):
    patients: List[Patient]


# --- /patients/{id}/documents ---------------------------------------------
class DocumentSummary(BaseModel):
    doc_id: str
    date: date
    type: str
    author: str
    title: str
    entered_in_error: bool = False
    ingested: bool = False
    fact_id: Optional[str] = None   # ledger fact id once ingested


class DocumentsResponse(BaseModel):
    patient_id: str
    documents: List[DocumentSummary]


class DocumentDetail(DocumentSummary):
    patient_id: str
    text: str


# --- /ingest_document -----------------------------------------------------
class IngestDocumentRequest(BaseModel):
    patient_id: str
    doc_id: str


class IngestDocumentResponse(BaseModel):
    doc_id: str
    facts: List[ClinicalFact]
    classification: str
    healed: bool = False
    reason: str = ""
    actions: List[str] = Field(default_factory=list)


# --- create patient -------------------------------------------------------
class CreatePatientRequest(BaseModel):
    name: str
    dob: str = ""
    sex: str = ""
    mrn: str = ""
