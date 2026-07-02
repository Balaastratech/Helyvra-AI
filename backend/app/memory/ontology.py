"""
Medical ontology — the single source of truth for clinical grounding
(CLINICAL_COPILOT_PLAN §4).

ONE set of Python tables drives BOTH consumers, so they can never drift:
  1. the clinical checks (Day 2) read the lookup helpers directly
     (drug->class, beta-lactam cross-reactivity, condition->monitoring, family->risk);
  2. Cognee grounds entity extraction against an OWL/RDF file we *generate* from the
     same tables (`build_owl`), so Cognee marks matched nodes ontology_valid=True and
     attaches the parent-class / object-property edges from this vocabulary.

Curated and intentionally small — Cognee matching stays precise and fast on a focused
ontology (per its docs). Extend the tables, not a hand-written .owl.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

# --- 1. drug -> drug class (FHIR AllergyIntolerance / MedicationStatement) -----
# Individual drug (lowercased generic name) -> its pharmacologic class.
DRUG_CLASS: Dict[str, str] = {
    # penicillins
    "penicillin": "penicillin", "amoxicillin": "penicillin", "ampicillin": "penicillin",
    "dicloxacillin": "penicillin", "piperacillin": "penicillin", "amoxicillin-clavulanate": "penicillin",
    # cephalosporins
    "cephalexin": "cephalosporin", "cefazolin": "cephalosporin", "ceftriaxone": "cephalosporin",
    "cefuroxime": "cephalosporin", "cefepime": "cephalosporin",
    # carbapenems
    "meropenem": "carbapenem", "imipenem": "carbapenem", "ertapenem": "carbapenem",
    # non-beta-lactam antibiotics
    "azithromycin": "macrolide", "clarithromycin": "macrolide",
    "ciprofloxacin": "fluoroquinolone", "levofloxacin": "fluoroquinolone",
    "sulfamethoxazole": "sulfonamide", "trimethoprim-sulfamethoxazole": "sulfonamide",
    "vancomycin": "glycopeptide", "doxycycline": "tetracycline",
    # cardiometabolic
    "lisinopril": "ace_inhibitor", "enalapril": "ace_inhibitor", "ramipril": "ace_inhibitor",
    "losartan": "arb", "valsartan": "arb",
    "amlodipine": "calcium_channel_blocker", "diltiazem": "calcium_channel_blocker",
    "metoprolol": "beta_blocker", "atenolol": "beta_blocker",
    "metformin": "biguanide", "glipizide": "sulfonylurea", "insulin": "insulin",
    "atorvastatin": "statin", "rosuvastatin": "statin", "simvastatin": "statin",
    "hydrochlorothiazide": "thiazide",
    # analgesics
    "ibuprofen": "nsaid", "naproxen": "nsaid", "aspirin": "nsaid", "diclofenac": "nsaid",
}

# --- 2. drug class -> cross-reactivity group (beta-lactam family) --------------
# Classes that share a group cross-react. The clinically critical one: a penicillin
# allergy contraindicates cephalosporins/carbapenems (shared beta-lactam ring).
CLASS_GROUP: Dict[str, str] = {
    "penicillin": "beta_lactam",
    "cephalosporin": "beta_lactam",
    "carbapenem": "beta_lactam",
}

# --- 3. condition -> monitoring rules (Condition -> Observation cadence) --------
# What an active condition should be monitored with, and how often. Drives the
# missed-follow-up / monitoring-gap check.
CONDITION_MONITORING: Dict[str, List[dict]] = {
    "type 2 diabetes": [{"analyte": "hba1c", "every_months": 3}],
    "type 1 diabetes": [{"analyte": "hba1c", "every_months": 3}],
    "diabetes": [{"analyte": "hba1c", "every_months": 3}],
    "chronic kidney disease": [{"analyte": "creatinine", "every_months": 6},
                               {"analyte": "egfr", "every_months": 6}],
    "hypertension": [{"analyte": "blood pressure", "every_months": 6}],
    "hyperlipidemia": [{"analyte": "ldl", "every_months": 12}],
    "heart failure": [{"analyte": "creatinine", "every_months": 6},
                      {"analyte": "potassium", "every_months": 6}],
    "atrial fibrillation": [{"analyte": "inr", "every_months": 1}],
}

# --- 4. family history -> hereditary risk (FamilyMemberHistory -> risk) ---------
# A first-degree relative's condition confers a familial risk category. Combined
# with the patient's own factors (smoking / LDL / HbA1c) in the combined-risk check.
FAMILY_RISK: Dict[str, str] = {
    "myocardial infarction": "cardiovascular", "heart attack": "cardiovascular",
    "coronary artery disease": "cardiovascular", "stroke": "cardiovascular",
    "sudden cardiac death": "cardiovascular",
    "diabetes": "metabolic", "type 2 diabetes": "metabolic",
    "breast cancer": "oncologic", "ovarian cancer": "oncologic",
    "colon cancer": "oncologic", "colorectal cancer": "oncologic",
}

FIRST_DEGREE_RELATIONS = {
    "father", "mother", "parent", "brother", "sister", "sibling", "son", "daughter", "child",
}

# Early-onset cutoff: a first-degree relative's CV event before this age is the
# hereditary red flag (CLINICAL_COPILOT_PLAN: "father MI<50").
EARLY_ONSET_AGE = 55


# --- lookup helpers (the checks' API) ------------------------------------------
def _norm(s: str) -> str:
    return s.strip().lower()


def drug_class(drug: str) -> Optional[str]:
    """Pharmacologic class for a drug name (tolerates a trailing dose, e.g.
    'amoxicillin 500mg')."""
    n = _norm(drug)
    if n in DRUG_CLASS:
        return DRUG_CLASS[n]
    for token in n.replace("/", " ").split():
        if token in DRUG_CLASS:
            return DRUG_CLASS[token]
    return None


def are_cross_reactive(drug_a: str, drug_b: str) -> bool:
    """True if two drugs cross-react: same class, or same cross-reactivity group
    (e.g. penicillin vs cephalosporin via the beta-lactam ring)."""
    ca, cb = drug_class(drug_a), drug_class(drug_b)
    if ca is None or cb is None:
        return False
    if ca == cb:
        return True
    return CLASS_GROUP.get(ca) is not None and CLASS_GROUP.get(ca) == CLASS_GROUP.get(cb)


def monitoring_for(condition: str) -> List[dict]:
    """Monitoring rules for an active condition ([] if none defined)."""
    return CONDITION_MONITORING.get(_norm(condition), [])


def family_risk_for(condition: str) -> Optional[str]:
    """Hereditary risk category a relative's condition confers (None if none).
    Matches exact or as a substring: extracted text often combines terms
    ("heart attack (myocardial infarction)") rather than one bare vocabulary
    key, so an exact-only lookup silently misses real phrasing."""
    n = _norm(condition)
    if n in FAMILY_RISK:
        return FAMILY_RISK[n]
    for key in sorted(FAMILY_RISK, key=len, reverse=True):
        if key in n:
            return FAMILY_RISK[key]
    return None


def is_heritable(condition: str) -> bool:
    """True if a condition confers a familial/hereditary risk (i.e. a relative
    having it matters for the patient). Reuses the FAMILY_RISK vocabulary — one
    source of truth for both the family-history read and the hereditary check."""
    return family_risk_for(condition) is not None


def is_first_degree(relation: str) -> bool:
    return _norm(relation) in FIRST_DEGREE_RELATIONS


def is_known(name: str) -> bool:
    """Local grounding fallback: is this entity anywhere in our vocabulary? Used
    when Cognee's resolver is unavailable so ontology_valid still resolves."""
    n = _norm(name)
    if n in DRUG_CLASS or drug_class(n) is not None:
        return True
    if n in CONDITION_MONITORING or n in FAMILY_RISK:
        return True
    # analytes referenced by monitoring rules count as known clinical entities
    analytes = {r["analyte"] for rules in CONDITION_MONITORING.values() for r in rules}
    return n in analytes


