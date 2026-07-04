"""
Consult-chat short-circuit (§4) — offline, model + tools mocked.

A first round that is exactly one read-only tool (recall_patient_facts) must
return the tool's own answer WITHOUT a second generate_content call (the round-2
paraphrase that only added latency). A first round of ingest_fact must still run
round 2 (its raw output is a log line, not a reply).
"""

from __future__ import annotations

import asyncio

from app.agent import history
from app.agent import router as agent_router
from app.agent import tools as agent_tools


# --- minimal fakes for the google-genai function-calling surface the router reads
class _FC:
    def __init__(self, name, args=None):
        self.name = name
        self.args = args or {}


class _Part:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call


class _Content:
    def __init__(self, parts):
        self.parts = parts
        self.role = "model"


class _Resp:
    def __init__(self, parts):
        self.candidates = [type("C", (), {"content": _Content(parts)})()]


class _Models:
    def __init__(self, responses, counter):
        self._responses = responses
        self._counter = counter

    def generate_content(self, **_kwargs):
        i = self._counter["n"]
        self._counter["n"] += 1
        return self._responses[min(i, len(self._responses) - 1)]


def _fake_client_factory(responses, counter):
    def _factory(**_kwargs):
        return type("Client", (), {"models": _Models(responses, counter)})()
    return _factory


def _patch_common(monkeypatch, responses, counter):
    monkeypatch.setattr(agent_router.genai, "Client", _fake_client_factory(responses, counter))
    # Keep the background Cognee writes fully offline.
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(history, "store_in_cognee", _noop)
    monkeypatch.setattr(history, "cognify_chat", _noop)


def _recall_tools(_patient_id):
    log = []

    def recall_patient_facts(query):
        log.append({
            "chip": "Recalled memory", "tool": "recall_patient_facts",
            "citations": [], "certainty": "settled",
            "answer": {
                "answer_text": "No penicillin allergy is on file.",
                "reason": "The only allergy record was cleared in 2024.",
                "certainty": "settled", "whats_missing": "",
                "suggested_action": "", "validation": "",
            },
            "fact_id": None,
        })
        return "ANSWER: No penicillin allergy is on file.\nCONFIDENCE: settled"

    return {"recall_patient_facts": recall_patient_facts}, agent_tools.declarations(), log


def _ingest_tools(_patient_id):
    log = []

    def ingest_fact(text):
        log.append({"chip": "Recorded: X", "tool": "ingest_fact", "fact_id": "f1"})
        return "Recorded 'X' (classification: NEW)."

    return {"ingest_fact": ingest_fact}, agent_tools.declarations(), log


def test_single_recall_returns_tool_text_without_round_two(monkeypatch):
    history.init()
    counter = {"n": 0}
    responses = [_Resp([_Part(function_call=_FC("recall_patient_facts", {"query": "penicillin?"}))])]
    _patch_common(monkeypatch, responses, counter)
    monkeypatch.setattr(agent_router.agent_tools, "build_patient_tools", _recall_tools)

    thread = history.create_thread("P001", "t")
    result = asyncio.run(agent_router.handle_message("P001", thread.id, "any penicillin allergy?"))

    # Exactly ONE model call — no round-2 paraphrase.
    assert counter["n"] == 1
    # Reply is the tool's own answer (answer_text + key reason), byte-for-byte.
    assert result["reply"] == (
        "No penicillin allergy is on file. The only allergy record was cleared in 2024."
    )


def test_single_ingest_still_runs_round_two(monkeypatch):
    history.init()
    counter = {"n": 0}
    responses = [
        _Resp([_Part(function_call=_FC("ingest_fact", {"text": "started metformin"}))]),
        _Resp([_Part(text="Recorded that the patient started metformin.")]),
    ]
    _patch_common(monkeypatch, responses, counter)
    monkeypatch.setattr(agent_router.agent_tools, "build_patient_tools", _ingest_tools)

    thread = history.create_thread("P001", "t")
    result = asyncio.run(agent_router.handle_message("P001", thread.id, "record metformin"))

    # ingest_fact is NOT single-shot: round 2 must run to phrase a human reply.
    assert counter["n"] == 2
    assert result["reply"] == "Recorded that the patient started metformin."
