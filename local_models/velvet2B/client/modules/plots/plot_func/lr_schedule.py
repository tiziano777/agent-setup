"""Learning-rate schedule over training steps.

Red Flags / Interpretation
--------------------------
* LR never reaches the configured peak -> warmup longer than max_steps; verify warmup_steps.
* LR stays flat at peak (no decay) -> lr_scheduler_type may be "constant"; verify config.
* LR drops to zero mid-training -> max_steps < full dataset steps; training ended early.
* LR spike at specific step -> scheduler restart or bad checkpoint resume artefact.
* Warmup region absent (LR starts at peak) -> warmup_steps=0; may cause early instability.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_lr_schedule(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (10, 4),
) -> Path:
    """Save learning-rate schedule to output_dir/lr_schedule.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    figsize : tuple
        Matplotlib figure size in inches (wide-short ratio recommended).

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- extract LR entries from train steps only --
    entries = [e for e in log_history if "learning_rate" in e]
    if not entries:
        logger.warning("plot_lr_schedule: no 'learning_rate' entries found in log_history.")
        raise KeyError("No 'learning_rate' entries found in log_history.")
    steps = np.array([e["step"]          for e in entries])
    lrs   = np.array([e["learning_rate"] for e in entries], dtype=float)

    # -- identify warmup region as steps where LR is still increasing --
    peak_idx  = int(np.argmax(lrs))
    peak_lr   = float(lrs[peak_idx])
    peak_step = int(steps[peak_idx])

    # -- build figure with warmup shading and peak reference line --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps, lrs, color="#009688", linewidth=2.0, label="Learning rate")
    ax.axhline(peak_lr, color="gray", linestyle=":", alpha=0.5, linewidth=0.8,
               label=f"Peak LR = {peak_lr:.2e}")
    if peak_idx > 0:
        ax.axvspan(steps[0], peak_step, alpha=0.08, color="#FF9800",
                   label=f"Warmup (up to step {peak_step})")
    ax.set_xlabel("Step")
    ax.set_ylabel("Learning Rate")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    ax.set_title("Learning Rate Schedule")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "lr_schedule.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
