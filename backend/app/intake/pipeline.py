"""
Universal intake pipeline — the doctor drops any file and the system does the rest.

1. Sniff format (PDF / FHIR JSON / CSV lab series / raw text; images → deferred)
2. Extract facts (deterministic for FHIR + CSV; Gemini for text/PDF), each carrying
   the FHIR-aligned `attributes` the clinical checks read (§3)
3. Resolve patient identity (hint → FHIR ref → name/MRN → auto-create)
4. Store the upload document
5. Run every fact through the self-healing engine

No hardcoding: uploading a patient's real files is what populates their chart and
makes the pre-visit checks fire.
"""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from pypdf import PdfReader

from app.engine import extract as extract_mod
from app.intake import family_resolver
from app.intake import fhir
from app.intake import structured as S
from app.intake.patient_index import resolve
from app.memory import records
from app.memory.schema import ClinicalFact

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")


@dataclass
class IntakeResult:
    patient_id: str
    patient_name: str
    doc_id: str
    facts: List[ClinicalFact] = field(default_factory=list)
    classification: str = "NEW"
    healed: bool = False
    reason: str = ""
    actions: List[str] = field(default_factory=list)
    created_patient: bool = False
    needs_verification: bool = False


def sniff_format(filename: str, raw_bytes: bytes) -> str:
    """Return 'pdf' | 'fhir' | 'csv' | 'image' | 'text'."""
    fn = filename.lower()
    if fn.endswith(".pdf"):
        return "pdf"
    if fn.endswith(_IMAGE_EXTS):
        return "image"
    if S.is_csv(fn):
        return "csv"
    if fn.endswith(".json"):
        try:
            payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
            if fhir.is_fhir_bundle(payload):
                return "fhir"
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return "text"


def extract_pdf_pages(raw_bytes: bytes) -> List[str]:
    """Per-page text (so a fact can cite the exact page — e.g. the allergy on p.2)."""
    reader = PdfReader(io.BytesIO(raw_bytes))
    return [page.extract_text() or "" for page in reader.pages]


_IMAGE_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/png", ".bmp": "image/png",
    ".tif": "image/png", ".tiff": "image/png",
}


def _image_mime(filename: str) -> str:
    """MIME for a Gemini vision Part; default to PNG for uncommon extensions."""
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return _IMAGE_MIME.get(ext, "image/png")


def _resolve_family_safe(patient_id: str) -> None:
    """Automatic family linkage — best-effort so it never breaks an ingest."""
    try:
        family_resolver.resolve_links(patient_id)
    except Exception:  # pragma: no cover - linkage is additive, never fatal
        pass


