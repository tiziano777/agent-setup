"""Raw per-logging-step loss without smoothing, with outlier flagging.

Complements loss.py: exposes noise texture and anomalous steps that smoothing hides.

Red Flags / Interpretation
--------------------------
* Many outlier steps flagged -> dataset contains noisy or mislabelled pairs.
* Single isolated outlier at one step -> specific bad batch; note the step number.
* Loss == 0.0 or NaN at any step -> tokenisation produced empty sequences after truncation.
* High variance throughout (jagged) -> batch size too small; increase gradient_accumulation_steps.
* Raw curve much noisier than smoothed but trend matches -> normal; noise is batching artefact.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np
from modules.plots.plot_func._utils import rolling_mean

logger = logging.getLogger(__name__)


def plot_batch_loss(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (12, 5),
) -> Path:
    """Save raw per-logging-step loss with outlier markers to output_dir/batch_loss.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    figsize : tuple
        Matplotlib figure size in inches (wider is better for noisy series).

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- extract raw train-loss entries --
    train = [
        (e["step"], e["loss"]) for e in log_history
        if "loss" in e and "eval_loss" not in e and "train_runtime" not in e
    ]
    if not train:
        logger.warning("plot_batch_loss: no train-loss entries found in log_history.")
        raise ValueError("No train-loss entries found in log_history.")
    steps  = np.array([x[0] for x in train])
    losses = np.array([x[1] for x in train], dtype=float)

    # -- compute light-smooth overlay and detect statistical outliers (>mean+3*std) --
    light_smooth = rolling_mean(losses, window=5)
    mean_loss = float(np.nanmean(losses))
    std_loss  = float(np.nanstd(losses))
    outlier_mask = losses > (mean_loss + 3 * std_loss)

    # -- build figure: transparent raw line + light smooth overlay + outlier dots --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps, losses, color="#2196F3", alpha=0.35, linewidth=0.9,
            label="Raw loss per logging step")
    ax.plot(steps, light_smooth, color="#2196F3", linewidth=1.8,
            alpha=0.85, label="Smooth (window=5)")
    if np.any(outlier_mask):
        ax.scatter(steps[outlier_mask], losses[outlier_mask],
                   color="#F44336", s=45, zorder=6,
                   label=f"Outliers >mean+3sigma  (n={int(outlier_mask.sum())})")
    ax.axhline(mean_loss, color="gray", linestyle=":", alpha=0.4, linewidth=0.8,
               label=f"Mean = {mean_loss:.4f}")
    ax.set_xlabel("Step")
    ax.set_ylabel("Loss (per logging window)")
    ax.set_title("Batch-level Train Loss (Raw)")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "batch_loss.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
