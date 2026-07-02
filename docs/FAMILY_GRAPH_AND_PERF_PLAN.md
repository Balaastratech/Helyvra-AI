# FAMILY GRAPH + PERFORMANCE — design (Cognee-native, local)

> Two additions raised in review: (1) a **cross-patient family / inheritance graph** (relatives'
> real records connect and drive hereditary risk), and (2) **speed** — the system is slow; make it
> fast without losing precision. Both are answered from Cognee's actual docs (researched, local
> self-hosted only — no cloud). Companion to `CLINICAL_COPILOT_PLAN.md`.

---

## PART A — Cross-patient family graph

### A.1 Where we are (confirmed correct)
Today: **strict per-patient isolation** — each chart is its own Cognee dataset `tr_<patient_id>`,
tools are closure-bound to one patient. "Father had MI at 49" is a **self-reported FamilyHistory
fact on the son's own chart**, extracted from a document filed under the son. There is **no link**
to the father's actual chart even if he is also a patient. The combined-risk check reasons over the
son's *own* facts only. That isolation is deliberate (the demo's safety thesis: one patient's data
never leaks into another's answer).

### A.2 The tension, and the resolution
A family graph is the *opposite* pressure (charts must connect). Resolve it with **two layers**:

- **Clinical layer (unchanged):** per-patient datasets stay isolated. No clinical detail crosses a
  chart boundary. Safety thesis intact.
- **Family layer (new, consent-gated):** a *separate* graph holding only `Patient` nodes + kinship
  edges + which of their conditions are **heritable** — and only for patients with an explicit
  `family_consent` link. Cross-chart reasoning happens **only** through this consented layer.

### A.2.5 Automatic family linkage — the system finds families itself (no manual work)

**Requirement:** the doctor never "puts the family in a folder" or types relation numbers. A patient's
records are ingested normally; the system **resolves family relationships automatically**, accurately,
with no duplicate/false-merge confusion. This is the well-studied **record-linkage / EMPI** problem;
here are the real options and the recommended one (researched, not assumed).

**Signals available from normal ingestion (ranked by precision):**
1. **Explicit relative named in a record + identity match** — a FamilyHistory / intake note names a
   relative *with identifiers* ("father: Rahul Sr., DOB 1948-… / MRN-2010"). Match against the patient
   index → link + the relation is stated, not guessed. **Highest precision.**
2. **Reciprocal next-of-kin / emergency contact** — patient A lists B ("father, emergency contact") and
   B is a patient → strong link + relation.
3. **Shared household identifiers** — same address + phone + surname → candidate family. Good recall,
   lower precision (roommates/coincidence).
4. **Probabilistic weighting (Fellegi–Sunter / EMPI)** — a score over partial matches of
   name/DOB/address/phone/surname; the standard EHR approach for messy data.

**Options:**

| Option | What it links on | Precision / recall | Verdict |
|---|---|---|---|
| **A. Deterministic explicit** | signals 1–2 only (relative named + resolves by MRN or name+DOB) | very high precision, lower recall | **Recommended core** — near-zero false merges; links exactly the relatives actually mentioned (the son's chart names the father — that's our case) |
| **B. Probabilistic household/EMPI** | signals 3–4 with weighted scoring | higher recall, real false-positive risk | powerful but needs a human-review tier; more work/risk |
| **C. Hybrid tiered (EMPI-standard)** | A auto-links; B *proposes* for confirmation; else ignore | tunable, safest | **Best overall shape** — this is how real EMPIs balance false-positive vs recall (uncertain → review) |

**Recommendation: Option C in shape, Option A fully built now.** Auto-link on explicit + strong
identity (Tier 1); surface household/probabilistic candidates as **proposed** links a doctor confirms
(Tier 2, never silent); ignore the rest. Research reality: even the best EMPI isn't 100% (real-world
duplicate rates ~18%), so *tiering + confirm-on-weak-match is the correct design, not a shortcut*.
[EMPI/record-linkage](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10365597/) ·
[household linkage from routine health data](https://pmc.ncbi.nlm.nih.gov/articles/PMC11659028/)

**No duplicates / no confusion:** identity is a **deterministic key** — MRN if present, else normalized
`name+DOB` → a UUID5 (Cognee `Dedup()`, §A.3). The same real person is always one node, whether they
appear as a patient or as someone's named relative. Weak matches never auto-merge (they wait for
confirmation), so a wrong link can't silently corrupt a chart.

**How it plugs in (all automatic, on normal ingest):**
1. Extend `engine/extract.py` to capture *relative identifiers* on FamilyHistory mentions —
   `{relation, name, dob?, mrn?}` (structured FHIR `FamilyMemberHistory` already carries name+relation;
   free-text via the existing Gemini extractor).
2. New `intake/family_resolver.py` — mirrors the existing `intake/patient_index.resolve` (MRN >
   name+DOB): for each extracted relative, resolve to an existing patient. Strong match → write a
   `related_to` edge (relation + confidence + consent state) to the family graph (§A.3) and a
   `data/family_links.json` mirror; weak match → a *proposed* link.
