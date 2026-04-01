"""Tests for guidance LangGraph tools.

Tier 1: Import/compile checks
Tier 2: Tool metadata checks (no API needed)
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


class TestToolsImport:
    """Verify tools factory is importable."""

    def test_get_guidance_tools_importable(self):
        from src.shared.guidance_toolkit.tools import get_guidance_tools

        assert callable(get_guidance_tools)

    def test_lazy_reexport(self):
        from src.shared.guidance_toolkit import get_guidance_tools

        assert callable(get_guidance_tools)


# ── Tier 2: Tool metadata checks ───────────────────────────────────


class TestToolMetadata:
    """Verify tool names and count (no API needed)."""

    def test_returns_three_tools(self):
        from src.shared.guidance_toolkit.tools import get_guidance_tools

        tools = get_guidance_tools()
        assert len(tools) == 3

    def test_tool_names(self):
        from src.shared.guidance_toolkit.tools import get_guidance_tools

        tools = get_guidance_tools()
        names = [t.name for t in tools]
        assert "guidance_json_generate" in names
        assert "guidance_select" in names
        assert "guidance_regex_generate" in names

    def test_tools_have_descriptions(self):
        from src.shared.guidance_toolkit.tools import get_guidance_tools

        tools = get_guidance_tools()
        for t in tools:
            assert t.description, f"Tool {t.name} has no description"


# ── Tier 3: Integration tests ──────────────────────────────────────


@requires_proxy
class TestToolsIntegration:
    """Integration test: invoke tools against real LLM."""

    def test_guidance_select_tool(self):
        from src.shared.guidance_toolkit.tools import get_guidance_tools

        tools = get_guidance_tools()
        select_tool = next(t for t in tools if t.name == "guidance_select")
        result = select_tool.invoke({"options": "yes,no", "prompt": "Is the sky blue?"})
        assert result in ["yes", "no"]
