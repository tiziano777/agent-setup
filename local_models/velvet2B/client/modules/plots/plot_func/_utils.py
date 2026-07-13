'''Shared utilities for the modules.plots package.

Provides output-directory creation with experiment lineage tracking
and a causal rolling-mean helper shared across all smoothed plot modules.
'''
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; safe for headless GPU servers

import numpy as np
import yaml

logger = logging.getLogger(__name__)


def create_run_dir(config_path: str = "config.yml") -> Path:
    '''Create a timestamped output directory and copy config.yml for lineage.

    Writes all plots under modules/docs/images/<experiment_name>_<UTC_ts>/
    and places a config.yml copy alongside for full experiment traceability.

    Parameters
    ----------
    config_path : str
        Path to the YAML config file containing experiment.experiment_name.

    Returns
    -------
    Path
        Absolute path to the newly created run directory.
    '''
    # -- load experiment name from YAML config --
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        exp_name = (config.get("experiment", {}) or {}).get("experiment_name") or "unknown"
    except (FileNotFoundError, PermissionError, yaml.YAMLError) as exc:
        logger.warning(
            "create_run_dir: cannot read config %r (%s); using 'unknown' for run dir name.",
            config_path, exc,
        )
        exp_name = "unknown"
    exp_name_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in exp_name)

    # -- build timestamped directory under modules/docs/images/ --
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(__file__).resolve().parent.parent / "docs" / "images"
        / f"{exp_name_safe}_{ts}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # -- copy config alongside plots for experiment lineage --
    src = Path(config_path)
    if src.exists():
        shutil.copy2(src, out_dir / "config.yml")

    return out_dir


def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    '''Compute a causal rolling mean with expanding window at the start.

    Parameters
    ----------
    arr : np.ndarray
        1-D float array of values to smooth.
    window : int
        Rolling window size; early indices use a shorter expanding window.

    Returns
    -------
    np.ndarray
        Smoothed array of the same length as arr.
    '''
    arr = np.asarray(arr, dtype=float)
    n = len(arr)
    if n == 0:
        return arr.copy()
    if window < 1:
        logger.warning("rolling_mean: window=%d clamped to 1.", window)
        window = 1
    if window > n:
        logger.warning("rolling_mean: window=%d exceeds array length %d; clamping.", window, n)
        window = n
    cumsum = np.cumsum(np.concatenate([[0.0], arr]))
    idx = np.arange(n)
    starts = np.maximum(0, idx - window + 1)
    return (cumsum[idx + 1] - cumsum[starts]) / (idx - starts + 1)
