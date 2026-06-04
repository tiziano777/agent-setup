"""Settings for annotator agent."""

import os
from dataclasses import dataclass, field
from pathlib import Path

_AGENT_DIR = Path(__file__).parent.parent


@dataclass
class AnnotatorSettings:
    """Annotator agent configuration.

    All paths default to locations relative to the agent directory.
    Override via environment variables for production.
    """

    input_path: str = field(
        default_factory=lambda: os.getenv(
            "ANNOTATOR_INPUT_PATH",
            str(_AGENT_DIR / "input" / "hallucinations_check.jsonl"),
        )
    )
    output_path: str = field(
        default_factory=lambda: os.getenv(
            "ANNOTATOR_OUTPUT_PATH",
            str(_AGENT_DIR / "output" / "verdicts.jsonl"),
        )
    )
    prompt_path: str = field(
        default_factory=lambda: os.getenv(
            "ANNOTATOR_PROMPT_PATH",
            str(_AGENT_DIR / "prompts" / "system.txt"),
        )
    )
    model: str = field(
        default_factory=lambda: os.getenv("ANNOTATOR_MODEL", "llm")
    )
    temperature: float = 0.1
    max_tokens: int = 2048
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("ANNOTATOR_BATCH_SIZE", "2"))
    )


settings = AnnotatorSettings()
