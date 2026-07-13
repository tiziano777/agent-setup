from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Callable, Union, List, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Signature: (sample, system_prompt_content) -> messages list
# Returns a list of {"role": str, "content": str} dicts for the chat completions API.
TemplateFn = Callable[..., Union[dict, List[dict]]]


class ChatTypeRegistry:
    """Maps chat_type strings to their field-extraction template functions.

    Each template function's sole responsibility is to read a sample according
    to its chat_type input schema and return a normalized list of role/content
    messages for the chat completions API. The server applies the tokenizer
    template — no manual model-specific formatting belongs here.

    Loads a YAML file with the structure:
        <chat_type>:
          template_fn: /absolute/path/to/fn.py
          schema:      /absolute/path/to/input_schema.json

    Template functions are lazily imported and cached on first access.
    Each .py file must expose:
        def apply_chat_template(sample, system_prompt) -> list[dict]

    Raises:
        FileNotFoundError: if mapping file or a referenced template file is missing.
        KeyError:          if chat_type is not in the mapping.
        AttributeError:    if the template module lacks apply_chat_template.
    """

    def __init__(self, mapping_path: Union[str, Path]) -> None:
        self._mapping_path = Path(mapping_path)
        self._raw: Dict = self._load_mapping()
        self._fn_cache: Dict[str, TemplateFn] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_template_fn(self, chat_type: str) -> TemplateFn:
        """Return the cached template function for chat_type."""
        if chat_type not in self._fn_cache:
            self._fn_cache[chat_type] = self._import_fn(chat_type)
        return self._fn_cache[chat_type]

    def get_schema_path(self, chat_type: str) -> Optional[Path]:
        """Return the input schema path for chat_type, or None if not defined."""
        entry = self._raw.get(chat_type)
        if not entry:
            return None
        schema = entry.get("schema")
        if not schema:
            return None
        schema_path = Path(schema)
        if not schema_path.is_absolute():
            schema_path = self._mapping_path.parent / schema_path
        return schema_path

    def known_chat_types(self) -> List[str]:
        return list(self._raw.keys())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_mapping(self) -> Dict:
        if not self._mapping_path.exists():
            raise FileNotFoundError(
                f"Chat type mapping file not found: {self._mapping_path}"
            )
        with open(self._mapping_path) as f:
            data = yaml.safe_load(f) or {}
        return data

    def _import_fn(self, chat_type: str) -> TemplateFn:
        entry = self._raw.get(chat_type)
        if entry is None:
            raise KeyError(
                f"Unknown chat_type '{chat_type}'. "
                f"Known types: {list(self._raw.keys())}. "
                f"Add it to {self._mapping_path}"
            )

        fn_path = Path(entry.get("template_fn", ""))
        if not fn_path.is_absolute():
            fn_path = self._mapping_path.parent / fn_path
        if not fn_path.exists():
            raise FileNotFoundError(
                f"Template function file not found for chat_type '{chat_type}': {fn_path}"
            )

        spec = importlib.util.spec_from_file_location(f"_chattype_{chat_type}", fn_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise ImportError(
                f"Failed to import template module for chat_type '{chat_type}' "
                f"from {fn_path}: {e}"
            ) from e

        fn = getattr(module, "apply_chat_template", None)
        if fn is None or not callable(fn):
            raise AttributeError(
                f"Template module for chat_type '{chat_type}' must define "
                f"'apply_chat_template(sample, system_prompt) -> list[dict]'. "
                f"File: {fn_path}"
            )

        logger.info("Loaded template function for chat_type '%s' from %s", chat_type, fn_path)
        return fn
