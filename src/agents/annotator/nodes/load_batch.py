"""Load next batch of K entries from JSONL input."""

import json
import logging
from pathlib import Path
from typing import Any

from src.agents.annotator.config import settings
from src.agents.annotator.states import AnnotatorState

logger = logging.getLogger(__name__)


def _load_processed_hashes() -> set[str]:
    """Read output file and return set of already-processed _id_hash values."""
    output_path = Path(settings.output_path)
    if not output_path.exists():
        return set()
    hashes = set()
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    obj = json.loads(line)
                    if "_id_hash" in obj:
                        hashes.add(obj["_id_hash"])
                except json.JSONDecodeError:
                    continue
    return hashes


def load_batch(state: AnnotatorState) -> dict[str, Any]:
    """Read next batch_size entries from all_entries.

    On first call, loads the entire JSONL file into state,
    skipping entries whose _id_hash already exists in the output file.
    On subsequent calls, advances the cursor by batch_size.
    """
    k = settings.batch_size

    if not state.get("all_entries"):
        path = Path(settings.input_path)
        with path.open(encoding="utf-8") as f:
            raw_entries = [json.loads(line) for line in f if line.strip()]

        processed = _load_processed_hashes()
        if processed:
            all_entries = [
                e for e in raw_entries
                if e.get("metadata", {}).get("_id_hash") not in processed
            ]
            logger.info(
                "Loaded %d entries from %s (skipped %d already processed)",
                len(all_entries), path.name, len(raw_entries) - len(all_entries),
            )
        else:
            all_entries = raw_entries
            logger.info("Loaded %d entries from %s", len(all_entries), path.name)

        if not all_entries:
            return {
                "all_entries": [],
                "total_entries": 0,
                "batch_index": 0,
                "current_batch": [],
                "status": "done",
                "processed_count": 0,
                "results": [],
            }

        return {
            "all_entries": all_entries,
            "total_entries": len(all_entries),
            "batch_index": k,
            "current_batch": all_entries[:k],
            "status": "judging",
            "processed_count": 0,
            "results": [],
        }

    idx = state["batch_index"]
    batch = state["all_entries"][idx: idx + k]
    logger.info("Batch at index %d, size %d", idx, len(batch))
    return {
        "current_batch": batch,
        "batch_index": idx + k,
        "status": "judging",
    }
