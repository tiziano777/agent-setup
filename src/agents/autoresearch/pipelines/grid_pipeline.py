"""Grid pipeline — Cartesian product sweep with parallel wave execution."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.autoresearch.nodes.execute_wave import execute_wave
from src.agents.autoresearch.nodes.generate_grid import generate_grid
from src.agents.autoresearch.nodes.initialize_session import initialize_session
from src.agents.autoresearch.nodes.persist_knowledge import persist_knowledge
from src.agents.autoresearch.nodes.slice_next_wave import slice_next_wave
from src.agents.autoresearch.nodes.store_results import store_results
from src.agents.autoresearch.nodes.update_escalation import update_escalation
from src.agents.autoresearch.nodes.wave_analyst import wave_analyst
from src.agents.autoresearch.states.state import AutoresearchState


def _should_continue(state: AutoresearchState) -> str:
    """Route: more grid configs remaining, or finish."""
    remaining = state.get("experiments_remaining", 0)
    grid_configs = state.get("grid_configs", [])
    offset = state.get("grid_offset", 0)
    should = state.get("should_continue", True)

    if remaining <= 0 or offset >= len(grid_configs) or not should:
        return "persist_knowledge"
    return "slice_next_wave"


def build_grid_pipeline() -> StateGraph:
    """Build the grid search pipeline.

    Flow::

        START → initialize → generate_grid → slice → execute → store
              → analyst → escalation → [loop or end]
    """
    builder = StateGraph(AutoresearchState)

    builder.add_node("initialize_session", initialize_session)
    builder.add_node("generate_grid", generate_grid)
    builder.add_node("slice_next_wave", slice_next_wave)
    builder.add_node("execute_wave", execute_wave)
    builder.add_node("store_results", store_results)
    builder.add_node("wave_analyst", wave_analyst)
    builder.add_node("update_escalation", update_escalation)
    builder.add_node("persist_knowledge", persist_knowledge)

    builder.add_edge(START, "initialize_session")
    builder.add_edge("initialize_session", "generate_grid")
    builder.add_edge("generate_grid", "slice_next_wave")
    builder.add_edge("slice_next_wave", "execute_wave")
    builder.add_edge("execute_wave", "store_results")
    builder.add_edge("store_results", "wave_analyst")
    builder.add_edge("wave_analyst", "update_escalation")
    builder.add_conditional_edges("update_escalation", _should_continue, {
        "persist_knowledge": "persist_knowledge",
        "slice_next_wave": "slice_next_wave",
    })
    builder.add_edge("persist_knowledge", END)

    return builder.compile()
