"""Input/output Pydantic schemas for rdf_reader."""

from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    """Schema for input to this agent."""

    context: str = Field(..., description="Long text to extract RDF triples from")
    instruction: str = Field(..., description="Question to answer using the extracted knowledge")
    thread_id: str | None = Field(None, description="Thread ID for persistence")


class AgentOutput(BaseModel):
    """Schema for output from this agent."""

    response: str = Field(..., description="The agent's answer based on SPARQL query results")
    triple_count: int = Field(0, description="Number of RDF triples extracted")
    metadata: dict = Field(default_factory=dict)
