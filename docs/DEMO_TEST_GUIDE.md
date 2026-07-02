# Total Recall — End-to-End Test & Demo Guide

A complete, do-this-then-that playbook for exercising **every feature** the system
offers: the tool-calling agent, self-healing memory, citations, honest uncertainty,
the human-approval correction gate, all four upload formats, every UI page, and the
full API surface. Ready-to-upload sample files live in [`/samples`](../samples).

> Everything here uses **synthetic data only**. Not medical advice.

---

## 0. Prerequisites & startup

You need: Python venv in `backend/.venv`, Node deps in `frontend/`, Google Vertex
ADC credentials available (the engine + extraction call Vertex Gemini), and the
short Cognee storage root `C:\cg\` (created automatically).

**Terminal 1 — backend** (do NOT use `--reload` for the demo; Cognee init is heavy):
```
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
Wait for `Application startup complete`. First Cognee call is slow (3–7s).

**Terminal 2 — frontend:**
```
cd frontend
npm run dev
```
Open http://localhost:5173. On first load you'll see the **Title Sequence** intro
(plays once per browser session; stored in `sessionStorage`).

**Sanity check (Terminal 3):**
```
Invoke-RestMethod http://127.0.0.1:8000/health
```
Expect `ok = True`, `cognee = up`, `ledger = up`. The NavBar shows **"systems up"**
with a green dot when this passes.

---

## 1. Reset & seed the demo patient (P001 Margaret Chen)

Start from a clean, known state every time.

```
Invoke-RestMethod http://127.0.0.1:8000/reset -Method Post -ContentType application/json -Body '{"patient_id":"P001"}'
Invoke-RestMethod http://127.0.0.1:8000/seed  -Method Post -ContentType application/json -Body '{"patient_id":"P001"}'
```

After `/seed`, P001's **active** memory is:

| Subject | Fact | Date | Source |
|---|---|---|---|
| allergy | **Allergic to penicillin** | 2026-01-10 | Dr. Adams |
| medication | **On lisinopril 10mg** | 2026-02-15 | Dr. Adams |
| diagnosis | **Type 2 diabetes** | 2026-05-11 | Dr. Patel |

Two events are **held back** on purpose so you can apply them live and watch memory
self-heal: the penicillin allergy *clear* (2026-03-02, Dr. Lee) and the lisinopril →
amlodipine *switch* (2026-04-20, Dr. Lee).

In the UI: open the NavBar patient chip (top-right) → it should read **Margaret Chen ·
MRN-004471**. If no patient is selected, the Chat landing shows the patient picker —
select Margaret Chen.

---

## 2. THE headline demo — agent + self-healing (do this first)

This is the money path. Go to the **Chat** tab (`/`), patient = Margaret Chen.

**Step 1 — ask before the correction.**
> Is the patient allergic to penicillin?

Expect: **"Yes"**, allergic to penicillin, cited to the 2026-01-10 allergy note.
Watch for:
- a **citation chip** under the answer (click it → the source `DocumentViewer` opens),
- the one-line **tool trace** ("checked memory") — click **raw** to expand the exact
  tool name / args / timing,
- certainty is **settled** (no warning badge).

**Step 2 — state the new clinical fact in plain language.**
> Dr. Lee cleared the penicillin allergy on 2026-03-02 after a negative re-test.

Expect: the agent calls `ingest_fact`; the self-healing engine classifies this as
**SUPERSEDES**; the trace chip reads **"Updated: Penicillin allergy cleared"**. The
Inspector (WhyPanel) opens on the affected fact.

**Step 3 — ask again.**
>   

Expect: **"No"** — and crucially, the *history*: "was diagnosed 2026-01-10 (Dr.
Adams), cleared 2026-03-02 by Dr. Lee after a negative re-test." Multiple citation
chips. This is the differentiator: it never just says "No", it explains the change.

**Step 4 — provenance.**
> Why did the penicillin allergy change?

Expect: `why_changed` runs; a change-history narrative (old → new, dates, who, why).

---

## 3. Every agent capability (exact prompts → expected behavior)

