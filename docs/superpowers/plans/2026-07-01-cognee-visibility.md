# Cognee Visibility (Attribution) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Cognee's real, already-computed work visible to a judge — **honestly**. Every chip/label this plan adds surfaces a field the backend already produces (`ontology_valid`, `search_type`, the raw Cognee graph, memify's own text) — nothing is invented, and nothing claims Cognee did something the ledger actually did.

**Architecture:** The chat answer (`engine/answer.py`) is synthesized from the **ledger**, not Cognee recall — that's correct and must stay that way (§5.3/§5.4's grounding guarantee). So the honest attribution surface is: (1) `ontology_valid` per citation — real, computed in `cognee_client.ground_fact`, stored on `ClinicalFact`, never rendered; (2) the Compare tab's `search_type` (`RAG_COMPLETION` vs `TEMPORAL`) — real, already returned by `/ask`, just not labeled "via Cognee"; (3) the memify risk-edge node in the raw Cognee graph — real (written by `memify_risk_edges`), needs a recognizable badge; (4) a "How we use Cognee" primitives panel — documentation, backed by real code references; (5) nav reachability to Memory Map / Compare, already routed, just not promoted.

**Tech Stack:** FastAPI/Pydantic (backend DTOs), React + TypeScript + Tailwind (frontend), pytest for backend, no new dependencies.

**On "editing Cognee's local install":** investigated first — not needed. Every primitive this plan surfaces (`RDFLibOntologyResolver`, `FuzzyMatchingStrategy`, `OntologyConfig`, `get_graph_engine`) imports and runs cleanly in the installed `cognee==1.2.2` (verified live in Task 0). Cognee's supported extension points (ontology file, custom `DataPoint`, Tasks) are what the existing code already uses — that *is* "using Cognee's local platform," done the way the library intends. Hand-patching vendored `site-packages/cognee` source would be unversioned, wouldn't survive a reinstall, and isn't necessary — so this plan does not touch vendored Cognee code.

---

## Task 0: Confirm the ontology modules import cleanly (no plan should rest on an assumption)

**Files:** none (verification only)

- [ ] **Step 1: Run the import check**

Run: `cd backend && .venv/Scripts/python.exe -c "from cognee.modules.ontology.rdf_xml.RDFLibOntologyResolver import RDFLibOntologyResolver; from cognee.modules.ontology.matching_strategies import FuzzyMatchingStrategy; from cognee.modules.ontology.ontology_config import Config, OntologyConfig; print('ontology modules OK')"`

Expected: prints `ontology modules OK` (confirmed already in this session — re-run once before starting so the executor sees it fresh, since these imports are exactly what `cognee_client._ontology_resolver`/`_ontology_config` depend on).

- [ ] **Step 2: No commit** (verification step only)

---

## Task 1: Surface `ontology_valid` on every citation

**Files:**
- Modify: `backend/app/engine/answer.py:43-54` (the `Citation` model)
- Modify: `backend/app/engine/answer.py:138-156` (`_citations_for`)
- Modify: `frontend/src/api/types.ts` (the `Citation` interface, ~line 237)
- Modify: `frontend/src/components/ChatPane.tsx:51-70` (`CitationChips`)
- Test: `backend/tests/test_answer.py` (new)

- [ ] **Step 1: Write the failing backend test**

```python
# backend/tests/test_answer.py
"""Citation grounding surfacing (Cognee-visibility plan, Task 1)."""
from __future__ import annotations

from datetime import date

from app.engine import answer
from app.memory.schema import ClinicalFact


def _fact(ontology_valid, **kw):
    defaults = dict(
        patient_id="P010", subject="allergy", predicate="diagnosed",
        value="penicillin", valid_from=date(2021, 8, 9), source="Dr. Adams",
        source_document="P010_discharge_2021.pdf", document_title="Discharge Summary",
    )
    defaults.update(kw)
    f = ClinicalFact(**defaults)
    f.ontology_valid = ontology_valid
    return f


def test_citations_for_carries_ontology_valid():
    grounded = _fact(True)
    ungrounded = _fact(False, value="some made up thing")
    facts = [grounded, ungrounded]
    citations = answer._citations_for([grounded.id, ungrounded.id], facts)
    by_id = {c.fact_id: c for c in citations}
    assert by_id[grounded.id].ontology_valid is True
    assert by_id[ungrounded.id].ontology_valid is False


def test_citations_for_none_when_not_checked():
    f = _fact(None)  # grounding never ran (no clinical entity to check)
    citations = answer._citations_for([f.id], [f])
    assert citations[0].ontology_valid is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_answer.py -v`
