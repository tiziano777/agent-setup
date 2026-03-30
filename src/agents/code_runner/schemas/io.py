"""Input/output Pydantic schemas for code_runner.

Used for validating external API requests, defining
explicit graph input/output schemas, or structured output parsing.
"""

from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    """Schema for input to this agent."""

    query: str = Field(..., description="The user query or task instruction")
    thread_id: str | None = Field(None, description="Thread ID for persistence")


class AgentOutput(BaseModel):
    """Schema for output from this agent."""

    response: str = Field(..., description="The agent's response")
    metadata: dict = Field(default_factory=dict)
