"""
FastAPI app — the HTTP surface over the self-healing engine + Cognee memory.

Importing `app.config` first wires Vertex / embeddings / Cognee storage before
any Cognee call. CORS allows the Vite dev server (Phase 3). A static-serve hook
is left for Phase 6 (serve the built frontend from the same origin).

Run:
    cd backend
    python -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import asyncio
import os

import app.config as config  # noqa: F401  (MUST be first — wires Cognee/Vertex)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_access, routes_ask, routes_chat, routes_family, routes_graph, routes_intake, routes_patients, routes_scenario
from app.agent import history as chat_history
from app import audit
from app.memory import cognee_client, ledger, records

app = FastAPI(
    title="Total Recall API",
    version="0.2.0",
    description="Self-healing, temporal patient memory — smart vs naive (demo only, synthetic data).",
)

# CORS: Vite dev server. Extra origins can be added via CORS_ORIGINS (comma-sep).
_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra = os.environ.get("CORS_ORIGINS", "")
if _extra:
    _origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_scenario.router)
app.include_router(routes_patients.router)
app.include_router(routes_access.router)
app.include_router(routes_ask.router)
app.include_router(routes_graph.router)
app.include_router(routes_intake.router)
app.include_router(routes_family.router)
app.include_router(routes_chat.api_router)


@app.on_event("startup")
def _startup() -> None:
    # Ensure the ledger schema exists before the first request.
    ledger.init()
    chat_history.init()
    audit.init()
    # Warm the Cognee graphs in the background (env-gated) so the demo isn't cold.
    try:
        asyncio.get_event_loop().create_task(_maybe_precompute())
    except RuntimeError:  # pragma: no cover - no running loop (e.g. some test runners)
        pass


async def _precompute_seed() -> None:
    """Cognify every seed patient's dataset once so the live demo is warm."""
    for p in records.list_patients():
        try:
            await cognee_client.cognify(p["patient_id"], temporal=False)
        except Exception:  # pragma: no cover - warmup is best-effort
            pass


async def _maybe_precompute() -> None:
    if os.environ.get("PRECOMPUTE_SEED") == "1":
        await _precompute_seed()


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "total-recall",
        "version": app.version,
        "disclaimer": "Demo only — synthetic data, not medical advice.",
        "endpoints": [
            "POST /seed", "POST /ingest", "POST /reset", "POST /forget",
            "POST /ask", "GET /graph", "GET /graph/cognee",
            "GET /why", "GET /health",
        ],
    }


# --- Phase 6 hook: serve the built frontend from this origin --------------
# from fastapi.staticfiles import StaticFiles
# _DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
# if os.path.isdir(_DIST):
#     app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
