"""
Dynamic ontology classification — the fallback for a drug or condition NOT in
the curated tables (ontology.py). Runs ONLY at ingest time (never from a sync
check, which must stay fast/deterministic), classifies into the SAME closed
vocabulary those tables already define (never invents a new category), and
the caller persists a successful result via ontology.remember_* so every
future lookup — sync checks AND Cognee's own OWL-grounded resolver, once
rebuilt — finds it without another LLM call.

Uses the same google-genai/Vertex client and EXTRACTION_MODEL as the rest of
the app (judge.py, extract.py) — no new provider, no new auth path.
"""

from __future__ import annotations

from typing import Optional

import app.config as config  # noqa: F401  (wires Vertex env)
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.memory import ontology

_SYSTEM_DRUG = (
    "You are a pharmacology classifier. Given a medication name, decide which "
    "ONE of these pharmacologic classes it belongs to: {classes}. "
    "If it clearly doesn't belong to any of them, answer 'unknown'. "
    "Return JSON: {{\"label\": \"<one of the classes above, or unknown>\"}}."
)

_SYSTEM_FAMILY = (
    "You are a clinical genetics classifier. Given a medical condition, decide "
    "which ONE of these hereditary-risk categories a first-degree relative "
    "having it would confer to the patient: {categories}. "
    "If none clearly apply, answer 'none'. "
    "Return JSON: {{\"label\": \"<one of the categories above, or none>\"}}."
)


class _Label(BaseModel):
    label: str


def _client() -> genai.Client:
    return genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)


def _classify(system_prompt: str, contents: str, allowed: list[str]) -> Optional[str]:
    try:
        client = _client()
        response = client.models.generate_content(
            model=config.EXTRACTION_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                response_mime_type="application/json",
                response_schema=_Label,
            ),
        )
        label = response.parsed.label.strip().lower()  # type: ignore[union-attr]
        return label if label in allowed else None
    except Exception:  # pragma: no cover - best-effort, never breaks an ingest
        return None


def classify_drug(drug: str) -> Optional[str]:
    """Classify an unrecognized drug into one of the ALREADY-KNOWN pharmacologic
    classes. Returns None on any failure or if the model says 'unknown' — a
    miss here just means ontology_valid stays False, it never breaks ingest."""
    classes = ontology.KNOWN_DRUG_CLASSES
    return _classify(
        _SYSTEM_DRUG.format(classes=", ".join(classes)),
        f"Medication: {drug}",
        classes,
    )


def classify_family_risk(condition: str) -> Optional[str]:
    """Classify an unrecognized family-history condition into one of the
    ALREADY-KNOWN hereditary risk categories. Same best-effort contract."""
    categories = ontology.KNOWN_RISK_CATEGORIES
    return _classify(
        _SYSTEM_FAMILY.format(categories=", ".join(categories)),
        f"Condition: {condition}",
        categories,
    )
