# Phase 2 — Backend API + naive baseline

> Goal: expose the engine + memory over HTTP, and implement the genuinely-naive
> baseline so the smart-vs-naive contrast is reproducible from the API.
>
> Inputs: Phase 1 engine working in-process.

## A. Files
| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app, CORS, static-serve hook (Phase 6), router include |
| `app/api/routes_scenario.py` | `/seed`, `/ingest`, `/reset` |
| `app/api/routes_ask.py` | `/ask` (total_recall vs naive) |
| `app/api/routes_graph.py` | `/graph`, `/graph/cognee`, `/why`, `/health` |
| `app/api/dto.py` | Pydantic request/response models (the data contracts below) |
| `tests/test_api.py` | httpx asserts on the contrast + heal + graph snapshots |

Deps (add): `fastapi`, `uvicorn[standard]`, `httpx` (tests).

## B. Endpoints + exact data contracts

### `POST /seed`  → reset + load baseline (holds back the contradictions for live heal)
Req: `{ "patient_id": "P001" }`
Behavior: ledger.reset + `cognee_client.seed_reset()`; load `patient_timeline_01.json` **baseline** facts only (the allergy-diagnosed + lisinopril + diabetes), **holding back** the "allergy cleared" + "switched to amlodipine" events for live ingest. (Which facts are held back is a flag in the data file: `"hold_back": true`.)
Res: `{ "patient_id":"P001", "seeded":[ClinicalFact...], "held_back":[{label,text}] }`

### `POST /ingest`  → run engine on one fact (the live heal)
Req: `{ "patient_id":"P001", "text":"On 2026-03-02 ...", "structured": {optional ClinicalFact fields} }`
Res: `{ "fact":ClinicalFact, "classification":"SUPERSEDES", "target_fact_id":"...", "reason":"...", "healed": true, "actions":[...] }`

### `POST /ask`  → smart vs naive
Req: `{ "patient_id":"P001", "question":"Is the patient allergic to penicillin?", "mode":"total_recall"|"naive", "as_of": "2026-06-29"|null }`
Behavior:
- `total_recall` → `cognee_client.recall(question, type=TEMPORAL or GRAPH_COMPLETION, node_set=[patient_id])` (force type; pick TEMPORAL if as_of/temporal words else GRAPH_COMPLETION).
- `naive` → `cognee_client.recall(question, type=RAG_COMPLETION, node_set=[patient_id])` (no graph/temporal) → stale answer.
Res: `{ "answer":"...", "mode":"...", "search_type":"TEMPORAL", "raw": {...} }`

### `GET /graph?patient_id=P001&as_of=YYYY-MM-DD`  → Fact-Timeline (ledger)
Behavior: `ledger.snapshot(patient, as_of)`. A fact node is **active** at `as_of` if `valid_from <= as_of AND (valid_to is None OR valid_to > as_of)`, else **superseded**.
Res:
```
{ "as_of":"2026-06-29",
  "nodes":[ {"id","label","subject","value","status","valid_from","valid_to","source"} ],
  "edges":[ {"source","target","type":"SUPERSEDED_BY"|"SAME_SUBJECT"} ] }
```

### `GET /graph/cognee?patient_id=P001`  → raw Cognee knowledge graph (depth tab)
Behavior: `nodes, edges = await get_graph_engine().get_graph_data()`; map to `{nodes,edges}` JSON (handle unlabeled Timestamp nodes → label fallback).

### `GET /why?fact_id=...`  → provenance trace
Behavior: `ledger.chain(fact_id)` → returns the supersession chain + reasons.
Res: `{ "fact":ClinicalFact, "superseded_by":ClinicalFact|null, "reason":"...", "source":"...", "date":"2026-03-02", "chain":[...] }`

### `GET /health` → `{ "ok":true, "cognee":"up", "ledger":"up" }`

## C. Steps
1. `dto.py` (mirror contracts above).
2. `cognee_client.recall(...)` returns `.text` from `ResponseGraphEntry` + raw.
3. Routers; include in `main.py`; CORS allow `http://localhost:5173` (Vite).
4. `python -m uvicorn app.main:app --reload` → manual curl/HTTPie.
5. `tests/test_api.py`.

## D. Acceptance (done-when)
- `POST /seed` → baseline loaded, contradictions held back.
- `POST /ask` allergy question: **naive → "yes/allergic" (stale/dangerous)**, **total_recall → "no, cleared"** (after the heal) — demonstrably different. (Pre-heal, both may say allergic; that's fine — the heal is what flips total_recall.)
- `POST /ingest` the clear-event → `classification=SUPERSEDES`, `healed=true`.
- `GET /graph?as_of=2026-02-15` shows allergy **active**; `as_of=2026-06-29` shows it **superseded**.
- `GET /why` returns the clear-event + reason + Dr. Lee + 2026-03-02.
- `GET /graph/cognee` returns a non-empty node/edge set.

## E. Risks
- Naive accidentally correct → ensure naive uses RAG_COMPLETION (no temporal) and does NOT read the ledger. Verify it returns the stale answer; if Cognee's RAG still corrects, fall back naive to `CHUNKS` (pure retrieval) or query a pre-heal snapshot.
- recall latency (~3–7s observed) → fine for demo; add a spinner in UI (Phase 3).

## F. NOT in this phase
No frontend; no deploy. JSON only.

## Done → `start Phase 3`.

---

## IMPLEMENTED DELTAS (what actually shipped — read before Phase 3)
- **Smart `/ask` forces `TEMPORAL`** (not "else GRAPH_COMPLETION"): GRAPH_COMPLETION
  returned garbage ("Got it.") for yes/no questions; TEMPORAL is reliable.
- **Naive baseline = a separate FROZEN `naive_baseline` dataset** (pre-heal snapshot),
  not the healed dataset. Needed because (a) supersession retains history so RAG over
  the smart dataset self-corrects, and (b) it guarantees the stale "Yes, allergic".
- **Supersession does NOT forget** (corrected per ARCHITECTURE.md): both dated
  assertions stay in Cognee → past-tense `/ask?as_of=` works ("was allergic as of Feb").
- **`forget` is a separate endpoint** `POST /forget` (entered-in-error), NOT a
  supersede side-effect. New ledger status `retracted`; see `docs/phase-2b-forget.md`.
- **`hold_back` flags** added to `data/patient_timeline_01.json` (the 2 superseding
  events). `/seed` loads only non-held-back baseline.
- Endpoints shipped: `POST /seed /ingest /reset /forget /ask`, `GET /graph
  /graph/cognee /why /health`. Contracts live in `app/api/dto.py` (frontend source of
  truth). All 12 `tests/test_api.py` green on live Vertex + Cognee.
