"""
Canonical clinical fact model (Phase 1).

`ClinicalFact` is the single source of truth that flows through the whole engine:
recall -> judge -> reconcile -> persist. It is a *pure Pydantic* model (no DB
coupling) so the judge, the LangGraph state, and the runner can all pass it
around freely. The ledger (ledger.py) owns its own SQLModel table and converts
to/from this model at the boundary.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, computed_field, model_validator


# FHIR resource discriminator. The engine still flows on subject/predicate/value;
# resource_type is the clinical-copilot layer's typed view, defaulted from subject
# so every existing fact becomes typed for free (CLINICAL_COPILOT_PLAN §2).
ResourceType = Literal[
    "Allergy", "Condition", "Medication", "LabResult", "Vital",
    "FamilyHistory", "Lifestyle", "Procedure", "Immunization", "SourceDoc",
]

# subject (the engine's free-text category) -> FHIR resource_type.
RESOURCE_BY_SUBJECT: Dict[str, ResourceType] = {
    "allergy": "Allergy",
    "diagnosis": "Condition",
    "condition": "Condition",
    "medication": "Medication",
    "lab": "LabResult",
    "labresult": "LabResult",
    "vital": "Vital",
    "family": "FamilyHistory",
    "family_history": "FamilyHistory",
    "lifestyle": "Lifestyle",
    "procedure": "Procedure",
    "immunization": "Immunization",
    "document": "SourceDoc",
}


def human_label(subject: str, predicate: str, value: str) -> str:
    """Plain-English label for a fact (predicate-aware), so the diagnosed vs
    cleared allergy don't both render as 'allergy: penicillin'."""
    s, p = subject.lower(), predicate.lower()
    if s == "allergy":
        return f"{value.title()} allergy cleared" if p == "cleared" else f"Allergic to {value}"
    if s == "medication":
        return f"Switched to {value}" if p == "switched" else f"On {value}"
    if s == "diagnosis":
        return f"Diagnosed: {value}"
    return f"{predicate.capitalize()} {value}"


# Status of a fact in the authoritative ledger.
FactStatus = Literal["active", "superseded", "contested", "retracted"]

# How a NEW fact relates to the EXISTING active facts for the same subject.
Classification = Literal["CONSISTENT", "NEW", "SUPERSEDES", "CONTRADICTS"]


def _new_id() -> str:
    return str(uuid.uuid4())


class ClinicalFact(BaseModel):
    """One atomic, dated clinical assertion about a patient."""

    id: str = Field(default_factory=_new_id)
    patient_id: str

    subject: str            # allergy | medication | diagnosis | ...
    predicate: str          # diagnosed | cleared | prescribed | switched | added
    value: str              # penicillin | amlodipine 5mg | type 2 diabetes

    valid_from: date
    valid_to: Optional[date] = None

    source: str = "unknown"
    status: FactStatus = "active"
    superseded_by: Optional[str] = None
    confidence: float = 1.0
    reason: Optional[str] = None

    raw_text: str = ""
    cognee_data_id: Optional[str] = None   # id of this fact's Cognee assertion (for targeted forget)
    source_document: Optional[str] = None  # doc_id of the record this fact came from
    document_title: Optional[str] = None   # human title of that source document

    # --- clinical-copilot layer (FHIR-aligned, additive — engine ignores these) ---
    resource_type: Optional[ResourceType] = None  # discriminator; defaulted from subject
    page: Optional[int] = None                     # page of source_document this fact cites
    # FHIR-typed fields keyed by name (drug_class, severity, reaction, analyte,
    # ref_range, abnormal_flag, relation, age_at_onset, factor, ...). A bag rather
    # than ~20 columns: the checks read named keys, the ledger stays small.
    # ponytail: attributes is a JSON blob, not SQL-queryable — fine at demo scale;
    # promote a key to a real column (or push to Cognee CYPHER) only if a check
    # needs to filter millions of facts on it.
    attributes: Dict[str, Any] = Field(default_factory=dict)
    ontology_valid: Optional[bool] = None          # set by Cognee ontology grounding (Day 1 PM)

    @model_validator(mode="after")
    def _default_resource_type(self) -> "ClinicalFact":
        if self.resource_type is None:
            self.resource_type = RESOURCE_BY_SUBJECT.get(self.subject.strip().lower())
        return self

    @classmethod
    def from_timeline_entry(cls, patient_id: str, entry: dict) -> "ClinicalFact":
        """Build a fact from a `patient_timeline_*.json` entry."""
        return cls(
            patient_id=patient_id,
            subject=entry["subject"],
            predicate=entry["predicate"],
            value=entry["value"],
            valid_from=date.fromisoformat(entry["date"]),
            source=entry.get("source", "unknown"),
            raw_text=entry.get("text", ""),
        )

    @computed_field
    @property
    def label(self) -> str:
        """Plain-English label, serialized to JSON for every fact display."""
        return human_label(self.subject, self.predicate, self.value)

    def short(self) -> str:
        """Compact human/LLM-friendly one-liner used in prompts and logs."""
        span = f"{self.valid_from.isoformat()}"
        if self.valid_to:
            span += f"→{self.valid_to.isoformat()}"
        return (
            f"[{self.id[:8]}] {self.subject}/{self.predicate}: {self.value} "
            f"({span}, {self.status}, src={self.source})"
        )


class Verdict(BaseModel):
    """Structured output of the judge (judge.py)."""

    classification: Classification
    target_fact_id: Optional[str] = None
    reason: str = ""
    confidence: float = 1.0
