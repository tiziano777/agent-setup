"""Reward accuracy (fraction of pairs ranked correctly) over training steps.

Red Flags / Interpretation
--------------------------
* Accuracy < 0.50 -> worse than random; training diverging or data is mislabelled.
* Stuck at ~0.50 for many steps -> model not learning; LR too low or dataset too noisy.
* Accuracy > 0.90 very quickly -> potential overfitting; verify with eval loss.
* Sharp mid-training drop -> data contamination, LR spike, or bad checkpoint resume.
* Accuracy rises but loss does not fall -> model learning shortcuts, not genuine quality.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_reward_accuracy(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (10, 5),
) -> Path:
    """Save reward-accuracy-over-steps plot to output_dir/reward_accuracy.png.

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
    # -- extract reward accuracy entries --
    entries = [e for e in log_history if "rewards/accuracies" in e]
    if not entries:
        logger.warning("plot_reward_accuracy: no 'rewards/accuracies' entries found in log_history.")
        raise KeyError("No 'rewards/accuracies' entries found in log_history.")
    steps    = np.array([e["step"]              for e in entries])
    accuracy = np.array([e["rewards/accuracies"] for e in entries], dtype=float)

    # -- build figure with reference lines at random baseline and healthy target --
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(steps, accuracy * 100, color="#3F51B5", linewidth=2.0, label="Reward accuracy")
    ax.axhline(50.0, color="#F44336", linestyle="--", alpha=0.7, linewidth=1.2,
               label="Random baseline (50%)")
    ax.axhline(75.0, color="#4CAF50", linestyle=":", alpha=0.7, linewidth=1.2,
               label="Healthy target (75%)")
    ax.fill_between(steps, accuracy * 100, 50.0, where=(accuracy * 100 >= 50),
                    alpha=0.08, color="#3F51B5")

    # -- annotate final accuracy value --
    final_acc = float(accuracy[-1]) * 100
    ax.annotate(
        f"Final: {final_acc:.1f}%",
        xy=(steps[-1], final_acc),
        xytext=(-50, 12), textcoords="offset points",
        fontsize=9, color="#3F51B5",
        arrowprops=dict(arrowstyle="->", color="#3F51B5", lw=0.8),
    )
    ax.set_ylim(0, 100)
    ax.set_xlabel("Step")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("DPO Reward Accuracy")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "reward_accuracy.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
