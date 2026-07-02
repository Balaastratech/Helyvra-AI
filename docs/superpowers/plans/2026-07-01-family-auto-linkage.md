# Family Auto-Linkage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a patient's records are ingested normally, the system **automatically** detects when a named relative is also a patient, links the two charts (deduplicated, no manual folders), and — behind a consent gate — raises hereditary-risk cards that reason over the *relative's actual diagnoses*, not just the self-reported family-history note.

**Architecture:** Follows the project's established pattern — a **deterministic authoritative store** (`data/family_links.json`, like the ledger) plus a **best-effort Cognee graph layer** (`FamilyMember` DataPoints with `Dedup()` identity + `related_to` edges, like Cognee's role next to the ledger). Extraction is extended to capture the relative's identifiers; a new `family_resolver` matches them to existing patients (MRN > name+DOB, reusing `patient_index` normalization) with **tiered confidence** (strong match auto-links; weak match is proposed, never silently merged); a new `hereditary` check traverses consented links. Isolation stays the default — no clinical detail crosses a chart without a consented link.

**Tech Stack:** Python 3.13, FastAPI, cognee 1.2.2 (`DataPoint`/`Dedup`/`Embeddable` from `cognee.infrastructure.engine`, `add_data_points` from `cognee.tasks.storage.add_data_points` — both verified present), pytest (monkeypatch + `asyncio.run`, matching `tests/test_engine.py` style).

---

## Files

- Modify: `backend/app/intake/structured.py` — `family_assert` gains relative identifiers.
- Modify: `backend/app/intake/fhir.py` — parse `FamilyMemberHistory.name`.
- Modify: `backend/app/engine/extract.py` — rich extractor captures relative name/dob.
- Create: `backend/app/intake/family_resolver.py` — match relatives → links, persist, best-effort Cognee graph.
- Modify: `backend/app/memory/cognee_client.py` — `add_family_members` (Dedup DataPoint graph).
- Modify: `backend/app/intake/pipeline.py` — run resolution after ingest.
- Create: `backend/app/checks/hereditary.py` — consent-gated hereditary check.
- Modify: `backend/app/checks/engine.py` — register the check.
- Modify: `backend/app/memory/ontology.py` — `is_heritable(condition)` helper.
- Create: `backend/app/api/routes_family.py` — links + consent-toggle endpoints.
- Modify: `backend/app/main.py` — mount the family router.
- Create: `data/family_links.json` (+ demo son patient in `data/patients_user.json` via intake).
- Test: `backend/tests/test_family.py` (new).

---

## Task 0: Verify Cognee DataPoint/Dedup APIs (no plan rests on an assumption)

- [ ] **Step 1: Run the import check**

Run:
```
cd backend && .venv/Scripts/python.exe -c "from cognee.infrastructure.engine import DataPoint, Dedup, Embeddable; from cognee.tasks.storage.add_data_points import add_data_points; print('family graph APIs OK')" 2>&1 | tail -1
```
Expected: `family graph APIs OK` (verified in this planning session). If it ever fails, the JSON-link store (Task 3) is the authoritative fallback and the whole feature still works — the Cognee graph (Task 4) is the additive "best use of Cognee" layer.

- [ ] **Step 2: No commit** (verification only)

---

## Task 1: `family_assert` carries the relative's identifiers

**Files:**
- Modify: `backend/app/intake/structured.py:113-135`
- Test: `backend/tests/test_family.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_family.py
"""Family auto-linkage (relative extraction → resolver → hereditary check)."""
from __future__ import annotations

from app.intake import structured as S


def test_family_assert_carries_relative_identity():
    a = S.family_assert(
        "father", "myocardial infarction", "2023-01-15",
        age_at_onset=49, relative_name="Rahul Sharma", relative_mrn="MRN-2010",
        relative_dob="1974-02-03", source="intake",
    )
    attrs = a["attributes"]
    assert attrs["relation"] == "father"
    assert attrs["condition"] == "myocardial infarction"
    assert attrs["relative_name"] == "Rahul Sharma"
    assert attrs["relative_mrn"] == "MRN-2010"
    assert attrs["relative_dob"] == "1974-02-03"


def test_family_assert_omits_blank_relative_fields():
    a = S.family_assert("mother", "breast cancer", "2022-05-01")
    assert "relative_name" not in a["attributes"]
    assert a["attributes"]["relation"] == "mother"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py::test_family_assert_carries_relative_identity -v`
Expected: FAIL — `family_assert` has no `relative_name` parameter (`TypeError`).

- [ ] **Step 3: Extend `family_assert`**

