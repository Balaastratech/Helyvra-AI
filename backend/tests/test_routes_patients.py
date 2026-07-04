"""
Manual chart creation is create-or-find (offline).

POST /patients must run the SAME match rule intake uses (patient_index.find)
before creating, so re-creating an existing patient returns the existing chart
instead of a duplicate. Isolated onto tmp JSON files so the real demo data is
untouched.
"""

from __future__ import annotations

import pytest

from app.api import routes_patients
from app.api.dto import CreatePatientRequest
from app.memory import records


@pytest.fixture()
def isolated_records(tmp_path, monkeypatch):
    monkeypatch.setattr(records, "_PATIENTS_FILE", tmp_path / "patients.json")
    monkeypatch.setattr(records, "_USER_PATIENTS_FILE", tmp_path / "patients_user.json")
    return tmp_path


def test_recreate_same_name_dob_returns_existing_chart(isolated_records):
    p1 = routes_patients.create_patient(CreatePatientRequest(name="Jane Roe", dob="1980-05-01"))
    # Same person, different casing/punctuation — the normalized name+DOB rule
    # must still resolve to the first chart, not a second one.
    p2 = routes_patients.create_patient(CreatePatientRequest(name="jane  roe", dob="1980-05-01"))

    assert p2.patient_id == p1.patient_id
    assert len(records.list_patients()) == 1


def test_recreate_same_mrn_returns_existing_chart(isolated_records):
    p1 = routes_patients.create_patient(CreatePatientRequest(name="John Doe", mrn="MRN-42"))
    p2 = routes_patients.create_patient(CreatePatientRequest(name="Totally Different", mrn="MRN-42"))

    assert p2.patient_id == p1.patient_id
    assert len(records.list_patients()) == 1


def test_distinct_patients_still_create_separate_charts(isolated_records):
    a = routes_patients.create_patient(CreatePatientRequest(name="Alice A", dob="1990-01-01"))
    b = routes_patients.create_patient(CreatePatientRequest(name="Bob B", dob="1991-02-02"))

    assert a.patient_id != b.patient_id
    assert len(records.list_patients()) == 2
