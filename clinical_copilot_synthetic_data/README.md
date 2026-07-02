# Clinical Copilot Synthetic Data Fixtures

Generated: 2026-06-30

Demo only - not medical advice. Synthetic data only - no real PHI.

This package implements the uploaded synthetic data plan for a doctor-facing clinical copilot demo. It contains patient-specific source files, uploadable samples, a small ontology, access-control fixtures, and a test oracle.

## Main paths

- `data/patients.json` - registry for P001, P002, P003, P010, P011, P012, P013.
- `data/doctors.json` - simulated demo doctors.
- `data/access.json` - doctor-to-patient access rules and refusal assertions.
- `data/ontology/medical.ttl` - small RDF/Turtle ontology for drug classes, cross-reactivity, monitoring, and family-risk edges.
- `data/ontology/medical.json` - JSON fallback for the same ontology facts.
- `data/patients/<patient_id>/documents.json` - per-patient facts, sources, and expected checks.
- `data/sample_uploads/` - drag-in copies for live ingestion demos.
- `data/test_oracle.json` - 15 feature-to-data expected-result assertions.

## Hero demo sequence

1. Open P010 Rahul Sharma (52M). Expected: exactly three top warning cards: renal gap, rising HbA1c, combined CV risk.
2. Ask: `Can I prescribe amoxicillin?` Expected: critical allergy warning citing `P010_discharge_2021.pdf` page 2 and ontology beta-lactam cross-reactivity.
3. Use Compare tab. Expected: naive output is unsafe; Total Recall blocks with cited allergy.
4. Switch to P011 Priya Mehta. Ask Rahul allergy. Expected: no cross-patient leakage.
5. Type `Rahul Sharma`. Expected: resolver shows P010 52M and P012 31M.
6. Ingest P001 hold-back correction. Expected: penicillin allergy becomes cleared and temporal rewind still shows active in February.

## Notes

All names, MRNs, doctors, dates, and records are synthetic and are not medical advice.
