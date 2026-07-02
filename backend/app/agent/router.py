"""
Real tool-calling agent (ReAct loop) — replaces the v1 intent classifier.

Per turn the model decides, via Vertex Gemini function-calling, whether to recall,
ingest, propose a correction, or explain — and may chain several tool calls before
answering in plain language. The four tools are bound to ONE patient via closures
(see agent/tools.py), so the agent is structurally incapable of touching another
patient's data.

Forced grounding (audit §2.5): the system prompt FORBIDS answering any clinical
question from the model's own knowledge — every clinical claim must come from a
`recall_patient_facts` call this turn. Destructive correction is staged
(`propose_forget` -> POST /chat/approve), never executed mid-turn.

Built directly on google-genai's native function-calling loop (the LLM SDK this
codebase already uses) instead of pulling in langchain/LangGraph's ToolNode — no
new dependency, same hand-rolled-loop spirit as engine/graph.py. Each tool call's
{seq, tool, args, result_summary, ms} is recorded into a per-turn trace (§7.5),
which is both the observability record and the data the live UI trace renders (§8).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from time import perf_counter
from typing import List, Optional

import app.config as config
from google import genai
from google.genai import types

from app.agent import history, tools as agent_tools
from app import audit

# Background tasks for best-effort Cognee chat-memory writes. Kept off the
# request's critical path (they were adding 5-20s/turn and nothing reads them
# back yet). Hold references so the event loop doesn't GC them mid-flight.
# ponytail: fire-and-forget on the single demo loop — a background cognify can
# contend with an engine cognify on Cognee's SQLite stores; both are best-effort
# and swallow errors. Upgrade to a real task queue if chat-memory recall ships.
_bg_tasks: set = set()


def _fire(coro) -> None:
    """Schedule a best-effort coroutine without blocking the response."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

# Cap tool-call rounds per turn so a misbehaving model can't loop forever
# (the standard defensive bound for any ReAct loop). ponytail: fixed cap, fine
# for a demo; raise if real multi-step workflows need more hops.
_MAX_ROUNDS = 6

# Worst-to-best ordering so a turn's overall certainty is the least-certain of
# its recall calls (one contested recall makes the whole answer contested).
_CERTAINTY_RANK = {"contested": 2, "low_confidence": 1, "settled": 0}

_SYSTEM = (
    "You are Total Recall, a clinical memory assistant for ONE patient. You can ONLY "
    "see and act on the current patient's records.\n\n"
    "Use the provided tools to do real work, not just talk:\n"
    "- recall_patient_facts: answer any clinical question (current truth + what changed).\n"
    "- run_clinical_checks: surface the patient's not-to-miss safety findings.\n"
    "- propose_order: run prescribe-time safety checks for a drug BEFORE any write — "
    "use this whenever the user asks whether they can prescribe/start a medication.\n"
    "- get_timeline: the patient's events in chronological order.\n"
    "- ingest_fact: record new clinical information the user states.\n"
    "- propose_forget: propose correcting a fact entered in error (NOT a fact that "
    "merely changed). This stages a one-click confirmation for the clinician — it does "
    "not delete anything itself.\n"
    "- why_changed: explain the history/provenance of a subject.\n\n"
    "HARD RULE — FORCED GROUNDING: You must NEVER answer a clinical question (about "
    "allergies, medications, diagnoses, labs, vitals, or procedures) from your own "
    "knowledge. EVERY such answer must come from a recall_patient_facts call made THIS "
    "turn. For a prescribe/medication-safety question you must call propose_order. If you "
    "have not called the relevant tool, you do not know the answer — call it. Do not "
    "guess, do not use general medical knowledge as the answer.\n\n"
    "When you answer a clinical question, reply with the answer and its key reason in "
    "one or two plain sentences. Do NOT restate the confidence, what's missing, or the "
    "suggested action in your reply — the app already shows those to the clinician from "
    "the tool result. Plain text only: no markdown, no asterisks, no headings. Never "
    "state a diagnosis or treatment beyond the cited evidence.\n\n"
    "You are a capable assistant that sometimes needs correction, not a confident expert. "
    "If the recalled memory is contested or uncertain, say so plainly rather than picking "
    "a confident winner. Frame a correction as fixing the record together with the "
    "clinician, not a destructive admin action.\n\n"
    "You may call more than one tool in a turn (e.g. recall then propose a correction). "
    "When you have enough information, reply in clear, concise clinical language. For "
    "greetings or non-clinical chit-chat, just reply directly without calling a tool."
)


def _history_to_contents(messages: List[history.ChatMessage]) -> List[types.Content]:
    """Replay prior turns as Gemini contents (assistant -> 'model')."""
    out: List[types.Content] = []
    for m in messages:
        role = "model" if m.role == "assistant" else "user"
        out.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
    return out


def _text_of(parts) -> str:
    return "".join(p.text for p in (parts or []) if getattr(p, "text", None))


