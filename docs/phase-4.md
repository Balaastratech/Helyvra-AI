# Phase 4 — "Why did this change?" provenance [EYE-CATCH]

> Goal: clicking a corrected fact explains *why* — the superseding event, source, date,
> reason, and (stretch) a cross-confirmation from Cognee's own graph reasoning.
>
> Inputs: Phases 1–3 done; `/why` already returns the basic chain; WhyDrawer exists.

## A. What this phase adds (beyond Phase 2's basic /why)
1. **Full supersession chain** (multi-hop): if a fact was superseded, then that superseder later superseded too, render the whole chain newest→oldest.
2. **Cross-confirmation (the wow):** call Cognee `GRAPH_COMPLETION` with a targeted question ("Why is patient P001 no longer allergic to penicillin? Cite the event.") and show its natural-language answer next to the ledger trace — two independent sources agreeing. Proves it's real reasoning, not a hardcoded label.
3. **Answer provenance (stretch):** for a `/ask` total_recall answer, surface which facts informed it (the active facts for that subject) as clickable chips.

## B. Files touched
| File | Change |
|---|---|
| `app/memory/ledger.py` | `chain(fact_id)` → returns ordered list (already partly there; ensure multi-hop) |
| `app/api/routes_graph.py` | `/why` enriched: add `graph_explanation` (Cognee GRAPH_COMPLETION) + `chain[]` |
| `app/api/dto.py` | extend `WhyResponse` |
| `frontend/.../WhyDrawer.tsx` | render chain timeline + "Cognee agrees:" block + source badges |
| `frontend/.../ChatPane.tsx` | (stretch) render provenance chips under total_recall answers |

## C. `/why` enriched contract
Req: `GET /why?fact_id=...&patient_id=P001`
Res:
```
{ "fact": ClinicalFact,
  "chain": [ {fact, reason, source, date} ...newest→oldest ],
  "current_truth": ClinicalFact|null,           // the active fact for this subject now
  "graph_explanation": "Penicillin allergy was cleared on 2026-03-02 after a negative re-test by Dr. Lee.",  // Cognee GRAPH_COMPLETION
  "sources": ["Dr. Lee","Dr. Adams"] }
```

## D. Steps
1. Ledger: confirm `chain()` walks `superseded_by` until null; include reasons/sources/dates.
2. `/why`: after building chain, call `cognee_client.recall(targeted_why_question, type=GRAPH_COMPLETION, node_set=[patient])`; attach `.text` as `graph_explanation`. Wrap in try/except (don't fail the trace if the LLM call hiccups).
3. WhyDrawer: vertical timeline (superseded → current), each step shows date · source · reason; a callout "🧠 Cognee's own reasoning:" with `graph_explanation`.
4. (Stretch) provenance chips in ChatPane.

## E. Acceptance (done-when)
- Click superseded penicillin-allergy node → drawer shows: superseded 2026-03-02 · Dr. Lee · "negative re-test", current truth = "not allergic", AND a Cognee GRAPH_COMPLETION sentence that agrees.
- Multi-hop chain renders correctly if a 2-step supersession exists (add one to timeline_01 if needed for the demo).
- `/why` degrades gracefully if the graph explanation call fails (still returns ledger chain).

## F. Risks
- GRAPH_COMPLETION phrasing varies → keep the targeted question tight; it's supplementary, ledger is source of truth.
- Latency (extra LLM call) → only on drawer open, with a spinner; cache per fact_id.

## Done → `start Phase 5`.

---

## G. Backend reality check (post Phase-2 / 2b)

- **`/why` already returns** `fact`, `superseded_by`, `reason`, `source`, `date`,
  `chain[]` (Phase 2, tested). This phase ADDS `current_truth` + `graph_explanation`
  (+ optional `sources`). Extend `WhyResponse` in `dto.py` accordingly.
- **Cross-confirmation: use `TEMPORAL`, not `GRAPH_COMPLETION`.** GRAPH_COMPLETION
  returned garbage ("Got it.") for yes/no questions in Phase 2; TEMPORAL reliably
  answers "…cleared on 2026-03-02…". So step B2's targeted question should call
  `cognee_client.recall_answer(targeted_q, query_type=SearchType.TEMPORAL,
  node_set=[patient])` and attach `.text` as `graph_explanation`. Keep the
  try/except — it's supplementary; the ledger chain is the source of truth.
- **`date` field gotcha:** in `dto.py`, a field literally named `date` must be typed
  `Optional[datetime.date]` (a bare `date` annotation collides with the field name
  and Pydantic forces it to `None`). Already fixed for `WhyResponse`; keep it when
  extending.
- **Multi-hop chain** already works in `ledger.chain()`. The demo timeline has
  single-hop supersessions; add a 2-step one to `patient_timeline_01.json` only if
  you want to show multi-hop (optional).
