# Design: Duplicate Prevention, Image Uploads, Faster Consult Chat

Date: 2026-07-04
Status: Approved (pending user sign-off on this doc)

## Context

Four independent gaps found in the intake and answer pipelines during a research
pass (see prior conversation for full findings):

1. No file-hash dedup on upload — the same document re-uploaded creates a second
   `UP-*` doc, re-runs (paid) LLM extraction, and re-runs the full fact
   reconciliation engine. The judge (`engine/nodes.py`) does mark the repeat
   CONSISTENT/SUPERSEDES, so the ledger doesn't visibly double, but the doc list
   and audit trail do.
2. `POST /patients` (manual chart creation) has no uniqueness check at all, while
   the intake pipeline already resolves duplicates correctly via
   `patient_index.resolve()`. The two code paths are inconsistent.
3. The backend fully supports image ingestion (Gemini vision extraction is wired
   in `pipeline.py`), but `DropZone.tsx`'s file-picker `accept` attribute excludes
   every image extension, so the picker is the only thing blocking it.
4. A single clinical question in the doctor-facing chat (`/chat`) costs **three
   sequential Vertex Flash calls** (~3-9s): agent decides to call
   `recall_patient_facts` → that tool itself calls `synthesize_answer` (a second
   LLM call) → agent re-paraphrases the tool's already-complete answer into a
   reply (a third LLM call that adds no accuracy, only latency).

## Goals

- Doctor never sees a duplicate document/chart from a re-upload or a manual
  create, without losing the ability to intentionally re-process a corrected
  file.
- Manual and automatic patient creation use one matching rule, not two.
- Images (jpg/png/webp/heic/heif) are selectable and ingestible end-to-end.
- The common single-question consult-chat turn drops from 3 LLM calls to 1,
  streamed, with **zero change to the answer's content, citations, or
  certainty** — this is a system fix, not a model swap or an accuracy
  trade-off.

## Non-goals

- No new dependency, no new datastore (SQLite/Postgres) — everything here is a
  small JSON file or reuses existing code paths, matching how the rest of the
  intake layer already stores state (`data/patients_user.json`,
  `data/access.json`, etc.).
- No change to the `/ask` Compare-tab pipeline (naive vs. smart demo) — that's
  a separate, deliberately-frozen surface.
- No HEIC→JPEG conversion code written speculatively — only added if Vertex
  actually rejects HEIC bytes in testing.

---

## 1. Upload dedup

### Data flow

```
POST /intake or /intake/batch
  -> hash = sha256(raw_bytes)
  -> lookup hash in data/upload_hashes.json
       found AND not force=true:
         -> return {duplicate: true, existing: {doc_id, patient_id, patient_name, uploaded_at}}
            (no extraction, no engine run — same short-circuit for cost as for UX)
       not found OR force=true:
         -> pipeline.run() as today
         -> on success: record hash -> {doc_id, patient_id, filename, uploaded_at}
```

### Components

- `app/intake/upload_hashes.py` (new, ~30 lines): `lookup(hash) -> dict | None`,
  `record(hash, doc_id, patient_id, filename)`. Same read/write-whole-file
  pattern as `app/memory/records.py` already uses for
  `data/patients_user.json` — no new persistence pattern introduced.
- `routes_intake.py`: hash check inserted before `pipeline.run()` in both
  `/intake` and the per-file loop of `/intake/batch`; new `force: bool = Form(False)`
  param on both.
- `IntakeResponse`/`BatchIntakeItem` DTOs gain optional
  `duplicate: bool = False` and `duplicate_of: dict | None` fields.

### Frontend

- `DropZone.tsx`: on a `duplicate: true` response, show a confirm
  (`"{filename} was already uploaded for {patient_name} on {date}. Upload anyway?"`).
  On confirm, resubmit the same file with `force=true`. On cancel, treat as a
  no-op (not an error) in the status line.

### Error handling

- Hash lookup/record I/O failures degrade to "treat as not-a-duplicate" (never
  block a legitimate upload because the dedup index itself is broken) —
  consistent with how `family_resolver.resolve_links` is already best-effort
  and swallows errors.

### Testing

- One `test_upload_hashes.py`: assert `record()` then `lookup()` round-trips;
  assert `lookup()` on an unseen hash returns `None`.
- One manual check via `/intake` twice with the same bytes: second call
  without `force` returns `duplicate: true` and does not create a second
  `UP-*` doc; with `force=true` it does create one (existing fact-dedupe
  behavior unchanged).

---

## 2. Patient dedup on manual create

### Change

`routes_patients.py: create_patient()` calls
`patient_index.resolve(req.name, req.dob, req.mrn)` first (MRN exact match →
name+DOB exact match → auto-create — the same three-tier rule intake already
uses, not a new/weaker single-factor check). If it resolves to an existing
`patient_id`, return that existing `Patient` (still HTTP 200 — a create-or-find
semantic, not an error) instead of calling `records.add_patient()` again. Only
falls through to creating a new record when `resolve()` itself doesn't find a
match.

