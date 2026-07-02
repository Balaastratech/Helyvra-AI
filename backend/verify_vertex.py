"""
Phase 0 acceptance test.

Proves: Cognee runs locally on Vertex AI (NO API key, ADC) and temporal
before/after works on the P001 patient timeline.

Run from the backend/ directory:
    python verify_vertex.py
"""

import asyncio
import json
import os
from pathlib import Path

import app.config as config  # configures Cognee on import (must be first)
import cognee

try:
    from cognee.api.v1.search import SearchType
except Exception:  # pragma: no cover - version fallback
    from cognee import SearchType

DATA = Path(__file__).resolve().parent.parent / "data" / "patient_timeline_01.json"
DATASET = "verify_p001"


async def retrieve(query_type, query_text, **kw):
    """recall() (new API) with fallback to search() (legacy)."""
    try:
        return await cognee.recall(query_type=query_type, query_text=query_text, **kw)
    except AttributeError:
        return await cognee.search(query_text, query_type=query_type, **kw)


async def main():
    # Hard guarantee we're NOT on an API key.
    assert "GEMINI_API_KEY" not in os.environ, "Unset GEMINI_API_KEY — we use Vertex ADC."
    assert "GOOGLE_API_KEY" not in os.environ, "Unset GOOGLE_API_KEY — we use Vertex ADC."
    print(config.summary())

    facts = [f["text"] for f in json.loads(DATA.read_text(encoding="utf-8"))["facts"]]

    print("\n[1/3] Pruning previous state...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    print("[2/3] add + cognify(temporal_cognify=True) via Vertex...")
    for text in facts:
        await cognee.add(text, dataset_name=DATASET)
    await cognee.cognify(datasets=[DATASET], temporal_cognify=True)

    print("[3/3] Temporal queries:\n")
    checks = [
        ("Was patient P001 allergic to penicillin before February 2026?", "EXPECT: yes (allergic)"),
        ("Is patient P001 allergic to penicillin after March 2026?", "EXPECT: no (cleared 2026-03-02)"),
        ("What blood pressure medication is patient P001 on now?", "EXPECT: amlodipine"),
    ]
    for q, exp in checks:
        res = await retrieve(SearchType.TEMPORAL, q, datasets=[DATASET], top_k=10)
        print("Q:", q)
        print("  ", exp)
        print("A:", res, "\n")

    print("Current-truth check (GRAPH_COMPLETION):")
    res = await retrieve(
        SearchType.GRAPH_COMPLETION,
        "Is patient P001 currently allergic to penicillin? Use the latest known fact.",
        datasets=[DATASET],
        top_k=10,
    )
    print("A:", res)

    print(
        "\n✅ PHASE 0 PASSES if: 'before Feb' = allergic, 'after March' = NOT allergic, "
        "and the current-truth check says NOT allergic — all via Vertex with NO API key."
    )


if __name__ == "__main__":
    asyncio.run(main())
