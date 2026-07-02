# Total Recall — Demo & Winning Script

> The runbook for the hackathon demo: the story, who it helps, exactly what to say and click, and
> **how Cognee makes it work at every step**. Built to be delivered in ~2–3 minutes with the real
> files in `data/demo_uploads/`. Track: **Best Use of Open Source** (self-hosted Cognee).
> *Demo only — synthetic data, not medical advice.*

---

## 1. The one-liner

> **Total Recall is a clinical memory that never confidently tells a doctor something that's no longer
> true.** A doctor uploads a patient's real records — PDFs, lab reports, even a *photo* of a paper
> prescription — and the agent builds a self-healing, time-aware memory that catches the things a
> tired clinician misses: a dangerous drug allergy, a lab that was never followed up, an inherited
> risk hiding across the family.

## 2. The problem (the hook — say this first)

> "The headline failure of AI memory isn't forgetting. It's **remembering wrong**. An assistant that
> keeps repeating an out-of-date fact — 'the patient is on this drug', 'the allergy is cleared' — is
> worse than one with no memory, because it's *confidently* wrong. In healthcare, a confidently wrong
> answer isn't a UX bug. It's a prescription for a patient who can't breathe."

That is exactly "The Hangover Part AI: Where's My Context?" — an AI that woke up and doesn't remember
last night still thinks the patient is allergic to penicillin… or worse, forgot that they are.

## 3. Who it helps

- **The doctor** in a 10-minute consult who can't re-read 5 years of scattered PDFs — gets a
  **pre-visit brief** + the top 3 things not to miss, each cited to the source page.
- **The patient** — the allergy stop, the missed-follow-up catch, the hereditary flag are all
  *safety* outcomes.
- **The clinic** — every record they already have (paper scans, lab PDFs, notes) becomes usable
  memory with **zero data-entry** — you upload the file you have, in the format you have it.
- **Cognee's engineers** (the real audience for the interview) — provenance, temporal correctness,
  and self-healing memory are *their* hard problems; this shows their platform solving them.

## 4. The demo runbook (scene by scene)

> Setup: backend + frontend running; the real files are in `data/demo_uploads/`. Log in as a doctor.

### Scene 0 — the cold open (10s)
Neon title: *"Your AI woke up with no memory of last night… it still thinks the patient is allergic
to penicillin."* → **Wake it up** → the screen "sobers up" into the calm, light clinical dashboard.
> Say: "That's the whole thesis in one line. Let's watch it save a patient."

### Scene 1 — upload the records the doctor actually has (30s) — **INGESTION, real formats**
Drag these onto the dashboard drop-zone, one at a time (no patient pre-selected — the system figures
it out):
1. `clinic_note_intake.txt` — a plain clinic note.
2. `discharge_summary_2021.pdf` — a formatted hospital discharge (2 pages).
3. `lab_report_2025.pdf` — a lab report with a results table.
4. `hba1c_series_2024.csv` — a lab spreadsheet.

> Say: "These are the formats a clinic actually has — a note, PDFs, a spreadsheet. No JSON, no
> developer format. The system detects it's the same patient, **Rahul Sharma**, and files everything
> to one chart automatically."
>
> **Cognee under the hood:** each fact is `add`-ed to Rahul's **isolated per-patient dataset**, then
> `cognify`-ed into a temporal knowledge graph, and **grounded against a medical ontology** so
> "penicillin", "amoxicillin", "HbA1c" are validated real clinical entities, not hallucinations.

### Scene 2 — the pre-visit brief (20s) — **the "doctor might miss" engine**
Open Rahul's chart. Before any chat, the **pre-visit brief** assembles: chart summary + **Top 3 things
not to miss**:
- ⚠ HbA1c rising (7.8 → 8.6) — diabetes worsening.
- ⚠ Creatinine 1.6, eGFR 52 — **no nephrology follow-up found**.
- ⚠ Father had an MI at 49 **+ smoker + LDL 165** → cardiovascular risk.

