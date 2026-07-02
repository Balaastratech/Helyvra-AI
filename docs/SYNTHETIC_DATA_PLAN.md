# SYNTHETIC DATA PLAN — testable fixtures for every feature

> Every feature in `CLINICAL_COPILOT_PLAN.md` gets data that *proves* it, in every input format a real
> doctor would upload, with real clinical relationships. Designed so generation is mechanical and every
> demo beat has a known-correct expected result (this doc doubles as the test oracle). Synthetic only —
> no real PHI. "Demo only · not medical advice" everywhere.

---

## 0. Design principle

Each patient is **engineered to showcase specific capabilities** — not random. Each uploadable file is
in a **specific format** so the format-coverage matrix (§3) is complete. Every fact has a known source,
date, and expected extraction, so §6 is a literal pass/fail checklist.

---

## 1. Patient roster (each one earns its place)

| ID | Name · demo | Showcases |
|---|---|---|
| **P001** | Margaret Chen · 68F (exists) | **Self-heal hero:** penicillin allergy → cleared; lisinopril → amlodipine; +T2 diabetes. Supersession, temporal rewind, why-trace, Compare money-shot. |
| **P010** | Rahul Sharma · 52M | **Clinical-checks hero:** penicillin allergy (reaction: rash + breathing difficulty); HbA1c rising 7.8→8.6→8.9 over 18mo; creatinine 1.0→1.6 over 9mo with **no nephrology follow-up**; father MI age 49; smoker; LDL 165. Fires all 3 hero checks + the rich pre-visit brief + combined-risk. |
| **P011** | Priya Mehta · 34F | **Isolation + safety:** clean unrelated record (asthma, pregnant). Used to prove patient-switch context-close and **no cross-patient leakage** (ask about Rahul's allergy while in Priya → refused/none). Pregnancy = a deferred-check stub. |
| **P012** | Rahul Sharma · 31M | **Disambiguation:** same name as P010, different age/MRN. Proves the patient resolver's duplicate handling. Minimal record. |
| **P002** | James O'Sullivan · 54M (exists) | **Interaction + renal dosing (stretch check):** atrial fibrillation, warfarin, CKD. Drug–drug interaction + "missing recent kidney lab before dose change." |
| **P003** | Aisha Rahman · 37F (exists) | **Forget/retract:** one record entered in error → demonstrates `forget` + restore-of-wrongly-superseded. |
| **P013** | Meera Nair · 41F | **Hereditary variety:** mother + maternal aunt breast cancer (BRCA-pattern family history) → hereditary-risk card distinct from cardiovascular, proves the risk engine generalizes. |

---

## 2. Per-patient data spec (the facts + their sources)

For each patient: the timeline of facts, each tagged with `resource_type` (FHIR), source document,
and date. (Abbreviated here to the demo-critical facts; full values go in the generated files.)

### P010 — Rahul Sharma (the hero patient)
| Date | resource_type | Fact | Source doc (format) |
|---|---|---|---|
| 2019-03 | Condition | Type 2 diabetes diagnosed | `P010_discharge_2019.pdf` (PDF) |
| 2019-03 | Medication | Metformin 500mg started | same PDF |
| 2021-08 | Allergy | Penicillin — rash + breathing difficulty (severe) | `P010_discharge_2021.pdf` (PDF, **page 2** — citation target) |
| 2023-01 | FamilyHistory | Father — MI at age 49 | `P010_family_history.json` (FHIR FamilyMemberHistory) |
| 2023-01 | Lifestyle | Current smoker; sedentary | `P010_intake_form.txt` (free text) |
| 2024-06 | LabResult | HbA1c 7.8% (high) | `P010_labs_2024.csv` (CSV) |
| 2024-06 | LabResult | LDL 165 (high) | `P010_labs_2024.csv` |
| 2024-09 | LabResult | Creatinine 1.0 (normal) | `P010_labs_2024.csv` |
| 2025-06 | LabResult | HbA1c 8.6% (high, rising) | `P010_lab_hba1c_2025.pdf` (PDF lab report) |
| 2025-12 | LabResult | Creatinine 1.6 (high) — **no follow-up after** | `P010_lab_renal_2025.pdf` (PDF) |
| 2026-05 | LabResult | HbA1c 8.9% (high, still rising) | `P010_lab_recent.fhir.json` (FHIR Observation) |

**Expected checks when P010 opens:** (1) creatinine-rising-no-follow-up `warning`; (2) HbA1c-rising
trend `warning`; (3) combined CV risk (father MI<50 + smoking + LDL 165) `warning`. **On "prescribe
amoxicillin":** `critical` allergy (penicillin→beta-lactam cross-reactivity) citing the 2021 PDF p.2.

### P001 — Margaret Chen (self-heal hero, exists; keep current timeline)
Penicillin allergy (2026-01-10) → **cleared** (2026-03-02); lisinopril (2026-02-15) → **switched** to
amlodipine (2026-04-20); +T2 diabetes (2026-05-11). The two corrections arrive via live `/ingest`
(held-back) to demo the self-heal + Compare. Files: existing `documents.json` + one **FHIR bundle**
upload `P001_allergy_cleared.fhir.json` to show structured supersession.

### P011 — Priya Mehta (isolation)
Asthma (Condition), salbutamol (Medication), pregnant (Observation/flag), one free-text note. No
overlap with P010 — used to prove switching from P010 closes context and that asking about "penicillin
allergy" here returns *nothing for this patient*, not Rahul's.

### P012 — Rahul Sharma 31M (disambiguation) — minimal: one visit note (`.txt`), no allergies.

### P002 — James O'Sullivan (interaction/renal, exists) — afib + warfarin + CKD; add
`P002_inr_labs.csv` (INR series) + `P002_meds.fhir.json` (MedicationStatement warfarin).

### P003 — Aisha Rahman (forget, exists) — asthma + one **entered-in-error** record
(`P003_erroneous_dx.txt`) that the demo retracts.

### P013 — Meera Nair (hereditary) — `P013_family_history.json` (FHIR: mother breast ca age 45,
maternal aunt breast ca) + normal labs → hereditary-risk card.

