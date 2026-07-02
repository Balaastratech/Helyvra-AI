"""
Phase 2 API acceptance tests (integration).

Drives the FastAPI app in-process via httpx ASGITransport. These make REAL
Vertex (judge + completions) and Cognee (add/cognify/recall) calls, so they are
slow (tens of seconds to a few minutes) and require ADC + the C:\\cg storage root.

Flow (run ONCE per module):
  seed -> ingest both held-back contradictions (the live heal)
       -> ask allergy (naive vs total_recall)
       -> graph snapshots at two dates
       -> why on the original allergy fact.

Deterministic assertions live on the ledger-backed surfaces (/graph, /why,
classification, healed). The LLM answer text is asserted loosely (the heal must
be reflected; the two modes must differ) to stay robust to phrasing.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

DATA = Path(__file__).resolve().parents[2] / "data" / "patient_timeline_01.json"
PATIENT = "P001"


@pytest.fixture(scope="module")
def flow():
    return asyncio.run(_run_flow())


async def _run_flow() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    held_entries = [e for e in data["facts"] if e.get("hold_back")]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        captured: dict = {}

        seed = (await c.post("/seed", json={"patient_id": PATIENT})).json()
        captured["seed"] = seed

        # id of the original (baseline) penicillin-allergy diagnosis.
        allergy_orig = next(
            f for f in seed["seeded"] if f["subject"] == "allergy"
        )
        captured["allergy_orig_id"] = allergy_orig["id"]

        # Live heal: ingest each held-back contradiction with structured fields.
        ingests = []
        for e in sorted(held_entries, key=lambda x: x["date"]):
            body = {
                "patient_id": PATIENT,
                "text": e.get("text", ""),
                "structured": {
                    "subject": e["subject"],
                    "predicate": e["predicate"],
                    "value": e["value"],
                    "date": e["date"],
                    "source": e.get("source", "unknown"),
                },
            }
            ingests.append((await c.post("/ingest", json=body)).json())
        captured["ingests"] = ingests

        # Ask the allergy question both ways (post-heal).
        q = {"patient_id": PATIENT, "question": "Is the patient allergic to penicillin?"}
        captured["ask_naive"] = (
            await c.post("/ask", json={**q, "mode": "naive"})
        ).json()
        captured["ask_smart"] = (
            await c.post("/ask", json={**q, "mode": "total_recall"})
        ).json()
        # Past-tense retention: as of February (before the clear), the patient
        # WAS allergic. Proves Cognee keeps the superseded fact (no hard-delete).
        captured["ask_past"] = (
            await c.post("/ask", json={**q, "mode": "total_recall", "as_of": "2026-02-15"})
        ).json()

        # Graph snapshots: allergy active in Feb, superseded by now.
        captured["graph_feb"] = (
            await c.get("/graph", params={"patient_id": PATIENT, "as_of": "2026-02-15"})
        ).json()
        captured["graph_now"] = (
            await c.get("/graph", params={"patient_id": PATIENT, "as_of": "2026-06-29"})
        ).json()

        # Provenance for the original allergy fact.
        captured["why"] = (
            await c.get("/why", params={"fact_id": captured["allergy_orig_id"]})
        ).json()

        # Raw Cognee graph.
        captured["cognee_graph"] = (
            await c.get("/graph/cognee", params={"patient_id": PATIENT})
        ).json()

        captured["health"] = (await c.get("/health")).json()

        # Forget flow: retract the diabetes diagnosis as "entered in error".
        diabetes = next(f for f in seed["seeded"] if f["subject"] == "diagnosis")
        captured["diabetes_id"] = diabetes["id"]
        captured["forget"] = (
            await c.post("/forget", json={
                "patient_id": PATIENT,
                "fact_id": diabetes["id"],
                "reason": "entered in error — wrong patient",
            })
        ).json()
        captured["graph_after_forget"] = (
            await c.get("/graph", params={"patient_id": PATIENT, "as_of": "2026-06-29"})
        ).json()

        print("\n" + "=" * 70)
        print("ASK CONTRAST (allergic to penicillin?)")
        print("  NAIVE       [", captured["ask_naive"]["search_type"], "]:",
              captured["ask_naive"]["answer"])
        print("  TOTAL_RECALL[", captured["ask_smart"]["search_type"], "]:",
              captured["ask_smart"]["answer"])
        print("  PAST as_of 2026-02-15 [", captured["ask_past"]["search_type"], "]:",
              captured["ask_past"]["answer"])
        print("=" * 70 + "\n")
        return captured


# --- /seed ----------------------------------------------------------------
def test_seed_baseline_and_holdback(flow):
    seed = flow["seed"]
    assert seed["patient_id"] == PATIENT
    subjects = {(f["subject"], f["predicate"]) for f in seed["seeded"]}
    # Baseline = allergy diagnosed + lisinopril prescribed + diabetes added.
    assert ("allergy", "diagnosed") in subjects
    assert ("medication", "prescribed") in subjects
    assert ("diagnosis", "added") in subjects
    # The two contradictions are held back, not seeded.
    held_labels = {h["label"] for h in seed["held_back"]}
    assert "allergy/cleared" in held_labels
    assert "medication/switched" in held_labels
    assert len(seed["seeded"]) == 3


# --- /ingest (the heal) ---------------------------------------------------
def test_ingest_clear_event_supersedes(flow):
    allergy_ingest = next(
        i for i in flow["ingests"] if i["fact"]["subject"] == "allergy"
    )
    assert allergy_ingest["classification"] == "SUPERSEDES"
    assert allergy_ingest["healed"] is True
    assert allergy_ingest["target_fact_id"] == flow["allergy_orig_id"]


def test_ingest_med_switch_supersedes(flow):
    med_ingest = next(
        i for i in flow["ingests"] if i["fact"]["subject"] == "medication"
    )
    assert med_ingest["classification"] == "SUPERSEDES"
    assert med_ingest["healed"] is True


# --- /ask contrast --------------------------------------------------------
def test_ask_search_types(flow):
    assert flow["ask_naive"]["search_type"] == "RAG_COMPLETION"
    # Smart path synthesizes from the full ledger history (cited, certainty-aware
    # per UPGRADE_PLAN §6) rather than a raw Cognee search type.
    assert flow["ask_smart"]["search_type"] == "SYNTHESIZED"


def test_ask_smart_reflects_heal(flow):
    naive = (flow["ask_naive"]["answer"] or "").lower()
    smart = (flow["ask_smart"]["answer"] or "").lower()
    assert smart, "total_recall answer should be non-empty"
    assert naive, "naive answer should be non-empty"
    # Smart must reflect the cleared allergy (not allergic).
    assert any(w in smart for w in ("no", "not", "clear", "negativ", "longer"))
    # The two modes must produce demonstrably different answers (the whole point).
    assert smart != naive
    # Naive (frozen pre-heal baseline) must still affirm the allergy = dangerous.
    assert "penicillin" in naive or "allerg" in naive or "yes" in naive


def test_ask_past_tense_retained(flow):
    """Superseded facts are NOT forgotten: as-of February the patient WAS allergic."""
    past = (flow["ask_past"]["answer"] or "").lower()
    assert flow["ask_past"]["search_type"] == "SYNTHESIZED"
    assert past, "past-tense answer should be non-empty"
    # As of 2026-02-15 (before the 2026-03-02 clear), the allergy was active.
    assert any(w in past for w in ("yes", "was", "allerg"))


# --- /graph snapshots -----------------------------------------------------
def test_graph_allergy_active_in_february(flow):
    g = flow["graph_feb"]
    orig = next(n for n in g["nodes"] if n["id"] == flow["allergy_orig_id"])
    assert orig["status"] == "active"


def test_graph_allergy_superseded_now(flow):
    g = flow["graph_now"]
    orig = next(n for n in g["nodes"] if n["id"] == flow["allergy_orig_id"])
    assert orig["status"] == "superseded"
    # A SUPERSEDED_BY edge must originate from the original allergy fact.
    assert any(
        e["type"] == "SUPERSEDED_BY" and e["source"] == flow["allergy_orig_id"]
        for e in g["edges"]
    )


# --- /why -----------------------------------------------------------------
def test_why_traces_clear_event(flow):
    why = flow["why"]
    assert why["superseded_by"] is not None
    assert why["source"] == "Dr. Lee"
    assert why["date"] == "2026-03-02"
    assert why["reason"]
    # Chain runs original -> clear-event.
    assert len(why["chain"]) >= 2


# --- /graph/cognee + /health ----------------------------------------------
def test_cognee_graph_nonempty(flow):
    cg = flow["cognee_graph"]
    assert isinstance(cg["nodes"], list)
    assert len(cg["nodes"]) > 0


def test_health_ok(flow):
    h = flow["health"]
    assert h["ledger"] == "up"
    assert h["cognee"] == "up"


# --- /forget (entered-in-error) -------------------------------------------
def test_forget_retracts_and_removes(flow):
    f = flow["forget"]
    # Cognee dropped the assertion (forget primitive actually fired).
    assert f["forgotten"] is True
    assert f["cognee"], "expected a Cognee deletion summary"
    assert f["fact"]["status"] == "retracted"
    assert "error" in f["fact"]["reason"].lower()
    # The retracted diabetes fact no longer appears in the fact-timeline graph.
    ids = {n["id"] for n in flow["graph_after_forget"]["nodes"]}
    assert flow["diabetes_id"] not in ids
