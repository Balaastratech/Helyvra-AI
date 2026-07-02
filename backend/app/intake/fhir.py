"""
FHIR → ClinicalFact assert parser (no LLM — pure structured parse).

Handles a FHIR **Bundle** (entry[].resource) *and* a bare top-level resource
(e.g. a standalone FamilyMemberHistory or Observation), extracting the resources
we care about into the shared attribute-rich assert shape (`intake.structured`):

  AllergyIntolerance  → Allergy   (substance, reaction, severity)
  MedicationStatement → Medication (drug)
  Condition           → Condition  (condition)
  Observation         → LabResult/Vital (analyte, value, unit, ref_range, flag)
  FamilyMemberHistory → FamilyHistory (relation, condition, age_at_onset)

Populating `attributes` here is what lets the clinical checks fire on an uploaded
FHIR file with zero hardcoding.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.intake import structured as S

# Resources we can turn into a fact — used for both Bundle entries and bare docs.
_KNOWN_RESOURCES = {
    "Bundle", "AllergyIntolerance", "MedicationStatement", "MedicationRequest",
    "Condition", "Observation", "FamilyMemberHistory",
}


def is_fhir_bundle(payload: dict) -> bool:
    """True if the dict is a FHIR Bundle OR a bare FHIR resource we can parse."""
    if not isinstance(payload, dict):
        return False
    return payload.get("resourceType") in _KNOWN_RESOURCES


def _resources(payload: dict) -> List[dict]:
    """Every clinical resource in the payload — Bundle entries, or the doc itself
    when it's a bare resource."""
    if payload.get("resourceType") == "Bundle":
        return [e.get("resource", {}) for e in payload.get("entry", [])]
    return [payload]


def extract_patient_identity(payload: dict) -> dict:
    """Patient name + DOB + MRN from a Patient resource, else empty strings.
    Also returns `ref` — the `Patient/{id}` referenced by clinical resources —
    so a bare resource that names no patient can still resolve to a known chart."""
    ref = ""
    for res in _resources(payload):
        if res.get("resourceType") == "Patient":
            return {
                "name": _patient_name(res), "dob": res.get("birthDate", ""),
                "mrn": _patient_mrn(res), "ref": res.get("id", ""),
            }
        if not ref:
            ref = _subject_ref(res)
    return {"name": "", "dob": "", "mrn": "", "ref": ref}


def extract_facts(payload: dict) -> List[dict]:
    """Parse clinical resources into attribute-rich assert dicts."""
    facts: List[dict] = []
    for res in _resources(payload):
        parsed = _parse_resource(res.get("resourceType", ""), res)
        facts.extend(parsed)
    return facts


# --- per-resource parsers -----------------------------------------------------
def _parse_resource(resource_type: str, res: dict) -> List[dict]:
    if resource_type == "AllergyIntolerance":
        return [_parse_allergy(res)]
    if resource_type in ("MedicationStatement", "MedicationRequest"):
        return [_parse_medication(res)]
    if resource_type == "Condition":
        return [_parse_condition(res)]
    if resource_type == "Observation":
        return [_parse_observation(res)]
    if resource_type == "FamilyMemberHistory":
        return _parse_family_history(res)
    return []


def _parse_allergy(res: dict) -> dict:
    substance = _codeable_text(res.get("code") or res.get("substance", {})) or "unknown allergen"
    cleared = _coding_text(res.get("clinicalStatus", {})) in ("inactive", "resolved")
    dt = _to_date(res.get("onsetDateTime") or res.get("recordedDate") or "")
    reaction = _reaction_text(res)
    severity = _reaction_severity(res)
    return S.allergy_assert(
        substance, dt, cleared=cleared, reaction=reaction, severity=severity,
        source=_recorder(res),
    )


def _parse_medication(res: dict) -> dict:
    med = _codeable_text(
        res.get("medicationCodeableConcept") or res.get("medicationReference", {})
        or res.get("code", {})
    ) or "unknown medication"
    stopped = res.get("status", "active") in ("stopped", "completed")
    dt = _to_date(res.get("effectiveDateTime") or res.get("dateAsserted") or res.get("authoredOn") or "")
    return S.medication_assert(med, dt, stopped=stopped, source=_recorder(res))


def _parse_condition(res: dict) -> dict:
    condition = _codeable_text(res.get("code", {})) or "unknown condition"
    resolved = _coding_text(res.get("clinicalStatus", {})) in ("inactive", "resolved", "remission")
    dt = _to_date(res.get("onsetDateTime") or res.get("recordedDate") or "")
    return S.condition_assert(condition, dt, resolved=resolved, source=_recorder(res))


