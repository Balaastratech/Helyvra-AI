"""
POST /chat — multi-turn tool-calling agent (recall / ingest / propose-correction / explain).
POST /chat/approve — execute or discard a staged correction (the forget approval gate).
GET  /chat/threads — list threads for a patient.
GET  /chat/threads/{thread_id}/messages — get messages in a thread.
POST /chat/threads — create a new thread.
DELETE /chat/threads/{thread_id} — delete a thread.

The agent decides per turn which memory tool(s) to call (§7). Its answers are
cited and certainty-aware (§6); destructive corrections are STAGED for one-click
human approval rather than executed mid-turn (§7.1). Chat history is persisted
server-side and also stored in Cognee for semantic recall.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.agent import history, pending, router as agent_router, tools as agent_tools
from app import audit, auth
from app.memory import records

api_router = APIRouter(tags=["chat"])


# --- DTOs ---
class ChatRequest(BaseModel):
    patient_id: str
    message: str
    thread_id: Optional[str] = None  # None = create a new thread automatically
    doctor_id: Optional[str] = None  # simulated identity for access control + audit (§7)


class ChatResponse(BaseModel):
    reply: str
    intent: str
    thread_id: str
    fact_id: Optional[str] = None
    actions: List[str] = []  # human-readable chips for tool actions the agent took this turn
    # v3 surfacing (§6/§8): grounding citations, honest certainty, the per-turn
    # tool trace, and any staged correction awaiting approval.
    citations: List[Dict[str, Any]] = []
    certainty: str = "settled"  # settled | contested | low_confidence
    trace: List[Dict[str, Any]] = []
    pending: Optional[Dict[str, Any]] = None
    cards: List[Dict[str, Any]] = []            # clinical safety cards (§5.2)
    answer: Optional[Dict[str, Any]] = None     # six-part structured answer contract (§5.3)


class ChatApproveRequest(BaseModel):
    pending_id: str
    decision: str = "approve"  # "approve" | "reject"
    doctor_id: Optional[str] = None  # who approved (audited)


class ChatApproveResponse(BaseModel):
    ok: bool
    decision: str
    message: str
    fact_id: Optional[str] = None
    restored_fact_id: Optional[str] = None
    forgotten: bool = False


class ThreadResponse(BaseModel):
    id: str
    patient_id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    timestamp: str
    intent: Optional[str] = None
    # Persisted surfacing data for assistant turns (§7.5): citations/certainty/
    # trace/pending — lets the UI re-render the agent's work after a reload.
    citations: List[Dict[str, Any]] = []
    certainty: str = "settled"
    trace: List[Dict[str, Any]] = []
    pending: Optional[Dict[str, Any]] = None
    cards: List[Dict[str, Any]] = []
    answer: Optional[Dict[str, Any]] = None


# --- Routes ---

@api_router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to the conversational agent."""
    if not records.get_patient(req.patient_id):
        raise HTTPException(404, f"Unknown patient: {req.patient_id}")

    # Access boundary (§7): if a doctor identity is supplied, it must have this
    # patient on its access list. A refusal is itself audited. No doctor => demo
    # open mode (still audited as 'unknown').
    doctor = req.doctor_id or "unknown"
    if req.doctor_id and not auth.can_access(req.doctor_id, req.patient_id):
        audit.log(doctor, "access_denied", req.patient_id, decision="not on access list")
        raise HTTPException(403, "You do not have access to this patient.")

    # Resolve or create thread
    thread_id = req.thread_id
    if not thread_id:
        thread = history.create_thread(req.patient_id, title=req.message[:80])
        thread_id = thread.id
    else:
        existing = history.get_thread(thread_id)
        if not existing:
            raise HTTPException(404, f"Unknown thread: {thread_id}")

    result = await agent_router.handle_message(
        patient_id=req.patient_id,
        thread_id=thread_id,
        message=req.message,
        doctor=doctor,
    )

    return ChatResponse(
        reply=result["reply"],
        intent=result.get("intent", "agent"),
        thread_id=thread_id,
        fact_id=result.get("fact_id"),
        actions=result.get("actions", []),
        citations=result.get("citations", []),
        certainty=result.get("certainty", "settled"),
        trace=result.get("trace", []),
        pending=result.get("pending"),
        cards=result.get("cards", []),
        answer=result.get("answer"),
    )