> Say: "It read the records like a good resident would — and each flag is clickable straight to the
> source page. The cardiovascular one is the key: no single record says 'high risk'. It's the
> *combination* — family history, plus smoking, plus the lab — reasoned together."
>
> **Cognee under the hood:** that combined-risk card is a **`memify`** enrichment pass — Cognee
> materializes a cross-fact `CardiovascularRisk` relationship in the graph, connecting facts that
> live in three different documents.

### Scene 3 — the photo of a prescription (30s) — **IMAGE → vision → the STOP** *(the money shot)*
Upload `prescription_scan.png` — a **phone photo of a paper prescription** for **amoxicillin**.

> Say: "This is a real thing that happens — a paper Rx, photographed. Watch the system *read the
> image*." (It's read by Gemini vision — no OCR service, no GPU.)
>
> The agent immediately raises a **CRITICAL** card:
> *"Do not prescribe amoxicillin — the patient has a documented **penicillin** allergy (rash and
> breathing difficulty), 2021 discharge summary, page 2. Amoxicillin is a beta-lactam and
> cross-reacts."*
>
> Say: "It read a **photo**, connected 'amoxicillin' to the drug class, cross-referenced a **penicillin
> allergy documented four years earlier on page 2 of a different PDF**, and stopped a dangerous
> prescription — with the citation a doctor can verify in one click."
>
> **Cognee under the hood:** the allergy fact and its provenance came from Cognee memory; the
> ontology supplies the beta-lactam cross-reactivity; the answer cites the exact record.

### Scene 4 — self-healing memory (20s) — **the Cognee differentiator**
In the Consult chat, ask: *"What blood-pressure medication is he on?"* Answer: **amlodipine** — because
`med_change_note.txt` superseded the earlier lisinopril.
Now open the **Compare** tab (the noir "villain" view) and ask the same thing:
- **Hungover AI** (naive RAG over the frozen pre-correction memory): *"lisinopril"* — stale, wrong.
- **Total Recall** (Cognee TEMPORAL over the healed memory): *"amlodipine — switched from lisinopril
  on 2026-04-20."*

> Say: "Same question. The naive AI repeats the outdated answer. Total Recall **healed its own
> memory** — kept the history, but knows the current truth, and can tell you *when and why* it
> changed."
>
> **Cognee under the hood:** `cognify(temporal_cognify=True)` + our supersession engine mark the old
> fact superseded (retained, not deleted) with a `SUPERSEDED_BY` edge; `improve()` repairs the graph;
> `TEMPORAL` search answers current *and* past correctly. Drag the **time-scrubber** to April and the
> graph shows lisinopril still active — memory you can rewind.

### Scene 5 — the family graph (20s) — **automatic linkage, consented**
Upload `son_intake_note.txt` — a new patient, **Arjun Sharma**, whose intake names *"Father — Rahul
Sharma, MRN RH-4471"*. Open Arjun's chart: the system has **automatically linked** him to his father's
chart, and — with consent — the hereditary card reads: *"Father (a linked patient) has type 2 diabetes
and early cardiac disease → consider screening."*

> Say: "No one filed a family tree. The system read the note, recognized the father is already a
> patient, linked the charts, and now reasons across a real family — while keeping every chart
> isolated unless there's explicit consent."
>
> **Cognee under the hood:** `Dedup()`-keyed `FamilyMember` DataPoints make the father one shared
> node across both charts; the hereditary check traverses that graph.

### Scene 6 — close (10s)
> "Every answer you saw was grounded in this patient's own records, cited to the source, and honest
> about uncertainty — and the whole memory layer is **self-hosted Cognee**, running locally, no cloud.
> That's an AI that remembers the *right* thing, at the *right* time, for the people who can't afford
> it to get it wrong."

---

## 5. Why it's better than naive RAG (the contrast to hammer)

