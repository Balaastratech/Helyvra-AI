"""
allergy_check — allergy-before-prescribe, the #1 hero check (§5.2).

Two entry points, one shared conflict logic:
  • `run(patient_id)`      — open-brief mode: flag any ACTIVE medication that
                             conflicts with an active allergy.
  • `for_drug(patient_id, drug)` — prescribe mode: run the SAME check against a
                             drug the doctor is about to order, BEFORE any write.

Cross-reactivity (penicillin → all beta-lactams) comes from the shared medical
ontology, so a cephalosporin/carbapenem trips a penicillin allergy — that is the
clinically critical case the demo turns on.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.checks.cards import Card, cite
from app.memory import ledger, ontology
from app.memory.schema import ClinicalFact

CHECK_ID = "allergy"


def _active_allergies(patient_id: str) -> List[ClinicalFact]:
    """Active allergy facts (a 'cleared' allergy is not a contraindication)."""
    return [
        f for f in ledger.all(patient_id)
        if f.resource_type == "Allergy"
        and f.status == "active"
        and f.predicate.strip().lower() != "cleared"
    ]


def _substance(allergy: ClinicalFact) -> str:
    return (
        allergy.attributes.get("substance")
        or allergy.attributes.get("drug")
        or allergy.value
        or ""
    ).strip()


def _matches(substance: str, drug: str) -> bool:
    """True if `drug` is contraindicated by an allergy to `substance`: same drug,
    same pharmacologic class, or same cross-reactivity group (beta-lactam ring).
    Falls back to an exact token match when a drug is outside the ontology."""
    if ontology.are_cross_reactive(substance, drug):
        return True
    ns = ontology._norm(substance)
    return ns in ontology._norm(drug).replace("/", " ").split()


def _conflict_card(drug: str, allergy: ClinicalFact) -> Optional[Card]:
    substance = _substance(allergy)
    if not substance or not _matches(substance, drug):
        return None

    drug_name = drug.split()[0] if drug.split() else drug
    drug_cls = ontology.drug_class(drug)
    group = ontology.CLASS_GROUP.get(drug_cls or "")

    reason = f"{drug_name.title()} is a {drug_cls}" if drug_cls else f"{drug_name.title()}"
    if group == "beta_lactam":
        reason += " (beta-lactam class)"
    reason += f"; the patient has a documented {substance} allergy"

    reaction = allergy.attributes.get("reaction")
    severity = allergy.attributes.get("severity")
    detail = reason
    if reaction:
        detail += f"; prior reaction: {reaction}"
    if severity:
        detail += f" (severity: {severity})"
    detail += "."

    return Card(
        check_id=CHECK_ID,
        summary=f"Do not prescribe {drug_name} — {substance} allergy",
        indicator="critical",
        detail=detail,
        source=[cite(allergy)],
        suggestions=[
            f"Avoid {drug_name} and other {(group or drug_cls or 'related').replace('_', ' ')} agents",
            "Choose a non-cross-reactive alternative",
            "Reconfirm the allergy and reaction with the patient",
        ],
    )


def for_drug(patient_id: str, drug: str) -> List[Card]:
    """Prescribe-time safety check: is `drug` safe given the patient's active
    allergies? Runs BEFORE any write (§5.1 propose_order)."""
    cards: List[Card] = []
    for allergy in _active_allergies(patient_id):
        card = _conflict_card(drug, allergy)
        if card:
            cards.append(card)
    return cards


def run(patient_id: str, as_of: Optional[date] = None) -> List[Card]:
    """Open-brief mode: flag active medications that conflict with active
    allergies. Returns [] when nothing on the active med list conflicts (the
    standalone allergy shows in the brief summary/badge, not as a not-to-miss
    card unless there is a real conflict)."""
    allergies = _active_allergies(patient_id)
    if not allergies:
        return []
    cards: List[Card] = []
    for med in ledger.all(patient_id):
        if med.resource_type != "Medication" or med.status != "active":
            continue
        drug = (med.attributes.get("drug") or med.value or "").strip()
        if not drug:
            continue
        for allergy in allergies:
            card = _conflict_card(drug, allergy)
            if card:
                card.summary = (
                    f"Active medication {drug.split()[0]} conflicts with "
                    f"{_substance(allergy)} allergy"
                )
                cards.append(card)
    return cards
