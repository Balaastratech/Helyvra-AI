# Phase 6 — Polish, hardening & deploy decision

> Goal: remove rough edges; produce a reliable shareable link.
> Inputs: app works end-to-end locally.

## A. Polish (frontend)
- Loading spinners + disabled buttons on every async action; optimistic toasts.
- Empty states (pre-seed), error toasts (API down), retry.
- Responsive at 1280–1440px (record demo at 1440); graph panel min-height.
- a11y pass: focus rings, aria labels, status conveyed by icon+text (not color alone).
- Final clinical-pro polish: consistent spacing, one accent, no console warnings.

## B. Hardening (backend)
- `spend.log`: log each LLM call (which model, tokens if available) + a per-run cap that aborts gracefully.
- Defensive: `/graph` empty → `{nodes:[],edges:[]}`; `/why` unknown id → 404 JSON; global exception handler → clean JSON error.
- `seed-on-startup` flag (`SEED_ON_START=1`) so a fresh deploy is demo-ready.
- Pin versions in `requirements.txt`; freeze a working `pip freeze` snapshot.

## C. Serve frontend from FastAPI (one link)
- `npm run build` → copy `frontend/dist` → mount `StaticFiles` at `/` in `main.py` (API under `/api/*`). One service, one URL.

## D. Deploy decision (pick ONE — both recipes ready)

### Option 1 — Cloud Run (always-on link; recommended for async judging)
- **Dockerfile:** `python:3.12-slim`; install deps; **prefetch fastembed model** at build (so cold start is fast); set `COGNEE_SYS_DIR=/data/sys COGNEE_DATA_DIR=/data/data` (Linux → no path-limit issue); `CMD uvicorn app.main:app --host 0.0.0.0 --port 8080`.
- **Auth = zero keys:** deploy with a **service account** granted `roles/aiplatform.user`; Vertex picks it up via ADC automatically. Set `VERTEXAI_PROJECT/LOCATION` env on the service. (No `gcloud auth` needed in the container.)
- **Persistence:** Cloud Run fs is ephemeral → set `--min-instances=1` + `SEED_ON_START=1` (re-seeds the synthetic demo on cold start). That's fine for a demo. (Optional: GCS volume mount if you want durable state — not needed.)
- **Deploy:** `gcloud run deploy total-recall --source . --region us-central1 --service-account <sa> --set-env-vars ... --min-instances=1 --allow-unauthenticated`.
- **Cost:** small; hits GCP credits.

### Option 2 — Cloudflare Tunnel (simplest; link lives while laptop runs)
- Run backend locally (serving built frontend); `cloudflared tunnel --url http://localhost:8000` → public HTTPS URL. Reinforces "self-hosted". Link dies when laptop sleeps.

**Recommendation:** Cloud Run for a 24/7 judge-proof link; keep Cloudflare Tunnel as the backup for live demos.

## E. Acceptance (done-when)
- Chosen target cold-starts and a second device opens the link and runs the full demo (seed → heal → contrast → scrub → why).
- No keys in the image/repo; `.env` gitignored; ADC/SA only.
- No console/server errors during the demo path.

## F. Risks
- fastembed download on cold start → prefetch in Docker build.
- Cognee migrations on first boot (seen in logs) → run once at startup before serving; healthcheck waits.
- Vertex region/model availability in Cloud Run SA project → same project/region as Phase 0 (already verified).

## Done → `start Phase 7`.

---

## Backend reality check (post Phase-2 / 2b)

- **Static-serve hook already stubbed** in `app/main.py` (commented `StaticFiles`
  mount block). Phase 6C = `npm run build` → uncomment + point at `frontend/dist`.
  Keep API routes (they're at root now, e.g. `/seed`); if you prefer `/api/*`, add a
  prefix when including routers and update `client.ts`.
- **Defensive coverage must include `/forget`:** unknown `fact_id` → 404 JSON (done);
  Cognee delete failure → response still returns with `forgotten:false` + error in the
  `cognee` summary (done — don't 500 the request).
- **`reset` / `seed` already wipe everything** (`cognee.forget(everything=True)`-style
  via `prune`). `SEED_ON_START=1` should call the seed flow on startup for deploys.
- **`/health`** already returns `{ok,cognee,ledger}` — use it as the container
  healthcheck; it must pass AFTER Cognee migrations run on first boot.
- **Windows→Linux:** the `C:\cg` short-path fix is Windows-only; in the container set
  `COGNEE_SYS_DIR=/data/sys`, `COGNEE_DATA_DIR=/data/data`, `LEDGER_DB=/data/ledger.db`,
  `ENGINE_CHECKPOINTS=/data/engine_checkpoints.sqlite` (all already env-driven).
