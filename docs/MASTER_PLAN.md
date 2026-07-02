# MASTER PLAN — Total Recall

> Authoritative build plan for the Cognee hackathon ("The Hangover Part AI", Jun 29–Jul 5).
> Supersedes the earlier draft PHASE_PLAN. Reflects verified decisions:
> **Vertex AI (no API key)**, **LangGraph reconciliation engine**, **react-force-graph-2d**, **local-first build on the laptop**.
>
> Delivery model: this is the map. Each phase gets a deep step-by-step plan generated **when you start it**.

---

## 0. Decisions locked (so nothing changes later)

| Area | Decision | Why |
|---|---|---|
| Project / idea | **Total Recall** — self-healing, **temporal** memory (idea #1, upgraded). Codename only; rename later (Evergreen / Mnemo). | Highest win ceiling; uses the rarest Cognee primitives. |
| **Demo domain (the data)** | **Patient / health memory — synthetic.** Hero scenario = patient `P001` whose facts change over time (penicillin allergy → cleared; lisinopril → amlodipine; +type-2 diabetes). Data lives in `data/patient_timeline_01.json`. | Highest-impact story: a stale fact (outdated allergy / discontinued med) = patient harm. Makes the naive-vs-Total-Recall contrast undeniable. |
| Build mode | **Solo**, 7-day window (Jun 29–Jul 5). | Your call. |
| Track | **Best Use of Open Source** (local/self-hosted Cognee). | Bigger hardware prize; matches local-first build. |
| Stretch features | **#1 temporal time-scrubber (core)** + **#2 "Why did this change" provenance** + **#5 ClinicalFact DataPoint (ontology-as-schema)** — stacked as engine→layer→skin. | You liked all three; they're one product, not three. |
| Judge/extraction models | Extraction = **Gemini Flash**; contradiction judge = **Gemini Pro** (exact Vertex IDs: you confirm). | Cost-safe; quality only where it matters. |
| LLM | **Vertex AI Gemini** via Cognee→LiteLLM `custom` provider + ADC. No API key. | You have GCP credits; rules need no key; cleanest auth. |
| Embeddings | **fastembed (local, CPU)** — `all-MiniLM-L6-v2`, 384-dim | $0, no key, runs on your laptop. |
| Orchestration | **LangGraph** for the self-healing engine only | 4-way branching + checkpointer (= time-travel + "why") + judge appeal. |
| Memory | **Cognee local** (SQLite + LanceDB + Kuzu), 5 lifecycle ops | Core requirement; "Best Use of Open Source" track. |
| Graph viz | **react-force-graph-2d** | Easiest animated recolor/grey/hide for the time-scrubber demo. |
| Frontend | React 18 + Vite + TS + Tailwind + shadcn/ui | Your default stack; fast, clean, judge-friendly. |
| Backend | FastAPI (async) | Thin wrapper over the engine; matches Cognee async. |
| Judge LLM calls | **google-genai SDK (Vertex mode)** with `response_schema` | Reliable structured JSON for the contradiction classifier. Same ADC as Cognee. |
| Deploy | **Decide in Phase 7** (Cloud Run vs Cloudflare Tunnel) | Build local-first; choose share method once it works. |
| Data | **Synthetic only**, single-user, no auth | Demo; avoids PHI/compliance scope. |
| Theme | **"Neon-Noir Clinic"** — Hangover × clinical, dual-register (dark neon framing → light clinical clarity). Full spec in `docs/theme-hangover.md`. Additive skin/copy/motion only. | On-theme + memorable without losing clinical trust; the film's "reconstruct the lost timeline" = our algorithm. |

**Hardware verdict:** build 100% on the IdeaPad S340 (20 GB RAM). No GPU, no rental. Only local compute is fastembed on CPU.

---

## 0.5 Demo scenario & data (what we actually feed it)

**Domain: synthetic patient memory.** Single patient `P001`. Source of truth: `data/patient_timeline_01.json` (already created). A 2nd patient (`patient_timeline_02.json`) is a Phase-5 stretch.

Time-ordered facts (some deliberately contradict earlier ones):
| Date | Fact | Note |
|---|---|---|
| 2026-01-10 | Penicillin **allergy diagnosed** (Dr. Adams) | baseline |
| 2026-02-15 | Prescribed **lisinopril 10mg** (hypertension) | baseline |
| 2026-03-02 | Penicillin allergy **cleared** by re-test (Dr. Lee) | **supersedes** 2026-01-10 |
| 2026-04-20 | Stopped lisinopril → **switched to amlodipine 5mg** (Dr. Lee) | **supersedes** 2026-02-15 |
| 2026-05-11 | **Type-2 diabetes diagnosed** (Dr. Patel) | new fact |

**The money-shot demo questions:**
- "Is the patient allergic to penicillin?" → Naive RAG may answer **yes** (from Jan 10) = **dangerous**; Total Recall answers **no — cleared 2026-03-02**.
- "What blood-pressure medication is the patient on?" → correct = **amlodipine** (switched from lisinopril).
- Scrub the time-slider to **February** → graph shows the allergy node *active*; scrub to **now** → it's greyed/superseded.
- Click the allergy node → **"Why did this change?"** → superseded 2026-03-02 by Dr. Lee's re-test.

**Guardrails:** synthetic data only (no PHI), prominent "demo only — not medical advice" banner everywhere.

---

## 1. Architecture (recap)

```
                ┌──────────────────────── Frontend (Vite/React/TS/Tailwind/shadcn) ───────────────────────┐
                │  Split-Chat (Total Recall ⟷ Naive)   │  Graph + Time-Scrubber   │  "Why did this change?" │
                └───────────────────────────────────────────────┬─────────────────────────────────────────┘
                                                                 │ REST (fetch)
                ┌────────────────────────────── Backend (FastAPI, async) ──────────────────────────────────┐
                │  /seed  /ingest  /ask(mode,as_of)  /graph(as_of)  /why(fact_id)                            │
                │                                                                                            │
                │   LangGraph reconciliation engine        Cognee adapter (one module wraps all Cognee)     │
                │   ingest→recall→judge→route→reconcile     remember/recall/improve/forget + temporal       │
                │   (SqliteSaver checkpointer)              ClinicalFact DataPoint, node_set per patient     │
                └───────────────┬──────────────────────────────────────┬───────────────────────────────────┘
                                │ google-genai (Vertex, ADC)            │ Cognee→LiteLLM (Vertex, ADC)
                          Gemini (judge: JSON)                    Gemini (extraction) + fastembed (local)
                                                                        │
                                              SQLite (provenance) + LanceDB (vectors) + Kuzu (graph)
```

**Cognee primitives used (judges scan for these):** `add`/`remember`, `cognify(temporal_cognify=True)`, `search`/`recall` (`GRAPH_COMPLETION`, `TEMPORAL`, `RAG_COMPLETION` for the naive baseline), `improve`/`memify`, `forget`, custom `DataPoint`, `node_set` scoping, provenance. **5 of 6 rare primitives.**

---

## 2. Repository layout (final)

```
total-recall/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI app + routes
│  │  ├─ config.py               # env loading, Vertex/Cognee wiring, Windows path fix
│  │  ├─ memory/
│  │  │  ├─ cognee_client.py     # ALL Cognee calls live here (single seam)
│  │  │  └─ schema.py            # ClinicalFact DataPoint (Pydantic)
│  │  ├─ engine/                 # LangGraph self-healing engine
│  │  │  ├─ state.py             # TRState TypedDict
│  │  │  ├─ nodes.py             # recall_related, judge, reconcile_*, persist
│  │  │  ├─ judge.py             # google-genai Vertex structured classifier
│  │  │  └─ graph.py             # StateGraph wiring + SqliteSaver
│  │  └─ api/
│  │     ├─ routes_ingest.py
│  │     ├─ routes_ask.py
│  │     └─ routes_graph.py
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/                     # Vite React TS
│  └─ src/
│     ├─ api/client.ts
│     ├─ components/
│     │  ├─ SplitChat.tsx
│     │  ├─ GraphView.tsx        # react-force-graph-2d
│     │  ├─ TimeScrubber.tsx
│     │  ├─ WhyPanel.tsx
│     │  └─ DisclaimerBanner.tsx
│     └─ App.tsx
├─ data/  patient_timeline_01.json  patient_timeline_02.json
├─ docs/  PRD.md  ARCHITECTURE.md  MASTER_PLAN.md  (+ per-phase plans)
├─ spike/ (kept for reference)
└─ README.md
```

---

## 3. Prerequisites you provide once (Phase 0 needs these)

- **GCP project ID** with billing/credits + **Vertex AI API enabled**.
- **Region** (default `us-central1`).
- **Model IDs** to use on Vertex (default extraction `vertex_ai/gemini-2.5-flash`; judge `gemini-2.5-pro` — confirm what's enabled in your project; you mentioned 3.x exists in your stack, we can use that).
- `gcloud` CLI installed; run `gcloud auth application-default login` once.
- Confirm **no** `GEMINI_API_KEY` / `GOOGLE_API_KEY` set in your shell/profile (they override ADC).

(The plan references these as config; exact values go in `backend/.env` in Phase 0.)

---

## 4. The phases (map). Tier-1 is submittable by end of Phase 4.

Legend — each phase has: **Goal · Build (what/how/tools) · Deliverables · Verify · Done-when**.

### Phase 0 — Vertex wiring + temporal confirmed (½ day)
- **Goal:** Cognee runs locally using **Vertex (no key)**; temporal before/after proven.
- **Build:** new `backend/` skeleton; `config.py` sets `LLM_PROVIDER=custom`, `LLM_MODEL=vertex_ai/<model>`, `VERTEXAI_PROJECT/LOCATION`, fastembed embeddings, and the Windows short-path fix (`C:\cg`). Port the spike's contradiction scenario to run through Vertex. Unset any Gemini API-key env vars.
- **Tools:** cognee 1.2.2, litellm (bundled), python-dotenv, fastembed, `gcloud` ADC.
- **Deliverables:** `config.py`, `.env`, a `verify_vertex.py` that runs add→cognify(temporal)→recall.
- **Verify:** "before Feb → allergic", "after March → not allergic"; confirm **zero** API-key usage (check it fails clearly if ADC is missing).
- **Done-when:** temporal answers are correct via Vertex, logged cost ≈ pennies.

### Phase 1 — Self-healing engine (LangGraph) (Day 1–2) ← **core**
- **Goal:** ingest a fact → detect supersession/contradiction → reconcile, keeping current truth correct while retaining history.
- **Build:** `engine/state.py` (TRState), `engine/judge.py` (google-genai Vertex classifier → `{classification, target_fact_id, reason, confidence}` via `response_schema`), `engine/nodes.py` (`recall_related` via Cognee graph search scoped by `node_set`+subject; `reconcile_supersede` sets `valid_to` + `SUPERSEDED_BY` edge + `improve()`; `reconcile_contradict` flags + lowers confidence; `store_new`; `reinforce`), `engine/graph.py` (StateGraph + conditional edges + **SqliteSaver** checkpointer). `memory/schema.py` ClinicalFact; `memory/cognee_client.py` seam.
- **Tools:** langgraph, langgraph-checkpoint-sqlite, google-genai, cognee.
- **Deliverables:** runnable engine + unit tests on the seeded supersession cases.
- **Verify:** TDD the classifier on `patient_timeline_01.json`; ingesting the timeline yields correct current-truth in a script; checkpoints persist.
- **Done-when:** the 3 supersession events classify + reconcile correctly, deterministically.

### Phase 2 — Backend API + naive baseline (Day 2–3)
- **Goal:** HTTP surface + the "villain" baseline for the side-by-side.
- **Build:** FastAPI routes — `POST /seed`, `POST /ingest` (runs the engine), `POST /ask {question, mode: total_recall|naive, as_of?}`, `GET /graph?as_of=`. **Naive mode** = plain Cognee `RAG_COMPLETION`/`CHUNKS` (no reconciliation) → returns stale/dangerous answer. `/graph` returns nodes+edges filtered by `valid_from/valid_to` for the scrubber.
- **Tools:** fastapi, uvicorn, pydantic.
- **Deliverables:** working API; curl/HTTPie test script.
- **Verify:** same question, both modes → demonstrably different answers; `/graph?as_of=` returns correct snapshots for ≥2 dates.
- **Done-when:** the dangerous-vs-correct contrast is reproducible from the API.

### Phase 3 — Frontend: split-chat + graph + scrubber (Day 3–4) ← **Tier-1 complete**
- **Goal:** the demo that makes a judge stop scrolling.
- **Build:** Vite React TS + Tailwind + shadcn. `SplitChat` (Total Recall vs Naive, same input), `GraphView` (react-force-graph-2d; superseded nodes greyed, `SUPERSEDED_BY` edges dashed), `TimeScrubber` (date slider → refetch `/graph?as_of=` → graph morphs), `DisclaimerBanner` ("demo only, synthetic data, not medical advice").
- **Tools:** vite, react, tailwind, shadcn/ui, react-force-graph-2d.
- **Deliverables:** running UI wired to the API.
- **Verify (preview tools):** ask the allergy question in both panes; drag the scrubber across ≥2 dates and watch nodes grey out; screenshot.
- **Done-when:** **complete, submittable project.** Record an insurance screen-capture here.

### Phase 4 — "Why did this change?" provenance (Day 5) ← eye-catch
- **Goal:** click a corrected fact → trace *why* it changed.
- **Build:** `GET /why?fact_id=` traverses `SUPERSEDED_BY`/provenance (Cognee graph + relational store; `NATURAL_LANGUAGE`/`CYPHER` if needed) → returns the superseding event + source + date + path. `WhyPanel` renders the trace on node click.
- **Verify:** clicking the (now-cleared) allergy explains: superseded 2026-03-02 by Dr. Lee re-test.
- **Done-when:** ≥1 correct provenance trace renders end-to-end.

### Phase 5 — STRETCH: depth credit (Day 6)
- **Goal:** maximize "Technical Excellence" + "Best Use of Cognee".
- **Build (pick by remaining time):** (a) full `ClinicalFact` DataPoint extraction via `custom_prompt`/custom Task; (b) `memify()` "consolidation" pass + 2nd patient timeline; (c) feedback-weight reinforce.
- **Verify:** graph shows typed clinical nodes; second patient works; memify prunes/strengthens visibly.
- **Done-when:** at least one stretch item demoably improves the graph.

### Phase 6 — Polish + harden + deploy decision (Day 6)
- **Goal:** no rough edges; choose share method.
- **Build:** empty/loading/error states, seed-reset button, spend log, README scaffolding. **Deploy decision:** Cloud Run (always-on, ADC via attached SA, min-instances=1, seed-on-startup) **or** Cloudflare Tunnel from laptop. (Linux container removes the Windows path issue entirely.)
- **Verify:** cold-start the chosen target; share link opens for someone else.
- **Done-when:** a working link exists (or local+tunnel rehearsed).

### Phase 7 — Submission & meta-game (Day 7) ← wins the other half
- **Goal:** presentation points + bonus tracks.
- **Build:**
  - **Demo video ≤2 min:** problem → naive kills patient → Total Recall saves → scrubber rewind → "why" trace → name each Cognee primitive.
  - **README:** problem, architecture diagram, **"How we use Cognee"** (name every primitive), run instructions, **AI-assistant disclosure** (required by rules), disclaimer.
  - **Best-Blog post** + **Social-Buzz thread** from the same material (extra prizes).
  - Optional **PR track:** 1–3 genuine Cognee issues ($100 each) — comment, tag maintainers, wait for assignment; **never spam / no typo PRs / ≤5 PRs** (permanent-ban rules).
- **Done-when:** submitted early with video + README (+disclosure) + working link.

---

## 5. Cost controls (cost-safe by default)
- Extraction LLM = **Flash** (cheap); judge = Pro only on subject/predicate collisions (few calls).
- Small synthetic dataset; `cognify` runs once per seed.
- Local embeddings = $0.
- `spend.log` per run; hard cap on total LLM calls; abort if exceeded.
- Vertex spend hits **GCP credits**, not a card.

## 6. Risk register
| Risk | Mitigation |
|---|---|
| Vertex/ADC misconfig | Phase 0 isolates it; `verify_vertex.py` fails loudly if ADC missing. |
| Cognee API drift (1.x) | All Cognee calls behind `cognee_client.py`; pin `cognee==1.2.2`. |
| Judge unreliable | Structured `response_schema`; dedupe by subject/predicate before calling judge. |
| Windows path limit | `C:\cg` short root locally; Linux container in deploy. |
| Scope creep (solo) | Strict tier ladder; cut from top of stretch, never Tier-1. |
| Temporal not granular enough | Fallback: enforce `valid_to` ourselves via ClinicalFact (already in design). |

## 7. Rules-compliance checklist (don't lose on a technicality)
- [ ] Uses Cognee for memory (5 lifecycle ops) ✅ by design
- [ ] **AI-assistant use declared** in submission ⚠️ easy to forget
- [ ] Public repo + clear README + ≤2-min demo
- [ ] Synthetic data + "not medical advice" disclaimer
- [ ] If doing PRs: assignment-first, ≤5, no low-effort/AI-spam
- [ ] Built during event window (Jun 29–Jul 5) ✅

## 8. Definition of done (minimum to submit)
Tier-1 (Phases 0–3) complete + 2-min video + README with "How we use Cognee" + AI disclosure + disclaimer. Everything after is score-maximizing upside.

---

## 9. Verified engineering findings (live — keep updated)

**Phase 0 — PASSED (2026-06-29).** Cognee 1.2.2 on **Vertex AI, no API key**, on the laptop:
before-Feb = allergic, after-March = not allergic, med-now = amlodipine, current-truth = not allergic. No `LanceError`.

Hard-won facts to build on (not assumptions — observed):
- **Vertex wiring:** `LLM_PROVIDER=custom` + `LLM_MODEL=vertex_ai/gemini-2.5-flash` + `VERTEXAI_PROJECT/LOCATION` + ADC. Cognee's `custom` provider **requires a non-empty `LLM_API_KEY`** as a config gate → set dummy `LLM_API_KEY=vertex-adc` (Vertex ignores it).
- **Windows:** Cognee storage MUST sit on a short root (`C:\cg`) or LanceDB hits the 260-char path limit.
- **Reframed differentiation:** Cognee's built-in `TEMPORAL` search **already** answers before/after supersession correctly. So our win is NOT making temporal work — it's the **visible, explainable self-healing**: write-time contradiction detection + explicit `SUPERSEDED_BY` edges + node greying + "why did this change" provenance, contrasted against a genuinely-naive baseline.
- **Naive "villain" =** `SearchType.RAG_COMPLETION` (chunks→LLM, no graph/temporal) → returns the stale/dangerous answer. Total Recall = `TEMPORAL`/`GRAPH_COMPLETION` + our healing.
- **Graph for the UI:** `from cognee.infrastructure.databases.graph import get_graph_engine` → `nodes, edges = await get_graph_engine().get_graph_data()`. Also `visualize_graph(path)` for a quick HTML fallback.
- **recall() return shape:** list of `ResponseGraphEntry(text, search_type, dataset_id, dataset_name, raw, source=...)` → API must serialize `.text` (+ optionally raw) to JSON.
- **Known cosmetic issue:** temporal `Timestamp` nodes log "Falling back to class name 'Timestamp' … neither metadata['index_fields'] nor name" → they render label-less. Fix in Phase 5 via the `ClinicalFact` DataPoint with `metadata={"index_fields": [...]}`; until then the viz must handle unlabeled nodes gracefully.
- **Built-in query router:** `recall()` auto-routes (regex) to TEMPORAL on "before/after/when". We will **force** `query_type` explicitly per call so behavior is deterministic in the demo.

**Phase 2 — PASSED (2026-06-29).** FastAPI surface over the engine + Cognee, with the naive baseline. `tests/test_api.py` = 10/10 green (real Vertex + Cognee, in-process httpx). Endpoints: `POST /seed /ingest /reset`, `POST /ask`, `GET /graph /graph/cognee /why /health`.

Money-shot contrast is reproducible from the API:
- **naive** `RAG_COMPLETION` → **"Yes, allergic to penicillin."** (stale/dangerous)
- **total_recall** `TEMPORAL` → **"No — penicillin allergy was cleared on 2026-03-02."** (current truth + the date it changed)
- **total_recall + `as_of=2026-02-15`** `TEMPORAL` → **"Yes, was allergic as of 2026-02-15."** (history retained — past-tense correct)

Hard-won Phase-2 facts (observed, not assumed):
- **Supersession RETAINS history in Cognee — it does NOT forget** (ARCHITECTURE.md "never hard-delete on supersession"). An earlier build forgot the stale assertion on `SUPERSEDES`; that broke past-tense temporal recall (the time-scrubber / "evergreen memory" thesis). Fixed: `persist` keeps BOTH dated assertions so `temporal_cognify` answers current AND past correctly. `forget()` is reserved for facts entered in error — now wired via `POST /forget` (Phase 2b, `docs/phase-2b-forget.md`).
- **`forget()` is implemented (Phase 2b).** Cognee 1.2.2 signature: `forget(data_id=, dataset=, dataset_id=, everything=, memory_only=, user=)`. We use single-item mode `forget(data_id=UUID, dataset=DATASET)` via `cognee_client.forget_fact`. `POST /forget {patient_id, fact_id, reason}` removes the assertion from Cognee, marks the ledger row `retracted` (audit kept, excluded from current truth/graph), and restores any fact it had wrongly superseded. Test `test_forget_retracts_and_removes` is green (real Cognee deletion summary).
- **GRAPH_COMPLETION is unreliable for yes/no questions** — it intermittently returned garbage ("Got it.") for "Is the patient allergic to penicillin?", while **TEMPORAL** consistently answered "No." and "Amlodipine 5mg". So the smart `/ask` path **forces TEMPORAL** for every query (rarest primitive + reliable), not the plan's literal "else GRAPH_COMPLETION".
- **Naive villain needs its own frozen dataset.** Since the smart dataset now retains both facts, a naive RAG query over it would read the correction too and "accidentally" self-correct to "No" (Risk E confirmed live). Fix: a separate `naive_baseline` dataset frozen at the **pre-heal seed snapshot** (corrective `/ingest`s are NOT written to it). Then naive stays dangerously "Yes".
- **`hold_back` flags** added to `data/patient_timeline_01.json` on the two superseding events (allergy cleared 2026-03-02, amlodipine switch 2026-04-20). `/seed` loads only the non-held-back baseline; the contradictions arrive via live `/ingest`.
- **Pydantic field/type name collision:** a response field literally named `date` typed `Optional[date]` resolves the annotation to the default `None` → "Input should be None". Qualify as `Optional[datetime.date]`.
- **`/ingest` accepts free text** (Vertex Flash extractor in `engine/extract.py`) **or** structured fields. The demo/tests use structured fields for determinism.
- **`node_set` scoping:** single-patient demo, so dataset scoping == patient scoping. We scope by `datasets=[...]` (verified path) and accept `node_set` for API parity without guessing an unverified Cognee kwarg.
- Engine runs each ingest on its own checkpoint thread (`{patient_id}:{fact.id}`) so `/ingest` actions/classification reflect only that fact.
