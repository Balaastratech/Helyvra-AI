"""
The clinical check engine (§5.2).

Every check is a module exposing `run(patient_id, as_of=None) -> list[Card]`, so
extending coverage = adding a module to OPEN_CHECKS. The §11 deferred checks
(drug-drug interaction, contraindication, preventive gaps, …) all plug in through
this same one interface — that is why "the rest are the same engine extended" is
literally true.

Triggered on patient-open (→ pre-visit brief) and on propose_order (→ prescribe
check). Output is capped most-severe-first for alert-fatigue control.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.checks import allergy, followup, hereditary, risk
from app.checks.cards import Card, top_by_severity

# Checks run when a patient is opened (the pre-visit brief). Order here is
# registration only; severity sorts the output.
OPEN_CHECKS = [allergy, followup, risk, hereditary]


def run_open_checks(patient_id: str, as_of: Optional[date] = None, limit: int = 5) -> List[Card]:
    """All open checks for a patient → the pre-visit brief's not-to-miss cards,
    most-severe-first and capped."""
    cards: List[Card] = []
    for check in OPEN_CHECKS:
        cards.extend(check.run(patient_id, as_of=as_of))
    return top_by_severity(cards, limit)


def run_prescribe_checks(
    patient_id: str, drug: str, as_of: Optional[date] = None, limit: int = 5
) -> List[Card]:
    """Prescribe-time safety checks for a proposed drug, run BEFORE any write
    (§5.1 propose_order). Allergy today; interaction/contraindication plug in here."""
    return top_by_severity(allergy.for_drug(patient_id, drug), limit)
