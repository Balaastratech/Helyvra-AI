"""
Automatic family linkage (Family-Auto-Linkage plan).

On normal ingest, detect when a patient's FamilyHistory names a relative who is
ALSO a patient, and link the two charts — no manual folders, no data entry, and
crucially NO requirement that anyone type the relative's medical-record number.

Matching uses only what a patient naturally provides (the relative's NAME and the
RELATION) plus corroborating signals ALREADY in the system — it never asks a
clinician to organize/cross-reference charts:

  * name        — normalized full-name match against existing patients;
  * surname     — the linking patient's own family name vs the candidate's
                  (relatives usually share it — a strong disambiguator);
  * generation  — the two patients' dates of birth must be age-plausible for the
                  stated relation (a "father" must be meaningfully OLDER than the
                  child; a 4-year gap rules a same-named candidate out). This is
                  what tells the two "Rahul Sharma" charts apart with no MRN;
  * relative_dob / relative_mrn — used ONLY if the document happens to state them
                  (bonus, near-certain identity), never required.

Confidence tiers (record-linkage practice): a near-certain identity (MRN or exact
DOB match) OR a single unambiguous name+surname+generation match → 'high' (auto-
consent). A unique name match without that corroboration, or the best of several
plausible candidates → 'medium' (proposed, never silently revealed — the clinician
confirms with one click). Links persist in data/family_links.json as reciprocal
edges. A best-effort Cognee `FamilyMember` Dedup graph mirrors them into the graph
for the Memory Map — but the JSON store is authoritative, so the feature works even
if Cognee is unavailable.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional

from app.intake.patient_index import _normalize
from app.memory import cognee_client, ledger, ontology, records

_LINKS_PATH = os.environ.get(
    "FAMILY_LINKS", str(Path(__file__).resolve().parents[3] / "data" / "family_links.json")
)

_INVERSE = {
    "father": "child", "mother": "child", "parent": "child",
    "son": "parent", "daughter": "parent", "child": "parent",
    "brother": "sibling", "sister": "sibling", "sibling": "sibling",
}

_PARENT_RELATIONS = {"father", "mother", "parent"}
_CHILD_RELATIONS = {"son", "daughter", "child"}
_SIBLING_RELATIONS = {"brother", "sister", "sibling"}

# Plausible birth-year gaps between two first-degree relatives. A parent is 12–70y
# older than the child; siblings within ~30y. Deliberately wide — the goal is to
# REJECT the impossible (a "father" 4 years older), not to over-constrain real
# families. ponytail: fixed bands, not per-locale actuarial tables — fine here;
# widen the constants if a real cohort surfaces a valid gap outside them.
_MIN_PARENT_GAP, _MAX_PARENT_GAP = 12, 70
_MAX_SIBLING_GAP = 30


def _birth_year(dob: str) -> Optional[int]:
    dob = (dob or "").strip()
    return int(dob[:4]) if len(dob) >= 4 and dob[:4].isdigit() else None


def _surname(name: str) -> str:
    """Last token of a normalized name ('Rahul Kumar Sharma' -> 'sharma')."""
    toks = _normalize(name).split()
    return toks[-1] if toks else ""


def _generation_plausible(relation: str, patient_dob: str, cand_dob: str) -> Optional[bool]:
    """Is the candidate age-plausible as `relation` of the patient?
    True/False when both DOBs are known; None when we can't tell (don't reject on
    missing data — absence of a birth year is not evidence of a bad match)."""
    py, cy = _birth_year(patient_dob), _birth_year(cand_dob)
    if py is None or cy is None:
        return None
    if relation in _PARENT_RELATIONS:      # candidate is the parent → older
        return _MIN_PARENT_GAP <= (py - cy) <= _MAX_PARENT_GAP
    if relation in _CHILD_RELATIONS:       # candidate is the child → younger
        return _MIN_PARENT_GAP <= (cy - py) <= _MAX_PARENT_GAP
    if relation in _SIBLING_RELATIONS:
        return abs(py - cy) <= _MAX_SIBLING_GAP
    return None


def _load() -> dict:
    if os.path.exists(_LINKS_PATH):
        try:
            return json.loads(Path(_LINKS_PATH).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"links": []}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_LINKS_PATH), exist_ok=True)
    Path(_LINKS_PATH).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _match_patient(
    patient: dict, relation: str, name: str, dob: str, mrn: str
) -> Optional[tuple[str, str]]:
    """Resolve a named relative to an existing patient using name + corroboration.
    Returns (patient_id, confidence) or None. Never requires an MRN.

    Ranking, high → low:
      1. relative_mrn matches a chart (bonus, if the document carried one)   → high
      2. relative_dob matches a same-named chart exactly                      → high
      3. exactly ONE name match that is generation-plausible AND shares the
         patient's surname                                                    → high
      4. a unique / best generation-plausible name match                      → medium
    Generation-IMPLAUSIBLE candidates (e.g. a 'father' younger than the child)
    are discarded, which is what disambiguates two same-named patients with no MRN."""
    patients = [p for p in records.list_patients() if p["patient_id"] != patient["patient_id"]]

    # 1. MRN — only if a document happened to include it (never required).
    if mrn.strip():
        for p in patients:
            if p.get("mrn", "").strip().lower() == mrn.strip().lower():
                return p["patient_id"], "high"

    nn = _normalize(name)
    if not nn:
        return None
    named = [p for p in patients if _normalize(p.get("name", "")) == nn]
    if not named:
        return None

    patient_surname = _surname(patient.get("name", ""))

    # 2. Exact relative-DOB match on a same-named chart → near-certain identity.
    if dob.strip():
        for p in named:
            if p.get("dob", "").strip() == dob.strip():
                return p["patient_id"], "high"

    # Keep candidates that are NOT provably generation-implausible (None = unknown
    # DOB, keep; True = plausible, keep; False = impossible for this relation, drop).
    plausible = [p for p in named if _generation_plausible(relation, patient.get("dob", ""), p.get("dob", "")) is not False]
    if not plausible:
        return None

    def _score(p: dict) -> tuple:
        gen = _generation_plausible(relation, patient.get("dob", ""), p.get("dob", "")) is True
        surname = bool(patient_surname) and _surname(p.get("name", "")) == patient_surname
        return (gen and surname, gen, surname)

    best = max(plausible, key=_score)
    top = _score(best)
    tied = [p for p in plausible if _score(p) == top]

    # 3. Unambiguous name + shared surname + confirmed generation gap → high.
    if len(tied) == 1 and top[0]:  # top[0] == (gen and surname)
        return best["patient_id"], "high"
    # 4. Otherwise a plausible-but-not-certain match → proposed for one-click confirm.
    return best["patient_id"], "medium"


def _upsert_link(data: dict, a: str, b: str, relation: str, confidence: str) -> None:
    """Insert a reciprocal edge (a→b relation, b→a inverse) if absent."""
    inverse = _INVERSE.get(relation, "relative")
    for src, tgt, rel in ((a, b, relation), (b, a, inverse)):
        if not any(l["patient_id"] == src and l["relative_id"] == tgt for l in data["links"]):
            data["links"].append({
                "patient_id": src, "relative_id": tgt, "relation": rel,
                "confidence": confidence, "consent": confidence == "high",
                "proposed": confidence != "high",
            })


def resolve_links(patient_id: str) -> List[dict]:
    """Scan this patient's family-history facts, link any relative who is a patient.
    Returns the NEW links created this call. Idempotent (existing edges are skipped)."""
    patient = next((p for p in records.list_patients() if p["patient_id"] == patient_id), None)
    if patient is None:
        return []
    data = _load()
    before = len(data["links"])
    created: List[dict] = []
    for f in ledger.all(patient_id):
        if f.resource_type != "FamilyHistory" or f.status == "retracted":
            continue
        attrs = f.attributes or {}
        relation = (attrs.get("relation") or "").strip().lower()
        if not ontology.is_first_degree(relation):
            continue
        name = attrs.get("relative_name", "")
        if not (name or attrs.get("relative_mrn")):
            continue
        match = _match_patient(
            patient, relation, name, attrs.get("relative_dob", ""), attrs.get("relative_mrn", "")
        )
        if match is None or match[0] == patient_id:
            continue
        relative_id, confidence = match
        n = len(data["links"])
        _upsert_link(data, patient_id, relative_id, relation, confidence)
        if len(data["links"]) > n:
            created.append({"patient_id": patient_id, "relative_id": relative_id,
                            "relation": relation, "confidence": confidence})
    if len(data["links"]) != before:
        _save(data)
        _mirror_to_cognee(data)
    return created


def _mirror_to_cognee(data: dict) -> None:
    """Best-effort: push the current family graph into Cognee (fire-and-forget)."""
    patients = {p["patient_id"]: p for p in records.list_patients()}
    # child → parent edges only (avoids duplicate inverse edges in the graph)
    child_rel = {"child"}
    members: list[dict] = []
    seen: set[str] = set()
    for l in data["links"]:
        p = patients.get(l["patient_id"])
        if not p or p["mrn"] in seen:
            continue
        parent_mrn = None
        if l["relation"] in child_rel:
            rp = patients.get(l["relative_id"])
            parent_mrn = rp["mrn"] if rp else None
        members.append({"patient_id": p["patient_id"], "name": p["name"],
                        "mrn": p["mrn"], "parent_mrn": parent_mrn})
        seen.add(p["mrn"])
    if not members:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None  # no running loop (sync test / CLI) — skip; JSON store is authoritative
    if loop is not None:
        loop.create_task(cognee_client.add_family_members(members))


def links_for(patient_id: str, consented_only: bool = False) -> List[dict]:
    links = [l for l in _load()["links"] if l["patient_id"] == patient_id]
    return [l for l in links if l.get("consent")] if consented_only else links


def set_consent(patient_id: str, relative_id: str, consent: bool) -> bool:
    """Toggle consent on BOTH directions of a link. Returns True if a link changed."""
    data = _load()
    changed = False
    for l in data["links"]:
        if {l["patient_id"], l["relative_id"]} == {patient_id, relative_id}:
            l["consent"] = consent
            changed = True
    if changed:
        _save(data)
    return changed
