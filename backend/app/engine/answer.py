"""
Answer synthesis — the "past vs present" narrator, now cited and uncertainty-aware.

Given a patient question + their full fact history from the ledger, produce an
answer that ALWAYS states current truth AND (when applicable) what changed, when,
and who changed it. This is the core differentiator: Total Recall never just says
"No" — it says "No — was diagnosed X, cleared by Y on Z."

v3 (UPGRADE_PLAN §6, §2.6.B): the synthesis now returns structured output —
`{answer_text, citations, certainty}` — not free prose:

  * citations: every clinical claim is grounded in a real ledger fact, so the UI
    can link each statement back to its source document (forced-grounding /
    anti-hallucination, audit §2.5).
  * certainty: "settled" | "contested" | "low_confidence". A contested subject is
    NEVER presented as one confident answer — both conflicting records are named.
    This is the "capable assistant that sometimes needs correction, not a confident
    expert" requirement (§2.6.B) — the single failure mode this project exists to
    prevent must not reappear in our own answers.

One Vertex Flash call, structured, temperature 0.
"""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

import app.config as config
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.memory import ledger
from app.memory.schema import ClinicalFact

# Below this, an active fact's confidence is surfaced as "unverified" (§2.6.B).
LOW_CONFIDENCE_THRESHOLD = 0.6

Certainty = Literal["settled", "contested", "low_confidence"]


class Citation(BaseModel):
    """A clinical claim's grounding — one ledger fact, with its provenance.

    Fields all come straight off `ClinicalFact` (already present today, just never
    surfaced), so the UI can open the exact source record behind a sentence."""
    fact_id: str
    source_document: Optional[str] = None
    document_title: Optional[str] = None
    page: Optional[int] = None
    valid_from: Optional[date] = None
    source: str = "unknown"


class SynthesizedAnswer(BaseModel):
    """Structured, cited, uncertainty-aware answer — the doctor-facing contract
    (§5.3): Answer · Reason · Evidence · Confidence · What's missing · Suggested
    action. `answer_text`/`citations`/`certainty` are the Answer/Evidence/Confidence
    legs; `reason`/`whats_missing`/`suggested_action` complete the six-part shape the
    UI renders as an AnswerCard. `validation` is the evidence validator's verdict (§5.4)."""
    answer_text: str
    reason: str = ""
    citations: List[Citation] = []
    certainty: Certainty = "settled"
    whats_missing: str = ""
    suggested_action: str = ""
    has_history: bool = False
    validation: dict = {}


class _LLMOut(BaseModel):
    """What the model returns. It only PICKS which facts it used (by id) — the
    citation details are filled from the authoritative ledger, never the model,
    so provenance can't be hallucinated."""
    answer_text: str
    reason: str = ""
    cited_fact_ids: List[str] = []
    certainty: Certainty = "settled"
    whats_missing: str = ""
    suggested_action: str = ""
    has_history: bool = False


_SYSTEM = (
    "You are a clinical memory assistant. Given a clinician's question and the FULL "
    "chronological fact history for the relevant subject(s), produce ONE answer.\n\n"
    "You are a capable assistant that sometimes needs correction — NOT a confident "
    "expert. Honesty about what you don't know is a feature. A confident WRONG answer "
    "is the worst possible outcome.\n\n"
    "Rules:\n"
    "1. ALWAYS state the CURRENT truth first.\n"
    "2. If the subject changed over time (more than one historical version), EXPLICITLY "
    "state what it was before, when it changed, and who/what changed it, with dates.\n"
    "3. Ground every clinical claim: list the `id` of each fact you used in "
    "`cited_fact_ids`. Do not assert anything not backed by a listed fact.\n"
    "4. Set `certainty`:\n"
    "   - 'contested': the relevant facts CONFLICT (a fact marked [contested], or two "
    "active same-subject facts that disagree). DO NOT pick a winner — name BOTH "
    "conflicting records and their sources/dates, and say you cannot resolve which is "
    "current.\n"
    "   - 'low_confidence': the best available fact is weak/uncertain.\n"
    "   - 'settled': exactly one clear, current, non-contested answer.\n"
    "5. If the facts don't contain enough info, say so honestly (certainty 'low_confidence').\n"
    "6. Be concise but complete; natural clinical language.\n"
    "7. `reason`: one short sentence on WHY this is the answer (the clinical "
    "reasoning from the cited facts) — not a restatement of the answer.\n"
    "8. `whats_missing`: name any information a clinician would want that the "
    "records do NOT contain (e.g. 'no recent renal function test', 'reaction "
    "severity not documented'). Empty string if nothing material is missing.\n"
    "9. `suggested_action`: a suggested NEXT STEP for the clinician, always framed "
    "'for your review' — never a directive, never a diagnosis beyond the evidence.\n\n"
    "Return JSON: answer_text (string), reason (string), cited_fact_ids (list of "
    "fact id strings), certainty ('settled'|'contested'|'low_confidence'), "
    "whats_missing (string), suggested_action (string), has_history (bool)."
)


def _format_history(facts: List[ClinicalFact]) -> str:
    """Format fact history for the LLM prompt (includes id, status, confidence)."""
    if not facts:
        return "(no facts recorded)"
    lines = []
    for f in facts:
        span = f.valid_from.isoformat()
        if f.valid_to:
            span += f" \u2192 {f.valid_to.isoformat()}"
        status_note = f" [{f.status}]" if f.status != "active" else " [CURRENT]"
        conf_note = f" conf={f.confidence:.2f}" if f.confidence < 1.0 else ""
        reason_note = f" reason: {f.reason}" if f.reason else ""
        lines.append(
            f"- id={f.id} {span}{status_note} {f.subject}/{f.predicate}: {f.value} "
            f"(source: {f.source}){conf_note}{reason_note}"
        )
    return "\n".join(lines)


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
            )
        )
    return out


