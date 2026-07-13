"""Checkpoint node tracker — wraps the existing LineageCheckpointCallback."""

from __future__ import annotations

import logging
from typing import Any

from ..http.client import ExecutionContext
from ..utils.callbacks.lineage_checkpoint_callback import LineageCheckpointCallback
from .base import EmitFn, NodeTracker

logger = logging.getLogger(__name__)


class CheckpointTracker(NodeTracker):
    """NodeTracker that produces a LineageCheckpointCallback for the run.

    Reuses the existing callback logic without rewriting it.
    """

    node_type: str = "Checkpoint"

    def __init__(self, blocking: bool = False) -> None:
        self._blocking = blocking

    def build_callback(self, ctx: ExecutionContext, emit: EmitFn) -> Any:
        """Build and return a LineageCheckpointCallback bound to the run context."""
        logger.debug("Building CheckpointTracker callback for run %s", ctx.run_id)
        return LineageCheckpointCallback(ctx=ctx, blocking=self._blocking)