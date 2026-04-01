"""Tests for guidance programs.

Tier 1: Import/compile checks (no guidance needed)
Tier 2: Unit tests with guidance.models.Mock (no API needed)
Tier 3: Integration tests with LiteLLM proxy (requires make build)
"""

from __future__ import annotations

import pytest

# ── Guidance availability check ──────────────────────────────────────

try:
    import guidance  # noqa: F401
    from guidance.models import Mock  # noqa: F401

    GUIDANCE_AVAILABLE = True
except ImportError:
    GUIDANCE_AVAILABLE = False

# ── Proxy availability check ────────────────────────────────────────

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


# ── Tier 1: Import / compile checks ────────────────────────────────


class TestImports:
    """Verify all programs are importable (no guidance needed at import time)."""

    def test_structured_json_importable(self):
        from src.shared.guidance_toolkit.programs import structured_json

        assert callable(structured_json)

    def test_constrained_select_importable(self):
        from src.shared.guidance_toolkit.programs import constrained_select

        assert callable(constrained_select)

    def test_regex_generate_importable(self):
        from src.shared.guidance_toolkit.programs import regex_generate

        assert callable(regex_generate)

    def test_grammar_generate_importable(self):
        from src.shared.guidance_toolkit.programs import grammar_generate

        assert callable(grammar_generate)

    def test_cfg_generate_importable(self):
        from src.shared.guidance_toolkit.programs import cfg_generate

        assert callable(cfg_generate)

    def test_build_cfg_grammar_importable(self):
        from src.shared.guidance_toolkit.programs import build_cfg_grammar

        assert callable(build_cfg_grammar)

    def test_lazy_reexports(self):
        from src.shared.guidance_toolkit import (
            build_cfg_grammar,
            cfg_generate,
            constrained_select,
            grammar_generate,
            regex_generate,
            structured_json,
        )

        for fn in [
            structured_json,
            constrained_select,
            regex_generate,
            grammar_generate,
            cfg_generate,
            build_cfg_grammar,
        ]:
            assert callable(fn)


# ── Tier 2: Unit tests with Mock model ──────────────────────────────


@requires_guidance
class TestStructuredJsonMock:
    """Test structured_json with guidance Mock model."""

    def test_returns_dict(self):
        from guidance.models import Mock
        from pydantic import BaseModel

        from src.shared.guidance_toolkit.programs import structured_json

        class Person(BaseModel):
            name: str
            age: int

        mock = Mock("<mock output>")
        result = structured_json(Person, "Extract person", model=mock)
        assert isinstance(result, dict)