def _parse_observation(res: dict) -> dict:
    analyte = _codeable_text(res.get("code", {}))
    dt = _to_date(res.get("effectiveDateTime") or res.get("issued") or "")
    flag = _codeable_text_list(res.get("interpretation", []))
    ref_range = _reference_range(res)
    source = res.get("_source") or _recorder(res)

    if "valueQuantity" in res:
        vq = res["valueQuantity"]
        return S.lab_assert(
            analyte, vq.get("value", ""), dt, unit=vq.get("unit", ""),
            ref_range=ref_range, flag=flag, source=source,
        )
    # Non-numeric observation (e.g. pregnancy flag) — record as a lifestyle/flag
    # fact so it's retained without polluting numeric trends.
    value = _observation_text(res)
    return S.lifestyle_assert(analyte or "observation", value, dt, source=source)


def _parse_family_history(res: dict) -> List[dict]:
    relation = _codeable_text(res.get("relationship", {})) or "relative"
    dt = _to_date(res.get("date") or "")
    source = res.get("_source") or _recorder(res)
    # FHIR FamilyMemberHistory.name is the relative's name — the linkage key.
    relative_name = res.get("name", "") if isinstance(res.get("name"), str) else ""
    out: List[dict] = []
    for cond in res.get("condition", []):
        condition = _codeable_text(cond.get("code", {})) or "condition"
        onset = cond.get("onsetAge") or {}
        age = onset.get("value") if isinstance(onset, dict) else None
        out.append(S.family_assert(
            relation, condition, dt, age_at_onset=age,
            relative_name=relative_name, source=source,
        ))
    return out


# --- helpers ------------------------------------------------------------------
def _codeable_text(concept: dict) -> str:
    if not concept or not isinstance(concept, dict):
        return ""
    if concept.get("text"):
        return concept["text"]
    for coding in concept.get("coding", []):
        if coding.get("display"):
            return coding["display"]
    return ""


def _coding_text(concept: dict) -> str:
    """Lowercased status text/code from a CodeableConcept (clinicalStatus etc.)."""
    if not concept or not isinstance(concept, dict):
        return ""
    if concept.get("text"):
        return concept["text"].strip().lower()
    for coding in concept.get("coding", []):
        if coding.get("code"):
            return coding["code"].strip().lower()
    return ""


def _codeable_text_list(items) -> str:
    for it in items or []:
        t = _codeable_text(it)
        if t:
            return t
    return ""


def _reaction_text(res: dict) -> str:
    for r in res.get("reaction", []) or []:
        manifestations = [_codeable_text(m) for m in r.get("manifestation", [])]
        manifestations = [m for m in manifestations if m]
        if manifestations:
            return ", ".join(manifestations)
    return ""


def _reaction_severity(res: dict) -> str:
    for r in res.get("reaction", []) or []:
        if r.get("severity"):
            return r["severity"]
    return res.get("criticality", "") or ""


def _reference_range(res: dict) -> str:
    for rr in res.get("referenceRange", []) or []:
        if rr.get("text"):
            return rr["text"]
    return ""


def _observation_text(res: dict) -> str:
    if "valueString" in res:
        return res["valueString"]
    if "valueCodeableConcept" in res:
        return _codeable_text(res["valueCodeableConcept"])
    return ""


def _recorder(res: dict) -> str:
    rec = res.get("recorder") or res.get("asserter") or res.get("requester") or {}
    if isinstance(rec, dict):
        return rec.get("display") or rec.get("reference") or "unknown"
    return "unknown"


def _subject_ref(res: dict) -> str:
    """The bare patient id a clinical resource points at: 'Patient/P010' -> 'P010'."""
    subj = res.get("subject") or res.get("patient") or {}
    ref = subj.get("reference", "") if isinstance(subj, dict) else ""
    return ref.split("/")[-1] if ref else ""


def _patient_name(patient: dict) -> str:
    names = patient.get("name", [])
    if not names:
        return ""
    n = names[0] if isinstance(names, list) else names
    if n.get("text"):
        return n["text"]
    return f"{' '.join(n.get('given', []))} {n.get('family', '')}".strip()


def _patient_mrn(patient: dict) -> str:
    for ident in patient.get("identifier", []):
        for coding in ident.get("type", {}).get("coding", []):
            if coding.get("code") == "MR":
                return ident.get("value", "")
        sys = (ident.get("system") or "").lower()
        if "mrn" in sys or "medical-record" in sys:
            return ident.get("value", "")
    return ""


def _to_date(dt_str: str) -> str:
    return dt_str[:10] if dt_str else date.today().isoformat()
