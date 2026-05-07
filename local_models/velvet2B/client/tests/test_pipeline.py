"""End-to-end pipeline tests — OpenAI /v1/chat/completions endpoint only.

Test sections
─────────────
  Step 1 · chat template   (apply_chat_template — train_dpo)
  Step 2 · prompt assigner (SystemPromptAssigner strategies)
  Step 3 · task builder    (_build_tasks, replica factor, sys_name tracking)
  Step 4 · inference mock  (_infer with mocked HTTP, OpenAI format)
  Step 5 · writer + ckpt   (RollingJsonlWriter  + _load_checkpoint round-trip)
  Step 6 · aggregation     (DuckDBAggregator → separate Parquet dir)
  Step 7 · full pipeline   (_process_entry end-to-end + checkpoint resume)

Persistent output (survives the pytest run):
    tests/logs/results/intermediate/   – raw JSONL from step 7
    tests/logs/results/aggregated/     – aggregated Parquet from step 7
    tests/logs/results/reports/        – per-test step JSON logs
    tests/logs/results/summary.json    – overall pass/fail
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pyarrow.parquet as pq
import pytest

# ── project imports ──────────────────────────────────────────────────────────
import async_client
from async_client import (
    InferenceTask,
    _build_tasks,
    _infer,
    _load_checkpoint,
    _process_entry,
)
from modules.aggregator.aggregator import DuckDBAggregator
from modules.recipe.recipe_config import RecipeEntry
from modules.schemas.inference_schemas import InferenceMode, InferenceParams, ResponseItem, make_base_record
from modules.system_prompt.assigner import PromptAssignmentStrategy, SystemPromptAssigner
from modules.templates.chat_type_registry import ChatTypeRegistry
from modules.templates.dpo.template_functions.instruct_dpo_apply_chat_template import (
    apply_chat_template,
)
from modules.writer.writer import RollingJsonlWriter

from helpers import (
    AGG_DIR,
    INTER_DIR,
    MockClientSession,
    _id_hash,
    _make_sample,
    openai_response,
    write_jsonl,
    CHAT_TYPE_MAPPING,
)


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 · Chat template (train_dpo)
# ════════════════════════════════════════════════════════════════════════════

class TestChatTemplate:
    """Verify apply_chat_template converts DPO samples to OpenAI role/content lists."""

    def test_single_turn_no_system_prompt(self, step_logger, sample_single_turn):
        step_logger.log("input", input=sample_single_turn)
        result = apply_chat_template(sample_single_turn, None)
        step_logger.log("output", output=result)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "Italia" in result[0]["content"]
        # No system message injected
        assert not any(m["role"] == "system" for m in result)
        step_logger.mark_passed()

    def test_single_turn_with_system_prompt(self, step_logger, sample_single_turn):
        sys_prompt = "Sei un assistente geografico esperto."
        step_logger.log("input", input={"sample": sample_single_turn, "sys_prompt": sys_prompt})
        result = apply_chat_template(sample_single_turn, sys_prompt)
        step_logger.log("output", output=result)

        assert result[0]["role"] == "system"
        assert result[0]["content"] == sys_prompt
        assert result[1]["role"] == "user"
        assert result[-1]["role"] == "user"  # generation target must end on user turn
        step_logger.mark_passed()

    def test_multi_turn_context_preserved(self, step_logger, sample_multi_turn):
        step_logger.log("input", input=sample_multi_turn)
        result = apply_chat_template(sample_multi_turn, None)
        step_logger.log("output", output=result)

        roles = [m["role"] for m in result]
        assert roles == ["user", "assistant", "user"]
        # Completed assistant turn must contain the canned reply
        assert "Italia" in result[1]["content"]
        # Last turn is user (the generation target ASSISTANT turn is excluded)
        assert result[-1]["role"] == "user"
        step_logger.mark_passed()

    def test_assistant_target_excluded(self, step_logger):
        """An ASSISTANT message without content is the generation target → must be dropped."""
        sample = _make_sample("excl_001", "Chi ha scritto la Divina Commedia?")
        step_logger.log("input", input=sample)
        result = apply_chat_template(sample, None)
        step_logger.log("output", output=result)

        # Only the USER message should survive
        assert all(m["role"] != "assistant" for m in result)
        step_logger.mark_passed()

    def test_error_empty_messages(self, step_logger):
        bad = {"_id_hash": _id_hash("err_001"), "messages": []}
        step_logger.log("input", input=bad)
        with pytest.raises(ValueError, match="missing or empty"):
            apply_chat_template(bad, None)
        step_logger.log("output", output="ValueError raised as expected")
        step_logger.mark_passed()

    def test_error_last_turn_not_user(self, step_logger):
        """A completed ASSISTANT turn as last usable message should raise."""
        bad = {
            "_id_hash": _id_hash("err_002"),
            "messages": [
                {"role": "USER",      "content": "Ciao"},
                {"role": "ASSISTANT", "content": "Ciao a te!"},
                # No pending ASSISTANT target, no trailing USER → last non-system = assistant
            ],
        }
        step_logger.log("input", input=bad)
        with pytest.raises(ValueError, match="last message must be a user turn"):
            apply_chat_template(bad, None)
        step_logger.log("output", output="ValueError raised as expected")
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 · System prompt assigner
# ════════════════════════════════════════════════════════════════════════════

class TestPromptAssigner:

    def test_all_strategy_cartesian(self, step_logger, sample_single_turn, system_prompts):
        prompts, names = system_prompts
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)
        step_logger.log("input", input={"sample_id": sample_single_turn["_id_hash"], "prompts": names})

        result = assigner.assign(sample_single_turn, prompts, names, row_idx=0)
        step_logger.log("output", output=[(n) for _, _, n in result])

        assert len(result) == len(prompts)
        assert {n for _, _, n in result} == set(names)
        step_logger.mark_passed()

    def test_round_robin_strategy(self, step_logger, system_prompts):
        prompts, names = system_prompts
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ROUND_ROBIN)

        for i in range(len(prompts) * 2):
            sample = _make_sample(f"rr_{i}", f"Domanda {i}")
            result = assigner.assign(sample, prompts, names, row_idx=i)
            step_logger.log(f"row_idx={i}", output=result[0][2])
            assert len(result) == 1
            assert result[0][2] == names[i % len(names)]

        step_logger.mark_passed()

    def test_random_strategy_returns_one(self, step_logger, sample_single_turn, system_prompts):
        prompts, names = system_prompts
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.RANDOM)
        step_logger.log("input", input={"prompts": names})

        result = assigner.assign(sample_single_turn, prompts, names, row_idx=0)
        step_logger.log("output", output=result[0][2])

        assert len(result) == 1
        assert result[0][2] in names
        step_logger.mark_passed()

    def test_no_prompts_returns_none_tuple(self, step_logger, sample_single_turn):
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)
        step_logger.log("input", input={"prompts": []})
        result = assigner.assign(sample_single_turn, [], [], row_idx=0)
        step_logger.log("output", output=result)

        assert result == [(sample_single_turn, None, None)]
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 · Task builder
# ════════════════════════════════════════════════════════════════════════════

class TestTaskBuilder:

    def _make_entry(
        self,
        dist_uri: str,
        replica: int = 1,
        prompts: list[str] | None = None,
        names: list[str] | None = None,
    ) -> RecipeEntry:
        return RecipeEntry(
            chat_type="train_dpo",
            dist_id=_id_hash("entry"),
            dist_name="test_dist",
            dist_uri=dist_uri,
            replica=replica,
            samples=1,
            system_prompt=prompts,
            system_prompt_name=names,
            tokens=100,
            words=50,
            validation_error=None,
        )

    def test_replica1_expansion(self, step_logger, sample_batch, chat_registry, tmp_path):
        """1 sample × replica=1 × 1 prompt × 2 temps → 2 tasks."""
        n_temps = len(async_client.TEMPERATURE_RANGE)  # patched to [0.0, 0.7]
        entry = self._make_entry(str(tmp_path), prompts=["sys"], names=["s1"])
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        tasks = _build_tasks([sample_batch[0]], entry, InferenceMode.negative,
                             async_client.TEMPERATURE_RANGE, assigner, chat_registry)
        step_logger.log("expansion", input={"samples": 1, "replica": 1, "temps": n_temps},
                        output={"n_tasks": len(tasks)})

        assert len(tasks) == 1 * 1 * 1 * n_temps  # samples × replica × prompts × temps
        step_logger.mark_passed()

    def test_replica2_doubles_tasks(self, step_logger, sample_batch, chat_registry, tmp_path):
        """replica=2 must double the task count."""
        n_temps = len(async_client.TEMPERATURE_RANGE)
        entry = self._make_entry(str(tmp_path), replica=2, prompts=["sys"], names=["s1"])
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        tasks = _build_tasks([sample_batch[0]], entry, InferenceMode.negative,
                             async_client.TEMPERATURE_RANGE, assigner, chat_registry)
        step_logger.log("expansion", input={"samples": 1, "replica": 2, "temps": n_temps},
                        output={"n_tasks": len(tasks), "replica_indices": [t.replica_idx for t in tasks]})

        assert len(tasks) == 1 * 2 * 1 * n_temps
        replica_idxs = {t.replica_idx for t in tasks}
        assert replica_idxs == {0, 1}
        step_logger.mark_passed()

    def test_system_prompt_id_propagated(self, step_logger, sample_batch, chat_registry, tmp_path):
        """sys_name from assigner must arrive in InferenceTask.system_prompt_id."""
        prompts = ["Prompt A", "Prompt B"]
        names   = ["sys_A",   "sys_B"]
        entry = self._make_entry(str(tmp_path), prompts=prompts, names=names)
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        tasks = _build_tasks([sample_batch[0]], entry, InferenceMode.negative,
                             async_client.TEMPERATURE_RANGE, assigner, chat_registry)
        found_names = {t.system_prompt_id for t in tasks}
        step_logger.log("sys_names", output=sorted(found_names))

        assert found_names == set(names)
        step_logger.mark_passed()

    def test_no_system_prompt_id_is_none(self, step_logger, sample_batch, chat_registry, tmp_path):
        """When entry has no system_prompt, system_prompt_id must be None in all tasks."""
        entry = self._make_entry(str(tmp_path), prompts=None, names=None)
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        tasks = _build_tasks([sample_batch[0]], entry, InferenceMode.negative,
                             async_client.TEMPERATURE_RANGE, assigner, chat_registry)
        step_logger.log("sys_names", output=[t.system_prompt_id for t in tasks])

        assert all(t.system_prompt_id is None for t in tasks)
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 · Inference mock  (OpenAI /v1/chat/completions)
# ════════════════════════════════════════════════════════════════════════════

def _make_task(
    seed: str = "infer_001",
    temperature: float = 0.5,
    sys_id: str | None = "sys_v1",
) -> InferenceTask:
    return InferenceTask(
        id_hash=_id_hash(seed),
        messages=[{"role": "user", "content": "Qual è la capitale d'Italia?"}],
        temperature=temperature,
        system_prompt_id=sys_id,
        dist_name="test_dist",
        mode=InferenceMode.negative,
        replica_idx=0,
    )


class TestInferMock:

    @pytest.mark.asyncio
    async def test_successful_inference_base_schema(self, step_logger):
        """Happy path: mock returns valid OpenAI response → BASE-schema record returned."""
        task = _make_task()
        resp_text = "Roma è la capitale d'Italia."
        session = MockClientSession(openai_response(resp_text))
        step_logger.log("task", input={"id_hash": task.id_hash[:8], "temp": task.temperature})

        sem = asyncio.Semaphore(1)
        record = await _infer(sem, session, task)
        step_logger.log("record", output=record)

        assert record is not None
        assert record["_id_hash"] == task.id_hash
        assert record["_distribution_name"] == "test_dist"
        assert record["_replica_idx"] == 0
        neg = record["negative"]
        assert neg["content"] == resp_text
        assert neg["inference_params"]["system_prompt_id"] == "sys_v1"
        assert neg["inference_params"]["temperature"] == 0.5
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_system_prompt_id_in_inference_params(self, step_logger):
        """system_prompt_id must be preserved through InferenceParams → record."""
        for sys_id in ["sys_v1", "sys_v2", None]:
            task = _make_task(seed=f"sp_{sys_id}", sys_id=sys_id)
            session = MockClientSession(openai_response("risposta"))
            record = await _infer(asyncio.Semaphore(1), session, task)
            step_logger.log(f"sys_id={sys_id}", output=record["negative"]["inference_params"])
            assert record["negative"]["inference_params"]["system_prompt_id"] == sys_id
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_500_retries_then_succeeds(self, step_logger):
        """One 500 followed by a 200 → retries and returns record (MAX_RETRIES ≥ 1)."""
        task = _make_task()
        # First call: 500, second call: 200 success
        session = MockClientSession(
            responses=[{}, openai_response("Dopo retry: Roma.")],
            statuses=[500, 200],
        )
        step_logger.log("setup", note="500 first call, 200 second call")

        sem = asyncio.Semaphore(1)
        record = await _infer(sem, session, task)
        step_logger.log("record", output=record)

        assert record is not None
        assert "Roma" in record["negative"]["content"]
        assert session._call_idx == 2  # exactly 2 HTTP calls made
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_none(self, step_logger):
        """If every attempt returns 500, _infer must return None without raising."""
        task = _make_task()
        max_calls = async_client.MAX_RETRIES + 1
        session = MockClientSession(
            responses=[{}] * max_calls,
            statuses=[500] * max_calls,
        )
        step_logger.log("setup", note=f"all {max_calls} attempts return 500")

        sem = asyncio.Semaphore(1)
        record = await _infer(sem, session, task)
        step_logger.log("result", output=record)

        assert record is None
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_unparseable_response_returns_none(self, step_logger):
        """A 200 with a response body that has no recognisable text field → None."""
        task = _make_task()
        session = MockClientSession({"totally_unexpected_key": "oops"})
        step_logger.log("setup", note="response body has no known text field")

        record = await _infer(asyncio.Semaphore(1), session, task)
        step_logger.log("result", output=record)

        assert record is None
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_payload_is_openai_format(self, step_logger):
        """When USE_CHAT_COMPLETIONS_API=True the payload must contain 'messages', not 'text'."""
        task = _make_task(temperature=0.3)
        session = MockClientSession(openai_response("ok"))
        step_logger.log("task_messages", input=task.messages)

        await _infer(asyncio.Semaphore(1), session, task)
        payload = session.recorded_payloads[0]["payload"]
        step_logger.log("payload_sent", output=payload)

        assert "messages" in payload, "OpenAI path must use 'messages'"
        assert "text" not in payload,  "OpenAI path must NOT use flat 'text'"
        assert payload["temperature"] == 0.3
        assert payload["messages"] == task.messages
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 5 · RollingJsonlWriter + checkpoint
# ════════════════════════════════════════════════════════════════════════════

def _make_base_record(seed: str, temperature: float, sys_id: str | None, replica: int = 0) -> dict:
    item = ResponseItem(
        content="Risposta di test.",
        score=0.0,
        inference_params=InferenceParams(
            model_id="velvet-2b",
            temperature=temperature,
            top_p=0.95,
            top_k=20,
            system_prompt_id=sys_id,
        ),
    )
    rec = make_base_record(_id_hash(seed), "test_dist", InferenceMode.negative, item)
    rec["_replica_idx"] = replica
    return rec


class TestWriterCheckpoint:

    def test_writer_creates_jsonl_files(self, step_logger, tmp_path):
        out_dir = tmp_path / "raw"
        writer = RollingJsonlWriter(str(out_dir), "inference", max_mb=100)
        records = [_make_base_record(f"w_{i}", 0.5, "sys_v1") for i in range(5)]

        for r in records:
            writer.write(r)
        writer.close()

        jsonl_files = list(out_dir.glob("*.jsonl"))
        step_logger.log("files_created", output=[f.name for f in jsonl_files])
        assert len(jsonl_files) >= 1

        # Verify each line is valid JSON with expected keys
        all_lines = []
        for f in jsonl_files:
            all_lines += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        step_logger.log("records_read_back", output=len(all_lines))
        assert len(all_lines) == 5
        for rec in all_lines:
            assert "_id_hash" in rec
            assert "negative" in rec
        step_logger.mark_passed()

    def test_checkpoint_round_trip(self, step_logger, tmp_path):
        """Written records must be recognized as 'done' by _load_checkpoint."""
        out_dir = tmp_path / "raw"
        writer = RollingJsonlWriter(str(out_dir), "inference", max_mb=100)

        combos = [
            ("ckpt_A", 0.0, "sys_v1", 0),
            ("ckpt_A", 0.7, "sys_v1", 0),
            ("ckpt_B", 0.0, "sys_v2", 1),
        ]
        for seed, temp, sid, rep in combos:
            writer.write(_make_base_record(seed, temp, sid, rep))
        writer.close()

        done = _load_checkpoint(str(out_dir))
        step_logger.log("checkpoint_keys", output=[(k[0][:8], k[1], k[2], k[3]) for k in done])

        assert len(done) == 3
        for seed, temp, sid, rep in combos:
            assert (_id_hash(seed), temp, sid, rep) in done, \
                f"Key ({seed[:8]}, {temp}, {sid}, {rep}) missing from checkpoint"
        step_logger.mark_passed()

    def test_checkpoint_excludes_missing(self, step_logger, tmp_path):
        """A task not yet written must NOT appear in the checkpoint set."""
        out_dir = tmp_path / "raw"
        writer = RollingJsonlWriter(str(out_dir), "inference", max_mb=100)
        writer.write(_make_base_record("present", 0.0, None, 0))
        writer.close()

        done = _load_checkpoint(str(out_dir))
        missing_key = (_id_hash("absent"), 0.0, None, 0)
        step_logger.log("done_keys", output=list(done))
        step_logger.log("missing_key", output=missing_key)
        assert missing_key not in done
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 6 · DuckDB aggregation → separate Parquet directory
# ════════════════════════════════════════════════════════════════════════════

class TestAggregation:

    def test_aggregates_variants_into_list(self, step_logger, tmp_path):
        """3 records for the same id_hash (3 temperatures) → 1 aggregated row, negatives=[3 items]."""
        raw_dir = tmp_path / "raw"
        agg_dir = tmp_path / "agg"
        raw_dir.mkdir()

        id_h  = _id_hash("agg_sample")
        temps = [0.0, 0.4, 0.7]
        records = []
        for temp in temps:
            item = ResponseItem(
                content=f"Risposta a temperatura {temp}",
                score=0.0,
                inference_params=InferenceParams(
                    model_id="velvet-2b",
                    temperature=temp,
                    top_p=0.95,
                    top_k=20,
                    system_prompt_id="sys_v1",
                ),
            )
            rec = make_base_record(id_h, "test_dist", InferenceMode.negative, item)
            rec["_replica_idx"] = 0
            records.append(rec)

        jsonl_path = raw_dir / "inference_part1.jsonl"
        write_jsonl(jsonl_path, records)
        step_logger.log("raw_records", input=len(records))

        aggregator = DuckDBAggregator(mode="negative", max_mb=100)
        parquet_files = aggregator.aggregate_and_write([jsonl_path], agg_dir)
        step_logger.log("parquet_files", output=[f.name for f in parquet_files])

        assert len(parquet_files) >= 1
        tbl = pq.read_table(parquet_files[0])
        df  = tbl.to_pydict()
        step_logger.log("schema", output=tbl.schema.to_string())
        step_logger.log("aggregated_rows", output=len(df["_id_hash"]))

        assert df["_id_hash"][0] == id_h
        assert len(df["negatives"][0]) == 3
        step_logger.mark_passed()

    def test_agg_and_raw_dirs_are_separate(self, step_logger, tmp_path):
        """Aggregated Parquet must land in agg_dir, NOT in raw_dir."""
        raw_dir = tmp_path / "raw"
        agg_dir = tmp_path / "agg"
        raw_dir.mkdir()

        jsonl_path = raw_dir / "inference_part1.jsonl"
        write_jsonl(jsonl_path, [_make_base_record("sep_001", 0.0, None)])

        aggregator = DuckDBAggregator(mode="negative", max_mb=100)
        parquet_files = aggregator.aggregate_and_write([jsonl_path], agg_dir)
        step_logger.log("parquet_dir", output=str(parquet_files[0].parent))

        for pf in parquet_files:
            assert pf.parent == agg_dir, \
                f"Parquet {pf.name} landed in wrong dir: {pf.parent}"
            assert raw_dir not in pf.parents, "Parquet must not be inside raw_dir"
        step_logger.mark_passed()

    def test_parquet_content_matches_negatives_schema(self, step_logger, tmp_path):
        """Each element in the negatives list must have content, score, inference_params."""
        raw_dir = tmp_path / "raw"
        agg_dir = tmp_path / "agg"
        raw_dir.mkdir()

        jsonl_path = raw_dir / "inference_part1.jsonl"
        write_jsonl(jsonl_path, [_make_base_record("schema_001", 0.5, "sys_v1")])

        aggregator = DuckDBAggregator(mode="negative", max_mb=100)
        parquet_files = aggregator.aggregate_and_write([jsonl_path], agg_dir)
        df = pq.read_table(parquet_files[0]).to_pydict()
        neg = df["negatives"][0][0]
        step_logger.log("negative_item", output=neg)

        assert "content"          in neg
        assert "score"            in neg
        assert "inference_params" in neg
        assert neg["inference_params"]["system_prompt_id"] == "sys_v1"
        step_logger.mark_passed()


# ════════════════════════════════════════════════════════════════════════════
# STEP 7 · Full pipeline  (_process_entry end-to-end)
# ════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end tests that write results to tests/logs/results/ for inspection."""

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _persistent_dirs(name: str) -> tuple[Path, Path]:
        """Return (raw_dir, agg_dir) inside tests/logs/results/ — NOT tmp_path."""
        raw = INTER_DIR / name
        agg = AGG_DIR   / name
        raw.mkdir(parents=True, exist_ok=True)
        agg.mkdir(parents=True, exist_ok=True)
        return raw, agg

    @staticmethod
    def _patch_session(responses: list[dict]) -> MockClientSession:
        return MockClientSession(responses)

    # ── tests ────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_e2e_negative_mode_three_samples(
        self, step_logger, recipe_entry_factory, sample_batch
    ):
        """Full pipeline: 3 samples, replica=1, 1 sys prompt, 2 temps → 6 inference calls,
        raw JSONL in intermediate/, aggregated Parquet in aggregated/."""

        sys_prompts = ["Sei un assistente utile."]
        sys_names   = ["sys_v1"]

        entry, _ = recipe_entry_factory(
            sample_batch,
            replica=1,
            system_prompts=sys_prompts,
            system_prompt_names=sys_names,
            dist_name="e2e_three_samples",
        )
        raw_dir, agg_dir = self._persistent_dirs("e2e_three_samples")
        step_logger.log("entry", input={
            "dist_name": entry.dist_name,
            "n_samples": entry.samples,
            "replica": entry.replica,
            "sys_prompts": sys_names,
            "temperatures": async_client.TEMPERATURE_RANGE,
        })

        # 3 samples × 1 prompt × 2 temps = 6 calls
        n_expected = 3 * 1 * len(async_client.TEMPERATURE_RANGE)
        responses  = [openai_response(f"Risposta mock #{i}") for i in range(n_expected)]
        mock_sess  = self._patch_session(responses)

        registry = ChatTypeRegistry(CHAT_TYPE_MAPPING)
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        with patch("aiohttp.ClientSession", return_value=mock_sess):
            await _process_entry(
                entry, InferenceMode.negative, assigner, registry,
                raw_dir.parent, agg_dir.parent,
            )

        # ── assertions ──────────────────────────────────────────────────────
        jsonl_files  = list(raw_dir.glob("*.jsonl"))
        parquet_files = list(agg_dir.glob("*.parquet"))
        step_logger.log("raw_jsonl_files",     output=[f.name for f in jsonl_files])
        step_logger.log("parquet_files",        output=[f.name for f in parquet_files])

        assert jsonl_files,  "Expected at least one JSONL file in intermediate/"
        assert parquet_files, "Expected at least one Parquet file in aggregated/"

        # Count total raw records
        all_raw = []
        for f in jsonl_files:
            all_raw += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        step_logger.log("total_raw_records", output=len(all_raw))
        assert len(all_raw) == n_expected

        # Verify raw record schema
        for rec in all_raw:
            assert "_id_hash"             in rec
            assert "_distribution_name"   in rec
            assert "_replica_idx"         in rec
            assert "negative"             in rec
            assert rec["negative"]["inference_params"]["system_prompt_id"] == "sys_v1"

        # Read and inspect Parquet
        all_rows = []
        for pf in parquet_files:
            tbl = pq.read_table(pf)
            all_rows += tbl.to_pylist()
        step_logger.log("aggregated_rows", output=len(all_rows))
        step_logger.log("sample_aggregated_row", output={
            "_id_hash":    all_rows[0]["_id_hash"][:12] + "...",
            "n_negatives": len(all_rows[0]["negatives"]),
        })

        # Each unique id_hash produces exactly one aggregated row
        agg_ids = {r["_id_hash"] for r in all_rows}
        assert len(agg_ids) == 3
        # Each row has as many negatives as (prompts × temps)
        for row in all_rows:
            assert len(row["negatives"]) == 1 * len(async_client.TEMPERATURE_RANGE)

        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_e2e_replica2_doubles_records(
        self, step_logger, recipe_entry_factory
    ):
        """replica=2 must produce twice as many raw records as replica=1."""
        samples = [_make_sample(f"r2_{i}", f"Domanda {i}") for i in range(2)]
        entry, _ = recipe_entry_factory(
            samples,
            replica=2,
            system_prompts=None,
            system_prompt_names=None,
            dist_name="e2e_replica2",
        )
        raw_dir, agg_dir = self._persistent_dirs("e2e_replica2")

        # 2 samples × replica=2 × 1 prompt(None) × 2 temps = 8 calls
        n_calls   = 2 * 2 * 1 * len(async_client.TEMPERATURE_RANGE)
        responses = [openai_response(f"Resp #{i}") for i in range(n_calls)]
        mock_sess = self._patch_session(responses)

        registry = ChatTypeRegistry(CHAT_TYPE_MAPPING)
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)
        step_logger.log("setup", input={"n_calls_expected": n_calls})

        with patch("aiohttp.ClientSession", return_value=mock_sess):
            await _process_entry(
                entry, InferenceMode.negative, assigner, registry,
                raw_dir.parent, agg_dir.parent,
            )

        all_raw = []
        for f in raw_dir.glob("*.jsonl"):
            all_raw += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        step_logger.log("raw_records", output=len(all_raw))

        assert len(all_raw) == n_calls
        replica_vals = {r["_replica_idx"] for r in all_raw}
        assert replica_vals == {0, 1}, "Both replica indices must appear in raw output"
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_checkpoint_resume_skips_done_tasks(
        self, step_logger, recipe_entry_factory
    ):
        """On a second run with the same raw_dir, all tasks are already checkpointed
        → zero HTTP calls should be made."""
        samples = [_make_sample("ckpt_resume", "Domanda di test")]
        entry, _ = recipe_entry_factory(
            samples, replica=1,
            system_prompts=["Sei utile."], system_prompt_names=["sys_v1"],
            dist_name="e2e_ckpt_resume",
        )
        # Use persistent dirs so both runs share the same JSONL directory
        raw_dir, agg_dir = self._persistent_dirs("e2e_ckpt_resume")

        registry = ChatTypeRegistry(CHAT_TYPE_MAPPING)
        assigner = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        # ── first run ────────────────────────────────────────────────────────
        n_first  = 1 * 1 * len(async_client.TEMPERATURE_RANGE)
        mock_r1  = self._patch_session([openai_response(f"Run1 #{i}") for i in range(n_first)])
        step_logger.log("run1_start", note=f"expecting {n_first} HTTP calls")
        with patch("aiohttp.ClientSession", return_value=mock_r1):
            await _process_entry(
                entry, InferenceMode.negative, assigner, registry,
                raw_dir.parent, agg_dir.parent,
            )
        step_logger.log("run1_calls", output=mock_r1._call_idx)
        assert mock_r1._call_idx == n_first

        # ── second run (checkpoint should skip everything) ────────────────
        mock_r2 = self._patch_session([openai_response("Should not be called")] * n_first)
        step_logger.log("run2_start", note="all tasks already checkpointed — expect 0 HTTP calls")
        with patch("aiohttp.ClientSession", return_value=mock_r2):
            await _process_entry(
                entry, InferenceMode.negative, assigner, registry,
                raw_dir.parent, agg_dir.parent,
            )
        step_logger.log("run2_calls", output=mock_r2._call_idx)
        assert mock_r2._call_idx == 0, \
            "Second run must make zero HTTP calls — checkpoint must cover all tasks"
        step_logger.mark_passed()

    @pytest.mark.asyncio
    async def test_raw_and_aggregated_dirs_never_overlap(
        self, step_logger, recipe_entry_factory
    ):
        """Parquet files must land in agg_dir; no Parquet in raw_dir."""
        samples = [_make_sample("sep_check", "Test separazione dir")]
        entry, _ = recipe_entry_factory(
            samples, dist_name="e2e_dir_separation",
            system_prompts=None, system_prompt_names=None,
        )
        raw_dir, agg_dir = self._persistent_dirs("e2e_dir_separation")
        step_logger.log("dirs", output={"raw": str(raw_dir), "agg": str(agg_dir)})

        n = len(async_client.TEMPERATURE_RANGE)
        mock_sess = self._patch_session([openai_response("ok")] * n)
        registry  = ChatTypeRegistry(CHAT_TYPE_MAPPING)
        assigner  = SystemPromptAssigner(PromptAssignmentStrategy.ALL)

        with patch("aiohttp.ClientSession", return_value=mock_sess):
            await _process_entry(
                entry, InferenceMode.negative, assigner, registry,
                raw_dir.parent, agg_dir.parent,
            )

        raw_parquets = list(raw_dir.glob("*.parquet"))
        agg_parquets = list(agg_dir.glob("*.parquet"))
        step_logger.log("raw_parquets", output=[f.name for f in raw_parquets])
        step_logger.log("agg_parquets", output=[f.name for f in agg_parquets])

        assert raw_parquets == [], "No Parquet files should appear in the raw JSONL directory"
        assert agg_parquets != [], "Parquet files must appear in the aggregated directory"
        step_logger.mark_passed()
