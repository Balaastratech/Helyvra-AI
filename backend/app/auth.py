"""
Simulated identity + access layer (CLINICAL_COPILOT_PLAN §7).

Deliberately thin and honest: a mock login (pick a doctor), a role, and a
per-doctor patient access list read from `data/access.json`. The ONE real
guarantee it enforces is a hard access boundary — a doctor cannot recall, order,
or resolve a patient not on their list. Real ABDM/ABHA consent + HIPAA safeguards
are the documented production path, not built (§11).

Pairs with `audit.py` (which IS real): every access decision this layer makes —
including a refusal — is auditable at the call site.

ponytail: access map is a flat JSON file loaded per call (tiny, 3 doctors). No
caching, no DB — upgrade to a table only if the doctor/patient sets grow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

_ACCESS_FILE = Path(__file__).resolve().parents[2] / "data" / "access.json"


def _load() -> List[dict]:
    if not _ACCESS_FILE.exists():
        return []
    return json.loads(_ACCESS_FILE.read_text(encoding="utf-8")).get("doctors", [])


def list_doctors() -> List[dict]:
    """The login picker's roster (id · name · specialty · role) — no patient lists."""
    return [
        {k: d[k] for k in ("doctor_id", "name", "specialty", "role") if k in d}
        for d in _load()
    ]


def get_doctor(doctor_id: str) -> Optional[dict]:
    return next((d for d in _load() if d.get("doctor_id") == doctor_id), None)


def allowed_patients(doctor_id: str) -> List[str]:
    """Patient ids this doctor may open. Empty list if the doctor is unknown."""
    d = get_doctor(doctor_id)
    return list(d.get("patients", [])) if d else []


def can_access(doctor_id: str, patient_id: str) -> bool:
    """The hard boundary: is this patient on this doctor's access list?"""
    return patient_id in allowed_patients(doctor_id)