All in the **Chat** tab. The four tools are `recall_patient_facts`, `ingest_fact`,
`propose_forget`, `why_changed` — bound to the **currently selected patient** via a
closure (the model never sees a patient_id).

### 3.1 Recall (current truth + history)
> What blood-pressure medication is the patient on?

→ recall. After you also ingest the switch (below), expect amlodipine 5mg with the
lisinopril history.

### 3.2 Ingest / improve (self-heal a medication)
>   

→ `ingest_fact` → **SUPERSEDES** → "Updated: Switched to amlodipine 5mg".

### 3.3 Forced grounding (anti-hallucination)
Ask any clinical question and confirm the trace **always** shows a
`recall_patient_facts` call before the answer ("checked memory"). The agent is
system-prompted to never answer allergy/medication/diagnosis/lab questions from its
own general knowledge. A clinical answer with no recall call is a bug.

### 3.4 Staged correction → human approval gate (the destructive path)
> The type 2 diabetes diagnosis was entered in error — wrong patient. Please remove it.

Expect: the agent calls `propose_forget` and **does NOT delete**. An **approval card**
appears inline: *"Mark Type 2 diabetes (2026-05-11, Dr. Patel) as entered in error and
remove it from memory?"* with **Confirm** / **Keep it**.
- Click **Confirm** → `POST /chat/approve` runs `execute_forget` → diabetes is
  retracted, disappears from the graph / board, and an outcome message is appended.
- Or click **Keep it** → nothing is deleted; conversation continues.

This proves: additive writes auto-execute, but anything destructive needs one human
click. (Contrast with the Records-inbox "Remove" which is the older direct `/forget`.)

### 3.5 Cross-patient isolation (security)
With Margaret Chen still selected:
> Does James O'Sullivan have atrial fibrillation?

Expect: the agent can only see **this** patient's chart; it answers from P001's memory
(no AFib record) rather than leaking P002. Switching the patient chip to James
O'Sullivan re-scopes every tool. This is enforced by the closure binding, not a prompt.

### 3.6 Idempotency (retry-safe writes)
Send the exact same ingest statement **twice** in one session, e.g.:
> Record that the patient now takes metformin 500mg.

The second identical send is **deduped** — the trace chip reads "Already recorded
(deduped)", and no duplicate fact is written.

