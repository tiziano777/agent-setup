"""Unit tests for guidance toolkit configuration (no guidance library needed)."""

from __future__ import annotations

import pytest

try:
    import guidance  # noqa: F401

    GUIDANCE_AVAILABLE = True
except ImportError:
    GUIDANCE_AVAILABLE = False

requires_guidance = pytest.mark.skipif(
    not GUIDANCE_AVAILABLE, reason="guidance not installed"
)


class TestGuidanceSettings:
    """Test GuidanceSettings dataclass defaults and overrides."""

    def test_defaults(self):
        from src.shared.guidance_toolkit.config import GuidanceSettings

        s = GuidanceSettings()
        assert s.litellm_base_url == "http://localhost:4000/v1"
        assert s.default_model == "llm"
        assert s.api_key == "sk-not-needed"
        assert s.default_temperature == 0.7
        assert s.default_max_tokens == 2048

    def test_custom_values(self):
        from src.shared.guidance_toolkit.config import GuidanceSettings

        s = GuidanceSettings(
            default_model="gpt-4",
            default_temperature=0.3,
            default_max_tokens=4096,
        )
        assert s.default_model == "gpt-4"
        assert s.default_temperature == 0.3
        assert s.default_max_tokens == 4096

    def test_env_override(self, monkeypatch):
        from src.shared.guidance_toolkit.config import GuidanceSettings

        monkeypatch.setenv("LITELLM_BASE_URL", "http://custom:8000/v1")
        monkeypatch.setenv("DEFAULT_MODEL", "custom-model")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        s = GuidanceSettings()
        assert s.litellm_base_url == "http://custom:8000/v1"
        assert s.default_model == "custom-model"
        assert s.api_key == "sk-test-key"


@requires_guidance
class TestSetupGuidance:
    """Test setup_guidance() idempotent configuration."""

    def test_setup_returns_settings(self):
        import src.shared.guidance_toolkit.config as cfg

        cfg._CONFIGURED = False
        cfg._SETTINGS = None
        try:
            result = cfg.setup_guidance()
            assert isinstance(result, cfg.GuidanceSettings)
            assert cfg._CONFIGURED is True
        finally:
            cfg._CONFIGURED = False
            cfg._SETTINGS = None

    def test_setup_with_custom_settings(self):
        import src.shared.guidance_toolkit.config as cfg

        cfg._CONFIGURED = False
        cfg._SETTINGS = None
        try:
            custom = cfg.GuidanceSettings(default_temperature=0.1)
            result = cfg.setup_guidance(settings=custom)
            assert result.default_temperature == 0.1
        finally:
            cfg._CONFIGURED = False
            cfg._SETTINGS = None

    def test_get_settings_auto_configures(self):
        import src.shared.guidance_toolkit.config as cfg

        cfg._CONFIGURED = False
        cfg._SETTINGS = None
        try:
            result = cfg.get_settings()
            assert isinstance(result, cfg.GuidanceSettings)
            assert cfg._CONFIGURED is True
        finally:
            cfg._CONFIGURED = False
            cfg._SETTINGS = None
