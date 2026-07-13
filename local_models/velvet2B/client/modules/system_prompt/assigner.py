from __future__ import annotations
import random
from enum import Enum
import logging

# Global fixed seed for reproducible RANDOM assignment. Set to None for non-deterministic behavior.
# Default is 42 to make assignments reproducible by default.
FIXED_SEED = 42

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
        # Instance RNG ensures RANDOM produces varied selections across samples
        # while remaining reproducible when FIXED_SEED is set.
        self._rng = random.Random(FIXED_SEED) if FIXED_SEED is not None else random.Random()
        logger = logging.getLogger(__name__)
        logger.info("SystemPromptAssigner initialized: strategy=%s fixed_seed=%s", strategy, FIXED_SEED)

    def assign(
        self,
        sample: dict,
        prompts: list[str],
        row_idx: int = 0,
    ) -> list[tuple[dict, str | None]]:
        """Return list of (sample, prompt_content) tuples.

        When no prompts are defined the single tuple (sample, None) is returned.
        """
        logger = logging.getLogger(__name__)
        if not prompts:
            logger.debug("assign: no prompts defined, returning single tuple")
            return [(sample, None, None)]



        if self.strategy == PromptAssignmentStrategy.ALL:
            result = [
                (sample, prompts[i])
                for i in range(len(prompts))
            ]
            logger.debug(
                "assign: row_idx=%s prompts=%d strategy=ALL -> assigned_count=%d",
                row_idx,
                len(prompts),
                len(result),
            )
            return result

        if self.strategy == PromptAssignmentStrategy.ROUND_ROBIN:
            i = row_idx % len(prompts)
            result = [(sample, prompts[i])]
            logger.debug(
                "assign: row_idx=%s prompts=%d strategy=ROUND_ROBIN -> assigned_count=%d",
                row_idx,
                len(prompts),
                len(result),
            )
            return result

        if self.strategy == PromptAssignmentStrategy.RANDOM:
            # Use instance RNG so repeated calls produce varied picks across samples.
            i = self._rng.randint(0, len(prompts) - 1)
            result = [(sample, prompts[i])]
            logger.debug(
                "assign: row_idx=%s prompts=%d strategy=RANDOM -> picked_index=%d",
                row_idx,
                len(prompts),
                i,
            )
            return result

        raise ValueError(f"Unknown strategy: {self.strategy}")
