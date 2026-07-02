"""
Patient-scoped agent tools (the four memory verbs).

`build_patient_tools(patient_id)` returns four tools with `patient_id` baked into
each closure — the model NEVER sees or supplies a patient_id. This is the literal
mechanism for "if a doctor asks about a specific patient, it should only answer
from that patient": the Python closure (not a prompt instruction) decides which
patient every tool call touches, so the model cannot ask for, guess, or be tricked
into another patient's data.

Each tool is a thin wrapper over already-correct engine code — no new business
logic, only new bindings:

  recall_patient_facts -> engine.answer.synthesize_answer   (recall, now cited)
  ingest_fact          -> extract.build_fact + service.run_fact  (remember / improve)
  propose_forget       -> stages a pending correction (§7.1) — does NOT delete
  why_changed          -> ledger supersession chain          (explain)

Destructive correction is STAGED, never direct (audit §2.5): `propose_forget`
returns a pending action the agent surfaces for human approval; the actual
retraction only happens via `execute_forget`, called from POST /chat/approve.
Additive writes (`ingest_fact`) stay auto-executing — they're reversible via the
ledger's supersession history; a forget is not.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from google.genai import types

from app import checks
from app.agent import pending
from app.engine import extract, service
from app.engine.answer import synthesize_answer
from app.memory import cognee_client, ledger
from app.memory.schema import ClinicalFact


def declarations() -> List[types.FunctionDeclaration]:
    """Function-calling schemas the model sees. NOTE: no `patient_id` anywhere —
    scoping is closure-bound in build_patient_tools, never an LLM-supplied arg."""
    _str = lambda desc: types.Schema(type=types.Type.STRING, description=desc)  # noqa: E731
    return [
        types.FunctionDeclaration(
            name="recall_patient_facts",
            description=(
                "Answer a clinical question about the current patient from their memory. "
                "Use for any question about allergies, medications, diagnoses, labs, vitals, "
                "or procedures — including what is true now and what changed over time. "
                "Returns a synthesized natural-language answer."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"query": _str("The clinical question to answer.")},
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="ingest_fact",
            description=(
                "Record a new clinical fact stated in natural language into the patient's "
                "memory (e.g. 'Dr. Lee cleared the penicillin allergy on 2024-03-02'). "
                "The self-healing engine decides whether this supersedes or contradicts an "
                "existing fact. Use whenever the user states new clinical information."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"text": _str("The clinical statement to record, verbatim.")},
                required=["text"],
            ),
        ),
        types.FunctionDeclaration(
            name="propose_forget",
            description=(
                "PROPOSE removing a fact that was ENTERED IN ERROR (never true) — e.g. the "
                "clinician says an allergy entry is wrong. This does NOT delete anything; it "
                "stages a correction for the clinician to confirm with one click. Use only for "
                "genuine mistakes, NOT for facts that simply changed over time (ingest those as "
                "updates instead). Identify the fact by a short description like 'penicillin "
                "allergy'. After calling this, tell the user you've proposed the correction and "
                "are awaiting their confirmation."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": _str("Short description of the fact to correct, e.g. 'penicillin allergy'."),
                    "reason": _str("Why it is being corrected (e.g. 'entered in error')."),
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="why_changed",
            description=(
                "Explain the history of a clinical subject: what it was, what it changed to, "
                "when, who changed it, and why. Use for 'why did X change?' / provenance "
                "questions. The subject is a category like 'allergy', 'medication', 'diagnosis'."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"subject": _str("Clinical subject, e.g. 'allergy' or 'medication'.")},
                required=["subject"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_clinical_checks",
            description=(
                "Run the clinical safety checks over the current patient's chart and return "
                "the top not-to-miss findings (allergy conflicts, abnormal-lab follow-up gaps, "
                "combined cardiovascular risk). Use for 'what should I not miss?', 'any red "
                "flags?', a pre-visit review, or before making a clinical decision. Returns "
                "cited cards, most-severe first."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"focus": _str("Optional area to focus on, e.g. 'renal' — omit for all.")},
            ),
        ),
        types.FunctionDeclaration(
            name="propose_order",
            description=(
                "Run prescribe-time SAFETY CHECKS for a drug the clinician is considering, "
                "BEFORE anything is written. Use whenever the user asks whether they can/should "
                "prescribe or start a medication (e.g. 'can I prescribe amoxicillin?'). Returns "
                "any contraindication cards (e.g. a critical allergy via cross-reactivity), each "
                "cited. This does NOT place an order or write anything."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"drug": _str("The drug being considered, e.g. 'amoxicillin 500mg'.")},
                required=["drug"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_timeline",
            description=(
                "Return the patient's clinical events in chronological order (diagnoses, "
                "medications, labs, allergies, procedures) for a timeline/overview. Use for "
                "'give me the timeline', 'what's the history', or an at-a-glance review."
            ),
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
    ]


def _resolve_fact(patient_id: str, target: str) -> Optional[ClinicalFact]:
    """Map a free-text description ('penicillin allergy') to one active fact.

    The model can't know internal fact UUIDs, so the correction flow takes a
    description and we resolve it here against the patient's own ledger (scoped, so
    resolution can never reach another patient's facts)."""
    t = target.strip().lower()
    active = [f for f in ledger.all(patient_id) if f.status == "active"]
    for f in active:  # strongest: value / label / subject contains the description
        if t and (t in f.value.lower() or t in f.label.lower() or t == f.subject.lower()):
            return f
    for f in active:  # fallback: any description token appears in the label
        if any(tok in f.label.lower() for tok in t.split() if tok):
            return f
    return None