### Testing

- `test_routes_patients.py`: create a patient, then POST `/patients` again with
  the same name+DOB — assert the response `patient_id` is identical to the
  first call's and no second entry appears in `records.list_patients()`.

---

## 3. Image upload support

### Backend

`pipeline.py`: extend `_IMAGE_EXTS` to include `.webp`, `.heic`, `.heif`, and
extend `_image_mime()`'s extension→MIME map to match.

### Frontend

`DropZone.tsx`: extend the file input's `accept` to
`.pdf,.json,.txt,.md,.csv,.jpg,.jpeg,.png,.webp,.heic,.heif` and update the
hint text under the drop target to mention photos/scans.

### Known risk, deliberately not pre-solved

Vertex's Gemini vision endpoint accepts JPEG/PNG/WEBP reliably; HEIC/HEIF
support varies by SDK/model version. If ingestion of a real HEIC file fails
at `extract_facts_rich_from_image`, the fix is a `pillow-heif`-based
conversion to JPEG bytes before the vision call — not written now, since we
have not confirmed the failure mode exists. `.heic`/`.heif` still ship in the
accept list because failing gracefully (a clear ingest error) is preferable to
blocking the file type outright.

### Testing

- Extend whatever existing intake test fixtures cover `sniff_format()` with
  one `.webp` filename case, asserting it returns `"image"`.

---

## 4. Consult chat speed (short-circuit + streaming)

### Current flow (3 sequential Vertex calls)

```
round 1: generate_content() -> model emits function_call(recall_patient_facts)
         tool runs synthesize_answer() -> Vertex call #2, returns cited/certain answer
round 2: generate_content() -> model paraphrases tool's text into final reply  [REMOVED]
```

### New flow (1 call for the common case)

```
round 1: generate_content() -> model emits function_call(recall_patient_facts)
         tool runs synthesize_answer() -> Vertex call #2
if this round's calls are exactly one read-only tool
   (recall_patient_facts | run_clinical_checks | propose_order | get_timeline | why_changed)
   and the model made no other calls this round:
       reply = tool's own returned text, verbatim — no round 2
else:
   round 2 runs as today (model composes a reply over multiple tool results,
   e.g. recall + propose_forget in the same turn)
```

This is a pure latency change: the reply text, citations, certainty, and cards
returned to the UI are **byte-for-byte what the tool already produced** —
`recall_patient_facts` already returns fully-formed, grounded, cited prose
(`tools.py:277-284`); round 2 was re-stating it, not improving it.

### Components

- `agent/router.py: handle_message()` — after building `calls` for a round,
  check: `len(calls) == 1 and calls[0].name in _SINGLE_SHOT_TOOLS`. If true and
  this is the first round, use the tool's string result as `reply` and `break`
  instead of appending the function response and looping again.
  `_SINGLE_SHOT_TOOLS = {"recall_patient_facts", "run_clinical_checks", "propose_order", "get_timeline", "why_changed"}` —
  `ingest_fact` and `propose_forget` are excluded because their raw tool output
  ("Recorded 'X' (classification: NEW).") is a log line, not a doctor-facing
  reply; those always need round 2 to phrase a human reply.

### Streaming

- New `stream: bool` support on `/chat` (or a parallel `/chat/stream` SSE
  endpoint — implementation detail decided at plan time) that swaps
  `generate_content` for `generate_content_stream` on the round whose output
  becomes the final reply, and forwards text chunks to the client as they
  arrive. Tool-calling rounds (which must be inspected for `function_call`
  parts before anything can stream) are unaffected — only the last,
  reply-producing round streams.
- Frontend `ChatPane`/`SplitChat`: render incoming chunks as they arrive
  instead of waiting for the full JSON response.

### Error handling

- If streaming the final round fails mid-stream (transport error), fall back
  to the existing non-streaming error reply path (`"Sorry, I hit an error
  reaching the model..."`) — same behavior as today, just triggered from a
  stream-read exception instead of a `generate_content` exception.

### Testing

- `test_router_single_shot.py`: mock a model response with exactly one
  `recall_patient_facts` call and assert `handle_message()` returns the tool's
  text without a second `generate_content` invocation (assert the mock was
  called once, not twice).
- One case with `ingest_fact` + no other calls: assert round 2 *does* run
  (unchanged behavior).

---

## Rollout order

Independent pieces, no shared code between them — can ship in any order or in
parallel:
1. Patient dedup (smallest diff, one function call added).
2. Upload dedup (new small module + two route edits + one frontend confirm).
3. Image support (two small edits, no new module).
4. Chat speed (router change + streaming, the only piece touching the
   doctor-facing chat surface — worth its own test pass before/after since
   it changes response timing behavior directly).
