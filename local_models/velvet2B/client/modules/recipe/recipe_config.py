# recipe_config.py

from __future__ import annotations
from pydantic import BaseModel, Field

class RecipeEntry(BaseModel):
    """Metadata for a single distribution/dataset entry in a recipe."""

    chat_type: str = Field(..., min_length=1, description="Chat conversation type")
    dist_id: str = Field(..., min_length=1, description="Distribution unique identifier")
    dist_name: str = Field(..., min_length=1, description="Human-readable distribution name")
    dist_uri: str = Field(..., min_length=1, description="Path or URI to distribution")
    replica: int = Field(1, ge=1, description="Replication factor (N× oversampling)")
    samples: int = Field(..., gt=0, description="Total number of samples in distribution")
    system_prompt: list[str] | None = Field(None, description="System prompt templates")
    system_prompt_name: list[str] | None = Field(None, description="System prompt names")
    tokens: int = Field(..., gt=0, description="Total token count")
    words: int = Field(..., gt=0, description="Total word count")
    validation_error: str | None = Field(None, description="Validation error if any")


class RecipeConfig(BaseModel):
    """Full recipe configuration — preserves all metadata fields from the YAML.

    Only 'entries' is required; all other metadata fields are optional and non-blocking.
    The recipe will process successfully even if metadata is missing.
    """

    entries: dict[str, RecipeEntry] = Field(
        ...,
        description="Mapping of dataset paths to distribution metadata (REQUIRED)"
    )
    recipe_id: str | None = Field(None, description="Recipe UUID")
    recipe_name: str | None = Field(None, description="Recipe short name")
    description: str | None = Field(None, description="Human-readable description")
    scope: str | None = Field(None, description="Training scope (e.g. continual_ft, sft)")
    tasks: list[str] = Field(default_factory=list, description="Task categories covered")
    tags: list[str] = Field(default_factory=list, description="Free-form classification tags")
    derived_from: str | None = Field(None, description="Parent recipe UUID this was derived from")