Replace `family_assert` in `backend/app/intake/structured.py` (lines 113-135):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_family.py -v`
Expected: PASS (both)

- [ ] **Step 5: Run structured-intake regression**

Run: `cd backend && python -m pytest tests/ -k "intake or fhir or family" -v`
Expected: PASS (additive optional params — existing callers unaffected).

- [ ] **Step 6: Commit**

```bash
git add backend/app/intake/structured.py backend/tests/test_family.py
git commit -m "feat: family_assert carries relative identifiers for linkage"
```

---

## Task 2: Extract the relative's identifiers (FHIR + free text)

**Files:**
- Modify: `backend/app/intake/fhir.py:135-145` (`_parse_family_history`)
- Modify: `backend/app/engine/extract.py:126-193` (`_RichFact`, `_RICH_SYSTEM`, `_rich_fact_to_assert`)
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: Write the failing test (FHIR parse)**

```python
# add to backend/tests/test_family.py
from app.intake import fhir


def test_fhir_family_history_captures_relative_name():
    res = {
        "resourceType": "FamilyMemberHistory",
        "name": "Rahul Sharma",
        "relationship": {"text": "father"},
        "date": "2023-01-15",
        "condition": [{"code": {"text": "myocardial infarction"},
                       "onsetAge": {"value": 49}}],
    }
    facts = fhir._parse_family_history(res)
    assert facts[0]["attributes"]["relative_name"] == "Rahul Sharma"
    assert facts[0]["attributes"]["relation"] == "father"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py::test_fhir_family_history_captures_relative_name -v`
Expected: FAIL — `relative_name` not in attributes.

- [ ] **Step 3: Pass the FHIR relative name through**

In `backend/app/intake/fhir.py`, change `_parse_family_history` (lines 135-145):

```python
def _parse_family_history(res: dict) -> List[dict]:
    relation = _codeable_text(res.get("relationship", {})) or "relative"
    dt = _to_date(res.get("date") or "")
    source = res.get("_source") or _recorder(res)
    # FHIR FamilyMemberHistory.name is the relative's name — the linkage key.
    relative_name = res.get("name", "") if isinstance(res.get("name"), str) else ""
    out: List[dict] = []
    for cond in res.get("condition", []):
        condition = _codeable_text(cond.get("code", {})) or "condition"
        onset = cond.get("onsetAge") or {}
        age = onset.get("value") if isinstance(onset, dict) else None
        out.append(S.family_assert(
            relation, condition, dt, age_at_onset=age,
            relative_name=relative_name, source=source,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_family.py::test_fhir_family_history_captures_relative_name -v`
Expected: PASS

- [ ] **Step 5: Extend the free-text rich extractor**

In `backend/app/engine/extract.py`: (a) add to the `_RICH_SYSTEM` FamilyHistory bullet (line ~126) so the model captures the relative's name/DOB — change the FamilyHistory line to:

```python
    "- FamilyHistory: relation ('father','mother',...), condition, age_at_onset "
    "(number, if stated), relative_name (the relative's full name if stated, e.g. "
    "'Rahul Sharma'), relative_dob (ISO date if stated).\n"
```

(b) add the two fields to `_RichFact` (after `factor: str = ""`, line ~153):

```python
    relative_name: str = ""
    relative_dob: str = ""
```

(c) in `_rich_fact_to_assert`, change the `familyhistory` branch (lines ~188-193):

```python
    if rt == "familyhistory":
        condition = f.condition or f.value
        if not (f.relation and condition):
            return None
        age = f.age_at_onset if f.age_at_onset else None
        return S.family_assert(
            f.relation, condition, dt, age_at_onset=age,
            relative_name=f.relative_name, relative_dob=f.relative_dob, source=source,
        )
```

- [ ] **Step 6: Write a test for the mapping function (deterministic, no LLM)**

```python
# add to backend/tests/test_family.py
from app.engine import extract as extract_mod


def test_rich_family_fact_maps_relative_name():
    rf = extract_mod._RichFact(
        resource_type="FamilyHistory", relation="father",
        condition="coronary artery disease", age_at_onset=49,
        relative_name="Rahul Sharma", relative_dob="1974-02-03",
    )
    a = extract_mod._rich_fact_to_assert(rf, "2023-01-15", "intake_form.txt")
    assert a["attributes"]["relative_name"] == "Rahul Sharma"
    assert a["attributes"]["relative_dob"] == "1974-02-03"
```

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest tests/test_family.py -v`
Expected: PASS (all family tests so far)

- [ ] **Step 8: Commit**

```bash
git add backend/app/intake/fhir.py backend/app/engine/extract.py backend/tests/test_family.py
git commit -m "feat: extract relative identifiers from FHIR + free text"
```

---

## Task 3: `family_resolver` — match relatives to patients + persist links

**Files:**
- Create: `backend/app/intake/family_resolver.py`
- Test: `backend/tests/test_family.py`

Design: for each of a patient's FamilyHistory facts that carries a relative identifier, match against existing patients (MRN exact > normalized name+DOB) and, when a **first-degree** relative resolves to a real patient, record a link. Links persist in `data/family_links.json` as reciprocal edges with a confidence tier and a consent flag.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
import json
from datetime import date

from app.memory.schema import ClinicalFact


def _fh_fact(pid, relation, condition, relative_name="", relative_mrn="", age=None):
    attrs = {"relation": relation, "condition": condition}
    if relative_name:
        attrs["relative_name"] = relative_name
    if relative_mrn:
        attrs["relative_mrn"] = relative_mrn
    if age is not None:
        attrs["age_at_onset"] = age
    return ClinicalFact(
        patient_id=pid, subject="family", predicate="reported",
        value=f"{relation}: {condition}", valid_from=date(2023, 1, 15),
        source="intake", resource_type="FamilyHistory", attributes=attrs,
    )


def test_resolver_links_relative_that_is_a_patient(tmp_path, monkeypatch):
    from app.intake import family_resolver as fr

    # Point the link store at a temp file.
    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))

    patients = [
        {"patient_id": "P010", "name": "Rahul Sharma", "dob": "1974-02-03", "mrn": "MRN-2010"},
        {"patient_id": "P020", "name": "Arjun Sharma", "dob": "1999-06-01", "mrn": "MRN-2020"},
    ]
    monkeypatch.setattr(fr.records, "list_patients", lambda: patients)

    facts = [_fh_fact("P020", "father", "coronary artery disease",
                      relative_mrn="MRN-2010", age=49)]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts if pid == "P020" else [])

    links = fr.resolve_links("P020")
    assert len(links) == 1
    assert links[0]["patient_id"] == "P020"
    assert links[0]["relative_id"] == "P010"
    assert links[0]["relation"] == "father"
    assert links[0]["confidence"] == "high"      # matched by MRN
    # Reciprocal edge persisted so P010 also knows about the child.
    stored = json.loads((tmp_path / "family_links.json").read_text())
    pairs = {(l["patient_id"], l["relative_id"]) for l in stored["links"]}
    assert ("P020", "P010") in pairs and ("P010", "P020") in pairs


