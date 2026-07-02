"""
Clinical check engine (CLINICAL_COPILOT_PLAN §5.2) — CDS-Hooks cards over the
authoritative ledger, grounded in the medical ontology. Import surface:

    from app import checks
    checks.run_open_checks(patient_id)          # pre-visit brief cards
    checks.run_prescribe_checks(patient_id, d)  # allergy-before-prescribe
"""

from app.checks.cards import Card, Citation, cite, top_by_severity
from app.checks.engine import OPEN_CHECKS, run_open_checks, run_prescribe_checks

__all__ = [
    "Card",
    "Citation",
    "cite",
    "top_by_severity",
    "OPEN_CHECKS",
    "run_open_checks",
    "run_prescribe_checks",
]