| Naive RAG memory | Total Recall (Cognee) |
|---|---|
| Retrieves all chunks, answers with the highest-ranked — including stale ones | Time-aware: knows which fact is *current* and which was *superseded* |
| No notion of truth-over-time | `temporal_cognify` + supersession edges + rewindable timeline |
| Confidently wrong, no provenance | Every claim cited to a source document + page; honest about conflicts |
| Facts are isolated chunks | Graph reasons *across* facts (family + lifestyle + lab → risk) via `memify` |
| Hallucinated entities | Ontology-grounded (`ontology_valid`) — validated clinical entities |
| Reads text only | Reads **PDFs, spreadsheets, and photos/scans** (Gemini vision) |

## 6. How Cognee makes it better (name these — judges scan for them)

`add` (per-patient isolated datasets) · `cognify(temporal_cognify=True)` · **ontology grounding**
(OWL/RDF resolver → `ontology_valid`) · **`memify`** (cross-fact risk relationships) · custom
**DataPoints** incl. `Dedup()` family nodes · `search` — **TEMPORAL** (current + past),
**RAG_COMPLETION** (the naive villain baseline), graph/CYPHER · `improve` (post-heal graph repair) ·
`forget` (retract entered-in-error) · provenance / raw graph view. **~11 primitives, several of them
the rare ones almost no team touches** (temporal, ontology grounding, memify, Dedup graph).

## 7. Winning checklist (rubric mapping)

- **Potential impact:** stale clinical memory = patient harm — concrete, undeniable stakes. ✅
- **Creativity:** forgetting-as-a-feature + a time-machine over the graph + reading a *photo* of a
  script + a consented family graph. ✅
- **Technical excellence:** full memory lifecycle (remember/recall/improve/forget) + temporal +
  ontology + memify + Dedup graph + multimodal ingest. ✅
- **Best use of Cognee:** §6 — and it's **self-hosted / local** (Best Use of Open Source track). ✅
- **UX:** calm light-clinical workspace, cited answers, honest uncertainty, ⌘K, the noir Compare
  money-shot. ✅
- **Presentation:** this script. ✅
- **Rules:** synthetic data + "not medical advice" banner everywhere; **AI-assistant use disclosed**
  in the submission (don't forget — disqualifying if omitted). ✅

## 8. Data manifest — which file proves which feature

| File (real format) | Feature it demonstrates | Cognee touchpoint |
|---|---|---|
| `clinic_note_intake.txt` | Free-text extraction; diabetes, meds, smoking, LDL, family history | add + cognify + grounding |
| `discharge_summary_2021.pdf` | PDF text-layer extraction; **page-2 citation** (allergy) | add + provenance |
| `lab_report_2025.pdf` | PDF table extraction; rising HbA1c, high creatinine (follow-up gap) | temporal + checks |
| `hba1c_series_2024.csv` | Spreadsheet lab series → trend | temporal trend |
| `prescription_scan.png` | **Image/photo → Gemini vision** → amoxicillin → **allergy STOP** | ontology cross-reactivity |
| `med_change_note.txt` | Supersession / **self-heal** (lisinopril → amlodipine) | temporal + improve + SUPERSEDED_BY |
| `son_intake_note.txt` | **Automatic family linkage** + consented hereditary risk | Dedup DataPoint graph |

## 9. Pre-flight (run once before demoing)

- Regenerate files if needed: `cd backend && .venv/Scripts/python.exe scripts/gen_demo_data.py`
- Verify image vision works end-to-end (one cheap Flash call, needs ADC):
  ```
  cd backend && .venv/Scripts/python.exe -c "import asyncio; from app.intake import pipeline; \
  b=open(r'..\data\demo_uploads\prescription_scan.png','rb').read(); \
  r=asyncio.run(pipeline.run(b,'prescription_scan.png','P010')); \
  print('facts from image:', [f.value for f in r.facts])"
  ```
  Expected: an amoxicillin medication fact extracted from the **image**.
- Confirm the disclaimer banner is visible and the AI-disclosure line is in the README/submission.
