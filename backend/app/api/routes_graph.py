"""
Graph + provenance + health routes.

/graph         Fact-Timeline from the authoritative ledger, statuses computed
               at `as_of` (drives the time-scrubber).
/graph/cognee  Raw Cognee knowledge graph (the "depth" tab).
/why           Provenance trace for one fact (the supersession chain + reason).
/health        Liveness of ledger + Cognee.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.dto import (
    CogneeGraphResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
    HealthResponse,
    WhyResponse,
)
from app.checks.followup import _RISING_BAD
from app.memory import cognee_client, ledger, ontology
from app.memory.schema import ClinicalFact

router = APIRouter(tags=["graph"])


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


def _status_at(fact, as_of: date) -> str:
    """Active iff valid_from <= as_of < valid_to (or no valid_to); else superseded."""
    if fact.valid_from <= as_of and (fact.valid_to is None or fact.valid_to > as_of):
        return "active"
    return "superseded"


@router.get("/graph", response_model=GraphResponse)
def graph(
    patient_id: str = Query("P001"),
    as_of: Optional[date] = Query(None),
    include_same_subject: bool = Query(False),
) -> GraphResponse:
    """Ledger fact-timeline snapshot with statuses computed at `as_of`."""
    as_of = as_of if isinstance(as_of, date) else date.today()
    include_same_subject = include_same_subject is True
    facts = [f for f in ledger.all(patient_id) if f.status != "retracted"]

    nodes: List[GraphNode] = [
        GraphNode(
            id=f.id,
            label=f.label,
            subject=f.subject,
            value=f.value,
            status=_status_at(f, as_of),
            valid_from=f.valid_from,
            valid_to=f.valid_to,
            source=f.source,
            source_document=f.source_document,
            document_title=f.document_title,
            category=f.resource_type or "Other",
            confidence=f.confidence,
            ontology_valid=f.ontology_valid,
            kind="fact",
        )
        for f in facts
    ]

    edges: List[GraphEdge] = []
    superseded_pairs = set()
    for f in facts:
        if f.superseded_by:
            edges.append(
                GraphEdge(source=f.id, target=f.superseded_by, type="SUPERSEDED_BY")
            )
            superseded_pairs.add((f.id, f.superseded_by))

    # SAME_SUBJECT edges between time-adjacent facts of one subject that are not
    # already linked by a supersession. In the category-laned layout the lane
    # already groups a subject, so these are redundant clutter — opt-in only.
    if include_same_subject:
        by_subject: dict = defaultdict(list)
        for f in facts:
            by_subject[f.subject].append(f)
        for group in by_subject.values():
            group.sort(key=lambda x: x.valid_from)
            for a, b in zip(group, group[1:]):
                if (a.id, b.id) in superseded_pairs or (b.id, a.id) in superseded_pairs:
                    continue
                edges.append(GraphEdge(source=a.id, target=b.id, type="SAME_SUBJECT"))

    # Family layer: a relative node + RELATED_TO edge per consented link, anchored
    # to the patient's earliest fact (a stable anchor). Degrades to no-op when the
    # family module isn't present or there are no consented links.
    anchor = min(
        (n for n in nodes if n.kind == "fact"),
        key=lambda n: n.valid_from,
        default=None,
    )
    for link in _family_links(patient_id):
        rid = link["relative_id"]
        rel_node_id = f"rel:{rid}"
        nodes.append(
            GraphNode(
                id=rel_node_id,
                label=f"{link['relation'].title()} · {_patient_name(rid)}",
                subject="family",
                value=_patient_name(rid),
                status="active",
                valid_from=as_of,
                category="Family",
                kind="relative",
            )
        )
        if anchor:
            edges.append(
                GraphEdge(
                    source=anchor.id,
                    target=rel_node_id,
                    type="RELATED_TO",
                    label=link["relation"],
                )
            )

    return GraphResponse(as_of=as_of, nodes=nodes, edges=edges)


# --- raw Cognee graph -----------------------------------------------------
def _jsonable(v: Any) -> Any:
    """Coerce a Cognee property value into something JSON-serializable."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


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
    return {
        "id": str(nid),
        "label": str(label),
        "type": str(props.get("type") or props.get("node_type") or ""),
        "properties": {k: _jsonable(v) for k, v in props.items()},
    }


def _map_cognee_edge(e: Any) -> dict:
    src = tgt = ""
    label = ""
    if isinstance(e, (list, tuple)):
        if len(e) >= 1:
            src = e[0]
        if len(e) >= 2:
            tgt = e[1]
        if len(e) >= 3:
            rel = e[2]
            if isinstance(rel, dict):
                label = rel.get("relationship_name") or rel.get("type") or ""
            else:
                label = rel
    elif isinstance(e, dict):
        src = e.get("source") or e.get("source_node_id") or ""
        tgt = e.get("target") or e.get("target_node_id") or ""
        label = e.get("relationship_name") or e.get("type") or e.get("label") or ""
    return {"source": str(src), "target": str(tgt), "type": str(label)}


