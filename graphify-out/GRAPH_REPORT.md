# Graph Report - backend/ + frontend/src/ + docs/  (2026-07-02)

## Corpus Check
- 155 files · ~114,579 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 999 nodes · 2102 edges · 46 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 849 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Allergy Checks & Rules|Allergy Checks & Rules]]
- [[_COMMUNITY_Audit & Logging|Audit & Logging]]
- [[_COMMUNITY_Cognee Client & Config|Cognee Client & Config]]
- [[_COMMUNITY_Answer Synthesis & Citations|Answer Synthesis & Citations]]
- [[_COMMUNITY_Intake Pipeline & Records|Intake Pipeline & Records]]
- [[_COMMUNITY_FHIR Extraction & Structured Data|FHIR Extraction & Structured Data]]
- [[_COMMUNITY_Allergy Check Engine|Allergy Check Engine]]
- [[_COMMUNITY_Architecture Concepts (Docs)|Architecture Concepts (Docs)]]
- [[_COMMUNITY_Family Graph & Patient Index|Family Graph & Patient Index]]
- [[_COMMUNITY_Engine Judge & Schema|Engine Judge & Schema]]
- [[_COMMUNITY_LangGraph Engine Core|LangGraph Engine Core]]
- [[_COMMUNITY_Chat API & UI|Chat API & UI]]
- [[_COMMUNITY_Auth & Access Control|Auth & Access Control]]
- [[_COMMUNITY_App Entry & Command Palette|App Entry & Command Palette]]
- [[_COMMUNITY_API Client & Tests|API Client & Tests]]
- [[_COMMUNITY_Clinical Check Engine|Clinical Check Engine]]
- [[_COMMUNITY_React Hooks & Patient Picker|React Hooks & Patient Picker]]
- [[_COMMUNITY_Python Dependencies|Python Dependencies]]
- [[_COMMUNITY_Force Graph Canvas|Force Graph Canvas]]
- [[_COMMUNITY_Time Slider & Rewind|Time Slider & Rewind]]
- [[_COMMUNITY_Module Group 20|Module Group 20]]
- [[_COMMUNITY_Module Group 26|Module Group 26]]
- [[_COMMUNITY_Module Group 51|Module Group 51]]
- [[_COMMUNITY_Module Group 52|Module Group 52]]
- [[_COMMUNITY_Module Group 69|Module Group 69]]
- [[_COMMUNITY_Module Group 70|Module Group 70]]
- [[_COMMUNITY_Module Group 71|Module Group 71]]
- [[_COMMUNITY_Module Group 72|Module Group 72]]
- [[_COMMUNITY_Module Group 73|Module Group 73]]
- [[_COMMUNITY_Module Group 74|Module Group 74]]
- [[_COMMUNITY_Module Group 75|Module Group 75]]
- [[_COMMUNITY_Module Group 76|Module Group 76]]
- [[_COMMUNITY_Module Group 77|Module Group 77]]
- [[_COMMUNITY_Module Group 78|Module Group 78]]
- [[_COMMUNITY_Module Group 79|Module Group 79]]
- [[_COMMUNITY_Module Group 80|Module Group 80]]
- [[_COMMUNITY_Module Group 81|Module Group 81]]
- [[_COMMUNITY_Module Group 82|Module Group 82]]
- [[_COMMUNITY_Module Group 83|Module Group 83]]
- [[_COMMUNITY_Module Group 84|Module Group 84]]
- [[_COMMUNITY_Module Group 85|Module Group 85]]
- [[_COMMUNITY_Module Group 86|Module Group 86]]
- [[_COMMUNITY_Module Group 87|Module Group 87]]
- [[_COMMUNITY_Module Group 88|Module Group 88]]
- [[_COMMUNITY_Module Group 89|Module Group 89]]
- [[_COMMUNITY_Module Group 90|Module Group 90]]

