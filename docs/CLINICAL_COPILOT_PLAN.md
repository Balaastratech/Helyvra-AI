# CLINICAL COPILOT — End-to-End Implementation Plan

> **The authoritative end-to-end plan.** Supersedes the scope of `UPGRADE_PLAN.md` (v1–v3) and folds
> it into the real product: a **doctor-facing clinical copilot** — dashboard → resolve patient →
> ingest records → pre-visit brief → grounded Q&A with evidence cards → clinical safety checks — with
> **Cognee as the memory + reasoning hero** across the whole flow.
>
> Hackathon: *The Hangover Part AI: Where's My Context?* (Cognee × WeMakeDevs). Track: **Best Use of
> Open Source** (self-hosted Cognee). Deadline **Jul 5**; ~5 days left (Jun 30). Solo. Build in place
> on the existing repo.
>
> **Locked decisions (from this brainstorming session):**
> - **Model:** Gemini-only — **Gemini 3 Pro** for clinical reasoning / judge / safety checks,
>   **Gemini Flash** for cheap extraction. No GPU. MedGemma deferred (documented future multimodal
>   path); BioNeMo rejected (drug-discovery tool, wrong domain).
> - **Compliance:** *simulated* thin auth/role/consent layer + a **real audit trail** on synthetic
>   data. ABDM/ABHA + HIPAA integration = documented production path, not built.
> - **Hero clinical checks (fully built):** (1) allergy-before-prescribe, (2) missed-follow-up on
>   abnormal lab, (3) combined family+lifestyle+lab risk. Others = same engine, extended later.
> - **Build target:** extend the existing repo (reuse engine, agent, intake, ledger, cognee_client).

---

## 0. What already exists and is reused (verified by reading the code)

| Already built | File(s) | Role in the copilot |
|---|---|---|
| Self-healing supersession engine | `engine/{state,nodes,judge,graph}.py` | Allergy-cleared / med-switched reconciliation — unchanged |
| Authoritative fact ledger (active/superseded/contested/retracted) | `memory/ledger.py` | Source of truth behind every answer + check |
| Cognee seam (per-patient datasets, add/cognify/search/forget/improve) | `memory/cognee_client.py` | The single place all Cognee calls live |
| ClinicalFact DataPoint | `memory/schema.py` | Base of the FHIR-aligned data model (§2) |
| Patient + document store | `memory/records.py` | Patient registry, document inbox, uploads |
| Universal intake (text/PDF/FHIR, identity match-or-create) | `intake/*` | Record ingestion (§3) |
| Tool-calling agent (closure-bound patient scope, native Gemini function-calling loop) | `agent/{tools,router}.py` | Extended into the clinical agent (§5) |
| Answer synthesis (cited, certainty-aware) | `engine/answer.py` | Becomes the structured clinical answer (§5.3) |
| Graph + time-scrubber + why-panel + naive-compare components | `frontend/src/components/*` | Reused as the Timeline / Memory-Map / Compare tabs (§6) |
| API: `/seed /ingest /reset /forget /ask /graph /why /health /chat /intake` | `app/api/*` | Extended, not replaced |

**Principle:** this plan adds *layers around* the proven engine. The self-healing core is not touched.

---

## 1. System architecture (target)