@router.get("/graph/cognee", response_model=CogneeGraphResponse)
async def graph_cognee(patient_id: str = Query("P001")) -> CogneeGraphResponse:
    """Raw Cognee knowledge graph for the depth tab."""
    try:
        nodes, edges = await cognee_client.get_graph_data()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(503, f"cognee graph unavailable: {type(exc).__name__}: {exc}")

    return CogneeGraphResponse(
        nodes=[_map_cognee_node(n) for n in (nodes or [])],
        edges=[_map_cognee_edge(e) for e in (edges or [])],
    )


def _trend_value(f: ClinicalFact) -> Optional[float]:
    try:
        return float(f.attributes.get("value"))
    except (TypeError, ValueError, AttributeError):
        return None


def _trend_reason(fact: ClinicalFact, siblings: List[ClinicalFact]) -> str:
    """Clinical-language trend narrative — deliberately mirrors followup.py's
    Pre-Visit-brief card wording (same _RISING_BAD direction knowledge) so a
    doctor reads the SAME verdict here as on the brief, never a system-internal
    'nothing replaced this' sentence that answers a question nobody asked."""
    valued = [(f2, v) for f2 in siblings if (v := _trend_value(f2)) is not None]
    if len(valued) < 2:
        return f"{fact.label} has no other dated readings on record to compare against."
    valued.sort(key=lambda fv: fv[0].valid_from)
    analyte = ontology._norm(fact.attributes.get("analyte") or fact.subject)
    first, last = valued[0][1], valued[-1][1]
    seq = " → ".join(f"{v:g}" for _, v in valued)
    start_date, end_date = valued[0][0].valid_from.isoformat(), valued[-1][0].valid_from.isoformat()
    if first == last:
        return f"{analyte.upper()} has stayed steady at {last:g} across {len(valued)} readings ({start_date} → {end_date})."
    rising = last > first
    wrong_way = (rising and analyte in _RISING_BAD) or (not rising and analyte not in _RISING_BAD)
    direction = "rising" if rising else "falling"
    verdict = "trending the wrong way despite prior results" if wrong_way else "trending in the right direction"
    return f"{analyte.upper()} is {direction}: {seq} ({start_date} → {end_date}) — {verdict}."


# --- provenance -----------------------------------------------------------
@router.get("/why", response_model=WhyResponse)
def why(fact_id: str = Query(...)) -> WhyResponse:
    """Why did this fact change? -> superseding event + reason + source + date.

    Not every fact fits the supersede model: a lab reading never invalidates
    the last one (each measurement is independently true), so it's never
    superseded — but "nothing has replaced it" reads as wrong next to a
    visibly rising HbA1c. When there's no supersession, look for other ACTIVE
    facts sharing this subject and surface them as a CLINICAL trend instead —
    what a doctor actually asked ("is this getting worse?"), not what the
    reconciliation engine did internally.
    """
    fact = ledger.get(fact_id)
    if fact is None:
        raise HTTPException(404, f"fact not found: {fact_id}")

    chain = ledger.chain(fact_id)
    sup = ledger.get(fact.superseded_by) if fact.superseded_by else None

    trend: list = []
    trend_reason = ""
    if sup is None:
        siblings = [
            f for f in ledger.query_all(fact.patient_id, fact.subject)
            if f.status == "active"
        ]
        if len(siblings) > 1:
            trend = siblings
            trend_reason = _trend_reason(fact, siblings)

    return WhyResponse(
        fact=fact,
        superseded_by=sup,
        reason=fact.reason or (sup.reason if sup else "") or "",
        source=(sup.source if sup else fact.source),
        date=(sup.valid_from if sup else fact.valid_from),
        chain=chain,
        trend=trend,
        trend_reason=trend_reason,
    )


# --- health ---------------------------------------------------------------
@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    ledger_status = "up"
    try:
        ledger.init()
        ledger.all("P001")
    except Exception:  # pragma: no cover - defensive
        ledger_status = "down"

    cognee_status = "up"
    try:
        from cognee.infrastructure.databases.graph import get_graph_engine  # noqa: F401
    except Exception:  # pragma: no cover - defensive
        cognee_status = "down"

    return HealthResponse(
        ok=(ledger_status == "up" and cognee_status == "up"),
        cognee=cognee_status,
        ledger=ledger_status,
    )
