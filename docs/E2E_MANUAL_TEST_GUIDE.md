# Total Recall — End-to-End MANUAL Test Guide (real user, click-by-click)

> You test this by **using the app like a doctor would** — logging in, opening patients,
> dragging files into the dropbox, chatting, clicking cards. No Python scripts. The only
> command line you touch is starting the two servers.
>
> Everything is **synthetic data · demo only · not medical advice.**

This guide walks every feature the system offers, in the order that tells the story, and
maps each step to the expected result. The synthetic files you'll upload live in:

```
D:\Balaastra\ideas\total-recall\clinical_copilot_synthetic_data\data\sample_uploads\
```

At the end there's a checklist mapping to the 15-point test oracle and a "known
limitations" section.

---

## 0. Start the system (one time)

**Terminal 1 — backend** (do NOT use `--reload`; Cognee init is heavy):
```
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
Wait for `Application startup complete`. The first Cognee call is slow (3–7s).

**Terminal 2 — frontend:**
```
cd frontend
npm run dev
```
Open **http://localhost:5173**.

**Sanity check (optional, Terminal 3):**
```
Invoke-RestMethod http://127.0.0.1:8000/health
```
Expect `ok = True`, `cognee = up`, `ledger = up`.

> Requirements: backend `.venv` present, Google Vertex ADC credentials configured (the
> extraction/judge/answer calls use Vertex Gemini — no API key), and `C:\cg\` writable
> (created automatically). If Vertex isn't configured, the **FHIR + CSV** uploads and all
> the deterministic checks/graph/rewind still work; only **PDF/free-text extraction** and
> **chat answers** need the model.

**Clean slate for a fresh run (optional):** in a REST client hit `POST /reset` for any
patient you've touched, or just delete `C:\cg\ledger.db` while the server is stopped.

---

## 1. Cold-open + Login

1. On first load you'll see the **cinematic cold-open** (plays once per browser session).
   Click **Skip** or let it finish — it wipes ("lights-on") into the light clinical app.
   - ✅ *Expect:* dark neon intro → transitions into a **light** dashboard/login. If you
     want to replay it, open a new private window.
2. You land on **Login**. Pick a clinician (e.g. **Dr. Anjali Mehta · Internal Medicine**).
   - ✅ *Expect:* sub-second, no password. You're taken to the **Dashboard**. The top-right
     shows your name + specialty and a **Sign out** button.

---

## 2. Dashboard (the command center)

You should see: a **Resolve** search bar, a **Patients** grid, a **File a record** dropbox,
and (once charts have flags) a red **critical reminders** strip.

1. **Patients grid** — tiles for Margaret Chen (P001), James O'Sullivan (P002), Aisha
   Rahman (P003), Rahul Sharma (P010), Priya Mehta (P011), Rahul Sharma (P012), Meera Nair
   (P013). Empty charts show no flag pips yet.
   - ✅ *Expect:* each tile shows name, MRN (monospaced), summary, and — once records are
     uploaded — red/amber **risk pips** with an "open flags" count.
2. **Resolver / disambiguation** — type `Rahul Sharma` in the Resolve box, press **Resolve**.
   - ✅ *Expect (oracle #10):* a **two-match** selector — *Rahul Sharma · 52 M · MRN-2010*
     and *Rahul Sharma · 31 M · MRN-2012*. It does **not** auto-pick. Selecting one opens
     that workspace.
   - Try `MRN-2010` → resolves directly to the 52M (single match → opens immediately).

---

## 3. Build Rahul's chart by uploading his files (the natural flow)

This is the heart of the demo: **nothing is pre-loaded** — the chart builds itself from the
documents you drop.

1. From the dashboard, open **Rahul Sharma (P010, 52M)** (click the tile, or resolve by
   `MRN-2010`).
   - ✅ *Expect:* the **Pre-visit brief** tab opens with an **empty state**: "No records yet
     for Rahul Sharma — drop this patient's clinical documents below," and a dropbox.
2. Drag these files (from `sample_uploads\`) onto the brief's dropbox **or** the right-rail
   dropbox, one at a time. Watch each confirm "✓ … · N fact(s) ingested":

   | File | Format | What it should add |
   |---|---|---|
   | `P010_discharge_2019.pdf` | PDF | Type 2 diabetes (Condition) + Metformin 500mg (Medication) |
   | `P010_discharge_2021.pdf` | PDF | **Penicillin allergy** (rash + breathing difficulty, severe) — cites **page 2** |
   | `P010_family_history.json` | FHIR FamilyMemberHistory | Father — myocardial infarction at **age 49** |
   | `P010_intake_form.txt` | free text | **Current smoker**; sedentary |
   | `P010_labs_2024.csv` | CSV | HbA1c **7.8 (high)**, LDL **165 (high)**, Creatinine 1.0 (normal) |
   | `P010_lab_hba1c_2025.pdf` | PDF lab | HbA1c **8.6 (high)** |
   | `P010_lab_renal_2025.pdf` | PDF lab | Creatinine **1.6 (high)** |
   | `P010_lab_recent.fhir.json` | FHIR Observation | HbA1c **8.9 (high)** |
   | `P010_prescription_scan.png` | scanned image | **Rejected on purpose** → "needs-verification" honest error |

   - ✅ *Expect:* FHIR + CSV ingest instantly (deterministic, no model). PDFs/text take a
     couple seconds (Vertex extraction). The **PNG** returns an honest error: "Scanned image
     … flagged needs-verification rather than silently ingested" (oracle #12, deferred OCR).
   - As facts land, the **context chip** at the top gains a red **Penicillin** allergy badge
     and an amber **risk** badge.

> Tip: you can also test **auto-create** — from the dashboard with *no* patient open, drop a
> FHIR/CSV/text file that names a patient; the system detects identity (MRN/`Patient/Pxxx`
> reference/name) and files it, creating a chart if needed.

---

## 4. Pre-visit brief (the hero screen) — oracle #1, #3, #4

With Rahul's files uploaded, look at the **Pre-visit brief** tab.

1. **Chart summary** (left): grouped cards — Conditions, Medications, Allergies, Labs,
   Family history, Lifestyle — each row clickable to its source document.
   - ✅ *Expect:* diabetes + metformin under Conditions/Medications; penicillin under
     Allergies; HbA1c/LDL/creatinine rows under Labs; father MI under Family; smoker under
     Lifestyle. Dates are monospaced.
2. **Top 3 things not to miss** (right): exactly **three warning cards**, each cited:
   - ✅ **Renal follow-up gap** — "Abnormal CREATININE (1.6) with no follow-up," citing
     `P010_lab_renal_2025.pdf` (oracle #3).
   - ✅ **HbA1c rising** — "7.8 → 8.6 → 8.9," citing all three readings (oracle #1).
   - ✅ **Combined cardiovascular risk** — "father MI + current smoker + elevated LDL 165,"
     each contributing fact cited (oracle #4).
3. Click any **citation chip** on a card.
   - ✅ *Expect:* the **source document viewer** opens at that record (page-referenced for
     the allergy).

> If a PDF's model extraction under-produced (e.g. only 2 of 3 HbA1c readings), the HbA1c
> trend still fires from the CSV + FHIR readings. The renal gap needs
> `P010_lab_renal_2025.pdf` to have ingested the 1.6 value; the CV card needs the intake
> form (smoking) + CSV (LDL) + family FHIR.

---

## 5. Consult (the chat agent) — the "one chat does everything" story

Switch to the **Consult** tab (chat is scoped to Rahul via a closure — it literally cannot
see another patient).

1. **Recall (grounded + cited).** Ask: `Is this patient allergic to penicillin?`
   - ✅ *Expect:* a structured **Answer card** (Answer · Reason · Evidence · Confidence ·
     What's missing · Suggested action), a **citation chip** to the 2021 discharge summary,
     and a one-line **tool trace** ("Recalled memory") with a **Raw** toggle showing the
     exact tool/args/timing. Certainty = settled.
2. **Prescribe-time safety (the money moment) — oracle #2.** Ask:
   `Can I prescribe amoxicillin?`
   - ✅ *Expect:* a **critical red allergy card** slides in: amoxicillin is a penicillin /
     beta-lactam, patient has a documented penicillin allergy (rash + breathing difficulty),
     citing `P010_discharge_2021.pdf` **p.2**. Nothing is written. The trace shows a
     `propose_order` (prescribe check) call, not a recall.
   - Contrast: ask `Can I prescribe azithromycin?` → ✅ no conflict (macrolide, not
     cross-reactive) — "safety screen only, confirm dosing."
3. **Not-to-miss on demand.** Ask: `What should I not miss for this patient?`
   - ✅ *Expect:* `run_clinical_checks` runs; the same 3 cards render in chat.
4. **Timeline.** Ask: `Give me the timeline.`
   - ✅ *Expect:* chronological events (diagnoses, meds, labs, allergy, family).
5. **Ingest / self-heal in chat.** Type a new fact, e.g.:
   `Dr. Rao switched Rahul from metformin to metformin 1000mg on 2026-06-01.`
   - ✅ *Expect:* trace shows **"Updated: …"** (the engine classified a change); the brief's
     Medications group / timeline reflect it. (Additive facts auto-execute; they're
     reversible via supersession history.)
6. **Forced grounding (anti-hallucination).** Ask a general medical question with no record,
   e.g. `What's the normal dose of ibuprofen?`
   - ✅ *Expect:* the agent grounds in the patient's chart / declines to answer from
     parametric knowledge for clinical claims — it should not confidently free-answer a
     clinical fact without a tool call. (This is enforced by the system prompt + tested.)

