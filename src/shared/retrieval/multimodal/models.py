"""Multimodal data models extending the base retrieval types."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path

from src.shared.retrieval.vectorstores.base import Document


class ContentType(enum.Enum):
    """Supported modality types in parsed multimodal content."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    GENERIC = "generic"


@dataclass
class MultimodalContent:
    """A single element extracted from a parsed multimodal document.

    Each instance represents one content block (a paragraph, an image, a table,
    an equation, etc.) and carries type-specific fields.  Use
    :meth:`to_raganything_dict` to convert to the dict schema expected by
    RAG-Anything's ``insert_content_list``.
    """

    content_type: ContentType
    page_idx: int = 0

    # -- TEXT fields --
    text: str | None = None

    # -- IMAGE fields --
    img_path: Path | None = None
    image_caption: str | None = None
    image_footnote: str | None = None

    # -- TABLE fields --
    table_body: str | None = None  # markdown
    table_caption: str | None = None
    table_footnote: str | None = None

    # -- EQUATION fields --
    latex: str | None = None

    # -- GENERIC fallback --
    content: str | None = None

    def to_raganything_dict(self) -> dict:
        """Convert to the dict schema RAG-Anything's ``insert_content_list`` expects."""
        base: dict = {"type": self.content_type.value, "page_idx": self.page_idx}

        if self.content_type is ContentType.TEXT:
            base["text"] = self.text or ""
        elif self.content_type is ContentType.IMAGE:
            base["img_path"] = str(self.img_path) if self.img_path else ""
            if self.image_caption:
                base["image_caption"] = self.image_caption
            if self.image_footnote:
                base["image_footnote"] = self.image_footnote
        elif self.content_type is ContentType.TABLE:
            base["table_body"] = self.table_body or ""
            if self.table_caption:
                base["table_caption"] = self.table_caption
            if self.table_footnote:
                base["table_footnote"] = self.table_footnote
        elif self.content_type is ContentType.EQUATION:
            base["latex"] = self.latex or ""
            if self.text:
                base["text"] = self.text
        else:
            base["content"] = self.content or ""

        return base

    @property
    def display_text(self) -> str:
        """Human-readable text for backward-compat with str-based systems."""
        if self.content_type is ContentType.TEXT:
            return self.text or ""
        if self.content_type is ContentType.IMAGE:
            caption = self.image_caption or str(self.img_path or "image")
            return f"[Image: {caption}]"
        if self.content_type is ContentType.TABLE:
            header = f"[Table: {self.table_caption}]\n" if self.table_caption else ""
            return f"{header}{self.table_body or ''}"
        if self.content_type is ContentType.EQUATION:
            return f"$${self.latex or ''}$$"
        return self.content or ""


@dataclass
class MultimodalDocument(Document):
    """Document enriched with structured multimodal content.

    Extends :class:`Document` so it can be passed to any existing function
    that accepts ``Document`` (rerankers, vector stores).  The ``content``
    field is auto-populated from concatenated :attr:`MultimodalContent.display_text`.
    """

    media: list[MultimodalContent] = field(default_factory=list)
    source_path: str | None = None

    @classmethod
    def from_content_list(
        cls,
        doc_id: str,
        content_list: list[MultimodalContent],
        source_path: str | None = None,
        metadata: dict | None = None,
    ) -> MultimodalDocument:
        """Build from parsed content.  ``content`` is set to concatenated display_text."""
        text_parts = [item.display_text for item in content_list if item.display_text]
        return cls(
            id=doc_id,
            content="\n\n".join(text_parts),
            media=list(content_list),
            source_path=source_path,
            metadata=metadata or {},
        )