## God Nodes (most connected - your core abstractions)
1. `ClinicalFact` - 175 edges
2. `get()` - 118 edges
3. `all()` - 38 edges
4. `Card` - 27 edges
5. `add()` - 24 edges
6. `TRState` - 22 edges
7. `run()` - 20 edges
8. `run()` - 19 edges
9. `resolve_links()` - 16 edges
10. `seed()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Patient-scoped agent tools (the four memory verbs).  `build_patient_tools(pati` --uses--> `ClinicalFact`  [INFERRED]
  backend\app\agent\tools.py → backend\app\memory\schema.py
- `Function-calling schemas the model sees. NOTE: no `patient_id` anywhere —     s` --uses--> `ClinicalFact`  [INFERRED]
  backend\app\agent\tools.py → backend\app\memory\schema.py
- `Map a free-text description ('penicillin allergy') to one active fact.      Th` --uses--> `ClinicalFact`  [INFERRED]
  backend\app\agent\tools.py → backend\app\memory\schema.py
- `Build a provenance narrative + the most relevant fact_id for the UI.` --uses--> `ClinicalFact`  [INFERRED]
  backend\app\agent\tools.py → backend\app\memory\schema.py
- `Actually retract a fact (Cognee + ledger). The ONLY place a forget executes,` --uses--> `ClinicalFact`  [INFERRED]
  backend\app\agent\tools.py → backend\app\memory\schema.py

## Hyperedges (group relationships)
- **Cognee Memory Lifecycle (add/cognify/search/improve/forget)** — concept_cognee, concept_temporal_cognify, concept_memify, concept_self_healing, concept_supersession [EXTRACTED 1.00]
- **Clinical Safety System** — concept_check_engine, concept_allergy_check, concept_followup_gap, concept_combined_risk, concept_hereditary_risk, concept_ontology [EXTRACTED 1.00]
- **Demo Money Shot (Naive vs Total Recall)** — concept_naive_baseline, concept_split_chat, concept_self_healing, concept_patient_p001 [EXTRACTED 1.00]

## Communities

### Community 0 - "Allergy Checks & Rules"
Cohesion: 0.06
Nodes (104): allergy_check — allergy-before-prescribe, the #1 hero check (§5.2).  Two entry, Open-brief mode: flag active medications that conflict with active     allergie, Active allergy facts (a 'cleared' allergy is not a contraindication)., True if `drug` is contraindicated by an allergy to `substance`: same drug,, Prescribe-time safety check: is `drug` safe given the patient's active     alle, _LLMOut, What the model returns. It only PICKS which facts it used (by id) — the     cit, BaseModel (+96 more)

### Community 1 - "Audit & Logging"
Cohesion: 0.03
Nodes (82): AuditEntry, log(), Real audit trail (CLINICAL_COPILOT_PLAN §7).  This is the one part of the iden, Append one audit row. Best-effort: auditing must never break the request it, Read the log newest-first, optionally scoped to one patient., recent(), add_message(), chat_dataset_for() (+74 more)

### Community 2 - "Cognee Client & Config"
Cohesion: 0.04
Nodes (66): _add_data_points(), add_fact(), add_family_members(), add_naive(), cognify(), cognify_naive(), dataset_for(), _entry_raw() (+58 more)

### Community 3 - "Answer Synthesis & Citations"
Cohesion: 0.05
Nodes (62): Citation, _citations_for(), _enforce_certainty(), _format_history(), Answer synthesis — the "past vs present" narrator, now cited and uncertainty-awa, Format fact history for the LLM prompt (includes id, status, confidence)., Build authoritative Citations from the facts the model cited (by id)., Deterministic guard over the model's self-reported certainty — the prompt     a (+54 more)

### Community 4 - "Intake Pipeline & Records"
Cohesion: 0.05
Nodes (55): decide(), invalidate(), uploadFiles(), useDocument(), useDocuments(), extract_pdf_pages(), _identity_from_csv(), _image_mime() (+47 more)

### Community 5 - "FHIR Extraction & Structured Data"
Cohesion: 0.08
Nodes (57): Map one extracted fact to the shared attribute-rich assert shape., _rich_fact_to_assert(), _codeable_text(), _codeable_text_list(), _coding_text(), extract_facts(), extract_patient_identity(), is_fhir_bundle() (+49 more)

### Community 6 - "Allergy Check Engine"
Cohesion: 0.06
Nodes (49): _active_allergies(), _conflict_card(), for_drug(), _matches(), run(), _substance(), Card(), cite() (+41 more)

### Community 7 - "Architecture Concepts (Docs)"
Cohesion: 0.08
Nodes (58): Agent Tool-Calling (Gemini), Allergy Check (Cross-Reactivity), Real Audit Trail, Background Cognify (Perf), Batch Cognify, Clinical Check Engine (CDS-Hooks), Clinical Copilot, ClinicalFact DataPoint (+50 more)

### Community 8 - "Family Graph & Patient Index"
Cohesion: 0.06
Nodes (45): onResolve(), open(), _birth_year(), _generation_plausible(), links_for(), _load(), _match_patient(), _mirror_to_cognee() (+37 more)

### Community 9 - "Engine Judge & Schema"
Cohesion: 0.06
Nodes (42): main(), CLEAN SLATE — wipe all patient memory + state for a fresh demo.  Clears BOTH lay, Use the app's own reset functions (also prunes Cognee cleanly)., _reset_json(), _reset_via_app(), _rm(), Wipe all Cognee data + system metadata (fresh demo run)., seed_reset() (+34 more)

### Community 10 - "LangGraph Engine Core"
Cohesion: 0.08
Nodes (38): build_graph(), checkpointer(), LangGraph wiring + SqliteSaver checkpointer.      START -> recall_related --(e, Compile the self-healing engine. Pass a checkpointer or None., AsyncSqliteSaver bound to the engine checkpoint DB (short Windows path)., judge_node(), _log(), Graph node functions.  Flow:   START -> recall_related -> (judge | store_new) (+30 more)

### Community 11 - "Chat API & UI"
Cohesion: 0.09
Nodes (22): onSubmit(), sendMessage(), get_thread(), chat(), chat_approve(), ChatApproveRequest, ChatApproveResponse, ChatRequest (+14 more)

### Community 12 - "Auth & Access Control"
Cohesion: 0.12
Nodes (23): allowed_patients(), can_access(), get_doctor(), list_doctors(), _load(), Simulated identity + access layer (CLINICAL_COPILOT_PLAN §7).  Deliberately th, The login picker's roster (id · name · specialty · role) — no patient lists., Patient ids this doctor may open. Empty list if the doctor is unknown. (+15 more)

### Community 13 - "App Entry & Command Palette"
Cohesion: 0.13
Nodes (20): openPatient(), run(), _maybe_precompute(), _precompute_seed(), FastAPI app — the HTTP surface over the self-healing engine + Cognee memory., Cognify every seed patient's dataset once so the live demo is warm., _startup(), Ingest the full timeline + a restated fact ONCE for the module.      Returns a (+12 more)

### Community 14 - "API Client & Tests"
Cohesion: 0.09
Nodes (9): ApiError, http(), post(), flow(), Phase 2 API acceptance tests (integration).  Drives the FastAPI app in-process, Superseded facts are NOT forgotten: as-of February the patient WAS allergic., _run_flow(), test_ask_past_tense_retained() (+1 more)

### Community 15 - "Clinical Check Engine"
Cohesion: 0.15
Nodes (15): Most-severe-first, capped (§5.2 'top 3–5 by severity' — alert-fatigue)., top_by_severity(), The clinical check engine (§5.2).  Every check is a module exposing `run(patie, All open checks for a patient → the pre-visit brief's not-to-miss cards,     mo, Prescribe-time safety checks for a proposed drug, run BEFORE any write     (§5., run_open_checks(), run_prescribe_checks(), _by_prefix() (+7 more)

### Community 16 - "React Hooks & Patient Picker"
Cohesion: 0.13
Nodes (7): useCreatePatient(), usePatients(), useTimeline(), PatientPicker(), escapeHtml(), PatientTimeline(), tooltip()

### Community 17 - "Python Dependencies"
Cohesion: 0.14
Nodes (14): aiosqlite                      # async checkpointer backend (AsyncSqliteSaver), cognee, fastapi, fastembed                      # local embeddings (CPU, no key), google-genai, httpx                          # in-process ASGI client for API tests, langgraph, langgraph-checkpoint-sqlite (+6 more)

### Community 18 - "Force Graph Canvas"
Cohesion: 0.28
Nodes (5): drawBackground(), isLit(), laneOf(), layout(), timeToX()

### Community 19 - "Time Slider & Rewind"
Cohesion: 0.36
Nodes (5): onChange(), isoOf(), parseDate(), statusAt(), todayIso()

### Community 20 - "Module Group 20"
Cohesion: 0.4
Nodes (1): Memory layer: canonical fact schema, authoritative ledger, and the Cognee seam.

### Community 26 - "Module Group 26"
Cohesion: 1.0
Nodes (1): Test isolation: point the ledger + checkpointer at dedicated SHORT-path DBs BEF

### Community 51 - "Module Group 51"
Cohesion: 1.0
Nodes (1): Build a fact from a `patient_timeline_*.json` entry.

### Community 52 - "Module Group 52"
Cohesion: 1.0
Nodes (1): Plain-English label, serialized to JSON for every fact display.

### Community 69 - "Module Group 69"
Cohesion: 1.0
Nodes (1): ASSET MANIFEST — where every image lives & is used

### Community 70 - "Module Group 70"
Cohesion: 1.0
Nodes (1): Total Recall — Demo & Winning Script

### Community 71 - "Module Group 71"
Cohesion: 1.0
Nodes (1): Total Recall — End-to-End Test & Demo Guide

### Community 72 - "Module Group 72"
Cohesion: 1.0
Nodes (1): Total Recall — End-to-End MANUAL Test Guide (real user, click-by-click)

### Community 73 - "Module Group 73"
Cohesion: 1.0
Nodes (1): IMAGE PROMPT PACK — "Neon-Noir Clinic" theme

### Community 74 - "Module Group 74"
Cohesion: 1.0
Nodes (1): Linkes

### Community 75 - "Module Group 75"
Cohesion: 1.0
Nodes (1): Phase 0 — Vertex wiring + temporal confirmed

### Community 76 - "Module Group 76"
Cohesion: 1.0
Nodes (1): Phase 1 — Self-healing engine (LangGraph) [CORE]

### Community 77 - "Module Group 77"
Cohesion: 1.0
Nodes (1): Phase 2 — Backend API + naive baseline

### Community 78 - "Module Group 78"
Cohesion: 1.0
Nodes (1): Phase 2b — `forget` (entered-in-error retraction)

### Community 79 - "Module Group 79"
Cohesion: 1.0
Nodes (1): Phase 3 — Frontend: split-chat + graph + scrubber + live heal [TIER-1 COMPLETE]

### Community 80 - "Module Group 80"
Cohesion: 1.0
Nodes (1): Phase 4 — "Why did this change?" provenance [EYE-CATCH]

### Community 81 - "Module Group 81"
Cohesion: 1.0
Nodes (1): Phase 5 — STRETCH depth (Best-Use-of-Cognee + Technical Excellence)

### Community 82 - "Module Group 82"
Cohesion: 1.0
Nodes (1): Phase 6 — Polish, hardening & deploy decision

### Community 83 - "Module Group 83"
Cohesion: 1.0
Nodes (1): Phase 7 — Submission & meta-game (wins the other half of the points)

### Community 84 - "Module Group 84"
Cohesion: 1.0
Nodes (1): SYNTHETIC DATA PLAN — testable fixtures for every feature

### Community 85 - "Module Group 85"
Cohesion: 1.0
Nodes (1): UPGRADE PLAN — Total Recall (real agent pass)

### Community 86 - "Module Group 86"
Cohesion: 1.0
Nodes (1): Cognee Visibility (Attribution) Implementation Plan

### Community 87 - "Module Group 87"
Cohesion: 1.0
Nodes (1): Family Auto-Linkage Implementation Plan

### Community 88 - "Module Group 88"
Cohesion: 1.0
Nodes (1): Graph / Memory-Map Visualization Upgrade Plan

### Community 89 - "Module Group 89"
Cohesion: 1.0
Nodes (1): Performance Optimization Implementation Plan

### Community 90 - "Module Group 90"
Cohesion: 1.0
Nodes (1): UX Perfection Pass Implementation Plan

## Knowledge Gaps
- **159 isolated node(s):** `Phase 0 acceptance test.  Proves: Cognee runs locally on Vertex AI (NO API key,`, `recall() (new API) with fallback to search() (legacy).`, `Real audit trail (CLINICAL_COPILOT_PLAN §7).  This is the one part of the iden`, `Append one audit row. Best-effort: auditing must never break the request it`, `Read the log newest-first, optionally scoped to one patient.` (+154 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Module Group 20`** (5 nodes): `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `Memory layer: canonical fact schema, authoritative ledger, and the Cognee seam.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 26`** (2 nodes): `conftest.py`, `Test isolation: point the ledger + checkpointer at dedicated SHORT-path DBs BEF`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 51`** (1 nodes): `Build a fact from a `patient_timeline_*.json` entry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 52`** (1 nodes): `Plain-English label, serialized to JSON for every fact display.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 69`** (1 nodes): `ASSET MANIFEST — where every image lives & is used`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 70`** (1 nodes): `Total Recall — Demo & Winning Script`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 71`** (1 nodes): `Total Recall — End-to-End Test & Demo Guide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 72`** (1 nodes): `Total Recall — End-to-End MANUAL Test Guide (real user, click-by-click)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 73`** (1 nodes): `IMAGE PROMPT PACK — "Neon-Noir Clinic" theme`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 74`** (1 nodes): `Linkes`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 75`** (1 nodes): `Phase 0 — Vertex wiring + temporal confirmed`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 76`** (1 nodes): `Phase 1 — Self-healing engine (LangGraph) [CORE]`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 77`** (1 nodes): `Phase 2 — Backend API + naive baseline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 78`** (1 nodes): `Phase 2b — `forget` (entered-in-error retraction)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 79`** (1 nodes): `Phase 3 — Frontend: split-chat + graph + scrubber + live heal [TIER-1 COMPLETE]`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 80`** (1 nodes): `Phase 4 — "Why did this change?" provenance [EYE-CATCH]`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 81`** (1 nodes): `Phase 5 — STRETCH depth (Best-Use-of-Cognee + Technical Excellence)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 82`** (1 nodes): `Phase 6 — Polish, hardening & deploy decision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 83`** (1 nodes): `Phase 7 — Submission & meta-game (wins the other half of the points)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 84`** (1 nodes): `SYNTHETIC DATA PLAN — testable fixtures for every feature`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 85`** (1 nodes): `UPGRADE PLAN — Total Recall (real agent pass)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 86`** (1 nodes): `Cognee Visibility (Attribution) Implementation Plan`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 87`** (1 nodes): `Family Auto-Linkage Implementation Plan`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 88`** (1 nodes): `Graph / Memory-Map Visualization Upgrade Plan`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 89`** (1 nodes): `Performance Optimization Implementation Plan`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 90`** (1 nodes): `UX Perfection Pass Implementation Plan`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `FHIR Extraction & Structured Data` to `Allergy Checks & Rules`, `Audit & Logging`, `Cognee Client & Config`, `Answer Synthesis & Citations`, `Intake Pipeline & Records`, `Allergy Check Engine`, `Family Graph & Patient Index`, `Engine Judge & Schema`, `LangGraph Engine Core`, `Chat API & UI`, `Auth & Access Control`, `App Entry & Command Palette`, `API Client & Tests`, `Clinical Check Engine`, `Force Graph Canvas`?**
  _High betweenness centrality (0.325) - this node is a cross-community bridge._
- **Why does `ClinicalFact` connect `Allergy Checks & Rules` to `Audit & Logging`, `Answer Synthesis & Citations`, `Intake Pipeline & Records`, `FHIR Extraction & Structured Data`, `Allergy Check Engine`, `Family Graph & Patient Index`, `Engine Judge & Schema`, `LangGraph Engine Core`, `App Entry & Command Palette`, `Clinical Check Engine`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Why does `all()` connect `Audit & Logging` to `Allergy Checks & Rules`, `Answer Synthesis & Citations`, `Intake Pipeline & Records`, `FHIR Extraction & Structured Data`, `Allergy Check Engine`, `Family Graph & Patient Index`, `Engine Judge & Schema`, `Clinical Check Engine`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 171 inferred relationships involving `ClinicalFact` (e.g. with `Patient-scoped agent tools (the four memory verbs).  `build_patient_tools(pati` and `Function-calling schemas the model sees. NOTE: no `patient_id` anywhere —     s`) actually correct?**
  _`ClinicalFact` has 171 INFERRED edges - model-reasoned connections that need verification._
- **Are the 113 inferred relationships involving `get()` (e.g. with `_load()` and `get_doctor()`) actually correct?**
  _`get()` has 113 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `all()` (e.g. with `recent()` and `list_threads()`) actually correct?**
  _`all()` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `Card` (e.g. with `BriefItem` and `BriefResponse`) actually correct?**
  _`Card` has 24 INFERRED edges - model-reasoned connections that need verification._