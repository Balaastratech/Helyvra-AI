"""
Phase 1 acceptance tests (deterministic, temp 0).

Ingests `patient_timeline_01.json` through the self-healing engine with Cognee
sync OFF (the ledger + judge are what we assert on; Cognee is exercised by
run.py). One synthetic re-stated fact is appended to prove CONSISTENT.

These tests make REAL Vertex judge calls (temperature 0) on the 3 subject
collisions only — the dedupe gate keeps the other 3 ingests LLM-free.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path

import pytest

from app.engine import graph as graph_mod
from app.engine import nodes
from app.engine import judge as judge_mod
from app.memory import ledger
from app.memory.schema import ClinicalFact

DATA = Path(__file__).resolve().parents[2] / "data" / "patient_timeline_01.json"


@pytest.fixture(scope="module")
def run_result():
    """
    Ingest the full timeline + a restated fact ONCE for the module.

    Returns a dict with:
      facts:           {key -> ClinicalFact (the ingested input, for ids)}
      classifications: {key -> classification string}
      targets:         {key -> target_fact_id}
      judge_calls:     int (real LLM calls made)
    """
    # Spy on the judge to count real LLM calls (collisions only).
    real_classify = judge_mod.classify
    counter = {"n": 0}

    def counting_classify(new_fact, related, context=None):
        counter["n"] += 1
        return real_classify(new_fact, related, context=context)

    judge_mod.classify = counting_classify  # nodes call judge_mod.classify at runtime
    try:
        result = asyncio.run(_ingest_all())
    finally:
        judge_mod.classify = real_classify

    result["judge_calls"] = counter["n"]
    return result


async def _ingest_all():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    patient_id = data["patient_id"]

    ledger.reset()
    # Clear any prior checkpoint thread so re-runs start clean.
    cp = os.environ["ENGINE_CHECKPOINTS"]
    if os.path.exists(cp):
        os.remove(cp)

    entries = sorted(data["facts"], key=lambda e: e["date"])

    facts: dict = {}
    classifications: dict = {}
    targets: dict = {}

    def key_for(entry):
        return f"{entry['subject']}/{entry['predicate']}"

    async with graph_mod.checkpointer() as saver:
        app = graph_mod.build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": patient_id}}

        for entry in entries:
            fact = ClinicalFact.from_timeline_entry(patient_id, entry)
            k = key_for(entry)
            facts[k] = fact
            res = await app.ainvoke(
                {"patient_id": patient_id, "new_fact": fact, "cognee_sync": False}, cfg
            )
            classifications[k] = res["classification"]
            targets[k] = res.get("target_fact_id")

        # Synthetic re-stated fact: re-affirm the diabetes diagnosis -> CONSISTENT.
        restate = ClinicalFact(
            patient_id=patient_id,
            subject="diagnosis",
            predicate="added",
            value="type 2 diabetes",
            valid_from=date(2026, 6, 1),
            source="Dr. Patel",
            raw_text="On 2026-06-01, patient P001's type 2 diabetes diagnosis was re-confirmed.",
        )
        facts["restate"] = restate
        res = await app.ainvoke(
            {"patient_id": patient_id, "new_fact": restate, "cognee_sync": False}, cfg
        )
        classifications["restate"] = res["classification"]
        targets["restate"] = res.get("target_fact_id")

    return {
        "patient_id": patient_id,
        "facts": facts,
        "classifications": classifications,
        "targets": targets,
    }


# --- classification assertions --------------------------------------------
def test_allergy_clear_supersedes(run_result):
    assert run_result["classifications"]["allergy/cleared"] == "SUPERSEDES"
    # Target must be the original penicillin-allergy diagnosis.
    assert run_result["targets"]["allergy/cleared"] == run_result["facts"]["allergy/diagnosed"].id


def test_med_switch_supersedes(run_result):
    assert run_result["classifications"]["medication/switched"] == "SUPERSEDES"
    assert run_result["targets"]["medication/switched"] == run_result["facts"]["medication/prescribed"].id


def test_diabetes_is_new(run_result):
    assert run_result["classifications"]["diagnosis/added"] == "NEW"


def test_restated_fact_is_consistent(run_result):
    assert run_result["classifications"]["restate"] == "CONSISTENT"


# --- ledger state assertions ----------------------------------------------
def test_penicillin_allergy_superseded(run_result):
    f = ledger.get(run_result["facts"]["allergy/diagnosed"].id)
    assert f.status == "superseded"
    assert f.valid_to == date(2026, 3, 2)
    assert f.superseded_by == run_result["facts"]["allergy/cleared"].id


def test_lisinopril_superseded_by_amlodipine(run_result):
    f = ledger.get(run_result["facts"]["medication/prescribed"].id)
    assert f.status == "superseded"
    assert f.superseded_by == run_result["facts"]["medication/switched"].id


def test_diabetes_active(run_result):
    f = ledger.get(run_result["facts"]["diagnosis/added"].id)
    assert f.status == "active"


def test_current_active_set(run_result):
    active = {(f.subject, f.value) for f in ledger.all(run_result["patient_id"]) if f.status == "active"}
    # Current truth: allergy CLEARED, on amlodipine, has diabetes.
    assert ("allergy", "penicillin") in active          # the clear-event (NOT-allergic) fact
    assert ("medication", "amlodipine 5mg") in active
    assert ("diagnosis", "type 2 diabetes") in active
    # The stale facts must NOT be active.
    assert ("medication", "lisinopril 10mg") not in active


def test_supersession_chain(run_result):
    chain = ledger.chain(run_result["facts"]["medication/prescribed"].id)
    values = [f.value for f in chain]
    assert values == ["lisinopril 10mg", "amlodipine 5mg"]


# --- determinism / cost gate ----------------------------------------------
def test_judge_only_on_collisions(run_result):
    # 2 supersessions + 1 restate = 3 real judge calls. The other 3 ingests
    # (first allergy, first medication, diabetes) are gated out (no LLM).
    assert run_result["judge_calls"] == 3
