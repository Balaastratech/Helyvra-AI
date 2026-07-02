# Sample upload files

Ready-to-upload clinical documents for testing every intake path. Full walkthrough:
[`docs/DEMO_TEST_GUIDE.md`](../docs/DEMO_TEST_GUIDE.md) §4.

| File | Format | What it tests | Drop it on… (with **no patient selected** unless noted) |
|---|---|---|---|
| `note-new-patient.txt` | free text | LLM fact + identity → **auto-creates** Robert Halloway | Chat DropZone |
| `note-existing-patient-heal.txt` | free text | name-match to Margaret Chen → **self-heals** medication | Chat DropZone |
| `structured-record.json` | structured `asserts` | deterministic multi-fact ingest (no LLM) | Records inbox (`/console`), patient = P001 |
| `fhir-bundle-new-patient.json` | FHIR Bundle | FHIR parse + **auto-create** Elena Vasquez (allergy/med/condition/lab) | Chat DropZone |
| `fhir-bundle-existing-patient.json` | FHIR Bundle | FHIR parse + **merge** CKD into Margaret Chen (MRN/name match) | Chat DropZone |
| `clinical-note.pdf` | PDF | pypdf extract + LLM → **auto-create** Daniel Foster | Chat DropZone (PDF only via `/intake`) |

Key gotcha: the Chat DropZone (`POST /intake`) attaches to the **selected** patient if
one is selected. To test identity resolution / auto-create, click the patient chip to
**deselect first**. The Records-inbox uploader (`POST /upload`) is `.txt/.md/.json`
only (no PDF) and always uses the selected patient.

All data is synthetic. Not medical advice.