3. `checks/hereditary.py` then traverses the linked graph (§A.4).

So: patient data is ingested as usual → the resolver notices "the father named here **is** patient
P010" → the link is created automatically, accurately, deduplicated — no folders, no numbers, no human
data entry. Exactly the behavior you asked for.

### A.3 Cognee is built for this (the actual mechanism — researched)
Cognee turns **typed DataPoint fields into graph edges automatically**, and `Dedup()` makes the
same real person a **single shared node** across records. That is exactly a family graph:

```python
from typing import Annotated
from cognee.infrastructure.engine import DataPoint, Embeddable, Dedup

class FamilyMember(DataPoint):
    mrn: Annotated[str, Dedup()]          # identity key → same person = one node across charts
    name: Annotated[str, Embeddable()]
    is_patient: bool                       # do we also hold a full chart for them?
    parent: "FamilyMember | None" = None   # typed ref → edge: child --parent--> parent
    heritable_conditions: list[str] = []   # e.g. ["early_CAD", "BRCA", "type_2_diabetes"]
    family_consent: bool = False           # gate: cross-chart reasoning allowed only if True

# Father is BOTH a relative on the son's chart AND his own patient — one node via Dedup(mrn):
father = FamilyMember(mrn="MRN-2010", name="Rahul Sr.", is_patient=True,
                      heritable_conditions=["early_CAD"], family_consent=True)
son    = FamilyMember(mrn="MRN-3010", name="Rahul Jr.", is_patient=True,
                      parent=father, family_consent=True)
await add_data_points([father, son])       # edges: son --parent--> father (single father node)
```
Because `Dedup(mrn)` yields a deterministic UUID5, the father referenced from the son's chart and
the father's own `Patient` node are **the same graph node** — the charts connect *through the
father entity*, without merging the isolated clinical datasets. This is a rare, high-credibility
Cognee usage (custom DataPoint relationship edges + entity dedup + graph traversal) — a strong
"Best Use of Cognee" signal.

### A.4 Hereditary reasoning (the new check)
`hereditary_risk_check(patient)`:
1. Traverse the family graph from the patient over `parent`/`child`/`sibling` edges (Cognee
   GRAPH_COMPLETION or CYPHER over the family dataset).
2. For each **first-degree relative who is also a consented patient**, read their *actual* heritable
   diagnoses (not just the self-reported snapshot).
3. Apply ontology inheritance rules (`data/ontology`): early CAD in a parent → CV screening flag;
   BRCA-pattern breast/ovarian → genetic-counsel flag; T2D in a parent + patient risk factors →
   monitoring flag.
4. Emit a `Card` — but **consent-gated surfacing**: if the relative consented, cite their real
   record ("your father was diagnosed with early CAD on <date>"); if not, degrade to
   "a consented first-degree relative has a heritable cardiac condition" (no identifying detail).

This *upgrades* the existing `combined_risk_check` from "the son's self-reported family history" to
"the father's **actual, live** diagnosis propagated to the son" — genuinely better medicine and a
visibly graph-powered story.

### A.5 Scope (committed build — automatic, not manual)
Build the **automatic linker end-to-end** (the point is zero human data-entry):
- **Tier-1 deterministic auto-linking** (§A.2.5 Option A): relative extraction + `family_resolver` +
  Cognee `Dedup()` shared nodes + `related_to` edges — runs on normal ingest, no folders/numbers.
- **`hereditary_risk_check`** (§A.4) traversing the linked graph, consent-gated surfacing.
- **Consent gate** visible (toggle off → card degrades to non-identifying).
- **Tier-2 proposed links** (household/probabilistic) surfaced as *suggestions to confirm* — the UI +
  a confidence score; auto-apply stays Tier-1 only.
- A demo family in the data (father `P010` + a new son patient) so the "system linked them itself"
  moment is real, plus the contrast: son's *self-reported* "father had MI" vs the **live-linked**
  father's actual diagnosis.

Defer (documented): multi-generation traversal, siblings/aunts beyond first-degree, pharmacogenomic
propagation, auto re-propagation of risk when a relative gets a *new* diagnosis later.

### A.6 What it touches
`memory/schema.py` (FamilyMember DataPoint), `memory/cognee_client.py` (a `family_<id>` dataset +
`add_data_points`), `checks/hereditary.py` (new), `data/` (a consented family + `family_links.json`),
UI (a consent chip + the degraded-vs-cited card). Isolation default preserved; family linkage is
explicit, consented opt-in.

---

## PART B — Performance (fast without losing precision)

