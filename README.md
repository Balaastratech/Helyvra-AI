# Total Recall — self-healing, time-aware clinical memory on Cognee

> **The Hangover Part AI: Where's My Context?** (WeMakeDevs × Cognee, Jun 29 – Jul 5 2026)
> Track: **Best Use of Open Source** (fully self-hosted Cognee). Solo build.
>
> ⚠️ **Demo only — synthetic data, not medical advice.** No real patient data (PHI/PII) anywhere.

**Total Recall is a clinical memory that never confidently tells a doctor something that's no longer true.**
A doctor uploads a patient's records — PDFs, lab reports, even a photo of a paper prescription — and the
agent builds a self-healing, time-aware memory that catches what a tired clinician misses: a dangerous
drug allergy, a lab that was never followed up, an inherited risk hiding across the family.

## The problem

The headline failure of AI memory isn't forgetting — it's **remembering wrong**. Naive RAG retrieves
*everything* it ever saw and answers with whichever chunk ranks highest: "the patient is allergic to
penicillin" (superseded four months ago), "on lisinopril" (switched in April). In healthcare a
confidently stale answer isn't a UX bug — it's a prescription for a patient who can't breathe.

Total Recall never silently overwrites and never blindly retrieves. Every new fact is reconciled
against existing memory at **write time**; superseded facts are kept with a validity window and a
`SUPERSEDED_BY` edge, so you can **rewind the graph to any date** and ask **"why did this change?"**

## Demo

- 🎬 **Demo video (≤2 min):** _link goes here_
- 🌐 **Live link:** _link goes here_

The money shot: ask *"Is the patient allergic to penicillin?"* side by side.
**Naive RAG: "Yes"** (stale, dangerous) · **Total Recall: "No — cleared 2026-03-02 by re-test (Dr. Lee)"**.

## How we use Cognee (5 of the 6 rarely-used primitives)

| Cognee primitive | Where | What it does here |
|---|---|---|
| `add` + `cognify(temporal_cognify=True)` | `backend/app/memory/cognee_client.py` (`add_fact`, `cognify`), invoked by the engine `persist` node | Every clinical fact enters memory time-aware |
| `search` — **TEMPORAL** | smart `/ask` path | Point-in-time answers ("was the patient allergic *in February*?") |
| `search` — **RAG_COMPLETION** | naive baseline over a frozen `naive_baseline` dataset | The villain: what every memoryless RAG app answers |
| `search` — **CHUNKS** | contradiction judge | Neighbor context when classifying a new fact |
| **`forget`** | `cognee_client.forget_fact` via `POST /forget` | Entered-in-error retraction. Supersession deliberately does **not** forget — it retains dated history |
| `improve` | after each heal (`persist` node) | Consolidates the graph after reconciliation |
| `get_graph_data` | `GET /graph/cognee` | Raw knowledge-graph view in the UI |
| `node_set` (patient scoping) + relational provenance | ledger `chain` / `GET /why` | Per-patient isolation + "why did this change?" trace |
| Custom `DataPoint` (`ClinicalFact`) | `backend/app/memory/schema.py` | Grounded, attribute-rich clinical facts instead of loose text |

## The self-healing pipeline

```
new fact
  └─ add(node_set=[patient]) + cognify(temporal_cognify=True)
  └─ recall related claims (scoped multi-hop)
  └─ contradiction judge (LLM, structured output)
        ├─ SUPERSEDES  → old fact gets valid_to + SUPERSEDED_BY edge, improve()
        ├─ CONTRADICTS → keep both, flag for review, lower confidence
        ├─ NEW         → store
        └─ CONSISTENT  → reinforce
```

Orchestrated with **LangGraph** (SQLite checkpointer = time-travel + auditability). Never hard-deletes
on supersession — that's what powers the time scrubber and the provenance trace. `forget()` is reserved
for facts that were outright entered in error.

## Stack (local-first, no API keys)

- **Memory:** Cognee self-hosted — SQLite (relational/provenance) + LanceDB (vectors) + Kuzu (graph)
- **LLM:** Vertex AI Gemini via ADC (extraction: Flash · contradiction judge: Pro, structured JSON)
- **Embeddings:** fastembed (local CPU, `all-MiniLM-L6-v2`) — $0, no key
- **Backend:** FastAPI (async) + LangGraph engine
- **Frontend:** React 19 + Vite + TS + Tailwind + react-force-graph-2d + vis-timeline

## Run locally

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # (Windows)
pip install -r requirements.txt
cp .env.example .env                              # fill in your GCP project (ADC, no API key)
python -m uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

Seed the demo patient: `POST /seed` (or use the in-app guided demo). Reset everything:
`python backend/scripts/clean_slate.py`.

## AI-assistant disclosure

Built with AI assistance: Claude (Claude Code), Gemini. All architecture decisions, verification,
and final code review by the author.

## License

[MIT](LICENSE) — fully open source, fully self-hostable.
