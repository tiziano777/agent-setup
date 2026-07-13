"""Evaluation loss tracking across validation steps.

Shows how validation loss evolves, independent of training loss.
Useful for detecting overfitting (train down, eval up) or convergence plateau.

Red Flags / Interpretation
--------------------------
* Eval loss >> train loss from step 1 -> possible data leakage or distribution mismatch.
* Eval loss rises while train loss drops -> overfitting; reduce epochs or add regularization.
* Eval loss plateau while train continues -> possible validation set too small or too easy.
* Eval loss spikes at one point -> rare; may indicate batch-specific anomaly.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np
from modules.plots.plot_func._utils import rolling_mean

logger = logging.getLogger(__name__)


def plot_eval_loss(
    log_history: List[Dict],
    output_dir: Path,
    smoothing_window: int = 3,
    figsize: Tuple[float, float] = (10, 5),
) -> Path:
    """Save eval-loss curve to output_dir/eval_loss.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    smoothing_window : int
        Rolling-mean window for eval series (default 3; low since eval points are sparse).
    figsize : tuple
        Matplotlib figure size in inches.

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- extract eval_loss entries --
    evals = [(e["step"], e["eval_loss"]) for e in log_history if "eval_loss" in e]
    if not evals:
        logger.warning("plot_eval_loss: no eval_loss entries found in log_history.")
        out = Path(output_dir) / "eval_loss.png"
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title("Eval Loss (no data)")
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out

    steps_e, losses_e = zip(*evals)
    steps_e = np.array(steps_e)
    losses_e = np.array(losses_e, dtype=float)

    # -- smooth eval curve if multiple points --
    if len(evals) > 1:
        smoothed = rolling_mean(losses_e, smoothing_window)
    else:
        smoothed = losses_e

    # -- compute basic stats --
    min_eval = float(np.min(losses_e))
    max_eval = float(np.max(losses_e))
    mean_eval = float(np.mean(losses_e))

    # -- build figure with raw + smoothed (if multiple) --
    fig, ax = plt.subplots(figsize=figsize)

    if len(evals) > 1:
        # Multiple eval points: show both raw and smoothed
        ax.plot(steps_e, losses_e, color="#E91E63", alpha=0.3, linewidth=0.8,
                label="Eval loss (raw)")
        ax.plot(steps_e, smoothed, color="#E91E63", linewidth=2.0,
                label=f"Eval loss (smooth={smoothing_window})", linestyle="-", marker="o", markersize=6)
    else:
        # Single eval point: just show the value
        ax.scatter(steps_e, losses_e, color="#E91E63", s=100, zorder=5,
                  label=f"Final eval loss = {losses_e[0]:.4f}", edgecolor="#C2185B", linewidth=2)

    # -- reference lines for min/max/mean --
    if len(evals) > 1:
        ax.axhline(mean_eval, color="gray", linestyle=":", alpha=0.5, linewidth=1.0,
                  label=f"Mean = {mean_eval:.4f}")
        ax.fill_between(steps_e, min_eval, max_eval, alpha=0.1, color="#E91E63")

    ax.set_xlabel("Step")
    ax.set_ylabel("Eval Loss")
    ax.set_title("Validation Loss Evolution")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "eval_loss.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
