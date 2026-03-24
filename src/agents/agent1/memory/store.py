"""Memory configuration for agent1.

Defines the namespace structure for long-term memory
and any agent-specific memory utilities.
Short-term memory is handled by the checkpointer passed
to the graph or entrypoint at compile time.
"""


def get_memory_namespace(user_id: str) -> tuple:
    """Return the memory store namespace for this agent and user.

    This follows LangGraph's (user_id, context) namespace convention
    for the BaseStore / InMemoryStore.
    """
    return (user_id, "agent1")