def test_resolver_no_link_when_relative_unknown(tmp_path, monkeypatch):
    from app.intake import family_resolver as fr
    monkeypatch.setattr(fr, "_LINKS_PATH", str(tmp_path / "family_links.json"))
    monkeypatch.setattr(fr.records, "list_patients",
                        lambda: [{"patient_id": "P020", "name": "Arjun Sharma", "dob": "", "mrn": "MRN-2020"}])
    facts = [_fh_fact("P020", "father", "coronary artery disease", relative_name="Someone Nobody")]
    monkeypatch.setattr(fr.ledger, "all", lambda pid: facts)
    assert fr.resolve_links("P020") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k resolver -v`
Expected: FAIL — `app.intake.family_resolver` does not exist.

- [ ] **Step 3: Write `family_resolver.py`**

```python
# backend/app/intake/family_resolver.py
"""
Automatic family linkage (Family-Auto-Linkage plan).

On normal ingest, detect when a patient's FamilyHistory names a relative who is
ALSO a patient, and link the two charts — no manual folders, no data entry.

Matching is tiered (record-linkage / EMPI practice): a strong identity match
(MRN, or normalized name+DOB) auto-links with confidence 'high'; a name-only
match is 'medium' and marked proposed (not silently merged). Links persist in
data/family_links.json as reciprocal edges. A best-effort Cognee `FamilyMember`
Dedup graph (cognee_client.add_family_members) mirrors the links into the graph
for the Memory Map — but the JSON store is authoritative, so the feature works
even if Cognee is unavailable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from app.intake.patient_index import _normalize
from app.memory import ledger, ontology, records

_LINKS_PATH = os.environ.get(
    "FAMILY_LINKS", str(Path(__file__).resolve().parents[3] / "data" / "family_links.json")
)


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


def _match_patient(name: str, dob: str, mrn: str) -> Optional[tuple[str, str]]:
    """(patient_id, confidence) for the best match, or None. MRN > name+DOB > name."""
    patients = records.list_patients()
    if mrn.strip():
        for p in patients:
            if p.get("mrn", "").strip().lower() == mrn.strip().lower():
                return p["patient_id"], "high"
    nn = _normalize(name)
    if nn:
        # name + DOB = high; name alone = medium (proposed).
        for p in patients:
            if _normalize(p.get("name", "")) == nn:
                pd = p.get("dob", "").strip()
                if dob.strip() and pd and dob.strip() == pd:
                    return p["patient_id"], "high"
        for p in patients:
            if _normalize(p.get("name", "")) == nn:
                return p["patient_id"], "medium"
    return None


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


_INVERSE = {
    "father": "child", "mother": "child", "parent": "child",
    "son": "parent", "daughter": "parent", "child": "parent",
    "brother": "sibling", "sister": "sibling", "sibling": "sibling",
}


def resolve_links(patient_id: str) -> List[dict]:
    """Scan this patient's family-history facts, link any relative who is a patient.
    Returns the NEW links created this call. Idempotent (existing edges are skipped)."""
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
        match = _match_patient(name, attrs.get("relative_dob", ""), attrs.get("relative_mrn", ""))
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
    return created


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_family.py -k resolver -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add backend/app/intake/family_resolver.py backend/tests/test_family.py
git commit -m "feat: family_resolver links relatives who are patients (tiered, consented)"
```

---

## Task 4: Best-effort Cognee `FamilyMember` Dedup graph

**Files:**
- Modify: `backend/app/memory/cognee_client.py` (append `add_family_members`)
- Modify: `backend/app/intake/family_resolver.py` (`resolve_links` calls it)
- Test: `backend/tests/test_family.py`

Design: mirror the links into a Cognee graph so the relationship is real Cognee data (the "best use of Cognee" layer). `Dedup(mrn)` makes the father one node whether he appears as a patient or a relative. Best-effort — never raises (the JSON store is authoritative).

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
import asyncio


def test_add_family_members_builds_dedup_datapoints(monkeypatch):
    captured = {}

    async def fake_add_dp(points, **kw):
        captured["points"] = points

    from app.memory import cognee_client
    monkeypatch.setattr(cognee_client, "_add_data_points", fake_add_dp)

    members = [
        {"patient_id": "P020", "name": "Arjun Sharma", "mrn": "MRN-2020",
         "relation_to_parent": "child", "parent_mrn": "MRN-2010"},
        {"patient_id": "P010", "name": "Rahul Sharma", "mrn": "MRN-2010",
         "relation_to_parent": None, "parent_mrn": None},
    ]
    asyncio.run(cognee_client.add_family_members(members))
    pts = captured["points"]
    by_mrn = {p.mrn: p for p in pts}
    # The child points at the SAME parent node (dedup by mrn).
    assert by_mrn["MRN-2020"].parent is not None
    assert by_mrn["MRN-2020"].parent.mrn == "MRN-2010"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k add_family_members -v`
Expected: FAIL — `add_family_members` / `_add_data_points` do not exist.

- [ ] **Step 3: Implement `add_family_members`**

Append to `backend/app/memory/cognee_client.py`:

```python
# --- family graph (Dedup DataPoints, §A.3) --------------------------------
FAMILY_DATASET = "family_graph"


async def _add_data_points(points, **kwargs):
    """Seam over Cognee's add_data_points (import kept local so a version change
    is one edit, and tests can monkeypatch this without importing cognee)."""
    from cognee.tasks.storage.add_data_points import add_data_points
    return await add_data_points(points, **kwargs)


def _family_datapoint_class():
    """Build the FamilyMember DataPoint class lazily (import-safe)."""
    from typing import Optional as _Opt
    from typing import Annotated
    from cognee.infrastructure.engine import DataPoint, Dedup, Embeddable

    class FamilyMember(DataPoint):
        mrn: Annotated[str, Dedup()]           # identity → same person = one node across charts
        name: Annotated[str, Embeddable()]
        patient_id: str = ""
        parent: "_Opt[FamilyMember]" = None    # typed ref → edge child --parent--> parent

    FamilyMember.model_rebuild()
    return FamilyMember


async def add_family_members(members: list[dict]) -> None:
    """Materialize kinship into the Cognee graph via Dedup DataPoints. Best-effort:
    the JSON link store (family_resolver) is authoritative; this is the graph layer
    for the Memory Map. `members` items: {patient_id, name, mrn, parent_mrn}."""
    try:
        FamilyMember = _family_datapoint_class()
        by_mrn: dict = {}
        for m in members:
            by_mrn[m["mrn"]] = FamilyMember(
                mrn=m["mrn"], name=m.get("name", ""), patient_id=m.get("patient_id", ""),
            )
        for m in members:
            pm = m.get("parent_mrn")
            if pm and pm in by_mrn:
                by_mrn[m["mrn"]].parent = by_mrn[pm]
        await _add_data_points(list(by_mrn.values()), dataset_name=FAMILY_DATASET)
    except Exception:  # pragma: no cover - graph is best-effort; JSON store is truth
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_family.py -k add_family_members -v`
Expected: PASS

- [ ] **Step 5: Wire the graph build into the resolver**

In `backend/app/intake/family_resolver.py`, at the end of `resolve_links`, after `_save(...)`, add a best-effort graph mirror (build the member list from the current links and schedule it). Add near the top: `import asyncio` and `from app.memory import cognee_client`. Then, replace the tail of `resolve_links`:

```python
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
        asyncio.get_event_loop().create_task(cognee_client.add_family_members(members))
    except RuntimeError:  # no running loop (e.g. sync test/CLI) — run inline, best-effort
        try:
            asyncio.run(cognee_client.add_family_members(members))
        except Exception:  # pragma: no cover
            pass
```

- [ ] **Step 6: Run the family suite**

Run: `cd backend && python -m pytest tests/test_family.py -v`
Expected: PASS (the resolver tests still pass; `_mirror_to_cognee` is best-effort and monkeypatched-safe — in the resolver tests `records.list_patients` is stubbed and `add_family_members` swallows any error).

- [ ] **Step 7: Commit**

```bash
git add backend/app/memory/cognee_client.py backend/app/intake/family_resolver.py
git commit -m "feat: mirror family links into a Cognee Dedup DataPoint graph"
```

---

## Task 5: Run family resolution automatically after ingest

**Files:**
- Modify: `backend/app/intake/pipeline.py:156-169`
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
def test_pipeline_runs_family_resolution(monkeypatch):
    called = {}
    from app.intake import pipeline as pl

    def fake_resolve(pid):
        called["pid"] = pid
        return []

    monkeypatch.setattr(pl, "family_resolver", type("M", (), {"resolve_links": staticmethod(fake_resolve)}))
    pl._resolve_family_safe("P020")
    assert called["pid"] == "P020"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k pipeline_runs_family -v`
Expected: FAIL — `pipeline._resolve_family_safe` and the `family_resolver` import don't exist.

- [ ] **Step 3: Add the hook**

In `backend/app/intake/pipeline.py`, add the import near the others (line ~29): `from app.intake import family_resolver`. Add a helper above `run`:

```python
def _resolve_family_safe(patient_id: str) -> None:
    """Automatic family linkage — best-effort so it never breaks an ingest."""
    try:
        family_resolver.resolve_links(patient_id)
    except Exception:  # pragma: no cover - linkage is additive, never fatal
        pass
```

Then in `run`, right before `patient = records.get_patient(patient_id)` (line ~158, after `_run_ingest`), add:

```python
    # Auto-link family: a relative named in this document may be another patient.
    _resolve_family_safe(patient_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_family.py -k pipeline_runs_family -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/intake/pipeline.py backend/tests/test_family.py
git commit -m "feat: run family linkage automatically after ingest"
```

---

## Task 6: `is_heritable` ontology helper

**Files:**
- Modify: `backend/app/memory/ontology.py` (add helper near `family_risk_for`, ~line 128)
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
from app.memory import ontology


def test_is_heritable():
    assert ontology.is_heritable("type 2 diabetes") is True
    assert ontology.is_heritable("coronary artery disease") is True
    assert ontology.is_heritable("sprained ankle") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k is_heritable -v`
Expected: FAIL — `ontology.is_heritable` doesn't exist.

- [ ] **Step 3: Add the helper**

In `backend/app/memory/ontology.py`, after `family_risk_for` (line ~130):

```python
def is_heritable(condition: str) -> bool:
    """True if a condition confers a familial/hereditary risk (i.e. a relative
    having it matters for the patient). Reuses the FAMILY_RISK vocabulary — one
    source of truth for both the family-history read and the hereditary check."""
    return family_risk_for(condition) is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_family.py -k is_heritable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/ontology.py backend/tests/test_family.py
git commit -m "feat: ontology.is_heritable helper"
```

---

## Task 7: `hereditary` check — consent-gated, traverses linked relatives' real diagnoses

**Files:**
- Create: `backend/app/checks/hereditary.py`
- Modify: `backend/app/checks/engine.py:19-24`
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
from app.checks import hereditary


def _condition_fact(pid, condition, dt=date(2023, 1, 1)):
    return ClinicalFact(
        patient_id=pid, subject="diagnosis", predicate="diagnosed", value=condition,
        valid_from=dt, source="Dr. Test", resource_type="Condition",
        attributes={"condition": condition.lower()},
    )


def test_hereditary_card_when_consented_relative_has_heritable_dx(monkeypatch):
    # P020's father P010 (consented link) actually has type 2 diabetes.
    monkeypatch.setattr(hereditary.family_resolver, "links_for",
                        lambda pid, consented_only=False: (
                            [{"patient_id": "P020", "relative_id": "P010", "relation": "father",
                              "confidence": "high", "consent": True}] if pid == "P020" else []))
    monkeypatch.setattr(hereditary.ledger, "all",
                        lambda pid: [_condition_fact("P010", "type 2 diabetes")] if pid == "P010" else [])
    monkeypatch.setattr(hereditary.records, "get_patient",
                        lambda pid: {"patient_id": pid, "name": "Rahul Sharma", "mrn": "MRN-2010"})

    cards = hereditary.run("P020")
    assert len(cards) == 1
    assert cards[0].indicator == "warning"
    assert "type 2 diabetes" in cards[0].detail.lower()
    assert "father" in cards[0].detail.lower()


def test_hereditary_degrades_without_consent(monkeypatch):
    monkeypatch.setattr(hereditary.family_resolver, "links_for",
                        lambda pid, consented_only=False: (
                            [{"patient_id": "P020", "relative_id": "P010", "relation": "father",
                              "confidence": "high", "consent": False}] if pid == "P020" else []))
    monkeypatch.setattr(hereditary.ledger, "all",
                        lambda pid: [_condition_fact("P010", "type 2 diabetes")] if pid == "P010" else [])
    monkeypatch.setattr(hereditary.records, "get_patient",
                        lambda pid: {"patient_id": pid, "name": "Rahul Sharma", "mrn": "MRN-2010"})

    cards = hereditary.run("P020")
    # No consent → no identifying detail leaks; either no card or a non-identifying one.
    for c in cards:
        assert "rahul" not in c.detail.lower()
        assert "MRN-2010" not in c.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k hereditary -v`
Expected: FAIL — `app.checks.hereditary` doesn't exist.

- [ ] **Step 3: Write the check**

```python
# backend/app/checks/hereditary.py
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
```

- [ ] **Step 4: Register the check**

In `backend/app/checks/engine.py`, change the import (line 19) and `OPEN_CHECKS` (line 24):

```python
from app.checks import allergy, followup, hereditary, risk
```
```python
OPEN_CHECKS = [allergy, followup, risk, hereditary]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_family.py -k hereditary -v`
Expected: PASS (both)

- [ ] **Step 6: Run the checks-engine regression**

Run: `cd backend && python -m pytest tests/ -k "check or engine" -v`
Expected: PASS (hereditary returns [] for patients with no links, so existing single-patient checks are unaffected).

- [ ] **Step 7: Commit**

```bash
git add backend/app/checks/hereditary.py backend/app/checks/engine.py backend/tests/test_family.py
git commit -m "feat: consent-gated hereditary check over linked relatives' diagnoses"
```

---

## Task 8: Family API — list links + consent toggle

**Files:**
- Create: `backend/app/api/routes_family.py`
- Modify: `backend/app/main.py` (mount the router)
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_family.py
from fastapi.testclient import TestClient


def test_family_routes(monkeypatch):
    from app.api import routes_family
    monkeypatch.setattr(routes_family.family_resolver, "links_for",
                        lambda pid, consented_only=False: [
                            {"patient_id": pid, "relative_id": "P010", "relation": "father",
                             "confidence": "high", "consent": True}])
    monkeypatch.setattr(routes_family.family_resolver, "set_consent",
                        lambda a, b, c: True)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(routes_family.router)
    client = TestClient(app)

    r = client.get("/family/P020")
    assert r.status_code == 200
    assert r.json()["links"][0]["relative_id"] == "P010"

    r = client.post("/family/consent", json={"patient_id": "P020", "relative_id": "P010", "consent": False})
    assert r.status_code == 200 and r.json()["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_family.py -k family_routes -v`
Expected: FAIL — `app.api.routes_family` doesn't exist.

- [ ] **Step 3: Write the router**

```python
# backend/app/api/routes_family.py
"""Family links + consent — the consent gate's control surface (§A.4)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.intake import family_resolver

