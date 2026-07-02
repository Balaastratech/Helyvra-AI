"""Family auto-linkage (relative extraction → resolver → hereditary check)."""
from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi.testclient import TestClient

from app.checks import hereditary
from app.engine import extract as extract_mod
from app.intake import fhir
from app.intake import structured as S
from app.memory import ontology
from app.memory.schema import ClinicalFact


# --- Task 1: family_assert carries relative identity --------------------------
def test_family_assert_carries_relative_identity():
    a = S.family_assert(
        "father", "myocardial infarction", "2023-01-15",
        age_at_onset=49, relative_name="Rahul Sharma", relative_mrn="MRN-2010",
        relative_dob="1974-02-03", source="intake",
    )
    attrs = a["attributes"]
    assert attrs["relation"] == "father"
    assert attrs["condition"] == "myocardial infarction"
    assert attrs["relative_name"] == "Rahul Sharma"
    assert attrs["relative_mrn"] == "MRN-2010"
    assert attrs["relative_dob"] == "1974-02-03"


def test_family_assert_omits_blank_relative_fields():
    a = S.family_assert("mother", "breast cancer", "2022-05-01")
    assert "relative_name" not in a["attributes"]
    assert a["attributes"]["relation"] == "mother"


# --- Task 2: extraction (FHIR + free text) ------------------------------------
def test_fhir_family_history_captures_relative_name():
    res = {
        "resourceType": "FamilyMemberHistory",
        "name": "Rahul Sharma",
        "relationship": {"text": "father"},
        "date": "2023-01-15",
        "condition": [{"code": {"text": "myocardial infarction"},
                       "onsetAge": {"value": 49}}],
    }
    facts = fhir._parse_family_history(res)
    assert facts[0]["attributes"]["relative_name"] == "Rahul Sharma"
    assert facts[0]["attributes"]["relation"] == "father"


def test_rich_family_fact_maps_relative_name():
    rf = extract_mod._RichFact(
        resource_type="FamilyHistory", relation="father",
        condition="coronary artery disease", age_at_onset=49,
        relative_name="Rahul Sharma", relative_dob="1974-02-03",
    )
    a = extract_mod._rich_fact_to_assert(rf, "2023-01-15", "intake_form.txt")
    assert a["attributes"]["relative_name"] == "Rahul Sharma"
    assert a["attributes"]["relative_dob"] == "1974-02-03"


# --- Task 3: resolver ---------------------------------------------------------
def _fh_fact(pid, relation, condition, relative_name="", relative_mrn="", age=None):
    attrs = {"relation": relation, "condition": condition}
    if relative_name:
        attrs["relative_name"] = relative_name
    if relative_mrn:
        attrs["relative_mrn"] = relative_mrn
    if age is not None:
        attrs["age_at_onset"] = age
    return ClinicalFact(
        patient_id=pid, subject="family", predicate="reported",
        value=f"{relation}: {condition}", valid_from=date(2023, 1, 15),
        source="intake", resource_type="FamilyHistory", attributes=attrs,
    )


def test_resolver_links_relative_that_is_a_patient(tmp_path, monkeypatch):
    from app.intake import family_resolver as fr

    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))

    patients = [
        {"patient_id": "P010", "name": "Rahul Sharma", "dob": "1974-02-03", "mrn": "MRN-2010"},
        {"patient_id": "P020", "name": "Arjun Sharma", "dob": "1999-06-01", "mrn": "MRN-2020"},
    ]
    monkeypatch.setattr(fr.records, "list_patients", lambda: patients)

    facts = [_fh_fact("P020", "father", "coronary artery disease",
                      relative_mrn="MRN-2010", age=49)]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts if pid == "P020" else [])

    links = fr.resolve_links("P020")
    assert len(links) == 1
    assert links[0]["patient_id"] == "P020"
    assert links[0]["relative_id"] == "P010"
    assert links[0]["relation"] == "father"
    assert links[0]["confidence"] == "high"      # matched by MRN
    stored = json.loads((tmp_path / "family_links.json").read_text())
    pairs = {(l["patient_id"], l["relative_id"]) for l in stored["links"]}
    assert ("P020", "P010") in pairs and ("P010", "P020") in pairs


