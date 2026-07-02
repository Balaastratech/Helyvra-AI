"""
Structured-intake helpers — the ONE place the FHIR-aligned `assert` shape is
built (CLINICAL_COPILOT_PLAN §2/§3).

Every intake path (FHIR parser, CSV lab series, LLM text/PDF extractor) emits the
same assert dict so `records.facts_from_document` can turn it into an
attribute-rich `ClinicalFact` the check engine reads:

    {
      "resource_type": "LabResult",           # FHIR discriminator
      "subject": "lab hba1c",                 # engine grouping key
      "predicate": "measured",
      "value": "HbA1c 7.8%",                  # human label
      "date": "2024-06-12",
      "source": "P010_labs_2024.csv",
      "attributes": {"analyte": "hba1c", "value": 7.8, "unit": "%",
                     "ref_range": "<7.0", "abnormal_flag": "high"},
    }

The attribute keys match exactly what `app/checks/*` read (analyte/value/
abnormal_flag, substance/reaction/severity, relation/condition/age_at_onset,
factor, drug), so a natural upload reproduces what the check tests seed by hand.
"""

from __future__ import annotations

import csv
import io
from typing import List, Optional

# --- analyte canonicalization -------------------------------------------------
# Free-text lab names -> the canonical token the checks + ontology key on. Kept
# small and substring-based; extend the map, not the callers.
# ponytail: substring match on a short table; a real LOINC map is the upgrade path.
_ANALYTE_ALIASES = {
    "hba1c": "hba1c", "a1c": "hba1c", "glycated": "hba1c",
    "ldl": "ldl", "hdl": "hdl", "triglyc": "triglycerides",
    "cholesterol": "cholesterol",
    "creatinine": "creatinine", "egfr": "egfr",
    "potassium": "potassium", "sodium": "sodium",
    "inr": "inr", "glucose": "glucose", "bmi": "bmi",
}

_ABNORMAL = {"high", "low", "abnormal", "critical", "h", "l"}
_FLAG_CANON = {"h": "high", "l": "low"}


def canonical_analyte(name: str) -> str:
    """'LDL cholesterol' -> 'ldl', 'HbA1c' -> 'hba1c'. Falls back to the first
    normalized token so unknown analytes still get a stable key."""
    n = (name or "").strip().lower()
    for alias, canon in _ANALYTE_ALIASES.items():
        if alias in n:
            return canon
    return n.split()[0] if n.split() else n


def canonical_flag(flag: str) -> str:
    f = (flag or "").strip().lower()
    return _FLAG_CANON.get(f, f)


def to_float(value) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


# --- assert builders ----------------------------------------------------------
def lab_assert(
    analyte_name: str,
    value,
    date: str,
    *,
    unit: str = "",
    ref_range: str = "",
    flag: str = "",
    source: str = "",
) -> dict:
    """One LabResult assert. `subject` is analyte-scoped ('lab hba1c') so the
    self-healing judge groups readings by analyte and never cross-supersedes an
    unrelated lab — while a rising series of the SAME analyte is retained as a
    trend."""
    analyte = canonical_analyte(analyte_name)
    num = to_float(value)
    flag_c = canonical_flag(flag)
    # No explicit flag but a numeric value + range we can compare? leave as given;
    # the synthetic data always carries a flag, so we trust it.
    label = f"{analyte_name.strip()} {value}".strip()
    if unit:
        label = f"{label} {unit}".strip()
    attributes = {"analyte": analyte}
    if num is not None:
        attributes["value"] = num
    if unit:
        attributes["unit"] = unit
    if ref_range:
        attributes["ref_range"] = ref_range
    if flag_c:
        attributes["abnormal_flag"] = flag_c
    return {
        "resource_type": "LabResult",
        "subject": f"lab {analyte}",
        "predicate": "measured",
        "value": label,
        "date": date,
        "source": source,
        "attributes": attributes,
    }


