# Total Recall — Entrypoints & Config

---

## How to Run

### Backend
```sh
cd backend
python -m uvicorn app.main:app --reload
# Serves on http://localhost:8000
```

### Frontend
```sh
cd frontend
npm run dev
# Vite dev server on http://localhost:5173
```

### CLI runner (ingest a timeline without the API)
```sh
cd backend
python -m app.engine.run                          # full (Vertex + Cognee)
python -m app.engine.run --no-cognee              # ledger + judge only (fast)
python -m app.engine.run --data ..\data\patient_timeline_01.json
```

### Build
```sh
cd frontend && npm run build    # tsc -b && vite build → dist/
```

### Tests
```sh
cd backend && pytest            # pytest.ini at backend/pytest.ini
```

---

## Main Entry Files

| File | Role |
|---|---|
| `backend/app/main.py:1` | FastAPI `app` object; router registration; startup hooks (`ledger.init`, `chat_history.init`, `audit.init`, optional `_precompute_seed`) |
| `backend/app/config.py:1` | **Import first** in every entrypoint — wires Vertex ADC env, Cognee storage, strips rogue API keys |
| `backend/app/engine/run.py:1` | CLI entrypoint for local timeline ingestion |
| `frontend/src/main.tsx:1` | React root; `QueryClientProvider` + `Toaster` wrap |
| `frontend/src/App.tsx:1` | `BrowserRouter` + routes; shows `TitleSequence` intro on first session load |

---

## API Routes

All routers registered in `backend/app/main.py:47-54`.

| Method | Path | Router file |
|---|---|---|
| `GET` | `/` | `main.py:84` — meta / endpoint list |
| `POST` | `/seed` | `routes_scenario.py` |
| `POST` | `/ingest` | `routes_scenario.py` |
| `POST` | `/reset` | `routes_scenario.py` |
| `POST` | `/forget` | `routes_scenario.py` |
| `GET` | `/health` | `routes_scenario.py` |
| `GET` | `/patients` | `routes_patients.py` |
| `POST` | `/patients` | `routes_patients.py` |
| `GET` | `/patients/{id}/brief` | `routes_patients.py` |
| `GET` | `/patients/{id}/documents` | `routes_patients.py` |
| `GET` | `/patients/resolve` | `routes_access.py` |
| `GET` | `/doctors` | `routes_access.py` |
| `GET` | `/audit` | `routes_access.py` |
| `POST` | `/ask` | `routes_ask.py` |
| `GET` | `/graph` | `routes_graph.py` |
| `GET` | `/graph/cognee` | `routes_graph.py` |
| `GET` | `/why` | `routes_graph.py` |
| `POST` | `/intake` | `routes_intake.py` |
| `POST` | `/upload` | `routes_intake.py` |
| `GET` | `/documents/{doc_id}` | `routes_intake.py` |
| `GET` | `/ingest_document` | `routes_intake.py` |
| `GET` | `/family/{patient_id}` | `routes_family.py` |
| `POST` | `/family/consent` | `routes_family.py` |
| `POST` | `/chat` | `routes_chat.py` |
| `POST` | `/chat/approve` | `routes_chat.py` |
| `GET/POST/DELETE` | `/chat/threads/*` | `routes_chat.py` |

---

## Frontend Routes

Defined in `frontend/src/App.tsx:29-37`.

| Path | Page component |
|---|---|
| `/login` | `pages/LoginPage.tsx` |
| `/` (index) | `pages/Dashboard.tsx` |
| `/patient/:id` | `pages/PatientWorkspace.tsx` |
| `/compare` | `pages/ComparePage.tsx` |
| `/memory` | `pages/MemoryMapPage.tsx` |
| `/board` | `pages/BoardPage.tsx` |

---

## Config Files

### Backend — `backend/.env` (copy from `.env.example`)

| Var | Default | Purpose |
|---|---|---|
| `VERTEXAI_PROJECT` | `ai-negotiation-copilot` | GCP project for Vertex ADC |
| `VERTEXAI_LOCATION` | `us-central1` | Vertex region |
| `EXTRACTION_MODEL` | `gemini-2.5-flash` | Cheap model for fact extraction |
| `JUDGE_MODEL` | `gemini-2.5-pro` | Strong model for contradiction judge |
| `EMBEDDING_PROVIDER` | `fastembed` | Local CPU embeddings (no key) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `EMBEDDING_DIMENSIONS` | `384` | Vector size |
| `COGNEE_SYS_DIR` | `C:\cg\sys` | Cognee system storage (short path, Windows MAX_PATH fix) |
| `COGNEE_DATA_DIR` | `C:\cg\data` | Cognee data storage |
| `LLM_API_KEY` | `vertex-adc` | Dummy key required by Cognee config gate (not used) |
| `ENGINE_CHECKPOINTS` | `C:\cg\engine_checkpoints.sqlite` | LangGraph checkpoint DB |
| `CORS_ORIGINS` | _(empty)_ | Extra allowed origins (comma-sep) |
| `PRECOMPUTE_SEED` | _(unset)_ | Set to `1` to warm Cognee graphs on startup |

### Frontend — `frontend/.env` (optional)

| Var | Default | Purpose |
|---|---|---|
| `VITE_API_BASE` | `http://localhost:8000` | Backend URL used by `api/client.ts:42` |

### Other config files

| File | Purpose |
|---|---|
| `backend/requirements.txt:1` | Python dependencies (pinned: cognee, langgraph, fastapi, google-genai, pypdf, sqlmodel) |
| `backend/pytest.ini:1` | pytest config |
| `frontend/package.json` | Node deps + scripts (`dev`, `build`, `lint`, `preview`) |
| `frontend/vite.config.ts` | Vite + `@vitejs/plugin-react` |
| `.vscode/settings.json` | Editor settings |

---

## Storage locations (runtime, local Windows)

| Store | Path | What lives there |
|---|---|---|
| Fact ledger | `C:\cg\ledger.db` | SQLite: `ClinicalFact` rows + lifecycle |
| LangGraph checkpoints | `C:\cg\engine_checkpoints.sqlite` | Per-patient engine state |
| Cognee system | `C:\cg\sys\` | Cognee metadata + Kuzu graph |
| Cognee data | `C:\cg\data\` | LanceDB vectors |
| Audit log | SQLite (same `C:\cg\` root) | Access + mutation audit |
| Chat history | SQLite (same root) | Per-thread message store |