---

## 3. Format coverage matrix (every input a doctor uploads)

| Format | File(s) | Path through the system | Proves |
|---|---|---|---|
| **Free text** `.txt`/`.md` | `P010_intake_form.txt`, `P003_erroneous_dx.txt`, `P012_visit.txt` | Gemini Flash extraction → `resource_type` tag | text NLP extraction |
| **PDF (narrative)** | `P010_discharge_2021.pdf`, `P010_discharge_2019.pdf` | `pypdf` text extract → extraction → **citation with page #** | PDF + page-cited evidence |
| **PDF (lab report)** | `P010_lab_hba1c_2025.pdf`, `P010_lab_renal_2025.pdf` | extract numeric labs + ref range → trend/gap | lab parse + abnormal flag |
| **CSV (lab series)** | `P010_labs_2024.csv`, `P002_inr_labs.csv` | structured rows → `LabResult` series | trend reasoning |
| **FHIR JSON bundle** | `P001_allergy_cleared.fhir.json`, `P010_family_history.json`, `P010_lab_recent.fhir.json`, `P002_meds.fhir.json`, `P013_family_history.json` | direct resource→fact map (no LLM) | FHIR interop, structured supersession |
| **Scanned image** `.png` | `P010_prescription_scan.png` | flagged **needs-verification** (OCR/MedGemma deferred) → shows the verification gate + documented future path | honest deferral, verification UX |

Sample uploadable copies live in `data/sample_uploads/` so the demo can **drag a fresh file in** and
watch intake → resolve → ingest live.

---

## 4. Relationships to showcase (the graph is the point)

| Relationship | Patient | Mechanism |
|---|---|---|
| **Supersession** (fact replaced) | P001 | engine self-heal (allergy cleared, med switched) |
| **Cross-reactivity** (drug→class→allergy) | P010 | ontology (penicillin→beta-lactam) |
| **Family→risk edge** | P010, P013 | memify (father MI → CV risk; mother breast ca → hereditary) |
| **Combined risk** (family+lifestyle+lab) | P010 | memify multi-fact (MI + smoking + LDL → CV review) |
| **Abnormal lab→no follow-up** | P010 | temporal/CYPHER gap detection |
| **Trend** (worsening over time) | P010, P002 | temporal series (HbA1c, creatinine, INR) |
| **Entered-in-error→forget** | P003 | `forget` + restore |
| **Same-name distinct patients** | P010 vs P012 | resolver disambiguation |
| **Isolation** (no leakage) | P010 vs P011 | per-patient datasets + closure scope |

---

## 5. Supporting data files

- **`data/ontology/medical.ttl`** (or `.owl`) — the small medical ontology Cognee grounds against:
  drug→class (amoxicillin/ampicillin/penicillin → beta-lactam; cephalexin → cephalosporin w/ partial
  cross-reactivity), allergy cross-reactivity edges, condition→monitoring (diabetes→{eye, renal,
  HbA1c}), family-relation→risk. Small, hand-authored, enough to power the allergy + monitoring +
  risk logic. (§12 fallback: same table as plain JSON if Cognee ontology loading misbehaves.)
