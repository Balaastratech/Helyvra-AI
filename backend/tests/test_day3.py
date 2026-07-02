r"""
Day-3 acceptance (CLINICAL_COPILOT_PLAN §5.1/§5.3/§5.4/§7).

Offline — exercises the new clinical agent tools against the authoritative ledger
+ ontology, the evidence validator, the simulated access layer, and the real audit
trail. No Vertex/Cognee server (recall/ingest, which call the model, are covered by
test_agent.py's scoping tests + online integration).

Run: .\.venv\Scripts\python.exe -m pytest tests/test_day3.py -q
"""

from datetime import date

import pytest

from app import audit, auth
from app.agent import tools as agent_tools
from app.engine.answer import SynthesizedAnswer, Citation, validate_answer
from app.memory import ledger
from app.memory.schema import ClinicalFact

PATIENT = "P010"


def _fact(subject, predicate, fact_value, day, **attrs):
    doc = attrs.pop("source_document", None)
    page = attrs.pop("page", None)
    title = attrs.pop("document_title", None)
    source = attrs.pop("source", "synthetic")
    return ClinicalFact(
        patient_id=PATIENT, subject=subject, predicate=predicate, value=fact_value,
        valid_from=day, source=source,
        source_document=doc, page=page, document_title=title, attributes=attrs,
    )


@pytest.fixture()
def rahul():
    ledger.reset()
    ledger.add(_fact("diagnosis", "diagnosed", "type 2 diabetes", date(2019, 3, 18),
                     condition="type 2 diabetes"))
    ledger.add(_fact("allergy", "diagnosed", "penicillin", date(2021, 8, 9),
                     substance="penicillin", drug_class="penicillin",
                     reaction="rash and breathing difficulty", severity="severe",
                     source_document="P010_discharge_2021.pdf", page=2,
                     document_title="2021 discharge summary"))
    ledger.add(_fact("family", "reported", "father myocardial infarction", date(2023, 1, 15),
                     relation="father", condition="myocardial infarction", age_at_onset=49,
                     source_document="P010_family_history.json"))
    ledger.add(_fact("lifestyle", "reported", "current smoker", date(2023, 1, 15),
                     factor="smoking", value="current smoker",
                     source_document="P010_intake_form.txt"))
    ledger.add(_fact("lab", "measured", "LDL 165", date(2024, 9, 5),
                     analyte="ldl", value=165, unit="mg/dL", abnormal_flag="high",
                     source_document="P010_labs_2024.csv"))
    ledger.add(_fact("lab", "measured", "creatinine 1.6", date(2025, 12, 4),
                     analyte="creatinine", value=1.6, unit="mg/dL", abnormal_flag="high",
                     source_document="P010_lab_renal_2025.pdf"))
    yield PATIENT
    ledger.reset()


# --- §5.1 new tools --------------------------------------------------------

def test_propose_order_amoxicillin_is_critical_and_writes_nothing(rahul):
    """"can I prescribe amoxicillin?" -> a critical allergy card, cited, no write."""
    before = len(ledger.all(rahul))
    tools_map, _decls, log = agent_tools.build_patient_tools(rahul)

    result = tools_map["propose_order"](drug="amoxicillin 500mg")

    assert "penicillin" in result.lower() and "critical" in result.lower()
    entry = next(a for a in log if a["tool"] == "propose_order")
    cards = entry["cards"]
    assert len(cards) == 1 and cards[0]["indicator"] == "critical"
    assert cards[0]["source"][0]["source_document"] == "P010_discharge_2021.pdf"
    # a safety screen must not mutate the ledger
    assert len(ledger.all(rahul)) == before


def test_propose_order_safe_drug_is_clear(rahul):
    tools_map, _decls, log = agent_tools.build_patient_tools(rahul)
    result = tools_map["propose_order"](drug="azithromycin")
    assert "no allergy" in result.lower()
    entry = next(a for a in log if a["tool"] == "propose_order")
    assert entry["cards"] == []


def test_run_clinical_checks_surfaces_cited_cards(rahul):
    tools_map, _decls, log = agent_tools.build_patient_tools(rahul)
    tools_map["run_clinical_checks"](focus="")
    entry = next(a for a in log if a["tool"] == "run_clinical_checks")
    assert entry["cards"], "expected not-to-miss cards"
    assert all(c["source"] for c in entry["cards"])  # never an uncited clinical claim


def test_get_timeline_is_chronological_and_scoped(rahul):
    tools_map, _decls, log = agent_tools.build_patient_tools(rahul)
    result = tools_map["get_timeline"]()
    entry = next(a for a in log if a["tool"] == "get_timeline")
    dates = [e["date"] for e in entry["timeline"]]
    assert dates == sorted(dates)
    assert "type 2 diabetes" in result.lower()


def test_new_tools_never_expose_patient_id():
    """Scoping stays closure-bound for the new tools too (no patient_id arg)."""
    names = {"run_clinical_checks", "propose_order", "get_timeline"}
    for decl in agent_tools.declarations():
        if decl.name in names:
            props = (decl.parameters.properties or {}) if decl.parameters else {}
            assert "patient_id" not in props


# --- §5.4 evidence validator ----------------------------------------------

def test_validator_hedges_ungrounded_confident_answer():
    ans = SynthesizedAnswer(answer_text="The patient is allergic to penicillin.",
                            certainty="settled")  # no citations
    out = validate_answer(ans)
    assert out.certainty == "low_confidence"      # can't stay settled without evidence
    assert "verify" in out.answer_text.lower()
    assert out.validation["grounded"] is False


def test_validator_keeps_grounded_answer_settled():
    ans = SynthesizedAnswer(
        answer_text="Active penicillin allergy.", certainty="settled",
        citations=[Citation(fact_id="f1", source_document="d.pdf")],
    )
    out = validate_answer(ans)
    assert out.certainty == "settled"
    assert out.validation["grounded"] is True and out.validation["conflicting"] is False


def test_validator_flags_contested_conflict():
    ans = SynthesizedAnswer(
        answer_text="Records disagree.", certainty="contested",
        citations=[Citation(fact_id="f1")],
    )
    out = validate_answer(ans)
    assert out.validation["conflicting"] is True


# --- §7 access + audit -----------------------------------------------------

def test_access_boundary_enforced():
    assert auth.can_access("dr_mehta", "P010") is True
    assert auth.can_access("nurse_kim", "P010") is False   # not on the nurse's list
    assert auth.can_access("ghost", "P001") is False        # unknown doctor


def test_audit_is_appended_and_readable():
    audit.init()
    audit.log("dr_mehta", "order_check", "P010",
              decision="critical: penicillin allergy", evidence_ids=["fX"])
    entries = audit.recent(patient_id="P010")
    assert entries and entries[0]["action"] == "order_check"
    assert entries[0]["doctor"] == "dr_mehta"
    assert "fX" in entries[0]["evidence_ids"]