### 3.7 Honest uncertainty (contested / low-confidence)
Certainty surfaces automatically from the engine. When the engine marks same-subject
facts **contested** (its CONTRADICTS path) or a fact's confidence drops below 0.6, the
answer renders a **"needs review — records conflict"** (amber) or **"unverified"**
badge and names both conflicting records instead of picking a confident winner.
*(Engine-dependent: try ingesting two directly conflicting same-date facts for one
subject; whether it classifies SUPERSEDES vs CONTRADICTS is the judge's call.)*

### 3.8 Multi-thread chat
Use the left sidebar: **New chat** starts a fresh thread; prior threads are listed and
clickable. Reload a thread — the persisted **trace, citations, certainty, and pending
card** re-render (they're stored on each assistant message, not just live).

### 3.9 Graceful degradation
If a tool errors or Cognee sync lags, the agent says so in plain language and the
conversation continues — never a stack trace, never a silent wrong answer.

---

## 4. Upload — all four formats (real files in `/samples`)

| Sample file | Format | Tests | How to upload |
|---|---|---|---|
| `note-new-patient.txt` | free text | LLM fact + **identity extraction → auto-creates a new chart** | Chat **landing DropZone** with **no patient selected** |
| `note-existing-patient-heal.txt` | free text | resolves to existing chart by name, **self-heals** the medication | DropZone with **no patient selected** (name matches Margaret Chen) |
| `structured-record.json` | structured `asserts` JSON | deterministic ingest (no LLM), multiple facts | **Records inbox** "Upload a record", patient = P001 |
| `fhir-bundle-new-patient.json` | FHIR Bundle | structured FHIR parse + **auto-create** (allergy/med/condition/lab) | DropZone, **no patient selected** |
| `fhir-bundle-existing-patient.json` | FHIR Bundle | FHIR parse + **merge into existing** chart (MRN/name match P001) | DropZone, no patient selected |
| `clinical-note.pdf` | PDF | **pypdf text extraction** → LLM fact + identity → auto-create | DropZone (PDF only works through `/intake`) |

**Two upload entry points — they behave differently:**

- **Chat-page / landing DropZone** → `POST /intake` (universal). Accepts **.pdf,
  .json, .txt, .md**. If **no patient is selected**, it auto-detects the patient from
  the document (FHIR Patient resource, or LLM-extracted name) and **creates a new
  chart** if there's no match — then auto-switches to that patient. If a patient *is*
  selected, the file is attached to that patient (the name in the doc is ignored).
  **So: to test auto-create / identity resolution, click the patient chip to
  deselect first** (land on the picker), then drop the file.
- **Records-inbox uploader** (Console page, `/console`) → `POST /upload`. Requires a
  selected patient; accepts **.txt/.md/.json only** (no PDF). Structured JSON with an
  `asserts` array ingests deterministically; free text is LLM-extracted.

### 4.1 Walkthrough — text, new patient (auto-create)
1. Deselect the patient (click the chip → patient picker appears).
2. Drag `samples/note-new-patient.txt` onto the DropZone.
3. Expect: *"✓ note-new-patient.txt → Robert Halloway (new chart created) · 1 fact(s)
   ingested"*, and the UI switches to the new chart. Verify in **The Board** / **Memory
   Map** that a `diagnosis: hypertension` fact exists.

### 4.2 Walkthrough — text, existing patient + heal
1. Deselect patient. Drag `samples/note-existing-patient-heal.txt`.
2. Identity resolves to **Margaret Chen (P001)** by name. The amlodipine switch
   supersedes lisinopril (toast: *"the AI updated itself"*). Ask in Chat
   *"what BP medication is the patient on?"* → amlodipine 5mg with lisinopril history.

### 4.3 Walkthrough — structured JSON
1. Select Margaret Chen. Go to `/console` → **Records inbox** → "Upload a record".
2. Choose `samples/structured-record.json`. Two facts (HbA1c lab + metformin) ingest
   with **no LLM call** (deterministic). They appear in the inbox as "in memory".

### 4.4 Walkthrough — FHIR (new + existing)
- `fhir-bundle-new-patient.json` (no patient selected) → creates **Elena Vasquez**
  with four facts: sulfa allergy, albuterol inhaler, asthma, IgE lab.
- `fhir-bundle-existing-patient.json` (no patient selected) → MRN/name match merges a
  **CKD stage 2** diagnosis into Margaret Chen's existing chart.

### 4.5 Walkthrough — PDF
1. Deselect patient. Drag `samples/clinical-note.pdf` onto the DropZone.
2. pypdf extracts the text → LLM extracts the fact + identity → creates **Daniel
   Foster** with an `atrial fibrillation` diagnosis.

### 4.6 Ingest the built-in source documents (provenance)
On `/console` with P001, the **Records inbox** lists the five seeded source notes
(DOC-P001-01..05). Click **Ingest** on one (or **Ingest all**) — each resulting fact
links back to its source document, so citation chips and the DocumentViewer can open
the exact record.

---

## 5. Every UI page & widget

### 5.1 Chat (`/`) — the primary surface
Already covered in §2–3. Widgets to verify: citation chips (click → DocumentViewer),
certainty badge, inline tool trace + **Raw** toggle (progressive disclosure), the
correction **approval card**, the global **DropZone**, the thread sidebar, and the
**Inspector drawer** (WhyPanel) that opens when a turn changes a fact.

### 5.2 Compare (`/compare`) — smart vs naive
Type the allergy question. Two columns:
- **Total Recall (smart)** → synthesized, cited, healed answer ("No — cleared…").
- **Naive baseline (villain)** → `RAG_COMPLETION` over the frozen pre-heal dataset →
  the **stale/dangerous** "Yes, allergic". This contrast is the core story; it only
  diverges *after* you've applied the clear event (§2 or the heal upload).

### 5.3 Memory Map (`/memory`) — the graph + time travel
- **Ledger timeline graph**: each node is a fact; dashed red **SUPERSEDED_BY** arrows
  show corrections. Click a node → WhyPanel.
- **Raw Cognee graph** (depth tab): the actual Cognee knowledge graph (`/graph/cognee`).
- **Rewind slider (time-scrubber)**: drag back to **2026-02-15** → the penicillin
  allergy shows **active**; drag to **today** → it's **superseded**. Status recomputes
  client-side with zero network calls. This proves superseded facts are *retained*, not
  deleted (temporal memory).

### 5.4 The Board (`/board`) — evidence wall
Polaroid-style cards of the timeline; click a card → open its source document or its
"why" provenance. Good for the cinematic demo shot.

### 5.5 Console (`/console`) — operator view (not in the nav; open by URL)
Three columns: PatientCard + GuidedSteps + **Records inbox** (ingest/upload/remove/
reset) | **SplitChat** (smart-vs-naive chat) | **MemoryGraph + RewindSlider**. This is
the most feature-dense page for manual ops.

### 5.6 NavBar extras
- **Patient chip** (top-right) — click to switch/deselect patient.
- **How it works** — explainer overlay.
- **systems up** — live `/health` indicator (green = ledger + Cognee up).
- **Cinema** — toggles the cinematic visual layer (film grain, light leaks).

---

## 6. Full API coverage (every endpoint)

The fastest full-surface check is the bundled smoke script (server must be running):
```
cd backend
.\scripts\smoke.ps1
```
It exercises `/health → /seed → /ask (naive pre-heal) → /ingest (clear) → /ingest
(switch) → /ask (naive vs total_recall) → /graph (Feb vs now) → /graph/cognee → /why →
/forget` end-to-end and prints each result.

Individual endpoints (PowerShell `Invoke-RestMethod`):

| Endpoint | Example |
|---|---|
| `GET /` | `irm http://127.0.0.1:8000/` |
| `GET /health` | `irm http://127.0.0.1:8000/health` |
| `GET /patients` | `irm http://127.0.0.1:8000/patients` |
| `POST /patients` | `irm .../patients -Method Post -ContentType application/json -Body '{"name":"Test Person","dob":"1990-01-01","sex":"M"}'` |
| `GET /patients/{id}/documents` | `irm http://127.0.0.1:8000/patients/P001/documents` |
| `GET /documents/{doc_id}` | `irm http://127.0.0.1:8000/documents/DOC-P001-03` |
| `POST /ingest_document` | `irm .../ingest_document -Method Post -ContentType application/json -Body '{"patient_id":"P001","doc_id":"DOC-P001-03"}'` |
| `POST /seed` / `POST /reset` | see §1 |
| `POST /ingest` | `irm .../ingest -Method Post -ContentType application/json -Body '{"patient_id":"P001","text":"Penicillin allergy cleared 2026-03-02 by Dr. Lee."}'` |
| `POST /ask` | `irm .../ask -Method Post -ContentType application/json -Body '{"patient_id":"P001","question":"allergic to penicillin?","mode":"total_recall"}'` (try `"mode":"naive"` and `"as_of":"2026-02-15"`) |
| `GET /graph` | `irm "http://127.0.0.1:8000/graph?patient_id=P001&as_of=2026-02-15"` |
| `GET /graph/cognee` | `irm "http://127.0.0.1:8000/graph/cognee?patient_id=P001"` |
| `GET /why` | `irm "http://127.0.0.1:8000/why?fact_id=<id from /graph>"` |
| `POST /forget` | `irm .../forget -Method Post -ContentType application/json -Body '{"patient_id":"P001","fact_id":"<id>","reason":"entered in error"}'` |
| `POST /intake` (multipart) | `curl.exe -F "file=@samples/clinical-note.pdf" http://127.0.0.1:8000/intake` |
| `POST /upload` (multipart) | `curl.exe -F "patient_id=P001" -F "file=@samples/structured-record.json" http://127.0.0.1:8000/upload` |
| `POST /chat` | `irm .../chat -Method Post -ContentType application/json -Body '{"patient_id":"P001","message":"allergic to penicillin?"}'` |
| `POST /chat/approve` | `irm .../chat/approve -Method Post -ContentType application/json -Body '{"pending_id":"<from /chat pending>","decision":"approve"}'` |
| `GET /chat/threads` | `irm "http://127.0.0.1:8000/chat/threads?patient_id=P001"` |
| `GET /chat/threads/{id}/messages` | `irm http://127.0.0.1:8000/chat/threads/<id>/messages` |

**Interactive docs:** open http://127.0.0.1:8000/docs (Swagger) to call any endpoint
from the browser with schemas.

### 6.1 Chat agent via API (full turn with the new fields)
```
$r = irm http://127.0.0.1:8000/chat -Method Post -ContentType application/json -Body '{"patient_id":"P001","message":"The diabetes diagnosis was entered in error, remove it."}'
$r.pending        # the staged correction (pending_id, label, …)
$r.trace          # ordered tool calls {seq,tool,args,ms,result_summary}
$r.citations      # grounding citations
$r.certainty      # settled | contested | low_confidence
irm http://127.0.0.1:8000/chat/approve -Method Post -ContentType application/json -Body (@{pending_id=$r.pending.pending_id; decision="approve"} | ConvertTo-Json)
```

---

## 7. Automated backend tests

```
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```
- `tests/test_agent.py` (offline, fast): closure scoping, staged-correction stages
  without deleting, write idempotency, why-scoping, forced-grounding prompt invariant.
- `tests/test_engine.py`, `tests/test_api.py`: the engine + API flow (these call Vertex
  + Cognee and are slow, several minutes).

Run only the fast offline agent suite:
```
.\.venv\Scripts\python.exe -m pytest tests/test_agent.py -q
```

---

## 8. Suggested 5-minute demo script (for a recording)

1. `/health` green, patient = Margaret Chen, `/seed`.
2. Chat: *"Is the patient allergic to penicillin?"* → **Yes** + citation chip.
3. Chat: *"Dr. Lee cleared the penicillin allergy on 2026-03-02 after a negative
   re-test."* → trace shows **Updated**.
4. Chat: *"Is the patient allergic to penicillin?"* → **No**, with full history +
   citations. Open the **Raw** trace toggle, then click a citation → DocumentViewer.
5. Chat: *"The diabetes diagnosis was entered in error, remove it."* → **approval
   card** → Confirm → it vanishes from **Memory Map**.
6. **Compare** tab: same question → smart **No** vs naive **Yes** (the danger you
   avoided).
7. **Memory Map**: drag the **Rewind** slider to February → the allergy is *active*
   again (history retained, not deleted).
8. Drop `samples/fhir-bundle-new-patient.json` (no patient selected) → a brand-new
   chart (Elena Vasquez) appears with four facts — "any document, any format, one drop."

---

## 9. Troubleshooting

- **`/health` cognee = down** or first call hangs: Cognee is initializing its
  databases under `C:\cg\`. Give the first request 3–7s; restart the server once if
  the very first init failed.
- **Vertex auth errors**: ensure ADC is configured for the project in
  `backend/app/config.py` (`VERTEXAI_PROJECT` / `VERTEXAI_LOCATION`). No API key is
  used — remove `GEMINI_API_KEY`/`GOOGLE_API_KEY` from the environment (config strips
  them, but a shell export can still interfere).
- **Upload created the wrong/duplicate patient**: you had a patient selected, so the
  file attached to them; or the name didn't match an existing chart. Deselect first to
  trigger auto-resolution; matching is exact normalized name+DOB or MRN (no fuzzy
  match yet).
- **Naive and smart give the same answer**: you haven't applied the clear event yet —
  do §2 step 2 (or upload `note-existing-patient-heal.txt`). The naive dataset is
  frozen at the pre-heal baseline by design.
- **An approval card reappears after reloading a thread**: it's persisted on the
  message; clicking it again just returns "no longer pending" (safe). The actual
  retraction already happened.
- **Reset for a clean slate**: `POST /reset` then `POST /seed` (or the "Reset all
  memory" link in the Records inbox).
