# Phase 0 — Vertex wiring + temporal confirmed

> Goal: Cognee runs locally using **Vertex AI Gemini with NO API key** (ADC), and the
> temporal before/after behaviour is proven on the P001 patient timeline.
> Outcome gate for the whole project — if this passes, every later phase is safe.

## Config values (locked)
- Project: `ai-negotiation-copilot` · Region: `us-central1`
- Extraction model: `gemini-2.5-flash` (Cognee/LiteLLM, prefix `vertex_ai/`)
- Judge model: `gemini-2.5-pro` (used later, Phase 1)
- Cheaper extraction option to try later: `gemini-3.1-flash-lite`
- Embeddings: `fastembed` local (`all-MiniLM-L6-v2`, 384) — $0, no key
- Cognee storage root (Windows path fix): `C:\cg\sys`, `C:\cg\data`

## Prerequisites (one-time, you run these)
```powershell
# Vertex API on + ADC quota project (avoids quota warnings)
gcloud services enable aiplatform.googleapis.com --project ai-negotiation-copilot
gcloud auth application-default set-quota-project ai-negotiation-copilot
# (ADC login already done per your confirmation)
```
Also make sure **no** `GEMINI_API_KEY` / `GOOGLE_API_KEY` is set in your shell/profile — `config.py` also strips them at runtime, but a profile-level export should be removed.

## Files created this phase
- `backend/requirements.txt` — full project deps (install once).
- `backend/.env.example` → copy to `backend/.env`.
- `backend/app/__init__.py`, `backend/app/config.py` — the Vertex/Cognee wiring (single seam).
- `backend/verify_vertex.py` — runs the P001 timeline through Vertex + temporal and asserts correctness.

## Steps
1. `cd backend` → create venv → `pip install -r requirements.txt` (first run downloads fastembed model ~90 MB).
2. `copy .env.example .env` (defaults already match your project; edit only if needed).
3. `python verify_vertex.py`.

## Acceptance criteria (Phase 0 passes when ALL true)
- Script prints `Provider=custom Model=vertex_ai/gemini-2.5-flash Project=ai-negotiation-copilot`.
- "before February" → **allergic**; "after March" → **NOT allergic**; "medication now" → **amlodipine**.
- Current-truth `GRAPH_COMPLETION` → **not allergic**.
- No API-key assertion fires (proves we're on ADC/Vertex).
- No `LanceError` (proves the short-path fix holds).

## Troubleshooting (known Vertex/Cognee gotchas)
- `DefaultCredentialsError` → ADC missing/wrong quota project → re-run the two `gcloud` commands above.
- `PermissionDenied` / 403 → Vertex API not enabled or model not granted in the project/region.
- Cognee complains about missing `LLM_API_KEY` → add `LLM_API_KEY=vertex-adc` to `.env` (LiteLLM ignores it on the `vertex_ai/` path; it just satisfies Cognee's config validation).
- `404 model not found` → confirm the model ID is available in `us-central1`; try `gemini-2.5-flash` exactly, or switch to `gemini-3.1-flash-lite`.
- Still slow first run → fastembed model download; subsequent runs are fast.

## Rollback / safety
- Pure additive: only creates `backend/` + `C:\cg` storage. Delete `C:\cg` to reset Cognee state. No changes to the spike or to Organizer.

## Done → next
When acceptance passes, say **"start Phase 1"** and I'll generate the LangGraph self-healing engine plan + code.
