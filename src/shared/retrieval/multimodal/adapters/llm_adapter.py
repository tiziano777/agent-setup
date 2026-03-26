"""Adapters bridging get_llm() ChatOpenAI to RAG-Anything async callables.

RAG-Anything expects bare async functions for ``llm_model_func`` and
``vision_model_func``.  These adapters wrap the project's
:func:`src.shared.llm.get_llm` so that **all** LLM calls still route
through the LiteLLM proxy.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_llm_model_func(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> Any:
    """Build the async ``llm_model_func`` expected by RAGAnything.

    Signature::

        async (prompt, system_prompt=None, history_messages=[], **kw) -> str
    """
    from src.shared.llm import DEFAULT_MODEL, get_llm

    llm = get_llm(model=model or DEFAULT_MODEL, temperature=temperature, max_tokens=max_tokens)

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        response = await llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)

    return llm_model_func


def create_vision_model_func(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> Any:
    """Build the async ``vision_model_func`` expected by RAGAnything.

    Three dispatch paths depending on which arguments are provided:

    1. ``messages`` list provided -> forward as-is (multi-image VLM).
    2. ``image_data`` (base64 string) provided -> build multimodal message.
    3. Neither -> text-only fallback.
    """
    from src.shared.llm import DEFAULT_MODEL, get_llm

    llm = get_llm(model=model or DEFAULT_MODEL, temperature=temperature, max_tokens=max_tokens)

    async def vision_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        image_data: str | None = None,
        messages: list[dict] | None = None,
        **kwargs: Any,
    ) -> str:
        # Path 1: pre-built multimodal messages
        if messages is not None:
            final: list[dict] = list(messages)
            if system_prompt and (not final or final[0].get("role") != "system"):
                final.insert(0, {"role": "system", "content": system_prompt})
            response = await llm.ainvoke(final)
            return response.content if hasattr(response, "content") else str(response)

        # Path 2: base64 image_data
        if image_data is not None:
            msg_list: list[dict] = []
            if system_prompt:
                msg_list.append({"role": "system", "content": system_prompt})
            if history_messages:
                msg_list.extend(history_messages)
            msg_list.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                        },
                    ],
                }
            )
            response = await llm.ainvoke(msg_list)
            return response.content if hasattr(response, "content") else str(response)

        # Path 3: text-only fallback
        msg_list = []
        if system_prompt:
            msg_list.append({"role": "system", "content": system_prompt})
        if history_messages:
            msg_list.extend(history_messages)
        msg_list.append({"role": "user", "content": prompt})

        response = await llm.ainvoke(msg_list)
        return response.content if hasattr(response, "content") else str(response)

    return vision_model_func
