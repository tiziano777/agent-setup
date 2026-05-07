from __future__ import annotations

from pathlib import Path

import yaml

from .recipe_config import RecipeConfig, RecipeEntry


class RecipeLoader:
    """Parse a recipe YAML file into a validated RecipeConfig."""

    @staticmethod
    def load(path: str | Path) -> RecipeConfig:
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        entries: dict[str, RecipeEntry] = {
            uri: RecipeEntry(**entry_data)
            for uri, entry_data in data.get("entries", {}).items()
        }

        return RecipeConfig(
            recipe_id=data.get("id"),
            recipe_name=data.get("name"),
            description=data.get("description"),
            scope=data.get("scope"),
            tasks=data.get("tasks") or [],
            tags=data.get("tags") or [],
            derived_from=data.get("derived_from"),
            entries=entries,
        )
