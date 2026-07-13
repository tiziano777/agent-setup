"""Gradient norm (pre-clip L2 norm of all parameters) over training steps.

Red Flags / Interpretation
--------------------------
* Norm persistently == max_grad_norm ceiling -> always clipping; effective LR smaller than set;
  consider raising max_grad_norm or lowering learning_rate.
* Single isolated spike -> bad batch; note the step and inspect that data slice.
* Norm growing monotonically without plateau -> instability; reduce LR or increase max_grad_norm.
* Norm approaching 0 after many steps -> vanishing gradients; check frozen layers or extreme beta.
* Norm absent from log_history -> run used max_grad_norm=0 (clipping disabled).
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np
from modules.plots.plot_func._utils import rolling_mean

logger = logging.getLogger(__name__)


def plot_grad_norm(
    log_history: List[Dict],
    output_dir: Path,
    max_grad_norm: Optional[float] = 1.0,
    smoothing_window: int = 20,
    figsize: Tuple[float, float] = (10, 5),
) -> Path:
    """Save gradient-norm-over-steps plot to output_dir/grad_norm.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    max_grad_norm : float or None
        Clipping ceiling from DPOConfig; drawn as a reference line. Pass None to omit.
    smoothing_window : int
        Rolling-mean window applied to reduce noise (1 = no smoothing, default 20).
    figsize : tuple
        Matplotlib figure size in inches.

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- extract gradient norm entries --
    entries = [e for e in log_history if "grad_norm" in e]
    if not entries:
        logger.warning("No 'grad_norm' entries in log_history; plot will be empty.")
        out = Path(output_dir) / "grad_norm.png"
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title("Gradient Norm (no data)")
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return out
    steps      = np.array([e["step"]      for e in entries])
    grad_norms = np.array([e["grad_norm"] for e in entries], dtype=float)

    # -- apply rolling mean to reduce noise --
    smoothed = rolling_mean(grad_norms, smoothing_window)

    # -- identify steps at or above the clip ceiling --
    clipped_mask = (
        np.zeros(len(steps), dtype=bool)
        if max_grad_norm is None
        else (grad_norms >= max_grad_norm * 0.99)
    )

    # -- build figure with raw norm (faint), smoothed, ceiling reference line, shaded over-ceiling --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps, grad_norms, color="#607D8B", alpha=0.2, linewidth=0.8, label="Grad norm (raw)")
    ax.plot(steps, smoothed, color="#607D8B", linewidth=2.0,
            label=f"Grad norm (smooth={smoothing_window})")
    if np.any(clipped_mask):
        ax.scatter(steps[clipped_mask], grad_norms[clipped_mask],
                   color="#F44336", s=30, zorder=5, label="At/above clip ceiling")
    if max_grad_norm is not None:
        ax.axhline(max_grad_norm, color="#F44336", linestyle="--", alpha=0.7,
                   linewidth=1.2, label=f"Clip ceiling ({max_grad_norm})")
        ax.fill_between(steps, grad_norms, max_grad_norm,
                        where=(grad_norms >= max_grad_norm),
                        alpha=0.15, color="#F44336")
    ax.set_xlabel("Step")
    ax.set_ylabel("Gradient Norm (pre-clip)")
    ax.set_title("Gradient Norm")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "grad_norm.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
