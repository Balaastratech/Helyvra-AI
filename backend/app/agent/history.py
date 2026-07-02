"""
Chat history persistence via Cognee datasets.

Each patient gets a chat dataset (chat_{patient_id}) that stores conversation
turns. Cognee is the hero — we store the chat as semantic memory so the agent
can recall past conversations contextually.

Additionally, a local SQLite table keeps the structured thread/message list for
the UI to display (Cognee stores meaning, SQLite stores the verbatim transcript).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

import app.config as config  # noqa: F401
import cognee

# --- SQLite store for verbatim chat history --------------------------------
_DB_PATH = os.environ.get("CHAT_DB", r"C:\cg\chat.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    thread_id: str = Field(index=True)
    patient_id: str = Field(index=True)
    role: str  # "user" | "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    intent: Optional[str] = None  # answer | why | timeline | chat
    # JSON blob of the assistant turn's surfacing data (§7.5/§8):
    # {trace, citations, certainty, pending}. Lets the UI re-render the agent's
    # work, citation chips, and certainty after a thread reload — not just live.
    meta: Optional[str] = None


class ChatThread(SQLModel, table=True):
    __tablename__ = "chat_threads"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    patient_id: str = Field(index=True)
    title: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def init():
    """Create chat tables if missing, then additively patch new columns."""
    SQLModel.metadata.create_all(_engine)
    _migrate()


def _migrate():
    """SQLModel.create_all never ALTERs an existing table; add new nullable columns
    on the live `chat_messages` table here (mirrors ledger._migrate)."""
    with _engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(chat_messages)")}
        if "meta" not in existing:
            conn.exec_driver_sql("ALTER TABLE chat_messages ADD COLUMN meta TEXT")
        conn.commit()


def create_thread(patient_id: str, title: str = "") -> ChatThread:
    """Start a new conversation thread for a patient."""
    thread = ChatThread(patient_id=patient_id, title=title or "New conversation")
    with Session(_engine) as s:
        s.add(thread)
        s.commit()
        s.refresh(thread)
    return thread


def list_threads(patient_id: str) -> List[ChatThread]:
    """All threads for a patient, newest first."""
    with Session(_engine) as s:
        rows = s.exec(
            select(ChatThread)
            .where(ChatThread.patient_id == patient_id)
            .order_by(ChatThread.updated_at.desc())  # type: ignore[attr-defined]
        ).all()
        return list(rows)


def get_thread(thread_id: str) -> Optional[ChatThread]:
    with Session(_engine) as s:
        return s.get(ChatThread, thread_id)


def add_message(thread_id: str, patient_id: str, role: str, content: str, intent: str = None, meta: str = None) -> ChatMessage:
    """Add a message to a thread and update thread timestamp."""
    msg = ChatMessage(
        thread_id=thread_id, patient_id=patient_id,
        role=role, content=content, intent=intent, meta=meta,
    )
    with Session(_engine) as s:
        s.add(msg)
        # Update thread's updated_at
        thread = s.get(ChatThread, thread_id)
        if thread:
            thread.updated_at = datetime.utcnow().isoformat()
            # Auto-title from first user message
            if not thread.title or thread.title == "New conversation":
                if role == "user":
                    thread.title = content[:80]
            s.add(thread)
        s.commit()
        s.refresh(msg)
    return msg


def get_messages(thread_id: str, limit: int = 50) -> List[ChatMessage]:
    """Messages in a thread, oldest first (for context replay)."""
    with Session(_engine) as s:
        rows = s.exec(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.timestamp)
            .limit(limit)
        ).all()
        return list(rows)


def delete_thread(thread_id: str) -> bool:
    """Delete a thread and all its messages."""
    from sqlalchemy import delete as sa_delete
    with Session(_engine) as s:
        s.exec(sa_delete(ChatMessage).where(ChatMessage.thread_id == thread_id))
        s.exec(sa_delete(ChatThread).where(ChatThread.id == thread_id))
        s.commit()
    return True


# --- Cognee integration: store chat turns as semantic memory ---------------

def chat_dataset_for(patient_id: str) -> str:
    """Dataset name for a patient's chat memory."""
    return f"chat_{patient_id.strip().lower()}"


async def store_in_cognee(patient_id: str, role: str, content: str) -> None:
    """
    Store a chat turn in Cognee for semantic recall. The agent can later
    recall past conversations when answering follow-ups.
    """
    text = f"[{role}] {content}"
    try:
        await cognee.add(text, dataset_name=chat_dataset_for(patient_id))
    except Exception:
        pass  # ponytail: best-effort, chat works without Cognee recall


async def cognify_chat(patient_id: str) -> None:
    """Build the semantic graph over chat history (enables contextual recall)."""
    try:
        await cognee.cognify(datasets=[chat_dataset_for(patient_id)])
    except Exception:
        pass  # best-effort
