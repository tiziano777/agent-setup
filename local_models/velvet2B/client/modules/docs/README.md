# DPO Setup — Documentation

Direct Preference Optimization (DPO) training pipeline for LLMs.

---

## Overview

Data preparation → cache generation → DPO training. 

Recipe-driven system: define data sources, system prompts, replication strategy → generates an Arrow-cached dataset → feeds `DPOTrainer` (TRL).

Key features:
- **Modular prompt assignment** — `ALL` / `ROUND_ROBIN` / `RANDOM` strategies
- **Pluggable chat templates** — YAML-mapped, dynamically imported per `chat_type`
- **Strict validation** — fail-fast on any missing config field or dataset column
- **Train / eval split** — automatic percentage-based split controlled from `config.yml`
- **Length filtering** — character-based and token-based filters with discarded sample logging
- **Hard negative selection** — NLP-based 3-phase pipeline for optimal rejected candidate selection
- **Dataset shuffle** — source-aware block shuffling (random or circular interleaving)
- **DeepSpeed integration** — ZeRO stages 0–3, optimizer offloading, activation checkpointing
- **LR schedulers** — linear, cosine, constant, constant_with_warmup
- **PEFT / LoRA** — optional adapter injection via `peft` config block
- **Diagnostic plots** — 9 automated training plots (loss, reward margin, KL divergence, throughput, etc.)
- **Metrics persistence** — crash-resilient log_history saving + periodic in-flight plots
- **HF + local model loading** — `model_uri` for nfs/s3/local checkpoint paths, `model_id` for HF Hub fallback

---

## Quick Start

### 1. Configure

