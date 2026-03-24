"""Memory and checkpointer factory utilities.

Provides factory functions for both short-term (checkpointer)
and long-term (store) memory. In development, uses in-memory
implementations. In production, swap for Postgres-backed versions.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore


def get_checkpointer():
    """Return a checkpointer for short-term (thread-scoped) memory.

    In production, replace with:
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver(conn_string=os.getenv("POSTGRES_URI"))
    """
    return InMemorySaver()


def get_store(embed_fn=None, dims: int = 1536):
    """Return a store for long-term (cross-thread) memory.

    Args:
        embed_fn: Optional embedding function for semantic search.
        dims: Embedding dimensionality.

    In production, replace with a DB-backed store.
    """
    if embed_fn is not None:
        return InMemoryStore(index={"embed": embed_fn, "dims": dims})
    return InMemoryStore()