def test_resolver_matches_by_name_and_generation_without_mrn(tmp_path, monkeypatch):
    """The realistic path: no MRN in the note. Shared surname + a plausible
    parent/child age gap disambiguates two same-named patients and links the
    correct one with high confidence."""
    from app.intake import family_resolver as fr
    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))
    patients = [
        {"patient_id": "P010", "name": "Rahul Sharma", "dob": "1974-02-11", "mrn": "MRN-2010"},
        # same name, but born 1995 — only 4y older than the child, impossible as father
        {"patient_id": "P012", "name": "Rahul Sharma", "dob": "1995-05-19", "mrn": "MRN-2012"},
        {"patient_id": "P008", "name": "Arjun Sharma", "dob": "1999-06-01", "mrn": "MRN-2020"},
    ]
    monkeypatch.setattr(fr.records, "list_patients", lambda: patients)
    facts = [_fh_fact("P008", "father", "type 2 diabetes", relative_name="Rahul Sharma")]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts if pid == "P008" else [])

    links = fr.resolve_links("P008")
    assert len(links) == 1
    assert links[0]["relative_id"] == "P010"     # the age-plausible Rahul, not P012
    assert links[0]["confidence"] == "high"       # surname + generation, unambiguous


def test_resolver_name_only_match_is_proposed_medium(tmp_path, monkeypatch):
    """A unique name match with no corroboration (different surname, no DOBs) still
    links, but as a 'medium' PROPOSED link — never auto-consented."""
    from app.intake import family_resolver as fr
    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))
    patients = [
        {"patient_id": "P010", "name": "Rahul Verma", "dob": "", "mrn": "MRN-2010"},
        {"patient_id": "P008", "name": "Arjun Sharma", "dob": "", "mrn": "MRN-2020"},
    ]
    monkeypatch.setattr(fr.records, "list_patients", lambda: patients)
    facts = [_fh_fact("P008", "father", "type 2 diabetes", relative_name="Rahul Verma")]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts if pid == "P008" else [])

    links = fr.resolve_links("P008")
    assert len(links) == 1
    assert links[0]["relative_id"] == "P010"
    assert links[0]["confidence"] == "medium"     # proposed — needs one-click consent
    stored = json.loads((tmp_path / "family_links.json").read_text())
    assert all(l["consent"] is False for l in stored["links"])


def test_resolver_no_link_when_relative_unknown(tmp_path, monkeypatch):
    from app.intake import family_resolver as fr
    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))
    monkeypatch.setattr(fr.records, "list_patients",
                        lambda: [{"patient_id": "P020", "name": "Arjun Sharma", "dob": "", "mrn": "MRN-2020"}])
    facts = [_fh_fact("P020", "father", "coronary artery disease", relative_name="Someone Nobody")]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts)
    assert fr.resolve_links("P020") == []


# --- Task 4: Cognee Dedup graph ----------------------------------------------
def test_add_family_members_builds_dedup_datapoints(monkeypatch):
    captured = {}

    async def fake_add_dp(points, **kw):
        captured["points"] = points

    from app.memory import cognee_client
    monkeypatch.setattr(cognee_client, "_add_data_points", fake_add_dp)

    members = [
        {"patient_id": "P020", "name": "Arjun Sharma", "mrn": "MRN-2020",
         "relation_to_parent": "child", "parent_mrn": "MRN-2010"},
        {"patient_id": "P010", "name": "Rahul Sharma", "mrn": "MRN-2010",
         "relation_to_parent": None, "parent_mrn": None},
    ]
    asyncio.run(cognee_client.add_family_members(members))
    pts = captured["points"]
    by_mrn = {p.mrn: p for p in pts}
    assert by_mrn["MRN-2020"].parent is not None
    assert by_mrn["MRN-2020"].parent.mrn == "MRN-2010"


