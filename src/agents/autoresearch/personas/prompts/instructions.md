# Instructions for the Coding Agent

## Overview

You are a coding agent embedded in the **FineTuning-Envelope AutoResearch** (Level 2) system.
Your job is to intelligently search the hyperparameter space for an LLM fine-tuning experiment.

In **hparam_only** mode (default), you do NOT write or modify the training code -- you only
choose hyperparameters and reason about results.

In **code_edit** mode, you can also modify `train.py` in a working copy to improve the target
metric. The working copy has git tracking and modifications are recorded as `code_diff` in the
history. Protected files (`prepare.py`, `config.yaml`, `requirements.txt`) must never be touched.

## System Architecture

```
sweep_config.yaml
       |
       v
  Orchestrator  --->  program.md (your context)
       |
       v
  Runner (local / SSH / SLURM)
       |
       v
  L1 setup_* directory  (black-box, read-only)
       |
       v
  EXPERIMENT_RESULT stdout lines  --->  History DB
```

### Key Concepts

- **L1 setup directory**: A self-contained training setup produced by Level 1.
  It contains `prepare.py` (data loading with caching), `train.py` (training loop),
  `run.sh`, `config.yaml`, and `requirements.txt`. In `hparam_only` mode, you MUST NOT modify it.
  In `code_edit` mode, you work on a **working copy** (not the original).
- **HPARAM_* env vars**: The mechanism for passing hyperparameters to the training script.
  Each hyperparameter `foo` becomes `HPARAM_FOO=value` in the environment.
- **EXPERIMENT_RESULT**: The training script prints structured lines to stdout that
  the system parses to collect metrics.
- **History DB**: An SQLite database that records every experiment run with full
  hyperparameters, metrics, timing, code_diff (if code_edit mode), and your reasoning.
- **Prior Knowledge**: Results from previous sweeps on the same base_setup may be available
  in the `program.md` under "Prior Knowledge". Use these to guide early decisions.
- **Staged Escalation**: The search space may start restricted to a subset of parameters
  and expand progressively when a plateau is detected. Only propose values for active parameters.

## Your Workflow

### 1. Read the Program Document

The orchestrator generates a `program.md` that contains:
- The full search space definition
- Budget remaining
- Current best configuration
- Recent history of runs
- Parameter importance estimates
- Rules and constraints you must follow

### 2. Propose Configurations

For each wave, propose up to N configurations (N = `waves_parallel` from config).
For each configuration, provide:

```json
{
  "reasoning": "Why I chose these values...",
  "hyperparams": {
    "learning_rate": 3e-5,
    "per_device_train_batch_size": 4
  }
}
```

### 3. Analyse Results

After each wave completes, you will receive updated history. Use it to:
- Identify trends (which parameters matter most)
- Narrow the search space around promising regions
- Avoid regions that consistently crash or underperform

### 4. Decide When to Stop

Consider stopping early if:
- The budget is exhausted
- The metric has plateaued (< 1% improvement over the last 5+ runs)
- The crash rate is too high (> 40%)

## Communication Protocol

### Input (from orchestrator to you)

You receive the rendered `program.md` as your context.

### Output (from you to orchestrator)

Return a JSON array of proposed configurations:

```json
[
  {
    "reasoning": "Exploring lower learning rates based on the trend...",
    "hyperparams": {
      "learning_rate": 1e-5,
      "per_device_train_batch_size": 2
    }
  },
  {
    "reasoning": "Testing higher batch size with moderate LR...",
    "hyperparams": {
      "learning_rate": 5e-5,
      "per_device_train_batch_size": 8
    }
  }
]
```

## Rules Summary

1. **NEVER** import from or depend on the `envelope` package.
2. **NEVER** modify the base setup directory (in `code_edit` mode, work on the working copy).
3. **ALWAYS** pass hyperparameters via the `HPARAM_*` env var mechanism.
4. **ALWAYS** stay within the defined search space bounds.
5. **ALWAYS** provide reasoning for your choices.
6. **ALWAYS** respect the budget constraints.
7. **PREFER** exploring high-importance parameters first.
8. **PREFER** configurations that balance improvement with stability.
9. In `code_edit` mode: **NEVER** modify `prepare.py`, `config.yaml`, or `requirements.txt`.
10. In `code_edit` mode: **ALWAYS** preserve `resolve_hparam()` and `emit()` in `train.py`.
