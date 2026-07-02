r"""
Day-3 intake bridge (the piece that was missing): uploading a patient's real
files must populate the FHIR-aligned `attributes` the check engine reads — with
NO hardcoding. This exercises the DETERMINISTIC paths (FHIR + CSV) end to end:
parse the synthetic P010 source files → build ClinicalFacts through the same
`records.facts_from_document` door the API uses → the three open checks fire.

Offline: no Vertex, no Cognee. The text/PDF LLM path (smoking, creatinine 1.6,
penicillin allergy) is simulated here with the same structured builders the LLM
extractor emits, so the whole check surface is covered.

Run: .\.venv\Scripts\python.exe -m pytest tests/test_intake_extract.py -q
"""

import json
from pathlib import Path

import pytest

from app import checks
from app.intake import fhir, structured as S
from app.memory import ledger, records

_SYNTH = Path(__file__).resolve().parents[2] / "clinical_copilot_synthetic_data" / "data" / "patients" / "P010"
PATIENT = "P010"

pytestmark = pytest.mark.skipif(not _SYNTH.exists(), reason="synthetic data package not present")


def _doc(doc_id, title, date, asserts):
    return {"doc_id": doc_id, "title": title, "date": date, "author": "test", "text": "", "asserts": asserts}


def _add(doc_id, title, date, asserts):
    for f in records.facts_from_document(PATIENT, _doc(doc_id, title, date, asserts)):
        ledger.add(f)


def test_fhir_family_history_parses_attributes():
    payload = json.loads((_SYNTH / "P010_family_history.json").read_text(encoding="utf-8"))
    asserts = fhir.extract_facts(payload)
    assert len(asserts) == 1
    a = asserts[0]
    assert a["resource_type"] == "FamilyHistory"
    assert a["attributes"]["relation"] == "father"
    assert a["attributes"]["condition"] == "myocardial infarction"
    assert a["attributes"]["age_at_onset"] == 49


def test_csv_labs_parse_to_typed_lab_results():
    text = (_SYNTH / "P010_labs_2024.csv").read_text(encoding="utf-8")
    asserts = S.parse_csv_labs(text, source="P010_labs_2024.csv")
    by_analyte = {a["attributes"]["analyte"]: a for a in asserts}
    assert set(by_analyte) == {"hba1c", "ldl", "creatinine"}
    assert by_analyte["hba1c"]["attributes"]["value"] == 7.8
    assert by_analyte["hba1c"]["attributes"]["abnormal_flag"] == "high"
    assert by_analyte["ldl"]["attributes"]["value"] == 165
    assert by_analyte["creatinine"]["attributes"]["abnormal_flag"] == "normal"
    assert all(a["resource_type"] == "LabResult" for a in asserts)


def test_fhir_observation_bundle_parses_lab():
    payload = json.loads((_SYNTH / "P010_lab_recent.fhir.json").read_text(encoding="utf-8"))
    asserts = fhir.extract_facts(payload)
    assert len(asserts) == 1
    assert asserts[0]["attributes"]["analyte"] == "hba1c"
    assert asserts[0]["attributes"]["value"] == 8.9
    assert asserts[0]["attributes"]["abnormal_flag"] == "high"


def test_uploaded_files_fire_the_three_open_checks():
    """The whole point: parsed uploads (not hand-seeded facts) produce the brief."""
    ledger.reset()
    try:
        # deterministic sources
        fam = fhir.extract_facts(json.loads((_SYNTH / "P010_family_history.json").read_text("utf-8")))
        _add("D-fam", "family history", "2023-01-15", fam)
        csv_labs = S.parse_csv_labs((_SYNTH / "P010_labs_2024.csv").read_text("utf-8"), "P010_labs_2024.csv")
        _add("D-csv", "2024 labs", "2024-06-12", csv_labs)
        recent = fhir.extract_facts(json.loads((_SYNTH / "P010_lab_recent.fhir.json").read_text("utf-8")))
        _add("D-fhir", "2026 labs", "2026-05-08", recent)

        # LLM-path facts, built with the same structured builders the extractor emits
        _add("D-allergy", "2021 discharge", "2021-08-09", [
            {**S.allergy_assert("penicillin", "2021-08-09", reaction="rash and breathing difficulty",
                                severity="severe", source="Dr. Rao"), "page": 2},
        ])
        _add("D-intake", "intake form", "2023-01-15", [
            S.lifestyle_assert("smoking", "current smoker", "2023-01-15", source="intake"),
        ])
        _add("D-renal", "2025 renal panel", "2025-12-04", [
            S.lab_assert("Creatinine", 1.6, "2025-12-04", unit="mg/dL", ref_range="0.7-1.3",
                         flag="high", source="P010_lab_renal_2025.pdf"),
        ])
        _add("D-hba1c25", "2025 HbA1c", "2025-06-18", [
            S.lab_assert("HbA1c", 8.6, "2025-06-18", unit="%", flag="high", source="P010_lab_hba1c_2025.pdf"),
        ])

        cards = checks.run_open_checks(PATIENT)
        ids = [c.check_id for c in cards]
        assert any(i.startswith("followup_gap:gap:creatinine") for i in ids), ids
        assert any(i.startswith("followup_gap:trend:hba1c") for i in ids), ids
        assert any(i.startswith("combined_risk:cardiovascular") for i in ids), ids
        assert all(c.source for c in cards)  # every card cited

        # prescribe-time allergy cross-reactivity
        rx = checks.run_prescribe_checks(PATIENT, "amoxicillin 500mg")
        assert len(rx) == 1 and rx[0].indicator == "critical"
        assert rx[0].source[0].page == 2
    finally:
        ledger.reset()
