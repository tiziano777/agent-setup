"""Environment variable validation for agent-setup.

Validates that required environment variables are set and at least
one LLM provider API key is configured. Called at application startup.

Usage:
    # As a module (standalone check):
    python -m src.shared.env_validation

    # From code (e.g., serve.py):
    from src.shared.env_validation import validate_env
    validate_env()
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class _Provider:
    env_var: str
    name: str


_LLM_PROVIDERS: list[_Provider] = [
    _Provider("OPENROUTER_API_KEY", "OpenRouter"),
    _Provider("GOOGLE_API_KEY", "Google AI Studio"),
    _Provider("NVIDIA_API_KEY", "NVIDIA NIM"),
    _Provider("MISTRAL_API_KEY", "Mistral"),
    _Provider("CODESTRAL_API_KEY", "Mistral Codestral"),
    _Provider("VERCEL_API_KEY", "Vercel AI Gateway"),
    _Provider("OPENCODEZEN_API_KEY", "OpenCode Zen"),
    _Provider("CEREBRAS_API_KEY", "Cerebras"),
    _Provider("GROQ_API_KEY", "Groq"),
    _Provider("COHERE_API_KEY", "Cohere"),
    _Provider("GITHUB_TOKEN", "GitHub Models"),
    _Provider("CLOUDFLARE_API_KEY", "Cloudflare Workers AI"),
    _Provider("SILICONFLOW_API_KEY", "SiliconFlow"),
]


def validate_env() -> dict:
    """Validate environment variables.

    Returns
    -------
    dict
        Keys: ``providers_configured`` (list[str]),
        ``warnings`` (list[str]), ``errors`` (list[str]).
    """
    result: dict = {"providers_configured": [], "warnings": [], "errors": []}

    for p in _LLM_PROVIDERS:
        if os.getenv(p.env_var, "").strip():
            result["providers_configured"].append(p.name)

    if not result["providers_configured"]:
        result["errors"].append(
            "Nessuna API key LLM trovata. "
            "Configura almeno un provider in .env (vedi .env.template)."
        )

    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        result["warnings"].append(
            f".env non trovato in {env_path}. "
            "Copia dal template: cp .env.template .env"
        )

    return result


def print_validation_report(result: dict) -> None:
    """Print a human-readable validation report."""
    print("=" * 50)
    print("Environment Validation Report")
    print("=" * 50)

    if result["providers_configured"]:
        n = len(result["providers_configured"])
        print(f"\nLLM Provider configurati ({n}):")
        for p in result["providers_configured"]:
            print(f"  + {p}")
    else:
        print("\nLLM Provider: NESSUNO CONFIGURATO")

    if result["warnings"]:
        print(f"\nWarning ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  ! {w}")

    if result["errors"]:
        print(f"\nErrori ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  X {e}")

    if not result["errors"] and not result["warnings"]:
        print("\nTutti i controlli superati.")

    print("=" * 50)


if __name__ == "__main__":
    r = validate_env()
    print_validation_report(r)
    if r["errors"]:
        sys.exit(1)
