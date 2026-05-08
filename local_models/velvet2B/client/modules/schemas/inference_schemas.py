from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InferenceMode(str, Enum):
    positive = "positive"
    negative = "negative"
    candidate = "candidate"


class InferenceParams(BaseModel):
    model_id: str
    temperature: float
    top_p: float | None = None
    top_k: float | None = None
    system_prompt_id: str | None = None


class ResponseItem(BaseModel):
    content: str = Field(..., min_length=1)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    think: str | None = None
    context: str | None = None
    inference_params: InferenceParams | None = None


def make_base_record(
    id_hash: str,
    dist_name: str,
    mode: InferenceMode,
    item: ResponseItem,
    dist_id: str | None = None,
    dist_uri: str | None = None,
) -> dict:
    """Serialize a single inferred sample into the BASE schema dict."""
    record = {
        "_id_hash": id_hash,
        "_distribution_name": dist_name,
        "_distribution_id": dist_id,
        "_distribution_uri": dist_uri,
        mode.value: item.model_dump(),
    }
    return record
