"""
The ONLY module that talks to Cognee (the seam).

Everything Cognee-related goes through here so the rest of the engine stays
decoupled and testable. Cognee provides the semantic + temporal memory; the
ledger (ledger.py) remains the authoritative status store.

`import app.config` first (done here) so Vertex/embeddings/storage are wired
before any Cognee call.
"""

from __future__ import annotations

from typing import Any, List, Optional

import app.config as config  # noqa: F401  (wires Cognee on import — must be first)
import cognee

from app.memory import ontology

try:
    from cognee.api.v1.search import SearchType
except Exception:  # pragma: no cover - version fallback
    from cognee import SearchType  # type: ignore

# Per-patient datasets keep each chart's memory isolated (real multi-patient).
# Legacy single-patient names kept as defaults for back-compat.
#
# ponytail: isolation here is by per-patient dataset NAME + the closure-bound tool
# scoping in agent/tools.py (the model never supplies a patient_id, so it cannot
# reach another patient's dataset). Cognee's ACL layer (create_authorized_dataset +
# ENABLE_BACKEND_ACCESS_CONTROL) is the heavier "enforced-by-permissions" upgrade,
# but in cognee 1.2.2 it requires a User principal and switches dataset addressing
# to IDs + an auth context, which would break the proven name-based seed/ask flow.
# Upgrade path: introduce a default User, route every add/recall through
# create_authorized_dataset + dataset IDs, and flip the env flag — do this only
# once per-clinician auth is a real feature.
DATASET = "total_recall"
NAIVE_DATASET = "naive_baseline"


def dataset_for(patient_id: str) -> str:
    """Smart (self-healed, temporal) memory dataset for one patient."""
    return f"tr_{patient_id.strip().lower()}"


def naive_dataset_for(patient_id: str) -> str:
    """Frozen 'villain' dataset for one patient (no healing, no temporal)."""
    return f"naive_{patient_id.strip().lower()}"


async def seed_reset() -> None:
    """Wipe all Cognee data + system metadata (fresh demo run)."""
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)


async def add_fact(fact) -> Optional[str]:
    """
    Push a fact's natural-language assertion into Cognee.

    Accepts a `ClinicalFact` (uses .raw_text, falling back to a synthesized
    sentence) or a raw string. Returns the Cognee `data_id` of the added
    assertion (so it can be forgotten precisely later), or None.
    """
    if isinstance(fact, str):
        text = fact
        ds = DATASET
    else:
        text = fact.raw_text or _synthesize(fact)
        ds = dataset_for(fact.patient_id)
    result = await cognee.add(text, dataset_name=ds)
    return _extract_data_id(result)


def _extract_data_id(result) -> Optional[str]:
    """Pull the data_id out of cognee.add's PipelineRunCompleted result."""
    try:
        info = getattr(result, "data_ingestion_info", None) or []
        if info and isinstance(info[0], dict) and info[0].get("data_id"):
            return str(info[0]["data_id"])
    except Exception:  # pragma: no cover - defensive
        pass
    return None


def _synthesize(fact) -> str:
    """Fallback sentence when a fact carries no raw_text."""
    return (
        f"On {fact.valid_from.isoformat()}, patient {fact.patient_id} "
        f"{fact.predicate} {fact.subject}: {fact.value} (source {fact.source})."
    )