async def run(
    raw_bytes: bytes,
    filename: str,
    patient_id_hint: Optional[str] = None,
) -> IntakeResult:
    from app.api.routes_patients import _run_ingest  # reuse existing ingest logic

    fmt = sniff_format(filename, raw_bytes)

    asserts: List[dict] = []
    identity = {"name": "", "dob": "", "mrn": "", "ref": ""}
    doc_date = date.today().isoformat()
    author = "uploaded"
    raw_text = ""

    # --- 1. Parse content by format ---
    if fmt == "pdf":
        pages = extract_pdf_pages(raw_bytes)
        raw_text = "\n\n".join(p for p in pages if p.strip())
        if not raw_text.strip():
            raise ValueError("PDF contains no extractable text (may be a scanned image).")
        for page_no, page_text in enumerate(pages, start=1):
            if not page_text.strip():
                continue
            rich = extract_mod.extract_facts_rich(page_text, doc_date, source=filename)
            for a in rich["asserts"]:
                a["page"] = page_no
            asserts.extend(rich["asserts"])
            identity = _merge_identity(identity, rich["identity"])

    elif fmt == "fhir":
        payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        identity = fhir.extract_patient_identity(payload)
        asserts = fhir.extract_facts(payload)
        raw_text = json.dumps(payload, indent=2)

    elif fmt == "image":
        # A photo/scan of a paper record — read directly with Gemini vision (no GPU).
        rich = extract_mod.extract_facts_rich_from_image(
            raw_bytes, _image_mime(filename), doc_date, source=filename
        )
        asserts = rich["asserts"]
        identity = {**identity, **rich["identity"]}
        raw_text = f"[Scanned/photographed document: {filename} — read by Gemini vision]"

    elif fmt == "csv":
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        asserts = S.parse_csv_labs(raw_text, source=filename)
        identity = _identity_from_csv(raw_text)

    else:  # text
        raw_text = raw_bytes.decode("utf-8", errors="replace").strip()
        rich = extract_mod.extract_facts_rich(raw_text, doc_date, source=filename)
        asserts = rich["asserts"]
        identity = {**identity, **rich["identity"]}

    if asserts:
        dates = [a["date"] for a in asserts if a.get("date")]
        if dates:
            doc_date = records._coerce_date(min(dates), date.today()).isoformat()
        author = asserts[0].get("source") or author

    if not asserts:
        raise ValueError("Document contains nothing to ingest.")

    # --- 2. Resolve patient ---
    patient_id, created_patient = _resolve_patient(patient_id_hint, identity)
    if not patient_id:
        raise ValueError(
            "Could not identify which patient this document belongs to. Open the "
            "patient first, or ensure the document names the patient / MRN."
        )

    # --- 3. Store the upload ---
    doc_id = f"UP-{patient_id}-{uuid.uuid4().hex[:8]}"
    doc = {
        "doc_id": doc_id, "date": doc_date, "type": "Uploaded record",
        "author": author, "title": filename,
        "text": raw_text or json.dumps(asserts, indent=2),
        "uploaded": True, "asserts": asserts,
    }
    records.save_upload(patient_id, doc)

    # --- 4. Run through the self-healing engine ---
    result = await _run_ingest(patient_id, {**doc, "patient_id": patient_id})

    # Auto-link family: a relative named in this document may be another patient.
    _resolve_family_safe(patient_id)

    patient = records.get_patient(patient_id)
    return IntakeResult(
        patient_id=patient_id,
        patient_name=patient["name"] if patient else patient_id,
        doc_id=doc_id,
        facts=result.facts,
        classification=result.classification,
        healed=result.healed,
        reason=result.reason,
        actions=result.actions,
        created_patient=created_patient,
    )


# --- identity helpers ---------------------------------------------------------
def _merge_identity(base: dict, new: dict) -> dict:
    """First non-empty wins for each field (early PDF pages usually carry the header)."""
    out = dict(base)
    for k in ("name", "dob", "mrn", "ref"):
        if not out.get(k) and new.get(k):
            out[k] = new[k]
    return out


def _identity_from_csv(text: str) -> dict:
    """Pull patient_id / mrn from the first CSV row for resolution."""
    import csv
    for row in csv.DictReader(io.StringIO(text)):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        return {"name": "", "dob": "", "mrn": r.get("mrn", ""), "ref": r.get("patient_id", "")}
    return {"name": "", "dob": "", "mrn": "", "ref": ""}


def _resolve_patient(hint: Optional[str], identity: dict) -> tuple[Optional[str], bool]:
    """(patient_id, created_new). Priority: explicit hint → known FHIR/CSV patient
    reference → name/MRN match-or-create."""
    if hint and records.get_patient(hint):
        return hint, False

    ref = (identity.get("ref") or "").strip()
    if ref and records.get_patient(ref):
        return ref, False

    name, dob, mrn = identity.get("name", ""), identity.get("dob", ""), identity.get("mrn", "")
    if name or mrn:
        existing_before = {p["patient_id"] for p in records.list_patients()}
        pid = resolve(name, dob, mrn)
        return pid, pid not in existing_before

    # A reference we don't know about yet — honor it rather than failing.
    if ref:
        return ref, False
    return None, False
