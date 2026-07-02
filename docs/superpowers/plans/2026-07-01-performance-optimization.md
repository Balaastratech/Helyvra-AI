# Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut ingest/seed/chat latency dramatically without changing a single answer, by making Cognee's expensive `cognify` run **once per ingest instead of once per fact**, tuning its chunking/temporal cost, and deferring it off the response path — safe because the **ledger is the authoritative source of truth and Cognee is a best-effort semantic layer**.

**Architecture:** All Cognee calls live behind `app/memory/cognee_client.py` (the seam). The engine's `persist` node (`app/engine/nodes.py`) currently does `add_fact` + `cognify(temporal=True)` (+`improve` on heal) **per fact**, and `service.run_facts` loops facts → N cognifies for N facts. We add a `defer_cognify` path so `persist` only *adds* during a batch, and the caller cognifies **once** at the end; we add chunking/batch/temporal tuning to `cognify()`; and we ensure the chat/agent ingest path schedules the sync in the background. No ledger logic changes → no answer changes.

**Tech Stack:** Python 3.13, FastAPI, cognee 1.2.2, LangGraph, pytest (monkeypatch by reassigning module functions; `asyncio.run`; count real calls — the existing `tests/test_engine.py` style).

---

## Files

- Modify: `backend/app/memory/cognee_client.py` — `cognify()` tuning params; new `cognify_batch_after_adds()` helper.
- Modify: `backend/app/engine/state.py` — add `defer_cognify: bool` to `TRState`.
- Modify: `backend/app/engine/nodes.py` — `persist` honors `defer_cognify` (add only, skip cognify/improve).
- Modify: `backend/app/engine/service.py` — `run_facts` runs with `defer_cognify=True`, then cognifies once.
- Modify: `backend/app/main.py` — optional env-gated startup precompute of seed patients.
- Test: `backend/tests/test_perf.py` — new; asserts call-counts/kwargs via monkeypatch (no real Cognee).

---

## Task 1: `cognify()` gains cost-tuning params

**Files:**
- Modify: `backend/app/memory/cognee_client.py:95-103`
- Test: `backend/tests/test_perf.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_perf.py
import asyncio
import types
import pytest
from app.memory import cognee_client


def _capture_cognify(monkeypatch):
    """Replace cognee.cognify with a call-recording stub. Returns the calls list."""
    calls = []

    async def fake_cognify(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(cognee_client.cognee, "cognify", fake_cognify)
    return calls


def test_cognify_passes_chunk_size_and_batch(monkeypatch):
    calls = _capture_cognify(monkeypatch)
    # No ontology config in the test env → cognify runs without `config`.
    monkeypatch.setattr(cognee_client, "_ontology_config", lambda: None)
    asyncio.run(cognee_client.cognify("P010", temporal=False))
    assert len(calls) == 1
    kw = calls[0]
    assert kw["datasets"] == ["tr_p010"]
    assert kw["temporal_cognify"] is False
    assert kw["chunk_size"] == 4096
    assert kw["data_per_batch"] == 20
    assert kw["chunks_per_batch"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_cognify_passes_chunk_size_and_batch -v`
Expected: FAIL — `KeyError: 'chunk_size'` (current `cognify` passes no chunk_size).

- [ ] **Step 3: Write minimal implementation**

Replace `cognify` in `backend/app/memory/cognee_client.py` (currently lines 95-103):

```python
async def cognify(
    patient_id: str,
    temporal: bool = True,
    chunk_size: int = 4096,
    data_per_batch: int = 20,
    chunks_per_batch: int = 100,
) -> None:
    """Build/refresh the temporal knowledge graph for the patient's dataset,
    grounded in the medical ontology (§4).

    Perf: clinical facts are tiny, so a large `chunk_size` keeps each fact to one
    chunk (fewer LLM calls); batch params keep the pipeline busy. `temporal=False`
    is much faster (temporal mode drops chunks_per_batch to 10) and is used for
    every patient except the supersession-demo chart that needs the time-scrubber."""
    kwargs: dict = {
        "datasets": [dataset_for(patient_id)],
        "temporal_cognify": temporal,
        "chunk_size": chunk_size,
        "data_per_batch": data_per_batch,
        "chunks_per_batch": chunks_per_batch,
    }
    cfg = _ontology_config()
    if cfg is not None:
        kwargs["config"] = cfg
    await cognee.cognify(**kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_perf.py::test_cognify_passes_chunk_size_and_batch -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/cognee_client.py backend/tests/test_perf.py
git commit -m "perf: tune cognify chunk_size + batch params"
```

