# ARCHITECTURE — Total Recall

## Stack (local, cost-safe)

- **Memory:** Cognee, self-hosted defaults — SQLite (relational/provenance) + LanceDB (vectors) + Kuzu (graph). `pip install cognee`.
- **Backend:** FastAPI (thin). Async throughout (all Cognee APIs are async).
- **Frontend:** React 18 + TS + Vite + Tailwind + **Sigma.js** (graph) + a date-scrubber slider. (Reuse your Sigma experience from Organizer's `ConnectionGraphSigma` — capability, not the file.)
- **LLMs (hard-capped):**
  - `cognify` bulk extraction → **cheap model** (Gemini Flash or DeepSeek) via `cognee.config.set_llm_*`.
  - **Contradiction judge** → stronger model (Claude) — quality matters only here, few calls.
- **Data:** synthetic patient timelines (JSON) authored by hand/LLM. No PHI.

## Cognee primitives used (and where)

| Primitive | Where | Tier |
|---|---|---|
| `add(..., node_set=[patient_id], dataset_name=...)` | ingest each fact | MUST |
| `cognify(temporal_cognify=True, custom_prompt=...)` | build time-aware graph | MUST |
| `search(SearchType.GRAPH_COMPLETION / TEMPORAL)` | recall + answer | MUST |
| `improve()` / `memify()` | reconcile + consolidate graph | MUST / STRETCH |
| `forget()` (scoped) | retire truly invalid facts | MUST |
| Provenance (relational store) + `NATURAL_LANGUAGE`/`CYPHER` | "why did this change?" trace | SHOULD |
| Custom `DataPoint` (`ClinicalFact`) + custom Task/pipeline | grounded extraction | STRETCH |
| `visualize_graph()` | fallback/quick graph render | any |

## The self-healing pipeline (core engine)

```
new_fact
  └─> add(node_set=[patient]) + cognify(temporal_cognify=True)
  └─> recall related claims  (graph multi-hop, scoped by node_set + same subject/predicate)
  └─> contradiction judge (LLM) -> { CONSISTENT | NEW | SUPERSEDES(old) | CONTRADICTS(old) }
        ├─ SUPERSEDES -> mark old fact valid_to = new.valid_from ; improve() ; link (:SUPERSEDED_BY)
        ├─ CONTRADICTS (no clear winner) -> flag for review, keep both, lower confidence
        ├─ NEW        -> keep
        └─ CONSISTENT -> reinforce (feedback_weight up)
```

Key design choice: **never hard-delete on supersession.** Old facts stay with `valid_to` set + a `SUPERSEDED_BY` edge — that's what powers both the time-scrubber and the "why" trace. `forget()` is reserved for facts judged outright invalid (e.g., entered in error).

## Data model — `ClinicalFact` (DataPoint, STRETCH; plain text fallback for MUST)

```python
class ClinicalFact(DataPoint):
    patient_id: str
    subject: str       # e.g. "allergy", "medication", "diagnosis"
    predicate: str     # e.g. "is", "discontinued", "added"
    value: str         # e.g. "penicillin"
    valid_from: str    # ISO date
    valid_to: str | None = None
    source: str        # where it came from
    confidence: float = 1.0
    metadata: dict = {"index_fields": ["subject", "value"]}
```

MUST-tier can run with structured natural-language facts ("On 2026-03-02, penicillin allergy cleared by re-test, source: Dr. Lee") and rely on `temporal_cognify`; promote to `ClinicalFact` in STRETCH for cleaner edges + extraction credit.

## API surface (FastAPI)

| Endpoint | Purpose |
|---|---|
| `POST /ingest` | add a fact → run self-healing pipeline → return classification |
| `POST /ask` | `{question, mode: "total_recall" | "naive", as_of?: date}` |
| `GET /graph?as_of=date` | nodes+edges for the scrubber (filter by valid_from/valid_to) |
| `GET /why?fact_id=` | provenance trace (SHOULD) |
| `POST /seed` | load a synthetic patient timeline |

## Frontend views

1. **Split chat:** left = Total Recall, right = Naive RAG (same question, different answer). The money shot.
2. **Graph + scrubber:** Sigma graph; slider over time; superseded nodes greyed, `SUPERSEDED_BY` edges dashed.
3. **Why panel:** click a fact → provenance path + source + date.

## Cost controls

- One-time `cognify` over a *small* synthetic set.
- Judge runs only on subject/predicate collisions, not every fact.
- Cheap model for extraction; hard cap on total LLM calls per run; log spend.
