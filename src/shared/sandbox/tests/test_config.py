"""Unit tests for sandbox configuration (no Docker required)."""

from src.shared.sandbox.config import SandboxSettings


class TestSandboxSettings:
    def test_defaults(self):
        s = SandboxSettings()
        assert s.image == "python:3.11-slim"
        assert s.timeout == 30
        assert s.mem_limit == "256m"
        assert s.cpu_limit == 0.5
        assert s.network_mode == "none"
        assert s.pids_limit == 64
        assert s.user == "nobody"
        assert s.max_output_chars == 10_000

    def test_custom_values(self):
        s = SandboxSettings(image="python:3.12-slim", timeout=60, mem_limit="512m")
        assert s.image == "python:3.12-slim"
        assert s.timeout == 60
        assert s.mem_limit == "512m"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_IMAGE", "ubuntu:22.04")
        monkeypatch.setenv("SANDBOX_TIMEOUT", "120")
        monkeypatch.setenv("SANDBOX_MEM_LIMIT", "1g")
        monkeypatch.setenv("SANDBOX_CPU_LIMIT", "2.0")
        monkeypatch.setenv("SANDBOX_WORKSPACE_SIZE", "256M")
        monkeypatch.setenv("SANDBOX_NETWORK", "bridge")
        s = SandboxSettings()
        assert s.image == "ubuntu:22.04"
        assert s.timeout == 120
        assert s.mem_limit == "1g"
        assert s.cpu_limit == 2.0
        assert s.workspace_size == "256M"
        assert s.network_mode == "bridge"
