"""Evaluation scorers for rag_agent.

Scoring functions to evaluate RAG output quality: groundedness
(does the answer use retrieved context?) and source coverage.
"""


def groundedness_score(context: str, response: str) -> float:
    """Check if the response is grounded in the context.

    Returns 1.0 if at least one context sentence appears (partially) in the response,
    0.0 otherwise. A simple heuristic; replace with LLM-as-judge for production.
    """
    if not context or not response:
        return 0.0
    context_sentences = [s.strip() for s in context.split(".") if len(s.strip()) > 10]
    response_lower = response.lower()
    for sentence in context_sentences:
        # Check if key phrases from context appear in response
        words = sentence.lower().split()
        if len(words) >= 3:
            # Check if a 3-word window from context appears in response
            for i in range(len(words) - 2):
                trigram = " ".join(words[i : i + 3])
                if trigram in response_lower:
                    return 1.0
    return 0.0


def source_coverage_score(expected_sources: list[str], actual_sources: list[str]) -> float:
    """Check what fraction of expected sources were retrieved.

    Returns a float in [0.0, 1.0].
    """
    if not expected_sources:
        return 1.0
    if not actual_sources:
        return 0.0
    hits = sum(1 for s in expected_sources if s in actual_sources)
    return hits / len(expected_sources)
