# Phase 1 — Self-healing engine (LangGraph) [CORE]

> Goal: ingesting a fact runs through a LangGraph agent that **detects** whether it
> supersedes/contradicts existing facts and **reconciles** memory so the current truth
> is correct AND the history (with reasons) is retained. No UI yet — proven by tests + a runner.
>
> Inputs: Phase 0 done (Vertex works). Decisions: **full engine**, clinical patient data.

## A. Architecture decision (flag — veto if you disagree)
Two stores, clear roles:
- **Cognee** = semantic + temporal memory. Holds fact texts (`add`+`cognify(temporal_cognify=True)`), powers `recall` (TEMPORAL/GRAPH_COMPLETION = smart; RAG_COMPLETION = naive villain), and `forget`/`improve`/`memify`/DataPoints (lifecycle credit).
- **Fact ledger** (app-side SQLite via SQLModel) = authoritative status of every `ClinicalFact`: `status` (active/superseded/contested), `valid_from`, `valid_to`, `superseded_by`, `source`, `confidence`, `reason`. Drives the heal visualization, the time-scrubber, and `/why`.
- **Why both:** writing/updating Kuzu node attributes + `SUPERSEDED_BY` edges live is fiddly and non-deterministic; the ledger gives a rock-solid demo while Cognee still does the heavy memory lifting. The UI later shows BOTH graphs (ledger-driven Fact-Timeline + raw Cognee Knowledge graph).

## B. Files created this phase
| File | Purpose |
|---|---|
| `app/memory/schema.py` | `ClinicalFact` Pydantic model (canonical fact) |
| `app/memory/ledger.py` | SQLModel store: CRUD + queries (active by subject, by as_of, supersession chain) |
| `app/memory/cognee_client.py` | the ONLY module that calls Cognee (seam): `seed_reset`, `add_fact`, `cognify`, `recall`, `forget`, `get_graph_data` |
| `app/engine/state.py` | `TRState` TypedDict |
| `app/engine/judge.py` | google-genai (Vertex) structured contradiction classifier |
| `app/engine/nodes.py` | node functions (recall_related, judge, reconcile_*, persist) |
| `app/engine/graph.py` | LangGraph `StateGraph` wiring + `SqliteSaver` checkpointer |
| `app/engine/run.py` | CLI runner: ingest a timeline, print ledger + audit log |
| `tests/test_engine.py` | pytest acceptance on `patient_timeline_01.json` |

Add to `requirements.txt` (already listed): `langgraph`, `langgraph-checkpoint-sqlite`, `google-genai`, `sqlmodel`.

## C. Data model — `ClinicalFact` (schema.py)
```
id: str (uuid4)         patient_id: str
subject: str            # allergy | medication | diagnosis | ...
predicate: str          # diagnosed | cleared | prescribed | switched | added
value: str              # penicillin | amlodipine 5mg | type 2 diabetes
valid_from: date (ISO)  valid_to: date|None
source: str             status: active|superseded|contested  (default active)
superseded_by: str|None confidence: float = 1.0
reason: str|None        raw_text: str
```

## D. Engine state (state.py)
```
TRState = TypedDict:
  patient_id: str
  new_fact: ClinicalFact
  related: list[ClinicalFact]        # active facts, same patient+subject (+ semantic neighbors)
  classification: "CONSISTENT"|"NEW"|"SUPERSEDES"|"CONTRADICTS"
  target_fact_id: str|None           # which existing fact it acts on
  reason: str
  confidence: float
  actions: list[str]                 # human-readable audit log
```

