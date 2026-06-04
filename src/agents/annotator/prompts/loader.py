"""Prompt loader for annotator agent."""

from pathlib import Path

from src.agents.annotator.config import settings


def load_prompt() -> str:
    """Load system prompt from the configured file path."""
    path = Path(settings.prompt_path)
    return path.read_text(encoding="utf-8").strip()