---

## Task 2: Add `defer_cognify` to engine state

**Files:**
- Modify: `backend/app/engine/state.py`
- Test: (covered by Task 3's test)

- [ ] **Step 1: Read the current state file**

Run: `cd backend && python -c "import app.engine.state as s; print(s.TRState.__annotations__)"`
Expected: prints the current TRState keys (includes `cognee_sync`).

- [ ] **Step 2: Add the field**

In `backend/app/engine/state.py`, add to the `TRState` TypedDict (next to `cognee_sync`):

```python
    # When True, the persist node ADDS the fact to Cognee but SKIPS cognify/improve
    # so a multi-fact ingest can cognify ONCE at the end (see service.run_facts).
    defer_cognify: bool
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/state.py
git commit -m "perf: add defer_cognify flag to engine state"
```

---

## Task 3: `persist` honors `defer_cognify` (add-only during batch)

**Files:**
- Modify: `backend/app/engine/nodes.py:162-213` (the `persist` async function)
- Test: `backend/tests/test_perf.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_perf.py
from app.engine import nodes as eng_nodes
from app.memory.schema import ClinicalFact
from datetime import date


def _fact(pid="P010", value="amlodipine 5mg"):
    return ClinicalFact(
        patient_id=pid, subject="medication", predicate="prescribed",
        value=value, valid_from=date(2026, 1, 1), source="Dr. Test",
        raw_text=f"On 2026-01-01, prescribed {value}.",
    )


def test_persist_defer_skips_cognify(monkeypatch):
    add_calls, cognify_calls = [], []

    async def fake_add(fact):
        add_calls.append(fact)
        return None  # no data_id

    async def fake_cognify(*a, **k):
        cognify_calls.append((a, k))

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)

    state = {
        "patient_id": "P010", "new_fact": _fact(), "classification": "NEW",
        "cognee_sync": True, "defer_cognify": True, "actions": [],
    }
    import asyncio
    asyncio.run(eng_nodes.persist(state))
    assert len(add_calls) == 1        # fact WAS added
    assert len(cognify_calls) == 0    # but cognify was DEFERRED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_persist_defer_skips_cognify -v`
Expected: FAIL — `cognify_calls` has 1 entry (current `persist` always cognifies).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/engine/nodes.py`, inside `persist`, after the `new = state["new_fact"]` line and before the `cognee_client.cognify(...)` call, wrap the cognify/improve block. Change the existing block:

```python
        data_id = await cognee_client.add_fact(new)
        if data_id:
            new.cognee_data_id = data_id
            ledger.upsert(new)  # persist the data_id for future targeted forgets
        await cognee_client.cognify(new.patient_id, temporal=True)
        if classification in ("SUPERSEDES", "CONTRADICTS"):
            try:
                await cognee_client.improve(new.patient_id)
                note = " +improve"
            except Exception as exc:  # pragma: no cover - defensive
                note = f" (improve skipped: {type(exc).__name__})"
        actions.append(f"persist: Cognee add+cognify{note} [{new.id[:8]}].")
```

to:

```python
        data_id = await cognee_client.add_fact(new)
        if data_id:
            new.cognee_data_id = data_id
            ledger.upsert(new)  # persist the data_id for future targeted forgets
        if state.get("defer_cognify"):
            # Batch mode: add now, caller cognifies ONCE after all facts.
            actions.append(f"persist: Cognee add (cognify deferred) [{new.id[:8]}].")
        else:
            await cognee_client.cognify(new.patient_id, temporal=True)
            if classification in ("SUPERSEDES", "CONTRADICTS"):
                try:
                    await cognee_client.improve(new.patient_id)
                    note = " +improve"
                except Exception as exc:  # pragma: no cover - defensive
                    note = f" (improve skipped: {type(exc).__name__})"
            actions.append(f"persist: Cognee add+cognify{note} [{new.id[:8]}].")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_perf.py::test_persist_defer_skips_cognify -v`
Expected: PASS

- [ ] **Step 5: Run the engine regression suite to prove no answer changed**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: PASS (all existing supersession/classification assertions still green — `cognee_sync=False` path is unaffected).

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/nodes.py backend/tests/test_perf.py
git commit -m "perf: persist honors defer_cognify (add-only during batch)"
```

---

## Task 4: `run_facts` batches — cognify ONCE after N facts

**Files:**
- Modify: `backend/app/engine/service.py:48-62`
- Test: `backend/tests/test_perf.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_perf.py
from app.engine import service as eng_service


def test_run_facts_cognifies_once(monkeypatch):
    cognify_calls = []

    async def fake_cognify(patient_id, temporal=True, **k):
        cognify_calls.append(patient_id)

    async def fake_add(fact):
        return None

    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)

    facts = [_fact(value="lisinopril 10mg"), _fact(value="amlodipine 5mg"),
             _fact(value="metformin 500mg")]
    import asyncio
    asyncio.run(eng_service.run_facts("P010", facts, cognee_sync=True))
    # Three facts, but Cognee is cognified exactly ONCE (batched), not 3x.
    assert cognify_calls == ["P010"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_run_facts_cognifies_once -v`
Expected: FAIL — `cognify_calls` has 3 entries (per-fact cognify today).

- [ ] **Step 3: Write minimal implementation**

Replace `run_facts` in `backend/app/engine/service.py` (lines 48-62). Add the import at the top of the file (next to the existing imports):

```python
from app.memory import cognee_client
```

Then:

```python
async def run_facts(
    patient_id: str, facts: List[ClinicalFact], cognee_sync: bool = True
) -> List[TRState]:
    """Ingest several facts in order, then cognify ONCE (perf: not per fact).

    Each fact still flows through the full engine (recall→judge→reconcile→persist)
    and the ledger is updated per fact — only the expensive Cognee graph build is
    batched to the end, which does not change any answer (the ledger is truth)."""
    results: List[TRState] = []
    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        for fact in facts:
            cfg = {"configurable": {"thread_id": f"{patient_id}:{fact.id}"}}
            res = await app.ainvoke(
                {
                    "patient_id": patient_id, "new_fact": fact,
                    "cognee_sync": cognee_sync, "defer_cognify": cognee_sync,
                },
                cfg,
            )
            results.append(res)
    if cognee_sync:
        # One graph build for the whole batch. Best-effort: a Cognee lag must not
        # break the ingest (the ledger already holds the authoritative result).
        try:
            healed = any(
                r.get("classification") in ("SUPERSEDES", "CONTRADICTS") for r in results
            )
            await cognee_client.cognify(patient_id, temporal=True)
            if healed:
                try:
                    await cognee_client.improve(patient_id)
                except Exception:  # pragma: no cover - best-effort
                    pass
        except Exception:  # pragma: no cover - Cognee lag never breaks ingest
            pass
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_perf.py::test_run_facts_cognifies_once -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/service.py backend/tests/test_perf.py
git commit -m "perf: batch cognify once per multi-fact ingest"
```

---

## Task 5: Background the cognify on the single-fact chat path

**Files:**
- Modify: `backend/app/engine/service.py` (add `run_fact_bg` helper)
- Test: `backend/tests/test_perf.py`

Context: `run_fact` (single fact, used by the agent's `ingest_fact` tool) still cognifies synchronously via `persist`. The chat response should not wait ~20s for the graph build. We add a helper that runs the engine with `defer_cognify=True` (ledger updated, answer ready) and schedules the one cognify as a background task.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_perf.py
def test_run_fact_bg_defers_and_schedules(monkeypatch):
    scheduled = []
    cognify_calls = []

    async def fake_add(fact):
        return None

    async def fake_cognify(patient_id, temporal=True, **k):
        cognify_calls.append(patient_id)

    def fake_schedule(coro):
        scheduled.append(coro)
        coro.close()  # don't actually run it in the test

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service, "_schedule", fake_schedule)

    import asyncio
    state = asyncio.run(eng_service.run_fact_bg("P010", _fact()))
    assert state["classification"] in ("NEW", "SUPERSEDES", "CONSISTENT", "CONTRADICTS")
    assert len(scheduled) == 1        # cognify was scheduled, not awaited inline
    assert cognify_calls == []        # (the scheduled coro was not run in the test)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_run_fact_bg_defers_and_schedules -v`
Expected: FAIL — `run_fact_bg` / `_schedule` do not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/engine/service.py` (after `run_fact`), plus an `asyncio` import if not present:

```python
import asyncio


def _schedule(coro) -> None:
    """Fire-and-forget a coroutine on the running loop (seam for tests)."""
    asyncio.create_task(coro)


async def _cognify_bg(patient_id: str, healed: bool) -> None:
    try:
        await cognee_client.cognify(patient_id, temporal=True)
        if healed:
            try:
                await cognee_client.improve(patient_id)
            except Exception:  # pragma: no cover - best-effort
                pass
    except Exception:  # pragma: no cover - Cognee lag never breaks a turn
        pass


async def run_fact_bg(patient_id: str, fact: ClinicalFact) -> TRState:
    """Ingest ONE fact for the chat path: the ledger answer is ready immediately;
    the Cognee graph build is scheduled in the BACKGROUND so the turn returns fast.
    Answer correctness is unaffected (the ledger is authoritative)."""
    async with checkpointer() as saver:
        app = build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": f"{patient_id}:{fact.id}"}}
        state = await app.ainvoke(
            {
                "patient_id": patient_id, "new_fact": fact,
                "cognee_sync": True, "defer_cognify": True,
            },
            cfg,
        )
    healed = state.get("classification") in ("SUPERSEDES", "CONTRADICTS")
    _schedule(_cognify_bg(patient_id, healed))
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_perf.py::test_run_fact_bg_defers_and_schedules -v`
Expected: PASS

- [ ] **Step 5: Wire the agent ingest tool to the background path**

In `backend/app/agent/tools.py`, find where `ingest_fact` calls `service.run_fact(...)` and change it to `service.run_fact_bg(...)`. (Read the file first; if it calls `run_fact`, swap the name — the return `state` shape is identical.)

Run: `cd backend && python -m pytest tests/test_agent.py -v`
Expected: PASS (agent behavior unchanged; only cognify timing moved off the response).

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/service.py backend/app/agent/tools.py backend/tests/test_perf.py
git commit -m "perf: background cognify on the chat ingest path"
```

---

## Task 6: temporal only where the time-scrubber needs it

**Files:**
- Modify: `backend/app/engine/service.py` (`run_facts`, `_cognify_bg`)
- Test: `backend/tests/test_perf.py`

Context: `temporal_cognify=True` forces `chunks_per_batch=10` (slow). Only the supersession-demo patient (`P001`) needs the time-scrubber / "as of" answers. Drive temporal by a small allowlist so every other patient gets the faster non-temporal build.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_perf.py
def test_temporal_only_for_demo_patient(monkeypatch):
    seen = {}

    async def fake_cognify(patient_id, temporal=True, **k):
        seen[patient_id] = temporal

    async def fake_add(fact):
        return None

    monkeypatch.setattr(eng_nodes.cognee_client, "add_fact", fake_add)
    monkeypatch.setattr(eng_nodes.cognee_client, "cognify", fake_cognify)
    monkeypatch.setattr(eng_service.cognee_client, "cognify", fake_cognify)

    import asyncio
    asyncio.run(eng_service.run_facts("P001", [_fact("P001")], cognee_sync=True))
    asyncio.run(eng_service.run_facts("P010", [_fact("P010")], cognee_sync=True))
    assert seen["P001"] is True    # supersession demo → temporal
    assert seen["P010"] is False   # everyone else → faster non-temporal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_temporal_only_for_demo_patient -v`
Expected: FAIL — both are `True` (temporal always on).

- [ ] **Step 3: Write minimal implementation**

At the top of `backend/app/engine/service.py` (after imports):

```python
import os

# Patients that need temporal_cognify (the time-scrubber / "as of" demo). Everyone
# else gets the faster non-temporal build — correctness is unaffected because the
# ledger holds valid_from/valid_to and drives "as of" answers.
_TEMPORAL_PATIENTS = set(
    p.strip() for p in os.environ.get("TEMPORAL_PATIENTS", "P001").split(",") if p.strip()
)


def _wants_temporal(patient_id: str) -> bool:
    return patient_id.strip() in _TEMPORAL_PATIENTS
```

In `run_facts`, change the batch cognify call:

```python
            await cognee_client.cognify(patient_id, temporal=_wants_temporal(patient_id))
```

In `_cognify_bg`, change its cognify call the same way:

```python
        await cognee_client.cognify(patient_id, temporal=_wants_temporal(patient_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_perf.py::test_temporal_only_for_demo_patient -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/service.py backend/tests/test_perf.py
git commit -m "perf: temporal cognify only for the scrubber-demo patient(s)"
```

---

## Task 7: Env-gated startup precompute of seed patients

**Files:**
- Modify: `backend/app/main.py` (the `_startup` hook, ~lines 46-49)
- Test: `backend/tests/test_perf.py`

Context: cold-start slowness disappears if the seed patients' graphs are built once at startup, so the live demo only cognifies the 1–2 held-back corrections. Gate behind `PRECOMPUTE_SEED=1` so tests/dev can skip it.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_perf.py
import app.main as main_mod


def test_precompute_seed_runs_when_enabled(monkeypatch):
    called = []

    async def fake_precompute():
        called.append(True)

    monkeypatch.setenv("PRECOMPUTE_SEED", "1")
    monkeypatch.setattr(main_mod, "_precompute_seed", fake_precompute)
    import asyncio
    asyncio.run(main_mod._maybe_precompute())
    assert called == [True]


def test_precompute_seed_skipped_when_disabled(monkeypatch):
    called = []

    async def fake_precompute():
        called.append(True)

    monkeypatch.delenv("PRECOMPUTE_SEED", raising=False)
    monkeypatch.setattr(main_mod, "_precompute_seed", fake_precompute)
    import asyncio
    asyncio.run(main_mod._maybe_precompute())
    assert called == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_perf.py::test_precompute_seed_runs_when_enabled -v`
Expected: FAIL — `_maybe_precompute` / `_precompute_seed` do not exist.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/main.py`, add near the other imports:

```python
import asyncio
from app.memory import cognee_client, records
```

Add these functions above `@app.on_event("startup")`:

```python
async def _precompute_seed() -> None:
    """Cognify every seed patient's dataset once so the live demo is warm."""
    for p in records.list_patients():
        try:
            await cognee_client.cognify(p["patient_id"], temporal=False)
        except Exception:  # pragma: no cover - warmup is best-effort
            pass


async def _maybe_precompute() -> None:
    if os.environ.get("PRECOMPUTE_SEED") == "1":
        await _precompute_seed()
```

Change the startup hook to schedule it without blocking boot:

```python
@app.on_event("startup")
def _startup() -> None:
    # Ensure the ledger schema exists before the first request.
    ledger.init()
    # Warm the Cognee graphs in the background (env-gated) so the demo isn't cold.
    try:
        asyncio.get_event_loop().create_task(_maybe_precompute())
    except RuntimeError:  # pragma: no cover - no running loop (e.g. under some test runners)
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_perf.py::test_precompute_seed_runs_when_enabled tests/test_perf.py::test_precompute_seed_skipped_when_disabled -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_perf.py
git commit -m "perf: env-gated startup precompute of seed patient graphs"
```

---

## Task 8: Full-suite regression + manual latency check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend test suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS — existing `test_engine.py`, `test_api.py`, `test_agent.py` all green (proves no answer changed), plus the new `test_perf.py`.

- [ ] **Step 2: Manual latency sanity check (before/after, real Cognee)**

Run: `cd backend && python -m pytest tests/test_api.py -k seed -v` (or the existing seed smoke) and note wall-clock time; compare against a pre-change run recorded in the commit message. Expect a large drop on multi-fact seed (N cognifies → 1).

- [ ] **Step 3: Commit any notes**

```bash
git add -A
git commit -m "perf: verify full suite green + record latency improvement" --allow-empty
```

---

## Self-Review

- **Spec coverage** (against `FAMILY_GRAPH_AND_PERF_PLAN.md` §B.3): B.3#1 background cognify → Task 5; B.3#2 skip-summarize → *deferred* (see note); B.3#3 batch not per-fact → Task 4; B.3#4 bigger chunk_size → Task 1; B.3#5 temporal only where needed → Task 6; B.3#6 precompute → Task 7. **Not covered: B.3#2 (skip `summarize_text`)** — it needs a custom Cognee pipeline whose API is version-risky in 1.2.2; the batching + chunk_size + background + temporal-off wins (Tasks 1,4,5,6) already collapse the LLM-call count, so skip-summarize is a documented follow-up, not built here. B.3#7 (batch embeddings) is internal to Cognee and not exposed — left to Cognee.
- **Placeholder scan:** none — every step has runnable code/commands.
- **Type consistency:** `defer_cognify` (state.py) is read in `persist` (Task 3) and set in `run_facts`/`run_fact_bg` (Tasks 4/5); `cognify(...)` signature (Task 1) matches every caller (Tasks 4,5,6,7); `_wants_temporal`/`_schedule`/`_maybe_precompute`/`_precompute_seed` are each defined before use.
```
```

**Note for the executor:** these changes touch only *when/how much* Cognee runs. If any existing test in `test_api.py`/`test_agent.py` asserts synchronous graph state immediately after a chat ingest, it may need to await the background task — surface that rather than reverting the perf win.
