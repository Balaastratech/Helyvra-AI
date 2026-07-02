"""LangGraph engine state."""

from __future__ import annotations

from typing import List, Optional, TypedDict

from app.memory.schema import Classification, ClinicalFact


class TRState(TypedDict, total=False):
    """State threaded through the self-healing graph for a single fact ingest."""

    patient_id: str
    new_fact: ClinicalFact

    related: List[ClinicalFact]        # active facts, same patient+subject
    classification: Classification     # CONSISTENT | NEW | SUPERSEDES | CONTRADICTS
    target_fact_id: Optional[str]      # which existing fact the new one acts on
    reason: str
    confidence: float

    semantic_context: List[str]        # optional Cognee neighbor snippets (judge background)
    actions: List[str]                 # human-readable audit log
    cognee_sync: bool                  # whether persist pushes to Cognee

    # When True, the persist node ADDS the fact to Cognee but SKIPS cognify/improve
    # so a multi-fact ingest can cognify ONCE at the end (see service.run_facts).
    defer_cognify: bool
