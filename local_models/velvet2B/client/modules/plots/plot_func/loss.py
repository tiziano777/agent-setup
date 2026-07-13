"""Train and eval loss curves over training steps.

Red Flags / Interpretation
--------------------------
* Train loss drops, eval loss rises (cross) -> overfitting; reduce epochs or add regularisation.
* Both curves flat after warmup -> LR too low or beta too large; updates are constrained.
* Sharp spike at one step -> bad data batch or LR spike; cross-check with grad_norm.png.
* Train loss << eval loss from step 1 -> possible data leakage in the train split.
* Eval loss constant across checkpoints -> eval split too small or too easy.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np
from modules.plots.plot_func._utils import rolling_mean

logger = logging.getLogger(__name__)


def plot_loss(
    log_history: List[Dict],
    output_dir: Path,
    smoothing_window: int = 10,
    figsize: Tuple[float, float] = (10, 5),
) -> Path:
    """Save smoothed train-loss and eval-loss curves to output_dir/loss.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    smoothing_window : int
        Rolling-mean window applied to the train series (1 = no smoothing).
    figsize : tuple
        Matplotlib figure size in inches.

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- split log_history into train and eval entries --
    train = [
        (e["step"], e["loss"]) for e in log_history
        if "loss" in e and "eval_loss" not in e and "train_runtime" not in e
    ]
    evals = [(e["step"], e["eval_loss"]) for e in log_history if "eval_loss" in e]
    if not train:
        logger.warning("plot_loss: no train-loss entries found in log_history.")
        raise ValueError("No train-loss entries found in log_history.")
    if not evals:
        logger.warning("plot_loss: no eval-loss entries found in log_history; eval will not be shown.")
    steps_t = np.array([x[0] for x in train])
    losses_t = np.array([x[1] for x in train], dtype=float)

    # -- apply rolling mean to reduce per-step noise --
    smoothed = rolling_mean(losses_t, smoothing_window)

    # -- detect epoch boundaries for vertical guide lines --
    epoch_bounds, prev_ep = [], 0
    for e in log_history:
        if "loss" not in e or "eval_loss" in e or "train_runtime" in e:
            continue
        ep_int = int(e.get("epoch", 0))
        if ep_int > prev_ep:
            epoch_bounds.append(e["step"])
            prev_ep = ep_int

    # -- build figure: transparent raw + smoothed train line + eval markers/line --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps_t, losses_t, color="#2196F3", alpha=0.2, linewidth=0.8)
    ax.plot(steps_t, smoothed, color="#2196F3", linewidth=2.0,
            label=f"Train loss (smooth={smoothing_window})")

    # -- plot eval loss (as dashed line with markers, or as reference line if single point) --
    if evals:
        steps_e, losses_e = zip(*evals)
        if len(evals) > 1:
            ax.plot(steps_e, losses_e, color="#E91E63", linewidth=1.8,
                    linestyle="--", marker="o", markersize=5, label="Eval loss (each eval_steps)")
        else:
            # Single eval entry: show as horizontal reference line + final marker
            eval_loss_val = losses_e[0]
            ax.axhline(eval_loss_val, color="#E91E63", linestyle="--", alpha=0.8,
                      linewidth=2.0, label=f"Final eval loss = {eval_loss_val:.4f}")
            ax.scatter(steps_e, losses_e, color="#E91E63", s=80, zorder=6, edgecolor="#C2185B", linewidth=2)
    else:
        # No eval loss: add visible warning text on plot
        ax.text(0.98, 0.05, "⚠ NO EVAL LOSS FOUND",
               transform=ax.transAxes, ha="right", va="bottom",
               fontsize=11, color="#E91E63", weight="bold",
               bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#E91E63", alpha=0.8))
        logger.warning("plot_loss: no eval_loss in log_history; ensure eval_size > 0 and eval_steps configured")

    # -- epoch boundaries --
    for eb in epoch_bounds:
        ax.axvline(eb, color="gray", linestyle=":", alpha=0.4, linewidth=0.8)

    ax.set_xlabel("Step")
    ax.set_ylabel("Loss")
    ax.set_title("Train / Eval Loss")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "loss.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
