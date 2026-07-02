r"""
Day-2 acceptance (CLINICAL_COPILOT_PLAN §5.2): the clinical check engine on the
hero patient Rahul Sharma (P010).

Offline — checks read the authoritative ledger + the local ontology; no Vertex
or Cognee server. Seeds P010's FHIR-typed facts directly into the ledger (the
attribute shapes the intake extractor will populate in Day 3), then asserts:
  • opening P010 yields EXACTLY the 3 expected cards (renal gap, HbA1c rising,
    combined CV risk), each cited;
  • proposing amoxicillin yields the CRITICAL allergy card via beta-lactam
    cross-reactivity, citing the 2021 discharge summary page 2.

Run: .\.venv\Scripts\python.exe -m pytest tests/test_checks.py -q
"""

from datetime import date

import pytest

from app import checks
from app.memory import ledger
from app.memory.schema import ClinicalFact

PATIENT = "P010"
# Fixed reference date so the follow-up-window logic is deterministic (matches the
# synthetic data's "today").
AS_OF = date(2026, 6, 30)


def _fact(subject, predicate, fact_value, day, **attrs):
    # attrs is the FHIR attribute bag (may legitimately carry its own `value`,
    # e.g. a lab's numeric value) — keep it separate from the fact's text value.
    doc = attrs.pop("source_document", None)
    page = attrs.pop("page", None)
    title = attrs.pop("document_title", None)
    source = attrs.pop("source", "synthetic")
    return ClinicalFact(
        patient_id=PATIENT, subject=subject, predicate=predicate, value=fact_value,
        valid_from=day, source=source,
        source_document=doc, page=page, document_title=title, attributes=attrs,
    )


@pytest.fixture(scope="module")
def rahul():
    """Seed P010's chart: T2DM, severe penicillin allergy, rising HbA1c, rising
    creatinine w/ no renal follow-up, father early MI, smoker, high LDL."""
    ledger.reset()
    ledger.add(_fact("diagnosis", "diagnosed", "type 2 diabetes", date(2019, 3, 18),
                     condition="type 2 diabetes", source_document="P010_discharge_2019.pdf",
                     document_title="2019 discharge summary"))
    ledger.add(_fact("medication", "prescribed", "metformin 500mg", date(2019, 3, 18),
                     drug="metformin", drug_class="biguanide"))
    ledger.add(_fact("allergy", "diagnosed", "penicillin", date(2021, 8, 9),
                     substance="penicillin", drug_class="penicillin",
                     reaction="rash and breathing difficulty", severity="severe",
                     source_document="P010_discharge_2021.pdf", page=2,
                     document_title="2021 discharge summary"))
    ledger.add(_fact("family", "reported", "father myocardial infarction", date(2023, 1, 15),
                     relation="father", condition="myocardial infarction", age_at_onset=49,
                     source_document="P010_family_history.json",
                     document_title="family history"))
    ledger.add(_fact("lifestyle", "reported", "current smoker", date(2023, 1, 15),
                     factor="smoking", value="current smoker",
                     source_document="P010_intake_form.txt", document_title="intake form"))
    # labs
    ledger.add(_fact("lab", "measured", "HbA1c 7.8%", date(2024, 6, 12),
                     analyte="hba1c", value=7.8, unit="%", abnormal_flag="high",
                     source_document="P010_labs_2024.csv", document_title="2024 labs"))
    ledger.add(_fact("lab", "measured", "LDL 165", date(2024, 9, 5),
                     analyte="ldl", value=165, unit="mg/dL", abnormal_flag="high",
                     source_document="P010_labs_2024.csv", document_title="2024 labs"))
    ledger.add(_fact("lab", "measured", "creatinine 1.0", date(2024, 6, 12),
                     analyte="creatinine", value=1.0, unit="mg/dL", abnormal_flag="normal",
                     source_document="P010_labs_2024.csv", document_title="2024 labs"))
    ledger.add(_fact("lab", "measured", "HbA1c 8.6%", date(2025, 6, 18),
                     analyte="hba1c", value=8.6, unit="%", abnormal_flag="high",
                     source_document="P010_lab_hba1c_2025.pdf", document_title="2025 HbA1c report"))
    ledger.add(_fact("lab", "measured", "creatinine 1.6", date(2025, 12, 4),
                     analyte="creatinine", value=1.6, unit="mg/dL", abnormal_flag="high",
                     source_document="P010_lab_renal_2025.pdf", document_title="2025 renal panel"))
    ledger.add(_fact("lab", "measured", "HbA1c 8.9%", date(2026, 5, 8),
                     analyte="hba1c", value=8.9, unit="%", abnormal_flag="high",
                     source_document="P010_lab_recent.fhir.json", document_title="2026 labs"))
    yield PATIENT
    ledger.reset()


def _by_prefix(cards, prefix):
    return [c for c in cards if c.check_id.startswith(prefix)]


def test_open_brief_yields_exactly_three_cited_cards(rahul):
    cards = checks.run_open_checks(rahul, as_of=AS_OF)

    assert len(cards) == 3, [c.check_id for c in cards]
    # every not-to-miss card is cited (the thesis: never an uncited clinical claim)
    assert all(c.source for c in cards)
    assert all(s.date for c in cards for s in c.source)

    # 1. renal follow-up gap: creatinine 1.6, no nephrology follow-up
    gap = _by_prefix(cards, "followup_gap:gap:creatinine")
    assert len(gap) == 1
    assert "1.6" in gap[0].detail and gap[0].source[0].source_document == "P010_lab_renal_2025.pdf"

    # 2. HbA1c rising trend 7.8 -> 8.6 -> 8.9 (three cited readings)
    trend = _by_prefix(cards, "followup_gap:trend:hba1c")
    assert len(trend) == 1
    assert "7.8" in trend[0].summary and "8.9" in trend[0].summary
    assert len(trend[0].source) == 3

    # 3. combined CV risk: father MI<50 + smoker + LDL 165, each cited
    cv = _by_prefix(cards, "combined_risk:cardiovascular")
    assert len(cv) == 1
    docs = {s.source_document for s in cv[0].source}
    assert {"P010_family_history.json", "P010_intake_form.txt", "P010_labs_2024.csv"} <= docs
    assert "165" in cv[0].detail and "smoker" in cv[0].detail.lower()


def test_prescribe_amoxicillin_is_critical_via_cross_reactivity(rahul):
    cards = checks.run_prescribe_checks(rahul, "amoxicillin 500mg", as_of=AS_OF)

    assert len(cards) == 1
    card = cards[0]
    assert card.indicator == "critical"
    assert "penicillin" in card.detail.lower() and "beta-lactam" in card.detail.lower()
    # cites the 2021 discharge summary, page 2 (the evidence a doctor can open)
    assert card.source[0].source_document == "P010_discharge_2021.pdf"
    assert card.source[0].page == 2


def test_prescribe_non_conflicting_drug_is_clear(rahul):
    # a macrolide does not cross-react with a penicillin allergy — no false alarm
    assert checks.run_prescribe_checks(rahul, "azithromycin", as_of=AS_OF) == []
