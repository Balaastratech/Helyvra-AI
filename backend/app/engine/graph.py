"""
LangGraph wiring + SqliteSaver checkpointer.

    START -> recall_related --(empty?)--> store_new
                           \\--> judge --> reconcile_supersede ---+--> persist -> END
                                      --> reconcile_contradict --/
                                      --> reinforce
                                      --> store_new

Checkpoints live in C:\\cg\\engine_checkpoints.sqlite (thread_id = patient_id),
so a re-run resumes / is inspectable.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.engine import nodes
from app.engine.state import TRState

_CHECKPOINT_DB = os.environ.get("ENGINE_CHECKPOINTS", r"C:\cg\engine_checkpoints.sqlite")


def build_graph(checkpointer=None):
    """Compile the self-healing engine. Pass a checkpointer or None."""
    g = StateGraph(TRState)

    g.add_node("recall_related", nodes.recall_related)
    g.add_node("judge", nodes.judge_node)
    g.add_node("reconcile_supersede", nodes.reconcile_supersede)
    g.add_node("reconcile_contradict", nodes.reconcile_contradict)
    g.add_node("store_new", nodes.store_new)
    g.add_node("reinforce", nodes.reinforce)
    g.add_node("persist", nodes.persist)

    g.add_edge(START, "recall_related")
    g.add_conditional_edges(
        "recall_related",
        nodes.route_after_recall,
        {"judge": "judge", "store_new": "store_new"},
    )
    g.add_conditional_edges(
        "judge",
        nodes.route_after_judge,
        {
            "reconcile_supersede": "reconcile_supersede",
            "reconcile_contradict": "reconcile_contradict",
            "store_new": "store_new",
            "reinforce": "reinforce",
        },
    )
    for n in ("reconcile_supersede", "reconcile_contradict", "store_new", "reinforce"):
        g.add_edge(n, "persist")
    g.add_edge("persist", END)

    return g.compile(checkpointer=checkpointer)


@asynccontextmanager
async def checkpointer():
    """AsyncSqliteSaver bound to the engine checkpoint DB (short Windows path)."""
    os.makedirs(os.path.dirname(_CHECKPOINT_DB), exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(_CHECKPOINT_DB) as saver:
        yield saver
