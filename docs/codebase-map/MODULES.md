# Total Recall — Module Index

---

## backend/app/config.py
Central config + Cognee/Vertex wiring. **Must be imported first** in every entrypoint.
- `config.py:1` — strips rogue API keys, sets Vertex ADC env, configures Cognee storage paths, sets model names

---

## backend/app/engine/
LangGraph self-healing pipeline — the core of the project.

- `engine/graph.py:1` — `build_graph()`, `StateGraph` wiring, `AsyncSqliteSaver` checkpointer; flow: `START → recall_related → judge → reconcile → persist → END`
- `engine/state.py:1` — `TRState` TypedDict (LangGraph state schema)
- `engine/nodes.py:1` — individual node functions (`recall_related`, `judge_node`, `reconcile_supersede`, `reconcile_contradict`, `reinforce`, `store_new`, `persist`)
- `engine/judge.py:1` — Gemini structured-output contradiction judge; returns `Verdict` (SUPERSEDES / CONTRADICTS / NEW / CONSISTENT)
- `engine/answer.py:1` — answer formatting helpers
- `engine/extract.py:1` — LLM-based fact extraction from free text
- `engine/service.py:1` — thin service wrapper to run the graph from API routes
- `engine/run.py:1` — CLI runner (`python -m app.engine.run`) for local timeline ingestion

---

## backend/app/memory/
Memory stores and the seam to Cognee.

- `memory/schema.py:1` — `ClinicalFact` (Pydantic, the fact model that flows everywhere), `Verdict`, `ResourceType`, `RESOURCE_BY_SUBJECT`
- `memory/ledger.py:1` — `SQLModel` over SQLite; authoritative fact status store (active / superseded / contested, `valid_from`, `valid_to`, supersession chain); `init()`, `reset()`, `upsert()`, `list_active()`
- `memory/cognee_client.py:1` — the ONLY module that calls Cognee; `add()`, `cognify()`, `search()`, `forget()`; per-patient dataset isolation
- `memory/records.py:1` — patient registry helpers (`list_patients`, seed/load from JSON)
- `memory/ontology.py:1` — clinical ontology helpers (FHIR alignment, subject normalisation)

---

## backend/app/intake/
Universal document intake pipeline (Phase 5).

- `intake/pipeline.py:1` — top-level entry: sniff format → extract facts → resolve patient → store doc → run engine per fact
- `intake/structured.py:1` — deterministic extractors for FHIR JSON and CSV lab series
- `intake/fhir.py:1` — FHIR R4 resource → `ClinicalFact` mapping
- `intake/patient_index.py:1` — `resolve()` — hint / FHIR ref / name/MRN → patient_id (auto-create if needed)
- `intake/family_resolver.py:1` — resolves family-member identity references in intake notes

---

## backend/app/agent/
Conversational ReAct agent (Phase 8).

- `agent/router.py:1` — Gemini native function-calling loop; four patient-scoped tools; forced grounding (no clinical answers from model knowledge); tool-call trace per turn
- `agent/tools.py:1` — tool definitions: `recall_patient_facts`, `ingest_fact`, `propose_forget`, `explain`; bound to one patient via closures
- `agent/history.py:1` — SQLite-backed per-thread message history; `init()`, `append()`, `get()`
- `agent/pending.py:1` — staged `propose_forget` actions awaiting `/chat/approve`

---

## backend/app/checks/
Clinical safety checks engine (Phase 5 / §5).

- `checks/engine.py:1` — `OPEN_CHECKS` registry; runs all checks on patient-open, severity-sorts output
- `checks/cards.py:1` — `Card` dataclass (severity, title, body, action); `top_by_severity()`
- `checks/allergy.py:1` — allergy cross-check (active allergies vs proposed medications)
- `checks/followup.py:1` — overdue follow-up detection
- `checks/risk.py:1` — risk flag check (e.g. high HbA1c, BP alerts)
- `checks/hereditary.py:1` — hereditary risk from family history facts

---

## backend/app/api/
FastAPI routers — one file per domain.

