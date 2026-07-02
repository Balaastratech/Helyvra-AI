"""
CDS-Hooks-modeled card — the single doctor-facing unit every clinical check
returns (CLINICAL_COPILOT_PLAN §5.2).

`Card = {summary, indicator: info|warning|critical, detail, source:[Citation],
suggestions:[str]}` is the CDS-Hooks card shape. Keeping ONE shape is what makes
"the rest are the same engine extended" literally true — a new check just returns
more Cards. The model is plain Pydantic so it doubles as the API response contract.
"""

from __future__ import annotations

from typing import Iterable, List, Literal, Optional

from pydantic import BaseModel, Field

from app.memory.schema import ClinicalFact

Indicator = Literal["info", "warning", "critical"]

# severity sort key (most severe first) — alert-fatigue control.
_ORDER = {"critical": 0, "warning": 1, "info": 2}


class Citation(BaseModel):
    """Where a claim comes from — the evidence chip the UI renders (source + date
    + page), and the ledger fact id so the UI can open the fact / source doc."""

    label: str
    source_document: Optional[str] = None
    page: Optional[int] = None
    date: Optional[str] = None
    fact_id: Optional[str] = None


class Card(BaseModel):
    """One clinical finding in CDS-Hooks card shape."""

    check_id: str
    summary: str
    indicator: Indicator = "info"
    detail: str = ""
    source: List[Citation] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


def cite(fact: ClinicalFact, label: Optional[str] = None) -> Citation:
    """Build a citation from a fact. Label prefers the human document title, then
    the source document id, then the clinician, then the fact's own label — so a
    card always cites *something* a doctor can click through to."""
    return Citation(
        label=label or fact.document_title or fact.source_document or fact.source or fact.label,
        source_document=fact.source_document,
        page=fact.page,
        date=fact.valid_from.isoformat(),
        fact_id=fact.id,
    )


def top_by_severity(cards: Iterable[Card], limit: int = 5) -> List[Card]:
    """Most-severe-first, capped (§5.2 'top 3–5 by severity' — alert-fatigue)."""
    return sorted(cards, key=lambda c: _ORDER.get(c.indicator, 3))[:limit]
