r"""
Day-1 foundation check (CLINICAL_COPILOT_PLAN §2): the FHIR-aligned fields added
to ClinicalFact derive correctly and survive a ledger round-trip. Offline — no
Vertex/Cognee. Run: .\.venv\Scripts\python.exe -m pytest tests/test_schema.py -q
"""

from datetime import date

from app.memory import ledger
from app.memory.schema import ClinicalFact


def test_resource_type_defaults_from_subject():
    # existing engine facts (subject only) become typed for free
    assert ClinicalFact(patient_id="P1", subject="allergy", predicate="diagnosed",
                        value="penicillin", valid_from=date(2026, 1, 1)).resource_type == "Allergy"
    assert ClinicalFact(patient_id="P1", subject="diagnosis", predicate="diagnosed",
                        value="t2dm", valid_from=date(2026, 1, 1)).resource_type == "Condition"
    # explicit resource_type is respected, not overwritten
    assert ClinicalFact(patient_id="P1", subject="note", predicate="x", value="y",
                        valid_from=date(2026, 1, 1), resource_type="LabResult").resource_type == "LabResult"
    # unknown subject leaves it unset rather than guessing
    assert ClinicalFact(patient_id="P1", subject="mystery", predicate="x", value="y",
                        valid_from=date(2026, 1, 1)).resource_type is None


def test_fhir_fields_round_trip_through_ledger():
    ledger.reset()
    f = ClinicalFact(
        patient_id="P1", subject="lab", predicate="measured", value="creatinine 1.6 mg/dL",
        valid_from=date(2026, 5, 1), source_document="DOC-9", page=2, ontology_valid=True,
        attributes={"analyte": "creatinine", "value": 1.6, "unit": "mg/dL",
                    "ref_range": "0.7-1.3", "abnormal_flag": "high"},
    )
    ledger.add(f)
    got = ledger.get(f.id)
    assert got is not None
    assert got.resource_type == "LabResult"
    assert got.page == 2
    assert got.ontology_valid is True
    assert got.attributes["abnormal_flag"] == "high"
    assert got.attributes["value"] == 1.6
