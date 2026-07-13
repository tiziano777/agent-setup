from __future__ import annotations
from pathlib import Path
import yaml
from .recipe_config import RecipeConfig, RecipeEntry

from pathlib import Path
import yaml

class RecipeLoader:
    """Parse a recipe YAML file or mapping into a validated RecipeConfig.

    Accepts either a path to a YAML file or an already-loaded mapping (dict).
    Also supports configuration files that embed the recipe under a top-level
    'recipe' key (e.g., config.yml).
    """

    @staticmethod
    def load(path: str | Path | dict) -> RecipeConfig:
        # Accept an already-parsed mapping
        if isinstance(path, dict):
            data = path
        else:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}

        # If the recipe is embedded under a top-level 'recipe' key, use it
        if isinstance(data, dict) and "recipe" in data and isinstance(data["recipe"], dict):
            data = data["recipe"]

        raw_entries = data.get("entries", []) or []
        
        # Costruiamo la lista di oggetti RecipeEntry
        entries: list[RecipeEntry] = []
        for entry_data in raw_entries:
            if isinstance(entry_data, dict):
                entries.append(RecipeEntry(**entry_data))

        # Istanziamo RecipeConfig passando la lista. 
        # Pydantic farà il resto del lavoro di validazione sui campi opzionali.
        return RecipeConfig(
            id=data.get("id"),
            name=data.get("name"),
            description=data.get("description"),
            scope=data.get("scope"),
            # Usiamo None se assenti per non forzare liste vuote se l'utente non le dichiara nel DB
            tasks=data.get("tasks"), 
            tags=data.get("tags"),
            derived_from=data.get("derived_from"),
            entries=entries,
        )