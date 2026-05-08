"""Async inference client for local model serving via OpenAI-compatible endpoint.

Workflow for each RecipeEntry:
  1. Load samples from dist_uri (parquet / jsonl.gz / jsonl).
  2. Expand into tasks: sample × replica × system_prompts × temperatures.
  3. Skip already-done tasks (checkpoint resume).
  4. Run async inference against SGLang /v1/chat/completions.
  5. Write BASE-schema records to rolling JSONL files (OUTPUT_BASE_DIR).
  6. Aggregate JSONL records by _id_hash → FINAL-schema rolling Parquet files
     (AGGREGATED_OUTPUT_DIR — always a separate directory from raw output).
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
from tqdm.asyncio import tqdm

from modules.aggregator.aggregator import DuckDBAggregator
from modules.loader.data_loader import DataLoader
from modules.recipe.recipe_config import RecipeEntry
from modules.recipe.recipe_loader import RecipeLoader
from modules.schemas.inference_schemas import InferenceMode, InferenceParams, ResponseItem, make_base_record
from modules.system_prompt.assigner import PromptAssignmentStrategy, SystemPromptAssigner
from modules.templates.chat_type_registry import ChatTypeRegistry
from modules.writer.writer import RollingJsonlWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required. Install with: pip install pyyaml"
        ) from exc
    with open(path) as f:
        return yaml.safe_load(f) or {}


_CFG_PATH = Path(__file__).parent / "inference_config.yml"
_cfg: dict = _load_yaml(_CFG_PATH) if _CFG_PATH.exists() else {}

API_URL: str = _cfg.get("API_URL", "http://localhost:30000/v1/chat/completions")
RECIPE_PATH: str = _cfg.get("RECIPE_PATH", "recipe.yml")
OUTPUT_BASE_DIR: str = _cfg.get("OUTPUT_BASE_DIR", "output/raw")
AGGREGATED_BASE_DIR: str = _cfg.get("AGGREGATED_OUTPUT_DIR", "output/aggregated")
MAX_FILE_SIZE_MB: int = int(_cfg.get("MAX_FILE_SIZE_MB", 100))
TEMPERATURE_RANGE: list[float] = _cfg.get("TEMPERATURE_RANGE", [0.0, 0.2, 0.3, 0.4, 0.5])
CONCURRENT_REQUESTS: int = int(_cfg.get("CONCURRENT_REQUESTS", 32))
MODEL_ID: str = _cfg.get("MODEL_ID", "velvet-2b")
MAX_NEW_TOKENS: int = int(_cfg.get("MAX_NEW_TOKENS", 512))
TOP_P: float = float(_cfg.get("TOP_P", 0.95))
MAX_RETRIES: int = int(_cfg.get("MAX_RETRIES", 3))
BACKOFF_FACTOR: float = float(_cfg.get("BACKOFF_FACTOR", 0.5))
SCHEMA_MODE: InferenceMode = InferenceMode(_cfg.get("SCHEMA_MODE", "positive"))
PROMPT_STRATEGY: PromptAssignmentStrategy = PromptAssignmentStrategy(
    _cfg.get("PROMPT_STRATEGY", "all")
)
CHAT_TYPE_MAPPING_PATH: str = _cfg.get(
    "CHAT_TYPE_MAPPING_PATH",
    str(Path(__file__).parent / "modules/templates/dpo/chat_type_mapping.yml"),
)

# --- Sampling extras (all optional; None = omit from payload) ---
# N: number of completions per request. n>1 → each choice becomes a separate record.
N: int = int(_cfg.get("N", 1))
STOP: list[str] | str | None = _cfg.get("STOP", None)
PRESENCE_PENALTY: float = float(_cfg.get("PRESENCE_PENALTY", 0.0))
FREQUENCY_PENALTY: float = float(_cfg.get("FREQUENCY_PENALTY", 0.0))
SEED: int | None = _cfg.get("SEED", None)
LOGPROBS: bool = bool(_cfg.get("LOGPROBS", False))
TOP_LOGPROBS: int | None = _cfg.get("TOP_LOGPROBS", None)
# response_format: "text" or "json_object"
RESPONSE_FORMAT: str = _cfg.get("RESPONSE_FORMAT", "text")

# Metadata keys injected by the client — never treated as a mode key
_META_KEYS: frozenset[str] = frozenset({"_id_hash", "_distribution_name", "_distribution_id", "_distribution_uri", "_replica_idx"})


# ---------------------------------------------------------------------------
# Task definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InferenceTask:
    id_hash: str
    messages: list[dict]         # role/content list (output of template function)
    temperature: float
    system_prompt_id: str | None
    dist_name: str
    mode: InferenceMode
    dist_id: str | None = field(default=None)  # distribution unique identifier
    dist_uri: str | None = field(default=None)  # distribution path or URI
    replica_idx: int = field(default=0)  # which replica pass (0-based)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint(output_dir: str) -> set[tuple[str, float, str | None, int]]:
    """Return set of (id_hash, temperature, system_prompt_id, replica_idx) already written."""
    done: set[tuple[str, float, str | None, int]] = set()
    for fpath in glob.glob(f"{output_dir}/*.jsonl"):
        with open(fpath) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    mode_key = next((k for k in d if k not in _META_KEYS), None)
                    if mode_key is None:
                        continue
                    params = (d.get(mode_key) or {}).get("inference_params") or {}
                    done.add((
                        d["_id_hash"],
                        params.get("temperature"),
                        params.get("system_prompt_id"),
                        int(d.get("_replica_idx", 0)),
                    ))
                except Exception:
                    continue
    return done


# ---------------------------------------------------------------------------
# Task builder
# ---------------------------------------------------------------------------

def _build_tasks(
    samples: list[dict],
    entry: RecipeEntry,
    mode: InferenceMode,
    temperatures: list[float],
    assigner: SystemPromptAssigner,
    registry: ChatTypeRegistry,
) -> list[InferenceTask]:
    """Expand samples into (sample × replica × prompts × temperatures) task list."""
    prompts: list[str] = entry.system_prompt or []
    prompt_names: list[str] = entry.system_prompt_name or []
    template_fn = registry.get_template_fn(entry.chat_type)
    tasks: list[InferenceTask] = []

    for rep in range(entry.replica):
        for row_idx, sample in enumerate(samples):
            id_hash: str = sample["_id_hash"]
            assigned = assigner.assign(sample, prompts, prompt_names, row_idx=row_idx)

            for _, sys_content, sys_name in assigned:
                try:
                    messages = template_fn(sample, sys_content)
                except Exception as e:
                    logger.error(
                        "[%s] Template error id_hash=%s sys_prompt=%s rep=%d: %s — skipping.",
                        entry.dist_name, id_hash, sys_name, rep, e,
                    )
                    continue
                for temp in temperatures:
                    tasks.append(
                        InferenceTask(
                            id_hash=id_hash,
                            messages=messages,
                            temperature=temp,
                            system_prompt_id=sys_name,
                            dist_name=entry.dist_name,
                            mode=mode,
                            dist_id=entry.dist_id,
                            dist_uri=entry.dist_uri,
                            replica_idx=rep,
                        )
                    )

    return tasks


# ---------------------------------------------------------------------------
# Async inference
# ---------------------------------------------------------------------------

async def _infer(
    sem: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    task: InferenceTask,
) -> list[dict[str, Any]] | None:
    """Send one /v1/chat/completions request.

    Returns a list of BASE-schema records (one per choice when N > 1),
    or None on unrecoverable failure.
    """
    payload: dict = {
        "model": MODEL_ID,
        "messages": task.messages,
        "temperature": task.temperature,
        "max_tokens": MAX_NEW_TOKENS,
        "top_p": TOP_P,
        "n": N,
        "presence_penalty": PRESENCE_PENALTY,
        "frequency_penalty": FREQUENCY_PENALTY,
        "logprobs": LOGPROBS,
        "response_format": {"type": RESPONSE_FORMAT},
    }
    if STOP is not None:
        payload["stop"] = STOP
    if SEED is not None:
        payload["seed"] = SEED
    if LOGPROBS and TOP_LOGPROBS is not None:
        payload["top_logprobs"] = TOP_LOGPROBS

    async with sem:
        attempt = 0
        while attempt <= MAX_RETRIES:
            try:
                timeout = aiohttp.ClientTimeout(total=600)
                async with session.post(API_URL, json=payload, timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "HTTP %d for id_hash=%s temp=%s (attempt=%d)",
                            resp.status, task.id_hash, task.temperature, attempt,
                        )
                        if 500 <= resp.status < 600 and attempt < MAX_RETRIES:
                            attempt += 1
                            await asyncio.sleep(BACKOFF_FACTOR * (2 ** (attempt - 1)))
                            continue
                        return None

                    result = await resp.json()

                    if not (
                        isinstance(result, dict)
                        and isinstance(result.get("choices"), list)
                        and result["choices"]
                    ):
                        logger.error(
                            "Unable to parse model response for id_hash=%s: %s",
                            task.id_hash, result,
                        )
                        return None

                    records: list[dict] = []
                    for choice_idx, choice in enumerate(result["choices"]):
                        if not isinstance(choice, dict):
                            continue
                        text_out = (choice.get("message") or {}).get("content")
                        if not text_out:
                            logger.warning(
                                "Empty content for id_hash=%s choice=%d — skipping.",
                                task.id_hash, choice_idx,
                            )
                            continue
                        item = ResponseItem(
                            content=str(text_out),
                            score=0.0,
                            think=None,
                            context=None,
                            inference_params=InferenceParams(
                                model_id=MODEL_ID,
                                temperature=task.temperature,
                                top_p=TOP_P,
                                system_prompt_id=task.system_prompt_id,
                            ),
                        )
                        record = make_base_record(
                            task.id_hash, task.dist_name, task.mode, item,
                            dist_id=task.dist_id, dist_uri=task.dist_uri
                        )
                        record["_replica_idx"] = task.replica_idx
                        record["_choice_idx"] = choice_idx
                        if LOGPROBS:
                            record["_logprobs"] = choice.get("logprobs")
                        records.append(record)

                    return records if records else None

            except Exception as e:
                logger.error(
                    "Request failed for id_hash=%s (attempt=%d): %s",
                    task.id_hash, attempt, e,
                )
                if attempt < MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(BACKOFF_FACTOR * (2 ** (attempt - 1)))
                    continue
                return None


# ---------------------------------------------------------------------------
# Entry pipeline
# ---------------------------------------------------------------------------

async def _process_entry(
    entry: RecipeEntry,
    mode: InferenceMode,
    assigner: SystemPromptAssigner,
    registry: ChatTypeRegistry,
    output_base: Path,
    agg_base: Path,
) -> None:
    raw_dir = output_base / entry.dist_name
    agg_dir = agg_base / entry.dist_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    agg_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[%s] Loading samples from %s", entry.dist_name, entry.dist_uri)
    samples = DataLoader.load(entry.dist_uri)
    logger.info(
        "[%s] %d samples loaded (replica=%d)", entry.dist_name, len(samples), entry.replica
    )

    all_tasks = _build_tasks(samples, entry, mode, TEMPERATURE_RANGE, assigner, registry)
    logger.info(
        "[%s] %d total tasks (samples=%d × replica=%d × prompts × temperatures)",
        entry.dist_name, len(all_tasks), len(samples), entry.replica,
    )

    done = _load_checkpoint(str(raw_dir))
    pending = [
        t for t in all_tasks
        if (t.id_hash, t.temperature, t.system_prompt_id, t.replica_idx) not in done
    ]
    logger.info("[%s] Checkpoint: %d done, %d pending", entry.dist_name, len(done), len(pending))

    if pending:
        writer = RollingJsonlWriter(str(raw_dir), "inference", MAX_FILE_SIZE_MB)
        sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

        async with aiohttp.ClientSession() as session:
            coros = [_infer(sem, session, t) for t in pending]
            for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=entry.dist_name):
                records = await coro
                for record in (records or []):
                    writer.write(record)

        writer.close()

    # Aggregate raw JSONL → Parquet in a separate output directory
    jsonl_files = list(raw_dir.glob("*.jsonl"))
    if jsonl_files:
        logger.info(
            "[%s] Aggregating %d JSONL files with DuckDB → %s",
            entry.dist_name, len(jsonl_files), agg_dir,
        )
        aggregator = DuckDBAggregator(mode=mode.value, max_mb=MAX_FILE_SIZE_MB)
        parquet_files = aggregator.aggregate_and_write(jsonl_files, agg_dir)
        logger.info(
            "[%s] Wrote %d Parquet file(s) to %s",
            entry.dist_name, len(parquet_files), agg_dir,
        )
    else:
        logger.warning("[%s] No JSONL files found for aggregation", entry.dist_name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    recipe = RecipeLoader.load(RECIPE_PATH)
    logger.info("Recipe: %s (%d entries)", recipe.recipe_name, len(recipe.entries))

    output_base = Path(OUTPUT_BASE_DIR)
    agg_base = Path(AGGREGATED_BASE_DIR)
    assigner = SystemPromptAssigner(strategy=PROMPT_STRATEGY)
    registry = ChatTypeRegistry(CHAT_TYPE_MAPPING_PATH)
    logger.info(
        "Loaded chat type registry: %s | endpoint=%s | mode=%s",
        registry.known_chat_types(),
        API_URL,
        SCHEMA_MODE.value,
    )

    for uri, entry in recipe.entries.items():
        logger.info(
            "=== Processing entry: %s (chat_type=%s) ===", entry.dist_name, entry.chat_type
        )
        await _process_entry(entry, SCHEMA_MODE, assigner, registry, output_base, agg_base)

    logger.info("All entries processed.")


if __name__ == "__main__":
    asyncio.run(main())
