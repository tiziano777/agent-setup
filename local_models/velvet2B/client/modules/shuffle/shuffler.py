"""Dataset block-shuffle strategies for DPO training.

Splits dataset into fixed-size blocks grouped by _source_uri,
then orders blocks according to the chosen strategy.
"""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from enum import Enum
from itertools import zip_longest

from datasets import Dataset

logger = logging.getLogger(__name__)

FIXED_SEED = 42


class ShuffleStrategy(str, Enum):
    RANDOM = "random"
    CIRCULAR = "circular"


class DatasetShuffler:
    """Reorder a HuggingFace Dataset by source-aware block strategy.

    Args:
        strategy: How blocks are ordered after splitting.
            - RANDOM: pseudo-random permutation of all blocks (reproducible via seed).
            - CIRCULAR: round-robin interleaving — one block per source at a time.
        block_size: Number of rows per block.
        seed: RNG seed for RANDOM strategy.
    """

    def __init__(self, strategy: ShuffleStrategy, block_size: int, seed: int = FIXED_SEED):
        self.strategy = strategy
        self.block_size = block_size
        self._rng = random.Random(seed)
        logger.info(
            "DatasetShuffler initialized: strategy=%s block_size=%d seed=%d",
            strategy, block_size, seed,
        )

    def shuffle(self, dataset: Dataset) -> Dataset:
        """Return a reordered copy of *dataset* according to the block strategy."""
        source_col = "_source_uri"
        if source_col not in dataset.column_names:
            logger.warning("Column '%s' not found — returning dataset unchanged.", source_col)
            return dataset

        # 1. Group row indices by source
        source_indices: dict[str, list[int]] = defaultdict(list)
        for idx, uri in enumerate(dataset[source_col]):
            source_indices[uri].append(idx)

        # 2. Split each source group into blocks of block_size
        source_blocks: dict[str, list[list[int]]] = {}
        for uri, indices in source_indices.items():
            blocks = [
                indices[i : i + self.block_size]
                for i in range(0, len(indices), self.block_size)
            ]
            source_blocks[uri] = blocks

        # 3. Order blocks according to strategy
        if self.strategy == ShuffleStrategy.RANDOM:
            ordered = self._random_order(source_blocks)
        elif self.strategy == ShuffleStrategy.CIRCULAR:
            ordered = self._circular_order(source_blocks)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        # 4. Flatten block list into final index order
        final_indices = [idx for block in ordered for idx in block]

        logger.info(
            "Shuffle complete: %d rows -> %d blocks (strategy=%s)",
            len(dataset), len(ordered), self.strategy,
        )
        return dataset.select(final_indices)

    def _random_order(self, source_blocks: dict[str, list[list[int]]]) -> list[list[int]]:
        """Collect all blocks, shuffle randomly."""
        all_blocks = [block for blocks in source_blocks.values() for block in blocks]
        self._rng.shuffle(all_blocks)
        return all_blocks

    def _circular_order(self, source_blocks: dict[str, list[list[int]]]) -> list[list[int]]:
        """Round-robin: take one block from each source at a time."""
        block_lists = list(source_blocks.values())
        ordered: list[list[int]] = []
        for row in zip_longest(*block_lists):
            for block in row:
                if block is not None:
                    ordered.append(block)
        return ordered