```
 Doctor (browser)
   │
   ▼
 ┌─ Identity & Access (simulated) ──────────────────────────────────────────┐
 │  login → doctor/role → patient-access list → AUDIT (real)                 │
 │  Patient Resolver: name/MRN/phone → confirmed ONE patient (no confirm =   │
 │  no clinical answer). Patient context LOCKED per chat.                     │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌─ Intake ────────────────────────────────────────────────────────────────┐
 │  upload (PDF/text/FHIR) → extract (Gemini Flash) → FHIR-aligned facts →   │
 │  doctor verifies uncertain/high-risk → store BOTH original doc + struct.  │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌─ COGNEE (the hero) ── per-patient dataset (hard isolation) ───────────────┐
 │  add(multi-format) · cognify(temporal) · ontology-grounding (ontology_    │
 │  valid flag) · memify (cross-fact risk edges) · DataPoints (FHIR types) · │
 │  node_set (by resource type) · search: GRAPH_COMPLETION / TEMPORAL /      │
 │  CYPHER / RAG(naive villain) / FEEDBACK · forget · improve · provenance   │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌─ Clinical Reasoning ──────────────────────────────────────────────────────┐
 │  Check Engine (CDS-Hooks-modeled cards): allergy · follow-up gap ·         │
 │  combined risk  →  top 3–5 cards (alert-fatigue control)                   │
 │  Agent (Gemini 3 Pro, forced grounding): recall · run_checks ·            │
 │  propose_order · ingest · propose_forget · why · timeline                  │
 │  Evidence Validator: grounded? recent? conflicting? cited? confident?      │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌─ Doctor UX ───────────────────────────────────────────────────────────────┐
 │  Dashboard → Patient resolve → Pre-visit brief → Workspace (chat + tabs +  │
 │  "doctor might miss" panel). Live trace, citation chips, certainty,        │
 │  approval cards, honest errors, progressive disclosure.                    │
 └───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Clinical data model — FHIR-aligned Cognee DataPoints (`memory/schema.py`)

Today's `ClinicalFact` (subject/predicate/value/dates/source/status) stays the engine's internal
unit. We add a **`resource_type`** discriminator + typed subclasses mapped to FHIR resources, each a
Cognee DataPoint with `metadata.index_fields` so it lands in both the graph and the vector layer:

| Our type | FHIR resource | Key fields | Drives |
|---|---|---|---|
| `Allergy` | AllergyIntolerance | substance, drug_class, reaction, severity, onset, status | allergy check |
| `Condition` | Condition | name, onset, status (active/resolved), monitoring_rules | risk + monitoring |
| `Medication` | MedicationStatement | drug, drug_class, dose, start, stop, status | conflict + allergy |
| `LabResult` | Observation | analyte, value, unit, ref_range, abnormal_flag, date | trend + follow-up gap |
| `Vital` | Observation | type, value, date | trend |
| `FamilyHistory` | FamilyMemberHistory | relation, condition, age_at_onset | hereditary risk |
| `Lifestyle` | Observation (social) | factor (smoking/alcohol/diet), value | combined risk |
| `Procedure` | Procedure | name, date | timeline |
| `Immunization` | Immunization | vaccine, date, due | preventive gap (deferred) |
| `SourceDoc` | DocumentReference | doc_id, page, date, original blob | evidence/citation |

Every fact keeps `source_document`, `page`, `date`, `confidence`, `ontology_valid` (from Cognee
grounding), and the existing `status` lifecycle. **Both** the original document (legal/evidence view)
and the structured extraction are stored — never summaries alone.
`// ponytail: add resource_type + typed fields to the existing ClinicalFact rather than a parallel
class hierarchy — the engine already flows ClinicalFact end-to-end; one discriminated model keeps the
judge/ledger/checkpointer untouched. Split into real subclasses only if field divergence demands it.`

---

## 3. Intake — record → structured profile (extends `intake/*`, already built)

Pipeline (mostly exists; additions marked **NEW**):
1. Upload PDF / text / FHIR JSON (Cognee ingests 38+ formats natively; PDFs handled).
2. Extract entities (Gemini Flash, structured output) → **NEW:** tag `resource_type` + FHIR fields;
   mark low-confidence items (`confidence < threshold`) as **needs-verification**.
3. **NEW — doctor verification gate:** uncertain or high-risk extractions (e.g. a possible allergy)
   surface as a "confirm this?" card before they become active facts. Verified → active; rejected →
   discarded with audit.
4. Identity resolve (match-or-create patient — exists).
5. Store original `SourceDoc` + structured facts; link facts → doc + page.
6. Facts flow through the existing engine (recall → judge → reconcile → persist) → self-healing +
   per-patient Cognee dataset.

---

## 4. Cognee — used at its full surface (the rubric-winning core)

Mapped primitive → feature. README's "How we use Cognee" section is built from this table.

| Cognee primitive | Where used | Rare? |
|---|---|---|
| `add` (multi-format, per-patient dataset) | every record ingested, isolated per patient | common |
| `cognify(temporal_cognify=True)` | time-aware graph; powers supersession + trends | uncommon |
| **Ontology grounding (OWL/RDF, `ontology_valid`)** | **NEW** — supply a small medical ontology (drug→class, beta-lactam cross-reactivity, condition→monitoring, family→risk). Cognee validates extracted entities against it and flags grounded vs hallucinated → this *is* the Evidence Validator | **rare** |
| **`memify`** | **NEW** — enrichment pass that creates cross-fact **risk edges** (family early-MI + smoking + high LDL → `CardiovascularRisk` node). Powers combined-risk reasoning | **rare** |
| Custom `DataPoint` (FHIR types, `index_fields`) | the §2 data model | rare |
| `search` GRAPH_COMPLETION | graph-reasoned Q&A | common |
| `search` TEMPORAL | supersession + lab trends + "as of date" | uncommon |
| `search` CYPHER | **NEW** — deterministic clinical checks ("abnormal labs with no follow-up after date") | rare |
| `search` RAG_COMPLETION | the **naive villain** (frozen pre-heal dataset) for the Compare tab | common |
| `search` FEEDBACK | **stretch** — reinforce answers the doctor accepted | rare |
| `forget` | retract entered-in-error facts | uncommon |
| `improve` | post-supersession graph repair | uncommon |
| Per-patient datasets (isolation) | the safety boundary — one patient = one dataset | core |
| `node_set` (by resource_type/encounter) | sub-scoping within a patient | uncommon |
| provenance / `visualize_graph` | "why did this change" + graph view | uncommon |

**~12 surfaces, 5 of them rare.** ACL/`create_authorized_dataset` stays deferred (see UPGRADE_PLAN §0
deviation — flipping it mid-build breaks the name-based flow; closure-bound scoping + per-patient
datasets already give isolation).

---

## 5. The clinical agent (extends `agent/*`)

### 5.1 Tools (closure-bound to the resolved patient)

| Tool | Wraps | New? |
|---|---|---|
| `recall_patient_facts(query)` | `engine/answer` synthesis (cited, certainty-aware) | exists |
| `run_clinical_checks(context)` | §5.2 check engine (patient-view) | **NEW** |
| `propose_order(drug)` | runs prescribe-time checks (allergy/interaction) **before** any write, returns cards | **NEW** |
| `get_timeline()` | ordered events for the Timeline tab | **NEW (thin)** |
| `ingest_fact(text)` | extract → engine | exists |
| `propose_forget(fact_id, reason)` | staged delete → `/chat/approve` | exists |
| `why_changed(subject)` | provenance trace | exists |

**Hard rules (enforced, tested):** patient scope is the closure (model never sees `patient_id` → no
cross-patient leak); **forced grounding** — never answer a clinical question from parametric knowledge,
always via a tool; **no confirmed patient → no clinical answer**.

### 5.2 Clinical check engine (`checks/`) — CDS-Hooks-modeled

Each check is a module with one interface `def run(patient_id) -> list[Card]`, so "the rest are the
same engine extended" is literally true. `Card = {summary, indicator: info|warning|critical, detail,
sources: [Citation], suggestions: [str]}` (the CDS-Hooks card shape). Engine returns **top 3–5 by
severity** (alert-fatigue control).

1. **`allergy_check`** — for a proposed/recorded drug → resolve drug→class via the **ontology** →
   match against active `Allergy` facts incl. **cross-reactivity** (penicillin → all beta-lactams) →
   `critical` card citing the source discharge summary + page.
2. **`followup_gap_check`** — find abnormal `LabResult` facts (outside ref_range) with **no**
   subsequent note/order/referral after their date (Cognee CYPHER + ledger temporal) → `warning` card.
3. **`combined_risk_check`** — read the **memify-built** risk edges: first-degree relative early
   disease + ≥1 patient risk factor (smoking / high LDL / rising HbA1c / high BMI) → `warning` card
   that names *each contributing fact with its citation* (the relationship-graph hero — reasons across
   facts, not one isolated fact).

Triggered on **patient-open** (→ pre-visit brief) and on **`propose_order`** (→ prescribe check).

### 5.3 Answer contract (the doctor-facing shape the user specified)

Every clinical answer returns, and the UI renders, exactly:
**Answer · Reason · Evidence (source + date + page) · Confidence · What's missing · Suggested doctor
action.** Never a diagnosis beyond evidence; never treatment without "for your review". Contested or
low-confidence facts are flagged, not smoothed over (the project's whole thesis applied to our own
voice).

### 5.4 Safety / evidence validator

Before an answer leaves the agent: grounded in *this* patient's records? recent? conflicting
evidence? cited? confidence stated? not exceeding evidence? Weak evidence → "I found a possible
mention but it's unclear — please verify," never a confident claim.

---

## 6. Doctor UX (extends `frontend/*`; reuses existing graph/scrubber/why)

**Dashboard (landing — NOT chat):** today's patients, search (name/MRN/phone), recent, a
cross-patient **critical reminders** strip, upload, "ask across patients" (stretch).

**Patient resolve:** typing a name with duplicates → disambiguation list (name/age/last-visit) →
select → **patient context chip** (name · age · sex · MRN · allergy badge · risk badge) locks. Switch
patient → prior context explicitly closed ("You are now viewing … Previous context closed").

**Pre-visit brief (on patient open, before chat):** one-screen summary (conditions / meds / allergies
/ family / recent concern / lifestyle) + **"Top 3 things not to miss"** cards from the check engine.

**Workspace:** left sidebar (search / today / recent / new chat); top bar (context chip + badges);
main (chat + tabs **Timeline / Records / Labs / Meds / Family / Alerts** — Timeline & graph reuse
existing `MemoryGraph`+`RewindSlider`+`WhyPanel`); right panel (Doctor-might-miss / Missing-data /
Follow-up tasks / Evidence sources).

**Chat behavior:** live tool-call trace inline; **citation chips** on every claim → open `SourceDoc`
at the page; **certainty** rendering (contested shown as conflict, never one confident line);
**approval cards** for orders + forgets (collaborative correction framing); honest error/degraded
notices; progressive disclosure (calm default, "Raw" toggle for tool/args/dataset).

**Compare tab:** the existing naive-vs-healed split — the money shot — kept for the rubric, off the
landing page.

---

## 7. Identity, access, audit (simulated thin layer — `auth/`, `audit.py`)

- **Login (mock):** pick a doctor; session carries doctor + role (doctor/nurse/admin).
- **Access list:** `data/access.json` maps doctor → allowed patient_ids; resolver/agent refuse
  out-of-scope patients.
- **Audit (REAL):** append-only SQLite log of `(doctor, ts, patient, action, decision, evidence_ids)`
  for every recall / order / ingest / forget / approval — this is genuine, not mocked, and is part of
  the "real doctor system" credibility.
- **Doctor decision capture:** accept / ignore / edit / add-note on each card → stored + audited.
- Banner everywhere: "Demo only · synthetic data · not medical advice."
- ABDM/ABHA consent + HIPAA technical safeguards = documented production path in README.

---

## 8. Robustness (from UPGRADE_PLAN §7.5 — carried forward)

Idempotency keys on write tools; durable per-turn checkpoint (reuse engine `SqliteSaver`); one
structured persisted trace `{seq,tool,args,result_summary,ms}` serving both observability and the live
UI trace; graceful in-context error recovery ("stored, but search may lag a moment").

---

## 9. Day-by-day (5 days, heavy reuse)

- **Day 1 — Data + ontology foundation.** Extend `ClinicalFact` to FHIR-aligned `resource_type` + typed
  fields (§2). Author the small **medical ontology** (drug→class, beta-lactam cross-reactivity,
  condition→monitoring, family→risk) and wire **ontology grounding** in `cognee_client`. Build the hero
  synthetic patient (**Rahul Sharma, 52M**: penicillin allergy w/ reaction; HbA1c trend; creatinine
  trend no-follow-up; father MI<50; smoker; LDL 165) + keep P001–P003. *Verify:* facts ingest with
  `resource_type` + `ontology_valid`; graph shows typed nodes.
- **Day 2 — Clinical brain.** `checks/` engine + 3 hero checks (§5.2) + CDS-Hooks card shape +
  **memify** risk-edge pass. *Verify:* opening Rahul yields exactly the 3 expected cards, each cited;
  proposing amoxicillin yields the critical allergy card via ontology cross-reactivity.
- **Day 3 — Agent + access.** Extend agent tools (`run_clinical_checks`, `propose_order`, `get_timeline`),
  enforce forced-grounding + structured Answer/Reason/Evidence/Confidence/Missing/Action (§5.3),
  evidence validator (§5.4); simulated auth + **real audit** + patient resolver/lock (§7). *Verify:*
  cross-patient leakage test passes; "can I prescribe amoxicillin?" returns the full structured answer;
  every action audited.
- **Day 4 — Doctor UX.** Dashboard, patient resolve + context chip, **pre-visit brief**, workspace
  tabs (reusing graph/scrubber/why), doctor-might-miss panel, citation chips, approval cards, honest
  errors. *Verify in browser:* login → dashboard → resolve Rahul → brief with Top-3 → ask → cards +
  citations → upload a superseding lab → live self-heal → Compare tab money shot.
- **Day 5 — Win the meta-game.** Demo video (≤2 min, §10), README "How we use Cognee" (§4 table, ~12
  primitives) + AI-assistant disclosure + disclaimer + ABDM/HIPAA-as-future-work. Buffer. *Optional:*
  spin up MedGemma 4B for a 1–2 hr "reads a scanned lab image" cameo, then undeploy (~$30–40 credits).

**Cut order if a day slips (never cut Day 1–2):** drop FEEDBACK reinforcement → drop the cross-patient
"ask across patients" → drop the Records/Labs/Meds sub-tabs (keep Timeline + Alerts) → MedGemma cameo
first to go.

---

## 10. Demo script (the 2-minute story)

1. Login → dashboard: today's patients + a red **critical reminders** strip.
2. Open "Rahul Sharma" → 2 matches → select → context chip locks (allergy badge red).
3. **Pre-visit brief** auto-renders: summary + **Top 3 not-to-miss** (penicillin allergy / creatinine
   1.0→1.6 no nephrology note / father MI<50 + smoking + LDL 165 → CV review).
4. "Can I prescribe amoxicillin?" → agent runs the prescribe check → **critical** card: *penicillin
   allergy, breathing difficulty, 2021 discharge summary p.2* + structured Answer/Reason/Evidence/
   Confidence/Missing/Action.
5. "Why is CV risk flagged?" → memify relationship graph → father MI + smoking + LDL 165, each a
   clickable citation.
6. Upload a new lab PDF that **clears** an old fact → intake → self-heal → the card updates live;
   scrub the timeline / "why did this change" → temporal + provenance.
7. **Compare tab:** naive RAG → "yes, amoxicillin is fine" (dangerous) vs Total Recall → "no —
   penicillin allergy." The money shot.
8. Close naming each Cognee primitive (§4).

---

## 11. Explicitly deferred (documented as production path, not faked)

Real ABDM/ABHA consent + HIPAA technical safeguards; OCR for scanned/handwritten docs; MedGemma
multimodal image reading (cameo only); the remaining ~8 clinical checks (drug-drug interaction,
disease contraindication, preventive-care gaps, immunization, red-flag symptoms, care-continuity,
timeline-conflict — all the *same* `checks/` interface); multi-clinician ACL via
`create_authorized_dataset`; cross-patient cohort queries ("all diabetics HbA1c>8 no follow-up");
fuzzy patient matching; wearable data.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Ontology grounding API unfamiliar / behaves unexpectedly | Spike it Day-1 morning behind the `cognee_client` seam; fallback = our own drug-class lookup table feeding the same check (cards don't depend on Cognee's flag to render) |
| memify output shape uncertain | Day-2 spike; fallback = compute risk edges ourselves from the ledger and write them as facts — the card logic is the same either way |
| Scope (production EHR in 5 days) | Strict vertical slice; §11 deferred list is firm; cut order in §9 |
| Alert fatigue / wrong cards | Top-3-by-severity cap; every card cited; doctor can dismiss + audited |
| Confident-wrong answer in our own voice | Evidence validator (§5.4) + certainty rendering — the thesis applied to ourselves; unit-tested |
| Cross-patient data leak | Closure-bound scope + per-patient datasets + explicit leakage test |
| Cost | Gemini-only, no GPU; Flash for bulk, Pro only for reasoning/judge; spend log + hard cap |

## References

(Carried from UPGRADE_PLAN + this session's research.)
- [Cognee core concepts / ontology grounding](https://www.cognee.ai/blog/deep-dives/ontology-ai-memory) ·
  [memify pipeline](https://medium.com/@cognee/cognee-knowledge-graph-optimization-memify-post-processing-pipeline-ce049417d9c3) ·
  [permissions/datasets](https://docs.cognee.ai/core-concepts/multi-user-mode/permissions-system/datasets) ·
  [search basics](https://docs.cognee.ai/guides/search-basics) ·
  [cognee/skill.md](https://github.com/topoteretes/cognee/blob/main/cognee/skill.md)
- [CDS Hooks practical guide](https://medblocks.com/blog/hl7-cds-hooks-a-practical-guide) ·
  [drug-allergy CDS service study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9693697/)
- [Gemini 3 in healthcare](https://intuitionlabs.ai/articles/gemini-3-healthcare-applications) ·
  [Capabilities of Gemini in medicine](https://arxiv.org/html/2404.18416v2)
- [MedGemma on Vertex (deferred path)](https://developers.google.com/health-ai-developer-foundations/medgemma/get-started) ·
  [Vertex L4 GPU pricing](https://cloud.google.com/vertex-ai/pricing)
- [Clinical copilot UX study](https://arxiv.org/pdf/2602.00726) ·
  [Manthan — winning-bar audit](https://github.com/akash-mondal/manthan)
- [FHIR resources (AllergyIntolerance, Condition, Observation, FamilyMemberHistory, …)](https://www.hl7.org/fhir/)
