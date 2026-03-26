"""Configuration for multimodal retrieval."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MultimodalRetrievalSettings:
    """Central configuration for the multimodal retrieval pipeline.

    Reads defaults from environment variables where appropriate.
    """

    # -- Storage --
    working_dir: str = field(
        default_factory=lambda: os.getenv("RAGANYTHING_WORKING_DIR", "./rag_storage")
    )

    # -- Parser --
    parser: Literal["mineru", "docling", "paddleocr", "glmocr"] = "mineru"
    parse_method: Literal["auto", "ocr", "txt"] = "auto"

    # -- GLM-OCR specific --
    glmocr_mode: Literal["maas", "selfhosted"] = field(
        default_factory=lambda: os.getenv("GLMOCR_MODE", "maas")
    )
    glmocr_api_key: str | None = field(
        default_factory=lambda: os.getenv("GLMOCR_API_KEY") or os.getenv("ZHIPU_API_KEY")
    )
    glmocr_selfhosted_host: str = field(
        default_factory=lambda: os.getenv("GLMOCR_HOST", "localhost")
    )
    glmocr_selfhosted_port: int = field(
        default_factory=lambda: int(os.getenv("GLMOCR_PORT", "8080"))
    )

    # -- Modality toggles --
    enable_image_processing: bool = True
    enable_table_processing: bool = True
    enable_equation_processing: bool = True

    # -- Query defaults --
    default_query_mode: Literal["hybrid", "local", "global", "naive"] = "hybrid"
    vlm_enhanced: bool | None = None  # None = auto-detect

    # -- Embedding (feeds the adapter) --
    embedding_provider: str = "sentence-transformer"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dims: int = 384
    embedding_max_tokens: int = 8192

    # -- LLM (feeds the adapter) --
    llm_model: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "llm"))
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096

    # -- Vision model --
    vision_model: str | None = field(default_factory=lambda: os.getenv("VISION_MODEL"))

    # -- Batch processing --
    max_workers: int = 4
    file_extensions: list[str] = field(
        default_factory=lambda: [".pdf", ".docx", ".pptx", ".png", ".jpg"]
    )