async def cognify(
    patient_id: str,
    temporal: bool = True,
    chunk_size: int = 4096,
    data_per_batch: int = 20,
    chunks_per_batch: int = 100,
) -> None:
    """Build/refresh the temporal knowledge graph for the patient's dataset,
    grounded in the medical ontology (§4) so Cognee validates extracted entities
    and attaches drug-class / monitoring / familial-risk edges from our vocabulary.

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


# --- ontology grounding (§4) ----------------------------------------------
# The resolver is Cognee's own RDFLibOntologyResolver over the OWL we generate from
# app/memory/ontology.py — so the per-fact ontology_valid flag and the graph-level
# grounding inside cognify() use the SAME vocabulary. Built once, lazily.
_resolver: Any = None
_resolver_built = False


def _ontology_resolver():
    global _resolver, _resolver_built
    if _resolver_built:
        return _resolver
    _resolver_built = True
    try:
        from cognee.modules.ontology.rdf_xml.RDFLibOntologyResolver import RDFLibOntologyResolver
        from cognee.modules.ontology.matching_strategies import FuzzyMatchingStrategy

        _resolver = RDFLibOntologyResolver(
            ontology_file=ontology.owl_path(), matching_strategy=FuzzyMatchingStrategy()
        )
    except Exception:  # pragma: no cover - degrade to local grounding
        _resolver = None
    return _resolver


def _ontology_config():
    """Cognee cognify config that attaches our ontology, or None to run ungrounded."""
    resolver = _ontology_resolver()
    if resolver is None:
        return None
    try:
        from cognee.modules.ontology.ontology_config import Config, OntologyConfig

        return Config(ontology_config=OntologyConfig(ontology_resolver=resolver))
    except Exception:  # pragma: no cover
        return None


def _grounding_candidates(fact) -> List[str]:
    """Clinical entity strings to validate for a fact: the typed attribute when
    present (drug / substance / analyte / condition), the raw value, and their
    word tokens (so 'amlodipine 5mg' still grounds on 'amlodipine')."""
    attrs = getattr(fact, "attributes", None) or {}
    rt = getattr(fact, "resource_type", None)
    primary = None
    if rt in ("Medication", "Allergy"):
        primary = attrs.get("drug") or attrs.get("substance")
    elif rt == "LabResult":
        primary = attrs.get("analyte")
    elif rt in ("Condition", "FamilyHistory"):
        primary = attrs.get("condition") or attrs.get("name")
    value = getattr(fact, "value", "") or ""
    cands: List[str] = []
    for s in (primary, value):
        s = (s or "").strip()
        if s and s not in cands:
            cands.append(s)
    for s in list(cands):
        for tok in s.replace("/", " ").split():
            if tok and tok not in cands:
                cands.append(tok)
    return cands


def ground_fact(fact) -> Optional[bool]:
    """Set and return `fact.ontology_valid`: True if the fact's clinical entity is
    grounded in the medical ontology, False if not. Uses Cognee's RDF resolver
    (authoritative when loaded); falls back to the local table only if the resolver
    is unavailable. Returns None when there's no entity to check. Mutates `fact`
    but does not persist — the caller owns the ledger write."""
    cands = _grounding_candidates(fact)
    if not cands:
        return None
    resolver = _ontology_resolver()
    grounded = False
    if resolver is not None:
        try:
            for c in cands:
                if resolver.find_closest_match(c, "individuals") or resolver.find_closest_match(
                    c, "classes"
                ):
                    grounded = True
                    break
        except Exception:  # pragma: no cover - resolver hiccup -> local fallback
            resolver = None
    if resolver is None:
        grounded = any(ontology.is_known(c) for c in cands)
    fact.ontology_valid = grounded
    return grounded


async def sync_fact(fact, healed: bool = False) -> None:
    """Push ONE new/healed fact into Cognee (semantic + temporal graph).

    This is the heavy part of an ingest — add + temporal cognify (+ improve on a
    heal) makes 2 LLM calls + embeddings, ~20s. The ledger is authoritative and
    already updated, so the agent calls this in the BACKGROUND off the chat
    response path (the engine's persist node does the same work synchronously for
    the document-upload path, where a spinner is expected). Best-effort: never
    raises — a Cognee lag must not break a turn (§2.6.F honest degradation)."""
    try:
        data_id = await add_fact(fact)
        if data_id:
            from app.memory import ledger
            f = ledger.get(fact.id)
            if f is not None:
                f.cognee_data_id = data_id  # enables targeted forget later
                ledger.upsert(f)
        await cognify(fact.patient_id, temporal=True)
        if healed:
            try:
                await improve(fact.patient_id)
            except Exception:  # pragma: no cover - best-effort
                pass
    except Exception:  # pragma: no cover - Cognee lag must never break a turn
        pass


async def memify_risk_edges(patient_id: str) -> None:
    """Enrichment pass (§4 memify): materialize cross-fact RISK relationships into
    the patient's graph so combined-risk reasoning has a real node/edge to show in
    the Memory-Map — the relationship-graph hero.

    Deterministic fallback FIRST (compute the risk edges from the ledger via the
    checks engine and add them as a natural-language assertion — this always works
    and is what the card logic already uses, §12), then a best-effort native
    `cognee.memify` enrichment over the built graph. Never raises: a Cognee lag
    must not break a turn (mirrors sync_fact's honest-degradation contract)."""
    added = False
    try:
        from app.checks import risk as risk_check

        for card in risk_check.run(patient_id):
            contributors = "; ".join(c.label for c in card.source) or "the patient's records"
            text = (
                f"Risk synthesis for patient {patient_id}: {card.summary}. "
                f"{card.detail} Derived from: {contributors}."
            )
            await cognee.add(text, dataset_name=dataset_for(patient_id))
            added = True
        if added:
            await cognify(patient_id, temporal=True)
    except Exception:  # pragma: no cover - fallback edge write is best-effort
        pass
    try:
        await cognee.memify(dataset=dataset_for(patient_id))
    except Exception:  # pragma: no cover - native memify optional
        pass


async def add_naive(fact) -> None:
    """Add a fact's assertion to the never-healed naive dataset (villain memory)."""
    text = fact if isinstance(fact, str) else (fact.raw_text or _synthesize(fact))
    ds = NAIVE_DATASET if isinstance(fact, str) else naive_dataset_for(fact.patient_id)
    await cognee.add(text, dataset_name=ds)


async def cognify_naive(patient_id: str) -> None:
    """Cognify the patient's naive dataset (no temporal — deliberately dumb)."""
    await cognee.cognify(datasets=[naive_dataset_for(patient_id)], temporal_cognify=False)


async def recall(
    query_text: str,
    query_type=None,
    top_k: int = 10,
    node_set: Optional[List[str]] = None,
    dataset: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> Any:
    """
    Query Cognee memory. Defaults to TEMPORAL over the patient's smart dataset.
    Pass `dataset=naive_dataset_for(pid)` for the naive baseline.
    """
    qt = query_type if query_type is not None else SearchType.TEMPORAL
    ds = dataset or (dataset_for(patient_id) if patient_id else DATASET)
    try:
        return await cognee.recall(
            query_text=query_text, query_type=qt, datasets=[ds], top_k=top_k
        )
    except AttributeError:  # pragma: no cover - legacy API
        return await cognee.search(query_text, query_type=qt, datasets=[ds], top_k=top_k)


def _entry_text(entry: Any) -> Optional[str]:
    """Best-effort: pull the human-readable answer text out of one recall entry."""
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry.strip() or None
    text = getattr(entry, "text", None)
    if text:
        return str(text).strip() or None
    # dict-shaped fallback
    if isinstance(entry, dict):
        for k in ("text", "answer", "content"):
            if entry.get(k):
                return str(entry[k]).strip()
    return None


def _entry_raw(entry: Any) -> Any:
    """JSON-serializable view of one entry for the `raw` debug field."""
    if isinstance(entry, str):
        return {"text": entry}
    out = {
        "text": _entry_text(entry),
        "search_type": getattr(getattr(entry, "search_type", None), "name", None)
        or getattr(entry, "search_type", None),
        "source": getattr(entry, "source", None),
    }
    return {k: v for k, v in out.items() if v is not None} or {"repr": str(entry)}


def _is_no_dataset(exc: Exception) -> bool:
    """True for Cognee's 'no datasets / not found' (empty memory for a patient)."""
    name = type(exc).__name__
    msg = str(exc).lower()
    return "DatasetNotFound" in name or "no datasets" in msg or "not found" in msg


async def recall_answer(
    query_text: str,
    query_type=None,
    top_k: int = 10,
    node_set: Optional[List[str]] = None,
    dataset: Optional[str] = None,
    patient_id: Optional[str] = None,
):
    """
    Run a recall and return `(answer_text, raw)`. If the patient's memory is empty
    (no dataset yet), answer gracefully instead of 500ing.
    """
    try:
        res = await recall(
            query_text, query_type=query_type, top_k=top_k, node_set=node_set,
            dataset=dataset, patient_id=patient_id,
        )
    except Exception as exc:
        if _is_no_dataset(exc):
            return (
                "No records have been added to this patient's memory yet — "
                "ingest or upload a record to begin.",
                [{"note": "empty_memory"}],
            )
        raise
    entries = res if isinstance(res, (list, tuple)) else [res]
    texts = [t for t in (_entry_text(e) for e in entries) if t]
    answer = "\n".join(texts) if texts else ""
    raw = [_entry_raw(e) for e in entries]
    return answer, raw


async def neighbors(query_text: str, top_k: int = 5, patient_id: Optional[str] = None) -> List[str]:
    """
    Fetch semantically-related memory snippets (graph/chunk neighbors) to give
    the judge extra background context. Best-effort: returns [] on any failure
    so it can never break an ingest. Used as CONTEXT ONLY — the authoritative
    judge candidate set stays ledger-based and deterministic.
    """
    try:
        res = await recall(query_text, query_type=SearchType.CHUNKS, top_k=top_k, patient_id=patient_id)
    except Exception:  # pragma: no cover - defensive
        return []
    out: List[str] = []
    for entry in res or []:
        text = getattr(entry, "text", None)
        if text:
            out.append(str(text).strip())
    return out


async def improve(patient_id: str, node_name: Optional[List[str]] = None) -> Any:
    """
    Light memory-improvement pass over the patient's dataset (Cognee lifecycle op).
    Called after a heal so the knowledge graph reflects the corrected truth.
    """
    return await cognee.improve(dataset=dataset_for(patient_id), node_name=node_name)


async def forget(*, dataset: Optional[str] = None, everything: bool = False) -> dict:
    """
    Forget memory by dataset / everything scope.
    """
    return await cognee.forget(dataset=dataset or DATASET, everything=everything)


async def forget_fact(data_id: str, patient_id: str) -> dict:
    """
    Forget ONE specific assertion by its Cognee `data_id` from the patient's
    dataset. RESERVED for facts entered in ERROR (truly invalid) — NOT for
    supersession (superseded facts are retained for temporal recall).
    """
    import uuid as _uuid

    did = data_id if isinstance(data_id, _uuid.UUID) else _uuid.UUID(str(data_id))
    return await cognee.forget(data_id=did, dataset=dataset_for(patient_id))


async def get_graph_data() -> Any:
    """
    Return the raw Cognee knowledge graph (nodes, edges) for visualization.
    Used by later phases (raw Cognee graph view next to the ledger timeline).
    """
    from cognee.infrastructure.databases.graph import get_graph_engine

    engine = await get_graph_engine()
    return await engine.get_graph_data()


# --- family graph (Dedup DataPoints, §A.3) --------------------------------
FAMILY_DATASET = "family_graph"


async def _add_data_points(points, **kwargs):
    """Seam over Cognee's add_data_points (import kept local so a version change
    is one edit, and tests can monkeypatch this without importing cognee)."""
    from cognee.tasks.storage.add_data_points import add_data_points
    return await add_data_points(points, **kwargs)


def _family_datapoint_class():
    """Build the FamilyMember DataPoint class lazily (import-safe)."""
    from typing import Optional as _Opt
    from typing import Annotated
    from cognee.infrastructure.engine import DataPoint, Dedup, Embeddable

    class FamilyMember(DataPoint):
        mrn: Annotated[str, Dedup()]           # identity → same person = one node across charts
        name: Annotated[str, Embeddable()]
        patient_id: str = ""
        parent: "_Opt[FamilyMember]" = None    # typed ref → edge child --parent--> parent

    FamilyMember.model_rebuild()
    return FamilyMember


async def add_family_members(members: list) -> None:
    """Materialize kinship into the Cognee graph via Dedup DataPoints. Best-effort:
    the JSON link store (family_resolver) is authoritative; this is the graph layer
    for the Memory Map. `members` items: {patient_id, name, mrn, parent_mrn}."""
    try:
        FamilyMember = _family_datapoint_class()
        by_mrn: dict = {}
        for m in members:
            by_mrn[m["mrn"]] = FamilyMember(
                mrn=m["mrn"], name=m.get("name", ""), patient_id=m.get("patient_id", ""),
            )
        for m in members:
            pm = m.get("parent_mrn")
            if pm and pm in by_mrn:
                by_mrn[m["mrn"]].parent = by_mrn[pm]
        await _add_data_points(list(by_mrn.values()), dataset_name=FAMILY_DATASET)
    except Exception:  # pragma: no cover - graph is best-effort; JSON store is truth
        pass
