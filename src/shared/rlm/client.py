"""RLM client factory and wrapper.

Integrates RLM (Recursive Language Models) with LiteLLM proxy for automatic
provider rotation. Handles tracing via Phoenix OTEL.
"""

import os
from typing import Any

from rlm import RLM
from rlm.logger import RLMLogger

from src.shared.rlm.config import RLMSettings
from src.shared.tracing import get_tracer

tracer = get_tracer(__name__)

# Module-level cache for default RLM instance
_rlm_instance = None


def get_rlm(settings: RLMSettings | None = None) -> RLM:
    """Return an RLM instance configured with LiteLLM proxy backend.

    Args:
        settings: RLMSettings instance. If None, uses cached default instance.

    Returns:
        An RLM instance ready for completion requests.
    """
    global _rlm_instance

    # Use cached instance if no custom settings provided
    if settings is None:
        if _rlm_instance is None:
            settings = RLMSettings()
            _rlm_instance = _create_rlm(settings)
        return _rlm_instance

    # Create new instance for custom settings
    return _create_rlm(settings)


def _create_rlm(settings: RLMSettings) -> RLM:
    """Create a new RLM instance from settings.

    Args:
        settings: RLMSettings dataclass.

    Returns:
        Configured RLM instance.
    """
    # Ensure log directory exists
    os.makedirs(settings.log_dir, exist_ok=True)

    # Create logger for execution trajectory capture
    logger = RLMLogger(log_dir=settings.log_dir) if settings.log_dir else None

    # Build RLM with LiteLLM proxy backend
    kwargs = settings.to_rlm_kwargs()
    kwargs["logger"] = logger

    return RLM(**kwargs)


@tracer.start_as_current_span("rlm.completion")
def rlm_completion(
    prompt: str,
    context: str | None = None,
    settings: RLMSettings | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute an RLM completion with optional context.

    This is a traced wrapper around RLM.completion() that enables Phoenix
    observability and handles context embedding.

    Args:
        prompt: The main task prompt.
        context: Optional long context (50k+ lines supported via compaction).
        settings: RLMSettings. Defaults to env-based settings if None.
        **kwargs: Additional kwargs passed to rlm.completion().

    Returns:
        dict with keys:
            - response: Final model response text
            - execution_time: Total execution time in seconds
            - metadata: Full trajectory with iterations and recursive calls
            - status: "success" or "error"
            - error: Error message if status is "error"
    """
    if settings is None:
        settings = RLMSettings()

    rlm = get_rlm(settings)

    # Embed context in prompt if provided
    full_prompt = prompt
    if context:
        full_prompt = f"{prompt}\n\n# CONTEXT:\n{context}"

    try:
        result = rlm.completion(full_prompt, **kwargs)

        return {
            "response": result.response,
            "execution_time": result.execution_time,
            "metadata": result.metadata,
            "status": "success",
            "error": None,
        }
    except Exception as e:
        return {
            "response": None,
            "execution_time": None,
            "metadata": None,
            "status": "error",
            "error": str(e),
        }


def get_rlm_metadata(result: dict) -> dict:
    """Extract execution trajectory from RLM completion result.

    Args:
        result: Dict returned from rlm_completion().

    Returns:
        Metadata with trajectory info:
            - iterations: List of iteration steps
            - recursive_calls: List of nested RLM calls if max_depth > 1
            - total_iterations: Total steps taken
    """
    metadata = result.get("metadata", {})
    return {
        "iterations": metadata.get("iterations", []),
        "recursive_calls": metadata.get("rlm_calls", []),
        "total_iterations": len(metadata.get("iterations", [])),
    }
