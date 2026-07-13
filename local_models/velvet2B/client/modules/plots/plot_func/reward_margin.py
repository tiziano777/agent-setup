"""Reward margin (chosen minus rejected) and individual reward series over steps.

The reward margin is the primary DPO health metric: how much more the model
prefers chosen over rejected responses relative to the reference policy.

Red Flags / Interpretation
--------------------------
* Margin flat or negative after many steps -> model not learning; check data quality and beta.
* Margin grows then suddenly drops -> reward hacking or catastrophic forgetting onset.
* Only rewards/rejected falls, chosen is flat -> model penalises bad but doesn't reinforce good.
* Both chosen and rejected rewards fall together -> model shrinking overall probability mass.
* Margin > 2.0 very quickly -> possible degenerate collapse; inspect logps/chosen.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_reward_margin(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (10, 6),
) -> Path:
    """Save reward margin + chosen/rejected series to output_dir/reward_margin.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer.
    output_dir : Path
        Directory where the figure is saved.
    figsize : tuple
        Matplotlib figure size in inches.

    Returns
    -------
    Path
        Path to the saved figure.
    """
    # -- extract DPO-specific reward entries --
    entries = [e for e in log_history if "rewards/margins" in e]
    if not entries:
        logger.warning("plot_reward_margin: no 'rewards/margins' entries found in log_history.")
        raise KeyError("No 'rewards/margins' entries found in log_history.")
    steps    = np.array([e["step"]              for e in entries])
    margins  = np.array([e["rewards/margins"]   for e in entries], dtype=float)
    chosen   = np.array([e.get("rewards/chosen",   float("nan")) for e in entries], dtype=float)
    rejected = np.array([e.get("rewards/rejected", float("nan")) for e in entries], dtype=float)

    # -- build two-panel figure: margin (top), chosen/rejected (bottom) --
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True,
                                    gridspec_kw={"height_ratios": [1.6, 1]})
    ax1.plot(steps, margins, color="#9C27B0", linewidth=2.0, label="Reward margin")
    ax1.axhline(0, color="red", linestyle="--", alpha=0.5, linewidth=1.0)
    ax1.fill_between(steps, margins, 0, where=(margins >= 0), alpha=0.15, color="#4CAF50")
    ax1.fill_between(steps, margins, 0, where=(margins < 0),  alpha=0.15, color="#F44336")
    ax1.set_ylabel("Margin")
    ax1.set_title("DPO Reward Margin")
    ax1.legend(loc="upper left")
    ax1.grid(axis="y", alpha=0.25)

    if not np.all(np.isnan(chosen)):
        ax2.plot(steps, chosen,   color="#4CAF50", linewidth=1.5, label="rewards/chosen")
    if not np.all(np.isnan(rejected)):
        ax2.plot(steps, rejected, color="#F44336", linewidth=1.5, label="rewards/rejected")
    ax2.axhline(0, color="gray", linestyle=":", alpha=0.4, linewidth=0.8)
    ax2.set_xlabel("Step")
    ax2.set_ylabel("Reward")
    ax2.legend(loc="upper left")
    ax2.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "reward_margin.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
