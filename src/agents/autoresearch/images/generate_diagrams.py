"""Generate Mermaid PNG diagrams for all autoresearch LangGraph pipelines.

Usage:
    python -m src.agents.autoresearch.images.generate_diagrams
"""

from __future__ import annotations

import importlib
import logging
import os
import traceback
from pathlib import Path

os.environ["PHOENIX_TRACING_ENABLED"] = "false"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).parent

PIPELINES: list[tuple[str, str, str, bool]] = [
    # (name, module_path, attr_name, is_factory)
    ("agent_pipeline", "src.agents.autoresearch.pipelines.agent_pipeline", "build_agent_pipeline", True),
    ("grid_pipeline", "src.agents.autoresearch.pipelines.grid_pipeline", "build_grid_pipeline", True),
    ("random_pipeline", "src.agents.autoresearch.pipelines.random_pipeline", "build_random_pipeline", True),
    ("functional_pipeline", "src.agents.autoresearch.pipelines.pipeline", "workflow", False),
]


def main() -> None:
    logger.info("Output directory: %s", IMAGES_DIR)

    for name, module_path, attr_name, is_factory in PIPELINES:
        logger.info("--- %s ---", name)
        try:
            mod = importlib.import_module(module_path)
            obj = getattr(mod, attr_name)
            pipeline = obj() if is_factory else obj

            png_bytes = pipeline.get_graph().draw_mermaid_png()
            out_path = IMAGES_DIR / f"{name}.png"
            out_path.write_bytes(png_bytes)
            logger.info("Salvata immagine: %s", out_path)
        except Exception as e:
            logger.warning("Errore generazione %s: %s", name, e)
            logger.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
