"""Tests for guidance LangGraph node factories.

Tier 1: Import/compile checks
Tier 2: Node structure checks with mock state (no API needed)
Tier 3: Integration tests (requires proxy)
"""

from __future__ import annotations

import pytest

try:
    import guidance  # noqa: F401

    GUIDANCE_AVAILABLE = True
except ImportError:
    GUIDANCE_AVAILABLE = False

PROXY_AVAILABLE = False
if GUIDANCE_AVAILABLE:
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:4000/health", timeout=2)
        PROXY_AVAILABLE = True
    except Exception:
        pass

requires_guidance = pytest.mark.skipif(
    not GUIDANCE_AVAILABLE, reason="guidance not installed"
)
requires_proxy = pytest.mark.skipif(
    not PROXY_AVAILABLE, reason="LiteLLM proxy not running (make build)"
)


# ── Tier 1: Import checks ──────────────────────────────────────────


class TestNodesImport:
    """Verify node factories are importable."""

    def test_structured_node_importable(self):
        from src.shared.guidance_toolkit.nodes import create_guidance_structured_node

        assert callable(create_guidance_structured_node)

    def test_select_node_importable(self):
        from src.shared.guidance_toolkit.nodes import create_guidance_select_node

        assert callable(create_guidance_select_node)

    def test_lazy_reexports(self):
        from src.shared.guidance_toolkit import (
            create_guidance_select_node,
            create_guidance_structured_node,
        )

        assert callable(create_guidance_structured_node)
        assert callable(create_guidance_select_node)


# ── Tier 2: Node factory structure checks ───────────────────────────


class TestNodeFactoryStructure:
    """Verify node factories return callables with correct behavior on empty state."""

    def test_structured_node_returns_callable(self):
        from pydantic import BaseModel

        from src.shared.guidance_toolkit.nodes import create_guidance_structured_node

        class Dummy(BaseModel):
            x: str

        node = create_guidance_structured_node(Dummy)
        assert callable(node)

    def test_structured_node_empty_messages_returns_empty(self):
        from pydantic import BaseModel

        from src.shared.guidance_toolkit.nodes import create_guidance_structured_node

        class Dummy(BaseModel):
            x: str

        node = create_guidance_structured_node(Dummy)
        result = node({"messages": []})
        assert result == {"guidance_output": {}}

    def test_structured_node_no_messages_key_returns_empty(self):
        from pydantic import BaseModel

        from src.shared.guidance_toolkit.nodes import create_guidance_structured_node

        class Dummy(BaseModel):
            x: str

        node = create_guidance_structured_node(Dummy)
        result = node({})
        assert result == {"guidance_output": {}}

    def test_select_node_returns_callable(self):
        from src.shared.guidance_toolkit.nodes import create_guidance_select_node

        node = create_guidance_select_node(["a", "b"])
        assert callable(node)

    def test_select_node_empty_messages_returns_empty(self):
        from src.shared.guidance_toolkit.nodes import create_guidance_select_node

        node = create_guidance_select_node(["a", "b"])
        result = node({"messages": []})
        assert result == {"guidance_selection": ""}

    def test_custom_result_key(self):
        from pydantic import BaseModel

        from src.shared.guidance_toolkit.nodes import create_guidance_structured_node

        class Dummy(BaseModel):
            x: str

        node = create_guidance_structured_node(Dummy, result_key="my_output")
        result = node({"messages": []})
        assert "my_output" in result

    def test_custom_query_key_empty(self):
        from src.shared.guidance_toolkit.nodes import create_guidance_select_node

        node = create_guidance_select_node(["a", "b"], query_key="custom_query")
        result = node({})
        assert result == {"guidance_selection": ""}


# ── Tier 3: Integration tests ──────────────────────────────────────


@requires_proxy
class TestNodesIntegration:
    """Integration test: invoke nodes against real LLM."""

    def test_select_node_with_message(self):
        from langchain_core.messages import HumanMessage

        from src.shared.guidance_toolkit.nodes import create_guidance_select_node

        node = create_guidance_select_node(
            ["positive", "negative", "neutral"],
            system_prompt="Classify sentiment.",
        )
        result = node({"messages": [HumanMessage(content="I love this product!")]})
        assert result["guidance_selection"] in ["positive", "negative", "neutral"]
