"""
CLEAN SLATE — wipe all patient memory + state for a fresh demo.

Clears BOTH layers:
  Runtime memory  : ledger, Cognee (graph+vectors+relational), engine checkpoints,
                    chat threads, audit log.
  Repo data       : auto-created patients (patients_user.json), family links, and
                    every uploaded file under data/patients/*/uploads/.

KEEPS your source material: the seed patient registry (patients.json), the P001
timeline, and the demo/sample upload files (data/demo_uploads, data/sample_uploads).

IMPORTANT: stop the backend server first (Windows locks the .db files while it runs).

Run:  cd backend && .venv/Scripts/python.exe scripts/clean_slate.py
      add  --yes  to skip the confirmation prompt.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CG = Path(os.environ.get("CG_ROOT", r"C:\cg"))


def _rm(p: Path) -> str:
    try:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            return f"removed dir  {p}"
        if p.exists():
            p.unlink()
            return f"removed file {p}"
        return f"(absent)     {p}"
    except Exception as exc:  # Windows file lock → tell the user to stop the server
        return f"FAILED       {p}  ({type(exc).__name__}: {exc} — is the server running?)"


def _reset_json(p: Path, empty: dict) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(empty, indent=2), encoding="utf-8")
    return f"reset file   {p}"


async def _reset_via_app() -> list[str]:
    """Use the app's own reset functions (also prunes Cognee cleanly)."""
    out = []
    try:
        import app.config  # noqa: F401 (wires Cognee/Vertex)
        from app.memory import cognee_client, ledger
        from app.engine import service
        ledger.reset(); out.append("ledger.reset()")
        service.reset_checkpoints(); out.append("engine checkpoints reset")
        await cognee_client.seed_reset(); out.append("cognee pruned (data + system)")
    except Exception as exc:
        out.append(f"app-level reset skipped ({type(exc).__name__}: {exc}) — falling back to file deletion")
    return out


def main() -> None:
    if "--yes" not in sys.argv:
        print(__doc__)
        if input("Wipe all memory + auto-created patients + uploads? [y/N] ").strip().lower() != "y":
            print("aborted."); return

    log: list[str] = []

    # 1. App-level resets (ledger, checkpoints, Cognee) — best-effort.
    log += asyncio.run(_reset_via_app())

    # 2. Delete runtime DB files that the app resets DON'T cover.
    for name in ("chat.db", "audit.db"):
        log.append(_rm(CG / name))
    # engine checkpoint stragglers (wal/shm) + ledger (in case app reset was skipped)
    for name in ("engine_checkpoints.sqlite", "engine_checkpoints.sqlite-wal",
                 "engine_checkpoints.sqlite-shm", "ledger.db"):
        log.append(_rm(CG / name))
    # Cognee storage dirs (full wipe; they rebuild on next ingest)
    log.append(_rm(CG / "data"))
    log.append(_rm(CG / "sys"))

    # 3. Reset repo data files (keep seed registry + source uploads).
    log.append(_reset_json(DATA / "patients_user.json", {"patients": []}))
    log.append(_reset_json(DATA / "family_links.json", {"links": []}))

    # 4. Clear every patient's uploaded files (keep documents.json).
    for up in DATA.glob("patients/*/uploads"):
        log.append(_rm(up))

    print("\n".join(log))
    print("\nClean slate ready. Restart the backend, then upload data/demo_uploads/* to rebuild.")


if __name__ == "__main__":
    main()
