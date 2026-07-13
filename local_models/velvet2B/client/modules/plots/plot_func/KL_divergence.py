"""Estimated KL divergence between trained policy and reference model over steps.

TRL does not log KL directly. This module estimates it from logged rewards:
    kl_proxy = (rewards/chosen - rewards/rejected) / (2 * beta)
This equals the symmetric log-ratio margin, correlating well with actual policy drift.

Red Flags / Interpretation
--------------------------
* KL proxy rising with no plateau -> model drifting far from reference; raise beta or lower LR.
* KL proxy near zero throughout -> updates too conservative; beta may be too high.
* KL proxy spikes then drops -> bad batch caused a large update; cross-check grad_norm.png.
* KL proxy > 5 (task-dependent) -> aggressive drift; outputs may degrade on held-out tasks.
* Large KL with good reward margin -> model learning preferences but changing generation style.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_kl_divergence(
    log_history: List[Dict],
    beta: float,
    output_dir: Path,
    figsize: Tuple[float, float] = (10, 5),
) -> Path:
    """Save estimated KL-divergence proxy plot to output_dir/kl_divergence.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    beta : float
        The beta value used in DPOConfig (controls KL penalty strength).
    output_dir : Path
        Directory where the figure is saved.
    figsize : tuple
        Matplotlib figure size in inches.

    Returns
    -------
    Path
        Path to the saved figure.

    Raises
    ------
    ValueError
        If beta is zero (division by zero in proxy calculation).
    """
    if beta == 0:
        logger.warning("plot_kl_divergence: beta=0 — division by zero in proxy calculation.")
        raise ValueError("beta must be non-zero for KL proxy calculation.")

    # -- extract reward entries and compute per-step KL proxy --
    entries = [e for e in log_history if "rewards/chosen" in e and "rewards/rejected" in e]
    if not entries:
        logger.warning(
            "plot_kl_divergence: no 'rewards/chosen'/'rewards/rejected' entries found in log_history."
        )
        raise KeyError("No 'rewards/chosen'/'rewards/rejected' entries found in log_history.")
    steps    = np.array([e["step"]              for e in entries])
    r_cho    = np.array([e["rewards/chosen"]    for e in entries], dtype=float)
    r_rej    = np.array([e["rewards/rejected"]  for e in entries], dtype=float)

    # -- compute symmetric KL proxy and per-side log-ratio contributions --
    kl_proxy = (r_cho - r_rej) / (2.0 * beta)
    kl_cho   = r_cho / beta
    kl_rej   = np.abs(r_rej) / beta

    # -- build figure with proxy series and per-side components --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps, kl_proxy, color="#FF5722", linewidth=2.2,
            label=f"KL proxy  (beta={beta})")
    ax.plot(steps, kl_cho, color="#4CAF50", linewidth=1.2, linestyle="--",
            alpha=0.7, label="chosen-side  r_chosen / beta")
    ax.plot(steps, kl_rej, color="#F44336", linewidth=1.2, linestyle="--",
            alpha=0.7, label="|rejected-side|  |r_rejected| / beta")
    ax.axhline(0, color="gray", linestyle=":", alpha=0.4, linewidth=0.8)
    ax.fill_between(steps, kl_proxy, 0, where=(kl_proxy >= 0), alpha=0.10, color="#FF5722")
    ax.set_xlabel("Step")
    ax.set_ylabel("KL proxy (approx. nats)")
    ax.set_title(f"Estimated KL Divergence proxy  [beta={beta}]")
    ax.text(0.02, 0.97, "Approximation: not the closed-form KL(pi_theta || pi_ref)",
            transform=ax.transAxes, fontsize=7, color="gray", va="top")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "kl_divergence.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
