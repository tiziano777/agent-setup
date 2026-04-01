"""Functional API pipeline wrapper for autoresearch."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

from src.agents.autoresearch.nodes.execute_wave import execute_wave
from src.agents.autoresearch.nodes.generate_random_wave import generate_random_wave
from src.agents.autoresearch.nodes.initialize_session import initialize_session
from src.agents.autoresearch.nodes.persist_knowledge import persist_knowledge
from src.agents.autoresearch.nodes.store_results import store_results

checkpointer = InMemorySaver()


@task
def init_task(state: dict[str, Any]) -> dict[str, Any]:
    return initialize_session(state)


@task
def generate_task(state: dict[str, Any]) -> dict[str, Any]:
    return generate_random_wave(state)


@task
def execute_task(state: dict[str, Any]) -> dict[str, Any]:
    return execute_wave(state)


@task
def store_task(state: dict[str, Any]) -> dict[str, Any]:
    return store_results(state)


@task
def finish_task(state: dict[str, Any]) -> dict[str, Any]:
    return persist_knowledge(state)


@entrypoint(checkpointer=checkpointer)
def workflow(state: dict[str, Any]) -> dict[str, Any]:
    """Functional API: simplified random pipeline."""
    s = init_task(state).result()
    state.update(s)

    while state.get("experiments_remaining", 0) > 0:
        wave = generate_task(state).result()
        state.update(wave)
        results = execute_task(state).result()
        state.update(results)
        stored = store_task(state).result()
        state.update(stored)

    final = finish_task(state).result()
    state.update(final)
    return state
