"""Pydantic schemas for text2sql agent I/O."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Text2SQLInput(BaseModel):
    """Input to text2sql agent."""

    prompt: str = Field(
        ...,
        description="Natural language question (e.g., 'Find customers who spent more than $1000')",
    )

    include_catalog: bool = Field(
        default=False,
        description="If True, return full database catalog in output",
    )


class QueryIteration(BaseModel):
    """Single query attempt in feedback loop."""

    iteration: int
    query: str
    error: str | None
    error_type: str | None
    rows_affected: int | None
    success: bool


class Text2SQLOutput(BaseModel):
    """Output from text2sql agent."""

    prompt: str
    final_query: str | None
    final_result: dict | None
    success: bool
    status: str
    error: str | None
    iterations: list[QueryIteration]
    message_count: int

    class Config:
        arbitrary_types_allowed = True