Copy and edit `config.yml` — see [Config Reference](#config-reference) below.

### 2. Set the HF token (gated models)

```bash
export HF_TOKEN=hf_...
# or add to a .env file in the project root
```

### 3. Prepare data

```bash
python prepare.py                  # uses config.yml by default
python prepare.py my_config.yml    # explicit path
```

### 4. Train

```bash
python train.py                    # uses config.yml
python train.py my_config.yml      # explicit path
python train.py --dry-run          # validate config + cache without launching training
```

---

## Pipeline

```
config.yml + recipe block
        │
        ▼
RecipeLoader ──► RecipeConfig (Pydantic)
        │
        ▼  (for each entry)
DataLoader.base_load(dist_uri)          ← READ parquet / jsonl.gz / jsonl auto-detect
        │
        ▼
replicate × entry.replica
        │
        ▼
SystemPromptAssigner                    ← ALL / ROUND_ROBIN / RANDOM
        │
        ▼
HardNegativeFilter (optional)           ← 3-phase NLP scoring for rejected selection
        │
        ▼
ChatTypeRegistry.get_template_fn()      ← dynamic import from mapping YAML
        │
        ▼
apply_chat_template(sample, prompt, temperature)
        │  → {prompt, chosen, rejected, _source_uri, _replica, _system_prompt_id, _id_hash}
        ▼
DataLoader.save_to_cache()              ← Arrow format 
        │
        ▼   (train.py)
DataLoader.load_cached_dataset(eval_size=0.05)
        │   → (ds_train, ds_eval)
        ▼
DatasetShuffler(strategy, block_size)   ← source-aware block shuffle
        │
        ▼
filter_by_length / filter_by_token      ← removes long-context outliers
        │
        ▼
DPOTrainer(train_dataset=ds_train, eval_dataset=ds_eval)
        │
        ▼
MetricsSaverCallback                    ← persists log_history + periodic plots
        │
        ▼
PlotManager.run(log_history)            ← 9 diagnostic plots post-training
```

---

## Config Reference

Full example in `config.yml`. All fields described below.

### `experiment` block

```yaml
experiment:
  id:        # optional UUID
  experiment_name:      # human-readable label (e.g. dpo-lora-velvet)
  description:          # free text
  tags:                 # list of strings
```

### `model` block

| Field | Type | Required | Description |
|---|---|---|---|
| `model_id` | str | yes* | HF Hub model ID (e.g. `meta-llama/Llama-2-7b-hf`) |
| `model_uri` | str | no | Local path or NFS checkpoint. When set, takes priority over `model_id` for loading |

> *Either `model_id` or `model_uri` must resolve to a loadable model.

### `model.dataset` block

| Field | Type | Default | Description |
|---|---|---|---|
| `cache_dir` | str | — | Directory where the Arrow cache is saved by `prepare.py` |
| `cache_file` | str | — | Subdirectory name inside `cache_dir` for the dataset |
| `filtered_samples` | str | — | Path to JSONL file where length-filtered samples are appended |
| `templates_mapping` | str | — | Path to `chat_type_mapping.yml` |
| `prompt_strategy` | str | `random` | Strategy for pairing samples with prompts: `random`, `round_robin`, `all` |
| `rejected_temperature` | float | `0.7` | Temperature used to select negatives during preparation |
| `shuffle_strategy` | str | `random` | Dataset shuffle strategy: `random` (Fisher-Yates) or `circular` (block interleaving) |
| `shuffle_seed` | int | `42` | RNG seed for shuffle reproducibility |
| `shuffle_block_size` | int | `1000` | Rows per block for the shuffler |
| `hard_negative_enabled` | bool | `true` | Enable NLP-based hard negative selection |
| `hard_negative_fallback` | str | `temperature` | Fallback when no candidate survives: `drop` or `temperature` |
| `hard_negative_rouge_delta` | float | `0.08` | ROUGE-L threshold for false negative filtering |
| `hard_negative_tau` | float | `0.5` | Target ROUGE-L distance for ideal hard negatives |
| `hard_negative_entropy_min` | float | `0.3` | Minimum normalized entropy (below = degenerate) |
| `hard_negative_ttr_min` | float | `0.2` | Minimum Type-Token Ratio (below = degenerate) |
| `hard_negative_w1` | float | `0.2` | Scoring weight: entropy |
| `hard_negative_w2` | float | `0.2` | Scoring weight: TTR |
| `hard_negative_w3` | float | `0.4` | Scoring weight: ROUGE distance from tau |
| `hard_negative_w4` | float | `0.2` | Scoring weight: length penalty |

### `model.training` block

| Field | Type | Default | Description |
|---|---|---|---|
| `per_device_train_batch_size` | int | `1` | Batch size per GPU |
| `gradient_accumulation_steps` | int | `16` | Steps to accumulate gradients before update |
| `num_train_epochs` | int | `3` | Number of full passes over training data |
| `max_steps` | int | — | Overrides epochs when set |
| `learning_rate` | float | `1e-5` | Learning rate |
| `lr_scheduler_type` | str | `linear` | LR scheduler (`linear`, `cosine`, `constant`, `constant_with_warmup`) |
| `optim` | str | `paged_adamw_8bit` | Optimizer (`paged_adamw_8bit`, `adamw_torch`, `adafactor`) |
| `weight_decay` | float | `0.0` | Weight decay for regularization |
| `warmup_steps` | int | `1000` | Warmup steps before scheduler kicks in |
| `beta` | float | `0.1` | DPO β (KL penalty coefficient) |
| `gradient_checkpointing` | bool | `true` | Gradient checkpointing to save memory |
| `logging_steps` | int | `10` | Log every N steps |
| `eval_steps` | int | `3000` | Run evaluation every N steps |
| `save_steps` | int | `3000` | Checkpoint every N steps |
| `bf16` | bool | `true` | Use bfloat16 mixed precision |
| `torch_dtype` | str | `bfloat16` | `bfloat16` / `float16` / `float32` |
| `device_map` | str | `auto` | `auto` / `cpu` / `cuda:0` |
| `max_length` | int | `8192` | Maximum total token length (prompt + response) |
| `max_prompt_length` | int | `2048` | Maximum token length for the prompt alone |
| `remove_unused_columns` | bool | `true` | Drop non-DPO columns automatically |
| `report_to` | str | `none` | Logging backend (`none`, `wandb`, `tensorboard`) |
| `eval_size` | float | `0.05` | Fraction held out as eval set (0–1). `0` = no eval split |
| `ref_model` | str | — | Path to reference model. Unset = use training model |
| `precompute_ref_log_probs` | bool | `false` | Precompute ref log probs (saves VRAM, costs disk) |
| `use_cache` | bool | `false` | Cached representations (disable with gradient checkpointing) |

### `model.training.deepspeed` block (optional)

Omit the block to train without DeepSpeed. When present, enables distributed training with ZeRO optimization.

```yaml
training:
  deepspeed:
    bf16:
      enabled: true
    zero_optimization:
      stage: 2                          # 0=disabled, 1=param, 2=grad+param, 3=full sharding
      offload_optimizer:
        device: cpu                     # cpu or nvme
        pin_memory: true
      activation_checkpointing:
        partition_activations: true
        cpu_checkpointing: true
        contiguous_memory_optimization: true
        synchronize_checkpoint_boundary: true
    gradient_accumulation_steps: auto   # "auto" inherits from training config
    gradient_clipping: auto
    train_batch_size: auto
    train_micro_batch_size_per_gpu: auto
```

| Field | Type | Default | Description |
|---|---|---|---|
| `bf16.enabled` | bool | `true` | BF16 precision in DeepSpeed |
| `fp16.enabled` | bool | `false` | FP16 precision (mutually exclusive with bf16) |
| `zero_optimization.stage` | int | `2` | ZeRO stage: 0 (disabled), 1 (param sharding), 2 (grad+param), 3 (full) |
| `zero_optimization.offload_optimizer.device` | str | `cpu` | Offload optimizer state to `cpu` or `nvme` |
| `zero_optimization.offload_optimizer.pin_memory` | bool | `true` | Pin memory for offloaded state |
| `zero_optimization.activation_checkpointing` | object | — | Enable activation checkpointing for memory savings |
| `gradient_accumulation_steps` | str/int | `auto` | `"auto"` inherits from training config |
| `gradient_clipping` | str/float | `auto` | Max gradient norm |
| `train_batch_size` | str/int | `auto` | Global batch size |
| `train_micro_batch_size_per_gpu` | str/int | `auto` | Micro batch per GPU |

### `model.training.peft` block (optional)

Omit the entire block to skip PEFT. When present, a LoRA adapter is injected.

```yaml
peft:
  r: 16
  lora_alpha: 32
  lora_dropout: 0.05
  target_modules: [q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj]
```

| Field | Type | Description |
|---|---|---|
| `r` | int | LoRA rank (intrinsic dimension of low-rank decomposition) |
| `lora_alpha` | int | Scaling factor for LoRA weights |
| `lora_dropout` | float | Dropout rate applied to LoRA layers (0.0–1.0) |
| `target_modules` | list[str] | Module names to apply LoRA to |

### `model.reward` block (optional)

```yaml
reward:
  type: verifiable
  functions:
    - name: accuracy_reward_example
      module_path: modules.rewards.accuracy_example
```

| Field | Type | Description |
|---|---|---|
| `type` | str | Reward type (`verifiable`, `learned`) |
| `functions[].name` | str | Name identifier for the reward function |
| `functions[].module_path` | str | Python import path (e.g. `modules.rewards.accuracy_example`) |

### `output` block

```yaml
output:
  output_dir: /path/to/checkpoints   # trainer writes here
  metrics_uri: /path/to/metrics      # eval metrics + log_history location
```

### `recipe` block

The recipe can live inside `config.yml` or in a standalone YAML file.

```yaml
recipe:
  id: <uuid>
  name: Base DPO Mix
  description: Multi-domain DPO training data
  scope: dpo
  tasks: [instruction-following, reasoning]
  tags: [v1, production]
  entries:
    /absolute/path/to/distribution:
      chat_type: train_dpo
      dist_id: <uuid>
      dist_name: Human-readable name
      dist_uri: /absolute/path/to/distribution
      replica: 2          # repeat dataset N times
      samples: 5000       # informational only
      tokens: 1000000     # informational only
      words: 150000       # informational only
      system_prompt:
        - "You are a helpful assistant."
        - "You are a precise AI."
      system_prompt_name:
        - prompt_helpful
        - prompt_precise
```

---

## Data Formats

### Input (raw distribution)

Supported file types, resolved in priority order:

| Priority | Pattern | Reader |
|---|---|---|
| 1 | `*.parquet` | `pandas.read_parquet` |
| 2 | `*.jsonl.gz` | `pandas.read_json` (gzip) |
| 3 | `*.jsonl` | `pandas.read_json` |

All files inside the directory must share the same format — mixed formats are not supported.

### Sample schema (`train_dpo` chat type)

```json
{
  "_id_hash": "abc123",
  "messages": [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "What is 2+2?"},
    {
      "role": "assistant",
      "positives": [
        {"inference_params": {"temperature": 0.7}, "content": "The answer is 4"}
      ],
      "negatives": [
        {"inference_params": {"temperature": 0.7}, "content": "I don't know"}
      ]
    }
  ]
}
```

Multi-turn samples are supported: completed `assistant` turns (those with `content`) are preserved as prompt context; only the final generation turn (with `positives`/`negatives`) is split into `chosen`/`rejected`.

### Output (DPOTrainer format)

```json
{
  "prompt":   [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "chosen":   [{"role": "assistant", "content": "The answer is 4"}],
  "rejected": [{"role": "assistant", "content": "I don't know"}],
  "_source_uri": "/path/to/dist",
  "_replica": 0,
  "_system_prompt_id": "prompt_helpful",
  "_id_hash": "abc123"
}
```

Temperature selection: matches `inference_params.temperature` in `positives`/`negatives`. Falls back to the first item if no exact match is found.

---

## Prompt Assignment Strategies

Configure via `model.dataset.prompt_strategy` in `config.yml`.

| Strategy | Behaviour | Dataset size |
|---|---|---|
| `all` | Each sample × every prompt (Cartesian product) | `N × P` |
| `round_robin` | Sample at index `i` gets prompt `i % len(prompts)` | `N` |
| `random` | Seeded random selection (`seed=42`) | `N` |

Default is `random`.

---

## Hard Negative Selection

`modules/filters/hard_negative_filtering.py` — `HardNegativeFilter`

When `hard_negative_enabled: true`, the pipeline selects the optimal rejected candidate from K negatives using a 3-phase NLP pipeline instead of simple temperature matching.

### Phase 1: Degenerate Interception

Detects loop/truncation candidates via normalized entropy and Type-Token Ratio. If a degenerate candidate is found, it is immediately selected as the rejected (worst = best negative for training signal).

### Phase 2: False Negative Filtering

Removes candidates with ROUGE-L > `(1 - rouge_delta)` vs gold — these are too close to the positive and would confuse the model.

### Phase 3: Multi-Attribute Scoring

Surviving candidates scored by weighted formula:

```
score = w1 * entropy + w2 * TTR - w3 * |ROUGE_L - tau| - w4 * length_penalty
```

The highest-scoring candidate is selected as the hard negative.

### Fallback

When no candidate survives filtering:
- `temperature` (default): delegate to temperature-based selection
- `drop`: return None, sample skipped from dataset

---

## Dataset Shuffle

`modules/shuffle/shuffler.py` — `DatasetShuffler`

Source-aware block shuffling to avoid training on long runs from the same data source.

1. Groups rows by `_source_uri`
2. Splits each group into fixed-size blocks (`shuffle_block_size` rows)
3. Orders blocks according to strategy

| Strategy | Behaviour |
|---|---|
| `random` | Fisher-Yates shuffle of all blocks (reproducible via `shuffle_seed`) |
| `circular` | Round-robin interleaving — one block per source at a time |

```python
from modules.shuffle.shuffler import DatasetShuffler, ShuffleStrategy

shuffler = DatasetShuffler(ShuffleStrategy.CIRCULAR, block_size=1000, seed=42)
ds_shuffled = shuffler.shuffle(ds_train)
```

---

## Train / Eval Split

Controlled by `model.training.eval_size` in `config.yml`.

- **`eval_size: 0`** — no split, `train.py` receives the full dataset for training only.
- **`eval_size: 0.05`** — 5% of the dataset is held out as `eval_dataset`.

`DataLoader.load_cached_dataset` behaviour:

1. If the cached `DatasetDict` already contains a `validation` / `valid` / `eval` / `test` split, that split is used as eval directly.
2. Otherwise, `train_test_split(test_size=eval_size)` is called on the `train` split.
3. Both `ds_train` and `ds_eval` are independently passed through filters before being handed to `DPOTrainer`.

---

## Length Filtering

Two complementary filters available:

### Character-based — `modules/filters/filter_by_length.py`

`filter_by_length(ds, filtered_samples_path, MAX_PAIR_CHARS=20000)`

Removes samples where:
```
len(prompt) + len(chosen) >= MAX_PAIR_CHARS
OR
len(prompt) + len(rejected) >= MAX_PAIR_CHARS
```

### Token-based — `modules/filters/filter_by_token_len.py`

`filter_by_token(ds, tokenizer, filtered_path, MAX_PAIR_TOKENS=4096, SYSTEM_TOKENS=1024)`

Uses the actual tokenizer for precise token-count filtering. Accounts for system prompt overhead via `SYSTEM_TOKENS`. More accurate than character-based but requires tokenizer to be loaded.

Both filters:
- Append discarded samples to the JSONL file at `model.dataset.filtered_samples`
- Apply independently to both `ds_train` and `ds_eval`
- Log warnings per discarded sample with `_id_hash` and length details

---

## Diagnostic Plots

`modules/plots/plot_manager.py` — `PlotManager`

Generates 9 training diagnostic plots from `trainer.state.log_history` after training completes.

### Available Plots

| Plot | File | Description |
|---|---|---|
| Loss | `loss.png` | Training loss over steps |
| Reward Margin | `reward_margin.png` | Chosen vs rejected reward gap |
| Reward Accuracy | `reward_accuracy.png` | % of correct preference predictions |
| Log Ratio | `log_ratio.png` | Policy/reference log probability ratio |
| KL Divergence | `KL_divergence.png` | KL(π ∥ π_ref) estimated from β |
| Grad Norm | `grad_norm.png` | Gradient norm per step (with clipping ceiling) |
| LR Schedule | `lr_schedule.png` | Learning rate over training |
| Batch Loss | `batch_loss.png` | Per-batch loss distribution |
| Throughput | `throughput.png` | Samples/sec, steps/sec, total runtime, FLOPs |

### Usage

```python
from modules.plots.plot_manager import PlotManager

pm = PlotManager(config_path="config.yml", beta=0.1, max_grad_norm=1.0)
plots_dir = pm.run(trainer.state.log_history)
# → modules/docs/images/<experiment_name>_<timestamp>/
```

Output directory includes a copy of `config.yml` for experiment lineage. Failed plots are logged to `errors.log` (non-fatal).

---

## Metrics Persistence

`modules/callbacks/metrics_saver.py` — `MetricsSaverCallback`

Trainer callback that persists `log_history` to JSON at every evaluate, save, and log event. Enables:
- **Crash recovery** — partial metrics survive interrupted training
- **In-flight plots** — generates diagnostic plots every N steps (default: 500)

```python
from modules.callbacks.metrics_saver import MetricsSaverCallback

callback = MetricsSaverCallback(
    metrics_path=Path("/output/metrics"),
    config_path="config.yml",
    beta=0.1,
    max_grad_norm=1.0,
    plot_every=500,       # generate plots every 500 steps
)
# Pass to DPOTrainer via callbacks=[callback]
```

Output at `metrics_uri`:
```
metrics/
├── log_history.json          # full trainer log (updated every event)
├── plots-iter-500/           # diagnostic plots at step 500
├── plots-iter-1000/          # diagnostic plots at step 1000
└── ...
```

---

## Chat Templates

Dynamic loading via `modules/templates/chat_type_mapping.yml`:

```yaml
train_dpo:
  template_fn: ./dpo/template_functions/instruct_dpo_apply_chat_template.py
  schema:      ./dpo/input_schema_templates/input_schema.json
```

Each template `.py` file must expose:

```python
def apply_chat_template(sample: dict, system_prompt: str | None, temperature: float = 0.7) -> dict:
    ...
```

Template functions are lazily imported and cached on first call. Paths may be relative to the mapping file's directory.

---

## Key Classes

### `DataLoader` — `modules/loader/data_loader.py`

| Method | Signature | Description |
|---|---|---|
| `base_load` | `(dist_uri: str) → list[dict]` | Load all files from a directory, auto-detect format |
| `save_to_cache` | `(data, save_path_dir)` | Persist list of dicts as Arrow dataset |
| `load_cached_dataset` | `(cache_dir, eval_size=0) → Dataset \| tuple[Dataset, Dataset]` | Load Arrow cache; returns `(train, eval)` when `eval_size > 0` |

### `RecipeLoader` — `modules/recipe/recipe_loader.py`

```python
recipe: RecipeConfig = RecipeLoader.load("config.yml")
# also accepts a standalone recipe YAML or an already-parsed dict
```

Extracts the `recipe` block automatically when passed `config.yml`.

### `RecipeConfig` / `RecipeEntry` — `modules/recipe/recipe_config.py`

Pydantic models. `RecipeEntry` validates required fields (`chat_type`, `dist_id`, `dist_name`, `dist_uri`) on load. `replica ≥ 1` is enforced.

### `ChatTypeRegistry` — `modules/templates/chat_type_registry.py`

```python
registry = ChatTypeRegistry("modules/templates/chat_type_mapping.yml")
fn = registry.get_template_fn("train_dpo")
result = fn(sample, system_prompt, temperature=0.7)
```

### `SystemPromptAssigner` — `modules/system_prompt/assigner.py`

```python
assigner = SystemPromptAssigner(PromptAssignmentStrategy.ROUND_ROBIN)
tuples = assigner.assign(sample, prompts, prompt_names, row_idx=0)
# → [(sample_copy, prompt_content, prompt_id), ...]
```

### `ModelLoader` — `modules/loader/model_loader.py`

```python
loader = ModelLoader(hf_token=os.getenv("HF_TOKEN"))
model, tokenizer = loader.load_model(
    model_id="meta-llama/Llama-2-7b-hf",
    model_uri=None,             # or local path
    torch_dtype="bfloat16",
    device_map="auto"
)
```

### `HardNegativeFilter` — `modules/filters/hard_negative_filtering.py`

```python
from modules.filters.hard_negative_filtering import HardNegativeFilter, HardNegativeConfig

config = HardNegativeConfig(enabled=True, fallback="temperature", tau=0.5)
hn_filter = HardNegativeFilter(config)
best_negative = hn_filter.select(candidates, gold_content, temperature=0.7)
```

### `DatasetShuffler` — `modules/shuffle/shuffler.py`

```python
from modules.shuffle.shuffler import DatasetShuffler, ShuffleStrategy

shuffler = DatasetShuffler(ShuffleStrategy.RANDOM, block_size=1000, seed=42)
ds_shuffled = shuffler.shuffle(dataset)
```

### `PlotManager` — `modules/plots/plot_manager.py`

```python
from modules.plots.plot_manager import PlotManager

pm = PlotManager(config_path="config.yml", beta=0.1, max_grad_norm=1.0)
plots_dir = pm.run(trainer.state.log_history)
```

### `MetricsSaverCallback` — `modules/callbacks/metrics_saver.py`

```python
from modules.callbacks.metrics_saver import MetricsSaverCallback

callback = MetricsSaverCallback(metrics_path=Path(metrics_uri), beta=0.1, plot_every=500)
```

### `filter_by_length` — `modules/filters/filter_by_length.py`

```python
ds_clean = filter_by_length(ds, "/path/to/discarded.jsonl", MAX_PAIR_CHARS=20000)
```

### `filter_by_token` — `modules/filters/filter_by_token_len.py`

```python
ds_clean = filter_by_token(ds, tokenizer, "/path/to/discarded.jsonl", MAX_PAIR_TOKENS=4096, SYSTEM_TOKENS=1024)
```

---

## Validation

`modules/utils/config_validator.py`

- `load_config(path)` — loads and YAML-parses the config; raises on `FileNotFoundError` or `YAMLError`.
- `require_field(config, *keys)` — traverses nested dict; raises `ValueError` with full key path if any key is missing or `None`.
- `resolve_config(config)` — resolves environment variables and relative paths in config values.

Dataset preflight in `train.py` checks that `{prompt, chosen, rejected}` columns are present before any model is loaded.

---

## File Layout

```
dpo-setup/
├── config.yml                                      # Main config
├── prepare.py                                      # Data prep pipeline
├── train.py                                        # Training entry point
├── requirements.txt
└── modules/
    ├── callbacks/
    │   └── metrics_saver.py                        # MetricsSaverCallback (log_history + periodic plots)
    ├── filters/
    │   ├── filter_by_length.py                     # Character-based length filter
    │   ├── filter_by_token_len.py                  # Token-based length filter (uses tokenizer)
    │   └── hard_negative_filtering.py              # 3-phase NLP hard negative selection
    ├── loader/
    │   ├── data_loader.py                          # Format auto-detect, cache, train/eval split
    │   └── model_loader.py                         # HF + URI/path model loading
    ├── model_config/
    │   ├── dataset_config.py                       # DatasetConfig (Pydantic) — shuffle, filter, HN params
    │   ├── deepspeed_config.py                     # DeepspeedConfig (Pydantic) — ZeRO, offloading, precision
    │   ├── peft_config.py                          # PeftConfig (Pydantic) — LoRA parameters
    │   ├── reward_config.py                        # RewardConfig (Pydantic) — reward functions
    │   └── train_config.py                         # TrainingConfig (Pydantic) — full training params
    ├── plots/
    │   ├── plot_manager.py                         # Orchestrates all 9 diagnostic plots
    │   └── plot_func/
    │       ├── loss.py                             # Training loss curve
    │       ├── reward_margin.py                    # Chosen vs rejected reward gap
    │       ├── reward_accuracy.py                  # Preference prediction accuracy
    │       ├── log_ratio.py                        # Policy/ref log prob ratio
    │       ├── KL_divergence.py                    # KL divergence estimate
    │       ├── grad_norm.py                        # Gradient norm per step
    │       ├── lr_schedule.py                      # Learning rate schedule
    │       ├── batch_loss.py                       # Per-batch loss distribution
    │       └── throughput.py                       # Samples/sec, runtime, FLOPs
    ├── recipe/
    │   ├── recipe_loader.py                        # YAML → RecipeConfig
    │   └── recipe_config.py                        # Pydantic models (RecipeConfig, RecipeEntry)
    ├── shuffle/
    │   └── shuffler.py                             # Source-aware block shuffle (RANDOM / CIRCULAR)
    ├── system_prompt/
    │   └── assigner.py                             # ALL / ROUND_ROBIN / RANDOM
    ├── templates/
    │   ├── chat_type_mapping.yml                   # chat_type → template file mapping
    │   ├── chat_type_registry.py                   # Dynamic template loader + cache
    │   └── dpo/
    │       ├── input_schema_templates/
    │       │   └── input_schema.json
    │       ├── output_schema_templates/
    │       │   └── DPOTrainer_template.json
    │       └── template_functions/
    │           ├── instruct_dpo_apply_chat_template.py
    │           └── context_dpo_apply_chat_template.py
    ├── utils/
    │   ├── config_validator.py                     # load_config(), require_field(), resolve_config()
    │   └── filter.py                               # (legacy) filter_by_length
    └── docs/
        └── README.md                               # this file
```

---

## Dependencies

```
torch>=2.4.0,<2.5.0
transformers>=4.36.0,<4.46.0
trl>=0.7.0,<0.12.0
accelerate>=0.25.0
deepspeed>=0.12.0
datasets>=2.14.0
pyyaml
pydantic>=2.0.0
pandas>=2.0.0
pyarrow>=12.0.0
numpy<2
peft
python-dotenv
rich
rouge-score
scipy
matplotlib
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Config error, missing cache, invalid data, CUDA issue |
| `2` | Missing dependency |
