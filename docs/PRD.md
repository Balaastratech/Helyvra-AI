# PRD — Total Recall

> Codename: **Total Recall** (rename candidates: *Recall*, *Mnemo*, *Evergreen Memory*).
> Hackathon: **The Hangover Part AI: Where's My Context?** (WeMakeDevs × Cognee), Jun 29 – Jul 5, 2026.
> Track: **Best Use of Open Source** (self-hosted / local Cognee). Solo build.

---

## 1. One-liner

A **self-healing, time-aware memory layer** for AI agents that never confidently answers with stale facts — it detects contradictions, marks old facts *superseded* (with a timestamp) instead of silently overwriting, lets you **rewind the knowledge graph to any past date**, and can **explain why a belief changed**. Demo skin: a patient-memory companion where a stale fact (an outdated allergy or discontinued medication) is the difference between a safe and a dangerous answer.

## 2. Problem

The headline failure of long-lived AI memory is **not forgetting — it's remembering wrong**. Memory accumulates stale and contradictory facts ("patient is allergic to penicillin" + later "allergy cleared by re-test"; "on warfarin" + later "switched to apixaban"). Naive RAG retrieves *all* of it and the agent answers confidently with whichever chunk ranks highest. In healthcare that is not a UX nuisance — it is harm.

No common memory tool surfaces "this fact was superseded on date X, here's why." Vector stores have no notion of truth-over-time; most graph-memory demos only ever `add` and never `forget` or reconcile.

## 3. Why this wins (rubric mapping)

| Judging criterion | How Total Recall scores |
|---|---|
| **Potential Impact** | Stale clinical memory = patient harm. Concrete, undeniable stakes. |
| **Creativity & Innovation** | Forgetting-as-a-feature + a *time-machine* over the graph. Directly answers "Where's My Context?". |
| **Technical Excellence** | Full lifecycle (`remember/recall/improve/forget`) + `temporal_cognify` + custom `DataPoint` schema + custom contradiction pipeline. |
| **Best Use of Cognee** | Uses 5 of Cognee's 6 rarely-touched primitives (temporal, forget, improve/memify, DataPoints, provenance). Most teams only `add→cognify→search`. |
| **User Experience** | Sigma.js graph with a **date scrubber**; superseded nodes grey out live. |
| **Presentation** | A 2-min demo where the naive baseline kills the patient and Total Recall saves them. |

## 4. Target users / personas

- **Primary (demo):** a clinician/caregiver using an AI assistant over a patient's evolving record.
- **Real audience:** AI engineers building agents on Cognee + **Cognee's own engineers** (they award the interview). Provenance and temporal correctness are *their* hard problems — impress them, not just the crowd.

## 5. Scope — the ladder (build top-down; ship whatever tier you reach)

### MUST (Tier 1 — a complete winning entry on its own)
- Ingest a time-ordered stream of patient facts via Cognee (`add` with `node_set` per patient).
- On each new fact: `recall()` related claims (graph multi-hop) → **contradiction judge** (LLM) decides *supersedes / contradicts / consistent / new*.
- On supersession: mark old fact superseded (retain it, do not destroy) and `improve()` the graph so the *current* answer is correct.
- `temporal_cognify=True` so facts carry validity timing.
- **Baseline-vs-Total-Recall toggle**: same question, naive RAG answers stale, Total Recall answers correctly.
- React + Sigma.js graph view with a **date/time scrubber** that rewinds graph state.

### SHOULD (Tier 2 — the eye-catch)
- **"Why did this change?"** — click a fact → trace provenance back through the graph to the fact(s) that superseded it and the source/time. (The Black Box layer.)

### STRETCH (Tier 3 — engineering-depth credit)
- Domain-grounded extraction: custom `DataPoint` schema (`ClinicalFact`: subject, predicate, value, valid_from, valid_to, source, confidence) + a `custom_prompt`/custom Task for clinical extraction.
- `memify()`-driven nightly "consolidation" that prunes/reweights.

### Day 7
- Demo video (≤2 min), README (with explicit "How we use Cognee" section), Best-Blog post, Social-Buzz thread. Optionally 1–3 genuine Cognee PRs (PR track $100 each — **follow the issue-assignment rule, never spam**).

### Explicitly OUT of scope
- Real PHI/PII (synthetic data only). Real medical advice. Auth/multi-tenant beyond `node_set`. Cloud deploy. Mobile.

## 6. Key user stories

1. As a caregiver, when I ask "what is the patient allergic to?", the agent answers with the *current* truth and **flags** that a prior allergy was cleared on a date.
2. As a caregiver, I can **drag a time slider to last month** and see what the record looked like then.
3. As a caregiver, I can click any current fact and ask **"why did this change?"** and see the superseding event + source.
4. As a skeptic, I can flip to **"naive mode"** and watch the same question return a dangerous, outdated answer — proving the value.

## 7. Success criteria (demo-able proof)

- A scripted scenario where naive RAG returns a superseded/dangerous fact and Total Recall returns the correct current one — **side by side**.
- Time-scrubber visibly changes the rendered graph for ≥2 distinct dates.
- ≥1 "why did this change?" trace renders a correct provenance path.
- README documents `remember/recall/improve/forget`, `temporal_cognify`, `DataPoint`, and the contradiction pipeline by name.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Contradiction judge unreliable | Keep schema tight (subject+predicate dedupe first, LLM only on collisions); use a strong model *only* for the judge step. |
| Cognee API/docs lag | Pin a version; keep a thin adapter around Cognee calls so APIs can shift in one place. |
| Scope creep solo | Strict tier ladder; Tier 1 alone is submittable by day 4. |
| LLM cost | Cheap model for `cognify` bulk extraction, hard request cap; synthetic dataset is small. |
| Medical sensitivity | Prominent "demo only, not medical advice, synthetic data" banner + README disclaimer. |

## 9. Non-negotiables

- Local/self-hosted Cognee (SQLite + LanceDB + Kuzu), no cloud dependency → qualifies for **Best Use of Open Source**.
- Every Cognee primitive used must be visible/explained in the demo + README (judges scan for this).
- Synthetic data only. Disclaimer everywhere.
