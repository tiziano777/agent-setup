"""Input/output schemas for deepconf_agent."""

from pydantic import BaseModel, Field


class DeepConfAgentInput(BaseModel):
    """Input to the deepconf agent."""

    question: str = Field(description="Question requiring deep reasoning")


class DeepConfAgentOutput(BaseModel):
    """Output from the deepconf agent."""

    final_answer: str = Field(description="Final reasoning answer")
    voting_results: dict = Field(
        default_factory=dict,
        description="Results from multiple reasoning strategies",
    )
    reasoning_steps: list[str] = Field(
        default_factory=list, description="Intermediate reasoning steps"
    )
    backend: str = Field(
        description="Backend used: 'deepthink' or 'fallback'"
    )
