"""Pytest suite for PlotManager and individual plot functions.

Run from project root:
    pytest modules/plots/plot_func/_test_plots.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path

# ensure project root is in sys.path when invoked directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import pytest
import yaml

from modules.plots.plot_func._utils          import rolling_mean
from modules.plots.plot_func.batch_loss      import plot_batch_loss
from modules.plots.plot_func.loss            import plot_loss
from modules.plots.plot_func.lr_schedule     import plot_lr_schedule
from modules.plots.plot_func.reward_margin   import plot_reward_margin
from modules.plots.plot_func.reward_accuracy import plot_reward_accuracy
from modules.plots.plot_func.log_ratio       import plot_log_ratio
from modules.plots.plot_func.KL_divergence   import plot_kl_divergence
from modules.plots.plot_func.grad_norm       import plot_grad_norm
from modules.plots.plot_func.throughput      import plot_throughput
from modules.plots.plot_manager              import PlotManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path: Path) -> str:
    cfg = {"experiment": {"experiment_name": "test-synthetic"}}
    p = tmp_path / "config.yml"
    p.write_text(yaml.dump(cfg))
    return str(p)


def _make_synthetic_log_history(n_log: int = 20, logging_steps: int = 10) -> list:
    """Realistic synthetic DPOTrainer log_history (fixed seed for reproducibility)."""
    np.random.seed(42)
    steps    = [i * logging_steps for i in range(1, n_log + 1)]
    progress = np.linspace(0.0, 1.0, n_log)
    n_steps  = steps[-1]

    entries = []
    for step, p in zip(steps, progress):
        epoch = round(float(3.0 * p), 4)
        loss  = float(max(0.05, 1.8 * np.exp(-3 * p) + 0.25 + np.random.normal(0, 0.06)))
        warmup_end = n_steps * 0.2
        if step <= warmup_end:
            lr = 1e-5 * step / warmup_end
        else:
            lr = 1e-5 * max(0.0, 1.0 - (step - warmup_end) / (n_steps - warmup_end))
        entries.append({
            "step":               step,
            "epoch":              epoch,
            "loss":               round(loss, 4),
            "learning_rate":      lr,
            "grad_norm":          round(float(max(0.05, 1.4 * np.exp(-2 * p) + 0.3
                                                   + abs(np.random.normal(0, 0.2)))), 4),
            "rewards/chosen":     round(float(0.3 * p + np.random.normal(0, 0.015)), 4),
            "rewards/rejected":   round(float(-0.2 * p + np.random.normal(0, 0.015)), 4),
            "rewards/margins":    round(float(0.5 * p + np.random.normal(0, 0.02)), 4),
            "rewards/accuracies": round(float(np.clip(
                0.5 + 0.22 * p + np.random.normal(0, 0.01), 0.0, 1.0)), 4),
            "logps/chosen":       round(float(-3.5 + 0.4 * p + np.random.normal(0, 0.1)), 4),
            "logps/rejected":     round(float(-3.0 - 0.3 * p + np.random.normal(0, 0.1)), 4),
        })
        if step in (steps[n_log // 2 - 1], steps[-1]):
            entries.append({
                "step":      step,
                "epoch":     epoch,
                "eval_loss": round(float(max(0.05, loss + 0.12 + np.random.normal(0, 0.03))), 4),
            })

    entries.append({
        "train_runtime":            3623.4,
        "train_samples_per_second": 14.2,
        "train_steps_per_second":   0.89,
        "total_flos":               1.4e15,
        "train_loss":               0.38,
        "epoch":                    3.0,
    })
    return entries


# ---------------------------------------------------------------------------
# Test 1 — Happy path: full PlotManager pipeline
# ---------------------------------------------------------------------------

def test_all_plots_happy_path(tmp_path):
    pm = PlotManager(
        config_path=_make_config(tmp_path),
        beta=0.1,
        max_grad_norm=1.0,
        output_base=tmp_path,
    )
    run_dir = pm.run(_make_synthetic_log_history())
    expected = [
        "loss.png", "reward_margin.png", "reward_accuracy.png",
        "log_ratio.png", "kl_divergence.png", "grad_norm.png",
        "lr_schedule.png", "batch_loss.png", "throughput.png",
    ]
    for fname in expected:
        p = run_dir / fname
        assert p.exists() and p.stat().st_size > 0, f"Missing or empty: {fname}"


# ---------------------------------------------------------------------------
# Test 2 — Empty log_history raises the correct exception per function
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plot_fn,extra_kwargs,exc_type", [
    (plot_loss,            {},            ValueError),
    (plot_batch_loss,      {},            ValueError),
    (plot_reward_margin,   {},            KeyError),
    (plot_reward_accuracy, {},            KeyError),
    (plot_log_ratio,       {},            KeyError),
    (plot_kl_divergence,   {"beta": 0.1}, KeyError),
    (plot_lr_schedule,     {},            KeyError),
    (plot_throughput,      {},            KeyError),
])
def test_empty_log_history_raises(plot_fn, extra_kwargs, exc_type, tmp_path):
    with pytest.raises(exc_type):
        plot_fn([], output_dir=tmp_path, **extra_kwargs)


# ---------------------------------------------------------------------------
# Test 3 — grad_norm with empty history produces a file (graceful degradation)
# ---------------------------------------------------------------------------

def test_grad_norm_empty_produces_file(tmp_path):
    out = plot_grad_norm([], tmp_path)
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test 4 — KL divergence: beta=0 raises ValueError
# ---------------------------------------------------------------------------

def test_kl_divergence_beta_zero_raises(tmp_path):
    with pytest.raises(ValueError, match="beta must be non-zero"):
        plot_kl_divergence(_make_synthetic_log_history(), beta=0, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Test 5 — loss.py with no eval entries still produces a valid file
# ---------------------------------------------------------------------------

def test_loss_no_eval_entries(tmp_path):
    history = [e for e in _make_synthetic_log_history() if "eval_loss" not in e]
    out = plot_loss(history, tmp_path)
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test 6 — reward_margin with only margins key (chosen/rejected absent)
# ---------------------------------------------------------------------------

def test_reward_margin_margins_only(tmp_path):
    history = [{"step": i * 10, "rewards/margins": float(i) * 0.1} for i in range(1, 6)]
    out = plot_reward_margin(history, tmp_path)
    assert out.exists() and out.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test 7 — throughput missing summary entry raises KeyError
# ---------------------------------------------------------------------------

def test_throughput_no_summary_raises(tmp_path):
    history = [e for e in _make_synthetic_log_history()
               if "train_samples_per_second" not in e]
    with pytest.raises(KeyError, match="train_samples_per_second"):
        plot_throughput(history, tmp_path)


# ---------------------------------------------------------------------------
# Test 8 — rolling_mean unit tests
# ---------------------------------------------------------------------------

def test_rolling_mean_single_element():
    result = rolling_mean(np.array([5.0]), window=10)
    assert result.shape == (1,)
    assert float(result[0]) == pytest.approx(5.0)


def test_rolling_mean_window_larger_than_array():
    arr = np.array([1.0, 2.0, 3.0])
    result = rolling_mean(arr, window=100)
    assert result.shape == (3,)
    assert float(result[-1]) == pytest.approx(2.0)  # mean([1,2,3])


def test_rolling_mean_empty():
    result = rolling_mean(np.array([]), window=5)
    assert result.shape == (0,)


def test_rolling_mean_window_one():
    arr = np.array([1.0, 4.0, 9.0])
    np.testing.assert_array_almost_equal(rolling_mean(arr, window=1), arr)


def test_rolling_mean_correctness():
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = rolling_mean(arr, window=3)
    # expanding window: [1], [1,2], [1,2,3], [2,3,4], [3,4,5]
    expected = np.array([1.0, 1.5, 2.0, 3.0, 4.0])
    np.testing.assert_array_almost_equal(result, expected)


# ---------------------------------------------------------------------------
# Test 9 — very small n_log (1 entry) — loss and batch_loss still produce files
# ---------------------------------------------------------------------------

def test_plots_single_log_entry(tmp_path):
    history = _make_synthetic_log_history(n_log=1)
    plot_loss(history, tmp_path)
    assert (tmp_path / "loss.png").exists()
    plot_batch_loss(history, tmp_path)
    assert (tmp_path / "batch_loss.png").exists()


# ---------------------------------------------------------------------------
# Test 10 — NaN values in batch_loss don't crash (nan-aware stats)
# ---------------------------------------------------------------------------

def test_batch_loss_nan_values(tmp_path):
    history = [{"step": i * 10, "loss": float("nan"), "epoch": 0.0} for i in range(1, 6)]
    out = plot_batch_loss(history, tmp_path)
    assert out.exists()
