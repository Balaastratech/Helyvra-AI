"""
Agent tool-scoping tests (offline — no Vertex/Cognee calls).

The security-critical property of the real agent is that its tools are bound to
ONE patient via closures, so it can never reach another patient's data even if
the user names that patient. These tests assert that property directly against
the ledger, without invoking the model.
"""

from __future__ import annotations

import asyncio
from datetime import date

from app.agent import pending
from app.agent import router as agent_router
from app.agent import tools as agent_tools
from app.memory import ledger
from app.memory.schema import ClinicalFact


def _seed_two_patients():
    ledger.reset()
    # Patient A: a diabetes diagnosis. Patient B: a penicillin allergy.
    ledger.add(ClinicalFact(
        patient_id="PA", subject="diagnosis", predicate="added",
        value="type 2 diabetes", valid_from=date(2024, 1, 1), source="Dr. A",
    ))
    ledger.add(ClinicalFact(
        patient_id="PB", subject="allergy", predicate="diagnosed",
        value="penicillin", valid_from=date(2024, 1, 1), source="Dr. B",
    ))


def test_declarations_never_expose_patient_id():
    """The model must not see a patient_id arg on any tool — scoping is closure-bound."""
    for decl in agent_tools.declarations():
        props = (decl.parameters.properties or {}) if decl.parameters else {}
        assert "patient_id" not in props, f"{decl.name} leaks patient_id to the model"


def test_propose_forget_cannot_reach_another_patients_fact():
    """Tools built for PA must not be able to even propose forgetting PB's allergy."""
    _seed_two_patients()
    tools_map, _decls, log = agent_tools.build_patient_tools("PA")

    # Ask PA's correction tool about "penicillin" — which only exists for PB.
    result = tools_map["propose_forget"](target="penicillin", reason="test")

    assert "no active fact matching" in result.lower()
    assert not any(a.get("pending") for a in log)  # nothing staged
    # PB's allergy is untouched.
    pb = [f for f in ledger.all("PB") if f.subject == "allergy"][0]
    assert pb.status == "active"


def test_propose_forget_stages_but_does_not_delete():
    """propose_forget stages a pending correction; the fact stays active until approval."""
    _seed_two_patients()
    ledger.add(ClinicalFact(
        patient_id="PA", subject="allergy", predicate="diagnosed",
        value="penicillin", valid_from=date(2024, 2, 1), source="Dr. A",
    ))
    tools_map, _decls, log = agent_tools.build_patient_tools("PA")

    result = tools_map["propose_forget"](target="penicillin", reason="entered in error")

    assert "proposed" in result.lower()
    staged = [a for a in log if a.get("pending")]
    assert len(staged) == 1
    # NOT deleted yet — the fact is still active until /chat/approve runs.
    pa_allergy = [f for f in ledger.all("PA") if f.subject == "allergy"][0]
    assert pa_allergy.status == "active"

    # Approving via execute_forget retracts it; PB's stays separate and active.
    pid = staged[0]["pending"]["pending_id"]
    proposal = pending.get_pending(pid)
    assert proposal is not None
    retracted, _restored = asyncio.run(
        agent_tools.execute_forget(proposal["patient_id"], proposal["fact_id"], proposal["reason"])
    )
    assert retracted is not None
    pa_allergy = [f for f in ledger.all("PA") if f.subject == "allergy"][0]
    pb_allergy = [f for f in ledger.all("PB") if f.subject == "allergy"][0]
    assert pa_allergy.status == "retracted"
    assert pb_allergy.status == "active"


def test_ingest_fact_is_idempotent():
    """A duplicate ingest of the same text for the same patient must not double-write."""
    _seed_two_patients()
    pending._idempotency.clear()
    # Pre-seed the idempotency cache so we don't need a live model call: the second
    # call must short-circuit to the deduped path without touching the ledger.
    key = pending.make_key("PA", "Patient now on lisinopril 10mg")
    pending.record_write(key, "Recorded 'On lisinopril 10mg' (classification: NEW).")
    tools_map, _decls, log = agent_tools.build_patient_tools("PA")

    result = asyncio.run(tools_map["ingest_fact"](text="Patient now on lisinopril 10mg"))

    assert "already recorded" in result.lower() or "recorded" in result.lower()
    assert any(a.get("deduped") for a in log)
    # No new medication fact was written by the deduped call.
    assert not any(f.subject == "medication" for f in ledger.all("PA"))


def test_why_changed_is_patient_scoped():
    """why_changed for PA reports PA's subject only, never PB's."""
    _seed_two_patients()
    tools_map, _decls, _log = agent_tools.build_patient_tools("PA")
    # PA has no allergy; PB does. PA's tool must not surface PB's penicillin.
    narrative = tools_map["why_changed"](subject="allergy")
    assert "penicillin" not in narrative.lower()


def test_system_prompt_forces_grounding():
    """Forced-grounding invariant (audit §2.5): the agent must be told it may never
    answer a clinical question from its own knowledge and must call
    recall_patient_facts. This guards the prompt — if the constraint is removed,
    this fails. (The live model-level assertion runs in integration, online.)"""
    sys = agent_router._SYSTEM.lower()
    assert "recall_patient_facts" in sys
    assert "never" in sys and "own knowledge" in sys
    # recall must be an available tool for grounding to be possible at all.
    assert any(d.name == "recall_patient_facts" for d in agent_tools.declarations())