Expected: FAIL — `Citation` has no `ontology_valid` attribute.

- [ ] **Step 3: Add the field to `Citation` and populate it**

In `backend/app/engine/answer.py`, change the `Citation` class (lines 43-54):

```python
class Citation(BaseModel):
    """A clinical claim's grounding — one ledger fact, with its provenance.

    Fields all come straight off `ClinicalFact` (already present today, just never
    surfaced), so the UI can open the exact source record behind a sentence.
    `ontology_valid` is Cognee's own ontology-grounding verdict (cognee_client.
    ground_fact) — real, computed at ingest time, not inferred here."""
    fact_id: str
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    page: Optional[int] = None
    valid_from: Optional[date] = None
    source: str = "unknown"
    ontology_valid: Optional[bool] = None
```

Change `_citations_for` (lines 138-156) to pass it through:

```python
def _citations_for(ids: List[str], facts: List[ClinicalFact]) -> List[Citation]:
    """Build authoritative Citations from the facts the model cited (by id)."""
    by_id = {f.id: f for f in facts}
    out: List[Citation] = []
    for fid in ids:
        f = by_id.get(fid)
        if f is None:
            continue  # model cited an id we didn't give it — drop it (no hallucinated provenance)
        out.append(
            Citation(
                fact_id=f.id,
                source_document=f.source_document,
                document_title=f.document_title,
                page=f.page,
                valid_from=f.valid_from,
                source=f.source,
                ontology_valid=f.ontology_valid,
            )
        )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_answer.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run the existing answer/agent regression suite**

Run: `cd backend && python -m pytest tests/test_engine.py tests/test_agent.py -v`
Expected: PASS (unchanged — this is an additive field)

- [ ] **Step 6: Add the field to the frontend `Citation` type**

In `frontend/src/api/types.ts`, find the `Citation` interface (~line 237) and add the field:

```typescript
/** One grounding citation behind a clinical claim (answer.py :: Citation). */
export interface Citation {
  fact_id: string
  source_document?: string | null
  document_title?: string | null
  page?: number | null
  valid_from?: string | null
  source: string
  /** Cognee's own ontology-grounding verdict (real, computed at ingest — not inferred). */
  ontology_valid?: boolean | null
}
```

(Keep whatever other fields already exist in that interface — only add `ontology_valid`.)

- [ ] **Step 7: Render the grounding badge on citation chips**

In `frontend/src/components/ChatPane.tsx`, replace the `CitationChips` function (lines 51-70):

```tsx
/** Citation chips — click opens the exact source document (provenance you can see).
 * A grounded chip also shows a small "Cognee ✓" badge — Cognee's real ontology
 * verdict (ClinicalFact.ontology_valid), not decoration. Ungrounded/unknown facts
 * get no badge (honest: we never invent a checkmark). */
