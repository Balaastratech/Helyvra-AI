"""
Synthetic medical-records store (read-only, disk-backed).

This is the "real application" data layer: a patient registry and per-patient
clinical DOCUMENTS (notes, labs, med orders) under `data/`. The UI lists
patients (name + MRN) and their documents; ingesting a document runs its
assertion through the self-healing engine and links the resulting fact back to
its source file (`ClinicalFact.source_document`).

Data is synthetic; the *flow* mirrors a real chart: pick a patient -> read their
records -> ingest documents -> memory builds and self-heals over time.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from app.memory.schema import ClinicalFact

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_PATIENTS_FILE = _DATA_DIR / "patients.json"
_USER_PATIENTS_FILE = _DATA_DIR / "patients_user.json"


def _load_patients() -> List[dict]:
    seed: List[dict] = []
    if _PATIENTS_FILE.exists():
        seed = json.loads(_PATIENTS_FILE.read_text(encoding="utf-8")).get("patients", [])
    user: List[dict] = []
    if _USER_PATIENTS_FILE.exists():
        user = json.loads(_USER_PATIENTS_FILE.read_text(encoding="utf-8")).get("patients", [])
    return seed + user


def add_patient(name: str, dob: str = "", sex: str = "", mrn: str = "", summary: str = "") -> dict:
    """Create a new (user-authored) patient chart, persisted separately from seed."""
    existing = _load_patients()
    ids = {p["patient_id"] for p in existing}
    n = len(existing) + 1
    while f"P{n:03d}" in ids:
        n += 1
    pid = f"P{n:03d}"
    patient = {
        "patient_id": pid,
        "mrn": mrn.strip() or f"MRN-{900000 + n}",
        "name": name.strip() or pid,
        "dob": dob.strip(),
        "sex": sex.strip(),
        "summary": summary.strip() or "New chart — upload records to begin.",
    }
    user: List[dict] = []
    if _USER_PATIENTS_FILE.exists():
        user = json.loads(_USER_PATIENTS_FILE.read_text(encoding="utf-8")).get("patients", [])
    user.append(patient)
    _USER_PATIENTS_FILE.write_text(
        json.dumps({"patients": user}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return patient


def _load_documents(patient_id: str) -> List[dict]:
    path = _DATA_DIR / "patients" / patient_id / "documents.json"
    docs: List[dict] = []
    if path.exists():
        docs = json.loads(path.read_text(encoding="utf-8")).get("documents", [])
    docs = docs + _load_uploads(patient_id)
    return sorted(docs, key=lambda d: d["date"])


def _uploads_dir(patient_id: str) -> Path:
    return _DATA_DIR / "patients" / patient_id / "uploads"


def _load_uploads(patient_id: str) -> List[dict]:
    d = _uploads_dir(patient_id)
    if not d.exists():
        return []
    out: List[dict] = []
    for f in d.glob("*.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def save_upload(patient_id: str, doc: dict) -> dict:
    """Persist an uploaded document so it shows in the inbox + viewer."""
    d = _uploads_dir(patient_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{doc['doc_id']}.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return doc


# --- public API -----------------------------------------------------------
def list_patients() -> List[dict]:
    return _load_patients()


def get_patient(patient_id: str) -> Optional[dict]:
    return next((p for p in _load_patients() if p["patient_id"] == patient_id), None)


def list_documents(patient_id: str) -> List[dict]:
    return _load_documents(patient_id)


def get_document(doc_id: str) -> Optional[dict]:
    """Find a document by id across all patients (doc_id encodes the patient)."""
    for p in _load_patients():
        for d in _load_documents(p["patient_id"]):
            if d["doc_id"] == doc_id:
                return {**d, "patient_id": p["patient_id"]}
    return None


def _coerce_date(raw, fallback) -> date:
    """Parse a date from intake that may be partial/odd (LLM or source tables emit
    '2019-03' or '2019'), never raising: coerce to a valid date, else use the
    document's date, else today. A partial date must not 422 an otherwise good
    document."""
    if isinstance(raw, date):
        return raw
    s = str(raw or "").strip()
    for candidate in (s, s[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    # YYYY-MM -> first of month; YYYY -> first of year.
    import re
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(r"^(\d{4})$", s)
    if m:
        return date(int(m.group(1)), 1, 1)
    if isinstance(fallback, date):
        return fallback
    try:
        return date.fromisoformat(str(fallback)[:10])
    except (ValueError, TypeError):
        return date.today()


def facts_from_document(patient_id: str, doc: dict) -> List[ClinicalFact]:
    """Build the ClinicalFact(s) a document asserts, linked back to the file.

    Each assert may carry the FHIR-aligned clinical detail the check engine reads
    (`resource_type`, `attributes`, `page`) plus its own `date`/`source`; when
    absent we fall back to the document's. This is the SINGLE door every intake
    path (FHIR, CSV, LLM text/PDF) funnels through, so the attribute bag the checks
    depend on is populated in exactly one place."""
    out: List[ClinicalFact] = []
    for a in doc.get("asserts", []):
        valid_from = _coerce_date(a.get("date"), doc.get("date"))
        attributes = dict(a.get("attributes") or {})
        out.append(
            ClinicalFact(
                patient_id=patient_id,
                subject=str(a["subject"]).strip().lower(),
                predicate=str(a["predicate"]).strip().lower(),
                value=str(a["value"]).strip(),
                valid_from=valid_from,
                source=str(a.get("source") or doc.get("author") or "unknown").strip(),
                raw_text=a.get("raw_text") or doc.get("text", ""),
                source_document=doc["doc_id"],
                document_title=doc.get("title", ""),
                resource_type=a.get("resource_type"),
                page=a.get("page"),
                attributes=attributes,
            )
        )
    return out


def ingested_doc_ids(patient_facts: List[ClinicalFact]) -> Dict[str, str]:
    """Map source_document -> fact_id for facts already in the ledger."""
    return {f.source_document: f.id for f in patient_facts if f.source_document}
