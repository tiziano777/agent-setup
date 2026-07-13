"""Plot manager for DPO training diagnostics.

Single entry point that:
  1. Creates the timestamped output directory (with config.yml lineage copy).
  2. Calls every plot function, passing the directory and any extra params.
  3. Logs a summary of saved files and any plots that failed gracefully.

Usage after trainer.train()::

    from modules.plots.plot_manager import PlotManager
    pm = PlotManager(config_path="config.yml", beta=0.1)
    pm.run(trainer.state.log_history)
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import traceback
import yaml
import matplotlib
matplotlib.use("Agg")  # headless / GPU-server safe
import matplotlib.pyplot as plt
plt.style.use("seaborn-v0_8-whitegrid")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import all plot functions from the plot_func sub-package
# ---------------------------------------------------------------------------
from modules.plots.plot_func.loss           import plot_loss
from modules.plots.plot_func.eval_loss      import plot_eval_loss
from modules.plots.plot_func.reward_margin  import plot_reward_margin
from modules.plots.plot_func.reward_accuracy import plot_reward_accuracy
from modules.plots.plot_func.log_ratio      import plot_log_ratio
from modules.plots.plot_func.KL_divergence  import plot_kl_divergence
from modules.plots.plot_func.grad_norm      import plot_grad_norm
from modules.plots.plot_func.lr_schedule    import plot_lr_schedule
from modules.plots.plot_func.batch_loss     import plot_batch_loss
from modules.plots.plot_func.throughput     import plot_throughput


class PlotManager:
    """Orchestrates all DPO training diagnostic plots for one experiment run.

    Parameters
    ----------
    config_path : str
        Path to the project config.yml.  Used to read experiment_name for the
        output directory name and copied alongside the plots for lineage.
    beta : float
        The beta value used in DPOConfig.  Required by the KL-divergence plot.
    max_grad_norm : float or None
        Clipping ceiling from DPOConfig; passed to the grad-norm plot.
        Defaults to 1.0 (the DPOConfig default).
    output_base : Path or None
        Override the base directory for plot output.  When None (default) the
        manager writes to ``<project_root>/modules/docs/images/``.
    grad_norm_smoothing : int
        Rolling-mean window for grad norm smoothing (default 20). Higher values
        produce smoother curves; set to 1 to disable smoothing.
    """

    def __init__(
        self,
        config_path: str = "config.yml",
        beta: float = 0.1,
        max_grad_norm: Optional[float] = 1.0,
        output_base: Optional[Path] = None,
        grad_norm_smoothing: int = 20,
    ) -> None:
        self.config_path   = config_path
        self.beta          = beta
        self.max_grad_norm = max_grad_norm
        self.output_base   = output_base
        self.grad_norm_smoothing = grad_norm_smoothing
        self.run_dir: Optional[Path] = None   # set after run() is called

    # ------------------------------------------------------------------
    # Directory + lineage helpers
    # ------------------------------------------------------------------

    def _create_run_dir(self) -> Path:
        """Create timestamped output dir and copy config.yml for lineage."""
        # -- read experiment name from config --
        with open(self.config_path, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        exp_name = (config.get("experiment", {}) or {}).get("name") or "unknown"
        exp_name_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in exp_name)

        # -- build base directory path --
        if self.output_base is not None:
            base = Path(self.output_base)
        else:
            base = Path(__file__).resolve().parent.parent / "docs" / "images"

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = base / f"{exp_name_safe}_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # -- copy config alongside plots for experiment traceability --
        src = Path(self.config_path)
        if src.exists():
            shutil.copy2(src, run_dir / "config.yml")
            logger.info("Config lineage saved to %s/config.yml", run_dir)

        return run_dir

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, log_history: List[Dict]) -> Path:
        """Generate all diagnostic plots from trainer.state.log_history.

        Parameters
        ----------
        log_history : list of dict
            ``trainer.state.log_history`` as returned by DPOTrainer after
            ``trainer.train()`` completes.

        Returns
        -------
        Path
            The run directory where all plots (and config.yml copy) were saved.
        """
        # -- create output directory once per run --
        self.run_dir = self._create_run_dir()
        logger.info("Saving plots to %s", self.run_dir)

        # -- ordered list of (label, callable) pairs --
        # Each callable receives (log_history, run_dir) plus extra kwargs.
        tasks = [
            ("loss",            self._run_loss),
            ("eval_loss",       self._run_eval_loss),
            ("reward_margin",   self._run_reward_margin),
            ("reward_accuracy", self._run_reward_accuracy),
            ("log_ratio",       self._run_log_ratio),
            ("kl_divergence",   self._run_kl_divergence),
            ("grad_norm",       self._run_grad_norm),
            ("lr_schedule",     self._run_lr_schedule),
            ("batch_loss",      self._run_batch_loss),
            ("throughput",      self._run_throughput),
        ]

        saved, failed = [], []
        for name, fn in tasks:
            try:
                out = fn(log_history, self.run_dir)
                saved.append((name, out))
            except Exception as exc:
                # -- non-fatal: log warning, append full traceback to errors.log --
                tb = traceback.format_exc()
                logger.warning("Plot '%s' failed: %s", name, exc)
                self._append_error_log(name, exc, tb)
                failed.append((name, exc))

        # -- summary --
        logger.info("Plots saved (%d/%d):", len(saved), len(tasks))
        for name, path in saved:
            size = Path(path).stat().st_size if Path(path).exists() else 0
            logger.info("  %-20s -> %s  (%d bytes)", name, path.name, size)
        if failed:
            logger.warning("Plots skipped — errors written to %s/errors.log:", self.run_dir)
            for name, exc in failed:
                logger.warning("  %-20s  %s", name, exc)

        return self.run_dir

    # ------------------------------------------------------------------
    # Per-plot wrappers (isolate extra params from the unified run loop)
    # ------------------------------------------------------------------

    def _append_error_log(self, plot_name: str, exc: Exception, tb: str) -> None:
        """Append a plot failure record to errors.log in the run directory."""
        # -- open in append mode so multiple failures accumulate in one file --
        if self.run_dir is None:
            return
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        log_path = self.run_dir / "errors.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}]  plot={plot_name}  error={exc!r}\n")
            fh.write(tb)
            fh.write("\n" + "-" * 72 + "\n")

    def _run_loss(self, log_history, run_dir):
        return plot_loss(log_history, run_dir)

    def _run_eval_loss(self, log_history, run_dir):
        return plot_eval_loss(log_history, run_dir)

    def _run_reward_margin(self, log_history, run_dir):
        return plot_reward_margin(log_history, run_dir)

    def _run_reward_accuracy(self, log_history, run_dir):
        return plot_reward_accuracy(log_history, run_dir)

    def _run_log_ratio(self, log_history, run_dir):
        return plot_log_ratio(log_history, run_dir)

    def _run_kl_divergence(self, log_history, run_dir):
        return plot_kl_divergence(log_history, self.beta, run_dir)

    def _run_grad_norm(self, log_history, run_dir):
        return plot_grad_norm(log_history, run_dir, max_grad_norm=self.max_grad_norm,
                             smoothing_window=self.grad_norm_smoothing)

    def _run_lr_schedule(self, log_history, run_dir):
        return plot_lr_schedule(log_history, run_dir)

    def _run_batch_loss(self, log_history, run_dir):
        return plot_batch_loss(log_history, run_dir)

    def _run_throughput(self, log_history, run_dir):
        return plot_throughput(log_history, run_dir)
