"""Token budget tracker for LLM calls during sweeps.

Tracks cumulative token usage and warns when the budget approaches the limit,
enabling fallback to deterministic strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenTracker:
    """Tracks cumulative token usage and enforces budget limits."""

    max_total_tokens: int = 500_000
    prompt_tokens: int = field(default=0, init=False)
    completion_tokens: int = field(default=0, init=False)
    calls: int = field(default=0, init=False)
    _warned: bool = field(default=False, init=False, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def budget_remaining(self) -> int:
        return max(0, self.max_total_tokens - self.total_tokens)

    @property
    def exhausted(self) -> bool:
        return self.total_tokens >= self.max_total_tokens

    def record(self, usage: dict) -> None:
        """Record token usage from a single LLM call.

        Args:
            usage: dict with ``prompt_tokens`` and ``completion_tokens`` keys
                   (standard OpenAI / langchain format).
        """
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.calls += 1

    def can_afford(self, estimated_tokens: int) -> bool:
        """Check whether budget allows a call with estimated token count."""
        return (self.total_tokens + estimated_tokens) <= self.max_total_tokens

    def to_state_dict(self) -> dict[str, int]:
        """Serialize for LangGraph state embedding."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "calls": self.calls,
            "total_tokens": self.total_tokens,
            "budget_remaining": self.budget_remaining,
        }

    def summary(self) -> str:
        return (
            f"Token: {self.total_tokens:,}/{self.max_total_tokens:,} "
            f"(prompt={self.prompt_tokens:,}, completion={self.completion_tokens:,}, "
            f"calls={self.calls})"
        )
