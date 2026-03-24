"""Evaluation scorers for __AGENT_NAME__.

Scoring functions to evaluate agent output quality.
Can be used standalone or integrated with LangSmith evaluation.
"""


def relevance_score(query: str, response: str) -> float:
    """Compute a relevance score between query and response.

    Returns a float in [0.0, 1.0]. Higher = more relevant.
    Replace with actual evaluation logic (LLM-as-judge, semantic similarity, etc.).
    """
    return 1.0 if query.lower() in response.lower() else 0.5
