"""Training throughput summary: samples/sec, steps/sec, total runtime and FLOPs.

Single aggregate data point from the final log entry — not a time series.
Use it to benchmark GPU utilisation across experiments.

Red Flags / Interpretation
--------------------------
* Very low samples/sec (< 2 on single A100) -> tokenisation or data-loading bottleneck;
  check dataset_num_proc and storage IOPS.
* train_samples_per_second missing -> training interrupted before completion.
* total_flos unexpectedly large -> sequences longer than expected; check filter_by_token_len.
* Runtime >> expected for step count -> check device_map; model may be split to CPU.
* Steps/sec very low relative to samples/sec -> large per_device_train_batch_size overhead.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_throughput(
    log_history: List[Dict],
    output_dir: Path,
    figsize: Tuple[float, float] = (9, 5),
) -> Path:
    """Save training throughput summary figure to output_dir/throughput.png.

    Parameters
    ----------
    log_history : list of dict
        trainer.state.log_history from DPOTrainer (uses the final summary entry).
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
    KeyError
        If log_history has no entry with train_samples_per_second (training interrupted).
    """
    # -- locate the training summary entry (prefer samples/sec, else steps/sec) --
    summary = next(
        (
            e
            for e in reversed(log_history)
            if any(k in e for k in ("train_samples_per_second", "train_steps_per_second", "train_runtime"))
        ),
        None,
    )

    # If nothing useful found, write a small placeholder image and return.
    if summary is None:
        logger.warning(
            "plot_throughput: no throughput summary entry found — training may have been interrupted."
        )
        fig, ax = plt.subplots(figsize=figsize)
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "No throughput data found in log_history\n(Training may have been interrupted)",
            ha="center",
            va="center",
            fontsize=11,
        )
        out = Path(output_dir) / "throughput.png"
        fig.tight_layout()
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved placeholder %s", out)
        return out

    # read available metrics (may be missing one of them)
    sps_val = summary.get("train_samples_per_second")
    stps_val = summary.get("train_steps_per_second")
    runtime = float(summary.get("train_runtime", 0))
    flos = summary.get("total_flos")
    t_loss = summary.get("train_loss")

    sps = float(sps_val) if sps_val is not None else None
    stps = float(stps_val) if stps_val is not None else None

    # -- build two-panel figure: bar chart (left) + text summary card (right) --
    fig, (ax_bar, ax_txt) = plt.subplots(1, 2, figsize=figsize,
                                          gridspec_kw={"width_ratios": [1, 1]})
    labels = []
    values = []
    colors = []
    if sps is not None:
        labels.append("Samples/sec")
        values.append(sps)
        colors.append("#3F51B5")
    if stps is not None:
        labels.append("Steps/sec")
        values.append(stps)
        colors.append("#9C27B0")
    bars = ax_bar.barh(labels, values, color=colors, height=0.45, edgecolor="white")
    for bar, val in zip(bars, values):
        fmt = "{:.2f}" if labels[list(bars).index(bar)] == "Samples/sec" else "{:.4f}"
        ax_bar.text(
            bar.get_width() + (max(values) if values else 1) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            fmt.format(val),
            va="center",
            fontsize=11,
            fontweight="bold",
        )
    ax_bar.set_xlim(0, (max(values) if values else 1) * 1.3)
    ax_bar.set_xlabel("Rate")
    ax_bar.set_title("Training Throughput")
    ax_bar.grid(axis="x", alpha=0.25)
    ax_bar.spines[["top", "right"]].set_visible(False)

    # -- compose text summary card with runtime, FLOPs, final loss --
    runtime_str = str(timedelta(seconds=int(runtime)))
    lines = [f"  Total runtime  :  {runtime_str}"]
    if sps is not None:
        lines.append(f"  Samples / sec  :  {sps:.2f}")
    if stps is not None:
        lines.append(f"  Steps / sec    :  {stps:.4f}")
    if flos is not None:
        lines.append(f"  Total FLOPs    :  {flos:.2e}")
    if t_loss is not None:
        lines.append(f"  Final train loss:  {t_loss:.4f}")
    ax_txt.axis("off")
    ax_txt.text(0.08, 0.72, "Training Summary", transform=ax_txt.transAxes,
                fontsize=12, fontweight="bold", va="center")
    ax_txt.text(0.08, 0.38, "\n".join(lines), transform=ax_txt.transAxes,
                fontsize=9.5, va="top", family="monospace",
                bbox=dict(boxstyle="round,pad=0.5", fc="#F5F5F5", ec="#BDBDBD"))

    # -- save and release memory --
    out = Path(output_dir) / "throughput.png"
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", out)
    return out