- `api/dto.py:1` — all Pydantic request/response DTOs shared across routes
- `api/routes_ask.py:1` — `POST /ask` (smart vs naive compare)
- `api/routes_intake.py:1` — `POST /intake`, `POST /upload`, `GET /documents/*`
- `api/routes_patients.py:1` — `GET /patients`, `POST /patients`, `GET /patients/{id}/brief`
- `api/routes_access.py:1` — `GET /doctors`, `GET /patients/resolve`, `GET /audit`
- `api/routes_graph.py:1` — `GET /graph`, `GET /graph/cognee`, `GET /why`
- `api/routes_family.py:1` — `GET /family/{id}`, `POST /family/consent`
- `api/routes_chat.py:1` — `POST /chat`, `POST /chat/approve`, chat thread CRUD
- `api/routes_scenario.py:1` — `POST /seed`, `POST /ingest`, `POST /reset`, `POST /forget`, `GET /health`

---

## backend/app/audit.py
Append-only audit log (SQLite). `init()`, `log()`, `query()`. All patient data access and mutations are recorded here.

## backend/app/auth.py
Doctor identity + access control. Validates `X-Doctor-Id` header; enforces patient access permissions.

---

## frontend/src/api/
Typed HTTP layer.

- `api/client.ts:1` — `api.*` functions (one per endpoint); `VITE_API_BASE` env var; `ApiError`
- `api/hooks.ts:1` — TanStack Query hooks wrapping `api.*` for all pages
- `api/types.ts:1` — TypeScript interfaces matching `dto.py` contracts

---

## frontend/src/pages/
Top-level route components.

- `pages/Dashboard.tsx:1` — patient list + quick actions
- `pages/PatientWorkspace.tsx:1` — full patient chart (timeline, checks, chat, docs)
- `pages/ComparePage.tsx:1` — side-by-side smart vs naive chat (`SplitChat`)
- `pages/MemoryMapPage.tsx:1` — force-graph of patient facts + `RewindSlider` time-scrubber
- `pages/BoardPage.tsx:1` — cork-board evidence view
- `pages/LoginPage.tsx:1` — doctor picker (simulated auth)

---

## frontend/src/components/
UI components (clinical, graph, cinematic).

- `components/layout/ClinicalShell.tsx:1` — app shell + nav
- `components/SplitChat.tsx:1` — two-pane compare chat
- `components/MemoryGraph.tsx:1` — react-force-graph-2d wrapper
- `components/ForceCanvas.tsx:1` — low-level canvas graph renderer
- `components/RewindSlider.tsx:1` — time-scrubber `as_of` date slider
- `components/WhyPanel.tsx:1` — provenance trace drawer
- `components/clinical/AnswerCard.tsx:1` — styled answer with mode badge
- `components/clinical/PreVisitBrief.tsx:1` — check cards on patient-open
- `components/clinical/FamilyPanel.tsx:1` — family links + consent toggle
- `components/cinematic/TitleSequence.tsx:1` — intro animation (plays once per session)
- `components/cinematic/CinematicLayer.tsx:1` — ambient cinematic effects overlay
- `components/DropZone.tsx:1` — drag-and-drop file upload → `POST /intake`
- `components/CommandPalette.tsx:1` — `⌘K` command palette (cmdk)
- `components/PatientTimeline.tsx:1` — vis-timeline patient event timeline

---

## frontend/src/store.ts
Zustand store: active `doctor`, `patientId`, `asOf`, `whyFactId`, `docId`, `cinemaMode`, `howOpen`, guided-steps state.

---

## data/
Synthetic patient timelines and demo uploads (no PHI).
- `data/patient_timeline_01.json` — primary test timeline
- `data/patients.json` — patient registry seed
- `data/family_links.json` — family relationship seed
- `data/demo_uploads/` — sample PDF/CSV/TXT files for intake demo

---

## backend/scripts/
Dev utilities.
- `scripts/gen_demo_data.py:1` — generates synthetic patient data
- `scripts/clean_slate.py:1` — wipes Cognee + ledger storage for a fresh run
- `scripts/smoke.ps1:1` — PowerShell smoke-test against running server
