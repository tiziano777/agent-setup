

<!-- GSD:project-start source:PROJECT.md -->
## Project

**DPO Setup — Direct Preference Optimization Training Pipeline**

**dpo-setup** is a modular, recipe-driven DPO training system. Converts data sources → training cache → DPOTrainer.

**Core Value**: **Pluggable templates, multi-strategy prompt assignment, strict validation.** High modularity: add chat types without modifying core pipeline. Flexible prompt selection: cartesian product, round-robin, or seeded random.

### Constraints

- Python 3.10+
- Linux/macOS (CUDA optional, works on CPU)
- Recipe YAML validation required (Pydantic)
- Chat templates must be Python files with `apply_chat_template()` export

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+

## Runtime & Package Management
- pip (requirements.txt)

## Core Framework Dependencies
- `torch>=2.4.0,<2.5.0` — Deep learning backend
- `transformers>=4.36.0,<4.46.0` — HuggingFace model loading
- `trl>=0.7.0,<0.12.0` — DPOTrainer, DPOConfig
- `accelerate>=0.25.0` — Multi-GPU/device support
- `deepspeed>=0.12.0` — Zero optimization
- `datasets>=2.14.0` — Arrow-backed dataset handling
- `pydantic>=2.0.0` — Config validation
- `pandas>=2.0.0` — Data frame ops
- `pyarrow>=12.0.0` — Parquet/IPC support
- `numpy<2` — Numerical arrays
- `pyyaml` — Recipe YAML parsing

## Optional Dependencies
- None (all core deps required for training)

## Build & Development Tools
- No build system required (pure Python)

## Configuration & Secrets
- `config.yml` — Main config (model, recipe, training, output, hardware)
- `modules/templates/chat_type_mapping.yml` — Chat type → template function mapping
- Recipe files in user's chosen format (YAML, passed via config)
- Environment: CUDA auto-detected via `torch.cuda.is_available()`

## Settings Dataclasses
- `RecipeConfig` — Full recipe metadata + entries dict (Pydantic)
- `RecipeEntry` — Per-distribution metadata (chat_type, dist_uri, replica, system_prompt, etc.)

## Deployment & Containerization
- Docker images: Use base `pytorch/pytorch:2.4.0-cuda12.1-devel-ubuntu22.04` (example)
- No containerfile included (user-configurable)

## Platform Requirements
- Linux/macOS
- CUDA 12.1+ (for GPU), CPU fallback supported
- 40GB+ RAM recommended
- GPU: 16GB+ VRAM (for bfloat16 training, batch_size=1)

## Installation & Project Setup

```bash
pip install -r requirements.txt
```

Verify:
```bash
python -c "from trl import DPOTrainer; print('OK')"
```

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
- Line length: **88 characters** (natural for Python)
- Error codes: E (PEP8), F (PyFlakes), W (warnings)
- Target: Python 3.10+
- No auto-formatter enforced (ruff available)
- Applied to `modules/` entire directory

## Naming Patterns
- Modules: `snake_case` (e.g., `data_loader.py`, `assigner.py`)
- Classes: `PascalCase` (e.g., `ChatTypeRegistry`, `SystemPromptAssigner`, `RecipeLoader`)
- Test files: `test_*.py` prefix
- Function names: `snake_case` (e.g., `apply_chat_template()`, `load()`, `assign()`)
- Private/internal helpers: `_leading_underscore()` (e.g., `_select_by_temperature()`)
- Constants: `UPPER_CASE` (e.g., `FIXED_SEED`)
- Dictionary keys: `snake_case` (e.g., `prompt`, `chosen`, `rejected`, `_source_uri`)
- Type hints: Inline, modern syntax (`list[dict]`, `dict[str, Any]`, `str | None`)

## Import Organization
- Absolute imports from project root (no relative imports)
- Standard lib → third-party → local: `from modules.recipe import RecipeLoader`
- Lazy imports for expensive modules (e.g., torch inside functions when optional)

## Type Hints
- Use `|` for unions (Python 3.10+ style)
- Use `list[dict]`, `dict[str, Any]` (lower case generics)
- Optional: `str | None` (not `Optional[str]`)
- Pydantic models for config (see `RecipeConfig`, `RecipeEntry`)

## Error Handling
- Fail early with `require_field(config, ...)` for config validation
- Raise with context: `ValueError(f"Sample {id_hash}: ...")`
- Never silently skip invalid data
- Log at appropriate level: `logger.info()` for success, `logger.warning()` for skips, `logger.error()` for failures

## Docstrings
- One-line summary
- Optional extended description (blank line, then details)
- Document Args and Returns where applicable
- Triple quotes `"""`
- No type hints in docstring (already in signature)

