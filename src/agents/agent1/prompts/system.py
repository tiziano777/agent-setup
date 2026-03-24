"""System prompts for agent1.

Keep prompts as module-level constants or use functions for dynamic prompts.
"""

SYSTEM_PROMPT = (
    "You are agent1, an AI assistant. "
    "Answer the user's questions accurately and concisely."
)


def get_prompt(context: str = "") -> str:
    """Return a dynamic prompt with optional context injection."""
    base = SYSTEM_PROMPT
    if context:
        base += f"\n\nContext:\n{context}"
    return base
