<div align="center">

# 🧠 Total Recall

### A self-healing, time-aware clinical memory built on self-hosted Cognee

**The Hangover Part AI: Where's My Context?** · WeMakeDevs × Cognee Hackathon (Jun 29 – Jul 5, 2026)
**Track: 🏆 Best Use of Open Source** — fully self-hosted Cognee, runs locally, no API keys

[Demo video](#-demo) · [Quickstart](#-run-it-locally) · [How we use Cognee](#-how-we-use-cognee) · [Architecture](#-architecture)

> ⚠️ **Demo only — synthetic data, not medical advice.** No real patient data (PHI/PII) anywhere.
> Built with AI assistance (see [disclosure](#-ai-assistance-disclosure)).

</div>

---

## The one-liner

**Total Recall is a clinical memory that never confidently tells a doctor something that's no longer true.**

A doctor uploads the records a clinic actually has — a plain note, a hospital discharge PDF, a lab
spreadsheet, even a *photo* of a paper prescription — and Cognee builds a **self-healing, time-aware
knowledge graph** that catches what a tired clinician misses: a dangerous drug allergy, a lab that was
never followed up, and an inherited risk hiding across a family.

## The problem — your AI woke up in Vegas

Your AI woke up with no memory of last night. It still thinks the patient is allergic to penicillin…
or worse, it forgot that he is.

The headline failure of AI memory isn't *forgetting* — it's **remembering wrong**. Naive RAG retrieves
*everything* it ever saw and answers with whichever chunk ranks highest: "the patient is allergic to
penicillin" (superseded months ago), "on lisinopril" (switched in April). In healthcare a confidently
stale answer isn't a UX bug — it's a prescription for a patient who can't breathe.

## The solution

Total Recall **never silently overwrites and never blindly retrieves**. Every new fact is reconciled
against existing memory at **write time**. Superseded facts are kept with a validity window and a
`SUPERSEDED_BY` edge — never hard-deleted — so you can **rewind the graph to any date** and ask
**"why did this change?"** The one operation that *does* delete is `forget()`, reserved for facts that
were entered in error.

---

## 🎬 Demo

- **Demo video (~3 min):** _paste your YouTube/Drive link here_
- **Live app:** _optional — paste deploy link, or run locally (below)_

**The money shot** — the doctor asks the Consult chat *"Can I prescribe amoxicillin?"* and the agent
answers, cited:

> **"Do not prescribe amoxicillin — the patient has a documented penicillin allergy (rash + breathing
> difficulty), from a 2021 discharge summary, page 2. Amoxicillin is a beta-lactam and cross-reacts."**

…and in the **Compare** view, the same "what BP med is he on now?" question gives two answers:
**Naive RAG → lisinopril (stale, wrong)** vs **Total Recall → amlodipine, switched from lisinopril on
2026-04-20** — with a timeline scrubber to rewind and watch the graph remember what *used* to be true.

---

## 🧩 How we use Cognee

Total Recall exercises the full **`remember → recall → improve → forget`** memory lifecycle — including
several of the rarely-touched primitives (temporal cognify, ontology grounding, memify, Dedup graph nodes).

| Lifecycle verb | Cognee primitive(s) | Where in this repo | What it does here |
|---|---|---|---|
| **remember** | `add(node_set=[patient])` + `cognify(temporal_cognify=True)` | `backend/app/memory/cognee_client.py`, invoked by the engine `persist` node | Every clinical fact enters an **isolated per-patient dataset**, time-aware |
| — grounding | OWL/RDF ontology resolver → `ontology_valid` | `backend/app/memory/ontology.py`, `ontology_classify.py` | "penicillin", "amoxicillin", "HbA1c" are validated clinical entities, not hallucinations |
| **recall** | `search` — **TEMPORAL** | smart `/ask` path | Point-in-time answers ("was he allergic *in February*?") |
| **recall** | `search` — **RAG_COMPLETION** | naive baseline over a frozen `naive` dataset | The villain: what every memoryless RAG app answers |
| **recall** | `search` — **CHUNKS** / graph | contradiction judge + `GET /graph/cognee` | Neighbor context for the judge; raw graph view in the UI |
| **improve** | `improve()` / **memify** | `persist` node after a heal; combined-risk enrichment | Repairs the graph after reconciliation; materializes cross-fact `CardiovascularRisk` relationships spanning 3 documents |
| **forget** | `forget()` | `cognee_client.forget_fact` via `POST /forget` | Entered-in-error retraction. Supersession deliberately does **not** forget — it retains dated history |
| custom `DataPoint` | `ClinicalFact`, `Dedup()` family nodes | `backend/app/memory/schema.py` | Grounded, attribute-rich facts + one shared `FamilyMember` node across linked charts |

## 🔄 The self-healing pipeline

```
new fact (from any file: txt · PDF · CSV · FHIR JSON · photo→Gemini vision)
  └─ add(node_set=[patient]) + cognify(temporal_cognify=True)      # remember
  └─ recall related claims (scoped, same-subject)                  # recall
  └─ contradiction judge  (Gemini, temperature 0, structured JSON)
        ├─ SUPERSEDES  → old fact gets valid_to + SUPERSEDED_BY edge, then improve()
        ├─ CONTRADICTS → keep both, flag for review, lower confidence
        ├─ NEW         → store
        └─ CONSISTENT  → reinforce
```

Orchestrated with **LangGraph** (SQLite checkpointer = time-travel + auditability). The ledger is the
authoritative store; Cognee is the hybrid graph-vector memory layer on top. Never hard-deletes on
supersession — that's what powers the time scrubber and the provenance trace.

---

## ✨ What it does (feature tour)

1. **Universal intake, zero data entry** — drop a `.txt`, PDF, CSV, FHIR JSON, or a *photo* of a paper
   prescription. The system detects the patient across formats and files everything to one chart. Images
   are read with Gemini vision (no OCR service, no GPU).
2. **Pre-visit brief** — before the visit, the agent surfaces the top things not to miss (rising HbA1c,
   an unfollowed high creatinine, combined cardiovascular risk), each **cited to its source page**.
3. **Prescribe-time safety STOP** — ask the Consult chat to prescribe amoxicillin and it refuses, citing
   a penicillin allergy buried in a 4-year-old PDF, connected through the ontology's beta-lactam
   cross-reactivity.
4. **Self-healing, rewindable memory** — a naive RAG pane vs Total Recall pane answer the same question;
   the timeline scrubber rewinds the graph to any date.
5. **Consented family graph** — a new patient's intake note names his father; the system dedup-links the
   charts and, with consent, flags hereditary risk.
6. **Provenance everywhere** — every answer is cited; "why did this change?" shows the superseding event,
   reason, source, and date.

---

## 🛠 Stack (local-first, no API keys required)

| Layer | Choice |
|---|---|
| **Memory** | **Cognee, self-hosted** — SQLite (relational/provenance) + LanceDB (vectors) + Kuzu (graph) |
| **LLM** | Vertex AI Gemini via ADC (extraction: Flash · contradiction judge: Pro, structured JSON) |
| **Embeddings** | fastembed (local CPU, `all-MiniLM-L6-v2`) — $0, no key |
| **Backend** | FastAPI (async) + a LangGraph self-healing engine |
| **Frontend** | React 19 + Vite + TypeScript + Tailwind + react-force-graph-2d + vis-timeline |

---

## 🚀 Run it locally

**Prerequisites:** Python 3.11+, Node 18+, and Google Cloud ADC configured (`gcloud auth
application-default login`) — no API key needed.

```bash
# 1. Backend  (http://localhost:8000)
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env            # set your GCP project id (ADC, not an API key)
python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend  (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Then open the app, pick a demo clinician, and either use the in-app guided demo or drop the files in
`data/demo_uploads/`. Regenerate demo files with `python backend/scripts/gen_demo_data.py`.

### Key API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/intake`, `/intake/batch` | Universal file ingest (auto-detects patient + format) |
| `POST` | `/ask` | Answer a question (`mode: total_recall` or `naive`, optional `as_of` date) |
| `GET` | `/patients/{id}/brief` | Pre-visit brief + not-to-miss cards |
| `POST` | `/seed` · `/ingest` · `/reset` | Load baseline · heal one fact live · clean slate |
| `POST` | `/forget` | Retract an entered-in-error fact |
| `GET` | `/graph` · `/graph/cognee` · `/why` | Ledger graph · raw Cognee graph · provenance trace |
| `GET` | `/family/{id}` · `POST /family/consent` | Family links + consent gate |
| `GET` | `/health` | Liveness of ledger + Cognee |

---

## 🏗 Architecture

Full design in **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**. In short:

```
┌────────────┐   files    ┌──────────────────────┐   fact    ┌─────────────────────────┐
│  React UI  │ ─────────► │  FastAPI intake API  │ ────────► │  LangGraph heal engine  │
│ (brief,    │ ◄───────── │  (parse · vision ·   │           │  recall→judge→reconcile │
│  compare,  │  cited     │   ontology ground)   │           │  →persist               │
│  scrubber) │  answers   └──────────────────────┘           └───────────┬─────────────┘
└────────────┘                                                            │ add · cognify · improve · forget
                                                        ┌─────────────────▼───────────────────┐
                                                        │  Cognee (self-hosted, per-patient)   │
                                                        │  SQLite · LanceDB · Kuzu graph       │
                                                        └──────────────────────────────────────┘
```

---

## ⚖️ Why this wins (mapped to the judging criteria)

| Criterion | How Total Recall answers it |
|---|---|
| **Potential Impact** | Stale clinical memory = patient harm. Allergy STOPs, missed-follow-up catches, and hereditary flags are concrete, undeniable safety outcomes. |
| **Creativity & Innovation** | Forgetting-as-a-feature, a *time machine* over the graph, reading a **photo** of a prescription, and a consented family graph. |
| **Technical Excellence** | Full memory lifecycle (remember/recall/improve/forget) + temporal cognify + ontology grounding + memify + Dedup graph + multimodal ingest, with write-time reconciliation and an auditable LangGraph engine. |
| **Best Use of Cognee** | Leans on the whole lifecycle **and the rare primitives** (temporal, ontology grounding, memify, Dedup) — and it's **self-hosted / local** (this track). |
| **User Experience** | Calm, light clinical workspace; cited answers; honest uncertainty; ⌘K palette; the noir Compare "money-shot". |
| **Presentation Quality** | This README, `docs/ARCHITECTURE.md`, and a code-generated demo video that maps every narration line to what's on screen. |

---

## 🤖 AI-assistance disclosure

This project was built with the help of AI coding tools. In the interest of full transparency, here is
every AI tool used to create this project:

| AI tool | How it was used |
|---|---|
| **Claude Code** (Anthropic) | Pair-programming, scaffolding, refactoring, and the code-generated demo video pipeline |
| **Kiro** (AWS) | Spec-driven development, requirements/design/task planning, and in-IDE implementation |
| **Codex** (OpenAI) | Code generation, completions, and debugging assistance |
| **Gemini** (Google) | Runtime LLM for clinical extraction, contradiction judging, and vision-based intake |

All architecture decisions, verification, and final code review were done by the author. The submission
complies with the hackathon rules on AI-tool disclosure.

## 📁 Repository layout

```
backend/      FastAPI app · LangGraph engine · Cognee client · clinical checks · intake pipeline
frontend/     React 19 + Vite clinical workspace (brief · consult · compare · memory map · scrubber)
data/         synthetic patients + demo_uploads (generated, not real PHI)
docs/         ARCHITECTURE.md · DEMO_SCRIPT.md · phase plans · PRD
video/        code-generated demo video pipeline (Playwright capture + HyperFrames/Remotion) — gitignored
```

## 📜 License

[MIT](LICENSE) — fully open source, fully self-hostable.
