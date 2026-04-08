"""deepconf_agent configuration."""

from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    """Configuration for the deepconf_agent."""

    temperature: float = Field(0.7, ge=0, le=2)
    model: str = Field("llm", description="Model for DeepConf reasoning")
    enable_deepthink: bool = Field(
        True, description="Enable DeepThinkLLM if available"
    )
    reasoning_budget: int = Field(
        5, ge=1, le=20, description="Number of reasoning traces"
    )
    reasoning_mode: str = Field(
        "offline", description="offline or online reasoning mode"
    )


settings = AgentSettings()
