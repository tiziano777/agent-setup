"""RLM Agent I/O schemas."""

from pydantic import BaseModel, Field


class RLMAgentInput(BaseModel):
    """Input for RLM Agent."""

    prompt: str = Field(
        ..., description="Task prompt (e.g., 'Find the SECRET_NUMBER in this text')"
    )
    context: str = Field(
        ..., description="Long context text to search through (50k+ lines supported)"
    )
    max_iterations: int = Field(
        default=10, description="Max RLM iterations per invocation"
    )


class RLMAgentOutput(BaseModel):
    """Output from RLM Agent."""

    response: str = Field(description="Final answer from RLM")
    execution_time: float | None = Field(description="Total execution time (seconds)")
    total_iterations: int = Field(
        description="Number of RLM iterations executed", default=0
    )
    recursive_calls: int = Field(
        description="Number of recursive RLM calls (if max_depth > 1)", default=0
    )
    status: str = Field(description="'success' or 'error'")
    error: str | None = Field(default=None, description="Error message if failed")
    full_metadata: dict = Field(
        description="Complete RLM execution trajectory and metadata"
    )
