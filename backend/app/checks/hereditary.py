"""
hereditary_risk_check — reasons over a linked relative's ACTUAL diagnoses.

Unlike combined_risk (which reads the patient's SELF-REPORTED family history),
this traverses the auto-built family links to a relative who is also a patient,
reads THEIR ledger for heritable conditions, and raises a consent-gated card:
  * consent → cite the relative's real diagnosis;
  * no consent → a non-identifying prompt (never leaks another chart's detail).

Isolation-preserving: only CONSENTED links are ever traversed for identifying
detail (§A.4).
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.checks.cards import Card, Citation
from app.intake import family_resolver
from app.memory import ledger, ontology, records

CHECK_ID = "hereditary"


def _heritable_conditions(relative_id: str) -> List[str]:
    """Active heritable conditions on a relative's own chart."""
    out: List[str] = []
    for f in ledger.all(relative_id):
        if f.resource_type == "Condition" and f.status == "active":
            cond = (f.attributes or {}).get("condition") or f.value
            if cond and ontology.is_heritable(cond):
                out.append(cond)
    return out


def run(patient_id: str, as_of: Optional[date] = None) -> List[Card]:
    cards: List[Card] = []
    for link in family_resolver.links_for(patient_id):
        relation = link.get("relation", "relative")
        conditions = _heritable_conditions(link["relative_id"])
        if not conditions:
            continue
        cond_str = ", ".join(sorted(set(conditions)))
        category = ontology.family_risk_for(conditions[0]) or "hereditary"
        if link.get("consent"):
            rel = records.get_patient(link["relative_id"]) or {}
            who = f"This patient's {relation}"
            detail = (
                f"{who} — a linked patient ({rel.get('name', link['relative_id'])}) — "
                f"has {cond_str}, conferring a hereditary {category} risk."
            )
            source = [Citation(label=f"Linked relative record · {rel.get('name', link['relative_id'])}",
                               fact_id=None, date=None)]
        else:
            # No consent → non-identifying prompt only.
            detail = (
                f"A first-degree relative in the system has a heritable {category} "
                f"condition. Enable family-record consent to see details."
            )
            source = []
        cards.append(Card(
            check_id=f"{CHECK_ID}:{category}",
            summary=f"Hereditary {category} risk — from a linked relative's record",
            indicator="warning",
            detail=detail,
            source=source,
            suggestions=[f"Consider {category} screening per family-history guidelines"],
        ))
    return cards