router = APIRouter(tags=["family"])


class ConsentRequest(BaseModel):
    patient_id: str
    relative_id: str
    consent: bool


@router.get("/family/{patient_id}")
def family_links(patient_id: str) -> dict:
    """All family links for a patient (both consented and proposed)."""
    return {"patient_id": patient_id, "links": family_resolver.links_for(patient_id)}


@router.post("/family/consent")
def set_consent(req: ConsentRequest) -> dict:
    changed = family_resolver.set_consent(req.patient_id, req.relative_id, req.consent)
    return {"ok": changed, "consent": req.consent}
```

- [ ] **Step 4: Mount it**

In `backend/app/main.py`, add to the imports (with the other `from app.api import ...`): include `routes_family`, and add `app.include_router(routes_family.router)` next to the other `include_router` calls.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_family.py -k family_routes -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes_family.py backend/app/main.py backend/tests/test_family.py
git commit -m "feat: family links + consent-toggle API"
```

---

## Task 9: Demo family data (the "system linked them itself" moment)

**Files:**
- Create: `data/sample_uploads/P020_intake_form.txt` (a son's intake naming the father)
- Create/update: `clinical_copilot_synthetic_data` note — document the demo family in `data/family_links.json` is produced by ingest, NOT hand-seeded (the whole point is auto-linkage).

- [ ] **Step 1: Author the son's intake note (names the father, who is P010)**

Create `data/sample_uploads/P020_intake_form.txt`:

```
New patient intake — Arjun Sharma, DOB 1999-06-01, MRN-2020.
Reason for visit: routine check, family history review.
Lifestyle: non-smoker, exercises weekly.
Family history: Father — Rahul Sharma, MRN-2010 — has type 2 diabetes and had a
myocardial infarction at age 49. Mother — no significant history.
Demo only — synthetic data, not medical advice.
```

- [ ] **Step 2: Manual end-to-end verification (real ingest → auto-link → card)**

Run the backend, then:
```
cd backend && .venv/Scripts/python.exe -c "
import asyncio
from app.intake import pipeline
raw = open(r'..\data\sample_uploads\P020_intake_form.txt','rb').read()
res = asyncio.run(pipeline.run(raw, 'P020_intake_form.txt'))
print('patient:', res.patient_id, res.patient_name, 'created:', res.created_patient)
from app.intake import family_resolver
print('links:', family_resolver.links_for(res.patient_id))
from app.checks import hereditary
print('hereditary cards:', [c.summary for c in hereditary.run(res.patient_id)])
"
```
Expected: a new son patient is created; a `father → P010` link appears (matched by MRN-2010); after enabling consent (auto for high-confidence), the hereditary check names the father's type 2 diabetes. (This exercises the WHOLE chain: extraction → resolver → link → check.)

- [ ] **Step 3: Commit**

```bash
git add data/sample_uploads/P020_intake_form.txt
git commit -m "data: demo son intake that auto-links to father P010"
```

---

## Task 10: UI — family panel + consent toggle

**Files:**
- Read first: `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, and the patient-workspace right rail (`frontend/src/components/clinical/PreVisitBrief.tsx` or the right-rail container) to match style.
- Create: `frontend/src/components/clinical/FamilyPanel.tsx`

Context: hereditary cards already flow to the pre-visit brief + chat through the existing `cards` mechanism (Task 7 registered the check) — so the *reasoning* surfaces with zero UI work. This task adds the **consent control** + a small family-links view so the consent gate is visible and toggleable.

- [ ] **Step 1: Add the API client methods**

In `frontend/src/api/client.ts`, add (matching the existing method style):

```typescript
  family: (patientId: string) =>
    request<{ patient_id: string; links: FamilyLink[] }>(`/family/${patientId}`),
  setFamilyConsent: (body: { patient_id: string; relative_id: string; consent: boolean }) =>
    request<{ ok: boolean; consent: boolean }>(`/family/consent`, { method: 'POST', body: JSON.stringify(body) }),
```

And in `frontend/src/api/types.ts` add:

```typescript
export interface FamilyLink {
  patient_id: string
  relative_id: string
  relation: string
  confidence: 'high' | 'medium'
  consent: boolean
  proposed?: boolean
}
```

(Match the exact `request`/method signatures already used in `client.ts` — read it first; the snippet above assumes a `request<T>(path, init?)` helper, adapt to whatever the file actually exposes.)

- [ ] **Step 2: Create `FamilyPanel.tsx`**

```tsx
// frontend/src/components/clinical/FamilyPanel.tsx
import { useEffect, useState } from 'react'
import { Users, ShieldCheck, ShieldAlert } from 'lucide-react'
import { api } from '@/api/client'
import type { FamilyLink } from '@/api/types'

/** The consent gate, made visible. Auto-detected family links; toggling consent
 * is what lets the hereditary check reveal a relative's real diagnosis. */
export function FamilyPanel({ patientId }: { patientId: string }) {
  const [links, setLinks] = useState<FamilyLink[]>([])
  useEffect(() => {
    api.family(patientId).then((r) => setLinks(r.links)).catch(() => setLinks([]))
  }, [patientId])
  if (links.length === 0) return null

  async function toggle(l: FamilyLink) {
    await api.setFamilyConsent({ patient_id: l.patient_id, relative_id: l.relative_id, consent: !l.consent })
    setLinks((prev) => prev.map((x) => (x.relative_id === l.relative_id ? { ...x, consent: !x.consent } : x)))
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <Users className="h-3.5 w-3.5" /> Family (auto-linked)
      </div>
      <ul className="mt-2 space-y-1.5">
        {links.map((l) => (
          <li key={l.relative_id} className="flex items-center justify-between gap-2 text-xs">
            <span className="text-text">
              {l.relation} · <span className="text-text-muted">{l.relative_id}</span>
              {l.proposed && <span className="ml-1 text-amber-500">(proposed)</span>}
            </span>
            <button
              onClick={() => toggle(l)}
              className={l.consent
                ? 'inline-flex items-center gap-1 rounded-full border border-active/40 bg-active-soft px-2 py-0.5 text-active'
                : 'inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-text-muted'}
              title="Consent controls whether hereditary checks may read this relative's records"
            >
              {l.consent ? <ShieldCheck className="h-3 w-3" /> : <ShieldAlert className="h-3 w-3" />}
              {l.consent ? 'consented' : 'no consent'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 3: Render it in the patient workspace right rail**

Read the right-rail container (grep for where `PreVisitBrief` or the "Doctor might miss" panel is composed — likely `frontend/src/pages/*` or `ClinicalShell.tsx`), and add `<FamilyPanel patientId={patientId} />` beside the existing panels. Match the existing spacing/wrapper.

- [ ] **Step 4: Manual verification**

Run backend + `npm run dev`; ingest the son (Task 9); open the son's chart; confirm the Family panel shows the auto-detected `father · P010` link and a consent toggle, and that toggling it changes whether the hereditary card names the father's diagnosis.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/types.ts frontend/src/components/clinical/FamilyPanel.tsx frontend/src/pages
git commit -m "feat: family panel + consent toggle in the patient workspace"
```

(Adjust the `git add` for the exact right-rail file edited in Step 3.)

---

## Task 11: Full regression

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS — new `test_family.py` green AND existing `test_engine.py`/`test_api.py`/`test_agent.py` unchanged (family features are additive; single-patient behavior is untouched when a patient has no links).

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build`
Expected: type-checks and builds (the new `FamilyLink` type + `FamilyPanel` compile).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: full regression green for family auto-linkage" --allow-empty
```

---

## Self-Review

- **Spec coverage:** relative extraction → Tasks 1 (assert), 2 (FHIR + text); `family_resolver` → Task 3; Cognee `Dedup()` nodes → Task 4; auto-run on ingest → Task 5; `hereditary_check` → Task 7 (with Task 6 helper); consent gate → Tasks 3 (link `consent` field), 7 (degrade branch), 8 (toggle API), 10 (toggle UI); demo → Task 9.
- **Placeholder scan:** none — every backend step ships runnable code + tests. The two "read first, then match style" steps (Task 10 Steps 1 & 3) are the frontend edits whose exact current file contents weren't pre-read in this planning session; each gives the exact component code to add and the exact grep to place it. This is the skill's sanctioned pattern for small UI insertions.
- **Type consistency:** `family_assert(..., relative_name=, relative_mrn=, relative_dob=)` (Task 1) is called with those exact kwargs in Tasks 2; link dict shape `{patient_id, relative_id, relation, confidence, consent, proposed}` is produced in Task 3 and consumed identically in Tasks 4 (`_mirror_to_cognee`), 7 (`links_for`), 8 (API), 10 (`FamilyLink` TS type); `add_family_members(members: list[dict])` with keys `{patient_id, name, mrn, parent_mrn}` matches between Task 4's impl/test and Task 4 Step 5's `_mirror_to_cognee`; `ontology.is_heritable` (Task 6) is used in Task 7; `family_resolver.links_for(pid, consented_only=)` signature matches across Tasks 3/7/8.
- **Isolation preserved:** a patient with no links gets `hereditary.run() == []`; only `consent=True` links ever surface identifying detail (Task 7 test asserts the no-consent branch leaks nothing) — the demo's safety thesis holds.