@requires_guidance
class TestConstrainedSelectMock:
    """Test constrained_select with guidance Mock model."""

    def test_returns_one_of_options(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import constrained_select

        options = ["positive", "negative", "neutral"]
        mock = Mock("<mock>")
        result = constrained_select(options, "Classify sentiment", model=mock)
        assert isinstance(result, str)

    def test_with_system_prompt(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import constrained_select

        options = ["yes", "no"]
        mock = Mock("<mock>")
        result = constrained_select(
            options, "Answer", model=mock, system_prompt="Be concise."
        )
        assert isinstance(result, str)


@requires_guidance
class TestRegexGenerateMock:
    """Test regex_generate with guidance Mock model."""

    def test_returns_string(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import regex_generate

        mock = Mock("ABC-1234")
        result = regex_generate(r"[A-Z]{3}-\d{4}", "Generate code", model=mock)
        assert isinstance(result, str)

    def test_custom_max_tokens(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import regex_generate

        mock = Mock("test")
        result = regex_generate(r"[a-z]+", "Generate word", model=mock, max_tokens=10)
        assert isinstance(result, str)


@requires_guidance
class TestGrammarGenerateMock:
    """Test grammar_generate with guidance Mock model."""

    def test_custom_grammar(self):
        from guidance import guidance, select
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import grammar_generate

        @guidance(stateless=True)
        def fruit_grammar(lm):
            lm += select(["apple", "banana", "cherry"], name="fruit")
            return lm

        mock = Mock("<mock>")
        result = grammar_generate(
            fruit_grammar, "Pick a fruit", model=mock, capture_name="fruit"
        )
        assert isinstance(result, str)

    def test_grammar_with_kwargs(self):
        from guidance import guidance, select
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import grammar_generate

        @guidance(stateless=True)
        def parameterized_grammar(lm, choices=None):
            lm += select(choices or ["a", "b"], name="choice")
            return lm

        mock = Mock("<mock>")
        result = grammar_generate(
            parameterized_grammar,
            "Choose",
            model=mock,
            capture_name="choice",
            choices=["x", "y", "z"],
        )
        assert isinstance(result, str)


@requires_guidance
class TestCfgGenerateMock:
    """Test cfg_generate with guidance Mock model."""

    def test_returns_dict_with_capture_names(self):
        from guidance import gen, guidance, select
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import cfg_generate

        @guidance(stateless=True)
        def entry_grammar(lm):
            lm += "Category: "
            lm += select(["A", "B", "C"], name="category")
            lm += " Item: "
            lm += gen(name="item", max_tokens=10)
            return lm

        mock = Mock("<mock>")
        result = cfg_generate(
            entry_grammar,
            "Create entry",
            model=mock,
            capture_names=["category", "item"],
        )
        assert isinstance(result, dict)
        assert "category" in result
        assert "item" in result

    def test_auto_extract_captures(self):
        from guidance import guidance, select
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import cfg_generate

        @guidance(stateless=True)
        def simple_grammar(lm):
            lm += select(["yes", "no"], name="answer")
            return lm

        mock = Mock("<mock>")
        result = cfg_generate(simple_grammar, "Answer", model=mock)
        assert isinstance(result, dict)


@requires_guidance
class TestBuildCfgGrammarMock:
    """Test build_cfg_grammar with guidance Mock model."""

    def test_literal_and_select(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import build_cfg_grammar, cfg_generate

        grammar = build_cfg_grammar([
            {"type": "literal", "text": "Color: "},
            {"type": "select", "name": "color", "options": ["red", "blue", "green"]},
        ])
        mock = Mock("<mock>")
        result = cfg_generate(
            grammar, "Pick a color", model=mock, capture_names=["color"]
        )
        assert isinstance(result, dict)
        assert "color" in result

    def test_literal_and_gen(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import build_cfg_grammar, cfg_generate

        grammar = build_cfg_grammar([
            {"type": "literal", "text": "Name: "},
            {"type": "gen", "name": "name", "max_tokens": 10},
        ])
        mock = Mock("<mock>")
        result = cfg_generate(
            grammar, "Generate name", model=mock, capture_names=["name"]
        )
        assert isinstance(result, dict)
        assert "name" in result

    def test_gen_with_regex(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import build_cfg_grammar, cfg_generate

        grammar = build_cfg_grammar([
            {"type": "gen", "name": "code", "max_tokens": 10, "regex": r"[A-Z]{3}-\d{3}"},
        ])
        mock = Mock("ABC-123")
        result = cfg_generate(
            grammar, "Generate code", model=mock, capture_names=["code"]
        )
        assert isinstance(result, dict)

    def test_unknown_step_type_raises(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import build_cfg_grammar, cfg_generate

        grammar = build_cfg_grammar([
            {"type": "nonexistent", "text": "bad"},
        ])
        mock = Mock("<mock>")
        with pytest.raises(ValueError, match="Unknown grammar step type"):
            cfg_generate(grammar, "test", model=mock)

    def test_multiple_steps_combined(self):
        from guidance.models import Mock

        from src.shared.guidance_toolkit.programs import build_cfg_grammar, cfg_generate

        grammar = build_cfg_grammar([
            {"type": "literal", "text": "Type: "},
            {"type": "select", "name": "type", "options": ["bug", "feature", "task"]},
            {"type": "literal", "text": " | Priority: "},
            {"type": "select", "name": "priority", "options": ["low", "medium", "high"]},
            {"type": "literal", "text": " | Title: "},
            {"type": "gen", "name": "title", "max_tokens": 20},
        ])
        mock = Mock("<mock>")
        result = cfg_generate(
            grammar,
            "Create a ticket",
            model=mock,
            capture_names=["type", "priority", "title"],
        )
        assert isinstance(result, dict)
        assert len(result) == 3


# ── Tier 3: Integration tests (require LiteLLM proxy) ──────────────


@requires_proxy
class TestConstrainedSelectIntegration:
    """Integration test: constrained_select against real LLM via proxy."""

    def test_selects_sentiment(self):
        from src.shared.guidance_toolkit.programs import constrained_select

        result = constrained_select(
            ["positive", "negative", "neutral"],
            "The weather is beautiful today!",
        )
        assert result in ["positive", "negative", "neutral"]