def _why_narrative(patient_id: str, subject: str) -> Tuple[str, Optional[str]]:
    """Build a provenance narrative + the most relevant fact_id for the UI."""
    facts = ledger.query_all(patient_id, subject) if subject else ledger.all(patient_id)
    if not facts:
        return "No records found for that subject.", None

    superseded = [f for f in facts if f.superseded_by]
    if not superseded:
        active = [f for f in facts if f.status == "active"]
        if active:
            f = active[-1]
            return (
                f"Current: {f.label} (since {f.valid_from}, source: {f.source}). "
                f"No prior changes recorded.",
                f.id,
            )
        return "No relevant changes found in the records.", None

    lines = []
    for old in superseded:
        new = ledger.get(old.superseded_by) if old.superseded_by else None
        if new:
            lines.append(
                f"\u2022 {old.label} ({old.valid_from}, {old.source}) was replaced by "
                f"{new.label} ({new.valid_from}, {new.source})"
                + (f" \u2014 reason: {new.reason}" if new.reason else "")
            )
    active = [f for f in facts if f.status == "active"]
    tail = ""
    if active:
        c = active[-1]
        tail = f"\n\nCurrent state: {c.label} (since {c.valid_from}, source: {c.source})."
    return "Change history:\n" + "\n".join(lines) + tail, superseded[0].id


async def execute_forget(patient_id: str, fact_id: str, reason: str):
    """Actually retract a fact (Cognee + ledger). The ONLY place a forget executes,
    called from the approval gate (POST /chat/approve) — never directly by the model.

    Returns (retracted_fact, restored_fact|None). `retracted` is None if the fact
    no longer exists (already retracted / unknown id) — keeps approve idempotent."""
    fact = ledger.get(fact_id)
    if fact is None or fact.status == "retracted":
        return None, None
    if fact.cognee_data_id:
        try:
            await cognee_client.forget_fact(fact.cognee_data_id, patient_id)
        except Exception:  # pragma: no cover - best-effort; ledger retract is authoritative
            pass
    return ledger.retract(fact.id, reason)


def _cards_to_text(cards: List["checks.Card"]) -> str:
    """Flatten cards into a compact block for the model to phrase from. Card data
    (indicator, detail, citation) is what the UI renders richly; this is just so
    the model's prose reflects the same findings."""
    if not cards:
        return "No safety concerns found."
    lines = []
    for c in cards:
        src = c.source[0] if c.source else None
        cite_str = ""
        if src:
            bits = [b for b in (src.label, src.date) if b]
            if src.page:
                bits.append(f"p.{src.page}")
            cite_str = f" [source: {', '.join(bits)}]"
        lines.append(f"- [{c.indicator.upper()}] {c.summary}: {c.detail}{cite_str}")
    return "\n".join(lines)


