# Total Recall — Codebase Overview

## What is this?

Total Recall is a clinical-memory demo that shows the difference between **smart temporal recall** (Cognee graph + self-healing pipeline) and **naive RAG** (stale flat retrieval) over synthetic patient records. A doctor uploads documents; the engine extracts clinical facts, resolves contradictions (e.g. an allergy cleared by re-test), links superseded facts with `SUPERSEDED_BY` edges, and stores the entire temporal chain. A side-by-side chat UI lets you ask the same question in both modes — "Total Recall" says "No allergy (cleared 2026-03)" while "Naive" still says "Yes, allergic." No PHI; synthetic data only.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend runtime | Python 3.12, FastAPI, uvicorn |
| Graph pipeline | LangGraph + AsyncSqliteSaver (checkpoints) |
| Memory / graph store | Cognee 1.2.2 → SQLite + LanceDB (vectors) + Kuzu (graph) |
| LLM — extraction | Gemini 2.5 Flash via Vertex AI (ADC, no API key) |
| LLM — contradiction judge | Gemini 2.5 Pro via Vertex AI |
| Embeddings | fastembed local CPU (`all-MiniLM-L6-v2`, 384d) |
| Ledger (authoritative) | SQLModel over SQLite (`C:\cg\ledger.db`) |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Frontend state | Zustand (UI) + TanStack Query (server cache) |
| Graph visualisation | react-force-graph-2d |
| Timeline | vis-timeline |
| Animations | Framer Motion |
| Routing | react-router-dom v6 |

---

## Top-Level Architecture

```
frontend/          React SPA (Vite dev on :5173)
  src/api/           typed fetch wrappers + TanStack Query hooks
  src/pages/         Dashboard, PatientWorkspace, ComparePage, MemoryMapPage, BoardPage
  src/components/    clinical UI, graph canvas, cinematic intro
  src/store.ts       Zustand: active doctor, patient, asOf, docId, cinemaMode

backend/           FastAPI server (uvicorn on :8000)
  app/config.py      MUST import first — wires Vertex ADC + Cognee storage paths
  app/engine/        LangGraph self-healing pipeline (the core)
  app/memory/        Cognee client seam + SQLite ledger + ClinicalFact schema
  app/intake/        Universal file intake (PDF/FHIR/CSV/text → facts)
  app/agent/         ReAct tool-calling conversational agent (Gemini function-calling)
  app/checks/        Clinical safety checks (allergy, followup, risk, hereditary)
  app/api/           FastAPI routers (one file per domain)
  app/audit.py       Append-only audit log (SQLite)
  app/auth.py        Doctor identity / access control

data/              Synthetic patient timelines (JSON) + demo uploads
assets/theme/      UI theme images (noir, cinematic, polaroid, stamps)
docs/              ARCHITECTURE.md, plan docs, demo scripts
```

---

## How the Pieces Fit Together

1. **Intake** — frontend drops a file → `POST /intake` → `app/intake/pipeline.py` sniffs format, extracts `ClinicalFact` objects (Gemini for PDF/text, deterministic for FHIR/CSV), resolves patient identity, stores the source doc.

2. **Self-healing engine** — each `ClinicalFact` enters `app/engine/graph.py` (LangGraph): `recall_related` → if collision → `judge.py` (Gemini structured output) → `SUPERSEDES / CONTRADICTS / NEW / CONSISTENT` → reconcile in ledger (`app/memory/ledger.py`) + sync to Cognee graph.

3. **Recall** — `POST /ask?mode=total_recall` → Cognee `TEMPORAL` search on healed graph. `mode=naive` → Cognee `RAG_COMPLETION` on frozen pre-heal baseline. Both answers surface in the `ComparePage` split-chat.

4. **Conversational agent** — `POST /chat` → `app/agent/router.py` runs a ReAct loop with four patient-scoped tools (recall, ingest, propose_forget, explain). Destructive actions are staged via `propose_forget` → `POST /chat/approve`.

5. **Clinical checks** — on patient-open, `app/checks/engine.py` runs allergy, follow-up, risk, and hereditary checks; output is severity-ranked `Card` objects for the pre-visit brief.

6. **Graph UI** — `GET /graph?as_of=` returns nodes+edges filtered by `valid_from/valid_to`; the `RewindSlider` on `MemoryMapPage` drives the `as_of` param so superseded nodes grey out as you scrub time forward.
