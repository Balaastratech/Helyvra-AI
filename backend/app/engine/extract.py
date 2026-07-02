"""
Free-text → ClinicalFact extraction (Vertex Gemini Flash, ADC, no API key).

`/ingest` accepts a natural-language clinical note (e.g. the held-back
"allergy cleared" event). When the caller does not supply structured fields, we
extract subject / predicate / value / date / source here with the cheap
extraction model and structured output, then hand the resulting `ClinicalFact`
to the self-healing engine.

Deterministic (temperature 0) and structured (`_Extracted` schema) so the demo
is reproducible.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import app.config as config  # noqa: F401  (strips API keys, sets Vertex env)
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.memory.schema import ClinicalFact

_SYSTEM = (
    "You extract ONE atomic clinical fact from a clinician's note about a single "
    "patient. Return strict JSON. Fields:\n"
    "- subject: the clinical category, lowercase, one of: allergy | medication | "
    "diagnosis | vital | procedure | lab (pick the closest).\n"
    "- predicate: the event verb, lowercase: diagnosed | cleared | prescribed | "
    "switched | stopped | added | resolved | updated.\n"
    "- value: the specific thing (e.g. 'penicillin', 'amlodipine 5mg', "
    "'type 2 diabetes'). Keep dosage if present.\n"
    "- valid_from: the ISO date (YYYY-MM-DD) the fact became true. Use the date in "
    "the note.\n"
    "- source: the clinician/source named in the note (e.g. 'Dr. Lee'), else 'unknown'."
)


class _Extracted(BaseModel):
    subject: str
    predicate: str
    value: str
    valid_from: date
    source: str = "unknown"


def extract_fact(patient_id: str, text: str) -> ClinicalFact:
    """Extract a `ClinicalFact` from a free-text clinical note via Vertex Flash."""
    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
    response = client.models.generate_content(
        model=config.EXTRACTION_MODEL,
        contents=f"NOTE:\n{text}",
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0,
            response_mime_type="application/json",
            response_schema=_Extracted,
        ),
    )
    e: _Extracted = response.parsed  # type: ignore[assignment]
    return ClinicalFact(
        patient_id=patient_id,
        subject=e.subject.strip().lower(),
        predicate=e.predicate.strip().lower(),
        value=e.value.strip(),
        valid_from=e.valid_from,
        source=e.source.strip() or "unknown",
        raw_text=text,
    )


def build_fact(patient_id: str, text: str, structured: Optional[dict]) -> ClinicalFact:
    """
    Build the `ClinicalFact` to ingest:
      - if `structured` carries the core fields (subject/predicate/value/date),
        use them directly (deterministic, no LLM);
      - otherwise extract them from `text` via Vertex Flash.
    `text` is always preserved as `raw_text` for the judge + provenance.
    """
    structured = structured or {}
    core = ("subject", "predicate", "value")
    has_date = structured.get("valid_from") or structured.get("date")
    if all(structured.get(k) for k in core) and has_date:
        raw_date = structured.get("valid_from") or structured.get("date")
        vf = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
        return ClinicalFact(
            patient_id=patient_id,
            subject=str(structured["subject"]).strip().lower(),
            predicate=str(structured["predicate"]).strip().lower(),
            value=str(structured["value"]).strip(),
            valid_from=vf,
            source=str(structured.get("source", "unknown")).strip() or "unknown",
            raw_text=text or structured.get("raw_text", ""),
        )
    if not text:
        raise ValueError("ingest requires either `text` or full `structured` fields.")
    return extract_fact(patient_id, text)


# --- rich multi-fact extraction (clinical-copilot intake, §3) -----------------
# Free text and PDFs assert MULTIPLE typed facts (a discharge names a diagnosis +
# a med; an intake form names smoking + family history). This extractor returns
# the FHIR-aligned attribute bag the check engine reads, so an uploaded document
# fires the clinical checks with zero hardcoding — the missing Day-3 bridge.

_RICH_SYSTEM = (
    "You are a clinical information extractor. From a clinician's note or a lab/"
    "discharge document, extract EVERY distinct clinical fact as structured JSON, "
    "and identify the patient. Do not invent facts. Use the dates in the document.\n\n"
    "For each fact set:\n"
    "- resource_type: one of Allergy | Condition | Medication | LabResult | Vital | "
    "FamilyHistory | Lifestyle | Procedure.\n"
    "- value: the specific thing in plain words (e.g. 'penicillin', "
    "'metformin 500mg', 'type 2 diabetes', 'HbA1c 8.6%', 'current smoker').\n"
    "- date: ISO YYYY-MM-DD the fact became true (the document/section date).\n"
    "- cleared: true only if the note says an allergy/condition was cleared/resolved.\n"
    "Fill ONLY the attribute fields that apply to the resource_type:\n"
    "- Allergy: substance (e.g. 'penicillin'), reaction (e.g. 'rash and breathing "
    "difficulty'), severity ('mild'|'moderate'|'severe').\n"
    "- Medication: drug (generic name + dose).\n"
    "- Condition: condition (the diagnosis name).\n"
    "- LabResult: analyte (e.g. 'HbA1c','LDL','creatinine'), numeric_value (number "
    "only), unit, ref_range, abnormal_flag ('high'|'low'|'normal').\n"
    "- FamilyHistory: relation ('father','mother',...), condition, age_at_onset "
    "(number, if stated), relative_name (the relative's full name if stated, e.g. "
    "'Rahul Sharma'), relative_mrn (the relative's MRN/medical-record number if "
    "stated, e.g. 'MRN-2010'), relative_dob (ISO date if stated).\n"
    "- Lifestyle: factor ('smoking','alcohol','diet','exercise'), and value the "
    "detail (e.g. 'current smoker').\n"
    "Leave unused fields blank/0. Also set patient_name / patient_dob / patient_mrn "
    "if the document identifies the patient, else leave blank."
)


class _RichFact(BaseModel):
    resource_type: str = ""
    value: str = ""
    date: str = ""
    cleared: bool = False
    # attribute bag (only the relevant ones are filled per resource_type)
    substance: str = ""
    reaction: str = ""
    severity: str = ""
    drug: str = ""
    condition: str = ""
    analyte: str = ""
    numeric_value: float = 0.0
    unit: str = ""
    ref_range: str = ""
    abnormal_flag: str = ""
    relation: str = ""
    age_at_onset: int = 0
    factor: str = ""
    relative_name: str = ""
    relative_dob: str = ""
    relative_mrn: str = ""


class _RichExtraction(BaseModel):
    facts: list[_RichFact] = []
    patient_name: str = ""
    patient_dob: str = ""
    patient_mrn: str = ""


def _rich_fact_to_assert(f: "_RichFact", default_date: str, source: str) -> Optional[dict]:
    """Map one extracted fact to the shared attribute-rich assert shape."""
    from app.intake import structured as S

    rt = (f.resource_type or "").strip().lower()
    dt = (f.date or default_date).strip() or default_date
    if rt == "allergy":
        substance = f.substance or f.value
        if not substance:
            return None
        return S.allergy_assert(substance, dt, cleared=f.cleared, reaction=f.reaction,
                                severity=f.severity, source=source)
    if rt == "medication":
        drug = f.drug or f.value
        return S.medication_assert(drug, dt, source=source) if drug else None
    if rt == "condition":
        condition = f.condition or f.value
        return S.condition_assert(condition, dt, resolved=f.cleared, source=source) if condition else None
    if rt == "labresult":
        analyte = f.analyte or f.value
        if not analyte:
            return None
        val = f.numeric_value if f.numeric_value else (f.value or "")
        return S.lab_assert(analyte, val, dt, unit=f.unit, ref_range=f.ref_range,
                            flag=f.abnormal_flag, source=source)
    if rt == "familyhistory":
        condition = f.condition or f.value
        if not (f.relation and condition):
            return None
        age = f.age_at_onset if f.age_at_onset else None
        return S.family_assert(
            f.relation, condition, dt, age_at_onset=age,
            relative_name=f.relative_name, relative_dob=f.relative_dob,
            relative_mrn=f.relative_mrn, source=source,
        )
    if rt == "lifestyle":
        factor = f.factor or f.value
        return S.lifestyle_assert(factor, f.value, dt, source=source) if factor else None
    if rt in ("vital", "procedure") and f.value:
        subject = "vital" if rt == "vital" else "procedure"
        return {"resource_type": f.resource_type, "subject": subject,
                "predicate": "measured" if rt == "vital" else "performed",
                "value": f.value, "date": dt, "source": source, "attributes": {}}
    # Unknown/blank resource_type but a value present — keep as a generic note.
    if f.value:
        return {"resource_type": None, "subject": "note", "predicate": "recorded",
                "value": f.value, "date": dt, "source": source, "attributes": {}}
    return None


def _asserts_from_extraction(parsed: "_RichExtraction", default_date: str, source: str,
                             raw_text: str) -> dict:
    """Shared: turn a model _RichExtraction into the {asserts, identity} shape."""
    asserts: list[dict] = []
    for rf in parsed.facts:
        a = _rich_fact_to_assert(rf, default_date, source)
        if a:
            a["raw_text"] = raw_text
            asserts.append(a)
    return {
        "asserts": asserts,
        "identity": {
            "name": parsed.patient_name.strip(),
            "dob": parsed.patient_dob.strip(),
            "mrn": parsed.patient_mrn.strip(),
        },
    }


def extract_facts_rich(text: str, default_date: str, source: str = "uploaded") -> dict:
    """Extract MANY typed facts + patient identity from free text / PDF text.
    Returns {"asserts": [...], "identity": {name, dob, mrn}}."""
    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
    response = client.models.generate_content(
        model=config.EXTRACTION_MODEL,
        contents=f"DOCUMENT:\n{text}",
        config=types.GenerateContentConfig(
            system_instruction=_RICH_SYSTEM,
            temperature=0,
            response_mime_type="application/json",
            response_schema=_RichExtraction,
        ),
    )
    parsed: _RichExtraction = response.parsed  # type: ignore[assignment]
    return _asserts_from_extraction(parsed, default_date, source, raw_text=text)


def extract_facts_rich_from_image(
    image_bytes: bytes, mime_type: str, default_date: str, source: str = "uploaded"
) -> dict:
    """Read a PHOTO or SCAN of a medical document — a real doctor's upload for old
    paper records, handwritten prescriptions, phone photos — directly with Gemini
    Flash (multimodal, on Vertex, no GPU). Same clinical extraction schema as text,
    so an image ingests exactly like a PDF/note. Returns {asserts, identity}.

    `raw_text` is set to a short provenance note (the image itself is the source of
    truth, retained as the uploaded document)."""
    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
    response = client.models.generate_content(
        model=config.EXTRACTION_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            "Read this scanned/photographed medical document and extract the clinical facts.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=_RICH_SYSTEM,
            temperature=0,
            response_mime_type="application/json",
            response_schema=_RichExtraction,
        ),
    )
    parsed: _RichExtraction = response.parsed  # type: ignore[assignment]
    return _asserts_from_extraction(
        parsed, default_date, source, raw_text=f"[Extracted from image: {source}]"
    )
