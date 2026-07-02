"""
CLI runner — ingest a patient timeline through the self-healing engine.

    cd backend
    python -m app.engine.run                       # full run (Vertex judge + Cognee sync)
    python -m app.engine.run --no-cognee           # ledger + judge only (fast)
    python -m app.engine.run --data ..\\data\\patient_timeline_01.json

Prints the final ledger (current truth + history) and the full audit log.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import app.config as config  # noqa: F401  (wires Vertex/Cognee first)
from google import genai
from google.genai import types

from app.engine.graph import build_graph, checkpointer
from app.memory import cognee_client, ledger
from app.memory.schema import ClinicalFact

_DEFAULT_DATA = Path(__file__).resolve().parents[3] / "data" / "patient_timeline_01.json"


def _genai_ping() -> None:
    """1-line Vertex/ADC sanity check (plan I): proves auth before we ingest."""
    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
    resp = client.models.generate_content(
        model=config.JUDGE_MODEL,
        contents="Reply with the single word: ok",
        config=types.GenerateContentConfig(temperature=0, max_output_tokens=8000),
    )
    print(f"  genai ping ({config.JUDGE_MODEL}): {(resp.text or '').strip()!r}")


async def ingest_timeline(path: Path, cognee_sync: bool) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    patient_id = data["patient_id"]

    # Fresh state.
    ledger.reset()
    # A full reseed starts a clean engine thread too (avoid resuming a prior run's
    # accumulated state). Checkpoints still persist *within* and after this run.
    cp_db = os.environ.get("ENGINE_CHECKPOINTS", r"C:\cg\engine_checkpoints.sqlite")
    for suffix in ("", "-wal", "-shm"):
        p = cp_db + suffix
        if os.path.exists(p):
            os.remove(p)
    if cognee_sync:
        print("  resetting Cognee state...")
        await cognee_client.seed_reset()

    # Facts in chronological order.
    entries = sorted(data["facts"], key=lambda e: e["date"])

    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": patient_id}}
        seen = 0  # actions accumulate across the timeline; print only the new ones
        for entry in entries:
            fact = ClinicalFact.from_timeline_entry(patient_id, entry)
            print(f"\n>> ingest {entry['date']} {entry['subject']}/{entry['predicate']}: {entry['value']}")
            result = await app.ainvoke(
                {"patient_id": patient_id, "new_fact": fact, "cognee_sync": cognee_sync},
                cfg,
            )
            actions = result.get("actions", [])
            for line in actions[seen:]:
                print("    -", line)
            seen = len(actions)
    return patient_id


def _print_ledger(patient_id: str) -> None:
    print("\n" + "=" * 72)
    print(f"FINAL LEDGER — patient {patient_id}")
    print("=" * 72)
    facts = ledger.all(patient_id)

    print("\nCURRENT TRUTH (active):")
    for f in facts:
        if f.status == "active":
            print("  ✓", f.short())

    print("\nHISTORY (superseded / contested):")
    for f in facts:
        if f.status != "active":
            tail = f" -> {f.superseded_by[:8]}" if f.superseded_by else ""
            print(f"  · {f.short()}{tail}")
            if f.reason:
                print(f"      reason: {f.reason}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Total Recall — self-healing engine runner")
    parser.add_argument("--data", type=Path, default=_DEFAULT_DATA)
    parser.add_argument("--no-cognee", action="store_true", help="skip Cognee sync (ledger+judge only)")
    args = parser.parse_args()

    print(config.summary())
    print("Vertex auth check:")
    _genai_ping()

    patient_id = await ingest_timeline(args.data, cognee_sync=not args.no_cognee)
    _print_ledger(patient_id)
    print("\n✅ Engine run complete.")


if __name__ == "__main__":
    asyncio.run(main())
