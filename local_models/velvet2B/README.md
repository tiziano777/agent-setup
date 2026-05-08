# Velvet-2B Local Inference Pipeline

**A scalable async inference client for local model serving via SGLang + OpenAI-compatible endpoints.**

Generate diverse inference data from datasets using configurable system prompts, temperatures, and replication strategies. Built for DPO (Direct Preference Optimization) and SFT (Supervised Fine-Tuning) dataset generation workflows.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Data Flow Pipeline](#data-flow-pipeline)
5. [Key Components](#key-components)
6. [Setup & Configuration](#setup--configuration)
7. [Usage](#usage)
8. [Data Schemas](#data-schemas)
9. [API & Endpoints](#api--endpoints)
10. [Troubleshooting](#troubleshooting)

---

## Overview

**velvet2B** is a production-ready async inference client designed to:

- **Load diverse datasets** (Parquet, JSONL, JSONL.gz) from distribution directories
- **Generate multiple inference variants** per sample (replicas × prompts × temperatures)
- **Execute async requests** against a local SGLang server via OpenAI-compatible `/v1/chat/completions`
- **Output raw inference records** in BASE schema (rolling JSONL files)
- **Aggregate results** using DuckDB into FINAL schema (rolling Parquet files)
- **Resume from checkpoints** transparently on interruptions (idempotent processing)

**Primary use case**: Generate preference pairs (positive/negative/candidate responses) for DPO training or augment existing datasets with synthetic data for SFT.

---

## Architecture

### Client-Server Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────────┐ │
│  │  async_client.py     │◄────────│  SGLang Server (GPU)     │ │
│  │  (Main Orchestrator) │         │  - Model: Velvet-2B      │ │
│  │                      │         │  - Port: 30000           │ │
│  │  - Load recipe YAML  │◄────────│ - OpenAI-compatible API  │ │
│  │  - Expand tasks      │         │                          │ │
│  │  - Async inference   │         │ HTTP /v1/chat/completions
│  │  - Write JSONL       │         │ (batched + prefix caching)
│  │  - Aggregate → DuckDB│         │                          │ │
│  └──────────────────────┘         └──────────────────────────┘ │
│        ▲                                       ▲                │
│        │                                       │                │
│   Input: Recipe YAML                  GPU Memory Optimized:    │
│   (r2_recipe.yaml)                    - KV-cache fp8           │
│   - Lists datasets & prompts          - Prefix caching enabled │
│   - Specifies chat_type               - Static mem allocation  │
│   - Defines replication factor        - Max context: 4096      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            └─► Output: Aggregated Results
                                - RAW: output/raw/{dist_name}/*.jsonl
                                - FINAL: output/aggregated/{dist_name}/*.parquet
```

### Two-Phase Processing

**Phase 1: Raw Inference** → BASE schema JSONL files
```
Recipe Entry
    ↓
Load Samples (from dist_uri)
    ↓
Expand Tasks (sample × replica × prompts × temperatures)
    ↓
Skip Checkpointed Tasks (resume capability)
    ↓
Async HTTP Requests to /v1/chat/completions
    ↓
Collect Responses (with metadata: temp, prompt_id, replica_idx)
    ↓
Write Rolling JSONL Files (max 100MB each by default)
```

**Phase 2: Aggregation** → FINAL schema Parquet files
```
Raw JSONL Files
    ↓
DuckDB: Group by _id_hash
    ↓
Collapse Mode Key (positive/negative/candidate) → array
    ↓
Write Rolling Parquet Files
    ↓
FINAL schema: [_id_hash, _distribution_name, positives/negatives/candidates[], ...]
```

---

## Directory Structure

```
local_models/velvet2B/
├── README.md                              # This file
├── server/
│   └── run_sglang_server.sh               # Shell script to launch SGLang server
│                                          # Sets GPU memory fraction, context length, optimizations
│
├── client/
│   ├── async_client.py                    # MAIN ENTRY POINT (async orchestrator)
│   ├── inference_config.yml               # Global configuration (API URL, batch size, etc.)
│   ├── r2_recipe.yaml                     # Example recipe with dataset entries
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   │
│   │   ├── schemas/                       # Data models & validation
│   │   │   ├── __init__.py
│   │   │   └── inference_schemas.py       # InferenceMode, ResponseItem, InferenceParams
│   │   │
│   │   ├── loader/                        # Data loading
│   │   │   ├── __init__.py
│   │   │   └── data_loader.py             # DataLoader: loads Parquet/JSONL/JSONL.gz
│   │   │
│   │   ├── recipe/                        # Recipe configuration & validation
│   │   │   ├── __init__.py
│   │   │   ├── recipe_config.py           # RecipeConfig, RecipeEntry dataclasses
│   │   │   └── recipe_loader.py           # RecipeLoader: parses YAML → RecipeConfig
│   │   │
│   │   ├── system_prompt/                 # System prompt assignment strategies
│   │   │   ├── __init__.py
│   │   │   └── assigner.py                # SystemPromptAssigner: all/round_robin/random
│   │   │
│   │   ├── templates/                     # Chat template registry & functions
│   │   │   ├── __init__.py
│   │   │   ├── chat_type_registry.py      # ChatTypeRegistry: lazy-loading template functions
│   │   │   ├── chat_type_mapping.yml      # Maps chat_type → template_fn + schema paths
│   │   │   └── dpo/
│   │   │       ├── __init__.py
│   │   │       ├── template_functions/    # Custom template functions per chat_type
│   │   │       └── input_schema_templates/
│   │   │           └── input_schema.json  # Example input schema for DPO
│   │   │
│   │   ├── writer/                        # Output writing
│   │   │   ├── __init__.py
│   │   │   └── writer.py                  # RollingJsonlWriter: size-based file rotation
│   │   │
│   │   └── aggregator/                    # Aggregation & parquet writing
│   │       ├── __init__.py
│   │       └── aggregator.py              # DuckDBAggregator: group by _id_hash → Parquet
│   │
│   └── .inference_venv/                   # Python virtual environment (auto-created)
│
└── output/                                # Generated during inference
    ├── raw/                               # Phase 1 output: rolling JSONL files
    │   └── {dist_name}/
    │       ├── inference_part1.jsonl
    │       ├── inference_part2.jsonl
    │       └── ...
    │
    └── aggregated/                        # Phase 2 output: rolling Parquet files
        └── {dist_name}/
            ├── aggregated_part1.parquet
            ├── aggregated_part2.parquet
            └── ...
```

---

## Data Flow Pipeline

### Step 1: Configuration Loading

```python
# inference_config.yml is loaded automatically
API_URL = "http://localhost:30000/v1/chat/completions"
RECIPE_PATH = "r2_recipe.yaml"
OUTPUT_BASE_DIR = "output/raw"
AGGREGATED_BASE_DIR = "output/aggregated"
TEMPERATURE_RANGE = [0.0, 0.2, 0.3, 0.4, 0.5]
CONCURRENT_REQUESTS = 32
SCHEMA_MODE = "negative"  # positive | negative | candidate
PROMPT_STRATEGY = "random"  # all | round_robin | random
```

### Step 2: Recipe Parsing

**Input**: `r2_recipe.yaml`

```yaml
entries:
  /path/to/dataset1:
    dist_id: "uuid-1"
    dist_name: "ARC-Challenge"
    dist_uri: "/path/to/dataset1"
    chat_type: "train_dpo"
    replica: 1
    samples: 2590
    system_prompt: ["p1", "p2"]
    system_prompt_name: ["system_1", "system_2"]
```

**Parsing**:
```
RecipeLoader.load(RECIPE_PATH)
    → RecipeConfig(entries: dict[str, RecipeEntry])
    → Each RecipeEntry validated via Pydantic
```

### Step 3: Sample Loading

```python
samples = DataLoader.load(entry.dist_uri)
# Supports: *.parquet, *.jsonl.gz, *.jsonl
# Returns: list[dict] with _id_hash field
```

### Step 4: Task Expansion

**Cartesian product**:
```
For each sample:
  For each replica (0 to entry.replica-1):
    For each system prompt (via assigner strategy):
      For each temperature in TEMPERATURE_RANGE:
        → InferenceTask(
            id_hash=sample["_id_hash"],
            messages=template_fn(sample, sys_prompt),
            temperature=temp,
            system_prompt_id=prompt_name,
            dist_name=entry.dist_name,
            mode=SCHEMA_MODE,  # positive/negative/candidate
            dist_id=entry.dist_id,
            dist_uri=entry.dist_uri,
            replica_idx=replica_idx,
          )
```

**Example**: 100 samples × 2 replicas × 2 prompts × 5 temperatures = **2,000 tasks**

### Step 5: Checkpoint & Resume

```python
done = _load_checkpoint(str(raw_dir))
# Scans existing JSONL files for (id_hash, temperature, prompt_id, replica_idx) tuples
pending = [t for t in all_tasks if (t.id_hash, t.temperature, t.system_prompt_id, t.replica_idx) not in done]
# Resume from checkpoint: skip already-written tasks
```

### Step 6: Async Inference

**Per task**:
```
1. Build payload:
   {
     "model": "velvet-2b",
     "messages": [{role: "system", content: "..."}, {role: "user", content: "..."}],
     "temperature": 0.3,
     "max_tokens": 512,
     "top_p": 0.95,
     "n": 1,
   }

2. POST to http://localhost:30000/v1/chat/completions

3. Retry logic:
   - Up to MAX_RETRIES (default: 3) on 5xx or network errors
   - Exponential backoff: sleep = BACKOFF_FACTOR * 2^attempt
   - Timeout per request: 600 seconds

4. Parse response:
   {
     "choices": [
       {
         "message": {
           "content": "generated text..."
         }
       }
     ]
   }
```

**Concurrency**: `asyncio.Semaphore(CONCURRENT_REQUESTS=32)` limits parallel requests.

### Step 7: BASE Schema Record Writing

**Per successful inference**:
```python
# ResponseItem wraps the model output
item = ResponseItem(
    content="generated response",
    score=0.0,
    think=None,
    context=None,
    inference_params=InferenceParams(
        model_id="velvet-2b",
        temperature=0.3,
        top_p=0.95,
        system_prompt_id="system_1",
    ),
)

# BASE schema record (written to JSONL)
record = {
    "_id_hash": "abc123def456",
    "_distribution_name": "ARC-Challenge",
    "_distribution_id": "uuid-1",
    "_distribution_uri": "/path/to/dataset1",
    "_replica_idx": 0,
    "_choice_idx": 0,
    "negative": {  # or "positive" / "candidate" depending on SCHEMA_MODE
        "content": "generated response",
        "score": 0.0,
        "think": null,
        "context": null,
        "inference_params": {
            "model_id": "velvet-2b",
            "temperature": 0.3,
            "top_p": 0.95,
            "system_prompt_id": "system_1",
        },
    },
}

# Written to rolling JSONL (rotates at MAX_FILE_SIZE_MB=100)
writer.write(record)
```

### Step 8: Aggregation (DuckDB)

**Read all raw JSONL files** for a distribution:
```sql
SELECT * FROM read_json_auto([
  'output/raw/ARC-Challenge/inference_part1.jsonl',
  'output/raw/ARC-Challenge/inference_part2.jsonl',
  ...
])
```

**Group and collapse**:
```sql
SELECT
    _id_hash,
    _distribution_name,
    _distribution_id,
    _distribution_uri,
    list(negative) AS negatives  -- Collects all negative responses per sample
FROM raw
GROUP BY _id_hash, _distribution_name
```

**Output**: Writing rolling Parquet files to `output/aggregated/ARC-Challenge/`

**FINAL schema record**:
```python
{
    "_id_hash": "abc123def456",
    "_distribution_name": "ARC-Challenge",
    "_distribution_id": "uuid-1",
    "_distribution_uri": "/path/to/dataset1",
    "negatives": [
        {
            "content": "response 1 (temp=0.0, prompt=p1)",
            "score": 0.0,
            "inference_params": {...},
        },
        {
            "content": "response 2 (temp=0.2, prompt=p1)",
            "score": 0.0,
            "inference_params": {...},
        },
        ...
    ],
}
```

---

## Key Components

### 1. `async_client.py` (Main Orchestrator)

**Entry Point**: `asyncio.run(main())`

**Main Flow**:
```python
async def main():
    recipe = RecipeLoader.load(RECIPE_PATH)  # Parse recipe YAML

    for entry in recipe.entries:
        await _process_entry(
            entry, SCHEMA_MODE, assigner, registry,
            output_base, agg_base
        )

async def _process_entry(entry):
    # 1. Load samples
    samples = DataLoader.load(entry.dist_uri)

    # 2. Build tasks (expand into variants)
    all_tasks = _build_tasks(samples, entry, mode, TEMPERATURE_RANGE, ...)

    # 3. Load checkpoint (skip completed tasks)
    done = _load_checkpoint(str(raw_dir))
    pending = [t for t in all_tasks if (t.id_hash, ...) not in done]

    # 4. Async inference (up to CONCURRENT_REQUESTS in parallel)
    async with aiohttp.ClientSession() as session:
        coros = [_infer(sem, session, t) for t in pending]
        for coro in tqdm.asyncio.as_completed(coros):
            records = await coro
            for record in records:
                writer.write(record)

    # 5. Aggregate with DuckDB
    aggregator = DuckDBAggregator(mode=mode.value)
    aggregator.aggregate_and_write(jsonl_files, agg_dir)
```

### 2. `DataLoader` (Data Input)

**Supports**:
- Parquet files (pandas `read_parquet`)
- JSONL files (pandas `read_json(..., lines=True)`)
- JSONL.gz files (gzip-compressed JSONL)

**Algorithm**:
```python
@staticmethod
def load(dist_uri: str) -> list[dict]:
    path = Path(dist_uri)
    for pattern, reader in [("*.parquet", ...), ("*.jsonl.gz", ...), ("*.jsonl", ...)]:
        files = sorted(path.glob(pattern))
        if files:
            df = pd.concat([reader(f) for f in files], ignore_index=True)
            return df.to_dict("records")  # list[dict]
    raise FileNotFoundError(f"No data files in {dist_uri}")
```

**Input Schema**:
Each record MUST have:
- `_id_hash`: str (unique sample identifier)
- All fields required by the template function for the specified `chat_type`

### 3. `SystemPromptAssigner` (Prompt Strategy)

**Strategies**:

| Strategy | Behavior |
|----------|----------|
| `all` | Each sample paired with EVERY prompt (Cartesian product) |
| `round_robin` | Sample at index i gets prompt i % len(prompts) |
| `random` | Each sample gets a uniformly random prompt |

**Example**:
```python
assigner = SystemPromptAssigner(strategy="random")
assigned = assigner.assign(sample, prompts=["p1", "p2"], prompt_names=["sys1", "sys2"])
# Returns: [(sample, "p2", "sys2")]  # One random prompt assigned
```

### 4. `ChatTypeRegistry` (Template Functions)

**Purpose**: Map `chat_type` strings to template functions that extract fields from samples and format messages for the LLM.

**Configuration** (`chat_type_mapping.yml`):
```yaml
train_dpo:
  template_fn: /path/to/modules/templates/dpo/template_functions/dpo_template.py
  schema: /path/to/modules/templates/dpo/input_schema_templates/input_schema.json
```

**Template Function Signature**:
```python
def apply_chat_template(sample: dict, system_prompt: str | None) -> list[dict]:
    """
    Extract fields from sample and build message list.

    Returns:
        [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": sample["prompt"]},
            ...
        ]
    """
```

**Lazy Loading**:
- Templates are imported on-demand and cached
- Errors during import are caught and logged with full context

### 5. `RollingJsonlWriter` (Output Buffering)

**Purpose**: Write records to disk, rotating files when size threshold is exceeded.

**Algorithm**:
```python
writer = RollingJsonlWriter(directory, "inference", max_mb=100)

for record in records:
    if os.path.getsize(current_file) > max_bytes:
        close()
        open_next_part()  # Part 1, 2, 3, ...

    write(json.dumps(record) + "\n")
    flush()
```

**Benefits**:
- Streaming write (no in-memory accumulation)
- Auto-rotation prevents single-file size explosion
- Resumable: checkpoint tracks task completion, not file position

### 6. `DuckDBAggregator` (Aggregation & Finalization)

**Purpose**: Read raw JSONL records, group by `_id_hash`, collapse mode key into an array, write Parquet.

**Algorithm**:
```python
aggregator = DuckDBAggregator(mode="negative", max_mb=100)

con = duckdb.connect()
con.execute(f"CREATE TABLE raw AS SELECT * FROM read_json_auto({jsonl_files})")

cursor = con.execute(f"""
    SELECT
        _id_hash,
        _distribution_name,
        _distribution_id,
        _distribution_uri,
        list(negative) AS negatives  -- Collapse into array
    FROM raw
    GROUP BY _id_hash, _distribution_name
""")

# Stream results and write rolling Parquet files
for row in cursor.fetchall():
    batch_rows.append(dict(zip(columns, row)))
    if len(batch_rows) * 512 >= max_bytes:
        write_parquet(batch_rows, f"aggregated_part{i}.parquet")
        batch_rows = []
```

**Output Rolling Parquet**:
- Each Parquet file: ~100MB (configurable)
- Compression: snappy
- Schema: pyarrow auto-inferred from collapsed records

---

## Setup & Configuration

### 1. Server Setup (SGLang)

**Install SGLang** (on your training machine with GPU):
```bash
pip install sglang[all]
```

**Launch Server**:
```bash
cd local_models/velvet2B/server
bash run_sglang_server.sh
```

**Script Details** (`run_sglang_server.sh`):
- Sets `MODEL_PATH` to your Velvet-2B checkpoint
- Allocates 95% of VRAM (e.g., 76GB on 80GB GPU)
- Context length: 4096 (prompt 2000 + generation 2000)
- KV-cache: fp8 (doubles density)
- Prefix caching: enabled (skips redundant prefills)
- Listen: `0.0.0.0:30000`

**Verify Server**:
```bash
curl http://localhost:30000/v1/models
# Returns: {"object": "list", "data": [{"id": "velvet-2b", ...}]}
```

### 2. Client Setup

**Create Virtual Environment**:
```bash
cd local_models/velvet2B/client
python3.10 -m venv .inference_venv
source .inference_venv/bin/activate
pip install -r requirements.txt  # Or install manually:
# pip install aiohttp pyyaml pandas duckdb pyarrow tqdm
```

**Configuration** (`inference_config.yml`):
```yaml
# --- Server ---
API_URL: "http://localhost:30000/v1/chat/completions"
MODEL_ID: "velvet-2b"
MAX_NEW_TOKENS: 512
TOP_P: 0.95
MAX_RETRIES: 3
BACKOFF_FACTOR: 0.5

# --- Input ---
RECIPE_PATH: "r2_recipe.yaml"

# --- Output ---
OUTPUT_BASE_DIR: "output/raw"
AGGREGATED_OUTPUT_DIR: "output/aggregated"
MAX_FILE_SIZE_MB: 100

# --- Inference ---
TEMPERATURE_RANGE: [0.0, 0.2, 0.3, 0.4, 0.5]
N: 1  # Completions per request
CONCURRENT_REQUESTS: 32
SCHEMA_MODE: "negative"  # positive | negative | candidate
PROMPT_STRATEGY: "random"  # all | round_robin | random
LOGPROBS: false
```

---

## Usage

### Basic Workflow

**1. Prepare Recipe YAML** (`r2_recipe.yaml`):
```yaml
name: r2
description: DPO dataset generation
scope: continual_ft
entries:
  /path/to/dataset1:
    dist_id: "uuid-1"
    dist_name: "ARC-Challenge"
    dist_uri: "/path/to/dataset1"
    chat_type: "train_dpo"
    replica: 1
    samples: 2590
    system_prompt: ["p1"]
    system_prompt_name: ["system_1"]
```

**2. Ensure SGLang Server is Running**:
```bash
# In a separate terminal
cd local_models/velvet2B/server
bash run_sglang_server.sh
# Wait for: "INFO: Uvicorn running on http://0.0.0.0:30000"
```

**3. Run Client**:
```bash
cd local_models/velvet2B/client
source .inference_venv/bin/activate
python async_client.py
```

**Console Output**:
```
2026-04-22 10:30:45 INFO Recipe: r2 (1 entries)
2026-04-22 10:30:45 INFO Loaded chat type registry: ['train_dpo'] | endpoint=http://localhost:30000/v1/chat/completions | mode=negative
2026-04-22 10:30:45 INFO === Processing entry: ARC-Challenge (chat_type=train_dpo) ===
2026-04-22 10:30:46 INFO [ARC-Challenge] Loading samples from /path/to/dataset1
2026-04-22 10:30:47 INFO [ARC-Challenge] 2590 samples loaded (replica=1)
2026-04-22 10:30:47 INFO [ARC-Challenge] 12950 total tasks (samples=2590 × replica=1 × prompts × temperatures)
2026-04-22 10:30:47 INFO [ARC-Challenge] Checkpoint: 0 done, 12950 pending
100%|██████████| 12950/12950 [2:35:14<00:00, 1.38it/s]
2026-04-22 13:06:02 INFO [ARC-Challenge] Aggregating 2 JSONL files with DuckDB → output/aggregated/ARC-Challenge
2026-04-22 13:06:05 INFO [ARC-Challenge] Wrote 1 Parquet file(s) to output/aggregated/ARC-Challenge
2026-04-22 13:06:05 INFO All entries processed.
```

### Resume from Checkpoint

If the client is interrupted:
```
KeyboardInterrupt: Ctrl+C pressed
# Partial records have been written to JSONL
# Re-run client:
python async_client.py
# It will:
# 1. Scan output/raw/{dist_name}/*.jsonl for completed tasks
# 2. Skip them (not re-infer)
# 3. Only process pending tasks
```

### Verify Output

**Raw output** (intermediate):
```bash
ls -lh output/raw/ARC-Challenge/
# -rw-r--r-- inference_part1.jsonl (100MB)
# -rw-r--r-- inference_part2.jsonl (100MB)

head -1 output/raw/ARC-Challenge/inference_part1.jsonl | jq .
# {
#   "_id_hash": "abc123",
#   "_distribution_name": "ARC-Challenge",
#   "_distribution_id": "uuid-1",
#   "_distribution_uri": "/path/to/dataset1",
#   "_replica_idx": 0,
#   "_choice_idx": 0,
#   "negative": {
#     "content": "response text",
#     "score": 0.0,
#     "inference_params": {...}
#   }
# }
```

**Aggregated output** (final):
```bash
ls -lh output/aggregated/ARC-Challenge/
# -rw-r--r-- aggregated_part1.parquet (100MB)

python3 << 'EOF'
import pandas as pd
df = pd.read_parquet("output/aggregated/ARC-Challenge/aggregated_part1.parquet")
print(df.head())
print(df.info())
print(f"Loaded {len(df)} unique samples (by _id_hash)")
# Shows:
# _id_hash | _distribution_name | _distribution_id | _distribution_uri | negatives
# Each row has N responses in the negatives array
EOF
```

---

## Data Schemas

### BASE Schema (Raw JSONL)

**Purpose**: Intermediate format, one record per (id_hash, temperature, prompt_id, replica_idx).

**Structure**:
```json
{
  "_id_hash": "sample_unique_id",
  "_distribution_name": "ARC-Challenge",
  "_distribution_id": "uuid-1",
  "_distribution_uri": "/path/to/dataset",
  "_replica_idx": 0,
  "_choice_idx": 0,
  "negative": {
    "content": "model generated response",
    "score": 0.0,
    "think": null,
    "context": null,
    "inference_params": {
      "model_id": "velvet-2b",
      "temperature": 0.3,
      "top_p": 0.95,
      "top_k": null,
      "system_prompt_id": "system_1"
    }
  }
}
```

**Metadata Keys** (never used as mode keys):
- `_id_hash`: Sample identifier
- `_distribution_name`: Dataset name
- `_distribution_id`: Dataset UUID
- `_distribution_uri`: Dataset path
- `_replica_idx`: Which replica (0-based)
- `_choice_idx`: Which choice when N > 1

**Mode Key** (one of):
- `positive`: Preferred response
- `negative`: Dispreferred response
- `candidate`: Alternative response

### FINAL Schema (Aggregated Parquet)

**Purpose**: Production-ready dataset with all responses per unique sample.

**Structure**:
```json
{
  "_id_hash": "sample_unique_id",
  "_distribution_name": "ARC-Challenge",
  "_distribution_id": "uuid-1",
  "_distribution_uri": "/path/to/dataset",
  "negatives": [
    {
      "content": "response 1 (temp=0.0, prompt=system_1)",
      "score": 0.0,
      "inference_params": {...}
    },
    {
      "content": "response 2 (temp=0.2, prompt=system_1)",
      "score": 0.0,
      "inference_params": {...}
    },
    ...
  ]
}
```

**Transformation Logic**:
```sql
GROUP BY _id_hash, _distribution_name
→ list(negative) AS negatives  -- Collect all responses into array
```

**Result**: Each original sample now has all its generated variants in a single FINAL record.

---

## API & Endpoints

### SGLang Server

**Endpoint**: `http://localhost:30000/v1/chat/completions`

**OpenAI-Compatible Request**:
```json
{
  "model": "velvet-2b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 0.95,
  "n": 1,
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0
}
```

**Response**:
```json
{
  "object": "text_completion",
  "model": "velvet-2b",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "2+2 equals 4."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

**Error Handling**:
- `500`: Server error → retry with exponential backoff
- `400`: Invalid request → skip task, log error
- `timeout`: Network timeout → retry
- `ConnectionError`: Server down → retry

---

## Troubleshooting

### Issue: "Connection refused" on port 30000

**Cause**: SGLang server not running.

**Solution**:
```bash
cd local_models/velvet2B/server
bash run_sglang_server.sh
# Wait for: "INFO: Uvicorn running on http://0.0.0.0:30000"
```

### Issue: No data files found in dist_uri

**Cause**: Path doesn't exist or wrong format.

**Solution**:
1. Verify path in recipe YAML:
   ```bash
   ls -lh /path/to/dataset1/
   # Should show *.parquet, *.jsonl, or *.jsonl.gz
   ```

2. Check supported formats:
   ```python
   from modules.loader.data_loader import DataLoader
   samples = DataLoader.load("/path/to/dataset1")
   # Supported: *.parquet > *.jsonl.gz > *.jsonl
   ```

### Issue: "Unknown chat_type 'train_dpo'"

**Cause**: Chat type not defined in mapping.

**Solution**:
1. Check mapping file:
   ```bash
   cat local_models/velvet2B/client/modules/templates/chat_type_mapping.yml
   ```

2. Add missing entry:
   ```yaml
   train_dpo:
     template_fn: /absolute/path/to/dpo_template.py
     schema: /absolute/path/to/input_schema.json
   ```

3. Ensure template function exists:
   ```python
   def apply_chat_template(sample: dict, system_prompt: str | None) -> list[dict]:
       # Extract fields from sample and build messages
       return [
           {"role": "system", "content": system_prompt or ""},
           {"role": "user", "content": sample["prompt"]},
       ]
   ```

### Issue: OutOfMemory error on GPU

**Cause**: KV-cache too large or insufficient static allocation.

**Solution** (edit `run_sglang_server.sh`):
```bash
# Increase mem-fraction if you have headroom:
MEM_FRACTION=0.98  # Default: 0.95

# OR reduce context length:
CONTEXT_LEN=2048  # Default: 4096

# OR add eager mode (disables CUDA graphs):
--enforce-eager
```

### Issue: Slow inference (<1 req/sec)

**Cause**: Low concurrency, small model, or prefix caching disabled.

**Solution**:
1. Increase concurrency:
   ```yaml
   CONCURRENT_REQUESTS: 64  # Default: 32
   ```

2. Enable prefix caching (in `run_sglang_server.sh`):
   ```bash
   --enable-prefix-caching  # Already enabled
   ```

3. Reduce max_tokens if possible:
   ```yaml
   MAX_NEW_TOKENS: 256  # Default: 512
   ```

### Issue: Incomplete or corrupted JSONL files

**Cause**: Partial writes on crash.

**Solution**:
1. Delete incomplete files:
   ```bash
   rm output/raw/{dist_name}/*.jsonl
   ```

2. Re-run client (checkpoint is clean):
   ```bash
   python async_client.py
   ```

### Issue: DuckDB aggregation fails

**Cause**: Malformed JSONL or missing required fields.

**Solution**:
1. Validate a sample record:
   ```bash
   head -1 output/raw/{dist_name}/*.jsonl | jq .
   # Should have: _id_hash, _distribution_name, mode key (negative/positive/candidate)
   ```

2. Check DuckDB error log:
   ```python
   import duckdb
   con = duckdb.connect()
   con.execute("CREATE TABLE raw AS SELECT * FROM read_json_auto(['file.jsonl'])")
   # If this fails, JSONL is malformed
   ```

---

## Advanced: Custom Configurations

### High-Concurrency Setup

For powerful machines:
```yaml
# inference_config.yml
CONCURRENT_REQUESTS: 128  # Instead of 32
MAX_FILE_SIZE_MB: 200     # Larger rolling files
TEMPERATURE_RANGE: [0.0, 0.5, 1.0, 1.5, 2.0]  # More diversity
N: 3  # Multiple completions per request (each becomes separate record)
```

### Multi-Prompt Cartesian Product

For all-vs-all comparisons (e.g., DPO):
```yaml
PROMPT_STRATEGY: "all"  # Instead of "random"
```

With recipe:
```yaml
system_prompt: ["p1", "p2", "p3"]
system_prompt_name: ["system_1", "system_2", "system_3"]
```

**Expansion**: 100 samples × 3 prompts × 5 temperatures = **1,500 tasks**

### Custom Output Directory

```yaml
OUTPUT_BASE_DIR: "/mnt/fast-disk/raw"
AGGREGATED_OUTPUT_DIR: "/mnt/fast-disk/aggregated"
```

---

## Performance Benchmarks

**Hardware**: A100 GPU (80GB VRAM)
**Model**: Velvet-2B model

| Setting | Throughput | Time ( n samples) |
|---------|-----------|-------------------|
| CONCURRENT=<>, N_TEMP=5 values | ~N req/sec | ~ <X> h <x> min |
| CONCURRENT=<>, N_TEMP=5 values | ~N req/sec | ~ h min |
| CONCURRENT=<>, N_TEMP=5 values | ~N req/sec | ~ min |

---

## Summary

**velvet2B** pipeline:
1. **Load** datasets from dist_uri (Parquet/JSONL)
2. **Expand** into task combinations (replica × prompt × temperature)
3. **Resume** from checkpoints (idempotent)
4. **Infer** async against SGLang server
5. **Write** BASE schema to rolling JSONL
6. **Aggregate** using DuckDB into FINAL schema Parquet
7. **Output** ready for DPO training or SFT data augmentation

All phases are observable, resumable, and production-grade.

---

**For more details**, see component docstrings in `modules/` subdirectories.

