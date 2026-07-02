"""
Agent-side stores for the human-approval gate (§7.1) and write idempotency (§7.5).

Two small process-local stores:

  * pending forget proposals — `propose_forget` stages a destructive correction
    here instead of executing it; `POST /chat/approve` is the ONLY path that
    actually retracts. Mirrors Manthan's Investigate -> Decide -> Approve split
    for anything that mutates/deletes memory.
  * write idempotency cache — a retried or duplicate write tool call (same patient
    + same normalized text in a turn) returns the prior result instead of
    double-applying it.

ponytail: both are in-process dicts — fine for a single-box demo. A process
restart drops pending proposals and the idempotency cache. Upgrade to a shared
key store (SQLite table / Redis) only if this ever runs multi-instance.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Dict, Optional

# pending_id -> proposal dict {patient_id, fact_id, label, reason, created_at}
_pending: Dict[str, dict] = {}

# idempotency key -> result summary string (write already applied this key)
_idempotency: Dict[str, str] = {}


def make_key(*parts: str) -> str:
    """Stable idempotency key from its parts (e.g. patient_id + normalized text)."""
    norm = "\x1f".join(p.strip().lower() for p in parts)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def seen_write(key: str) -> Optional[str]:
    """Return the stored result if this write key was already applied, else None."""
    return _idempotency.get(key)


def record_write(key: str, result_summary: str) -> None:
    """Mark a write key as applied with its result summary."""
    _idempotency[key] = result_summary


def add_pending(patient_id: str, fact_id: str, label: str, reason: str) -> dict:
    """Stage a forget proposal; returns the proposal (with its `pending_id`)."""
    pid = str(uuid.uuid4())
    proposal = {
        "pending_id": pid,
        "patient_id": patient_id,
        "fact_id": fact_id,
        "label": label,
        "reason": reason,
        "created_at": datetime.utcnow().isoformat(),
    }
    _pending[pid] = proposal
    return proposal


def get_pending(pending_id: str) -> Optional[dict]:
    return _pending.get(pending_id)


def pop_pending(pending_id: str) -> Optional[dict]:
    """Remove and return a proposal (so a second approve/reject is a no-op — the
    natural idempotency for the approval path)."""
    return _pending.pop(pending_id, None)
