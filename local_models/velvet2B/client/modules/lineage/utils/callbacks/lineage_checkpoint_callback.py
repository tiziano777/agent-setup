"""LineageCheckpointCallback: TrainerCallback that sends checkpoint events to the lineage server."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import json
try:
    from transformers import TrainerCallback, TrainerState
except ImportError:
    TrainerCallback = object  # type: ignore[assignment, misc]
    TrainerState = Any  # type: ignore[assignment, misc]

from ...http.client import ExecutionContext
from ...http.base.connector import ConnectorFactory, ServerError
from ...http.data_classes.http_config import CheckpointRequest, CheckpointResponse

logger = logging.getLogger(__name__)


class LineageCheckpointCallback(TrainerCallback):
    """Sends checkpoint creation events to the lineage server on each Trainer save.

    Args:
        ctx: ExecutionContext from the lineage_tracker decorator PRE phase.
        blocking: If True, raises on communication failure. If False, logs warning and continues.
    """

    def __init__(self, ctx: ExecutionContext, blocking: bool = False):
        self._ctx = ctx
        self._blocking = blocking
        self._connector = ConnectorFactory.create(ctx.server_config)
        self._run_counter = 0

    def on_save(self, args, state: TrainerState, control, **kwargs):
        """Capture checkpoint data and send to lineage server."""
        self._run_counter += 1

        checkpoint_dir = state.best_model_checkpoint or args.output_dir
        metrics = state.log_history[-1] if state.log_history else {}

        # state.epoch is float in HuggingFace (e.g. 1.0, 1.5) — cast to int for the schema
        epoch = int(state.epoch) if state.epoch is not None else 0

        request = CheckpointRequest(
            experiment_id=self._ctx.experiment_id,
            name=Path(checkpoint_dir).name,
            epoch=epoch,
            run=self._run_counter,
            uri=str(checkpoint_dir),
            metrics=json.dumps(metrics),
            derived_from=self._ctx.extra.get("model_id", ""),
            is_merging=False,
        )

        try:
            response: CheckpointResponse = self._connector.send_checkpoint(request)
            logger.info(
                "Checkpoint tracked: %s (id=%s, epoch=%d, run=%d)",
                request.name, response.checkpoint_id, request.epoch, request.run,
            )
        except (ConnectionError, ServerError) as e:
            if self._blocking:
                raise
            logger.warning("Checkpoint tracking failed (non-blocking): %s", e)
        except Exception as e:
            if self._blocking:
                raise
            logger.warning("Unexpected error in checkpoint tracking: %s", e)

    def on_train_end(self, args, state: TrainerState, control, **kwargs):
        """Release connector resources when training ends."""
        try:
            self._connector.close()
        except Exception as e:
            logger.warning("Error closing checkpoint connector: %s", e)