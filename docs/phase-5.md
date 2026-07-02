# Phase 5 — STRETCH depth (Best-Use-of-Cognee + Technical Excellence)

> Goal: maximize judge scores on "deep Cognee usage" and engineering. Pick by remaining
> time; each item is independently shippable and independently demoable.
>
> Inputs: Tier-1 + Phase 4 done.

## Item A — `ClinicalFact` as a Cognee **DataPoint** (typed nodes; fixes the label bug)
- **Why:** Phase 0 logged "Falling back to class name 'Timestamp' … neither metadata['index_fields'] nor name" → unlabeled nodes. A custom DataPoint with `metadata={"index_fields":[...]}` gives **typed, labeled clinical nodes** and real engineering credit.
- **How:** `app/memory/schema.py` adds a `ClinicalFactDP(DataPoint)` (from `cognee.infrastructure.engine import DataPoint`) with fields subject/predicate/value/valid_from/valid_to/source + `metadata={"index_fields":["subject","value"]}`. Ingest path uses `from cognee.tasks.storage import add_data_points` (+ a small custom pipeline or `custom_prompt` on cognify) instead of raw text `add`.
- **Acceptance:** Cognee Knowledge graph shows labeled clinical nodes (no "Timestamp" fallback warning); typed nodes visible in `/graph/cognee`.

## Item B — `memify()` "consolidation" pass (the rarest op)
- **Why:** showcases the post-processing lifecycle op almost no team uses; visible graph evolution.
- **How:** `cognee_client.consolidate()` → `await cognee.memify(...)`. Add a "🧠 Consolidate memory" button (ScenarioControls) → call → refetch `/graph/cognee`.
- **Acceptance:** after consolidation the knowledge graph visibly changes (pruned/strengthened); narrate in demo.

## Item C — Second patient (`patient_timeline_02.json`)
- **Why:** proves `node_set` scoping / multi-tenant memory; shows it's not hardcoded to one story.
- **How:** add `data/patient_timeline_02.json` (different evolving facts, e.g. dosage change + resolved condition); PatientPanel patient switcher; all queries already `node_set`-scoped.
- **Acceptance:** switch patient → independent graph + correct answers; no cross-contamination.

## Item D — Feedback weighting (optional)
- **Why:** demonstrates the FEEDBACK loop primitive.
- **How:** thumbs up/down on an answer → `cognee.search(..., SearchType.FEEDBACK, last_k=1)` after `save_interaction=True`.
- **Acceptance:** feedback recorded without errors; mention in README (don't over-invest).

## Priority order if time-limited: **A → B → C → D.** (A also fixes a real cosmetic bug, so do it first.)

## Risks
- DataPoint/custom pipeline API drift → keep raw-text `add` path as fallback; A is additive, not a rewrite.
- memify behavior varies by version → demo it on a small graph; have a fallback narration if change is subtle.

## Done → `start Phase 6`.

---

## Backend reality check (post Phase-2 / 2b)

- **`forget()` is already wired** (Phase 2b, `docs/phase-2b-forget.md`): `POST /forget`
  retracts entered-in-error facts (single-item Cognee delete + ledger `retracted` +
  restore-prior). So the `forget` lifecycle primitive is DONE — Phase 5 is now purely
  about DataPoint / memify / 2nd-patient / feedback depth.
- **Item A (DataPoint)** is still the highest-value item — it fixes the real
  "Timestamp" label-fallback warning and gives typed clinical nodes in `/graph/cognee`.
- **Item C (2nd patient) interacts with two datasets.** The naive baseline lives in a
  single frozen `naive_baseline` dataset. For a real 2nd patient, scope naive per
  patient too (e.g. `naive_baseline::P002`) or accept that the naive villain is only
  wired for P001 in the demo. Smart memory is already patient-scoped by `node_set`/
  subject in the ledger; Cognee uses one `total_recall` dataset (single-patient demo).
  Decide before investing in Item C.
- **Item B (memify):** add `cognee_client.consolidate()` → `await cognee.memify(...)`;
  surface as a "🧠 Consolidate" button. Verify the API on cognee 1.2.2 first (signature
  may differ); keep it optional.
