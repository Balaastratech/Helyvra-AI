# Phase 2b — `forget` (entered-in-error retraction)

> Goal: wire Cognee's `forget()` MUST primitive into a real, demoable flow. This is
> the ONE legitimate use of forget in Total Recall — retracting a fact that was
> **entered in error** (wrong patient, typo, mis-keyed lab). It is NOT supersession
> (supersession retains history; see ARCHITECTURE.md "never hard-delete on
> supersession" and `engine/nodes.py::persist`).
>
> Status: DONE (2026-06-29). Implemented + `test_forget_retracts_and_removes` green (real Cognee deletion summary). Inputs: Phase 2 API working.

---

## A. How Cognee `forget()` actually works (verified, cognee 1.2.2)

Signature (from `cognee/api/v1/forget/forget.py`):

```python
async def forget(
    data_id: Optional[UUID] = None,
    dataset: Optional[str] = None,
    dataset_id: Optional[UUID] = None,
    everything: bool = False,
    memory_only: bool = False,
    user: Any = None,
) -> dict   # deletion summary: items removed, datasets removed
```

Modes (one mental model that replaces the old prune/delete/empty_dataset APIs):

| Call | Effect |
|---|---|
| `forget(data_id=ID, dataset="ds")` | delete ONE item (its data record + graph nodes + vector entries) |
| `forget(dataset="ds")` | delete the entire dataset |
| `forget(everything=True)` | delete everything the user owns (this is what `seed_reset`-style wipes use) |
| `forget(dataset="ds", memory_only=True)` | drop graph+vector memory but KEEP raw files (so you can re-`cognify` with new settings) |
| `forget(dataset="ds", data_id=ID, memory_only=True)` | memory-only for a single file |

Notes:
- `data_id` MUST be a `uuid.UUID` and requires `dataset`/`dataset_id`.
- We already capture each fact's `cognee_data_id` on the ledger row during `persist`, so single-item forget is possible.
- Our existing `cognee_client.forget_fact(data_id)` already calls
  `cognee.forget(data_id=UUID(...), dataset=DATASET)` — the single-item mode. It
  works (verified in logs: `forget: deleted data_id=… from dataset=…`). It is just
  **not wired to any trigger** right now — that's what this phase adds.

## B. What we are building

A new explicit endpoint (NOT a judge outcome — a human/clinician action):

### `POST /forget`
Req: `{ "patient_id":"P001", "fact_id":"<uuid>", "reason":"entered in error — wrong patient" }`
Behavior:
1. `ledger.get(fact_id)` → 404 if missing.
2. If the fact has `cognee_data_id` → `cognee_client.forget_fact(data_id)` (removes it
   from the healed `total_recall` graph+vector memory → recall stops returning it).
3. Ledger: set `status="retracted"`, store `reason`. The row is KEPT for audit
   (so `/why` can still explain "retracted on <date>: entered in error"), but it is
   excluded from current truth, the time-scrubber, and the active set.
4. **Un-supersede restore (edge case):** if the retracted fact had superseded an
   older one (i.e. some fact `X` has `X.superseded_by == fact_id`), restore `X`:
   `X.status="active"`, `X.valid_to=None`, `X.superseded_by=None`. Rationale: if the
   superseding fact was bogus, the prior truth becomes current again.
Res: `{ "fact":ClinicalFact(retracted), "restored":ClinicalFact|null, "forgotten":true, "cognee":{deletion summary} }`

### Supporting changes
- `schema.py`: `FactStatus` gains `"retracted"`.
- `ledger.py`:
  - `retract(fact_id, reason) -> (retracted: ClinicalFact|None, restored: ClinicalFact|None)`.
  - `snapshot(...)` and the `/graph` builder **skip** `status=="retracted"` facts
    (an error was never "true at" any date). `query_active` already excludes them.
- `dto.py`: `ForgetRequest`, `ForgetResponse`.
- `routes_scenario.py`: add `POST /forget` (lifecycle sits next to seed/ingest/reset).

## C. Why this is the correct design (not a forget-on-supersede regression)
- Supersession = the fact WAS true, then stopped being true. Keep it (temporal history).
- Entered-in-error = the fact was NEVER true. Remove it from memory. `forget()`.
- The two are different lifecycle events; only the second calls `forget`.

## D. Demo value (hackathon "How we use Cognee")
- Claims the `forget` lifecycle primitive with a real story: "this penicillin-allergy
  note was entered for the wrong patient — retract it." Watch it disappear from the
  Cognee graph (`/graph/cognee`) and from recall, while the ledger keeps an audit
  trail of the retraction. Pairs with the time-scrubber and "why".

## E. Acceptance (done-when)
- `POST /forget` on a baseline fact returns `forgotten=true` and a Cognee deletion
  summary showing ≥1 item removed.
- The retracted fact no longer appears in `GET /graph` (any `as_of`) and is not in
  the active set; ledger row persists with `status="retracted"` + reason.
- If the retracted fact had superseded another, the prior fact is `active` again.
- `GET /graph/cognee` no longer contains the forgotten assertion's nodes.
- A `/ask` over the affected subject no longer surfaces the forgotten fact.

## F. Edge cases / ceilings (ponytail)
- Forgetting a fact that also lives in the frozen `naive_baseline` dataset is NOT
  mirrored there (naive `add` doesn't track per-fact `data_id`). Acceptable: the
  villain is a fixed pre-heal snapshot; entered-in-error correction is a
  smart-memory feature. Upgrade path: track naive data_ids if we ever need it.
- `memory_only=True` is the better choice if we later want to re-cognify after an
  edit rather than a true delete; entered-in-error is a true delete, so full forget.

## Done → primitive count complete (add/cognify/temporal, recall TEMPORAL/RAG, improve, **forget**, provenance).
