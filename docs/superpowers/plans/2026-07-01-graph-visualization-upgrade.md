# Graph / Memory-Map Visualization Upgrade Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current unreadable force-directed "blob" into a **clear, temporally-ordered, category-laned, interactive** memory graph that a doctor understands at a glance — including **family relationships** — with hover detail, filtering, highlight-on-select, and clean labels.

**Architecture:** Two changes. **(1) Enrich the graph data** (`GET /graph`) so each node carries its category/status/source/date/confidence/ontology-grounding and each edge is typed (supersedes / family / risk) — and add the **family + memify layers** (currently the endpoint only returns one patient's own facts with `SUPERSEDED_BY`/`SAME_SUBJECT`). **(2) Replace the free force layout** with a **structured temporal-lane layout** — x = time (`valid_from`), y = category swimlane — the research-backed clinical pattern, plus real interactivity (tooltips, filter, highlight, semantic-zoom labels). Keep `react-force-graph-2d` (already integrated, canvas, ample for our ~15–40-node graphs) but drive node positions ourselves; no heavy new graph library.

**Tech Stack:** FastAPI/Pydantic (graph DTO), React + TS + Tailwind, `react-force-graph-2d` (existing) with computed fixed positions, `d3-scale`/`d3-time` (tiny, for the time axis — or hand-rolled), pytest for the backend enrichment.

---

## Current state (audited from code + the screenshot)

- `GET /graph` (`routes_graph.py`) returns `GraphNode{id,label,subject,value,status,valid_from,valid_to,source,source_document,document_title}` and `GraphEdge{source,target,type: SUPERSEDED_BY|SAME_SUBJECT}` — **one patient only, no family, no category, no memify risk**.
- `MemoryGraph.tsx` maps nodes to `{id,label,color,dim,marker}` and edges to dashed/plain lines; `ForceCanvas.tsx` runs `react-force-graph-2d` with a **free force layout** (positions pinned only to avoid jitter on rewind).
- **Problems visible:** labels collide and overlap ("HbA1c 8.6%" over "HbA1c 8.9%"); no time order; no grouping; `SAME_SUBJECT` faint links make a web; no family; no hover detail; no filter; nodes are bare dots. It's technically a graph but not *legible*.

## Research-backed direction

Clinical-record visualization consistently uses **timeline + category lanes + semantic zoom + link-to-source**, and interactive graphs need **hover tooltips, highlight-connected-on-select, filtering, and zoom/fit** ([EHR-KG / JMIR](https://pmc.ncbi.nlm.nih.gov/articles/PMC11259764/), [clinical timeline scoping review](https://www.jmir.org/2022/10/e38041), [React graph viz best practices](https://cambridge-intelligence.com/blog/react-graph-visualization-library/), [KG viz insights](https://www.falkordb.com/blog/knowledge-graph-visualization-insights/)). Our graph is tiny, so the constraint is **readability, not scale** — which is why the fix is *layout + interactivity*, not a bigger rendering engine. (Library note: Cytoscape/Sigma are for 1k–100k-node analysis; overkill here and a full rewrite of the working rewind-pinning logic. Keep `react-force-graph-2d`.)

---

## Task 1: Enrich the graph node/edge DTO (backend)

**Files:**
- Modify: `backend/app/api/dto.py` (`GraphNode`, `GraphEdge`, `GraphResponse`)
- Test: `backend/tests/test_graph_viz.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graph_viz.py
"""Graph enrichment for the visualization upgrade."""
from datetime import date
from app.api import dto


def test_graphnode_has_category_and_grounding_fields():
    n = dto.GraphNode(
        id="1", label="Allergic to penicillin", subject="allergy", value="penicillin",
        status="active", valid_from=date(2021, 8, 6), category="Allergy",
        source="Dr. Adams", confidence=1.0, ontology_valid=True,
    )
    assert n.category == "Allergy"
    assert n.ontology_valid is True


def test_graphedge_supports_family_and_risk_types():
    dto.GraphEdge(source="a", target="b", type="RELATED_TO", label="father")
    dto.GraphEdge(source="a", target="r", type="RISK", label="cardiovascular")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -v`
Expected: FAIL — `GraphNode` has no `category`; `GraphEdge.type` is a Literal missing `RELATED_TO`/`RISK`.

- [ ] **Step 3: Extend the DTOs**

In `backend/app/api/dto.py`, extend `GraphNode` (add fields) and widen `GraphEdge.type`:

```python
class GraphNode(BaseModel):
    id: str
    label: str
    subject: str
    value: str
    status: str
    valid_from: date
    valid_to: Optional[date] = None
    source: str = "unknown"
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    # visualization layer (additive)
    category: str = "Other"          # FHIR resource_type → swimlane (Allergy/Medication/…)
    confidence: float = 1.0
    ontology_valid: Optional[bool] = None
    kind: Literal["fact", "relative", "risk"] = "fact"


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["SUPERSEDED_BY", "SAME_SUBJECT", "RELATED_TO", "RISK"]
    label: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/dto.py backend/tests/test_graph_viz.py
git commit -m "feat: enrich graph DTO (category, grounding, family/risk edges)"
```

---

## Task 2: Populate category + grounding, drop the noisy SAME_SUBJECT web (backend)

**Files:**
- Modify: `backend/app/api/routes_graph.py:39-85` (the `graph` route)
- Test: `backend/tests/test_graph_viz.py`

Rationale: in a category-laned layout, same-subject grouping is shown by the **lane**, so the `SAME_SUBJECT` edges are redundant clutter — keep the data available but default the visual to *supersession + family + risk* edges only.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_graph_viz.py
from app.api import routes_graph
from app.memory import ledger
from app.memory.schema import ClinicalFact


def test_graph_route_sets_category_from_resource_type(monkeypatch):
    f = ClinicalFact(patient_id="P0", subject="allergy", predicate="diagnosed",
                     value="penicillin", valid_from=date(2021, 8, 6),
                     resource_type="Allergy", source="Dr. Adams")
    f.ontology_valid = True
    monkeypatch.setattr(ledger, "all", lambda pid: [f])
    resp = routes_graph.graph(patient_id="P0")
    node = resp.nodes[0]
    assert node.category == "Allergy"
    assert node.ontology_valid is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -k category_from_resource -v`
Expected: FAIL — the route doesn't set `category`/`ontology_valid`.

- [ ] **Step 3: Populate the fields in the `graph` route**

In `routes_graph.py`, in the `graph()` node-building loop, add `category`, `confidence`, `ontology_valid`, `kind="fact"` to each `GraphNode(...)`:

```python
        GraphNode(
            id=f.id, label=f.label, subject=f.subject, value=f.value,
            status=_status_at(f, as_of), valid_from=f.valid_from, valid_to=f.valid_to,
            source=f.source, source_document=f.source_document,
            document_title=f.document_title,
            category=f.resource_type or "Other",
            confidence=f.confidence, ontology_valid=f.ontology_valid, kind="fact",
        )
```

Keep emitting `SUPERSEDED_BY` edges. Keep `SAME_SUBJECT` emission behind a query flag so the client can request it but it's off by default — change the route signature to accept `include_same_subject: bool = Query(False)` and only append `SAME_SUBJECT` edges when true.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes_graph.py backend/tests/test_graph_viz.py
git commit -m "feat: graph nodes carry category+grounding; SAME_SUBJECT opt-in"
```

---

## Task 3: Add the family + risk layers to the graph (backend)

**Files:**
- Modify: `backend/app/api/routes_graph.py` (the `graph` route)
- Test: `backend/tests/test_graph_viz.py`

Dependency: consumes `family_resolver.links_for` from the **family-auto-linkage plan**. If that module isn't present yet, guard the import so the graph degrades gracefully (no family layer) — this task can land before or after the family plan.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_graph_viz.py
def test_graph_includes_family_relatives(monkeypatch):
    f = ClinicalFact(patient_id="P020", subject="diagnosis", predicate="diagnosed",
                     value="anemia", valid_from=date(2024, 1, 1), resource_type="Condition")
    monkeypatch.setattr(ledger, "all", lambda pid: [f] if pid == "P020" else [])
    # one consented father link + the father is a patient named Rahul
    import app.api.routes_graph as rg
    monkeypatch.setattr(rg, "_family_links", lambda pid: [
        {"patient_id": "P020", "relative_id": "P010", "relation": "father", "consent": True}])
    monkeypatch.setattr(rg, "_patient_name", lambda pid: "Rahul Sharma" if pid == "P010" else pid)
    resp = rg.graph(patient_id="P020")
    rel_nodes = [n for n in resp.nodes if n.kind == "relative"]
    rel_edges = [e for e in resp.edges if e.type == "RELATED_TO"]
    assert rel_nodes and rel_nodes[0].label.startswith("Father")
    assert rel_edges and rel_edges[0].label == "father"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -k family_relatives -v`
Expected: FAIL — no relative nodes/edges + helpers missing.

- [ ] **Step 3: Add the family layer helpers + wiring**

In `routes_graph.py`, add guarded helpers near the top:

```python
def _family_links(patient_id: str) -> list[dict]:
    try:
        from app.intake import family_resolver
        return family_resolver.links_for(patient_id, consented_only=True)
    except Exception:  # family module not present yet — degrade gracefully
        return []


def _patient_name(patient_id: str) -> str:
    from app.memory import records
    p = records.get_patient(patient_id)
    return p["name"] if p else patient_id
```

At the end of `graph()` (before `return`), append a relative node + `RELATED_TO` edge per consented link, anchored to the patient's most-recent fact (or a synthetic patient node):

```python
    for link in _family_links(patient_id):
        rid = link["relative_id"]
        rel_node_id = f"rel:{rid}"
        nodes.append(GraphNode(
            id=rel_node_id, label=f"{link['relation'].title()} · {_patient_name(rid)}",
            subject="family", value=_patient_name(rid), status="active",
            valid_from=as_of, category="Family", kind="relative",
        ))
        # link the relative to the patient's earliest node (a stable anchor)
        if nodes:
            anchor = min((n for n in nodes if n.kind == "fact"),
                         key=lambda n: n.valid_from, default=None)
            if anchor:
                edges.append(GraphEdge(source=anchor.id, target=rel_node_id,
                                       type="RELATED_TO", label=link["relation"]))
```

(Optionally add a `RISK` edge from the memify risk card's contributing facts — a follow-up; the family layer is the priority.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes_graph.py backend/tests/test_graph_viz.py
git commit -m "feat: family relatives + edges in the graph (consent-gated, degrades safely)"
```

---

## Task 4: Structured temporal-lane layout (frontend — the core readability fix)

**Files:**
- Modify: `frontend/src/api/types.ts` (extend `GraphNode`/`GraphEdge`)
- Create: `frontend/src/lib/graphLayout.ts` (compute x=time, y=category-lane positions)
- Modify: `frontend/src/components/ForceCanvas.tsx` (consume fixed positions + lanes)
- Modify: `frontend/src/components/MemoryGraph.tsx` (pass category/kind, lane config)

Design: **x = time** (linear scale over `valid_from` range), **y = category swimlane** (fixed band per category, ordered Allergy · Condition · Medication · Lab · Family · Lifestyle · Other). Nodes get `fx`/`fy` from the layout; supersession edges run mostly horizontal within a lane (readable), family/risk edges cross lanes (visible). This removes label collisions because nodes are spread on a grid, not piled by force.

- [ ] **Step 1: Extend the frontend graph types**

In `frontend/src/api/types.ts`, add to `GraphNode`: `category?: string`, `confidence?: number`, `ontology_valid?: boolean | null`, `kind?: 'fact' | 'relative' | 'risk'`, `valid_from?: string`; to `GraphEdge`: `label?: string` and widen `type` to include `'RELATED_TO' | 'RISK'`.

- [ ] **Step 2: Create the layout helper**

```ts
// frontend/src/lib/graphLayout.ts
import type { GraphNode } from '@/api/types'

export const LANES = ['Allergy', 'Condition', 'Medication', 'LabResult', 'Vital', 'Family', 'Lifestyle', 'Other'] as const
export const LANE_LABEL: Record<string, string> = {
  Allergy: 'Allergies', Condition: 'Conditions', Medication: 'Medications',
  LabResult: 'Labs', Vital: 'Vitals', Family: 'Family', Lifestyle: 'Lifestyle', Other: 'Other',
}
const LANE_INDEX: Record<string, number> = Object.fromEntries(LANES.map((l, i) => [l, i]))

export interface Positioned { id: string; fx: number; fy: number; lane: number }

/** Compute x=time, y=lane positions in a normalized [0..W]x[0..H] space. Nodes in the
 * same lane + same date are nudged apart on x so labels never stack. */
export function layout(nodes: GraphNode[], W = 1000, H = 560): Map<string, Positioned> {
  const dates = nodes.map((n) => (n.valid_from ? Date.parse(n.valid_from) : NaN)).filter((d) => !isNaN(d))
  const min = Math.min(...dates), max = Math.max(...dates)
  const span = Math.max(1, max - min)
  const laneH = H / LANES.length
  const perDate = new Map<string, number>()
  const out = new Map<string, Positioned>()
  for (const n of nodes) {
    const lane = LANE_INDEX[n.category ?? 'Other'] ?? LANE_INDEX.Other
    const t = n.valid_from ? Date.parse(n.valid_from) : min
    const baseX = 60 + ((t - min) / span) * (W - 120)
    const key = `${lane}:${Math.round(baseX)}`
    const bump = perDate.get(key) ?? 0
    perDate.set(key, bump + 1)
    out.set(n.id, { id: n.id, lane, fx: baseX + bump * 26, fy: laneH * (lane + 0.5) })
  }
  return out
}
```

- [ ] **Step 3: Feed fixed positions + lane bands into the canvas**

In `MemoryGraph.tsx`, compute `const pos = layout(data?.nodes ?? [])` and pass each node's `fx`/`fy` + `category`/`kind` through to `ForceCanvas`. In `ForceCanvas.tsx`, when a node has `fx`/`fy` set, use them (already supported by react-force-graph — it honors `fx`/`fy`); disable the charge/link forces (set `d3Force('charge', null)` and rely on fixed positions) so the layout is the deterministic lane grid, not a force blob. Draw faint horizontal **lane bands + lane labels** on the left and light **time-axis gridlines/ticks** (year marks) in a background render pass (`onRenderFramePre`).

- [ ] **Step 4: Verify (preview)**

Run: `cd frontend && npm run build`, then open a patient's Timeline: facts are now laid out **left→right by date, grouped in labeled category lanes**, labels no longer overlap, supersession arrows read horizontally, family relatives appear in the Family lane linked across.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/lib/graphLayout.ts frontend/src/components/ForceCanvas.tsx frontend/src/components/MemoryGraph.tsx
git commit -m "feat: temporal category-lane layout for the memory graph"
```

---

## Task 5: Interactivity — hover tooltip, highlight-connected, semantic-zoom labels

**Files:**
- Modify: `frontend/src/components/ForceCanvas.tsx`
- Modify: `frontend/src/components/MemoryGraph.tsx`

- [ ] **Step 1: Hover tooltip**

Add `onNodeHover` to track the hovered node; render an HTML tooltip (absolutely positioned over the canvas) showing: label, category, date (+ valid_to if superseded), status, source, confidence, and a "✓ ontology-grounded" line when `ontology_valid`. (HTML tooltip is crisper than canvas text and matches the clinical-viz "detail on hover" pattern.)

- [ ] **Step 2: Highlight connected on select**

On node click (keep `openWhy`), also set a `selectedId`; in the canvas render, draw non-connected nodes/edges at low opacity and the selected node + its direct neighbors + connecting edges at full strength — the "explore connections" pattern from the research. Clicking empty space clears it.

- [ ] **Step 3: Semantic-zoom labels (kills residual clutter)**

Only draw a node's label when: it's hovered/selected/neighbor, OR the node is `active`, OR `globalScale > 1.4` (zoomed in). At low zoom show only active-fact labels; zooming in reveals the rest. This is the research-backed "semantic zoom" fix for label density.

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run build`; hover shows a rich tooltip; clicking a fact dims the rest and highlights its supersession/family chain; zooming in reveals more labels, out declutters.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ForceCanvas.tsx frontend/src/components/MemoryGraph.tsx
git commit -m "feat: graph tooltips, highlight-connected, semantic-zoom labels"
```

---

## Task 6: Legend, category filter, zoom controls, node styling by category/kind

**Files:**
- Create: `frontend/src/components/GraphLegend.tsx` (legend + category filter chips + zoom/fit buttons)
- Modify: `frontend/src/components/MemoryGraph.tsx` (filter state, category colors/icons, controls)

- [ ] **Step 1: Category color + icon map**

Give each category a distinct calm color + lucide icon (Allergy=ShieldAlert/red, Medication=Pill/teal, Condition=Stethoscope, Lab=FlaskConical, Family=Users, Lifestyle=HeartPulse, Vital=Activity). Relative nodes render as a person glyph; risk nodes as a warning glyph. Node fill = category color; superseded = greyed + ⊘ (keep existing).

- [ ] **Step 2: Legend + filter chips + controls**

`GraphLegend.tsx`: a compact panel showing each category swatch+icon as a **toggle chip** (click to hide/show that lane), the edge-type key (solid = replaced-by, line = family, dashed = risk), and **Fit / Zoom+ / Zoom−** buttons wired to `fgRef.zoomToFit()` / `zoom()`. Filtering hides a lane's nodes+edges (recompute the layout without them).

- [ ] **Step 3: Wire into MemoryGraph + MemoryMapPage**

Render `GraphLegend` over the canvas (top-right), pass the active-category set down to filter nodes before layout. Apply the same to `MemoryMapPage` (the full-screen `/memory` view) so both the tab and the full map get the upgrade.

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run build`; the graph shows a legend, category filter chips that hide/show lanes, and working zoom/fit controls; colors+icons make categories scannable.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GraphLegend.tsx frontend/src/components/MemoryGraph.tsx frontend/src/pages/MemoryMapPage.tsx
git commit -m "feat: graph legend, category filters, zoom controls, category styling"
```

---

## Task 7: Sync the Rewind slider with a moving time cursor

**Files:**
- Modify: `frontend/src/components/ForceCanvas.tsx` (draw a "now" line)
- Modify: `frontend/src/components/MemoryGraph.tsx` (pass the as-of x-position)

- [ ] **Step 1: Draw the time cursor**

Since x is now real time, map the Rewind `asOf` date to an x-position and draw a subtle vertical "as-of" line across the lanes in the background pass; facts to the right of it dim (future relative to the scrub point). This ties the existing time-scrubber to the new time-axis so rewinding reads as moving along the timeline.

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run build`; dragging Rewind moves the vertical cursor along the time axis and dims facts after that date — the "what did we know on this date" story is now spatially obvious.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ForceCanvas.tsx frontend/src/components/MemoryGraph.tsx
git commit -m "feat: rewind slider drives a time cursor on the graph axis"
```

---

## Task 8: Final verification (readability + acceptance)

**Files:** none

- [ ] **Step 1: Build + backend graph tests**

Run: `cd backend && python -m pytest tests/test_graph_viz.py -v` (green) and `cd frontend && npm run build` (clean).

- [ ] **Step 2: Readability acceptance (with the demo patient loaded)**

Confirm, in the running app on the hero patient:
1. Facts read left→right by date in labeled category lanes; **no overlapping labels**. ✅/❌
2. Supersession arrows are legible; family relatives appear and link across; (risk edge if built). ✅/❌
3. Hover shows source/date/status/grounding; clicking highlights the connected chain. ✅/❌
4. Category filter chips + zoom/fit work; Rewind moves the time cursor. ✅/❌
5. A non-technical viewer can explain the patient's history from the graph alone. ✅/❌

- [ ] **Step 3: Commit the pass marker**

```bash
git commit -m "test: graph visualization upgrade — readability acceptance walked" --allow-empty
```

---

## Options considered (and why not)

- **Switch to Cytoscape.js / Sigma.js:** built for 1k–100k-node analysis; our graphs are ~15–40 nodes, so they add a heavy dependency and a full rewrite of the working rewind-pinning logic for zero scale benefit. Rejected.
- **Pure timeline (no cross-links):** clearest for a single category but loses the *relationships* (supersession, family, risk) that are the point. The **temporal-lane graph** (this plan) keeps both — time legibility *and* edges — matching the EHR-KG literature.
- **Keep force layout, just fix labels:** label collision is a symptom; the root cause is the unstructured layout. Structured lanes fix both at once.

## Self-Review

- **Spec coverage:** "understandable/relevant" → temporal-lane layout (Task 4) + legend/filters (Task 6); "include family" → Tasks 1/3 (data) + 4 (Family lane) + 6 (styling); "needs information" → enriched DTO (Task 1) + hover tooltip (Task 5); "interactive" → Tasks 5 (hover/highlight/semantic-zoom), 6 (filter/zoom), 7 (rewind cursor); "properly presented" → legend, lane labels, time axis, category color/icon.
- **Placeholder scan:** backend tasks (1–3) ship complete code + tests. Frontend tasks (4–7) give the exact new file (`graphLayout.ts`), the exact layout algorithm, and precise change points; the canvas-render edits are described against the exact `nodeCanvasObject`/`onRenderFramePre` hooks in the file just read — the "read the current render pass, then add" steps are the sanctioned pattern for canvas drawing where pixel code adapts to the existing draw loop.
- **Type consistency:** `GraphNode` gains `category/confidence/ontology_valid/kind/valid_from` on both backend (Task 1) and frontend (Task 4); `GraphEdge.type` widened to include `RELATED_TO`/`RISK` on both ends; `layout()`'s `LANES`/`LANE_INDEX` keys use the FHIR `resource_type` values the backend puts in `category`; `_family_links`/`links_for(consented_only=)` matches the family-auto-linkage plan's resolver signature.
- **Dependency note:** Task 3's family layer consumes the family-auto-linkage plan's `family_resolver`; it's import-guarded so this plan is safe to execute before *or* after that one (degrades to no-family gracefully).
```
