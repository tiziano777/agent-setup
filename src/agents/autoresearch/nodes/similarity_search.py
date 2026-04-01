"""Find similar experiments via Cognee knowledge graph or PostgreSQL."""

from __future__ import annotations

from typing import Any

from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import KnowledgeRepository
from src.agents.autoresearch.states.state import AutoresearchState


def similarity_search(state: AutoresearchState) -> dict[str, Any]:
    """Search for experiments with similar setups to inform agent decisions.

    Tries Cognee knowledge graph first, falls back to PostgreSQL knowledge
    table for exact-match retrieval.
    """
    sweep_config = state.get("sweep_config", {})
    base_setup = str(sweep_config.get("base_setup", ""))
    metric_name = sweep_config.get("metric", {}).get("name", "")

    results: list[dict[str, Any]] = []

    # Try Cognee semantic search if available
    try:
        from src.shared.cognee_toolkit.memory import CogneeMemory

        memory = CogneeMemory()
        query = (
            f"hyperparameter optimization for {base_setup} "
            f"optimizing {metric_name}"
        )
        cognee_results = memory.search_sync(query, top_k=5)
        if cognee_results:
            for r in cognee_results:
                results.append({
                    "source": "cognee",
                    "content": str(r),
                })
    except Exception:
        pass  # Cognee not available or not configured

    # Always supplement with PostgreSQL knowledge
    connector = PostgresConnector()
    knowledge_repo = KnowledgeRepository(connector)
    prior = knowledge_repo.find_relevant(base_setup, metric_name)
    for entry in prior:
        results.append({
            "source": "knowledge_db",
            "sweep_name": entry.sweep_name,
            "best_config": entry.best_config,
            "best_metric_value": entry.best_metric_value,
            "parameter_importance": entry.parameter_importance,
            "recommendations": entry.parameter_recommendations,
        })

    return {"similar_experiments": results}