@api_router.post("/chat/approve", response_model=ChatApproveResponse)
async def chat_approve(req: ChatApproveRequest) -> ChatApproveResponse:
    """Execute (approve) or discard (reject) a staged correction — the ONLY path
    that actually retracts a fact (§7.1). Popping the proposal makes a repeat
    approve/reject a safe no-op (idempotent, §7.5)."""
    proposal = pending.pop_pending(req.pending_id)
    if proposal is None:
        # Already handled, or never existed — honest, non-fatal.
        return ChatApproveResponse(
            ok=False, decision=req.decision,
            message="That correction is no longer pending (already handled or expired).",
        )

    if req.decision == "reject":
        audit.log(
            req.doctor_id or "unknown", "approve", proposal["patient_id"],
            decision=f"rejected correction of {proposal['label']}",
            evidence_ids=[proposal["fact_id"]],
        )
        return ChatApproveResponse(
            ok=True, decision="reject",
            message=f"Kept '{proposal['label']}' in the record — correction discarded.",
            fact_id=proposal["fact_id"],
        )

    retracted, restored = await agent_tools.execute_forget(
        proposal["patient_id"], proposal["fact_id"], proposal.get("reason", "entered in error")
    )
    if retracted is None:
        return ChatApproveResponse(
            ok=False, decision="approve", fact_id=proposal["fact_id"],
            message="That fact was already removed — nothing further to do.",
        )
    msg = f"Marked '{retracted.label}' as entered in error and removed it from memory."
    if restored:
        msg += f" Restored the prior fact it had replaced: {restored.label}."
    audit.log(
        req.doctor_id or "unknown", "forget", proposal["patient_id"],
        decision=f"approved retraction of {retracted.label}",
        evidence_ids=[e for e in [retracted.id, restored.id if restored else None] if e],
    )
    return ChatApproveResponse(
        ok=True, decision="approve", forgotten=True,
        fact_id=retracted.id,
        restored_fact_id=restored.id if restored else None,
        message=msg,
    )


@api_router.get("/chat/threads", response_model=List[ThreadResponse])
def list_threads(patient_id: str = Query(...)) -> List[ThreadResponse]:
    """List all chat threads for a patient."""
    threads = history.list_threads(patient_id)
    return [
        ThreadResponse(
            id=t.id, patient_id=t.patient_id, title=t.title,
            created_at=t.created_at, updated_at=t.updated_at,
        )
        for t in threads
    ]


@api_router.post("/chat/threads", response_model=ThreadResponse)
def create_thread(patient_id: str = Query(...), title: str = Query("")) -> ThreadResponse:
    """Create a new chat thread."""
    if not records.get_patient(patient_id):
        raise HTTPException(404, f"Unknown patient: {patient_id}")
    thread = history.create_thread(patient_id, title)
    return ThreadResponse(
        id=thread.id, patient_id=thread.patient_id, title=thread.title,
        created_at=thread.created_at, updated_at=thread.updated_at,
    )


@api_router.get("/chat/threads/{thread_id}/messages", response_model=List[MessageResponse])
def get_messages(thread_id: str) -> List[MessageResponse]:
    """Get all messages in a thread."""
    thread = history.get_thread(thread_id)
    if not thread:
        raise HTTPException(404, f"Unknown thread: {thread_id}")
    messages = history.get_messages(thread_id, limit=200)
    out: List[MessageResponse] = []
    for m in messages:
        meta = {}
        if m.meta:
            try:
                meta = json.loads(m.meta)
            except (ValueError, TypeError):
                meta = {}
        out.append(
            MessageResponse(
                id=m.id, thread_id=m.thread_id, role=m.role,
                content=m.content, timestamp=m.timestamp, intent=m.intent,
                citations=meta.get("citations", []),
                certainty=meta.get("certainty", "settled"),
                trace=meta.get("trace", []),
                pending=meta.get("pending"),
                cards=meta.get("cards", []),
                answer=meta.get("answer"),
            )
        )
    return out


@api_router.delete("/chat/threads/{thread_id}")
def delete_thread(thread_id: str) -> dict:
    """Delete a thread and all its messages."""
    thread = history.get_thread(thread_id)
    if not thread:
        raise HTTPException(404, f"Unknown thread: {thread_id}")
    history.delete_thread(thread_id)
    return {"ok": True, "deleted": thread_id}
