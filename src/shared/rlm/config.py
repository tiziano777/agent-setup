"""RLM (Recursive Language Models) configuration and settings."""

import os
from dataclasses import dataclass, field


@dataclass
class RLMSettings:
    """Configuration for RLM integration.

    RLM enables recursive problem-solving through programmatic decomposition,
    running code in isolated environments to examine, decompose, and recursively
    call LLMs on large contexts (50k+ lines).
    """

    # Backend config (via LiteLLM proxy)
    backend_type: str = field(
        default_factory=lambda: os.getenv("RLM_BACKEND", "openai")
    )
    model_name: str = field(default_factory=lambda: os.getenv("RLM_MODEL", "llm"))
    api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "sk-not-needed")
    )
    litellm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LITELLM_BASE_URL", "http://localhost:4000/v1"
        )
    )

    # Execution environment config
    environment: str = field(default="local")  # local | docker | modal | e2b | prime
    max_iterations: int = field(default=10)  # Max steps per RLM invocation
    max_depth: int = field(default=2)  # Max recursion depth

    # Context handling
    enable_compaction: bool = field(default=True)  # Auto-compress >85% full context
    compaction_threshold_pct: float = field(default=0.85)

    # Logging & observability
    log_dir: str = field(default_factory=lambda: os.getenv("RLM_LOG_DIR", "./logs"))
    verbose: bool = field(
        default_factory=lambda: os.getenv("RLM_VERBOSE", "false").lower() == "true"
    )

    # Phoenix OTEL tracing
    phoenix_enabled: bool = field(
        default_factory=lambda: os.getenv("PHOENIX_TRACING_ENABLED", "true").lower()
        == "true"
    )
    phoenix_project_name: str = field(
        default_factory=lambda: os.getenv("PHOENIX_PROJECT_NAME", "agent-setup")
    )

    def to_rlm_kwargs(self) -> dict:
        """Convert settings to RLM() kwargs."""
        return {
            "backend": self.backend_type,
            "backend_kwargs": {
                "model_name": self.model_name,
                "api_key": self.api_key,
                "base_url": self.litellm_base_url,
            },
            "environment": self.environment,
            "max_iterations": self.max_iterations,
            "max_depth": self.max_depth,
            "verbose": self.verbose,
            "compaction": self.enable_compaction,
            "compaction_threshold_pct": self.compaction_threshold_pct,
        }
