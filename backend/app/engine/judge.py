"""
The judge — a deterministic clinical-memory reconciler on Vertex AI.

Uses google-genai (Vertex, ADC, no API key) with structured output (`Verdict`)
and temperature 0. The judge ONLY runs when there is at least one related active
fact (the dedupe gate lives in the graph), so the LLM is never called for the
trivially-additive case.
"""

from __future__ import annotations

from typing import List

import app.config as config  # noqa: F401  (strips API keys, sets Vertex env)
from google import genai
from google.genai import types

from app.memory.schema import ClinicalFact, Verdict

_SYSTEM = (
    "You are a clinical memory reconciler. You are given a NEW clinical fact and a "
    "list of EXISTING active facts for the SAME patient and SAME subject. Decide how "
    "the NEW fact relates to the existing ones and return JSON.\n\n"
    "Classifications:\n"
    "- SUPERSEDES: the NEW fact makes exactly one EXISTING fact no longer true "
    "(e.g. an allergy is later cleared, a medication is switched/stopped). Set "
    "target_fact_id to that existing fact's id.\n"
    "- CONTRADICTS: the NEW fact directly conflicts with an EXISTING fact but there "
    "is no clear winner (both could be true / needs human review). Set target_fact_id "
    "to the conflicting fact.\n"
    "- CONSISTENT: the NEW fact merely restates / re-confirms an EXISTING active fact "
    "(same meaning). Set target_fact_id to that fact.\n"
    "- NEW: the NEW fact is unrelated or purely additive (no existing fact is "
    "affected). target_fact_id must be null.\n\n"
    "Pick a SINGLE target_fact_id for SUPERSEDES / CONTRADICTS / CONSISTENT. "
    "Use the exact id string shown in brackets. Be precise and conservative: prefer "
    "SUPERSEDES only when the new fact clearly invalidates the old one."
)

# Few-shot grounding (matches the demo timeline patterns).
_FEWSHOT = (
    "EXAMPLE 1\n"
    "NEW: allergy/cleared: penicillin (2026-03-02) raw='penicillin allergy cleared "
    "after negative re-test'\n"
    "EXISTING:\n  [aaaaaaaa] allergy/diagnosed: penicillin (2026-01-10, active)\n"
    'ANSWER: {"classification":"SUPERSEDES","target_fact_id":"aaaaaaaa",'
    '"reason":"Negative re-test clears the previously diagnosed penicillin allergy.",'
    '"confidence":0.97}\n\n'
    "EXAMPLE 2\n"
    "NEW: medication/switched: amlodipine 5mg (2026-04-20) raw='stopped lisinopril, "
    "switched to amlodipine'\n"
    "EXISTING:\n  [bbbbbbbb] medication/prescribed: lisinopril 10mg (2026-02-15, active)\n"
    'ANSWER: {"classification":"SUPERSEDES","target_fact_id":"bbbbbbbb",'
    '"reason":"Switching to amlodipine stops the prior lisinopril prescription.",'
    '"confidence":0.96}\n'
)


def _client() -> genai.Client:
    return genai.Client(
        vertexai=True, project=config.PROJECT, location=config.LOCATION
    )


def _render(new_fact: ClinicalFact, related: List[ClinicalFact], context=None) -> str:
    existing = "\n".join(
        f"  [{f.id}] {f.subject}/{f.predicate}: {f.value} "
        f"({f.valid_from.isoformat()}, {f.status}) raw='{f.raw_text}'"
        for f in related
    )
    ctx_block = ""
    if context:
        joined = "\n".join(f"  - {c}" for c in list(context)[:5])
        ctx_block = (
            "\nADDITIONAL MEMORY CONTEXT (background only — do NOT pick "
            f"target_fact_id from here):\n{joined}\n"
        )
    return (
        f"{_FEWSHOT}\n"
        "NOW CLASSIFY THIS CASE.\n"
        f"NEW: {new_fact.subject}/{new_fact.predicate}: {new_fact.value} "
        f"({new_fact.valid_from.isoformat()}) raw='{new_fact.raw_text}'\n"
        f"EXISTING:\n{existing}\n"
        f"{ctx_block}"
    )


def classify(new_fact: ClinicalFact, related: List[ClinicalFact], context=None) -> Verdict:
    """
    Classify how `new_fact` relates to `related` active facts.

    Deterministic (temperature 0) + structured output (`Verdict`). Caller must
    only invoke this when `related` is non-empty (dedupe gate). `context` is
    optional Cognee neighbor text used as background only; the target id is
    always validated against the ledger candidate set.
    """
    if not related:
        # Defensive: should be gated upstream, but never burn a call on nothing.
        return Verdict(classification="NEW", reason="No related active facts.")

    client = _client()
    response = client.models.generate_content(
        model=config.JUDGE_MODEL,
        contents=_render(new_fact, related, context),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0,
            response_mime_type="application/json",
            response_schema=Verdict,
        ),
    )

    verdict: Verdict = response.parsed  # type: ignore[assignment]

    # Validate the target id points at a real candidate; otherwise downgrade.
    valid_ids = {f.id for f in related}
    if verdict.classification in ("SUPERSEDES", "CONTRADICTS", "CONSISTENT"):
        if verdict.target_fact_id not in valid_ids:
            # Single-candidate convenience: snap to it; else treat as NEW.
            if len(related) == 1:
                verdict.target_fact_id = related[0].id
            else:
                verdict.classification = "NEW"
                verdict.target_fact_id = None
    return verdict