function CitationChips({ citations }: { citations?: Citation[] }) {
  const openDoc = useUi((s) => s.openDoc)
  const openWhy = useUi((s) => s.openWhy)
  if (!citations || citations.length === 0) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {citations.map((c, i) => (
        <button
          key={`${c.fact_id}-${i}`}
          onClick={() => (c.source_document ? openDoc(c.source_document) : openWhy(c.fact_id))}
          title={c.source_document ? 'Open source document' : 'Show provenance'}
          className="inline-flex items-center gap-1 rounded-full border border-active/40 bg-active-soft px-2 py-0.5 text-[10px] font-medium text-active hover:border-active hover:bg-active/10"
        >
          <FileText className="h-2.5 w-2.5" />
          {c.document_title || c.source || `${c.valid_from ?? ''}`.trim() || 'source'}
          {c.ontology_valid === true && (
            <span
              className="ml-1 rounded-full bg-active/20 px-1 text-active"
              title="Grounded in the medical ontology (Cognee ontology resolver)"
            >
              Cognee ✓
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/engine/answer.py backend/tests/test_answer.py frontend/src/api/types.ts frontend/src/components/ChatPane.tsx
git commit -m "feat: surface Cognee ontology grounding on citation chips"
```

---

## Task 2: Label the Compare tab's real Cognee search types as "via Cognee"

**Files:**
- Read first: `frontend/src/components/SplitChat.tsx` (find where `search_type` is rendered per pane)
- Modify: `frontend/src/components/SplitChat.tsx`

- [ ] **Step 1: Locate the current search_type rendering**

Run: `cd frontend && grep -n "search_type\|RAG_COMPLETION\|TEMPORAL" src/components/SplitChat.tsx`
Expected: shows the line(s) where each pane displays its `search_type` (per the existing `AskResponse.search_type` field from `backend/app/api/dto.py:86-90`).

- [ ] **Step 2: Read the surrounding JSX to match existing style**

Read `frontend/src/components/SplitChat.tsx` in full before editing (small file) so the edit matches existing badge/pill conventions (the codebase already uses `rounded-full border ... px-2 py-0.5 text-[10px]` pill styling throughout `ChatPane.tsx` — match that).

- [ ] **Step 3: Add a "via Cognee ·" prefix to the existing search_type pill**

Wherever the pane currently renders something like `{searchType}` or a badge with the raw enum value (e.g. `TEMPORAL` / `RAG_COMPLETION`), change the displayed text to prefix it, e.g.:

```tsx
<span className="inline-flex items-center gap-1 rounded-full border border-active/40 bg-active-soft px-2 py-0.5 text-[10px] font-medium text-active" title="The exact Cognee search type used for this answer">
  via Cognee · {searchType === 'TEMPORAL' ? 'Time-aware memory' : 'No memory · plain lookup'}
</span>
```

(Match the existing dev→human copy rewrite table already established in `docs/design-brief.md` — `TEMPORAL` → "Time-aware memory", `RAG_COMPLETION` → "No memory · plain lookup" — this task only adds the "via Cognee" attribution prefix to copy that already exists; do not invent new copy conventions.)

- [ ] **Step 4: Manual verification (no backend contract change, so no new test)**

Run: `cd frontend && npm run dev` then open `/compare`, ask the allergy question, confirm both panes show a "via Cognee · …" pill with the correct search type per side (naive = RAG_COMPLETION/no memory, smart = TEMPORAL/time-aware).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SplitChat.tsx
git commit -m "feat: label Compare tab search types as via Cognee"
```

---

## Task 3: Badge the memify risk-edge node in the raw Cognee graph

**Files:**
- Modify: `backend/app/memory/cognee_client.py:224-253` (`memify_risk_edges`)
- Modify: `backend/app/api/routes_graph.py:96-121` (`_map_cognee_node`)
- Modify: `backend/app/api/dto.py` (`CogneeGraphResponse` — add nothing; nodes are already `List[dict]`, so no schema change needed)
- Test: `backend/tests/test_graph_routes.py` (new)

Context: `memify_risk_edges` writes a recognizable sentence prefix (`"Risk synthesis for patient {patient_id}: ..."`) into Cognee before cognifying. The raw graph node Cognee extracts from that text has no visible marker today. We detect the prefix and badge the node so a judge sees "memify" attached to a *real* node, not a label pasted onto something unrelated.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graph_routes.py
"""Memify node labeling in the raw Cognee graph (Cognee-visibility plan, Task 3)."""
from app.api import routes_graph


def test_map_cognee_node_badges_memify_risk_synthesis():
    node = ("n1", {"text": "Risk synthesis for patient P010: Elevated cardiovascular risk."})
    mapped = routes_graph._map_cognee_node(node)
    assert mapped["memify"] is True
    assert mapped["label"] == "Risk synthesis for patient P010: Elevated cardiovascular risk."


def test_map_cognee_node_not_memify_for_ordinary_fact():
    node = ("n2", {"text": "On 2021-08-09, patient P010 diagnosed allergy: penicillin."})
    mapped = routes_graph._map_cognee_node(node)
    assert mapped["memify"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_routes.py -v`
Expected: FAIL — `mapped["memify"]` raises `KeyError` (the key doesn't exist yet).

- [ ] **Step 3: Add the marker constant and detection**

In `backend/app/memory/cognee_client.py`, add a module-level constant right above `memify_risk_edges` (before line 224):

```python
# Recognizable prefix on every memify-synthesized sentence (§4 memify). The raw
# Cognee graph has no built-in "this came from memify" flag, so we detect our
# own marker text — real data we wrote, not an invented label.
MEMIFY_MARKER = "Risk synthesis for patient"
```

Then inside `memify_risk_edges`, change the `text = (...)` assignment to use the constant instead of a bare f-string prefix:

```python
            text = (
                f"{MEMIFY_MARKER} {patient_id}: {card.summary}. "
                f"{card.detail} Derived from: {contributors}."
            )
```

- [ ] **Step 4: Detect the marker in `_map_cognee_node`**

In `backend/app/api/routes_graph.py`, add the import at the top:

```python
from app.memory.cognee_client import MEMIFY_MARKER
```

Change `_map_cognee_node` (lines 96-121) — add the `memify` key to the returned dict:

```python
def _map_cognee_node(n: Any) -> dict:
    if isinstance(n, (list, tuple)) and len(n) >= 2:
        nid, props = n[0], n[1]
    elif isinstance(n, dict):
        nid, props = n.get("id"), n
    else:
        nid, props = getattr(n, "id", str(n)), getattr(n, "__dict__", {})
    props = props if isinstance(props, dict) else {}

    label = (
        props.get("name")
        or props.get("text")
        or props.get("title")
        or props.get("label")
        or props.get("type")
        or props.get("node_type")
    )
    if not label:
        # Known cosmetic issue: temporal Timestamp nodes render label-less.
        label = props.get("__class__") or "Timestamp"
    label = str(label)
    return {
        "id": str(nid),
        "label": label,
        "type": str(props.get("type") or props.get("node_type") or ""),
        "properties": {k: _jsonable(v) for k, v in props.items()},
        # True iff this node originated from the memify enrichment pass (§4) —
        # detected by the real marker text memify_risk_edges writes, not guessed.
        "memify": label.startswith(MEMIFY_MARKER),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_routes.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run the existing graph route regression**

Run: `cd backend && python -m pytest tests/test_api.py -k graph -v`
Expected: PASS (additive field, no existing assertion should break)

- [ ] **Step 7: Render the memify badge in the Memory Map graph component**

Read `frontend/src/components/MemoryGraph.tsx` first (find where a Cognee/Board node is rendered — likely `frontend/src/components/EvidenceBoard.tsx` or `ForceCanvas.tsx`, since `/board` shows the raw Cognee graph per `NavBar.tsx`'s "The Board" link). Run:

Run: `cd frontend && grep -rn "properties\|node.label\|CogneeGraphResponse\|graph/cognee" src/components/EvidenceBoard.tsx src/components/ForceCanvas.tsx src/components/MemoryGraph.tsx 2>/dev/null`

Wherever the raw Cognee node is rendered (the file that fetches `/graph/cognee` and maps nodes to visual elements), add a small badge when `node.memify === true`, e.g. a `"🧬 memify"` tag rendered next to the node label, with `title="Created by Cognee's memify enrichment pass — a real relationship the graph, not the ledger, computed."`. Match the existing node-rendering style in that file (do not introduce a new visual language — reuse whatever badge/pill pattern the Board already uses for node types).

- [ ] **Step 8: Manual verification**

Run the backend + frontend dev servers, open a patient with a combined-risk card fired (e.g. P010 after ingest), trigger `memify_risk_edges` (already wired into the ingest flow per `cognee_client.py`), open `/board`, confirm the risk-synthesis node shows the memify badge.

- [ ] **Step 9: Commit**

```bash
git add backend/app/memory/cognee_client.py backend/app/api/routes_graph.py backend/tests/test_graph_routes.py frontend/src/components/EvidenceBoard.tsx
git commit -m "feat: badge memify-created nodes in the raw Cognee graph"
```

(Adjust the last `git add` path to whichever file Step 7 actually edited.)

---

## Task 4: "How we use Cognee" panel (doubles as the README table)

**Files:**
- Modify: `frontend/src/components/HowItWorks.tsx`
- Test: none (static content; verified by manual review + reused verbatim in the README, Task 5)

- [ ] **Step 1: Add a primitives table to the existing modal**

In `frontend/src/components/HowItWorks.tsx`, add a new constant above the `HowItWorks` function (after `STEPS`):

```tsx
const COGNEE_PRIMITIVES: { primitive: string; where: string }[] = [
  { primitive: 'add (per-patient dataset)', where: 'Every ingested record — isolated per patient chart.' },
  { primitive: 'cognify(temporal_cognify=True)', where: 'Builds the time-aware graph after each heal.' },
  { primitive: 'Ontology grounding', where: 'Validates each fact against our medical ontology — see the "Cognee ✓" badge on citations.' },
  { primitive: 'memify', where: 'Materializes combined-risk relationships into the graph — see The Board.' },
  { primitive: 'recall (TEMPORAL / RAG_COMPLETION)', where: 'Powers the Compare tab’s naive-vs-healed contrast.' },
  { primitive: 'improve', where: 'Repairs the graph after a supersession heal.' },
  { primitive: 'forget', where: 'Retracts a fact entered in error — removes it from the graph.' },
  { primitive: 'per-patient datasets', where: 'One dataset per chart — a doctor asking about one patient cannot reach another’s data.' },
  { primitive: 'raw graph read', where: 'The Board / Memory Map render Cognee’s own nodes and edges directly.' },
]
```

Then add the table inside the modal body, after the existing `STEPS` `.map(...)` block (still inside the `<div className="space-y-3">...</div>` sibling structure — add a new sibling section below it):

```tsx
            <div className="mt-4 border-t border-border pt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                How we use Cognee
              </h3>
              <dl className="mt-2 space-y-1.5 text-xs">
                {COGNEE_PRIMITIVES.map((p) => (
                  <div key={p.primitive} className="flex gap-2">
                    <dt className="w-52 shrink-0 font-medium text-active">{p.primitive}</dt>
                    <dd className="text-text-muted">{p.where}</dd>
                  </div>
                ))}
              </dl>
            </div>
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`, click "How it works" in the nav, confirm the new "How we use Cognee" section renders below the existing 3-step guide, scrolls cleanly inside the modal's existing `max-h`/overflow (check the modal wrapper doesn't need an explicit scroll fix — if the list overflows the viewport, add `max-h-[70vh] overflow-y-auto` to the outer `motion.div` in the same file).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/HowItWorks.tsx
git commit -m "feat: add How we use Cognee primitives panel"
```

---

## Task 5: README "How we use Cognee" section (rubric deliverable, reuses Task 4's table verbatim)

**Files:**
- Modify: `README.md` (repo root — read it first to find the right insertion point, likely after an architecture/overview section)

- [ ] **Step 1: Read the current README structure**

Run: `head -60 "D:\Balaastra\ideas\total-recall\README.md"` (or open it) to find where an architecture/features section ends, so the new section is inserted at a natural point rather than appended blindly.

- [ ] **Step 2: Add the section**

Insert a `## How we use Cognee` section (mirroring `docs/MASTER_PLAN.md`'s existing "Cognee primitives used" table format) using the **same 9 rows** as Task 4's `COGNEE_PRIMITIVES` list, as a markdown table:

```markdown
## How we use Cognee

| Cognee primitive | Where |
|---|---|
| `add` (per-patient dataset) | Every ingested record — isolated per patient chart. |
| `cognify(temporal_cognify=True)` | Builds the time-aware graph after each heal. |
| Ontology grounding | Validates each fact against our medical ontology — surfaced as a "Cognee ✓" badge on citations. |
| `memify` | Materializes combined-risk relationships into the graph — see The Board. |
| `recall` (TEMPORAL / RAG_COMPLETION) | Powers the Compare tab's naive-vs-healed contrast. |
| `improve` | Repairs the graph after a supersession heal. |
| `forget` | Retracts a fact entered in error — removes it from the graph. |
| Per-patient datasets | One dataset per chart — a doctor asking about one patient cannot reach another's data. |
| Raw graph read | The Board / Memory Map render Cognee's own nodes and edges directly. |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add How we use Cognee section for the hackathon rubric"
```

---

## Task 6: Promote Memory Map / Compare reachability

**Files:**
- Read first: `frontend/src/components/layout/NavBar.tsx` (already read — links exist at lines 8-11)

Context: `NavBar.tsx` already lists `/compare` and `/memory` as top-level nav links (confirmed by reading the file — this part of the original ask is **already done**, not a gap). Nothing to build here.

- [ ] **Step 1: Confirm reachability is already correct**

Run: `cd frontend && grep -n "to: '/compare'\|to: '/memory'" src/components/layout/NavBar.tsx`
Expected: both lines present (already true — no code change needed).

- [ ] **Step 2: No commit** (nothing changed; this task documents that the concern is already satisfied)

---

## Self-Review

- **Spec coverage:** attribution chip on citations → Task 1; label Compare's search_type as Cognee → Task 2; label memify in the graph → Task 3; "How we use Cognee" panel → Task 4; README rubric section → Task 5; nav reachability → Task 6 (confirmed pre-existing). "Edit Cognee's local install" → addressed in the plan header with a verified reason not to (Task 0 proves the needed modules already work; no vendored-source edit is required or advisable).
- **Placeholder scan:** none — every step has exact file paths, runnable commands, and complete code (Task 2/3 Step 7 are the only "read first, then adapt to existing style" steps, which is correct per the skill's guidance for small UI edits inside files whose exact current JSX wasn't pre-read in this planning session — each still gives the exact snippet to insert and the exact grep to locate the insertion point).
- **Type consistency:** `Citation.ontology_valid` (Task 1, backend Pydantic + frontend TS) matches on both ends; `MEMIFY_MARKER` (Task 3) is defined once in `cognee_client.py` and imported (not redefined) in `routes_graph.py`; `_map_cognee_node`'s new `"memify"` key is read the same way in the Task 3 tests and the Step 7 frontend instructions.