---

## 6. Correction with human approval — oracle #9 (use P003)

1. Go to the dashboard → open **Aisha Rahman (P003)**. Upload
   `sample_uploads\P003_erroneous_dx.txt` (a diagnosis entered in error).
2. In **Consult**, say: `That diagnosis was entered in error — please remove it.`
   - ✅ *Expect:* an inline **approval card**: "Mark *…* as entered in error and remove it?"
     with **Confirm** / **Keep it**. **Nothing is deleted yet** (staged, audit §2.5).
3. Click **Confirm**.
   - ✅ *Expect:* the fact is retracted and disappears from the brief/timeline; if it had
     superseded an older fact, that prior fact is restored; an outcome message is appended.
   - Click **Keep it** on a fresh proposal → ✅ nothing changes.

---

## 7. Timeline + time-travel — oracle #6, #7

Open any patient with history (best on **P001** after §11's self-heal, or Rahul).

1. **Timeline** tab → the force-graph shows fact nodes; dashed arrows = "replaced by".
2. Drag the **Rewind** slider back in time.
   - ✅ *Expect:* node statuses recompute client-side with no network lag; a fact that was
     later superseded shows **active** at the earlier date (history retained, not deleted).
3. Click a **superseded** node.
   - ✅ *Expect:* the **Why panel** opens with the supersession chain: what it was, what
     replaced it, when, who, and the reason (oracle #7).

---

## 8. Compare — the naive villain — oracle #8

Open **Rahul (P010)** → **Compare** tab.

1. Ask the allergy / "can I prescribe amoxicillin" question in the split view.
   - ✅ *Expect:* **Total Recall (smart)** → "No — penicillin allergy, do not prescribe,"
     cited. **Naive baseline (villain)** → the unsafe/stale "looks fine" answer. The
     contrast is the money shot.

---

## 9. Cross-patient isolation (safety) — oracle #11

1. Open **Priya Mehta (P011)**. (Optionally upload `P011_visit_note.txt` +
   `P011_pregnancy_flag.fhir.json` first.)
2. In **Consult**, ask: `Is this patient allergic to penicillin?`
   - ✅ *Expect:* **no penicillin allergy on record for Priya** — the agent answers only
     from P011's chart and does **not** leak Rahul's allergy. Switching patients closes the
     prior context (the chip updates to Priya).

---

## 10. Hereditary variety — oracle #14

1. Open **Meera Nair (P013)**. Upload `P013_family_history.json` (+ `P013_labs.csv`).
2. Look at the brief / ask `what should I not miss?`.
   - ✅ *Expect:* a **hereditary breast-cancer risk** card (first-degree family history),
     **distinct** from the cardiovascular card — proves the check engine generalizes.

---

## 11. Self-heal on P001 (the original supersession story) — oracle #5

P001 has a built-in seed timeline for the classic heal.

1. Reset + seed P001 via a REST client (this one path is easiest seeded, not uploaded):
   ```
   Invoke-RestMethod http://127.0.0.1:8000/reset -Method Post -ContentType application/json -Body '{"patient_id":"P001"}'
   Invoke-RestMethod http://127.0.0.1:8000/seed  -Method Post -ContentType application/json -Body '{"patient_id":"P001"}'
   ```
   *(Or, fully in-app: open P001 and upload `P001_med_switch.txt` / `P001_allergy_cleared.fhir.json` from `sample_uploads\`.)*
2. Open **Margaret Chen (P001)** → **Consult**: `Is she allergic to penicillin?` → "Yes."
3. Say: `Dr. Lee cleared the penicillin allergy on 2026-03-02 after a negative re-test.`
   - ✅ *Expect:* trace shows **"Updated"** (SUPERSEDES). Ask again → **"No — was diagnosed
     …, cleared 2026-03-02 by Dr. Lee,"** with citations (oracle #5).
4. **Timeline** → rewind to **February 2026** → allergy shows **active** again (oracle #6).

---

## 12. Access control + audit — oracle #15

1. **Sign out** (top-right) → log in as **Dr. Vikram Rao (Cardiology)** — his access list is
   only P002 + P010.
2. Try to reach **P001**: use the **Resolve** box → search `Margaret` or `MRN-004471`.
   - ✅ *Expect:* Dr. Rao's resolver is **scoped** — P001 does not resolve for him.
3. (If you open P001 by other means and ask in **Consult**) → ✅ the chat is **refused**
   (403 "You do not have access to this patient") and the refusal is **audited**.
4. **Audit trail** (real, append-only): in a REST client,
   `Invoke-RestMethod "http://127.0.0.1:8000/audit?patient_id=P010"`.
   - ✅ *Expect:* rows for every resolve / recall / order / ingest / forget / approval /
     access-denied, with doctor, timestamp, decision, and evidence fact-ids.

> Note (known scoping detail): the **dashboard grid** currently lists all patients and the
> **brief** endpoint isn't access-scoped; the enforced boundary is at **chat** and
> **resolve**. See "Known limitations."

---

## 13. Multi-format intake coverage — oracle #12, #13

You've already exercised most formats in §3. To confirm each path explicitly:
- **FHIR** (`*.fhir.json`, and bare resources like `P010_family_history.json`) → structured
  parse, **no LLM**, correct types + attributes (oracle #13).
- **CSV** (`P010_labs_2024.csv`, `P002_inr_labs.csv`, `P013_labs.csv`) → one lab fact per
  row with numeric value + flag.
- **PDF** (`*.pdf`) → text extracted, facts + page numbers.
- **Free text** (`*.txt`) → multi-fact extraction (e.g. smoking + family history).
- **PNG** (`P010_prescription_scan.png`) → honest **needs-verification** rejection.

---

## 14. Honest degradation (optional)

- Stop the backend mid-session and send a chat → ✅ the UI shows a plain-language error, not
  a stack trace; the app stays usable when the backend returns.
- The **health pill** (top bar) flips to "connecting…" (amber) when the backend is down.

---

## 15. The 15-point oracle checklist

Tick each as you go (matches `clinical_copilot_synthetic_data/data/test_oracle.json`):

- [~] 1 — Open P010 → exactly 3 cited Top cards (§4)
- [ ~] 2 — P010 "prescribe amoxicillin?" → critical allergy, cites p.2 (§5.2)
- [ ] 3 — Creatinine 1.0→1.6, no nephrology follow-up (§4 renal gap)
- [ ] 4 — CV risk = father MI<50 + smoking + LDL 165, each cited (§4)
- [ ] 5 — P001 ingest allergy-cleared → answer flips to cleared (§11)
- [ ] 6 — P001 rewind to Feb → allergy active (§7/§11)
- [ ] 7 — Click allergy → why-trace: superseded 2026-03-02 Dr. Lee (§7)
- [ ] 8 — Compare tab: naive unsafe vs Total Recall blocks (§8)
- [ ] 9 — P003 remove erroneous dx → vanishes + audit row (§6)
- [ ] 10 — Type "Rahul Sharma" → two-match selector (§2)
- [ ] 11 — In P011, ask Rahul's allergy → no leak (§9)
- [ ] 12 — Drag each format → ingests; PNG → needs-verification (§13)
- [ ] 13 — Upload *.fhir.json → typed facts, no LLM (§13)
- [ ] 14 — Open P013 → hereditary breast-cancer card, distinct from CV (§10)
- [ ] 15 — Doctor opens non-allowed patient → refused + audit (§12)

---

## 16. Every API endpoint (optional REST spot-check)

Browse **http://127.0.0.1:8000/docs** (Swagger) to call any endpoint with schemas:
`/health · /doctors · /patients · /patients/{id}/brief · /patients/resolve · /audit ·
/seed · /ingest · /reset · /forget · /ask · /intake · /upload · /graph · /graph/cognee ·
/why · /chat · /chat/approve · /chat/threads`.

---

## 17. Known limitations (accurate as of this build)

These do **not** block the hero demo, but be aware while testing:

1. **`/why` is the base supersession chain only.** The Phase-4 "eye-catch" cross-confirmation
   (a second Cognee `GRAPH_COMPLETION`/`TEMPORAL` explanation shown next to the ledger trace,
   plus `current_truth`/`sources[]`) is **not implemented**. The why-panel shows the chain,
   date, source, and reason.
2. **`node_set` is not applied to Cognee recall.** Patient isolation is still enforced (per-
   patient datasets + closure-bound tools), but sub-scoping within a patient via `node_set`
   isn't wired.
3. **Facts are stored as natural-language text + ontology grounding, not custom Cognee
   `DataPoint`s with `index_fields`.** Functionally equivalent for this demo; the literal
   "typed DataPoint" primitive isn't used.
4. **Dashboard + `/brief` are not access-scoped.** Access is enforced at `/chat` and
   `/patients/resolve` (agent + resolver refuse out-of-scope patients + audit); a doctor can
   still see other charts' tiles/brief on the dashboard.
5. **Deferred by plan (cut-order, documented):** SSE token streaming, durable turn-resume,
   Cognee ACL (`create_authorized_dataset`), `SearchType.FEEDBACK` reinforcement, ⌘K command
   palette, separate Records/Labs/Meds/Family sub-tabs (folded into the brief), MedGemma/OCR.
6. **PDF / free-text extraction and chat answers require Vertex ADC** at runtime. FHIR + CSV
   uploads, the check engine, graph, rewind, and audit work without the model.

> All data is synthetic. This is a demo, not a medical device, and not medical advice.