def family_assert(
    relation: str,
    condition: str,
    date: str,
    *,
    age_at_onset=None,
    relative_name: str = "",
    relative_mrn: str = "",
    relative_dob: str = "",
    source: str = "",
) -> dict:
    attributes = {"relation": relation.strip().lower(), "condition": condition.strip().lower()}
    if age_at_onset is not None:
        attributes["age_at_onset"] = age_at_onset
    # Relative identifiers drive automatic family linkage (family_resolver). Only
    # stored when actually present — a blank name must never match a real patient.
    if relative_name.strip():
        attributes["relative_name"] = relative_name.strip()
    if relative_mrn.strip():
        attributes["relative_mrn"] = relative_mrn.strip()
    if relative_dob.strip():
        attributes["relative_dob"] = relative_dob.strip()
    label = f"{relation.strip().title()}: {condition.strip()}"
    if age_at_onset is not None:
        label += f" (age {age_at_onset})"
    return {
        "resource_type": "FamilyHistory",
        "subject": "family",
        "predicate": "reported",
        "value": label,
        "date": date,
        "source": source,
        "attributes": attributes,
    }


def allergy_assert(
    substance: str,
    date: str,
    *,
    cleared: bool = False,
    reaction: str = "",
    severity: str = "",
    source: str = "",
) -> dict:
    attributes = {"substance": substance.strip().lower()}
    if reaction:
        attributes["reaction"] = reaction.strip()
    if severity:
        attributes["severity"] = severity.strip().lower()
    return {
        "resource_type": "Allergy",
        "subject": "allergy",
        "predicate": "cleared" if cleared else "diagnosed",
        "value": substance.strip(),
        "date": date,
        "source": source,
        "attributes": attributes,
    }


def medication_assert(drug: str, date: str, *, stopped: bool = False, source: str = "") -> dict:
    return {
        "resource_type": "Medication",
        "subject": "medication",
        "predicate": "stopped" if stopped else "prescribed",
        "value": drug.strip(),
        "date": date,
        "source": source,
        "attributes": {"drug": drug.strip().lower()},
    }


def condition_assert(condition: str, date: str, *, resolved: bool = False, source: str = "") -> dict:
    return {
        "resource_type": "Condition",
        "subject": "diagnosis",
        "predicate": "resolved" if resolved else "diagnosed",
        "value": condition.strip(),
        "date": date,
        "source": source,
        "attributes": {"condition": condition.strip().lower()},
    }


def lifestyle_assert(factor: str, value: str, date: str, *, source: str = "") -> dict:
    return {
        "resource_type": "Lifestyle",
        "subject": "lifestyle",
        "predicate": "reported",
        "value": value.strip() or factor.strip(),
        "date": date,
        "source": source,
        "attributes": {"factor": factor.strip().lower(), "value": value.strip()},
    }


# --- CSV lab-series parser ----------------------------------------------------
def is_csv(filename: str) -> bool:
    return filename.lower().endswith(".csv")


def parse_csv_labs(text: str, source: str = "") -> List[dict]:
    """Parse a tabular lab CSV into one LabResult assert per row.

    Expected columns (case-insensitive, flexible): date, test/analyte, value,
    unit, reference_range/ref_range, flag/interpretation. Non-numeric values
    (e.g. 'within normal limits') are kept as the label but carry no numeric
    `value`, so they never enter a trend."""
    rows = list(csv.DictReader(io.StringIO(text)))
    out: List[dict] = []
    for row in rows:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        analyte_name = r.get("test") or r.get("analyte") or r.get("name") or ""
        if not analyte_name:
            continue
        out.append(
            lab_assert(
                analyte_name,
                r.get("value", ""),
                r.get("date", ""),
                unit=r.get("unit", ""),
                ref_range=r.get("reference_range") or r.get("ref_range", ""),
                flag=r.get("flag") or r.get("interpretation", ""),
                source=r.get("source") or source,
            )
        )
    return out