## E. Judge (judge.py) — google-genai on Vertex
- Client: `genai.Client(vertexai=True, project=VERTEXAI_PROJECT, location=VERTEXAI_LOCATION)` (ADC; no key).
- Model: `JUDGE_MODEL` (gemini-2.5-pro).
- Structured output via `response_schema` (Pydantic `Verdict{classification, target_fact_id, reason, confidence}`), `response_mime_type="application/json"`.
- Prompt contract: "You are a clinical memory reconciler. Given a NEW fact and EXISTING active facts (same patient+subject), decide if NEW makes one EXISTING fact no longer true (SUPERSEDES), directly conflicts without a clear winner (CONTRADICTS), restates an existing one (CONSISTENT), or is unrelated/additive (NEW). Pick the single target_fact_id when SUPERSEDES/CONTRADICTS." Few-shot with the allergy-cleared + med-switch examples.
- **Determinism:** temperature 0; only call the judge when ≥1 related active fact shares subject (dedupe gate) — else classify NEW without an LLM call (cost + determinism).

## F. Nodes (nodes.py) + graph (graph.py)
Flow:
```
START → recall_related → judge → [route] → {reconcile_supersede | reconcile_contradict | store_new | reinforce} → persist → END
```
- **recall_related:** ledger.query_active(patient, subject) (+ optional Cognee graph neighbors for context). → state.related. If empty → set classification NEW, skip judge.
- **judge:** call judge.py → fill classification/target/reason/confidence + append action.
- **route:** conditional edge on classification.
- **reconcile_supersede:** old = ledger.get(target); set old.valid_to = new.valid_from, old.status=superseded, old.superseded_by=new.id, old.reason=reason; ledger.upsert(old, new active). Cognee: `add_fact(new)` + (optional) `forget` the stale assertion; `improve()`/`memify` light. Log action.
- **reconcile_contradict:** keep both; set both status=contested, confidence↓; log "flagged for review".
- **store_new / reinforce:** add new active / bump confidence + log.
- **persist:** ledger commit + `cognee_client.add_fact(new)` then `cognify(temporal)`; checkpoint via SqliteSaver (thread_id = patient_id).
- Checkpointer DB: `C:\cg\engine_checkpoints.sqlite` (short path).

## G. Steps (execution order)
1. Add deps; create `app/memory/`, `app/engine/`, `tests/`.
2. `schema.py` → `ledger.py` (SQLModel, SQLite at `C:\cg\ledger.db`) with: `init`, `reset`, `add`, `get`, `upsert`, `query_active(patient,subject)`, `all(patient)`, `snapshot(patient, as_of)`, `chain(fact_id)`.
3. `cognee_client.py` seam (imports `app.config`).
4. `judge.py` (google-genai Vertex, Verdict schema, temp 0, dedupe gate).
5. `state.py` → `nodes.py` → `graph.py` (compile with checkpointer).
6. `run.py` — load `patient_timeline_01.json`, ingest each fact in date order through the engine, print final ledger + audit log.
7. `tests/test_engine.py` — assertions below.

## H. Acceptance criteria (Phase 1 done-when)
- Ingesting the 5-fact timeline yields a ledger where: penicillin allergy = **superseded** (valid_to 2026-03-02, superseded_by the clear-event), lisinopril = **superseded** by amlodipine, diabetes = **active/new**, current active set correct.
- The 2 supersession events classify **SUPERSEDES** with the correct `target_fact_id`; diabetes classifies **NEW**; a re-stated fact classifies **CONSISTENT**.
- Judge calls only fire on subject collisions (verify via log/spend).
- Checkpoints persist (re-run resumes/inspectable).
- `tests/test_engine.py` passes deterministically (temp 0).

## I. Risks & mitigations
- Judge picks wrong target → tighten prompt + few-shot; assert in tests; keep subject-scoped candidate set small.
- google-genai Vertex auth differs from Cognee → both use ADC; verify with a 1-line genai ping at start of `run.py`.
- Cost → judge only on collisions; Flash-tier fallback for judge if Pro quota tight.

## J. NOT in this phase
No FastAPI, no UI, no provenance endpoint (Phase 2/4). Engine is callable in-process only.

## Done → `start Phase 2`.