def _enforce_certainty(certainty: Certainty, cited: List[ClinicalFact]) -> Certainty:
    """Deterministic guard over the model's self-reported certainty — the prompt
    asks for honesty, this makes contested/low-confidence non-bypassable (§2.6.B).
    A contested cited fact can NEVER be reported as 'settled'."""
    if any(f.status == "contested" for f in cited):
        return "contested"
    if certainty == "settled" and any(
        f.confidence < LOW_CONFIDENCE_THRESHOLD for f in cited if f.status == "active"
    ):
        return "low_confidence"
    return certainty


# Hedge used when an answer isn't grounded in this patient's records (§5.4).
_UNGROUNDED_HEDGE = (
    "I couldn't find a clear record supporting this in this patient's chart — "
    "please verify directly before relying on it."
)


def validate_answer(ans: SynthesizedAnswer) -> SynthesizedAnswer:
    """The evidence validator (§5.4) — a deterministic gate every clinical answer
    passes before it leaves the agent. It never invents confidence: an answer with
    no citation can NEVER stay 'settled', and a bare confident claim is rewritten
    to an explicit "please verify" hedge. The thesis (a confident-wrong answer is
    the worst outcome) applied to our own voice.

    Records the verdict on `ans.validation` so the UI/audit can show what was
    checked: grounded · cited · confidence_stated · conflicting."""
    grounded = bool(ans.citations)
    # A clinical answer with no evidence must not read as settled fact.
    if not grounded and ans.certainty == "settled" and ans.answer_text.strip():
        ans.certainty = "low_confidence"
        ans.answer_text = f"{ans.answer_text.rstrip('.')}. {_UNGROUNDED_HEDGE}"
    ans.validation = {
        "grounded": grounded,
        "cited": grounded,
        "confidence_stated": True,  # certainty is always set
        "conflicting": ans.certainty == "contested",
    }
    return ans


def synthesize_answer(
    patient_id: str, question: str, as_of: str | None = None
) -> SynthesizedAnswer:
    """
    Produce a cited, certainty-aware answer from the full ledger history.
    Falls back gracefully (still structured) if the LLM call fails.
    """
    all_facts = ledger.all(patient_id)
    if not all_facts:
        return validate_answer(SynthesizedAnswer(
            answer_text="No records have been ingested for this patient yet.",
            certainty="low_confidence",
            whats_missing="This patient has no clinical records on file.",
        ))

    # Retracted (entered-in-error) facts never appear in the narrative.
    visible_facts = [f for f in all_facts if f.status != "retracted"]
    if not visible_facts:
        return validate_answer(SynthesizedAnswer(
            answer_text="No active clinical records found for this patient.",
            certainty="low_confidence",
            whats_missing="No active clinical records on file.",
        ))

    history_text = _format_history(visible_facts)
    # Time awareness: "state the CURRENT truth first" is meaningless unless the
    # model knows what "now" is. Always anchor to a concrete date — the rewound
    # as_of when scrubbing, else today.
    effective_date = as_of or date.today().isoformat()
    prompt = f"QUESTION: {question}\n"
    prompt += (
        f"(TODAY'S DATE IS {date.today().isoformat()}. Answer as of {effective_date} — "
        "treat facts valid on that date as current, later facts as not yet known.)\n"
    )
    prompt += f"\nFULL FACT HISTORY (chronological):\n{history_text}"

    try:
        client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
        response = client.models.generate_content(
            model=config.EXTRACTION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                temperature=0,
                response_mime_type="application/json",
                response_schema=_LLMOut,
            ),
        )
        out: _LLMOut = response.parsed  # type: ignore[assignment]
        cited_facts = [f for f in visible_facts if f.id in set(out.cited_fact_ids)]
        return validate_answer(SynthesizedAnswer(
            answer_text=out.answer_text,
            reason=out.reason,
            citations=_citations_for(out.cited_fact_ids, visible_facts),
            certainty=_enforce_certainty(out.certainty, cited_facts),
            whats_missing=out.whats_missing,
            suggested_action=out.suggested_action,
            has_history=out.has_history,
        ))
    except Exception as exc:
        # Honest degraded fallback (§2.6.F): answer from ledger data, still cited,
        # still uncertainty-flagged — never a silent confident guess.
        active = [f for f in visible_facts if f.status == "active"]
        if active:
            text = "; ".join(
                f"{f.label} (since {f.valid_from}, source: {f.source})" for f in active
            )
            return validate_answer(SynthesizedAnswer(
                answer_text=text,
                citations=_citations_for([f.id for f in active], visible_facts),
                certainty=_enforce_certainty("low_confidence", active),
                suggested_action="Model synthesis was unavailable — review the cited "
                "records directly for your assessment.",
            ))
        return validate_answer(SynthesizedAnswer(
            answer_text=f"Could not synthesize answer: {type(exc).__name__}",
            certainty="low_confidence",
        ))


def synthesize(patient_id: str, question: str, as_of: str | None = None) -> str:
    """Back-compat string accessor (used by /ask's total_recall branch and the
    Compare tab). Same synthesis, just the prose — citations/certainty are for
    the agent chat surface (§6)."""
    return synthesize_answer(patient_id, question, as_of=as_of).answer_text