- **`data/doctors.json`** — demo doctors (e.g. Dr. Anya Sharma · GP; Dr. Lee · specialist) for the
  simulated login.
- **`data/access.json`** — doctor → allowed `patient_ids` (so the access/audit story is real). Include
  one patient a given doctor is *not* allowed to see, to demo the refusal + audit.
- **`hold_back` flags** (existing pattern) on P001's two corrections so they arrive live.

---

## 6. Feature → data → expected-result traceability (the test oracle)

Each row is a demo beat AND a test assertion.

| # | Feature | Patient/action | Expected result |
|---|---|---|---|
| 1 | Pre-visit brief | open P010 | summary + exactly 3 Top cards (renal gap, HbA1c trend, CV risk), each cited |
| 2 | Allergy-before-prescribe | P010 "prescribe amoxicillin?" | `critical` card; reason cites penicillin→beta-lactam + 2021 PDF p.2 |
| 3 | Missed follow-up | P010 brief / "any abnormal labs not acted on?" | creatinine 1.0→1.6, no nephrology note after 2025-12 |
| 4 | Combined risk | P010 "why CV risk?" | names father MI<50 + smoking + LDL 165, each a citation |
| 5 | Self-heal supersession | P001 ingest "allergy cleared" | old fact greys + REDACTED, answer flips to "no, cleared 2026-03-02" |
| 6 | Temporal rewind | P001 scrub to Feb | allergy shows active; "as of" answer past-tense correct |
| 7 | Why-trace | P001 click allergy | superseded 2026-03-02 by Dr. Lee re-test |
| 8 | Compare (villain) | P010 amoxicillin, Compare tab | naive "fine to prescribe" (red) vs Total Recall "no — allergy" |
| 9 | Forget/retract | P003 remove erroneous dx | fact vanishes; any wrongly-superseded fact restored; audited |
| 10 | Disambiguation | type "Rahul Sharma" | two-match selector (P010 52M vs P012 31M) |
| 11 | Isolation/no-leak | in P011, ask Rahul's allergy | "no penicillin allergy on record for Priya Mehta" (no leak) |
| 12 | Multi-format intake | drag each `sample_uploads/*` | text/PDF/CSV/FHIR ingest correctly; PNG → needs-verification |
| 13 | FHIR structured | upload `*.fhir.json` | resources map to facts with no LLM, correct types |
| 14 | Hereditary variety | open P013 | hereditary (breast ca) risk card, distinct from CV |
| 15 | Access/audit | doctor opens a non-allowed patient | refused + audit row written |

---

## 7. On-disk layout

```
data/
├─ patients.json                 # registry (add P010–P013; keep P001–P003)
├─ doctors.json                  # NEW — simulated login
├─ access.json                   # NEW — doctor→patients
├─ ontology/medical.ttl          # NEW — grounding ontology (+ medical.json fallback)
├─ patients/
│  ├─ P010/ documents.json       # references the files below + expected asserts
│  ├─ P011/ … P013/ …
│  └─ P001..P003/ (exist)
└─ sample_uploads/               # NEW — drag-in copies for the live demo
   ├─ P010_discharge_2021.pdf  P010_lab_hba1c_2025.pdf  P010_labs_2024.csv
   ├─ P010_family_history.json (FHIR)  P010_intake_form.txt
   ├─ P010_prescription_scan.png  P001_allergy_cleared.fhir.json  …
```

---

## 8. Generation plan (how the files get made)

- **Text / CSV / JSON / FHIR** — authored directly (mechanical from §2). Lowest risk; do first.
- **PDFs** — generated from authored content via the `pdf` skill (narrative discharge summaries + lab
  reports with a real page-2 so the citation is genuine). Must contain the exact fact text §6 asserts.
- **PNG scan** — a single rendered "prescription" image to exercise the needs-verification gate; OCR
  itself stays deferred (documented), so this file only needs to *look* like a scan.
- **Ontology** — hand-authored `.ttl` (small) + a `.json` mirror as the §12 fallback.

> Suggested next action: generate the **text/CSV/FHIR/JSON + ontology + doctors/access** files first
> (mechanical, unblocks Day 1–2 of the build), then the PDFs via the pdf skill, then the PNG. I can
> start on these as soon as the plan is approved.
