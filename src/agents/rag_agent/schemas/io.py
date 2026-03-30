"""Input/output Pydantic schemas for rag_agent.

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
    sources: list[str] = Field(default_factory=list, description="IDs of retrieved source documents")
    metadata: dict = Field(default_factory=dict)
