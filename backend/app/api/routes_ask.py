"""
/ask — the smart-vs-naive contrast.

total_recall : Cognee TEMPORAL search over the healed `total_recall` dataset.
               TEMPORAL is forced for every smart query because (a) it is the
               rarest/most demo-worthy Cognee primitive and (b) it is empirically
               reliable here — GRAPH_COMPLETION intermittently returned garbage
               like "Got it." for the yes/no allergy question, whereas TEMPORAL
               consistently answers "No." (allergy cleared) and "Amlodipine 5mg".
               (docs/phase-2.md says "TEMPORAL or GRAPH_COMPLETION"; we pick the
               one that actually works.)
naive        : RAG_COMPLETION over the FROZEN `naive_baseline` dataset (pre-heal
               snapshot, no graph/temporal, no ledger) -> the stale/dangerous
               answer ("Yes, allergic"). This is the "villain".

We FORCE the search type per call so the demo is deterministic (no reliance on
Cognee's built-in regex query router).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dto import AskRequest, AskResponse
from app.memory import cognee_client
from app.memory.cognee_client import SearchType

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    if req.mode == "naive":
        # The villain: pure retrieval completion over the never-healed naive
        # dataset (no graph/temporal, no ledger) -> stale/dangerous answer.
        node_set = [req.patient_id]
        answer, raw = await cognee_client.recall_answer(
            req.question,
            query_type=SearchType.RAG_COMPLETION,
            node_set=node_set,
            dataset=cognee_client.naive_dataset_for(req.patient_id),
        )
        return AskResponse(
            answer=answer, mode=req.mode, search_type="RAG_COMPLETION", raw=raw
        )

    # Smart: synthesized answer from full ledger history (past+present+delta+source).
    from app.engine.answer import synthesize

    as_of_str = req.as_of.isoformat() if req.as_of else None
    answer = synthesize(req.patient_id, req.question, as_of=as_of_str)

    return AskResponse(
        answer=answer, mode=req.mode, search_type="SYNTHESIZED", raw=None
    )
