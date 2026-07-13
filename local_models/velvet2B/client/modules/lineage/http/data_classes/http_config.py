"""Pydantic models for Client-Server communication payloads."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ExperimentType(str, Enum):
    TRAINING = "training"
    EVALUATION = "evaluation"
    INFERENCE = "inference"
    MERGING = "merging"


# ─── PRE-EXECUTION ─────────────────────────────────────────────────────────────

class PreRequest(BaseModel):
    """Payload sent to server before training execution starts.

    Contains the full experiment config and captured codebase content
    for the server to run rules detection and create the experiment/run node.
    """
    # Experiment identity
    experiment_id: Optional[str] = None  # current_exp_id, assigned as root first exp_id by server if not provided
    experiment_name: str
    experiment_uri: Optional[str] = None
    base: Optional[bool] 
    base_experiment_id: Optional[str] = None
    previous_experiment_id: Optional[str] = None
    description: Optional[str] = None
    experiment_type: ExperimentType

    merging: bool = False
    codebase: str # JSON string of {relative_path: content}

    # BASE NODE RELATIONSHIPS
    model_id: Optional[str] = None
    model_uri: Optional[str] = None
    component_id: Optional[str] = None
    recipe_id: Optional[str] = None

    checkpoint_resume_from: Optional[str] = None  # checkpoint_id to resume from, if any


class PreResponse(BaseModel):
    """Server response after PRE-execution processing.

    Contains the assigned experiment_id, detected strategy, and metadata
    the client needs to update local state.
    """

    experiment_id: str
    strategy: str  # NEW, RETRY, BRANCH, RESUME, MERGE
    base: bool
    description: str
    base_experiment_id: Optional[str] = None
    previous_experiment_id: Optional[str] = None

# ─── POST-EXECUTION ───────────────────────────────────────────────────────────

class PostRequest(BaseModel):
    """Payload sent to server after training execution ends.

    Reports final status and optional metrics URI.
    """

    experiment_id: str
    status: str  # COMPLETED or FAILED
    exit_message: Optional[str] = None
    metrics_uri: Optional[str] = None
    strategy: Optional[str] = None  # NEW, RETRY, BRANCH, RESUME, MERGE or None
    checkpoint_resume_from: Optional[str] = None  # checkpoint_uri to resume from, if any

class PostResponse(BaseModel):
    """Server acknowledgement of POST-execution update."""

    experiment_id: str
    status: str
    acknowledged: bool = True

# ─── HEALTH ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Server health check response."""

    status: str = "ok"
    version: str = ""
    neo4j_connected: bool = False

# ─── CHECKPOINT ────────────────────────────────────────────────────────────────

class CheckpointRequest(BaseModel):
    """Payload received from client when a checkpoint is saved."""

    experiment_id: str
    name: str
    epoch: int
    run: int
    uri: str
    metrics: str = Field(default_factory=str)  
    derived_from: str = ""
    is_merging: bool = False

class CheckpointResponse(BaseModel):
    """Server acknowledgement of checkpoint creation."""

    checkpoint_id: str
    experiment_id: str
    acknowledged: bool = True

