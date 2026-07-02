"""
combined_risk_check — reasons ACROSS facts, not one in isolation (§5.2 check #3).

The relationship-graph hero: a first-degree relative's EARLY disease PLUS the
patient's OWN risk factors (smoking / high LDL) combine into one elevated risk,
and the card names EACH contributing fact with its citation.

Computed deterministically from the ledger — the documented memify fallback
(§12: "compute risk edges ourselves from the ledger … the card logic is the same
either way"). The optional `cognee_client.memify_risk_edges` pass materializes the
same relationship into the graph for the Memory-Map / graph view.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from app.checks.cards import Card, cite
from app.memory import ledger, ontology
from app.memory.schema import ClinicalFact

CHECK_ID = "combined_risk"


def _family_risks(patient_id: str) -> List[Tuple[str, ClinicalFact]]:
    """First-degree relatives whose condition confers a hereditary risk category."""
    out: List[Tuple[str, ClinicalFact]] = []
    for f in ledger.all(patient_id):
        if f.resource_type != "FamilyHistory" or f.status == "retracted":
            continue
        relation = f.attributes.get("relation") or ""
        condition = f.attributes.get("condition") or f.value or ""
        if not ontology.is_first_degree(relation):
            continue
        category = ontology.family_risk_for(condition)
        if category:
            out.append((category, f))
    return out


def _is_early_onset(f: ClinicalFact) -> bool:
    """Relative's event before the early-onset cutoff. Unknown onset → not early
    (don't raise a hereditary CV flag on an assumption)."""
    try:
        return int(f.attributes.get("age_at_onset")) < ontology.EARLY_ONSET_AGE
    except (TypeError, ValueError):
        return False


def _relative_desc(f: ClinicalFact) -> str:
    relation = (f.attributes.get("relation") or "relative").title()
    condition = f.attributes.get("condition") or f.value or "a serious condition"
    age = f.attributes.get("age_at_onset")
    return f"{relation} had {condition}" + (f" at age {age}" if age else "")


def _patient_cv_factors(patient_id: str) -> List[Tuple[str, ClinicalFact]]:
    """The patient's own cardiovascular risk factors, each as (label, fact):
    current smoking (lifestyle) and elevated LDL (lab)."""
    factors: List[Tuple[str, ClinicalFact]] = []
    for f in ledger.all(patient_id):
        if f.status == "retracted":
            continue
        if f.resource_type == "Lifestyle":
            blob = ontology._norm(
                f"{f.attributes.get('factor', '')} {f.attributes.get('value', '')} {f.value}"
            )
            if "smok" in blob and "non-smok" not in blob and "never" not in blob:
                factors.append(("current smoker", f))
        elif f.resource_type == "LabResult":
            if _ldl_high(f):
                v = f.attributes.get("value")
                factors.append((f"elevated LDL {v:g}" if isinstance(v, (int, float)) else "elevated LDL", f))
    return factors


def _ldl_high(f: ClinicalFact) -> bool:
    return ontology._norm(f.attributes.get("analyte") or "") == "ldl" and ontology._norm(
        f.attributes.get("abnormal_flag") or ""
    ) in ("high", "abnormal", "critical")


def run(patient_id: str, as_of: Optional[date] = None) -> List[Card]:
    cards: List[Card] = []
    family = _family_risks(patient_id)

    # Cardiovascular: require an EARLY-onset first-degree event AND ≥1 patient
    # factor — the combination is the signal, not any single fact.
    cv_relatives = [f for cat, f in family if cat == "cardiovascular" and _is_early_onset(f)]
    cv_factors = _patient_cv_factors(patient_id)
    if cv_relatives and cv_factors:
        relative = cv_relatives[0]
        factor_names = ", ".join(label for label, _ in cv_factors)
        cards.append(Card(
            check_id=f"{CHECK_ID}:cardiovascular",
            summary="Elevated cardiovascular risk — family history plus active risk factors",
            indicator="warning",
            detail=(
                f"{_relative_desc(relative)}, combined with {factor_names}, "
                f"raises this patient's cardiovascular risk."
            ),
            source=[cite(relative)] + [cite(f) for _, f in cv_factors],
            suggestions=[
                "Assess 10-year cardiovascular risk",
                "Discuss smoking cessation",
                "Consider lipid-lowering therapy and cardiovascular review",
            ],
        ))

    # Non-CV hereditary risk (oncologic / metabolic): a first-degree family history
    # alone warrants a screening flag (distinct card from CV — oracle #14).
    for category, f in family:
        if category == "cardiovascular":
            continue
        cards.append(Card(
            check_id=f"{CHECK_ID}:{category}",
            summary=f"Hereditary {category} risk — first-degree family history",
            indicator="warning",
            detail=f"{_relative_desc(f)}, conferring a hereditary {category} risk.",
            source=[cite(f)],
            suggestions=[f"Consider {category} screening per family-history guidelines"],
        ))
    return cards