# --- OWL generation (the Cognee grounding artifact) ----------------------------
_OWL_PATH = os.environ.get("MED_ONTOLOGY_OWL", r"C:\cg\medical_ontology.owl")
_NS = "http://totalrecall.local/med#"


def build_owl(path: str = _OWL_PATH) -> str:
    """Render the tables above to an RDF/XML OWL file Cognee can ground against.
    Classes: drug classes, cross-reactivity groups, conditions, analytes, risk
    categories. Individuals: drugs (typed by class). Edges: subClassOf for the
    beta-lactam group, monitoredBy (condition->analyte), confersFamilialRisk
    (condition->risk). Single source — regenerated from this module, never edited."""
    from rdflib import Graph, Namespace, OWL, RDF, RDFS, URIRef

    MED = Namespace(_NS)
    g = Graph()
    g.bind("med", MED)
    g.bind("owl", OWL)

    def uri(name: str) -> URIRef:
        return MED[name.strip().lower().replace(" ", "_").replace("/", "_")]

    def cls(name: str) -> URIRef:
        u = uri(name)
        g.add((u, RDF.type, OWL.Class))
        return u

    def obj_prop(name: str) -> URIRef:
        u = uri(name)
        g.add((u, RDF.type, OWL.ObjectProperty))
        return u

    monitored_by = obj_prop("monitoredBy")
    confers_risk = obj_prop("confersFamilialRisk")

    # drug classes + cross-reactivity groups (subClassOf the group)
    for klass, group in CLASS_GROUP.items():
        g.add((cls(klass), RDFS.subClassOf, cls(group)))
    for klass in set(DRUG_CLASS.values()):
        cls(klass)
    # individual drugs typed by their class
    for drug, klass in DRUG_CLASS.items():
        d = uri(drug)
        g.add((d, RDF.type, uri(klass)))
    # conditions + monitoring edges
    for condition, rules in CONDITION_MONITORING.items():
        c = cls(condition)
        for rule in rules:
            g.add((c, monitored_by, cls(rule["analyte"])))
    # family-history risk edges
    for condition, category in FAMILY_RISK.items():
        g.add((cls(condition), confers_risk, cls(f"{category}_risk")))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    g.serialize(destination=path, format="xml")
    return path


def owl_path() -> str:
    """Path to the OWL file, generating it on first use (cached on disk)."""
    if not os.path.exists(_OWL_PATH):
        build_owl(_OWL_PATH)
    return _OWL_PATH
