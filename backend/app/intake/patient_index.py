"""
Patient identity resolution.

Given a name + DOB (or MRN) extracted from a document, resolve to an existing
patient_id or create a new chart automatically.

ponytail: exact normalized name+DOB match only, no fuzzy/phonetic matching.
Upgrade to rapidfuzz only if duplicate-name collisions actually show up in testing.
"""

from __future__ import annotations

from typing import Optional

from app.memory import records


def _normalize(s: str) -> str:
    """Lowercase, strip, collapse whitespace, remove common punctuation."""
    return " ".join(s.lower().strip().replace("'", "").replace("-", " ").split())


def resolve(name: str, dob: str = "", mrn: str = "") -> str:
    """
    Find an existing patient or create a new one.
    Priority: MRN exact match > name+DOB exact match > create new.
    Returns patient_id.
    """
    patients = records.list_patients()

    # 1. MRN exact match (strongest signal)
    if mrn.strip():
        for p in patients:
            if p.get("mrn", "").strip().lower() == mrn.strip().lower():
                return p["patient_id"]

    # 2. Normalized name + DOB match
    norm_name = _normalize(name)
    norm_dob = dob.strip()
    if norm_name:
        for p in patients:
            p_name = _normalize(p.get("name", ""))
            p_dob = p.get("dob", "").strip()
            if p_name == norm_name:
                # If both have DOB, they must match; if either is missing, name alone is ok
                if not norm_dob or not p_dob or norm_dob == p_dob:
                    return p["patient_id"]

    # 3. No match — auto-create
    new = records.add_patient(name=name, dob=dob, mrn=mrn)
    return new["patient_id"]


def resolve_or_none(name: str, dob: str = "", mrn: str = "") -> Optional[str]:
    """Like resolve() but returns None if name is empty (can't identify)."""
    if not name.strip() and not mrn.strip():
        return None
    return resolve(name, dob, mrn)