async def handle_message(patient_id: str, thread_id: str, message: str, doctor: str = "unknown") -> dict:
    """Run one agent turn.

    Returns {reply, actions, fact_id, intent, trace, citations, certainty, pending, cards, answer}.
    Every tool call is written to the real audit trail against `doctor` (§7).
    """
    prior = history.get_messages(thread_id, limit=20)

    # Persist the user turn verbatim (fast SQLite). The Cognee semantic copy is
    # best-effort and unused on the read path — fire it in the background.
    history.add_message(thread_id, patient_id, "user", message)
    _fire(history.store_in_cognee(patient_id, "user", message))

    tools_map, decls, log = agent_tools.build_patient_tools(patient_id)
    cfg = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        tools=[types.Tool(function_declarations=decls)],
        temperature=0,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = _history_to_contents(prior)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.LOCATION)
    trace: List[dict] = []  # ordered per-turn trace: {seq, tool, args, result_summary, ms, ...}
    reply = ""
    for _ in range(_MAX_ROUNDS):
        try:
            resp = client.models.generate_content(
                model=config.EXTRACTION_MODEL, contents=contents, config=cfg
            )
        except Exception as exc:  # model/transport failure — degrade gracefully (§2.6.F)
            reply = f"Sorry, I hit an error reaching the model: {type(exc).__name__}."
            break

        cand = resp.candidates[0] if resp.candidates else None
        parts = cand.content.parts if (cand and cand.content) else []
        calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

        if not calls:
            reply = _text_of(parts).strip()
            break

        contents.append(cand.content)  # the model's tool-call turn
        resp_parts = []
        for fc in calls:
            fn = tools_map.get(fc.name)
            args = dict(fc.args or {})
            before = len(log)
            t0 = perf_counter()
            try:
                if fn is None:
                    out = f"Unknown tool: {fc.name}"
                else:
                    res = fn(**args)
                    out = await res if inspect.isawaitable(res) else res
            except Exception as exc:  # surface as ToolMessage so the model can recover
                out = f"Error running {fc.name}: {type(exc).__name__}: {exc}"
            ms = round((perf_counter() - t0) * 1000)
            # Promote whatever the tool logged into the persisted trace, enriching
            # each entry with the call's args/timing/result summary (§7.5).
            new_entries = log[before:] or [{"chip": fc.name, "tool": fc.name}]
            for entry in new_entries:
                entry["seq"] = len(trace)
                entry["args"] = args
                entry["ms"] = ms
                entry["result_summary"] = str(out)[:240]
                trace.append(entry)
                # Real audit trail (§7): one row per tool action, with the evidence
                # (fact ids + citation/card fact ids) that backed it.
                evidence = []
                if entry.get("fact_id"):
                    evidence.append(entry["fact_id"])
                evidence += [c.get("fact_id") for c in entry.get("citations", []) if c.get("fact_id")]
                for card in entry.get("cards", []):
                    evidence += [s.get("fact_id") for s in card.get("source", []) if s.get("fact_id")]
                audit.log(
                    doctor=doctor,
                    action=fc.name,
                    patient_id=patient_id,
                    decision=entry.get("chip", "")[:200],
                    evidence_ids=[e for e in evidence if e],
                )
            resp_parts.append(
                types.Part.from_function_response(name=fc.name, response={"result": out})
            )
        contents.append(types.Content(role="user", parts=resp_parts))

    if not reply:
        reply = "I wasn't able to finish that request — please try rephrasing."

    # Derive UI signals from the trace.
    actions = [a["chip"] for a in trace if a.get("chip")]
    fact_id: Optional[str] = next(
        (a["fact_id"] for a in reversed(trace) if a.get("fact_id")), None
    )
    citations = [c for a in trace for c in a.get("citations", [])]
    certainty = "settled"
    for a in trace:
        c = a.get("certainty")
        if c and _CERTAINTY_RANK.get(c, 0) > _CERTAINTY_RANK.get(certainty, 0):
            certainty = c
    pending_action = next((a["pending"] for a in trace if a.get("pending")), None)
    # Clinical cards from checks / prescribe screens (most-recent tool first is fine —
    # the UI renders them in trace order). Structured answer = the last recall's
    # six-part contract (§5.3) for the AnswerCard.
    cards = [c for a in trace for c in a.get("cards", [])]
    answer_contract = next((a["answer"] for a in reversed(trace) if a.get("answer")), None)

    # Persist the assistant turn (verbatim + the surfacing data, so the UI can
    # re-render trace/citations/certainty after a reload — §7.5).
    meta = json.dumps(
        {
            "trace": trace,
            "citations": citations,
            "certainty": certainty,
            "pending": pending_action,
            "cards": cards,
            "answer": answer_contract,
        }
    )
    history.add_message(thread_id, patient_id, "assistant", reply, meta=meta)
    # Background, off the critical path (was adding 1-15s/turn for zero read benefit).
    _fire(history.store_in_cognee(patient_id, "assistant", reply))
    if len(prior) % 5 == 0:
        _fire(history.cognify_chat(patient_id))

    return {
        "reply": reply,
        "actions": actions,
        "fact_id": fact_id,
        "intent": "agent",
        "trace": trace,
        "citations": citations,
        "certainty": certainty,
        "pending": pending_action,
        "cards": cards,
        "answer": answer_contract,
    }