# --- Task 5: pipeline hook ----------------------------------------------------
def test_pipeline_runs_family_resolution(monkeypatch):
    called = {}
    from app.intake import pipeline as pl

    def fake_resolve(pid):
        called["pid"] = pid
        return []

    monkeypatch.setattr(pl, "family_resolver", type("M", (), {"resolve_links": staticmethod(fake_resolve)}))
    pl._resolve_family_safe("P020")
    assert called["pid"] == "P020"


# --- Task 6: is_heritable -----------------------------------------------------
def test_is_heritable():
    assert ontology.is_heritable("type 2 diabetes") is True
    assert ontology.is_heritable("coronary artery disease") is True
    assert ontology.is_heritable("sprained ankle") is False


# --- Task 7: hereditary check -------------------------------------------------
def _condition_fact(pid, condition, dt=date(2023, 1, 1)):
    return ClinicalFact(
        patient_id=pid, subject="diagnosis", predicate="diagnosed", value=condition,
        valid_from=dt, source="Dr. Test", resource_type="Condition",
        attributes={"condition": condition.lower()},
    )


def test_hereditary_card_when_consented_relative_has_heritable_dx(monkeypatch):
    monkeypatch.setattr(hereditary.family_resolver, "links_for",
                        lambda pid, consented_only=False: (
                            [{"patient_id": "P020", "relative_id": "P010", "relation": "father",
                              "confidence": "high", "consent": True}] if pid == "P020" else []))
    monkeypatch.setattr(hereditary.ledger, "all",
                        lambda pid: [_condition_fact("P010", "type 2 diabetes")] if pid == "P010" else [])
    monkeypatch.setattr(hereditary.records, "get_patient",
                        lambda pid: {"patient_id": pid, "name": "Rahul Sharma", "mrn": "MRN-2010"})

    cards = hereditary.run("P020")
    assert len(cards) == 1
    assert cards[0].indicator == "warning"
    assert "type 2 diabetes" in cards[0].detail.lower()
    assert "father" in cards[0].detail.lower()


def test_hereditary_degrades_without_consent(monkeypatch):
    monkeypatch.setattr(hereditary.family_resolver, "links_for",
                        lambda pid, consented_only=False: (
                            [{"patient_id": "P020", "relative_id": "P010", "relation": "father",
                              "confidence": "high", "consent": False}] if pid == "P020" else []))
    monkeypatch.setattr(hereditary.ledger, "all",
                        lambda pid: [_condition_fact("P010", "type 2 diabetes")] if pid == "P010" else [])
    monkeypatch.setattr(hereditary.records, "get_patient",
                        lambda pid: {"patient_id": pid, "name": "Rahul Sharma", "mrn": "MRN-2010"})

    cards = hereditary.run("P020")
    for c in cards:
        assert "rahul" not in c.detail.lower()
        assert "MRN-2010" not in c.detail


# --- Task 8: family API -------------------------------------------------------
def test_family_routes(monkeypatch):
    from app.api import routes_family
    monkeypatch.setattr(routes_family.family_resolver, "links_for",
                        lambda pid, consented_only=False: [
                            {"patient_id": pid, "relative_id": "P010", "relation": "father",
                             "confidence": "high", "consent": True}])
    monkeypatch.setattr(routes_family.family_resolver, "set_consent",
                        lambda a, b, c: True)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(routes_family.router)
    client = TestClient(app)

    r = client.get("/family/P020")
    assert r.status_code == 200
    assert r.json()["links"][0]["relative_id"] == "P010"

    r = client.post("/family/consent", json={"patient_id": "P020", "relative_id": "P010", "consent": False})
    assert r.status_code == 200 and r.json()["ok"] is True
