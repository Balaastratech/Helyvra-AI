"""Perf-optimization tests: assert Cognee call-counts/kwargs via monkeypatch.

These never hit real Cognee — they verify that the batching/deferral wiring
runs cognify the intended number of times with the intended params, so the
latency win holds without changing any answer (the ledger stays authoritative).
"""

import asyncio
from datetime import date

from app.memory import cognee_client
from app.engine import nodes as eng_nodes
from app.engine import service as eng_service
from app.memory.schema import ClinicalFact
import app.main as main_mod


def _capture_cognify(monkeypatch):
    """Replace cognee.cognify with a call-recording stub. Returns the calls list."""
    calls = []

    async def fake_cognify(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(cognee_client.cognee, "cognify", fake_cognify)
    return calls


def _fact(pid="P010", value="amlodipine 5mg"):
    return ClinicalFact(
        patient_id=pid, subject="medication", predicate="prescribed",
        value=value, valid_from=date(2026, 1, 1), source="Dr. Test",
        raw_text=f"On 2026-01-01, prescribed {value}.",
    )


# --- Task 1 ---------------------------------------------------------------
def test_cognify_passes_chunk_size_and_batch(monkeypatch):
    calls = _capture_cognify(monkeypatch)
    # No ontology config in the test env → cognify runs without `config`.
    monkeypatch.setattr(cognee_client, "_ontology_config", lambda: None)
    asyncio.run(cognee_client.cognify("P010", temporal=False))
    assert len(calls) == 1
    kw = calls[0]
    assert kw["datasets"] == ["tr_p010"]
    assert kw["temporal_cognify"] is False
    assert kw["chunk_size"] == 4096
    assert kw["data_per_batch"] == 20
    assert kw["chunks_per_batch"] == 100


# --- Task 3 ---------------------------------------------------------------
def test_persist_defer_skips_cognify(monkeypatch):
    add_calls, cognify_calls = [], []

    async def fake_add(fact):
        add_calls.append(fact)
        return None  # no data_id

    async def fake_cognify(*a, **k):
        cognify_calls.append((a, k))

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)

    state = {
        "patient_id": "P010", "new_fact": _fact(), "classification": "NEW",
        "cognee_sync": True, "defer_cognify": True, "actions": [],
    }
    asyncio.run(eng_nodes.persist(state))
    assert len(add_calls) == 1        # fact WAS added
    assert len(cognify_calls) == 0    # but cognify was DEFERRED


# --- Task 4 ---------------------------------------------------------------
def test_run_facts_cognifies_once(monkeypatch):
    cognify_calls = []

    async def fake_cognify(patient_id, temporal=True, **k):
        cognify_calls.append(patient_id)

    async def fake_add(fact):
        return None

    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)

    facts = [_fact(value="lisinopril 10mg"), _fact(value="amlodipine 5mg"),
             _fact(value="metformin 500mg")]
    asyncio.run(eng_service.run_facts("P010", facts, cognee_sync=True))
    # Three facts, but Cognee is cognified exactly ONCE (batched), not 3x.
    assert cognify_calls == ["P010"]


# --- Task 5 ---------------------------------------------------------------
def test_run_fact_bg_defers_and_schedules(monkeypatch):
    scheduled = []
    cognify_calls = []

    async def fake_add(fact):
        return None

    async def fake_cognify(patient_id, temporal=True, **k):
        cognify_calls.append(patient_id)

    def fake_schedule(coro):
        scheduled.append(coro)
        coro.close()  # don't actually run it in the test

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service, "_schedule", fake_schedule)

    state = asyncio.run(eng_service.run_fact_bg("P010", _fact()))
    assert state["classification"] in ("NEW", "SUPERSEDES", "CONSISTENT", "CONTRADICTS")
    assert len(scheduled) == 1        # cognify was scheduled, not awaited inline
    assert cognify_calls == []        # (the scheduled coro was not run in the test)


# --- Task 6 ---------------------------------------------------------------
def test_temporal_only_for_demo_patient(monkeypatch):
    seen = {}

    async def fake_cognify(patient_id, temporal=True, **k):
        seen[patient_id] = temporal

    async def fake_add(fact):
        return None

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)

    asyncio.run(eng_service.run_facts("P001", [_fact("P001")], cognee_sync=True))
    asyncio.run(eng_service.run_facts("P010", [_fact("P010")], cognee_sync=True))
    assert seen["P001"] is True    # supersession demo → temporal
    assert seen["P010"] is False   # everyone else → faster non-temporal


# --- Task 7 ---------------------------------------------------------------
def test_precompute_seed_runs_when_enabled(monkeypatch):
    called = []

    async def fake_precompute():
        called.append(True)

    monkeypatch.setenv("PRECOMPUTE_SEED", "1")
    monkeypatch.setattr(main_mod, "_precompute_seed", fake_precompute)
    asyncio.run(main_mod._maybe_precompute())
    assert called == [True]


def test_precompute_seed_skipped_when_disabled(monkeypatch):
    called = []

    async def fake_precompute():
        called.append(True)

    monkeypatch.delenv("PRECOMPUTE_SEED", raising=False)
    monkeypatch.setattr(main_mod, "_precompute_seed", fake_precompute)
    asyncio.run(main_mod._maybe_precompute())
    assert called == []
