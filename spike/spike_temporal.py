"""
Total Recall — Day-1 spike.

Goal: PROVE that local Cognee + temporal_cognify + SearchType.TEMPORAL works on
this machine BEFORE building anything around it.

Scenario (the core of the whole project): two CONTRADICTING patient facts over time.
  - 2026-01-10: patient is allergic to penicillin
  - 2026-03-02: penicillin allergy CLEARED by re-test
A naive store remembers both and may answer "allergic". A time-aware store should
let us ask "what was true before / after a date" and get the right answer.

Run:  python spike_temporal.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

import cognee

# WINDOWS MAX_PATH FIX: LanceDB writes deeply-nested temp files. Inside a venv the
# base path is already ~120 chars, so Lance blows past the 260-char limit and fails
# with "The system cannot find the path specified (os error 3)". Move Cognee's
# storage to a SHORT root so every path stays under the limit.
cognee.config.system_root_directory(r"C:\cg\sys")
cognee.config.data_root_directory(r"C:\cg\data")

# SearchType import path differs across versions — try both.
try:
    from cognee.api.v1.search import SearchType
except Exception:  # pragma: no cover
    from cognee import SearchType


DATASET = "spike_patient"

# Time-ordered, deliberately contradicting facts.
FACTS = [
    "On 2026-01-10, patient P001 was diagnosed with a penicillin allergy by Dr. Adams.",
    "On 2026-02-15, patient P001 was prescribed lisinopril 10mg for hypertension.",
    "On 2026-03-02, patient P001's penicillin allergy was CLEARED after a negative re-test by Dr. Lee.",
    "On 2026-04-20, patient P001 stopped lisinopril and switched to amlodipine 5mg.",
]

TEMPORAL_QUERIES = [
    "Was patient P001 allergic to penicillin before February 2026?",
    "Is patient P001 allergic to penicillin after March 2026?",
    "What medication was patient P001 on between February and April 2026?",
]


def configure():
    """Configure Cognee from environment. Local embeddings keep cost at $0."""
    provider = os.environ.get("LLM_PROVIDER")
    if provider:
        cognee.config.set_llm_provider(provider)
    if os.environ.get("LLM_MODEL"):
        cognee.config.set_llm_model(os.environ["LLM_MODEL"])
    if os.environ.get("LLM_API_KEY"):
        cognee.config.set_llm_api_key(os.environ["LLM_API_KEY"])
    if os.environ.get("LLM_ENDPOINT"):
        cognee.config.set_llm_endpoint(os.environ["LLM_ENDPOINT"])
    # Embedding provider/model are read from env (EMBEDDING_PROVIDER=fastembed → local, free).


async def retrieve(query_type, query_text, **kw):
    """search() vs recall() across versions — try recall, fall back to search."""
    try:
        return await cognee.recall(query_type=query_type, query_text=query_text, **kw)
    except AttributeError:
        return await cognee.search(query_text, query_type=query_type, **kw)


async def main():
    configure()

    print("Cognee version:", getattr(cognee, "__version__", "unknown"))
    print("Available SearchTypes:", [t.name for t in SearchType])

    # Clean slate so re-runs are deterministic.
    print("\n[1/4] Pruning previous state...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    print("[2/4] Adding facts...")
    for f in FACTS:
        await cognee.add(f, dataset_name=DATASET)

    print("[3/4] cognify(temporal_cognify=True) — building time-aware graph...")
    await cognee.cognify(datasets=[DATASET], temporal_cognify=True)

    print("[4/4] Temporal queries:\n")
    for q in TEMPORAL_QUERIES:
        print("Q:", q)
        res = await retrieve(SearchType.TEMPORAL, q, datasets=[DATASET], top_k=10)
        print("A:", res, "\n")

    # Sanity: does a plain graph completion know the CURRENT truth?
    print("Current-truth check (GRAPH_COMPLETION):")
    res = await retrieve(
        SearchType.GRAPH_COMPLETION,
        "Is patient P001 currently allergic to penicillin? Answer with the latest known fact.",
        datasets=[DATASET],
        top_k=10,
    )
    print("A:", res)

    print(
        "\n✅ Spike done. SUCCESS CRITERIA:\n"
        "  - 'before Feb' → allergic; 'after March' → NOT allergic (temporal distinguishes them)\n"
        "  - current-truth check says NOT allergic\n"
        "If temporal answers ignore the dates, note it now and we adjust the design."
    )


if __name__ == "__main__":
    asyncio.run(main())
