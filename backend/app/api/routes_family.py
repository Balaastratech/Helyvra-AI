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
