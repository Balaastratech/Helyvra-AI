"""
Engine service seam for the API layer.

`/seed` and `/ingest` both need to push a single `ClinicalFact` through the
self-healing LangGraph engine. This module owns that one operation so the
routers stay thin and there is exactly one engine entry-point.

Each ingest runs on its OWN checkpoint thread (`{patient_id}:{fact.id}`) so the
returned `actions`/`classification` reflect just that fact (no state bleed from
a prior invoke on the same patient thread), while checkpoints still persist and
stay inspectable.
"""

from __future__ import annotations

import asyncio
import os
from typing import List

from app.engine.graph import build_graph, checkpointer
from app.engine.state import TRState
from app.memory import cognee_client
from app.memory.schema import ClinicalFact

_CHECKPOINT_DB = os.environ.get("ENGINE_CHECKPOINTS", r"C:\cg\engine_checkpoints.sqlite")

# Patients that need temporal_cognify (the time-scrubber / "as of" demo). Everyone
# else gets the faster non-temporal build — correctness is unaffected because the
# ledger holds valid_from/valid_to and drives "as of" answers.
_TEMPORAL_PATIENTS = set(
    p.strip() for p in os.environ.get("TEMPORAL_PATIENTS", "P001").split(",") if p.strip()
)


def _wants_temporal(patient_id: str) -> bool:
    return patient_id.strip() in _TEMPORAL_PATIENTS


def reset_checkpoints() -> None:
    """Delete the engine checkpoint DB (+ WAL/SHM) for a clean demo reseed."""
    for suffix in ("", "-wal", "-shm"):
        p = _CHECKPOINT_DB + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:  # pragma: no cover - file lock on Windows; best effort
                pass


async def run_fact(patient_id: str, fact: ClinicalFact, cognee_sync: bool = True) -> TRState:
    """Ingest ONE fact through the engine and return the final state."""
    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": f"{patient_id}:{fact.id}"}}
        return await app.ainvoke(
            {"patient_id": patient_id, "new_fact": fact, "cognee_sync": cognee_sync},
            cfg,
        )


async def run_facts(
    patient_id: str, facts: List[ClinicalFact], cognee_sync: bool = True,
    cognify_after: bool = True,
) -> List[TRState]:
    """Ingest several facts in order, then cognify ONCE (perf: not per fact).

    Each fact still flows through the full engine (recall→judge→reconcile→persist)
    and the ledger is updated per fact — only the expensive Cognee graph build is
    batched to the end, which does not change any answer (the ledger is truth).

    `cognify_after=False` skips even that one graph build — for a multi-FILE
    batch (pipeline.run_batch), where the caller does ONE cognify after every
    file's facts are in, instead of once per file. Cognify's cost scales with
    the patient's total accumulated facts, so doing it once per file in an
    N-file drop re-pays that growing cost N times."""
    results: List[TRState] = []
    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        for fact in facts:
            cfg = {"configurable": {"thread_id": f"{patient_id}:{fact.id}"}}
            res = await app.ainvoke(
                {
                    "patient_id": patient_id, "new_fact": fact,
                    "cognee_sync": cognee_sync, "defer_cognify": cognee_sync,
                },
                cfg,
            )
            results.append(res)
    if cognee_sync and cognify_after:
        # One graph build for the whole batch. Best-effort: a Cognee lag must not
        # break the ingest (the ledger already holds the authoritative result).
        try:
            healed = any(
                r.get("classification") in ("SUPERSEDES", "CONTRADICTS") for r in results
            )
            await cognee_client.cognify(patient_id, temporal=_wants_temporal(patient_id))
            if healed:
                try:
                    await cognee_client.improve(patient_id)
                except Exception:  # pragma: no cover - best-effort
                    pass
        except Exception:  # pragma: no cover - Cognee lag never breaks ingest
            pass
    return results


def _schedule(coro) -> None:
    """Fire-and-forget a coroutine on the running loop (seam for tests)."""
    asyncio.create_task(coro)


async def _cognify_bg(patient_id: str, healed: bool) -> None:
    try:
        await cognee_client.cognify(patient_id, temporal=_wants_temporal(patient_id))
        if healed:
            try:
                await cognee_client.improve(patient_id)
            except Exception:  # pragma: no cover - best-effort
                pass
    except Exception:  # pragma: no cover - Cognee lag never breaks a turn
        pass


async def run_fact_bg(patient_id: str, fact: ClinicalFact) -> TRState:
    """Ingest ONE fact for the chat path: the ledger answer is ready immediately;
    the Cognee graph build is scheduled in the BACKGROUND so the turn returns fast.
    Answer correctness is unaffected (the ledger is authoritative)."""
    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": f"{patient_id}:{fact.id}"}}
        state = await app.ainvoke(
            {
                "patient_id": patient_id, "new_fact": fact,
                "cognee_sync": True, "defer_cognify": True,
            },
            cfg,
        )
    healed = state.get("classification") in ("SUPERSEDES", "CONTRADICTS")
    _schedule(_cognify_bg(patient_id, healed))
    return state
