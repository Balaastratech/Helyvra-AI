"""
Graph node functions.

Flow:
  START -> recall_related -> (judge | store_new)
        -> judge -> {reconcile_supersede | reconcile_contradict | store_new | reinforce}
        -> persist -> END

The ledger is mutated inside the reconcile/store/reinforce nodes (each owns its
specific status logic). `persist` then syncs the authoritative truth into Cognee.
"""

from __future__ import annotations

from app.engine.state import TRState
from app.memory import cognee_client, ledger, ontology
from app.engine import judge as judge_mod


def _log(state: TRState, msg: str) -> list:
    actions = list(state.get("actions") or [])
    actions.append(msg)
    return actions


def _try_dynamic_ground(fact) -> bool:
    """Fallback when both the static ontology AND Cognee's OWL resolver miss:
    ask the LLM to classify into an EXISTING category (never invents a new
    one), remember it, and regenerate the OWL export so Cognee's own
    grounding learns it too. Best-effort — a miss here just leaves
    ontology_valid False, it never breaks the ingest.

    Scoped to Medication and FamilyHistory: these are the two places a
    vocabulary gap silently breaks a SAFETY check (an unrecognized drug can't
    be checked for allergy cross-reactivity; an unrecognized family condition
    can't feed the hereditary-risk check) — Condition/LabResult misses are
    lower-stakes and stay on the static table only.
    """
    from app.memory import ontology_classify  # local: only imported when needed

    attrs = fact.attributes or {}
    try:
        if fact.resource_type == "Medication":
            drug = attrs.get("drug") or fact.value
            klass = ontology_classify.classify_drug(drug)
            if klass and ontology.remember_drug_class(drug, klass):
                ontology.build_owl()
                cognee_client.invalidate_ontology_resolver()
                return True
        elif fact.resource_type == "FamilyHistory":
            condition = attrs.get("condition") or fact.value
            category = ontology_classify.classify_family_risk(condition)
            if category and ontology.remember_family_risk(condition, category):
                ontology.build_owl()
                cognee_client.invalidate_ontology_resolver()
                return True
    except Exception:  # pragma: no cover - best-effort, never breaks ingest
        pass
    return False


# --- recall ---------------------------------------------------------------
async def recall_related(state: TRState) -> TRState:
    """Fetch the active, same-subject candidate set from the ledger (+ optional
    Cognee neighbor snippets as judge background context)."""
    new = state["new_fact"]
    related = ledger.query_active(new.patient_id, new.subject)
    actions = _log(
        state,
        f"recall: {len(related)} active '{new.subject}' fact(s) for {new.patient_id}.",
    )
    out: TRState = {"related": related, "actions": actions}
    if not related:
        # Dedupe gate: nothing to compare against -> NEW without an LLM call.
        out["classification"] = "NEW"
        out["target_fact_id"] = None
        out["reason"] = "No prior active fact for this subject."
        out["confidence"] = new.confidence
        out["actions"] = _log({"actions": actions}, "gate: no collision -> NEW (no judge call).")
        return out

    # NOTE: we intentionally do NOT pull Cognee "neighbor" snippets here. The
    # judge's candidate set is the ledger (authoritative + deterministic), and the
    # extra recall fired a noisy DatasetNotFoundError on a patient's first ingest
    # (the dataset doesn't exist until `persist` creates it). Dropping it removes a
    # wasted Cognee call and the scary log with no effect on classification.
    return out


def route_after_recall(state: TRState) -> str:
    """If recall already decided NEW (empty candidates), skip the judge."""
    return "store_new" if not state.get("related") else "judge"


# --- judge ----------------------------------------------------------------
def judge_node(state: TRState) -> TRState:
    """Run the deterministic Vertex judge on a real subject collision."""
    new = state["new_fact"]
    verdict = judge_mod.classify(new, state["related"], context=state.get("semantic_context"))
    actions = _log(
        state,
        f"judge: {verdict.classification} "
        f"(target={verdict.target_fact_id[:8] if verdict.target_fact_id else None}, "
        f"conf={verdict.confidence:.2f}) — {verdict.reason}",
    )
    return {
        "classification": verdict.classification,
        "target_fact_id": verdict.target_fact_id,
        "reason": verdict.reason,
        "confidence": verdict.confidence,
        "actions": actions,
    }


def route_after_judge(state: TRState) -> str:
    return {
        "SUPERSEDES": "reconcile_supersede",
        "CONTRADICTS": "reconcile_contradict",
        "CONSISTENT": "reinforce",
        "NEW": "store_new",
    }[state["classification"]]


