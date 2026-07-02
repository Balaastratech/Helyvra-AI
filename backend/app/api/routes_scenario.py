"""
Scenario routes: /seed, /ingest, /reset.

`/seed`   loads the BASELINE timeline (everything NOT flagged `hold_back`) so the
          contradictions can be applied live via `/ingest` to demo the heal.
`/ingest` runs one fact through the self-healing engine (the live heal).
`/reset`  wipes ledger + Cognee + engine checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from app.api.dto import (
    ForgetRequest,
    ForgetResponse,
    HeldBack,
    IngestRequest,
    IngestResponse,
    ResetRequest,
    ResetResponse,
    SeedRequest,
    SeedResponse,
)
from app.engine import extract, service
from app.memory import cognee_client, ledger
from app.memory.schema import ClinicalFact

router = APIRouter(tags=["scenario"])

# data/patient_timeline_01.json (repo-root/data, like run.py).
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _timeline_path(patient_id: str) -> Path:
    # P001 -> patient_timeline_01.json (default demo file).
    if patient_id.upper() == "P001":
        return _DATA_DIR / "patient_timeline_01.json"
    # Generic fallback: patient_timeline_<n>.json by trailing digits.
    digits = "".join(c for c in patient_id if c.isdigit()) or "01"
    return _DATA_DIR / f"patient_timeline_{int(digits):02d}.json"


@router.post("/seed", response_model=SeedResponse)
async def seed(req: SeedRequest) -> SeedResponse:
    """Reset everything, then load baseline facts (holding back contradictions)."""
    path = _timeline_path(req.patient_id)
    if not path.exists():
        raise HTTPException(404, f"timeline not found: {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    patient_id = data["patient_id"]

    # Fresh slate: ledger, Cognee memory, engine checkpoints.
    ledger.reset()
    await cognee_client.seed_reset()
    service.reset_checkpoints()

    entries = sorted(data["facts"], key=lambda e: e["date"])
    baseline = [e for e in entries if not e.get("hold_back")]
    held = [e for e in entries if e.get("hold_back")]

    baseline_facts: List[ClinicalFact] = [
        ClinicalFact.from_timeline_entry(patient_id, e) for e in baseline
    ]
    # Push baseline through the engine (ledger + Cognee add/cognify). No subject
    # collisions in the baseline set -> all classify NEW, zero judge calls.
    await service.run_facts(patient_id, baseline_facts, cognee_sync=True)

    # Mirror the baseline into the never-healed naive dataset (the villain).
    for f in baseline_facts:
        await cognee_client.add_naive(f)
    await cognee_client.cognify_naive(patient_id)

    seeded = [ledger.get(f.id) for f in baseline_facts]
    seeded = [f for f in seeded if f is not None]
    held_back = [
        HeldBack(label=f"{e['subject']}/{e['predicate']}", text=e.get("text", ""))
        for e in held
    ]
    return SeedResponse(patient_id=patient_id, seeded=seeded, held_back=held_back)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    """Run one fact (text and/or structured) through the self-healing engine."""
    try:
        fact = extract.build_fact(req.patient_id, req.text, req.structured)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    result = await service.run_fact(req.patient_id, fact, cognee_sync=True)

    # NOTE: we deliberately do NOT feed the naive dataset here. The naive baseline
    # is frozen at the pre-heal snapshot (seed-time baseline) so it keeps answering
    # with the stale/dangerous fact — that is what makes the smart-vs-naive contrast
    # reproducible (docs/phase-2.md Risk E: otherwise RAG reads the correction too
    # and "accidentally" self-corrects, collapsing the contrast).
    classification = result.get("classification", "NEW")
    final = ledger.get(fact.id) or fact
    return IngestResponse(
        fact=final,
        classification=classification,
        target_fact_id=result.get("target_fact_id"),
        reason=result.get("reason", ""),
        healed=classification in ("SUPERSEDES", "CONTRADICTS"),
        actions=list(result.get("actions") or []),
    )


@router.post("/reset", response_model=ResetResponse)
async def reset(req: ResetRequest) -> ResetResponse:
    """Wipe ledger + Cognee memory + engine checkpoints."""
    ledger.reset()
    await cognee_client.seed_reset()
    service.reset_checkpoints()
    return ResetResponse(ok=True, patient_id=req.patient_id)


@router.post("/forget", response_model=ForgetResponse)
async def forget(req: ForgetRequest) -> ForgetResponse:
    """
    Retract a fact ENTERED IN ERROR: remove its assertion from Cognee memory and
    mark it retracted in the ledger (audit kept). If it had superseded an older
    fact, restore that older fact to active. This is the ONE legitimate use of
    Cognee's `forget()` primitive (supersession retains history instead).
    """
    fact = ledger.get(req.fact_id)
    if fact is None:
        raise HTTPException(404, f"fact not found: {req.fact_id}")

    cognee_result: dict = {}
    forgotten = False
    if fact.cognee_data_id:
        try:
            cognee_result = await cognee_client.forget_fact(fact.cognee_data_id, req.patient_id)
            forgotten = True
        except Exception as exc:  # pragma: no cover - defensive
            cognee_result = {"error": f"{type(exc).__name__}: {exc}"}

    retracted, restored = ledger.retract(req.fact_id, req.reason)
    return ForgetResponse(
        fact=retracted or fact,
        restored=restored,
        forgotten=forgotten,
        cognee=cognee_result,
    )
