# recipe_config.py

from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class RecipeEntry(BaseModel):
    """Metadata for a single distribution/dataset entry in a recipe."""

    chat_type: Optional[str] = Field(None, min_length=1, description="Chat conversation type")
    dist_id: Optional[str] = Field(None, min_length=1, description="Distribution unique identifier")
    dist_name: str = Field(..., min_length=1, description="Human-readable distribution name")
    dist_uri: str = Field(..., min_length=1, description="Path or URI to distribution")
    replica: Optional[int] = Field(None, ge=1, description="Replication factor (N× oversampling)")
    samples: Optional[int] = Field(None, ge=0, description="Total number of samples in distribution")
    system_prompt: Optional[Dict[str, str]] = Field(None, description="System prompt name→content templates (unified dict format)")
    tokens: Optional[int] = Field(None, ge=0, description="Total token count")
    words: Optional[int] = Field(None, ge=0, description="Total word count")
    validation_error: Optional[str] = Field(None, description="Validation error if any")

class RecipeConfig(BaseModel):
    """Full recipe configuration — preserves all metadata fields from the YAML.

    Only 'entries' is required; all other metadata fields are optional and non-blocking.
    The recipe will process successfully even if metadata is missing.
    """

    entries: List[RecipeEntry] = Field(
        ...,
        description="List of distribution metadata objects (REQUIRED)"
    )
    id: Optional[str] = Field(None, description="Recipe UUID")
    name: Optional[str] = Field(None, description="Recipe short name")
    description: Optional[str] = Field(None, description="Human-readable description")
    scope: Optional[str] = Field(None, description="Training scope (e.g. continual_ft, sft)")
    tasks: Optional[List[str]] = Field(None, description="Task categories covered")
    tags: Optional[List[str]] = Field(None, description="Free-form classification tags")
    derived_from: Optional[str] = Field(None, description="Parent recipe UUID this was derived from")