## Factory Functions
- Use `ChatTypeRegistry.get_template_fn(chat_type)` for lazy template loading
- `RecipeLoader.load(path)` for YAML parsing
- `DataLoader.load(dist_uri)` for auto-detect file loading

## Logging
- Use `logger = logging.getLogger(__name__)` at module level
- Include context: `f"Loaded {len(data)} samples from {uri}"`
- Log at `info` level for major pipeline milestones
- Log at `warning` level for skipped samples
- Log at `error` level for exceptions

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
Recipe-driven data pipeline. User defines YAML with data sources + chat types + system prompts → prepare.py orchestrates loading, templating, prompting → JSONL cache → train.py feeds DPOTrainer.

## Layers
- **Config Layer** (`config.yml`) — Top-level system config, recipe path, output paths
- **Recipe Layer** (user YAML) — Entry definitions: distributions, replicas, system prompts
- **Data Layer** (`DataLoader`) — Format auto-detection, concatenation
- **Transform Layer** (`SystemPromptAssigner`, `ChatTypeRegistry`) — Prompt assignment, template function selection
- **Template Layer** (pluggable .py files) — Domain-specific sample → {prompt, chosen, rejected} conversion
- **Cache Layer** (JSONL) — Intermediate format, dataset validation
- **Training Layer** (`train.py`, `DPOTrainer`) — Model loading, training execution

## Data Flow
```
config.yml + recipe.yml
    ↓
RecipeLoader (YAML → Pydantic)
    ↓
RecipeConfig {entries: ...}
    ↓
prepare.py loop: for each entry:
    ↓
DataLoader (auto-detect format)
    ↓
list[dict] samples
    ↓
Replicate N times (replica field)
    ↓
SystemPromptAssigner (ALL/ROUND_ROBIN/RANDOM)
    ↓
(sample, prompt_content, prompt_id) tuples
    ↓
ChatTypeRegistry.get_template_fn()
    ↓
apply_chat_template(sample, prompt, temperature)
    ↓
{prompt, chosen, rejected, metadata}
    ↓
JSONL write (.cache/)
    ↓
train.py: load cache + CUDA check
    ↓
DPOTrainer.train()
```

## Key Abstractions
- **RecipeConfig** — Validates full recipe + all entries via Pydantic. Non-blocking metadata (id, name, description, scope, tags, derived_from).
- **ChatTypeRegistry** — Dynamic import + caching. One YAML file maps chat_type → template .py path. No hardcoding.
- **SystemPromptAssigner** — Strategy pattern (ALL/ROUND_ROBIN/RANDOM). Decouples prompt selection from pipeline.
- **DataLoader** — Format auto-detection. Single interface for parquet/jsonl.gz/jsonl. User sees no format differences.
- **Template Function** — Pure function: (sample, system_prompt, temperature) → dict. No state, no side effects.

## Entry Points
- `prepare.py` — CLI entry point, calls `prepare(config_path, strategy)` → writes cache
- `train.py` — CLI entry point, calls `preflight(config_path)` → DPOTrainer initialization

## Multi-Chat-Type Support
One recipe can mix multiple chat types (e.g., `train_dpo` + `train_sft`):
```yaml
entries:
  /data/a:
    chat_type: train_dpo
    ...
  /data/b:
    chat_type: custom_format
    ...
```
Each entry dynamically loads its own template function → handles format-specific preprocessing.

## Metadata Preservation
Every sample exits pipeline with:
- `_source_uri` — original data source
- `_replica` — which replication iteration (0 to replica-1)
- `_system_prompt_id` — which system prompt was assigned
- `_id_hash` — deduplication key (from original sample or generated)

Enables tracing, dedup, per-source metrics.

## Validation Strategy
- **Config level** — `require_field()` enforces strict nested key access. Missing/None → early error.
- **Recipe level** — Pydantic `RecipeConfig` + `RecipeEntry` validation (type checking, range validation).
- **Sample level** — Template function raises `ValueError` with sample ID on missing/malformed fields.
- **Dataset level** — train.py checks required columns (`prompt`, `chosen`, `rejected`) after cache load.

Error propagation: skip invalid sample + log warning → continue processing (non-blocking for individual samples, blocking for config/system).

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| skypilot | "Use when launching cloud VMs, Kubernetes pods, or Slurm jobs for GPU/TPU/CPU workloads, training or fine-tuning models on cloud GPUs, deploying inference servers (vllm, TGI, etc.) with autoscaling, writing or debugging SkyPilot task YAML files, using spot/preemptible instances for cost savings, comparing GPU prices across clouds, managing compute across 25+ clouds, Kubernetes, Slurm, and on-prem clusters with failover between them, troubleshooting resource availability or SkyPilot errors, or optimizing cost and GPU availability." | `.claude/skills/skypilot/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
