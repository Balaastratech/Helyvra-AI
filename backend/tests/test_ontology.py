"""
Day-1 ontology + grounding check (CLINICAL_COPILOT_PLAN §4). Offline — the OWL
parse + fuzzy match are local (no Vertex/Cognee server). Run:
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ontology.py -q
"""

from datetime import date

from app.memory import cognee_client, ontology
from app.memory.schema import ClinicalFact


def _fact(subject, value, resource_type=None, attributes=None):
    return ClinicalFact(
        patient_id="P1", subject=subject, predicate="x", value=value,
        valid_from=date(2026, 1, 1), resource_type=resource_type, attributes=attributes or {},
    )


def test_drug_class_and_beta_lactam_cross_reactivity():
    assert ontology.drug_class("amoxicillin 500mg") == "penicillin"
    assert ontology.drug_class("cephalexin") == "cephalosporin"
    # the clinically critical case: penicillin allergy contraindicates a cephalosporin
    assert ontology.are_cross_reactive("penicillin", "cephalexin") is True
    assert ontology.are_cross_reactive("amoxicillin", "meropenem") is True  # carbapenem too
    # a non-beta-lactam must NOT cross-react (no false alarm)
    assert ontology.are_cross_reactive("penicillin", "azithromycin") is False


def test_condition_monitoring_and_family_risk():
    assert ontology.monitoring_for("type 2 diabetes") == [{"analyte": "hba1c", "every_months": 3}]
    assert any(r["analyte"] == "creatinine" for r in ontology.monitoring_for("chronic kidney disease"))
    assert ontology.family_risk_for("myocardial infarction") == "cardiovascular"
    assert ontology.is_first_degree("father") and not ontology.is_first_degree("cousin")


def test_ground_fact_flags_known_vs_hallucinated():
    # known clinical entities ground True
    assert cognee_client.ground_fact(_fact("medication", "amoxicillin 500mg")) is True
    assert cognee_client.ground_fact(_fact("diagnosis", "type 2 diabetes")) is True
    assert cognee_client.ground_fact(_fact("allergy", "penicillin")) is True
    # a made-up entity grounds False (the Evidence Validator's hallucination flag)
    assert cognee_client.ground_fact(_fact("medication", "unicorn dust")) is False
    # ontology_valid is set on the fact, not just returned
    f = _fact("medication", "atorvastatin")
    cognee_client.ground_fact(f)
    assert f.ontology_valid is True