# --- reconcile / store / reinforce ----------------------------------------
def reconcile_supersede(state: TRState) -> TRState:
    """Old fact becomes superseded; new fact becomes the active truth."""
    new = state["new_fact"]
    reason = state.get("reason") or "Superseded by newer fact."
    old = ledger.get(state["target_fact_id"])

    new.status = "active"
    new.confidence = state.get("confidence", new.confidence)
    new.reason = reason

    if old is not None:
        old.status = "superseded"
        old.valid_to = new.valid_from
        old.superseded_by = new.id
        old.reason = reason
        ledger.upsert(old, new)
        msg = (
            f"supersede: [{old.id[:8]}] {old.value} -> [{new.id[:8]}] {new.value} "
            f"(old.valid_to={new.valid_from.isoformat()}, status=superseded)."
        )
    else:
        ledger.upsert(new)
        msg = f"supersede: target missing; stored [{new.id[:8]}] {new.value} as active."
    return {"actions": _log(state, msg)}


def reconcile_contradict(state: TRState) -> TRState:
    """No clear winner: keep BOTH, flag both contested, lower confidence."""
    new = state["new_fact"]
    reason = state.get("reason") or "Conflicting facts; no clear winner."
    old = ledger.get(state["target_fact_id"])

    new.status = "contested"
    new.confidence = min(new.confidence, 0.5)
    new.reason = reason

    if old is not None:
        old.status = "contested"
        old.confidence = min(old.confidence, 0.5)
        old.reason = reason
        ledger.upsert(old, new)
        msg = (
            f"contradict: [{old.id[:8]}] vs [{new.id[:8]}] both flagged contested "
            f"for review — {reason}"
        )
    else:
        ledger.upsert(new)
        msg = f"contradict: target missing; stored [{new.id[:8]}] as contested."
    return {"actions": _log(state, msg)}


def store_new(state: TRState) -> TRState:
    """Additive fact: just store it active."""
    new = state["new_fact"]
    new.status = "active"
    new.confidence = state.get("confidence", new.confidence)
    ledger.upsert(new)
    return {"actions": _log(state, f"store_new: [{new.id[:8]}] {new.value} active.")}


def reinforce(state: TRState) -> TRState:
    """Restated fact: bump the existing fact's confidence; drop the duplicate."""
    target = ledger.get(state.get("target_fact_id")) if state.get("target_fact_id") else None
    if target is not None:
        target.confidence = min(1.0, round(target.confidence + 0.05, 4))
        ledger.upsert(target)
        msg = f"reinforce: [{target.id[:8]}] confidence -> {target.confidence:.2f}."
    else:
        msg = "reinforce: no target; nothing changed."
    return {"actions": _log(state, msg)}


# --- persist (Cognee sync) ------------------------------------------------
async def persist(state: TRState) -> TRState:
    """
    Sync the authoritative new truth into Cognee (semantic + temporal memory):
      1. Add the new fact's assertion (skip for CONSISTENT — it's a duplicate)
         and capture its Cognee data_id back onto the ledger row.
      2. cognify(temporal) + a light improve() pass after a heal.
    Skipped entirely when cognee_sync is disabled (tests).

    NOTE on supersession (ARCHITECTURE.md "never hard-delete on supersession"):
    we DO NOT forget the superseded fact. Cognee keeps BOTH the old and new dated
    assertions so `temporal_cognify` retains validity-over-time — the smart memory
    can still answer past-tense questions correctly ("the patient WAS allergic
    until it was cleared on 2026-03-02"), which powers the time-scrubber and the
    "evergreen memory" thesis. `forget()` is reserved for facts entered in error,
    not for facts that merely became outdated. The ledger tracks the
    active/superseded status + valid_to + SUPERSEDED_BY chain for the demo.
    """
    classification = state.get("classification")
    actions = list(state.get("actions") or [])

    # Ontology grounding (§4) is local (OWL parse + fuzzy match), Cognee-server
    # independent, so it runs on EVERY stored fact — incl. the agent's fast path
    # (cognee_sync=False) and offline tests. Sets ClinicalFact.ontology_valid.
    staged = state.get("new_fact")
    if staged is not None and classification != "CONSISTENT":
        valid = cognee_client.ground_fact(staged)
        learned = False
        if valid is False and staged.resource_type in ("Medication", "FamilyHistory"):
            learned = _try_dynamic_ground(staged)
            if learned:
                staged.ontology_valid = True
                valid = True
        if valid is not None:
            ledger.upsert(staged)
            note = " (learned dynamically via LLM classification)" if learned else ""
            actions.append(f"persist: ontology_valid={valid}{note} [{staged.id[:8]}].")

    if not state.get("cognee_sync", True):
        actions.append("persist: cognee_sync disabled (ledger only).")
        return {"actions": actions}

    # CONSISTENT is a restate -> no new Cognee node.
    if classification == "CONSISTENT":
        actions.append("persist: restate — no new Cognee node.")
        return {"actions": actions}

    new = state["new_fact"]
    # Cognee is best-effort: the ledger is the authoritative store that drives the
    # Memory Map, Board, and /why. If Cognee add/cognify fails, the ingest (and the
    # supersession edge already written to the ledger) must still succeed.
    note = ""
    try:
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
    except Exception as exc:  # pragma: no cover - Cognee must never break ingest
        actions.append(
            f"persist: Cognee sync skipped ({type(exc).__name__}: {exc}); "
            f"ledger is authoritative [{new.id[:8]}]."
        )
    return {"actions": actions}