def build_patient_tools(
    patient_id: str,
) -> Tuple[Dict[str, Callable], List[types.FunctionDeclaration], List[dict]]:
    """Return (tool dispatch map, declarations, action log) all bound to one patient.

    Each tool appends ONE rich entry to `log` per call; the router enriches each
    entry with seq/args/ms/result_summary to form the persisted per-turn trace
    (§7.5) that also drives the live UI trace (§8)."""
    log: List[dict] = []

    def recall_patient_facts(query: str) -> str:
        ans = synthesize_answer(patient_id, query)
        log.append(
            {
                "chip": "Recalled memory",
                "tool": "recall_patient_facts",
                "citations": [c.model_dump(mode="json") for c in ans.citations],
                "certainty": ans.certainty,
                # The six-part doctor-facing answer contract (§5.3) for the UI AnswerCard.
                "answer": {
                    "answer_text": ans.answer_text,
                    "reason": ans.reason,
                    "certainty": ans.certainty,
                    "whats_missing": ans.whats_missing,
                    "suggested_action": ans.suggested_action,
                    "validation": ans.validation,
                },
                "fact_id": ans.citations[0].fact_id if ans.citations else None,
            }
        )
        # Return the structured contract to the model so its prose reflects
        # reason/missing/action, not just the bare answer.
        parts = [f"ANSWER: {ans.answer_text}", f"CONFIDENCE: {ans.certainty}"]
        if ans.reason:
            parts.insert(1, f"REASON: {ans.reason}")
        if ans.whats_missing:
            parts.append(f"WHAT'S MISSING: {ans.whats_missing}")
        if ans.suggested_action:
            parts.append(f"SUGGESTED ACTION (for your review): {ans.suggested_action}")
        return "\n".join(parts)

    async def ingest_fact(text: str) -> str:
        # Idempotency (§7.5): a retried/duplicate ingest of the same text for the
        # same patient returns the prior result instead of double-writing.
        key = pending.make_key(patient_id, text)
        prior = pending.seen_write(key)
        if prior is not None:
            log.append(
                {"chip": "Already recorded (deduped)", "tool": "ingest_fact", "deduped": True}
            )
            return prior

        fact = extract.build_fact(patient_id, text, None)
        # FAST PATH: heal the ledger + add to Cognee synchronously (recall -> judge
        # -> reconcile -> persist). run_fact_bg DEFERS the ~20s temporal cognify to a
        # background task, so the reply (which reads the authoritative ledger) is
        # correct and returns immediately; the Cognee graph + search catch up a few
        # seconds later.
        state = await service.run_fact_bg(patient_id, fact)
        classification = state.get("classification", "NEW")
        final = ledger.get(fact.id) or fact
        healed = classification in ("SUPERSEDES", "CONTRADICTS")
        log.append(
            {
                "chip": f"{'Updated' if healed else 'Recorded'}: {final.label}",
                "fact_id": final.id,
                "tool": "ingest_fact",
            }
        )
        reason = state.get("reason", "")
        summary = (
            f"Recorded '{final.label}' (classification: {classification})."
            + (f" {reason}" if reason else "")
        )
        pending.record_write(key, summary)
        return summary

    def propose_forget(target: str, reason: str = "entered in error") -> str:
        """Stage a destructive correction for human approval — does NOT delete."""
        fact = _resolve_fact(patient_id, target)
        if fact is None:
            log.append({"chip": f"No match to correct: {target}", "tool": "propose_forget"})
            return f"No active fact matching '{target}' was found to correct."
        proposal = pending.add_pending(patient_id, fact.id, fact.label, reason)
        log.append(
            {
                "chip": f"Proposed correction: {fact.label}",
                "fact_id": fact.id,
                "tool": "propose_forget",
                "pending": {
                    "pending_id": proposal["pending_id"],
                    "fact_id": fact.id,
                    "label": fact.label,
                    "valid_from": fact.valid_from.isoformat(),
                    "source": fact.source,
                    "reason": reason,
                },
            }
        )
        return (
            f"Proposed marking '{fact.label}' ({fact.valid_from}, {fact.source}) as entered "
            f"in error — awaiting the clinician's one-click confirmation. Nothing has been "
            f"removed yet."
        )

    def why_changed(subject: str) -> str:
        narrative, fid = _why_narrative(patient_id, subject.strip().lower())
        log.append({"chip": f"Explained: {subject or 'history'}", "fact_id": fid, "tool": "why_changed"})
        return narrative

    def run_clinical_checks(focus: str = "") -> str:
        """Patient-view safety checks → the not-to-miss cards (§5.2)."""
        cards = checks.run_open_checks(patient_id)
        if focus.strip():
            f = focus.strip().lower()
            filtered = [c for c in cards if f in (c.summary + c.detail).lower()]
            cards = filtered or cards  # don't hide everything on a bad focus term
        log.append(
            {
                "chip": f"Ran clinical checks ({len(cards)} finding{'s' if len(cards) != 1 else ''})",
                "tool": "run_clinical_checks",
                "cards": [c.model_dump(mode="json") for c in cards],
            }
        )
        return _cards_to_text(cards)

    def propose_order(drug: str) -> str:
        """Prescribe-time safety check, run BEFORE any write (§5.1). Writes nothing."""
        cards = checks.run_prescribe_checks(patient_id, drug)
        crit = any(c.indicator == "critical" for c in cards)
        log.append(
            {
                "chip": (f"Prescribe check: {drug.split()[0] if drug.split() else drug}"
                         + (" — CRITICAL" if crit else " — clear")),
                "tool": "propose_order",
                "cards": [c.model_dump(mode="json") for c in cards],
            }
        )
        if not cards:
            return (
                f"No allergy or contraindication found for {drug} in this patient's records. "
                "This is a safety screen only — confirm dosing and interactions for your review."
            )
        return "Prescribe-time safety findings (nothing has been ordered):\n" + _cards_to_text(cards)

    def get_timeline() -> str:
        """Chronological clinical events for the Timeline tab (§5.1, thin over ledger)."""
        facts = [f for f in ledger.all(patient_id) if f.status != "retracted"]
        events = [
            {
                "date": f.valid_from.isoformat(),
                "resource_type": f.resource_type,
                "label": f.label,
                "status": f.status,
                "fact_id": f.id,
                "source_document": f.source_document,
            }
            for f in facts
        ]
        log.append(
            {"chip": f"Built timeline ({len(events)} events)", "tool": "get_timeline", "timeline": events}
        )
        if not events:
            return "No clinical events on record for this patient."
        return "\n".join(f"- {e['date']}: {e['label']}" for e in events)

    tools_map: Dict[str, Callable] = {
        "recall_patient_facts": recall_patient_facts,
        "ingest_fact": ingest_fact,
        "propose_forget": propose_forget,
        "why_changed": why_changed,
        "run_clinical_checks": run_clinical_checks,
        "propose_order": propose_order,
        "get_timeline": get_timeline,
    }
    return tools_map, declarations(), log
