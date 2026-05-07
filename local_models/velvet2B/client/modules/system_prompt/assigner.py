from __future__ import annotations

import random
from enum import Enum


class PromptAssignmentStrategy(str, Enum):
    ALL = "all"
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


class SystemPromptAssigner:
    """Assign system prompt(s) to a sample given a strategy.

    Args:
        strategy: How prompts are assigned to samples.
            - ALL: each sample is paired with every prompt (cartesian product).
            - ROUND_ROBIN: sample at row index i gets prompt i % len(prompts).
            - RANDOM: sample gets a uniformly random prompt.
    """

    def __init__(self, strategy: PromptAssignmentStrategy = PromptAssignmentStrategy.ALL):
        self.strategy = strategy

    def assign(
        self,
        sample: dict,
        prompts: list[str],
        prompt_names: list[str],
        row_idx: int = 0,
    ) -> list[tuple[dict, str | None, str | None]]:
        """Return list of (sample, prompt_content, prompt_id) tuples.

        When no prompts are defined the single tuple (sample, None, None) is returned.
        """
        if not prompts:
            return [(sample, None, None)]

        if self.strategy == PromptAssignmentStrategy.ALL:
            return [
                (sample, content, name)
                for content, name in zip(prompts, prompt_names)
            ]

        if self.strategy == PromptAssignmentStrategy.ROUND_ROBIN:
            i = row_idx % len(prompts)
            return [(sample, prompts[i], prompt_names[i])]

        if self.strategy == PromptAssignmentStrategy.RANDOM:
            i = random.randint(0, len(prompts) - 1)
            return [(sample, prompts[i], prompt_names[i])]

        raise ValueError(f"Unknown strategy: {self.strategy}")
