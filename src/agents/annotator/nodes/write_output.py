"""Write verdicts to output JSONL."""

import json
import logging
from pathlib import Path
from typing import Any

from src.agents.annotator.config import settings
from src.agents.annotator.states import AnnotatorState

logger = logging.getLogger(__name__)


def write_output(state: AnnotatorState) -> dict[str, Any]:
    """Append batch verdicts to output JSONL file."""
    output_path = Path(settings.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    batch_size = len(state["current_batch"])
    new_verdicts = state["results"][-batch_size:]

    with output_path.open("a", encoding="utf-8") as f:
        for verdict in new_verdicts:
            f.write(json.dumps(verdict, ensure_ascii=False) + "\n")

    processed = state.get("processed_count", 0) + batch_size
    status = "done" if state["batch_index"] >= state["total_entries"] else "loading"

    logger.info("Written %d verdicts, total processed: %d/%d",
                batch_size, processed, state["total_entries"])

    return {
        "processed_count": processed,
        "status": status,
    }
