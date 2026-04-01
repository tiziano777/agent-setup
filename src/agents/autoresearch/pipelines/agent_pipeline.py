"""Agent pipeline — full LLM-driven AutoEvolve loop.

The most complex pipeline: a supervisor loop where LLM agents decide
which hyperparameters to try next, when to stop, and when to diagnose
crashes. Implements the AutoEvolve-style scientific method pattern.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.autoresearch.nodes.crash_diagnostician import crash_diagnostician
from src.agents.autoresearch.nodes.execute_wave import execute_wave
from src.agents.autoresearch.nodes.hyperparams_advisor import hyperparams_advisor
from src.agents.autoresearch.nodes.initialize_session import initialize_session
from src.agents.autoresearch.nodes.loop_operator import loop_operator
from src.agents.autoresearch.nodes.persist_knowledge import persist_knowledge
from src.agents.autoresearch.nodes.query_trajectory import query_trajectory
from src.agents.autoresearch.nodes.similarity_search import similarity_search
from src.agents.autoresearch.nodes.store_results import store_results
from src.agents.autoresearch.nodes.update_escalation import update_escalation
from src.agents.autoresearch.nodes.validate_proposals import validate_proposals
from src.agents.autoresearch.nodes.wave_analyst import wave_analyst
from src.agents.autoresearch.states.state import AutoresearchState


def _route_loop_action(state: AutoresearchState) -> str:
    """Route based on the loop operator's decision."""
    action = state.get("loop_action", "next_wave")
    if action == "stop":
        return "persist_knowledge"
    if action == "pause":
        return "persist_knowledge"
    if action == "request_diagnostics":
        return "crash_diagnostician"
    return "hyperparams_advisor"  # next_wave


def _route_after_escalation(state: AutoresearchState) -> str:
    """After escalation update, decide whether to continue the loop."""
    remaining = state.get("experiments_remaining", 0)
    should = state.get("should_continue", True)
    if remaining <= 0 or not should:
        return "persist_knowledge"
    return "query_trajectory"


def build_agent_pipeline() -> StateGraph:
    """Build the full LLM-driven agent pipeline.

    Flow::

        START → initialize → query_trajectory → similarity_search → loop_operator
            ├─ "stop/pause"               → persist_knowledge → END
            ├─ "request_diagnostics"      → crash_diagnostician → loop_operator
            └─ "next_wave" → advisor → validate → execute → store
                           → analyst → escalation → [loop or end]
    """
    builder = StateGraph(AutoresearchState)

    # Add all nodes
    builder.add_node("initialize_session", initialize_session)
    builder.add_node("query_trajectory", query_trajectory)
    builder.add_node("similarity_search", similarity_search)
    builder.add_node("loop_operator", loop_operator)
    builder.add_node("crash_diagnostician", crash_diagnostician)
    builder.add_node("hyperparams_advisor", hyperparams_advisor)
    builder.add_node("validate_proposals", validate_proposals)
    builder.add_node("execute_wave", execute_wave)
    builder.add_node("store_results", store_results)
    builder.add_node("wave_analyst", wave_analyst)
    builder.add_node("update_escalation", update_escalation)
    builder.add_node("persist_knowledge", persist_knowledge)

    # Wire the edges
    builder.add_edge(START, "initialize_session")
    builder.add_edge("initialize_session", "query_trajectory")
    builder.add_edge("query_trajectory", "similarity_search")
    builder.add_edge("similarity_search", "loop_operator")

    # Loop operator routes to different paths
    builder.add_conditional_edges("loop_operator", _route_loop_action, {
        "persist_knowledge": "persist_knowledge",
        "crash_diagnostician": "crash_diagnostician",
        "hyperparams_advisor": "hyperparams_advisor",
    })

    # Crash diagnostician loops back to loop_operator
    builder.add_edge("crash_diagnostician", "loop_operator")

    # Main experiment flow
    builder.add_edge("hyperparams_advisor", "validate_proposals")
    builder.add_edge("validate_proposals", "execute_wave")
    builder.add_edge("execute_wave", "store_results")
    builder.add_edge("store_results", "wave_analyst")
    builder.add_edge("wave_analyst", "update_escalation")

    # After escalation, loop back or finish
    builder.add_conditional_edges("update_escalation", _route_after_escalation, {
        "persist_knowledge": "persist_knowledge",
        "query_trajectory": "query_trajectory",
    })

    # Terminal
    builder.add_edge("persist_knowledge", END)

    return builder.compile()
