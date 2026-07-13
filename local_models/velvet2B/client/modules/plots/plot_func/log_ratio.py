"""Log-probability series for chosen and rejected responses over steps.

Tracking logps/chosen and logps/rejected separately reveals WHY the reward margin
moves — which the margin plot alone cannot show.

Red Flags / Interpretation
--------------------------
* logps/chosen rises AND logps/rejected falls -> ideal dual improvement.
* Only logps/rejected falls, logps/chosen flat -> model penalises bad but not reinforcing good.
* Both series fall together -> model reducing overall output probability (length collapse risk).
* Both series rise together -> model becoming more confident about everything; overfit risk.
* Gap between series shrinks over time -> margin is collapsing; cross-check reward_margin.png.
* Very large absolute values (< -20) -> sequences too long for max_length; tokenisation issue.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_log_ratio(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (10, 6),
) -> Path:
    """Save chosen and rejected log-probability series to output_dir/log_ratio.png.

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
    # -- extract log-probability entries --
    entries = [e for e in log_history if "logps/chosen" in e and "logps/rejected" in e]
    if not entries:
        logger.warning("plot_log_ratio: no 'logps/chosen'/'logps/rejected' entries found in log_history.")
        raise KeyError("No 'logps/chosen'/'logps/rejected' entries found in log_history.")
    steps  = np.array([e["step"]            for e in entries])
    lp_cho = np.array([e["logps/chosen"]    for e in entries], dtype=float)
    lp_rej = np.array([e["logps/rejected"]  for e in entries], dtype=float)

    # -- compute log-ratio gap as a derived diagnostic series --
    gap = lp_cho - lp_rej

    # -- build two-panel figure: individual logps (top), their gap (bottom) --
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True,
                                    gridspec_kw={"height_ratios": [1.6, 1]})
    ax1.plot(steps, lp_cho, color="#4CAF50", linewidth=1.8, label="logps/chosen")
    ax1.plot(steps, lp_rej, color="#F44336", linewidth=1.8, label="logps/rejected")
    ax1.set_ylabel("Log-Probability (nats)")
    ax1.set_title("Log-Probabilities: Chosen vs Rejected")
    ax1.legend(loc="upper right")
    ax1.grid(axis="y", alpha=0.25)

    ax2.plot(steps, gap, color="#9C27B0", linewidth=1.5, label="gap (chosen - rejected)")
    ax2.axhline(0, color="gray", linestyle=":", alpha=0.4, linewidth=0.8)
    ax2.fill_between(steps, gap, 0, where=(gap >= 0), alpha=0.12, color="#4CAF50")
    ax2.fill_between(steps, gap, 0, where=(gap < 0),  alpha=0.12, color="#F44336")
    ax2.set_xlabel("Step")
    ax2.set_ylabel("Gap (nats)")
    ax2.legend(loc="upper left")
    ax2.grid(axis="y", alpha=0.25)

    # -- save and release memory --
    out = Path(output_dir) / "log_ratio.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