### B.1 Why it's slow (root cause, from Cognee docs)
`cognify` runs a **6-step pipeline** with **2 LLM calls per chunk** (graph-extract + summarize),
plus embeddings. Today the engine calls `add + cognify(temporal=True)` **per fact ingest** and
`improve()` after every heal — **synchronously, blocking the request**. Temporal mode also drops
`chunks_per_batch` to 10 (slower). So every ingest pays a full multi-call pipeline while the user
waits. [Cognify docs](https://docs.cognee.ai/core-concepts/main-operations/legacy-operations/cognify)

### B.2 The key insight that makes speed *free* of precision
**The ledger is the authoritative store; Cognee is the semantic/graph layer.** Clinical answers are
synthesized from the deterministic ledger (§CLINICAL_COPILOT §5.3). So we can make Cognee cheaper
and asynchronous **without changing a single answer's correctness** — Cognee affects *graph/search
richness*, not the source of truth.

### B.3 Levers (all local, all precision-safe), in impact order
1. **Background the cognify.** Return the chat/ingest answer from the ledger immediately; run
   `add/cognify` in a FastAPI background task. Biggest *perceived* speedup — the doctor never waits
   on the pipeline. (Graph/Memory-Map catches up a beat later; acceptable.)
2. **Skip the `summarize_text` task** via a custom pipeline → **2 LLM calls/chunk → 1** (halves
   cognify LLM time). We never use Cognee summaries (we synthesize from the ledger). Pure win.
   [docs: custom pipeline omitting summarize_text]
3. **Batch, don't per-fact cognify.** Add all facts of an ingest/seed, then cognify **once** — not
   once per fact. Tune `data_per_batch`/`chunks_per_batch`.
4. **Bigger `chunk_size`.** Clinical facts are tiny; one fact = one chunk = minimal calls
   (`cognify(chunk_size=4096)`).
5. **Temporal only where it matters.** `temporal_cognify=True` (slow, `chunks_per_batch=10`) only on
   the supersession-demo patient (P001); other patients use plain cognify. Temporal correctness for
   the demo is unaffected (only P001 needs the time-scrubber).
6. **Precompute the demo graph.** Cognify all seed patients **once at startup / checked-in state**,
   so the live demo only cognifies the 1–2 held-back corrections. Kills cold-start lag.
7. **Batch local embeddings** (fastembed CPU is a likely bottleneck); keep incremental loading on
   (`pipeline_status` skips already-processed) so nothing re-embeds. Optionally a smaller local embed
   model — still local, precise enough for these small graphs.
8. **`improve()` sparingly** — only after an actual supersession, not every ingest (already partly
   true; enforce).

### B.4 Expected effect
Perceived latency drops from "wait through a multi-call pipeline per message" to "instant ledger
answer + background graph update." Cognify itself ~halves (skip summaries) and runs far less often
(batch + precompute). No answer changes — the ledger is untouched.

### B.5 What it touches
`memory/cognee_client.py` (custom pipeline w/o summarize, chunk_size, batch params, temporal only
where needed), `engine/nodes.persist` (background task + batch + improve-only-on-heal),
`app/main.py` (startup precompute of seed patients).

---

## Sequencing (remaining days, ~Jul 1 → Jul 5)
1. **Perf first (½ day, highest leverage):** B.1–B.6 — makes *everything* demoable and every later
   step faster to iterate. Do before more feature work.
2. **Data fixes (from the review):** regenerate the leaky 2021 PDF, add a contested fixture, wire the
   `documents.json`→backend format.
3. **Core copilot** (CLINICAL_COPILOT_PLAN Days 1–4).
4. **Family graph — committed build (A.5)** as the headline Cognee differentiator: automatic Tier-1
   linking + hereditary check + consent gate. Sequenced after perf + data + core-verify so it builds on
   a working base, but it *is* being built (per decision), not left as bonus. Multi-gen/probabilistic
   auto-apply remain deferred.

## Risks
| Risk | Mitigation |
|---|---|
| Custom pipeline (skip-summarize) API differs in 1.2.2 | Behind `cognee_client` seam; fallback = keep summaries but background + batch (still big win) |
| Background cognify races the graph view | Graph reads tolerate "catching up"; ledger drives answers, so never wrong, just briefly stale |
| `Dedup()`/relationship-edge API differs in installed version | Spike A.3 in 30 min; fallback = model kinship edges ourselves in the ledger + a small family table, traverse in Python |
| Family graph endangers isolation | Consent gate is mandatory; no clinical detail crosses without a `family_consent` edge; default stays isolated |
| Time | Perf + data + core are the must; family graph is explicitly the first thing to cut |

## References
- [Cognify pipeline & perf levers](https://docs.cognee.ai/core-concepts/main-operations/legacy-operations/cognify)
- [DataPoints — relationships, Dedup, edges](https://docs.cognee.ai/core-concepts/building-blocks/datapoints)
- [Cognee custom graph models (deep dive)](https://www.cognee.ai/blog/deep-dives/expanding-custom-graph-models-for-reliable-agent-memory-and-retrieval)
- [Cognee docs home](https://docs.cognee.ai/)
