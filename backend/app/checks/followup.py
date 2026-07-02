"""
followup_gap_check — abnormal labs that were never acted on, plus worsening
trends despite monitoring (§5.2 check #2 + the HbA1c-rising signal).

Deterministic over the ledger's LabResult facts:
  • TREND — ≥2 abnormal readings of one analyte moving the wrong way (rising
            HbA1c/creatinine/glucose, etc.) → a warning citing every reading.
  • GAP   — the latest abnormal reading of an organ-function analyte with NO
            follow-up (repeat lab / note / referral / procedure) for that
            analyte's domain past a window → the "missed follow-up" warning.

Division of labour with combined_risk (§5.2 #3): risk-factor labs (LDL, etc.)
feed the combined-risk card, organ-function labs (creatinine, HbA1c, K, INR)
feed this one — so a chronic risk marker isn't double-carded as a follow-up gap.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from app.checks.cards import Card, cite
from app.memory import ledger, ontology
from app.memory.schema import ClinicalFact

CHECK_ID = "followup_gap"

# An abnormal result may sit this long with no follow-up before it's a gap.
# ponytail: single global window; upgrade path = per-analyte cadence from
# ontology.CONDITION_MONITORING once conditions reliably drive monitoring rules.
_GAP_DAYS = 90

# Analytes where a RISING value is the concerning direction.
_RISING_BAD = {"hba1c", "ldl", "creatinine", "glucose", "potassium", "inr"}

# Risk-factor labs owned by combined_risk — excluded from the follow-up gap so
# they aren't double-carded.
_RISK_FACTOR_ANALYTES = {"ldl", "hdl", "cholesterol", "triglycerides", "bmi"}

# What counts as "following up" an abnormal analyte (domain keywords).
_FOLLOWUP_KEYWORDS: Dict[str, List[str]] = {
    "creatinine": ["creatinine", "renal", "kidney", "nephrolog", "egfr"],
    "egfr": ["egfr", "creatinine", "renal", "kidney", "nephrolog"],
    "hba1c": ["hba1c", "a1c", "diabet", "glycemic", "glycaemic", "endocrin"],
    "potassium": ["potassium", "electrolyte"],
    "inr": ["inr", "warfarin", "anticoag"],
}


def _labs(patient_id: str) -> List[ClinicalFact]:
    return [
        f for f in ledger.all(patient_id)
        if f.resource_type == "LabResult" and f.status != "retracted"
    ]


def _analyte(f: ClinicalFact) -> str:
    return ontology._norm(f.attributes.get("analyte") or "")


def _value(f: ClinicalFact) -> Optional[float]:
    try:
        return float(f.attributes.get("value"))
    except (TypeError, ValueError):
        return None


def _is_abnormal(f: ClinicalFact) -> bool:
    return ontology._norm(f.attributes.get("abnormal_flag") or "") in (
        "high", "low", "abnormal", "critical",
    )


def _has_followup(patient_id: str, analyte: str, after: date) -> bool:
    """Any evidence the abnormal analyte was acted on after `after`: a later
    reading of the SAME analyte, or a later note/referral/procedure/condition
    that references the analyte's clinical domain."""
    keywords = _FOLLOWUP_KEYWORDS.get(analyte, [analyte])
    for f in ledger.all(patient_id):
        if f.valid_from <= after or f.status == "retracted":
            continue
        if f.resource_type == "LabResult" and _analyte(f) == analyte:
            return True
        if f.resource_type in ("Procedure", "Condition") or f.subject.lower() in (
            "note", "referral", "followup", "plan",
        ):
            text = " ".join(str(x) for x in (
                f.value, f.raw_text, f.attributes.get("name", ""),
                f.attributes.get("condition", ""),
            )).lower()
            if any(k in text for k in keywords):
                return True
    return False


def run(patient_id: str, as_of: Optional[date] = None) -> List[Card]:
    today = as_of or date.today()
    by_analyte: Dict[str, List[ClinicalFact]] = {}
    for f in _labs(patient_id):
        a = _analyte(f)
        if a:
            by_analyte.setdefault(a, []).append(f)

    cards: List[Card] = []
    for analyte, facts in by_analyte.items():
        facts.sort(key=lambda f: f.valid_from)
        abnormal = [f for f in facts if _is_abnormal(f)]
        if not abnormal:
            continue

        trended = False
        valued = [f for f in abnormal if _value(f) is not None]
        if len(valued) >= 2:
            first, last = _value(valued[0]), _value(valued[-1])
            rising = last > first
            wrong_way = (rising and analyte in _RISING_BAD) or (
                not rising and analyte not in _RISING_BAD
            )
            if wrong_way and first != last:
                trended = True
                seq = " → ".join(f"{_value(f):g}" for f in valued)
                cards.append(Card(
                    check_id=f"{CHECK_ID}:trend:{analyte}",
                    summary=f"{analyte.upper()} {'rising' if rising else 'falling'}: {seq}",
                    indicator="warning",
                    detail=(
                        f"{analyte.upper()} moved {seq} "
                        f"({valued[0].valid_from.isoformat()} → "
                        f"{valued[-1].valid_from.isoformat()}) — trending the wrong "
                        f"way despite prior results."
                    ),
                    source=[cite(f) for f in valued],
                    suggestions=[
                        f"Review {analyte.upper()} management",
                        "Consider treatment intensification or specialist referral",
                    ],
                ))

        # Gap: the latest abnormal organ-function reading with no follow-up. Skip
        # risk-factor labs (combined_risk owns them) and analytes already surfaced
        # as a trend (the trend card already carries the signal).
        if analyte in _RISK_FACTOR_ANALYTES or trended:
            continue
        latest = abnormal[-1]
        if (today - latest.valid_from).days >= _GAP_DAYS and not _has_followup(
            patient_id, analyte, latest.valid_from
        ):
            val = _value(latest)
            valstr = f"{val:g}" if val is not None else latest.value
            flag = ontology._norm(latest.attributes.get("abnormal_flag") or "abnormal")
            cards.append(Card(
                check_id=f"{CHECK_ID}:gap:{analyte}",
                summary=f"Abnormal {analyte.upper()} ({valstr}) with no follow-up",
                indicator="warning",
                detail=(
                    f"{analyte.upper()} was {valstr} ({flag}) on "
                    f"{latest.valid_from.isoformat()} with no subsequent lab, note, "
                    f"or referral on record."
                ),
                source=[cite(latest)],
                suggestions=[
                    f"Order a repeat {analyte.upper()}",
                    "Refer to the relevant specialist",
                    "Document a follow-up plan",
                ],
            ))
    return cards
